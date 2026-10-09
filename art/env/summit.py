"""Vetta innevata: lampione alpino, panchina di legno, roccia con cappello di neve.

Uso: python env/summit.py LampPost Bench SnowRock  (oppure "all")
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.sdf import SDF, box, union  # noqa: E402
from common import GROUND, Prop, ceiling, cleaved_block, convex, ground, run, surface_crack  # noqa: E402

IRON = (50, 54, 62)
SNOW = (240, 246, 252)
STONE = (126, 128, 132)


def ngon_prism(n: int, r0: float, r1: float, z0: float, z1: float, phase: float = 0.0, c=(0.0, 0.0)) -> SDF:
    """Prisma (o tronco di piramide) regolare a n lati, raggio r0 in basso e r1 in alto."""
    N, D = [], []
    h = z1 - z0
    for i in range(n):
        a = phase + 2 * math.pi * (i + 0.5) / n
        ap0, ap1 = r0 * math.cos(math.pi / n), r1 * math.cos(math.pi / n)  # apotemi
        nz = (ap0 - ap1) / h
        nn = np.array([math.cos(a), math.sin(a), nz])
        nn /= np.linalg.norm(nn)
        N.append(nn)
        D.append(float(nn @ np.array([c[0] + ap0 * math.cos(a), c[1] + ap0 * math.sin(a), z0])))
    N += [[0, 0, 1], [0, 0, -1]]
    D += [z1, -z0]
    return convex(N, D)


# ------------------------------------------------------------------------------ lampione

def lamp_post() -> Prop:
    """Lampione alpino (~9): plinto di pietra, palo di ferro, lanterna esagonale calda con neve sul tetto."""
    m = Prop("LampPost", voxel=0.02)
    plinth = cleaved_block((0, 0, 0.2), (0.62, 0.62, 0.42), seed=31, rot=(0, 0, 10), taper=0.35, tilt=3, chips=6, chip=(0.25, 0.5))
    m.add("Base", plinth.intersect(ground()), STONE, role="detail", tris=140, smooth=False)
    post = union(
        ngon_prism(8, 0.3, 0.26, 0.5, 0.95),     # zoccolo
        ngon_prism(8, 0.17, 0.12, 0.9, 7.35),    # fusto rastremato
        ngon_prism(8, 0.22, 0.22, 2.0, 2.15),    # anelli decorativi
        ngon_prism(8, 0.2, 0.2, 6.6, 6.72),
        ngon_prism(8, 0.16, 0.3, 7.2, 7.5),      # capitello che regge la lanterna
        ngon_prism(6, 0.5, 0.5, 7.48, 7.6),      # piatto della lanterna
        ngon_prism(6, 0.6, 0.16, 8.5, 9.05),     # tetto a piramide
        ngon_prism(6, 0.62, 0.62, 8.44, 8.52),   # bordo del tetto
        ngon_prism(6, 0.07, 0.03, 9.0, 9.32),    # pinnacolo
    )
    # montanti della lanterna agli spigoli dell'esagono
    posts = [ngon_prism(4, 0.05, 0.05, 7.58, 8.46, phase=0, c=(0.44 * math.cos(math.pi / 3 * i), 0.44 * math.sin(math.pi / 3 * i)))
             for i in range(6)]
    m.add("Post", union(post, *posts), IRON, material="Metal", tris=700, smooth=False)
    m.add("Glow", ngon_prism(6, 0.4, 0.36, 7.6, 8.46), (255, 194, 102), material="Neon", role="glow", tris=60, smooth=False)
    roof = ngon_prism(6, 0.6, 0.16, 8.5, 9.05)
    snow = roof.offset(0.07).intersect(SDF(lambda p: 8.68 + 0.04 * np.sin(5 * np.arctan2(p[:, 1], p[:, 0])) - p[:, 2],
                                           (-1, -1, 8.6), (1, 1, 9.2)))
    m.add("Snow", snow, SNOW, role="detail", tris=120, smooth=False)
    return m


# ------------------------------------------------------------------------------ panchina

def bench() -> Prop:
    """Panchina (~5 di lunghezza, seduta verso -Y): assi di legno su fianchi di ferro, neve sullo schienale."""
    m = Prop("Bench", voxel=0.02)
    L = 2.35
    planks = []
    for k, y in enumerate((-0.42, -0.12, 0.18)):  # seduta
        planks.append(box((L, 0.13, 0.055), (0.0, y, 1.0), round=0.02))
    for z in (1.42, 1.78):  # schienale inclinato all'indietro
        planks.append(box((L, 0.055, 0.14), (0.0, 0.0, 0.0), round=0.02).rot(-12, 0, 0).translate((0, 0.36 + (z - 1.42) * 0.22, z)))
    m.add("Planks", union(*planks), (156, 106, 66), material="Wood", tris=420, smooth=False)
    frame = []
    for x in (-1.9, 1.9):
        frame += [
            box((0.06, 0.06, 0.55), (x, -0.4, 0.42), round=0.015),                      # gamba davanti
            box((0.06, 0.06, 0.95), (x, 0.0, 0.0), round=0.015).rot(-12, 0, 0).translate((0, 0.3, 0.98)),  # gamba dietro + schienale
            box((0.06, 0.5, 0.05), (x, -0.12, 0.92), round=0.015),                      # traversa della seduta
            box((0.06, 0.38, 0.04), (x, -0.25, 0.25), round=0.015),                     # traversa bassa
            box((0.07, 0.36, 0.04), (x, -0.25, 1.35), round=0.015),                     # bracciolo
            box((0.05, 0.05, 0.22), (x, -0.55, 1.15), round=0.015),                     # sostegno del bracciolo
            box((0.12, 0.1, 0.04), (x, -0.4, -0.12), round=0.01),                       # piedini
            box((0.12, 0.1, 0.04), (x, 0.2, -0.12), round=0.01),
        ]
    m.add("Frame", union(*frame).intersect(ground()), IRON, material="Metal", role="detail", tris=520, smooth=False)
    # neve: cordolo sullo schienale e un mucchietto su un angolo della seduta
    top_plank = box((L, 0.055, 0.14), (0.0, 0.0, 0.0), round=0.02).rot(-12, 0, 0).translate((0, 0.36 + 0.36 * 0.22, 1.78))
    rim = top_plank.offset(0.07).intersect(SDF(lambda p: 1.9 + 0.02 * np.sin(3 * p[:, 0]) - p[:, 2], (-3, -1, 1.8), (3, 1, 2.2)))
    pile = SDF(lambda p: np.sqrt(((p[:, 0] - 1.7) / 0.55) ** 2 + ((p[:, 1] + 0.1) / 0.35) ** 2 + ((p[:, 2] - 1.03) / 0.16) ** 2) - 1.0,
               (1.1, -0.5, 0.95), (2.3, 0.3, 1.25))
    pile = pile.intersect(SDF(lambda p: 1.04 - p[:, 2], (1.1, -0.5, 1.04), (2.3, 0.3, 1.25)))
    m.add("Snow", union(rim, pile), SNOW, role="detail", tris=200, smooth=False)
    return m


# ------------------------------------------------------------------------------ roccia innevata

def snow_rock() -> Prop:
    """Roccia spigolosa grigio-blu (~3) con un cappello di neve sulle facce alte."""
    m = Prop("SnowRock", voxel=0.025)
    a = cleaved_block((0, 0, 0.8), (1.4, 1.05, 1.0), seed=61, rot=(0, 4, 25), ridge=0.55, taper=0.3, chips=8)
    b = cleaved_block((1.05, 0.45, 0.45), (0.7, 0.6, 0.6), seed=62, rot=(0, -12, 60), peak=0.4, chips=5)
    c = cleaved_block((-1.0, -0.5, 0.3), (0.55, 0.45, 0.42), seed=63, rot=(0, 10, -20), chips=4)
    body = union(a, b, c).intersect(ground())
    body = body.subtract(surface_crack(body, (0, 0, 0.9), (0.2, -1, 0.1), (0.1, 0, -1), depth=0.22, width=0.06, length=1.3, zigzag=3, seed=64))
    m.add("Rock", body, (114, 120, 132), tris=520, smooth=False)

    def snow_line(p):  # la neve copre la parte alta, con il bordo irregolare
        th = np.arctan2(p[:, 1], p[:, 0])
        edge = 1.25 + 0.14 * np.sin(3 * th + 0.5) + 0.07 * np.sin(7 * th + 1.3) - 0.12 * p[:, 0]
        return edge - p[:, 2]

    m.add("Snow", body.offset(0.1).intersect(SDF(snow_line, (-9, -9, 0.9), (9, 9, 9))), SNOW, role="detail", tris=340, smooth=False)
    return m


CATALOG = {"LampPost": lamp_post, "Bench": bench, "SnowRock": snow_rock}

if __name__ == "__main__":
    run(CATALOG)
