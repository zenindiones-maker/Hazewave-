from __future__ import annotations

from dataclasses import dataclass, replace
import math
import re
from typing import Mapping

from hazewave.animation_assets import MouthShapeSet


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_FACIAL_EVENTS = frozenset({"HOLD", "BLINK", "FACIAL_ACCENT", "JAW"})
_ALLOWED_FACIAL_SOURCES = frozenset({"HUMAN_PLANNED", "AUTOMATIC_CANDIDATE"})
_TRANSCRIPT_STATUSES = frozenset({"HUMAN_VERIFIED", "MACHINE_DRAFT"})


class LipSyncError(RuntimeError):
    pass


def _text(value: str, code: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise LipSyncError(code)
    if "\x00" in normalized or "\n" in normalized or "\r" in normalized:
        raise LipSyncError(code)
    return normalized


def _number(value: float, code: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise LipSyncError(code) from exc
    if not math.isfinite(result):
        raise LipSyncError(code)
    return result


def _sha(value: str, code: str) -> str:
    result = str(value or "").strip()
    if not _SHA256_RE.fullmatch(result):
        raise LipSyncError(code)
    return result


@dataclass(frozen=True)
class DialogueSegment:
    segment_id: str
    start_seconds: float
    end_seconds: float
    text: str
    speaker_id: str
    schema: str = "DialogueSegment/v1"

    def __post_init__(self) -> None:
        _text(self.segment_id, "DIALOGUE_SEGMENT_ID_REQUIRED")
        _text(self.text, "DIALOGUE_SEGMENT_TEXT_REQUIRED")
        _text(self.speaker_id, "DIALOGUE_SEGMENT_SPEAKER_REQUIRED")
        start = _number(self.start_seconds, "DIALOGUE_SEGMENT_RANGE_INVALID")
        end = _number(self.end_seconds, "DIALOGUE_SEGMENT_RANGE_INVALID")
        if start < 0 or end <= start:
            raise LipSyncError("DIALOGUE_SEGMENT_RANGE_INVALID")


@dataclass(frozen=True)
class DialogueTiming:
    audio_sha256: str
    duration_seconds: float
    language: str
    transcript_status: str
    segments: tuple[DialogueSegment, ...]
    grants_execution_authority: bool = False
    schema: str = "DialogueTiming/v1"

    def __post_init__(self) -> None:
        _sha(self.audio_sha256, "DIALOGUE_TIMING_AUDIO_SHA_INVALID")
        duration = _number(
            self.duration_seconds,
            "DIALOGUE_TIMING_DURATION_INVALID",
        )
        if duration <= 0:
            raise LipSyncError("DIALOGUE_TIMING_DURATION_INVALID")
        _text(self.language, "DIALOGUE_TIMING_LANGUAGE_REQUIRED")
        if self.transcript_status not in _TRANSCRIPT_STATUSES:
            raise LipSyncError("DIALOGUE_TIMING_TRANSCRIPT_STATUS_INVALID")

        previous_end: float | None = None
        seen: set[str] = set()
        for segment in self.segments:
            if not isinstance(segment, DialogueSegment):
                raise LipSyncError("DIALOGUE_TIMING_SEGMENT_INVALID")
            if segment.segment_id in seen:
                raise LipSyncError("DIALOGUE_TIMING_DUPLICATE_SEGMENT")
            seen.add(segment.segment_id)
            if segment.end_seconds > duration + 1e-9:
                raise LipSyncError("DIALOGUE_TIMING_SEGMENT_OUT_OF_RANGE")
            if (
                previous_end is not None
                and segment.start_seconds < previous_end - 1e-9
            ):
                raise LipSyncError("DIALOGUE_TIMING_OVERLAP")
            previous_end = segment.end_seconds


@dataclass(frozen=True)
class LipSyncAnalyzerQualification:
    analyzer_id: str
    analyzer_version: str
    language: str
    recognizer_mode: str
    platform: str
    architecture: str
    status: str
    automatic_approval: bool
    human_validation_required: bool
    known_limitations: tuple[str, ...]
    grants_execution_authority: bool = False
    schema: str = "LipSyncAnalyzerQualification/v1"


def qualify_rhubarb_ptbr(
    *,
    version: str,
    platform: str,
    architecture: str,
) -> LipSyncAnalyzerQualification:
    version_value = _text(version, "LIP_SYNC_ANALYZER_VERSION_REQUIRED")
    platform_value = _text(platform, "LIP_SYNC_ANALYZER_PLATFORM_REQUIRED")
    architecture_value = _text(
        architecture,
        "LIP_SYNC_ANALYZER_ARCHITECTURE_REQUIRED",
    )
    compatible = (
        platform_value.casefold() == "linux"
        and architecture_value.casefold() in {"x86_64", "amd64"}
    )
    return LipSyncAnalyzerQualification(
        analyzer_id="rhubarb",
        analyzer_version=version_value,
        language="pt-BR",
        recognizer_mode="phonetic",
        platform=platform_value,
        architecture=architecture_value,
        status="SUBORDINATE_CANDIDATE" if compatible else "NOT_QUALIFIED",
        automatic_approval=False,
        human_validation_required=True,
        known_limitations=(
            "The Rhubarb project documents the phonetic recognizer for non-English recordings as usually less precise than its English PocketSphinx recognizer.",
            "Portuguese timing and mouth-shape performance require real PT-BR validation and owner correction before final animation.",
        ),
    )


@dataclass(frozen=True)
class PhonemeEvent:
    event_id: str
    phoneme: str
    start_seconds: float
    end_seconds: float
    confidence: float
    schema: str = "PhonemeEvent/v1"

    def __post_init__(self) -> None:
        _text(self.event_id, "PHONEME_EVENT_ID_REQUIRED")
        _text(self.phoneme, "PHONEME_EVENT_PHONEME_REQUIRED")
        start = _number(self.start_seconds, "PHONEME_EVENT_RANGE_INVALID")
        end = _number(self.end_seconds, "PHONEME_EVENT_RANGE_INVALID")
        confidence = _number(
            self.confidence,
            "PHONEME_EVENT_CONFIDENCE_INVALID",
        )
        if start < 0 or end <= start:
            raise LipSyncError("PHONEME_EVENT_RANGE_INVALID")
        if not 0.0 <= confidence <= 1.0:
            raise LipSyncError("PHONEME_EVENT_CONFIDENCE_INVALID")


@dataclass(frozen=True)
class PhonemeTimeline:
    audio_sha256: str
    duration_seconds: float
    language: str
    analyzer_id: str
    analyzer_version: str
    recognizer_mode: str
    events: tuple[PhonemeEvent, ...]
    analysis_only: bool = True
    grants_execution_authority: bool = False
    schema: str = "PhonemeTimeline/v1"

    def __post_init__(self) -> None:
        _sha(self.audio_sha256, "PHONEME_TIMELINE_AUDIO_SHA_INVALID")
        duration = _number(
            self.duration_seconds,
            "PHONEME_TIMELINE_DURATION_INVALID",
        )
        if duration <= 0:
            raise LipSyncError("PHONEME_TIMELINE_DURATION_INVALID")
        _text(self.language, "PHONEME_TIMELINE_LANGUAGE_REQUIRED")
        _text(self.analyzer_id, "PHONEME_TIMELINE_ANALYZER_REQUIRED")
        _text(
            self.analyzer_version,
            "PHONEME_TIMELINE_ANALYZER_VERSION_REQUIRED",
        )
        _text(
            self.recognizer_mode,
            "PHONEME_TIMELINE_RECOGNIZER_REQUIRED",
        )

        previous_end: float | None = None
        seen: set[str] = set()
        for event in self.events:
            if not isinstance(event, PhonemeEvent):
                raise LipSyncError("PHONEME_TIMELINE_EVENT_INVALID")
            if event.event_id in seen:
                raise LipSyncError("PHONEME_TIMELINE_DUPLICATE_EVENT")
            seen.add(event.event_id)
            if event.end_seconds > duration + 1e-9:
                raise LipSyncError("PHONEME_TIMELINE_EVENT_OUT_OF_RANGE")
            if (
                previous_end is not None
                and event.start_seconds < previous_end - 1e-9
            ):
                raise LipSyncError("PHONEME_TIMELINE_OVERLAP")
            previous_end = event.end_seconds


@dataclass(frozen=True)
class FacialPerformanceEvent:
    event_id: str
    event_type: str
    start_seconds: float
    end_seconds: float
    intensity: float
    source: str
    grants_execution_authority: bool = False
    schema: str = "FacialPerformanceEvent/v1"

    def __post_init__(self) -> None:
        _text(self.event_id, "FACIAL_EVENT_ID_REQUIRED")
        if self.event_type not in _ALLOWED_FACIAL_EVENTS:
            raise LipSyncError("FACIAL_EVENT_TYPE_INVALID")
        start = _number(self.start_seconds, "FACIAL_EVENT_RANGE_INVALID")
        end = _number(self.end_seconds, "FACIAL_EVENT_RANGE_INVALID")
        intensity = _number(
            self.intensity,
            "FACIAL_EVENT_INTENSITY_INVALID",
        )
        if start < 0 or end <= start:
            raise LipSyncError("FACIAL_EVENT_RANGE_INVALID")
        if not 0.0 <= intensity <= 1.0:
            raise LipSyncError("FACIAL_EVENT_INTENSITY_INVALID")
        if self.source not in _ALLOWED_FACIAL_SOURCES:
            raise LipSyncError("FACIAL_EVENT_SOURCE_INVALID")


@dataclass(frozen=True)
class VisemeEvent:
    event_id: str
    viseme_id: str
    start_seconds: float
    end_seconds: float
    source_phoneme_ids: tuple[str, ...]
    source: str
    schema: str = "VisemeEvent/v1"

    def __post_init__(self) -> None:
        _text(self.event_id, "VISEME_EVENT_ID_REQUIRED")
        _text(self.viseme_id, "VISEME_EVENT_VISEME_REQUIRED")
        start = _number(self.start_seconds, "VISEME_EVENT_RANGE_INVALID")
        end = _number(self.end_seconds, "VISEME_EVENT_RANGE_INVALID")
        if start < 0 or end <= start:
            raise LipSyncError("VISEME_EVENT_RANGE_INVALID")
        if not self.source_phoneme_ids:
            raise LipSyncError("VISEME_EVENT_PHONEME_SOURCE_REQUIRED")
        for item in self.source_phoneme_ids:
            _text(item, "VISEME_EVENT_PHONEME_SOURCE_REQUIRED")
        if self.source not in {"AUTOMATIC_ANALYSIS", "HUMAN_CORRECTION"}:
            raise LipSyncError("VISEME_EVENT_SOURCE_INVALID")


@dataclass(frozen=True)
class VisemeTimeline:
    audio_sha256: str
    duration_seconds: float
    language: str
    character_id: str
    events: tuple[VisemeEvent, ...]
    facial_events: tuple[FacialPerformanceEvent, ...]
    requires_human_review: bool
    human_validated: bool
    human_owner_approval_id: str | None = None
    grants_execution_authority: bool = False
    schema: str = "VisemeTimeline/v1"

    def __post_init__(self) -> None:
        _sha(self.audio_sha256, "VISEME_TIMELINE_AUDIO_SHA_INVALID")
        duration = _number(
            self.duration_seconds,
            "VISEME_TIMELINE_DURATION_INVALID",
        )
        if duration <= 0:
            raise LipSyncError("VISEME_TIMELINE_DURATION_INVALID")
        _text(self.language, "VISEME_TIMELINE_LANGUAGE_REQUIRED")
        _text(self.character_id, "VISEME_TIMELINE_CHARACTER_REQUIRED")
        previous_end: float | None = None
        ids: set[str] = set()
        for event in self.events:
            if event.event_id in ids:
                raise LipSyncError("VISEME_TIMELINE_DUPLICATE_EVENT")
            ids.add(event.event_id)
            if event.end_seconds > duration + 1e-9:
                raise LipSyncError("VISEME_TIMELINE_EVENT_OUT_OF_RANGE")
            if (
                previous_end is not None
                and event.start_seconds < previous_end - 1e-9
            ):
                raise LipSyncError("VISEME_TIMELINE_OVERLAP")
            previous_end = event.end_seconds
        for event in self.facial_events:
            if event.end_seconds > duration + 1e-9:
                raise LipSyncError("FACIAL_EVENT_OUT_OF_RANGE")
        if self.human_validated:
            if not str(self.human_owner_approval_id or "").strip():
                raise LipSyncError("VISEME_HUMAN_APPROVAL_REQUIRED")
            if self.requires_human_review:
                raise LipSyncError("VISEME_VALIDATION_STATE_INVALID")


@dataclass(frozen=True)
class ManualVisemeCorrection:
    correction_id: str
    target_event_id: str
    new_viseme_id: str
    new_start_seconds: float
    new_end_seconds: float
    reason: str
    schema: str = "ManualVisemeCorrection/v1"

    def __post_init__(self) -> None:
        _text(self.correction_id, "VISEME_CORRECTION_ID_REQUIRED")
        _text(self.target_event_id, "VISEME_CORRECTION_TARGET_REQUIRED")
        _text(self.new_viseme_id, "VISEME_CORRECTION_VISEME_REQUIRED")
        _text(self.reason, "VISEME_CORRECTION_REASON_REQUIRED")
        start = _number(
            self.new_start_seconds,
            "VISEME_CORRECTION_RANGE_INVALID",
        )
        end = _number(
            self.new_end_seconds,
            "VISEME_CORRECTION_RANGE_INVALID",
        )
        if start < 0 or end <= start:
            raise LipSyncError("VISEME_CORRECTION_RANGE_INVALID")


def _mouth_ids(mouth_shape_set: MouthShapeSet) -> set[str]:
    if not isinstance(mouth_shape_set, MouthShapeSet):
        raise LipSyncError("MOUTH_SHAPE_SET_REQUIRED")
    return {shape.viseme_id for shape in mouth_shape_set.shapes}


def map_phonemes_to_visemes(
    phonemes: PhonemeTimeline,
    mouth_shape_set: MouthShapeSet,
    *,
    mapping: Mapping[str, str],
    facial_events: tuple[FacialPerformanceEvent, ...] = (),
) -> VisemeTimeline:
    if not isinstance(phonemes, PhonemeTimeline):
        raise LipSyncError("PHONEME_TIMELINE_REQUIRED")
    if phonemes.language != mouth_shape_set.language:
        raise LipSyncError("VISEME_LANGUAGE_MISMATCH")
    if phonemes.language != "pt-BR":
        raise LipSyncError("VISEME_PTBR_VALIDATION_REQUIRED")
    if not isinstance(mapping, Mapping):
        raise LipSyncError("VISEME_MAPPING_INVALID")

    known_visemes = _mouth_ids(mouth_shape_set)
    events: list[VisemeEvent] = []
    for phoneme in phonemes.events:
        target = mapping.get(phoneme.phoneme)
        if target is None or not str(target).strip():
            raise LipSyncError(
                f"VISEME_MAPPING_MISSING:{phoneme.phoneme}"
            )
        target_id = str(target).strip()
        if target_id not in known_visemes:
            raise LipSyncError(
                f"VISEME_MAPPING_TARGET_UNKNOWN:{target_id}"
            )
        events.append(
            VisemeEvent(
                event_id=f"viseme-{phoneme.event_id}",
                viseme_id=target_id,
                start_seconds=phoneme.start_seconds,
                end_seconds=phoneme.end_seconds,
                source_phoneme_ids=(phoneme.event_id,),
                source="AUTOMATIC_ANALYSIS",
            )
        )

    return VisemeTimeline(
        audio_sha256=phonemes.audio_sha256,
        duration_seconds=phonemes.duration_seconds,
        language=phonemes.language,
        character_id=mouth_shape_set.character_id,
        events=tuple(events),
        facial_events=facial_events,
        requires_human_review=True,
        human_validated=False,
    )


def apply_manual_viseme_corrections(
    timeline: VisemeTimeline,
    *,
    corrections: tuple[ManualVisemeCorrection, ...],
    mouth_shape_set: MouthShapeSet,
    human_owner_approval_id: str,
) -> VisemeTimeline:
    approval = str(human_owner_approval_id or "").strip()
    if not approval:
        raise LipSyncError("VISEME_HUMAN_APPROVAL_REQUIRED")
    if timeline.language != mouth_shape_set.language:
        raise LipSyncError("VISEME_LANGUAGE_MISMATCH")
    if timeline.character_id != mouth_shape_set.character_id:
        raise LipSyncError("VISEME_CHARACTER_MISMATCH")

    known_visemes = _mouth_ids(mouth_shape_set)
    events = list(timeline.events)
    by_id = {event.event_id: index for index, event in enumerate(events)}
    seen_corrections: set[str] = set()

    for correction in corrections:
        if correction.correction_id in seen_corrections:
            raise LipSyncError("VISEME_CORRECTION_DUPLICATE_ID")
        seen_corrections.add(correction.correction_id)
        if correction.target_event_id not in by_id:
            raise LipSyncError("VISEME_CORRECTION_TARGET_UNKNOWN")
        if correction.new_viseme_id not in known_visemes:
            raise LipSyncError("VISEME_MAPPING_TARGET_UNKNOWN")
        if correction.new_end_seconds > timeline.duration_seconds + 1e-9:
            raise LipSyncError("VISEME_CORRECTION_RANGE_INVALID")

        index = by_id[correction.target_event_id]
        current = events[index]

        if index > 0:
            previous = events[index - 1]
            if correction.new_start_seconds <= previous.start_seconds:
                raise LipSyncError("VISEME_CORRECTION_RANGE_INVALID")
            events[index - 1] = replace(
                previous,
                end_seconds=correction.new_start_seconds,
            )

        if index + 1 < len(events):
            following = events[index + 1]
            if correction.new_end_seconds >= following.end_seconds:
                raise LipSyncError("VISEME_CORRECTION_RANGE_INVALID")
            events[index + 1] = replace(
                following,
                start_seconds=correction.new_end_seconds,
            )

        events[index] = VisemeEvent(
            event_id=current.event_id,
            viseme_id=correction.new_viseme_id,
            start_seconds=correction.new_start_seconds,
            end_seconds=correction.new_end_seconds,
            source_phoneme_ids=current.source_phoneme_ids,
            source="HUMAN_CORRECTION",
        )

    return VisemeTimeline(
        audio_sha256=timeline.audio_sha256,
        duration_seconds=timeline.duration_seconds,
        language=timeline.language,
        character_id=timeline.character_id,
        events=tuple(events),
        facial_events=timeline.facial_events,
        requires_human_review=False,
        human_validated=True,
        human_owner_approval_id=approval,
    )
