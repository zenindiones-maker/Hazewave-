from reaper_bridge import ReaperBridge
from reahub_server import MidiRequest, Note
import pytest

class RPR:
    def __init__(self):
        self.tracks=[{'guid':'{source}','name':'Sample','I_RECARM':0,'D_VOL':1.0,'B_MUTE':0,'I_SOLO':0}]
        self.state=0
        self.created=[]
        self.fx=-1
        self.selected_item={'position':0.0,'duration':1.0,'track':self.tracks[0]}
    def GetAppVersion(self): return '7.82'
    def GetPlayState(self): return self.state
    def CountTracks(self,p): return len(self.tracks)
    def GetTrack(self,p,i): return self.tracks[i]
    def GetTrackGUID(self,t):return '(GUID*)0x1'
    def GetSetMediaTrackInfo_String(self,t,k,v,setnew):return [True,t,k,t['guid'],setnew]
    def GetTrackName(self,t,n,s):return (True,t,t['name'],s)
    def GetMediaTrackInfo_Value(self,t,key):
        return (self.tracks.index(t)+1) if key=='IP_TRACKNUMBER' else t[key]
    def SetMediaTrackInfo_Value(self,t,key,val): t[key]=val;return True
    def TrackList_AdjustWindows(self,x): pass
    def Main_OnCommand(self,action,flag): self.cmds=getattr(self,'cmds',[])+[action];self.state={1013:5,1016:0,40667:0,1007:1,40029:self.state,40030:self.state}[action]
    def CountSelectedMediaItems(self,p):return 1
    def GetSelectedMediaItem(self,p,i):return self.selected_item
    def GetActiveTake(self,item):return item.get('take',{'midi':False})
    def TakeIsMIDI(self,take):return take['midi']
    def GetMediaItemTrack(self,item):return item['track']
    def GetMediaItemInfo_Value(self,item,key):return item['position'] if key=='D_POSITION' else item['duration']
    def Undo_BeginBlock2(self,p): pass
    def Undo_EndBlock2(self,*x): pass
    def PreventUIRefresh(self,x): pass
    def InsertTrackAtIndex(self,i,x):self.tracks.insert(i,{'guid':'{new}','name':'MIDI','I_RECARM':0,'D_VOL':1.0,'B_MUTE':0,'I_SOLO':0})
    def TrackFX_AddByName(self,*a):return self.fx
    def CreateNewMIDIItemInProj(self,t,start,end,qn):return [{'take':{'midi':True,'events':[]}},t,start,end,0]
    def MIDI_DisableSort(self,take): pass
    def MIDI_GetPPQPosFromProjTime(self,take,sec):return sec*960.0
    def MIDI_InsertNote(self,take,selected,muted,a,b,chan,pitch,velocity,no_sort):
        take['events'].append((pitch,a,b));self.created.append(pitch);self.events=take['events'];return True
    def MIDI_Sort(self,take):pass
    def MIDI_CountEvts(self,take,*others):return (True,take,len(take['events']),0,0)
    def UpdateArrange(self):pass
    def DeleteTrack(self,t):self.tracks.remove(t)

def test_real_reascript_shape_transport_and_fader():
    api=RPR();bridge=ReaperBridge(api=api)
    with pytest.raises(ValueError,match='NO_TRACK_ARMED'): bridge.transport('rec')
    bridge.set_track('{source}',{'armed':True,'volume':0.5})
    assert bridge.tracks()[0]['volume']==0.5
    assert bridge.transport('rec')['state']=='recording'
    assert bridge.transport('stop')['state']=='stopped'

def test_native_midi_three_notes_track_below_source():
    api=RPR();api.fx=0;bridge=ReaperBridge(api=api)
    req=MidiRequest(notes=[Note(pitch=36,start=0,duration=.2),Note(pitch=40,start=.25,duration=.2),Note(pitch=43,start=.5,duration=.2)])
    receipt=bridge.create_midi(req)
    assert receipt['notes_created']==3
    assert api.created==[36,40,43]
    assert api.tracks[0]['guid']=='{source}' and api.tracks[1]['guid']=='{new}'

def test_jsfx_missing_does_not_leave_track():
    api=RPR();bridge=ReaperBridge(api=api)
    req=MidiRequest(notes=[Note(pitch=36,start=0,duration=.2)])
    with pytest.raises(ValueError,match='JSFX_MISSING'):bridge.create_midi(req)
    assert len(api.tracks)==1

