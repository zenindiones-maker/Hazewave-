#!/usr/bin/env bash
# Explicit REA6 route conformance on the EXISTING Hazewave Codespace.
# No installs, auto providers, remote websites, passwords, REAPER/Colibri effects.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
SCRIPTS="$ROOT/scripts/codespaces"
ENV_FILE="$HOME/.config/hazewave/reverse-engineering-rea6.env"
RE_ROOT="${HAZEWAVE_RE_ROOT:-$HOME/.local/share/hazewave/reverse-engineering}"
REA_BIN="$RE_ROOT/rea-6.0.0/bin/rea"
GHIDRA_SCOPE="ghidra"

deny() {
  echo "REA6_PROVIDER_CONFORMANCE=BLOCKED:$1" >&2
  exit 20
}
[[ $# -eq 1 ]] || deny "MODE_REQUIRED"
case "$1" in
  --preflight|--native|--javascript|--managed-negative) mode="$1" ;;
  *) deny "UNKNOWN_MODE" ;;
esac

[[ "${CODESPACE_NAME:-}" == "hazewave-zero-cost-4jxp45676rq6279xx" ]] || deny "EXISTING_CODESPACE_REQUIRED"
[[ -f "$ENV_FILE" && ! -L "$ENV_FILE" ]] || deny "REA6_ENV_NOT_INSTALLED"
[[ "$(stat -c %a "$ENV_FILE")" == "600" ]] || deny "ENV_PERMISSIONS_BAD"
[[ -x "$REA_BIN" ]] || deny "VERSION_PINNED_BINARY_ABSENT"
[[ "${HAZEWAVE_REA6_EXPECTED_SHA:-}" =~ ^[a-f0-9]{40}$ ]] || deny "REVIEWED_SHA_REQUIRED"
[[ "$(git -C "$ROOT" rev-parse HEAD)" == "$HAZEWAVE_REA6_EXPECTED_SHA" ]] || deny "HEAD_MOVED"
[[ -z "$(git -C "$ROOT" status --porcelain)" ]] || deny "WORKTREE_DIRTY"
"$REA_BIN" --version | grep -F "6.0.0" >/dev/null || deny "REA_VERSION_DRIFT"
available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
[[ "$available_kib" =~ ^[0-9]+$ ]] || deny "MEMORY_UNKNOWN"
(( available_kib >= 4 * 1024 * 1024 )) || deny "MEMORY_BELOW_4GIB"
[[ -f "$ROOT/tests/fixtures/rea6-javascript-owned/main.js" ]] || deny "OWNED_JS_FIXTURE_MISSING"

OUT="$RE_ROOT/doctor/rea6/routes"
# --preflight must not create directories or execute any analyzer.
if [[ "$mode" == "--preflight" ]]; then
  echo "REA6_PROVIDER_PREFLIGHT=PASS"
  echo "REA6_PROVIDER_EXECUTION=NOT_ATTEMPTED"
  echo "REA6_PROVIDER_CONFORMANCE_CODESPACE_PROVEN=NO"
  exit 0
fi

mkdir -p "$OUT"
chmod 0700 "$OUT"
if [[ "$mode" == "--native" ]]; then
  # The native provider is Ghidra. Rizin and Frida are separate auxiliary tools,
  # and their command presence does not constitute a Ghidra provider PASS.
  bash "$SCRIPTS/reverse-engineering-doctor.sh" --deep || deny "GHIDRA_DEEP_PROOF_FAILED"
  echo "REA6_NATIVE_GHIDRA_FIXTURE=PASS"
elif [[ "$mode" == "--javascript" ]]; then
  file="$OUT/js-graph.json"
  "$REA_BIN" analyze-javascript-application "$ROOT/tests/fixtures/rea6-javascript-owned" --json >"$file" || deny "JS_STATIC_CLI_FAILED"
  chmod 0600 "$file"
  PYTHONPATH="$ROOT/src" python3 -m hazewave.rea6_provider_conformance validate-js-fixture \
    --fixture "$ROOT/tests/fixtures/rea6-javascript-owned" --evidence "$file" \
    >"$OUT/js-graph-audit.json" || deny "JS_STATIC_GRAPH_NOT_PROVEN"
  chmod 0600 "$OUT/js-graph-audit.json"
  echo "REA6_JAVASCRIPT_STATIC_FIXTURE=PASS"
else
  invalid="$OUT/not-an-assembly.dll"
  printf 'HAZEWAVE_OWNED_NOT_MANAGED_PE\n' > "$invalid"
  chmod 0600 "$invalid"
  set +e
  "$REA_BIN" inspect-managed-artifact "$invalid" --json >"$OUT/managed-negative.json" 2>"$OUT/managed-negative.stderr"
  rc=$?
  set -e
  chmod 0600 "$OUT/managed-negative.json" "$OUT/managed-negative.stderr"
  [[ "$rc" -ne 0 ]] || deny "MANAGED_NON_PE_INCORRECTLY_ACCEPTED"
  echo "REA6_MANAGED_NEGATIVE_FIXTURE=PASS"
  echo "REA6_MANAGED_POSITIVE_RUNTIME=NOT_TESTED"
fi

echo "REA6_CONFORMANCE_CODESPACE_PROVEN=NO"
echo "REA6_PROVIDER_AGENT_CONNECTED=NOT_TESTED"
echo "REA6_PRODUCTION_APPROVED=FALSE"
