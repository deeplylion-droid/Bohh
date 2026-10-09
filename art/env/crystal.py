"""Zona Grotte di Cristallo: gruppi di cristalli viola e azzurri, funghi luminosi.

Uso: python env/crystal.py CrystalCluster1 CrystalCluster2 GlowShroom  (oppure "all")
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.sdf import SDF, crystal, ellipsoid, round_cone, tube, union  # noqa: E402
from common import GROUND, Prop, cleaved_block, fast_union, ground, run  # noqa: E402

BASE_ROCK = (68, 64, 80)   # ardesia scura


def crystal_at(base, length: float, radius: float, tilt: float, azim: float, spin: float = 0.0,
               tip: float = 0.28, sides: int = 6) -> SDF:
    """Cristallo sfaccettato che parte da 'base', inclinato di 'tilt' gradi verso l'azimut 'azim'."""
    return crystal(length, radius, tip, sides).rot(0, 0, spin).rot(0, tilt, azim).translate(base)


def rock_base(half, seed: int, z: float = 0.1) -> SDF:
    a = cleaved_block((0, 0, z), half, seed=seed, rot=(0, 0, 15), ridge=half[2] * 0.4, chips=6)
    b = cleaved_block((half[0] * 0.55, half[1] * 0.45, z - 0.05), (half[0] * 0.55, half[1] * 0.5, half[2] * 0.8), seed=seed + 1,
                      rot=(0, 6, 50), chips=4)
    return union(a, b).intersect(ground())


def cluster1() -> Prop:
    """Grande gruppo (~5) di 7 cristalli viola (due luminosi) su una base di roccia scura."""
    m = Prop("CrystalCluster1", voxel=0.022)
    glass = [  # base, lunghezza, raggio, inclinazione, azimut, rotazione propria
        ((0.0, 0.1, 0.15), 4.75, 0.62, 6, 200, 10),
        ((0.62, -0.3, 0.1), 3.2, 0.45, 27, -30, 25),
        ((-0.65, -0.2, 0.1), 2.8, 0.42, 32, 200, 5),
        ((0.2, 0.75, 0.1), 2.5, 0.38, 30, 100, 40),
        ((-0.25, -0.8, 0.05), 1.6, 0.3, 46, 255, 15),
    ]
    glow = [((0.95, 0.4, 0.05), 2.0, 0.32, 42, 20, 30), ((-0.95, 0.55, 0.05), 1.4, 0.26, 50, 150, 0),
            ((0.45, -0.95, 0.0), 0.75, 0.16, 55, 290, 20), ((-1.15, -0.45, 0.0), 0.6, 0.14, 60, 210, 10)]
    m.add("Crystals", union(*[crystal_at(*g) for g in glass]).intersect(ground()), (146, 94, 214), material="Glass",
          tris=900, smooth=False)
    m.add("GlowCrystals", union(*[crystal_at(*g) for g in glow]).intersect(ground()), (204, 152, 255), material="Neon",
          role="glow", tris=420, smooth=False)
    m.add("Base", rock_base((1.55, 1.3, 0.38), 700), BASE_ROCK, role="detail", tris=260, smooth=False)
    return m


def cluster2() -> Prop:
    """Gruppo piu' piccolo (~3) di cristalli azzurri, due luminosi."""
    m = Prop("CrystalCluster2", voxel=0.02)
    glass = [((0.0, 0.0, 0.1), 2.85, 0.42, 8, 210, 0), ((0.45, -0.2, 0.05), 1.9, 0.32, 30, -20, 20),
             ((-0.45, -0.1, 0.05), 1.65, 0.3, 34, 190, 35)]
    glow = [((0.1, 0.5, 0.05), 1.5, 0.26, 32, 95, 10), ((-0.25, -0.5, 0.0), 0.9, 0.2, 50, 260, 0),
            ((0.62, 0.3, 0.0), 0.55, 0.13, 58, 40, 15)]
    m.add("Crystals", union(*[crystal_at(*g) for g in glass]).intersect(ground()), (72, 194, 222), material="Glass",
          tris=600, smooth=False)
    m.add("GlowCrystals", union(*[crystal_at(*g) for g in glow]).intersect(ground()), (150, 240, 255), material="Neon",
          role="glow", tris=300, smooth=False)
    m.add("Base", rock_base((1.0, 0.85, 0.28), 710, z=0.05), BASE_ROCK, role="detail", tris=200, smooth=False)
    return m


def glow_shroom() -> Prop:
    """Funghi luminosi (~2): gambi chiari e cappelli al neon azzurri e rosa."""
    m = Prop("GlowShroom", voxel=0.015)
    specs = [  # base (x, y), altezza del cappello, raggio, piega del gambo (x, y), colore (0 azzurro, 1 rosa)
        ((0.0, 0.1), 1.5, 0.62, (0.08, -0.04), 0),
        ((0.62, -0.35), 1.0, 0.45, (0.12, -0.06), 1),
        ((-0.58, -0.28), 0.72, 0.36, (-0.1, -0.05), 1),
        ((0.12, -0.72), 0.45, 0.26, (0.05, -0.08), 0),
    ]
    stems, caps = [], {0: [], 1: []}
    for (x, y), h, R, (bx, by), col in specs:
        top = np.array([x + bx, y + by, h])
        mid = np.array([x + bx * 0.3, y + by * 0.3, h * 0.5])
        stems.append(tube([(x, y, GROUND), tuple(mid), tuple(top)], [R * 0.42, R * 0.33, R * 0.3]))
        stems.append(ellipsoid((R * 0.85, R * 0.85, R * 0.12), tuple(top + np.array([0, 0, -R * 0.02]))))  # lamelle
        cap = ellipsoid((R, R, R * 0.7), tuple(top + np.array([0, 0, R * 0.02])))
        cap = cap.intersect(SDF(lambda p, z=top[2] + R * 0.02: z - p[:, 2], (-9, -9, top[2]), (9, 9, 9)))
        caps[col].append(cap)
    m.add("Stems", fast_union(*stems, k=0.02).intersect(ground()), (200, 192, 218), tris=320, smooth=False)
    m.add("CapsCyan", union(*caps[0]), (40, 206, 226), material="Neon", role="glow", tris=240, smooth=False)
    m.add("CapsPink", union(*caps[1]), (226, 74, 190), material="Neon", role="glow", tris=240, smooth=False)
    return m


CATALOG = {"CrystalCluster1": cluster1, "CrystalCluster2": cluster2, "GlowShroom": glow_shroom}

if __name__ == "__main__":
    run(CATALOG)
