from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from hazewave.nvidia import (
    FAST_STRUCTURED,
    NvidiaNIMAdapter,
    normalize_nvidia_request,
)
from hazewave.nvidia_optimization import (
    DEEP_HARD,
    DEEP_MEDIUM,
    FAST_CODE,
    HARD,
    MODERATE,
    SIMPLE,
    VERY_HARD,
    TaskComplexitySignals,
    classify_task_complexity,
    next_reasoning_budget,
    reasoning_budget_for_complexity,
    select_nvidia_execution_profile,
    update_nvidia_concurrency,
    load_nvidia_optimization_state,
    evaluate_model_lifecycle,
)
from hazewave.nvidia_proof import evaluate_probe_item
from hazewave.provider_runtime import HazewaveProviderExecutionResult


MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"


def _result(content: str) -> HazewaveProviderExecutionResult:
    return HazewaveProviderExecutionResult(
        provider="nvidia",
        model_id=MODEL,
        execution_profile=FAST_CODE,
        capability_id="code.generate",
        status="PASS",
        content=content,
        finish_reason="stop",
        prompt_tokens=10,
        completion_tokens=10,
        reasoning_tokens=0,
        total_tokens=20,
        latency_ms=100,
        tool_calls=(),
        error_class=None,
        http_status=200,
        retry_after_seconds=None,
        cost_class="FREE_DEVELOPMENT_ENDPOINT",
        semantic_pass=True,
    )


def test_short_structured_reason_deep_is_not_forced_to_deep_hard() -> None:
    complexity = classify_task_complexity(
        TaskComplexitySignals(
            capability_id="reason.deep",
            task_family="provider.failure.classification",
            estimated_context_tokens=300,
            constraint_count=3,
            dependent_reasoning_steps=2,
            structured_output=True,
        )
    )
    assert complexity in {SIMPLE, MODERATE}
    assert select_nvidia_execution_profile(
        capability_id="reason.deep",
        complexity=complexity,
        structured_output=True,
    ) == FAST_STRUCTURED


def test_hard_architecture_task_selects_deep_hard() -> None:
    complexity = classify_task_complexity(
        TaskComplexitySignals(
            capability_id="reason.deep",
            task_family="architecture.distributed-state",
            estimated_context_tokens=18000,
            constraint_count=9,
            dependent_reasoning_steps=8,
            evidence_items=12,
            historical_failure_count=2,
        )
    )
    assert complexity in {HARD, VERY_HARD}
    assert select_nvidia_execution_profile(
        capability_id="reason.deep",
        complexity=complexity,
        structured_output=False,
    ) == DEEP_HARD


def test_small_code_task_selects_fast_code() -> None:
    assert select_nvidia_execution_profile(
        capability_id="code.generate",
        complexity=SIMPLE,
        structured_output=False,
    ) == FAST_CODE


@pytest.mark.parametrize(
    ("complexity", "expected"),
    [
        (SIMPLE, 0),
        (MODERATE, 512),
        (HARD, 1024),
        (VERY_HARD, 2048),
    ],
)
def test_reasoning_budget_ladder_is_complexity_aware(
    complexity: str, expected: int
) -> None:
    assert reasoning_budget_for_complexity(complexity) == expected


@pytest.mark.parametrize(
    "error_class",
    [
        "RATE_LIMITED",
        "AUTH_OR_ELIGIBILITY_FAILURE",
        "PROVIDER_SERVER_FAILURE",
        "PROVIDER_TIMEOUT",
    ],
)
def test_capacity_and_auth_failures_never_escalate_reasoning_budget(
    error_class: str,
) -> None:
    assert next_reasoning_budget(
        current_budget=512,
        error_class=error_class,
        may_benefit_from_more_reasoning=True,
    ) == 512


def test_token_exhaustion_can_escalate_one_bounded_budget_step() -> None:
    assert next_reasoning_budget(
        current_budget=512,
        error_class="TOKEN_BUDGET_EXHAUSTED",
        may_benefit_from_more_reasoning=True,
    ) == 1024


def test_semantic_failure_requires_explicit_evidence_before_budget_escalation() -> None:
    assert next_reasoning_budget(
        current_budget=512,
        error_class="SEMANTIC_CONTRACT_FAILURE",
        may_benefit_from_more_reasoning=False,
    ) == 512
    assert next_reasoning_budget(
        current_budget=512,
        error_class="SEMANTIC_CONTRACT_FAILURE",
        may_benefit_from_more_reasoning=True,
    ) == 1024


