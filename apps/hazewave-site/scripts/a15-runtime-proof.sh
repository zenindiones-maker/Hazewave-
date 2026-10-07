#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE_DIR="${HOME}/.cache"
DIST_DIR="${APP_DIR}/dist-a15"
LOG="${CACHE_DIR}/hazewave-site-a15-preview.log"
PIDFILE="${CACHE_DIR}/hazewave-site-a15-preview.pid"
PORTFILE="${CACHE_DIR}/hazewave-site-a15-preview.port"
PORT="${HAZEWAVE_SITE_PORT:-4321}"
REPO="zenindiones-maker/Hazewave-"
WORKFLOW="WAVE Site CI"
BRANCH="work/wave-hazewave-site-v1"
ARTIFACT="hazewave-site-static-dist"
EXPECTED_HEAD="$(git -C "$APP_DIR" rev-parse HEAD)"

cd "$APP_DIR"
mkdir -p "$CACHE_DIR"

echo "=== HAZEWAVE / WAVE A15 RUNTIME PROOF ==="
echo "APP_DIR=$APP_DIR"
echo "NODE=$(node --version 2>/dev/null || echo unavailable)"
echo "PLATFORM=$(node -p 'process.platform' 2>/dev/null || echo unknown)"
echo "ARCH=$(node -p 'process.arch' 2>/dev/null || echo unknown)"
echo "EXPECTED_HEAD=$EXPECTED_HEAD"

# Android/Termux is a runtime target, not the canonical Astro build host.
# Astro 7 -> Satteri currently has no published Android arm64 native binding,
# and the WASI fallback can fail under Node/Termux uvwasi initialization.
# Therefore the A15 consumes the exact static dist already built and validated
# by WAVE Site CI on the supported Linux build host.
if [ "$(node -p 'process.platform' 2>/dev/null || true)" = "android" ]; then
  echo "A15_BUILD_MODE=CI_PREBUILT_STATIC_DIST"

  if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR=GH_CLI_REQUIRED"
    echo "FIX=pkg install gh -y"
    exit 1
  fi

  if ! gh auth status --hostname github.com >/dev/null 2>&1; then
    echo "ERROR=GH_AUTH_REQUIRED"
    echo "FIX=gh auth login --hostname github.com --web"
    exit 1
  fi

  RUN_ID="$(
    gh run list       --repo "$REPO"       --workflow "$WORKFLOW"       --branch "$BRANCH"       --status success       --limit 50       --json databaseId,headSha,conclusion       --jq "map(select(.headSha == \"$EXPECTED_HEAD\"))[0].databaseId // empty"
  )"

  if [ -z "$RUN_ID" ]; then
    echo "ERROR=NO_SUCCESSFUL_SITE_CI_FOR_EXACT_HEAD"
    echo "EXPECTED_HEAD=$EXPECTED_HEAD"
    echo "ACTION=WAIT_FOR_EXACT_HEAD_CI_THEN_RETRY"
    exit 1
  fi

  rm -rf "$DIST_DIR"
  mkdir -p "$DIST_DIR"

  echo "CI_RUN_ID=$RUN_ID"
  echo "CI_HEAD=$EXPECTED_HEAD"
  echo "CI_ARTIFACT=$ARTIFACT"

  gh run download "$RUN_ID"     --repo "$REPO"     --name "$ARTIFACT"     --dir "$DIST_DIR"

  test -f "$DIST_DIR/index.html"
  test -d "$DIST_DIR/_astro"
  echo "A15_STATIC_DIST=PASS"
else
  echo "A15_BUILD_MODE=LOCAL_NON_ANDROID"
  rm -rf "$DIST_DIR"
  npm ci --ignore-scripts --no-audit --no-fund
  npm run build
  cp -a dist "$DIST_DIR"
  test -f "$DIST_DIR/index.html"
  echo "A15_STATIC_DIST=PASS"
fi

# Never kill unrelated processes. Pick a free localhost port.
while ss -ltn 2>/dev/null | grep -q ":${PORT} "; do
  PORT=$((PORT + 1))
  if [ "$PORT" -gt 4340 ]; then
    echo "ERROR=NO_FREE_PREVIEW_PORT"
    exit 1
  fi
done

nohup python -m http.server "$PORT"   --bind 127.0.0.1   --directory "$DIST_DIR"   >"$LOG" 2>&1 &

PID=$!
echo "$PID" > "$PIDFILE"
echo "$PORT" > "$PORTFILE"

READY=0
for _ in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" != "1" ]; then
  echo "ERROR=A15_LOCAL_PREVIEW_NOT_READY"
  tail -n 120 "$LOG" || true
  exit 1
fi

URL="http://127.0.0.1:$PORT/?diagnostics=1"
echo "A15_LOCAL_PREVIEW=PASS"
echo "PID=$PID"
echo "PORT=$PORT"
echo "URL=$URL"

if command -v termux-open-url >/dev/null 2>&1; then
  termux-open-url "$URL" || true
elif command -v /system/bin/am >/dev/null 2>&1; then
  /system/bin/am start -a android.intent.action.VIEW -d "$URL" >/dev/null 2>&1 || true
fi
