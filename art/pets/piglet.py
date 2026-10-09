"""Maialino (Piglet) - pet Comune."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (Frame, bezier, box, cylinder, ellipsoid, prism, project, project_curve, sphere,  # noqa: E402
                     stick, tube, union)
from lib.toy import Model  # noqa: E402

PINK = (255, 184, 198)
PINK_LIGHT = (255, 202, 212)
SNOUT = (255, 146, 172)
NOSTRIL = (150, 58, 92)
HOOF = (172, 102, 112)
MUD = (132, 90, 62)
EYE = (36, 22, 34)
WHITE = (255, 255, 255)
BLUSH = (255, 112, 146)
MOUTH = (150, 62, 92)

m = Model("Piglet", "pet")

# ------------------------------------------------------------------ corpo tondo + testone
HEAD_C = (0, -0.1, 1.84)
body = ellipsoid((0.9, 0.88, 0.76), (0, 0.1, 0.96))
head = ellipsoid((0.88, 0.8, 0.76), HEAD_C)
core = union(body, head, k=0.35)
LEGS = ((0.44, -0.42), (-0.44, -0.42), (0.46, 0.52), (-0.46, 0.52))
legs = union(*[cylinder((x, y, 0.2), (x, y, 0.5), 0.17, round=0.07) for x, y in LEGS])
core = union(core, legs, k=0.1)
m.add("Body", core, PINK, tris=5600)
painted = core.offset(0.02)


def paint(region, t=0.02, depth=0.05):
    """Vernice sottile che segue la superficie (solo uno strato vicino alla pelle)."""
    return core.offset(t).intersect(region).subtract(core.offset(-depth))


belly_region = ellipsoid((0.5, 0.5, 0.44), (0, -0.66, 0.74))
m.add("Belly", paint(belly_region.subtract(legs.offset(0.06))), PINK_LIGHT, role="detail", tris=1000)

# zoccoli piu' scuri (con l'unghia divisa)
hooves = []
for x, y in LEGS:
    h = cylinder((x, y, 0.05), (x, y, 0.1), 0.18, round=0.05)
    hooves.append(h.subtract(box((0.014, 0.1, 0.12), (x, y - 0.18, 0.06)), k=0.01))
m.add("Hooves", union(*hooves), HOOF, role="detail", tris=900, voxel=0.015)

# ------------------------------------------------------------------ grugno a disco con narici
SN_C = np.array((0.0, -0.84, 1.6))


def oval_x(shape, sx):
    """Allarga una forma lungo x (deformazione dello spazio, distanza approssimata)."""
    return shape.warp(lambda p: p * np.array([1.0 / sx, 1.0, 1.0], dtype=np.float32), pad=0.1)


disc = cylinder((0, 0.0, 0), (0, -0.14, 0), 0.25, round=0.08)
disc = oval_x(disc, 1.18).rot(-8, 0, 0).translate(SN_C)
nostril_holes = union(*[ellipsoid((0.05, 0.08, 0.075), (sx * 0.1, -0.22, 0.0)) for sx in (1, -1)])
nostril_holes = nostril_holes.rot(-8, 0, 0).translate(SN_C)
m.add("Snout", disc.subtract(nostril_holes, k=0.025), SNOUT, role="detail", tris=1200, voxel=0.015)
nostrils = union(*[ellipsoid((0.045, 0.03, 0.068), (sx * 0.1, -0.165, 0.0)) for sx in (1, -1)])
m.add("Nostrils", nostrils.rot(-8, 0, 0).translate(SN_C), NOSTRIL, role="detail", tris=400, voxel=0.01)

# ------------------------------------------------------------------ orecchie triangolari ripiegate (animabili)
def tri_plate(poly, t=0.045, r=0.035):
    """Lastra con contorno poligonale nel piano XZ (spessore lungo Y)."""
    return prism(poly, -t, t, round=r).rot(90, 0, 0)


ear_base = tri_plate([(-0.3, 0.0), (0.3, 0.0), (0.16, 0.36), (-0.16, 0.36)], t=0.05)
ear_tip = tri_plate([(-0.18, 0.33), (0.18, 0.33), (0.0, 0.62)], t=0.05).rot(115, 0, 0, pivot=(0, 0, 0.35))
ear_local = union(ear_base, ear_tip, k=0.04)


def place_ear(shape, sx):
    s = shape.rot(0, 0, 12).rot(0, 28, 0).translate((0.42, -0.08, 2.36))
    return s if sx > 0 else s.mirrored()


for sx, nm in ((1, "EarR"), (-1, "EarL")):
    m.add(nm, place_ear(ear_local, sx), PINK, role="skin", tris=900, voxel=0.015, group=nm,
          pivot=(sx * 0.42, -0.08, 2.4))

# ------------------------------------------------------------------ codina a cavatappi (tubo lungo un'elica)
helix = [(0.0, -0.25, 0.0)]
turns = 2.0
for i in range(56):
    a = i / 55 * turns * 2 * math.pi
    rr = 0.15 * (1 - 0.3 * i / 55)
    helix.append((rr * math.sin(a), 0.04 + 0.13 * a / (2 * math.pi), rr * (1 - math.cos(a))))
radii = [0.06] + [0.056 - 0.018 * i / 55 for i in range(56)]
tail = tube(helix, radii).rot(40, 0, 0).translate((0, 0.98, 1.0))
m.add("Tail", tail, PINK, role="skin", tris=1400, voxel=0.014)

# ------------------------------------------------------------------ schizzo di fango sul fianco destro
mud_spots = []
p0, n0 = project(core, (0, 0.1, 0.95), (1.0, -0.12, -0.12))
t1 = np.cross(n0, (0, 0, 1))
t1 /= np.linalg.norm(t1)
t2 = np.cross(t1, n0)
for (u, v, r) in ((0, 0, 0.2), (0.16, 0.08, 0.12), (-0.15, 0.1, 0.12), (0.05, -0.17, 0.12), (-0.1, -0.13, 0.1),
                  (0.2, -0.1, 0.09), (0.36, 0.12, 0.055), (-0.34, 0.16, 0.05), (0.12, -0.34, 0.05),
                  (0.3, -0.3, 0.035)):
    mud_spots.append(sphere(r, p0 + t1 * u + t2 * v))
mud_region = union(*mud_spots[:6], k=0.06).union(*mud_spots[6:])
m.add("Mud", paint(mud_region), MUD, role="detail", tris=900, voxel=0.015)

# ------------------------------------------------------------------ faccia
eye_shape = ellipsoid((0.15, 0.09, 0.19))
eye_frames = [Frame(head, HEAD_C, (0.4 * sx, -1.0, 0.3), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in eye_frames]), EYE, role="eye", tris=1000, voxel=0.014)
shines = []
for f in eye_frames:
    shines.append(f.place(sphere(0.06), (-0.052, -0.075, 0.072)))
    shines.append(f.place(sphere(0.031), (0.058, -0.07, -0.082)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=500, voxel=0.01)

blush = ellipsoid((0.15, 0.04, 0.09))
m.add("Blush", union(*[stick(blush, core, HEAD_C, (0.78 * sx, -0.8, -0.24), sink=0.02) for sx in (1, -1)]),
      BLUSH, role="detail", tris=500, voxel=0.014)

smile = project_curve(painted, bezier((-0.14, -1.0, 1.3), (-0.07, -1.0, 1.23), (0.07, -1.0, 1.23),
                                      (0.14, -1.0, 1.3), 14), (0, -1, 0), inset=0.008)
m.add("Mouth", tube(smile, 0.022), MOUTH, role="detail", tris=400, voxel=0.01)

# zampe piu' corte: abbassa tutto tranne gli zoccoli (le zampe affondano nel corpo); poi scala a ~3 unita'
DROP, S = 0.1, 1.1
for _p in m.parts:
    if _p.name != "Hooves":
        _p.sdf = _p.sdf.translate((0, 0, -DROP))
        if _p.pivot:
            _p.pivot = (_p.pivot[0], _p.pivot[1], _p.pivot[2] - DROP)
    _p.sdf = _p.sdf.scale(S)
    if _p.pivot:
        _p.pivot = tuple(c * S for c in _p.pivot)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
