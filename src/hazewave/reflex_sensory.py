from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from typing import Any, Mapping

from hazewave.animation_qc import AnimationQCReport
from hazewave.audio_analysis import ProfessionalAudioAnalysisReport
from hazewave.audio_qc import AudioQCReport
from hazewave.video_qc import VideoQCReport


class ReflexSensoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReflexSensoryFrame:
    frame_digest: str
    signals: dict[str, Any]
    raw_media_included: bool = False
    source_paths_included: bool = False
    artistic_verdict_included: bool = False
    state_language: str = "en"
    schema: str = "HazewaveReflexSensoryFrame/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "frame_digest": self.frame_digest,
            "state_language": self.state_language,
            "raw_media_included": self.raw_media_included,
            "source_paths_included": self.source_paths_included,
            "artistic_verdict_included": self.artistic_verdict_included,
            "signals": self.signals,
        }

    def model_state(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "state_language": self.state_language,
            "signals": self.signals,
        }


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _finite(value: Any, *, field: str) -> float:
    if not isinstance(value, (int, float)):
        raise ReflexSensoryError(f"REFLEX_SENSORY_NUMERIC_INVALID:{field}")
    result = float(value)
    if not math.isfinite(result):
        raise ReflexSensoryError(f"REFLEX_SENSORY_NUMERIC_INVALID:{field}")
    return result


def _flags(values: Any, *, max_flags: int = 32) -> list[str]:
    if not isinstance(values, (tuple, list)):
        raise ReflexSensoryError("REFLEX_SENSORY_FLAGS_INVALID")
    result = sorted({str(value).strip() for value in values if str(value).strip()})
    if len(result) > max_flags:
        raise ReflexSensoryError("REFLEX_SENSORY_TOO_MANY_FLAGS")
    return result


def _audio_qc(report: AudioQCReport) -> dict[str, Any]:
    if report.schema != "AudioQCReport/v1":
        raise ReflexSensoryError("REFLEX_SENSORY_AUDIO_QC_SCHEMA_INVALID")
    return {
        "schema": report.schema,
        "integrated_lufs": _finite(report.integrated_lufs, field="integrated_lufs"),
        "momentary_max_lufs": None if report.momentary_max_lufs is None else _finite(report.momentary_max_lufs, field="momentary_max_lufs"),
        "short_term_max_lufs": None if report.short_term_max_lufs is None else _finite(report.short_term_max_lufs, field="short_term_max_lufs"),
        "loudness_range_lu": _finite(report.loudness_range_lu, field="loudness_range_lu"),
        "true_peak_dbfs": _finite(report.true_peak_dbfs, field="true_peak_dbfs"),
        "sample_peak_dbfs": _finite(report.sample_peak_dbfs, field="sample_peak_dbfs"),
        "rms_dbfs": _finite(report.rms_dbfs, field="rms_dbfs"),
        "dc_offset": _finite(report.dc_offset, field="dc_offset"),
        "crest_factor_ratio": _finite(report.crest_factor_ratio, field="crest_factor_ratio"),
        "clipping_detected": bool(report.clipping_detected),
        "technical_flags": _flags(report.technical_flags),
        "sample_rate": int(report.sample_rate),
        "channels": int(report.channels),
        "duration_seconds": _finite(report.duration_seconds, field="audio_duration_seconds"),
    }


def _audio_analysis(report: ProfessionalAudioAnalysisReport) -> dict[str, Any]:
    if report.schema != "ProfessionalAudioAnalysisReport/v1":
        raise ReflexSensoryError("REFLEX_SENSORY_AUDIO_ANALYSIS_SCHEMA_INVALID")
    return {
        "schema": report.schema,
        "integrated_lufs": _finite(report.integrated_lufs, field="analysis_integrated_lufs"),
        "true_peak_dbfs": _finite(report.true_peak_dbfs, field="analysis_true_peak_dbfs"),
        "crest_factor_ratio": _finite(report.crest_factor_ratio, field="analysis_crest_factor"),
        "stereo_correlation": _finite(report.stereo_correlation, field="stereo_correlation"),
        "stereo_side_energy_ratio": _finite(report.stereo_side_energy_ratio, field="stereo_side_energy_ratio"),
        "stereo_balance_db": _finite(report.stereo_balance_db, field="stereo_balance_db"),
        "low_energy_ratio": _finite(report.low_energy_ratio, field="low_energy_ratio"),
        "mid_energy_ratio": _finite(report.mid_energy_ratio, field="mid_energy_ratio"),
        "high_energy_ratio": _finite(report.high_energy_ratio, field="high_energy_ratio"),
        "transient_density_per_second": _finite(report.transient_density_per_second, field="transient_density"),
        "tempo_bpm": _finite(report.tempo_bpm, field="tempo_bpm"),
        "tempo_confidence": _finite(report.tempo_confidence, field="tempo_confidence"),
        "beat_count": int(report.beat_count),
        "onset_count": int(report.onset_count),
        "key": str(report.key),
        "scale": str(report.scale),
        "key_strength": _finite(report.key_strength, field="key_strength"),
        "structure_status": str(report.structure_status),
        "rejected_section_count": int(report.rejected_section_count),
        "analysis_engine": str(report.analysis_engine),
        "analysis_engine_version": str(report.analysis_engine_version),
    }


