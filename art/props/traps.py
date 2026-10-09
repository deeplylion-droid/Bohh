"""Trappole da piazzare nella base (kind "prop"): appoggiate al pavimento, origine al centro a terra
(z = 0), larghe ~3.4, il lato "bello" guarda verso -Y.

  TrapBananaPeel   buccia di banana aperta a terra: 4 lembi gialli con le punte marroni
  TrapSlimePuddle  pozza di melma verde lucida e un po' trasparente, con bolle e schizzi
  TrapBearTrap     tagliola da cartone animato: ganasce di metallo aperte con i denti, piatto rosso al centro

Uso: python props/traps.py [Nome ...]
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.sdf import SDF, bezier, box, cylinder, ellipsoid, prism, sphere, torus, tube, union  # noqa: E402
from propkit import FineModel, paint, run, unit  # noqa: E402

WHITE = (255, 255, 255)


def above_ground(z0: float = 0.0) -> SDF:
    """Semispazio z >= z0 (base piatta sul pavimento)."""
    return SDF(lambda p: z0 - p[:, 2], (-50, -50, z0), (50, 50, 50))


# ================================================================================ TrapBananaPeel

def flap_sdf(length: float, width: float, thick: float, rise: float, curl: float, trough: float, r: float = 0.04):
    """Lembo di buccia lungo +X (da 0 a length): appuntito in fondo, scende dal centro al pavimento e
    arriccia la punta verso l'alto. Ritorna (sdf, funzione quota del piano medio)."""

    def mid(u, v):
        t = np.clip(u / length, 0, 1)
        h = rise * np.clip(1 - t / 0.38, 0, 1) ** 2 + curl * np.clip((t - 0.72) / 0.28, 0, 1) ** 2
        return thick * 0.5 + h + trough * v * v

    def f(p):
        u, v, z = p[:, 0], p[:, 1], p[:, 2]
        t = np.clip(u / length, 0, 1)
        w = width * 0.5 * np.clip(np.sin(math.pi * np.clip(0.12 + 0.88 * t, 0, 1)) ** 0.75, 0.05, 1)
        dz = np.abs(z - mid(u, v)) - (thick * 0.5 - r)
        dv = np.abs(v) - (w - r)
        cross = np.sqrt(np.maximum(dz, 0) ** 2 + np.maximum(dv, 0) ** 2) + np.minimum(np.maximum(dz, dv), 0) - r
        du = np.maximum(-u, u - length)
        return np.maximum(cross * 0.8, du)

    return SDF(f, (-0.1, -width, -0.1), (length + 0.1, width, rise + curl + thick + 0.3)), mid


def banana_peel() -> FineModel:
    m = FineModel("TrapBananaPeel", "prop", voxel=0.014)
    yellow, cream, brown = (255, 214, 36), (255, 242, 196), (116, 72, 30)
    flaps, unders, tips = [], [], []
    specs = [(18, 1.58, 0.72), (108, 1.48, 0.68), (196, 1.6, 0.7), (284, 1.46, 0.66)]
    for k, (ang, ln, wd) in enumerate(specs):
        sdf, mid = flap_sdf(ln, wd, 0.14, 0.42, 0.13 + 0.03 * (k % 2), 0.3)
        rot = dict(rz=ang)
        flap = sdf.translate((0.12, 0, 0)).rot(**rot)
        flaps.append(flap)
        # meta' inferiore del lembo (lato interno color crema), visibile sui bordi e sulla punta arricciata
        below = SDF(lambda p, mid=mid: p[:, 2] - mid(p[:, 0] - 0.12, p[:, 1]) * 1.0 + 0.0, (-0.1, -1, -0.2), (2, 1, 1.2))
        unders.append(sdf.translate((0.12, 0, 0)).intersect(below).rot(**rot))
        tip = np.array((0.12 + ln * 1.0, 0.0, 0.14))
        tips.append(sphere(0.26, tuple(tip)).rot(**rot))
    center = ellipsoid((0.42, 0.42, 0.36), (0, 0, 0.26))
    stem = tube(bezier((0, 0, 0.4), (0.0, 0.0, 0.75), (0.08, -0.05, 0.92), (0.2, -0.08, 1.0), 8),
                [0.16, 0.15, 0.14, 0.13, 0.125, 0.12, 0.12, 0.12, 0.12])
    peel = union(union(*flaps, k=0.12), center, k=0.18)
    peel = union(peel, stem, k=0.1).intersect(above_ground())
    m.add("Peel", peel, yellow, tris=1700)
    m.add("Inner", peel.offset(0.008).intersect(union(*unders)), cream, role="detail", tris=500, voxel=0.012)
    # punte marroni, estremita' del gambo e qualche macchiolina da banana matura
    stem_end = sphere(0.17, (0.21, -0.08, 1.02))
    rng = np.random.default_rng(3)
    dots = []
    for k, (ang, ln, wd) in enumerate(specs):
        for j in range(2):
            u = rng.uniform(0.35, 0.7) * ln + 0.12
            v = rng.uniform(-0.12, 0.12)
            a = math.radians(ang)
            x, y = u * math.cos(a) - v * math.sin(a), u * math.sin(a) + v * math.cos(a)
            dots.append(sphere(rng.uniform(0.045, 0.07), (x, y, 0.16)))
    brown_bits = union(*tips, stem_end)
    m.add("Tips", union(paint(peel, brown_bits, t=0.012, depth=0.05), paint(peel, union(*dots), t=0.01, depth=0.03)),
          brown, role="detail", tris=700, voxel=0.01)
    return m


