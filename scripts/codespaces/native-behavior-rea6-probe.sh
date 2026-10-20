#!/usr/bin/env bash
# Native REA/Ghidra behavioral conformance; only the EXISTING Hazewave Codespace.
# No downloads/installs, no global agent registration, no stock/Colibri restart.
set -euo pipefail
fail() { printf 'HAZEWAVE_NATIVE_CODESPACE=BLOCKED:%s\n' "$1" >&2; exit 20; }
[[ "$#" -eq 1 ]] || fail "EXPLICIT_MODE_REQUIRED"
mode="$1"
case "$mode" in --inventory|--behavior|--ghidra) ;; *) fail "MODE_NOT_ADMITTED" ;; esac

[[ "${CODESPACE_NAME:-}" == "hazewave-zero-cost-4jxp45676rq6279xx" ]] || fail "WRONG_CODESPACE_ID"
DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$DIR/../.." && pwd -P)"
SHA="${HAZEWAVE_NATIVE_EXPECTED_SHA:-}"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || fail "REVIEWED_SHA_REQUIRED"
[[ "$(git -C "$ROOT" rev-parse HEAD 2>/dev/null)" == "$SHA" ]] || fail "GIT_SHA_MOVED"
[[ -z "$(git -C "$ROOT" status --porcelain)" ]] || fail "WORKTREE_DIRTY"
remote="$(git -C "$ROOT" remote get-url origin 2>/dev/null)" || fail "GIT_REMOTE_UNKNOWN"
case "$remote" in
  https://github.com/zenindiones-maker/Hazewave-|https://github.com/zenindiones-maker/Hazewave-.git|git@github.com:zenindiones-maker/Hazewave-|git@github.com:zenindiones-maker/Hazewave-.git) ;;
  *) fail "REPOSITORY_IDENTITY_MISMATCH" ;;
esac
for file in "config/capability-evidence-plane-v1.json" \
  "tests/fixtures/native-owned-reconstruction/original.c" \
  "tests/fixtures/native-owned-reconstruction/reconstruction.c"; do
  [[ -f "$ROOT/$file" && ! -L "$ROOT/$file" ]] || fail "OWNED_SOURCE_UNAVAILABLE"
done
command -v python3 >/dev/null || fail "PYTHON3_MISSING"
export PYTHONPATH="$ROOT/src"

if [[ "$mode" == "--inventory" ]]; then
  echo "HAZEWAVE_CAPABILITY_INVENTORY_SCOPE=EXISTING_CODESPACE"
  python3 -m hazewave.capability_plane inventory --host-id "$CODESPACE_NAME" --repo-sha "$SHA" || fail "HOST_TOOL_INVENTORY_INVALID"
  python3 -m hazewave.harness_connection_inventory || fail "FULL_CONNECTION_LEDGER_INVALID"
  echo "HAZEWAVE_CAPABILITY_READY_WITHOUT_SIGNED_EVIDENCE=NONE"
  echo "HAZEWAVE_AGENT_SESSIONS=NOT_TESTED"
  exit 0
fi

command -v cc >/dev/null || fail "COMPILER_MISSING"
available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
[[ "$available_kib" =~ ^[0-9]+$ ]] || fail "RESOURCE_BUDGET_UNKNOWN"
(( available_kib >= 1 * 1024 * 1024 )) || fail "RAM_BELOW_1GIB"

STATE="$HOME/.local/state/hazewave/native-owned"
if [[ "$mode" == "--behavior" ]]; then
  python3 -m hazewave.native_behavior_qualification \
    --state-root "$STATE" --seed 42 --count 300 || fail "BOUNDED_BEHAVIOR_MISMATCH"
  echo "HAZEWAVE_NATIVE_CODESPACE=PASS:BOUNDED_BEHAVIOR_ONLY"
  echo "HAZEWAVE_GHIDRA_DIRECT_EVIDENCE=NOT_TESTED"
  exit 0
fi

(( available_kib >= 4 * 1024 * 1024 )) || fail "GHIDRA_RAM_BELOW_4GIB"
REA="$HOME/.local/share/hazewave/reverse-engineering/rea-6.0.0/bin/rea"
ENVFILE="$HOME/.config/hazewave/reverse-engineering-rea6.env"
[[ -x "$REA" && -f "$ENVFILE" && ! -L "$ENVFILE" ]] || fail "REA6_CONFIG_NOT_INSTALLED"
[[ "$(stat -c '%a' "$ENVFILE")" == 600 ]] || fail "REA6_ENVFILE_PERMISSIONS"
# shellcheck disable=SC1090
source "$ENVFILE"
[[ "${REA_ANALYSIS_PROVIDER:-}" == ghidra ]] || fail "IMPLICIT_FALLBACK_FORBIDDEN"
[[ -n "${GHIDRA_INSTALL_DIR:-}" && -x "$GHIDRA_INSTALL_DIR/support/analyzeHeadless" ]] || fail "GHIDRA_HEADLESS_MISSING"
command -v javac >/dev/null || [[ -n "${JAVA_HOME:-}" && -x "$JAVA_HOME/bin/javac" ]] || fail "FULL_JDK_REQUIRED"
"$REA" --version | grep -F '6.0.0' >/dev/null || fail "REA_VERSION_NOT_PINNED"
"$REA" doctor --provider ghidra --json > /dev/null || fail "GHIDRA_PROVIDER_DOCTOR_FAILED"
python3 -m hazewave.native_behavior_qualification \
  --state-root "$STATE" --seed 42 --count 300 --rea "$REA" || fail "GHIDRA_BOUND_NATIVE_BEHAVIOR_FAILED"
echo "HAZEWAVE_NATIVE_CODESPACE=PASS:BOUNDED_PLUS_GHIDRA_EVIDENCE"
echo "HAZEWAVE_GHIDRA_AGENT_MCP_SESSION=NOT_PROVEN"
echo "HAZEWAVE_PRODUCTION_APPROVAL=NOT_GRANTED"