def _video_qc(report: VideoQCReport) -> dict[str, Any]:
    if report.schema != "VideoQCReport/v1":
        raise ReflexSensoryError("REFLEX_SENSORY_VIDEO_QC_SCHEMA_INVALID")
    fps = report.frame_rate_numerator / report.frame_rate_denominator
    quality: dict[str, Any] | None = None
    if report.reference_quality is not None:
        quality = {
            key: report.reference_quality.get(key)
            for key in ("vmaf", "ssim", "psnr_db")
            if key in report.reference_quality
        }
    return {
        "schema": report.schema,
        "duration_seconds": _finite(report.duration_seconds, field="video_duration_seconds"),
        "width": int(report.width),
        "height": int(report.height),
        "fps": _finite(fps, field="fps"),
        "pixel_format": str(report.pixel_format),
        "color_primaries": str(report.color_primaries),
        "color_transfer": str(report.color_transfer),
        "color_matrix": str(report.color_matrix),
        "color_range": str(report.color_range),
        "bit_depth": int(report.bit_depth),
        "audio_stream_count": int(report.audio_stream_count),
        "av_duration_delta_seconds": _finite(report.av_duration_delta_seconds, field="av_duration_delta"),
        "encode_integrity": str(report.encode_integrity),
        "visual_anomaly_count": int(report.visual_anomaly_count),
        "black_duration_seconds": _finite(report.black_duration_seconds, field="black_duration_seconds"),
        "freeze_duration_seconds": _finite(report.freeze_duration_seconds, field="freeze_duration_seconds"),
        "technical_flags": _flags(report.technical_flags),
        "reference_quality": quality,
    }


def _animation_qc(report: AnimationQCReport) -> dict[str, Any]:
    if report.schema != "AnimationQCReport/v1":
        raise ReflexSensoryError("REFLEX_SENSORY_ANIMATION_QC_SCHEMA_INVALID")
    return {
        "schema": report.schema,
        "frame_start": int(report.frame_start),
        "frame_end": int(report.frame_end),
        "frame_count": int(report.frame_count),
        "width": int(report.width),
        "height": int(report.height),
        "bit_depth": int(report.bit_depth),
        "alpha_channel_present": bool(report.alpha_channel_present),
        "missing_frame_count": len(report.missing_frames),
        "empty_frame_count": len(report.empty_frames),
        "technical_status": str(report.technical_status),
    }


def _runtime_metrics(values: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {"available_ram_gb", "disk_free_gb", "cpu_load_1", "active_render_jobs"}
    extras = set(values) - allowed
    if extras:
        raise ReflexSensoryError("REFLEX_SENSORY_RUNTIME_METRIC_NOT_ALLOWED")
    result: dict[str, Any] = {}
    for key, raw in values.items():
        if key == "active_render_jobs":
            if not isinstance(raw, int) or raw < 0:
                raise ReflexSensoryError("REFLEX_SENSORY_RUNTIME_METRIC_INVALID")
            result[key] = raw
        else:
            value = _finite(raw, field=key)
            if value < 0:
                raise ReflexSensoryError("REFLEX_SENSORY_RUNTIME_METRIC_INVALID")
            result[key] = value
    return result


def build_reflex_sensory_frame(
    *,
    audio_qc: AudioQCReport | None = None,
    audio_analysis: ProfessionalAudioAnalysisReport | None = None,
    video_qc: VideoQCReport | None = None,
    animation_qc: AnimationQCReport | None = None,
    runtime_metrics: Mapping[str, Any] | None = None,
) -> ReflexSensoryFrame:
    signals: dict[str, Any] = {}
    if audio_qc is not None:
        signals["audio_qc"] = _audio_qc(audio_qc)
    if audio_analysis is not None:
        signals["audio_analysis"] = _audio_analysis(audio_analysis)
    if video_qc is not None:
        signals["video_qc"] = _video_qc(video_qc)
    if animation_qc is not None:
        signals["animation_qc"] = _animation_qc(animation_qc)
    if runtime_metrics is not None:
        signals["runtime"] = _runtime_metrics(runtime_metrics)
    if not signals:
        raise ReflexSensoryError("REFLEX_SENSORY_NO_SIGNALS")

    # Explicitly serialized sanitized signals only. Source paths, media bytes,
    # creative/artistic verdicts and credentials never enter this frame.
    encoded = _canonical(signals)
    if len(encoded) > 64_000:
        raise ReflexSensoryError("REFLEX_SENSORY_FRAME_TOO_LARGE")
    forbidden_keys = {
        "source_path", "output_path", "path", "frames", "source_sha256",
        "output_sha256", "artistic_verdict", "creative_verdict", "api_key",
        "token", "secret", "raw_media",
    }
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).casefold() in forbidden_keys:
                    raise ReflexSensoryError("REFLEX_SENSORY_FORBIDDEN_FIELD")
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(signals)

    return ReflexSensoryFrame(
        frame_digest=sha256(encoded).hexdigest(),
        signals=signals,
    )
