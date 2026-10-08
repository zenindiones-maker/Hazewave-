"""Read-only validation of owner-provided Codespace AV fixture evidence.

Checks source output, durable receipt integrity and negative-control metrics.
This is NOT independent host attestation, benchmarking, tool routing or approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any


class HostAvEvidenceError(ValueError):
    pass


SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
MAX_BYTES = 2 * 1024 * 1024
MARKER = b"HAZEWAVE_AV_METRICS=PASS:OWNED_SYNTHETIC_ONLY"
OUTPUT_MARKER = b"HAZEWAVE_AV_FIDELITY=PASS_SYNTHETIC"


def _private_file(path: Path) -> bytes:
    try:
        st = path.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or st.st_mode & 0o077 or st.st_size < 1
                or st.st_size > MAX_BYTES or path.is_symlink()):
            raise HostAvEvidenceError("UNSAFE_FILE")
        return path.read_bytes()
    except OSError as exc:
        raise HostAvEvidenceError("UNSAFE_FILE") from exc


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for k, v in pairs:
        if k in data:
            raise HostAvEvidenceError("DUPLICATE_JSON_KEY")
        data[k] = v
    return data


def _json(payload: bytes) -> dict[str, Any]:
    try:
        obj = json.loads(payload, object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HostAvEvidenceError("INVALID_JSON") from exc
    if not isinstance(obj, dict):
        raise HostAvEvidenceError("INVALID_JSON")
    return obj


def _numeric(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HostAvEvidenceError("METRIC_NEGATIVE_CONTROL_FAILED")
    x = float(value)
    if not math.isfinite(x):
        raise HostAvEvidenceError("METRIC_NEGATIVE_CONTROL_FAILED")
    return x


def verify_host_av_evidence(
    *, log_path: Path, receipt_path: Path, reviewed_sha: str,
    expected_log_sha256: str, expected_receipt_sha256: str
) -> dict[str, Any]:
    """Validate actual local bytes against externally supplied expected digests."""
    if not SHA40.fullmatch(reviewed_sha):
        raise HostAvEvidenceError("REVIEWED_SHA_INVALID")
    if not SHA64.fullmatch(expected_log_sha256) or not SHA64.fullmatch(expected_receipt_sha256):
        raise HostAvEvidenceError("EXPECTED_HASH_INVALID")
    log_path, receipt_path = Path(log_path), Path(receipt_path)
    if log_path.name != "av_synthetic_fixture.log" or log_path.parent.name != reviewed_sha:
        raise HostAvEvidenceError("HOST_LOG_SCOPE_MISMATCH")
    if not receipt_path.name.startswith("av-receipt-") or not receipt_path.parent.name.startswith("av-metrics-"):
        raise HostAvEvidenceError("HOST_RECEIPT_SCOPE_MISMATCH")
    log, receipt = _private_file(log_path), _private_file(receipt_path)
    if hashlib.sha256(log).hexdigest() != expected_log_sha256:
        raise HostAvEvidenceError("LOG_DIGEST_MISMATCH")
    if hashlib.sha256(receipt).hexdigest() != expected_receipt_sha256:
        raise HostAvEvidenceError("RECEIPT_DIGEST_MISMATCH")
    rows = log.splitlines()
    if rows.count(MARKER) != 1 or rows.count(OUTPUT_MARKER) != 1:
        raise HostAvEvidenceError("ORACLE_SUCCESS_MARKER_MISSING")
    entries = [row for row in rows if row.startswith(b"{")]
    if len(entries) != 1:
        raise HostAvEvidenceError("ORACLE_RECEIPT_COUNT_INVALID")
    record = _json(entries[0])
    stored = _json(receipt)
    if record != stored or receipt != (json.dumps(record, sort_keys=True) + "\n").encode():
        raise HostAvEvidenceError("LOG_RECEIPT_MISMATCH")
    required = {
        "schema": "HazewaveSyntheticAudioVideoFidelity/v1",
        "harness_authority": "HAZEWAVE_HARNESS",
        "source": "OWNED_SYNTHETIC_MEDIA",
        "actual_ffmpeg_executed": True,
        "synthetic_audio_verified": True,
        "synthetic_video_verified": True,
        "owner_media_analyzed": False,
        "agent_mcp_connected": False,
        "capability_plane_ready": False,
        "production_approved": False,
        "no_subjective_audio_or_visual_approval": True,
    }
    if any(record.get(k) != v or type(record.get(k)) is not type(v)
           for k, v in required.items()):
        raise HostAvEvidenceError("UNAUTHORIZED_READINESS_CLAIM")
    if (not isinstance(record.get("haze_authorization_id"), str)
            or not record["haze_authorization_id"]
            or not isinstance(record.get("wave_authorization_id"), str)
            or not record["wave_authorization_id"]):
        raise HostAvEvidenceError("HARNESS_AUTHORIZATION_CLAIM_MISSING")
    try:
        attenuation = _numeric(record["audio_attenuation_detected_db"])
        same = _numeric(record["identical_video_ssim"])
        diff = _numeric(record["altered_video_ssim"])
        hashes = record["sample_hashes"]
        keys = ("reference_wav", "altered_wav", "reference_video", "altered_video")
        if not isinstance(hashes, dict) or not all(
            isinstance(hashes.get(k), str) and SHA64.fullmatch(hashes[k]) for k in keys
        ):
            raise HostAvEvidenceError("SAMPLE_DIGESTS_INVALID")
    except (KeyError, TypeError) as exc:
        raise HostAvEvidenceError("METRIC_NEGATIVE_CONTROL_FAILED") from exc
    if not (10 <= attenuation <= 14 and 0.999 <= same <= 1
            and 0 <= diff < 0.99 and same > diff
            and hashes["reference_wav"] != hashes["altered_wav"]
            and hashes["reference_video"] != hashes["altered_video"]):
        raise HostAvEvidenceError("METRIC_NEGATIVE_CONTROL_FAILED")
    return {
        "schema": "HazewaveObservedHostAVExecution/v1",
        "evidence_state": "EXECUTED",
        "provenance": "LOCAL_LOG_AND_RECEIPT_INTEGRITY_NOT_INDEPENDENT_ATTESTATION",
        "reviewed_repo_sha": reviewed_sha,
        "log_sha256": expected_log_sha256,
        "receipt_sha256": expected_receipt_sha256,
        "source": "OWNED_SYNTHETIC_MEDIA",
        "metrics": {
            "audio_attenuation_db": attenuation,
            "identical_video_ssim": same,
            "altered_video_ssim": diff
        },
        "operations": {
            "audio.qc": "FFMPEG_VOLUMEDETECT",
            "visual.qc": "FFMPEG_SSIM_NOT_FFPROBE_EXECUTION",
        },
        "agent_connected": False,
        "tool_routing_authorized": False,
        "benchmarked": False,
        "production_approved": False,
        "limits": [
            "Owner-provided local execution log, not independent host attestation.",
            "One-second synthetic fixtures are not a professional audio/video benchmark.",
            "No agent MCP tool call, provider routing or production authorization.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify already-produced private AV host evidence")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--reviewed-sha", required=True)
    parser.add_argument("--log-sha256", required=True)
    parser.add_argument("--receipt-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_host_av_evidence(
            log_path=args.log, receipt_path=args.receipt,
            reviewed_sha=args.reviewed_sha,
            expected_log_sha256=args.log_sha256,
            expected_receipt_sha256=args.receipt_sha256
        )
    except HostAvEvidenceError as exc:
        print("HAZEWAVE_HOST_AV_EVIDENCE=BLOCKED:" + str(exc), file=sys.stderr)
        return 20
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
