from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


class AnimationProductionError(RuntimeError):
    pass


def _required_text(value: str, code: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise AnimationProductionError(code)
    return text


def _required_tuple(values: tuple[str, ...], code: str) -> tuple[str, ...]:
    if not values or any(not str(item or "").strip() for item in values):
        raise AnimationProductionError(code)
    return tuple(str(item).strip() for item in values)


@dataclass(frozen=True)
class AnimationProductionKnowledge:
    pipeline_stages: tuple[str, ...]
    animation_principles: tuple[str, ...]
    cinematography_topics: tuple[str, ...]
    final_video_mode: str = "ANIMATED_CARTOON"
    authority: str = "NONE"
    grants_execution_authority: bool = False
    schema: str = "AnimationProductionKnowledge/v1"

    @classmethod
    def default(cls) -> "AnimationProductionKnowledge":
        return cls(
            pipeline_stages=(
                "concept-development",
                "visual-development",
                "character-style-bible",
                "storyboard",
                "animatic",
                "approved-timing",
                "layout",
                "staging",
                "key-poses",
                "breakdowns",
                "in-betweens",
                "clean-up",
                "ink-line",
                "color",
                "background",
                "fx",
                "compositing",
                "haze-audio-integration",
                "frame-sequence-render",
                "editorial-conform",
                "encode",
                "technical-qc",
                "creative-review",
                "human-review",
            ),
            animation_principles=(
                "key-poses",
                "extremes",
                "breakdowns",
                "in-betweens",
                "timing",
                "spacing",
                "holds",
                "ones-twos-threes",
                "arcs",
                "anticipation",
                "follow-through-overlap",
                "squash-stretch",
                "slow-in-slow-out",
                "secondary-action",
                "silhouette",
                "appeal",
            ),
            cinematography_topics=(
                "shot-size",
                "camera-height",
                "perspective-intent",
                "composition",
                "negative-space",
                "screen-direction",
                "180-degree-continuity",
                "eyelines",
                "match-action",
                "cut-motivation",
                "jl-audio-transitions",
                "pacing",
                "visual-rhythm",
                "reveals",
                "reaction-shots",
                "establishing-shots",
                "inserts",
                "montage",
                "camera-movement",
                "parallax",
                "depth-layers",
            ),
        )


@dataclass(frozen=True)
class ExposureSpan:
    frame_start: int
    frame_end: int
    pose_id: str
    exposure: str
    schema: str = "ExposureSpan/v1"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.frame_start, int)
            or not isinstance(self.frame_end, int)
            or self.frame_start < 0
            or self.frame_end < self.frame_start
        ):
            raise AnimationProductionError("EXPOSURE_SPAN_RANGE_INVALID")
        _required_text(self.pose_id, "EXPOSURE_SPAN_POSE_REQUIRED")
        if self.exposure not in {"ONES", "TWOS", "THREES", "HOLD", "CUSTOM"}:
            raise AnimationProductionError("EXPOSURE_SPAN_MODE_INVALID")


@dataclass(frozen=True)
class ExposureSheet:
    exposure_sheet_id: str
    shot_id: str
    fps: int
    frame_start: int
    frame_end: int
    spans: tuple[ExposureSpan, ...]
    schema: str = "ExposureSheet/v1"

    def __post_init__(self) -> None:
        _required_text(self.exposure_sheet_id, "EXPOSURE_SHEET_ID_REQUIRED")
        _required_text(self.shot_id, "EXPOSURE_SHEET_SHOT_REQUIRED")
        if not isinstance(self.fps, int) or self.fps <= 0:
            raise AnimationProductionError("EXPOSURE_SHEET_FPS_INVALID")
        if (
            not isinstance(self.frame_start, int)
            or not isinstance(self.frame_end, int)
            or self.frame_start < 0
            or self.frame_end < self.frame_start
        ):
            raise AnimationProductionError("EXPOSURE_SHEET_RANGE_INVALID")
        if not self.spans:
            raise AnimationProductionError("EXPOSURE_SHEET_FRAME_COVERAGE_INVALID")

        expected = self.frame_start
        for span in self.spans:
            if span.frame_start != expected:
                raise AnimationProductionError(
                    "EXPOSURE_SHEET_FRAME_COVERAGE_INVALID"
                )
            expected = span.frame_end + 1
        if expected != self.frame_end + 1:
            raise AnimationProductionError(
                "EXPOSURE_SHEET_FRAME_COVERAGE_INVALID"
            )

    @property
    def frame_count(self) -> int:
        return self.frame_end - self.frame_start + 1

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["spans"] = [asdict(span) for span in self.spans]
        return value


