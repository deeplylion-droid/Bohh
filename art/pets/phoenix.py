"""Fenice (Phoenix) - pet Leggendario, volante. Carattere: sbruffone (sguardo sornione, ghigno aguzzo)."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, box, capsule, cylinder, ellipsoid, project, round_cone, smin,  # noqa: E402
                     sphere, stick, torus, tube, union)
from lib.toy import Model  # noqa: E402


# ============================================================ helper "toy horror" (lib/ non si modifica: copiati qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def grad(sdf, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float64)
    g = np.zeros(3)
    for ax in range(3):
        e = np.zeros(3)
        e[ax] = eps
        g[ax] = sdf((p + e)[None, :].astype(np.float32))[0] - sdf((p - e)[None, :].astype(np.float32))[0]
    return g / max(np.linalg.norm(g), 1e-9)


def on_surface(sdf, p, lift=0.0, iters=4):
    """Porta p sulla superficie (a distanza 'lift' verso l'esterno) seguendo il gradiente."""
    p = np.asarray(p, dtype=np.float64)
    for _ in range(iters):
        d = float(sdf(p[None, :].astype(np.float32))[0])
        p = p - grad(sdf, p) * (d - lift)
    return p


def flatten(shape, s, axis=1):
    """Schiaccia (s<1) o allunga (s>1) una forma lungo un asse, con distanza conservativa."""
    def f(p):
        q = p.copy()
        q[:, axis] = q[:, axis] / s
        return shape(q) * min(s, 1.0)

    lo, hi = shape.lo.copy(), shape.hi.copy()
    lo[axis] *= s
    hi[axis] *= s
    return SDF(f, lo, hi)


def fast_union(shapes, k=0.0, base=None, margin=0.06):
    """Unione di tante forme piccole, ognuna valutata solo vicino al proprio ingombro."""
    shapes = list(shapes)
    los = np.array([s.lo for s in shapes]) - margin - k
    his = np.array([s.hi for s in shapes]) + margin + k

    def f(p):
        d = base(p) if base is not None else np.full(len(p), 1.0, dtype=np.float32)
        if len(p) == 0:
            return d
        plo, phi = p.min(0), p.max(0)
        for i in np.nonzero(np.all((his >= plo) & (los <= phi), axis=1))[0]:
            msk = np.all((p >= los[i]) & (p <= his[i]), axis=1)
            if msk.any():
                idx = np.nonzero(msk)[0]
                d[idx] = smin(d[idx], shapes[i](p[idx]), k)
        return d

    lo, hi = los.min(0), his.max(0)
    if base is not None:
        lo, hi = np.minimum(lo, base.lo), np.maximum(hi, base.hi)
    return SDF(f, lo, hi)


def resample(points, step):
    pts = np.asarray(points, dtype=np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(int(round(cum[-1] / step)), 1)
    out = []
    for s in np.linspace(0.0, cum[-1], n + 1):
        i = int(min(np.searchsorted(cum, s, side="right") - 1, len(seg) - 1))
        t = (s - cum[i]) / max(seg[i], 1e-9)
        out.append(pts[i] * (1 - t) + pts[i + 1] * t)
    return out


def curve_on(sdf, pts, direction=(0, -1, 0), lift=0.0):
    """Proietta punti (interni alla forma) sulla superficie lungo 'direction'."""
    d = norm(direction)
    out = []
    for q in pts:
        p, n = project(sdf, np.asarray(q, float), d)
        out.append(np.asarray(p, float) + np.asarray(n, float) * lift)
    return out


def stitch_row(sdf, pts, dash=0.075, gap=0.05, r=0.017, cross=False, cross_len=0.11, sink=0.35, closed=False):
    """Cucitura sulla superficie: trattini lungo la linea, oppure punti trasversali (cross=True)."""
    pts = list(pts) + ([pts[0]] if closed else [])
    pts = resample(pts, (dash + gap) * (0.8 if cross else 1.0))
    out = []
    for i in range(len(pts) if cross else len(pts) - 1):
        if cross:
            p = pts[i]
            t = norm(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)])
            side = norm(np.cross(t, grad(sdf, p)))
            a = on_surface(sdf, p - side * cross_len / 2, -r * sink, 3)
            b = on_surface(sdf, p + side * cross_len / 2, -r * sink, 3)
        else:
            a = on_surface(sdf, pts[i], -r * sink, 2)
            b = on_surface(sdf, pts[i] + (pts[i + 1] - pts[i]) * dash / (dash + gap), -r * sink, 2)
        out.append(capsule(tuple(a), tuple(b), r))
    return out


