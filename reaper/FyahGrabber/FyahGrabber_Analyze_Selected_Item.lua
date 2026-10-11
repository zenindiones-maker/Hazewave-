-- @description FyahGrabber Open - Analyze Selected Item (REAPER-first)
-- @version 0.1.0
-- @author Hazewave
-- @about MIT licensed original ReaScript. Paint notes, then CREATE MIDI BELOW.
-- @provides
--   FyahGrabber_Core.lua
--   FyahGrabber_808.jsfx
--   fyahgrabber_analyze.py
-- @changelog
--   Initial REAPER-native authoring: actual MIDI item, JSFX 808, bounded CQT bridge.
local r = reaper
if not r or not gfx then error("REAPER_AND_GFX_REQUIRED") end
local _, own = r.get_action_context()
local sep = package.config:sub(1,1)
local dir = own:match("^(.*[\\/])") or ""
local core = dofile(dir .. "FyahGrabber_Core.lua")
local TITLE = "FyahGrabber Open · REAPER"
local top, left, pitch_h, lo, hi = 142, 104, 9, 36, 84
local source_item, ctx, source_file
local painted, previous, draft = {}, {}, nil
local cursor_down = false
local png_loaded, image_slot = false, 7
local status = "Clique e arraste para pintar notas; CREATE MIDI BELOW insere MIDI tocando 808."
local last_midi_created = nil

local function fail(message)
  status = tostring(message)
  r.ShowConsoleMsg("FYAHGRABBER: "..status.."\n")
end
local function context()
  if r.CountSelectedMediaItems(0) ~= 1 then
    return nil,"Selecione exatamente UM item de áudio."
  end
  local item = r.GetSelectedMediaItem(0,0)
  local take = r.GetActiveTake(item)
  if not take or r.TakeIsMIDI(take) then return nil,"A seleção precisa ser áudio." end
  local src = r.GetMediaItemTake_Source(take)
  local filename = src and r.GetMediaSourceFileName(src)
  if not filename or filename=="" then return nil,"Sem arquivo-fonte externo válido." end
  local tr = r.GetMediaItemTrack(item)
  local out = {
    item=item, take=take, src=src,
    position=r.GetMediaItemInfo_Value(item,"D_POSITION"),
    duration=r.GetMediaItemInfo_Value(item,"D_LENGTH"),
    tracknumber=math.floor(r.GetMediaTrackInfo_Value(tr,"IP_TRACKNUMBER")),
    offset=r.GetMediaItemTakeInfo_Value(take,"D_STARTOFFS"),
    rate=r.GetMediaItemTakeInfo_Value(take,"D_PLAYRATE"),
    pitch=r.GetMediaItemTakeInfo_Value(take,"D_PITCH"),
    filename=filename,
  }
  local ok,err=pcall(core.validate_context,out)
  if not ok then return nil,err end
  if out.duration>20 then
    return nil,"MVP: selecione um trecho de até 20 s (split antes)."
  end
  return out
end

local function get_seconds_per_grid() return .125 end
local function px_per_s()
  return math.max(15,(gfx.w-left-24)/ctx.duration)
end
local function selected_ok()
  return r.ValidatePtr2(0,ctx.item,"MediaItem*") and
         r.ValidatePtr2(0,ctx.take,"MediaItem_Take*")
end

