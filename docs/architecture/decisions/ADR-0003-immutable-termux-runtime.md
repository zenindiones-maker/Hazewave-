# ADR-0003 — Immutable Termux Runtime
- Status: Accepted for development
- Date: 2026-10-04
## Context
A mutable development checkout is not a reproducible runtime source.
## Decision
Termux uses SHA-addressed immutable releases under `~/.local/share/hazewave/deploy/releases/<sha>/`, with a `current` pointer and separate state/config namespaces.
## Consequences
Exact runtime identity, development/runtime separation and durable state outside source releases.
