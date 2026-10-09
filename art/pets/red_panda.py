"""Panda Rosso (RedPanda) - pet Raro: seduto, con la grande coda folta ad anelli."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, ellipsoid, project_curve, round_cone, sphere,  # noqa: E402
                     stick, tube, union)
from lib.toy import Model  # noqa: E402

RED = (214, 92, 44)
RUST = (150, 54, 30)
WHITE_FUR = (255, 248, 236)
DARK = (76, 42, 36)
NOSE = (48, 32, 34)
EYE = (30, 20, 26)
WHITE = (255, 255, 255)
BLUSH = (255, 128, 146)

m = Model("RedPanda", "pet")


def front_region(points2d, r, y0=-3.0, y1=0.4):
    """Regione 'disegnata' nella vista frontale: catena di capsule nel piano XZ estrusa lungo Y."""
    pts = np.asarray(points2d, dtype=np.float32)

    def f(p):
        q = p[:, [0, 2]]
        d = np.full(len(p), 1e3, dtype=np.float32)
        for a, b in zip(pts[:-1], pts[1:]):
            ba = b - a
            h = np.clip(((q - a) @ ba) / float(ba @ ba), 0.0, 1.0)
            d = np.minimum(d, np.linalg.norm(q - a - h[:, None] * ba, axis=1))
        return np.maximum(d - r, np.maximum(y0 - p[:, 1], p[:, 1] - y1))

    lo = (pts[:, 0].min() - r, y0, pts[:, 1].min() - r)
    hi = (pts[:, 0].max() + r, y1, pts[:, 1].max() + r)
    return SDF(f, lo, hi)


def slab(c, t, w):
    """Fetta spessa 2w perpendicolare alla direzione t, centrata in c (per gli anelli della coda)."""
    c = np.asarray(c, dtype=np.float32)
    t = np.asarray(t, dtype=np.float32)
    t = t / np.linalg.norm(t)
    return SDF(lambda p: np.abs((p - c) @ t) - w, c - 2, c + 2)


# ---------------------------------------------------------------- corpo seduto e testa larga
HEAD_C = (0, -0.15, 2.1)
head = ellipsoid((0.9, 0.78, 0.72), HEAD_C)
cheeks = union(*[ellipsoid((0.38, 0.36, 0.32), (sx * 0.62, -0.32, 1.9)) for sx in (1, -1)])
MUZZLE_C = (0, -0.78, 1.9)
muzzle = ellipsoid((0.3, 0.24, 0.2), MUZZLE_C)
head_full = union(union(head, cheeks, k=0.2), muzzle, k=0.14)
body = ellipsoid((0.82, 0.78, 0.9), (0, 0.12, 0.92))
haunch = union(*[ellipsoid((0.4, 0.5, 0.38), (sx * 0.5, -0.05, 0.4)) for sx in (1, -1)])
torso = union(body, haunch, k=0.25)
EAR_C = [(sx * 0.6, -0.04, 2.7) for sx in (1, -1)]


def ear_shape(sx):
    e = round_cone((0, 0, -0.1), (0, 0, 0.26), 0.32, 0.13).warp(lambda p: p * [[1.0, 2.4, 1.0]])
    return e.rot(0, sx * 26, 0)


ears = union(*[ear_shape(sx).translate(c) for sx, c in zip((1, -1), EAR_C)])
core0 = union(torso, head_full, k=0.35)

# grande coda folta che si arriccia sul fianco (raggio "a sbuffi": gli anelli scuri cadono nelle strozzature)
N = 40
tail_pts = bezier((0.25, 0.75, 0.42), (1.05, 1.35, 0.25), (1.45, 0.75, 0.95), (1.05, 0.5, 1.72), N)
BANDS_T = [0.3, 0.47, 0.64, 0.81]


def tail_r(t):
    base = 0.26 + 0.18 * math.sin(math.pi * min(t / 0.9, 1.0) ** 0.8)
    puff = 1.0 + 0.07 * math.cos(2 * math.pi * (t - BANDS_T[0]) / 0.17 + math.pi)
    tip = 1.0 if t < 0.88 else max(0.0, 1.0 - (t - 0.88) / 0.12) ** 0.5
    return max(base * puff * tip, 0.06)


tail_radii = [tail_r(i / N) for i in range(N + 1)]
tail = tube(tail_pts, tail_radii)
core = union(core0, ears, k=0.06)
core = union(core, tail, k=0.12)
m.add("Body", core, RED, tris=6800, voxel=0.025)

# maschera bianca: muso, guance, sopracciglia e bordo delle orecchie
PK = 0.012  # bordo morbido delle "vernici": spigolo pulito dopo marching cubes e decimazione
muzzle_white = core0.offset(0.022).intersect(ellipsoid((0.36, 0.5, 0.27), (0, -0.85, 1.84)), k=PK)
cheek_white = core0.offset(0.022).intersect(union(*[ellipsoid((0.3, 0.5, 0.25), (sx * 0.64, -0.55, 1.8))
                                                   for sx in (1, -1)]), k=PK)
brows = union(*[stick(ellipsoid((0.135, 0.04, 0.08)), core0, HEAD_C, (sx * 0.38, -1.0, 0.55), sink=0.018)
                for sx in (1, -1)])
ears_painted = ears.offset(0.02)
ear_white = ears_painted.intersect(union(*[ellipsoid((0.6, 0.12, 0.6), (c[0], c[1] - 0.12, c[2] + 0.05)) for c in EAR_C]),
                                   k=PK)
# centro della parte visibile dell'orecchio (sull'asse inclinato), sul lato anteriore
EAR_MID = [(c[0] + sx * 0.08, c[1] - 0.08, c[2] + 0.17) for sx, c in zip((1, -1), EAR_C)]
m.add("White", union(muzzle_white, cheek_white, brows, ear_white), WHITE_FUR, role="detail", tris=2400, voxel=0.014)

# zampe, pancia e interno delle orecchie marrone scuro
belly = core0.offset(0.022).intersect(union(ellipsoid((0.46, 0.5, 0.5), (0, -0.62, 0.7)),
                                            *[ellipsoid((0.44, 0.5, 0.26), (sx * 0.5, -0.25, 0.2)) for sx in (1, -1)]), k=PK)
front_legs = union(*[union(round_cone((sx * 0.37, -0.42, 1.05), (sx * 0.39, -0.66, 0.16), 0.19, 0.165),
                           ellipsoid((0.19, 0.23, 0.13), (sx * 0.39, -0.73, 0.13)), k=0.06) for sx in (1, -1)])
hind_feet = union(*[ellipsoid((0.2, 0.3, 0.12), (sx * 0.64, -0.42, 0.12)) for sx in (1, -1)])
ear_inner = ears.offset(0.034).intersect(union(*[ellipsoid((0.11, 0.1, 0.16)).rot(0, sx * 26, 0).translate(c)
                                                 for sx, c in zip((1, -1), EAR_MID)]), k=PK)
m.add("Dark", union(belly, front_legs, hind_feet, ear_inner), DARK, role="detail", tris=1800)

# anelli della coda (parte separata) + "lacrime" sotto gli occhi
bands = []
for t0 in BANDS_T + [0.97]:
    i = int(round(t0 * N))
    c = tail_pts[i]
    tan = np.subtract(tail_pts[min(i + 1, N)], tail_pts[max(i - 1, 0)])
    w = 0.055 if t0 < 0.9 else 0.09
    bands.append(tail.offset(0.022).intersect(slab(c, tan, w).intersect(sphere(0.6, c)), k=PK))
tip = tail.offset(0.022).intersect(sphere(0.32, tail_pts[N]), k=PK)
m.add("Bands", union(*bands, tip), RUST, role="detail", tris=1400)
tears = core0.offset(0.036).intersect(union(*[front_region([(sx * 0.27, 2.06), (sx * 0.31, 1.9), (sx * 0.39, 1.72)],
                                                           0.062) for sx in (1, -1)]), k=0.01)
m.add("Tears", tears, RUST, role="detail", tris=600, voxel=0.012)

# naso e bocca
nose = Frame(core0, MUZZLE_C, (0, -1.0, 0.5), sink=0.03).place(
    union(ellipsoid((0.1, 0.065, 0.06)), ellipsoid((0.05, 0.05, 0.05), (0, 0, -0.035)), k=0.04))
mouth_pts = [(0.0, 1.88), (0.0, 1.82), (-0.03, 1.79), (-0.07, 1.78), (-0.11, 1.8), (-0.13, 1.83)]
painted = core0.offset(0.022)
mouth_l = project_curve(painted, [(x, -0.4, z) for x, z in mouth_pts], (0, -1, 0), inset=0.006)
mouth_r = project_curve(painted, [(-x, -0.4, z) for x, z in mouth_pts[1:]], (0, -1, 0), inset=0.006)
m.add("Nose", union(nose, tube(mouth_l, 0.022), tube(mouth_r, 0.022)), NOSE, role="detail", tris=700, voxel=0.012)

# occhioni lucidi, riflessi, guance rosa
eye_shape = ellipsoid((0.15, 0.09, 0.19))
frames = [Frame(core0, HEAD_C, (0.42 * sx, -1.0, 0.16), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in frames]), EYE, role="eye", tris=900, voxel=0.014)
shines = []
for f in frames:
    shines.append(f.place(sphere(0.058), (-0.05, -0.075, 0.075)))
    shines.append(f.place(sphere(0.03), (0.055, -0.07, -0.085)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=450, voxel=0.01)
blush = ellipsoid((0.13, 0.04, 0.08))
m.add("Blush", union(*[stick(blush, core0.offset(0.022), HEAD_C, (sx * 0.85, -0.75, -0.38), sink=0.016)
                       for sx in (1, -1)]), BLUSH, role="detail", tris=450, voxel=0.013)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
