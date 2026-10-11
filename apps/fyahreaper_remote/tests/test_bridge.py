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
    def GetTrackGUID(self,t):return t['guid']
    def GetTrackName(self,t,n,s):return (True,t,t['name'],s)
    def GetMediaTrackInfo_Value(self,t,key):
        return (self.tracks.index(t)+1) if key=='IP_TRACKNUMBER' else t[key]
    def SetMediaTrackInfo_Value(self,t,key,val): t[key]=val;return True
    def TrackList_AdjustWindows(self,x): pass
    def Main_OnCommand(self,action,flag): self.state={1013:4,1016:0,1007:1}[action]
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
    def CreateNewMIDIItemInProj(self,t,start,end,qn):return {'take':{'midi':True,'events':[]}}
    def MIDI_DisableSort(self,take): pass
    def MIDI_GetPPQPosFromProjTime(self,take,sec):return sec*960.0
    def MIDI_InsertNote(self,take,selected,muted,a,b,chan,pitch,velocity,no_sort):
        take['events'].append((pitch,a,b));self.created.append(pitch);return True
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
    api.CreateNewMIDIItemInProj=lambda *a:{'take':NULL_TAKE}
    api.GetActiveTake=lambda item:item.get('take',{'midi':False}) if item is api.selected_item else NULL_TAKE
    req=MidiRequest(notes=[Note(pitch=36,start=0,duration=.2)])
    with pytest.raises(RuntimeError,match='MIDI_TAKE_CREATE_FAILED'):ReaperBridge(api=api).create_midi(req)
    assert len(api.tracks)==1

def test_is_null_helper():
    from reaper_bridge import _is_null
    assert _is_null(None) and _is_null('') and _is_null(NULL_TAKE)
    assert not _is_null('(MediaTrack*)0x00007f1234567890') and not _is_null({'x':1})
