"""Uova per rarita'. Uso: python eggs/eggs.py Common Uncommon Rare Epic Legendary Mythic Divine Secret"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, box, crystal, egg, ellipsoid, octahedron, prism, project, sphere, star_points,  # noqa: E402
                     torus, tube, union)
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


def sparkles(base: SDF, n: int, size: float, seed: int, zmin=-0.6, zmax=0.9) -> SDF:
    """Stelline a quattro punte appoggiate sulla superficie."""
    star = prism(star_points(4, size, size * 0.36, rot_deg=90), -size * 0.12, size * 0.12, round=size * 0.06).rot(90, 0, 0)
    out = []
    for d in surface_dirs(n, seed, zmin, zmax):
        fr = Frame(base, CENTER, tuple(d), sink=size * 0.06)
        out.append(fr.place(star))
    return union(*out)


def crystals(base: SDF, n: int, seed: int, length: float, width: float, zmin=-0.1, zmax=0.85):
    """Gruppi di cristalli sfaccettati che spuntano dal guscio. Ritorna (cristalli grandi, piccoli)."""
    rng = np.random.default_rng(seed)
    big, small = [], []
    for d in surface_dirs(n, seed, zmin, zmax):
        fr = Frame(base, CENTER, tuple(d), sink=length * 0.3)
        # cristallo principale lungo la normale (asse -Y locale) e due laterali inclinati
        main = crystal(length, width, tip=0.32).rot(90, 0, 0).rot(0, float(rng.uniform(0, 60)), 0)
        big.append(fr.place(main))
        for sx in (-1, 1):
            ln = length * float(rng.uniform(0.45, 0.62))
            side = crystal(ln, width * 0.7, tip=0.35).rot(90, 0, 0).rot(0, 0, sx * float(rng.uniform(24, 36)))
            small.append(fr.place(side, (sx * width * 0.9, 0, float(rng.uniform(-0.06, 0.06)))))
    clip = box((R + 1.0, R + 1.0, H / 2 + 1.0), (0, 0, H / 2))
    return union(*big).intersect(clip), union(*small).intersect(clip)


def cracks(base: SDF, n: int, seed: int, steps: int = 9, step: float = 0.22) -> SDF:
    """Crepe ramificate disegnate sulla superficie (tubi sottili che seguono il guscio)."""
    rng = np.random.default_rng(seed)
    lines = []
    for d in surface_dirs(n, seed, -0.7, 0.85):
        p, nrm = project(base, CENTER, tuple(d))
        heading = np.cross(nrm, [0, 0, 1.0])
        if np.linalg.norm(heading) < 1e-3:
            heading = np.array([1.0, 0, 0])
        heading /= np.linalg.norm(heading)
        if rng.random() < 0.5:
            heading = -heading
        pts = [p]
        for _ in range(steps):
            turn = rng.normal(0, 0.55)
            heading = heading * math.cos(turn) + np.cross(nrm, heading) * math.sin(turn)
            q = pts[-1] + heading * step
            q, nrm = project(base, CENTER, q - np.array(CENTER))
            heading = heading - nrm * float(heading @ nrm)
            heading /= max(np.linalg.norm(heading), 1e-6)
            pts.append(q)
            # piccole diramazioni
            if rng.random() < 0.3:
                b = q + (np.cross(nrm, heading) * (1 if rng.random() < 0.5 else -1) + heading * 0.4) * step * 0.9
                b, _ = project(base, CENTER, b - np.array(CENTER))
                lines.append(tube([tuple(q), tuple(b)], [0.042, 0.02]))
        radii = [0.06 - 0.034 * i / steps for i in range(len(pts))]
        lines.append(tube([tuple(x) for x in pts], radii))
    return union(*lines)


def spiral(turns: float, width: float, phase: float = 0.0) -> SDF:
    """Fascia a spirale attorno all'asse verticale (larghezza in radianti)."""
    def f(p):
        theta = np.arctan2(p[:, 1], p[:, 0])
        w = theta - 2 * math.pi * turns * (p[:, 2] / H) + phase
        w = (w + math.pi) % (2 * math.pi) - math.pi
        rxy = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2)
        return (np.abs(w) - width / 2) * np.maximum(rxy, 0.05)
    return SDF(f, (-R * 1.3, -R * 1.3, -0.1), (R * 1.3, R * 1.3, H + 0.1))


