from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from hazewave.colibri import ColibriDecisionResult
from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.reflex import (
    ReflexDecisionError,
    append_reflex_outcome,
    build_reflex_outcome,
    evaluate_reflex_outcomes,
    execute_reflex_choice,
    govern_reflex_result,
    load_reflex_outcomes,
    load_reflex_policy,
    reflex_recalibration_readiness,
    validate_reflex_request,
)


ROOT = Path(__file__).resolve().parents[1]


def _authorization(capability: str = "decision.route"):
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id=f"reflex-{capability}",
                goal="Bounded local reflex decision",
                required_capability=capability,
                requested_domain=HAZE,
            )
        )
    )


def _calibrated_policy(*capabilities: str) -> dict:
    policy = load_reflex_policy(ROOT / "config/reflex-governor-v1.json")
    cloned = json.loads(json.dumps(policy))
    for capability in capabilities or ("decision.route",):
        cloned["profiles"][capability]["production_calibrated"] = True
    return cloned


def _result(
    probabilities: dict[str, float],
    *,
    choice: str | None = None,
    confidence: float,
    latency_ms: float = 120.0,
    question_id: str = "q",
) -> ColibriDecisionResult:
    if choice is None:
        choice = max(probabilities, key=probabilities.get)
    return ColibriDecisionResult(
        model_id="laya",
        answers={
            question_id: {
                "type": "choice",
                "choice": choice,
                "probabilities": probabilities,
                "confidence": confidence,
            }
        },
        request_sha256="a" * 64,
        response_sha256="b" * 64,
        latency_ms=latency_ms,
        usage={"cost": 0},
    )


