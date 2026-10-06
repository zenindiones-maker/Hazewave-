from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hazewave.video_qc import (
    VideoQCError,
    analyze_video_qc,
    parse_reference_quality_metrics,
)


def _payload(*, video_duration: str = "10.0", audio_duration: str = "10.0") -> dict:
    return {
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": "10.0",
        },
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "avg_frame_rate": "30000/1001",
                "color_range": "tv",
                "color_space": "bt709",
                "color_transfer": "bt709",
                "color_primaries": "bt709",
                "bits_per_raw_sample": "8",
                "duration": video_duration,
            },
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
                "channel_layout": "stereo",
                "duration": audio_duration,
            },
        ],
    }


def test_video_qc_report_captures_encode_and_av_integrity(tmp_path: Path) -> None:
    output = tmp_path / "delivery.mp4"
    output.write_bytes(b"encoded-fixture")

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args, 0, stdout=json.dumps(_payload()), stderr=""
        )

    report = analyze_video_qc(output, runner=runner)

    assert report.schema == "VideoQCReport/v1"
    assert report.output_path == str(output.resolve())
    assert len(report.output_sha256) == 64
    assert report.container_format.startswith("mov")
    assert report.video_codec == "h264"
    assert report.width == 1920
    assert report.height == 1080
    assert report.pixel_format == "yuv420p"
    assert report.frame_rate_numerator == 30000
    assert report.frame_rate_denominator == 1001
    assert report.color_primaries == "bt709"
    assert report.color_transfer == "bt709"
    assert report.color_matrix == "bt709"
    assert report.color_range == "tv"
    assert report.bit_depth == 8
    assert report.audio_stream_count == 1
    assert report.av_duration_delta_seconds == pytest.approx(0.0)
    assert report.encode_integrity == "PASS"
    assert report.technical_flags == ()
    assert report.artistic_verdict == "NOT_ASSIGNED"


def test_video_qc_flags_av_duration_mismatch_without_artistic_judgment(
    tmp_path: Path,
) -> None:
    output = tmp_path / "mismatch.mp4"
    output.write_bytes(b"encoded-fixture")

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps(_payload(video_duration="10.0", audio_duration="9.2")),
            stderr="",
        )

    report = analyze_video_qc(
        output,
        runner=runner,
        av_duration_tolerance_seconds=0.1,
    )

    assert report.av_duration_delta_seconds == pytest.approx(0.8)
    assert "AV_DURATION_MISMATCH" in report.technical_flags
    assert report.artistic_verdict == "NOT_ASSIGNED"


def test_video_qc_flags_ambiguous_color_metadata(tmp_path: Path) -> None:
    output = tmp_path / "unknown-color.mp4"
    output.write_bytes(b"encoded-fixture")
    payload = _payload()
    payload["streams"][0]["color_primaries"] = "unknown"
    payload["streams"][0]["color_transfer"] = "unknown"

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

    report = analyze_video_qc(output, runner=runner)

    assert "COLOR_METADATA_AMBIGUOUS" in report.technical_flags


def test_video_qc_fails_closed_without_video_stream(tmp_path: Path) -> None:
    output = tmp_path / "audio.m4a"
    output.write_bytes(b"audio")
    payload = _payload()
    payload["streams"] = [payload["streams"][1]]

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

    with pytest.raises(VideoQCError, match="VIDEO_QC_VIDEO_STREAM_REQUIRED"):
        analyze_video_qc(output, runner=runner)


def test_reference_quality_parser_keeps_metrics_technical_not_artistic() -> None:
    log = """
    [libvmaf @ 0x1] VMAF score: 96.321000
    [Parsed_ssim_1 @ 0x2] SSIM Y:0.991 U:0.995 V:0.996 All:0.992345 (20.123456)
    [Parsed_psnr_2 @ 0x3] PSNR y:43.20 u:44.10 v:44.30 average:43.55 min:40.0 max:48.0
    """

    result = parse_reference_quality_metrics(log)

    assert result["schema"] == "ReferenceVideoQualityReport/v1"
    assert result["vmaf"] == pytest.approx(96.321)
    assert result["ssim"] == pytest.approx(0.992345)
    assert result["psnr_db"] == pytest.approx(43.55)
    assert result["interpretation"] == "TECHNICAL_FIDELITY_ONLY"
    assert result["artistic_verdict"] == "NOT_ASSIGNED"


def test_reference_quality_parser_requires_at_least_one_metric() -> None:
    with pytest.raises(VideoQCError, match="VIDEO_QC_REFERENCE_METRICS_MISSING"):
        parse_reference_quality_metrics("no metrics here")
