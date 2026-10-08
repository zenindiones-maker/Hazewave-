from pathlib import Path
import json
import subprocess
import sys

import pytest

from hazewave.rea6_provider_conformance import (
    ReaProviderError, summarize_provider_matrix, validate_javascript_probe
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "codespaces" / "rea6-provider-conformance.sh"
FIXTURE = ROOT / "tests" / "fixtures" / "rea6-javascript-owned"


def test_script_uses_exact_fixed_providers_and_never_autoselects_proprietary_tool() -> None:
    raw = SCRIPT.read_text()
    for token in ("--preflight", "--native", "--javascript", "--managed-negative",
                  "reverse-engineering-doctor.sh", "analyze-javascript-application",
                  "inspect-managed-artifact", "REA_CONFORMANCE_CODESPACE_PROVEN=NO"):
        assert token in raw
    for banned in ("gh codespace create", "sudo ", "hopper", "rea-agents@latest",
                   "hazewave-reflex serve-stop", "git reset --hard", "REA_ANALYSIS_PROVIDER=auto"):
        assert banned not in raw
    check = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert check.returncode == 0, check.stderr


def test_owned_js_application_fixture_contains_no_network_or_process_execution() -> None:
    for file in ("package.json", "main.js", "views/home.js"):
        assert (FIXTURE / file).is_file()
    for file in FIXTURE.rglob("*.js"):
        data = file.read_text()
        assert "child_process" not in data
        assert "fetch(" not in data
        assert "http://" not in data
        assert "https://" not in data


def test_js_probe_rejects_arbitrary_short_or_incomplete_result() -> None:
    for data in ({}, [], {"status": "ok"}, {"evidence": []}, {"graph": {}}):
        with pytest.raises(ReaProviderError):
            validate_javascript_probe(data, fixture_sha256="a" * 64)


def test_matrix_never_conflates_cli_with_runtime_on_codespace() -> None:
    matrix = summarize_provider_matrix({
        "ghidra": {"status": "NOT_TESTED"},
        "javascript_static": {"status": "CI_PROVEN", "evidence_hash": "a" * 64},
        "managed_static": {"status": "NEGATIVE_CONTROL_PROVEN"},
        "rizin": {"status": "TOOL_DISCOVERED"},
        "frida": {"status": "TOOL_DISCOVERED"},
    })
    assert matrix["codespace_native_ready"] is False
    assert matrix["agent_mcp_connected"] is False
    assert matrix["production_approved"] is False
    assert matrix["fully_ready"] is False
    assert matrix["capability_coverage"]["positive_runtime_routes"] == 0


def test_provider_matrix_rejects_fake_pass_or_missing_route() -> None:
    with pytest.raises(ReaProviderError, match="UNKNOWN_PROVIDER_ROUTE"):
        summarize_provider_matrix({"ghidra": {"status": "PASS"}})
    with pytest.raises(ReaProviderError, match="PROVIDER_STATUS_INVALID"):
        summarize_provider_matrix({"ghidra": {"status": "READY"}})


def test_native_ghidra_readiness_does_not_depend_on_auxiliary_frida_rizin() -> None:
    raw = SCRIPT.read_text()
    assert "rea doctor --provider ghidra --json" in raw
    assert "rea function" in raw
    assert "-m hazewave.rea6_integration verify-evidence" in raw
    assert "reverse-engineering-doctor.sh --deep" not in raw
    assert "GHIDRA_INSTALL_DIR" in raw
    assert "REA6_NATIVE_AUXILIARY=NOT_REQUIRED" in raw
