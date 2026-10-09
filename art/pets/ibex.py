"""Stambecco (Ibex) - pet Raro: cucciolo di stambecco con grandi corna ricurve a anelli."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (Frame, bezier, capped_cone, capsule, ellipsoid, project, project_curve,  # noqa: E402
                     rot_matrix, round_cone, sphere, stick, torus, tube, union)
from lib.toy import Model  # noqa: E402

FUR = (182, 146, 112)
CREAM = (250, 236, 210)
STRIPE = (104, 78, 62)
HOOF = (64, 56, 58)
HORN = (230, 198, 142)
NOSE = (70, 50, 48)
EYE = (30, 22, 28)
WHITE = (255, 255, 255)
BLUSH = (255, 128, 140)

m = Model("Ibex", "pet")


def ring(c, d, R, r):
    """Toro di raggio R (sezione r) centrato in c, con l'asse lungo la direzione d."""
    d = np.asarray(d, dtype=np.float64)
    d = d / np.linalg.norm(d)
    z = np.array([0.0, 0.0, 1.0])
    ax = np.cross(z, d)
    s = float(np.linalg.norm(ax))
    t = torus(R, r)
    if s > 1e-6:
        t = t.rotate(rot_matrix(ax, math.degrees(math.atan2(s, float(z @ d)))))
    return t.translate(c)


# ---------------------------------------------------------------- corpo
HEAD_C = (0, -0.62, 2.08)
head = ellipsoid((0.79, 0.71, 0.69), HEAD_C)
SNOUT_C = (0, -1.18, 1.85)
snout = ellipsoid((0.38, 0.3, 0.28), SNOUT_C)
head_full = union(head, snout, k=0.16)
body = ellipsoid((0.66, 0.82, 0.58), (0, 0.24, 1.0))
neck = capsule((0, -0.28, 1.28), (0, -0.5, 1.74), 0.32)
torso = union(body, neck, k=0.2)
LEGS = [(sx * 0.36, y) for sx in (1, -1) for y in (-0.3, 0.74)]
legs = union(*[round_cone((x, y, 0.92), (x * 1.04, y, 0.24), 0.22, 0.18) for x, y in LEGS])
EAR_C = [(sx * 0.81, -0.5, 2.14) for sx in (1, -1)]
ears = union(*[ellipsoid((0.3, 0.115, 0.13)).rot(0, sx * 18, -sx * 22).translate(c) for sx, c in zip((1, -1), EAR_C)])
core_np = union(torso, head_full, k=0.3)
bp, _ = project(core_np, (0, -1.12, 1.8), (0, -0.25, -1))
beard = tube(bezier(tuple(bp + [0, 0.03, 0.06]), tuple(bp + [0, -0.03, -0.06]), tuple(bp + [0, -0.06, -0.14]),
                    tuple(bp + [0, -0.12, -0.2]), 6), [0.085, 0.085, 0.08, 0.07, 0.058, 0.045, 0.032])
core = union(union(core_np, legs, k=0.12), ears, beard, k=0.05)
m.add("Body", core, FUR, tris=5700)

# pancia, petto e muso color crema + interno delle orecchie
PK = 0.012  # bordo morbido delle "vernici": spigolo pulito dopo marching cubes e decimazione
belly = torso.offset(0.022).intersect(union(ellipsoid((0.52, 0.8, 0.36), (0, 0.16, 0.46)),
                                            ellipsoid((0.42, 0.4, 0.5), (0, -0.62, 1.08)), k=0.2), k=PK)
muzzle = core_np.offset(0.022).intersect(ellipsoid((0.46, 0.34, 0.34), (0, -1.42, 1.83)), k=PK)
inner_ears = ears.offset(0.022).intersect(union(*[ellipsoid((0.2, 0.17, 0.075)).translate((sx * 0.03, -0.16, 0))
                                                  .rot(0, sx * 18, -sx * 22).translate(c) for sx, c in zip((1, -1), EAR_C)]),
                                           k=PK)
m.add("Belly", union(belly, muzzle, inner_ears), CREAM, role="detail", tris=1900, voxel=0.02)

# striscia scura sulla schiena (dalla nuca alla coda) e codina
spine = []
for y in np.linspace(-0.12, 1.0, 12):
    p, _ = project(core_np, (0, float(y), 1.0), (0, 0, 1))
    spine.append(tuple(p))
stripe = core.offset(0.022).intersect(tube(spine, 0.17), k=PK)
tail = round_cone((0, 1.0, 1.32), (0, 1.22, 1.58), 0.13, 0.08)
m.add("Markings", union(stripe, tail), STRIPE, role="detail", tris=1300)

# zoccoli scuri
hooves = union(*[capped_cone((x * 1.04, y, 0.0), (x * 1.04, y, 0.26), 0.235, 0.2, round=0.06) for x, y in LEGS])
m.add("Hooves", hooves, HOOF, role="detail", tris=1000)

# grandi corna ricurve all'indietro con anelli in rilievo
horn_parts = []
for sx in (1, -1):
    n = 24
    pts = bezier((sx * 0.24, -0.66, 2.5), (sx * 0.3, -0.74, 3.1), (sx * 0.5, -0.06, 3.34), (sx * 0.6, 0.38, 2.98), n)
    radii = [0.2 - 0.13 * i / n for i in range(n + 1)]
    rings = []
    for i in range(4, n - 1, 2):  # un anello ogni ~0.13 unita'
        d = np.subtract(pts[i + 1], pts[i - 1])
        rings.append(ring(pts[i], d, radii[i] - 0.012, 0.032))
    horn_parts.append(union(tube(pts, radii), *rings, k=0.022))
m.add("Horns", union(*horn_parts), HORN, role="detail", tris=3000, voxel=0.012)

# naso e sorriso
painted = core_np.offset(0.022)  # superficie della vernice crema del muso
nose = Frame(painted, SNOUT_C, (0, -1.0, 0.55), sink=0.025).place(
    union(ellipsoid((0.09, 0.06, 0.05)), ellipsoid((0.045, 0.045, 0.045), (0, 0, -0.03)), k=0.04))
mouth = tube(project_curve(painted, bezier((0.13, -1.5, 1.76), (0.05, -1.5, 1.7), (-0.05, -1.5, 1.7),
                                           (-0.13, -1.5, 1.76), 12), (0, -1, 0), inset=0.006), 0.025)
m.add("Nose", union(nose, mouth), NOSE, role="detail", tris=700, voxel=0.012)

# occhioni lucidi, riflessi e guance
eye_shape = ellipsoid((0.16, 0.095, 0.2))
frames = [Frame(core_np, HEAD_C, (0.48 * sx, -1.0, 0.16), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in frames]), EYE, role="eye", tris=900, voxel=0.014)
shines = []
for f in frames:
    shines.append(f.place(sphere(0.062), (-0.053, -0.08, 0.08)))
    shines.append(f.place(sphere(0.032), (0.058, -0.074, -0.09)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=450, voxel=0.01)
blush = ellipsoid((0.14, 0.04, 0.085))
m.add("Blush", union(*[stick(blush, core_np, HEAD_C, (sx * 0.8, -0.85, -0.32), sink=0.018) for sx in (1, -1)]),
      BLUSH, role="detail", tris=450, voxel=0.013)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
