"""Drago di Lava (Lava Dragon) - pet Leggendario."""
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (Frame, bezier, box, capsule, ellipsoid, prism, project_curve, round_cone, sphere,  # noqa: E402
                     tube, union)
from lib.toy import Model  # noqa: E402

RED = (220, 50, 38)
RED_DARK = (150, 26, 24)
GOLD = (255, 192, 58)
BONE = (255, 236, 196)
MEMBRANE = (255, 132, 44)
LAVA = (255, 112, 20)
FLAME_IN = (255, 214, 64)
EYE = (30, 20, 26)
WHITE = (255, 255, 255)

m = Model("LavaDragon", "pet")

HEAD_C = (0, -0.12, 2.12)
body = ellipsoid((0.95, 0.88, 0.98), (0, 0.06, 1.02))
head = ellipsoid((0.98, 0.86, 0.84), HEAD_C)
snout = ellipsoid((0.54, 0.56, 0.37), (0, -0.86, 1.84))
arms = union(*[capsule((sx * 0.72, -0.3, 1.25), (sx * 0.86, -0.6, 0.95), 0.2) for sx in (1, -1)])
legs = union(*[ellipsoid((0.34, 0.42, 0.26), (sx * 0.5, -0.32, 0.22)) for sx in (1, -1)])
tail = tube(bezier((0, 0.7, 0.62), (0.2, 1.4, 0.45), (0.9, 1.55, 0.55), (1.2, 1.2, 0.95), 14),
            [0.42 - 0.025 * i for i in range(15)])
core = union(body, head, k=0.42)
core = union(core, snout, k=0.25)
core = union(core, arms, legs, tail, k=0.16)
# narici
nostrils = union(sphere(0.055, (0.14, -1.3, 2.05)), sphere(0.055, (-0.14, -1.3, 2.05)))
core = core.subtract(nostrils, k=0.04)
m.add("Body", core, RED, tris=7000)

# pancia a placche: sovrapposizione dorata con solchi orizzontali
belly_region = ellipsoid((0.66, 0.8, 0.72), (0, -0.6, 0.98))
grooves = union(*[box((1.0, 1.0, 0.025), (0, -0.8, z)) for z in (0.62, 0.92, 1.22)])
belly = core.offset(0.02).intersect(belly_region).subtract(grooves)
m.add("Belly", belly, GOLD, role="detail", tris=2200)

# macchie di lava luminose su schiena e testa
lava_spots = union(
    ellipsoid((0.32, 0.3, 0.2), (0.45, 0.55, 1.5)), ellipsoid((0.26, 0.24, 0.18), (-0.5, 0.6, 1.2)),
    ellipsoid((0.22, 0.2, 0.16), (0.05, 0.78, 0.9)), ellipsoid((0.25, 0.22, 0.2), (-0.35, 0.35, 2.75)),
    ellipsoid((0.2, 0.2, 0.16), (0.55, 0.1, 2.65)), ellipsoid((0.2, 0.2, 0.2), (0.7, 1.45, 0.75)),
    ellipsoid((0.18, 0.22, 0.14), (0.78, -0.25, 1.62)), ellipsoid((0.15, 0.2, 0.12), (-0.8, -0.2, 1.58)),
    ellipsoid((0.16, 0.2, 0.12), (0.0, -0.55, 2.82)),
)
m.add("Lava", core.offset(0.018).intersect(lava_spots), LAVA, material="Neon", role="glow", tris=1600)

# corna e artigli color osso
horns = union(*[tube(bezier((sx * 0.42, 0.0, 2.72), (sx * 0.5, 0.25, 3.08), (sx * 0.62, 0.55, 3.22), (sx * 0.78, 0.72, 3.18), 10),
                     [0.16 - 0.013 * i for i in range(11)]) for sx in (1, -1)])
claws = []
for sx in (1, -1):
    for dx in (-0.14, 0.0, 0.14):
        claws.append(round_cone((sx * 0.5 + dx, -0.66, 0.16), (sx * 0.5 + dx * 1.15, -0.8, 0.1), 0.07, 0.025))
