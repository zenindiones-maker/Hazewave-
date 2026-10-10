#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE="$ROOT/apps/hazewave-site"
mkdir -p "$ROOT/verification/screenshots"
test -e "$ROOT/.git"
COUNT="$(find "$ROOT" -name .git | wc -l)"
echo "HAZEWAVE_DOT_GIT_COUNT=$COUNT"
test "$COUNT" -eq 1
cd "$SITE"
npm ci --ignore-scripts --no-audit --no-fund
if grep -RniE 'TODO|MOCK|placeholder|lorem ipsum' src; then
 echo "HAZEWAVE_INCOMPLETE_SOURCE=FAIL"
 exit 1
fi
npm run build
npm run start &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' EXIT
sleep 3
curl -fsSI http://127.0.0.1:3000/
npx playwright install chromium
node scripts/verify-brand-screenshots.mjs
export CHROME_PATH
CHROME_PATH="$(node --input-type=module -e 'import {chromium} from "@playwright/test"; console.log(chromium.executablePath())')"
npx --yes lighthouse@12.8.2 http://127.0.0.1:3000/ --only-categories=performance --chrome-flags="--headless --no-sandbox" --output=json --output-path="$ROOT/verification/lighthouse-mobile.json" --quiet
node -e 'const r=require(process.argv[1]); const s=Math.round(r.categories.performance.score*100); console.log("HAZEWAVE_LIGHTHOUSE="+s); if(s<=90)process.exit(1)' "$ROOT/verification/lighthouse-mobile.json"
bash "$ROOT/scripts/run_hazewave_site.sh" verify
echo "HAZEWAVE_VERIFY=PASS"
