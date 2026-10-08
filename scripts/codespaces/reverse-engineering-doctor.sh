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

rea --version | grep -F "6.0.0" >/dev/null || fail "REA_VERSION_MISMATCH"
"$HAZEWAVE_RE_PYTHON" - "$ROOT/rea-6.0.0/node_modules/rea-agents/package.json" <<'PY' || fail "REA_INSTALLED_PACKAGE_IDENTITY_MISMATCH"
import json
import sys
from pathlib import Path
p = Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))
if data.get("name") != "rea-agents" or data.get("version") != "6.0.0" or data.get("license") != "MIT":
    raise SystemExit(2)
PY
frida --version | grep -F "17.23.0" >/dev/null || fail "FRIDA_VERSION_MISMATCH"
rizin -v | grep -F "0.9.1" >/dev/null || fail "RIZIN_VERSION_MISMATCH"
java -version 2>&1 | sed -n '1p' | grep -Eq '"21([."]|$)' || fail "JAVA_VERSION_MISMATCH"
"$HAZEWAVE_RE_PYTHON" -c "import httpx" || fail "HAZEWAVE_CLI_HTTPX_IMPORT_FAILED"

mkdir -p "$ROOT/doctor"
chmod 700 "$ROOT/doctor"
hazewave-re-cli registry >"$ROOT/doctor/hazewave-registry.json"   || fail "HAZEWAVE_CLI_REGISTRY_FAILED"
rea providers --json >"$ROOT/doctor/providers.json" || fail "REA_PROVIDERS_FAILED"
set +e
rea doctor --provider ghidra --json >"$ROOT/doctor/doctor.json"
doctor_rc=$?
set -e

python3 - "$ROOT/doctor/providers.json" <<'PY' || fail "GHIDRA_PROVIDER_NOT_DISCOVERED"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
raw = json.dumps(data).casefold()
if "ghidra" not in raw:
    raise SystemExit(1)
PY

[[ "$doctor_rc" -eq 0 ]] || fail "REA_DOCTOR_FAILED:$doctor_rc"

if [[ "$DEEP" -eq 1 ]]; then
  command -v cc >/dev/null 2>&1 || fail "RE_DEEP_COMPILER_MISSING"
  # The Codespace is shared with REAPER/FFmpeg and stock Colibri. Do not
  # start a JVM decompiler when memory is already under pressure.
  available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  [[ "$available_kib" =~ ^[0-9]+$ ]] || fail "RE_DEEP_MEMORY_UNKNOWN"
  (( available_kib >= 4 * 1024 * 1024 )) || fail "RE_DEEP_MEMORY_BELOW_4GIB"

  # Compile a harmless first-party target rather than assume the system
  # /bin/true has a searchable `main` function or stable symbols.
  local_run="$(mktemp -d "$ROOT/doctor/rea6-fixture.XXXXXXXX")"
  chmod 700 "$local_run"
  source_file="$local_run/fixture.c"
  target="$local_run/fixture"
  evidence_file="$local_run/ghidra-main.evidence.json"
  cat >"$source_file" <<'C'
/* REA6_SOURCE_OWNED_FIXTURE: no secrets, network or third-party code. */
__attribute__((noinline)) static int evidence_constant(void) { return 42; }
int main(void) { return evidence_constant() == 42 ? 0 : 1; }
C
  chmod 600 "$source_file"
  cc -O0 -g -fno-omit-frame-pointer -o "$target" "$source_file" || fail "RE_DEEP_FIXTURE_COMPILE_FAILED"
  chmod 700 "$target"
  target_sha="$(sha256sum "$target" | awk '{print $1}')"

  # Ghidra provider explicitly selected: no Hopper/proprietary fallback.
  # JSON remains on disk even when the schema validation fails.
  REA_ANALYSIS_PROVIDER=ghidra rea function "$target" main --provider ghidra --json \
    >"$evidence_file" || fail "RE_DEEP_GHIDRA_FUNCTION_FAILED"
  chmod 600 "$evidence_file"
  "$HAZEWAVE_RE_PYTHON" -m hazewave.rea6_integration verify-evidence \
    --target "$target" --evidence "$evidence_file" \
    >"$local_run/evidence-audit.json" || fail "RE_DEEP_EVIDENCE_NOT_VERIFIED"
  chmod 600 "$local_run/evidence-audit.json"
  echo "HAZEWAVE_RE_DEEP_FIXTURE_SHA256=$target_sha"
  echo "HAZEWAVE_RE_DEEP_EVIDENCE=$evidence_file"
  echo "HAZEWAVE_RE_DEEP_PROBE=PASS"
fi

chmod 600   "$ROOT/doctor/hazewave-registry.json"   "$ROOT/doctor/providers.json"   "$ROOT/doctor/doctor.json"
echo "HAZEWAVE_RE_DOCTOR_GLOBAL_RC=$doctor_rc"
echo "HAZEWAVE_RE_PROVIDER=ghidra"
echo "HAZEWAVE_RE_DOCTOR=PASS"
