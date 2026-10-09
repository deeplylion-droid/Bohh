"""Pizzasauro Rex - pet Divino (creatura meme originale).

Un T-rex giocattolo fatto di pizza che di notte prende vita: pelle color crosta dorata con
cornicione, schiena di pomodoro con salame piccante, mozzarella che cola, cresta di foglie di
basilico, braccine corte con manone. Carattere: il bullo affamato - ghigno enorme pieno di
dentini aguzzi, sopracciglia minacciose, sguardo storto e una cucitura sulla pancia.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capsule, ellipsoid, euler, project, project_curve,  # noqa: E402
                     round_cone, smin, sphere, tube, union)
from lib.toy import Model  # noqa: E402

CRUST = (240, 148, 44)
DOUGH = (255, 214, 140)
SAUCE = (212, 30, 28)
PEPPERONI = (112, 14, 30)
CHEESE = (255, 249, 228)
BASIL = (30, 152, 54)
MOUTH = (46, 8, 22)
TOOTH = (255, 252, 242)
EYE_WHITE = (255, 253, 246)
PUPIL = (24, 14, 22)
BROW = (92, 18, 30)
THREAD = (70, 14, 30)
WHITE = (255, 255, 255)

m = Model("PizzasauroRex", "pet")


# ---------------------------------------------------------------- helper locali
def seg2(x, z, a, b, r):
    """Distanza 2D da un segmento (a, b) con raggio r, nel piano locale (x, z)."""
    px, pz = x - a[0], z - a[1]
    ex, ez = b[0] - a[0], b[1] - a[1]
    t = np.clip((px * ex + pz * ez) / (ex * ex + ez * ez + 1e-12), 0.0, 1.0)
    dx, dz = px - ex * t, pz - ez * t
    return np.sqrt(dx * dx + dz * dz) - r


def circ2(x, z, c, r):
    return np.sqrt((x - c[0]) ** 2 + (z - c[1]) ** 2) - r


def stencil(fn2d, xr, zr, depth=0.35):
    """Estrude una forma 2D fn2d(x, z) lungo l'asse locale Y (decalcomania da Frame.place)."""
    def f(p):
        return np.maximum(fn2d(p[:, 0], p[:, 2]), np.abs(p[:, 1]) - depth)
    return SDF(f, (xr[0], -depth, zr[0]), (xr[1], depth, zr[1]))


def drip(length, w):
    """Colata verso il basso (locale -Z) che finisce con una goccia tonda."""
    def fn(x, z):
        bar = seg2(x, z, (0, 0.15), (0, -length), w)
        return smin(bar, circ2(x, z, (0, -length - w * 0.25), w * 1.45), 0.07)
    return stencil(fn, (-w * 2.2, w * 2.2), (-length - w * 2.2, 0.3))


def leaf(L, W, T, fold=0.35):
    """Foglia a punta piegata a V lungo la nervatura: asse lungo -Y locale, larghezza su Z, sottile su X."""
    c = W * 0.5
    A = L * 0.577
    t = T / 0.866
    flat = ellipsoid((t, A, W), (0, -L * 0.5, c)).intersect(ellipsoid((t, A, W), (0, -L * 0.5, -c)))

    def fold_pts(p):
        q = p.copy()
        q[:, 0] = q[:, 0] + fold * np.abs(q[:, 2])
        return q
    return flat.warp(fold_pts, pad=fold * W * 0.6)


def at(base, src, d):
    p, _ = project(base, src, d)
    return p


def normal_at(base, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float32)
    g = np.array([base((p + e)[None, :])[0] - base((p - e)[None, :])[0]
                  for e in np.eye(3, dtype=np.float32) * eps])
    return g / max(np.linalg.norm(g), 1e-9)


def grin_edges(u, a, h, curve, skew):
    """Bordi superiore/inferiore di un ghigno a mezzaluna (u: ascissa, >0 = destra dell'immagine)."""
    t = np.clip(u / a, -1.0, 1.0)
    top = curve * t * t + skew * t
    bot = top - h * np.power(np.clip(1.0 - t * t, 0.0, 1.0), 0.7)
    return top, bot


def grin_paint(base, frame, a, h, curve, skew, off=0.014, depth=0.5):
    def fn(x, z):
        top, bot = grin_edges(-x, a, h, curve, skew)
        return np.maximum(np.maximum(z - top, bot - z), np.abs(x) - a) * 0.8
    lo, hi = -h - abs(skew) - 0.05, curve + abs(skew) + 0.05
    return base.offset(off).intersect(frame.place(stencil(fn, (-a - 0.05, a + 0.05), (lo, hi), depth)))


