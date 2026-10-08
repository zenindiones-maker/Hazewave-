#!/usr/bin/env bash
# Execute with bash as a child, NEVER source into the active A15 Termux.
set -euo pipefail
umask 077
fail(){ printf 'HAZEWAVE_SLM_V3=BLOCKED:%s\n' "$1" >&2; exit 20; }
[[ "$#" -eq 1 ]] || fail MODE_NOT_ADMITTED
MODE="$1"
[[ "$MODE" == "--inventory" || "$MODE" == "--activate" ]] || fail MODE_NOT_ADMITTED
SHA="$(printenv HAZEWAVE_SLM_V3_EXPECTED_SHA 2>/dev/null || :)"
[[ "$SHA" =~ ^[a-f0-9]{40}$ ]] || fail SHA_INVALID
REPO="zenindiones-maker/Hazewave-"
REF="work/slm-real-model-qualification-v3"
BASE="$HOME/Hazewave-dev"
WT="$HOME/.local/share/hazewave/worktrees/slm-real-model-qualification-v3"
STATE="$HOME/.local/state/hazewave/slm-real-model-v3"
OLD="2d779b38cfa0d8b093160b9df5b7b130a13fa538"
LOG_SHA="0a5c4f3ba77a8e13ad3aa7dcad91f2853cfb6058d262e763381715749d07cfe4"
REC_SHA="9dc6f17a60a4406dd2a233cb719a8e6145ca0a1533dd052173e7d408aa03b3b6"
MODEL="qwen3:4b"
for executable in gh git python3 timeout; do
 command -v "$executable" >/dev/null 2>&1 || fail REQUIRED_COMMAND_MISSING
done
[[ -x "$BASE/.venv/bin/python" ]] || fail A15_HAZEWAVE_PYTHON_UNAVAILABLE
[[ -e "$BASE/.git" ]] || fail A15_REPOSITORY_UNAVAILABLE
case "$(git -C "$BASE" remote get-url origin 2>/dev/null)" in
  https://github.com/zenindiones-maker/Hazewave-|https://github.com/zenindiones-maker/Hazewave-.git|git@github.com:zenindiones-maker/Hazewave-|git@github.com:zenindiones-maker/Hazewave-.git) ;;
  *) fail WRONG_REPOSITORY ;;
esac
REMOTE_SHA="$(gh api "repos/$REPO/git/ref/heads/$REF" --jq '.object.sha' 2>/dev/null)" || fail GITHUB_UNAVAILABLE
[[ "$REMOTE_SHA" == "$SHA" ]] || fail REMOTE_SHA_CHANGED
git -C "$BASE" fetch --no-tags origin "$REF" || fail REMOTE_FETCH_FAILED
[[ "$(git -C "$BASE" rev-parse FETCH_HEAD)" == "$SHA" ]] || fail FETCH_SHA_MISMATCH
if [[ -e "$WT" || -L "$WT" ]]; then
  [[ ! -L "$WT" && -d "$WT" ]] || fail WORKTREE_PATH_UNSAFE
  [[ "$(git -C "$WT" rev-parse HEAD)" == "$SHA" ]] || fail WORKTREE_HEAD_CHANGED
  [[ -z "$(git -C "$WT" status --porcelain)" ]] || fail WORKTREE_DIRTY
else
  mkdir -p "$(dirname "$WT")"
  git -C "$BASE" worktree add --detach "$WT" "$SHA" || fail WORKTREE_CREATE_FAILED
fi
mkdir -p "$STATE"
chmod 700 "$STATE"
RUN="$(mktemp -d "$STATE/probe.XXXXXXXX")" || fail PRIVATE_CHECKPOINT_FAILED
INVENTORY="$RUN/models.json"
if ! PYTHONPATH="$WT/src" timeout --kill-after=5s 30s \
    "$BASE/.venv/bin/python" -m hazewave.slm_local_model_qualification \
      --inventory >"$INVENTORY"; then
  fail OLLAMA_LOCAL_INVENTORY_UNAVAILABLE
fi
chmod 600 "$INVENTORY"
"$BASE/.venv/bin/python" - "$INVENTORY" <<'PY'
import json, pathlib, sys
data=json.loads(pathlib.Path(sys.argv[1]).read_text())
print("LOCAL_MODEL_INVENTORY=PASS")
print("EXISTING_MODEL_COUNT="+str(data["total_models_installed"]))
for m in data["models"]:
    print("MODEL_NAME="+m["name"])
    print("MODEL_DIGEST="+str(m["local_identity_digest_sha256"]))
    print("SIZE_METADATA_VERIFIED="+str(m["size_verified"]).upper())
    print("LICENSE_METADATA_VERIFIED="+str(m["license_metadata_verified"]).upper())
    print("CANDIDATE_ADMITTED_FOR_SMOKE="+str(m["candidate_admitted_for_smoke"]).upper())
