---
project: HAZEWAVE
type: skill-acquisition-map
authority: KNOWLEDGE_ONLY
status: DEVELOPMENT
updated: 2026-10-08
---

# Skill Acquisition Map

Hazewave does not treat a long prompt as a skill and does not treat skill installation as proof of competence.

Every reusable skill must be:
1. scoped to a real capability;
2. grounded in attributable knowledge;
3. tested against pressure scenarios;
4. validated in the real tool/runtime when the skill claims tool operation;
5. measured with objective gates where applicable;
6. reviewed for recovery/failure behavior;
7. versioned and superseded rather than silently edited.

## HAZE skill ladder

### Foundation
- digital audio fundamentals;
- gain staging and metering;
- routing/buses/sends/sidechains;
- editing, comping, fades and time alignment;
- critical listening and level-matched comparison.

### REAPER specialist
- project/session architecture;
- routing matrix and folders;
- items/takes/lanes;
- envelopes and automation modes;
- MIDI/tempo maps;
- FX chains and presets;
- render matrix, stems and batch output;
- actions/custom actions;
- ReaScript Lua/EEL2;
- JSFX;
- resource paths, undo/rollback and recovery.

### Production specialist
- vocal production;
- beatmaking and arrangement;
- synthesis/sampling;
- sound design;
- EQ/dynamics/saturation;
- depth/spatial processing;
- mix architecture;
- mastering and delivery;
- reference matching;
- translation checks.

### Engineering/QC specialist
- ITU-R BS.1770 measurement;
- EBU/AES delivery profiles;
- true-peak/loudness/LRA;
- phase/mono/spectrum/noise/artifact QC;
- deterministic FFmpeg tooling;
- plugin qualification and benchmarking.

## WAVE skill ladder

### Visual foundations
- composition/hierarchy;
- typography;
- color and contrast;
- art direction;
- image processing;
- visual reference analysis.

### Animation specialist
- storyboard/animatic;
- 12 principles and timing/spacing;
- character consistency and model sheets;
- frame-by-frame/cartoon;
- rigging;
- Grease Pencil;
- lip sync;
- compositing and continuity.

### Video/post specialist
- editorial language;
- OpenTimelineIO;
- scene detection;
- motion graphics;
- color management/grading;
- VFX/compositing;
- FFmpeg encoding/QC;
- delivery profiles.

### Interactive-web specialist
- responsive UI;
- accessibility/WCAG;
- Core Web Vitals;
- Three.js;
- GSAP;
- WebGPU/WGSL;
- Web Audio visual interaction;
- WebCodecs;
- progressive enhancement and fallback design.

## Existing connected production capabilities

Use these as subordinate tools, not authorities:
- Higgsfield production skills for video, motion and websites;
- Figma skills for design systems, motion and design-to-code;
- Descript for conversational video/audio post workflows;
- HyperFrames skills for HTML-based video, audio-reactive visuals and GSAP.

A tool-specific skill can accelerate execution, but HAZE/WAVE still must independently satisfy Hazewave theory, measurement, judgement and recovery gates.

## New external learning helpers

Candidate learning helpers may be connected for research/discovery, but their content stays below official standards/docs in source precedence.

No plugin may:
- rewrite domain boundaries;
- auto-install production audio plugins;
- approve itself;
- mutate runtime pins;
- publish without authorization.

## Skill promotion states

`CANDIDATE -> PRESSURE_TESTED -> TOOL_VERIFIED -> RUNTIME_PROVEN -> PRODUCTION_SKILL`

Any failure returns the skill to CANDIDATE with evidence preserved.
