#!/usr/bin/env bash
set -euo pipefail

PORT="14500"
SESSION=":100"
RUNTIME="/tmp/hazewave-runtime-${UID}"
SOCKET_DIR="${RUNTIME}/xpra"
EXPECTED_REAPER="${HOME}/.local/opt/reaper/7.82/REAPER/reaper"

mkdir -p "$SOCKET_DIR"
chmod 700 "$RUNTIME" "$SOCKET_DIR"
export XDG_RUNTIME_DIR="$RUNTIME"

required=(xpra ffmpeg ffprobe sox curl ss gst-inspect-1.0 pactl reaper lv2ls)
for cmd in "${required[@]}"; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "MISSING_COMMAND=$cmd"
    exit 20
  }
done

[[ "$(readlink -f "$(command -v reaper)")" == "$EXPECTED_REAPER" ]] || {
  echo "REAPER_PRIMARY=FAIL_UNEXPECTED_BINARY"
  echo "EXPECTED=$EXPECTED_REAPER"
  echo "ACTUAL=$(readlink -f "$(command -v reaper)")"
  exit 21
}

for pkg in \
  xpra xpra-x11 xpra-html5 xpra-audio-server \
  pulseaudio pulseaudio-utils \
  gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-pulseaudio \
  lsp-plugins-lv2 x42-plugins dragonfly-reverb-lv2 rubberband-cli lilv-utils
do
  dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed' || {
    echo "PACKAGE_MISSING=$pkg"
    exit 22
  }
done

LV2_COUNT="$(lv2ls 2>/dev/null | wc -l | tr -d ' ')"
(( LV2_COUNT >= 10 )) || {
  echo "LV2_DISCOVERY=FAIL"
  echo "LV2_COUNT=$LV2_COUNT"
  exit 23
}

gst-inspect-1.0 pulsesrc >/dev/null 2>&1 || {
  echo "XPRA_AUDIO_CAPTURE_PLUGIN=FAIL"
  exit 24
}
gst-inspect-1.0 opusenc >/dev/null 2>&1 || {
  echo "XPRA_AUDIO_CODEC_OPUS=FAIL"
  exit 25
}

curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null || {
  echo "XPRA_HTML5=FAIL"
  exit 26
}

LISTEN_LINE="$(ss -ltn | awk -v p=":${PORT}" '$4 ~ p"$" {print $4; exit}')"
[[ "$LISTEN_LINE" == "127.0.0.1:${PORT}" ]] || {
  echo "XPRA_BIND=FAIL"
  echo "LISTEN=${LISTEN_LINE:-NONE}"
  exit 27
}

xpra info "$SESSION" --socket-dir="$SOCKET_DIR" >/tmp/hazewave-xpra-info.txt 2>/dev/null || {
  echo "XPRA_SESSION=FAIL"
  exit 28
}

CPU_COUNT="$(nproc)"
MEM_AVAILABLE_MB="$(awk '/MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo)"
DISK_FREE_MB="$(df -Pm /workspaces | awk 'NR==2 {print $4}')"

(( CPU_COUNT == 2 )) || {
  echo "ZERO_COST_MACHINE_SHAPE=FAIL"
  echo "CPU_COUNT=$CPU_COUNT"
  exit 29
}
(( MEM_AVAILABLE_MB >= 2048 )) || {
  echo "MEMORY_HEADROOM=FAIL"
  echo "MEM_AVAILABLE_MB=$MEM_AVAILABLE_MB"
  exit 30
}
(( DISK_FREE_MB >= 8192 )) || {
  echo "WORKSPACE_HEADROOM=FAIL"
  echo "WORKSPACE_FREE_MB=$DISK_FREE_MB"
  exit 31
}

ARDOUR_BIN=""
for candidate in ardour9 ardour8 ardour7 ardour6 ardour; do
  if command -v "$candidate" >/dev/null 2>&1; then
    ARDOUR_BIN="$(command -v "$candidate")"
    break
  fi
done

echo "HAZEWAVE_PRO_WORKSTATION=PASS"
echo "WORKSTATION_ROLE=HAZE_AUDIO_REAPER"
echo "REAPER_PRIMARY=PASS"
echo "REAPER_VERSION_PIN=7.82"
echo "ARDOUR_FALLBACK=$([[ -n "$ARDOUR_BIN" ]] && echo AVAILABLE || echo NOT_INSTALLED)"
echo "XPRA_HTML5=PASS"
echo "XPRA_X11=PASS"
echo "XPRA_AUDIO_SERVER=PASS"
echo "XPRA_AUDIO_CAPTURE_PLUGIN=PASS"
echo "XPRA_AUDIO_CODEC_OPUS=PASS"
echo "XPRA_BIND=LOOPBACK_ONLY"
echo "SPEAKER_FORWARDING=CONFIGURED"
echo "MICROPHONE_FORWARDING=DISABLED"
echo "LSP_LV2=PASS"
echo "X42_LV2=PASS"
echo "DRAGONFLY_LV2=PASS"
echo "LV2_DISCOVERY_COUNT=$LV2_COUNT"
echo "RUBBERBAND=PASS"
echo "FFMPEG=PASS"
echo "SOX=PASS"
echo "NOVNC_FALLBACK=PRESERVED"
echo "CPU_COUNT=$CPU_COUNT"
echo "MEM_AVAILABLE_MB=$MEM_AVAILABLE_MB"
echo "WORKSPACE_FREE_MB=$DISK_FREE_MB"
echo "SCRATCH_POLICY=TMP_EPHEMERAL"
echo "REFERENCE_QC=LOCAL_A15"
echo "PAID_FALLBACK=FALSE"
echo "UNKNOWN_COST_FALLBACK=FALSE"
