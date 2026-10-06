from __future__ import annotations

import pytest

from hazewave.animation_assets import MouthShape, MouthShapeSet
from hazewave.lip_sync import (
    DialogueSegment,
    DialogueTiming,
    FacialPerformanceEvent,
    LipSyncError,
    ManualVisemeCorrection,
    PhonemeEvent,
    PhonemeTimeline,
    apply_manual_viseme_corrections,
    map_phonemes_to_visemes,
    qualify_rhubarb_ptbr,
)


def _mouths() -> MouthShapeSet:
    return MouthShapeSet(
        character_id="hero-001",
        language="pt-BR",
        shapes=(
            MouthShape(viseme_id="REST", phoneme_classes=("silence",)),
            MouthShape(viseme_id="A", phoneme_classes=("a", "ã", "á")),
            MouthShape(viseme_id="M", phoneme_classes=("m", "b", "p")),
            MouthShape(viseme_id="E", phoneme_classes=("e", "é", "ê")),
        ),
    )


def _phonemes() -> PhonemeTimeline:
    return PhonemeTimeline(
        audio_sha256="a" * 64,
        duration_seconds=1.2,
        language="pt-BR",
        analyzer_id="rhubarb",
        analyzer_version="1.13.0",
        recognizer_mode="phonetic",
        events=(
            PhonemeEvent(
                event_id="ph-001",
                phoneme="m",
                start_seconds=0.0,
                end_seconds=0.18,
                confidence=0.65,
            ),
            PhonemeEvent(
                event_id="ph-002",
                phoneme="a",
                start_seconds=0.18,
                end_seconds=0.55,
                confidence=0.62,
            ),
            PhonemeEvent(
                event_id="ph-003",
                phoneme="e",
                start_seconds=0.55,
                end_seconds=0.9,
                confidence=0.58,
            ),
        ),
    )


def test_dialogue_timing_is_ptbr_hash_bound_and_non_overlapping() -> None:
    timing = DialogueTiming(
        audio_sha256="a" * 64,
        duration_seconds=2.0,
        language="pt-BR",
        transcript_status="HUMAN_VERIFIED",
        segments=(
            DialogueSegment(
                segment_id="line-001",
                start_seconds=0.1,
                end_seconds=0.9,
                text="Boa noite.",
                speaker_id="hero-001",
            ),
            DialogueSegment(
                segment_id="line-002",
                start_seconds=1.1,
                end_seconds=1.8,
                text="Vamos nessa.",
                speaker_id="hero-001",
            ),
        ),
    )

    assert timing.schema == "DialogueTiming/v1"
    assert timing.language == "pt-BR"
    assert timing.transcript_status == "HUMAN_VERIFIED"
    assert timing.grants_execution_authority is False


def test_dialogue_timing_rejects_overlap() -> None:
    with pytest.raises(LipSyncError, match="DIALOGUE_TIMING_OVERLAP"):
        DialogueTiming(
            audio_sha256="a" * 64,
            duration_seconds=2.0,
            language="pt-BR",
            transcript_status="HUMAN_VERIFIED",
            segments=(
                DialogueSegment(
                    segment_id="a",
                    start_seconds=0.0,
                    end_seconds=1.2,
                    text="A",
                    speaker_id="hero",
                ),
                DialogueSegment(
                    segment_id="b",
                    start_seconds=1.0,
                    end_seconds=1.8,
                    text="B",
                    speaker_id="hero",
                ),
            ),
        )


def test_rhubarb_ptbr_is_subordinate_candidate_never_automatic_approval() -> None:
    qualification = qualify_rhubarb_ptbr(
        version="1.13.0",
        platform="linux",
        architecture="x86_64",
    )

    assert qualification.schema == "LipSyncAnalyzerQualification/v1"
    assert qualification.analyzer_id == "rhubarb"
    assert qualification.recognizer_mode == "phonetic"
    assert qualification.language == "pt-BR"
    assert qualification.status == "SUBORDINATE_CANDIDATE"
    assert qualification.automatic_approval is False
    assert qualification.human_validation_required is True
    assert "less precise" in qualification.known_limitations[0].lower()


