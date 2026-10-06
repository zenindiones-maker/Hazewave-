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
local heartbeat_path = bridge_root .. "/heartbeat.json"

reaper.RecursiveCreateDirectory(requests_dir, 0)
reaper.RecursiveCreateDirectory(processing_dir, 0)
reaper.RecursiveCreateDirectory(responses_dir, 0)
reaper.RecursiveCreateDirectory(checkpoint_root, 0)

local ARRAY_MT = {}
local JSON_NULL = {}

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
