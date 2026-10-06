from __future__ import annotations

import pytest

from hazewave.animation_production import (
    AnimationDirector,
    AnimationProductionError,
    AnimationProductionKnowledge,
    AnimationShot,
    ExposureSheet,
    ExposureSpan,
    ShotPlan,
)


def _shot(
    *,
    shot_id: str = "shot-002",
    entry_continuity_id: str = "continuity-001",
    exit_continuity_id: str = "continuity-002",
    technique: str = "GREASE_PENCIL_POSE_TO_POSE",
) -> AnimationShot:
    return AnimationShot(
        shot_id=shot_id,
        scene_id="scene-001",
        duration_seconds=3.0,
        fps=24,
        aspect_ratio="16:9",
        shot_scale="MEDIUM",
        camera={
            "height": "eye-level",
            "movement": "locked",
            "perspective_intent": "neutral",
        },
        composition={
            "subject_zone": "left-third",
            "negative_space": "screen-right",
            "screen_direction": "LEFT_TO_RIGHT",
        },
        characters=("hero",),
        poses=("anticipation", "contact", "settle"),
        action="Hero steps into frame and stops.",
        dialogue=(),
        audio_refs=("haze-master.wav#0.0-3.0",),
        background="alley-bg-v1",
        foreground=("foreground-pipe",),
        props=("radio",),
        lighting_color_intent="cool dusk with warm practical accent",
        entry_continuity_id=entry_continuity_id,
        exit_continuity_id=exit_continuity_id,
        animation_technique=technique,
        frame_exposure_plan="exposure-shot-002",
        render_dependencies=("hero-rig-v3", "alley-bg-v1"),
    )


def test_animation_production_knowledge_is_non_authoritative_and_cartoon_first() -> None:
    knowledge = AnimationProductionKnowledge.default()

    assert knowledge.schema == "AnimationProductionKnowledge/v1"
    assert knowledge.authority == "NONE"
    assert knowledge.grants_execution_authority is False
    assert knowledge.final_video_mode == "ANIMATED_CARTOON"
    assert "storyboard" in knowledge.pipeline_stages
    assert "animatic" in knowledge.pipeline_stages
    assert "layout" in knowledge.pipeline_stages
    assert "key-poses" in knowledge.pipeline_stages
    assert "breakdowns" in knowledge.pipeline_stages
    assert "in-betweens" in knowledge.pipeline_stages
    assert "compositing" in knowledge.pipeline_stages
    assert "human-review" in knowledge.pipeline_stages
    assert "screen-direction" in knowledge.cinematography_topics
    assert "180-degree-continuity" in knowledge.cinematography_topics
    assert "negative-space" in knowledge.cinematography_topics
    assert "timing" in knowledge.animation_principles
    assert "spacing" in knowledge.animation_principles
    assert "silhouette" in knowledge.animation_principles


def test_animation_shot_carries_full_scene_contract() -> None:
    shot = _shot()

    assert shot.schema == "AnimationShot/v1"
    assert shot.scene_id == "scene-001"
    assert shot.duration_seconds == pytest.approx(3.0)
    assert shot.fps == 24
    assert shot.aspect_ratio == "16:9"
    assert shot.entry_continuity_id == "continuity-001"
    assert shot.exit_continuity_id == "continuity-002"
    assert shot.frame_exposure_plan == "exposure-shot-002"
    assert shot.render_dependencies == ("hero-rig-v3", "alley-bg-v1")