@dataclass(frozen=True)
class AnimationShot:
    shot_id: str
    scene_id: str
    duration_seconds: float
    fps: int
    aspect_ratio: str
    shot_scale: str
    camera: Mapping[str, str]
    composition: Mapping[str, str]
    characters: tuple[str, ...]
    poses: tuple[str, ...]
    action: str
    dialogue: tuple[str, ...]
    audio_refs: tuple[str, ...]
    background: str
    foreground: tuple[str, ...]
    props: tuple[str, ...]
    lighting_color_intent: str
    entry_continuity_id: str
    exit_continuity_id: str
    animation_technique: str
    frame_exposure_plan: str
    render_dependencies: tuple[str, ...]
    final_video_mode: str = "ANIMATED_CARTOON"
    schema: str = "AnimationShot/v1"

    def __post_init__(self) -> None:
        for value, code in (
            (self.shot_id, "ANIMATION_SHOT_ID_REQUIRED"),
            (self.scene_id, "ANIMATION_SHOT_SCENE_REQUIRED"),
            (self.aspect_ratio, "ANIMATION_SHOT_ASPECT_REQUIRED"),
            (self.shot_scale, "ANIMATION_SHOT_SCALE_REQUIRED"),
            (self.action, "ANIMATION_SHOT_ACTION_REQUIRED"),
            (self.background, "ANIMATION_SHOT_BACKGROUND_REQUIRED"),
            (
                self.lighting_color_intent,
                "ANIMATION_SHOT_LIGHTING_COLOR_REQUIRED",
            ),
            (
                self.entry_continuity_id,
                "ANIMATION_SHOT_ENTRY_CONTINUITY_REQUIRED",
            ),
            (
                self.exit_continuity_id,
                "ANIMATION_SHOT_EXIT_CONTINUITY_REQUIRED",
            ),
            (
                self.animation_technique,
                "ANIMATION_SHOT_TECHNIQUE_REQUIRED",
            ),
            (
                self.frame_exposure_plan,
                "ANIMATION_SHOT_EXPOSURE_PLAN_REQUIRED",
            ),
        ):
            _required_text(value, code)

        if self.final_video_mode != "ANIMATED_CARTOON":
            raise AnimationProductionError("ANIMATION_SHOT_FINAL_MODE_INVALID")
        if self.duration_seconds <= 0:
            raise AnimationProductionError("ANIMATION_SHOT_DURATION_INVALID")
        if not isinstance(self.fps, int) or self.fps <= 0:
            raise AnimationProductionError("ANIMATION_SHOT_FPS_INVALID")
        if not isinstance(self.camera, Mapping) or not self.camera:
            raise AnimationProductionError("ANIMATION_SHOT_CAMERA_REQUIRED")
        if not isinstance(self.composition, Mapping) or not self.composition:
            raise AnimationProductionError(
                "ANIMATION_SHOT_COMPOSITION_REQUIRED"
            )
        _required_tuple(
            self.characters,
            "ANIMATION_SHOT_CHARACTERS_REQUIRED",
        )
        _required_tuple(self.poses, "ANIMATION_SHOT_POSES_REQUIRED")
        _required_tuple(
            self.audio_refs,
            "ANIMATION_SHOT_AUDIO_REFS_REQUIRED",
        )
        _required_tuple(
            self.render_dependencies,
            "ANIMATION_SHOT_RENDER_DEPENDENCIES_REQUIRED",
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["camera"] = dict(self.camera)
        value["composition"] = dict(self.composition)
        return value


@dataclass(frozen=True)
class ShotPlan:
    shot_plan_id: str
    scene_id: str
    shots: tuple[AnimationShot, ...]
    schema: str = "ShotPlan/v1"

    def __post_init__(self) -> None:
        _required_text(self.shot_plan_id, "SHOT_PLAN_ID_REQUIRED")
        _required_text(self.scene_id, "SHOT_PLAN_SCENE_REQUIRED")
        if not self.shots:
            raise AnimationProductionError("SHOT_PLAN_SHOTS_REQUIRED")

        seen: set[str] = set()
        previous: AnimationShot | None = None
        for shot in self.shots:
            if shot.scene_id != self.scene_id:
                raise AnimationProductionError("SHOT_PLAN_SCENE_MISMATCH")
            if shot.shot_id in seen:
                raise AnimationProductionError("SHOT_PLAN_DUPLICATE_SHOT_ID")
            seen.add(shot.shot_id)
            if (
                previous is not None
                and previous.exit_continuity_id != shot.entry_continuity_id
            ):
                raise AnimationProductionError("SHOT_PLAN_CONTINUITY_BROKEN")
            previous = shot

    @property
    def shot_count(self) -> int:
        return len(self.shots)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "shot_plan_id": self.shot_plan_id,
            "scene_id": self.scene_id,
            "shot_count": self.shot_count,
            "shots": [shot.to_dict() for shot in self.shots],
        }


