#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

HAZEWAVE_DEPLOY_ROOT="${HAZEWAVE_DEPLOY_ROOT:-$HOME/.local/share/hazewave/deploy}"
HAZEWAVE_RUNTIME_STATE_ROOT="${HAZEWAVE_STATE_ROOT:-$HOME/.local/state/hazewave}"
HAZEWAVE_CURRENT="$HAZEWAVE_DEPLOY_ROOT/current"

HAZEWAVE_TELEGRAM_CONFIG_ROOT="${HAZEWAVE_TELEGRAM_CONFIG_ROOT:-$HOME/.config/hazewave/telegram}"
HAZEWAVE_TELEGRAM_STATE_ROOT="${HAZEWAVE_TELEGRAM_STATE_ROOT:-$HOME/.local/state/hazewave/telegram}"

PID_FILE="$HAZEWAVE_TELEGRAM_STATE_ROOT/gateway.pid"
LOG_FILE="$HAZEWAVE_TELEGRAM_STATE_ROOT/gateway.log"
REVISION_FILE="$HAZEWAVE_TELEGRAM_STATE_ROOT/runtime-revision"
READY_FILE="$HAZEWAVE_TELEGRAM_STATE_ROOT/ready"
TOKEN_FILE="$HAZEWAVE_TELEGRAM_CONFIG_ROOT/bot-token"

mkdir -p "$HAZEWAVE_TELEGRAM_STATE_ROOT" "$HAZEWAVE_TELEGRAM_CONFIG_ROOT"
chmod 700 "$HAZEWAVE_TELEGRAM_STATE_ROOT" "$HAZEWAVE_TELEGRAM_CONFIG_ROOT" 2>/dev/null || true

current_release() {
  test -L "$HAZEWAVE_CURRENT" || {
    echo "HAZEWAVE_TELEGRAM=FAIL runtime_not_installed" >&2
    return 1
  }
  readlink -f "$HAZEWAVE_CURRENT"
}

active_sha() {
  local value
  value="$(cat "$HAZEWAVE_RUNTIME_STATE_ROOT/active-sha" 2>/dev/null || true)"
  test -n "$value" || {
    echo "HAZEWAVE_TELEGRAM=FAIL active_sha_missing" >&2
    return 1
  }
  printf '%s\n' "$value"
}

pid_is_gateway() {
  local pid="$1"
  test -r "/proc/$pid/cmdline" || return 1
  tr '\0' '\n' < "/proc/$pid/cmdline" 2>/dev/null | grep -Fxq "hazewave.telegram_gateway"
}

preflight() {
  local release expected observed
  release="$(current_release)"
  expected="$(active_sha)"
  observed="$(git -C "$release" rev-parse HEAD)"
  test "$observed" = "$expected" || {
    echo "HAZEWAVE_TELEGRAM=FAIL runtime_sha_mismatch expected=$expected observed=$observed" >&2
    return 1
  }
  test -f "$release/src/hazewave/telegram_gateway.py"
  test -s "$TOKEN_FILE" || {
    echo "HAZEWAVE_TELEGRAM=NOT_CONFIGURED token_missing" >&2
    return 1
  }
}

is_running() {
  test -s "$PID_FILE" || return 1
  local pid expected loaded
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  pid_is_gateway "$pid" || return 1
  expected="$(active_sha 2>/dev/null || true)"
  loaded="$(cat "$REVISION_FILE" 2>/dev/null || true)"
  test -n "$expected" && test "$loaded" = "$expected" || return 1
  test -s "$READY_FILE" || return 1
}

stop_gateway() {
  if [ -s "$PID_FILE" ]; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null && pid_is_gateway "$pid"; then
      kill "$pid" 2>/dev/null || true
      for _ in 1 2 3 4 5; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
      done
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
  rm -f "$PID_FILE" "$REVISION_FILE" "$READY_FILE"
  echo "HAZEWAVE_TELEGRAM_GATEWAY=STOPPED"
}

