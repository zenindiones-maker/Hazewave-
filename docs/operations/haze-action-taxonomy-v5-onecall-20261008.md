# V5 controlled single-call taxonomy experiment

**Hypothesis from genuine run 37866993358:** Qwen3-0.6B correctly selected ATTENUATION_DETECTED for the independent 12.0 dB loss but did not select its required technical review action; independent failure_class=ACTION_MISMATCH. This is not an incorrect amplitude measurement and does not prove domain competence.

Single variable: give the model a general finding-to-safe-action taxonomy for all four enum classes, identical for every case. Do not disclose the case-specific oracle classification; do not alter grading criteria, schema, FFmpeg evidence, model GGUF hash, llama.cpp SHA, or quantization.

**Authorization:** one additional single-case diagnostic inference on public ephemeral GitHub Actions CPU, case `gain_loss_12db`, no 3×3 repetitions. The run is expected to produce genuine model output and an independent grade. A PASS would be guided adherence to a known action taxonomy for this known case only, not professional certification, not holdout evidence or mastering authority. A FAIL remains blocked. The previous run's audit receipt hash is `54a5df398645cb4192590bf9aa14588ae876e2e84af5ff3b376ba96f0203c62f`.

Software CI green at `37867428404`; no A15 changes, no Codespace creation, no paid models, no publish or merge.
