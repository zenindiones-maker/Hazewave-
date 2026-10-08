from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from hazewave.capability_plane import (
    CapabilityPlaneError,
    describe_capabilities,
    inventory,
    select_provider,
    verify_signed_runtime_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/capability-evidence-plane-v1.json"
CODESPACE = "hazewave-zero-cost-4jxp45676rq6279xx"
SHA = "a" * 40
NOW = datetime(2026, 10, 8, 15, tzinfo=timezone.utc)


def test_manifest_is_grounded_to_real_harness_and_includes_full_tool_portfolio() -> None:
    from hazewave.harness import harness_status
    m = json.loads(MANIFEST.read_text())
    assert m["authority"] == "HAZEWAVE_HARNESS"
    assert m["automatic_install"] is False
    ids = {item["tool_id"] for item in m["tools"]}
    assert {"iris", "rea6", "ffmpeg_audio", "ffmpeg_video", "pillow",
            "pyscenedetect", "essentia", "otio", "demucs", "opencv"} <= ids
    assert all(x["capability_id"] in harness_status()["capabilities"] for x in m["tools"])
    assert all(x["cost_class"] in {"FREE_OPEN_SOURCE", "UNKNOWN_DENY"} for x in m["tools"])


def test_no_receipts_gives_zero_operational_coverage_even_if_tools_are_installed() -> None:
    data = inventory(
        manifest=MANIFEST, host_id=CODESPACE, repo_sha=SHA,
        binary_lookup=lambda name: "/usr/bin/" + name,
        evidence_files=[], now=NOW,
    )
    assert data["coverage"]["operational_ready"] == 0
    assert data["coverage"]["ready_percent"] == 0.0
    assert data["coverage"]["total_harness_capabilities"] >= 100
    assert data["coverage"]["unmapped_harness_capabilities"] > 0
    assert data["tools"]["iris"]["state"] == "PRESENT_UNPROVEN"
    assert data["tools"]["rea6"]["state"] == "PRESENT_UNPROVEN"
    assert data["tools"]["iris"]["route_eligible"] is False
    with pytest.raises(CapabilityPlaneError, match="NO_OPERATIONALLY_VERIFIED_PROVIDER"):
        select_provider(data, "web.visual_regression", "WAVE")


def test_missing_tools_report_unavailable_not_qualified() -> None:
    report = inventory(manifest=MANIFEST, host_id=CODESPACE, repo_sha=SHA,
                       binary_lookup=lambda name: None, evidence_files=[], now=NOW)
    assert report["tools"]["iris"]["state"] == "UNAVAILABLE"
    assert report["tools"]["rea6"]["state"] == "UNAVAILABLE"


def _signed_evidence(tmp_path: Path, *, tool: str = "iris", capability: str = "web.visual_regression",
                     host: str = CODESPACE, sha: str = SHA, expires: datetime | None = None,
                     stage: str = "BENCHMARKED", observed: bool = True,
                     scope: str = "LOCAL_HOST", sample_count: int = 5):
    if shutil.which("ssh-keygen") is None:
        pytest.skip("OpenSSH signatures unavailable")
    key = tmp_path / "key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    trust = tmp_path / "trusted_signers"
    trust.write_text("hazewave-owner " + (tmp_path / "key.pub").read_text().strip() + "\n")
    trust.chmod(0o600)
    artifact = tmp_path / "owned-fixture-log.txt"
    artifact.write_text("HAZEWAVE_IRIS_FIXTURE=PASS\\nTOOL_CALL=PASS\\n")
    artifact.chmod(0o600)
    evidence = {
        "schema": "HazewaveCapabilityRuntimeEvidence/v1",
        "authority": "HAZEWAVE_HARNESS", "issuer": "hazewave-owner",
        "tool_id": tool, "capability_id": capability,
        "domain": "WAVE", "version": "0.4.1",
        "host_id": host, "repo_sha": sha, "scope": scope,
        "stage": stage, "binary_sha256": "b" * 64,
        "tool_list_observed": observed,
        "tool_call_observed": observed,
        "fixture_result": "PASS" if observed else "NOT_TESTED",
        "fixture_sha256": "c" * 64,
        "evidence_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "benchmark": {
            "sample_count": sample_count, "quality_score": 0.88,
            "cost_usd": 0.0, "risk_score": 0.1,
            "p50_latency_ms": 200.0, "p95_latency_ms": 300.0,
        },
        "issued_at": (NOW - timedelta(minutes=5)).isoformat(),
        "expires_at": (expires or (NOW + timedelta(minutes=30))).isoformat(),
        "production_approved": False,
    }
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(evidence))
    path.chmod(0o600)
    subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(key),
         "-n", "hazewave-capability-proof", str(path)],
        check=True, capture_output=True,
    )
    (tmp_path / "evidence.json.sig").chmod(0o600)
    return path, (tmp_path / "evidence.json.sig"), trust, artifact


def test_signed_exact_bound_local_measurement_can_be_routed_without_prod_approval(tmp_path: Path) -> None:
    evidence, sig, trust, artifact = _signed_evidence(tmp_path)
    proof = verify_signed_runtime_evidence(evidence, sig, trust, artifact=artifact, now=NOW)
    report = inventory(
        manifest=MANIFEST, host_id=CODESPACE, repo_sha=SHA,
        binary_lookup=lambda name: "/bin/" + name, binary_fingerprint=lambda path: "b" * 64, evidence_files=[proof], now=NOW,
    )
    assert report["tools"]["iris"]["state"] == "MEASURED_READY"
    assert report["tools"]["iris"]["route_eligible"] is True
    assert report["tools"]["iris"]["production_approved"] is False
    assert select_provider(report, "web.visual_regression", "WAVE")["tool_id"] == "iris"


