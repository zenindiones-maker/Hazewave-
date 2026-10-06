from __future__ import annotations

import pytest

from hazewave.expertise_acceptance import (
    ExpertiseAcceptanceError,
    ExpertiseAcceptanceEvaluator,
    ExpertiseCaseEvidence,
)


CANDIDATE = "c" * 40


def _case(
    *,
    expertise: str,
    case_id: str,
    proof_id: str,
    decision_digest: str,
    artifact_digest: str,
    human_preference_applied: bool = False,
    passed: bool = True,
    evidence_type: str = "RUNTIME_PROVEN",
    candidate_head: str = CANDIDATE,
) -> ExpertiseCaseEvidence:
    return ExpertiseCaseEvidence(
        expertise=expertise,
        case_id=case_id,
        proof_id=proof_id,
        evidence_type=evidence_type,
        candidate_head=candidate_head,
        runtime_identity="codespace:fixture",
        decision_digest=decision_digest,
        artifact_digest=artifact_digest,
        explanation=(
            f"Case {case_id} selected a bounded strategy from runtime evidence "
            "and verified the resulting artifact."
        ),
        technical_verification_passed=passed,
        human_preference_applied=human_preference_applied,
        evidence_digest=(proof_id.replace("-", "") + "0" * 64)[:64],
    )


def test_haze_reaper_expertise_requires_five_distinct_runtime_cases() -> None:
    evaluator = ExpertiseAcceptanceEvaluator(candidate_head=CANDIDATE)
    cases = (
        _case(
            expertise="HAZE_REAPER_EXPERT",
            case_id="clean-transparent",
            proof_id="proof-clean",
            decision_digest="1" * 64,
            artifact_digest="a" * 64,
        ),
        _case(
            expertise="HAZE_REAPER_EXPERT",
            case_id="colored-character",
            proof_id="proof-colored",
            decision_digest="2" * 64,
            artifact_digest="b" * 64,
        ),
        _case(
            expertise="HAZE_REAPER_EXPERT",
            case_id="dub-send-fx",
            proof_id="proof-dub",
            decision_digest="3" * 64,
            artifact_digest="c" * 64,
            human_preference_applied=True,
        ),
        _case(
            expertise="HAZE_REAPER_EXPERT",
            case_id="dynamic-control",
            proof_id="proof-dynamics",
            decision_digest="4" * 64,
            artifact_digest="d" * 64,
        ),
        _case(
            expertise="HAZE_REAPER_EXPERT",
            case_id="mix-bus-master",
            proof_id="proof-master",
            decision_digest="5" * 64,
            artifact_digest="e" * 64,
        ),
    )

    receipt = evaluator.evaluate(
        expertise="HAZE_REAPER_EXPERT",
        cases=cases,
    )

    assert receipt.schema == "ExpertiseAcceptanceReceipt/v1"
    assert receipt.status == "PASS"
    assert receipt.candidate_head == CANDIDATE
    assert receipt.acceptance_cases == (
        "clean-transparent",
        "colored-character",
        "dub-send-fx",
        "dynamic-control",
        "mix-bus-master",
    )
    assert receipt.runtime_proven is True
    assert receipt.distinct_proofs is True
    assert receipt.distinct_decisions is True
    assert receipt.human_preference_learning_proven is True
    assert receipt.grants_execution_authority is False


def test_wave_video_expertise_requires_editorial_scene_color_render_and_qc_cases() -> None:
    evaluator = ExpertiseAcceptanceEvaluator(candidate_head=CANDIDATE)
    required = (
        "editorial-reasoning",
        "scene-analysis",
        "color-management",
        "conform-render",
        "video-qc",
    )
    cases = tuple(
        _case(
            expertise="WAVE_VIDEO_EXPERT",
            case_id=case_id,
            proof_id=f"wave-{index}",
            decision_digest=f"{index}" * 64,
            artifact_digest=f"{(index + 5) % 16:x}" * 64,
            human_preference_applied=index == 1,
        )
        for index, case_id in enumerate(required, start=1)
    )

    receipt = evaluator.evaluate(
        expertise="WAVE_VIDEO_EXPERT",
        cases=cases,
    )

    assert receipt.status == "PASS"
    assert receipt.acceptance_cases == required


def test_wave_cartoon_expertise_requires_all_distinct_animation_cases() -> None:
    evaluator = ExpertiseAcceptanceEvaluator(candidate_head=CANDIDATE)
    required = (
        "storyboard-reasoning",
        "timing-reasoning",
        "character-continuity",
        "shot-continuity",
        "animation-construction",
        "compositing",
        "final-qc",
    )
    cases = tuple(
        _case(
            expertise="WAVE_CARTOON_EXPERT",
            case_id=case_id,
            proof_id=f"cartoon-{index}",
            decision_digest=f"{index}" * 64,
            artifact_digest=f"{(index + 7) % 10}" * 64,
            human_preference_applied=index == 2,
        )
        for index, case_id in enumerate(required, start=1)
    )

    receipt = evaluator.evaluate(
        expertise="WAVE_CARTOON_EXPERT",
        cases=cases,
    )

    assert receipt.status == "PASS"
    assert receipt.acceptance_cases == required


def test_missing_required_case_is_not_proven() -> None:
    evaluator = ExpertiseAcceptanceEvaluator(candidate_head=CANDIDATE)
    cases = (
        _case(
            expertise="HAZE_REAPER_EXPERT",
            case_id="clean-transparent",
            proof_id="proof-clean",
            decision_digest="1" * 64,
            artifact_digest="a" * 64,
            human_preference_applied=True,
        ),
    )

    receipt = evaluator.evaluate(
        expertise="HAZE_REAPER_EXPERT",
        cases=cases,
    )

    assert receipt.status == "NOT_PROVEN"
    assert "colored-character" in receipt.missing_cases
    assert receipt.runtime_proven is False


