"""Leopardo delle Nevi (SnowLeopard) - pet Raro.

Carattere: dolce-inquietante. Occhioni spalancati color ghiaccio con pupille a fessura, sopracciglia
innocenti e un sorriso un po' troppo largo pieno di dentini. Ha un fiocco bordeaux al collo come una
bambola, la coda foltissima "ricucita" al corpo e le rosette blu notte ad anello.
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

FUR = (196, 202, 218)
WHITE_FUR = (250, 250, 248)
SPOT = (38, 42, 80)
PINK = (226, 116, 150)
IRIS = (150, 212, 242)
EYE_WHITE = (255, 252, 246)
EYE = (22, 24, 52)
MOUTH = (34, 34, 70)
TOOTH = (255, 252, 244)
WHITE = (255, 255, 255)
RIBBON = (128, 24, 58)


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


def paint(base, region, d=0.022, depth=0.045, k=0.012):
    """Vernice a strato sottile (fra -depth e +d dalla superficie) ritagliata dalla regione: niente grandi
    superfici nascoste, quindi voxel fine a parita' di triangoli. Spessore d + depth >= 2.5 voxel."""
    t = (d + depth) / 2
    return base.offset(d - t).shell(t).intersect(region, k=k)


def circle_around(c, d, R, n=24):
    """Punti di una circonferenza (chiusa) di raggio R attorno all'asse d."""
    d = np.asarray(d, dtype=np.float64)
    d = d / np.linalg.norm(d)
    u = np.cross(d, [0.0, 0.0, 1.0] if abs(d[2]) < 0.9 else [1.0, 0.0, 0.0])
    u /= np.linalg.norm(u)
    v = np.cross(d, u)
    return [tuple(np.asarray(c) + R * (math.cos(a) * u + math.sin(a) * v)) for a in np.linspace(0, 2 * math.pi, n + 1)]


def slab(c, t, w):
    """Fetta spessa 2w perpendicolare alla direzione t, centrata in c."""
    c = np.asarray(c, dtype=np.float32)
    t = np.asarray(t, dtype=np.float32)
    t = t / np.linalg.norm(t)
    return SDF(lambda p: np.abs((p - c) @ t) - w, c - 2, c + 2)


# ============================================================ modello
m = Model("SnowLeopard", "pet")
PK = 0.01
TILT, NECK = -10.0, (0.0, -0.45, 1.5)


def tilt(s):
    """Testa inclinata con aria innocente."""
    return s.rot(0, TILT, 0, pivot=NECK)


HEAD_C = (0, -0.58, 2.02)
head = ellipsoid((0.84, 0.74, 0.7), HEAD_C)
jowls = union(*[ellipsoid((0.36, 0.32, 0.3), (sx * 0.52, -0.86, 1.8)) for sx in (1, -1)])
pads = union(*[ellipsoid((0.15, 0.12, 0.11), (sx * 0.11, -1.3, 1.79)) for sx in (1, -1)])
head_u = union(union(head, jowls, k=0.18), pads, k=0.08)
body = ellipsoid((0.6, 0.85, 0.55), (0, 0.25, 0.94))
neck = round_cone((0, -0.2, 1.12), (0, -0.45, 1.6), 0.4, 0.38)
torso = union(body, neck, k=0.2)
LEGS = [(sx * 0.33, y) for sx in (1, -1) for y in (-0.3, 0.8)]
legs = union(*[round_cone((x, y, 0.84), (x, y - 0.02, 0.2), 0.19, 0.17) for x, y in LEGS])
paws = union(*[ellipsoid((0.22, 0.26, 0.15), (x * 1.04, y - 0.06, 0.15)) for x, y in LEGS])
EAR_C = [(sx * 0.6, -0.36, 2.6) for sx in (1, -1)]
ears_u = union(*[ellipsoid((0.2, 0.1, 0.18)).rot(0, sx * 26, 0).translate(c) for sx, c in zip((1, -1), EAR_C)])
core0 = union(torso, tilt(head_u), k=0.3)
limbs = union(legs, paws, k=0.08)

# coda foltissima che sale e si arriccia
N = 32
tail_pts = bezier((0.05, 0.95, 0.9), (0.25, 1.95, 0.7), (0.95, 2.05, 2.0), (0.4, 1.32, 2.12), N)


def tail_r(t):
    r = 0.22 + 0.13 * min(t / 0.3, 1.0) ** 0.7
    return r * (1.0 if t < 0.9 else max(0.25, 1.0 - (t - 0.9) / 0.1) ** 0.4)


tail = tube(tail_pts, [tail_r(i / N) for i in range(N + 1)])
core = union(union(core0, limbs, k=0.1), tilt(ears_u), k=0.05)
core = union(core, tail, k=0.12)
m.add("Body", core, FUR, tris=5200)

