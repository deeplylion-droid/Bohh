"""Coniglietto (Bunny) - pet Comune. Carattere: maniacale (occhi sgranati, ghignone, testa inclinata)."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, box, capsule, ellipsoid, euler, prism, project, sphere, tube,  # noqa: E402
                     union)
from lib.toy import Model  # noqa: E402

FUR = (248, 244, 236)
CREAM = (255, 224, 192)
PINK_IN = (240, 88, 146)
NOSE = (222, 40, 104)
PADS = (238, 82, 140)
PATCH = (112, 62, 170)
THREAD = (36, 26, 66)
EYE = (30, 18, 46)
MOUTH = (62, 10, 44)
WHITE = (255, 255, 255)

m = Model("Bunny", "pet")


# ------------------------------------------------------------------ aiuti (ghigno, cuciture)
def face_prism(poly, y0, y1, r=0.0):
    """Regione: poligono nel piano XZ (coppie x, z) estruso lungo Y fra y0 e y1."""
    return prism(poly, -y1, -y0, round=r).rot(90, 0, 0)


def paint(base, region, t=0.02, depth=0.05):
    """Vernice sottile che segue la superficie (solo uno strato vicino alla pelle)."""
    return base.offset(t).intersect(region).subtract(base.offset(-depth))


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
    """Bocca a mezzaluna (regione) e denti (regione). teeth_spec: (x, larghezza, frazione, tipo) con tipo
    'up' (aguzzo dal bordo alto), 'low' (aguzzo dal basso) o 'buck' (dentone squadrato)."""
    def top(x):
        u = (x - xc) / half_w
        return zc + curve * u * u + slope * u, thick * max(0.0, 1 - u * u) ** 0.7

    xs = np.linspace(xc - half_w, xc + half_w, 25)
    upper = [(x, top(x)[0]) for x in xs]
    lower = [(x, top(x)[0] - top(x)[1]) for x in xs[-2:0:-1]]  # niente vertici doppi: prism() darebbe NaN
    mouth = face_prism(upper + lower, y0, y1, r=0.004)
    teeth = []
    for x, w, frac, kind in teeth_spec:
        z, th = top(x)
        if kind == "up":
            poly = [(x - w / 2, z + 0.02), (x + w / 2, z + 0.02), (x, z - frac * th)]
        elif kind == "low":
            poly = [(x - w / 2, z - th - 0.02), (x + w / 2, z - th - 0.02), (x, z - (1 - frac) * th)]
        else:
            b = z - frac * th
            poly = [(x - w / 2, z + 0.02), (x + w / 2, z + 0.02), (x + w / 2, b + 0.02), (x + w * 0.3, b),
                    (x - w * 0.3, b), (x - w / 2, b + 0.02)]
        teeth.append(face_prism(poly, y0, y1, r=0.004))
    return mouth, union(*teeth).intersect(mouth.offset(-0.009))


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


def stitches(path, every=0.07, half=0.035, r=0.011, inset=0.0):
    """Punti di cucitura corti, perpendicolari al percorso (punto, normale)."""
    pts = resample(path, every)
    out = []
    for i, (p, n) in enumerate(pts):
        t = pts[min(i + 1, len(pts) - 1)][0] - pts[max(i - 1, 0)][0]
        side = np.cross(n, t / np.linalg.norm(t))
        c = p - n * inset
        out.append(capsule(c - side * half, c + side * half, r))
    return out


# testa inclinata: tutto cio' che sta sulla testa e' costruito dritto e poi ruotato attorno al collo
TILT, NECK = 10.0, np.array((0.0, 0.0, 1.45))
_R = euler(0, TILT, 0)


def tilt(s):
    return s.rot(0, TILT, 0, pivot=NECK)


def tilt_pt(p):
    return tuple(float(v) for v in _R @ (np.asarray(p, dtype=np.float32) - NECK) + NECK)


# ------------------------------------------------------------------ testa (spazio "dritto")
HEAD_C = (0, -0.05, 1.9)
head = ellipsoid((0.8, 0.72, 0.68), HEAD_C)
head_core = union(head, *[ellipsoid((0.34, 0.28, 0.28), (sx * 0.38, -0.34, 1.7)) for sx in (1, -1)], k=0.18)

# ------------------------------------------------------------------ corpo seduto, braccia lunghe, piedoni
body = ellipsoid((0.72, 0.66, 0.78), (0, 0.08, 0.84))
arms = []
for sx in (1, -1):
    arms.append(tube([(sx * 0.55, -0.02, 1.34), (sx * 0.68, -0.18, 0.86), (sx * 0.71, -0.3, 0.44)], [0.12, 0.11, 0.115]))
    arms.append(ellipsoid((0.16, 0.16, 0.14), (sx * 0.71, -0.36, 0.31)))
    arms += [sphere(0.075, (sx * 0.71 + dx, -0.47, 0.2)) for dx in (-0.085, 0.0, 0.085)]
arms = union(*arms, k=0.06)


def place_foot(shape, sx):
    s = shape.rot(-45, 0, 0).rot(0, 0, 8).translate((0.42, -0.52, 0.336))
    return s if sx > 0 else s.mirrored()


foot_local = ellipsoid((0.24, 0.44, 0.165))
feet = union(place_foot(foot_local, 1), place_foot(foot_local, -1))
core = union(body, arms, k=0.08)
core = union(core, feet, k=0.08)
core = union(core, tilt(head_core), k=0.3)
m.add("Body", core, FUR, material="Fabric", tris=4800)

# ------------------------------------------------------------------ ghignone (spazio testa)
spec = [(-0.05, 0.08, 0.62, "buck"), (0.05, 0.08, 0.62, "buck")]
spec += [(sx * x, 0.048, 0.58, "up") for sx in (1, -1) for x in (0.145, 0.215, 0.285)]
spec += [(sx * x, 0.042, 0.48, "low") for sx in (1, -1) for x in (0.11, 0.18, 0.25)]
mouth, teeth = grin(0.0, 1.62, 0.38, 0.1, 0.02, 0.145, spec, -1.3, -0.3)

belly_region = ellipsoid((0.48, 0.48, 0.5), (0, -0.6, 0.76)).subtract(union(arms, feet).offset(0.04))
muzzle_region = tilt(ellipsoid((0.44, 0.34, 0.25), (0, -0.66, 1.6)).subtract(mouth.offset(0.012)))
m.add("Cream", paint(core, union(belly_region, muzzle_region)), CREAM, role="detail", tris=1100)

pad_local = union(ellipsoid((0.13, 0.17, 0.1), (0, 0.08, -0.165)),
                  *[sphere(0.06, (dx, -0.26, -0.133 + abs(dx) * 0.2)) for dx in (-0.11, 0.0, 0.11)])
finger_pads = [sphere(0.05, (sx * 0.71 + dx, -0.54, 0.19)) for sx in (1, -1) for dx in (-0.085, 0.0, 0.085)]
m.add("Pads", paint(core, union(place_foot(pad_local, 1), place_foot(pad_local, -1), *finger_pads), t=0.018),
      PADS, role="detail", tris=800, voxel=0.015)

# ------------------------------------------------------------------ orecchie: una dritta, una piegata con la toppa
ear_r = ellipsoid((0.2, 0.09, 0.52), (0, 0, 0.52)).subtract(ellipsoid((0.11, 0.05, 0.36), (0, -0.1, 0.6)), k=0.04)
ear_r_in = ear_r.offset(0.016).intersect(ellipsoid((0.125, 0.12, 0.4), (0, -0.07, 0.6)))


def droop(s):
    """Orecchio sinistro "a penzoloni": base inclinata in fuori, meta' alta ripiegata verso il basso."""
    return s.rot(0, 55, 0)


