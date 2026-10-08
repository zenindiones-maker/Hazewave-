"""Hazewave WAVE: bounded visual screenshot evidence from Iris v0.4.1.

Iris is a *camera*, not an autonomous web explorer and not a reverse
engineering authority. This module accepts a first-party test fixture and
optionally validates an explicit localhost preview origin. Never use it
to ingest arbitrary URLs, secrets, intranet hosts or private artist media.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import tempfile
from typing import Any
from urllib.parse import urlsplit
import zlib


class IrisCaptureError(RuntimeError):
    pass


_PNG_SIG = bytes.fromhex("89504e470d0a1a0a")
_FIXTURE = Path("tests/fixtures/iris-proof.html")
_STOCK_REFLEX_PORT = 28080


def iris_capture_policy(
    url: str,
    *,
    workspace: Path,
    admitted_preview_origin: str | None = None,
) -> str:
    """Admit ONLY a first-party exact fixture or explicitly named local preview.

    The upstream Iris binary is NOT a secure URL policy enforcement gateway;
    its MCP stdio service remains unregistered until a redirect-safe and
    request-scoped Harness gateway is independently reviewed. Local preview
    admission is solely an input-planning contract, not live MCP approval.
    """
    if not isinstance(url, str) or not url or len(url) > 2048:
        raise IrisCaptureError("IRIS_TARGET_NOT_ADMITTED")
    parts = urlsplit(url)
    if parts.scheme == "file":
        fixture = (Path(workspace).resolve() / _FIXTURE)
        if parts.netloc or parts.query or parts.fragment or not parts.path:
            raise IrisCaptureError("IRIS_TARGET_NOT_ADMITTED")
        target = Path(parts.path)
        try:
            if target.is_symlink() or not stat.S_ISREG(target.lstat().st_mode):
                raise IrisCaptureError("IRIS_TARGET_NOT_ADMITTED")
            if target.resolve(strict=True) != fixture.resolve(strict=True):
                raise IrisCaptureError("IRIS_TARGET_NOT_ADMITTED")
        except OSError as exc:
            raise IrisCaptureError("IRIS_TARGET_NOT_ADMITTED") from exc
        return url
    if admitted_preview_origin is None:
        raise IrisCaptureError("IRIS_TARGET_NOT_ADMITTED")
    if parts.scheme != "http" or parts.username or parts.password or parts.fragment:
        raise IrisCaptureError("IRIS_TARGET_NOT_ADMITTED")
    if parts.hostname not in {"localhost", "127.0.0.1"}:
        raise IrisCaptureError("IRIS_TARGET_NOT_ADMITTED")
    try:
        port = parts.port
    except ValueError as exc:
        raise IrisCaptureError("IRIS_TARGET_NOT_ADMITTED") from exc
    if not port or port == _STOCK_REFLEX_PORT:
        raise IrisCaptureError("IRIS_TARGET_NOT_ADMITTED")
    if f"{parts.scheme}://{parts.netloc}" != admitted_preview_origin:
        raise IrisCaptureError("IRIS_TARGET_NOT_ADMITTED")
    return url


def _inspect_png(path: Path) -> tuple[str, int, int, int]:
    if path.is_symlink():
        raise IrisCaptureError("IRIS_IMAGE_UNSAFE")
    try:
        meta = path.lstat()
        if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= 20_000_000:
            raise IrisCaptureError("IRIS_IMAGE_UNSAFE")
        data = path.read_bytes()
    except OSError as exc:
        raise IrisCaptureError("IRIS_IMAGE_UNSAFE") from exc
    if not data.startswith(_PNG_SIG):
        raise IrisCaptureError("IRIS_IMAGE_INVALID_PNG")
    offset = len(_PNG_SIG)
    found_header = False
    found_end = False
    width = height = 0
    while offset + 12 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        if length > 20_000_000 or offset + 12 + length > len(data):
            raise IrisCaptureError("IRIS_IMAGE_INVALID_PNG")
        kind = data[offset + 4:offset + 8]
        chunk = data[offset + 8:offset + 8 + length]
        crc = struct.unpack_from(">I", data, offset + 8 + length)[0]
        if zlib.crc32(kind + chunk) & 0xFFFFFFFF != crc:
            raise IrisCaptureError("IRIS_IMAGE_INVALID_PNG")
        if not found_header:
            if kind != b"IHDR" or length != 13:
                raise IrisCaptureError("IRIS_IMAGE_INVALID_PNG")
            width, height = struct.unpack_from(">II", chunk)
            if not (0 < width <= 16384 and 0 < height <= 16384):
                raise IrisCaptureError("IRIS_IMAGE_DIMENSIONS_INVALID")
            found_header = True
        if kind == b"IEND":
            if length or offset + 12 != len(data):
                raise IrisCaptureError("IRIS_IMAGE_INVALID_PNG")
            found_end = True
            break
        offset += 12 + length
    if not found_header or not found_end:
        raise IrisCaptureError("IRIS_IMAGE_INVALID_PNG")
    return hashlib.sha256(data).hexdigest(), len(data), width, height


def verify_iris_capture(
    result: dict[str, Any],
    *,
    output: Path,
    source_url: str,
) -> dict[str, Any]:
    if not isinstance(result, dict) or result.get("status") != "ok":
        raise IrisCaptureError("IRIS_CAPTURE_STATUS_NOT_OK")
    if result.get("url") != source_url or result.get("format") != "png":
        raise IrisCaptureError("IRIS_CAPTURE_SOURCE_OR_FORMAT_DRIFT")
    digest, size, px_width, px_height = _inspect_png(Path(output))
    if result.get("bytes") != size:
        raise IrisCaptureError("IRIS_CAPTURE_BYTES_MISMATCH")
    w, h = result.get("css_width"), result.get("css_height")
    if not isinstance(w, (int, float)) or not isinstance(h, (int, float)) or not (0 < w <= 16000 and 0 < h <= 16000):
        raise IrisCaptureError("IRIS_CAPTURE_DIMENSIONS_MISSING")
    return {
        "schema": "HazewaveIrisVisualEvidence/v1",
        "status": "CAPTURE_FILE_VERIFIED",
        "source_type": "FIRST_PARTY_SYNTHETIC_FIXTURE",
        "domain": "WAVE",
        "authority": "HAZEWAVE_HARNESS",
        "iris_version": "0.4.1",
        "image_sha256": digest,
        "png_bytes": size,
        "pixel_width": px_width,
        "pixel_height": px_height,
        "css_width": w,
        "css_height": h,
        "mcp_connected": False,
        "harness_live_route_proven": False,
        "stock_health": "NOT_TESTED",
        "codespace_runtime_proven": False,
        "production_approved": False,
        "human_review_required": True,
    }


def capture_owned_fixture(
    *,
    workspace: Path,
    iris_binary: Path,
    chrome_binary: Path,
    output: Path,
    process_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    fixture = (workspace.resolve() / _FIXTURE)
    url = iris_capture_policy(fixture.as_uri(), workspace=workspace)
    if Path(iris_binary).is_symlink() or not Path(iris_binary).is_file():
        raise IrisCaptureError("IRIS_BINARY_NOT_ATTESTED")
    if not Path(chrome_binary).is_file():
        raise IrisCaptureError("IRIS_CHROME_NOT_FOUND")
    out = Path(output)
    if out.exists() or out.is_symlink():
        raise IrisCaptureError("IRIS_OUTPUT_MUST_NOT_EXIST")
    if out.parent.is_symlink():
        raise IrisCaptureError("IRIS_OUTPUT_DIR_UNSAFE")
    out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    args = [
        str(iris_binary), "--chrome", str(chrome_binary),
        "--selector", "#hazewave-iris-proof",
        "--padding", "8", "--scale", "1",
        "--timeout", "20", "--json", "-o", str(out), url,
    ]
    try:
        process = subprocess.run(args, capture_output=True, text=True, timeout=36, check=False, env=process_env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise IrisCaptureError("IRIS_CAPTURE_PROCESS_ERROR") from exc
    if process.returncode != 0:
        # Only the immutable first-party fixture is admitted here; expose a
        # bounded diagnostic for reproducible Chrome startup failures.
        safe_error = " ".join(process.stderr.split())[-1000:]
        raise IrisCaptureError("IRIS_CAPTURE_NONZERO:" + safe_error)
    try:
        lines = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise IrisCaptureError("IRIS_CAPTURE_OUTPUT_INVALID") from exc
    if len(lines) != 1:
        raise IrisCaptureError("IRIS_CAPTURE_OUTPUT_INVALID")
    return verify_iris_capture(lines[0], output=out, source_url=url)


def _save_receipt(receipt: dict[str, Any], state_root: Path) -> Path:
    root = Path(state_root).expanduser()
    if root.is_symlink():
        raise IrisCaptureError("IRIS_RECEIPT_ROOT_UNSAFE")
    dest = root / "iris" / "receipts"
    if dest.parent.is_symlink() or dest.is_symlink():
        raise IrisCaptureError("IRIS_RECEIPT_ROOT_UNSAFE")
    dest.mkdir(parents=True, exist_ok=True, mode=0o700)
    dest.chmod(0o700)
    path = dest / ("iris-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    blob = (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(blob)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hazewave.iris_capture")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--iris", type=Path, required=True)
    parser.add_argument("--chrome", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(prefix="iris-hazewave-owned-fixture-") as temp:
            output = Path(temp) / "proof.png"
            receipt = capture_owned_fixture(
                workspace=args.workspace, iris_binary=args.iris,
                chrome_binary=args.chrome, output=output,
            )
        path = _save_receipt(receipt, args.state_root)
        print("HAZEWAVE_IRIS_FIXTURE=PASS")
        print("HAZEWAVE_IRIS_MCP_CONNECTED=NOT_PROVEN")
        print("HAZEWAVE_IRIS_CODESPACE=NOT_ATTESTED")
        print(json.dumps({"status": receipt["status"], "sha256": receipt["image_sha256"],
                          "pixel_width": receipt["pixel_width"], "pixel_height": receipt["pixel_height"],
                          "receipt": str(path)}))
        return 0
    except (IrisCaptureError, ValueError, OSError) as exc:
        print("HAZEWAVE_IRIS_FIXTURE=BLOCKED:" + str(exc), file=sys.stderr)
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
