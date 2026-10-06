from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hazewave.professional_knowledge import (
    KnowledgeEvidence,
    KnowledgeKind,
    KnowledgeValidationStatus,
    ProfessionalKnowledgeRegistry,
    ToolKnowledge,
    PluginKnowledge,
    TechniqueKnowledge,
    StyleKnowledge,
)


def _evidence(
    *,
    retrieved_at: datetime | None = None,
    validation_status: KnowledgeValidationStatus = KnowledgeValidationStatus.SOURCE_VERIFIED,
) -> KnowledgeEvidence:
    return KnowledgeEvidence(
        source="https://example.invalid/official",
        source_type="OFFICIAL_DOCUMENTATION",
        retrieved_at=retrieved_at or datetime(2026, 10, 6, tzinfo=timezone.utc),
        version="1.2.3",
        platform="linux",
        architecture="x86_64",
        license_or_cost_class="FREE_OPEN_SOURCE",
        confidence=0.99,
        freshness_days=30,
        validation_status=validation_status,
    )


def test_registry_supports_required_typed_knowledge_surfaces_without_authority() -> None:
    registry = ProfessionalKnowledgeRegistry()

    entries = (
        ToolKnowledge(
            knowledge_id="tool-blender",
            title="Blender production runtime",
            kind=KnowledgeKind.TOOL_CAPABILITY,
            evidence=(_evidence(),),
            tool_id="blender",
            tool_version="5.2.2",
            capabilities=("GREASE_PENCIL", "COMPOSITOR", "PYTHON_API"),
        ),
        PluginKnowledge(
            knowledge_id="plugin-tape-echo",
            title="Tape Echo 2 runtime semantics",
            kind=KnowledgeKind.COMPATIBILITY_EVIDENCE,
            evidence=(
                _evidence(
                    validation_status=KnowledgeValidationStatus.RUNTIME_PROVEN
                ),
            ),
            plugin_id="tape-echo-2",
            plugin_version="1.0.8",
            semantic_roles=("delay", "dub_delay"),
        ),
        TechniqueKnowledge(
            knowledge_id="technique-dub-send",
            title="Dub send-based delay performance",
            kind=KnowledgeKind.CREATIVE_HEURISTIC,
            evidence=(_evidence(),),
            domain="HAZE",
            technique="send_based_delay",
        ),
        StyleKnowledge(
            knowledge_id="style-cartoon",
            title="Animated cartoon canonical output",
            kind=KnowledgeKind.HUMAN_PREFERENCE,
            evidence=(_evidence(),),
            domain="WAVE",
            style_id="animated_cartoon",
        ),
    )

    for entry in entries:
        registry.register(entry)

    payload = registry.to_dict()

    assert payload["schema"] == "ProfessionalKnowledgeRegistry/v1"
    assert payload["authority"] == "NONE"
    assert payload["grants_execution_authority"] is False
    assert len(payload["entries"]) == 4
    assert {entry["schema"] for entry in payload["entries"]} == {
        "ToolKnowledge/v1",
        "PluginKnowledge/v1",
        "TechniqueKnowledge/v1",
        "StyleKnowledge/v1",
    }


@pytest.mark.parametrize(
    "kind",
    [
        KnowledgeKind.FACT,
        KnowledgeKind.STANDARD,
        KnowledgeKind.TOOL_CAPABILITY,
        KnowledgeKind.COMPATIBILITY_EVIDENCE,
        KnowledgeKind.EXPERIMENTAL_EVIDENCE,
        KnowledgeKind.CREATIVE_HEURISTIC,
        KnowledgeKind.HUMAN_PREFERENCE,
    ],
)
def test_required_knowledge_kinds_round_trip(kind: KnowledgeKind) -> None:
    entry = TechniqueKnowledge(
        knowledge_id=f"kind-{kind.value.lower()}",
        title="Fixture",
        kind=kind,
        evidence=(_evidence(),),
        domain="HAZE",
        technique="fixture",
    )

    assert entry.to_dict()["kind"] == kind.value


def test_external_material_fact_requires_evidence() -> None:
    with pytest.raises(ValueError, match="KNOWLEDGE_EVIDENCE_REQUIRED"):
        ToolKnowledge(
            knowledge_id="tool-no-evidence",
            title="Unsupported tool claim",
            kind=KnowledgeKind.FACT,
            evidence=(),
            tool_id="tool",
            tool_version="1",
            capabilities=("x",),
        )


def test_evidence_confidence_and_freshness_are_fail_closed() -> None:
    with pytest.raises(ValueError, match="KNOWLEDGE_CONFIDENCE_INVALID"):
        _evidence().with_confidence(1.1)

    old = _evidence(
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    assert old.is_stale(as_of=datetime(2026, 10, 6, tzinfo=timezone.utc)) is True
    assert _evidence().is_stale(
        as_of=datetime(2026, 10, 20, tzinfo=timezone.utc)
    ) is False


def test_source_verified_does_not_become_runtime_proven() -> None:
    evidence = _evidence(
        validation_status=KnowledgeValidationStatus.SOURCE_VERIFIED
    )

    assert evidence.runtime_proven is False


def test_registry_rejects_duplicate_id_with_different_content() -> None:
    registry = ProfessionalKnowledgeRegistry()
    first = TechniqueKnowledge(
        knowledge_id="duplicate",
        title="First",
        kind=KnowledgeKind.CREATIVE_HEURISTIC,
        evidence=(_evidence(),),
        domain="HAZE",
        technique="a",
    )
    second = TechniqueKnowledge(
        knowledge_id="duplicate",
        title="Second",
        kind=KnowledgeKind.CREATIVE_HEURISTIC,
        evidence=(_evidence(),),
        domain="HAZE",
        technique="b",
    )

    registry.register(first)

    with pytest.raises(ValueError, match="KNOWLEDGE_ID_CONFLICT"):
        registry.register(second)


def test_project_seed_is_versioned_source_verified_not_fake_runtime_proof() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = ProfessionalKnowledgeRegistry.load(
        root / "knowledge" / "professional-knowledge-v1.json"
    )

    assert registry.get("tool-blender-5.2-lts").tool_version == "5.2.2"
    assert registry.get("tool-opentimelineio").tool_version == "0.18.1"
    assert registry.get("tool-pyscenedetect").tool_version == "0.7.1"
    assert registry.get("tool-krita").tool_version in {"5.3.4", "6.0.4"}
    assert registry.get("tool-opentoonz").tool_version == "1.8.0"

    for entry in registry.entries:
        for evidence in entry.evidence:
            assert evidence.validation_status != KnowledgeValidationStatus.RUNTIME_PROVEN

    assert registry.to_dict()["authority"] == "NONE"
