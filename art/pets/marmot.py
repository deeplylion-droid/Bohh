"""Marmotta (Marmot) - pet Raro.

Carattere: ladruncola furba. Offre una stella alpina con un ghigno a dentoni (e un sopracciglio alzato)
mentre nasconde dietro la schiena un uovo d'oro rubato. Pancia ricucita come un vecchio peluche.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, box, capsule, ellipsoid, project, project_curve,  # noqa: E402
                     round_cone, sphere, tube, union)
from lib.toy import Model  # noqa: E402

FUR = (204, 122, 50)
FUR_DARK = (120, 64, 38)
CREAM = (255, 224, 168)
PAW = (70, 40, 40)
MOUTH = (78, 18, 42)
TOOTH = (255, 250, 236)
EYE_WHITE = (255, 251, 240)
EYE = (24, 16, 30)
WHITE = (255, 255, 255)
THREAD = (60, 32, 78)
PETAL = (252, 252, 246)
FLOWER_C = (255, 200, 40)
STEM = (86, 150, 62)
GOLD = (255, 190, 50)


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


def lid_shape(radii, cut, slope=0.0, grow=0.016, k=0.012):
    """Palpebra pesante (coordinate locali del Frame): calotta dell'occhio ingrandito sopra z = cut + slope*x."""
    a, b, c = radii
    nrm = math.sqrt(1.0 + slope * slope)
    above = SDF(lambda p: (cut + slope * p[:, 0] - p[:, 2]) / nrm, (-1, -1, -1), (1, 1, 1))
    return ellipsoid((a + grow, b + grow, c + grow)).intersect(above, k=k)


def eye_set(frame, white, pupil, look=(0.0, 0.0), lid=None):
    """Occhio: bianco, pupilla (spostata di look=(x, z) locali), riflesso piccolo, palpebra opzionale."""
    a, b, c = white
    lx, lz = look
    ys = -b * math.sqrt(max(1 - (lx / a) ** 2 - (lz / c) ** 2, 0.05))
    pa, pb, pc = pupil
    pup = frame.place(ellipsoid(pupil), (lx, ys + pb * 0.45, lz))
    shine = frame.place(sphere(pa * 0.34), (lx - pa * 0.42, ys - pb * 0.3, lz + pc * 0.42))
    lid_s = frame.place(lid_shape(white, *lid)) if lid else None
    return frame.place(ellipsoid(white)), pup, shine, lid_s


def surface_tube(base, pts2d, radii, y=-0.3, inset=0.0, direction=(0, -1, 0)):
    """Tubo (sopracciglio, bocca) disegnato nella vista frontale e appoggiato sulla superficie."""
    return tube(project_curve(base, [(x, y, z) for x, z in pts2d], direction, inset=inset), radii)


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


# ============================================================ modello
m = Model("Marmot", "pet")
PK = 0.012

TILT, NECK = 8.0, (0.0, -0.1, 1.55)


def tilt(s):
    """Testa inclinata di lato (posa sfacciata)."""
    return s.rot(0, TILT, 0, pivot=NECK)


# testa (costruita dritta, poi inclinata) e corpo a pera
HEAD_C = (0, -0.1, 2.2)
head = ellipsoid((0.84, 0.77, 0.72), HEAD_C)
cheeks = union(*[ellipsoid((0.4, 0.38, 0.34), (sx * 0.44, -0.36, 1.98)) for sx in (1, -1)])
muzzle = ellipsoid((0.37, 0.28, 0.26), (0, -0.66, 1.96))
head_u = union(union(head, cheeks, k=0.2), muzzle, k=0.16)
EAR_C = [(sx * 0.55, -0.02, 2.74) for sx in (1, -1)]
ears_u = union(*[ellipsoid((0.2, 0.1, 0.18)).rot(0, 0, -sx * 18).rot(0, sx * 22, 0).translate(c)
                 for sx, c in zip((1, -1), EAR_C)])
body = ellipsoid((0.95, 0.86, 0.98), (0, 0.06, 1.04))
haunch = union(*[ellipsoid((0.42, 0.5, 0.36), (sx * 0.56, -0.12, 0.42)) for sx in (1, -1)])
torso = union(body, haunch, k=0.25)
core0 = union(torso, tilt(head_u), k=0.35)

