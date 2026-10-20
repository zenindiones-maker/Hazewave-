# HAZEWAVE REVERSE-ENGINEERING SCIENCE LOOP — V1

**Authority:** HAZEWAVE_HARNESS. **Research classes:** native executable, audio (HAZE), visual (WAVE).
**Review:** draft PR #37, stacked on #36 and earlier branches, no merge/promotion.
**Execution provenance:** GitHub runner is disposable; existing Codespace and real agent sessions need independent evidence.

## Research-backed architecture

Treat each operation as a repeatable scientific experiment, not a tool catalog entry:

1. **Observe:** exact target SHA, source ownership/license, environment, provider/version, scope and baseline.
2. **Hypothesize:** choose a constrained behavioral model or an audiovisual change from measured evidence.
3. **Execute:** real tool invocation inside authorized sandbox; preserve raw logs or metrics, executable/tool hashes and resource usage.
4. **Attempt to falsify:** test boundary cases, negative controls, mutant implementations, and regression cases; fuzz or symbolic-check where applicable.
5. **Rank:** compare correctness, evidence coverage, quality, failure rate, p50/p95 latency, CPU/RAM, measured cost and permissions.
6. **Learn:** record both failures and passing hypotheses with provenance; revise the next experiment.
7. **Promote only after separate gates:** host-signed proof, actual agent tool enumeration/call, safety, human artistic acceptance and explicit owner approval.

The Harness remains the **sole authority**, REA analyzes native/JS/managed artifacts, HAZE owns sound, WAVE owns imagery/animation/web/video. No agent may infer execution authority from a shared package, green CI or an installed MCP.

### Native: automatic C synthesis, actually executed

`hazewave.native_behavior_synthesis` now compiles a synthetic owner-created ELF in an isolated tempdir and calls the **executable itself** across all **2001** accepted integers from -1000 to 1000. The synthesis algorithm does **not** inspect the oracle's C source: it infers a three-segment affine/quadratic/affine program from I/O only, discovers two boundaries, generates new C source, compiles the candidate and re-executes the full domain. It requires exact output parity on **every** input, writes a 0600 candidate and receipt, fails on nonmatching grammars and deliberate corrupted oracle outputs.

State: `AUTOMATIC_BOUNDED_BEHAVIORAL_SYNTHESIS` (NOT arbitrary native decompilation).
**What we can claim:** reconstruction for this specific source-owned binary's finite input domain under this explicitly limited grammar. **What we cannot claim:** recovering the original source, handling arbitrary binaries, proof outside -1000..1000, proof of timing/side effects/other external state, automatic Ghidra-guided synthesis, or symbolic universal equivalence.

PR #36 independently proved **REA 6.0.0 + real Ghidra 12.1.4** direct native function Evidence bound to the ELF SHA, as well as a deliberately incorrect manually-authored mutant being rejected. The new black-box synthesis is a **separate** experiment. Future work must join the native function dossier and trace insights to a real hypothesis generator and use coverage-driven mutation plus an SMT or bounded model checking oracle. No Z3/AFL++ install is authorized merely by catalog discovery.

### Audio (HAZE): measured contrast, not subjective quality

`hazewave.av_fidelity_oracle` uses real FFmpeg to generate 440Hz mono WAV, then a second WAV attenuated to 25% amplitude. It runs `volumedetect` on both and verifies approximately **12 dB** of difference, fail-closed if a known change is not measured. This is evidence the FFmpeg audio-metric pipeline is actually operational on a disposable runner.

Still not proven: LUFS EBU R128 integrated loudness, true peak, dynamic range, spectral consistency, reverb/delay character, voice identity, pronunciation, stem quality, mix and mastering subjectivity, Reaper project execution, owner voice `BR_OWNER_V1`. Future HAZE evaluation needs actual rights-cleared references and owner approval, with versioned plugin chains and before/after tracks; never substitute basic volume difference for professional mix quality.

### Video/image (WAVE): measured contrast, not artist approval

The module generates **lossless FFV1** blue and red synthetic videos (160×96, 10 fps), runs FFmpeg `ssim` against identical and deliberately altered sequences, requires identical near 1.0 and altered below 0.99, and stores hashes. This tests actual frame comparison, not whether scrollytelling, color/animation, transitions or audiovisual storytelling are professionally good.

