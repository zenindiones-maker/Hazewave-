from __future__ import annotations

import pytest

from hazewave.nvidia_experiments import (
    build_model_access_canary_request,
    compare_parameter_ab,
    select_minimum_reasoning_budget,
    select_sustainable_concurrency,
)


def test_parameter_ab_requires_same_model_task_and_seed() -> None:
    control = {
        "task_id": "task-1",
        "model_id": "nvidia/model",
        "seed": 42,
        "semantic_pass": True,
        "quality_score": 1.0,
        "total_tokens": 100,
        "latency_ms": 1000,
    }
    candidate = dict(control)
    candidate.update(total_tokens=70, latency_ms=800)
    result = compare_parameter_ab(control, candidate)
    assert result["semantic_success_delta"] == 0
    assert result["token_delta"] == -30
    assert result["latency_delta_ms"] == -200

    bad = dict(candidate)
    bad["seed"] = 43
    with pytest.raises(ValueError, match="EXPERIMENT_SEED_MISMATCH"):
        compare_parameter_ab(control, bad)


def test_reasoning_budget_selects_smallest_budget_meeting_quality_floor() -> None:
    rows = [
        {"reasoning_budget": 512, "semantic_pass": True, "quality_score": 0.82},
        {"reasoning_budget": 1024, "semantic_pass": True, "quality_score": 0.96},
        {"reasoning_budget": 2048, "semantic_pass": True, "quality_score": 0.98},
    ]
    selected = select_minimum_reasoning_budget(rows, quality_floor=0.95)
    assert selected == 1024


def test_reasoning_budget_does_not_select_failed_budget() -> None:
    rows = [
        {"reasoning_budget": 512, "semantic_pass": False, "quality_score": 1.0},
        {"reasoning_budget": 1024, "semantic_pass": True, "quality_score": 0.95},
    ]
    assert select_minimum_reasoning_budget(rows, quality_floor=0.9) == 1024


def test_concurrency_selector_stops_before_degradation() -> None:
    points = [
        {"concurrency": 1, "semantic_success_rate": 1.0, "p95_latency_ms": 1000, "429_rate": 0.0, "fallback_rate": 0.0},
        {"concurrency": 2, "semantic_success_rate": 1.0, "p95_latency_ms": 1300, "429_rate": 0.0, "fallback_rate": 0.0},
        {"concurrency": 4, "semantic_success_rate": 0.98, "p95_latency_ms": 1700, "429_rate": 0.02, "fallback_rate": 0.02},
        {"concurrency": 8, "semantic_success_rate": 0.80, "p95_latency_ms": 5000, "429_rate": 0.20, "fallback_rate": 0.30},
    ]
    assert select_sustainable_concurrency(points) == 4


def test_concurrency_selector_requires_concurrency_one_baseline() -> None:
    with pytest.raises(ValueError, match="CONCURRENCY_BASELINE_REQUIRED"):
        select_sustainable_concurrency([
            {"concurrency": 2, "semantic_success_rate": 1.0, "p95_latency_ms": 1000, "429_rate": 0.0, "fallback_rate": 0.0}
        ])


def test_model_access_canary_uses_only_minimal_model_agnostic_parameters() -> None:
    body = build_model_access_canary_request(
        "nvidia/nemotron-3-super-120b-a12b"
    )
    assert body["model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert body["stream"] is False
    assert body["max_tokens"] == 64
    assert body["temperature"] == 0.0
    assert "chat_template_kwargs" not in body
    assert "reasoning_budget" not in body
    assert "tools" not in body
    assert "response_format" not in body
