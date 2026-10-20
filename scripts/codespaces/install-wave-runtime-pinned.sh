#!/usr/bin/env bash
set -euo pipefail

OTIO_VERSION="0.18.1"
SCENEDETECT_VERSION="0.7.1"
WAVE_RUNTIME_ROOT="${HOME}/.local/opt/hazewave-wave-runtime/0.18.1-0.7.1"
WAVE_RUNTIME_PYTHON="${WAVE_RUNTIME_ROOT}/bin/python"
STATE_ROOT="${HOME}/.local/state/hazewave-codespace"
RECEIPT="${STATE_ROOT}/wave-runtime-0.18.1-0.7.1.receipt"
CREATED_TARGET=0

die() {
  echo "$1" >&2
  exit "${2:-20}"
}

verify_runtime() {
  [[ -x "$WAVE_RUNTIME_PYTHON" ]] || return 1
  local versions
  versions="$("$WAVE_RUNTIME_PYTHON" - <<'PY'
import opentimelineio as otio
import scenedetect

print(f"OTIO={getattr(otio, '__version__', '')}")
print(f"SCENEDETECT={getattr(scenedetect, '__version__', '')}")
PY
)" || return 1
  grep -Fxq "OTIO=0.18.1" <<<"$versions" || return 1
  grep -Fxq "SCENEDETECT=0.7.1" <<<"$versions" || return 1
  [[ -s "$RECEIPT" ]] || return 1
  grep -Fxq "WAVE_OTIO_VERSION=0.18.1" "$RECEIPT" || return 1
  grep -Fxq "WAVE_SCENEDETECT_VERSION=0.7.1" "$RECEIPT" || return 1
  return 0
}

cleanup_failed_target() {
  local status=$?
  if [[ "$status" -ne 0 && "$CREATED_TARGET" == "1" ]]; then
    rm -rf "$WAVE_RUNTIME_ROOT"
  fi
  exit "$status"
}
trap cleanup_failed_target EXIT

mkdir -p "$(dirname "$WAVE_RUNTIME_ROOT")" "$STATE_ROOT"

if verify_runtime; then
  echo "WAVE_RUNTIME_INSTALL=PASS_ALREADY_PINNED"
  echo "WAVE_OTIO_VERSION=0.18.1"
  echo "WAVE_SCENEDETECT_VERSION=0.7.1"
  echo "PAID_FALLBACK=FALSE"
  echo "UNKNOWN_COST_FALLBACK=FALSE"
  trap - EXIT
  exit 0
fi

[[ ! -e "$WAVE_RUNTIME_ROOT" ]] ||   die "WAVE_RUNTIME_INSTALL=BLOCKED_EXISTING_UNVERIFIED_TARGET" 21

command -v python3 >/dev/null 2>&1 || die "WAVE_RUNTIME_INSTALL=FAIL_PYTHON3_MISSING" 22
python3 -m venv --help >/dev/null 2>&1 || die "WAVE_RUNTIME_INSTALL=FAIL_VENV_UNAVAILABLE" 23

python3 -m venv "$WAVE_RUNTIME_ROOT"
CREATED_TARGET=1

export PIP_DISABLE_PIP_VERSION_CHECK=1
"$WAVE_RUNTIME_PYTHON" -m pip install --only-binary=:all: \
  --no-cache-dir \
  "OpenTimelineIO==0.18.1" \
  "scenedetect-headless==0.7.1"

VERSIONS="$("$WAVE_RUNTIME_PYTHON" - <<'PY'
import opentimelineio as otio
import scenedetect

print(f"OTIO={getattr(otio, '__version__', '')}")
print(f"SCENEDETECT={getattr(scenedetect, '__version__', '')}")
PY
)"

grep -Fxq "OTIO=0.18.1" <<<"$VERSIONS" ||   die "WAVE_RUNTIME_INSTALL=FAIL_OTIO_VERSION" 24
grep -Fxq "SCENEDETECT=0.7.1" <<<"$VERSIONS" ||   die "WAVE_RUNTIME_INSTALL=FAIL_SCENE_VERSION" 25

cat >"$RECEIPT" <<EOF
WAVE_RUNTIME=HAZEWAVE_WAVE_PYTHON_V1
WAVE_RUNTIME_ROOT=$WAVE_RUNTIME_ROOT
WAVE_OTIO_VERSION=0.18.1
WAVE_SCENEDETECT_VERSION=0.7.1
OTIO_PACKAGE=OpenTimelineIO==0.18.1
SCENEDETECT_PACKAGE=scenedetect-headless==0.7.1
INSTALL_MODE=ISOLATED_VENV_BINARY_WHEELS_ONLY
PAID_FALLBACK=FALSE
UNKNOWN_COST_FALLBACK=FALSE
EOF
chmod 600 "$RECEIPT"

verify_runtime || die "WAVE_RUNTIME_INSTALL=FAIL_POSTINSTALL_VERIFY" 26

CREATED_TARGET=0
trap - EXIT

echo "WAVE_RUNTIME_INSTALL=PASS"
echo "WAVE_RUNTIME_PYTHON=$WAVE_RUNTIME_PYTHON"
echo "WAVE_OTIO_VERSION=0.18.1"
echo "WAVE_SCENEDETECT_VERSION=0.7.1"
echo "PAID_FALLBACK=FALSE"
echo "UNKNOWN_COST_FALLBACK=FALSE"
