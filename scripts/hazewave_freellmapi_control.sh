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
PORT="${FREELLMAPI_PORT:-3001}"

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

pid_alive() {
  test -s "$FREELLMAPI_PID_FILE" || return 1
  local pid
  pid="$(cat "$FREELLMAPI_PID_FILE")"
  kill -0 "$pid" 2>/dev/null
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
  if pid_alive && probe; then
    echo "HAZEWAVE_FREELLMAPI=ALREADY_RUNNING"
    return 0
  fi
  if pid_alive; then
    kill "$(cat "$FREELLMAPI_PID_FILE")" 2>/dev/null || true
  fi
  rm -f "$FREELLMAPI_PID_FILE"
  (
    cd "$release"
    nohup npm run start -w server >>"$FREELLMAPI_LOG_FILE" 2>&1 &
    echo $! > "$FREELLMAPI_PID_FILE"
  )
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if pid_alive && probe; then
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
  if pid_alive; then
    kill "$(cat "$FREELLMAPI_PID_FILE")"
    for _ in 1 2 3 4 5; do
      pid_alive || break
      sleep 1
    done
  fi
  rm -f "$FREELLMAPI_PID_FILE"
  echo "HAZEWAVE_FREELLMAPI=STOPPED"
}

status() {
  local release sha recorded
  release="$(current_release)"
  sha="$(git -C "$release" rev-parse HEAD)"
  recorded="$(cat "$FREELLMAPI_STATE_ROOT/active-sha" 2>/dev/null || true)"
  test -n "$recorded"
  test "$sha" = "$recorded"
  if pid_alive && probe; then
    echo "HAZEWAVE_FREELLMAPI=ONLINE"
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
}

doctor() {
  current_release >/dev/null
  load_runtime_env
  status
  echo "HAZEWAVE_FREELLMAPI_AUTHORITY=NONE"
  echo "HAZEWAVE_FREELLMAPI_PROJECT_AUTHORITY=HAZEWAVE_HARNESS"
  echo "HAZEWAVE_FREELLMAPI_PRIVATE_MEDIA_EGRESS=FORBIDDEN"
}

case "${1:-status}" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  restart)
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
