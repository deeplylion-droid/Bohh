"""Marmotta (Marmot) - pet Raro: marmotta paffuta in piedi che stringe una stella alpina."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (Frame, bezier, box, ellipsoid, project, project_curve, round_cone, sphere,  # noqa: E402
                     stick, tube, union)
from lib.toy import Model  # noqa: E402

FUR = (222, 154, 80)
FUR_DARK = (170, 104, 52)
CREAM = (255, 230, 186)
PAW = (92, 58, 44)
NOSE = (66, 40, 38)
TOOTH = (255, 252, 242)
EYE = (30, 22, 28)
WHITE = (255, 255, 255)
BLUSH = (255, 124, 140)
PETAL = (252, 252, 246)
FLOWER_C = (255, 206, 46)
STEM = (104, 172, 74)

m = Model("Marmot", "pet")

# ---------------------------------------------------------------- corpo a pera + testa con guance paffute
HEAD_C = (0, -0.08, 2.18)
head = ellipsoid((0.86, 0.78, 0.74), HEAD_C)
cheeks = union(*[ellipsoid((0.42, 0.4, 0.36), (sx * 0.44, -0.32, 1.98)) for sx in (1, -1)])
muzzle = ellipsoid((0.34, 0.26, 0.24), (0, -0.66, 1.98))
head_full = union(union(head, cheeks, k=0.2), muzzle, k=0.16)
body = ellipsoid((0.98, 0.88, 0.95), (0, 0.06, 1.02))
haunch = union(*[ellipsoid((0.42, 0.5, 0.36), (sx * 0.56, -0.12, 0.42)) for sx in (1, -1)])
torso = union(body, haunch, k=0.25)
core0 = union(torso, head_full, k=0.35)
EAR_C = [(sx * 0.56, 0.0, 2.72) for sx in (1, -1)]
ears = union(*[ellipsoid((0.2, 0.1, 0.18)).rot(0, 0, -sx * 18).rot(0, sx * 22, 0).translate(c)
               for sx, c in zip((1, -1), EAR_C)])

# braccine che arrivano davanti alla pancia (le mani scure stringono il gambo)
HANDS = [(sx * 0.13, -0.96, 1.0) for sx in (1, -1)]
arms = union(*[tube([(sx * 0.66, -0.4, 1.5), (sx * 0.52, -0.79, 1.2), (sx * 0.15, -0.95, 1.0)], [0.16, 0.14, 0.11])
               for sx in (1, -1)])
core = union(core0, arms, k=0.06)
m.add("Body", core, FUR, tris=5200)

# pancia e muso color crema + interno delle orecchie
PK = 0.012  # bordo morbido delle "vernici": spigolo pulito dopo marching cubes e decimazione
belly = core0.offset(0.022).intersect(ellipsoid((0.66, 0.62, 0.8), (0, -0.62, 1.0)), k=PK)
snout_paint = core0.offset(0.022).intersect(ellipsoid((0.4, 0.36, 0.29), (0, -0.84, 1.96)), k=PK)
inner_ears = union(*[Frame(ears, c, (sx * 0.3, -1.0, 0.05), sink=0.035).place(ellipsoid((0.11, 0.04, 0.1)))
                     for sx, c in zip((1, -1), EAR_C)])
m.add("Belly", union(belly, snout_paint, inner_ears), CREAM, role="detail", tris=1900, voxel=0.02)

# orecchie e coda folta piu' scure
tail = tube(bezier((0.12, 0.78, 0.34), (0.3, 1.3, 0.16), (0.56, 1.58, 0.44), (0.46, 1.42, 0.9), 12),
            [0.2, 0.22, 0.24, 0.26, 0.27, 0.27, 0.27, 0.26, 0.25, 0.23, 0.21, 0.19, 0.16])
m.add("Markings", union(ears, tail), FUR_DARK, role="detail", tris=1400)

# mani e piedi scuri
hands = union(*[ellipsoid((0.13, 0.12, 0.12), h) for h in HANDS])
feet = []
for sx in (1, -1):
    x = sx * 0.42
    toes = [sphere(0.075, (x + dx, -0.9, 0.08)) for dx in (-0.12, 0.0, 0.12)]
    feet.append(union(ellipsoid((0.25, 0.33, 0.13), (x, -0.62, 0.13)), *toes, k=0.06))
m.add("Paws", union(hands, *feet), PAW, role="detail", tris=1300)

# naso e boccuccia a "w"
painted = core0.offset(0.022)  # superficie della vernice crema del muso
nose_f = Frame(painted, (0, -0.66, 1.98), (0, -1.0, 0.55), sink=0.03)
nose = nose_f.place(union(ellipsoid((0.1, 0.065, 0.06)), ellipsoid((0.05, 0.05, 0.05), (0, 0.0, -0.035)), k=0.04))
mouth_2d = ([(0.0, 2.0), (0.0, 1.935)]
            + [(x, z) for x, z in [(-0.03, 1.9), (-0.07, 1.89), (-0.11, 1.9), (-0.14, 1.93)]])
mouth_l = project_curve(painted, [(x, -0.5, z) for x, z in mouth_2d], (0, -1, 0), inset=0.006)
mouth_r = project_curve(painted, [(-x, -0.5, z) for x, z in mouth_2d[1:]], (0, -1, 0), inset=0.006)
mouth = union(tube(mouth_l, 0.022), tube(mouth_r, 0.022))
m.add("Nose", union(nose, mouth), NOSE, role="detail", tris=700, voxel=0.012)

# due dentoni
tp, tn = project(painted, (0, -0.5, 1.86), (0, -1, 0))
teeth = union(*[box((0.046, 0.028, 0.082), (0, 0, 0), round=0.024).rot(-8, 0, 0)
                .translate((sx * 0.049, tp[1] - 0.022, 1.845)) for sx in (1, -1)])
m.add("Teeth", teeth, TOOTH, role="detail", tris=500, voxel=0.01)

# occhioni lucidi
eye_shape = ellipsoid((0.15, 0.09, 0.19))
frames = [Frame(core0, HEAD_C, (0.42 * sx, -1.0, 0.16), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in frames]), EYE, role="eye", tris=900, voxel=0.014)
shines = []
for f in frames:
    shines.append(f.place(sphere(0.058), (-0.05, -0.075, 0.075)))
    shines.append(f.place(sphere(0.03), (0.055, -0.07, -0.085)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=450, voxel=0.01)

blush = ellipsoid((0.15, 0.04, 0.09))
m.add("Blush", union(*[stick(blush, core0, HEAD_C, (sx * 0.78, -0.8, -0.3), sink=0.018) for sx in (1, -1)]),
      BLUSH, role="detail", tris=450, voxel=0.013)

# ---------------------------------------------------------------- stella alpina (modellata con fronte +Z locale)
FLOWER_C_POS = (0.0, -1.2, 1.36)


def cup(shape, k):
    """Incurva verso l'alto (+Z locale) le punte di una forma piatta."""
    return shape.warp(lambda p: p - (p[:, 0:1] ** 2 + p[:, 1:2] ** 2) * [[0.0, 0.0, k]], pad=0.08)


