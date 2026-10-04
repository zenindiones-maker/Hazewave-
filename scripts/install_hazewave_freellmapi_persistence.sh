#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

HAZEWAVE_DEPLOY_ROOT="${HAZEWAVE_DEPLOY_ROOT:-$HOME/.local/share/hazewave/deploy}"
HAZEWAVE_CURRENT="$HAZEWAVE_DEPLOY_ROOT/current"
FREELLMAPI_STATE_ROOT="${FREELLMAPI_STATE_ROOT:-$HOME/.local/state/hazewave/providers/freellmapi}"
FREELLMAPI_CONFIG_ROOT="${FREELLMAPI_CONFIG_ROOT:-$HOME/.config/hazewave/providers/freellmapi}"

CONTROL="$HAZEWAVE_CURRENT/scripts/hazewave_freellmapi_control.sh"
SUPERVISOR="$FREELLMAPI_CONFIG_ROOT/supervisor.sh"
SUPERVISOR_PID="$FREELLMAPI_STATE_ROOT/supervisor.pid"
SUPERVISOR_LOG="$FREELLMAPI_STATE_ROOT/supervisor.log"
LOCK_DIR="$FREELLMAPI_STATE_ROOT/supervisor.lock"
LOCK_OWNER_FILE="$LOCK_DIR/owner.pid"
BOOT_DIR="$HOME/.termux/boot"
BOOT_SCRIPT="$BOOT_DIR/hazewave-freellmapi.sh"

mkdir -p "$FREELLMAPI_CONFIG_ROOT" "$FREELLMAPI_STATE_ROOT" "$BOOT_DIR"
chmod 700 "$FREELLMAPI_CONFIG_ROOT" "$FREELLMAPI_STATE_ROOT" "$BOOT_DIR" 2>/dev/null || true

test -L "$HAZEWAVE_CURRENT" || {
  echo "HAZEWAVE_FREELLMAPI_PERSISTENCE=FAIL hazewave_runtime_not_installed" >&2
  exit 2
}
test -f "$CONTROL" || {
  echo "HAZEWAVE_FREELLMAPI_PERSISTENCE=FAIL control_missing:$CONTROL" >&2
  exit 2
}

cat > "$SUPERVISOR" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -u

SELF="$HOME/.config/hazewave/providers/freellmapi/supervisor.sh"
CONTROL="$HOME/.local/share/hazewave/deploy/current/scripts/hazewave_freellmapi_control.sh"
STATE_ROOT="$HOME/.local/state/hazewave/providers/freellmapi"
PID_FILE="$STATE_ROOT/supervisor.pid"
LOG_FILE="$STATE_ROOT/supervisor.log"
LOCK_DIR="$STATE_ROOT/supervisor.lock"
LOCK_OWNER_FILE="$LOCK_DIR/owner.pid"

supervisor_process_matches() {
  local pid="$1" cmdline
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  test -r "/proc/$pid/cmdline" || return 1
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmdline" == *"$SELF"* ]]
}

acquire_supervisor_lock() {
  local attempt owner stale_dir
  mkdir -p "$STATE_ROOT"

  for attempt in 1 2 3; do
    if mkdir "$LOCK_DIR" 2>/dev/null; then
      printf '%s\n' "$$" > "$LOCK_OWNER_FILE"
      printf '%s\n' "$$" > "$PID_FILE"
      return 0
    fi

    owner="$(cat "$LOCK_OWNER_FILE" 2>/dev/null || true)"
    if [ -z "$owner" ]; then
      sleep 0.1
      owner="$(cat "$LOCK_OWNER_FILE" 2>/dev/null || true)"
    fi

    if supervisor_process_matches "$owner"; then
      printf '%s\n' "$owner" > "$PID_FILE"
      printf '%s HAZEWAVE_FREELLMAPI_SUPERVISOR=SINGLETON_ALREADY_HELD PID=%s\n' \
        "$(date -Iseconds 2>/dev/null || date)" "$owner" >> "$LOG_FILE"
      return 75
    fi

    stale_dir="${LOCK_DIR}.stale.$$.$attempt"
    if mv "$LOCK_DIR" "$stale_dir" 2>/dev/null; then
      rm -f "$stale_dir/owner.pid"
      if ! rmdir "$stale_dir" 2>/dev/null; then
        printf '%s HAZEWAVE_FREELLMAPI_SUPERVISOR_STALE_LOCK=UNSAFE_CONTENT\n' \
          "$(date -Iseconds 2>/dev/null || date)" >> "$LOG_FILE"
        return 76
      fi
      printf '%s HAZEWAVE_FREELLMAPI_SUPERVISOR_STALE_LOCK=RECOVERED\n' \
        "$(date -Iseconds 2>/dev/null || date)" >> "$LOG_FILE"
      continue
    fi

    sleep 0.1
  done

  printf '%s HAZEWAVE_FREELLMAPI_SUPERVISOR=LOCK_ACQUIRE_FAILED\n' \
    "$(date -Iseconds 2>/dev/null || date)" >> "$LOG_FILE"
  return 75
}

