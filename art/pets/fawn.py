"""Cerbiatto (Fawn) - pet Non comune."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (Frame, bezier, box, capsule, cylinder, ellipsoid, project, project_curve, round_cone,  # noqa: E402
                     sphere, stick, tube, union)
from lib.toy import Model  # noqa: E402

FAWN = (212, 146, 90)
CREAM = (255, 238, 212)
SPOT = (255, 252, 244)
HOOF = (72, 48, 42)
EAR_IN = (255, 204, 188)
NOSE = (40, 28, 32)
EYE = (32, 20, 26)
WHITE = (255, 255, 255)
BLUSH = (255, 130, 140)
MOUTH = (92, 50, 42)

m = Model("Fawn", "pet")

# ------------------------------------------------------------------ corpo in piedi, collo corto e testone
HEAD_C = (0, -0.42, 2.18)
head = ellipsoid((0.64, 0.58, 0.56), HEAD_C)
muzzle = ellipsoid((0.3, 0.32, 0.24), (0, -0.9, 2.0))
torso = ellipsoid((0.5, 0.72, 0.46), (0, 0.22, 1.08))
chest = ellipsoid((0.44, 0.4, 0.44), (0, -0.25, 1.15))
neck = capsule((0, -0.25, 1.3), (0, -0.38, 1.85), 0.26)
haunches = union(*[ellipsoid((0.25, 0.34, 0.34), (sx * 0.27, 0.62, 1.0)) for sx in (1, -1)])
LEGS = ((0.26, -0.28), (-0.26, -0.28), (0.27, 0.66), (-0.27, 0.66))
DROP = 0.1  # alla fine tutto (tranne gli zoccoli) scende di DROP: zampe piu' corte e tozze
legs = union(*[round_cone((x, y, 0.95), (x, y, 0.16 + DROP), 0.15, 0.115) for x, y in LEGS])
core = union(torso, chest, k=0.2)
core = union(core, haunches, k=0.15)
core = union(core, neck, k=0.18)
core = union(core, head, k=0.2)
core = union(core, muzzle, k=0.15)
core = union(core, legs, k=0.1)
m.add("Body", core, FAWN, tris=6400)
painted = core.offset(0.02)


def paint(region, t=0.02, depth=0.06):
    """Vernice sottile che segue la superficie (solo uno strato vicino alla pelle)."""
    return core.offset(t).intersect(region).subtract(core.offset(-depth))


# pancia, petto, gola e muso color crema
cream_region = union(ellipsoid((0.4, 0.72, 0.3), (0, 0.22, 0.66)), ellipsoid((0.3, 0.3, 0.42), (0, -0.52, 1.25)),
                     ellipsoid((0.22, 0.25, 0.36), (0, -0.56, 1.72)), ellipsoid((0.27, 0.3, 0.22), (0, -0.98, 1.94)),
                     k=0.12).subtract(legs.offset(0.03))
m.add("Cream", paint(cream_region), CREAM, role="detail", tris=1600, voxel=0.022)

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
m.add("Spots", paint(union(*spots), t=0.026, depth=0.04), SPOT, role="detail", tris=1100, voxel=0.014)

# zoccoli scuri con l'unghia divisa
hooves = []
for x, y in LEGS:
    h = cylinder((x, y, 0.05), (x, y, 0.12), 0.135, round=0.05)
    hooves.append(h.subtract(box((0.012, 0.08, 0.12), (x, y - 0.13, 0.06)), k=0.01))
m.add("Hooves", union(*hooves), HOOF, role="detail", tris=800, voxel=0.014)

# codina bianca
tail = ellipsoid((0.1, 0.12, 0.17)).rot(-40, 0, 0).translate((0, 0.92, 1.4))
m.add("Tail", tail, WHITE, role="detail", tris=400, voxel=0.014)

# ------------------------------------------------------------------ orecchie grandi (animabili)
ear_local = ellipsoid((0.17, 0.065, 0.38), (0, 0, 0.34))
ear_in_local = ear_local.offset(0.014).intersect(ellipsoid((0.11, 0.1, 0.27), (0, -0.06, 0.38)))


def place_ear(shape, sx):
    s = shape.rot(-10, 0, 0).rot(0, 0, 20).rot(0, 55, 0).translate((0.4, -0.32, 2.5))
    return s if sx > 0 else s.mirrored()


for sx, nm in ((1, "EarR"), (-1, "EarL")):
    pivot = (sx * 0.42, -0.32, 2.52)
    m.add(nm, place_ear(ear_local, sx), FAWN, role="skin", tris=800, voxel=0.016, group=nm, pivot=pivot)
    m.add(nm + "In", place_ear(ear_in_local, sx), EAR_IN, role="detail", tris=400, voxel=0.013, group=nm,
          pivot=pivot)

# ------------------------------------------------------------------ faccia
eye_shape = ellipsoid((0.15, 0.09, 0.2))
eye_frames = [Frame(head, HEAD_C, (0.6 * sx, -1.0, 0.22), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in eye_frames]), EYE, role="eye", tris=900, voxel=0.013)
shines = []
for f in eye_frames:
    shines.append(f.place(sphere(0.06), (-0.052, -0.075, 0.075)))
    shines.append(f.place(sphere(0.031), (0.058, -0.07, -0.085)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=450, voxel=0.01)

nose = union(ellipsoid((0.09, 0.06, 0.06), (0, 0, 0.012)), ellipsoid((0.05, 0.05, 0.045), (0, -0.005, -0.03)), k=0.04)
m.add("Nose", Frame(painted, (0, -0.9, 2.0), (0, -1.0, 0.35), sink=0.03).place(nose), NOSE, role="detail", tris=400,
      voxel=0.011, reflectance=0.08)

blush = ellipsoid((0.13, 0.035, 0.08))
m.add("Blush", union(*[stick(blush, painted, HEAD_C, (0.66 * sx, -0.85, -0.32), sink=0.015) for sx in (1, -1)]),
      BLUSH, role="detail", tris=350, voxel=0.013)

smile = project_curve(painted, bezier((-0.11, -1.3, 1.9), (-0.05, -1.3, 1.85), (0.05, -1.3, 1.85),
                                      (0.11, -1.3, 1.9), 12), (0, -1, 0), inset=0.008)
m.add("Mouth", tube(smile, 0.02), MOUTH, role="detail", tris=400, voxel=0.01)

# zampe piu' corte: abbassa tutto tranne gli zoccoli (le zampe sono gia' state accorciate di DROP); scala a ~3
S = 1.04
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