def fold(s):
    return s.rot(0, 75, 0, pivot=(0, 0, 0.34))


low = ellipsoid((0.2, 0.09, 0.2), (0, 0, 0.17))
up = ellipsoid((0.19, 0.085, 0.38), (0, 0, 0.68))
ear_l = droop(union(low, fold(up), k=0.08))
ear_l_in = ear_l.offset(0.016).intersect(droop(union(ellipsoid((0.12, 0.1, 0.13), (0, -0.09, 0.2)),
                                                     fold(ellipsoid((0.115, 0.1, 0.3), (0, -0.09, 0.66))))))
# toppa cucita sulla parte che penzola (solo faccia davanti: y < 0)
patch_box = box((0.1, 0.1, 0.12), (0.0, -0.1, 0.78), round=0.03)
ear_l_patch = droop(fold(paint(up, patch_box, t=0.03, depth=0.03)))
outline = [(-0.1, 0.66), (0.1, 0.66), (0.1, 0.9), (-0.1, 0.9), (-0.1, 0.66)]
dense = []
for (x0, z0), (x1, z1) in zip(outline[:-1], outline[1:]):
    dense += [(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t) for t in np.linspace(0, 1, 6)[:-1]]
dense.append(outline[-1])
patch_path = [project(up.offset(0.03), (x, 0.0, z), (0, -1, 0)) for x, z in dense]
ear_l_stitch = droop(fold(fast_union(stitches(patch_path, every=0.06, half=0.028, r=0.014, inset=0.008))))


