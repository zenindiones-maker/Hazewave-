#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

FREELLMAPI_PROVIDER_ROOT="${FREELLMAPI_PROVIDER_ROOT:-$HOME/.local/share/hazewave/providers/freellmapi}"
FREELLMAPI_DEPLOY_ROOT="$FREELLMAPI_PROVIDER_ROOT/deploy"
FREELLMAPI_CURRENT="$FREELLMAPI_DEPLOY_ROOT/current"
FREELLMAPI_STATE_ROOT="${FREELLMAPI_STATE_ROOT:-$HOME/.local/state/hazewave/providers/freellmapi}"
FREELLMAPI_CONFIG_ROOT="${FREELLMAPI_CONFIG_ROOT:-$HOME/.config/hazewave/providers/freellmapi}"
FREELLMAPI_ENCRYPTION_KEY_FILE="$FREELLMAPI_CONFIG_ROOT/encryption-key"
FREELLMAPI_UNIFIED_KEY_FILE="$FREELLMAPI_CONFIG_ROOT/unified-api-key"
FREELLMAPI_PID_FILE="$FREELLMAPI_STATE_ROOT/server.pid"
FREELLMAPI_LOG_FILE="$FREELLMAPI_STATE_ROOT/server.log"
CONTROL_LOCK_DIR="$FREELLMAPI_STATE_ROOT/control.lock"
CONTROL_LOCK_OWNER_FILE="$CONTROL_LOCK_DIR/owner.pid"
PORT="${FREELLMAPI_PORT:-3001}"

control_lock_owner_alive() {
  local pid="$1" cmdline
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  test -r "/proc/$pid/cmdline" || return 1
  cmdline="$(tr '\\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmdline" == *"hazewave_freellmapi_control.sh"* ]]
}

acquire_control_lock() {
  local attempt owner stale_dir
  mkdir -p "$FREELLMAPI_STATE_ROOT"

  for attempt in 1 2 3; do
    if mkdir "$CONTROL_LOCK_DIR" 2>/dev/null; then
      printf '%s\n' "$" > "$CONTROL_LOCK_OWNER_FILE"
      trap 'release_control_lock' EXIT INT TERM
      return 0
    fi

    owner="$(cat "$CONTROL_LOCK_OWNER_FILE" 2>/dev/null || true)"
    if [ -z "$owner" ]; then
      sleep 0.1
      owner="$(cat "$CONTROL_LOCK_OWNER_FILE" 2>/dev/null || true)"
    fi

    if control_lock_owner_alive "$owner"; then
      echo "HAZEWAVE_FREELLMAPI_CONTROL=BUSY" >&2
      return 75
    fi

    stale_dir="${CONTROL_LOCK_DIR}.stale.$.$attempt"
    if mv "$CONTROL_LOCK_DIR" "$stale_dir" 2>/dev/null; then
      rm -f "$stale_dir/owner.pid"
      if ! rmdir "$stale_dir" 2>/dev/null; then
        echo "HAZEWAVE_FREELLMAPI_CONTROL_STALE_LOCK=UNSAFE_CONTENT" >&2
        return 76
      fi
      echo "HAZEWAVE_FREELLMAPI_CONTROL_STALE_LOCK=RECOVERED" >&2
      continue
    fi

    sleep 0.1
  done

  echo "HAZEWAVE_FREELLMAPI_CONTROL=BUSY" >&2
  return 75
}

release_control_lock() {
  local owner
  owner="$(cat "$CONTROL_LOCK_OWNER_FILE" 2>/dev/null || true)"
  if [ "$owner" = "$" ]; then
    rm -f "$CONTROL_LOCK_OWNER_FILE"
    rmdir "$CONTROL_LOCK_DIR" 2>/dev/null || true
  fi
}

current_release() {
  test -L "$FREELLMAPI_CURRENT" || {
    echo "HAZEWAVE_FREELLMAPI=NOT_INSTALLED"
    return 1
  }
  readlink -f "$FREELLMAPI_CURRENT"
}

