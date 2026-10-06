#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO="zenindiones-maker/Hazewave-"
BRANCH="work/creative-execution-plane-v1"
DISPLAY_NAME="hazewave-zero-cost"
MACHINE="basicLinux32gb"
PRIMARY_PORT="14500"
FALLBACK_PORT="6080"

die() {
  echo "$1" >&2
  exit "${2:-20}"
}

require_tools() {
  command -v gh >/dev/null 2>&1 || die "GH_CLI=MISSING"
  command -v jq >/dev/null 2>&1 || die "JQ=MISSING"
  gh auth status -h github.com >/dev/null 2>&1 || die "GITHUB_AUTH=BLOCKED"
}

matching_json() {
  gh codespace list -R "$REPO" --json name,displayName,state,lastUsedAt
}

guard_singleton() {
  local json count
  json="$(matching_json)"
  count="$(printf '%s' "$json" | jq -r --arg d "$DISPLAY_NAME" '[.[]|select(.displayName==$d)]|length')"
  [ "$count" -le 1 ] || {
    printf '%s
' "$json" | jq --arg d "$DISPLAY_NAME" '[.[]|select(.displayName==$d)]'
    die "HAZEWAVE_CODESPACE=BLOCKED_DUPLICATE_WORKSTATIONS" 30
  }
}

resolve_cs() {
  matching_json | jq -r --arg d "$DISPLAY_NAME" '
    [.[] | select(.displayName==$d)]
    | sort_by(.lastUsedAt)
    | reverse
    | .[0].name // empty
  '
}

state_of() {
  gh codespace view -c "$1" --json state --jq '.state'
}

verify_machine_only() {
  local cs="$1" machine
  machine="$(gh codespace view -c "$cs" --json machineName --jq '.machineName')"
  [ "$machine" = "$MACHINE" ] || {
    echo "HAZEWAVE_CODESPACE=BLOCKED_WRONG_MACHINE"
    echo "EXPECTED=$MACHINE"
    echo "ACTUAL=$machine"
    exit 22
  }
}

verify_identity() {
  local cs="$1" ref
  verify_machine_only "$cs"
  ref="$(gh codespace view -c "$cs" --json gitStatus --jq '.gitStatus.ref')"
  [ "$ref" = "$BRANCH" ] || {
    echo "HAZEWAVE_CODESPACE=BLOCKED_WRONG_BRANCH"
    echo "EXPECTED=$BRANCH"
    echo "ACTUAL=$ref"
    exit 21
  }
}

start_cs() {
  local cs="$1" state
  state="$(state_of "$cs")"

  if [ "$state" != "Available" ]; then
    echo "HAZEWAVE=STARTING"
    gh api --method POST "/user/codespaces/$cs/start" >/dev/null || die "HAZEWAVE_START=BLOCKED" 23
    for _ in $(seq 1 120); do
      state="$(state_of "$cs")"
      echo "STATE=$state"
      [ "$state" = "Available" ] && break
      sleep 5
    done
  fi

  [ "$state" = "Available" ] || die "HAZEWAVE=BLOCKED_STATE_$state" 24
}

port_record() {
  local cs="$1" port="$2"
  gh codespace ports -c "$cs" --json sourcePort,browseUrl,visibility,label 2>/dev/null |
    jq -c --argjson p "$port" 'first(.[]|select(.sourcePort==$p)) // empty'
}

ensure_private_url() {
  local cs="$1" port="$2" record url vis
  for _ in $(seq 1 45); do
    record="$(port_record "$cs" "$port" || true)"
    [ -n "$record" ] && break
    sleep 2
  done

  [ -n "$record" ] || return 1

  url="$(printf '%s' "$record" | jq -r '.browseUrl // empty')"
  vis="$(printf '%s' "$record" | jq -r '.visibility // empty')"

  if [ "$vis" != "private" ]; then
    gh codespace ports visibility "$port:private" -c "$cs" >/dev/null
    record="$(port_record "$cs" "$port")"
    vis="$(printf '%s' "$record" | jq -r '.visibility')"
  fi

  [ "$vis" = "private" ] || die "PORT_${port}_VISIBILITY=BLOCKED_NOT_PRIVATE" 25
  [ -n "$url" ] || return 1
  printf '%s
' "$url"
}

