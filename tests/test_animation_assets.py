from __future__ import annotations

import pytest

from hazewave.animation_assets import (
    AnimationAssetError,
    CharacterBible,
    CharacterModelSheet,
    CharacterTurnaround,
    ColorBeat,
    ColorScript,
    ContinuityState,
    EnvironmentBible,
    ExpressionDefinition,
    ExpressionSheet,
    ModelView,
    MouthShape,
    MouthShapeSet,
    PoseDefinition,
    PoseLibrary,
    PropBible,
    PropDefinition,
    StyleBible,
    validate_continuity_transition,
)


def _sha(char: str) -> str:
    return char * 64


def _character_bible() -> CharacterBible:
    return CharacterBible(
        character_id="hero-001",
        name="Hero",
        silhouette="compact triangular torso with round head",
        proportions={
            "head_to_body": 0.33,
            "shoulder_to_height": 0.28,
            "eye_spacing_to_face": 0.24,
        },
        palette=("#112233", "#DDEEFF", "#FFB000"),
        line_language="clean dark line, medium weight",
        costume_signature=("blue-jacket", "white-shirt"),
        allowed_deformation=("squash-10-percent", "stretch-8-percent"),
        signature_poses=("neutral", "alert", "running"),
    )


def test_character_consistency_assets_are_identity_bound_and_non_authoritative() -> None:
    bible = _character_bible()
    model = CharacterModelSheet(
        character_id=bible.character_id,
        views=(
            ModelView(
                view_id="front",
                angle_degrees=0.0,
                asset_sha256=_sha("a"),
                relative_measurements={"head_width": 1.0, "body_height": 3.0},
            ),
            ModelView(
                view_id="profile",
                angle_degrees=90.0,
                asset_sha256=_sha("b"),
                relative_measurements={"head_width": 0.78, "body_height": 3.0},
            ),
            ModelView(
                view_id="back",
                angle_degrees=180.0,
                asset_sha256=_sha("c"),
                relative_measurements={"head_width": 1.0, "body_height": 3.0},
            ),
        ),
    )
    turnaround = CharacterTurnaround(
        character_id=bible.character_id,
        model_sheet_digest=model.digest(),
        required_views=("front", "profile", "back"),
    )

    assert bible.schema == "CharacterBible/v1"
    assert model.schema == "CharacterModelSheet/v1"
    assert turnaround.schema == "CharacterTurnaround/v1"
    assert model.character_id == bible.character_id
    assert turnaround.character_id == bible.character_id
    assert len(model.digest()) == 64
    assert bible.grants_execution_authority is False


def test_model_sheet_requires_front_profile_and_back_views() -> None:
    with pytest.raises(AnimationAssetError, match="CHARACTER_MODEL_SHEET_REQUIRED_VIEWS"):
        CharacterModelSheet(
            character_id="hero-001",
            views=(
                ModelView(
                    view_id="front",
                    angle_degrees=0.0,
                    asset_sha256=_sha("a"),
                    relative_measurements={"body_height": 3.0},
                ),
            ),
        )


def test_expression_pose_and_mouth_shape_assets_require_unique_semantic_ids() -> None:
    expressions = ExpressionSheet(
        character_id="hero-001",
        expressions=(
            ExpressionDefinition(
                expression_id="neutral",
                traits=("relaxed-brows", "closed-mouth"),
                asset_sha256=_sha("d"),
            ),
            ExpressionDefinition(
                expression_id="joy",
                traits=("raised-cheeks", "open-smile"),
                asset_sha256=_sha("e"),
            ),
        ),
    )
    poses = PoseLibrary(
        character_id="hero-001",
        poses=(
            PoseDefinition(
                pose_id="neutral",
                silhouette_intent="readable upright neutral",
                balance="centered",
                asset_sha256=_sha("f"),
            ),
            PoseDefinition(
                pose_id="anticipation",
                silhouette_intent="compressed backward anticipation",
                balance="rear-biased",
                asset_sha256=_sha("1"),
            ),
        ),
    )
    mouths = MouthShapeSet(
        character_id="hero-001",
        language="pt-BR",
        shapes=(
            MouthShape(viseme_id="REST", phoneme_classes=("silence", "hold")),
            MouthShape(viseme_id="A", phoneme_classes=("a", "ã", "á")),
            MouthShape(viseme_id="M", phoneme_classes=("m", "b", "p")),
        ),
    )

    assert expressions.schema == "ExpressionSheet/v1"
    assert poses.schema == "PoseLibrary/v1"
    assert mouths.schema == "MouthShapeSet/v1"
    assert mouths.language == "pt-BR"

    with pytest.raises(AnimationAssetError, match="MOUTH_SHAPE_DUPLICATE_VISEME"):
        MouthShapeSet(
            character_id="hero-001",
            language="pt-BR",
            shapes=(
                MouthShape(viseme_id="A", phoneme_classes=("a",)),
                MouthShape(viseme_id="A", phoneme_classes=("ã",)),
            ),
        )


