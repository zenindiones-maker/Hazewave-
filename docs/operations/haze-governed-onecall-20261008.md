# HAZE — Governed one-call structural probe V2

**Experiment branch:** work/haze-governed-structure-probe-v2
**Reviewed base:** a8479a6190db51b7abeca071ccead1e3ac6e2c85 (Harness source-truth PR #50).
**Original HAZE model baseline:** 20482f93299e398e08a38a0e215a613ff37c136e (PR #49).

## Reason for the bounded experiment

Run 37860280849 returned one real Qwen3-0.6B reply with MISSING_KEYS and independent grade FAIL. The next code change to src/hazewave/actions_slm_multicase.py enumerated all four required JSON keys without disclosing the correct audio finding; CI 37860918920 passed. The revised model response has not yet been measured.

## Single authorized experiment

Reuse exactly the official Qwen3-0.6B GGUF file digest b0638f08417a2d3c8652760462eb5407c6e30173cf9608ad0820757a281eea0e and pinned llama.cpp source d81235049384534c167caea52b85a694f6103d14. Existing synthetic gain case: FFmpeg 12dB attenuation. One response only.

Immutable constraints: standard public GitHub-hosted CPU only, A15 control only, no Codespace, no paid providers, no owner media, no installation outside disposable runner. Existing deterministic semantic verifier remains unchanged.

Expected evidence: model_response_sha256, model_json_shape, observed_finding_enum, independent semantic grade, exact model runtime identifiers, FFmpeg controls, bounded create-only receipt hash. A syntactically valid but wrong conclusion is FAIL. This is not a 3x3 reliability benchmark.

No automatic professional promotion or production approval. CI on this branch includes the new exact-Git-source security job. Stop rather than running additional full cohorts if a model-specific cause remains unidentified.
