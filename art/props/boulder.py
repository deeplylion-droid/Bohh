"""Masso rotolante (Boulder) - ostacolo che rotola giu' dai sentieri.

Roccia spigolosa e tagliente, quasi sferica (raggio ~1): grandi faccette piatte, qualche punta
sporgente, crepe a V e faccette piu' scure; colori naturali da pietra (grigio-bruno).
ORIGINE AL CENTRO DEL MASSO (la roccia scende anche sotto z = 0), cosi' il gioco puo' farlo
rotolare attorno al suo centro.

Uso: python props/boulder.py
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.sdf import SDF, project, union  # noqa: E402
from propkit import FineModel, convex, fast_union, paint, run, unit  # noqa: E402

ROCK = (124, 116, 107)
ROCK_DARK = (84, 77, 72)


def fib_dirs(n: int, jitter: float, rng) -> np.ndarray:
    """n direzioni quasi uniformi sulla sfera (spirale di Fibonacci) con un po' di disordine."""
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5 ** 0.5) * i
    d = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)
    d += rng.normal(scale=jitter, size=d.shape)
    return d / np.linalg.norm(d, axis=1, keepdims=True)


class Facets:
    """Poliedro convesso irregolare: n piani attorno al centro c a distanza r * spread."""

    def __init__(self, r: float, n: int, seed: int, c=(0, 0, 0), spread=(0.85, 1.0), jitter=0.12):
        rng = np.random.default_rng(seed)
        self.r = r
        self.c = np.asarray(c, dtype=np.float32)
        self.dirs = fib_dirs(n, jitter, rng).astype(np.float32)
        self.dists = (r * rng.uniform(*spread, n)).astype(np.float32)

    def sdf(self) -> SDF:
        return convex(self.dirs, self.dists, self.c, ext=self.r * 1.8)

    def nearest(self, d) -> int:
        return int(np.argmax(self.dirs @ unit(d).astype(np.float32)))

    def raised_faces(self, sel, t: float, depth: float) -> SDF:
        """Solo le facce `sel`, sollevate di t: macchie che coprono faccette intere (bordi sugli spigoli)."""
        mask = np.zeros(len(self.dists), dtype=bool)
        mask[list(sel)] = True
        c = self.c

        def f(p):
            q = (p - c) @ self.dirs.T - self.dists
            inner = q.max(axis=1)
            q2 = q.copy()
            q2[:, mask] -= t
            outer = q2.max(axis=1)
            region = q[:, ~mask].max(axis=1) - q[:, mask].max(axis=1)
            return np.maximum(np.maximum(outer, -inner - depth), region)

        e = self.r * 1.8
        return SDF(f, c - e, c + e)


def spike(axis, tip: float, base: float, half_angle: float, seed: int, sides: int = 4) -> SDF:
    """Punta piramidale irregolare lungo `axis`: apice a distanza `tip` dal centro, base a `base`."""
    rng = np.random.default_rng(seed)
    a = unit(axis)
    u = unit(np.cross(a, [0.3, 0.2, 1.0]))
    v = np.cross(a, u)
    apex = a * tip
    normals, offsets = [-a], [-base]
    for k in range(sides):
        ang = 2 * math.pi * k / sides + rng.uniform(-0.3, 0.3)
        side = math.cos(ang) * u + math.sin(ang) * v
        b = math.radians(90 - half_angle + rng.uniform(-6, 6))
        n = unit(math.cos(b) * side + math.sin(b) * a)
        normals.append(n)
        offsets.append(float(n @ apex))
    return convex(normals, offsets, ext=tip + 0.1)


def _wedge(a, b, n, d0, d1, w0, w1) -> SDF:
    """Tratto di crepa a V da a a b: apertura e profondita' variano da (w0, d0) a (w1, d1)."""
    t = unit(b - a - np.dot(b - a, n) * n)
    bn = np.cross(n, t)
    ln = float(np.dot(b - a, t))
    a32, n32, t32, b32 = (np.asarray(x, dtype=np.float32) for x in (a, n, t, bn))
    pad = 0.03

    def f(p):
        v = p - a32
        s = v @ t32
        u = np.clip(s / max(ln, 1e-6), 0.0, 1.0)
        w = w0 + (w1 - w0) * u
        d = d0 + (d1 - d0) * u
        y = v @ n32 + d
        x = np.abs(v @ b32)
        k = w / np.maximum(d, 1e-4)
        wedge = (x - k * y) / np.sqrt(1 + k * k)
        return np.maximum(wedge, np.maximum(-s - pad, s - ln - pad))

    ext = max(d0, d1) + max(w0, w1) + pad
    return SDF(f, np.minimum(a, b) - ext, np.maximum(a, b) + ext)