Still not proven: reference-aligned perceptual VMAF/PSNR in long clips, temporal consistency, optical flow, OCR/scene change correctness, 2D cartoon quality, frame-to-timeline/source traceability, artist artwork integration, and controlled Iris rendering for live websites.

### Iris live-site blocker

The prior constrained Iris gateway proves offline owned-fixture PNG over real stdio MCP, **not live-site egress safety**. Playwright `context.route` alone does not guarantee all requests are blocked: redirects are processed as a chain and Service Workers may hide traffic. Require isolated ephemeral profile, Service Workers blocked, explicit network capability denial at the kernel/container layer, redirect/subresource/WS tests and signed target grants before exposing external URLs. Never globally enable raw upstream `iris mcp`.

Primary references:
- REA upstream provider contract: https://github.com/morluto/rea
- Ghidra NSA: https://github.com/NationalSecurityAgency/ghidra
- AFL++ instrumentation/fuzzing: https://aflplus.plus/docs/fuzzing_in_depth/
- Z3 solver: https://microsoft.github.io/z3guide/programming/Z3%20Python/Introduction/
- FFmpeg ebur128/SSIM: https://ffmpeg.org/ffmpeg-filters.html
- Netflix VMAF: https://github.com/Netflix/vmaf
- Playwright network limitations: https://playwright.dev/docs/network

## Existing Codespace — real on-host gates

Use **only** `hazewave-zero-cost-4jxp45676rq6279xx`, preserve the current branch, create a detached worktree at the branch remote's **verified HEAD**. Do not claim success if the terminal is inaccessible. For the present PR:

```bash
# Run inside an already detached, clean worktree on the ONE Codespace.
# Revalidate that the fetched remote SHA matches the reviewed PR HEAD.
export HAZEWAVE_RESEARCH_EXPECTED_SHA="$(git rev-parse HEAD)"
bash scripts/codespaces/research-closed-loop-qualification.sh --preflight
bash scripts/codespaces/research-closed-loop-qualification.sh --native-auto
bash scripts/codespaces/research-closed-loop-qualification.sh --av-metrics

# Existing separately guarded Ghidra and agent paths:
export HAZEWAVE_NATIVE_EXPECTED_SHA="$(git rev-parse HEAD)"
bash scripts/codespaces/native-behavior-rea6-probe.sh --inventory
bash scripts/codespaces/native-behavior-rea6-probe.sh --behavior
bash scripts/codespaces/native-behavior-rea6-probe.sh --ghidra
```

If FFmpeg is missing, `--av-metrics` blocks; qualify installing it through the reviewed A/V tool installer on this same host only after resource/licensing preflight. If Ghidra is missing or incompatible, `--ghidra` blocks. Do not import runner receipts as Codespace proof.

## Gap register / priority for next cycle

| Priority | Proof required | Current actual state |
|---|---|---|
| P0 | Existing Codespace: native Ghidra Evidence + generated C synthesis + A/V oracle | NOT EXECUTED HERE |
| P0 | Actual-agent MCP tools/list+call with reviewed task scope | NOT PROVEN |
| P0 | Signed owner/runtime grants independent of self-issued Harness tokens | NOT PROVEN; no promotion |
| P1 | Ghidra guided symbolic hypothesis plus AFL++ mutation/CBMC/Z3 bounded obligations | NOT PROVEN |
| P1 | Full REA 6.0.0 managed (.NET) positive, Electron JS/ASAR runtime and Frida as separate ops | NOT PROVEN |
| P1 | Iris Chromium isolation with request/redirect/Service Worker/WebSocket denial | NOT PROVEN |
| P1 | HAZE integrated EBU R128/true peak + stem/reference identity and owner review | NOT PROVEN |
| P1 | WAVE long-media VMAF, FFprobe timestamps, scene/time consistency, optical flow | NOT PROVEN |
| P2 | Per-capability inventory beyond 10/124 provider mappings with host measurements | NOT PROVEN |
| P2 | Repeatability on ≥3 host runs, p50/p95 RAM/CPU, incidents and candidate rejection ledger | NOT PROVEN |

All proof records must state host, version, SHA, route, first-party fixture, what observation was *actually* performed, sample/coverage range and what *cannot* be concluded. Preserve existing stock/voice policy and unrelated workspace WIP. No new Codespace, no forced merge, no paid fallback, no global agent registration.
