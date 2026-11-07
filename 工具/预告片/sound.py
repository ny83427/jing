#!/usr/bin/env python3
"""《景》预告片配乐：全部合成。输出 out/sound.wav"""
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 48000
DUR = 32.6
N = int(SR * DUR)
L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(1)
T = np.arange(N) / SR

def lp(x, f, order=2):
    return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x)
def bp(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)
def env_curve(points):
    ts = [p[0] for p in points]; vs = [p[1] for p in points]
    return np.interp(T, ts, vs)
def add(sig, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= N: return
    sig = sig[: N - i]
    L[i:i + len(sig)] += sig * gain * (1 - max(pan, 0))
    R[i:i + len(sig)] += sig * gain * (1 + min(pan, 0))

# 场景起点：0 4.0 8.2 12.2 16.2 20.4 24.2 27.6
# 风
wind = lp(rng.normal(0, 1, N), 700)
wind = bp(wind, 120, 900) * (0.6 + 0.4 * np.sin(T * 0.7) * np.sin(T * 0.23 + 1))
wenv = env_curve([(0, 0.0), (1.5, 0.5), (4, 0.4), (8, 0.25), (12.2, 0.4), (20.4, 0.2), (24.2, 0.6), (27.4, 0.5), (27.6, 0.05), (30, 0.15), (32.6, 0)])
add(wind * wenv * 1.4, 0, pan=0.2)
add(lp(rng.normal(0, 1, N), 500) * wenv * 0.9, 0, pan=-0.2)

# 低音持续
drone = (np.sin(2 * np.pi * 36.7 * T) + 0.6 * np.sin(2 * np.pi * 55.0 * T + 0.5) + 0.35 * np.sin(2 * np.pi * 73.4 * T + 1.1))
drone *= 0.85 + 0.15 * np.sin(T * 1.3)
denv = env_curve([(0, 0), (3, 0.25), (8.2, 0.35), (16, 0.45), (24.2, 0.6), (27.5, 0.8), (27.6, 0), (27.9, 0), (28.2, 0.55), (32.6, 0)])
add(drone * denv * 0.5, 0)

# 弦乐垫（小调和弦，锯齿波低通）
def saw(f, n):
    t = np.arange(n) / SR
    return 2 * ((t * f) % 1) - 1
def pad(freqs, dur, cutoff=900):
    n = int(dur * SR)
    s = sum(saw(f * d, n) for f in freqs for d in (0.997, 1.0, 1.004))
    s = lp(s, cutoff, 2) / (len(freqs) * 3)
    a = np.minimum(1, np.arange(n) / (SR * 1.2)) * np.minimum(1, (n - np.arange(n)) / (SR * 1.5))
    return s * a
add(pad([73.4, 110, 146.8, 174.6], 8.6, 700), 8.0, 0.5, pan=-0.15)        # D 小调 8.2–16.2
add(pad([65.4, 98, 130.8, 155.6], 4.6, 800), 16.0, 0.5, pan=0.15)          # C 小调 碑
add(pad([58.3, 87.3, 116.5, 146.8], 3.8, 1000), 20.2, 0.55)                 # 会昌 降B
add(pad([73.4, 110, 146.8, 220, 293.7], 3.6, 1200), 24.0, 0.5)               # 西出 D
add(pad([73.4, 110, 146.8, 174.6, 220], 4.8, 900), 27.9, 0.6)                # 片名

# 钟
def bell(f0, dur=5.0):
    n = int(dur * SR); t = np.arange(n) / SR
    s = np.zeros(n)
    for ratio, amp, dec in ((0.5, 0.5, 1.4), (1, 1, 1.0), (2.0, 0.5, 0.7), (2.76, 0.35, 0.5), (5.4, 0.2, 0.3), (8.9, 0.1, 0.2)):
        s += amp * np.sin(2 * np.pi * f0 * ratio * t) * np.exp(-t / (dur * dec * 0.35))
    return s * np.minimum(1, t * 400)
add(bell(196), 0.25, 0.28, pan=-0.1)
add(bell(146.8, 6), 28.2, 0.3)

# 太鼓
def taiko(size=1.0, dur=1.6):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 42 + 90 * np.exp(-t * 18 / size)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 3.2 / size)
    hit = lp(rng.normal(0, 1, n), 1800) * np.exp(-t * 45)
    return np.tanh((body + 0.5 * hit) * 1.6)
