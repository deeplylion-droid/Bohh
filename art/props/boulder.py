"""Masso rotolante (Boulder) - ostacolo che rotola giu' dai sentieri.

Roccia spigolosa e tagliente, quasi sferica (raggio ~1): grandi faccette piatte, qualche punta
sporgente, crepe a zig-zag e macchie piu' scure, colori naturali da pietra.
ORIGINE AL CENTRO DEL MASSO (la roccia scende anche sotto z = 0), cosi' il gioco puo' farlo
rotolare attorno al suo centro.

Uso: python props/boulder.py
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import SDF, smax, union  # noqa: E402
from lib.toy import Model  # noqa: E402

ROCK = (124, 116, 107)
ROCK_DARK = (80, 74, 70)


def fib_dirs(n: int, jitter: float, rng) -> np.ndarray:
    """n direzioni quasi uniformi sulla sfera (spirale di Fibonacci) con un po' di disordine."""
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5 ** 0.5) * i
    d = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)
    d += rng.normal(scale=jitter, size=d.shape)
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def convex(normals, offsets, c=(0, 0, 0), cap: float | None = None, ext: float = 2.0, soft: float = 0.03) -> SDF:
    """Poliedro convesso: intersezione dei semispazi n.(p - c) <= d.

    soft: raggio dello smusso degli spigoli (massimo "morbido" log-sum-exp). Il toolkit rimesha i
    pezzi grandi con voxel ~0.1: uno smusso di qualche centesimo evita spigoli seghettati e la
    decimazione lo trasforma in una faccetta sottile (aspetto scolpito, a spigoli vivi).
    """
    nrm = np.asarray(normals, dtype=np.float32)
    off = np.asarray(offsets, dtype=np.float32)
    c = np.asarray(c, dtype=np.float32)

    def f(p):
        q = (p - c) @ nrm.T - off
        m = q.max(axis=1)
        d = m + soft * np.log(np.exp((q - m[:, None]) / soft).sum(axis=1)) if soft > 0 else m
        if cap is not None:  # sfera che smussa (dolcemente) solo i vertici piu' estremi
            sph = np.sqrt(((p - c) ** 2).sum(axis=1)) - cap
            d = smax(d, sph, max(soft, 1e-3) * 2) if soft > 0 else np.maximum(d, sph)
        return d

    return SDF(f, c - ext, c + ext)


def facet_ball(r: float, n: int, seed: int, c=(0, 0, 0), spread=(0.85, 1.0), jitter=0.12, cap=1.22,
               soft: float = 0.03) -> SDF:
    rng = np.random.default_rng(seed)
    dirs = fib_dirs(n, jitter, rng)
    rc = r * cap if cap else None
    return convex(dirs, r * rng.uniform(*spread, n), c, cap=rc, ext=r * (cap or 1.6) + 0.05, soft=soft)


def shard(axis, tip: float, half_angle: float, seed: int, sides: int = 4) -> SDF:
    """Punta piramidale irregolare lungo `axis`, con l'apice a distanza `tip` dal centro."""
    rng = np.random.default_rng(seed)
    a = unit(axis)
    u = unit(np.cross(a, [0.3, 0.2, 1.0]))
    v = np.cross(a, u)
    apex = a * tip
    normals, offsets = [], []
    for k in range(sides):
        ang = 2 * math.pi * k / sides + rng.uniform(-0.35, 0.35)
        side = math.cos(ang) * u + math.sin(ang) * v
        b = math.radians(90 - half_angle + rng.uniform(-8, 8))
        n = unit(math.cos(b) * side + math.sin(b) * a)
        normals.append(n)
        offsets.append(float(n @ apex))
    a32 = a.astype(np.float32)
    return convex(normals, offsets, (0, 0, 0), ext=tip + 0.1, soft=0.08).intersect(
        SDF(lambda p: 0.35 - p @ a32, (-tip,) * 3, (tip,) * 3))


def crack(base: SDF, start, heading, steps: int, step: float, seed: int, zig: float = 0.55):
    """Crepa a zig-zag che segue la superficie: lista di punti sulla superficie."""
    rng = np.random.default_rng(seed)
    p, n = project(base, (0, 0, 0), start)
    h = unit(heading)
    pts = [p]
    for k in range(steps):
        h = unit(h - n * (h @ n))
        side = unit(np.cross(n, h))
        turn = zig * (1 if k % 2 == 0 else -1) + rng.uniform(-0.2, 0.2)
        d = unit(h + side * turn)
        q = pts[-1] + d * step
        p, n = project(base, (0, 0, 0), q)
        pts.append(p)
    return [tuple(float(x) for x in q) for q in pts]


def boulder() -> Model:
    # nota: con pochi triangoli il toolkit rimesha la roccia a voxel ~0.1. Si parte da un poliedro
    # irregolare a spigoli appena smussati (niente dettagli sottili) e lo si decima con decisione:
    # la decimazione lo riporta a grandi faccette piatte con spigoli vivi.
    m = Model("Boulder", "prop", voxel=0.03)
    core = facet_ball(1.0, 16, seed=8, spread=(0.8, 1.0), jitter=0.16, cap=1.28, soft=0.1)
    # un paio di blocchi spigolosi che sporgono (sagoma irregolare ma ancora "rotolabile")
    chunks = [facet_ball(0.55, 8, seed=31, c=tuple(unit((0.85, -0.35, 0.45)) * 0.62), spread=(0.85, 1.0), jitter=0.3,
                         cap=1.3, soft=0.08),
              facet_ball(0.5, 8, seed=33, c=tuple(unit((-0.6, 0.55, -0.5)) * 0.66), spread=(0.85, 1.0), jitter=0.3,
                         cap=1.3, soft=0.08)]
    rock = union(core, *chunks)
    m.add("Rock", rock, ROCK, tris=560, smooth=False)

    # macchie scure: vernice spessa che segue le faccette, ritagliata da piccoli poliedri (bordi dritti)
    regions = []
    for k, (d, r) in enumerate((((0.4, -0.85, 0.3), 0.36), ((-0.8, -0.38, -0.36), 0.34), ((-0.1, 0.62, 0.8), 0.32),
                                ((0.3, -0.25, -0.95), 0.34), ((0.95, 0.15, -0.2), 0.28))):
        regions.append(facet_ball(r, 7, seed=60 + k, c=tuple(unit(d) * 0.98), spread=(0.75, 1.0), jitter=0.3, cap=None,
                                  soft=0.0))
    paint = rock.offset(0.05).subtract(rock.offset(-0.12))
    m.add("Patches", paint.intersect(union(*regions)), ROCK_DARK, role="detail", tris=380, smooth=False)
    return m


CATALOG = {"Boulder": boulder}

if __name__ == "__main__":
    views = tuple(os.environ.get("VIEWS", "3q,front").split(","))
    res = int(os.environ.get("RES", 700))
    for name in sys.argv[1:] or list(CATALOG):
        CATALOG[name]().build(views=views, res=res)
