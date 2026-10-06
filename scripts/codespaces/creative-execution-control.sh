#!/usr/bin/env bash
set -euo pipefail

BRANCH="work/creative-execution-plane-v1"
REPO_ROOT="/workspaces/Hazewave-"
BRIDGE_ROOT="${HAZEWAVE_REAPER_BRIDGE_DIR:-${HOME}/.local/state/hazewave/reaper-bridge}"
export HAZEWAVE_REAPER_BRIDGE_DIR="$BRIDGE_ROOT"
export PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

die() {
  echo "$1" >&2
  exit "${2:-20}"
}

require_candidate() {
  cd "$REPO_ROOT"
  local actual_branch actual_head remote_head
  actual_branch="$(git branch --show-current)"
  actual_head="$(git rev-parse HEAD)"
  remote_head="$(git rev-parse "origin/${BRANCH}" 2>/dev/null || true)"

  [ "$actual_branch" = "$BRANCH" ] || {
    echo "CREATIVE_BRANCH=FAIL"
    echo "EXPECTED=$BRANCH"
    echo "ACTUAL=$actual_branch"
    exit 21
  }
  [ -n "$remote_head" ] || die "CREATIVE_REMOTE_REF=UNAVAILABLE" 22
  [ "$actual_head" = "$remote_head" ] || {
    echo "CREATIVE_HEAD_EXACT_REMOTE=FAIL"
    echo "HEAD=$actual_head"
    echo "REMOTE_HEAD=$remote_head"
    exit 23
  }
}

cmd_producer_doctor() {
  require_candidate
  command -v python >/dev/null 2>&1 || die "PYTHON=MISSING"
  pgrep -f "${HOME}/.local/opt/reaper/7.82/REAPER/reaper" >/dev/null 2>&1 ||
    die "REAPER_PROCESS=NOT_RUNNING" 24

  python -m hazewave.creative_cli doctor
  echo "CREATIVE_PRODUCER_DOCTOR=PASS"
}

cmd_snapshot() {
  require_candidate
  local request_id
  request_id="$(python -c 'import uuid; print("snapshot-" + uuid.uuid4().hex)')"
  python -m hazewave.creative_cli snapshot     --task-id "termux-snapshot"     --request-id "$request_id"     --idempotency-key "$request_id"
}

cmd_execute() {
  require_candidate
  local command_file="${1:-}"
  [ -n "$command_file" ] || die "EXECUTE=BLOCKED_COMMAND_FILE_REQUIRED" 25
  [ -f "$command_file" ] || die "EXECUTE=BLOCKED_COMMAND_FILE_NOT_FOUND" 26
  python -m hazewave.creative_cli execute "$command_file"
}

cmd_render_preview() {
  require_candidate
  local request_id
  request_id="$(python -c 'import uuid; print("render-" + uuid.uuid4().hex)')"
  python -m hazewave.creative_cli render-preview \
    --task-id "termux-render-preview" \
    --request-id "$request_id" \
    --idempotency-key "$request_id"
  echo "HUMAN_APPROVAL=REQUIRED"
}


