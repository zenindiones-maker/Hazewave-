#!/usr/bin/env bash
# Install only in the existing Hazewave Codespace. Never switch the active checkout.
set -Eeuo pipefail
REPO="/workspaces/Hazewave-"
EXPECTED_CODESPACE="hazewave-zero-cost-4jxp45676rq6279xx"
REAPER="/home/vscode/.local/opt/reaper/7.82/REAPER/reaper"
BRANCH="work/fyahgrabber-reaper-native-v1"
ROOT="${HOME}/.local/share/hazewave/fyahgrabber-open"
RESOURCE="${REAPER_RESOURCE:-${HOME}/.config/REAPER}"
PYTHON="${ROOT}/.venv/bin/python"
WITH_CQT=false
if [[ "${1:-}" == "--with-cqt" ]]; then WITH_CQT=true; elif [[ $# -ne 0 ]]; then
  echo "Usage: $0 [--with-cqt]" >&2; exit 2
fi
if [[ -n "${CODESPACE_NAME:-}" && "$CODESPACE_NAME" != "$EXPECTED_CODESPACE" ]]; then
  echo "BLOCKED:NOT_APPROVED_HAZEWAVE_CODESPACE";exit 3
fi
if [[ ! -d "$REPO/.git" ]] && [[ ! -f "$REPO/.git" ]]; then
  echo "BLOCKED:WORKSPACE_NOT_FOUND";exit 3
fi
if [[ ! -x "$REAPER" ]]; then
  echo "BLOCKED:EXISTING_REAPER_7_82_NOT_FOUND";exit 3
fi
if [[ ! -d "$RESOURCE" || -L "$RESOURCE" ]]; then
  echo "BLOCKED:REAPER_RESOURCE_PATH_INVALID";exit 3
fi
if [[ -L "$ROOT" ]]; then
  echo "BLOCKED:INSTALL_ROOT_SYMLINK";exit 3
fi
if [[ -e "$RESOURCE/Effects/FyahGrabber_808.jsfx" ]]; then
  echo "BLOCKED:EXISTING_JSFX_PRESERVE_DO_NOT_OVERWRITE";exit 4
fi
before_head="$(git -C "$REPO" rev-parse HEAD)"
before_status="$(git -C "$REPO" status --porcelain=v1)"
echo "HAZE_EXISTING_HEAD=$before_head"
echo "HAZE_WORKTREE_DIRTY=$([[ -z "$before_status" ]] && echo false || echo true)"
git -C "$REPO" fetch --no-tags origin "refs/heads/$BRANCH"
source_sha="$(git -C "$REPO" rev-parse FETCH_HEAD)"
if [[ ! "$source_sha" =~ ^[a-f0-9]{40}$ ]]; then
  echo "BLOCKED:INVALID_FETCHED_SHA";exit 3
fi
if [[ -e "$ROOT/source-$source_sha" ]]; then
  echo "BLOCKED:ALREADY_INSTALLED_SOURCE_PRESERVED";exit 4
fi
mkdir -p "$ROOT" "$RESOURCE/Scripts" "$RESOURCE/Effects"
staged="$(mktemp -d "$ROOT/.stage.XXXXXXXX")"
trap 'rm -rf "$staged"' EXIT
git -C "$REPO" archive "$source_sha" reaper/FyahGrabber | tar -xf - -C "$staged"
files="$staged/reaper/FyahGrabber"
for f in FyahGrabber_Analyze_Selected_Item.lua FyahGrabber_Core.lua \
  FyahGrabber_AudioExport.lua FyahGrabber_Live_Proof_3_Notes.lua \
  FyahGrabber_808.jsfx fyahgrabber_analyze.py; do
  [[ -s "$files/$f" ]] || { echo "BLOCKED:MISSING:$f";exit 3; }
done
source_dir="$ROOT/source-$source_sha"
mkdir -p "$source_dir"
cp -R "$staged/reaper" "$source_dir/"
scripts_target="$RESOURCE/Scripts/FyahGrabber-${source_sha:0:12}"
if [[ -e "$scripts_target" ]]; then
  echo "BLOCKED:VERSION_DIRECTORY_EXISTS";exit 4
fi
mkdir "$scripts_target"
cp "$files/"*.lua "$files/"*.py "$scripts_target/"
install -m 0644 "$files/FyahGrabber_808.jsfx" "$RESOURCE/Effects/FyahGrabber_808.jsfx"
if [[ "$WITH_CQT" == true ]]; then
  if [[ ! -x "$PYTHON" ]]; then python3 -m venv "$ROOT/.venv"; fi
  "$PYTHON" -m pip install --disable-pip-version-check --no-input \
    'librosa==0.11.0' 'pillow==11.3.0'
  "$PYTHON" -c 'import librosa, PIL, soundfile, numpy;print("CQT_IMPORT_PASS")'
fi
after_head="$(git -C "$REPO" rev-parse HEAD)"
after_status="$(git -C "$REPO" status --porcelain=v1)"
[[ "$before_head" == "$after_head" ]] || { echo "BLOCKED:MAIN_WORKTREE_HEAD_CHANGED";exit 7; }
[[ "$before_status" == "$after_status" ]] || { echo "BLOCKED:MAIN_WORKTREE_WIP_CHANGED";exit 7; }
cat <<RECEIPT
FYAH_WORKSTATION_INSTALL=PASS
FYAH_EXISTING_CODESPACE=$EXPECTED_CODESPACE
FYAH_INSTALLED_SOURCE_SHA=$source_sha
FYAH_REAPER_BINARY=$REAPER
FYAH_REASCRIPT=$scripts_target/FyahGrabber_Analyze_Selected_Item.lua
FYAH_LIVE_PROOF_SCRIPT=$scripts_target/FyahGrabber_Live_Proof_3_Notes.lua
FYAH_808_JSFX=$RESOURCE/Effects/FyahGrabber_808.jsfx
FYAH_PYTHON=$PYTHON
FYAH_CQT_INSTALLED=$WITH_CQT
FYAH_REAPER_LIVE_PROOF=NOT_RUN
FYAH_HUMAN_3_NOTES_UNDER_10_SECONDS=NOT_RUN
RECEIPT
