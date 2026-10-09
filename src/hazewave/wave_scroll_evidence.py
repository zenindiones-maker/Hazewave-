"""Bounded WAVE scroll forensics over one immutable, first-party browser fixture.

Consumes *real capture files*, not claimed visual states alone. This is not a
third-party site crawler, REA provider, host attestation or production gate.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import struct
from typing import Any
import zlib

from hazewave.harness import HazewaveTask, issue_authorization, route_task, validate_authorization

_FIXTURE = Path(__file__).resolve().parents[2] / "tests/fixtures/wave-scroll-owned.html"
_APP_SCRIPT = _FIXTURE.parent / "wave-scroll-js-owned" / "main.js"
_POSITIONS = (0.0, 0.15, 0.4, 0.7, 0.95, 1.0, 0.4, 0.0)
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SHA40 = re.compile(r"^[a-f0-9]{40}$")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ALLOWED_VIEWPORTS = {(393, 852), (360, 800), (1280, 720)}


class ScrollResearchError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ScrollResearchError(code)


def _number(value: Any, code: str) -> float:
    _require(type(value) in (float, int) and math.isfinite(value), code)
    return float(value)


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate-key")
        output[key] = value
    return output


def load_capture_json(path: Path) -> dict[str, Any]:
    try:
        f = Path(path)
        _require(f.is_file() and not f.is_symlink() and f.stat().st_size <= 256_000,
                 "JSON_INVALID")
        parsed = json.loads(f.read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs)
        _require(isinstance(parsed, dict), "JSON_INVALID")
        return parsed
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ScrollResearchError("JSON_INVALID") from exc


def _png_pixels(path: Path, *, width: int, height: int) -> tuple[str, str]:
    # A PNG SHA alone could differ only due to metadata. Decode its RGB pixels
    # to establish a separate image-content digest, with strict memory limits.
    _require(path.is_file() and not path.is_symlink() and 100 < path.stat().st_size <= 12_000_000,
             "FRAME_FILE_INVALID")
    content = path.read_bytes()
    _require(content.startswith(_PNG_SIGNATURE), "FRAME_PNG_INVALID")
    offset = len(_PNG_SIGNATURE)
    idat: list[bytes] = []
    bpp = 0
    saw_ihdr = False
    ended = False
    while offset + 12 <= len(content):
        n = struct.unpack_from(">I", content, offset)[0]
        offset += 4
        _require(n <= 10_000_000 and offset + n + 8 <= len(content), "FRAME_PNG_INVALID")
        marker = content[offset:offset + 4]
        offset += 4
        payload = content[offset:offset + n]
        offset += n
        crc = struct.unpack_from(">I", content, offset)[0]
        offset += 4
        _require(zlib.crc32(marker + payload) & 0xffffffff == crc, "FRAME_PNG_CRC_INVALID")
        if marker == b"IHDR":
            _require(not saw_ihdr and n == 13, "FRAME_PNG_INVALID")
            w, h, depth, col, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            _require((w, h) == (width, height), "FRAME_DIMENSIONS_MISMATCH")
            _require(depth == 8 and col in (2, 6) and compression == 0
                     and filtering == 0 and interlace == 0, "FRAME_PNG_FORMAT_UNSUPPORTED")
            bpp = 3 if col == 2 else 4
            saw_ihdr = True
        elif marker == b"IDAT":
            _require(saw_ihdr, "FRAME_PNG_INVALID")
            idat.append(payload)
        elif marker == b"IEND":
            _require(n == 0 and saw_ihdr and bool(idat), "FRAME_PNG_INVALID")
            ended = True
            break
    _require(ended and offset == len(content), "FRAME_PNG_INVALID")
    row_len = width * bpp
    raw_limit = (row_len + 1) * height
    _require(raw_limit < 7_000_000, "FRAME_PNG_TOO_LARGE")
    try:
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(b"".join(idat), raw_limit + 1)
        _require(len(raw) == raw_limit and decompressor.eof and not decompressor.unused_data,
                 "FRAME_PNG_INVALID")
    except zlib.error as exc:
        raise ScrollResearchError("FRAME_PNG_INVALID") from exc
    previous = bytearray(row_len)
    pixel_hash = sha256()
    for y in range(height):
        idx = y * (row_len + 1)
        kind = raw[idx]
        _require(kind <= 4, "FRAME_PNG_FILTER_INVALID")
        line = bytearray(raw[idx + 1:idx + 1 + row_len])
        for j in range(row_len):
            left = line[j - bpp] if j >= bpp else 0
            up = previous[j]
            upper_left = previous[j - bpp] if j >= bpp else 0
            if kind == 1:
                line[j] = (line[j] + left) & 255
            elif kind == 2:
                line[j] = (line[j] + up) & 255
            elif kind == 3:
                line[j] = (line[j] + (left + up) // 2) & 255
            elif kind == 4:
                p = left + up - upper_left
                a, b, c = abs(p - left), abs(p - up), abs(p - upper_left)
                pred = left if a <= b and a <= c else up if b <= c else upper_left
                line[j] = (line[j] + pred) & 255
        pixel_hash.update(line)
        previous = line
    return sha256(content).hexdigest(), pixel_hash.hexdigest()


def verify_owned_scroll_capture(
    capture: Mapping[str, Any], *, capture_root: Path, repo_sha: str,
) -> dict[str, Any]:
    _require(isinstance(repo_sha, str) and bool(_SHA40.fullmatch(repo_sha)), "REPO_SHA_INVALID")
    _require(isinstance(capture, Mapping), "CAPTURE_INVALID")
    required = {"schema", "fixture_scope", "fixture_sha256", "app_source_sha256", "browser", "browser_version",
                "viewport", "samples", "network_request_count", "external_sites_analyzed"}
    _require(set(capture) == required, "CAPTURE_FIELDS_INVALID")
    _require(capture["schema"] == "HazewaveOwnedScrollBrowserCapture/v1",
             "CAPTURE_SCHEMA_INVALID")
    _require(capture["fixture_scope"] == "LOCAL_FIRST_PARTY_ONLY"
             and capture["browser"] == "chromium"
             and capture["external_sites_analyzed"] is False
             and type(capture["network_request_count"]) is int
             and capture["network_request_count"] == 0, "EXTERNAL_RESEARCH_FORBIDDEN")
    _require(isinstance(capture["browser_version"], str)
             and 1 <= len(capture["browser_version"]) <= 100,
             "BROWSER_VERSION_INVALID")
    _require(not _FIXTURE.is_symlink() and _FIXTURE.is_file()
             and capture["fixture_sha256"] == sha256(_FIXTURE.read_bytes()).hexdigest(),
             "SOURCE_DIGEST_MISMATCH")
    _require(_APP_SCRIPT.is_file() and not _APP_SCRIPT.is_symlink()
             and capture["app_source_sha256"] == sha256(_APP_SCRIPT.read_bytes()).hexdigest(),
             "APP_SOURCE_DIGEST_MISMATCH")
    viewport = capture["viewport"]
    _require(isinstance(viewport, Mapping) and set(viewport) == {"width", "height"}
             and type(viewport["width"]) is int and type(viewport["height"]) is int
             and (viewport["width"], viewport["height"]) in _ALLOWED_VIEWPORTS,
             "VIEWPORT_INVALID")
    root = Path(capture_root)
    repo_root = Path(__file__).resolve().parents[2]
    _require(root.is_dir() and not root.is_symlink() and
             not root.resolve().is_relative_to(repo_root), "CAPTURE_ROOT_UNSAFE")
    samples = capture["samples"]
    _require(isinstance(samples, list) and len(samples) == len(_POSITIONS),
             "SAMPLE_COUNT_INVALID")
    checked: list[dict[str, Any]] = []
    pixel_hashes: list[str] = []
    for index, (target, sample) in enumerate(zip(_POSITIONS, samples)):
        _require(isinstance(sample, Mapping) and set(sample) == {
            "target", "progress", "stroke_reveal", "pad_active",
            "rig_translate_x", "camera_translate_x", "frame_name", "frame_sha256",
        }, "SAMPLE_FIELDS_INVALID")
        _require(abs(_number(sample["target"], "TARGET_INVALID") - target) <= 0.000001
                 and abs(_number(sample["progress"], "PROGRESS_INVALID") - target) <= 0.015,
                 "SCROLL_POSITION_INVALID")
        ratio = _number(sample["stroke_reveal"], "STROKE_RATIO_INVALID")
        _require(-0.005 <= ratio <= 1.005, "STROKE_RATIO_INVALID")
        _require(type(sample["pad_active"]) is bool, "PAD_STATE_INVALID")
        _number(sample["rig_translate_x"], "RIG_POSITION_INVALID")
        _number(sample["camera_translate_x"], "CAMERA_POSITION_INVALID")
        _require(sample["frame_name"] == f"{index:02d}.png", "FRAME_PATH_INVALID")
        _require(isinstance(sample["frame_sha256"], str)
                 and bool(_SHA256.fullmatch(sample["frame_sha256"])), "FRAME_DIGEST_INVALID")
        actual_sha, pixel_sha = _png_pixels(root / sample["frame_name"],
                                           width=viewport["width"], height=viewport["height"])
        _require(actual_sha == sample["frame_sha256"], "FRAME_DIGEST_MISMATCH")
        pixel_hashes.append(pixel_sha)
        checked.append(dict(sample))

    first, stroke, pad, near, hub, end, reverse, reset = checked
    _require(first["stroke_reveal"] <= 0.01
             and 0.25 <= stroke["stroke_reveal"] <= 0.5
             and pad["stroke_reveal"] >= 0.98
             and hub["stroke_reveal"] >= 0.98, "STROKE_NOT_GROWING")
    _require(not first["pad_active"] and not stroke["pad_active"]
             and all(x["pad_active"] for x in (pad, near, hub, end, reverse)),
             "PAD_CAUSAL_ORDER_INVALID")
    _require(near["rig_translate_x"] - first["rig_translate_x"] >= 15
             and end["rig_translate_x"] - near["rig_translate_x"] >= 5,
             "RIG_MOTION_NOT_PROVEN")
    _require(abs(near["camera_translate_x"] - first["camera_translate_x"]) >= 25,
             "CAMERA_PAN_NOT_PROVEN")
    for field in ("stroke_reveal", "rig_translate_x", "camera_translate_x"):
        _require(abs(float(pad[field]) - float(reverse[field])) <= 0.005
                 and abs(float(first[field]) - float(reset[field])) <= 0.005,
                 "REVERSAL_MISMATCH")
    _require(reverse["pad_active"] == pad["pad_active"] and
             reset["pad_active"] == first["pad_active"],
             "REVERSAL_MISMATCH")
    _require(pixel_hashes[0] == pixel_hashes[7] and pixel_hashes[2] == pixel_hashes[6],
             "REVERSAL_VISUAL_MISMATCH")
    _require(len({pixel_hashes[i] for i in (0, 1, 2, 3, 5)}) >= 4,
             "NO_VISIBLE_FRAME_CHANGE")

    task = HazewaveTask("wave-owned-scroll-fixture", "Verify causal illustrated scroll fixture",
                        "web.visual_regression", "WAVE")
    auth = validate_authorization(issue_authorization(route_task(task)),
                                  expected_task_id=task.task_id,
                                  expected_capability=task.required_capability)
    return {
        "schema": "HazewaveOwnedScrollResearchEvidence/v1",
        "status": "BOUNDED_REPRODUCED_BEHAVIOR",
        "scope": "OWNED_FIXTURE_ONLY",
        "harness_authority": auth.authority,
        "harness_authorization_id": auth.authorization_id,
        "domain": "WAVE",
        "capability": task.required_capability,
        "repo_sha_claimed_by_caller": repo_sha,
        "source_sha256": capture["fixture_sha256"],
        "app_source_sha256": capture["app_source_sha256"],
        "browser": "chromium",
        "viewport": dict(viewport),
        "verified_frames": len(checked),
        "png_sha256": [item["frame_sha256"] for item in checked],
        "pixel_sha256": pixel_hashes,
        "external_sites_analyzed": False,
        "rea6_used_in_this_probe": False,
        "browser_runtime_approved": False,
        "codespace_runtime_proven": False,
        "agent_mcp_connected": False,
        "production_approved": False,
        "limitations": [
            "Only a repository-authored SVG/scroll fixture was reproduced.",
            "PNG/frame and DOM values are linked, but browser process/host identity is not independently attested.",
            "No third-party website observed; no REA6 static or native inference in this probe.",
            "No human approval, provider readiness promotion or production publication.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate real first-party WAVE scroll screenshot evidence")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--repo-sha", required=True)
    args = parser.parse_args()
    try:
        result = verify_owned_scroll_capture(load_capture_json(args.input),
                                             capture_root=args.capture_root, repo_sha=args.repo_sha)
    except (OSError, ScrollResearchError) as exc:
        print(f"WAVE_SCROLL_EVIDENCE=BLOCKED:{exc}")
        return 20
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print("WAVE_SCROLL_OWNED_BROWSER_EVIDENCE=PASS")
    print("WAVE_EXTERNAL_SITES=NOT_TESTED")
    print("WAVE_OWNER_CODESPACE=NOT_TESTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
