from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Any, Final


_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
CUE_DIRECTION: Final = "HAZE_STATE_TO_WAVE_STATE_ONLY"


class HazeWaveBridgeError(RuntimeError):
    pass


def _required_text(value: str, code: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise HazeWaveBridgeError(code)
    return normalized


def _finite(value: float, code: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise HazeWaveBridgeError(code) from exc
    if not math.isfinite(number):
        raise HazeWaveBridgeError(code)
    return number


@dataclass(frozen=True)
class TimedEvent:
    event_id: str
    time_seconds: float
    strength: float
    schema: str = "TimedEvent/v1"

    def __post_init__(self) -> None:
        _required_text(self.event_id, "MUSIC_STRUCTURE_EVENT_ID_REQUIRED")
        time_seconds = _finite(
            self.time_seconds,
            "MUSIC_STRUCTURE_EVENT_INVALID",
        )
        strength = _finite(
            self.strength,
            "MUSIC_STRUCTURE_EVENT_INVALID",
        )
        if time_seconds < 0.0 or not 0.0 <= strength <= 1.0:
            raise HazeWaveBridgeError("MUSIC_STRUCTURE_EVENT_INVALID")


@dataclass(frozen=True)
class IntensityPoint:
    time_seconds: float
    normalized_intensity: float
    schema: str = "IntensityPoint/v1"

    def __post_init__(self) -> None:
        time_seconds = _finite(
            self.time_seconds,
            "MUSIC_STRUCTURE_INTENSITY_INVALID",
        )
        intensity = _finite(
            self.normalized_intensity,
            "MUSIC_STRUCTURE_INTENSITY_INVALID",
        )
        if time_seconds < 0.0 or not 0.0 <= intensity <= 1.0:
            raise HazeWaveBridgeError("MUSIC_STRUCTURE_INTENSITY_INVALID")


@dataclass(frozen=True)
class MusicSection:
    section_id: str
    label: str
    start_seconds: float
    end_seconds: float
    schema: str = "MusicSection/v1"

    def __post_init__(self) -> None:
        _required_text(
            self.section_id,
            "MUSIC_STRUCTURE_SECTION_ID_REQUIRED",
        )
        _required_text(
            self.label,
            "MUSIC_STRUCTURE_SECTION_LABEL_REQUIRED",
        )
        start = _finite(
            self.start_seconds,
            "MUSIC_STRUCTURE_SECTIONS_INVALID",
        )
        end = _finite(
            self.end_seconds,
            "MUSIC_STRUCTURE_SECTIONS_INVALID",
        )
        if start < 0.0 or end <= start:
            raise HazeWaveBridgeError("MUSIC_STRUCTURE_SECTIONS_INVALID")


@dataclass(frozen=True)
class MusicStructure:
    source_master_sha256: str
    duration_seconds: float
    tempo_bpm: float | None
    time_signature_numerator: int | None
    time_signature_denominator: int | None
    sections: tuple[MusicSection, ...]
    beats: tuple[TimedEvent, ...]
    transients: tuple[TimedEvent, ...]
    phrase_boundaries: tuple[TimedEvent, ...]
    intensity: tuple[IntensityPoint, ...]
    schema: str = "MusicStructure/v1"

    def __post_init__(self) -> None:
        if not _SHA256_RE.fullmatch(
            str(self.source_master_sha256 or "")
        ):
            raise HazeWaveBridgeError(
                "MUSIC_STRUCTURE_SOURCE_SHA256_INVALID"
            )

        duration = _finite(
            self.duration_seconds,
            "MUSIC_STRUCTURE_DURATION_INVALID",
        )
        if duration <= 0.0:
            raise HazeWaveBridgeError(
                "MUSIC_STRUCTURE_DURATION_INVALID"
            )

        if self.tempo_bpm is not None:
            tempo = _finite(
                self.tempo_bpm,
                "MUSIC_STRUCTURE_TEMPO_INVALID",
            )
            if tempo <= 0.0:
                raise HazeWaveBridgeError(
                    "MUSIC_STRUCTURE_TEMPO_INVALID"
                )

        numerator = self.time_signature_numerator
        denominator = self.time_signature_denominator
        if (numerator is None) != (denominator is None):
            raise HazeWaveBridgeError(
                "MUSIC_STRUCTURE_TIME_SIGNATURE_INVALID"
            )
        if numerator is not None and denominator is not None:
            if (
                not isinstance(numerator, int)
                or isinstance(numerator, bool)
                or not isinstance(denominator, int)
                or isinstance(denominator, bool)
                or numerator <= 0
                or denominator <= 0
            ):
                raise HazeWaveBridgeError(
                    "MUSIC_STRUCTURE_TIME_SIGNATURE_INVALID"
                )

        self._validate_sections(duration)
        self._validate_events(duration)
        self._validate_intensity(duration)

    def _validate_sections(self, duration: float) -> None:
        previous_end: float | None = None
        seen_ids: set[str] = set()
        for section in self.sections:
            if not isinstance(section, MusicSection):
                raise HazeWaveBridgeError(
                    "MUSIC_STRUCTURE_SECTIONS_INVALID"
                )
            if section.section_id in seen_ids:
                raise HazeWaveBridgeError(
                    "MUSIC_STRUCTURE_SECTIONS_INVALID"
                )
            seen_ids.add(section.section_id)
            start = float(section.start_seconds)
            end = float(section.end_seconds)
            if end > duration + 1e-9:
                raise HazeWaveBridgeError(
                    "MUSIC_STRUCTURE_SECTIONS_INVALID"
                )
            if previous_end is not None and start < previous_end - 1e-9:
                raise HazeWaveBridgeError(
                    "MUSIC_STRUCTURE_SECTIONS_INVALID"
                )
            previous_end = end

    @staticmethod
    def _validate_event_group(
        events: tuple[TimedEvent, ...],
        *,
        duration: float,
    ) -> None:
        previous_time: float | None = None
        seen_ids: set[str] = set()
        for event in events:
            if not isinstance(event, TimedEvent):
                raise HazeWaveBridgeError(
                    "MUSIC_STRUCTURE_EVENT_INVALID"
                )
            if event.event_id in seen_ids:
                raise HazeWaveBridgeError(
                    "MUSIC_STRUCTURE_EVENT_INVALID"
                )
            seen_ids.add(event.event_id)
            time_seconds = float(event.time_seconds)
            if time_seconds > duration + 1e-9:
                raise HazeWaveBridgeError(
                    "MUSIC_STRUCTURE_EVENT_OUT_OF_RANGE"
                )
            if (
                previous_time is not None
                and time_seconds < previous_time - 1e-9
            ):
                raise HazeWaveBridgeError(
                    "MUSIC_STRUCTURE_EVENT_ORDER_INVALID"
                )
            previous_time = time_seconds

    def _validate_events(self, duration: float) -> None:
        for events in (
            self.beats,
            self.transients,
            self.phrase_boundaries,
        ):
            self._validate_event_group(
                events,
                duration=duration,
            )

    def _validate_intensity(self, duration: float) -> None:
        previous_time: float | None = None
        for point in self.intensity:
            if not isinstance(point, IntensityPoint):
                raise HazeWaveBridgeError(
                    "MUSIC_STRUCTURE_INTENSITY_INVALID"
                )
            time_seconds = float(point.time_seconds)
            if time_seconds > duration + 1e-9:
                raise HazeWaveBridgeError(
                    "MUSIC_STRUCTURE_INTENSITY_INVALID"
                )
            if (
                previous_time is not None
                and time_seconds <= previous_time + 1e-12
            ):
                raise HazeWaveBridgeError(
                    "MUSIC_STRUCTURE_INTENSITY_INVALID"
                )
            previous_time = time_seconds

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["sections"] = [asdict(item) for item in self.sections]
        value["beats"] = [asdict(item) for item in self.beats]
        value["transients"] = [asdict(item) for item in self.transients]
        value["phrase_boundaries"] = [
            asdict(item) for item in self.phrase_boundaries
        ]
        value["intensity"] = [
            asdict(item) for item in self.intensity
        ]
        return value


@dataclass(frozen=True)
class AudiovisualCue:
    cue_id: str
    cue_type: str
    time_seconds: float
    strength: float
    editorial_hints: tuple[str, ...]
    label: str | None = None
    visual_command: None = None
    schema: str = "AudiovisualCue/v1"

    def __post_init__(self) -> None:
        _required_text(self.cue_id, "AUDIOVISUAL_CUE_ID_REQUIRED")
        _required_text(self.cue_type, "AUDIOVISUAL_CUE_TYPE_REQUIRED")
        time_seconds = _finite(
            self.time_seconds,
            "AUDIOVISUAL_CUE_TIME_INVALID",
        )
        strength = _finite(
            self.strength,
            "AUDIOVISUAL_CUE_STRENGTH_INVALID",
        )
        if time_seconds < 0.0:
            raise HazeWaveBridgeError(
                "AUDIOVISUAL_CUE_TIME_INVALID"
            )
        if not 0.0 <= strength <= 1.0:
            raise HazeWaveBridgeError(
                "AUDIOVISUAL_CUE_STRENGTH_INVALID"
            )
        if not self.editorial_hints:
            raise HazeWaveBridgeError(
                "AUDIOVISUAL_CUE_HINT_REQUIRED"
            )


@dataclass(frozen=True)
class AudiovisualCueSheet:
    source_master_sha256: str
    duration_seconds: float
    master_timing_approval_id: str
    cues: tuple[AudiovisualCue, ...]
    direction: str = CUE_DIRECTION
    authority: str = "NONE"
    grants_execution_authority: bool = False
    reverse_authority: bool = False
    schema: str = "AudiovisualCueSheet/v1"

    def __post_init__(self) -> None:
        if not _SHA256_RE.fullmatch(
            str(self.source_master_sha256 or "")
        ):
            raise HazeWaveBridgeError(
                "AUDIOVISUAL_CUE_SOURCE_SHA256_INVALID"
            )
        _required_text(
            self.master_timing_approval_id,
            "HAZE_WAVE_TIMING_APPROVAL_ID_REQUIRED",
        )
        if self.direction != CUE_DIRECTION:
            raise HazeWaveBridgeError(
                "HAZE_WAVE_DIRECTION_INVALID"
            )
        for cue in self.cues:
            if cue.time_seconds > self.duration_seconds + 1e-9:
                raise HazeWaveBridgeError(
                    "AUDIOVISUAL_CUE_OUT_OF_RANGE"
                )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["cues"] = [asdict(item) for item in self.cues]
        return value


def build_audiovisual_cue_sheet(
    structure: MusicStructure,
    *,
    master_timing_approved: bool,
    approval_id: str,
) -> AudiovisualCueSheet:
    if not isinstance(structure, MusicStructure):
        raise HazeWaveBridgeError(
            "HAZE_WAVE_MUSIC_STRUCTURE_REQUIRED"
        )
    approval = str(approval_id or "").strip()
    if not master_timing_approved or not approval:
        raise HazeWaveBridgeError(
            "HAZE_WAVE_TIMING_NOT_APPROVED"
        )

    cues: list[AudiovisualCue] = []

    for section in structure.sections:
        cues.append(
            AudiovisualCue(
                cue_id=f"section:{section.section_id}",
                cue_type="SECTION_BOUNDARY",
                time_seconds=section.start_seconds,
                strength=1.0,
                label=section.label,
                editorial_hints=(
                    "section_boundary",
                    "cut_candidate",
                    "transition_candidate",
                ),
            )
        )

    for event in structure.beats:
        cues.append(
            AudiovisualCue(
                cue_id=f"beat:{event.event_id}",
                cue_type="BEAT",
                time_seconds=event.time_seconds,
                strength=event.strength,
                editorial_hints=(
                    "rhythm_reference",
                    "editorial_pulse_candidate",
                ),
            )
        )

    for event in structure.transients:
        cues.append(
            AudiovisualCue(
                cue_id=f"transient:{event.event_id}",
                cue_type="TRANSIENT",
                time_seconds=event.time_seconds,
                strength=event.strength,
                editorial_hints=(
                    "cut_candidate",
                    "motion_accent_candidate",
                ),
            )
        )

    for event in structure.phrase_boundaries:
        cues.append(
            AudiovisualCue(
                cue_id=f"phrase:{event.event_id}",
                cue_type="PHRASE_BOUNDARY",
                time_seconds=event.time_seconds,
                strength=event.strength,
                editorial_hints=(
                    "phrase_boundary",
                    "transition_candidate",
                    "shot_change_candidate",
                ),
            )
        )

    for index, point in enumerate(structure.intensity, start=1):
        cues.append(
            AudiovisualCue(
                cue_id=f"intensity:{index:04d}",
                cue_type="INTENSITY",
                time_seconds=point.time_seconds,
                strength=point.normalized_intensity,
                editorial_hints=(
                    "motion_intensity_reference",
                    "visual_density_reference",
                ),
            )
        )

    order = {
        "SECTION_BOUNDARY": 0,
        "PHRASE_BOUNDARY": 1,
        "TRANSIENT": 2,
        "BEAT": 3,
        "INTENSITY": 4,
    }
    cues.sort(
        key=lambda cue: (
            cue.time_seconds,
            order.get(cue.cue_type, 99),
            cue.cue_id,
        )
    )

    return AudiovisualCueSheet(
        source_master_sha256=structure.source_master_sha256,
        duration_seconds=structure.duration_seconds,
        master_timing_approval_id=approval,
        cues=tuple(cues),
    )
