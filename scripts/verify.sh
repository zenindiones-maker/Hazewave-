#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE="$ROOT/apps/hazewave-site"
mkdir -p "$ROOT/verification/screenshots"
exec > >(tee "$ROOT/verification/verify.log") 2>&1
test -e "$ROOT/.git"
COUNT="$(find "$ROOT" -name .git | wc -l)"
echo "HAZEWAVE_DOT_GIT_COUNT=$COUNT"
test "$COUNT" -eq 1
cd "$SITE"
# All clean-up strictly scoped to the existing single Astro package.
# Never touch the Reflex worktree, Codespace services or another repository.
rm -rf -- node_modules .next dist
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
# Prove the NEW Site 01 directly before the noisy legacy performance audit.
# This command builds and tests the seven-act ink route, then restores the
# approved production dist. It does not publish the experimental candidate.
bash "$ROOT/scripts/run_hazewave_site.sh" verify
curl -fsSI http://127.0.0.1:3000/
export CHROME_PATH
CHROME_PATH="$(node --input-type=module -e 'import {chromium} from "@playwright/test"; console.log(chromium.executablePath())')"
# Chrome's own documentation warns that one free CI result can fluctuate.
# Collect independent, SEQUENTIAL runs; enforce the unchanged >90 boundary
# on the median. Publish ALL raw readings, not only the best sample.
for n in 1 2 3; do
  npx --yes lighthouse@12.8.2 http://127.0.0.1:3000/ --only-categories=performance --chrome-flags="--headless --no-sandbox" --output=json --output-path="$ROOT/verification/lighthouse-mobile-$n.json" --quiet
done
node -e 'const fs=require("node:fs"),d=process.argv[1];const runs=[1,2,3].map(i=>({i,p:d+"/lighthouse-mobile-"+i+".json",v:JSON.parse(fs.readFileSync(d+"/lighthouse-mobile-"+i+".json","utf8"))}));for(const r of runs){r.s=Math.round(r.v.categories.performance.score*100)}runs.sort((a,b)=>a.s-b.s);const median=runs[1];fs.copyFileSync(median.p,d+"/lighthouse-mobile.json");const s=median.s;console.log("HAZEWAVE_LIGHTHOUSE_TRIPLE="+runs.map(r=>r.s).join(","));console.log("HAZEWAVE_LIGHTHOUSE_MEDIAN="+s);console.log("HAZEWAVE_LIGHTHOUSE="+s);if(s<=90)process.exit(1)' "$ROOT/verification"
npx astro preview stop
echo "HAZEWAVE_VERIFY=PASS"
