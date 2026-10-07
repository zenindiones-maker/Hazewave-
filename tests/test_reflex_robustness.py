from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from hazewave.colibri import ColibriDecisionResult
from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.reflex_robustness import (
    RiskCalibrationSample,
    aggregate_choice_answers,
    execute_robust_reflex_route,
    hoeffding_one_sided_upper_bound,
    load_robustness_policy,
    select_risk_threshold_candidate,
)


ROOT = Path(__file__).resolve().parents[1]


def _authorization():
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id="robust-route",
                goal="Robust shadow route",
                required_capability="decision.route",
                requested_domain=HAZE,
            )
        )
    )


def _question():
    return {
        "type": "choice",
        "instructions": "Select the best Hazewave domain.",
        "criteria": {
            "HAZE": "audio engineering",
            "WAVE": "visual production",
            "BRIDGE": "cross-domain coordination",
        },
    }


def _answer(probabilities: dict[str, float]) -> dict:
    winner = max(probabilities, key=probabilities.get)
    n = len(probabilities)
    confidence = (n * probabilities[winner] - 1.0) / (n - 1.0)
    return {
        "type": "choice",
        "choice": winner,
        "probabilities": probabilities,
        "confidence": confidence,
    }


def test_robustness_policy_schema_is_valid() -> None:
    schema = json.loads(
        (ROOT / "schemas/reflex-robustness-v1.schema.json").read_text()
    )
    policy = json.loads(
        (ROOT / "config/reflex-robustness-v1.json").read_text()
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(policy)
    loaded = load_robustness_policy()
    assert loaded["activation_state"] == "SHADOW_ONLY"
    assert loaded["risk_control"]["activation_authority"] == "NONE"
    ensemble = loaded["option_order_ensemble"]
    assert ensemble["strategy"] == "COMPLETE_PERMUTATIONS_IN_ONE_SYSTEM_ONE_BATCH"
    assert ensemble["max_labels"] == 3
    assert ensemble["max_rotations"] == 6


def test_order_ensemble_runs_all_three_domain_permutations_in_one_model_request() -> None:
    calls = []

    def executor(**kwargs):
        calls.append(kwargs)
        answers = {
            qid: _answer({"HAZE": 0.90, "WAVE": 0.07, "BRIDGE": 0.03})
            for qid in kwargs["questions"]
        }
        return ColibriDecisionResult(
            model_id="laya",
            answers=answers,
            request_sha256="a" * 64,
            response_sha256="b" * 64,
            latency_ms=410.0,
            usage={"cost": 0},
        )

    result = execute_robust_reflex_route(
        authorization=_authorization(),
        question_id="route",
        state={"kind": "audio_mix"},
        question=_question(),
        api_key="x" * 32,
        deterministic_precheck_complete=True,
        model_installed=True,
        model_revision_verified=True,
        executor=executor,
    )

    assert len(calls) == 1
    assert len(calls[0]["questions"]) == 6
    orders = [
        tuple(item["criteria"])
        for item in calls[0]["questions"].values()
    ]
    assert orders == [
        ("HAZE", "WAVE", "BRIDGE"),
        ("HAZE", "BRIDGE", "WAVE"),
        ("WAVE", "HAZE", "BRIDGE"),
        ("WAVE", "BRIDGE", "HAZE"),
        ("BRIDGE", "HAZE", "WAVE"),
        ("BRIDGE", "WAVE", "HAZE"),
    ]
    for position in range(3):
        assert sorted(order[position] for order in orders) == [
            "BRIDGE", "BRIDGE", "HAZE", "HAZE", "WAVE", "WAVE"
        ]
    assert result.ensemble.winner_agreement == 1.0
    assert result.ensemble.aggregate_winner == "HAZE"
    assert result.robust_eligible is True
    assert result.disposition == "SHADOW_RECOMMENDATION"
    assert result.grants_execution_authority is False


def test_order_sensitive_model_is_detected_and_not_robust_eligible() -> None:
    def executor(**kwargs):
        answers = {}
        for qid, question in kwargs["questions"].items():
            first = next(iter(question["criteria"]))
            probabilities = {label: 0.05 for label in question["criteria"]}
            probabilities[first] = 0.90
            total = sum(probabilities.values())
            probabilities = {k: v / total for k, v in probabilities.items()}
            answers[qid] = _answer(probabilities)
        return ColibriDecisionResult(
            model_id="laya",
            answers=answers,
            request_sha256="c" * 64,
            response_sha256="d" * 64,
            latency_ms=500.0,
            usage={"cost": 0},
        )

    result = execute_robust_reflex_route(
        authorization=_authorization(),
        question_id="route",
        state={"kind": "ambiguous"},
        question=_question(),
        api_key="y" * 32,
        deterministic_precheck_complete=True,
        model_installed=True,
        model_revision_verified=True,
        executor=executor,
    )

    assert result.ensemble.winner_agreement < 1.0
    assert "OPTION_ORDER_WINNER_DISAGREEMENT" in result.robustness_reasons
    assert result.robust_eligible is False
    assert result.disposition == "SHADOW_RECOMMENDATION"


def test_aggregate_rejects_label_set_drift() -> None:
    with pytest.raises(Exception, match="LABEL_SET_DRIFT"):
        aggregate_choice_answers(
            [
                _answer({"HAZE": 0.9, "WAVE": 0.1}),
                _answer({"HAZE": 0.9, "BRIDGE": 0.1}),
            ]
        )


def test_hoeffding_candidate_is_evidence_only_never_activation() -> None:
    samples = [
        RiskCalibrationSample(score=0.90, correct=True, stable=True)
        for _ in range(600)
    ] + [
        RiskCalibrationSample(score=0.20, correct=False, stable=True)
        for _ in range(150)
    ]
    candidate = select_risk_threshold_candidate(samples)

    assert candidate.status == "CANDIDATE_ONLY_HUMAN_REVIEW_REQUIRED"
    assert candidate.threshold == pytest.approx(0.90)
    assert candidate.accepted_samples == 600
    assert candidate.errors == 0
    assert candidate.risk_upper_bound is not None
    assert candidate.risk_upper_bound <= 0.05
    assert candidate.activation_authority == "NONE"
    assert candidate.automatic_activation is False


def test_risk_candidate_fails_closed_on_insufficient_evidence() -> None:
    candidate = select_risk_threshold_candidate(
        [RiskCalibrationSample(score=0.99, correct=True) for _ in range(50)]
    )
    assert candidate.status == "INSUFFICIENT_TOTAL_EVIDENCE"
    assert candidate.threshold is None


def test_hoeffding_bound_increases_with_errors() -> None:
    clean = hoeffding_one_sided_upper_bound(errors=0, sample_count=600, delta=0.05)
    noisy = hoeffding_one_sided_upper_bound(errors=20, sample_count=600, delta=0.05)
    assert 0 < clean < noisy < 1


def test_robust_route_uses_observation_deadline_wider_than_latency_gate() -> None:
    calls = []

    def executor(**kwargs):
        calls.append(kwargs)
        answers = {
            qid: _answer({"HAZE": 0.90, "WAVE": 0.07, "BRIDGE": 0.03})
            for qid in kwargs["questions"]
        }
        return ColibriDecisionResult(
            model_id="laya",
            answers=answers,
            request_sha256="e" * 64,
            response_sha256="f" * 64,
            latency_ms=3500.0,
            usage={"cost": 0},
        )

    result = execute_robust_reflex_route(
        authorization=_authorization(),
        question_id="route",
        state={"kind": "complex_labeled_observation"},
        question=_question(),
        api_key="z" * 32,
        deterministic_precheck_complete=True,
        model_installed=True,
        model_revision_verified=True,
        executor=executor,
    )

    assert calls[0]["timeout_seconds"] == 10.0
    assert result.base_verdict.threshold_eligible is False
    assert "LATENCY_BUDGET_EXCEEDED" in result.base_verdict.reasons
    assert result.disposition == "SHADOW_RECOMMENDATION"
