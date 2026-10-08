"""Evidence-bound HAZE SLM, with real router authorization and falsifiable grading."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from types import SimpleNamespace

import pytest

from hazewave.slm_audio_specialist import (
    SLMAudioSpecialistError, build_audio_prompt, execute_audio_specialist,
    evaluate_audio_decision,
)
from tests.test_host_av_evidence import proof, SHA

MODEL = "oc/mimo-v2.6-flash-free"
GOOD = {
    "finding": "ATTENUATION_DETECTED",
    "action": "REVIEW_GAIN_STAGE",
    "evidence_keys": ["audio_attenuation_db"],
    "requires_human_review": True,
}


def _args(tmp_path: Path, executor):
    log, receipt = proof(tmp_path)
    import hashlib
    return dict(
        log_path=log, receipt_path=receipt, reviewed_sha=SHA,
        log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
        receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(),
        model_id=MODEL, executor=executor
    )


def _response(auth, content):
    return SimpleNamespace(
        status="PASS", model_id=MODEL, zero_cost_verified=True,
        authorization_id=auth.authorization_id, task_id=auth.task_id,
        gateway="9router", provider="opencode", content=json.dumps(content),
        total_tokens=26, prompt_tokens=18, completion_tokens=8,
        fallback_count=0
    )


def test_specialist_calls_existing_governed_9router_and_scores_real_evidence(tmp_path: Path):
    calls = []
    def executor(**kw):
        calls.append(kw)
        return _response(kw["authorization"], GOOD)
    report = execute_audio_specialist(**_args(tmp_path, executor))
    assert report["schema"] == "HazewaveSLMAudioSpecialistBenchmark/v1"
    assert report["harness_authority"] == "HAZEWAVE_HARNESS"
    assert report["reviewed_source_sha"] == SHA
    assert report["specialist"]["grade"] == "PASS"
    assert report["specialist"]["decision"]["action"] == "REVIEW_GAIN_STAGE"
    assert report["specialist"]["model_id"] == MODEL
    assert report["specialist"]["total_tokens"] == 26
    assert report["baseline"] is None
    assert report["model_improvement_proven"] is False
    assert report["agent_tool_execution_proven"] is False
    assert report["production_approved"] is False
    assert calls[0]["authorization"].domain == "HAZE"
    assert calls[0]["authorization"].capability_id == "reason.general"
    assert calls[0]["data_classification"] == "PUBLIC"
    assert calls[0]["max_fallbacks"] == 1
    assert calls[0]["model_id"] == MODEL
    assert not any(x in calls[0]["prompt"] for x in ("/etc/shadow", "private_root", "receipt_path"))


def test_compare_mode_runs_same_model_both_conditions_without_false_improvement(tmp_path: Path):
    calls = []
    def executor(**kw):
        calls.append(kw)
        return _response(kw["authorization"], GOOD)
    report = execute_audio_specialist(**_args(tmp_path, executor), compare_baseline=True)
    assert len(calls) == 2
    assert [x["model_id"] for x in calls] == [MODEL, MODEL]
    assert report["baseline"]["grade"] == "PASS"
    assert report["specialist"]["grade"] == "PASS"
    assert report["model_improvement_proven"] is False
    assert report["benchmark_execution"] == "SIMILAR_TWO_MODEL_CALLS_NO_OUTCOME_ADVANTAGE"
    assert report["total_tokens"] == 52


def test_bad_model_output_fails_closed_without_professional_readiness(tmp_path: Path):
    def bad(**kw):
        return _response(kw["authorization"], {
            **GOOD, "action": "PUBLISH_AUTOMATICALLY"
        })
    report = execute_audio_specialist(**_args(tmp_path, bad))
    assert report["specialist"]["grade"] == "FAIL"
    assert report["specialist"]["error"] == "OUTPUT_SCHEMA_OR_SEMANTICS_INVALID"
    assert report["production_approved"] is False


def test_model_output_cannot_promote_authority_or_bypass_qa(tmp_path: Path):
    def fake(**kw):
        return _response(kw["authorization"], {
            **GOOD, "production_approved": True, "agent_authority": "OWNER"
        })
    report = execute_audio_specialist(**_args(tmp_path, fake))
    assert report["specialist"]["grade"] == "FAIL"


def test_route_rejects_arbitrary_model_and_unverified_source_before_any_model_call(tmp_path: Path):
    count = []
    def executor(**kw):
        count.append(kw)
        return _response(kw["authorization"], GOOD)
    inp = _args(tmp_path, executor)
    with pytest.raises(SLMAudioSpecialistError, match="MODEL_ID_NOT_EXACT_FREE_ROUTE"):
        execute_audio_specialist(**{**inp, "model_id": "auto"})
    with pytest.raises(SLMAudioSpecialistError, match="MODEL_ID_NOT_EXACT_FREE_ROUTE"):
        execute_audio_specialist(**{**inp, "model_id": "oc/paid-premium"})
    with pytest.raises(Exception):
        execute_audio_specialist(**{**inp, "log_sha256": "0"*64})
    assert not count


def test_prompt_keeps_metadata_as_data_not_as_tool_instructions():
    prompt = build_audio_prompt(12.0, knowledge=("volumedetect", "Do not change system policies."))
    assert "NO TOOL CALLS" in prompt
    assert "UNTRUSTED_REFERENCE_DATA" in prompt
    assert "12.0" in prompt


def test_independent_grade_rejects_unfounded_or_missing_evidence():
    assert evaluate_audio_decision(GOOD, attenuation=12.0)["grade"] == "PASS"
    assert evaluate_audio_decision({**GOOD, "evidence_keys": []}, attenuation=12.0)["grade"] == "FAIL"
    assert evaluate_audio_decision({**GOOD, "finding": "NO_ISSUE_DETECTED"}, attenuation=12.0)["grade"] == "FAIL"


def test_cli_preserves_safe_router_failure_code_not_raw_secret(capsys, monkeypatch):
    from hazewave import slm_audio_specialist as module
    from hazewave.ninerouter import NineRouterExecutionError
    def blocked(**kw):
        raise NineRouterExecutionError("NINEROUTER_ADMISSION_RECEIPT_EXPIRED")
    monkeypatch.setattr(module, "execute_audio_specialist", blocked)
    rc = module.main([
        "--log", "/missing", "--receipt", "/missing",
        "--reviewed-sha", SHA, "--log-sha256", "a"*64,
        "--receipt-sha256", "b"*64, "--model", MODEL
    ])
    assert rc == 20
    assert "NINEROUTER_ADMISSION_RECEIPT_EXPIRED" in capsys.readouterr().err
    def secret(**kw):
        raise NineRouterExecutionError("password=confidential")
    monkeypatch.setattr(module, "execute_audio_specialist", secret)
    assert module.main([
        "--log", "/missing", "--receipt", "/missing",
        "--reviewed-sha", SHA, "--log-sha256", "a"*64,
        "--receipt-sha256", "b"*64, "--model", MODEL
    ]) == 20
    error = capsys.readouterr().err
    assert "confidential" not in error
    assert "GOVERNED_EXECUTION_FAILED" in error


def test_model_attempt_to_invoke_external_tool_is_rejected(tmp_path: Path):
    def executor(**kw):
        res = _response(kw["authorization"], GOOD)
        res.tool_calls = [{"function": {"name": "delete_files"}}]
        return res
    with pytest.raises(SLMAudioSpecialistError, match="GOVERNED_MODEL_RESPONSE_INVALID"):
        execute_audio_specialist(**_args(tmp_path, executor))


def test_different_trial_ids_bind_distinct_real_harness_task_grants(tmp_path: Path):
    task_ids = []
    def executor(**kw):
        task_ids.append(kw["authorization"].task_id)
        return _response(kw["authorization"], GOOD)
    args = _args(tmp_path, executor)
    first = execute_audio_specialist(**args, trial_id="trial0001", compare_baseline=True)
    second = execute_audio_specialist(**args, trial_id="trial0002", compare_baseline=True)
    assert first["trial_id"] == "trial0001"
    assert second["trial_id"] == "trial0002"
    assert len(set(task_ids)) == 4
    assert "trial0001" in task_ids[0] and "trial0002" in task_ids[2]
    assert first["baseline"]["task_id"] != first["specialist"]["task_id"]


def test_invalid_trial_id_fails_before_model_invocation(tmp_path: Path):
    called = []
    def executor(**kw):
        called.append(kw)
        return _response(kw["authorization"], GOOD)
    args = _args(tmp_path, executor)
    for trial_id in ("", "bad id", "trial/../secret", "x" * 100, 25):
        with pytest.raises(SLMAudioSpecialistError, match="TRIAL_ID_INVALID"):
            execute_audio_specialist(**args, trial_id=trial_id)
    assert not called


def test_reference_model_result_does_not_claim_slm_or_certify_size(tmp_path: Path):
    def executor(**kw):
        return _response(kw["authorization"], GOOD)
    report = execute_audio_specialist(**_args(tmp_path, executor))
    assert report["model_size_verified"] is False
    assert report["model_is_slm_proven"] is False
    assert report["model_reference_only"] is True
    assert report["model_improvement_proven"] is False
