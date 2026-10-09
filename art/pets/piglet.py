"""Maialino (Piglet) - pet Comune. Carattere: sbruffone (toppa cucita sull'occhio, sopracciglio alzato, ghigno)."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, box, capsule, cylinder, ellipsoid, prism, project, sphere,  # noqa: E402
                     tube, union)
from lib.toy import Model  # noqa: E402

PINK = (255, 128, 166)
PINK_LIGHT = (255, 170, 196)
SNOUT = (236, 82, 130)
NOSTRIL = (92, 18, 52)
HOOF = (112, 34, 66)
MUD = (98, 62, 40)
PATCH = (34, 30, 64)
GOLD = (240, 186, 64)
DARK = (96, 20, 58)
EYE = (26, 14, 30)
WHITE = (255, 255, 255)

m = Model("Piglet", "pet")


# ------------------------------------------------------------------ aiuti
def paint(base, region, t=0.02, depth=0.05):
    """Vernice sottile che segue la superficie (solo uno strato vicino alla pelle)."""
    return base.offset(t).intersect(region).subtract(base.offset(-depth))


def above_line(z0, slope, size=1.0):
    """Semispazio z > z0 + slope * x (coordinate locali): taglio delle palpebre."""
    n = math.sqrt(1 + slope * slope)
    return SDF(lambda p: (slope * p[:, 0] - p[:, 2] + z0) / n, (-size,) * 3, (size,) * 3)


def fast_union(shapes, pad=0.04):
    """Unione semplice di molte forme piccole: ognuna e' valutata solo vicino al suo ingombro."""
    los = [s.lo - pad for s in shapes]
    his = [s.hi + pad for s in shapes]

    def f(p):
        d = np.ones(len(p), dtype=np.float32)
        for s, lo, hi in zip(shapes, los, his):
            msk = np.all((p >= lo) & (p <= hi), axis=1)
            if msk.any():
                d[msk] = np.minimum(d[msk], s(p[msk]))
        return d

    return SDF(f, np.min(los, axis=0), np.max(his, axis=0))


def resample(path, step):
    pts = np.array([p for p, _ in path])
    nrm = np.array([n for _, n in path])
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for t in np.arange(0.0, s[-1] + 1e-9, step):
        i = min(int(np.searchsorted(s, t, side="right")) - 1, len(seg) - 1)
        f = (t - s[i]) / max(seg[i], 1e-9)
        n = nrm[i] + (nrm[i + 1] - nrm[i]) * f
        out.append((pts[i] + (pts[i + 1] - pts[i]) * f, n / np.linalg.norm(n)))
    return out


def stitches(path, every=0.07, half=0.035, r=0.012, inset=0.0):
    """Punti di cucitura corti, perpendicolari al percorso (punto, normale)."""
    pts = resample(path, every)
    out = []
    for i, (p, n) in enumerate(pts):
        t = pts[min(i + 1, len(pts) - 1)][0] - pts[max(i - 1, 0)][0]
        side = np.cross(n, t / np.linalg.norm(t))
        c = p - n * inset
        out.append(capsule(c - side * half, c + side * half, r))
    return out


def ring_path(base, center, normal, rx, rz, n=32):
    """Anello (ellisse rx, rz attorno a center, nel piano perpendicolare a normal) proiettato sulla superficie."""
    normal = np.asarray(normal, dtype=float) / np.linalg.norm(normal)
    u = np.cross(normal, (0, 0, 1.0))
    u /= np.linalg.norm(u)
    v = np.cross(u, normal)
    out = []
    for a in np.linspace(0, 2 * math.pi, n + 1):
        q = np.asarray(center) + u * rx * math.cos(a) + v * rz * math.sin(a) - normal * 0.4
        out.append(project(base, q, normal))
    return out


# ------------------------------------------------------------------ corpo tondo + testone
HEAD_C = (0, -0.1, 1.84)
body = ellipsoid((0.9, 0.88, 0.76), (0, 0.1, 0.96))
head = ellipsoid((0.88, 0.8, 0.76), HEAD_C)
core = union(body, head, k=0.35)
LEGS = ((0.44, -0.42), (-0.44, -0.42), (0.46, 0.52), (-0.46, 0.52))
legs = union(*[cylinder((x, y, 0.2), (x, y, 0.5), 0.17, round=0.07) for x, y in LEGS])
core = union(core, legs, k=0.1)
m.add("Body", core, PINK, tris=4600)

