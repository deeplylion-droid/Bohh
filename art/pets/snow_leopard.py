"""Leopardo delle Nevi (SnowLeopard) - pet Raro: cucciolo con rosette ad anello e coda foltissima."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, ellipsoid, prism, project, project_curve, round_cone, sphere,  # noqa: E402
                     stick, tube, union)
from lib.toy import Model  # noqa: E402

FUR = (208, 212, 224)
WHITE_FUR = (252, 252, 250)
SPOT = (72, 74, 86)
PINK = (255, 150, 172)
IRIS = (132, 198, 238)
EYE = (24, 26, 38)
WHITE = (255, 255, 255)
BLUSH = (255, 140, 160)

m = Model("SnowLeopard", "pet")
PK = 0.01  # bordo morbido delle "vernici"


def paint(base, region, d=0.022, depth=0.04, k=PK):
    """Vernice a strato: fra -depth e +d attorno alla superficie, ritagliata dalla regione.

    Uno strato (invece del pezzo pieno core.offset(d).intersect(regione)) non ha grandi superfici nascoste
    all'interno, quindi a parita' di triangoli si puo' usare un voxel fine e i bordi restano puliti.
    Lo spessore d + depth deve restare >= 2 voxel, altrimenti il marching cubes lo buca.
    """
    t = (d + depth) / 2
    return base.offset(d - t).shell(t).intersect(region, k=k)


# ---------------------------------------------------------------- corpo da cucciolo in piedi
HEAD_C = (0, -0.58, 2.02)
head = ellipsoid((0.84, 0.74, 0.7), HEAD_C)
jowls = union(*[ellipsoid((0.36, 0.32, 0.3), (sx * 0.52, -0.86, 1.8)) for sx in (1, -1)])
pads = union(*[ellipsoid((0.17, 0.14, 0.13), (sx * 0.12, -1.3, 1.74)) for sx in (1, -1)])
head_full = union(union(head, jowls, k=0.18), pads, k=0.08)
body = ellipsoid((0.6, 0.85, 0.55), (0, 0.25, 0.9))
neck = round_cone((0, -0.2, 1.1), (0, -0.45, 1.6), 0.4, 0.38)
torso = union(body, neck, k=0.2)
LEGS = [(sx * 0.33, y) for sx in (1, -1) for y in (-0.3, 0.8)]
legs = union(*[round_cone((x, y, 0.8), (x, y - 0.02, 0.2), 0.19, 0.17) for x, y in LEGS])
paws = union(*[ellipsoid((0.21, 0.25, 0.15), (x * 1.04, y - 0.06, 0.15)) for x, y in LEGS])
EAR_C = [(sx * 0.6, -0.36, 2.6) for sx in (1, -1)]
ears = union(*[ellipsoid((0.2, 0.1, 0.18)).rot(0, sx * 26, 0).translate(c) for sx, c in zip((1, -1), EAR_C)])
core0 = union(torso, head_full, k=0.3)
limbs = union(legs, paws, k=0.08)

# coda foltissima che sale e si arriccia
N = 32
tail_pts = bezier((0.05, 0.95, 0.9), (0.25, 1.95, 0.7), (0.95, 2.05, 2.0), (0.4, 1.32, 2.12), N)


def tail_r(t):
    r = 0.22 + 0.13 * min(t / 0.3, 1.0) ** 0.7
    return r * (1.0 if t < 0.9 else max(0.25, 1.0 - (t - 0.9) / 0.1) ** 0.4)


tail = tube(tail_pts, [tail_r(i / N) for i in range(N + 1)])
core = union(union(core0, limbs, k=0.1), ears, k=0.05)
core = union(core, tail, k=0.12)
m.add("Body", core, FUR, tris=6000)

# pancia, petto, mento e cuscinetti del muso bianchi
belly = core0.offset(0.022).intersect(union(ellipsoid((0.46, 0.82, 0.3), (0, 0.25, 0.4)),
                                            ellipsoid((0.4, 0.36, 0.48), (0, -0.56, 1.0)),
                                            ellipsoid((0.42, 0.34, 0.3), (0, -1.28, 1.62)), k=0.15), k=PK)
m.add("Belly", belly, WHITE_FUR, role="detail", tris=1500)

# rosette ad anello (alcune aperte a "C") sul dorso, sui fianchi e sulla coda, macchie sulla testa e sulle zampe


def fast_union(shapes, margin=0.06):
    """Unione di tante forme piccole: ognuna e' valutata solo dentro il proprio box di ingombro."""
    los = [s.lo - margin for s in shapes]
    his = [s.hi + margin for s in shapes]

    def f(p):
        d = np.full(len(p), 1e3, dtype=np.float32)
        for s, lo, hi in zip(shapes, los, his):
            mask = np.all((p >= lo) & (p <= hi), axis=1)
            if mask.any():
                d[mask] = np.minimum(d[mask], s(p[mask]))
        return d

    return SDF(f, np.min(los, axis=0), np.max(his, axis=0))


rng = np.random.default_rng(11)
centres = []


def ring_shell(p, n, r_out, width=0.058, gap=None):
    """Regione ad anello attorno al punto p della superficie: guscio fra due sfere concentriche."""
    shell = sphere(r_out, p).subtract(sphere(r_out - width, p))
    if gap is not None:
        t = np.cross(n, gap)
        t = t / np.linalg.norm(t)
        shell = shell.subtract(sphere(0.06, p + t * (r_out - width / 2)))
    return shell


def free(p, r):
    return all(np.linalg.norm(q - p) > r * 2.4 for q in centres)


