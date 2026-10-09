"""Agnellino (Lamb) - pet Comune. Carattere: bambola inquietante-tenera (occhi a bottone, sorriso cucito)."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, box, capsule, cylinder, ellipsoid, project, sphere, stick, torus,  # noqa: E402
                     tube, union)
from lib.toy import Model  # noqa: E402

WOOL = (246, 238, 218)
FACE = (78, 60, 72)
HOOF = (38, 28, 38)
EAR_IN = (214, 112, 138)
BUTTON = (228, 218, 200)
THREAD = (206, 34, 62)
NOSE = (226, 120, 146)
BLUSH = (232, 106, 136)

m = Model("Lamb", "pet")


def fib_dirs(n):
    """Direzioni quasi uniformi sulla sfera (spirale di Fibonacci)."""
    out = []
    ga = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - z * z)
        out.append((r * math.cos(i * ga), r * math.sin(i * ga), z))
    return out


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


def seam(path, every=0.075, half=0.04, r=0.013, line_r=0.012, inset=0.0):
    """Cucitura: linea + punti corti perpendicolari (come una cicatrice di peluche)."""
    pts = resample(path, every)
    out = [tube([p - n * inset for p, n in resample(path, 0.03)], line_r)]
    for i, (p, n) in enumerate(pts):
        t = pts[min(i + 1, len(pts) - 1)][0] - pts[max(i - 1, 0)][0]
        side = np.cross(n, t / np.linalg.norm(t))
        c = p - n * inset
        out.append(capsule(c - side * half, c + side * half, r))
    return fast_union(out)


def button(r, t=0.05):
    """Bottone a quattro fori (faccia verso -Y locale): disco con bordo rialzato + filo a X (a parte)."""
    disc = cylinder((0, -0.02, 0), (0, -(t - 0.02), 0), r, round=0.02)
    rim = torus(r - 0.022, 0.016).rot(90, 0, 0).translate((0, -t + 0.004, 0))
    holes = union(*[cylinder((hx, 0.0, hz), (hx, -t - 0.05, hz), 0.017) for hx in (-0.032, 0.032)
                    for hz in (-0.032, 0.032)])
    thread = union(capsule((-0.032, -t - 0.002, -0.032), (0.032, -t - 0.002, 0.032), 0.014),
                   capsule((-0.032, -t - 0.002, 0.032), (0.032, -t - 0.002, -0.032), 0.014))
    return union(disc, rim).subtract(holes, k=0.006), thread


# ------------------------------------------------------------------ lana arruffata: batuffoli irregolari
BODY_C = np.array((0.0, 0.12, 0.98))
BODY_R = np.array((0.82, 0.8, 0.62))
rng = np.random.default_rng(11)
puffs = [ellipsoid(BODY_R, BODY_C)]
for d in fib_dirs(36):
    if d[2] < -0.55:
        continue  # sotto la pancia restano libere le zampe
    c = BODY_C + BODY_R * np.array(d) * rng.uniform(0.82, 0.93)
    puffs.append(sphere(rng.uniform(0.23, 0.33), c))
for d in fib_dirs(9)[:6]:  # ciocche spettinate che sporgono
    c = BODY_C + BODY_R * np.array(d) * 1.12 + np.array((0, 0.05, 0.02))
    puffs.append(sphere(rng.uniform(0.1, 0.13), c))
puffs += [sphere(0.15, (0, 1.02, 1.12)), sphere(0.11, (0.1, 1.08, 1.22)), sphere(0.11, (-0.08, 1.1, 1.05))]
wool = union(*puffs, k=0.07)

HEAD_C = (0, -0.52, 1.86)
head = ellipsoid((0.6, 0.52, 0.58), HEAD_C)
tuft_puffs = []
tuft_spec = [(0, 0, 0.17), (14, 120, 0.15), (22, -40, 0.14)]
tuft_spec += [(34, a + rng.uniform(-15, 15), rng.uniform(0.12, 0.16)) for a in range(0, 360, 60)]
tuft_spec += [(50, -90, 0.14), (50, -55, 0.12), (52, -125, 0.13)]
for pol, az, r in tuft_spec:
    pr, ar = math.radians(pol), math.radians(az)
    p, n = project(head, HEAD_C, (math.sin(pr) * math.cos(ar), math.sin(pr) * math.sin(ar), math.cos(pr)))
    tuft_puffs.append(sphere(r, p - n * 0.03))
p, n = project(head, HEAD_C, (0.2, 0.1, 1.0))
curl = bezier(p, p + n * 0.22, p + n * 0.3 + np.array((0.16, -0.04, 0.0)),
              p + n * 0.16 + np.array((0.18, -0.06, 0.0)), 10)
tuft_puffs.append(tube(curl, list(np.linspace(0.09, 0.045, 11))))  # ricciolo ribelle
tuft = union(*tuft_puffs, k=0.06)
m.add("Wool", union(wool, tuft), WOOL, material="Fabric", role="skin", tris=6000, voxel=0.025)

# ------------------------------------------------------------------ testa scura
snout = ellipsoid((0.4, 0.3, 0.28), (0, -0.86, 1.62))
face = union(head, snout, k=0.15)
m.add("Head", face, FACE, role="detail", tris=2300)

ear_local = ellipsoid((0.28, 0.08, 0.13), (0.22, 0, 0))
ear_in_local = ear_local.offset(0.014).intersect(ellipsoid((0.19, 0.1, 0.075), (0.27, -0.07, 0)))


def place_ear(shape, sx):
    s = shape.rot(0, 32 if sx > 0 else 22, 0).rot(0, 0, -15).translate((0.42, -0.52, 2.05))
    return s if sx > 0 else s.mirrored()


for sx, nm in ((1, "EarR"), (-1, "EarL")):
    pivot = (sx * 0.5, -0.52, 2.05)
    m.add(nm, place_ear(ear_local, sx), FACE, role="detail", tris=600, voxel=0.015, group=nm, pivot=pivot)
    m.add(nm + "In", place_ear(ear_in_local, sx), EAR_IN, role="detail", tris=350, voxel=0.012, group=nm,
          pivot=pivot)

# ------------------------------------------------------------------ zampe con zoccoli
legs, hooves = [], []
for x, y in ((0.34, -0.3), (-0.34, -0.3), (0.36, 0.52), (-0.36, 0.52)):
    # nota: cylinder(round=) allunga il cilindro di 'round' a ogni estremita'
    legs.append(cylinder((x, y, 0.16), (x, y, 0.62), 0.16, round=0.06))
    hoof = cylinder((x, y, 0.05), (x, y, 0.12), 0.175, round=0.05)
    hooves.append(hoof.subtract(box((0.012, 0.08, 0.1), (x, y - 0.17, 0.06)), k=0.01))  # unghia divisa
m.add("Legs", union(*legs), FACE, role="detail", tris=1100)
m.add("Hooves", union(*hooves), HOOF, role="detail", tris=800, voxel=0.015)

# ------------------------------------------------------------------ occhi a bottone cuciti (uno piu' grande e storto)
buttons, threads = [], []
for sx, r, spin in ((1, 0.125, 18), (-1, 0.108, -8)):
    disc, x_thread = button(r)
    f = Frame(head, HEAD_C, (0.42 * sx, -1.0, 0.16), sink=0.02)
    buttons.append(f.place(disc.rot(0, spin, 0)))
    threads.append(f.place(x_thread.rot(0, spin, 0)))
m.add("Eyes", union(*buttons), BUTTON, role="eye", tris=1000, voxel=0.01)

# sorriso cucito, un po' storto
smile_pts = bezier((-0.27, 0, 1.6), (-0.12, 0, 1.47), (0.12, 0, 1.47), (0.29, 0, 1.63), 14)
smile_path = [project(face, (p[0], -0.7, p[2]), (0, -1, 0)) for p in smile_pts]
m.add("Thread", union(*threads, seam(smile_path, every=0.07, half=0.038)), THREAD, role="detail", tris=1300,
      voxel=0.009)

nose = union(ellipsoid((0.085, 0.05, 0.05), (0, 0, 0.012)), ellipsoid((0.04, 0.04, 0.04), (0, -0.004, -0.03)), k=0.035)
m.add("Nose", Frame(face, (0, -0.8, 1.62), (0, -1.0, 0.45), sink=0.025).place(nose), NOSE, role="detail", tris=400,
      voxel=0.011)
blush = ellipsoid((0.1, 0.03, 0.1))
m.add("Blush", union(*[stick(blush, face, HEAD_C, (0.66 * sx, -0.85, -0.3), sink=0.012) for sx in (1, -1)]),
      BLUSH, role="detail", tris=400, voxel=0.012)

# zampe piu' corte e tozze: abbassa tutto tranne zampe e zoccoli; poi scala globale a ~3 unita' di altezza
DROP, S = 0.08, 1.1
for _p in m.parts:
    if _p.name not in ("Legs", "Hooves"):
        _p.sdf = _p.sdf.translate((0, 0, -DROP))
        if _p.pivot:
            _p.pivot = (_p.pivot[0], _p.pivot[1], _p.pivot[2] - DROP)
    _p.sdf = _p.sdf.scale(S)
    if _p.pivot:
        _p.pivot = tuple(c * S for c in _p.pivot)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
