"""Unicorno (Unicorn) - pet Leggendario."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capsule, cylinder, ellipsoid, project, project_curve,  # noqa: E402
                     sphere, stick, tube, union)
from lib.toy import Model  # noqa: E402

WHITE_BODY = (250, 248, 255)
PINK_HOOF = (255, 186, 212)
BLUSH = (255, 140, 176)
GOLD = (255, 196, 64)
EYE = (40, 22, 60)
WHITE = (255, 255, 255)
MOUTH = (196, 92, 128)
MANE = [  # un colore per parte, dal ciuffo alla coda
    ("Pink", (255, 128, 184)),
    ("Orange", (255, 168, 76)),
    ("Yellow", (255, 226, 88)),
    ("Mint", (118, 228, 182)),
    ("Sky", (112, 196, 255)),
    ("Lilac", (188, 142, 255)),
]


def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def grad(sdf, p, eps=1e-3):
    g = np.zeros(3)
    for ax in range(3):
        e = np.zeros(3)
        e[ax] = eps
        g[ax] = sdf((p + e)[None, :].astype(np.float32))[0] - sdf((p - e)[None, :].astype(np.float32))[0]
    return g / max(np.linalg.norm(g), 1e-9)


def snap(points, sdf, target):
    """Porta i punti a distanza 'target' dalla superficie (ciocche che aderiscono al corpo)."""
    out = []
    for p in points:
        p = np.asarray(p, dtype=np.float64)
        for _ in range(4):
            d = float(sdf(p[None, :].astype(np.float32))[0])
            p = p - grad(sdf, p) * (d - target)
        out.append(tuple(p))
    return out


def lock_path(root, U, V, length, curl_r, turns=0.75, n_line=6, n_curl=10, sag=0.0):
    """Ciocca: tratto quasi dritto lungo U, poi ricciolo a spirale verso V."""
    root, U, V = np.asarray(root, float), norm(U), norm(V)
    V = norm(V - U * (V @ U))
    pts = [root + U * length * (i / n_line) + V * sag * math.sin(math.pi * i / n_line) for i in range(n_line + 1)]
    end = pts[-1]
    c = end + V * curl_r
    for j in range(1, n_curl + 1):
        a = j / n_curl * turns * 2 * math.pi
        r = curl_r * (1 - 0.45 * j / n_curl)
        pts.append(c + (-V * math.cos(a) + U * math.sin(a)) * r)
    return pts


def lock_radii(pts, r0, r_peak, r_tip, peak=0.25):
    seg = [0.0] + [float(np.linalg.norm(np.subtract(pts[i + 1], pts[i]))) for i in range(len(pts) - 1)]
    cum = np.cumsum(seg)
    out = []
    for s in cum / cum[-1]:
        if s < peak:
            out.append(r0 + (r_peak - r0) * math.sin(s / peak * math.pi / 2))
        else:
            u = (s - peak) / (1 - peak)
            out.append(r_tip + (r_peak - r_tip) * (1 - u) ** 1.1)
    return out


def twisted_horn(length, r_base, r_tip, lobes=2, turns=2.2, amp=0.2) -> SDF:
    """Corno a spirale (asse +Z da 0 a length): sezione a lobi che ruota salendo."""
    def f(p):
        rho = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2)
        th = np.arctan2(p[:, 1], p[:, 0])
        t = np.clip(p[:, 2] / length, 0.0, 1.0)
        R = r_base * (1 - t) + r_tip * t
        mod = 1.0 + amp * np.cos(lobes * (th - 2 * math.pi * turns * t))
        d_side = (rho - R * mod) * 0.6
        d_cap = np.maximum(-p[:, 2], p[:, 2] - length)
        a = np.maximum(d_side, 0)
        b = np.maximum(d_cap, 0)
        return np.minimum(np.maximum(d_side, d_cap), 0) + np.sqrt(a * a + b * b)

    e = r_base * (1 + amp)
    return SDF(f, (-e, -e, 0), (e, e, length))


m = Model("Unicorn", "pet")

# ------------------------------------------------------------------ corpo (testa grande, collo corto, zampe tozze)
HEAD_C = (0, -0.42, 1.9)
head = ellipsoid((0.72, 0.64, 0.62), HEAD_C)
MZ_C = (0, -0.99, 1.66)
muzzle = ellipsoid((0.45, 0.36, 0.32), MZ_C)
torso = ellipsoid((0.66, 0.8, 0.56), (0, 0.22, 0.84))
chest = ellipsoid((0.6, 0.5, 0.52), (0, -0.2, 0.92))
neck = capsule((0, -0.1, 1.12), (0, -0.3, 1.56), 0.36)
LEGS = [(sx * 0.33, y) for sx in (1, -1) for y in (-0.24, 0.62)]
legs = union(*[capsule((x, y, 0.74), (x * 1.06, y + 0.02, 0.22), 0.185) for x, y in LEGS])
EAR_C = [(sx * 0.38, -0.3, 2.48) for sx in (1, -1)]
ears = union(*[ellipsoid((0.135, 0.085, 0.24), (0, 0, 0)).rot(0, sx * 20, 0).translate(c) for sx, c in zip((1, -1), EAR_C)])
core = union(torso, chest, k=0.3)
core = union(core, neck, k=0.25)
core = union(core, head, k=0.25)
core = union(core, muzzle, k=0.18)
core = union(core, legs, k=0.12)
core = union(core, ears, k=0.06)
m.add("Body", core, WHITE_BODY, tris=5200, voxel=0.025)

# zoccoli rosa pastello e interno delle orecchie
hooves = union(*[cylinder((x * 1.06, y + 0.02, 0.0), (x * 1.06, y + 0.02, 0.21), 0.215, round=0.065) for x, y in LEGS])
ear_in = union(*[ellipsoid((0.075, 0.1, 0.16), (0, -0.07, -0.02)).rot(0, sx * 20, 0).translate(c) for sx, c in zip((1, -1), EAR_C)])
m.add("Hooves", union(hooves, core.offset(0.02).intersect(ear_in)), PINK_HOOF, role="detail", tris=1000, voxel=0.016)

# ------------------------------------------------------------------ corno d'oro a spirale
horn_base, horn_n = project(head, HEAD_C, (0, -0.62, 0.82))
horn = twisted_horn(0.76, 0.14, 0.018).rot(18, 0, 0).translate(horn_base - horn_n * 0.06)
m.add("Horn", horn, GOLD, role="detail", tris=1000, voxel=0.012)

# ------------------------------------------------------------------ criniera e coda arcobaleno
locks = {nm: [] for nm, _ in MANE}
NAMES = [nm for nm, _ in MANE]

# frangia: due ciocche che partono dietro il corno e ricadono ai lati sopra le orecchie
for nm, sx in (("Pink", 1), ("Orange", -1)):
    root = np.array([sx * 0.05, -0.5, 2.56])
    pts = snap(lock_path(root, (sx * 1.0, -0.35, -0.32), (0, -1.0, -0.7), 0.4, 0.12, turns=0.6, sag=0.04), core, 0.08)
    locks[nm].append(tube(pts, lock_radii(pts, 0.16, 0.18, 0.04)))

# criniera lungo il collo: radici sulla cresta, ciocche che ricadono ai due lati
crest = snap(bezier((0, -0.36, 2.58), (0, 0.0, 2.62), (0, 0.16, 2.16), (0, 0.24, 1.34), 40), core, 0.02)
roots_t = [0.1, 0.22, 0.36, 0.5, 0.64, 0.8, 0.95]
order = ["Yellow", "Mint", "Sky", "Lilac", "Pink", "Orange", "Yellow"]
for i, nm in enumerate(order):
    root = np.asarray(crest[int(roots_t[i] * (len(crest) - 1))])
    alt = 1 if i % 2 == 0 else -1
    for sx in (1, -1):
        U = (sx * 0.6, 0.1 + 0.1 * i, -0.8) if i < 2 else (sx * 0.78, 0.25 + 0.06 * i, -0.62)
        V = (0, alt * sx, 0.25 * alt)
        pts = snap(lock_path(root, U, V, ((0.7, 0.6)[i] if i < 2 else 0.3 + 0.025 * i), 0.14, turns=0.7), core, 0.075)
        locks[nm].append(tube(pts, lock_radii(pts, 0.17, 0.19, 0.04)))

# coda: sei grosse ciocche a cascata
TAIL_ROOT = np.array([0, 0.94, 1.02])
tail_dirs = [(0.15, 0.85, 0.3), (-0.22, 0.9, 0.0), (0.26, 0.8, -0.38), (-0.26, 0.7, -0.6), (0.14, 0.55, -0.85),
             (-0.12, 0.45, -0.92)]
for i, nm in enumerate(NAMES):
    U = norm(tail_dirs[i])
    root = TAIL_ROOT + np.array([0.05 * (1 if i % 2 else -1), 0, -0.03 * i])
    V = norm(np.cross(U, (1 if i % 2 else -1, 0, 0)))
    pts = lock_path(root, U, V, 0.42 + 0.04 * i, 0.17, turns=0.75)
    locks[nm].append(tube(pts, lock_radii(pts, 0.15, 0.2, 0.045, peak=0.2)))

for nm, col in MANE:
    m.add(nm, union(*locks[nm]), col, role="detail", tris=750, voxel=0.016)

# stelline magiche dipinte sui fianchi
from lib.sdf import prism, star_points  # noqa: E402
star = prism(star_points(5, 0.21, 0.092, rot_deg=180), -0.9, 0.9).rot(0, 90, 0)  # stella nel piano YZ, punta in alto
stars = star.translate((0, 0.46, 0.96))
m.add("Stars", core.offset(0.02).intersect(stars), (255, 214, 92), material="Neon", role="glow", tris=500, voxel=0.012)

# ------------------------------------------------------------------ occhi con ciglia lunghe
eye_shape = ellipsoid((0.165, 0.1, 0.225))
frames = [Frame(head, HEAD_C, (0.5 * sx, -1.0, 0.24), sink=0.05) for sx in (1, -1)]
eyes = [f.place(eye_shape) for f in frames]
lashes = []
for f, sx in zip(frames, (1, -1)):
    o = -sx  # lato esterno dell'occhio nell'asse X locale
    for phi, ln in ((18, 0.13), (42, 0.15), (66, 0.12)):
        a = math.radians(phi)
        p0 = np.array([o * 0.155 * math.cos(a), -0.02, 0.215 * math.sin(a)])
        d = np.array([o * math.cos(a + 0.3), 0, math.sin(a + 0.3)])
        p1 = p0 + d * ln * 0.55 + np.array([0, -0.02, 0])
        p2 = p0 + d * ln + np.array([0, -0.01, 0.05])
        lashes.append(f.place(tube([tuple(p0), tuple(p1), tuple(p2)], [0.026, 0.02, 0.011])))
m.add("Eyes", union(*eyes, *lashes), EYE, role="eye", tris=1100, voxel=0.011)
shines = []
for f in frames:
    shines.append(f.place(sphere(0.064), (-0.055, -0.085, 0.085)))
    shines.append(f.place(sphere(0.032), (0.062, -0.08, -0.1)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=400, voxel=0.01)

blush = ellipsoid((0.15, 0.04, 0.085))
m.add("Blush", union(*[stick(blush, head, HEAD_C, (sx * 0.78, -0.72, -0.3), sink=0.02) for sx in (1, -1)]),
      BLUSH, role="detail", tris=400, voxel=0.013)

# narici e sorriso sul muso
nostrils = union(*[Frame(muzzle, MZ_C, (sx * 0.4, -1.0, 0.3), sink=0.02).place(ellipsoid((0.045, 0.03, 0.03))) for sx in (1, -1)])
smile = project_curve(core, bezier((0.2, -1.2, 1.64), (0.09, -1.2, 1.54), (-0.09, -1.2, 1.54), (-0.2, -1.2, 1.64), 14),
                      (0, -1, 0), inset=0.008)
m.add("Mouth", union(nostrils, tube(smile, 0.026)), MOUTH, role="detail", tris=500, voxel=0.011)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
