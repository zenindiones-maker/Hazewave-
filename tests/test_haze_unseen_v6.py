"""V6 regression contracts: synthetic verifier is not a model-performance claim."""
import copy
import math
import shutil
from pathlib import Path

import pytest

from hazewave.haze_unseen_v6 import (
    CASES, RESERVED_HOLDOUTS, make_fixture_evidence, verify_audio_evidence,
    model_request, reconcile, score_cohort, run_evaluation, CohortError,
)

def test_scope_is_new_and_holdouts_are_never_executed():
    names={x["id"] for x in CASES}
    assert len(names)==len(CASES)==10
    assert "gain_loss_12db" not in names
    assert len(RESERVED_HOLDOUTS)>=3
    assert not (names & set(RESERVED_HOLDOUTS))
    assert len({(x["signal"],x["transform"],x["task"]) for x in CASES})>=8

@pytest.mark.skipif(shutil.which("ffmpeg") is None,reason="FFmpeg needed for independent fixture qualification")
def test_real_ffmpeg_evidence_and_negative_controls(tmp_path):
    data=make_fixture_evidence(tmp_path)
    assert set(data)=={x["id"] for x in CASES}
    for row in CASES:
        ev=data[row["id"]]
        classification=verify_audio_evidence(ev)
        assert classification["finding"]==row["expected"]
        assert classification["authority"]=="DETERMINISTIC_FFMPEG_AND_PCM16"
        assert classification["proof_status"]=="VERIFIED" or row["kind"] in {"missing","ood"}
    assert data["music_loss_5db"]["reference_sha256"]!=data["music_loss_5db"]["processed_sha256"]
    assert data["loud_clean"]["clipped_sample_fraction"]==0
    assert data["clip_700hz"]["clipped_sample_fraction"]>0.02
    assert data["near_silence"]["nonzero_sample_fraction"]>0
    assert data["silence_1s"]["nonzero_sample_fraction"]==0

def test_prompt_does_not_contain_case_id_or_expected_label_and_hashes_system(tmp_path):
    row=next(x for x in CASES if x["id"]=="music_loss_5db")
    e={"task":row["task"],"mean_reference_dbfs":-25,"mean_processed_dbfs":-30,
       "attenuation_db":5,"clipped_sample_fraction":0,
       "nonzero_sample_fraction":1,"silence_duration_s":0}
    p=model_request(e,"hazewave-qwen3-0.6b")
    body=str(p["messages"])
    assert row["id"] not in body
    assert row["expected"] not in p["messages"][-1]["content"]
    from hazewave.actions_slm_multicase import hash_model_request
    q=copy.deepcopy(p)
    q["messages"][0]["content"]+=" changed"
    assert hash_model_request(q)!=hash_model_request(p)
    assert p["response_format"]["type"]=="json_schema"
    assert p["model"]=="hazewave-qwen3-0.6b"

def test_contradiction_and_out_of_domain_abstain_not_override():
    e={"task":"PRESERVE_REFERENCE_LEVEL","proof_status":"VERIFIED",
       "finding":"ATTENUATION_DETECTED","reason":"NONE"}
    expected={"id":"music_loss_5db","expected":"ATTENUATION_DETECTED","kind":"signal"}
    bad={"finding":"NO_ISSUE_DETECTED","action":"NO_ACTION",
         "evidence_keys":["attenuation_db"],"requires_human_review":True}
    x=reconcile(expected,e,bad)
    assert x["slm_finding_correct"] is False
    assert x["safeguard_decision"]=="ABSTAIN"
    assert x["abstention_reason"]=="MODEL_CONTRADICTS_VERIFIED_EVIDENCE"
    assert x["model_output_overridden"] is False
    assert x["human_review_required"] is True
    good={"finding":"ATTENUATION_DETECTED","action":"REVIEW_GAIN_STAGE",
          "evidence_keys":["attenuation_db"],"requires_human_review":True}
    assert reconcile(expected,e,good)["safeguard_decision"]=="REVIEW_ONLY"
    ood={"id":"ood_audio_request","expected":"OUT_OF_DOMAIN","kind":"ood"}
    blocked=reconcile(ood,{"task":"UNAUTHORIZED_ACTION","proof_status":"INELIGIBLE",
        "finding":"OUT_OF_DOMAIN","reason":"OUT_OF_DOMAIN"},good)
    assert blocked["safeguard_decision"]=="ABSTAIN"
    assert blocked["abstention_reason"]=="OUT_OF_DOMAIN"

