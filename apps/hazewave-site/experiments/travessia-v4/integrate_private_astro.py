"""Private, no-network WAVE V4 / Astro static build integration.

Compose EXISTING exact reviewed Astro dist ZIP with private owner-approved
media without writing to repository public/ or mutating the source website.
The result is a local preview directory only, no owner approval or deploy.
"""
from __future__ import annotations
import argparse,hashlib,json,stat
from pathlib import Path,PurePosixPath
import shutil,zipfile

DIST_SHA='5cff7ae24fc0461dbaa70827d8a16b21b0a3bade792a16c37c1d705e2c871de4'
ART_SCHEMA='HazewaveTraversalV4ArtSource/v1'

def digest(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()

def compose(archive:Path,source:Path,media:Path,output:Path)->dict:
 archive=archive.resolve(strict=True);source=source.resolve(strict=True)
 media=media.resolve(strict=True);output=output.resolve(strict=False)
 if output.exists() or output.is_relative_to(source) or output.is_relative_to(media):
  raise ValueError('PRIVATE_OUTPUT_MUST_BE_FRESH_OUTSIDE_SOURCE_AND_ART')
 if archive.is_symlink() or media.is_symlink() or source.is_symlink() or digest(archive)!=DIST_SHA:
  raise ValueError('EXACT_ASTRO_DIST_OR_MEDIA_PROVENANCE_BLOCKED')
 receipt=json.loads((media/'asset-manifest.json').read_text(encoding='utf8'))
 if receipt.get('schema')!=ART_SCHEMA or receipt.get('productionApproved') is not False or receipt.get('ownerOriginalsInGithub') is not False:
  raise ValueError('V4_PRIVATE_MEDIA_UNQUALIFIED')
 if len(receipt.get('v3aPieces',[]))!=24 or len(receipt.get('assetSha256',{}))!=43:
  raise ValueError('V4_RIG_ASSET_COUNT_INVALID')
 for name,sha in receipt['assetSha256'].items():
  if Path(name).name!=name or not name.endswith('.webp') or len(sha)!=64:
   raise ValueError('ASSET_PATH_INVALID')
  path=media/'assets'/name
  if path.is_symlink() or not path.is_file() or digest(path)!=sha:
   raise ValueError('PRIVATE_ASSET_SHA_MISMATCH:'+name)
 for name in ('index.html','travessia.css','travessia.js'):
  if not (source/name).is_file():raise ValueError('ENGINE_SOURCE_MISSING')
 with zipfile.ZipFile(archive) as z:
  infos=z.infolist()
  if len(infos)>500 or sum(i.file_size for i in infos)>150_000_000:
   raise ValueError('EXACT_ASTRO_ZIP_RESOURCE_BUDGET_DENIED')
  for member in infos:
   path=PurePosixPath(member.filename)
   if member.filename.startswith('/') or '..' in path.parts or member.filename.startswith('\\') or path.is_absolute():
    raise ValueError('ZIP_SLIP_OR_ABSOLUTE_MEMBER')
   mode=(member.external_attr>>16)&0xffff
   if stat.S_ISLNK(mode):raise ValueError('ZIP_SYMLINK_FORBIDDEN')
  if not {'index.html','artists/indionesbala/index.html'}<=set(z.namelist()):
   raise ValueError('ASTRO_BUILD_NOT_RECOGNIZED')
  # All existing website bytes copied unchanged into PRIVATE new directory.
  output.mkdir(mode=0o700,parents=True)
  for info in infos:
   if info.is_dir():continue
   target=output/PurePosixPath(info.filename)
   target.parent.mkdir(parents=True,exist_ok=True)
   target.write_bytes(z.read(info.filename))
 entry=output/'experimental'/'travessia-v4';entry.mkdir(mode=0o700)
 for name in ('index.html','travessia.css','travessia.js'):
  shutil.copyfile(source/name,entry/name)
 shutil.copyfile(media/'asset-manifest.json',entry/'asset-manifest.json')
 target=entry/'assets';target.mkdir(mode=0o700)
 for file in (media/'assets').glob('*.webp'):
  shutil.copyfile(file,target/file.name)
 # Link on the private copy ONLY. Never patch the public source homepage.
 homepage=output/'index.html'
 original=homepage.read_text(encoding='utf8')
 if '</body>' not in original:raise ValueError('ASTRO_HTML_UNEXPECTED')
 link='<a href="/experimental/travessia-v4/" data-private-wave-v4="true" style="position:fixed;bottom:24px;right:16px;z-index:9999;background:#100626;color:#ffd6fe;border:1px solid #bb62ed;padding:12px 15px;text-decoration:none;font:600 13px system-ui;border-radius:4px">Entrar na Travessia V4 (experimento privado)</a>'
 homepage.write_text(original.replace('</body>',link+'</body>'),encoding='utf8')
 report={'schema':'HazewaveV4PrivateAstroIntegration/v1','authority':'NONE',
    'sourceArtifactSha256':DIST_SHA,'sourceActionsCommit':'8c6d06335af6733ecdaa048a42d64ed360d60e2f',
    'rigPieceCount':24,'totalVerifiedArtTextures':43,
    'artistRoutePreserved':(output/'artists'/'indionesbala'/'index.html').is_file(),
    'newPrivateRoute':'/experimental/travessia-v4/',
    'homepageOriginalUnmodified':True,'homepageCopyWithPrivateEntry':True,
    'ownerSourcePixelsCopiedToGitHub':False,
    'productionApproved':False,'githubPublished':False,'codespaceHostAttested':False}
 (output/'HAZEWAVE_TRAVESSIA_V4_PRIVATE_SITE_RECEIPT.json').write_text(json.dumps(report,indent=2)+'\n')
 return report

if __name__=='__main__':
 cli=argparse.ArgumentParser()
 cli.add_argument('--astro-dist-zip',type=Path,required=True)
 cli.add_argument('--engine',type=Path,default=Path(__file__).parent)
 cli.add_argument('--private-media',type=Path,required=True)
 cli.add_argument('--output',type=Path,required=True)
 a=cli.parse_args()
 print(json.dumps(compose(a.astro_dist_zip,a.engine,a.private_media,a.output),indent=2))
