"""Line-by-line Python reference of the Hazewave JSFX DSP (mono), for offline verification."""
import math
import numpy as np


class FyahComp:
    def __init__(self, sr=48000, input_db=0.0, output_db=0.0, ratio=4, attack_us=200, release_ms=300,
                 feedback=0.0, saturation=0.3, mix=1.0):
        self.ing, self.outg = 10 ** (input_db / 20), 10 ** (output_db / 20)
        self.allb = ratio == "all"
        self.ratio = 20 if self.allb else ratio
        self.knee = 12 if self.allb else 6
        self.att = math.exp(-1 / (sr * attack_us * 1e-6 * (0.5 if self.allb else 1)))
        self.rel = math.exp(-1 / (sr * release_ms * 1e-3))
        self.fb, self.sat, self.mix = feedback, saturation, mix
        self.drv, self.bias = 1 + 4 * saturation, 0.15 * saturation
        self.thr, self.gr, self.prev = -18.0, 0.0, 0.0

    def static_gr(self, lev):
        ov, r, k = lev - self.thr, self.ratio, self.knee
        if ov <= -k / 2: t = 0.0
        elif ov >= k / 2: t = ov * (1 - 1 / r)
        else: t = (1 - 1 / r) * (ov + k / 2) ** 2 / (2 * k)
        if self.allb and ov > 6: t += 0.25 * (ov - 6)
        return t

    def process(self, x, return_gr=False):
        y_out, grs = np.empty_like(x), np.empty_like(x)
        for n, s in enumerate(x):
            xi = s * self.ing
            det = abs(xi) * (1 - self.fb) + abs(self.prev) * self.fb
            t = self.static_gr(20 * math.log10(max(det, 1e-6)))
            if self.fb > 0: t *= 1 + self.fb * (self.ratio - 1) / self.ratio
            c = self.att if t > self.gr else self.rel
            self.gr = c * self.gr + (1 - c) * t
            y = xi * 10 ** (-self.gr / 20); self.prev = y
            if self.sat > 0:
                y = ((math.tanh(self.drv * y + self.bias) - math.tanh(self.bias)) / self.drv) * self.sat + y * (1 - self.sat)
            y_out[n] = (y * self.mix + xi * (1 - self.mix)) * self.outg; grs[n] = self.gr
        return (y_out, grs) if return_gr else y_out


def _biquad(kind, f, q, db, sr):
    w = 2 * math.pi * min(f, 0.45 * sr) / sr; al = math.sin(w) / (2 * q); c = math.cos(w)
    if kind == "peak":
        A = 10 ** (db / 40); a0 = 1 + al / A
        return [(1 + al * A) / a0, -2 * c / a0, (1 - al * A) / a0], [1, -2 * c / a0, (1 - al / A) / a0]
    if kind == "lp":
        a0 = 1 + al; return [(1 - c) / 2 / a0, (1 - c) / a0, (1 - c) / 2 / a0], [1, -2 * c / a0, (1 - al) / a0]
    a0 = 1 + al; return [(1 + c) / 2 / a0, -(1 + c) / a0, (1 + c) / 2 / a0], [1, -2 * c / a0, (1 - al) / a0]


SPEEDS = {7.5: (45, 3.0, 9000), 15: (65, 2.5, 16000), 30: (110, 2.0, 22000)}


class FyahTape:
    def __init__(self, sr=48000, drive_db=0.0, output_db=0.0, speed=15, bias=0.5, wow=0.2, hiss_db=-70, mix=1.0, seed=1):
        self.sr, self.drv, self.outg = sr, 10 ** (drive_db / 20), 10 ** (output_db / 20)
        bf, bdb, hf = SPEEDS[speed]
        self.filters = [_biquad("peak", bf, 1.0, bdb, sr), _biquad("lp", hf, 0.6, 0, sr), _biquad("hp", bf * 0.35, 0.707, 0, sr)]
        self.alpha, self.rate = 0.6 * (1 - bias), 0.25 + 0.75 * bias
        self.wf, self.hiss, self.mix = wow, 10 ** (hiss_db / 20), mix
        self.rng = np.random.default_rng(seed)

    def filters_response(self, freqs):
        z = np.exp(-2j * np.pi * np.asarray(freqs) / self.sr); h = np.ones_like(z)
        for b, a in self.filters:
            h *= (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)
        return h

    def process(self, x):
        sr, m, bsz = self.sr, 0.0, 4096
        buf = np.zeros(bsz); wp = 0; ph1 = ph2 = 0.0
        st = [[0.0, 0.0] for _ in self.filters]; y_out = np.empty_like(x)
        noise = self.rng.uniform(-1, 1, len(x)) * self.hiss
        for n, s in enumerate(x):
            m += (math.tanh(self.drv * s + self.alpha * m) - m) * self.rate
            buf[wp] = m * (1 - self.alpha) / self.drv
            ph1 = (ph1 + 0.6 / sr) % 1; ph2 = (ph2 + 7 / sr) % 1
            d = 0.002 * sr + self.wf * (0.0015 * sr * math.sin(2 * math.pi * ph1) + 0.0002 * sr * math.sin(2 * math.pi * ph2))
            rp = (wp - d) % bsz; i = int(rp); fr = rp - i
            y = buf[i] * (1 - fr) + buf[(i + 1) % bsz] * fr; wp = (wp + 1) % bsz
            for (b, a), z in zip(self.filters, st):
                o = b[0] * y + z[0]; z[0] = b[1] * y - a[1] * o + z[1]; z[1] = b[2] * y - a[2] * o; y = o
            y += noise[n]
            y_out[n] = (y * self.mix + s * (1 - self.mix)) * self.outg
        return y_out