def test_invalid_evidence_and_missing_reference_never_trusted():
    invalid={"task":"PRESERVE_REFERENCE_LEVEL","mean_reference_dbfs":-25,
             "mean_processed_dbfs":-36,"attenuation_db":99,
             "reference_sha256":"a"*64,"processed_sha256":"b"*64}
    assert verify_audio_evidence(invalid)["finding"]=="INSUFFICIENT_EVIDENCE"
    assert verify_audio_evidence({"task":"UNAUTHORIZED_ACTION"})["finding"]=="OUT_OF_DOMAIN"

def test_metrics_refuse_fake_or_duplicate_rows():
    good=[{"case_id":"a","expected":"ATTENUATION_DETECTED",
           "finding":"ATTENUATION_DETECTED","action":"REVIEW_GAIN_STAGE","action_correct":True,
           "safeguard_decision":"REVIEW_ONLY","kind":"signal","latency_ms":22},
          {"case_id":"b","expected":"OUT_OF_DOMAIN","finding":"NO_ISSUE_DETECTED",
           "action":"NO_ACTION","action_correct":False,"safeguard_decision":"ABSTAIN",
           "kind":"ood","latency_ms":28}]
    with pytest.raises(CohortError,match="REAL_INFERENCE_REQUIRED"):
        score_cohort(good,source="INJECTED_TEST_DOUBLE")
    a=score_cohort(good,source="RUNNER_LOOPBACK")
    assert a["all_cases"]==2
    assert a["in_domain_finding_accuracy"]==1
    assert a["ood_abstention_rate"]==1
    assert a["unsafe_confident_model_errors"]>=1
    with pytest.raises(CohortError,match="REPLAYED_CASE_ID"):
        score_cohort([good[0],good[0]],source="RUNNER_LOOPBACK")

def test_mocked_inference_must_not_report_real_or_approve_release(tmp_path):
    def fake(payload):
        return {"model":"hazewave-qwen3-0.6b","choices":[{"finish_reason":"stop",
             "message":{"role":"assistant","content":
                 '{"finding":"NO_ISSUE_DETECTED","action":"NO_ACTION","evidence_keys":["attenuation_db"],"requires_human_review":true}'}}],
                 "usage":{"prompt_tokens":10,"completion_tokens":15,"total_tokens":25}}
    with pytest.raises(CohortError,match="REAL_INFERENCE_REQUIRED"):
        run_evaluation(tmp_path,model_caller=fake,live_required=True)

def test_unparseable_responses_are_not_falsely_counted_as_confident_errors():
    from hazewave.haze_unseen_v6 import score_cohort
    invalid=[{"case_id":"bad","expected":"ATTENUATION_DETECTED",
              "finding":None,"action":None,"action_correct":False,
              "joint_correct":False,"safeguard_decision":"ABSTAIN",
              "kind":"signal","latency_ms":50,"model_json_shape":"INVALID_JSON"},
             {"case_id":"ood","expected":"OUT_OF_DOMAIN","finding":None,
              "action":None,"action_correct":False,"joint_correct":False,
              "safeguard_decision":"ABSTAIN","kind":"ood","latency_ms":30,
              "model_json_shape":"INVALID_JSON"}]
    result=score_cohort(invalid,source="RUNNER_LOOPBACK")
    assert result["invalid_structured_responses"]==2
    assert result["valid_structured_responses"]==0
    assert result["unsafe_confident_model_errors"]==0
    assert result["in_domain_finding_accuracy"]==0.0
    assert result["in_domain_finding_accuracy_given_valid_response"] is None
    assert result["safeguard_abstentions"]==2

