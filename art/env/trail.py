"""Bordi del sentiero: file di pietre piatte e tronchi mezzi interrati.

Uso: python env/trail.py EdgeStones LogBorder  (oppure "all")
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.sdf import union  # noqa: E402
from common import GROUND, Prop, bark_grooves, cleaved_block, ground, log_parts, run, stub  # noqa: E402


def edge_stones() -> Prop:
    """Fila di 4 pietre piatte e irregolari (~4 di lunghezza) mezze interrate, lungo X."""
    m = Prop("EdgeStones", voxel=0.02)
    rng = np.random.default_rng(71)
    light, dark = [], []
    x = -1.55
    for k in range(4):
        w = rng.uniform(0.45, 0.58)
        d = rng.uniform(0.38, 0.5)
        h = rng.uniform(0.14, 0.2)
        c = (x, rng.uniform(-0.12, 0.12), h * 0.2)
        stone = cleaved_block(c, (w, d, h), seed=700 + k, rot=(rng.uniform(-6, 6), rng.uniform(-8, 8), rng.uniform(-25, 25)),
                              tilt=8, taper=0.25, ridge=h * 0.35 if k % 2 else 0.0, chips=5, chip=(0.3, 0.6))
        (light if k % 2 == 0 else dark).append(stone)
        x += w + rng.uniform(0.5, 0.6)
    m.add("Stones", union(*light).intersect(ground()), (124, 122, 116), tris=280, smooth=False)
    m.add("StonesDark", union(*dark).intersect(ground()), (102, 100, 96), role="detail", tris=280, smooth=False)
    return m


def log_border() -> Prop:
    """Tronco tagliato mezzo interrato (~5 di lunghezza) per bordare il sentiero, lungo X."""
    m = Prop("LogBorder", voxel=0.02)
    r, cz = 0.46, 0.0
    bark, ends = log_parts(-2.5, 2.5, r, cz, seed=81)
    knot = stub((0.9, -0.1, 0.2), (1.12, -0.42, 0.55), 0.13)
    bark = bark_grooves(union(bark, knot), [(-1.4, 1.6, 90), (0.2, 1.4, 60), (1.5, 1.2, 115), (-0.3, 1.0, 130)], cz)
    m.add("Bark", bark.intersect(ground(GROUND - 0.1)), (98, 72, 50), material="Wood", tris=420, smooth=False)
    m.add("Ends", ends.intersect(ground(GROUND - 0.1)), (198, 164, 112), material="Wood", role="detail", tris=200, smooth=False)
    return m


CATALOG = {"EdgeStones": edge_stones, "LogBorder": log_border}

if __name__ == "__main__":
    run(CATALOG)
