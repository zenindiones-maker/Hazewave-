from __future__ import annotations

import pytest

from hazewave.music_production_knowledge import (
    ListeningReasoningEngine,
    MusicProductionBrief,
    MusicProductionKnowledgeRegistry,
    MusicProductionPlanner,
)


def test_default_genre_registry_contains_required_specialisms_without_authority() -> None:
    registry = MusicProductionKnowledgeRegistry.default()
    snapshot = registry.snapshot()

    assert snapshot["schema"] == "MusicProductionKnowledge/v1"
    assert snapshot["authority"] == "NONE"
    assert snapshot["grants_execution_authority"] is False

    genre_ids = {item["genre_id"] for item in snapshot["genre_profiles"]}
    assert {
        "dub-reggae",
        "hip-hop",
        "rock",
        "psychedelic",
        "electronic",
        "ambient",
        "cinematic",
        "brazilian-contexts",
    }.issubset(genre_ids)

    assert all(item["fixed_preset"] is False for item in snapshot["genre_profiles"])
    assert all(item["human_refinement_required"] is True for item in snapshot["genre_profiles"])


def test_dub_profile_models_performance_topology_not_fixed_plugin_settings() -> None:
    registry = MusicProductionKnowledgeRegistry.default()
    dub = registry.genre_profile("dub-reggae")
    text = " ".join(dub.principles + dub.topologies).casefold()

    for concept in (
        "send-based delay",
        "feedback riding",
        "filtered repeats",
        "bass preservation",
        "automation as performance",
        "pre/post",
        "space as arrangement",
    ):
        assert concept in text

    assert dub.fixed_preset is False
    assert dub.default_parameter_values == {}


@pytest.mark.parametrize(
    "term",
    [
        "mud",
        "harshness",
        "boxiness",
        "nasality",
        "sibilance",
        "boom",
        "thinness",
        "masking",
        "depth",
        "width",
        "punch",
        "density",
        "air",
        "warmth",
        "brightness",
        "darkness",
        "glue",
        "movement",
        "contrast",
        "clarity",
    ],
)
def test_listening_ontology_treats_perceptual_language_as_hypothesis_not_numeric_truth(
    term: str,
) -> None:
    engine = ListeningReasoningEngine.default()
    concept = engine.concept(term)

    assert concept.term == term
    assert concept.numeric_truth is False
    assert concept.automatic_action is False
    assert concept.candidate_capabilities
    assert concept.evidence_candidates


def test_listening_reasoning_combines_observation_measurement_context_and_reference() -> None:
    engine = ListeningReasoningEngine.default()

    hypothesis = engine.hypothesize(
        term="mud",
        evidence={
            "low_mid_energy_ratio": 0.44,
            "section": "chorus",
        },
        context={
            "source": "mix-bus",
            "genre": "dub-reggae",
        },
        reference_features={
            "low_mid_energy_ratio": 0.31,
        },
    )

    assert hypothesis.schema == "ListeningHypothesis/v1"
    assert hypothesis.term == "mud"
    assert hypothesis.automatic_action is False
    assert hypothesis.artistic_truth_claimed is False
    assert "mix.eq" in hypothesis.candidate_capabilities
    assert hypothesis.evidence["low_mid_energy_ratio"] == pytest.approx(0.44)
    assert hypothesis.reference_features["low_mid_energy_ratio"] == pytest.approx(0.31)


def test_planner_makes_materially_different_strategies_for_distinct_briefs() -> None:
    planner = MusicProductionPlanner(
        registry=MusicProductionKnowledgeRegistry.default(),
    )

    clean = planner.plan(
        MusicProductionBrief(
            brief_id="clean",
            intent="CLEAN_TRANSPARENT",
            genre_id="rock",
            source_kind="vocal",
            desired_character=("transparent", "clear"),
            delivery_context="mix",
        )
    )
    colored = planner.plan(
        MusicProductionBrief(
            brief_id="colored",
            intent="COLORED_CHARACTER",
            genre_id="psychedelic",
            source_kind="guitar",
            desired_character=("warm", "saturated"),
            delivery_context="mix",
        )
    )
    dub = planner.plan(
        MusicProductionBrief(
            brief_id="dub",
            intent="DUB_SEND_FX",
            genre_id="dub-reggae",
            source_kind="drum-bus",
            desired_character=("warm", "moving"),
            delivery_context="mix",
        )
    )
    dynamics = planner.plan(
        MusicProductionBrief(
            brief_id="dynamic",
            intent="DYNAMIC_CONTROL",
            genre_id="hip-hop",
            source_kind="vocal",
            desired_character=("controlled", "punchy"),
            delivery_context="mix",
        )
    )
    master = planner.plan(
        MusicProductionBrief(
            brief_id="master",
            intent="MIX_BUS_MASTER",
            genre_id="electronic",
            source_kind="mix-bus",
            desired_character=("cohesive",),
            delivery_context="private-review-master",
        )
    )

    strategies = {
        tuple(clean.ordered_capabilities),
        tuple(colored.ordered_capabilities),
        tuple(dub.ordered_capabilities),
        tuple(dynamics.ordered_capabilities),
        tuple(master.ordered_capabilities),
    }
    assert len(strategies) == 5

    assert "mix.saturation" not in clean.ordered_capabilities
    assert "mix.saturation" in colored.ordered_capabilities
    assert "routing.send" in dub.ordered_capabilities
    assert "mix.delay" in dub.ordered_capabilities
    assert "mix.automation" in dub.ordered_capabilities
    assert "mix.dynamics" in dynamics.ordered_capabilities
    assert master.ordered_capabilities[-3:] == (
        "master.prepare",
        "master.process",
        "master.render",
    )

    for strategy in (clean, colored, dub, dynamics, master):
        assert strategy.fixed_preset is False
        assert strategy.grants_execution_authority is False
        assert strategy.requires_snapshot is True
        assert strategy.requires_post_analysis is True


def test_planner_rejects_unknown_intent_instead_of_falling_back_to_generic_preset() -> None:
    planner = MusicProductionPlanner(
        registry=MusicProductionKnowledgeRegistry.default(),
    )

    with pytest.raises(ValueError, match="MUSIC_PRODUCTION_INTENT_UNSUPPORTED"):
        planner.plan(
            MusicProductionBrief(
                brief_id="bad",
                intent="MAKE_IT_GOOD",
                genre_id="ambient",
                source_kind="mix",
                desired_character=(),
                delivery_context="mix",
            )
        )
