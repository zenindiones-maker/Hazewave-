#!/usr/bin/env bash
# Hazewave Termux control plane: existing Codespace only, no implicit paid wake.
# --status is read-only, --audit works only for Available, --start-existing opt-in.
set -euo pipefail
die() { printf 'HAZEWAVE_CODESPACE_CONTROL=BLOCKED:%s\n' "$1" >&2; exit 20; }
[[ "$#" -eq 1 ]] || die "EXPLICIT_MODE_REQUIRED"
mode="$1"
case "$mode" in --status|--inventory|--av-fixture|--audit|--start-existing) ;; *) die "MODE_UNSUPPORTED" ;; esac

CS="hazewave-zero-cost-4jxp45676rq6279xx"
REPO="zenindiones-maker/Hazewave-"
BRANCH="${HAZEWAVE_RESEARCH_REF:-work/native-auto-synthesis-av-qa-v1}"
# Only these already-reviewed repository branches may be selected.
case "$BRANCH" in
  work/native-auto-synthesis-av-qa-v1|work/research-codespace-identity-authenticated-v1|work/provider-python-distribution-qualification-v1|work/av-fixture-existing-codespace-v1) ;;
  *) die "UNREVIEWED_RESEARCH_REF" ;;
esac
command -v gh >/dev/null 2>&1 || die "GH_CLI_UNAVAILABLE"
gh auth status -h github.com >/dev/null 2>&1 || die "GITHUB_NOT_AUTHENTICATED"
state="$(gh api "user/codespaces/$CS" --jq '.state')" || die "CODESPACE_STATE_QUERY_FAILED"
case "$state" in Shutdown|Queued|Starting|Available|Unavailable|Unknown|Failed|Stopping|Stopped) ;; *) die "CODESPACE_STATE_UNKNOWN" ;; esac
echo "CODESPACE_ID=$CS"
echo "CODESPACE_STATE=$state"

if [[ "$mode" == "--status" ]]; then
  echo "CODESPACE_AUTO_START=FORBIDDEN"
  echo "CODESPACE_EXISTING_ONLY=TRUE"
  exit 0
fi

if [[ "$mode" == "--start-existing" ]]; then
  if [[ "$state" == "Available" ]]; then
    echo "CODESPACE_ALREADY_AVAILABLE=TRUE"
    exit 0
  fi
  [[ "$state" == "Shutdown" ]] || die "CODESPACE_STATE_NOT_STOPPED"
  [[ "${HAZEWAVE_FREE_COMPUTE_VERIFIED:-NO}" == "YES" ]] || die "FREE_COMPUTE_NOT_VERIFIED"
  # Starts the EXISTING Codespace only, never creates, resizes or rebuilds.
  gh api --method POST "user/codespaces/$CS/start" >/dev/null || die "CODESPACE_EXISTING_START_FAILED"
  echo "CODESPACE_START_ATTEMPTED=EXISTING_ONLY"
  echo "CODESPACE_NEW_MACHINE=FORBIDDEN"
  exit 0
fi

[[ "$state" == "Available" ]] || die "CODESPACE_SHUTDOWN_START_REQUIRED"
if [[ "$mode" == "--audit" && "${HAZEWAVE_FREE_COMPUTE_VERIFIED:-NO}" != "YES" ]]; then
  die "FREE_COMPUTE_NOT_VERIFIED"
fi
EXPECTED="${HAZEWAVE_RESEARCH_EXPECTED_SHA:-}"
[[ "$EXPECTED" =~ ^[0-9a-f]{40}$ ]] || die "REVIEWED_SHA_REQUIRED"
remote_sha="$(gh api "repos/$REPO/git/ref/heads/$BRANCH" --jq '.object.sha')" || die "BRANCH_SHA_QUERY_FAILED"
[[ "$remote_sha" == "$EXPECTED" ]] || die "BRANCH_MOVED_REVIEW_BEFORE_RUNNING"
# Authenticated GitHub API verifies both SSH target identity and repository.
api_name="$(gh api "user/codespaces/$CS" --jq '.name')" || die "CODESPACE_IDENTITY_QUERY_FAILED"
api_repo="$(gh api "user/codespaces/$CS" --jq '.repository.full_name')" || die "CODESPACE_REPOSITORY_QUERY_FAILED"
[[ "$api_name" == "$CS" && "$api_repo" == "$REPO" ]] || die "CODESPACE_CONTROL_PLANE_IDENTITY_MISMATCH"
echo "CODESPACE_CONTROL_PLANE_IDENTITY=PASS"
command -v ssh >/dev/null 2>&1 || die "SSH_CLIENT_MISSING"
echo "REVIEWED_REF=$BRANCH"
echo "REVIEWED_SHA=$EXPECTED"
echo "CODESPACE_NO_NEW_MACHINE=TRUE"
# No op to start machine here. SSH existing instance and run a bounded
# audited bash script over STDIN, not an interpolated user script.
gh codespace ssh -c "$CS" -- "env HAZEWAVE_RESEARCH_REF=$BRANCH HAZEWAVE_RESEARCH_EXPECTED_SHA=$EXPECTED HAZEWAVE_RESEARCH_MODE=$mode bash -se" <<'REMOTE'
set -euo pipefail
umask 077
CS="hazewave-zero-cost-4jxp45676rq6279xx"
REPO="zenindiones-maker/Hazewave-"
BRANCH="${HAZEWAVE_RESEARCH_REF:-work/native-auto-synthesis-av-qa-v1}"
case "$BRANCH" in
  work/native-auto-synthesis-av-qa-v1|work/research-codespace-identity-authenticated-v1|work/provider-python-distribution-qualification-v1|work/av-fixture-existing-codespace-v1) ;;
  *) echo "REMOTE_RESEARCH_REF=BLOCKED"; exit 20 ;;
