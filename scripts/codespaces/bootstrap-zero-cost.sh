#!/usr/bin/env bash
set -euo pipefail

STATE_ROOT="${HOME}/.local/state/hazewave-codespace"
MARKER="${STATE_ROOT}/bootstrap-v2"
mkdir -p "$STATE_ROOT"

if [[ "${CODESPACES:-}" != "true" ]]; then
  echo "HAZEWAVE_CODESPACE=BLOCKED_NOT_CODESPACES"
  exit 20
fi

if [[ ! -f "$MARKER" ]]; then
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends     ardour     ffmpeg     sox     libsox-fmt-all     xfce4     xfce4-terminal     tigervnc-standalone-server     novnc     websockify     python3-venv     jq     curl     dbus-x11     ca-certificates

  mkdir -p "$HOME/.vnc"
  cat > "$HOME/.vnc/xstartup" <<'XSTART'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec dbus-launch --exit-with-session startxfce4
XSTART
  chmod 700 "$HOME/.vnc/xstartup"
  touch "$MARKER"
  sudo apt-get clean
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

PIP_DISABLE_PIP_VERSION_CHECK=1 .venv/bin/python -m pip install --no-cache-dir --upgrade pip
PIP_DISABLE_PIP_VERSION_CHECK=1 .venv/bin/python -m pip install --no-cache-dir -e ".[dev]"

echo "HAZEWAVE_CODESPACE_BOOTSTRAP=PASS"
echo "BOOTSTRAP_VERSION=2"
echo "PIP_CACHE=PERSISTENT_DISABLED"
echo "PAID_FALLBACK=FALSE"
echo "UNKNOWN_COST_FALLBACK=FALSE"
