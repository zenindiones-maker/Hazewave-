from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.ninerouter import (
    NineRouterExecutionError,
    evaluate_9router_admission,
    execute_9router_messages,
    rank_9router_models,
)
from hazewave.ninerouter_capacity import (
    TaskContextProfile,
    acquire_capacity_lease,
    build_task_context_profile,
    cache_lookup,
    cache_store,
    classify_outcome,
    load_max_capacity_state,
    quality_aware_model_score,
    record_capacity_outcome,
    release_capacity_lease,
    safe_request_parameters,
    verify_zero_cost_catalog,
)


def _authorization(capability: str = "code.review"):
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id="max-capacity-001",
                goal="Review a Wave Python change",
                required_capability=capability,
                requested_domain=HAZE,
            )
        )
    )


def _profile(**overrides) -> TaskContextProfile:
    values = {
        "capability_id": "code.review",
        "task_family": "wave.python.review",
        "context_size_bucket": "MEDIUM",
        "tool_use_requirement": True,
        "reasoning_requirement": "DEEP",
        "estimated_context_tokens": 12000,
    }
    values.update(overrides)
    return TaskContextProfile(**values)


def _v3_receipt() -> dict:
    models = ["oc/fast-wrong-free", "oc/slower-correct-free"]
    proof = {
        "status": "semantic_pass",
        "latency_ms": 1000,
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        "response_sha256": "proof",
        "benchmark_samples": [
            {"status": "semantic_pass"},
            {"status": "semantic_pass"},
            {"status": "semantic_pass"},
        ],
        "metrics": {
            "sample_count": 3,
            "semantic_success_count": 3,
            "semantic_success_rate": 1.0,
            "median_latency_ms": 1000,
            "median_total_tokens": 120,
        },
    }
    return {
        "schema": "Hazewave9RouterFreeAdmissionReceipt/v3",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "gateway": "9router",
        "gateway_authority": "NONE",
        "upstream_repository": "decolua/9router",
        "upstream_commit": "a99cf57239ff778b61e434c2786009d5ed1c412c",
        "endpoint": "http://127.0.0.1:20128",
        "provider": "opencode",
        "provider_alias": "oc",
        "provider_policy": {
            "has_free": True,
            "no_auth": True,
            "paid_fallback": "FORBIDDEN",
            "unknown_cost": "DENY",
            "denylist": [],
        },
        "catalog_source": "https://opencode.ai/zen/v1/models",
        "catalog_discovered_models": models,
        "execution_admitted_models": models,
        "model_proofs": {model: dict(proof) for model in models},
        "model_lifecycle": {
            model: {
                "stage": "ADMITTED",
                "zero_cost_verified": True,
                "capacity_class": "FREE_UNMETERED_OR_DYNAMIC",
                "compatibility": {
                    "hazewave_chat_execution_compatible": True,
                    "tool_support": True,
                    "reasoning_effort_values": [],
                    "temperature_supported": False,
                    "max_output_tokens": 4096,
                },
            }
            for model in models
        },
        "optimization_policy": {
            "stream": False,
            "rtk_enabled": True,
            "headroom_enabled": False,
            "combos_allowed": False,
            "selection": "QUALITY_AWARE_CONTEXTUAL",
        },
        "observed_at": "2026-10-05T15:00:00+00:00",
    }


def _safe_settings() -> dict:
    return {
        "requireApiKey": False,
        "cloudEnabled": False,
        "tunnelEnabled": False,
        "tailscaleEnabled": False,
        "capacityAdapter": {"vision": {"enabled": False, "models": []}},
        "outboundProxyEnabled": False,
        "rtkEnabled": True,
        "headroomEnabled": False,
    }


