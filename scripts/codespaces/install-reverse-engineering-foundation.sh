#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"

PROJECT_ID="HAZEWAVE"
AUTHORITY="HAZEWAVE_HARNESS"
NODE_VERSION="24.11.0"
NODE_ASSET="node-v24.11.0-linux-x64.tar.xz"
NODE_SHA256="46da9a098973ab7ba4fca76945581ecb2eaf468de347173897044382f10e0a0a"
NODE_URL="https://nodejs.org/dist/v24.11.0/$NODE_ASSET"
REA_VERSION="6.0.0"
GHIDRA_VERSION="12.1.4"
GHIDRA_ASSET="ghidra_12.1.4_PUBLIC_20260921.zip"
GHIDRA_SHA256="ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db"
GHIDRA_URL="https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/$GHIDRA_ASSET"
FRIDA_VERSION="17.23.0"
FRIDA_TOOLS_VERSION="14.11.0"
RIZIN_VERSION="0.9.1"
RIZIN_ASSET="rizin-v0.9.1-static-x86_64.tar.xz"
RIZIN_SHA256="9102249a9f0b6319c5334a2e5cf8d9cc3f2035e1d3def027c41f6a90f647e8cf"
RIZIN_URL="https://github.com/rizinorg/rizin/releases/download/v0.9.1/$RIZIN_ASSET"

ROOT="${HAZEWAVE_RE_ROOT:-$HOME/.local/share/hazewave/reverse-engineering}"
BIN_ROOT="$HOME/.local/bin"
CONFIG_ROOT="$HOME/.config/hazewave"
ENV_FILE="$CONFIG_ROOT/reverse-engineering-rea6.env"
RECEIPT="$ROOT/reverse-engineering-rea6-install-receipt.json"
DOWNLOADS="$ROOT/downloads"
NODE_ROOT="$ROOT/node-$NODE_VERSION"
REA_PREFIX="$ROOT/rea-$REA_VERSION"
GHIDRA_ROOT="$ROOT/ghidra-$GHIDRA_VERSION"
FRIDA_VENV="$ROOT/frida-$FRIDA_VERSION"
RIZIN_ROOT="$ROOT/rizin-$RIZIN_VERSION"
CLI_VENV="$ROOT/hazewave-cli-venv"

fail() {
  printf 'HAZEWAVE_RE_INSTALL=FAIL:%s\n' "$1" >&2
  exit 20
}

[[ "$(uname -s)" == "Linux" ]] || fail "UNSUPPORTED_OS"
[[ "$(uname -m)" == "x86_64" ]] || fail "UNSUPPORTED_ARCH"

# Prevent a heavy install when disk headroom is insufficient for Ghidra,
# Rizin, Node/npm and the existing Colibri model. Do not mutate the host on preflight.
available_kib="$(df -Pk "$HOME" | awk 'NR==2 {print $4}')"
[[ "$available_kib" =~ ^[0-9]+$ ]] || fail "DISK_HEADROOM_UNKNOWN"
(( available_kib >= 8 * 1024 * 1024 )) || fail "DISK_HEADROOM_BELOW_8GIB"
echo "HAZEWAVE_RE_DISK_FREE_KIB=$available_kib"
if [[ "${1:-}" == "--preflight" ]]; then
  echo "HAZEWAVE_RE_PREFLIGHT=PASS"
  echo "HAZEWAVE_RE_INSTALL=NOT_ATTEMPTED"
  exit 0
fi
[[ "$#" -eq 0 ]] || fail "UNSUPPORTED_ARGUMENT"

for cmd in curl sha256sum tar python3; do
  command -v "$cmd" >/dev/null 2>&1 || fail "MISSING_PREREQUISITE:$cmd"
done

mkdir -p "$ROOT" "$DOWNLOADS" "$BIN_ROOT" "$CONFIG_ROOT"
chmod 700 "$ROOT" "$DOWNLOADS" "$CONFIG_ROOT"

if [[ ! -x "$CLI_VENV/bin/python" ]]; then
  python3 -m venv "$CLI_VENV"     || fail "HAZEWAVE_CLI_VENV_CREATE_FAILED"
fi

"$CLI_VENV/bin/python" -m pip install   --disable-pip-version-check   --no-input   -e "$REPO_ROOT"   >/dev/null   || fail "HAZEWAVE_CLI_DEPENDENCIES_INSTALL_FAILED"

"$CLI_VENV/bin/python" -c "import httpx, hazewave"   || fail "HAZEWAVE_CLI_IMPORT_FAILED"

