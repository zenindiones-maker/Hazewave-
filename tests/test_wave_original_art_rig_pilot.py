"""CI contracts never invent artwork availability or final rig approval."""
from __future__ import annotations

from pathlib import Path
import json
import runpy
import subprocess
import sys
from hashlib import sha256

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXTRACT = ROOT / "scripts/creative/wave_original_art_rig_pilot.py"
PREVIEW = ROOT / "scripts/creative/wave_original_art_rig_preview.py"


def _load(path: Path) -> dict:
    return runpy.run_path(str(path), run_name="test_import_no_execution")


def _parts() -> list[dict]:
    return [
        {"id": ident, "path": ident + ".png",
         "x": 250, "y": 320, "width": 100, "height": 40}
        for ident in (
            *(f"p{r}{c}" for r in range(3) for c in range(3)),
            "encoder_right",
        )
    ]


def test_original_art_is_sha_pinned_and_not_in_repository():
    module = _load(EXTRACT)
    assert module["SOURCE_SHA"] == "460eaf43069e608fc959ca95dd7431330e98ace110752640145d5d711cb8be96"
    assert module["FOG_SHA"] == "bc38da43aa8d21100ec116c7247a1613e75b6168e91d656f4be0b7b299320b51"
    assert module["SHAPE"] == (1448, 1086)
    assert "cv2" not in sys.modules or module["masks_for_shape"]
    assert "https://" not in EXTRACT.read_text()
    assert not (ROOT / "apps/hazewave-site/public/media/owner-rig").exists()


def test_first_party_originals_cannot_be_guessed(tmp_path):
    p = tmp_path / "unapproved.png"
    p.write_bytes(b"fakepng")
    module = _load(EXTRACT)
    assert module["hash_file"](p) == sha256(b"fakepng").hexdigest()
    # No source/art bytes are shipped within the GitHub PR.
    assert not (ROOT / "tests/fixtures/owner-private-controller.png").exists()


def test_offline_preview_generates_real_independent_animation_state(tmp_path):
    root = tmp_path / "private-pilot"
    root.mkdir()
    ledger = {
        "schema": "HazewaveWaveRigPilot/v1",
        "production_approved": False,
        "individual_art_pieces": 10,
        "pieces": _parts(),
    }
    (root / "pilot-manifest.json").write_text(json.dumps(ledger), encoding="utf-8")
    dest = _load(PREVIEW)["build_preview"](root)
    content = dest.read_text(encoding="utf-8")
    for name in [f"p{r}{c}" for r in range(3) for c in range(3)] + ["encoder_right"]:
        assert f'id="{name}"' in content
    assert "strokeDashoffset" in content
    assert "getTotalLength()" in content
    assert "getPointAtLength" in content
    assert "activePads" in content
    assert 'production_approved' not in content
    assert "https://" not in content
    assert 'controller-cleanplate-EXPERIMENTAL.png' in content


def test_preview_denies_privileged_or_repeated_state(tmp_path):
    root = tmp_path / "working"
    root.mkdir()
    data = {
        "schema": "HazewaveWaveRigPilot/v1",
        "production_approved": False,
        "individual_art_pieces": 10,
        "pieces": _parts(),
    }
    manifest = root / "pilot-manifest.json"
    manifest.write_text(json.dumps(data))
    build = _load(PREVIEW)["build_preview"]
    build(root)
    with pytest.raises(ValueError, match="PREVIEW_EXISTS_WIP_PRESERVED"):
        build(root)
    data["production_approved"] = True
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="PILOT_SCOPE_DENIED"):
        build(root)


def test_offhost_cli_fails_closed_without_owner_art(tmp_path):
    target = tmp_path / "unexpected"
    process = subprocess.run([
        sys.executable, str(EXTRACT),
        "--source", str(tmp_path / "nonexistent-controller.png"),
        "--fog", str(tmp_path / "nonexistent-fog.png"),
        "--output", str(target),
    ], capture_output=True, text=True, timeout=15)
    assert process.returncode != 0
    assert "WAVE_RIG_PILOT=BLOCKED:" in process.stderr
    assert not target.exists()


def test_no_automatic_install_publish_or_live_agent_registration():
    raw = EXTRACT.read_text() + PREVIEW.read_text()
    for banned in (
        "npm install", "pip install", "apt install", "gh codespace create",
        "git push", "git reset --hard", "codex mcp add",
        "hazewave-reflex serve-stop", "production_approved\": True",
    ):
        assert banned not in raw
