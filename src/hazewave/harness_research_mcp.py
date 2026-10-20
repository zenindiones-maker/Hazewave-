"""Constrained stdio MCP facade: agents can request ONLY owned REA/Iris fixtures.

This is deliberately NOT the raw upstream Iris MCP server or unrestricted REA.
Tools/list can expose available *fixture probe commands*, not production routes.
Each call is bound to an exact reviewed worktree SHA and Harness authorization,
executes a pinned tool, verifies measurements and writes a private receipt.

No extra arguments, URLs, target paths, provider selection, shell commands,
blind auto-install, agent privilege escalation, or production promotion.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from typing import Any, Callable, Mapping

from hazewave.harness_research_execution import (
    ResearchExecutionError, execute_owned_fixture
)


@dataclass
class FixtureMcpGateway:
    workspace: Path
    expected_sha: str
    state_root: Path
    rea_binary: Path | None = None
    iris_binary: Path | None = None
    chrome_binary: Path | None = None
    executor: Callable[..., dict[str, Any]] = execute_owned_fixture
    completed_calls: int = field(default=0, init=False)
    max_calls: int = 2

    def supported_tools(self) -> list[dict[str, Any]]:
        candidates: list[tuple[str, str]] = []
        if self.rea_binary is not None:
            candidates.append((
                "harness_rea_owned_js",
                "Analyze ONLY reviewed Hazewave-owned JavaScript fixture via REA 6.0.0. "
                "Not an external target authorization or production approval."
            ))
        if self.iris_binary is not None and self.chrome_binary is not None:
            candidates.append((
                "harness_iris_owned_page",
                "Capture ONLY reviewed Hazewave-owned local HTML fixture via Iris 0.4.1. "
                "Never navigate to arbitrary URLs or user-provided paths."
            ))
        return [{
            "name": name,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "minLength": 4, "maxLength": 80},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        } for name, description in candidates]

    def call(self, name: str, args: Mapping[str, Any]) -> dict[str, Any]:
        if self.completed_calls >= self.max_calls:
            raise ResearchExecutionError("MCP_FIXTURE_CALL_BUDGET_EXCEEDED")
        if not isinstance(args, Mapping) or set(args) != {"task_id"}:
            raise ResearchExecutionError("MCP_TARGET_OVERRIDE_NOT_ADMITTED")
        enabled = {tool["name"] for tool in self.supported_tools()}
        if name not in enabled:
            raise ResearchExecutionError("MCP_TOOL_NOT_ADMITTED")
        self.completed_calls += 1  # even failed attempts consume the budget
        kind = "rea_owned_js" if name == "harness_rea_owned_js" else "iris_owned_page"
        return self.executor(
            kind=kind,
            task_id=args["task_id"],
            workspace=self.workspace,
            expected_sha=self.expected_sha,
            state_root=self.state_root,
            rea_binary=self.rea_binary,
            iris_binary=self.iris_binary,
            chrome_binary=self.chrome_binary,
        )


def serve_request(gateway: FixtureMcpGateway, request: Any) -> dict[str, Any] | None:
    if not isinstance(request, Mapping) or request.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None,
                "error": {"code": -32600, "message": "Invalid Request"}}
    method = request.get("method")
    rid = request.get("id")
    if method == "notifications/initialized" and rid is None:
        return None
    if rid is None or isinstance(rid, bool) or not isinstance(rid, (int, str)):
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": -32600, "message": "Invalid Request"}}
    params = request.get("params", {})
    if not isinstance(params, Mapping):
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": -32602, "message": "Invalid params"}}
    if method == "initialize":
        if params.get("protocolVersion") != "2025-11-25":
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32602, "message": "Unsupported protocol version"}}
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": "2025-11-25",
            "serverInfo": {"name": "hazewave-research-fixtures", "version": "1.0.0"},
            "capabilities": {"tools": {"listChanged": False}},
        }}
    if method == "tools/list":
        if params:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32602, "message": "Pagination not supported"}}
        return {"jsonrpc": "2.0", "id": rid,
                "result": {"tools": gateway.supported_tools()}}
    if method == "tools/call":
        try:
            if set(params) != {"name", "arguments"} or not isinstance(params["name"], str):
                raise ResearchExecutionError("MCP_ARGUMENTS_INVALID")
            report = gateway.call(params["name"], params["arguments"])
            # Do not report success beyond the narrow OBSERVATION_ONLY envelope.
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": json.dumps(report, sort_keys=True)}],
                "isError": False,
            }}
        except (ResearchExecutionError, TypeError, ValueError, OSError) as exc:
            label = str(exc) if isinstance(exc, ResearchExecutionError) else "TOOL_ERROR"
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": "HAZEWAVE_FIXTURE_BLOCKED:" + label}],
                "isError": True,
            }}
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": "Method not found"}}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Owner-fixture-only Harness MCP gateway")
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--expected-sha", required=True)
    p.add_argument("--state-root", type=Path, required=True)
    p.add_argument("--rea", type=Path)
    p.add_argument("--iris", type=Path)
    p.add_argument("--chrome", type=Path)
    args = p.parse_args(argv)
    gateway = FixtureMcpGateway(
        workspace=args.workspace,
        expected_sha=args.expected_sha,
        state_root=args.state_root,
        rea_binary=args.rea,
        iris_binary=args.iris,
        chrome_binary=args.chrome,
    )
    for line in sys.stdin:
        if len(line) > 8192:
            print(json.dumps({"jsonrpc": "2.0", "id": None,
                              "error": {"code": -32600, "message": "Request too large"}}),
                  flush=True)
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": "Parse error"}}
        else:
            reply = serve_request(gateway, request)
        if reply is not None:
            print(json.dumps(reply, separators=(",", ":"), allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