def grin_sdf(cx, cz, w, depth, curve, tilt=0.0, y_max=-0.2, power=0.75):
    """Bocca a mezzaluna nel piano XZ (estrusa lungo Y, solo per y < y_max)."""
    def f(p):
        x = (p[:, 0] - cx) / w
        up = cz + curve * x * x + tilt * x
        lo = up - depth * np.clip(1.0 - x * x, 0.0, None) ** power
        d = np.maximum(np.maximum(p[:, 2] - up, lo - p[:, 2]), (np.abs(x) - 1.0) * w)
        return np.maximum(d, p[:, 1] - y_max)

    pad = abs(curve) + abs(tilt) + depth + 0.05
    return SDF(f, (cx - w, -6.0, cz - pad), (cx + w, y_max, cz + pad))


def grin_teeth(surf, y_in, cx, cz, w, depth, curve, tilt=0.0, n=8, length=0.08, r=0.03, lower=0,
               power=0.75, span=0.84, lift=0.006):
    """Dentini aguzzi bianchi lungo il bordo superiore (e inferiore) della bocca."""
    def tooth(x, upper):
        up = cz + curve * x * x + tilt * x
        open_h = depth * max(1.0 - x * x, 0.0) ** power
        z_edge = up if upper else up - open_h
        s = -1.0 if upper else 1.0
        L = min(length, 0.55 * open_h)
        X = cx + x * w
        base, tip = curve_on(surf, [(X, y_in, z_edge - s * 0.012), (X, y_in, z_edge + s * L)], lift=lift)
        return round_cone(tuple(base), tuple(tip), r * min(1.0, 0.45 + open_h / depth), 0.004)

    teeth = [tooth(-span + 2 * span * (i + 0.5) / n, True) for i in range(n)]
    teeth += [tooth(-span * 0.75 + 1.5 * span * (i + 0.5) / lower, False) for i in range(lower)]
    return teeth


def brow(surf, y_in, pts_xz, r=0.045, lift=0.0):
    """Sopracciglio spesso e affusolato (punti dal lato interno a quello esterno, nel piano XZ)."""
    pts = curve_on(surf, [(x, y_in, z) for x, z in pts_xz], lift=lift)
    pts = resample(pts, 0.04)
    n = len(pts)
    radii = [r * (0.72 + 0.28 * math.sin(math.pi * min(i / (n - 1) * 1.6, 1.0))) * (1.0 - 0.45 * (i / (n - 1)) ** 2)
             for i in range(n)]
    return tube([tuple(p) for p in pts], radii)


def lid_parts(frame, a, b, c, cut, slope=0.0, t=0.02, lash_r=0.02):
    """Palpebra superiore pesante (colore pelle) e linea scura del bordo (coordinate locali dell'occhio)."""
    A, B, C = a + t, b + t, c + t
    plane = SDF(lambda p: (cut + slope * p[:, 0] - p[:, 2]) / math.sqrt(1 + slope * slope), (-A, -B, -C), (A, B, C))
    lid = ellipsoid((A, B, C)).intersect(plane)
    pts = []
    for x in np.linspace(-A * 0.98, A * 0.98, 15):
        z = cut + slope * x
        q = 1 - (x / A) ** 2 - (z / C) ** 2
        if q > 0.01:
            pts.append((x, -B * math.sqrt(q), z))
    return frame.place(lid), frame.place(tube(pts, lash_r))