def test_context_profile_segments_all_required_dimensions() -> None:
    profile = build_task_context_profile(
        capability_id="code.review",
        messages=[
            {"role": "user", "content": "A" * 34000},
            {"role": "tool", "tool_call_id": "c1", "content": "B" * 4000},
        ],
        tools=[{"type": "function", "function": {"name": "read_file"}}],
        task_family="wave.python.review",
        reasoning_requirement="deep",
    )
    assert profile.capability_id == "code.review"
    assert profile.task_family == "wave.python.review"
    assert profile.context_size_bucket == "MEDIUM"
    assert profile.tool_use_requirement is True
    assert profile.reasoning_requirement == "DEEP"
    assert profile.segment_key == "code.review|wave.python.review|MEDIUM|TOOLS|DEEP"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("EMPTY", "MODEL_QUALITY_COOLDOWN"),
        ("HTTP_429", "PROVIDER_RATE_LIMIT_COOLDOWN"),
        ("HTTP_403", "PROVIDER_AUTH_ELIGIBILITY_FAILURE"),
        ("HTTP_500", "PROVIDER_SERVER_FAILURE"),
        ("HTTP_503", "PROVIDER_SERVER_FAILURE"),
        ("TIMEOUT", "PROVIDER_SERVER_FAILURE"),
        ("PASS", "HEALTHY"),
    ],
)
def test_failure_classes_are_causal(status: str, expected: str) -> None:
    assert classify_outcome(status) == expected


def test_segment_metrics_are_durable_and_separate(tmp_path: Path) -> None:
    path = tmp_path / "capacity.json"
    profile = _profile()
    record_capacity_outcome(
        path=path, provider="opencode", model_id="oc/big-pickle", profile=profile,
        status="EMPTY", input_tokens=100, output_tokens=0, reasoning_tokens=0,
        latency_ms=1500, fallback_used=False, now="2026-10-05T15:00:00+00:00",
    )
    record_capacity_outcome(
        path=path, provider="opencode", model_id="oc/big-pickle", profile=profile,
        status="HTTP_429", latency_ms=700, fallback_used=True, retry_after_seconds=90,
        now="2026-10-05T15:01:00+00:00",
    )
    record_capacity_outcome(
        path=path, provider="opencode", model_id="oc/big-pickle", profile=profile,
        status="PASS", semantic_pass=True, quality_score=0.92,
        input_tokens=120, output_tokens=35, reasoning_tokens=9, latency_ms=1000,
        fallback_used=False, now="2026-10-05T15:03:00+00:00",
    )
    row = load_max_capacity_state(path)["models"]["oc/big-pickle"]["segments"][profile.segment_key]
    assert row["attempt_count"] == 3
    assert row["pass_count"] == 1
    assert row["semantic_pass_count"] == 1
    assert row["empty_count"] == 1
    assert row["429_count"] == 1
    assert row["403_count"] == 0
    assert row["5xx_count"] == 0
    assert row["timeout_count"] == 0
    assert row["fallback_count"] == 1
    assert row["input_tokens"] == 220
    assert row["output_tokens"] == 35
    assert row["reasoning_tokens"] == 9
    assert row["quality_score"] == pytest.approx(0.92)
    assert path.stat().st_mode & 0o777 == 0o600


