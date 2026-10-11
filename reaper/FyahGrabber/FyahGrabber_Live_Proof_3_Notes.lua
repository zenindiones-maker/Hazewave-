-- @description FyahGrabber Open - Live REAPER 3-note API proof (selected audio)
-- @version 0.1.0
-- @author Hazewave
-- @about Test only on a disposable REAPER project. Emits local receipt, not a human-paint speed proof.
local r=reaper
if not r then error("REAPER_RUNTIME_REQUIRED") end
local _,path=r.get_action_context()
local folder=path:match("^(.*[\\/])") or ""
local core=dofile(folder.."FyahGrabber_Core.lua")
local function q(v) return '"'..tostring(v):gsub('\\','\\\\'):gsub('"','\\"')..'"' end
local function blocked(s)
  r.MB("FYAH REAPER LIVE PROOF BLOCKED:\n"..s,"FyahGrabber",0)
end
local function run()
  assert(r.GetAppVersion() and r.GetOS(), "NOT_REAPER_RUNTIME")
  assert(r.CountSelectedMediaItems(0)==1,"SELECT_EXACTLY_ONE_AUDIO_ITEM")
  local item=r.GetSelectedMediaItem(0,0)
  local source=r.GetActiveTake(item)
  assert(source and not r.TakeIsMIDI(source),"SELECTED_TAKE_NOT_AUDIO")
  local track=r.GetMediaItemTrack(item)
  local start=r.GetMediaItemInfo_Value(item,"D_POSITION")
  local duration=r.GetMediaItemInfo_Value(item,"D_LENGTH")
  local tracknum=math.floor(r.GetMediaTrackInfo_Value(track,"IP_TRACKNUMBER"))
  assert(duration>=0.75, "SELECT_ITEM_LONGER_THAN_750MS")
  local ctx={position=start,duration=duration,tracknumber=tracknum}
  core.validate_context(ctx)
  local notes={
    core.note(36,0.00,0.25),
    core.note(40,0.25,0.25),
    core.note(43,0.50,0.25),
  }
  local t0=r.time_precise()
  local created=nil
  r.Undo_BeginBlock2(0)
  r.PreventUIRefresh(1)
  local ok,err=pcall(function()
    r.InsertTrackAtIndex(core.track_insert_index(ctx),true)
    created=r.GetTrack(0,core.track_insert_index(ctx))
    assert(created,"FAILED_TO_CREATE_MIDI_TRACK")
    local fx=r.TrackFX_AddByName(created,"JS: FyahGrabber 808 Instrument",false,-1)
    assert(fx and fx>=0,"FYAH_808_NOT_INSTALLED_IN_REAPER_EFFECTS")
    local midi=r.CreateNewMIDIItemInProj(created,start,start+duration,false)
    assert(midi and r.GetActiveTake(midi),"NO_MIDI_TAKE")
    local take=r.GetActiveTake(midi)
    assert(r.TakeIsMIDI(take),"CREATED_TAKE_IS_NOT_MIDI")
    local planned=core.plan(ctx,notes,function(t)
      return r.MIDI_GetPPQPosFromProjTime(take,t)
    end)
    r.MIDI_DisableSort(take)
    for _,event in ipairs(planned) do
      assert(r.MIDI_InsertNote(take,false,false,event.start_ppq,
        event.end_ppq,0,event.pitch,event.velocity,true),
        "MIDI_INSERT_FAILED")
    end
    r.MIDI_Sort(take)
    local _,count=r.MIDI_CountEvts(take)
    assert(count==3,"REAPER_DID_NOT_SAVE_3_NOTES")
    for i=0,2 do
      local exists,_,_,startppq,endppq,_,pitch=r.MIDI_GetNote(take,i)
      assert(exists and endppq>startppq, "REAPER_MIDI_NOTE_CORRUPTED")
      assert(({36,40,43})[i+1]==pitch,"REAPER_WRONG_PITCH")
    end
    r.GetSetMediaTrackInfo_String(created,"P_NAME",
      "FyahGrabber PROOF • MIDI + 808",true)
    r.UpdateArrange()
  end)
  if not ok and created then r.DeleteTrack(created) end
  r.PreventUIRefresh(-1)
  r.Undo_EndBlock2(0,ok and "FyahGrabber: live 3-note proof" or
    "FyahGrabber: rollback failed proof",-1)
  if not ok then error(err) end
  local elapsed=r.time_precise()-t0
  local receipt={
    schema="FyahGrabberLiveReaperReceipt/v1",
    status="REAPER_API_3_NOTES_PASS",
    reaper_version=r.GetAppVersion(),
    operating_system=r.GetOS(),
    notes_count=3,
    new_track_below=true,
    jsfx_808_attached=true,
    api_execution_seconds=elapsed,
    human_paint_under_10s="NOT_MEASURED",
    workstation="existing_codespace_only",
    publication_attempted=false,
  }
  local output=r.GetResourcePath().."/FyahGrabber-live-proof.json"
  local file=assert(io.open(output,"w"),"CANNOT_WRITE_PROOF_RECEIPT")
  file:write("{\n")
  file:write('"schema":'..q(receipt.schema)..',\n')
  file:write('"status":'..q(receipt.status)..',\n')
  file:write('"reaper_version":'..q(receipt.reaper_version)..',\n')
  file:write('"operating_system":'..q(receipt.operating_system)..',\n')
  file:write('"notes_count":3,\n"new_track_below":true,\n"jsfx_808_attached":true,\n')
  file:write('"api_execution_seconds":'..string.format("%.6f",elapsed)..',\n')
  file:write('"human_paint_under_10s":"NOT_MEASURED",\n')
  file:write('"publication_attempted":false\n}\n')
  file:close()
  r.MB(("REAPER 3-NOTE API PASS\nAPI time %.3fs\nReceipt: %s\n"
    .."Human paint 10s: NOT MEASURED."):format(elapsed,output),"FyahGrabber",0)
end
local ok,err=pcall(run)
if not ok then blocked(tostring(err)) end
