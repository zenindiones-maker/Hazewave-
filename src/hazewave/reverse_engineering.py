from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any, Final


class ReverseEngineeringError(RuntimeError):
    pass


_ALLOWED_DOMAINS: Final[frozenset[str]] = frozenset({"HAZE", "WAVE", "BRIDGE"})



_SIGNER_IDENTITY = "hazewave-owner"
_SIGNING_NAMESPACE = "hazewave-research-grant"
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_GRANT_SCHEMA = "HazewaveReverseEngineeringTargetGrant/v1"


def _private_file(path: Path, *, trust: bool = False) -> bytes:
    try:
        details = path.lstat()
        if not stat.S_ISREG(details.st_mode) or path.is_symlink():
            raise ReverseEngineeringError("RE_SIGNER_TRUST_FILE_UNSAFE" if trust else "RE_GRANT_FILE_UNSAFE")
        if details.st_uid != os.geteuid() or details.st_mode & 0o077:
            raise ReverseEngineeringError("RE_SIGNER_TRUST_FILE_UNSAFE" if trust else "RE_GRANT_FILE_UNSAFE")
        if details.st_size > 64 * 1024:
            raise ReverseEngineeringError("RE_GRANT_FILE_OVERSIZED")
        return path.read_bytes()
    except OSError as exc:
        raise ReverseEngineeringError("RE_SIGNER_TRUST_FILE_UNSAFE" if trust else "RE_GRANT_FILE_UNSAFE") from exc


