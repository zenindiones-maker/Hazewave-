-- FyahGrabber Open: safely extract the selected REAPER take pre-FX to mono WAV.
-- Supports decoded source formats using REAPER's own audio accessor (MP3/FLAC/etc).
-- This file does not alter the active REAPER project or external original audio.
local M={}
local SR=16000
local FRAMES_PER_CHUNK=4096
local function put32(n) return string.pack("<I4",n) end
local function pcm16(v)
  if v~=v or v==math.huge or v==-math.huge then error("NONFINITE_AUDIO_VALUE") end
  return string.pack("<i2",math.max(-32768,math.min(32767,
    math.floor(math.max(-1,math.min(1,v))*32767+0.5))))
end
function M.export_take(r,take,position,duration,filename)
  assert(r and r.CreateTakeAudioAccessor and r.GetAudioAccessorSamples,
    "REAPER_AUDIO_ACCESSOR_UNAVAILABLE")
  assert(type(filename)=="string" and #filename>0 and not filename:find("%z"),
    "INVALID_WAV_OUTPUT")
  assert(type(position)=="number" and position>=0 and position==position,
    "INVALID_ITEM_POSITION")
  assert(type(duration)=="number" and duration>0 and duration<=20 and duration==duration,
    "AUDIO_DURATION_OUT_OF_BOUNDS")
  assert(not r.file_exists(filename),"WAV_DESTINATION_ALREADY_EXISTS")
  local sample_count=math.floor(duration*SR+0.5)
  assert(sample_count>=1 and sample_count<=SR*20,"SAMPLE_COUNT_OUT_OF_BOUNDS")
  local accessor=r.CreateTakeAudioAccessor(take)
  assert(accessor,"CANNOT_CREATE_TAKE_AUDIO_ACCESSOR")
  local output,success=io.open(filename,"wb")
  if not output then r.DestroyAudioAccessor(accessor);error("WAV_OPEN_FAILED") end
  local ok,err=pcall(function()
    output:write("RIFF",put32(36+sample_count*2),"WAVEfmt ",
      put32(16),string.pack("<I2I2I4I4I2I2",1,1,SR,SR*2,2,16),
      "data",put32(sample_count*2))
    local block=r.new_array(FRAMES_PER_CHUNK)
    local written=0
    while written<sample_count do
      local n=math.min(FRAMES_PER_CHUNK,sample_count-written)
      block.clear() -- REAPER numeric array userdata supports clear()
      local result=r.GetAudioAccessorSamples(
        accessor,SR,1,position+written/SR,n,block)
      assert(result==1,"AUDIO_ACCESSOR_NO_AUDIO_OR_ERROR")
      local chunk={}
      for i=1,n do chunk[i]=pcm16(block[i]) end
      output:write(table.concat(chunk))
      written=written+n
    end
  end)
  output:close()
  r.DestroyAudioAccessor(accessor)
  if not ok then os.remove(filename);error(err) end
  return {path=filename,sample_rate=SR,channels=1,duration=duration,
          frames=sample_count,byte_count=sample_count*2+44}
end
return M
