"""Fontinello Volantello (FontinelloVolantello) - pet Mitico, volante: spicchio di Fontina con ali d'angelo.

Carattere: dispettoso (occhi diversi, ghigno storto con dentini e linguaccia).
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, capsule, ellipsoid, round_cone, smax, smin, sphere, stick, torus,  # noqa: E402
                     tube, union, project)
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
CHEESE = (255, 210, 92)
RIND = (190, 96, 30)
BROWN = (92, 42, 18)
WING = (255, 250, 240)
HALO = (255, 196, 40)
EYE = (34, 16, 20)
WHITE = (255, 255, 255)
TONGUE = (255, 96, 128)

m = Model("FontinelloVolantello", "pet")

# ------------------------------------------------------------------ spicchio di formaggio in piedi (punta in alto)
AX, AZ = 0.0, 2.5  # vertice (centro della forma intera)
R, HALF, T, K = 1.85, math.radians(31), 1.0, 0.3
N1 = (math.cos(HALF), math.sin(HALF))
N2 = (-math.cos(HALF), math.sin(HALF))


def wedge_f(p):
    x, z = p[:, 0] - AX, p[:, 2] - AZ
    d = smax(np.sqrt(x * x + z * z) - R, x * N1[0] + z * N1[1], K)
    d = smax(d, x * N2[0] + z * N2[1], K)
    return smax(d, np.abs(p[:, 1]) - T / 2, K)


wedge = SDF(wedge_f, (-R * 0.6, -T / 2, AZ - R), (R * 0.6, T / 2, AZ + 0.05))

# buchi rotondi sulle superfici (non sulla faccia, ne' sulla crosta)
holes = []
for x, z, r in ((-0.06, 2.06, 0.11), (0.17, 1.86, 0.065), (-0.62, 1.0, 0.09), (0.66, 0.98, 0.07)):  # davanti
    holes.append(sphere(r, (x, -T / 2 + 0.02, z)))
for x, z, r in ((0.05, 1.9, 0.15), (-0.3, 1.35, 0.12), (0.35, 1.2, 0.1), (-0.1, 0.95, 0.08), (0.1, 1.55, 0.07),
                (-0.5, 1.0, 0.07)):  # dietro
    holes.append(sphere(r, (x, T / 2 - 0.02, z)))
for sx in (1, -1):  # fianchi inclinati
    for s, yy, r in ((0.55, -0.1, 0.12), (1.0, 0.22, 0.1), (1.35, -0.2, 0.08), (0.8, 0.3, 0.06)):
        c = np.array([AX + sx * s * math.sin(HALF), yy, AZ - s * math.cos(HALF)])
        n = np.array([sx * math.cos(HALF), 0.0, math.sin(HALF)])
        holes.append(sphere(r, tuple(c + n * 0.01)))
cheese = wedge.subtract(fast_union(holes), k=0.03)
m.add("Cheese", cheese, CHEESE, tris=5200, voxel=0.02)

# crosta: fascia sull'arco in basso, con cucitura sul davanti
rind_region = SDF(lambda p: (R - 0.16) - np.sqrt((p[:, 0] - AX) ** 2 + (p[:, 2] - AZ) ** 2), (-R, -1, AZ - R - 0.1), (R, 1, AZ - R + 0.6))
m.add("Rind", cheese.offset(0.02).intersect(rind_region), RIND, role="detail", tris=1500, voxel=0.018)
arc = [(AX + (R - 0.16) * math.sin(a), 0.0, AZ - (R - 0.16) * math.cos(a)) for a in np.linspace(-HALF * 0.8, HALF * 0.8, 30)]
seam_surf = cheese.offset(0.01)
seam = stitch_row(seam_surf, curve_on(seam_surf, arc), dash=0.05, gap=0.05, r=0.017, cross=True, cross_len=0.1)

# ------------------------------------------------------------------ faccia dispettosa: occhi diversi
face = cheese  # la faccia sta sulla superficie del formaggio
fb = Frame(face, (-0.24, 0.0, 1.47), (0, -1, 0), sink=0.045)  # occhione sgranato
BA, BB, BC = 0.19, 0.1, 0.22
big_white = fb.place(ellipsoid((BA, BB, BC)))
big_pupil = fb.place(ellipsoid((0.07, 0.04, 0.085)), (-0.035, -BB * 0.9, -0.03))
big_rim = fb.place(tube([(BA * 0.88 * math.cos(t), -0.05, BC * 0.88 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 41)], 0.017))
fs = Frame(face, (0.27, 0.0, 1.43), (0, -1, 0), sink=0.04)  # occhio socchiuso
SA, SB, SC = 0.15, 0.085, 0.16
small_eye = fs.place(ellipsoid((SA, SB, SC)))
s_lid, s_lash = lid_parts(fs, SA, SB, SC, cut=-0.015, slope=-0.22)
hls = [fb.place(sphere(0.022), (-0.055, -BB * 0.9 - 0.035, 0.0)), fb.place(sphere(0.011), (-0.01, -BB * 0.9 - 0.03, -0.065)),
       fs.place(sphere(0.026), (-0.04, -0.075, -0.07))]
brows = [brow(face, 0.0, [(-0.07, 1.77), (-0.19, 1.84), (-0.29, 1.84), (-0.34, 1.79)], r=0.043),  # alzato
         brow(face, 0.0, [(0.1, 1.6), (0.22, 1.65), (0.33, 1.69), (0.4, 1.68)], r=0.043)]  # abbassato, furbo

MOUTH = dict(cx=0.02, cz=1.12, w=0.4, depth=0.15, curve=0.1, tilt=0.06)
mouth_surf = cheese.offset(0.016)
mouth = mouth_surf.intersect(grin_sdf(**MOUTH, y_max=-0.3))
teeth = grin_teeth(mouth_surf, 0.0, **MOUTH, n=9, length=0.07, r=0.028)
# linguaccia che esce da un angolo della bocca
tongue_c = curve_on(mouth_surf, [(0.2, 0.0, 1.05)])[0]
tongue = union(ellipsoid((0.085, 0.06, 0.1), tuple(tongue_c + np.array([0.0, -0.01, -0.03]))),
               ellipsoid((0.06, 0.05, 0.06), tuple(tongue_c + np.array([0.0, 0.03, 0.04]))), k=0.03)

m.add("Eyes", union(big_pupil, big_rim, small_eye, s_lash, *brows, mouth), EYE, role="eye", tris=1200, voxel=0.011)
m.add("Shine", union(big_white, *hls, *teeth), WHITE, role="shine", tris=700, voxel=0.01)
m.add("Lid", s_lid, CHEESE, role="skin", tris=300, voxel=0.011)
m.add("Tongue", tongue, TONGUE, role="detail", tris=300, voxel=0.011)

# ------------------------------------------------------------------ gambette penzolanti + cuciture (marrone scuro)
legs = []
for sx in (1, -1):
    legs.append(tube([(sx * 0.3, 0.0, 0.8), (sx * 0.33, -0.02, 0.45), (sx * 0.36, -0.04, 0.16)], [0.075, 0.07, 0.07]))
    legs.append(union(ellipsoid((0.13, 0.2, 0.1), (sx * 0.37, -0.1, 0.1)), sphere(0.08, (sx * 0.36, -0.04, 0.17)), k=0.05))
m.add("Brown", union(*legs, fast_union(seam)), BROWN, role="detail", tris=1200, voxel=0.013)

# ------------------------------------------------------------------ ali d'angelo (animabili) e aureola
# ala vera: osso curvo in alto, copritrici, penne parallele che si allungano verso la punta
from lib.sdf import bezier  # noqa: E402
arm_pts = bezier((0.0, 0, 0.0), (0.25, 0, 0.24), (0.5, 0, 0.38), (0.74, 0, 0.44), 10)
wing_parts = [tube(arm_pts, [0.115 - 0.0055 * i for i in range(11)]),
              ellipsoid((0.36, 0.13, 0.15)).rot(0, -28, 0).translate((0.34, 0, 0.17))]
for t in (0.1, 0.28, 0.46, 0.64, 0.82, 1.0):
    anchor = np.array(arm_pts[int(round(t * 10))])
    ang = math.radians(8 + 44 * t)  # da verso il basso a verso l'esterno
    L = 0.26 + 0.34 * t
    tip = anchor + np.array([math.sin(ang), 0.0, -math.cos(ang)]) * L
    wing_parts.append(round_cone(tuple(anchor), tuple(tip), 0.1, 0.082))
    # fila di copritrici piu' corte, appena davanti
    tip2 = anchor + np.array([math.sin(ang - 0.15), -0.06, -math.cos(ang - 0.15)]) * L * 0.55
    wing_parts.append(round_cone(tuple(anchor + np.array([0, -0.06, 0])), tuple(tip2), 0.095, 0.08))
wing_local = flatten(union(*wing_parts, k=0.04), 0.42).scale(1.12)
ATTACH = (0.38, 0.36, 1.72)
for sx, nm in ((1, "WingR"), (-1, "WingL")):
    w = wing_local.rot(0, -18, 0).rot(0, 0, 24).translate(ATTACH)
    m.add(nm, w if sx > 0 else w.mirrored(), WING, role="detail", tris=1000, voxel=0.014, group=nm,
          pivot=(sx * ATTACH[0], ATTACH[1], ATTACH[2]))
halo = torus(0.3, 0.05).rot(14, 0, 0).translate((0.0, 0.06, 2.76))
m.add("Halo", halo, HALO, material="Neon", role="glow", tris=600, voxel=0.012)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
