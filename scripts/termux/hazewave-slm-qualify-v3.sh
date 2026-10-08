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

if [[ "$MATCH_COUNT" -eq 0 ]]; then
  # Host-proven fixture is absent on A15: fetch ONLY those two bounded,
  # hash-pinned files from the one EXISTING authenticated Codespace.
  CS="hazewave-zero-cost-4jxp45676rq6279xx"
  CS_STATE="$(gh api "user/codespaces/$CS" --jq '.state' 2>/dev/null)" || fail CODESPACE_STATE_QUERY_FAILED
  CS_OWNER="$(gh api "user/codespaces/$CS" --jq '.repository.full_name' 2>/dev/null)" || fail CODESPACE_REPO_QUERY_FAILED
  [[ "$CS_OWNER" == "$REPO" ]] || fail CODESPACE_REPO_MISMATCH
  [[ "$CS_STATE" == "Available" ]] || fail CODESPACE_SHUTDOWN_NOT_ADMITTED
  TRANSFER="$RUN/transfer.json"
  if ! timeout --kill-after=5s 75s gh codespace ssh -c "$CS" -- 'python3 -' > "$TRANSFER" <<'REMOTE'
import base64, hashlib, json, os, stat, subprocess
from pathlib import Path
if os.environ.get("CODESPACES") != "true":
    raise SystemExit("CODESPACE_RUNTIME_IDENTITY_INVALID")
valid={
    "https://github.com/zenindiones-maker/Hazewave-",
    "https://github.com/zenindiones-maker/Hazewave-.git",
    "git@github.com:zenindiones-maker/Hazewave-",
    "git@github.com:zenindiones-maker/Hazewave-.git",
}
origin=subprocess.run(
    ["git","-C","/workspaces/Hazewave-","remote","get-url","origin"],
    text=True,capture_output=True,check=True,timeout=10
).stdout.strip()
if origin not in valid:
    raise SystemExit("CODESPACE_REPOSITORY_IDENTITY_INVALID")
root=Path.home()/".local/state/hazewave"
log=root/"audits/2d779b38cfa0d8b093160b9df5b7b130a13fa538/av_synthetic_fixture.log"
records=root/"research-lab"
log_digest="0a5c4f3ba77a8e13ad3aa7dcad91f2853cfb6058d262e763381715749d07cfe4"
record_digest="9dc6f17a60a4406dd2a233cb719a8e6145ca0a1533dd052173e7d408aa03b3b6"
def secure(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|
               getattr(os,"O_CLOEXEC",0)|getattr(os,"O_NONBLOCK",0))
    with os.fdopen(fd,"rb") as stream:
        st=os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or st.st_mode&0o077 or not 0<st.st_size<2097153:
            raise SystemExit("CODESPACE_EVIDENCE_PERMISSIONS_INVALID")
        data=stream.read(2097153)
        if len(data)!=st.st_size:
            raise SystemExit("CODESPACE_EVIDENCE_SIZE_MISMATCH")
        return data
log_data=secure(log)
if hashlib.sha256(log_data).hexdigest()!=log_digest:
    raise SystemExit("CODESPACE_LOG_DIGEST_MISMATCH")
matches=[]
for p in records.glob("av-metrics-*/av-receipt-*.json"):
    if p.is_symlink():
        continue
    try:
        blob=secure(p)
    except OSError:
        continue
    if hashlib.sha256(blob).hexdigest()==record_digest:
        matches.append(blob)
if len(matches)!=1:
    raise SystemExit("CODESPACE_RECEIPT_UNIQUE_MATCH_FAILED")
print(json.dumps({"log":base64.b64encode(log_data).decode("ascii"),
                  "receipt":base64.b64encode(matches[0]).decode("ascii")}))
REMOTE
  then
    fail REMOTE_SYNTHETIC_EVIDENCE_UNAVAILABLE
  fi
  "$BASE/.venv/bin/python" - "$TRANSFER" "$RUN" "$OLD" "$LOG_SHA" "$REC_SHA" <<'PY'
import base64, hashlib, json, pathlib, sys
src,root,rev,log_hash,rec_hash=pathlib.Path(sys.argv[1]),pathlib.Path(sys.argv[2]),*sys.argv[3:]
payload=json.loads(src.read_bytes())
if set(payload)!={"log","receipt"}:
    raise SystemExit("TRANSFER_SCHEMA_MISMATCH")
paths=(
    ("log", root/"audits"/rev/"av_synthetic_fixture.log",log_hash),
    ("receipt", root/"research-lab"/"av-metrics-imported"/"av-receipt-owned.json",rec_hash)
)
for key,path,expected in paths:
    data=base64.b64decode(payload[key],validate=True)
    if hashlib.sha256(data).hexdigest()!=expected:
        raise SystemExit("TRANSFER_INTEGRITY_MISMATCH")
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o600)
src.unlink()
print("SYNTHETIC_EVIDENCE_TRANSFER=VERIFIED_ONLY")
PY
  FOUND_LOG="$RUN/audits/$OLD/av_synthetic_fixture.log"
  FOUND_RECEIPT="$RUN/research-lab/av-metrics-imported/av-receipt-owned.json"
  MATCH_COUNT=1
fi

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
