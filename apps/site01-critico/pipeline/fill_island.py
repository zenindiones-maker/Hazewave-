import numpy as np, json
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import dilation, disk
ink=np.load('ink.npy'); obj=np.load('obj.npy'); H,W=ink.shape
barrier=dilation(ink,disk(2))
lab,n=ndi.label(~barrier)
areas=ndi.sum(np.ones_like(lab),lab,range(n+1))
border=set(np.unique(np.concatenate([lab[0],lab[-1],lab[:,0],lab[:,-1]])))
PAL={'paper':(244,239,230),'light':(227,221,210),'mid':(201,193,180),'dark':(150,143,133),'deep':(94,90,85),'accent':(201,111,74),'slate':(122,134,148)}
out=np.zeros((H,W,4),np.uint8)
objs=ndi.find_objects(lab)
stats={}
for i in range(1,n+1):
    if i in border: continue
    sl=objs[i-1]; m=(lab[sl]==i); a=areas[i]
    if a<6: continue
    cy=(sl[0].start+sl[0].stop)/2; cx=(sl[1].start+sl[1].stop)/2
    h=sl[0].stop-sl[0].start; w=sl[1].stop-sl[1].start; fill=a/(h*w)
    if not obj[int(cy),int(cx)] and a>20000: continue
    under = cy>0.60*H
    if 480<cx<780 and 185<cy<345 and 550<a<1000 and fill>=0.5 and 44<w<66 and 17<h<33: c='accent'      # pads
    elif a>2500 and fill>0.5 and 0.75<w/h<1.33 and (cx<420 or cx>880) and cy<260: c='deep'  # speaker cones
    elif a>6000: c='mid' if under else 'light'
    elif a>900: c='dark' if under else 'mid'
    elif a>120: c='slate' if under else 'dark'
    else: c='deep'
    stats[c]=stats.get(c,0)+1
    out[sl][m]=PAL[c]+(255,)
# fill ink pixels within object with ink color under alpha so no gaps (ink layer covers)
# ink pixels: grow fills into the ink gaps (ink strokes are drawn on top)
for _ in range(3):
    m=out[...,3]==0
    grow=ndi.grey_dilation(out,size=(3,3,1))
    sel=m & barrier & obj & (grow[...,3]>0)
    out[sel]=grow[sel]
Image.fromarray(out,'RGBA').save('island-flat.png')
json.dump({k:'#%02x%02x%02x'%v for k,v in PAL.items()},open('palette.json','w'))
print(n,stats)

# --- pads: complete the 4x3 lattice (some pads leak into the plate through ink gaps) ---
pads=[]
for i in range(1,n+1):
    if i in border: continue
    sl=objs[i-1]; a=areas[i]
    cy=(sl[0].start+sl[0].stop)/2; cx=(sl[1].start+sl[1].stop)/2; h=sl[0].stop-sl[0].start; w=sl[1].stop-sl[1].start
    if 480<cx<780 and 185<cy<345 and 550<a<1000 and a/(h*w)>=0.5 and 44<w<66 and 17<h<33: pads.append((i,cx,cy))
P=np.array([[p[1],p[2]] for p in pads])
# estimate lattice by brute force over integer coords
best=None
for u in [(51,7),(52,8),(50,6),(53,7)]:
    for v in [(-26,25),(-27,24),(-25,26),(-27,23)]:
        A=np.array([u,v],float).T
        cr=np.linalg.solve(A,(P-P[0]).T).T
        R=np.round(cr); err=np.abs(cr-R).sum()
        if best is None or err<best[0]: best=(err,np.array(u,float),np.array(v,float),R)
err,u,v,R=best
R-=R.min(0); have={(int(c),int(r)) for c,r in R}
origin=(P-(R[:,0:1]*u+R[:,1:2]*v)).mean(0)
ref=pads[0]; rsl=objs[ref[0]-1]; rmask=(lab[rsl]==ref[0]); rc=np.array([ref[1],ref[2]])
cmax,rmax=int(R[:,0].max()),int(R[:,1].max())
added=0
for c in range(cmax+1):
    for r in range(rmax+1):
        if (c,r) in have: continue
        ctr=origin+c*u+r*v; d=(ctr-rc).round().astype(int)
        ys,xs=np.nonzero(rmask); ys=ys+rsl[0].start+d[1]; xs=xs+rsl[1].start+d[0]
        ok=(ys>=0)&(ys<H)&(xs>=0)&(xs<W); ys,xs=ys[ok],xs[ok]; keep=~barrier[ys,xs]
        out[ys[keep],xs[keep]]=PAL['accent']+(255,); added+=1
print('lattice',cmax+1,'x',rmax+1,'detected',len(pads),'added',added,'err',round(float(err),2))
Image.fromarray(out,'RGBA').save('island-flat.png')
