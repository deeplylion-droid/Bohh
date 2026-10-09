"""Stambecco (Ibex) - pet Raro.

Carattere: lo sbruffone. Mento all'insu', palpebre pesanti e pupille che ti guardano dall'alto in basso,
sorrisetto storto con un dentino. Un corno e' stato ricucito con una fascia bordeaux; al collo il
campanaccio d'oro di cui va fiero.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capped_cone, capsule, ellipsoid, project, project_curve,  # noqa: E402
                     rot_matrix, round_cone, sphere, torus, tube, union)
from lib.toy import Model  # noqa: E402

FUR = (178, 132, 92)
CREAM = (250, 232, 200)
STRIPE = (76, 48, 40)
HOOF = (46, 42, 64)
HORN = (234, 206, 152)
STRAP = (132, 28, 54)
THREAD = (255, 244, 222)
MOUTH = (58, 20, 36)
EYE_WHITE = (255, 251, 240)
EYE = (24, 16, 30)
WHITE = (255, 255, 255)
GOLD = (255, 192, 52)


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


def ring(c, d, R, r):
    """Toro di raggio R (sezione r) centrato in c, con l'asse lungo la direzione d."""
    d = np.asarray(d, dtype=np.float64)
    d = d / np.linalg.norm(d)
    z = np.array([0.0, 0.0, 1.0])
    ax = np.cross(z, d)
    s = float(np.linalg.norm(ax))
    t = torus(R, r)
    if s > 1e-6:
        t = t.rotate(rot_matrix(ax, math.degrees(math.atan2(s, float(z @ d)))))
    return t.translate(c)


def circle_around(c, d, R, n=24):
    """Punti di una circonferenza di raggio R attorno all'asse d (chiusa)."""
    d = np.asarray(d, dtype=np.float64)
    d = d / np.linalg.norm(d)
    u = np.cross(d, [0.0, 0.0, 1.0] if abs(d[2]) < 0.9 else [1.0, 0.0, 0.0])
    u /= np.linalg.norm(u)
    v = np.cross(d, u)
    return [tuple(np.asarray(c) + R * (math.cos(a) * u + math.sin(a) * v)) for a in np.linspace(0, 2 * math.pi, n + 1)]


# ============================================================ modello
m = Model("Ibex", "pet")
PK = 0.012
NECK = (0.0, -0.42, 1.62)


def tilt(s):
    """Mento all'insu' (aria di superiorita')."""
    return s.rot(-9, 0, 0, pivot=NECK)


HEAD_C = (0, -0.62, 2.12)
head = ellipsoid((0.78, 0.7, 0.68), HEAD_C)
SNOUT_C = (0, -1.17, 1.88)
snout = ellipsoid((0.38, 0.3, 0.28), SNOUT_C)
head_u = union(head, snout, k=0.16)
EAR_C = [(sx * 0.8, -0.5, 2.17) for sx in (1, -1)]
ears_u = union(*[ellipsoid((0.3, 0.115, 0.13)).rot(0, sx * 18, -sx * 22).translate(c) for sx, c in zip((1, -1), EAR_C)])
bp, _ = project(head_u, (0, -1.12, 1.82), (0, -0.25, -1))
beard_u = tube(bezier(tuple(bp + [0, 0.03, 0.06]), tuple(bp + [0, -0.03, -0.06]), tuple(bp + [0, -0.06, -0.14]),
                      tuple(bp + [0, -0.12, -0.2]), 6), [0.085, 0.085, 0.08, 0.07, 0.058, 0.045, 0.032])

body = ellipsoid((0.66, 0.82, 0.58), (0, 0.24, 1.12))
neck = capsule((0, -0.28, 1.36), (0, -0.48, 1.8), 0.32)
torso = union(body, neck, k=0.2)
LEGS = [(sx * 0.36, y) for sx in (1, -1) for y in (-0.3, 0.74)]
legs = union(*[round_cone((x, y, 1.0), (x * 1.04, y, 0.24), 0.21, 0.17) for x, y in LEGS])
core_np = union(torso, tilt(head_u), k=0.3)

# occhi socchiusi (palpebre orizzontali pesanti), pupille in basso: ti guarda dall'alto in basso
EYE_W = (0.16, 0.09, 0.19)
frames = {sx: Frame(head_u, HEAD_C, (0.48 * sx, -1.0, 0.18), sink=0.045) for sx in (1, -1)}
eyes = {sx: eye_set(frames[sx], EYE_W, (0.074, 0.04, 0.09), look=(0.0, -0.055), lid=(-0.005, 0.0)) for sx in (1, -1)}
core = union(union(core_np, legs, k=0.12), tilt(union(ears_u, beard_u)), k=0.05)
core = union(core, tilt(union(eyes[1][3], eyes[-1][3])))
m.add("Body", core, FUR, tris=5200)

# pancia, petto e muso color crema + interno delle orecchie
belly = torso.offset(0.022).intersect(union(ellipsoid((0.52, 0.8, 0.36), (0, 0.16, 0.54)),
                                            ellipsoid((0.42, 0.4, 0.5), (0, -0.62, 1.16)), k=0.2), k=PK)
muzzle = core_np.offset(0.022).intersect(tilt(ellipsoid((0.46, 0.34, 0.34), (0, -1.42, 1.86))), k=PK)
inner_ears = tilt(ears_u.offset(0.022).intersect(union(*[ellipsoid((0.2, 0.17, 0.075)).translate((sx * 0.03, -0.16, 0))
                                                         .rot(0, sx * 18, -sx * 22).translate(c)
                                                         for sx, c in zip((1, -1), EAR_C)]), k=PK))
