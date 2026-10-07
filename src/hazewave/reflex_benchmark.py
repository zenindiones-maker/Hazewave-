from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from typing import Any, Callable, Iterable, Mapping

from hazewave.reflex_robustness import (
    RiskCalibrationSample,
    aggregate_choice_answers,
    cyclic_choice_questions,
    load_robustness_policy,
)


class ReflexBenchmarkError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReflexBenchmarkCase:
    case_id: str
    state: Mapping[str, Any]
    criteria: Mapping[str, str | None]
    expected_label: str
    decision_key: str = "domain.route.v1"


@dataclass(frozen=True)
class ReflexBenchmarkCaseResult:
    case_id: str
    expected_label: str
    base_winner: str
    ensemble_winner: str
    state_reversed_winner: str
    aggregate_peak_probability: float
    winner_agreement: float
    normalized_jsd: float
    base_correct: bool
    ensemble_correct: bool
    option_order_flip: bool
    state_order_flip: bool
    multiclass_brier: float
    schema: str = "HazewaveReflexBenchmarkCaseResult/v1"


@dataclass(frozen=True)
class ReflexRobustnessBenchmarkReport:
    case_count: int
    base_accuracy: float
    ensemble_accuracy: float
    option_order_flip_rate: float
    state_order_flip_rate: float
    mean_normalized_jsd: float
    multiclass_brier: float
    ece: float
    review_ready: bool
    benchmark_digest: str
    cases: tuple[ReflexBenchmarkCaseResult, ...]
    status: str = "EVIDENCE_ONLY"
    grants_production_authority: bool = False
    schema: str = "HazewaveReflexRobustnessBenchmark/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["cases"] = [asdict(item) for item in self.cases]
        return value


Predictor = Callable[[Mapping[str, Any], Mapping[str, str | None]], Mapping[str, float]]


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _answer(probabilities: Mapping[str, float]) -> dict[str, Any]:
    if len(probabilities) < 2:
        raise ReflexBenchmarkError("REFLEX_BENCHMARK_PROBABILITIES_INVALID")
    parsed: dict[str, float] = {}
    for label, raw in probabilities.items():
        if not isinstance(raw, (int, float)):
            raise ReflexBenchmarkError("REFLEX_BENCHMARK_PROBABILITY_INVALID")
        value = float(raw)
        if not math.isfinite(value) or value < 0 or value > 1:
            raise ReflexBenchmarkError("REFLEX_BENCHMARK_PROBABILITY_INVALID")
        parsed[str(label)] = value
    total = sum(parsed.values())
    if total <= 0 or abs(total - 1.0) > 0.02:
        raise ReflexBenchmarkError("REFLEX_BENCHMARK_PROBABILITY_MASS_INVALID")
    parsed = {key: value / total for key, value in parsed.items()}
    winner = max(parsed, key=parsed.get)
    n = len(parsed)
    confidence = (n * parsed[winner] - 1.0) / (n - 1.0)
    return {
        "type": "choice",
        "choice": winner,
        "probabilities": parsed,
        "confidence": confidence,
    }


def _brier(probabilities: Mapping[str, float], expected: str) -> float:
    return sum(
        (float(value) - (1.0 if label == expected else 0.0)) ** 2
        for label, value in probabilities.items()
    )


def _ece(rows: list[tuple[float, bool]], bins: int = 10) -> float:
    if not rows:
        return 0.0
    result = 0.0
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        bucket = [
            (confidence, correct)
            for confidence, correct in rows
            if confidence >= lower and (confidence < upper or index == bins - 1)
        ]
        if not bucket:
            continue
        mean_confidence = sum(value for value, _ in bucket) / len(bucket)
        mean_accuracy = sum(1.0 if correct else 0.0 for _, correct in bucket) / len(bucket)
        result += (len(bucket) / len(rows)) * abs(mean_confidence - mean_accuracy)
    return result