def test_deterministic_sampling_sends_temperature_only_and_seed() -> None:
    payload = normalize_nvidia_request(
        model_id=MODEL,
        messages=[{"role": "user", "content": "classify"}],
        execution_profile=FAST_STRUCTURED,
        capability_id="reason.general",
        sampling_policy="DETERMINISTIC_STRUCTURED",
        seed=42,
        compatibility={
            "temperature_supported": True,
            "top_p_supported": True,
            "seed_supported": True,
            "max_output_tokens": 32768,
        },
    )
    assert payload["temperature"] == 0
    assert "top_p" not in payload
    assert payload["seed"] == 42


def test_top_p_sampling_sends_top_p_only() -> None:
    payload = normalize_nvidia_request(
        model_id=MODEL,
        messages=[{"role": "user", "content": "sample"}],
        execution_profile=FAST_STRUCTURED,
        capability_id="reason.general",
        sampling_policy="TOP_P_EXPERIMENT",
        top_p=0.8,
        compatibility={
            "temperature_supported": True,
            "top_p_supported": True,
            "max_output_tokens": 32768,
        },
    )
    assert payload["top_p"] == pytest.approx(0.8)
    assert "temperature" not in payload


def test_provider_default_sampling_sends_neither_temperature_nor_top_p() -> None:
    payload = normalize_nvidia_request(
        model_id=MODEL,
        messages=[{"role": "user", "content": "default"}],
        execution_profile=FAST_STRUCTURED,
        capability_id="reason.general",
        sampling_policy="PROVIDER_DEFAULT",
        compatibility={
            "temperature_supported": True,
            "top_p_supported": True,
            "max_output_tokens": 32768,
        },
    )
    assert "temperature" not in payload
    assert "top_p" not in payload


def test_python_behavior_evaluator_accepts_equivalent_implementation_shape() -> None:
    item = {
        "evaluation": {
            "kind": "PYTHON_RESTRICTED_BEHAVIOR",
            "function_name": "clamp_retry_after",
            "cases": [
                {"args": [-5], "expected": 0},
                {"args": [45], "expected": 45},
                {"args": [5000], "expected": 3600},
                {"args": [12.5], "expected": 12.5},
            ],
        }
    }
    evaluation = evaluate_probe_item(
        item,
        _result(
            "def clamp_retry_after(seconds):\n"
            "    return min(max(seconds, 0), 3600)\n"
        ),
    )
    assert evaluation.semantic_pass is True


def test_python_behavior_evaluator_rejects_wrong_behavior() -> None:
    item = {
        "evaluation": {
            "kind": "PYTHON_RESTRICTED_BEHAVIOR",
            "function_name": "clamp_retry_after",
            "cases": [{"args": [5000], "expected": 3600}],
        }
    }
    evaluation = evaluate_probe_item(
        item,
        _result("def clamp_retry_after(seconds):\n    return seconds\n"),
    )
    assert evaluation.semantic_pass is False


