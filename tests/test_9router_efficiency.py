from __future__ import annotations

import json
from pathlib import Path

import httpx

from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.ninerouter import (
    build_9router_efficiency_status,
    execute_9router_text,
    load_9router_route_health,
    rank_9router_models,
)


def _authorization(capability: str = "reason.general"):
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id="efficiency-001",
                goal="Use the most efficient proven free model",
                required_capability=capability,
                requested_domain=HAZE,
            )
        )
    )


def _v2_receipt() -> dict:
    fast = "oc/space-bunny-free"
    cheap = "oc/mimo-v2.6-flash-free"
    slower = "oc/nemotron-3.5-lightning-free"
    return {
        "schema": "Hazewave9RouterFreeAdmissionReceipt/v2",
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
            "catalog_rule": "id.endswith(-free) OR id==big-pickle",
            "denylist": ["deepseek-v4-flash-free"],
        },
        "catalog_source": "https://opencode.ai/zen/v1/models",
        "catalog_sha256": "catalog-proof",
        "catalog_discovered_models": [fast, cheap, slower],
        "execution_admitted_models": [fast, cheap, slower],
        "model_proofs": {
            fast: {
                "status": "semantic_pass",
                "latency_ms": 1500,
                "usage": {"prompt_tokens": 220, "completion_tokens": 30, "total_tokens": 250},
                "response_sha256": "fast-proof",
            },
            cheap: {
                "status": "semantic_pass",
                "latency_ms": 900,
                "usage": {"prompt_tokens": 210, "completion_tokens": 20, "total_tokens": 230},
                "response_sha256": "cheap-proof",
            },
            slower: {
                "status": "semantic_pass",
                "latency_ms": 1100,
                "usage": {"prompt_tokens": 220, "completion_tokens": 20, "total_tokens": 240},
                "response_sha256": "slow-proof",
            },
        },
        "optimization_policy": {
            "stream": False,
            "rtk_enabled": True,
            "headroom_enabled": False,
            "combos_allowed": False,
            "selection": "LOWEST_TOTAL_TOKENS_THEN_LATENCY",
        },
        "probe": {
            "model": cheap,
            "max_tokens": 128,
            "max_attempts": 13,
            "attempts": [{"model": cheap, "status": "semantic_pass"}],
            "semantic_expected": "HAZEWAVE_OK",
            "response_sha256": "cheap-proof",
            "status": "PASS",
        },
        "observed_at": "2026-10-05T12:00:00+00:00",
    }


def test_ranker_balances_tokens_and_latency_instead_of_token_only() -> None:
    receipt = _v2_receipt()
    receipt["model_proofs"] = {
        "oc/longcat-2.5-preview-free": {
            "status": "semantic_pass",
            "latency_ms": 20730,
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 39,
                "total_tokens": 59,
            },
            "response_sha256": "longcat-proof",
        },
        "oc/space-bunny-free": {
            "status": "semantic_pass",
            "latency_ms": 1793,
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 151,
                "total_tokens": 171,
            },
            "response_sha256": "space-proof",
        },
        "oc/big-pickle": {
            "status": "semantic_pass",
            "latency_ms": 1299,
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 163,
                "total_tokens": 183,
            },
            "response_sha256": "pickle-proof",
        },
    }
    receipt["catalog_discovered_models"] = list(receipt["model_proofs"])
    receipt["execution_admitted_models"] = list(receipt["model_proofs"])

    ranked = rank_9router_models(
        authorization=_authorization(),
        receipt=receipt,
        data_classification="PUBLIC",
        now="2026-10-05T12:30:00+00:00",
    )

    assert ranked == [
        "oc/big-pickle",
        "oc/space-bunny-free",
        "oc/longcat-2.5-preview-free",
    ]


def test_ranker_keeps_v1_receipts_compatible() -> None:
    receipt = _v2_receipt()
    receipt["schema"] = "Hazewave9RouterFreeAdmissionReceipt/v1"
    receipt["execution_admitted_models"] = ["oc/mimo-v2.6-flash-free"]
    receipt.pop("model_proofs")
    receipt.pop("optimization_policy")

    ranked = rank_9router_models(
        authorization=_authorization(),
        receipt=receipt,
        data_classification="PUBLIC",
        now="2026-10-05T12:30:00+00:00",
    )

    assert ranked == ["oc/mimo-v2.6-flash-free"]


