"""Prove Iris stdio MCP tools/list and tools/call on one first-party HTML fixture.

Does not register an MCP client, broaden URL permission, or attest that
owner agents have loaded this server. Only meant for isolated test runners.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time

from hazewave.iris_capture import _inspect_png, iris_capture_policy


class IrisMcpProofError(RuntimeError):
    pass


def _request(child: subprocess.Popen[str], payload: dict) -> None:
    assert child.stdin is not None
    child.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    child.stdin.flush()


def _wait(child: subprocess.Popen[str], msgid: int, timeout: float) -> dict:
    assert child.stdout is not None
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        ready, _, _ = select.select([child.stdout], [], [], min(1.0, until - time.monotonic()))
        if not ready:
            if child.poll() is not None:
                raise IrisMcpProofError("IRIS_MCP_EXITED_EARLY")
            continue
        line = child.stdout.readline()
        if not line:
            raise IrisMcpProofError("IRIS_MCP_CLOSED_STDOUT")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IrisMcpProofError("IRIS_MCP_INVALID_JSON") from exc
        if event.get("id") == msgid:
            if "error" in event:
                raise IrisMcpProofError("IRIS_MCP_JSONRPC_ERROR")
            return event
    raise IrisMcpProofError("IRIS_MCP_TIMEOUT")


def probe(iris: Path, chrome: Path, workspace: Path) -> dict:
    url = iris_capture_policy(
        (workspace.resolve() / "tests/fixtures/iris-proof.html").as_uri(),
        workspace=workspace,
    )
    proc = subprocess.Popen(
        [str(iris), "mcp", "--chrome", str(chrome)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, bufsize=1,
    )
    try:
        _request(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                       "clientInfo": {"name": "hazewave-iris-fixture-probe", "version": "1.0.0"}},
        })
        initialize = _wait(proc, 1, 8)
        if initialize.get("result", {}).get("serverInfo", {}).get("name") != "iris":
            raise IrisMcpProofError("IRIS_MCP_SERVER_IDENTITY_INVALID")
        _request(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        _request(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        listed = _wait(proc, 2, 8)
        tools = listed.get("result", {}).get("tools", [])
        if len(tools) != 1 or tools[0].get("name") != "capture":
            raise IrisMcpProofError("IRIS_MCP_UNEXPECTED_TOOL_CATALOG")
        _request(proc, {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {
                "name": "capture",
                "arguments": {
                    "url": url, "selector": "#hazewave-iris-proof",
                    "padding": 8, "size": "320x240", "scale": 1,
                    "timeout_seconds": 20,
                },
            },
        })
        captured = _wait(proc, 3, 35).get("result", {})
        if captured.get("isError") is True:
            raise IrisMcpProofError("IRIS_MCP_CAPTURE_ERROR")
        meta = captured.get("structuredContent", {})
        if meta.get("status") != "ok" or meta.get("url") != url or meta.get("output") is not None:
            raise IrisMcpProofError("IRIS_MCP_CAPTURE_METADATA_INVALID")
        blocks = [v for v in captured.get("content", []) if v.get("type") == "image"]
        if len(blocks) != 1 or blocks[0].get("mimeType") != "image/png":
            raise IrisMcpProofError("IRIS_MCP_INLINE_IMAGE_MISSING")
        try:
            raw = base64.b64decode(blocks[0]["data"], validate=True)
        except (ValueError, KeyError) as exc:
            raise IrisMcpProofError("IRIS_MCP_INLINE_IMAGE_INVALID") from exc
        with tempfile.TemporaryDirectory() as temp:
            png = Path(temp) / "iris-mcp-proof.png"
            png.write_bytes(raw)
            digest, size, width, height = _inspect_png(png)
        return {
            "schema": "HazewaveIrisMcpFixtureProof/v1",
            "status": "PASS:FIRST_PARTY_SYNTHETIC_MCP_CAPTURE",
            "upstream_server_name": "iris",
            "tools_listed": ["capture"],
            "image_sha256": digest,
            "png_bytes": size,
            "pixel_width": width,
            "pixel_height": height,
            "owner_agent_session_connected": False,
            "harness_runtime_authorized": False,
            "production_approved": False,
        }
    finally:
        if proc.stdin:
            proc.stdin.close()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--iris", type=Path, required=True)
    p.add_argument("--chrome", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        out = probe(args.iris, args.chrome, args.workspace)
    except (IrisMcpProofError, OSError, ValueError) as exc:
        print("HAZEWAVE_IRIS_MCP_FIXTURE=BLOCKED:" + str(exc), file=sys.stderr)
        return 20
    print("HAZEWAVE_IRIS_MCP_FIXTURE=PASS")
    print(json.dumps(out, sort_keys=True))
    print("HAZEWAVE_OWNER_AGENT_MCP=NOT_CONNECTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
