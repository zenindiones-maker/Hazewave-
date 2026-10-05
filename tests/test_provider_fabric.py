from __future__ import annotations

from pathlib import Path

import pytest

from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.provider_fabric import (
    ProviderRoute,
    execute_provider_routes,
    load_provider_learning,
    rank_provider_routes,
    record_provider_result,
)
from hazewave.provider_runtime import HazewaveProviderExecutionResult


def _authorization(capability: str = "code.review"):
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id="fabric-001",
                goal="review code",
                required_capability=capability,
                requested_domain=HAZE,
            )
        )
    )


def _route(provider: str, model: str, profile: str) -> ProviderRoute:
    return ProviderRoute(
        provider=provider,
        model_id=model,
        execution_profile=profile,
        capability_id="code.review",
        cost_class=(
            "ZERO_COST_VERIFIED"
            if provider == "9router"
            else "FREE_DEVELOPMENT_ENDPOINT"
        ),
    )


def _result(route: ProviderRoute, *, status: str, error: str | None = None,
            quality: float | None = None, latency: int = 1000,
            total_tokens: int = 100) -> HazewaveProviderExecutionResult:
    return HazewaveProviderExecutionResult(
        provider=route.provider,
        model_id=route.model_id,
        execution_profile=route.execution_profile,
        capability_id=route.capability_id,
        status=status,
        content="ok" if status == "PASS" else "",
        finish_reason="stop" if status == "PASS" else None,
        prompt_tokens=80 if status == "PASS" else None,
        completion_tokens=20 if status == "PASS" else None,
        reasoning_tokens=5 if status == "PASS" else None,
        total_tokens=total_tokens if status == "PASS" else None,
        latency_ms=latency,
        tool_calls=(),
        error_class=error,
        http_status=200 if status == "PASS" else 503,
        retry_after_seconds=None,
        cost_class=route.cost_class,
        semantic_pass=(status == "PASS"),
        quality_score=quality,
    )


def test_learning_persists_per_provider_model_profile_capability(tmp_path: Path) -> None:
    path = tmp_path / "provider-learning.json"
    route = _route("nvidia", "nvidia/nemotron-3.5-lightning-30b-a3b", "DEEP_REASONING")
    record_provider_result(
        path=path,
        route=route,
        result=_result(route, status="PASS", quality=0.91, latency=1400, total_tokens=180),
        fallback_used=False,
        now="2026-10-05T16:00:00+00:00",
    )
    record_provider_result(
        path=path,
        route=route,
        result=_result(route, status="FAIL", error="RATE_LIMITED"),
        fallback_used=True,
        now="2026-10-05T16:01:00+00:00",
    )

    state = load_provider_learning(path)
    row = state["routes"][route.route_key]
    assert row["attempt_count"] == 2
    assert row["pass_count"] == 1
    assert row["semantic_failure_count"] == 0
    assert row["429_count"] == 1
    assert row["fallback_count"] == 1
    assert row["quality_score"] == pytest.approx(0.91)
    assert row["input_tokens"] == 80
    assert row["output_tokens"] == 20
    assert row["reasoning_tokens"] == 5
    assert path.stat().st_mode & 0o777 == 0o600


def test_quality_failure_capacity_auth_and_outage_are_not_mixed(tmp_path: Path) -> None:
    path = tmp_path / "provider-learning.json"
    route = _route("nvidia", "nvidia/nemotron-3.5-lightning-30b-a3b", "FAST_STRUCTURED")
    for error in (
        "EMPTY_SEMANTIC_RESPONSE",
        "TOKEN_BUDGET_EXHAUSTED",
        "RATE_LIMITED",
        "AUTH_OR_ELIGIBILITY_FAILURE",
        "PROVIDER_SERVER_FAILURE",
        "PROVIDER_TIMEOUT",
    ):
        record_provider_result(
            path=path,
            route=route,
            result=_result(route, status="FAIL", error=error),
            fallback_used=False,
            now="2026-10-05T16:00:00+00:00",
        )
    row = load_provider_learning(path)["routes"][route.route_key]
    assert row["empty_count"] == 1
    assert row["token_budget_exhaustion_count"] == 1
    assert row["429_count"] == 1
    assert row["auth_or_eligibility_count"] == 1
    assert row["5xx_count"] == 1
    assert row["timeout_count"] == 1


