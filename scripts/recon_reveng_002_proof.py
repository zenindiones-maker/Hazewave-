"""Create and verify native inspector CI receipts, then render an honest evidence replay.

The video is NOT a live terminal capture. It replays deterministic CI output.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys

from hazewave.harness import HazewaveTask, issue_authorization, route_task
from hazewave.re_inspectors import run_inspection


TARGETS = (
    ("binary_header_inspector", "python.elf", "HAZE"),
    ("media_container_deep_parser", "unknown-sample.mp4", "WAVE"),
    ("codec_stream_analyzer", "tone.wav", "HAZE"),
    ("streaming_manifest_parser", "playlist.m3u8", "WAVE"),
    ("protection_detector", "playlist.m3u8", "WAVE"),
)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def build_evidence(directory: Path) -> list[dict]:
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(sys.executable).resolve(), directory / "python.elf")
    playlist = directory / "playlist.m3u8"
    playlist.write_text(
        '#EXTM3U\n#EXT-X-VERSION:3\n'
        '#EXT-X-KEY:METHOD=AES-128,URI="unused-protected-key.bin"\n'
        '#EXTINF:2.0,\nsegment.ts\n', encoding="utf-8"
    )
    ledger = []
    for capability, filename, domain in TARGETS:
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"PROOF_INPUT_MISSING:{path}")
        task_id = f"recon-reveng-002-ci-{capability}"
        a = issue_authorization(route_task(HazewaveTask(
            task_id=task_id, goal="Produce bounded CI inspection evidence",
            required_capability=capability, requested_domain=domain,
        )))
        output = run_inspection(capability, path, task_id=task_id, authorization=a)
        receipt, result = output["receipt"], output["result"]
        if receipt["source_sha256"] != sha256(path.read_bytes()).hexdigest():
            raise AssertionError("INPUT_RECEIPT_SHA_MISMATCH")
        if receipt["result_sha256"] != sha256(canonical(result)).hexdigest():
            raise AssertionError("RESULT_RECEIPT_SHA_MISMATCH")
        if receipt["status"] != "EXECUTED_READ_ONLY":
            raise AssertionError("EXECUTION_RECEIPT_NOT_REAL")
        proof = {
            "schema": "HazewaveREVerifiedProof/v1",
            "capability": capability,
            "file": filename,
            "source": "GitHubActions-controlled executable/media fixtures",
            "runner_head_sha": os.environ.get("GITHUB_SHA", "UNKNOWN"),
            "runner_run_id": os.environ.get("GITHUB_RUN_ID", "UNKNOWN"),
            "receipt": receipt,
            "result": result,
        }
        (directory / f"{capability}.json").write_text(
            json.dumps(proof, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        ledger.append(proof)
    media = next(x for x in ledger if x["capability"] == "media_container_deep_parser")
    boxes = media["result"]["boxes"]
    if boxes[0]["offset"] != 0 or boxes[-1]["end"] != media["result"]["file_size"]:
        raise AssertionError("MP4_TOP_LEVEL_BYTES_NOT_MAPPED")
    for prev, nxt in zip(boxes, boxes[1:]):
        if prev["end"] != nxt["offset"]:
            raise AssertionError("MP4_STRUCTURAL_BYTES_GAP")
    (directory / "RE_EXECUTION_LEDGER.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in ledger),
        encoding="utf-8"
    )
    return ledger


def create_video(directory: Path, ledger: list[dict]) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        raise RuntimeError("PILLOW_REQUIRED_FOR_PROOF_VIDEO") from e

    boxes = next(x["result"]["boxes"] for x in ledger
                 if x["capability"] == "media_container_deep_parser")
    receipts = [x["receipt"] for x in ledger]
    sha = ledger[0]["runner_head_sha"][:12]
    scenes = [
        ["RECON-REVENG-002", "REAL GITHUB ACTIONS INPUTS",
         "Five native inspectors; read-only; Harness receipts",
         f"Commit {sha}", f"Run {ledger[0]['runner_run_id']}"],
        ["INPUT FILE: unknown-sample.mp4", "Public CI-generated sample (not untrusted)",
         "Format: ISO BMFF", "Full top-level byte coverage validated",
         f"Size: {sum(b['size'] for b in boxes)} bytes"],
        ["STRUCTURAL BYTE MAP: ISO BMFF"] + [
            f"{b['offset']:>10} - {b['end']:<10} | {b['type']:<5} | {b['size']} bytes"
            for b in boxes[:12]
        ],
        ["RECEIPT VALIDATION: SHA256"] + [
            f"{r['capability'][:28]:28} | {r['source_sha256'][:16]}"
            for r in receipts
        ],
        ["RESULT: 5 EXECUTED READ-ONLY RECEIPTS",
         "No binaries from third parties executed",
         "No publication, no bypass of protection",
         "Native parsing verified; mastery remains BLOCKED",
         "Replay of real CI output; not a terminal recording"],
    ]
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    font = ImageFont.truetype(font_path, 17) if Path(font_path).exists() else ImageFont.load_default()
    width, height, fps, seconds = 960, 540, 10, 30
    target = directory / "RECON_REVENG_002_REAL_EVIDENCE_30S.mp4"
    cmd = [
        "ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pixel_format", "rgb24",
        "-video_size", f"{width}x{height}", "-framerate", str(fps), "-i", "-",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(seconds),
        "-movflags", "+faststart", str(target),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for index in range(fps * seconds):
            scene = scenes[min(index // (6 * fps), len(scenes) - 1)]
            im = Image.new("RGB", (width, height), (10, 17, 28))
            draw = ImageDraw.Draw(im)
            draw.text((30, 25), "HAZEWAVE / RECON-REVENG-002", font=font, fill=(111, 215, 245))
            draw.line((30, 65, 930, 65), fill=(48, 83, 109), width=2)
            for line_index, line in enumerate(scene):
                if line_index > (index % (6 * fps)) // 7 + 1:
                    continue
                draw.text((30, 95 + 39 * line_index), line[:97], font=font, fill=(227, 236, 244))
            draw.text((30, 485), "EVIDENCE REPLAY • source artifact: RE_EXECUTION_LEDGER.jsonl",
                      font=font, fill=(133, 154, 172))
            draw.text((820, 485), f"{index/fps:04.1f}/30s",
                      font=font, fill=(133, 154, 172))
            assert proc.stdin is not None
            proc.stdin.write(im.tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("VIDEO_ENCODING_FAILED")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    if not target.is_file() or target.stat().st_size < 1000:
        raise RuntimeError("PROOF_VIDEO_MISSING")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--video", action="store_true")
    args = parser.parse_args()
    ledger = build_evidence(args.evidence_dir)
    if args.video:
        create_video(args.evidence_dir, ledger)
    print(json.dumps({
        "schema": "HazewaveREProofSummary/v1",
        "capabilities_executed": len(ledger),
        "sha256_verified": len(ledger),
        "evidence_dir": str(args.evidence_dir),
        "publication_attempted": False, "re_mastery": "BLOCKED",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