def test_note_outside_item_does_not_mutate_project():
    api=RPR();api.fx=0;bridge=ReaperBridge(api=api)
    req=MidiRequest(notes=[Note(pitch=36,start=.95,duration=.2)])
    with pytest.raises(ValueError,match='NOTE_OUTSIDE'):bridge.create_midi(req)
    assert len(api.tracks)==1

NULL_TAKE='(MediaItem_Take*)0x0000000000000000'

def test_null_pointer_string_take_is_rejected():
    api=RPR();api.fx=0;api.selected_item['take']=NULL_TAKE
    api.TakeIsMIDI=lambda take: (_ for _ in ()).throw(AssertionError('must not deref NULL'))
    req=MidiRequest(notes=[Note(pitch=36,start=0,duration=.2)])
    with pytest.raises(ValueError,match='SELECTED_TAKE_NOT_AUDIO'):ReaperBridge(api=api).create_midi(req)
    assert len(api.tracks)==1

def test_null_created_midi_take_rolls_back_track():
    api=RPR();api.fx=0
    api.CreateNewMIDIItemInProj=lambda *a:[{'take':NULL_TAKE},None,0,1,0]
    api.GetActiveTake=lambda item:item.get('take',{'midi':False}) if item is api.selected_item else NULL_TAKE
    req=MidiRequest(notes=[Note(pitch=36,start=0,duration=.2)])
    with pytest.raises(RuntimeError,match='MIDI_TAKE_CREATE_FAILED'):ReaperBridge(api=api).create_midi(req)
    assert len(api.tracks)==1

def test_is_null_helper():
    from reaper_bridge import _is_null
    assert _is_null(None) and _is_null('') and _is_null(NULL_TAKE)
    assert not _is_null('(MediaTrack*)0x00007f1234567890') and not _is_null({'x':1})

def test_rec_refused_by_reaper_is_reported_not_silent():
    api=RPR();api.Main_OnCommand=lambda a,f:None
    b=ReaperBridge(api=api);b.set_track('{source}',{'armed':True})
    with pytest.raises(RuntimeError,match='REC_NOT_STARTED'):b.transport('rec')

def test_track_id_is_stable_guid_string_not_pointer():
    assert ReaperBridge(api=RPR()).tracks()[0]['id']=='{source}'

def test_stop_while_recording_saves_without_modal_prompt():
    api=RPR();b=ReaperBridge(api=api);b.set_track('{source}',{'armed':True})
    b.transport('rec');assert b.transport('stop')['state']=='stopped'
    assert api.cmds==[1013,40667]

def test_three_note_spec_timing_maps_to_exact_ppq():
    api=RPR();api.fx=0
    req=MidiRequest(notes=[Note(pitch=36,start=0,duration=.2),Note(pitch=40,start=.25,duration=.2),Note(pitch=43,start=.5,duration=.2)])
    ReaperBridge(api=api).create_midi(req)
    # fake converter: 960 PPQ per second, item starts at 0
    assert api.events==[(36,0.0,192.0),(40,240.0,432.0),(43,480.0,672.0)]

def test_broken_pipe_reconnects_and_health_recovers():
    dead=RPR();dead.GetAppVersion=lambda:(_ for _ in ()).throw(BrokenPipeError(32,'Broken pipe'))
    fresh=RPR();calls=[]
    b=ReaperBridge(api=dead,reconnect=lambda:(calls.append(1),fresh)[1])
    assert b.health()['reaper_connected'] is True and calls==[1]

def test_broken_pipe_on_mutation_is_typed_and_not_retried():
    dead=RPR();dead.CountTracks=lambda p:(_ for _ in ()).throw(BrokenPipeError())
    fresh=RPR();fresh.Main_OnCommand=lambda *a:(_ for _ in ()).throw(AssertionError('must not retry'))
    b=ReaperBridge(api=dead,reconnect=lambda:fresh)
    with pytest.raises(RuntimeError,match='REAPER_CONNECTION_LOST'):b.transport('rec')
    assert b.r is fresh

def test_reconnect_failure_is_typed():
    dead=RPR();dead.GetAppVersion=lambda:(_ for _ in ()).throw(ConnectionResetError())
    def boom():raise ConnectionRefusedError()
    with pytest.raises(RuntimeError,match='REAPER_CONNECTION_LOST'):ReaperBridge(api=dead,reconnect=boom).health()

