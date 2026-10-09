"""Masso rotolante (Boulder) - ostacolo che rotola giu' dai sentieri.

Roccia grezza quasi sferica (raggio ~1) a faccette piatte, con bozzi sporgenti e qualche
faccetta piu' scura. ORIGINE AL CENTRO DEL MASSO (la roccia scende anche sotto z = 0),
cosi' il gioco puo' farlo rotolare attorno al suo centro.

Uso: python props/boulder.py
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import SDF, union  # noqa: E402
from lib.toy import Model  # noqa: E402

ROCK = (140, 126, 114)
ROCK_DARK = (98, 87, 80)


def fib_dirs(n: int, jitter: float, rng) -> np.ndarray:
    """n direzioni quasi uniformi sulla sfera (spirale di Fibonacci) con un po' di disordine."""
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5 ** 0.5) * i
    d = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)
    d += rng.normal(scale=jitter, size=d.shape)
    return d / np.linalg.norm(d, axis=1, keepdims=True)


class Facets:
    """Poliedro convesso irregolare: intersezione di n semispazi attorno al centro c."""

    def __init__(self, r: float, n: int, seed: int, c=(0, 0, 0), spread=(0.9, 1.0), jitter=0.12):
        rng = np.random.default_rng(seed)
        self.r = r
        self.c = np.asarray(c, dtype=np.float32)
        self.dirs = fib_dirs(n, jitter, rng).astype(np.float32)
        self.dists = (r * rng.uniform(*spread, n)).astype(np.float32)

    def planes(self, p):
        return (p - self.c) @ self.dirs.T - self.dists

    def sdf(self) -> SDF:
        e = self.r * 1.6
        return SDF(lambda p: self.planes(p).max(axis=1), self.c - e, self.c + e)

    def nearest(self, d) -> int:
        d = np.asarray(d, dtype=np.float32)
        return int(np.argmax(self.dirs @ (d / np.linalg.norm(d))))

    def raised_faces(self, sel, t: float) -> SDF:
        """Solo le facce `sel`, sollevate di t (una "vernice" a faccette, bordi netti sugli spigoli)."""
        mask = np.zeros(len(self.dists), dtype=bool)
        mask[list(sel)] = True

        def f(p):
            q = self.planes(p)
            inner = q.max(axis=1)
            q2 = q.copy()
            q2[:, mask] -= t
            outer = q2.max(axis=1)
            region = q[:, ~mask].max(axis=1) - q[:, mask].max(axis=1)
            return np.maximum(np.maximum(outer, -inner - 0.02), region)

        e = self.r * 1.6
        return SDF(f, self.c - e, self.c + e)


def boulder() -> Model:
    m = Model("Boulder", "prop", voxel=0.022)
    core = Facets(1.0, 34, seed=11, spread=(0.88, 1.0), jitter=0.1)
    # bozzi: blocchi spigolosi che sporgono dalla sfera
    rng = np.random.default_rng(5)
    lumps = []
    for k, d in enumerate(fib_dirs(4, 0.3, rng)):
        r = float(rng.uniform(0.45, 0.55))
        lumps.append(Facets(r, 9, seed=40 + k, c=tuple(d * (1.0 - r * 0.7)), spread=(0.85, 1.0), jitter=0.25).sdf())
    rock = union(core.sdf(), *lumps)
    m.add("Rock", rock, ROCK, tris=1080, smooth=False)

    # alcune faccette piu' scure, a gruppi, sui lati ben visibili
    sel = set()
    for d in ((0.6, -0.7, 0.35), (0.7, -0.6, 0.1), (-0.75, -0.45, -0.3), (-0.1, 0.6, 0.8), (0.2, -0.3, -0.95),
              (-0.5, -0.8, 0.45)):
        sel.add(core.nearest(d))
    m.add("Patches", core.raised_faces(sel, 0.025), ROCK_DARK, role="detail", tris=380, smooth=False)
    return m


CATALOG = {"Boulder": boulder}

if __name__ == "__main__":
    views = tuple(os.environ.get("VIEWS", "3q,front").split(","))
    res = int(os.environ.get("RES", 700))
    for name in sys.argv[1:] or list(CATALOG):
        CATALOG[name]().build(views=views, res=res)
