from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import httpx
import pytest

from hazewave.freellmapi import FreeLLMAPIClient, FreeLLMAPILocalCatalog
from hazewave.harness import HazewaveTask, issue_authorization, route_task


def _db(path: Path, *, vision: bool = False, tools: bool = False) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE api_keys (
          id INTEGER PRIMARY KEY,
          platform TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          status TEXT NOT NULL DEFAULT 'unknown'
        );
        CREATE TABLE models (
          id INTEGER PRIMARY KEY,
          platform TEXT NOT NULL,
          model_id TEXT NOT NULL,
          display_name TEXT NOT NULL,
          intelligence_rank INTEGER NOT NULL DEFAULT 999,
          speed_rank INTEGER NOT NULL DEFAULT 999,
          context_window INTEGER,
          enabled INTEGER NOT NULL DEFAULT 1,
          supports_vision INTEGER NOT NULL DEFAULT 0,
          supports_tools INTEGER NOT NULL DEFAULT 0,
          key_id INTEGER
        );
        """
    )
    con.execute("INSERT INTO api_keys VALUES(1,'github',1,'healthy')")
    con.execute(
        """
        INSERT INTO models(
          id,platform,model_id,display_name,intelligence_rank,speed_rank,
          context_window,enabled,supports_vision,supports_tools,key_id
        ) VALUES(1,'github','gpt-free','GitHub Free',1,1,128000,1,?,?,NULL)
        """,
        (1 if vision else 0, 1 if tools else 0),
    )
    con.commit()
    con.close()


def _auth(task_id: str, capability: str, domain: str):
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id=task_id,
                goal="governed compatibility surface test",
                required_capability=capability,
                requested_domain=domain,
            )
        )
    )


def _client(handler) -> FreeLLMAPIClient:
    client = FreeLLMAPIClient("http://127.0.0.1:3001/v1", api_key="router-secret")
    client._client.close()
    client._client = httpx.Client(
        base_url="http://127.0.0.1:3001/v1",
        headers={"Authorization": "Bearer router-secret"},
        transport=httpx.MockTransport(handler),
    )
    return client


def test_governed_vision_hard_pins_vision_capable_provider(tmp_path: Path) -> None:
    db = tmp_path / "freellmapi.db"
    _db(db, vision=True)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "github:gpt-free"
        blocks = payload["messages"][0]["content"]
        assert blocks[0]["type"] == "text"
        assert blocks[1]["type"] == "image_url"
        return httpx.Response(
            200,
            headers={"X-Routed-Via": "github/gpt-free"},
            json={
                "model": "gpt-free",
                "choices": [{"message": {"role": "assistant", "content": "visual observation"}}],
                "usage": {"cost": 0},
            },
        )

    authorization = _auth("vision-1", "visual.analyze", "WAVE")
    with _client(handler) as client:
        result = client.governed_vision(
            prompt="Describe the public reference image.",
            image_url="https://example.invalid/public.png",
            authorization=authorization,
            task_id="vision-1",
            capability_id="visual.analyze",
            data_classification="PUBLIC",
            catalog=FreeLLMAPILocalCatalog(db),
        )

    assert result.content == "visual observation"
    assert result.receipt["provider"] == "github"
    assert result.receipt["zero_cost_verified"] is True


@pytest.mark.parametrize(
    ("method", "endpoint"),
    [
        ("governed_responses", "/v1/responses"),
        ("governed_anthropic_messages", "/v1/messages"),
        ("governed_completion", "/v1/completions"),
    ],
)
def test_governed_compatibility_surfaces_never_use_auto(
    tmp_path: Path, method: str, endpoint: str
) -> None:
    db = tmp_path / "freellmapi.db"
    _db(db)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == endpoint
        payload = json.loads(request.content)
        assert payload["model"] == "github:gpt-free"
        assert payload["model"] != "auto"
        if endpoint == "/v1/responses":
            return httpx.Response(
                200,
                headers={"X-Routed-Via": "github/gpt-free"},
                json={
                    "id": "resp-1",
                    "object": "response",
                    "model": "gpt-free",
                    "output_text": "responses answer",
                    "output": [],
                    "usage": {"input_tokens": 2, "output_tokens": 2, "total_tokens": 4},
                },
            )
        if endpoint == "/v1/messages":
            assert request.headers["anthropic-version"] == "2023-06-01"
            assert request.headers["x-api-key"] == "router-secret"
            return httpx.Response(
                200,
                headers={"X-Routed-Via": "github/gpt-free"},
                json={
                    "id": "msg-1",
                    "type": "message",
                    "role": "assistant",
                    "model": "gpt-free",
                    "content": [{"type": "text", "text": "anthropic answer"}],
                    "usage": {"input_tokens": 2, "output_tokens": 2},
                },
            )
        return httpx.Response(
            200,
            headers={"X-Routed-Via": "github/gpt-free"},
            json={
                "id": "cmpl-1",
                "object": "text_completion",
                "model": "gpt-free",
                "choices": [{"text": "completion answer", "index": 0, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
            },
        )

    authorization = _auth(f"{method}-1", "reason.general", "HAZE")
    kwargs = dict(
        authorization=authorization,
        task_id=f"{method}-1",
        capability_id="reason.general",
        data_classification="PUBLIC",
        catalog=FreeLLMAPILocalCatalog(db),
    )
    if method == "governed_responses":
        kwargs["input_data"] = "public task"
    elif method == "governed_anthropic_messages":
        kwargs["messages"] = [{"role": "user", "content": "public task"}]
        kwargs["max_tokens"] = 64
    else:
        kwargs["prompt"] = "public task"

    with _client(handler) as client:
        result = getattr(client, method)(**kwargs)

    assert result.receipt["provider"] == "github"
    assert result.receipt["zero_cost_verified"] is True
    assert "router-secret" not in json.dumps(result.receipt, sort_keys=True)


def test_governed_chat_efficiency_headers_are_bounded_and_provider_pinned(
    tmp_path: Path,
) -> None:
    db = tmp_path / "freellmapi.db"
    _db(db)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-freellm-cache"] == "on"
        assert request.headers["x-freellm-compress"] == "lossless"
        assert request.headers["x-freellm-task-type"] == "code"
        assert request.headers["x-session-id"] == "hazewave-session-7"
        payload = json.loads(request.content)
        assert payload["model"] == "github:gpt-free"
        return httpx.Response(
            200,
            headers={"X-Routed-Via": "github/gpt-free"},
            json={
                "model": "gpt-free",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"cost": 0},
            },
        )

    authorization = _auth("headers-1", "code.review", "HAZE")
    with _client(handler) as client:
        result = client.governed_chat(
            messages=[{"role": "user", "content": "review public code"}],
            authorization=authorization,
            task_id="headers-1",
            capability_id="code.review",
            data_classification="PUBLIC",
            catalog=FreeLLMAPILocalCatalog(db),
            cache=True,
            compression="lossless",
            task_type="code",
            session_id="hazewave-session-7",
        )

    assert result.receipt["cache_requested"] is True
    assert result.receipt["compression_requested"] == "lossless"


class _SSEStream(httpx.SyncByteStream):
    def __iter__(self):
        yield b'data: {"id":"c1","model":"gpt-free","choices":[{"delta":{"content":"hello "}}]}\n\n'
        yield b'data: {"id":"c1","model":"gpt-free","choices":[{"delta":{"content":"world"},"finish_reason":"stop"}]}\n\n'
        yield b'data: [DONE]\n\n'


def test_governed_stream_chat_yields_deltas_and_final_receipt(tmp_path: Path) -> None:
    db = tmp_path / "freellmapi.db"
    _db(db)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "github:gpt-free"
        assert payload["stream"] is True
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream", "X-Routed-Via": "github/gpt-free"},
            stream=_SSEStream(),
        )

    authorization = _auth("stream-1", "reason.general", "HAZE")
    with _client(handler) as client:
        stream = client.governed_stream_chat(
            messages=[{"role": "user", "content": "stream public reply"}],
            authorization=authorization,
            task_id="stream-1",
            capability_id="reason.general",
            data_classification="PUBLIC",
            catalog=FreeLLMAPILocalCatalog(db),
        )
        chunks = list(stream)

    assert chunks == ["hello ", "world"]
    assert stream.receipt is not None
    assert stream.receipt["output_sha256"]
    assert stream.receipt["provider"] == "github"
    assert stream.receipt["zero_cost_verified"] is True
