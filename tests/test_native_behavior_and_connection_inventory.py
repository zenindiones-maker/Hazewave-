from __future__ import annotations
from pathlib import Path
import json
import shutil
import subprocess
import pytest

from hazewave.native_behavior_qualification import (
    NativeBehaviorError,
    make_test_inputs,
    qualify_native_behavior,
)
from hazewave.harness_connection_inventory import inventory_all_capabilities

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tests" / "fixtures" / "native-owned-reconstruction"


def _cc() -> str:
    if not shutil.which("cc"):
        pytest.skip("C compiler unavailable on host")
    return "cc"


def test_inventory_contains_every_actual_harness_capability_even_if_unconnected():
    from hazewave.harness import harness_status
    report = inventory_all_capabilities(ROOT / "config/capability-evidence-plane-v1.json")
    source_caps = set(harness_status()["capabilities"])
    assert set(report["capabilities"]) == source_caps
    assert report["summary"]["declared"] == len(source_caps)
    assert report["summary"]["provider_mapped"] == 10
    assert report["summary"]["provider_unmapped"] == len(source_caps) - 10
    assert report["summary"]["ready_on_existing_codespace"] == 0
    assert report["summary"]["agent_connected_on_existing_codespace"] == 0
    assert all(not item["production_approved"] for item in report["capabilities"].values())


def test_missing_provider_is_not_misclassified_as_missing_installed_tool():
    report = inventory_all_capabilities(ROOT / "config/capability-evidence-plane-v1.json")
    assert report["capabilities"]["web.visual_regression"]["mapping"] == "MAPPED_UNVERIFIED"
    assert report["capabilities"]["audio.separate"]["mapping"] == "MAPPED_UNVERIFIED"
    assert report["capabilities"]["audio.mix"]["mapping"] == "NO_EXACT_PROVIDER_MAPPING"
    assert report["capabilities"]["research.visual.inspect"]["selected_provider"] is None
    assert report["capabilities"]["research.visual.inspect"]["ready"] is False


def test_connection_sequence_is_evidence_gated_not_bulk_autoinstall():
    report = inventory_all_capabilities(ROOT / "config/capability-evidence-plane-v1.json")
    queue = report["connection_sequence"]
    assert [x["route"] for x in queue[:3]] == [
        "rea6.ghidra_native", "rea6.js_static", "iris.local_fixture",
    ]
    assert all(x["next_action"] in ("PROVE_OWNED_FIXTURE", "QUALIFY_PROVIDER", "WAIT_FOR_SECURITY_ISOLATION") for x in queue)
    assert all(x["auto_connect"] is False for x in queue)
    assert report["authority"] == "HAZEWAVE_HARNESS"
    assert report["codespace_proven"] is False


def test_native_vectors_include_boundary_cases_and_multiple_seeds():
    vectors = make_test_inputs(seed=42, count=300)
    assert {-1000, -8, -7, -6, 0, 8, 9, 10, 1000} <= set(vectors)
    assert len(vectors) == len(set(vectors))
    assert all(-1000 <= n <= 1000 for n in vectors)


def test_native_actual_compiled_source_and_equivalent_candidate_pass(tmp_path):
    report = qualify_native_behavior(
        original_source=SRC / "original.c",
        candidate_source=SRC / "reconstruction.c",
        state_root=tmp_path / "receipts",
        compiler=_cc(),
        seed=42,
        count=300,
    )
    assert report["oracle_runs"] >= 300
    assert report["candidate_runs"] == report["oracle_runs"]
    assert report["semantic_status"] == "BOUNDED_BEHAVIOR_MATCH"
    assert report["universal_equivalence_proven"] is False
    assert report["reconstruction_automatically_generated"] is False
    assert report["native_binary_executed"] is True
    assert report["ghidra_provider_attested"] is False
    assert report["production_approved"] is False
    assert report["receipt_sha256"]
    receipts = list((tmp_path / "receipts").glob("*.json"))
    assert len(receipts) == 1
    assert receipts[0].stat().st_mode & 0o077 == 0


def test_native_mutation_is_rejected_and_never_yields_false_pass(tmp_path):
    with pytest.raises(NativeBehaviorError, match="BEHAVIOR_MISMATCH"):
        qualify_native_behavior(
            original_source=SRC / "original.c",
            candidate_source=SRC / "mutant.c",
            state_root=tmp_path / "wrong",
            compiler=_cc(),
            seed=42,
            count=300,
        )
    receipts = list((tmp_path / "wrong").glob("*.json"))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text())["semantic_status"] == "REJECTED_BEHAVIOR_MISMATCH"


def test_native_source_is_bounded_and_denies_arbitrary_compilation(tmp_path):
    (tmp_path / "evil.c").write_text("int main(){return 0;}")
    with pytest.raises(NativeBehaviorError, match="SOURCE_NOT_ADMITTED"):
        qualify_native_behavior(
            original_source=tmp_path / "evil.c", candidate_source=SRC / "reconstruction.c",
            state_root=tmp_path / "state", compiler=_cc(), seed=42, count=50,
        )


def test_native_result_never_automatically_promotes_ghidra_or_live_mcp(tmp_path):
    report = qualify_native_behavior(
        original_source=SRC / "original.c",
        candidate_source=SRC / "reconstruction.c",
        state_root=tmp_path / "audit",
        compiler=_cc(), seed=7, count=100,
    )
    assert report["harness_authority"] == "HAZEWAVE_HARNESS"
    assert report["owner_agent_mcp_connected"] is False
    assert report["codespace_runtime_proven"] is False
    assert report["ghidra_provider_attested"] is False


def test_harness_itself_exposes_full_inventory_cli_not_only_subordinate_module():
    from os import environ
    env={**environ, "PYTHONPATH": str(ROOT/"src")}
    r=subprocess.run([__import__("sys").executable, "-m", "hazewave.harness", "inventory"],
                     cwd=ROOT, env=env, capture_output=True, text=True, timeout=15)
    assert r.returncode == 0, r.stderr
    payload=json.loads(r.stdout)
    assert payload["schema"]=="HazewaveFullCapabilityConnectionInventory/v1"
    assert payload["summary"]["declared"]==124
    assert payload["summary"]["ready_on_existing_codespace"]==0
    assert payload["authority"]=="HAZEWAVE_HARNESS"


def test_codespace_native_proofs_are_opt_in_host_guarded_and_never_autopromoted():
    path=ROOT/"scripts/codespaces/native-behavior-rea6-probe.sh"
    code=path.read_text()
    assert "hazewave-zero-cost-4jxp45676rq6279xx" in code
    assert "--inventory|--behavior|--ghidra" in code
    assert "HAZEWAVE_NATIVE_EXPECTED_SHA" in code
    assert "GHIDRA_HEADLESS_MISSING" in code
    assert "HAZEWAVE_GHIDRA_AGENT_MCP_SESSION=NOT_PROVEN" in code
    for banned in ("gh codespace create", "sudo ", "git reset", "git push", "hazewave-reflex serve-stop", "curl | sh"):
        assert banned not in code
    assert subprocess.run(["bash","-n",str(path)],capture_output=True,text=True).returncode==0
