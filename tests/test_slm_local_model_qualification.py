"""Real local-model discovery + controlled HAZE live-response qualification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hazewave.slm_local_model_qualification import (
    ModelQualificationError, inventory_local_ollama, probe_verified_audio_case,
    write_private_result
)
from tests.test_host_av_evidence import SHA, proof


def fixed_transport(*, size="4.0B", digest="a"*64, license_text="Apache License Version 2.0",
                    show_count=4_000_000_000, reply=None):
    calls = []
    def request(method, path, payload=None):
        calls.append((method, path, payload))
        if path == "/api/tags":
            return {"models": [
                {"name": "qwen3:4b", "digest": digest, "size": 2600000000,
                 "details": {"family": "qwen3", "parameter_size": size,
                             "quantization_level": "Q4_K_M", "format": "gguf"}}
            ]}
        if path == "/api/show":
            return {"license": license_text,
                    "details": {"family": "qwen3", "parameter_size": size,
                                "quantization_level": "Q4_K_M"},
                    "model_info": {"general.parameter_count": show_count,
                                   "general.architecture": "qwen3"}}
        if path == "/api/chat":
            content = reply if reply is not None else json.dumps({
                "finding": "ATTENUATION_DETECTED",
                "action": "REVIEW_GAIN_STAGE",
                "evidence_keys": ["audio_attenuation_db"],
                "requires_human_review": True
            })
            return {"model": "qwen3:4b", "done": True,
                    "message": {"role": "assistant", "content": content},
                    "eval_count": 31, "prompt_eval_count": 102,
                    "total_duration": 2200000000, "done_reason": "stop"}
        raise AssertionError(path)
    return request, calls


def audited_case(tmp_path):
    log, receipt = proof(tmp_path)
    return dict(
        log_path=log, receipt_path=receipt, reviewed_sha=SHA,
        log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
        receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest()
    )


def test_local_inventory_reads_real_model_digest_and_license_without_any_inference():
    req, calls = fixed_transport()
    info = inventory_local_ollama(transport=req)
    assert info["schema"] == "HazewaveLocalModelInventory/v3"
    assert info["runtime_available"] is True
    assert info["total_models_installed"] == 1
    model = info["models"][0]
    assert model["name"] == "qwen3:4b"
    assert model["local_identity_digest_sha256"] == "a"*64
    assert model["local_identity_verified"] is True
    assert model["size_verified"] is True
    assert model["license_metadata_verified"] is True
    assert model["total_parameters"] == 4_000_000_000
    assert model["quantization"] == "Q4_K_M"
    assert model["model_is_slm_proven"] is False
    assert model["inference_tested"] is False
    assert model["upstream_weights_provenance_verified"] is False
    assert model["production_approved"] is False
    assert all(p != "/api/chat" for _,p,_ in calls)


def test_inventory_abstains_on_alias_ambiguity_or_missing_license():
    for kw in (
        {"digest": "unknown"}, {"size": "unknown"}, {"license_text": ""},
        {"show_count": 27_000_000_000}, {"size": "30B"}
    ):
        req, _ = fixed_transport(**kw)
        info = inventory_local_ollama(transport=req)
        assert info["models"][0]["candidate_admitted_for_smoke"] is False
        assert info["models"][0]["model_is_slm_proven"] is False


def test_no_local_ollama_is_blocker_not_fictitious_inventory():
    def unavailable(method,path,payload=None):
        raise ModelQualificationError("OLLAMA_LOCAL_UNAVAILABLE")
    with pytest.raises(ModelQualificationError, match="OLLAMA_LOCAL_UNAVAILABLE"):
        inventory_local_ollama(transport=unavailable)


def test_model_request_requires_digest_bound_synthetic_evidence_and_real_chat(tmp_path: Path):
    req, calls = fixed_transport()
    result = probe_verified_audio_case(
        **audited_case(tmp_path),
        transport=req, model_name="qwen3:4b", expected_digest="a"*64,
        trial_id="live-trial-000001"
    )
    assert result["schema"] == "HazewaveLocalAudioInferenceProof/v3"
    # A mocked transport never proves that a model actually ran.
    assert result["real_model_request_observed"] is False
    assert result["real_model_response_observed"] is False
    assert result["model_response_observed"] is True
    assert result["transport_provenance"] == "INJECTED_TEST_DOUBLE"
    assert result["harness_authorization"] == "PASS"
    assert result["evidence_validation"] == "PASS"
    assert result["verifier_result"] == "PASS"
    assert result["model_local_digest_sha256"] == "a"*64
    assert result["candidate_type"] == "LOCALLY_IDENTIFIED_COMPACT_MODEL"
    assert result["qualified_slm_production"] is False
    assert result["model_is_slm_proven"] is False
    assert result["model_response_sha256"]
    assert result["total_duration_ns"] == 2200000000
    assert result["completion_tokens"] == 31
    assert result["prompt_tokens"] == 102
    assert result["production_approved"] is False
    assert len([c for c in calls if c[1] == "/api/chat"]) == 1
    request = [c[2] for c in calls if c[1] == "/api/chat"][0]
    assert request["model"] == "qwen3:4b"
    assert request["stream"] is False
    assert request["format"] == "json"
    assert "tools" not in request
    assert request["options"]["num_predict"] <= 128


def test_model_digest_changed_blocks_before_inference(tmp_path: Path):
    req, calls = fixed_transport(digest="b"*64)
    with pytest.raises(ModelQualificationError, match="MODEL_DIGEST_MISMATCH"):
        probe_verified_audio_case(
            **audited_case(tmp_path), transport=req,
            model_name="qwen3:4b", expected_digest="a"*64
        )
    assert not [c for c in calls if c[1] == "/api/chat"]


def test_forged_size_or_license_blocks_before_inference(tmp_path: Path):
    for i, args in enumerate(({"license_text": ""}, {"size": "400B"}, {"show_count": 9_000_000_000})):
        req, calls = fixed_transport(**args)
        case_dir = tmp_path / str(i)
        case_dir.mkdir()
        with pytest.raises(ModelQualificationError, match="MODEL_NOT_ELIGIBLE"):
            probe_verified_audio_case(
                **audited_case(case_dir), transport=req,
                model_name="qwen3:4b", expected_digest="a"*64
            )
        assert not [c for c in calls if c[1] == "/api/chat"]


def test_invalid_model_output_stays_failed_and_never_promotes(tmp_path: Path):
    req, _ = fixed_transport(reply='{"finding":"ATTENUATION_DETECTED","action":"PUBLISH_AUTOMATICALLY"}')
    result = probe_verified_audio_case(
        **audited_case(tmp_path), transport=req,
        model_name="qwen3:4b", expected_digest="a"*64
    )
    assert result["real_model_response_observed"] is False
    assert result["model_response_observed"] is True
    assert result["transport_provenance"] == "INJECTED_TEST_DOUBLE"
    assert result["verifier_result"] == "FAIL"
    assert result["production_approved"] is False


def test_host_receipt_corruption_rejected_without_model_call(tmp_path: Path):
    data = audited_case(tmp_path)
    data["receipt_path"].write_text(data["receipt_path"].read_text()+"tamper")
    req, calls = fixed_transport()
    with pytest.raises(Exception):
        probe_verified_audio_case(**data, transport=req, model_name="qwen3:4b", expected_digest="a"*64)
    assert not [c for c in calls if c[1] == "/api/chat"]


def test_empty_model_or_tool_calls_and_unfinished_response_rejected(tmp_path: Path):
    req, calls = fixed_transport()
    def malformed(method,path,payload=None):
        row = req(method,path,payload)
        if path == "/api/chat":
            row["message"]["tool_calls"] = [{"function":{"name":"delete_files"}}]
        return row
    with pytest.raises(ModelQualificationError, match="UNAUTHORIZED_MODEL_TOOL_CALL"):
        probe_verified_audio_case(
            **audited_case(tmp_path), transport=malformed,
            model_name="qwen3:4b", expected_digest="a"*64
        )


def test_private_checkpoint_is_create_only_and_owner_only(tmp_path: Path):
    path=tmp_path / "receipts" / "qualified.json"
    receipt={"schema":"HazewaveLocalAudioInferenceProof/v3","production_approved":False}
    digest=write_private_result(path,receipt)
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    assert path.stat().st_mode & 0o077 == 0
    with pytest.raises(ModelQualificationError,match="RECEIPT_EXISTS"):
        write_private_result(path,receipt)


def test_ollama_transport_uses_local_host_only_and_denies_redirects():
    from hazewave.slm_local_model_qualification import _RefuseRedirect, BASE_URL
    from urllib.request import Request
    assert BASE_URL == "http://127.0.0.1:11434"
    blocked = _RefuseRedirect().redirect_request(
        Request(BASE_URL + "/api/tags"), None, 302, "Found", {},
        "http://169.254.169.254/latest/meta-data"
    )
    assert blocked is None


def test_inventory_cli_preserves_remote_gateway_audit_if_ollama_is_offline(monkeypatch, capsys):
    from hazewave import slm_local_model_qualification as mod
    from hazewave import ninerouter
    def offline():
        raise ModelQualificationError("OLLAMA_LOCAL_UNAVAILABLE")
    monkeypatch.setattr(mod, "inventory_local_ollama", offline)
    monkeypatch.setattr(ninerouter, "load_9router_admission_receipt", lambda: None)
    assert mod.main(["--inventory"]) == 0
    report=json.loads(capsys.readouterr().out)
    assert report["runtime_available"] is False
    assert report["local_runtime_blocker"] == "OLLAMA_LOCAL_UNAVAILABLE"
    assert report["models"] == []
    assert report["remote_9router"]["receipt_present"] is False
    assert report["professional_approved"] is False


def test_gateway_alias_discovery_cannot_qualify_large_reference_as_small():
    from hazewave.slm_local_model_qualification import inspect_ninerouter_models
    receipt={
       "schema":"Hazewave9RouterFreeAdmissionReceipt/v2",
       "execution_admitted_models":["oc/mimo-v2.6-flash-free"],
       "catalog_discovered_models":["oc/mimo-v2.6-flash-free"]
    }
    result=inspect_ninerouter_models(receipt=receipt)
    assert result["receipt_present"] is True
    assert len(result["models"]) == 1
    item=result["models"][0]
    assert item["model_id"] == "oc/mimo-v2.6-flash-free"
    assert item["upstream_checkpoint_verified"] is False
    assert item["slm_qualified"] is False
    assert item["professional"] is False
