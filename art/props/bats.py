"""Mazze comiche per schiaffeggiare i ladri (kind "bat"), misure reali in stud.

Convenzione delle mazze: l'estremita' dell'impugnatura e' nell'origine, l'arma si allunga lungo +Z
(Blender) per ~4.2 ed e' centrata su x = 0, y = 0; il lato "bello" guarda verso -Y.

  BatRubberMallet  martello di gomma rosso, manico di legno con impugnatura fasciata
  BatBaguette      baguette dorata con tagli diagonali e incarto di carta all'impugnatura
  BatFrozenFish    pesce blu congelato (tenuto per la coda) in un blocco di ghiaccio, faccia stordita
  BatCandyCane     grande bastoncino di zucchero a spirale bianca e rossa, uncino in cima
  BatGiantSpoon    cucchiaio gigante d'argento lucido (Metal)
  BatGoldenMallet  martello VIP d'oro (Foil) con gemme rosse

Uso: python props/bats.py [Nome ...]
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.sdf import (SDF, box, capped_cone, crystal, cylinder, ellipsoid, project, round_cone, sphere,  # noqa: E402
                     torus, tube, union)
from propkit import FineModel, convex, face_prism, paint, run, unit  # noqa: E402

WHITE = (255, 255, 255)


def helix_wrap(z0: float, z1: float, r: float, turns: float, thick: float, phase: float = 0.0, n: int = 60) -> SDF:
    """Fascia elicoidale (nastro avvolto) attorno all'asse Z fra z0 e z1."""
    pts = []
    for i in range(n + 1):
        t = i / n
        a = phase + 2 * math.pi * turns * t
        pts.append((r * math.cos(a), r * math.sin(a), z0 + (z1 - z0) * t))
    return tube(pts, thick)


def mallet_head(zc: float, r: float, half: float, rnd: float) -> SDF:
    """Testa di martello: cilindro lungo X con bordi arrotondati e facce appena bombate."""
    body = cylinder((-half, 0, zc), (half, 0, zc), r, round=rnd)
    domes = union(*[ellipsoid((0.12, r * 0.86, r * 0.86), (sx * (half - 0.06), 0, zc)) for sx in (1, -1)])
    return union(body, domes, k=0.05)


# ================================================================================ BatRubberMallet

def rubber_mallet() -> FineModel:
    m = FineModel("BatRubberMallet", "bat", voxel=0.012)
    zc, r, half = 3.62, 0.56, 0.78
    head = mallet_head(zc, r, half, 0.16)
    faces = union(*[box((0.08, r, r), (sx * half, 0, zc)) for sx in (1, -1)])
    m.add("Head", head, (228, 40, 44), tris=1300)
    m.add("Faces", head.offset(0.014).intersect(faces), (150, 18, 30), role="detail", tris=700)
    handle = union(round_cone((0, 0, 0.18), (0, 0, zc), 0.145, 0.12), sphere(0.2, (0, 0, 0.17)), k=0.06)
    m.add("Handle", handle.subtract(head.offset(-0.02)), (206, 150, 92), material="Wood", role="detail", tris=700)
    sleeve = capped_cone((0, 0, 0.3), (0, 0, 1.35), 0.17, 0.162, round=0.03)
    wraps = union(helix_wrap(0.36, 1.3, 0.165, 4.5, 0.032), helix_wrap(0.36, 1.3, 0.165, 4.5, 0.032, phase=math.pi))
    m.add("Grip", union(sleeve, wraps), (40, 40, 52), material="Fabric", role="detail", tris=1000, voxel=0.009)
    return m


# ================================================================================ BatBaguette