def crack(base: SDF, start, heading, steps: int, step: float, seed: int, depth: float, width: float,
          zig: float = 0.6) -> SDF:
    """Crepa a zig-zag a V che segue la superficie e si assottiglia fino a chiudersi."""
    rng = np.random.default_rng(seed)
    p, n = project(base, (0, 0, 0), start)
    h = unit(heading)
    pts, nrm = [p], [n]
    for k in range(steps):
        h = unit(h - n * (h @ n))
        side = unit(np.cross(n, h))
        turn = zig * (1 if k % 2 == 0 else -1) + rng.uniform(-0.2, 0.2)
        q = pts[-1] + unit(h + side * turn) * step
        p, n = project(base, (0, 0, 0), q)
        pts.append(p)
        nrm.append(n)
    total = sum(float(np.linalg.norm(b - a)) for a, b in zip(pts[:-1], pts[1:]))
    parts, run_len = [], 0.0
    for i in range(len(pts) - 1):
        ln = float(np.linalg.norm(pts[i + 1] - pts[i]))
        f0, f1 = 1 - run_len / total, 1 - (run_len + ln) / total
        run_len += ln
        parts.append(_wedge(pts[i], pts[i + 1], unit(nrm[i] + nrm[i + 1]), depth * (0.5 + 0.5 * f0),
                            depth * (0.5 + 0.5 * f1), width * f0 ** 0.6, width * f1 ** 0.6))
    return fast_union(*parts)


def boulder() -> FineModel:
    m = FineModel("Boulder", "prop", voxel=0.018)
    core = Facets(1.0, 18, seed=8, spread=(0.82, 1.0), jitter=0.14)
    # due punte basse e larghe (spigoli rotti) e un blocco spigoloso: sagoma tagliente ma "rotolabile"
    spikes = [spike((0.62, -0.5, 0.75), 1.14, 0.55, 56, 1), spike((-0.85, 0.3, 0.35), 1.12, 0.55, 58, 2, sides=5)]
    chunk = Facets(0.5, 9, seed=33, c=tuple(unit((0.75, 0.45, -0.5)) * 0.66), spread=(0.82, 1.0), jitter=0.3).sdf()
    solid = union(core.sdf(), chunk, *spikes)
    cracks = union(crack(solid, (0.15, -1.0, 0.3), (0.3, 0.0, -1.0), 4, 0.25, 11, depth=0.2, width=0.075),
                   crack(solid, (0.9, -0.2, 0.3), (0.0, 0.7, -0.6), 3, 0.25, 12, depth=0.18, width=0.065),
                   crack(solid, (-0.6, -0.5, 0.6), (-0.4, 0.1, -1.0), 3, 0.24, 13, depth=0.18, width=0.065))
    rock = solid.subtract(cracks)
    m.add("Rock", rock, ROCK, tris=1050, smooth=False)

    # macchie piu' scure che attraversano le faccette (bordi dritti da piccoli poliedri)
    regions = []
    for k, (d, r) in enumerate((((0.45, -0.85, 0.1), 0.42), ((-0.85, -0.35, -0.25), 0.4), ((-0.1, 0.55, 0.85), 0.38),
                                ((0.3, -0.3, -0.9), 0.4), ((0.95, 0.25, 0.25), 0.34), ((-0.35, -0.75, 0.65), 0.26))):
        c, _ = project(solid, (0, 0, 0), d)
        regions.append(Facets(r, 7, seed=60 + k, c=tuple(c), spread=(0.7, 1.0), jitter=0.3).sdf())
    m.add("Patches", paint(solid, union(*regions), t=0.02, depth=0.08).subtract(cracks), ROCK_DARK, role="detail",
          tris=420, smooth=False)
    return m


CATALOG = {"Boulder": boulder}

if __name__ == "__main__":
    run(CATALOG)
