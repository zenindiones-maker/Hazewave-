#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-/tmp/hazewave-audio-smoke}"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/input.wav "$OUT_DIR"/stretched.wav "$OUT_DIR"/render.flac "$OUT_DIR"/probe.json

for cmd in sox rubberband ffmpeg ffprobe python3; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "HAZEWAVE_AUDIO_SMOKE=BLOCKED_MISSING_$cmd"
    exit 20
  }
done

START_MS="$(date +%s%3N)"

sox -n   -r 48000   -c 2   -b 24   "$OUT_DIR/input.wav"   synth 1 sine 440   vol 0.10

rubberband   -t 1.05   "$OUT_DIR/input.wav"   "$OUT_DIR/stretched.wav"   >/dev/null 2>&1

ffmpeg -hide_banner -loglevel error   -threads 2   -i "$OUT_DIR/stretched.wav"   -c:a flac   -compression_level 5   -y "$OUT_DIR/render.flac"

ffprobe -v error   -show_entries stream=codec_type,codec_name,sample_rate,channels   -of json   "$OUT_DIR/render.flac"   >"$OUT_DIR/probe.json"

python3 - "$OUT_DIR/probe.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)

audio = next(s for s in data["streams"] if s["codec_type"] == "audio")
assert audio["codec_name"] == "flac", audio
assert audio["sample_rate"] == "48000", audio
assert audio["channels"] == 2, audio
PY

END_MS="$(date +%s%3N)"
ELAPSED_MS="$((END_MS - START_MS))"
SIZE_BYTES="$(stat -c '%s' "$OUT_DIR/render.flac")"
SHA256="$(sha256sum "$OUT_DIR/render.flac" | awk '{print $1}')"

echo "HAZEWAVE_AUDIO_TOOLCHAIN_SMOKE=PASS"
echo "AUDIO_SAMPLE_RATE=48000"
echo "AUDIO_CHANNELS=2"
echo "AUDIO_SOURCE_BIT_DEPTH=24"
echo "RUBBERBAND_PROCESSING=PASS"
echo "FLAC_RENDER=PASS"
echo "RENDER_SIZE_BYTES=$SIZE_BYTES"
echo "RENDER_SHA256=$SHA256"
echo "SMOKE_ELAPSED_MS=$ELAPSED_MS"
echo "FFMPEG_THREADS=2"
