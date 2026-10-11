-- Standalone Lua syntax and pure-function regression suite.
-- This is NOT proof of execution inside REAPER; use live workstation proof.
local dir=arg[1] or "reaper/FyahGrabber"
local core=dofile(dir.."/FyahGrabber_Core.lua")
local wav=dofile(dir.."/FyahGrabber_AudioExport.lua")

local ctx={position=6,duration=3.0,tracknumber=2}
local notes={
  core.note(36,0.0,0.25),
  core.note(40,0.50,0.25),
  core.note(43,1.00,0.50),
}
assert(core.track_insert_index(ctx)==2)
local result=core.plan(ctx,notes,function(x) return (x-ctx.position)*960 end)
assert(#result==3)
assert(result[1].pitch==36 and result[1].start_ppq==0 and result[1].end_ppq==240)
assert(result[2].pitch==40 and result[2].start_ppq==480)
assert(result[3].pitch==43 and result[3].end_ppq==1440)
local ok=pcall(core.plan,ctx,{core.note(60,2.95,0.5)},function(x) return x*960 end)
assert(not ok,"NOTE_OUTSIDE_ITEM_MUST_FAIL")

local path=os.tmpname()
os.remove(path)
local sampleCalls=0
local r={
  file_exists=function(f) return false end,
  CreateTakeAudioAccessor=function(take) return {tag="test"} end,
  DestroyAudioAccessor=function(accessor) assert(accessor.tag=="test") end,
  new_array=function(size)
    local arr={};arr.clear=function()
      for i=1,size do arr[i]=0 end
    end
    return arr
  end,
  GetAudioAccessorSamples=function(accessor,sr,ch,pos,n,buf)
    sampleCalls=sampleCalls+1
    assert(sr==16000 and ch==1 and n<=4096)
    for i=1,n do buf[i]=math.sin(2*math.pi*110*(pos+(i-1)/sr))*.25 end
    return 1
  end,
}
local receipt=wav.export_take(r,{},8,0.5,path)
assert(receipt.frames==8000)
assert(sampleCalls>=2)
local f=assert(io.open(path,"rb"))
local bytes=f:read("*a");f:close();os.remove(path)
assert(#bytes==16044 and bytes:sub(1,4)=="RIFF" and bytes:sub(9,12)=="WAVE")
assert(bytes:sub(37,40)=="data")
print("FYAH_CORE_AND_WAV_EXPORT_TESTS=PASS notes=3 frames=8000")
