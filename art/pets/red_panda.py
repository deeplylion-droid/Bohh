"""Panda Rosso (RedPanda) - pet Raro.

Carattere: il furbetto. Strizza l'occhio con un sorrisetto storto e un canino in vista; la maschera
bianca ha i contorni appuntiti. E' un peluche con una toppa blu notte ricucita sul fianco e la grande
coda ad anelli.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, box, capsule, ellipsoid, project, project_curve, round_cone,  # noqa: E402
                     sphere, tube, union)
from lib.toy import Model  # noqa: E402

RED = (198, 72, 34)
RUST = (110, 34, 28)
WHITE_FUR = (255, 246, 232)
DARK = (60, 32, 44)
PATCH = (42, 50, 104)
THREAD = (255, 234, 196)
MOUTH = (44, 20, 30)
EYE_WHITE = (255, 251, 240)
EYE = (24, 16, 30)
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


def paint(base, region, d=0.022, depth=0.045, k=0.012):
    """Vernice a strato sottile (fra -depth e +d dalla superficie) ritagliata dalla regione: niente grandi
    superfici nascoste, quindi voxel fine a parita' di triangoli. Spessore d + depth >= 2.5 voxel."""
    t = (d + depth) / 2
    return base.offset(d - t).shell(t).intersect(region, k=k)


def front(shape, y1, y0=-3.0, yp=-2.0):
    """Regione disegnata nella vista frontale: shape (modellata nel piano y = yp) estrusa lungo Y fra y0 e y1."""
    def f(p):
        q = p.copy()
        q[:, 1] = yp
        return np.maximum(shape(q), np.maximum(y0 - p[:, 1], p[:, 1] - y1))

    return SDF(f, (shape.lo[0], y0, shape.lo[2]), (shape.hi[0], y1, shape.hi[2]))


def slab(c, t, w):
    """Fetta spessa 2w perpendicolare alla direzione t, centrata in c (per gli anelli della coda)."""
    c = np.asarray(c, dtype=np.float32)
    t = np.asarray(t, dtype=np.float32)
    t = t / np.linalg.norm(t)
    return SDF(lambda p: np.abs((p - c) @ t) - w, c - 2, c + 2)


def frame_curve(base, frame, pts2d, depth=0.12):
    """Curva disegnata nel piano locale (x, z) di un Frame e proiettata sulla superficie lungo la normale."""
    out = []
    for x, z in pts2d:
        p, _ = project(base, frame.point((x, depth, z)), frame.normal)
        out.append(tuple(p))
    return out


# ============================================================ modello
m = Model("RedPanda", "pet")
PK = 0.012
TILT, NECK = 8.0, (0.0, -0.12, 1.55)


def tilt(s):
    """Testa inclinata verso l'occhio che strizza."""
    return s.rot(0, TILT, 0, pivot=NECK)


# testa larga (costruita dritta, poi inclinata), corpo seduto
HEAD_C = (0, -0.15, 2.1)
head = ellipsoid((0.9, 0.78, 0.72), HEAD_C)
cheeks = union(*[ellipsoid((0.38, 0.36, 0.32), (sx * 0.62, -0.32, 1.9)) for sx in (1, -1)])
MUZZLE_C = (0, -0.78, 1.9)
muzzle = ellipsoid((0.3, 0.24, 0.2), MUZZLE_C)
head_u = union(union(head, cheeks, k=0.2), muzzle, k=0.14)
body = ellipsoid((0.82, 0.78, 0.9), (0, 0.12, 0.92))
haunch = union(*[ellipsoid((0.4, 0.5, 0.38), (sx * 0.5, -0.05, 0.4)) for sx in (1, -1)])
torso = union(body, haunch, k=0.25)
EAR_C = [(sx * 0.6, -0.04, 2.7) for sx in (1, -1)]


def ear_shape(sx):
    e = round_cone((0, 0, -0.1), (0, 0, 0.28), 0.32, 0.12).warp(lambda p: p * [[1.0, 2.4, 1.0]])
    return e.rot(0, sx * 26, 0)


ears_u = union(*[ear_shape(sx).translate(c) for sx, c in zip((1, -1), EAR_C)])
core0 = union(torso, tilt(head_u), k=0.35)

