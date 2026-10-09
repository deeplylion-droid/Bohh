"""Yeti - pet Leggendario. Carattere: abbraccione esaltato (braccia lunghe, occhi sgranati, ghigno enorme)."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, box, capsule, ellipsoid, halfspace_z, project, round_cone, smin,  # noqa: E402
                     sphere, stick, tube, union)
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


# ============================================================ colori
FUR = (230, 240, 255)
SKIN = (74, 146, 236)
HORN = (84, 66, 132)
DARK = (24, 16, 56)
WHITE = (255, 255, 255)
TONGUE = (255, 92, 132)
PATCH = (134, 74, 206)
THREAD = (30, 26, 84)

m = Model("Yeti", "pet")

# ------------------------------------------------------------------ corpo base: spalle alte e curve, braccia lunghe
HEAD_C = (0, -0.14, 1.95)
BODY_C = (0, 0.06, 1.0)
head = ellipsoid((0.94, 0.84, 0.8), HEAD_C)
body = ellipsoid((1.0, 0.88, 0.88), BODY_C)
face_bulge = ellipsoid((0.62, 0.3, 0.5), (0, -0.72, 1.84))
LEG = [(sx * 0.44, -0.02) for sx in (1, -1)]
legs = union(*[capsule((x, y, 0.62), (x, y - 0.06, 0.24), 0.3) for x, y in LEG])
SHOULDER = [(sx * 0.84, 0.02, 1.7) for sx in (1, -1)]
WRIST = [(sx * 1.24, -0.18, 0.66) for sx in (1, -1)]
arms = union(*[round_cone(s, w, 0.29, 0.22) for s, w in zip(SHOULDER, WRIST)])
core = union(head, body, k=0.5)
core = union(core, face_bulge, k=0.2)
core = union(core, legs, k=0.15)
core = union(core, arms, k=0.2)

# ------------------------------------------------------------------ pelo: file ordinate di ciuffi a goccia
FACE_C, FACE_R = np.array([0, -0.9, 1.84]), (0.68, 0.6)
PATCH_C, PATCH_R, PATCH_ROT = (0.08, 0.86), (0.27, 0.25), 9.0


def in_face(p, grow=0.0):
    return ((p[0] / (FACE_R[0] + grow)) ** 2 + ((p[2] - FACE_C[2]) / (FACE_R[1] + grow)) ** 2 < 1.0) and p[1] < -0.3


def in_patch(p, grow=0.0):
    a = math.radians(PATCH_ROT)
    x, z = p[0] - PATCH_C[0], p[2] - PATCH_C[1]
    u, v = x * math.cos(a) + z * math.sin(a), -x * math.sin(a) + z * math.cos(a)
    return abs(u) < PATCH_R[0] + grow and abs(v) < PATCH_R[1] + grow and p[1] < -0.3


def clump_at(p, n, size):
    n = n / np.linalg.norm(n)
    down = np.array([0, 0, -1.0]) - n * (-n[2])
    if np.linalg.norm(down) < 0.2:
        down = np.array([0, 1.0, 0]) - n * n[1]
    down /= np.linalg.norm(down)
    a = p - n * (0.03 * size) - down * 0.08 * size
    b = p + down * 0.25 * size
    return round_cone(a, b, 0.17 * size, 0.06 * size)


def ring_dirs(el_deg, count, phase):
    el = math.radians(el_deg)
    return [np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
            for az in (2 * math.pi * (i + phase) / count for i in range(count))]


clumps = []
rows = [(HEAD_C, 78, 5), (HEAD_C, 58, 11), (HEAD_C, 38, 15), (HEAD_C, 18, 17), (HEAD_C, -2, 18), (HEAD_C, -22, 18),
        (BODY_C, 12, 19), (BODY_C, -8, 19), (BODY_C, -28, 18), (BODY_C, -48, 15)]
for r, (c, el, cnt) in enumerate(rows):
    for d in ring_dirs(el, cnt, 0.5 * (r % 2)):
        try:
            p, nrm = project(core, c, d)
        except ValueError:
            continue
        if in_face(p) or in_patch(p, 0.1) or p[2] < 0.32:
            continue
        if c is BODY_C and p[2] > 1.5:
            continue
        clumps.append(clump_at(p, nrm, 1.0))
for s, w in zip(SHOULDER, WRIST):  # maniche pelose lungo le braccia
    for t, ph in ((0.18, 0.0), (0.4, 0.5), (0.62, 0.0), (0.84, 0.5), (1.0, 0.0)):
        a = np.array(s) * (1 - t) + np.array(w) * t
        for ang in np.linspace(0, 2 * math.pi, 7)[:-1] + ph:
            d = np.array([math.cos(ang), math.sin(ang), 0.25])
            try:
                p, nrm = project(core, a, d)
            except ValueError:
                continue
            if in_face(p, 0.05):
                continue
            clumps.append(clump_at(p, nrm, 0.85))
tuft = union(*[tube(bezier((x0, -0.2, 2.6), (x0 * 1.3, -0.3, 2.9), (x0 * 1.6 + 0.08, -0.4, 3.0), (x0 * 1.7 + 0.12, -0.52, 2.92), 8),
                    [0.12, 0.11, 0.1, 0.09, 0.08, 0.06, 0.05, 0.04, 0.035]) for x0 in (-0.12, 0.0, 0.12)], k=0.04)
fur = union(fast_union(clumps, k=0.08, base=core), tuft, k=0.08)
m.add("Fur", fur, FUR, material="Fabric", tris=7000, voxel=0.022)

# ------------------------------------------------------------------ pelle blu: viso, mani enormi, piedi
face = core.offset(0.025).intersect(ellipsoid((FACE_R[0], 0.6, FACE_R[1]), tuple(FACE_C)))
m.add("Face", face, SKIN, role="detail", tris=1000, voxel=0.016)


def hand(sx):
    palm = ellipsoid((0.3, 0.2, 0.28), (0, 0, 0))
    fingers = [tube([(dx, -0.02, -0.12), (dx * 1.15, -0.08, -0.3), (dx * 1.2, -0.17, -0.38)], [0.115, 0.108, 0.098])
               for dx in (-0.16, 0.0, 0.16)]
    thumb = capsule((0.2, -0.06, 0.02), (0.34, -0.18, -0.08), 0.105)
    h = union(palm, *fingers, thumb, k=0.07).rot(0, 0, -18).translate((-1.3, -0.25, 0.52))
    return h if sx < 0 else h.mirrored()


def foot(sx):
    x = sx * 0.46
    f = union(ellipsoid((0.35, 0.46, 0.2), (x, -0.28, 0.12)),
              *[sphere(0.135, (x + dx, -0.68, 0.11)) for dx in (-0.19, 0.0, 0.19)], k=0.08)
    return f.intersect(halfspace_z(0.0, above=True))


m.add("Hands", union(hand(1), hand(-1)), SKIN, role="detail", tris=1300, voxel=0.018)
m.add("Feet", union(foot(1), foot(-1)), SKIN, role="detail", tris=900, voxel=0.018)

horns = union(*[tube(bezier((sx * 0.46, -0.06, 2.56), (sx * 0.74, -0.06, 2.74), (sx * 0.88, -0.14, 2.98), (sx * 0.76, -0.24, 3.1), 12),
                     [0.17 - 0.0095 * i for i in range(13)]) for sx in (1, -1)])
m.add("Horns", horns, HORN, role="detail", tris=600, voxel=0.016)
horn_tips = horns.offset(0.016).intersect(union(*[sphere(0.2, (sx * 0.78, -0.22, 3.08)) for sx in (1, -1)]))
m.add("HornTips", horn_tips, (120, 226, 255), material="Neon", role="glow", tris=300, voxel=0.012)

# toppa viola cucita sulla pancia
a_ = math.radians(PATCH_ROT)
patch_region = box((PATCH_R[0], 0.6, PATCH_R[1]), (0, 0, 0), round=0.06).rot(0, -PATCH_ROT, 0).translate((PATCH_C[0], -0.9, PATCH_C[1]))
m.add("Patch", core.offset(0.03).intersect(patch_region), PATCH, role="detail", tris=400, voxel=0.014)
corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
outline = []
for (u0, v0), (u1, v1) in zip(corners, corners[1:] + corners[:1]):
    for t in np.linspace(0, 1, 6)[:-1]:
        u = (u0 * (1 - t) + u1 * t) * (PATCH_R[0] - 0.02)
        v = (v0 * (1 - t) + v1 * t) * (PATCH_R[1] - 0.02)
        outline.append((PATCH_C[0] + u * math.cos(a_) - v * math.sin(a_), BODY_C[1], PATCH_C[1] + u * math.sin(a_) + v * math.cos(a_)))
seam_surf = core.offset(0.015)
seam = stitch_row(seam_surf, curve_on(seam_surf, outline), dash=0.05, gap=0.05, r=0.017, cross=True, cross_len=0.1, closed=True)

# ------------------------------------------------------------------ occhi sgranati con pupille piccole
face_surf = core.offset(0.025)
EA, EB, EC = 0.17, 0.09, 0.21
frames = [Frame(face_surf, HEAD_C, (0.36 * sx, -1.0, 0.07), sink=0.04) for sx in (1, -1)]
whites, darks, hls = [], [], []
for f, sx in zip(frames, (1, -1)):
    whites.append(f.place(ellipsoid((EA, EB, EC))))
    pr = 0.06 if sx > 0 else 0.052  # pupille leggermente diverse: sguardo un po' folle
    darks.append(f.place(ellipsoid((pr, 0.035, pr * 1.25)), (0.0, -EB * 0.9, 0.0)))
    darks.append(f.place(tube([(EA * 0.9 * math.cos(t), -0.045, EC * 0.9 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 41)], 0.017)))
    hls.append(f.place(sphere(0.018), (-0.018, -EB * 0.9 - 0.03, 0.028)))
    hls.append(f.place(sphere(0.009), (0.02, -EB * 0.9 - 0.026, -0.03)))
brows = [brow(face_surf, HEAD_C[1], [(sx * 0.12, 2.29), (sx * 0.26, 2.37), (sx * 0.42, 2.37), (sx * 0.55, 2.3)], r=0.046)
         for sx in (1, -1)]

# ------------------------------------------------------------------ ghigno enorme con due file di denti
MOUTH = dict(cx=0.0, cz=1.64, w=0.44, depth=0.22, curve=0.16, tilt=0.0)
mouth_surf = core.offset(0.042)
mouth = mouth_surf.intersect(grin_sdf(**MOUTH, y_max=-0.4))
teeth = grin_teeth(mouth_surf, HEAD_C[1], **MOUTH, n=11, length=0.085, r=0.032, lower=8)
tongue = core.offset(0.052).intersect(grin_sdf(**MOUTH, y_max=-0.4)).intersect(ellipsoid((0.2, 2.0, 0.09), (0.0, -0.9, 1.45)))
m.add("Eyes", union(*darks, mouth), DARK, role="eye", tris=1100, voxel=0.011)
m.add("Shine", union(*whites, *hls, *teeth), WHITE, role="shine", tris=1100, voxel=0.01)
m.add("Tongue", tongue, TONGUE, role="detail", tris=250, voxel=0.011)
m.add("Accents", union(*brows, fast_union(seam)), THREAD, role="detail", tris=900, voxel=0.011)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