def test_ranking_uses_evidence_not_fixed_provider_preference(tmp_path: Path) -> None:
    path = tmp_path / "provider-learning.json"
    nvidia = _route("nvidia", "nvidia/nemotron-3.5-lightning-30b-a3b", "FAST_STRUCTURED")
    router = _route("9router", "oc/big-pickle", "DEFAULT")

    for _ in range(5):
        record_provider_result(
            path=path, route=nvidia,
            result=_result(nvidia, status="PASS", quality=0.95, latency=900, total_tokens=90),
            fallback_used=False, now="2026-10-05T16:00:00+00:00",
        )
        record_provider_result(
            path=path, route=router,
            result=_result(router, status="PASS", quality=0.60, latency=500, total_tokens=80),
            fallback_used=False, now="2026-10-05T16:00:00+00:00",
        )

    ranked = rank_provider_routes(
        routes=[router, nvidia],
        state=load_provider_learning(path),
        task_id="fabric-001",
        now="2026-10-05T16:05:00+00:00",
    )
    assert ranked[0] == nvidia


def test_cross_provider_fallback_is_bounded_and_never_revisits_route(tmp_path: Path) -> None:
    path = tmp_path / "provider-learning.json"
    nvidia = _route("nvidia", "nvidia/nemotron-3.5-lightning-30b-a3b", "FAST_STRUCTURED")
    router = _route("9router", "oc/big-pickle", "DEFAULT")
    calls = []

    def executor(route: ProviderRoute) -> HazewaveProviderExecutionResult:
        calls.append(route.route_key)
        if route.provider == "nvidia":
            return _result(route, status="FAIL", error="RATE_LIMITED")
        return _result(route, status="PASS", quality=0.85)

    result = execute_provider_routes(
        authorization=_authorization(),
        routes=[nvidia, router, nvidia],
        executor=executor,
        learning_path=path,
        max_attempts=2,
        now="2026-10-05T16:00:00+00:00",
    )

    assert result.status == "PASS"
    assert result.provider == "9router"
    assert calls == [nvidia.route_key, router.route_key]
    assert len(set(calls)) == len(calls)


def test_cross_provider_max_attempts_hard_bounds_failures(tmp_path: Path) -> None:
    path = tmp_path / "provider-learning.json"
    routes = [
        _route("nvidia", "nvidia/nemotron-3.5-lightning-30b-a3b", "FAST_STRUCTURED"),
        _route("9router", "oc/big-pickle", "DEFAULT"),
        _route("9router", "oc/mimo-v2.6-flash-free", "DEFAULT"),
    ]
    calls = []

    def executor(route: ProviderRoute) -> HazewaveProviderExecutionResult:
        calls.append(route.route_key)
        return _result(route, status="FAIL", error="PROVIDER_SERVER_FAILURE")

    result = execute_provider_routes(
        authorization=_authorization(),
        routes=routes,
        executor=executor,
        learning_path=path,
        max_attempts=2,
        now="2026-10-05T16:00:00+00:00",
    )
    assert result.status == "FAIL"
    assert len(calls) == 2


def test_provider_wide_auth_cooldown_blocks_sibling_routes(tmp_path: Path) -> None:
    path = tmp_path / "provider-learning.json"
    fast = _route("nvidia", "nvidia/nemotron-3.5-lightning-30b-a3b", "FAST_STRUCTURED")
    deep = ProviderRoute(
        provider="nvidia",
        model_id="nvidia/nemotron-3.5-lightning-30b-a3b",
        execution_profile="DEEP_REASONING",
        capability_id="code.review",
        cost_class="FREE_DEVELOPMENT_ENDPOINT",
    )
    record_provider_result(
        path=path,
        route=fast,
        result=_result(fast, status="FAIL", error="AUTH_OR_ELIGIBILITY_FAILURE"),
        fallback_used=False,
        now="2026-10-05T16:00:00+00:00",
    )
    ranked = rank_provider_routes(
        routes=[deep],
        state=load_provider_learning(path),
        task_id="fabric-001",
        now="2026-10-05T16:01:00+00:00",
    )
    assert ranked == []


