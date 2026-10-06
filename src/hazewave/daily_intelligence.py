from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Iterable, Mapping


_ALLOWED_DOMAINS = frozenset({"HAZE", "WAVE", "BRIDGE"})
_CYCLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class SourceTier(str, Enum):
    A_AUTHORITATIVE = "A_AUTHORITATIVE"
    B_PROFESSIONAL = "B_PROFESSIONAL"
    C_DISCOVERY = "C_DISCOVERY"
    D_UNTRUSTED_DISCOVERY = "D_UNTRUSTED_DISCOVERY"


@dataclass(frozen=True)
class DailySource:
    source_id: str
    url: str
    domains: tuple[str, ...]
    tier: SourceTier
    source_kind: str
    data_classification: str = "PUBLIC"
    enabled: bool = True
    schema: str = "DailyIntelligenceSource/v1"

    def __post_init__(self) -> None:
        if not str(self.source_id or "").strip():
            raise ValueError("DAILY_INTELLIGENCE_SOURCE_ID_REQUIRED")
        if not str(self.url or "").startswith("https://"):
            raise ValueError("DAILY_INTELLIGENCE_SOURCE_URL_INVALID")
        if not self.domains or any(domain not in _ALLOWED_DOMAINS for domain in self.domains):
            raise ValueError("DAILY_INTELLIGENCE_SOURCE_DOMAIN_INVALID")
        if not str(self.source_kind or "").strip():
            raise ValueError("DAILY_INTELLIGENCE_SOURCE_KIND_REQUIRED")
        if self.data_classification != "PUBLIC":
            raise ValueError("DAILY_INTELLIGENCE_SOURCE_MUST_BE_PUBLIC")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["tier"] = self.tier.value
        value["domains"] = list(self.domains)
        return value


@dataclass(frozen=True)
class FetchedSource:
    body: bytes
    etag: str | None = None
    last_modified: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.body, bytes) or not self.body:
            raise ValueError("DAILY_INTELLIGENCE_SOURCE_BODY_INVALID")


@dataclass(frozen=True)
class ProposedFinding:
    knowledge_key: str
    domain: str
    claim: str
    confidence: float

    def __post_init__(self) -> None:
        if not str(self.knowledge_key or "").strip():
            raise ValueError("DAILY_INTELLIGENCE_FINDING_KEY_REQUIRED")
        if self.domain not in _ALLOWED_DOMAINS:
            raise ValueError("DAILY_INTELLIGENCE_FINDING_DOMAIN_INVALID")
        if not str(self.claim or "").strip():
            raise ValueError("DAILY_INTELLIGENCE_FINDING_CLAIM_REQUIRED")
        try:
            confidence = float(self.confidence)
        except (TypeError, ValueError) as exc:
            raise ValueError("DAILY_INTELLIGENCE_FINDING_CONFIDENCE_INVALID") from exc
        if confidence < 0.0 or confidence > 1.0:
            raise ValueError("DAILY_INTELLIGENCE_FINDING_CONFIDENCE_INVALID")


@dataclass(frozen=True)
class DailyIntelligenceReceipt:
    cycle_id: str
    observed_at: str
    status: str
    source_count: int
    changed_source_count: int
    unchanged_source_count: int
    finding_count: int
    superseded_record_count: int
    error_count: int
    errors: tuple[str, ...]
    source_digests: Mapping[str, str]
    receipt_path: str
    authority: str = "HAZEWAVE_HARNESS"
    knowledge_authority: str = "KNOWLEDGE_ONLY"
    grants_execution_authority: bool = False
    runtime_mutation_authority: bool = False
    auto_install: bool = False
    auto_upgrade: bool = False
    schema: str = "DailyIntelligenceReceipt/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["errors"] = list(self.errors)
        value["source_digests"] = dict(self.source_digests)
        return value


Fetcher = Callable[[DailySource], FetchedSource]
Analyzer = Callable[[DailySource, bytes, str], Iterable[ProposedFinding]]


