# ADR-0011 — Reflex latency tuning by measured per-host profiles

Status: ACTIVE

## Context

The first physical robust Laya smoke on the existing Hazewave Codespace completed at
`c90e482266e2ee3a39763354e8172c1df484c3a7` with a 3-rotation option-order ensemble,
winner agreement 1.0, normalized JSD 0.0021258774 and end-to-end Colibri latency
2836.051 ms. That is inside the provisional 3000 ms route ceiling, but too close to
the boundary to treat as operational headroom.

The workstation is constrained to the existing 2-vCPU / 8-GB Codespace and also hosts
creative workloads. A latency optimization therefore has to improve the exact robust
decision workload without increasing authority, changing the model, weakening the
ensemble, silently truncating input, or starving REAPER/FFmpeg/WAVE work.

Colibri v2.0.0 already compiles Laya with `-O3 -march=native -fopenmp`, batches all
questions of a System One request in one forward pass, and exposes engine, server and
queue timing through the decision serving path. The supported OpenMP runtime controls
are host-sensitive. An optimization that helps a many-core server is not assumed to
help this 2-vCPU guest.

## Decision

Hazewave adopts a measured latency profile layer:

1. Preserve the exact pinned Colibri source, pinned Laya revision, weight SHA-256,
   f32 execution behavior and 3-rotation robust ensemble.
2. Instrument each System One call with:
   - end-to-end client latency;
   - health request latency;
   - System One HTTP latency;
   - Colibri `x-colibri-engine-ms`;
   - Colibri `x-colibri-elapsed-ms`;
   - Colibri `x-colibri-queue-wait-ms`.
3. Compare a bounded allowlist of OpenMP scheduling profiles sequentially, one Laya
   server at a time, on the actual Codespace.
4. Warm each profile before measurement and use repeated samples with p50 and p95,
   not a single fastest observation.
5. A non-baseline profile may persist only when all measured requests succeed,
   robust eligibility remains true, the selected label does not drift, p50 improves
   by at least 5%, and p95 is no more than 3% worse than baseline.
6. Bind any selected profile to the latency-policy SHA. Policy drift invalidates the
   selection and fails closed instead of silently reusing it.
7. The selected profile changes scheduling only. It grants no execution, production,
   security, publication, model-promotion or threshold-promotion authority.

## Candidate profiles

The first bounded sweep is intentionally small:

- `baseline_2t`: two OpenMP threads;
- `single_1t`: one thread, to detect barrier/oversubscription cost;
- `close_2t`: two threads pinned close to cores;
- `spread_2t`: two threads spread across cores;
- `passive_close_2t`: close binding with passive wait and no libgomp spin.

Active spin is deliberately not a default candidate. The workstation is shared with
creative workloads and upstream Colibri evidence shows wait-policy tuning can regress
when the worker team competes with other critical work.

## Explicit non-decisions

This ADR does not authorize:

- Laya int8;
- `-ffast-math` or another numerical-contract change;
- fewer robustness rotations;
- shorter Laya state/head limits;
- a different Laya checkpoint or source revision;
- automatic model/threshold promotion;
- a larger or paid Codespace.

Those changes affect quality, robustness, numerical fidelity, cost or architecture
and require separate evidence.

## Runtime lifecycle

`hazewave-reflex latency-tune` is an explicit maintenance operation. It refuses to
run while port 28080 is occupied, starts exactly one profile server at a time, records
profile reports, stops only the server it started, selects a profile under the policy,
and then requires a normal server restart.

Normal `hazewave-reflex serve` loads the selected measured profile. In the absence of
valid measured evidence it uses `baseline_2t`.

## Evidence boundary

Repository CI proves implementation compatibility only. The profile winner can be
claimed only after `latency-tune` runs on the existing Codespace and leaves durable
profile/selection receipts. A faster profile does not prove model accuracy or
production calibration.