# pancia, petto, mento e cuscinetti del muso bianchi
belly = paint(core0, union(ellipsoid((0.46, 0.82, 0.3), (0, 0.25, 0.42)), ellipsoid((0.4, 0.36, 0.48), (0, -0.56, 1.02)),
                           tilt(ellipsoid((0.42, 0.34, 0.3), (0, -1.28, 1.66))), k=0.15), depth=0.075, k=PK)
m.add("Belly", belly, WHITE_FUR, role="detail", tris=1500, voxel=0.034)

# rosette blu notte ad anello (alcune aperte a "C"), macchie su testa e zampe
rng = np.random.default_rng(11)
centres = []


def ring_shell(p, n, r_out, width=0.058, gap=None):
    """Regione ad anello attorno al punto p della superficie: guscio fra due sfere concentriche."""
    shell = sphere(r_out, p).subtract(sphere(r_out - width, p))
    if gap is not None:
        t = np.cross(n, gap)
        t = t / np.linalg.norm(t)
        shell = shell.subtract(sphere(0.06, p + t * (r_out - width / 2)))
    return shell


def free(p, r):
    return all(np.linalg.norm(q - p) > r * 2.4 for q in centres)


body_shells = []
BODY_C = np.array([0, 0.3, 0.92])
tries = 0
while len(body_shells) < 13 and tries < 800:
    tries += 1
    d = rng.normal(size=3)
    d[2] = abs(d[2]) + 0.15
    d = d / np.linalg.norm(d)
    p, n = project(core0, BODY_C, d)
    r = rng.uniform(0.135, 0.16)
    if p[2] < 0.84 or p[1] < -0.3 or np.linalg.norm(p - np.array(HEAD_C)) < 1.0 or not free(p, r):
        continue
    centres.append(p)
    body_shells.append(ring_shell(p, n, r, gap=rng.normal(size=3) if rng.random() < 0.5 else None))
tail_shells = []
for t in np.linspace(0.2, 0.78, 6):
    i = int(t * N)
    a = rng.uniform(0, 2 * math.pi)
    c = np.array(tail_pts[i])
    tan = np.subtract(tail_pts[i + 1], tail_pts[i - 1])
    tan = tan / np.linalg.norm(tan)
    side = np.cross(tan, [0, 0, 1.0])
    side = side / np.linalg.norm(side) if np.linalg.norm(side) > 0.3 else np.array([1.0, 0, 0])
    up = np.cross(side, tan)
    for aa in (a, a + 2.1, a + 4.2):
        d = side * math.cos(aa) + up * math.sin(aa)
        p, n = project(tail, c, d)
        r = rng.uniform(0.12, 0.14)
        if free(p, r):
            centres.append(p)
            tail_shells.append(ring_shell(p, n, r, gap=rng.normal(size=3) if rng.random() < 0.4 else None))
body_rings = paint(core0, fast_union(body_shells), depth=0.045, k=0.005)
tail_rings = paint(tail, union(fast_union(tail_shells), sphere(0.34, tail_pts[N])), depth=0.045, k=0.005)
head_dots = []
for x, z, r in [(0.0, 2.65, 0.085), (0.21, 2.58, 0.07), (-0.21, 2.58, 0.07), (0.62, 2.22, 0.075), (-0.62, 2.22, 0.075)]:
    p, _ = project(head_u, (x * 0.5, HEAD_C[1], z * 0.6 + HEAD_C[2] * 0.4), (x, -0.6, z - HEAD_C[2]))
    head_dots.append(sphere(r, p))
leg_dots = []
for x, y in LEGS:
    p, _ = project(limbs, (x, y, 0.58), (np.sign(x), -0.4, 0))
    leg_dots.append(sphere(0.065, p))
dots = paint(limbs, fast_union(leg_dots), depth=0.045, k=0.005)
m.add("Rosettes", union(body_rings, tail_rings, dots), SPOT, role="detail", tris=2900, voxel=0.026)
m.add("Spots", tilt(paint(head_u, fast_union(head_dots), depth=0.035, k=0.004)), SPOT, role="detail", tris=400,
      voxel=0.014)

# naso e interno delle orecchie rosa
painted = head_u.offset(0.022)
nose = Frame(painted, (0, -1.2, 1.84), (0, -1.0, 0.75), sink=0.02).place(
    union(ellipsoid((0.095, 0.06, 0.055)), ellipsoid((0.05, 0.05, 0.05), (0, 0, -0.035)), k=0.04))
inner_ears = paint(ears_u, union(*[ellipsoid((0.13, 0.12, 0.12)).translate((0, -0.12, -0.01)).rot(0, sx * 26, 0)
                                   .translate(c) for sx, c in zip((1, -1), EAR_C)]), depth=0.03)
m.add("Pink", tilt(union(nose, inner_ears)), PINK, role="detail", tris=600, voxel=0.012)