def test_nvidia_concurrency_aimd_grows_slowly_and_halves_on_429(tmp_path: Path) -> None:
    path = tmp_path / "nvidia-opt.json"
    for index in range(4):
        update_nvidia_concurrency(
            path=path,
            model_id=MODEL,
            outcome="PASS",
            latency_ms=1000,
            now=f"2026-10-05T16:00:0{index}+00:00",
        )
    before = load_nvidia_optimization_state(path)["concurrency"]["limit"]
    assert before >= 2

    update_nvidia_concurrency(
        path=path,
        model_id=MODEL,
        outcome="RATE_LIMITED",
        retry_after_seconds=30,
        latency_ms=2000,
        now="2026-10-05T16:01:00+00:00",
    )
    after = load_nvidia_optimization_state(path)
    assert after["concurrency"]["limit"] == max(1, before // 2)
    assert after["concurrency"]["cooldown_kind"] == "RATE_LIMITED"


def test_model_lifecycle_requires_admitted_and_current_free_development_status() -> None:
    receipt = {
        "model_lifecycle": {
            MODEL: {
                "stage": "ADMITTED",
                "cost_class": "FREE_DEVELOPMENT_ENDPOINT",
                "free_endpoint_available": True,
            },
            "nvidia/nemotron-3-super-120b-a12b": {
                "stage": "COST_STATUS_VERIFIED",
                "cost_class": "FREE_DEVELOPMENT_ENDPOINT",
                "free_endpoint_available": True,
            },
        }
    }
    assert evaluate_model_lifecycle(receipt, MODEL).allowed is True
    super_decision = evaluate_model_lifecycle(
        receipt, "nvidia/nemotron-3-super-120b-a12b"
    )
    assert super_decision.allowed is False
    assert super_decision.reason == "NVIDIA_MODEL_NOT_ADMITTED"


def test_adapter_reuses_long_lived_http_client(tmp_path: Path) -> None:
    secret = tmp_path / "nvidia.env"
    secret.write_text("NVIDIA_API_KEY=nvapi-unit-test\n", encoding="utf-8")
    secret.chmod(0o600)
    receipt = {
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
        "admitted_models": [MODEL],
        "profiles": ["FAST_STRUCTURED"],
        "observed_at": "2026-10-05T12:00:00+00:00",
        "expires_at": "2026-10-12T12:00:00+00:00",
        "source_evidence": ["https://build.nvidia.com/"],
        "model_contracts": {
            MODEL: {
                "temperature_supported": True,
                "top_p_supported": True,
                "max_output_tokens": 32768,
            }
        },
    }
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task

    auth = issue_authorization(
        route_task(
            HazewaveTask(
                task_id="reuse",
                goal="reuse",
                required_capability="reason.general",
                requested_domain=HAZE,
            )
        )
    )
    adapter = NvidiaNIMAdapter(
        secret_path=secret,
        receipt=receipt,
        transport=httpx.MockTransport(handler),
    )
    first_client_id = adapter.client_identity
    adapter.execute(
        authorization=auth,
        model_id=MODEL,
        execution_profile=FAST_STRUCTURED,
        messages=[{"role": "user", "content": "one"}],
        now="2026-10-05T16:00:00+00:00",
    )
    second_client_id = adapter.client_identity
    adapter.execute(
        authorization=auth,
        model_id=MODEL,
        execution_profile=FAST_STRUCTURED,
        messages=[{"role": "user", "content": "two"}],
        now="2026-10-05T16:00:00+00:00",
    )
    assert calls == 2
    assert first_client_id == second_client_id
    adapter.close()


from hazewave.provider_fabric import (
    ProviderRoute,
    build_cross_provider_routes,
    load_provider_learning,
    record_provider_result,
)


def test_provider_route_learning_key_binds_task_family_complexity_and_budget(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-learning.json"
    base = ProviderRoute(
        provider="nvidia",
        model_id=MODEL,
        execution_profile=DEEP_MEDIUM,
        capability_id="reason.deep",
        cost_class="FREE_DEVELOPMENT_ENDPOINT",
        task_family="architecture.review",
        complexity=MODERATE,
        reasoning_budget=512,
    )
    harder = ProviderRoute(
        provider="nvidia",
        model_id=MODEL,
        execution_profile=DEEP_HARD,
        capability_id="reason.deep",
        cost_class="FREE_DEVELOPMENT_ENDPOINT",
        task_family="architecture.review",
        complexity=HARD,
        reasoning_budget=1024,
    )
    assert base.route_key != harder.route_key

    for route, quality in ((base, 0.8), (harder, 0.95)):
        record_provider_result(
            path=path,
            route=route,
            result=HazewaveProviderExecutionResult(
                provider=route.provider,
                model_id=route.model_id,
                execution_profile=route.execution_profile,
                capability_id=route.capability_id,
                status="PASS",
                content="ok",
                finish_reason="stop",
                prompt_tokens=10,
                completion_tokens=10,
                reasoning_tokens=route.reasoning_budget,
                total_tokens=20 + route.reasoning_budget,
                latency_ms=100,
                tool_calls=(),
                error_class=None,
                http_status=200,
                retry_after_seconds=None,
                cost_class=route.cost_class,
                semantic_pass=True,
                quality_score=quality,
            ),
            fallback_used=False,
            now="2026-10-05T16:00:00+00:00",
        )
    state = load_provider_learning(path)
    assert base.route_key in state["routes"]
    assert harder.route_key in state["routes"]


def test_cross_provider_builder_uses_complexity_not_capability_name() -> None:
    from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task

    authorization = issue_authorization(
        route_task(
            HazewaveTask(
                task_id="v2-route",
                goal="classify failures",
                required_capability="reason.deep",
                requested_domain=HAZE,
            )
        )
    )
    receipt = {
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
        "admitted_models": [MODEL],
        "profiles": [
            "FAST_STRUCTURED",
            "FAST_CODE",
            "DEEP_MEDIUM",
            "DEEP_HARD",
        ],
        "observed_at": "2026-10-05T12:00:00+00:00",
        "expires_at": "2026-10-12T12:00:00+00:00",
        "source_evidence": ["https://build.nvidia.com/"],
    }
    routes = build_cross_provider_routes(
        authorization=authorization,
        ninerouter_models=["oc/big-pickle"],
        nvidia_receipt=receipt,
        now="2026-10-05T16:00:00+00:00",
        task_family="provider.failure.classification",
        complexity=MODERATE,
        structured_output=True,
    )
    nvidia_route = next(route for route in routes if route.provider == "nvidia")
    assert nvidia_route.execution_profile == FAST_STRUCTURED
    assert nvidia_route.complexity == MODERATE
    assert nvidia_route.reasoning_budget == 0


from hazewave.nvidia_proof import load_probe_corpus, probe_request_options, resolve_probe_profile


def test_v2_corpus_has_multiple_items_per_capability_and_explicit_complexity() -> None:
    root = Path(__file__).resolve().parents[1]
    corpus = load_probe_corpus(root / "config" / "nvidia-capability-eval-v2.json")
    assert corpus["schema"] == "HazewaveNvidiaCapabilityEvalCorpus/v2"
    grouped = {}
    for item in corpus["items"]:
        grouped.setdefault(item["capability"], []).append(item)
        assert item["complexity"] in {
            "TRIVIAL", "SIMPLE", "MODERATE", "HARD", "VERY_HARD"
        }
        assert item["evaluation"]["kind"] != "EXACT_LITERAL_ONLY"
    for capability in (
        "reason.general", "reason.deep", "code.generate", "code.review"
    ):
        assert len(grouped[capability]) >= 5


def test_probe_profile_and_budget_are_derived_from_complexity() -> None:
    item = {
        "capability": "reason.deep",
        "task_family": "architecture.distributed-state",
        "complexity": "HARD",
        "structured_output": True,
        "evaluation": {"kind": "JSON_SUBSET", "expected": {"safe": True}},
    }
    assert resolve_probe_profile(item) == DEEP_HARD
    options = probe_request_options(item)
    assert options["reasoning_budget"] == 1024
    assert options["sampling_policy"] == "DETERMINISTIC_STRUCTURED"
    assert options["seed"] == 20261005
    assert options["response_format"] == {"type": "json_object"}


def test_simple_structured_reason_deep_probe_uses_no_thinking() -> None:
    item = {
        "capability": "reason.deep",
        "task_family": "provider.failure.classification",
        "complexity": "SIMPLE",
        "structured_output": True,
        "evaluation": {"kind": "JSON_SUBSET", "expected": {"safe": True}},
    }
    assert resolve_probe_profile(item) == FAST_STRUCTURED
    assert probe_request_options(item)["reasoning_budget"] == 0


def test_admission_config_keeps_super_and_ultra_as_canaries_not_admitted() -> None:
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads(
        (root / "config" / "nvidia-provider-admission-v1.json").read_text()
    )
    assert set(receipt["profiles"]) >= {
        "FAST_STRUCTURED", "FAST_CODE", "DEEP_MEDIUM", "DEEP_HARD"
    }
    lifecycle = receipt["model_lifecycle"]
    assert lifecycle[MODEL]["stage"] == "ADMITTED"
    for model in (
        "nvidia/nemotron-3-super-120b-a12b",
        "nvidia/nemotron-3-ultra-550b-a55b",
    ):
        assert lifecycle[model]["stage"] == "COST_STATUS_VERIFIED"
        assert model not in receipt["admitted_models"]
        assert lifecycle[model]["free_endpoint_available"] is True


from hazewave.nvidia import evaluate_nvidia_admission, probe_hosted_guided_json
from hazewave.nvidia_optimization import acquire_nvidia_capacity, release_nvidia_capacity


def _optimization_authorization():
    from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id="v2-admission",
                goal="test admission",
                required_capability="reason.general",
                requested_domain=HAZE,
            )
        )
    )