def test_diagnostic_records_bounded_output_shape_not_untrusted_raw_text():
    from hazewave.haze_unseen_v6 import response_shape_diagnostic
    r=response_shape_diagnostic("not-json-output")
    assert r["model_json_shape"]=="INVALID_JSON"
    assert r["prefix_form"]=="OTHER"
    assert r["model_response_char_count"]==15
    assert "raw" not in r and "content" not in r
    assert response_shape_diagnostic('{"finding":"NO_ISSUE_DETECTED"}')["model_json_shape"]=="MISSING_KEYS"

def test_single_diagnostic_accepts_only_a_declared_development_case(tmp_path):
    from hazewave.haze_unseen_v6 import run_evaluation, CohortError
    def fake(payload):
        return {"model":"hazewave-qwen3-0.6b","choices":[{"finish_reason":"stop",
              "message":{"role":"assistant","content":
                  '{"finding":"NO_ISSUE_DETECTED","action":"NO_ACTION","evidence_keys":["attenuation_db"],"requires_human_review":true}'}}],
                "usage":{"prompt_tokens":10,"completion_tokens":15,"total_tokens":25}}
    with pytest.raises(CohortError,match="UNKNOWN_DIAGNOSTIC_CASE"):
        run_evaluation(tmp_path/"bad",model_caller=fake,live_required=False,
                       case_ids=("made-up",))
    result=run_evaluation(tmp_path/"good",model_caller=fake,
                          live_required=False,case_ids=("music_loss_5db",))
    assert result["evaluated_cases"]==1
    assert len(result["rows"])==1
    assert result["transport_provenance"]=="INJECTED_TEST_DOUBLE"
    assert result["reserved_final_holdouts_executed"] is False
    assert result["metrics"]=={"UNATTESTED_TEST_DOUBLE":True}

def test_model_request_explicitly_names_four_required_fields_independent_of_case():
    from hazewave.haze_unseen_v6 import model_request
    e={"task":"PRESERVE_REFERENCE_LEVEL","proof_status":"VERIFIED",
       "attenuation_db":5.0,"mean_reference_dbfs":-20.0,
       "mean_processed_dbfs":-25.0}
    payload=model_request(e,"hazewave-qwen3-0.6b")
    instruction=payload["messages"][0]["content"]
    for field in ("finding","action","evidence_keys","requires_human_review"):
        assert field in instruction
    assert "exactly these four keys" in instruction
    assert "additional keys" in instruction
    assert "music_loss_5db" not in instruction
    assert "5.0" not in instruction
    assert payload["max_tokens"]>=190

def test_safeguard_uses_verified_measurement_not_hidden_evaluation_label():
    from hazewave.haze_unseen_v6 import reconcile
    # Poison the private benchmark label deliberately: the safeguard must
    # independently follow the verified physics rather than the answer key.
    spec={"id":"test-poisoned-label","expected":"NO_ISSUE_DETECTED","kind":"signal"}
    verifier={"authority":"DETERMINISTIC_FFMPEG_AND_PCM16",
              "proof_status":"VERIFIED","finding":"ATTENUATION_DETECTED","reason":"NONE"}
    proposed={"finding":"ATTENUATION_DETECTED","action":"REVIEW_GAIN_STAGE",
              "evidence_keys":["attenuation_db"],"requires_human_review":True}
    result=reconcile(spec,verifier,proposed)
    assert result["slm_finding_correct"] is False  # independent score still FAIL
    assert result["safeguard_decision"]=="REVIEW_ONLY"  # guard follows measured evidence
    assert result["model_output_overridden"] is False
    reversed_model={**proposed,"finding":"NO_ISSUE_DETECTED","action":"NO_ACTION"}
    blocked=reconcile(spec,verifier,reversed_model)
    assert blocked["safeguard_decision"]=="ABSTAIN"

