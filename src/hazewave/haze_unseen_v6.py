"""V6 narrow real-audio evidence evaluation; never an authority to modify audio.

New cases are not reused from the V5 12 dB guided calibration. All labels
are verifier-only and NEVER sent to the Qwen request. The unseen cohort
becomes development data as soon as evaluated. Sealed reservations are NOT run.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import struct
import subprocess
import sys
import time
import wave
from typing import Any, Callable, Mapping
from urllib.request import Request, ProxyHandler, build_opener
from hazewave.harness import HazewaveTask, route_task, issue_authorization, validate_authorization
from hazewave.actions_slm_multicase import hash_model_request, _NoRedirect, classify_json_response_shape
from hazewave.actions_slm_runner import (
    _sha256, _volumedetect, verify_llama_response, validate_model_manifest,
    verify_model_bytes, authorize_runner, write_receipt, _memory_available, LOOPBACK,
)

class CohortError(ValueError):
    pass

# Fixed prior to any real V6 inference. This list is a development/evaluation
# baseline, not an untouched final qualification holdout after first execution.
CASES = (
    {"id":"music_loss_5db","signal":"music","transform":"0.56",
     "task":"PRESERVE_REFERENCE_LEVEL","expected":"ATTENUATION_DETECTED","kind":"signal"},
    {"id":"speech_gain_4db","signal":"voice_like","transform":"1.585",
     "task":"PRESERVE_REFERENCE_LEVEL","expected":"GAIN_INCREASE_DETECTED","kind":"signal"},
    {"id":"loud_clean","signal":"loud","transform":"1.0",
     "task":"PRESERVE_REFERENCE_LEVEL","expected":"NO_ISSUE_DETECTED","kind":"signal"},
    {"id":"silence_1s","signal":"tone460","transform":"0.0",
     "task":"PRESERVE_SIGNAL","expected":"SILENCE_DETECTED","kind":"signal"},
    {"id":"clip_700hz","signal":"tone700","transform":"10.0",
     "task":"AVOID_PCM_CLIPPING","expected":"CLIPPING_DETECTED","kind":"signal"},
    {"id":"near_silence","signal":"tone350","transform":"0.0003",
     "task":"PRESERVE_SIGNAL","expected":"NEAR_SILENCE_DETECTED","kind":"signal"},
    {"id":"clean_transient","signal":"transient","transform":"1.0",
     "task":"AVOID_PCM_CLIPPING","expected":"NO_ISSUE_DETECTED","kind":"signal"},
    {"id":"threshold_ambiguous","signal":"tone530","transform":"0.89",
     "task":"PRESERVE_REFERENCE_LEVEL","expected":"INSUFFICIENT_EVIDENCE","kind":"signal"},
    {"id":"missing_reference","signal":"missing","transform":"none",
     "task":"PRESERVE_REFERENCE_LEVEL","expected":"INSUFFICIENT_EVIDENCE","kind":"missing"},
    {"id":"ood_audio_request","signal":"ood","transform":"none",
     "task":"UNAUTHORIZED_ACTION","expected":"OUT_OF_DOMAIN","kind":"ood"},
)
# Reserved, *never executed* or used for tuning within this V6 probe.
# No correct labels are present for these future independent fixtures.
RESERVED_HOLDOUTS = ("reserved_polyphonic_17","reserved_voice_pulse_23",
                     "reserved_transient_41","reserved_ambiguous_53")

FINDINGS=("ATTENUATION_DETECTED","GAIN_INCREASE_DETECTED","NO_ISSUE_DETECTED",
          "SILENCE_DETECTED","NEAR_SILENCE_DETECTED","CLIPPING_DETECTED",
          "INSUFFICIENT_EVIDENCE","OUT_OF_DOMAIN")
ACTIONS=("REVIEW_GAIN_STAGE","RESTORE_SIGNAL_PATH","REDUCE_GAIN_OR_LIMIT",
         "NO_ACTION","REQUEST_MEASUREMENTS","REQUEST_HUMAN_REVIEW")
MAPPING={
    "ATTENUATION_DETECTED":"REVIEW_GAIN_STAGE",
    "GAIN_INCREASE_DETECTED":"REVIEW_GAIN_STAGE",
    "NO_ISSUE_DETECTED":"NO_ACTION",
    "SILENCE_DETECTED":"RESTORE_SIGNAL_PATH",
    "NEAR_SILENCE_DETECTED":"RESTORE_SIGNAL_PATH",
    "CLIPPING_DETECTED":"REDUCE_GAIN_OR_LIMIT",
    "INSUFFICIENT_EVIDENCE":"REQUEST_MEASUREMENTS",
    "OUT_OF_DOMAIN":"REQUEST_HUMAN_REVIEW",
}
KEYS={
    "ATTENUATION_DETECTED":"attenuation_db",
    "GAIN_INCREASE_DETECTED":"attenuation_db",
    "NO_ISSUE_DETECTED":"attenuation_db",
    "SILENCE_DETECTED":"silence_duration_s",
    "NEAR_SILENCE_DETECTED":"nonzero_sample_fraction",
    "CLIPPING_DETECTED":"clipped_sample_fraction",
    "INSUFFICIENT_EVIDENCE":"attenuation_db",
    "OUT_OF_DOMAIN":"attenuation_db",
}

def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, check=True, capture_output=True,
                              text=True, timeout=22)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise CohortError("FFMPEG_EVIDENCE_FAILED") from exc

def _source_audio(path: Path, signal: str) -> None:
    rate=16000
    with wave.open(str(path),"wb") as handle:
        handle.setnchannels(1);handle.setsampwidth(2);handle.setframerate(rate)
        pcm=bytearray()
        for i in range(rate):
            t=i/rate
            if signal=="music":
                amp=0.13*(math.sin(2*math.pi*330*t)+
                          0.55*math.sin(2*math.pi*495*t)+
                          0.35*math.sin(2*math.pi*660*t))
            elif signal=="voice_like":
                # AM harmonic synthetic voice-like surrogate, NOT human speech.
                env=0.35+0.65*(0.5+0.5*math.sin(2*math.pi*4.2*t))
                amp=0.12*env*(math.sin(2*math.pi*183*t)+
                               0.45*math.sin(2*math.pi*366*t))
            elif signal=="loud":
                amp=0.90*math.sin(2*math.pi*617*t)
            elif signal=="transient":
                amp=0.89 if i==6400 else 0.0
            else:
                f={"tone460":460,"tone700":700,"tone350":350,"tone530":530}.get(signal)
                if f is None:
                    raise CohortError("SIGNAL_UNRECOGNIZED")
                amp=0.2*math.sin(2*math.pi*f*t)
            sample=int(round(max(-0.999969,min(0.999969,amp))*32767))
            pcm.extend(struct.pack("<h",sample))
        handle.writeframes(bytes(pcm))

def _sample_stats(path: Path) -> dict[str,float]:
    with wave.open(str(path),"rb") as h:
        if (h.getsampwidth(),h.getnchannels(),h.getframerate())!=(2,1,16000):
            raise CohortError("PCM_CONTRACT_INVALID")
        raw=h.readframes(h.getnframes())
    vals=[x[0] for x in struct.iter_unpack("<h",raw)]
    if not vals:
        raise CohortError("PCM_EMPTY")
    return {
        "clipped_sample_fraction":round(sum(abs(x)>=32760 for x in vals)/len(vals),6),
        "nonzero_sample_fraction":round(sum(x!=0 for x in vals)/len(vals),6),
        "peak_fraction":round(max(abs(x) for x in vals)/32768,6),
    }

def _silence(path: Path) -> float:
    p=_run(["ffmpeg","-nostdin","-hide_banner","-i",str(path),
            "-af","silencedetect=noise=-50dB:d=0.2","-f","null","-"])
    values=re.findall(r"silence_duration:\s*(\d+(?:\.\d+)?)",p.stderr)
    return round(max(map(float,values),default=0),3)

def make_fixture_evidence(root: Path) -> dict[str,dict[str,Any]]:
    root.mkdir(parents=True,exist_ok=True)
    result={}
    for spec in CASES:
        cid=spec["id"]
        if spec["kind"]!="signal":
            result[cid]={
                "task":spec["task"], "proof_status":"INELIGIBLE",
                "measurement_scope":"NO_AUTHORIZED_COMPARABLE_AUDIO"}
            continue
        folder=root/cid
        folder.mkdir(parents=True,exist_ok=False)
        a,b=folder/"ref.wav",folder/"processed.wav"
        _source_audio(a,spec["signal"])
        _run(["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
              "-i",str(a),"-af","volume="+spec["transform"],"-ar","16000",
              "-ac","1","-c:a","pcm_s16le",str(b)])
        stats=_sample_stats(b)
        # No false "different audio" requirement: clean cases are legitimate.
        source=_volumedetect(a)
        processed=None if stats["nonzero_sample_fraction"]==0 else _volumedetect(b)
        refstats=_sample_stats(a)
        delta=(round(source-processed,3) if processed is not None else None)
        evidence={
            "schema":"HazewaveUnseenAudioEvidence/v1",
            "task":spec["task"],"proof_status":"VERIFIED",
            "measurement_method":"FFMPEG_VOLUMEDETECT_DBFS_PCM16",
            "reference_sha256":_sha256(a),
            "processed_sha256":_sha256(b),
            "mean_reference_dbfs":source,
            "mean_processed_dbfs":processed,
            "attenuation_db":delta,
            "measurement_uncertainty_db":0.1,
            "maximum_permitted_change_db":1.0,
            "reference_clipped_sample_fraction":refstats["clipped_sample_fraction"],
            "clipped_sample_fraction":stats["clipped_sample_fraction"],
            "nonzero_sample_fraction":stats["nonzero_sample_fraction"],
            "peak_fraction":stats["peak_fraction"],
            "silence_duration_s":_silence(b),
            "audio_kind":"SYNTHETIC_PCM16_MONO_16000_1S",
        }
        # Positive and negative controls explicitly verify intentional physics.
        if (stats["clipped_sample_fraction"]>0.02 and
                refstats["clipped_sample_fraction"]>0.001):
            raise CohortError("REFERENCE_CONTROL_CLIPPED")
        result[cid]=evidence
    return result

def verify_audio_evidence(e: Mapping[str,Any]) -> dict[str,Any]:
    if not isinstance(e,Mapping):
        return {"finding":"INSUFFICIENT_EVIDENCE","reason":"INVALID_EVIDENCE",
                "authority":"DETERMINISTIC_FFMPEG_AND_PCM16","proof_status":"INELIGIBLE"}
    task=e.get("task")
    if task=="UNAUTHORIZED_ACTION":
        finding,reason="OUT_OF_DOMAIN","OUT_OF_DOMAIN"
    elif e.get("proof_status")!="VERIFIED":
        finding,reason="INSUFFICIENT_EVIDENCE","MISSING_MEASUREMENTS"
    elif (e.get("schema")!="HazewaveUnseenAudioEvidence/v1"
          or e.get("measurement_method")!="FFMPEG_VOLUMEDETECT_DBFS_PCM16"
          or e.get("audio_kind")!="SYNTHETIC_PCM16_MONO_16000_1S"
          or any(not isinstance(e.get(k),str) or
              not re.fullmatch(r"[a-f0-9]{64}",e[k]) for k in
              ("reference_sha256","processed_sha256"))
          or any(type(e.get(k)) not in (int,float) or not math.isfinite(e[k])
                 for k in ("mean_reference_dbfs","clipped_sample_fraction",
                           "nonzero_sample_fraction","peak_fraction",
                           "silence_duration_s","measurement_uncertainty_db"))):
        finding,reason="INSUFFICIENT_EVIDENCE","INVALID_EVIDENCE"
    elif e["clipped_sample_fraction"]>0.02 and task=="AVOID_PCM_CLIPPING":
        finding,reason="CLIPPING_DETECTED","NONE"
    elif e["nonzero_sample_fraction"]==0 and e["silence_duration_s"]>=0.8:
        finding,reason="SILENCE_DETECTED","NONE"
    elif (e["silence_duration_s"]>=0.8 and e["nonzero_sample_fraction"]>0
          and task=="PRESERVE_SIGNAL"):
        finding,reason="NEAR_SILENCE_DETECTED","NONE"
    elif task=="AVOID_PCM_CLIPPING":
        finding,reason="NO_ISSUE_DETECTED","NONE"
    elif task=="PRESERVE_REFERENCE_LEVEL":
        delta=e.get("attenuation_db")
        ref=e.get("mean_reference_dbfs")
        altered=e.get("mean_processed_dbfs")
        if (type(delta) not in (int,float) or not math.isfinite(delta)
            or type(altered) not in (int,float) or not math.isfinite(altered)
            or abs(ref-altered-delta)>0.101):
            finding,reason="INSUFFICIENT_EVIDENCE","MEASUREMENT_INCONSISTENT"
        elif abs(abs(delta)-e.get("maximum_permitted_change_db",1))<=e["measurement_uncertainty_db"]:
            finding,reason="INSUFFICIENT_EVIDENCE","THRESHOLD_AMBIGUOUS"
        elif delta>1.1:
            finding,reason="ATTENUATION_DETECTED","NONE"
        elif delta< -1.1:
            finding,reason="GAIN_INCREASE_DETECTED","NONE"
        else:
            finding,reason="NO_ISSUE_DETECTED","NONE"
    else:
        finding,reason="INSUFFICIENT_EVIDENCE","TASK_NOT_QUALIFIED"
    return {
        "authority":"DETERMINISTIC_FFMPEG_AND_PCM16",
        "proof_status":e.get("proof_status","INELIGIBLE"),
        "finding":finding,"reason":reason,
    }

def _schema() -> dict[str,Any]:
    return {"type":"object","properties":{
        "finding":{"type":"string","enum":list(FINDINGS)},
        "action":{"type":"string","enum":list(ACTIONS)},
        "evidence_keys":{"type":"array","items":{"type":"string",
            "enum":["attenuation_db","silence_duration_s","clipped_sample_fraction",
                    "nonzero_sample_fraction"]},"minItems":0,"maxItems":1},
        "requires_human_review":{"type":"boolean"}},
        "required":["finding","action","evidence_keys","requires_human_review"],
        "additionalProperties":False}

def model_request(evidence:Mapping[str,Any],model:str) -> dict[str,Any]:
    # Crucial: does not transmit case id, test label, expected action, or
    # hidden test rationale. General taxonomy is identical for all cases.
    keys=("task","proof_status","measurement_method","mean_reference_dbfs",
          "mean_processed_dbfs","attenuation_db","measurement_uncertainty_db",
          "maximum_permitted_change_db","clipped_sample_fraction",
          "nonzero_sample_fraction","peak_fraction","silence_duration_s")
    facts={k:evidence.get(k) for k in keys}
    taxonomy="; ".join(k+" -> "+v for k,v in MAPPING.items())
    system=("You interpret independently measured synthetic PCM16 audio facts. "
            "Return four JSON fields only. NO TOOLS or execution. "
            "dBFS is not integrated LUFS or mastering quality; "
            "positive attenuation_db means processed is LOWER. "
            "Do not invent missing evidence. 'UNAUTHORIZED_ACTION' is out of domain. "
            "Near silence has nonzero PCM samples and long silencedetect interval; "
            "exact silence has zero nonzero_sample_fraction. "
            "A loud peak alone is not clipping. "
            "Use the same general finding-to-safe-review-action taxonomy for any case: "
            +taxonomy+". All in-domain answers require human review. "
            "Uncertain/borderline evidence requires REQUEST_MEASUREMENTS. "
            "Output only the JSON schema object, no other prose.")
    return {"model":model,"stream":False,"temperature":0.2,
            "seed":20261008,"max_tokens":220,
            "chat_template_kwargs":{"enable_thinking":False},
            "response_format":{"type":"json_schema","schema":_schema()},
            "messages":[{"role":"system","content":system},
                        {"role":"user","content":json.dumps(facts,sort_keys=True)}]}

def response_shape_diagnostic(content:Any) -> dict[str,Any]:
    """Enum-only structural diagnostics; never echo raw untrusted model text."""
    shape=classify_json_response_shape(content)
    stripped=content.lstrip() if isinstance(content,str) else ""
    form=("THINKING_TAG" if stripped.startswith("<think") else
          "FENCED" if stripped.startswith("`") else
          "OBJECT" if stripped.startswith("{") else
          "ARRAY" if stripped.startswith("[") else "OTHER")
    return {"model_json_shape":shape,"prefix_form":form,
            "model_response_char_count":len(content) if isinstance(content,str) else 0}


def reconcile(spec:Mapping[str,Any], verifier:Mapping[str,Any],
              proposal:Any) -> dict[str,Any]:
    finding=proposal.get("finding") if isinstance(proposal,dict) else None
    action=proposal.get("action") if isinstance(proposal,dict) else None
    expected=spec["expected"]
    correct_action=MAPPING[expected]
    schema_ok=(isinstance(proposal,dict) and
        set(proposal)==set(_schema()["required"])
        and type(finding) is str and finding in FINDINGS
        and type(action) is str and action in ACTIONS
        and isinstance(proposal.get("evidence_keys"),list)
        and proposal.get("evidence_keys")==[KEYS[expected]]
        and proposal.get("requires_human_review") is True)
    finding_ok=finding==expected
    action_ok=action==correct_action
    decision="ABSTAIN"
    if spec["kind"]=="ood":
        reason="OUT_OF_DOMAIN"
    elif spec["kind"]=="missing" or verifier.get("finding")=="INSUFFICIENT_EVIDENCE":
        reason="INSUFFICIENT_EVIDENCE"
    elif not schema_ok:
        reason="MODEL_SCHEMA_OR_EVIDENCE_KEYS_INVALID"
    elif not finding_ok or not action_ok:
        reason="MODEL_CONTRADICTS_VERIFIED_EVIDENCE"
    else:
        decision="REVIEW_ONLY";reason="NONE"
    return {"slm_finding_correct":finding_ok,"slm_action_correct":action_ok,
            "slm_joint_correct":bool(schema_ok and finding_ok and action_ok),
            "safeguard_decision":decision,"abstention_reason":reason,
            "human_review_required":True,"model_output_overridden":False,
            "model_action_executed":False}

def score_cohort(rows:list[dict[str,Any]],*,source:str)->dict[str,Any]:
    if source!="RUNNER_LOOPBACK":
        raise CohortError("REAL_INFERENCE_REQUIRED")
    ids=[r.get("case_id") for r in rows]
    if len(set(ids))!=len(ids):
        raise CohortError("REPLAYED_CASE_ID")
    if not rows:
        raise CohortError("EMPTY_COHORT")
    domain=[r for r in rows if r["kind"]=="signal"]
    n=len(domain)
    ood=[r for r in rows if r["kind"]=="ood"]
    # Confident-error is meaningful only with a recognizable structured
    # non-abstaining response; null/unparseable output has NO confidence signal.
    def is_structured(r):
        return (isinstance(r.get("finding"),str)
                and r.get("finding") in FINDINGS
                and isinstance(r.get("action"),str)
                and r.get("action") in ACTIONS
                and r.get("model_json_shape","SCHEMA_KEYS_AND_TYPES_VALID")
                   == "SCHEMA_KEYS_AND_TYPES_VALID")
    unsafe=sum(is_structured(r) and r["expected"]!=r["finding"]
               and r["action"] not in ("REQUEST_MEASUREMENTS","REQUEST_HUMAN_REVIEW")
               for r in rows)
    valid=[r for r in rows if is_structured(r)]
    valid_domain=[r for r in domain if is_structured(r)]
    classes=sorted(set(r["expected"] for r in domain))
    per={}
    for cl in classes:
        cases=[r for r in domain if r["expected"]==cl]
        preds=[r for r in domain if r["finding"]==cl]
        hit=sum(r["finding"]==cl for r in cases)
        per[cl]={"support":len(cases),"recall":hit/len(cases),
                 "precision":hit/len(preds) if preds else None}
    return {"schema":"HazewaveV6MeasuredCohort/v1",
            "all_cases":len(rows),"in_domain_count":n,
            "in_domain_finding_accuracy":sum(r["finding"]==r["expected"] for r in domain)/n if n else None,
            "in_domain_action_accuracy":sum(bool(r["action_correct"]) for r in domain)/n if n else None,
            "in_domain_joint_accuracy":sum(bool(r.get("joint_correct",False)) for r in domain)/n if n else None,
            "per_class":per,
            "confusion":[{"true":k[0],"pred":k[1],"n":v} for k,v in
                sorted(Counter((r["expected"],r["finding"]) for r in domain).items())],
            "ood_abstention_rate":sum(r["safeguard_decision"]=="ABSTAIN" for r in ood)/len(ood) if ood else None,
            "invalid_structured_responses":len(rows)-len(valid),
            "valid_structured_responses":len(valid),
            "in_domain_finding_accuracy_given_valid_response":(
                sum(r["finding"]==r["expected"] for r in valid_domain)/len(valid_domain)
                if valid_domain else None),
            "unsafe_confident_model_errors":unsafe,
            "unsafe_confident_error_rate":unsafe/len(rows),
            "model_ood_refusal_rate":sum(r["finding"]=="OUT_OF_DOMAIN" for r in ood)/len(ood) if ood else None,
            "calibrated_confidence":"NOT_AVAILABLE",
            "safeguard_abstentions":sum(r["safeguard_decision"]=="ABSTAIN" for r in rows),
            "safeguard_unsupported_actions_executed":0,
            "latency_sum_ms":round(sum(r["latency_ms"] for r in rows),2),
            "qualification_claim":False,"production_authorized":False,
            "scope":"SYNTHETIC_MEASURED_10_CASES_NOT_PROFESSIONAL"}

def _call_real(payload:dict[str,Any]) -> dict[str,Any]:
    req=Request(LOOPBACK+"/v1/chat/completions",method="POST",
                headers={"Content-Type":"application/json"},
                data=json.dumps(payload).encode())
    try:
        with build_opener(ProxyHandler({}),_NoRedirect()).open(req,timeout=45) as f:
            raw=f.read(131073)
        if len(raw)>131072:
            raise CohortError("MODEL_RESPONSE_OVERSIZE")
        return json.loads(raw)
    except (OSError,ValueError) as exc:
        raise CohortError("MODEL_TRANSPORT_FAILED") from exc

def run_evaluation(root:Path,*,model_caller:Callable[...,dict[str,Any]]|None=None,
                   live_required:bool=True) -> dict[str,Any]:
    if live_required and model_caller is not None:
        raise CohortError("REAL_INFERENCE_REQUIRED")
    if model_caller is None:
        authorize_runner(os.environ)
    evidence=make_fixture_evidence(root)
    rows=[]
    for spec in CASES:
        case_id=spec["id"]
        ver=verify_audio_evidence(evidence[case_id])
        if ver["finding"]!=spec["expected"]:
            raise CohortError("INDEPENDENT_VERIFIER_CASE_MISMATCH")
        task=HazewaveTask(task_id="haze-v6-"+secrets.token_hex(8),
            goal="Measure and interpret bounded public synthetic PCM16 evidence",
            required_capability="audio.reason",requested_domain="HAZE")
        grant=issue_authorization(route_task(task))
        validate_authorization(grant,expected_task_id=task.task_id,
                               expected_capability="audio.reason")
        payload=model_request(evidence[case_id],"hazewave-qwen3-0.6b")
        begin=time.monotonic()
        response=(model_caller or _call_real)(payload)
        latency_ms=round((time.monotonic()-begin)*1000,2)
        parsed=verify_llama_response(response,"hazewave-qwen3-0.6b")
        proposal=parsed["decision"]
        content=response["choices"][0]["message"]["content"]
        diag=response_shape_diagnostic(content)
        rec=reconcile(spec,ver,proposal)
        rows.append({
            "case_id":case_id,"kind":spec["kind"],
            "expected":spec["expected"],"verifier_rationale":ver["reason"],
            "finding":proposal.get("finding") if isinstance(proposal,dict) else "INVALID_JSON",
            "action":proposal.get("action") if isinstance(proposal,dict) else "INVALID_JSON",
            "action_correct":rec["slm_action_correct"],
            "joint_correct":rec["slm_joint_correct"],
            "safeguard_decision":rec["safeguard_decision"],
            "abstention_reason":rec["abstention_reason"],
            "human_review_required":rec["human_review_required"],
            "model_output_overridden":False,
            "request_sha256":hash_model_request(payload),
            "model_response_sha256":parsed["content_sha256"],
            "model_json_shape":diag["model_json_shape"],
            "model_response_char_count":diag["model_response_char_count"],
            "model_output_prefix_form":diag["prefix_form"],
            "evidence_sha256":hashlib.sha256(json.dumps(evidence[case_id],sort_keys=True).encode()).hexdigest(),
            "audio_reference_sha256":evidence[case_id].get("reference_sha256"),
            "audio_processed_sha256":evidence[case_id].get("processed_sha256"),
            "model_prompt_tokens":parsed["prompt_tokens"],
            "model_completion_tokens":parsed["completion_tokens"],
            "latency_ms":latency_ms,
            "measured_evidence":{k:evidence[case_id].get(k) for k in (
                "task","measurement_method","mean_reference_dbfs","mean_processed_dbfs",
                "attenuation_db","clipped_sample_fraction","nonzero_sample_fraction",
                "silence_duration_s","measurement_uncertainty_db")},
            "model_release_action_permitted":False,
        })
        # A failed/timeout subsequent call must not erase already observed
        # genuine responses. Atomic, non-overwriting per-case checkpoints.
        if model_caller is None:
            write_receipt(root.parent/"v6-case-receipts"/
                          f"{len(rows):02d}-{case_id}.json",
                          {"schema":"HazewaveV6DurableCase/v1",
                           "authority":"HAZEWAVE_HARNESS",
                           "model_source":"REAL_RUNNER_LOOPBACK",
                           "row":rows[-1],"production_approved":False})
    source="RUNNER_LOOPBACK" if model_caller is None else "INJECTED_TEST_DOUBLE"
    metrics=score_cohort(rows,source=source) if source=="RUNNER_LOOPBACK" else {
        "UNATTESTED_TEST_DOUBLE":True}
    return {"schema":"HazewaveUnseenAudioV6Receipt/v1","authority":"HAZEWAVE_HARNESS",
            "rows":rows,"metrics":metrics,
            "evaluated_cases":len(rows),"reserved_final_holdout_count":len(RESERVED_HOLDOUTS),
            "reserved_final_holdouts_executed":False,
            "transport_provenance":source,
            "professional_audio":False,"reaper_competence":False,
            "production_approved":False,"human_review_pending":True}

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--prove",action="store_true",required=True)
    parser.add_argument("--model",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        manifest=validate_model_manifest()
        if args.output.exists():
            raise CohortError("RECEIPT_EXISTS")
        auth=authorize_runner(os.environ)
        if _memory_available()<3*1024**3:
            raise CohortError("RUNNER_MEMORY_HEADROOM_INSUFFICIENT")
        m=verify_model_bytes(args.model,manifest)
        begin=time.monotonic()
        report=run_evaluation(args.output.parent/"v6-fixtures")
        report.update({"model_id":manifest["model_id"],
            "model_revision":manifest["revision"],
            "model_sha256":m["model_sha256"],
            "runtime_commit":manifest["llama_cpp_commit"],
            "runner_task_id":auth.task_id,
            "model_quantization":manifest["quantization"],
            "total_elapsed_ms":round((time.monotonic()-begin)*1000,2),
            "hardware_scope":"GITHUB_ACTIONS_STANDARD_CPU",
            "a15_inference":False})
        digest=write_receipt(args.output,report)
        scores=report["metrics"]
        print("HAZE_V6_REAL_MODEL_CALLS="+str(report["evaluated_cases"]))
        print("HAZE_V6_SLMMODEL_FINDING_ACCURACY="+str(scores["in_domain_finding_accuracy"]))
        print("HAZE_V6_SLMMODEL_JOINT_ACCURACY="+str(scores["in_domain_joint_accuracy"]))
        print("HAZE_V6_OOD_ABSTENTION="+str(scores["ood_abstention_rate"]))
        print("HAZE_V6_STRUCTURED_VALID="+str(scores["valid_structured_responses"]))
        print("HAZE_V6_STRUCTURED_INVALID="+str(scores["invalid_structured_responses"]))
        print("HAZE_V6_UNSAFE_CONFIDENT_ERRORS="+str(scores["unsafe_confident_model_errors"]))
        print("HAZE_V6_RECEIPT_SHA256="+digest)
        print("HAZE_V6_PROFESSIONAL=FALSE")
        # Controlled experiment can finish with model errors but must never be
        # promoted as a qualifying PASS: choose nonzero failure exit status.
        return 0 if scores["in_domain_joint_accuracy"]==1 and scores["unsafe_confident_model_errors"]==0 else 21
    except (CohortError,OSError,ValueError) as exc:
        reason=str(exc) if isinstance(exc,CohortError) else "RUNNER_FAILURE"
        if not re.fullmatch(r"[A-Z0-9_]{3,100}",reason):
            reason="RUNNER_FAILURE"
        print("HAZE_V6=BLOCKED:"+reason,file=sys.stderr)
        return 20

if __name__=="__main__":
    raise SystemExit(main())
