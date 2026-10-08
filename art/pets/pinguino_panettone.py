"""Pinguino Panettone - pet Mitico (creatura meme originale)."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capsule, cylinder, ellipsoid, project, revolve,  # noqa: E402
                     round_cone, sphere, tube, union)
from lib.toy import Model  # noqa: E402

PAPER = (204, 30, 44)
PAPER_GOLD = (255, 200, 64)
CRUST = (196, 118, 44)
CRUST_DARK = (128, 64, 26)
SUGAR = (255, 252, 244)
BLACK = (38, 40, 58)
WHITE = (255, 255, 255)
ORANGE = (255, 140, 30)
EYE = (24, 20, 30)
BLUSH = (255, 120, 150)
CHERRY = (230, 20, 50)
RAISIN = (92, 40, 52)
CANDIED = (255, 150, 30)

m = Model("PinguinoPanettone", "pet")


def pleated_cylinder(r: float, z0: float, z1: float, pleats: int, depth: float) -> SDF:
    def prof_r(theta):
        return r + depth * (0.5 + 0.5 * np.cos(pleats * theta))

    def f(p):
        theta = np.arctan2(p[:, 1], p[:, 0])
        rho = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2)
        d_side = rho - prof_r(theta)
        d_cap = np.maximum(z0 - p[:, 2], p[:, 2] - z1)
        a = np.maximum(d_side, 0)
        b = np.maximum(d_cap, 0)
        return np.minimum(np.maximum(d_side, d_cap), 0) + np.sqrt(a * a + b * b)

    e = r + depth
    return SDF(f, (-e, -e, z0), (e, e, z1))


# pirottino di carta pieghettato
paper = pleated_cylinder(0.9, 0.14, 1.72, 28, 0.035)
m.add("Paper", paper, PAPER, role="skin", tris=5000, voxel=0.02)
rim = pleated_cylinder(0.92, 1.56, 1.74, 28, 0.035).subtract(cylinder((0, 0, 1.3), (0, 0, 2.0), 0.82))
rim = union(rim, pleated_cylinder(0.92, 0.14, 0.3, 28, 0.035).subtract(cylinder((0, 0, 0.0), (0, 0, 0.5), 0.82)))
m.add("PaperRim", rim, PAPER_GOLD, role="detail", tris=2500, voxel=0.02)

# cupola del panettone che deborda dalla carta
def dome_profile(z):
    t = np.clip((z - 1.66) / 0.78, 0, 1)
    return 1.0 * np.sqrt(np.clip(1 - t ** 2.4, 0, 1))

dome = revolve(dome_profile, 1.02, 1.66, 2.44)
dome = union(dome, cylinder((0, 0, 1.55), (0, 0, 1.8), 0.86), k=0.08)
m.add("Dome", dome, CRUST, role="skin", tris=4500, voxel=0.02)
top_crust = dome.offset(0.016).intersect(sphere(1.0, (0, 0, 2.95)))
m.add("DomeTop", top_crust, CRUST_DARK, role="detail", tris=2500, voxel=0.02)

# zucchero a velo, uvetta e canditi sulla crosta
rng = np.random.default_rng(7)
sugar, raisins, candied = [], [], []
for i in range(150):
    a = rng.uniform(0, 2 * math.pi)
    up = rng.uniform(-0.1, 1.4)
    p, n = project(dome, (0, 0, 1.9), (math.cos(a), math.sin(a), up))
    if np.hypot(p[0], p[1]) < 0.62 or p[2] < 1.75:
        continue  # lascia libero il collo del pinguino
    kind = rng.random()
    if kind < 0.7:
        sugar.append(sphere(rng.uniform(0.03, 0.05), p + n * 0.005))
    elif kind < 0.86:
        raisins.append(ellipsoid((0.07, 0.07, 0.05), p))
    else:
        candied.append(ellipsoid((0.08, 0.06, 0.05), p))
m.add("Sugar", union(*sugar), SUGAR, role="detail", tris=1500, voxel=0.012)
m.add("Raisins", union(*raisins), RAISIN, role="detail", tris=900, voxel=0.014)
m.add("Candied", union(*candied), CANDIED, role="detail", tris=700, voxel=0.014)

# pinguino che spunta dalla cupola
HEAD_C = (0, -0.04, 2.84)
head = ellipsoid((0.74, 0.7, 0.68), HEAD_C)
neck = cylinder((0, 0, 2.2), (0, 0, 2.62), 0.56)
penguin = union(head, neck, k=0.2)
m.add("Head", penguin, BLACK, role="skin", tris=4000, voxel=0.02)
mask = union(ellipsoid((0.36, 0.5, 0.42), (0.22, -0.5, 2.79)), ellipsoid((0.36, 0.5, 0.42), (-0.22, -0.5, 2.79)),
             ellipsoid((0.4, 0.5, 0.3), (0, -0.5, 2.52)), k=0.12)
m.add("Face", penguin.offset(0.02).intersect(mask), WHITE, role="detail", tris=2000, voxel=0.016)

# becco, occhi, guance
beak = union(ellipsoid((0.2, 0.2, 0.1), (0, -0.07, 0.02)), ellipsoid((0.14, 0.13, 0.07), (0, -0.04, -0.09)), k=0.04)
m.add("Beak", Frame(head, HEAD_C, (0, -1.0, -0.12), sink=0.07).place(beak), ORANGE, role="detail", tris=900, voxel=0.014)
frames = [Frame(head, HEAD_C, (0.38 * sx, -1.0, 0.12), sink=0.03) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(ellipsoid((0.13, 0.08, 0.17))) for f in frames]), EYE, role="eye", tris=900, voxel=0.013)
shines = []
for f in frames:
    shines.append(f.place(sphere(0.05), (-0.04, -0.065, 0.065)))
    shines.append(f.place(sphere(0.025), (0.05, -0.06, -0.07)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=400, voxel=0.01)
m.add("Blush", union(*[Frame(penguin.offset(0.02), HEAD_C, (0.6 * sx, -0.85, -0.26), sink=0.012).place(ellipsoid((0.13, 0.035, 0.08)))
                       for sx in (1, -1)]), BLUSH, role="detail", tris=400, voxel=0.013)

# ciliegina candita in testa
cherry = union(sphere(0.2, (0.12, 0.05, 3.62)), tube(bezier((0.12, 0.05, 3.78), (0.14, 0.05, 3.96), (0.26, 0.08, 4.04), (0.34, 0.1, 4.0), 8), 0.025))
m.add("Cherry", cherry, CHERRY, material="Glass", role="glow", tris=900, voxel=0.012)

# pinne che escono dalla carta (animabili) e zampe
fl = ellipsoid((0.14, 0.32, 0.5), (0, 0, 0)).rot(0, 38, 0).translate((1.05, -0.05, 1.12))
m.add("FlipperR", fl, BLACK, role="skin", tris=900, group="FlipperR", pivot=(0.88, -0.05, 1.38))
m.add("FlipperL", fl.mirrored(), BLACK, role="skin", tris=900, group="FlipperL", pivot=(-0.88, -0.05, 1.38))
feet = union(*[union(ellipsoid((0.3, 0.38, 0.12), (sx * 0.38, -0.55, 0.1)),
                     *[capsule((sx * 0.38, -0.6, 0.08), (sx * 0.38 + dx, -0.92, 0.07), 0.08) for dx in (-0.16, 0, 0.16)], k=0.08)
               for sx in (1, -1)])
m.add("Feet", feet, ORANGE, role="detail", tris=1400)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
