from __future__ import annotations

import hashlib
import json
import struct
import time

import pytest

from hazewave.harness import (
    HazewaveTask, harness_status, issue_authorization, route_task,
)
from hazewave.re_inspectors import inspect_file, run_inspection


def _box(tag: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload) + 8) + tag + payload


def _authorization(capability: str, domain: str = "WAVE"):
    return issue_authorization(route_task(HazewaveTask(
        task_id="recon-reveng-002-tests",
        goal="Inspect a local controlled artifact",
        required_capability=capability,
        requested_domain=domain,
    )))


def test_registry_exposes_five_inspection_capabilities():
    required = {
        "binary_header_inspector", "media_container_deep_parser",
        "codec_stream_analyzer", "streaming_manifest_parser",
        "protection_detector",
    }
    assert required.issubset(set(harness_status()["capabilities"]))
    with pytest.raises(PermissionError):
        route_task(HazewaveTask(
            task_id="wrong-domain", goal="invalid", requested_domain="BRIDGE",
            required_capability="media_container_deep_parser",
        ))


def test_elf_header_binary_real_bytes(tmp_path):
    path = tmp_path / "hello.elf"
    data = bytearray(64)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", data, 16, 2)
    struct.pack_into("<H", data, 18, 62)
    struct.pack_into("<Q", data, 24, 0x401000)
    path.write_bytes(data)
    result = inspect_file("binary_header_inspector", path)
    assert result["format"] == "ELF64"
    assert result["entry_point"] == 0x401000
    assert result["architecture"] == 62


def test_pe_header_offsets_are_bounded(tmp_path):
    path = tmp_path / "sample.exe"
    b = bytearray(256)
    b[:2] = b"MZ"
    struct.pack_into("<I", b, 0x3c, 0x80)
    b[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<H", b, 0x84, 0x8664)
    struct.pack_into("<H", b, 0x86, 1)
    path.write_bytes(b)
    assert inspect_file("binary_header_inspector", path)["format"] == "PE"
    b[0x3c:0x40] = b"\xff\xff\xff\x7f"
    path.write_bytes(b)
    with pytest.raises(ValueError, match="TRUNCATED_PE_HEADER"):
        inspect_file("binary_header_inspector", path)


def test_mp4_boxes_nested_offsets_and_corruption(tmp_path):
    path = tmp_path / "media.mp4"
    data = _box(b"ftyp", b"isom\x00\x00\x00\x00isom") + _box(
        b"moov", _box(b"trak", _box(b"free", b"abcd"))
    ) + _box(b"mdat", b"data")
    path.write_bytes(data)
    result = inspect_file("media_container_deep_parser", path)
    assert [x["type"] for x in result["boxes"]] == ["ftyp", "moov", "mdat"]
    assert result["boxes"][1]["children"][0]["children"][0]["type"] == "free"
    assert result["boxes"][1]["offset"] == 20
    assert result["boxes"][2]["end"] == len(data)
    path.write_bytes(b"\x00\x00\x01\x00ftyp")
    with pytest.raises(ValueError, match="MP4_BOX_OUT_OF_BOUNDS"):
        inspect_file("media_container_deep_parser", path)


def test_codec_adts_frame_and_corruption(tmp_path):
    path = tmp_path / "sample.aac"
    # ADTS: AAC-LC, 44.1 kHz, 2 channels, 9 bytes total.
    path.write_bytes(bytes([0xff, 0xf1, 0x50, 0x80, 0x01, 0x3f, 0xfc, 0, 0]))
    out = inspect_file("codec_stream_analyzer", path)
    assert out["codec"] == "AAC_ADTS"
    assert out["sample_rate"] == 44100
    assert out["channels"] == 2
    path.write_bytes(bytes([0xff, 0xf1, 0x50, 0x80, 0x00, 0x00, 0xfc]))
    with pytest.raises(ValueError, match="INVALID_ADTS_FRAME"):
        inspect_file("codec_stream_analyzer", path)


def test_wav_pcm_header(tmp_path):
    path = tmp_path / "x.wav"
    payload = bytes(8)
    fmt = struct.pack("<HHIIHH", 1, 1, 48000, 96000, 2, 16)
    riff = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
    riff += b"data" + struct.pack("<I", len(payload)) + payload
    path.write_bytes(b"RIFF" + struct.pack("<I", len(riff)) + riff)
    result = inspect_file("codec_stream_analyzer", path)
    assert result["codec"] == "PCM"
    assert result["sample_rate"] == 48000


def test_hls_manifest_and_protection_detection(tmp_path):
    path = tmp_path / "master.m3u8"
    path.write_text(
        '#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-KEY:METHOD=AES-128,URI="key.bin"\n'
        '#EXTINF:3.500,\nsegment1.ts\n', encoding="utf-8"
    )
    manifest = inspect_file("streaming_manifest_parser", path)
    assert manifest["segments"][0]["uri"] == "segment1.ts"
    assert manifest["segments"][0]["duration"] == 3.5
    detection = inspect_file("protection_detector", path)
    assert detection["detected"] is True
    assert "HLS_EXT_X_KEY" in detection["signals"]
    assert "key.bin" not in json.dumps(detection)  # Never emit key endpoints.


def test_receipt_is_evidence_bound_and_fails_closed(tmp_path):
    p = tmp_path / "source.m3u8"
    p.write_text("#EXTM3U\n#EXTINF:2,\na.ts\n", encoding="utf-8")
    a = _authorization("streaming_manifest_parser")
    output = run_inspection(
        "streaming_manifest_parser", p,
        task_id=a.task_id, authorization=a,
    )
    assert output["receipt"]["authority"] == "HAZEWAVE_HARNESS"
    assert output["receipt"]["source_sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
    assert output["receipt"]["capability"] == "streaming_manifest_parser"
    assert output["receipt"]["result_sha256"] == hashlib.sha256(
        json.dumps(output["result"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(PermissionError):
        run_inspection(
            "protection_detector", p, task_id=a.task_id, authorization=a,
        )


def test_corrupted_and_unknown_files_fail_closed(tmp_path):
    p = tmp_path / "unknown.bin"
    p.write_bytes(b"totally unknown file")
    for cap in ("binary_header_inspector", "media_container_deep_parser",
                "codec_stream_analyzer", "streaming_manifest_parser"):
        with pytest.raises(ValueError):
            inspect_file(cap, p)
    assert inspect_file("protection_detector", p)["status"] == "UNKNOWN"


def test_parser_bounded_runtime_for_1mb_local_file(tmp_path):
    p = tmp_path / "big.mp4"
    p.write_bytes(_box(b"mdat", bytes(1024 * 1024)))
    start = time.monotonic()
    out = inspect_file("media_container_deep_parser", p)
    assert out["boxes"][0]["size"] == p.stat().st_size
    assert time.monotonic() - start < 3.0
