"""Volpe di Ghiaccio (FrostFox) - pet Epico (grotte di cristallo).

Carattere: la regina di ghiaccio, fredda e altezzosa. Occhi a mandorla socchiusi con pupille a fessura
luminose, sorrisetto gelido da un lato, "cuciture" di brina luminose sulle guance. Spuntoni di ghiaccio
lungo la schiena, calzini blu notte e coda folta avvolta davanti alle zampe con la punta di ghiaccio.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capsule, ellipsoid, project, project_curve, rot_matrix,  # noqa: E402
                     round_cone, sphere, tube, union)
from lib.toy import Model  # noqa: E402

FUR = (176, 210, 246)
WHITE_FUR = (248, 252, 255)
NAVY = (40, 48, 108)
ICE = (176, 238, 255)
GLOW = (90, 250, 255)
EYE = (22, 26, 62)
MOUTH = (28, 32, 74)
WHITE = (255, 255, 255)


# ============================================================ helper "toy horror" (definiti qui: lib non si tocca)
def normal_at(sdf, p, eps=1e-3):
    """Normale uscente della superficie di sdf vicino al punto p."""
    p = np.asarray(p, dtype=np.float32)
    g = np.array([sdf((p + e)[None])[0] - sdf((p - e)[None])[0] for e in np.eye(3, dtype=np.float32) * eps])
    return g / max(float(np.linalg.norm(g)), 1e-9)


def resample(pts, step):
    """Ricampiona una polilinea a passo costante."""
    pts = np.asarray(pts, dtype=np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    acc = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for s in np.linspace(0.0, acc[-1], max(int(round(acc[-1] / step)), 1) + 1):
        i = int(min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1))
        f = (s - acc[i]) / max(seg[i], 1e-9)
        out.append(pts[i] * (1 - f) + pts[i + 1] * f)
    return np.array(out)


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


def stitches(base, pts, step=0.09, length=0.07, r=0.016, cross=True):
    """Cucitura: trattini corti lungo una curva gia' appoggiata sulla superficie (cross: punti a cavallo)."""
    q = resample(pts, step)
    dashes = []
    for i, p in enumerate(q):
        t = q[min(i + 1, len(q) - 1)] - q[max(i - 1, 0)]
        n = normal_at(base, p)
        d = np.cross(n, t) if cross else t
        d = d / np.linalg.norm(d)
        dashes.append(capsule(tuple(p - d * length / 2), tuple(p + d * length / 2), r))
    return fast_union(dashes)


def lid_shape(radii, cut, slope=0.0, grow=0.016, k=0.012):
    """Palpebra pesante (coordinate locali del Frame): calotta dell'occhio ingrandito sopra z = cut + slope*x."""
    a, b, c = radii
    nrm = math.sqrt(1.0 + slope * slope)
    above = SDF(lambda p: (cut + slope * p[:, 0] - p[:, 2]) / nrm, (-1, -1, -1), (1, 1, 1))
    return ellipsoid((a + grow, b + grow, c + grow)).intersect(above, k=k)


def surface_tube(base, pts2d, radii, y=-0.3, inset=0.0, direction=(0, -1, 0)):
    """Tubo (sopracciglio, bocca) disegnato nella vista frontale e appoggiato sulla superficie."""
    return tube(project_curve(base, [(x, y, z) for x, z in pts2d], direction, inset=inset), radii)


def paint(base, region, d=0.022, depth=0.045, k=0.012):
    """Vernice a strato sottile (fra -depth e +d dalla superficie) ritagliata dalla regione: niente grandi
    superfici nascoste, quindi voxel fine a parita' di triangoli. Spessore d + depth >= 2.5 voxel."""
    t = (d + depth) / 2
    return base.offset(d - t).shell(t).intersect(region, k=k)


def crystal(length, radius, tip=0.32, sides=6):
    """Cristallo sfaccettato lungo +Z (base in z=0): prisma regolare con punta piramidale."""
    normals = np.array([[math.cos(2 * math.pi * i / sides), math.sin(2 * math.pi * i / sides)] for i in range(sides)],
                       dtype=np.float32)
    apothem = radius * math.cos(math.pi / sides)
    z_tip = length * (1 - tip)
    slope = apothem / (length - z_tip)
    k = 1.0 / math.sqrt(1.0 + slope * slope)

    def f(p):
        side = (p[:, :2] @ normals.T).max(axis=1)
        d = np.maximum(side - apothem, (side - apothem + slope * (p[:, 2] - z_tip)) * k)
        return np.maximum(d, -p[:, 2])

    return SDF(f, (-radius, -radius, 0.0), (radius, radius, length))


def orient(shape, base, direction, spin=0.0):
    """Porta l'asse +Z della forma lungo direction, con la base nel punto base."""
    d = np.asarray(direction, dtype=np.float64)
    d = d / np.linalg.norm(d)
    ax = np.cross([0.0, 0.0, 1.0], d)
    s = float(np.linalg.norm(ax))
    if spin:
        shape = shape.rot(0, 0, spin)
    if s > 1e-6:
        shape = shape.rotate(rot_matrix(ax, math.degrees(math.atan2(s, d[2]))))
    return shape.translate(base)


