# ADR-0008 — Hazewave Reflex Governor: Selective Cascade, Abstention and Calibration

- Status: ACTIVE / DEVELOPMENT IMPLEMENTATION
- Date: 2026-10-07
- Authority: HAZEWAVE_HARNESS
- Extends: ADR-0007 Colibri Local Decision Plane
- Supersedes: ADR-0007 confidence-gating semantics only

## Context

Colibri System One is useful for fast local closed-set decisions, but deeper review found an important semantic boundary: the response field named `confidence` is not a calibrated probability that the selected answer is correct. In Colibri's System One contract it is an option-concentration statistic derived from the winning probability and number of options. Treating that number as a correctness probability would create false assurance.

Independent September 2026 System One benchmarking also shows that Laya's zero-shot quality changes materially with task shape. It performs well on small label sets such as binary sentiment, reasonably on six-way TREC, and poorly on 77-way Banking77. The same benchmark reports severe ECE degradation on the 77-label case. Laya's own current model card is explicit that the base checkpoints are not universal production specialists and that domain fine-tuning is where large gains appear.

Therefore the useful architecture is not "Laya decides". It is a selective local reflex layer that may abstain, escalate, collect outcomes and later become a Hazewave-specific specialist after measured calibration.

## Decision

Hazewave adds a governed Reflex Governor around Colibri.

The execution hierarchy is:

`DETERMINISTIC_RULE -> COLIBRI_LAYA_SELECTIVE -> 9ROUTER_ZERO_COST_REASONING -> HUMAN_REVIEW`

The Harness remains the only execution authority. Every reflex result is a recommendation with `grants_execution_authority=false`.

### 1. Deterministic-first

If the answer is already encoded by project policy, media type, capability ownership, security policy, explicit human instruction or another deterministic contract, no model may override it. The high-level reflex execution entry point requires a caller assertion that deterministic prechecks completed.

### 2. Selective prediction instead of forced prediction

The Reflex Governor evaluates multiple uncertainty signals:

- top-option probability;
- top-1 minus top-2 probability margin;
- normalized entropy;
- latency budget;
- exact probability-mass validity;
- consistency between the returned winner and the argmax;
- consistency between Colibri's documented concentration formula and the returned `confidence` value.

A reflex answer may be accepted as a recommendation, shadowed, or escalated. Low-confidence or ambiguous inputs are not coerced into a winner.

This follows the selective-classification / reject-option principle: coverage is deliberately traded for lower decision risk.

### 3. Small decision spaces

The current governor caps a single choice question at eight labels. Larger taxonomies must be decomposed hierarchically or escalated.

This is not an upstream API limitation. It is a Hazewave reliability policy based on the observed sharp accuracy/calibration degradation of the current base model on high-cardinality choices.

### 4. Calibration-before-activation

All current profiles have `production_calibrated=false`.

Even the route profile remains shadow-only under the checked-in V1 policy until Hazewave-specific labeled outcomes exist. This intentionally prevents repository compatibility or upstream benchmark results from being presented as Hazewave production accuracy.

Initial threshold values are provisional evaluation working points, not calibration claims.

### 5. Consequence-sensitive profiles

The V1 profiles distinguish consequence level:

- `decision.route`: designed for selective local routing once calibrated.
- `decision.gate`: shadow-only; consequential gates remain deterministic or human-controlled.
- `decision.score`: shadow-only until task-specific scoring calibration exists.

No reflex output may self-approve security, promotion, publication or canonical mutation.

### 6. Privacy-preserving outcome ledger

Hazewave records labeled reflex outcomes for future calibration and specialization, but does not persist raw state through the reflex ledger.

The ledger stores:

- request digest;
- decision key;
- model and policy identity;
- predicted and actual labels;
- probability distribution;
- whether the governor would have accepted the decision;
- label source;
- label-evidence digest tying the label to a human/deterministic/QC receipt;
- whether the sample would have passed the current selective thresholds even while the profile is still shadow-only;
- latency;
- timestamp.

Accepted label sources are human review, deterministic ground truth and runtime QC.

### 7. Calibration metrics

The calibration harness reports:

- accuracy;
- shadow coverage (the fraction that would pass current thresholds);
- selective risk if those threshold-eligible samples were activated;
- Expected Calibration Error;
- multiclass Brier score;
- p50 latency;
- p95 latency.

Raw System One `confidence` is not used as a correctness probability.

### 8. Learning without self-mutation

Hazewave may use its labeled decision history to fine-tune a future Laya specialist. The upstream Laya project reports a large improvement after task-specific fine-tuning and calibration on its own typed-decisions workflows; that is evidence for specialization, not evidence that the same checkpoint is already correct for Hazewave.

The V1 learning boundary therefore requires:

- at least 500 labeled outcomes overall;
- at least 50 labeled outcomes for the target decision key;
- a held-out evaluation split;
- no online threshold mutation;
- no automatic model promotion;
- human review;
- real runtime proof.

Training data must come from Hazewave-labeled outcomes, not self-generated pseudo-labels presented as truth.

## Research basis

Primary / high-value references reviewed for this decision:

- JustVugg/colibri System One documentation and v2.0.0 source.
- Colibri System One benchmark repository and published September 2026 benchmark.
- convaiinnovations/laya and laya-typed-decisions model cards.
- El-Yaniv & Wiener, selective classification and risk-coverage.
- Geifman & El-Yaniv, selective classification / reject option.
- Guo et al., neural-network calibration and temperature scaling.
- Angelopoulos et al., conformal risk control.
- RouteLLM, preference-trained dynamic routing.
- FrugalGPT, learned model cascades.
- Cluster, Route, Escalate (2026), two-stage routing plus quality-estimation escalation.

These references motivate the architecture. They do not grant production approval.

## Runtime proof required

Repository CI can prove contract and implementation compatibility only.

`RUNTIME_PROVEN` requires the real Hazewave workstation to demonstrate:

- pinned Colibri and Laya identities;
- authenticated loopback-only runtime;
- representative reflex requests;
- measured p50/p95 latency;
- RAM and disk headroom;
- outcome ledger durability;
- restart/recovery;
- no paid egress;
- no raw private-media persistence.

`PRODUCTION_CALIBRATED` is a later state and requires Hazewave-labeled evaluation data.
