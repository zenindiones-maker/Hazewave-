"""HAZEWAVE-only offline vector-art production bridge.

Render the EXISTING first-party world-signal SVG path through a separately
verified VectorCraft CLI. ArtCraft is an optional isolated design tool, never
a browser/runtime dependency. This does not approve or publish generated art.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ENGINE_DIR = Path(__file__).resolve().parent
APP_ROOT = ENGINE_DIR.parent.parent
SVG_PATH = re.compile(r'<path\s+id="world-signal-path"\s+d="([^"]+)"')
SAFE_PATH = re.compile(r"^[MLHVCSQTAZmlhvcsqtaz0-9.,+\-\sEe]+$")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
EXPECTED_SIZE = (420, 820)
PROJECT_NAME = "zenindiones-maker/Hazewave-"
TOOL_REPO = "storytold/vectorcraft"
TOOL_TAG = "v0.7.0"
TOOL_RELEASE_SHA256 = "d6b0ee57e1bdbd377b44c8524e8569ad2b4dff46b792fc10b0edbf8d74292acd"


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def _private_output(dest: Path) -> Path:
    target = dest.expanduser().resolve(strict=False)
    if target.exists() or target.is_relative_to(APP_ROOT):
        raise ValueError("OUTPUT_MUST_BE_FRESH_OUTSIDE_HAZEWAVE_REPOSITORY")
    return target


def source_svg(source: Path) -> tuple[bytes, str]:
    if not source.is_file() or source.is_symlink():
        raise ValueError("HAZEWAVE_SOURCE_MISSING")
    raw = source.read_bytes()
    if len(raw) > 40_000 or not raw.startswith(b"<!doctype html>"):
        raise ValueError("HAZEWAVE_SOURCE_FORMAT_INVALID")
    html = raw.decode("utf-8")
    found = SVG_PATH.findall(html)
    if len(found) != 1 or len(found[0]) > 2000 or not SAFE_PATH.fullmatch(found[0]):
        raise ValueError("FIRST_PARTY_SVG_PATH_NOT_VERIFIABLE")
    # All image geometry derives from the first-party WAVE engine; this is a
    # vector asset proof, not a substitute for the moving browser signal.
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="420" height="820" '
        'viewBox="0 0 420 820"><path d="' + found[0] +
        '" stroke="#eeb2ff" stroke-width="5" stroke-linecap="round" '
        'stroke-linejoin="round" fill="none"/></svg>\n'
    ).encode("utf-8")
    return svg, digest(raw)


def prepare(source: Path, output: Path) -> dict:
    svg, source_sha = source_svg(source)
    dest = _private_output(output)
    dest.mkdir(parents=True, mode=0o700)
    (dest / "wave-signal-source.svg").write_bytes(svg)
    receipt = {
        "schema": "HazewaveVectorCraftSiteAssetProof/v1",
        "authority": "NONE",
        "project": PROJECT_NAME,
        "site_engine_path": "apps/hazewave-site/experiments/travessia-v4/index.html",
        "site_engine_source_sha256": source_sha,
        "first_party_svg_sha256": digest(svg),
        "external_tool_repo": TOOL_REPO,
        "external_tool_release": TOOL_TAG,
        "external_release_archive_sha256": TOOL_RELEASE_SHA256,
        "tool_executed": False,
        "original_art_files_modified": False,
        "production_approved": False,
        "merged_or_published": False,
        "output_png_sha256": None,
    }
    (dest / "proof.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return receipt


def validate_png(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("VECTORCRAFT_PNG_NOT_GENERATED")
    raw = path.read_bytes()
    if len(raw) < 100 or len(raw) > 9_000_000 or raw[:8] != PNG_SIGNATURE:
        raise ValueError("VECTORCRAFT_OUTPUT_NOT_PNG")
    width = int.from_bytes(raw[16:20], "big")
    height = int.from_bytes(raw[20:24], "big")
    if (width, height) != EXPECTED_SIZE:
        raise ValueError("VECTORCRAFT_WRONG_CANVAS_SIZE")
    return digest(raw)


def render(output: Path, cli: Path, pinned_binary_hash: str) -> dict:
    root = output.resolve(strict=True)
    if root.is_symlink() or root.is_relative_to(APP_ROOT):
        raise ValueError("PRIVATE_OUTPUT_LOCATION_DENIED")
    manifest_path = root / "proof.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "HazewaveVectorCraftSiteAssetProof/v1"
        or manifest.get("project") != PROJECT_NAME
        or manifest.get("external_release_archive_sha256") != TOOL_RELEASE_SHA256
        or manifest.get("production_approved") is not False
        or manifest.get("tool_executed") is not False
    ):
        raise ValueError("WRONG_BRIDGE_RECEIPT_OR_REPLAY")
    svg = root / "wave-signal-source.svg"
    if digest(svg.read_bytes()) != manifest["first_party_svg_sha256"]:
        raise ValueError("SOURCE_SVG_MUTATED")
    exe = cli.resolve(strict=True)
    if not exe.is_file() or cli.is_symlink() or not os.access(exe, os.X_OK):
        raise ValueError("VECTORCRAFT_CLI_NOT_EXECUTABLE")
    if not re.fullmatch("[a-f0-9]{64}", pinned_binary_hash) or digest(exe.read_bytes()) != pinned_binary_hash:
        raise ValueError("VECTORCRAFT_BINARY_HASH_DRIFT")
    dest = root / "wave-signal-vectorcraft.png"
    if dest.exists():
        raise ValueError("OUTPUT_ALREADY_EXISTS")
    # No shell expansion, no upstream setup scripts, bounded execution.
    proc = subprocess.run(
        [str(exe), "convert", str(svg), str(dest)],
        cwd=root, stdin=subprocess.DEVNULL, capture_output=True,
        check=False, timeout=100, env={
            "HOME": str(root), "TMPDIR": str(root),
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C.UTF-8",
        },
    )
    if proc.returncode != 0:
        raise ValueError("VECTORCRAFT_REAL_CONVERT_FAILED")
    png_sha = validate_png(dest)
    manifest["tool_executed"] = True
    manifest["tool_binary_sha256"] = pinned_binary_hash
    manifest["output_png_sha256"] = png_sha
    manifest["tool_execution_status"] = "REAL_CLI_OUTPUT_PNG_VALIDATED"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--source", type=Path, default=ENGINE_DIR / "index.html")
    prep.add_argument("--output", type=Path, required=True)
    proof = sub.add_parser("render")
    proof.add_argument("--output", type=Path, required=True)
    proof.add_argument("--cli", type=Path, required=True)
    proof.add_argument("--binary-sha256", required=True)
    args = parser.parse_args()
    try:
        receipt = (
            prepare(args.source, args.output)
            if args.command == "prepare"
            else render(args.output, args.cli, args.binary_sha256)
        )
    except (OSError, ValueError, subprocess.TimeoutExpired, UnicodeError, json.JSONDecodeError) as exc:
        print("HAZEWAVE_VECTORCRAFT=BLOCKED:" + str(exc), file=sys.stderr)
        return 20
    print("HAZEWAVE_VECTORCRAFT=" + (
        "REAL_CLI_PNG_VALIDATED" if receipt["tool_executed"] else "PREPARED_NOT_EXECUTED"
    ))
    print("PROJECT=HAZEWAVE_ONLY")
    print("PRODUCTION_APPROVED=FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