# sorriso un po' troppo largo con tanti dentini, sopracciglia innocenti, coda "ricucita"
upper = [(-0.39, 1.81), (-0.28, 1.715), (-0.14, 1.67), (0.0, 1.66), (0.14, 1.67), (0.28, 1.715), (0.39, 1.81)]
lower = [(-0.39, 1.81), (-0.28, 1.682), (-0.14, 1.626), (0.0, 1.612), (0.14, 1.626), (0.28, 1.682), (0.39, 1.81)]
Y_BACK = max(project(head_u, (x, -0.8, z), (0, -1, 0))[0][1] for x, z in upper) + 0.09
mouth, teeth = grin(head_u, upper, lower, y_back=Y_BACK, up_teeth=(-0.27, -0.19, -0.115, -0.04, 0.04, 0.115, 0.19, 0.27),
                    tooth=(0.038, 0.016))
philtrum = surface_tube(painted, [(0.0, 1.86), (0.0, 1.67)], 0.016, y=-1.0, inset=0.004)
brows = union(surface_tube(head_u, [(-0.46, 2.46), (-0.33, 2.5), (-0.21, 2.55)], [0.02, 0.027, 0.022], y=-1.0, inset=0.008),
              surface_tube(head_u, [(0.21, 2.55), (0.33, 2.5), (0.46, 2.46)], [0.022, 0.027, 0.02], y=-1.0, inset=0.008))
ic = 4
seam = stitches(tail, circle_around(tail_pts[ic], np.subtract(tail_pts[ic + 1], tail_pts[ic - 1]), tail_r(ic / N), 28),
                step=0.08, length=0.09, r=0.015)
m.add("Mouth", tilt(union(mouth, philtrum, brows)), MOUTH, role="detail", tris=1200, voxel=0.012)
m.add("Teeth", tilt(union(*teeth)), TOOTH, role="detail", tris=400, voxel=0.008)

# occhioni spalancati: bianco, iride azzurra, pupilla a fessura, contorno scuro, riflessi piccoli
EYE_W = (0.17, 0.09, 0.205)
frames = [Frame(head_u, HEAD_C, (0.46 * sx, -1.0, 0.2), sink=0.05) for sx in (1, -1)]
LOOK = (0.0, 0.015)
whites, irises, slits, shines = [], [], [], []
for f in frames:
    a, b, c = EYE_W
    ys = -b * math.sqrt(1 - (LOOK[1] / c) ** 2)
    ic_ = (LOOK[0], ys + 0.045 * 0.55, LOOK[1])
    whites.append(f.place(ellipsoid(EYE_W)))
    irises.append(f.place(ellipsoid((0.115, 0.045, 0.135)), ic_))
    slits.append(f.place(ellipsoid((0.028, 0.03, 0.092)), (ic_[0], ic_[1] - 0.03, ic_[2])))
    shines.append(f.place(sphere(0.026), (ic_[0] - 0.05, ic_[1] - 0.037, ic_[2] + 0.05)))
    shines.append(f.place(sphere(0.014), (ic_[0] + 0.045, ic_[1] - 0.04, ic_[2] - 0.05)))
outline = paint(head_u, union(*[f.place(ellipsoid((0.19, 0.3, 0.226)).subtract(ellipsoid((0.145, 0.4, 0.178))))
                                for f in frames]), d=0.012, depth=0.03, k=0.004)
m.add("EyeWhite", tilt(union(*whites)), EYE_WHITE, role="eye", tris=500, voxel=0.014)
m.add("Iris", tilt(union(*irises)), IRIS, role="eye", tris=500, voxel=0.012)
m.add("Pupils", tilt(union(*slits, outline)), EYE, role="eye", tris=1000, voxel=0.012)
m.add("Shine", tilt(union(*shines)), WHITE, role="shine", tris=200, voxel=0.007)

# fiocco bordeaux al collo (fascia dipinta + fiocco), come una bambola
NECK_A = np.array([0.0, -0.36, 1.42])
NECK_D = np.array([0.0, -0.47, 0.88])
band = paint(core0, slab(NECK_A, NECK_D, 0.05).intersect(sphere(0.75, NECK_A)), d=0.03, depth=0.06, k=0.006)
fdir = np.array([0.0, -1.0, 0.0]) - 0.471 * NECK_D / np.linalg.norm(NECK_D) * (NECK_D / np.linalg.norm(NECK_D) @ [0, -1, 0]) / 0.471
bow_f = Frame(core0, NECK_A, fdir, sink=0.0)
bow = union(sphere(0.062, (0, -0.03, 0)),
            *[ellipsoid((0.18, 0.06, 0.11)).rot(0, sx * 22, 0).translate((sx * 0.17, -0.015, 0.035)) for sx in (1, -1)],
            *[round_cone((sx * 0.03, -0.02, -0.03), (sx * 0.12, 0.0, -0.24), 0.05, 0.032) for sx in (1, -1)], k=0.03)
m.add("Ribbon", union(band, bow_f.place(bow)), RIBBON, role="detail", tris=1000, voxel=0.02)
m.add("Seam", seam, RIBBON, role="detail", tris=500, voxel=0.012)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
