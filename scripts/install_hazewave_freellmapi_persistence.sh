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

CONTROL="$HOME/.local/share/hazewave/deploy/current/scripts/hazewave_freellmapi_control.sh"
STATE_ROOT="$HOME/.local/state/hazewave/providers/freellmapi"
PID_FILE="$STATE_ROOT/supervisor.pid"
LOG_FILE="$STATE_ROOT/supervisor.log"
LOCK_DIR="$STATE_ROOT/supervisor.lock"

mkdir -p "$STATE_ROOT"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  printf '%s HAZEWAVE_FREELLMAPI_SUPERVISOR=SINGLETON_ALREADY_HELD\n' "$(date -Iseconds 2>/dev/null || date)" >> "$LOG_FILE"
  exit 0
fi
printf '%s\n' "$$" > "$PID_FILE"

cleanup() {
  rm -f "$PID_FILE"
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
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
LOG_FILE="$STATE_ROOT/supervisor.log"

mkdir -p "$STATE_ROOT"
sleep 10
if [ -s "$PID_FILE" ]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    exit 0
  fi
fi
nohup bash "$SUPERVISOR" >>"$LOG_FILE" 2>&1 </dev/null &
EOF
chmod 700 "$BOOT_SCRIPT"

if [ -s "$SUPERVISOR_PID" ]; then
  old_pid="$(cat "$SUPERVISOR_PID" 2>/dev/null || true)"
  if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
    kill "$old_pid" 2>/dev/null || true
    sleep 1
  fi
fi
rm -f "$SUPERVISOR_PID"
rmdir "$LOCK_DIR" 2>/dev/null || true

bash "$CONTROL" start
nohup bash "$SUPERVISOR" >>"$SUPERVISOR_LOG" 2>&1 </dev/null &
sleep 1

echo "HAZEWAVE_FREELLMAPI_PERSISTENCE=PASS"
echo "HAZEWAVE_FREELLMAPI_SUPERVISOR=$SUPERVISOR"
echo "HAZEWAVE_FREELLMAPI_BOOT_SCRIPT=$BOOT_SCRIPT"
echo "HAZEWAVE_FREELLMAPI_STATE_ROOT=$FREELLMAPI_STATE_ROOT"
echo "HAZEWAVE_FREELLMAPI_CONFIG_ROOT=$FREELLMAPI_CONFIG_ROOT"