# coda folta ad anelli che si arriccia sul fianco
N = 40
tail_pts = bezier((0.25, 0.75, 0.42), (1.05, 1.35, 0.25), (1.45, 0.75, 0.95), (1.05, 0.5, 1.72), N)
BANDS_T = [0.3, 0.47, 0.64, 0.81]


def tail_r(t):
    base = 0.26 + 0.18 * math.sin(math.pi * min(t / 0.9, 1.0) ** 0.8)
    puff = 1.0 + 0.07 * math.cos(2 * math.pi * (t - BANDS_T[0]) / 0.17 + math.pi)
    tip = 1.0 if t < 0.88 else max(0.0, 1.0 - (t - 0.88) / 0.12) ** 0.5
    return max(base * puff * tip, 0.06)


tail = tube(tail_pts, [tail_r(i / N) for i in range(N + 1)])

# occhi: il sinistro (+X) strizzato, il destro socchiuso e furbo
EYE_W = (0.16, 0.09, 0.2)
frames = {sx: Frame(head_u, HEAD_C, (0.42 * sx, -1.0, 0.16), sink=0.05) for sx in (1, -1)}
eye_r = eye_set(frames[-1], EYE_W, (0.078, 0.042, 0.098), look=(-0.035, -0.03), lid=(0.05, 0.16))
wink = tube(frame_curve(head_u, frames[1], [(x, 0.06 * (1 - (x / 0.14) ** 2) - 0.03) for x in np.linspace(-0.14, 0.14, 9)]),
            [0.026, 0.03, 0.033, 0.034, 0.034, 0.034, 0.033, 0.03, 0.026])

core = union(core0, tilt(ears_u), k=0.06)
core = union(core, tail, k=0.12)
core = union(core, tilt(eye_r[3]))
m.add("Body", core, RED, material="Fabric", tris=5300, voxel=0.03)

# maschera bianca appuntita: muso, guance a goccia, "sopracciglia" a fiamma, orecchie
Y1 = HEAD_C[1] + 0.25
YP = -2.0
mask = front(union(ellipsoid((0.34, 1.0, 0.26), (0, YP, 1.85)),
                   *[round_cone((sx * 0.64, YP, 1.8), (sx * 0.5, YP, 2.1), 0.18, 0.03) for sx in (1, -1)],
                   round_cone((-0.21, YP, 2.47), (-0.5, YP, 2.63), 0.07, 0.022),
                   round_cone((0.21, YP, 2.45), (0.5, YP, 2.49), 0.06, 0.022)), Y1)
face_white = paint(core0, tilt(mask))
ear_white = tilt(paint(ears_u, union(*[ellipsoid((0.6, 0.12, 0.6), (c[0], c[1] - 0.12, c[2] + 0.05)) for c in EAR_C]),
                       d=0.02, depth=0.04))
m.add("White", union(face_white, ear_white), WHITE_FUR, material="Fabric", role="detail", tris=2800, voxel=0.024)

# zampe, pancia e interno delle orecchie prugna scuro
EAR_MID = [(c[0] + sx * 0.08, c[1] - 0.08, c[2] + 0.18) for sx, c in zip((1, -1), EAR_C)]
ear_inner = tilt(paint(ears_u, union(*[ellipsoid((0.11, 0.1, 0.17)).rot(0, sx * 26, 0).translate(c)
                                         for sx, c in zip((1, -1), EAR_MID)]), d=0.034, depth=0.03))  # parte Mouth
belly = paint(core0, union(ellipsoid((0.46, 0.5, 0.5), (0, -0.62, 0.7)),
                           *[ellipsoid((0.44, 0.5, 0.26), (sx * 0.5, -0.25, 0.2)) for sx in (1, -1)]), depth=0.09)
front_legs = []
for sx in (1, -1):
    x = sx * 0.4
    toes = [sphere(0.075, (x + dx, -0.92, 0.09)) for dx in (-0.12, 0.0, 0.12)]
    front_legs.append(union(round_cone((sx * 0.37, -0.42, 1.08), (x, -0.68, 0.18), 0.2, 0.17),
                            ellipsoid((0.22, 0.26, 0.14), (x, -0.74, 0.14)), *toes, k=0.06))
