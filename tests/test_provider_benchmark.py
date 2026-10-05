from __future__ import annotations

import pytest

from hazewave.provider_benchmark import summarize_cross_provider_rows


def test_cross_provider_summary_ranks_per_capability_not_globally() -> None:
    rows = [
        {"capability":"code.review","provider":"nvidia","model_id":"nvidia/model","profile":"FAST_STRUCTURED","semantic_pass":True,"quality_score":0.95,"latency_ms":800,"total_tokens":120,"error_class":None},
        {"capability":"code.review","provider":"nvidia","model_id":"nvidia/model","profile":"FAST_STRUCTURED","semantic_pass":True,"quality_score":0.90,"latency_ms":1000,"total_tokens":130,"error_class":None},
        {"capability":"code.review","provider":"9router","model_id":"oc/big-pickle","profile":"DEFAULT","semantic_pass":True,"quality_score":0.75,"latency_ms":500,"total_tokens":90,"error_class":None},
        {"capability":"code.review","provider":"9router","model_id":"oc/big-pickle","profile":"DEFAULT","semantic_pass":False,"quality_score":0.0,"latency_ms":600,"total_tokens":100,"error_class":"EMPTY_SEMANTIC_RESPONSE"},
        {"capability":"reason.deep","provider":"nvidia","model_id":"nvidia/model","profile":"DEEP_REASONING","semantic_pass":True,"quality_score":1.0,"latency_ms":1600,"total_tokens":300,"error_class":None},
        {"capability":"reason.deep","provider":"9router","model_id":"oc/big-pickle","profile":"DEFAULT","semantic_pass":True,"quality_score":1.0,"latency_ms":1100,"total_tokens":220,"error_class":None},
    ]
    summary = summarize_cross_provider_rows(rows)
    assert set(summary["capabilities"]) == {"code.review", "reason.deep"}
    assert summary["capabilities"]["code.review"]["ranking"][0]["provider"] == "nvidia"
    assert summary["capabilities"]["reason.deep"]["ranking"][0]["provider"] == "9router"
    assert "global_winner" not in summary


def test_cross_provider_summary_reports_required_efficiency_metrics() -> None:
    rows = [
        {"capability":"reason.general","provider":"nvidia","model_id":"nvidia/model","profile":"FAST_STRUCTURED","semantic_pass":True,"quality_score":1.0,"latency_ms":1000,"total_tokens":100,"reasoning_tokens":0,"error_class":None},
        {"capability":"reason.general","provider":"nvidia","model_id":"nvidia/model","profile":"FAST_STRUCTURED","semantic_pass":False,"quality_score":0.0,"latency_ms":3000,"total_tokens":200,"reasoning_tokens":20,"error_class":"RATE_LIMITED"},
        {"capability":"reason.general","provider":"nvidia","model_id":"nvidia/model","profile":"FAST_STRUCTURED","semantic_pass":True,"quality_score":0.8,"latency_ms":2000,"total_tokens":120,"reasoning_tokens":5,"error_class":None},
    ]
    metrics = summarize_cross_provider_rows(rows)["capabilities"]["reason.general"]["routes"][0]
    assert metrics["semantic_success_rate"] == pytest.approx(2/3)
    assert metrics["p50_latency_ms"] == pytest.approx(2000)
    assert metrics["p95_latency_ms"] == pytest.approx(3000)
    assert metrics["tokens_per_successful_task"] == pytest.approx(220/2)
    assert metrics["rate_limit_rate"] == pytest.approx(1/3)
    assert metrics["reasoning_tokens_per_success"] == pytest.approx(5/2)


def test_benchmark_adds_task_family_rankings_without_global_winner() -> None:
    rows = [
        {"capability":"code.review","task_family":"review.aimd","provider":"nvidia","model_id":"nvidia/model","profile":"FAST_CODE","semantic_pass":True,"quality_score":1.0,"latency_ms":800,"total_tokens":100,"reasoning_tokens":0,"fallback_count":0,"error_class":None},
        {"capability":"code.review","task_family":"review.aimd","provider":"9router","model_id":"oc/model","profile":"DEFAULT","semantic_pass":True,"quality_score":0.8,"latency_ms":400,"total_tokens":80,"reasoning_tokens":0,"fallback_count":0,"error_class":None},
        {"capability":"code.review","task_family":"review.cache","provider":"nvidia","model_id":"nvidia/model","profile":"FAST_CODE","semantic_pass":True,"quality_score":0.7,"latency_ms":700,"total_tokens":100,"reasoning_tokens":0,"fallback_count":0,"error_class":None},
        {"capability":"code.review","task_family":"review.cache","provider":"9router","model_id":"oc/model","profile":"DEFAULT","semantic_pass":True,"quality_score":1.0,"latency_ms":500,"total_tokens":90,"reasoning_tokens":0,"fallback_count":0,"error_class":None},
    ]
    summary = summarize_cross_provider_rows(rows)
    assert summary["task_families"]["code.review"]["review.aimd"]["ranking"][0]["provider"] == "nvidia"
    assert summary["task_families"]["code.review"]["review.cache"]["ranking"][0]["provider"] == "9router"
    assert "global_winner" not in summary


def test_useful_work_score_penalizes_tokens_latency_and_fallback_after_quality() -> None:
    rows = [
        {"capability":"reason.general","task_family":"a","provider":"nvidia","model_id":"nvidia/efficient","profile":"FAST_STRUCTURED","semantic_pass":True,"quality_score":1.0,"latency_ms":500,"total_tokens":80,"reasoning_tokens":0,"fallback_count":0,"error_class":None},
        {"capability":"reason.general","task_family":"a","provider":"nvidia","model_id":"nvidia/wasteful","profile":"FAST_STRUCTURED","semantic_pass":True,"quality_score":1.0,"latency_ms":5000,"total_tokens":2000,"reasoning_tokens":0,"fallback_count":1,"error_class":None},
    ]
    ranking = summarize_cross_provider_rows(rows)["capabilities"]["reason.general"]["ranking"]
    assert ranking[0]["model_id"] == "nvidia/efficient"
    assert ranking[0]["useful_work_score"] > ranking[1]["useful_work_score"]
