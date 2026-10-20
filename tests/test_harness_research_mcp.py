from pathlib import Path

from hazewave.harness_research_mcp import FixtureMcpGateway, serve_request

ROOT = Path(__file__).resolve().parents[1]


def gateway(*, rea=True, iris=True):
    calls = []
    def executor(**kwargs):
        calls.append(kwargs)
        return {
            "kind": kwargs["kind"],
            "state": "OBSERVATION_ONLY",
            "capability_plane_measured_ready": False,
            "production_approved": False,
            "agent_mcp_session_connected": False,
            "receipt_sha256": "a" * 64,
            "measurements": {"module_node_count": 3},
        }
    mcp = FixtureMcpGateway(
        workspace=ROOT, expected_sha="a" * 40,
        state_root=Path("/tmp/owner-fixtures-private"),
        rea_binary=Path("/path/to/rea") if rea else None,
        iris_binary=Path("/path/to/iris") if iris else None,
        chrome_binary=Path("/path/to/chromium") if iris else None,
        executor=executor,
    )
    return mcp, calls


def test_mcp_initialize_advertises_tools_without_production_authority():
    m, calls = gateway()
    out = serve_request(m, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                            "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                                       "clientInfo": {"name": "owner-fixture-client", "version": "1"}}})
    assert out["result"]["protocolVersion"] == "2025-11-25"
    assert out["result"]["serverInfo"]["name"] == "hazewave-research-fixtures"
    assert out["result"]["capabilities"]["tools"] == {"listChanged": False}
    assert not calls


def test_mcp_lists_only_locally_configured_fixed_fixture_tools():
    m, _ = gateway(iris=False)
    out = serve_request(m, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    assert [t["name"] for t in out["result"]["tools"]] == ["harness_rea_owned_js"]
    assert out["result"]["tools"][0]["inputSchema"]["additionalProperties"] is False


def test_mcp_tool_call_reaches_only_scoped_executor_and_returns_observation():
    m, calls = gateway()
    r = serve_request(m, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                          "params": {"name": "harness_iris_owned_page",
                                     "arguments": {"task_id": "owner-fixture-789"}}})
    assert r["result"]["isError"] is False
    assert calls[0]["kind"] == "iris_owned_page"
    assert calls[0]["task_id"] == "owner-fixture-789"
    assert calls[0]["expected_sha"] == "a" * 40
    assert "OBSERVATION_ONLY" in r["result"]["content"][0]["text"]
    assert "production_approved" in r["result"]["content"][0]["text"]


def test_mcp_rejects_any_user_target_override():
    m, calls = gateway()
    for arg in (
        {"task_id": "owner-fixture-789", "url": "https://example.com"},
        {"task_id": "owner-fixture-789", "path": "/etc/shadow"},
        {"task_id": "owner-fixture-789", "provider_id": "hopper"},
        {"task_id": "owner-fixture-789", "execute": "rm -rf /"},
    ):
        r = serve_request(m, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                              "params": {"name": "harness_rea_owned_js", "arguments": arg}})
        assert r["result"]["isError"] is True
    assert calls == []


def test_mcp_refuses_arbitrary_tool_and_disabled_binary():
    m, calls = gateway(iris=False)
    for name in ("harness_iris_owned_page", "rea_decompile_everything"):
        out = serve_request(m, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                "params": {"name": name, "arguments": {"task_id": "owner-fixture-789"}}})
        assert out["result"]["isError"] is True
    assert calls == []


def test_mcp_request_budget_prevents_unbounded_agent_loop():
    m, calls = gateway()
    for i in range(2):
        out = serve_request(m, {"jsonrpc": "2.0", "id": i+3, "method": "tools/call",
                                "params": {"name": "harness_rea_owned_js",
                                           "arguments": {"task_id": f"fixture-owned-{i+1:04d}"}}})
        assert out["result"]["isError"] is False
    out = serve_request(m, {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                            "params": {"name": "harness_rea_owned_js",
                                       "arguments": {"task_id": "fixture-owned-0003"}}})
    assert out["result"]["isError"] is True
    assert len(calls) == 2


def test_mcp_does_not_accept_bad_rpc_or_unsupported_method():
    m, _ = gateway()
    for request in ({"jsonrpc": "1.0", "id": 1, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 1, "method": "shutdown"},
                    {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"cursor": "x"}}):
        out = serve_request(m, request)
        assert "error" in out or out.get("result", {}).get("isError") is True