esac
BASE="/workspaces/Hazewave-"
SHA="${HAZEWAVE_RESEARCH_EXPECTED_SHA:-}"
# Noninteractive SSH sessions can omit CODESPACE_NAME. The GitHub CLI -c
# target is authenticated by the control plane; remote checks remain fail-closed.
[[ "${CODESPACES:-}" == "true" ]] || { echo "REMOTE_PLATFORM=BLOCKED"; exit 20; }
[[ -z "${CODESPACE_NAME:-}" || "${CODESPACE_NAME}" == "$CS" ]] || { echo "REMOTE_IDENTITY=BLOCKED"; exit 20; }
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "REMOTE_REVIEWED_SHA=BLOCKED"; exit 20; }
[[ -d "$BASE" ]] || { echo "BASE_CHECKOUT_UNAVAILABLE"; exit 20; }
origin="$(git -C "$BASE" remote get-url origin)"
case "$origin" in
  https://github.com/zenindiones-maker/Hazewave-|https://github.com/zenindiones-maker/Hazewave-.git|git@github.com:zenindiones-maker/Hazewave-|git@github.com:zenindiones-maker/Hazewave-.git) ;;
  *) echo "REMOTE_REPO_IDENTITY=BLOCKED"; exit 20 ;;
esac
echo "REMOTE_IDENTITY_SOURCE=AUTHENTICATED_GH_SSH_AND_REPOSITORY"
echo "REMOTE_CODESPACE_NAME_FIELD=${CODESPACE_NAME:-UNSET}"
git -C "$BASE" fetch --no-tags origin "refs/heads/$BRANCH"
[[ "$(git -C "$BASE" rev-parse FETCH_HEAD)" == "$SHA" ]] || { echo "REMOTE_REVIEWED_SHA_MOVED"; exit 20; }
WT="$HOME/.local/share/hazewave/research-audit-${SHA:0:12}"
mkdir -p "$(dirname "$WT")"
if [[ ! -d "$WT" ]]; then
  git -C "$BASE" worktree add --detach "$WT" "$SHA"
fi
[[ "$(git -C "$WT" rev-parse HEAD)" == "$SHA" ]] || { echo "WORKTREE_SHA_MISMATCH"; exit 20; }
[[ -z "$(git -C "$WT" status --porcelain)" ]] || { echo "WORKTREE_DIRTY"; exit 20; }
cd "$WT"
# Reuse the existing Codespace's installed project runtime, not Termux Python
# or an ad-hoc internet install in the isolated worktree.
if [[ -x "$BASE/.venv/bin/python" ]]; then
  export PATH="$BASE/.venv/bin:$PATH"