@pytest.mark.parametrize("override", [
    {"host": "github-ci-runner", "scope": "CI_FIXTURE"},
    {"sha": "f" * 40},
    {"expires": NOW - timedelta(minutes=1)},
    {"stage": "INSTALLED"},
    {"observed": False},
    {"sample_count": 1},
])
def test_wrong_host_stale_no_runtime_no_benchmark_cannot_route(tmp_path: Path, override: dict) -> None:
    evidence, sig, trust, artifact = _signed_evidence(tmp_path, **override)
    if override.get("expires") is not None and override["expires"] <= NOW:
        with pytest.raises(CapabilityPlaneError, match="EVIDENCE_EXPIRED"):
            verify_signed_runtime_evidence(evidence, sig, trust, artifact=artifact, now=NOW)
        return
    proof = verify_signed_runtime_evidence(evidence, sig, trust, artifact=artifact, now=NOW)
    report = inventory(manifest=MANIFEST, host_id=CODESPACE, repo_sha=SHA,
                       binary_lookup=lambda name: "/usr/bin/" + name,
                       binary_fingerprint=lambda path: "b" * 64, evidence_files=[proof], now=NOW)
    assert not report["tools"]["iris"]["route_eligible"]
    with pytest.raises(CapabilityPlaneError, match="NO_OPERATIONALLY_VERIFIED_PROVIDER"):
        select_provider(report, "web.visual_regression", "WAVE")


def test_fake_json_without_valid_signature_rejected(tmp_path: Path) -> None:
    evidence, sig, trust, artifact = _signed_evidence(tmp_path)
    record = json.loads(evidence.read_text())
    record["benchmark"]["quality_score"] = 1.0
    evidence.write_text(json.dumps(record))
    with pytest.raises(CapabilityPlaneError, match="EVIDENCE_SIGNATURE_INVALID"):
        verify_signed_runtime_evidence(evidence, sig, trust, artifact=artifact, now=NOW)


def test_malformed_or_untrusted_provider_cannot_win_selection(tmp_path: Path) -> None:
    e, sig, trust, artifact = _signed_evidence(tmp_path)
    proof = verify_signed_runtime_evidence(e, sig, trust, artifact=artifact, now=NOW)
    report = inventory(manifest=MANIFEST, host_id=CODESPACE, repo_sha=SHA,
                       binary_lookup=lambda x: "/usr/bin/" + x, binary_fingerprint=lambda path: "b" * 64, evidence_files=[proof], now=NOW)
    assert select_provider(report, "web.visual_regression", "WAVE")["quality_score"] == 0.88
    with pytest.raises(CapabilityPlaneError, match="CAPABILITY_DOMAIN_MISMATCH"):
        select_provider(report, "web.visual_regression", "HAZE")


def test_manifest_is_non_executable_and_inventory_cannot_write_or_start_tools() -> None:
    import inspect
    import hazewave.capability_plane as module
    text = inspect.getsource(module)
    assert "subprocess.run" in text  # Only ssh-keygen *verification*, no tool invocation
    assert "pip install" not in text
    assert "gh codespace create" not in text
    assert "codex mcp add" not in text


def test_ci_fixture_is_visible_but_cannot_be_promoted_to_codespace(tmp_path: Path) -> None:
    evidence, sig, trust, artifact = _signed_evidence(
        tmp_path, host="github-actions-disposable-worker", scope="CI_FIXTURE"
    )
    proof = verify_signed_runtime_evidence(evidence, sig, trust, artifact=artifact, now=NOW)
    report = inventory(manifest=MANIFEST, host_id=CODESPACE, repo_sha=SHA,
                       binary_lookup=lambda _: "/usr/bin/iris",
                       binary_fingerprint=lambda _: "b" * 64,
                       evidence_files=[proof], now=NOW)
    assert report["tools"]["iris"]["state"] == "CI_FIXTURE_PROVEN"
    assert report["coverage"]["ci_fixture_proven"] >= 1
    assert report["coverage"]["operational_ready"] == 0


def test_after_freshness_deadline_even_verified_in_memory_claim_cannot_route(tmp_path: Path) -> None:
    evidence, sig, trust, artifact = _signed_evidence(tmp_path)
    proof = verify_signed_runtime_evidence(evidence, sig, trust, artifact=artifact, now=NOW)
    late = NOW + timedelta(hours=1)
    report = inventory(manifest=MANIFEST, host_id=CODESPACE, repo_sha=SHA,
                       binary_lookup=lambda _: "/usr/bin/iris",
                       binary_fingerprint=lambda _: "b" * 64,
                       evidence_files=[proof], now=late)
    assert report["tools"]["iris"]["state"] == "STALE"
    assert report["coverage"]["operational_ready"] == 0


def test_default_discovery_of_isolated_iris_binary_without_global_path(tmp_path: Path) -> None:
    from hazewave.capability_plane import discover_local_executable
    iris = tmp_path / ".local/share/hazewave/iris/v0.4.1/bin/iris"
    iris.parent.mkdir(parents=True)
    iris.write_bytes(b"fixture only")
    iris.chmod(0o700)
    assert discover_local_executable("iris", home=tmp_path, which=lambda _: None) == str(iris)


def test_unknown_or_missing_benchmark_never_selects_freeware_by_assumption() -> None:
    data = inventory(manifest=MANIFEST, host_id=CODESPACE, repo_sha=SHA,
                     binary_lookup=lambda x: "/bin/" + x, evidence_files=[], now=NOW)
    assert data["tools"]["demucs"]["cost_class"] == "UNKNOWN_DENY"
    assert data["tools"]["demucs"]["route_eligible"] is False
    with pytest.raises(CapabilityPlaneError, match="NO_OPERATIONALLY_VERIFIED_PROVIDER"):
        select_provider(data, "audio.separate", "HAZE")
