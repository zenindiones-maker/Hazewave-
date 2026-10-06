#!/usr/bin/env bash
set -euo pipefail

BRANCH="work/creative-execution-plane-v1"
REPO_ROOT="/workspaces/Hazewave-"
STATE_ROOT="${HOME}/.local/state/hazewave-codespace/runtime-proof"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="$STATE_ROOT/$STAMP"
RECEIPT="$OUT_DIR/receipt.txt"
RECEIPT_SHA_FILE="$OUT_DIR/receipt.sha256"
EXPECTED_REAPER="${HOME}/.local/opt/reaper/7.82/REAPER/reaper"
EXPECTED_BLENDER="${HOME}/.local/opt/blender/5.2.2/blender"

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

  export HAZEWAVE_REAPER_BRIDGE_DIR="${HAZEWAVE_REAPER_BRIDGE_DIR:-${HOME}/.local/state/hazewave/reaper-bridge}"
  export PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

  CREATIVE_DOCTOR_JSON="$OUT_DIR/creative-producer-doctor.json"
  if ! python -m hazewave.creative_cli doctor >"$CREATIVE_DOCTOR_JSON"; then
    echo "REAPER_BRIDGE=FAIL_DOCTOR"
    echo "LIVE_REAPER_PROOF=FAIL_BRIDGE"
    exit 32
  fi
  grep -Fq '"schema": "CreativeProducerDoctor/v1"' "$CREATIVE_DOCTOR_JSON" || {
    echo "REAPER_BRIDGE=FAIL_DOCTOR_SCHEMA"
    echo "LIVE_REAPER_PROOF=FAIL_BRIDGE"
    exit 33
  }
  grep -Fq '"bridge_id": "HAZEWAVE_REAPER_BRIDGE"' "$CREATIVE_DOCTOR_JSON" || {
    echo "REAPER_BRIDGE=FAIL_BRIDGE_IDENTITY"
    echo "LIVE_REAPER_PROOF=FAIL_BRIDGE"
    exit 34
  }
  echo "REAPER_BRIDGE=PASS_RUNTIME_HEARTBEAT"

  SNAPSHOT_JSON="$OUT_DIR/reaper-project-snapshot.json"
  SNAPSHOT_REQUEST_ID="runtime-snapshot-$STAMP"
  if ! python -m hazewave.creative_cli snapshot       --task-id "runtime-proof-snapshot"       --request-id "$SNAPSHOT_REQUEST_ID"       --idempotency-key "$SNAPSHOT_REQUEST_ID" >"$SNAPSHOT_JSON"; then
    echo "REAPER_SNAPSHOT=FAIL_RUNTIME"
    echo "LIVE_REAPER_PROOF=FAIL_SNAPSHOT"
    exit 35
  fi
  grep -Fq '"schema": "ReaperProjectSnapshot/v1"' "$SNAPSHOT_JSON" || {
    echo "REAPER_SNAPSHOT=FAIL_SCHEMA"
    echo "LIVE_REAPER_PROOF=FAIL_SNAPSHOT"
    exit 36
  }
  echo "REAPER_SNAPSHOT=PASS_RUNTIME"

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

  TAPE_ECHO_DIR="${HOME}/.vst3/tape-echo-2.vst3"
  TAPE_ECHO_RECEIPT="${HOME}/.local/state/hazewave-codespace/tape-echo-2-1.0.8.receipt"
  [[ -d "$TAPE_ECHO_DIR" && -s "$TAPE_ECHO_RECEIPT" ]] || {
    echo "TAPE_ECHO_2_RUNTIME=FAIL_NOT_INSTALLED"
    exit 29
  }
  grep -Fxq 'TAPE_ECHO_2_VERSION=1.0.8' "$TAPE_ECHO_RECEIPT" || {
    echo "TAPE_ECHO_2_RUNTIME=FAIL_VERSION"
    exit 30
  }
  grep -Fxq 'ARCHIVE_SHA256=698c8825cac19547b40cd7a893d1b9bfac25587ec79cb30518f64084123b29f3' "$TAPE_ECHO_RECEIPT" || {
    echo "TAPE_ECHO_2_RUNTIME=FAIL_ARCHIVE_SHA"
    exit 31
  }
  echo "TAPE_ECHO_2_RUNTIME=PASS"
  echo "TAPE_ECHO_2_VERSION=1.0.8"

  VERTICAL_PROOF_LOG="$OUT_DIR/reaper-live-vertical-proof.txt"
  if ! bash scripts/codespaces/creative-execution-control.sh vertical-proof | tee "$VERTICAL_PROOF_LOG"; then
    echo "LIVE_REAPER_PROOF=FAIL_EXECUTION"
    exit 37
  fi

  grep -Fq '"schema": "ReaperLiveVerticalProof/v1"' "$VERTICAL_PROOF_LOG" || {
    echo "LIVE_REAPER_PROOF=FAIL_SCHEMA"
    exit 38
  }
  grep -Fq '"status": "PASS"' "$VERTICAL_PROOF_LOG" || {
    echo "LIVE_REAPER_PROOF=FAIL_STATUS"
    exit 39
  }
  grep -Fq 'fixture-close=RUNNER_VERIFIED' "$VERTICAL_PROOF_LOG" || {
    echo "LIVE_REAPER_PROOF=FAIL_FIXTURE_RESTORE"
    exit 40
  }
  grep -Fq 'LIVE_REAPER_PROOF=PASS' "$VERTICAL_PROOF_LOG" || {
    echo "LIVE_REAPER_PROOF=FAIL_PASS_MARKER"
    exit 41
  }
  grep -Fq 'HUMAN_APPROVAL=REQUIRED' "$VERTICAL_PROOF_LOG" || {
    echo "LIVE_REAPER_PROOF=FAIL_HUMAN_REVIEW_MARKER"
    exit 42
  }

  VERTICAL_PROOF_JSON="$(sed -n 's/^VERTICAL_PROOF_JSON=//p' "$VERTICAL_PROOF_LOG" | tail -n 1)"
  [[ -n "$VERTICAL_PROOF_JSON" && -s "$VERTICAL_PROOF_JSON" ]] || {
    echo "LIVE_REAPER_PROOF=FAIL_DURABLE_JSON"
    exit 43
  }

  HAZE_RENDER_B="$(python - "$VERTICAL_PROOF_JSON" "$HAZEWAVE_REAPER_BRIDGE_DIR/artifacts" <<'PY'
