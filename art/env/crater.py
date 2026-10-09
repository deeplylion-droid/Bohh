"""Zona Cratere Vulcanico: roccia lavica con crepe incandescenti, albero carbonizzato, spuntoni
di ossidiana.

Uso: python env/crater.py LavaRock DeadTree ObsidianSpikes  (oppure "all")
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.sdf import SDF, crystal, round_cone, tube, union  # noqa: E402
from common import (GROUND, Prop, cleaved_block, convex, fast_union, ground, polyline_crack, run,  # noqa: E402
                    surface_crack)

BASALT = (58, 52, 60)
LAVA = (255, 112, 32)


# ------------------------------------------------------------------------------ roccia lavica

def voronoi_cells(seeds, gap: float, box: float = 6.0):
    """Celle di Voronoi (poliedri convessi) attorno ai semi, ristrette di gap/2 per lato."""
    seeds = [np.asarray(s, dtype=np.float64) for s in seeds]
    cells = []
    for i, si in enumerate(seeds):
        N, D = [], []
        for j, sj in enumerate(seeds):
            if i == j:
                continue
            n = (sj - si) / np.linalg.norm(sj - si)
            N.append(n)
            D.append(float(n @ ((si + sj) / 2)) - gap / 2)
        for ax in range(3):
            for s in (1, -1):
                n = np.zeros(3)
                n[ax] = s
                N.append(n)
                D.append(box)
        cells.append(convex(N, D))
    return cells


def lava_rock() -> Prop:
    """Masso di basalto (~3) spaccato in blocchi: dalle fessure filtra la lava incandescente."""
    m = Prop("LavaRock", voxel=0.022)
    a = cleaved_block((0, 0, 0.85), (1.45, 1.15, 1.0), seed=41, rot=(0, 4, 20), ridge=0.4, taper=0.3, chips=8)
    b = cleaved_block((0.95, 0.55, 0.5), (0.7, 0.62, 0.6), seed=42, rot=(0, -10, 55), peak=0.35, chips=5)
    body = union(a, b).intersect(ground())
    seeds = [(-0.65, -0.35, 0.7), (0.55, -0.45, 0.65), (0.05, 0.6, 0.8), (0.2, -0.1, 1.85), (1.15, 0.65, 0.55)]
    cells = voronoi_cells(seeds, gap=0.13)
    chunks = union(*[body.intersect(c) for c in cells])
    m.add("Rock", chunks, BASALT, tris=640, smooth=False)
    # nucleo incandescente: visibile solo attraverso le fessure
    m.add("Lava", body.offset(-0.1), LAVA, material="Neon", role="glow", tris=300, smooth=False)
    return m


# ------------------------------------------------------------------------------ albero morto

def dead_tree() -> Prop:
    """Albero morto carbonizzato (~7): tronco attorcigliato, rami spezzati e storti, braci nelle crepe."""
    m = Prop("DeadTree", voxel=0.03)
    strands = []
    for k in range(3):  # tre fibre che si avvolgono: tronco attorcigliato
        ph = 2 * math.pi * k / 3
        pts, rad = [], []
        for i in range(9):
            t = i / 8
            z = GROUND - 0.05 + t * 4.6
            a = ph + t * 2.4
            rr = 0.2 * (1 - 0.4 * t)
            sway = 0.25 * math.sin(t * 2.5)
            pts.append((rr * math.cos(a) + sway, rr * math.sin(a) - 0.1 * t, z))
            rad.append(0.36 * (1 - 0.55 * t) + 0.05)
        strands.append(tube(pts, rad, k=0.08))
    roots = [round_cone((0.1 * math.cos(a), 0.1 * math.sin(a), 0.55), (0.95 * math.cos(a), 0.95 * math.sin(a), GROUND), 0.26, 0.08)
             for a in (0.2, 1.6, 2.9, 4.1, 5.3)]
    top = (0.25 * math.sin(2.5), -0.1, GROUND - 0.05 + 4.6)
    branches = [
        tube([top, (0.9, -0.2, 5.3), (1.3, -0.1, 5.5), (1.85, 0.0, 6.4)], [0.2, 0.13, 0.1, 0.04]),
        tube([top, (-0.5, 0.1, 5.4), (-1.1, 0.3, 5.6), (-1.5, 0.35, 6.6)], [0.19, 0.13, 0.09, 0.04]),
        tube([(0.15, -0.05, 3.4), (-0.6, -0.3, 3.9), (-1.3, -0.6, 4.0), (-1.75, -0.7, 4.5)], [0.16, 0.11, 0.07, 0.035]),
        tube([(0.25, -0.1, 3.9), (0.8, 0.4, 4.4), (1.4, 0.7, 4.5)], [0.14, 0.09, 0.04]),
        tube([top, (0.2, -0.4, 5.6), (0.05, -0.55, 6.9)], [0.16, 0.1, 0.04]),
        tube([(1.3, -0.1, 5.5), (1.7, -0.5, 5.6)], [0.07, 0.03]),
        tube([(-1.1, 0.3, 5.6), (-1.0, 0.8, 6.0)], [0.07, 0.03]),
    ]
    wood = union(union(*strands, k=0.1), *roots, *branches, k=0.12).intersect(ground())
    m.add("Wood", wood, (54, 46, 46), tris=1500, smooth=False)
    # braci: crepe incandescenti sul tronco (vernice in rilievo che segue la superficie)
    glow = []
    for inside, d, along, ln, s in [((0.1, 0, 1.2), (0.2, -1, 0), (0.1, 0, 1), 1.6, 1), ((0.05, 0, 2.6), (1, -0.3, 0), (-0.1, 0.1, 1), 1.2, 2)]:
        glow.append(surface_crack(wood, inside, d, along, depth=0.12, width=0.07, length=ln, zigzag=3, seed=s))
    m.add("Embers", wood.offset(0.02).intersect(union(*glow)), LAVA, material="Neon", role="glow", tris=220, voxel=0.018, smooth=False)
    return m


# ------------------------------------------------------------------------------ ossidiana

def obsidian_spikes() -> Prop:
    """Spuntoni di ossidiana nera e viola (~3), lucidi e sfaccettati, su una base di basalto."""
    m = Prop("ObsidianSpikes", voxel=0.02)

    def spike(base, length, radius, tilt, azim, spin=0.0, sides=4):
        return crystal(length, radius, 0.55, sides).rot(0, 0, spin).rot(0, tilt, azim).translate(base)

    black = [((0.0, 0.05, 0.05), 3.1, 0.5, 8, 160, 20, 5), ((0.6, -0.35, 0.05), 2.1, 0.38, 28, -25, 10, 4),
             ((-0.55, 0.45, 0.05), 1.9, 0.36, 30, 135, 40, 5), ((0.45, 0.65, 0.0), 1.3, 0.28, 40, 60, 0, 4)]
    purple = [((-0.6, -0.35, 0.05), 2.3, 0.36, 24, 215, 15, 5), ((0.95, 0.2, 0.0), 1.05, 0.22, 48, 15, 30, 4)]
    m.add("Spikes", union(*[spike(*s) for s in black]).intersect(ground()), (38, 32, 48), material="Glass", tris=520, smooth=False)
    m.add("SpikesPurple", union(*[spike(*s) for s in purple]).intersect(ground()), (98, 60, 150), material="Glass", role="detail",
          tris=260, smooth=False)
    base = union(cleaved_block((0, 0, 0.0), (1.2, 1.0, 0.32), seed=81, rot=(0, 0, 25), ridge=0.12, chips=6),
                 cleaved_block((-0.75, -0.55, -0.05), (0.5, 0.45, 0.26), seed=82, rot=(0, 8, -20), chips=4)).intersect(ground())
    m.add("Base", base, (64, 58, 66), role="detail", tris=220, smooth=False)
    return m


CATALOG = {"LavaRock": lava_rock, "DeadTree": dead_tree, "ObsidianSpikes": obsidian_spikes}

if __name__ == "__main__":
    run(CATALOG)
