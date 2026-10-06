#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

bash "$SCRIPT_DIR/install-xpra-stable.sh"

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends   lsp-plugins-lv2   x42-plugins   dragonfly-reverb-lv2   rubberband-cli   iproute2

sudo apt-get clean

mkdir -p /tmp/hazewave-scratch /tmp/hazewave-cache
chmod 700 /tmp/hazewave-scratch /tmp/hazewave-cache

bash "$SCRIPT_DIR/start-professional-desktop.sh"
bash "$SCRIPT_DIR/professional-doctor.sh"

echo "HAZEWAVE_PRO_V2_UPGRADE=PASS"
echo "PAID_FALLBACK=FALSE"
echo "UNKNOWN_COST_FALLBACK=FALSE"
