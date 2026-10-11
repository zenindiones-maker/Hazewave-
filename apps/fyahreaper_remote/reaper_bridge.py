"""Small, synchronous reapy-to-ReaScript adapter for the existing REAPER session.

Never boots REAPER, creates a new session or touches projects without an API request.
"""
from __future__ import annotations

import math
import time
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
    def __init__(self, api=None, context=None, reconnect=None):
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
        self._reconnect = reconnect if reconnect is not None else (self._reapy_reconnect if context is not None else None)

    @staticmethod
    def _reapy_reconnect():
        # reapy keeps one cached socket; after REAPER stalls/restarts it is dead
        # (BrokenPipeError). reapy.reconnect() drops it and reloads reascript_api.
        import reapy
        reapy.reconnect()
        if not reapy.dist_api_is_enabled():
            raise RuntimeError('REAPER_DIST_API_UNAVAILABLE')
        from reapy import reascript_api
        return reascript_api

    def mark_stale(self):
        """Called by ReaHub after a call timed out: reconnect before the next call."""
        self._stale = True

    def _guarded(self, fn, *args, retry=False):
        """Turn transport failures into typed errors; reconnect for the next call.
        Only read-only calls are retried, so a mutation is never applied twice."""
        if getattr(self, '_stale', False) and self._reconnect is not None:
            try:
                api = self._reconnect()
                if api is not None:
                    self.r = api
                self._stale = False
            except Exception as exc:
                raise RuntimeError('REAPER_CONNECTION_LOST') from exc
        try:
            return fn(*args)
        except (OSError, EOFError) as exc:
            lost = exc
        if self._reconnect is None:
            raise RuntimeError('REAPER_CONNECTION_LOST') from lost
        try:
            api = self._reconnect()
            if api is not None:
                self.r = api
        except Exception as exc:
            raise RuntimeError('REAPER_CONNECTION_LOST') from exc
        if not retry:
            raise RuntimeError('REAPER_CONNECTION_LOST_RECONNECTED_RETRY') from lost
        try:
            return fn(*args)
        except (OSError, EOFError) as exc:
            raise RuntimeError('REAPER_CONNECTION_LOST') from exc

    def _state(self):
        state = int(self.r.GetPlayState())
        return 'recording' if state & 4 else ('playing' if state & 1 else ('paused' if state & 2 else 'stopped'))

    def _health_impl(self):
        version = self.r.GetAppVersion()
        return {'reaper_connected': bool(version), 'reaper_version': str(version), 'state': self._state()}

    def _transport_impl(self, action):
        state = self._state()
        if action == 'rec':
            if state == 'recording':
                return {'state': state}
            if not any(bool(self.r.GetMediaTrackInfo_Value(self.r.GetTrack(0,i),'I_RECARM'))
                       for i in range(int(self.r.CountTracks(0)))):
                raise ValueError('NO_TRACK_ARMED')
            self.r.Main_OnCommand(1013,0)
            for _ in range(20):
                if self._state() == 'recording':
                    break
                time.sleep(0.05)
            else:
                # Do not report success when REAPER silently refuses (e.g. no audio device).
                raise RuntimeError('REC_NOT_STARTED')
        elif action == 'play':
            if state in ('playing','recording'):
                return {'state':state}
            self.r.Main_OnCommand(1007,0)
        elif action == 'stop':
            if state == 'stopped':
                return {'state':state}
            # 1016 opens the modal "keep recorded media?" prompt when recording, which
            # blocks REAPER's main thread (and the reapy server). 40667 = Transport:
            # Stop (save all recorded media) ends recording without a dialog.
            self.r.Main_OnCommand(40667 if state == 'recording' else 1016,0)
        else:
            raise ValueError('UNKNOWN_TRANSPORT_ACTION')
        return {'state':self._state()}

    def _guid(self, track):
        # GetTrackGUID returns an opaque '(GUID*)0x...' pointer over the dist API;
        # the stable '{...}' string comes from GetSetMediaTrackInfo_String.
        res = self.r.GetSetMediaTrackInfo_String(track,'GUID','',False)
        guid = res[3] if isinstance(res,(list,tuple)) else res
        if not (isinstance(guid,str) and guid.startswith('{')):
            raise RuntimeError('TRACK_GUID_UNAVAILABLE')
        return guid

    def _by_guid(self, guid):
        for i in range(int(self.r.CountTracks(0))):
            track = self.r.GetTrack(0,i)
            if self._guid(track) == guid:
                return track
        raise KeyError(guid)

    def _snapshot(self, track):
        _,_,name,*_ = self.r.GetTrackName(track,'',512)
        return {
            'id':self._guid(track),
            'name':str(name),
            'mute':bool(self.r.GetMediaTrackInfo_Value(track,'B_MUTE')),
            'solo':bool(self.r.GetMediaTrackInfo_Value(track,'I_SOLO')),
            'armed':bool(self.r.GetMediaTrackInfo_Value(track,'I_RECARM')),
            'volume':round(float(self.r.GetMediaTrackInfo_Value(track,'D_VOL')),6),
        }

    def _tracks_impl(self):
        with self._context():
            return [self._snapshot(self.r.GetTrack(0,i)) for i in range(int(self.r.CountTracks(0)))]

    def _set_track_impl(self, guid, update):
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

    def _create_midi_impl(self, request):
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
                # Real reapy 0.10 / reaper_python returns
                # [item, track, start, end, qnIn] because qnIn is an optional pointer arg.
                if isinstance(midi_item,(list,tuple)):
                    midi_item = midi_item[0] if midi_item else None
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
                return {'notes_created':len(request.notes),'track_id':self._guid(created),
                        'position_seconds':start}
            except Exception:
                if not _is_null(created):
                    r.DeleteTrack(created)
                raise
            finally:
                r.PreventUIRefresh(-1)
                r.Undo_EndBlock2(0,'FyahReaper Remote: create MIDI below selected sample',-1)

    def health(self):
        return self._guarded(self._health_impl, retry=True)

    def tracks(self):
        return self._guarded(self._tracks_impl, retry=True)

    def transport(self, action):
        return self._guarded(self._transport_impl, action)

    def set_track(self, guid, update):
        return self._guarded(self._set_track_impl, guid, update)

    def create_midi(self, request):
        return self._guarded(self._create_midi_impl, request)