import json
from pathlib import Path
import sys

proof_path = Path(sys.argv[1]).expanduser().resolve()
artifact_root = Path(sys.argv[2]).expanduser().resolve()
payload = json.loads(proof_path.read_text(encoding="utf-8"))

if payload.get("schema") != "ReaperLiveVerticalProof/v1":
    raise SystemExit("LIVE_REAPER_PROOF=FAIL_DURABLE_SCHEMA")
if payload.get("status") != "PASS":
    raise SystemExit("LIVE_REAPER_PROOF=FAIL_DURABLE_STATUS")

render_b = payload.get("render_b")
if not isinstance(render_b, dict):
    raise SystemExit("LIVE_REAPER_PROOF=FAIL_RENDER_B")
artifact = Path(str(render_b.get("artifact_path") or "")).expanduser().resolve()
try:
    artifact.relative_to(artifact_root)
except ValueError as exc:
    raise SystemExit("LIVE_REAPER_PROOF=FAIL_RENDER_B_OUTSIDE_ROOT") from exc
if not artifact.is_file() or artifact.stat().st_size <= 0:
    raise SystemExit("LIVE_REAPER_PROOF=FAIL_RENDER_B_MISSING")
print(artifact)
PY
)"
  [[ -n "$HAZE_RENDER_B" && -s "$HAZE_RENDER_B" ]] || {
    echo "LIVE_REAPER_PROOF=FAIL_RENDER_B_ARTIFACT"
    exit 44
  }
  echo "VERTICAL_PROOF_JSON=$VERTICAL_PROOF_JSON"
  echo "HAZE_RENDER_B=$HAZE_RENDER_B"

  POLICY_DIGEST="$(sha256sum "$REPO_ROOT/config/project-profile-v2.json" | awk '{print $1}')"
  RUNTIME_IDENTITY="codespace:${CODESPACE_NAME:-$(hostname)}"
  WAVE_PROOF_ID="wave-$STAMP"
  WAVE_PROOF_ROOT="$OUT_DIR/wave-proofs"
  WAVE_LIVE_PROOF_JSON="$OUT_DIR/wave-live-proof.json"
  mkdir -p "$WAVE_PROOF_ROOT"
  chmod 700 "$WAVE_PROOF_ROOT"

  if ! python -m hazewave.wave_live_proof \
      --proof-root "$WAVE_PROOF_ROOT" \
      --proof-id "$WAVE_PROOF_ID" \
      --candidate-head "$ACTUAL_HEAD" \
      --policy-digest "$POLICY_DIGEST" \
      --runtime-identity "$RUNTIME_IDENTITY" \
      >"$WAVE_LIVE_PROOF_JSON"; then
    echo "LIVE_WAVE_PROOF=FAIL_EXECUTION"
    exit 45
  fi

  python - "$WAVE_LIVE_PROOF_JSON" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

