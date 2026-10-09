"""Mucca Moka (MuccaMoka) - pet Mitico, creatura meme originale: una mucca che e' una caffettiera moka.

Carattere: furba (palpebre pesanti, sorrisetto storto con tre dentini, macchie cucite).
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capsule, cylinder, ellipsoid, project, round_cone, smax, smin,  # noqa: E402
                     sphere, tube, union)
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


def grin_teeth_at(surf, y_in, xs, cx, cz, w, depth, curve, tilt=0.0, length=0.08, r=0.03, power=0.75, lift=0.006):
    """Dentini aguzzi sul bordo superiore della bocca, nelle posizioni normalizzate xs (-1..1)."""
    teeth = []
    for x in xs:
        up = cz + curve * x * x + tilt * x
        open_h = depth * max(1.0 - x * x, 0.0) ** power
        L = min(length, 0.6 * open_h)
        base, tip = curve_on(surf, [(cx + x * w, y_in, up + 0.012), (cx + x * w, y_in, up - L)], lift=lift)
        teeth.append(round_cone(tuple(base), tuple(tip), r * min(1.0, 0.5 + open_h / depth), 0.004))
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


def blob_region(frame, r, wobble=0.14, phase=0.0, lobes=3, depth=0.6):
    """Macchia irregolare (raggio che ondeggia) nel piano tangente di 'frame'; ritorna (regione, contorno locale)."""
    def f(p):
        rho = np.sqrt(p[:, 0] ** 2 + p[:, 2] ** 2)
        th = np.arctan2(p[:, 2], p[:, 0])
        R = r * (1 + wobble * np.sin(lobes * th + phase))
        return np.maximum((rho - R) * 0.8, np.abs(p[:, 1]) - depth)

    e = r * (1 + wobble)
    local = SDF(f, (-e, -depth, -e), (e, depth, e))
    outline = [(r * (1 + wobble * math.sin(lobes * t + phase)) * math.cos(t), 0.0,
                r * (1 + wobble * math.sin(lobes * t + phase)) * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 48)]
    return frame.place(local), outline


# ============================================================ moka ottagonale
def oct_frustum(z0, z1, a0, a1, k=0.05):
    """Tronco di piramide ottagonale (apotema a0 in basso, a1 in alto) con spigoli ammorbiditi."""
    ns = [(math.cos(math.radians(45 * i)), math.sin(math.radians(45 * i))) for i in range(8)]
    slope = (a1 - a0) / (z1 - z0)
    inv = 1 / math.sqrt(1 + slope * slope)

    def f(p):
        a = a0 + slope * (p[:, 2] - z0)
        d = (p[:, 0] * ns[0][0] + p[:, 1] * ns[0][1] - a) * inv
        for nx, ny in ns[1:]:
            d = smax(d, (p[:, 0] * nx + p[:, 1] * ny - a) * inv, k)
        d = smax(d, z0 - p[:, 2], k)
        return smax(d, p[:, 2] - z1, k)

    R = max(a0, a1) / math.cos(math.pi / 8)
    return SDF(f, (-R, -R, z0), (R, R, z1))


METAL = (176, 184, 198)
BLACK = (30, 27, 33)
COW = (250, 248, 246)
PINK = (255, 116, 152)
HORN = (250, 224, 176)
EYE = (24, 14, 22)
WHITE = (255, 255, 255)

m = Model("MuccaMoka", "pet")

boiler = oct_frustum(0.1, 0.76, 0.74, 0.58)
waist = oct_frustum(0.74, 0.88, 0.61, 0.61, k=0.035)
collector = oct_frustum(0.86, 1.5, 0.56, 0.74)
lid_rim = oct_frustum(1.48, 1.58, 0.78, 0.78, k=0.035)
lid_top = oct_frustum(1.56, 1.68, 0.74, 0.52, k=0.04)
spout = flatten(round_cone((0.0, 0, 0.0), (0.38, 0, 0.17), 0.15, 0.022), 0.62).translate((0.64, 0, 1.38))
pot = union(boiler, waist, collector, lid_rim, lid_top, k=0.015)
pot = union(pot, spout, k=0.05)
m.add("Pot", pot, METAL, material="Metal", tris=5200, voxel=0.018)

# manico e pomello in bachelite nera, zoccoletti
handle = flatten(tube(bezier((-0.64, 0, 1.42), (-1.3, 0, 1.52), (-1.28, 0, 0.84), (-0.5, 0, 0.9), 16),
                      [0.13, 0.12, 0.115, 0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.115, 0.12, 0.12, 0.12, 0.12, 0.12]), 0.68)
HOOVES = [(sx * 0.42, y) for sx in (1, -1) for y in (-0.6, 0.5)]
hooves = union(*[cylinder((x, y, 0.0), (x, y, 0.2), 0.15, round=0.05) for x, y in HOOVES])

# ------------------------------------------------------------------ testa di mucca che esce dal coperchio
HEAD_C = (0, -0.06, 2.24)
head = ellipsoid((0.78, 0.68, 0.66), HEAD_C)
neck = capsule((0, 0.0, 1.58), (0, -0.03, 1.92), 0.4)
EAR = [(sx * 0.84, 0.0, 2.36) for sx in (1, -1)]
ears = union(*[ellipsoid((0.24, 0.09, 0.13)).rot(0, -sx * 18, 0).translate(c) for sx, c in zip((1, -1), EAR)])
head_all = union(union(head, neck, k=0.15), ears, k=0.06)

SN_C = (0, -0.66, 1.98)
snout = ellipsoid((0.54, 0.34, 0.32), SN_C)
horns = union(*[tube(bezier((sx * 0.4, 0.0, 2.68), (sx * 0.56, 0.0, 2.86), (sx * 0.72, -0.05, 2.97), (sx * 0.74, -0.12, 3.08), 10),
                     [0.115 - 0.0062 * i for i in range(11)]) for sx in (1, -1)])
knob = union(ellipsoid((0.16, 0.16, 0.1), (0, 0.04, 2.97)), cylinder((0, 0.04, 2.74), (0, 0.04, 2.94), 0.065))

# macchie nere cucite (una attorno all'occhio destro)
head_surf = head_all.offset(0.018)
spots, spot_stitches = [], []
for d, r, ph in (((0.5, -0.8, 0.36), 0.33, 0.6), ((-0.55, 0.15, 0.82), 0.3, 2.0), ((0.35, 0.9, 0.3), 0.28, 4.1),
                 ((-0.7, 0.55, -0.1), 0.22, 1.0)):
    fr = Frame(head, HEAD_C, d, sink=0.0)
    region, outline = blob_region(fr, r, phase=ph)
    spots.append(head_surf.intersect(region))
    pts = [fr.point(q) for q in outline]
    pts = [on_surface(head_all.offset(0.009), p) for p in pts]
    spot_stitches += stitch_row(head_all.offset(0.009), pts, dash=0.05, gap=0.05, r=0.019, cross=True, cross_len=0.11, closed=True)

# ------------------------------------------------------------------ faccia furba
EA, EB, EC = 0.17, 0.095, 0.21
frames = [Frame(head, HEAD_C, (0.55 * sx, -1.0, 0.36), sink=0.045) for sx in (1, -1)]
eyes, lashes, shines, lids_white, lids_black = [], [], [], [], []
for f, sx in zip(frames, (1, -1)):
    eyes.append(f.place(ellipsoid((EA, EB, EC))))
    lid, lash = lid_parts(f, EA, EB, EC, cut=(-0.03 if sx > 0 else 0.05), slope=sx * 0.06)
    (lids_black if sx > 0 else lids_white).append(lid)
    lashes.append(lash)
    shines.append(f.place(sphere(0.036), (-0.05, -0.078, -0.07)))
    shines.append(f.place(sphere(0.017), (0.056, -0.07, -0.125)))
# sopracciglio alzato (nero) sul lato bianco; sul lato della macchia un sopracciglio bianco, rilassato
brow_up = brow(head, HEAD_C[1], [(-0.14, 2.75), (-0.29, 2.82), (-0.45, 2.81), (-0.58, 2.74)], r=0.045)
brow_flat = brow(head, HEAD_C[1], [(0.14, 2.74), (0.3, 2.75), (0.46, 2.73), (0.58, 2.68)], r=0.045)
brows = [brow_up]

# sorrisetto storto sul muso rosa, con tre dentini dal lato alzato
MOUTH = dict(cx=0.06, cz=1.86, w=0.35, depth=0.085, curve=0.06, tilt=0.085)
mouth_surf = snout.offset(0.014)
mouth = mouth_surf.intersect(grin_sdf(**MOUTH, y_max=-0.7))
teeth = grin_teeth_at(mouth_surf, SN_C[1], (0.25, 0.48, 0.7), **MOUTH, length=0.06, r=0.028)
nostrils = union(*[Frame(snout, SN_C, (sx * 0.42, -1.0, 0.36), sink=0.02).place(ellipsoid((0.055, 0.03, 0.035)).rot(0, sx * 20, 0))
                   for sx in (1, -1)])
ear_in = union(*[ellipsoid((0.15, 0.1, 0.07), (sx * 0.06, -0.06, 0)).rot(0, -sx * 18, 0).translate(c) for sx, c in zip((1, -1), EAR)])

m.add("Head", union(head_all, *lids_white, brow_flat), COW, role="skin", tris=3000, voxel=0.016)
m.add("Black", union(handle, hooves, knob, *spots, *lids_black), BLACK, role="detail", tris=2300, voxel=0.016)
m.add("Pink", union(snout, head_all.offset(0.018).intersect(ear_in), fast_union(spot_stitches)), PINK,
      role="detail", tris=1700, voxel=0.012)
m.add("Horns", horns, HORN, role="detail", tris=500, voxel=0.014)
m.add("Eyes", union(*eyes, *lashes, *brows, mouth, nostrils), EYE, role="eye", tris=1100, voxel=0.011)
m.add("Shine", union(*shines, *teeth), WHITE, role="shine", tris=400, voxel=0.009)

# ------------------------------------------------------------------ sbuffi di vapore dal beccuccio
puffs = []
for c, r in (((1.06, 0.0, 1.63), 0.1), ((1.15, -0.03, 1.83), 0.14), ((1.07, 0.02, 2.1), 0.18), ((1.2, 0.0, 2.44), 0.22)):
    c = np.array(c)
    puffs.append(sphere(r, c))
    puffs.append(sphere(r * 0.7, c + np.array([r * 0.8, 0.0, -r * 0.25])))
    puffs.append(sphere(r * 0.65, c + np.array([-r * 0.75, -r * 0.2, -r * 0.2])))
m.add("Steam", union(*puffs, k=0.06), WHITE, role="detail", tris=1200, voxel=0.016)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
