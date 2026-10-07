#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

SHELLS_FILE="${HAZEWAVE_PROJECT_SHELLS_FILE:-$HOME/.config/project-shells.sh}"
BACKUP_FILE="${SHELLS_FILE}.pre-hazewave-always-ready-v1"
CONTROLLER="$HOME/.local/bin/hazewave-reflex"
MARKER_BEGIN="# HAZEWAVE_ALWAYS_READY_V1_BEGIN"
MARKER_END="# HAZEWAVE_ALWAYS_READY_V1_END"
ANCHOR='  bash scripts/hazewave_termux_control.sh doctor'

[[ "${PREFIX:-}" == */com.termux/files/usr ]] || {
  echo "HAZEWAVE_ALWAYS_READY_TERMUX_INSTALL=FAIL:not_termux" >&2
  exit 20
}
[[ -f "$SHELLS_FILE" ]] || {
  echo "HAZEWAVE_ALWAYS_READY_TERMUX_INSTALL=FAIL:project_shells_missing" >&2
  exit 21
}
[[ -x "$CONTROLLER" ]] || {
  echo "HAZEWAVE_ALWAYS_READY_TERMUX_INSTALL=FAIL:reflex_controller_missing" >&2
  exit 22
}

if grep -Fq "$MARKER_BEGIN" "$SHELLS_FILE"; then
  grep -Fq "$MARKER_END" "$SHELLS_FILE" || {
    echo "HAZEWAVE_ALWAYS_READY_TERMUX_INSTALL=FAIL:marker_incomplete" >&2
    exit 23
  }
  echo "HAZEWAVE_ALWAYS_READY_TERMUX_INSTALL=ALREADY_INSTALLED"
  exit 0
fi

[[ ! -e "$BACKUP_FILE" ]] && cp -p "$SHELLS_FILE" "$BACKUP_FILE"

tmp="$(mktemp "${SHELLS_FILE}.tmp.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

python - "$SHELLS_FILE" "$tmp" "$ANCHOR" "$MARKER_BEGIN" "$MARKER_END" <<'PY'
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
anchor = sys.argv[3]
begin = sys.argv[4]
end = sys.argv[5]
text = src.read_text(encoding="utf-8")
if text.count(anchor) != 1:
    raise SystemExit("HAZEWAVE_ALWAYS_READY_TERMUX_INSTALL=FAIL:doctor_anchor_not_unique")
block = """{anchor}
  {begin}
  if command -v hazewave-reflex >/dev/null 2>&1; then
    hazewave-reflex ready || echo "HAZEWAVE_REMOTE_READY=FAIL"
  else
    echo "HAZEWAVE_REMOTE_READY=FAIL:controller_missing"
  fi
  {end}""".format(anchor=anchor, begin=begin, end=end)
dst.write_text(text.replace(anchor, block, 1), encoding="utf-8")
PY

bash -n "$tmp" || {
  echo "HAZEWAVE_ALWAYS_READY_TERMUX_INSTALL=FAIL:patched_shell_syntax" >&2
  exit 24
}

chmod --reference="$SHELLS_FILE" "$tmp" 2>/dev/null || chmod 600 "$tmp"
mv "$tmp" "$SHELLS_FILE"
trap - EXIT

echo "HAZEWAVE_ALWAYS_READY_TERMUX_INSTALL=PASS"
echo "HAZEWAVE_ALWAYS_READY_TERMUX_SHELLS=$SHELLS_FILE"
echo "HAZEWAVE_ALWAYS_READY_TERMUX_BACKUP=$BACKUP_FILE"
echo "HAZEWAVE_ENTRYPOINT=hazewave"
