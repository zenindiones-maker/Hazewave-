from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import re
from typing import Any, Mapping


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_REQUIRED_TURNAROUND_VIEWS = frozenset({"front", "profile", "back"})


class AnimationAssetError(RuntimeError):
    pass


def _text(value: str, code: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise AnimationAssetError(code)
    if "\x00" in normalized or "\n" in normalized or "\r" in normalized:
        raise AnimationAssetError(code)
    return normalized


def _sha(value: str, code: str) -> str:
    normalized = str(value or "").strip()
    if not _SHA256_RE.fullmatch(normalized):
        raise AnimationAssetError(code)
    return normalized


def _palette(values: tuple[str, ...], code: str) -> tuple[str, ...]:
    if not values or not all(_HEX_COLOR_RE.fullmatch(str(item)) for item in values):
        raise AnimationAssetError(code)
    if len(set(item.upper() for item in values)) != len(values):
        raise AnimationAssetError(code)
    return values


def _string_tuple(values: tuple[str, ...], code: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise AnimationAssetError(code)
    if not allow_empty and not values:
        raise AnimationAssetError(code)
    normalized = tuple(_text(item, code) for item in values)
    if len(set(normalized)) != len(normalized):
        raise AnimationAssetError(code)
    return normalized


def _positive_measurements(values: Mapping[str, float], code: str) -> dict[str, float]:
    if not isinstance(values, Mapping) or not values:
        raise AnimationAssetError(code)
    result: dict[str, float] = {}
    for key, raw in values.items():
        name = _text(str(key), code)
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise AnimationAssetError(code) from exc
        if not math.isfinite(value) or value <= 0:
            raise AnimationAssetError(code)
        result[name] = value
    return result


@dataclass(frozen=True)
class CharacterBible:
    character_id: str
    name: str
    silhouette: str
    proportions: Mapping[str, float]
    palette: tuple[str, ...]
    line_language: str
    costume_signature: tuple[str, ...]
    allowed_deformation: tuple[str, ...]
    signature_poses: tuple[str, ...]
    grants_execution_authority: bool = False
    schema: str = "CharacterBible/v1"

    def __post_init__(self) -> None:
        _text(self.character_id, "CHARACTER_BIBLE_ID_REQUIRED")
        _text(self.name, "CHARACTER_BIBLE_NAME_REQUIRED")
        _text(self.silhouette, "CHARACTER_BIBLE_SILHOUETTE_REQUIRED")
        _positive_measurements(self.proportions, "CHARACTER_BIBLE_PROPORTIONS_INVALID")
        _palette(self.palette, "CHARACTER_BIBLE_PALETTE_INVALID")
        _text(self.line_language, "CHARACTER_BIBLE_LINE_LANGUAGE_REQUIRED")
        _string_tuple(self.costume_signature, "CHARACTER_BIBLE_COSTUME_INVALID")
        _string_tuple(self.allowed_deformation, "CHARACTER_BIBLE_DEFORMATION_INVALID")
        _string_tuple(self.signature_poses, "CHARACTER_BIBLE_POSES_INVALID")


@dataclass(frozen=True)
class ModelView:
    view_id: str
    angle_degrees: float
    asset_sha256: str
    relative_measurements: Mapping[str, float]
    schema: str = "CharacterModelView/v1"

    def __post_init__(self) -> None:
        _text(self.view_id, "CHARACTER_MODEL_VIEW_ID_REQUIRED")
        try:
            angle = float(self.angle_degrees)
        except (TypeError, ValueError) as exc:
            raise AnimationAssetError("CHARACTER_MODEL_VIEW_ANGLE_INVALID") from exc
        if not math.isfinite(angle) or angle < -360.0 or angle > 360.0:
            raise AnimationAssetError("CHARACTER_MODEL_VIEW_ANGLE_INVALID")
        _sha(self.asset_sha256, "CHARACTER_MODEL_VIEW_SHA_INVALID")
        _positive_measurements(
            self.relative_measurements,
            "CHARACTER_MODEL_VIEW_MEASUREMENTS_INVALID",
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["relative_measurements"] = dict(self.relative_measurements)
        return value


@dataclass(frozen=True)
class CharacterModelSheet:
    character_id: str
    views: tuple[ModelView, ...]
    grants_execution_authority: bool = False
    schema: str = "CharacterModelSheet/v1"

    def __post_init__(self) -> None:
        _text(self.character_id, "CHARACTER_MODEL_SHEET_ID_REQUIRED")
        if not self.views or not all(isinstance(item, ModelView) for item in self.views):
            raise AnimationAssetError("CHARACTER_MODEL_SHEET_VIEWS_INVALID")
        ids = tuple(item.view_id for item in self.views)
        if len(set(ids)) != len(ids):
            raise AnimationAssetError("CHARACTER_MODEL_SHEET_DUPLICATE_VIEW")
        if not _REQUIRED_TURNAROUND_VIEWS.issubset(set(ids)):
            raise AnimationAssetError("CHARACTER_MODEL_SHEET_REQUIRED_VIEWS")

    def digest(self) -> str:
        payload = {
            "schema": self.schema,
            "character_id": self.character_id,
            "views": [item.to_dict() for item in self.views],
        }
        material = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return sha256(material).hexdigest()


@dataclass(frozen=True)
class CharacterTurnaround:
    character_id: str
    model_sheet_digest: str
    required_views: tuple[str, ...]
    grants_execution_authority: bool = False
    schema: str = "CharacterTurnaround/v1"

    def __post_init__(self) -> None:
        _text(self.character_id, "CHARACTER_TURNAROUND_ID_REQUIRED")
        _sha(self.model_sheet_digest, "CHARACTER_TURNAROUND_DIGEST_INVALID")
        views = _string_tuple(
            self.required_views,
            "CHARACTER_TURNAROUND_VIEWS_INVALID",
        )
        if not _REQUIRED_TURNAROUND_VIEWS.issubset(set(views)):
            raise AnimationAssetError("CHARACTER_TURNAROUND_REQUIRED_VIEWS")


@dataclass(frozen=True)
class ExpressionDefinition:
    expression_id: str
    traits: tuple[str, ...]
    asset_sha256: str
    schema: str = "ExpressionDefinition/v1"

    def __post_init__(self) -> None:
        _text(self.expression_id, "EXPRESSION_ID_REQUIRED")
        _string_tuple(self.traits, "EXPRESSION_TRAITS_INVALID")
        _sha(self.asset_sha256, "EXPRESSION_ASSET_SHA_INVALID")


@dataclass(frozen=True)
class ExpressionSheet:
    character_id: str
    expressions: tuple[ExpressionDefinition, ...]
    grants_execution_authority: bool = False
    schema: str = "ExpressionSheet/v1"

    def __post_init__(self) -> None:
        _text(self.character_id, "EXPRESSION_SHEET_CHARACTER_REQUIRED")
        if not self.expressions:
            raise AnimationAssetError("EXPRESSION_SHEET_EMPTY")
        ids = [item.expression_id for item in self.expressions]
        if len(set(ids)) != len(ids):
            raise AnimationAssetError("EXPRESSION_SHEET_DUPLICATE_ID")


@dataclass(frozen=True)
class PoseDefinition:
    pose_id: str
    silhouette_intent: str
    balance: str
    asset_sha256: str
    schema: str = "PoseDefinition/v1"

    def __post_init__(self) -> None:
        _text(self.pose_id, "POSE_ID_REQUIRED")
        _text(self.silhouette_intent, "POSE_SILHOUETTE_REQUIRED")
        _text(self.balance, "POSE_BALANCE_REQUIRED")
        _sha(self.asset_sha256, "POSE_ASSET_SHA_INVALID")


@dataclass(frozen=True)
class PoseLibrary:
    character_id: str
    poses: tuple[PoseDefinition, ...]
    grants_execution_authority: bool = False
    schema: str = "PoseLibrary/v1"

    def __post_init__(self) -> None:
        _text(self.character_id, "POSE_LIBRARY_CHARACTER_REQUIRED")
        if not self.poses:
            raise AnimationAssetError("POSE_LIBRARY_EMPTY")
        ids = [item.pose_id for item in self.poses]
        if len(set(ids)) != len(ids):
            raise AnimationAssetError("POSE_LIBRARY_DUPLICATE_ID")


@dataclass(frozen=True)
class MouthShape:
    viseme_id: str
    phoneme_classes: tuple[str, ...]
    schema: str = "MouthShape/v1"

    def __post_init__(self) -> None:
        _text(self.viseme_id, "MOUTH_SHAPE_VISEME_REQUIRED")
        _string_tuple(
            self.phoneme_classes,
            "MOUTH_SHAPE_PHONEMES_INVALID",
        )


@dataclass(frozen=True)
class MouthShapeSet:
    character_id: str
    language: str
    shapes: tuple[MouthShape, ...]
    grants_execution_authority: bool = False
    schema: str = "MouthShapeSet/v1"

    def __post_init__(self) -> None:
        _text(self.character_id, "MOUTH_SHAPE_CHARACTER_REQUIRED")
        _text(self.language, "MOUTH_SHAPE_LANGUAGE_REQUIRED")
        if not self.shapes:
            raise AnimationAssetError("MOUTH_SHAPE_SET_EMPTY")
        ids = [item.viseme_id for item in self.shapes]
        if len(set(ids)) != len(ids):
            raise AnimationAssetError("MOUTH_SHAPE_DUPLICATE_VISEME")


@dataclass(frozen=True)
class PropDefinition:
    prop_id: str
    identity_traits: tuple[str, ...]
    palette: tuple[str, ...]
    asset_sha256: str
    schema: str = "PropDefinition/v1"

    def __post_init__(self) -> None:
        _text(self.prop_id, "PROP_ID_REQUIRED")
        _string_tuple(self.identity_traits, "PROP_IDENTITY_TRAITS_INVALID")
        _palette(self.palette, "PROP_PALETTE_INVALID")
        _sha(self.asset_sha256, "PROP_ASSET_SHA_INVALID")


@dataclass(frozen=True)
class PropBible:
    production_id: str
    props: tuple[PropDefinition, ...]
    grants_execution_authority: bool = False
    schema: str = "PropBible/v1"

    def __post_init__(self) -> None:
        _text(self.production_id, "PROP_BIBLE_PRODUCTION_REQUIRED")
        if not self.props:
            raise AnimationAssetError("PROP_BIBLE_EMPTY")
        ids = [item.prop_id for item in self.props]
        if len(set(ids)) != len(ids):
            raise AnimationAssetError("PROP_BIBLE_DUPLICATE_ID")


@dataclass(frozen=True)
class EnvironmentBible:
    production_id: str
    environment_id: str
    shape_language: str
    palette: tuple[str, ...]
    perspective_rules: tuple[str, ...]
    continuity_landmarks: tuple[str, ...]
    grants_execution_authority: bool = False
    schema: str = "EnvironmentBible/v1"

    def __post_init__(self) -> None:
        _text(self.production_id, "ENVIRONMENT_BIBLE_PRODUCTION_REQUIRED")
        _text(self.environment_id, "ENVIRONMENT_BIBLE_ID_REQUIRED")
        _text(self.shape_language, "ENVIRONMENT_BIBLE_SHAPE_LANGUAGE_REQUIRED")
        _palette(self.palette, "ENVIRONMENT_BIBLE_PALETTE_INVALID")
        _string_tuple(
            self.perspective_rules,
            "ENVIRONMENT_BIBLE_PERSPECTIVE_RULES_INVALID",
        )
        _string_tuple(
            self.continuity_landmarks,
            "ENVIRONMENT_BIBLE_LANDMARKS_INVALID",
        )


@dataclass(frozen=True)
class StyleBible:
    production_id: str
    final_video_mode: str
    shape_language: str
    line_language: str
    palette: tuple[str, ...]
    value_structure: str
    texture_language: str
    shadow_grammar: str
    highlight_grammar: str
    motion_language: str
    camera_language: str
    frame_cadence: str
    fx_grammar: str
    typography: str
    compositing_treatment: str
    human_owner_override_id: str | None = None
    postprocess_filter_only: bool = False
    grants_execution_authority: bool = False
    schema: str = "StyleBible/v1"

    def __post_init__(self) -> None:
        _text(self.production_id, "STYLE_BIBLE_PRODUCTION_REQUIRED")
        mode = _text(self.final_video_mode, "STYLE_BIBLE_FINAL_VIDEO_MODE_REQUIRED")
        override = (
            str(self.human_owner_override_id or "").strip()
            if self.human_owner_override_id is not None
            else ""
        )
        if mode != "ANIMATED_CARTOON" and not override:
            raise AnimationAssetError("STYLE_BIBLE_FINAL_VIDEO_MODE_FORBIDDEN")
        for value, code in (
            (self.shape_language, "STYLE_BIBLE_SHAPE_LANGUAGE_REQUIRED"),
            (self.line_language, "STYLE_BIBLE_LINE_LANGUAGE_REQUIRED"),
            (self.value_structure, "STYLE_BIBLE_VALUE_STRUCTURE_REQUIRED"),
            (self.texture_language, "STYLE_BIBLE_TEXTURE_LANGUAGE_REQUIRED"),
            (self.shadow_grammar, "STYLE_BIBLE_SHADOW_GRAMMAR_REQUIRED"),
            (self.highlight_grammar, "STYLE_BIBLE_HIGHLIGHT_GRAMMAR_REQUIRED"),
            (self.motion_language, "STYLE_BIBLE_MOTION_LANGUAGE_REQUIRED"),
            (self.camera_language, "STYLE_BIBLE_CAMERA_LANGUAGE_REQUIRED"),
            (self.frame_cadence, "STYLE_BIBLE_FRAME_CADENCE_REQUIRED"),
            (self.fx_grammar, "STYLE_BIBLE_FX_GRAMMAR_REQUIRED"),
            (self.typography, "STYLE_BIBLE_TYPOGRAPHY_REQUIRED"),
            (self.compositing_treatment, "STYLE_BIBLE_COMPOSITING_REQUIRED"),
        ):
            _text(value, code)
        _palette(self.palette, "STYLE_BIBLE_PALETTE_INVALID")
        if self.postprocess_filter_only:
            raise AnimationAssetError("STYLE_BIBLE_FILTER_ONLY_FORBIDDEN")


@dataclass(frozen=True)
class ColorBeat:
    beat_id: str
    start_seconds: float
    end_seconds: float
    palette: tuple[str, ...]
    value_intent: str
    emotional_intent: str
    schema: str = "ColorBeat/v1"

    def __post_init__(self) -> None:
        _text(self.beat_id, "COLOR_BEAT_ID_REQUIRED")
        try:
            start = float(self.start_seconds)
            end = float(self.end_seconds)
        except (TypeError, ValueError) as exc:
            raise AnimationAssetError("COLOR_BEAT_RANGE_INVALID") from exc
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
            raise AnimationAssetError("COLOR_BEAT_RANGE_INVALID")
        _palette(self.palette, "COLOR_BEAT_PALETTE_INVALID")
        _text(self.value_intent, "COLOR_BEAT_VALUE_INTENT_REQUIRED")
        _text(self.emotional_intent, "COLOR_BEAT_EMOTIONAL_INTENT_REQUIRED")


@dataclass(frozen=True)
class ColorScript:
    production_id: str
    beats: tuple[ColorBeat, ...]
    grants_execution_authority: bool = False
    schema: str = "ColorScript/v1"

    def __post_init__(self) -> None:
        _text(self.production_id, "COLOR_SCRIPT_PRODUCTION_REQUIRED")
        if not self.beats:
            raise AnimationAssetError("COLOR_SCRIPT_EMPTY")
        seen: set[str] = set()
        previous_end: float | None = None
        for beat in self.beats:
            if beat.beat_id in seen:
                raise AnimationAssetError("COLOR_SCRIPT_DUPLICATE_BEAT")
            seen.add(beat.beat_id)
            if previous_end is not None and beat.start_seconds < previous_end - 1e-9:
                raise AnimationAssetError("COLOR_SCRIPT_OVERLAP")
            previous_end = beat.end_seconds


@dataclass(frozen=True)
class ContinuityState:
    shot_id: str
    character_id: str
    costume_id: str
    held_props: tuple[str, ...]
    environment_id: str
    pose_entry: str | None = None
    pose_exit: str | None = None
    expression_entry: str | None = None
    expression_exit: str | None = None
    screen_position_entry: str | None = None
    screen_position_exit: str | None = None
    screen_direction_entry: str | None = None
    screen_direction_exit: str | None = None
    discontinuity_override_id: str | None = None
    grants_execution_authority: bool = False
    schema: str = "ContinuityState/v1"

    def __post_init__(self) -> None:
        _text(self.shot_id, "CONTINUITY_SHOT_ID_REQUIRED")
        _text(self.character_id, "CONTINUITY_CHARACTER_ID_REQUIRED")
        _text(self.costume_id, "CONTINUITY_COSTUME_ID_REQUIRED")
        _text(self.environment_id, "CONTINUITY_ENVIRONMENT_ID_REQUIRED")
        _string_tuple(
            self.held_props,
            "CONTINUITY_PROPS_INVALID",
            allow_empty=True,
        )
        for value in (
            self.pose_entry,
            self.pose_exit,
            self.expression_entry,
            self.expression_exit,
            self.screen_position_entry,
            self.screen_position_exit,
            self.screen_direction_entry,
            self.screen_direction_exit,
        ):
            if value is not None:
                _text(value, "CONTINUITY_FIELD_INVALID")
        if self.discontinuity_override_id is not None:
            _text(
                self.discontinuity_override_id,
                "CONTINUITY_OVERRIDE_ID_INVALID",
            )


@dataclass(frozen=True)
class ContinuityTransition:
    previous_shot_id: str
    next_shot_id: str
    status: str
    mismatches: tuple[str, ...]
    discontinuity_override_id: str | None
    grants_execution_authority: bool = False
    schema: str = "ContinuityTransition/v1"


def validate_continuity_transition(
    previous: ContinuityState,
    next_state: ContinuityState,
) -> ContinuityTransition:
    if not isinstance(previous, ContinuityState) or not isinstance(next_state, ContinuityState):
        raise AnimationAssetError("CONTINUITY_STATE_REQUIRED")

    mismatches: list[str] = []

    if previous.character_id != next_state.character_id:
        mismatches.append("character_id")
    if previous.costume_id != next_state.costume_id:
        mismatches.append("costume_id")
    if previous.environment_id != next_state.environment_id:
        mismatches.append("environment_id")
    if tuple(sorted(previous.held_props)) != tuple(sorted(next_state.held_props)):
        mismatches.append("held_props")

    paired = (
        ("pose", previous.pose_exit, next_state.pose_entry),
        ("expression", previous.expression_exit, next_state.expression_entry),
        (
            "screen_position",
            previous.screen_position_exit,
            next_state.screen_position_entry,
        ),
        (
            "screen_direction",
            previous.screen_direction_exit,
            next_state.screen_direction_entry,
        ),
    )
    for name, exit_value, entry_value in paired:
        if exit_value is not None and entry_value is not None and exit_value != entry_value:
            mismatches.append(name)
        elif (exit_value is None) != (entry_value is None):
            mismatches.append(name)

    override = (
        str(next_state.discontinuity_override_id).strip()
        if next_state.discontinuity_override_id is not None
        else None
    )

    if mismatches and not override:
        raise AnimationAssetError(
            "CONTINUITY_STATE_MISMATCH:" + ",".join(mismatches)
        )

    return ContinuityTransition(
        previous_shot_id=previous.shot_id,
        next_shot_id=next_state.shot_id,
        status="OVERRIDDEN" if mismatches else "PASS",
        mismatches=tuple(mismatches),
        discontinuity_override_id=override if mismatches else None,
    )
