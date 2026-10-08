from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hazewave.reflex_research import audit_derived_engines, discover_tools


UPSTREAM = "bf2442915d6e3dd4cdfd2eb9c2a3d2aa44a25850"
VARIANTS = ("direct_y_store_v1", "mc_144_v2", "mc_408_v2", "mc_816_v2")


def _fixture(derived_root: Path, stock: Path) -> None:
    stock.parent.mkdir(parents=True)
    stock.write_bytes(b"stock-laya")
    stock.chmod(0o755)
    for variant in VARIANTS:
        root = derived_root / variant
        binary = root / "c" / "laya"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(("distinct-" + variant).encode())
        binary.chmod(0o755)
        metadata = {
            "schema": "HazewaveReflexDerivedEngineBuild/v1",
            "variant": variant,
            "upstream_commit": UPSTREAM,
            "patch_sha256": "a" * 64,
            "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "changes_model_or_precision": False,
            "preserves_k_accumulation_order": True,
            "requires_exact_output_gate": True,
            "provider_authority": "NONE",
        }
        if variant.startswith("mc_"):
            metadata["qi_mc"] = int(variant.split("_")[1])
            metadata["cache_block_mc_only"] = True
        else:
            metadata["direct_y_store_only"] = True
            metadata["full_tile_only"] = True
        (root / "build.json").write_text(json.dumps(metadata), encoding="utf-8")


def _audit(tmp_path: Path) -> dict:
    return audit_derived_engines(
        stock_binary=tmp_path / "source" / "c" / "laya",
        derived_root=tmp_path / "derived",
        upstream_commit=UPSTREAM,
    )


def test_clean_distinct_derived_artifacts_pass_without_activation(tmp_path: Path) -> None:
    _fixture(tmp_path / "derived", tmp_path / "source" / "c" / "laya")
    report = _audit(tmp_path)
    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert [row["variant"] for row in report["artifacts"]] == list(VARIANTS)
    assert len({row["binary_sha256"] for row in report["artifacts"]}) == 4
    assert report["provider_authority"] == "NONE"
    assert report["activation"] == "FORBIDDEN"


def test_mc_variant_must_match_its_exact_metadata(tmp_path: Path) -> None:
    _fixture(tmp_path / "derived", tmp_path / "source" / "c" / "laya")
    meta = tmp_path / "derived" / "mc_408_v2" / "build.json"
    row = json.loads(meta.read_text())
    row["qi_mc"] = 144
    meta.write_text(json.dumps(row))
    report = _audit(tmp_path)
    assert report["status"] == "BLOCKED"
    assert "RE_MC_METADATA_MISMATCH:mc_408_v2" in report["errors"]


def test_duplicate_mc_binaries_are_blocked_even_with_valid_metadata(tmp_path: Path) -> None:
    _fixture(tmp_path / "derived", tmp_path / "source" / "c" / "laya")
    first = tmp_path / "derived" / "mc_144_v2" / "c" / "laya"
    duplicate = tmp_path / "derived" / "mc_816_v2" / "c" / "laya"
    duplicate.write_bytes(first.read_bytes())
    meta = tmp_path / "derived" / "mc_816_v2" / "build.json"
    row = json.loads(meta.read_text())
    row["binary_sha256"] = hashlib.sha256(duplicate.read_bytes()).hexdigest()
    meta.write_text(json.dumps(row))
    report = _audit(tmp_path)
    assert report["status"] == "BLOCKED"
    assert any(error.startswith("RE_DUPLICATE_BINARY:") for error in report["errors"])


def test_binary_tampering_is_blocked(tmp_path: Path) -> None:
    _fixture(tmp_path / "derived", tmp_path / "source" / "c" / "laya")
    (tmp_path / "derived" / "direct_y_store_v1" / "c" / "laya").write_bytes(b"modified")
    report = _audit(tmp_path)
    assert "RE_BINARY_SHA_MISMATCH:direct_y_store_v1" in report["errors"]


def test_symlink_binary_is_not_followed(tmp_path: Path) -> None:
    _fixture(tmp_path / "derived", tmp_path / "source" / "c" / "laya")
    binary = tmp_path / "derived" / "mc_144_v2" / "c" / "laya"
    binary.unlink()
    binary.symlink_to(tmp_path / "source" / "c" / "laya")
    report = _audit(tmp_path)
    assert "RE_SYMLINK_FORBIDDEN:mc_144_v2" in report["errors"]


def test_missing_artifact_fails_closed(tmp_path: Path) -> None:
    _fixture(tmp_path / "derived", tmp_path / "source" / "c" / "laya")
    (tmp_path / "derived" / "mc_408_v2" / "build.json").unlink()
    report = _audit(tmp_path)
    assert "RE_METADATA_MISSING:mc_408_v2" in report["errors"]


def test_wrong_upstream_is_rejected(tmp_path: Path) -> None:
    _fixture(tmp_path / "derived", tmp_path / "source" / "c" / "laya")
    report = audit_derived_engines(
        stock_binary=tmp_path / "source" / "c" / "laya",
        derived_root=tmp_path / "derived",
        upstream_commit="b" * 40,
    )
    assert report["status"] == "BLOCKED"
    assert "RE_UPSTREAM_SHA_MISMATCH" in report["errors"]


def test_tool_inventory_is_read_only_and_has_no_install_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    import hazewave.reflex_research as research

    monkeypatch.setattr(research.shutil, "which", lambda tool: "/usr/bin/readelf" if tool == "readelf" else None)
    tools = discover_tools()
    assert tools["readelf"] == "AVAILABLE"
    assert tools["perf"] == "NOT_INSTALLED"
    assert tools["ghidra"] == "NOT_INSTALLED"


def test_reflex_control_plane_exposes_read_only_audit_without_runtime_restart() -> None:
    root = Path(__file__).resolve().parents[1]
    remote = (root / "scripts" / "codespaces" / "reflex-shadow-control.sh").read_text(encoding="utf-8")
    termux = (root / "scripts" / "hazewave_reflex_termux_control.sh").read_text(encoding="utf-8")
    assert "engine-re-doctor) reflex_research_doctor ;;" in remote
    assert "engine-re-doctor" in termux
    block = remote.split("reflex_research_doctor() {", 1)[1].split("\nlatency_engine_tune() {", 1)[0]
    assert "ensure_checkout" in block
    assert "--stock-binary" in block
    assert "--derived-root" in block
    assert "--state-root" in block
    assert "latency_engine_tune" not in block
    assert "reconcile" not in block
    assert "serve-stop" not in block
