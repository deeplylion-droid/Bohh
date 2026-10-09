"""Arancino Astronauta - pet Segreto (creatura meme originale).

Un arancino siciliano giocattolo (a pera, dorato, con la panatura a briciole) vestito da astronauta:
casco di vetro trasparente con bordo bianco, zaino bianco con antennina dalla punta luminosa,
guantoni bianchi, stivali bianchi e una toppa tricolore cucita sul fianco.
Carattere: lo sfacciato - un occhio a bottone cucito con la X, un sopracciglio alzato, pollice in
su e un ghigno storto pieno di dentini.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, box, capsule, cylinder, ellipsoid, project, revolve, round_cone,  # noqa: E402
                     sphere, torus, tube, union)
from lib.toy import Model  # noqa: E402

RICE = (236, 136, 26)
CRUMB = (178, 82, 18)
GLASS = (170, 222, 255)
WHITE_SUIT = (246, 248, 252)
GREY = (120, 128, 146)
TIP = (255, 50, 60)
EYE = (24, 16, 26)
BUTTON = (40, 34, 86)
SHINE = (255, 255, 255)
MOUTH = (52, 12, 22)
TOOTH = (255, 252, 242)
BLUSH = (255, 92, 104)
FLAG_G = (20, 150, 70)
FLAG_R = (214, 30, 44)

m = Model("ArancinoAstronauta", "pet")


# ---------------------------------------------------------------- helper locali
def stencil(fn2d, xr, zr, depth=0.35):
    """Estrude una forma 2D fn2d(x, z) lungo l'asse locale Y (decalcomania da Frame.place)."""
    def f(p):
        return np.maximum(fn2d(p[:, 0], p[:, 2]), np.abs(p[:, 1]) - depth)
    return SDF(f, (xr[0], -depth, zr[0]), (xr[1], depth, zr[1]))


def normal_at(base, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float32)
    g = np.array([base((p + e)[None, :])[0] - base((p - e)[None, :])[0]
                  for e in np.eye(3, dtype=np.float32) * eps])
    return g / max(np.linalg.norm(g), 1e-9)


def on_surf(base, src, q):
    src = np.asarray(src, dtype=np.float64)
    return project(base, src, np.asarray(q, dtype=np.float64) - src)


def spheres(centers, radii):
    C = np.asarray(centers, dtype=np.float32)
    R = np.broadcast_to(np.asarray(radii, dtype=np.float32), (len(C),)).copy()
    tree = cKDTree(C)
    k = min(4, len(C))

    def f(p):
        d, i = tree.query(p, k=k)
        return np.min(d - R[i], axis=1).astype(np.float32)
    return SDF(f, C.min(0) - R.max(), C.max(0) + R.max())


def smooth_union(a, b, k):
    from lib.sdf import smin
    return SDF(lambda p: smin(a(p), b(p), k), np.minimum(a.lo, b.lo) - k, np.maximum(a.hi, b.hi) + k)


def grin_edges(u, a, h, curve, skew):
    t = np.clip(u / a, -1.0, 1.0)
    top = curve * t * t + skew * t
    bot = top - h * np.power(np.clip(1.0 - t * t, 0.0, 1.0), 0.7)
    return top, bot


def stitches(base, pts, n, dash, r, across=True, lift=0.006, closed=False):
    pts = np.asarray(pts, dtype=np.float64)
    if closed:
        pts = np.vstack([pts, pts[:1]])
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for t in np.linspace(0.0, s[-1], n, endpoint=not closed):
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


# ---------------------------------------------------------------- arancino a pera con la punta
Z0, Z1 = 0.32, 2.6


def prof(z):
    t = np.clip((z - Z0) / (Z1 - Z0), 0.0, 1.0)
    return 1.9 * np.power(t, 0.45) * np.power(1.0 - t, 0.75)


