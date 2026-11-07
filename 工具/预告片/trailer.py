#!/usr/bin/env python3
"""《景》预告片：程序绘制水墨画面，逐场景编码。
用法: python3 trailer.py [scene_index ...]   不带参数则渲染全部
      python3 trailer.py still <scene> <t>   导出单帧检查
"""
import math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1920, 1080, 30
BAR = 138
HERE = os.path.dirname(os.path.abspath(__file__))
BRUSH = os.path.join(HERE, "fonts/MaShanZheng.ttf")
SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
SERIF_B = "/usr/share/fonts/opentype/noto/NotoSerifCJK-SemiBold.ttc"
IVORY = (236, 226, 202)
GOLD = (201, 166, 102)

_font_cache = {}
def font(path, size, idx=None):
    k = (path, size)
    if k not in _font_cache:
        if path.endswith(".ttc"):
            # index 2 = SC in Noto CJK ttc (JP, KR, SC, TC, HK)
            _font_cache[k] = ImageFont.truetype(path, size, index=2)
        else:
            _font_cache[k] = ImageFont.truetype(path, size)
    return _font_cache[k]

def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)

def fade(t, a, b, fin=0.6, fout=0.6):
    """a..b 可见，含淡入淡出，返回 0..1"""
    if t < a or t > b:
        return 0.0
    return min(ease((t - a) / fin) if fin else 1, ease((b - t) / fout) if fout else 1)

# ---------- 基础图层 ----------
def vgrad(h, w, stops):
    ys = np.linspace(0, 1, h)
    out = np.zeros((h, 3))
    pos = [s[0] for s in stops]
    for c in range(3):
        out[:, c] = np.interp(ys, pos, [s[1][c] for s in stops])
    arr = np.repeat(out[:, None, :], w, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")

def ridge_layer(w, h, base, amp, seed, color, fadelen=260, rough=1.0, alpha=1.0, smooth=False):
    rng = np.random.default_rng(seed)
    x = np.arange(w)
    prof = np.full(w, float(base))
    for i in range(5):
        f = (i + 1) ** 1.6 / w * rng.uniform(2, 4) * math.pi
        prof -= amp / (i + 1) ** 1.1 * (np.sin(f * x + rng.uniform(0, 6.28)) * 0.5 + 0.5)
    if not smooth:
        walk = np.cumsum(rng.normal(0, 1.2 * rough, w))
        walk -= np.convolve(walk, np.ones(301) / 301, mode="same")
        prof += np.convolve(walk, np.ones(9) / 9, mode="same")
    yy = np.arange(h)[:, None]
    d = yy - prof[None, :]
    a = np.where(d >= 0, np.clip(1 - d / fadelen * 0.75, 0.25, 1), 0)
    # 边缘柔化
    a = np.where((d > -2) & (d < 0), 0.5, a) * alpha
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA"), prof

def mist_layer(w, h, y, thick, color, alpha=0.55):
    yy = np.arange(h)[:, None]
    a = np.exp(-((yy - y) / thick) ** 2) * alpha
    a = np.repeat(a, w, axis=1)
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")

def glow(r, color, power=2.0, strength=1.0):
    s = 2 * r
    yy, xx = np.mgrid[0:s, 0:s]
    d = np.sqrt((xx - r) ** 2 + (yy - r) ** 2) / r
    a = np.clip(1 - d, 0, 1) ** power * strength
    arr = np.zeros((s, s, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")

def paste_alpha(base, layer, xy, alpha=1.0):
    if alpha <= 0.003:
        return
    if alpha < 0.999:
        layer = layer.copy()
        a = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer.putalpha(a)
    base.alpha_composite(layer, dest=(int(xy[0]), int(xy[1])))

def crop_pan(layer, offx, offy=0):
    return layer.crop((int(offx), int(offy), int(offx) + W, int(offy) + H))

def text_img(s, size, path=SERIF, color=IVORY, spacing=0.35, shadow=True):
    f = font(path, size)
    chars = list(s)
    widths = [f.getbbox(c)[2] - f.getbbox(c)[0] if c.strip() else size * 0.6 for c in chars]
    gap = size * spacing
    tw = int(sum(widths) + gap * (len(chars) - 1)) + 40
    th = int(size * 1.6)
    im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 20
    for c, wd in zip(chars, widths):
        if c.strip():
            bb = f.getbbox(c)
            d.text((x - bb[0], size * 0.25), c, font=f, fill=color + (255,))
        x += wd + gap
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sh.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(size * 0.18)).point(lambda v: int(v * 0.85)))
        out = Image.new("RGBA", im.size, (0, 0, 0, 0))
        out.alpha_composite(sh)
        out.alpha_composite(im)
        im = out
    return im

def draw_text(base, img, cy, alpha, rise=0.0, cx=W / 2):
    if alpha <= 0:
        return
    paste_alpha(base, img, (cx - img.width / 2, cy - img.height / 2 + rise), alpha)

def letterbox(img):
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, BAR), fill=(0, 0, 0, 255))
    d.rectangle((0, H - BAR, W, H), fill=(0, 0, 0, 255))