def test_auto_executor_falls_back_only_inside_admitted_free_pool(tmp_path: Path) -> None:
    settings = {
        "requireApiKey": True,
        "cloudEnabled": False,
        "tunnelEnabled": False,
        "tailscaleEnabled": False,
        "capacityAdapter": {
            "vision": {"enabled": True, "models": []},
        },
        "outboundProxyEnabled": False,
        "rtkEnabled": False,
        "headroomEnabled": True,
    }
    patches: list[dict] = []
    attempted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/settings" and request.method == "GET":
            return httpx.Response(200, json=settings)
        if request.url.path == "/api/settings" and request.method == "PATCH":
            body = json.loads(request.content)
            patches.append(body)
            settings.update(body)
            return httpx.Response(200, json=settings)
        if request.url.path == "/v1/chat/completions":
            body = json.loads(request.content)
            model = body["model"]
            attempted.append(model)
            assert body["stream"] is False
            if model == "oc/mimo-v2.6-flash-free":
                return httpx.Response(503, json={"error": {"message": "temporary"}})
            if model == "oc/nemotron-3.5-lightning-free":
                return httpx.Response(
                    200,
                    json={
                        "choices": [{"message": {"content": "fallback answer"}}],
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 3,
                            "total_tokens": 13,
                        },
                    },
                )
            raise AssertionError(f"unexpected model {model}")

    result = execute_9router_text(
        authorization=_authorization(),
        model_id="auto",
        prompt="hello",
        receipt=_v2_receipt(),
        now="2026-10-05T12:30:00+00:00",
        lock_path=tmp_path / "lock",
        transport=httpx.MockTransport(handler),
        cli_token="unit-test-token",
        max_fallbacks=3,
    )

    assert result.model_id == "oc/nemotron-3.5-lightning-free"
    assert result.content == "fallback answer"
    assert result.selection_mode == "auto"
    assert result.fallback_count == 1
    assert result.attempted_models == (
        "oc/mimo-v2.6-flash-free",
        "oc/nemotron-3.5-lightning-free",
    )
    assert result.rtk_enabled is True
    assert result.stream is False
    assert attempted == [
        "oc/mimo-v2.6-flash-free",
        "oc/nemotron-3.5-lightning-free",
    ]

    opening = patches[0]
    assert opening["requireApiKey"] is False
    assert opening["rtkEnabled"] is True
    assert opening["headroomEnabled"] is False
    assert opening["outboundProxyEnabled"] is False
    assert opening["capacityAdapter"]["vision"]["enabled"] is False

    closing = patches[-1]
    assert closing["requireApiKey"] is True
    assert closing["rtkEnabled"] is False
    assert closing["headroomEnabled"] is True


def test_optimizer_script_benchmarks_entire_free_catalog() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "hazewave_9router_free_probe.sh").read_text(
        encoding="utf-8"
    )
    control = (root / "scripts" / "hazewave_9router_control.sh").read_text(
        encoding="utf-8"
    )

    assert "catalog|probe|optimize" in script
    assert '"Hazewave9RouterFreeAdmissionReceipt/v2"' in script
    assert "model_proofs" in script
    assert "latency_ms" in script
    assert "total_tokens" in script
    assert "rtkEnabled: true" in script
    assert "headroomEnabled: false" in script
    assert "combos_allowed: false" in script
    assert "for (let index = 0; index < candidates.length; index += 1)" in script
    assert "optimize)" in control


def test_deep_reasoning_prefers_observed_reasoning_before_efficiency_score() -> None:
    receipt = _v2_receipt()
    receipt["model_proofs"]["oc/nemotron-3.5-lightning-free"]["usage"][
        "reasoning_tokens"
    ] = 16

    ranked = rank_9router_models(
        authorization=_authorization("reason.deep"),
        receipt=receipt,
        data_classification="PUBLIC",
        now="2026-10-05T12:30:00+00:00",
    )

    assert ranked[0] == "oc/nemotron-3.5-lightning-free"