# ============================================================ colori e modello
BODY = (212, 38, 36)
BELLY = (255, 176, 34)
WING = (126, 16, 44)
FLAME = (255, 84, 16)
FLAME_IN = (255, 206, 48)
GOLD = (255, 168, 28)
EYE = (26, 10, 24)
ACCENT = (86, 10, 38)
WHITE = (255, 255, 255)


def tongue(p0, p1, p2, p3, r_base, r_peak, r_tip, peak=0.25, n=16):
    """Lingua di fiamma lungo una bezier: si allarga fino a 'peak' e poi si assottiglia in punta."""
    pts = bezier(p0, p1, p2, p3, n)
    radii = []
    for i in range(n + 1):
        t = i / n
        if t < peak:
            radii.append(r_base + (r_peak - r_base) * math.sin(t / peak * math.pi / 2))
        else:
            radii.append(r_tip + (r_peak - r_tip) * (1 - (t - peak) / (1 - peak)) ** 1.25)
    return tube(pts, radii)


def shrink_path(path, frac):
    p0, p1, p2, p3 = path
    return p0, p1, p2, tuple(frac * a + (1 - frac) * b for a, b in zip(p3, p2))


m = Model("Phoenix", "pet")
Z0 = 0.14  # tutto il corpo e' rialzato: si vedono le zampe

# ------------------------------------------------------------------ corpo con petto gonfio
HEAD_C = (0, -0.08, 1.95 + Z0)
head = ellipsoid((0.88, 0.82, 0.8), HEAD_C)
body = ellipsoid((0.94, 0.88, 0.8), (0, 0.06, 0.9 + Z0))
chest = ellipsoid((0.72, 0.5, 0.62), (0, -0.36, 1.0 + Z0))
core = union(body, head, k=0.4)
core = union(core, chest, k=0.25)
m.add("Body", core, BODY, tris=4400, voxel=0.025)

# pancia dorata cucita come una toppa
BELLY_C, BELLY_R = (0.0, 0.88 + Z0), (0.6, 0.52)
belly_region = SDF(lambda p: np.maximum(((p[:, 0] / BELLY_R[0]) ** 2 + ((p[:, 2] - BELLY_C[1]) / BELLY_R[1]) ** 2 - 1) * 0.3,
                                        p[:, 1] + 0.2), (-0.7, -2, 0.2), (0.7, -0.2, 1.7))
m.add("Belly", core.offset(0.022).intersect(belly_region), BELLY, role="detail", tris=1100)
belly_edge = curve_on(core.offset(0.011), [(BELLY_R[0] * math.cos(a), 0.0, BELLY_C[1] + BELLY_R[1] * math.sin(a))
                                           for a in np.linspace(0, 2 * math.pi, 64)])
seam = stitch_row(core.offset(0.011), belly_edge, dash=0.05, gap=0.06, r=0.016, cross=True, cross_len=0.1, closed=True)

# ------------------------------------------------------------------ fiamme: cresta + coda
CREST_BASE = (0, -0.02, 2.6 + Z0)
crest_front = [
    (((0, 0, 0), (0.16, 0, 0.32), (-0.16, 0, 0.6), (0.06, 0, 0.98)), 0.17, 0.22, 0.03),
    (((0.2, 0, -0.06), (0.38, 0, 0.14), (0.38, 0, 0.36), (0.58, 0, 0.62)), 0.13, 0.16, 0.025),
    (((-0.2, 0, -0.06), (-0.36, 0, 0.16), (-0.44, 0, 0.34), (-0.56, 0, 0.66)), 0.13, 0.16, 0.025),
]
crest_back = [
    (((0.12, 0, 0), (0.24, 0, 0.26), (0.1, 0, 0.46), (0.3, 0, 0.72)), 0.14, 0.17, 0.025),
    (((-0.12, 0, 0), (-0.26, 0, 0.24), (-0.12, 0, 0.44), (-0.32, 0, 0.7)), 0.14, 0.17, 0.025),
]