def test_ci_only_evidence_can_never_prove_expertise() -> None:
    evaluator = ExpertiseAcceptanceEvaluator(candidate_head=CANDIDATE)
    cases = (
        _case(
            expertise="HAZE_REAPER_EXPERT",
            case_id="clean-transparent",
            proof_id="proof-clean",
            decision_digest="1" * 64,
            artifact_digest="a" * 64,
            evidence_type="CI_PROVEN",
            human_preference_applied=True,
        ),
    )

    with pytest.raises(
        ExpertiseAcceptanceError,
        match="EXPERTISE_CASE_RUNTIME_EVIDENCE_REQUIRED",
    ):
        evaluator.evaluate(
            expertise="HAZE_REAPER_EXPERT",
            cases=cases,
        )


def test_case_bound_to_different_candidate_is_rejected() -> None:
    evaluator = ExpertiseAcceptanceEvaluator(candidate_head=CANDIDATE)
    bad = _case(
        expertise="HAZE_REAPER_EXPERT",
        case_id="clean-transparent",
        proof_id="proof-clean",
        decision_digest="1" * 64,
        artifact_digest="a" * 64,
        candidate_head="d" * 40,
        human_preference_applied=True,
    )

    with pytest.raises(
        ExpertiseAcceptanceError,
        match="EXPERTISE_CASE_HEAD_MISMATCH",
    ):
        evaluator.evaluate(
            expertise="HAZE_REAPER_EXPERT",
            cases=(bad,),
        )


def test_duplicate_proof_ids_cannot_satisfy_multiple_cases() -> None:
    evaluator = ExpertiseAcceptanceEvaluator(candidate_head=CANDIDATE)
    cases = (
        _case(
            expertise="HAZE_REAPER_EXPERT",
            case_id="clean-transparent",
            proof_id="same-proof",
            decision_digest="1" * 64,
            artifact_digest="a" * 64,
            human_preference_applied=True,
        ),
        _case(
            expertise="HAZE_REAPER_EXPERT",
            case_id="colored-character",
            proof_id="same-proof",
            decision_digest="2" * 64,
            artifact_digest="b" * 64,
        ),
    )

    with pytest.raises(
        ExpertiseAcceptanceError,
        match="EXPERTISE_CASE_PROOF_REUSED",
    ):
        evaluator.evaluate(
            expertise="HAZE_REAPER_EXPERT",
            cases=cases,
        )


def test_same_decision_signature_replayed_across_cases_is_rejected() -> None:
    evaluator = ExpertiseAcceptanceEvaluator(candidate_head=CANDIDATE)
    cases = (
        _case(
            expertise="HAZE_REAPER_EXPERT",
            case_id="clean-transparent",
            proof_id="proof-clean",
            decision_digest="1" * 64,
            artifact_digest="a" * 64,
            human_preference_applied=True,
        ),
        _case(
            expertise="HAZE_REAPER_EXPERT",
            case_id="colored-character",
            proof_id="proof-colored",
            decision_digest="1" * 64,
            artifact_digest="b" * 64,
        ),
    )

    with pytest.raises(
        ExpertiseAcceptanceError,
        match="EXPERTISE_CASE_DECISION_REPLAY",
    ):
        evaluator.evaluate(
            expertise="HAZE_REAPER_EXPERT",
            cases=cases,
        )


def test_failed_technical_verification_cannot_prove_case() -> None:
    evaluator = ExpertiseAcceptanceEvaluator(candidate_head=CANDIDATE)
    failed = _case(
        expertise="HAZE_REAPER_EXPERT",
        case_id="clean-transparent",
        proof_id="proof-clean",
        decision_digest="1" * 64,
        artifact_digest="a" * 64,
        human_preference_applied=True,
        passed=False,
    )

    receipt = evaluator.evaluate(
        expertise="HAZE_REAPER_EXPERT",
        cases=(failed,),
    )

    assert receipt.status == "NOT_PROVEN"
    assert "clean-transparent" in receipt.failed_cases


def test_expertise_requires_at_least_one_runtime_case_using_human_preference() -> None:
    evaluator = ExpertiseAcceptanceEvaluator(candidate_head=CANDIDATE)
    required = (
        "clean-transparent",
        "colored-character",
        "dub-send-fx",
        "dynamic-control",
        "mix-bus-master",
    )
    cases = tuple(
        _case(
            expertise="HAZE_REAPER_EXPERT",
            case_id=case_id,
            proof_id=f"proof-{index}",
            decision_digest=f"{index}" * 64,
            artifact_digest=f"{index + 4}" * 64,
        )
        for index, case_id in enumerate(required, start=1)
    )

    receipt = evaluator.evaluate(
        expertise="HAZE_REAPER_EXPERT",
        cases=cases,
    )

    assert receipt.status == "NOT_PROVEN"
    assert receipt.human_preference_learning_proven is False


def test_explanation_is_required_for_each_runtime_case() -> None:
    with pytest.raises(
        ExpertiseAcceptanceError,
        match="EXPERTISE_CASE_EXPLANATION_REQUIRED",
    ):
        ExpertiseCaseEvidence(
            expertise="HAZE_REAPER_EXPERT",
            case_id="clean-transparent",
            proof_id="proof-clean",
            evidence_type="RUNTIME_PROVEN",
            candidate_head=CANDIDATE,
            runtime_identity="codespace:fixture",
            decision_digest="1" * 64,
            artifact_digest="a" * 64,
            explanation="",
            technical_verification_passed=True,
            human_preference_applied=True,
            evidence_digest="f" * 64,
        )