if [[ ! -x "$NODE_ROOT/bin/node" || ! -x "$NODE_ROOT/bin/npm" ]]; then
  node_tar="$DOWNLOADS/$NODE_ASSET"
  if [[ ! -f "$node_tar" ]]; then
    curl --fail --location --retry 3 --output "$node_tar" "$NODE_URL"
  fi
  printf '%s  %s\n' "$NODE_SHA256" "$node_tar" | sha256sum -c - >/dev/null \
    || fail "NODE_SHA256_MISMATCH"

  stage="$(mktemp -d "$ROOT/.node-stage.XXXXXX")"
  tar -xJf "$node_tar" -C "$stage" \
    || { rm -rf "$stage"; fail "NODE_EXTRACT_FAILED"; }

  extracted="$stage/node-v$NODE_VERSION-linux-x64"
  [[ -x "$extracted/bin/node" && -x "$extracted/bin/npm" ]] \
    || { rm -rf "$stage"; fail "NODE_LAYOUT_INVALID"; }

  [[ ! -e "$NODE_ROOT" ]] \
    || { rm -rf "$stage"; fail "NODE_ROOT_OCCUPIED_INVALID"; }

  mv "$extracted" "$NODE_ROOT"
  rm -rf "$stage"
fi

export PATH="$NODE_ROOT/bin:$PATH"

for cmd in node npm; do
  command -v "$cmd" >/dev/null 2>&1 || fail "PINNED_NODE_COMMAND_MISSING:$cmd"
done

python3 - "$(node --version)" <<'PY' || fail "NODE_VERSION_UNSUPPORTED"
import re, sys
raw = sys.argv[1].lstrip("v")
if not re.fullmatch(r"\d+\.\d+\.\d+", raw):
    raise SystemExit(1)
major, minor, patch = map(int, raw.split("."))
ok = (
    (major == 22 and (minor, patch) >= (19, 0))
    or (major == 24 and (minor, patch) >= (11, 0))
    or major >= 26
)
raise SystemExit(0 if ok else 1)
PY

[[ "$(node --version)" == "v$NODE_VERSION" ]] || fail "NODE_PIN_MISMATCH:$(node --version)"
node_version="$(node --version | tr -d '\r')"
npm_version="$(npm --version | tr -d '\r')"

echo "HAZEWAVE_RE_NODE=$node_version"
echo "HAZEWAVE_RE_NPM=$npm_version"

if [[ ! -x "$REA_PREFIX/node_modules/.bin/rea" ]]; then
  stage="$(mktemp -d "$ROOT/.rea-stage.XXXXXX")"
  npm_config_ignore_scripts=true npm install --prefix "$stage" --no-audit --no-fund "rea-agents@6.0.0"
  [[ -x "$stage/node_modules/.bin/rea" ]] || { rm -rf "$stage"; fail "REA_BINARY_MISSING"; }
  observed="$("$stage/node_modules/.bin/rea" --version 2>/dev/null | tr -d '\r' | tail -n 1)"
  [[ "$observed" == *"$REA_VERSION"* ]] || { rm -rf "$stage"; fail "REA_VERSION_MISMATCH:$observed"; }
  mv "$stage" "$REA_PREFIX"
fi

REA_BIN="$REA_PREFIX/node_modules/.bin/rea"
[[ -x "$REA_BIN" ]] || fail "REA_BINARY_MISSING_AFTER_INSTALL"

if ! command -v java >/dev/null 2>&1 || ! java -version 2>&1 | sed -n '1p' | grep -Eq '"21([."]|$)'; then
  if command -v sudo >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y openjdk-21-jdk-headless unzip mediainfo
  else
    fail "JDK21_REQUIRED"
  fi
fi
java -version 2>&1 | sed -n '1p' | grep -Eq '"21([."]|$)' || fail "JDK21_NOT_ACTIVE"
command -v unzip >/dev/null 2>&1 || fail "UNZIP_MISSING"

if [[ ! -x "$GHIDRA_ROOT/support/analyzeHeadless" ]]; then
  ghidra_zip="$DOWNLOADS/$GHIDRA_ASSET"
  if [[ ! -f "$ghidra_zip" ]]; then
    curl --fail --location --retry 3 --output "$ghidra_zip" "$GHIDRA_URL"
  fi
  printf '%s  %s\n' "$GHIDRA_SHA256" "$ghidra_zip" | sha256sum -c - >/dev/null     || fail "GHIDRA_SHA256_MISMATCH"
  stage="$(mktemp -d "$ROOT/.ghidra-stage.XXXXXX")"
  unzip -q "$ghidra_zip" -d "$stage"
  extracted="$(find "$stage" -mindepth 1 -maxdepth 1 -type d -name 'ghidra_*' -print -quit)"
  [[ -n "$extracted" && -x "$extracted/support/analyzeHeadless" ]]     || { rm -rf "$stage"; fail "GHIDRA_LAYOUT_INVALID"; }
  mv "$extracted" "$GHIDRA_ROOT"
  rm -rf "$stage"