def baguette() -> FineModel:
    m = FineModel("BatBaguette", "bat", voxel=0.014)

    def loaf_profile(z):
        """Raggio della baguette lungo Z: estremita' arrotondate, appena piu' sottile verso l'impugnatura."""
        t = np.clip(z / 4.2, 0, 1)
        end = np.sqrt(np.clip(np.minimum(t, 1 - t) / 0.06, 0, 1))
        return (0.3 + 0.05 * t) * (0.25 + 0.75 * end)

    def loaf_f(p):
        z = p[:, 2]
        r = loaf_profile(z)
        q = np.sqrt((p[:, 0] / 1.0) ** 2 + (p[:, 1] / 0.86) ** 2)  # sezione un po' schiacciata
        d = (q - r) * 0.86
        return np.maximum(d, np.maximum(-z, z - 4.2))

    loaf = SDF(loaf_f, (-0.45, -0.4, -0.02), (0.45, 0.4, 4.22))
    # tagli diagonali sul davanti (-Y): solchi con la mollica chiara sul fondo
    cuts = []
    for i in range(5):
        zc = 1.75 + i * 0.5
        a = np.array((0.19, -0.27, zc - 0.2))
        b = np.array((-0.19, -0.27, zc + 0.2))
        cuts.append(round_cone(tuple(a), tuple(b), 0.065, 0.065))
    cuts = union(*cuts)
    m.add("Bread", loaf.subtract(cuts, k=0.03), (212, 136, 56), tris=1800)
    m.add("Crumb", loaf.offset(-0.03).intersect(cuts.offset(0.01)), (250, 222, 160), role="detail", tris=600,
          voxel=0.01)
    # incarto di carta: manicotto svasato con il bordo a zig-zag, e due righe rosse
    def paper_f(p):
        z = p[:, 2]
        th = np.arctan2(p[:, 1], p[:, 0])
        top = 1.28 + 0.07 * (2 / math.pi) * np.arcsin(np.sin(9 * th))
        r_out = 0.36 + 0.06 * np.clip(z / 1.3, 0, 1) + 0.02
        rho = np.sqrt(p[:, 0] ** 2 + (p[:, 1] / 0.9) ** 2)
        wall = np.abs(rho - r_out + 0.03) - 0.03
        return np.maximum(wall, np.maximum(-z, z - top))

    paper = SDF(paper_f, (-0.5, -0.5, -0.05), (0.5, 0.5, 1.4))
    bottom = capped_cone((0, 0, 0.0), (0, 0, 0.14), 0.33, 0.37, round=0.03)
    stripes = union(*[box((0.6, 0.6, 0.035), (0, 0, z)) for z in (0.62, 0.8)])
    paper_all = union(paper, bottom)
    m.add("Paper", paper_all, (246, 242, 232), role="detail", tris=900, voxel=0.01)
    m.add("Stripes", paper_all.offset(0.01).intersect(stripes), (214, 44, 52), role="detail", tris=400, voxel=0.008)
    return m


# ================================================================================ BatFrozenFish

FISH_BLUE = (58, 128, 226)
FISH_FIN = (40, 92, 196)
FISH_BELLY = (196, 232, 255)
ICE = (198, 240, 255)


