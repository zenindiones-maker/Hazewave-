# HAZE V5 — one authorized measured-semantic inference

Experimental hypothesis (falsifiable): the Qwen3-0.6B one-call gain classification may fail because it previously saw only `metric=attenuation_db, measured_value=12.0`, without both FFmpeg reference/processed mean levels or the task-specific permitted tolerance. Schema-only changes previously fixed missing keys but did not fix semantic interpretation.

This controlled V5 request provides FFmpeg mean levels (dBFS, **not LUFS**), the difference definition, and the authorized task `PRESERVE_REFERENCE_LEVEL` with a predeclared 1 dB tolerance. **No oracle label enters the prompt.** The deterministic guard separately expects large loss in the synthetic 0.25 gain case and abstains when a model reports `NO_ISSUE_DETECTED`, but never rewrites or upgrades the SLM-only grade.

The real diagnostic is admitted only by a single push commit carrying `[haze-diagnostic-onecall]` on the dedicated V5 branch. The workflow must execute exactly `--repetitions 1 --diagnose-case gain_loss_12db`, record the exact commit and pinned SHA256 model/runtime, and preserve the natural model output's failure if observed. Plain pushes are not live-model triggers.

Prior genuine runs: 37860280849 (MISSING_KEYS, FAIL), subsequent user-observed 12 dB semantic NO_ISSUE_DETECTED (FAIL); PR51 latest diagnostic was skipped. The V5 CI (37866458564) passed source_truth plus Python 3.12/3.14 tests, but is not real model inference.

No authority to master audio, publish, merge or certify HAZE. No A15 runtime changes, paid provider, new Codespace, or Colibri/Reflex restart. Independent unseen holdout evaluation remains a separate requirement.

## Non-inference cancellation observed and remediated

Initial V5 run [37866566261](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37866566261) was **CANCELLED during pinned llama.cpp build**. Its real-model inference step was SKIPPED. This is not an accuracy result and produces no successful model receipt. Root cause: workflow-level `concurrency.group` was by Git ref and `cancel-in-progress: true`, so an ordinary later branch push, whose live job was itself skipped, could still cancel an authorized live execution.

V5 remediation commit `a548c9368cec9de1932caccb76675811ed316aeb` scopes concurrency by immutable `github.sha` with `cancel-in-progress: false`; the explicit marker remains required, so unmarked commits do not initiate model inference. This fix is a separate operational correction, not a semantic model PASS.

## Genuine V5 measured-context inference — run 37866993358

Pinned SHA `9c2691073e12e8d34ae15b379c575e8687d21381`, genuine runner loopback, Qwen3-0.6B Q4_K_M SHA256 `b0638f08417a2d3c8652760462eb5407c6e30173cf9608ad0820757a281eea0e`, pinned llama.cpp `d81235049384534c167caea52b85a694f6103d14`. FFmpeg independently measured mean levels `reference=-21.1 dBFS`, `processed=-33.1 dBFS`, `attenuation=+12.0 dB`, under task `PRESERVE_REFERENCE_LEVEL` and predeclared 1 dB tolerance.

The one real model response was `SCHEMA_KEYS_AND_TYPES_VALID`, `observed_finding_enum=ATTENUATION_DETECTED`, but `verifier_result=FAIL`, `verifier_failure_class=ACTION_MISMATCH`. The actual incorrect action enum is not retained by this minimized receipt and must not be invented. The safeguarded result was `haze_decision=ABSTAIN`, `abstention_reason=MODEL_CONTRADICTS_MEASUREMENT`. Audit receipt hash `54a5df398645cb4192590bf9aa14588ae876e2e84af5ff3b376ba96f0203c62f`; retained artifact ID `11588558427` from run `37866993358`. **Real 1-case model accuracy = 0/1 for the combined finding+action contract; finding alone matched in 1/1, but neither estimate generalizes to unseen audio.** No held-out benchmark.

An isolated improvement experiment changes just the general `finding -> action` taxonomy instruction for **all four classes equally**, without encoding the observed case's correct label. This is guided schema adherence and does not demonstrate independent mastering expertise even if it succeeds.
