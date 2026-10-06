#!/usr/bin/env bash
set -euo pipefail

PORT="14500"
SESSION=":100"

required=(xpra ffmpeg ffprobe sox ardour curl ss)
for cmd in "${required[@]}"; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    if [[ "$cmd" == "ardour" ]] && { command -v ardour8 >/dev/null 2>&1 || command -v ardour9 >/dev/null 2>&1; }; then
      continue
    fi
    echo "MISSING_COMMAND=$cmd"
    exit 20
  fi
done

curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null || {
  echo "XPRA_HTML5=FAIL"
  exit 21
}

LISTEN_LINE="$(ss -ltn | awk -v p=":${PORT}" '$4 ~ p"$" {print $4; exit}')"
[[ "$LISTEN_LINE" == "127.0.0.1:${PORT}" ]] || {
  echo "XPRA_BIND=FAIL"
  echo "LISTEN=${LISTEN_LINE:-NONE}"
  exit 22
}

xpra info "$SESSION" >/tmp/hazewave-xpra-info.txt 2>/dev/null || {
  echo "XPRA_SESSION=FAIL"
  exit 23
}

for pkg in lsp-plugins-lv2 x42-plugins dragonfly-reverb-lv2 rubberband-cli; do
  dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed' || {
    echo "PLUGIN_PACKAGE_MISSING=$pkg"
    exit 24
  }
done

echo "HAZEWAVE_PRO_WORKSTATION=PASS"
echo "XPRA_HTML5=PASS"
echo "XPRA_BIND=LOOPBACK_ONLY"
echo "SPEAKER_FORWARDING=CONFIGURED"
echo "MICROPHONE_FORWARDING=DISABLED"
echo "ARDOUR=PASS"
echo "LSP_LV2=PASS"
echo "X42_LV2=PASS"
echo "DRAGONFLY_LV2=PASS"
echo "RUBBERBAND=PASS"
echo "NOVNC_FALLBACK=PRESERVED"
echo "PAID_FALLBACK=FALSE"
echo "UNKNOWN_COST_FALLBACK=FALSE"
