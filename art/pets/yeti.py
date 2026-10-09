"""Yeti - pet Leggendario: cucciolo di yeti peloso e amichevole."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, box, capsule, ellipsoid, halfspace_z, project, project_curve,  # noqa: E402
                     round_cone, smin, sphere, stick, tube, union)
from lib.toy import Model  # noqa: E402

FUR = (234, 243, 255)
SKIN = (128, 190, 244)
HORN = (240, 226, 196)
EYE = (22, 26, 50)
WHITE = (255, 255, 255)
BLUSH = (255, 140, 184)
MOUTH = (52, 34, 84)
TONGUE = (255, 120, 150)


def fast_union(base: SDF, shapes, k: float = 0.0, margin: float = 0.08) -> SDF:
    """Unione (morbida) di molte forme piccole: ognuna e' valutata solo vicino al suo ingombro."""
    los = np.array([s.lo for s in shapes]) - margin - k
    his = np.array([s.hi for s in shapes]) + margin + k

    def f(p):
        d = base(p)
        if len(p) == 0:
            return d
        plo, phi = p.min(0), p.max(0)
        for i in np.nonzero(np.all((his >= plo) & (los <= phi), axis=1))[0]:
            msk = np.all((p >= los[i]) & (p <= his[i]), axis=1)
            if msk.any():
                idx = np.nonzero(msk)[0]
                d[idx] = smin(d[idx], shapes[i](p[idx]), k)
        return d

    return SDF(f, np.minimum(base.lo, los.min(0)), np.maximum(base.hi, his.max(0)))


def fib_dirs(n):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    theta = math.pi * (1 + 5 ** 0.5) * i
    return np.stack([np.cos(theta) * np.sin(phi), np.sin(theta) * np.sin(phi), np.cos(phi)], 1)


m = Model("Yeti", "pet")

# ------------------------------------------------------------------ corpo base
HEAD_C = (0, -0.06, 2.0)
BODY_C = (0, 0.04, 1.0)
head = ellipsoid((0.94, 0.84, 0.8), HEAD_C)
body = ellipsoid((0.98, 0.86, 0.86), BODY_C)
face_bulge = ellipsoid((0.6, 0.32, 0.5), (0, -0.64, 1.86))
LEG = [(sx * 0.42, -0.04) for sx in (1, -1)]
legs = union(*[capsule((x, y, 0.62), (x, y - 0.06, 0.24), 0.3) for x, y in LEG])
SHOULDER = [(sx * 0.8, 0.0, 1.56) for sx in (1, -1)]
WRIST = [(sx * 1.18, -0.16, 1.0) for sx in (1, -1)]
arms = union(*[capsule(s, w, 0.27) for s, w in zip(SHOULDER, WRIST)])
core = union(head, body, k=0.5)
core = union(core, face_bulge, k=0.2)
core = union(core, legs, k=0.15)
core = union(core, arms, k=0.18)

# ------------------------------------------------------------------ pelo: file ordinate di ciuffi a goccia
FACE_C = np.array([0, -0.85, 1.86])
FACE_R = (0.66, 0.58)


def in_face(p, grow=0.0):
    return ((p[0] / (FACE_R[0] + grow)) ** 2 + ((p[2] - FACE_C[2]) / (FACE_R[1] + grow)) ** 2 < 1.0) and p[1] < -0.3


def clump_at(p, n, size):
    n = n / np.linalg.norm(n)
    down = np.array([0, 0, -1.0]) - n * (-n[2])
    if np.linalg.norm(down) < 0.2:
        down = np.array([0, 1.0, 0]) - n * n[1]
    down /= np.linalg.norm(down)
    a = p - n * (0.03 * size) - down * 0.08 * size
    b = p + n * (0.0 * size) + down * 0.25 * size
    return round_cone(a, b, 0.17 * size, 0.06 * size)


def ring_dirs(el_deg, count, phase):
    el = math.radians(el_deg)
    return [np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
            for az in (2 * math.pi * (i + phase) / count for i in range(count))]


clumps = []
rows = [(HEAD_C, 78, 5), (HEAD_C, 58, 11), (HEAD_C, 38, 15), (HEAD_C, 18, 17), (HEAD_C, -2, 18), (HEAD_C, -22, 18),
        (BODY_C, 12, 19), (BODY_C, -8, 19), (BODY_C, -28, 18), (BODY_C, -48, 15)]
for r, (c, el, cnt) in enumerate(rows):
    for d in ring_dirs(el, cnt, 0.5 * (r % 2)):
        try:
            p, nrm = project(core, c, d)
        except ValueError:
            continue
        if in_face(p) or p[2] < 0.32:
            continue
        if c is BODY_C and p[2] > 1.5:
            continue  # zona gia' coperta dalle file della testa
        clumps.append(clump_at(p, nrm, 1.0))
# braccia pelose (maniche a ciuffi)
for s, w in zip(SHOULDER, WRIST):
    for t, ph in ((0.3, 0.0), (0.62, 0.5), (0.92, 0.0)):
        a = np.array(s) * (1 - t) + np.array(w) * t
        for ang in np.linspace(0, 2 * math.pi, 7)[:-1] + ph:
            d = np.array([math.cos(ang), math.sin(ang), 0.2])
            try:
                p, nrm = project(core, a, d)
            except ValueError:
                continue
            if in_face(p, 0.05):
                continue
            clumps.append(clump_at(p, nrm, 0.85))