cmd_status() {
  local cs
  guard_singleton
  cs="$(resolve_cs)"
  if [ -z "$cs" ]; then
    echo "HAZEWAVE_CODESPACE=NOT_CREATED"
    return 0
  fi
  verify_identity "$cs"
  gh codespace view -c "$cs" --json name,displayName,state,machineName,machineDisplayName,gitStatus,idleTimeoutMinutes,retentionExpiresAt
  if [ "$(state_of "$cs")" = "Available" ]; then
    echo
    gh codespace ports -c "$cs" --json sourcePort,label,visibility,browseUrl || true
  fi
}

cmd_open() {
  local cs url transport
  guard_singleton
  cs="$(resolve_cs)"
  [ -n "$cs" ] || die "HAZEWAVE_CODESPACE=NOT_FOUND_EXISTING_REUSE_REQUIRED" 27
  verify_identity "$cs"
  start_cs "$cs"

  echo "HAZEWAVE_CODESPACE=AVAILABLE"
  echo "CODESPACE=$cs"

  transport="XPRA_HTML5"
  gh codespace ssh -c "$cs" -- 'cd /workspaces/Hazewave- && bash scripts/codespaces/start-professional-desktop.sh' ||
    die "HAZEWAVE_XPRA=BLOCKED_START_FAILED" 28

  url="$(ensure_private_url "$cs" "$PRIMARY_PORT" || true)"
  [ -n "$url" ] || die "HAZEWAVE_XPRA=BLOCKED_NO_PRIVATE_PORT" 29

  echo "REMOTE_TRANSPORT=$transport"
  echo "DESKTOP_VISIBILITY=PRIVATE"
  echo "HAZEWAVE_WORKSTATION_READY=PASS"
  echo "XPRA_REQUIRED=TRUE"
  echo "WORKSTATION_ROLE=HAZE_AUDIO_REAPER"
  echo "REAPER_PRIMARY=TRUE"
  echo "ZERO_COST_MODE=INCLUDED_USAGE_ONLY"
  echo "PAID_FALLBACK=FALSE"

  if command -v termux-open-url >/dev/null 2>&1; then
    termux-open-url "$url"
  else
    echo "DESKTOP_URL=$url"
  fi
}

cmd_doctor() {
  local cs state
  guard_singleton
  cs="$(resolve_cs)"
  [ -n "$cs" ] || die "HAZEWAVE_CODESPACE=NOT_CREATED" 27
  verify_identity "$cs"
  state="$(state_of "$cs")"
  if [ "$state" != "Available" ]; then
    echo "HAZEWAVE_CODESPACE_STATE=$state"
    echo "DOCTOR=WAIT_CODESPACE_STOPPED"
    return 0
  fi

  gh codespace ssh -c "$cs" -- bash -lc '
    set -euo pipefail
    cd /workspaces/Hazewave-
    echo "BRANCH=$(git branch --show-current)"
    echo "HEAD=$(git rev-parse HEAD)"
    if [ -x scripts/codespaces/professional-doctor.sh ] || [ -f scripts/codespaces/professional-doctor.sh ]; then
      bash scripts/codespaces/professional-doctor.sh
    else
      bash scripts/codespaces/doctor.sh
    fi
  '

  echo
  gh codespace ports -c "$cs" --json sourcePort,label,visibility,browseUrl
}

cmd_sync() {
  local cs
  guard_singleton
  cs="$(resolve_cs)"
  [ -n "$cs" ] || die "HAZEWAVE_CODESPACE=NOT_CREATED" 27

  verify_machine_only "$cs"
  start_cs "$cs"

  gh codespace ssh -c "$cs" -- bash -lc '
    set -euo pipefail
    cd /workspaces/Hazewave-

    if [ -n "$(git status --porcelain)" ]; then
      echo "WORKTREE=BLOCKED_DIRTY_PRESERVE_WIP"
      git status --short --branch
      exit 41
    fi

    git fetch origin work/creative-execution-plane-v1

    if git show-ref --verify --quiet refs/heads/work/creative-execution-plane-v1; then
      git switch work/creative-execution-plane-v1
    else
      git switch --track -c work/creative-execution-plane-v1 origin/work/creative-execution-plane-v1
    fi

    git pull --ff-only origin work/creative-execution-plane-v1

    HEAD_NOW="$(git rev-parse HEAD)"
    REMOTE_NOW="$(git rev-parse origin/work/creative-execution-plane-v1)"
    [ "$HEAD_NOW" = "$REMOTE_NOW" ] || {
      echo "SYNC=BLOCKED_NOT_EXACT_REMOTE"
      exit 42
    }

    echo "SYNC=PASS"
    echo "BRANCH=$(git branch --show-current)"
    echo "HEAD=$HEAD_NOW"

    bash scripts/codespaces/upgrade-professional-v2.sh
  '

  verify_identity "$cs"
  echo "HAZEWAVE_V3_SYNC=PASS"
  echo "XPRA_REQUIRED=TRUE"
  echo "PAID_FALLBACK=FALSE"
}

