#!/usr/bin/env bash
set -euo pipefail

ROOT="${HAZEWAVE_RE_ROOT:-$HOME/.local/share/hazewave/reverse-engineering}"
ENV_FILE="$HOME/.config/hazewave/reverse-engineering.env"
DEEP=0
[[ "${1:-}" == "--deep" ]] && DEEP=1

fail() {
  printf 'HAZEWAVE_RE_DOCTOR=FAIL:%s\n' "$1" >&2
  exit 20
}

[[ -f "$ENV_FILE" && ! -L "$ENV_FILE" ]] || fail "ENV_FILE_MISSING_OR_SYMLINK"
[[ "$(stat -c %a "$ENV_FILE")" == "600" ]] || fail "ENV_FILE_PERMISSIONS_INVALID"
# shellcheck disable=SC1090
source "$ENV_FILE"

[[ -n "${HAZEWAVE_RE_PYTHON:-}" && -x "$HAZEWAVE_RE_PYTHON" ]]   || fail "HAZEWAVE_RE_PYTHON_MISSING"
[[ -n "${HAZEWAVE_RE_REPO_ROOT:-}" && -d "$HAZEWAVE_RE_REPO_ROOT/src/hazewave" ]]   || fail "HAZEWAVE_RE_REPO_ROOT_INVALID"

for cmd in rea rizin frida ffmpeg ffprobe mediainfo java python3 hazewave-re-cli; do
  command -v "$cmd" >/dev/null 2>&1 || fail "COMMAND_MISSING:$cmd"
done

[[ "${REA_ANALYSIS_PROVIDER:-}" == "ghidra" ]] || fail "REA_PROVIDER_NOT_GHIDRA"
[[ -n "${GHIDRA_INSTALL_DIR:-}" ]] || fail "GHIDRA_INSTALL_DIR_MISSING"
[[ -x "$GHIDRA_INSTALL_DIR/support/analyzeHeadless" ]] || fail "GHIDRA_HEADLESS_MISSING"

rea --version | grep -F "4.1.0" >/dev/null || fail "REA_VERSION_MISMATCH"
frida --version | grep -F "17.23.0" >/dev/null || fail "FRIDA_VERSION_MISMATCH"
rizin -v | grep -F "0.9.1" >/dev/null || fail "RIZIN_VERSION_MISMATCH"
java -version 2>&1 | sed -n '1p' | grep -Eq '"21([."]|$)' || fail "JAVA_VERSION_MISMATCH"
"$HAZEWAVE_RE_PYTHON" -c "import httpx" || fail "HAZEWAVE_CLI_HTTPX_IMPORT_FAILED"

mkdir -p "$ROOT/doctor"
chmod 700 "$ROOT/doctor"
hazewave-re-cli registry >"$ROOT/doctor/hazewave-registry.json"   || fail "HAZEWAVE_CLI_REGISTRY_FAILED"
rea providers --json >"$ROOT/doctor/providers.json" || fail "REA_PROVIDERS_FAILED"
set +e
rea doctor --json >"$ROOT/doctor/doctor.json"
doctor_rc=$?
set -e

python3 - "$ROOT/doctor/providers.json" <<'PY' || fail "GHIDRA_PROVIDER_NOT_DISCOVERED"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
raw = json.dumps(data).casefold()
if "ghidra" not in raw:
    raise SystemExit(1)
PY

if [[ "$DEEP" -eq 1 ]]; then
  target="/bin/true"
  [[ -x "$target" ]] || fail "DEEP_PROBE_TARGET_MISSING"
  target_sha="$(sha256sum "$target" | awk '{print $1}')"
  REA_ANALYSIS_PROVIDER=ghidra rea analyze "$target" --provider ghidra --json     >"$ROOT/doctor/deep-probe.json" || fail "GHIDRA_DEEP_PROBE_FAILED"
  python3 - "$ROOT/doctor/deep-probe.json" "$target_sha" <<'PY' || fail "DEEP_PROBE_EVIDENCE_INVALID"
import json, sys
path, target_sha = sys.argv[1:]
data = json.load(open(path, encoding="utf-8"))
raw = json.dumps(data)
if not raw or len(raw) < 64:
    raise SystemExit(1)
# The exact REA Evidence schema is provider/version specific. Keep the target
# digest beside the immutable output rather than inventing a field REA may not expose.
print(f"HAZEWAVE_RE_DEEP_TARGET_SHA256={target_sha}")
PY
  chmod 600 "$ROOT/doctor/deep-probe.json"
  echo "HAZEWAVE_RE_DEEP_PROBE=PASS"
fi

chmod 600   "$ROOT/doctor/hazewave-registry.json"   "$ROOT/doctor/providers.json"   "$ROOT/doctor/doctor.json"
echo "HAZEWAVE_RE_DOCTOR_GLOBAL_RC=$doctor_rc"
echo "HAZEWAVE_RE_PROVIDER=ghidra"
echo "HAZEWAVE_RE_DOCTOR=PASS"
