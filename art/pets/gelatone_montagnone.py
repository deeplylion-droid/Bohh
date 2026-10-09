"""Gelatone Montagnone (GelatoneMontagnone) - pet Mitico, creatura meme originale: un cono gelato che e' una montagna.

Carattere: brontolone (fronte aggrottata, braccia conserte, morso inverso con zanne, bava di panna).
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capped_cone, capsule, cylinder, ellipsoid, prism, project, round_cone,  # noqa: E402
                     smin, sphere, torus, tube, union)
from lib.toy import Model  # noqa: E402


# ============================================================ helper "toy horror" (lib/ non si modifica: copiati qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def grad(sdf, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float64)
    g = np.zeros(3)
    for ax in range(3):
        e = np.zeros(3)
        e[ax] = eps
        g[ax] = sdf((p + e)[None, :].astype(np.float32))[0] - sdf((p - e)[None, :].astype(np.float32))[0]
    return g / max(np.linalg.norm(g), 1e-9)


def on_surface(sdf, p, lift=0.0, iters=4):
    """Porta p sulla superficie (a distanza 'lift' verso l'esterno) seguendo il gradiente."""
    p = np.asarray(p, dtype=np.float64)
    for _ in range(iters):
        d = float(sdf(p[None, :].astype(np.float32))[0])
        p = p - grad(sdf, p) * (d - lift)
    return p


def fast_union(shapes, k=0.0, base=None, margin=0.06):
    """Unione di tante forme piccole, ognuna valutata solo vicino al proprio ingombro."""
    shapes = list(shapes)
    los = np.array([s.lo for s in shapes]) - margin - k
    his = np.array([s.hi for s in shapes]) + margin + k

    def f(p):
        d = base(p) if base is not None else np.full(len(p), 1.0, dtype=np.float32)
        if len(p) == 0:
            return d
        plo, phi = p.min(0), p.max(0)
        for i in np.nonzero(np.all((his >= plo) & (los <= phi), axis=1))[0]:
            msk = np.all((p >= los[i]) & (p <= his[i]), axis=1)
            if msk.any():
                idx = np.nonzero(msk)[0]
                d[idx] = smin(d[idx], shapes[i](p[idx]), k)
        return d

    lo, hi = los.min(0), his.max(0)
    if base is not None:
        lo, hi = np.minimum(lo, base.lo), np.maximum(hi, base.hi)
    return SDF(f, lo, hi)


def resample(points, step):
    pts = np.asarray(points, dtype=np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(int(round(cum[-1] / step)), 1)
    out = []
    for s in np.linspace(0.0, cum[-1], n + 1):
        i = int(min(np.searchsorted(cum, s, side="right") - 1, len(seg) - 1))
        t = (s - cum[i]) / max(seg[i], 1e-9)
        out.append(pts[i] * (1 - t) + pts[i + 1] * t)
    return out


def curve_on(sdf, pts, direction=(0, -1, 0), lift=0.0):
    """Proietta punti (interni alla forma) sulla superficie lungo 'direction'."""
    d = norm(direction)
    out = []
    for q in pts:
        p, n = project(sdf, np.asarray(q, float), d)
        out.append(np.asarray(p, float) + np.asarray(n, float) * lift)
    return out


def grin_sdf(cx, cz, w, depth, curve, tilt=0.0, y_max=-0.2, power=0.75):
    """Bocca a mezzaluna nel piano XZ (estrusa lungo Y, solo per y < y_max); curve<0 = broncio."""
    def f(p):
        x = (p[:, 0] - cx) / w
        up = cz + curve * x * x + tilt * x
        lo = up - depth * np.clip(1.0 - x * x, 0.0, None) ** power
        d = np.maximum(np.maximum(p[:, 2] - up, lo - p[:, 2]), (np.abs(x) - 1.0) * w)
        return np.maximum(d, p[:, 1] - y_max)

    pad = abs(curve) + abs(tilt) + depth + 0.05
    return SDF(f, (cx - w, -6.0, cz - pad), (cx + w, y_max, cz + pad))


def brow(surf, y_in, pts_xz, r=0.045, lift=0.0):
    """Sopracciglio spesso e affusolato (punti dal lato interno a quello esterno, nel piano XZ)."""
    pts = curve_on(surf, [(x, y_in, z) for x, z in pts_xz], lift=lift)
    pts = resample(pts, 0.04)
    n = len(pts)
    radii = [r * (0.72 + 0.28 * math.sin(math.pi * min(i / (n - 1) * 1.6, 1.0))) * (1.0 - 0.45 * (i / (n - 1)) ** 2)
             for i in range(n)]
    return tube([tuple(p) for p in pts], radii)


def lid_parts(frame, a, b, c, cut, slope=0.0, t=0.02, lash_r=0.02):
    """Palpebra superiore pesante e linea scura del bordo (coordinate locali dell'occhio)."""
    A, B, C = a + t, b + t, c + t
    plane = SDF(lambda p: (cut + slope * p[:, 0] - p[:, 2]) / math.sqrt(1 + slope * slope), (-A, -B, -C), (A, B, C))
    lid = ellipsoid((A, B, C)).intersect(plane)
    pts = []
    for x in np.linspace(-A * 0.98, A * 0.98, 15):
        z = cut + slope * x
        q = 1 - (x / A) ** 2 - (z / C) ** 2
        if q > 0.01:
            pts.append((x, -B * math.sqrt(q), z))
    return frame.place(lid), frame.place(tube(pts, lash_r))


# ============================================================ colori
WAFFLE = (226, 154, 72)
WAFFLE_DARK = (138, 72, 28)
PISTACHIO = (124, 194, 70)
STRAWBERRY = (255, 96, 142)
CHOCO = (112, 58, 34)
CREAM = (255, 251, 242)
FLAG = (232, 30, 44)
EYE = (36, 16, 20)
WHITE = (255, 255, 255)
SPRINKLE_A = (255, 214, 30)
SPRINKLE_B = (50, 160, 255)

m = Model("GelatoneMontagnone", "pet")

# ------------------------------------------------------------------ cono di cialda bicolore con griglia incisa
CZ0, CZ1, CR0, CR1 = 0.32, 1.36, 0.4, 0.84
cone = capped_cone((0, 0, CZ0), (0, 0, CZ1), CR0, CR1, round=0.09)
NG, HG, DEPTH, HALF_W = 12, 0.3, 0.05, 0.024


def grooves_f(p):
    r = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2) + 1e-6
    th = np.arctan2(p[:, 1], p[:, 0])
    a = th * NG / (2 * math.pi)
    b = p[:, 2] / HG
    gu = np.sqrt((NG / (2 * math.pi * r)) ** 2 + (1 / HG) ** 2)
    du = np.abs((a + b) - np.round(a + b)) / gu
    dv = np.abs((a - b) - np.round(a - b)) / gu
    g = np.minimum(du, dv) - HALF_W
    g = np.maximum(g, p[:, 2] - (CZ1 - 0.06))  # niente solchi sul bordo
    return np.maximum(g, -(cone(p) + DEPTH))


grooves = SDF(grooves_f, cone.lo, cone.hi)
rim = torus(CR1 - 0.03, 0.085, (0, 0, CZ1))
LEGS = [(sx * 0.24, -0.04) for sx in (1, -1)]
legs = union(*[capsule((x, y, 0.5), (x * 1.1, y - 0.04, 0.18), 0.14) for x, y in LEGS])
m.add("Cone", union(cone.subtract(grooves), rim), WAFFLE, tris=6500, voxel=0.016)
m.add("ConeDark", cone.offset(-0.026), WAFFLE_DARK, role="detail", tris=800, voxel=0.022)


def r_cone(z):
    return CR0 + (CR1 - CR0) * (z - CZ0) / (CZ1 - CZ0)


# ------------------------------------------------------------------ tre palline a forma di vetta
PC = (0, -0.04, 1.7)
pist_ball = ellipsoid((0.98, 0.96, 0.7), PC)
pist_lip = torus(0.9, 0.11, (0, -0.02, 1.32))
pist_drips = []
for i, a in enumerate(np.linspace(0, 2 * math.pi, 11)[:-1] + 0.2):
    L = (0.12, 0.26, 0.16, 0.32, 0.1, 0.22, 0.14, 0.3, 0.18, 0.12)[i]
    z0, z1 = 1.3, 1.3 - L
    p0 = (math.cos(a) * (r_cone(z0) + 0.06), math.sin(a) * (r_cone(z0) + 0.06), z0)
    p1 = (math.cos(a) * (r_cone(z1) + 0.04), math.sin(a) * (r_cone(z1) + 0.04), z1)
    pist_drips.append(round_cone(p0, p1, 0.1, 0.075))
pistachio = union(union(pist_ball, pist_lip, k=0.1), *pist_drips, k=0.06)

SC = (0, 0.06, 2.34)
straw = union(ellipsoid((0.74, 0.72, 0.5), SC), torus(0.68, 0.09, (0, 0.05, 2.06)), k=0.1)
straw_drips = [round_cone((math.cos(a) * 0.7, 0.05 + math.sin(a) * 0.7, 2.06), (math.cos(a) * 0.78, 0.05 + math.sin(a) * 0.76, 2.06 - L),
                          0.085, 0.065) for a, L in ((0.3, 0.16), (2.6, 0.2), (3.4, 0.12), (6.0, 0.18))]
strawberry = union(straw, *straw_drips, k=0.05)

CC = (0, 0.12, 2.78)
choco_ball = union(ellipsoid((0.52, 0.5, 0.4), CC), round_cone((0, 0.12, 2.78), (0, 0.14, 3.2), 0.4, 0.12), k=0.15)
chocolate_scoop = union(choco_ball, torus(0.48, 0.075, (0, 0.11, 2.54)), k=0.08)

# panna come neve sulla vetta, con colate e ciuffo a spirale
cap_region = SDF(lambda p: (3.02 - 0.12 * np.maximum(np.sin(5 * np.arctan2(p[:, 1] - 0.12, p[:, 0]) + 0.6), 0) ** 2) - p[:, 2],
                 (-1, -1, 2.68), (1, 1, 3.6))
snow = chocolate_scoop.offset(0.035).intersect(cap_region)
swirl = union(*[torus(0.16 - 0.035 * i, 0.06 - 0.008 * i, (0.0, 0.13, 3.18 + 0.07 * i)) for i in range(3)],
              round_cone((0, 0.13, 3.3), (0.02, 0.13, 3.42), 0.06, 0.015), k=0.04)
pole = cylinder((0.02, 0.13, 3.28), (0.02, 0.13, 3.74), 0.018)

# ------------------------------------------------------------------ faccia brontolona sulla pallina davanti
face_surf = pistachio
EA, EB, EC = 0.15, 0.09, 0.17
frames = [Frame(pist_ball, PC, (0.36 * sx, -1.0, 0.22), sink=0.04) for sx in (1, -1)]
eyes, lids, lashes, shines = [], [], [], []
for f, sx in zip(frames, (1, -1)):
    eyes.append(f.place(ellipsoid((EA, EB, EC))))
    lid, lash = lid_parts(f, EA, EB, EC, cut=0.05, slope=-sx * 0.13)
    lids.append(lid)
    lashes.append(lash)
    shines.append(f.place(sphere(0.03), (-0.04, -0.075, -0.06)))
    shines.append(f.place(sphere(0.014), (0.045, -0.068, -0.11)))
brows = [brow(face_surf, PC[1], [(sx * 0.07, 2.08), (sx * 0.2, 2.11), (sx * 0.34, 2.14), (sx * 0.47, 2.15)], r=0.05)
         for sx in (1, -1)]
crease = brow(face_surf, PC[1], [(0.0, 1.99), (0.0, 2.04), (0.01, 2.09)], r=0.02)

MOUTH = dict(cx=0.0, cz=1.62, w=0.33, depth=0.1, curve=-0.11, tilt=0.02)
mouth_surf = pistachio.offset(0.016)
mouth = mouth_surf.intersect(grin_sdf(**MOUTH, y_max=-0.5))
fangs = []
for x, L, r in ((-0.5, 0.15, 0.04), (0.5, 0.14, 0.038), (-0.14, 0.07, 0.024), (0.16, 0.075, 0.024)):  # morso inverso
    up = MOUTH["cz"] + MOUTH["curve"] * x * x + MOUTH["tilt"] * x
    lo = up - MOUTH["depth"] * (1 - x * x) ** 0.75
    X = MOUTH["cx"] + x * MOUTH["w"]
    base, tip = curve_on(mouth_surf, [(X, PC[1], lo - 0.012), (X + 0.01 * np.sign(x), PC[1], lo + L)], lift=0.008)
    fangs.append(round_cone(tuple(base), tuple(tip), r, 0.006))
# bava di panna che cola da un angolo della bocca
drool_pts = curve_on(pistachio, [(0.3 + 0.025 * math.sin(i * 1.3), PC[1], z) for i, z in enumerate(np.linspace(1.56, 1.25, 9))],
                     lift=0.03)
drool = union(tube([tuple(q) for q in drool_pts], [0.045, 0.042, 0.046, 0.05, 0.048, 0.052, 0.055, 0.058, 0.06]),
              sphere(0.085, tuple(drool_pts[-1] + np.array([0, -0.015, -0.05]))), k=0.04)

# ------------------------------------------------------------------ braccia conserte di cioccolato e piedini
arm_r = tube(bezier((0.55, -0.12, 0.9), (0.46, -0.6, 0.8), (0.0, -0.69, 0.74), (-0.36, -0.57, 0.77), 12),
             [0.11] * 9 + [0.105, 0.1, 0.1, 0.1])
arm_l = tube(bezier((-0.55, -0.12, 0.82), (-0.46, -0.64, 0.68), (0.0, -0.72, 0.62), (0.36, -0.57, 0.66), 12),
             [0.11] * 9 + [0.105, 0.1, 0.1, 0.1])
hands = union(sphere(0.125, (-0.37, -0.56, 0.77)), sphere(0.125, (0.37, -0.56, 0.66)))
feet = union(*[ellipsoid((0.17, 0.24, 0.12), (x * 1.12, y - 0.12, 0.12)) for x, y in LEGS])

# ------------------------------------------------------------------ zuccherini colorati (non sulla faccia)
rng = np.random.default_rng(11)
spr = {"A": [], "B": []}
for i in range(70):
    which = rng.random()
    if which < 0.45:
        c, ball = SC, straw
    elif which < 0.75:
        c, ball = CC, choco_ball
    else:
        c, ball = PC, pist_ball
    d = norm((rng.normal(), rng.normal(), abs(rng.normal()) + 0.25))
    p, n = project(ball, c, d)
    if ball is pist_ball and (p[1] < -0.3 or p[2] < 1.85):
        continue  # niente zuccherini sulla faccia
    if ball is choco_ball and p[2] > 2.95:
        continue  # sotto la panna
    t = norm(np.cross(n, norm(rng.normal(size=3))))
    piece = capsule(tuple(p + n * 0.01 - t * 0.045), tuple(p + n * 0.01 + t * 0.045), 0.024)
    key = "A" if rng.random() < 0.5 else "B"
    if len(spr[key]) < 14:
        spr[key].append(piece)

m.add("Pistachio", union(pistachio, *lids), PISTACHIO, role="detail", tris=2000, voxel=0.016)
m.add("Strawberry", strawberry, STRAWBERRY, role="detail", tris=1300, voxel=0.018)
m.add("Chocolate", union(chocolate_scoop, arm_r, arm_l, hands, legs, feet), CHOCO, role="detail", tris=1600, voxel=0.016)
m.add("Cream", union(snow, swirl, pole, drool), CREAM, role="detail", tris=1100, voxel=0.014)
flag = prism([(0.0, 0.0), (0.3, -0.06), (0.0, -0.15)], -0.012, 0.012, round=0.01).rot(90, 0, 0).translate((0.035, 0.13, 3.74))
m.add("Flag", flag, FLAG, role="detail", tris=200, voxel=0.01)
m.add("Eyes", union(*eyes, *lashes, *brows, crease, mouth), EYE, role="eye", tris=900, voxel=0.011)
m.add("Shine", union(*shines, *fangs), WHITE, role="shine", tris=400, voxel=0.009)
m.add("SprinklesA", fast_union(spr["A"]), SPRINKLE_A, material="Neon", role="glow", tris=450, voxel=0.012)
m.add("SprinklesB", fast_union(spr["B"]), SPRINKLE_B, material="Neon", role="glow", tris=450, voxel=0.012)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
