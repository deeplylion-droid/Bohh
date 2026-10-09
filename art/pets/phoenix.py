"""Fenice (Phoenix) - pet Leggendario, volante."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import SDF, Frame, bezier, capsule, ellipsoid, round_cone, sphere, stick, tube, union  # noqa: E402
from lib.toy import Model  # noqa: E402

BODY = (236, 72, 40)
BELLY = (255, 198, 72)
WING = (204, 38, 46)
FLAME = (255, 84, 20)
FLAME_IN = (255, 206, 56)
GOLD = (255, 178, 36)
EYE = (30, 20, 26)
WHITE = (255, 255, 255)
BLUSH = (255, 142, 166)


def flatten(shape: SDF, s: float, axis: int = 1) -> SDF:
    """Schiaccia (s<1) o allunga (s>1) la forma lungo un asse locale, mantenendo la distanza <= reale."""
    def f(p):
        q = p.copy()
        q[:, axis] = q[:, axis] / s
        return shape(q) * min(s, 1.0)

    lo = shape.lo.copy()
    hi = shape.hi.copy()
    lo[axis] *= s
    hi[axis] *= s
    return SDF(f, lo, hi)


def tongue(p0, p1, p2, p3, r_base, r_peak, r_tip, peak=0.25, n=16):
    """Lingua di fiamma lungo una bezier: si allarga fino a 'peak' e poi si assottiglia in punta."""
    pts = bezier(p0, p1, p2, p3, n)
    radii = []
    for i in range(n + 1):
        t = i / n
        if t < peak:
            u = t / peak
            radii.append(r_base + (r_peak - r_base) * math.sin(u * math.pi / 2))
        else:
            u = (t - peak) / (1 - peak)
            radii.append(r_tip + (r_peak - r_tip) * (1 - u) ** 1.25)
    return tube(pts, radii)


def shrink_path(path, frac):
    """Bezier accorciata: l'ultimo punto di controllo avvicinato al penultimo."""
    p0, p1, p2, p3 = path
    return p0, p1, p2, tuple(frac * a + (1 - frac) * b for a, b in zip(p3, p2))


m = Model("Phoenix", "pet")

# ------------------------------------------------------------------ corpo
HEAD_C = (0, -0.08, 1.95)
body = ellipsoid((0.96, 0.9, 0.82), (0, 0.06, 0.9))
head = ellipsoid((0.88, 0.82, 0.8), HEAD_C)
core = union(body, head, k=0.4)
m.add("Body", core, BODY, tris=4600, voxel=0.025)

# pancia dorata con bordo superiore a piume (smerlato)
belly_region = union(ellipsoid((0.64, 0.7, 0.52), (0, -0.66, 0.78)),
                     *[sphere(0.15, (x, -0.8, z)) for x, z in ((-0.44, 1.08), (-0.22, 1.2), (0.0, 1.24), (0.22, 1.2), (0.44, 1.08))],
                     k=0.04)
m.add("Belly", core.offset(0.022).intersect(belly_region), BELLY, role="detail", tris=1300)

# ------------------------------------------------------------------ fiamme: cresta + coda
CREST_BASE = (0, -0.02, 2.6)
crest_front = [  # bezier locali nel piano XZ, raggi base/picco/punta
    (((0, 0, 0), (0.16, 0, 0.32), (-0.16, 0, 0.6), (0.06, 0, 0.98)), 0.17, 0.22, 0.03),
    (((0.2, 0, -0.06), (0.38, 0, 0.14), (0.38, 0, 0.36), (0.58, 0, 0.62)), 0.13, 0.16, 0.025),
    (((-0.2, 0, -0.06), (-0.36, 0, 0.16), (-0.44, 0, 0.34), (-0.56, 0, 0.66)), 0.13, 0.16, 0.025),
]
crest_back = [
    (((0.12, 0, 0), (0.24, 0, 0.26), (0.1, 0, 0.46), (0.3, 0, 0.72)), 0.14, 0.17, 0.025),
    (((-0.12, 0, 0), (-0.26, 0, 0.24), (-0.12, 0, 0.44), (-0.32, 0, 0.7)), 0.14, 0.17, 0.025),
]


def place_crest(shape, back=0.0):
    return shape.rot(-20 - back * 60, 0, 0).translate((CREST_BASE[0], CREST_BASE[1] + back, CREST_BASE[2] - back * 0.25))


crest_out, crest_in = [], []
for rows, back in ((crest_front, 0.0), (crest_back, 0.24)):
    for path, rb, rp, rt in rows:
        crest_out.append(place_crest(flatten(tongue(*path, rb, rp, rt, peak=0.22), 0.6), back))
        crest_in.append(place_crest(flatten(tongue(*shrink_path(path, 0.5), rb * 0.45, rp * 0.45, 0.02, peak=0.22), 3.0), back))

# coda: tre lunghe piume di fuoco che scendono all'indietro e si arricciano verso l'alto
PLUME = ((0, 0, 0), (0.7, 0, -0.28), (1.38, 0, 0.16), (1.02, 0, 1.68))
LICK = ((1.16, 0, 0.66), (1.34, 0, 0.74), (1.46, 0, 0.92), (1.58, 0, 1.12))


