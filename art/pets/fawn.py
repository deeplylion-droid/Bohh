"""Cerbiatto (Fawn) - pet Non comune. Carattere: dolce-inquietante (testa inclinata, pupille piccole, sorriso largo)."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (Frame, box, capsule, cylinder, ellipsoid, euler, prism, project, round_cone, sphere,  # noqa: E402
                     union)
from lib.toy import Model  # noqa: E402

FAWN = (204, 118, 58)
CREAM = (255, 232, 200)
SPOT = (255, 250, 240)
HOOF = (54, 32, 44)
EAR_IN = (226, 140, 152)
NOSE = (36, 22, 30)
EYE = (30, 16, 30)
MOUTH = (72, 16, 42)
BOW = (142, 22, 58)
WHITE = (255, 255, 255)

m = Model("Fawn", "pet")


# ------------------------------------------------------------------ aiuti
def face_prism(poly, y0, y1, r=0.0):
    """Regione: poligono nel piano XZ (coppie x, z) estruso lungo Y fra y0 e y1."""
    return prism(poly, -y1, -y0, round=r).rot(90, 0, 0)


def grin(xc, zc, half_w, curve, slope, thick, n_teeth, tooth_w, y0, y1):
    """Sorriso sottile a mezzaluna (regione) con una fila di dentini aguzzi (regione)."""
    def top(x):
        u = (x - xc) / half_w
        return zc + curve * u * u + slope * u, thick * max(0.0, 1 - u * u) ** 0.7

    xs = np.linspace(xc - half_w, xc + half_w, 25)
    upper = [(x, top(x)[0]) for x in xs]
    lower = [(x, top(x)[0] - top(x)[1]) for x in xs[-2:0:-1]]  # niente vertici doppi: prism() darebbe NaN
    mouth = face_prism(upper + lower, y0, y1, r=0.003)
    teeth = []
    for i in range(n_teeth):
        x = xc + (i - (n_teeth - 1) / 2) * 1.5 * half_w / n_teeth
        z, th = top(x)
        teeth.append(face_prism([(x - tooth_w / 2, z + 0.02), (x + tooth_w / 2, z + 0.02), (x, z - 0.6 * th)],
                                y0, y1, r=0.003))
    return mouth, union(*teeth).intersect(mouth.offset(-0.008))


# testa inclinata: tutto cio' che sta sulla testa e' costruito dritto e poi ruotato attorno al collo
TILT, NECK = -12.0, np.array((0.0, -0.38, 1.88))
_R = euler(0, TILT, 0)


def tilt(s):
    return s.rot(0, TILT, 0, pivot=NECK)


def tilt_pt(p):
    return tuple(float(v) for v in _R @ (np.asarray(p, dtype=np.float32) - NECK) + NECK)


# ------------------------------------------------------------------ testa (spazio "dritto") e corpo su zampe lunghe
HEAD_C = (0, -0.42, 2.18)
head = ellipsoid((0.64, 0.58, 0.56), HEAD_C)
muzzle = ellipsoid((0.3, 0.32, 0.24), (0, -0.9, 2.0))
head_core = union(head, muzzle, k=0.15)

torso = ellipsoid((0.5, 0.72, 0.46), (0, 0.22, 1.08))
chest = ellipsoid((0.44, 0.4, 0.44), (0, -0.25, 1.15))
neck = capsule((0, -0.25, 1.3), (0, -0.38, 1.85), 0.25)
haunches = union(*[ellipsoid((0.25, 0.34, 0.34), (sx * 0.27, 0.62, 1.0)) for sx in (1, -1)])
LEGS = ((0.26, -0.28), (-0.26, -0.28), (0.27, 0.66), (-0.27, 0.66))
LIFT = 0.12  # alla fine tutto (tranne gli zoccoli) sale di LIFT: zampe piu' lunghe e sottili
legs = union(*[round_cone((x, y, 0.95), (x, y, 0.16 - LIFT), 0.135, 0.1) for x, y in LEGS])
core = union(torso, chest, k=0.2)
core = union(core, haunches, k=0.15)
core = union(core, neck, k=0.18)
core = union(core, legs, k=0.1)
core = union(core, tilt(head_core), k=0.2)
m.add("Body", core, FAWN, tris=5600)


def paint(region, t=0.02, depth=0.06):
    """Vernice sottile che segue la superficie (solo uno strato vicino alla pelle)."""
    return core.offset(t).intersect(region).subtract(core.offset(-depth))


# sorriso troppo largo con dentini (spazio testa)
mouth, teeth = grin(0.0, 1.905, 0.27, 0.085, 0.0, 0.05, 9, 0.03, -1.4, -0.6)

# pancia, petto, gola e muso color crema
cream_region = union(ellipsoid((0.4, 0.72, 0.3), (0, 0.22, 0.66)), ellipsoid((0.3, 0.3, 0.42), (0, -0.52, 1.25)),
                     ellipsoid((0.22, 0.25, 0.36), (0, -0.56, 1.72)), k=0.12).subtract(legs.offset(0.03))
muzzle_region = tilt(ellipsoid((0.3, 0.3, 0.22), (0, -0.98, 1.94)).subtract(mouth.offset(0.01)))
m.add("Cream", paint(union(cream_region, muzzle_region)), CREAM, role="detail", tris=1300, voxel=0.022)

# macchie bianche sul dorso (due file lungo la schiena + qualcuna sui fianchi)
spots = []
for x, y, r in ((0.17, 0.1, 0.075), (-0.17, 0.1, 0.075), (0.2, 0.33, 0.085), (-0.2, 0.33, 0.085),
                (0.18, 0.56, 0.08), (-0.18, 0.56, 0.08), (0.14, 0.78, 0.065), (-0.14, 0.78, 0.065)):
    p, _ = project(core, (x * 0.5, y, 1.1), (x, 0.0, 1.0))
    spots.append(sphere(r, p))
for sx in (1, -1):
    for y, z, r in ((0.02, 1.2, 0.065), (0.3, 1.27, 0.07), (0.56, 1.22, 0.065), (0.78, 1.1, 0.06)):
        p, _ = project(core, (0, y, z), (sx, 0.0, 0.25))
        spots.append(sphere(r, p))
m.add("Spots", paint(union(*spots), t=0.026, depth=0.04), SPOT, role="detail", tris=1000, voxel=0.014)

hooves = []
for x, y in LEGS:
    h = cylinder((x, y, 0.05), (x, y, 0.12), 0.12, round=0.05)
    hooves.append(h.subtract(box((0.012, 0.08, 0.12), (x, y - 0.12, 0.06)), k=0.01))
m.add("Hooves", union(*hooves), HOOF, role="detail", tris=700, voxel=0.014)

tail = ellipsoid((0.1, 0.12, 0.17)).rot(-40, 0, 0).translate((0, 0.92, 1.4))
m.add("Tail", tail, WHITE, role="detail", tris=350, voxel=0.014)

# ------------------------------------------------------------------ orecchie grandi (animabili) e fiocco
ear_local = ellipsoid((0.17, 0.065, 0.38), (0, 0, 0.34))
ear_in_local = ear_local.offset(0.014).intersect(ellipsoid((0.11, 0.1, 0.27), (0, -0.06, 0.38)))


def place_ear(shape, sx):
    s = shape.rot(-10, 0, 0).rot(0, 0, 20).rot(0, 55, 0).translate((0.4, -0.32, 2.5))
    return tilt(s if sx > 0 else s.mirrored())


for sx, nm in ((1, "EarR"), (-1, "EarL")):
    pivot = tilt_pt((sx * 0.42, -0.32, 2.52))
    m.add(nm, place_ear(ear_local, sx), FAWN, role="skin", tris=700, voxel=0.016, group=nm, pivot=pivot)
    m.add(nm + "In", place_ear(ear_in_local, sx), EAR_IN, role="detail", tris=350, voxel=0.013, group=nm,
          pivot=pivot)

bow_f = Frame(head, HEAD_C, (0.7, -0.25, 0.85), sink=0.02)
loop = ellipsoid((0.13, 0.075, 0.095)).subtract(ellipsoid((0.06, 0.1, 0.035), (0.03, -0.04, 0.0)), k=0.02)
bow = union(*[(loop if sx > 0 else loop.mirrored()).rot(0, -sx * 22, 0).translate((sx * 0.11, -0.03, 0.02))
              for sx in (1, -1)],
            sphere(0.06, (0, -0.05, 0)), *[round_cone((sx * 0.02, -0.03, -0.03), (sx * 0.1, -0.03, -0.19), 0.04, 0.022)
                                             for sx in (1, -1)], k=0.02)
m.add("Bow", tilt(bow_f.place(bow)), BOW, material="Fabric", role="detail", tris=700, voxel=0.011)

# ------------------------------------------------------------------ occhioni: bianco grande, pupilla piccola, ciglia
eye_frames = [Frame(head, HEAD_C, (0.6 * sx, -1.0, 0.22), sink=0.045) for sx in (1, -1)]
dark, whites, shines = [], [], []
for f, sx in zip(eye_frames, (1, -1)):
    dark.append(f.place(ellipsoid((0.17, 0.05, 0.212)), (0, -0.015, 0)))
    whites.append(f.place(ellipsoid((0.152, 0.08, 0.194)), (0, -0.025, 0)))
    dark.append(f.place(ellipsoid((0.066, 0.035, 0.072)), (0.012 * sx, -0.09, 0.01)))
    shines.append(f.place(sphere(0.02), (0.012 * sx - 0.03, -0.118, 0.04)))
    # tre ciglia all'angolo esterno, verso l'alto
    for k, ang in enumerate((25, 45, 65)):
        a = math.radians(ang)
        base = np.array((-sx * 0.12, -0.03, 0.15))
        tip = base + np.array((-sx * math.cos(a), -0.02, math.sin(a))) * 0.09
        dark.append(f.place(round_cone(tuple(base), tuple(tip), 0.016, 0.008)))
m.add("Eyes", tilt(union(*dark)), EYE, role="eye", tris=1000, voxel=0.01)
m.add("EyeWhites", tilt(union(*whites)), WHITE, role="shine", tris=600, voxel=0.012)
m.add("Shine", tilt(union(*shines)), WHITE, role="shine", tris=200, voxel=0.008)

nose = union(ellipsoid((0.09, 0.06, 0.06), (0, 0, 0.012)), ellipsoid((0.05, 0.05, 0.045), (0, -0.005, -0.03)), k=0.04)
m.add("Nose", tilt(Frame(head_core.offset(0.02), (0, -0.9, 2.0), (0, -1.0, 0.35), sink=0.03).place(nose)), NOSE,
      role="detail", tris=350, voxel=0.011, reflectance=0.08)
head_paint = head_core.offset(0.014).intersect(mouth).subtract(head_core.offset(-0.03))
m.add("Mouth", tilt(head_paint), MOUTH, role="eye", tris=600, voxel=0.008)
m.add("Teeth", tilt(head_core.offset(0.03).intersect(teeth).subtract(head_core.offset(-0.02))), WHITE, role="shine",
      tris=700, voxel=0.0065)

# zampe piu' lunghe: alza tutto tranne gli zoccoli (le zampe sono gia' state allungate di LIFT); scala a ~3 unita'
S = 0.97
for _p in m.parts:
    if _p.name != "Hooves":
        _p.sdf = _p.sdf.translate((0, 0, LIFT))
        if _p.pivot:
            _p.pivot = (_p.pivot[0], _p.pivot[1], _p.pivot[2] + LIFT)
    _p.sdf = _p.sdf.scale(S)
    if _p.pivot:
        _p.pivot = tuple(c * S for c in _p.pivot)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