hind_feet = union(*[union(ellipsoid((0.22, 0.32, 0.13), (sx * 0.66, -0.42, 0.13)),
                          *[sphere(0.07, (sx * 0.66 + dx, -0.7, 0.08)) for dx in (-0.1, 0.0, 0.1)], k=0.05)
                    for sx in (1, -1)])
m.add("Dark", union(belly, *front_legs, hind_feet), DARK, material="Fabric", role="detail", tris=1800,
      voxel=0.04)

# anelli della coda + punta + "lacrime" affilate
bands = []
for t0 in BANDS_T:
    i = int(round(t0 * N))
    c = tail_pts[i]
    tan = np.subtract(tail_pts[min(i + 1, N)], tail_pts[max(i - 1, 0)])
    bands.append(paint(tail, slab(c, tan, 0.055).intersect(sphere(0.6, c)), depth=0.07))
tip = paint(tail, sphere(0.34, tail_pts[N]), depth=0.07)
tears = front(union(*[round_cone((sx * 0.27, YP, 2.03), (sx * 0.37, YP, 1.71), 0.058, 0.022) for sx in (1, -1)]), Y1)
tears = paint(core0, tilt(tears), d=0.036, depth=0.055, k=0.008)
m.add("Bands", union(*bands, tip, tears), RUST, material="Fabric", role="detail", tris=1800, voxel=0.032)

# toppa blu notte ricucita sul fianco sinistro
pf = Frame(core0, (0.3, 0.05, 0.9), (1.0, -0.25, 0.08), sink=0.0)
patch = paint(core0, pf.place(box((0.2, 0.4, 0.17), round=0.05).rot(0, 10, 0)), d=0.03, depth=0.04, k=0.008)
m.add("Patch", patch, PATCH, material="Fabric", role="detail", tris=400, voxel=0.022)
border = []
for a in np.linspace(0, 2 * math.pi, 40):
    x, z = 0.155 * math.cos(a), 0.125 * math.sin(a)
    x, z = (math.copysign(min(abs(x) * 1.25, 0.155), x), math.copysign(min(abs(z) * 1.25, 0.125), z))
    border.append((x * math.cos(math.radians(10)) + z * math.sin(math.radians(10)),
                   -x * math.sin(math.radians(10)) + z * math.cos(math.radians(10))))
patch_stitches = stitches(core0.offset(0.03), frame_curve(core0.offset(0.03), pf, border), step=0.075, length=0.07,
                          r=0.014)

# sorrisetto storto con un canino, naso
painted = head_u.offset(0.022)
smirk = union(surface_tube(painted, [(0.0, 1.9), (0.0, 1.815)], 0.02, y=-0.6, inset=0.004),
              surface_tube(painted, [(-0.11, 1.835), (-0.02, 1.808), (0.1, 1.82), (0.18, 1.86), (0.22, 1.9)],
                           [0.019, 0.022, 0.023, 0.022, 0.019], y=-0.6, inset=0.004))
nose = Frame(painted, MUZZLE_C, (0, -1.0, 0.5), sink=0.03).place(
    union(ellipsoid((0.1, 0.065, 0.06)), ellipsoid((0.05, 0.05, 0.05), (0, 0, -0.035)), k=0.04))
m.add("Mouth", tilt(union(smirk, nose)).union(ear_inner), MOUTH, role="detail", tris=900, voxel=0.014)
fb, ft = project_curve(painted, [(0.1, -0.6, 1.815), (0.1, -0.6, 1.75)], (0, -1, 0), inset=0.0)
m.add("Thread", union(patch_stitches, tilt(round_cone(fb, ft, 0.022, 0.006))), THREAD, role="detail", tris=800,
      voxel=0.011)

# occhi
m.add("EyeWhite", tilt(eye_r[0]), EYE_WHITE, role="eye", tris=300, voxel=0.012)
m.add("Pupils", tilt(union(eye_r[1], wink)), EYE, role="eye", tris=500, voxel=0.01)
m.add("Shine", tilt(eye_r[2]), WHITE, role="shine", tris=150, voxel=0.008)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
