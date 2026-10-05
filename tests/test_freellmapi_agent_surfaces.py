from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import httpx
import pytest

from hazewave.cli import build_parser
from hazewave.freellmapi import FreeLLMAPIClient, FreeLLMAPIError, FreeLLMAPILocalCatalog
from hazewave.harness import HazewaveTask, issue_authorization, route_task


def _db(path: Path) -> None:
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
        INSERT INTO api_keys VALUES(1,'github',1,'healthy');
        INSERT INTO models(
          id,platform,model_id,display_name,intelligence_rank,speed_rank,
          context_window,enabled,supports_vision,supports_tools,key_id
        ) VALUES(1,'github','gpt-free','GitHub Free',1,1,128000,1,1,1,NULL);
        """
    )
    con.commit()
    con.close()


def _auth(task_id: str, capability: str = "reason.general", domain: str = "HAZE"):
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id=task_id,
                goal="governed compatibility proof",
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


def test_governed_gemini_native_surface_pins_provider_qualified_model(tmp_path: Path) -> None:
    db = tmp_path / "freellmapi.db"
    _db(db)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1beta/models/github:gpt-free:generateContent"
        payload = json.loads(request.content)
        assert payload["contents"][0]["parts"][0]["text"] == "public task"
        return httpx.Response(
            200,
            headers={"X-Routed-Via": "github/gpt-free"},
            json={
                "candidates": [
                    {"content": {"role": "model", "parts": [{"text": "gemini-compatible answer"}]}}
                ],
                "usageMetadata": {"promptTokenCount": 2, "candidatesTokenCount": 2, "totalTokenCount": 4},
                "modelVersion": "gpt-free",
            },
        )

    with _client(handler) as client:
        result = client.governed_gemini_generate_content(
            contents=[{"role": "user", "parts": [{"text": "public task"}]}],
            authorization=_auth("gemini-1"),
            task_id="gemini-1",
            capability_id="reason.general",
            data_classification="PUBLIC",
            catalog=FreeLLMAPILocalCatalog(db),
        )

    assert result.receipt["provider"] == "github"
    assert result.receipt["requested_model"] == "github:gpt-free"
    assert result.receipt["zero_cost_verified"] is True


def test_governed_ollama_surface_pins_provider_qualified_model(tmp_path: Path) -> None:
    db = tmp_path / "freellmapi.db"
    _db(db)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["model"] == "github:gpt-free"
        assert payload["stream"] is False
        return httpx.Response(
            200,
            headers={"X-Routed-Via": "github/gpt-free"},
            json={
                "model": "github:gpt-free",
                "message": {"role": "assistant", "content": "ollama-compatible answer"},
                "done": True,
            },
        )

    with _client(handler) as client:
        result = client.governed_ollama_chat(
            messages=[{"role": "user", "content": "public task"}],
            authorization=_auth("ollama-1"),
            task_id="ollama-1",
            capability_id="reason.general",
            data_classification="PUBLIC",
            catalog=FreeLLMAPILocalCatalog(db),
        )

    assert result.receipt["provider"] == "github"
    assert result.receipt["requested_model"] == "github:gpt-free"
    assert result.receipt["zero_cost_verified"] is True


def test_mcp_surface_allows_only_read_only_observability_tools() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        assert request.url.path == "/mcp"
        payload = json.loads(request.content)
        assert payload["method"] == "tools/call"
        assert payload["params"]["name"] == "healthcheck"
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"status": "ready"})}]
                },
            },
        )

    with _client(handler) as client:
        result = client.mcp_readonly("healthcheck")
        assert result["result"]["content"][0]["type"] == "text"

        with pytest.raises(FreeLLMAPIError, match="FREELLMAPI_MCP_TOOL_NOT_ALLOWED"):
            client.mcp_readonly("set_routing_strategy", {"strategy": "smartest"})

        with pytest.raises(FreeLLMAPIError, match="FREELLMAPI_MCP_TOOL_NOT_ALLOWED"):
            client.mcp_readonly("ask_freellmapi", {"prompt": "bypass"})

    assert seen == ["/mcp"]


@pytest.mark.parametrize(
    "subcommand",
    ["inventory", "eligible", "health", "quota", "probe", "probe-all"],
)
def test_cli_exposes_governed_free_fabric_operational_commands(subcommand: str) -> None:
    args = build_parser().parse_args(["freellmapi", subcommand])
    assert args.command == "freellmapi"
    assert args.freellmapi_command == subcommand


def test_adr_0005_is_superseded_by_governed_fabric_decision() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = json.loads(
        (root / "docs" / "DOCUMENTATION_REGISTRY_V2.json").read_text(encoding="utf-8")
    )
    entries = {entry["id"]: entry for entry in registry["documents"]}

    assert entries["adr-0005-freellmapi-provider-gateway"]["status"] == "SUPERSEDED"
    assert entries["adr-0006-governed-zero-cost-provider-fabric"]["status"] == "ACTIVE"