fi

if [[ ! -x "$RIZIN_ROOT/bin/rizin" ]]; then
  rizin_tar="$DOWNLOADS/$RIZIN_ASSET"
  if [[ ! -f "$rizin_tar" ]]; then
    curl --fail --location --retry 3 --output "$rizin_tar" "$RIZIN_URL"
  fi
  printf '%s  %s\n' "$RIZIN_SHA256" "$rizin_tar" | sha256sum -c - >/dev/null     || fail "RIZIN_SHA256_MISMATCH"
  stage="$(mktemp -d "$ROOT/.rizin-stage.XXXXXX")"
  tar -xJf "$rizin_tar" -C "$stage"
  candidate="$(find "$stage" -type f -name rizin -perm -u+x -print -quit)"
  [[ -n "$candidate" ]] || { rm -rf "$stage"; fail "RIZIN_BINARY_MISSING"; }
  prefix="$(dirname "$(dirname "$candidate")")"
  mv "$prefix" "$RIZIN_ROOT"
  rm -rf "$stage"
fi

if [[ ! -x "$FRIDA_VENV/bin/frida" ]]; then
  python3 -m venv "$FRIDA_VENV"
  "$FRIDA_VENV/bin/python" -m pip install --disable-pip-version-check --no-input     "frida==17.23.0" "frida-tools==14.11.0"
fi

command -v ffmpeg >/dev/null 2>&1 || fail "FFMPEG_REQUIRED_EXISTING_RUNTIME"
command -v ffprobe >/dev/null 2>&1 || fail "FFPROBE_REQUIRED_EXISTING_RUNTIME"
if ! command -v mediainfo >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mediainfo
  else
    fail "MEDIAINFO_MISSING"
  fi
fi

RIZIN_BIN="$RIZIN_ROOT/bin/rizin"
[[ -x "$RIZIN_BIN" ]] || fail "RIZIN_BINARY_MISSING_AFTER_INSTALL"
[[ -x "$FRIDA_VENV/bin/frida" ]] || fail "FRIDA_BINARY_MISSING_AFTER_INSTALL"
[[ -x "$GHIDRA_ROOT/support/analyzeHeadless" ]] || fail "GHIDRA_HEADLESS_MISSING_AFTER_INSTALL"

mkdir -p "$REA_PREFIX/bin"
ln -sfn "$REA_BIN" "$REA_PREFIX/bin/rea"




cat >"$BIN_ROOT/hazewave-rea6" <<EOF
#!/usr/bin/env bash
set -euo pipefail
source "$ENV_FILE"
exec "$REA_BIN" "\$@"
EOF
chmod 755 "$BIN_ROOT/hazewave-rea6"

cat >"$ENV_FILE" <<EOF
export HAZEWAVE_RE_ROOT="$ROOT"
export REA_ANALYSIS_PROVIDER=ghidra
export GHIDRA_INSTALL_DIR="$GHIDRA_ROOT"
export HAZEWAVE_RE_AUTHORITY="$AUTHORITY"
export HAZEWAVE_RE_PYTHON="$CLI_VENV/bin/python"
export HAZEWAVE_RE_REPO_ROOT="$REPO_ROOT"
export PATH="$REA_PREFIX/bin:$NODE_ROOT/bin:$FRIDA_VENV/bin:$RIZIN_ROOT/bin:$BIN_ROOT:\$PATH"
EOF
chmod 600 "$ENV_FILE"

cat >"$BIN_ROOT/hazewave-re6-cli" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
source "$HOME/.config/hazewave/reverse-engineering-rea6.env"
[[ -x "$HAZEWAVE_RE_PYTHON" ]] || {
  echo "HAZEWAVE_RE_CLI=FAIL:PYTHON_RUNTIME_MISSING" >&2
  exit 20
}
[[ -d "$HAZEWAVE_RE_REPO_ROOT/src/hazewave" ]] || {
  echo "HAZEWAVE_RE_CLI=FAIL:REPOSITORY_SOURCE_MISSING" >&2
  exit 20
}
exec env PYTHONPATH="$HAZEWAVE_RE_REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
  "$HAZEWAVE_RE_PYTHON" -m hazewave.cli reverse-engineering "$@"
EOF
chmod 755 "$BIN_ROOT/hazewave-re6-cli"

source "$ENV_FILE"

"$HAZEWAVE_RE_PYTHON" -c "import httpx"   || fail "HAZEWAVE_CLI_HTTPX_IMPORT_FAILED"
hazewave-re6-cli registry >/dev/null   || fail "HAZEWAVE_CLI_REGISTRY_SMOKE_FAILED"