def wing(side: int) -> SDF:
    """Alucce di piume ai lati dell'uovo divino."""
    feathers = [ellipsoid((0.16, 0.08, 0.5 - 0.07 * i)).rot(0, 18 + 16 * i, 0).translate((0.12 * i, 0, -0.06 * i))
                for i in range(4)]
    w = union(*feathers, k=0.06).rot(0, 0, -15).translate((R * 0.98, 0.2, H * 0.55))
    return w if side > 0 else w.mirrored()


def build(kind: str) -> Model:
    m = Model(f"Egg{kind}", "egg", voxel=0.022)
    s = shell()
    lift = s.offset(0.014)
    # strato di "vernice" per fasce e decori: un guscio sottile (senza l'interno pieno, che
    # sprecherebbe triangoli in superfici nascoste e renderebbe irregolare la decimazione)
    paint = s.offset(0.032).subtract(s.offset(-0.07))
    if kind == "Common":
        m.add("Shell", s, (255, 244, 220), tris=4500)
        m.add("Spots", lift.intersect(spots(s, 18, 0.11, 0.21, seed=3)), (196, 146, 98), role="detail", tris=2500)
        m.add("Spots2", lift.intersect(spots(s, 14, 0.06, 0.11, seed=11)), (226, 186, 140), role="detail", tris=1500)
    elif kind == "Legendary":
        m.add("Shell", s, (255, 178, 30), material="Foil", tris=4500)
        thin = s.offset(-0.07)
        outer = lift.subtract(thin).intersect(flames(0.0, 1.55, 7)).intersect(band(0.12, 9, 0, 0))
        inner = s.offset(0.028).subtract(thin).intersect(flames(0.0, 0.95, 7)).intersect(band(0.12, 9, 0, 0))
        m.add("Flames", outer, (255, 84, 20), material="Neon", role="glow", tris=3500)
        m.add("FlamesInner", inner, (255, 214, 60), material="Neon", role="glow", tris=2500)
        m.add("Band", lift.subtract(thin).intersect(band(1.92, 2.2, 0.09, 12, 0.0, sharp=True)), (178, 20, 44), role="detail", tris=2500)
        m.add("Gems", gem_ring(s, 6, 2.06, 0.36, phase=math.pi / 12), (255, 36, 72), material="Glass", role="glow", tris=1800, voxel=0.015)
    elif kind == "Uncommon":
        m.add("Shell", s, (132, 226, 108), tris=4500)
        m.add("Band", paint.intersect(k=0.012, other=band(1.18, 1.52, 0.11, 6, 0.3)), (40, 164, 74), role="detail", tris=2500, voxel=0.013)
        m.add("Band2", paint.intersect(k=0.012, other=band(0.62, 0.72, 0.06, 6, 0.3 + math.pi)), (40, 164, 74), role="detail", tris=2200, voxel=0.013)
        m.add("Dots", paint.intersect(spots(s, 16, 0.07, 0.13, seed=21)).subtract(band(0.55, 1.6)), (236, 255, 212), role="detail", tris=2200, voxel=0.013)
    elif kind == "Rare":
        m.add("Shell", s, (88, 182, 255), tris=4500)
        m.add("Zigzag", paint.intersect(k=0.012, other=union(band(0.8, 1.0, 0.1, 9, 0.0, sharp=True), band(2.05, 2.22, 0.08, 9, 0.5, sharp=True))),
              (26, 98, 216), role="detail", tris=3000, voxel=0.013)
        m.add("Sparkles", sparkles(s, 9, 0.2, seed=5), (246, 252, 255), role="detail", tris=2200, voxel=0.015)
        m.add("Dots", paint.intersect(spots(s, 12, 0.05, 0.09, seed=8)).subtract(union(band(0.7, 1.1), band(1.95, 2.32))),
              (196, 232, 255), role="detail", tris=2200, voxel=0.013)
    elif kind == "Epic":
        m.add("Shell", s, (170, 102, 250), tris=4500)
        m.add("Band", paint.intersect(k=0.012, other=band(1.05, 1.32, 0.1, 8, 0.0, sharp=True)), (96, 40, 190), role="detail", tris=2500, voxel=0.013)
        big, small = crystals(s, 5, seed=17, length=1.0, width=0.25, zmin=0.3, zmax=0.7)
        m.add("Crystals", big, (196, 150, 255), material="Glass", role="detail", tris=2400, voxel=0.012, smooth=False)
        m.add("CrystalsSmall", small, (255, 120, 236), material="Neon", role="glow", tris=1800, voxel=0.012, smooth=False)
        m.add("Dots", paint.intersect(spots(s, 10, 0.05, 0.1, seed=30, zmin=-0.85, zmax=0.2)), (220, 190, 255), role="detail", tris=2200, voxel=0.013)
    elif kind == "Mythic":
        m.add("Shell", s, (226, 38, 52), tris=4500)
        m.add("Cracks", cracks(s, 11, seed=12), (255, 176, 44), material="Neon", role="glow", tris=4000, voxel=0.014)
        m.add("Glow", paint.intersect(spots(s, 9, 0.12, 0.2, seed=44, zmin=-0.5, zmax=0.7)), (255, 96, 40), material="Neon", role="glow", tris=1800, voxel=0.014)
        m.add("Base", paint.intersect(k=0.012, other=band(-0.2, 0.42, 0.08, 7, 0.0, sharp=True)), (40, 14, 26), role="detail", tris=2200, voxel=0.013)
    elif kind == "Divine":
        m.add("Shell", s, (255, 238, 250), reflectance=0.1, tris=4500)
        colors = [(255, 96, 110), (255, 170, 70), (255, 226, 80), (110, 226, 120), (90, 190, 255), (178, 120, 255)]
        for i, c in enumerate(colors):
            z0 = 0.95 + i * 0.17
            m.add(f"Rainbow{i + 1}", paint.intersect(k=0.012, other=band(z0, z0 + 0.15, 0.1, 5, 0.0)), c, role="detail", tris=1200, voxel=0.013)
        m.add("Halo", torus(0.62, 0.075, (0, 0, H + 0.32)), (255, 222, 96), material="Neon", role="glow", tris=1200, voxel=0.015)
        m.add("Wings", union(wing(1), wing(-1)), (255, 255, 255), role="detail", tris=2400, voxel=0.016)
        m.add("Sparkles", sparkles(s, 6, 0.17, seed=3, zmin=0.3, zmax=0.95), (255, 214, 90), role="detail", tris=1400, voxel=0.015)
    elif kind == "Secret":
        m.add("Shell", s, (34, 22, 62), reflectance=0.12, tris=4500)
        m.add("SwirlA", paint.intersect(spiral(1.15, 0.55)), (60, 236, 220), material="Neon", role="glow", tris=3000)
        m.add("SwirlB", paint.intersect(spiral(1.15, 0.3, math.pi)), (232, 80, 230), material="Neon", role="glow", tris=2600)
        m.add("Stars", s.offset(0.02).intersect(spots(s, 40, 0.025, 0.05, seed=77)), (235, 255, 255), material="Neon", role="glow", tris=2500, voxel=0.012)
        ring = torus(R + 0.42, 0.06).rot(68, 0, 18).translate(CENTER)
        m.add("Ring", ring, (120, 255, 240), material="Neon", role="glow", tris=1400, voxel=0.015)
    else:
        raise SystemExit(f"Rarita' sconosciuta: {kind}")
    m.meta["rarity"] = kind
    return m


if __name__ == "__main__":
    for kind in sys.argv[1:]:
        build(kind).build(views=tuple(os.environ.get("VIEWS", "3q").split(",")), res=int(os.environ.get("RES", 700)))
