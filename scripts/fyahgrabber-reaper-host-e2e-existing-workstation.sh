#!/usr/bin/env bash
# Only existing Hazewave Codespace. Isolated REAPER 7.82 instance, synthetic test WAV.
# No actions against an already-running REAPER session. No A15 CPU processing.
set -Eeuo pipefail
TARGET="hazewave-zero-cost-4jxp45676rq6279xx"
REAPER="/home/vscode/.local/opt/reaper/7.82/REAPER/reaper"
REPO="/workspaces/Hazewave-"
ROOT="$HOME/.local/share/hazewave/fyahgrabber-open"
BRANCH="work/fyahgrabber-reaper-native-v1"
if [[ -n "$${CODESPACE_NAME:-}" && "$CODESPACE_NAME" != "$TARGET" ]]; then
  echo "BLOCKED:WRONG_CODESPACE";exit 2
fi
[[ -x "$REAPER" ]] || { echo "BLOCKED:REAPER_NOT_INSTALLED";exit 2; }
[[ -d "$REPO/.git" || -f "$REPO/.git" ]] || {
  echo "BLOCKED:REPO_NOT_AT_EXPECTED_PATH";exit 2;
}
srcsha="$(git -C "$REPO" ls-remote origin "refs/heads/$BRANCH" | awk 'NR==1{print $1}')"
[[ "$srcsha" =~ ^[a-f0-9]{40}$ ]] || { echo "BLOCKED:SOURCE_REF_MISSING";exit 2; }
scripts="$HOME/.config/REAPER/Scripts/FyahGrabber-${srcsha:0:12}"
test_script="$scripts/FyahGrabber_Disposable_Host_E2E.lua"
[[ -s "$test_script" ]] || {
  echo "BLOCKED:EXACT_REVISION_NOT_INSTALLED:$srcsha";exit 3;
}
[[ -f "$HOME/.config/REAPER/Effects/FyahGrabber_808.jsfx" ]] || {
  echo "BLOCKED:808_JSFX_NOT_PRESENT";exit 3;
}
[[ -d "$ROOT" && ! -L "$ROOT" ]] || { echo "BLOCKED:INSTALL_ROOT_MISSING";exit 3; }
# Locate DISPLAY only from the current existing REAPER user session, when present.
if [[ -z "${DISPLAY:-}" ]]; then
  while IFS= read -r pid; do
    [[ -r "/proc/$pid/environ" ]] || continue
    display="$(tr '\0' '\n' <"/proc/$pid/environ" | sed -n 's/^DISPLAY=//p' | head -n1)"
    if [[ -n "$display" ]]; then export DISPLAY="$display";break;fi
  done < <(pgrep -u "$(id -u)" -x reaper || true)
fi
[[ -n "${DISPLAY:-}" ]] || {
  echo "BLOCKED:NO_XPRA_DISPLAY:OPEN_A_TERMINAL_IN_EXISTING_XPRA_SESSION";exit 3;
}
if command -v xdpyinfo >/dev/null 2>&1; then
  xdpyinfo -display "$DISPLAY" >/dev/null 2>&1 || {
    echo "BLOCKED:XPRA_DISPLAY_UNREACHABLE";exit 3;
  }
fi
proofbase="$HOME/.local/state/hazewave/fyahgrabber/proofs"
mkdir -p "$proofbase"
[[ ! -L "$proofbase" ]] || { echo "BLOCKED:PROOFS_ROOT_SYMLINK";exit 3; }
proofdir="$(mktemp -d "$proofbase/reaper-host-XXXXXXXX")"
chmod 700 "$proofdir"
headbefore="$(git -C "$REPO" rev-parse HEAD)"
statusbefore="$(git -C "$REPO" status --porcelain=v1)"
echo "FYAH_E2E_PROOF_DIR=$proofdir"
echo "FYAH_SELECTED_DISPLAY=$DISPLAY"
echo "FYAH_HOST_SOURCE_SHA=$srcsha"
echo "FYAH_REAPER_INSTANCE_ISOLATION=-newinst -new -noactivate"
# REAPER CLI supports script.lua directly on startup; timeout terminates ONLY
# the isolated process it starts. Never send command to an existing instance.
set +e
FYAH_E2E_ISOLATED=1 FYAH_E2E_DIR="$proofdir" \
  timeout --signal=TERM --kill-after=3s 35s \
  "$REAPER" -nosplash -newinst -new -noactivate "$test_script" \
  >"$proofdir/reaper-stdout.log" 2>"$proofdir/reaper-stderr.log"
exit_code=$?
set -e
echo "FYAH_REAPER_EXIT_CODE=$exit_code"
proof="$proofdir/reaper-host-proof.json"
[[ -s "$proof" ]] || {
  echo "BLOCKED:REAPER_DID_NOT_WRITE_EVIDENCE"
  tail -n 30 "$proofdir/reaper-stderr.log" || true
  exit 5
}
python3 - "$proof" "$proofdir" <<'PY'
from pathlib import Path
import hashlib
import json
import sys
p=Path(sys.argv[1])
base=Path(sys.argv[2])
d=json.loads(p.read_text())
print("FYAH_REAPER_API_TEST_STATUS="+str(d.get("status")))
print("FYAH_REAPER_VERSION="+str(d.get("reaper_version")))
print("FYAH_REAPER_API_ELAPSED_SECONDS="+str(d.get("api_elapsed_seconds")))
print("FYAH_HUMAN_3_NOTES_UNDER_10S="+str(d.get("human_paint_under_10_seconds")))
print("FYAH_TEST_DETAILS="+str(d.get("detail")))
for f in sorted(base.iterdir()):
    if f.is_file():
        print("FYAH_FILE_SHA256", hashlib.sha256(f.read_bytes()).hexdigest(), f.name)
assert d["status"]=="PASS", "FYAH_REAL_HOST_E2E_FAILED"
assert d["three_notes_verified"] is True
assert d["jsfx_808_present"] is True
assert (base/"selected-pre-fx.wav").stat().st_size == 32044
print("FYAH_REAL_REAPER_HOST_E2E=PASS")
PY
headafter="$(git -C "$REPO" rev-parse HEAD)"
statusafter="$(git -C "$REPO" status --porcelain=v1)"
[[ "$headbefore" == "$headafter" ]] && [[ "$statusbefore" == "$statusafter" ]] || {
  echo "BLOCKED:REAPER_TEST_MUTATED_REPOSITORY";exit 7;
}
echo "FYAH_WORKSTATION_WIP_UNCHANGED=PASS"
