-- @description FyahGrabber Open - disposable real REAPER host E2E
-- @version 0.2.0
-- This script MUST run ONLY with FYAH_E2E_ISOLATED=1 in a new empty REAPER instance.
-- It writes files only within FYAH_E2E_DIR and never opens/saves existing projects.
local r=reaper
if not r then error("REAPER_HOST_REQUIRED") end
local dir=os.getenv("FYAH_E2E_DIR")
local isolated=os.getenv("FYAH_E2E_ISOLATED")
if isolated~="1" or not dir or #dir<8 or dir:sub(1,1)~="/" or dir:find("[%c]") then
  error("FYAH_ISOLATION_NOT_AUTHORIZED")
end
local function q(s)
  return '"'..tostring(s):gsub("\\","\\\\"):gsub('"','\\"'):gsub("\n","\\n")..'"'
end
local function receipt(status, detail, elapsed)
  local file,err=io.open(dir.."/reaper-host-proof.json","wb")
  if not file then error("EVIDENCE_OUTPUT_FAILED:"..tostring(err)) end
  file:write("{\n",'"schema":"FyahReaperHostProof/v1",\n',
    '"status":',q(status),',\n',
    '"reaper_version":',q(r.GetAppVersion()),',\n',
    '"host_os":',q(r.GetOS()),',\n',
    '"detail":',q(detail),',\n',
    '"api_elapsed_seconds":',string.format("%.6f",elapsed or 0),',\n',
    '"three_notes_verified":',status=="PASS" and "true" or "false",',\n',
    '"jsfx_808_present":',status=="PASS" and "true" or "false",',\n',
    '"human_paint_under_10_seconds":"NOT_MEASURED",\n',
    '"publication_attempted":false\n}\n')
  file:close()
end

local begin=r.time_precise()
local function test()
  assert(r.CountTracks(0)==0 and r.CountMediaItems(0)==0,
    "CANNOT_RUN_WITH_NONEMPTY_PROJECT")
  local _,action=r.get_action_context()
  local folder=type(action)=="string" and action:match("^(.*[\\/])")
  assert(folder,"SCRIPT_PATH_NOT_RESOLVED")
  local core=dofile(folder.."FyahGrabber_Core.lua")
  local export=dofile(folder.."FyahGrabber_AudioExport.lua")
  -- Original test signal generated in this isolated project, NOT user audio.
  local path=dir.."/source-110hz.wav"
  local f=assert(io.open(path,"wb"))
  local rate,frames=16000,16000
  f:write("RIFF",string.pack("<I4",36+frames*2),"WAVEfmt ",
    string.pack("<I4",16),string.pack("<I2I2I4I4I2I2",1,1,rate,rate*2,2,16),
    "data",string.pack("<I4",frames*2))
  for i=0,frames-1 do
    f:write(string.pack("<i2",math.floor(math.sin(i*2*math.pi*110/rate)*12000)))
  end
  f:close()
  r.InsertTrackAtIndex(0,true)
  local src_track=assert(r.GetTrack(0,0),"NO_AUDIO_TRACK")
  local item=assert(r.AddMediaItemToTrack(src_track),"CANNOT_CREATE_AUDIO_ITEM")
  local take=assert(r.AddTakeToMediaItem(item),"CANNOT_CREATE_AUDIO_TAKE")
  local src=assert(r.PCM_Source_CreateFromFile(path),"WAV_SOURCE_INVALID")
  r.SetMediaItemTake_Source(take,src)
  r.SetMediaItemInfo_Value(item,"D_POSITION",0)
  r.SetMediaItemInfo_Value(item,"D_LENGTH",1.0)
  r.SetMediaItemSelected(item,true)
  r.UpdateItemInProject(item)
  -- Exercise actual REAPER accessor before attempting to create 808 MIDI.
  local pcm=dir.."/selected-pre-fx.wav"
  local signal=export.export_take(r,take,0,1,pcm)
  assert(signal.frames==rate and signal.byte_count==44+rate*2,
    "REAL_REAPER_ACCESSOR_BROKEN")
  local testfile=assert(io.open(pcm,"rb"))
  local bytes=testfile:read("*a");testfile:close()
  assert(#bytes==44+rate*2 and bytes:sub(1,4)=="RIFF","REAL_WAV_EXPORT_INVALID")
  local nonzero=false
  for k=80,120,2 do
    if bytes:byte(k) and bytes:byte(k)~=0 then nonzero=true end
  end
  assert(nonzero,"REAL_AUDIO_ACCESSOR_EMPTY")
  -- True REAPER MIDI item and VST-like JSFX insertion.
  local ctx={position=0,duration=1,tracknumber=1}
  local notes={
    core.note(36,0.0,0.2),core.note(40,0.25,0.2),
    core.note(43,0.5,0.2),
  }
  r.InsertTrackAtIndex(core.track_insert_index(ctx),true)
  local track=assert(r.GetTrack(0,1),"NO_NEW_MIDI_TRACK")
  local fx=r.TrackFX_AddByName(track,"JS: FyahGrabber 808 Instrument",false,-1)
  assert(fx and fx>=0,"FYAH_808_JSFX_NOT_RESOLVED")
  local midiitem=assert(r.CreateNewMIDIItemInProj(track,0,1,false),
    "CANNOT_CREATE_MIDI_ITEM")
  local miditake=assert(r.GetActiveTake(midiitem),"NO_NEW_MIDI_TAKE")
  assert(r.TakeIsMIDI(miditake),"WRONG_TAKE_TYPE")
  local planned=core.plan(ctx,notes,function(t)
    return r.MIDI_GetPPQPosFromProjTime(miditake,t)
  end)
  r.MIDI_DisableSort(miditake)
  for _,n in ipairs(planned) do
    assert(r.MIDI_InsertNote(miditake,false,false,
      n.start_ppq,n.end_ppq,0,n.pitch,n.velocity,true),"MIDI_INSERT_FAILED")
  end
  r.MIDI_Sort(miditake)
  local _,count=r.MIDI_CountEvts(miditake)
  assert(count==3,"MIDI_READBACK_NOTE_COUNT_NOT_THREE")
  for i=0,2 do
    local exists,_,_,a,b,chan,pitch=r.MIDI_GetNote(miditake,i)
    assert(exists and b>a and chan==0 and pitch==({36,40,43})[i+1],
      "MIDI_READBACK_WRONG_NOTE")
  end
  assert(r.CountTracks(0)==2 and r.GetTrack(0,1)==track,
    "CREATED_TRACK_NOT_DIRECTLY_BELOW_SOURCE")
  assert(r.TrackFX_GetCount(track)>=1,"JSFX_NOT_PERSISTING")
  r.UpdateArrange()
  return ("MIDI3_PASS; FX_INDEX=%d; SOURCE_AUDIO_NONZERO; PPQ_OK; "..
    "TRACK_BELOW; WAV_FRAMES=%d"):format(fx,signal.frames)
end

local ok,result=pcall(test)
local elapsed=r.time_precise()-begin
receipt(ok and "PASS" or "FAIL",tostring(result),elapsed)
-- Distinguish function of the host API from actual 10-second human painting.
r.ShowConsoleMsg("FYAH_DISPOSABLE_E2E="..(ok and "PASS" or "FAIL")..
  " elapsed="..string.format("%.3f",elapsed).." details="..tostring(result).."\n")