def plume(scale, heading, lift, base):
    sc = lambda path: tuple((x * scale, y, z * scale) for x, y, z in path)  # noqa: E731
    p, lk = sc(PLUME), sc(LICK)
    outer = union(tongue(*p, 0.09, 0.28 * scale, 0.03, peak=0.6, n=20),
                  tongue(*lk, 0.1 * scale, 0.11 * scale, 0.02, peak=0.2, n=8), k=0.06)
    inner = union(tongue(*shrink_path(p, 0.45), 0.02, 0.14 * scale, 0.02, peak=0.6, n=20),
                  tongue(*shrink_path(lk, 0.5), 0.04, 0.05, 0.02, peak=0.2, n=8), k=0.04)
    tf = lambda s: s.rot(0, -lift, 0).rot(0, 0, 90 - heading).translate(base)  # noqa: E731
    return tf(flatten(outer, 0.5)), tf(flatten(inner, 3.0))


plumes = [plume(1.0, 0, 6, (0, 0.6, 0.86)), plume(0.92, 58, 16, (0.16, 0.58, 0.88)),
          plume(0.92, -58, 16, (-0.16, 0.58, 0.88))]
flames = union(*crest_out, *[p[0] for p in plumes], k=0.0)
m.add("Flames", flames, FLAME, material="Neon", role="glow", tris=2600, voxel=0.02)
flame_core = flames.offset(0.018).intersect(union(*crest_in, *[p[1] for p in plumes]))
m.add("FlameCore", flame_core, FLAME_IN, material="Neon", role="glow", tris=1400, voxel=0.016)

# ------------------------------------------------------------------ ali (animabili) con penne di fuoco
FEATHERS = [  # punta della penna (x fuori, z su), raggio alla radice
    ((1.08, 0, 0.34), 0.13), ((1.02, 0, 0.08), 0.13), ((0.9, 0, -0.15), 0.12), ((0.72, 0, -0.33), 0.11),
    ((0.5, 0, -0.43), 0.1)]
wing_local = union(
    ellipsoid((0.44, 0.17, 0.27), (0.34, 0, 0.0)),
    *[tongue((0.18, 0, 0.0), (0.5, 0, 0.05 + 0.4 * tz), (0.8 * tx, 0, 0.9 * tz + 0.06), (tx, 0, tz), r, r * 1.08, 0.03,
             peak=0.3, n=12) for (tx, _, tz), r in FEATHERS],
    k=0.06)
wing_local = flatten(wing_local, 0.48).scale(1.14)
tip_region_local = union(*[sphere(0.26, (tx * 1.04, 0, tz * 1.04)) for (tx, _, tz), _r in FEATHERS], k=0.06).scale(1.14)
SHOULDER = (0.74, 0.18, 1.38)


def place_wing(s, sx):
    s = s.rot(0, -24, 0).rot(0, 0, 16).translate(SHOULDER)
    return s if sx > 0 else s.mirrored()


for sx, nm in ((1, "WingR"), (-1, "WingL")):
    piv = (sx * SHOULDER[0], SHOULDER[1], SHOULDER[2])
    m.add(nm, place_wing(wing_local, sx), WING, role="detail", tris=900, voxel=0.018, group=nm, pivot=piv)
    tips = place_wing(wing_local.offset(0.018).intersect(tip_region_local), sx)
    m.add(nm + "Fire", tips, FLAME, material="Neon", role="glow", tris=500, voxel=0.016, group=nm, pivot=piv)

# ------------------------------------------------------------------ occhi, becco, guance, zampe
eye_shape = ellipsoid((0.17, 0.1, 0.22))
frames = [Frame(head, HEAD_C, (0.42 * sx, -1.0, 0.06), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in frames]), EYE, role="eye", tris=900, voxel=0.014)
shines = []
for f in frames:
    shines.append(f.place(sphere(0.066), (-0.055, -0.085, 0.085)))
    shines.append(f.place(sphere(0.034), (0.065, -0.08, -0.1)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=400, voxel=0.01)

blush = ellipsoid((0.16, 0.04, 0.09))
m.add("Blush", union(stick(blush, head, HEAD_C, (0.7, -0.85, -0.32), sink=0.02),
                     stick(blush, head, HEAD_C, (-0.7, -0.85, -0.32), sink=0.02)),
      BLUSH, role="detail", tris=400, voxel=0.014)

beak = union(ellipsoid((0.19, 0.17, 0.1), (0, -0.06, 0.04)), ellipsoid((0.14, 0.12, 0.075), (0, -0.03, -0.08)), k=0.04)
beak = stick(beak, head, HEAD_C, (0, -1.0, -0.16), sink=0.07)


def foot(x):
    toes = [capsule((x, -0.24, 0.07), (x + dx, -0.56, 0.06), 0.07) for dx in (-0.15, 0.0, 0.15)]
    return union(*toes, sphere(0.12, (x, -0.22, 0.1)), k=0.07)


m.add("Gold", union(beak, foot(0.34), foot(-0.34)), GOLD, role="detail", tris=1200, voxel=0.016)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
