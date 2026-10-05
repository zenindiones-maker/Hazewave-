# ADR-0001 — HAZE/WAVE Domain Boundary
- Status: Accepted for development
- Date: 2026-10-04
## Context
Hazewave combines sound and visual production but needs explicit ownership to prevent silent cross-domain policy.
## Decision
HAZE owns sound/music. WAVE owns image/visual media. BRIDGE owns only the typed `HAZE_STATE -> WAVE_STATE` translation boundary. Cross-domain behavior must be explicit and structured, not a one-value amplitude visualizer.
## Consequences
Independent evolution, testable boundaries, fail-closed routing and versioned state schemas.
