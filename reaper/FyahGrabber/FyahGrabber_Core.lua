-- FYAHGRABBER OPEN: deterministic, REAPER-independent note planning (MIT).
local M = {}
local function finite(x)
  return type(x) == "number" and x == x and x ~= math.huge and x ~= -math.huge
end
function M.validate_context(ctx)
  assert(type(ctx)=="table" and finite(ctx.position) and ctx.position>=0, "INVALID_ITEM_POSITION")
  assert(finite(ctx.duration) and ctx.duration>0 and ctx.duration<=3600, "INVALID_ITEM_DURATION")
  assert(type(ctx.tracknumber)=="number" and ctx.tracknumber>=1
         and ctx.tracknumber%1==0, "INVALID_TRACK_NUMBER")
  return true
end
function M.note(pitch,start,duration)
  assert(finite(pitch) and pitch%1==0 and pitch>=0 and pitch<=127,"INVALID_PITCH")
  assert(finite(start) and start>=0, "INVALID_NOTE_START")
  assert(finite(duration) and duration>0, "INVALID_NOTE_DURATION")
  return {pitch=pitch,start=start,duration=duration,velocity=100}
end
function M.plan(ctx,notes,project_to_ppq)
  M.validate_context(ctx)
  assert(type(project_to_ppq)=="function","PPQ_CONVERTER_REQUIRED")
  assert(type(notes)=="table" and #notes>0 and #notes<=2048,"NOTE_COUNT_OUT_OF_BOUNDS")
  local result={}
  for i,n in ipairs(notes) do
    assert(finite(n.pitch) and n.pitch%1==0 and n.pitch>=0 and n.pitch<=127,
           "INVALID_PITCH")
    assert(finite(n.start) and finite(n.duration) and n.start>=0 and n.duration>0,
           "INVALID_TIME")
    assert(n.start+n.duration<=ctx.duration+1e-7,"NOTE_OUTSIDE_SELECTED_ITEM")
    local a,b=project_to_ppq(ctx.position+n.start),
              project_to_ppq(ctx.position+n.start+n.duration)
    assert(finite(a) and finite(b) and a>=0 and b>a, "INVALID_PPQ_CONVERSION")
    result[#result+1]={pitch=n.pitch,velocity=math.max(1,math.min(127,
      math.floor(tonumber(n.velocity) or 100))),
      start_ppq=a,end_ppq=b}
  end
  table.sort(result,function(a,b)
    return a.start_ppq<b.start_ppq or
      (a.start_ppq==b.start_ppq and a.pitch<b.pitch)
  end)
  return result
end
function M.track_insert_index(ctx)
  M.validate_context(ctx)
  return ctx.tracknumber -- source track number is one-based, insertion index is zero-based.
end
function M.grid_note(y,top,cell,high,low)
  assert(finite(y) and finite(top) and finite(cell) and cell>0)
  local pitch=high-math.floor((y-top)/cell)
  return math.max(low,math.min(high,pitch))
end
function M.grid_time(x,left,pixels_per_second,item_seconds,step)
  assert(finite(x) and pixels_per_second>0 and step>0 and item_seconds>0)
  local value=math.max(0,(x-left)/pixels_per_second)
  return math.min(item_seconds, math.floor(value/step+0.5)*step)
end
return M
