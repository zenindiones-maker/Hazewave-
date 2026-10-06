#!/usr/bin/env bash
set -euo pipefail

cd /workspaces/Hazewave-

bash scripts/codespaces/install-xpra-stable.sh

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  lsp-plugins-lv2 \
  x42-plugins \
  dragonfly-reverb-lv2 \
  rubberband-cli \
  iproute2

mkdir -p /tmp/hazewave-scratch /tmp/hazewave-cache

bash scripts/codespaces/start-professional-desktop.sh
bash scripts/codespaces/professional-doctor.sh

echo "HAZEWAVE_PRO_V2_UPGRADE=PASS"