def test_efficiency_policy_locks_safe_maximum_surface() -> None:
    root = Path(__file__).resolve().parents[1]
    policy = json.loads(
        (root / "config" / "9router-efficiency-policy-v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert policy["schema"] == "Hazewave9RouterEfficiencyPolicy/v1"
    assert policy["authority"] == "HAZEWAVE_HARNESS"
    assert policy["gateway_authority"] == "NONE"
    assert policy["security"]["minimum_fixed_version"] == "0.5.8"
    assert policy["optimizer"]["receipt_ttl_hours"] == 24
    assert policy["optimizer"]["benchmark_max_models"] == 16
    assert policy["optimizer"]["execution_max_fallbacks"] == 3
    assert policy["optimizer"]["benchmark_sample_count"] == 3
    assert (
        policy["optimizer"]["general_and_code_selection"]
        == "BALANCED_TOKEN_LATENCY_PRODUCT"
    )
    assert (
        policy["optimizer"]["deep_reasoning_selection"]
        == "REASONING_EVIDENCE_THEN_BALANCED_TOKEN_LATENCY_PRODUCT"
    )
    assert policy["optimizer"]["transient_cooldown"]["base_seconds"] == 60
    assert policy["optimizer"]["transient_cooldown"]["max_seconds"] == 900
    assert policy["optimizer"]["transient_cooldown"]["strategy"] == "EXPONENTIAL"
    assert policy["token_efficiency"]["rtk"] == "FORCE_ON_DURING_GOVERNED_EXECUTION"
    assert policy["token_efficiency"]["headroom"] == "OFF_UNTIL_MANAGED_LOCAL_PROOF"
    assert policy["routing"]["combos"] == "FORBIDDEN"
    assert policy["routing"]["capacity_adapters"] == "FORBIDDEN"
    assert policy["routing"]["paid_tiers"] == "FORBIDDEN"
    assert policy["routing"]["unknown_cost"] == "DENY"


def test_ranker_skips_model_in_active_transient_cooldown() -> None:
    health = {
        "schema": "Hazewave9RouterRouteHealth/v1",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "models": {
            "oc/mimo-v2.6-flash-free": {
                "consecutive_transient_failures": 2,
                "cooldown_until": "2026-10-05T12:40:00+00:00",
                "last_status": "HTTP_429",
            }
        },
    }

    ranked = rank_9router_models(
        authorization=_authorization(),
        receipt=_v2_receipt(),
        route_health=health,
        data_classification="PUBLIC",
        now="2026-10-05T12:30:00+00:00",
    )

    assert ranked == [
        "oc/nemotron-3.5-lightning-free",
        "oc/space-bunny-free",
    ]


def test_auto_executor_records_transient_cooldown_and_success_reset(
    tmp_path: Path,
) -> None:
    receipt = _v2_receipt()
    settings = {
        "requireApiKey": True,
        "cloudEnabled": False,
        "tunnelEnabled": False,
        "tailscaleEnabled": False,
        "capacityAdapter": {},
        "outboundProxyEnabled": False,
        "rtkEnabled": True,
        "headroomEnabled": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/settings" and request.method == "GET":
            return httpx.Response(200, json=settings)
        if request.url.path == "/api/settings" and request.method == "PATCH":
            settings.update(json.loads(request.content))
            return httpx.Response(200, json=settings)
        if request.url.path == "/v1/chat/completions":
            body = json.loads(request.content)
            if body["model"] == "oc/mimo-v2.6-flash-free":
                return httpx.Response(429, json={"error": {"message": "rate limited"}})
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "healthy fallback"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
                },
            )
        raise AssertionError("unexpected request")

    health_path = tmp_path / "route-health.json"
    result = execute_9router_text(
        authorization=_authorization(),
        model_id="auto",
        prompt="hello",
        receipt=receipt,
        now="2026-10-05T12:30:00+00:00",
        lock_path=tmp_path / "lock",
        route_health_path=health_path,
        transport=httpx.MockTransport(handler),
        cli_token="unit-test-token",
    )

    assert result.model_id == "oc/nemotron-3.5-lightning-free"

    health = load_9router_route_health(health_path)
    failed = health["models"]["oc/mimo-v2.6-flash-free"]
    healthy = health["models"]["oc/nemotron-3.5-lightning-free"]

    assert failed["consecutive_transient_failures"] == 1
    assert failed["cooldown_until"] == "2026-10-05T12:31:00+00:00"
    assert failed["last_status"] == "HTTP_429"
    assert healthy["consecutive_transient_failures"] == 0
    assert healthy["cooldown_until"] is None
    assert healthy["last_status"] == "PASS"
    assert health_path.stat().st_mode & 0o777 == 0o600


def test_efficiency_status_exposes_active_model_cooldowns() -> None:
    receipt = _v2_receipt()
    health = {
        "schema": "Hazewave9RouterRouteHealth/v1",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "models": {
            "oc/mimo-v2.6-flash-free": {
                "consecutive_transient_failures": 1,
                "cooldown_until": "2026-10-05T12:31:00+00:00",
                "last_status": "HTTP_429",
                "updated_at": "2026-10-05T12:30:00+00:00",
            }
        },
    }

    status = build_9router_efficiency_status(
        receipt=receipt,
        route_health=health,
        now="2026-10-05T12:30:30+00:00",
    )

    assert status["cooling_model_count"] == 1
    assert status["cooling_models"] == [
        {
            "model": "oc/mimo-v2.6-flash-free",
            "cooldown_until": "2026-10-05T12:31:00+00:00",
            "last_status": "HTTP_429",
            "consecutive_transient_failures": 1,
        }
    ]


def test_ranker_prefers_live_ewma_metrics_over_stale_benchmark() -> None:
    receipt = _v2_receipt()
    health = {
        "schema": "Hazewave9RouterRouteHealth/v1",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "models": {
            "oc/space-bunny-free": {
                "consecutive_transient_failures": 0,
                "cooldown_until": None,
                "last_status": "PASS",
                "success_count": 4,
                "ewma_latency_ms": 500,
                "ewma_total_tokens": 100,
            }
        },
    }

    ranked = rank_9router_models(
        authorization=_authorization(),
        receipt=receipt,
        route_health=health,
        data_classification="PUBLIC",
        now="2026-10-05T12:30:00+00:00",
    )

    assert ranked[0] == "oc/space-bunny-free"


def test_execution_records_reasoning_tokens_and_live_efficiency_ewma(
    tmp_path: Path,
) -> None:
    receipt = _v2_receipt()
    settings = {
        "requireApiKey": True,
        "cloudEnabled": False,
        "tunnelEnabled": False,
        "tailscaleEnabled": False,
        "capacityAdapter": {},
        "outboundProxyEnabled": False,
        "rtkEnabled": True,
        "headroomEnabled": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/settings" and request.method == "GET":
            return httpx.Response(200, json=settings)
        if request.url.path == "/api/settings" and request.method == "PATCH":
            settings.update(json.loads(request.content))
            return httpx.Response(200, json=settings)
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": "runtime answer"}}
                    ],
                    "usage": {
                        "prompt_tokens": 20,
                        "completion_tokens": 40,
                        "total_tokens": 60,
                        "completion_tokens_details": {
                            "reasoning_tokens": 30
                        },
                    },
                },
            )
        raise AssertionError("unexpected request")

    health_path = tmp_path / "route-health.json"
    result = execute_9router_text(
        authorization=_authorization(),
        model_id="oc/mimo-v2.6-flash-free",
        prompt="hello",
        receipt=receipt,
        now="2026-10-05T12:30:00+00:00",
        lock_path=tmp_path / "lock",
        route_health_path=health_path,
        transport=httpx.MockTransport(handler),
        cli_token="unit-test-token",
    )

    assert result.reasoning_tokens == 30

    health = load_9router_route_health(health_path)
    row = health["models"]["oc/mimo-v2.6-flash-free"]
    assert row["success_count"] == 1
    assert row["ewma_total_tokens"] == 60
    assert isinstance(row["ewma_latency_ms"], int)
    assert row["ewma_latency_ms"] >= 0
    assert row["last_reasoning_tokens"] == 30


