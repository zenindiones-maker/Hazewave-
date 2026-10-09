"""Fail-closed HAZE producer qualification over two *real* audio renders.

This is an isolated technical listening prerequisite, not a DAW operator,
a surrogate human listener, a machine-learning trainer or a runtime admission.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Final, Sequence

from hazewave.audio_qc import AudioQCReport, analyze_audio_qc


class ProducerQualificationError(RuntimeError):
    pass


_CANDIDATES: Final[tuple[dict[str, str], ...]] = (
    {"id":"xdarkzx-reapermcp","kind":"REAPER_MCP_AGENT",
     "upstream":"https://github.com/xDarkzx/Reaper-MCP",
     "revision":"1c9863c4e722673e9629518d8dfb85e10e2db6d6",
     "license":"Apache-2.0"},
    {"id":"mthines-reaper-mcp","kind":"REAPER_MCP_AGENT",
     "upstream":"https://github.com/mthines/reaper-mcp",
     "revision":"4a01d1efe7b3b165e2354153445d515a101caf46",
     "license":"MIT"},
    {"id":"danielkinahan-reamcp","kind":"REAPER_MCP_AGENT",
     "upstream":"https://github.com/danielkinahan/ReaMCP",
     "revision":"670dda408e6e297102a9d87276ab9d6a685eb004",
     "license":"GPL-3.0"},
    {"id":"ace-step-1.5","kind":"GENERATIVE_MUSIC_ENGINE",
     "upstream":"https://github.com/ace-step/ACE-Step-1.5",
     "revision":"ca1e85fe9430179831e6bc6be790c332190a3866",
     "license":"MIT"},
)


def candidate_inventory() -> list[dict[str, Any]]:
    return [{**entry,"admission":"DISCOVERY_ONLY","production_approved":False,
             "paid_fallback_permitted":False,"runtime_proven":False,
             "can_read_private_files":False} for entry in _CANDIDATES]


def admit_candidate_tool_surface(
    *,candidate_id: str,requested_operations: Sequence[str],
    expected_upstream_sha256: str | None = None
) -> dict[str, Any]:
    match=next((x for x in _CANDIDATES if x["id"]==candidate_id),None)
    if match is None:
        raise ProducerQualificationError("CANDIDATE_NOT_REVIEWED")
    if expected_upstream_sha256 is not None and not re.fullmatch(
        r"[a-f0-9]{40}",expected_upstream_sha256
    ):
        raise ProducerQualificationError("CANDIDATE_SHA_REQUIRED")
    if expected_upstream_sha256 is not None and expected_upstream_sha256!=match["revision"]:
        raise ProducerQualificationError("CANDIDATE_SHA_MISMATCH")
    if not isinstance(requested_operations,(list,tuple)) or any(
        op not in {"session.inspect","fx.inventory","fx.parameter.read"}
        for op in requested_operations
    ):
        raise ProducerQualificationError("CANDIDATE_OPERATION_FORBIDDEN")
    return {"schema":"HazeExternalAgentCandidateAdmission/v1",
            "candidate_id":candidate_id,"upstream_ref":match["revision"],
            "requested_operations":list(requested_operations),
            "decision":"CATALOG_ONLY","allowed_runtime_operations":[],
            "can_mutate_reaper":False,"can_start_server":False,
            "can_read_private_files":False,"authority":"HAZEWAVE_HARNESS",
            "runtime_proven":False,"production_approved":False}


def _under_owned_root(root: Path, raw: str | Path) -> Path:
    path=Path(raw).expanduser().resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ProducerQualificationError("UNOWNED_RENDER_PATH") from exc
    if not path.is_file() or path.suffix.casefold() not in {".wav",".flac"}:
        raise ProducerQualificationError("RENDER_MUST_BE_OWNED_LOSSLESS_AUDIO")
    return path


def _digest(path: Path, expected: str) -> str:
    if not isinstance(expected,str) or re.fullmatch(r"[a-f0-9]{64}",expected) is None:
        raise ProducerQualificationError("AUDIO_DIGEST_INVALID")
    d=sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):
            d.update(chunk)
    actual=d.hexdigest()
    if actual!=expected:
        raise ProducerQualificationError("AUDIO_DIGEST_MISMATCH")
    return actual


def _report(report: AudioQCReport) -> dict[str, Any]:
    return {"sha256":report.source_sha256,
            "sample_rate":report.sample_rate,"channels":report.channels,
            "duration_seconds":report.duration_seconds,
            "integrated_lufs":report.integrated_lufs,
            "true_peak_dbfs":report.true_peak_dbfs,
            "sample_peak_dbfs":report.sample_peak_dbfs,
            "dc_offset":report.dc_offset,
            "clipping_detected":report.clipping_detected,
            "technical_flags":list(report.technical_flags)}


def evaluate_producer_render_pair(
    *,fixture_root: Path | str,reference:Path | str,candidate:Path | str,
    reference_sha256:str,candidate_sha256:str,intent:str
) -> dict[str, Any]:
    """Measure a bounded local A/B. Never mutate audio or grant DAW authorization."""
    if intent!="REMOVE_DC_OFFSET":
        raise ProducerQualificationError("PRODUCER_INTENT_NOT_QUALIFIED")
    root=Path(fixture_root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ProducerQualificationError("FIXTURE_ROOT_INVALID")
    before=_under_owned_root(root,reference)
    after=_under_owned_root(root,candidate)
    if before==after:
        raise ProducerQualificationError("DISTINCT_RENDER_REQUIRED")
    bh=_digest(before,reference_sha256)
    ah=_digest(after,candidate_sha256)
    if bh==ah:
        raise ProducerQualificationError("DISTINCT_RENDER_REQUIRED")
    before_qc=analyze_audio_qc(before)
    after_qc=analyze_audio_qc(after)
    failures=[]
    if before_qc.sample_rate!=after_qc.sample_rate or before_qc.channels!=after_qc.channels:
        failures.append("SIGNAL_FORMAT_CHANGED")
    if abs(before_qc.duration_seconds-after_qc.duration_seconds)>0.05:
        failures.append("DURATION_CHANGED")
    if abs(after_qc.dc_offset)>0.005:
        failures.append("DC_OFFSET_NOT_CORRECTED")
    if abs(after_qc.dc_offset)>=abs(before_qc.dc_offset)*0.2:
        failures.append("DC_OFFSET_REDUCTION_INSUFFICIENT")
    if after_qc.clipping_detected:
        failures.append("CANDIDATE_CLIPPING")
    if after_qc.true_peak_dbfs>before_qc.true_peak_dbfs+1.0:
        failures.append("UNEXPECTED_TRUE_PEAK_INCREASE")
    return {"schema":"HazeProducerMeasuredAB/v1",
            "intent":intent,
            "measurement_engine":"FFMPEG_EBUR128_AND_ASTATS",
            "before":_report(before_qc),"after":_report(after_qc),
            "qc_failures":failures,
            "technical_result":"REJECTED_BY_QC" if failures else "TARGETED_QC_IMPROVEMENT",
            "music_quality_judgement":"HUMAN_LISTENING_NOT_PERFORMED",
            "reaper_runtime_proven":False,
            "mix_master_competence_proven":False,
            "production_approved":False,
            "action_executed":False,
            "human_review_required":True,
            "training_authorized":False,
            "private_audio_exported":False}