def frozen_fish() -> FineModel:
    m = FineModel("BatFrozenFish", "bat", voxel=0.012)
    # pesce di profilo: fianchi verso -Y/+Y, dorso verso +X, testa in alto, coda (impugnatura) in basso
    body = ellipsoid((0.6, 0.3, 1.25), (0.0, 0, 2.62))
    head = union(ellipsoid((0.55, 0.31, 0.6), (0.02, 0, 3.5)), ellipsoid((0.32, 0.23, 0.28), (-0.06, 0, 3.93)), k=0.25)
    peduncle = round_cone((0, 0, 0.62), (0, 0, 1.6), 0.15, 0.3)
    fish = union(body, head, k=0.25)
    fish = union(fish, peduncle, k=0.2)
    # bocca spalancata sulla punta del muso (intaglio a V)
    mouth_cut = face_prism([(0.24, 4.36), (-0.02, 3.97), (-0.5, 4.3)], -0.6, 0.6, round=0.02)
    fish = fish.subtract(mouth_cut, k=0.035)
    tail = face_prism([(0.0, 0.85), (0.58, 0.02), (0.22, 0.22), (0.0, 0.42), (-0.22, 0.22), (-0.58, 0.02)], -0.07, 0.07,
                      round=0.05)
    dorsal = face_prism([(0.45, 2.0), (0.92, 2.25), (0.86, 2.8), (0.5, 3.1)], -0.06, 0.06, round=0.04)
    ventral = face_prism([(-0.42, 1.75), (-0.75, 1.95), (-0.5, 2.3)], -0.05, 0.05, round=0.03)
    pect = [ellipsoid((0.2, 0.06, 0.34), (0.05, sy * 0.3, 2.95)).rot(0, -25, 0, pivot=(0.05, sy * 0.3, 2.95)) for sy in (1, -1)]
    fins = union(tail, dorsal, ventral, *pect)
    m.add("Fish", union(fish, fins, k=0.04), FISH_BLUE, tris=1450)
    m.add("Belly", paint(fish, box((0.4, 0.5, 1.8), (-0.55, 0, 2.6), round=0.2), t=0.012, depth=0.04),
          FISH_BELLY, role="detail", tris=450, voxel=0.01)
    # faccia stordita ma sfacciata: occhi a spirale e ghigno aperto sulla punta del muso con dentini
    eyes, face = [], []
    for sy in (-1, 1):
        c, n = project(head, (0.12, 0, 3.58), (0, sy, 0.05))
        eyes.append(ellipsoid((0.22, 0.05, 0.22), tuple(c)))
        spiral = []
        for i in range(36):
            t = i / 35
            a = 2 * math.pi * 2.3 * t
            rr = 0.02 + 0.16 * t
            spiral.append(tuple(c + n * 0.045 + np.array((rr * math.cos(a), 0.0, rr * math.sin(a)))))
        face.append(tube(spiral, 0.017))
    face.append(paint(fish, mouth_cut.offset(0.045), t=0.014, depth=0.05))
    teeth = [round_cone((0.05, sy * 0.1, 4.08), (-0.03, sy * 0.1, 4.1), 0.035, 0.008) for sy in (-1, 1)]
    eyes.extend(teeth)
    m.add("EyeWhites", union(*eyes), WHITE, role="shine", tris=380, voxel=0.007)
    m.add("Face", union(*face), (24, 20, 44), role="eye", tris=620, voxel=0.007)
    # blocco di ghiaccio sfaccettato attorno al corpo (la testa sbuca fuori)
    rng = np.random.default_rng(5)
    dirs, offs = [], []
    for k in range(16):
        a = 2 * math.pi * k / 16 + rng.uniform(-0.15, 0.15)
        tz = rng.uniform(-0.35, 0.35)
        d = unit((math.cos(a), math.sin(a) * 1.5, tz))
        dirs.append(d)
        offs.append(float(np.linalg.norm(d * (1.02, 0.52, 1.0))) * rng.uniform(0.94, 1.0))
    dirs += [unit((0.25, 0.1, -1)), unit((-0.2, -0.1, -1)), unit((0.5, 0.2, 1)), unit((-0.4, -0.2, 1)), unit((0.0, 0.3, 1))]
    offs += [1.0, 1.02, 0.86, 0.9, 0.95]
    block = convex(dirs, offs, (0, 0, 2.25), ext=2.2).intersect(box((1.3, 1.0, 1.1), (0, 0, 2.25)))
    m.add("Ice", block, ICE, material="Ice", role="detail", tris=300, transparency=0.45, smooth=False, voxel=0.015)
    return m


# ================================================================================ BatCandyCane

