# Reflex Binary Research — governed open-source evidence gate (V1)

Status: CANDIDATE / NOT PRODUCTION-APPROVED.

## Boundaries

This read-only check supplements the existing Hazewave HAZE/WAVE Reverse Engineering Lab (PR #27). Its scope is narrower: **integrity and provenance of the pinned, locally derived Colibri/Laya experiment binaries**. The wider research lab owns authorized audio/visual target studies. Neither toolset has policy, provider, promotion, production or publishing authority.

The current 2-vCPU/8-GB Codespace remains unchanged. This feature does not install tools, download anything, start/stop a server, perform inference or modify the stock executable. The operator invokes it explicitly from A15:

```bash
hazewave-reflex engine-re-doctor
```

The control plane verifies the exact existing Codespace, existing branch, clean pinned Colibri source and stock binary, then audits the four pinned derived artifacts (direct_y_store_v1 and MC 144/408/816 V2). It detects tampered metadata, wrong MC, wrong upstream, symlink aliases, reused byte-identical binaries and reused inodes. A mismatch is **BLOCKED**, never PASS.

Evidence: a new owner-local 0600 JSON receipt under `~/.local/state/hazewave/reflex/research/audits/`. Receipts do not contain model weights, prompt content or credentials. Existing receipts remain untouched.

### Interpretation

- `REFLEX_RE_RESEARCH_AUDIT=PASS`: the limited file-integrity checks passed. **Not** a semantic, numerical, memory-safety, robustness or runtime-performance proof.
- `REFLEX_RE_RESEARCH_AUDIT=BLOCKED`: retain the receipt, investigate and do not activate any derived binary. The existing stock runtime is not stopped by this audit.
- `NOT_INSTALLED` in the optional tool inventory does not block the binary audit. It is a capability gap, not authorization to auto-install.

This is not a declaration that the broader HAZE/WAVE laboratory is installed or ready. It requires separate Codespace runtime evidence and its own doctor.

## Open-source tool strategy

Build the research pipeline progressively, rather than installing all analyzers into the shared Codespace:

| Stage | Open-source tool | Appropriate use | Gate |
| --- | --- | --- | --- |
| 0. Baseline | git, SHA-256, binutils (`readelf`, `objdump`, `nm`) | provenance, ELF sections and symbols | present + pin |
| 1. Evidence | Rizin; diffoscope | static disassembly and binary-build differences | rights/license/source check |
| 2. Diagnostics | LLVM `llvm-mca` | model estimated throughput for hot assembly; not proof of wall-time speed | target CPU + reproducibility |
| 3. Sampling | Linux `perf` / FlameGraph | user-space hotspots **only if** kernel/host permissions allow | privileges and source checks |
| 4. Controlled profiling | Valgrind Callgrind | call graphs on small, bounded inputs; high overhead | resource budget |
| 5. Deep decompilation | Ghidra `analyzeHeadless` | structurally unknown binaries or third-party authorized targets | isolated host, memory budget, explicit case |
| 6. Memory safety | ASan/UBSan | instrumented synthetic harness builds in separate diagnostic worktree | never the stock process |
| 7. Performance confirmation | repeated, randomized/interleaved A/B runs | independent trials, drift/variance management | latency/p95/robustness policy |

**Not defaults:** BOLT requires suitable profiles and build layout; do not treat it as a magic flag. Ghidra and Valgrind are heavyweight, so reserve them for cases where source-first inspection and the in-tree Colibri phase profiler cannot answer the question.

External REA/Hopper providers: REA itself is MIT, but Hopper is separately licensed; it must not be used in a strictly free/open-source lane. If the separate HAZE/WAVE lab uses REA, explicitly configure the Ghidra provider without Hopper fallback.

Repository licensing: installing open-source tools does not automatically grant this Hazewave repository an open-source license. Publication or relicensing of Hazewave code requires an explicit owner license decision.

## Scientific experiment protocol

1. Record a hypothesis linked to a line/function/hotspot and resource signature.
2. Preserve pinned upstream/model/checkpoint source and SHA-256, f32 path, three-rotation ensemble and stock comparison.
3. Build each candidate in an immutable distinct location; ensure no metadata or binary aliases.
4. Prove correctness against unmodified stock before discussing speed; also test edge paths, variable dimensions and overflow cases where relevant.
5. Run repeated, order-balanced trials with warmups and stable runtime fingerprints; report p50, p95, spread, failed requests and CPU contention.
6. Retain both positive and negative experiments; no cherry-picking fastest sample, no numeric result invented from static inspection.
7. Enforce existing **at least 5% p50** improvement, **at most 3% p95 regression**, exact output contract and all stability gates. Any missing proof is BLOCKED. Activation remains an independent human-governed operation.

Known boundary: the latest MC V2 sweep retained stock; all cases indicated `robust=False` and `production_calibrated=false`. That sweep is not performance acceptance.

## References

- Ghidra headless: https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/RuntimeScripts/support/analyzeHeadlessREADME.md
- Rizin: https://github.com/rizinorg/rizin
- Linux perf security: https://docs.kernel.org/admin-guide/perf-security.html
- Valgrind Callgrind: https://valgrind.org/docs/manual/cl-manual.html
- LLVM llvm-mca: https://llvm.org/docs/CommandGuide/llvm-mca.html
- Google Benchmark variance: https://github.com/google/benchmark/blob/main/docs/reducing_variance.md
- LLVM AddressSanitizer: https://clang.llvm.org/docs/AddressSanitizer.html
- LLVM UndefinedBehaviorSanitizer: https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html
- diffoscope: https://diffoscope.org/