def test_optimizer_uses_repeated_samples_medians_and_reasoning_usage() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "hazewave_9router_free_probe.sh").read_text(
        encoding="utf-8"
    )

    assert "OPTIMIZE_SAMPLE_COUNT = 3" in script
    assert "benchmark_samples" in script
    assert "median_latency_ms" in script
    assert "median_total_tokens" in script
    assert "semantic_success_rate" in script
    assert "efficiency_score" in script
    assert "reasoning_tokens" in script
    assert "BALANCED_TOKEN_LATENCY_PRODUCT" in script


def test_optimizer_requires_two_of_three_semantic_successes_for_admission() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "hazewave_9router_free_probe.sh").read_text(
        encoding="utf-8"
    )

    assert "MIN_SEMANTIC_SUCCESSES = 2" in script
    assert "semanticSuccessCount >= MIN_SEMANTIC_SUCCESSES" in script
    assert "insufficient_semantic_success" in script


def test_optimizer_stops_hammering_nonrecoverable_or_rate_limited_models() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "hazewave_9router_free_probe.sh").read_text(
        encoding="utf-8"
    )

    assert "NON_RETRYABLE_SAMPLE_STATUSES" in script
    assert '"http_400"' in script
    assert '"http_401"' in script
    assert '"http_403"' in script
    assert '"http_429"' in script
    assert "break;" in script


