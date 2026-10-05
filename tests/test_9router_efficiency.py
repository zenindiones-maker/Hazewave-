from __future__ import annotations

import json
from pathlib import Path

import httpx

from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.ninerouter import (
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
                "latency_ms": 900,
                "usage": {"prompt_tokens": 220, "completion_tokens": 30, "total_tokens": 250},
                "response_sha256": "fast-proof",
            },
            cheap: {
                "status": "semantic_pass",
                "latency_ms": 1100,
                "usage": {"prompt_tokens": 210, "completion_tokens": 20, "total_tokens": 230},
                "response_sha256": "cheap-proof",
            },
            slower: {
                "status": "semantic_pass",
                "latency_ms": 1800,
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


def test_ranker_prefers_lowest_tokens_then_latency() -> None:
    ranked = rank_9router_models(
        authorization=_authorization(),
        receipt=_v2_receipt(),
        data_classification="PUBLIC",
        now="2026-10-05T12:30:00+00:00",
    )

    assert ranked == [
        "oc/mimo-v2.6-flash-free",
        "oc/nemotron-3.5-lightning-free",
        "oc/space-bunny-free",
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


def test_deep_reasoning_prefers_observed_reasoning_before_token_score() -> None:
    receipt = _v2_receipt()
    receipt["model_proofs"]["oc/nemotron-3.5-lightning-free"]["reasoning_observed"] = True

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