cmd_vertical_proof() {
  require_candidate
  local fixture_root proof_id source_audio proof_json
  local CANDIDATE_HEAD POLICY_DIGEST RUNTIME_IDENTITY

  command -v sox >/dev/null 2>&1 || die "SOX=MISSING" 32
  command -v python >/dev/null 2>&1 || die "PYTHON=MISSING" 33

  fixture_root="$BRIDGE_ROOT/fixtures"
  mkdir -p "$fixture_root"

  proof_id="$(python -c 'import uuid; print("vertical-" + uuid.uuid4().hex)')"
  source_audio="$fixture_root/${proof_id}-source.wav"
  proof_json="$(mktemp --suffix=.hazewave-vertical-proof.json)"

  cleanup_fixture() {
    rm -f "$source_audio" "$proof_json"
  }
  trap cleanup_fixture EXIT

  sox -n -r 48000 -c 2 -b 24 "$source_audio" \
    synth 2 sine 220 sine 440 vol 0.05

  CANDIDATE_HEAD="$(git rev-parse HEAD)"
  POLICY_DIGEST="$(sha256sum "$REPO_ROOT/config/project-profile-v2.json" | awk '{print $1}')"
  RUNTIME_IDENTITY="codespace:${CODESPACE_NAME:-$(hostname)}"

  echo "fixture-open=RUNNER_MANAGED"
  python -m hazewave.creative_cli vertical-proof \
    --source-audio "$source_audio" \
    --fixture-root "$fixture_root" \
    --proof-id "$proof_id" \
    --candidate-head "$CANDIDATE_HEAD" \
    --policy-digest "$POLICY_DIGEST" \
    --runtime-identity "$RUNTIME_IDENTITY" \
    --tape-echo-version "1.0.8" \
    >"$proof_json"

  python - "$proof_json" <<'PY'
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
if payload.get("schema") != "ReaperLiveVerticalProof/v1":
    raise SystemExit("VERTICAL_PROOF=FAIL_SCHEMA")
if payload.get("status") != "PASS":
    raise SystemExit("VERTICAL_PROOF=FAIL_STATUS")

session = payload.get("fixture_session")
if not isinstance(session, dict) or not session.get("isolated"):
    raise SystemExit("VERTICAL_PROOF=FAIL_FIXTURE_NOT_ISOLATED")
if session.get("original_project_restored") is not True:
    raise SystemExit("VERTICAL_PROOF=FAIL_ORIGINAL_PROJECT_NOT_RESTORED")

render_a = payload.get("render_a")
render_b = payload.get("render_b")
if not isinstance(render_a, dict) or not isinstance(render_b, dict):
    raise SystemExit("VERTICAL_PROOF=FAIL_RENDERS_MISSING")
path_a = Path(str(render_a.get("artifact_path", "")))
path_b = Path(str(render_b.get("artifact_path", "")))
if path_a == path_b or not path_a.is_file() or not path_b.is_file():
    raise SystemExit("VERTICAL_PROOF=FAIL_RENDER_ARTIFACTS")

receipts = payload.get("durable_receipts")
if not isinstance(receipts, list) or len(receipts) < 10:
    raise SystemExit("VERTICAL_PROOF=FAIL_RECEIPTS")
if not all(Path(str(item)).is_file() for item in receipts):
    raise SystemExit("VERTICAL_PROOF=FAIL_RECEIPT_FILES")
PY

  cat "$proof_json"
  echo "fixture-close=RUNNER_VERIFIED"
  echo "LIVE_REAPER_PROOF=PASS"
  echo "HUMAN_APPROVAL=REQUIRED"
}

cmd_audition() {
  require_candidate
  local artifact="${1:-}" scratch
  [ -n "$artifact" ] || die "AUDITION=BLOCKED_ARTIFACT_REQUIRED" 27
  [ -f "$artifact" ] || die "AUDITION=BLOCKED_ARTIFACT_NOT_FOUND" 28

  command -v ffprobe >/dev/null 2>&1 || die "FFPROBE=MISSING" 29
  command -v ffmpeg >/dev/null 2>&1 || die "FFMPEG=MISSING" 30
  command -v aplay >/dev/null 2>&1 || die "APLAY=MISSING" 31

  ffprobe -v error     -show_entries format=duration:stream=codec_type,codec_name,sample_rate,channels     -of json "$artifact"

  scratch="$(mktemp --suffix=.hazewave-audition.wav)"
  trap 'rm -f "$scratch"' EXIT
  ffmpeg -nostdin -v error -y -i "$artifact"     -map 0:a:0 -c:a pcm_s16le -ar 48000 -ac 2 "$scratch"
  aplay -q "$scratch"
  echo "AUDITION_PLAYBACK=PASS"
  echo "HUMAN_APPROVAL=REQUIRED"
}

cmd_proof() {
  require_candidate
  bash "$REPO_ROOT/scripts/codespaces/hazewave-runtime-proof.sh"
}

case "${1:-producer-doctor}" in
  producer-doctor) cmd_producer_doctor ;;
  snapshot) cmd_snapshot ;;
  execute) shift; cmd_execute "${1:-}" ;;
  render-preview) cmd_render_preview ;;
  vertical-proof) shift; cmd_vertical_proof ;;
  audition) shift; cmd_audition "${1:-}" ;;
  proof) cmd_proof ;;
  *) echo "usage: creative-execution-control.sh {producer-doctor|snapshot|execute COMMAND.json|render-preview|vertical-proof|audition AUDIO_FILE|proof}"; exit 2 ;;
esac
