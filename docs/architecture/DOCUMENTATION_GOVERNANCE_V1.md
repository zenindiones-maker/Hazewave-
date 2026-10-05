# HAZEWAVE Documentation Governance v1

## Purpose
Hazewave separates normative rules, creative canon, operations, explanation, evidence and publication artifacts so agents and humans do not mistake aspiration for executable authority.

## Document classes
- **NORMATIVE** — rules execution must obey: ProjectProfile, AGENTS, schemas and accepted ADRs.
- **CANONICAL** — creative identity and work invariants; canon does not grant infrastructure authority.
- **OPERATIONAL** — procedures for operating an already-authorized system; runbooks never expand authority.
- **EXPLANATORY** — design intent, theory, alternatives and targets; explanation is not automatically executable.
- **EVIDENCE** — tests, logs, manifests and receipts proving what happened.
- **PUBLICATION ARTIFACT** — rendered books, sites, media and other outputs derived from canonical sources.

## Source-of-truth rule
For execution authority and safety: ProjectProfile -> AGENTS -> schemas -> accepted ADRs -> operational reference/runbooks -> explanation.
For creative identity: project/work canon -> accepted work specifications -> explanatory design.
If repository/runtime evidence contradicts normative intent, report drift; do not silently redefine the norm.

## Lifecycle
Governance-critical documents use DEVELOPMENT, ACTIVE or SUPERSEDED. New tasks bind only to active/current replacements.

## Registration
Governance-critical documents are registered in `docs/DOCUMENTATION_REGISTRY_V2.json` with stable id, path, type, authority, lifecycle, owner, applicability and description. CI validates the registry.

## Machine-readable contracts
Cross-component state and provenance use JSON Schema Draft 2020-12 under `schemas/`. Valid examples live under `examples/contracts/`. Prose may explain schemas but may not silently redefine them.

## Architecture decisions
Material architecture choices use ADRs under `docs/architecture/decisions/`. Materially changed decisions are superseded explicitly instead of being silently rewritten.

## Freshness and drift
Material changes requiring review include authority, domain boundaries, runtime/deployment, security/data classification, schemas/contracts and canonical/promotion model. Cosmetic edits do not force ProjectProfile revalidation.

## Change discipline
A normative change updates its contract, tests/validator, registry metadata when needed, and affected reference/runbook material. No document gains authority solely because an agent generated it.