# braccia lunghe: la destra (-X) porge il fiore, la sinistra (+X) va dietro la schiena con l'uovo
H_FLOWER = (-0.86, -1.0, 1.12)
H_EGG = (0.9, 0.62, 1.0)
arms = union(tube([(-0.68, -0.3, 1.55), (-0.98, -0.62, 1.3), (-0.88, -0.95, 1.13)], [0.17, 0.15, 0.12]),
             tube([(0.7, -0.25, 1.55), (1.0, 0.16, 1.25), (0.92, 0.56, 1.02)], [0.17, 0.15, 0.12]))

# occhi: destro socchiuso e furbo, sinistro spalancato sotto il sopracciglio alzato
EYE_W = (0.15, 0.085, 0.185)
frames = {sx: Frame(head_u, HEAD_C, (0.42 * sx, -1.0, 0.17), sink=0.045) for sx in (1, -1)}
eyes = {1: eye_set(frames[1], EYE_W, (0.072, 0.04, 0.094), look=(-0.035, 0.0)),
        -1: eye_set(frames[-1], EYE_W, (0.072, 0.04, 0.094), look=(-0.035, -0.045), lid=(0.02, 0.32))}
lids = tilt(eyes[-1][3])

core = union(core0, arms, k=0.06)
core = union(core, lids)
m.add("Body", core, FUR, material="Fabric", tris=4800)

# crema: pancia, muso, interno orecchie
belly = core0.offset(0.022).intersect(ellipsoid((0.68, 0.62, 0.82), (0, -0.62, 1.0)), k=PK)
snout = core0.offset(0.022).intersect(tilt(ellipsoid((0.44, 0.36, 0.33), (0, -0.84, 1.9))), k=PK)
inner_ears = tilt(union(*[Frame(ears_u, c, (sx * 0.3, -1.0, 0.05), sink=0.035).place(ellipsoid((0.11, 0.04, 0.1)))
                          for sx, c in zip((1, -1), EAR_C)]))
m.add("Belly", union(belly, snout, inner_ears), CREAM, material="Fabric", role="detail", tris=1500)

# orecchie e coda folta piu' scure
tail = tube(bezier((0.12, 0.78, 0.34), (0.3, 1.3, 0.16), (0.56, 1.58, 0.44), (0.46, 1.42, 0.9), 12),
            [0.2, 0.22, 0.24, 0.26, 0.27, 0.27, 0.27, 0.26, 0.25, 0.23, 0.21, 0.19, 0.16])
m.add("Markings", union(tilt(ears_u), tail), FUR_DARK, material="Fabric", role="detail", tris=1000)

# manone scure con dita tozze + piedoni
fist = union(ellipsoid((0.15, 0.13, 0.15), H_FLOWER),
             *[sphere(0.062, (H_FLOWER[0] + 0.05, H_FLOWER[1] - 0.11, H_FLOWER[2] + dz)) for dz in (-0.08, 0.0, 0.08)],
             sphere(0.06, (H_FLOWER[0] - 0.07, H_FLOWER[1] - 0.1, H_FLOWER[2] + 0.12)), k=0.04)
EGG_C = (0.86, 0.86, 1.12)
cup_hand = union(ellipsoid((0.15, 0.14, 0.12), H_EGG),
                 *[sphere(0.06, (EGG_C[0] + 0.15 * math.cos(a), EGG_C[1] + 0.15 * math.sin(a), 1.02))
                   for a in (0.6, 1.4, 2.2, 3.4)], k=0.04)
feet = []
for sx in (1, -1):
    x = sx * 0.42
    toes = [sphere(0.085, (x + dx, -0.96, 0.09)) for dx in (-0.13, 0.0, 0.13)]
    feet.append(union(ellipsoid((0.27, 0.36, 0.14), (x, -0.64, 0.14)), *toes, k=0.06))
m.add("Paws", union(fist, cup_hand, *feet), PAW, role="detail", tris=1500)

# ghigno a dentoni (angolo destro piu' alto) e naso
upper = [(-0.31, 1.91), (-0.2, 1.87), (-0.08, 1.858), (0.0, 1.86), (0.1, 1.862), (0.22, 1.895), (0.34, 1.98)]
lower = [(-0.31, 1.91), (-0.23, 1.79), (-0.11, 1.705), (0.0, 1.69), (0.12, 1.705), (0.25, 1.79), (0.34, 1.98)]
mouth, small_teeth = grin(head_u, upper, lower, y_back=-0.62, up_teeth=(-0.24, -0.16, 0.17, 0.26),
                          down_teeth=(-0.17, 0.19), tooth=(0.058, 0.025))
