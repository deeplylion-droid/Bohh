"""Mozzarella Ninjella - pet Segreto (creatura meme originale).

Una mozzarella giocattolo (palla lucida con il "nodino" in cima e una fogliolina di basilico)
travestita da ninja: maschera nera cucita con la fessura per gli occhi, fascia rossa con le code al
vento, stivaletti neri, polsini fasciati e uno shuriken d'acciaio sulla schiena.
Carattere: il sornione - occhi stretti nella fessura che guardano di lato e un sorrisetto storto con
un solo canino.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, capsule, cylinder, ellipsoid, prism, project, round_cone, sphere,  # noqa: E402
                     star_points, tube, union, bezier)
from lib.toy import Model  # noqa: E402

MOZZA = (250, 248, 238)
MASK = (30, 28, 40)
RED = (214, 34, 48)
BASIL = (54, 150, 64)
BASIL_DARK = (30, 104, 44)
STEEL = (196, 204, 216)
PUPIL = (22, 16, 30)
MOUTH = (60, 14, 28)
TOOTH = (255, 252, 242)
BLUSH = (255, 128, 150)
THREAD = (226, 40, 56)

m = Model("MozzarellaNinjella", "pet")


# ---------------------------------------------------------------- helper locali
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


def grin_edges(u, a, h, curve, skew):
    t = np.clip(u / a, -1.0, 1.0)
    top = curve * t * t + skew * t
    bot = top - h * np.power(np.clip(1.0 - t * t, 0.0, 1.0), 0.7)
    return top, bot


def stitches(base, pts, n, dash, r, lift=0.02):
    """Trattini di cucitura perpendicolari alla linea pts, appoggiati sulla superficie."""
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
        d = np.cross(nrm, tan)
        d /= np.linalg.norm(d)
        c = p + nrm * lift
        out.append(capsule(c - d * dash * 0.5, c + d * dash * 0.5, r))
    return union(*out)


def shell(core, outer, inner):
    """Strato di "vernice" che segue la superficie (guscio sottile, niente interno pieno)."""
    return core.offset(outer).subtract(core.offset(-inner))


# ---------------------------------------------------------------- corpo: palla di mozzarella col nodino
HC = (0.0, 0.0, 1.12)
ball = ellipsoid((1.0, 0.94, 0.96), HC)
knot = union(round_cone((0.0, 0.06, 1.95), (0.04, 0.12, 2.32), 0.24, 0.07),
             sphere(0.09, (0.05, 0.14, 2.33)), k=0.06)
legs = union(*[capsule((sx * 0.36, -0.02, 0.42), (sx * 0.38, -0.08, 0.2), 0.16) for sx in (1, -1)])
# braccia corte: destra a pugno avanti, sinistra alzata nel "segno" ninja davanti al petto
HAND_R = (0.98, -0.52, 0.86)
HAND_L = (-1.04, -0.3, 0.82)
arms = union(capsule((0.78, -0.2, 1.08), HAND_R, 0.12),
             capsule((-0.8, -0.16, 1.06), HAND_L, 0.12), k=0.05)
core = union(ball, knot, k=0.1)
core = union(core, legs, arms, k=0.06)
fists = union(sphere(0.16, HAND_R), sphere(0.15, HAND_L), k=0.04)
body = union(core, fists, k=0.03)
m.add("Body", body, MOZZA, reflectance=0.06, tris=5200, voxel=0.02)

# ---------------------------------------------------------------- maschera nera con fessura per gli occhi
MASK_LO, MASK_HI = 1.18, 1.72
SLIT_LO, SLIT_HI = 1.33, 1.55


def mask_region(p):
    z = p[:, 2]
    band = np.maximum(MASK_LO - z, z - MASK_HI)
    # fessura davanti (y < 0), larga e un po' inclinata: lo sguardo sornione
    tilt = 0.06 * p[:, 0]
    in_slit = np.maximum(np.maximum((SLIT_LO + tilt) - z, z - (SLIT_HI + tilt)), np.maximum(np.abs(p[:, 0]) - 0.66, p[:, 1] + 0.25))
    return np.maximum(band, -in_slit)


mask_sdf = SDF(mask_region, (-1.2, -1.2, MASK_LO - 0.1), (1.2, 1.2, MASK_HI + 0.1))
mask = shell(ball, 0.035, 0.06).intersect(mask_sdf, k=0.01)
# nodo della fascia dietro la testa
mask_knot = union(ellipsoid((0.17, 0.12, 0.15), (0.0, 0.95, 1.46)), ellipsoid((0.13, 0.1, 0.11), (0.14, 0.97, 1.42)),
                  ellipsoid((0.13, 0.1, 0.11), (-0.14, 0.97, 1.42)), k=0.04)
m.add("Mask", mask, MASK, material="Fabric", role="detail", tris=3000, voxel=0.014)

# code della fascia rossa al vento
tails = []
for sx, lift in ((1, 0.0), (-1, -0.1)):
    pts = bezier((sx * 0.08, 1.0, 1.44), (sx * 0.45, 1.45, 1.3 + lift), (sx * 0.62, 1.75, 0.92 + lift), (sx * 0.9, 1.95, 1.08 + lift), 14)
    tails.append(tube(pts, [0.11 - 0.0045 * i for i in range(15)]))
m.add("Headband", union(mask_knot.offset(0.01), *tails, k=0.03), RED, material="Fabric", role="detail", tris=1800, voxel=0.014)

# ---------------------------------------------------------------- occhi stretti che guardano di lato
FACE = (0.0, 0.0, 1.45)
eyes, pupils, shines = [], [], []
for sx in (1, -1):
    f = Frame(ball, FACE, (0.34 * sx, -1.0, 0.0), sink=0.02)
    # occhio a mandorla, scuro, con la palpebra superiore dritta (sguardo sornione)
    almond = ellipsoid((0.16, 0.06, 0.09)).intersect(SDF(lambda p: p[:, 2] - 0.035, (-0.2, -0.2, -0.1), (0.2, 0.2, 0.05)))
    eyes.append(f.place(almond.rot(0, -10 * sx, 0)))
    shines.append(f.place(sphere(0.026), (0.05 * sx, -0.065, 0.0)))
    shines.append(f.place(sphere(0.013), (-0.04 * sx, -0.06, -0.035)))
m.add("Eyes", union(*eyes), PUPIL, role="eye", tris=500, voxel=0.009)
m.add("Shine", union(*shines), (255, 255, 255), role="shine", tris=200, voxel=0.006)

# sopracciglia rosse cucite sulla maschera sopra la fessura (una piu' alta: aria da sbruffona)
brows = []
for sx, raise_ in ((1, 0.07), (-1, -0.01)):
    pts = []
    for x, z in ((0.14, -0.035 + raise_ * 0.3), (0.31, 0.0 + raise_ * 0.6), (0.48, 0.03 + raise_)):
        p, _ = on_surf(ball, FACE, (sx * x, -1.0, SLIT_HI + 0.08 + z))
        pts.append(p + normal_at(ball, p) * 0.04)
    brows.append(tube(pts, [0.034, 0.04, 0.03]))

# cuciture rosse lungo il bordo inferiore della maschera
edge = []
for i in range(15):
    a = math.radians(-150 + i * 120 / 14)
    p, _ = on_surf(ball, (0.0, 0.0, MASK_LO + 0.03), (math.cos(a), math.sin(a), MASK_LO + 0.03))
    edge.append(p)
m.add("Thread", union(*brows, stitches(ball, edge, 12, 0.07, 0.014, lift=0.04)), THREAD, role="detail", tris=900, voxel=0.008)

# ---------------------------------------------------------------- sorrisetto storto con un canino
MOUTH_F = Frame(ball, (0.0, 0.0, 1.0), (0.12, -1.0, 0.0))
GA, GH, GC, GS = 0.27, 0.13, 0.06, 0.07


def mouth_fn(x, z):
    top, bot = grin_edges(-x, GA, GH, GC, GS)
    return np.maximum(np.maximum(z - top, bot - z), np.abs(x) - GA) * 0.8


m.add("Mouth", shell(ball, 0.014, 0.05).intersect(MOUTH_F.place(stencil(mouth_fn, (-0.26, 0.26), (-0.2, 0.2), 0.4))),
      MOUTH, role="eye", tris=350, voxel=0.008)
top, _ = grin_edges(-0.15, GA, GH, GC, GS)
pa, na = on_surf(ball, (0.0, 0.0, 1.0), MOUTH_F.point((0.15, 0.0, top - 0.004)))
pb, nb = on_surf(ball, (0.0, 0.0, 1.0), MOUTH_F.point((0.15, 0.0, top - 0.11)))
fang = round_cone(pa + na * 0.018, pb + nb * 0.018, 0.038, 0.007)
m.add("Fang", fang, TOOTH, role="shine", tris=150, voxel=0.006)
m.add("Blush", union(*[Frame(ball, (0.0, 0.0, 1.05), (0.6 * sx, -1.0, 0.0), sink=0.012).place(ellipsoid((0.11, 0.035, 0.06)))
                       for sx in (1, -1)]), BLUSH, role="detail", tris=250, voxel=0.01)

# ---------------------------------------------------------------- basilico, stivaletti, polsini, shuriken
stem = capsule((0.05, 0.14, 2.36), (0.06, 0.12, 2.52), 0.03)
leaf_a = ellipsoid((0.3, 0.16, 0.04)).rot(0, -38, 20).translate((0.27, 0.1, 2.62))
leaf_b = ellipsoid((0.26, 0.14, 0.035)).rot(0, 40, -30).translate((-0.16, 0.16, 2.6))
m.add("Basil", union(stem, leaf_a, leaf_b, k=0.03), BASIL, role="detail", tris=800, voxel=0.01)
veins = union(capsule((0.08, 0.12, 2.52), (0.46, 0.06, 2.75), 0.013),
              capsule((0.04, 0.14, 2.52), (-0.36, 0.2, 2.73), 0.012))
m.add("BasilVein", veins, BASIL_DARK, role="detail", tris=200, voxel=0.007)

boots = union(*[union(ellipsoid((0.22, 0.3, 0.15), (sx * 0.38, -0.12, 0.13)),
                      cylinder((sx * 0.38, -0.06, 0.16), (sx * 0.38, -0.06, 0.34), 0.165, round=0.04), k=0.05) for sx in (1, -1)])
wraps = union(*[cylinder(np.asarray(h) + (np.asarray(h) - np.asarray(s)) * -0.38, np.asarray(h) + (np.asarray(h) - np.asarray(s)) * -0.18,
                         0.14, round=0.03) for h, s in ((HAND_R, (0.78, -0.2, 1.08)), (HAND_L, (-0.8, -0.16, 1.06)))])
m.add("Boots", union(boots, wraps), MASK, material="Fabric", role="detail", tris=1600, voxel=0.014)

star = prism(star_points(4, 0.46, 0.15, rot_deg=45), -0.05, 0.05, round=0.02)
star = star.subtract(cylinder((0, 0, -0.2), (0, 0, 0.2), 0.07))
# lo shuriken sta sulla schiena, inclinato
shuriken = star.rot(90, 0, 0).rot(0, 18, 0).translate((0.0, 1.0, 0.98))
m.add("Shuriken", shuriken, STEEL, material="Metal", role="detail", tris=900, voxel=0.01, smooth=False)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
