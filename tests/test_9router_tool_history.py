from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import httpx
import pytest

from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.ninerouter import (
    NineRouterExecutionError,
    execute_9router_messages,
)


def _authorization(capability: str = "code.review"):
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id="tool-history-001",
                goal="Review public tool output efficiently",
                required_capability=capability,
                requested_domain=HAZE,
            )
        )
    )


def _receipt() -> dict:
    model = "oc/mimo-v2.6-flash-free"
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
        "catalog_discovered_models": [model],
        "execution_admitted_models": [model],
        "model_proofs": {
            model: {
                "status": "semantic_pass",
                "latency_ms": 1000,
                "usage": {
                    "prompt_tokens": 200,
                    "completion_tokens": 20,
                    "total_tokens": 220,
                },
                "response_sha256": "proof",
            }
        },
        "optimization_policy": {
            "stream": False,
            "rtk_enabled": True,
            "headroom_enabled": False,
            "combos_allowed": False,
            "selection": "LOWEST_TOTAL_TOKENS_THEN_LATENCY",
        },
        "probe": {
            "model": model,
            "max_tokens": 256,
            "max_attempts": 1,
            "attempts": [{"model": model, "status": "semantic_pass"}],
            "semantic_expected": "HAZEWAVE_OK",
            "response_sha256": "proof",
            "status": "PASS",
        },
        "observed_at": "2026-10-05T12:00:00+00:00",
    }


def _settings_transport(response_payload: dict):
    settings = {
        "requireApiKey": True,
        "cloudEnabled": False,
        "tunnelEnabled": False,
        "tailscaleEnabled": False,
        "capacityAdapter": {},
        "outboundProxyEnabled": False,
        "rtkEnabled": False,
        "headroomEnabled": False,
    }
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/settings" and request.method == "GET":
            return httpx.Response(200, json=settings)
        if request.url.path == "/api/settings" and request.method == "PATCH":
            body = json.loads(request.content)
            settings.update(body)
            return httpx.Response(200, json=settings)
        if request.url.path == "/v1/chat/completions":
            captured.update(json.loads(request.content))
            return httpx.Response(200, json=response_payload)
        raise AssertionError(f"unexpected {request.method} {request.url}")

    return httpx.MockTransport(handler), captured


def test_messages_executor_preserves_public_tool_history_for_rtk(tmp_path: Path) -> None:
    transport, captured = _settings_transport(
        {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "review complete"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 8, "total_tokens": 108},
        }
    )
    messages = [
        {"role": "system", "content": "Review code."},
        {"role": "user", "content": "Inspect the diff."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "git_diff", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": "diff --git a/a.py b/a.py\n" + ("+print('x')\n" * 300),
        },
    ]

    result = execute_9router_messages(
        authorization=_authorization(),
        model_id="oc/mimo-v2.6-flash-free",
        messages=messages,
        receipt=_receipt(),
        now="2026-10-05T12:30:00+00:00",
        lock_path=tmp_path / "lock",
        transport=transport,
        cli_token="unit-test-token",
    )

    assert result.content == "review complete"
    assert captured["messages"] == messages
    assert captured["stream"] is False


def test_messages_executor_returns_tool_calls_without_requiring_content(tmp_path: Path) -> None:
    tool_calls = [
        {
            "id": "call_2",
            "type": "function",
            "function": {"name": "search_code", "arguments": "{\"q\":\"needle\"}"},
        }
    ]
    transport, _ = _settings_transport(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": tool_calls,
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }
    )

    result = execute_9router_messages(
        authorization=_authorization(),
        model_id="oc/mimo-v2.6-flash-free",
        messages=[{"role": "user", "content": "Find the symbol."}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Search public code",
                    "parameters": {
                        "type": "object",
                        "properties": {"q": {"type": "string"}},
                        "required": ["q"],
                    },
                },
            }
        ],
        receipt=_receipt(),
        now="2026-10-05T12:30:00+00:00",
        lock_path=tmp_path / "lock",
        transport=transport,
        cli_token="unit-test-token",
    )

    assert result.content == ""
    assert result.tool_calls == tuple(tool_calls)


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]}],
        [{"role": "tool", "content": "output"}],
        [{"role": "invalid", "content": "x"}],
    ],
)
def test_messages_executor_rejects_invalid_or_non_text_public_history(
    tmp_path: Path,
    messages: list[dict],
) -> None:
    transport, _ = _settings_transport(
        {"choices": [{"message": {"content": "unused"}}]}
    )

    with pytest.raises(ValueError, match="NINEROUTER_MESSAGES_"):
        execute_9router_messages(
            authorization=_authorization(),
            model_id="oc/mimo-v2.6-flash-free",
            messages=messages,
            receipt=_receipt(),
            now="2026-10-05T12:30:00+00:00",
            lock_path=tmp_path / "lock",
            transport=transport,
            cli_token="unit-test-token",
        )


def test_executor_sends_stable_opaque_session_hint_per_task(tmp_path: Path) -> None:
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
    observed_sessions: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/settings" and request.method == "GET":
            return httpx.Response(200, json=settings)
        if request.url.path == "/api/settings" and request.method == "PATCH":
            settings.update(json.loads(request.content))
            return httpx.Response(200, json=settings)
        if request.url.path == "/v1/chat/completions":
            observed_sessions.append(request.headers["x-session-id"])
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {
                        "prompt_tokens": 5,
                        "completion_tokens": 1,
                        "total_tokens": 6,
                    },
                },
            )
        raise AssertionError("unexpected request")

    authorization = _authorization()
    transport = httpx.MockTransport(handler)
    for index in range(2):
        execute_9router_messages(
            authorization=authorization,
            model_id="oc/mimo-v2.6-flash-free",
            messages=[{"role": "user", "content": f"turn {index}"}],
            receipt=_receipt(),
            now="2026-10-05T12:30:00+00:00",
            lock_path=tmp_path / "lock",
            route_health_path=tmp_path / "health.json",
            transport=transport,
            cli_token="unit-test-token",
        )

    expected = "hz_" + sha256(authorization.task_id.encode("utf-8")).hexdigest()[:32]
    assert observed_sessions == [expected, expected]
    assert authorization.task_id not in observed_sessions[0]
