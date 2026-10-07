# Reflex Latency V1 — measured optimization runbook

This runbook optimizes the physical Colibri/Laya reflex path without changing the
model, precision, option-order ensemble, authority or zero-cost boundary.

## Owner surface

All owner commands are issued from A15/Termux through `hazewave-reflex`. Heavy work
runs in the existing Hazewave Codespace.

The candidate ref is:

    work/reflex-latency-v1

Do not create another Codespace, resize the machine, enable a paid resource, or switch
the owner's active Hazewave checkout.

## Why measure before changing

The first real 3-rotation smoke measured 2836.051 ms end-to-end. One sample is not a
benchmark. The latency layer therefore records warm repeated samples and separates:

    client wall time
    /health time
    /v1/systemone time
    x-colibri-engine-ms
    x-colibri-elapsed-ms
    x-colibri-queue-wait-ms

This identifies whether the limiting term is the C engine, HTTP/server overhead or
queueing.

## Before tuning

A currently attached `hazewave-reflex serve` must be stopped with Ctrl-C in the
Termux tab that owns it. Do not kill arbitrary Codespace processes.

Then from Termux:

    hazewave-reflex doctor
    hazewave-reflex latency-profiles
    hazewave-reflex latency-selected

The doctor must remain `READY_FOR_LIVE_PROBE`.

## Run the bounded sweep

From Termux:

    hazewave-reflex latency-tune

The command fails closed if 127.0.0.1:28080 is already occupied.

For each profile it:

1. starts one loopback-only Laya server;
2. waits for a healthy authenticated local runtime;
3. performs three warmups;
4. records twenty-one identical robust 3-rotation requests;
5. captures wall/health/System One/engine/server/queue timings;
6. requires robust eligibility and output stability;
7. stops only the profile server it created;
8. proceeds to the next profile.

No two Laya servers are intentionally resident at the same time.

## Selection rule

The baseline is `baseline_2t`.

A candidate is persistable only if:

- every measured request passed;
- every measured result remained robust-eligible;
- the selected label is identical to baseline;
- p50 improves by at least 5%;
- p95 is no more than 3% worse than baseline.

If no candidate satisfies all conditions, baseline remains selected.

The durable selection is stored below the runtime state namespace and is bound to the
latency policy digest:

    ~/.local/state/hazewave/reflex/latency/selected-profile.json

Reports live under:

    ~/.local/state/hazewave/reflex/latency/runs/<UTC>/

## Inspect

From Termux:

    hazewave-reflex latency-report
    hazewave-reflex latency-selected

The report is evidence about scheduling only. It is not an accuracy, calibration or
promotion receipt.

## Restart and prove

After tuning, start the normal server from Termux:

    hazewave-reflex serve

In another Termux tab:

    hazewave-reflex smoke

The smoke must still prove:

    LIVE_ROBUST_ENSEMBLE_INFERENCE_PASS
    real_inference_proven=true
    rotation_count=3
    robust_eligible=true
    provider_authority=NONE
    production_calibrated=false

Compare the new smoke to the original 2836.051 ms observation, but use the repeated
latency-tune p50/p95 as the authoritative performance comparison.

## Safety

Do not enable int8 Laya, fast-math, active spin by default, model-revision changes,
rotation reduction or state/head truncation to win the benchmark. Do not feed
synthetic benchmark rows into calibration/training outcomes. If creative workloads
need the workstation, stop the reflex server rather than competing for headroom.


### Sample-size note

The sweep uses 21 measured requests per profile. With the nearest-rank estimator used by the harness, p95 is rank 20 of 21 rather than simply the maximum as it would be with only seven observations. This remains a workstation tuning sample, not a population-level SLO proof; repeat the sweep if host contention or Codespaces placement changes materially.
