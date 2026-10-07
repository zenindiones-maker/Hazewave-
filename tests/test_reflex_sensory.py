from __future__ import annotations

import json

import pytest

from hazewave.animation_qc import AnimationQCReport
from hazewave.audio_qc import AudioQCReport
from hazewave.reflex_sensory import ReflexSensoryError, build_reflex_sensory_frame
from hazewave.video_qc import VideoQCReport


def _audio() -> AudioQCReport:
    return AudioQCReport(
        source_path="/private/mix.wav",
        source_sha256="a" * 64,
        codec_name="pcm_s24le",
        sample_rate=48000,
        channels=2,
        channel_layout="stereo",
        duration_seconds=60.0,
        integrated_lufs=-14.0,
        integrated_threshold_lufs=-24.0,
        loudness_range_lu=7.0,
        true_peak_dbfs=-1.1,
        sample_peak_dbfs=-1.3,
        rms_dbfs=-18.0,
        dc_offset=0.0001,
        crest_factor_ratio=8.0,
        clipping_detected=False,
        technical_flags=("LOUDNESS_OK",),
        momentary_max_lufs=-10.0,
        short_term_max_lufs=-12.0,
        loudness_timeseries_frames=100,
    )


def _video() -> VideoQCReport:
    return VideoQCReport(
        output_path="/private/final.mp4",
        output_sha256="b" * 64,
        container_format="mp4",
        duration_seconds=60.0,
        video_codec="h264",
        width=1920,
        height=1080,
        pixel_format="yuv420p",
        frame_rate_numerator=30,
        frame_rate_denominator=1,
        color_primaries="bt709",
        color_transfer="bt709",
        color_matrix="bt709",
        color_range="tv",
        bit_depth=8,
        audio_stream_count=1,
        av_duration_delta_seconds=0.02,
        encode_integrity="PASS",
        technical_flags=("FROZEN_INTERVALS_DETECTED",),
        black_duration_seconds=0.0,
        freeze_duration_seconds=2.0,
        visual_anomaly_count=1,
        reference_quality={"vmaf": 96.2, "ssim": 0.99, "psnr_db": 43.0, "artistic_verdict": "NOT_ASSIGNED"},
    )


def _animation() -> AnimationQCReport:
    return AnimationQCReport(
        frame_start=1,
        frame_end=10,
        frame_count=10,
        width=1920,
        height=1080,
        bit_depth=8,
        alpha_channel_present=False,
        frames=(),
        missing_frames=(),
        empty_frames=(),
        sequence_sha256="c" * 64,
    )


def test_sensory_frame_excludes_paths_hashes_raw_media_and_artistic_verdicts() -> None:
    frame = build_reflex_sensory_frame(
        audio_qc=_audio(),
        video_qc=_video(),
        animation_qc=_animation(),
        runtime_metrics={
            "available_ram_gb": 4.5,
            "disk_free_gb": 18.0,
            "cpu_load_1": 0.7,
            "active_render_jobs": 0,
        },
    )
    payload = frame.to_dict()
    encoded = json.dumps(payload, sort_keys=True)

    assert payload["raw_media_included"] is False
    assert payload["source_paths_included"] is False
    assert payload["artistic_verdict_included"] is False
    assert len(payload["frame_digest"]) == 64
    assert "/private/" not in encoded
    assert "source_path" not in encoded
    assert "output_path" not in encoded
    assert '"raw_media"' not in encoded
    assert "artistic_verdict" not in json.dumps(payload["signals"])
    assert payload["signals"]["audio_qc"]["integrated_lufs"] == pytest.approx(-14.0)
    assert payload["signals"]["video_qc"]["visual_anomaly_count"] == 1
    assert payload["signals"]["animation_qc"]["frame_count"] == 10


def test_sensory_frame_is_deterministic_for_same_signals() -> None:
    first = build_reflex_sensory_frame(audio_qc=_audio())
    second = build_reflex_sensory_frame(audio_qc=_audio())
    assert first.frame_digest == second.frame_digest
    assert first.model_state() == second.model_state()


def test_sensory_frame_rejects_unknown_runtime_metrics() -> None:
    with pytest.raises(ReflexSensoryError, match="RUNTIME_METRIC_NOT_ALLOWED"):
        build_reflex_sensory_frame(
            audio_qc=_audio(),
            runtime_metrics={"hostname": "codespace"},
        )


def test_sensory_frame_requires_at_least_one_deterministic_signal() -> None:
    with pytest.raises(ReflexSensoryError, match="NO_SIGNALS"):
        build_reflex_sensory_frame()
