# Reflex Shadow Runtime V1 — existing GitHub Codespace

This is the **next real execution stage** after PR #19 and PR #20. It must run inside the existing Codespace, not in a new machine or a transient GitHub Actions runner.

## 1. Create an isolated, detached candidate checkout

Open the terminal of existing Codespace `redesigned-space-bassoon-gxp67g5g7r739w59`. Inspect concurrent work before proceeding. Never switch/reset the current checkout.

```bash
cd /workspaces/Hazewave-
git status --short
git fetch --no-tags origin work/reflex-shadow-runtime-v1
R="$HOME/.local/share/hazewave/reflex-shadow-runtime/checkout"
if [ ! -e "$R/.git" ]; then
  test ! -e "$R" || { echo WORKTREE_PATH_OCCUPIED; exit 18; }
  mkdir -p "$(dirname "$R")"
  git worktree add --detach "$R" origin/work/reflex-shadow-runtime-v1
fi
bash "$R/scripts/codespaces/reflex-shadow-control.sh" doctor
```

Doctor will initially fail closed until the pinned Colibri source, weight files, and engine are present. **That is expected; do not forge a PASS.**

## 2. Admit hardware and explicitly prepare

Inspect RAM/disk and confirm the Codespace quota is still within the included free allowance. No machine resizing or paid provider access is authorized.

```bash
bash "$R/scripts/codespaces/reflex-shadow-control.sh" prepare
```

This action performs a resource check before downloading anything, then fetches exactly Colibri release v2.0.0 and the pinned Laya English weights, compiles only the Laya engine, compares the model SHA-256, and generates a private bearer key if none exists. It neither modifies the active branch nor installs a daemon.

If `hf`, gcc or make is missing, it stops; it does **not** silently install dependencies or change the workstation base image.

## 3. Start local server

In a dedicated Codespace terminal:

```bash
bash "$R/scripts/codespaces/reflex-shadow-control.sh" serve
```

Keep this terminal open. There is no autorestart and no background loop. It refuses a previously occupied port instead of killing the existing process. Endpoint: `127.0.0.1:28080`, bearer-authenticated.

## 4. Prove real local inference

In a second Codespace terminal:

```bash
R="$HOME/.local/share/hazewave/reflex-shadow-runtime/checkout"
bash "$R/scripts/codespaces/reflex-shadow-control.sh" smoke
```

A receipt is created only if a real Colibri System One response reaches the Hazewave adapter and the result is still shadow-only. It records source/model digests, request/response hashes, latency and Codespace identity. A smoke PASS **does not** mean production calibration or verified monthly billing allowance.

## 5. Observe one real, non-secret structured task

After deterministic project policy prechecks, produce a local internal event file with this shape:

```json
{
  "schema": "HazewaveReflexShadowEvent/v1",
  "task_id": "operator-event-0001",
  "requested_domain": "HAZE",
  "data_classification": "INTERNAL_NON_SECRET",
  "state_language": "en",
  "precheck_status": "UNRESOLVED_PERMITTED_AMBIGUITY",
  "decision_key": "domain.route.v1",
  "state": {
    "operation_kind": "timeline cue alignment",
    "media_surfaces": ["audio", "animation"],
    "decision_required": "advisory routing"
  }
}
```

This example is a schema illustration, **not** a claim that the event happened. Real observations must come from an actual task's allowed machine-state metadata and pass through the existing Harness prechecks.

```bash
bash "$R/scripts/codespaces/reflex-shadow-control.sh" observe /path/to/real-event.json
```

Never insert raw Telegram text, audio, images, credentials or private media into this contract. Never mislabel a model prediction as a human/QC ground-truth answer.

Optional post-hoc `ground_truth` requires `actual_label`, `label_source` and `label_evidence_digest`. The digest alone does not authenticate its producer. Human-label authenticity needs a trusted upstream review receipt before those labels can become training inputs.

## 6. Read the outcome report

```bash
bash "$R/scripts/codespaces/reflex-shadow-control.sh" report
```

The initial report will likely say `NO_LABELED_OUTCOMES`. This is not an error and must not be replaced by fabricated labels.

## 7. Boundary and stopping conditions

Immediately stop the reflex process (its own foreground terminal only) if REAPER/FFmpeg or Wave rendering requires the RAM/CPU headroom. No change to other processes is permitted.

Completion gates:
- `REPOSITORY_COMPATIBLE` — CI, contracts and unit tests green.
- `SOURCE_MODEL_PINNED` — real source and weights hashes verified in the Codespace.
- `LIVE_SMOKE_PASS` — actual authenticated HTTP inference and durable receipt.
- `SHADOW_OBSERVATIONS` — real, separate task events, no authority mutation.
- `LABELED_CALIBRATION` — enough trusted evidence from actual outcomes.
- `PRODUCTION_APPROVED` — separate reviewed promotion, not part of this stage.

Do not claim the final four gates merely because a test or build passes.
