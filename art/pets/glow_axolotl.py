"""Axolotl Luminoso (GlowAxolotl) - pet Epico (grotte di cristallo).

Carattere: il maniaco allegro. Occhioni neri con pupille piccolissime che brillano, un sorriso da
guancia a guancia pieno di dentini e le dita unite a punta come chi sta tramando qualcosa. Le branchie
piumate brillano fucsia e azzurro; pancia e pinna sono traslucide.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capsule, ellipsoid, project, project_curve, round_cone,  # noqa: E402
                     sphere, tube, union)
from lib.toy import Model  # noqa: E402

SKIN = (255, 112, 168)
BELLY = (255, 200, 226)
FIN = (255, 172, 222)
GLOW_M = (255, 70, 225)
GLOW_C = (80, 255, 248)
MOUTH = (92, 14, 62)
FRECKLE = (156, 28, 112)
TOOTH = (255, 252, 246)
EYE = (26, 12, 38)
WHITE = (255, 255, 255)


# ============================================================ helper "toy horror" (definiti qui: lib non si tocca)


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


def poly_xz(poly, y0, y1):
    """Regione disegnata nella vista frontale: poligono nel piano XZ estruso lungo Y fra y0 e y1."""
    pts = np.asarray(poly, dtype=np.float32)

    def f(p):
        px, pz = p[:, 0], p[:, 2]
        d = np.full(len(p), np.inf, dtype=np.float32)
        s = np.ones(len(p), dtype=np.float32)
        for i in range(len(pts)):
            vi, vj = pts[i], pts[i - 1]
            ex, ez = vj[0] - vi[0], vj[1] - vi[1]
            wx, wz = px - vi[0], pz - vi[1]
            t = np.clip((wx * ex + wz * ez) / max(ex * ex + ez * ez, 1e-12), 0.0, 1.0)
            d = np.minimum(d, (wx - ex * t) ** 2 + (wz - ez * t) ** 2)
            c1, c2, c3 = pz >= vi[1], pz < vj[1], ex * wz > ez * wx
            s = np.where((c1 & c2 & c3) | (~c1 & ~c2 & ~c3), -s, s)
        return np.maximum(s * np.sqrt(d), np.maximum(y0 - p[:, 1], p[:, 1] - y1))

    return SDF(f, (pts[:, 0].min(), y0, pts[:, 1].min()), (pts[:, 0].max(), y1, pts[:, 1].max()))


def grin(base, upper, lower, y_back, up_teeth=(), down_teeth=(), tooth=(0.06, 0.026), d=0.034):
    """Ghigno: bocca scura fra labbro superiore e inferiore (punti 2D x,z da sinistra a destra) + dentini."""
    region = poly_xz(list(upper) + list(lower[-2:0:-1]), -3.0, y_back)  # gli angoli sono in comune
    mouth = base.offset(d).intersect(region, k=0.006)
    lip = base.offset(d)
    (ux, uz), (lx, lz) = np.array(upper).T, np.array(lower).T
    length, r = tooth
    teeth = []
    for x in up_teeth:
        z = float(np.interp(x, ux, uz))
        b, t = project_curve(lip, [(x, y_back - 0.6, z + 0.012), (x, y_back - 0.6, z - length)], (0, -1, 0), inset=0.004)
        teeth.append(round_cone(b, t, r, 0.006))
    for x in down_teeth:
        z = float(np.interp(x, lx, lz))
        b, t = project_curve(lip, [(x, y_back - 0.6, z - 0.012), (x, y_back - 0.6, z + length * 0.8)], (0, -1, 0),
                             inset=0.004)
        teeth.append(round_cone(b, t, r * 0.85, 0.006))
    return mouth, teeth


def paint(base, region, d=0.022, depth=0.045, k=0.012):
    """Vernice a strato sottile (fra -depth e +d dalla superficie) ritagliata dalla regione: niente grandi
    superfici nascoste, quindi voxel fine a parita' di triangoli. Spessore d + depth >= 2.5 voxel."""
    t = (d + depth) / 2
    return base.offset(d - t).shell(t).intersect(region, k=k)


