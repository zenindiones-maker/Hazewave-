#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

bash "$SCRIPT_DIR/install-xpra-stable.sh"
bash "$SCRIPT_DIR/install-reaper-pinned.sh"

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  lsp-plugins-lv2 \
  x42-plugins \
  dragonfly-reverb-lv2 \
  rubberband-cli \
  lilv-utils \
  libasound2-plugins \
  alsa-utils \
  iproute2

sudo apt-get clean

mkdir -p /tmp/hazewave-scratch /tmp/hazewave-cache
chmod 700 /tmp/hazewave-scratch /tmp/hazewave-cache

ASOUNDRC="${HOME}/.asoundrc"
ASOUNDRC_BACKUP="${HOME}/.asoundrc.pre-hazewave"
if [[ -f "$ASOUNDRC" && ! -f "$ASOUNDRC_BACKUP" ]]; then
  cp -p "$ASOUNDRC" "$ASOUNDRC_BACKUP"
fi

cat >"$ASOUNDRC" <<'ASOUND'
# Managed by Hazewave zero-cost workstation v3.
# Route ALSA clients such as REAPER through the Xpra PulseAudio server.
pcm.!default {
  type pulse
}
ctl.!default {
  type pulse
}
ASOUND
chmod 600 "$ASOUNDRC"

bash "$SCRIPT_DIR/start-professional-desktop.sh"
bash "$SCRIPT_DIR/professional-doctor.sh"

echo "HAZEWAVE_PRO_V3_UPGRADE=PASS"
echo "WORKSTATION_ROLE=HAZE_AUDIO_REAPER"
echo "REAPER_PRIMARY=TRUE"
echo "ARDOUR_FALLBACK=INSTALLED"
echo "REAPER_AUDIO_BRIDGE=ALSA_PULSE"
echo "PAID_FALLBACK=FALSE"
echo "UNKNOWN_COST_FALLBACK=FALSE"
