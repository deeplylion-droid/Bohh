"""Uova per rarita'. Uso: python eggs/eggs.py Common Legendary ..."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import SDF, Frame, egg, ellipsoid, octahedron, project, sphere, union  # noqa: E402
from lib.toy import Model  # noqa: E402

R, H = 1.15, 3.1
CENTER = (0, 0, H * 0.45)


def shell() -> SDF:
    return egg(R, H, taper=0.2)


def surface_dirs(n: int, seed: int, zmin: float = -0.9, zmax: float = 0.95):
    rng = np.random.default_rng(seed)
    out = []
    while len(out) < n:
        v = rng.normal(size=3)
        v /= np.linalg.norm(v)
        if zmin <= v[2] <= zmax:
            out.append(v)
    return out


def spots(base: SDF, n: int, rmin: float, rmax: float, seed: int, zmin=-0.85, zmax=0.95) -> SDF:
    """Macchie tonde distribuite sulla superficie (evita sovrapposizioni troppo strette)."""
    rng = np.random.default_rng(seed + 1)
    placed = []
    for d in surface_dirs(n * 4, seed, zmin, zmax):
        p, _ = project(base, CENTER, d)
        r = float(rng.uniform(rmin, rmax))
        if all(np.linalg.norm(p - q) > (r + rq) * 1.15 for q, rq in placed):
            placed.append((p, r))
        if len(placed) >= n:
            break
    return union(*[sphere(r, p) for p, r in placed])


def band(z0: float, z1: float, wave_amp: float = 0.0, waves: int = 0, phase: float = 0.0, sharp: bool = False) -> SDF:
    """Fascia orizzontale fra z0 e z1, con bordo ondulato o a zig-zag opzionale."""
    def f(p):
        theta = np.arctan2(p[:, 1], p[:, 0])
        if waves:
            w = (2 / math.pi) * np.arcsin(np.sin(waves * theta + phase)) if sharp else np.sin(waves * theta + phase)
        else:
            w = 0.0
        lo = z0 + wave_amp * w
        hi = z1 + wave_amp * w
        return np.maximum(lo - p[:, 2], p[:, 2] - hi)
    return SDF(f, (-R * 1.3, -R * 1.3, z0 - abs(wave_amp)), (R * 1.3, R * 1.3, z1 + abs(wave_amp)))


def flames(z0: float, height: float, n: int) -> SDF:
    """Lingue di fuoco che salgono dal basso."""
    def f(p):
        theta = np.arctan2(p[:, 1], p[:, 0])
        u = (np.cos(n * theta) * 0.5 + 0.5) ** 3  # punte strette
        u2 = (np.cos(n * theta + math.pi) * 0.5 + 0.5) ** 3 * 0.45
        top = z0 + height * np.maximum(u, u2)
        return p[:, 2] - top
    return SDF(f, (-R * 1.3, -R * 1.3, -0.1), (R * 1.3, R * 1.3, z0 + height))


def gem_ring(base: SDF, n: int, z: float, size: float, phase: float = 0.0):
    gems = []
    for i in range(n):
        a = phase + i * 2 * math.pi / n
        fr = Frame(base, (0, 0, z), (math.cos(a), math.sin(a), 0.0), sink=size * 0.25)
        gem = octahedron(1.0).warp(lambda p: p / np.array([0.8, 0.75, 1.05], dtype=np.float32)).scale(size)
        gems.append(fr.place(gem))
    return union(*gems)


def build(kind: str) -> Model:
    m = Model(f"Egg{kind}", "egg", voxel=0.022)
    s = shell()
    lift = s.offset(0.014)
    if kind == "Common":
        m.add("Shell", s, (255, 244, 220), tris=4500)
        m.add("Spots", lift.intersect(spots(s, 18, 0.11, 0.21, seed=3)), (196, 146, 98), role="detail", tris=2500)
        m.add("Spots2", lift.intersect(spots(s, 14, 0.06, 0.11, seed=11)), (226, 186, 140), role="detail", tris=1500)
    elif kind == "Legendary":
        m.add("Shell", s, (255, 178, 30), material="Foil", tris=4500)
        outer = lift.intersect(flames(0.0, 1.55, 7)).intersect(band(0.12, 9, 0, 0))
        inner = s.offset(0.028).intersect(flames(0.0, 0.95, 7)).intersect(band(0.12, 9, 0, 0))
        m.add("Flames", outer, (255, 84, 20), material="Neon", role="glow", tris=3500)
        m.add("FlamesInner", inner, (255, 214, 60), material="Neon", role="glow", tris=2500)
        m.add("Band", lift.intersect(band(1.92, 2.2, 0.09, 12, 0.0, sharp=True)), (178, 20, 44), role="detail", tris=2500)
        m.add("Gems", gem_ring(s, 6, 2.06, 0.36, phase=math.pi / 12), (255, 36, 72), material="Glass", role="glow", tris=1800, voxel=0.015)
    else:
        raise SystemExit(f"Rarita' sconosciuta: {kind}")
    m.meta["rarity"] = kind
    return m


if __name__ == "__main__":
    for kind in sys.argv[1:]:
        build(kind).build(views=tuple(os.environ.get("VIEWS", "3q").split(",")), res=int(os.environ.get("RES", 700)))