def flat(shape, kx):
    """Schiaccia una forma lungo X (centrata in x=0) di un fattore kx."""
    return shape.warp(lambda p: p * [[kx, 1.0, 1.0]])


# ============================================================ modello
m = Model("GlowAxolotl", "pet")
PK = 0.01

# testa larghissima e piatta, corpo a pera, zampette, coda piatta
HEAD_C = (0, -0.15, 2.0)
head = ellipsoid((1.0, 0.78, 0.64), HEAD_C)
body = ellipsoid((0.66, 0.6, 0.74), (0, 0.05, 0.86))
core_u = union(head, body, k=0.3)
LEGS = [(sx * 0.4, -0.2) for sx in (1, -1)]
legs = union(*[union(ellipsoid((0.21, 0.27, 0.17), (x, y, 0.17)),
                     *[sphere(0.07, (x + 0.09 * dx, y - 0.25, 0.07)) for dx in (-1.2, -0.4, 0.4, 1.2)], k=0.05)
               for x, y in LEGS])
# braccia: le mani si toccano con la punta delle dita davanti alla pancia
hands = []
for sx in (1, -1):
    arm = tube([(sx * 0.56, -0.16, 1.2), (sx * 0.74, -0.52, 0.98), (sx * 0.27, -0.8, 1.1)], [0.13, 0.115, 0.1])
    palm = ellipsoid((0.12, 0.1, 0.12), (sx * 0.23, -0.82, 1.12))
    fingers = [capsule((sx * 0.2, -0.84 + dy, 1.14), (sx * 0.035, -0.88 + dy * 1.3, 1.33), 0.037)
               for dy in (-0.06, -0.02, 0.02, 0.06)]
    hands.append(union(arm, palm, *fingers, k=0.035))
TAIL_BASE = (0, 0.45, 0.62)
TAIL_PTS = bezier(TAIL_BASE, (0, 1.02, 0.3), (0, 1.62, 0.3), (0, 2.02, 0.58), 16)
TAIL_R = [0.34 - 0.29 * (i / 16) ** 0.9 for i in range(17)]


def swing(s):
    """La coda (piatta, nel piano YZ) ruota rigidamente verso +X attorno alla sua base."""
    return s.rot(0, 0, -28, pivot=TAIL_BASE)


tail = swing(flat(tube(TAIL_PTS, TAIL_R), 1.9))
core = union(core_u, legs, k=0.08)
core = union(core, *hands, k=0.05)
core = union(core, tail, k=0.12)
m.add("Body", core, SKIN, tris=5200)

# pancia traslucida
belly = paint(core_u, ellipsoid((0.46, 0.42, 0.58), (0, -0.52, 0.86)), depth=0.06, k=PK)
m.add("Belly", belly, BELLY, material="Glass", transparency=0.15, role="detail", tris=900, voxel=0.028)

# pinna dorsale e pinna della coda (membrana sottile traslucida)
fin_tail = swing(flat(tube(TAIL_PTS, [r + 0.17 for r in TAIL_R]), 5.5))
fin_back = flat(tube([(0, 0.32, 1.72), (0, 0.56, 1.32), (0, 0.66, 0.92), (0, 0.6, 0.64)], [0.05, 0.11, 0.13, 0.13]), 6.0)
m.add("Fin", union(fin_tail, fin_back, k=0.05), FIN, material="Glass", transparency=0.25, role="detail", tris=1600,
      voxel=0.03)

