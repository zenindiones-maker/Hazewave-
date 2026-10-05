#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${HAZEWAVE_9ROUTER_ROOT:-$HOME/.local/share/hazewave/providers/9router}"
CURRENT="$ROOT/current"
STATE_ROOT="${HAZEWAVE_9ROUTER_STATE_ROOT:-$HOME/.local/state/hazewave/providers/9router}"
RUNTIME_HOME="$STATE_ROOT/home"
PID_FILE="$STATE_ROOT/launcher.pid"
OWNERSHIP_FILE="$STATE_ROOT/ownership.meta"
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

write_ownership_metadata() {
  local release pid
  release="$(current_release)"
  pid="$1"
  {
    printf 'pid=%s\n' "$pid"
    printf 'release=%s\n' "$release"
    printf 'host=%s\n' "$HOST"
    printf 'port=%s\n' "$PORT"
  } > "$OWNERSHIP_FILE"
  chmod 600 "$OWNERSHIP_FILE"
}

ownership_metadata_matches() {
  test -s "$OWNERSHIP_FILE" || return 1
  local pid expected_release meta_pid meta_release meta_host meta_port
  pid="$1"
  expected_release="$(current_release)"
  meta_pid="$(sed -n 's/^pid=//p' "$OWNERSHIP_FILE" | head -n1)"
  meta_release="$(sed -n 's/^release=//p' "$OWNERSHIP_FILE" | head -n1)"
  meta_host="$(sed -n 's/^host=//p' "$OWNERSHIP_FILE" | head -n1)"
  meta_port="$(sed -n 's/^port=//p' "$OWNERSHIP_FILE" | head -n1)"
  test "$meta_pid" = "$pid"
  test "$meta_release" = "$expected_release"
  test "$meta_host" = "$HOST"
  test "$meta_port" = "$PORT"
}

owned_server_alive() {
  test -s "$PID_FILE" || return 1
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  ownership_metadata_matches "$pid"
}

adopt_legacy_pid_file() {
  test -s "$PID_FILE" || return 1
  test -s "$OWNERSHIP_FILE" && return 0
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  probe >/dev/null 2>&1 || return 1
  write_ownership_metadata "$pid"
  echo "HAZEWAVE_9ROUTER_PID_ADOPTED=$pid"
  echo "HAZEWAVE_9ROUTER_OWNERSHIP=PASS"
}

ensure_cli_auth_material() {
  local data_dir auth_dir machine_file secret_file created machine_tmp secret_tmp
  data_dir="$RUNTIME_HOME/.9router"
  auth_dir="$data_dir/auth"
  machine_file="$data_dir/machine-id"
  secret_file="$auth_dir/cli-secret"
  created=0

  mkdir -p "$auth_dir"
  chmod 700 "$data_dir" "$auth_dir"

  if ! test -s "$machine_file"; then
    machine_tmp="$machine_file.tmp.$"
    umask 077
    node -e 'process.stdout.write(require("crypto").randomUUID())' > "$machine_tmp"
    chmod 600 "$machine_tmp"
    mv "$machine_tmp" "$machine_file"
    created=1
  fi

  if ! test -s "$secret_file"; then
    secret_tmp="$secret_file.tmp.$"
    umask 077
    node -e 'process.stdout.write(require("crypto").randomBytes(32).toString("hex"))' > "$secret_tmp"
    chmod 600 "$secret_tmp"
    mv "$secret_tmp" "$secret_file"
    created=1
  fi

  chmod 600 "$machine_file" "$secret_file"
  echo "HAZEWAVE_9ROUTER_CLI_AUTH_MATERIAL=READY"
  echo "HAZEWAVE_9ROUTER_CLI_AUTH_CREATED=$created"
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
  adopt_legacy_pid_file || true
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
  ensure_cli_auth_material >/dev/null
  entry="$(server_entry)"
  runtime_node_path="$RUNTIME_HOME/.9router/runtime/node_modules"

  HOME="$RUNTIME_HOME" \
  DATA_DIR="$RUNTIME_HOME/.9router" \
  PORT="$PORT" \
  HOSTNAME="$HOST" \
  NODE_PATH="$runtime_node_path" \
  nohup node "$entry" >>"$LOG_FILE" 2>&1 </dev/null &
  pid=$!
  printf '%s\n' "$pid" > "$PID_FILE"
  write_ownership_metadata "$pid"

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

  rm -f "$PID_FILE" "$OWNERSHIP_FILE"
  echo "HAZEWAVE_9ROUTER=STOPPED"
}

status_runtime() {
  local release version commit
  release="$(current_release)"
  version="$(cat "$release/UPSTREAM_VERSION")"
  commit="$(cat "$release/UPSTREAM_COMMIT")"

  if probe; then
    adopt_legacy_pid_file || true
    if ! owned_server_alive; then
      echo "HAZEWAVE_9ROUTER=FAIL unmanaged_process_on_port_$PORT" >&2
      return 3
    fi
    echo "HAZEWAVE_9ROUTER=ONLINE"
    echo "HAZEWAVE_9ROUTER_OWNERSHIP=PASS"
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
  ensure-auth)
    ensure_cli_auth_material
    ;;
  catalog)
    exec bash "$SCRIPT_DIR/hazewave_9router_free_probe.sh" catalog
    ;;
  probe-free)
    exec bash "$SCRIPT_DIR/hazewave_9router_free_probe.sh" probe
    ;;
  logs)
    tail -n "${2:-100}" "$LOG_FILE"
    ;;
  *)
    echo "usage: $0 {install|start|stop|restart|status|doctor|ensure-auth|catalog|probe-free|logs [lines]}" >&2
    exit 2
    ;;
esac
