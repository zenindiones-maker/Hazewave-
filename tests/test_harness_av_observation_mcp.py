"""MCP read-only observation of previously verified HAZE/WAVE host receipts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from hazewave.harness_research_mcp import AvEvidenceBinding, FixtureMcpGateway, serve_request

ROOT = Path(__file__).resolve().parents[1]
AV_SHA = "2d779b38cfa0d8b093160b9df5b7b130a13fa538"


def current_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        text=True, timeout=10, check=True
    ).stdout.strip()


def fixture(tmp_path: Path):
    logs = tmp_path / "audits" / AV_SHA
    logs.mkdir(parents=True)
    directory = tmp_path / "research-lab" / "av-metrics-20261008T210000Z"
    directory.mkdir(parents=True)
    rec = {
        "schema": "HazewaveSyntheticAudioVideoFidelity/v1",
        "harness_authority": "HAZEWAVE_HARNESS",
        "source": "OWNED_SYNTHETIC_MEDIA",
        "actual_ffmpeg_executed": True,
        "synthetic_audio_verified": True,
        "synthetic_video_verified": True,
        "haze_authorization_id": "fixture-haze",
        "wave_authorization_id": "fixture-wave",
        "owner_media_analyzed": False,
        "agent_mcp_connected": False,
        "capability_plane_ready": False,
        "production_approved": False,
        "no_subjective_audio_or_visual_approval": True,
        "audio_attenuation_detected_db": 12,
        "identical_video_ssim": 1.0,
        "altered_video_ssim": 0.773094,
        "sample_hashes": {
            "reference_wav": "1"*64, "altered_wav": "2"*64,
            "reference_video": "3"*64, "altered_video": "4"*64,
        }
    }
    log = logs / "av_synthetic_fixture.log"
    receipt = directory / "av-receipt-20261008T210000Z.json"
    log.write_text("HAZEWAVE_AV_FIDELITY=PASS_SYNTHETIC\n" +
                   json.dumps(rec, sort_keys=True) +
                   "\nHAZEWAVE_AV_METRICS=PASS:OWNED_SYNTHETIC_ONLY\n")
    receipt.write_text(json.dumps(rec, sort_keys=True) + "\n")
    log.chmod(0o600)
    receipt.chmod(0o600)
    return AvEvidenceBinding(
        log_path=log, receipt_path=receipt, reviewed_sha=AV_SHA,
        log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
        receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest()
    )


def client(gateway: FixtureMcpGateway, method: str, params: dict, rid: int=1):
    return serve_request(gateway, {
        "jsonrpc": "2.0", "id": rid, "method": method, "params": params
    })


def test_mcp_haze_wave_observation_only_exposed_with_explicit_server_binding(tmp_path: Path):
    no_evidence = FixtureMcpGateway(workspace=ROOT, expected_sha=current_sha(),
                                   state_root=tmp_path)
    assert no_evidence.supported_tools() == []
    yes = FixtureMcpGateway(workspace=ROOT, expected_sha=current_sha(),
                            state_root=tmp_path, av_evidence=fixture(tmp_path))
    tools = client(yes, "tools/list", {})["result"]["tools"]
    assert [x["name"] for x in tools] == ["harness_av_observed_evidence"]
    assert tools[0]["inputSchema"] == {"type": "object", "additionalProperties": False}


def test_mcp_can_read_real_private_receipt_without_promoting_any_capability(tmp_path: Path):
    gateway = FixtureMcpGateway(workspace=ROOT, expected_sha=current_sha(),
                                state_root=tmp_path, av_evidence=fixture(tmp_path))
    response = client(gateway, "tools/call", {
        "name": "harness_av_observed_evidence", "arguments": {}
    })
    assert response["result"]["isError"] is False, response
    parsed = json.loads(response["result"]["content"][0]["text"])
    assert parsed["observation"]["evidence_state"] == "EXECUTED"
    assert parsed["haze"]["status"] == "EXECUTED_SYNTHETIC_UNATTESTED"
    assert parsed["wave"]["status"] == "EXECUTED_SYNTHETIC_UNATTESTED"
    assert parsed["agent_mcp_session_connected"] is False
    assert parsed["production_approved"] is False
    assert parsed["capability_plane_ready"] is False
    assert parsed["harness_authority"] == "HAZEWAVE_HARNESS"
    assert parsed["tool_call_observed"] is True
    assert gateway.completed_calls == 1


def test_mcp_refuses_any_agent_supplied_path_or_metadata(tmp_path: Path):
    gateway = FixtureMcpGateway(workspace=ROOT, expected_sha=current_sha(),
                                state_root=tmp_path, av_evidence=fixture(tmp_path))
    for extras in ({"url": "https://example.com"}, {"path": "/etc/shadow"},
                   {"task_id": "unauthorized-0001"}, {"reviewed_sha": "a"*40}):
        response = client(gateway, "tools/call", {
            "name": "harness_av_observed_evidence", "arguments": extras
        })
        assert response["result"]["isError"] is True
    assert gateway.completed_calls == 0


def test_mcp_private_receipt_tampering_is_a_tool_error_and_consumes_budget(tmp_path: Path):
    binding = fixture(tmp_path)
    gateway = FixtureMcpGateway(workspace=ROOT, expected_sha=current_sha(),
                                state_root=tmp_path, av_evidence=binding)
    binding.receipt_path.write_text(binding.receipt_path.read_text() + "changed")
    response = client(gateway, "tools/call", {
        "name": "harness_av_observed_evidence", "arguments": {}
    })
    assert response["result"]["isError"] is True
    assert "BLOCKED" in response["result"]["content"][0]["text"]
    assert gateway.completed_calls == 1


def test_mcp_agent_observation_still_enforces_budget(tmp_path: Path):
    gateway = FixtureMcpGateway(workspace=ROOT, expected_sha=current_sha(),
                                state_root=tmp_path, av_evidence=fixture(tmp_path),
                                max_calls=1)
    first = client(gateway, "tools/call", {
        "name": "harness_av_observed_evidence", "arguments": {}
    })
    second = client(gateway, "tools/call", {
        "name": "harness_av_observed_evidence", "arguments": {}
    })
    assert first["result"]["isError"] is False
    assert second["result"]["isError"] is True
    assert "BUDGET" in second["result"]["content"][0]["text"]


def test_real_stdio_mcp_round_trip_through_python_process(tmp_path: Path):
    binding = fixture(tmp_path)
    sha = current_sha()
    argv = [
        sys.executable, "-m", "hazewave.harness_research_mcp",
        "--workspace", str(ROOT),
        "--expected-sha", sha,
        "--state-root", str(tmp_path),
        "--av-log", str(binding.log_path),
        "--av-receipt", str(binding.receipt_path),
        "--av-reviewed-sha", binding.reviewed_sha,
        "--av-log-sha256", binding.log_sha256,
        "--av-receipt-sha256", binding.receipt_sha256
    ]
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "hazewave-ci-fixture-client", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "harness_av_observed_evidence", "arguments": {}}},
    ]
    result = subprocess.run(
        argv, input="\n".join(json.dumps(r) for r in requests) + "\n",
        text=True, capture_output=True, cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        timeout=20
    )
    assert result.returncode == 0, result.stderr
    lines = [json.loads(x) for x in result.stdout.splitlines()]
    assert len(lines) == 3
    assert lines[0]["result"]["protocolVersion"] == "2025-11-25"
    assert [x["name"] for x in lines[1]["result"]["tools"]] == [
        "harness_av_observed_evidence"
    ]
    assert lines[2]["result"]["isError"] is False, lines[2]
    assert json.loads(lines[2]["result"]["content"][0]["text"])["agent_mcp_session_connected"] is False