lip = head_u.offset(0.034)
buck = []
for x in (-0.05, 0.05):
    p, _ = project(lip, (x, -0.4, 1.8), (0, -1, 0))
    buck.append(box((0.045, 0.024, 0.075), (x, p[1] - 0.012, 1.8), round=0.022))
nose = Frame(head_u.offset(0.022), (0, -0.66, 1.98), (0, -1.0, 0.6), sink=0.025).place(
    union(ellipsoid((0.11, 0.07, 0.065)), ellipsoid((0.055, 0.05, 0.05), (0, 0, -0.04)), k=0.04))
m.add("Mouth", tilt(union(mouth, nose)), MOUTH, role="detail", tris=800, voxel=0.015)
m.add("Teeth", tilt(union(*buck, *small_teeth)), TOOTH, role="detail", tris=700, voxel=0.01)

# occhi
m.add("EyeWhite", tilt(union(eyes[1][0], eyes[-1][0])), EYE_WHITE, role="eye", tris=600, voxel=0.013)
m.add("Pupils", tilt(union(eyes[1][1], eyes[-1][1])), EYE, role="eye", tris=500, voxel=0.01)
m.add("Shine", tilt(union(eyes[1][2], eyes[-1][2])), WHITE, role="shine", tris=250, voxel=0.008)

# sopracciglia spesse (una alzata, una abbassata) e pancia ricucita
brows = union(surface_tube(head_u, [(-0.5, 2.6), (-0.36, 2.58), (-0.2, 2.52)], [0.035, 0.05, 0.04], inset=0.012),
              surface_tube(head_u, [(0.16, 2.6), (0.31, 2.72), (0.5, 2.66)], [0.04, 0.05, 0.035], inset=0.012))
seam_pts = project_curve(core0.offset(0.022), [(x, -0.3, z) for x, z in
                                               [(0.08, 1.52), (0.02, 1.25), (0.07, 0.95), (0.02, 0.62)]],
                         (0, -1, 0))
seam = union(stitches(core0.offset(0.022), seam_pts, step=0.1, length=0.12, r=0.018),
             tube(seam_pts, 0.011))
m.add("Thread", union(tilt(brows), seam), THREAD, role="detail", tris=1500, voxel=0.012)

# stella alpina porta in avanti (modellata con fronte +Z locale)
FLOWER_POS = (-0.94, -1.14, 1.64)


def cup(shape, k):
    return shape.warp(lambda p: p - (p[:, 0:1] ** 2 + p[:, 1:2] ** 2) * [[0.0, 0.0, k]], pad=0.08)


def place_flower(shape):
    return shape.rot(62, 0, 0).rot(0, 0, -18).translate(FLOWER_POS)


def petal(length, width, thick):
    shape = union(round_cone((0, 0, 0), (0, 0.4 * length, 0), 0.6 * width, width),
                  round_cone((0, 0.4 * length, 0), (0, length, 0), width, 0.28 * width), k=0.02)
    return shape.warp(lambda p: p * [[1.0, 1.0, width / thick]])


outer = cup(union(*[petal(0.42, 0.09, 0.032).rot(0, 0, i * 45) for i in range(8)], k=0.02), 0.6)
inner = cup(union(*[petal(0.27, 0.07, 0.028).rot(0, 0, 22.5 + i * 45) for i in range(8)], k=0.02), 0.95)
m.add("Petals", place_flower(union(outer, inner.translate((0, 0, 0.04)))), PETAL, role="detail", tris=1200,
      voxel=0.012)
florets = [sphere(0.062, (0, 0, 0.105))] + [sphere(0.052, (0.082 * math.cos(a), 0.082 * math.sin(a), 0.082))
                                           for a in [i * math.pi / 3 for i in range(6)]]
m.add("FlowerCentre", place_flower(union(*florets, k=0.02)), FLOWER_C, role="detail", tris=400, voxel=0.01)
stem = tube([FLOWER_POS, (-0.9, -1.04, 1.2), (-0.86, -1.0, 0.98)], [0.042, 0.04, 0.036])
m.add("Stem", stem, STEM, role="detail", tris=300, voxel=0.012)

# l'uovo d'oro rubato, nascosto dietro la schiena
egg = ellipsoid((0.17, 0.17, 0.22)).rot(-20, 15, 0).translate(EGG_C)
m.add("Egg", egg, GOLD, material="Foil", role="detail", tris=400, voxel=0.015)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
