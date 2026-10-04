from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from hazewave.freellmapi import (
    DEFAULT_BASE_URL,
    FREELLMAPI_PINNED_REF,
    FREELLMAPI_REPOSITORY,
    FreeLLMAPIClient,
    FreeLLMAPIError,
)
from hazewave.harness import HazewaveTask, issue_authorization, route_task


ROOT = Path(__file__).resolve().parents[1]


def _authorization():
    decision = route_task(
        HazewaveTask(
            task_id="t-provider-1",
            goal="analyze non-secret sonic planning context",
            required_capability="audio.analyze",
            requested_domain="HAZE",
        )
    )
    return issue_authorization(decision)


def _client(handler, *, api_key="freellmapi-test-key") -> FreeLLMAPIClient:
    client = FreeLLMAPIClient(DEFAULT_BASE_URL, api_key=api_key)
    client._client.close()
    client._client = httpx.Client(
        base_url=DEFAULT_BASE_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        transport=httpx.MockTransport(handler),
    )
    return client


def test_upstream_is_exactly_pinned() -> None:
    assert FREELLMAPI_REPOSITORY == "https://github.com/tashfeenahmed/freellmapi.git"
    assert FREELLMAPI_PINNED_REF == "716948f20b12ec1c9b7c6fcebd22a3e7233cda1b"


def test_client_rejects_non_loopback_gateway_by_default() -> None:
    with pytest.raises(FreeLLMAPIError, match="loopback"):
        FreeLLMAPIClient("https://router.example.com/v1", api_key="x")


def test_chat_requires_harness_bound_authorization_and_keeps_router_subordinate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer freellmapi-test-key"
        payload = __import__("json").loads(request.content)
        assert payload["model"] == "auto"
        assert payload["messages"] == [{"role": "user", "content": "analyze this structure"}]
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "model": "provider/model-served",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5},
            },
        )

    with _client(handler) as client:
        result = client.chat(
            messages=[{"role": "user", "content": "analyze this structure"}],
            authorization=_authorization(),
            task_id="t-provider-1",
            capability_id="audio.analyze",
            data_classification="INTERNAL_NON_SECRET",
        )

    assert result.content == "ok"
    assert result.served_model == "provider/model-served"
    assert result.authority == "HAZEWAVE_HARNESS"
    assert result.provider_gateway == "FREELLMAPI"


def test_private_media_and_credentials_are_fail_closed_before_provider_egress() -> None:
    called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    with _client(handler) as client:
        for classification in ("PRIVATE_MEDIA", "CREDENTIAL"):
            with pytest.raises(FreeLLMAPIError, match="DATA_CLASS_NOT_ALLOWED"):
                client.chat(
                    messages=[{"role": "user", "content": "do not send"}],
                    authorization=_authorization(),
                    task_id="t-provider-1",
                    capability_id="audio.analyze",
                    data_classification=classification,
                )

    assert called is False


def test_termux_provider_runtime_is_project_namespaced_pinned_and_loopback_only() -> None:
    installer = (ROOT / "scripts" / "install_hazewave_freellmapi_termux.sh").read_text(
        encoding="utf-8"
    )
    control = (ROOT / "scripts" / "hazewave_freellmapi_control.sh").read_text(
        encoding="utf-8"
    )
    combined = installer + "\n" + control

    assert "716948f20b12ec1c9b7c6fcebd22a3e7233cda1b" in installer
    assert ".local/share/hazewave/providers/freellmapi" in combined
    assert ".local/state/hazewave/providers/freellmapi" in combined
    assert ".config/hazewave/providers/freellmapi" in combined
    assert "HOST=127.0.0.1" in control
    assert "FREELLMAPI_UPDATE_CHECK=off" in control
    assert "BR-no-GTA" not in combined


def test_freellmapi_architecture_and_runbook_are_registered() -> None:
    import json

    registry = json.loads(
        (ROOT / "docs" / "DOCUMENTATION_REGISTRY_V2.json").read_text(encoding="utf-8")
    )
    paths = {entry["path"] for entry in registry["documents"]}
    assert "docs/architecture/decisions/ADR-0005-freellmapi-provider-gateway.md" in paths
    assert "docs/runbooks/FREELLMAPI_PROVIDER_V1.md" in paths
