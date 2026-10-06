from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Any, ClassVar, Mapping, Sequence


class KnowledgeKind(str, Enum):
    FACT = "FACT"
    STANDARD = "STANDARD"
    TOOL_CAPABILITY = "TOOL_CAPABILITY"
    COMPATIBILITY_EVIDENCE = "COMPATIBILITY_EVIDENCE"
    EXPERIMENTAL_EVIDENCE = "EXPERIMENTAL_EVIDENCE"
    CREATIVE_HEURISTIC = "CREATIVE_HEURISTIC"
    HUMAN_PREFERENCE = "HUMAN_PREFERENCE"


class KnowledgeValidationStatus(str, Enum):
    UNVALIDATED = "UNVALIDATED"
    SOURCE_VERIFIED = "SOURCE_VERIFIED"
    RUNTIME_PROVEN = "RUNTIME_PROVEN"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class KnowledgeEvidence:
    source: str
    source_type: str
    retrieved_at: datetime
    version: str
    platform: str
    architecture: str
    license_or_cost_class: str
    confidence: float
    freshness_days: int
    validation_status: KnowledgeValidationStatus
    schema: ClassVar[str] = "KnowledgeEvidence/v1"

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("KNOWLEDGE_SOURCE_REQUIRED")
        if not self.source_type.strip():
            raise ValueError("KNOWLEDGE_SOURCE_TYPE_REQUIRED")
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("KNOWLEDGE_RETRIEVED_AT_TIMEZONE_REQUIRED")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("KNOWLEDGE_CONFIDENCE_INVALID")
        if not isinstance(self.freshness_days, int) or self.freshness_days < 1:
            raise ValueError("KNOWLEDGE_FRESHNESS_INVALID")
        for name in (
            "version",
            "platform",
            "architecture",
            "license_or_cost_class",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"KNOWLEDGE_EVIDENCE_FIELD_REQUIRED:{name}")

    @property
    def runtime_proven(self) -> bool:
        return self.validation_status == KnowledgeValidationStatus.RUNTIME_PROVEN

    def with_confidence(self, confidence: float) -> "KnowledgeEvidence":
        if not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("KNOWLEDGE_CONFIDENCE_INVALID")
        return replace(self, confidence=float(confidence))

    def is_stale(self, *, as_of: datetime) -> bool:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("KNOWLEDGE_AS_OF_TIMEZONE_REQUIRED")
        retrieved = self.retrieved_at.astimezone(timezone.utc)
        current = as_of.astimezone(timezone.utc)
        return current > retrieved + timedelta(days=self.freshness_days)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "source": self.source,
            "source_type": self.source_type,
            "retrieved_at": self.retrieved_at.astimezone(timezone.utc).isoformat(),
            "version": self.version,
            "platform": self.platform,
            "architecture": self.architecture,
            "license_or_cost_class": self.license_or_cost_class,
            "confidence": self.confidence,
            "freshness_days": self.freshness_days,
            "validation_status": self.validation_status.value,
            "runtime_proven": self.runtime_proven,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "KnowledgeEvidence":
        required = {
            "source",
            "source_type",
            "retrieved_at",
            "version",
            "platform",
            "architecture",
            "license_or_cost_class",
            "confidence",
            "freshness_days",
            "validation_status",
        }
        if not isinstance(payload, Mapping) or required.difference(payload):
            raise ValueError("KNOWLEDGE_EVIDENCE_MALFORMED")
        try:
            retrieved_at = datetime.fromisoformat(str(payload["retrieved_at"]))
            status = KnowledgeValidationStatus(str(payload["validation_status"]))
            confidence = float(payload["confidence"])
            freshness_days = int(payload["freshness_days"])
        except (TypeError, ValueError) as exc:
            raise ValueError("KNOWLEDGE_EVIDENCE_MALFORMED") from exc
        return cls(
            source=str(payload["source"]),
            source_type=str(payload["source_type"]),
            retrieved_at=retrieved_at,
            version=str(payload["version"]),
            platform=str(payload["platform"]),
            architecture=str(payload["architecture"]),
            license_or_cost_class=str(payload["license_or_cost_class"]),
            confidence=confidence,
            freshness_days=freshness_days,
            validation_status=status,
        )


