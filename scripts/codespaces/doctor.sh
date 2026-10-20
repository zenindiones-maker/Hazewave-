#!/usr/bin/env bash
set -euo pipefail

required=(ffmpeg sox websockify vncserver)
for cmd in "${required[@]}"; do
  command -v "${cmd}" >/dev/null 2>&1 || {
    echo "MISSING_COMMAND=${cmd}"
    exit 20
  }
done

ARDOUR_BIN=""
for candidate in ardour8 ardour7 ardour6 ardour; do
  if command -v "${candidate}" >/dev/null 2>&1; then
    ARDOUR_BIN="$(command -v "${candidate}")"
    break
  fi
done

[[ -n "${ARDOUR_BIN}" ]] || {
  echo "ARDOUR=FAIL"
  exit 21
}

curl -fsS http://127.0.0.1:6080/vnc.html >/dev/null || {
  echo "NOVNC=FAIL"
  exit 22
}

echo "HAZEWAVE_CODESPACE=PASS"
echo "ARDOUR=PASS"
echo "NOVNC=PASS"
echo "PAID_FALLBACK=FALSE"
echo "REFERENCE_QC=LOCAL_A15"
