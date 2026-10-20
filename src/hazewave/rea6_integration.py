"""Fail-closed REA 6.0.0 interface contracts under HAZEWAVE_HARNESS.

This module does not start REA, register an MCP server, mutate agent configuration,
approve targets or activate tools. It validates caller-supplied Evidence from the
official provider-neutral schema and refuses version/provider/path drift.
"""
from __future__ import annotations

from collections.abc import Mapping
import re
from pathlib import Path
from typing import Any


class Rea6ContractError(ValueError):
    pass


REA_VERSION = "6.0.0"
REA_NPM_PACKAGE = "rea-agents@6.0.0"
PROVIDER = "ghidra"
_EVIDENCE_ID = re.compile(r"^ev_[a-f0-9]{64}$")
_HEX_SHA256 = re.compile(r"^[a-f0-9]{64}$")
# REA 6.0.0 changed all filesystem MCP input arguments to absolute paths.
# This list covers the explicitly admitted native/agent research commands.
_PATH_FIELDS = frozenset({
    "path", "target_path", "snapshot_path", "bundle_path",
    "evidence_path", "output_path", "expected_server_path",
    "application_path", "script_path", "input_path",
})


def audited_capability(domain: str) -> str:
    """Never issue autonomous bridge or cross-domain research authority."""
    if domain == "HAZE":
        return "research.audio.inspect"
    if domain == "WAVE":
        return "research.visual.inspect"
    raise Rea6ContractError(f"REA6_DOMAIN_NOT_ADMITTED:{domain}")