def test_aimd_grows_then_halves_on_429(tmp_path: Path) -> None:
    path = tmp_path / "capacity.json"
    profile = _profile(tool_use_requirement=False)
    for second in range(4):
        record_capacity_outcome(
            path=path, provider="opencode", model_id="oc/big-pickle", profile=profile,
            status="PASS", semantic_pass=True, quality_score=1.0,
            input_tokens=100, output_tokens=10, reasoning_tokens=0, latency_ms=1000,
            fallback_used=False, now=f"2026-10-05T15:00:0{second}+00:00",
        )
    state = load_max_capacity_state(path)
    before_p = state["providers"]["opencode"]["concurrency"]["limit"]
    before_m = state["models"]["oc/big-pickle"]["concurrency"]["limit"]
    assert before_p >= 2 and before_m >= 2
    record_capacity_outcome(
        path=path, provider="opencode", model_id="oc/big-pickle", profile=profile,
        status="HTTP_429", retry_after_seconds=30, latency_ms=2000,
        fallback_used=False, now="2026-10-05T15:01:00+00:00",
    )
    state = load_max_capacity_state(path)
    assert state["providers"]["opencode"]["concurrency"]["limit"] == max(1, before_p // 2)
    assert state["models"]["oc/big-pickle"]["concurrency"]["limit"] == max(1, before_m // 2)
    assert state["models"]["oc/big-pickle"]["circuit"]["kind"] == "PROVIDER_RATE_LIMIT_COOLDOWN"


def test_quality_score_values_correctness_over_raw_latency() -> None:
    profile = _profile(tool_use_requirement=False)
    def seg(semantic: int, quality: float, latency: int, fallback: int) -> dict:
        return {
            "attempt_count": 20, "pass_count": 20 if semantic < 10 else 19,
            "semantic_evaluation_count": 20, "semantic_pass_count": semantic,
            "fallback_count": fallback, "input_tokens": 2200, "output_tokens": 450,
            "reasoning_tokens": 0, "latency_ms": latency, "quality_score": quality,
        }
    state = {
        "models": {
            "oc/fast": {"segments": {profile.segment_key: seg(8, 0.4, 350, 0)}},
            "oc/good": {"segments": {profile.segment_key: seg(19, 0.95, 1100, 1)}},
        }
    }
    assert quality_aware_model_score(state, "oc/good", profile) > quality_aware_model_score(state, "oc/fast", profile)


def test_cache_binds_context_policy_dependency_and_forbids_tools(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    profile = _profile(tool_use_requirement=False)
    key = cache_store(
        path=path, semantic_hash="s1", profile=profile, context_revision="c1",
        policy_revision="p1", dependency_revision="d1",
        payload={"content": "cached"}, now="2026-10-05T15:00:00+00:00",
    )
    hit = cache_lookup(
        path=path, semantic_hash="s1", profile=profile, context_revision="c1",
        policy_revision="p1", dependency_revision="d1",
        now="2026-10-05T15:01:00+00:00",
    )
    assert hit and hit["key"] == key
    miss = cache_lookup(
        path=path, semantic_hash="s1", profile=profile, context_revision="c2",
        policy_revision="p1", dependency_revision="d1",
        now="2026-10-05T15:02:00+00:00",
    )
    assert miss is None
    metrics = json.loads(path.read_text())["metrics"]
    assert metrics["CACHE_HIT"] == 1 and metrics["CACHE_INVALIDATED"] >= 1
    with pytest.raises(ValueError, match="CACHE_TOOL_USE_FORBIDDEN"):
        cache_store(
            path=path, semantic_hash="x", profile=_profile(tool_use_requirement=True),
            context_revision="c", policy_revision="p", dependency_revision="d",
            payload={"content": "unsafe"},
        )


def test_zero_cost_catalog_does_not_trust_free_suffix() -> None:
    lifecycle = verify_zero_cost_catalog(
        ["big-pickle", "muse-spark-1.2-contributor-free", "muse-spark-1.3-contributor-free"],
        {
            "big-pickle": {"capacity_class": "FREE_UNMETERED_OR_DYNAMIC"},
            "muse-spark-1.3-contributor-free": {"capacity_class": "FREE_UNMETERED_OR_DYNAMIC"},
        },
    )
    assert lifecycle["big-pickle"]["stage"] == "ZERO_COST_VERIFIED"
    assert lifecycle["muse-spark-1.3-contributor-free"]["stage"] == "ZERO_COST_VERIFIED"
    assert lifecycle["muse-spark-1.2-contributor-free"]["stage"] == "DISCOVERED"


def test_safe_parameters_strip_unproved_reasoning_and_temperature() -> None:
    payload = safe_request_parameters(
        model_id="oc/muse-spark-1.3-contributor-free",
        messages=[{"role": "user", "content": "review"}],
        profile=_profile(tool_use_requirement=True),
        compatibility={
            "hazewave_chat_execution_compatible": True, "tool_support": True,
            "reasoning_effort_values": [], "temperature_supported": False,
            "max_output_tokens": 2048,
        },
        requested_max_tokens=4096,
        tools=[{"type": "function", "function": {"name": "read_file"}}],
        requested_reasoning_effort="xhigh",
        requested_temperature=0.2,
    )
    assert payload["max_tokens"] == 2048
    assert "reasoning_effort" not in payload and "temperature" not in payload


def test_capacity_lease_respects_limits(tmp_path: Path) -> None:
    path = tmp_path / "capacity.json"
    profile = _profile(tool_use_requirement=False)
    first = acquire_capacity_lease(
        path=path, provider="opencode", model_id="oc/big-pickle", profile=profile,
        now="2026-10-05T15:00:00+00:00", lease_ttl_seconds=60, wait_timeout_seconds=0,
    )
    with pytest.raises(RuntimeError, match="NINEROUTER_CAPACITY_BUSY"):
        acquire_capacity_lease(
            path=path, provider="opencode", model_id="oc/big-pickle", profile=profile,
            now="2026-10-05T15:00:01+00:00", lease_ttl_seconds=60, wait_timeout_seconds=0,
        )
    release_capacity_lease(path=path, provider="opencode", model_id="oc/big-pickle", lease_id=first)
    assert acquire_capacity_lease(
        path=path, provider="opencode", model_id="oc/big-pickle", profile=profile,
        now="2026-10-05T15:00:02+00:00", lease_ttl_seconds=60, wait_timeout_seconds=0,
    ) != first


def test_v3_admission_requires_verified_free_lifecycle() -> None:
    receipt = _v3_receipt()
    model = "oc/fast-wrong-free"
    assert evaluate_9router_admission(
        authorization=_authorization(), model_id=model, receipt=receipt,
        now="2026-10-05T15:30:00+00:00",
    ).allowed is True
    receipt["model_lifecycle"][model]["capacity_class"] = "UNKNOWN"
    denied = evaluate_9router_admission(
        authorization=_authorization(), model_id=model, receipt=receipt,
        now="2026-10-05T15:30:00+00:00",
    )
    assert denied.allowed is False
    assert denied.reason == "NINEROUTER_ZERO_COST_VERIFICATION_MISSING"


def test_contextual_ranker_prefers_segment_quality() -> None:
    receipt = _v3_receipt()
    profile = _profile(tool_use_requirement=False)
    state = {
        "schema": "Hazewave9RouterMaxCapacityState/v1",
        "project_id": "HAZEWAVE", "authority": "HAZEWAVE_HARNESS", "providers": {},
        "models": {
            "oc/fast-wrong-free": {"segments": {profile.segment_key: {
                "attempt_count": 10, "pass_count": 10, "semantic_evaluation_count": 10,
                "semantic_pass_count": 3, "fallback_count": 0, "input_tokens": 1000,
                "output_tokens": 100, "reasoning_tokens": 0, "latency_ms": 300,
                "quality_score": 0.3,
            }}, "circuit": {"state": "CLOSED"}},
            "oc/slower-correct-free": {"segments": {profile.segment_key: {
                "attempt_count": 10, "pass_count": 9, "semantic_evaluation_count": 10,
                "semantic_pass_count": 9, "fallback_count": 1, "input_tokens": 1200,
                "output_tokens": 120, "reasoning_tokens": 0, "latency_ms": 1100,
                "quality_score": 0.95,
            }}, "circuit": {"state": "CLOSED"}},
        },
        "cache": {},
    }
    assert rank_9router_models(
        authorization=_authorization(), receipt=receipt, now="2026-10-05T15:30:00+00:00",
        context_profile=profile, capacity_state=state,
    ) == ["oc/slower-correct-free", "oc/fast-wrong-free"]


def test_prepared_runtime_no_settings_patch_and_records_segment(tmp_path: Path) -> None:
    methods: list[tuple[str, str]] = []
    bodies: list[dict] = []
    def handler(request: httpx.Request) -> httpx.Response:
        methods.append((request.method, request.url.path))
        if request.url.path == "/api/settings":
            assert request.method == "GET"
            return httpx.Response(200, json=_safe_settings())
        body = json.loads(request.content); bodies.append(body)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "review ok"}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 20, "total_tokens": 140,
                      "completion_tokens_details": {"reasoning_tokens": 7}},
        })
    state_path = tmp_path / "capacity.json"
    result = execute_9router_messages(
        authorization=_authorization(), model_id="auto",
        messages=[{"role": "user", "content": "Review this Wave change"}],
        receipt=_v3_receipt(), now="2026-10-05T15:30:00+00:00",
        lock_path=tmp_path/"settings.lock", route_health_path=tmp_path/"route-health.json",
        transport=httpx.MockTransport(handler), cli_token="unit-test-token",
        prepared_runtime=True, capacity_state_path=state_path,
        task_family="wave.python.review", reasoning_requirement="deep",
    )
    assert result.status == "PASS" and result.content == "review ok"
    assert all(method != "PATCH" for method, _ in methods)
    row = next(iter(load_max_capacity_state(state_path)["models"][result.model_id]["segments"].values()))
    assert (row["attempt_count"], row["pass_count"], row["input_tokens"], row["output_tokens"], row["reasoning_tokens"]) == (1,1,120,20,7)