m.add("Belly", paint(core, ellipsoid((0.5, 0.5, 0.42), (0, -0.66, 0.72)).subtract(legs.offset(0.06))), PINK_LIGHT,
      role="detail", tris=800)

hooves = []
for x, y in LEGS:
    h = cylinder((x, y, 0.05), (x, y, 0.1), 0.18, round=0.05)
    hooves.append(h.subtract(box((0.014, 0.1, 0.12), (x, y - 0.18, 0.06)), k=0.01))
m.add("Hooves", union(*hooves), HOOF, role="detail", tris=800, voxel=0.015)

# ------------------------------------------------------------------ grugno cucito sul muso
SN_C = np.array((0.0, -0.84, 1.6))


def oval_x(shape, sx):
    """Allarga una forma lungo x (deformazione dello spazio, distanza approssimata)."""
    return shape.warp(lambda p: p * np.array([1.0 / sx, 1.0, 1.0], dtype=np.float32), pad=0.1)


disc = cylinder((0, 0.0, 0), (0, -0.14, 0), 0.25, round=0.08)
disc = oval_x(disc, 1.18).rot(-8, 0, 0).translate(SN_C)
nostril_holes = union(*[ellipsoid((0.05, 0.08, 0.075), (sx * 0.1, -0.22, 0.0)) for sx in (1, -1)])
m.add("Snout", disc.subtract(nostril_holes.rot(-8, 0, 0).translate(SN_C), k=0.025), SNOUT, role="detail", tris=1000,
      voxel=0.015)
nostrils = union(*[ellipsoid((0.045, 0.03, 0.068), (sx * 0.1, -0.165, 0.0)) for sx in (1, -1)])
m.add("Nostrils", nostrils.rot(-8, 0, 0).translate(SN_C), NOSTRIL, role="detail", tris=300, voxel=0.01)
snout_stitch = stitches(ring_path(core, SN_C + (0, 0.25, 0), (0, -1, 0), 0.34, 0.3), every=0.085, half=0.036,
                        r=0.013, inset=-0.004)

# ------------------------------------------------------------------ orecchie triangolari ripiegate (animabili)
def tri_plate(poly, t=0.045, r=0.035):
    """Lastra con contorno poligonale nel piano XZ (spessore lungo Y)."""
    return prism(poly, -t, t, round=r).rot(90, 0, 0)


ear_base = tri_plate([(-0.3, 0.0), (0.3, 0.0), (0.16, 0.36), (-0.16, 0.36)], t=0.05)
ear_tip = tri_plate([(-0.18, 0.33), (0.18, 0.33), (0.0, 0.62)], t=0.05).rot(115, 0, 0, pivot=(0, 0, 0.35))
ear_local = union(ear_base, ear_tip, k=0.04)


def place_ear(shape, sx):
    s = shape.rot(0, 0, 12).rot(0, 28, 0).translate((0.42, -0.08, 2.36))
    return s if sx > 0 else s.mirrored()


for sx, nm in ((1, "EarR"), (-1, "EarL")):
    m.add(nm, place_ear(ear_local, sx), PINK, role="skin", tris=800, voxel=0.015, group=nm,
          pivot=(sx * 0.42, -0.08, 2.4))

# ------------------------------------------------------------------ codina a cavatappi (tubo lungo un'elica)
helix = [(0.0, -0.25, 0.0)]
for i in range(56):
    a = i / 55 * 2.0 * 2 * math.pi
    rr = 0.15 * (1 - 0.3 * i / 55)
    helix.append((rr * math.sin(a), 0.04 + 0.13 * a / (2 * math.pi), rr * (1 - math.cos(a))))
radii = [0.06] + [0.056 - 0.018 * i / 55 for i in range(56)]
m.add("Tail", tube(helix, radii).rot(40, 0, 0).translate((0, 0.98, 1.0)), PINK, role="skin", tris=1100, voxel=0.015)