def place_ear(shape, sx):
    s = shape.rot(0, 0, 15).rot(0, 12, 0).rot(-8, 0, 0).translate((0.3, 0.0, 2.33))
    return tilt(s if sx > 0 else s.mirrored())


for sx, nm, shell, inner in ((1, "EarR", ear_r, ear_r_in), (-1, "EarL", ear_l, ear_l_in)):
    pivot = tilt_pt((sx * 0.3, 0.0, 2.43))
    m.add(nm, place_ear(shell, sx), FUR, material="Fabric", role="skin", tris=1000, voxel=0.02, group=nm,
          pivot=pivot)
    m.add(nm + "In", place_ear(inner, sx), PINK_IN, role="detail", tris=500, voxel=0.015, group=nm, pivot=pivot)
    if nm == "EarL":
        m.add("EarLPatch", place_ear(ear_l_patch, sx), PATCH, material="Fabric", role="detail", tris=400,
              voxel=0.012, group=nm, pivot=pivot)
        m.add("EarLStitch", place_ear(ear_l_stitch, sx), THREAD, role="detail", tris=500, voxel=0.008, group=nm,
              pivot=pivot)

# ------------------------------------------------------------------ occhi sgranati cerchiati di scuro
eye_frames = [Frame(head, HEAD_C, (0.42 * sx, -1.0, 0.12), sink=0.04) for sx in (1, -1)]
dark, whites, shines = [], [], []
for f, sx, pr in zip(eye_frames, (1, -1), (0.085, 0.064)):  # pupille diverse: sguardo un po' folle
    dark.append(f.place(ellipsoid((0.163, 0.075, 0.203))))
    whites.append(f.place(ellipsoid((0.15, 0.08, 0.19)), (0, -0.012, 0)))
    dark.append(f.place(ellipsoid((pr, 0.035, pr * 1.12)), (0.02 * sx, -0.074, -0.01)))
    shines.append(f.place(sphere(0.022), (0.02 * sx - pr * 0.45, -0.1, pr * 0.5)))
brows = []
for sx in (1, -1):
    pts = bezier((sx * 0.13, 0, 2.3), (sx * 0.24, 0, 2.44), (sx * 0.4, 0, 2.44), (sx * 0.5, 0, 2.33), 8)
    path = [project(head, (p[0], -0.05, p[2]), (0, -1, 0)) for p in pts]
    brows.append(tube([p - n * 0.008 for p, n in path], list(np.linspace(0.034, 0.024, len(path)))))
m.add("Eyes", tilt(union(*dark, *brows)), EYE, role="eye", tris=1100, voxel=0.011)
m.add("EyeWhites", tilt(union(*whites)), WHITE, role="shine", tris=600, voxel=0.012)
m.add("Shine", tilt(union(*shines)), WHITE, role="shine", tris=250, voxel=0.008)

nose = union(ellipsoid((0.1, 0.06, 0.06), (0, 0, 0.015)), ellipsoid((0.05, 0.05, 0.05), (0, -0.005, -0.035)), k=0.04)
m.add("Nose", tilt(Frame(head_core.offset(0.02), HEAD_C, (0, -1.0, -0.13), sink=0.03).place(nose)), NOSE,
      role="detail", tris=400, voxel=0.012)
m.add("Mouth", tilt(paint(head_core, mouth, t=0.014, depth=0.03)), MOUTH, role="eye", tris=900, voxel=0.01)
m.add("Teeth", tilt(paint(head_core, teeth, t=0.03, depth=0.02)), WHITE, role="shine", tris=1000, voxel=0.0075)

# ------------------------------------------------------------------ codina a batuffolo
TAIL_C = (0, 0.82, 0.5)
puffs = [sphere(0.2, TAIL_C)]
for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1), (0.6, 0.6, 0.5), (-0.6, 0.6, 0.5),
          (0.6, 0.6, -0.5), (-0.6, 0.6, -0.5), (0, 0.7, 0.7), (0.7, 0.2, 0.7), (-0.7, 0.2, 0.7)):
    v = np.array(d, dtype=float) / np.linalg.norm(d)
    puffs.append(sphere(0.12, tuple(np.array(TAIL_C) + v * 0.17)))
m.add("Tail", union(*puffs, k=0.06), WHITE, material="Fabric", role="detail", tris=700, voxel=0.016)

# scala globale (le orecchie lunghe superano le 3 unita')
S = 0.95
for _p in m.parts:
    _p.sdf = _p.sdf.scale(S)
    if _p.pivot:
        _p.pivot = tuple(c * S for c in _p.pivot)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