def place_crest(shape, back=0.0):
    return shape.rot(-20 - back * 60, 0, 0).translate((CREST_BASE[0], CREST_BASE[1] + back, CREST_BASE[2] - back * 0.25))


crest_out, crest_in = [], []
for rows, back in ((crest_front, 0.0), (crest_back, 0.24)):
    for path, rb, rp, rt in rows:
        crest_out.append(place_crest(flatten(tongue(*path, rb, rp, rt, peak=0.22), 0.6), back))
        crest_in.append(place_crest(flatten(tongue(*shrink_path(path, 0.5), rb * 0.45, rp * 0.45, 0.02, peak=0.22), 3.0), back))

PLUME = ((0, 0, 0), (0.7, 0, -0.28), (1.38, 0, 0.16), (1.02, 0, 1.68))
LICK = ((1.16, 0, 0.66), (1.34, 0, 0.74), (1.46, 0, 0.92), (1.58, 0, 1.12))


def plume(scale, heading, lift, base):
    sc = lambda path: tuple((x * scale, y, z * scale) for x, y, z in path)  # noqa: E731
    p, lk = sc(PLUME), sc(LICK)
    outer = union(tongue(*p, 0.09, 0.28 * scale, 0.03, peak=0.6, n=20),
                  tongue(*lk, 0.1 * scale, 0.11 * scale, 0.02, peak=0.2, n=8), k=0.06)
    inner = union(tongue(*shrink_path(p, 0.45), 0.02, 0.14 * scale, 0.02, peak=0.6, n=20),
                  tongue(*shrink_path(lk, 0.5), 0.04, 0.05, 0.02, peak=0.2, n=8), k=0.04)
    tf = lambda s: s.rot(0, -lift, 0).rot(0, 0, 90 - heading).translate(base)  # noqa: E731
    return tf(flatten(outer, 0.5)), tf(flatten(inner, 3.0))


plumes = [plume(1.0, 0, 6, (0, 0.6, 0.86 + Z0)), plume(0.92, 58, 16, (0.16, 0.58, 0.88 + Z0)),
          plume(0.92, -58, 16, (-0.16, 0.58, 0.88 + Z0))]
flames = union(*crest_out, *[p[0] for p in plumes])
m.add("Flames", flames, FLAME, material="Neon", role="glow", tris=2200, voxel=0.02)
flame_core = flames.offset(0.018).intersect(union(*crest_in, *[p[1] for p in plumes]))
m.add("FlameCore", flame_core, FLAME_IN, material="Neon", role="glow", tris=1200, voxel=0.016)

# ------------------------------------------------------------------ ali (animabili) con penne di fuoco
FEATHERS = [((1.08, 0, 0.34), 0.13), ((1.02, 0, 0.08), 0.13), ((0.9, 0, -0.15), 0.12), ((0.72, 0, -0.33), 0.11),
            ((0.5, 0, -0.43), 0.1)]
wing_local = union(
    ellipsoid((0.44, 0.17, 0.27), (0.34, 0, 0.0)),
    *[tongue((0.18, 0, 0.0), (0.5, 0, 0.05 + 0.4 * tz), (0.8 * tx, 0, 0.9 * tz + 0.06), (tx, 0, tz), r, r * 1.08, 0.03,
             peak=0.3, n=12) for (tx, _, tz), r in FEATHERS],
    k=0.06)
wing_local = flatten(wing_local, 0.48).scale(1.14)
tip_region_local = union(*[sphere(0.26, (tx * 1.04, 0, tz * 1.04)) for (tx, _, tz), _r in FEATHERS], k=0.06).scale(1.14)
SHOULDER = (0.74, 0.18, 1.38 + Z0)


def place_wing(s, sx):
    s = s.rot(0, -24, 0).rot(0, 0, 16).translate(SHOULDER)
    return s if sx > 0 else s.mirrored()


