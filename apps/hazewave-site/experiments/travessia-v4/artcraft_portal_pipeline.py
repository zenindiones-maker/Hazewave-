"""Original Hazewave portal FX: real EffectCraft composition, FilmCraft QC.

This is an offline opt-in LAB step. No owner-private images, no credentials,
no calls to a third-party MCP authority, no editing original site art.
Run only in an isolated runner with SHA-verified official CLI releases.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

SCHEMA = "HazewaveRealArtcraftPortalOverlay/v1"
CANVAS = (420, 820)
FRAME_TIMES = tuple(round(i / 8, 3) for i in range(8))
FIRST_PARTY_PROJECT = "zenindiones-maker/Hazewave-"
RELEASE_ARCHIVES = {
    "effectcraft": "71810719903378cdab32a1fe328f23c874d38cd3d833abb19c6263dd2bad218c",
    "filmcraft": "841790ff6649f0d49daa4a8ade1cb18d948e5ca43d00771046663e06c8d8ce83",
}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def require(ok: bool, label: str) -> None:
    if not ok:
        raise ValueError(label)


def hash_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def json_arg(value: dict) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def checked_binary(path: Path, expected_sha: str) -> Path:
    require(re.fullmatch(r"[a-f0-9]{64}", expected_sha) is not None, "BINARY_HASH_INVALID")
    require(path.is_file() and not path.is_symlink(), "BINARY_NOT_REGULAR")
    require(hash_file(path) == expected_sha, "BINARY_SHA_MISMATCH")
    return path.resolve(strict=True)


def run(args: list[str], *, cwd: Path, timeout: int) -> str:
    p = subprocess.run(args, cwd=cwd, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=timeout)
    require(p.returncode == 0,
            "REAL_UPSTREAM_COMMAND_FAILED:" + (p.stderr + " " + p.stdout)[-1400:])
    return p.stdout.strip()


def checked_png(file: Path) -> dict:
    require(file.is_file() and not file.is_symlink(), "EFFECTCRAFT_FRAME_NOT_FOUND")
    data = file.read_bytes()
    require(100 < len(data) < 10_000_000 and data.startswith(PNG_MAGIC), "INVALID_PNG")
    w, h, bits, color, comp, filt, inter = struct.unpack_from(">IIBBBBB", data, 16)
    require((w, h) == CANVAS and bits == 8 and color in (2, 6)
            and comp == filt == inter == 0, "FRAME_FORMAT_OR_CANVAS_MISMATCH")
    return {"sha256": sha256(data).hexdigest(), "bytes": len(data), "width": w,
            "height": h, "alpha_channel": color == 6}


def build(*, output: Path, effect_cli: Path, film_cli: Path,
          effect_sha: str, film_sha: str) -> dict:
    require(not output.exists(), "NEVER_OVERWRITE_WIP")
    checked_binary(effect_cli, effect_sha)
    checked_binary(film_cli, film_sha)
    root = output.resolve(strict=False)
    # No assets or outputs belong in Git; paths must be outside this repository.
    repo = Path(__file__).resolve().parents[4]
    require(not root.is_relative_to(repo), "NO_GENERATED_ART_INSIDE_REPO")
    root.mkdir(parents=True, mode=0o700)
    project = root / "hazewave-original-sonic-portal.ecproj"
    comp = json_arg({"name": "HAZEWAVE_SIGNAL_PORTAL", "width": 420,
                     "height": 820, "frameRate": 8, "duration": 1.0})
    shape = json_arg({"kind": "ellipse", "size": [286, 450],
                      "name": "SONIC_PORTAL_OUTLINE", "stroke": "#e9a4ff",
                      "strokeWidth": 8, "position": [210, 410]})
    def prop(time: float, value: list[int]) -> str:
        return json_arg({"layer": "SONIC_PORTAL_OUTLINE",
                         "path": "transform/scale", "time": time, "value": value})
    command = [
        str(effect_cli), "run", "--empty",
        "comp.new", comp, "layer.newShape", shape,
        "prop.set", json_arg({"layer": "SONIC_PORTAL_OUTLINE",
                             "path": "contents/group/contents/fill/opacity", "value": 0}),
        "prop.addKey", prop(0.0, [10, 10]),
        "prop.addKey", prop(0.5, [100, 100]),
        "prop.addKey", prop(1.0, [150, 150]),
        "--save-as", str(project), "--json"
    ]
    creation = run(command, cwd=root, timeout=75)
    require(project.is_file() and project.stat().st_size > 500, "EFFECTCRAFT_PROJECT_NOT_SAVED")
    frame_root = root / "frames"
    frame_root.mkdir()
    receipts = []
    for idx, time in enumerate(FRAME_TIMES):
        name = f"sonic-portal-{idx:02}.png"
        file = frame_root / name
        run([str(effect_cli), "render-frame", str(project),
             "--time", str(time), "--out", str(file),
             "--transparent", "--json"], cwd=root, timeout=90)
        entry = checked_png(file)
        require(entry["alpha_channel"], "EFFECTCRAFT_ALPHA_REQUIRED_FOR_SITE_OVERLAY")
        entry.update({"file": name, "time": time})
        receipts.append(entry)
    unique = len({f["sha256"] for f in receipts})
    require(unique >= 5, "ACTUAL_FX_HAS_INSUFFICIENT_MOTION")
    video = root / "effectcraft-reference.webm"
    render_text = run(
        [str(effect_cli), "render", str(project), "--out", str(video),
         "--format", "webm", "--start", "0", "--end", "1",
         "--fps", "8", "--audio", "off", "--json"],
        cwd=root, timeout=240)
    require(video.is_file() and 1000 < video.stat().st_size < 40_000_000,
            "EFFECTCRAFT_VIDEO_MISSING")
    # Real FilmCraft executable must successfully decode and describe the
    # same encoded media. This is QA, NOT a claim FilmCraft edited the video.
    film_probe = run([str(film_cli), "probe", str(video)],
                     cwd=root, timeout=90)
    require(len(film_probe) > 15, "FILMCRAFT_PROBE_EMPTY")
    info = json.loads(film_probe)
    video_info = info.get("video")
    require(info.get("container") == "WebM" and isinstance(video_info, dict)
            and (video_info.get("width"), video_info.get("height")) == CANVAS
            and video_info.get("codec") in ("VP9", "AV1")
            and video_info.get("frame_rate") == {"num": 8, "den": 1}
            and isinstance(info.get("duration"), (int, float))
            and 0.85 <= info["duration"] / 254_016_000_000 <= 1.15
            and info.get("audio") is None,
            "FILMCRAFT_PROBED_WRONG_MEDIA")
    # The WebM is only a reference/probe output; the browser must use
    # transparent PNG frames. This video does NOT carry an alpha channel.

    (root / "filmcraft-probe.txt").write_text(film_probe + "\n")
    payload = {
        "schema": SCHEMA, "owner_repository": FIRST_PARTY_PROJECT,
        "art_source": "ORIGINAL_FIRST_PARTY_PROCEDURAL_SHAPE_ONLY",
        "owner_private_media_used": False,
        "authority": "NONE", "production_approved": False,
        "effectcraft_release_sha256": RELEASE_ARCHIVES["effectcraft"],
        "filmcraft_release_sha256": RELEASE_ARCHIVES["filmcraft"],
        "effectcraft_binary_sha256": effect_sha,
        "filmcraft_binary_sha256": film_sha,
        "project_sha256": hash_file(project),
        "filmcraft_probe_executed": True,
        "filmcraft_probe_sha256": sha256(film_probe.encode()).hexdigest(),
        "filmcraft_video_codec": video_info["codec"],
        "filmcraft_verified_frame_rate": video_info["frame_rate"],
        "site_overlay_uses_alpha_png_not_webm": True,
        "effectcraft_video_sha256": hash_file(video),
        "real_effectcraft_render": True,
        "frames": receipts, "distinct_frames": unique,
        "frame_size": [*CANVAS], "duration_seconds": 1,
        "fps": 8,
        "website_production_published": False,
        "owner_visual_approval": "PENDING",
    }
    (root / "effectcraft-filmcraft-proof.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print("HAZEWAVE_EFFECTCRAFT_REAL_RENDER=PASS")
    print("HAZEWAVE_FILMCRAFT_REAL_MEDIA_PROBE=PASS")
    print("HAZEWAVE_EFFECT_FRAMES_UNIQUE=" + str(unique))
    print("HAZEWAVE_PRODUCTION_APPROVED=FALSE")
    return payload


def verify(output: Path) -> dict:
    root = output.resolve(strict=True)
    d = json.loads((root / "effectcraft-filmcraft-proof.json").read_text())
    require(d.get("schema") == SCHEMA and d.get("owner_repository") == FIRST_PARTY_PROJECT,
            "FX_PROVENANCE_MISSING")
    require(d.get("authority") == "NONE" and d.get("production_approved") is False
            and d.get("owner_private_media_used") is False
            and d.get("website_production_published") is False
            and d.get("real_effectcraft_render") is True
            and d.get("filmcraft_probe_executed") is True,
            "UNAUTHORIZED_CLAIMS")
    frames = d.get("frames")
    require(isinstance(frames, list) and len(frames) == len(FRAME_TIMES),
            "FRAME_MANIFEST_MISSING")
    seen = set()
    for i, frame in enumerate(frames):
        require(frame.get("file") == f"sonic-portal-{i:02}.png"
                and frame.get("time") == FRAME_TIMES[i], "FRAME_ORDER_DRIFT")
        checked = checked_png(root / "frames" / frame["file"])
        require(checked["sha256"] == frame["sha256"]
                and checked["bytes"] == frame["bytes"]
                and checked["alpha_channel"] is True, "FRAME_SHA_OR_ALPHA_DRIFT")
        seen.add(frame["sha256"])
    require(len(seen) >= 5, "ACTUAL_FX_HAS_INSUFFICIENT_MOTION")
    require(hash_file(root / "effectcraft-reference.webm")
            == d.get("effectcraft_video_sha256"), "VIDEO_SHA_DRIFT")
    report_text = (root / "filmcraft-probe.txt").read_text().rstrip("\n")
    require(sha256(report_text.encode()).hexdigest() ==
            d.get("filmcraft_probe_sha256") and
            d.get("site_overlay_uses_alpha_png_not_webm") is True,
            "FILMCRAFT_QA_RECEIPT_DRIFT")
    return d


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--effect", type=Path, required=True)
    b.add_argument("--film", type=Path, required=True)
    b.add_argument("--effect-sha", required=True)
    b.add_argument("--film-sha", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        if args.command == "build":
            build(output=args.out, effect_cli=args.effect, film_cli=args.film,
                  effect_sha=args.effect_sha, film_sha=args.film_sha)
        else:
            verify(args.out)
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired,
            subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print("HAZEWAVE_ARTCRAFT_PORTAL=BLOCKED:" + str(exc), file=sys.stderr)
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