def _hash_target(path: Path) -> str:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or path.is_symlink():
            raise ReverseEngineeringError("RE_TARGET_FILE_UNSAFE")
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as exc:
        raise ReverseEngineeringError("RE_TARGET_FILE_UNSAFE") from exc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for key, value in pairs:
        if key in record:
            raise ValueError("duplicate JSON key")
        record[key] = value
    return record


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ReverseEngineeringError("RE_GRANT_TIME_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReverseEngineeringError("RE_GRANT_TIME_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReverseEngineeringError("RE_GRANT_TIME_INVALID")
    return parsed.astimezone(timezone.utc)


def verify_research_grant(
    *,
    grant_file: Path,
    signature_file: Path,
    target_file: Path,
    allowed_signers_file: Path,
    domain: str,
    target_kind: str,
    purpose: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Verify a short-lived owner-signed target grant; no self-authorization flag.

    The trust file must be provisioned by the owner/Harness outside the checkout.
    A CLI caller cannot provide another signers path; a compromised local owner
    account/trust store is outside this process-local authorization boundary.
    """
    grant_bytes = _private_file(Path(grant_file))
    _private_file(Path(signature_file))
    trusted_signers = _private_file(Path(allowed_signers_file), trust=True)
    if not trusted_signers or not any(
        line.startswith((_SIGNER_IDENTITY + " ").encode())
        for line in trusted_signers.splitlines()
    ):
        raise ReverseEngineeringError("RE_SIGNER_TRUST_FILE_UNSAFE")
    try:
        grant = json.loads(grant_bytes.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeError, ValueError) as exc:
        raise ReverseEngineeringError("RE_GRANT_DOCUMENT_INVALID") from exc
    if not isinstance(grant, dict):
        raise ReverseEngineeringError("RE_GRANT_DOCUMENT_INVALID")
    if (grant.get("schema") != _GRANT_SCHEMA
            or grant.get("authority") != "HAZEWAVE_HARNESS"
            or grant.get("issuer") != _SIGNER_IDENTITY
            or not isinstance(grant.get("grant_id"), str)
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", grant["grant_id"])):
        raise ReverseEngineeringError("RE_GRANT_IDENTITY_INVALID")
    if any(grant.get(key) != expected for key, expected in (
        ("domain", domain), ("target_kind", target_kind), ("purpose", purpose)
    )):
        raise ReverseEngineeringError("RE_GRANT_SCOPE_MISMATCH")
    digest = grant.get("target_sha256")
    if not isinstance(digest, str) or not _HEX_64.fullmatch(digest):
        raise ReverseEngineeringError("RE_TARGET_DIGEST_INVALID")
    if digest != _hash_target(Path(target_file)):
        raise ReverseEngineeringError("RE_TARGET_DIGEST_MISMATCH")
    issued = _parse_time(grant.get("issued_at"))
    expires = _parse_time(grant.get("expires_at"))
    clock = now if now is not None else datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ReverseEngineeringError("RE_GRANT_TIME_INVALID")
    clock = clock.astimezone(timezone.utc)
    if (issued > clock + timedelta(minutes=2)
            or expires <= clock
            or expires <= issued
            or expires - issued > timedelta(hours=24)):
        raise ReverseEngineeringError("RE_GRANT_TIME_INVALID")
    try:
        verified = subprocess.run(
            [
                "ssh-keygen", "-Y", "verify",
                "-f", str(allowed_signers_file),
                "-I", _SIGNER_IDENTITY,
                "-n", _SIGNING_NAMESPACE,
                "-s", str(signature_file),
            ],
            input=grant_bytes,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReverseEngineeringError("RE_SIGNER_VERIFICATION_UNAVAILABLE") from exc
    if verified.returncode != 0:
        raise ReverseEngineeringError("RE_GRANT_SIGNATURE_INVALID")
    return {
        "schema": _GRANT_SCHEMA,
        "grant_id": grant["grant_id"],
        "issuer": _SIGNER_IDENTITY,
        "target_sha256": digest,
        "issued_at": issued.isoformat(),
        "expires_at": expires.isoformat(),
        "signature_verified": True,
        "authorization_authority": "OWNER_SIGNED_HARNESS_SCOPE",
    }


@dataclass(frozen=True)
class ReverseEngineeringTool:
    tool_id: str
    name: str
    version: str
    source_repository: str
    license_id: str
    cost_class: str
    roles: tuple[str, ...]
    domains: tuple[str, ...]
    installation_class: str
    grants_execution_authority: bool = False

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "ReverseEngineeringTool":
        required = (
            "tool_id",
            "name",
            "version",
            "source_repository",
            "license_id",
            "cost_class",
            "roles",
            "domains",
            "installation_class",
        )
        missing = [key for key in required if key not in row]
        if missing:
            raise ReverseEngineeringError(
                f"REVERSE_ENGINEERING_TOOL_FIELDS_MISSING:{','.join(missing)}"
            )
        if row.get("grants_execution_authority") is not False:
            raise ReverseEngineeringError(
                f"REVERSE_ENGINEERING_TOOL_AUTHORITY_FORBIDDEN:{row['tool_id']}"
            )
        return cls(
            tool_id=str(row["tool_id"]),
            name=str(row["name"]),
            version=str(row["version"]),
            source_repository=str(row["source_repository"]),
            license_id=str(row["license_id"]),
            cost_class=str(row["cost_class"]),
            roles=tuple(str(x) for x in row["roles"]),
            domains=tuple(str(x) for x in row["domains"]),
            installation_class=str(row["installation_class"]),
            grants_execution_authority=False,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "version": self.version,
            "source_repository": self.source_repository,
            "license_id": self.license_id,
            "cost_class": self.cost_class,
            "roles": list(self.roles),
            "domains": list(self.domains),
            "installation_class": self.installation_class,
            "grants_execution_authority": False,
        }


class ReverseEngineeringFoundation:
    def __init__(self, policy: dict[str, Any]) -> None:
        self._policy = policy
        if policy.get("authority") != "HAZEWAVE_HARNESS":
            raise ReverseEngineeringError("REVERSE_ENGINEERING_AUTHORITY_INVALID")
        if policy.get("grants_execution_authority") is not False:
            raise ReverseEngineeringError(
                "REVERSE_ENGINEERING_EXECUTION_AUTHORITY_FORBIDDEN"
            )
        self._allowed_purposes = frozenset(
            str(x) for x in policy.get("allowed_purposes", [])
        )
        self._forbidden_purposes = frozenset(
            str(x) for x in policy.get("forbidden_purposes", [])
        )
        self._tools: dict[str, ReverseEngineeringTool] = {}
        for row in policy.get("tools", []):
            tool = ReverseEngineeringTool.from_dict(row)
            if tool.tool_id in self._tools:
                raise ReverseEngineeringError(
                    f"REVERSE_ENGINEERING_TOOL_DUPLICATE:{tool.tool_id}"
                )
            self._tools[tool.tool_id] = tool

    @property
    def authority(self) -> str:
        return "HAZEWAVE_HARNESS"

    def _route(self, *, domain: str, target_kind: str) -> list[str]:
        if domain not in _ALLOWED_DOMAINS:
            raise ReverseEngineeringError(
                f"REVERSE_ENGINEERING_DOMAIN_INVALID:{domain}"
            )
        routes = self._policy.get("routes", {})
        domain_routes = routes.get(domain)
        if not isinstance(domain_routes, dict) or target_kind not in domain_routes:
            raise ReverseEngineeringError(
                f"REVERSE_ENGINEERING_ROUTE_UNDEFINED:{domain}:{target_kind}"
            )
        tools = [str(x) for x in domain_routes[target_kind]]
        unknown = [tool_id for tool_id in tools if tool_id not in self._tools]
        if unknown:
            raise ReverseEngineeringError(
                f"REVERSE_ENGINEERING_ROUTE_TOOL_UNKNOWN:{','.join(unknown)}"
            )
        for tool_id in tools:
            if domain not in self._tools[tool_id].domains:
                raise ReverseEngineeringError(
                    f"REVERSE_ENGINEERING_ROUTE_DOMAIN_MISMATCH:{tool_id}:{domain}"
                )
        return tools

    def plan(
        self,
        *,
        domain: str,
        target_kind: str,
        purpose: str,
        target_file: Path | None = None,
        grant_file: Path | None = None,
        signature_file: Path | None = None,
        trusted_signers_file: Path | None = None,
        authorized: bool = False,
    ) -> dict[str, Any]:
        # A user-supplied --authorized/authorized=True assertion is not a grant.
        if authorized:
            raise ReverseEngineeringError("REVERSE_ENGINEERING_LEGACY_BOOLEAN_UNTRUSTED")
        purpose = str(purpose)
        if purpose in self._forbidden_purposes:
            raise ReverseEngineeringError(
                f"REVERSE_ENGINEERING_PURPOSE_FORBIDDEN:{purpose}"
            )
        if purpose not in self._allowed_purposes:
            raise ReverseEngineeringError(
                f"REVERSE_ENGINEERING_PURPOSE_UNRECOGNIZED:{purpose}"
            )

        if not all((target_file, grant_file, signature_file, trusted_signers_file)):
            raise ReverseEngineeringError("REVERSE_ENGINEERING_TARGET_AUTHORIZATION_REQUIRED")
        evidence_grant = verify_research_grant(
            grant_file=Path(grant_file),
            signature_file=Path(signature_file),
            target_file=Path(target_file),
            allowed_signers_file=Path(trusted_signers_file),
            domain=domain,
            target_kind=target_kind,
            purpose=purpose,
        )
        tools = self._route(domain=domain, target_kind=target_kind)
        evidence = self._policy.get("evidence", {})
        required_evidence = [
            str(x) for x in evidence.get("allowed_claims", [])
        ]
        return {
            "schema": "HazewaveReverseEngineeringPlan/v1",
            "authority": self.authority,
            "domain": domain,
            "domain_authority": str(
                self._policy.get("domain_authority", {}).get(domain, "NONE")
            ),
            "target_kind": target_kind,
            "purpose": purpose,
            "authorized_target": True,
            "authorization_evidence": evidence_grant,
            "tools": tools,
            "required_evidence": required_evidence,
            "source_recovery_claim": evidence.get(
                "source_recovery_claim", "FORBIDDEN"
            ),
            "grants_execution_authority": False,
            "production_approved": False,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": self._policy.get("schema"),
            "policy_id": self._policy.get("policy_id"),
            "authority": self.authority,
            "grants_execution_authority": False,
            "tools": [
                self._tools[tool_id].to_dict()
                for tool_id in sorted(self._tools)
            ],
            "allowed_purposes": sorted(self._allowed_purposes),
            "forbidden_purposes": sorted(self._forbidden_purposes),
            "evidence": dict(self._policy.get("evidence", {})),
        }


def load_default_foundation(path: Path | str) -> ReverseEngineeringFoundation:
    policy_path = Path(path)
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReverseEngineeringError(
            f"REVERSE_ENGINEERING_POLICY_LOAD_FAILED:{policy_path}"
        ) from exc
    if payload.get("schema") != "HazewaveReverseEngineeringFoundation/v1":
        raise ReverseEngineeringError("REVERSE_ENGINEERING_POLICY_SCHEMA_INVALID")
    return ReverseEngineeringFoundation(payload)