rice = revolve(prof, 0.9, Z0, Z1)
legs = union(*[capsule((sx * 0.3, -0.04, 0.5), (sx * 0.34, -0.1, 0.2), 0.13) for sx in (1, -1)])
HAND_R = (1.0, -0.42, 1.12)   # pollice in su
HAND_L = (-1.0, -0.3, 1.45)   # saluto
arms = union(capsule((0.66, -0.2, 1.08), HAND_R, 0.1), capsule((-0.66, -0.15, 1.12), HAND_L, 0.1), k=0.04)
FC = (0.0, 0.0, 1.9)
face_zone = ellipsoid((0.5, 0.6, 0.42), (0.0, -0.62, 1.86))
FLAG_SRC = (0.0, 0.0, 0.95)
FLAG_F = Frame(rice, FLAG_SRC, (1.0, -0.42, -0.1))
flag_zone = sphere(0.26, FLAG_F.origin)

# panatura: tante briciole tonde fuse nella superficie (niente briciole sul viso e sulla toppa)
rng = np.random.default_rng(17)
bumps = []
for _ in range(900):
    v = rng.normal(size=3)
    v /= np.linalg.norm(v)
    src = (0.0, 0.0, 1.0 + 0.6 * v[2])
    p, n = project(rice, src, v)
    pp = p[None, :].astype(np.float32)
    if face_zone(pp)[0] < 0.0 or flag_zone(pp)[0] < 0.0 or p[2] < Z0 + 0.06:
        continue
    bumps.append(p + n * 0.006)
    if len(bumps) >= 420:
        break
bumpy = smooth_union(rice, spheres(bumps, 0.047), 0.04)
body = union(bumpy, legs, k=0.06)
body = union(body, arms, k=0.05)
m.add("Body", body, RICE, tris=5000, voxel=0.02)

# briciole piu' scure sparse
crumbs = []
for _ in range(400):
    v = rng.normal(size=3)
    v /= np.linalg.norm(v)
    p, n = project(rice, (0.0, 0.0, 1.0 + 0.6 * v[2]), v)
    pp = p[None, :].astype(np.float32)
    if face_zone(pp)[0] < 0.05 or flag_zone(pp)[0] < 0.05 or p[2] < Z0 + 0.08:
        continue
    crumbs.append(ellipsoid(tuple(rng.uniform(0.03, 0.05, 3)), p + n * 0.035))
    if len(crumbs) >= 55:
        break
m.add("Crumbs", union(*crumbs), CRUMB, role="detail", tris=700, voxel=0.012)

# ---------------------------------------------------------------- casco di vetro con bordo bianco
DOME_C, DOME_R, RIM_Z = (0.0, 0.0, 2.0), 1.0, 1.45
# casco = calotta di vetro piena che racchiude la testa: davanti alla faccia c'e' una sola superficie di vetro
# (un guscio avrebbe due superfici e la faccia si vedrebbe velata; un guscio sottile verrebbe anche bucato
# dal rimeshing grossolano del toolkit)
dome = sphere(DOME_R, DOME_C).intersect(SDF(lambda p: (RIM_Z - 0.02) - p[:, 2], (-1.1, -1.1, RIM_Z - 0.05), (1.1, 1.1, 3.1)))
m.add("Helmet", dome, GLASS, material="Glass", role="detail", tris=2000, voxel=0.02, transparency=0.55)

rim = torus(float(prof(np.array([RIM_Z]))[0]) + 0.02, 0.09, (0.0, 0.0, RIM_Z))

# ---------------------------------------------------------------- zaino, guantoni, stivali (bianchi)
pack = box((0.44, 0.2, 0.5), (0.0, 0.96, 1.05), round=0.12)
pack = union(pack, cylinder((0.0, 0.94, 1.42), (0.0, 0.94, 1.6), 0.12, round=0.04), k=0.04)


def glove_fist(c, thumb_dir, side):
    c = np.asarray(c, dtype=np.float64)
    parts = [ellipsoid((0.13, 0.12, 0.13), c)]
    for dz in (-0.07, 0.0, 0.07):
        parts.append(capsule(c + np.array([side * 0.02, -0.1, dz]), c + np.array([side * 0.11, -0.04, dz]), 0.055))
    parts.append(capsule(c + np.array([0.0, -0.04, 0.08]), c + np.asarray(thumb_dir) * 0.22, 0.055))
    return union(*parts, k=0.03)