load_runtime_env() {
  test -s "$FREELLMAPI_ENCRYPTION_KEY_FILE" || {
    echo "HAZEWAVE_FREELLMAPI=FAIL missing_encryption_key" >&2
    return 1
  }
  mkdir -p "$FREELLMAPI_STATE_ROOT" "$FREELLMAPI_CONFIG_ROOT"
  chmod 700 "$FREELLMAPI_STATE_ROOT" "$FREELLMAPI_CONFIG_ROOT"
  export NODE_ENV=production
  export HOST=127.0.0.1
  export PORT
  export FREEAPI_DB_PATH="$FREELLMAPI_STATE_ROOT/freellmapi.db"
  export FREEAPI_DB_DIR_HARDENING=1
  export ENCRYPTION_KEY
  ENCRYPTION_KEY="$(cat "$FREELLMAPI_ENCRYPTION_KEY_FILE")"
  export FREELLMAPI_UPDATE_CHECK=off
}

owned_runtime_pid() {
  local pid="$1" release cwd cmdline
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  test -r "/proc/$pid/cmdline" || return 1
  test -e "/proc/$pid/cwd" || return 1
  release="$(current_release)"
  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"

  case "$cwd|$cmdline" in
    "$release|"*"node server/dist/index.js"*)
      return 0
      ;;
    "$release|"*"npm run start -w server"*)
      return 0
      ;;
    "$release/server|"*"node dist/index.js"*)
      return 0
      ;;
    "$release/server|"*"sh -c node dist/index.js"*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

managed_pid_alive() {
  test -s "$FREELLMAPI_PID_FILE" || return 1
  local pid release cwd cmdline
  pid="$(cat "$FREELLMAPI_PID_FILE" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  release="$(current_release)"
  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  test "$cwd" = "$release" || return 1
  [[ "$cmdline" == *"node server/dist/index.js"* ]]
}

owned_runtime_pids() {
  local proc pid
  for proc in /proc/[0-9]*; do
    pid="${proc##*/}"
    if owned_runtime_pid "$pid"; then
      printf '%s\n' "$pid"
    fi
  done
}

stop_owned_runtime_processes() {
  local pids pid
  pids="$(owned_runtime_pids || true)"
  if [ -n "$pids" ]; then
    while IFS= read -r pid; do
      [ -n "$pid" ] || continue
      kill "$pid" 2>/dev/null || true
    done <<EOF
$pids
EOF

    for _ in 1 2 3 4 5; do
      local alive=""
      while IFS= read -r pid; do
        [ -n "$pid" ] || continue
        if kill -0 "$pid" 2>/dev/null; then
          alive="$alive $pid"
        fi
      done <<EOF
$pids
EOF
      [ -z "$alive" ] && break
      sleep 1
    done

    while IFS= read -r pid; do
      [ -n "$pid" ] || continue
      if kill -0 "$pid" 2>/dev/null && owned_runtime_pid "$pid"; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    done <<EOF
$pids
EOF
  fi
  rm -f "$FREELLMAPI_PID_FILE"
}

probe() {
  node - "$PORT" <<'NODE'
const port = process.argv[2];
fetch(`http://127.0.0.1:${port}/api/ping`)
  .then(r => process.exit(r.ok ? 0 : 1))
  .catch(() => process.exit(1));
NODE
}

start() {
  local release
  release="$(current_release)"
  load_runtime_env
  if managed_pid_alive && probe; then
    echo "HAZEWAVE_FREELLMAPI=ALREADY_RUNNING"
    return 0
  fi
  if probe >/dev/null 2>&1; then
    if [ -n "$(owned_runtime_pids || true)" ]; then
      echo "HAZEWAVE_FREELLMAPI=LEGACY_RUNTIME_ONLINE"
      echo "HAZEWAVE_FREELLMAPI_ACTION=restart_required_for_pid_rebind"
      return 4
    fi
  fi
  rm -f "$FREELLMAPI_PID_FILE"
  (
    cd "$release"
    nohup node server/dist/index.js >>"$FREELLMAPI_LOG_FILE" 2>&1 </dev/null &
    echo $! > "$FREELLMAPI_PID_FILE"
  )
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if managed_pid_alive && probe; then
      echo "HAZEWAVE_FREELLMAPI=ONLINE"
      echo "HAZEWAVE_FREELLMAPI_PID=$(cat "$FREELLMAPI_PID_FILE")"
      echo "HAZEWAVE_FREELLMAPI_URL=http://127.0.0.1:$PORT/v1"
      return 0
    fi
    sleep 1
  done
  echo "HAZEWAVE_FREELLMAPI=FAIL startup_timeout" >&2
  return 3
}

