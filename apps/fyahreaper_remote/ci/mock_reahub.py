"""CI-only ReaHub with the REAL reahub_server routes and a fake studio (no REAPER)."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from reahub_server import app_factory
LOG = os.environ['MOCK_LOG']
class Studio:
    state = 'stopped'
    def _log(self, *a):
        with open(LOG, 'a') as f: f.write(json.dumps(a) + '\n')
    def health(self): return {'reaper_connected': True, 'reaper_version': 'MOCK', 'state': self.state}
    def tracks(self): return [{'id': '{T1}', 'name': 'Mock', 'mute': False, 'solo': False, 'armed': True, 'volume': 1.0}]
    def transport(self, action):
        self._log('transport', action); self.state = {'play': 'playing', 'rec': 'recording', 'stop': 'stopped'}[action]; return {'state': self.state}
    def edit(self, action): self._log('edit', action); return {'action': action, 'state': self.state}
    def set_track(self, g, u): self._log('set_track', g, u); return self.tracks()[0]
    TOUCH_ACTIONS = {'zoom_in_h','zoom_out_h','zoom_in_v','zoom_out_v','scroll_left','scroll_right','scroll_up','scroll_down','zoom_item','toolbar_edit','toolbar_arrange','play','stop','record','undo','redo'}
    def action(self, name, repeat=1): self._log('action', name, repeat); return {'action': name, 'repeat': repeat, 'state': self.state}
    def move_selected(self, d, commit=False, x=None, y=None): self._log('move', round(d,1), commit, x, y); return {'moved': 1}
    def view_zoom(self, f, a, p): self._log('view', round(f, 3), a, round(p)); return {'start': 0, 'end': 10}
    def drag(self, phase, x=0, y=0):
        self._log('drag', phase, x, y)
        return {'grabbed': True, 'mode': 'move', 'left_px': max(0, x - 100), 'right_px': x + 300, 'track_h': 150} if phase == 'grab' else {'ok': True}
    def mixer(self):
        t = [{'id': '{T%d}' % i, 'number': i, 'name': n, 'color': c, 'volume': 1.0, 'volume_db': 0.0, 'pan': 0.0, 'mute': False,
              'solo': False, 'armed': False, 'peak_db': [-12.0, -14.0]} for i, (n, c) in enumerate([('Kick', '#c62828'), ('Bass', '#1565c0'), ('Vox', None)], 1)]
        return {'tracks': t, 'master': {'volume': 1.0, 'volume_db': 0.0, 'peak_db': [-6.0, -6.0]}, 'state': self.state}
    def create_midi(self, r): self._log('create_midi', len(r.notes)); return {'notes_created': len(r.notes)}
app = app_factory(Studio(), os.environ['MOCK_TOKEN'])
