"""Bounded REAL subprocess MCP client probe, not an agent-session attestation.

This process launches the existing fixture-only Harness STDIO server, verifies
initialize/tools/list, denies URL escalation, makes two real tools/call requests,
checks underlying receipts, and retains production/agent readiness false.
No real agent is implicitly connected by this independent client.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import time
from typing import Any, Mapping


_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ADMITTED = {"harness_rea_owned_js": "rea_owned_js",
             "harness_iris_owned_page": "iris_owned_page"}


class QualificationError(ValueError):
    pass


def _require(value: bool, code: str) -> None:
    if not value:
        raise QualificationError(code)


def verify_advertised_tools(catalog: Mapping[str, Any]) -> list[str]:
    _require(isinstance(catalog, Mapping) and isinstance(catalog.get("tools"), list),
             "MCP_CATALOG_INVALID")
    tools = catalog["tools"]
    _require(len(tools) == len(_ADMITTED), "MCP_CATALOG_UNEXPECTED_TOOL_COUNT")
    names: list[str] = []
    for item in tools:
        _require(isinstance(item, Mapping), "MCP_CATALOG_TOOL_INVALID")
        name = item.get("name")
        schema = item.get("inputSchema")
        _require(isinstance(name, str) and name in _ADMITTED
                 and name not in names, "MCP_CATALOG_UNAUTHORIZED_TOOL")
        _require(isinstance(schema, Mapping)
                 and schema.get("type") == "object"
                 and schema.get("additionalProperties") is False
                 and schema.get("required") == ["task_id"]
                 and set(schema.get("properties", {})) == {"task_id"},
                 "MCP_CATALOG_UNBOUNDED_INPUT")
        names.append(name)
    return sorted(names)


def verify_observation_result(
    result: Mapping[str, Any], *, kind: str, expected_sha: str
) -> dict[str, Any]:
    _require(kind in _ADMITTED.values(), "MCP_KIND_UNAUTHORIZED")
    _require(isinstance(expected_sha, str) and bool(_SHA40.fullmatch(expected_sha)),
             "REVIEWED_SHA_INVALID")
    _require(isinstance(result, Mapping) and result.get("isError") is False
             and isinstance(result.get("content"), list)
             and len(result["content"]) == 1
             and result["content"][0].get("type") == "text",
             "MCP_RESULT_FAILED")
    try:
        payload = json.loads(result["content"][0]["text"])
    except (ValueError, TypeError) as exc:
        raise QualificationError("MCP_RESULT_JSON_INVALID") from exc
    _require(isinstance(payload, Mapping), "MCP_RESULT_JSON_INVALID")
    _require(payload.get("schema") == "HazewaveHarnessExecutedResearchFixture/v1"
             and payload.get("kind") == kind
             and payload.get("reviewed_repo_sha") == expected_sha
             and payload.get("harness_authority") == "HAZEWAVE_HARNESS"
             and payload.get("authorization_scope") == "FIRST_PARTY_FIXTURE_BOOTSTRAP_ONLY"
             and payload.get("state") == "OBSERVATION_ONLY",
             "MCP_RESULT_IDENTITY_INVALID")
    for field in ("host_identity_verified", "agent_mcp_session_connected",
                  "capability_plane_measured_ready", "production_approved",
                  "owner_signed_external_target"):
        _require(payload.get(field) is False, "MCP_UNAUTHORIZED_PROMOTION")
    for field in ("provider_tool_sha256", "receipt_sha256"):
        v = payload.get(field)
        _require(isinstance(v, str) and bool(_SHA256.fullmatch(v)),
                 "MCP_EVIDENCE_HASH_MISSING")
    return dict(payload)


class StdioRpc:
    def __init__(self, child: subprocess.Popen[bytes]):
        self.child = child
        self.pending = bytearray()

    def send(self, request: Mapping[str, Any], *, expect_reply: bool = True,
             timeout: float = 125.0) -> dict[str, Any] | None:
        if self.child.stdin is None or self.child.stdout is None:
            raise QualificationError("MCP_STDIO_UNAVAILABLE")
        data = json.dumps(request, separators=(",", ":"), allow_nan=False).encode() + b"\n"
        self.child.stdin.write(data)
        self.child.stdin.flush()
        if not expect_reply:
            return None
        deadline = time.monotonic() + timeout
        while True:
            if b"\n" in self.pending:
                record, _, suffix = self.pending.partition(b"\n")
                self.pending = bytearray(suffix)
                try:
                    answer = json.loads(record)
                except ValueError as exc:
                    raise QualificationError("MCP_INVALID_STDOUT_FRAME") from exc
                _require(isinstance(answer, dict)
                         and answer.get("id") == request["id"]
                         and answer.get("jsonrpc") == "2.0"
                         and "error" not in answer
                         and isinstance(answer.get("result"), Mapping),
                         "MCP_RPC_RESPONSE_INVALID")
                return answer["result"]
            remaining = deadline - time.monotonic()
            _require(remaining > 0, "MCP_CLIENT_TIMEOUT")
            ready, _, _ = select.select([self.child.stdout.fileno()], [], [], remaining)
            _require(bool(ready), "MCP_CLIENT_TIMEOUT")
            chunk = os.read(self.child.stdout.fileno(), 65536)
            _require(bool(chunk), "MCP_CLIENT_EOF")
            self.pending.extend(chunk)
            _require(len(self.pending) <= 10 * 1024 * 1024, "MCP_RESPONSE_TOO_LARGE")


def probe_fixture_gateway(
    *, workspace: Path, expected_sha: str, state_root: Path,
    rea: Path, iris: Path, chrome: Path,
) -> dict[str, Any]:
    _require(bool(_SHA40.fullmatch(str(expected_sha))), "REVIEWED_SHA_INVALID")
    workspace = Path(workspace).resolve(strict=True)
    for binary in (rea, iris, chrome):
        _require(Path(binary).is_file(), "PINNED_TOOL_MISSING")
    state_root = Path(state_root)
    _require(not state_root.resolve(strict=False).is_relative_to(workspace),
             "STATE_ROOT_INSIDE_REPO")
    cmd = [
        sys.executable, "-m", "hazewave.harness_research_mcp",
        "--workspace", str(workspace),
        "--expected-sha", expected_sha,
        "--state-root", str(state_root),
        "--rea", str(rea), "--iris", str(iris), "--chrome", str(chrome),
    ]
    env = {key: os.environ[key] for key in (
        "HOME", "PATH", "LANG", "LC_ALL", "TMPDIR", "DISPLAY",
        "XDG_RUNTIME_DIR", "XDG_CACHE_HOME", "FONTCONFIG_PATH",
    ) if key in os.environ}
    env["PYTHONPATH"] = str(workspace / "src")
    with subprocess.Popen(cmd, cwd=workspace, env=env,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, bufsize=0) as child:
        client = StdioRpc(child)
        session = client.send({"jsonrpc": "2.0", "id": 1,
            "method": "initialize", "params": {
                "protocolVersion": "2025-11-25",
                "clientInfo": {"name": "hazewave-independent-host-probe",
                               "version": "1.0.0"},
                "capabilities": {},
            }}, timeout=10)
        _require(session is not None
                 and session.get("protocolVersion") == "2025-11-25"
                 and session.get("serverInfo", {}).get("name") == "hazewave-research-fixtures",
                 "MCP_INITIALIZATION_INVALID")
        client.send({"jsonrpc": "2.0", "method": "notifications/initialized"},
                    expect_reply=False)
        catalog = client.send({"jsonrpc": "2.0", "id": 2,
                               "method": "tools/list", "params": {}}, timeout=10)
        tools = verify_advertised_tools(catalog)

        injection = client.send({"jsonrpc": "2.0", "id": 3,
                                 "method": "tools/call", "params": {
                                     "name": "harness_iris_owned_page",
                                     "arguments": {"task_id": "owned-host-negative-0001",
                                                   "url": "https://example.com"}}}, timeout=10)
        _require(injection.get("isError") is True, "MCP_SCOPE_OVERRIDE_WAS_ACCEPTED")
        results: list[dict[str, Any]] = []
        for rid, (name, kind) in enumerate(_ADMITTED.items(), start=4):
            outcome = client.send({"jsonrpc": "2.0", "id": rid,
                                   "method": "tools/call", "params": {
                                       "name": name,
                                       "arguments": {"task_id": f"owned-codespace-fixture-{rid:04d}"}}})
            results.append(verify_observation_result(
                outcome, kind=kind, expected_sha=expected_sha))
        if child.stdin is not None:
            child.stdin.close()
        child.wait(timeout=10)
        _require(child.returncode == 0, "MCP_SERVER_UNCLEAN_EXIT")

    return {
        "schema": "HazewaveIndependentHostMcpProbe/v1",
        "authority": "NONE",
        "actual_stdio_mcp_initialize": True,
        "actual_stdio_mcp_tools_list": True,
        "actual_stdio_mcp_tools_call": True,
        "observed_tools": tools,
        "negative_external_url_denied": True,
        "reviewed_repo_sha": expected_sha,
        "provider_receipts_sha256": [x["receipt_sha256"] for x in results],
        "independent_client_probe": True,
        "existing_owner_agent_session_connected": False,
        "verified_codespace_identity": False,
        "production_approved": False,
    }


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--expected-sha", required=True)
    p.add_argument("--state-root", type=Path, required=True)
    p.add_argument("--rea", type=Path, required=True)
    p.add_argument("--iris", type=Path, required=True)
    p.add_argument("--chrome", type=Path, required=True)
    args=p.parse_args()
    try:
        report=probe_fixture_gateway(**vars(args))
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print("WAVE_MCP_HOST_PROBE=BLOCKED:" + str(exc), file=sys.stderr)
        return 20
    print(json.dumps(report, sort_keys=True))
    print("WAVE_MCP_HOST_PROBE=PASS_BOUNDED_INDEPENDENT_CLIENT")
    print("WAVE_EXISTING_AGENT_SESSION=NOT_PROVEN")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
