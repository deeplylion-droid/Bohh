"""Agnellino (Lamb) - pet Comune."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (Frame, bezier, box, cylinder, ellipsoid, project, project_curve, sphere, stick, tube,  # noqa: E402
                     union)
from lib.toy import Model  # noqa: E402

WOOL = (255, 246, 226)
FACE = (104, 86, 82)
HOOF = (62, 48, 48)
EAR_IN = (255, 170, 184)
NOSE = (255, 148, 170)
EYE = (20, 14, 18)
WHITE = (255, 255, 255)
BLUSH = (255, 128, 150)
MOUTH = (52, 36, 38)

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


# ------------------------------------------------------------------ lana: tanti batuffoli fusi insieme
BODY_C = np.array((0.0, 0.12, 0.98))
BODY_R = np.array((0.82, 0.8, 0.62))
rng = np.random.default_rng(3)
puffs = [ellipsoid(BODY_R, BODY_C)]
for d in fib_dirs(34):
    if d[2] < -0.55:
        continue  # sotto la pancia restano libere le zampe
    c = BODY_C + BODY_R * np.array(d) * 0.86
    puffs.append(sphere(0.27 + rng.uniform(-0.03, 0.03), c))
# codina di lana
puffs += [sphere(0.15, (0, 1.02, 1.12)), sphere(0.11, (0.1, 1.08, 1.22)), sphere(0.11, (-0.08, 1.1, 1.05))]
wool = union(*puffs, k=0.08)

# ciuffo di lana in testa: batuffoli appoggiati sulla calotta, con la frangetta sulla fronte
HEAD_C = (0, -0.52, 1.86)
head = ellipsoid((0.6, 0.52, 0.58), HEAD_C)
tuft_puffs = []
for pol, az, r in ([(0, 0, 0.18)] + [(32, a, 0.15) for a in range(0, 360, 60)]
                   + [(52, -90, 0.14), (50, -60, 0.13), (50, -120, 0.13)]):
    pr, ar = math.radians(pol), math.radians(az)
    p, n = project(head, HEAD_C, (math.sin(pr) * math.cos(ar), math.sin(pr) * math.sin(ar), math.cos(pr)))
    tuft_puffs.append(sphere(r, p - n * 0.035))
tuft = union(*tuft_puffs, k=0.06)
m.add("Wool", union(wool, tuft), WOOL, role="skin", tris=6200, voxel=0.025)

# ------------------------------------------------------------------ testa scura
snout = ellipsoid((0.4, 0.3, 0.28), (0, -0.86, 1.62))
face = union(head, snout, k=0.15)
m.add("Head", face, FACE, role="detail", tris=2600)

# orecchie morbide che sporgono di lato (animabili)
ear_local = ellipsoid((0.28, 0.08, 0.13), (0.22, 0, 0))
ear_in_local = ear_local.offset(0.014).intersect(ellipsoid((0.19, 0.1, 0.075), (0.27, -0.07, 0)))


def place_ear(shape, sx):
    s = shape.rot(0, 25, 0).rot(0, 0, -15).translate((0.42, -0.52, 2.05))
    return s if sx > 0 else s.mirrored()


for sx, nm in ((1, "EarR"), (-1, "EarL")):
    pivot = (sx * 0.5, -0.52, 2.05)
    m.add(nm, place_ear(ear_local, sx), FACE, role="detail", tris=700, voxel=0.015, group=nm, pivot=pivot)
    m.add(nm + "In", place_ear(ear_in_local, sx), EAR_IN, role="detail", tris=400, voxel=0.012, group=nm,
          pivot=pivot)

# ------------------------------------------------------------------ zampe con zoccoli
legs, hooves = [], []
for x, y in ((0.34, -0.3), (-0.34, -0.3), (0.36, 0.52), (-0.36, 0.52)):
    # nota: cylinder(round=) allunga il cilindro di 'round' a ogni estremita'
    legs.append(cylinder((x, y, 0.16), (x, y, 0.62), 0.16, round=0.06))
    hoof = cylinder((x, y, 0.05), (x, y, 0.12), 0.175, round=0.05)
    hoof = hoof.subtract(box((0.012, 0.08, 0.1), (x, y - 0.17, 0.06)), k=0.01)  # unghia divisa
    hooves.append(hoof)
m.add("Legs", union(*legs), FACE, role="detail", tris=1300)
m.add("Hooves", union(*hooves), HOOF, role="detail", tris=900, voxel=0.015)

# ------------------------------------------------------------------ faccia
eye_shape = ellipsoid((0.14, 0.085, 0.18))
eye_frames = [Frame(head, HEAD_C, (0.42 * sx, -1.0, 0.16), sink=0.045) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in eye_frames]), EYE, role="eye", tris=900, voxel=0.013)
shines = []
for f in eye_frames:
    shines.append(f.place(sphere(0.056), (-0.048, -0.07, 0.07)))
    shines.append(f.place(sphere(0.029), (0.054, -0.066, -0.08)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=450, voxel=0.01)

blush = ellipsoid((0.12, 0.035, 0.075))
m.add("Blush", union(*[stick(blush, face, HEAD_C, (0.62 * sx, -0.85, -0.3), sink=0.015) for sx in (1, -1)]),
      BLUSH, role="detail", tris=400, voxel=0.013)

# nasino rosa e sorriso
nose = union(ellipsoid((0.085, 0.05, 0.05), (0, 0, 0.012)), ellipsoid((0.04, 0.04, 0.04), (0, -0.004, -0.03)), k=0.035)
nose_f = Frame(face, (0, -0.8, 1.62), (0, -1.0, 0.45), sink=0.025)
smile = project_curve(face, bezier((-0.12, -1.0, 1.56), (-0.06, -1.0, 1.5), (0.06, -1.0, 1.5), (0.12, -1.0, 1.56), 12),
                      (0, -1, 0), inset=0.008)
mid = project_curve(face, [(0, -1.0, 1.6), (0, -1.0, 1.53)], (0, -1, 0), inset=0.008)
m.add("Nose", nose_f.place(nose), NOSE, role="detail", tris=400, voxel=0.011)
m.add("Mouth", union(tube(smile, 0.02), tube(mid, 0.018)), MOUTH, role="detail", tris=400, voxel=0.01)

# zampe piu' corte e tozze: abbassa tutto tranne zampe e zoccoli; poi scala globale a ~3 unita' di altezza
DROP, S = 0.08, 1.12
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
