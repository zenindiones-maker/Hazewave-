--[[
  Hazewave: Separar Stems (Demucs) — offline, open-source, clean-room.
  UI: gfx panel (ReaImGui-style). Default model htdemucs_6s (6 stems).
  Worker: hazewave_stems_worker.py (background; no Terminal window).
]]

local SCRIPT_DIR = ({reaper.get_action_context()})[2]:match("(.+[\\/])") or ""
local WORKER = SCRIPT_DIR .. "hazewave_stems_worker.py"
local EXT_NS = "HazewaveStems"

local MODE = {
  { id = "6", label = "6 stems (htdemucs_6s)", model = "htdemucs_6s", two = nil },
  { id = "4", label = "4 stems (htdemucs)", model = "htdemucs", two = nil },
  { id = "2", label = "2 stems (voz / instrumental)", model = "htdemucs", two = "vocals" },
}
local mode_idx = 1
local items = {} -- { take_name, item, track, track_idx, checked, position, length }
local running = false
local status_msg = "Selecione itens e aperte SEPARAR"
local progress = 0
local job_dir = nil
local status_path = nil
local err_box = nil

local COL = {
  bg = {0.09, 0.09, 0.11},
  panel = {0.14, 0.14, 0.18},
  text = {0.92, 0.92, 0.94},
  muted = {0.55, 0.55, 0.60},
  accent = {0.00, 0.74, 0.83},
  red = {0.80, 0.12, 0.15},
  red_hot = {0.95, 0.18, 0.20},
  ok = {0.32, 0.82, 0.42},
  check = {0.18, 0.80, 0.55},
}

local function set_color(c, a)
  gfx.set(c[1], c[2], c[3], a or 1)
end

local function fill_round(x, y, w, h, r)
  -- simple rounded rect approx
  gfx.rect(x + r, y, w - 2 * r, h, 1)
  gfx.rect(x, y + r, w, h - 2 * r, 1)
  gfx.circle(x + r, y + r, r, 1, 1)
  gfx.circle(x + w - r, y + r, r, 1, 1)
  gfx.circle(x + r, y + h - r, r, 1, 1)
  gfx.circle(x + w - r, y + h - r, r, 1, 1)
end

local function hit(mx, my, x, y, w, h)
  return mx >= x and my >= y and mx <= x + w and my <= y + h
end

local function python_bin()
  local override = reaper.GetExtState(EXT_NS, "python")
  if override ~= "" then return override end
  local home = os.getenv("HOME") or os.getenv("USERPROFILE") or ""
  local candidates = {
    home .. "/.local/share/hazewave/stems-venv/bin/python",
    home .. "/.local/share/hazewave/stems-venv/Scripts/python.exe",
    "python3",
    "python",
  }
  for _, c in ipairs(candidates) do
    if c == "python3" or c == "python" then return c end
    local f = io.open(c, "r")
    if f then f:close(); return c end
  end
  return "python3"
end

local function project_path()
  local _, path = reaper.EnumProjects(-1, "")
  if not path or path == "" then return nil end
  return path:match("(.+[\\/])")
end

local function stems_out_root()
  local base = project_path()
  if not base then
    base = (os.getenv("TMPDIR") or os.getenv("TEMP") or "/tmp") .. "/HazewaveStems/"
  end
  return base .. "HAZEWAVE_STEMS"
end

