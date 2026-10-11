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
            for name,param in (('mute','B_MUTE'),('solo','I_SOLO'),('armed','I_RECARM'),('volume','D_VOL'),('pan','D_PAN')):
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

    # Allowlisted REAPER actions only: Edit: Undo (40029) / Edit: Redo (40030).
    _EDIT_ACTIONS = {'undo': 40029, 'redo': 40030}

    def _edit_impl(self, action):
        if action not in self._EDIT_ACTIONS:
            raise ValueError('UNKNOWN_EDIT_ACTION')
        self.r.Main_OnCommand(self._EDIT_ACTIONS[action], 0)
        return {'action': action, 'command_id': self._EDIT_ACTIONS[action], 'state': self._state()}

    def edit(self, action):
        return self._guarded(self._edit_impl, action)


    # Touch actions: fixed allowlist of REAPER command IDs (never arbitrary IDs from the client).
    TOUCH_ACTIONS = {
        'play': 1007, 'stop': 1016, 'record': 1013, 'loop': 1068, 'undo': 40029, 'redo': 40030,
        'split': 40012, 'delete': 40697, 'zoom_in_h': 1012, 'zoom_out_h': 1011, 'zoom_in_v': 40111,
        'zoom_out_v': 40112, 'zoom_project': 40295, 'zoom_item': 41622, 'scroll_left': 40140,
        'scroll_right': 40141, 'scroll_up': 40138, 'scroll_down': 40139, 'insert_track': 40001,
        'arm_selected': 9, 'metronome': 40364, 'mixer': 40078, 'midi_editor': 40153,
        'select_all_items': 40182, 'toolbar_arrange': 41105, 'toolbar_edit': 41106, 'unselect_items': 40289, 'marker': 40157, 'save': 40026,
    }
    TOUCH_TRACK_HEIGHT = 150

    def _action_impl(self, name, repeat=1):
        if name not in self.TOUCH_ACTIONS:
            raise ValueError('UNKNOWN_ACTION')
        repeat = max(1, min(int(repeat), 8))
        cmd = self.TOUCH_ACTIONS[name]
        for _ in range(repeat):
            self.r.Main_OnCommand(cmd, 0)
        if name == 'insert_track':
            t = self.r.GetSelectedTrack(0, 0)
            if not _is_null(t):
                self.r.SetMediaTrackInfo_Value(t, 'I_HEIGHTOVERRIDE', self.TOUCH_TRACK_HEIGHT)
                self.r.TrackList_AdjustWindows(False)
        return {'action': name, 'command_id': cmd, 'repeat': repeat, 'state': self._state()}

    def action(self, name, repeat=1):
        return self._guarded(self._action_impl, name, repeat)

    def _move_impl(self, delta_px, commit, x=None, y=None):
        """Move selected items by a horizontal screen delta (REAPER arrange pixels).
        With x/y (screen px of the REAPER display) first grab the item under that point; no item there -> no-op."""
        r = self.r
        if x is not None and y is not None:
            hit = r.GetItemFromPoint(int(x), int(y), False, None)
            hit = hit[0] if isinstance(hit, (list, tuple)) else hit
            if _is_null(hit):
                return {'moved': 0, 'delta_seconds': 0.0, 'grabbed': False}
            if not r.IsMediaItemSelected(hit):
                r.SelectAllMediaItems(0, False)
                r.SetMediaItemSelected(hit, True)
                r.UpdateArrange()
        n = int(r.CountSelectedMediaItems(0))
        if n == 0:
            return {'moved': 0, 'delta_seconds': 0.0}
        dpx = max(-4000.0, min(4000.0, float(delta_px)))
        zoom = float(r.GetHZoomLevel()) or 100.0
        dt = dpx / zoom
        items = [r.GetSelectedMediaItem(0, i) for i in range(n)]
        first = min(float(r.GetMediaItemInfo_Value(it, 'D_POSITION')) for it in items)
        if first + dt < 0:
            dt = -first
        if dt:
            r.PreventUIRefresh(1)
            for it in items:
                r.SetMediaItemInfo_Value(it, 'D_POSITION', float(r.GetMediaItemInfo_Value(it, 'D_POSITION')) + dt)
            r.PreventUIRefresh(-1)
            r.UpdateArrange()
        if commit:
            r.Undo_OnStateChange('FyahReaper Remote: move items (touch)')
        return {'moved': n, 'delta_seconds': dt, 'zoom_px_per_s': zoom}

    def move_selected(self, delta_px, commit=False, x=None, y=None):
        return self._guarded(self._move_impl, delta_px, commit, x, y)


    # ---- touch mixer -------------------------------------------------------------------------------
    @staticmethod
    def _db(v):
        return -150.0 if v <= 1e-8 else 20.0 * math.log10(v)

    def _mixer_impl(self):
        r = self.r
        out = []
        for i in range(int(r.CountTracks(0))):
            t = r.GetTrack(0, i)
            name = r.GetTrackName(t, '', 512)
            name = name[2] if isinstance(name, (list, tuple)) else name
            col = int(r.GetMediaTrackInfo_Value(t, 'I_CUSTOMCOLOR'))
            rgb = None
            if col & 0x1000000:
                rr, gg, bb = r.ColorFromNative(col & 0xFFFFFF, 0, 0, 0)[1:4] if hasattr(r, 'ColorFromNative') else (col & 0xFF, (col >> 8) & 0xFF, (col >> 16) & 0xFF)
                rgb = '#%02x%02x%02x' % (rr, gg, bb)
            vol = float(r.GetMediaTrackInfo_Value(t, 'D_VOL'))
            out.append({
                'id': self._guid(t), 'number': i + 1, 'name': name or f'Track {i + 1}', 'color': rgb,
                'volume': vol, 'volume_db': round(self._db(vol), 2), 'pan': float(r.GetMediaTrackInfo_Value(t, 'D_PAN')),
                'mute': bool(r.GetMediaTrackInfo_Value(t, 'B_MUTE')), 'solo': bool(r.GetMediaTrackInfo_Value(t, 'I_SOLO')),
                'armed': bool(r.GetMediaTrackInfo_Value(t, 'I_RECARM')),
                'peak_db': [round(self._db(float(r.Track_GetPeakInfo(t, ch))), 1) for ch in (0, 1)],
            })
        m = r.GetMasterTrack(0)
        mv = float(r.GetMediaTrackInfo_Value(m, 'D_VOL'))
        return {'tracks': out, 'master': {'volume': mv, 'volume_db': round(self._db(mv), 2),
                'peak_db': [round(self._db(float(r.Track_GetPeakInfo(m, ch))), 1) for ch in (0, 1)]},
                'state': self._state()}

    def mixer(self):
        return self._guarded(self._mixer_impl, retry=True)

    # ---- smooth, finger-anchored arrange zoom/pan ----------------------------------------------------
    ARRANGE_LEFT_DEFAULT = 695  # REAPER display px where the arrange view starts; refined by _calibrate_left

    def _view_impl(self, factor, anchor_x, pan_px):
        r = self.r
        v = r.GetSet_ArrangeView2(0, False, 0, 0, 0, 0)
        start, end = float(v[4]), float(v[5])
        hz = float(r.GetHZoomLevel()) or 100.0
        left = getattr(self, '_arr_left', self.ARRANGE_LEFT_DEFAULT)
        span = max(1e-3, end - start)
        at = start + max(0.0, anchor_x - left) / hz
        frac = min(1.0, max(0.0, (at - start) / span))
        new_span = min(4 * 3600.0, max(0.05, span / float(factor)))
        ns = at - frac * new_span - float(pan_px) / hz
        ns = max(0.0, ns)
        r.GetSet_ArrangeView2(0, True, 0, 0, ns, ns + new_span)
        return {'start': ns, 'end': ns + new_span, 'anchor_seconds': at}

    def view_zoom(self, factor=1.0, anchor_x=0, pan_px=0.0):
        return self._guarded(self._view_impl, factor, anchor_x, pan_px)

    # ---- direct manipulation of items (MOVER) -------------------------------------------------------
    EDGE_PX = 44  # grab zone for trim handles, REAPER px (~6 mm on the phone)

    def _hit(self, x, y):
        h = self.r.GetItemFromPoint(int(x), int(y), False, None)
        h = h[0] if isinstance(h, (list, tuple)) else h
        return None if _is_null(h) else h

    def _edge(self, item, x, y, step):
        """Last px (walking by `step`) where `item` is still under the finger -> item screen edge."""
        lo, hi = 0, 4096
        while lo < hi:  # find largest d with item still hit at x + step*d
            mid = (lo + hi + 1) // 2
            px = x + step * mid
            if 0 <= px <= 16383 and self._hit(px, y) == item:
                lo = mid
            else:
                hi = mid - 1
        return x + step * lo

    def _drag_impl(self, phase, x, y):
        r = self.r
        if phase == 'grab':
            self._drag = None
            item = self._hit(x, y)
            if item is None:
                return {'grabbed': False}
            if not r.IsMediaItemSelected(item):
                r.SelectAllMediaItems(0, False)
                r.SetMediaItemSelected(item, True)
            hz = float(r.GetHZoomLevel()) or 100.0
            pos = float(r.GetMediaItemInfo_Value(item, 'D_POSITION'))
            length = float(r.GetMediaItemInfo_Value(item, 'D_LENGTH'))
            lpx, rpx = self._edge(item, x, y, -1), self._edge(item, x, y, +1)
            v = r.GetSet_ArrangeView2(0, False, 0, 0, 0, 0)
            self._arr_left = int(round(lpx - (pos - float(v[4])) * hz)) if pos >= float(v[4]) else getattr(self, '_arr_left', self.ARRANGE_LEFT_DEFAULT)
            edge = min(self.EDGE_PX, max(8, (rpx - lpx) // 3))
            mode = 'trim_left' if x - lpx <= edge else ('trim_right' if rpx - x <= edge else 'move')
            items = [r.GetSelectedMediaItem(0, i) for i in range(int(r.CountSelectedMediaItems(0)))] if mode == 'move' else [item]
            tracks = [r.GetTrack(0, i) for i in range(int(r.CountTracks(0)))]
            def tidx(it):
                tr = r.GetMediaItemTrack(it)
                return next((i for i, t in enumerate(tracks) if t == tr), 0)
            orig = []
            for it in items:
                tk = r.GetActiveTake(it)
                orig.append({'item': it, 'pos': float(r.GetMediaItemInfo_Value(it, 'D_POSITION')),
                             'len': float(r.GetMediaItemInfo_Value(it, 'D_LENGTH')), 'track': tidx(it),
                             'take': None if _is_null(tk) else tk,
                             'offs': 0.0 if _is_null(tk) else float(r.GetMediaItemTakeInfo_Value(tk, 'D_STARTOFFS')),
                             'rate': 1.0 if _is_null(tk) else float(r.GetMediaItemTakeInfo_Value(tk, 'D_PLAYRATE')) or 1.0})
            self._drag = {'x0': x, 'y0': y, 'mode': mode, 'anchor': item, 'orig': orig, 'hz': hz, 'ntracks': len(tracks),
                          'anchor_pos': pos, 'anchor_len': length, 'anchor_track': tidx(item)}
            r.UpdateArrange()
            tr = r.GetMediaItemTrack(item)
            return {'grabbed': True, 'mode': mode, 'left_px': lpx, 'right_px': rpx, 'items': len(items),
                    'track_h': int(r.GetMediaTrackInfo_Value(tr, 'I_TCPH')), 'arrange_left': self._arr_left}
        d = getattr(self, '_drag', None)
        if d is None:
            return {'grabbed': False}
        if phase in ('end', 'cancel'):
            if phase == 'cancel' and d.get('changed'):
                self._apply(d, 0.0, 0)
            self._drag = None
            if phase == 'end' and d.get('changed'):
                r.Undo_OnStateChange('FyahReaper Remote: ' + d['mode'].replace('_', ' ') + ' (touch)')
            return {'done': True, 'mode': d['mode'], 'changed': bool(d.get('changed')) and phase == 'end'}
        dt = (x - d['x0']) / d['hz']
        dtrack = 0
        if d['mode'] == 'move':
            hit = r.GetTrackFromPoint(int(x), int(y), 0)
            tr = hit[0] if isinstance(hit, (list, tuple)) else hit
            if not _is_null(tr):
                n = int(r.GetMediaTrackInfo_Value(tr, 'IP_TRACKNUMBER'))
                if n > 0:
                    dtrack = (n - 1) - d['anchor_track']
        d['changed'] = True
        return self._apply(d, dt, dtrack)

    def _snap(self, t):
        r = self.r
        return float(r.SnapToGrid(0, t)) if r.GetToggleCommandState(1157) == 1 else t

    def _apply(self, d, dt, dtrack):
        r = self.r
        r.PreventUIRefresh(1)
        try:
            if d['mode'] == 'move':
                target = self._snap(max(0.0, d['anchor_pos'] + dt))
                delta = target - d['anchor_pos']
                lo = min(o['pos'] for o in d['orig'])
                delta = max(delta, -lo)
                tmin = min(o['track'] for o in d['orig']); tmax = max(o['track'] for o in d['orig'])
                dtrack = max(-tmin, min(d['ntracks'] - 1 - tmax, dtrack))
                for o in d['orig']:
                    r.SetMediaItemInfo_Value(o['item'], 'D_POSITION', o['pos'] + delta)
                    want = r.GetTrack(0, o['track'] + dtrack)
                    if not _is_null(want) and r.GetMediaItemTrack(o['item']) != want:
                        r.MoveMediaItemToTrack(o['item'], want)
                out = {'mode': 'move', 'delta_seconds': delta, 'delta_tracks': dtrack}
            else:
                o = d['orig'][0]
                end = o['pos'] + o['len']
                if d['mode'] == 'trim_left':
                    floor = o['pos'] - o['offs'] / o['rate'] if o['take'] is not None else 0.0
                    ns = min(end - 0.01, max(0.0, floor, self._snap(o['pos'] + dt)))
                    r.SetMediaItemInfo_Value(o['item'], 'D_POSITION', ns)
                    r.SetMediaItemInfo_Value(o['item'], 'D_LENGTH', end - ns)
                    if o['take'] is not None:
                        r.SetMediaItemTakeInfo_Value(o['take'], 'D_STARTOFFS', o['offs'] + (ns - o['pos']) * o['rate'])
                    out = {'mode': 'trim_left', 'position': ns, 'length': end - ns}
                else:
                    ne = max(o['pos'] + 0.01, self._snap(end + dt))
                    r.SetMediaItemInfo_Value(o['item'], 'D_LENGTH', ne - o['pos'])
                    out = {'mode': 'trim_right', 'position': o['pos'], 'length': ne - o['pos']}
        finally:
            r.PreventUIRefresh(-1)
            r.UpdateArrange()
        return out

    def drag(self, phase, x=0, y=0):
        return self._guarded(self._drag_impl, phase, x, y)