def require_absolute_mcp_paths(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate native MCP inputs *before* dispatch to a version-pinned REA.

    Reject invalid paths (including empty, relative, NUL and malformed nested
    fields), and disable non-FOSS/implicit provider selection. Path validation
    does not imply that the caller owns the target or can execute a tool.
    """
    if not isinstance(payload, Mapping):
        raise Rea6ContractError("REA6_MCP_ARGUMENTS_INVALID")

    def scan(obj: Any) -> None:
        if isinstance(obj, Mapping):
            for key, value in obj.items():
                if key in _PATH_FIELDS and value is not None:
                    if (
                        not isinstance(value, str)
                        or not value
                        or "\x00" in value
                        or not Path(value).is_absolute()
                    ):
                        raise Rea6ContractError(f"REA6_ABSOLUTE_PATH_REQUIRED:{key}")
                if key == "provider_id" and value != PROVIDER:
                    raise Rea6ContractError(f"REA6_PROVIDER_FORBIDDEN:{value}")
                scan(value)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                scan(item)

    scan(payload)
    return dict(payload)


def inspect_ghidra_evidence(
    evidence: Mapping[str, Any], *, expected_sha256: str
) -> dict[str, Any]:
    """Validate one *direct* Ghidra native Evidence observation.

    Upstream contract is src/domain/evidence.ts at tag rea-agents-6.0.0.
    This is narrower than a generic workflow overview: derived summaries,
    empty observations, non-native targets and target-free Evidence cannot
    establish direct native-analysis proof. Verifying the envelope does not
    prove the provider really executed; that still requires host attestation.
    """
    if not _HEX_SHA256.fullmatch(expected_sha256):
        raise Rea6ContractError("REA6_EXPECTED_DIGEST_INVALID")
    if not isinstance(evidence, Mapping):
        raise Rea6ContractError("REA6_EVIDENCE_INVALID")
    eid = evidence.get("evidence_id")
    if not isinstance(eid, str) or not _EVIDENCE_ID.fullmatch(eid):
        raise Rea6ContractError("REA6_EVIDENCE_ID_INVALID")
    subject = evidence.get("subject")
    if not isinstance(subject, Mapping):
        raise Rea6ContractError("REA6_SUBJECT_MISSING")
    digest_record = subject.get("digest")
    if not isinstance(digest_record, Mapping):
        raise Rea6ContractError("REA6_SUBJECT_DIGEST_MISSING")
    observed = digest_record.get("sha256")
    if observed != expected_sha256:
        raise Rea6ContractError("REA6_TARGET_DIGEST_MISMATCH")
    if subject.get("format") not in {"elf", "pe", "mach-o"}:
        raise Rea6ContractError("REA6_NATIVE_TARGET_FORMAT_INVALID")
    local_path = subject.get("local_path")
    if not isinstance(local_path, str) or not Path(local_path).is_absolute():
        raise Rea6ContractError("REA6_ABSOLUTE_PATH_REQUIRED:subject.local_path")
    provider = evidence.get("provider")
    if not isinstance(provider, Mapping) or provider.get("id") != PROVIDER:
        raise Rea6ContractError("REA6_NATIVE_PROVIDER_NOT_GHIDRA")
    if not isinstance(provider.get("name"), str) or not provider["name"].strip():
        raise Rea6ContractError("REA6_PROVIDER_IDENTITY_MISSING")
    if evidence.get("confidence") != "observed" or evidence.get("authority") != "shipped-artifact":
        raise Rea6ContractError("REA6_NATIVE_OBSERVATION_NOT_PROVEN")
    if not isinstance(evidence.get("operation"), str) or not evidence["operation"]:
        raise Rea6ContractError("REA6_NATIVE_OPERATION_MISSING")
    result = evidence.get("normalized_result")
    if not isinstance(result, (dict, list, str)) or not result:
        raise Rea6ContractError("REA6_NATIVE_OBSERVATION_EMPTY")
    locations = evidence.get("locations")
    if not isinstance(locations, list):
        raise Rea6ContractError("REA6_LOCATIONS_MISSING")
    # Official REA Evidence schema permits an empty locations array.
    # For the specific native analyze_function operation, the result's
    # structured procedure entry and disassembly carry exact address identity.
    # Other operations continue to require explicit Evidence locations.
    if not locations:
        if evidence.get("operation") != "analyze_function" or not isinstance(result, dict):
            raise Rea6ContractError("REA6_LOCATIONS_MISSING")
        proc = result.get("procedure")
        if (not isinstance(proc, Mapping)
                or not isinstance(proc.get("address"), str)
                or not re.fullmatch(r"0x[0-9a-fA-F]+", proc["address"])
                or not isinstance(proc.get("name"), str)
                or not proc["name"].strip()
                or not isinstance(result.get("assembly"), list)
                or not result["assembly"]
                or any(not isinstance(line, str) or not line.strip()
                       for line in result["assembly"])):
            raise Rea6ContractError("REA6_FUNCTION_DOSSIER_INCOMPLETE")
    limitations = evidence.get("limitations")
    if not isinstance(limitations, list) or any(not isinstance(x, str) for x in limitations):
        raise Rea6ContractError("REA6_LIMITATIONS_MISSING")
    return {
        "schema": "HazewaveRea6GhidraEvidenceAudit/v1",
        "state": "EVIDENCE_VALIDATED",
        "evidence_id": eid,
        "target_sha256": observed,
        "provider_id": PROVIDER,
        "operation": evidence["operation"],
        "limitations": list(limitations),
        "grants_execution_authority": False,
        "production_approved": False,
        "runtime_proven": False,
        "notes": "Shape and digest validated; live provider execution not attested.",
    }


def main(argv: list[str] | None = None) -> int:
    """CLI verifier for recorded, source-owned Ghidra fixture Evidence only.

    Arbitrary target studies must follow the independent signed-grant pathway.
    No provider process is launched and no external agent is registered here.
    """
    import argparse
    import hashlib
    import json
    import stat
    import sys

    parser = argparse.ArgumentParser(prog="python -m hazewave.rea6_integration")
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify-evidence")
    verify.add_argument("--target", type=Path, required=True)
    verify.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        for path in (args.target, args.evidence):
            if not path.is_absolute() or path.is_symlink():
                raise Rea6ContractError("REA6_ABSOLUTE_REGULAR_FILE_REQUIRED")
            if not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode):
                raise Rea6ContractError("REA6_ABSOLUTE_REGULAR_FILE_REQUIRED")
        if args.evidence.stat().st_size > 4 * 1024 * 1024:
            raise Rea6ContractError("REA6_EVIDENCE_SIZE_LIMIT")
        target_sha = hashlib.sha256(args.target.read_bytes()).hexdigest()
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        receipt = inspect_ghidra_evidence(evidence, expected_sha256=target_sha)
        # The verifier cannot authenticate process identity; runtime proof
        # requires separately bound provider execution evidence.
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        print("REA6_EVIDENCE_SHAPE=PASS")
        return 0
    except (Rea6ContractError, OSError, ValueError, TypeError) as exc:
        print(f"REA6_EVIDENCE_SHAPE=BLOCKED:{type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
