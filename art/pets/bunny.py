"""Coniglietto (Bunny) - pet Comune."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import Frame, bezier, box, ellipsoid, project_curve, sphere, stick, tube, union  # noqa: E402
from lib.toy import Model  # noqa: E402

WHITE_FUR = (248, 244, 238)
CREAM = (255, 232, 212)
PINK_IN = (255, 178, 198)
PINK_NOSE = (255, 118, 150)
PADS = (255, 160, 184)
BLUSH = (255, 138, 165)
EYE = (42, 28, 44)
MOUTH = (128, 58, 78)
WHITE = (255, 255, 255)

m = Model("Bunny", "pet")

# ------------------------------------------------------------------ corpo seduto + testa paffuta
HEAD_C = (0, -0.05, 1.78)
body = ellipsoid((0.74, 0.68, 0.7), (0, 0.08, 0.76))
head = ellipsoid((0.84, 0.76, 0.7), HEAD_C)
cheeks = union(*[ellipsoid((0.36, 0.3, 0.3), (sx * 0.4, -0.36, 1.6)) for sx in (1, -1)])
muzzle = union(*[sphere(0.13, (sx * 0.1, -0.68, 1.55)) for sx in (1, -1)])
paws = union(*[ellipsoid((0.15, 0.13, 0.16), (sx * 0.16, -0.62, 1.04)) for sx in (1, -1)])
core = union(body, head, k=0.3)
core = union(core, cheeks, k=0.18)
core = union(core, muzzle, k=0.08)
core = union(core, paws, k=0.06)


# zampe posteriori grandi, con la pianta rivolta in avanti (cuscinetti visibili)
def place_foot(shape, sx):
    s = shape.rot(-45, 0, 0).rot(0, 0, 8).translate((0.42, -0.52, 0.336))
    return s if sx > 0 else s.mirrored()


foot_local = ellipsoid((0.24, 0.44, 0.165))
feet = union(place_foot(foot_local, 1), place_foot(foot_local, -1))
core = union(core, feet, k=0.08)
m.add("Body", core, WHITE_FUR, tris=5400)

# pancia e musetto color crema (la pancia esclude zampine e piedi)
belly_region = ellipsoid((0.5, 0.5, 0.5), (0, -0.62, 0.72)).subtract(union(paws, feet).offset(0.04))
muzzle_region = union(*[ellipsoid((0.17, 0.2, 0.14), (sx * 0.1, -0.7, 1.52)) for sx in (1, -1)], k=0.05)
m.add("Cream", core.offset(0.02).intersect(union(belly_region, muzzle_region)), CREAM, role="detail", tris=1300)

# cuscinetti rosa sulle piante dei piedi
pad_local = union(ellipsoid((0.13, 0.17, 0.1), (0, 0.08, -0.165)),
                  *[sphere(0.06, (dx, -0.26, -0.133 + abs(dx) * 0.2)) for dx in (-0.11, 0.0, 0.11)])
pads = union(place_foot(pad_local, 1), place_foot(pad_local, -1))
m.add("Pads", core.offset(0.018).intersect(pads), PADS, role="detail", tris=900, voxel=0.015)

# ------------------------------------------------------------------ orecchie lunghe (animabili)
ear_local = ellipsoid((0.2, 0.09, 0.52), (0, 0, 0.52))
ear_local = ear_local.subtract(ellipsoid((0.11, 0.05, 0.36), (0, -0.1, 0.6)), k=0.04)
inner_local = ear_local.offset(0.016).intersect(ellipsoid((0.125, 0.12, 0.4), (0, -0.07, 0.6)))


def bend(shape, z0, deg_per_unit, axis=0):
    """Piega la parte sopra z0 verso +asse (0=x, 1=y), con angolo proporzionale all'altezza.

    Deformazione dello spazio: la distanza resta approssimata (va bene per pieghe morbide)."""
    k = math.radians(deg_per_unit)

    def fn(p):
        q = p.copy()
        h = np.maximum(p[:, 2] - z0, 0.0)
        c, s = np.cos(k * h), np.sin(k * h)
        u, z = p[:, axis], p[:, 2] - z0
        q[:, axis] = np.where(h > 0, c * u - s * z, u)
        q[:, 2] = np.where(h > 0, s * u + c * z + z0, p[:, 2])
        return q

    return shape.warp(fn, pad=0.25)


def place_ear(shape, sx):
    s = shape.rot(0, 0, 15).rot(0, 12, 0).rot(-8, 0, 0).translate((0.3, 0.0, 2.25))
    return s if sx > 0 else s.mirrored()


# l'orecchio sinistro ha la punta piegata verso l'esterno
for sx, nm, ear, inner in ((1, "EarR", ear_local, inner_local),
                           (-1, "EarL", bend(ear_local, 0.58, 80), bend(inner_local, 0.58, 80))):
    pivot = (sx * 0.3, 0.0, 2.35)
    m.add(nm, place_ear(ear, sx), WHITE_FUR, role="skin", tris=1100, voxel=0.02, group=nm, pivot=pivot)
    m.add(nm + "In", place_ear(inner, sx), PINK_IN, role="detail", tris=600, voxel=0.015, group=nm, pivot=pivot)

# ------------------------------------------------------------------ faccia
eye_shape = ellipsoid((0.16, 0.09, 0.21))
eye_frames = [Frame(head, HEAD_C, (0.4 * sx, -1.0, 0.12), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in eye_frames]), EYE, role="eye", tris=1000, voxel=0.015)
shines = []
for f in eye_frames:
    shines.append(f.place(sphere(0.062), (-0.055, -0.075, 0.08)))
    shines.append(f.place(sphere(0.032), (0.06, -0.07, -0.09)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=500, voxel=0.01)

blush = ellipsoid((0.15, 0.04, 0.09))
m.add("Blush", union(*[stick(blush, core, HEAD_C, (0.74 * sx, -0.85, -0.36), sink=0.02) for sx in (1, -1)]),
      BLUSH, role="detail", tris=500, voxel=0.015)

nose = union(ellipsoid((0.1, 0.06, 0.06), (0, 0, 0.015)), ellipsoid((0.05, 0.05, 0.05), (0, -0.005, -0.035)), k=0.04)
m.add("Nose", Frame(core.offset(0.02), HEAD_C, (0, -1.0, -0.22), sink=0.03).place(nose), PINK_NOSE, role="detail", tris=500,
      voxel=0.012)

# bocca a "omega" sotto il naso (appoggiata sopra la vernice crema del musetto)
painted = core.offset(0.02)


def face_curve(pts2d, inset=0.008):
    return project_curve(painted, [(x, -1.0, z) for x, z in pts2d], (0, -1, 0), inset=inset)


z_n = 1.555
lobe = bezier((0, 0, z_n - 0.05), (-0.012, 0, z_n - 0.115), (-0.115, 0, z_n - 0.115), (-0.15, 0, z_n - 0.055), 12)
stem = face_curve([(0, z_n), (0, z_n - 0.05)])
left = face_curve([(p[0], p[2]) for p in lobe])
right = face_curve([(-p[0], p[2]) for p in lobe])
mouth = union(tube(stem, 0.024), tube(left, 0.024), tube(right, 0.024))

# dentini da castoro
tooth = box((0.044, 0.035, 0.064), round=0.022)
teeth = union(*[stick(tooth, painted, (sx * 0.057, -0.3, z_n - 0.125), (0, -1, 0), sink=0.008) for sx in (1, -1)])
m.add("Mouth", mouth, MOUTH, role="detail", tris=500, voxel=0.01)
m.add("Teeth", teeth, WHITE, role="detail", tris=400, voxel=0.01)

# ------------------------------------------------------------------ codina a batuffolo
TAIL_C = (0, 0.84, 0.46)
puffs = [sphere(0.2, TAIL_C)]
for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1), (0.6, 0.6, 0.5), (-0.6, 0.6, 0.5),
          (0.6, 0.6, -0.5), (-0.6, 0.6, -0.5), (0, 0.7, 0.7), (0.7, 0.2, 0.7), (-0.7, 0.2, 0.7)):
    v = [c / sum(x * x for x in d) ** 0.5 for c in d]
    puffs.append(sphere(0.12, (TAIL_C[0] + v[0] * 0.17, TAIL_C[1] + v[1] * 0.17, TAIL_C[2] + v[2] * 0.17)))
m.add("Tail", union(*puffs, k=0.06), WHITE, role="detail", tris=900, voxel=0.015)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