@dataclass(frozen=True)
class BaseKnowledge:
    knowledge_id: str
    title: str
    kind: KnowledgeKind
    evidence: tuple[KnowledgeEvidence, ...]
    schema: ClassVar[str] = "KnowledgeEvidenceBase/v1"

    def __post_init__(self) -> None:
        if not self.knowledge_id.strip():
            raise ValueError("KNOWLEDGE_ID_REQUIRED")
        if not self.title.strip():
            raise ValueError("KNOWLEDGE_TITLE_REQUIRED")
        if not self.evidence:
            raise ValueError("KNOWLEDGE_EVIDENCE_REQUIRED")
        if not all(isinstance(item, KnowledgeEvidence) for item in self.evidence):
            raise ValueError("KNOWLEDGE_EVIDENCE_MALFORMED")

    def _specific_payload(self) -> dict[str, Any]:
        base_names = {"knowledge_id", "title", "kind", "evidence"}
        result: dict[str, Any] = {}
        for item in fields(self):
            if item.name in base_names:
                continue
            value = getattr(self, item.name)
            if isinstance(value, tuple):
                value = list(value)
            result[item.name] = value
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "knowledge_id": self.knowledge_id,
            "title": self.title,
            "kind": self.kind.value,
            "evidence": [item.to_dict() for item in self.evidence],
            **self._specific_payload(),
        }


@dataclass(frozen=True)
class ToolKnowledge(BaseKnowledge):
    tool_id: str
    tool_version: str
    capabilities: tuple[str, ...]
    schema: ClassVar[str] = "ToolKnowledge/v1"

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.tool_id.strip() or not self.tool_version.strip():
            raise ValueError("TOOL_KNOWLEDGE_IDENTITY_REQUIRED")
        if not self.capabilities:
            raise ValueError("TOOL_KNOWLEDGE_CAPABILITIES_REQUIRED")


@dataclass(frozen=True)
class PluginKnowledge(BaseKnowledge):
    plugin_id: str
    plugin_version: str
    semantic_roles: tuple[str, ...]
    schema: ClassVar[str] = "PluginKnowledge/v1"

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.plugin_id.strip() or not self.plugin_version.strip():
            raise ValueError("PLUGIN_KNOWLEDGE_IDENTITY_REQUIRED")
        if not self.semantic_roles:
            raise ValueError("PLUGIN_KNOWLEDGE_ROLES_REQUIRED")


@dataclass(frozen=True)
class TechniqueKnowledge(BaseKnowledge):
    domain: str
    technique: str
    schema: ClassVar[str] = "TechniqueKnowledge/v1"

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.domain not in {"HAZE", "WAVE", "BRIDGE"}:
            raise ValueError("TECHNIQUE_KNOWLEDGE_DOMAIN_INVALID")
        if not self.technique.strip():
            raise ValueError("TECHNIQUE_KNOWLEDGE_NAME_REQUIRED")


@dataclass(frozen=True)
class StyleKnowledge(BaseKnowledge):
    domain: str
    style_id: str
    schema: ClassVar[str] = "StyleKnowledge/v1"

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.domain not in {"HAZE", "WAVE", "BRIDGE"}:
            raise ValueError("STYLE_KNOWLEDGE_DOMAIN_INVALID")
        if not self.style_id.strip():
            raise ValueError("STYLE_KNOWLEDGE_ID_REQUIRED")


_ENTRY_TYPES: dict[str, type[BaseKnowledge]] = {
    ToolKnowledge.schema: ToolKnowledge,
    PluginKnowledge.schema: PluginKnowledge,
    TechniqueKnowledge.schema: TechniqueKnowledge,
    StyleKnowledge.schema: StyleKnowledge,
}