local function create_midi()
  if #painted<1 then return fail("Pinte uma nota pelo menos; 3 notas são o teste de aceite.") end
  if not selected_ok() then return fail("Item foi removido: reinicie o script.") end
  local source_track=r.GetMediaItemTrack(ctx.item)
  local fx_name="JS: FyahGrabber 808 Instrument"
  r.Undo_BeginBlock2(0)
  r.PreventUIRefresh(1)
  local created_track
  local ok,err=pcall(function()
    local track_index=core.track_insert_index(ctx)
    r.InsertTrackAtIndex(track_index, true)
    created_track=r.GetTrack(0,track_index)
    assert(created_track,"CANNOT_CREATE_MIDI_TRACK")
    local fx_index=r.TrackFX_AddByName(created_track,fx_name,false,-1)
    assert(fx_index and fx_index>=0,
      "FYAH_808_JSFX_MISSING: instale FyahGrabber_808.jsfx em Effects")
    local start,end_time=ctx.position,ctx.position+ctx.duration
    local item=r.CreateNewMIDIItemInProj(created_track,start,end_time,false)
    assert(item,"CREATE_MIDI_ITEM_FAILED")
    local take=r.GetActiveTake(item)
    assert(take and r.TakeIsMIDI(take),"MIDI_TAKE_NOT_CREATED")
    local notes=core.plan(ctx,painted,function(t)
      return r.MIDI_GetPPQPosFromProjTime(take,t)
    end)
    r.MIDI_DisableSort(take)
    for _,n in ipairs(notes) do
      assert(r.MIDI_InsertNote(take,false,false,n.start_ppq,n.end_ppq,0,
                n.pitch,n.velocity,true),"MIDI_INSERT_NOTE_FAILED")
    end
    r.MIDI_Sort(take)
    local _,note_count=r.MIDI_CountEvts(take)
    assert(note_count==#notes,"MIDI_COUNT_MISMATCH")
    r.GetSetMediaTrackInfo_String(created_track,"P_NAME","FyahGrabber • 808 MIDI",true)
    r.GetSetMediaItemTakeInfo_String(take,"P_NAME","Fyah • painted MIDI",true)
    r.SetMediaItemSelected(item,true)
    r.UpdateItemInProject(item)
    r.UpdateArrange()
    last_midi_created=r.time_precise()
  end)
  if not ok and created_track then r.DeleteTrack(created_track) end
  r.PreventUIRefresh(-1)
  r.Undo_EndBlock2(0,ok and ("FyahGrabber: "..#painted.." notes -> 808 track") or
    "FyahGrabber: rolled back failed creation",-1)
  if ok then
    status=("MIDI CRIADO • %d notas em faixa com 808. Verifique áudio na DAW."):format(#painted)
  else fail(err) end
end

local function safequote(p)
  if type(p)~="string" or p=="" or p:find('["\r\n]') then
    error("UNSAFE_COMMAND_PATH")
  end
  return '"'..p..'"'
end
local function analyze_source()
  if not selected_ok() then return fail("Selecionado mudou: reinicie.") end
  if math.abs(ctx.rate-1)>1e-6 or math.abs(ctx.pitch)>1e-6 then
    return fail("CQT exige rate 1 e pitch 0. Faça Glue no item e selecione novamente.")
  end
  if not r.file_exists(ctx.filename) then return fail("Arquivo-fonte não está disponível.") end
  local python=r.GetExtState("FyahGrabber","PYTHON")
  if python=="" then
    local ok,input=r.GetUserInputs("Python local do FyahGrabber",1,
      "Caminho absoluto do python.exe:", "")
    if not ok then return end
    python=input
    if not r.file_exists(python) then return fail("Python inválido.") end
    r.SetExtState("FyahGrabber","PYTHON",python,true)
  end
  if not r.file_exists(python) then return fail("Python não encontrado.") end
  local cache=r.GetResourcePath()..sep.."FyahGrabber-cache"
  r.RecursiveCreateDirectory(cache,0)
  -- Source hash validation and processing are delegated to local sidecar.
  local input=ctx.filename
  local path_png=cache..sep.."last-cqt.png"
  local output=cache..sep.."last-analysis.tsv"
  local command
  local ok,err=pcall(function()
    command=safequote(python).." "..safequote(dir.."fyahgrabber_analyze.py")
      .." --source "..safequote(input)
      .." --offset "..string.format("%.6f",ctx.offset)
      .." --duration "..string.format("%.6f",ctx.duration)
      .." --png "..safequote(path_png)
      .." --tsv "..safequote(output)
  end)
  if not ok then return fail(err) end
  status="Analisando CQT... (pode demorar, limite 20 segundos)"
  gfx.update()
  local result=r.ExecProcess(command,20000)
  if not result or not result:match("^0\n") then
    return fail("Análise falhou ou excedeu limite; use pintura manual. "..tostring(result or ""))
  end
  local handle=io.open(output,"r")
  if not handle then return fail("Analisador não produziu TSV.") end
  local first=handle:read("*l")
  handle:close()
  if first~="FYAH_CQT_V1" then
    return fail("TSV não corresponde ao protocolo esperado.")
  end
  png_loaded=gfx.loadimg(image_slot,path_png)>=0
  status=png_loaded and "CQT carregado; pinte notas sobre o mapa." or
    "CQT calculado, mas REAPER não carregou PNG."
end

local buttons={
  {key="analyze",title="ANALYZE CQT",x=15,w=135,fn=analyze_source},
  {key="create",title="CREATE MIDI BELOW",x=165,w=195,fn=create_midi},
  {key="erase",title="UNDO NOTE",x=375,w=125,fn=function()
    if #painted>0 then table.remove(painted); status="Última nota removida." end
  end},
  {key="clear",title="CLEAR",x=515,w=100,fn=function()
    painted={};status="Notas removidas." end},
}
local function fill(r1,g1,b1)
  gfx.set(r1,g1,b1,1)
end
local function box(x,y,w,h,r1,g1,b1)
  fill(r1,g1,b1);gfx.rect(x,y,w,h,true)
end
local function text(x,y,s)
  gfx.x=x;gfx.y=y;gfx.drawstr(s)
end
local function draw()
  box(0,0,gfx.w,gfx.h,.048,.073,.105)
  fill(.29,.89,.76);gfx.setfont(1,"Arial",22);text(14,13,"FYAHGRABBER OPEN")
  fill(.66,.74,.83);gfx.setfont(1,"Arial",12)
  text(14,43,"REAPER FIRST • ORIGINAL OPEN-SOURCE WORKFLOW • NOT noteGRABBER2")
  for _,b in ipairs(buttons) do
    box(b.x,72,b.w,36,b.key=="create" and .15 or .13,
        b.key=="create" and .52 or .27,b.key=="create" and .44 or .37)
    fill(1,1,1);gfx.setfont(1,"Arial",12);text(b.x+8,83,b.title)
  end
  fill(.71,.79,.87);text(15,121,("Selecionado: %.2fs   |   %d notas  |  Arraste horizontal para pintar"):format(ctx.duration,#painted))
  local width=gfx.w-left-20
  local height=(hi-lo+1)*pitch_h
  box(left,top,width,height,.07,.11,.155)
  -- Optional CQT image is visualization only, never treated as pitch truth.
  if png_loaded then
    gfx.a=.42;gfx.blit(image_slot,1,0,0,0,0,0,left,top,width,height);gfx.a=1
  end
  for pitch=lo,hi do
    local y=top+(hi-pitch)*pitch_h
    if pitch%12==0 then box(0,y,gfx.w,1,.21,.28,.34)
    elseif pitch%12==1 or pitch%12==3 or pitch%12==6 or pitch%12==8 or pitch%12==10 then
      box(0,y,left-1,pitch_h,.095,.13,.17)
    end
    if pitch%12==0 then fill(.66,.74,.82);text(12,y-2,"C"..tostring(math.floor(pitch/12)-1)) end
  end
  for t=0,math.ceil(ctx.duration/get_seconds_per_grid()) do
    local x=left+t*get_seconds_per_grid()*px_per_s()
    if x>gfx.w-15 then break end
    fill(t%8==0 and .29 or .15,t%8==0 and .35 or .20,t%8==0 and .42 or .26)
    gfx.line(x,top,x,top+height)
  end
  local function draw_note(n,r1,g1,b1)
    local x=left+n.start*px_per_s()
    local y=top+(hi-n.pitch)*pitch_h
    if n.pitch>=lo and n.pitch<=hi then
      box(x,y,math.max(3,n.duration*px_per_s()-2),pitch_h-1,r1,g1,b1)
    end
  end
  for _,n in ipairs(painted)do draw_note(n,.99,.55,.26)end
  if draft then draw_note(draft,.51,.92,.70)end
  fill(.72,.82,.88);gfx.setfont(1,"Arial",12)
  text(15,gfx.h-51,status:sub(1,125))
  fill(.4,.51,.61);text(15,gfx.h-27,
    "BASIS: selected media item -> paint pitches -> native MIDI + bundled 808 JSFX | MIT")
end
local function on_click(x,y)
  for _,b in ipairs(buttons) do
    if y>=72 and y<=108 and x>=b.x and x<=b.x+b.w then
      b.fn();return true
    end
  end
  return false
end
local function window_loop()
  if not selected_ok() then gfx.quit();return end
  local char=gfx.getchar()
  if char<0 or char==27 then gfx.quit();return end
  local down=(gfx.mouse_cap & 1)==1
  local x,y=gfx.mouse_x,gfx.mouse_y
  local within=x>=left and x<gfx.w-17 and y>=top and y<top+(hi-lo+1)*pitch_h
  if down and not cursor_down then
    if not on_click(x,y) and within then
      local pitch=core.grid_note(y,top,pitch_h,hi,lo)
      local start=core.grid_time(x,left,px_per_s(),ctx.duration,get_seconds_per_grid())
      if start<ctx.duration then
        draft=core.note(pitch,start,math.min(.25,ctx.duration-start))
      end
    end
  elseif down and cursor_down and draft then
    local end_time=core.grid_time(x,left,px_per_s(),ctx.duration,get_seconds_per_grid())
    draft.duration=math.max(get_seconds_per_grid(),math.min(ctx.duration-draft.start,
      end_time-draft.start))
  elseif not down and cursor_down and draft then
    painted[#painted+1]=draft
    draft=nil
    status=("Nota pintada: %d. CREATE MIDI BELOW para enviar ao Reaper."):format(#painted)
  end
  cursor_down=down
  draw()
  gfx.update()
  r.defer(window_loop)
end
local out,err=context()
if not out then
  r.MB(err,TITLE,0)
else
  source_item=out.item;ctx=out;source_file=out.filename
  gfx.init(TITLE,920,680,0)
  window_loop()
end
