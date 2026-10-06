-- Hazewave project-owned REAPER bridge.
-- Authority remains HAZEWAVE_HARNESS; this script is a bounded subordinate executor.
-- IPC is local filesystem only. No network listener and no dynamic source execution.

local BRIDGE_SCHEMA = "HazewaveReaperBridge/v1"
local REQUEST_SCHEMA = "ReaperExecutionRequest/v1"
local RESPONSE_SCHEMA = "ReaperExecutionResponse/v1"
local HEARTBEAT_SCHEMA = "ReaperBridgeHeartbeat/v1"

local bridge_root = os.getenv("HAZEWAVE_REAPER_BRIDGE_DIR")
if bridge_root == nil or bridge_root == "" then
  local home = os.getenv("HOME") or ""
  bridge_root = home .. "/.local/state/hazewave/reaper-bridge"
end

local requests_dir = bridge_root .. "/requests"
local processing_dir = bridge_root .. "/processing"
local responses_dir = bridge_root .. "/responses"
local checkpoint_root = bridge_root .. "/checkpoints"
local render_root = bridge_root .. "/artifacts"
local fixture_root = bridge_root .. "/fixtures"
local heartbeat_path = bridge_root .. "/heartbeat.json"

reaper.RecursiveCreateDirectory(requests_dir, 0)
reaper.RecursiveCreateDirectory(processing_dir, 0)
reaper.RecursiveCreateDirectory(responses_dir, 0)
reaper.RecursiveCreateDirectory(checkpoint_root, 0)
reaper.RecursiveCreateDirectory(render_root, 0)
reaper.RecursiveCreateDirectory(fixture_root, 0)

local ARRAY_MT = {}
local JSON_NULL = {}
local fixture_session = nil

local function array(values)
  return setmetatable(values or {}, ARRAY_MT)
end

local function is_array(value)
  return getmetatable(value) == ARRAY_MT
end

local function utc_now()
  return os.date("!%Y-%m-%dT%H:%M:%SZ")
end

local function json_escape(value)
  local s = tostring(value)
  s = s:gsub("\\", "\\\\")
  s = s:gsub('"', '\\"')
  s = s:gsub("\b", "\\b")
  s = s:gsub("\f", "\\f")
  s = s:gsub("\n", "\\n")
  s = s:gsub("\r", "\\r")
  s = s:gsub("\t", "\\t")
  return '"' .. s .. '"'
end

