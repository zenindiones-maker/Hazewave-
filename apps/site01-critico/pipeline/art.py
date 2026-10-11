"""Pipeline de arte HAZEWAVE (MIT): line art raster -> traços de linha central ordenados (.hzs binário)
+ camada de cor chapada alinhada à tinta (flood-fill). Uso: python3 art.py <entrada.jpg> <saida_prefixo> [x0 y0 x1 y1] [--fill none|soft]"""
import sys, math, struct, json
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import skeletonize, dilation, disk, remove_small_objects

SEEDS = None; OFF = (0, 0)
PAL = {'light': (227, 221, 210), 'mid': (201, 193, 180), 'dark': (150, 143, 133), 'deep': (94, 90, 85), 'accent': (201, 111, 74), 'slate': (122, 134, 148), 'ochre': (196, 160, 92), 'terra': (201, 111, 74)}

def load(path, crop=None):
    im = Image.open(path).convert('L')
    if crop: im = im.crop(crop)
    a = np.asarray(im).astype(float)
    thr = int(sys.argv[sys.argv.index('--thr') + 1]) if '--thr' in sys.argv else 150
    ink = remove_small_objects(a < thr, max_size=12)
    return a, ink

def centerline(ink):
    H, W = ink.shape
    sk = skeletonize(ink)
    K = ndi.convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8), mode='constant') - 1
    node = sk & (K != 2)
    visited = set(); strokes = []
    def nb(y, x):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if (dy or dx) and 0 <= y + dy < H and 0 <= x + dx < W and sk[y + dy, x + dx]: yield (y + dy, x + dx)
    def walk(a, b):
        path = [a, b]; prev, cur = a, b
        while not node[cur]:
            nxt = [p for p in nb(*cur) if p != prev and (min(cur, p), max(cur, p)) not in visited]
            if not nxt: break
            n = nxt[0]; visited.add((min(cur, n), max(cur, n))); prev, cur = cur, n; path.append(cur)
        return path
    for y, x in zip(*np.nonzero(node)):
        for n in nb(y, x):
            e = (min((y, x), n), max((y, x), n))
            if e in visited: continue
            visited.add(e); strokes.append(walk((y, x), n))
    rest = sk.copy()
    for s in strokes:
        for p in s: rest[p] = False
    lab, nl = ndi.label(rest, structure=np.ones((3, 3)))
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        pts = [(y + sl[0].start, x + sl[1].start) for y, x in zip(*np.nonzero(lab[sl] == i))]
        if len(pts) < 8: continue
        s = [pts.pop(0)]
        while pts:
            j = min(range(len(pts)), key=lambda k: (pts[k][0] - s[-1][0]) ** 2 + (pts[k][1] - s[-1][1]) ** 2)
            if (pts[j][0] - s[-1][0]) ** 2 + (pts[j][1] - s[-1][1]) ** 2 > 8: break
            s.append(pts.pop(j))
        strokes.append(s)
    return strokes

def rdp(pts, eps=0.9):
    if len(pts) < 3: return pts
    a, b = np.array(pts[0], float), np.array(pts[-1], float); d = b - a; n = math.hypot(*d) or 1
    dist = [abs(d[0] * (a[1] - p[1]) - d[1] * (a[0] - p[0])) / n for p in pts]
    i = int(np.argmax(dist))
    if dist[i] > eps: return rdp(pts[:i + 1], eps)[:-1] + rdp(pts[i:], eps)
    return [pts[0], pts[-1]]

def length(p): return sum(math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]) for i in range(1, len(p)))

