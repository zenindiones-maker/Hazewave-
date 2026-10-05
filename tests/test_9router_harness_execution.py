from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.ninerouter import (
    NineRouterExecutionError,
    execute_9router_text,
)


def _authorization():
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id="exec-9router-001",
                goal="Answer through governed free route",
                required_capability="reason.general",
                requested_domain=HAZE,
            )
        )
    )


def _receipt() -> dict:
    model = "oc/mimo-v2.6-flash-free"
    return {
        "schema": "Hazewave9RouterFreeAdmissionReceipt/v1",
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
        "catalog_discovered_models": [model],
        "execution_admitted_models": [model],
        "probe": {
            "model": model,
            "max_tokens": 128,
            "max_attempts": 3,
            "attempts": [{"model": model, "status": "semantic_pass"}],
            "semantic_expected": "HAZEWAVE_OK",
            "response_sha256": "response-proof",
            "status": "PASS",
        },
        "observed_at": "2026-10-05T11:45:00+00:00",
    }


def _transport(*, exposed: bool = False, completion: str = "answer"):
    settings = {
        "requireApiKey": True,
        "cloudEnabled": exposed,
        "tunnelEnabled": False,
        "tailscaleEnabled": False,
        "capacityAdapter": {},
        "outboundProxyEnabled": False,
    }
    patches: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/settings" and request.method == "GET":
            return httpx.Response(200, json=settings)

        if request.url.path == "/api/settings" and request.method == "PATCH":
            body = json.loads(request.content)
            patches.append(body)
            settings.update(body)
            return httpx.Response(200, json=settings)

        if request.url.path == "/v1/chat/completions":
            assert settings["requireApiKey"] is False
            body = json.loads(request.content)
            assert body["model"] == "oc/mimo-v2.6-flash-free"
            assert body["stream"] is False
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": completion},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
                },
            )

        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    return httpx.MockTransport(handler), settings, patches


def test_executor_requires_harness_admission_before_http(tmp_path: Path) -> None:
    transport, _, patches = _transport()

    with pytest.raises(NineRouterExecutionError, match="MODEL_NOT_EXECUTION_ADMITTED"):
        execute_9router_text(
            authorization=_authorization(),
            model_id="oc/space-bunny-free",
            prompt="hello",
            receipt=_receipt(),
            now="2026-10-05T12:00:00+00:00",
            lock_path=tmp_path / "lock",
            transport=transport,
        cli_token="unit-test-token",
            cli_token="unit-test-token",
        )

    assert patches == []


def test_executor_refuses_any_external_exposure(tmp_path: Path) -> None:
    transport, settings, patches = _transport(exposed=True)

    with pytest.raises(NineRouterExecutionError, match="NINEROUTER_EXTERNAL_EXPOSURE_ENABLED"):
        execute_9router_text(
            authorization=_authorization(),
            model_id="oc/mimo-v2.6-flash-free",
            prompt="hello",
            receipt=_receipt(),
            now="2026-10-05T12:00:00+00:00",
            lock_path=tmp_path / "lock",
            transport=transport,
        cli_token="unit-test-token",
            cli_token="unit-test-token",
        )

    assert settings["requireApiKey"] is True
    assert patches == []


def test_executor_temporarily_opens_loopback_api_and_restores_setting(tmp_path: Path) -> None:
    transport, settings, patches = _transport(completion="Hazewave answer")

    result = execute_9router_text(
        authorization=_authorization(),
        model_id="oc/mimo-v2.6-flash-free",
        prompt="hello",
        receipt=_receipt(),
        now="2026-10-05T12:00:00+00:00",
        lock_path=tmp_path / "lock",
        transport=transport,
        cli_token="unit-test-token",
    )

    assert result.status == "PASS"
    assert result.model_id == "oc/mimo-v2.6-flash-free"
    assert result.content == "Hazewave answer"
    assert result.zero_cost_verified is True
    assert result.gateway == "9router"
    assert result.provider == "opencode"
    assert settings["requireApiKey"] is True
    assert patches[0]["requireApiKey"] is False
    assert patches[-1]["requireApiKey"] is True


def test_executor_restores_setting_when_completion_fails(tmp_path: Path) -> None:
    settings = {
        "requireApiKey": True,
        "cloudEnabled": False,
        "tunnelEnabled": False,
        "tailscaleEnabled": False,
        "capacityAdapter": {},
        "outboundProxyEnabled": False,
    }
    patches: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/settings" and request.method == "GET":
            return httpx.Response(200, json=settings)
        if request.url.path == "/api/settings" and request.method == "PATCH":
            body = json.loads(request.content)
            patches.append(body)
            settings.update(body)
            return httpx.Response(200, json=settings)
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(503, json={"error": {"message": "upstream unavailable"}})
        raise AssertionError("unexpected request")

    with pytest.raises(NineRouterExecutionError, match="NINEROUTER_COMPLETION_HTTP_503"):
        execute_9router_text(
            authorization=_authorization(),
            model_id="oc/mimo-v2.6-flash-free",
            prompt="hello",
            receipt=_receipt(),
            now="2026-10-05T12:00:00+00:00",
            lock_path=tmp_path / "lock",
            transport=httpx.MockTransport(handler),
            cli_token="unit-test-token",
        )

    assert settings["requireApiKey"] is True
    assert patches[-1]["requireApiKey"] is True


def test_executor_rejects_empty_prompt_before_mutation(tmp_path: Path) -> None:
    transport, _, patches = _transport()

    with pytest.raises(ValueError, match="NINEROUTER_PROMPT_REQUIRED"):
        execute_9router_text(
            authorization=_authorization(),
            model_id="oc/mimo-v2.6-flash-free",
            prompt="   ",
            receipt=_receipt(),
            now="2026-10-05T12:00:00+00:00",
            lock_path=tmp_path / "lock",
            transport=transport,
        cli_token="unit-test-token",
            cli_token="unit-test-token",
        )

    assert patches == []
