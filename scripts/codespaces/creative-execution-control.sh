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
  local source_audio="${1:-}" fixture_root proof_id
  local CANDIDATE_HEAD POLICY_DIGEST RUNTIME_IDENTITY

  [ -n "$source_audio" ] || die "VERTICAL_PROOF=BLOCKED_SOURCE_AUDIO_REQUIRED" 32
  [ -f "$source_audio" ] || die "VERTICAL_PROOF=BLOCKED_SOURCE_AUDIO_NOT_FOUND" 33

  fixture_root="${HAZEWAVE_CREATIVE_FIXTURE_ROOT:-${HOME}/.local/state/hazewave-codespace/creative-fixtures}"
  [ -d "$fixture_root" ] || die "VERTICAL_PROOF=BLOCKED_FIXTURE_ROOT_MISSING" 34

  CANDIDATE_HEAD="$(git rev-parse HEAD)"
  POLICY_DIGEST="$(sha256sum "$REPO_ROOT/config/project-profile-v2.json" | awk '{print $1}')"
  RUNTIME_IDENTITY="codespace:${CODESPACE_NAME:-$(hostname)}"
  proof_id="$(python -c 'import uuid; print("vertical-" + uuid.uuid4().hex)')"

  python -m hazewave.creative_cli vertical-proof \
    --source-audio "$source_audio" \
    --fixture-root "$fixture_root" \
    --proof-id "$proof_id" \
    --candidate-head "$CANDIDATE_HEAD" \
    --policy-digest "$POLICY_DIGEST" \
    --runtime-identity "$RUNTIME_IDENTITY" \
    --tape-echo-version "1.0.8"

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
  vertical-proof) shift; cmd_vertical_proof "${1:-}" ;;
  audition) shift; cmd_audition "${1:-}" ;;
  proof) cmd_proof ;;
  *) echo "usage: creative-execution-control.sh {producer-doctor|snapshot|execute COMMAND.json|render-preview|vertical-proof SOURCE_AUDIO|audition AUDIO_FILE|proof}"; exit 2 ;;
esac
