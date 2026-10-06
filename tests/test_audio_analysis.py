from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from hazewave.audio_analysis import (
    AudioAnalysisError,
    AudioSectionEstimate,
    MusicAnalysisResult,
    ProfessionalAudioAnalysisReport,
    analyze_professional_audio,
)
from hazewave.audio_qc import AudioQCReport
from hazewave.reference_profile import DecodedPCM


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _qc(path: Path) -> AudioQCReport:
    return AudioQCReport(
        source_path=str(path.resolve()),
        source_sha256=_sha(path),
        codec_name="pcm_s24le",
        sample_rate=48000,
        channels=2,
        channel_layout="stereo",
        duration_seconds=4.0,
        integrated_lufs=-15.0,
        integrated_threshold_lufs=-25.0,
        loudness_range_lu=6.0,
        true_peak_dbfs=-1.0,
        sample_peak_dbfs=-1.2,
        rms_dbfs=-18.0,
        dc_offset=0.0001,
        crest_factor_ratio=7.0,
        clipping_detected=False,
        technical_flags=(),
        momentary_max_lufs=-12.5,
        short_term_max_lufs=-14.1,
        loudness_timeseries_frames=40,
    )


def _pcm(_path: Path) -> DecodedPCM:
    frames = tuple(
        (
            0.45 * ((index % 11) / 10.0 - 0.5),
            0.30 * ((index % 7) / 6.0 - 0.5),
        )
        for index in range(4800)
    )
    return DecodedPCM(
        sample_rate=12000,
        channels=2,
        frames=frames,
    )


def _music(_path: Path) -> MusicAnalysisResult:
    return MusicAnalysisResult(
        engine="Essentia",
        engine_version="2.1-beta6-dev",
        tempo_bpm=92.0,
        tempo_confidence=0.84,
        beat_positions_seconds=(0.0, 0.652, 1.304, 1.956, 2.608, 3.260),
        onset_positions_seconds=(0.05, 0.62, 1.31, 2.02, 2.61, 3.40),
        onset_rate_per_second=1.5,
        key="D",
        scale="minor",
        key_strength=0.73,
        sections=(
            AudioSectionEstimate(
                section_id="section-0001",
                start_seconds=0.0,
                end_seconds=2.0,
                confidence=0.82,
                label="A",
            ),
            AudioSectionEstimate(
                section_id="section-0002",
                start_seconds=2.0,
                end_seconds=4.0,
                confidence=0.79,
                label="B",
            ),
        ),
        structure_method="ESSENTIA_COMPATIBLE_SECTION_ANALYZER",
    )


