import numpy as np, json, math
from PIL import Image
from skimage.morphology import skeletonize, binary_dilation, disk, remove_small_objects
from scipy import ndimage as ndi
im=np.asarray(Image.open('island-ink.jpg').convert('L')).astype(float)
H,W=im.shape
ink=im<150
ink=remove_small_objects(ink,12)
sk=skeletonize(ink)
# neighbors
def nb(y,x):
    for dy in(-1,0,1):
        for dx in(-1,0,1):
            if (dy or dx) and 0<=y+dy<H and 0<=x+dx<W and sk[y+dy,x+dx]: yield (y+dy,x+dx)
deg=np.zeros_like(sk,dtype=np.uint8)
ys,xs=np.nonzero(sk)
for y,x in zip(ys,xs): deg[y,x]=sum(1 for _ in nb(y,x))
node=(deg!=2)&sk
visited=set(); strokes=[]
def walk(a,b):
    path=[a,b]; prev,cur=a,b
    while True:
        if node[cur]: break
        nxt=[p for p in nb(*cur) if p!=prev and (min(cur,p),max(cur,p)) not in visited]
        if not nxt: break
        n=nxt[0]; visited.add((min(cur,n),max(cur,n))); prev,cur=cur,n; path.append(cur)
    return path
for y,x in zip(*np.nonzero(node)):
    for n in nb(y,x):
        e=(min((y,x),n),max((y,x),n))
        if e in visited: continue
        visited.add(e); strokes.append(walk((y,x),n))
# loops w/o nodes
rest=sk.copy()
for s in strokes:
    for p in s: rest[p]=False
lab,nl=ndi.label(rest,structure=np.ones((3,3)))
for i in range(1,nl+1):
    pts=list(zip(*np.nonzero(lab==i)))
    if len(pts)<8: continue
    # order by nearest neighbor chain
    s=[pts.pop(0)]
    while pts:
        j=min(range(len(pts)),key=lambda k:(pts[k][0]-s[-1][0])**2+(pts[k][1]-s[-1][1])**2)
        if (pts[j][0]-s[-1][0])**2+(pts[j][1]-s[-1][1])**2>8: break
        s.append(pts.pop(j))
    strokes.append(s)
def rdp(pts,eps=0.9):
    if len(pts)<3: return pts
    a,b=np.array(pts[0],float),np.array(pts[-1],float); d=b-a; n=np.hypot(*d) or 1
    dist=[abs(d[0]*(a[1]-p[1])-d[1]*(a[0]-p[0]))/n for p in pts]
    i=int(np.argmax(dist))
    if dist[i]>eps: return rdp(pts[:i+1],eps)[:-1]+rdp(pts[i:],eps)
    return [pts[0],pts[-1]]
def length(p): return sum(math.hypot(p[i][0]-p[i-1][0],p[i][1]-p[i-1][1]) for i in range(1,len(p)))
# merge: join strokes end-to-end at shared nodes greedily (longer continuous gestures)
strokes=[s for s in strokes if length(s)>=4]
# silhouette
obj=ndi.binary_fill_holes(binary_dilation(ink,disk(4)))
obj=remove_small_objects(obj,5000)
edge=obj ^ ndi.binary_erosion(obj,disk(6))
cy,cx=[v.mean() for v in np.nonzero(obj)]
out=[]
for s in strokes:
    L=length(s); onEdge=np.mean([edge[p] for p in s])
    g=0 if onEdge>0.6 else (1 if L>45 else 2)
    my=np.mean([p[0] for p in s]); mx=np.mean([p[1] for p in s])
    ang=math.atan2(my-cy,mx-cx)
    key=(g, ang if g==0 else (round(my/60), mx) if g==1 else (round(my/40),mx))
    pts=rdp(s)
    d='M'+' L'.join(f'{p[1]:.0f} {p[0]:.0f}' for p in pts)
    out.append((key,d,g,L))
out.sort(key=lambda t:t[0])
json.dump({'w':W,'h':H,'paths':[{'d':d,'g':g} for _,d,g,_ in out]},open('island-ink-centerline.json','w'))
print('strokes',len(out),'by group',[sum(1 for o in out if o[2]==k) for k in range(3)],'chars',sum(len(o[1]) for o in out))
np.save('obj.npy',obj); np.save('ink.npy',ink)
