from __future__ import annotations

from pathlib import Path

import pytest

from hazewave.creative_memory import (
    CreativeMemoryError,
    CreativeMemoryStore,
    HumanPreferenceSignal,
    MixDecision,
    ProductionReview,
)


def _decision() -> MixDecision:
    return MixDecision(
        decision_id="mix-001",
        scope="genre:dub",
        capability="mix.delay",
        tool_id="tape-echo-2",
        parameter_summary={"mix": 0.42, "feedback": 0.61},
        rationale="Warm send-based delay with bounded feedback.",
        evidence_digest="a" * 64,
    )


def _signal(
    signal_id: str,
    *,
    dimension: str,
    score: float,
    source_review_id: str = "review-001",
) -> HumanPreferenceSignal:
    return HumanPreferenceSignal(
        signal_id=signal_id,
        scope="genre:dub",
        dimension=dimension,
        preference_score=score,
        source_review_id=source_review_id,
        evidence_digest="b" * 64,
    )


def test_creative_memory_persists_human_approved_preferences_outside_code(
    tmp_path: Path,
) -> None:
    store = CreativeMemoryStore(tmp_path)
    decision = _decision()
    store.record_decision(decision)
    review = ProductionReview(
        review_id="review-001",
        decision_id=decision.decision_id,
        artifact_sha256="c" * 64,
        technical_status="PASS",
        creative_decision="ACCEPT",
        human_outcome="APPROVED",
        notes="Keep the dub return warm but not dominant.",
        preference_signals=(
            _signal("signal-001", dimension="delay_warmth", score=0.8),
            _signal("signal-002", dimension="effect_prominence", score=-0.25),
        ),
    )
    store.record_review(review)

    reopened = CreativeMemoryStore(tmp_path)
    snapshot = reopened.snapshot()

    assert snapshot["schema"] == "CreativeMemoryStore/v1"
    assert snapshot["authority"] == "NONE"
    assert snapshot["grants_execution_authority"] is False
    assert snapshot["can_publish"] is False
    assert snapshot["can_modify_canonical_policy"] is False
    assert len(snapshot["decisions"]) == 1
    assert len(snapshot["reviews"]) == 1
    assert len(snapshot["preference_signals"]) == 2
    assert (tmp_path / "creative-memory-v1.json").is_file()


def test_preference_summary_combines_global_and_scope_specific_human_signals(
    tmp_path: Path,
) -> None:
    store = CreativeMemoryStore(tmp_path)
    decision = _decision()
    store.record_decision(decision)

    store.record_review(
        ProductionReview(
            review_id="review-001",
            decision_id=decision.decision_id,
            artifact_sha256="c" * 64,
            technical_status="PASS",
            creative_decision="ACCEPT",
            human_outcome="APPROVED",
            notes="",
            preference_signals=(
                _signal("signal-001", dimension="bass_weight", score=0.7),
            ),
        )
    )
    global_signal = HumanPreferenceSignal(
        signal_id="signal-global",
        scope="global",
        dimension="bass_weight",
        preference_score=0.3,
        source_review_id="review-002",
        evidence_digest="d" * 64,
    )
    store.record_decision(
        MixDecision(
            decision_id="mix-002",
            scope="global",
            capability="mix.balance",
            tool_id="REAPER_NATIVE",
            parameter_summary={},
            rationale="Global balance preference fixture.",
            evidence_digest="e" * 64,
        )
    )
    store.record_review(
        ProductionReview(
            review_id="review-002",
            decision_id="mix-002",
            artifact_sha256="f" * 64,
            technical_status="PASS",
            creative_decision="ACCEPT",
            human_outcome="APPROVED",
            notes="",
            preference_signals=(global_signal,),
        )
    )

    summary = store.preference_summary(
        scope="genre:dub",
        dimension="bass_weight",
        include_global=True,
    )

    assert summary.schema == "HumanPreferenceSummary/v1"
    assert summary.signal_count == 2
    assert summary.preference_score == pytest.approx(0.5)
    assert summary.grants_execution_authority is False


def test_pending_or_machine_only_review_cannot_create_human_preference_signal(
    tmp_path: Path,
) -> None:
    store = CreativeMemoryStore(tmp_path)
    store.record_decision(_decision())

    with pytest.raises(
        CreativeMemoryError,
        match="CREATIVE_MEMORY_HUMAN_OUTCOME_REQUIRED_FOR_SIGNALS",
    ):
        store.record_review(
            ProductionReview(
                review_id="review-001",
                decision_id="mix-001",
                artifact_sha256="c" * 64,
                technical_status="PASS",
                creative_decision="HUMAN_REVIEW",
                human_outcome="PENDING",
                notes="Awaiting owner.",
                preference_signals=(
                    _signal("signal-001", dimension="vocal_prominence", score=0.8),
                ),
            )
        )


def test_signal_must_be_bound_to_same_review_and_scope_as_decision(
    tmp_path: Path,
) -> None:
    store = CreativeMemoryStore(tmp_path)
    store.record_decision(_decision())

    with pytest.raises(
        CreativeMemoryError,
        match="CREATIVE_MEMORY_SIGNAL_REVIEW_MISMATCH",
    ):
        store.record_review(
            ProductionReview(
                review_id="review-001",
                decision_id="mix-001",
                artifact_sha256="c" * 64,
                technical_status="PASS",
                creative_decision="ACCEPT",
                human_outcome="APPROVED",
                notes="",
                preference_signals=(
                    _signal(
                        "signal-001",
                        dimension="vocal_prominence",
                        score=0.5,
                        source_review_id="other-review",
                    ),
                ),
            )
        )


def test_rejected_review_is_persisted_but_does_not_silently_invert_signal(
    tmp_path: Path,
) -> None:
    store = CreativeMemoryStore(tmp_path)
    store.record_decision(_decision())
    signal = _signal("signal-001", dimension="delay_warmth", score=-0.9)

    store.record_review(
        ProductionReview(
            review_id="review-001",
            decision_id="mix-001",
            artifact_sha256="c" * 64,
            technical_status="PASS",
            creative_decision="REVISE",
            human_outcome="REJECTED",
            notes="Too dark and smeared.",
            preference_signals=(signal,),
        )
    )

    summary = store.preference_summary(
        scope="genre:dub",
        dimension="delay_warmth",
        include_global=False,
    )
    assert summary.preference_score == pytest.approx(-0.9)
    assert summary.signal_count == 1


def test_duplicate_ids_fail_closed_instead_of_overwriting_history(tmp_path: Path) -> None:
    store = CreativeMemoryStore(tmp_path)
    decision = _decision()
    store.record_decision(decision)

    with pytest.raises(CreativeMemoryError, match="CREATIVE_MEMORY_DUPLICATE_DECISION_ID"):
        store.record_decision(decision)


def test_preference_score_is_bounded(tmp_path: Path) -> None:
    with pytest.raises(CreativeMemoryError, match="CREATIVE_MEMORY_PREFERENCE_SCORE_INVALID"):
        _signal("signal-bad", dimension="stereo_width", score=1.2)