def flat_y(shape, ky):
    """Schiaccia una forma (centrata in y=0) lungo Y."""
    return shape.warp(lambda p: p * [[1.0, ky, 1.0]])


# ============================================================ modello
m = Model("FrostFox", "pet")
PK = 0.01

# corpo seduto e slanciato
torso = ellipsoid((0.56, 0.62, 0.78), (0, 0.12, 0.96))
haunch = union(*[ellipsoid((0.36, 0.5, 0.36), (sx * 0.4, 0.22, 0.38)) for sx in (1, -1)])
FRONT_LEGS = []
for sx in (1, -1):
    x = sx * 0.28
    toes = [sphere(0.06, (x + 0.07 * dx, -0.66, 0.065)) for dx in (-1.2, -0.4, 0.4, 1.2)]
    FRONT_LEGS.append(union(round_cone((sx * 0.26, -0.26, 0.98), (x, -0.42, 0.18), 0.145, 0.125),
                            ellipsoid((0.17, 0.22, 0.12), (x, -0.5, 0.12)), *toes, k=0.05))
hind = union(*[ellipsoid((0.17, 0.27, 0.11), (sx * 0.55, -0.12, 0.11)) for sx in (1, -1)])
neck = capsule((0, -0.04, 1.36), (0, -0.22, 1.8), 0.3)
HEAD_C = (0, -0.28, 2.12)
skull = ellipsoid((0.64, 0.56, 0.52), HEAD_C)
snout = round_cone((0, -0.62, 2.0), (0, -1.1, 1.93), 0.27, 0.1)
ruffs = union(*[round_cone((sx * 0.46, -0.44, 1.92), (sx * 0.8, -0.38, 1.72), 0.21, 0.05) for sx in (1, -1)])
head = union(union(skull, snout, k=0.16), ruffs, k=0.1)
EAR_C = [(sx * 0.34, -0.16, 2.46) for sx in (1, -1)]
ears = union(*[flat_y(round_cone((0, 0, 0), (0, 0, 0.64), 0.25, 0.035), 2.3).rot(0, sx * 18, 0).translate(c)
               for sx, c in zip((1, -1), EAR_C)])
core_u = union(union(torso, haunch, k=0.22), neck, k=0.2)
core_u = union(core_u, head, k=0.2)
core_u = union(core_u, *FRONT_LEGS, hind, k=0.06)

# coda folta avvolta davanti alle zampe (lato +X), punta bianca con cristalli di ghiaccio
N = 30
TAIL = bezier((0.15, 0.7, 0.34), (1.05, 1.15, 0.26), (1.25, 0.15, 0.3), (0.72, -0.5, 0.32), N)
tail = tube(TAIL, [0.17 + 0.2 * math.sin(math.pi * min(i / N / 0.92, 1.0) ** 0.85) for i in range(N + 1)])

# occhi a mandorla scuri, palpebre pesanti un po' inclinate (sguardo altezzoso)
frames = {sx: Frame(head, HEAD_C, (0.44 * sx, -1.0, 0.22), sink=0.045) for sx in (1, -1)}
EYE_R = (0.145, 0.08, 0.13)
eye_local = ellipsoid(EYE_R)
lids = union(*[frames[sx].place(lid_shape(EYE_R, 0.0, -sx * 0.18).rot(0, -sx * 14, 0)) for sx in (1, -1)])
core = union(core_u, ears, k=0.05)
core = union(core, tail, k=0.1)
core = union(core, lids)
m.add("Body", core, FUR, tris=5200)

# bianco: muso, guance, petto, interno orecchie, punta della coda
mask = union(ellipsoid((0.3, 0.6, 0.24), (0, -0.85, 1.86)),
             *[ellipsoid((0.3, 0.4, 0.22), (sx * 0.55, -0.45, 1.8)) for sx in (1, -1)],
             ellipsoid((0.36, 0.4, 0.55), (0, -0.48, 1.25)))
inner_ears = paint(ears, union(*[ellipsoid((0.14, 0.12, 0.2)).translate((0, -0.1, 0.33)).rot(0, sx * 18, 0).translate(c)
                                 for sx, c in zip((1, -1), EAR_C)]), depth=0.035)
tail_tip = paint(tail, sphere(0.42, TAIL[-1]), depth=0.06)
m.add("White", union(paint(core_u, mask, depth=0.06), tail_tip), WHITE_FUR, role="detail", tris=2000, voxel=0.032)
m.add("EarInner", inner_ears, WHITE_FUR, role="detail", tris=500, voxel=0.016)

# calzini e punte delle orecchie blu notte
socks = paint(core_u, union(*[ellipsoid((0.24, 0.3, 0.32), (sx * 0.28, -0.46, 0.12)) for sx in (1, -1)],
                            *[ellipsoid((0.22, 0.32, 0.2), (sx * 0.55, -0.14, 0.08)) for sx in (1, -1)]), depth=0.06)
