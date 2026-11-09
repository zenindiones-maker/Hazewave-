#!/usr/bin/env bash
# Instala o pacote Hazewave Separar Stems no REAPER do usuário (Linux/macOS/Windows via Git Bash).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
REAPER_RESOURCE="${REAPER_RESOURCE:-${HOME}/.config/REAPER}"
case "$(uname -s)" in
  Darwin) REAPER_RESOURCE="${REAPER_RESOURCE:-${HOME}/Library/Application Support/REAPER}" ;;
  MINGW*|MSYS*|CYGWIN*|Windows*) REAPER_RESOURCE="${REAPER_RESOURCE:-${APPDATA}/REAPER}" ;;
esac
DEST="${REAPER_RESOURCE}/Scripts/Hazewave/Stems"
mkdir -p "$DEST" "${REAPER_RESOURCE}/Data/toolbar_icons" \
  "${REAPER_RESOURCE}/Data/toolbar_icons/150" "${REAPER_RESOURCE}/Data/toolbar_icons/200"
cp -f "$ROOT/Hazewave_Separar_Stems.lua" "$ROOT/hazewave_stems_worker.py" "$ROOT/register_stems.lua" "$DEST/"
# Icons (optional; generate if Pillow present)
ICONS_PY="$(dirname "$ROOT")/make_icons.py"
if command -v python3 >/dev/null && python3 -c 'import PIL' 2>/dev/null; then
  python3 "$ICONS_PY" "$REAPER_RESOURCE" || true
fi
# Python venv with demucs (prefer 3.12 for torch wheels)
VENV="${HOME}/.local/share/hazewave/stems-venv"
PY=python3
command -v python3.12 >/dev/null && PY=python3.12
if ! "$PY" -c 'import venv' 2>/dev/null; then
  echo "Instale o pacote venv do Python (ex.: sudo apt install python3.12-venv)" >&2
  exit 1
fi
"$PY" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -U pip wheel
pip install torch --index-url https://download.pytorch.org/whl/cpu || pip install torch
pip install 'demucs>=4.0.1,<5' soundfile numpy
python -c 'import demucs; print("demucs_ok")'
deactivate
# Startup hook: register on launch
STARTUP="${REAPER_RESOURCE}/Scripts/__startup.lua"
HOOK='dofile(reaper.GetResourcePath().."/Scripts/Hazewave/Stems/register_stems.lua")'
mkdir -p "$(dirname "$STARTUP")"
if [[ ! -f "$STARTUP" ]]; then
  printf '%s\n' "-- Hazewave startup" "$HOOK" >"$STARTUP"
elif ! grep -q 'Hazewave/Stems/register_stems.lua' "$STARTUP"; then
  printf '\n%s\n' "$HOOK" >>"$STARTUP"
fi
echo "HAZEWAVE_STEMS_INSTALL=PASS"
echo "HAZEWAVE_STEMS_DEST=$DEST"
echo "HAZEWAVE_STEMS_VENV=$VENV"
echo "Abra o REAPER uma vez (Actions → load register_stems.lua se o botão não aparecer)."
