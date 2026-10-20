"""REA 6.0.0 provider-route evidence classification (read-only).

This file does not install REA, authorize a target or register agents.
Native Ghidra, JS static inspection and managed static parsing are different
capabilities. Rizin/Frida are supporting open-source tools, not automatically
equivalent REA analysis providers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


class ReaProviderError(ValueError):
    pass


_SHA = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED = frozenset({"ghidra", "javascript_static", "managed_static", "rizin", "frida"})
_STATES = frozenset({"NOT_TESTED", "UNAVAILABLE", "BLOCKED", "TOOL_DISCOVERED",
                     "CI_PROVEN", "NEGATIVE_CONTROL_PROVEN", "HOST_FIXTURE_PROVEN"})


def validate_javascript_probe(data: Any, *, fixture_sha256: str) -> dict[str, Any]:
    """Validate a substantive static application graph, not just CLI exit(0).

    When REA's canonical directory root hashing differs from our fixture-tree
    hash, keep both digests separately. No assertion of code equivalence.
    """
    if not _SHA.fullmatch(str(fixture_sha256)):
        raise ReaProviderError("REA6_JS_FIXTURE_SHA_INVALID")
    if not isinstance(data, Mapping):
        raise ReaProviderError("REA6_JS_RESULT_INVALID")
    # REA CLI normally emits the domain Evidence result directly.
    record = data.get("result") if isinstance(data.get("result"), Mapping) else data
    if not isinstance(record, Mapping):
        raise ReaProviderError("REA6_JS_RESULT_INVALID")
    evidence_id = record.get("evidence_id")
    if not isinstance(evidence_id, str) or not evidence_id.startswith("ev_"):
        raise ReaProviderError("REA6_JS_EVIDENCE_MISSING")
    result = record.get("normalized_result")
    if not isinstance(result, Mapping):
        raise ReaProviderError("REA6_JS_GRAPH_MISSING")
    graph = result.get("graph")
    if not isinstance(graph, Mapping):
        raise ReaProviderError("REA6_JS_GRAPH_MISSING")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ReaProviderError("REA6_JS_NODES_MISSING")
    if not any(isinstance(n, Mapping) and n.get("kind") == "javascript-module" for n in nodes):
        raise ReaProviderError("REA6_JS_MODULE_NOT_OBSERVED")
    return {
        "schema": "HazewaveRea6JsStaticFixtureEvidence/v1",
        "source_type": "FIRST_PARTY_SYNTHETIC",
        "state": "GRAPH_STRUCTURALLY_VALIDATED",
        "fixture_tree_sha256": fixture_sha256,
        "rea_evidence_id": evidence_id,
        "module_node_count": sum(isinstance(n, Mapping) and n.get("kind") == "javascript-module" for n in nodes),
        "graph_node_count": len(nodes),
        "codespace_proven": False,
        "mcp_agent_connected": False,
        "human_production_approved": False,
    }


def summarize_provider_matrix(routes: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(routes, Mapping):
        raise ReaProviderError("PROVIDER_MATRIX_INVALID")
    if set(routes) - _ALLOWED:
        raise ReaProviderError("UNKNOWN_PROVIDER_ROUTE")
    normalized = {}
    for name in sorted(_ALLOWED):
        item = routes.get(name, {"status": "NOT_TESTED"})
        if not isinstance(item, Mapping) or item.get("status") not in _STATES:
            raise ReaProviderError("PROVIDER_STATUS_INVALID")
        normalized[name] = dict(item)
    return {
        "schema": "HazewaveRea6ProviderConformance/v1",
        "version": "6.0.0",
        "owner_authority": "HAZEWAVE_HARNESS",
        "routes": normalized,
        "capability_coverage": {
            "route_count": len(_ALLOWED),
            "ci_fixture_routes": sum(x["status"] == "CI_PROVEN" for x in normalized.values()),
            "positive_runtime_routes": sum(x["status"] == "HOST_FIXTURE_PROVEN" for x in normalized.values()),
            "blocked_or_unavailable": sum(x["status"] in {"BLOCKED", "UNAVAILABLE"} for x in normalized.values()),
        },
        "codespace_native_ready": False,
        "agent_mcp_connected": False,
        "fully_ready": False,
        "production_approved": False,
        "note": "A source-owned fixture cannot authorize external binaries or any production target.",
    }


def fixture_tree_sha(root: Path) -> str:
    """Commit a deterministic ordered list of names and bytes, without traversal."""
    base = Path(root).resolve(strict=True)
    digest = hashlib.sha256()
    files = sorted(x for x in base.rglob("*") if x.is_file())
    if not files or len(files) > 24:
        raise ReaProviderError("REA6_JS_FIXTURE_LAYOUT_INVALID")
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(base):
            raise ReaProviderError("REA6_JS_FIXTURE_LAYOUT_UNSAFE")
        rel = path.relative_to(base).as_posix().encode()
        data = path.read_bytes()
        if len(data) > 64000:
            raise ReaProviderError("REA6_JS_FIXTURE_SIZE_INVALID")
        digest.update(len(rel).to_bytes(4, "big") + rel)
        digest.update(len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    js = sub.add_parser("validate-js-fixture")
    js.add_argument("--fixture", type=Path, required=True)
    js.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-js-fixture":
            input_file = args.evidence
            if input_file.is_symlink() or not input_file.is_file() or input_file.stat().st_size > 4_000_000:
                raise ReaProviderError("REA6_JS_OUTPUT_UNSAFE")
            record = json.loads(input_file.read_text())
            result = validate_javascript_probe(
                record, fixture_sha256=fixture_tree_sha(args.fixture)
            )
            print(json.dumps(result, sort_keys=True))
            print("REA6_JS_FIXTURE_GRAPH=PASS")
            return 0
    except (ValueError, OSError, TypeError) as exc:
        print(f"REA6_JS_FIXTURE_GRAPH=BLOCKED:{type(exc).__name__}:{exc}", file=sys.stderr)
        return 20
    return 20


if __name__ == "__main__":
    raise SystemExit(main())