# ================================================================================ TrapSlimePuddle

def slime_puddle() -> FineModel:
    m = FineModel("TrapSlimePuddle", "prop", voxel=0.018)
    green, light, dark = (104, 214, 56), (176, 246, 120), (60, 150, 40)
    rng = np.random.default_rng(12)
    blobs = [ellipsoid((1.15, 1.0, 0.3), (0.0, 0.0, 0.0))]
    for k in range(9):
        a = 2 * math.pi * k / 9 + rng.uniform(-0.2, 0.2)
        rr = rng.uniform(0.75, 1.15)
        s = rng.uniform(0.38, 0.6)
        blobs.append(ellipsoid((s, s * rng.uniform(0.8, 1.1), 0.22), (rr * math.cos(a), rr * math.sin(a), 0.0)))
    puddle = union(*blobs, k=0.35)
    mound = ellipsoid((0.7, 0.6, 0.42), (0.15, 0.1, 0.0))  # "goccia" piu' alta al centro
    puddle = union(puddle, mound, k=0.3)
    # schizzi staccati attorno alla pozza
    drops = []
    for a, rr, s in ((0.4, 1.78, 0.17), (1.9, 1.72, 0.13), (2.9, 1.62, 0.15), (4.3, 1.7, 0.12), (5.4, 1.66, 0.16)):
        drops.append(ellipsoid((s, s * 0.85, s * 0.65), (rr * math.cos(a), rr * math.sin(a), 0.0)))
    slime = union(puddle, *drops).intersect(above_ground())
    m.add("Slime", slime, green, tris=1500, transparency=0.15, reflectance=0.15)
    # bolle (calotte) sulla superficie, alcune scoppiate (anelli)
    bubbles, rings = [], []
    for x, y, r in ((0.2, 0.15, 0.2), (-0.55, 0.35, 0.14), (0.62, -0.42, 0.16), (-0.25, -0.55, 0.11), (0.85, 0.5, 0.1),
                    (-0.9, -0.15, 0.12), (0.35, 0.7, 0.09)):
        top = float(slime(np.array([[x, y, 1.0]], dtype=np.float32))[0])
        zs = 1.0 - top  # quota della superficie in (x, y)
        bubbles.append(sphere(r, (x, y, zs - r * 0.35)))
    for x, y, r in ((-0.35, 0.05, 0.1), (0.45, 0.2, 0.08)):
        top = float(slime(np.array([[x, y, 1.0]], dtype=np.float32))[0])
        rings.append(torus(r, 0.028, (x, y, 1.0 - top)))
    m.add("Bubbles", union(*bubbles, *rings).intersect(above_ground(0.05)), light, role="detail", tris=700,
          transparency=0.1, reflectance=0.2, voxel=0.012)
    # riflessi bianchi lucidi
    shines = []
    for x, y, r in ((0.05, -0.15, 0.11), (-0.62, 0.18, 0.07), (0.45, 0.52, 0.06), (0.18, 0.28, 0.05)):
        top = float(slime(np.array([[x, y, 1.0]], dtype=np.float32))[0])
        shines.append(ellipsoid((r * 1.6, r, r * 0.4), (x, y, 1.0 - top + 0.01)))
    m.add("Shine", union(*shines).intersect(slime.offset(0.03)), WHITE, role="shine", tris=200, voxel=0.01)
    # chiazze piu' scure (profondita')
    spots = union(ellipsoid((0.4, 0.3, 0.5), (-0.6, -0.5, 0.0)), ellipsoid((0.35, 0.25, 0.5), (0.9, -0.1, 0.0)),
                  ellipsoid((0.3, 0.3, 0.5), (-0.2, 0.75, 0.0)))
    m.add("Goo", paint(slime, spots, t=0.01, depth=0.03), dark, role="detail", tris=400, transparency=0.1,
          voxel=0.012)
    return m


