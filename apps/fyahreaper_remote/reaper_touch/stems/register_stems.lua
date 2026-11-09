-- One-shot: register Hazewave Separar Stems and persist command id for ReaHub / toolbar.
local INFO = debug.getinfo(1, "S")
local HERE = INFO and INFO.source and INFO.source:match("^@(.+[\\/])") or ""
local script = HERE .. "Hazewave_Separar_Stems.lua"
if not reaper.file_exists(script) then
  reaper.ShowConsoleMsg("Hazewave stems: script missing: " .. script .. "\n")
  return
end
local cmd = reaper.AddRemoveReaScript(true, 0, script, true)
if not cmd or cmd == 0 then
  reaper.ShowConsoleMsg("Hazewave stems: AddRemoveReaScript failed\n")
  return
end
reaper.SetExtState("HazewaveStems", "cmd_id", tostring(cmd), true)
local named = ""
if reaper.ReverseNamedCommandLookup then
  named = reaper.ReverseNamedCommandLookup(cmd) or ""
  if named ~= "" then reaper.SetExtState("HazewaveStems", "named_cmd", named, true) end
end
local side = HERE .. "cmd_id.txt"
local sf = io.open(side, "w")
if sf then sf:write(tostring(cmd) .. "\n" .. tostring(named) .. "\n"); sf:close() end
reaper.ShowConsoleMsg(string.format("Hazewave stems registered cmd=%s named=%s\n", tostring(cmd), tostring(named)))