print("LOCAL_MODEL_IDENTITY=NOT_UPSTREAM_ATTESTED")
print("MODEL_IS_SLM_PROVEN=FALSE")
print("PRODUCTION_APPROVED=FALSE")
PY
if [[ "$MODE" == "--inventory" ]]; then
  echo "HAZEWAVE_SLM_V3_INVENTORY=EXECUTED_READ_ONLY"
  echo "TERMUX_PARENT_SHELL_UNCHANGED=TRUE"
  exit 0
fi

# Explicit single known candidate only. No silent alternative or paid fallback.
DIGEST="$("$BASE/.venv/bin/python" - "$INVENTORY" "$MODEL" <<'PY'
import json,pathlib,sys
rows=json.loads(pathlib.Path(sys.argv[1]).read_text())["models"]
candidates=[r for r in rows if r["name"]==sys.argv[2] and r["candidate_admitted_for_smoke"] is True]
if len(candidates)!=1:
    raise SystemExit("MODEL_NOT_ELIGIBLE_FOR_SMOKE")
print(candidates[0]["local_identity_digest_sha256"])
PY
)" || fail NO_QUALIFIED_COMPACT_MODEL
[[ "$DIGEST" =~ ^[a-f0-9]{64}$ ]] || fail MODEL_DIGEST_INVALID

# Use a previous owner-generated synthetic fixture if already imported to A15.
# This script NEVER starts the Codespace or transfers real owner audio.
MATCH_COUNT=0
FOUND_LOG=""
FOUND_RECEIPT=""
for path in "$HOME"/.local/state/hazewave/slm-specialist-proof-v1/session.*/audits/"$OLD"/av_synthetic_fixture.log; do
  [[ -f "$path" && ! -L "$path" ]] || continue
  session_root="$(dirname "$(dirname "$(dirname "$path")")")"
  paired="$session_root/research-lab/av-metrics-imported/av-receipt-owned.json"
  [[ -f "$paired" && ! -L "$paired" ]] || continue
  if [[ "$(sha256sum "$path" | awk '{print $1}')" == "$LOG_SHA" \
     && "$(sha256sum "$paired" | awk '{print $1}')" == "$REC_SHA" ]]; then
    MATCH_COUNT=$((MATCH_COUNT+1))
    FOUND_LOG="$path"
    FOUND_RECEIPT="$paired"
  fi
done
[[ "$MATCH_COUNT" -eq 1 ]] || fail PREVIOUS_SYNTHETIC_EVIDENCE_NOT_IMPORTED_OR_AMBIGUOUS
OUT="$RUN/local-audio-model-receipt.json"
if ! PYTHONPATH="$WT/src" timeout --kill-after=5s 100s \
  "$BASE/.venv/bin/python" -m hazewave.slm_local_model_qualification \
  --probe --model "$MODEL" --expected-digest "$DIGEST" \
  --log "$FOUND_LOG" --receipt "$FOUND_RECEIPT" \
  --reviewed-sha "$OLD" --log-sha256 "$LOG_SHA" --receipt-sha256 "$REC_SHA" \
  --output "$OUT" >"$RUN/model-observation.json"; then
  fail LOCAL_LIVE_INFERENCE_OR_VERIFIER_FAILED
fi
"$BASE/.venv/bin/python" - "$OUT" <<'PY'
import hashlib, json, pathlib, sys
p=pathlib.Path(sys.argv[1])
r=json.loads(p.read_text())
assert r["transport_provenance"]=="LOCAL_LOOPBACK"
assert r["real_model_response_observed"] is True
assert r["harness_authorization"]=="PASS"
assert r["evidence_validation"]=="PASS"
assert r["production_approved"] is False
print("REAL_MODEL_REQUEST=PASS")
print("REAL_MODEL_RESPONSE=PASS")
print("HAZE_VERIFIER_RESULT="+r["verifier_result"])
print("MODEL_LOCAL_DIGEST="+r["model_local_digest_sha256"])
print("MODEL_IS_SLM_PROVEN=FALSE")
print("LOCAL_MODEL_IDENTITY=NOT_UPSTREAM_ATTESTED")
print("HAZE_MODEL_REPORT_SHA256="+hashlib.sha256(p.read_bytes()).hexdigest())
print("HAZE_MODEL_PROMPT_TOKENS="+str(r["prompt_tokens"]))
print("HAZE_MODEL_COMPLETION_TOKENS="+str(r["completion_tokens"]))
print("HAZE_MODEL_DURATION_NS="+str(r["total_duration_ns"]))
print("HAZE_MODEL_PRODUCTION_APPROVED=FALSE")
print("TERMUX_PARENT_SHELL_UNCHANGED=TRUE")
PY
