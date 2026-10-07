from __future__ import annotations

import pytest

from hazewave.reflex_benchmark import (
    ReflexBenchmarkCase,
    evaluate_reflex_robustness_benchmark,
    risk_samples_from_benchmark,
)


def _cases(count: int = 10):
    return tuple(
        ReflexBenchmarkCase(
            case_id=f"case-{index:03d}",
            state={"operation": "mix", "index": index},
            criteria={
                "HAZE": "audio engineering",
                "WAVE": "visual production",
                "BRIDGE": "cross-domain coordination",
            },
            expected_label="HAZE",
        )
        for index in range(count)
    )


def test_benchmark_measures_stable_predictor_without_persisting_state() -> None:
    def predictor(state, criteria):
        return {"HAZE": 0.90, "WAVE": 0.07, "BRIDGE": 0.03}

    report = evaluate_reflex_robustness_benchmark(_cases(), predictor=predictor)

    assert report.base_accuracy == 1.0
    assert report.ensemble_accuracy == 1.0
    assert report.option_order_flip_rate == 0.0
    assert report.state_order_flip_rate == 0.0
    assert report.mean_normalized_jsd == pytest.approx(0.0)
    assert report.review_ready is False
    assert report.grants_production_authority is False
    assert len(report.benchmark_digest) == 64
    samples = risk_samples_from_benchmark(report)
    assert len(samples) == 10
    assert all(sample.stable for sample in samples)
    assert all(sample.correct for sample in samples)


def test_benchmark_detects_option_order_sensitive_predictor() -> None:
    def predictor(state, criteria):
        first = next(iter(criteria))
        result = {label: 0.05 for label in criteria}
        result[first] = 0.90
        total = sum(result.values())
        return {key: value / total for key, value in result.items()}

    report = evaluate_reflex_robustness_benchmark(_cases(3), predictor=predictor)

    assert report.option_order_flip_rate == 1.0
    assert report.mean_normalized_jsd > 0
    samples = risk_samples_from_benchmark(report)
    assert all(sample.stable is False for sample in samples)


def test_benchmark_detects_state_key_order_sensitivity() -> None:
    def predictor(state, criteria):
        first_state_key = next(iter(state))
        if first_state_key == "operation":
            return {"HAZE": 0.9, "WAVE": 0.07, "BRIDGE": 0.03}
        return {"HAZE": 0.03, "WAVE": 0.9, "BRIDGE": 0.07}

    report = evaluate_reflex_robustness_benchmark(_cases(4), predictor=predictor)
    assert report.state_order_flip_rate == 1.0


def test_benchmark_review_gate_requires_real_case_volume() -> None:
    def predictor(state, criteria):
        return {"HAZE": 0.9, "WAVE": 0.07, "BRIDGE": 0.03}

    report = evaluate_reflex_robustness_benchmark(_cases(100), predictor=predictor)
    assert report.review_ready is True
    assert report.status == "EVIDENCE_ONLY"