local function refresh_items()
  items = {}
  local n = reaper.CountMediaItems(0)
  for i = 0, n - 1 do
    local it = reaper.GetMediaItem(0, i)
    local take = reaper.GetActiveTake(it)
    if take and not reaper.TakeIsMIDI(take) then
      local track = reaper.GetMediaItemTrack(it)
      local track_idx = reaper.GetMediaTrackInfo_Value(track, "IP_TRACKNUMBER") - 1
      local _, tname = reaper.GetSetMediaTrackInfo_String(track, "P_NAME", "", false)
      local _, take_name = reaper.GetSetMediaItemTakeInfo_String(take, "P_NAME", "", false)
      if take_name == "" then
        local src = reaper.GetMediaItemTake_Source(take)
        take_name = reaper.GetMediaSourceFileName(src, "")
        take_name = take_name:match("([^\\/]+)$") or take_name
      end
      local selected = reaper.IsMediaItemSelected(it)
      items[#items + 1] = {
        item = it,
        track = track,
        track_idx = track_idx,
        track_name = tname,
        name = take_name,
        position = reaper.GetMediaItemInfo_Value(it, "D_POSITION"),
        length = reaper.GetMediaItemInfo_Value(it, "D_LENGTH"),
        checked = selected or (#items == 0 and false) or selected,
      }
    end
  end
  -- if nothing selected, check nothing; user must tick. If some selected, those are checked.
  local any_sel = false
  for _, it in ipairs(items) do if reaper.IsMediaItemSelected(it.item) then any_sel = true; break end end
  for _, it in ipairs(items) do
    it.checked = any_sel and reaper.IsMediaItemSelected(it.item) or (not any_sel and false)
  end
end

local function export_item_audio(entry, dest_wav)
  -- Render respecting item trim: glue-copy via CreateTakeFromPCM / simpler: use CF or RenderFileSection.
  -- Portable approach: GetMediaItemTake_Source + PCM_Source_CreateFromType + time selection render via
  -- reaper.GetMediaSourceParent and CF_GetMediaSourceOnline — but SWS may be missing.
  -- Use built-in: set time selection to item, render selected items to file via Main_OnCommand is heavy.
  -- Instead: use GetMediaItemTake_Source file + ffmpeg trim via worker after writing a cue.
  local take = reaper.GetActiveTake(entry.item)
  local src = reaper.GetMediaItemTake_Source(take)
  local src_file = reaper.GetMediaSourceFileName(src, "")
  local offs = reaper.GetMediaItemTakeInfo_Value(take, "D_STARTOFFS")
  local playrate = reaper.GetMediaItemTakeInfo_Value(take, "D_PLAYRATE")
  local length = entry.length
  -- Write a small sidecar JSON so worker can ffmpeg-trim if needed; for full-file items copy path.
  local meta = {
    source = src_file,
    start_offs = offs,
    length = length,
    playrate = playrate,
    dest = dest_wav,
  }
  -- Prefer REAPER's native render of the take section via "Item: Apply track FX to items as new take"
  -- too invasive. Use ffmpeg when available through a tiny helper in the worker.
  return meta
end

local function write_json(path, tbl)
  -- minimal JSON encoder for our structures
  local function esc(s)
    s = tostring(s)
    s = s:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"):gsub("\r", "\\r")
    return '"' .. s .. '"'
  end
  local function enc(v)
    local t = type(v)
    if t == "nil" then return "null"
    elseif t == "boolean" then return v and "true" or "false"
    elseif t == "number" then return string.format("%.12g", v)
    elseif t == "string" then return esc(v)
    elseif t == "table" then
      local is_arr = (#v > 0)
      if is_arr then
        local parts = {}
        for i = 1, #v do parts[i] = enc(v[i]) end
        return "[" .. table.concat(parts, ",") .. "]"
      else
        local parts = {}
        for k, val in pairs(v) do
          parts[#parts + 1] = esc(k) .. ":" .. enc(val)
        end
        return "{" .. table.concat(parts, ",") .. "}"
      end
    end
    return "null"
  end
  local f = assert(io.open(path, "w")); f:write(enc(tbl)); f:close()
end

local function read_json_file(path)
  local f = io.open(path, "r")
  if not f then return nil end
  local s = f:read("*a"); f:close()
  -- tiny parser via reaper or load — use simple field extraction for status
  local state = s:match('"state"%s*:%s*"([^"]+)"')
  local message = s:match('"message"%s*:%s*"([^"]*)"')
  local prog = tonumber(s:match('"progress"%s*:%s*([0-9]+)')) or 0
  return { state = state, message = message, progress = prog, raw = s }
end

local function color_int(hex)
  local r = tonumber(hex:sub(1, 2), 16) or 128
  local g = tonumber(hex:sub(3, 4), 16) or 128
  local b = tonumber(hex:sub(5, 6), 16) or 128
  if reaper.ColorToNative then
    return reaper.ColorToNative(r, g, b) | 0x1000000
  end
  return r + g * 256 + b * 65536
end

local function import_results(raw)
  local tsv_path = job_dir .. "/import.tsv"
  local f = io.open(tsv_path, "r")
  if not f then
    -- wait briefly for worker flush
    for _ = 1, 20 do
      reaper.JS_Sleep and reaper.JS_Sleep(50)
      f = io.open(tsv_path, "r")
      if f then break end
    end
  end
  if not f then return false, "import.tsv ausente (worker não gravou resultados)" end
  local lines = {}
  for line in f:lines() do
    local path, label, color, pos, tidx = line:match("^(.-)\t(.-)\t(.-)\t(.-)\t(.-)$")
    if path then
      lines[#lines + 1] = {
        path = path,
        label = label,
        color = color,
        position = tonumber(pos) or 0,
        track_idx = tonumber(tidx) or 0,
      }
    end
  end
  f:close()
  if #lines == 0 then return false, "import.tsv vazio" end

  reaper.Undo_BeginBlock2(0)
  reaper.PreventUIRefresh(1)
  for _, entry in ipairs(items) do
    if entry.checked then
      reaper.SetMediaItemInfo_Value(entry.item, "B_MUTE", 1)
    end
  end
  local by_track = {}
  for _, ln in ipairs(lines) do
    by_track[ln.track_idx] = by_track[ln.track_idx] or {}
    table.insert(by_track[ln.track_idx], ln)
  end
  local inserted = 0
  local sorted_keys = {}
  for k in pairs(by_track) do sorted_keys[#sorted_keys + 1] = k end
  table.sort(sorted_keys)
  for _, tidx in ipairs(sorted_keys) do
    local offs = 0
    for _, ln in ipairs(by_track[tidx]) do
      local insert_at = tidx + 1 + offs
      reaper.InsertTrackAtIndex(insert_at, true)
      local tr = reaper.GetTrack(0, insert_at)
      reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", ln.label, true)
      reaper.SetTrackColor(tr, color_int(ln.color))
      reaper.SetMediaTrackInfo_Value(tr, "I_HEIGHTOVERRIDE", 150)
      local item = reaper.AddMediaItemToTrack(tr)
      reaper.SetMediaItemInfo_Value(item, "D_POSITION", ln.position)
      local take = reaper.AddTakeToMediaItem(item)
      local pcm = reaper.PCM_Source_CreateFromFile(ln.path)
      if pcm then
        reaper.SetMediaItemTake_Source(take, pcm)
        local len = reaper.GetMediaSourceLength(pcm, false)
        if type(len) == "number" then
          reaper.SetMediaItemInfo_Value(item, "D_LENGTH", len)
        end
        reaper.GetSetMediaItemTakeInfo_String(take, "P_NAME", ln.label, true)
      end
      offs = offs + 1
      inserted = inserted + 1
    end
  end
  reaper.PreventUIRefresh(-1)
  reaper.UpdateArrange()
  reaper.TrackList_AdjustWindows(false)
  reaper.Undo_EndBlock2(0, "Hazewave: Separar Stems (Demucs)", -1)
  return true, inserted
end

local function spawn_worker(job_path)
  local py = python_bin()
  local is_win = reaper.GetOS():match("Win")
  local cmd
  if is_win then
    -- no console window
    cmd = string.format('cmd /c start /b "" "%s" "%s" --job "%s"', py, WORKER, job_path)
  else
    local log = job_dir .. "/worker.log"
    cmd = string.format('"%s" "%s" --job "%s" > "%s" 2>&1 &', py, WORKER, job_path, log)
  end
  -- ExecProcess with 0 waits; use os.execute for background on Unix
  if is_win then
    reaper.ExecProcess(cmd, -1)
  else
    os.execute(cmd)
  end
end

local function prepare_inputs_with_ffmpeg(checked)
  -- Build wavs that respect item trim via ffmpeg (worker also can, but we do it here for clarity)
  local out_root = stems_out_root()
  reaper.RecursiveCreateDirectory(out_root, 0)
  job_dir = out_root .. "/_job_" .. tostring(math.floor(reaper.time_precise() * 1000))
  reaper.RecursiveCreateDirectory(job_dir, 0)
  status_path = job_dir .. "/status.json"
  local inputs = {}
  local py = python_bin()
  for i, entry in ipairs(checked) do
    local take = reaper.GetActiveTake(entry.item)
    local src = reaper.GetMediaItemTake_Source(take)
    local src_file = reaper.GetMediaSourceFileName(src, "")
    local offs = reaper.GetMediaItemTakeInfo_Value(take, "D_STARTOFFS")
    local playrate = reaper.GetMediaItemTakeInfo_Value(take, "D_PLAYRATE")
    local length = entry.length
    local safe = (entry.name or ("item" .. i)):gsub("[^%w%._%-]+", "_")
    local dest = job_dir .. "/" .. safe .. "_in.wav"
    -- Extract trimmed section at playrate≈1; if playrate != 1, still extract wall-clock length from source at offs.
    local src_start = offs
    local src_len = length * (playrate ~= 0 and playrate or 1)
    local ff = string.format(
      'ffmpeg -y -hide_banner -loglevel error -ss %.9f -t %.9f -i "%s" -acodec pcm_f32le "%s"',
      src_start, length, src_file, dest
    )
    -- On Windows use start /b wait? We need sync export before demucs.
    if reaper.GetOS():match("Win") then
      reaper.ExecProcess('cmd /c ' .. ff, 0)
    else
      os.execute(ff)
    end
    local f = io.open(dest, "r")
    if not f then
      -- fallback: copy whole file if ffmpeg missing / failed
      local rf = io.open(src_file, "rb")
      if not rf then return nil, "Não li o áudio fonte: " .. tostring(src_file) end
      local data = rf:read("*a"); rf:close()
      local wf = io.open(dest, "wb"); wf:write(data); wf:close()
    else
      f:close()
    end
    inputs[#inputs + 1] = {
      path = dest,
      out_dir = out_root .. "/" .. safe,
      name = safe,
      position = entry.position,
      track_idx = entry.track_idx,
    }
    reaper.RecursiveCreateDirectory(inputs[#inputs].out_dir, 0)
  end
  local m = MODE[mode_idx]
  local job = {
    model = m.model,
    two_stems = m.two,
    device = "cpu",
    status_path = status_path,
    inputs = inputs,
  }
  local job_path = job_dir .. "/job.json"
  write_json(job_path, job)
  write_json(status_path, { state = "queued", progress = 0, message = "Na fila…" })
  return job_path
end

local function start_separation()
  err_box = nil
  local checked = {}
  for _, it in ipairs(items) do if it.checked then checked[#checked + 1] = it end end
  if #checked == 0 then
    status_msg = "Marque ao menos um item de áudio"
    return
  end
  if not reaper.file_exists(WORKER) then
    status_msg = "Worker ausente: " .. WORKER
    err_box = status_msg
    return
  end
  local job_path, err = prepare_inputs_with_ffmpeg(checked)
  if not job_path then
    status_msg = err or "Falha ao preparar áudio"
    err_box = status_msg
    return
  end
  running = true
  progress = 0
  status_msg = "Demucs rodando (offline)…"
  spawn_worker(job_path)
end

local scroll = 0
local W, H = 520, 560
local last_cap = 0

local function draw()
  local w, h = gfx.w, gfx.h
  set_color(COL.bg); gfx.rect(0, 0, w, h, 1)

  -- header
  set_color(COL.panel); fill_round(12, 12, w - 24, 56, 8)
  set_color(COL.accent); gfx.rect(12, 12, 6, 56, 1)
  set_color(COL.text); gfx.setfont(1, "Arial", 20, "b")
  gfx.x, gfx.y = 28, 22; gfx.drawstr("Hazewave · Separar Stems")
  set_color(COL.muted); gfx.setfont(1, "Arial", 13)
  gfx.x, gfx.y = 28, 46; gfx.drawstr("Demucs offline · zero custo · open source")

  -- mode row
  set_color(COL.panel); fill_round(12, 80, w - 24, 70, 8)
  set_color(COL.text); gfx.setfont(1, "Arial", 14, "b")
  gfx.x, gfx.y = 24, 88; gfx.drawstr("Modo")
  local mx, my = gfx.mouse_x, gfx.mouse_y
  local bx = 24
  for i, m in ipairs(MODE) do
    local bw = 150
    local on = (i == mode_idx)
    if on then set_color(COL.accent) else set_color({0.22, 0.22, 0.28}) end
    fill_round(bx, 112, bw, 28, 6)
    set_color(on and {0.05, 0.05, 0.08} or COL.text)
    gfx.setfont(1, "Arial", 13)
    gfx.x, gfx.y = bx + 10, 118; gfx.drawstr(m.id == "2" and "2 stems" or (m.id .. " stems"))
    if not running and (gfx.mouse_cap & 1 == 1) and (last_cap & 1 == 0) and hit(mx, my, bx, 112, bw, 28) then
      mode_idx = i
    end
    bx = bx + bw + 10
  end

  -- item list
  local list_y = 164
  local list_h = h - 300
  set_color(COL.panel); fill_round(12, list_y, w - 24, list_h, 8)
  set_color(COL.text); gfx.setfont(1, "Arial", 14, "b")
  gfx.x, gfx.y = 24, list_y + 10; gfx.drawstr("Itens do projeto")
  -- select all / none
  set_color(COL.muted); gfx.setfont(1, "Arial", 12)
  gfx.x, gfx.y = w - 180, list_y + 12; gfx.drawstr("[todos]")
  local click = (gfx.mouse_cap & 1 == 1) and (last_cap & 1 == 0)
  if not running and click and hit(mx, my, w - 180, list_y + 8, 50, 18) then
    for _, it in ipairs(items) do it.checked = true end
  end
  gfx.x, gfx.y = w - 120, list_y + 12; gfx.drawstr("[nenhum]")
  if not running and click and hit(mx, my, w - 120, list_y + 8, 60, 18) then
    for _, it in ipairs(items) do it.checked = false end
  end
  gfx.x, gfx.y = w - 50, list_y + 12; gfx.drawstr("↻")
  if not running and click and hit(mx, my, w - 50, list_y + 8, 24, 18) then
    refresh_items()
  end

  local row_h = 28
  local y = list_y + 36 - scroll
  for i, it in ipairs(items) do
    if y > list_y + 28 and y < list_y + list_h - 8 then
      if it.checked then set_color({0.16, 0.22, 0.24}) else set_color({0.12, 0.12, 0.15}) end
      fill_round(22, y, w - 44, row_h - 4, 4)
      -- checkbox
      set_color(it.checked and COL.check or COL.muted)
      gfx.rect(30, y + 6, 16, 16, it.checked and 1 or 0)
      if not it.checked then gfx.rect(30, y + 6, 16, 16, 0) end
      set_color(COL.text); gfx.setfont(1, "Arial", 13)
      local label = string.format("T%d · %s  (%.1fs)", it.track_idx + 1, it.name, it.length)
      gfx.x, gfx.y = 56, y + 6; gfx.drawstr(label:sub(1, 56))
      if not running and click and hit(mx, my, 22, y, w - 44, row_h - 4) then
        it.checked = not it.checked
      end
    end
    y = y + row_h
  end
  if #items == 0 then
    set_color(COL.muted); gfx.x, gfx.y = 30, list_y + 50; gfx.drawstr("Nenhum item de áudio no projeto.")
  end

  -- progress
  local py = h - 120
  set_color(COL.panel); fill_round(12, py, w - 24, 40, 8)
  set_color({0.2, 0.2, 0.25}); fill_round(20, py + 12, w - 40, 16, 4)
  if progress > 0 then
    set_color(COL.ok); fill_round(20, py + 12, math.floor((w - 40) * (progress / 100)), 16, 4)
  end
  set_color(COL.text); gfx.setfont(1, "Arial", 13)
  gfx.x, gfx.y = 24, py - 18; gfx.drawstr(status_msg)

  -- big red button
  local bw, bh = w - 24, 52
  local bx, by = 12, h - 70
  local hot = hit(mx, my, bx, by, bw, bh)
  set_color((hot and not running) and COL.red_hot or COL.red)
  if running then set_color({0.35, 0.18, 0.18}) end
  fill_round(bx, by, bw, bh, 10)
  set_color(COL.text); gfx.setfont(1, "Arial", 22, "b")
  local label = running and "SEPARANDO…" or "SEPARAR STEMS"
  local tw = gfx.measurestr(label)
  gfx.x = (w - tw) / 2; gfx.y = by + 14; gfx.drawstr(label)
  if not running and (gfx.mouse_cap & 1 == 1) and (last_cap & 1 == 0) and hot then
    start_separation()
  end

  if err_box then
    set_color({0.9, 0.3, 0.3}); gfx.setfont(1, "Arial", 12)
    gfx.x, gfx.y = 24, h - 88; gfx.drawstr(err_box:sub(1, 80))
  end
end

local function loop()
  local char = gfx.getchar()
  if char == -1 or char == 27 then return end -- closed / ESC
  if char == 114 or char == 82 then refresh_items() end -- R
  -- mouse click edge
  local cap = gfx.mouse_cap
  draw()
  -- poll worker
  if running and status_path then
    local st = read_json_file(status_path)
    if st then
      progress = st.progress or progress
      if st.message and st.message ~= "" then status_msg = st.message end
      if st.state == "done" then
        running = false
        local ok, info = import_results(st.raw)
        if ok then
          status_msg = string.format("Pronto · %s stems inseridos · originais mutados", tostring(info))
          progress = 100
        else
          status_msg = "Falha ao importar: " .. tostring(info)
          err_box = status_msg
        end
      elseif st.state == "error" then
        running = false
        status_msg = "Erro: " .. (st.message or "?")
        err_box = status_msg
      end
    end
  end
  last_cap = cap
  reaper.defer(loop)
end

-- Optional: open with mode from ExtState (ReaHub / app)
local pref = reaper.GetExtState(EXT_NS, "mode")
if pref == "4" then mode_idx = 2 elseif pref == "2" then mode_idx = 3 else mode_idx = 1 end
reaper.DeleteExtState(EXT_NS, "mode", false)

local auto = reaper.GetExtState(EXT_NS, "auto_start") == "1"
reaper.DeleteExtState(EXT_NS, "auto_start", false)

refresh_items()
if auto then
  for _, it in ipairs(items) do it.checked = true end
  -- Headless: still open a tiny gfx so defer loop runs for progress/import
  gfx.init("Hazewave · Separar Stems", W, H, 0, 200, 120)
  gfx.setfont(1, "Arial", 14)
  start_separation()
  reaper.defer(loop)
else
  gfx.init("Hazewave · Separar Stems", W, H, 0, 200, 120)
  gfx.setfont(1, "Arial", 14)
  reaper.defer(loop)
end