def glove_open(c, side):
    c = np.asarray(c, dtype=np.float64)
    parts = [ellipsoid((0.12, 0.08, 0.14), c)]
    for k, ang in enumerate((-22, 0, 22)):
        a = math.radians(ang)
        d = np.array([side * math.sin(a) * 0.6, -0.08, math.cos(a)])
        d /= np.linalg.norm(d)
        parts.append(capsule(c + d * 0.08, c + d * 0.24, 0.05))
    parts.append(capsule(c + np.array([side * 0.06, -0.04, 0.0]), c + np.array([side * 0.2, -0.06, 0.06]), 0.05))
    return union(*parts, k=0.03)


gloves = union(glove_fist(HAND_R, (0.05, -0.1, 1.0), 1),
               glove_open(HAND_L, -1),
               torus(0.115, 0.04).rot(0, 90, 0).translate((0.88, -0.38, 1.12)),
               torus(0.115, 0.04).rot(0, 90, 0).translate((-0.89, -0.27, 1.38)))
boots = union(*[union(ellipsoid((0.21, 0.29, 0.17), (sx * 0.35, -0.16, 0.16)),
                      cylinder((sx * 0.34, -0.08, 0.2), (sx * 0.34, -0.08, 0.36), 0.155, round=0.05), k=0.05) for sx in (1, -1)])

# ---------------------------------------------------------------- faccia sfacciata: occhio vero + occhio a bottone
eye_f = Frame(body, FC, (-0.42, -1.0, 0.12), sink=0.04)   # occhio vero (a sinistra nell'immagine)
btn_f = Frame(body, FC, (0.42, -1.0, 0.12), sink=0.0)     # bottone cucito (a destra nell'immagine)
m.add("Eye", eye_f.place(ellipsoid((0.15, 0.09, 0.18))), EYE, role="eye", tris=300, voxel=0.01)
m.add("Shine", union(eye_f.place(sphere(0.04), (-0.045, -0.07, 0.06)), eye_f.place(sphere(0.02), (0.05, -0.065, -0.07))),
      SHINE, role="shine", tris=150, voxel=0.007)
BR = 0.15
button = cylinder((0, -0.03, 0), (0, 0.04, 0), BR, round=0.02)
button = union(button, torus(BR - 0.02, 0.022).rot(90, 0, 0).translate((0, -0.028, 0)), k=0.01)
holes = union(*[cylinder((hx, -0.08, hz), (hx, 0.08, hz), 0.022) for hx in (-0.04, 0.04) for hz in (-0.04, 0.04)])
button = button.subtract(holes)
x_thread = union(capsule((-0.07, -0.05, -0.07), (0.07, -0.05, 0.07), 0.024),
                 capsule((-0.07, -0.05, 0.07), (0.07, -0.05, -0.07), 0.024))

brows = []
for f, pts2d in ((eye_f, ((0.16, 0.23), (0.06, 0.3), (-0.05, 0.32), (-0.16, 0.28))),       # alzato
                 (btn_f, ((-0.17, 0.23), (-0.06, 0.24), (0.05, 0.23), (0.16, 0.19)))):       # quasi piatto
    pts = [on_surf(body, FC, f.point((x, 0.0, z)))[0] for x, z in pts2d]
    brows.append(tube([p + normal_at(body, p) * 0.01 for p in pts], [0.036, 0.048, 0.048, 0.036]))

# ghigno storto pieno di dentini
mouth_f = Frame(body, FC, (0.0, -1.0, -0.3))
GA, GH, GC, GS = 0.3, 0.17, 0.12, 0.07


def mouth_fn(x, z):
    top, bot = grin_edges(-x, GA, GH, GC, GS)
    return np.maximum(np.maximum(z - top, bot - z), np.abs(x) - GA) * 0.8


