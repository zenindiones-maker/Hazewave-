from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from hazewave.daily_intelligence import (
    DailyIntelligenceEngine,
    DailySource,
    FetchedSource,
    ProposedFinding,
    SourceTier,
    load_source_registry,
)


NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def _source(
    source_id: str,
    *,
    tier: SourceTier = SourceTier.A_AUTHORITATIVE,
    domains: tuple[str, ...] = ("HAZE",),
) -> DailySource:
    return DailySource(
        source_id=source_id,
        url=f"https://example.com/{source_id}",
        domains=domains,
        tier=tier,
        source_kind="OFFICIAL_DOCUMENTATION",
    )


def test_daily_source_requires_https_and_known_domain() -> None:
    with pytest.raises(ValueError, match="DAILY_INTELLIGENCE_SOURCE_URL_INVALID"):
        DailySource(
            source_id="bad",
            url="http://example.com",
            domains=("HAZE",),
            tier=SourceTier.A_AUTHORITATIVE,
            source_kind="OFFICIAL_DOCUMENTATION",
        )

    with pytest.raises(ValueError, match="DAILY_INTELLIGENCE_SOURCE_DOMAIN_INVALID"):
        DailySource(
            source_id="bad-domain",
            url="https://example.com",
            domains=("OTHER",),
            tier=SourceTier.A_AUTHORITATIVE,
            source_kind="OFFICIAL_DOCUMENTATION",
        )


def test_unchanged_source_is_not_reanalyzed(tmp_path: Path) -> None:
    source = _source("reaper-api")
    analyzer_calls: list[str] = []

    def fetcher(item: DailySource) -> FetchedSource:
        return FetchedSource(
            body=b"REAPER API current",
            etag='"v1"',
            last_modified="Tue, 06 Oct 2026 10:00:00 GMT",
        )

    def analyzer(item: DailySource, body: bytes, source_digest: str):
        analyzer_calls.append(source_digest)
        return (
            ProposedFinding(
                knowledge_key="reaper.api.current",
                domain="HAZE",
                claim="REAPER API current",
                confidence=1.0,
            ),
        )

    engine = DailyIntelligenceEngine(
        state_root=tmp_path,
        sources=(source,),
        fetcher=fetcher,
        analyzer=analyzer,
    )

    first = engine.run(cycle_id="cycle-1", observed_at=NOW)
    second = engine.run(cycle_id="cycle-2", observed_at=NOW)

    assert first.status == "PASS"
    assert first.changed_source_count == 1
    assert first.finding_count == 1
    assert second.status == "PASS"
    assert second.changed_source_count == 0
    assert second.unchanged_source_count == 1
    assert second.finding_count == 0
    assert len(analyzer_calls) == 1


def test_authoritative_finding_supersedes_older_same_source_key(tmp_path: Path) -> None:
    source = _source("reaper-release")
    bodies = iter((b"REAPER 7.82", b"REAPER 7.83"))

    def fetcher(item: DailySource) -> FetchedSource:
        return FetchedSource(body=next(bodies))

    def analyzer(item: DailySource, body: bytes, source_digest: str):
        value = body.decode("utf-8")
        return (
            ProposedFinding(
                knowledge_key="reaper.current_version",
                domain="HAZE",
                claim=value,
                confidence=1.0,
            ),
        )

    engine = DailyIntelligenceEngine(
        state_root=tmp_path,
        sources=(source,),
        fetcher=fetcher,
        analyzer=analyzer,
    )

    first = engine.run(cycle_id="cycle-1", observed_at=NOW)
    second = engine.run(cycle_id="cycle-2", observed_at=NOW)

    registry = engine.registry_snapshot()
    records = registry["records"]

    assert first.superseded_record_count == 0
    assert second.superseded_record_count == 1
    assert len(records) == 2
    old = next(item for item in records if item["claim"] == "REAPER 7.82")
    new = next(item for item in records if item["claim"] == "REAPER 7.83")
    assert old["status"] == "SUPERSEDED"
    assert new["status"] == "VERIFIED"
    assert new["supersedes_record_id"] == old["record_id"]


