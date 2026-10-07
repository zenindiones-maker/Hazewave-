# ADR-0010 — Reflex Robustness, Sensory Frame and Risk-Control V3

- Status: ACTIVE / DEVELOPMENT IMPLEMENTATION
- Date: 2026-10-07
- Authority: HAZEWAVE_HARNESS
- Extends: ADR-0008 and ADR-0009
- Production authority: NONE

## Context

The local reflex lane is useful only if its recommendation is stable under harmless presentation changes and if its inputs are grounded in deterministic media/runtime evidence rather than raw private media or free-form text.

Laya/System One is a closed-set decision system, but the ordering of choice labels can influence logits. A single answer therefore is not sufficient evidence for a robust Hazewave route.

Hazewave already has deterministic AudioQCReport, ProfessionalAudioAnalysisReport, VideoQCReport and AnimationQCReport contracts. These are better reflex inputs than media bytes because they are bounded, inspectable, reproducible and compatible with the existing private-media boundary.

A fixed probability threshold is also not a statistical guarantee of correctness. Risk thresholds require labeled calibration evidence, a held-out evaluation boundary and an explicit statistical assumption.

## Decision

Hazewave adds three subordinate layers:

1. **Option-order ensemble** for `decision.route`.
2. **Reflex Sensory Frame** built only from deterministic project reports and an allowlisted set of runtime metrics.
3. **Risk-control candidate generator** that may propose, but never activate, a threshold.

The Harness remains sole authority.

## Option-order ensemble

For a choice with N labels, the runtime generates cyclic rotations up to the configured maximum. The rotations are sent in **one System One HTTP request** as separate typed questions against the same state.

This is deliberately different from starting multiple model processes. It preserves the one-server resource boundary and uses Laya's batch-of-questions execution model.

The result aggregates probabilities by arithmetic mean. The governor records:

- the top label from every rotation;
- winner agreement;
- normalized Jensen-Shannon divergence across the distributions;
- aggregate probabilities;
- aggregate winner and peak probability.

Current shadow policy requires full winner agreement and normalized JSD <= 0.08 before the result is marked `robust_eligible`. These are evaluation gates, not production-calibrated guarantees.

If a future calibrated route would otherwise be accepted, order instability forces escalation instead.

## Sensory Feature Frame

`HazewaveReflexSensoryFrame/v1` may contain only sanitized deterministic signals from:

- `AudioQCReport/v1`;
- `ProfessionalAudioAnalysisReport/v1`;
- `VideoQCReport/v1`;
- `AnimationQCReport/v1`;
- allowlisted runtime metrics.

The frame explicitly excludes:

- media bytes;
- source/output paths;
- source/output hashes as model features;
- credentials/secrets;
- frame arrays;
- artistic or creative verdicts;
- arbitrary runtime metadata such as hostname.

The frame digest is computed only over the sanitized signal object. The model-facing state therefore contains technical evidence, not raw private media.

This preserves a key boundary: deterministic analyzers sense the world; the reflex model classifies the resulting bounded state.

## Robustness benchmark

The benchmark harness evaluates at least:

- base accuracy;
- ensemble accuracy;
- option-order flip rate;
- state-key-order flip rate;
- normalized JSD;
- multiclass Brier score;
- ECE.

Benchmark case results contain identifiers, expected/predicted labels and metrics, not raw case state.

A benchmark requires the configured minimum case volume before review readiness. Review readiness is not production approval.

## Risk control

V3 uses a conservative one-sided Hoeffding upper bound over labeled Bernoulli errors as a **candidate-generation mechanism**.

For a threshold candidate:

`upper_risk = empirical_risk + sqrt(log(1/delta)/(2n))`

clamped to 1.

The default policy requires:

- at least 750 labeled samples total;
- at least 600 accepted stable samples at the candidate threshold;
- target selective risk <= 0.05;
- delta = 0.05.

The method assumes that the calibration examples are sufficiently representative/independent for the bound to be meaningful. That assumption MUST be reviewed. Distribution shift invalidates the interpretation.

This is not claimed to be conformal risk control or LEC. A later revision may introduce those methods after a Hazewave-specific validation set exists.

The output state is always `CANDIDATE_ONLY_HUMAN_REVIEW_REQUIRED` or a fail-closed evidence state. It has `activation_authority=NONE` and cannot modify `config/reflex-governor-v1.json`.

## Shadow runtime integration

The existing Codespace shadow observer now routes `decision.route` through the option-order ensemble.

Receipts add:

- rotation count;
- winner agreement;
- normalized JSD;
- robust eligibility;
- robustness reasons.

The observer stays shadow-only and continues to use the base aggregated ReflexVerdict when building a labeled outcome. This preserves the existing append-only outcome schema while the robustness evidence is stored in the observation receipt.

## Promotion boundary

None of these conditions grant production authority:

- repository CI PASS;
- robustness benchmark PASS;
- low JSD;
- full winner agreement;
- a risk-threshold candidate;
- a successful synthetic smoke request.

Production activation still requires real Codespace inference, Hazewave-labeled calibration and holdout evaluation, security review and human approval.
