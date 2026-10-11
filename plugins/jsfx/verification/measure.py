"""Offline measurements of the Hazewave JSFX reference DSP. Writes results.json and PNG plots."""
import json, math, pathlib, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from reference_dsp import FyahComp, FyahTape
SR = 48000; OUT = pathlib.Path(__file__).parent / "results"; OUT.mkdir(exist_ok=True)
db = lambda v: 20 * np.log10(np.maximum(v, 1e-12))
rms = lambda v: float(np.sqrt(np.mean(v ** 2)))

def tone(f, amp, sec): t = np.arange(int(SR * sec)) / SR; return amp * np.sin(2 * np.pi * f * t)

def thd(y, f):
    w = np.hanning(len(y)); S = np.abs(np.fft.rfft(y * w)); fr = np.fft.rfftfreq(len(y), 1 / SR)
    pk = lambda h: S[np.argmin(abs(fr - h * f)) - 2: np.argmin(abs(fr - h * f)) + 3].max()
    return math.sqrt(sum(pk(h) ** 2 for h in range(2, 10))) / pk(1), pk(2) / pk(1), pk(3) / pk(1)

def comp_curve():
    res = {}; levels = np.arange(-40, 1, 2.0)
    for r in [4, 8, 12, 20, "all"]:
        outs = []
        for L in levels:
            y = FyahComp(SR, ratio=r, saturation=0, attack_us=100, release_ms=100).process(tone(1000, 10 ** (L / 20), 0.3))
            outs.append(float(db(rms(y[-4800:]) * math.sqrt(2))))
        res[str(r)] = outs; plt.plot(levels, outs, label=f"ratio {r}")
    plt.plot(levels, levels, "k:", label="unity"); plt.xlabel("in dBFS peak"); plt.ylabel("out dBFS peak"); plt.legend(); plt.grid()
    plt.title("FyahComp static curve"); plt.savefig(OUT / "comp_static_curve.png"); plt.close()
    return {"levels_db": levels.tolist(), "out_db": res}

def comp_timing():
    res = {}
    for a_us, r_ms in [(20, 50), (200, 300), (800, 1100)]:
        x = np.concatenate([tone(1000, 0.01, 0.2), tone(1000, 1.0, 0.5), tone(1000, 0.01, 3.0)])
        _, gr = FyahComp(SR, ratio=20, saturation=0, attack_us=a_us, release_ms=r_ms).process(x, True)
        s, e = int(0.2 * SR), int(0.7 * SR); grmax = gr[e - 100]
        t_att = (np.argmax(gr[s:] >= 0.632 * grmax)) / SR * 1e6
        t_rel = (np.argmax(gr[e:] <= 0.368 * grmax)) / SR * 1e3
        res[f"att{a_us}us_rel{r_ms}ms"] = {"gr_max_db": round(float(grmax), 2), "attack_63pct_us": round(t_att, 1), "release_63pct_ms": round(t_rel, 1)}
        plt.plot(np.arange(len(gr)) / SR, gr, label=f"A{a_us}us R{r_ms}ms")
    plt.xlabel("s"); plt.ylabel("GR dB"); plt.legend(); plt.grid(); plt.title("FyahComp attack/release (0 dBFS burst, ratio 20)")
    plt.savefig(OUT / "comp_timing.png"); plt.close(); return res

def thd_sweep(make, label, fname):
    res = {}; levels = list(range(-30, 7, 3))
    for L in levels:
        y = make().process(tone(1000, 10 ** (L / 20), 0.5))[SR // 4:]
        t, h2, h3 = thd(y, 1000); res[L] = {"thd_pct": round(100 * t, 4), "h2_db": round(float(db(h2)), 1), "h3_db": round(float(db(h3)), 1)}
    plt.semilogy(levels, [res[L]["thd_pct"] for L in levels], "o-"); plt.xlabel("input dBFS"); plt.ylabel("THD %"); plt.grid(); plt.title(label)
    plt.savefig(OUT / fname); plt.close(); return res

def tape_fr():
    f = np.logspace(np.log10(20), np.log10(23000), 400); res = {}
    for sp in [7.5, 15, 30]:
        h = db(np.abs(FyahTape(SR, speed=sp).filters_response(f))); plt.semilogx(f, h, label=f"{sp} ips")
        pick = lambda q: round(float(np.interp(q, f, h)), 2)
        res[str(sp)] = {"bump_peak_db": round(float(h[f < 300].max()), 2), "bump_peak_hz": round(float(f[f < 300][h[f < 300].argmax()]), 1),
                        "20Hz": pick(20), "1kHz": pick(1000), "10kHz": pick(10000), "16kHz": pick(16000), "20kHz": pick(20000)}
    plt.xlabel("Hz"); plt.ylabel("dB"); plt.legend(); plt.grid(which="both"); plt.title("FyahTape linear response (head bump + HF loss)")
    plt.savefig(OUT / "tape_freq_response.png"); plt.close()
    # measured with real signal path (small-signal sine, no hiss/wow) to cross-check filter analysis
    chk = {}
    for fq in [50, 1000, 10000]:
        y = FyahTape(SR, speed=7.5, wow=0, hiss_db=-200).process(tone(fq, 0.01, 0.5))[SR // 4:]
        chk[fq] = round(float(db(rms(y) / (0.01 / math.sqrt(2)))), 2)
    res["sine_check_7.5ips_db"] = chk; return res

def tape_wow_hiss():
    y = FyahTape(SR, wow=1.0, hiss_db=-200).process(tone(1000, 0.1, 4.0))[SR:]
    a = np.unwrap(np.angle(np.fft.ifft(np.fft.fft(y) * (np.arange(len(y)) < len(y) // 2) * 2)))
    inst = np.diff(a) * SR / (2 * np.pi); dev = inst[1000:-1000] - 1000
    h = FyahTape(SR, hiss_db=-60, wow=0).process(np.zeros(SR))
    return {"wow100_peak_freq_dev_hz": round(float(np.percentile(abs(dev), 99)), 2), "hiss_-60dB_setting_rms_dbfs": round(float(db(rms(h[SR // 4:]))), 1)}

if __name__ == "__main__":
    r = {"comp_static": comp_curve(), "comp_timing": comp_timing(),
         "comp_thd_sat30": thd_sweep(lambda: FyahComp(SR, ratio=4, input_db=-30, saturation=0.3), "FyahComp THD (input -30dB trim => no GR, sat 30%)", "comp_thd.png"),
         "tape_thd_15ips_bias50": thd_sweep(lambda: FyahTape(SR, wow=0, hiss_db=-200), "FyahTape THD vs level (15 ips, bias 50%)", "tape_thd.png"),
         "tape_fr": tape_fr(), "tape_wow_hiss": tape_wow_hiss()}
    (OUT / "results.json").write_text(json.dumps(r, indent=1)); print(json.dumps(r, indent=1))
