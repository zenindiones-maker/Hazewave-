from __future__ import annotations

import pytest

from hazewave.haze_wave_bridge import (
    HazeWaveBridgeError,
    IntensityPoint,
    MusicSection,
    MusicStructure,
    TimedEvent,
    build_audiovisual_cue_sheet,
)


def _structure() -> MusicStructure:
    return MusicStructure(
        source_master_sha256="a" * 64,
        duration_seconds=12.0,
        tempo_bpm=80.0,
        time_signature_numerator=4,
        time_signature_denominator=4,
        sections=(
            MusicSection(
                section_id="intro",
                label="Intro",
                start_seconds=0.0,
                end_seconds=4.0,
            ),
            MusicSection(
                section_id="body",
                label="Body",
                start_seconds=4.0,
                end_seconds=12.0,
            ),
        ),
        beats=(
            TimedEvent(event_id="beat-001", time_seconds=0.0, strength=0.7),
            TimedEvent(event_id="beat-002", time_seconds=0.75, strength=0.8),
            TimedEvent(event_id="beat-003", time_seconds=1.5, strength=0.9),
        ),
        transients=(
            TimedEvent(event_id="hit-001", time_seconds=4.0, strength=1.0),
            TimedEvent(event_id="hit-002", time_seconds=8.0, strength=0.85),
        ),
        phrase_boundaries=(
            TimedEvent(event_id="phrase-001", time_seconds=4.0, strength=1.0),
            TimedEvent(event_id="phrase-002", time_seconds=8.0, strength=0.8),
        ),
        intensity=(
            IntensityPoint(time_seconds=0.0, normalized_intensity=0.25),
            IntensityPoint(time_seconds=4.0, normalized_intensity=0.65),
            IntensityPoint(time_seconds=8.0, normalized_intensity=0.85),
            IntensityPoint(time_seconds=12.0, normalized_intensity=0.45),
        ),
    )


def test_bridge_materializes_unidirectional_typed_cue_sheet() -> None:
    structure = _structure()

    sheet = build_audiovisual_cue_sheet(
        structure,
        master_timing_approved=True,
        approval_id="human-owner-approval-001",
    )

    assert structure.schema == "MusicStructure/v1"
    assert sheet.schema == "AudiovisualCueSheet/v1"
    assert sheet.direction == "HAZE_STATE_TO_WAVE_STATE_ONLY"
    assert sheet.source_master_sha256 == "a" * 64
    assert sheet.master_timing_approval_id == "human-owner-approval-001"
    assert sheet.grants_execution_authority is False
    assert sheet.reverse_authority is False

    cue_types = {cue.cue_type for cue in sheet.cues}
    assert {
        "SECTION_BOUNDARY",
        "BEAT",
        "TRANSIENT",
        "PHRASE_BOUNDARY",
        "INTENSITY",
    }.issubset(cue_types)

    assert all(0.0 <= cue.time_seconds <= 12.0 for cue in sheet.cues)
    assert all(cue.visual_command is None for cue in sheet.cues)


def test_bridge_refuses_unapproved_master_timing() -> None:
    with pytest.raises(HazeWaveBridgeError, match="HAZE_WAVE_TIMING_NOT_APPROVED"):
        build_audiovisual_cue_sheet(
            _structure(),
            master_timing_approved=False,
            approval_id="",
        )


def test_music_structure_rejects_overlapping_sections() -> None:
    with pytest.raises(HazeWaveBridgeError, match="MUSIC_STRUCTURE_SECTIONS_INVALID"):
        MusicStructure(
            source_master_sha256="a" * 64,
            duration_seconds=10.0,
            tempo_bpm=80.0,
            time_signature_numerator=4,
            time_signature_denominator=4,
            sections=(
                MusicSection(
                    section_id="a",
                    label="A",
                    start_seconds=0.0,
                    end_seconds=6.0,
                ),
                MusicSection(
                    section_id="b",
                    label="B",
                    start_seconds=5.5,
                    end_seconds=10.0,
                ),
            ),
            beats=(),
            transients=(),
            phrase_boundaries=(),
            intensity=(),
        )


def test_music_structure_rejects_out_of_range_events() -> None:
    with pytest.raises(HazeWaveBridgeError, match="MUSIC_STRUCTURE_EVENT_OUT_OF_RANGE"):
        MusicStructure(
            source_master_sha256="a" * 64,
            duration_seconds=10.0,
            tempo_bpm=80.0,
            time_signature_numerator=4,
            time_signature_denominator=4,
            sections=(),
            beats=(
                TimedEvent(
                    event_id="bad",
                    time_seconds=10.1,
                    strength=1.0,
                ),
            ),
            transients=(),
            phrase_boundaries=(),
            intensity=(),
        )


def test_intensity_is_bounded_and_monotonic_in_time() -> None:
    with pytest.raises(HazeWaveBridgeError, match="MUSIC_STRUCTURE_INTENSITY_INVALID"):
        MusicStructure(
            source_master_sha256="a" * 64,
            duration_seconds=10.0,
            tempo_bpm=None,
            time_signature_numerator=None,
            time_signature_denominator=None,
            sections=(),
            beats=(),
            transients=(),
            phrase_boundaries=(),
            intensity=(
                IntensityPoint(time_seconds=5.0, normalized_intensity=0.8),
                IntensityPoint(time_seconds=4.0, normalized_intensity=0.6),
            ),
        )


def test_cue_sheet_contains_editorial_hints_not_actions() -> None:
    sheet = build_audiovisual_cue_sheet(
        _structure(),
        master_timing_approved=True,
        approval_id="approval-001",
    )

    transient = next(cue for cue in sheet.cues if cue.cue_type == "TRANSIENT")
    assert "cut_candidate" in transient.editorial_hints
    assert transient.visual_command is None

    intensity = next(cue for cue in sheet.cues if cue.cue_type == "INTENSITY")
    assert "motion_intensity_reference" in intensity.editorial_hints
    assert intensity.visual_command is None