start_gateway() {
  preflight
  if is_running; then
    echo "HAZEWAVE_TELEGRAM_GATEWAY=ALREADY_RUNNING PID=$(cat "$PID_FILE")"
    return 0
  fi

  stop_gateway >/dev/null 2>&1 || true

  local release sha
  release="$(current_release)"
  sha="$(active_sha)"
  rm -f "$REVISION_FILE" "$READY_FILE"

  HAZEWAVE_TELEGRAM_CONFIG_ROOT="$HAZEWAVE_TELEGRAM_CONFIG_ROOT" \
  HAZEWAVE_TELEGRAM_STATE_ROOT="$HAZEWAVE_TELEGRAM_STATE_ROOT" \
  HAZEWAVE_RUNTIME_SHA="$sha" \
  PYTHONPATH="$release/src" \
    nohup python -u -m hazewave.telegram_gateway serve \
      >>"$LOG_FILE" 2>&1 </dev/null &
  local pid=$!
  printf '%s\n' "$pid" > "$PID_FILE"
  chmod 600 "$PID_FILE"

  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "HAZEWAVE_TELEGRAM_GATEWAY=FAIL process_exited" >&2
      tail -n 80 "$LOG_FILE" >&2 || true
      rm -f "$PID_FILE"
      return 1
    fi
    if [ "$(cat "$REVISION_FILE" 2>/dev/null || true)" = "$sha" ] && [ -s "$READY_FILE" ]; then
      echo "HAZEWAVE_TELEGRAM_GATEWAY=ONLINE PID=$pid"
      echo "HAZEWAVE_TELEGRAM_RUNTIME_SHA=$sha"
      return 0
    fi
    sleep 1
  done

  echo "HAZEWAVE_TELEGRAM_GATEWAY=FAIL readiness_timeout" >&2
  tail -n 80 "$LOG_FILE" >&2 || true
  stop_gateway >/dev/null 2>&1 || true
  return 1
}

status_gateway() {
  local sha
  sha="$(active_sha)"
  if is_running; then
    echo "HAZEWAVE_TELEGRAM_GATEWAY=ONLINE"
    echo "HAZEWAVE_TELEGRAM_PID=$(cat "$PID_FILE")"
    echo "HAZEWAVE_TELEGRAM_RUNTIME_SHA=$sha"
    echo "HAZEWAVE_TELEGRAM_BOT=@HazewaveAgentBot"
    if [ -s "$HAZEWAVE_TELEGRAM_CONFIG_ROOT/allowed-user-id" ]; then
      echo "HAZEWAVE_TELEGRAM_PAIRED=YES"
    else
      echo "HAZEWAVE_TELEGRAM_PAIRED=NO"
    fi
    return 0
  fi
  echo "HAZEWAVE_TELEGRAM_GATEWAY=OFFLINE"
  echo "HAZEWAVE_TELEGRAM_EXPECTED_RUNTIME_SHA=$sha"
  return 1
}

doctor_gateway() {
  preflight
  local release sha
  release="$(current_release)"
  sha="$(active_sha)"
  HAZEWAVE_TELEGRAM_CONFIG_ROOT="$HAZEWAVE_TELEGRAM_CONFIG_ROOT" \
  HAZEWAVE_TELEGRAM_STATE_ROOT="$HAZEWAVE_TELEGRAM_STATE_ROOT" \
  HAZEWAVE_RUNTIME_SHA="$sha" \
  PYTHONPATH="$release/src" \
    python -m hazewave.telegram_gateway doctor
  status_gateway || true
}

case "${1:-status}" in
  start)
    start_gateway
    ;;
  stop)
    stop_gateway
    ;;
  restart)
    stop_gateway
    start_gateway
    ;;
  status)
    status_gateway
    ;;
  doctor)
    doctor_gateway
    ;;
  pair-code)
    if [ -s "$HAZEWAVE_TELEGRAM_CONFIG_ROOT/pairing-code" ]; then
      echo "HAZEWAVE_TELEGRAM_PAIRING_CODE=$(cat "$HAZEWAVE_TELEGRAM_CONFIG_ROOT/pairing-code")"
    elif [ -s "$HAZEWAVE_TELEGRAM_CONFIG_ROOT/allowed-user-id" ]; then
      echo "HAZEWAVE_TELEGRAM_PAIRING=ALREADY_BOUND"
    else
      echo "HAZEWAVE_TELEGRAM_PAIRING=NOT_CONFIGURED"
      exit 1
    fi
    ;;
  logs)
    tail -n "${2:-80}" "$LOG_FILE" 2>/dev/null || true
    ;;
  *)
    echo "usage: $0 {start|stop|restart|status|doctor|pair-code|logs}" >&2
    exit 2
    ;;
esac