def _sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_name = handle.name
            json.dump(
                dict(payload),
                handle,
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if tmp_name is not None and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _load_json(path: Path, *, schema: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"DAILY_INTELLIGENCE_STATE_MALFORMED:{path.name}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != schema:
        raise ValueError(f"DAILY_INTELLIGENCE_STATE_SCHEMA_INVALID:{path.name}")
    return payload


def load_source_registry(path: Path | str) -> dict[str, Any]:
    source_path = Path(path)
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("DAILY_INTELLIGENCE_SOURCE_REGISTRY_MALFORMED") from exc

    if not isinstance(payload, dict) or payload.get("schema") != "DailyIntelligenceSourceRegistry/v1":
        raise ValueError("DAILY_INTELLIGENCE_SOURCE_REGISTRY_SCHEMA_INVALID")
    if payload.get("project_id") != "HAZEWAVE":
        raise ValueError("DAILY_INTELLIGENCE_SOURCE_REGISTRY_PROJECT_INVALID")
    if payload.get("authority") != "HAZEWAVE_HARNESS":
        raise ValueError("DAILY_INTELLIGENCE_SOURCE_REGISTRY_AUTHORITY_INVALID")
    if payload.get("knowledge_authority") != "KNOWLEDGE_ONLY":
        raise ValueError("DAILY_INTELLIGENCE_SOURCE_REGISTRY_KNOWLEDGE_AUTHORITY_INVALID")
    if payload.get("cadence") != "DAILY":
        raise ValueError("DAILY_INTELLIGENCE_SOURCE_REGISTRY_CADENCE_INVALID")
    if payload.get("runtime_mutation_authority") is not False:
        raise ValueError("DAILY_INTELLIGENCE_RUNTIME_MUTATION_MUST_BE_FALSE")

    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError("DAILY_INTELLIGENCE_SOURCE_REGISTRY_MALFORMED")

    sources: list[DailySource] = []
    seen: set[str] = set()
    for raw in raw_sources:
        if not isinstance(raw, dict):
            raise ValueError("DAILY_INTELLIGENCE_SOURCE_REGISTRY_MALFORMED")
        try:
            source = DailySource(
                source_id=str(raw["source_id"]),
                url=str(raw["url"]),
                domains=tuple(str(value) for value in raw["domains"]),
                tier=SourceTier(str(raw["tier"])),
                source_kind=str(raw["source_kind"]),
                data_classification=str(raw.get("data_classification") or "PUBLIC"),
                enabled=bool(raw.get("enabled", True)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith("DAILY_INTELLIGENCE_"):
                raise
            raise ValueError("DAILY_INTELLIGENCE_SOURCE_REGISTRY_MALFORMED") from exc
        if source.source_id in seen:
            raise ValueError("DAILY_INTELLIGENCE_DUPLICATE_SOURCE_ID")
        seen.add(source.source_id)
        sources.append(source)

    return {
        "schema": payload["schema"],
        "project_id": payload["project_id"],
        "authority": payload["authority"],
        "knowledge_authority": payload["knowledge_authority"],
        "cadence": payload["cadence"],
        "runtime_mutation_authority": payload["runtime_mutation_authority"],
        "auto_install": bool(payload.get("auto_install", False)),
        "auto_upgrade": bool(payload.get("auto_upgrade", False)),
        "sources": tuple(sources),
    }


class DailyIntelligenceEngine:
    SOURCE_STATE_SCHEMA = "DailyIntelligenceSourceState/v1"
    KNOWLEDGE_SCHEMA = "DailyKnowledgeRegistry/v1"

    def __init__(
        self,
        *,
        state_root: Path | str,
        sources: Iterable[DailySource],
        fetcher: Fetcher,
        analyzer: Analyzer,
    ) -> None:
        self.state_root = Path(state_root).expanduser().resolve()
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.receipts_root = self.state_root / "receipts"
        self.source_state_path = self.state_root / "source-state-v1.json"
        self.knowledge_path = self.state_root / "knowledge-registry-v1.json"
        self.sources = tuple(source for source in sources if source.enabled)
        self.fetcher = fetcher
        self.analyzer = analyzer

        ids = [source.source_id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("DAILY_INTELLIGENCE_DUPLICATE_SOURCE_ID")

        self._source_state: dict[str, dict[str, Any]] = {}
        self._records: list[dict[str, Any]] = []
        self._load_state()

    def _load_state(self) -> None:
        if self.source_state_path.exists():
            payload = _load_json(
                self.source_state_path,
                schema=self.SOURCE_STATE_SCHEMA,
            )
            raw = payload.get("sources")
            if not isinstance(raw, dict):
                raise ValueError("DAILY_INTELLIGENCE_SOURCE_STATE_MALFORMED")
            for source_id, value in raw.items():
                if not isinstance(source_id, str) or not isinstance(value, dict):
                    raise ValueError("DAILY_INTELLIGENCE_SOURCE_STATE_MALFORMED")
            self._source_state = {str(key): dict(value) for key, value in raw.items()}

        if self.knowledge_path.exists():
            payload = _load_json(
                self.knowledge_path,
                schema=self.KNOWLEDGE_SCHEMA,
            )
            if payload.get("authority") != "KNOWLEDGE_ONLY":
                raise ValueError("DAILY_INTELLIGENCE_KNOWLEDGE_AUTHORITY_INVALID")
            if payload.get("grants_execution_authority") is not False:
                raise ValueError("DAILY_INTELLIGENCE_KNOWLEDGE_AUTHORITY_INVALID")
            raw_records = payload.get("records")
            if not isinstance(raw_records, list) or any(
                not isinstance(item, dict) for item in raw_records
            ):
                raise ValueError("DAILY_INTELLIGENCE_KNOWLEDGE_REGISTRY_MALFORMED")
            self._records = [dict(item) for item in raw_records]

    def _write_state(self) -> None:
        _atomic_write_json(
            self.source_state_path,
            {
                "schema": self.SOURCE_STATE_SCHEMA,
                "project_id": "HAZEWAVE",
                "authority": "KNOWLEDGE_ONLY",
                "grants_execution_authority": False,
                "sources": self._source_state,
            },
        )
        _atomic_write_json(self.knowledge_path, self.registry_snapshot())

    def registry_snapshot(self) -> dict[str, Any]:
        return {
            "schema": self.KNOWLEDGE_SCHEMA,
            "project_id": "HAZEWAVE",
            "authority": "KNOWLEDGE_ONLY",
            "project_authority": "HAZEWAVE_HARNESS",
            "grants_execution_authority": False,
            "runtime_mutation_authority": False,
            "records": [dict(item) for item in self._records],
        }

    def _validate_findings(
        self,
        *,
        source: DailySource,
        findings: Iterable[ProposedFinding],
    ) -> tuple[ProposedFinding, ...]:
        materialized = tuple(findings)
        keys: set[tuple[str, str]] = set()
        for finding in materialized:
            if not isinstance(finding, ProposedFinding):
                raise ValueError("DAILY_INTELLIGENCE_FINDING_TYPE_INVALID")
            if finding.domain not in source.domains:
                raise ValueError(
                    f"FINDING_DOMAIN_NOT_ALLOWED:{source.source_id}:{finding.domain}"
                )
            identity = (finding.domain, finding.knowledge_key)
            if identity in keys:
                raise ValueError(
                    f"DAILY_INTELLIGENCE_DUPLICATE_FINDING_KEY:{finding.domain}:{finding.knowledge_key}"
                )
            keys.add(identity)
        return materialized

    def _record_findings(
        self,
        *,
        source: DailySource,
        source_digest: str,
        findings: tuple[ProposedFinding, ...],
        observed_at: str,
    ) -> tuple[int, int]:
        finding_count = 0
        superseded_count = 0
        new_status = (
            "VERIFIED"
            if source.tier in {
                SourceTier.A_AUTHORITATIVE,
                SourceTier.B_PROFESSIONAL,
            }
            else "DISCOVERY_ONLY"
        )

        for finding in findings:
            previous: dict[str, Any] | None = None
            for record in reversed(self._records):
                if (
                    record.get("source_id") == source.source_id
                    and record.get("domain") == finding.domain
                    and record.get("knowledge_key") == finding.knowledge_key
                    and record.get("status") in {"VERIFIED", "DISCOVERY_ONLY", "CONFLICT"}
                ):
                    previous = record
                    break

            supersedes: str | None = None
            if previous is not None:
                previous["status"] = "SUPERSEDED"
                supersedes = str(previous["record_id"])
                superseded_count += 1

            material = {
                "source_id": source.source_id,
                "source_tier": source.tier.value,
                "domain": finding.domain,
                "knowledge_key": finding.knowledge_key,
                "claim": finding.claim,
                "confidence": float(finding.confidence),
                "source_digest": source_digest,
                "observed_at": observed_at,
                "supersedes_record_id": supersedes,
            }
            record_id = _canonical_digest(material)
            self._records.append(
                {
                    "schema": "DailyKnowledgeRecord/v1",
                    "record_id": record_id,
                    **material,
                    "status": new_status,
                    "grants_execution_authority": False,
                    "runtime_mutation_authority": False,
                }
            )
            finding_count += 1

        return finding_count, superseded_count

    def run(
        self,
        *,
        cycle_id: str,
        observed_at: datetime,
    ) -> DailyIntelligenceReceipt:
        if not _CYCLE_ID_RE.fullmatch(str(cycle_id or "")):
            raise ValueError("DAILY_INTELLIGENCE_CYCLE_ID_INVALID")
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("DAILY_INTELLIGENCE_OBSERVED_AT_MUST_BE_AWARE")

        observed = observed_at.isoformat()
        changed = 0
        unchanged = 0
        finding_count = 0
        superseded_count = 0
        errors: list[str] = []
        source_digests: dict[str, str] = {}

        for source in self.sources:
            try:
                fetched = self.fetcher(source)
                if not isinstance(fetched, FetchedSource):
                    raise ValueError("DAILY_INTELLIGENCE_FETCH_RESULT_INVALID")
                source_digest = _sha256_bytes(fetched.body)
                source_digests[source.source_id] = source_digest

                previous = self._source_state.get(source.source_id) or {}
                if previous.get("sha256") == source_digest:
                    unchanged += 1
                    continue

                proposed = self._validate_findings(
                    source=source,
                    findings=self.analyzer(
                        source,
                        fetched.body,
                        source_digest,
                    ),
                )
                added, superseded = self._record_findings(
                    source=source,
                    source_digest=source_digest,
                    findings=proposed,
                    observed_at=observed,
                )
                finding_count += added
                superseded_count += superseded
                changed += 1
                self._source_state[source.source_id] = {
                    "sha256": source_digest,
                    "etag": fetched.etag,
                    "last_modified": fetched.last_modified,
                    "observed_at": observed,
                    "source_url": source.url,
                }
            except Exception as exc:
                errors.append(f"{source.source_id}:{exc}")

        self._write_state()

        receipt_path = self.receipts_root / f"{cycle_id}.json"
        receipt = DailyIntelligenceReceipt(
            cycle_id=cycle_id,
            observed_at=observed,
            status="PASS" if not errors else "FAIL",
            source_count=len(self.sources),
            changed_source_count=changed,
            unchanged_source_count=unchanged,
            finding_count=finding_count,
            superseded_record_count=superseded_count,
            error_count=len(errors),
            errors=tuple(errors),
            source_digests=source_digests,
            receipt_path=str(receipt_path),
        )
        _atomic_write_json(receipt_path, receipt.to_dict())
        return receipt