for sx, nm in ((1, "WingR"), (-1, "WingL")):
    piv = (sx * SHOULDER[0], SHOULDER[1], SHOULDER[2])
    m.add(nm, place_wing(wing_local, sx), WING, role="detail", tris=700, voxel=0.018, group=nm, pivot=piv)
    tips = place_wing(wing_local.offset(0.018).intersect(tip_region_local), sx)
    m.add(nm + "Fire", tips, FLAME, material="Neon", role="glow", tris=400, voxel=0.016, group=nm, pivot=piv)

# ------------------------------------------------------------------ faccia: occhi sornioni, sopracciglia, ghigno
EA, EB, EC = 0.17, 0.1, 0.23
frames = [Frame(head, HEAD_C, (0.42 * sx, -1.0, 0.07), sink=0.05) for sx in (1, -1)]
eyes, lids, lashes, shines = [], [], [], []
for f, sx in zip(frames, (1, -1)):
    eyes.append(f.place(ellipsoid((EA, EB, EC))))
    cut = 0.0 if sx > 0 else 0.055  # un occhio piu' chiuso dell'altro
    lid, lash = lid_parts(f, EA, EB, EC, cut, slope=-sx * 0.16)
    lids.append(lid)
    lashes.append(lash)
    shines.append(f.place(sphere(0.042), (-0.06, -0.082, -0.07)))
    shines.append(f.place(sphere(0.02), (0.06, -0.072, -0.15)))
m.add("Lids", union(*lids), BODY, role="skin", tris=600, voxel=0.012)

# ghigno aguzzo sotto il becco (asimmetrico: un angolo piu' alto)
MOUTH = dict(cx=0.02, cz=1.66 + Z0, w=0.36, depth=0.13, curve=0.1, tilt=0.06)
mouth = core.offset(0.02).intersect(grin_sdf(**MOUTH, y_max=-0.3))
m.add("Eyes", union(*eyes, *lashes, mouth), EYE, role="eye", tris=1200, voxel=0.011)
teeth = grin_teeth(core.offset(0.02), HEAD_C[1], **MOUTH, n=9, length=0.07, r=0.027)
m.add("Shine", union(*shines, *teeth), WHITE, role="shine", tris=700, voxel=0.009)

brows = [brow(core, HEAD_C[1], [(0.12, 2.39 + Z0), (0.26, 2.5 + Z0), (0.42, 2.52 + Z0), (0.55, 2.45 + Z0)], r=0.05),
         brow(core, HEAD_C[1], [(-0.12, 2.32 + Z0), (-0.27, 2.37 + Z0), (-0.43, 2.4 + Z0), (-0.56, 2.37 + Z0)], r=0.05)]
m.add("Accents", union(*brows, fast_union(seam)), ACCENT, role="detail", tris=1300, voxel=0.011)

# becco all'insu' (petto in fuori, mento alto) e zampe con dita tozze
beak = union(ellipsoid((0.18, 0.18, 0.1), (0, -0.07, 0.05)), ellipsoid((0.12, 0.11, 0.065), (0, -0.04, -0.07)), k=0.04)
beak = stick(beak.rot(-12, 0, 0), head, HEAD_C, (0, -1.0, -0.12), sink=0.07)


def leg(x):
    shin = capsule((x, -0.02, 0.5), (x * 1.04, -0.12, 0.14), 0.085)
    toes = [capsule((x * 1.04, -0.16, 0.09), (x * 1.04 + dx, -0.56, 0.085), 0.085) for dx in (-0.17, 0.0, 0.17)]
    heel = capsule((x * 1.04, -0.1, 0.08), (x * 1.04, 0.12, 0.08), 0.075)
    return union(shin, *toes, heel, sphere(0.12, (x * 1.04, -0.16, 0.125)), k=0.07)


m.add("Gold", union(beak, leg(0.34), leg(-0.34)), GOLD, role="detail", tris=1100, voxel=0.016)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
