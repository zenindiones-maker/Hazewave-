#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE_DIR="${HOME}/.cache"
LOG="${CACHE_DIR}/hazewave-site-a15-preview.log"
PIDFILE="${CACHE_DIR}/hazewave-site-a15-preview.pid"
PORTFILE="${CACHE_DIR}/hazewave-site-a15-preview.port"
PORT="${HAZEWAVE_SITE_PORT:-4321}"

cd "$APP_DIR"
mkdir -p "$CACHE_DIR"

echo "=== HAZEWAVE / WAVE A15 RUNTIME PROOF ==="
echo "APP_DIR=$APP_DIR"
echo "NODE=$(node --version)"
echo "NPM=$(npm --version)"
echo "PLATFORM=$(node -p 'process.platform')"
echo "ARCH=$(node -p 'process.arch')"

# Bootstrap dependencies deterministically for this isolated worktree.
if [ ! -f package-lock.json ]; then
  npm install --package-lock-only --ignore-scripts --no-audit --no-fund
fi
npm ci --ignore-scripts --no-audit --no-fund

# Astro 7 uses Satteri. Current Satteri loaders recognize Android, but
# upstream does not publish an @bruits/satteri-android-arm64 package.
# Satteri itself provides a WASI fallback via NAPI_RS_FORCE_WASI.
if [ "$(node -p 'process.platform')" = "android" ]; then
  SATTERI_VERSION="$(node -p "require('./node_modules/satteri/package.json').version")"
  echo "SATTERI_VERSION=$SATTERI_VERSION"
  echo "SATTERI_ANDROID_NATIVE=UNAVAILABLE_UPSTREAM"
  echo "SATTERI_WASI_FALLBACK=INSTALLING"
  npm install     --no-save     --package-lock=false     --ignore-scripts     --no-audit     --no-fund     --force     "@bruits/satteri-wasm32-wasi@$SATTERI_VERSION"
  export NAPI_RS_FORCE_WASI=true
  echo "SATTERI_WASI_FALLBACK=ENABLED"
fi

echo "=== STATIC BUILD ==="
npm run build
test -f dist/index.html
echo "A15_STATIC_BUILD=PASS"

# Never kill unrelated processes. Find the first free port.
while ss -ltn 2>/dev/null | grep -q ":${PORT} "; do
  PORT=$((PORT + 1))
  if [ "$PORT" -gt 4340 ]; then
    echo "ERROR=NO_FREE_PREVIEW_PORT"
    exit 1
  fi
done

# Serve the already-built static site with Python. Do not use astro preview
# on Android because that needlessly loads the build-time native toolchain.
nohup python -m http.server "$PORT"   --bind 127.0.0.1   --directory "$APP_DIR/dist"   >"$LOG" 2>&1 &

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
