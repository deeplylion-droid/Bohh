"""Volpacchiotto (FoxKit) - pet Non comune."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (Frame, bezier, box, capsule, ellipsoid, prism, project_curve, round_cone, sphere,  # noqa: E402
                     stick, tube, union)
from lib.toy import Model  # noqa: E402

ORANGE = (240, 126, 40)
WHITE_FUR = (255, 248, 238)
CREAM_IN = (255, 222, 184)
DARK = (58, 38, 34)
NOSE = (34, 26, 30)
EYE = (30, 20, 26)
WHITE = (255, 255, 255)
BLUSH = (255, 130, 148)
MOUTH = (92, 48, 40)

m = Model("FoxKit", "pet")


def tri_plate(poly, t, r):
    """Lastra con contorno poligonale nel piano XZ (spessore 2t lungo Y)."""
    return prism(poly, -t, t, round=r).rot(90, 0, 0)


# ------------------------------------------------------------------ corpo seduto e testa con guance a ciuffi
HEAD_C = (0, -0.06, 1.82)
body = ellipsoid((0.72, 0.68, 0.74), (0, 0.1, 0.8))
head = ellipsoid((0.84, 0.74, 0.7), HEAD_C)
ruffs = union(*[round_cone((sx * 0.56, -0.3, 1.58), (sx * 0.82, -0.26, 1.34), 0.2, 0.06) for sx in (1, -1)])
muzzle = ellipsoid((0.28, 0.27, 0.19), (0, -0.72, 1.58))
front_legs = union(*[union(capsule((sx * 0.28, -0.4, 0.8), (sx * 0.3, -0.5, 0.2), 0.125),
                           sphere(0.14, (sx * 0.3, -0.56, 0.16)), k=0.06) for sx in (1, -1)])
haunches = union(*[ellipsoid((0.32, 0.42, 0.34), (sx * 0.46, 0.06, 0.4)) for sx in (1, -1)])
hind_feet = union(*[ellipsoid((0.14, 0.24, 0.1), (sx * 0.58, -0.2, 0.12)) for sx in (1, -1)])

ear_local = tri_plate([(-0.28, 0.0), (0.28, 0.0), (0.0, 0.8)], 0.08, 0.06)


def place_ear(shape, sx):
    s = shape.rot(0, 0, 14).rot(0, 22, 0).rot(-8, 0, 0).translate((0.42, 0.0, 2.24))
    return s if sx > 0 else s.mirrored()


ears = union(place_ear(ear_local, 1), place_ear(ear_local, -1))
core = union(body, head, k=0.32)
core = union(core, ruffs, k=0.1)
core = union(core, muzzle, k=0.14)
core = union(core, haunches, k=0.12)
core = union(core, front_legs, k=0.08)
core = union(core, hind_feet, k=0.08)
core = union(core, ears, k=0.08)
m.add("Body", core, ORANGE, tris=6200)
painted = core.offset(0.02)


def paint(region, t=0.02, depth=0.06):
    """Vernice sottile che segue la superficie (solo uno strato vicino alla pelle: niente facce interne inutili)."""
    return core.offset(t).intersect(region).subtract(core.offset(-depth))


# muso, guance a ciuffi e petto bianchi
cheek = ellipsoid((0.33, 0.42, 0.17)).rot(0, -28, 0).translate((0.47, -0.44, 1.47))  # sale verso l'esterno
white_region = union(ellipsoid((0.3, 0.42, 0.24), (0, -0.84, 1.5)), cheek, cheek.mirrored(),
                     ellipsoid((0.3, 0.4, 0.33), (0, -0.66, 1.14)), k=0.1)
white_region = white_region.subtract(front_legs.offset(0.03))
m.add("White", paint(white_region), WHITE_FUR, role="detail", tris=1800, voxel=0.022)

# interno delle orecchie crema e punte scure
inner_local = box((0.4, 0.2, 0.5), (0, -0.2, 0.25)).intersect(
    tri_plate([(-0.15, 0.1), (0.15, 0.1), (0.0, 0.56)], 0.3, 0.05))
tip_local = box((0.5, 0.3, 0.2), (0, 0, 0.75))
ear_in = union(place_ear(inner_local, 1), place_ear(inner_local, -1))
ear_tip = union(place_ear(tip_local, 1), place_ear(tip_local, -1))
m.add("EarIn", paint(ear_in, t=0.018, depth=0.04), CREAM_IN, role="detail", tris=600, voxel=0.014)
m.add("EarTips", paint(ear_tip, depth=0.04), DARK, role="detail", tris=600, voxel=0.014)

# calzini neri: zampe anteriori fino a meta' e punta dei piedi posteriori
socks_region = union(*[box((0.2, 0.22, 0.18), (sx * 0.3, -0.54, 0.18)) for sx in (1, -1)],
                     *[ellipsoid((0.17, 0.13, 0.13), (sx * 0.58, -0.38, 0.12)) for sx in (1, -1)])
m.add("Socks", paint(socks_region), DARK, role="detail", tris=1000, voxel=0.02)

# ------------------------------------------------------------------ codone gonfio con punta bianca (scodinzola)
tail_pts = bezier((0.22, 0.52, 0.48), (0.85, 1.02, 0.35), (1.18, 0.86, 1.15), (0.9, 0.62, 1.72), 18)
tail_r = [max(0.05, 0.17 + 0.23 * math.sin(math.pi * t * 1.1) - 0.12 * t) for t in np.linspace(0, 1, 19)]
tail = tube(tail_pts, tail_r)
TAIL_PIVOT = (0.25, 0.55, 0.52)
m.add("Tail", tail, ORANGE, role="skin", tris=1800, voxel=0.02, group="Tail", pivot=TAIL_PIVOT)
m.add("TailTip", tail.offset(0.02).intersect(sphere(0.36, tail_pts[-2])), WHITE_FUR, role="detail", tris=700,
      voxel=0.015, group="Tail", pivot=TAIL_PIVOT)

# ------------------------------------------------------------------ faccia
eye_shape = ellipsoid((0.15, 0.09, 0.2))
eye_frames = [Frame(head, HEAD_C, (0.4 * sx, -1.0, 0.15), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in eye_frames]), EYE, role="eye", tris=1000, voxel=0.014)
shines = []
for f in eye_frames:
    shines.append(f.place(sphere(0.06), (-0.052, -0.075, 0.075)))
    shines.append(f.place(sphere(0.031), (0.058, -0.07, -0.085)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=500, voxel=0.01)

nose = union(ellipsoid((0.095, 0.065, 0.06), (0, 0, 0.012)), ellipsoid((0.05, 0.05, 0.045), (0, -0.005, -0.03)), k=0.04)
m.add("Nose", Frame(painted, (0, -0.72, 1.6), (0, -1.0, 0.3), sink=0.03).place(nose), NOSE, role="detail",
      tris=450, voxel=0.011, reflectance=0.08)

blush = ellipsoid((0.14, 0.04, 0.085))
m.add("Blush", union(*[stick(blush, painted, HEAD_C, (0.74 * sx, -0.82, -0.26), sink=0.018) for sx in (1, -1)]),
      BLUSH, role="detail", tris=450, voxel=0.013)

lobe = bezier((0, 0, 1.5), (-0.01, 0, 1.44), (-0.09, 0, 1.43), (-0.12, 0, 1.48), 10)
mouth_l = project_curve(painted, [(p[0], -1.0, p[2]) for p in lobe], (0, -1, 0), inset=0.008)
mouth_r = project_curve(painted, [(-p[0], -1.0, p[2]) for p in lobe], (0, -1, 0), inset=0.008)
stem = project_curve(painted, [(0, -1.0, 1.55), (0, -1.0, 1.5)], (0, -1, 0), inset=0.008)
m.add("Mouth", union(tube(mouth_l, 0.02), tube(mouth_r, 0.02), tube(stem, 0.02)), MOUTH, role="detail", tris=450,
      voxel=0.01)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