# ================================================================================ TrapBearTrap

def half_ring(sx: int, R: float, half_w: float, half_h: float, z: float, rnd: float = 0.025) -> SDF:
    """Mezzo anello piatto (sezione rettangolare arrotondata) dal lato y*sx >= 0."""

    def f(p):
        x, y, zz = p[:, 0], p[:, 1], p[:, 2]
        rho = np.sqrt(x * x + y * y)
        dr = np.abs(rho - R) - (half_w - rnd)
        dz = np.abs(zz - z) - (half_h - rnd)
        d = np.sqrt(np.maximum(dr, 0) ** 2 + np.maximum(dz, 0) ** 2) + np.minimum(np.maximum(dr, dz), 0) - rnd
        return np.maximum(d, -y * sx)

    e = R + half_w + 0.05
    return SDF(f, (-e, -e if sx < 0 else -0.05, z - half_h - 0.05), (e, e if sx > 0 else 0.05, z + half_h + 0.05))


def bear_trap() -> FineModel:
    m = FineModel("TrapBearTrap", "prop", voxel=0.014)
    steel, dark_steel, red, brass = (156, 162, 172), (92, 98, 110), (222, 36, 42), (230, 180, 70)
    R, zj = 1.0, 0.17  # raggio delle ganasce e quota delle cerniere
    jaws = []
    for sx in (1, -1):
        ring = half_ring(sx, R, 0.11, 0.07, zj)
        teeth = []
        for k in range(8):
            a = math.pi * (k + 0.5) / 8
            radial = np.array((math.cos(a), sx * math.sin(a), 0.0))
            side = np.cross(radial, (0, 0, 1))
            base = np.array((0, 0, zj + 0.05)) + radial * (R - 0.02)
            apex = base - radial * 0.06 + np.array((0, 0, 0.32))
            teeth.append(tooth(tuple(base + side * 0.115), tuple(base - side * 0.115), tuple(apex), 0.045))
        # ganascia aperta: ruotata attorno all'asse delle cerniere (asse X), il bordo esterno si alza un po'
        jaws.append(union(ring, union(*teeth), k=0.02).rot(sx * 16, 0, 0, pivot=(0, 0, zj)))
    m.add("Jaws", union(*jaws), steel, material="Metal", tris=1300, reflectance=0.1)
    # telaio: barra a croce sotto il piatto, cerniere, molle a balestra con anelli alle estremita'
    frame = [box((1.25, 0.1, 0.06), (0, 0, 0.07), round=0.03), box((0.1, 0.62, 0.05), (0, 0, 0.06), round=0.03)]
    for sx in (1, -1):
        frame.append(cylinder((sx * R, -0.22, zj), (sx * R, 0.22, zj), 0.12, round=0.03))
        frame.append(tube([(sx * 1.08, 0.0, 0.15), (sx * 1.28, 0.0, 0.2), (sx * 1.42, 0.0, 0.19)], [0.085, 0.075, 0.07]))
        frame.append(torus(0.13, 0.055).rot(90, 0, 0).translate((sx * 1.47, 0.0, 0.2)))
    m.add("Frame", union(*frame).intersect(above_ground()), dark_steel, material="Metal", role="detail", tris=900)
    plate = cylinder((0, 0, 0.1), (0, 0, 0.25), 0.5, round=0.05)
    m.add("Plate", plate, red, role="detail", tris=400)
    rivets = [sphere(0.065, (sx * R, sy * 0.23, zj)) for sx in (1, -1) for sy in (1, -1)]
    rivets.append(torus(0.3, 0.032, (0, 0, 0.25)))
    m.add("Rivets", union(*rivets), brass, material="Metal", role="detail", tris=300)
    return m


def tooth(a, b, apex, r: float) -> SDF:
    """Dente triangolare (lama spessa 2r) dai due punti di base all'apice."""
    a, b, apex = (np.asarray(v, dtype=np.float64) for v in (a, b, apex))
    n = unit(np.cross(b - a, apex - a))
    poly = [(0.0, 0.0), (float(np.linalg.norm(b - a)), 0.0)]
    ex = unit(b - a)
    ey = np.cross(n, ex)
    q = apex - a
    poly.append((float(q @ ex), float(q @ ey)))
    tri = prism(poly, -r, r, round=0.012)
    mtx = np.stack([ex, ey, n], axis=1).astype(np.float32)
    return tri.rotate(mtx).translate(tuple(a))


CATALOG = {
    "TrapBananaPeel": banana_peel,
    "TrapSlimePuddle": slime_puddle,
    "TrapBearTrap": bear_trap,
}

if __name__ == "__main__":
    run(CATALOG)
