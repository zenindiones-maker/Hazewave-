# HAZE + WAVE Reverse Engineering Lab V1

- Status: NORMATIVE / DEVELOPMENT
- Owner: HUMAN_OWNER
- Project authority: HAZEWAVE_HARNESS
- Policy: `config/reverse-engineering-foundation-v1.json`
- Runtime installer: `scripts/codespaces/install-reverse-engineering-foundation.sh`
- Runtime doctor: `scripts/codespaces/reverse-engineering-doctor.sh`

## 1. Mission

The Reverse Engineering Lab is a first-class research capability for HAZE and WAVE.

Its job is to understand mechanisms, interfaces, data flows, signal behavior, rendering behavior and implementation trade-offs in authorized reference systems, then turn that evidence into independent Hazewave implementations adapted to Hazewave's architecture.

Reverse engineering is not treated as source recovery, copying authority, a license bypass or permission to operate on arbitrary targets.

The lab follows one rule:

`REFERENCE -> OBSERVE -> MEASURE -> EXPLAIN -> REPRODUCE INDEPENDENTLY -> VERIFY`

No external tool becomes project authority. HAZEWAVE_HARNESS remains the sole execution authority.

## 2. Target authorization boundary

An investigation may proceed only when the target is owned by the operator, open-source, explicitly authorized, or otherwise legitimately available for the intended analysis.

The lab fails closed for:

- unauthorized access;
- credential extraction;
- DRM or license-control bypass;
- stealth or evasion;
- malware development;
- data exfiltration.

Authorization to inspect one target is not transferable to another target.

## 3. Evidence model

Every material conclusion must identify which evidence class supports it:

1. `STATIC_INFERENCE` — strings, symbols, control flow, decompilation, resource layout or other non-executing observations.
2. `MEASURED_BEHAVIOR` — repeatable input/output measurements such as latency, spectral response, file metadata, frame timing or shader outputs.
3. `RUNTIME_OBSERVATION` — authorized observation of a running process or graphics pipeline.
4. `REPRODUCED_BEHAVIOR` — an independent Hazewave implementation demonstrates the same required behavior under a defined benchmark.

Static inference is never silently promoted to runtime fact. Decompiler output is pseudocode, not original source.

Each investigation should preserve, when applicable:

- target identity and cryptographic digest;
- source or acquisition provenance;
- exact tool and version;
- configuration and provider identity;
- timestamps;
- immutable analysis output or snapshot;
- measurements and fixtures;
- limitations and unresolved questions;
- reproduction commit/artifact hashes;
- human approval outcome.

## 4. Tool architecture

### REA — investigation orchestration and evidence

REA is the primary agent-facing reverse-engineering surface.

Hazewave pins the released `rea-agents` artifact and runs it locally. REA may orchestrate native, JavaScript/Electron and web investigations, but remains a tool under Harness policy.

Primary roles:

- evidence-aware investigation;
- Ghidra-backed native analysis;
- JavaScript/Electron static analysis;
- browser/application observation where supported;
- immutable snapshots and comparisons;
- CLI/MCP research surface.

### Ghidra — primary deep native provider

Ghidra is the default deep-analysis provider because it is open source and supports deterministic headless analysis.

Hazewave pins the official supported release and verifies its release SHA-256 before use. Ghidra results are read-only evidence; they do not grant mutation authority.

### Rizin — fast scriptable binary triage

Rizin complements Ghidra for CLI-first inspection of formats, sections, symbols, strings and disassembly.

It is not a second authority and does not override conflicting Ghidra/runtime evidence.

### Frida — authorized runtime instrumentation

Frida is available only for approved runtime observation when static evidence is insufficient.

Dynamic instrumentation is not a default first step. It must be scoped to an authorized target and the observation required by the investigation.

### FFmpeg / ffprobe + MediaInfo — audiovisual evidence

Hazewave reuses the qualified FFmpeg runtime and adds MediaInfo as an independent metadata cross-check.

These tools are central to codec, container, timing, color, stream and signal investigations.

### RenderDoc + SPIR-V tools — WAVE graphics laboratory

RenderDoc is the preferred GPU frame-inspection surface where a compatible graphical workstation is available.

SPIRV-Tools and SPIRV-Cross provide shader validation, disassembly, reflection and cross-language inspection.

These are optional WAVE workstation capabilities; their absence on a headless Codespace must not be falsified as a failure of REA/Ghidra core readiness.