def grin_teeth(base, frame, src, a, h, curve, skew, n_top, n_bot, L, r, lift=0.016):
    """Dentini aguzzi lungo il bordo superiore (verso il basso) e inferiore (verso l'alto)."""
    src = np.asarray(src, dtype=np.float64)
    out = []
    rows = [(n_top, 0.84, 1.0, 0.55), (n_bot, 0.7, -1.0, 0.42)]
    for n, span, sign, frac in rows:
        for i in range(n):
            u = a * span * (-1.0 + 2.0 * (i + 0.5) / n)
            top, bot = grin_edges(u, a, h, curve, skew)
            li = min(L * (1.0 if sign > 0 else 0.8), (top - bot) * frac)
            if li < 0.03:
                continue
            z0 = top - 0.004 if sign > 0 else bot + 0.004
            z1 = z0 - sign * li
            pa, na = project(base, src, frame.point((-u, -0.3, z0)) - src)
            pb, nb = project(base, src, frame.point((-u, -0.3, z1)) - src)
            out.append(round_cone(pa + na * lift, pb + nb * lift, r, 0.006))
    return union(*out)


def stitches(base, pts, n, dash, r, across=True, lift=0.006):
    """Punti di cucitura (trattini) lungo una polilinea che sta sulla superficie."""
    pts = np.asarray(pts, dtype=np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for t in np.linspace(0.0, s[-1], n):
        i = min(np.searchsorted(s, t, side="right") - 1, len(seg) - 1)
        w = (t - s[i]) / max(seg[i], 1e-9)
        p = pts[i] * (1 - w) + pts[i + 1] * w
        tan = (pts[i + 1] - pts[i]) / max(seg[i], 1e-9)
        nrm = normal_at(base, p)
        d = np.cross(nrm, tan) if across else tan - nrm * float(tan @ nrm)
        d /= np.linalg.norm(d)
        c = p + nrm * lift
        out.append(capsule(c - d * dash * 0.5, c + d * dash * 0.5, r))
    return union(*out)


def rotp(p, R, pivot):
    return R @ (np.asarray(p, dtype=np.float32) - np.asarray(pivot, dtype=np.float32)) + np.asarray(pivot, dtype=np.float32)


# ---------------------------------------------------------------- corpo
NECK = (0.0, -0.1, 1.62)
HEAD_TILT = (7.0, 9.0, 0.0)  # testa un po' bassa e inclinata: sguardo da bullo
RH = euler(*HEAD_TILT)
HEAD_C = tuple(rotp((0.0, -0.16, 2.16), RH, NECK))
SNOUT_C = tuple(rotp((0.0, -0.8, 1.94), RH, NECK))
BODY_C = (0.0, 0.12, 1.08)
body = ellipsoid((0.8, 0.74, 0.8), BODY_C)
head = union(ellipsoid((0.86, 0.8, 0.72), (0.0, -0.16, 2.16)),
             ellipsoid((0.66, 0.62, 0.45), (0.0, -0.8, 1.94)),
             ellipsoid((0.58, 0.52, 0.3), (0.0, -0.74, 1.72)), k=0.22).rot(*HEAD_TILT, pivot=NECK)
legs = []
for sx in (1, -1):
    legs += [ellipsoid((0.31, 0.37, 0.42), (sx * 0.52, 0.04, 0.62)),
             capsule((sx * 0.53, -0.02, 0.5), (sx * 0.55, -0.14, 0.22), 0.21),
             ellipsoid((0.29, 0.42, 0.17), (sx * 0.55, -0.24, 0.17))]
TAIL_PTS = bezier((0.0, 0.62, 0.98), (0.05, 1.15, 0.68), (0.34, 1.58, 0.34), (0.8, 1.74, 0.36), 14)
tail = tube(TAIL_PTS, [0.44 - 0.026 * i for i in range(15)])
# braccine (corte, da T-rex) con manone a tre dita tozze
HANDS = []
arm_parts = []
for sx in (1, -1):
    sh = (sx * 0.5, -0.46, 1.42)
    wr = (sx * 0.62, -0.88, 1.3)
    HANDS.append((sx, wr))
    arm_parts += [capsule(sh, wr, 0.105), sphere(0.13, wr)]
    for dx, dz in ((-0.07, 0.06), (0.0, -0.02), (0.08, 0.04)):
        tip = (wr[0] + sx * 0.04 + dx, wr[1] - 0.15, wr[2] + dz - 0.06)
        arm_parts.append(capsule(wr, tip, 0.055))
core = union(body, head, k=0.4)
core = union(core, *legs, tail, k=0.14)
core = union(core, union(*arm_parts, k=0.05), k=0.07)
_nos = [at(core, SNOUT_C, tuple(RH @ np.array([sx * 0.3, -1.0, 0.62], dtype=np.float32))) for sx in (1, -1)]
core = core.subtract(union(*[sphere(0.05, p) for p in _nos]), k=0.04)


# pomodoro sulla schiena e sulla testa (regione con bordo ondulato)
def sauce_fn(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    head_cap = (2.74 - 0.62 * (y + 0.9)) - z
    back = np.maximum((1.64 - 0.95 * (y - 0.1)) - z, 0.08 - y)
    d = smin(head_cap, back, 0.1) * 0.75
    ang = np.arctan2(x, y - 0.25)
    return d + 0.026 * np.sin(11.0 * ang) + 0.014 * np.sin(23.0 * ang + 1.3)


# cornicione: la crosta si gonfia in un bordo morbido attorno al pomodoro, come una pizza
_base = core


def _rim(p):
    return _base(p) - 0.06 * np.exp(-((sauce_fn(p) - 0.07) / 0.05) ** 2)


core = SDF(_rim, _base.lo - 0.1, _base.hi + 0.1)
m.add("Body", core, CRUST, tris=4600)

# pancia di impasto chiaro con una cucitura da peluche
belly_region = ellipsoid((0.6, 0.7, 0.62), (0.0, -0.6, 1.04))
m.add("Belly", core.offset(0.02).intersect(belly_region), DOUGH, role="detail", tris=600)

sauce = core.offset(0.02).intersect(SDF(sauce_fn, (-5, -5, -5), (5, 5, 5)))
m.add("Sauce", sauce, SAUCE, role="detail", tris=1500)

# mozzarella: fette tonde che si sciolgono sul pomodoro, con una colata grossa oltre il bordo
cheese = []
for src, d, r in [
    (HEAD_C, (-0.5, 0.0, 0.85), 0.25), (HEAD_C, (0.35, 0.85, 0.45), 0.2),
    (BODY_C, (0.62, 0.62, 0.55), 0.25), (BODY_C, (-0.66, 0.62, 0.4), 0.24), (BODY_C, (0.15, 1.0, -0.1), 0.2),
]:
    cheese.append(sphere(r, at(core, src, d)))
for src, d, L in [
    (HEAD_C, (-0.82, -0.3, 0.5), 0.16), (HEAD_C, (0.95, 0.4, 0.3), 0.18),
    (BODY_C, (0.92, 0.35, 0.5), 0.2), (BODY_C, (-0.92, 0.35, 0.5), 0.18), (BODY_C, (-0.7, 0.85, -0.05), 0.12),
]:
    cheese.append(Frame(core, src, d).place(drip(L, 0.1), (0, 0, 0.08)))
m.add("Cheese", core.offset(0.034).intersect(union(*cheese, k=0.05)), CHEESE, role="detail", tris=1500)

# fette di salame piccante (dischi rialzati, bordo morbido)
pep = []
for src, d, r in [
    (HEAD_C, (0.5, 0.25, 0.85), 0.17), (HEAD_C, (-0.45, 0.75, 0.5), 0.15),
    (BODY_C, (0.45, 0.88, 0.15), 0.18), (BODY_C, (-0.38, 0.92, 0.62), 0.17), (BODY_C, (0.72, 0.42, 0.75), 0.15),
    (BODY_C, (-0.82, 0.45, -0.05), 0.14),
]:
    pep.append(sphere(r, at(core, src, d)))
pep.append(sphere(0.13, at(core, TAIL_PTS[7], (0.45, 0.25, 1.0))))
pep.append(sphere(0.1, at(core, TAIL_PTS[11], (-0.1, 0.1, 1.0))))
m.add("Pepperoni", core.offset(0.05).intersect(union(*pep), k=0.02), PEPPERONI, role="detail", tris=800)

# cresta di foglie di basilico lungo la spina dorsale (alternate, inclinate all'indietro)
leaves = []
crest = [
    (HEAD_C, tuple(RH @ np.array([0.0, -0.45, 1.0], dtype=np.float32)), 0.56, 0.38, 14, 14),
    (HEAD_C, tuple(RH @ np.array([0.0, 0.12, 1.0], dtype=np.float32)), 0.66, 0.44, 20, -14),
    (HEAD_C, (0.0, 0.78, 0.72), 0.6, 0.4, 24, 14), (BODY_C, (0.0, 1.0, 0.85), 0.58, 0.38, 24, -14),
    (BODY_C, (0.0, 1.0, 0.3), 0.54, 0.36, 26, 14), (TAIL_PTS[4], (0.05, 0.3, 1.0), 0.5, 0.33, 24, -14),
    (TAIL_PTS[8], (-0.2, 0.3, 1.0), 0.42, 0.28, 24, 12), (TAIL_PTS[12], (-0.3, 0.2, 1.0), 0.32, 0.22, 24, -10),
]
for src, d, L, W, tilt, yaw in crest:
    f = Frame(core, src, d, sink=0.07)
    leaves.append(f.place(leaf(L, W, 0.04).rot(tilt, 0, 0).rot(0, yaw * 0.6, 0)))
m.add("Basil", union(*leaves), BASIL, role="detail", tris=1400, voxel=0.014)

# ---------------------------------------------------------------- muso da bullo
# occhi: bianco visibile, pupille piccole, palpebra superiore storta e sopracciglia a V
EYE_R = (0.17, 0.1, 0.21)
eye_frames = [Frame(core, HEAD_C, tuple(RH @ np.array([0.43 * sx, -1.0, 0.36], dtype=np.float32)), sink=0.05)
              for sx in (1, -1)]
m.add("EyeWhites", union(*[f.place(ellipsoid(EYE_R)) for f in eye_frames]), EYE_WHITE, role="shine",
      tris=500, voxel=0.013)
pupils, shines, lids = [], [], []
for f, sx in zip(eye_frames, (1, -1)):
    px, pz = 0.035 * sx, -0.045  # pupille strette, puntate un po' in basso verso il centro
    py = -EYE_R[1] * math.sqrt(max(1 - (px / EYE_R[0]) ** 2 - (pz / EYE_R[2]) ** 2, 0.0))
    pupils.append(f.place(ellipsoid((0.068, 0.04, 0.085)), (px, py + 0.022, pz)))
    shines.append(f.place(sphere(0.026), (px - 0.025, py - 0.012, pz + 0.035)))
    # palpebra: guscio sopra l'occhio tagliato da un piano inclinato (piu' basso verso il naso)
    slope = 0.55

    def lid_cut(p, sx=sx, slope=slope):
        return (0.07 - slope * sx * p[:, 0] - p[:, 2]) / math.sqrt(1 + slope * slope)
    shell = ellipsoid((EYE_R[0] + 0.03, EYE_R[1] + 0.03, EYE_R[2] + 0.03))
    lids.append(f.place(shell.intersect(SDF(lambda p, c=lid_cut: c(p), shell.lo, shell.hi))))
m.add("Pupils", union(*pupils), PUPIL, role="eye", tris=400, voxel=0.01)
m.add("Shine", union(*shines), WHITE, role="shine", tris=200, voxel=0.008)
m.add("Lids", union(*lids), CRUST, role="skin", tris=500, voxel=0.012)

brows = []
for f, sx in zip(eye_frames, (1, -1)):
    # (x verso il naso, z): estremo interno basso, esterno alto -> sopracciglia a V da bullo
    pts = [f.point((sx * xi, 0.0, z)) for xi, z in ((-0.21, 0.43), (-0.09, 0.39), (0.03, 0.33), (0.15, 0.26))]
    pts = project_curve(core, [tuple(q) for q in pts], -f.normal, inset=0.0, start_back=0.4)
    brows.append(tube(pts, [0.05, 0.062, 0.062, 0.048]))
m.add("Brows", union(*brows, k=0.02), BROW, role="detail", tris=500, voxel=0.012)

# ghigno enorme da orecchio a orecchio, pieno di dentini aguzzi
mouth_f = Frame(core, SNOUT_C, tuple(RH @ np.array([0.0, -1.0, -0.36], dtype=np.float32)))
GA, GH, GC, GS = 0.52, 0.2, 0.16, 0.05
m.add("Mouth", grin_paint(core, mouth_f, GA, GH, GC, GS), MOUTH, role="detail", tris=500, voxel=0.011)
teeth = grin_teeth(core, mouth_f, SNOUT_C, GA, GH, GC, GS, n_top=11, n_bot=8, L=0.085, r=0.026)
claws = []
for sx in (1, -1):
    for dx in (-0.15, 0.0, 0.15):
        claws.append(round_cone((sx * 0.55 + dx, -0.56, 0.13), (sx * 0.55 + dx * 1.15, -0.7, 0.08), 0.065, 0.02))
for sx, wr in HANDS:
    for dx, dz in ((-0.07, 0.06), (0.0, -0.02), (0.08, 0.04)):
        tip = np.array((wr[0] + sx * 0.04 + dx, wr[1] - 0.15, wr[2] + dz - 0.06))
        d = tip - np.array(wr)
        d /= np.linalg.norm(d)
        claws.append(round_cone(tuple(tip + d * 0.02), tuple(tip + d * 0.1 + np.array([0, 0, -0.03])), 0.035, 0.008))
m.add("Teeth", union(teeth, *claws), TOOTH, role="detail", tris=1100, voxel=0.01)

# cucitura da peluche lungo la pancia (punti incrociati)
seam = project_curve(core, [(0.0, -1.0, z) for z in np.linspace(1.48, 0.62, 10)], (0, -1, 0), inset=-0.012)
m.add("Stitches", stitches(core, seam, 9, 0.13, 0.017), THREAD, role="detail", tris=500, voxel=0.01)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
