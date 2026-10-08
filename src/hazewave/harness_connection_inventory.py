"""Read-only full Harness connection inventory, not a presence = ready shortcut.

Catalog coverage is derived from the actual Harness, not a manually copied
count. The connection sequence is a deterministic work queue, not an
automatic installer, unreviewed global MCP registration or authority grant.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from hazewave.harness import (
    AUTHORITY, classify_capability_domain, capability_allows_domain, harness_status
)
from hazewave.capability_plane import describe_capabilities

_DEFAULT = Path(__file__).resolve().parents[2] / "config" / "capability-evidence-plane-v1.json"

_ROUTE_PLAN = (
    ("rea6.ghidra_native", "research.visual.inspect", "rea6", "PROVE_OWNED_FIXTURE"),
    ("rea6.js_static", "research.visual.inspect", "rea6", "PROVE_OWNED_FIXTURE"),
    ("iris.local_fixture", "web.visual_regression", "iris", "PROVE_OWNED_FIXTURE"),
    ("rea6.managed", "research.visual.inspect", "rea6", "QUALIFY_PROVIDER"),
    ("rea6.electron_observation", "research.visual.inspect", "rea6", "WAIT_FOR_SECURITY_ISOLATION"),
    ("iris.live_site", "web.visual_regression", "iris", "WAIT_FOR_SECURITY_ISOLATION"),
    ("haze.ffmpeg_qc", "audio.qc", "ffmpeg_audio", "PROVE_OWNED_FIXTURE"),
    ("wave.ffprobe_qc", "visual.qc", "ffmpeg_video", "PROVE_OWNED_FIXTURE"),
    ("wave.pillow_image", "image.qc", "pillow", "PROVE_OWNED_FIXTURE"),
    ("wave.scenedetect", "scene.detect", "pyscenedetect", "PROVE_OWNED_FIXTURE"),
    ("wave.otio", "timeline.inspect", "otio", "PROVE_OWNED_FIXTURE"),
    ("haze.essentia", "audio.analyze", "essentia", "QUALIFY_PROVIDER"),
    ("haze.demucs", "audio.separate", "demucs", "QUALIFY_PROVIDER"),
    ("wave.opencv", "visual.analyze", "opencv", "QUALIFY_PROVIDER"),
)


def inventory_all_capabilities(
    manifest: Path = _DEFAULT, *, host_av_execution: dict[str, Any] | None = None
) -> dict[str, Any]:
    declared = tuple(harness_status()["capabilities"])
    registry = describe_capabilities(Path(manifest))
    providers: dict[str, list[str]] = {}
    for tool in registry["tools"]:
        providers.setdefault(tool["capability_id"], []).append(tool["tool_id"])
    if any(key not in declared for key in providers):
        raise ValueError("MANIFEST_REFERENCES_UNDECLARED_CAPABILITY")
    # Cross-domain capability classification requires explicit request domain.
    capabilities: dict[str, Any] = {}
    for cap in declared:
        mapped = providers.get(cap, [])
        try:
            domain = classify_capability_domain(cap)
        except ValueError:
            domain = "CROSS_DOMAIN_EXPLICIT_REQUEST_REQUIRED"
        capabilities[cap] = {
            "domain": domain,
            "provider_candidates": list(sorted(mapped)),
            "selected_provider": None,
            "mapping": "MAPPED_UNVERIFIED" if mapped else "NO_EXACT_PROVIDER_MAPPING",
            "host_binary_present": "UNVERIFIED",
            "live_agent_mcp_connected": "UNVERIFIED",
            "fixture_execution": "UNVERIFIED",
            "native_ghidra_evidence": "UNVERIFIED",
            "benchmark": "UNVERIFIED",
            "ready": False,
            "production_approved": False,
        }
    observed_av_count = 0
    if host_av_execution is not None:
        if (host_av_execution.get("schema") != "HazewaveObservedHostAVExecution/v1"
                or host_av_execution.get("evidence_state") != "EXECUTED"
                or host_av_execution.get("provenance")
                    != "LOCAL_LOG_AND_RECEIPT_INTEGRITY_NOT_INDEPENDENT_ATTESTATION"
                or any(host_av_execution.get(k) is not False for k in
                       ("agent_connected", "tool_routing_authorized", "benchmarked", "production_approved"))):
            raise ValueError("HOST_AV_UNVERIFIED_OR_PROMOTED")
        for cap in ("audio.qc", "visual.qc"):
            if cap not in capabilities:
                raise ValueError("HOST_AV_CAPABILITY_NOT_DECLARED")
            capabilities[cap]["fixture_execution"] = "EXECUTED_SYNTHETIC_UNATTESTED"
            capabilities[cap]["execution_evidence_sha256"] = host_av_execution["log_sha256"]
            observed_av_count += 1
    queue: list[dict[str, Any]] = []
    for route, cap, provider, action in _ROUTE_PLAN:
        if provider not in providers.get(cap, []):
            raise ValueError("CONNECTION_PLAN_NO_PROVIDER_MAPPING:" + route)
        queue.append({
            "route": route, "harness_capability": cap,
            "provider": provider, "domain": capabilities[cap]["domain"],
            "next_action": action, "auto_connect": False,
            "host": "EXISTING_CODESPACE_ONLY", "task_grant_required": True,
            "agent_connection_status": "NOT_PROVEN",
        })
    mapped_set = set(providers)
    for cap in declared:
        if cap not in mapped_set:
            queue.append({
                "route": "unmapped:" + cap,
                "harness_capability": cap, "provider": None,
                "domain": capabilities[cap]["domain"],
                "next_action": "QUALIFY_PROVIDER", "auto_connect": False,
                "host": "EXISTING_CODESPACE_ONLY", "task_grant_required": True,
                "agent_connection_status": "NOT_PROVEN",
            })
    return {
        "schema": "HazewaveFullCapabilityConnectionInventory/v1",
        "authority": AUTHORITY,
        "scope": ("REPOSITORY_DECLARATIONS_WITH_UNATTESTED_AV_OBSERVATION"
                  if observed_av_count else "REPOSITORY_DECLARATIONS_NOT_LIVE_HOST"),
        "codespace_proven": False,
        "capabilities": capabilities,
        "summary": {
            "declared": len(declared),
            "provider_mapped": len(mapped_set),
            "provider_unmapped": len(declared) - len(mapped_set),
            "providers_declared": len(registry["tools"]),
            "ready_on_existing_codespace": 0,
            "agent_connected_on_existing_codespace": 0,
            "host_synthetic_av_executions_observed": observed_av_count,
        },
        "connection_sequence": queue,
        "production_approved": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read-only full Harness capability coverage")
    p.add_argument("--manifest", type=Path, default=_DEFAULT)
    p.add_argument("--output", type=Path)
    p.add_argument("--host-av-log", type=Path)
    p.add_argument("--host-av-receipt", type=Path)
    p.add_argument("--host-av-repo-sha")
    p.add_argument("--host-av-log-sha256")
    p.add_argument("--host-av-receipt-sha256")
    args = p.parse_args(argv)
    parts = (args.host_av_log, args.host_av_receipt, args.host_av_repo_sha,
             args.host_av_log_sha256, args.host_av_receipt_sha256)
    if any(v is not None for v in parts) and not all(v is not None for v in parts):
        raise SystemExit("HOST_AV_EVIDENCE_ARGS_INCOMPLETE")
    observation = None
    if all(v is not None for v in parts):
        from hazewave.host_av_evidence import HostAvEvidenceError, verify_host_av_evidence
        try:
            observation = verify_host_av_evidence(
                log_path=args.host_av_log, receipt_path=args.host_av_receipt,
                reviewed_sha=args.host_av_repo_sha,
                expected_log_sha256=args.host_av_log_sha256,
                expected_receipt_sha256=args.host_av_receipt_sha256
            )
        except HostAvEvidenceError as exc:
            raise SystemExit("HOST_AV_EVIDENCE_BLOCKED:" + str(exc)) from exc
    report = inventory_all_capabilities(args.manifest, host_av_execution=observation)
    # Do not write into the repo by default; private output optional.
    if args.output:
        import os
        out = args.output.expanduser()
        if out.is_symlink() or out.exists():
            raise SystemExit("INVENTORY_OUTPUT_ALREADY_EXISTS")
        if out.parent.is_symlink():
            raise SystemExit("INVENTORY_OUTPUT_PARENT_UNSAFE")
        out.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        fd = os.open(out, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(report, stream, sort_keys=True, indent=2)
            stream.write("\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
