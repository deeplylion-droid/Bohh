"""Vulcano Spaghettone - pet Divino (creatura meme originale).

Un vulcanetto fatto di spaghetti: un cono avvolto da tanti spaghetti, un cratere che trabocca di
sugo di pomodoro incandescente con due polpette, una faccina sul davanti e una forchetta
d'argento piantata nel fianco con gli spaghetti arrotolati.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, box, capsule, ellipsoid, project, revolve, round_cone,  # noqa: E402
                     smin, sphere, torus, tube, union)
from lib.toy import Model  # noqa: E402

PASTA_DEEP = (246, 198, 96)
PASTA = (255, 234, 150)
LAVA = (255, 66, 22)
LAVA_CORE = (255, 172, 40)
MEATBALL = (128, 66, 42)
BASIL = (56, 172, 64)
FORK = (190, 198, 212)
EYE = (30, 22, 30)
WHITE = (255, 255, 255)
BLUSH = (255, 112, 120)
MOUTH = (110, 24, 34)
TONGUE = (255, 116, 128)

m = Model("VulcanoSpaghettone", "pet")


# ---------------------------------------------------------------- helper locali
def seg2(x, z, a, b, r):
    px, pz = x - a[0], z - a[1]
    ex, ez = b[0] - a[0], b[1] - a[1]
    t = np.clip((px * ex + pz * ez) / (ex * ex + ez * ez + 1e-12), 0.0, 1.0)
    dx, dz = px - ex * t, pz - ez * t
    return np.sqrt(dx * dx + dz * dz) - r


def circ2(x, z, c, r):
    return np.sqrt((x - c[0]) ** 2 + (z - c[1]) ** 2) - r


def stencil(fn2d, xr, zr, depth=0.35):
    """Estrude una forma 2D fn2d(x, z) lungo l'asse locale Y (decalcomania da Frame.place)."""
    def f(p):
        return np.maximum(fn2d(p[:, 0], p[:, 2]), np.abs(p[:, 1]) - depth)
    return SDF(f, (xr[0], -depth, zr[0]), (xr[1], depth, zr[1]))


def drip(length, w):
    def fn(x, z):
        bar = seg2(x, z, (0, 0.2), (0, -length), w)
        return smin(bar, circ2(x, z, (0, -length - w * 0.2), w * 1.4), 0.07)
    return stencil(fn, (-w * 2.2, w * 2.2), (-length - w * 2.2, 0.35))


def leaf(L, W, T, fold=0.35):
    c = W * 0.5
    A = L * 0.577
    t = T / 0.866
    flat = ellipsoid((t, A, W), (0, -L * 0.5, c)).intersect(ellipsoid((t, A, W), (0, -L * 0.5, -c)))

    def fold_pts(p):
        q = p.copy()
        q[:, 0] = q[:, 0] + fold * np.abs(q[:, 2])
        return q
    return flat.warp(fold_pts, pad=fold * W * 0.6)


def basis(d, hint=(0.0, 0.0, 1.0)):
    """Matrice con colonne (x, y, z): z = d, x perpendicolare a d e a hint."""
    z = np.asarray(d, dtype=np.float64)
    z /= np.linalg.norm(z)
    x = np.cross(np.asarray(hint, dtype=np.float64), z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1).astype(np.float32)


# ---------------------------------------------------------------- cono
H = 2.4


def cone_r(z):
    t = np.clip(z / H, 0.0, 1.0)
    return 1.12 - 0.6 * t + 0.07 * np.sin(math.pi * t)


def profile(z):
    rb = 0.16
    base = cone_r(z)
    zz = np.clip(z, 0.0, rb)
    return base - rb + np.sqrt(np.maximum(rb * rb - (rb - zz) ** 2, 0.0))


cone = revolve(profile, 1.12, 0.0, H)
cone = union(cone, torus(0.46, 0.12, (0, 0, H)), k=0.1)
cone = cone.subtract(ellipsoid((0.4, 0.4, 0.28), (0, 0, H + 0.15)), k=0.08)
feet = union(*[ellipsoid((0.24, 0.3, 0.15), (sx * 0.42, -0.98, 0.15)) for sx in (1, -1)])
body = union(cone, feet, k=0.08)
m.add("Body", body, PASTA_DEEP, tris=3600)

