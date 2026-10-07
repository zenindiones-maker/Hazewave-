from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import httpx

from hazewave.colibri import (
    ColibriDecisionResult,
    execute_colibri_system_one,
)
from hazewave.harness import AUTHORITY, PROJECT_ID, HazewaveAuthorization, validate_authorization


DEFAULT_REFLEX_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "reflex-governor-v1.json"
)
_ALLOWED_LABEL_SOURCES = frozenset({"HUMAN", "DETERMINISTIC", "RUNTIME_QC"})
_ALLOWED_DISPOSITIONS = frozenset(
    {"ACCEPT_RECOMMENDATION", "ESCALATE", "SHADOW_RECOMMENDATION"}
)


class ReflexDecisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReflexProbabilityMetrics:
    selected_label: str
    probabilities: tuple[tuple[str, float], ...]
    peak_probability: float
    top2_margin: float
    normalized_entropy: float
    system_one_confidence: float
    expected_concentration: float
    schema: str = "HazewaveReflexProbabilityMetrics/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["probabilities"] = dict(self.probabilities)
        return value


@dataclass(frozen=True)
class ReflexVerdict:
    task_id: str
    capability_id: str
    domain: str
    question_id: str
    model_id: str
    disposition: str
    reasons: tuple[str, ...]
    escalation_target: str | None
    metrics: ReflexProbabilityMetrics
    latency_ms: float
    request_sha256: str
    response_sha256: str
    policy_sha256: str
    threshold_eligible: bool
    authority: str = AUTHORITY
    provider_authority: str = "NONE"
    grants_execution_authority: bool = False
    correctness_probability_claimed: bool = False
    schema: str = "HazewaveReflexVerdict/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reasons"] = list(self.reasons)
        value["metrics"] = self.metrics.to_dict()
        return value


@dataclass(frozen=True)
class ReflexOutcome:
    observed_at: str
    decision_key: str
    task_id: str
    capability_id: str
    domain: str
    model_id: str
    request_sha256: str
    predicted_label: str
    actual_label: str
    probabilities: tuple[tuple[str, float], ...]
    accepted_by_governor: bool
    threshold_eligible: bool
    label_source: str
    label_evidence_digest: str
    latency_ms: float
    policy_sha256: str
    outcome_id: str
    raw_state_persisted: bool = False
    schema: str = "HazewaveReflexOutcome/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["probabilities"] = dict(self.probabilities)
        return value


