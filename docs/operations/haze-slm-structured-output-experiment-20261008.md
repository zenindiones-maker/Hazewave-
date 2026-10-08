# HAZE small-model structured-output experiment — 2026-10-08

## Independent observed baseline

- GitHub Actions run: https://github.com/zenindiones-maker/Hazewave-/actions/runs/37852051966
- Runtime: public standard Linux GitHub-hosted runner, *not* Android A15 or Codespace
- GGUF: Qwen3-0.6B Q4_K_M, SHA-256 `b0638f08417a2d3c8652760462eb5407c6e30173cf9608ad0820757a281eea0e`
- CPU llama.cpp: `d81235049384534c167caea52b85a694f6103d14`
- Observed FFmpeg gain: 12.0 dB attenuation, independent negative-control PASS
- Live language model response: OBSERVED; response hash `62a40be76a879f3864727e2c25a82a0152f5ab16dd20facfffd96fb73a5c84d3`
- Technical grade: FAIL; first receipt `2db2ce6df401f3d149cf7c6a8a8c11f532a805d0cfce3811f39ef1ae60816c96`.
- Diagnostic limitation: the historical receipt saved only generic `OUTPUT_SCHEMA_OR_SEMANTICS_INVALID`. Do **not** infer which field failed from this receipt.

## Single justified next experiment

Use exactly the same model digest, inference runtime, synthetic FFmpeg test and original strict Harness evaluator. Change only the request output constraint to an upstream llama.cpp-documented JSON schema and add fail-closed **enum-only** rejection diagnostics. Both semantic finding and action alternatives remain available to the model; grammar does not encode the right answer. A schema-conformant but wrong decision **must still fail**.

- RED before GREEN: CI `37854018253` showed 4 expected failures for missing schema-builder/categorizer.
- GREEN: CI `37854117118` Python 3.12+3.14 SUCCESS on SHA `b60e9ce51a2039e4d914c196094381746e833318`.
- Trigger one isolated live Actions experiment on this updated branch. Do not reuse a failed attempt as success.
- Do not persist raw model text, audio media, access tokens, or A15 data in public artifacts.
- The structured-output flag means *requested*, not independent proof that the server enforced the schema. The strict Harness grader and negative controls remain authoritative.

## Non-negotiable status

`MODEL_INFERENCE` must be read from actual runner output. `HAZE_PROFESSIONAL=false`, `WAVE_PROFESSIONAL=false`, `PRODUCTION_APPROVED=false`, `MODEL_SUPERIORITY_PROVEN=false`, even if this single case passes. No merge, paid workstation, A15 model, Codespace restart, Colibri restart or unreviewed promotion.
