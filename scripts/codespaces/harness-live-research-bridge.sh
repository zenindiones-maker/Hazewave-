#!/usr/bin/env bash
# First-party Harness REA+Iris real execution bridge for existing Codespace.
# Opt-in, separate from stock Reflex/REAPER and global agent MCP settings.
set -euo pipefail

fail() {
  printf 'HAZEWAVE_RESEARCH_BRIDGE=BLOCKED:%s\n' "$1" >&2
  exit 20
}

[[ "$#" -eq 1 ]] || fail "MODE_REQUIRED"
mode="$1"
case "$mode" in --preflight|--prove|--mcp) ;; *) fail "MODE_UNSUPPORTED" ;; esac
[[ "${CODESPACE_NAME:-}" == "hazewave-zero-cost-4jxp45676rq6279xx" ]] || fail "CODESPACE_ID_MISMATCH"

DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$DIR/../.." && pwd -P)"
REA="$HOME/.local/share/hazewave/reverse-engineering/rea-6.0.0/bin/rea"
IRIS="$HOME/.local/share/hazewave/iris/v0.4.1/bin/iris"
STATE="$HOME/.local/state/hazewave"
EXPECTED="${HAZEWAVE_RESEARCH_EXPECTED_SHA:-}"
[[ "$EXPECTED" =~ ^[0-9a-f]{40}$ ]] || fail "REVIEWED_SHA_REQUIRED"
[[ "$(git -C "$ROOT" rev-parse HEAD 2>/dev/null)" == "$EXPECTED" ]] || fail "HEAD_MISMATCH"
[[ -z "$(git -C "$ROOT" status --porcelain)" ]] || fail "WORKTREE_DIRTY"
remote="$(git -C "$ROOT" remote get-url origin)" || fail "REMOTE_UNKNOWN"
case "$remote" in
  https://github.com/zenindiones-maker/Hazewave-|https://github.com/zenindiones-maker/Hazewave-.git|git@github.com:zenindiones-maker/Hazewave-|git@github.com:zenindiones-maker/Hazewave-.git) ;;
  *) fail "REMOTE_REPOSITORY_MISMATCH" ;;
esac
head_remote="$(git -C "$ROOT" ls-remote --exit-code origin refs/heads/work/harness-live-research-execution-v1 | awk 'NR==1 {print $1}')" || fail "REMOTE_HEAD_UNKNOWN"
[[ "$head_remote" == "$EXPECTED" ]] || fail "REMOTE_REF_MOVED"

[[ -f "$ROOT/tests/fixtures/rea6-javascript-owned/main.js" ]] || fail "REA_JS_FIXTURE_MISSING"
[[ -f "$ROOT/tests/fixtures/iris-proof.html" ]] || fail "IRIS_FIXTURE_MISSING"
[[ -x "$REA" && -x "$IRIS" ]] || fail "PINNED_TOOLS_NOT_INSTALLED"
"$REA" --version | grep -F '6.0.0' >/dev/null || fail "REA_VERSION_MISMATCH"
"$IRIS" --version | grep -F '0.4.1' >/dev/null || fail "IRIS_VERSION_MISMATCH"
command -v python3 >/dev/null || fail "PYTHON_UNAVAILABLE"

CHROME=""
for name in chromium chromium-browser google-chrome google-chrome-stable; do
  if command -v "$name" >/dev/null 2>&1; then
    CHROME="$(command -v "$name")"
    break
  fi
done
[[ -n "$CHROME" && -x "$CHROME" ]] || fail "CHROMIUM_NOT_INSTALLED"
ram_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
disk_kib="$(df -Pk "$HOME" | awk 'NR==2 {print $4}')"
[[ "$ram_kib" =~ ^[0-9]+$ && "$disk_kib" =~ ^[0-9]+$ ]] || fail "RESOURCE_EVIDENCE_UNAVAILABLE"
(( ram_kib >= 4 * 1024 * 1024 )) || fail "RAM_BELOW_4GIB"
(( disk_kib >= 4 * 1024 * 1024 )) || fail "DISK_BELOW_4GIB"
export PYTHONPATH="$ROOT/src"

if [[ "$mode" == "--preflight" ]]; then
  echo "HAZEWAVE_RESEARCH_BRIDGE=PASS:PREREQUISITES"
  echo "HAZEWAVE_RESEARCH_CODE_SHA=$EXPECTED"
  echo "HAZEWAVE_RESEARCH_FEATURES=REA6_OWNED_JS,IRIS_OWNED_PAGE"
  echo "HAZEWAVE_RESEARCH_EXTERNAL_TARGETS=NO_EXTERNAL_TARGETS"
  echo "HAZEWAVE_RESEARCH_RUNTIME_EXECUTION=NOT_ATTEMPTED"
  echo "HAZEWAVE_RESEARCH_AGENT_CONNECTION=NOT_PROVEN"
  exit 0
fi

if [[ "$mode" == "--prove" ]]; then
  python3 -m hazewave.harness_research_execution \
    --kind rea_owned_js --task-id owned-rea-codespace-001 \
    --workspace "$ROOT" --expected-sha "$EXPECTED" --state-root "$STATE" \
    --rea "$REA" || fail "REA_FIXTURE_RUNTIME_FAILED"
  python3 -m hazewave.harness_research_execution \
    --kind iris_owned_page --task-id owned-iris-codespace-001 \
    --workspace "$ROOT" --expected-sha "$EXPECTED" --state-root "$STATE" \
    --iris "$IRIS" --chrome "$CHROME" || fail "IRIS_FIXTURE_RUNTIME_FAILED"
  echo "HAZEWAVE_RESEARCH_BRIDGE=PASS:OWNED_FIXTURE_EXECUTION"
  echo "HAZEWAVE_RESEARCH_EXTERNAL_TARGETS=NO_EXTERNAL_TARGETS"
  echo "HAZEWAVE_RESEARCH_AGENT_CONNECTION=NOT_PROVEN"
  echo "HAZEWAVE_RESEARCH_PRODUCTION=NOT_APPROVED"
  exit 0
fi

# MCP STDIO stdout belongs EXCLUSIVELY to the JSON-RPC protocol.
# The raw REA/Iris tools stay unregistered; this facade exposes no URL/path args.
exec python3 -m hazewave.harness_research_mcp \
  --workspace "$ROOT" --expected-sha "$EXPECTED" --state-root "$STATE" \
  --rea "$REA" --iris "$IRIS" --chrome "$CHROME"
