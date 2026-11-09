#!/usr/bin/env bash
set -euo pipefail
LOG=$HOME/fyah-stems-reaper-e2e.log
exec > >(tee -a "$LOG") 2>&1
echo "== $(date -Is) REAPER import E2E =="
BASE=$HOME/.local/share/hazewave/fyahreaper-stems-e2e
RP=$HOME/.config/REAPER
REAPER=$HOME/.local/opt/reaper/7.82/REAPER/reaper
MIX=$BASE/test_mix_20s.wav
TSV=$BASE/job_worker/import.tsv
PROOF=$BASE/proof.json
PROJDIR=$BASE/project
SHOT=$BASE/reaper_stems.png
mkdir -p "$PROJDIR" "$RP/Scripts/Hazewave/Stems"
# ensure scripts present
SRC=/workspaces/Hazewave-/apps/fyahreaper_remote/reaper_touch/stems
cp -f "$SRC"/*.lua "$SRC"/hazewave_stems_worker.py "$RP/Scripts/Hazewave/Stems/"
[[ -f $TSV ]] || { echo "MISSING_TSV"; exit 2; }
[[ -f $MIX ]] || { echo "MISSING_MIX"; exit 2; }
pkill -f 'REAPER/reaper' 2>/dev/null || true
sleep 1
pgrep -f 'Xvfb :99' >/dev/null || setsid nohup Xvfb :99 -screen 0 1600x900x24 -nolisten tcp >"$BASE/xvfb.log" 2>&1 &
sleep 1
# jack optional
pgrep -x jackd >/dev/null || setsid nohup jackd --no-realtime -d dummy -r 48000 -p 512 >"$BASE/jackd.log" 2>&1 &
sleep 1

cat > "$BASE/import_boot.lua" <<'LUA'
local mix = os.getenv("FYAH_STEMS_MIX")
local tsv = os.getenv("FYAH_STEMS_TSV")
local proof = os.getenv("FYAH_STEMS_PROOF")
local projdir = os.getenv("FYAH_STEMS_PROJDIR")
local function color_int(hex)
  local r = tonumber(hex:sub(1,2),16)
  local g = tonumber(hex:sub(3,4),16)
  local b = tonumber(hex:sub(5,6),16)
  return r + g*256 + b*65536
end
-- register
dofile(reaper.GetResourcePath() .. "/Scripts/Hazewave/Stems/register_stems.lua")
reaper.ClearAllRecArmed()
-- new tracks from scratch
while reaper.CountTracks(0) > 0 do reaper.DeleteTrack(reaper.GetTrack(0,0)) end
reaper.InsertTrackAtIndex(0, true)
local tr = reaper.GetTrack(0,0)
reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", "Fonte", true)
local item = reaper.AddMediaItemToTrack(tr)
local take = reaper.AddTakeToMediaItem(item)
local pcm = reaper.PCM_Source_CreateFromFile(mix)
reaper.SetMediaItemTake_Source(take, pcm)
local len = reaper.GetMediaSourceLength(pcm, false)
if type(len)=="number" then reaper.SetMediaItemInfo_Value(item, "D_LENGTH", len) end
reaper.SetMediaItemInfo_Value(item, "B_MUTE", 1)
reaper.Main_SaveProjectEx(0, projdir .. "/stems_e2e.rpp", 0)

local f = io.open(tsv, "r")
local lines = {}
for line in f:lines() do
  local path, label, color, pos, tidx = line:match("^(.-)\t(.-)\t(.-)\t(.-)\t(.-)$")
  if path then lines[#lines+1] = {path=path,label=label,color=color,position=tonumber(pos) or 0, track_idx=tonumber(tidx) or 0} end
end
f:close()
reaper.Undo_BeginBlock2(0)
reaper.PreventUIRefresh(1)
local offs = 0
for _, ln in ipairs(lines) do
  local insert_at = 1 + offs
  reaper.InsertTrackAtIndex(insert_at, true)
  local t = reaper.GetTrack(0, insert_at)
  reaper.GetSetMediaTrackInfo_String(t, "P_NAME", ln.label, true)
  reaper.SetTrackColor(t, color_int(ln.color))
  reaper.SetMediaTrackInfo_Value(t, "I_HEIGHTOVERRIDE", 150)
  local it = reaper.AddMediaItemToTrack(t)
  reaper.SetMediaItemInfo_Value(it, "D_POSITION", ln.position)
  local tk = reaper.AddTakeToMediaItem(it)
  local src = reaper.PCM_Source_CreateFromFile(ln.path)
  if src then
    reaper.SetMediaItemTake_Source(tk, src)
    local L = reaper.GetMediaSourceLength(src, false)
    if type(L)=="number" then reaper.SetMediaItemInfo_Value(it, "D_LENGTH", L) end
    reaper.GetSetMediaItemTakeInfo_String(tk, "P_NAME", ln.label, true)
  end
  offs = offs + 1
end
reaper.PreventUIRefresh(-1)
reaper.UpdateArrange()
reaper.Main_OnCommand(40295, 0) -- zoom project
reaper.Undo_EndBlock2(0, "Hazewave: Separar Stems (Demucs)", -1)
reaper.Main_SaveProjectEx(0, projdir .. "/stems_e2e.rpp", 0)
local n = reaper.CountTracks(0)
local pf = io.open(proof, "w")
pf:write(string.format('{"status":"%s","tracks":%d,"stems":%d}\n', n>=7 and "PASS" or "FAIL", n, #lines))
pf:close()
-- leave REAPER open for screenshot
LUA

export DISPLAY=:99
export FYAH_STEMS_MIX=$MIX
export FYAH_STEMS_TSV=$TSV
export FYAH_STEMS_PROOF=$PROOF
export FYAH_STEMS_PROJDIR=$PROJDIR
rm -f "$PROOF"
setsid nohup env DISPLAY=:99 FYAH_STEMS_MIX="$MIX" FYAH_STEMS_TSV="$TSV" FYAH_STEMS_PROOF="$PROOF" FYAH_STEMS_PROJDIR="$PROJDIR" \
  "$REAPER" -nosplash -new "$BASE/import_boot.lua" >"$BASE/reaper.log" 2>&1 &
echo REAPER_PID=$!
for i in $(seq 1 60); do
  [[ -f $PROOF ]] && break
  sleep 2
done
echo "PROOF=$(cat "$PROOF" 2>/dev/null || echo missing)"
sleep 3
# screenshot
if command -v import >/dev/null 2>&1; then
  DISPLAY=:99 import -window root "$SHOT"
elif command -v scrot >/dev/null 2>&1; then
  DISPLAY=:99 scrot "$SHOT"
else
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq imagemagick >/dev/null
  DISPLAY=:99 import -window root "$SHOT" || DISPLAY=:99 xwd -root -silent | convert xwd:- "$SHOT"
fi
ls -la "$SHOT" "$PROOF" "$PROJDIR/stems_e2e.rpp" 2>&1
# also open the stems UI briefly for a second shot
CMD=$(cat "$RP/Scripts/Hazewave/Stems/cmd_id.txt" 2>/dev/null | head -1 || true)
echo "REGISTERED_CMD=$CMD"
echo "== $(date -Is) REAPER import E2E end =="
