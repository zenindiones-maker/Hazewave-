"""Adversarial, first-party fixture-only WAVE scroll evidence tests."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import struct
import zlib

import pytest

from hazewave.wave_scroll_evidence import ScrollResearchError, verify_owned_scroll_capture

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "wave-scroll-owned.html"
APP_SCRIPT = FIXTURE.parent / "wave-scroll-js-owned" / "main.js"
POSITIONS = (0.0, 0.15, 0.4, 0.7, 0.95, 1.0, 0.4, 0.0)
REPO_SHA = "a" * 40


def _chunk(marker: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + marker + payload + struct.pack(
        ">I", zlib.crc32(marker + payload) & 0xffffffff
    )


def _png_rgb(color: int) -> bytes:
    # Real, decodable RGB PNG; no browser asserted by these unit tests.
    width, height = 393, 852
    scan = (b"\x00" + bytes((color, 30, 65)) * width) * height
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(scan))
            + _chunk(b"IEND", b""))


def _report(root: Path) -> dict:
    root.mkdir(exist_ok=True, parents=True)
    samples = []
    for i, progress in enumerate(POSITIONS):
        # Same physical pose must restore byte-identical frame on reversal.
        color = 20 + round(progress * 100)
        path = root / f"{i:02d}.png"
        image = _png_rgb(color)
        path.write_bytes(image)
        samples.append({
            "target": progress,
            "progress": progress,
            "stroke_reveal": min(1.0, progress / 0.4),
            "pad_active": progress >= 0.3,
            "rig_translate_x": round(progress * 32, 3),
            "camera_translate_x": round(-progress * 68, 3),
            "frame_name": path.name,
            "frame_sha256": sha256(image).hexdigest(),
        })
    return {
        "schema": "HazewaveOwnedScrollBrowserCapture/v1",
        "fixture_scope": "LOCAL_FIRST_PARTY_ONLY",
        "fixture_sha256": sha256(FIXTURE.read_bytes()).hexdigest(),
        "app_source_sha256": sha256(APP_SCRIPT.read_bytes()).hexdigest(),
        "browser": "chromium",
        "browser_version": "test-fixture-only",
        "viewport": {"width": 393, "height": 852},
        "samples": samples,
        "network_request_count": 0,
        "external_sites_analyzed": False,
    }


def test_reproduced_scroll_reversibility_is_bounded_not_production_ready(tmp_path):
    capture = _report(tmp_path)
    result = verify_owned_scroll_capture(capture, capture_root=tmp_path, repo_sha=REPO_SHA)
    assert result["scope"] == "OWNED_FIXTURE_ONLY"
    assert result["status"] == "BOUNDED_REPRODUCED_BEHAVIOR"
    assert result["harness_authority"] == "HAZEWAVE_HARNESS"
    assert result["capability"] == "web.visual_regression"
    assert result["verified_frames"] == 8
    assert result["codespace_runtime_proven"] is False
    assert result["agent_mcp_connected"] is False
    assert result["rea6_used_in_this_probe"] is False
    assert result["production_approved"] is False


@pytest.mark.parametrize("field,value", [
    ("fixture_scope", "EXTERNAL_WEB"),
    ("browser", "firefox"),
    ("external_sites_analyzed", True),
    ("network_request_count", 1),
])
def test_refuses_unauthorized_scope_and_network(tmp_path, field, value):
    capture = _report(tmp_path)
    capture[field] = value
    with pytest.raises(ScrollResearchError):
        verify_owned_scroll_capture(capture, capture_root=tmp_path, repo_sha=REPO_SHA)


def test_refuses_fabricated_visual_hash(tmp_path):
    capture = _report(tmp_path)
    capture["samples"][2]["frame_sha256"] = "b" * 64
    with pytest.raises(ScrollResearchError, match="FRAME_DIGEST_MISMATCH"):
        verify_owned_scroll_capture(capture, capture_root=tmp_path, repo_sha=REPO_SHA)


def test_refuses_missing_stroke_activation(tmp_path):
    capture = _report(tmp_path)
    capture["samples"][1]["stroke_reveal"] = 0.0
    with pytest.raises(ScrollResearchError, match="STROKE_NOT_GROWING"):
        verify_owned_scroll_capture(capture, capture_root=tmp_path, repo_sha=REPO_SHA)


def test_refuses_fake_reversibility(tmp_path):
    capture = _report(tmp_path)
    capture["samples"][-1]["pad_active"] = True
    with pytest.raises(ScrollResearchError, match="REVERSAL_MISMATCH"):
        verify_owned_scroll_capture(capture, capture_root=tmp_path, repo_sha=REPO_SHA)


def test_refuses_camera_only_without_machine_motion(tmp_path):
    capture = _report(tmp_path)
    for sample in capture["samples"]:
        sample["rig_translate_x"] = 0.0
    with pytest.raises(ScrollResearchError, match="RIG_MOTION_NOT_PROVEN"):
        verify_owned_scroll_capture(capture, capture_root=tmp_path, repo_sha=REPO_SHA)


def test_refuses_path_escape_even_with_valid_digest(tmp_path):
    capture = _report(tmp_path)
    capture["samples"][0]["frame_name"] = "../secret.png"
    with pytest.raises(ScrollResearchError, match="FRAME_PATH_INVALID"):
        verify_owned_scroll_capture(capture, capture_root=tmp_path, repo_sha=REPO_SHA)


def test_refuses_wrong_source_and_sha(tmp_path):
    capture = _report(tmp_path)
    capture["fixture_sha256"] = "c" * 64
    with pytest.raises(ScrollResearchError, match="SOURCE_DIGEST_MISMATCH"):
        verify_owned_scroll_capture(capture, capture_root=tmp_path, repo_sha=REPO_SHA)
    capture = _report(tmp_path)
    with pytest.raises(ScrollResearchError, match="REPO_SHA_INVALID"):
        verify_owned_scroll_capture(capture, capture_root=tmp_path, repo_sha="not-a-sha")


def test_refuses_static_analysis_source_mismatch(tmp_path):
    capture = _report(tmp_path)
    capture["app_source_sha256"] = "d" * 64
    with pytest.raises(ScrollResearchError, match="APP_SOURCE_DIGEST_MISMATCH"):
        verify_owned_scroll_capture(capture, capture_root=tmp_path, repo_sha=REPO_SHA)


def test_refuses_merely_repeated_poster_frames(tmp_path):
    capture = _report(tmp_path)
    original = (tmp_path / "00.png").read_bytes()
    for index, sample in enumerate(capture["samples"]):
        (tmp_path / f"{index:02d}.png").write_bytes(original)
        sample["frame_sha256"] = sha256(original).hexdigest()
    with pytest.raises(ScrollResearchError, match="NO_VISIBLE_FRAME_CHANGE"):
        verify_owned_scroll_capture(capture, capture_root=tmp_path, repo_sha=REPO_SHA)


def test_refuses_duplicate_json_keys_in_cli_input(tmp_path):
    # A parser must not silently select either interpretation of a duplicated
    # scope field. Tested against the public loader as well.
    from hazewave.wave_scroll_evidence import load_capture_json
    source = tmp_path / "bad.json"
    source.write_text('{"fixture_scope":"LOCAL_FIRST_PARTY_ONLY","fixture_scope":"EXTERNAL_WEB"}')
    with pytest.raises(ScrollResearchError, match="JSON_INVALID"):
        load_capture_json(source)