def _v2_admission_receipt() -> dict:
    root = Path(__file__).resolve().parents[1]
    return json.loads(
        (root / "config" / "nvidia-provider-admission-v1.json").read_text()
    )


def test_admission_fails_closed_when_lifecycle_is_not_admitted() -> None:
    receipt = _v2_admission_receipt()
    receipt["model_lifecycle"][MODEL]["stage"] = "COST_STATUS_VERIFIED"
    decision = evaluate_nvidia_admission(
        authorization=_optimization_authorization(),
        model_id=MODEL,
        execution_profile=FAST_STRUCTURED,
        receipt=receipt,
        data_classification="PUBLIC",
        now="2026-10-05T16:00:00+00:00",
    )
    assert decision.allowed is False
    assert decision.reason == "NVIDIA_MODEL_NOT_ADMITTED"


def test_capacity_lease_enforces_current_aimd_limit(tmp_path: Path) -> None:
    path = tmp_path / "nvidia-opt.json"
    lease = acquire_nvidia_capacity(
        path=path,
        model_id=MODEL,
        now="2026-10-05T16:00:00+00:00",
        lease_ttl_seconds=60,
    )
    with pytest.raises(RuntimeError, match="NVIDIA_CAPACITY_BUSY"):
        acquire_nvidia_capacity(
            path=path,
            model_id=MODEL,
            now="2026-10-05T16:00:01+00:00",
            lease_ttl_seconds=60,
        )
    release_nvidia_capacity(path=path, lease_id=lease)


