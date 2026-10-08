# HAZE small-model multi-case recovery checkpoint — 2026-10-08

## Source-of-truth baseline (already verified, do not rerun)
- [PR #48](https://github.com/zenindiones-maker/Hazewave-/pull/48) HEAD `6e09d26226e9adfb04030b296032cdda239faa8c` — CI [37854840809](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37854840809): PASS.
- First real Qwen3-0.6B answer failed strict audio semantics [37852051966](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37852051966).
- Controlled JSON-schema experiment with **same exact GGUF SHA** `b0638f08417a2d3c8652760462eb5407c6e30173cf9608ad0820757a281eea0e` and llama.cpp `d81235049384534c167caea52b85a694f6103d14` returned a real PASS at [37854251998](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37854251998), receipt SHA `0661132fdd8f4a7fa5a160297a342707ef61449be211c77ed3256be8ea9cfbee`. Still one case, no HAZE/WAVE professional approval.

## Implemented multi-case regression and oracle validation
- [PR #49](https://github.com/zenindiones-maker/Hazewave-/pull/49) is draft stacked on PR #48, isolated development branch `work/haze-actions-multicase-reliability-v1`.
- Exact FFmpeg oracle run [37858405364](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37858405364) **SUCCESS**: three owned synthetic cases and negative controls. General CI [37858409917](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37858409917) **SUCCESS** on Python 3.12/3.14.
- Gain test: 12.0dB attenuation, source SHA `05c82ef95094257dfa2505243dc3b7b067d928d8db45582945288c9052e1e255`, processed SHA `724bd5ced073bdfe9b111d8fa5b152a1fe2ae4247d2ced41fdb9c5756863b3b3`.
- Silence test: 1.0s detected in processed WAV, none in reference; source SHA `46c3907e4c1d6e97301b6c9431a024773fbfa1803d63bf973e3e47390f04d76a`, processed SHA `2f9039fb7e2c15d743271adff11d21badd1c7fae95897e09c969ba9c060da3a6`.
- Clipping test: 0.67 fraction of saturated PCM16 samples in processed WAV vs 0.0 reference; source SHA `1e0d4162a7af65280547c000b58887edca07743fd707b2ad2d9e15d83705b9f8`, processed SHA `3d8f10a676bafeb5134872f92c13589ade078d12b3e40faae30c385e9ace52cc`.
- The FFmpeg test is **not a model response**; the model suite has its own nine bounded real requests, three per case. Oracle IDs that encode answers are never included in prompts. Independent strict semantics decide grade, not output JSON schema alone.
- First CI failure [37858231559](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37858231559): missing FFmpeg in *generic CI*; explicitly skipped only that integration test in generic CI, and proved it instead on dedicated FFmpeg runner [37858405364]. No threshold change.

## Security and promotion
- Qwen3-0.6B and its verified GGUF are loaded only on a disposable public standard GitHub Actions CPU runner. No A15 inference, no Colibri/Reflex restarts, no new Codespace and no paid cloud.
- All nine tasks use distinct Harness authorization/task IDs. Aggregation refuses incomplete/replayed cohorts; pass@1, pass@3 and observed pass^3 are computed only from completed groups of 3.
- Model transport may fail or produce incorrect semantics. The result must be FAIL if any critical checks fail. There is no auto-promotion, owner media, artistic mastering claim, installed model on A15 or automatic rerun.
- `HAZE_PROFESSIONAL=false`, `WAVE_PROFESSIONAL=false`, `PRODUCTION_APPROVED=false`.

## Controlled model failure and bounded knowledge intervention

First live multi-case Actions cohort [37858541806](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37858541806), exact SHA `e55f0e901b365450921562b659761fdc54bae0b0`:
- 9 real Qwen3-0.6B CPU-loopback responses, 3 cases x 3 attempts; model file and runtime hashes unchanged.
- **Strict HAZE semantic verdict 0/9 (FAIL)**; pass@1 = pass@3 = observed pass^3 = 0.0. Exit 21 by design.
- Categorized failure: `FINDING_MISMATCH` on all nine (3 gain, 3 silence, 3 clipping). The raw model answer is not stored, so further speculation about exact strings is unwarranted.
- Original artifact [11584998908](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37858541806/artifacts/11584998908), create-only receipt SHA-256 `3139e80b7a56b824bde9d743b1d619eb737570ea606fec126005b9fadea6b2d1`, 1,088 tokens, sum HTTP elapsed 8,752.86 ms. Audio FFmpeg controls remained PASS, not ML results.

Targeted change on this branch: new `config/haze-slm-audio-evidence-knowledge-v1.json` with factual, source-versioned explanations of measurements for ALL cases, not an answer key; add its SHA-256 to receipts and only enum-level reported finding. Rationale: original numeric-only prompts lacked domain definitions. This is a **testable root-cause hypothesis**, not a proven causal attribution.

New regression CI [37859251200](https://github.com/zenindiones-maker/Hazewave-/actions/runs/37859251200) **SUCCESS** Py3.12/3.14 at `ac73d4e92d2b9a9d1056dd60bbc40f67de0fc002`. Keep the original strict grade, negative controls, model GGUF SHA and runtime SHA unchanged.

Next authorized experiment: exactly one bounded 3x3 live cohort on standard public GitHub Actions CPU to measure before-vs-after effects. **Never promote on the basis of a single improved run, and do not assert knowledge or model training occurred.** No A15 inference; no Colibri/Reflex changes, no new Codespace or paid runner.
