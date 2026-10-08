from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Final


class ReverseEngineeringError(RuntimeError):
    pass


_ALLOWED_DOMAINS: Final[frozenset[str]] = frozenset({"HAZE", "WAVE", "BRIDGE"})


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
        authorized: bool,
        purpose: str,
    ) -> dict[str, Any]:
        if not authorized:
            raise ReverseEngineeringError(
                "REVERSE_ENGINEERING_TARGET_AUTHORIZATION_REQUIRED"
            )
        purpose = str(purpose)
        if purpose in self._forbidden_purposes:
            raise ReverseEngineeringError(
                f"REVERSE_ENGINEERING_PURPOSE_FORBIDDEN:{purpose}"
            )
        if purpose not in self._allowed_purposes:
            raise ReverseEngineeringError(
                f"REVERSE_ENGINEERING_PURPOSE_UNRECOGNIZED:{purpose}"
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
