"""Hazewave Harness evidence-first capability inventory and advisory router.

Never conflates tool catalog, executable presence, CI fixture proof, observed
agent access, task-scoped authorization or production approval. Read-only,
stdlib-only. No background loops, installations or implicit side effects.

The returned selection is ADVISORY; it is not an authorization token.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any, Callable, Mapping

from hazewave.harness import AUTHORITY, harness_status, capability_allows_domain


class CapabilityPlaneError(ValueError):
    pass


_HEX = re.compile(r"^[0-9a-f]{64}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_NAME = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_PRINCIPAL = "hazewave-owner"
_NAMESPACE = "hazewave-capability-proof"
_SCHEMA = "HazewaveCapabilityRuntimeEvidence/v1"
_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MANIFEST = _ROOT / "config" / "capability-evidence-plane-v1.json"


@dataclass(frozen=True)
class VerifiedCapabilityEvidence:
    data: Mapping[str, Any]
    proof_sha256: str
    source: str = "OWNER_SIGNED_BYTES_AND_LOCAL_ARTIFACT"


def _private_bytes(path: Path, *, max_bytes: int = 64 * 1024) -> bytes:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or path.is_symlink():
            raise CapabilityPlaneError("EVIDENCE_UNSAFE_PATH")
        if info.st_uid != os.geteuid() or info.st_mode & 0o077 or info.st_size > max_bytes:
            raise CapabilityPlaneError("EVIDENCE_UNSAFE_PERMISSIONS")
        return path.read_bytes()
    except OSError as exc:
        raise CapabilityPlaneError("EVIDENCE_FILE_UNAVAILABLE") from exc


def _load_json(blob: bytes) -> Any:
    def no_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in items:
            if k in out:
                raise ValueError("duplicate key")
            out[k] = v
        return out
    try:
        return json.loads(blob, object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, ValueError) as exc:
        raise CapabilityPlaneError("EVIDENCE_INVALID_JSON") from exc


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise CapabilityPlaneError("EVIDENCE_TIME_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CapabilityPlaneError("EVIDENCE_TIME_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CapabilityPlaneError("EVIDENCE_TIME_INVALID")
    return parsed.astimezone(timezone.utc)


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or path.is_symlink():
            raise CapabilityPlaneError("EVIDENCE_ARTIFACT_UNSAFE")
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError as exc:
        raise CapabilityPlaneError("EVIDENCE_ARTIFACT_UNAVAILABLE") from exc
    return h.hexdigest()


def verify_signed_runtime_evidence(
    evidence: Path,
    signature: Path,
    allowed_signers: Path,
    *,
    artifact: Path,
    now: datetime | None = None,
) -> VerifiedCapabilityEvidence:
    """Verify short-lived owner-signed *claims* bound to an actual local log.

    Signature authenticates who attests the result; it does not independently
    prove execution unless a trusted verifier has reviewed the underlying log.
    No user-supplied boolean self-certifies readiness.
    """
    evidence, signature, allowed_signers, artifact = map(
        Path, (evidence, signature, allowed_signers, artifact)
    )
    data_bytes = _private_bytes(evidence)
    _private_bytes(signature)
    signers = _private_bytes(allowed_signers)
    if not any(line.startswith((_PRINCIPAL + " ").encode()) for line in signers.splitlines()):
        raise CapabilityPlaneError("EVIDENCE_SIGNER_NOT_TRUSTED")
    data = _load_json(data_bytes)
    if not isinstance(data, dict):
        raise CapabilityPlaneError("EVIDENCE_INVALID_ENVELOPE")
    if any(data.get(k) != v for k, v in (
        ("schema", _SCHEMA), ("authority", AUTHORITY), ("issuer", _PRINCIPAL)
    )):
        raise CapabilityPlaneError("EVIDENCE_AUTHORITY_INVALID")
    if not isinstance(data.get("tool_id"), str) or not _NAME.fullmatch(data["tool_id"]):
        raise CapabilityPlaneError("EVIDENCE_TOOL_INVALID")
    if not isinstance(data.get("repo_sha"), str) or not _SHA.fullmatch(data["repo_sha"]):
        raise CapabilityPlaneError("EVIDENCE_REPO_SHA_INVALID")
    if not isinstance(data.get("host_id"), str) or not (3 <= len(data["host_id"]) <= 128):
        raise CapabilityPlaneError("EVIDENCE_HOST_INVALID")
    if data.get("scope") not in {"CI_FIXTURE", "LOCAL_HOST"}:
        raise CapabilityPlaneError("EVIDENCE_SCOPE_INVALID")
    if data.get("stage") not in {"INSTALLED", "EXPOSED", "EXECUTED", "BENCHMARKED"}:
        raise CapabilityPlaneError("EVIDENCE_STAGE_INVALID")
    if not all(isinstance(data.get(k), str) and _HEX.fullmatch(data[k]) for k in (
        "binary_sha256", "fixture_sha256", "evidence_sha256"
    )):
        raise CapabilityPlaneError("EVIDENCE_DIGEST_INVALID")
    if data["evidence_sha256"] != _sha_file(artifact):
        raise CapabilityPlaneError("EVIDENCE_ARTIFACT_DIGEST_MISMATCH")
    if data.get("fixture_result") not in {"PASS", "FAIL", "NOT_TESTED"}:
        raise CapabilityPlaneError("EVIDENCE_RESULT_INVALID")
    if type(data.get("tool_list_observed")) is not bool or type(data.get("tool_call_observed")) is not bool:
        raise CapabilityPlaneError("EVIDENCE_OBSERVATION_INVALID")
    if data.get("production_approved") is not False:
        raise CapabilityPlaneError("EVIDENCE_CANNOT_GRANT_PRODUCTION_APPROVAL")
    benchmark = data.get("benchmark")
    if not isinstance(benchmark, dict):
        raise CapabilityPlaneError("EVIDENCE_BENCHMARK_MISSING")
    if type(benchmark.get("sample_count")) is not int or not 0 <= benchmark["sample_count"] <= 100000:
        raise CapabilityPlaneError("EVIDENCE_SAMPLES_INVALID")
    for k in ("quality_score", "cost_usd", "risk_score", "p50_latency_ms", "p95_latency_ms"):
        v = benchmark.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            raise CapabilityPlaneError("EVIDENCE_BENCHMARK_VALUE_INVALID")
    if not (0 <= benchmark["quality_score"] <= 1 and 0 <= benchmark["risk_score"] <= 1
            and benchmark["cost_usd"] >= 0 and benchmark["p50_latency_ms"] > 0
            and benchmark["p95_latency_ms"] >= benchmark["p50_latency_ms"]):
        raise CapabilityPlaneError("EVIDENCE_BENCHMARK_RANGE_INVALID")
    issued, expires = _time(data.get("issued_at")), _time(data.get("expires_at"))
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise CapabilityPlaneError("EVIDENCE_TIME_INVALID")
    clock = clock.astimezone(timezone.utc)
    if expires <= clock:
        raise CapabilityPlaneError("EVIDENCE_EXPIRED")
    if issued > clock + timedelta(minutes=2) or expires <= issued or expires - issued > timedelta(hours=6):
        raise CapabilityPlaneError("EVIDENCE_TIME_INVALID")
    try:
        result = subprocess.run(
            ["ssh-keygen", "-Y", "verify", "-f", str(allowed_signers),
             "-I", _PRINCIPAL, "-n", _NAMESPACE, "-s", str(signature)],
            input=data_bytes, capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CapabilityPlaneError("EVIDENCE_SIGNATURE_VERIFIER_UNAVAILABLE") from exc
    if result.returncode:
        raise CapabilityPlaneError("EVIDENCE_SIGNATURE_INVALID")
    return VerifiedCapabilityEvidence(
        data=data, proof_sha256=hashlib.sha256(data_bytes).hexdigest()
    )


def describe_capabilities(manifest: Path = _DEFAULT_MANIFEST) -> dict[str, Any]:
    try:
        data = _load_json(Path(manifest).read_bytes())
    except OSError as exc:
        raise CapabilityPlaneError("CAPABILITY_MANIFEST_UNAVAILABLE") from exc
    if not isinstance(data, dict) or data.get("schema") != "HazewaveCapabilityEvidencePlane/v1":
        raise CapabilityPlaneError("CAPABILITY_MANIFEST_INVALID")
    if data.get("authority") != AUTHORITY or data.get("automatic_install") is not False:
        raise CapabilityPlaneError("CAPABILITY_AUTHORITY_INVALID")
    if not isinstance(data.get("tools"), list):
        raise CapabilityPlaneError("CAPABILITY_TOOLS_INVALID")
    current = set(harness_status()["capabilities"])
    seen: set[str] = set()
    for tool in data["tools"]:
        if not isinstance(tool, dict) or tool.get("tool_id") in seen:
            raise CapabilityPlaneError("CAPABILITY_TOOL_DUPLICATE")
        tid = tool.get("tool_id")
        if not isinstance(tid, str) or not _NAME.fullmatch(tid):
            raise CapabilityPlaneError("CAPABILITY_TOOL_INVALID")
        seen.add(tid)
        if tool.get("capability_id") not in current or tool.get("domain") not in {"HAZE", "WAVE"}:
            raise CapabilityPlaneError("CAPABILITY_HARNESS_MAPPING_INVALID")
        if not capability_allows_domain(tool["capability_id"], tool["domain"]):
            raise CapabilityPlaneError("CAPABILITY_HARNESS_DOMAIN_INVALID")
        if tool.get("cost_class") not in {"FREE_OPEN_SOURCE", "UNKNOWN_DENY"}:
            raise CapabilityPlaneError("CAPABILITY_COST_CLASS_INVALID")
        if tool.get("risk_tier") not in {"LOW", "MEDIUM", "HIGH"}:
            raise CapabilityPlaneError("CAPABILITY_RISK_TIER_INVALID")
        if not isinstance(tool.get("executable"), str) or not tool["executable"]:
            raise CapabilityPlaneError("CAPABILITY_EXECUTABLE_INVALID")
    return data


def discover_local_executable(
    executable: str,
    *,
    home: Path | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> str | None:
    """Search only the known, version-pinned first-party installation slots.

    This is executable presence detection, never an automatic doctor or proof.
    """
    base = Path(home or Path.home())
    relative_slots = {
        "iris": (".local/share/hazewave/iris/v0.4.1/bin/iris",),
        "rea": (".local/share/hazewave/reverse-engineering/rea-6.0.0/bin/rea",),
        "scenedetect": (".local/share/hazewave/av-research/av-research-venv/bin/scenedetect",),
    }
    for relative in relative_slots.get(executable, ()):
        candidate = base / relative
        try:
            if candidate.is_file() and os.access(candidate, os.X_OK) and not candidate.is_symlink():
                return str(candidate)
        except OSError:
            pass
    return which(executable)


def _real_binary_sha(path: str) -> str | None:
    try:
        p = Path(path)
        if p.is_symlink():
            # PATH symlinks are normal for executables; resolved bytes are measured.
            p = p.resolve(strict=True)
        if not p.is_file():
            return None
        return _sha_file(p)
    except (OSError, CapabilityPlaneError):
        return None


def inventory(
    *,
    manifest: Path = _DEFAULT_MANIFEST,
    host_id: str,
    repo_sha: str,
    binary_lookup: Callable[[str], str | None] = discover_local_executable,
    binary_fingerprint: Callable[[str], str | None] = _real_binary_sha,
    evidence_files: list[VerifiedCapabilityEvidence] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Enumerate declared Harness capabilities; count **zero** unproven routes.

    Caller-provided verifier objects are advisory in Python; the CLI ingests
    only proofs checked against an owner-controlled public signer truststore.
    """
    if not isinstance(repo_sha, str) or not _SHA.fullmatch(repo_sha):
        raise CapabilityPlaneError("CAPABILITY_REPO_SHA_INVALID")
    if not isinstance(host_id, str) or not host_id.strip():
        raise CapabilityPlaneError("CAPABILITY_HOST_REQUIRED")
    definition = describe_capabilities(manifest)
    official = set(harness_status()["capabilities"])
    measured = list(evidence_files or [])
    tools: dict[str, dict[str, Any]] = {}
    mapped: set[str] = set()
    ready: set[str] = set()
    for item in definition["tools"]:
        tid = item["tool_id"]
        cap = item["capability_id"]
        mapped.add(cap)
        path = binary_lookup(item["executable"])
        available = bool(path)
        fingerprint = binary_fingerprint(str(path)) if available else None
        state = "PRESENT_UNPROVEN" if available else "UNAVAILABLE"
        p: Mapping[str, Any] | None = None
        candidates = [x for x in measured if
                      isinstance(x, VerifiedCapabilityEvidence) and
                      x.source == "OWNER_SIGNED_BYTES_AND_LOCAL_ARTIFACT" and
                      x.data.get("tool_id") == tid and
                      x.data.get("capability_id") == cap and
                      x.data.get("domain") == item["domain"] and
                      x.data.get("version") == item["version"]]
        if candidates and available:
            # Do not promote old CI proof to host readiness or stale branch.
            local = [x for x in candidates if
                     x.data.get("host_id") == host_id and x.data.get("repo_sha") == repo_sha
                     and x.data.get("scope") == "LOCAL_HOST"]
            valid = [x for x in local if x.data.get("binary_sha256") == fingerprint]
            if valid:
                p = valid[-1].data
                if (p.get("stage") == "BENCHMARKED" and p.get("fixture_result") == "PASS"
                        and p.get("tool_list_observed") is True
                        and p.get("tool_call_observed") is True
                        and p["benchmark"]["sample_count"] >= definition["policy"]["minimum_samples"]
                        and item["cost_class"] == "FREE_OPEN_SOURCE"
                        and p["benchmark"]["cost_usd"] == 0):
                    state = "MEASURED_READY"
                    ready.add(cap)
                else:
                    state = "FIXTURE_PROVEN" if p.get("fixture_result") == "PASS" else "EVIDENCE_UNVERIFIED"
            else:
                if any(x.data.get("scope") == "CI_FIXTURE" and x.data.get("fixture_result") == "PASS"
                       for x in candidates):
                    state = "CI_FIXTURE_PROVEN"
                else:
                    state = "STALE"
        # Previously verified objects must expire when reused by a long-lived caller.
        relevant = [x for x in candidates if
                    x.data.get("host_id") == host_id and
                    x.data.get("repo_sha") == repo_sha and
                    x.data.get("scope") == "LOCAL_HOST"]
        clock = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if any(_time(x.data["expires_at"]) <= clock for x in relevant):
            state = "STALE"
            ready.discard(cap)
        tools[tid] = {
            "tool_id": tid,
            "capability_id": cap,
            "domain": item["domain"],
            "state": state,
            "route_eligible": state == "MEASURED_READY",
            "production_approved": False,
            "cost_class": item["cost_class"],
            "risk_tier": item["risk_tier"],
            "source": item["source"],
            "installed_path_observed": available,
            "binary_digest_verified": p is not None and p.get("binary_sha256") == fingerprint,
            "evidence_scope": p.get("scope") if p else None,
            "evidence_version": p.get("version") if p else None,
            "quality_score": p["benchmark"]["quality_score"] if state == "MEASURED_READY" else None,
            "risk_score": p["benchmark"]["risk_score"] if state == "MEASURED_READY" else None,
            "cost_usd": p["benchmark"]["cost_usd"] if state == "MEASURED_READY" else None,
            "p50_latency_ms": p["benchmark"]["p50_latency_ms"] if state == "MEASURED_READY" else None,
            "p95_latency_ms": p["benchmark"]["p95_latency_ms"] if state == "MEASURED_READY" else None,
        }
    count = len(definition["tools"])
    operational = sum(x["route_eligible"] for x in tools.values())
    return {
        "schema": "HazewaveCapabilityCoverageSnapshot/v1",
        "authority": AUTHORITY,
        "host_id": host_id,
        "repo_sha": repo_sha,
        "routing": "ADVISORY_ONLY_NO_EXECUTION_AUTHORIZATION",
        "tools": tools,
        "coverage": {
            "tools_declared": count,
            "tools_present_unproven": sum(x["state"] == "PRESENT_UNPROVEN" for x in tools.values()),
            "ci_fixture_proven": sum(x["state"] == "CI_FIXTURE_PROVEN" for x in tools.values()),
            "operational_ready": operational,
            "ready_percent": round(100 * operational / count, 2) if count else 0.0,
            "total_harness_capabilities": len(official),
            "mapped_harness_capabilities": len(mapped),
            "unmapped_harness_capabilities": len(official - mapped),
            "mapped_percent": round(100 * len(mapped) / len(official), 2),
            "ready_distinct_harness_capabilities": len(ready),
        },
        "owner_approval": "NOT_INFERRED",
        "production_approved": False,
        "limitations": [
            "Installed command presence is not a working analyzer.",
            "A signed owner statement is not independent reproduction of the underlying tool log.",
            "Host-scoped benchmark evidence does not grant executable or production authority.",
        ],
    }


