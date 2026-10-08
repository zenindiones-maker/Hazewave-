"""Bounded synthetic audiovisual research runtime proof.

Unlike a regular import doctor, this executes real local FFmpeg audio/video
decodes and first-party Pillow/editorial measurements. It never accesses owner
media, grants, REA, network APIs, production publishing or stock Colibri.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable


class AVRuntimeProofError(RuntimeError):
    pass


def _receipt_envelope() -> dict[str, Any]:
    return {
        "schema": "HazewaveAVSyntheticRuntimeProof/v1",
        "status": "NOT_RUN",
        "source_type": "SYNTHETIC_OWNED_FIXTURE",
        "research_authority": "HAZEWAVE_HARNESS",
        "agent_execution_authority": "NONE",
        "owner_signed_study": "NOT_PROVEN",
        "harness_signed_route": "NOT_TESTED",
        "rea6_mcp_connected": "NOT_TESTED",
        "stock_health": "NOT_TESTED",
        "production_approved": False,
        "artistic_verdict": "NOT_ASSIGNED",
        "tool_versions": {},
        "measurements": {},
        "input_sha256": {},
        "runtime": {},
        "limitations": [
            "Only synthetic fixtures were used; no owner audio, media or license studies.",
            "A synthetic analysis PASS does not attest Codespace identity, MCP connectivity, "
            "owner authorization, subjective fidelity or production approval.",
        ],
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _exec(args: list[str], *, timeout: int = 55) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            check=False,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AVRuntimeProofError("SYNTHETIC_COMMAND_UNAVAILABLE_OR_TIMEOUT") from exc
    if result.returncode != 0:
        raise AVRuntimeProofError("SYNTHETIC_TOOL_NONZERO")
    return result


def _persist_receipt(report: dict[str, Any], state_root: Path) -> Path:
    root = Path(state_root).expanduser()
    if root.is_symlink():
        raise AVRuntimeProofError("STATE_ROOT_SYMLINK")
    path = root / "av-research" / "runtime-proofs"
    if path.parent.is_symlink() or path.is_symlink():
        raise AVRuntimeProofError("STATE_ROOT_SYMLINK")
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    path.chmod(0o700)
    name = "synthetic-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + str(os.getpid()) + ".json"
    final = path / name
    payload = (json.dumps(report, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(final, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    return final


def run_synthetic_runtime_proof(
    state_root: Path,
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> dict[str, Any]:
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        raise AVRuntimeProofError("FFMPEG_MISSING")
    ffprobe = which("ffprobe")
    if not ffprobe:
        raise AVRuntimeProofError("FFPROBE_MISSING")
    from hazewave.audio_qc import analyze_audio_qc
    from hazewave.video_qc import analyze_video_qc
    from hazewave.scene_detection import detect_scenes
    from hazewave.av_research_lab import analyze_image_metrics, analyze_editorial_script

    began = time.monotonic()
    report = _receipt_envelope()
    report["tool_versions"] = {
        "ffmpeg": _exec([ffmpeg, "-version"], timeout=10).stdout.splitlines()[0][:180],
        "ffprobe": _exec([ffprobe, "-version"], timeout=10).stdout.splitlines()[0][:180],
    }
    try:
        with tempfile.TemporaryDirectory(prefix="hazewave-av-owned-fixture-") as work:
            root = Path(work)
            audio = root / "test-audio.wav"
            video = root / "test-video.mp4"
            image = root / "test-image.png"
            script = root / "test-script.json"

            _exec([
                ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-y",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                "-ac", "2", "-ar", "48000", str(audio),
            ])
            _exec([
                ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-y",
                "-f", "lavfi", "-i", "color=c=red:size=160x90:rate=24:duration=2",
                "-f", "lavfi", "-i", "color=c=blue:size=160x90:rate=24:duration=2",
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p",
                "-color_primaries", "bt709", "-color_trc", "bt709",
                "-colorspace", "bt709", "-color_range", "tv",
                "-c:v", "mpeg4", "-q:v", "3", str(video),
            ])
            from PIL import Image
            import PIL
            import importlib.metadata

            Image.new("RGB", (64, 48), (100, 125, 150)).save(image)
            script.write_text(json.dumps({
                "schema": "HazewaveEditorialReference/v1",
                "segments": [
                    {"id": "intro001", "start_seconds": 0, "duration_seconds": 10,
                     "narration": "Primeira imagem animada"},
                    {"id": "scene002", "start_seconds": 10, "duration_seconds": 10,
                     "narration": "Segunda imagem animada"},
                ],
            }), encoding="utf-8")

            a = analyze_audio_qc(audio)
            v = analyze_video_qc(video)
            cuts = detect_scenes(video)
            im = analyze_image_metrics(image)
            editorial = analyze_editorial_script(script)

            if a.sample_rate != 48000 or not 2.9 <= a.duration_seconds <= 3.1:
                raise AVRuntimeProofError("SYNTHETIC_AUDIO_TIMING_INVALID")
            if not math.isfinite(a.integrated_lufs) or not math.isfinite(a.crest_factor_ratio):
                raise AVRuntimeProofError("SYNTHETIC_AUDIO_METRICS_INVALID")
            if v.width != 160 or v.height != 90 or not 3.9 <= v.duration_seconds <= 4.1:
                raise AVRuntimeProofError("SYNTHETIC_VIDEO_TIMING_INVALID")
            if cuts.scene_count < 2 or cuts.source_sha256 != v.output_sha256:
                raise AVRuntimeProofError("SYNTHETIC_SCENE_CUT_NOT_DETECTED")
            if im["width"] != 64 or im["height"] != 48:
                raise AVRuntimeProofError("SYNTHETIC_IMAGE_DECODE_INVALID")
            if editorial["segment_count"] != 2 or editorial["duration_seconds"] != 20:
                raise AVRuntimeProofError("SYNTHETIC_EDITORIAL_TIMELINE_INVALID")

            report["tool_versions"].update({
                "pillow": str(PIL.__version__),
                "scenedetect-headless": importlib.metadata.version("scenedetect-headless"),
                "opentimelineio": importlib.metadata.version("opentimelineio"),
            })
            report["input_sha256"] = {
                "synthetic_wav": _sha256(audio),
                "synthetic_mp4": _sha256(video),
                "synthetic_png": _sha256(image),
                "synthetic_editorial_json": _sha256(script),
            }
            report["measurements"] = {
                "haze_audio_qc": {
                    "status": "PASS",
                    "sample_rate": a.sample_rate,
                    "integrated_lufs": a.integrated_lufs,
                    "true_peak_dbfs": a.true_peak_dbfs,
                    "crest_factor_ratio": a.crest_factor_ratio,
                },
                "wave_video_qc": {
                    "status": "PASS",
                    "width": v.width,
                    "height": v.height,
                    "duration_seconds": v.duration_seconds,
                    "technical_flags": list(v.technical_flags),
                },
                "wave_scene_detection": {
                    "status": "PASS",
                    "scene_count": cuts.scene_count,
                },
                "wave_image_decode": {
                    "status": "PASS",
                    "width": im["width"],
                    "height": im["height"],
                    "mean_luma_8bit": im["mean_luma_8bit"],
                },
                "wave_editorial": {
                    "status": "PASS",
                    "segment_count": editorial["segment_count"],
                    "duration_seconds": editorial["duration_seconds"],
                },
            }
            report["status"] = "PASS:OWNED_SYNTHETIC_FIXTURES"
    except Exception as exc:
        report["status"] = "BLOCKED:SYNTHETIC_RUNTIME_ERROR"
        report["failure_type"] = type(exc).__name__
        report["runtime"]["elapsed_ms"] = round((time.monotonic() - began) * 1000, 1)
        _persist_receipt(report, Path(state_root))
        if isinstance(exc, AVRuntimeProofError):
            raise
        raise AVRuntimeProofError("SYNTHETIC_ANALYZER_FAILED:" + type(exc).__name__) from exc

    report["runtime"].update({
        "elapsed_ms": round((time.monotonic() - began) * 1000, 1),
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "free_disk_bytes": shutil.disk_usage(Path(state_root).expanduser().parent if
                                            Path(state_root).expanduser().parent.is_dir() else Path.home()).free,
        "codespace_env_identity": os.environ.get("CODESPACE_NAME") or "UNSPECIFIED",
        "host_identity_attestation": "NOT_PERFORMED",
    })
    receipt = _persist_receipt(report, Path(state_root))
    report["receipt_path"] = str(receipt)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prove bounded real-media analysis on owned synthetic fixtures")
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".local" / "state" / "hazewave")
    args = parser.parse_args(argv)
    try:
        report = run_synthetic_runtime_proof(args.state_root)
    except AVRuntimeProofError as exc:
        print("AV_RESEARCH_SYNTHETIC_RUNTIME=BLOCKED:" + str(exc), file=sys.stderr)
        return 20
    print("AV_RESEARCH_SYNTHETIC_RUNTIME=PASS")
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
