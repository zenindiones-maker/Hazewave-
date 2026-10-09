# V6 bounded real baseline authorization

Fixed development cohort: 10 new cases in src/hazewave/haze_unseen_v6.py (eight actual FFmpeg-verified synthetic PCM16 signals plus missing-reference and out-of-domain controls). V5 gain_loss_12db is EXCLUDED. Every case receives exactly one response from the pre-qualified Qwen3-0.6B Q4_K_M / llama.cpp v0.6.0 pinned runtime, same request-payload contract, no per-case retries. Four future IDs are reserved but NEVER executed as holdouts in this probe.

The independently authored expected finding is stored only in verifier metadata, not in the model request. Every request is fully hashed including system instruction, model identity and decoding parameters; real model output, action, safe abstention and an immutable SHA256 receipt are independently recorded. Every completed response is checkpointed; failures must not be silently recovered as model successes. A FAIL is valuable evidence. This cohort becomes seen development evidence after running; **future reserved holdouts remain untouched**.

Strict controls: public standard GitHub Actions CPU only; do not use A15 inference or Codespace, do not start Colibri/Reflex, no paid providers, no retraining, no audio actions, no main merge or production certification. Job-level marker is mandatory. Owner-requested evaluation only, not routine inference.
