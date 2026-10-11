import math, sys, pathlib, numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from reference_dsp import FyahComp, FyahTape
SR = 48000
tone = lambda f, a, s: a * np.sin(2 * np.pi * f * np.arange(int(SR * s)) / SR)
pk_db = lambda y: 20 * math.log10(np.sqrt(np.mean(y[-4800:] ** 2)) * math.sqrt(2))

def test_comp_static_slopes():
    for r in (4, 8, 12, 20):
        o = [pk_db(FyahComp(SR, ratio=r, saturation=0, attack_us=100, release_ms=100).process(tone(1000, 10 ** (L / 20), 0.3))) for L in (-8, 0)]
        assert abs((o[1] - o[0]) / 8 - 1 / r) < 0.06

def test_comp_below_threshold_is_unity():
    assert abs(pk_db(FyahComp(SR, saturation=0).process(tone(1000, 10 ** (-30 / 20), 0.3))) + 30) < 0.05

def test_all_buttons_overcompresses():
    a = pk_db(FyahComp(SR, ratio="all", saturation=0).process(tone(1000, 1.0, 0.3)))
    b = pk_db(FyahComp(SR, ratio=20, saturation=0).process(tone(1000, 1.0, 0.3)))
    assert a < b - 2

def test_release_time_constant():
    x = np.concatenate([tone(1000, 1, 0.5), np.zeros(SR * 2)])
    _, gr = FyahComp(SR, ratio=20, saturation=0, release_ms=300).process(x, True)
    g0 = gr[int(0.5 * SR) - 1]; t = np.argmax(gr[int(0.5 * SR):] <= 0.368 * g0) / SR * 1000
    assert 280 < t < 320

def test_saturation_is_asymmetric_even_harmonics():
    y = FyahComp(SR, input_db=-30, saturation=1.0).process(tone(1000, 1.0, 0.5))
    S = np.abs(np.fft.rfft(y[SR // 4:] * np.hanning(len(y) - SR // 4)))
    assert S[2000 * len(S) // (SR // 2)] / S.max() > 1e-4  # 2nd harmonic present

def test_tape_head_bump_and_hf_loss_by_speed():
    f = np.array([45, 65, 110, 1000, 10000]); r = {s: 20 * np.log10(abs(FyahTape(SR, speed=s).filters_response(f))) for s in (7.5, 15, 30)}
    assert r[7.5][0] > 2 and r[15][1] > 1.5 and r[30][2] > 1.5
    assert r[7.5][4] < r[15][4] < r[30][4] and abs(r[30][3]) < 0.2

def test_tape_thd_grows_with_level():
    def thd(a):
        y = FyahTape(SR, wow=0, hiss_db=-200).process(tone(1000, a, 0.3))[SR // 10:]
        S = np.abs(np.fft.rfft(y * np.hanning(len(y)))); k = 1000 * len(y) // SR
        return S[3 * k - 2:3 * k + 3].max() / S[k - 2:k + 3].max()
    assert thd(0.03) < thd(0.3) < thd(1.0)