# ciuffo spettinato in cima alla testa
tuft = union(*[tube(bezier((x0, -0.1, 2.6), (x0 * 1.3, -0.2, 2.9), (x0 * 1.6 + 0.08, -0.3, 3.0), (x0 * 1.7 + 0.12, -0.42, 2.92), 8),
                    [0.12, 0.11, 0.1, 0.09, 0.08, 0.06, 0.05, 0.04, 0.035]) for x0 in (-0.12, 0.0, 0.12)], k=0.04)
fur = fast_union(core, clumps, k=0.08)
fur = union(fur, tuft, k=0.08)
m.add("Fur", fur, FUR, tris=7200, voxel=0.022)

# ------------------------------------------------------------------ pelle azzurra: viso, mani, piedi
face_region = ellipsoid((FACE_R[0], 0.6, FACE_R[1]), (0, -0.85, 1.86))
face = core.offset(0.025).intersect(face_region)
m.add("Face", face, SKIN, role="detail", tris=1100, voxel=0.016)


def hand(sx):
    palm = ellipsoid((0.29, 0.19, 0.3), (0, 0, 0))
    fingers = [capsule((dx, -0.02, -0.14), (dx * 1.25, -0.07, -0.42), 0.1) for dx in (-0.15, 0.0, 0.15)]
    thumb = capsule((0.2, -0.04, 0.02), (0.35, -0.13, 0.15), 0.1)
    h = union(palm, *fingers, thumb, k=0.07)
    # mano sinistra (lato -X): palmo in avanti e un po' all'esterno, pollice verso il corpo
    h = h.rot(0, 0, -22).translate((-1.26, -0.24, 0.84))
    return h if sx < 0 else h.mirrored()


def foot(sx):
    x = sx * 0.44
    sole = ellipsoid((0.34, 0.45, 0.2), (x, -0.26, 0.12))
    toes = [sphere(0.13, (x + dx, -0.66, 0.11)) for dx in (-0.18, 0.0, 0.18)]
    f = union(sole, *toes, k=0.08)
    return f.intersect(halfspace_z(0.0, above=True))


m.add("Hands", union(hand(1), hand(-1)), SKIN, role="detail", tris=1300, voxel=0.018)
m.add("Feet", union(foot(1), foot(-1)), SKIN, role="detail", tris=1000, voxel=0.018)

# ------------------------------------------------------------------ corna ricurve
horns = union(*[tube(bezier((sx * 0.46, 0.02, 2.56), (sx * 0.72, 0.02, 2.74), (sx * 0.86, -0.06, 2.98), (sx * 0.74, -0.16, 3.1), 12),
                     [0.17 - 0.0095 * i for i in range(13)]) for sx in (1, -1)])
m.add("Horns", horns, HORN, role="detail", tris=800, voxel=0.016)

# ------------------------------------------------------------------ occhi, guance
face_surf = core.offset(0.025)
eye_shape = ellipsoid((0.17, 0.1, 0.22))
frames = [Frame(face_surf, HEAD_C, (0.36 * sx, -1.0, 0.04), sink=0.045) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in frames]), EYE, role="eye", tris=900, voxel=0.013)
shines = []
for f in frames:
    shines.append(f.place(sphere(0.064), (-0.055, -0.085, 0.085)))
    shines.append(f.place(sphere(0.032), (0.062, -0.08, -0.1)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=400, voxel=0.01)
blush = ellipsoid((0.13, 0.04, 0.08))
m.add("Blush", union(*[stick(blush, face_surf, HEAD_C, (sx * 0.6, -0.9, -0.3), sink=0.018) for sx in (1, -1)]),
      BLUSH, role="detail", tris=400, voxel=0.013)

# ------------------------------------------------------------------ sorriso largo con due dentini
MZ = 1.7  # quota della linea del sorriso
mouth_region = ellipsoid((0.3, 5.0, 0.17), (0, -0.9, MZ)).subtract(capsule((0, -3, MZ + 0.8), (0, 3, MZ + 0.8), 0.8))
mouth_region = mouth_region.intersect(box((0.5, 0.45, 0.4), (0, -1.0, MZ)))
mouth = core.offset(0.04).intersect(mouth_region)
m.add("Mouth", mouth, MOUTH, role="detail", tris=600, voxel=0.011)
tongue = core.offset(0.05).intersect(mouth_region).intersect(ellipsoid((0.16, 5.0, 0.085), (0, -0.9, MZ - 0.15)))
m.add("Tongue", tongue, TONGUE, role="detail", tris=300, voxel=0.011)
fangs = []
for sx in (1, -1):
    x = sx * 0.14
    ztop = MZ + 0.8 - math.sqrt(0.8 ** 2 - x ** 2)
    p, nrm = project(core.offset(0.04), (x, -0.4, ztop), (0, -1, 0))
    fangs.append(round_cone(p - nrm * 0.01 + np.array([0, 0, 0.01]), p - nrm * 0.0 - np.array([0, 0, 0.1]), 0.042, 0.014))
m.add("Fangs", union(*fangs), WHITE, role="detail", tris=300, voxel=0.01)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
