#!/usr/bin/env bash
set -euo pipefail

STATE_ROOT="${HOME}/.local/state/hazewave-codespace"
mkdir -p "$STATE_ROOT"

if [[ "${CODESPACES:-}" != "true" ]]; then
  echo "HAZEWAVE_CODESPACE=BLOCKED_NOT_CODESPACES"
  exit 20
fi

if ! pgrep -f 'Xtigervnc.*:1' >/dev/null 2>&1; then
  vncserver :1     -localhost yes     -SecurityTypes None     -geometry 1440x900     -depth 24
fi

if ! pgrep -f 'websockify.*6080' >/dev/null 2>&1; then
  nohup websockify     --web=/usr/share/novnc     127.0.0.1:6080     localhost:5901     >"$STATE_ROOT/novnc.log" 2>&1 &
  echo $! > "$STATE_ROOT/novnc.pid"
fi

for _ in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:6080/vnc.html >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS http://127.0.0.1:6080/vnc.html >/dev/null

ARDOUR_BIN=""
for candidate in ardour9 ardour8 ardour7 ardour6 ardour; do
  if command -v "$candidate" >/dev/null 2>&1; then
    ARDOUR_BIN="$(command -v "$candidate")"
    break
  fi
done

[[ -n "$ARDOUR_BIN" ]] || {
  echo "ARDOUR=BLOCKED_NOT_INSTALLED"
  exit 21
}

if ! pgrep -f 'ardour' >/dev/null 2>&1; then
  nohup env DISPLAY=:1 "$ARDOUR_BIN" >"$STATE_ROOT/ardour.log" 2>&1 &
fi

echo "HAZEWAVE_CODESPACE_DESKTOP=PASS"
echo "NOVNC_PORT=6080"
echo "NOVNC_BIND=LOOPBACK_ONLY"
echo "ARDOUR=START_REQUESTED"
echo "REFERENCE_QC=LOCAL_A15"
echo "AUTOFORWARD_HINT=http://localhost:6080/vnc.html"