@dataclass(frozen=True)
class ReflexCalibrationReport:
    sample_count: int
    actual_accept_count: int
    threshold_eligible_count: int
    shadow_coverage: float
    accuracy: float
    selective_risk_if_activated: float | None
    ece: float
    multiclass_brier: float
    latency_p50_ms: float
    latency_p95_ms: float
    schema: str = "HazewaveReflexCalibrationReport/v1"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def load_reflex_policy(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else DEFAULT_REFLEX_POLICY_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("schema") != "HazewaveReflexGovernorPolicy/v1":
        raise ValueError("REFLEX_POLICY_SCHEMA_INVALID")
    if payload.get("project_id") != PROJECT_ID or payload.get("authority") != AUTHORITY:
        raise ValueError("REFLEX_POLICY_AUTHORITY_INVALID")
    if payload.get("provider_authority") != "NONE":
        raise ValueError("REFLEX_PROVIDER_AUTHORITY_INVALID")
    if payload.get("mode") != "SELECTIVE_CASCADE":
        raise ValueError("REFLEX_POLICY_MODE_INVALID")
    safety = payload.get("safety") or {}
    if safety.get("deterministic_rules_first") is not True:
        raise ValueError("REFLEX_DETERMINISTIC_PRECHECK_REQUIRED")
    if safety.get("raw_system_one_confidence_is_correctness_probability") is not False:
        raise ValueError("REFLEX_CONFIDENCE_SEMANTICS_INVALID")
    if safety.get("raw_system_one_confidence_automation_authority") != "NONE":
        raise ValueError("REFLEX_RAW_CONFIDENCE_AUTHORITY_INVALID")
    if safety.get("auto_threshold_mutation") is not False:
        raise ValueError("REFLEX_AUTO_THRESHOLD_MUTATION_FORBIDDEN")
    if safety.get("auto_model_promotion") is not False:
        raise ValueError("REFLEX_AUTO_MODEL_PROMOTION_FORBIDDEN")
    for capability, profile in (payload.get("profiles") or {}).items():
        if not isinstance(profile, Mapping):
            raise ValueError(f"REFLEX_PROFILE_INVALID:{capability}")
        latency_budget = float(profile.get("max_latency_ms") or 0.0)
        transport_timeout = float(profile.get("transport_timeout_ms") or 0.0)
        if latency_budget <= 0.0 or transport_timeout <= 0.0:
            raise ValueError(f"REFLEX_TIMEOUT_POLICY_INVALID:{capability}")
        if transport_timeout < latency_budget:
            raise ValueError(f"REFLEX_TRANSPORT_TIMEOUT_BELOW_LATENCY_BUDGET:{capability}")
    return payload


def reflex_policy_digest(policy: Mapping[str, Any]) -> str:
    return _sha256_json(dict(policy))


def _profile(
    authorization: HazewaveAuthorization,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    capability = str(authorization.capability_id or "").strip()
    row = (policy.get("profiles") or {}).get(capability)
    if not isinstance(row, dict):
        raise ReflexDecisionError(f"REFLEX_CAPABILITY_NOT_PROFILED:{capability}")
    return dict(row)


def _state_bytes(state: str | Mapping[str, Any]) -> bytes:
    if isinstance(state, str):
        value = state.strip()
        if not value:
            raise ReflexDecisionError("REFLEX_STATE_REQUIRED")
        return value.encode("utf-8")
    if isinstance(state, Mapping):
        return _canonical_bytes(dict(state))
    raise ReflexDecisionError("REFLEX_STATE_INVALID")


def validate_reflex_request(
    *,
    authorization: HazewaveAuthorization,
    state: str | Mapping[str, Any],
    questions: Mapping[str, Any],
    data_classification: str,
    policy: Mapping[str, Any] | None = None,
) -> None:
    selected = dict(policy) if policy is not None else load_reflex_policy()
    validate_authorization(
        authorization,
        expected_task_id=authorization.task_id,
        expected_capability=authorization.capability_id,
    )
    if str(data_classification or "").strip().upper() == "CREDENTIAL":
        raise ReflexDecisionError("REFLEX_CREDENTIAL_INPUT_FORBIDDEN")
    if str(data_classification or "").strip().upper() == "PRIVATE_MEDIA":
        raise ReflexDecisionError("REFLEX_RAW_PRIVATE_MEDIA_FORBIDDEN")

    limits = selected.get("request_limits") or {}
    if not isinstance(questions, Mapping) or not questions:
        raise ReflexDecisionError("REFLEX_QUESTIONS_REQUIRED")
    if len(questions) > int(limits.get("max_questions_per_request") or 0):
        raise ReflexDecisionError("REFLEX_TOO_MANY_QUESTIONS")
    if len(_state_bytes(state)) > int(limits.get("max_state_bytes") or 0):
        raise ReflexDecisionError("REFLEX_STATE_TOO_LARGE")

    profile = _profile(authorization, selected)
    expected_type = str(profile.get("question_type") or "")
    for question_id, question in questions.items():
        if not str(question_id or "").strip() or not isinstance(question, Mapping):
            raise ReflexDecisionError("REFLEX_QUESTION_INVALID")
        if len(_canonical_bytes(dict(question))) > int(
            limits.get("max_question_bytes") or 0
        ):
            raise ReflexDecisionError("REFLEX_QUESTION_TOO_LARGE")
        question_type = str(question.get("type") or "")
        if question_type != expected_type:
            raise ReflexDecisionError("REFLEX_QUESTION_TYPE_MISMATCH")
        criteria = question.get("criteria")
        if question_type == "choice":
            if not isinstance(criteria, Mapping):
                raise ReflexDecisionError("REFLEX_CHOICE_CRITERIA_INVALID")
            option_count = len(criteria)
        elif question_type == "score":
            if not isinstance(criteria, list):
                raise ReflexDecisionError("REFLEX_SCORE_CRITERIA_INVALID")
            option_count = len(criteria)
        else:
            raise ReflexDecisionError("REFLEX_QUESTION_TYPE_UNSUPPORTED")
        if option_count < 2:
            raise ReflexDecisionError("REFLEX_TOO_FEW_OPTIONS")
        if option_count > int(limits.get("max_choice_labels") or 0):
            raise ReflexDecisionError("REFLEX_REQUIRES_HIERARCHICAL_DECISION")


def _probability_metrics(
    answer: Mapping[str, Any],
    *,
    selected_label: str | None = None,
) -> ReflexProbabilityMetrics:
    probabilities = answer.get("probabilities")
    if not isinstance(probabilities, Mapping) or len(probabilities) < 2:
        raise ReflexDecisionError("REFLEX_PROBABILITIES_REQUIRED")

    parsed: list[tuple[str, float]] = []
    for label, raw in probabilities.items():
        name = str(label or "").strip()
        if not name or not isinstance(raw, (int, float)):
            raise ReflexDecisionError("REFLEX_PROBABILITY_INVALID")
        value = float(raw)
        if not math.isfinite(value) or value < 0.0 or value > 1.0:
            raise ReflexDecisionError("REFLEX_PROBABILITY_INVALID")
        parsed.append((name, value))

    total = sum(value for _, value in parsed)
    if total <= 0.0 or abs(total - 1.0) > 0.02:
        raise ReflexDecisionError("REFLEX_PROBABILITY_MASS_INVALID")
    normalized = tuple(sorted((name, value / total) for name, value in parsed))
    ranking = sorted(normalized, key=lambda item: item[1], reverse=True)
    peak_label, peak = ranking[0]
    second = ranking[1][1]
    chosen = str(selected_label or peak_label).strip()
    if chosen not in dict(normalized):
        raise ReflexDecisionError("REFLEX_SELECTED_LABEL_NOT_IN_PROBABILITIES")
    if selected_label is not None:
        chosen_probability = dict(normalized)[chosen]
        if chosen_probability + 1e-9 < peak:
            raise ReflexDecisionError("REFLEX_SELECTED_LABEL_NOT_ARGMAX")

    n = len(normalized)
    entropy = -sum(p * math.log(p) for _, p in normalized if p > 0.0)
    normalized_entropy = entropy / math.log(n)
    expected_concentration = (n * peak - 1.0) / (n - 1.0)

    raw_confidence = answer.get("confidence")
    if not isinstance(raw_confidence, (int, float)):
        raise ReflexDecisionError("REFLEX_SYSTEM_ONE_CONFIDENCE_REQUIRED")
    confidence = float(raw_confidence)
    if not math.isfinite(confidence) or confidence < 0.0 or confidence > 1.0:
        raise ReflexDecisionError("REFLEX_SYSTEM_ONE_CONFIDENCE_INVALID")
    if abs(confidence - expected_concentration) > 0.03:
        raise ReflexDecisionError("REFLEX_SYSTEM_ONE_CONFIDENCE_SEMANTICS_DRIFT")

    return ReflexProbabilityMetrics(
        selected_label=chosen,
        probabilities=normalized,
        peak_probability=peak,
        top2_margin=peak - second,
        normalized_entropy=normalized_entropy,
        system_one_confidence=confidence,
        expected_concentration=expected_concentration,
    )


def govern_reflex_result(
    *,
    authorization: HazewaveAuthorization,
    result: ColibriDecisionResult,
    question_id: str,
    policy: Mapping[str, Any] | None = None,
) -> ReflexVerdict:
    selected = dict(policy) if policy is not None else load_reflex_policy()
    validate_authorization(
        authorization,
        expected_task_id=authorization.task_id,
        expected_capability=authorization.capability_id,
    )
    profile = _profile(authorization, selected)
    answer = result.answers.get(question_id)
    if not isinstance(answer, Mapping):
        raise ReflexDecisionError("REFLEX_ANSWER_MISSING")

    question_type = str(answer.get("type") or "")
    if question_type != str(profile.get("question_type") or ""):
        raise ReflexDecisionError("REFLEX_ANSWER_TYPE_MISMATCH")

    selected_label: str | None
    if question_type == "choice":
        selected_label = str(answer.get("choice") or "").strip()
        if not selected_label:
            raise ReflexDecisionError("REFLEX_CHOICE_MISSING")
    else:
        selected_label = None

    metrics = _probability_metrics(answer, selected_label=selected_label)
    reasons: list[str] = []
    if metrics.peak_probability < float(profile.get("min_peak_probability") or 0.0):
        reasons.append("PEAK_PROBABILITY_BELOW_THRESHOLD")
    if metrics.top2_margin < float(profile.get("min_top2_margin") or 0.0):
        reasons.append("TOP2_MARGIN_BELOW_THRESHOLD")
    if metrics.normalized_entropy > float(profile.get("max_normalized_entropy") or 1.0):
        reasons.append("ENTROPY_ABOVE_THRESHOLD")
    if result.latency_ms > float(profile.get("max_latency_ms") or 0.0):
        reasons.append("LATENCY_BUDGET_EXCEEDED")

    threshold_eligible = not reasons
    mode = str(profile.get("acceptance_mode") or "")
    reject_action = str(profile.get("reject_action") or "")
    production_calibrated = profile.get("production_calibrated") is True
    if not production_calibrated:
        disposition = "SHADOW_RECOMMENDATION"
        reasons.insert(0, "HAZEWAVE_CALIBRATION_REQUIRED")
        escalation_target = reject_action
    elif mode == "SHADOW_ONLY":
        disposition = "SHADOW_RECOMMENDATION"
        reasons.insert(0, "PROFILE_SHADOW_ONLY")
        escalation_target = reject_action
    elif reasons:
        disposition = "ESCALATE"
        escalation_target = reject_action
    else:
        disposition = "ACCEPT_RECOMMENDATION"
        escalation_target = None

    if disposition not in _ALLOWED_DISPOSITIONS:
        raise ReflexDecisionError("REFLEX_DISPOSITION_INVALID")

    return ReflexVerdict(
        task_id=authorization.task_id,
        capability_id=authorization.capability_id,
        domain=authorization.domain,
        question_id=question_id,
        model_id=result.model_id,
        disposition=disposition,
        reasons=tuple(reasons),
        escalation_target=escalation_target,
        metrics=metrics,
        latency_ms=float(result.latency_ms),
        request_sha256=result.request_sha256,
        response_sha256=result.response_sha256,
        policy_sha256=reflex_policy_digest(selected),
        threshold_eligible=threshold_eligible,
    )


Executor = Callable[..., ColibriDecisionResult]


def execute_reflex_choice(
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
    transport: httpx.BaseTransport | None = None,
    policy: Mapping[str, Any] | None = None,
    executor: Executor = execute_colibri_system_one,
) -> ReflexVerdict:
    selected = dict(policy) if policy is not None else load_reflex_policy()
    if deterministic_precheck_complete is not True:
        raise ReflexDecisionError("REFLEX_DETERMINISTIC_PRECHECK_REQUIRED")
    questions = {question_id: dict(question)}
    validate_reflex_request(
        authorization=authorization,
        state=state,
        questions=questions,
        data_classification=data_classification,
        policy=selected,
    )
    profile = _profile(authorization, selected)
    result = executor(
        authorization=authorization,
        model_id=str(selected.get("source_model") or "laya"),
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
        timeout_seconds=float(profile.get("transport_timeout_ms") or 10000.0) / 1000.0,
        transport=transport,
    )
    return govern_reflex_result(
        authorization=authorization,
        result=result,
        question_id=question_id,
        policy=selected,
    )


def build_reflex_outcome(
    *,
    verdict: ReflexVerdict,
    decision_key: str,
    actual_label: str,
    label_source: str,
    label_evidence_digest: str,
    observed_at: str,
) -> ReflexOutcome:
    key = str(decision_key or "").strip()
    actual = str(actual_label or "").strip()
    source = str(label_source or "").strip().upper()
    evidence_digest = str(label_evidence_digest or "").strip().lower()
    timestamp = str(observed_at or "").strip()
    if not key:
        raise ValueError("REFLEX_DECISION_KEY_REQUIRED")
    if not actual:
        raise ValueError("REFLEX_ACTUAL_LABEL_REQUIRED")
    if source not in _ALLOWED_LABEL_SOURCES:
        raise ValueError("REFLEX_LABEL_SOURCE_INVALID")
    if len(evidence_digest) != 64 or any(ch not in "0123456789abcdef" for ch in evidence_digest):
        raise ValueError("REFLEX_LABEL_EVIDENCE_DIGEST_INVALID")
    if not timestamp:
        raise ValueError("REFLEX_OBSERVED_AT_REQUIRED")
    if actual not in dict(verdict.metrics.probabilities):
        raise ValueError("REFLEX_ACTUAL_LABEL_NOT_IN_OPTIONS")

    material = {
        "observed_at": timestamp,
        "decision_key": key,
        "task_id": verdict.task_id,
        "capability_id": verdict.capability_id,
        "domain": verdict.domain,
        "model_id": verdict.model_id,
        "request_sha256": verdict.request_sha256,
        "predicted_label": verdict.metrics.selected_label,
        "actual_label": actual,
        "probabilities": dict(verdict.metrics.probabilities),
        "accepted_by_governor": verdict.disposition == "ACCEPT_RECOMMENDATION",
        "threshold_eligible": verdict.threshold_eligible,
        "label_source": source,
        "label_evidence_digest": evidence_digest,
        "latency_ms": verdict.latency_ms,
        "policy_sha256": verdict.policy_sha256,
        "raw_state_persisted": False,
    }
    return ReflexOutcome(
        observed_at=timestamp,
        decision_key=key,
        task_id=verdict.task_id,
        capability_id=verdict.capability_id,
        domain=verdict.domain,
        model_id=verdict.model_id,
        request_sha256=verdict.request_sha256,
        predicted_label=verdict.metrics.selected_label,
        actual_label=actual,
        probabilities=verdict.metrics.probabilities,
        accepted_by_governor=verdict.disposition == "ACCEPT_RECOMMENDATION",
        threshold_eligible=verdict.threshold_eligible,
        label_source=source,
        label_evidence_digest=evidence_digest,
        latency_ms=verdict.latency_ms,
        policy_sha256=verdict.policy_sha256,
        outcome_id=_sha256_json(material),
    )


def append_reflex_outcome(path: str | Path, outcome: ReflexOutcome) -> None:
    if not isinstance(outcome, ReflexOutcome):
        raise TypeError("REFLEX_OUTCOME_TYPE_INVALID")
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(target.parent, 0o700)
    except OSError:
        pass
    payload = outcome.to_dict()
    encoded = _canonical_bytes(payload) + b"\n"
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, encoded)
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass


def load_reflex_outcomes(path: str | Path) -> tuple[ReflexOutcome, ...]:
    target = Path(path).expanduser()
    if not target.is_file():
        return ()
    rows: list[ReflexOutcome] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("schema") != "HazewaveReflexOutcome/v1":
            raise ValueError("REFLEX_OUTCOME_SCHEMA_INVALID")
        probabilities = payload.get("probabilities")
        if not isinstance(probabilities, dict):
            raise ValueError("REFLEX_OUTCOME_PROBABILITIES_INVALID")
        outcome = ReflexOutcome(
            observed_at=str(payload["observed_at"]),
            decision_key=str(payload["decision_key"]),
            task_id=str(payload["task_id"]),
            capability_id=str(payload["capability_id"]),
            domain=str(payload["domain"]),
            model_id=str(payload["model_id"]),
            request_sha256=str(payload["request_sha256"]),
            predicted_label=str(payload["predicted_label"]),
            actual_label=str(payload["actual_label"]),
            probabilities=tuple(
                sorted((str(k), float(v)) for k, v in probabilities.items())
            ),
            accepted_by_governor=bool(payload["accepted_by_governor"]),
            threshold_eligible=bool(payload["threshold_eligible"]),
            label_source=str(payload["label_source"]),
            label_evidence_digest=str(payload["label_evidence_digest"]),
            latency_ms=float(payload["latency_ms"]),
            policy_sha256=str(payload["policy_sha256"]),
            outcome_id=str(payload["outcome_id"]),
            raw_state_persisted=bool(payload.get("raw_state_persisted", False)),
        )
        if outcome.raw_state_persisted is not False:
            raise ValueError("REFLEX_OUTCOME_RAW_STATE_PERSISTENCE_FORBIDDEN")
        if (
            len(outcome.label_evidence_digest) != 64
            or any(ch not in "0123456789abcdef" for ch in outcome.label_evidence_digest)
        ):
            raise ValueError("REFLEX_OUTCOME_LABEL_EVIDENCE_DIGEST_INVALID")
        material = {
            "observed_at": outcome.observed_at,
            "decision_key": outcome.decision_key,
            "task_id": outcome.task_id,
            "capability_id": outcome.capability_id,
            "domain": outcome.domain,
            "model_id": outcome.model_id,
            "request_sha256": outcome.request_sha256,
            "predicted_label": outcome.predicted_label,
            "actual_label": outcome.actual_label,
            "probabilities": dict(outcome.probabilities),
            "accepted_by_governor": outcome.accepted_by_governor,
            "threshold_eligible": outcome.threshold_eligible,
            "label_source": outcome.label_source,
            "label_evidence_digest": outcome.label_evidence_digest,
            "latency_ms": outcome.latency_ms,
            "policy_sha256": outcome.policy_sha256,
            "raw_state_persisted": False,
        }
        if _sha256_json(material) != outcome.outcome_id:
            raise ValueError("REFLEX_OUTCOME_DIGEST_MISMATCH")
        rows.append(outcome)
    return tuple(rows)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def evaluate_reflex_outcomes(
    outcomes: Iterable[ReflexOutcome],
    *,
    ece_bins: int = 10,
) -> ReflexCalibrationReport:
    rows = tuple(outcomes)
    if not rows:
        raise ValueError("REFLEX_CALIBRATION_DATA_REQUIRED")
    if ece_bins < 2 or ece_bins > 100:
        raise ValueError("REFLEX_ECE_BINS_INVALID")

    cohorts = {
        (row.decision_key, row.capability_id, row.model_id, row.policy_sha256)
        for row in rows
    }
    if len(cohorts) != 1:
        raise ValueError("REFLEX_CALIBRATION_COHORT_MIXED")

    correct = [row.predicted_label == row.actual_label for row in rows]
    actually_accepted = [row for row in rows if row.accepted_by_governor]
    eligible = [row for row in rows if row.threshold_eligible]
    eligible_correct = [
        row.predicted_label == row.actual_label for row in eligible
    ]
    accuracy = sum(correct) / len(rows)
    shadow_coverage = len(eligible) / len(rows)
    selective_risk = (
        1.0 - (sum(eligible_correct) / len(eligible))
        if eligible
        else None
    )

    calibration_rows: list[tuple[float, int]] = []
    brier_values: list[float] = []
    latencies: list[float] = []
    for row in rows:
        probs = dict(row.probabilities)
        peak = max(probs.values())
        calibration_rows.append(
            (peak, 1 if row.predicted_label == row.actual_label else 0)
        )
        labels = tuple(probs)
        brier_values.append(
            sum(
                (probs[label] - (1.0 if label == row.actual_label else 0.0)) ** 2
                for label in labels
            )
        )
        latencies.append(float(row.latency_ms))

    ece = 0.0
    for index in range(ece_bins):
        lower = index / ece_bins
        upper = (index + 1) / ece_bins
        bucket = [
            (confidence, outcome)
            for confidence, outcome in calibration_rows
            if (confidence >= lower and (confidence < upper or index == ece_bins - 1))
        ]
        if not bucket:
            continue
        avg_conf = sum(value for value, _ in bucket) / len(bucket)
        avg_acc = sum(value for _, value in bucket) / len(bucket)
        ece += (len(bucket) / len(rows)) * abs(avg_conf - avg_acc)

    return ReflexCalibrationReport(
        sample_count=len(rows),
        actual_accept_count=len(actually_accepted),
        threshold_eligible_count=len(eligible),
        shadow_coverage=shadow_coverage,
        accuracy=accuracy,
        selective_risk_if_activated=selective_risk,
        ece=ece,
        multiclass_brier=sum(brier_values) / len(brier_values),
        latency_p50_ms=_percentile(latencies, 0.50),
        latency_p95_ms=_percentile(latencies, 0.95),
    )


def reflex_recalibration_readiness(
    outcomes: Iterable[ReflexOutcome],
    *,
    decision_key: str,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selected = dict(policy) if policy is not None else load_reflex_policy()
    rows = tuple(outcomes)
    learning = selected.get("learning") or {}
    key = str(decision_key or "").strip()
    matching = [row for row in rows if row.decision_key == key]
    total_min = int(learning.get("minimum_labeled_samples_for_recalibration") or 0)
    per_key_min = int(
        learning.get("minimum_labeled_samples_per_decision_key") or 0
    )
    return {
        "schema": "HazewaveReflexRecalibrationReadiness/v1",
        "decision_key": key,
        "total_labeled_samples": len(rows),
        "decision_key_labeled_samples": len(matching),
        "minimum_total_required": total_min,
        "minimum_key_required": per_key_min,
        "ready": len(rows) >= total_min and len(matching) >= per_key_min,
        "auto_threshold_mutation": False,
        "auto_model_promotion": False,
    }