def select_provider(report: Mapping[str, Any], capability: str, domain: str) -> dict[str, Any]:
    if not capability_allows_domain(capability, domain):
        raise CapabilityPlaneError("CAPABILITY_DOMAIN_MISMATCH")
    options = [dict(x) for x in report["tools"].values()
               if x["capability_id"] == capability and x["domain"] == domain
               and x["route_eligible"] and x["cost_class"] == "FREE_OPEN_SOURCE"
               and x["cost_usd"] == 0]
    if not options:
        raise CapabilityPlaneError("NO_OPERATIONALLY_VERIFIED_PROVIDER")
    # Quality/risk from independent signed measurements, not guessed labels.
    # Prefer high observed quality, lower risk, then latency; unknown cost denied.
    ordered = sorted(options, key=lambda v: (
        -v["quality_score"], v["risk_score"], v["p95_latency_ms"], v["tool_id"]
    ))
    result = ordered[0]
    result["selection"] = "ADVISORY_ONLY"
    result["requires_harness_task_authorization"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hazewave.capability_plane")
    parser.add_argument("command", choices=("inventory", "select"))
    parser.add_argument("--host-id", required=True)
    parser.add_argument("--repo-sha", required=True)
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument("--evidence", type=Path, action="append", default=[])
    parser.add_argument("--signer-trust", type=Path)
    parser.add_argument("--capability")
    parser.add_argument("--domain")
    args = parser.parse_args(argv)
    try:
        proofs: list[VerifiedCapabilityEvidence] = []
        if args.evidence:
            if args.signer_trust is None:
                raise CapabilityPlaneError("EVIDENCE_TRUSTSTORE_REQUIRED")
            for path in args.evidence:
                proofs.append(verify_signed_runtime_evidence(
                    path, Path(str(path) + ".sig"), args.signer_trust,
                    artifact=Path(str(path) + ".log")
                ))
        report = inventory(
            manifest=args.manifest, host_id=args.host_id,
            repo_sha=args.repo_sha, evidence_files=proofs,
        )
        output = report if args.command == "inventory" else select_provider(
            report, args.capability or "", args.domain or ""
        )
        print(json.dumps(output, sort_keys=True))
        return 0
    except (CapabilityPlaneError, ValueError, OSError) as exc:
        print(f"HAZEWAVE_CAPABILITY_PLANE=BLOCKED:{exc}", file=sys.stderr)
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
