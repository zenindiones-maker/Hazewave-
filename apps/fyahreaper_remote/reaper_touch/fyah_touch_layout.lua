-- Fyah touch layout (test REAPER): big toolbar docked at top of main window, main toolbar box closed, mixer hidden, tall tracks.
local function on(id, want) if reaper.GetToggleCommandState(id) ~= want then reaper.Main_OnCommand(id, 0) end end
on(40078, 0)
for i = 0, reaper.CountTracks(0) - 1 do
  local t = reaper.GetTrack(0, i)
  if reaper.GetMediaTrackInfo_Value(t, "I_HEIGHTOVERRIDE") < 150 then reaper.SetMediaTrackInfo_Value(t, "I_HEIGHTOVERRIDE", 150) end
end
reaper.TrackList_AdjustWindows(false); reaper.UpdateArrange()