def test_server_maps_connection_loss_to_503():
    from reahub_server import app_factory
    from fastapi.testclient import TestClient
    dead=RPR();dead.GetAppVersion=lambda:(_ for _ in ()).throw(BrokenPipeError())
    def boom():raise OSError()
    tok='x'*32;c=TestClient(app_factory(ReaperBridge(api=dead,reconnect=boom),tok))
    r=c.get('/health',headers={'Authorization':'Bearer '+tok})
    assert r.status_code==503

def test_hung_reaper_call_times_out_503_marks_stale_and_recovers():
    import threading, time
    from reahub_server import app_factory
    from fastapi.testclient import TestClient
    release=threading.Event()
    hung=RPR();hung.GetAppVersion=lambda:(release.wait(5),'7.82')[1]
    fresh=RPR();calls=[]
    b=ReaperBridge(api=hung,reconnect=lambda:(calls.append(1),fresh)[1])
    tok='y'*32;c=TestClient(app_factory(b,tok,call_timeout=0.3));H={'Authorization':'Bearer '+tok}
    t0=time.time();r=c.get('/health',headers=H)
    assert r.status_code==503 and r.json()['detail']=='REAPER_TIMEOUT' and time.time()-t0<2
    r=c.get('/health',headers=H)
    assert r.status_code==200 and r.json()['reaper_connected'] and calls==[1]
    release.set()

def test_mutations_stay_serialized():
    import threading, time
    from reahub_server import app_factory
    from fastapi.testclient import TestClient
    api=RPR();active=[0];peak=[0]
    orig=api.SetMediaTrackInfo_Value
    def slow(*a):
        active[0]+=1;peak[0]=max(peak[0],active[0]);time.sleep(0.05);active[0]-=1;return orig(*a)
    api.SetMediaTrackInfo_Value=slow
    tok='z'*32;c=TestClient(app_factory(ReaperBridge(api=api),tok,call_timeout=5));H={'Authorization':'Bearer '+tok}
    ts=[threading.Thread(target=lambda:c.patch('/api/tracks/{source}',json={'mute':True},headers=H)) for _ in range(6)]
    [t.start() for t in ts];[t.join() for t in ts]
    assert peak[0]==1

# --- Contract tests replaying the exact request shapes MainActivity.kt sends ---
def _app_client():
    from reahub_server import app_factory
    from fastapi.testclient import TestClient
    api=RPR();tok='k'*32
    return TestClient(app_factory(ReaperBridge(api=api),tok)),{'Authorization':'Bearer '+tok},api

def test_app_patch_with_urlencoded_guid_and_json_body():
    import urllib.parse
    c,H,api=_app_client()
    url='/api/tracks/'+urllib.parse.quote_plus('{source}')   # URLEncoder.encode(id,"UTF-8")
    r=c.patch(url,content='{"armed":true}',headers={**H,'Content-Type':'application/json; charset=utf-8'})
    assert r.status_code==200 and r.json()['armed'] is True

def test_app_transport_post_with_empty_json_body_returns_state():
    c,H,api=_app_client()
    hdr={**H,'Content-Type':'application/json; charset=utf-8'}
    r=c.post('/api/transport/rec',content='{}',headers=hdr)
    assert r.status_code==409 and r.json()['detail']=='NO_TRACK_ARMED'
    c.patch('/api/tracks/%7Bsource%7D',content='{"armed":true}',headers=hdr)
    assert c.post('/api/transport/rec',content='{}',headers=hdr).json()['state']=='recording'
    assert c.post('/api/transport/stop',content='{}',headers=hdr).json()['state']=='stopped'
    assert c.post('/api/transport/play',content='{}',headers=hdr).json()['state']=='playing'

def test_app_websocket_receives_transport_frames():
    c,H,api=_app_client()
    with c.websocket_connect('/ws',headers=H) as ws:
        m=ws.receive_json()
    assert m['type']=='transport' and m['state']=='stopped'

def test_app_undo_redo_allowlisted_actions():
    c,H,api=_app_client();hdr={**H,'Content-Type':'application/json; charset=utf-8'}
    assert c.post('/api/edit/undo',content='{}',headers=hdr).json()['command_id']==40029
    assert c.post('/api/edit/redo',content='{}',headers=hdr).json()['command_id']==40030
    assert c.post('/api/edit/delete_everything',content='{}',headers=hdr).status_code==422
    assert api.cmds==[40029,40030]