m.add("Belly", union(belly, muzzle, inner_ears), CREAM, role="detail", tris=1500)

# striscia scura sul dorso, codina e sopracciglia alte e rilassate (aria di sufficienza)
spine = []
for y in np.linspace(-0.12, 1.0, 12):
    p, _ = project(core_np, (0, float(y), 1.1), (0, 0, 1))
    spine.append(tuple(p))
stripe = core.offset(0.022).intersect(tube(spine, 0.17), k=PK)
tail = round_cone((0, 1.0, 1.42), (0, 1.22, 1.68), 0.13, 0.08)
brows = union(surface_tube(head_u, [(-0.5, 2.43), (-0.36, 2.48), (-0.21, 2.46)], [0.034, 0.048, 0.034], y=-0.95,
                           inset=0.012),
              surface_tube(head_u, [(0.21, 2.47), (0.36, 2.53), (0.5, 2.48)], [0.034, 0.048, 0.034], y=-0.95, inset=0.012))
m.add("Markings", union(stripe, tail, tilt(brows)), STRIPE, role="detail", tris=1300)

# zoccoli
hooves = union(*[capped_cone((x * 1.04, y, 0.0), (x * 1.04, y, 0.26), 0.235, 0.2, round=0.06) for x, y in LEGS])
m.add("Hooves", hooves, HOOF, role="detail", tris=800)

# grandi corna ad anelli; quello sinistro (+X) e' ricucito con una fascia bordeaux
horns, straps, threads = [], [], []
for sx in (1, -1):
    n = 24
    pts = bezier((sx * 0.24, -0.66, 2.52), (sx * 0.3, -0.74, 3.12), (sx * 0.5, -0.06, 3.36), (sx * 0.6, 0.38, 3.0), n)
    radii = [0.2 - 0.13 * i / n for i in range(n + 1)]
    band = range(8, 12) if sx > 0 else range(0)
    rings = []
    for i in range(4, n - 1, 2):
        if i in band or i + 1 in band or i - 1 in band:
            continue
        rings.append(ring(pts[i], np.subtract(pts[i + 1], pts[i - 1]), radii[i] - 0.012, 0.032))
    horns.append(union(tube(pts, radii), *rings, k=0.022))
    if sx > 0:
        b0, b1 = band[0], band[-1]
        strap = tube(pts[b0:b1 + 1], [radii[i] + 0.03 for i in range(b0, b1 + 1)])
        straps.append(strap)
        ic = (b0 + b1) // 2
        threads.append(stitches(strap, circle_around(pts[ic], np.subtract(pts[ic + 1], pts[ic - 1]), radii[ic] + 0.03, 28),
                                step=0.075, length=0.1, r=0.014))
m.add("Horns", tilt(union(*horns)), HORN, role="detail", tris=2700, voxel=0.022)

# collare bordeaux con campanaccio d'oro
NECK_A = np.array([0, -0.39, 1.58])
NECK_D = np.array([0, -0.43, 0.9])
collar = ring(NECK_A, NECK_D, 0.345, 0.055)
m.add("Straps", union(tilt(union(*straps)), collar), STRAP, role="detail", tris=900, voxel=0.014)
front = np.array([0, -0.903, -0.429])
BELL = NECK_A + front * 0.36 + np.array([0, -0.06, -0.14])
bell = union(capped_cone(tuple(BELL + [0, 0, -0.1]), tuple(BELL + [0, 0, 0.05]), 0.11, 0.065, round=0.02),
             sphere(0.07, tuple(BELL + [0, 0, 0.04])), sphere(0.035, tuple(BELL + [0, 0, -0.12])),
             ring(tuple(BELL + [0, 0, 0.13]), (0, 1, 0), 0.035, 0.014), k=0.02)
m.add("Bell", bell, GOLD, material="Foil", role="detail", tris=500, voxel=0.01)

# sorrisetto storto con un dentino, naso
painted = head_u.offset(0.022)
smirk = surface_tube(painted, [(-0.13, 1.775), (-0.04, 1.75), (0.07, 1.755), (0.16, 1.79), (0.21, 1.83)],
                     [0.02, 0.023, 0.024, 0.023, 0.02], y=-1.0, inset=0.004)
nose = Frame(painted, SNOUT_C, (0, -1.0, 0.55), sink=0.025).place(
    union(ellipsoid((0.09, 0.06, 0.05)), ellipsoid((0.045, 0.045, 0.045), (0, 0, -0.03)), k=0.04))
m.add("Mouth", tilt(union(smirk, nose)), MOUTH, role="detail", tris=600, voxel=0.012)
fb, ft = project_curve(painted, [(0.1, -1.0, 1.765), (0.1, -1.0, 1.705)], (0, -1, 0), inset=0.0)
fang = round_cone(fb, ft, 0.022, 0.006)  # (gia' nelle coordinate della testa dritta)
m.add("Thread", tilt(union(*threads, fang)), THREAD, role="detail", tris=700, voxel=0.01)

# occhi
m.add("EyeWhite", tilt(union(eyes[1][0], eyes[-1][0])), EYE_WHITE, role="eye", tris=500, voxel=0.013)
m.add("Pupils", tilt(union(eyes[1][1], eyes[-1][1])), EYE, role="eye", tris=400, voxel=0.01)
m.add("Shine", tilt(union(eyes[1][2], eyes[-1][2])), WHITE, role="shine", tris=200, voxel=0.008)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
