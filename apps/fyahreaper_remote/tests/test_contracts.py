from fastapi.testclient import TestClient
import pytest
from reahub_server import app_factory, MidiRequest, Note

class Studio:
    def __init__(self):
        self.recording=False
        self.armed=False
        self.notes=[]
        self.volume=1.0
    def health(self): return {'reaper_connected':True, 'state':'recording' if self.recording else 'stopped'}
    def transport(self, action):
        if action=='rec':
            if not self.armed: raise ValueError('NO_TRACK_ARMED')
            self.recording=True
        elif action=='stop': self.recording=False
        return {'state':'recording' if self.recording else 'stopped'}
    def tracks(self): return [{'id':'{a}', 'name':'Bass', 'mute':False, 'solo':False, 'armed':self.armed,'volume':self.volume}]
    def set_track(self, guid, update):
        if guid!='{a}': raise KeyError(guid)
        if 'armed' in update:self.armed=update['armed']
        if 'volume' in update:self.volume=update['volume']
        return self.tracks()[0]
    def create_midi(self, req):
        if self.recording: raise ValueError('TRANSPORT_RECORDING')
        self.notes=[n.model_dump() for n in req.notes]
        return {'notes_created':len(self.notes),'track_id':'{new}','position_seconds':0.0}

def client():
    st=Studio()
    return TestClient(app_factory(st,'A'*32)),st

def test_rejects_missing_or_bad_token():
    c,_=client()
    assert c.get('/api/tracks').status_code==401
    assert c.get('/api/tracks',headers={'Authorization':'Bearer bad'}).status_code==401

def test_rec_requires_armed_track_and_stop():
    c,s=client(); h={'Authorization':'Bearer '+ 'A'*32}
    assert c.post('/api/transport/rec',headers=h).status_code==409
    assert c.patch('/api/tracks/%7Ba%7D',headers=h,json={'armed':True}).status_code==200
    assert c.post('/api/transport/rec',headers=h).json()['state']=='recording'
    assert c.post('/api/transport/stop',headers=h).json()['state']=='stopped'

def test_fader_and_invalid_guid():
    c,s=client();h={'Authorization':'Bearer '+'A'*32}
    assert c.patch('/api/tracks/%7Ba%7D',headers=h,json={'volume':0.42}).json()['volume']==0.42
    assert c.patch('/api/tracks/unknown',headers=h,json={'volume':0.4}).status_code==404
    assert c.patch('/api/tracks/%7Ba%7D',headers=h,json={'volume':99}).status_code==422
    assert c.patch('/api/tracks/%7Ba%7D',headers=h,json={}).status_code==422

def test_three_notes_payload_and_negative_validation():
    c,s=client();h={'Authorization':'Bearer '+'A'*32}
    req={'notes':[{'pitch':36,'start':0.0,'duration':0.2,'velocity':100}, {'pitch':40,'start':0.25,'duration':0.2,'velocity':100}, {'pitch':43,'start':0.5,'duration':0.2,'velocity':100}]}
    assert c.post('/api/project/create_midi',headers=h,json=req).json()['notes_created']==3
    assert [n['pitch'] for n in s.notes]==[36,40,43]
    req['notes'][0]['pitch']=128
    assert c.post('/api/project/create_midi',headers=h,json=req).status_code==422
    req['notes'][0]['pitch']=36
    req['notes'][0]['duration']=0.0
    assert c.post('/api/project/create_midi',headers=h,json=req).status_code==422

def test_websocket_requires_auth():
    c,_=client()
    with pytest.raises(Exception):
        with c.websocket_connect('/ws'): pass
