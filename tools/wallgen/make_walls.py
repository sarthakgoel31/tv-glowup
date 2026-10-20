#!/usr/bin/env python3
"""Procedural festival wallpapers for the TV Glowup "india" theme.

Run:  python3 tools/wallgen/make_walls.py [id ...]   (pip install -r tools/requirements.txt)
Out:  themes/india/festivals/<id>.jpg  (1920x1080, q~85, <250 KB)
      tools/wallgen/contact.jpg (labelled grid) and contact_mock.jpg (same, with a UI mock overlay)

Layout contract (every image):
  clock zone     x 0-900,    y 0-260   dark + calm
  pill zone      x 1150-1920 y 60-200  calm
  tile zone      y > 480               dark (luma mostly < 15 %)
  decoration     top edge y 0-120, middle band y 260-480, faint corners
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

W, H = 1920, 1080
SS = 2  # supersampling for vector drawing
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "themes", "india", "festivals")
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
TAU = 2 * math.pi


# ----------------------------------------------------------------------------- basics
def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def c255(h, k=1.0, a=255):
    v = hexc(h) * k
    return tuple(int(max(0, min(255, round(x * 255)))) for x in v) + (a,)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def vgrad(stops):
    """stops: [(y_px, '#hex'), ...] -> HxWx3"""
    ys = np.array([s[0] for s in stops], np.float32)
    cols = np.array([hexc(s[1]) for s in stops])
    t = np.arange(H, dtype=np.float32)
    col = np.stack([np.interp(t, ys, cols[:, c]) for c in range(3)], -1)
    return np.repeat(col[:, None, :], W, axis=1).astype(np.float32)


def gauss(cx, cy, sx, sy=None, ang=0.0):
    sy = sy or sx
    dx, dy = XX - cx, YY - cy
    if ang:
        c, s = math.cos(ang), math.sin(ang)
        dx, dy = c * dx + s * dy, -s * dx + c * dy
    return np.exp(-0.5 * ((dx / sx) ** 2 + (dy / sy) ** 2)).astype(np.float32)


_DIVS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 24, 30, 40]


def blur(a, s):
    """Gaussian blur of HxW or HxWx3 float array; large sigmas via downsample."""
    if s <= 0:
        return a
    f = max(d for d in _DIVS if d <= max(1, s / 3.0))
    if f == 1:
        return gaussian_filter(a, (s, s, 0) if a.ndim == 3 else s)
    chans = [a] if a.ndim == 2 else [a[..., i] for i in range(a.shape[2])]
    out = []
    for ch in chans:
        sm = ch.reshape(H // f, f, W // f, f).mean(axis=(1, 3))
        sm = gaussian_filter(sm, s / f)
        out.append(np.asarray(Image.fromarray(sm.astype(np.float32), "F").resize((W, H), Image.BICUBIC)))
    return out[0] if a.ndim == 2 else np.stack(out, -1)


def fbm(rng, base=8, octaves=5, persist=0.55):
    """Smooth fractal value noise in [0,1], HxW."""
    acc = np.zeros((H, W), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        gw, gh = int(base * 2 ** o) + 2, int(base * 2 ** o * H / W) + 2
        g = rng.random((gh, gw)).astype(np.float32)
        up = np.asarray(Image.fromarray(g, "F").resize((W, H), Image.BICUBIC))
        acc += amp * up
        tot += amp
        amp *= persist
    acc /= tot
    acc = (acc - acc.min()) / (acc.max() - acc.min() + 1e-6)
    return acc


# ----------------------------------------------------------------------------- splats (numpy, additive)
def splat_disc(acc, cx, cy, r, col, a, edge=1.2, ring=0.0):
    x0, x1 = int(max(0, cx - r - 3)), int(min(W, cx + r + 4))
    y0, y1 = int(max(0, cy - r - 3)), int(min(H, cy + r + 4))
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    d = np.hypot(xx - cx, yy - cy)
    m = np.clip((r - d) / edge + 0.5, 0, 1)
    if ring:
        m = m * (1 - ring + ring * smoothstep(r * 0.55, r, d) * 1.6)
    acc[y0:y1, x0:x1] += m[..., None] * (np.asarray(col, np.float32) * a)


def splat_gauss(acc, cx, cy, s, col, a):
    r = 3 * s
    x0, x1 = int(max(0, cx - r)), int(min(W, cx + r + 1))
    y0, y1 = int(max(0, cy - r)), int(min(H, cy + r + 1))
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    m = np.exp(-0.5 * ((xx - cx) ** 2 + (yy - cy) ** 2) / (s * s))
    acc[y0:y1, x0:x1] += m[..., None] * (np.asarray(col, np.float32) * a)


# ----------------------------------------------------------------------------- supersampled vector layer
class Layer:
    def __init__(self, mode="RGB"):
        self.mode = mode
        bg = (0, 0, 0, 0) if mode == "RGBA" else 0
        self.im = Image.new(mode, (W * SS, H * SS), bg)
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def P(pts):
        return [(x * SS, y * SS) for x, y in pts]

    def line(self, pts, fill, width=1.0):
        self.d.line(self.P(pts), fill=fill, width=max(1, int(round(width * SS))), joint="curve")

    def ellipse(self, cx, cy, rx, ry, fill=None, outline=None, width=1.0):
        self.d.ellipse([(cx - rx) * SS, (cy - ry) * SS, (cx + rx) * SS, (cy + ry) * SS],
                       fill=fill, outline=outline, width=max(1, int(round(width * SS))))

    def poly(self, pts, fill=None, outline=None):
        self.d.polygon(self.P(pts), fill=fill, outline=outline)

    def arr(self):
        if self.mode == "RGBA":
            im = self.im.convert("RGBa").resize((W, H), Image.LANCZOS)
            return np.asarray(im, np.float32) / 255.0  # premultiplied
        im = self.im.resize((W, H), Image.LANCZOS)
        a = np.asarray(im, np.float32) / 255.0
        return a


def over(base, rgba_pm, k=1.0):
    a = rgba_pm[..., 3:4] * k
    return base * (1 - a) + rgba_pm[..., :3] * k


def screen(base, light):
    return 1 - (1 - base) * (1 - np.clip(light, 0, 1))


# ----------------------------------------------------------------------------- layout mask
def deco_mask(tl=0.22, pill=0.45, low=0.10):
    """Where decoration may live (1) vs must stay calm (small).
    Elliptical, edge-free falloffs so broad glows never show a rectangular seam."""
    clock = np.exp(-0.5 * (((XX - 360) / 470) ** 2 + ((YY - 165) / 95) ** 4))
    clock *= smoothstep(30, 90, YY)              # leave the very top edge free for garlands
    pills = np.exp(-0.5 * (((XX - 1560) / 400) ** 4 + ((YY - 130) / 60) ** 4))
    m = (1 - clock * (1 - tl)) * (1 - pills * (1 - pill))
    m = m * (low + (1 - low) * (1 - smoothstep(440, 560, YY)))
    return m.astype(np.float32)


def finish(img, rng, bottom=(0.78, 0.55)):
    """Global bottom darkening, vignette, dither, clamp -> uint8."""
    k = 1 - (1 - bottom[0]) * smoothstep(470, 620, YY) - (bottom[0] - bottom[1]) * smoothstep(620, 1080, YY)
    vig = 1 - 0.28 * smoothstep(0.55, 1.25, np.hypot((XX - W / 2) / (W / 2), (YY - H * 0.45) / (H * 0.62)))
    img = img * (k * vig)[..., None]
    img = np.clip(img, 0, 1)
    img = img + rng.normal(0, 0.55 / 255, img.shape).astype(np.float32)
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


# ----------------------------------------------------------------------------- motifs
def marigold(L, x, y, r, base, rng, light=0.82):
    def sh(k):
        return c255(base, k * light)
    L.ellipse(x, y, r, r, fill=sh(0.42))
    rings = [(0.60, 0.44, 0.62, 12), (0.34, 0.38, 0.82, 8), (0.08, 0.30, 1.0, 4)]
    for rr, pr, k, m in rings:
        off = rng.uniform(0, TAU)
        for i in range(m):
            a = off + TAU * i / m + rng.normal(0, 0.12)
            L.ellipse(x + r * rr * math.cos(a), y + r * rr * math.sin(a), r * pr, r * pr,
                      fill=sh(k * rng.uniform(0.86, 1.08)))
    L.ellipse(x - r * 0.18, y - r * 0.22, r * 0.22, r * 0.18, fill=sh(1.18))


def leaf(L, x, y, length, width, ang, col, rib):
    pts = []
    N = 22
    for i in range(N + 1):
        t = i / N
        pts.append((t * length, width * math.sin(math.pi * t) ** 0.85 * (1 - 0.3 * t)))
    for i in range(N, -1, -1):
        t = i / N
        pts.append((t * length, -width * math.sin(math.pi * t) ** 0.85 * (1 - 0.3 * t)))
    c, s = math.cos(ang), math.sin(ang)
    P = [(x + px * c - py * s, y + px * s + py * c) for px, py in pts]
    L.poly(P, fill=col)
    L.line([(x, y), (x + length * 0.92 * c, y + length * 0.92 * s)], fill=rib, width=0.9)


def catenary(x0, x1, y, dip, n):
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((x0 + (x1 - x0) * t, y + dip * 4 * t * (1 - t)))
    return pts


def resample(pts, step):
    """Points every `step` px along a polyline."""
    out = [pts[0]]
    carry = 0.0
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        seg = math.hypot(bx - ax, by - ay)
        d = step - carry
        while d <= seg:
            t = d / seg
            out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
            d += step
        carry = seg - (d - step)
    return out


def toran(rng, y0=13, light=0.8, palette=("#e8731a", "#f2a81d"), right_strands=True):
    """Marigold + mango-leaf toran along the top edge. Returns premultiplied RGBA."""
    L = Layer("RGBA")
    greens = ["#24481a", "#2d5a1f", "#1f3e17"]
    # mango leaves hanging from the cord
    x = -10
    i = 0
    while x < W + 20:
        left = x < 900
        ln = rng.uniform(34, 42) if left else rng.uniform(52, 64)
        ang = math.pi / 2 + rng.normal(0, 0.18)
        leaf(L, x, y0 + 4, ln, ln * 0.2, ang, c255(greens[i % 3], light), c255("#5f8a3a", light * 0.9))
        x += rng.uniform(40, 50)
        i += 1
    L.line([(-10, y0), (W + 10, y0)], fill=c255("#3a2412", light), width=2)
    # swags
    hangs = [0, 300, 600, 900, 1180, 1460, 1720, 1920]
    for a, b in zip(hangs, hangs[1:]):
        dip = 26 if b <= 900 else 44
        pts = resample(catenary(a, b, y0 + 6, dip, 80), 15.5)
        for j, (px, py) in enumerate(pts):
            col = palette[(j // 3) % 2]
            marigold(L, px, py + rng.normal(0, 0.6), 8.2, col, rng, light * 0.92)
    # short strands at right-side hang points
    if right_strands:
        for hx in hangs[3:-1]:
            yy = y0 + 18
            for k in range(2):
                marigold(L, hx + rng.normal(0, 1), yy, 9.5, palette[k % 2], rng, light)
                yy += 17
            leaf(L, hx, yy - 6, 26, 6, math.pi / 2, c255("#2d5a1f", light), c255("#5f8a3a", light))
    # main flower band along the cord
    xs = np.arange(-6, W + 12, 16.5)
    for j, px in enumerate(xs):
        col = palette[(j // 4) % 2]
        marigold(L, px, y0 + rng.normal(0, 1.2), 11.5, col, rng, light)
    return L.arr()


def apply_toran(img, rng, tint="#ff9a3c", **kw):
    t = toran(rng, **kw)
    glow = blur(t[..., 3], 28)[..., None] * hexc(tint) * 0.10
    img = img + glow
    # soft drop shadow so it sits on the sky
    sh = blur(t[..., 3], 6)[..., None]
    img = img * (1 - 0.35 * np.roll(sh, 5, axis=0))
    return over(img, t)


def bokeh(acc, rng, n, ybounds, xbounds, rmin, rmax, cols, amin, amax, ring=0.35):
    for _ in range(n):
        r = rng.uniform(rmin, rmax) ** 1.0
        cx = rng.uniform(*xbounds)
        cy = rng.uniform(*ybounds)
        col = hexc(cols[rng.integers(len(cols))])
        splat_disc(acc, cx, cy, r, col, rng.uniform(amin, amax), edge=max(1.2, r * 0.12), ring=ring)


def burst(L, cx, cy, R, n, rng, width=1.2, droop=0.12, segs=10, val=255):
    """Firework rays drawn on an L-mode layer (fading toward the tips)."""
    for i in range(n):
        a = TAU * i / n + rng.normal(0, 0.03)
        rl = R * rng.uniform(0.7, 1.0)
        r0 = R * 0.12
        prev = None
        for s in range(segs + 1):
            t = s / segs
            r = r0 + (rl - r0) * t
            px = cx + r * math.cos(a)
            py = cy + r * math.sin(a) + droop * R * t * t
            if prev:
                v = int(val * (0.25 + 0.75 * math.sin(math.pi * min(1, t * 1.15)) ** 0.7) * (1 - 0.55 * t))
                L.line([prev, (px, py)], fill=v, width=width * (1 - 0.4 * t))
            prev = (px, py)
        L.ellipse(prev[0], prev[1], 1.6, 1.6, fill=int(val * 0.75))


# ----------------------------------------------------------------------------- scenes
def scene_diwali(rng):
    img = vgrad([(0, "#1d0710"), (300, "#1a0818"), (560, "#0b0a1d"), (1080, "#04050c")])
    img += gauss(1350, 420, 520, 170)[..., None] * hexc("#5a2a0c") * 0.55   # warm haze behind lamps
    img += gauss(300, 360, 500, 160)[..., None] * hexc("#3a0d22") * 0.35
    M = deco_mask()
    light = np.zeros((H, W, 3), np.float32)
    bokeh(light, rng, 55, (150, 470), (0, W), 3, 16, ["#ffb347", "#ffd27a", "#ff8c3a"], 0.05, 0.15, ring=0.15)
    img += blur(light, 1.4) * M[..., None]
    big = np.zeros((H, W, 3), np.float32)
    bokeh(big, rng, 22, (200, 470), (700, W), 16, 40, ["#ffb347", "#ffcf70", "#ff9a50"], 0.035, 0.07, ring=0.2)
    img += blur(big, 4.5) * M[..., None]
    # faint rangoli bottom-right
    R = Layer("L")
    cx, cy = 1830, 1050
    for k, rad in enumerate([90, 150, 215, 290, 370]):
        R.ellipse(cx, cy, rad, rad, outline=255, width=1.1)
        n = 8 + 4 * k
        for i in range(n):
            a = TAU * i / n
            pr = rad + 30
            p = [(cx + (rad + 4) * math.cos(a - 0.5 * TAU / n), cy + (rad + 4) * math.sin(a - 0.5 * TAU / n)),
                 (cx + pr * math.cos(a), cy + pr * math.sin(a)),
                 (cx + (rad + 4) * math.cos(a + 0.5 * TAU / n), cy + (rad + 4) * math.sin(a + 0.5 * TAU / n))]
            R.line(p, fill=255, width=1.0)
            R.ellipse(cx + (pr + 9) * math.cos(a), cy + (pr + 9) * math.sin(a), 2.2, 2.2, fill=255)
    img += R.arr()[..., None] * hexc("#d6a34a") * 0.075
    # diyas
    diyas = []
    for i in range(7):
        t = i / 6
        x = 1030 + t * 690 + rng.normal(0, 6)
        s = 0.88 + 0.22 * math.sin(math.pi * t) + rng.normal(0, 0.03)
        y = 458 + 6 * math.sin(math.pi * t)
        diyas.append((x, y, s))
    flame_o, flame_c = Layer("L"), Layer("L")
    bowls = Layer("RGBA")
    for x, y, s in diyas:
        bw, bd = 40 * s, 19 * s
        # body (lower half ellipse) + rim
        body = [(x + bw * math.cos(a), y + bd * math.sin(a)) for a in np.linspace(0, math.pi, 40)]
        spout = [(x - bw * 1.18, y - 2 * s)]
        body = [(x + bw, y - 1)] + body + spout
        bowls.poly(body, fill=c255("#5c2412"))
        bowls.ellipse(x - 2 * s, y, bw * 1.02, 7.5 * s, fill=c255("#8a3c18"))
        bowls.ellipse(x - 2 * s, y + 0.5, bw * 0.86, 5.2 * s, fill=c255("#2a0f06"))
        bowls.ellipse(x - 2 * s, y + 0.5, bw * 0.70, 3.6 * s, fill=c255("#6b4a12"))
        # little painted dots on the body
        for a in np.linspace(0.45, math.pi - 0.45, 7):
            bowls.ellipse(x + bw * 0.78 * math.cos(a), y + bd * 0.62 * math.sin(a), 1.5 * s, 1.5 * s,
                          fill=c255("#c98a2c", 0.85))
        # flame at the spout
        fx, fy = x - bw * 0.98, y - 4 * s
        fh, fw = 44 * s, 9.5 * s
        def tear(h, w, lean):
            P = []
            for u in np.linspace(0, 1, 30):
                P.append((fx + w * (1 - u) ** 1.25 * math.sqrt(u) * 1.9 + lean * u * u, fy - h * u))
            for u in np.linspace(1, 0, 30):
                P.append((fx - w * (1 - u) ** 1.25 * math.sqrt(u) * 1.9 + lean * u * u, fy - h * u))
            return P
        lean = rng.normal(0, 2.5) * s
        flame_o.poly(tear(fh, fw, lean), fill=255)
        flame_c.poly([(px, py + 3 * s) for px, py in tear(fh * 0.52, fw * 0.5, lean * 0.5)], fill=255)
    fo, fc = flame_o.arr(), flame_c.arr()
    img += blur(fo, 90)[..., None] * hexc("#ff7a1a") * 0.9
    img += blur(fo, 26)[..., None] * hexc("#ff9a30") * 0.8
    img = over(img, bowls.arr())
    img += blur(fo, 1.6)[..., None] * hexc("#ff8a1e") * 1.0
    img += blur(fo, 6)[..., None] * hexc("#ffb040") * 0.45
    img = screen(img, blur(fc, 1.2)[..., None] * hexc("#fff3c8") * 1.1)
    img = apply_toran(img, rng)
    return finish(img, rng)


def scene_dussehra(rng):
    img = vgrad([(0, "#170507"), (250, "#240a0b"), (380, "#33110a"), (520, "#140806"), (760, "#080405"), (1080, "#050304")])
    img += gauss(1250, 360, 950, 110)[..., None] * hexc("#7a3008") * 0.18   # dusk glow
    img += gauss(1350, 350, 420, 70)[..., None] * hexc("#c25a10") * 0.08
    M = deco_mask()
    L1 = Layer("L")
    for cx, cy, R in [(1200, 320, 95), (1520, 290, 70), (980, 370, 50), (1730, 365, 55), (760, 330, 38)]:
        burst(L1, cx, cy, R, 40, rng, width=0.8, droop=0.3, val=255)
    sp = L1.arr()
    img += (sp[..., None] * 0.45 + blur(sp, 4)[..., None] * 0.4 + blur(sp, 25)[..., None] * 0.6) * hexc("#ffc45a") * M[..., None]
    light = np.zeros((H, W, 3), np.float32)
    for _ in range(160):
        cx, cy = rng.uniform(0, W), rng.uniform(160, 470)
        splat_gauss(light, cx, cy, rng.uniform(0.6, 1.4), hexc("#ffcf6a"), rng.uniform(0.08, 0.35))
    bokeh(light, rng, 30, (250, 470), (900, W), 6, 22, ["#ff9a3c", "#ffc35a"], 0.03, 0.08)
    img += blur(light, 1.0) * M[..., None]
    img = apply_toran(img, rng, palette=("#e5641a", "#f0a01c"))
    return finish(img, rng)


def scene_christmas(rng):
    img = vgrad([(0, "#07111f"), (260, "#08182a"), (480, "#06171a"), (700, "#041010"), (1080, "#020606")])
    img += gauss(1250, 360, 650, 170)[..., None] * hexc("#0f4030") * 0.35
    img += gauss(350, 330, 500, 140)[..., None] * hexc("#10234a") * 0.35
    img += gauss(1300, 0, 900, 100)[..., None] * hexc("#5a3a14") * 0.14   # warm wash from the lights
    M = deco_mask()
    # pine branches, top-right corner
    P = Layer("RGBA")
    def branch(x0, y0, ang, length, depth):
        n = int(length / 4)
        pts = []
        for i in range(n + 1):
            t = i / n
            a = ang + 0.22 * t
            pts.append((x0 + length * t * math.cos(a), y0 + length * t * math.sin(a) + 14 * t * t))
        P.line(pts, fill=c255("#2a2416"), width=3.2 if depth == 0 else 1.8)
        for i, (px, py) in enumerate(pts[1:]):
            t = (i + 1) / n
            nl = (28 if depth == 0 else 16) * (1 - 0.55 * t)
            for side in (-1, 1):
                a = ang + side * 1.0 + rng.normal(0, 0.12) + 0.35
                k = rng.uniform(0.8, 1.2)
                col = c255("#1e4a2c" if rng.random() < 0.6 else "#2a5e36", k)
                P.line([(px, py), (px + nl * math.cos(a), py + nl * math.sin(a))], fill=col, width=1.3)
        if depth == 0:
            for t in (0.28, 0.5, 0.72):
                i = int(t * n)
                branch(pts[i][0], pts[i][1], ang + rng.choice([-0.55, 0.5]), length * 0.36, 1)
    branch(1990, -36, math.radians(160), 360, 0)
    branch(1975, 26, math.radians(174), 230, 0)
    branch(-60, -30, math.radians(22), 210, 0)    # tiny one top-left, above the clock
    br = P.arr()
    img = over(img, br, 0.9)
    img += blur(br[..., 3], 3)[..., None] * hexc("#ffcf80") * 0.035   # rim from the bulbs
    # fairy lights: two strands along the top
    wire = Layer("L")
    bulbs = np.zeros((H, W, 3), np.float32)
    cols = ["#ffd69a", "#ffc070", "#fff0d6", "#ffb35a"]
    for ystart, hangs, dip, phase in [(6, [-40, 420, 880, 1340, 1800, 2060], 62, 0),
                                      (18, [-260, 180, 650, 1110, 1570, 2100], 46, 1)]:
        for a, b in zip(hangs, hangs[1:]):
            d = dip if a > 850 else dip * 0.5
            cat = catenary(a, b, ystart, d, 140)
            wire.line(cat, fill=255, width=1.0)
            for j, (px, py) in enumerate(resample(cat, 30)):
                if -5 <= px < W + 5:
                    col = hexc(cols[(j + phase) % len(cols)])
                    k = rng.uniform(0.6, 1.0)
                    splat_disc(bulbs, px, py + 3.5, 3.0, col, k, edge=1.0)
    wa = wire.arr()[..., None]
    img = img * (1 - wa * 0.5) + wa * hexc("#3a3428") * 0.5
    img += blur(bulbs, 4) * 1.6 + blur(bulbs, 14) * 2.6 + blur(bulbs, 45) * 2.4
    img = screen(img, bulbs * 1.1)
    # snow: sharp near flakes + soft out-of-focus flakes
    snow = np.zeros((H, W, 3), np.float32)
    for _ in range(260):
        cy, cx = rng.uniform(0, H), rng.uniform(0, W)
        r = rng.uniform(0.8, 2.4)
        a = rng.uniform(0.15, 0.45) * (1 - 0.8 * smoothstep(380, 640, cy))
        splat_disc(snow, cx, cy, r, hexc("#e8f0ff"), a, edge=1.4)
    soft = np.zeros((H, W, 3), np.float32)
    for _ in range(28):
        splat_disc(soft, rng.uniform(0, W), rng.uniform(140, 470), rng.uniform(5, 13), hexc("#dfe8ff"), rng.uniform(0.04, 0.08), edge=3)
    img += (blur(snow, 0.8) + blur(soft, 3)) * (0.5 + 0.5 * M)[..., None]
    warm = np.zeros((H, W, 3), np.float32)
    bokeh(warm, rng, 26, (260, 470), (950, W), 8, 30, ["#ffc070", "#ffd69a", "#e85a4a", "#5ad08a"], 0.025, 0.06, ring=0.2)
    img += blur(warm, 3.5) * M[..., None]
    return finish(img, rng)


def scene_newyear(rng):
    img = vgrad([(0, "#03040c"), (380, "#070b1f"), (620, "#04060f"), (1080, "#020306")])
    img += gauss(1250, 360, 650, 150)[..., None] * hexc("#14183a") * 0.5
    M = deco_mask()
    specs = [(1180, 340, 150, "#ffcc66", 48), (1540, 285, 110, "#f3e2b8", 40), (860, 395, 85, "#e8c27a", 34),
             (1790, 400, 75, "#ffd890", 30), (620, 330, 55, "#f3e2b8", 26), (1360, 440, 45, "#ffcc66", 24)]
    for cx, cy, R, col, n in specs:
        L = Layer("L")
        burst(L, cx, cy, R, n, rng, width=1.1, droop=0.14)
        a = L.arr()
        c = hexc(col)
        img += (a[..., None] * 0.75 + blur(a, 4)[..., None] * 0.6 + blur(a, 30)[..., None] * 0.9) * c * M[..., None]
        img += gauss(cx, cy, R * 0.6)[..., None] * c * 0.06
        img += gauss(cx, cy, R * 0.12)[..., None] * c * 0.22
    light = np.zeros((H, W, 3), np.float32)
    # confetti sparkle near top
    for _ in range(220):
        cy = abs(rng.normal(0, 55))
        cx = rng.uniform(0, W)
        if cy > 140:
            continue
        col = hexc(["#ffd27a", "#f3e2b8", "#ffffff", "#e8b860"][rng.integers(4)])
        splat_disc(light, cx, cy, rng.uniform(0.7, 1.8), col, rng.uniform(0.25, 0.75) * (1 - cy / 150), edge=0.9)
    G = Layer("L")
    for _ in range(16):
        cx, cy = rng.uniform(950, W), abs(rng.normal(0, 40))
        s = rng.uniform(5, 11)
        G.line([(cx - s, cy), (cx + s, cy)], fill=200, width=0.7)
        G.line([(cx, cy - s), (cx, cy + s)], fill=200, width=0.7)
    g = G.arr()
    light += (g[..., None] + blur(g, 3)[..., None]) * hexc("#ffe7b0") * 0.6
    for _ in range(90):
        splat_gauss(light, rng.uniform(0, W), rng.uniform(250, 480), rng.uniform(0.6, 1.2), hexc("#ffd890"), rng.uniform(0.1, 0.4))
    tm = np.maximum(M, (YY < 110).astype(np.float32) * 0.8)
    img += (light + blur(light, 6) * 0.8) * tm[..., None]
    return finish(img, rng)


def scene_holi(rng):
    img = vgrad([(0, "#07050c"), (500, "#06050a"), (1080, "#020203")])
    M = deco_mask(tl=0.15, pill=0.4, low=0.04)
    win = smoothstep(20, 180, YY) * (1 - smoothstep(300, 490, YY))
    clouds = [  # cx, cy, sx, sy, color, k
        (1480, 290, 380, 150, "#e0218a", 0.85),
        (1060, 330, 340, 130, "#ff8c1a", 0.80),
        (620, 340, 380, 120, "#1fb36a", 0.65),
        (1820, 140, 300, 130, "#2a6cff", 0.55),
        (1760, 380, 240, 100, "#ffcc33", 0.40),
        (240, 330, 300, 110, "#8a2bff", 0.40),
        (1250, 210, 260, 100, "#ff3a6a", 0.35),
    ]
    light = np.zeros((H, W, 3), np.float32)
    for cx, cy, sx, sy, col, k in clouds:
        nz = fbm(rng, base=4, octaves=6, persist=0.6)
        nz2 = fbm(rng, base=14, octaves=4, persist=0.55)
        g = gauss(cx, cy, sx, sy, ang=rng.normal(0, 0.2))
        d = np.clip(g * (0.15 + 1.3 * nz ** 1.4) * (0.7 + 0.6 * nz2) - 0.08, 0, None) ** 1.1
        light += d[..., None] * hexc(col) * k * 0.8
    light = blur(light, 2.2)
    wr = smoothstep(1350, 1750, XX)
    tw = (smoothstep(0, 120, YY) * wr + smoothstep(20, 180, YY) * (1 - wr)) * (1 - smoothstep(300, 490, YY))
    light *= tw[..., None]
    # fine powder specks where the colour is
    sp = np.zeros((H, W, 3), np.float32)
    for _ in range(700):
        cx, cy = rng.uniform(0, W), rng.uniform(100, 470)
        col = hexc(["#ff4fa8", "#ffb03a", "#3fe08f", "#5a8bff", "#ffe06a"][rng.integers(5)])
        splat_gauss(sp, cx, cy, rng.uniform(0.5, 1.4), col, rng.uniform(0.1, 0.5))
    light += sp * np.clip(light.max(-1, keepdims=True) * 2.2, 0, 1)
    img = screen(img, light * M[..., None])
    return finish(img, rng)


def scene_tricolour(rng):
    img = vgrad([(0, "#03050d"), (380, "#060a1a"), (640, "#03050c"), (1080, "#020306")])
    M = deco_mask()
    x = np.arange(W, dtype=np.float32)
    yc = 365 + 48 * np.sin(x / W * TAU * 0.9 + 0.6) + 18 * np.sin(x / W * TAU * 2.1 + 1.7)
    tw = 0.5 + 0.5 * (0.5 + 0.5 * np.cos(x / W * TAU * 1.15 + 0.4))          # twist -> width
    hw = 58 * tw                                                            # half width
    v = (YY - yc[None, :]) / hw[None, :]                                    # -1..1 across ribbon
    edge = 1 - smoothstep(0.82, 1.08, np.abs(v))
    sweep = 0.55 + 0.45 * smoothstep(0, 1, x / W)[None, :] * (1 - 0.35 * smoothstep(0.8, 1.0, x / W))[None, :]
    sweep = sweep * (0.35 + 0.65 * smoothstep(-80, 400, x)[None, :])
    shade = (0.55 + 0.45 * tw)[None, :]
    sf, wh, gr = hexc("#ff8a1f"), hexc("#e9e6dc"), hexc("#1ea84e")
    wS = 1 - smoothstep(-0.42, -0.24, v)
    wG = smoothstep(0.24, 0.42, v)
    wW = 1 - wS - wG
    col = wS[..., None] * sf + wW[..., None] * wh * 0.82 + wG[..., None] * gr
    a = edge * sweep * shade
    rib = col * (a[..., None] * 0.55)
    # aurora curtains rising above and a soft glow
    streak = fbm(rng, base=40, octaves=3)
    above = np.exp(-np.clip(yc[None, :] - hw[None, :] - YY, 0, None) / 90) * (YY < yc[None, :])
    cur = above * (0.4 + 0.6 * smoothstep(0.35, 0.8, streak)) * sweep * 0.18
    curcol = (wS[..., None] * 0 + 1) * sf * 0.5 + gr * 0.15
    img += cur[..., None] * curcol * M[..., None]
    img += blur(rib, 26) * 0.8 * M[..., None]
    img += blur(rib, 1.2) * M[..., None]
    # thin bright edge lines
    for off, c in [(-1.0, sf), (1.0, gr)]:
        e = np.exp(-0.5 * ((v - off) / 0.05) ** 2) * sweep * shade
        img += e[..., None] * c * 0.35 * M[..., None]
    light = np.zeros((H, W, 3), np.float32)
    for _ in range(80):
        splat_gauss(light, rng.uniform(0, W), rng.uniform(0, 470), rng.uniform(0.5, 1.0), hexc("#dfe6ff"), rng.uniform(0.05, 0.22))
    img += light * M[..., None]
    return finish(img, rng)


def scene_lohri(rng):
    img = vgrad([(0, "#04040a"), (260, "#08060f"), (520, "#0d0608"), (1080, "#120604")])
    fx = 600
    nz = fbm(rng, base=5, octaves=5)
    warp = (nz - 0.5) * 160
    plume = np.exp(-0.5 * ((XX - fx - warp - 0.12 * (1080 - YY)) / (90 + 0.55 * (1080 - YY))) ** 2)
    plume *= np.exp(-(1080 - YY) / 520)
    img += plume[..., None] * hexc("#ff6a1a") * 0.14
    img += gauss(fx, 1110, 230, 90)[..., None] * hexc("#ff7a20") * 0.22
    img += gauss(fx + 200, 380, 700, 170)[..., None] * hexc("#3a1406") * 0.40
    M = deco_mask(low=0.2)
    sparks = Layer("L")
    for _ in range(420):
        h = rng.uniform(0.02, 1.0) ** 0.8
        y = 1070 - h * 860
        x = fx + rng.normal(0, 30 + 380 * h) + 160 * h
        Ls = rng.uniform(5, 16) * (1.2 - 0.5 * h)
        ang = -math.pi / 2 + rng.normal(0, 0.35) + 0.0007 * (x - fx)
        v = int(255 * rng.uniform(0.3, 1.0) * (0.55 + 0.45 * h))
        cx2 = x - Ls * math.cos(ang) + rng.normal(0, 2)
        sparks.line([(x, y), ((x + cx2) / 2 + rng.normal(0, 1.5), (y + y - Ls * math.sin(ang)) / 2), (cx2, y - Ls * math.sin(ang))],
                    fill=v, width=rng.uniform(1.0, 2.0))
    s = sparks.arr()
    sm = np.maximum(M, 0.25)
    img += (s[..., None] * hexc("#ffc060") * 1.0 + blur(s, 3)[..., None] * hexc("#ff8a2a") * 1.2
            + blur(s, 14)[..., None] * hexc("#ff6a1a") * 0.6) * sm[..., None]
    light = np.zeros((H, W, 3), np.float32)
    bokeh(light, rng, 30, (250, 470), (250, 1500), 5, 22, ["#ff8a30", "#ffb050"], 0.04, 0.10, ring=0.15)
    img += blur(light, 2.5) * M[..., None]
    stars = np.zeros((H, W, 3), np.float32)
    for _ in range(90):
        splat_gauss(stars, rng.uniform(900, W), rng.uniform(0, 300), rng.uniform(0.5, 1.0), hexc("#d8dcff"), rng.uniform(0.06, 0.25))
    img += stars * M[..., None]
    return finish(img, rng, bottom=(0.78, 0.55))


def scene_rakhi(rng):
    img = vgrad([(0, "#1d0a1e"), (360, "#1a0a1f"), (620, "#0d0612"), (1080, "#060309")])
    img += gauss(1300, 380, 600, 150)[..., None] * hexc("#3a1236") * 0.45
    M = deco_mask()
    thread = Layer("L")
    thread2 = Layer("L")
    beads = []
    nloops = 9
    b = 21.0
    for k, (Lr, ph, yb) in enumerate([(thread, 0.0, 34), (thread2, math.pi, 36)]):
        pts = []
        for t in np.linspace(0, TAU * nloops, 3000):
            s = W / (TAU * nloops)
            x = s * t - 2.3 * b * math.sin(t + ph) - 20
            y = yb - b * math.cos(t + ph) * (0.75 if k else 1.0) + 6 * math.sin(t * 0.15)
            pts.append((x, y))
        Lr.line(pts, fill=255, width=1.5 if k == 0 else 1.0)
        if k == 0:
            for i in range(nloops):
                t = TAU * i + math.pi
                s = W / (TAU * nloops)
                beads.append((s * t - 20, yb + b + 6 * math.sin(t * 0.15)))
    th = thread.arr()
    th2 = thread2.arr()
    gold = hexc("#e2b356")
    img += (th[..., None] * gold * 0.95 + blur(th, 5)[..., None] * gold * 0.55 + blur(th, 22)[..., None] * gold * 0.35)
    img += (th2[..., None] * hexc("#c8443c") * 0.75 + blur(th2, 5)[..., None] * hexc("#c8443c") * 0.4)
    bl = np.zeros((H, W, 3), np.float32)
    bcols = ["#e8b850", "#b8202a", "#f3e6d0"]
    for i, (x, y) in enumerate(beads):
        c = hexc(bcols[i % 3])
        r = 6.5 if i % 3 != 2 else 5.0
        splat_disc(img, x, y, r, c * 0.8, 1.0, edge=1.2)
        img[int(y) - 3:int(y) + 3, int(x) - 3:int(x) + 3] *= 0.92
        splat_gauss(img, x - r * 0.3, y - r * 0.35, r * 0.25, hexc("#fff6e0"), 0.8)
        splat_gauss(bl, x, y, r * 2.2, c, 0.6)
        # small drop pendants on every third bead
        if i % 3 == 1:
            thread.d.line([(x * SS, (y + r) * SS), (x * SS, (y + r + 18) * SS)], fill=255, width=2)
            splat_disc(img, x, y + r + 22, 3.5, hexc("#e8b850") * 0.8, 1.0)
            splat_gauss(bl, x, y + r + 22, 8, hexc("#e8b850"), 0.4)
    pend = thread.arr() - th
    img += np.clip(pend, 0, 1)[..., None] * gold * 0.8
    img += blur(bl, 6) * 0.9
    light = np.zeros((H, W, 3), np.float32)
    bokeh(light, rng, 40, (240, 470), (0, W), 4, 22, ["#e8b850", "#ff7aa8", "#f3d9a0"], 0.03, 0.10)
    for _ in range(100):
        splat_gauss(light, rng.uniform(0, W), rng.uniform(80, 470), rng.uniform(0.6, 1.2), hexc("#f3d29a"), rng.uniform(0.08, 0.3))
    img += blur(light, 1.5) * M[..., None]
    return finish(img, rng)


def scene_ganesh(rng):
    img = vgrad([(0, "#170806"), (300, "#1f0b06"), (560, "#0d0605"), (1080, "#050303")])
    img += gauss(1240, 380, 520, 150)[..., None] * hexc("#a0460a") * 0.30
    img += gauss(1240, 380, 220, 90)[..., None] * hexc("#ff8a1a") * 0.12
    M = deco_mask()
    # abstract lotus line-work around (1240, 470)
    Lt = Layer("L")
    cx, cy = 1240, 478
    for layer, (R, n, spread) in enumerate([(200, 9, 0.17), (150, 7, 0.20), (100, 5, 0.24)]):
        for i in range(n):
            a = math.pi + math.pi * (i + 0.5) / n
            pts = []
            for u in np.linspace(-1, 1, 60):
                ang = a + spread * u * math.cos(u * math.pi / 2)
                rr = R * (1 - 0.65 * u * u) ** 0.5 + 6
                pts.append((cx + rr * math.cos(ang), cy + 0.62 * rr * math.sin(ang)))
            Lt.line(pts, fill=255, width=1.1)
    for k, R in enumerate([230, 270, 320]):
        pts = [(cx + R * math.cos(a), cy + 0.62 * R * math.sin(a)) for a in np.linspace(math.pi * 1.03, math.pi * 1.97, 120)]
        Lt.line(pts, fill=150 - 30 * k, width=0.9)
        for a in np.linspace(math.pi * 1.06, math.pi * 1.94, 18 + 6 * k):
            Lt.ellipse(cx + (R + 10) * math.cos(a), cy + 0.62 * (R + 10) * math.sin(a), 1.6, 1.6, fill=170 - 30 * k)
    lt = Lt.arr()
    gold = hexc("#e2a94a")
    img += (lt[..., None] * gold * 0.42 + blur(lt, 6)[..., None] * gold * 0.3) * M[..., None]
    light = np.zeros((H, W, 3), np.float32)
    bokeh(light, rng, 45, (200, 470), (0, W), 4, 22, ["#ffb347", "#ffd27a", "#ff8c3a"], 0.04, 0.12)
    for _ in range(120):
        splat_gauss(light, rng.uniform(800, W), rng.uniform(220, 470), rng.uniform(0.6, 1.2), hexc("#ffd890"), rng.uniform(0.1, 0.35))
    img += blur(light, 1.6) * M[..., None]
    img = apply_toran(img, rng, palette=("#f0a01c", "#e8731a"))
    return finish(img, rng)


def feather_eye(img, cx, cy, a, b, ang, k, rng):
    """Abstract peacock 'eye' rendered analytically in local coords. a=length, b=width."""
    R = int(max(a, b) * 2.4)
    x0, x1, y0, y1 = max(0, int(cx - R)), min(W, int(cx + R)), max(0, int(cy - R)), min(H, int(cy + R))
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dx, dy = xx - cx, yy - cy
    c, s = math.cos(ang), math.sin(ang)
    u, v = c * dx + s * dy, -s * dx + c * dy           # u: along the feather (toward tip = +)
    bb = b * (1 + 0.28 * np.clip(u / a, -1, 1))          # teardrop: wider toward the tip
    d = np.sqrt((u / a) ** 2 + (v / bb) ** 2)
    th = np.arctan2(v, u)
    def band(lo, hi, soft=0.035):
        return smoothstep(lo - soft, lo + soft, d) * (1 - smoothstep(hi - soft, hi + soft, d))
    heart = 1 - smoothstep(0.30, 0.36, np.sqrt(((u - 0.06 * a) / (a * 0.95)) ** 2 + (v / (bb * 0.8)) ** 2))
    layers = [
        (heart, "#0a1a5c", 1.0),
        (band(0.33, 0.47) * (1 - heart), "#1aa2c4", 0.9),
        (band(0.47, 0.58), "#b07a2e", 0.8),
        (band(0.58, 0.74), "#3f8a3a", 0.75),
        (band(0.74, 0.80), "#b8963a", 0.45),
    ]
    acc = np.zeros(dx.shape + (3,), np.float32)
    alpha = np.zeros(dx.shape, np.float32)
    for m, col, kk in layers:
        acc += m[..., None] * hexc(col) * kk
        alpha = np.maximum(alpha, m)
    # loose barbs fanning out beyond the eye
    fil = (0.5 + 0.5 * np.cos(th * 70 + 6 * d)) ** 6
    fan = smoothstep(0.75, 0.85, d) * (1 - smoothstep(1.0, 2.0, d)) * fil * (0.6 + 0.4 * np.cos(th * 0.5))
    acc += fan[..., None] * hexc("#3a9a6a") * 0.55
    alpha = np.maximum(alpha, fan * 0.8)
    # fine filament sheen over the solid eye
    sheen = 0.85 + 0.15 * np.cos(th * 90)
    acc *= sheen[..., None]
    reg = img[y0:y1, x0:x1]
    img[y0:y1, x0:x1] = reg * (1 - alpha[..., None] * k) + acc * k


def scene_janmashtami(rng):
    img = vgrad([(0, "#040824"), (320, "#06103a"), (600, "#040820"), (1080, "#02030c")])
    img += gauss(1200, 380, 700, 150)[..., None] * hexc("#0c2560") * 0.35
    M = deco_mask(pill=0.55)
    # three feathers sweeping in from the top-right corner, eyes in the middle band
    feathers = [((2080, -80), (1720, 110), (1600, 300), 1.0),
                ((2110, 20), (1900, 170), (1810, 350), 0.85),
                ((2040, -170), (1580, 20), (1400, 240), 0.72)]
    F = Layer("L")
    for (sx, sy), (qx, qy), (ex, ey), s in feathers:
        n = 160
        pts = [((1 - t) ** 2 * sx + 2 * (1 - t) * t * qx + t * t * ex, (1 - t) ** 2 * sy + 2 * (1 - t) * t * qy + t * t * ey)
               for t in np.linspace(0, 0.93, n)]
        F.line(pts, fill=255, width=1.1 * s)
        for i in range(4, n):
            (x0, y0), (x1, y1) = pts[i - 1], pts[i]
            a = math.atan2(y1 - y0, x1 - x0)
            t = i / n
            bl = (10 + 70 * t ** 1.4) * s * rng.uniform(0.85, 1.1)
            for side in (-1, 1):
                bang = a + side * (1.15 - 0.55 * t) + rng.normal(0, 0.04)
                mx, my = x1 + 0.5 * bl * math.cos(bang - side * 0.12), y1 + 0.5 * bl * math.sin(bang - side * 0.12)
                F.line([(x1, y1), (mx, my), (x1 + bl * math.cos(bang), y1 + bl * math.sin(bang))],
                       fill=int(185 * (0.25 + 0.75 * t)), width=0.6)
    fl = F.arr()
    tint = hexc("#3f9a6a") * (1 - smoothstep(1200, 1900, XX))[..., None] * 0.4 + hexc("#2f8a7a") * 0.6
    img += fl[..., None] * tint * 0.75 * (0.45 + 0.55 * M)[..., None]
    img += blur(fl, 12)[..., None] * hexc("#1f6a6a") * 0.35
    for (sx, sy), (qx, qy), (ex, ey), s in feathers:
        ang = math.atan2(ey - qy, ex - qx)
        img += gauss(ex, ey, 90 * s)[..., None] * hexc("#1a6a8a") * 0.12
        feather_eye(img, ex, ey, 64 * s, 44 * s, ang, 0.92, rng)
    # flowing flute-like gold line
    Lf = Layer("L")
    for k, (amp, ph, wv, yb) in enumerate([(34, 0.0, 1.0, 425), (28, 0.7, 0.9, 434), (24, 1.6, 1.1, 418)]):
        pts = []
        for x in np.linspace(-20, W + 20, 500):
            env = 0.6 + 0.4 * math.sin(x / W * math.pi)
            y = yb + amp * env * math.sin(x / W * TAU * wv * 1.2 + ph) + 12 * math.sin(x / 160 + k)
            pts.append((x, y))
        Lf.line(pts, fill=[255, 140, 90][k], width=[1.6, 0.9, 0.8][k])
    lf = Lf.arr()
    gold = hexc("#e8c36a")
    fade = 0.3 + 0.7 * smoothstep(0, 1300, XX)
    img += (lf[..., None] * gold * 0.9 + blur(lf, 5)[..., None] * gold * 0.55 + blur(lf, 24)[..., None] * gold * 0.4) * (M * fade)[..., None]
    light = np.zeros((H, W, 3), np.float32)
    for _ in range(160):
        x = rng.uniform(0, W)
        y = 425 + 34 * (0.6 + 0.4 * math.sin(x / W * math.pi)) * math.sin(x / W * TAU * 1.2) + rng.normal(0, 24)
        splat_gauss(light, x, y, rng.uniform(0.6, 1.4), gold, rng.uniform(0.1, 0.5) * (0.3 + 0.7 * x / W))
    for _ in range(120):
        splat_gauss(light, rng.uniform(0, W), rng.uniform(0, 470), rng.uniform(0.5, 1.0), hexc("#dfe6ff"), rng.uniform(0.05, 0.22))
    img += light * M[..., None]
    return finish(img, rng)


def rays1d(rng, n=W + 800):
    r = rng.random(n).astype(np.float32)
    out = 0.5 * gaussian_filter(r, 2.5) + 0.3 * gaussian_filter(r, 7) + 0.2 * gaussian_filter(r, 25)
    out = (out - out.min()) / (out.max() - out.min())
    return out


def scene_default_night(rng):
    img = vgrad([(0, "#03050d"), (380, "#050a18"), (640, "#03050c"), (1080, "#020306")])
    M = deco_mask()
    x = np.arange(W, dtype=np.float32)
    aur = np.zeros((H, W, 3), np.float32)
    curtains = [  # base y, amp, phase, height, edge colour, top colour, gain
        (420, 45, 0.3, 170, "#1fd6a8", "#6a3cff", 0.85),
        (350, 55, 2.4, 150, "#25b8d8", "#8a4cff", 0.45),
        (300, 30, 4.4, 110, "#2ad0a0", "#3a5aff", 0.25),
    ]
    for yb, amp, ph, hgt, ce, ct, g in curtains:
        yc = yb + amp * np.sin(x / W * TAU * 0.75 + ph) + 18 * np.sin(x / W * TAU * 2.2 + ph * 1.7)
        d = yc[None, :] - YY                       # >0 above the lower edge
        dp = np.clip(d, 0, None)
        prof = np.where(d > 0, np.exp(-dp / hgt), np.exp(-0.5 * (np.clip(-d, 0, None) / 14) ** 2))
        r1 = rays1d(rng)
        idx = np.clip((XX + 0.35 * (yc[None, :] - YY) + 200).astype(np.int32), 0, len(r1) - 1)
        rays = 0.45 + 0.55 * r1[idx] ** 1.3
        env = (0.25 + 0.75 * np.clip(np.sin(np.clip(x / W * math.pi * 1.15 + ph * 0.15 - 0.1, 0, math.pi)), 0, 1) ** 1.5)[None, :]
        tmix = np.clip(d / (hgt * 1.4), 0, 1)[..., None]
        col = hexc(ce) * (1 - tmix) + hexc(ct) * tmix
        aur += (prof * rays * env)[..., None] * col * g
    aur = blur(aur, 2.6)
    img = screen(img, aur * M[..., None])
    img += blur(aur, 45) * 0.4 * M[..., None]
    light = np.zeros((H, W, 3), np.float32)
    for _ in range(170):
        splat_gauss(light, rng.uniform(0, W), rng.uniform(0, 470), rng.uniform(0.5, 1.0), hexc("#e6ecff"), rng.uniform(0.05, 0.28))
    img += light * np.maximum(M, 0.3)[..., None]
    return finish(img, rng)


SCENES = {
    "diwali": scene_diwali,
    "dussehra": scene_dussehra,
    "christmas": scene_christmas,
    "newyear": scene_newyear,
    "holi": scene_holi,
    "tricolour": scene_tricolour,
    "lohri": scene_lohri,
    "rakhi": scene_rakhi,
    "ganesh": scene_ganesh,
    "janmashtami": scene_janmashtami,
    "default-night": scene_default_night,
}


# ----------------------------------------------------------------------------- output + checks
def luma(u8):
    a = u8.astype(np.float32) / 255
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def save(name, u8):
    path = os.path.join(OUT, f"{name}.jpg")
    im = Image.fromarray(u8)
    for q in (86, 84, 82, 80, 76, 72):
        im.save(path, "JPEG", quality=q, optimize=True, progressive=True, subsampling=2)
        if os.path.getsize(path) < 250 * 1024:
            break
    return path, q


def report(name, u8, path, q):
    y = luma(u8)
    b = y[480:]
    tl = y[0:260, 0:900]
    pr = y[60:200, 1150:]
    print(f"{name:14s} {os.path.getsize(path) / 1024:6.1f} KB q{q}  "
          f"bottom mean {b.mean() * 100:4.1f}%  p95 {np.percentile(b, 95) * 100:4.1f}%  >15% {np.mean(b > 0.15) * 100:4.1f}%  "
          f"| clock mean {tl.mean() * 100:4.1f}% std {tl.std() * 100:4.1f}  | pills mean {pr.mean() * 100:4.1f}% std {pr.std() * 100:4.1f}")


def contact(names, mock=False):
    tw, th = 624, 351
    cols = 3
    rows = math.ceil(len(names) / cols)
    pad, lab = 16, 30
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * pad, rows * (th + lab) + (rows + 1) * pad), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        cfont = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 96)
        sfont = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 30)
    except OSError:
        font = cfont = sfont = ImageFont.load_default()
    for i, n in enumerate(names):
        im = Image.open(os.path.join(OUT, f"{n}.jpg")).convert("RGB")
        if mock:
            im = im.copy()
            md = ImageDraw.Draw(im, "RGBA")
            md.text((72, 50), "9:41", fill=(255, 255, 255, 255), font=cfont)
            md.text((76, 165), "Good evening", fill=(230, 230, 230, 220), font=sfont)
            for k in range(3):
                x0 = 1500 + k * 135
                md.rounded_rectangle([x0, 95, x0 + 115, 160], 32, fill=(255, 255, 255, 40), outline=(255, 255, 255, 90))
            for r in range(2):
                for c in range(5):
                    x0, y0 = 90 + c * 355, 560 + r * 250
                    md.rounded_rectangle([x0, y0, x0 + 320, y0 + 200], 22, fill=(70, 80, 110, 255))
        im = im.resize((tw, th), Image.LANCZOS)
        cx, cy = pad + (i % cols) * (tw + pad), pad + (i // cols) * (th + lab + pad)
        sheet.paste(im, (cx, cy))
        d.text((cx + 4, cy + th + 5), n, fill=(220, 220, 220), font=font)
    out = os.path.join(HERE, "contact_mock.jpg" if mock else "contact.jpg")
    sheet.save(out, "JPEG", quality=88)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    names = sys.argv[1:] or list(SCENES)
    for i, n in enumerate(SCENES):
        if n not in names:
            continue
        rng = np.random.default_rng(1000 + i)
        u8 = SCENES[n](rng)
        path, q = save(n, u8)
        report(n, u8, path, q)
    allnames = [n for n in SCENES if os.path.exists(os.path.join(OUT, f"{n}.jpg"))]
    print(contact(allnames))
    print(contact(allnames, mock=True))


if __name__ == "__main__":
    main()
