#!/usr/bin/env bash
# REA research loop next-level qualified fixtures: on the ONE existing Hazewave Codespace.
# No npm/apt installs, no service restart, and no global agent registration.
set -euo pipefail
fail() { echo "HAZEWAVE_CLOSED_LOOP=BLOCKED:$1" >&2; exit 20; }
[[ $# -eq 1 ]] || fail "EXPLICIT_MODE_REQUIRED"
case "$1" in --preflight|--native-auto|--av-metrics|--triangulate) mode="$1";; *) fail "MODE_NOT_ADMITTED";; esac
[[ "${CODESPACE_NAME:-}" == "hazewave-zero-cost-4jxp45676rq6279xx" ]] || fail "EXISTING_CODESPACE_REQUIRED"

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$HERE/../.." && pwd -P)"
EXPECTED="${HAZEWAVE_RESEARCH_EXPECTED_SHA:-}"
[[ "$EXPECTED" =~ ^[0-9a-f]{40}$ ]] || fail "REVIEWED_SHA_REQUIRED"
[[ "$(git -C "$ROOT" rev-parse HEAD 2>/dev/null)" == "$EXPECTED" ]] || fail "HEAD_DRIFT"
[[ -z "$(git -C "$ROOT" status --porcelain)" ]] || fail "DIRTY_WORKTREE"
remote="$(git -C "$ROOT" remote get-url origin 2>/dev/null)" || fail "MISSING_ORIGIN"
case "$remote" in
  https://github.com/zenindiones-maker/Hazewave-|https://github.com/zenindiones-maker/Hazewave-.git|git@github.com:zenindiones-maker/Hazewave-|git@github.com:zenindiones-maker/Hazewave-.git) ;;
  *) fail "REPO_IDENTITY_MISMATCH" ;;
esac
[[ -f "$ROOT/tests/fixtures/native-owned-reconstruction/original.c" ]] || fail "OWNED_ORACLE_MISSING"
[[ -f "$ROOT/src/hazewave/av_fidelity_oracle.py" ]] || fail "AV_ORACLE_MODULE_MISSING"
command -v python3 >/dev/null || fail "PYTHON_MISSING"
command -v cc >/dev/null || fail "CC_MISSING"
if [[ "$mode" == "--av-metrics" ]]; then
  command -v ffmpeg >/dev/null || fail "FFMPEG_NOT_INSTALLED"
fi
if [[ "$mode" == "--triangulate" ]]; then
  python3 -c 'import z3; assert z3.get_version_string()' 2>/dev/null || fail "Z3_PYTHON_BINDING_REQUIRED"
  REA="$HOME/.local/share/hazewave/reverse-engineering/rea-6.0.0/bin/rea"
  [[ -x "$REA" ]] || fail "REA6_BINARY_MISSING"
  "$REA" --version | grep -F '6.0.0' >/dev/null || fail "REA6_VERSION_MISMATCH"
  ENVFILE="$HOME/.config/hazewave/reverse-engineering-rea6.env"
  [[ -f "$ENVFILE" && ! -L "$ENVFILE" ]] || fail "REA6_ENVFILE_MISSING"
  [[ "$(stat -c %a "$ENVFILE")" == "600" ]] || fail "REA6_ENVFILE_PERMISSIONS"
  # shellcheck disable=SC1090
  source "$ENVFILE"
  [[ "${REA_ANALYSIS_PROVIDER:-}" == "ghidra" ]] || fail "GHIDRA_PROVIDER_EXPLICIT_REQUIRED"
  [[ -n "${GHIDRA_INSTALL_DIR:-}" && -x "$GHIDRA_INSTALL_DIR/support/analyzeHeadless" ]] || fail "GHIDRA_HEADLESS_MISSING"
  command -v java >/dev/null || fail "JAVA_RUNTIME_MISSING"
fi
available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
[[ "$available_kib" =~ ^[0-9]+$ ]] || fail "RAM_UNOBSERVED"
(( available_kib >= 1024*1024 )) || fail "MEMORY_BUDGET_DENIED"
if [[ "$mode" == "--triangulate" ]]; then
  (( available_kib >= 4*1024*1024 )) || fail "GHIDRA_MEMORY_BUDGET_DENIED"
fi
export PYTHONPATH="$ROOT/src"
if [[ "$mode" == "--preflight" ]]; then
  echo "HAZEWAVE_CLOSED_LOOP_PREFLIGHT=PASS"
  echo "HAZEWAVE_RESEARCH_SCOPE=OWNED_SOURCE_FIXTURES_ONLY"
  echo "HAZEWAVE_RESEARCH_TOOL_EXECUTION=NOT_ATTEMPTED"
  echo "HAZEWAVE_RESEARCH_AGENT_CONNECTION=NOT_PROVEN"
  echo "STOCK_HEALTH=NOT_CHECKED"
  exit 0
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
STATE="$HOME/.local/state/hazewave/research-lab"
if [[ "$mode" == "--triangulate" ]]; then
  python3 -m hazewave.native_behavior_synthesis \
    --state-root "$STATE/triangulate-$STAMP" --formal --rea "$REA" \
    || fail "GHIDRA_FORMAL_NATIVE_TRIANGULATION_FAILED"
  echo "GHIDRA_FORMAL_NATIVE_TRIANGULATION=PASS"
  echo "GHIDRA_GUIDED_SYNTHESIS=NOT_PROVEN"
elif [[ "$mode" == "--native-auto" ]]; then
  python3 -m hazewave.native_behavior_synthesis \
    --state-root "$STATE/native-auto-$STAMP" || fail "NATIVE_AUTOSYNTHESIS_FAILED"
  echo "HAZEWAVE_NATIVE_AUTOSYNTHESIS=PASS:OWNED_FINITE_DOMAIN_ONLY"
else
  python3 -m hazewave.av_fidelity_oracle \
    --private-root "$STATE/av-metrics-$STAMP" || fail "AV_SYNTHETIC_METRICS_FAILED"
  echo "HAZEWAVE_AV_METRICS=PASS:OWNED_SYNTHETIC_ONLY"
fi
echo "PRODUCTION_APPROVED=FALSE"
echo "HAZEWAVE_PRODUCTION_AUTHORIZED=FALSE"
echo "HAZEWAVE_AGENT_MCP=NOT_PROVEN"
echo "STOCK_HEALTH=NOT_CHECKED"