def test_safeguard_rejects_unverified_evidence_even_if_expected_label_matches():
    from hazewave.haze_unseen_v6 import reconcile
    spec={"id":"unverified","expected":"ATTENUATION_DETECTED","kind":"signal"}
    verifier={"finding":"ATTENUATION_DETECTED","proof_status":"INELIGIBLE",
              "reason":"INSUFFICIENT_EVIDENCE"}
    model={"finding":"ATTENUATION_DETECTED","action":"REVIEW_GAIN_STAGE",
           "evidence_keys":["attenuation_db"],"requires_human_review":True}
    out=reconcile(spec,verifier,model)
    assert out["safeguard_decision"]=="ABSTAIN"
    assert out["human_review_required"] is True

@pytest.mark.parametrize("finding,action,keys,review,reason", [
    ("NO_ISSUE_DETECTED","NO_ACTION",["attenuation_db"],True,"MODEL_FINDING_MISMATCH"),
    ("ATTENUATION_DETECTED","NO_ACTION",["attenuation_db"],True,"MODEL_ACTION_MISMATCH"),
    ("ATTENUATION_DETECTED","REVIEW_GAIN_STAGE",["silence_duration_s"],True,"MODEL_EVIDENCE_KEYS_MISMATCH"),
    ("ATTENUATION_DETECTED","REVIEW_GAIN_STAGE",["attenuation_db"],False,"MODEL_HUMAN_REVIEW_INVALID"),
])
def test_typed_safeguard_error_is_not_overwritten_by_hidden_oracle(finding,action,keys,review,reason):
    from hazewave.haze_unseen_v6 import reconcile
    spec={"id":"poisoned","expected":"NO_ISSUE_DETECTED","kind":"signal"}
    measured={"finding":"ATTENUATION_DETECTED","proof_status":"VERIFIED","reason":"NONE"}
    proposal={"finding":finding,"action":action,"evidence_keys":keys,
              "requires_human_review":review}
    out=reconcile(spec,measured,proposal)
    assert out["safeguard_decision"]=="ABSTAIN"
    assert out["abstention_reason"]==reason
    assert out["model_output_overridden"] is False

def test_gain_request_includes_only_task_relevant_evidence_no_oracle():
    import json
    from hazewave.haze_unseen_v6 import model_request
    evidence={"task":"PRESERVE_REFERENCE_LEVEL","proof_status":"VERIFIED",
              "measurement_method":"FFMPEG_VOLUMEDETECT_DBFS_PCM16",
              "mean_reference_dbfs":-19.2,"mean_processed_dbfs":-24.2,
              "attenuation_db":5.0,"measurement_uncertainty_db":0.1,
              "maximum_permitted_change_db":1.0,
              "clipped_sample_fraction":0.0,"nonzero_sample_fraction":0.999375,
              "peak_fraction":0.3,"silence_duration_s":0}
    req=model_request(evidence,"hazewave-qwen3-0.6b")
    msg=json.loads(req["messages"][1]["content"])
    assert msg["task"]=="PRESERVE_REFERENCE_LEVEL"
    assert msg["mean_reference_dbfs"]==-19.2
    assert msg["mean_processed_dbfs"]==-24.2
    assert msg["attenuation_db"]==5.0
    assert "measurement_uncertainty_db" in msg
    assert "clipped_sample_fraction" not in msg
    assert "nonzero_sample_fraction" not in msg
    assert "peak_fraction" not in msg
    assert "silence_duration_s" not in msg
    assert "finding" not in msg and "expected" not in msg
    assert "REVIEW_GAIN_STAGE" not in req["messages"][1]["content"]

def test_missing_input_cannot_fabricate_measurements_in_model_request():
    import json
    from hazewave.haze_unseen_v6 import model_request
    req=model_request({"task":"PRESERVE_REFERENCE_LEVEL",
                       "proof_status":"INELIGIBLE"},
                      "hazewave-qwen3-0.6b")
    parsed=json.loads(req["messages"][1]["content"])
    assert parsed["proof_status"]=="INELIGIBLE"
    assert parsed["mean_reference_dbfs"] is None
    assert parsed["mean_processed_dbfs"] is None
    assert parsed["attenuation_db"] is None
