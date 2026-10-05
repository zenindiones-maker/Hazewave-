from __future__ import annotations

from typing import Any


def compare_parameter_ab(
    control: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, float | int]:
    if control.get("task_id") != candidate.get("task_id"):
        raise ValueError("EXPERIMENT_TASK_MISMATCH")
    if control.get("model_id") != candidate.get("model_id"):
        raise ValueError("EXPERIMENT_MODEL_MISMATCH")
    if control.get("seed") != candidate.get("seed"):
        raise ValueError("EXPERIMENT_SEED_MISMATCH")

    control_semantic = 1 if control.get("semantic_pass") is True else 0
    candidate_semantic = 1 if candidate.get("semantic_pass") is True else 0
    control_quality = float(control.get("quality_score") or 0.0)
    candidate_quality = float(candidate.get("quality_score") or 0.0)
    control_tokens = int(control.get("total_tokens") or 0)
    candidate_tokens = int(candidate.get("total_tokens") or 0)
    control_latency = int(control.get("latency_ms") or 0)
    candidate_latency = int(candidate.get("latency_ms") or 0)

    return {
        "semantic_success_delta": candidate_semantic - control_semantic,
        "quality_delta": candidate_quality - control_quality,
        "token_delta": candidate_tokens - control_tokens,
        "latency_delta_ms": candidate_latency - control_latency,
    }


def select_minimum_reasoning_budget(
    rows: list[dict[str, Any]],
    *,
    quality_floor: float,
) -> int | None:
    qualified = []
    for row in rows:
        if row.get("semantic_pass") is not True:
            continue
        quality = row.get("quality_score")
        if not isinstance(quality, (int, float)):
            continue
        if float(quality) < float(quality_floor):
            continue
        budget = row.get("reasoning_budget")
        if not isinstance(budget, int) or budget < 0:
            continue
        qualified.append(budget)
    return min(qualified) if qualified else None


def select_sustainable_concurrency(
    points: list[dict[str, Any]],
    *,
    minimum_semantic_success_rate: float = 0.95,
    maximum_429_rate: float = 0.05,
    maximum_fallback_rate: float = 0.10,
    maximum_p95_multiplier: float = 2.0,
) -> int:
    if not points:
        raise ValueError("CONCURRENCY_POINTS_REQUIRED")
    ordered = sorted(points, key=lambda row: int(row.get("concurrency") or 0))
    if int(ordered[0].get("concurrency") or 0) != 1:
        raise ValueError("CONCURRENCY_BASELINE_REQUIRED")
    baseline_p95 = float(ordered[0].get("p95_latency_ms") or 0.0)
    if baseline_p95 <= 0:
        raise ValueError("CONCURRENCY_BASELINE_LATENCY_INVALID")

    selected = 1
    for point in ordered:
        concurrency = int(point.get("concurrency") or 0)
        if concurrency < 1:
            continue
        semantic_rate = float(point.get("semantic_success_rate") or 0.0)
        rate_429 = float(point.get("429_rate") or 0.0)
        fallback_rate = float(point.get("fallback_rate") or 0.0)
        p95 = float(point.get("p95_latency_ms") or 0.0)
        healthy = (
            semantic_rate >= minimum_semantic_success_rate
            and rate_429 <= maximum_429_rate
            and fallback_rate <= maximum_fallback_rate
            and p95 <= baseline_p95 * maximum_p95_multiplier
        )
        if not healthy:
            break
        selected = concurrency
    return selected


def build_model_access_canary_request(model_id: str) -> dict[str, Any]:
    model = str(model_id or "").strip()
    if not model:
        raise ValueError("MODEL_CANARY_MODEL_REQUIRED")
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Respond exactly HAZEWAVE_NVIDIA_CANARY_OK",
            }
        ],
        "max_tokens": 64,
        "stream": False,
        "temperature": 0.0,
    }