# ------------------------------------------------------------------ schizzo di fango sul fianco
p0, n0 = project(core, (0, 0.1, 0.95), (1.0, -0.12, -0.12))
t1 = np.cross(n0, (0, 0, 1))
t1 /= np.linalg.norm(t1)
t2 = np.cross(t1, n0)
mud_spots = [sphere(r, p0 + t1 * u + t2 * v) for u, v, r in
             ((0, 0, 0.2), (0.16, 0.08, 0.12), (-0.15, 0.1, 0.12), (0.05, -0.17, 0.12), (-0.1, -0.13, 0.1),
              (0.2, -0.1, 0.09), (0.36, 0.12, 0.055), (-0.34, 0.16, 0.05), (0.12, -0.34, 0.05), (0.3, -0.3, 0.035))]
m.add("Mud", paint(core, union(*mud_spots[:6], k=0.06).union(*mud_spots[6:])), MUD, role="detail", tris=700,
      voxel=0.015)

# ------------------------------------------------------------------ toppa di stoffa cucita sopra l'occhio (x > 0)
patch_f = Frame(head, HEAD_C, (0.4, -1.0, 0.3))
patch_region = ellipsoid((0.21, 0.4, 0.19), patch_f.surface)
m.add("EyePatch", paint(core, patch_region, t=0.045, depth=0.04), PATCH, material="Fabric", role="detail", tris=700,
      voxel=0.013)
rim = ring_path(core.offset(0.045), patch_f.surface - patch_f.normal * 0.3, patch_f.normal, 0.17, 0.15, n=28)
thread = fast_union(stitches(rim, every=0.06, half=0.026, r=0.011, inset=0.004) + snout_stitch)
m.add("Thread", thread, GOLD, role="detail", tris=1500, voxel=0.01)

# ------------------------------------------------------------------ occhio sinistro sornione, sopracciglio alzato
EYE_R = (0.15, 0.09, 0.19)
eye_f = Frame(head, HEAD_C, (-0.4, -1.0, 0.3), sink=0.05)
m.add("Eyes", eye_f.place(ellipsoid(EYE_R)), EYE, role="eye", tris=500, voxel=0.012)
lid = ellipsoid((EYE_R[0] + 0.022, EYE_R[1] + 0.03, EYE_R[2] + 0.022)).intersect(above_line(0.04, 0.1), k=0.012)
m.add("Lids", eye_f.place(lid), PINK, role="skin", tris=400, voxel=0.012)
shines = union(eye_f.place(sphere(0.042), (-0.05, -0.082, -0.0)), eye_f.place(sphere(0.022), (0.055, -0.075, -0.1)))
m.add("Shine", shines, WHITE, role="shine", tris=250, voxel=0.009)

brow_pts = bezier((-0.13, 0, 2.31), (-0.24, 0, 2.47), (-0.42, 0, 2.47), (-0.54, 0, 2.31), 10)
brow = tube([p - n * 0.008 for p, n in [project(head, (q[0], -0.1, q[2]), (0, -1, 0)) for q in brow_pts]],
            list(np.linspace(0.052, 0.034, 11)))
smirk_pts = bezier((-0.27, 0, 1.2), (-0.08, 0, 1.09), (0.18, 0, 1.11), (0.34, 0, 1.3), 14)
smirk = tube([p - n * 0.006 for p, n in [project(core, (q[0], -0.4, q[2]), (0, -1, 0)) for q in smirk_pts]], 0.028)
dimple = tube([p - n * 0.006 for p, n in [project(core, (q[0], -0.4, q[2]), (0, -1, 0))
                                          for q in ((0.31, 0, 1.37), (0.38, 0, 1.28))]], 0.022)
m.add("Brow", union(brow, smirk, dimple), DARK, role="detail", tris=1000, voxel=0.013)

# zampe piu' corte: abbassa tutto tranne gli zoccoli (le zampe affondano nel corpo); poi scala a ~3 unita'
DROP, S = 0.1, 1.1
for _p in m.parts:
    if _p.name != "Hooves":
        _p.sdf = _p.sdf.translate((0, 0, -DROP))
        if _p.pivot:
            _p.pivot = (_p.pivot[0], _p.pivot[1], _p.pivot[2] - DROP)
    _p.sdf = _p.sdf.scale(S)
    if _p.pivot:
        _p.pivot = tuple(c * S for c in _p.pivot)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
