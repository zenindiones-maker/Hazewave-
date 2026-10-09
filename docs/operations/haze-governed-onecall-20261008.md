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

## Observed outcome — genuine model response, semantic FAIL

- Exact source SHA: 7235fee64862783b504662cffa29d09f75555094.
- Live Actions: https://github.com/zenindiones-maker/Hazewave-/actions/runs/37864871352 — FAIL intentionally, exit 21 (strict independent verifier).
- Public artifact: https://github.com/zenindiones-maker/Hazewave-/actions/runs/37864871352/artifacts/11588300490. Create-only receipt SHA256: a6bddae9928fbcbd219de395d00038af60ade88c3ce205da5cac6d68a00c9671.
- One observed real Qwen3-0.6B response; Qwen model SHA-256 remained b0638f08417a2d3c8652760462eb5407c6e30173cf9608ad0820757a281eea0e. No Android inference.
- Tested case: gain_loss_12db. Output structure: SCHEMA_KEYS_AND_TYPES_VALID (correct schema), finding enum: NO_ISSUE_DETECTED (wrong semantic classification for the 12dB attenuation). Independent grade: FAIL.
- Prior run 37860280849 was MISSING_KEYS. Explicit four-key instructions corrected only output structure; model domain finding still wrong. Do not equate schema repair with technical competence.
- CI for this live attempt: https://github.com/zenindiones-maker/Hazewave-/actions/runs/37864886828 — SUCCESS, 857 passed / 2 skipped in each Python 3.12/3.14; independent source_truth governance check SUCCESS, exact branch SHA/tree verified. This software CI does not override the failed real model grade.
- Root cause class: MODEL_SEMANTIC_MISCLASSIFICATION. Whether weak domain reasoning, prompt design, or other limits cause it is NOT established. A further blind 3x3 retry is unjustified.
- HAZE_PROFESSIONAL=FALSE; WAVE_PROFESSIONAL=FALSE; MODEL_PRODUCTION_APPROVED=FALSE.
- Next high-value action: isolate model understanding against audited technical examples and deterministic HAZE fallback/ABSTAIN without pretending the model is correct; benchmark alternate compact weights only after separate license/identity/cost qualification and held-out cases. Owner approval is required for any production promotion.

No new model, Codespace, A15 install, paid workstation, merge, force push, publishing, credential change or stock Colibri/Reflex restart occurred.
