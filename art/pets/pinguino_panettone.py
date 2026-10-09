"""Pinguino Panettone - pet Mitico (creatura meme originale). Carattere: furbetto (occhiata di lato, ghigno a dentini)."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capsule, cylinder, ellipsoid, project, revolve,  # noqa: E402
                     round_cone, smin, sphere, tube, union)
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
    """Palpebra superiore pesante e linea scura del bordo (coordinate locali dell'occhio)."""
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


# ============================================================ colori
PAPER = (210, 22, 40)
PAPER_GOLD = (255, 188, 36)
CRUST = (194, 108, 34)
CRUST_DARK = (120, 56, 20)
SUGAR = (255, 252, 244)
BLACK = (28, 28, 52)
WHITE = (255, 255, 255)
ORANGE = (255, 128, 18)
EYE = (22, 16, 34)
CHERRY = (232, 18, 50)
RAISIN = (84, 30, 48)
CANDIED = (255, 146, 24)
THREAD = (226, 30, 56)

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
m.add("Paper", paper, PAPER, role="skin", tris=2400, voxel=0.02)
rim = pleated_cylinder(0.92, 1.56, 1.74, 28, 0.035).subtract(cylinder((0, 0, 1.3), (0, 0, 2.0), 0.82))
rim = union(rim, pleated_cylinder(0.92, 0.14, 0.3, 28, 0.035).subtract(cylinder((0, 0, 0.0), (0, 0, 0.5), 0.82)))
m.add("PaperRim", rim, PAPER_GOLD, role="detail", tris=1000, voxel=0.02)


# cupola del panettone che deborda dalla carta
def dome_profile(z):
    t = np.clip((z - 1.66) / 0.78, 0, 1)
    return 1.0 * np.sqrt(np.clip(1 - t ** 2.4, 0, 1))


dome = revolve(dome_profile, 1.02, 1.66, 2.44)
dome = union(dome, cylinder((0, 0, 1.55), (0, 0, 1.8), 0.86), k=0.08)
m.add("Dome", dome, CRUST, role="skin", tris=1800, voxel=0.02)
m.add("DomeTop", dome.offset(0.016).intersect(sphere(1.0, (0, 0, 2.95))), CRUST_DARK, role="detail", tris=1000, voxel=0.02)

# zucchero a velo, uvetta e canditi sulla crosta (meno pezzi, piu' grandi)
rng = np.random.default_rng(7)
sugar, raisins, candied = [], [], []
for i in range(110):
    a = rng.uniform(0, 2 * math.pi)
    up = rng.uniform(-0.1, 1.4)
    p, n = project(dome, (0, 0, 1.9), (math.cos(a), math.sin(a), up))
    if np.hypot(p[0], p[1]) < 0.64 or p[2] < 1.75:
        continue  # lascia libero il collo del pinguino
    kind = rng.random()
    if kind < 0.62 and len(sugar) < 34:
        sugar.append(sphere(rng.uniform(0.04, 0.055), p + n * 0.005))
    elif 0.62 <= kind < 0.84 and len(raisins) < 12:
        raisins.append(ellipsoid((0.075, 0.075, 0.055), p))
    elif kind >= 0.84 and len(candied) < 9:
        candied.append(ellipsoid((0.085, 0.065, 0.055), p))
m.add("Sugar", fast_union(sugar), SUGAR, role="detail", tris=700, voxel=0.014)
m.add("Raisins", fast_union(raisins), RAISIN, role="detail", tris=400, voxel=0.015)
m.add("Candied", fast_union(candied), CANDIED, role="detail", tris=300, voxel=0.015)

# ------------------------------------------------------------------ pinguino che spunta dalla cupola (testa inclinata)
TILT, PIVOT = -8.0, (0.0, 0.0, 2.3)


def T(s):
    return s.rot(0, TILT, 0, pivot=PIVOT)


HEAD_C = (0, -0.04, 2.84)
head = ellipsoid((0.74, 0.7, 0.68), HEAD_C)
neck = cylinder((0, 0, 2.2), (0, 0, 2.62), 0.56)
penguin = union(head, neck, k=0.2)
m.add("Head", T(penguin), BLACK, role="skin", tris=2000, voxel=0.02)
MASK_PARTS = [((0.36, 0.5, 0.42), (0.22, -0.5, 2.79)), ((0.36, 0.5, 0.42), (-0.22, -0.5, 2.79)), ((0.4, 0.5, 0.3), (0, -0.5, 2.52))]
mask = union(*[ellipsoid(r, c) for r, c in MASK_PARTS], k=0.12)
face_surf = penguin.offset(0.02)

# occhiata furba di lato: bianco dell'occhio contornato, pupille spostate, palpebre pesanti
EA, EB, EC = 0.15, 0.085, 0.18
frames = [Frame(head, HEAD_C, (0.38 * sx, -1.0, 0.12), sink=0.03) for sx in (1, -1)]
whites, darks, lids, hls = [], [], [], []
for f, sx in zip(frames, (1, -1)):
    whites.append(f.place(ellipsoid((EA, EB, EC))))
    darks.append(f.place(tube([(EA * 0.88 * math.cos(t), -0.042, EC * 0.88 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 41)], 0.015)))
    # pupille verso il lato -X del mondo (= +X locale) e un po' in basso
    darks.append(f.place(ellipsoid((0.06, 0.04, 0.075)), (0.07, -EB * 0.78, -0.05)))
    lid, lash = lid_parts(f, EA, EB, EC, cut=(0.04 if sx > 0 else 0.0), slope=sx * 0.05)
    lids.append(lid)
    darks.append(lash)
    hls.append(f.place(sphere(0.02), (0.05, -EB * 0.78 - 0.035, -0.03)))

# ghigno storto con dentini sotto il becco
MOUTH = dict(cx=0.04, cz=2.6, w=0.27, depth=0.08, curve=0.08, tilt=0.06)
mouth_surf = penguin.offset(0.034)
mouth = mouth_surf.intersect(grin_sdf(**MOUTH, y_max=-0.4))
teeth = grin_teeth(mouth_surf, HEAD_C[1], **MOUTH, n=8, length=0.04, r=0.017)

# cucitura attorno alla maschera bianca (fino al bordo della cupola)
mask_edge = []
for phi in np.linspace(math.radians(-30), math.radians(210), 40):
    lo_r, hi_r = 0.05, 0.9
    for _ in range(18):
        r_ = 0.5 * (lo_r + hi_r)
        q = curve_on(penguin, [(r_ * math.cos(phi), HEAD_C[1], 2.66 + r_ * math.sin(phi))])[0]
        if float(mask(q[None, :].astype(np.float32))[0]) < 0:
            lo_r = r_
        else:
            hi_r = r_
    q = curve_on(penguin, [(lo_r * math.cos(phi), HEAD_C[1], 2.66 + lo_r * math.sin(phi))])[0]
    if q[2] > 2.5:
        mask_edge.append(q)
seam = stitch_row(penguin.offset(0.01), mask_edge, dash=0.045, gap=0.05, r=0.016, cross=True, cross_len=0.09)

m.add("Face", T(union(face_surf.intersect(mask), *lids)), WHITE, role="detail", tris=1300, voxel=0.016)
beak = union(ellipsoid((0.2, 0.2, 0.1), (0, -0.07, 0.02)), ellipsoid((0.14, 0.13, 0.07), (0, -0.04, -0.09)), k=0.04)
m.add("Beak", T(Frame(head, HEAD_C, (0, -1.0, -0.06), sink=0.07).place(beak)), ORANGE, role="detail", tris=500, voxel=0.014)
m.add("Eyes", T(union(*darks, mouth)), EYE, role="eye", tris=1100, voxel=0.01)
m.add("Shine", T(union(*whites, *hls, *teeth)), WHITE, role="shine", tris=700, voxel=0.01)
m.add("Stitches", T(fast_union(seam)), THREAD, role="detail", tris=700, voxel=0.01)

# ciliegina candita in testa
cherry = union(sphere(0.2, (0.12, 0.05, 3.62)), tube(bezier((0.12, 0.05, 3.78), (0.14, 0.05, 3.96), (0.26, 0.08, 4.04), (0.34, 0.1, 4.0), 8), 0.025))
m.add("Cherry", T(cherry), CHERRY, material="Glass", role="detail", tris=400, voxel=0.012)

# pinne che escono dalla carta (animabili) e zampe
fl = ellipsoid((0.14, 0.32, 0.5), (0, 0, 0)).rot(0, 38, 0).translate((1.05, -0.05, 1.12))
m.add("FlipperR", fl, BLACK, role="skin", tris=400, group="FlipperR", pivot=(0.88, -0.05, 1.38))
m.add("FlipperL", fl.mirrored(), BLACK, role="skin", tris=400, group="FlipperL", pivot=(-0.88, -0.05, 1.38))
feet = union(*[union(ellipsoid((0.3, 0.38, 0.12), (sx * 0.38, -0.55, 0.12)),
                     *[capsule((sx * 0.38, -0.6, 0.09), (sx * 0.38 + dx, -0.92, 0.085), 0.085) for dx in (-0.16, 0, 0.16)], k=0.08)
               for sx in (1, -1)])
m.add("Feet", feet, ORANGE, role="detail", tris=700)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