def test_professional_audio_analysis_combines_qc_pcm_and_music_evidence(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mix.wav"
    source.write_bytes(b"fixture-audio")

    report = analyze_professional_audio(
        source,
        audio_qc_analyzer=_qc,
        pcm_decoder=_pcm,
        music_analyzer=_music,
        structure_confidence_threshold=0.7,
    )

    assert isinstance(report, ProfessionalAudioAnalysisReport)
    assert report.schema == "ProfessionalAudioAnalysisReport/v1"
    assert report.source_sha256 == _sha(source)
    assert report.integrated_lufs == pytest.approx(-15.0)
    assert report.momentary_max_lufs == pytest.approx(-12.5)
    assert report.short_term_max_lufs == pytest.approx(-14.1)

    assert -1.0 <= report.stereo_correlation <= 1.0
    assert 0.0 <= report.stereo_side_energy_ratio <= 1.0
    assert report.stereo_balance_db != pytest.approx(0.0)

    total = (
        report.low_energy_ratio
        + report.mid_energy_ratio
        + report.high_energy_ratio
    )
    assert total == pytest.approx(1.0)
    assert report.transient_density_per_second >= 0.0

    assert report.tempo_bpm == pytest.approx(92.0)
    assert report.tempo_confidence == pytest.approx(0.84)
    assert report.beat_count == 6
    assert report.onset_count == 6
    assert report.onset_rate_per_second == pytest.approx(1.5)
    assert report.key == "D"
    assert report.scale == "minor"
    assert report.key_strength == pytest.approx(0.73)

    assert report.structure_status == "AVAILABLE"
    assert tuple(item.section_id for item in report.sections) == (
        "section-0001",
        "section-0002",
    )
    assert report.analysis_engine == "Essentia"
    assert report.analysis_engine_version == "2.1-beta6-dev"
    assert report.private_media_policy == "LOCAL_ONLY"
    assert report.artistic_verdict == "NOT_ASSIGNED"


def test_low_confidence_structure_is_not_promoted_as_section_truth(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mix.wav"
    source.write_bytes(b"fixture-audio")

    def weak(_path: Path) -> MusicAnalysisResult:
        result = _music(_path)
        return MusicAnalysisResult(
            **{
                **result.__dict__,
                "sections": (
                    AudioSectionEstimate(
                        section_id="weak",
                        start_seconds=0.0,
                        end_seconds=4.0,
                        confidence=0.41,
                        label="possible-section",
                    ),
                ),
            }
        )

    report = analyze_professional_audio(
        source,
        audio_qc_analyzer=_qc,
        pcm_decoder=_pcm,
        music_analyzer=weak,
        structure_confidence_threshold=0.7,
    )

    assert report.structure_status == "LOW_CONFIDENCE"
    assert report.sections == ()
    assert report.rejected_section_count == 1


def test_audio_analysis_rejects_qc_bound_to_different_source_bytes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mix.wav"
    source.write_bytes(b"fixture-audio")

    def bad_qc(path: Path) -> AudioQCReport:
        report = _qc(path)
        return AudioQCReport(
            **{
                **report.__dict__,
                "source_sha256": "0" * 64,
            }
        )

    with pytest.raises(
        AudioAnalysisError,
        match="AUDIO_ANALYSIS_QC_SOURCE_HASH_MISMATCH",
    ):
        analyze_professional_audio(
            source,
            audio_qc_analyzer=bad_qc,
            pcm_decoder=_pcm,
            music_analyzer=_music,
        )


def test_audio_analysis_rejects_malformed_or_unversioned_music_backend(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mix.wav"
    source.write_bytes(b"fixture-audio")

    def bad(_path: Path) -> MusicAnalysisResult:
        result = _music(_path)
        return MusicAnalysisResult(
            **{
                **result.__dict__,
                "engine_version": "",
            }
        )

    with pytest.raises(
        AudioAnalysisError,
        match="AUDIO_ANALYSIS_ENGINE_VERSION_REQUIRED",
    ):
        analyze_professional_audio(
            source,
            audio_qc_analyzer=_qc,
            pcm_decoder=_pcm,
            music_analyzer=bad,
        )


def test_audio_analysis_validates_monotonic_beats_onsets_and_sections(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mix.wav"
    source.write_bytes(b"fixture-audio")

    def bad(_path: Path) -> MusicAnalysisResult:
        result = _music(_path)
        return MusicAnalysisResult(
            **{
                **result.__dict__,
                "onset_positions_seconds": (1.0, 0.5),
            }
        )

    with pytest.raises(
        AudioAnalysisError,
        match="AUDIO_ANALYSIS_EVENT_TIMELINE_INVALID",
    ):
        analyze_professional_audio(
            source,
            audio_qc_analyzer=_qc,
            pcm_decoder=_pcm,
            music_analyzer=bad,
        )


def test_default_music_analyzer_fails_closed_when_essentia_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "mix.wav"
    source.write_bytes(b"fixture-audio")

    import hazewave.audio_analysis as module

    monkeypatch.setattr(
        module,
        "_load_essentia",
        lambda: (_ for _ in ()).throw(
            AudioAnalysisError("AUDIO_ANALYSIS_ESSENTIA_RUNTIME_MISSING")
        ),
    )

    with pytest.raises(
        AudioAnalysisError,
        match="AUDIO_ANALYSIS_ESSENTIA_RUNTIME_MISSING",
    ):
        analyze_professional_audio(
            source,
            audio_qc_analyzer=_qc,
            pcm_decoder=_pcm,
        )
