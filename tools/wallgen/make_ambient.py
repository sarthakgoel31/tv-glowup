#!/usr/bin/env python3
"""Procedural ambient (time-of-day + weather) backgrounds for the TV Glowup "india" theme.

Extends make_walls.py: same canvas, helpers, layout contract and measurements.

Run:  python3 tools/wallgen/make_ambient.py [slot ...]   (pip install -r tools/requirements.txt)
Out:  themes/india/ambient/<slot>.jpg  (1920x1080, q~85, <200 KB)
      tools/wallgen/ambient_contact.jpg and ambient_contact_mock.jpg (white clock + tiles overlay)

Layout contract (every image):
  clock zone  x 0-900,    y 0-260   mean luma <= 18 %, calm
  pill zone   x 1150-1920 y 60-200  calm
  tile zone   y > 480               mean luma < 15 %, few pixels > 15 %
  sky         y 0-480 (interest mostly y 120-440)
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter, map_coordinates

from make_walls import (H, HERE, TAU, W, XX, YY, Layer, blur, finish, gauss, hexc, luma, smoothstep,
                        splat_gauss, vgrad)

OUT = os.path.join(HERE, "..", "..", "themes", "india", "ambient")
MAX_KB = 200


# ----------------------------------------------------------------------------- sky helpers
def fbm_xy(rng, bx, by, octaves=6, persist=0.55, lac=2.0):
    """Value-noise fbm in [0,1] with independent x/y base frequencies (stretched clouds)."""
    acc = np.zeros((H, W), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        gw, gh = int(bx * lac ** o) + 3, int(by * lac ** o) + 3
        g = rng.random((gh, gw)).astype(np.float32)
        acc += amp * np.asarray(Image.fromarray(g, "F").resize((W, H), Image.BICUBIC))
        tot += amp
        amp *= persist
    acc /= tot
    return (acc - acc.min()) / (acc.max() - acc.min() + 1e-6)


def band(y0, y1, y2, y3):
    """Vertical envelope: 0 above y0, ramps to 1 by y1, back to 0 by y3."""
    return (smoothstep(y0, y1, YY) * (1 - smoothstep(y2, y3, YY))).astype(np.float32)


def density(rng, bx, by, cover, soft, env, octaves=6, persist=0.55, warp=0.0):
    n = fbm_xy(rng, bx, by, octaves, persist)
    if warp:
        n = 0.75 * n + 0.25 * fbm_xy(rng, bx * 3, by * 3, 3, 0.5) * warp
    return smoothstep(cover - soft, cover + soft, n * (0.35 + 0.65 * env) + 0.35 * env - 0.35) * env


def shift(a, dx, dy):
    dx, dy = int(round(dx)), int(round(dy))
    p = max(abs(dx), abs(dy)) + 1
    ap = np.pad(a, p, mode="edge")
    return ap[p + dy:p + dy + H, p + dx:p + dx + W]


def illum_dir(d, L, steps=5, step=10, k=1.6, pre=3):
    """Directional light: transmittance toward the light along L=(dx,dy)."""
    db = blur(d, pre)
    n = math.hypot(*L)
    lx, ly = L[0] / n, L[1] / n
    acc = np.zeros_like(d)
    for i in range(1, steps + 1):
        acc += shift(db, lx * step * i, ly * step * i)
    return np.exp(-k * acc / steps).astype(np.float32)


def illum_point(d, P, steps=5, step=12, k=1.6, pre=3):
    """Point light at P (sun/moon in frame): transmittance toward P."""
    db = blur(d, pre)
    vx, vy = P[0] - XX, P[1] - YY
    n = np.hypot(vx, vy) + 1e-3
    vx, vy = vx / n, vy / n
    acc = np.zeros_like(d)
    for i in range(1, steps + 1):
        s = np.minimum(step * i, n)
        acc += map_coordinates(db, [YY + vy * s, XX + vx * s], order=1, mode="nearest")
    return np.exp(-k * acc / steps).astype(np.float32)


def cloud_over(img, d, il, dark, lit, alpha=1.0, rim=0.0, rimcol=None):
    """Composite a cloud layer: colour = dark..lit by illumination; rim = silver/gold lining."""
    dark = dark if isinstance(dark, np.ndarray) and dark.ndim == 3 else np.asarray(dark, np.float32)
    lit = lit if isinstance(lit, np.ndarray) and lit.ndim == 3 else np.asarray(lit, np.float32)
    col = dark * (1 - il[..., None]) + lit * il[..., None]
    a = np.clip(d * alpha, 0, 1)[..., None]
    img = img * (1 - a) + col * a
    if rim:
        edge = np.clip(d * (1 - d) * 4, 0, 1) * il
        img = img + edge[..., None] * (rimcol if rimcol is not None else lit) * rim
    return img


def sparse_stars(rng, p, ymax=480, amin=0.15, amax=1.0, weight=None):
    """Vectorised starfield: Bernoulli points, power-law brightness, tiny blur."""
    m = rng.random((H, W)) < p * (1 if weight is None else weight)
    v = np.where(m, amin + (amax - amin) * rng.random((H, W)) ** 3, 0).astype(np.float32)
    v *= 1 - smoothstep(ymax - 120, ymax, YY)
    return gaussian_filter(v, 0.6) * 3.2


def rain_streaks(rng, density_p=0.0035, length=26, ang=0.22):
    """Static diagonal rain texture in [0,~1]."""
    pad = 200
    n = (rng.random((H + 2 * pad, W + 2 * pad)) < density_p).astype(np.float32) * rng.random((H + 2 * pad, W + 2 * pad))
    s = gaussian_filter(n, (length, 0.55))
    s = s / (s.max() + 1e-6)
    im = Image.fromarray(s.astype(np.float32), "F").rotate(math.degrees(ang), Image.BILINEAR)
    s = np.asarray(im)[pad:pad + H, pad:pad + W]
    return np.clip(s / np.percentile(s, 99.7), 0, 1.5).astype(np.float32)


def layout(img, tl=0.45, pill=0.7, fade=(330, 560), floor=0.02, tail=0.13):
    """Soft elliptical darkening for the clock + pills, then fade to near-black below the sky."""
    clock = np.exp(-0.5 * (((XX - 330) / 600) ** 2 + ((YY - 110) / 190) ** 2))
    pills = np.exp(-0.5 * (((XX - 1580) / 520) ** 4 + ((YY - 130) / 105) ** 4))
    k = (1 - clock * (1 - tl)) * (1 - pills * (1 - pill))
    # gaussian roll-off below fade[0] (reaches ~2 % at fade[1]): no visible horizon seam
    sig = (fade[1] - fade[0]) / 2.8
    dy = np.clip(YY - fade[0], 0, None)
    g = np.exp(-0.5 * (dy / sig) ** 2)
    bot = floor + (1 - floor) * (g + tail * (1 - g) * np.exp(-dy / 320))   # long faint tail keeps sky colour
    bot = bot * (1 - 0.6 * smoothstep(620, 1080, YY))
    return img * (k * bot)[..., None]


def done(img, rng, **kw):
    return finish(layout(np.clip(img, 0, None), **kw), rng, bottom=(0.8, 0.55))


# ----------------------------------------------------------------------------- scenes
def scene_dawn(rng):
    img = vgrad([(0, "#18213c"), (160, "#2c4068"), (290, "#6a7ea6"), (370, "#c79aa2"), (430, "#f2b38e"), (520, "#f6c49a")])
    img += gauss(260, 450, 820, 150)[..., None] * hexc("#ff9a7a") * 0.45
    img += gauss(220, 470, 300, 70)[..., None] * hexc("#ffd6a8") * 0.55
    img += gauss(1500, 120, 900, 200)[..., None] * hexc("#9ab4dc") * 0.10
    env = band(150, 230, 360, 430) * (0.4 + 0.6 * smoothstep(1700, 300, XX))
    d = density(rng, 3.0, 11, 0.56, 0.14, env, octaves=6) * 0.8
    il = illum_point(d, (200, 520), steps=5, step=10, k=2.2)
    warm = smoothstep(1500, 100, XX)[..., None]
    lit = hexc("#ffc9a0") * warm + hexc("#e6a8b8") * (1 - warm)
    img = cloud_over(img, d, il, hexc("#6a5470"), lit * 1.05, alpha=0.9, rim=0.25, rimcol=hexc("#ffe0c0"))
    return done(img, rng, tl=0.42, pill=0.75, fade=(330, 540))


def scene_day(rng):
    img = vgrad([(0, "#0a2552"), (220, "#184a8c"), (400, "#3d7cc0"), (520, "#6aa0d4")])
    img += gauss(1920, -40, 620, 420)[..., None] * hexc("#fff2cf") * 0.30
    img += gauss(1920, -40, 170)[..., None] * hexc("#fffaf0") * 0.45
    env = band(120, 210, 390, 450) * (0.7 + 0.3 * smoothstep(300, 1500, XX))
    d = density(rng, 5.0, 4.0, 0.56, 0.09, env, octaves=7, persist=0.5)
    il = illum_dir(d, (0.75, -0.65), steps=6, step=7, k=2.2)
    img = cloud_over(img, d, il, hexc("#8296ba"), hexc("#fbfcff"), alpha=0.95, rim=0.15)
    return done(img, rng, tl=0.42, pill=0.62, fade=(330, 540))


def scene_dusk(rng):
    img = vgrad([(0, "#140c2c"), (150, "#2c1648"), (270, "#6a2258"), (350, "#c2464a"), (410, "#f08a3a"), (470, "#ffb84a")])
    sun = (1480, 425)
    img += gauss(*sun, 700, 150)[..., None] * hexc("#ff8a30") * 0.45
    img += gauss(*sun, 120, 50)[..., None] * hexc("#ffe6a8") * 0.9
    env = band(70, 160, 340, 410)
    d = density(rng, 2.6, 7.5, 0.52, 0.12, env, octaves=7, persist=0.56)
    il = illum_point(d, sun, steps=6, step=12, k=2.0)
    near = np.exp(-0.5 * (((XX - sun[0]) / 650) ** 2 + ((YY - sun[1]) / 260) ** 2))[..., None]
    lit = hexc("#ffb040") * near + hexc("#e04a8a") * (1 - near)
    lit = lit * (0.75 + 0.35 * smoothstep(80, 380, YY))[..., None]
    img = cloud_over(img, d, il, hexc("#2e1a44"), lit * 1.1, alpha=0.95, rim=0.35, rimcol=hexc("#ffd080"))
    return done(img, rng, tl=0.5, pill=0.7, fade=(340, 540))


def scene_night(rng):
    img = vgrad([(0, "#02040b"), (260, "#050c22"), (440, "#0a1636"), (520, "#0c1a3c")])
    img += gauss(1920, 0, 520, 360)[..., None] * hexc("#8aa0e0") * 0.10
    img += gauss(1920, 0, 120)[..., None] * hexc("#d8e2ff") * 0.10
    # Milky Way: band from lower-left middle up to the top-right-centre
    a = math.atan2(-520, 1300)
    nx, ny = -math.sin(a), math.cos(a)
    dist = (XX - 500) * nx + (YY - 470) * ny
    mw = np.exp(-0.5 * (dist / 120) ** 2)
    neb = fbm_xy(rng, 6, 4, 6, 0.6)
    dust = smoothstep(0.45, 0.75, fbm_xy(rng, 10, 7, 5, 0.6)) * np.exp(-0.5 * (dist / 40) ** 2)
    glow = mw * (0.35 + 0.65 * neb ** 1.5) * (1 - 0.7 * dust)
    img += glow[..., None] * (hexc("#8a90c8") * 0.30 + hexc("#e0c8b8") * 0.12 * np.exp(-0.5 * (dist / 50) ** 2)[..., None])
    st = sparse_stars(rng, 0.0016, weight=1 + 5 * mw * (1 - dust))
    img += st[..., None] * hexc("#e8eeff") * 0.6
    L = Layer("L")
    bright = []
    for _ in range(14):
        x, y = rng.uniform(950, 1880), rng.uniform(220, 440)
        if rng.random() < 0.3:
            x = rng.uniform(80, 900)
            y = rng.uniform(290, 440)
        bright.append((x, y))
        s = rng.uniform(5, 11)
        L.line([(x - s, y), (x + s, y)], fill=160, width=0.6)
        L.line([(x, y - s), (x, y + s)], fill=160, width=0.6)
    sp = L.arr()
    img += (sp + blur(sp, 2.5))[..., None] * hexc("#dfe6ff") * 0.35
    for x, y in bright:
        splat_gauss(img, x, y, rng.uniform(1.0, 1.6), hexc("#f2f5ff"), rng.uniform(0.6, 0.9))
        splat_gauss(img, x, y, 5, hexc("#a8b8ff"), 0.10)
    return done(img, rng, tl=0.6, pill=0.8, fade=(360, 560))


def scene_cloudy_day(rng):
    img = vgrad([(0, "#28323f"), (220, "#4c5a6b"), (400, "#7a8797"), (520, "#8f9aa8")])
    brk = gauss(1260, 240, 260, 110)
    img += brk[..., None] * hexc("#fff3dc") * 0.30
    for i, (bx, by, cov, y0, y3, dk, lt, al) in enumerate([
            (1.6, 5.5, 0.48, 0, 420, "#3a4452", "#8c98a8", 0.85),
            (2.4, 7.0, 0.55, 120, 450, "#4a5564", "#a8b2c0", 0.80),
            (3.4, 9.0, 0.60, 250, 470, "#56606e", "#c0c8d2", 0.70)]):
        env = band(y0, y0 + 80, y3 - 70, y3)
        d = density(rng, bx, by, cov, 0.16, env, octaves=6) * (1 - 0.75 * brk)
        il = illum_point(d, (1260, 180), steps=5, step=11, k=1.8)
        img = cloud_over(img, d, il, hexc(dk), hexc(lt), alpha=al, rim=0.18, rimcol=hexc("#f2ece0"))
    return done(img, rng, tl=0.45, pill=0.62, fade=(330, 540))


def scene_cloudy_night(rng):
    img = vgrad([(0, "#03050c"), (260, "#070d1c"), (440, "#0c1528"), (520, "#0e182c")])
    moon = (1080, 250)
    img += gauss(*moon, 420, 260)[..., None] * hexc("#6a7ea8") * 0.22
    img += gauss(*moon, 60)[..., None] * hexc("#e8eeff") * 0.55
    img += sparse_stars(rng, 0.0006, amax=0.6)[..., None] * hexc("#dfe6ff") * 0.4
    for bx, by, cov, y0, y3, al in [(2.0, 6.0, 0.52, 40, 440, 0.95), (3.0, 8.0, 0.58, 160, 470, 0.9)]:
        env = band(y0, y0 + 90, y3 - 80, y3)
        d = density(rng, bx, by, cov, 0.13, env, octaves=6)
        il = illum_point(d, moon, steps=6, step=10, k=2.6)
        near = np.exp(-0.5 * (np.hypot(XX - moon[0], (YY - moon[1]) * 1.6) / 520) ** 2)
        img = cloud_over(img, d, il * (0.35 + 0.65 * near), hexc("#070b16"), hexc("#7d8aa8"), alpha=al,
                         rim=0.6 * 1, rimcol=hexc("#c8d4f0") * near[..., None])
    return done(img, rng, tl=0.6, pill=0.75, fade=(360, 560))


def scene_rain_day(rng):
    img = vgrad([(0, "#1c232d"), (220, "#33404e"), (400, "#56626e"), (520, "#606c78")])
    for bx, by, cov, y0, y3, dk, lt in [(1.8, 4.5, 0.42, 0, 400, "#1e2630", "#56616e"),
                                        (2.8, 6.5, 0.52, 80, 330, "#2a333e", "#6a7582")]:
        env = band(y0, y0 + 60, y3 - 90, y3)
        d = density(rng, bx, by, cov, 0.2, env, octaves=6)
        il = illum_dir(d, (0.3, -1), steps=4, step=12, k=1.5)
        img = cloud_over(img, d, il, hexc(dk), hexc(lt), alpha=0.9)
    haze = band(250, 380, 470, 560) * (0.6 + 0.4 * fbm_xy(rng, 2, 3, 4))
    img = img * (1 - 0.4 * haze[..., None]) + haze[..., None] * hexc("#8a96a2") * 0.4
    r = rain_streaks(rng, 0.004, 24, 0.24) * band(60, 160, 380, 520)
    img = img + r[..., None] * hexc("#c8d2dc") * 0.13
    return done(img, rng, tl=0.5, pill=0.7, fade=(330, 540))


def scene_rain_night(rng):
    img = vgrad([(0, "#020409"), (260, "#060b16"), (440, "#0b1322"), (520, "#0c1424")])
    for bx, by, cov, y0, y3, dk, lt in [(1.8, 4.5, 0.45, 0, 420, "#03060c", "#1e2a3e"),
                                        (2.8, 6.5, 0.55, 90, 360, "#050912", "#26344a")]:
        env = band(y0, y0 + 60, y3 - 90, y3)
        d = density(rng, bx, by, cov, 0.2, env, octaves=6)
        il = illum_dir(d, (0.2, -1), steps=4, step=12, k=1.5)
        img = cloud_over(img, d, il, hexc(dk), hexc(lt), alpha=0.95, rim=0.12, rimcol=hexc("#5a6e90"))
    haze = band(260, 380, 470, 560) * (0.6 + 0.4 * fbm_xy(rng, 2, 3, 4))
    img += haze[..., None] * hexc("#1a2638") * 0.35
    r = rain_streaks(rng, 0.0035, 26, 0.24) * band(40, 140, 380, 520)
    img = img + r[..., None] * hexc("#8ea4c8") * 0.10
    return done(img, rng, tl=0.65, pill=0.8, fade=(360, 560))


def scene_storm(rng):
    img = vgrad([(0, "#08060e"), (220, "#16111f"), (400, "#2a2238"), (520, "#30283e")])
    env = band(0, 40, 360, 450)
    d = density(rng, 2.4, 3.2, 0.48, 0.14, env, octaves=7, persist=0.56)
    il = illum_dir(d, (0.2, -1), steps=5, step=12, k=1.6)
    img = cloud_over(img, d, il, hexc("#0c0912"), hexc("#4a3e5c"), alpha=0.95, rim=0.15, rimcol=hexc("#8a7aa8"))
    # internal lightning glow, lighting the cloud mass from inside
    flash = gauss(1230, 330, 230, 120) + 0.45 * gauss(1660, 250, 150, 90) + 0.25 * gauss(760, 380, 140, 70)
    inner = blur(d, 6)
    fl = flash * (0.3 + 0.7 * inner) * (0.6 + 0.4 * fbm_xy(rng, 8, 6, 4))
    img += fl[..., None] * hexc("#c8b4ff") * 0.75
    img += gauss(1230, 330, 70, 45)[..., None] * inner[..., None] * hexc("#f2ecff") * 0.45
    return done(img, rng, tl=0.6, pill=0.75, fade=(350, 560))


def scene_fog(rng):
    img = vgrad([(0, "#3c3830"), (220, "#6e685c"), (400, "#958d7e"), (520, "#9c9484")])
    sun = (1280, 235)
    img += gauss(*sun, 380, 260)[..., None] * hexc("#d8c8a0") * 0.22
    dsc = np.clip((58 - np.hypot(XX - sun[0], YY - sun[1])) / 4 + 0.5, 0, 1)
    disc = blur(dsc, 2.5)
    for bx, by, y0, y3, k in [(1.2, 10, 0, 480, 0.35), (2.0, 16, 120, 480, 0.30), (3.2, 22, 200, 480, 0.25)]:
        n = fbm_xy(rng, bx, by, 5, 0.5)
        layer = smoothstep(0.3, 0.8, n) * band(y0, y0 + 80, y3 - 60, y3)
        img = img * (1 - k * layer[..., None]) + layer[..., None] * hexc("#b2aa98") * k
    img += disc[..., None] * hexc("#fff0d0") * 0.13
    return done(img, rng, tl=0.32, pill=0.55, fade=(320, 530))


def scene_hot(rng):
    img = vgrad([(0, "#b89a68"), (170, "#d8c08e"), (330, "#efe0bc"), (480, "#f6eedc")])
    sun = (1870, -20)
    img *= (0.5 + 0.5 * smoothstep(-200, 1700, XX) + 0.5 * smoothstep(200, 470, YY))[..., None].clip(0, 1)
    img += gauss(*sun, 1000, 520)[..., None] * hexc("#fff0c0") * 0.30
    img += gauss(*sun, 300, 240)[..., None] * hexc("#fff8e6") * 0.45
    img += gauss(*sun, 80)[..., None] * hexc("#ffffff") * 0.9
    # heat-haze shimmer bands low in the sky
    wob = fbm_xy(rng, 6, 2, 4, 0.5)
    sh = np.sin(YY * 0.42 + 9 * wob + XX * 0.004) * np.sin(YY * 0.11 + 4 * wob)
    hb = band(310, 380, 440, 490)
    img = img * (1 + 0.045 * sh * hb)[..., None] + hb[..., None] * hexc("#fff4d8") * 0.05
    # thin bleached high haze
    hz = smoothstep(0.5, 0.85, fbm_xy(rng, 2, 7, 5)) * band(150, 230, 380, 440)
    img += hz[..., None] * hexc("#fff8e8") * 0.10
    return done(img, rng, tl=0.17, pill=0.4, fade=(320, 520))


def frost(L, x0, y0, ang, length, rng, depth=0, val=255):
    """Ice dendrite: a spine with paired +-60 degree side branches."""
    n = max(3, int(length / 7))
    x, y = x0, y0
    for i in range(n):
        a = ang + rng.normal(0, 0.03)
        nx, ny = x + length / n * math.cos(a), y + length / n * math.sin(a)
        v = int(val * (1 - 0.7 * i / n))
        L.line([(x, y), (nx, ny)], fill=v, width=1.3 if depth == 0 else 0.9)
        if depth < 2 and i > 0 and rng.random() < 0.7:
            bl = length * (1 - i / n) * rng.uniform(0.22, 0.4)
            for side in (-1, 1):
                frost(L, nx, ny, a + side * math.pi / 3, bl, rng, depth + 1, int(v * 0.85))
        x, y = nx, ny


def scene_cold(rng):
    img = vgrad([(0, "#14243a"), (200, "#36587a"), (360, "#7aa2c0"), (470, "#b8d4e4"), (520, "#c4dcea")])
    img += gauss(1120, 440, 700, 130)[..., None] * hexc("#fff6ea") * 0.30
    img += gauss(1120, 455, 120, 40)[..., None] * hexc("#fffdf8") * 0.40
    hz = smoothstep(0.55, 0.85, fbm_xy(rng, 1.6, 9, 6)) * band(140, 220, 380, 440)
    img += hz[..., None] * hexc("#e8f2ff") * 0.18
    L = Layer("L")
    corners = [((W, 0), math.radians(135), 1.0), ((0, H), math.radians(-45), 0.6), ((W, H), math.radians(-135), 0.6),
               ((0, 0), math.radians(45), 0.35)]
    for (cx, cy), base, s in corners:
        for k in range(7):
            a = base + rng.uniform(-0.7, 0.7)
            r0 = rng.uniform(0, 60)
            frost(L, cx + r0 * math.cos(a), cy + r0 * math.sin(a), a, rng.uniform(80, 170) * s, rng, val=int(255 * s))
    fr = L.arr()
    corner_w = np.maximum.reduce([np.exp(-np.hypot(XX - cx, YY - cy) / 210) for (cx, cy), _, _ in corners])
    fimg = (fr + blur(fr, 3) * 0.8)[..., None] * hexc("#dceeff") * corner_w[..., None]
    out = done(img, rng, tl=0.42, pill=0.65, fade=(330, 540)).astype(np.float32) / 255
    out = np.clip(out + fimg * 0.33, 0, 1)
    return (out * 255 + 0.5).astype(np.uint8)


SCENES = {
    "dawn": scene_dawn, "day": scene_day, "dusk": scene_dusk, "night": scene_night,
    "cloudy-day": scene_cloudy_day, "cloudy-night": scene_cloudy_night,
    "rain-day": scene_rain_day, "rain-night": scene_rain_night, "storm": scene_storm,
    "fog": scene_fog, "hot": scene_hot, "cold": scene_cold,
}


# ----------------------------------------------------------------------------- output + checks
def save(name, u8):
    path = os.path.join(OUT, f"{name}.jpg")
    im = Image.fromarray(u8)
    for q in (86, 85, 84, 82, 80, 76, 72):
        im.save(path, "JPEG", quality=q, optimize=True, progressive=True, subsampling=2)
        if os.path.getsize(path) < MAX_KB * 1024:
            break
    return path, q


def measure(u8):
    y = luma(u8)
    b, tl, pr = y[480:], y[0:260, 0:900], y[60:200, 1150:]
    return dict(bottom=b.mean() * 100, b15=np.mean(b > 0.15) * 100, clock=tl.mean() * 100, clock_std=tl.std() * 100,
                pills=pr.mean() * 100, pills_std=pr.std() * 100, sky=y[0:480].mean() * 100)


def report(name, u8, path, q):
    m = measure(u8)
    ok = m["bottom"] < 15 and m["b15"] < 5 and m["clock"] <= 18
    print(f"{name:13s} {os.path.getsize(path) / 1024:6.1f} KB q{q} | bottom {m['bottom']:4.1f}% >15% {m['b15']:4.1f}% "
          f"| clock {m['clock']:4.1f}% sd {m['clock_std']:4.1f} | pills {m['pills']:4.1f}% sd {m['pills_std']:4.1f} "
          f"| sky {m['sky']:4.1f}%  {'OK' if ok else 'FAIL'}")


def contact(names, mock=False):
    tw, th, cols, pad, lab = 624, 351, 3, 16, 30
    rows = math.ceil(len(names) / cols)
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * pad, rows * (th + lab) + (rows + 1) * pad), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    hel = "/System/Library/Fonts/Helvetica.ttc"
    font, cfont, sfont = (ImageFont.truetype(hel, s) for s in (20, 120, 34))
    for i, n in enumerate(names):
        im = Image.open(os.path.join(OUT, f"{n}.jpg")).convert("RGB")
        if mock:
            md = ImageDraw.Draw(im, "RGBA")
            md.text((72, 40), "9:41", fill=(255, 255, 255, 255), font=cfont)
            md.text((78, 185), "Good morning", fill=(235, 235, 235, 230), font=sfont)
            for k in range(3):
                x0 = 1480 + k * 140
                md.rounded_rectangle([x0, 95, x0 + 120, 160], 32, fill=(255, 255, 255, 40), outline=(255, 255, 255, 110))
            for r in range(2):
                for c in range(4):
                    x0, y0 = 90 + c * 450, 560 + r * 260
                    md.rounded_rectangle([x0, y0, x0 + 410, y0 + 220], 24, fill=(60, 70, 100, 255))
        im = im.resize((tw, th), Image.LANCZOS)
        cx, cy = pad + (i % cols) * (tw + pad), pad + (i // cols) * (th + lab + pad)
        sheet.paste(im, (cx, cy))
        d.text((cx + 4, cy + th + 5), n, fill=(220, 220, 220), font=font)
    out = os.path.join(HERE, "ambient_contact_mock.jpg" if mock else "ambient_contact.jpg")
    sheet.save(out, "JPEG", quality=88)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    names = sys.argv[1:] or list(SCENES)
    for i, n in enumerate(SCENES):
        if n not in names:
            continue
        rng = np.random.default_rng(2000 + i)
        u8 = SCENES[n](rng)
        path, q = save(n, u8)
        report(n, u8, path, q)
    allnames = [n for n in SCENES if os.path.exists(os.path.join(OUT, f"{n}.jpg"))]
    print(contact(allnames))
    print(contact(allnames, mock=True))


if __name__ == "__main__":
    main()