ear_tips = paint(ears, union(*[sphere(0.24, (c[0] + sx * 0.2, c[1], c[2] + 0.62)) for sx, c in zip((1, -1), EAR_C)]),
                 depth=0.06)
m.add("Socks", union(socks, ear_tips), NAVY, role="detail", tris=1400, voxel=0.03)

# spuntoni di ghiaccio sul dorso + cristalli sulla punta della coda
ice = []
for i, (o, dv, s) in enumerate([((0, -0.1, 1.55), (0, 0.35, 1.0), 0.62), ((0, 0.08, 1.3), (0, 0.6, 1.0), 0.78),
                                 ((0, 0.18, 1.05), (0, 0.9, 1.0), 0.66), ((0, 0.25, 0.8), (0, 1.0, 0.6), 0.5),
                                 ((0, 0.28, 0.6), (0, 1.0, 0.3), 0.36)]):
    p, n = project(core_u, o, dv)
    d = n * 0.5 + np.array([0, 0.25, 1.0]) * (1.0 - 0.12 * i) + np.array([0, 0.12 * i, 0])
    d = d / np.linalg.norm(d)
    ice.append(orient(crystal(s, 0.11 + 0.08 * s, tip=0.45), p - d * 0.1, d, spin=30 * i))
for sx in (1, -1):  # cristalli ai lati delle spalle: la cresta si vede anche da davanti e di tre quarti
    for j, (o, dv, s) in enumerate([((sx * 0.24, 0.02, 1.42), (sx * 0.85, 0.35, 0.9), 0.74),
                                    ((sx * 0.28, 0.22, 1.12), (sx * 0.95, 0.6, 0.6), 0.56)]):
        p, n = project(core_u, o, dv)
        d = np.asarray(dv) / np.linalg.norm(dv)
        ice.append(orient(crystal(s, 0.1 + 0.08 * s, tip=0.45), p - d * 0.1, d, spin=40 * j + 15 * sx))
tt = np.array(TAIL[-1])
for j, (d, s) in enumerate([((0.1, -0.5, 1.0), 0.42), ((-0.5, -0.4, 0.8), 0.3), ((0.6, -0.2, 0.7), 0.32),
                            ((0.0, -1.0, 0.3), 0.28)]):
    d = np.asarray(d) / np.linalg.norm(d)
    ice.append(orient(crystal(s, 0.07 + 0.1 * s, tip=0.45), tt + d * 0.12, d, spin=20 * j))
m.add("Ice", union(*ice), ICE, material="Ice", role="detail", tris=2400, voxel=0.024, smooth=False)

# naso, sorrisetto gelido (angolo +X all'insu'), sopracciglia sottili
painted = head.offset(0.022)
nose = sphere(0.075, tuple(project(head, (0, -0.9, 1.95), (0, -1, 0.15))[0] + [0, -0.02, 0.01]))
smirk = union(surface_tube(painted, [(0.0, 1.85), (0.0, 1.8)], 0.017, y=HEAD_C[1] - 0.6, inset=0.004),
              surface_tube(painted, [(-0.08, 1.795), (0.0, 1.8), (0.09, 1.795), (0.16, 1.815), (0.2, 1.85)],
                           [0.016, 0.019, 0.019, 0.018, 0.015], y=HEAD_C[1] - 0.6, inset=0.004))
brows = union(surface_tube(head, [(-0.42, 2.4), (-0.3, 2.44), (-0.17, 2.42)], [0.022, 0.03, 0.022], y=HEAD_C[1] - 0.6,
                           inset=0.006),
              surface_tube(head, [(0.17, 2.44), (0.3, 2.49), (0.42, 2.46)], [0.022, 0.03, 0.022], y=HEAD_C[1] - 0.6,
                           inset=0.006))
m.add("Mouth", union(nose, smirk, brows), MOUTH, role="detail", tris=800, voxel=0.011)

# occhi scuri con pupille a fessura luminose + "cuciture" di brina luminose sulle guance
eyes, slits, shines = [], [], []
for sx, f in frames.items():
    eyes.append(f.place(eye_local.rot(0, -sx * 14, 0)))
    slits.append(f.place(ellipsoid((0.024, 0.03, 0.095)).rot(0, -sx * 14, 0), (sx * 0.005, -0.068, -0.02)))
    shines.append(f.place(sphere(0.02), (-0.05, -0.078, -0.035)))
frost = []
for sx in (1, -1):
    pts = project_curve(painted, [(sx * x, HEAD_C[1] - 0.6, z) for x, z in [(0.42, 1.98), (0.52, 1.92), (0.6, 1.84)]],
                        (0, -1, 0))
    frost.append(stitches(painted, pts, step=0.075, length=0.085, r=0.015))
m.add("Eyes", union(*eyes), EYE, role="eye", tris=500, voxel=0.012)
m.add("Glow", union(*slits, *frost), GLOW, material="Neon", role="glow", tris=700, voxel=0.009)
m.add("Shine", union(*shines), WHITE, role="shine", tris=150, voxel=0.007)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