_fp = project_curve(core, [(0.2, -1.0, 1.62)], (0, -1, 0), inset=0.05)[0]
fang = round_cone(_fp, (_fp[0], _fp[1] - 0.03, _fp[2] - 0.15), 0.055, 0.015)
m.add("Horns", union(horns, *claws, fang), BONE, role="detail", tris=1800, voxel=0.018)

# creste dorsali
spikes = []
for i, (y, z) in enumerate([(0.55, 2.62), (0.88, 2.15), (0.98, 1.65), (0.95, 1.15), (1.02, 0.72)]):
    r = 0.2 - 0.02 * i
    spikes.append(round_cone((0, y - 0.05, z - 0.05), (0, y + 0.22, z + 0.12), r, 0.04))
m.add("Spikes", union(*spikes, k=0.02), LAVA, material="Neon", role="glow", tris=1500)

# ali (membrana + ossa), animabili
wing_poly = [(0.0, 0.0), (0.7, 0.36), (1.38, 0.84), (1.55, 0.4), (1.3, 0.08), (1.28, -0.3), (0.94, -0.22),
             (0.8, -0.56), (0.48, -0.36), (0.24, -0.5)]
membrane = prism(wing_poly, -0.035, 0.035, round=0.03)
bones = union(tube([(0, 0, 0), (0.7, 0.36, 0), (1.38, 0.84, 0)], [0.08, 0.065, 0.045]),
              tube([(0.7, 0.36, 0), (1.3, 0.08, 0)], [0.055, 0.035]),
              tube([(0.7, 0.36, 0), (0.8, -0.56, 0)], [0.055, 0.035]))
def place_wing(shape, sx):
    s = shape.rot(90, 0, 0).rot(0, 0, 38).rot(0, -24, 0).translate((0.42, 0.58, 1.86))
    return s if sx > 0 else s.mirrored()
for sx, nm in ((1, "WingR"), (-1, "WingL")):
    m.add(nm, place_wing(membrane, sx), MEMBRANE, role="detail", tris=1200, voxel=0.018, group=nm,
          pivot=(sx * 0.42, 0.58, 1.86))
    m.add(nm + "Bone", place_wing(bones, sx), RED_DARK, role="detail", tris=900, voxel=0.018, group=nm,
          pivot=(sx * 0.42, 0.58, 1.86))

# fiamma sulla punta della coda
tip = (1.25, 1.12, 1.05)
flame_out = union(sphere(0.3, tip), round_cone(tip, (1.42, 1.0, 1.75), 0.3, 0.04), k=0.1)
flame_in = union(sphere(0.18, (tip[0] - 0.04, tip[1] - 0.1, tip[2] + 0.02)),
                 round_cone((tip[0] - 0.04, tip[1] - 0.1, tip[2] + 0.02), (1.32, 0.98, 1.5), 0.18, 0.03), k=0.08)
m.add("Flame", flame_out, LAVA, material="Neon", role="glow", tris=1200)
m.add("FlameCore", flame_in, FLAME_IN, material="Neon", role="glow", tris=800)

# occhi con riflessi
eye_shape = ellipsoid((0.2, 0.1, 0.26))
frames = [Frame(head, HEAD_C, (0.4 * sx, -1.0, 0.24), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in frames]), EYE, role="eye", tris=1000, voxel=0.015)
shines = []
for f in frames:
    shines.append(f.place(sphere(0.072), (-0.06, -0.085, 0.1)))
    shines.append(f.place(sphere(0.036), (0.075, -0.08, -0.11)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=500, voxel=0.01)
# bocca sorridente sul muso
mouth_pts = project_curve(core, bezier((0.32, -1.0, 1.72), (0.16, -1.0, 1.6), (-0.16, -1.0, 1.6), (-0.32, -1.0, 1.72), 14),
                          (0, -1, 0), inset=0.01)
mouth = tube(mouth_pts, 0.04)
m.add("Mouth", mouth, RED_DARK, role="detail", tris=600, voxel=0.012)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
