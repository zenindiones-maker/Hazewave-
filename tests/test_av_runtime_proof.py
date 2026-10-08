from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "codespaces" / "install-av-research-open-tools.sh"


def test_runtime_smoke_is_explicit_and_never_promotes_by_tool_presence() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "--smoke" in source
    assert '"$VENV/bin/python" -m hazewave.av_runtime_proof' in source
    assert "AV_RESEARCH_FULL_PROFESSIONAL_RUNTIME=NOT_PROVEN" in source
    assert "hazewave-reflex serve-stop" not in source
    assert "gh codespace create" not in source


def test_runtime_proof_refuses_missing_runtime_dependencies(tmp_path: Path) -> None:
    from hazewave.av_runtime_proof import AVRuntimeProofError, run_synthetic_runtime_proof
    def no_tools(name: str) -> None:
        return None
    with pytest.raises(AVRuntimeProofError, match="FFMPEG_MISSING"):
        run_synthetic_runtime_proof(tmp_path / "state", which=no_tools)
    assert not (tmp_path / "state").exists()


def test_runtime_proof_plan_records_unproven_human_and_harness_gates() -> None:
    from hazewave.av_runtime_proof import _receipt_envelope
    r = _receipt_envelope()
    assert r["schema"] == "HazewaveAVSyntheticRuntimeProof/v1"
    assert r["source_type"] == "SYNTHETIC_OWNED_FIXTURE"
    assert r["owner_signed_study"] == "NOT_PROVEN"
    assert r["production_approved"] is False
    assert r["rea6_mcp_connected"] == "NOT_TESTED"
    assert r["stock_health"] == "NOT_TESTED"


def test_runtime_proof_does_not_write_receipt_for_invalid_state_root(tmp_path: Path) -> None:
    from hazewave.av_runtime_proof import AVRuntimeProofError, _persist_receipt
    target = tmp_path / "real"
    target.mkdir()
    alias = tmp_path / "link"
    alias.symlink_to(target, target_is_directory=True)
    with pytest.raises(AVRuntimeProofError, match="STATE_ROOT_SYMLINK"):
        _persist_receipt(_empty_receipt(), alias)


def _empty_receipt() -> dict:
    from hazewave.av_runtime_proof import _receipt_envelope
    return _receipt_envelope()


def test_proof_entrypoint_has_reproducible_bounded_synthetic_media_inputs() -> None:
    from hazewave import av_runtime_proof as p
    import inspect
    s = inspect.getsource(p)
    assert "sine=frequency=440:duration=3" in s
    assert "color=c=red:size=160x90:rate=24:duration=2" in s
    assert "color=c=blue:size=160x90:rate=24:duration=2" in s
    assert "analyze_audio_qc" in s
    assert "analyze_video_qc" in s
    assert "detect_scenes" in s
    assert "analyze_image_metrics" in s
    assert "analyze_editorial_script" in s
