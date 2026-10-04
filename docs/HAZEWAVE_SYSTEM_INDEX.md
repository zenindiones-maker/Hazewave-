# HAZEWAVE — System Documentation Index

Hazewave documentation is governed by:

- [Documentation Governance v1](./architecture/DOCUMENTATION_GOVERNANCE_V1.md)
- [Documentation Registry v2](./DOCUMENTATION_REGISTRY_V2.json)
- [ProjectProfile v2](../config/project-profile-v2.json)
- [Agent Operating Contract v2](../AGENTS.md)

The JSON registry is the machine-readable index for governance-critical documents. This page is the human navigation surface.

## Authority map

### Project execution

- ProjectProfile v2 — normative project authority, security and runtime profile.
- AGENTS.md — normative operating contract for agents.
- JSON Schemas — normative machine-readable data contracts.
- ADRs — accepted architecture decisions.

### Creative canon

- [Hazewave domain model](../canon/hazewave-domain-v1.json)
- [Neandercaus series canon](../canon/neandercaus-series-v1.json)
- [Hazewave Books system canon](../canon/hazewave-books-series-v1.json)

Creative canon defines identity and creative invariants. It does not grant execution authority.

## Architecture decisions

- [ADR-0001 — HAZE/WAVE Domain Boundary](./architecture/decisions/ADR-0001-haze-wave-domain-boundary.md)
- [ADR-0002 — Hazewave Harness](./architecture/decisions/ADR-0002-hazewave-harness.md)
- [ADR-0003 — Immutable Termux Runtime](./architecture/decisions/ADR-0003-immutable-termux-runtime.md)

## Machine-readable contracts

- [ProjectProfile v2 schema](../schemas/project-profile-v2.schema.json)
- [HAZE state schema](../schemas/haze-state-v1.schema.json)
- [WAVE state schema](../schemas/wave-state-v1.schema.json)
- [Hazewave Asset Manifest schema](../schemas/hazewave-asset-manifest-v1.schema.json)
- [Documentation Registry schema](../schemas/documentation-registry-v2.schema.json)

## Reference

- [Hazewave Harness Reference v1](./reference/HAZEWAVE_HARNESS_V1.md)
- [HAZE/WAVE State Contracts v1](./reference/HAZE_WAVE_STATE_CONTRACTS_V1.md)

## Operations

- [Termux Runtime Runbook v1](./runbooks/TERMUX_RUNTIME_V1.md)

## WAVE

- [WAVE — Living Resonance Engine v1](./wave/WAVE_LIVING_RESONANCE_ENGINE_V1.md)

## Hazewave site / brand platform

- [HAZEWAVE — Brand Platform / Site Concept v1](./site/HAZEWAVE_BRAND_PLATFORM_V1.md)

## NEANDERCAUS

- [NEANDERCAUS — interactive animated series foundation](../apps/neandercaus/README.md)

## Hazewave Books / publishing

- [HAZEWAVE BOOKS — Editorial & Educational System v1](./publishing/HAZEWAVE_BOOKS_V1.md)
- [HAZEWAVE Academic Library index](./publishing/academic/README.md)
- [Academic Library Master Specification](./publishing/academic/HAZEWAVE_ACADEMIC_LIBRARY_MASTER_SPEC_V1.md)
- [Academic Research Pipeline](./publishing/academic/HAZEWAVE_ACADEMIC_RESEARCH_PIPELINE_V1.md)
- [University Publication Standard](./publishing/academic/HAZEWAVE_UNIVERSITY_PUBLICATION_STANDARD_V1.md)
- [Peer Review & Editorial Governance](./publishing/academic/HAZEWAVE_PEER_REVIEW_AND_EDITORIAL_GOVERNANCE_V1.md)
- [Asset Provenance & Rights Standard](./publishing/academic/HAZEWAVE_ACADEMIC_ASSET_PROVENANCE_STANDARD_V1.md)
- [Reader Verification & Source Portal](./publishing/academic/HAZEWAVE_READER_VERIFICATION_AND_SOURCE_PORTAL_V1.md)
- [Historical Narrative Protocol](./publishing/academic/HAZEWAVE_HISTORICAL_NARRATIVE_PROTOCOL_V1.md)
- [Scholarly Source & Musicology Standard](./publishing/academic/HAZEWAVE_SCHOLARLY_SOURCE_MUSICOLOGY_STANDARD_V1.md)
- [Musicology Analysis Framework](./publishing/academic/HAZEWAVE_MUSICOLOGY_ANALYSIS_FRAMEWORK_V1.md)
- [Global Sound History Program](./publishing/academic/HAZEWAVE_GLOBAL_SOUND_HISTORY_PROGRAM_V1.md)

## Source-of-truth rule

Markdown and JSON in the repository are the canonical working sources for review, diffing and automation. Generated publication formats are outputs and must be reconciled against their canonical sources.

When runtime evidence conflicts with normative documentation, report documentation drift rather than silently changing the meaning of either.