## 5. HAZE playbooks

### Audio plug-in / DSP feature

1. Hash and inventory the authorized artifact.
2. Record plug-in format, architecture, imports, strings and resources.
3. Establish behavior with controlled audio probes before assuming implementation details.
4. Use impulses, sweeps, tones, null tests, level sweeps, timing probes and automation fixtures where appropriate.
5. Measure frequency response, phase, dynamics, latency, nonlinear behavior, state transitions and determinism.
6. Use REA + Ghidra/Rizin to explain observed mechanisms.
7. Use Frida only when an authorized runtime observation is necessary.
8. Implement the required behavior independently in Hazewave/REAPER/JSFX/native code.
9. Compare reference and reproduction with level-matched objective and human tests.
10. Preserve evidence and limitations.

The goal is not to clone a proprietary plug-in. The goal is to learn the mechanism needed for a Hazewave capability and independently meet the benchmark.

### Codec / container / media pipeline

Start with fixture corpus, ffprobe and MediaInfo. Inspect bitstreams, timestamps, channel layouts and metadata. Escalate to static binary analysis only when the observable format behavior does not answer the question.

### REAPER integrations

HAZE may investigate owned/open-source scripts, extensions, JSFX, project structures and authorized plug-ins. REAPER remains the primary DAW surface and the Harness remains authority over any mutation.

## 6. WAVE playbooks

### Web / Electron reference

Prefer passive observation first:

- DOM and accessibility structure;
- layout and responsive behavior;
- network contract shapes where legitimately visible;
- animation timing;
- state transitions;
- WebGL/WebGPU resource behavior;
- performance characteristics.

Do not copy private source, branding assets or copyrighted content merely because a behavior is observable.

### Native visual application

Use REA/Ghidra/Rizin for application logic. Use Frida only for authorized runtime questions. If the feature is GPU-driven, capture the graphics pipeline with RenderDoc on a compatible workstation and inspect shader artifacts with SPIR-V tooling.

### Video / image pipeline

Use FFmpeg/ffprobe and MediaInfo for codec, color, frame cadence, timing and metadata; pair that with WAVE's existing QC, rendering and visual-comparison surfaces.

## 7. BRIDGE boundary

BRIDGE may coordinate typed audiovisual evidence such as:

- audio timing -> visual transition timing;
- media stream metadata -> render/encode decisions;
- synchronization evidence -> coordinated HAZE/WAVE fixes.

BRIDGE owns no reverse-engineering authority. It may not turn HAZE evidence into WAVE authority or vice versa.

## 8. Learning loop

Reverse-engineering outcomes feed HAZE/WAVE knowledge only after evidence is classified.

Daily Intelligence watches the upstream projects in the machine policy for material security, capability and version changes. Discovery does not auto-upgrade the production runtime.

A learned capability may move through:

`KNOWN -> COMPATIBLE -> RUNTIME_PROVEN -> PRODUCTION_APPROVED -> HUMAN_APPROVED`

No lower state may be presented as a higher one.

## 9. Admission gates

A tool or capability requires, as applicable:

1. source identity;
2. license review;
3. security review;
4. pinned/reproducible install proof;
5. real runtime proof;
6. HAZE/WAVE domain benchmark;
7. human approval.

Installation alone is never `PRODUCTION_APPROVED`.

## 10. Current boundary

The repository contains the policy, routing layer, pinned installer and runtime doctor.

Until the existing Hazewave Codespace executes the installer and deep doctor successfully, the reverse-engineering runtime state is:

`COMPATIBLE / IMPLEMENTED-IN-REPOSITORY, NOT YET RUNTIME_PROVEN`

RenderDoc and shader tooling are intentionally treated as WAVE workstation capabilities rather than falsely claiming that a headless CPU Codespace proves graphics capture.

## 11. Selected complementary projects

The core stack deliberately avoids tool-count inflation.

- REA: agent orchestration + evidence.
- Ghidra: deep open-source native analysis.
- Rizin: scriptable binary triage.
- Frida: authorized runtime instrumentation.
- FFmpeg/MediaInfo: audiovisual containers/codecs/measurements.
- RenderDoc: graphics frame capture.
- SPIRV-Tools/SPIRV-Cross: shader analysis.

Other projects such as apitrace, Kaitai Struct, ImHex and JADX remain candidates/watchlist items. They are admitted only when a concrete HAZE/WAVE gap exists and they outperform or complement the current stack under the normal qualification gate.