cleanup() {
  local recorded owner
  recorded="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ "$recorded" = "$$" ]; then
    rm -f "$PID_FILE"
  fi

  owner="$(cat "$LOCK_OWNER_FILE" 2>/dev/null || true)"
  if [ "$owner" = "$$" ]; then
    rm -f "$LOCK_OWNER_FILE"
    rmdir "$LOCK_DIR" 2>/dev/null || true
  fi
}

acquire_supervisor_lock
lock_rc=$?
if [ "$lock_rc" -ne 0 ]; then
  exit "$lock_rc"
fi
trap cleanup EXIT INT TERM

if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock >/dev/null 2>&1 || true
fi

while true; do
  if [ -f "$CONTROL" ]; then
    if ! bash "$CONTROL" status >>"$LOG_FILE" 2>&1; then
      printf '%s HAZEWAVE_FREELLMAPI_SUPERVISOR=RECONCILING\n' "$(date -Iseconds 2>/dev/null || date)" >> "$LOG_FILE"
      bash "$CONTROL" restart >>"$LOG_FILE" 2>&1 || true
    fi
  else
    printf '%s HAZEWAVE_FREELLMAPI_SUPERVISOR=CONTROL_MISSING\n' "$(date -Iseconds 2>/dev/null || date)" >> "$LOG_FILE"
  fi
  sleep 30
done
EOF
chmod 700 "$SUPERVISOR"

cat > "$BOOT_SCRIPT" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -u

SUPERVISOR="$HOME/.config/hazewave/providers/freellmapi/supervisor.sh"
STATE_ROOT="$HOME/.local/state/hazewave/providers/freellmapi"
PID_FILE="$STATE_ROOT/supervisor.pid"
LOCK_OWNER_FILE="$STATE_ROOT/supervisor.lock/owner.pid"
LOG_FILE="$STATE_ROOT/supervisor.log"

supervisor_process_matches() {
  local pid="$1" cmdline
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  test -r "/proc/$pid/cmdline" || return 1
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmdline" == *"$SUPERVISOR"* ]]
}

mkdir -p "$STATE_ROOT"
sleep 10

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if supervisor_process_matches "$pid"; then
  exit 0
fi

owner="$(cat "$LOCK_OWNER_FILE" 2>/dev/null || true)"
if supervisor_process_matches "$owner"; then
  printf '%s\n' "$owner" > "$PID_FILE"
  exit 0
fi

rm -f "$PID_FILE"
nohup bash "$SUPERVISOR" >>"$LOG_FILE" 2>&1 </dev/null &
EOF
chmod 700 "$BOOT_SCRIPT"

supervisor_process_matches() {
  local pid="$1" cmdline
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  test -r "/proc/$pid/cmdline" || return 1
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmdline" == *"$SUPERVISOR"* ]]
}

old_pid="$(cat "$SUPERVISOR_PID" 2>/dev/null || true)"
lock_owner="$(cat "$LOCK_OWNER_FILE" 2>/dev/null || true)"

for candidate in "$old_pid" "$lock_owner"; do
  if supervisor_process_matches "$candidate"; then
    kill -TERM "$candidate" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      supervisor_process_matches "$candidate" || break
      sleep 1
    done
    if supervisor_process_matches "$candidate"; then
      kill -KILL "$candidate" 2>/dev/null || true
    fi
  fi
done

rm -f "$SUPERVISOR_PID"

bash "$CONTROL" restart
nohup bash "$SUPERVISOR" >>"$SUPERVISOR_LOG" 2>&1 </dev/null &
sleep 1

new_pid="$(cat "$SUPERVISOR_PID" 2>/dev/null || true)"
if ! supervisor_process_matches "$new_pid"; then
  echo "HAZEWAVE_FREELLMAPI_PERSISTENCE=FAIL supervisor_not_running" >&2
  exit 3
fi

echo "HAZEWAVE_FREELLMAPI_PERSISTENCE=PASS"
echo "HAZEWAVE_FREELLMAPI_SUPERVISOR=$SUPERVISOR"
echo "HAZEWAVE_FREELLMAPI_BOOT_SCRIPT=$BOOT_SCRIPT"
echo "HAZEWAVE_FREELLMAPI_STATE_ROOT=$FREELLMAPI_STATE_ROOT"
echo "HAZEWAVE_FREELLMAPI_CONFIG_ROOT=$FREELLMAPI_CONFIG_ROOT"
