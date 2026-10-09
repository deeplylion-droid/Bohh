"""Riccio (Hedgehog) - pet Non comune. Carattere: scontroso (braccia conserte, sopracciglia aggrottate, dentoni)."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, ellipsoid, prism, project, round_cone, sphere, tube,  # noqa: E402
                     union)
from lib.toy import Model  # noqa: E402

BROWN = (128, 78, 52)
SPIKE = (78, 46, 42)
SPIKE_TIP = (238, 212, 170)
CREAM = (250, 226, 188)
PAW = (222, 150, 118)
NOSE = (24, 18, 24)
EYE = (28, 16, 24)
WHITE = (255, 255, 255)
DARK = (56, 30, 26)
MOUTH = (58, 14, 30)
APPLE = (226, 32, 46)
LEAF = (104, 186, 62)

m = Model("Hedgehog", "pet")


# ------------------------------------------------------------------ aiuti
def face_prism(poly, y0, y1, r=0.0):
    """Regione: poligono nel piano XZ (coppie x, z) estruso lungo Y fra y0 e y1."""
    return prism(poly, -y1, -y0, round=r).rot(90, 0, 0)


def above_line(z0, slope, size=1.0):
    """Semispazio z > z0 + slope * x (coordinate locali): taglio delle palpebre."""
    n = math.sqrt(1 + slope * slope)
    return SDF(lambda p: (slope * p[:, 0] - p[:, 2] + z0) / n, (-size,) * 3, (size,) * 3)


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


# ------------------------------------------------------------------ corpo tondo, musetto a punta, braccia conserte
HEAD_C = (0, -0.12, 1.78)
body = ellipsoid((0.88, 0.92, 0.84), (0, 0.12, 0.86))
head = ellipsoid((0.82, 0.76, 0.72), HEAD_C)
snout = round_cone((0, -0.62, 1.6), (0, -0.98, 1.53), 0.28, 0.1)
ARM_R = [0.14, 0.13, 0.125, 0.12]
arm_r = tube([(0.66, -0.3, 1.2), (0.44, -0.78, 1.04), (0.0, -0.92, 1.0), (-0.3, -0.88, 1.0)], ARM_R)
arm_l = tube([(-0.66, -0.3, 1.1), (-0.44, -0.76, 0.9), (0.0, -0.87, 0.84), (0.3, -0.83, 0.86)], ARM_R)
arms = union(arm_r, arm_l)
core = union(body, head, k=0.4)
core = union(core, snout, k=0.15)
core = union(core, arms, k=0.08)
m.add("Body", core, BROWN, tris=2000)
# vernice del muso piu' spessa: il corpo (quasi tutto coperto dagli aculei) e' a bassa risoluzione
painted = core.offset(0.03)


def paint(region, t=0.03, depth=0.08):
    """Vernice sottile che segue la superficie (solo uno strato vicino alla pelle)."""
    return core.offset(t).intersect(region).subtract(core.offset(-depth))


# ------------------------------------------------------------------ aculei aguzzi a file (dalla fronte alla coda)
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
        if p[2] < 0.42 or (p[1] < -0.55 and p[2] < 1.3):
            continue  # niente aculei sotto la pancia ne' sulle braccia
        d = n + np.array((0.0, 0.55, 0.1))
        d /= np.linalg.norm(d)
        tip = p + d * (0.25 + 0.1 * min(1.0, (beta - 50) / 70))
        spikes.append(round_cone(p - n * 0.08, tip, 0.2, 0.04))
        tips.append(sphere(0.09, tip + d * 0.03))
spike_sdf = fast_union(spikes).subtract(core.offset(-0.05))  # via le basi nascoste dentro il corpo
m.add("Spikes", spike_sdf, SPIKE, role="detail", tris=7200, voxel=0.032)
m.add("SpikeTips", spike_sdf.offset(0.012).intersect(fast_union(tips)), SPIKE_TIP, role="detail", tris=1300,
      voxel=0.028)

# ------------------------------------------------------------------ bocca all'ingiu' con i dentoni di sotto
MZ = 1.4  # bordo alto della bocca al centro
def lip(x):
    return MZ - 0.035 * (x / 0.2) ** 2  # angoli all'ingiu'


mouth_poly = [(x, lip(x)) for x in np.linspace(-0.2, 0.2, 17)]
mouth_poly += [(x, lip(x) - 0.075 * (1 - (x / 0.2) ** 2) ** 0.7) for x in np.linspace(0.2, -0.2, 17)[1:-1]]
mouth = face_prism(mouth_poly, -1.4, -0.5, r=0.003)
small = union(*[face_prism([(x - 0.018, MZ - 0.11), (x + 0.018, MZ - 0.11), (x, MZ - 0.04)], -1.4, -0.5, r=0.003)
                for x in (-0.15, -0.03, 0.03, 0.15)]).intersect(mouth.offset(-0.006))
fangs = union(*[face_prism([(x - 0.028, MZ - 0.12), (x + 0.028, MZ - 0.12), (x + 0.004, MZ + 0.04)], -1.4, -0.5,
                           r=0.004) for x in (-0.09, 0.09)])

# ------------------------------------------------------------------ musetto e pancia color crema, mani e piedi rosa
face_region = union(ellipsoid((0.62, 0.6, 0.52), (0, -0.66, 1.66)), ellipsoid((0.56, 0.55, 0.56), (0, -0.62, 0.84)),
                    k=0.2).subtract(arms.offset(0.03)).subtract(mouth.offset(0.01))
m.add("Cream", paint(face_region), CREAM, role="detail", tris=1200, voxel=0.025)
paws = [ellipsoid((0.17, 0.24, 0.12), (sx * 0.34, -0.38, 0.12)) for sx in (1, -1)]
for (hx, hy, hz) in ((-0.38, -0.84, 1.03), (0.38, -0.79, 0.89)):  # mani infilate sotto le braccia
    paws.append(sphere(0.115, (hx, hy, hz)))
    paws += [sphere(0.05, (hx + dx, hy - 0.06, hz + 0.08)) for dx in (-0.06, 0.0, 0.06)]
m.add("Paws", union(*paws, k=0.03), PAW, role="detail", tris=500, voxel=0.015)

# ------------------------------------------------------------------ faccia scontrosa
EYE_R = (0.14, 0.085, 0.19)
eye_frames = [Frame(painted, HEAD_C, (0.42 * sx, -1.0, 0.14), sink=0.045) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(ellipsoid(EYE_R)) for f in eye_frames]), EYE, role="eye", tris=500, voxel=0.013)
lid = ellipsoid((EYE_R[0] + 0.02, EYE_R[1] + 0.028, EYE_R[2] + 0.02))
m.add("Lids", union(*[f.place(lid.intersect(above_line(0.03, -0.42 * sx), k=0.012))
                      for f, sx in zip(eye_frames, (1, -1))]), CREAM, role="detail", tris=400, voxel=0.012)
shines = []
for f in eye_frames:
    shines.append(f.place(sphere(0.036), (-0.045, -0.072, -0.04)))
    shines.append(f.place(sphere(0.019), (0.05, -0.066, -0.11)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=250, voxel=0.009)

m.add("Nose", sphere(0.105, (0, -1.07, 1.545)), NOSE, role="detail", tris=300, voxel=0.012, reflectance=0.15)

brows = []
for sx in (1, -1):
    pts = bezier((sx * 0.09, 0, 2.06), (sx * 0.2, 0, 2.12), (sx * 0.32, 0, 2.2), (sx * 0.47, 0, 2.23), 8)
    path = [project(painted, (q[0], -0.3, q[2]), (0, -1, 0)) for q in pts]
    brows.append(tube([p - n * 0.004 for p, n in path], list(np.linspace(0.055, 0.032, len(path)))))

# ------------------------------------------------------------------ mela infilzata sugli aculei
pa, na = project(core, C, hood_dir(*APPLE_AB))
AC = pa + na * 0.42
apple = ellipsoid((0.25, 0.25, 0.22), AC).subtract(sphere(0.07, AC + (0, 0, 0.24)), k=0.06)
apple = apple.subtract(sphere(0.05, AC - (0, 0, 0.24)), k=0.05)
m.add("Apple", apple, APPLE, role="detail", tris=500, voxel=0.016, reflectance=0.06)
stem_pts = bezier(AC + (0, 0, 0.12), AC + (0.0, 0.0, 0.25), AC + (0.03, 0.02, 0.3), AC + (0.07, 0.03, 0.33), 8)
leaf = ellipsoid((0.11, 0.025, 0.055), (-0.1, 0, 0)).rot(0, 25, 0).rot(0, 0, 30).translate(stem_pts[4])
m.add("Leaf", leaf, LEAF, role="detail", tris=200, voxel=0.01)
m.add("Brows", union(*brows, tube(stem_pts, [0.03] * 3 + [0.026] * 3 + [0.022] * 3)), DARK, role="detail", tris=450,
      voxel=0.011)
m.add("Mouth", paint(mouth, t=0.014, depth=0.03), MOUTH, role="eye", tris=400, voxel=0.009)
m.add("Teeth", union(paint(small, t=0.03, depth=0.02), paint(fangs, t=0.045, depth=0.02)), WHITE, role="shine",
      tris=700, voxel=0.0075)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