fi
export PYTHONPATH="$WT/src"
export HAZEWAVE_NATIVE_EXPECTED_SHA="$SHA"
export HAZEWAVE_RESEARCH_EXPECTED_SHA="$SHA"
LOG="$HOME/.local/state/hazewave/audits/$SHA"
mkdir -p "$LOG"
chmod 700 "$LOG"
echo "=== HAZEWAVE ISOLATED RESEARCH AUDIT ==="
echo "REPO_SHA=$SHA"
echo "RESEARCH_LOG_DIRECTORY=$LOG"
failures=0
run_step() {
  local name="$1"
  shift
  echo "=== CHECK: $name ==="
  if "$@" > "$LOG/$name.log" 2>&1; then
    echo "$name=PASS"
  else
    local rc=$?
    echo "$name=BLOCKED:$rc"
    tail -n 8 "$LOG/$name.log"
    failures=$((failures+1))
  fi
}
run_step harness_inventory python3 -m hazewave.harness inventory
run_step codespace_inventory bash scripts/codespaces/native-behavior-rea6-probe.sh --inventory
if [[ "${HAZEWAVE_RESEARCH_MODE:-}" == "--inventory" ]]; then
  echo "HAZEWAVE_RESEARCH_AUDIT_SCOPE=NON_DESTRUCTIVE_HOST_INVENTORY_WITH_LOCAL_WORKTREE_AND_LOG_WRITES"
  echo "HAZEWAVE_RESEARCH_AGENT_CONNECTION=NOT_TESTED"
  echo "RESEARCH_LOG_DIRECTORY=$LOG"
  if (( failures > 0 )); then
    echo "HAZEWAVE_RESEARCH_AUDIT=INCOMPLETE"
    exit 21
  fi
  echo "HAZEWAVE_RESEARCH_AUDIT=PASS"
  exit 0
fi
if [[ "${HAZEWAVE_RESEARCH_MODE:-}" == "--av-fixture" ]]; then
  # Dedicated low-resource real HAZE/WAVE execution, not the heavyweight audit.
  # FFmpeg is run only against the existing first-party 1s generated fixtures.
  if command -v ffmpeg >/dev/null 2>&1; then
    run_step av_synthetic_fixture timeout --kill-after=5s 150s bash scripts/codespaces/research-closed-loop-qualification.sh --av-metrics
  else
    echo "av_synthetic_fixture=BLOCKED:FFMPEG_UNAVAILABLE"
    failures=$((failures+1))
  fi
  if (( failures > 0 )); then
    echo "HAZEWAVE_AV_HOST_PROOF=BLOCKED:PREREQUISITES_OR_EXECUTION"
    exit 21
  fi
  grep -Fxq "HAZEWAVE_AV_METRICS=PASS:OWNED_SYNTHETIC_ONLY" "$LOG/av_synthetic_fixture.log" || {
    echo "HAZEWAVE_AV_HOST_PROOF=BLOCKED:ORACLE_RECEIPT_MISSING"
    exit 21
  }
  python3 - "$LOG/av_synthetic_fixture.log" <<'PY'
import hashlib
import json
import pathlib
import re
import stat
import sys

log = pathlib.Path(sys.argv[1])
if log.is_symlink() or log.stat().st_mode & 0o077:
    raise SystemExit("HAZEWAVE_AV_HOST_PROOF=BLOCKED:LOG_PERMISSIONS")
data = log.read_bytes()
records = []
for line in data.splitlines():
    if line.startswith(b"{"):
        try:
            obj = json.loads(line)
        except ValueError:
            raise SystemExit("HAZEWAVE_AV_HOST_PROOF=BLOCKED:INVALID_JSON")
        if obj.get("schema") == "HazewaveSyntheticAudioVideoFidelity/v1":
            records.append(obj)
if len(records) != 1:
    raise SystemExit("HAZEWAVE_AV_HOST_PROOF=BLOCKED:EVIDENCE_COUNT")
r = records[0]
required = {
    "harness_authority": "HAZEWAVE_HARNESS",
    "source": "OWNED_SYNTHETIC_MEDIA",
    "actual_ffmpeg_executed": True,
    "synthetic_audio_verified": True,
    "synthetic_video_verified": True,
    "owner_media_analyzed": False,
    "agent_mcp_connected": False,
    "capability_plane_ready": False,
    "production_approved": False,
}
if any(r.get(k) != v for k, v in required.items()):
    raise SystemExit("HAZEWAVE_AV_HOST_PROOF=BLOCKED:CLAIMS_INCONSISTENT")
try:
    delta = float(r["audio_attenuation_detected_db"])
    same = float(r["identical_video_ssim"])
    different = float(r["altered_video_ssim"])
    digests = r["sample_hashes"]
except (KeyError, ValueError, TypeError):
    raise SystemExit("HAZEWAVE_AV_HOST_PROOF=BLOCKED:METRICS_MISSING")
if not (10 <= delta <= 14 and 0.999 <= same <= 1 and 0 <= different < 0.99 and same > different):
    raise SystemExit("HAZEWAVE_AV_HOST_PROOF=BLOCKED:NEGATIVE_CONTROL")
if not all(isinstance(digests.get(k), str) and re.fullmatch(r"[0-9a-f]{64}", digests[k])
           for k in ("reference_wav", "altered_wav", "reference_video", "altered_video")):
    raise SystemExit("HAZEWAVE_AV_HOST_PROOF=BLOCKED:FIXTURE_HASH_MISSING")
