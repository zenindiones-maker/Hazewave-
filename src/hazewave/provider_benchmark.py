from __future__ import annotations

import math
from typing import Any


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def _nearest_rank(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(math.ceil(fraction * len(ordered)))))
    return float(ordered[rank - 1])


def _route_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    successes = [row for row in rows if row.get("semantic_pass") is True]
    latencies = [
        float(row["latency_ms"])
        for row in rows
        if isinstance(row.get("latency_ms"), (int, float))
    ]
    quality_values = [
        float(row["quality_score"])
        for row in rows
        if isinstance(row.get("quality_score"), (int, float))
    ]
    successful_tokens = sum(
        max(0, int(row.get("total_tokens") or 0))
        for row in successes
    )
    successful_reasoning = sum(
        max(0, int(row.get("reasoning_tokens") or 0))
        for row in successes
    )
    rate_limits = sum(
        1 for row in rows if row.get("error_class") == "RATE_LIMITED"
    )
    empties = sum(
        1
        for row in rows
        if row.get("error_class") == "EMPTY_SEMANTIC_RESPONSE"
    )
    fallback_count = sum(max(0, int(row.get("fallback_count") or 0)) for row in rows)

    semantic_success_rate = len(successes) / max(1, total)
    quality_score = sum(quality_values) / max(1, len(quality_values))
    p50_latency_ms = _median(latencies)
    tokens_per_successful_task = successful_tokens / max(1, len(successes))
    fallback_rate = fallback_count / max(1, total)
    useful_work_score = (
        semantic_success_rate
        * quality_score
        / (
            1.0
            + tokens_per_successful_task / 1000.0
            + p50_latency_ms / 5000.0
            + fallback_rate * 2.0
        )
    )

    first = rows[0]
    return {
        "provider": first.get("provider"),
        "model_id": first.get("model_id"),
        "execution_profile": first.get("profile"),
        "sample_count": total,
        "semantic_success_rate": semantic_success_rate,
        "quality_score": quality_score,
        "p50_latency_ms": p50_latency_ms,
        "p95_latency_ms": _nearest_rank(latencies, 0.95),
        "tokens_per_successful_task": tokens_per_successful_task,
        "reasoning_tokens_per_success": successful_reasoning / max(1, len(successes)),
        "fallback_rate": fallback_rate,
        "empty_rate": empties / max(1, total),
        "rate_limit_rate": rate_limits / max(1, total),
        "useful_work_score": useful_work_score,
    }


def summarize_cross_provider_rows(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    grouped: dict[str, dict[tuple[str, str, str], list[dict[str, Any]]]] = {}
    for row in rows:
        capability = str(row.get("capability") or "")
        provider = str(row.get("provider") or "")
        model_id = str(row.get("model_id") or "")
        profile = str(row.get("profile") or "")
        if not capability or not provider or not model_id or not profile:
            raise ValueError("CROSS_PROVIDER_BENCHMARK_ROW_INVALID")
        grouped.setdefault(capability, {}).setdefault(
            (provider, model_id, profile),
            [],
        ).append(row)

    capabilities: dict[str, Any] = {}
    for capability, route_groups in sorted(grouped.items()):
        route_metrics = [
            _route_metrics(route_rows)
            for _, route_rows in sorted(route_groups.items())
        ]
        ranking = sorted(
            route_metrics,
            key=lambda metric: (
                -float(metric["semantic_success_rate"]),
                -float(metric["quality_score"]),
                -float(metric["useful_work_score"]),
                float(metric["tokens_per_successful_task"]),
                float(metric["p50_latency_ms"]),
                str(metric["provider"]),
                str(metric["model_id"]),
            ),
        )
        capabilities[capability] = {
            "routes": route_metrics,
            "ranking": ranking,
        }
    family_grouped: dict[
        str,
        dict[str, dict[tuple[str, str, str], list[dict[str, Any]]]],
    ] = {}
    for row in rows:
        capability = str(row.get("capability") or "")
        task_family = str(row.get("task_family") or "generic")
        key = (
            str(row.get("provider") or ""),
            str(row.get("model_id") or ""),
            str(row.get("profile") or ""),
        )
        family_grouped.setdefault(capability, {}).setdefault(
            task_family, {}
        ).setdefault(key, []).append(row)

    task_families: dict[str, Any] = {}
    for capability, families in sorted(family_grouped.items()):
        capability_families: dict[str, Any] = {}
        for family, route_groups in sorted(families.items()):
            route_metrics = [
                _route_metrics(route_rows)
                for _, route_rows in sorted(route_groups.items())
            ]
            ranking = sorted(
                route_metrics,
                key=lambda metric: (
                    -float(metric["semantic_success_rate"]),
                    -float(metric["quality_score"]),
                    -float(metric["useful_work_score"]),
                    float(metric["tokens_per_successful_task"]),
                    float(metric["p50_latency_ms"]),
                    str(metric["provider"]),
                    str(metric["model_id"]),
                ),
            )
            capability_families[family] = {
                "routes": route_metrics,
                "ranking": ranking,
            }
        task_families[capability] = capability_families

    return {
        "schema": "HazewaveCrossProviderBenchmarkSummary/v2",
        "authority": "HAZEWAVE_HARNESS",
        "capabilities": capabilities,
        "task_families": task_families,
    }
