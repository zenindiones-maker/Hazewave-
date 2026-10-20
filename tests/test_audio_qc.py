from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hazewave.audio_qc import (
    AudioQCError,
    analyze_audio_qc,
    parse_astats_summary,
    parse_ebur128_summary,
    parse_ebur128_timeseries,
)


EBUR128_LOG = """
[Parsed_ebur128_0 @ 0x1] t: 0.099979 TARGET:-23 LUFS M:-20.1 S:-23.5 I:-30.0 LUFS LRA:0.0 LU
[Parsed_ebur128_0 @ 0x1] t: 0.199979 TARGET:-23 LUFS M:-18.7 S:-22.2 I:-28.0 LUFS LRA:0.0 LU
[Parsed_ebur128_0 @ 0x1] t: 0.299979 TARGET:-23 LUFS M:-19.3 S:-21.8 I:-26.0 LUFS LRA:0.0 LU
[Parsed_ebur128_0 @ 0x1] Summary:

  Integrated loudness:
    I:         -14.2 LUFS
    Threshold: -24.3 LUFS

  Loudness range:
    LRA:         5.8 LU
    Threshold: -34.1 LUFS
    LRA low:   -17.9 LUFS
    LRA high:  -12.1 LUFS

  True peak:
    Peak:       -0.7 dBFS
"""

ASTATS_LOG = """
[Parsed_astats_0 @ 0x2] Overall
[Parsed_astats_0 @ 0x2] DC offset: 0.000231
[Parsed_astats_0 @ 0x2] Min level: -0.92
[Parsed_astats_0 @ 0x2] Max level: 0.91
[Parsed_astats_0 @ 0x2] Peak level dB: -0.82
[Parsed_astats_0 @ 0x2] RMS level dB: -16.40
[Parsed_astats_0 @ 0x2] Crest factor: 6.01
"""


def test_parse_ebur128_summary_extracts_program_measurements() -> None:
    values = parse_ebur128_summary(EBUR128_LOG)

    assert values["integrated_lufs"] == pytest.approx(-14.2)
    assert values["loudness_range_lu"] == pytest.approx(5.8)
    assert values["true_peak_dbfs"] == pytest.approx(-0.7)
    assert values["integrated_threshold_lufs"] == pytest.approx(-24.3)


def test_parse_astats_summary_uses_overall_program_values() -> None:
    values = parse_astats_summary(ASTATS_LOG)

    assert values["dc_offset"] == pytest.approx(0.000231)
    assert values["sample_peak_dbfs"] == pytest.approx(-0.82)
    assert values["rms_dbfs"] == pytest.approx(-16.40)
    assert values["crest_factor_ratio"] == pytest.approx(6.01)




def test_parse_astats_real_ffmpeg_overall_without_crest_factor() -> None:
    """FFmpeg documents Crest_factor per-channel, not Overall."""
    log = ASTATS_LOG.replace("[Parsed_astats_0 @ 0x2] Crest factor: 6.01", "")
    metrics = parse_astats_summary(log)
    assert metrics["sample_peak_dbfs"] == pytest.approx(-0.82)
    assert metrics["rms_dbfs"] == pytest.approx(-16.40)
    assert metrics["crest_factor_ratio"] == pytest.approx(10 ** ((-0.82 + 16.40) / 20.0))


def test_audio_qc_runs_ffprobe_ebur128_and_astats_without_artistic_target(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mix.wav"
    source.write_bytes(b"fixture")
    calls: list[list[str]] = []

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[0] == "ffprobe":
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=json.dumps(
                    {
                        "streams": [
                            {
                                "codec_name": "pcm_s24le",
                                "sample_rate": "48000",
                                "channels": 2,
                                "channel_layout": "stereo",
                            }
                        ],
                        "format": {"duration": "12.500000"},
                    }
                ),
                stderr="",
            )
        if any(value.startswith("ebur128=peak=true") for value in args):
            return subprocess.CompletedProcess(args, 0, stdout="", stderr=EBUR128_LOG)
        if any("astats=" in value for value in args):
            return subprocess.CompletedProcess(args, 0, stdout="", stderr=ASTATS_LOG)
        raise AssertionError(args)

    report = analyze_audio_qc(source, runner=runner)

    assert report.schema == "AudioQCReport/v1"
    assert report.integrated_lufs == pytest.approx(-14.2)
    assert report.loudness_range_lu == pytest.approx(5.8)
    assert report.true_peak_dbfs == pytest.approx(-0.7)
    assert report.sample_peak_dbfs == pytest.approx(-0.82)
    assert report.dc_offset == pytest.approx(0.000231)
    assert report.crest_factor_ratio == pytest.approx(6.01)
    assert report.sample_rate == 48000
    assert report.channels == 2
    assert report.duration_seconds == pytest.approx(12.5)
    assert report.delivery_profile is None
    assert report.artistic_verdict == "NOT_ASSIGNED"
    assert report.clipping_detected is False

    assert calls[0][0] == "ffprobe"
    assert "ebur128=peak=true:framelog=info" in calls[1]
    assert any("astats=" in value for value in calls[2])


