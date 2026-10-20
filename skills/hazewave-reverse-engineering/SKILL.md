---
name: hazewave-reverse-engineering
description: Conduct authorized, evidence-first reverse-engineering research for HAZE audio and WAVE visual work under Hazewave Harness control. Apply when actual behavior or shipped artifacts must be studied; do not invoke REA for ordinary readable source-only code review.
---

# HAZEWAVE — Reverse Engineering Research Skill

This is a **project-local, subordinate** skill. It neither installs REA nor registers MCP tools and is not evidence of a live provider. It must always obey `AGENTS.md`, `config/project-profile-v2.json`, the signed-grant policy, and `config/reverse-engineering-foundation-v1.json`.

## Tool contract

- Source identity: `morluto/rea`, exact package `rea-agents@6.0.0`; do not resolve `@latest` inside an execution job.
- Tool authority: **NONE**. `HAZEWAVE_HARNESS` routes every task and owns the result gate.
- Provider on Linux Codespace for native binaries: **Ghidra**. Never choose Hopper or allow automatic fallback to proprietary tools.
- MCP version-6 filesystem arguments must contain host-absolute paths; verify with the local `hazewave.rea6_integration.require_absolute_mcp_paths` contract before dispatch.
- REA 6.0.0 skills/MCP registrations are **not** automatically assumed present when its CLI or this skill exists. Follow the bundled `reverse-engineer-anything` skill of the exact installed release if a real REA agent session is attached; do not mix versions.

## Research method, required in order

1. **Define a lawful owned/reviewable target.** Identify its SHA-256, source/license, format, domain and rights. For non-fixture targets, obtain a valid owner/Harness-signed grant bound to those exact bytes, purpose, domain, target kind and expiry. A user-supplied `--authorized` boolean cannot replace it.
2. **Route by domain.** HAZE: voice, codecs, DAWs, plugins, DSP, mixing, mastering and music. WAVE: video, animation, visual renderers, graphics, sites, shaders and image pipelines. BRIDGE only translates already authorized typed HAZE/WAVE evidence and grants no own execution authority.
3. **Start with the simplest truthful observation.** Source exists → static repository inspection, tests and trace; shipped binary → REA/Ghidra/Rizin as appropriate; audio/media → FFmpeg/MediaInfo plus controlled listening and measurement; WebGL/rendering → shader analysis and frame capture of authorized assets. Do not use REA reflexively for source-code-only tasks.
4. **Collect raw evidence.** Record tool/package version, provider, UTC time, input digest, exact parameters, actual observations, limitations, failure output, host resource budget and provenance. Distinguish `STATIC_INFERENCE`, `RUNTIME_OBSERVATION`, `MEASURED_BEHAVIOR` and `REPRODUCED_BEHAVIOR`.
5. **Propose one testable hypothesis.** Derive measurable predictions; don't treat generated pseudocode as original source. Evaluate a controlled fixture first.
6. **Recreate independently.** Author original Hazewave code/tests, not unauthorized copying or protected asset redistribution. Test visual/audio fidelity and regressions with independent sources and metrics.
7. **Compare and learn.** Run repeated baselines and candidates under bounded CPU/RAM/disk; preserve failed/null results. Store concise, privacy-safe findings for governed daily HAZE/WAVE intelligence; never silently mutate production code.
8. **Fail closed.** Absent signed grant, mismatched package/provider, insufficient resources, unverifiable direct Evidence, cross-domain request or unknown license → BLOCK. CI pass does not replace Codespace runtime proof; MCP setup does not establish that a client has loaded the tools.

## Reflex / Colibri source-first boundary

For the open-source pinned Colibri/Laya engine, begin with source, `hazewave-reflex engine-re-doctor` and its in-tree phase profiler. Do not add 139 REA tools as a substitute for an understood hotspot. Preserve pinned Laya weights/source SHA, f32 numerical path and robust 3-rotation ensemble; no benchmark promotion below the project gate. Do not stop the stock server solely to install this skill.

## Agent handoff artifacts

Each HAZE/WAVE task should hand back a **typed evidence packet**, rather than a generic narrative. Required fields: target SHA-256, domain/goal/purpose, signed-grant identity, source/engine/tool version, provider and operations, direct observation vs inference, limitations, evidence digest, test/profiling artifacts, observed results and uncertainty, reproduction status, unresolved blockers, and explicit `production_approved=false`. Never attach secrets/private recordings to public GitHub artifacts.

## Canonical upstream

- REA release: https://github.com/morluto/rea/releases/tag/rea-agents-6.0.0
- Version-matched REA skill: https://github.com/morluto/rea/blob/rea-agents-6.0.0/skills/reverse-engineer-anything/SKILL.md
- Evidence model: https://github.com/morluto/rea/blob/rea-agents-6.0.0/src/domain/evidence.ts
- Native CLI contract: https://github.com/morluto/rea/blob/rea-agents-6.0.0/docs/cli.md
