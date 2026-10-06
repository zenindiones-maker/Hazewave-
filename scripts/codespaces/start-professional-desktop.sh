#!/usr/bin/env bash
set -euo pipefail

SESSION=":100"
PORT="14500"
STATE_ROOT="${HOME}/.local/state/hazewave-codespace"
SCRATCH="/tmp/hazewave-scratch"
CACHE="/tmp/hazewave-cache"
RUNTIME="/tmp/hazewave-runtime-${UID}"
SOCKET_DIR="${RUNTIME}/xpra"
LOG_FILE="${STATE_ROOT}/xpra-professional.log"

if [[ "${CODESPACES:-}" != "true" ]]; then
  echo "HAZEWAVE_PRO=BLOCKED_NOT_CODESPACES"
  exit 20
fi

for cmd in xpra curl ss xfce4-session; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "HAZEWAVE_PRO=BLOCKED_MISSING_$cmd"
    exit 21
  }
done

for pkg in xpra-x11 xpra-html5 xpra-audio-server; do
  dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed' || {
    echo "HAZEWAVE_PRO=BLOCKED_PACKAGE_$pkg"
    exit 22
  }
done

mkdir -p "$STATE_ROOT" "$SCRATCH" "$CACHE" "$SOCKET_DIR"
chmod 700 "$RUNTIME" "$SOCKET_DIR"
export XDG_RUNTIME_DIR="$RUNTIME"

ARDOUR_BIN=""
for candidate in ardour9 ardour8 ardour7 ardour6 ardour; do
  if command -v "$candidate" >/dev/null 2>&1; then
    ARDOUR_BIN="$(command -v "$candidate")"
    break
  fi
done

[[ -n "$ARDOUR_BIN" ]] || {
  echo "ARDOUR=BLOCKED_NOT_INSTALLED"
  exit 23
}

session_live() {
  xpra list --socket-dir="$SOCKET_DIR" 2>/dev/null |
    grep -Eq "LIVE.*${SESSION}|${SESSION}.*LIVE"
}

http_live() {
  curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1
}

if session_live && ! http_live; then
  echo "XPRA_SESSION=STALE_RECOVERY"
  xpra stop "$SESSION" --socket-dir="$SOCKET_DIR" >/dev/null 2>&1 || true
  sleep 2
fi

if ! session_live; then
  xpra start-desktop "$SESSION"     --socket-dir="$SOCKET_DIR"     --bind-tcp="127.0.0.1:${PORT},auth=none"     --html=on     --pulseaudio=yes     --speaker=on     --microphone=disabled     --webcam=no     --file-transfer=off     --open-files=off     --printing=no     --mdns=no     --sharing=no     --start-new-commands=no     --systemd-run=no     --resize-display=1600x900     --dpi=96     --session-name="Hazewave Professional"     --env="TMPDIR=${SCRATCH}"     --env="XDG_CACHE_HOME=${CACHE}"     --start-child="xfce4-session"     --start="$ARDOUR_BIN"     --exit-with-children=no     --log-file="$LOG_FILE"     --daemon=yes
fi

for _ in $(seq 1 60); do
  http_live && break
  sleep 1
done

if ! http_live; then
  echo "XPRA_HTML5=FAIL"
  tail -n 80 "$LOG_FILE" 2>/dev/null || true
  exit 24
fi

LISTEN_LINE="$(ss -ltn 2>/dev/null | awk -v p=":${PORT}" '$4 ~ p"$" {print $4; exit}')"
[[ "$LISTEN_LINE" == "127.0.0.1:${PORT}" ]] || {
  echo "XPRA_BIND=FAIL"
  echo "LISTEN=${LISTEN_LINE:-NONE}"
  exit 25
}

echo "HAZEWAVE_PRO_DESKTOP=PASS"
echo "REMOTE_TRANSPORT=XPRA_HTML5"
echo "XPRA_PORT=$PORT"
echo "XPRA_BIND=LOOPBACK_ONLY"
echo "SPEAKER_FORWARDING=CONFIGURED"
echo "MICROPHONE_FORWARDING=DISABLED"
echo "FILE_TRANSFER=DISABLED"
echo "PRINTING=DISABLED"
echo "NOVNC_FALLBACK_PORT=6080"
echo "SCRATCH_ROOT=$SCRATCH"
echo "CACHE_ROOT=$CACHE"
echo "REFERENCE_QC=LOCAL_A15"
echo "AUTOFORWARD_HINT=http://localhost:${PORT}/"
