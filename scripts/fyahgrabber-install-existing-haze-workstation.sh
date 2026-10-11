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
before_head="$(git -C "$REPO" rev-parse HEAD)"
before_status="$(git -C "$REPO" status --porcelain=v1)"
echo "HAZE_EXISTING_HEAD=$before_head"
echo "HAZE_WORKTREE_DIRTY=$([[ -z "$before_status" ]] && echo false || echo true)"
expected_source_sha="26868b4bbce8fce372159332a09ceffc882f6ef2"
git -C "$REPO" cat-file -e "${expected_source_sha}^{commit}" || { echo "BLOCKED:PINNED_SOURCE_NOT_LOCAL"; exit 3; }
source_sha="$(git -C "$REPO" rev-parse "${expected_source_sha}^{commit}")"
[[ "$source_sha" == "$expected_source_sha" ]] || { echo "BLOCKED:PINNED_SOURCE_MISMATCH"; exit 3; }
if [[ ! "$source_sha" =~ ^[a-f0-9]{40}$ ]]; then
  echo "BLOCKED:INVALID_FETCHED_SHA";exit 3
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
scripts_target="$RESOURCE/Scripts/FyahGrabber-${source_sha:0:12}"
fx_target="$RESOURCE/Effects/FyahGrabber_808.jsfx"
# Validate all existing files; NEVER overwrite conflicting user state.
if [[ -e "$fx_target" || -L "$fx_target" ]]; then
  [[ ! -L "$fx_target" ]] && cmp -s "$files/FyahGrabber_808.jsfx" "$fx_target" || {
    echo "BLOCKED:CONFLICTING_JSFX_PRESERVED";exit 4;
  }
fi
if [[ -e "$scripts_target" || -L "$scripts_target" ]]; then
  [[ -d "$scripts_target" && ! -L "$scripts_target" ]] || {
    echo "BLOCKED:CONFLICTING_SCRIPTS_TARGET";exit 4;
  }
  for existing in "$files/"*.lua "$files/"*.py; do
    [[ -f "$scripts_target/$(basename "$existing")" ]] &&
      cmp -s "$existing" "$scripts_target/$(basename "$existing")" || {
      echo "BLOCKED:CONFLICTING_SCRIPT_VERSION";exit 4;
    }
  done
fi
if [[ -e "$source_dir" || -L "$source_dir" ]]; then
  [[ -d "$source_dir" && ! -L "$source_dir" ]] || {
    echo "BLOCKED:CONFLICTING_SOURCE_PATH";exit 4;
  }
  for existing in "$files/"*; do
    [[ -f "$source_dir/reaper/FyahGrabber/$(basename "$existing")" ]] &&
      cmp -s "$existing" "$source_dir/reaper/FyahGrabber/$(basename "$existing")" || {
      echo "BLOCKED:CHANGED_SOURCE_VERSION";exit 4;
    }
  done
fi
# Dependencies first: retry-safe, no half-installed JSFX if pip fails.
if [[ "$WITH_CQT" == true ]]; then
  if [[ ! -x "$PYTHON" ]]; then python3 -m venv "$ROOT/.venv"; fi
  "$PYTHON" -m pip install --disable-pip-version-check --no-input \
    'librosa==0.11.0' 'pillow==11.3.0'
  "$PYTHON" -c 'import librosa, PIL, soundfile, numpy;print("CQT_IMPORT_PASS")'
fi
if [[ ! -e "$source_dir" ]]; then
  mkdir "$source_dir"
  cp -R "$staged/reaper" "$source_dir/"
fi
if [[ ! -e "$scripts_target" ]]; then
  mkdir "$scripts_target"
  cp "$files/"*.lua "$files/"*.py "$scripts_target/"
fi
if [[ ! -e "$fx_target" ]]; then
  install -m 0644 "$files/FyahGrabber_808.jsfx" "$fx_target"
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
