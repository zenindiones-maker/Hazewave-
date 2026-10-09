#!/usr/bin/env python3
"""Recover the V3A animated textures from its self-contained, versioned HTML.

No external services, packages or model calls. Output is a fresh directory only;
existing files are never replaced. This is for asset provenance and reproducibility,
not a substitute for the owner-supplied original high-resolution master illustration.
"""
import argparse
import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

DATA_URI = re.compile(r'^data:image/(?:webp|png|jpeg);base64,([A-Za-z0-9+/=]+)$')
MANIFEST = re.compile(r'window\.__rigManifest\s*=\s*(\{.*?\});\s*</script>', re.S)
CSS_COSMOS = re.compile(r"url\(['\"](data:image/webp;base64,[A-Za-z0-9+/=]+)['\"]\)")

class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images=[]
    def handle_starttag(self, tag, attrs):
        if tag=='img': self.images.append(dict(attrs))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('html',type=Path,help='HAZEWAVE-RIG-V3-ABRIR.html from the V3A GitHub development branch')
    parser.add_argument('output_dir',type=Path,help='A NONEXISTING directory to create')
    args=parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit('STOP: destination already exists, refusing to replace or delete it')
    content=args.html.read_text(encoding='utf-8')
    m=MANIFEST.search(content)
    if not m: raise SystemExit('STOP: no embedded manifest detected')
    spec=json.loads(m.group(1))
    if spec.get('schema')!='HazewaveArticulatedRig/v1' or len(spec.get('pieces',[]))!=24:
        raise SystemExit('STOP: unexpected source schema or missing articulated parts')
    found=Images()
    found.feed(content)
    save={}
    def queue(path, url):
        match=DATA_URI.fullmatch(url)
        if not match: raise ValueError('Unsupported or missing image data: '+path)
        data=base64.b64decode(match.group(1),validate=True)
        if not data.startswith(b'RIFF') and not data.startswith(b'\x89PNG') and not data.startswith(b'\xff\xd8\xff'):
            raise ValueError('Invalid image header: '+path)
        if path in save and save[path]!=data:
            raise ValueError('Contradictory texture bytes: '+path)
        save[path]=data
    for piece in spec['pieces']:
        pid=piece['id'];typ=piece['type']
        if typ not in {'pad','knob','speaker'} or not re.fullmatch(r'(pad|knob|speaker)_\d{2}',pid):
            raise ValueError('Unexpected piece identifier: '+pid)
        queue('assets/'+pid+'.webp',piece['file'])
        piece['file']='assets/'+pid+'.webp'
        if piece.get('energizedFile'):
            if typ!='pad': raise ValueError('Only pads may have energy textures')
            queue('assets/'+pid+'_energized.webp',piece['energizedFile'])
            piece['energizedFile']='assets/'+pid+'_energized.webp'
    backgrounds=CSS_COSMOS.findall(content)
    if not backgrounds:raise ValueError('Missing cosmos backdrop')
    queue('assets/cosmos_reference.webp',backgrounds[0])
    for im in found.images:
        css=im.get('class','')
        if 'fog' in css:
            queue('assets/painterly_fog.webp',im['src'])
        elif 'wordmark' in css:
            queue('assets/logo_hazewave_cutout.webp',im['src'])
        elif 'chassis' in css:
            queue('assets/chassis_clean.webp',im['src'])
        elif im.get('alt')=='Logo original Indionesbala':
            queue('assets/logo_indionesbala.jpg',im['src'])
    if len(save)!=41:
        raise ValueError('Expected 41 unique textures, got '+str(len(save)))
    args.output_dir.mkdir(parents=True)
    for name,data in save.items():
        target=args.output_dir/name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(data)
    (args.output_dir/'rig-manifest.json').write_text(json.dumps(spec,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    report={'schema':'HazewaveRecoveredRigAssets/v1','source_html_sha256':hashlib.sha256(content.encode()).hexdigest(),
            'count':len(save),'pieces':len(spec['pieces']),
            'files':{k:hashlib.sha256(v).hexdigest() for k,v in sorted(save.items())}}
    (args.output_dir/'RECOVERY_SHA256.json').write_text(json.dumps(report,indent=2)+'\n')
    print('V3A_RECOVERED_ASSETS='+str(len(save)))
    print('V3A_RECOVERED_PIECES='+str(len(spec['pieces'])))
    print('V3A_RECOVERY=PASS')

if __name__=='__main__':main()