"""Riccio (Hedgehog) - pet Non comune."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, ellipsoid, project, project_curve, round_cone, sphere, stick,  # noqa: E402
                     tube, union)
from lib.toy import Model  # noqa: E402

BROWN = (160, 110, 74)
SPIKE = (110, 70, 46)
SPIKE_TIP = (240, 214, 174)
CREAM = (255, 234, 204)
PAW = (234, 170, 146)
NOSE = (26, 22, 26)
EYE = (30, 20, 26)
WHITE = (255, 255, 255)
BLUSH = (255, 134, 150)
DARK = (96, 56, 40)
APPLE = (228, 38, 50)
LEAF = (112, 196, 72)

m = Model("Hedgehog", "pet")

# ------------------------------------------------------------------ corpo tondo con musetto a punta
HEAD_C = (0, -0.12, 1.78)
body = ellipsoid((0.88, 0.92, 0.84), (0, 0.12, 0.86))
head = ellipsoid((0.82, 0.76, 0.72), HEAD_C)
snout = round_cone((0, -0.62, 1.6), (0, -0.98, 1.53), 0.28, 0.1)
core = union(body, head, k=0.4)
core = union(core, snout, k=0.15)
m.add("Body", core, BROWN, tris=2000)
# vernice del muso piu' spessa: il corpo (quasi tutto coperto dagli aculei) e' a bassa risoluzione
painted = core.offset(0.03)


def paint(region, t=0.03, depth=0.08):
    """Vernice sottile che segue la superficie (solo uno strato vicino alla pelle)."""
    return core.offset(t).intersect(region).subtract(core.offset(-depth))


# ------------------------------------------------------------------ aculei fitti a file (dalla fronte alla coda)
def fast_union(shapes, pad=0.06):
    """Unione semplice di molte forme piccole: ognuna viene valutata solo vicino al suo ingombro."""
    los = [sh.lo - pad for sh in shapes]
    his = [sh.hi + pad for sh in shapes]

    def f(p):
        d = np.ones(len(p), dtype=np.float32)
        for sh, lo, hi in zip(shapes, los, his):
            msk = np.all((p >= lo) & (p <= hi), axis=1)
            if msk.any():
                d[msk] = np.minimum(d[msk], sh(p[msk]))
        return d

    return SDF(f, np.min(los, axis=0), np.max(his, axis=0))


C = (0.0, 0.05, 1.3)


def hood_dir(alpha, beta):
    """alpha: angolo dall'asse +X (90 = linea mediana); beta: da davanti (0) a sopra (90) a dietro (180)."""
    a, b = math.radians(alpha), math.radians(beta)
    return (math.cos(a), -math.sin(a) * math.cos(b), math.sin(a) * math.sin(b))


APPLE_AB = (62, 118)
spikes, tips = [], []
for row, beta in enumerate(range(50, 243, 20)):
    for alpha in np.arange(20 + (11 if row % 2 else 0), 161, 22):
        if beta < 50 + 22 * (abs(alpha - 90) / 70) ** 2:
            continue  # il muso resta libero, incorniciato dagli aculei
        p, n = project(core, C, hood_dir(alpha, beta))
        if p[2] < 0.42:
            continue  # niente aculei sotto la pancia
        d = n + np.array((0.0, 0.55, 0.1))
        d /= np.linalg.norm(d)
        tip = p + d * (0.22 + 0.1 * min(1.0, (beta - 50) / 70))
        spikes.append(round_cone(p - n * 0.08, tip, 0.21, 0.075))
        tips.append(sphere(0.1, tip + d * 0.035))
spike_sdf = fast_union(spikes).subtract(core.offset(-0.05))  # via le basi nascoste dentro il corpo
m.add("Spikes", spike_sdf, SPIKE, role="detail", tris=7200, voxel=0.033)
m.add("SpikeTips", spike_sdf.offset(0.012).intersect(fast_union(tips)), SPIKE_TIP, role="detail", tris=2000,
      voxel=0.03)

# ------------------------------------------------------------------ musetto e pancia color crema, zampette rosa
face_region = union(ellipsoid((0.62, 0.6, 0.52), (0, -0.66, 1.66)), ellipsoid((0.56, 0.55, 0.56), (0, -0.62, 0.84)),
                    k=0.2)
m.add("Cream", paint(face_region), CREAM, role="detail", tris=1400, voxel=0.025)
paws = union(*[ellipsoid((0.17, 0.24, 0.12), (sx * 0.34, -0.38, 0.12)) for sx in (1, -1)],
             *[ellipsoid((0.14, 0.13, 0.17), (sx * 0.44, -0.62, 0.98)) for sx in (1, -1)])
m.add("Paws", paws, PAW, role="detail", tris=450, voxel=0.016)

# ------------------------------------------------------------------ faccia
eye_shape = ellipsoid((0.14, 0.085, 0.19))
eye_frames = [Frame(painted, HEAD_C, (0.42 * sx, -1.0, 0.14), sink=0.045) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in eye_frames]), EYE, role="eye", tris=700, voxel=0.013)
shines = []
for f in eye_frames:
    shines.append(f.place(sphere(0.055), (-0.048, -0.07, 0.07)))
    shines.append(f.place(sphere(0.028), (0.052, -0.066, -0.08)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=350, voxel=0.01)

m.add("Nose", sphere(0.105, (0, -1.07, 1.545)), NOSE, role="detail", tris=350, voxel=0.012, reflectance=0.15)

blush = ellipsoid((0.13, 0.035, 0.08))
m.add("Blush", union(*[stick(blush, painted, HEAD_C, (0.66 * sx, -0.85, -0.3), sink=0.015) for sx in (1, -1)]),
      BLUSH, role="detail", tris=300, voxel=0.013)

smile = project_curve(painted, bezier((-0.12, -1.0, 1.42), (-0.06, -1.0, 1.37), (0.06, -1.0, 1.37),
                                      (0.12, -1.0, 1.42), 12), (0, -1, 0), inset=0.008)

# ------------------------------------------------------------------ mela infilzata sugli aculei
pa, na = project(core, C, hood_dir(*APPLE_AB))
AC = pa + na * 0.4
apple = ellipsoid((0.25, 0.25, 0.22), AC).subtract(sphere(0.07, AC + (0, 0, 0.24)), k=0.06)
apple = apple.subtract(sphere(0.05, AC - (0, 0, 0.24)), k=0.05)
m.add("Apple", apple, APPLE, role="detail", tris=600, voxel=0.016, reflectance=0.06)
stem_pts = bezier(AC + (0, 0, 0.12), AC + (0.0, 0.0, 0.25), AC + (0.03, 0.02, 0.3), AC + (0.07, 0.03, 0.33), 8)
leaf = ellipsoid((0.11, 0.025, 0.055), (-0.1, 0, 0)).rot(0, 25, 0).rot(0, 0, 30).translate(stem_pts[4])
m.add("Leaf", leaf, LEAF, role="detail", tris=250, voxel=0.01)
m.add("Mouth", union(tube(smile, 0.02), tube(stem_pts, [0.03] * 3 + [0.026] * 3 + [0.022] * 3)), DARK,
      role="detail", tris=300, voxel=0.01)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
