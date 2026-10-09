# HAZE V5 — one authorized measured-semantic inference

Experimental hypothesis (falsifiable): the Qwen3-0.6B one-call gain classification may fail because it previously saw only `metric=attenuation_db, measured_value=12.0`, without both FFmpeg reference/processed mean levels or the task-specific permitted tolerance. Schema-only changes previously fixed missing keys but did not fix semantic interpretation.

This controlled V5 request provides FFmpeg mean levels (dBFS, **not LUFS**), the difference definition, and the authorized task `PRESERVE_REFERENCE_LEVEL` with a predeclared 1 dB tolerance. **No oracle label enters the prompt.** The deterministic guard separately expects large loss in the synthetic 0.25 gain case and abstains when a model reports `NO_ISSUE_DETECTED`, but never rewrites or upgrades the SLM-only grade.

The real diagnostic is admitted only by a single push commit carrying `[haze-diagnostic-onecall]` on the dedicated V5 branch. The workflow must execute exactly `--repetitions 1 --diagnose-case gain_loss_12db`, record the exact commit and pinned SHA256 model/runtime, and preserve the natural model output's failure if observed. Plain pushes are not live-model triggers.

Prior genuine runs: 37860280849 (MISSING_KEYS, FAIL), subsequent user-observed 12 dB semantic NO_ISSUE_DETECTED (FAIL); PR51 latest diagnostic was skipped. The V5 CI (37866458564) passed source_truth plus Python 3.12/3.14 tests, but is not real model inference.

No authority to master audio, publish, merge or certify HAZE. No A15 runtime changes, paid provider, new Codespace, or Colibri/Reflex restart. Independent unseen holdout evaluation remains a separate requirement.
