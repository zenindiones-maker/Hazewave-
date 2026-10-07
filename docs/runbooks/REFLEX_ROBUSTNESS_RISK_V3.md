# Reflex Robustness + Risk V3 Runbook

This runbook upgrades the shadow brain; it does not promote it.

## 1. Repository checks

Run:

    python -m compileall -q src
    python scripts/validate_repository_contracts.py
    pytest

All tests passing establishes repository compatibility only.

## 2. Existing Codespace runtime

Use the existing Codespace and the isolated worktree pattern from REFLEX_SHADOW_RUNTIME_V1.

Current candidate ref:

    work/reflex-robustness-risk-v3

The controller is still:

    scripts/codespaces/reflex-shadow-control.sh

Its `smoke` and `observe` paths now use the option-order ensemble.

Do not create another Codespace, resize the existing one or start extra Colibri servers.

## 3. Robust smoke

Start the one loopback Colibri/Laya server and run:

    bash scripts/codespaces/reflex-shadow-control.sh smoke

A V3 smoke PASS must show:

- one real authenticated System One request;
- multiple order-rotated questions in that request;
- a shadow disposition;
- rotation count;
- winner agreement;
- normalized JSD.

It proves transport + real inference + ensemble execution. It does not prove accuracy.

## 4. Sensory frame

Use existing deterministic reports to construct a frame with:

    build_reflex_sensory_frame(...)

Feed only `frame.model_state()` to a reflex decision.

Do not inject file paths, media bytes, raw Telegram messages, secrets or artistic verdicts.

The first useful deployments are:

- HAZE technical triage from AudioQCReport / ProfessionalAudioAnalysisReport;
- WAVE render triage from VideoQCReport / AnimationQCReport;
- resource pressure advisory from allowlisted runtime counters.

## 5. Benchmark

Build a labeled benchmark from actual Hazewave decision receipts. Every case needs an evidence-backed expected label.

Run `evaluate_reflex_robustness_benchmark()` with the real local predictor.

Required metrics:

- base and ensemble accuracy;
- option-order flip rate;
- state-key-order flip rate;
- mean normalized JSD;
- multiclass Brier;
- ECE.

Do not store raw private media in the benchmark file.

At least 100 cases are required before the benchmark is even review-ready under V3 policy.

## 6. Risk-threshold candidate

After enough labeled calibration samples exist, transform the robustness benchmark/evidence into `RiskCalibrationSample` rows and call:

    select_risk_threshold_candidate(...)

Default evidence gates are 750 total labeled samples and 600 stable accepted samples.

The result is a candidate for human/statistical review only. Never write the returned number back into production policy automatically.

## 7. Calibration hygiene

Separate:

    training
    calibration
    holdout

Do not:

- tune a threshold on holdout;
- evaluate a fine-tuned specialist on its training data;
- count model-generated pseudo-labels as human/QC truth;
- combine samples from incompatible decision keys/model revisions/policy revisions;
- interpret System One concentration confidence as P(correct).

## 8. Runtime/resource boundary

One System One request batches the order rotations. Do not create three Laya processes.

If REAPER, FFmpeg, Blender or another approved creative workload needs the workstation headroom, stop/refuse the reflex operation rather than competing for the machine.

## 9. Next promotion state

V3 can reach:

    REPOSITORY_COMPATIBLE
    ROBUST_LIVE_SMOKE_PROVEN
    SHADOW_ROBUSTNESS_EVIDENCE_AVAILABLE
    RISK_THRESHOLD_CANDIDATE_AVAILABLE

It cannot itself reach:

    PRODUCTION_CALIBRATED
    PRODUCTION_APPROVED
    CANONICAL_PROMOTED