def test_phoneme_mapping_produces_viseme_candidates_not_final_performance() -> None:
    timeline = map_phonemes_to_visemes(
        _phonemes(),
        _mouths(),
        mapping={
            "m": "M",
            "a": "A",
            "e": "E",
        },
        facial_events=(
            FacialPerformanceEvent(
                event_id="blink-001",
                event_type="BLINK",
                start_seconds=0.7,
                end_seconds=0.82,
                intensity=0.8,
                source="HUMAN_PLANNED",
            ),
        ),
    )

    assert timeline.schema == "VisemeTimeline/v1"
    assert [event.viseme_id for event in timeline.events] == ["M", "A", "E"]
    assert timeline.requires_human_review is True
    assert timeline.human_validated is False
    assert timeline.grants_execution_authority is False
    assert timeline.facial_events[0].event_type == "BLINK"


def test_unmapped_ptbr_phoneme_fails_closed_instead_of_guessing() -> None:
    with pytest.raises(LipSyncError, match="VISEME_MAPPING_MISSING"):
        map_phonemes_to_visemes(
            _phonemes(),
            _mouths(),
            mapping={"m": "M", "a": "A"},
        )


def test_mapping_to_unknown_character_mouth_shape_fails_closed() -> None:
    with pytest.raises(LipSyncError, match="VISEME_MAPPING_TARGET_UNKNOWN"):
        map_phonemes_to_visemes(
            _phonemes(),
            _mouths(),
            mapping={"m": "M", "a": "A", "e": "DOES_NOT_EXIST"},
        )


def test_manual_owner_correction_can_change_boundary_and_mouth_shape_traceably() -> None:
    automatic = map_phonemes_to_visemes(
        _phonemes(),
        _mouths(),
        mapping={"m": "M", "a": "A", "e": "E"},
    )

    corrected = apply_manual_viseme_corrections(
        automatic,
        corrections=(
            ManualVisemeCorrection(
                correction_id="corr-001",
                target_event_id="viseme-ph-002",
                new_viseme_id="E",
                new_start_seconds=0.20,
                new_end_seconds=0.58,
                reason="Owner prefers a narrower mouth transition here.",
            ),
        ),
        mouth_shape_set=_mouths(),
        human_owner_approval_id="owner-review-001",
    )

    event = next(item for item in corrected.events if item.event_id == "viseme-ph-002")
    assert event.viseme_id == "E"
    assert event.start_seconds == pytest.approx(0.20)
    assert event.end_seconds == pytest.approx(0.58)
    assert event.source == "HUMAN_CORRECTION"
    assert corrected.human_validated is True
    assert corrected.human_owner_approval_id == "owner-review-001"
    assert corrected.requires_human_review is False


def test_manual_correction_requires_owner_approval() -> None:
    automatic = map_phonemes_to_visemes(
        _phonemes(),
        _mouths(),
        mapping={"m": "M", "a": "A", "e": "E"},
    )

    with pytest.raises(LipSyncError, match="VISEME_HUMAN_APPROVAL_REQUIRED"):
        apply_manual_viseme_corrections(
            automatic,
            corrections=(),
            mouth_shape_set=_mouths(),
            human_owner_approval_id="",
        )


@pytest.mark.parametrize("event_type", ["HOLD", "BLINK", "FACIAL_ACCENT", "JAW"])
def test_facial_performance_supports_manual_animation_surfaces(event_type: str) -> None:
    event = FacialPerformanceEvent(
        event_id=f"event-{event_type.lower()}",
        event_type=event_type,
        start_seconds=0.2,
        end_seconds=0.4,
        intensity=0.5,
        source="HUMAN_PLANNED",
    )

    assert event.schema == "FacialPerformanceEvent/v1"
    assert event.event_type == event_type
    assert event.grants_execution_authority is False
