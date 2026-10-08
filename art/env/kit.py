"""Kit ambiente: rocce, pini, cespugli, fiori, ciuffi d'erba, nido.

Ogni funzione ritorna un Model pronto per l'esportazione (e riusabile nelle scene).
Uso: python env/kit.py Rock1 PineTree ...  (oppure "all")
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, capped_cone, capsule, cylinder, ellipsoid, round_cone, sphere, torus,  # noqa: E402
                     tube, union)
from lib.toy import Model  # noqa: E402


def noisy(shape: SDF, amp: float, freq: float, seed: int) -> SDF:
    """Deforma la superficie con rumore (somma di sinusoidi) per forme naturali."""
    rng = np.random.default_rng(seed)
    waves = [(rng.normal(size=3) * freq, rng.uniform(0, 6.28), rng.uniform(0.5, 1.0)) for _ in range(6)]

    def f(p):
        d = shape(p)
        n = np.zeros(len(p), dtype=np.float32)
        for k, ph, w in waves:
            n += w * np.sin(p @ k.astype(np.float32) + ph)
        return d + amp * n / 3.0

    return SDF(f, shape.lo - amp * 2, shape.hi + amp * 2)


ROCK_COLORS = [(150, 156, 170), (164, 160, 152), (132, 140, 158)]


def rock(i: int) -> Model:
    m = Model(f"Rock{i}", "prop", voxel=0.05)
    rng = np.random.default_rng(100 + i)
    base = ellipsoid((rng.uniform(1.6, 2.2), rng.uniform(1.3, 1.8), rng.uniform(1.0, 1.5)), (0, 0, 0.7))
    extra = ellipsoid((rng.uniform(0.8, 1.2),) * 3, (rng.uniform(-0.8, 0.8), rng.uniform(-0.5, 0.5), 1.3))
    shape = noisy(union(base, extra, k=0.6), 0.22, 1.6, i).intersect(SDF(lambda p: -p[:, 2], (-9, -9, 0), (9, 9, 9)))
    m.add("Rock", shape, ROCK_COLORS[i % 3], material="SmoothPlastic", tris=260, smooth=False)
    return m


PINE_TIERS = [(1.5, 2.6, 2.4), (2.9, 2.1, 2.2), (4.2, 1.6, 2.0), (5.4, 1.05, 1.7)]


def pine(name="PineTree", snowy=False, scale=1.0, leaf=(46, 156, 80)) -> Model:
    m = Model(name, "prop", voxel=0.05)
    trunk = cylinder((0, 0, 0), (0, 0, 2.2), 0.42, round=0.1)
    m.add("Trunk", trunk.scale(scale), (122, 82, 52), material="Wood", tris=300)
    # piani conici con base piatta e bordo arrotondato: silhouette a "pagoda" ben leggibile
    tiers = [capped_cone((0, 0, z), (0, 0, z + h), r, 0.16, round=0.14) for (z, r, h) in PINE_TIERS]
    leaves = union(*tiers)
    m.add("Leaves", leaves.scale(scale), leaf, tris=1400)
    if snowy:
        caps = union(*[capped_cone((0, 0, z + h * 0.42), (0, 0, z + h + 0.1), r * 0.62, 0.0) for (z, r, h) in PINE_TIERS])
        snow = leaves.offset(0.05).intersect(caps)
        m.add("Snow", snow.scale(scale), (246, 250, 255), tris=1200)
    return m


def bush(i: int = 1) -> Model:
    m = Model(f"Bush{i}", "prop", voxel=0.05)
    rng = np.random.default_rng(200 + i)
    balls = [sphere(rng.uniform(0.7, 1.1), (rng.uniform(-0.9, 0.9), rng.uniform(-0.6, 0.6), rng.uniform(0.5, 1.1)))
             for _ in range(5)]
    shape = union(*balls, k=0.35).intersect(SDF(lambda p: -p[:, 2], (-9, -9, 0), (9, 9, 9)))
    m.add("Leaves", shape, (70, 178, 80), tris=700)
    berries = union(*[sphere(0.13, (rng.uniform(-1.2, 1.2), rng.uniform(-1.0, -0.3), rng.uniform(0.6, 1.5))) for _ in range(6)])
    m.add("Berries", berries.intersect(shape.offset(0.12)), (232, 50, 72), tris=500)
    return m


def flower_patch(i: int = 1) -> Model:
    """Gruppo di fiorellini a 5 petali su steli corti."""
    m = Model(f"Flowers{i}", "prop", voxel=0.025)
    rng = np.random.default_rng(300 + i)
    palettes = [((255, 255, 255), (255, 210, 60)), ((255, 140, 190), (255, 240, 120)), ((170, 140, 255), (255, 230, 120))]
    petals_by_color = {}
    centers, stems = [], []
    for k in range(7):
        x, y = rng.uniform(-1.1, 1.1), rng.uniform(-1.1, 1.1)
        h = rng.uniform(0.45, 0.75)
        pet_col, cen_col = palettes[rng.integers(0, 3)]
        stems.append(capsule((x, y, 0), (x, y, h), 0.035))
        ring = [sphere(0.13, (x + 0.16 * math.cos(a), y + 0.16 * math.sin(a), h)) for a in np.linspace(0, 2 * math.pi, 6)[:-1]]
        petals_by_color.setdefault(pet_col, []).append(union(*ring).warp(lambda p, h=h: p * np.array([1, 1, 2.2], dtype=np.float32) - np.array([0, 0, h * 1.2], dtype=np.float32), pad=0.2))
        centers.append(sphere(0.08, (x, y, h + 0.03)))
    m.add("Stems", union(*stems), (70, 160, 70), tris=600)
    for idx, (col, shapes) in enumerate(petals_by_color.items()):
        m.add(f"Petals{idx}", union(*shapes), col, tris=900)
    m.add("Centers", union(*centers), (255, 205, 50), tris=400)
    return m


def grass_tuft(i: int = 1) -> Model:
    m = Model(f"Grass{i}", "prop", voxel=0.02)
    rng = np.random.default_rng(400 + i)
    blades = []
    for k in range(9):
        a = rng.uniform(0, 2 * math.pi)
        lean = rng.uniform(0.15, 0.4)
        h = rng.uniform(0.5, 0.85)
        x, y = 0.12 * math.cos(a), 0.12 * math.sin(a)
        blades.append(tube(bezier((x, y, 0), (x, y, h * 0.5), (x + lean * math.cos(a) * 0.6, y + lean * math.sin(a) * 0.6, h * 0.9),
                                  (x + lean * math.cos(a), y + lean * math.sin(a), h), 6), [0.06, 0.055, 0.045, 0.035, 0.025, 0.015, 0.008]))
    m.add("Blades", union(*blades, k=0.02), (96, 196, 76), tris=700)
    return m


def nest() -> Model:
    m = Model("Nest", "prop", voxel=0.03)
    ring = torus(1.35, 0.42, (0, 0, 0.42))
    bowl = ellipsoid((1.45, 1.45, 0.5), (0, 0, 0.32)).subtract(ellipsoid((1.15, 1.15, 0.5), (0, 0, 0.62)))
    body = noisy(union(ring, bowl, k=0.2), 0.05, 7.0, 5)
    m.add("Nest", body, (166, 112, 62), tris=2200)
    twigs = []
    rng = np.random.default_rng(9)
    for k in range(22):
        a = rng.uniform(0, 2 * math.pi)
        r = 1.35 + rng.uniform(-0.2, 0.25)
        z = 0.42 + rng.uniform(-0.25, 0.3)
        da = rng.uniform(0.35, 0.7)
        p0 = (r * math.cos(a), r * math.sin(a), z)
        p1 = ((r + rng.uniform(-0.1, 0.15)) * math.cos(a + da), (r + rng.uniform(-0.1, 0.15)) * math.sin(a + da), z + rng.uniform(-0.15, 0.15))
        twigs.append(capsule(p0, p1, 0.05))
    m.add("Twigs", union(*twigs).intersect(body.offset(0.09)), (120, 76, 40), tris=1800)
    straw = ellipsoid((1.2, 1.2, 0.18), (0, 0, 0.45)).subtract(ellipsoid((1.1, 1.1, 0.4), (0, 0, 0.75)))
    m.add("Straw", noisy(straw, 0.03, 9.0, 3), (240, 210, 120), tris=900)
    return m


CATALOG = {
    "Rock1": lambda: rock(1), "Rock2": lambda: rock(2), "Rock3": lambda: rock(3),
    "PineTree": lambda: pine(), "PineSnowy": lambda: pine("PineSnowy", snowy=True),
    "Bush1": lambda: bush(1), "Flowers1": lambda: flower_patch(1), "Flowers2": lambda: flower_patch(2),
    "Grass1": lambda: grass_tuft(1), "Nest": nest,
}

if __name__ == "__main__":
    names = list(CATALOG) if sys.argv[1:] == ["all"] else sys.argv[1:]
    for n in names:
        CATALOG[n]().build(views=tuple(os.environ.get("VIEWS", "3q").split(",")), res=int(os.environ.get("RES", 500)))