def test_prop_environment_style_and_color_script_are_traceable_systems_not_filters() -> None:
    props = PropBible(
        production_id="cartoon-001",
        props=(
            PropDefinition(
                prop_id="radio",
                identity_traits=("rectangular-body", "single-antenna"),
                palette=("#202020", "#FFAA00"),
                asset_sha256=_sha("2"),
            ),
        ),
    )
    environment = EnvironmentBible(
        production_id="cartoon-001",
        environment_id="studio-room",
        shape_language="chunky geometric",
        palette=("#101820", "#243447", "#C7D4E8"),
        perspective_rules=("two-point-default", "horizon-eye-level"),
        continuity_landmarks=("window-left", "console-center"),
    )
    style = StyleBible(
        production_id="cartoon-001",
        final_video_mode="ANIMATED_CARTOON",
        shape_language="chunky geometric",
        line_language="clean medium dark line",
        palette=("#101820", "#C7D4E8", "#FFAA00"),
        value_structure="bright character against dark environment",
        texture_language="subtle paper grain",
        shadow_grammar="single hard graphic shadow",
        highlight_grammar="minimal edge highlight",
        motion_language="pose-to-pose with held accents",
        camera_language="graphic staging with motivated moves",
        frame_cadence="24fps mixed twos/ones",
        fx_grammar="drawn smears and restrained glow",
        typography="bold condensed sans",
        compositing_treatment="layered 2D/2.5D",
    )
    color = ColorScript(
        production_id="cartoon-001",
        beats=(
            ColorBeat(
                beat_id="opening",
                start_seconds=0.0,
                end_seconds=4.0,
                palette=("#101820", "#2B3B52"),
                value_intent="low-key",
                emotional_intent="anticipation",
            ),
            ColorBeat(
                beat_id="release",
                start_seconds=4.0,
                end_seconds=8.0,
                palette=("#203040", "#FFAA00"),
                value_intent="higher contrast",
                emotional_intent="release",
            ),
        ),
    )

    assert props.schema == "PropBible/v1"
    assert environment.schema == "EnvironmentBible/v1"
    assert style.schema == "StyleBible/v1"
    assert color.schema == "ColorScript/v1"
    assert style.final_video_mode == "ANIMATED_CARTOON"
    assert style.postprocess_filter_only is False


def test_style_bible_rejects_non_cartoon_final_mode_without_owner_override() -> None:
    with pytest.raises(AnimationAssetError, match="STYLE_BIBLE_FINAL_VIDEO_MODE_FORBIDDEN"):
        StyleBible(
            production_id="cartoon-001",
            final_video_mode="PHOTOREAL",
            shape_language="realistic",
            line_language="none",
            palette=("#000000", "#FFFFFF"),
            value_structure="naturalistic",
            texture_language="photo",
            shadow_grammar="physical",
            highlight_grammar="physical",
            motion_language="live-action",
            camera_language="live-action",
            frame_cadence="24fps",
            fx_grammar="photo",
            typography="sans",
            compositing_treatment="photo",
        )


def test_continuity_transition_requires_inherited_character_prop_and_screen_state() -> None:
    previous = ContinuityState(
        shot_id="shot-001",
        character_id="hero-001",
        costume_id="blue-jacket",
        pose_exit="standing-right",
        expression_exit="alert",
        screen_position_exit="RIGHT",
        screen_direction_exit="LEFT_TO_RIGHT",
        held_props=("radio",),
        environment_id="studio-room",
    )
    next_state = ContinuityState(
        shot_id="shot-002",
        character_id="hero-001",
        costume_id="blue-jacket",
        pose_entry="standing-right",
        expression_entry="alert",
        screen_position_entry="RIGHT",
        screen_direction_entry="LEFT_TO_RIGHT",
        held_props=("radio",),
        environment_id="studio-room",
    )

    result = validate_continuity_transition(previous, next_state)

    assert result.schema == "ContinuityTransition/v1"
    assert result.status == "PASS"
    assert result.discontinuity_override_id is None


def test_continuity_drift_fails_closed_without_explicit_owner_override() -> None:
    previous = ContinuityState(
        shot_id="shot-001",
        character_id="hero-001",
        costume_id="blue-jacket",
        pose_exit="standing-right",
        expression_exit="alert",
        screen_position_exit="RIGHT",
        screen_direction_exit="LEFT_TO_RIGHT",
        held_props=("radio",),
        environment_id="studio-room",
    )
    next_state = ContinuityState(
        shot_id="shot-002",
        character_id="hero-001",
        costume_id="red-jacket",
        pose_entry="standing-right",
        expression_entry="alert",
        screen_position_entry="LEFT",
        screen_direction_entry="RIGHT_TO_LEFT",
        held_props=(),
        environment_id="studio-room",
    )

    with pytest.raises(AnimationAssetError, match="CONTINUITY_STATE_MISMATCH"):
        validate_continuity_transition(previous, next_state)


def test_continuity_override_is_traceable_not_silent() -> None:
    previous = ContinuityState(
        shot_id="shot-001",
        character_id="hero-001",
        costume_id="blue-jacket",
        pose_exit="standing-right",
        expression_exit="alert",
        screen_position_exit="RIGHT",
        screen_direction_exit="LEFT_TO_RIGHT",
        held_props=("radio",),
        environment_id="studio-room",
    )
    next_state = ContinuityState(
        shot_id="shot-002",
        character_id="hero-001",
        costume_id="red-jacket",
        pose_entry="sitting",
        expression_entry="neutral",
        screen_position_entry="CENTER",
        screen_direction_entry="STATIC",
        held_props=(),
        environment_id="studio-room",
        discontinuity_override_id="human-owner-override-001",
    )

    result = validate_continuity_transition(previous, next_state)

    assert result.status == "OVERRIDDEN"
    assert result.discontinuity_override_id == "human-owner-override-001"
    assert result.mismatches
