# HAZEWAVE — REAL HARNESS INVENTORY + NATIVE BEHAVIOR QUALIFICATION V1

**Status:** stacked development PR #36. **Authority:** HAZEWAVE_HARNESS.
**Scope:** true capability declaration inventory, evidence-scoped wiring sequence, and original-source native analysis/behavior only.
**Do not merge, make paid infrastructure, restart Reflex/Colibri, or touch BR-no-GTA.**

## The inventory is real, but host readiness is a different observation

`python -m hazewave.harness inventory` now calls the actual Harness capability catalog and maps every capability to the exact entries in `config/capability-evidence-plane-v1.json`. Output `HazewaveFullCapabilityConnectionInventory/v1` includes each individual capability, domain, possible providers and *unverified* runtime states.

Current inventory baseline at PR creation: **124 Harness capabilities**, **10 mapped to one or more of 10 declared providers**, **114 without an exact provider mapping**. Mapped does NOT mean installed or connected. Unmapped does NOT prove a tool is missing; it means one has not been qualified for that capability. **Ready and live-agent-connected on the owner's Codespace remain UNKNOWN/NOT ATTESTED, not a measured zero.** The baseline's 0 is the number of positive signed host attestations in this report, not a real-time claim about the machine.

The full machine-readable connection queue starts:
1. `rea6.ghidra_native` (native function provider and actual Evidence).
2. `rea6.js_static` (JavaScript source-owned graph, actual CLI and agent MCP).
3. `iris.local_fixture` (offline screenshot and bounded tool route).
4. `rea6.managed` (positive CIL/metadata qualification).
5. `rea6.electron_observation` and `iris.live_site` (stay BLOCKED until independent browser network isolation and task-grant review).
6. HAZE/FFmpeg, WAVE/FFprobe/Pillow/PySceneDetect/OpenTimelineIO, HAZE/Essentia/Demucs, WAVE/OpenCV.
7. Every remaining catalog capability queued for an exact provider selection, sample-quality test, cost/risk/license review and runtime evidence.

No broad `mcp add`, `rea setup`, `curl|bash` or auto-install/auto-promotion is authorized from this queue. Each connection requires host and agent `tools/list`/effective tool call, audited grants and private receipts, not a package name.

## Actual native differential test

Run in a **reviewed** first-party checkout:

```bash
PYTHONPATH=src python -m hazewave.harness inventory
PYTHONPATH=src python -m hazewave.native_behavior_qualification \
  --state-root "$HOME/.local/state/hazewave/native-owned" --seed 42 --count 300

# Mutation control MUST exit nonzero and create a rejected private receipt:
PYTHONPATH=src python -m hazewave.native_behavior_qualification \
  --state-root "$HOME/.local/state/hazewave/native-mutant" \
  --candidate mutant --seed 42 --count 300
```

The module compiles and executes source-owned C original and reconstruction hypothesis, checks exact exit values on sampled inputs including boundary -7, 9, ±1000, records executable/source SHA-256 plus input/output digests and emits mode-0600 local receipts. A mutated hypothesis intentionally excludes x=9 and MUST be rejected, proving the comparator can detect a known discrepancy.

**Limits:** original and hypothesis source are known and checked in; the Harness does not automatically derive the reconstruction from binary/pseudocode. Passing 300 inputs is **BOUNDED_BEHAVIOR_MATCH**, never mathematical equivalence for every input or identical original source. Native behavior itself does not imply Ghidra was running.

## Ghidra native direct Evidence

REA's exact published npm 6.0.0 and the official [Ghidra 12.1.4 release](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.4_build) are separate dependencies. Official Linux ZIP SHA256: `ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db`.

A separate disposable GitHub Action `rea6-real-ghidra-native.yml` downloads the public Ghidra release with SHA verification, sets up JDK 21 and official REA6 without npm scripts, invokes `rea doctor --provider ghidra --json` then `rea function ... main --provider ghidra --json`. Evidence is only accepted if exact ELF SHA256, Ghidra provider ID, direct native observation and nonempty result are verified by `hazewave.rea6_integration.inspect_ghidra_evidence`. Any mismatch fails closed.

The test procedure on the **existing** Codespace is:

```bash
# First isolate the reviewed branch into a detached worktree, preserving
# current WIP and runtime; set SHA to exact remote verified commit.
export HAZEWAVE_NATIVE_EXPECTED_SHA="$(git rev-parse HEAD)"
bash scripts/codespaces/native-behavior-rea6-probe.sh --inventory
bash scripts/codespaces/native-behavior-rea6-probe.sh --behavior

# Requires actual pinned REA6, 64-bit full JDK, GHIDRA_INSTALL_DIR,
# Ghidra read-only provider and ≥4GiB MemAvailable:
bash scripts/codespaces/native-behavior-rea6-probe.sh --ghidra
```

This script refuses wrong Codespace identity, repository mismatch, dirty worktree,
reviewed SHA drift, absent tool, insufficient RAM or Ghidra doctor failure.
Ghidra is a read-only provider; the auditor does not mutate third-party
programs. If prerequisite is missing, report `BLOCKED:<exact reason>`,
not `PASS`.

The GitHub Actions runner is **not** `hazewave-zero-cost-4jxp45676rq6279xx`.
Do not rebind a runner's receipts to the owner's host, promote native tool
readiness, attach Frida, register a raw Iris MCP or grant new URL scope without
independent authorization.

## Evidence and connection graduation

A mature native capability requires:
- Three independently reviewed bounded behavioral runs, randomized and boundary inputs, known-mutant rejection, and p50/p95/CPU/RAM of actual provider.
- Ghidra direct evidence whose binary SHA256 matches the exact executed ELF, plus native decompiler operation and CI/server log provenance.
- For real external targets, owner-scoped signed target grant, legal authorization and sandbox.
- A separate actual-session MCP listing/call in the owner's chosen agent (not a stand-in GitHub runner).
- A signed capability-plane record bound to the host, exact tool digest, repo SHA and preserved local log, owner review.
- Distinct *quality*, *cost*, *risk*, *scope*, and *production approval*; fail closed on missing values.

Learn from failures by writing versioned negative evidence; do not train models on private references or silently promote unverified conclusions.
