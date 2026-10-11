"""Small, synchronous reapy-to-ReaScript adapter for the existing REAPER session.

Never boots REAPER, creates a new session or touches projects without an API request.
"""
from __future__ import annotations

import math
from contextlib import nullcontext


def _is_null(ptr):
    """reapy dist API returns pointers as strings like '(MediaTrack*)0x0000000000000000',
    which are truthy; treat those (and None/empty) as NULL."""
    if not ptr:
        return True
    if isinstance(ptr, str) and ')0x' in ptr:
        try:
            return int(ptr.rsplit('0x', 1)[1], 16) == 0
        except ValueError:
            return False
    return False


class ReaperBridge:
    def __init__(self, api=None, context=None):
        if api is None:
            try:
                import reapy
                from reapy import reascript_api as api
            except ImportError as exc:
                raise RuntimeError('python-reapy not installed on workstation') from exc
            if not reapy.is_inside_reaper() and not reapy.dist_api_is_enabled():
                # reapy 0.10.0 defines no reascript_api functions and inside_reaper()
                # dereferences a None client when the distant API is unreachable.
                raise RuntimeError('REAPER_DIST_API_UNAVAILABLE')
            context = reapy.inside_reaper
        self.r = api
        self._context = context or (lambda: nullcontext())

    def _state(self):
        state = int(self.r.GetPlayState())
        return 'recording' if state & 4 else ('playing' if state & 1 else ('paused' if state & 2 else 'stopped'))

    def health(self):
        version = self.r.GetAppVersion()
        return {'reaper_connected': bool(version), 'reaper_version': str(version), 'state': self._state()}

    def transport(self, action):
        state = self._state()
        if action == 'rec':
            if state == 'recording':
                return {'state': state}
            if not any(bool(self.r.GetMediaTrackInfo_Value(self.r.GetTrack(0,i),'I_RECARM'))
                       for i in range(int(self.r.CountTracks(0)))):
                raise ValueError('NO_TRACK_ARMED')
            self.r.Main_OnCommand(1013,0)
        elif action == 'play':
            if state in ('playing','recording'):
                return {'state':state}
            self.r.Main_OnCommand(1007,0)
        elif action == 'stop':
            if state == 'stopped':
                return {'state':state}
            self.r.Main_OnCommand(1016,0)
        else:
            raise ValueError('UNKNOWN_TRANSPORT_ACTION')
        return {'state':self._state()}

    def _by_guid(self, guid):
        for i in range(int(self.r.CountTracks(0))):
            track = self.r.GetTrack(0,i)
            if str(self.r.GetTrackGUID(track)) == guid:
                return track
        raise KeyError(guid)

    def _snapshot(self, track):
        _,_,name,*_ = self.r.GetTrackName(track,'',512)
        return {
            'id':str(self.r.GetTrackGUID(track)),
            'name':str(name),
            'mute':bool(self.r.GetMediaTrackInfo_Value(track,'B_MUTE')),
            'solo':bool(self.r.GetMediaTrackInfo_Value(track,'I_SOLO')),
            'armed':bool(self.r.GetMediaTrackInfo_Value(track,'I_RECARM')),
            'volume':round(float(self.r.GetMediaTrackInfo_Value(track,'D_VOL')),6),
        }

    def tracks(self):
        with self._context():
            return [self._snapshot(self.r.GetTrack(0,i)) for i in range(int(self.r.CountTracks(0)))]

    def set_track(self, guid, update):
        with self._context():
            track = self._by_guid(guid)
            for name,param in (('mute','B_MUTE'),('solo','I_SOLO'),('armed','I_RECARM'),('volume','D_VOL')):
                if name in update:
                    value = update[name]
                    if name == 'volume' and (not math.isfinite(value) or value<0 or value>4):
                        raise ValueError('INVALID_VOLUME')
                    changed = self.r.SetMediaTrackInfo_Value(track, param, float(value))
                    if not changed:
                        raise RuntimeError('REAPER_TRACK_UPDATE_FAILED')
            self.r.TrackList_AdjustWindows(False)
            return self._snapshot(track)

    def create_midi(self, request):
        if self._state() == 'recording':
            raise ValueError('TRANSPORT_RECORDING')
        with self._context():
            r = self.r
            if int(r.CountSelectedMediaItems(0)) != 1:
                raise ValueError('SELECT_EXACTLY_ONE_AUDIO_ITEM')
            source = r.GetSelectedMediaItem(0,0)
            if _is_null(source):
                raise ValueError('SELECT_EXACTLY_ONE_AUDIO_ITEM')
            source_take = r.GetActiveTake(source)
            if _is_null(source_take) or r.TakeIsMIDI(source_take):
                raise ValueError('SELECTED_TAKE_NOT_AUDIO')
            track = r.GetMediaItemTrack(source)
            index = int(r.GetMediaTrackInfo_Value(track,'IP_TRACKNUMBER'))
            start = float(r.GetMediaItemInfo_Value(source,'D_POSITION'))
            duration = float(r.GetMediaItemInfo_Value(source,'D_LENGTH'))
            if not (0 < duration <= 3600 and index >= 1):
                raise ValueError('INVALID_SELECTED_ITEM')
            for note in request.notes:
                if note.start+note.duration > duration+1e-7:
                    raise ValueError('NOTE_OUTSIDE_SELECTED_ITEM')
            created = None
            r.Undo_BeginBlock2(0)
            r.PreventUIRefresh(1)
            try:
                r.InsertTrackAtIndex(index, True)
                created = r.GetTrack(0,index)
                if _is_null(created):
                    raise RuntimeError('MIDI_TRACK_INSERT_FAILED')
                fx = r.TrackFX_AddByName(created,'JS: FyahGrabber 808 Instrument',False,-1)
                if int(fx) < 0:
                    raise ValueError('FYAHGRABBER_808_JSFX_MISSING')
                midi_item = r.CreateNewMIDIItemInProj(created,start,start+duration,False)
                if _is_null(midi_item):
                    raise RuntimeError('MIDI_TAKE_CREATE_FAILED')
                take = r.GetActiveTake(midi_item)
                if _is_null(take) or not r.TakeIsMIDI(take):
                    raise RuntimeError('MIDI_TAKE_CREATE_FAILED')
                r.MIDI_DisableSort(take)
                for n in request.notes:
                    a = float(r.MIDI_GetPPQPosFromProjTime(take,start+n.start))
                    b = float(r.MIDI_GetPPQPosFromProjTime(take,start+n.start+n.duration))
                    if not (math.isfinite(a) and math.isfinite(b) and b>a):
                        raise ValueError('PPQ_CONVERSION_FAILED')
                    if not r.MIDI_InsertNote(take,False,False,a,b,0,n.pitch,n.velocity,True):
                        raise RuntimeError('MIDI_INSERT_FAILED')
                r.MIDI_Sort(take)
                counted = r.MIDI_CountEvts(take,0,0,0)
                if int(counted[2]) != len(request.notes):
                    raise RuntimeError('MIDI_READBACK_COUNT_MISMATCH')
                r.UpdateArrange()
                return {'notes_created':len(request.notes),'track_id':str(r.GetTrackGUID(created)),
                        'position_seconds':start}
            except Exception:
                if not _is_null(created):
                    r.DeleteTrack(created)
                raise
            finally:
                r.PreventUIRefresh(-1)
                r.Undo_EndBlock2(0,'FyahReaper Remote: create MIDI below selected sample',-1)
