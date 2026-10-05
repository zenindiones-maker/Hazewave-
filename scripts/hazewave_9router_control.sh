#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${HAZEWAVE_9ROUTER_ROOT:-$HOME/.local/share/hazewave/providers/9router}"
CURRENT="$ROOT/current"
STATE_ROOT="${HAZEWAVE_9ROUTER_STATE_ROOT:-$HOME/.local/state/hazewave/providers/9router}"
RUNTIME_HOME="$STATE_ROOT/home"
PID_FILE="$STATE_ROOT/launcher.pid"
LOG_FILE="$STATE_ROOT/server.log"
HOST="127.0.0.1"
PORT="${HAZEWAVE_9ROUTER_PORT:-20128}"

current_release() {
  test -L "$CURRENT" || {
    echo "HAZEWAVE_9ROUTER=NOT_INSTALLED"
    return 1
  }
  readlink -f "$CURRENT"
}

server_entry() {
  local release custom fallback
  release="$(current_release)"
  custom="$release/node_modules/9router/app/custom-server.js"
  fallback="$release/node_modules/9router/app/server.js"
  if test -f "$custom"; then
    printf '%s\n' "$custom"
  elif test -f "$fallback"; then
    printf '%s\n' "$fallback"
  else
    echo "HAZEWAVE_9ROUTER=FAIL standalone_server_missing" >&2
    return 2
  fi
}

owned_server_alive() {
  test -s "$PID_FILE" || return 1
  local pid release cmdline
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  release="$(current_release)"
  test -r "/proc/$pid/cmdline" || return 1
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmdline" == *"$release/node_modules/9router/app/custom-server.js"* || "$cmdline" == *"$release/node_modules/9router/app/server.js"* ]]
}

probe() {
  node - "$PORT" <<'NODE'
const port = process.argv[2];
fetch(`http://127.0.0.1:${port}/api/health`)
  .then(async r => {
    if (!r.ok) process.exit(1);
    const body = await r.json().catch(() => null);
    process.exit(body && body.ok === true ? 0 : 1);
  })
  .catch(() => process.exit(1));
NODE
}

install_runtime() {
  local hazewave_release installer
  hazewave_release="${HAZEWAVE_RUNTIME_CURRENT:-$HOME/.local/share/hazewave/deploy/current}"
  installer="$hazewave_release/scripts/install_hazewave_9router_termux.sh"
  test -f "$installer" || {
    echo "HAZEWAVE_9ROUTER_INSTALL=FAIL installer_not_found" >&2
    return 2
  }
  bash "$installer"
}

start_runtime() {
  local entry pid runtime_node_path
  mkdir -p "$STATE_ROOT" "$RUNTIME_HOME"
  chmod 700 "$STATE_ROOT" "$RUNTIME_HOME"

  if owned_server_alive && probe; then
    echo "HAZEWAVE_9ROUTER=ALREADY_RUNNING"
    return 0
  fi

  if probe >/dev/null 2>&1; then
    echo "HAZEWAVE_9ROUTER=FAIL unmanaged_process_on_port_$PORT" >&2
    return 3
  fi

  rm -f "$PID_FILE"
  bin="$(launcher_bin)"

  if command -v setsid >/dev/null 2>&1; then
    HOME="$RUNTIME_HOME" nohup setsid "$bin"       --host "$HOST"       --port "$PORT"       --no-browser       --skip-update       --log       >>"$LOG_FILE" 2>&1 </dev/null &
  else
    HOME="$RUNTIME_HOME" nohup "$bin"       --host "$HOST"       --port "$PORT"       --no-browser       --skip-update       --log       >>"$LOG_FILE" 2>&1 </dev/null &
  fi
  pid=$!
  printf '%s\n' "$pid" > "$PID_FILE"

  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    if probe; then
      echo "HAZEWAVE_9ROUTER=ONLINE"
      echo "HAZEWAVE_9ROUTER_PID=$pid"
      echo "HAZEWAVE_9ROUTER_URL=http://$HOST:$PORT/v1"
      return 0
    fi
    sleep 1
  done

  echo "HAZEWAVE_9ROUTER=FAIL startup_timeout" >&2
  tail -n 80 "$LOG_FILE" >&2 2>/dev/null || true
  return 4
}

stop_runtime() {
  local pid=""
  if test -s "$PID_FILE"; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  fi

  if owned_server_alive; then
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi

  rm -f "$PID_FILE"
  echo "HAZEWAVE_9ROUTER=STOPPED"
}

status_runtime() {
  local release version commit
  release="$(current_release)"
  version="$(cat "$release/UPSTREAM_VERSION")"
  commit="$(cat "$release/UPSTREAM_COMMIT")"

  if probe; then
    if ! owned_server_alive; then
      echo "HAZEWAVE_9ROUTER=FAIL unmanaged_process_on_port_$PORT" >&2
      return 3
    fi
    echo "HAZEWAVE_9ROUTER=ONLINE"
  else
    echo "HAZEWAVE_9ROUTER=OFFLINE"
  fi

  echo "HAZEWAVE_9ROUTER_VERSION=$version"
  echo "HAZEWAVE_9ROUTER_UPSTREAM_COMMIT=$commit"
  echo "HAZEWAVE_9ROUTER_BIND=$HOST:$PORT"
  echo "HAZEWAVE_9ROUTER_LOOPBACK_ONLY=PASS"
  echo "HAZEWAVE_9ROUTER_AUTHORITY=NONE"
  echo "HAZEWAVE_9ROUTER_PROJECT_AUTHORITY=HAZEWAVE_HARNESS"
  echo "HAZEWAVE_9ROUTER_PAID_FALLBACK=FORBIDDEN"
  echo "HAZEWAVE_9ROUTER_UNKNOWN_COST=DENY"
  echo "HAZEWAVE_9ROUTER_EXECUTION_POLICY=DISCOVERY_ONLY_UNTIL_ROUTE_ADMISSION"
}

doctor_runtime() {
  status_runtime
  echo "HAZEWAVE_9ROUTER_SECURITY_BIND=LOOPBACK_ONLY"
  echo "HAZEWAVE_9ROUTER_AUTO_UPDATE=OFF_DIRECT_STANDALONE_SERVER"
  echo "HAZEWAVE_9ROUTER_FREE_ROUTE_ADMISSION=PENDING_RUNTIME_CATALOG_PROOF"
}

case "${1:-status}" in
  install)
    install_runtime
    ;;
  start)
    start_runtime
    ;;
  stop)
    stop_runtime
    ;;
  restart)
    stop_runtime
    start_runtime
    ;;
  status)
    status_runtime
    ;;
  doctor)
    doctor_runtime
    ;;
  logs)
    tail -n "${2:-100}" "$LOG_FILE"
    ;;
  *)
    echo "usage: $0 {install|start|stop|restart|status|doctor|logs [lines]}" >&2
    exit 2
    ;;
esac