def test_ranker_penalizes_live_failure_reliability_after_cooldown_expires() -> None:
    receipt = _v2_receipt()
    receipt["model_proofs"]["oc/mimo-v2.6-flash-free"]["latency_ms"] = 800
    receipt["model_proofs"]["oc/mimo-v2.6-flash-free"]["usage"]["total_tokens"] = 100
    receipt["model_proofs"]["oc/space-bunny-free"]["latency_ms"] = 1000
    receipt["model_proofs"]["oc/space-bunny-free"]["usage"]["total_tokens"] = 120

    health = {
        "schema": "Hazewave9RouterRouteHealth/v1",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "models": {
            "oc/mimo-v2.6-flash-free": {
                "attempt_count": 1,
                "success_count": 0,
                "failure_count": 1,
                "consecutive_transient_failures": 1,
                "cooldown_until": "2026-10-05T12:29:00+00:00",
                "last_status": "HTTP_503",
            },
            "oc/space-bunny-free": {
                "attempt_count": 1,
                "success_count": 1,
                "failure_count": 0,
                "consecutive_transient_failures": 0,
                "cooldown_until": None,
                "last_status": "PASS",
                "ewma_latency_ms": 1000,
                "ewma_total_tokens": 120,
            },
        },
    }

    ranked = rank_9router_models(
        authorization=_authorization(),
        receipt=receipt,
        route_health=health,
        data_classification="PUBLIC",
        now="2026-10-05T12:30:00+00:00",
    )

    assert ranked[0] == "oc/space-bunny-free"


def test_auto_executor_emits_attempt_trace_with_fallback_reason(tmp_path: Path) -> None:
    settings = {
        "requireApiKey": True,
        "cloudEnabled": False,
        "tunnelEnabled": False,
        "tailscaleEnabled": False,
        "capacityAdapter": {},
        "outboundProxyEnabled": False,
        "rtkEnabled": True,
        "headroomEnabled": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/settings" and request.method == "GET":
            return httpx.Response(200, json=settings)
        if request.url.path == "/api/settings" and request.method == "PATCH":
            settings.update(json.loads(request.content))
            return httpx.Response(200, json=settings)
        if request.url.path == "/v1/chat/completions":
            model = json.loads(request.content)["model"]
            if model == "oc/mimo-v2.6-flash-free":
                return httpx.Response(503, json={"error": {"message": "temporary"}})
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                    },
                },
            )
        raise AssertionError("unexpected request")

    receipt = _v2_receipt()
    receipt["model_proofs"]["oc/mimo-v2.6-flash-free"]["latency_ms"] = 800
    receipt["model_proofs"]["oc/mimo-v2.6-flash-free"]["usage"]["total_tokens"] = 100
    receipt["model_proofs"]["oc/nemotron-3.5-lightning-free"]["latency_ms"] = 900
    receipt["model_proofs"]["oc/nemotron-3.5-lightning-free"]["usage"]["total_tokens"] = 110
    receipt["model_proofs"]["oc/space-bunny-free"]["latency_ms"] = 5000
    receipt["model_proofs"]["oc/space-bunny-free"]["usage"]["total_tokens"] = 500

    result = execute_9router_text(
        authorization=_authorization(),
        model_id="auto",
        prompt="hello",
        receipt=receipt,
        now="2026-10-05T12:30:00+00:00",
        lock_path=tmp_path / "lock",
        route_health_path=tmp_path / "health.json",
        transport=httpx.MockTransport(handler),
        cli_token="unit-test-token",
        max_fallbacks=3,
    )

    assert result.attempt_trace[0]["model"] == "oc/mimo-v2.6-flash-free"
    assert result.attempt_trace[0]["status"] == "HTTP_503"
    assert result.attempt_trace[1]["model"] == "oc/nemotron-3.5-lightning-free"
    assert result.attempt_trace[1]["status"] == "PASS"
    assert result.attempt_trace[1]["total_tokens"] == 12