def test_prepared_runtime_fails_closed_on_unsafe_settings(tmp_path: Path) -> None:
    settings = _safe_settings(); settings["headroomEnabled"] = True
    calls = 0
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if request.url.path == "/api/settings":
            return httpx.Response(200, json=settings)
        calls += 1
        return httpx.Response(200, json={})
    with pytest.raises(NineRouterExecutionError, match="NINEROUTER_PREPARED_SETTINGS_UNSAFE"):
        execute_9router_messages(
            authorization=_authorization(), model_id="auto", messages=[{"role":"user","content":"review"}],
            receipt=_v3_receipt(), now="2026-10-05T15:30:00+00:00",
            lock_path=tmp_path/"lock", route_health_path=tmp_path/"rh.json",
            transport=httpx.MockTransport(handler), cli_token="unit-test-token",
            prepared_runtime=True, capacity_state_path=tmp_path/"capacity.json",
            task_family="wave.python.review",
        )
    assert calls == 0


def test_prepared_runtime_applies_compatibility_contract(tmp_path: Path) -> None:
    receipt = _v3_receipt()
    for row in receipt["model_lifecycle"].values():
        row["compatibility"].update({
            "reasoning_effort_values": [], "temperature_supported": False,
            "max_output_tokens": 256,
        })
    bodies = []
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/settings":
            return httpx.Response(200, json=_safe_settings())
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={
            "choices":[{"message":{"content":"ok"}}],
            "usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12},
        })
    execute_9router_messages(
        authorization=_authorization("reason.deep"), model_id="auto",
        messages=[{"role":"user","content":"reason carefully"}], receipt=receipt,
        now="2026-10-05T15:30:00+00:00", max_tokens=1024,
        lock_path=tmp_path/"lock", route_health_path=tmp_path/"rh.json",
        transport=httpx.MockTransport(handler), cli_token="unit-test-token",
        prepared_runtime=True, capacity_state_path=tmp_path/"capacity.json",
        task_family="haze.reasoning", reasoning_requirement="deep",
        requested_reasoning_effort="xhigh", requested_temperature=0.2,
    )
    assert bodies[0]["max_tokens"] == 256
    assert "reasoning_effort" not in bodies[0] and "temperature" not in bodies[0]


