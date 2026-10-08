"""Host synthetic AV execution must be observed without any readiness promotion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from hazewave.host_av_evidence import HostAvEvidenceError, verify_host_av_evidence
from hazewave.harness_connection_inventory import inventory_all_capabilities

SHA = "a" * 40


def proof(tmp_path: Path):
    log_dir = tmp_path / "audits" / SHA
    log_dir.mkdir(parents=True)
    receipt_dir = tmp_path / "research-lab" / "av-metrics-20261008T210000Z"
    receipt_dir.mkdir(parents=True)
    result = {
        "schema": "HazewaveSyntheticAudioVideoFidelity/v1",
        "harness_authority": "HAZEWAVE_HARNESS",
        "source": "OWNED_SYNTHETIC_MEDIA",
        "actual_ffmpeg_executed": True,
        "synthetic_audio_verified": True,
        "synthetic_video_verified": True,
        "haze_authorization_id": "haze-fixture-test",
        "wave_authorization_id": "wave-fixture-test",
        "owner_media_analyzed": False,
        "agent_mcp_connected": False,
        "capability_plane_ready": False,
        "production_approved": False,
        "no_subjective_audio_or_visual_approval": True,
        "audio_attenuation_detected_db": 12.0,
        "identical_video_ssim": 1.0,
        "altered_video_ssim": 0.773094,
        "sample_hashes": {
            "reference_wav": "1" * 64, "altered_wav": "2" * 64,
            "reference_video": "3" * 64, "altered_video": "4" * 64,
        }
    }
    log = log_dir / "av_synthetic_fixture.log"
    receipt = receipt_dir / "av-receipt-20261008T210000Z.json"
    receipt.write_bytes((json.dumps(result, sort_keys=True) + "\n").encode())
    log.write_text("HAZEWAVE_AV_FIDELITY=PASS_SYNTHETIC\n" +
                   json.dumps(result, sort_keys=True) +
                   "\nHAZEWAVE_AV_METRICS=PASS:OWNED_SYNTHETIC_ONLY\n")
    log.chmod(0o600)
    receipt.chmod(0o600)
    return log, receipt


def inspect(log: Path, receipt: Path):
    return verify_host_av_evidence(
        log_path=log, receipt_path=receipt, reviewed_sha=SHA,
        expected_log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
        expected_receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest()
    )


def test_real_log_and_durable_receipt_project_execution_without_readiness(tmp_path: Path):
    log, receipt = proof(tmp_path)
    observation = inspect(log, receipt)
    assert observation["schema"] == "HazewaveObservedHostAVExecution/v1"
    assert observation["evidence_state"] == "EXECUTED"
    assert observation["provenance"] == "LOCAL_LOG_AND_RECEIPT_INTEGRITY_NOT_INDEPENDENT_ATTESTATION"
    assert observation["reviewed_repo_sha"] == SHA
    assert observation["metrics"]["audio_attenuation_db"] == 12.0
    report = inventory_all_capabilities(host_av_execution=observation)
    assert report["capabilities"]["audio.qc"]["fixture_execution"] == "EXECUTED_SYNTHETIC_UNATTESTED"
    assert report["capabilities"]["visual.qc"]["fixture_execution"] == "EXECUTED_SYNTHETIC_UNATTESTED"
    assert report["capabilities"]["audio.qc"]["ready"] is False
    assert report["capabilities"]["visual.qc"]["live_agent_mcp_connected"] == "UNVERIFIED"
    assert report["summary"]["host_synthetic_av_executions_observed"] == 2
    assert report["summary"]["ready_on_existing_codespace"] == 0
    assert report["summary"]["agent_connected_on_existing_codespace"] == 0
    assert report["production_approved"] is False


def test_tampered_receipt_rejected_even_when_hash_is_updated(tmp_path: Path):
    log, receipt = proof(tmp_path)
    obj = json.loads(receipt.read_text())
    obj["altered_video_ssim"] = 1.0
    receipt.write_text(json.dumps(obj, sort_keys=True) + "\n")
    with pytest.raises(HostAvEvidenceError, match="LOG_RECEIPT_MISMATCH"):
        inspect(log, receipt)


def test_bad_metrics_rejected_even_with_forged_consistent_hashes(tmp_path: Path):
    log, receipt = proof(tmp_path)
    obj = json.loads(receipt.read_text())
    obj["audio_attenuation_detected_db"] = 0.0
    receipt.write_text(json.dumps(obj, sort_keys=True) + "\n")
    log.write_text("HAZEWAVE_AV_FIDELITY=PASS_SYNTHETIC\n" +
                   json.dumps(obj, sort_keys=True) +
                   "\nHAZEWAVE_AV_METRICS=PASS:OWNED_SYNTHETIC_ONLY\n")
    with pytest.raises(HostAvEvidenceError, match="METRIC_NEGATIVE_CONTROL_FAILED"):
        inspect(log, receipt)


def test_claimed_agent_connected_and_production_status_are_rejected(tmp_path: Path):
    log, receipt = proof(tmp_path)
    obj = json.loads(receipt.read_text())
    obj["agent_mcp_connected"] = True
    obj["production_approved"] = True
    receipt.write_text(json.dumps(obj, sort_keys=True) + "\n")
    log.write_text("HAZEWAVE_AV_FIDELITY=PASS_SYNTHETIC\n" +
                   json.dumps(obj, sort_keys=True) +
                   "\nHAZEWAVE_AV_METRICS=PASS:OWNED_SYNTHETIC_ONLY\n")
    with pytest.raises(HostAvEvidenceError, match="UNAUTHORIZED_READINESS_CLAIM"):
        inspect(log, receipt)


def test_untrusted_file_permissions_and_symlinks_rejected(tmp_path: Path):
    log, receipt = proof(tmp_path)
    log.chmod(0o644)
    with pytest.raises(HostAvEvidenceError, match="UNSAFE_FILE"):
        inspect(log, receipt)
    log.chmod(0o600)
    alias = tmp_path / "linked.json"
    alias.symlink_to(receipt)
    with pytest.raises(HostAvEvidenceError, match="UNSAFE_FILE"):
        inspect(log, alias)


def test_unverified_inputs_do_not_affect_declarative_catalog() -> None:
    report = inventory_all_capabilities()
    assert report["summary"]["host_synthetic_av_executions_observed"] == 0
    assert report["capabilities"]["audio.qc"]["fixture_execution"] == "UNVERIFIED"
    assert report["summary"]["ready_on_existing_codespace"] == 0