body_shells = []
BODY_C = np.array([0, 0.3, 0.9])
tries = 0
while len(body_shells) < 13 and tries < 800:
    tries += 1
    d = rng.normal(size=3)
    d[2] = abs(d[2]) + 0.15
    d = d / np.linalg.norm(d)
    p, n = project(core0, BODY_C, d)
    r = rng.uniform(0.135, 0.16)
    if p[2] < 0.82 or p[1] < -0.35 or np.linalg.norm(p - np.array(HEAD_C)) < 1.0 or not free(p, r):
        continue
    centres.append(p)
    body_shells.append(ring_shell(p, n, r, gap=rng.normal(size=3) if rng.random() < 0.5 else None))
tail_shells = []
for t in np.linspace(0.16, 0.78, 6):
    i = int(t * N)
    a = rng.uniform(0, 2 * math.pi)
    c = np.array(tail_pts[i])
    tan = np.subtract(tail_pts[i + 1], tail_pts[i - 1])
    tan = tan / np.linalg.norm(tan)
    side = np.cross(tan, [0, 0, 1.0])
    side = side / np.linalg.norm(side) if np.linalg.norm(side) > 0.3 else np.array([1.0, 0, 0])
    up = np.cross(side, tan)
    for aa in (a, a + 2.1, a + 4.2):
        d = side * math.cos(aa) + up * math.sin(aa)
        p, n = project(tail, c, d)
        r = rng.uniform(0.12, 0.14)
        if free(p, r):
            centres.append(p)
            tail_shells.append(ring_shell(p, n, r, gap=rng.normal(size=3) if rng.random() < 0.4 else None))
body_rings = paint(core0, fast_union(body_shells), depth=0.034, k=0.005)
tail_rings = paint(tail, union(fast_union(tail_shells), sphere(0.34, tail_pts[N])), depth=0.034, k=0.005)
head_dots = []
for x, z, r in [(0.0, 2.64, 0.07), (0.16, 2.56, 0.055), (-0.16, 2.56, 0.055), (0.58, 2.24, 0.06), (-0.58, 2.24, 0.06),
                (0.7, 2.06, 0.05), (-0.7, 2.06, 0.05)]:
    p, _ = project(core0, (x * 0.5, HEAD_C[1], z * 0.6 + HEAD_C[2] * 0.4), (x, -0.6, z - HEAD_C[2]))
    head_dots.append(sphere(r, p))
leg_dots = []
for x, y in LEGS:
    p, _ = project(limbs, (x, y, 0.56), (np.sign(x), -0.4, 0))
    leg_dots.append(sphere(0.065, p))
dots = union(paint(core0, fast_union(head_dots), depth=0.034, k=0.005),
             paint(limbs, fast_union(leg_dots), depth=0.034, k=0.005))
m.add("Rosettes", union(body_rings, tail_rings, dots), SPOT, role="detail", tris=3200, voxel=0.026)

# naso rosa e interno delle orecchie
painted = core0.offset(0.022)
nose_f = Frame(painted, (0, -1.2, 1.8), (0, -1.0, 0.75), sink=0.02)
nose = nose_f.place(prism([(-0.09, 0.035), (0.09, 0.035), (0.0, -0.065)], -0.035, 0.035, round=0.03).rot(90, 0, 0))
inner_ears = paint(ears, union(*[ellipsoid((0.13, 0.12, 0.12)).translate((0, -0.12, -0.01)).rot(0, sx * 26, 0)
                                  .translate(c) for sx, c in zip((1, -1), EAR_C)]))
m.add("Pink", union(nose, inner_ears), PINK, role="detail", tris=700, voxel=0.012)

mouth_pts = [(0.0, 1.8), (0.0, 1.73), (-0.03, 1.69), (-0.07, 1.68), (-0.11, 1.7), (-0.13, 1.73)]
mouth_l = project_curve(painted, [(x, -0.9, z) for x, z in mouth_pts], (0, -1, 0), inset=0.006)
mouth_r = project_curve(painted, [(-x, -0.9, z) for x, z in mouth_pts[1:]], (0, -1, 0), inset=0.006)
m.add("Mouth", union(tube(mouth_l, 0.02), tube(mouth_r, 0.02)), SPOT, role="detail", tris=500, voxel=0.011)

# occhi azzurri: contorno scuro dipinto, iride azzurra, pupilla scura, riflessi
frames = [Frame(core0, HEAD_C, (0.46 * sx, -1.0, 0.2), sink=0.05) for sx in (1, -1)]
outline = paint(core0, union(*[f.place(ellipsoid((0.18, 0.3, 0.222))) for f in frames]), d=0.012, depth=0.03, k=0.004)
pupils = union(*[f.place(ellipsoid((0.088, 0.04, 0.11)), (0, -0.065, 0.0)) for f in frames])
m.add("EyeDark", union(outline, pupils), EYE, role="eye", tris=1000, voxel=0.016)
m.add("Iris", union(*[f.place(ellipsoid((0.16, 0.09, 0.2))) for f in frames]), IRIS, role="eye", tris=800,
      voxel=0.0165)
shines = []
for f in frames:
    shines.append(f.place(sphere(0.056), (-0.05, -0.085, 0.075)))
    shines.append(f.place(sphere(0.029), (0.055, -0.08, -0.085)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=450, voxel=0.01)
blush = ellipsoid((0.13, 0.04, 0.08))
m.add("Blush", union(*[stick(blush, core0, HEAD_C, (sx * 0.8, -0.78, -0.3), sink=0.018) for sx in (1, -1)]),
      BLUSH, role="detail", tris=450, voxel=0.013)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
