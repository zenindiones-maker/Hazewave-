from __future__ import annotations

import hashlib
import math
from pathlib import Path

import pytest

from hazewave.audio_qc import AudioQCReport
from hazewave.reference_profile import (
    DecodedPCM,
    ReferenceProfileError,
    build_reference_profile,
)


def _qc(source: Path) -> AudioQCReport:
    return AudioQCReport(
        source_path=str(source.resolve()),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        codec_name="pcm_s24le",
        sample_rate=48000,
        channels=2,
        channel_layout="stereo",
        duration_seconds=1.0,
        integrated_lufs=-16.2,
        integrated_threshold_lufs=-26.0,
        loudness_range_lu=6.5,
        true_peak_dbfs=-1.2,
        sample_peak_dbfs=-1.5,
        rms_dbfs=-18.0,
        dc_offset=0.0,
        crest_factor_ratio=4.2,
        clipping_detected=False,
        technical_flags=(),
    )


def _pcm() -> DecodedPCM:
    sample_rate = 1000
    frames = []
    for index in range(sample_rate):
        t = index / sample_rate
        base = 0.35 * math.sin(2 * math.pi * 40 * t)
        mid = 0.18 * math.sin(2 * math.pi * 180 * t)
        high = 0.05 * math.sin(2 * math.pi * 420 * t)
        transient = 0.5 if index in {250, 500, 750} else 0.0
        left = base + mid + high + transient
        right = base + mid + high + transient * 0.9
        frames.append((left, right))
    return DecodedPCM(
        sample_rate=sample_rate,
        channels=2,
        frames=tuple(frames),
    )


def test_reference_profile_extracts_non_reconstructive_comparison_features(
    tmp_path: Path,
) -> None:
    source = tmp_path / "reference.wav"
    source.write_bytes(b"authorized-reference")

    profile = build_reference_profile(
        source,
        authorized=True,
        audio_qc_analyzer=lambda path: _qc(path),
        pcm_decoder=lambda path: _pcm(),
        section_count=4,
    )

    assert profile.schema == "ReferenceProfile/v1"
    assert profile.source_sha256
    assert profile.authorization == "AUTHORIZED"
    assert profile.artistic_verdict == "NOT_ASSIGNED"
    assert profile.reconstructs_reference_content is False
    assert profile.integrated_lufs == pytest.approx(-16.2)
    assert profile.loudness_range_lu == pytest.approx(6.5)
    assert profile.true_peak_dbfs == pytest.approx(-1.2)
    assert profile.crest_factor_ratio == pytest.approx(4.2)

    total = (
        profile.low_energy_ratio
        + profile.mid_energy_ratio
        + profile.high_energy_ratio
    )
    assert total == pytest.approx(1.0, abs=1e-6)
    assert 0.0 <= profile.stereo_correlation <= 1.0
    assert profile.transient_density_per_second >= 0.0
    assert len(profile.section_energy_dbfs) == 4
    assert profile.feature_method == "LOCAL_PCM_HEURISTIC_V1"


def test_reference_profile_refuses_unauthorized_reference_before_analysis(
    tmp_path: Path,
) -> None:
    source = tmp_path / "reference.wav"
    source.write_bytes(b"reference")
    calls = {"qc": 0, "pcm": 0}

    def qc(path: Path):
        calls["qc"] += 1
        return _qc(path)

    def pcm(path: Path):
        calls["pcm"] += 1
        return _pcm()

    with pytest.raises(ReferenceProfileError, match="REFERENCE_NOT_AUTHORIZED"):
        build_reference_profile(
            source,
            authorized=False,
            audio_qc_analyzer=qc,
            pcm_decoder=pcm,
        )

    assert calls == {"qc": 0, "pcm": 0}


def test_reference_profile_fails_closed_when_audio_qc_source_hash_does_not_match(
    tmp_path: Path,
) -> None:
    source = tmp_path / "reference.wav"
    source.write_bytes(b"reference")

    bad_qc = _qc(source)
    object.__setattr__(bad_qc, "source_sha256", "0" * 64)

    with pytest.raises(
        ReferenceProfileError,
        match="REFERENCE_AUDIO_QC_SOURCE_HASH_MISMATCH",
    ):
        build_reference_profile(
            source,
            authorized=True,
            audio_qc_analyzer=lambda path: bad_qc,
            pcm_decoder=lambda path: _pcm(),
        )


def test_reference_profile_requires_stereo_or_mono_pcm_consistent_frames(
    tmp_path: Path,
) -> None:
    source = tmp_path / "reference.wav"
    source.write_bytes(b"reference")

    malformed = DecodedPCM(
        sample_rate=1000,
        channels=2,
        frames=((0.1,), (0.2, 0.2)),
    )

    with pytest.raises(ReferenceProfileError, match="REFERENCE_PCM_MALFORMED"):
        build_reference_profile(
            source,
            authorized=True,
            audio_qc_analyzer=lambda path: _qc(path),
            pcm_decoder=lambda path: malformed,
        )


def test_reference_profile_section_count_is_bounded(tmp_path: Path) -> None:
    source = tmp_path / "reference.wav"
    source.write_bytes(b"reference")

    with pytest.raises(ReferenceProfileError, match="REFERENCE_SECTION_COUNT_INVALID"):
        build_reference_profile(
            source,
            authorized=True,
            audio_qc_analyzer=lambda path: _qc(path),
            pcm_decoder=lambda path: _pcm(),
            section_count=129,
        )
