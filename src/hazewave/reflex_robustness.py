from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from hazewave.colibri import ColibriDecisionResult, execute_colibri_system_one
from hazewave.harness import AUTHORITY, PROJECT_ID, HazewaveAuthorization, validate_authorization
from hazewave.reflex import (
    ReflexDecisionError,
    ReflexVerdict,
    govern_reflex_result,
    load_reflex_policy,
    validate_reflex_request,
)


DEFAULT_ROBUSTNESS_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "reflex-robustness-v1.json"
)


class ReflexRobustnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class OrderEnsembleMetrics:
    rotations: int
    labels: tuple[str, ...]
    per_rotation_winner: tuple[str, ...]
    winner_agreement: float
    normalized_jsd: float
    aggregate_probabilities: tuple[tuple[str, float], ...]
    aggregate_winner: str
    aggregate_peak_probability: float
    schema: str = "HazewaveOrderEnsembleMetrics/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["labels"] = list(self.labels)
        value["per_rotation_winner"] = list(self.per_rotation_winner)
        value["aggregate_probabilities"] = dict(self.aggregate_probabilities)
        return value


@dataclass(frozen=True)
class RobustReflexVerdict:
    base_verdict: ReflexVerdict
    ensemble: OrderEnsembleMetrics
    robust_eligible: bool
    robustness_reasons: tuple[str, ...]
    disposition: str
    escalation_target: str | None
    authority: str = AUTHORITY
    provider_authority: str = "NONE"
    grants_execution_authority: bool = False
    production_calibrated: bool = False
    schema: str = "HazewaveRobustReflexVerdict/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "authority": self.authority,
            "provider_authority": self.provider_authority,
            "grants_execution_authority": self.grants_execution_authority,
            "production_calibrated": self.production_calibrated,
            "robust_eligible": self.robust_eligible,
            "robustness_reasons": list(self.robustness_reasons),
            "disposition": self.disposition,
            "escalation_target": self.escalation_target,
            "ensemble": self.ensemble.to_dict(),
            "base_verdict": self.base_verdict.to_dict(),
        }


@dataclass(frozen=True)
class RiskCalibrationSample:
    score: float
    correct: bool
    stable: bool = True


@dataclass(frozen=True)
class RiskThresholdCandidate:
    status: str
    threshold: float | None
    accepted_samples: int
    errors: int
    empirical_risk: float | None
    risk_upper_bound: float | None
    target_risk: float
    delta: float
    total_samples: int
    activation_authority: str = "NONE"
    automatic_activation: bool = False
    schema: str = "HazewaveRiskThresholdCandidate/v1"