path = Path(sys.argv[1]).expanduser().resolve()
payload = json.loads(path.read_text(encoding="utf-8"))

if payload.get("schema") != "WaveLiveProof/v1":
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_SCHEMA")
if payload.get("status") != "PASS":
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_STATUS")
if payload.get("authority") != "HAZEWAVE_HARNESS":
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_AUTHORITY")
if payload.get("portfolio_authority") != "NONE":
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_PORTFOLIO_AUTHORITY")

scene = payload.get("scene_detection")
if not isinstance(scene, dict) or scene.get("schema") != "SceneDetectionReport/v1":
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_SCENE_SCHEMA")
if int(scene.get("scene_count") or 0) < 2:
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_SCENE_COUNT")

otio = payload.get("otio")
if not isinstance(otio, dict) or otio.get("schema") != "OTIOInterchangeReceipt/v1":
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_OTIO_SCHEMA")
if otio.get("otio_version") != "0.18.1":
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_OTIO_VERSION")

render = payload.get("render")
if not isinstance(render, dict) or render.get("schema") != "WaveRenderReceipt/v1":
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_RENDER_SCHEMA")

video_qc = payload.get("video_qc")
if not isinstance(video_qc, dict) or video_qc.get("schema") != "VideoQCReport/v1":
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_VIDEO_QC_SCHEMA")
if video_qc.get("encode_integrity") != "PASS":
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_VIDEO_QC")

output_manifest = payload.get("output_manifest")
if not isinstance(output_manifest, dict) or output_manifest.get("schema") != "MediaManifest/v1":
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_OUTPUT_MANIFEST")

receipt_path = Path(str(payload.get("receipt_path") or "")).expanduser().resolve()
receipt_sha256 = str(payload.get("receipt_sha256") or "")
if not receipt_path.is_file() or receipt_path.stat().st_size <= 0:
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_DURABLE_RECEIPT")
actual_sha256 = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
if actual_sha256 != receipt_sha256:
    raise SystemExit("LIVE_WAVE_PROOF=FAIL_RECEIPT_HASH")
