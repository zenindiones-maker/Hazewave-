"""The A15 must remain control-only; prove a compact HAZE model on a public Actions runner."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from hazewave.actions_slm_runner import (
    RunnerProofError, authorize_runner, validate_model_manifest,
    verify_llama_response, evaluate_audio_metric, write_receipt
)
from hazewave.slm_audio_specialist import evaluate_audio_decision

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "slm-actions-runner-model-v1.json"
WORKFLOW = ROOT / ".github/workflows/hazewave-slm-actions-inference-v1.yml"


def test_manifest_pins_official_compact_weights_and_oss_runtime():
    m = validate_model_manifest(MANIFEST)
    assert m["model_id"] == "Qwen/Qwen3-0.6B-GGUF"
    assert m["model_file"] == "Qwen3-0.6B-Q4_K_M.gguf"
    assert m["revision"] == "1208e45d782fe18602c5eaf10e5758d5b0f24c03"
    assert m["sha256"] == "b0638f08417a2d3c8652760462eb5407c6e30173cf9608ad0820757a281eea0e"
    assert m["license"] == "apache-2.0"
    assert m["total_parameters_estimated"] <= 1_000_000_000
    assert m["llama_cpp_commit"] == "d81235049384534c167caea52b85a694f6103d14"
    assert m["production_approved"] is False


def test_runner_authorization_refuses_termux_codespace_and_private_repo():
    good = dict(GITHUB_ACTIONS="true", GITHUB_REPOSITORY="zenindiones-maker/Hazewave-",
                RUNNER_OS="Linux", HAZEWAVE_REPOSITORY_PUBLIC="true")
    assert authorize_runner(good).domain == "HAZE"
    for bad in (
        {**good, "GITHUB_ACTIONS": "false"},
        {**good, "CODESPACES": "true"},
        {**good, "TERMUX_VERSION": "0.119"},
        {**good, "HAZEWAVE_REPOSITORY_PUBLIC": "false"},
        {**good, "RUNNER_OS": "Windows"},
        {**good, "GITHUB_REPOSITORY": "attacker/sandbox"},
    ):
        with pytest.raises(RunnerProofError):
            authorize_runner(bad)


def test_llama_response_must_be_completed_and_never_invoke_tools():
    good = {
        "model": "hazewave-qwen3-0.6b",
        "choices": [{
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps({
                "finding": "ATTENUATION_DETECTED",
                "action": "REVIEW_GAIN_STAGE",
                "evidence_keys": ["audio_attenuation_db"],
                "requires_human_review": True
            })}
        }],
        "usage": {"prompt_tokens": 74, "completion_tokens": 32, "total_tokens": 106}
    }
    obj = verify_llama_response(good, "hazewave-qwen3-0.6b")
    assert evaluate_audio_decision(obj["decision"], attenuation=12.0)["grade"] == "PASS"
    assert obj["tokens"] == 106
    for change in (
        {"choices": [{"finish_reason": "length", "message": good["choices"][0]["message"]}]},
        {"choices": [{"finish_reason": "stop", "message": {
            **good["choices"][0]["message"], "tool_calls":[{"function": {"name":"publish"}}]}}]},
        {"model": "different-checkpoint"},
        {"usage": {"total_tokens": -1, "prompt_tokens": 74, "completion_tokens": 32}},
    ):
        with pytest.raises(RunnerProofError):
            verify_llama_response({**good, **change}, "hazewave-qwen3-0.6b")


def test_audio_metric_has_real_reference_and_negative_control():
    proof = evaluate_audio_metric(-21.1, -33.14, reference_sha="a"*64, modified_sha="b"*64)
    assert proof["attenuation_db"] == pytest.approx(12.04, abs=0.01)
    assert proof["metric_negative_control"] == "PASS"
    with pytest.raises(RunnerProofError):
        evaluate_audio_metric(-21.1, -21.1, reference_sha="a"*64, modified_sha="b"*64)
    with pytest.raises(RunnerProofError):
        evaluate_audio_metric(-21.1, -33.1, reference_sha="a"*64, modified_sha="a"*64)


def test_receipt_is_owner_private_atomic_and_not_overwritten(tmp_path: Path):
    path=tmp_path/"proof.json"
    data={"schema":"HazewaveActionsSLMExecution/v1","production_approved":False}
    digest=write_receipt(path,data)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    assert path.stat().st_mode & 0o077 == 0
    with pytest.raises(RunnerProofError,match="RECEIPT_EXISTS"):
        write_receipt(path,data)


def test_actions_runner_job_public_only_and_a15_never_installs():
    w=WORKFLOW.read_text()
    assert "work/slm-actions-runner-real-inference-v1" in w
    assert "github.event.repository.private == false" in w
    assert "runs-on: ubuntu-latest" in w
    assert "timeout-minutes: 15" in w
    assert "--inventory" in w
    assert w.index("--inventory") < w.index("Qwen3-0.6B-Q4_K_M.gguf")
    assert "b0638f08417a2d3c8652760462eb5407c6e30173cf9608ad0820757a281eea0e" in w
    assert "d81235049384534c167caea52b85a694f6103d14" in w
    assert "sudo apt-get install -y --no-install-recommends ffmpeg" in w
    assert "httpx==0.28.1" in w
    assert w.index("httpx==0.28.1") < w.index("-m hazewave.actions_slm_runner --inventory")
    assert "127.0.0.1" in w
    assert "python -m hazewave.actions_slm_runner --prove" in w
    for forbidden in ("ollama pull", "gh codespace create", "gh codespace start",
                      "TERMUX_VERSION=", "git push --force"):
        assert forbidden not in w
    assert "A15_INFERENCE=FORBIDDEN" in w


def test_public_evidence_does_not_disclose_live_harness_authorization_identifier():
    code=(ROOT/"src"/"hazewave"/"actions_slm_runner.py").read_text()
    assert '"authorization_id": grant.authorization_id' not in code
    assert '"authorization_id_sha256"' in code
