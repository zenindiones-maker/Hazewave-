#!/usr/bin/env bash
# Single supported WAVE site entrypoint. No cloud service, private media upload,
# A15 computation, domain-crossing operation, or publication is authorized.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
SITE="$ROOT/apps/hazewave-site"
MODE="${1:-serve}"
case "$MODE" in
  verify|serve) ;;
  --help|-h)
    printf 'Usage: bash scripts/run_hazewave_site.sh [serve|verify]\n'
    printf 'serve: clean install, build, Chromium E2E, local preview\n'
    printf 'verify: same checks, then exit successfully without serving\n'
    exit 0 ;;
  *) printf 'HAZEWAVE_SITE_BAD_MODE: %s\n' "$MODE" >&2; exit 64 ;;
esac

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo 'HAZEWAVE_SITE_NODE_NPM_MISSING: install Node.js 24+' >&2
  exit 69
fi
NODE_MAJOR="$(node -p "Number(process.versions.node.split('.')[0])")"
if (( NODE_MAJOR < 24 )); then
  echo "HAZEWAVE_SITE_NODE_VERSION_UNSUPPORTED: $NODE_MAJOR; requires 24+" >&2
  exit 69
fi
if ! command -v git >/dev/null 2>&1 || ! git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo 'HAZEWAVE_SITE_GIT_CHECKOUT_REQUIRED' >&2
  exit 69
fi
if [[ ! -f "$SITE/package-lock.json" ]]; then
  echo 'HAZEWAVE_SITE_COMMITTED_LOCKFILE_MISSING' >&2
  exit 66
fi

cd "$SITE"
printf 'HAZEWAVE_SITE_STAGE=SOURCE_ART_PROVENANCE\n'
node scripts/verify-owner-art.mjs
printf 'HAZEWAVE_SITE_STAGE=IMMUTABLE_INSTALL\n'
npm ci --ignore-scripts --no-audit --no-fund
git -C "$ROOT" diff --exit-code HEAD -- apps/hazewave-site/package-lock.json

printf 'HAZEWAVE_SITE_STAGE=SOURCE_AND_SCHEMA\n'
bash -n scripts/a15-runtime-proof.sh
node --check experiments/travessia-v4/travessia.js
npx tsc --noEmit
printf 'HAZEWAVE_SITE_STAGE=STATIC_BUILD\n'
npm run build
node scripts/verify-owner-art.mjs --dist
node scripts/check-bundle-budget.mjs

printf 'HAZEWAVE_SITE_STAGE=CHROMIUM_E2E\n'
if [[ "${GITHUB_ACTIONS:-false}" == "true" ]]; then
  npx playwright install --with-deps chromium
else
  npx playwright install chromium
fi
CI=true npm test -- --workers=1 --project=chromium-desktop --project=chromium-mobile
printf 'HAZEWAVE_SITE_E2E=PASS\n'

if [[ "$MODE" == "serve" ]]; then
  printf 'HAZEWAVE_SITE_PREVIEW=http://127.0.0.1:4321\n'
  exec npm run preview -- --host 127.0.0.1 --port 4321
fi
printf 'HAZEWAVE_SITE_VERIFY=PASS\n'
