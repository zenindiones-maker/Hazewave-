#!/usr/bin/env bash
# Optional FOSS capability installation for existing Hazewave media research.
# There is no Codespace creation, stock service operation, privileged install,
# agent MCP registration, global package update or automatic heavy model pull.
set -euo pipefail

ROOT="${HOME}/.local/share/hazewave/av-research"
VENV="$ROOT/av-research-venv"
REPORTS="$ROOT/reports"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"

die() {
  echo "AV_RESEARCH_INSTALL=BLOCKED:$1" >&2
  exit 20
}

[[ "$#" -eq 1 ]] || die "EXPLICIT_MODE_REQUIRED"
case "$1" in
  --preflight|--core|--music|--doctor) MODE="$1" ;;
  *) die "UNKNOWN_MODE" ;;
esac

[[ "${CODESPACE_NAME:-}" == "hazewave-zero-cost-4jxp45676rq6279xx" ]] || die "EXISTING_CODESPACE_ID_REQUIRED"
[[ -f "$REPO_ROOT/config/creative-specialists-v1.json" ]] || die "HAZEWAVE_REPOSITORY_INVALID"
[[ -d "$REPO_ROOT/src/hazewave" ]] || die "HAZEWAVE_SOURCE_MISSING"
for tool in python3 ffprobe ffmpeg; do
  command -v "$tool" >/dev/null 2>&1 || die "PREREQUISITE_MISSING:$tool"
done
py_version="$(python3 -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
[[ "$py_version" == "3.12" ]] || die "PINNED_CODESPACE_PYTHON_REQUIRED_3_12"
disk_free="$(df -Pk "$HOME" | awk 'NR==2 {print $4}')"
ram_free="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
[[ "$disk_free" =~ ^[0-9]+$ && "$ram_free" =~ ^[0-9]+$ ]] || die "RESOURCE_EVIDENCE_MISSING"
(( disk_free >= 6 * 1024 * 1024 )) || die "DISK_BELOW_6GIB"
(( ram_free >= 2 * 1024 * 1024 )) || die "RAM_BELOW_2GIB"
echo "AV_RESEARCH_CPU_RESOURCE_PROFILE=EXISTING_2VCPU_8GIB"
echo "AV_RESEARCH_DISK_FREE_KIB=$disk_free"
echo "AV_RESEARCH_MEM_AVAILABLE_KIB=$ram_free"

if [[ "$MODE" == "--preflight" ]]; then
  echo "AV_RESEARCH_PREFLIGHT=PASS"
  echo "AV_RESEARCH_INSTALL=NOT_ATTEMPTED"
  exit 0
fi

if [[ "$MODE" == "--doctor" ]]; then
  [[ -x "$VENV/bin/python" ]] || die "VENV_NOT_INSTALLED"
  "$VENV/bin/python" - <<'PY' || die "CORE_RUNTIME_VERIFICATION_FAILED"
import importlib.metadata as m
import json
from PIL import Image
import scenedetect
import opentimelineio
from hazewave import av_research_lab
expected = {"pillow":"12.3.0", "scenedetect-headless":"0.7.1", "opentimelineio":"0.18.1"}
for name, version in expected.items():
    observed = m.version(name)
    assert observed == version, (name, observed, version)
im = Image.new("RGB", (4, 4), color=(0, 0, 0))
assert im.getpixel((0, 0)) == (0, 0, 0)
print(json.dumps({"schema":"HazewaveAVResearchCoreDoctor/v1", "tools":expected, "image_fixture":"PASS", "media_input_tested":False, "rea6_mcp_connected":False}))
PY
  echo "AV_RESEARCH_DOCTOR=PASS:CORE_IMPORTS_ONLY"
  echo "AV_RESEARCH_FULL_PROFESSIONAL_RUNTIME=NOT_PROVEN"
  exit 0
fi

# Both installation profiles are explicitly invoked by the operator.
mkdir -p "$ROOT" "$REPORTS"
chmod 700 "$ROOT" "$REPORTS"
if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV" || die "ISOLATED_VENV_CREATION_FAILED"
fi
if [[ "$MODE" == "--core" ]]; then
  "$VENV/bin/python" -m pip install --no-input --disable-pip-version-check --no-cache-dir --only-binary=:all: \
    --report "$REPORTS/core-install.json" \
    "pillow==12.3.0" "scenedetect-headless==0.7.1" "opentimelineio==0.18.1" \
    || die "CORE_PACKAGE_INSTALL_FAILED"
  "$VENV/bin/python" -m pip install --no-input --disable-pip-version-check --no-cache-dir --only-binary=:all: \
    -e "$REPO_ROOT" || die "HAZEWAVE_EDITABLE_ADAPTER_FAILED"
  echo "AV_RESEARCH_INSTALL=PASS:CORE_CAPABILITY_INSTALLED"
  echo "AV_RESEARCH_RUNTIME=DOCTOR_REQUIRED"
  exit 0
fi

# Essentia is AGPL-3.0-only. Approval is explicit, separate from the
# permissive core: network-service implications need legal review.
[[ "${HAZEWAVE_ACCEPT_AGPL3:-}" == "yes" ]] || die "AGPL3_LICENSE_REVIEW_REQUIRED"
(( disk_free >= 8 * 1024 * 1024 )) || die "MUSIC_DISK_BELOW_8GIB"
(( ram_free >= 4 * 1024 * 1024 )) || die "MUSIC_RAM_BELOW_4GIB"
[[ -x "$VENV/bin/python" ]] || die "CORE_NOT_INSTALLED"
"$VENV/bin/python" -c 'import scenedetect, PIL, opentimelineio' || die "CORE_NOT_READY"
"$VENV/bin/python" -m pip install --no-input --disable-pip-version-check --no-cache-dir --only-binary=:all: \
  --report "$REPORTS/music-install.json" \
  "essentia==2.1b6.dev1389" "librosa==1.0.0" \
  || die "MUSIC_PACKAGE_INSTALL_FAILED"
"$VENV/bin/python" - <<'PY' || die "MUSIC_IMPORT_FAILED"
import essentia, librosa
print("AV_RESEARCH_ESSENTIA_VERSION=" + essentia.__version__)
print("AV_RESEARCH_LIBROSA_VERSION=" + librosa.__version__)
PY
echo "AV_RESEARCH_INSTALL=PASS:MUSIC_CAPABILITY_INSTALLED"
echo "AV_RESEARCH_RUNTIME=REFERENCE_CASE_REQUIRED"