def place_flower(shape):
    return shape.rot(58, 0, 0).rot(0, 0, 6).translate(FLOWER_C_POS)


def petal(length, width, thick):
    """Petalo lanceolato (piu' largo a 40% della lunghezza), schiacciato in Z."""
    shape = union(round_cone((0, 0, 0), (0, 0.4 * length, 0), 0.6 * width, width),
                  round_cone((0, 0.4 * length, 0), (0, length, 0), width, 0.28 * width), k=0.02)
    return shape.warp(lambda p: p * [[1.0, 1.0, width / thick]])


outer = cup(union(*[petal(0.4, 0.085, 0.032).rot(0, 0, i * 45) for i in range(8)], k=0.02), 0.65)
inner = cup(union(*[petal(0.26, 0.066, 0.028).rot(0, 0, 22.5 + i * 45) for i in range(8)], k=0.02), 1.0)
m.add("Petals", place_flower(union(outer, inner.translate((0, 0, 0.04)))), PETAL, role="detail", tris=1500,
      voxel=0.012)
import math  # noqa: E402
florets = [sphere(0.065, (0, 0, 0.11))] + [sphere(0.055, (0.085 * math.cos(a), 0.085 * math.sin(a), 0.085))
                                          for a in [i * math.pi / 3 for i in range(6)]]
m.add("FlowerCentre", place_flower(union(*florets, k=0.02)), FLOWER_C, role="detail", tris=600, voxel=0.01)
stem = tube([FLOWER_C_POS, (0.0, -1.06, 1.02), (0.0, -1.0, 0.82)], [0.045, 0.042, 0.036])
m.add("Stem", stem, STEM, role="detail", tris=400, voxel=0.012)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
