"""Read-only, bounded Hazewave inspection primitives.

All entrypoints operate on LOCAL files only; they never execute input bytes,
download remote manifests, decrypt content, or publish outputs. The governed
entrypoint is run_inspection(); inspect_file() is the pure parser boundary.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import argparse
import json
import struct
import time

from hazewave.harness import (
    HazewaveAuthorization, HazewaveTask, issue_authorization, route_task,
    validate_authorization,
)

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_BOX_COUNT = 10000
MAX_BOX_DEPTH = 12
CAPABILITIES = frozenset({
    "binary_header_inspector",
    "media_container_deep_parser",
    "codec_stream_analyzer",
    "streaming_manifest_parser",
    "protection_detector",
})
MP4_CONTAINERS = frozenset({
    "moov", "trak", "mdia", "minf", "stbl", "edts", "dinf",
    "moof", "traf", "mvex", "udta", "sinf", "schi", "mfra",
})


def _u(data: bytes, offset: int, size: int, order: str = "big") -> int:
    if offset < 0 or offset + size > len(data):
        raise ValueError("TRUNCATED_BINARY_FIELD")
    return int.from_bytes(data[offset:offset + size], order)


def _binary_header(data: bytes) -> dict:
    if data.startswith(b"\x7fELF"):
        if len(data) < 52 or data[4] not in (1, 2) or data[5] not in (1, 2):
            raise ValueError("INVALID_ELF_HEADER")
        width = 8 if data[4] == 2 else 4
        size = 64 if width == 8 else 52
        if len(data) < size:
            raise ValueError("TRUNCATED_ELF_HEADER")
        endian = "little" if data[5] == 1 else "big"
        return {
            "format": "ELF64" if width == 8 else "ELF32",
            "byte_order": endian,
            "type": _u(data, 16, 2, endian),
            "architecture": _u(data, 18, 2, endian),
            "entry_point": _u(data, 24, width, endian),
            "header_bytes": size,
        }
    if data.startswith(b"MZ"):
        if len(data) < 64:
            raise ValueError("TRUNCATED_PE_HEADER")
        pe_off = _u(data, 0x3c, 4, "little")
        if pe_off + 24 > len(data):
            raise ValueError("TRUNCATED_PE_HEADER")
        if data[pe_off:pe_off + 4] != b"PE\x00\x00":
            raise ValueError("INVALID_PE_SIGNATURE")
        return {
            "format": "PE",
            "header_offset": pe_off,
            "architecture": _u(data, pe_off + 4, 2, "little"),
            "section_count": _u(data, pe_off + 6, 2, "little"),
            "optional_header_size": _u(data, pe_off + 20, 2, "little"),
        }
    if len(data) >= 32:
        magic = data[:4]
        magics = {
            b"\xfe\xed\xfa\xce": ("Mach-O32", "big"),
            b"\xce\xfa\xed\xfe": ("Mach-O32", "little"),
            b"\xfe\xed\xfa\xcf": ("Mach-O64", "big"),
            b"\xcf\xfa\xed\xfe": ("Mach-O64", "little"),
        }
        if magic in magics:
            fmt, endian = magics[magic]
            return {
                "format": fmt, "byte_order": endian,
                "architecture": _u(data, 4, 4, endian),
                "load_command_count": _u(data, 16, 4, endian),
            }
    raise ValueError("UNKNOWN_BINARY_FORMAT")


def _boxes(data: bytes, start: int, stop: int, depth: int, budget: list[int]) -> list:
    if depth > MAX_BOX_DEPTH:
        raise ValueError("MP4_MAX_DEPTH")
    boxes = []
    cursor = start
    while cursor < stop:
        budget[0] -= 1
        if budget[0] < 0:
            raise ValueError("MP4_MAX_BOX_COUNT")
        if stop - cursor < 8:
            raise ValueError("MP4_TRUNCATED_BOX_HEADER")
        size = _u(data, cursor, 4)
        tag = data[cursor + 4:cursor + 8].decode("latin-1")
        h = 8
        if size == 1:
            if stop - cursor < 16:
                raise ValueError("MP4_TRUNCATED_LARGE_BOX")
            size = _u(data, cursor + 8, 8)
            h = 16
        elif size == 0:
            size = stop - cursor
        if size < h or cursor + size > stop:
            raise ValueError("MP4_BOX_OUT_OF_BOUNDS")
        end = cursor + size
        item = {
            "type": tag, "offset": cursor, "size": size,
            "header_size": h, "payload_offset": cursor + h,
            "end": end,
        }
        if tag in MP4_CONTAINERS:
            item["children"] = _boxes(data, cursor + h, end, depth + 1, budget)
        boxes.append(item)
        cursor = end
    return boxes


def _walk(boxes: list):
    for b in boxes:
        yield b
        yield from _walk(b.get("children", []))


def _media(data: bytes) -> dict:
    if len(data) < 8 or data[4:8] not in {b"ftyp", b"styp", b"moov", b"moof", b"mdat"}:
        raise ValueError("NOT_ISO_BMFF")
    boxes = _boxes(data, 0, len(data), 0, [MAX_BOX_COUNT])
    if not boxes:
        raise ValueError("EMPTY_MP4")
    codecs = []
    chunk_offsets = []
    duration = None
    brand = None
    for b in _walk(boxes):
        at = b["payload_offset"]
        end = b["end"]
        if b["type"] == "ftyp" and end - at >= 8:
            brand = data[at:at + 4].decode("latin-1")
        elif b["type"] == "stsd" and end - at >= 8:
            count = _u(data, at + 4, 4)
            if count > 4096:
                raise ValueError("MP4_SAMPLE_ENTRY_COUNT_EXCEEDED")
            pos = at + 8
            for _ in range(count):
                if pos + 8 > end:
                    raise ValueError("MP4_TRUNCATED_SAMPLE_ENTRY")
                n = _u(data, pos, 4)
                if n < 8 or pos + n > end:
                    raise ValueError("MP4_INVALID_SAMPLE_ENTRY")
                codecs.append(data[pos + 4:pos + 8].decode("latin-1"))
                pos += n
        elif b["type"] == "mvhd" and end - at >= 20:
            version = data[at]
            if version == 0 and end - at >= 20:
                scale = _u(data, at + 12, 4)
                ticks = _u(data, at + 16, 4)
            elif version == 1 and end - at >= 32:
                scale = _u(data, at + 20, 4)
                ticks = _u(data, at + 24, 8)
            else:
                continue
            if scale:
                duration = ticks / scale
        elif b["type"] in ("stco", "co64") and end - at >= 8:
            count = _u(data, at + 4, 4)
            width = 4 if b["type"] == "stco" else 8
            if count > 1000000 or at + 8 + count * width > end:
                raise ValueError("MP4_INVALID_CHUNK_TABLE")
            # Bound displayed offsets while still validating the full table.
            chunk_offsets.extend(_u(data, at + 8 + i * width, width)
                                 for i in range(min(count, 1000)))
    return {
        "format": "ISO_BMFF", "major_brand": brand, "duration_seconds": duration,
        "codecs": sorted(set(codecs)), "chunk_offsets_sample": chunk_offsets[:1000],
        "boxes": boxes, "hex_preview": data[:64].hex(),
        "file_size": len(data),
    }


def _codec(data: bytes) -> dict:
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        if len(data) < 20 or _u(data, 4, 4, "little") + 8 > len(data):
            raise ValueError("INVALID_WAV_RIFF")
        at = 12
        while at + 8 <= len(data):
            size = _u(data, at + 4, 4, "little")
            nxt = at + 8 + size + (size % 2)
            if nxt > len(data):
                raise ValueError("TRUNCATED_WAV_CHUNK")
            if data[at:at + 4] == b"fmt ":
                if size < 16:
                    raise ValueError("INVALID_WAV_FMT")
                fmt, channels, sample_rate, byte_rate, align, bits = struct.unpack_from(
                    "<HHIIHH", data, at + 8
                )
                return {
                    "codec": "PCM" if fmt == 1 else f"WAV_FORMAT_{fmt}",
                    "channels": channels, "sample_rate": sample_rate,
                    "bits_per_sample": bits, "block_align": align,
                    "byte_rate": byte_rate,
                }
            at = nxt
        raise ValueError("WAV_FMT_NOT_FOUND")
    if len(data) >= 7 and data[:1] == b"\xff" and data[1] & 0xf0 == 0xf0:
        profile = (data[2] >> 6) & 3
        sf = (data[2] >> 2) & 15
        frequencies = (
            96000, 88200, 64000, 48000, 44100, 32000, 24000,
            22050, 16000, 12000, 11025, 8000, 7350,
        )
        channels = ((data[2] & 1) << 2) | (data[3] >> 6)
        frame_length = ((data[3] & 3) << 11) | (data[4] << 3) | (data[5] >> 5)
        header_len = 7 if data[1] & 1 else 9
        if sf >= len(frequencies) or frame_length < header_len or frame_length > len(data):
            raise ValueError("INVALID_ADTS_FRAME")
        return {
            "codec": "AAC_ADTS", "profile": profile + 1,
            "sample_rate": frequencies[sf], "channels": channels,
            "first_frame_length": frame_length, "header_length": header_len,
        }
    raise ValueError("UNKNOWN_CODEC_STREAM")


def _hls(data: bytes) -> dict:
    try:
        s = data.decode("utf-8-sig")
    except UnicodeError as e:
        raise ValueError("INVALID_HLS_UTF8") from e
    if s.startswith("\ufeff") or not s.startswith("#EXTM3U"):
        raise ValueError("INVALID_HLS_HEADER")
    if len(s) > 2 * 1024 * 1024:
        raise ValueError("HLS_TOO_LARGE")
    lines = [line.strip() for line in s.splitlines() if line.strip()]
    if not lines or lines[0] != "#EXTM3U":
        raise ValueError("INVALID_HLS_HEADER")
    segments = []
    variants = []
    tags = []
    duration = None
    next_variant = False
    protection = []
    for line in lines[1:]:
        if line.startswith("#"):
            if line.startswith("#EXT-X-KEY:") or line.startswith("#EXT-X-SESSION-KEY:"):
                # Never emit key URIs, keys or raw encryption attributes.
                protection.append("HLS_EXT_X_KEY")
            elif line.startswith("#EXT-X-STREAM-INF:"):
                next_variant = True
            elif line.startswith("#EXTINF:"):
                try:
                    duration = float(line.split(":", 1)[1].split(",", 1)[0])
                except (ValueError, IndexError) as e:
                    raise ValueError("INVALID_EXTINF") from e
                if duration < 0 or duration > 86400:
                    raise ValueError("INVALID_EXTINF")
            tags.append(line.split(":", 1)[0])
        elif next_variant:
            variants.append({"uri": line})
            next_variant = False
        else:
            segments.append({"uri": line, "duration": duration})
            duration = None
    if duration is not None or next_variant:
        raise ValueError("HLS_MISSING_SEGMENT_URI")
    return {
        "format": "HLS", "playlist_type": "master" if variants else "media",
        "segments": segments[:10000], "variants": variants[:10000],
        "tag_names": sorted(set(tags)), "protection_signals": sorted(set(protection)),
    }


def _protection(data: bytes) -> dict:
    signals = []
    if data.startswith(b"#EXTM3U"):
        hls = _hls(data)
        signals.extend(hls["protection_signals"])
    elif len(data) >= 8 and data[4:8] in (b"ftyp", b"styp", b"moov", b"moof", b"mdat"):
        media = _media(data)
        signals.extend("ISOBMFF_" + box["type"].upper()
                       for box in _walk(media["boxes"])
                       if box["type"] in ("pssh", "sinf", "schm", "tenc"))
    elif data.startswith(b"\x7fELF") or data.startswith(b"MZ"):
        return {"detected": False, "signals": [], "status": "UNKNOWN"}
    else:
        return {"detected": False, "signals": [], "status": "UNKNOWN"}
    signals = sorted(set(signals))
    return {
        "detected": bool(signals), "signals": signals,
        "status": "PROTECTION_DETECTED" if signals else "NOT_DETECTED",
        "note": "Detection only; NOT_DETECTED does not guarantee absence of DRM.",
    }


def inspect_file(capability: str, file_path: str | Path) -> dict:
    """Pure read-only parser. Does not establish authorization."""
    if capability not in CAPABILITIES:
        raise ValueError("UNKNOWN_INSPECTION_CAPABILITY")
    path = Path(file_path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("INPUT_MUST_BE_REGULAR_LOCAL_FILE")
    size = path.stat().st_size
    if not 0 < size <= MAX_FILE_BYTES:
        raise ValueError("INSPECTION_INPUT_SIZE_OUT_OF_BOUNDS")
    data = path.read_bytes()
    if len(data) != size:
        raise ValueError("INPUT_MODIFIED_DURING_INSPECTION")
    if capability == "binary_header_inspector":
        return _binary_header(data)
    if capability == "media_container_deep_parser":
        return _media(data)
    if capability == "codec_stream_analyzer":
        return _codec(data)
    if capability == "streaming_manifest_parser":
        return _hls(data)
    return _protection(data)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def run_inspection(
    capability: str, file_path: str | Path, *,
    task_id: str, authorization: HazewaveAuthorization,
) -> dict:
    """Harness-checked boundary with honest result/provenance hash receipt."""
    started = time.perf_counter()
    validate_authorization(
        authorization, expected_task_id=task_id, expected_capability=capability,
    )
    # Structural auth is reproducible, not a signed owner/publisher permission.
    fresh = issue_authorization(route_task(HazewaveTask(
        task_id=task_id, goal="Read-only inspection",
        required_capability=capability, requested_domain=authorization.domain,
    )))
    if authorization.authorization_id != fresh.authorization_id:
        raise PermissionError("AUTHORIZATION_ID_MISMATCH")
    path = Path(file_path)
    result = inspect_file(capability, path)
    data_hash = sha256(path.read_bytes()).hexdigest()
    elapsed = round((time.perf_counter() - started) * 1000, 3)
    receipt = {
        "schema": "HazewaveREExecutionReceipt/v1",
        "authority": "HAZEWAVE_HARNESS",
        "authorization_id": authorization.authorization_id,
        "task_id": task_id,
        "capability": capability,
        "status": "EXECUTED_READ_ONLY",
        "source_sha256": data_hash, "result_sha256": sha256(_canonical(result)).hexdigest(),
        "file_size": path.stat().st_size,
        "elapsed_ms": elapsed, "third_party_execution": False,
        "cost_usd": 0, "publication_attempted": False,
    }
    return {"result": result, "receipt": receipt}


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m hazewave.re_inspectors")
    parser.add_argument("capability", choices=sorted(CAPABILITIES))
    parser.add_argument("file_path")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--domain", choices=("HAZE", "WAVE"), required=True)
    args = parser.parse_args()
    try:
        auth = issue_authorization(route_task(HazewaveTask(
            task_id=args.task_id, goal="Read-only inspected artifact",
            required_capability=args.capability, requested_domain=args.domain,
        )))
        print(json.dumps(run_inspection(
            args.capability, args.file_path, task_id=args.task_id,
            authorization=auth), sort_keys=True))
        return 0
    except (OSError, PermissionError, ValueError) as e:
        print(json.dumps({"status": "BLOCKED", "reason": str(e)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