m.add("Mouth", body.offset(0.014).intersect(mouth_f.place(stencil(mouth_fn, (-0.36, 0.36), (-0.3, 0.26), 0.4))),
      MOUTH, role="detail", tris=400, voxel=0.009)
teeth = []
for n_row, span, sign, frac, L in ((8, 0.84, 1.0, 0.55, 0.07), (6, 0.7, -1.0, 0.42, 0.055)):
    for i in range(n_row):
        u = GA * span * (-1.0 + 2.0 * (i + 0.5) / n_row)
        top, bot = grin_edges(u, GA, GH, GC, GS)
        li = min(L, (top - bot) * frac)
        if li < 0.025:
            continue
        z0 = top - 0.003 if sign > 0 else bot + 0.003
        pa, na = on_surf(body, FC, mouth_f.point((-u, 0.0, z0)))
        pb, nb = on_surf(body, FC, mouth_f.point((-u, 0.0, z0 - sign * li)))
        teeth.append(round_cone(pa + na * 0.015, pb + nb * 0.015, 0.022, 0.005))
m.add("Teeth", union(*teeth), TOOTH, role="detail", tris=500, voxel=0.008)
m.add("Blush", union(*[Frame(body, FC, (0.62 * sx, -1.0, -0.12), sink=0.015).place(ellipsoid((0.1, 0.035, 0.065)))
                       for sx in (1, -1)]), BLUSH, role="detail", tris=250, voxel=0.011)

# ---------------------------------------------------------------- toppa tricolore cucita sul fianco
FW, FH = 0.2, 0.15


def stripe(x0, x1):
    def fn(x, z):
        return np.maximum(np.maximum(x0 - x, x - x1), np.abs(z) - FH)
    return body.offset(0.024).intersect(FLAG_F.place(stencil(fn, (x0 - 0.01, x1 + 0.01), (-FH - 0.01, FH + 0.01), 0.3)))


third = 2 * FW / 3
m.add("FlagGreen", stripe(FW - third, FW), FLAG_G, role="detail", tris=250, voxel=0.01)
m.add("FlagRed", stripe(-FW, -FW + third), FLAG_R, role="detail", tris=250, voxel=0.01)
flag_white = stripe(-FW + third, FW - third)
m.add("White", union(rim, pack, gloves, boots, btn_f.place(x_thread), flag_white), WHITE_SUIT, role="detail",
      tris=2800, voxel=0.014)

# ---------------------------------------------------------------- suole, antennina e punta luminosa
soles = union(*[ellipsoid((0.22, 0.3, 0.06), (sx * 0.35, -0.17, 0.05)) for sx in (1, -1)])
ANT_A, ANT_B = (0.24, 1.0, 1.5), (0.34, 1.08, 2.32)
antenna = union(capsule(ANT_A, ANT_B, 0.024), cylinder((0.24, 1.0, 1.44), (0.24, 1.0, 1.56), 0.06, round=0.02), k=0.02)
border = []
for i in range(24):
    t = 2 * math.pi * i / 24
    x, z = (FW + 0.02) * math.cos(t), (FH + 0.02) * math.sin(t)
    sq = max(abs(math.cos(t)), abs(math.sin(t)))
    border.append(on_surf(body, FLAG_SRC, FLAG_F.point((x / sq ** 0.7, 0.0, z / sq ** 0.7)))[0])
m.add("Grey", union(soles, antenna), GREY, material="Metal", role="detail", tris=500, voxel=0.01)
# filo blu notte: bottone-occhio, sopracciglia e cuciture della toppa
m.add("Button", union(btn_f.place(button), *brows,
                      stitches(body, border, 12, 0.05, 0.015, across=False, lift=0.028, closed=True)),
      BUTTON, role="detail", tris=800, voxel=0.009)
m.add("AntennaTip", sphere(0.07, (ANT_B[0] + 0.01, ANT_B[1] + 0.01, ANT_B[2] + 0.05)), TIP, material="Neon",
      role="glow", tris=200, voxel=0.01)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
