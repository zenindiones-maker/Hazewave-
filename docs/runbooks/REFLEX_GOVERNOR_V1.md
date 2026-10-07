# Hazewave Reflex Governor V1 Runbook

The Reflex Governor turns the Colibri/Laya lane into a measured selective decision system. It is not a replacement for the Harness and it is not permission to automate consequential decisions.

## 1. Repository validation

Run:

    python -m compileall -q src
    python scripts/validate_repository_contracts.py
    pytest

The repository is only COMPATIBLE when all three pass.

## 2. Real runtime prerequisite

First complete the Colibri local provider runtime proof from:

    docs/runbooks/COLIBRI_LOCAL_PROVIDER_V1.md

Do not claim reflex runtime proof from mocked HTTP tests.

## 3. Deterministic precheck is mandatory

Before invoking execute_reflex_choice:

1. apply explicit human instructions;
2. apply Harness authority/domain/capability policy;
3. apply security and data-classification rules;
4. apply exact deterministic routing rules;
5. invoke the model only if ambiguity remains.

The API requires deterministic_precheck_complete=true.

## 4. Current operating mode: shadow calibration

The checked-in V1 policy has production_calibrated=false for every reflex profile.

Therefore current outputs are evidence only:

- record the recommendation;
- record the distribution and latency;
- continue using the existing deterministic/9Router/human path;
- compare the final ground truth to the reflex recommendation.

Do not flip production_calibrated in-place. Promotion requires a reviewed policy revision.

## 5. Decision-shape rule

Keep one reflex question small and specific.

Current hard limit:

- maximum 8 labels per choice;
- maximum 4 questions per request.

For larger taxonomies, use a hierarchy such as:

    coarse family -> narrow subfamily -> final option

or escalate to the existing reasoning plane.

This avoids the high-cardinality degradation observed in current Laya benchmarks.

## 6. Interpreting uncertainty correctly

Do not treat System One response confidence as P(correct).

For each decision the governor uses:

- winning probability;
- top-two margin;
- normalized entropy;
- latency;
- response consistency.

The returned System One confidence is retained only as a concentration/contract check.

## 7. Outcome capture

After a real ground-truth outcome is known:

    verdict -> build_reflex_outcome(...) -> append_reflex_outcome(...)

Recommended runtime path:

    ~/.local/state/hazewave/reflex/outcomes-v1.jsonl

The ledger contains no raw state. It stores request digest plus labels/probabilities/evidence identity.

Permitted label sources:

- HUMAN
- DETERMINISTIC
- RUNTIME_QC

Do not label a result from another model as HUMAN or deterministic truth.

## 8. Daily calibration report

Use evaluate_reflex_outcomes() over the durable ledger and track:

- accuracy;
- coverage;
- selective risk;
- ECE;
- multiclass Brier;
- p50 latency;
- p95 latency.

A rising coverage number is not automatically good if selective risk rises with it.

No daily job may silently rewrite production thresholds.

## 9. Recalibration readiness

reflex_recalibration_readiness() remains false until both are satisfied:

- 500 labeled outcomes overall;
- 50 labeled outcomes for the target decision key.

These are minimum evidence gates, not automatic approval.

## 10. Hazewave-specific Laya specialist

Once enough clean labels exist, export a de-identified training dataset from labeled outcomes and train a candidate specialist outside the production runtime.

The upstream Laya project provides a free Kaggle 2xT4 fine-tuning path and fits calibration temperatures as part of its training workflow. Hazewave may use that workflow as a development surface, but a resulting checkpoint is still only a candidate.

Required sequence:

    LABEL -> SPLIT -> TRAIN -> CALIBRATE -> HOLDOUT_EVAL -> SECURITY_REVIEW
    -> WORKSTATION_RUNTIME_PROOF -> HUMAN_REVIEW -> PRODUCTION_APPROVED

Never train on the holdout set and never promote on training accuracy.

## 11. Promotion evidence

A future production-calibrated policy revision must identify:

- dataset digest;
- train/calibration/holdout split;
- model revision and weight digest;
- decision keys covered;
- accuracy;
- coverage;
- selective risk;
- ECE;
- Brier;
- latency;
- failure classes;
- runtime workstation identity;
- human approval.

Until that receipt exists, the reflex brain remains shadow/advisory.