def order(strokes, ink, region_fn=None):
    obj = ndi.binary_fill_holes(dilation(ink, disk(4))); obj = remove_small_objects(obj, max_size=3000)
    edge = obj ^ ndi.binary_erosion(obj, disk(6))
    ys, xs = np.nonzero(obj); cy, cx = (ys.mean(), xs.mean()) if len(ys) else (ink.shape[0] / 2, ink.shape[1] / 2)
    out = []
    for s in strokes:
        L = length(s)
        if L < 4: continue
        onE = np.mean([edge[p] for p in s]); g = 0 if onE > .6 else (1 if L > 45 else 2)
        my = np.mean([p[0] for p in s]); mx = np.mean([p[1] for p in s])
        tag = region_fn(my, mx) if region_fn else 0
        key = (tag, g, math.atan2(my - cy, mx - cx) if g == 0 else (round(my / 50), mx))
        out.append((key, g, tag, [(int(p[1]), int(p[0])) for p in rdp(s)]))
    if '--prune' in sys.argv:
        minlen = float(sys.argv[sys.argv.index('--prune') + 1]); cap = 6; cells = {}; kept = []
        for t in sorted(out, key=lambda t: -length([(p[1], p[0]) for p in t[3]])):
            L = length([(p[1], p[0]) for p in t[3]])
            if t[1] == 0: kept.append(t); continue  # silhuetas sempre
            if L < minlen: continue
            c = (int(np.mean([p[0] for p in t[3]]) // 40), int(np.mean([p[1] for p in t[3]]) // 40))
            if t[1] == 2 and cells.get(c, 0) >= cap: continue
            cells[c] = cells.get(c, 0) + 1; kept.append(t)
        out = kept
    out.sort(key=lambda t: t[0])
    return out, obj

def encode(out, W, H, path):
    """HZS1: u16 W,u16 H,u32 N; por traço: u8 grupo, u8 tag, u16 n, i16 x0,y0, (n-1)×(i8 dx,i8 dy). Deltas >127 viram pontos intermediários."""
    buf = bytearray(b'HZS1') + struct.pack('<HHI', W, H, len(out))
    for _, g, tag, pts in out:
        q = [pts[0]]
        for p in pts[1:]:
            while abs(p[0] - q[-1][0]) > 127 or abs(p[1] - q[-1][1]) > 127:
                k = max(abs(p[0] - q[-1][0]), abs(p[1] - q[-1][1])) / 127.0
                q.append((q[-1][0] + int((p[0] - q[-1][0]) / k), q[-1][1] + int((p[1] - q[-1][1]) / k)))
            q.append(p)
        buf += struct.pack('<BBHhh', g, tag, len(q), q[0][0], q[0][1])
        for a, b in zip(q, q[1:]): buf += struct.pack('<bb', b[0] - a[0], b[1] - a[1])
    open(path, 'wb').write(buf); return len(buf)

def flat(ink, obj, path, rules='soft'):
    H, W = ink.shape
    barrier = dilation(ink, disk(2)); lab, n = ndi.label(~barrier)
    areas = ndi.sum(np.ones_like(lab), lab, range(n + 1))
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    out = np.zeros((H, W, 4), np.uint8)
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        if i in border or areas[i] < (400 if '--soft' in sys.argv else 6): continue
        m = lab[sl] == i; a = areas[i]; cy = (sl[0].start + sl[0].stop) / 2
        if not obj[min(H - 1, int(cy)), min(W - 1, int((sl[1].start + sl[1].stop) / 2))] and a > 20000: continue
        under = cy > .62 * H
        c = ('mid' if under else 'light') if a > 6000 else ('dark' if under else 'mid') if a > 900 else ('slate' if under else 'dark') if a > 120 else 'deep'
        if '--soft' in sys.argv: c = ('mid' if under else 'light') if a > 3000 else ('dark' if under else 'mid')
        out[sl][m] = PAL[c] + (255,)
    for _ in range(3):
        m = out[..., 3] == 0; grow = ndi.grey_dilation(out, size=(3, 3, 1)); sel = m & barrier & obj & (grow[..., 3] > 0); out[sel] = grow[sel]
    seeds = json.load(open(SEEDS)) if SEEDS else []
    for sx, sy, c in seeds:
        sx -= OFF[0]; sy -= OFF[1]; best = None
        for r in range(0, 9):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    y, x = int(sy + dy), int(sx + dx)
                    if 0 <= y < H and 0 <= x < W and lab[y, x] and lab[y, x] not in border: best = lab[y, x]; break
                if best: break
            if best: break
        if best: out[lab == best] = PAL[c] + (255,)
        else: print('seed miss', sx, sy)
    Image.fromarray(out, 'RGBA').save(path)
    return out

if __name__ == '__main__':
    src, pref = sys.argv[1], sys.argv[2]
    crop = tuple(map(int, sys.argv[3:7])) if len(sys.argv) >= 7 and all(x.lstrip('-').isdigit() for x in sys.argv[3:7]) else None

    SEEDS = sys.argv[sys.argv.index('--seeds') + 1] if '--seeds' in sys.argv else None; OFF = crop[:2] if crop else (0, 0)
    a, ink = load(src, crop); H, W = ink.shape
    out, obj = order(centerline(ink), ink)
    print(pref, 'strokes', len(out), 'bytes', encode(out, W, H, pref + '.hzs'))
    if '--nofill' not in sys.argv: flat(ink, obj, pref + '-flat.png')