class ProfessionalKnowledgeRegistry:
    schema = "ProfessionalKnowledgeRegistry/v1"
    authority = "NONE"
    grants_execution_authority = False

    def __init__(self, entries: Sequence[BaseKnowledge] = ()) -> None:
        self._entries: dict[str, BaseKnowledge] = {}
        for entry in entries:
            self.register(entry)

    @property
    def entries(self) -> tuple[BaseKnowledge, ...]:
        return tuple(self._entries[key] for key in sorted(self._entries))

    def register(self, entry: BaseKnowledge) -> None:
        if not isinstance(entry, BaseKnowledge):
            raise TypeError("KNOWLEDGE_ENTRY_TYPE_INVALID")
        current = self._entries.get(entry.knowledge_id)
        if current is not None and current != entry:
            raise ValueError("KNOWLEDGE_ID_CONFLICT")
        self._entries[entry.knowledge_id] = entry

    def get(self, knowledge_id: str) -> BaseKnowledge:
        try:
            return self._entries[knowledge_id]
        except KeyError as exc:
            raise KeyError(f"KNOWLEDGE_NOT_FOUND:{knowledge_id}") from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "authority": self.authority,
            "grants_execution_authority": self.grants_execution_authority,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @staticmethod
    def _entry_from_dict(payload: Mapping[str, Any]) -> BaseKnowledge:
        if not isinstance(payload, Mapping):
            raise ValueError("KNOWLEDGE_ENTRY_MALFORMED")
        schema = str(payload.get("schema") or "")
        entry_type = _ENTRY_TYPES.get(schema)
        if entry_type is None:
            raise ValueError(f"KNOWLEDGE_ENTRY_SCHEMA_UNSUPPORTED:{schema}")
        raw_evidence = payload.get("evidence")
        if not isinstance(raw_evidence, list) or not raw_evidence:
            raise ValueError("KNOWLEDGE_EVIDENCE_REQUIRED")
        evidence = tuple(KnowledgeEvidence.from_dict(item) for item in raw_evidence)
        try:
            common = {
                "knowledge_id": str(payload["knowledge_id"]),
                "title": str(payload["title"]),
                "kind": KnowledgeKind(str(payload["kind"])),
                "evidence": evidence,
            }
            if entry_type is ToolKnowledge:
                return ToolKnowledge(
                    **common,
                    tool_id=str(payload["tool_id"]),
                    tool_version=str(payload["tool_version"]),
                    capabilities=tuple(str(x) for x in payload["capabilities"]),
                )
            if entry_type is PluginKnowledge:
                return PluginKnowledge(
                    **common,
                    plugin_id=str(payload["plugin_id"]),
                    plugin_version=str(payload["plugin_version"]),
                    semantic_roles=tuple(str(x) for x in payload["semantic_roles"]),
                )
            if entry_type is TechniqueKnowledge:
                return TechniqueKnowledge(
                    **common,
                    domain=str(payload["domain"]),
                    technique=str(payload["technique"]),
                )
            if entry_type is StyleKnowledge:
                return StyleKnowledge(
                    **common,
                    domain=str(payload["domain"]),
                    style_id=str(payload["style_id"]),
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("KNOWLEDGE_ENTRY_MALFORMED") from exc
        raise AssertionError("unreachable")

    @classmethod
    def load(cls, path: Path | str) -> "ProfessionalKnowledgeRegistry":
        source = Path(path)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValueError("KNOWLEDGE_REGISTRY_NOT_FOUND") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("KNOWLEDGE_REGISTRY_MALFORMED") from exc
        if not isinstance(payload, dict):
            raise ValueError("KNOWLEDGE_REGISTRY_MALFORMED")
        if payload.get("schema") != cls.schema:
            raise ValueError("KNOWLEDGE_REGISTRY_SCHEMA_INVALID")
        if payload.get("authority") != "NONE":
            raise ValueError("KNOWLEDGE_REGISTRY_AUTHORITY_INVALID")
        if payload.get("grants_execution_authority") is not False:
            raise ValueError("KNOWLEDGE_REGISTRY_AUTHORITY_INVALID")
        raw_entries = payload.get("entries")
        if not isinstance(raw_entries, list):
            raise ValueError("KNOWLEDGE_REGISTRY_MALFORMED")
        return cls(cls._entry_from_dict(item) for item in raw_entries)