def test_prepared_runtime_403_stops_fallback_storm_and_opens_provider_circuit(tmp_path: Path) -> None:
    calls = []
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/settings":
            return httpx.Response(200, json=_safe_settings())
        calls.append(json.loads(request.content)["model"])
        return httpx.Response(403, json={"error":{"message":"free unavailable"}})
    state_path = tmp_path/"capacity.json"
    with pytest.raises(NineRouterExecutionError, match="NINEROUTER_COMPLETION_HTTP_403"):
        execute_9router_messages(
            authorization=_authorization(), model_id="auto",
            messages=[{"role":"user","content":"review"}], receipt=_v3_receipt(),
            now="2026-10-05T15:30:00+00:00", max_fallbacks=2,
            lock_path=tmp_path/"lock", route_health_path=tmp_path/"rh.json",
            transport=httpx.MockTransport(handler), cli_token="unit-test-token",
            prepared_runtime=True, capacity_state_path=state_path,
            task_family="wave.python.review",
        )
    assert len(calls) == 1
    assert load_max_capacity_state(state_path)["providers"]["opencode"]["circuit"]["kind"] == "PROVIDER_AUTH_ELIGIBILITY_FAILURE"


def test_prepared_runtime_timeout_classified_and_lease_released(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/settings":
            return httpx.Response(200, json=_safe_settings())
        raise httpx.ReadTimeout("slow", request=request)
    state_path = tmp_path/"capacity.json"
    with pytest.raises(NineRouterExecutionError, match="NINEROUTER_COMPLETION_TIMEOUT"):
        execute_9router_messages(
            authorization=_authorization(), model_id="oc/fast-wrong-free",
            messages=[{"role":"user","content":"review"}], receipt=_v3_receipt(),
            now="2026-10-05T15:30:00+00:00", lock_path=tmp_path/"lock",
            route_health_path=tmp_path/"rh.json", transport=httpx.MockTransport(handler),
            cli_token="unit-test-token", prepared_runtime=True,
            capacity_state_path=state_path, task_family="wave.python.review",
        )
    model = load_max_capacity_state(state_path)["models"]["oc/fast-wrong-free"]
    assert model["circuit"]["kind"] == "PROVIDER_SERVER_FAILURE"
    assert model["concurrency"]["active_leases"] == {}


from hazewave.ninerouter_capacity import (
    compute_rtk_ab_metrics,
    summarize_capacity_benchmark,
)


def test_rtk_ab_metrics_require_same_task_model_and_real_provider_accounting() -> None:
    off = {
        "task_id": "eval-1", "model_id": "oc/big-pickle", "rtk_enabled": False,
        "input_tokens": 1000, "output_tokens": 100, "latency_ms": 2000,
        "semantic_pass": True, "quality_score": 0.95,
    }
    on = {
        "task_id": "eval-1", "model_id": "oc/big-pickle", "rtk_enabled": True,
        "input_tokens": 700, "output_tokens": 100, "latency_ms": 1800,
        "semantic_pass": True, "quality_score": 0.95,
    }
    metrics = compute_rtk_ab_metrics(off, on)
    assert metrics["RTK_REAL_TOKEN_REDUCTION"] == pytest.approx(0.30)
    assert metrics["RTK_QUALITY_DELTA"] == pytest.approx(0.0)
    assert metrics["RTK_LATENCY_DELTA"] == pytest.approx(-200.0)

    bad = dict(on); bad["model_id"] = "oc/other-free"
    with pytest.raises(ValueError, match="RTK_AB_MODEL_MISMATCH"):
        compute_rtk_ab_metrics(off, bad)


def test_capacity_summary_reports_sustainable_operating_metrics() -> None:
    rows = [
        {"status":"PASS","semantic_pass":True,"latency_ms":1000,"total_tokens":100,
         "fallback_count":0,"http_status":200,"cache_hit":False},
        {"status":"PASS","semantic_pass":True,"latency_ms":2000,"total_tokens":150,
         "fallback_count":1,"http_status":200,"cache_hit":False},
        {"status":"HTTP_429","semantic_pass":False,"latency_ms":3000,"total_tokens":0,
         "fallback_count":0,"http_status":429,"cache_hit":False},
        {"status":"CACHE_HIT","semantic_pass":True,"latency_ms":5,"total_tokens":0,
         "fallback_count":0,"http_status":None,"cache_hit":True},
    ]
    summary = summarize_capacity_benchmark(rows, elapsed_seconds=60.0, concurrency=3)
    assert summary["SUSTAINABLE_CONCURRENCY"] == 3
    assert summary["USEFUL_TASKS_PER_MINUTE"] == pytest.approx(3.0)
    assert summary["SUCCESS_RATE"] == pytest.approx(0.75)
    assert summary["SEMANTIC_SUCCESS_RATE"] == pytest.approx(0.75)
    assert summary["P50_LATENCY"] == pytest.approx(1500.0)
    assert summary["P95_LATENCY"] >= 2000
    assert summary["TOKENS_PER_SUCCESSFUL_TASK"] == pytest.approx(250/3)
    assert summary["FALLBACK_AMPLIFICATION"] == pytest.approx(1/3)
    assert summary["429_RATE"] == pytest.approx(0.25)
    assert summary["CACHE_HIT_RATE"] == pytest.approx(0.25)


def test_representative_eval_corpus_is_not_transport_smoke_only() -> None:
    root = Path(__file__).resolve().parents[1]
    corpus = json.loads((root/"config"/"9router-representative-eval-v1.json").read_text())
    assert corpus["schema"] == "Hazewave9RouterRepresentativeEvalCorpus/v1"
    by_capability = {}
    for item in corpus["items"]:
        by_capability.setdefault(item["capability"], []).append(item)
        assert item["evaluation"]["kind"] != "EXACT_LITERAL_ONLY"
        assert item["task_family"]
        assert item["prompt"]
    for capability in ("reason.general","reason.deep","code.generate","code.review"):
        assert len(by_capability[capability]) >= 2


def test_zero_cost_registry_separates_verified_pricing_from_catalog_discovery() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = json.loads((root/"config"/"opencode-zero-cost-registry-v1.json").read_text())
    assert registry["schema"] == "HazewaveOpenCodeZeroCostRegistry/v1"
    assert registry["paid"] == "DENY"
    assert registry["unknown"] == "DENY"
    assert registry["source"]["pricing_url"] == "https://opencode.ai/docs/zen/"
    assert registry["source"]["catalog_url"] == "https://opencode.ai/zen/v1/models"
    assert all(row["capacity_class"] in ("FREE_UNMETERED_OR_DYNAMIC","FREE_QUOTA")
               for row in registry["verified_free"].values())
    assert "muse-spark-1.2-contributor-free" not in registry["verified_free"]