def load_robustness_policy(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else DEFAULT_ROBUSTNESS_POLICY_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("schema") != "HazewaveReflexRobustnessPolicy/v1":
        raise ValueError("REFLEX_ROBUSTNESS_POLICY_SCHEMA_INVALID")
    if payload.get("project_id") != PROJECT_ID or payload.get("authority") != AUTHORITY:
        raise ValueError("REFLEX_ROBUSTNESS_POLICY_AUTHORITY_INVALID")
    if payload.get("provider_authority") != "NONE":
        raise ValueError("REFLEX_ROBUSTNESS_PROVIDER_AUTHORITY_INVALID")
    if payload.get("activation_state") != "SHADOW_ONLY":
        raise ValueError("REFLEX_ROBUSTNESS_MUST_START_SHADOW_ONLY")
    ensemble = payload.get("option_order_ensemble") or {}
    if ensemble.get("enabled") is not True:
        raise ValueError("REFLEX_ORDER_ENSEMBLE_REQUIRED")
    if ensemble.get("strategy") != "CYCLIC_ROTATIONS_IN_ONE_SYSTEM_ONE_BATCH":
        raise ValueError("REFLEX_ORDER_ENSEMBLE_STRATEGY_INVALID")
    risk = payload.get("risk_control") or {}
    if risk.get("activation_authority") != "NONE" or risk.get("auto_threshold_mutation") is not False:
        raise ValueError("REFLEX_RISK_CONTROL_AUTHORITY_INVALID")
    return payload


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def robustness_policy_digest(policy: Mapping[str, Any]) -> str:
    return sha256(_canonical(dict(policy))).hexdigest()


def cyclic_choice_questions(
    *,
    question_id: str,
    question: Mapping[str, Any],
    max_rotations: int,
) -> dict[str, dict[str, Any]]:
    if str(question.get("type") or "") != "choice":
        raise ReflexRobustnessError("REFLEX_ROBUSTNESS_CHOICE_REQUIRED")
    criteria = question.get("criteria")
    if not isinstance(criteria, Mapping):
        raise ReflexRobustnessError("REFLEX_ROBUSTNESS_CRITERIA_INVALID")
    labels = [str(label) for label in criteria]
    if len(labels) < 2:
        raise ReflexRobustnessError("REFLEX_ROBUSTNESS_TOO_FEW_LABELS")
    rotations = min(len(labels), max(2, int(max_rotations)))
    result: dict[str, dict[str, Any]] = {}
    for offset in range(rotations):
        order = labels[offset:] + labels[:offset]
        rotated = {
            **dict(question),
            "criteria": {label: criteria[label] for label in order},
        }
        result[f"{question_id}__order_{offset}"] = rotated
    return result


def _normalized_distribution(answer: Mapping[str, Any]) -> dict[str, float]:
    probs = answer.get("probabilities")
    if not isinstance(probs, Mapping) or len(probs) < 2:
        raise ReflexRobustnessError("REFLEX_ROBUSTNESS_PROBABILITIES_REQUIRED")
    parsed: dict[str, float] = {}
    for raw_label, raw_value in probs.items():
        label = str(raw_label or "").strip()
        if not label or not isinstance(raw_value, (int, float)):
            raise ReflexRobustnessError("REFLEX_ROBUSTNESS_PROBABILITY_INVALID")
        value = float(raw_value)
        if not math.isfinite(value) or value < 0 or value > 1:
            raise ReflexRobustnessError("REFLEX_ROBUSTNESS_PROBABILITY_INVALID")
        parsed[label] = value
    total = sum(parsed.values())
    if total <= 0 or abs(total - 1.0) > 0.02:
        raise ReflexRobustnessError("REFLEX_ROBUSTNESS_PROBABILITY_MASS_INVALID")
    normalized = {label: value / total for label, value in parsed.items()}
    winner = str(answer.get("choice") or "").strip()
    if winner not in normalized:
        raise ReflexRobustnessError("REFLEX_ROBUSTNESS_WINNER_INVALID")
    argmax = max(normalized, key=normalized.get)
    if winner != argmax:
        raise ReflexRobustnessError("REFLEX_ROBUSTNESS_WINNER_NOT_ARGMAX")
    n = len(normalized)
    expected_confidence = (n * normalized[winner] - 1.0) / (n - 1.0)
    confidence = answer.get("confidence")
    if not isinstance(confidence, (int, float)):
        raise ReflexRobustnessError("REFLEX_ROBUSTNESS_CONFIDENCE_REQUIRED")
    if abs(float(confidence) - expected_confidence) > 0.03:
        raise ReflexRobustnessError("REFLEX_ROBUSTNESS_CONFIDENCE_SEMANTICS_DRIFT")
    return normalized


def _entropy(distribution: Mapping[str, float]) -> float:
    return -sum(value * math.log(value) for value in distribution.values() if value > 0)


def aggregate_choice_answers(
    answers: Sequence[Mapping[str, Any]],
) -> OrderEnsembleMetrics:
    if len(answers) < 2:
        raise ReflexRobustnessError("REFLEX_ROBUSTNESS_MULTIPLE_ROTATIONS_REQUIRED")
    distributions = [_normalized_distribution(answer) for answer in answers]
    labels = tuple(sorted(distributions[0]))
    if any(tuple(sorted(row)) != labels for row in distributions[1:]):
        raise ReflexRobustnessError("REFLEX_ROBUSTNESS_LABEL_SET_DRIFT")

    mean = {
        label: sum(row[label] for row in distributions) / len(distributions)
        for label in labels
    }
    mean_total = sum(mean.values())
    mean = {label: value / mean_total for label, value in mean.items()}
    winner = max(mean, key=mean.get)
    rotation_winners = tuple(max(row, key=row.get) for row in distributions)
    agreement = sum(1 for item in rotation_winners if item == winner) / len(rotation_winners)

    jsd = _entropy(mean) - sum(_entropy(row) for row in distributions) / len(distributions)
    normalizer = math.log(len(labels))
    normalized_jsd = 0.0 if normalizer <= 0 else max(0.0, jsd / normalizer)

    return OrderEnsembleMetrics(
        rotations=len(distributions),
        labels=labels,
        per_rotation_winner=rotation_winners,
        winner_agreement=agreement,
        normalized_jsd=normalized_jsd,
        aggregate_probabilities=tuple(sorted(mean.items())),
        aggregate_winner=winner,
        aggregate_peak_probability=mean[winner],
    )


RobustExecutor = Callable[..., ColibriDecisionResult]


def execute_robust_reflex_route(
    *,
    authorization: HazewaveAuthorization,
    question_id: str,
    state: str | Mapping[str, Any],
    question: Mapping[str, Any],
    api_key: str,
    deterministic_precheck_complete: bool,
    data_classification: str = "INTERNAL_NON_SECRET",
    state_language: str = "en",
    execution_context: str = "DEVELOPMENT",
    model_installed: bool = False,
    model_revision_verified: bool = False,
    hardware: Any = None,
    base_url: str | None = None,
    transport: Any = None,
    reflex_policy: Mapping[str, Any] | None = None,
    robustness_policy: Mapping[str, Any] | None = None,
    executor: RobustExecutor = execute_colibri_system_one,
) -> RobustReflexVerdict:
    validate_authorization(
        authorization,
        expected_task_id=authorization.task_id,
        expected_capability="decision.route",
    )
    if authorization.capability_id != "decision.route":
        raise ReflexRobustnessError("REFLEX_ROBUSTNESS_ROUTE_CAPABILITY_REQUIRED")
    if deterministic_precheck_complete is not True:
        raise ReflexDecisionError("REFLEX_DETERMINISTIC_PRECHECK_REQUIRED")

    reflex = dict(reflex_policy) if reflex_policy is not None else load_reflex_policy()
    robust = (
        dict(robustness_policy)
        if robustness_policy is not None
        else load_robustness_policy()
    )
    settings = robust["option_order_ensemble"]
    questions = cyclic_choice_questions(
        question_id=question_id,
        question=question,
        max_rotations=int(settings["max_rotations"]),
    )
    criteria = question.get("criteria")
    if not isinstance(criteria, Mapping) or len(criteria) > int(settings["max_labels"]):
        raise ReflexRobustnessError("REFLEX_ROBUSTNESS_LABEL_LIMIT_EXCEEDED")

    validate_reflex_request(
        authorization=authorization,
        state=state,
        questions=questions,
        data_classification=data_classification,
        policy=reflex,
    )
    profile = reflex["profiles"]["decision.route"]
    result = executor(
        authorization=authorization,
        model_id=str(reflex.get("source_model") or "laya"),
        state=state,
        questions=questions,
        api_key=api_key,
        data_classification=data_classification,
        state_language=state_language,
        execution_context=execution_context,
        model_installed=model_installed,
        model_revision_verified=model_revision_verified,
        hardware=hardware,
        base_url=base_url,
        timeout_seconds=float(profile.get("max_latency_ms") or 3000.0) / 1000.0,
        transport=transport,
    )
    ordered_answers = []
    for key in questions:
        answer = result.answers.get(key)
        if not isinstance(answer, Mapping):
            raise ReflexRobustnessError("REFLEX_ROBUSTNESS_ROTATION_ANSWER_MISSING")
        ordered_answers.append(answer)
    ensemble = aggregate_choice_answers(ordered_answers)

    n = len(ensemble.labels)
    aggregate_confidence = (
        (n * ensemble.aggregate_peak_probability - 1.0) / (n - 1.0)
    )
    aggregate_answer = {
        "type": "choice",
        "choice": ensemble.aggregate_winner,
        "probabilities": dict(ensemble.aggregate_probabilities),
        "confidence": aggregate_confidence,
    }
    aggregate_result = ColibriDecisionResult(
        model_id=result.model_id,
        answers={question_id: aggregate_answer},
        request_sha256=result.request_sha256,
        response_sha256=result.response_sha256,
        latency_ms=result.latency_ms,
        usage=dict(result.usage),
        health_ms=result.health_ms,
        system_one_ms=result.system_one_ms,
        engine_ms=result.engine_ms,
        server_elapsed_ms=result.server_elapsed_ms,
        queue_wait_ms=result.queue_wait_ms,
    )
    base = govern_reflex_result(
        authorization=authorization,
        result=aggregate_result,
        question_id=question_id,
        policy=reflex,
    )

    reasons: list[str] = []
    if ensemble.winner_agreement < float(settings["min_winner_agreement"]):
        reasons.append("OPTION_ORDER_WINNER_DISAGREEMENT")
    if ensemble.normalized_jsd > float(settings["max_normalized_jsd"]):
        reasons.append("OPTION_ORDER_DISTRIBUTION_DRIFT")
    robust_eligible = base.threshold_eligible and not reasons

    disposition = base.disposition
    escalation = base.escalation_target
    if reasons and disposition == "ACCEPT_RECOMMENDATION":
        disposition = "ESCALATE"
        escalation = str(profile.get("reject_action") or "ESCALATE_9ROUTER_REASON_DEEP")

    return RobustReflexVerdict(
        base_verdict=base,
        ensemble=ensemble,
        robust_eligible=robust_eligible,
        robustness_reasons=tuple(reasons),
        disposition=disposition,
        escalation_target=escalation,
    )


def hoeffding_one_sided_upper_bound(
    *,
    errors: int,
    sample_count: int,
    delta: float,
) -> float:
    if sample_count <= 0 or errors < 0 or errors > sample_count:
        raise ValueError("REFLEX_RISK_SAMPLE_COUNT_INVALID")
    if not 0.0 < delta < 1.0:
        raise ValueError("REFLEX_RISK_DELTA_INVALID")
    empirical = errors / sample_count
    radius = math.sqrt(math.log(1.0 / delta) / (2.0 * sample_count))
    return min(1.0, empirical + radius)


def select_risk_threshold_candidate(
    samples: Iterable[RiskCalibrationSample],
    *,
    policy: Mapping[str, Any] | None = None,
    target_risk: float | None = None,
    delta: float | None = None,
    minimum_total_samples: int | None = None,
    minimum_accepted_samples: int | None = None,
) -> RiskThresholdCandidate:
    selected = dict(policy) if policy is not None else load_robustness_policy()
    cfg = selected["risk_control"]
    target = float(cfg["target_selective_risk"] if target_risk is None else target_risk)
    alpha = float(cfg["delta"] if delta is None else delta)
    min_total = int(
        cfg["minimum_total_labeled_samples"]
        if minimum_total_samples is None
        else minimum_total_samples
    )
    min_accepted = int(
        cfg["minimum_accepted_samples"]
        if minimum_accepted_samples is None
        else minimum_accepted_samples
    )
    rows = tuple(samples)
    for row in rows:
        if (
            not isinstance(row, RiskCalibrationSample)
            or not math.isfinite(float(row.score))
            or not 0.0 <= float(row.score) <= 1.0
        ):
            raise ValueError("REFLEX_RISK_SAMPLE_INVALID")

    if len(rows) < min_total:
        return RiskThresholdCandidate(
            status="INSUFFICIENT_TOTAL_EVIDENCE",
            threshold=None,
            accepted_samples=0,
            errors=0,
            empirical_risk=None,
            risk_upper_bound=None,
            target_risk=target,
            delta=alpha,
            total_samples=len(rows),
        )

    stable_rows = tuple(row for row in rows if row.stable)
    candidates = sorted({float(row.score) for row in stable_rows})
    best: RiskThresholdCandidate | None = None
    for threshold in candidates:
        accepted = tuple(row for row in stable_rows if float(row.score) >= threshold)
        if len(accepted) < min_accepted:
            continue
        errors = sum(1 for row in accepted if not row.correct)
        empirical = errors / len(accepted)
        upper = hoeffding_one_sided_upper_bound(
            errors=errors, sample_count=len(accepted), delta=alpha
        )
        if upper <= target:
            candidate = RiskThresholdCandidate(
                status="CANDIDATE_ONLY_HUMAN_REVIEW_REQUIRED",
                threshold=threshold,
                accepted_samples=len(accepted),
                errors=errors,
                empirical_risk=empirical,
                risk_upper_bound=upper,
                target_risk=target,
                delta=alpha,
                total_samples=len(rows),
            )
            if best is None or candidate.accepted_samples > best.accepted_samples:
                best = candidate
    if best is not None:
        return best
    return RiskThresholdCandidate(
        status="NO_THRESHOLD_MEETS_RISK_BOUND",
        threshold=None,
        accepted_samples=0,
        errors=0,
        empirical_risk=None,
        risk_upper_bound=None,
        target_risk=target,
        delta=alpha,
        total_samples=len(rows),
    )
