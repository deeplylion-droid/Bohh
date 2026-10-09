"""Zona Bosco: quercia, funghi, tronco caduto, felce.

Uso: python env/forest.py OakTree Mushrooms FallenLog Fern  (oppure "all")
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.sdf import SDF, bezier, capsule, ellipsoid, round_cone, sphere, tube, union  # noqa: E402
from common import (GROUND, Prop, bark_grooves, facet_blob, fast_union, ground, log_parts, mesh_concat,  # noqa: E402
                    mesh_leaf, mesh_tube, run, stub)

BARK = (92, 68, 50)
LEAF_DARK = (48, 88, 42)
LEAF_LIGHT = (90, 134, 58)


# ------------------------------------------------------------------------------ quercia

def oak_tree() -> Prop:
    """Quercia (~9): tronco robusto che si apre in grosse branche, chioma larga e irregolare di
    ciuffi low-poly in due verdi."""
    m = Prop("OakTree", voxel=0.05)
    trunk = tube([(0, 0, GROUND - 0.05), (0.05, 0.0, 1.3), (-0.08, 0.05, 2.5), (0.0, 0.0, 3.2)], [0.9, 0.7, 0.6, 0.55], k=0.2)
    roots = [round_cone((0, 0, 0.8), (1.15 * math.cos(a), 1.15 * math.sin(a), GROUND), 0.42, 0.14) for a in (0.3, 1.8, 3.2, 4.6)]
    limbs = [tube([(0.0, 0.0, 3.0), (1.0, -0.3, 4.0), (2.0, -0.6, 4.9)], [0.42, 0.3, 0.18]),
             tube([(0.0, 0.0, 2.9), (-0.95, 0.2, 3.8), (-1.9, 0.45, 4.7)], [0.42, 0.3, 0.18]),
             tube([(0.0, 0.0, 3.1), (0.15, 0.95, 4.2), (0.25, 1.8, 5.1)], [0.38, 0.27, 0.16]),
             tube([(0.0, 0.0, 3.1), (0.05, -0.35, 4.5), (0.1, -0.5, 5.8)], [0.4, 0.28, 0.17])]
    wood = union(trunk, *roots, *limbs, k=0.22).intersect(ground())
    m.add("Trunk", wood, BARK, material="Wood", tris=440, voxel=0.035, smooth=False)
    # chioma larga e bassa: anello basso, anello medio, cima; nessuna simmetria
    rng = np.random.default_rng(9)
    dark, light = [], []
    for k in range(7):
        a = 2 * math.pi * k / 7 + rng.uniform(-0.3, 0.3)
        r = rng.uniform(2.3, 2.9)
        sz = rng.uniform(1.2, 1.55)
        dark.append(((r * math.cos(a), r * math.sin(a) * 0.9, rng.uniform(5.3, 5.9)), (sz * 1.15, sz, sz * 0.68)))
    for k in range(6):  # ciuffi piccoli sul bordo: sagoma irregolare
        a = 2 * math.pi * k / 6 + rng.uniform(-0.25, 0.25) + 0.3
        r = rng.uniform(3.2, 3.7)
        sz = rng.uniform(0.6, 0.85)
        (light if k % 2 else dark).append(((r * math.cos(a), r * math.sin(a) * 0.9, rng.uniform(5.0, 6.4)), (sz * 1.1, sz, sz * 0.8)))
    for k in range(5):
        a = 2 * math.pi * k / 5 + rng.uniform(-0.4, 0.4) + 0.6
        r = rng.uniform(1.2, 2.0)
        sz = rng.uniform(1.2, 1.5)
        tgt = light if math.sin(a) < -0.2 or math.cos(a) > 0.6 else dark  # davanti e a destra: verde chiaro
        tgt.append(((r * math.cos(a), r * math.sin(a) * 0.9, rng.uniform(6.1, 6.7)), (sz * 1.1, sz, sz * 0.8)))
    dark.append(((0.0, 0.1, 5.9), (2.1, 2.0, 1.3)))  # nucleo che chiude i buchi
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.3
        r = rng.uniform(0.3, 0.9)
        sz = rng.uniform(1.05, 1.3)
        light.append(((r * math.cos(a), r * math.sin(a) - 0.1, rng.uniform(7.3, 7.8)), (sz * 1.1, sz, sz * 0.85)))
    blob = dict(n=15, depth=(0.74, 1.0), zmax=0.85, top=1.1)
    dk = union(*[facet_blob(c, r, seed=900 + k, rot=(0, 0, 41 * k), **blob) for k, (c, r) in enumerate(dark)])
    lt = union(*[facet_blob(c, r, seed=930 + k, rot=(0, 0, 67 * k), **blob) for k, (c, r) in enumerate(light)])
    m.add("Leaves", dk, LEAF_DARK, tris=1150, smooth=False)
    m.add("LeavesLight", lt, LEAF_LIGHT, role="detail", tris=880, smooth=False)
    return m


# ------------------------------------------------------------------------------ funghi

def mushrooms() -> Prop:
    """Tre funghi dal cappello rosso a pois chiari (~1.5)."""
    m = Prop("Mushrooms", voxel=0.015)
    specs = [  # base (x, y), altezza del cappello, raggio del cappello, inclinazione (gradi, verso x)
        ((0.0, 0.12), 1.32, 0.62, (6, -4)),
        ((0.62, -0.35), 0.86, 0.44, (-10, 14)),
        ((-0.55, -0.3), 0.6, 0.34, (12, -12)),
    ]
    caps, stems, spots = [], [], []
    rng = np.random.default_rng(12)
    for k, ((x, y), h, R, (tx, ty)) in enumerate(specs):
        top = np.array([x + math.tan(math.radians(ty)) * h, y - math.tan(math.radians(tx)) * h, h])
        base = np.array([x, y, GROUND])
        mid = (base + top) / 2 + np.array([0.04, -0.03, 0])
        stems.append(tube([tuple(base), tuple(mid), tuple(top)], [R * 0.42, R * 0.33, R * 0.3]))
        stems.append(round_cone(tuple(base), tuple(base + np.array([0, 0, 0.18])), R * 0.55, R * 0.38))
        # cappello: cupola schiacciata con il sotto leggermente concavo (lamelle color crema)
        cap = ellipsoid((R, R, R * 0.62), tuple(top + np.array([0, 0, R * 0.05])))
        cap = cap.intersect(SDF(lambda p, z=top[2] - R * 0.08: z - p[:, 2], (-9, -9, top[2] - R * 0.1), (9, 9, 9)))
        caps.append(cap)
        stems.append(ellipsoid((R * 0.92, R * 0.92, R * 0.1), tuple(top - np.array([0, 0, R * 0.05]))))
        # pois: piccole calotte sulla superficie del cappello
        n = [6, 4, 3][k]
        for i in range(n):
            a = 2 * math.pi * i / n + rng.uniform(-0.3, 0.3) + k
            el = math.radians(rng.uniform(25, 55)) if i else math.radians(88)
            d = np.array([math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el) * 0.62])
            c = top + np.array([0, 0, R * 0.05]) + d * R
            spots.append(sphere(R * rng.uniform(0.16, 0.22), tuple(c)))
    cap_u = union(*caps)
    m.add("Caps", cap_u, (176, 46, 38), tris=420, smooth=False)
    m.add("Stems", fast_union(*stems, k=0.03).intersect(ground()), (226, 214, 190), role="detail", tris=260, smooth=False)
    m.add("Spots", cap_u.offset(0.025).intersect(fast_union(*spots)), (236, 228, 212), role="detail", tris=200, smooth=False)
    return m


# ------------------------------------------------------------------------------ tronco caduto

def fallen_log() -> Prop:
    """Tronco caduto (~5) con le sezioni tagliate, muschio sopra e un moncone di ramo."""
    m = Prop("FallenLog", voxel=0.025)
    r, cz = 0.6, 0.42
    bark, ends = log_parts(-2.45, 2.45, r, cz, seed=31, sides=10, cut0=(0.1, 0.06), cut1=(-0.08, -0.1), bark_t=0.08)
    branch = stub((0.6, -0.2, cz + 0.2), (0.95, -0.85, cz + 0.75), 0.17)
    bark = bark_grooves(union(bark, branch), [(-1.6, 1.4, 70), (-0.2, 1.8, 115), (1.3, 1.5, 60), (1.7, 1.0, 150), (-1.0, 1.2, 30)], cz)
    m.add("Bark", bark.intersect(ground()), (96, 70, 50), material="Wood", tris=520, smooth=False)
    m.add("Ends", ends.intersect(ground()), (196, 160, 110), material="Wood", role="detail", tris=220, smooth=False)

    # muschio: coltre irregolare sulla parte alta, con qualche ciuffo
    def moss_region(p):
        x = p[:, 0]
        edge = cz + 0.22 + 0.1 * np.sin(2.3 * x + 0.5) + 0.06 * np.sin(5.1 * x + 1.7) + 0.05 * p[:, 1]
        return np.maximum(edge - p[:, 2], np.abs(x) - 2.15)
    moss = bark.offset(0.05).intersect(SDF(moss_region, (-2.3, -1, cz), (2.3, 1, cz + 1)))
    rng = np.random.default_rng(33)
    tufts = [facet_blob((x, rng.uniform(-0.2, 0.2), cz + r * 0.92), (0.28, 0.24, 0.14), n=10, seed=40 + i)
             for i, x in enumerate((-1.7, -0.7, 0.3, 1.5))]
    m.add("Moss", union(moss, *tufts), (86, 118, 50), role="detail", tris=360, smooth=False)
    return m


# ------------------------------------------------------------------------------ felce

def fern() -> Prop:
    """Felce (~1.5): ciuffo di fronde arcuate con foglioline a spina di pesce e due pastorali.

    Mesh low-poly costruite direttamente (foglioline piegate a V da 4 triangoli)."""
    m = Prop("Fern")
    rng = np.random.default_rng(21)
    pieces = []
    nfr = 7
    for f in range(nfr):
        a = 2 * math.pi * f / nfr + rng.uniform(-0.2, 0.2)
        d = np.array([math.cos(a), math.sin(a), 0.0])
        L = rng.uniform(0.95, 1.2)
        hgt = rng.uniform(1.15, 1.45)
        p0 = np.array([0, 0, GROUND + 0.05])
        p1 = p0 + d * 0.15 * L + np.array([0, 0, hgt * 0.8])
        p2 = p0 + d * 0.7 * L + np.array([0, 0, hgt * 1.08])
        p3 = p0 + d * 1.25 * L + np.array([0, 0, hgt * 0.5])
        pts = np.array(bezier(p0, p1, p2, p3, 24))
        rachis = pts[::3]
        pieces.append(mesh_tube(rachis, list(np.linspace(0.034, 0.012, len(rachis))), sides=3))
        side = np.array([-d[1], d[0], 0.0])
        for i in range(2, len(rachis) - 1):
            t = (i - 2) / (len(rachis) - 4)
            pc = rachis[i]
            tan = _unit3(rachis[i + 1] - rachis[i - 1])
            ln = 0.44 * (1 - 0.6 * t)
            for sgn in (1, -1):
                sd = side * sgn - np.dot(side * sgn, tan) * tan
                axis = _unit3(sd) * math.cos(math.radians(42)) + tan * math.sin(math.radians(42)) - np.array([0, 0, 0.22])
                pieces.append(mesh_leaf(pc, axis, tan, ln, 0.1 * (1 - 0.35 * t), 0.035))
        pieces.append(mesh_leaf(rachis[-1], rachis[-1] - rachis[-2], side, 0.16, 0.05, 0.02))
    m.add("Fronds", mesh_concat(pieces), (58, 110, 52), tris=900, smooth=False)
    # due pastorali (fronde giovani arrotolate), verde piu' chiaro
    curls = []
    for a, h in ((0.5, 0.78), (2.9, 0.62)):
        d = np.array([math.cos(a), math.sin(a), 0.0])
        pts = [(0.04 * d[0], 0.04 * d[1], GROUND + 0.05), (0.1 * d[0], 0.1 * d[1], h * 0.55), (0.15 * d[0], 0.15 * d[1], h)]
        c = np.array([0.15 * d[0], 0.15 * d[1], h]) + d * 0.12
        for i in range(1, 7):
            th = i * 0.9
            rr = 0.12 * (1 - i / 9)
            pts.append(tuple(c - d * rr * math.cos(th) + np.array([0, 0, rr * math.sin(th)])))
        curls.append(mesh_tube(pts, list(np.linspace(0.035, 0.016, len(pts))), sides=3))
    m.add("Fiddleheads", mesh_concat(curls), (100, 138, 64), role="detail", tris=300, smooth=False)
    return m


def _unit3(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


CATALOG = {"OakTree": oak_tree, "Mushrooms": mushrooms, "FallenLog": fallen_log, "Fern": fern}

if __name__ == "__main__":
    run(CATALOG)