def test_exposure_sheet_requires_complete_non_overlapping_frame_coverage() -> None:
    sheet = ExposureSheet(
        exposure_sheet_id="exposure-shot-002",
        shot_id="shot-002",
        fps=24,
        frame_start=1,
        frame_end=72,
        spans=(
            ExposureSpan(
                frame_start=1,
                frame_end=12,
                pose_id="anticipation",
                exposure="TWOS",
            ),
            ExposureSpan(
                frame_start=13,
                frame_end=48,
                pose_id="contact",
                exposure="TWOS",
            ),
            ExposureSpan(
                frame_start=49,
                frame_end=72,
                pose_id="settle",
                exposure="THREES",
            ),
        ),
    )

    assert sheet.schema == "ExposureSheet/v1"
    assert sheet.frame_count == 72

    with pytest.raises(
        AnimationProductionError,
        match="EXPOSURE_SHEET_FRAME_COVERAGE_INVALID",
    ):
        ExposureSheet(
            exposure_sheet_id="bad",
            shot_id="shot-002",
            fps=24,
            frame_start=1,
            frame_end=72,
            spans=(
                ExposureSpan(
                    frame_start=1,
                    frame_end=10,
                    pose_id="anticipation",
                    exposure="TWOS",
                ),
                ExposureSpan(
                    frame_start=12,
                    frame_end=72,
                    pose_id="settle",
                    exposure="TWOS",
                ),
            ),
        )


def test_shot_plan_enforces_continuity_chain_between_adjacent_shots() -> None:
    first = _shot(
        shot_id="shot-001",
        entry_continuity_id="continuity-start",
        exit_continuity_id="continuity-shared",
    )
    second = _shot(
        shot_id="shot-002",
        entry_continuity_id="continuity-shared",
        exit_continuity_id="continuity-end",
    )

    plan = ShotPlan(
        shot_plan_id="scene-001-plan",
        scene_id="scene-001",
        shots=(first, second),
    )
    assert plan.schema == "ShotPlan/v1"
    assert plan.shot_count == 2

    broken = _shot(
        shot_id="shot-002",
        entry_continuity_id="wrong-continuity",
        exit_continuity_id="continuity-end",
    )
    with pytest.raises(
        AnimationProductionError,
        match="SHOT_PLAN_CONTINUITY_BROKEN",
    ):
        ShotPlan(
            shot_plan_id="bad",
            scene_id="scene-001",
            shots=(first, broken),
        )


def test_animation_director_selects_only_context_relevant_principles() -> None:
    director = AnimationDirector(AnimationProductionKnowledge.default())

    hold = director.reason_for_shot(
        shot=_shot(technique="LIMITED_HOLD"),
        production_intent="quiet reaction with readable silhouette",
        dialogue_present=False,
        high_energy_action=False,
    )
    action = director.reason_for_shot(
        shot=_shot(technique="GREASE_PENCIL_POSE_TO_POSE"),
        production_intent="fast physical action with strong direction change",
        dialogue_present=False,
        high_energy_action=True,
    )

    assert hold.schema == "AnimationDirectionDecision/v1"
    assert "silhouette" in hold.selected_principles
    assert "holds" in hold.selected_principles
    assert "squash-stretch" not in hold.selected_principles
    assert "anticipation" in action.selected_principles
    assert "arcs" in action.selected_principles
    assert "follow-through-overlap" in action.selected_principles
    assert hold.selected_principles != action.selected_principles


def test_animation_director_adds_lip_sync_only_when_dialogue_is_present() -> None:
    director = AnimationDirector(AnimationProductionKnowledge.default())

    no_dialogue = director.reason_for_shot(
        shot=_shot(),
        production_intent="silent establishing beat",
        dialogue_present=False,
        high_energy_action=False,
    )
    dialogue = director.reason_for_shot(
        shot=_shot(),
        production_intent="close reaction with PT-BR dialogue",
        dialogue_present=True,
        high_energy_action=False,
    )

    assert "lip-sync-performance" not in no_dialogue.required_competencies
    assert "lip-sync-performance" in dialogue.required_competencies


def test_animation_shot_rejects_photoreal_final_mode_override() -> None:
    with pytest.raises(
        AnimationProductionError,
        match="ANIMATION_SHOT_FINAL_MODE_INVALID",
    ):
        AnimationShot(
            **{
                **_shot().__dict__,
                "final_video_mode": "PHOTOREAL",
                "schema": "AnimationShot/v1",
            }
        )