# ---------------------------------------------------------------- spaghetti avvolti
FACE_C = np.array(project(body, (0, 0, 1.2), (0, -1, 0))[0])
face_window = ellipsoid((0.64, 0.6, 0.56), FACE_C + np.array([0, 0.05, 0.02]))
R_STRAND = 0.066
rng = np.random.default_rng(3)
LOOPS = []
for i, h in enumerate(np.linspace(0.24, 2.3, 14)):
    a = rng.uniform(0.04, 0.17) * (1 if i % 2 else -1)
    LOOPS.append((h + rng.uniform(-0.03, 0.03), a, rng.uniform(0, 2 * math.pi), rng.uniform(0.02, 0.05),
                  rng.uniform(0, 2 * math.pi), R_STRAND * rng.uniform(0.3, 0.6)))


def loops_fn(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    rho = np.sqrt(x * x + y * y)
    th = np.arctan2(y, x)
    d = np.full(len(p), 1e3, dtype=np.float32)
    for h, a, psi, b, chi, off in LOOPS:
        zc = h + a * np.sin(th + psi) + b * np.sin(3 * th + chi)
        rc = cone_r(zc) + off
        d = np.minimum(d, np.sqrt((rho - rc) ** 2 + ((z - zc) * 0.97) ** 2) - R_STRAND)
    return d


loops = SDF(loops_fn, (-1.3, -1.3, 0.0), (1.3, 1.3, H + 0.2)).subtract(face_window, k=0.05)

# forchetta d'argento piantata nel fianco destro (manico dentro), con una forchettata di spaghetti sui rebbi
F_ENTRY = np.array(project(body, (0, 0, 1.38), (1.0, 0.12, 0.0))[0])
F_DIR = np.array([0.78, -0.05, 0.62])
F_DIR /= np.linalg.norm(F_DIR)
VIEW = np.array([0.62, -1.0, 0.42])
FM = basis(F_DIR, hint=VIEW)
handle = box((0.085, 0.04, 0.42), (0, 0, -0.08), round=0.036)
neck = capsule((0, 0, 0.3), (0, 0, 0.56), 0.05)
head_ = round_cone((0, 0, 0.56), (0, 0, 0.66), 0.06, 0.06)
head_ = union(head_, box((0.165, 0.036, 0.07), (0, 0, 0.66), round=0.03), k=0.06)
tines = union(*[round_cone((tx, 0, 0.68), (tx * 1.05, 0, 1.06), 0.033, 0.026) for tx in (-0.125, -0.042, 0.042, 0.125)])
fork_local = union(handle, neck, head_, tines, k=0.03)
fork = fork_local.rotate(FM).translate(F_ENTRY)
m.add("Fork", fork, FORK, material="Metal", role="detail", tris=900, voxel=0.012)

twirl_pts = []
for i in range(49):
    t = i / 48
    ang = t * 2 * math.pi * 3.2
    rr = 0.2 + 0.035 * math.sin(t * math.pi)
    twirl_pts.append(FM @ np.array([rr * math.cos(ang), rr * math.sin(ang), 0.62 + 0.24 * t]) + F_ENTRY)
twirl = tube(twirl_pts, 0.056)
p_last = twirl_pts[-1]
dangle = tube(bezier(tuple(p_last), tuple(p_last + np.array([0.12, -0.12, -0.05])),
                     tuple(p_last + np.array([0.2, -0.16, -0.35])), tuple(p_last + np.array([0.12, -0.14, -0.62])), 12),
              [0.056] * 12 + [0.064])
p0 = twirl_pts[0]
tail_in = tube(bezier(tuple(p0), tuple(p0 + np.array([-0.1, -0.14, -0.12])),
                      tuple(p0 + np.array([-0.26, -0.2, -0.2])), tuple(F_ENTRY + np.array([-0.06, -0.3, -0.28])), 10), 0.056)
strands = union(loops, twirl, tail_in, dangle)
m.add("Strands", strands, PASTA, role="detail", tris=5800, voxel=0.02)
surf = union(body, loops)  # la lava cola solo sul cono, non sulla forchettata

# ---------------------------------------------------------------- lava di sugo che trabocca dal cratere
pool = ellipsoid((0.57, 0.57, 0.15), (0, 0, H + 0.08))
drips = []
for ang, L, w in [(-80, 0.55, 0.11), (-118, 0.32, 0.1), (-42, 0.4, 0.1), (42, 0.3, 0.09),
                  (80, 0.5, 0.11), (130, 0.42, 0.1), (175, 0.7, 0.12), (220, 0.36, 0.1), (262, 0.5, 0.11)]:
    a = math.radians(ang)
    f = Frame(surf, (0, 0, H - 0.25), (math.cos(a), math.sin(a), 0.42))
    drips.append(f.place(drip(L, w), (0, 0, 0.0)))
lava = union(pool, surf.offset(0.035).intersect(union(*drips)), k=0.04)
m.add("Lava", lava, LAVA, material="Neon", role="glow", tris=1500)
bubbles = [((0.02, -0.4, H + 0.13), 0.1), ((0.17, -0.33, H + 0.16), 0.06), ((-0.36, -0.24, H + 0.12), 0.085),
           ((0.4, -0.14, H + 0.11), 0.07), ((-0.12, 0.42, H + 0.13), 0.08), ((0.33, 0.33, H + 0.12), 0.065)]
core_glow = union(*[sphere(r, c) for c, r in bubbles])
m.add("LavaCore", core_glow, LAVA_CORE, material="Neon", role="glow", tris=500, voxel=0.015)

# due polpette nel sugo, con un po' di basilico
MB = [((0.17, 0.1, H + 0.21), 0.23), ((-0.2, -0.03, H + 0.19), 0.21)]


def meat_fn(p):
    d = np.full(len(p), 1e3, dtype=np.float32)
    for c, r in MB:
        q = p - np.array(c, dtype=np.float32)
        bumps = 0.012 * (np.sin(19 * q[:, 0] + 1.0) * np.sin(17 * q[:, 1] + 2.0) * np.sin(23 * q[:, 2]))
        d = np.minimum(d, np.sqrt(np.einsum("ij,ij->i", q, q)) - r + bumps)
    return d


meatballs = SDF(meat_fn, (-0.6, -0.4, H - 0.1), (0.55, 0.45, H + 0.55))
m.add("Meatballs", meatballs, MEATBALL, role="detail", tris=1000, voxel=0.015)
leaves = []
for c, r in MB[:1]:
    top = np.array(c) + np.array([0, 0, r])
    for yaw, tilt in ((30, -18), (-75, -12)):
        lf = leaf(0.32, 0.2, 0.026).rot(0, 90, 0).rot(tilt, 0, 0).rot(0, 0, yaw)
        leaves.append(lf.translate(top + np.array([0, 0, -0.035])))
m.add("Basil", union(*leaves), BASIL, role="detail", tris=400, voxel=0.012)

# ---------------------------------------------------------------- faccina
FC = (0.0, 0.0, 1.25)
eye_shape = ellipsoid((0.16, 0.1, 0.21))
eye_frames = [Frame(body, FC, (0.4 * sx, -1.0, 0.12), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in eye_frames]), EYE, role="eye", tris=700, voxel=0.014)
shines = []
for f in eye_frames:
    shines.append(f.place(sphere(0.062), (-0.05, -0.085, 0.08)))
    shines.append(f.place(sphere(0.031), (0.06, -0.08, -0.095)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=400, voxel=0.01)
blush = ellipsoid((0.13, 0.04, 0.08))
m.add("Blush", union(*[Frame(body, FC, (0.7 * sx, -1.0, -0.22), sink=0.018).place(blush) for sx in (1, -1)]),
      BLUSH, role="detail", tris=400, voxel=0.013)

mouth_f = Frame(body, FC, (0.0, -1.0, -0.33))
MA, MBB, MC = 0.2, 0.15, 0.06


def mouth_2d(x, z):
    ell = np.sqrt((x / MA) ** 2 + (z / MBB) ** 2) - 1.0
    return np.maximum(ell * 0.12, z - MC * (x / MA) ** 2)


m.add("Mouth", body.offset(0.014).intersect(mouth_f.place(stencil(mouth_2d, (-0.3, 0.3), (-0.22, 0.12), 0.3))),
      MOUTH, role="detail", tris=400, voxel=0.012)
tongue_2d = lambda x, z: np.maximum(circ2(x, z, (0.0, -0.15), 0.1), mouth_2d(x, z))  # noqa: E731
m.add("Tongue", body.offset(0.024).intersect(mouth_f.place(stencil(tongue_2d, (-0.2, 0.2), (-0.3, 0.0), 0.3))),
      TONGUE, role="detail", tris=300, voxel=0.012)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