class CaneCurve:
    """Asse del bastoncino: fusto dritto (asse Z) + uncino a semicerchio verso +X + breve tratto in discesa."""

    def __init__(self, z0: float, z1: float, R: float, tail: float):
        self.z0, self.z1, self.R, self.tail = z0, z1, R, tail
        self.L1 = z1 - z0

    def points(self, n: int = 60):
        pts = [(0.0, 0.0, self.z0), (0.0, 0.0, self.z1)]
        for i in range(1, n + 1):
            phi = math.pi * (1 - i / n)
            pts.append((self.R + self.R * math.cos(phi), 0.0, self.z1 + self.R * math.sin(phi)))
        pts.append((2 * self.R, 0.0, self.z1 - self.tail))
        return pts

    def param(self, p):
        """(arco s, angolo attorno all'asse, distanza dall'asse) per ogni punto."""
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        R, z0, z1 = self.R, self.z0, self.z1
        # fusto
        zs = np.clip(z, z0, z1)
        d1 = np.sqrt(x * x + y * y + (z - zs) ** 2)
        s1 = zs - z0
        n1x, n1z = -1.0, 0.0
        # uncino
        qx, qz = x - R, z - z1
        phi = np.clip(np.arctan2(qz, qx), 0.0, math.pi)
        cx, cz = R + R * np.cos(phi), z1 + R * np.sin(phi)
        d2 = np.sqrt((x - cx) ** 2 + y * y + (z - cz) ** 2)
        s2 = self.L1 + R * (math.pi - phi)
        # coda in discesa
        zt = np.clip(z, z1 - self.tail, z1)
        d3 = np.sqrt((x - 2 * R) ** 2 + y * y + (z - zt) ** 2)
        s3 = self.L1 + math.pi * R + (z1 - zt)
        best = np.argmin(np.stack([d1, d2, d3]), axis=0)
        s = np.choose(best, [s1, s2, s3])
        d = np.choose(best, [d1, d2, d3])
        # vettore radiale nel riferimento (N, Y) dell'asse
        rx = np.choose(best, [x - 0.0, x - cx, x - 2 * R])
        rz = np.choose(best, [z - zs, z - cz, z - zt])
        nx = np.choose(best, [np.full_like(x, n1x), np.cos(phi), np.ones_like(x)])
        nz = np.choose(best, [np.full_like(x, n1z), np.sin(phi), np.zeros_like(x)])
        theta = np.arctan2(y, rx * nx + rz * nz)
        return s, theta, d


def candy_cane() -> FineModel:
    m = FineModel("BatCandyCane", "bat", voxel=0.012)
    rc = 0.27
    curve = CaneCurve(rc, 3.4, 0.5, 0.42)
    cane = tube(curve.points(), rc)
    m.add("Cane", cane, (252, 250, 246), tris=1800, reflectance=0.1)

    def stripe_region(nb: int, pitch: float, width: float, offset: float = 0.0) -> SDF:
        grad = nb * math.sqrt(1 / pitch ** 2 + 1 / (2 * math.pi * rc) ** 2)

        def f(p):
            s, th, _ = curve.param(p)
            u = nb * (s / pitch + th / (2 * math.pi)) + offset
            v = u - np.round(u)
            return (np.abs(v) - width / 2) / grad

        return SDF(f, cane.lo, cane.hi)

    red = paint(cane, stripe_region(3, 2.2, 0.36), t=0.012, depth=0.04)
    thin = paint(cane, stripe_region(3, 2.2, 0.08, offset=0.5), t=0.012, depth=0.04)
    m.add("Stripes", red, (226, 30, 44), role="detail", tris=1500, voxel=0.009)
    m.add("Pinstripes", thin, (36, 160, 84), role="detail", tris=600, voxel=0.008)
    return m


# ================================================================================ BatGiantSpoon