def test_semantic_failure_does_not_provider_ban_sibling_profile(tmp_path: Path) -> None:
    path = tmp_path / "provider-learning.json"
    fast = _route("nvidia", "nvidia/nemotron-3.5-lightning-30b-a3b", "FAST_STRUCTURED")
    deep = ProviderRoute(
        provider="nvidia",
        model_id="nvidia/nemotron-3.5-lightning-30b-a3b",
        execution_profile="DEEP_REASONING",
        capability_id="code.review",
        cost_class="FREE_DEVELOPMENT_ENDPOINT",
    )
    record_provider_result(
        path=path,
        route=fast,
        result=_result(fast, status="FAIL", error="EMPTY_SEMANTIC_RESPONSE"),
        fallback_used=False,
        now="2026-10-05T16:00:00+00:00",
    )
    ranked = rank_provider_routes(
        routes=[deep],
        state=load_provider_learning(path),
        task_id="fabric-001",
        now="2026-10-05T16:01:00+00:00",
    )
    assert ranked == [deep]


from hazewave.provider_fabric import (
    build_cross_provider_routes,
    canonicalize_ninerouter_result,
)
from hazewave.ninerouter import NineRouterExecutionResult


def _nvidia_receipt_for_fabric() -> dict:
    return {
        "schema": "HazewaveNvidiaProviderAdmission/v1",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "provider": "nvidia",
        "provider_authority": "NONE",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "cost_class": "FREE_DEVELOPMENT_ENDPOINT",
        "paid_fallback": "FORBIDDEN",
        "unknown_cost": "DENY",
        "development_endpoint_allowed": True,
        "known_billing_status": "NO_KNOWN_CHARGE_FOR_PROTOTYPE_FREE_ENDPOINT",
        "allowed_data_classes": ["PUBLIC"],
        "admitted_models": ["nvidia/nemotron-3.5-lightning-30b-a3b"],
        "profiles": ["FAST_STRUCTURED", "DEEP_REASONING"],
        "observed_at": "2026-10-05T12:00:00+00:00",
        "expires_at": "2026-10-12T12:00:00+00:00",
        "source_evidence": ["https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b"],
    }


def test_cross_provider_route_builder_only_admits_hard_eligible_routes() -> None:
    routes = build_cross_provider_routes(
        authorization=_authorization(),
        ninerouter_models=["oc/big-pickle", "oc/mimo-v2.6-flash-free"],
        nvidia_receipt=_nvidia_receipt_for_fabric(),
        now="2026-10-05T16:00:00+00:00",
    )
    assert {route.provider for route in routes} == {"9router", "nvidia"}
    nvidia = next(route for route in routes if route.provider == "nvidia")
    assert nvidia.execution_profile == "FAST_STRUCTURED"

    denied = _nvidia_receipt_for_fabric()
    denied["cost_class"] = "UNKNOWN"
    routes = build_cross_provider_routes(
        authorization=_authorization(),
        ninerouter_models=["oc/big-pickle"],
        nvidia_receipt=denied,
        now="2026-10-05T16:00:00+00:00",
    )
    assert [route.provider for route in routes] == ["9router"]


def test_deep_capability_builds_deep_nvidia_profile() -> None:
    routes = build_cross_provider_routes(
        authorization=_authorization("reason.deep"),
        ninerouter_models=["oc/big-pickle"],
        nvidia_receipt=_nvidia_receipt_for_fabric(),
        now="2026-10-05T16:00:00+00:00",
    )
    nvidia = next(route for route in routes if route.provider == "nvidia")
    assert nvidia.execution_profile == "DEEP_REASONING"


def test_ninerouter_result_canonicalizes_without_changing_gateway_authority() -> None:
    legacy = NineRouterExecutionResult(
        status="PASS",
        task_id="fabric-001",
        authorization_id="auth",
        model_id="oc/big-pickle",
        content="answer",
        prompt_tokens=10,
        completion_tokens=3,
        total_tokens=13,
        reasoning_tokens=2,
        fallback_count=0,
    )
    canonical = canonicalize_ninerouter_result(
        result=legacy,
        capability_id="code.review",
        latency_ms=700,
        quality_score=0.9,
    )
    assert canonical.provider == "9router"
    assert canonical.provider_gateway == "9router"
    assert canonical.cost_class == "ZERO_COST_VERIFIED"
    assert canonical.semantic_pass is True
    assert canonical.model_id == "oc/big-pickle"
