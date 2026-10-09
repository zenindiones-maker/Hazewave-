"""SHA-bound V3A+owner-layer reconstruction into an OPTIONAL PRIVATE output.

The operator supplies exact verified 2026-10-09 Actions static artifact and
materialized owner Library masters. No network, no installs, no stock mutation.
Never commit output `assets/` into GitHub: source art remains owner-private.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import zipfile
from PIL import Image

MASTER_HASHES = {
 'estação_de_música_cyberpunk_flutuante.png':'4d1cdcf38beb758d93a4c28483a00d8cd9bfa6616fbd0f5fc1b88f1ca8c39ddd',
 'controlador_mpc_cyberpunk_neon.png':'460eaf43069e608fc959ca95dd7431330e98ace110752640145d5d711cb8be96',
 'metrópole_musical_flutuante_neon.png':'9f8619db60c99e3ed1bf426c3a5838e6739df275dfe4c3294e5b8a274a9ed963',
 'fortaleza_dj_futurista_indionesbala.png':'2fdf7b8e4d7a7ad1c9ed3a99da31e16eefda0efc1b9d06a28a6032891934e72e',
 'nebulosa_roxa_em_camadas_transparente.png':'bc38da43aa8d21100ec116c7247a1613e75b6168e91d656f4be0b7b299320b51'
}
ACTIONS_ZIP_SHA256 = '5cff7ae24fc0461dbaa70827d8a16b21b0a3bade792a16c37c1d705e2c871de4'
ACTIONS_V3A_COMMIT = '8c6d06335af6733ecdaa048a42d64ed360d60e2f'
NAMES = {
 'estação_de_música_cyberpunk_flutuante.png':'station',
 'controlador_mpc_cyberpunk_neon.png':'controller',
 'metrópole_musical_flutuante_neon.png':'city',
 'fortaleza_dj_futurista_indionesbala.png':'hub',
 'nebulosa_roxa_em_camadas_transparente.png':'fog'
}

def hexhash(b:bytes)->str:return hashlib.sha256(b).hexdigest()
class ApprovedImgParser(HTMLParser):
 def __init__(self):super().__init__();self.data={}
 def handle_starttag(self,tag,attrs):
  if tag!='img':return
  d=dict(attrs);classes=set(d.get('class','').split())
  for name in ('chassis','fog'):
   if name in classes and name not in self.data:
    self.data[name]=d.get('src')

def build(owner_root:Path, artifact:Path, output:Path):
 owner_root=owner_root.resolve(strict=True)
 artifact=artifact.resolve(strict=True)
 output=output.resolve(strict=False)
 if output.exists() or output.is_relative_to(owner_root):
  raise ValueError('OUTPUT_ALREADY_EXISTS_OR_TOUCHES_OWNER_MASTERS')
 if not owner_root.is_dir() or owner_root.is_symlink():raise ValueError('ORIGINAL_LIBRARY_FOLDER_REQUIRED')
 if artifact.is_symlink() or hexhash(artifact.read_bytes())!=ACTIONS_ZIP_SHA256:
  raise ValueError('ACTIONS_ZIP_SHA_DRIFT')
 # Gate all master bytes BEFORE creating output.
 for fname,expected in MASTER_HASHES.items():
  src=owner_root/fname
  if src.is_symlink() or hexhash(src.read_bytes())!=expected:
   raise ValueError('APPROVED_ART_SHA_MISMATCH:'+fname)
 with zipfile.ZipFile(artifact) as zipfile_in:
  html=zipfile_in.read('experimental/articulated-rig-v3a.html').decode('utf8')
 anchor='window.__rigManifest = '
 start=html.index(anchor)+len(anchor)
 v3a,_=json.JSONDecoder().raw_decode(html[start:])
 counts={name:sum(p['type']==name for p in v3a['pieces']) for name in ['pad','knob','speaker']}
 if v3a['source_sha256']!=MASTER_HASHES['estação_de_música_cyberpunk_flutuante.png'] or counts!={'pad':12,'knob':8,'speaker':4}:
  raise ValueError('V3A_MANIFEST_CHANGED_OR_INCORRECT')
 parser=ApprovedImgParser();parser.feed(html)
 if not {'chassis','fog'}<=set(parser.data):raise ValueError('V3A_PIXEL_SPRITES_MISSING')
 def decode_inline(s:str)->bytes:
  if not isinstance(s,str) or not s.startswith('data:image/webp;base64,'):
   raise ValueError('NON_FIRST_PARTY_SPRITE_URL_DENIED')
  return base64.b64decode(s.split(',',1)[1],validate=True)
 # Exactly planned files. No network and no arbitrary URLs.
 output.mkdir(mode=0o700,parents=True)
 dest=output/'assets';dest.mkdir(mode=0o700)
 for name in MASTER_HASHES:
  with Image.open(owner_root/name) as img:
   rendered=img.convert('RGBA')
   rendered.thumbnail((1400,1024),Image.Resampling.LANCZOS)
   rendered.save(dest/(NAMES[name]+'.webp'),'WEBP',quality=84,method=5)
 for entry in v3a['pieces']:
  for field in ('file','energizedFile'):
   if field not in entry:continue
   filename=entry['id']+('_on' if field=='energizedFile' else '')+'.webp'
   (dest/filename).write_bytes(decode_inline(entry[field]));entry[field]=filename
 for cls,filename in [('chassis','chassis.webp'),('fog','v3a_fog.webp')]:
  (dest/filename).write_bytes(decode_inline(parser.data[cls]))
 media={p.name:hexhash(p.read_bytes()) for p in sorted(dest.glob('*.webp'))}
 receipt={'schema':'HazewaveTraversalV4ArtSource/v1','authority':'NONE',
  'productionApproved':False,'ownerOriginalsInGithub':False,
  'ownerApprovedSourceSha256':MASTER_HASHES,
  'v3aSourceActionsSha':ACTIONS_V3A_COMMIT,
  'v3aSourceIllustrationSha256':v3a['source_sha256'],
  'v3aPieces':v3a['pieces'],
  'worldStages':['cosmos','signal','machine','rupture','indionesbala_hub'],
  'assetSha256':media,'localReviewOnly':True}
 (output/'asset-manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
 print('V4_SOURCE_PROVENANCE=PASS_APPROVED_5_MASTERS_ACTIONS_ZIP_SHA_EXACT')
 print('V4_ACTUAL_V3A_PIECES=24_PADS12_KNOBS8_SPEAKERS4')
 return receipt

if __name__=='__main__':
 cli=argparse.ArgumentParser()
 cli.add_argument('--approved-art-root',type=Path,required=True)
 cli.add_argument('--v3a-actions-zip',type=Path,required=True)
 cli.add_argument('--output',type=Path,required=True)
 a=cli.parse_args()
 build(a.approved_art_root,a.v3a_actions_zip,a.output)