def test_audio_qc_flags_clipping_as_technical_evidence_not_artistic_failure(
    tmp_path: Path,
) -> None:
    source = tmp_path / "clip.wav"
    source.write_bytes(b"fixture")

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[0] == "ffprobe":
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=json.dumps(
                    {
                        "streams": [
                            {
                                "codec_name": "pcm_s16le",
                                "sample_rate": "48000",
                                "channels": 2,
                                "channel_layout": "stereo",
                            }
                        ],
                        "format": {"duration": "1.0"},
                    }
                ),
                stderr="",
            )
        if any(value.startswith("ebur128=peak=true") for value in args):
            return subprocess.CompletedProcess(
                args,
                0,
                stdout="",
                stderr=EBUR128_LOG.replace("-0.7 dBFS", "0.3 dBFS"),
            )
        return subprocess.CompletedProcess(
            args,
            0,
            stdout="",
            stderr=ASTATS_LOG.replace("-0.82", "0.10"),
        )

    report = analyze_audio_qc(source, runner=runner)

    assert report.clipping_detected is True
    assert report.artistic_verdict == "NOT_ASSIGNED"


def test_audio_qc_fails_closed_when_ffprobe_has_no_audio_stream(tmp_path: Path) -> None:
    source = tmp_path / "video-only.mp4"
    source.write_bytes(b"fixture")

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps({"streams": [], "format": {"duration": "4.0"}}),
            stderr="",
        )

    with pytest.raises(AudioQCError, match="AUDIO_QC_NO_AUDIO_STREAM"):
        analyze_audio_qc(source, runner=runner)


def test_audio_qc_fails_closed_on_unparseable_loudness_output(tmp_path: Path) -> None:
    source = tmp_path / "bad.wav"
    source.write_bytes(b"fixture")

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[0] == "ffprobe":
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=json.dumps(
                    {
                        "streams": [
                            {
                                "codec_name": "pcm_s16le",
                                "sample_rate": "48000",
                                "channels": 1,
                                "channel_layout": "mono",
                            }
                        ],
                        "format": {"duration": "1.0"},
                    }
                ),
                stderr="",
            )
        if any(value.startswith("ebur128=peak=true") for value in args):
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="no summary")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr=ASTATS_LOG)

    with pytest.raises(AudioQCError, match="AUDIO_QC_EBUR128_MALFORMED"):
        analyze_audio_qc(source, runner=runner)


def test_parse_ebur128_timeseries_extracts_momentary_and_short_term_maxima() -> None:
    values = parse_ebur128_timeseries(EBUR128_LOG)

    assert values["momentary_max_lufs"] == pytest.approx(-18.7)
    assert values["short_term_max_lufs"] == pytest.approx(-21.8)
    assert values["frame_count"] == 3


def test_audio_qc_report_includes_momentary_and_short_term_loudness(tmp_path: Path) -> None:
    source = tmp_path / "mix.wav"
    source.write_bytes(b"fixture")

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[0] == "ffprobe":
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=json.dumps(
                    {
                        "streams": [
                            {
                                "codec_name": "pcm_s24le",
                                "sample_rate": "48000",
                                "channels": 2,
                                "channel_layout": "stereo",
                            }
                        ],
                        "format": {"duration": "12.5"},
                    }
                ),
                stderr="",
            )
        if any("ebur128=" in value for value in args):
            return subprocess.CompletedProcess(args, 0, stdout="", stderr=EBUR128_LOG)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr=ASTATS_LOG)

    report = analyze_audio_qc(source, runner=runner)

    assert report.momentary_max_lufs == pytest.approx(-18.7)
    assert report.short_term_max_lufs == pytest.approx(-21.8)
    assert report.loudness_timeseries_frames == 3
