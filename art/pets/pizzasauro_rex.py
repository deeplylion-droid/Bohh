"""Pizzasauro Rex - pet Divino (creatura meme originale).

Un cucciolo di T-rex fatto di pizza: pelle color crosta dorata, schiena di pomodoro con
fette di salame piccante, mozzarella filante che cola, cresta di foglie di basilico,
braccine minuscole e un gran sorriso con dentini.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capsule, ellipsoid, project, round_cone, smin,  # noqa: E402
                     sphere, tube, union)
from lib.toy import Model  # noqa: E402

CRUST = (240, 172, 78)
DOUGH = (255, 228, 168)
SAUCE = (226, 52, 34)
PEPPERONI = (122, 20, 34)
CHEESE = (255, 250, 232)
BASIL = (56, 172, 64)
MOUTH = (110, 24, 34)
TONGUE = (255, 116, 128)
TOOTH = (255, 252, 240)
EYE = (30, 22, 30)
WHITE = (255, 255, 255)
BLUSH = (255, 112, 120)

m = Model("PizzasauroRex", "pet")


# ---------------------------------------------------------------- helper locali
def seg2(x, z, a, b, r):
    """Distanza 2D da un segmento (a, b) con raggio r, nel piano locale (x, z)."""
    px, pz = x - a[0], z - a[1]
    ex, ez = b[0] - a[0], b[1] - a[1]
    t = np.clip((px * ex + pz * ez) / (ex * ex + ez * ez + 1e-12), 0.0, 1.0)
    dx, dz = px - ex * t, pz - ez * t
    return np.sqrt(dx * dx + dz * dz) - r


def circ2(x, z, c, r):
    return np.sqrt((x - c[0]) ** 2 + (z - c[1]) ** 2) - r


def stencil(fn2d, xr, zr, depth=0.35):
    """Estrude una forma 2D fn2d(x, z) lungo l'asse locale Y (decalcomania da Frame.place)."""
    def f(p):
        return np.maximum(fn2d(p[:, 0], p[:, 2]), np.abs(p[:, 1]) - depth)
    return SDF(f, (xr[0], -depth, zr[0]), (xr[1], depth, zr[1]))


def drip(length, w):
    """Colata verso il basso (locale -Z) che finisce con una goccia tonda."""
    def fn(x, z):
        bar = seg2(x, z, (0, 0.15), (0, -length), w)
        return smin(bar, circ2(x, z, (0, -length - w * 0.25), w * 1.45), 0.07)
    return stencil(fn, (-w * 2.2, w * 2.2), (-length - w * 2.2, 0.3))


def leaf(L, W, T, fold=0.35):
    """Foglia a punta piegata a V lungo la nervatura: asse lungo -Y locale, larghezza su Z, sottile su X."""
    c = W * 0.5
    A = L * 0.577
    t = T / 0.866
    a = ellipsoid((t, A, W), (0, -L * 0.5, c))
    b = ellipsoid((t, A, W), (0, -L * 0.5, -c))
    flat = a.intersect(b)

    def fold_pts(p):
        q = p.copy()
        q[:, 0] = q[:, 0] + fold * np.abs(q[:, 2])
        return q
    return flat.warp(fold_pts, pad=fold * W * 0.6)


def at(base, src, d):
    p, _ = project(base, src, d)
    return p


# ---------------------------------------------------------------- corpo
HEAD_C = (0.0, -0.16, 2.08)
SNOUT_C = (0.0, -0.8, 1.86)
BODY_C = (0.0, 0.12, 1.0)
body = ellipsoid((0.8, 0.74, 0.8), BODY_C)
head = ellipsoid((0.86, 0.8, 0.72), HEAD_C)
snout = ellipsoid((0.64, 0.6, 0.44), SNOUT_C)
jaw = ellipsoid((0.56, 0.5, 0.3), (0.0, -0.74, 1.64))
thighs = union(*[ellipsoid((0.3, 0.36, 0.36), (sx * 0.52, 0.04, 0.52)) for sx in (1, -1)])
feet = union(*[ellipsoid((0.27, 0.38, 0.17), (sx * 0.52, -0.2, 0.17)) for sx in (1, -1)])
TAIL_PTS = bezier((0.0, 0.62, 0.9), (0.05, 1.15, 0.62), (0.32, 1.55, 0.32), (0.72, 1.72, 0.34), 14)
tail = tube(TAIL_PTS, [0.44 - 0.026 * i for i in range(15)])
arms = union(*[union(capsule((sx * 0.48, -0.5, 1.3), (sx * 0.56, -0.78, 1.22), 0.1),
                     sphere(0.115, (sx * 0.57, -0.82, 1.22)), k=0.05) for sx in (1, -1)])
