# ADR-0007 — Governed Reverse Engineering Lab

- Status: ACCEPTED / DEVELOPMENT
- Date: 2026-10-08
- Authority: HUMAN_OWNER / HAZEWAVE_HARNESS

## Context

HAZE and WAVE need a repeatable way to understand advanced audio, video, graphics, application and web mechanisms from authorized reference systems without converting external tools into project authority or confusing decompiler inference with observed behavior.

A pile of unrelated reverse-engineering tools would increase operational risk and produce inconsistent evidence.

## Decision

Hazewave establishes one governed Reverse Engineering Lab.

REA is the agent-facing investigation/evidence layer. Ghidra is the default deep native provider. Rizin, Frida, FFmpeg/ffprobe, MediaInfo, RenderDoc and SPIR-V tooling are specialized adjuncts with explicit domain boundaries.

HAZE owns audio/DSP/REAPER-oriented investigations. WAVE owns visual/video/graphics/web investigations. BRIDGE may translate typed audiovisual evidence but has no authority.

All targets require authorization. Static inference, measured behavior, runtime observation and reproduced behavior remain distinct evidence classes. The system never claims original source recovery from decompilation.

The zero-cost/open-source core is preferred. Paid tools are not required for the baseline.

Runtime tools are pinned, reviewed and proven before production adoption. Discovery or installation does not grant execution authority or production approval.

## Consequences

- Reverse engineering becomes a measurable specialist capability rather than an ad-hoc agent behavior.
- HAZE can build independent behavioral models of authorized audio references using DSP measurements plus implementation evidence.
- WAVE can inspect modern visual stacks, frame pipelines and shaders with appropriate workstation tooling.
- Results are attributable and reproducible.
- Dynamic instrumentation remains explicit and scoped.
- Graphics tooling can remain unproven on a headless Codespace without blocking the core native-analysis runtime.
- The Harness can reject unsafe or unsupported investigation intents before tools execute.