def giant_spoon() -> FineModel:
    m = FineModel("BatGiantSpoon", "bat", voxel=0.012)
    silver = (206, 212, 224)

    def bend(p):
        """Leggera curva a S del profilo (lungo Y in funzione di Z)."""
        q = p.copy()
        z = p[:, 2]
        q[:, 1] = p[:, 1] - 0.12 * np.sin(np.clip((z - 0.4) / 3.2, 0, 1) * math.pi) + 0.1 * np.clip((z - 2.6) / 1.6, 0, 1)
        return q

    bowl_out = union(ellipsoid((0.66, 0.26, 0.82), (0, 0.0, 3.38)), ellipsoid((0.38, 0.2, 0.5), (0, 0.0, 2.84)), k=0.35)
    bowl = bowl_out.subtract(bowl_out.offset(-0.07).translate((0, -0.16, 0.03)), k=0.02)
    outline = [(0.0, 0.0), (0.2, 0.04), (0.27, 0.35), (0.25, 0.75), (0.17, 1.6), (0.105, 2.25), (0.13, 2.5),
               (-0.13, 2.5), (-0.105, 2.25), (-0.17, 1.6), (-0.25, 0.75), (-0.27, 0.35), (-0.2, 0.04)]
    handle = face_prism(outline, -0.075, 0.075, round=0.05)
    spoon = union(handle, bowl, k=0.12).warp(bend, pad=0.15)
    m.add("Spoon", spoon, silver, material="Metal", tris=2400, reflectance=0.2)
    grip_band = box((0.4, 0.3, 0.5), (0, 0, 0.82))
    grooves = union(*[box((0.5, 0.4, 0.018), (0, 0, z)).rot(0, 18, 0, pivot=(0, 0, z)) for z in np.linspace(0.42, 1.22, 7)])
    grip = handle.offset(0.035).intersect(grip_band, k=0.02).subtract(grooves).warp(bend, pad=0.15)
    m.add("Grip", grip, (44, 64, 156), material="Leather", role="detail", tris=900, voxel=0.009)
    return m


# ================================================================================ BatGoldenMallet

def golden_mallet() -> FineModel:
    m = FineModel("BatGoldenMallet", "bat", voxel=0.012)
    gold = (255, 196, 58)
    zc, r, half = 3.62, 0.56, 0.78
    head = mallet_head(zc, r, half, 0.14)
    rings_h = union(*[cylinder((sx * (half - 0.2), 0, zc), (sx * (half - 0.08), 0, zc), r + 0.05, round=0.03) for sx in (1, -1)])
    bezels = union(*[torus(0.3, 0.06).rot(90, 0, 0).translate((0, sy * (r - 0.02), zc)) for sy in (1, -1)])
    handle = union(round_cone((0, 0, 0.2), (0, 0, zc), 0.14, 0.125), k=0.04)
    pommel = sphere(0.23, (0, 0, 0.22))
    bands = union(*[torus(0.15, 0.045, (0, 0, z)) for z in (1.42, 3.0)])
    gold_all = union(head, handle, pommel, k=0.04)
    m.add("Gold", gold_all, gold, material="Foil", tris=1800, reflectance=0.15)
    m.add("Trim", union(rings_h, bezels, bands), (255, 226, 120), material="Foil", role="detail", tris=900)
    sleeve = capped_cone((0, 0, 0.42), (0, 0, 1.36), 0.175, 0.165, round=0.03)
    wraps = union(helix_wrap(0.46, 1.32, 0.17, 3.0, 0.028), helix_wrap(0.46, 1.32, 0.17, 3.0, 0.028, phase=math.pi))
    m.add("Grip", sleeve.subtract(wraps.offset(0.004)), (176, 18, 44), material="Fabric", role="detail", tris=600,
          voxel=0.009)
    gem = crystal(0.28, 0.27, tip=0.55, sides=8)
    gems = [gem.rot(90, 0, 0).translate((0, -(r - 0.06), zc)), gem.rot(-90, 0, 0).translate((0, r - 0.06, zc))]
    m.add("Gem", union(*gems), (232, 26, 58), material="Glass", role="detail", tris=400, voxel=0.008, smooth=False)
    return m


CATALOG = {
    "BatRubberMallet": rubber_mallet,
    "BatBaguette": baguette,
    "BatFrozenFish": frozen_fish,
    "BatCandyCane": candy_cane,
    "BatGiantSpoon": giant_spoon,
    "BatGoldenMallet": golden_mallet,
}

if __name__ == "__main__":
    run(CATALOG)