def evaluate_reflex_robustness_benchmark(
    cases: Iterable[ReflexBenchmarkCase],
    *,
    predictor: Predictor,
    policy: Mapping[str, Any] | None = None,
) -> ReflexRobustnessBenchmarkReport:
    selected = dict(policy) if policy is not None else load_robustness_policy()
    ensemble_policy = selected["option_order_ensemble"]
    benchmark_policy = selected["benchmark"]
    rows = tuple(cases)
    if not rows:
        raise ReflexBenchmarkError("REFLEX_BENCHMARK_CASES_REQUIRED")

    results: list[ReflexBenchmarkCaseResult] = []
    calibration: list[tuple[float, bool]] = []
    for case in rows:
        if not case.case_id.strip() or not case.decision_key.strip():
            raise ReflexBenchmarkError("REFLEX_BENCHMARK_CASE_ID_INVALID")
        criteria = dict(case.criteria)
        if case.expected_label not in criteria:
            raise ReflexBenchmarkError("REFLEX_BENCHMARK_EXPECTED_LABEL_INVALID")
        if len(criteria) < 2 or len(criteria) > int(ensemble_policy["max_labels"]):
            raise ReflexBenchmarkError("REFLEX_BENCHMARK_LABEL_COUNT_INVALID")

        question = {
            "type": "choice",
            "instructions": "Select the best Hazewave domain for this structured operational state.",
            "criteria": criteria,
        }
        rotations = cyclic_choice_questions(
            question_id="route",
            question=question,
            max_rotations=int(ensemble_policy["max_rotations"]),
        )
        answers: list[dict[str, Any]] = []
        for rotated in rotations.values():
            probs = predictor(case.state, rotated["criteria"])
            if set(probs) != set(criteria):
                raise ReflexBenchmarkError("REFLEX_BENCHMARK_PREDICTOR_LABEL_DRIFT")
            answers.append(_answer(probs))
        ensemble = aggregate_choice_answers(answers)
        aggregate_probs = dict(ensemble.aggregate_probabilities)

        base_winner = answers[0]["choice"]
        reversed_state = dict(reversed(list(case.state.items())))
        reversed_probs = predictor(reversed_state, criteria)
        if set(reversed_probs) != set(criteria):
            raise ReflexBenchmarkError("REFLEX_BENCHMARK_PREDICTOR_LABEL_DRIFT")
        state_winner = _answer(reversed_probs)["choice"]

        result = ReflexBenchmarkCaseResult(
            case_id=case.case_id,
            expected_label=case.expected_label,
            base_winner=base_winner,
            ensemble_winner=ensemble.aggregate_winner,
            state_reversed_winner=state_winner,
            aggregate_peak_probability=ensemble.aggregate_peak_probability,
            winner_agreement=ensemble.winner_agreement,
            normalized_jsd=ensemble.normalized_jsd,
            base_correct=base_winner == case.expected_label,
            ensemble_correct=ensemble.aggregate_winner == case.expected_label,
            option_order_flip=len(set(ensemble.per_rotation_winner)) > 1,
            state_order_flip=state_winner != base_winner,
            multiclass_brier=_brier(aggregate_probs, case.expected_label),
        )
        results.append(result)
        calibration.append((result.aggregate_peak_probability, result.ensemble_correct))

    count = len(results)
    material = [
        {
            "case_id": item.case_id,
            "expected_label": item.expected_label,
            "base_winner": item.base_winner,
            "ensemble_winner": item.ensemble_winner,
            "state_reversed_winner": item.state_reversed_winner,
            "aggregate_peak_probability": item.aggregate_peak_probability,
            "winner_agreement": item.winner_agreement,
            "normalized_jsd": item.normalized_jsd,
        }
        for item in results
    ]
    return ReflexRobustnessBenchmarkReport(
        case_count=count,
        base_accuracy=sum(item.base_correct for item in results) / count,
        ensemble_accuracy=sum(item.ensemble_correct for item in results) / count,
        option_order_flip_rate=sum(item.option_order_flip for item in results) / count,
        state_order_flip_rate=sum(item.state_order_flip for item in results) / count,
        mean_normalized_jsd=sum(item.normalized_jsd for item in results) / count,
        multiclass_brier=sum(item.multiclass_brier for item in results) / count,
        ece=_ece(calibration),
        review_ready=count >= int(benchmark_policy["minimum_cases_before_review"]),
        benchmark_digest=sha256(_canonical(material)).hexdigest(),
        cases=tuple(results),
    )


def risk_samples_from_benchmark(
    report: ReflexRobustnessBenchmarkReport,
    *,
    policy: Mapping[str, Any] | None = None,
) -> tuple[RiskCalibrationSample, ...]:
    selected = dict(policy) if policy is not None else load_robustness_policy()
    cfg = selected["option_order_ensemble"]
    return tuple(
        RiskCalibrationSample(
            score=item.aggregate_peak_probability,
            correct=item.ensemble_correct,
            stable=(
                item.winner_agreement >= float(cfg["min_winner_agreement"])
                and item.normalized_jsd <= float(cfg["max_normalized_jsd"])
            ),
        )
        for item in report.cases
    )
