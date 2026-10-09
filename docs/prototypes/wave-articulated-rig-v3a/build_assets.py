#!/usr/bin/env python3
"""Reproducible, owner-art-first extraction of mechanical MPC sprites.
No new arbitrary art; preserve source and make actual independently moving components.
"""
from pathlib import Path
import hashlib,json,cv2,numpy as np
from PIL import Image, ImageDraw,ImageFilter,ImageEnhance
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'site/assets'; OUT.mkdir(parents=True,exist_ok=True)
S=Path('/mnt/data/estação_de_música_cyberpunk_flutuante.png')
original=Image.open(S).convert('RGBA'); W,H=original.size
# A 2x crop was examined against a 100 px coordinate grid. These polygons
# follow actual pad faces rather than inventing rectangles over the artwork.
zoom_polygons=[
[(420,99),(531,75),(673,118),(552,173)],
[(598,165),(709,126),(860,164),(747,239)],
[(825,219),(932,172),(1058,221),(941,298)],
[(980,295),(1092,237),(1267,279),(1166,377)],
[(266,202),(390,145),(536,196),(419,273)],
[(442,261),(563,210),(722,265),(606,339)],
[(681,327),(803,270),(918,309),(807,398)],
[(831,390),(935,333),(1131,383),(1001,481)],
[(96,300),(238,231),(383,291),(262,369)],
[(274,355),(401,295),(560,358),(426,445)],
[(463,425),(599,361),(766,419),(626,530)],
[(668,528),(794,435),(980,497),(842,601)] ]
polygons=[[(round(370+x/2),round(325+y/2)) for x,y in poly] for poly in zoom_polygons]
# Knob metalcaps and independently pulsing speaker cones, examined in original artwork.
knobs=[(255,441,31),(346,416,31),(407,386,31),(464,353,31),(521,331,31),(962,551,31),(1012,656,34),(1072,453,46)]
speakers=[(225,167,42),(226,286,44),(1220,323,40),(1222,434,44)]
# Transparent original and extracted parts, no change to master file.
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
source_hash=sha(S)
original.save(OUT/'original_mpc.png')
base=np.asarray(original).copy()
base_rgb=base[:,:,:3].copy(); cut=np.zeros((H,W),dtype=np.uint8)
parts=[]
def crop_and_save(name,mask,kind,x,y,**extra):
    mask=np.maximum(mask,0).astype(np.uint8)
    yy,xx=np.where(mask>5)
    x0=max(0,int(xx.min())-7); x1=min(W,int(xx.max())+8)
    y0=max(0,int(yy.min())-7); y1=min(H,int(yy.max())+8)
    pix=np.asarray(original).copy()[y0:y1,x0:x1]
    pix[:,:,3]=(pix[:,:,3].astype('uint16')*mask[y0:y1,x0:x1].astype('uint16')//255).astype('uint8')
    fname=name+'.webp'; Image.fromarray(pix).save(OUT/fname,format='WEBP',lossless=True,method=5)
    if kind=='pad':
        on=pix.copy(); rgb=on[:,:,:3].astype('float32'); alpha=(on[:,:,3].astype('float32')/255.)[:,:,None]
        # Painted on-state: retain luminance texture and hard original ink edge.
        lum=rgb.mean(axis=2,keepdims=True)
        warm=np.array([255,133,34],dtype='float32').reshape((1,1,3))
        painted=(warm*.68 + rgb*.18 + lum*.24).clip(0,255)
        on[:,:,:3]=np.where(alpha>.01,painted,rgb).astype('uint8')
        Image.fromarray(on).save(OUT/(name+'_energized.webp'),format='WEBP',quality=93,method=5)
    parts.append(dict(id=name,type=kind,file='assets/'+fname,**({'energizedFile':'assets/'+name+'_energized.webp'} if kind=='pad' else {}),x=x0,y=y0,width=x1-x0,height=y1-y0,pivot=[round(x-x0,2),round(y-y0,2)],**extra))
for i,poly in enumerate(polygons):
    mk=np.zeros((H,W),dtype='uint8');cv2.fillConvexPoly(mk,np.array(poly,np.int32),255)
    mk=cv2.GaussianBlur(mk,(3,3),0.4)
    center=np.mean(poly,axis=0);crop_and_save(f'pad_{i:02}',mk,'pad',float(center[0]),float(center[1]),activation=round(.10+i*.058,3))
    cv2.fillConvexPoly(cut,np.array(poly,np.int32),255)
for i,(x,y,r) in enumerate(knobs):
    mk=np.zeros((H,W),dtype='uint8');cv2.circle(mk,(x,y),r,255,-1);mk=cv2.GaussianBlur(mk,(5,5),0.8)
    crop_and_save(f'knob_{i:02}',mk,'knob',x,y,activation=round(.25+i*.055,3))
    cv2.circle(cut,(x,y),r-3,255,-1)
for i,(x,y,r) in enumerate(speakers):
    mk=np.zeros((H,W),dtype='uint8');cv2.circle(mk,(x,y),r,255,-1);mk=cv2.GaussianBlur(mk,(3,3),0.7)
    crop_and_save(f'speaker_{i:02}',mk,'speaker',x,y,activation=round(.38+i*.12,3))
    cv2.circle(cut,(x,y),r-3,255,-1)
# Mechanically honest underlayer: inpaint removed pads/control surfaces, leaving dark wells.
# Production review must check filled occlusion against every pose.
filled=cv2.inpaint(base_rgb,cut,7,cv2.INPAINT_TELEA)
# Tone down inpainted wells; present original surrounding metal intact.
mask=cv2.GaussianBlur(cut,(5,5),0.8).astype(np.float32)/255
filled=(filled*.63).clip(0,255).astype('uint8')
base_rgb=(base_rgb*(1-mask[:,:,None])+filled*mask[:,:,None]).astype('uint8')
base[:,:,:3]=base_rgb
Image.fromarray(base).save(OUT/'chassis_clean.webp',format='WEBP',quality=87,method=5)
# Nebula source is already owner-approved RGBA. Resize for handset, preserve alpha.
neb=Image.open('/mnt/data/nebulosa_roxa_em_camadas_transparente.png').convert('RGBA')
neb.thumbnail((1160,700)); neb.save(OUT/'painterly_fog.webp',format='WEBP',quality=80,method=5)
# Master as environment-only reference, not a locked fullscreen slideshow.
master=Image.open('/mnt/data/1001094499.png').convert('RGB');master.thumbnail((672,1194));master.save(OUT/'cosmos_reference.webp',format='WEBP',quality=82,method=5)
# Preserve exact official logos in source assets (production must never redraw name lettering).
for source,out in [('/mnt/data/1001044236.webp','logo_indionesbala.webp'),('/mnt/data/1000795868.png','logo_hazewave.png')]:
    (OUT/out).write_bytes(Path(source).read_bytes())
# Non-destructive display copy: black-to-alpha matte derived from exact brand pixels.
raw=Image.open('/mnt/data/1000795868.png').convert('RGB'); data=np.asarray(raw).copy(); luminance=np.max(data,axis=2).astype('float32'); a=np.clip((luminance-13)*1.11,0,255).astype('uint8');
cut=np.dstack([data,a]); Image.fromarray(cut,'RGBA').save(OUT/'logo_hazewave_cutout.webp',format='WEBP',quality=91,method=5)
# Small schematic with regions/pivots for independent human verification.
canvas=original.convert('RGB'); draw=ImageDraw.Draw(canvas)
for part in parts:
    x,y=part['x']+part['pivot'][0],part['y']+part['pivot'][1]
    color={'pad':'#a3ff93','knob':'#ffd464','speaker':'#9bd4ff'}[part['type']]
    draw.ellipse((x-5,y-5,x+5,y+5),outline=color,width=2)
    draw.text((x+6,y-14),part['id'],fill=color,stroke_width=1,stroke_fill='black')
canvas.thumbnail((900,900));canvas.save(ROOT/'proof/rig-pivots.jpg',quality=88)
manifest=dict(schema='HazewaveArticulatedRig/v1',source_image='estação_de_música_cyberpunk_flutuante.png',source_sha256=source_hash,source_dimensions=[W,H],original_logo_hazewave_sha256=sha('/mnt/data/1000795868.png'),original_logo_indionesbala_sha256=sha('/mnt/data/1001044236.webp'),pieces=parts,artwork_discipline='owner-approved hand-drawn cosmic 2D, mechanical parts from original illustration',risks=['automatic cleanplate inpainting around pad wells needs manual visual approval','rotated cap cutouts can reveal filled regions; restrict pivot range','initial proof is only one station, not five-act production site'])
(ROOT/'site/rig-manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
print('source_hash',source_hash,'pieces',len(parts),'pads',sum(p['type']=='pad' for p in parts),'knobs',sum(p['type']=='knob' for p in parts),'speakers',sum(p['type']=='speaker' for p in parts))
print('assets size',sum(p.stat().st_size for p in OUT.iterdir())//1024,'KiB')