core = union(body, head, k=0.4)
core = union(core, snout, jaw, k=0.22)
core = union(core, thighs, feet, tail, k=0.14)
core = union(core, arms, k=0.07)
_nos = [at(core, SNOUT_C, (sx * 0.3, -1.0, 0.62)) for sx in (1, -1)]
core = core.subtract(union(*[sphere(0.05, p) for p in _nos]), k=0.04)


# pomodoro sulla schiena e sulla testa (regione con bordo ondulato)
def sauce_fn(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    head_cap = (2.66 - 0.62 * (y + 0.9)) - z
    back = np.maximum((1.56 - 0.95 * (y - 0.1)) - z, 0.08 - y)
    d = smin(head_cap, back, 0.1) * 0.75
    ang = np.arctan2(x, y - 0.25)
    return d + 0.026 * np.sin(11.0 * ang) + 0.014 * np.sin(23.0 * ang + 1.3)


# cornicione: la crosta si gonfia in un bordo morbido attorno al pomodoro, come una pizza
_base = core


def _rim(p):
    return _base(p) - 0.06 * np.exp(-((sauce_fn(p) - 0.07) / 0.05) ** 2)


core = SDF(_rim, _base.lo - 0.1, _base.hi + 0.1)
m.add("Body", core, CRUST, tris=5100)

# pancia di impasto chiaro
belly_region = ellipsoid((0.6, 0.7, 0.6), (0.0, -0.6, 0.96))
m.add("Belly", core.offset(0.02).intersect(belly_region), DOUGH, role="detail", tris=800)

sauce = core.offset(0.02).intersect(SDF(sauce_fn, (-5, -5, -5), (5, 5, 5)))
m.add("Sauce", sauce, SAUCE, role="detail", tris=1800)

# mozzarella: fette tonde che si sciolgono sul pomodoro, con una colata grossa oltre il bordo
cheese = []
for src, d, r in [
    (HEAD_C, (-0.5, 0.0, 0.85), 0.25), (HEAD_C, (0.3, -0.5, 0.9), 0.2), (HEAD_C, (0.35, 0.85, 0.45), 0.2),
    (BODY_C, (0.62, 0.62, 0.55), 0.25), (BODY_C, (-0.66, 0.62, 0.4), 0.24), (BODY_C, (0.15, 1.0, -0.1), 0.2),
]:
    cheese.append(sphere(r, at(core, src, d)))
for src, d, L in [
    (HEAD_C, (-0.8, -0.38, 0.55), 0.16), (HEAD_C, (0.72, -0.5, 0.58), 0.13), (HEAD_C, (0.95, 0.4, 0.3), 0.18),
    (BODY_C, (0.92, 0.35, 0.5), 0.2), (BODY_C, (-0.92, 0.35, 0.5), 0.18), (BODY_C, (-0.7, 0.85, -0.05), 0.12),
]:
    cheese.append(Frame(core, src, d).place(drip(L, 0.1), (0, 0, 0.08)))
m.add("Cheese", core.offset(0.034).intersect(union(*cheese, k=0.05)), CHEESE, role="detail", tris=2000)

# fette di salame piccante (dischi rialzati, bordo morbido)
pep = []
for src, d, r in [
    (HEAD_C, (0.55, 0.2, 0.85), 0.17), (HEAD_C, (-0.45, 0.75, 0.5), 0.15),
    (BODY_C, (0.45, 0.88, 0.15), 0.18), (BODY_C, (-0.38, 0.92, 0.62), 0.17), (BODY_C, (0.72, 0.42, 0.75), 0.15),
    (BODY_C, (-0.82, 0.45, -0.05), 0.14),
]:
    pep.append(sphere(r, at(core, src, d)))
pep.append(sphere(0.13, at(core, TAIL_PTS[7], (0.45, 0.25, 1.0))))
pep.append(sphere(0.1, at(core, TAIL_PTS[11], (-0.1, 0.1, 1.0))))
m.add("Pepperoni", core.offset(0.05).intersect(union(*pep), k=0.02), PEPPERONI, role="detail", tris=1000)

# cresta di foglie di basilico lungo la spina dorsale (alternate, inclinate all'indietro)
leaves = []
crest = [
    (HEAD_C, (0.0, -0.45, 1.0), 0.56, 0.38, 14, 14), (HEAD_C, (0.0, 0.12, 1.0), 0.66, 0.44, 20, -14),
    (HEAD_C, (0.0, 0.78, 0.72), 0.6, 0.4, 24, 14), (BODY_C, (0.0, 1.0, 0.85), 0.58, 0.38, 24, -14),
    (BODY_C, (0.0, 1.0, 0.3), 0.54, 0.36, 26, 14), (TAIL_PTS[4], (0.05, 0.3, 1.0), 0.5, 0.33, 24, -14),
    (TAIL_PTS[8], (-0.2, 0.3, 1.0), 0.42, 0.28, 24, 12), (TAIL_PTS[12], (-0.3, 0.2, 1.0), 0.32, 0.22, 24, -10),
]
for src, d, L, W, tilt, yaw in crest:
    f = Frame(core, src, d, sink=0.07)
    leaves.append(f.place(leaf(L, W, 0.04).rot(tilt, 0, 0).rot(0, yaw * 0.6, 0)))
m.add("Basil", union(*leaves), BASIL, role="detail", tris=1800, voxel=0.014)

# ---------------------------------------------------------------- muso
eye_shape = ellipsoid((0.17, 0.1, 0.23))
eye_frames = [Frame(core, HEAD_C, (0.43 * sx, -1.0, 0.34), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in eye_frames]), EYE, role="eye", tris=800, voxel=0.014)
shines = []
for f in eye_frames:
    shines.append(f.place(sphere(0.066), (-0.055, -0.085, 0.085)))
    shines.append(f.place(sphere(0.033), (0.065, -0.08, -0.1)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=500, voxel=0.01)

blush = ellipsoid((0.14, 0.04, 0.085))
m.add("Blush", union(*[Frame(core, HEAD_C, (0.8 * sx, -0.8, -0.06), sink=0.018).place(blush) for sx in (1, -1)]),
      BLUSH, role="detail", tris=400, voxel=0.013)

# bocca aperta a "D" sul muso, con lingua e dentini
mouth_f = Frame(core, SNOUT_C, (0.0, -1.0, -0.38))
MA, MB, MC = 0.44, 0.22, 0.14


def mouth_2d(x, z):
    ell = np.sqrt((x / MA) ** 2 + (z / MB) ** 2) - 1.0
    top = z - MC * (x / MA) ** 2
    return np.maximum(ell * 0.19, top)


mouth = core.offset(0.014).intersect(mouth_f.place(stencil(mouth_2d, (-0.5, 0.5), (-0.3, 0.2), 0.5)))
m.add("Mouth", mouth, MOUTH, role="detail", tris=500, voxel=0.012)
tongue_2d = lambda x, z: np.maximum(circ2(x, z, (0.04, -0.22), 0.15), mouth_2d(x, z))  # noqa: E731
tongue = core.offset(0.024).intersect(mouth_f.place(stencil(tongue_2d, (-0.25, 0.25), (-0.4, 0.0), 0.45)))
m.add("Tongue", tongue, TONGUE, role="detail", tris=300, voxel=0.012)

teeth = []
for tx, sz in ((-0.31, 0.75), (-0.18, 1.0), (-0.06, 0.85), (0.06, 0.85), (0.18, 1.0), (0.31, 0.75)):
    tz = MC * (tx / MA) ** 2 - 0.012
    p, n = project(core, SNOUT_C, mouth_f.point((tx, -0.3, tz)) - np.array(SNOUT_C))
    p2, n2 = project(core, SNOUT_C, mouth_f.point((tx * 0.97, -0.3, tz - 0.085 * sz)) - np.array(SNOUT_C))
    teeth.append(round_cone(p + n * 0.012, p2 + n2 * 0.022, 0.034 * sz, 0.012))
claws = []
for sx in (1, -1):
    for dx in (-0.14, 0.0, 0.14):
        claws.append(round_cone((sx * 0.52 + dx, -0.5, 0.13), (sx * 0.52 + dx * 1.15, -0.64, 0.08), 0.065, 0.025))
    for dz in (0.05, -0.05):
        claws.append(round_cone((sx * 0.58, -0.88, 1.22 + dz), (sx * 0.61, -0.99, 1.2 + dz * 1.4), 0.035, 0.014))
m.add("Teeth", union(*teeth, *claws), TOOTH, role="detail", tris=800, voxel=0.012)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