def test_reflex_policy_validates_against_schema() -> None:
    schema = json.loads(
        (ROOT / "schemas/reflex-governor-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    config = json.loads(
        (ROOT / "config/reflex-governor-v1.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(config)
    loaded = load_reflex_policy(ROOT / "config/reflex-governor-v1.json")
    assert loaded["safety"]["raw_system_one_confidence_is_correctness_probability"] is False
    assert loaded["safety"]["auto_threshold_mutation"] is False
    assert loaded["profiles"]["decision.route"]["production_calibrated"] is False


def test_small_label_route_can_be_accepted_as_recommendation() -> None:
    verdict = govern_reflex_result(
        authorization=_authorization(),
        result=_result(
            {"HAZE": 0.90, "WAVE": 0.07, "BRIDGE": 0.03},
            confidence=0.85,
            choice="HAZE",
        ),
        question_id="q",
        policy=_calibrated_policy("decision.route"),
    )

    assert verdict.disposition == "ACCEPT_RECOMMENDATION"
    assert verdict.grants_execution_authority is False
    assert verdict.correctness_probability_claimed is False
    assert verdict.metrics.peak_probability == pytest.approx(0.90)
    assert verdict.metrics.system_one_confidence == pytest.approx(0.85)


def test_raw_system_one_confidence_semantics_drift_fails_closed() -> None:
    with pytest.raises(
        ReflexDecisionError,
        match="REFLEX_SYSTEM_ONE_CONFIDENCE_SEMANTICS_DRIFT",
    ):
        govern_reflex_result(
            authorization=_authorization(),
            result=_result(
                {"HAZE": 0.90, "WAVE": 0.10},
                confidence=0.10,
                choice="HAZE",
            ),
            question_id="q",
            policy=_calibrated_policy("decision.route"),
        )


def test_uncertain_route_escalates_instead_of_forcing_a_choice() -> None:
    verdict = govern_reflex_result(
        authorization=_authorization(),
        result=_result(
            {"HAZE": 0.60, "WAVE": 0.35, "BRIDGE": 0.05},
            confidence=0.40,
            choice="HAZE",
        ),
        question_id="q",
        policy=_calibrated_policy("decision.route"),
    )

    assert verdict.disposition == "ESCALATE"
    assert verdict.escalation_target == "ESCALATE_9ROUTER_REASON_DEEP"
    assert "PEAK_PROBABILITY_BELOW_THRESHOLD" in verdict.reasons
    assert verdict.grants_execution_authority is False


def test_gate_lane_remains_shadow_only_even_when_distribution_is_sharp() -> None:
    verdict = govern_reflex_result(
        authorization=_authorization("decision.gate"),
        result=_result(
            {"allow": 0.97, "deny": 0.03},
            confidence=0.94,
            choice="allow",
        ),
        question_id="q",
        policy=_calibrated_policy("decision.gate"),
    )

    assert verdict.disposition == "SHADOW_RECOMMENDATION"
    assert verdict.escalation_target == "REQUIRE_HUMAN_OR_DETERMINISTIC_RULE"
    assert verdict.reasons[0] == "PROFILE_SHADOW_ONLY"


def test_large_flat_taxonomy_requires_hierarchical_decision() -> None:
    criteria = {f"label-{index}": f"bucket {index}" for index in range(9)}
    with pytest.raises(
        ReflexDecisionError,
        match="REFLEX_REQUIRES_HIERARCHICAL_DECISION",
    ):
        validate_reflex_request(
            authorization=_authorization(),
            state={"kind": "internal"},
            questions={
                "route": {
                    "type": "choice",
                    "instructions": "choose the bucket",
                    "criteria": criteria,
                }
            },
            data_classification="INTERNAL_NON_SECRET",
        )


def test_private_media_and_credentials_do_not_enter_reflex_lane() -> None:
    question = {
        "q": {
            "type": "choice",
            "instructions": "route",
            "criteria": {"HAZE": "audio", "WAVE": "visual"},
        }
    }
    for classification, error in (
        ("CREDENTIAL", "REFLEX_CREDENTIAL_INPUT_FORBIDDEN"),
        ("PRIVATE_MEDIA", "REFLEX_RAW_PRIVATE_MEDIA_FORBIDDEN"),
    ):
        with pytest.raises(ReflexDecisionError, match=error):
            validate_reflex_request(
                authorization=_authorization(),
                state={"media_digest": "abc"},
                questions=question,
                data_classification=classification,
            )


def test_outcome_ledger_persists_digest_and_labels_not_raw_state(tmp_path: Path) -> None:
    accepted = govern_reflex_result(
        authorization=_authorization(),
        result=_result(
            {"HAZE": 0.90, "WAVE": 0.07, "BRIDGE": 0.03},
            confidence=0.85,
            choice="HAZE",
        ),
        question_id="q",
        policy=_calibrated_policy("decision.route"),
    )
    outcome = build_reflex_outcome(
        verdict=accepted,
        decision_key="domain.route.v1",
        actual_label="HAZE",
        label_source="HUMAN",
        label_evidence_digest="1" * 64,
        observed_at="2026-10-07T01:30:00+00:00",
    )
    path = tmp_path / "reflex" / "outcomes.jsonl"
    append_reflex_outcome(path, outcome)

    raw = path.read_text(encoding="utf-8")
    assert '"raw_state":' not in raw
    assert '"raw_state_persisted":false' in raw
    restored = load_reflex_outcomes(path)
    assert len(restored) == 1
    assert restored[0].outcome_id == outcome.outcome_id
    assert restored[0].request_sha256 == "a" * 64


def test_calibration_report_measures_coverage_risk_brier_and_latency() -> None:
    good = govern_reflex_result(
        authorization=_authorization(),
        result=_result(
            {"HAZE": 0.90, "WAVE": 0.07, "BRIDGE": 0.03},
            confidence=0.85,
            choice="HAZE",
            latency_ms=100.0,
        ),
        question_id="q",
        policy=_calibrated_policy("decision.route"),
    )
    uncertain = govern_reflex_result(
        authorization=_authorization(),
        result=_result(
            {"HAZE": 0.60, "WAVE": 0.35, "BRIDGE": 0.05},
            confidence=0.40,
            choice="HAZE",
            latency_ms=300.0,
        ),
        question_id="q",
        policy=_calibrated_policy("decision.route"),
    )
    outcomes = (
        build_reflex_outcome(
            verdict=good,
            decision_key="domain.route.v1",
            actual_label="HAZE",
            label_source="DETERMINISTIC",
            label_evidence_digest="3" * 64,
            observed_at="2026-10-07T01:30:00+00:00",
        ),
        build_reflex_outcome(
            verdict=uncertain,
            decision_key="domain.route.v1",
            actual_label="WAVE",
            label_source="HUMAN",
            label_evidence_digest="2" * 64,
            observed_at="2026-10-07T01:31:00+00:00",
        ),
    )

    report = evaluate_reflex_outcomes(outcomes)
    assert report.sample_count == 2
    assert report.actual_accept_count == 1
    assert report.threshold_eligible_count == 1
    assert report.shadow_coverage == pytest.approx(0.5)
    assert report.accuracy == pytest.approx(0.5)
    assert report.selective_risk_if_activated == pytest.approx(0.0)
    assert report.multiclass_brier > 0
    assert report.latency_p50_ms == pytest.approx(200.0)
    assert report.latency_p95_ms == pytest.approx(290.0)


def test_recalibration_never_self_promotes_from_tiny_sample() -> None:
    verdict = govern_reflex_result(
        authorization=_authorization(),
        result=_result(
            {"HAZE": 0.90, "WAVE": 0.07, "BRIDGE": 0.03},
            confidence=0.85,
            choice="HAZE",
        ),
        question_id="q",
    )
    outcomes = (
        build_reflex_outcome(
            verdict=verdict,
            decision_key="domain.route.v1",
            actual_label="HAZE",
            label_source="HUMAN",
            label_evidence_digest="2" * 64,
            observed_at="2026-10-07T01:30:00+00:00",
        ),
    )

    readiness = reflex_recalibration_readiness(
        outcomes,
        decision_key="domain.route.v1",
    )
    assert readiness["ready"] is False
    assert readiness["minimum_total_required"] == 500
    assert readiness["minimum_key_required"] == 50
    assert readiness["auto_threshold_mutation"] is False
    assert readiness["auto_model_promotion"] is False


def test_selected_label_must_match_probability_argmax() -> None:
    with pytest.raises(
        ReflexDecisionError,
        match="REFLEX_SELECTED_LABEL_NOT_ARGMAX",
    ):
        govern_reflex_result(
            authorization=_authorization(),
            result=_result(
                {"HAZE": 0.10, "WAVE": 0.90},
                confidence=0.80,
                choice="HAZE",
            ),
            question_id="q",
            policy=_calibrated_policy("decision.route"),
        )



def test_default_route_policy_is_shadow_until_hazewave_calibration_exists() -> None:
    verdict = govern_reflex_result(
        authorization=_authorization(),
        result=_result(
            {"HAZE": 0.90, "WAVE": 0.07, "BRIDGE": 0.03},
            confidence=0.85,
            choice="HAZE",
        ),
        question_id="q",
    )

    assert verdict.disposition == "SHADOW_RECOMMENDATION"
    assert verdict.reasons[0] == "HAZEWAVE_CALIBRATION_REQUIRED"
    assert verdict.threshold_eligible is True
    assert verdict.grants_execution_authority is False



def test_high_level_reflex_execution_requires_deterministic_precheck() -> None:
    def fake_executor(**kwargs):
        return _result(
            {"HAZE": 0.90, "WAVE": 0.07, "BRIDGE": 0.03},
            confidence=0.85,
            choice="HAZE",
        )

    question = {
        "type": "choice",
        "instructions": "Which domain owns this structured task?",
        "criteria": {
            "HAZE": "audio",
            "WAVE": "visual",
            "BRIDGE": "typed cross-domain translation",
        },
    }

    with pytest.raises(
        ReflexDecisionError,
        match="REFLEX_DETERMINISTIC_PRECHECK_REQUIRED",
    ):
        execute_reflex_choice(
            authorization=_authorization(),
            question_id="q",
            state={"kind": "mix"},
            question=question,
            api_key="k" * 32,
            deterministic_precheck_complete=False,
            model_installed=True,
            model_revision_verified=True,
            executor=fake_executor,
        )

    verdict = execute_reflex_choice(
        authorization=_authorization(),
        question_id="q",
        state={"kind": "mix"},
        question=question,
        api_key="k" * 32,
        deterministic_precheck_complete=True,
        model_installed=True,
        model_revision_verified=True,
        executor=fake_executor,
    )
    assert verdict.disposition == "SHADOW_RECOMMENDATION"
    assert verdict.reasons[0] == "HAZEWAVE_CALIBRATION_REQUIRED"


def test_latency_budget_escalates_a_calibrated_route() -> None:
    verdict = govern_reflex_result(
        authorization=_authorization(),
        result=_result(
            {"HAZE": 0.95, "WAVE": 0.03, "BRIDGE": 0.02},
            confidence=0.925,
            choice="HAZE",
            latency_ms=3500.0,
        ),
        question_id="q",
        policy=_calibrated_policy("decision.route"),
    )

    assert verdict.disposition == "ESCALATE"
    assert "LATENCY_BUDGET_EXCEEDED" in verdict.reasons



def test_outcome_requires_label_evidence_digest() -> None:
    verdict = govern_reflex_result(
        authorization=_authorization(),
        result=_result(
            {"HAZE": 0.90, "WAVE": 0.07, "BRIDGE": 0.03},
            confidence=0.85,
            choice="HAZE",
        ),
        question_id="q",
    )
    with pytest.raises(ValueError, match="REFLEX_LABEL_EVIDENCE_DIGEST_INVALID"):
        build_reflex_outcome(
            verdict=verdict,
            decision_key="domain.route.v1",
            actual_label="HAZE",
            label_source="HUMAN",
            label_evidence_digest="not-a-digest",
            observed_at="2026-10-07T02:00:00+00:00",
        )


def test_calibration_refuses_mixed_policy_or_decision_cohorts() -> None:
    verdict = govern_reflex_result(
        authorization=_authorization(),
        result=_result(
            {"HAZE": 0.90, "WAVE": 0.07, "BRIDGE": 0.03},
            confidence=0.85,
            choice="HAZE",
        ),
        question_id="q",
    )
    first = build_reflex_outcome(
        verdict=verdict,
        decision_key="domain.route.v1",
        actual_label="HAZE",
        label_source="HUMAN",
        label_evidence_digest="4" * 64,
        observed_at="2026-10-07T02:00:00+00:00",
    )
    second = build_reflex_outcome(
        verdict=verdict,
        decision_key="different.route.v1",
        actual_label="HAZE",
        label_source="HUMAN",
        label_evidence_digest="5" * 64,
        observed_at="2026-10-07T02:01:00+00:00",
    )
    with pytest.raises(ValueError, match="REFLEX_CALIBRATION_COHORT_MIXED"):
        evaluate_reflex_outcomes((first, second))



def test_outcome_ledger_detects_tampering(tmp_path: Path) -> None:
    verdict = govern_reflex_result(
        authorization=_authorization(),
        result=_result(
            {"HAZE": 0.90, "WAVE": 0.07, "BRIDGE": 0.03},
            confidence=0.85,
            choice="HAZE",
        ),
        question_id="q",
    )
    outcome = build_reflex_outcome(
        verdict=verdict,
        decision_key="domain.route.v1",
        actual_label="HAZE",
        label_source="HUMAN",
        label_evidence_digest="6" * 64,
        observed_at="2026-10-07T02:10:00+00:00",
    )
    path = tmp_path / "outcomes.jsonl"
    append_reflex_outcome(path, outcome)

    payload = json.loads(path.read_text(encoding="utf-8").strip())
    payload["actual_label"] = "WAVE"
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="REFLEX_OUTCOME_DIGEST_MISMATCH"):
        load_reflex_outcomes(path)


def test_transport_timeout_is_separate_from_latency_eligibility_budget() -> None:
    captured = {}

    def fake_executor(**kwargs):
        captured.update(kwargs)
        return _result(
            {"HAZE": 0.95, "WAVE": 0.03, "BRIDGE": 0.02},
            confidence=0.925,
            choice="HAZE",
            latency_ms=3500.0,
        )

    question = {
        "type": "choice",
        "instructions": "Which domain owns this structured task?",
        "criteria": {
            "HAZE": "audio",
            "WAVE": "visual",
            "BRIDGE": "typed cross-domain translation",
        },
    }

    verdict = execute_reflex_choice(
        authorization=_authorization(),
        question_id="q",
        state={"kind": "audio_mix"},
        question=question,
        api_key="k" * 32,
        deterministic_precheck_complete=True,
        model_installed=True,
        model_revision_verified=True,
        executor=fake_executor,
    )

    assert captured["timeout_seconds"] == pytest.approx(10.0)
    assert verdict.latency_ms == pytest.approx(3500.0)
    assert verdict.threshold_eligible is False
    assert "LATENCY_BUDGET_EXCEEDED" in verdict.reasons
    assert verdict.disposition == "SHADOW_RECOMMENDATION"


def test_reflex_policy_rejects_transport_timeout_below_latency_budget(
    tmp_path: Path,
) -> None:
    policy = json.loads(
        (ROOT / "config/reflex-governor-v1.json").read_text(encoding="utf-8")
    )
    policy["profiles"]["decision.route"]["transport_timeout_ms"] = 2000
    target = tmp_path / "bad-policy.json"
    target.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="REFLEX_TRANSPORT_TIMEOUT_BELOW_LATENCY_BUDGET",
    ):
        load_reflex_policy(target)
