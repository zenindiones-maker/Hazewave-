"""Build an Android `sendevent` script for multi-touch gestures (MT protocol B), from landscape coordinates.
usage: mt.py DEVICE MAXX MAXY NATW NATH GESTURE  -> prints shell script for `adb shell sh`."""
import sys
dev, mx, my, nw, nh, g = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
out = []
def ev(t, c, v): out.append(f"sendevent {dev} {t} {c} {v}")
def raw(lx, ly):  # display rotation 90: natural x = W - ly, natural y = lx
    nx, ny = nw - ly, lx
    return int(nx * (mx + 1) / nw), int(ny * (my + 1) / nh)
def frame(pts, first=False):
    for s, (x, y) in enumerate(pts):
        rx, ry = raw(x, y); ev(3, 47, s)
        if first: ev(3, 57, 100 + s)
        ev(3, 53, rx); ev(3, 54, ry); ev(3, 58, 60)
    if first: ev(1, 330, 1)
    ev(0, 0, 0)
def up(n):
    for s in range(n): ev(3, 47, s); ev(3, 57, 4294967295)
    ev(1, 330, 0); ev(0, 0, 0)
def gesture(a0, b0, a1, b1, steps=12):
    frame([a0, b0], first=True)
    for i in range(1, steps + 1):
        f = i / steps
        lerp = lambda p, q: (p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f)
        frame([lerp(a0, a1), lerp(b0, b1)]); out.append("sleep 0.02")
    up(2)
cx, cy = 1000, 560
if g == 'pinch_out_h': gesture((cx - 120, cy), (cx + 120, cy), (cx - 450, cy), (cx + 450, cy))
elif g == 'pinch_in_h': gesture((cx - 450, cy), (cx + 450, cy), (cx - 120, cy), (cx + 120, cy))
elif g == 'pinch_out_v': gesture((cx, cy - 80), (cx, cy + 80), (cx, cy - 330), (cx, cy + 330))
elif g == 'pan_right': gesture((cx - 400, cy - 60), (cx - 400, cy + 60), (cx + 300, cy - 60), (cx + 300, cy + 60))
elif g == 'pan_down': gesture((cx - 60, 300), (cx + 60, 300), (cx - 60, 800), (cx + 60, 800))
elif g == 'double_tap':
    for k in range(2):
        rx, ry = raw(cx, cy); ev(3, 47, 0); ev(3, 57, 200 + k); ev(3, 53, rx); ev(3, 54, ry); ev(1, 330, 1); ev(0, 0, 0)
        out.append("sleep 0.05"); ev(3, 57, 4294967295); ev(1, 330, 0); ev(0, 0, 0); out.append("sleep 0.08")
print("\n".join(out))