PY

  echo "WAVE_LIVE_PROOF_JSON=$WAVE_LIVE_PROOF_JSON"
  echo "LIVE_WAVE_PROOF=PASS"

  [[ -x "$EXPECTED_BLENDER" ]] || {
    echo "BLENDER_RUNTIME=FAIL_BINARY"
    exit 45
  }
  BLENDER_VERSION_LINE="$("$EXPECTED_BLENDER" --background --factory-startup --disable-autoexec --version 2>&1 | sed -n '1p')"
  [[ "$BLENDER_VERSION_LINE" == "Blender 5.2.2 LTS" ]] || {
    echo "BLENDER_RUNTIME=FAIL_VERSION"
    echo "ACTUAL=$BLENDER_VERSION_LINE"
    exit 46
  }
  echo "BLENDER_RUNTIME=PASS"
  echo "BLENDER_VERSION_PIN=5.2.2"

  CARTOON_PROOF_ID="cartoon-$STAMP"
  CARTOON_PROOF_ROOT="$OUT_DIR/cartoon-proofs"
  CARTOON_PROOF_JSON="$OUT_DIR/cartoon-live-proof.json"
  BLENDER_ROOT="${HOME}/.local/state/hazewave/blender"
  POLICY_DIGEST="$(sha256sum "$REPO_ROOT/config/project-profile-v2.json" | awk '{print $1}')"
  RUNTIME_IDENTITY="codespace:${CODESPACE_NAME:-$(hostname)}"
  mkdir -p "$CARTOON_PROOF_ROOT" "$BLENDER_ROOT"
  chmod 700 "$CARTOON_PROOF_ROOT" "$BLENDER_ROOT"

  if ! python -m hazewave.cartoon_live_proof \
      --blender-root "$BLENDER_ROOT" \
      --proof-root "$CARTOON_PROOF_ROOT" \
      --blender-binary "$EXPECTED_BLENDER" \
      --adapter-script "$REPO_ROOT/scripts/blender/hazewave_blender_adapter.py" \
      --haze-audio "$HAZE_RENDER_B" \
      --proof-id "$CARTOON_PROOF_ID" \
      --candidate-head "$ACTUAL_HEAD" \
      --policy-digest "$POLICY_DIGEST" \
      --runtime-identity "$RUNTIME_IDENTITY" \
      >"$CARTOON_PROOF_JSON"; then
    echo "CARTOON_LIVE_PROOF=FAIL_EXECUTION"
    exit 47
  fi

  python - "$CARTOON_PROOF_JSON" <<'PY'
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
if payload.get("schema") != "CartoonLiveProof/v1":
    raise SystemExit("CARTOON_LIVE_PROOF=FAIL_SCHEMA")
if payload.get("status") != "PASS":
    raise SystemExit("CARTOON_LIVE_PROOF=FAIL_STATUS")
if payload.get("final_video_mode") != "ANIMATED_CARTOON":
    raise SystemExit("CARTOON_LIVE_PROOF=FAIL_VIDEO_MODE")

animation_qc = payload.get("animation_qc")
if not isinstance(animation_qc, dict) or animation_qc.get("schema") != "AnimationQCReport/v1":
    raise SystemExit("CARTOON_LIVE_PROOF=FAIL_ANIMATION_QC_SCHEMA")
if animation_qc.get("technical_status") != "PASS":
    raise SystemExit("CARTOON_LIVE_PROOF=FAIL_ANIMATION_QC")

video_qc = payload.get("video_qc")
if not isinstance(video_qc, dict) or video_qc.get("schema") != "VideoQCReport/v1":
    raise SystemExit("CARTOON_LIVE_PROOF=FAIL_VIDEO_QC_SCHEMA")
if video_qc.get("encode_integrity") != "PASS":
    raise SystemExit("CARTOON_LIVE_PROOF=FAIL_VIDEO_QC")

repair = payload.get("repair")
if not isinstance(repair, dict) or repair.get("deterministic_match") is not True:
    raise SystemExit("CARTOON_LIVE_PROOF=FAIL_FRAME_REPAIR")
if payload.get("human_owner_review") != "REQUIRED":
    raise SystemExit("CARTOON_LIVE_PROOF=FAIL_HUMAN_REVIEW_MARKER")

final_video = payload.get("final_video")
if not isinstance(final_video, dict):
    raise SystemExit("CARTOON_LIVE_PROOF=FAIL_FINAL_VIDEO")
video_path = Path(str(final_video.get("path") or ""))
if not video_path.is_file() or video_path.stat().st_size <= 0:
    raise SystemExit("CARTOON_LIVE_PROOF=FAIL_FINAL_VIDEO_ARTIFACT")
PY

  echo "CARTOON_PROOF_JSON=$CARTOON_PROOF_JSON"
  echo "CARTOON_LIVE_PROOF=PASS"
  echo "ANIMATION_QC=PASS"
  echo "VIDEO_QC=PASS"
  echo "HUMAN_OWNER_REVIEW=REQUIRED"

  echo "LIVE_REAPER_PROOF=PASS"
  echo "REAPER_GUI_PROCESS=PASS"
  echo "REAPER_MINIMAL_PROJECT=PASS_LIVE_FIXTURE"
  echo "REAPER_PLUGIN_LOAD=PASS_LIVE_TAPE_ECHO_2"
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