if not r.get("haze_authorization_id") or not r.get("wave_authorization_id"):
    raise SystemExit("HAZEWAVE_AV_HOST_PROOF=BLOCKED:HARNESS_AUTH_MISSING")

# The oracle separately persists its first-party JSON receipt with mode 0600.
private = pathlib.Path.home() / ".local/state/hazewave/research-lab"
normalized = (json.dumps(r, sort_keys=True) + "\n").encode()
matches = []
for file in private.glob("av-metrics-*/av-receipt-*.json"):
    if (not file.is_symlink() and file.is_file() and file.stat().st_mode & 0o077 == 0
            and file.read_bytes() == normalized):
        matches.append(file)
if len(matches) != 1:
    raise SystemExit("HAZEWAVE_AV_HOST_PROOF=BLOCKED:DURABLE_RECEIPT_MISMATCH")
print("HAZEWAVE_AV_LOG_SHA256=" + hashlib.sha256(data).hexdigest())
print("HAZEWAVE_AV_RECEIPT_SHA256=" + hashlib.sha256(normalized).hexdigest())
print("HAZEWAVE_AV_ATTENUATION_DB=" + str(delta))
print("HAZEWAVE_AV_IDENTICAL_SSIM=" + str(same))
print("HAZEWAVE_AV_DIFFERENT_SSIM=" + str(different))
print("HAZEWAVE_AV_LOG=" + str(log))
PY
  echo "HAZEWAVE_AV_HOST_PROOF=PASS_SYNTHETIC_EXECUTION_ONLY"
  echo "HAZEWAVE_AV_AGENT_MCP=NOT_PROVEN"
  echo "HAZEWAVE_AV_PRODUCTION_APPROVED=FALSE"
  echo "HAZEWAVE_STOCK_RESTART=NONE"
  exit 0
fi
run_step native_behavior bash scripts/codespaces/native-behavior-rea6-probe.sh --behavior
run_step closed_loop_preflight bash scripts/codespaces/research-closed-loop-qualification.sh --preflight
run_step automatic_reconstruction bash scripts/codespaces/research-closed-loop-qualification.sh --native-auto
if command -v ffmpeg >/dev/null 2>&1; then
  run_step audiovisual_metrics bash scripts/codespaces/research-closed-loop-qualification.sh --av-metrics
else
  echo "audiovisual_metrics=NOT_TESTED:FFMPEG_UNAVAILABLE"
  failures=$((failures+1))
fi
REA="$HOME/.local/share/hazewave/reverse-engineering/rea-6.0.0/bin/rea"
IRIS="$HOME/.local/share/hazewave/iris/v0.4.1/bin/iris"
if [[ -x "$REA" ]]; then
  run_step rea_ghidra_native bash scripts/codespaces/native-behavior-rea6-probe.sh --ghidra
else
  echo "rea_ghidra_native=NOT_TESTED:REA6_UNAVAILABLE"
  failures=$((failures+1))
fi
if [[ -x "$REA" && -x "$IRIS" ]]; then
  run_step iris_rea_bridge_preflight bash scripts/codespaces/harness-live-research-bridge.sh --preflight
  # Running --prove requires actual browser; preflight must pass.
  if [[ -f "$LOG/iris_rea_bridge_preflight.log" ]] &&
      grep -Fq 'HAZEWAVE_RESEARCH_BRIDGE=PASS:PREREQUISITES' "$LOG/iris_rea_bridge_preflight.log"; then
    run_step iris_rea_own_fixture bash scripts/codespaces/harness-live-research-bridge.sh --prove
  else
    echo "iris_rea_own_fixture=NOT_TESTED:PREFLIGHT_FAILED"
    failures=$((failures+1))
  fi
else
  echo "iris_rea_bridge=NOT_TESTED:PINNED_EXECUTABLES_MISSING"
  failures=$((failures+1))
fi
echo "RESEARCH_AUDIT_BLOCKED_COUNT=$failures"
echo "RESEARCH_LOG_DIRECTORY=$LOG"
echo "CODESPACE_STOCK_RESTART=NONE"
echo "CODESPACE_NEW_MACHINE=NONE"
echo "CODESPACE_AGENT_MCP_CONNECTION=NOT_ATTESTED"
if (( failures > 0 )); then
  echo "HAZEWAVE_RESEARCH_AUDIT=INCOMPLETE"
  exit 21
fi
echo "HAZEWAVE_RESEARCH_AUDIT=PASS"
REMOTE
