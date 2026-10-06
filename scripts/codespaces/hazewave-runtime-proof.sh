#!/usr/bin/env bash
set -euo pipefail

BRANCH="work/zero-cost-workstation-v3"
REPO_ROOT="/workspaces/Hazewave-"
STATE_ROOT="${HOME}/.local/state/hazewave-codespace/runtime-proof"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="$STATE_ROOT/$STAMP"
RECEIPT="$OUT_DIR/receipt.txt"
RECEIPT_SHA_FILE="$OUT_DIR/receipt.sha256"
EXPECTED_REAPER="${HOME}/.local/opt/reaper/7.82/REAPER/reaper"

mkdir -p "$OUT_DIR"

run_proof() {
  echo "PROJECT=HAZEWAVE"
  echo "WORKSTATION_ROLE=HAZE_AUDIO_REAPER"
  echo "PROOF_STARTED_UTC=$STAMP"

  [[ "${CODESPACES:-}" == "true" ]] || {
    echo "RUNTIME_INSIDE_CODESPACE=BLOCKED_NOT_CODESPACES"
    exit 20
  }

  cd "$REPO_ROOT"

  ACTUAL_BRANCH="$(git branch --show-current)"
  ACTUAL_HEAD="$(git rev-parse HEAD)"
  REMOTE_HEAD="$(git rev-parse "origin/$BRANCH")"

  echo "BRANCH=$ACTUAL_BRANCH"
  echo "HEAD=$ACTUAL_HEAD"
  echo "REMOTE_HEAD=$REMOTE_HEAD"

  [[ "$ACTUAL_BRANCH" == "$BRANCH" ]] || {
    echo "BRANCH_PROOF=FAIL"
    exit 21
  }
  [[ "$ACTUAL_HEAD" == "$REMOTE_HEAD" ]] || {
    echo "HEAD_EXACT_REMOTE=FAIL"
    exit 22
  }

  CPU_COUNT="$(nproc)"
  MEM_AVAILABLE_MB="$(awk '/MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo)"
  DISK_FREE_MB="$(df -Pm /workspaces | awk 'NR==2 {print $4}')"

  echo "CPU_COUNT=$CPU_COUNT"
  echo "MEM_AVAILABLE_MB=$MEM_AVAILABLE_MB"
  echo "WORKSPACE_FREE_MB=$DISK_FREE_MB"

  [[ "$CPU_COUNT" == "2" ]] || {
    echo "MACHINE_SHAPE_RUNTIME=FAIL"
    exit 23
  }

  START_NS="$(date +%s%N)"
  bash scripts/codespaces/start-professional-desktop.sh
  START_END_NS="$(date +%s%N)"
  echo "XPRA_STARTUP_MS=$(((START_END_NS - START_NS) / 1000000))"

  bash scripts/codespaces/professional-doctor.sh

  [[ -x "$EXPECTED_REAPER" ]] || {
    echo "REAPER_RUNTIME=FAIL_BINARY"
    exit 24
  }

  echo "REAPER_BINARY=$EXPECTED_REAPER"
  echo "REAPER_BINARY_SHA256=$(sha256sum "$EXPECTED_REAPER" | awk '{print $1}')"
  echo "REAPER_VERSION_PIN=7.82"

  for _ in $(seq 1 30); do
    pgrep -f "$EXPECTED_REAPER" >/dev/null 2>&1 && break
    sleep 1
  done

  pgrep -f "$EXPECTED_REAPER" >/dev/null 2>&1 || {
    echo "REAPER_PROCESS=FAIL"
    exit 25
  }
  echo "REAPER_PROCESS=PASS"

  pactl info >"$OUT_DIR/pactl-info.txt"
  pactl list short sinks >"$OUT_DIR/pulse-sinks.txt"
  test -s "$OUT_DIR/pulse-sinks.txt" || {
    echo "PULSEAUDIO_SINK=FAIL"
    exit 26
  }
  echo "PULSEAUDIO_SINK=PASS"

  aplay -L >"$OUT_DIR/aplay-devices.txt"
  grep -qx 'pulse' "$OUT_DIR/aplay-devices.txt" || {
    echo "ALSA_PULSE_BRIDGE=FAIL"
    exit 27
  }
  echo "ALSA_PULSE_BRIDGE=PASS"

  AUDIO_TEST="$OUT_DIR/playback.wav"
  sox -n -r 48000 -c 2 -b 16 "$AUDIO_TEST" synth 0.5 sine 880 vol 0.03
  timeout 10 aplay -q "$AUDIO_TEST"
  echo "SERVER_SIDE_AUDIO_PLAYBACK=PASS"

  bash scripts/codespaces/hazewave-audio-smoke.sh "$OUT_DIR/audio-smoke"

  xpra info :100 --socket-dir="/tmp/hazewave-runtime-${UID}/xpra"     >"$OUT_DIR/xpra-info.txt"
  grep -Ei 'audio|speaker|sound' "$OUT_DIR/xpra-info.txt"     >"$OUT_DIR/xpra-audio-info.txt" || true

  LV2_COUNT="$(lv2ls 2>/dev/null | wc -l | tr -d ' ')"
  echo "LV2_PLUGIN_COUNT=$LV2_COUNT"
  (( LV2_COUNT >= 10 )) || {
    echo "LV2_DISCOVERY=FAIL"
    exit 28
  }
  echo "LV2_DISCOVERY=PASS"

  dpkg-query -W -f='LSP_PACKAGE=${Status}\n' lsp-plugins-lv2
  dpkg-query -W -f='X42_PACKAGE=${Status}\n' x42-plugins
  dpkg-query -W -f='DRAGONFLY_PACKAGE=${Status}\n' dragonfly-reverb-lv2
  echo "RUBBERBAND_VERSION=$(rubberband --version 2>&1 | sed -n '1p')"

  echo "REAPER_GUI_PROCESS=PASS"
  echo "REAPER_MINIMAL_PROJECT=AWAITING_HUMAN_UI_PROOF"
  echo "REAPER_PLUGIN_LOAD=AWAITING_HUMAN_UI_PROOF"
  echo "BROWSER_END_TO_END_AUDIO=AWAITING_HUMAN_LISTENING_PROOF"
  echo "XPRA_REQUIRED=TRUE"
  echo "PAID_FALLBACK=FALSE"
  echo "UNKNOWN_COST_FALLBACK=FALSE"
  echo "RUNTIME_INSIDE_CODESPACE=PASS_AUTOMATED_BOUNDARY"
  echo "PROOF_COMPLETED_UTC=$(date -u +%Y%m%dT%H%M%SZ)"
}

run_proof | tee "$RECEIPT"

RECEIPT_SHA256="$(sha256sum "$RECEIPT" | awk '{print $1}')"
printf '%s  %s\n' "$RECEIPT_SHA256" "receipt.txt" >"$RECEIPT_SHA_FILE"

echo "RECEIPT=$RECEIPT"
echo "RECEIPT_SHA_FILE=$RECEIPT_SHA_FILE"
echo "RECEIPT_SHA256=$RECEIPT_SHA256"
