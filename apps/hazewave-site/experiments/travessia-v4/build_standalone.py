"""Materialize an offline standalone review copy, never into repository public/.

Input media root must contain SHA-bound assets/ and asset-manifest.json
from build_assets.py. Media files remain private, not in repo or GitHub Actions.
"""
from pathlib import Path
import argparse,base64,hashlib,json,re

def build(source:Path,media:Path,destination:Path)->Path:
 source=source.resolve(strict=True);media=media.resolve(strict=True)
 destination=destination.resolve(strict=False)
 if destination.exists() or destination.is_relative_to(source) or destination.is_relative_to(media):
  raise ValueError('STANDALONE_OUTPUT_EXISTS_OR_INSIDE_INPUTS')
 manifest=json.loads((media/'asset-manifest.json').read_text(encoding='utf8'))
 assert manifest['schema']=='HazewaveTraversalV4ArtSource/v1' and manifest['productionApproved'] is False
 mapping={}
 for filename,expected in manifest['assetSha256'].items():
  data=(media/'assets'/filename).read_bytes()
  if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('PRIVATE_ASSET_HASH_DRIFT:'+filename)
  mapping[filename]='data:image/webp;base64,'+base64.b64encode(data).decode()
 page=(source/'index.html').read_text(encoding='utf8')
 css=(source/'travessia.css').read_text(encoding='utf8')
 js=(source/'travessia.js').read_text(encoding='utf8')
 page=page.replace('<link rel="stylesheet" href="travessia.css">','<style>'+css+'</style>')
 page=re.sub(r'(src=")assets/([^"\s]+)(")',lambda m:m.group(1)+mapping[m.group(2)]+m.group(3),page)
 inline='<script>window.__assetManifest='+json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+';window.__assetUrls='+json.dumps(mapping,separators=(',',':'))+';</script>'
 page=page.replace('<script src="travessia.js" defer></script>',inline+'<script>'+js+'</script>')
 if 'src="assets/' in page or 'href="travessia.css"' in page:raise ValueError('STANDALONE_HAS_NETWORK_DEPENDENCIES')
 destination.parent.mkdir(parents=True,exist_ok=True)
 destination.write_text(page,encoding='utf8')
 print('V4_OFFLINE_SELF_CONTAINED=PASS')
 print('V4_PRIVATE_HTML_SHA256='+hashlib.sha256(destination.read_bytes()).hexdigest())
 return destination

if __name__=='__main__':
 cli=argparse.ArgumentParser()
 cli.add_argument('--source',type=Path,default=Path(__file__).parent)
 cli.add_argument('--media',type=Path,default=Path(__file__).parent)
 cli.add_argument('--output',type=Path,required=True)
 a=cli.parse_args()
 build(a.source,a.media,a.output)
