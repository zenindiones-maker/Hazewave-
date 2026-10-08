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


## Result of the one controlled live experiment (verified 2026-10-08)

- Exact code SHA: `e4802533d9808bffd186150724a6f1e586d893b1`
- CI: [37854262439](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37854262439), SUCCESS Python 3.12 and 3.14
- LIVE Actions run: [37854251998](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37854251998), SUCCESS
- Original Actions artifact: [11583194560](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37854251998/artifacts/11583194560) (one-day retention); the receipt bytes were independently extracted and SHA-256 rechecked.
- **Exact receipt SHA-256:** `0661132fdd8f4a7fa5a160297a342707ef61449be211c77ed3256be8ea9cfbee`
- Model GGUF SHA-256: `b0638f08417a2d3c8652760462eb5407c6e30173cf9608ad0820757a281eea0e`, 396,704,416 bytes
- llama.cpp exact runtime commit: `d81235049384534c167caea52b85a694f6103d14`
- Model response content SHA-256: `d1cfe0fbabe34a91953f9b23e749c49ab59cc34122c3affb45de97a2ef86874d` (response content not published)
- HARNESS: `model_real_request=true`, `model_real_response=true`, `transport=GITHUB_ACTIONS_CPU_RUNNER_LOOPBACK`
- Independent FFmpeg: reference -21.1 dBFS, processed -33.1 dBFS, attenuation +12.0 dB, negative-control PASS
- Independent quality evaluator: `audio_verifier_result=PASS`, `audio_verifier_error=NONE`, `audio_failure_class=NONE`
- Token count: 249 prompt + 49 completion, total 298
- End-to-end measured Python/audio/model stage elapsed: 3614.4 ms; **not** model-only first-token latency. `maxrss_kib_this_runner_process=26140` is the Python process memory usage, **not** whole-model / llama-server RSS.
- `json_schema_constrained_generation_requested=true`; `json_schema_server_enforcement_independently_proven=false`. This PASS is an independent strict-semantic verdict, not proof that the serving runtime enforced the requested grammar.
- `agent_tools_connected=false`, `independent_case_diversity_proven=false`, `model_benchmark_superiority_proven=false`, `professional_audio=false`, `production_approved=false`, `a15_inference=false`.

### Decision

**Real Qwen3 0.6B inference and one bounded HAZE technical audio assessment: VERIFIED PASS.** Production promotion and professional competency remain **BLOCKED**: this is a single owned synthetic attenuation case, without multiple independent audio failure classes, multi-run stability or artistic/REAPER proficiency.

No raw model response, input owner media, API credential, private gateway address or personal payload is committed. This research PR remains draft and unmerged. The next valid workload is representative distinct audio cases plus complete repeated trials without changes to verification thresholds.
