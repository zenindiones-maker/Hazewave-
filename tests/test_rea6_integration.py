from __future__ import annotations

import json
from pathlib import Path

import pytest

from hazewave.rea6_integration import (
    Rea6ContractError,
    audited_capability,
    inspect_ghidra_evidence,
    require_absolute_mcp_paths,
)

ROOT = Path(__file__).resolve().parents[1]
TARGET = "a" * 64


def _evidence(digest: str = TARGET) -> dict:
    return {
        "evidence_id": "ev_" + "b" * 64,
        "subject": {
            "name": "safe_test_fixture",
            "digest": {"sha256": digest},
            "format": "elf",
            "architecture": "x86_64",
            "local_path": "/usr/bin/true",
        },
        "provider": {"id": "ghidra", "name": "Ghidra", "version": "12.1.4"},
        "predicate_type": "native-function-observation",
        "operation": "list_procedures",
        "parameters": {},
        "raw_result": None,
        "normalized_result": [{"address": "0x401000", "value": "main"}],
        "confidence": "observed",
        "authority": "shipped-artifact",
        "environment": None,
        "limitations": ["Static disassembly is not the original source."],
        "locations": [{"kind": "address", "address": "0x401000"}],
        "evidence_links": [],
    }


def test_rea6_policy_and_installer_are_exactly_pinned() -> None:
    policy = json.loads((ROOT / "config/reverse-engineering-foundation-v1.json").read_text())
    rea = next(row for row in policy["tools"] if row["tool_id"] == "rea")
    assert rea["version"] == "6.0.0"
    assert rea["package"] == "rea-agents@6.0.0"
    assert rea["source_repository"] == "morluto/rea"
    assert rea["grants_execution_authority"] is False
    installer = (ROOT / "scripts/codespaces/install-reverse-engineering-foundation.sh").read_text()
    doctor = (ROOT / "scripts/codespaces/reverse-engineering-doctor.sh").read_text()
    assert 'REA_VERSION="6.0.0"' in installer
    assert '"rea-agents@6.0.0"' in installer
    assert 'grep -F "6.0.0"' in doctor
    assert "rea-agents@latest" not in installer


@pytest.mark.parametrize("candidate", ["./hello.so", "../data/snap.json", "tmp/evidence.json", ""])
def test_rea6_mcp_disallows_relative_paths(candidate: str) -> None:
    with pytest.raises(Rea6ContractError, match="REA6_ABSOLUTE_PATH_REQUIRED"):
        require_absolute_mcp_paths({"path": candidate})


def test_rea6_mcp_accepts_absolute_paths_and_ignores_nonpath_options() -> None:
    args = {"path": "/mnt/data/source.so", "snapshot_path": "/mnt/data/obs.json", "provider_id": "ghidra"}
    assert require_absolute_mcp_paths(args) == args


def test_rea6_mcp_rejects_unadmitted_provider() -> None:
    with pytest.raises(Rea6ContractError, match="REA6_PROVIDER_FORBIDDEN"):
        require_absolute_mcp_paths({"path": "/safe/test.so", "provider_id": "hopper"})


def test_rea6_evidence_accepts_only_ghidra_bound_observed_native_target() -> None:
    output = inspect_ghidra_evidence(_evidence(), expected_sha256=TARGET)
    assert output["state"] == "EVIDENCE_VALIDATED"
    assert output["target_sha256"] == TARGET
    assert output["provider_id"] == "ghidra"
    assert output["grants_execution_authority"] is False
    assert output["production_approved"] is False


def test_rea6_evidence_rejects_digest_substitution() -> None:
    with pytest.raises(Rea6ContractError, match="REA6_TARGET_DIGEST_MISMATCH"):
        inspect_ghidra_evidence(_evidence("c" * 64), expected_sha256=TARGET)


@pytest.mark.parametrize("field,value", [
    ("provider", {"id": "rea-workflow", "name": "REA", "version": "6.0.0"}),
    ("confidence", "inferred"),
    ("normalized_result", []),
    ("locations", []),
    ("authority", "analyst-inference"),
])
def test_rea6_evidence_rejects_unverified_or_empty_observation(field: str, value: object) -> None:
    evidence = _evidence()
    evidence[field] = value
    with pytest.raises(Rea6ContractError):
        inspect_ghidra_evidence(evidence, expected_sha256=TARGET)


def test_rea6_integrates_as_subordinate_haze_and_wave_research_capability() -> None:
    assert audited_capability("HAZE") == "research.audio.inspect"
    assert audited_capability("WAVE") == "research.visual.inspect"
    with pytest.raises(Rea6ContractError):
        audited_capability("BRIDGE")


def test_existing_harness_registry_has_no_cross_domain_research_escalation() -> None:
    from hazewave.harness import HazewaveTask, issue_authorization, route_task
    for capability, domain in (("research.audio.inspect", "HAZE"), ("research.visual.inspect", "WAVE")):
        task = HazewaveTask(task_id="rea6-contract", goal="Authorized evidence only", required_capability=capability, requested_domain=domain)
        grant = issue_authorization(route_task(task))
        assert grant.domain == domain
        assert grant.authority == "HAZEWAVE_HARNESS"
    with pytest.raises(PermissionError, match="DOMAIN_CAPABILITY_MISMATCH"):
        route_task(HazewaveTask(task_id="bad", goal="invalid cross domain", required_capability="research.audio.inspect", requested_domain="WAVE"))