def test_discovery_source_cannot_create_verified_knowledge(tmp_path: Path) -> None:
    source = _source(
        "community",
        tier=SourceTier.C_DISCOVERY,
        domains=("WAVE",),
    )

    engine = DailyIntelligenceEngine(
        state_root=tmp_path,
        sources=(source,),
        fetcher=lambda item: FetchedSource(body=b"interesting claim"),
        analyzer=lambda item, body, digest: (
            ProposedFinding(
                knowledge_key="wave.experimental.idea",
                domain="WAVE",
                claim="interesting claim",
                confidence=0.8,
            ),
        ),
    )

    receipt = engine.run(cycle_id="cycle-1", observed_at=NOW)
    record = engine.registry_snapshot()["records"][0]

    assert receipt.status == "PASS"
    assert record["status"] == "DISCOVERY_ONLY"
    assert record["source_tier"] == "C_DISCOVERY"


def test_finding_cannot_escape_source_domain(tmp_path: Path) -> None:
    source = _source("haze-only", domains=("HAZE",))
    engine = DailyIntelligenceEngine(
        state_root=tmp_path,
        sources=(source,),
        fetcher=lambda item: FetchedSource(body=b"source"),
        analyzer=lambda item, body, digest: (
            ProposedFinding(
                knowledge_key="wrong.domain",
                domain="WAVE",
                claim="not allowed",
                confidence=1.0,
            ),
        ),
    )

    receipt = engine.run(cycle_id="cycle-1", observed_at=NOW)

    assert receipt.status == "FAIL"
    assert receipt.finding_count == 0
    assert receipt.error_count == 1
    assert "FINDING_DOMAIN_NOT_ALLOWED" in receipt.errors[0]


def test_daily_intelligence_receipt_has_knowledge_only_authority(tmp_path: Path) -> None:
    source = _source("reaper-api")
    engine = DailyIntelligenceEngine(
        state_root=tmp_path,
        sources=(source,),
        fetcher=lambda item: FetchedSource(body=b"source"),
        analyzer=lambda item, body, digest: (),
    )

    receipt = engine.run(cycle_id="cycle-authority", observed_at=NOW)
    payload = receipt.to_dict()

    assert payload["authority"] == "HAZEWAVE_HARNESS"
    assert payload["knowledge_authority"] == "KNOWLEDGE_ONLY"
    assert payload["grants_execution_authority"] is False
    assert payload["runtime_mutation_authority"] is False
    assert payload["auto_install"] is False
    assert payload["auto_upgrade"] is False
    assert Path(payload["receipt_path"]).is_file()


def test_source_registry_is_project_local_public_and_daily() -> None:
    registry = load_source_registry(
        Path("config/daily-intelligence-sources-v1.json")
    )

    assert registry["schema"] == "DailyIntelligenceSourceRegistry/v1"
    assert registry["authority"] == "HAZEWAVE_HARNESS"
    assert registry["knowledge_authority"] == "KNOWLEDGE_ONLY"
    assert registry["cadence"] == "DAILY"
    assert registry["runtime_mutation_authority"] is False

    sources = registry["sources"]
    ids = {item.source_id for item in sources}
    assert {
        "reaper-release",
        "reaper-reascript",
        "reaper-jsfx",
        "itu-bs1770",
        "ffmpeg-filters",
        "blender-lts",
        "krita-scripting",
        "w3c-wcag22",
        "playwright-accessibility",
    }.issubset(ids)

    assert all(item.url.startswith("https://") for item in sources)
    assert all(item.data_classification == "PUBLIC" for item in sources)


def test_registry_rejects_duplicate_source_ids(tmp_path: Path) -> None:
    path = tmp_path / "sources.json"
    payload = {
        "schema": "DailyIntelligenceSourceRegistry/v1",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "knowledge_authority": "KNOWLEDGE_ONLY",
        "cadence": "DAILY",
        "runtime_mutation_authority": False,
        "sources": [
            {
                "source_id": "dup",
                "url": "https://example.com/a",
                "domains": ["HAZE"],
                "tier": "A_AUTHORITATIVE",
                "source_kind": "OFFICIAL_DOCUMENTATION",
                "data_classification": "PUBLIC",
            },
            {
                "source_id": "dup",
                "url": "https://example.com/b",
                "domains": ["WAVE"],
                "tier": "A_AUTHORITATIVE",
                "source_kind": "OFFICIAL_DOCUMENTATION",
                "data_classification": "PUBLIC",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="DAILY_INTELLIGENCE_DUPLICATE_SOURCE_ID"):
        load_source_registry(path)
