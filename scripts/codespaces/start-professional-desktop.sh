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
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BRIDGE_SOURCE="$REPO_ROOT/scripts/reaper/hazewave_reaper_bridge.lua"
BRIDGE_INSTALL_RECEIPT="$STATE_ROOT/reaper-bridge-install.json"

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

REAPER_BIN="${HOME}/.local/bin/reaper"
EXPECTED_REAPER="${HOME}/.local/opt/reaper/7.82/REAPER/reaper"
[[ -x "$REAPER_BIN" ]] || {
  echo "REAPER_PRIMARY=BLOCKED_NOT_INSTALLED"
  exit 23
}
[[ "$(readlink -f "$REAPER_BIN")" == "$EXPECTED_REAPER" ]] || {
  echo "REAPER_PRIMARY=BLOCKED_UNEXPECTED_BINARY"
  echo "EXPECTED=$EXPECTED_REAPER"
  echo "ACTUAL=$(readlink -f "$REAPER_BIN")"
  exit 24
}

ASOUNDRC="${HOME}/.asoundrc"
[[ -f "$ASOUNDRC" ]] || {
  echo "REAPER_AUDIO_BRIDGE=BLOCKED_MISSING_ASOUNDRC"
  exit 25
}

grep -q "type pulse" "$ASOUNDRC" || {
  echo "REAPER_AUDIO_BRIDGE=BLOCKED_NOT_PULSE"
  exit 26
}

export PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
python -m hazewave.reaper_bridge_install   --source "$BRIDGE_SOURCE"   --resource-dir "${HOME}/.config/REAPER"   --receipt "$BRIDGE_INSTALL_RECEIPT"

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
  xpra start-desktop "$SESSION" \
    --socket-dir="$SOCKET_DIR" \
    --bind-tcp="127.0.0.1:${PORT},auth=none" \
    --html=on \
    --pulseaudio=yes \
    --speaker=on \
    --microphone=disabled \
    --webcam=no \
    --file-transfer=off \
    --open-files=off \
    --printing=no \
    --mdns=no \
    --sharing=no \
    --start-new-commands=no \
    --systemd-run=no \
    --resize-display=1600x900 \
    --dpi=96 \
    --session-name="Hazewave HAZE Audio / REAPER" \
    --env="TMPDIR=${SCRATCH}" \
    --env="XDG_CACHE_HOME=${CACHE}" \
    --start="xfce4-session" \
    --start="$REAPER_BIN" \
    --exit-with-children=no \
    --log-file="$LOG_FILE" \
    --daemon=yes
fi

for _ in $(seq 1 60); do
  http_live && break
  sleep 1
done

if ! http_live; then
  echo "XPRA_HTML5=FAIL"
  tail -n 80 "$LOG_FILE" 2>/dev/null || true
  exit 27
fi

LISTEN_LINE="$(ss -ltn 2>/dev/null | awk -v p=":${PORT}" '$4 ~ p"$" {print $4; exit}')"
[[ "$LISTEN_LINE" == "127.0.0.1:${PORT}" ]] || {
  echo "XPRA_BIND=FAIL"
  echo "LISTEN=${LISTEN_LINE:-NONE}"
  exit 28
}

echo "HAZEWAVE_PRO_DESKTOP=PASS"
echo "WORKSTATION_ROLE=HAZE_AUDIO_REAPER"
echo "REAPER_PRIMARY=PASS"
echo "REAPER_VERSION_PIN=7.82"
echo "REAPER_AUDIO_BRIDGE=ALSA_PULSE"
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
