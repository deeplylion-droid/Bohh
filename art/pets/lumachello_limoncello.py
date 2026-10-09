"""Lumachello Limoncello - pet Divino (creatura meme originale).

Una lumachina giocattolo il cui guscio e' un limone lucido (buccia a fossette, due foglie in cima e
una spirale cucita sul fianco come il guscio di una chiocciola), corpo lime morbido, occhi in cima
alle antenne e un tappo di sughero come cappellino. Gocce di limoncello luminose.
Carattere: dolce-inquietante - occhioni innocenti con pupille piccolissime, ciglia, e un sorriso un
po' troppo largo pieno di dentini.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, capped_cone, capsule, ellipsoid, euler, project, round_cone,  # noqa: E402
                     sphere, torus, tube, union)
from lib.toy import Model  # noqa: E402

LIME = (170, 218, 40)
LIME_PALE = (222, 244, 140)
LEMON = (255, 214, 0)
LEAF = (34, 156, 58)
THREAD = (74, 22, 92)
EYE_WHITE = (255, 253, 246)
PUPIL = (24, 14, 30)
MOUTH = (58, 14, 62)
TOOTH = (255, 252, 242)
BLUSH = (255, 106, 140)
CORK = (198, 146, 90)
GOLD = (255, 186, 30)
DROP = (255, 236, 90)
WHITE = (255, 255, 255)

m = Model("LumachelloLimoncello", "pet")


# ---------------------------------------------------------------- helper locali
def seg2(x, z, a, b, r):
    px, pz = x - a[0], z - a[1]
    ex, ez = b[0] - a[0], b[1] - a[1]
    t = np.clip((px * ex + pz * ez) / (ex * ex + ez * ez + 1e-12), 0.0, 1.0)
    dx, dz = px - ex * t, pz - ez * t
    return np.sqrt(dx * dx + dz * dz) - r


def stencil(fn2d, xr, zr, depth=0.35):
    """Estrude una forma 2D fn2d(x, z) lungo l'asse locale Y (decalcomania da Frame.place)."""
    def f(p):
        return np.maximum(fn2d(p[:, 0], p[:, 2]), np.abs(p[:, 1]) - depth)
    return SDF(f, (xr[0], -depth, zr[0]), (xr[1], depth, zr[1]))


def normal_at(base, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float32)
    g = np.array([base((p + e)[None, :])[0] - base((p - e)[None, :])[0]
                  for e in np.eye(3, dtype=np.float32) * eps])
    return g / max(np.linalg.norm(g), 1e-9)


def on_surf(base, src, q):
    src = np.asarray(src, dtype=np.float64)
    return project(base, src, np.asarray(q, dtype=np.float64) - src)


def spheres(centers, r):
    """Unione veloce di tante sfere uguali (vicino piu' prossimo)."""
    C = np.asarray(centers, dtype=np.float32)
    tree = cKDTree(C)

    def f(p):
        d, _ = tree.query(p, k=1)
        return (d - r).astype(np.float32)
    return SDF(f, C.min(0) - r, C.max(0) + r)


def leaf(L, W, T, fold=0.35):
    c = W * 0.5
    A = L * 0.577
    t = T / 0.866
    flat = ellipsoid((t, A, W), (0, -L * 0.5, c)).intersect(ellipsoid((t, A, W), (0, -L * 0.5, -c)))

    def fold_pts(p):
        q = p.copy()
        q[:, 0] = q[:, 0] + fold * np.abs(q[:, 2])
        return q
    return flat.warp(fold_pts, pad=fold * W * 0.6)


def grin_edges(u, a, h, curve, skew):
    t = np.clip(u / a, -1.0, 1.0)
    top = curve * t * t + skew * t
    bot = top - h * np.power(np.clip(1.0 - t * t, 0.0, 1.0), 0.7)
    return top, bot


def grin_paint(base, frame, a, h, curve, skew, off=0.012, depth=0.4):
    def fn(x, z):
        top, bot = grin_edges(-x, a, h, curve, skew)
        return np.maximum(np.maximum(z - top, bot - z), np.abs(x) - a) * 0.8
    lo, hi = -h - abs(skew) - 0.05, curve + abs(skew) + 0.05
    return base.offset(off).intersect(frame.place(stencil(fn, (-a - 0.05, a + 0.05), (lo, hi), depth)))


def grin_teeth(base, frame, src, a, h, curve, skew, n_top, n_bot, L, r, lift=0.013):
    src = np.asarray(src, dtype=np.float64)
    out = []
    for n, span, sign, frac in [(n_top, 0.84, 1.0, 0.55), (n_bot, 0.7, -1.0, 0.42)]:
        for i in range(n):
            u = a * span * (-1.0 + 2.0 * (i + 0.5) / n)
            top, bot = grin_edges(u, a, h, curve, skew)
            li = min(L * (1.0 if sign > 0 else 0.8), (top - bot) * frac)
            if li < 0.02:
                continue
            z0 = top - 0.003 if sign > 0 else bot + 0.003
            z1 = z0 - sign * li
            pa, na = project(base, src, frame.point((-u, -0.3, z0)) - src)
            pb, nb = project(base, src, frame.point((-u, -0.3, z1)) - src)
            out.append(round_cone(pa + na * lift, pb + nb * lift, r, 0.005))
    return union(*out)


