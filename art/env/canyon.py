"""Zona Canyon (roccia rossa): mesa a strati, saguaro, cespuglio secco, masso rosso.

Uso: python env/canyon.py Mesa Cactus DryBush CanyonRock  (oppure "all")
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.sdf import SDF, ellipsoid, sphere, union  # noqa: E402
from common import (GROUND, Prop, cleaved_block, facet_blob, fast_union, ground, irregular_poly,  # noqa: E402
                    mesh_concat, mesh_tube, run, slab, surface_crack)

RUST = (170, 98, 64)     # arenaria rosso ruggine
OCHRE = (198, 140, 88)   # ocra
PALE = (216, 180, 134)   # arenaria chiara della cima


# ------------------------------------------------------------------------------ mesa

def mesa() -> Prop:
    """Pilastro di arenaria (~8): blocco unico spigoloso con fasce di strati, cima piatta, bordi
    scheggiati e qualche masso caduto ai piedi."""
    m = Prop("Mesa", voxel=0.035)
    main = cleaved_block((0, 0, 3.6), (2.1, 1.8, 3.8), seed=561, rot=(0, 0, 12), taper=0.06, tilt=4, chips=9, chip=(0.3, 0.7))
    side = cleaved_block((1.2, 0.85, 1.9), (1.35, 1.15, 2.1), seed=562, rot=(0, 0, 50), taper=0.12, tilt=4, chips=6, chip=(0.3, 0.7))
    talus = slab(irregular_poly(9, 2.9, 2.5, seed=563, jitter=0.12), GROUND, 0.75, bevel=0.6, bevel_bottom=0.0, seed=564, chips=4, chip_depth=0.3)
    body = union(main, side, talus).intersect(ground()).intersect(SDF(lambda p: p[:, 2] - 7.6 + 0.04 * p[:, 0], (-9, -9, -9), (9, 9, 7.8)))
    for args in [((0.3, 0, 3.4), (0.35, -1, 0), (0, 0, -1), 3.0, 581), ((0, 0, 6.0), (-1, -0.5, 0), (0.1, 0, -1), 2.0, 582),
                 ((0.5, 0.3, 2.0), (1, -0.4, 0), (0, 0.1, -1), 1.6, 583)]:
        inside, d, along, ln, sd = args
        body = body.subtract(surface_crack(body, inside, d, along, depth=0.3, width=0.08, length=ln, zigzag=4, seed=sd))
    boulders = union(cleaved_block((2.9, -1.3, 0.2), (0.55, 0.45, 0.45), seed=590, rot=(0, 12, 30), ridge=0.2, chips=4),
                     cleaved_block((-2.5, -2.1, 0.1), (0.4, 0.35, 0.3), seed=591, rot=(8, 0, -20), chips=4)).intersect(ground())
    m.add("Rock", union(body, boulders), RUST, tris=1150, smooth=False)

    def strata(p):  # fasce leggermente inclinate e ondulate, di spessore variabile
        th = np.arctan2(p[:, 1], p[:, 0])
        z = p[:, 2] - 0.05 * p[:, 0] + 0.03 * p[:, 1]
        bands = [(1.3, 0.38, 0.6), (3.0, 0.2, 1.9), (4.15, 0.5, 3.1), (5.85, 0.24, 4.4)]
        d = np.full(len(p), 9.0, dtype=np.float32)
        for zc, hh, ph in bands:
            wave = 0.1 * np.sin(2 * th + ph) + 0.05 * np.sin(5 * th + ph * 2)
            d = np.minimum(d, np.abs(z - zc - wave) - hh * (1 + 0.35 * np.sin(3 * th + ph)))
        return d

    m.add("Strata", body.offset(0.05).intersect(SDF(strata, (-9, -9, 0.7), (9, 9, 6.6))), OCHRE, role="detail", tris=750, smooth=False)
    m.add("Cap", body.offset(0.07).intersect(SDF(lambda p: 6.75 - 0.05 * p[:, 0] - p[:, 2], (-9, -9, 6.4), (9, 9, 9))), PALE,
          role="detail", tris=350, smooth=False)
    return m


# ------------------------------------------------------------------------------ saguaro

def ribbed_segment(a, b, ra: float, rb: float, ribs: int = 8, depth: float = 0.1) -> SDF:
    """Tratto di fusto di cactus da a a b con costolature longitudinali (scanalature a V)."""
    from lib.sdf import round_cone
    base = round_cone(a, b, ra, rb)
    a = np.asarray(a, dtype=np.float32)
    ax = np.asarray(b, dtype=np.float32) - a
    ax /= np.linalg.norm(ax)
    ref = np.array([1, 0, 0], dtype=np.float32) if abs(ax[0]) < 0.9 else np.array([0, 1, 0], dtype=np.float32)
    u = np.cross(ax, ref)
    u /= np.linalg.norm(u)
    w = np.cross(ax, u)
    rmax = max(ra, rb)

    def f(p):
        v = p - a
        phi = np.arctan2(v @ w, v @ u)
        groove = 0.5 - 0.5 * np.cos(ribs * phi)
        return base(p) + depth * rmax * groove

    return SDF(f, base.lo, base.hi)


def cactus() -> Prop:
    """Saguaro (~5) con due braccia e un fiore rosa in cima."""
    m = Prop("Cactus", voxel=0.03)
    trunk = ribbed_segment((0, 0, GROUND - 0.1), (0, 0, 4.25), 0.5, 0.44, ribs=9)
    arm_r = [  # attacco, gomito, punta, raggio
        ((0.3, 0, 1.65), (1.05, -0.05, 1.9), (1.12, -0.05, 3.25), 0.31),
        ((-0.3, 0.05, 2.25), (-0.92, 0.1, 2.45), (-0.98, 0.1, 3.45), 0.27),
    ]
    arms = []
    for s, e, t, r in arm_r:
        arms.append(ribbed_segment(s, e, r * 1.05, r, ribs=8))
        arms.append(ribbed_segment(e, t, r, r * 0.95, ribs=8))
    body = union(trunk, *arms, k=0.18).intersect(ground())
    m.add("Body", body, (84, 124, 72), tris=880, smooth=False)
    # fiore in cima: petali piatti attorno a un centro giallo
    top = np.array([0.0, 0.0, 4.25 + 0.42])
    petals = [ellipsoid((0.2, 0.11, 0.06), (0.16, 0, 0)).rot(0, -25, a).translate(top) for a in range(0, 360, 60)]
    m.add("Flower", union(*petals), (214, 108, 142), role="detail", tris=140, smooth=False)
    m.add("FlowerCenter", sphere(0.1, tuple(top + np.array([0, 0, 0.04]))), (232, 196, 84), role="detail", tris=40, smooth=False)
    return m


# ------------------------------------------------------------------------------ cespuglio secco

def dry_bush() -> Prop:
    """Cespuglio secco (~1.6) tipo rotolacampo: groviglio di rametti curvi (mesh low-poly)."""
    m = Prop("DryBush")
    rng = np.random.default_rng(66)
    c0 = np.array([0.0, 0.0, 0.7])
    dark, light = [], []
    for k in range(9):
        n = rng.normal(size=3)
        n /= np.linalg.norm(n)
        u = np.cross(n, [0.3, 0.5, 0.8])
        u /= np.linalg.norm(u)
        v = np.cross(n, u)
        R = rng.uniform(0.55, 0.78)
        c = c0 + rng.normal(size=3) * 0.1
        ph = rng.uniform(0, 6.28)
        pts = []
        for i in range(15):
            t = 2 * math.pi * i / 14
            rr = R * (1 + 0.12 * math.sin(3 * t + ph))
            p = c + (u * math.cos(t) + v * math.sin(t)) * rr
            p[2] = c0[2] + (p[2] - c0[2]) * 0.85  # un po' schiacciato
            pts.append(p)
        (dark if k % 2 else light).append(mesh_tube(pts, 0.042, sides=3))
    # rametti dritti che sporgono
    for k in range(7):
        d = rng.normal(size=3)
        d[2] = abs(d[2]) * 0.6
        d /= np.linalg.norm(d)
        p0 = c0 + d * 0.3
        p1 = c0 + d * 0.95
        p2 = p1 + (d + rng.normal(size=3) * 0.5) * 0.2
        dark.append(mesh_tube([p0, p1, p2], [0.042, 0.03, 0.014], sides=3))
    m.add("Twigs", mesh_concat(dark), (122, 96, 70), tris=900, smooth=False)
    m.add("TwigsLight", mesh_concat(light), (172, 142, 102), role="detail", tris=900, smooth=False)
    return m


# ------------------------------------------------------------------------------ masso rosso

def canyon_rock() -> Prop:
    """Masso di arenaria (~3) spigoloso, con fasce di strati chiari e una crepa."""
    m = Prop("CanyonRock", voxel=0.025)
    a = cleaved_block((0, 0, 0.8), (1.45, 1.05, 1.0), seed=91, rot=(0, 3, 15), ridge=0.35, taper=0.3, chips=8)
    b = cleaved_block((1.1, 0.5, 0.45), (0.65, 0.6, 0.55), seed=92, rot=(0, -8, 40), chips=5)
    c = cleaved_block((-1.05, -0.55, 0.3), (0.55, 0.45, 0.4), seed=93, rot=(0, 10, -25), ridge=0.15, chips=4)
    body = union(a, b, c).intersect(ground())
    body = body.subtract(surface_crack(body, (0, 0, 1.0), (0.2, -1, 0.3), (0.15, 0, -1), depth=0.25, width=0.07, length=1.5, zigzag=3, seed=94))
    m.add("Rock", body, (178, 108, 70), tris=520, smooth=False)

    def bands(p):  # due fasce orizzontali leggermente inclinate
        z = p[:, 2] - 0.08 * p[:, 0]
        return np.minimum(np.abs(z - 0.62) - 0.13, np.abs(z - 1.32) - 0.09)

    m.add("Strata", body.offset(0.035).intersect(SDF(bands, (-9, -9, 0.2), (9, 9, 1.8))), (208, 160, 110), role="detail",
          tris=300, smooth=False)
    return m


CATALOG = {"Mesa": mesa, "Cactus": cactus, "DryBush": dry_bush, "CanyonRock": canyon_rock}

if __name__ == "__main__":
    run(CATALOG)
