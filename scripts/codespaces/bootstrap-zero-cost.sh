#!/usr/bin/env bash
set -euo pipefail

STATE_ROOT="${HOME}/.local/state/hazewave-codespace"
MARKER="${STATE_ROOT}/bootstrap-v1"
mkdir -p "${STATE_ROOT}"

if [[ "${CODESPACES:-}" != "true" ]]; then
  echo "HAZEWAVE_CODESPACE=BLOCKED_NOT_CODESPACES"
  exit 20
fi

if [[ ! -f "${MARKER}" ]]; then
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ardour \
    ffmpeg \
    sox \
    libsox-fmt-all \
    xfce4 \
    xfce4-terminal \
    tigervnc-standalone-server \
    novnc \
    websockify \
    python3-venv \
    jq \
    dbus-x11 \
    ca-certificates

  mkdir -p "${HOME}/.vnc"
  cat > "${HOME}/.vnc/xstartup" <<'XSTART'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec dbus-launch --exit-with-session startxfce4
XSTART
  chmod 700 "${HOME}/.vnc/xstartup"
  touch "${MARKER}"
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"

echo "HAZEWAVE_CODESPACE_BOOTSTRAP=PASS"
echo "PAID_FALLBACK=FALSE"
echo "UNKNOWN_COST_FALLBACK=FALSE"