def test_guided_json_canary_requires_schema_valid_200(tmp_path: Path) -> None:
    secret = tmp_path / "nvidia.env"
    secret.write_text("NVIDIA_API_KEY=nvapi-unit-test\n", encoding="utf-8")
    secret.chmod(0o600)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"ok":true}'},
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    result = probe_hosted_guided_json(
        secret_path=secret,
        model_id=MODEL,
        transport=httpx.MockTransport(handler),
    )
    assert result.status == "SUPPORTED"
    assert seen["body"]["guided_json"]["required"] == ["ok"]
    assert "response_format" not in seen["body"]


def test_guided_json_canary_treats_422_as_unsupported(tmp_path: Path) -> None:
    secret = tmp_path / "nvidia.env"
    secret.write_text("NVIDIA_API_KEY=nvapi-unit-test\n", encoding="utf-8")
    secret.chmod(0o600)

    result = probe_hosted_guided_json(
        secret_path=secret,
        model_id=MODEL,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(422, json={"detail": "unsupported"})
        ),
    )
    assert result.status == "UNSUPPORTED"
    assert result.http_status == 422


def test_adapter_enforces_capacity_lease_before_provider_call(tmp_path: Path) -> None:
    secret = tmp_path / "nvidia.env"
    secret.write_text("NVIDIA_API_KEY=nvapi-unit-test\n", encoding="utf-8")
    secret.chmod(0o600)
    state_path = tmp_path / "optimization.json"
    held = acquire_nvidia_capacity(
        path=state_path,
        model_id=MODEL,
        now="2026-10-05T16:00:00+00:00",
        lease_ttl_seconds=60,
    )
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    adapter = NvidiaNIMAdapter(
        secret_path=secret,
        receipt=_v2_admission_receipt(),
        transport=httpx.MockTransport(handler),
        optimization_state_path=state_path,
    )
    result = adapter.execute(
        authorization=_optimization_authorization(),
        model_id=MODEL,
        execution_profile=FAST_STRUCTURED,
        messages=[{"role": "user", "content": "classify"}],
        now="2026-10-05T16:00:01+00:00",
    )
    assert calls == 0
    assert result.status == "FAIL"
    assert result.error_class == "PROVIDER_CAPACITY_BUSY"
    release_nvidia_capacity(path=state_path, lease_id=held)
    adapter.close()


def test_adapter_429_updates_aimd_state_and_releases_lease(tmp_path: Path) -> None:
    secret = tmp_path / "nvidia.env"
    secret.write_text("NVIDIA_API_KEY=nvapi-unit-test\n", encoding="utf-8")
    secret.chmod(0o600)
    state_path = tmp_path / "optimization.json"

    adapter = NvidiaNIMAdapter(
        secret_path=secret,
        receipt=_v2_admission_receipt(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                429,
                headers={"Retry-After": "45"},
                json={"error": {"message": "limited"}},
            )
        ),
        optimization_state_path=state_path,
    )
    result = adapter.execute(
        authorization=_optimization_authorization(),
        model_id=MODEL,
        execution_profile=FAST_STRUCTURED,
        messages=[{"role": "user", "content": "classify"}],
        now="2026-10-05T16:00:00+00:00",
    )
    state = load_nvidia_optimization_state(state_path)
    assert result.error_class == "RATE_LIMITED"
    assert state["concurrency"]["cooldown_kind"] == "RATE_LIMITED"
    assert state["concurrency"]["active_leases"] == {}
    adapter.close()