def stitches(base, pts, n, dash, r, across=True, lift=0.006):
    pts = np.asarray(pts, dtype=np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for t in np.linspace(0.0, s[-1], n):
        i = min(np.searchsorted(s, t, side="right") - 1, len(seg) - 1)
        w = (t - s[i]) / max(seg[i], 1e-9)
        p = pts[i] * (1 - w) + pts[i + 1] * w
        tan = (pts[i + 1] - pts[i]) / max(seg[i], 1e-9)
        nrm = normal_at(base, p)
        d = np.cross(nrm, tan) if across else tan - nrm * float(tan @ nrm)
        d /= np.linalg.norm(d)
        c = p + nrm * lift
        out.append(capsule(c - d * dash * 0.5, c + d * dash * 0.5, r))
    return union(*out)


# ---------------------------------------------------------------- corpo di lumaca (piede, collo, testa, antenne)
HEAD_C = (0.0, -0.8, 1.42)
foot = tube([(0.0, 1.3, 0.12), (0.0, 0.85, 0.22), (0.0, 0.25, 0.32), (0.0, -0.3, 0.4), (0.0, -0.66, 0.66),
             (0.0, -0.78, 1.0)], [0.1, 0.22, 0.32, 0.4, 0.42, 0.42], k=0.1)
skirt = ellipsoid((0.52, 1.15, 0.15), (0.0, 0.2, 0.14))
head = ellipsoid((0.52, 0.48, 0.5), HEAD_C)
STALK_TIPS = [(sx * 0.46, -0.98, 2.42) for sx in (1, -1)]
stalks = union(*[round_cone((sx * 0.18, -0.86, 1.78), tip, 0.1, 0.07) for sx, tip in zip((1, -1), STALK_TIPS)])
body = union(foot, skirt, k=0.12)
body = union(body, head, k=0.2)
body = union(body, stalks, k=0.08)
m.add("Body", body, LIME, tris=4400)

# pettorina chiara davanti (collo e viso)
front = ellipsoid((0.4, 0.4, 0.4), (0.0, -1.06, 1.36))
m.add("Front", body.offset(0.018).intersect(front), LIME_PALE, role="detail", tris=700)

# ---------------------------------------------------------------- guscio-limone (inclinato all'indietro) con fossette
LEMON_C = np.array([0.0, 0.36, 1.48])
LR, LL = 0.74, 0.86
LTILT = (-27.0, 0.0, 0.0)
RL = euler(*LTILT)
lemon_local = union(ellipsoid((LR, LR, LL)),
                    round_cone((0, 0, LL - 0.12), (0, 0, LL + 0.14), 0.2, 0.065),
                    round_cone((0, 0, -LL + 0.12), (0, 0, -LL - 0.12), 0.2, 0.07), k=0.13)
lemon0 = lemon_local.rot(*LTILT).translate(LEMON_C)
rng = np.random.default_rng(21)
dimples = []
for _ in range(260):
    v = rng.normal(size=3)
    v /= np.linalg.norm(v)
    p, n = project(lemon0, LEMON_C, RL @ v.astype(np.float32))
    dimples.append(p + n * 0.037)
lemon = lemon0.subtract(spheres(dimples, 0.065), k=0.012)
m.add("Lemon", lemon, LEMON, role="detail", tris=5000, voxel=0.016, reflectance=0.15)
TOP = LEMON_C + RL @ np.array([0.0, 0.0, LL + 0.12], dtype=np.float32)

# foglie e piccolo picciolo in cima
leaves = [capsule(TOP - RL @ np.array([0, 0, 0.04], dtype=np.float32), TOP + RL @ np.array([0, 0, 0.08], dtype=np.float32), 0.04)]
for yaw, tilt, size in ((35, -24, 1.0), (-120, -16, 0.85)):
    lf = leaf(0.5 * size, 0.28 * size, 0.03).rot(0, 90, 0).rot(tilt, 0, 0).rot(0, 0, yaw)
    leaves.append(lf.translate(TOP + RL @ np.array([0, 0, 0.05], dtype=np.float32)))
m.add("Leaves", union(*leaves), LEAF, role="detail", tris=600, voxel=0.012)

# spirale cucita sui due fianchi del limone: guscio di chiocciola + cucitura da peluche
spiral_parts = []
for sx in (1, -1):
    side = RL @ np.array([sx * 1.0, 0.0, 0.0], dtype=np.float32)
    up = RL @ np.array([0.0, 0.0, 1.0], dtype=np.float32)
    fwd = np.cross(side, up)
    pts = []
    for t in np.linspace(0.0, 2.3 * 2 * math.pi, 70):
        r = 0.06 + 0.4 * t / (2.3 * 2 * math.pi)
        q = LEMON_C + side * 1.2 + (up * math.cos(t) * 1.15 + fwd * math.sin(t) * sx) * r
        pts.append(on_surf(lemon0, LEMON_C, q)[0])
    spiral_parts.append(stitches(lemon0, pts, 30, 0.07, 0.017, across=False, lift=0.004))

# gocce di limoncello luminose sul guscio
drops = []
for d, s in (((0.7, -0.3, 0.35), 0.075), ((0.55, 0.6, -0.1), 0.065), ((-0.75, -0.2, 0.15), 0.07),
             ((-0.4, 0.75, 0.45), 0.06), ((0.2, -0.75, -0.25), 0.06)):
    p, n = on_surf(lemon0, LEMON_C, LEMON_C + RL @ np.array(d, dtype=np.float32) * 3.0)
    up = np.array([0.0, 0.0, 1.0]) - n * float(n[2])  # la goccia scivola giu': punta verso l'alto lungo la buccia
    up /= max(np.linalg.norm(up), 1e-6)
    base_c = p + n * (s * 0.3)
    drops.append(union(sphere(s, base_c), round_cone(base_c, base_c + up * s * 2.0 + n * s * 0.2, s * 0.75, 0.01), k=0.03))
m.add("Drops", union(*drops), DROP, material="Neon", role="glow", tris=500, voxel=0.01)

# ---------------------------------------------------------------- occhioni sulle antenne (pupille piccolissime) e ciglia
EYE_R = 0.2
eyes_w, pupils, shines, lashes = [], [], [], []
for sx, tip in zip((1, -1), STALK_TIPS):
    c = np.array(tip) + np.array([sx * 0.02, -0.04, 0.06])
    eyes_w.append(sphere(EYE_R, c))
    look = np.array([-sx * 0.12, -1.0, -0.05])
    look /= np.linalg.norm(look)
    pc = c + look * (EYE_R - 0.012)
    pupils.append(ellipsoid((0.06, 0.06, 0.07), pc))
    shines.append(sphere(0.022, pc + np.array([0.03, -0.04, 0.035])))
    for k in (-1, 0, 1):  # tre ciglia sopra l'occhio
        a = math.radians(70 + 22 * k)
        root = c + np.array([sx * math.cos(a) * 0.12 * (1 if k else 0.4), -0.08, math.sin(a) * EYE_R * 0.92])
        tip_l = root + np.array([sx * 0.04 * k + sx * 0.01, -0.03, 0.1])
        lashes.append(round_cone(root, tip_l, 0.022, 0.008))
m.add("EyeWhites", union(*eyes_w), EYE_WHITE, role="shine", tris=700, voxel=0.012)
m.add("Pupils", union(*pupils), PUPIL, role="eye", tris=300, voxel=0.01)
m.add("Shine", union(*shines), WHITE, role="shine", tris=200, voxel=0.008)

# sorriso troppo largo con dentini
mouth_f = Frame(body, HEAD_C, (0.0, -1.0, -0.1))
GA, GH, GC, GS = 0.36, 0.21, 0.14, 0.0
m.add("Mouth", grin_paint(body, mouth_f, GA, GH, GC, GS, off=0.03), MOUTH, role="detail", tris=400, voxel=0.01)
m.add("Teeth", grin_teeth(body, mouth_f, HEAD_C, GA, GH, GC, GS, n_top=12, n_bot=9, L=0.055, r=0.019, lift=0.034), TOOTH,
      role="detail", tris=500, voxel=0.008)
blush = ellipsoid((0.12, 0.04, 0.08))
m.add("Blush", union(*[Frame(body, HEAD_C, (0.72 * sx, -1.0, 0.4), sink=0.015).place(blush) for sx in (1, -1)]),
      BLUSH, role="detail", tris=300, voxel=0.012)
# filo scuro: spirali cucite sul limone e ciglia (stesso colore, una sola parte)
m.add("Stitches", union(*spiral_parts, *lashes), THREAD, role="detail", tris=900, voxel=0.009)

# ---------------------------------------------------------------- tappo di sughero come cappellino (inclinato)
HAT_BASE = np.array(on_surf(body, HEAD_C, (0.12, -0.62, 2.2))[0])
hat_local = union(capped_cone((0, 0, -0.06), (0, 0, 0.26), 0.17, 0.2, round=0.04))
band_local = torus(0.19, 0.035, (0, 0, 0.17))
HM = euler(-14.0, 16.0, 0.0)
m.add("Cork", hat_local.rotate(HM).translate(HAT_BASE), CORK, role="detail", tris=500, voxel=0.012)
m.add("CorkBand", band_local.rotate(HM).translate(HAT_BASE), GOLD, material="Metal", role="detail", tris=300,
      voxel=0.01)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