# branchie piumate: tre steli per lato (alto e basso fucsia, centrale azzurro)
gills = {"M": [], "C": []}
for sx in (1, -1):
    for j, (d, length, col) in enumerate([((0.45, 0.3, 0.85), 0.72, "M"), ((1.0, 0.32, 0.28), 0.78, "C"),
                                          ((0.9, 0.28, -0.32), 0.62, "M")]):
        d = np.array([sx * d[0], d[1], d[2]])
        d = d / np.linalg.norm(d)
        base, _ = project(head, HEAD_C, d + [0, 0.25, 0])
        base = base - d * 0.1
        bend = np.array([0, 0.38, 0.3])
        pts = bezier(tuple(base), tuple(base + d * length * 0.35), tuple(base + d * length * 0.7 + bend * 0.55),
                     tuple(base + d * length * 0.85 + bend), 10)
        stalk = tube(pts, [0.09 - 0.0045 * i for i in range(11)])
        frills = []
        for i in range(3, 11):
            p = np.array(pts[i])
            t = np.subtract(pts[min(i + 1, 10)], pts[i - 1])
            t /= np.linalg.norm(t)
            side = np.cross(t, [0.0, 1.0, 0.0])
            side /= np.linalg.norm(side)
            ln = 0.07 + 0.11 * math.sin(math.pi * (i - 1.5) / 9.5)
            for s in (1, -1):
                tip = p + side * s * ln + t * 0.08
                frills.append(round_cone(tuple(p), tuple(tip), 0.042, 0.033))
        gills[col].append(union(stalk, fast_union(frills), k=0.025))
m.add("GillsMagenta", union(*gills["M"]), GLOW_M, material="Neon", role="glow", tris=2200, voxel=0.027)

# lentiggini fucsia scuro su testa e dorso
rng = np.random.default_rng(5)
spots, centres = [], []
while len(spots) < 16:
    d = rng.normal(size=3)
    d[1] = abs(d[1]) * 0.9 + 0.1
    d[2] = abs(d[2]) + 0.2
    d /= np.linalg.norm(d)
    c = np.array(HEAD_C) if len(spots) < 9 else np.array([0, 0.05, 1.0])
    p, _ = project(core_u, c, d)
    if all(np.linalg.norm(p - q) > 0.22 for q in centres):
        centres.append(p)
        spots.append(sphere(float(rng.uniform(0.05, 0.07)), p))
m.add("Freckles", paint(core_u, fast_union(spots), depth=0.045, k=0.004), FRECKLE, role="detail", tris=500,
      voxel=0.024)

# occhi neri spalancati con pupille minuscole luminose
frames = {sx: Frame(head, HEAD_C, (0.56 * sx, -1.0, 0.28), sink=0.045) for sx in (1, -1)}
EYE_R = (0.165, 0.09, 0.19)
pupils = union(*[frames[sx].place(sphere(0.042), (sx * 0.012, -0.087, 0.0)) for sx in (1, -1)])
m.add("GillsCyan", union(*gills["C"], pupils), GLOW_C, material="Neon", role="glow", tris=1500, voxel=0.024)
m.add("Eyes", union(*[f.place(ellipsoid(EYE_R)) for f in frames.values()]), EYE, role="eye", tris=600, voxel=0.013)
shines = []
for sx, f in frames.items():
    shines.append(f.place(sphere(0.03), (-0.075, -0.074, 0.08)))
    shines.append(f.place(sphere(0.015), (0.065, -0.076, -0.09)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=250, voxel=0.007)

# sorriso da guancia a guancia pieno di dentini
upper = [(-0.64, 1.9), (-0.46, 1.79), (-0.25, 1.74), (0.0, 1.725), (0.25, 1.74), (0.46, 1.79), (0.64, 1.9)]
lower = [(-0.64, 1.9), (-0.46, 1.71), (-0.25, 1.625), (0.0, 1.6), (0.25, 1.625), (0.46, 1.71), (0.64, 1.9)]
Y_BACK = max(project(head, (x, HEAD_C[1], z), (0, -1, 0))[0][1] for x, z in upper) + 0.08
mouth, teeth = grin(head, upper, lower, y_back=Y_BACK,
                    up_teeth=[-0.52, -0.42, -0.32, -0.22, -0.12, -0.04, 0.04, 0.12, 0.22, 0.32, 0.42, 0.52],
                    down_teeth=[-0.4, -0.29, -0.18, -0.07, 0.07, 0.18, 0.29, 0.4], tooth=(0.05, 0.022), d=0.012)
m.add("Mouth", mouth, MOUTH, role="detail", tris=900, voxel=0.016)
m.add("Teeth", union(*teeth), TOOTH, role="detail", tris=1000, voxel=0.008)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