cmd_proof() {
  local cs
  cmd_sync
  guard_singleton
  cs="$(resolve_cs)"
  [ -n "$cs" ] || die "HAZEWAVE_CODESPACE=NOT_CREATED" 27
  verify_identity "$cs"

  gh codespace ssh -c "$cs" -- bash -lc '
    set -euo pipefail
    cd /workspaces/Hazewave-
    bash scripts/codespaces/hazewave-runtime-proof.sh
  '

  ensure_private_url "$cs" "$PRIMARY_PORT" >/dev/null ||
    die "HAZEWAVE_PROOF=BLOCKED_PRIVATE_PORT_UNPROVEN" 43

  echo "HAZEWAVE_RUNTIME_PROOF=PASS_AUTOMATED_BOUNDARY"
  echo "XPRA_REQUIRED=TRUE"
  echo "PORT_VISIBILITY=PRIVATE"
  echo "PAID_FALLBACK=FALSE"
  echo "UNKNOWN_COST_FALLBACK=FALSE"
}

cmd_close() {
  local cs state
  guard_singleton
  cs="$(resolve_cs)"
  if [ -z "$cs" ]; then
    echo "HAZEWAVE_CODESPACE=NOT_CREATED"
    return 0
  fi
  verify_machine_only "$cs"
  state="$(state_of "$cs")"
  if [ "$state" = "Available" ]; then
    gh codespace stop -c "$cs"
  fi
  echo "HAZEWAVE_CODESPACE_STOP=PASS"
  echo "CODESPACE=$cs"
  echo "CODESPACE_DELETED=FALSE"
}

cmd_creative_remote() {
  local action="$1" argument="${2:-}" cs remote_action remote_arg
  guard_singleton
  cs="$(resolve_cs)"
  [ -n "$cs" ] || die "HAZEWAVE_CODESPACE=NOT_FOUND_EXISTING_REUSE_REQUIRED" 27
  verify_identity "$cs"
  start_cs "$cs"

  printf -v remote_action '%q' "$action"
  remote_arg=""
  if [ -n "$argument" ]; then
    printf -v remote_arg ' %q' "$argument"
  fi

  gh codespace ssh -c "$cs" -- bash -lc "
    set -euo pipefail
    cd /workspaces/Hazewave-
    bash scripts/codespaces/creative-execution-control.sh $remote_action$remote_arg
  "
}

cmd_create() {
  echo "EXISTING_CODESPACE_REUSE=REQUIRED"
  echo "HAZEWAVE_CODESPACE_CREATE=BLOCKED_BY_CREATIVE_PLANE_MISSION"
  exit 31
}

require_tools

case "${1:-status}" in
  open) cmd_open ;;
  status) cmd_status ;;
  sync) cmd_sync ;;
  proof) cmd_proof ;;
  doctor) cmd_doctor ;;
  producer-doctor) cmd_creative_remote producer-doctor ;;
  snapshot) cmd_creative_remote snapshot ;;
  execute) cmd_creative_remote execute "${2:-}" ;;
  render-preview) cmd_creative_remote render-preview ;;
  audition) cmd_creative_remote audition "${2:-}" ;;
  close|stop) cmd_close ;;
  create) cmd_create ;;
  *) echo "usage: hazectl {open|status|sync|proof|doctor|producer-doctor|snapshot|execute|render-preview|audition|close|create}"; exit 2 ;;
esac
