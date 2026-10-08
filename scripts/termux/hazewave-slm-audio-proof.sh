#!/usr/bin/env bash
# Single-existing-Codespace synthetic HAZE proof -> existing A15 9Router.
# Always run with bash SCRIPT --benchmark (child process), NEVER source in Termux.
set -euo pipefail
umask 077

fail() { printf 'HAZEWAVE_SLM_PROOF=BLOCKED:%s\n' "$1" >&2; exit 20; }
[[ "$#" -eq 1 && "$1" == "--benchmark" ]] || fail "MODE_UNSUPPORTED"
SHA="${HAZEWAVE_SLM_EXPECTED_SHA:-}"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || fail "REVIEWED_SHA_INVALID"
REPO="zenindiones-maker/Hazewave-"
CS="hazewave-zero-cost-4jxp45676rq6279xx"
REF="work/slm-professional-audio-triage-v1"
OLD_SHA="2d779b38cfa0d8b093160b9df5b7b130a13fa538"
OLD_LOG_HASH="0a5c4f3ba77a8e13ad3aa7dcad91f2853cfb6058d262e763381715749d07cfe4"
OLD_RECEIPT_HASH="9dc6f17a60a4406dd2a233cb719a8e6145ca0a1533dd052173e7d408aa03b3b6"
MODEL="oc/mimo-v2.6-flash-free"
BASE="$HOME/Hazewave-dev"
WT="$HOME/.local/share/hazewave/worktrees/slm-professional-audio-triage-v1"
STATE="$HOME/.local/state/hazewave/slm-specialist-proof-v1"

for executable in gh git python3 timeout; do
  command -v "$executable" >/dev/null 2>&1 || fail "REQUIRED_COMMAND_MISSING"
done
[[ -x "$BASE/.venv/bin/python" ]] || fail "LOCAL_HAZEWAVE_VENV_MISSING"
[[ -d "$BASE/.git" || -f "$BASE/.git" ]] || fail "LOCAL_REPO_NOT_FOUND"
case "$(git -C "$BASE" remote get-url origin 2>/dev/null)" in
  https://github.com/zenindiones-maker/Hazewave-|https://github.com/zenindiones-maker/Hazewave-.git|git@github.com:zenindiones-maker/Hazewave-|git@github.com:zenindiones-maker/Hazewave-.git) ;;
  *) fail "LOCAL_REPOSITORY_IDENTITY_INVALID" ;;
esac

NAME="$(gh api "user/codespaces/$CS" --jq '.name' 2>/dev/null)" || fail "CODESPACE_API_MISSING"
STATE_REMOTE="$(gh api "user/codespaces/$CS" --jq '.state' 2>/dev/null)" || fail "CODESPACE_STATE_QUERY_FAILED"
OWNER="$(gh api "user/codespaces/$CS" --jq '.repository.full_name' 2>/dev/null)" || fail "CODESPACE_REPOSITORY_QUERY_FAILED"
[[ "$NAME" == "$CS" && "$OWNER" == "$REPO" ]] || fail "CODESPACE_AUTH_IDENTITY_INVALID"
[[ "$STATE_REMOTE" == "Available" ]] || fail "CODESPACE_SHUTDOWN_NOT_ADMITTED"
REMOTE_SHA="$(gh api "repos/$REPO/git/ref/heads/$REF" --jq '.object.sha' 2>/dev/null)" || fail "REMOTE_SHA_QUERY_FAILED"
[[ "$REMOTE_SHA" == "$SHA" ]] || fail "REMOTE_SHA_MISMATCH"
echo "HAZEWAVE_SLM_CODESPACE_AUTH=PASS"

git -C "$BASE" fetch --no-tags origin "$REF" || fail "REF_FETCH_FAILED"
[[ "$(git -C "$BASE" rev-parse FETCH_HEAD)" == "$SHA" ]] || fail "FETCH_SHA_MISMATCH"
if [[ -e "$WT" || -L "$WT" ]]; then
  [[ ! -L "$WT" && -d "$WT" ]] || fail "WORKTREE_PATH_UNSAFE"
  [[ "$(git -C "$WT" rev-parse HEAD)" == "$SHA" ]] || fail "WORKTREE_HEAD_MISMATCH"
  [[ -z "$(git -C "$WT" status --porcelain)" ]] || fail "WORKTREE_DIRTY"
else
  mkdir -p "$(dirname "$WT")"
  git -C "$BASE" worktree add --detach "$WT" "$SHA" || fail "ISOLATED_WORKTREE_CREATION_FAILED"
fi

mkdir -p "$STATE"
chmod 700 "$STATE"
RUN="$(mktemp -d "$STATE/session.XXXXXXXX")" || fail "PRIVATE_SESSION_DIRECTORY_FAILED"
BUNDLE="$RUN/transfer.json"
echo "HAZEWAVE_SLM_WORKTREE_SHA=$SHA"

# The remote supplies ONLY previously owner-produced synthetic log and receipt.
# The 9Router remains on A15 loopback; no tunnel, external API exposure or
# Codespace port-forwarding is used.
gh codespace ssh -c "$CS" -- 'python3 -' > "$BUNDLE" <<'REMOTE_PY'
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

def fail(code):
    raise SystemExit("REMOTE_SOURCE_BLOCKED:" + code)

if os.environ.get("CODESPACES") != "true":
    fail("NOT_CODESPACE")