for t0, g in [(4.0, 1.0), (5.0, 0.6), (5.55, 0.6), (6.4, 0.9), (7.1, 0.55), (7.45, 0.6), (7.8, 0.8)]:
    add(taiko(), t0, 0.55 * g, pan=rng.uniform(-0.2, 0.2))
for t0 in (8.2, 12.2, 16.2):
    add(taiko(1.5, 2.4), t0, 0.5)
for t0, g in [(20.4, 1.0), (21.2, 0.6), (21.6, 0.6), (22.3, 0.8), (22.7, 0.6), (23.05, 0.65), (23.35, 0.7), (23.6, 0.75), (23.8, 0.8), (23.95, 0.85), (24.08, 0.9)]:
    add(taiko(0.9), t0, 0.55 * g, pan=rng.uniform(-0.25, 0.25))
add(taiko(1.4, 2.0), 24.2, 0.45)
add(taiko(2.4, 4.0), 27.9, 0.85)          # 片名重鼓
# 次低音下潜
n = int(2.5 * SR); tt = np.arange(n) / SR
sub = np.sin(2 * np.pi * np.cumsum(30 + 40 * np.exp(-tt * 2)) / SR) * np.exp(-tt * 1.2)
add(sub, 27.9, 0.6)

# 上扬噪声（片名前）
n = int(1.2 * SR); tt = np.arange(n) / SR
riser = bp(rng.normal(0, 1, n), 400, 5000) * (tt / 1.2) ** 2.5
add(riser, 26.4, 0.35)
add(riser * 0.8, 3.0, 0.3)

# 拨弦（Karplus-Strong，古筝味）
def pluck(f, dur=2.4, bright=0.5):
    n = int(dur * SR); p = int(SR / f)
    buf = rng.uniform(-1, 1, p) * 1.0
    out = np.zeros(n)
    for i in range(n):
        j = i % p
        out[i] = buf[j]
        buf[j] = 0.996 * (bright * buf[j] + (1 - bright) * buf[(j + 1) % p])
    out = out * np.exp(-np.arange(n) / SR * 1.2)
    return lp(out, 3500)
D3, F3, G3, A3, C4, D4, F4 = 146.8, 174.6, 196.0, 220.0, 261.6, 293.7, 349.2
melody = [(8.7, A3), (9.3, D4), (9.9, C4), (10.5, A3), (11.4, G3), (11.8, A3),
          (12.7, D4), (13.2, F4), (13.7, D4), (14.4, C4), (15.2, A3),
          (16.6, G3), (17.3, A3), (18.0, C4), (18.8, D4), (19.6, A3),
          (24.6, D4), (25.4, A3), (26.1, D4)]
for t0, f in melody:
    add(pluck(f), t0, 0.32, pan=rng.uniform(-0.35, 0.35))
add(pluck(D3, 4) + pluck(A3, 4), 28.5, 0.3)

# 混响（简单多抽头）
def reverb(x):
    y = x.copy()
    for d, g in ((0.031, 0.32), (0.047, 0.28), (0.071, 0.24), (0.113, 0.2), (0.167, 0.16), (0.233, 0.12), (0.31, 0.09)):
        k = int(d * SR)
        y[k:] += x[:-k] * g
    return lp(y, 6000)
L2, R2 = reverb(L), reverb(np.roll(R, 37))
mix = np.stack([L2, R2], 1)
mix /= np.max(np.abs(mix)) + 1e-9
mix = np.tanh(mix * 1.4) / np.tanh(1.4)
fade = np.minimum(1, (N - np.arange(N)) / (SR * 1.2))[:, None]
mix *= fade * 0.92
wavfile.write("out/sound.wav", SR, (mix * 32767).astype(np.int16))
print("ok", mix.shape)
