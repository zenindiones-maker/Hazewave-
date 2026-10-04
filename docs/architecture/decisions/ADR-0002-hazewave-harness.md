# ADR-0002 — Hazewave Harness as Project-Local Control Plane
- Status: Accepted for development
- Date: 2026-10-04
## Context
Multiple workers, models and tools require unambiguous project-local authority.
## Decision
Hazewave Harness owns task-domain routing, capability authorization and project-local execution policy. Workers/providers are subordinate; routing is capability-first; portfolio metadata has no execution authority.
## Consequences
Domain mismatches fail closed, workers cannot self-expand authority and future model integrations use the same project contracts.