@dataclass(frozen=True)
class AnimationDirectionDecision:
    shot_id: str
    production_intent: str
    selected_principles: tuple[str, ...]
    required_competencies: tuple[str, ...]
    cinematography_checks: tuple[str, ...]
    reason: str
    authority: str = "NONE"
    grants_execution_authority: bool = False
    schema: str = "AnimationDirectionDecision/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["selected_principles"] = list(self.selected_principles)
        value["required_competencies"] = list(self.required_competencies)
        value["cinematography_checks"] = list(self.cinematography_checks)
        return value


class AnimationDirector:
    def __init__(self, knowledge: AnimationProductionKnowledge) -> None:
        if knowledge.final_video_mode != "ANIMATED_CARTOON":
            raise AnimationProductionError(
                "ANIMATION_DIRECTOR_KNOWLEDGE_MODE_INVALID"
            )
        self.knowledge = knowledge

    def reason_for_shot(
        self,
        *,
        shot: AnimationShot,
        production_intent: str,
        dialogue_present: bool,
        high_energy_action: bool,
    ) -> AnimationDirectionDecision:
        intent = _required_text(
            production_intent,
            "ANIMATION_DIRECTION_INTENT_REQUIRED",
        ).casefold()

        principles: list[str] = ["timing", "spacing", "silhouette"]
        competencies: list[str] = [
            "continuity-reasoning",
            "shot-composition",
            "animation-construction",
        ]

        technique = shot.animation_technique.casefold()
        quiet_or_hold = (
            "hold" in technique
            or "quiet" in intent
            or "reaction" in intent
        )
        if quiet_or_hold:
            principles.append("holds")
            competencies.append("pose-readability")

        if high_energy_action:
            principles.extend(
                (
                    "anticipation",
                    "arcs",
                    "follow-through-overlap",
                    "slow-in-slow-out",
                )
            )
            competencies.extend(
                ("action-staging", "motion-continuity")
            )

        if dialogue_present:
            competencies.append("lip-sync-performance")
            principles.append("secondary-action")

        if "pose-to-pose" in technique:
            principles.extend(("key-poses", "breakdowns", "in-betweens"))

        selected_principles = tuple(dict.fromkeys(principles))
        required_competencies = tuple(dict.fromkeys(competencies))
        cinematography_checks = (
            "composition",
            "negative-space",
            "screen-direction",
            "180-degree-continuity",
            "eyelines",
            "cut-motivation",
        )

        unsupported = set(selected_principles).difference(
            self.knowledge.animation_principles
        )
        if unsupported:
            raise AnimationProductionError(
                "ANIMATION_DIRECTION_PRINCIPLE_NOT_IN_KNOWLEDGE"
            )

        return AnimationDirectionDecision(
            shot_id=shot.shot_id,
            production_intent=production_intent,
            selected_principles=selected_principles,
            required_competencies=required_competencies,
            cinematography_checks=cinematography_checks,
            reason=(
                "Selected animation principles and competencies from the "
                "shot technique, motion energy, dialogue state and stated "
                "production intent. No principle is treated as mandatory "
                "for every shot."
            ),
        )