def grain(img, t, amt=10):
    rng = np.random.default_rng(int(t * 1000) % 100000)
    n = rng.integers(-amt, amt + 1, (H // 2, W // 2, 1), dtype=np.int16)
    n = np.repeat(np.repeat(n, 2, 0), 2, 1)
    a = np.asarray(img.convert("RGB"), np.int16) + n
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")

def vignette_layer():
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
    a = np.clip((d - 0.55) * 1.3, 0, 0.85)
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")
VIG = None

class Dust:
    def __init__(self, n, seed, color, size=(1, 3), vel=((-10, 10), (-8, 8)), region=(0, W, BAR, H - BAR), alpha=(60, 160)):
        r = np.random.default_rng(seed)
        self.p = np.c_[r.uniform(region[0], region[1], n), r.uniform(region[2], region[3], n)]
        self.v = np.c_[r.uniform(*vel[0], n), r.uniform(*vel[1], n)]
        self.s = r.uniform(*size, n)
        self.a = r.uniform(*alpha, n)
        self.ph = r.uniform(0, 6.28, n)
        self.color = color
        self.region = region
    def draw(self, img, t, mult=1.0, flicker=False):
        d = ImageDraw.Draw(img)
        x0, x1, y0, y1 = self.region
        pos = self.p + self.v * t
        pos[:, 0] = x0 + (pos[:, 0] - x0) % (x1 - x0)
        pos[:, 1] = y0 + (pos[:, 1] - y0) % (y1 - y0)
        for (x, y), s, a, ph in zip(pos, self.s, self.a, self.ph):
            aa = a * mult * ((0.55 + 0.45 * math.sin(t * 6 + ph)) if flicker else 1)
            d.ellipse((x - s, y - s, x + s, y + s), fill=self.color + (int(min(255, aa)),))

# ---------- 剪影 ----------
def soldier(d, x, y, s, color, phase, spear=True, banner=None, t=0):
    bob = math.sin(phase) * 2 * s
    y = y + bob
    d.ellipse((x - 4 * s, y - 34 * s, x + 4 * s, y - 26 * s), fill=color)          # 头
    d.polygon([(x - 2 * s, y - 32 * s), (x, y - 40 * s), (x + 2 * s, y - 32 * s)], fill=color)  # 盔缨
    d.polygon([(x - 6 * s, y - 26 * s), (x + 6 * s, y - 26 * s), (x + 8 * s, y - 6 * s), (x - 8 * s, y - 6 * s)], fill=color)
    lg = math.sin(phase) * 5 * s
    d.line((x - 3 * s, y - 7 * s, x - 3 * s + lg, y + 4 * s), fill=color, width=max(2, int(3 * s)))
    d.line((x + 3 * s, y - 7 * s, x + 3 * s - lg, y + 4 * s), fill=color, width=max(2, int(3 * s)))
    if spear:
        d.line((x + 7 * s, y - 20 * s, x + 11 * s, y - 62 * s), fill=color, width=max(1, int(1.6 * s)))
        d.polygon([(x + 10 * s, y - 62 * s), (x + 12.5 * s, y - 70 * s), (x + 13 * s, y - 61 * s)], fill=color)
    if banner:
        pole_top = (x - 6 * s, y - 95 * s)
        d.line((x - 6 * s, y - 15 * s, *pole_top), fill=color, width=max(2, int(2 * s)))
        pts = []
        for i in range(13):
            u = i / 12
            pts.append((pole_top[0] - u * 34 * s, pole_top[1] + 2 * s + math.sin(t * 5 + u * 5 + phase) * 4 * s * u))
        for i in range(12, -1, -1):
            u = i / 12
            pts.append((pole_top[0] - u * 34 * s, pole_top[1] + 24 * s + math.sin(t * 5 + u * 5 + phase) * 4 * s * u))
        d.polygon(pts, fill=banner)

def horse_rider(d, x, y, s, color, phase):
    lg = math.sin(phase) * 7 * s
    d.ellipse((x - 26 * s, y - 34 * s, x + 18 * s, y - 14 * s), fill=color)  # 马身
    d.polygon([(x + 12 * s, y - 32 * s), (x + 26 * s, y - 52 * s), (x + 34 * s, y - 48 * s), (x + 20 * s, y - 24 * s)], fill=color)
    d.polygon([(x + 26 * s, y - 52 * s), (x + 38 * s, y - 46 * s), (x + 36 * s, y - 42 * s), (x + 28 * s, y - 44 * s)], fill=color)
    for dx, sg in ((-20, 1), (-14, -1), (8, -1), (14, 1)):
        d.line((x + dx * s, y - 18 * s, x + dx * s + lg * sg, y + 6 * s), fill=color, width=max(2, int(3 * s)))
    d.line((x - 26 * s, y - 30 * s, x - 36 * s, y - 14 * s), fill=color, width=max(2, int(3 * s)))  # 尾
    d.polygon([(x - 8 * s, y - 34 * s), (x + 4 * s, y - 34 * s), (x + 2 * s, y - 58 * s), (x - 6 * s, y - 58 * s)], fill=color)  # 人
    d.ellipse((x - 7 * s, y - 70 * s, x + 3 * s, y - 59 * s), fill=color)
    d.polygon([(x - 10 * s, y - 50 * s), (x + 6 * s, y - 50 * s), (x + 4 * s, y - 34 * s), (x - 16 * s, y - 30 * s)], fill=color)  # 斗篷

def camel(d, x, y, s, color, phase, rider=True):
    lg = math.sin(phase) * 8 * s
    d.ellipse((x - 30 * s, y - 50 * s, x + 22 * s, y - 26 * s), fill=color)
    d.ellipse((x - 20 * s, y - 64 * s, x - 4 * s, y - 40 * s), fill=color)  # 驼峰
    d.ellipse((x - 2 * s, y - 62 * s, x + 12 * s, y - 40 * s), fill=color)
    d.polygon([(x + 16 * s, y - 44 * s), (x + 30 * s, y - 56 * s), (x + 36 * s, y - 78 * s), (x + 42 * s, y - 76 * s), (x + 38 * s, y - 52 * s), (x + 22 * s, y - 34 * s)], fill=color)
    d.polygon([(x + 36 * s, y - 80 * s), (x + 50 * s, y - 76 * s), (x + 48 * s, y - 72 * s), (x + 38 * s, y - 72 * s)], fill=color)
    for dx, sg in ((-24, 1), (-16, -1), (10, -1), (17, 1)):
        d.line((x + dx * s, y - 30 * s, x + dx * s + lg * sg, y + 6 * s), fill=color, width=max(2, int(3.2 * s)))
    if rider:
        d.polygon([(x - 10 * s, y - 62 * s), (x + 0 * s, y - 62 * s), (x - 2 * s, y - 86 * s), (x - 9 * s, y - 86 * s)], fill=color)
        d.ellipse((x - 11 * s, y - 97 * s, x - 1 * s, y - 86 * s), fill=color)

def lotus_cross(size, color=GOLD):
    """景教莲花十字（白描），返回 RGBA"""
    S = size * 4  # 超采样
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    cy = S * 0.40
    arm = S * 0.30
    w0, w1 = S * 0.035, S * 0.10
    for ang in range(4):
        a = ang * math.pi / 2
        ca, sa = math.cos(a), math.sin(a)
        def P(u, v):
            return (c + ca * u - sa * v, cy + sa * u + ca * v)
        d.polygon([P(0, -w0), P(arm, -w1), P(arm, w1), P(0, w0)], fill=color + (255,))
        for v in (-w1 * 0.9, 0, w1 * 0.9):
            px, py = P(arm + S * 0.03, v)
            r = S * 0.022
            d.ellipse((px - r, py - r, px + r, py + r), fill=color + (255,))
    r = S * 0.05
    d.ellipse((c - r, cy - r, c + r, cy + r), fill=color + (255,))
    # 莲座
    base = S * 0.84
    lw = S * 0.02
    for i, (dx, hgt, wd) in enumerate([(0, 0.20, 0.08), (-0.12, 0.16, 0.08), (0.12, 0.16, 0.08), (-0.23, 0.10, 0.08), (0.23, 0.10, 0.08)]):
        x0 = c + dx * S
        h = hgt * S
        w = wd * S
        pts = []
        for k in range(21):
            u = k / 20 * math.pi
            pts.append((x0 - math.cos(u) * w, base - math.sin(u) ** 1.5 * h))
        d.line(pts, fill=color + (255,), width=int(lw))
    d.line((c - S * 0.36, base, c + S * 0.36, base), fill=color + (255,), width=int(lw))
    d.line((c, cy + arm + S * 0.05, c, base - S * 0.17), fill=color + (255,), width=int(lw * 1.4))
    # 云纹
    for sg in (-1, 1):
        pts = [(c + sg * (S * 0.36 + k * S * 0.004), base + math.sin(k / 6) * S * 0.02) for k in range(30)]
        d.line(pts, fill=color + (255,), width=int(lw))
    return im.resize((size, size), Image.LANCZOS)

# ---------- 场景 ----------
SCENES = []
def scene(dur):
    def deco(fn):
        SCENES.append((fn, dur))
        return fn
    return deco

def dip(img, t, dur, fin=0.5, fout=0.45):
    k = min(ease(t / fin) if fin else 1, ease((dur - t) / fout) if fout else 1)
    if k < 0.999:
        img = Image.blend(Image.new("RGB", img.size, (0, 0, 0)), img, k)
    return img

def finish(img, t, dur, fin=0.5, fout=0.45, g=8):
    img.alpha_composite(VIG)
    letterbox(img)
    out = grain(img, t, g)
    return dip(out, t, dur, fin, fout)

# 1 黑暗中一盏灯
class S1:
    def __init__(s):
        s.bg = vgrad(H, W, [(0, (6, 5, 4)), (1, (14, 11, 8))])
        s.g1 = glow(520, (210, 140, 60), 2.2, 0.55)
        s.g2 = glow(90, (255, 210, 140), 1.6, 1.0)
        s.dust = Dust(140, 1, (230, 190, 130), (0.8, 2.2), ((-6, 6), (-14, -3)), alpha=(30, 120))
        s.t1 = text_img("天宝十四载", 76, SERIF_B, IVORY, 0.55)
        s.t2 = text_img("安禄山起兵范阳", 40, SERIF, (200, 186, 160), 0.6)
    def frame(s, t, dur):
        img = s.bg.copy()
        k = ease(t / 1.6)
        fl = 0.85 + 0.15 * math.sin(t * 13) * math.sin(t * 7.3 + 1)
        cx, cy = W / 2, 690
        paste_alpha(img, s.g1, (cx - 520, cy - 520), k * fl)
        d = ImageDraw.Draw(img)
        # 灯盏与罩
        d.polygon([(cx - 70, cy + 58), (cx + 70, cy + 58), (cx + 40, cy + 82), (cx - 40, cy + 82)], fill=(40, 30, 20, int(255 * k)))
        d.rectangle((cx - 58, cy - 70, cx + 58, cy + 58), outline=(120, 88, 50, int(200 * k)), width=3)
        for yy in range(-70, 58, 16):
            d.line((cx - 58, cy + yy, cx + 58, cy + yy), fill=(90, 66, 40, int(90 * k)), width=1)
        paste_alpha(img, s.g2, (cx - 90, cy - 70), k * fl)
        fh = 34 * fl
        sway = math.sin(t * 5) * 3
        d.polygon([(cx - 9, cy + 30), (cx + 9, cy + 30), (cx + 2 + sway, cy + 30 - fh), (cx - 2 + sway, cy + 30 - fh)], fill=(255, 236, 190, int(255 * k)))
        d.ellipse((cx - 9, cy + 20, cx + 9, cy + 38), fill=(255, 220, 150, int(255 * k)))
        s.dust.draw(img, t, k)
        draw_text(img, s.t1, 400, fade(t, 1.2, dur - 0.3, 0.9, 0.5), -12 * ease((t - 1.2) / 3))
        draw_text(img, s.t2, 500, fade(t, 2.2, dur - 0.3, 0.9, 0.5))
        return finish(img, t, dur, fin=0.01)
scene(4.0)(S1)

# 2 烽火 大军
class S2:
    def __init__(s):
        s.bg = vgrad(H, W, [(0, (24, 16, 12)), (0.45, (120, 62, 30)), (0.62, (190, 110, 50)), (0.75, (70, 40, 24)), (1, (20, 14, 10))])
        s.sun = glow(420, (255, 170, 80), 1.4, 0.75)
        s.m1, _ = ridge_layer(2600, H, 560, 220, 11, (70, 44, 32), 300, alpha=0.75)
        s.m2, _ = ridge_layer(2800, H, 700, 160, 12, (40, 26, 20), 260, alpha=0.9)
        s.m3, s.p3 = ridge_layer(3200, H, 830, 70, 13, (14, 10, 8), 400, smooth=True)
        s.mist = mist_layer(2600, H, 660, 60, (200, 130, 70), 0.35)
        s.puff = glow(160, (40, 26, 20), 1.3, 0.55)
        r = np.random.default_rng(22)
        s.puffs = [(r.uniform(0, W), r.uniform(450, 800), r.uniform(-40, -15), r.uniform(-12, -4), r.uniform(0.5, 1)) for _ in range(16)]
        s.embers = Dust(70, 3, (255, 150, 60), (1, 2.5), ((-60, -20), (-40, -10)), alpha=(80, 220))
        s.t1 = text_img("大唐　烽烟四起", 64, SERIF_B, IVORY, 0.5)
    def frame(s, t, dur):
        img = s.bg.copy()
        paste_alpha(img, s.sun, (1300 - 420, 600 - 420), 0.9)
        img.alpha_composite(crop_pan(s.m1, 200 + t * 18))
        img.alpha_composite(crop_pan(s.mist, 100 + t * 30))
        img.alpha_composite(crop_pan(s.m2, 300 + t * 34))
        off = 500 + t * 70
        img.alpha_composite(crop_pan(s.m3, off))
        for (px, py, vx, vy, a) in s.puffs:
            x = (px + vx * t) % (W + 320) - 160
            paste_alpha(img, s.puff, (x - 160, py + vy * t - 160), a)
        d = ImageDraw.Draw(img)
        col = (10, 7, 6, 255)
        for i in range(46):
            gx = 2900 - i * 58 - (i % 3) * 14 + t * 55
            sx = gx - off
            if -80 < sx < W + 80:
                y = s.p3[int(min(max(gx, 0), 3199))] + 6
                ban = (150, 26, 20, 255) if i % 9 == 4 else ((28, 20, 16, 255) if i % 9 == 0 else None)
                soldier(d, sx, y, 1.25, col, t * 7 + i * 1.3, banner=ban, t=t)
        s.embers.draw(img, t, 1, flicker=True)
        draw_text(img, s.t1, 300, fade(t, 1.0, dur - 0.35, 0.8, 0.5))
        return finish(img, t, dur)
scene(4.2)(S2)

# 3 一人一骑 在山脊
class S3:
    def __init__(s):
        s.bg = vgrad(H, W, [(0, (16, 18, 22)), (0.5, (70, 72, 74)), (0.7, (150, 140, 120)), (1, (30, 28, 26))])
        s.m1, _ = ridge_layer(2400, H, 600, 240, 21, (60, 62, 64), 320, alpha=0.6)
        s.m2, _ = ridge_layer(2400, H, 760, 180, 22, (34, 34, 36), 300, alpha=0.85)
        s.mist = mist_layer(2400, H, 720, 70, (190, 182, 165), 0.5)
        s.cloud = mist_layer(2400, H, 380, 90, (120, 120, 118), 0.25)
        s.snow = Dust(70, 4, (220, 220, 220), (1, 2.6), ((-40, -10), (20, 60)), alpha=(60, 160))
        s.t1 = text_img("他不领兵　不冲阵", 58, SERIF_B, IVORY, 0.5)
        s.t2 = text_img("只替郭公看路", 46, SERIF, (215, 205, 185), 0.6)
    def frame(s, t, dur):
        z = 1 + 0.06 * t / dur
        img = s.bg.copy()
        img.alpha_composite(crop_pan(s.cloud, 100 + t * 25))
        img.alpha_composite(crop_pan(s.m1, 120 + t * 10))
        img.alpha_composite(crop_pan(s.mist, 140 + t * 22))
        img.alpha_composite(crop_pan(s.m2, 200 + t * 16))
        d = ImageDraw.Draw(img)
        # 前景崖
        cliff = [(0, 1000), (0, 830), (300, 800), (640, 760), (900, 742), (1040, 752), (1180, 800), (1500, 860), (1920, 900), (1920, 1080), (0, 1080)]
        d.polygon(cliff, fill=(10, 10, 11, 255))
        horse_rider(d, 940, 750, 2.2, (10, 10, 11, 255), 0)
        # 披风随风
        sway = math.sin(t * 3) * 6
        d.polygon([(925, 640), (900 - 30 - sway, 680), (880 - 50 - sway * 1.5, 700), (918, 668)], fill=(10, 10, 11, 255))
        s.snow.draw(img, t)
        if z > 1.001:
            cw, ch = W / z, H / z
            img = img.crop((int((W - cw) / 2), int((H - ch) * 0.6), int((W + cw) / 2), int((H - ch) * 0.6 + ch))).resize((W, H), Image.BILINEAR)
        draw_text(img, s.t1, 300, fade(t, 0.7, dur - 0.35, 0.7, 0.5))
        draw_text(img, s.t2, 395, fade(t, 1.9, dur - 0.35, 0.7, 0.5))
        return finish(img, t, dur)
scene(4.0)(S3)

# 4 长安夜 大秦寺 门口灯
class S4:
    def __init__(s):
        s.bg = vgrad(H, W, [(0, (8, 10, 18)), (0.6, (26, 30, 44)), (1, (12, 12, 16))])
        s.moon = glow(160, (230, 225, 210), 0.9, 0.9)
        s.moong = glow(400, (120, 130, 160), 2, 0.4)
        s.stars = Dust(160, 5, (220, 220, 235), (0.6, 1.4), ((0, 0), (0, 0)), region=(0, W, BAR, 520), alpha=(40, 160))
        s.city = Image.new("RGBA", (2400, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(s.city)
        c = (14, 14, 20, 255)
        # 远处坊墙与城楼
        d.rectangle((0, 720, 2400, 1080), fill=(22, 22, 30, 255))
        for x in range(0, 2400, 22):
            d.rectangle((x, 708, x + 12, 720), fill=(22, 22, 30, 255))
        def tower(cx, base, wd, fillc):
            d.rectangle((cx - wd * 0.45, base - wd * 0.55, cx + wd * 0.45, base), fill=fillc)
            for lvl, (yy, ww) in enumerate([(base - wd * 0.55, wd * 0.75), (base - wd * 0.95, wd * 0.55)]):
                d.rectangle((cx - ww * 0.42, yy - wd * 0.22, cx + ww * 0.42, yy), fill=fillc)
                roof = [(cx - ww * 0.75, yy - wd * 0.18), (cx - ww * 0.55, yy - wd * 0.24), (cx - ww * 0.3, yy - wd * 0.36), (cx + ww * 0.3, yy - wd * 0.36), (cx + ww * 0.55, yy - wd * 0.24), (cx + ww * 0.75, yy - wd * 0.18), (cx + ww * 0.45, yy - wd * 0.26), (cx - ww * 0.45, yy - wd * 0.26)]
                d.polygon(roof, fill=fillc)
                d.polygon([(cx - ww * 0.62, yy - wd * 0.2), (cx + ww * 0.62, yy - wd * 0.2), (cx + ww * 0.3, yy - wd * 0.36), (cx - ww * 0.3, yy - wd * 0.36)], fill=fillc)
        tower(700, 720, 300, (22, 22, 30, 255))
        tower(1900, 720, 220, (22, 22, 30, 255))
        # 近处寺门
        d.rectangle((0, 820, 2400, 1080), fill=c)
        tower(1260, 900, 360, c)
        d.rectangle((1200, 820, 1320, 900), fill=(6, 5, 6, 255))
        # 槐树
        rng = np.random.default_rng(7)
        def branch(x, y, ang, ln, wdt, depth):
            x2, y2 = x + math.cos(ang) * ln, y - math.sin(ang) * ln
            d.line((x, y, x2, y2), fill=c, width=max(1, int(wdt)))
            if depth == 0:
                for _ in range(3):
                    r = rng.uniform(14, 30)
                    ox, oy = rng.normal(0, 14, 2)
                    d.ellipse((x2 + ox - r, y2 + oy - r * 0.7, x2 + ox + r, y2 + oy + r * 0.7), fill=c)
                return
            for da in (-0.45, 0.35):
                branch(x2, y2, ang + da + rng.normal(0, 0.12), ln * rng.uniform(0.66, 0.8), wdt * 0.68, depth - 1)
        branch(1560, 900, math.pi / 2 + 0.1, 150, 24, 6)
        s.lamp = glow(220, (240, 160, 70), 2.0, 0.8)
        s.lamps = [(380, 700), (520, 702), (1010, 700), (1700, 702), (2050, 698)]
        s.small = glow(26, (255, 170, 80), 1.5, 0.9)
        s.t1 = text_img("长安　义宁坊　大秦寺", 56, SERIF_B, IVORY, 0.45)
        s.t2 = text_img("门口　有一盏灯", 46, SERIF, (220, 205, 175), 0.6)
    def frame(s, t, dur):
        img = s.bg.copy()
        s.stars.draw(img, t, 1, flicker=True)
        paste_alpha(img, s.moong, (420 - 400, 320 - 400), 1)
        paste_alpha(img, s.moon, (420 - 160, 320 - 160), 1)
        off = 240 - t * 22
        img.alpha_composite(crop_pan(s.city, off))
        for (x, y) in s.lamps:
            paste_alpha(img, s.small, (x - off - 26, y - 26), 0.7 + 0.3 * math.sin(t * 9 + x))
        lx, ly = 1180 - off, 860
        fl = 0.88 + 0.12 * math.sin(t * 12) * math.sin(t * 5.1)
        paste_alpha(img, s.lamp, (lx - 220, ly - 220), fl)
        d = ImageDraw.Draw(img)
        d.rectangle((lx - 12, ly - 16, lx + 12, ly + 16), fill=(255, 205, 130, 255))
        d.rectangle((lx - 3, ly + 16, lx + 3, ly + 40), fill=(14, 14, 20, 255))
        draw_text(img, s.t1, 290, fade(t, 0.6, dur - 0.35, 0.7, 0.5))
        draw_text(img, s.t2, 385, fade(t, 1.8, dur - 0.35, 0.7, 0.5))
        return finish(img, t, dur)
scene(4.0)(S4)

# 5 立碑：碑文逐行显现
STELE_TEXT = ["粤若常然真寂", "先先而无元", "窅然灵虚", "后后而妙有", "总玄枢而造化", "妙众圣以元尊"]
class S5:
    def __init__(s):
        s.bg = vgrad(H, W, [(0, (14, 12, 10)), (1, (34, 28, 22))])
        rng = np.random.default_rng(9)
        sw, sh = 560, 900
        st = np.zeros((sh, sw, 4), np.uint8)
        base = 92 + rng.normal(0, 7, (sh, sw))
        base = np.clip(base, 0, 255)
        st[..., 0] = base * 0.95
        st[..., 1] = base * 0.9
        st[..., 2] = base * 0.82
        st[..., 3] = 255
        stone = Image.fromarray(st.astype(np.uint8), "RGBA").filter(ImageFilter.GaussianBlur(0.8))
        mask = Image.new("L", (sw, sh), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((0, 120, sw, sh), 10, fill=255)
        md.ellipse((-10, 0, sw + 10, 300), fill=255)
        stone.putalpha(mask)
        d = ImageDraw.Draw(stone)
        # 碑额
        d.rectangle((sw / 2 - 100, 70, sw / 2 + 100, 280), outline=(50, 44, 38, 255), width=4)
        f = font(SERIF_B, 50)
        title = ["大秦景", "教流行", "中国碑"]
        for ci, col in enumerate(title):
            for ri, ch in enumerate(col):
                d.text((sw / 2 + 33 - ci * 58, 90 + ri * 60), ch, font=f, fill=(40, 34, 30, 255))
        # 小十字
        cx = sw / 2
        d.line((cx - 16, 40, cx + 16, 40), fill=(48, 42, 36, 255), width=6)
        d.line((cx, 24, cx, 56), fill=(48, 42, 36, 255), width=6)
        s.stone = stone
        s.sw, s.sh = sw, sh
        s.base = Image.new("RGBA", (760, 160), (0, 0, 0, 0))
        bd = ImageDraw.Draw(s.base)
        bd.ellipse((0, 20, 760, 160), fill=(44, 38, 32, 255))
        bd.ellipse((560, 0, 720, 110), fill=(44, 38, 32, 255))
        s.ray = glow(700, (230, 190, 120), 2.4, 0.5)
        s.dust = Dust(120, 6, (230, 200, 150), (0.8, 2), ((-5, 5), (-10, -2)), alpha=(30, 110))
        s.cf = font(SERIF, 38)
        s.t1 = text_img("建中二年　立碑长安", 56, SERIF_B, IVORY, 0.45)
        s.t2 = text_img("真常之道　妙而难名　强称景教", 40, SERIF, (220, 205, 175), 0.4)
    def frame(s, t, dur):
        img = s.bg.copy()
        paste_alpha(img, s.ray, (600 - 700, 140 - 400), 0.7 + 0.2 * ease(t / dur))
        rise = (1 - ease(t / 2.0)) * 40
        x0, y0 = 600 - s.sw / 2, 150 + rise
        st = s.stone.copy()
        d = ImageDraw.Draw(st)
        # 碑文逐字显现（竖排，从右往左）
        n_total = sum(len(c) for c in STELE_TEXT)
        shown = int(n_total * ease((t - 0.6) / (dur - 1.4)))
        k = 0
        for ci, col in enumerate(STELE_TEXT):
            for ri, ch in enumerate(col):
                if k < shown:
                    age = (shown - k)
                    colr = (34, 28, 24, 255) if age > 3 else (150, 110, 50, 255)
                    d.text((s.sw - 110 - ci * 62, 330 + ri * 48), ch, font=s.cf, fill=colr)
                k += 1
        img.alpha_composite(st, (int(x0), int(y0)))
        img.alpha_composite(s.base, (int(600 - 380), int(y0 + s.sh - 90)))
        s.dust.draw(img, t)
        # 字幕放画面左侧，竖立的碑在中间
        a1 = fade(t, 1.0, dur - 0.3, 0.7, 0.5)
        a2 = fade(t, 2.0, dur - 0.3, 0.7, 0.5)
        draw_text(img, s.t1, 480, a1, cx=1320)
        draw_text(img, s.t2, 570, a2, cx=1320)
        return finish(img, t, dur)
scene(4.2)(S5)

# 6 会昌：火光，碑入土
class S6:
    def __init__(s):
        s.bg = vgrad(H, W, [(0, (16, 6, 4)), (0.55, (110, 30, 12)), (0.8, (200, 80, 24)), (1, (40, 10, 6))])
        s.fire = glow(700, (255, 120, 30), 1.6, 0.7)
        s.emb = Dust(260, 7, (255, 160, 60), (1, 3), ((-30, 30), (-160, -60)), alpha=(100, 255))
        s.ash = Dust(80, 8, (40, 30, 26), (3, 9), ((-20, 20), (-50, -20)), alpha=(60, 140))
        s.t1 = text_img("会昌五年　敕毁诸寺", 62, SERIF_B, IVORY, 0.45)
        s.t2 = text_img("碑　入了土", 50, SERIF, (240, 215, 180), 0.8)
    def frame(s, t, dur):
        img = s.bg.copy()
        shake = (math.sin(t * 40) * 3, math.cos(t * 33) * 2) if t < 1.0 else (0, 0)
        paste_alpha(img, s.fire, (W / 2 - 700, 980 - 700), 0.75 + 0.25 * math.sin(t * 8) * math.sin(t * 3.3))
        d = ImageDraw.Draw(img)
        # 残寺剪影（燃烧的屋顶）
        col = (16, 8, 6, 255)
        for bx, bw, bh in ((180, 420, 260), (1340, 460, 300)):
            d.rectangle((bx, 900 - bh, bx + bw, 900), fill=col)
            d.polygon([(bx - 60, 900 - bh), (bx + bw * 0.5, 900 - bh - 120), (bx + bw + 60, 900 - bh)], fill=col)
            fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            fd = ImageDraw.Draw(fl)
            for k in range(9):
                fx = bx - 30 + k * (bw + 60) / 8
                fh = 90 + 50 * math.sin(t * 9 + k * 2.1) + 40 * math.sin(t * 13.7 + k * 0.7)
                pts = []
                for j in range(15):
                    u = j / 14
                    yy = 900 - bh - 10 - u * fh
                    wd = 34 * (1 - u) ** 0.8
                    pts.append((fx - wd + 10 * math.sin(t * 8 + u * 4 + k) * u, yy))
                for j in range(14, -1, -1):
                    u = j / 14
                    yy = 900 - bh - 10 - u * fh
                    wd = 34 * (1 - u) ** 0.8
                    pts.append((fx + wd + 10 * math.sin(t * 8 + u * 4 + k) * u, yy))
                fd.polygon(pts, fill=(255, 140 + 40 * (k % 2), 40, 230))
            fl = fl.filter(ImageFilter.GaussianBlur(7))
            img.alpha_composite(fl)
            img.alpha_composite(fl)
            d = ImageDraw.Draw(img)
        # 碑，被土慢慢埋
        sx, sw, sh = W / 2 - 150, 300, 520
        top = 940 - sh
        d.rounded_rectangle((sx + shake[0], top + shake[1], sx + sw + shake[0], 940), 40, fill=(30, 20, 16, 255))
        d.line((W / 2 - 14, top + 50, W / 2 + 14, top + 50), fill=(120, 70, 40, 255), width=5)
        d.line((W / 2, top + 36, W / 2, top + 64), fill=(120, 70, 40, 255), width=5)
        bury = ease((t - 1.0) / (dur - 1.4))
        mound_top = 940 - (sh + 60) * bury
        pts = [(0, H)]
        for i in range(41):
            x = i / 40 * W
            u = (x - W / 2) / 700
            y = max(mound_top + (u * u) * 260, 900 - 30 * (1 - u * u)) if abs(u) < 1.2 else 930
            pts.append((x, min(y + math.sin(i * 1.7) * 6, 960)))
        pts.append((W, H))
        d.polygon(pts, fill=(12, 6, 4, 255))
        d.rectangle((0, 930, W, H), fill=(12, 6, 4, 255))
        s.ash.draw(img, t)
        s.emb.draw(img, t, 1, flicker=True)
        draw_text(img, s.t1, 270, fade(t, 0.5, dur - 0.3, 0.5, 0.5))
        draw_text(img, s.t2, 360, fade(t, 1.6, dur - 0.3, 0.6, 0.5))
        return finish(img, t, dur, fin=0.15)
scene(3.8)(S6)

# 7 西出玉门：落日驼队
class S7:
    def __init__(s):
        s.bg = vgrad(H, W, [(0, (30, 18, 14)), (0.45, (150, 80, 40)), (0.66, (235, 150, 70)), (0.72, (120, 66, 36)), (1, (30, 18, 12))])
        s.sun = glow(260, (255, 225, 160), 0.7, 1.0)
        s.sung = glow(700, (255, 160, 70), 2, 0.6)
        s.d1, _ = ridge_layer(2600, H, 760, 90, 31, (110, 60, 32), 300, smooth=True, alpha=0.7)
        s.d2, s.p2 = ridge_layer(3000, H, 850, 60, 32, (22, 12, 8), 500, smooth=True)
        s.sand = Dust(140, 10, (240, 180, 110), (0.8, 2), ((-120, -60), (-6, 6)), alpha=(30, 110))
        s.t1 = text_img("西出玉门", 70, SERIF_B, IVORY, 0.8)
        s.t2 = text_img("灯　还在路上", 48, SERIF, (240, 220, 190), 0.7)
    def frame(s, t, dur):
        img = s.bg.copy()
        paste_alpha(img, s.sung, (W / 2 - 700, 700 - 700), 1)
        paste_alpha(img, s.sun, (W / 2 - 260, 700 - 260 + t * 6), 1)
        img.alpha_composite(crop_pan(s.d1, 200 + t * 15))
        off = 400 + t * 30
        img.alpha_composite(crop_pan(s.d2, off))
        d = ImageDraw.Draw(img)
        for i in range(7):
            gx = 1500 + i * 120 - t * 10
            sx = gx - off + 600
            y = s.p2[int(min(max(gx + 600, 0), 2999))] + 8
            camel(d, sx, y, 1.15, (18, 10, 6, 255), t * 5 + i * 0.9, rider=(i % 2 == 0))
        s.sand.draw(img, t)
        draw_text(img, s.t1, 300, fade(t, 0.5, dur - 0.3, 0.7, 0.5))
        draw_text(img, s.t2, 400, fade(t, 1.5, dur - 0.3, 0.7, 0.5))
        return finish(img, t, dur)
scene(3.4)(S7)

# 8 片名
class S8:
    def __init__(s):
        s.bg = vgrad(H, W, [(0, (8, 7, 6)), (0.5, (20, 17, 13)), (1, (8, 7, 6))])
        s.halo = glow(330, (200, 160, 100), 1.6, 0.45)
        s.cross = lotus_cross(300)
        s.title = text_img("景", 300, BRUSH, (238, 230, 210), 0, shadow=True)
        s.by = text_img("老铁　CLAUDE　著", 38, SERIF, (200, 186, 160), 0.5)
        s.sub = text_img("三部　十三卷　长篇历史小说", 32, SERIF, (170, 156, 130), 0.45)
        s.url = text_img("ny83427.github.io/jing", 26, SERIF, (140, 128, 108), 0.12, shadow=False)
        s.dust = Dust(90, 11, (230, 200, 150), (0.8, 2), ((-4, 4), (-8, -2)), alpha=(20, 90))
    def frame(s, t, dur):
        img = s.bg.copy()
        a = ease(t / 1.2)
        paste_alpha(img, s.halo, (620 - 330, 520 - 330), a)
        paste_alpha(img, s.cross, (620 - 150, 520 - 150 + (1 - a) * 30), a)
        at = ease((t - 0.9) / 1.0)
        paste_alpha(img, s.title, (1180 - s.title.width / 2, 520 - s.title.height / 2 - 20 + (1 - at) * 20), at)
        draw_text(img, s.by, 760, fade(t, 1.8, 99, 0.8, 0.1), cx=1180)
        draw_text(img, s.sub, 812, fade(t, 2.4, 99, 0.8, 0.1), cx=1180)
        draw_text(img, s.url, 905, fade(t, 3.0, 99, 0.8, 0.1))
        s.dust.draw(img, t, a)
        return finish(img, t, dur, fin=0.01, fout=0.9, g=6)
scene(5.0)(S8)

# ---------- 渲染 ----------
def render_scene(i):
    global VIG
    VIG = vignette_layer()
    cls, dur = SCENES[i]
    sc = cls()
    n = int(round(dur * FPS))
    tmp = os.path.join(HERE, f"out/s{i}.tmp.mp4")
    final = os.path.join(HERE, f"out/s{i}.mp4")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS), tmp], stdin=subprocess.PIPE)
    for f in range(n):
        im = sc.frame(f / FPS, dur)
        p.stdin.write(im.convert("RGB").tobytes())
    p.stdin.close()
    if p.wait() == 0:
        os.replace(tmp, final)
    print("scene", i, "done", n, "frames", flush=True)

def still(i, t):
    global VIG
    VIG = vignette_layer()
    cls, dur = SCENES[i]
    im = cls().frame(t, dur)
    im.convert("RGB").save(os.path.join(HERE, f"out/still_{i}_{t}.jpg"), quality=90)

if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    a = sys.argv[1:]
    if a and a[0] == "still":
        for spec in a[1:]:
            i, t = spec.split("@")
            still(int(i), float(t))
    else:
        idx = [int(x) for x in a] if a else list(range(len(SCENES)))
        for i in idx:
            render_scene(i)
    print("durations", [d for _, d in SCENES], sum(d for _, d in SCENES))
