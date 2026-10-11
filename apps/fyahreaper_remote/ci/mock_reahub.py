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
    TOUCH_ACTIONS = {'zoom_in_h','zoom_out_h','zoom_in_v','zoom_out_v','scroll_left','scroll_right','scroll_up','scroll_down','zoom_item','play','stop','record','undo','redo'}
    def action(self, name, repeat=1): self._log('action', name, repeat); return {'action': name, 'repeat': repeat, 'state': self.state}
    def move_selected(self, d, commit=False, x=None, y=None): self._log('move', round(d,1), commit, x, y); return {'moved': 1}
    def create_midi(self, r): self._log('create_midi', len(r.notes)); return {'notes_created': len(r.notes)}
app = app_factory(Studio(), os.environ['MOCK_TOKEN'])