stop() {
  stop_owned_runtime_processes
  echo "HAZEWAVE_FREELLMAPI=STOPPED"
}

status() {
  local release sha recorded healthy=0
  release="$(current_release)"
  sha="$(git -C "$release" rev-parse HEAD)"
  recorded="$(cat "$FREELLMAPI_STATE_ROOT/active-sha" 2>/dev/null || true)"
  test -n "$recorded"
  test "$sha" = "$recorded"
  if managed_pid_alive && probe; then
    echo "HAZEWAVE_FREELLMAPI=ONLINE"
    echo "HAZEWAVE_FREELLMAPI_PROCESS_IDENTITY=MANAGED_DIRECT_NODE"
    healthy=1
  elif probe >/dev/null 2>&1 && [ -n "$(owned_runtime_pids || true)" ]; then
    echo "HAZEWAVE_FREELLMAPI=LEGACY_RUNTIME_ONLINE"
    echo "HAZEWAVE_FREELLMAPI_PROCESS_IDENTITY=LEGACY_NPM_WRAPPER_OR_CHILD"
  else
    echo "HAZEWAVE_FREELLMAPI=OFFLINE"
  fi
  echo "HAZEWAVE_FREELLMAPI_SHA=$sha"
  echo "HAZEWAVE_FREELLMAPI_URL=http://127.0.0.1:$PORT/v1"
  echo "HAZEWAVE_FREELLMAPI_LOOPBACK_ONLY=PASS"
  echo "HAZEWAVE_FREELLMAPI_UPDATE_CHECK=OFF"
  if [ -s "$FREELLMAPI_UNIFIED_KEY_FILE" ]; then
    echo "HAZEWAVE_FREELLMAPI_UNIFIED_KEY=CONFIGURED"
  else
    echo "HAZEWAVE_FREELLMAPI_UNIFIED_KEY=NOT_CONFIGURED"
  fi
  test "$healthy" -eq 1
}

doctor() {
  current_release >/dev/null
  load_runtime_env
  status
  echo "HAZEWAVE_FREELLMAPI_AUTHORITY=NONE"
  echo "HAZEWAVE_FREELLMAPI_PROJECT_AUTHORITY=HAZEWAVE_HARNESS"
  echo "HAZEWAVE_FREELLMAPI_PRIVATE_MEDIA_EGRESS=FORBIDDEN"
  echo "HAZEWAVE_FREE_FABRIC=ENFORCED"
  echo "HAZEWAVE_FREE_FABRIC_ZERO_COST_GUARD=ENFORCED"
  echo "HAZEWAVE_FREE_FABRIC_PAID_FALLBACK=FORBIDDEN"
  echo "HAZEWAVE_FREE_FABRIC_UNKNOWN_COST=DENY"
  echo "HAZEWAVE_FREE_FABRIC_PRIVATE_MEDIA_DEFAULT_EGRESS=DENY"
  echo "HAZEWAVE_FREE_FABRIC_UNREVIEWED_PROVIDER=QUARANTINED"
}

case "${1:-status}" in
  start)
    acquire_control_lock
    start
    ;;
  stop)
    acquire_control_lock
    stop
    ;;
  restart)
    acquire_control_lock
    stop
    start
    ;;
  status)
    status
    ;;
  doctor)
    doctor
    ;;
  logs)
    tail -n "${2:-100}" "$FREELLMAPI_LOG_FILE"
    ;;
  *)
    echo "usage: $0 {start|stop|restart|status|doctor|logs [lines]}" >&2
    exit 2
    ;;
esac