local function json_encode(value)
  local kind = type(value)
  if value == JSON_NULL then
    return "null"
  elseif kind == "nil" then
    return "null"
  elseif kind == "boolean" then
    return value and "true" or "false"
  elseif kind == "number" then
    if value ~= value or value == math.huge or value == -math.huge then
      error("JSON_NONFINITE_NUMBER")
    end
    return string.format("%.17g", value)
  elseif kind == "string" then
    return json_escape(value)
  elseif kind == "table" then
    local parts = {}
    if is_array(value) then
      for i = 1, #value do
        parts[#parts + 1] = json_encode(value[i])
      end
      return "[" .. table.concat(parts, ",") .. "]"
    end
    local keys = {}
    for key, _ in pairs(value) do
      if type(key) ~= "string" then
        error("JSON_OBJECT_KEY_NOT_STRING")
      end
      keys[#keys + 1] = key
    end
    table.sort(keys)
    for _, key in ipairs(keys) do
      parts[#parts + 1] = json_escape(key) .. ":" .. json_encode(value[key])
    end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  error("JSON_UNSUPPORTED_TYPE:" .. kind)
end

local function json_decode(text)
  local pos = 1
  local len = #text

  local function skip_ws()
    while pos <= len do
      local c = text:sub(pos, pos)
      if c == " " or c == "\n" or c == "\r" or c == "\t" then
        pos = pos + 1
      else
        break
      end
    end
  end

  local parse_value

  local function parse_string()
    if text:sub(pos, pos) ~= '"' then error("JSON_EXPECTED_STRING") end
    pos = pos + 1
    local out = {}
    while pos <= len do
      local c = text:sub(pos, pos)
      if c == '"' then
        pos = pos + 1
        return table.concat(out)
      end
      if c == "\\" then
        pos = pos + 1
        local esc = text:sub(pos, pos)
        local map = {
          ['"'] = '"', ['\\'] = '\\', ['/'] = '/',
          ['b'] = "\b", ['f'] = "\f", ['n'] = "\n",
          ['r'] = "\r", ['t'] = "\t",
        }
        if esc == "u" then
          local hex = text:sub(pos + 1, pos + 4)
          if not hex:match("^%x%x%x%x$") then error("JSON_BAD_UNICODE_ESCAPE") end
          local code = tonumber(hex, 16)
          if code < 0x80 then
            out[#out + 1] = string.char(code)
          elseif code < 0x800 then
            out[#out + 1] = string.char(
              0xC0 + math.floor(code / 64),
              0x80 + (code % 64)
            )
          else
            out[#out + 1] = string.char(
              0xE0 + math.floor(code / 4096),
              0x80 + (math.floor(code / 64) % 64),
              0x80 + (code % 64)
            )
          end
          pos = pos + 4
        elseif map[esc] ~= nil then
          out[#out + 1] = map[esc]
        else
          error("JSON_BAD_ESCAPE")
        end
      else
        out[#out + 1] = c
      end
      pos = pos + 1
    end
    error("JSON_UNTERMINATED_STRING")
  end

  local function parse_number()
    local start_pos = pos
    local c = text:sub(pos, pos)
    if c == "-" then pos = pos + 1 end
    while text:sub(pos, pos):match("%d") do pos = pos + 1 end
    if text:sub(pos, pos) == "." then
      pos = pos + 1
      while text:sub(pos, pos):match("%d") do pos = pos + 1 end
    end
    c = text:sub(pos, pos)
    if c == "e" or c == "E" then
      pos = pos + 1
      c = text:sub(pos, pos)
      if c == "+" or c == "-" then pos = pos + 1 end
      while text:sub(pos, pos):match("%d") do pos = pos + 1 end
    end
    local value = tonumber(text:sub(start_pos, pos - 1))
    if value == nil then error("JSON_BAD_NUMBER") end
    return value
  end

  local function parse_array()
    pos = pos + 1
    skip_ws()
    local result = array()
    if text:sub(pos, pos) == "]" then
      pos = pos + 1
      return result
    end
    while true do
      result[#result + 1] = parse_value()
      skip_ws()
      local c = text:sub(pos, pos)
      if c == "]" then
        pos = pos + 1
        return result
      end
      if c ~= "," then error("JSON_EXPECTED_ARRAY_SEPARATOR") end
      pos = pos + 1
      skip_ws()
    end
  end

  local function parse_object()
    pos = pos + 1
    skip_ws()
    local result = {}
    if text:sub(pos, pos) == "}" then
      pos = pos + 1
      return result
    end
    while true do
      skip_ws()
      local key = parse_string()
      skip_ws()
      if text:sub(pos, pos) ~= ":" then error("JSON_EXPECTED_COLON") end
      pos = pos + 1
      skip_ws()
      result[key] = parse_value()
      skip_ws()
      local c = text:sub(pos, pos)
      if c == "}" then
        pos = pos + 1
        return result
      end
      if c ~= "," then error("JSON_EXPECTED_OBJECT_SEPARATOR") end
      pos = pos + 1
      skip_ws()
    end
  end

  parse_value = function()
    skip_ws()
    local c = text:sub(pos, pos)
    if c == '"' then
      return parse_string()
    elseif c == "{" then
      return parse_object()
    elseif c == "[" then
      return parse_array()
    elseif c == "-" or c:match("%d") then
      return parse_number()
    elseif text:sub(pos, pos + 3) == "true" then
      pos = pos + 4
      return true
    elseif text:sub(pos, pos + 4) == "false" then
      pos = pos + 5
      return false
    elseif text:sub(pos, pos + 3) == "null" then
      pos = pos + 4
      return JSON_NULL
    end
    error("JSON_UNEXPECTED_TOKEN_AT:" .. tostring(pos))
  end

  local value = parse_value()
  skip_ws()
  if pos <= len then error("JSON_TRAILING_DATA") end
  return value
end

local function read_text(path)
  local handle, err = io.open(path, "rb")
  if not handle then return nil, err end
  local content = handle:read("*a")
  handle:close()
  return content, nil
end

local function atomic_write_json(path, payload)
  local tmp = path .. ".tmp." .. tostring(os.time()) .. "." .. tostring(math.random(100000, 999999))
  local handle, err = io.open(tmp, "wb")
  if not handle then return false, err end
  local ok, encoded = pcall(json_encode, payload)
  if not ok then
    handle:close()
    os.remove(tmp)
    return false, encoded
  end
  handle:write(encoded)
  handle:write("\n")
  handle:flush()
  handle:close()
  local renamed, rename_err = os.rename(tmp, path)
  if not renamed then
    os.remove(tmp)
    return false, rename_err
  end
  return true, nil
end

local function bool_value(value)
  return value ~= nil and value ~= false and value ~= 0
end

local function current_project()
  local proj, filename = reaper.EnumProjects(-1, "")
  if proj == nil then error("REAPER_PROJECT_UNAVAILABLE") end
  local identity = filename or ""
  if identity == "" then
    identity = "UNSAVED:" .. tostring(proj)
  end
  return proj, identity, filename or ""
end

local function track_guid(track)
  if track == nil then return "" end
  return reaper.GetTrackGUID(track) or ""
end

local function project_snapshot()
  local proj, identity, project_path = current_project()
  local _, numerator, denominator, tempo = reaper.TimeMap_GetTimeSigAtTime(proj, 0.0)
  if tempo == nil or tempo <= 0 then tempo = reaper.Master_GetTempo() end
  if numerator == nil or numerator <= 0 then numerator = 4 end
  if denominator == nil or denominator <= 0 then denominator = 4 end

  local snapshot = {
    schema = "ReaperProjectSnapshot/v1",
    project_identity = identity,
    project_path = project_path,
    project_state_change_count = reaper.GetProjectStateChangeCount(proj),
    dirty = reaper.IsProjectDirty(proj) ~= 0,
    sample_rate = math.floor(reaper.GetSetProjectInfo(proj, "PROJECT_SRATE", 0, false) + 0.5),
    tempo = tempo,
    time_signature = {numerator = numerator, denominator = denominator},
    project_length = reaper.GetProjectLength(proj),
    markers = array(),
    regions = array(),
    tracks = array(),
    items = array(),
    routing = array(),
    fx = array(),
  }

  local _, marker_count, region_count = reaper.CountProjectMarkers(proj)
  local total_markers = (marker_count or 0) + (region_count or 0)
  for i = 0, total_markers - 1 do
    local ok, is_region, position, region_end, name, mark_index, color =
      reaper.EnumProjectMarkers3(proj, i)
    if ok and ok ~= 0 then
      local entry = {
        id = mark_index,
        name = name or "",
        color = color or 0,
      }
      if is_region then
        entry.start = position
        entry["end"] = region_end
        snapshot.regions[#snapshot.regions + 1] = entry
      else
        entry.position = position
        snapshot.markers[#snapshot.markers + 1] = entry
      end
    end
  end

  local track_count = reaper.CountTracks(proj)
  for index = 0, track_count - 1 do
    local track = reaper.GetTrack(proj, index)
    local _, name = reaper.GetTrackName(track, "")
    snapshot.tracks[#snapshot.tracks + 1] = {
      guid = track_guid(track),
      name = name or "",
      index = index,
      volume = reaper.GetMediaTrackInfo_Value(track, "D_VOL"),
      pan = reaper.GetMediaTrackInfo_Value(track, "D_PAN"),
      width = reaper.GetMediaTrackInfo_Value(track, "D_WIDTH"),
      mute = bool_value(reaper.GetMediaTrackInfo_Value(track, "B_MUTE")),
      solo = reaper.GetMediaTrackInfo_Value(track, "I_SOLO") ~= 0,
      record_arm = bool_value(reaper.GetMediaTrackInfo_Value(track, "I_RECARM")),
      folder_depth = reaper.GetMediaTrackInfo_Value(track, "I_FOLDERDEPTH"),
      channel_count = reaper.GetMediaTrackInfo_Value(track, "I_NCHAN"),
    }

    local send_count = reaper.GetTrackNumSends(track, 0)
    for send_index = 0, send_count - 1 do
      local destination = reaper.GetTrackSendInfo_Value(track, 0, send_index, "P_DESTTRACK")
      snapshot.routing[#snapshot.routing + 1] = {
        relationship = "SEND",
        source_track_guid = track_guid(track),
        destination_track_guid = track_guid(destination),
        source_channels = reaper.GetTrackSendInfo_Value(track, 0, send_index, "I_SRCCHAN"),
        destination_channels = reaper.GetTrackSendInfo_Value(track, 0, send_index, "I_DSTCHAN"),
        gain = reaper.GetTrackSendInfo_Value(track, 0, send_index, "D_VOL"),
        pan = reaper.GetTrackSendInfo_Value(track, 0, send_index, "D_PAN"),
        mute = bool_value(reaper.GetTrackSendInfo_Value(track, 0, send_index, "B_MUTE")),
        mode = reaper.GetTrackSendInfo_Value(track, 0, send_index, "I_SENDMODE"),
      }
    end

    local receive_count = reaper.GetTrackNumSends(track, -1)
    for receive_index = 0, receive_count - 1 do
      local source = reaper.GetTrackSendInfo_Value(track, -1, receive_index, "P_SRCTRACK")
      snapshot.routing[#snapshot.routing + 1] = {
        relationship = "RECEIVE",
        source_track_guid = track_guid(source),
        destination_track_guid = track_guid(track),
        source_channels = reaper.GetTrackSendInfo_Value(track, -1, receive_index, "I_SRCCHAN"),
        destination_channels = reaper.GetTrackSendInfo_Value(track, -1, receive_index, "I_DSTCHAN"),
        gain = reaper.GetTrackSendInfo_Value(track, -1, receive_index, "D_VOL"),
        pan = reaper.GetTrackSendInfo_Value(track, -1, receive_index, "D_PAN"),
        mute = bool_value(reaper.GetTrackSendInfo_Value(track, -1, receive_index, "B_MUTE")),
        mode = reaper.GetTrackSendInfo_Value(track, -1, receive_index, "I_SENDMODE"),
      }
    end

    local fx_count = reaper.TrackFX_GetCount(track)
    for fx_index = 0, fx_count - 1 do
      local _, fx_name = reaper.TrackFX_GetFXName(track, fx_index, "")
      local _, preset = reaper.TrackFX_GetPreset(track, fx_index, "")
      local _, fx_ident = reaper.TrackFX_GetNamedConfigParm(track, fx_index, "fx_ident")
      local fx_entry = {
        track_guid = track_guid(track),
        fx_index = fx_index,
        fx_guid = reaper.TrackFX_GetFXGUID(track, fx_index) or "",
        name = fx_name or "",
        vendor = "",
        identity = fx_ident or "",
        enabled = reaper.TrackFX_GetEnabled(track, fx_index),
        offline = reaper.TrackFX_GetOffline(track, fx_index),
        preset = preset or "",
        parameters = array(),
      }
      local param_count = reaper.TrackFX_GetNumParams(track, fx_index)
      for param_index = 0, param_count - 1 do
        local _, param_name = reaper.TrackFX_GetParamName(track, fx_index, param_index, "")
        local value, min_value, max_value, mid_value =
          reaper.TrackFX_GetParamEx(track, fx_index, param_index)
        local envelope = reaper.GetFXEnvelope(track, fx_index, param_index, false)
        fx_entry.parameters[#fx_entry.parameters + 1] = {
          index = param_index,
          name = param_name or "",
          value = value,
          min = min_value,
          max = max_value,
          mid = mid_value,
          envelope_present = envelope ~= nil,
        }
      end
      snapshot.fx[#snapshot.fx + 1] = fx_entry
    end
  end

  local item_count = reaper.CountMediaItems(proj)
  for item_index = 0, item_count - 1 do
    local item = reaper.GetMediaItem(proj, item_index)
    local _, item_guid = reaper.GetSetMediaItemInfo_String(item, "GUID", "", false)
    local item_track = reaper.GetMediaItemTrack(item)
    local item_entry = {
      guid = item_guid or "",
      track_guid = track_guid(item_track),
      position = reaper.GetMediaItemInfo_Value(item, "D_POSITION"),
      length = reaper.GetMediaItemInfo_Value(item, "D_LENGTH"),
      fade_in = reaper.GetMediaItemInfo_Value(item, "D_FADEINLEN"),
      fade_out = reaper.GetMediaItemInfo_Value(item, "D_FADEOUTLEN"),
      mute = bool_value(reaper.GetMediaItemInfo_Value(item, "B_MUTE")),
      takes = array(),
    }
    local take_count = reaper.CountTakes(item)
    for take_index = 0, take_count - 1 do
      local take = reaper.GetTake(item, take_index)
      if take ~= nil then
        local _, take_guid_value = reaper.GetSetMediaItemTakeInfo_String(take, "GUID", "", false)
        local source = reaper.GetMediaItemTake_Source(take)
        local source_path = ""
        if source ~= nil then
          source_path = reaper.GetMediaSourceFileName(source, "") or ""
        end
        item_entry.takes[#item_entry.takes + 1] = {
          guid = take_guid_value or "",
          source = source_path,
          gain = reaper.GetMediaItemTakeInfo_Value(take, "D_VOL"),
          pitch = reaper.GetMediaItemTakeInfo_Value(take, "D_PITCH"),
          rate = reaper.GetMediaItemTakeInfo_Value(take, "D_PLAYRATE"),
        }
      end
    end
    snapshot.items[#snapshot.items + 1] = item_entry
  end

  return snapshot
end

local function require_number(args, key)
  local value = args[key]
  if type(value) ~= "number" then error("REAPER_ARGUMENT_REQUIRED_NUMBER:" .. key) end
  return value
end

local function require_string(args, key)
  local value = args[key]
  if type(value) ~= "string" or value == "" then
    error("REAPER_ARGUMENT_REQUIRED_STRING:" .. key)
  end
  return value
end

local function get_track_by_index(proj, index)
  if type(index) ~= "number" or index < 0 or index % 1 ~= 0 then
    error("REAPER_TRACK_INDEX_INVALID")
  end
  local track = reaper.GetTrack(proj, index)
  if track == nil then error("REAPER_TRACK_NOT_FOUND") end
  return track
end


local function require_boolean(args, key)
  local value = args[key]
  if type(value) ~= "boolean" then
    error("REAPER_ARGUMENT_REQUIRED_BOOLEAN:" .. key)
  end
  return value
end

local function get_item_by_guid(proj, guid)
  if type(guid) ~= "string" or guid == "" then
    error("REAPER_ITEM_GUID_REQUIRED")
  end
  local count = reaper.CountMediaItems(proj)
  for index = 0, count - 1 do
    local item = reaper.GetMediaItem(proj, index)
    local _, actual = reaper.GetSetMediaItemInfo_String(item, "GUID", "", false)
    if actual == guid then return item end
  end
  error("REAPER_ITEM_NOT_FOUND")
end

local function get_take_from_args(item, args)
  local take_index = args.take_index
  if take_index == nil then take_index = 0 end
  if type(take_index) ~= "number"
      or take_index < 0
      or take_index % 1 ~= 0 then
    error("REAPER_TAKE_INDEX_INVALID")
  end
  local take = reaper.GetTake(item, take_index)
  if take == nil then error("REAPER_TAKE_NOT_FOUND") end
  return take, take_index
end

local function validate_fx_index(track, fx_index)
  if type(fx_index) ~= "number"
      or fx_index < 0
      or fx_index % 1 ~= 0
      or fx_index >= reaper.TrackFX_GetCount(track) then
    error("REAPER_FX_INDEX_INVALID")
  end
  return fx_index
end

local RENDER_ACTION_ID = 42230

local render_numeric_keys = {
  "RENDER_SETTINGS",
  "RENDER_BOUNDSFLAG",
  "RENDER_CHANNELS",
  "RENDER_SRATE",
  "RENDER_TAILFLAG",
  "RENDER_ADDTOPROJ",
  "RENDER_DITHER",
  "RENDER_NORMALIZE",
}

local render_string_keys = {
  "RENDER_FILE",
  "RENDER_PATTERN",
  "RENDER_FORMAT",
  "RENDER_FORMAT2",
}

local function capture_render_settings(proj)
  local saved = {numeric = {}, strings = {}}
  for _, key in ipairs(render_numeric_keys) do
    saved.numeric[key] = reaper.GetSetProjectInfo(proj, key, 0, false)
  end
  for _, key in ipairs(render_string_keys) do
    local _, value = reaper.GetSetProjectInfo_String(proj, key, "", false)
    saved.strings[key] = value or ""
  end
  return saved
end

local function restore_render_settings(proj, saved)
  for _, key in ipairs(render_numeric_keys) do
    reaper.GetSetProjectInfo(proj, key, saved.numeric[key], true)
  end
  for _, key in ipairs(render_string_keys) do
    reaper.GetSetProjectInfo_String(proj, key, saved.strings[key] or "", true)
  end
end

local function configure_preview_render(proj, render_pattern)
  reaper.GetSetProjectInfo(proj, "RENDER_SETTINGS", 0, true)
  reaper.GetSetProjectInfo(proj, "RENDER_BOUNDSFLAG", 1, true)
  reaper.GetSetProjectInfo(proj, "RENDER_CHANNELS", 2, true)
  reaper.GetSetProjectInfo(proj, "RENDER_SRATE", 48000, true)
  reaper.GetSetProjectInfo(proj, "RENDER_TAILFLAG", 0, true)
  reaper.GetSetProjectInfo(proj, "RENDER_ADDTOPROJ", 0, true)
  reaper.GetSetProjectInfo(proj, "RENDER_DITHER", 0, true)
  reaper.GetSetProjectInfo(proj, "RENDER_NORMALIZE", 0, true)
  reaper.GetSetProjectInfo_String(proj, "RENDER_FILE", render_root, true)
  reaper.GetSetProjectInfo_String(proj, "RENDER_PATTERN", render_pattern, true)
  reaper.GetSetProjectInfo_String(proj, "RENDER_FORMAT", "evaw", true)
  reaper.GetSetProjectInfo_String(proj, "RENDER_FORMAT2", "", true)
end

local RENDER_SETTINGS_MASTER = 0
local RENDER_SETTINGS_STEMS_ONLY = 2

local function collect_render_artifacts(prefix)
  local artifacts = array()
  local index = 0
  while true do
    local name = reaper.EnumerateFiles(render_root, index)
    if name == nil then break end
    index = index + 1
    if name:sub(1, #prefix) == prefix and name:lower():match("%.wav$") then
      local path = render_root .. "/" .. name
      local handle = io.open(path, "rb")
      if handle ~= nil then
        local size = handle:seek("end") or 0
        handle:close()
        if size > 0 then
          artifacts[#artifacts + 1] = {
            name = name,
            path = path,
            size_bytes = size,
          }
        end
      end
    end
  end
  table.sort(artifacts, function(a, b) return a.name < b.name end)
  return artifacts
end

local function capture_track_selection(proj)
  local values = array()
  local count = reaper.CountTracks(proj)
  for index = 0, count - 1 do
    values[#values + 1] = reaper.IsTrackSelected(reaper.GetTrack(proj, index))
  end
  return values
end

local function restore_track_selection(proj, selection)
  local count = reaper.CountTracks(proj)
  for index = 0, count - 1 do
    local track = reaper.GetTrack(proj, index)
    reaper.SetTrackSelected(track, selection[index + 1] == true)
  end
end

local function select_render_tracks(proj, indices)
  if type(indices) ~= "table" or #indices < 1 then
    error("REAPER_RENDER_STEMS_TRACKS_REQUIRED")
  end
  local count = reaper.CountTracks(proj)
  for index = 0, count - 1 do
    reaper.SetTrackSelected(reaper.GetTrack(proj, index), false)
  end
  local seen = {}
  for _, value in ipairs(indices) do
    if type(value) ~= "number"
        or value < 0
        or value % 1 ~= 0
        or value >= count then
      error("REAPER_RENDER_STEMS_TRACK_INDEX_INVALID")
    end
    if seen[value] then error("REAPER_RENDER_STEMS_TRACK_DUPLICATE") end
    seen[value] = true
    reaper.SetTrackSelected(reaper.GetTrack(proj, value), true)
  end
end

local function configure_owned_render(proj, pattern, settings)
  reaper.GetSetProjectInfo(proj, "RENDER_SETTINGS", settings, true)
  reaper.GetSetProjectInfo(proj, "RENDER_BOUNDSFLAG", 1, true)
  reaper.GetSetProjectInfo(proj, "RENDER_CHANNELS", 2, true)
  reaper.GetSetProjectInfo(proj, "RENDER_SRATE", 48000, true)
  reaper.GetSetProjectInfo(proj, "RENDER_TAILFLAG", 0, true)
  reaper.GetSetProjectInfo(proj, "RENDER_ADDTOPROJ", 0, true)
  reaper.GetSetProjectInfo(proj, "RENDER_DITHER", 0, true)
  reaper.GetSetProjectInfo(proj, "RENDER_NORMALIZE", 0, true)
  reaper.GetSetProjectInfo_String(proj, "RENDER_FILE", render_root, true)
  reaper.GetSetProjectInfo_String(proj, "RENDER_PATTERN", pattern, true)
  reaper.GetSetProjectInfo_String(proj, "RENDER_FORMAT", "evaw", true)
  reaper.GetSetProjectInfo_String(proj, "RENDER_FORMAT2", "", true)
end

local function perform_owned_render(proj, prefix, pattern, settings, track_indices)
  if #collect_render_artifacts(prefix) > 0 then
    error("REAPER_RENDER_TARGET_ALREADY_EXISTS")
  end

  local action_text = reaper.kbd_getTextFromCmd(RENDER_ACTION_ID, 0) or ""
  local action_lower = string.lower(action_text)
  if action_lower == ""
      or not action_lower:find("render project", 1, true)
      or not action_lower:find("most recent render settings", 1, true) then
    error("REAPER_RENDER_ACTION_IDENTITY_MISMATCH")
  end

  local saved_settings = capture_render_settings(proj)
  local saved_selection = capture_track_selection(proj)

  local ok_prepare, prepare_err = pcall(function()
    if track_indices ~= nil then select_render_tracks(proj, track_indices) end
    configure_owned_render(proj, pattern, settings)
  end)
  if not ok_prepare then
    restore_render_settings(proj, saved_settings)
    restore_track_selection(proj, saved_selection)
    error(tostring(prepare_err))
  end

  local ok_render, render_err = pcall(
    reaper.Main_OnCommandEx,
    RENDER_ACTION_ID,
    0,
    proj
  )

  restore_render_settings(proj, saved_settings)
  restore_track_selection(proj, saved_selection)

  if not ok_render then
    error("REAPER_RENDER_ACTION_FAILED:" .. tostring(render_err))
  end

  local artifacts = collect_render_artifacts(prefix)
  if #artifacts < 1 then error("REAPER_RENDER_OUTPUT_MISSING") end
  return artifacts, action_text
end

local FIXTURE_NEW_TAB_ACTION_ID = 40859
local FIXTURE_CLOSE_TAB_ACTION_ID = 40860

local function count_project_tabs()
  local count = 0
  while true do
    local project = reaper.EnumProjects(count, "")
    if project == nil then break end
    count = count + 1
  end
  return count
end

local function fixture_id_valid(value)
  return type(value) == "string"
    and #value >= 1
    and #value <= 64
    and value:match("^[A-Za-z0-9][A-Za-z0-9_.%-]*$") ~= nil
end

local function action_text_lower(action_id)
  return string.lower(reaper.kbd_getTextFromCmd(action_id, 0) or "")
end

local handlers = {}

handlers["session.inspect"] = function(_request, _proj)
  return {snapshot = project_snapshot()}
end


handlers["session.checkpoint"] = function(request, proj)
  local safe_request_id = tostring(request.request_id):gsub("[^A-Za-z0-9_.%-]", "_")
  local checkpoint_path = checkpoint_root .. "/" .. safe_request_id .. ".rpp"

  local existing = io.open(checkpoint_path, "rb")
  if existing ~= nil then
    existing:close()
    error("REAPER_CHECKPOINT_ALREADY_EXISTS")
  end

  -- options=0 writes a project copy without changing this ReaProject's filename.
  reaper.Main_SaveProjectEx(proj, checkpoint_path, 0)

  local saved, open_err = io.open(checkpoint_path, "rb")
  if saved == nil then
    error("REAPER_CHECKPOINT_SAVE_FAILED:" .. tostring(open_err))
  end
  local size = saved:seek("end") or 0
  saved:close()
  if size <= 0 then
    os.remove(checkpoint_path)
    error("REAPER_CHECKPOINT_EMPTY")
  end

  return {
    checkpoint_path = checkpoint_path,
    checkpoint_size_bytes = size,
  }
end

handlers["session.rollback"] = function(request, proj)
  local args = request.arguments or {}
  local expected_undo_description = require_string(args, "expected_undo_description")
  local actual_undo_description = reaper.Undo_CanUndo2(proj)

  if actual_undo_description == nil
      or actual_undo_description ~= expected_undo_description then
    error("REAPER_ROLLBACK_UNDO_MISMATCH")
  end

  local undo_result = reaper.Undo_DoUndo2(proj)
  if undo_result == 0 then
    error("REAPER_ROLLBACK_UNDO_FAILED")
  end

  return {
    undone_description = actual_undo_description,
  }
end


handlers["session.fixture.open"] = function(request, proj)
  if fixture_session ~= nil then
    error("REAPER_FIXTURE_SESSION_ALREADY_ACTIVE")
  end

  local args = request.arguments or {}
  local fixture_id = args.fixture_id
  if not fixture_id_valid(fixture_id) then
    error("REAPER_FIXTURE_ID_INVALID")
  end
  for key, _ in pairs(args) do
    if key ~= "fixture_id" then
      error("REAPER_FIXTURE_ARGUMENTS_INVALID")
    end
  end

  local fixture_path = fixture_root .. "/" .. fixture_id .. ".rpp"
  local existing = io.open(fixture_path, "rb")
  if existing ~= nil then
    existing:close()
    error("REAPER_FIXTURE_ALREADY_EXISTS")
  end

  local new_tab_text = action_text_lower(FIXTURE_NEW_TAB_ACTION_ID)
  if not new_tab_text:find("new project tab", 1, true) then
    error("REAPER_FIXTURE_NEW_TAB_ACTION_MISMATCH")
  end

  local previous_project, previous_identity = current_project()
  if previous_project ~= proj then
    error("REAPER_FIXTURE_PREVIOUS_PROJECT_MISMATCH")
  end
  local tabs_before = count_project_tabs()

  reaper.Main_OnCommandEx(FIXTURE_NEW_TAB_ACTION_ID, 0, previous_project)

  local fixture_project = reaper.EnumProjects(-1, "")
  if fixture_project == nil or fixture_project == previous_project then
    error("REAPER_FIXTURE_NEW_TAB_FAILED")
  end
  if count_project_tabs() ~= tabs_before + 1 then
    error("REAPER_FIXTURE_TAB_COUNT_MISMATCH")
  end

  reaper.Main_SaveProjectEx(fixture_project, fixture_path, 8)

  local active_project, active_identity = current_project()
  if active_project ~= fixture_project or active_identity ~= fixture_path then
    error("REAPER_FIXTURE_SAVE_IDENTITY_MISMATCH")
  end
  if reaper.IsProjectDirty(fixture_project) ~= 0 then
    reaper.Main_SaveProject(fixture_project, false)
  end
  if reaper.IsProjectDirty(fixture_project) ~= 0 then
    error("REAPER_FIXTURE_INITIAL_SAVE_DIRTY")
  end

  fixture_session = {
    previous_project = previous_project,
    previous_identity = previous_identity,
    fixture_project = fixture_project,
    fixture_path = fixture_path,
  }

  return {
    fixture_id = fixture_id,
    fixture_project = fixture_path,
    previous_project_identity = previous_identity,
    tabs_before = tabs_before,
    tabs_after = tabs_before + 1,
  }
end

handlers["session.fixture.close"] = function(request, proj)
  local args = request.arguments or {}
  if next(args) ~= nil then
    error("REAPER_FIXTURE_CLOSE_ARGUMENTS_FORBIDDEN")
  end
  if fixture_session == nil then
    error("REAPER_FIXTURE_SESSION_NOT_ACTIVE")
  end

  local current, identity = current_project()
  if current ~= proj
      or current ~= fixture_session.fixture_project
      or identity ~= fixture_session.fixture_path then
    error("REAPER_FIXTURE_ACTIVE_PROJECT_MISMATCH")
  end

  reaper.Main_SaveProject(current, false)
  if reaper.IsProjectDirty(current) ~= 0 then
    error("REAPER_FIXTURE_CLOSE_SAVE_FAILED")
  end

  local close_text = action_text_lower(FIXTURE_CLOSE_TAB_ACTION_ID)
  if not close_text:find("close current project", 1, true)
      or not close_text:find("tab", 1, true) then
    error("REAPER_FIXTURE_CLOSE_TAB_ACTION_MISMATCH")
  end

  local tabs_before = count_project_tabs()
  local previous_project = fixture_session.previous_project
  local previous_identity = fixture_session.previous_identity
  reaper.Main_OnCommandEx(FIXTURE_CLOSE_TAB_ACTION_ID, 0, current)

  local restored_project, restored_identity = current_project()
  if restored_project ~= previous_project or restored_identity ~= previous_identity then
    error("REAPER_FIXTURE_PREVIOUS_PROJECT_NOT_RESTORED")
  end
  if count_project_tabs() ~= tabs_before - 1 then
    error("REAPER_FIXTURE_CLOSE_TAB_COUNT_MISMATCH")
  end

  fixture_session = nil
  return {
    restored_project_identity = restored_identity,
    closed_fixture_project = identity,
    tabs_before = tabs_before,
    tabs_after = tabs_before - 1,
  }
end


handlers["render.preview"] = function(request, proj)
  local args = request.arguments or {}
  if args.path ~= nil
      or args.output_path ~= nil
      or args.render_path ~= nil
      or args.destination ~= nil
      or args.directory ~= nil then
    error("REAPER_RENDER_PATH_CALLER_CONTROLLED")
  end

  local action_text = reaper.kbd_getTextFromCmd(RENDER_ACTION_ID, 0) or ""
  local action_lower = string.lower(action_text)
  if action_lower == ""
      or not action_lower:find("render project", 1, true)
      or not action_lower:find("most recent render settings", 1, true) then
    error("REAPER_RENDER_ACTION_IDENTITY_MISMATCH")
  end

  local safe_request_id = tostring(request.request_id):gsub("[^A-Za-z0-9_.%-]", "_")
  local output_path = render_root .. "/" .. safe_request_id .. ".wav"
  local existing = io.open(output_path, "rb")
  if existing ~= nil then
    existing:close()
    error("REAPER_RENDER_TARGET_ALREADY_EXISTS")
  end

  local saved = capture_render_settings(proj)
  configure_preview_render(proj, safe_request_id)

  local ok_render, render_err = pcall(
    reaper.Main_OnCommandEx,
    RENDER_ACTION_ID,
    0,
    proj
  )

  restore_render_settings(proj, saved)

  if not ok_render then
    error("REAPER_RENDER_ACTION_FAILED:" .. tostring(render_err))
  end

  local rendered, open_err = io.open(output_path, "rb")
  if rendered == nil then
    error("REAPER_RENDER_OUTPUT_MISSING:" .. tostring(open_err))
  end
  local size = rendered:seek("end") or 0
  rendered:close()
  if size <= 0 then
    error("REAPER_RENDER_OUTPUT_EMPTY")
  end

  return {
    artifact_path = output_path,
    artifact_size_bytes = size,
    render_action_id = RENDER_ACTION_ID,
    render_action_text = action_text,
    sample_rate = 48000,
    channels = 2,
    format = "WAV",
  }
end

handlers["arrangement.marker"] = function(request, proj)
  local args = request.arguments or {}
  local position = require_number(args, "position")
  if position < 0 then error("REAPER_MARKER_POSITION_INVALID") end
  local name = require_string(args, "name")
  local wantidx = args.marker_id or -1
  local color = args.color or 0
  if type(wantidx) ~= "number" or wantidx % 1 ~= 0 then
    error("REAPER_MARKER_ID_INVALID")
  end
  if type(color) ~= "number" or color % 1 ~= 0 then
    error("REAPER_MARKER_COLOR_INVALID")
  end
  local marker_id = reaper.AddProjectMarker2(
    proj, false, position, 0.0, name, wantidx, color
  )
  if marker_id < 0 then error("REAPER_MARKER_CREATE_FAILED") end
  return {marker_id = marker_id, position = position, name = name, color = color}
end

handlers["arrangement.region"] = function(request, proj)
  local args = request.arguments or {}
  local start_time = require_number(args, "start")
  local end_time = require_number(args, "end")
  if start_time < 0 or end_time <= start_time then
    error("REAPER_REGION_RANGE_INVALID")
  end
  local name = require_string(args, "name")
  local wantidx = args.region_id or -1
  local color = args.color or 0
  if type(wantidx) ~= "number" or wantidx % 1 ~= 0 then
    error("REAPER_REGION_ID_INVALID")
  end
  if type(color) ~= "number" or color % 1 ~= 0 then
    error("REAPER_REGION_COLOR_INVALID")
  end
  local region_id = reaper.AddProjectMarker2(
    proj, true, start_time, end_time, name, wantidx, color
  )
  if region_id < 0 then error("REAPER_REGION_CREATE_FAILED") end
  return {
    region_id = region_id,
    start = start_time,
    ["end"] = end_time,
    name = name,
    color = color,
  }
end

handlers["audio.split"] = function(request, proj)
  local args = request.arguments or {}
  local item = get_item_by_guid(proj, require_string(args, "item_guid"))
  local split_position = require_number(args, "position")
  local item_position = reaper.GetMediaItemInfo_Value(item, "D_POSITION")
  local item_length = reaper.GetMediaItemInfo_Value(item, "D_LENGTH")
  local item_end = item_position + item_length
  if split_position <= item_position or split_position >= item_end then
    error("REAPER_AUDIO_SPLIT_POSITION_INVALID")
  end

  local right = reaper.SplitMediaItem(item, split_position)
  if right == nil then error("REAPER_AUDIO_SPLIT_FAILED") end
  local _, left_guid = reaper.GetSetMediaItemInfo_String(item, "GUID", "", false)
  local _, right_guid = reaper.GetSetMediaItemInfo_String(right, "GUID", "", false)
  return {
    left_item_guid = left_guid or "",
    right_item_guid = right_guid or "",
    split_position = split_position,
  }
end

handlers["audio.trim"] = function(request, proj)
  local args = request.arguments or {}
  local item = get_item_by_guid(proj, require_string(args, "item_guid"))
  local new_position = require_number(args, "new_position")
  local new_length = require_number(args, "new_length")
  local old_position = reaper.GetMediaItemInfo_Value(item, "D_POSITION")
  local old_length = reaper.GetMediaItemInfo_Value(item, "D_LENGTH")
  local old_end = old_position + old_length
  local new_end = new_position + new_length

  if new_length <= 0
      or new_position < old_position
      or new_end > old_end + 0.0000001 then
    error("REAPER_AUDIO_TRIM_RANGE_INVALID")
  end

  local delta = new_position - old_position
  local take_count = reaper.CountTakes(item)
  for take_index = 0, take_count - 1 do
    local take = reaper.GetTake(item, take_index)
    if take ~= nil and delta > 0 then
      local rate = reaper.GetMediaItemTakeInfo_Value(take, "D_PLAYRATE")
      local old_offset = reaper.GetMediaItemTakeInfo_Value(take, "D_STARTOFFS")
      local new_offset = old_offset + delta * rate
      if new_offset < 0 then error("REAPER_AUDIO_TRIM_SOURCE_OFFSET_INVALID") end
      if not reaper.SetMediaItemTakeInfo_Value(take, "D_STARTOFFS", new_offset) then
        error("REAPER_AUDIO_TRIM_SOURCE_OFFSET_FAILED")
      end
    end
  end

  if not reaper.SetMediaItemPosition(item, new_position, false) then
    error("REAPER_AUDIO_TRIM_POSITION_FAILED")
  end
  if not reaper.SetMediaItemLength(item, new_length, false) then
    error("REAPER_AUDIO_TRIM_LENGTH_FAILED")
  end
  return {
    item_guid = args.item_guid,
    old_position = old_position,
    old_length = old_length,
    new_position = new_position,
    new_length = new_length,
  }
end

handlers["audio.fade"] = function(request, proj)
  local args = request.arguments or {}
  local item = get_item_by_guid(proj, require_string(args, "item_guid"))
  local fade_in = require_number(args, "fade_in")
  local fade_out = require_number(args, "fade_out")
  local length = reaper.GetMediaItemInfo_Value(item, "D_LENGTH")
  if fade_in < 0 or fade_out < 0 or fade_in + fade_out > length then
    error("REAPER_AUDIO_FADE_RANGE_INVALID")
  end
  if not reaper.SetMediaItemInfo_Value(item, "D_FADEINLEN", fade_in) then
    error("REAPER_AUDIO_FADE_IN_FAILED")
  end
  if not reaper.SetMediaItemInfo_Value(item, "D_FADEOUTLEN", fade_out) then
    error("REAPER_AUDIO_FADE_OUT_FAILED")
  end
  return {item_guid = args.item_guid, fade_in = fade_in, fade_out = fade_out}
end

handlers["audio.align"] = function(request, proj)
  local args = request.arguments or {}
  local item = get_item_by_guid(proj, require_string(args, "item_guid"))
  local position = require_number(args, "position")
  if position < 0 then error("REAPER_AUDIO_ALIGN_POSITION_INVALID") end
  local old_position = reaper.GetMediaItemInfo_Value(item, "D_POSITION")
  if not reaper.SetMediaItemPosition(item, position, false) then
    error("REAPER_AUDIO_ALIGN_FAILED")
  end
  return {
    item_guid = args.item_guid,
    old_position = old_position,
    new_position = position,
  }
end

handlers["audio.time_stretch"] = function(request, proj)
  local args = request.arguments or {}
  local item = get_item_by_guid(proj, require_string(args, "item_guid"))
  local take, take_index = get_take_from_args(item, args)
  local rate = require_number(args, "rate")
  if rate < 0.125 or rate > 8.0 then
    error("REAPER_AUDIO_PLAYRATE_RANGE_INVALID")
  end
  local preserve_pitch = true
  if args.preserve_pitch ~= nil then
    preserve_pitch = require_boolean(args, "preserve_pitch")
  end
  local old_rate = reaper.GetMediaItemTakeInfo_Value(take, "D_PLAYRATE")
  local old_length = reaper.GetMediaItemInfo_Value(item, "D_LENGTH")
  if not reaper.SetMediaItemTakeInfo_Value(take, "D_PLAYRATE", rate) then
    error("REAPER_AUDIO_PLAYRATE_WRITE_FAILED")
  end
  if not reaper.SetMediaItemTakeInfo_Value(
      take, "B_PPITCH", preserve_pitch and 1 or 0
    ) then
    error("REAPER_AUDIO_PRESERVE_PITCH_WRITE_FAILED")
  end
  if args.adjust_item_length == true then
    local adjusted = old_length * old_rate / rate
    if adjusted <= 0
        or not reaper.SetMediaItemLength(item, adjusted, false) then
      error("REAPER_AUDIO_STRETCH_LENGTH_FAILED")
    end
  end
  return {
    item_guid = args.item_guid,
    take_index = take_index,
    old_rate = old_rate,
    new_rate = rate,
    preserve_pitch = preserve_pitch,
  }
end

handlers["audio.pitch"] = function(request, proj)
  local args = request.arguments or {}
  local item = get_item_by_guid(proj, require_string(args, "item_guid"))
  local take, take_index = get_take_from_args(item, args)
  local semitones = require_number(args, "semitones")
  if semitones < -48 or semitones > 48 then
    error("REAPER_AUDIO_PITCH_RANGE_INVALID")
  end
  local old_pitch = reaper.GetMediaItemTakeInfo_Value(take, "D_PITCH")
  if not reaper.SetMediaItemTakeInfo_Value(take, "D_PITCH", semitones) then
    error("REAPER_AUDIO_PITCH_WRITE_FAILED")
  end
  return {
    item_guid = args.item_guid,
    take_index = take_index,
    old_pitch = old_pitch,
    new_pitch = semitones,
  }
end

handlers["render.master"] = function(request, proj)
  local args = request.arguments or {}
  for key, _ in pairs(args) do
    if key == "path"
        or key == "output_path"
        or key == "render_path"
        or key == "destination"
        or key == "directory" then
      error("REAPER_RENDER_PATH_CALLER_CONTROLLED")
    end
  end
  local safe_request_id = tostring(request.request_id):gsub("[^A-Za-z0-9_.%-]", "_")
  local prefix = safe_request_id .. "-master"
  local artifacts, action_text = perform_owned_render(
    proj,
    prefix,
    prefix,
    RENDER_SETTINGS_MASTER,
    nil
  )
  if #artifacts ~= 1 then error("REAPER_RENDER_MASTER_ARTIFACT_COUNT_INVALID") end
  return {
    render_kind = "MASTER",
    artifact = artifacts[1],
    render_action_id = RENDER_ACTION_ID,
    render_action_text = action_text,
    sample_rate = 48000,
    channels = 2,
    format = "WAV",
  }
end

handlers["render.stems"] = function(request, proj)
  local args = request.arguments or {}
  for key, _ in pairs(args) do
    if key == "path"
        or key == "output_path"
        or key == "render_path"
        or key == "destination"
        or key == "directory" then
      error("REAPER_RENDER_PATH_CALLER_CONTROLLED")
    end
  end
  local safe_request_id = tostring(request.request_id):gsub("[^A-Za-z0-9_.%-]", "_")
  local prefix = safe_request_id .. "-stem"
  local pattern = prefix .. "-$track"
  local artifacts, action_text = perform_owned_render(
    proj,
    prefix,
    pattern,
    RENDER_SETTINGS_STEMS_ONLY,
    args.track_indices
  )
  if #artifacts ~= #args.track_indices then
    error("REAPER_RENDER_STEMS_ARTIFACT_COUNT_INVALID")
  end
  return {
    render_kind = "STEMS",
    artifacts = artifacts,
    artifact_count = #artifacts,
    render_action_id = RENDER_ACTION_ID,
    render_action_text = action_text,
    sample_rate = 48000,
    channels = 2,
    format = "WAV",
  }
end

handlers["track.create"] = function(request, proj)
  local args = request.arguments or {}
  local index = args.index
  if index == nil then index = reaper.CountTracks(proj) end
  if type(index) ~= "number" or index < 0 or index % 1 ~= 0 then
    error("REAPER_TRACK_INDEX_INVALID")
  end
  reaper.InsertTrackAtIndex(index, true)
  local track = reaper.GetTrack(proj, index)
  if track == nil then error("REAPER_TRACK_CREATE_FAILED") end
  if type(args.name) == "string" and args.name ~= "" then
    reaper.GetSetMediaTrackInfo_String(track, "P_NAME", args.name, true)
  end
  return {track_index = index, track_guid = track_guid(track)}
end

handlers["track.configure"] = function(request, proj)
  local args = request.arguments or {}
  local track = get_track_by_index(proj, require_number(args, "track_index"))

  if args.name ~= nil then
    if type(args.name) ~= "string" or args.name == "" then
      error("REAPER_TRACK_NAME_INVALID")
    end
    reaper.GetSetMediaTrackInfo_String(track, "P_NAME", args.name, true)
  end

  local numeric = {
    volume = {"D_VOL", 0.0, 16.0},
    pan = {"D_PAN", -1.0, 1.0},
    width = {"D_WIDTH", -1.0, 1.0},
  }
  for key, spec in pairs(numeric) do
    if args[key] ~= nil then
      if type(args[key]) ~= "number"
          or args[key] < spec[2]
          or args[key] > spec[3] then
        error("REAPER_TRACK_PARAMETER_RANGE:" .. key)
      end
      if not reaper.SetMediaTrackInfo_Value(track, spec[1], args[key]) then
        error("REAPER_TRACK_PARAMETER_WRITE_FAILED:" .. key)
      end
    end
  end

  local bools = {
    mute = "B_MUTE",
    record_arm = "I_RECARM",
  }
  for key, parm in pairs(bools) do
    if args[key] ~= nil then
      local value = require_boolean(args, key)
      if not reaper.SetMediaTrackInfo_Value(track, parm, value and 1 or 0) then
        error("REAPER_TRACK_PARAMETER_WRITE_FAILED:" .. key)
      end
    end
  end

  if args.solo ~= nil then
    local solo = require_boolean(args, "solo")
    if not reaper.SetMediaTrackInfo_Value(track, "I_SOLO", solo and 1 or 0) then
      error("REAPER_TRACK_PARAMETER_WRITE_FAILED:solo")
    end
  end

  if args.channel_count ~= nil then
    local channels = args.channel_count
    if type(channels) ~= "number"
        or channels < 2
        or channels > 64
        or channels % 2 ~= 0 then
      error("REAPER_TRACK_CHANNEL_COUNT_INVALID")
    end
    if not reaper.SetMediaTrackInfo_Value(track, "I_NCHAN", channels) then
      error("REAPER_TRACK_CHANNEL_COUNT_WRITE_FAILED")
    end
  end

  return {
    track_guid = track_guid(track),
    track_index = args.track_index,
    volume = reaper.GetMediaTrackInfo_Value(track, "D_VOL"),
    pan = reaper.GetMediaTrackInfo_Value(track, "D_PAN"),
    width = reaper.GetMediaTrackInfo_Value(track, "D_WIDTH"),
    channel_count = reaper.GetMediaTrackInfo_Value(track, "I_NCHAN"),
  }
end

handlers["track.folder"] = function(request, proj)
  local args = request.arguments or {}
  local track = get_track_by_index(proj, require_number(args, "track_index"))
  local depth = require_number(args, "folder_depth")
  if depth % 1 ~= 0 or depth < -16 or depth > 1 then
    error("REAPER_TRACK_FOLDER_DEPTH_INVALID")
  end
  if not reaper.SetMediaTrackInfo_Value(track, "I_FOLDERDEPTH", depth) then
    error("REAPER_TRACK_FOLDER_WRITE_FAILED")
  end
  return {
    track_guid = track_guid(track),
    track_index = args.track_index,
    folder_depth = depth,
  }
end

handlers["audio.import"] = function(request, proj)
  local args = request.arguments or {}
  local source_path = require_string(args, "source_path")
  local track = get_track_by_index(proj, require_number(args, "track_index"))
  local source = reaper.PCM_Source_CreateFromFile(source_path)
  if source == nil then error("REAPER_AUDIO_SOURCE_OPEN_FAILED") end
  local item = reaper.AddMediaItemToTrack(track)
  if item == nil then error("REAPER_AUDIO_ITEM_CREATE_FAILED") end
  local take = reaper.AddTakeToMediaItem(item)
  if take == nil then error("REAPER_AUDIO_TAKE_CREATE_FAILED") end
  reaper.SetMediaItemTake_Source(take, source)
  local position = args.position or 0.0
  reaper.SetMediaItemInfo_Value(item, "D_POSITION", position)
  local length, length_is_qn = reaper.GetMediaSourceLength(source)
  if length_is_qn then
    length = reaper.TimeMap2_QNToTime(proj, length)
  end
  if type(args.length) == "number" and args.length > 0 then length = args.length end
  reaper.SetMediaItemInfo_Value(item, "D_LENGTH", length)
  return {track_guid = track_guid(track), source_path = source_path, position = position, length = length}
end

handlers["routing.bus"] = function(request, proj)
  local args = request.arguments or {}
  local index = args.index
  if index == nil then index = reaper.CountTracks(proj) end
  reaper.InsertTrackAtIndex(index, true)
  local bus = reaper.GetTrack(proj, index)
  if bus == nil then error("REAPER_BUS_CREATE_FAILED") end
  reaper.GetSetMediaTrackInfo_String(bus, "P_NAME", args.name or "Hazewave Bus", true)
  local sources = args.source_track_indices
  local sends = array()
  if type(sources) == "table" then
    for _, source_index in ipairs(sources) do
      local source = get_track_by_index(proj, source_index)
      if source == bus then error("REAPER_BUS_SELF_SEND_FORBIDDEN") end
      local send_index = reaper.CreateTrackSend(source, bus)
      if send_index < 0 then error("REAPER_SEND_CREATE_FAILED") end
      sends[#sends + 1] = {source_track_guid = track_guid(source), send_index = send_index}
    end
  end
  return {bus_index = index, bus_guid = track_guid(bus), sends = sends}
end

handlers["routing.send"] = function(request, proj)
  local args = request.arguments or {}
  local source = get_track_by_index(proj, require_number(args, "source_track_index"))
  local destination = get_track_by_index(proj, require_number(args, "destination_track_index"))
  if source == destination then error("REAPER_SEND_SELF_ROUTE_FORBIDDEN") end
  local send_index = reaper.CreateTrackSend(source, destination)
  if send_index < 0 then error("REAPER_SEND_CREATE_FAILED") end
  local optional = {
    gain = "D_VOL",
    pan = "D_PAN",
    mute = "B_MUTE",
    mode = "I_SENDMODE",
    source_channels = "I_SRCCHAN",
    destination_channels = "I_DSTCHAN",
  }
  for key, parm in pairs(optional) do
    if type(args[key]) == "number" then
      reaper.SetTrackSendInfo_Value(source, 0, send_index, parm, args[key])
    end
  end
  return {send_index = send_index, source_track_guid = track_guid(source), destination_track_guid = track_guid(destination)}
end

handlers["fx.inventory"] = function(_request, _proj)
  return {fx = project_snapshot().fx}
end

handlers["fx.add"] = function(request, proj)
  local args = request.arguments or {}
  local track = get_track_by_index(proj, require_number(args, "track_index"))
  local fx_name = require_string(args, "plugin_identity")
  local fx_index = reaper.TrackFX_AddByName(track, fx_name, false, -1)
  if fx_index < 0 then error("REAPER_PLUGIN_NOT_FOUND") end
  local _, actual_name = reaper.TrackFX_GetFXName(track, fx_index, "")
  return {track_guid = track_guid(track), fx_index = fx_index, name = actual_name or ""}
end

handlers["fx.remove"] = function(request, proj)
  local args = request.arguments or {}
  local track = get_track_by_index(proj, require_number(args, "track_index"))
  local fx_index = validate_fx_index(track, require_number(args, "fx_index"))
  local _, name = reaper.TrackFX_GetFXName(track, fx_index, "")
  if not reaper.TrackFX_Delete(track, fx_index) then
    error("REAPER_FX_REMOVE_FAILED")
  end
  return {
    track_guid = track_guid(track),
    removed_fx_index = fx_index,
    removed_name = name or "",
  }
end

handlers["fx.bypass"] = function(request, proj)
  local args = request.arguments or {}
  local track = get_track_by_index(proj, require_number(args, "track_index"))
  local fx_index = validate_fx_index(track, require_number(args, "fx_index"))
  local bypass = require_boolean(args, "bypass")
  reaper.TrackFX_SetEnabled(track, fx_index, not bypass)
  local enabled = reaper.TrackFX_GetEnabled(track, fx_index)
  if enabled == bypass then error("REAPER_FX_BYPASS_VERIFY_FAILED") end
  return {
    track_guid = track_guid(track),
    fx_index = fx_index,
    bypass = bypass,
    enabled = enabled,
  }
end

handlers["fx.preset"] = function(request, proj)
  local args = request.arguments or {}
  local track = get_track_by_index(proj, require_number(args, "track_index"))
  local fx_index = validate_fx_index(track, require_number(args, "fx_index"))
  local preset = require_string(args, "preset")
  if not reaper.TrackFX_SetPreset(track, fx_index, preset) then
    error("REAPER_FX_PRESET_NOT_FOUND")
  end
  local _, actual = reaper.TrackFX_GetPreset(track, fx_index, "")
  return {
    track_guid = track_guid(track),
    fx_index = fx_index,
    requested_preset = preset,
    active_preset = actual or "",
  }
end

handlers["fx.automation"] = function(request, proj)
  local args = request.arguments or {}
  local track = get_track_by_index(proj, require_number(args, "track_index"))
  local fx_index = validate_fx_index(track, require_number(args, "fx_index"))
  local param_index = require_number(args, "parameter_index")
  if param_index < 0
      or param_index % 1 ~= 0
      or param_index >= reaper.TrackFX_GetNumParams(track, fx_index) then
    error("REAPER_FX_PARAMETER_INDEX_INVALID")
  end
  local points = args.points
  if type(points) ~= "table" or #points < 1 then
    error("REAPER_FX_AUTOMATION_POINTS_REQUIRED")
  end
  local envelope = reaper.GetFXEnvelope(track, fx_index, param_index, true)
  if envelope == nil then error("REAPER_FX_AUTOMATION_ENVELOPE_FAILED") end
  local scaling_mode = reaper.GetEnvelopeScalingMode(envelope)
  local inserted = 0
  for _, point in ipairs(points) do
    if type(point) ~= "table" then
      error("REAPER_FX_AUTOMATION_POINT_MALFORMED")
    end
    local time = point.time
    local normalized = point.normalized_value
    local shape = point.shape or 0
    local tension = point.tension or 0.0
    if type(time) ~= "number" or time < 0 then
      error("REAPER_FX_AUTOMATION_TIME_INVALID")
    end
    if type(normalized) ~= "number"
        or normalized < 0
        or normalized > 1 then
      error("REAPER_FX_AUTOMATION_VALUE_INVALID")
    end
    if type(shape) ~= "number" or shape % 1 ~= 0 or shape < 0 or shape > 5 then
      error("REAPER_FX_AUTOMATION_SHAPE_INVALID")
    end
    if type(tension) ~= "number" or tension < -1 or tension > 1 then
      error("REAPER_FX_AUTOMATION_TENSION_INVALID")
    end
    local envelope_value = reaper.ScaleToEnvelopeMode(scaling_mode, normalized)
    local ok = reaper.InsertEnvelopePointEx(
      envelope, -1, time, envelope_value, shape, tension, false, true
    )
    if not ok then error("REAPER_FX_AUTOMATION_INSERT_FAILED") end
    inserted = inserted + 1
  end
  reaper.Envelope_SortPointsEx(envelope, -1)
  return {
    track_guid = track_guid(track),
    fx_index = fx_index,
    parameter_index = param_index,
    inserted_points = inserted,
  }
end

handlers["fx.parameter.read"] = function(request, proj)
  local args = request.arguments or {}
  local track = get_track_by_index(proj, require_number(args, "track_index"))
  local fx_index = require_number(args, "fx_index")
  local param_index = require_number(args, "parameter_index")
  local _, name = reaper.TrackFX_GetParamName(track, fx_index, param_index, "")
  local value, min_value, max_value, mid_value = reaper.TrackFX_GetParamEx(track, fx_index, param_index)
  return {
    track_guid = track_guid(track),
    fx_index = fx_index,
    parameter_index = param_index,
    name = name or "",
    value = value,
    min = min_value,
    max = max_value,
    mid = mid_value,
  }
end

handlers["fx.parameter.write"] = function(request, proj)
  local args = request.arguments or {}
  local track = get_track_by_index(proj, require_number(args, "track_index"))
  local fx_index = require_number(args, "fx_index")
  local param_index = require_number(args, "parameter_index")
  local normalized_value = require_number(args, "normalized_value")
  if normalized_value < 0 or normalized_value > 1 then
    error("REAPER_FX_PARAMETER_NORMALIZED_RANGE")
  end
  local _, actual_name = reaper.TrackFX_GetParamName(track, fx_index, param_index, "")
  if type(args.expected_parameter_name) == "string"
      and args.expected_parameter_name ~= ""
      and actual_name ~= args.expected_parameter_name then
    error("REAPER_FX_PARAMETER_IDENTITY_MISMATCH")
  end
  local ok = reaper.TrackFX_SetParamNormalized(track, fx_index, param_index, normalized_value)
  if not ok then error("REAPER_FX_PARAMETER_WRITE_FAILED") end
  return {
    track_guid = track_guid(track),
    fx_index = fx_index,
    parameter_index = param_index,
    name = actual_name or "",
    normalized_value = normalized_value,
  }
end

local readonly_operations = {
  ["session.inspect"] = true,
  ["fx.inventory"] = true,
  ["fx.parameter.read"] = true,
}


local special_operations = {
  ["session.checkpoint"] = true,
  ["session.rollback"] = true,
  ["render.preview"] = true,
  ["render.master"] = true,
  ["render.stems"] = true,
}


local context_switch_operations = {
  ["session.fixture.open"] = true,
  ["session.fixture.close"] = true,
}

local function validate_request(request)
  if type(request) ~= "table" then error("REAPER_REQUEST_MALFORMED") end
  if request.schema ~= REQUEST_SCHEMA then error("REAPER_REQUEST_SCHEMA_INVALID") end
  local required_strings = {
    "request_id", "task_id", "authorization_id", "idempotency_key",
    "operation", "expected_project_identity", "deadline", "issued_at",
  }
  for _, key in ipairs(required_strings) do
    if type(request[key]) ~= "string" or request[key] == "" then
      error("REAPER_REQUEST_FIELD_REQUIRED:" .. key)
    end
  end
  if type(request.arguments) ~= "table" then error("REAPER_REQUEST_ARGUMENTS_MALFORMED") end
  if type(request.expected_project_state_change_count) ~= "number" then
    error("REAPER_REQUEST_EXPECTED_STATE_REQUIRED")
  end
  if type(request.issued_at_epoch_seconds) ~= "number"
      or type(request.deadline_epoch_seconds) ~= "number"
      or request.deadline_epoch_seconds <= request.issued_at_epoch_seconds then
    error("REAPER_REQUEST_DEADLINE_INVALID")
  end
  if os.time() > request.deadline_epoch_seconds then
    error("REAPER_REQUEST_DEADLINE_EXCEEDED")
  end
  if handlers[request.operation] == nil then
    error("REAPER_OPERATION_NOT_ALLOWLISTED")
  end
end

local function preflight_project(request)
  local proj, identity = current_project()
  if identity ~= request.expected_project_identity then
    error("REAPER_PROJECT_IDENTITY_MISMATCH")
  end
  local actual_state = reaper.GetProjectStateChangeCount(proj)
  if actual_state ~= request.expected_project_state_change_count then
    error("REAPER_STATE_STALE")
  end
  return proj, actual_state
end

local function response_base(request, started_at)
  return {
    schema = RESPONSE_SCHEMA,
    request_id = request.request_id or "",
    task_id = request.task_id or "",
    operation = request.operation or "",
    status = "FAIL",
    state_before = {},
    state_after = {},
    result = {},
    error = JSON_NULL,
    started_at = started_at,
    completed_at = utc_now(),
  }
end

local function execute_request(request)
  local started_at = utc_now()
  local response = response_base(request, started_at)

  local ok_validate, validate_err = pcall(validate_request, request)
  if not ok_validate then
    response.error = {code = tostring(validate_err)}
    response.completed_at = utc_now()
    return response
  end

  local proj, before_count
  if context_switch_operations[request.operation] then
    local ok_project, project_or_err, state_or_nil = pcall(preflight_project, request)
    if not ok_project then
      response.error = {code = tostring(project_or_err)}
      response.completed_at = utc_now()
      return response
    end
    proj = project_or_err
    before_count = state_or_nil
    response.state_before = {project_state_change_count = before_count}

    local ok_handler, result_or_err = pcall(handlers[request.operation], request, proj)
    local active_after = reaper.EnumProjects(-1, "")
    local after_count = 0
    if active_after ~= nil then
      after_count = reaper.GetProjectStateChangeCount(active_after)
    end

    if not ok_handler then
      response.error = {code = tostring(result_or_err)}
      response.state_after = {project_state_change_count = after_count}
      response.completed_at = utc_now()
      return response
    end

    response.status = "PASS"
    response.result = result_or_err or {}
    response.state_after = {project_state_change_count = after_count}
    response.completed_at = utc_now()
    return response
  end

  if special_operations[request.operation] then
    local ok_project, project_or_err, state_or_nil = pcall(preflight_project, request)
    if not ok_project then
      response.error = {code = tostring(project_or_err)}
      response.completed_at = utc_now()
      return response
    end
    proj = project_or_err
    before_count = state_or_nil
    response.state_before = {project_state_change_count = before_count}

    local ok_handler, result_or_err = pcall(handlers[request.operation], request, proj)
    if not ok_handler then
      response.error = {code = tostring(result_or_err)}
      response.state_after = {
        project_state_change_count = reaper.GetProjectStateChangeCount(proj)
      }
      response.completed_at = utc_now()
      return response
    end

    response.status = "PASS"
    response.result = result_or_err or {}
    response.state_after = {
      project_state_change_count = reaper.GetProjectStateChangeCount(proj)
    }
    response.completed_at = utc_now()
    return response
  end

  if readonly_operations[request.operation] then
    local ok_project, project_or_err, state_or_nil = pcall(preflight_project, request)
    if not ok_project then
      response.error = {code = tostring(project_or_err)}
      response.completed_at = utc_now()
      return response
    end
    proj = project_or_err
    before_count = state_or_nil
    response.state_before = {project_state_change_count = before_count}
    local ok_handler, result_or_err = pcall(handlers[request.operation], request, proj)
    if not ok_handler then
      response.error = {code = tostring(result_or_err)}
      response.state_after = {project_state_change_count = reaper.GetProjectStateChangeCount(proj)}
      response.completed_at = utc_now()
      return response
    end
    response.status = "PASS"
    response.result = result_or_err or {}
    response.state_after = {project_state_change_count = reaper.GetProjectStateChangeCount(proj)}
    response.completed_at = utc_now()
    return response
  end

  local ok_preflight, project_or_err, state_or_nil = pcall(preflight_project, request)
  if not ok_preflight then
    response.error = {code = tostring(project_or_err)}
    response.completed_at = utc_now()
    return response
  end
  proj = project_or_err
  before_count = state_or_nil
  response.state_before = {project_state_change_count = before_count}

  local undo_name = "Hazewave: " .. request.operation .. " [" .. request.request_id .. "]"
  reaper.Undo_BeginBlock2(proj)
  reaper.PreventUIRefresh(1)
  local ok_handler, result_or_err = pcall(handlers[request.operation], request, proj)
  reaper.PreventUIRefresh(-1)

  if not ok_handler then
    reaper.Undo_EndBlock2(proj, undo_name, -1)
    reaper.Undo_DoUndo2(proj)
    response.status = "ROLLED_BACK"
    response.error = {code = tostring(result_or_err)}
    response.state_after = {project_state_change_count = reaper.GetProjectStateChangeCount(proj)}
    response.completed_at = utc_now()
    return response
  end

  reaper.UpdateArrange()
  local after_count = reaper.GetProjectStateChangeCount(proj)
  if after_count <= before_count then
    reaper.Undo_EndBlock2(proj, undo_name, -1)
    reaper.Undo_DoUndo2(proj)
    response.status = "ROLLED_BACK"
    response.error = {code = "REAPER_POSTCONDITION_STATE_UNCHANGED"}
    response.state_after = {project_state_change_count = reaper.GetProjectStateChangeCount(proj)}
    response.completed_at = utc_now()
    return response
  end

  reaper.Undo_EndBlock2(proj, undo_name, -1)
  response.status = "PASS"
  response.result = result_or_err or {}
  response.state_after = {project_state_change_count = after_count}

  if request.arguments and request.arguments.save_project == true then
    reaper.Main_SaveProject(proj, false)
  end

  response.completed_at = utc_now()
  return response
end

local function request_name_valid(name)
  return type(name) == "string"
    and name:match("^[A-Za-z0-9_.%-]+%.json$") ~= nil
    and not name:match("%.tmp%.")
end

local function response_path_for(request_id)
  local safe = tostring(request_id):gsub("[^A-Za-z0-9_.%-]", "_")
  return responses_dir .. "/" .. safe .. ".json"
end

local function recover_inflight_files()
  local index = 0
  while true do
    local name = reaper.EnumerateFiles(processing_dir, index)
    if name == nil then break end
    index = index + 1
    if request_name_valid(name) then
      local path = processing_dir .. "/" .. name
      local text = read_text(path)
      if text ~= nil then
        local ok, request = pcall(json_decode, text)
        if ok and type(request) == "table" then
          local response = response_base(request, utc_now())
          response.status = "FAIL"
          response.error = {
            code = "REAPER_INDETERMINATE_AFTER_CRASH",
            detail = "Processing file survived bridge restart; mutation is not retried automatically.",
          }
          local proj = reaper.EnumProjects(-1, "")
          if proj ~= nil then
            response.state_after = {
              project_state_change_count = reaper.GetProjectStateChangeCount(proj)
            }
          end
          response.completed_at = utc_now()
          atomic_write_json(response_path_for(request.request_id or name), response)
        end
      end
      os.remove(path)
    end
  end
end

local function process_one_request()
  local index = 0
  while true do
    local name = reaper.EnumerateFiles(requests_dir, index)
    if name == nil then return end
    index = index + 1
    if request_name_valid(name) then
      local source_path = requests_dir .. "/" .. name
      local claimed_path = processing_dir .. "/" .. name
      local claimed = os.rename(source_path, claimed_path)
      if claimed then
        local text, read_err = read_text(claimed_path)
        local request = nil
        local response = nil
        if text == nil then
          response = {
            schema = RESPONSE_SCHEMA,
            request_id = name,
            task_id = "",
            operation = "",
            status = "FAIL",
            state_before = {},
            state_after = {},
            result = {},
            error = {code = "REAPER_REQUEST_READ_FAILED", detail = tostring(read_err)},
            started_at = utc_now(),
            completed_at = utc_now(),
          }
        else
          local ok_decode, decoded_or_err = pcall(json_decode, text)
          if not ok_decode then
            response = {
              schema = RESPONSE_SCHEMA,
              request_id = name,
              task_id = "",
              operation = "",
              status = "FAIL",
              state_before = {},
              state_after = {},
              result = {},
              error = {code = "REAPER_REQUEST_MALFORMED", detail = tostring(decoded_or_err)},
              started_at = utc_now(),
              completed_at = utc_now(),
            }
          else
            request = decoded_or_err
            response = execute_request(request)
          end
        end
        local request_id = request and request.request_id or name
        local ok_write, write_err = atomic_write_json(response_path_for(request_id), response)
        if ok_write then
          os.remove(claimed_path)
        else
          reaper.ShowConsoleMsg("Hazewave REAPER bridge response write failed: " .. tostring(write_err) .. "\n")
        end
        return
      end
    end
  end
end

local last_heartbeat = 0
local function write_heartbeat()
  local now = os.time()
  if now == last_heartbeat then return end
  last_heartbeat = now
  local proj, identity = current_project()
  local payload = {
    schema = HEARTBEAT_SCHEMA,
    bridge_schema = BRIDGE_SCHEMA,
    bridge_id = "HAZEWAVE_REAPER_BRIDGE",
    updated_at = utc_now(),
    project_identity = identity,
    project_state_change_count = reaper.GetProjectStateChangeCount(proj),
  }
  local ok, err = atomic_write_json(heartbeat_path, payload)
  if not ok then
    reaper.ShowConsoleMsg("Hazewave REAPER bridge heartbeat failed: " .. tostring(err) .. "\n")
  end
end

recover_inflight_files()

local function loop()
  local ok_heartbeat, heartbeat_err = pcall(write_heartbeat)
  if not ok_heartbeat then
    reaper.ShowConsoleMsg("Hazewave REAPER bridge heartbeat exception: " .. tostring(heartbeat_err) .. "\n")
  end
  local ok_request, request_err = pcall(process_one_request)
  if not ok_request then
    reaper.ShowConsoleMsg("Hazewave REAPER bridge request exception: " .. tostring(request_err) .. "\n")
  end
  reaper.defer(loop)
end

reaper.atexit(function()
  local payload = {
    schema = HEARTBEAT_SCHEMA,
    bridge_schema = BRIDGE_SCHEMA,
    bridge_id = "HAZEWAVE_REAPER_BRIDGE",
    updated_at = utc_now(),
    status = "STOPPED",
  }
  atomic_write_json(heartbeat_path, payload)
end)

loop()