root = Path("/workspaces/Hazewave-")
origin = __import__("subprocess").run(
    ["git", "-C", str(root), "remote", "get-url", "origin"],
    text=True, capture_output=True, timeout=10
).stdout.strip()
if origin not in {
    "https://github.com/zenindiones-maker/Hazewave-",
    "https://github.com/zenindiones-maker/Hazewave-.git",
    "git@github.com:zenindiones-maker/Hazewave-",
    "git@github.com:zenindiones-maker/Hazewave-.git"
}:
    fail("REPO_IDENTITY")

home = Path.home()
log = home / ".local/state/hazewave/audits/2d779b38cfa0d8b093160b9df5b7b130a13fa538/av_synthetic_fixture.log"
record_root = home / ".local/state/hazewave/research-lab"
expected_log = "0a5c4f3ba77a8e13ad3aa7dcad91f2853cfb6058d262e763381715749d07cfe4"
expected_record = "9dc6f17a60a4406dd2a233cb719a8e6145ca0a1533dd052173e7d408aa03b3b6"

def secure(p):
    if p.is_symlink():
        fail("UNSAFE_SYMLINK")
    s = p.stat()
    if (not stat.S_ISREG(s.st_mode) or s.st_uid != os.geteuid()
            or s.st_mode & 0o077 or s.st_size <= 0 or s.st_size > 2097152):
        fail("UNSAFE_FILE")
    return p.read_bytes()

log_data = secure(log)
if hashlib.sha256(log_data).hexdigest() != expected_log:
    fail("LOG_DIGEST")
candidates = []
for path in record_root.glob("av-metrics-*/av-receipt-*.json"):
    if path.is_symlink():
        continue
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size > 2097152 or st.st_mode & 0o077:
        continue
    if hashlib.sha256(path.read_bytes()).hexdigest() == expected_record:
        candidates.append(path)
if len(candidates) != 1:
    fail("RECEIPT_NOT_UNIQUE")
receipt = secure(candidates[0])
print(json.dumps({
    "log": base64.b64encode(log_data).decode("ascii"),
    "receipt": base64.b64encode(receipt).decode("ascii")
}))
REMOTE_PY
RC=$?
[[ "$RC" -eq 0 ]] || fail "EXISTING_CODESPACE_EVIDENCE_TRANSFER_FAILED"

python3 - "$BUNDLE" "$RUN" "$OLD_LOG_HASH" "$OLD_RECEIPT_HASH" "$OLD_SHA" <<'LOCAL_PY'
import base64, hashlib, json, pathlib, sys
src, root = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
payload = json.loads(src.read_text())
if set(payload) != {"log", "receipt"}:
    raise SystemExit("EVIDENCE_TRANSFER_SCHEMA_BLOCKED")
p1 = root / "audits" / sys.argv[5] / "av_synthetic_fixture.log"
p2 = root / "research-lab" / "av-metrics-imported" / "av-receipt-owned.json"
for key, expected, path in [
    ("log", sys.argv[3], p1), ("receipt", sys.argv[4], p2)
]:
    data = base64.b64decode(payload[key], validate=True)
    if hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit("EVIDENCE_TRANSFER_HASH_BLOCKED")
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o600)
src.unlink()
print("HAZEWAVE_SLM_EVIDENCE_TRANSFER=PASS:OWNED_SYNTHETIC_ONLY")
LOCAL_PY

LOG="$RUN/audits/$OLD_SHA/av_synthetic_fixture.log"
RECEIPT="$RUN/research-lab/av-metrics-imported/av-receipt-owned.json"
OUT="$RUN/benchmark.json"
PYTHONPATH="$WT/src" timeout --kill-after=5s 175s "$BASE/.venv/bin/python" \
  -m hazewave.slm_audio_specialist \
  --log "$LOG" --receipt "$RECEIPT" --reviewed-sha "$OLD_SHA" \
  --log-sha256 "$OLD_LOG_HASH" --receipt-sha256 "$OLD_RECEIPT_HASH" \
  --model "$MODEL" --compare-baseline > "$OUT" || fail "GOVERNED_MODEL_OR_BENCHMARK_FAILED"

python3 - "$OUT" <<'REPORT_PY'
import hashlib, json, pathlib, sys
p = pathlib.Path(sys.argv[1])
r = json.loads(p.read_text())
assert r["schema"] == "HazewaveSLMAudioSpecialistBenchmark/v1"
assert r["harness_authority"] == "HAZEWAVE_HARNESS"
assert r["model_improvement_proven"] is False
assert r["production_approved"] is False
assert r["agent_tool_execution_proven"] is False
assert r["baseline"] is not None
print("HAZE_SLM_BASELINE_GRADE=" + r["baseline"]["grade"])
print("HAZE_SLM_SPECIALIST_GRADE=" + r["specialist"]["grade"])
print("HAZE_SLM_BENCHMARK_STATUS=" + r["benchmark_execution"])
print("HAZE_SLM_MODEL=" + r["model_id"])
print("HAZE_SLM_TOKENS=" + str(r["total_tokens"]))
print("HAZE_SLM_RECEIPT_SHA256=" + hashlib.sha256(p.read_bytes()).hexdigest())
print("HAZE_SLM_PRODUCTION_APPROVED=FALSE")
print("HAZE_SLM_AGENT_TOOL_EXECUTION=NOT_PROVEN")
REPORT_PY

echo "HAZEWAVE_SLM_RUNTIME_SCOPE=OWNED_SYNTHETIC_READ_PLUS_FREE_MODEL"
echo "TERMUX_PARENT_SHELL_UNCHANGED=TRUE"