rea_version="$("$REA_BIN" --version 2>/dev/null | tail -n 1 | tr -d '\r')"
rizin_version="$("$RIZIN_BIN" -v 2>/dev/null | sed -n '1p' | tr -d '\r')"
frida_version="$("$FRIDA_VENV/bin/frida" --version 2>/dev/null | sed -n '1p' | tr -d '\r')"
ffmpeg_version="$(ffmpeg -version 2>/dev/null | sed -n '1p' | tr -d '\r')"
mediainfo_version="$(mediainfo --Version 2>/dev/null | tail -n 1 | tr -d '\r')"
java_version="$(java -version 2>&1 | sed -n '1p' | tr -d '\r')"

REA_ANALYSIS_PROVIDER=ghidra GHIDRA_INSTALL_DIR="$GHIDRA_ROOT"   "$REA_BIN" providers --json >"$ROOT/rea6-providers.json" || fail "REA_PROVIDERS_FAILED"
set +e
REA_ANALYSIS_PROVIDER=ghidra GHIDRA_INSTALL_DIR="$GHIDRA_ROOT"   "$REA_BIN" doctor --provider ghidra --json >"$ROOT/rea6-doctor.json"
rea_doctor_rc=$?
set -e
[[ "$rea_doctor_rc" -eq 0 ]] || echo "HAZEWAVE_RE_DIAGNOSTIC=RE_DOCTOR_NONZERO:$rea_doctor_rc"

python3 - "$RECEIPT" "$rea_version" "$rizin_version" "$frida_version"   "$ffmpeg_version" "$mediainfo_version" "$java_version" "$GHIDRA_ROOT"   "$GHIDRA_SHA256" "$RIZIN_SHA256" "$node_version" "$npm_version" "$rea_doctor_rc" <<'PY'
import hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

(
    receipt_path, rea_version, rizin_version, frida_version, ffmpeg_version,
    mediainfo_version, java_version, ghidra_root, ghidra_sha, rizin_sha,
    node_version, npm_version, rea_doctor_rc
) = sys.argv[1:]
providers = Path(os.environ["HAZEWAVE_RE_ROOT"]) / "rea6-providers.json"
doctor = Path(os.environ["HAZEWAVE_RE_ROOT"]) / "rea6-doctor.json"
payload = {
    "schema": "HazewaveReverseEngineeringInstallReceipt/v1",
    "project_id": "HAZEWAVE",
    "authority": "HAZEWAVE_HARNESS",
    "installed_at": datetime.now(timezone.utc).isoformat(),
    "node": {"version_output": node_version, "pin": "24.11.0", "npm_version_output": npm_version},
    "rea": {"version_output": rea_version, "pin": "6.0.0"},
    "ghidra": {
        "pin": "12.1.4",
        "install_dir": ghidra_root,
        "release_sha256": ghidra_sha,
    },
    "rizin": {"version_output": rizin_version, "pin": "0.9.1", "release_sha256": rizin_sha},
    "frida": {"version_output": frida_version, "pin": "17.23.0", "tools_pin": "14.11.0"},
    "ffmpeg": {"version_output": ffmpeg_version},
    "mediainfo": {"version_output": mediainfo_version},
    "java": {"version_output": java_version},
    "rea_providers_sha256": hashlib.sha256(providers.read_bytes()).hexdigest(),
    "rea_doctor_sha256": hashlib.sha256(doctor.read_bytes()).hexdigest() if doctor.exists() else None,
    "grants_execution_authority": False,
    "production_approved": False,
    "rea_doctor_exit_code": int(rea_doctor_rc),
    "runtime_ready": False,
    "installation_state": "INSTALLED_NOT_RUNTIME_PROVEN",
}
target = Path(receipt_path)
tmp = target.with_suffix(".tmp")
tmp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
PY
chmod 600 "$RECEIPT"

echo "HAZEWAVE_RE_PROJECT=$PROJECT_ID"
echo "HAZEWAVE_RE_AUTHORITY=$AUTHORITY"
echo "HAZEWAVE_RE_NODE=$node_version"
echo "HAZEWAVE_RE_NPM=$npm_version"
echo "HAZEWAVE_RE_REA=$rea_version"
echo "HAZEWAVE_RE_GHIDRA=$GHIDRA_VERSION"
echo "HAZEWAVE_RE_RIZIN=$rizin_version"
echo "HAZEWAVE_RE_FRIDA=$frida_version"
echo "HAZEWAVE_RE_RECEIPT=$RECEIPT"
echo "HAZEWAVE_RE_INSTALL=PASS"
echo "HAZEWAVE_RE_RUNTIME_READY=NOT_PROVEN"
[[ "$rea_doctor_rc" -eq 0 ]] || echo "HAZEWAVE_RE_READY_BLOCKER=RE_DOCTOR_NONZERO"
