"""Volpacchiotto (FoxKit) - pet Non comune. Carattere: furbo (palpebre pesanti, ghigno storto con una zanna)."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, box, capsule, ellipsoid, prism, project, round_cone, sphere,  # noqa: E402
                     tube, union)
from lib.toy import Model  # noqa: E402

ORANGE = (242, 96, 22)
WHITE_FUR = (255, 246, 232)
CREAM_IN = (255, 218, 176)
DARK = (46, 30, 50)
NOSE = (28, 20, 30)
EYE = (26, 16, 30)
MOUTH = (64, 14, 40)
THREAD = (60, 34, 96)
WHITE = (255, 255, 255)

m = Model("FoxKit", "pet")


# ------------------------------------------------------------------ aiuti
def tri_plate(poly, t, r):
    """Lastra con contorno poligonale nel piano XZ (spessore 2t lungo Y)."""
    return prism(poly, -t, t, round=r).rot(90, 0, 0)


def face_prism(poly, y0, y1, r=0.0):
    """Regione: poligono nel piano XZ (coppie x, z) estruso lungo Y fra y0 e y1."""
    return prism(poly, -y1, -y0, round=r).rot(90, 0, 0)


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


def grin(xc, zc, half_w, curve, slope, thick, teeth_spec, y0, y1):
    """Bocca a mezzaluna (regione) e denti aguzzi (regione) in coordinate x, z del muso."""
    def top(x):
        u = (x - xc) / half_w
        return zc + curve * u * u + slope * u, thick * max(0.0, 1 - u * u) ** 0.7

    xs = np.linspace(xc - half_w, xc + half_w, 21)
    upper = [(x, top(x)[0]) for x in xs]
    lower = [(x, top(x)[0] - top(x)[1]) for x in xs[-2:0:-1]]  # niente vertici doppi: prism() darebbe NaN
    mouth = face_prism(upper + lower, y0, y1, r=0.003)
    teeth = []
    for x, w, frac in teeth_spec:
        z, th = top(x)
        teeth.append(face_prism([(x - w / 2, z + 0.02), (x + w / 2, z + 0.02), (x, z - frac * th)], y0, y1, r=0.003))
    return mouth, union(*teeth).intersect(mouth.offset(-0.006))


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


# ------------------------------------------------------------------ corpo seduto e testa con guance a ciuffi
HEAD_C = (0, -0.06, 1.82)
body = ellipsoid((0.72, 0.68, 0.74), (0, 0.1, 0.8))
head = ellipsoid((0.84, 0.74, 0.7), HEAD_C)
ruffs = union(*[round_cone((sx * 0.56, -0.3, 1.58), (sx * 0.82, -0.26, 1.34), 0.2, 0.06) for sx in (1, -1)])
muzzle = ellipsoid((0.28, 0.27, 0.19), (0, -0.72, 1.58))
front_legs = union(*[union(capsule((sx * 0.28, -0.4, 0.8), (sx * 0.3, -0.5, 0.2), 0.125),
                           sphere(0.145, (sx * 0.3, -0.56, 0.165)),
                           *[sphere(0.062, (sx * 0.3 + dx, -0.68, 0.085)) for dx in (-0.075, 0.0, 0.075)], k=0.05)
                     for sx in (1, -1)])
haunches = union(*[ellipsoid((0.32, 0.42, 0.34), (sx * 0.46, 0.06, 0.4)) for sx in (1, -1)])
hind_feet = union(*[ellipsoid((0.14, 0.24, 0.1), (sx * 0.58, -0.2, 0.12)) for sx in (1, -1)])

ear_local = tri_plate([(-0.28, 0.0), (0.28, 0.0), (0.0, 0.8)], 0.08, 0.06)


def place_ear(shape, sx):
    s = shape.rot(0, 0, 14).rot(0, 22, 0).rot(-8, 0, 0).translate((0.42, 0.0, 2.24))
    return s if sx > 0 else s.mirrored()


ears = union(place_ear(ear_local, 1), place_ear(ear_local, -1))
core = union(body, head, k=0.32)
core = union(core, ruffs, k=0.1)
core = union(core, muzzle, k=0.14)
core = union(core, haunches, k=0.12)
core = union(core, front_legs, k=0.08)
core = union(core, hind_feet, k=0.08)
core = union(core, ears, k=0.08)
m.add("Body", core, ORANGE, tris=5400)
painted = core.offset(0.02)


def paint(region, t=0.02, depth=0.06):
    """Vernice sottile che segue la superficie (solo uno strato vicino alla pelle: niente facce interne inutili)."""
    return core.offset(t).intersect(region).subtract(core.offset(-depth))


# ghigno storto: aperto solo sul lato destro (x > 0), con una zanna
mouth, fang = grin(0.135, 1.508, 0.12, 0.035, 0.035, 0.078, [(0.13, 0.046, 0.9)], -1.3, -0.4)

# muso, guance a ciuffi e petto bianchi
cheek = ellipsoid((0.33, 0.42, 0.17)).rot(0, -28, 0).translate((0.47, -0.44, 1.47))  # sale verso l'esterno
white_region = union(ellipsoid((0.3, 0.42, 0.24), (0, -0.84, 1.5)), cheek, cheek.mirrored(),
                     ellipsoid((0.3, 0.4, 0.33), (0, -0.66, 1.14)), k=0.1)
white_region = white_region.subtract(front_legs.offset(0.03)).subtract(mouth.offset(0.01))
m.add("White", paint(white_region), WHITE_FUR, role="detail", tris=1600, voxel=0.022)

# interno delle orecchie crema e punte scure
inner_local = box((0.4, 0.2, 0.5), (0, -0.2, 0.25)).intersect(
    tri_plate([(-0.15, 0.1), (0.15, 0.1), (0.0, 0.56)], 0.3, 0.05))
tip_local = box((0.5, 0.3, 0.2), (0, 0, 0.75))
ear_in = union(place_ear(inner_local, 1), place_ear(inner_local, -1))
ear_tip = union(place_ear(tip_local, 1), place_ear(tip_local, -1))
m.add("EarIn", paint(ear_in, t=0.018, depth=0.04), CREAM_IN, role="detail", tris=900, voxel=0.015)
m.add("EarTips", paint(ear_tip, depth=0.04), DARK, role="detail", tris=500, voxel=0.014)

# calzini scuri: zampe anteriori fino a meta' (dita comprese) e punta dei piedi posteriori
socks_region = union(*[box((0.22, 0.26, 0.18), (sx * 0.3, -0.56, 0.18)) for sx in (1, -1)],
                     *[ellipsoid((0.17, 0.13, 0.13), (sx * 0.58, -0.38, 0.12)) for sx in (1, -1)])
m.add("Socks", paint(socks_region), DARK, role="detail", tris=1000, voxel=0.02)

# ------------------------------------------------------------------ codone con la punta bianca cucita (scodinzola)
tail_pts = bezier((0.22, 0.52, 0.48), (0.85, 1.02, 0.35), (1.18, 0.86, 1.15), (0.9, 0.62, 1.72), 18)
tail_r = [max(0.05, 0.17 + 0.23 * math.sin(math.pi * t * 1.1) - 0.12 * t) for t in np.linspace(0, 1, 19)]
tail = tube(tail_pts, tail_r)
TAIL_PIVOT = (0.25, 0.55, 0.52)
tip_c = np.array(tail_pts[-2])
m.add("Tail", tail, ORANGE, role="skin", tris=1600, voxel=0.02, group="Tail", pivot=TAIL_PIVOT)
m.add("TailTip", tail.offset(0.02).intersect(sphere(0.36, tip_c)), WHITE_FUR, role="detail", tris=600,
      voxel=0.015, group="Tail", pivot=TAIL_PIVOT)
# cucitura dove la punta bianca e' attaccata: anello di punti attorno alla coda
# (il bordo del bianco e' dove la superficie della coda dista 0.36 dal centro della punta)
dense = np.array(bezier((0.22, 0.52, 0.48), (0.85, 1.02, 0.35), (1.18, 0.86, 1.15), (0.9, 0.62, 1.72), 300))
dense_r = np.interp(np.linspace(0, 1, 301), np.linspace(0, 1, 19), tail_r)
gap = np.abs(np.linalg.norm(dense - tip_c, axis=1) ** 2 + (dense_r + 0.02) ** 2 - 0.36 ** 2)
i_seam = int(np.argmin(np.where(np.arange(301) < 285, gap, 1e9)))
c_seam = dense[i_seam]
axis = dense[i_seam + 2] - dense[i_seam - 2]
axis /= np.linalg.norm(axis)
u = np.cross(axis, (0, 0, 1.0))
u /= np.linalg.norm(u)
v = np.cross(axis, u)
ring = [project(tail.offset(0.012), c_seam, u * math.cos(a) + v * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 29)]
m.add("TailStitch", fast_union(stitches(ring, every=0.075, half=0.04, r=0.017, inset=0.003)), THREAD, role="detail",
      tris=800, voxel=0.011, group="Tail", pivot=TAIL_PIVOT)

# ------------------------------------------------------------------ faccia: occhi socchiusi, naso, ghigno
EYE_R = (0.15, 0.09, 0.2)
eye_frames = [Frame(head, HEAD_C, (0.4 * sx, -1.0, 0.15), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(ellipsoid(EYE_R)) for f in eye_frames]), EYE, role="eye", tris=700, voxel=0.013)
lid = ellipsoid((EYE_R[0] + 0.022, EYE_R[1] + 0.03, EYE_R[2] + 0.022))
m.add("Lids", union(eye_frames[0].place(lid.intersect(above_line(-0.01, 0.0), k=0.012)),
                    eye_frames[1].place(lid.intersect(above_line(0.02, 0.0), k=0.012))), ORANGE, role="skin",
      tris=500, voxel=0.012)
shines = []
for f, hz in zip(eye_frames, (-0.05, -0.03)):
    shines.append(f.place(sphere(0.04), (-0.05, -0.08, hz)))
    shines.append(f.place(sphere(0.021), (0.055, -0.072, hz - 0.08)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=300, voxel=0.009)

nose = union(ellipsoid((0.095, 0.065, 0.06), (0, 0, 0.012)), ellipsoid((0.05, 0.05, 0.045), (0, -0.005, -0.03)), k=0.04)
m.add("Nose", Frame(painted, (0, -0.72, 1.6), (0, -1.0, 0.3), sink=0.03).place(nose), NOSE, role="detail",
      tris=400, voxel=0.011, reflectance=0.08)

line_pts = [(0.05, 1.512), (0, 1.505), (0, 1.56), (0, 1.505), (-0.05, 1.49), (-0.1, 1.49), (-0.14, 1.505)]
mouth_line = tube([p - n * 0.006 for p, n in [project(painted, (x, -0.5, z), (0, -1, 0)) for x, z in line_pts]], 0.02)
m.add("Mouth", union(paint(mouth, t=0.014, depth=0.03), mouth_line), MOUTH, role="eye", tris=700, voxel=0.009)
m.add("Teeth", paint(fang, t=0.03, depth=0.02), WHITE, role="shine", tris=300, voxel=0.007)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
