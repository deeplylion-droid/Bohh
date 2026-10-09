"""Kit ambiente: rocce, pini, cespugli, fiori, ciuffi d'erba, nido.

Ogni funzione ritorna un Model pronto per l'esportazione (e riusabile nelle scene).
Uso: python env/kit.py Rock1 PineTree ...  (oppure "all")
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.sdf import (SDF, bezier, capsule, cylinder, ellipsoid, sphere, torus,  # noqa: E402
                     tube, union)
from common import (GROUND, Prop, ceiling, facet_blob, fast_union, ground, noisy, run,  # noqa: E402
                    star_tier, surface_crack)

# ------------------------------------------------------------------------------ rocce

# colori naturali poco saturi: ardesia grigio-blu, grigio caldo, grigio-bruno
ROCK_COLORS = {1: (116, 124, 138), 2: (132, 128, 122), 3: (124, 112, 98)}
PEBBLE_COLORS = {1: (92, 98, 110), 2: (104, 100, 96), 3: (98, 88, 78)}


def rock_body(i: int) -> SDF:
    """Massi spigolosi: blocchi convessi a facce piatte uniti, con punte e crepe."""
    if i == 1:  # masso largo con una cresta appuntita su un lato
        main = facet_blob((0, 0, 0.75), (2.0, 1.35, 1.2), n=15, seed=11, depth=(0.78, 1.0), rot=(0, 0, 12))
        peak = facet_blob((0.75, 0.15, 1.35), (1.05, 0.9, 1.5), n=11, seed=12, zmax=0.55, top=1.5, rot=(0, -12, 30))
        side = facet_blob((-1.45, -0.35, 0.45), (0.8, 0.75, 0.75), n=10, seed=13, rot=(0, 15, -20))
        body = union(main, peak, side)
        cracks = [((0.2, 0, 1.0), (0.3, -1, 0.35), (0.2, 0.1, 1), 0.9),
                  ((-0.6, 0, 0.8), (-0.6, -1, 0.5), (1, 0, -0.4), 0.8)]
    elif i == 2:  # dente alto e appuntito con un blocco ai piedi
        main = facet_blob((0, 0, 1.15), (1.35, 1.2, 1.75), n=14, seed=21, zmax=0.6, top=1.4, depth=(0.8, 1.0), rot=(0, 8, 20))
        foot = facet_blob((0.9, -0.5, 0.4), (0.95, 0.85, 0.65), n=10, seed=22, rot=(0, -10, 40))
        back = facet_blob((-0.75, 0.55, 0.6), (0.9, 0.8, 0.95), n=10, seed=23, zmax=0.7, rot=(0, 12, -15))
        body = union(main, foot, back)
        cracks = [((0, 0, 1.4), (0.4, -1, 0.1), (0.15, 0, 1), 1.1),
                  ((0.2, 0, 0.9), (1, 0.2, 0.3), (0.2, 0.3, 1), 0.7)]
    else:  # masso spaccato: due meta' separate da una fessura, sommita' scheggiata
        a = facet_blob((-0.55, 0, 0.8), (1.25, 1.35, 1.15), n=13, seed=31, depth=(0.8, 1.0), rot=(0, 0, 5))
        b = facet_blob((0.75, 0.1, 0.7), (1.1, 1.25, 1.05), n=13, seed=32, depth=(0.8, 1.0), rot=(0, 0, -8))
        split = facet_blob((0.12, 0, 1.1), (0.09, 2.0, 1.6), n=6, seed=33, rot=(0, -8, 4))
        body = union(a, b).subtract(split)
        cracks = [((-0.6, 0, 0.9), (-0.3, -1, 0.3), (0.3, 0, 1), 0.9),
                  ((0.8, 0, 0.8), (0.5, -1, 0.6), (1, 0, 0.2), 0.7)]
    body = body.intersect(ground())
    for inside, d, along, ln in cracks:
        body = body.subtract(surface_crack(body, inside, d, along, depth=0.22, width=0.07, length=ln, zigzag=2, seed=len(cracks)))
    return body


def rock(i: int) -> Prop:
    m = Prop(f"Rock{i}", voxel=0.025)
    body = rock_body(i)
    m.add("Rock", body, ROCK_COLORS[i], tris=520, smooth=False)
    # schegge ai piedi del masso (tono piu' scuro)
    rng = np.random.default_rng(140 + i)
    chips = []
    for k in range(3):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(1.6, 2.1)
        c = (r * math.cos(a), r * math.sin(a) * 0.8, 0.0)
        chips.append(facet_blob(c, (rng.uniform(0.22, 0.36), rng.uniform(0.18, 0.3), rng.uniform(0.16, 0.26)), n=8,
                                seed=150 + 10 * i + k, rot=(0, 0, rng.uniform(0, 180))))
    pebbles = union(*chips).intersect(ground()).subtract(body.offset(0.02))
    m.add("Chips", pebbles, PEBBLE_COLORS[i], role="detail", tris=160, smooth=False)
    return m


def rock_spire() -> Prop:
    """Pinnacolo di roccia alto e frastagliato (~7) per pareti e bordi del sentiero."""
    m = Prop("RockSpire", voxel=0.035)
    base = facet_blob((0, 0, 0.7), (2.0, 1.7, 1.25), n=15, seed=501, depth=(0.78, 1.0), rot=(0, 0, 15))
    mid = facet_blob((0.15, 0.05, 2.7), (1.3, 1.1, 2.2), n=13, seed=502, zmax=0.65, depth=(0.8, 1.0), rot=(0, 5, 35))
    top = facet_blob((0.35, 0.1, 5.0), (0.85, 0.75, 2.1), n=11, seed=503, zmax=0.45, top=1.6, rot=(0, 7, 70))
    spur = facet_blob((-0.95, 0.35, 2.4), (0.6, 0.55, 1.6), n=10, seed=504, zmax=0.45, top=1.6, rot=(0, -16, 10))
    ledge = facet_blob((1.05, -0.55, 1.45), (0.75, 0.6, 0.55), n=9, seed=505, rot=(0, 10, -25))
    body = union(base, mid, top, spur, ledge).intersect(ground())
    for inside, d, along, ln, s in [((0.2, 0, 3.2), (0.3, -1, 0), (0.1, 0, 1), 1.8, 1),
                                    ((0.3, 0, 5.0), (1, -0.4, 0), (0, 0.2, 1), 1.2, 2),
                                    ((0, 0, 1.0), (-0.6, -1, 0.2), (1, 0, 0.3), 1.2, 3)]:
        body = body.subtract(surface_crack(body, inside, d, along, depth=0.28, width=0.09, length=ln, zigzag=2, seed=s))
    m.add("Rock", body, (112, 118, 130), tris=1150, smooth=False)
    rng = np.random.default_rng(510)
    chips = []
    for k in range(4):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(1.9, 2.4)
        chips.append(facet_blob((r * math.cos(a), r * math.sin(a), 0.0), (rng.uniform(0.28, 0.45), rng.uniform(0.22, 0.35),
                                rng.uniform(0.2, 0.32)), n=8, seed=520 + k, rot=(0, 0, rng.uniform(0, 180))))
    m.add("Chips", union(*chips).intersect(ground()).subtract(body.offset(0.02)), (92, 96, 106), role="detail", tris=200, smooth=False)
    return m


def rock_shards() -> Prop:
    """Gruppo di 3-4 lame di roccia appuntite e inclinate (~3)."""
    m = Prop("RockShards", voxel=0.025)
    blades = [  # centro, raggi (largo, sottile, alto), rotazione
        ((0.0, 0.1, 1.3), (0.62, 0.28, 1.65), (8, -6, 15)),
        ((0.75, -0.35, 0.95), (0.5, 0.24, 1.25), (-10, 24, 60)),
        ((-0.7, -0.15, 0.85), (0.48, 0.22, 1.1), (6, -26, -35)),
        ((0.2, 0.75, 0.75), (0.45, 0.22, 0.95), (-22, 8, 100)),
    ]
    shards = [facet_blob(c, r, n=10, seed=600 + k, zmax=0.35, top=1.7, depth=(0.85, 1.0), rot=rot)
              for k, (c, r, rot) in enumerate(blades)]
    body = union(*shards).intersect(ground())
    for inside, d, along, ln, s in [((0, 0.1, 1.4), (0.2, -1, 0), (0, 0, 1), 1.0, 1),
                                    ((0.8, -0.35, 0.9), (0.6, -1, 0), (0.3, 0, 1), 0.7, 2)]:
        body = body.subtract(surface_crack(body, inside, d, along, depth=0.12, width=0.05, length=ln, zigzag=1, seed=s))
    m.add("Rock", body, (110, 116, 128), tris=620, smooth=False)
    base = facet_blob((0.05, 0.1, -0.05), (1.25, 1.05, 0.35), n=12, seed=640, rot=(0, 0, 20)).intersect(ground())
    m.add("Base", base.subtract(body.offset(0.01)), (94, 98, 108), role="detail", tris=180, smooth=False)
    return m


# ------------------------------------------------------------------------------ pini

# palchi (base, altezza, raggio, punte): coni con bordo a stella e punte dei rami che scendono
PINE_TIERS = [(1.2, 2.45, 2.5, 9), (2.3, 2.3, 2.1, 8), (3.35, 2.15, 1.72, 8), (4.35, 1.95, 1.34, 7), (5.3, 1.95, 0.95, 6)]


def pine_tiers():
    tiers = []
    for k, (z, h, r, n) in enumerate(PINE_TIERS):
        twist = (k * 0.5 + 0.13 * k) * 2 * math.pi / n
        tiers.append((star_tier(z, h, r, n=n, notch=0.36, droop=0.32 * r / 2.5 + 0.08, lift=0.5 * r / 2.5, twist=twist), z, h, r, n, twist))
    return tiers


def pine(name="PineTree", leaf=(44, 104, 62)) -> Prop:
    m = Prop(name, voxel=0.03)
    tiers = pine_tiers()
    leaves = union(*[t[0] for t in tiers])
    m.add("Leaves", leaves, leaf, tris=1150, smooth=False)
    trunk = cylinder((0, 0, GROUND), (0, 0, 2.0), 0.36, round=0.04)
    roots = union(*[capsule((0, 0, 0.35), (0.55 * math.cos(a), 0.55 * math.sin(a), GROUND + 0.05), 0.16)
                    for a in (0.4, 2.5, 4.4)])
    m.add("Trunk", union(trunk, roots, k=0.15).intersect(ground()), (92, 64, 44), material="Wood", role="detail", tris=180, smooth=False)
    return m


def _spike(p, n, twist):
    th = np.arctan2(p[:, 1], p[:, 0]) + twist
    u = (th * n / (2 * math.pi)) % 1.0
    return np.abs(2 * u - 1)


def pine_snowy() -> Prop:
    """Abete innevato: neve spessa sopra ogni palco, che scende lungo i rami; punta imbiancata."""
    m = pine("PineSnowy", leaf=(38, 92, 70))
    tiers = pine_tiers()
    snow = []
    for k, (tier, z, h, r, n, twist) in enumerate(tiers):
        droop = 0.32 * r / 2.5 + 0.08
        if k + 1 < len(tiers):
            z_next = tiers[k + 1][1]
            z_lo = z - droop * 0.55 + 0.12  # sulle creste dei rami la neve arriva quasi alla punta
            z_hi = z + (z_next - z) * 0.5   # negli incavi resta piu' in alto
            top = z_next + 0.35
        else:
            z_lo = z + h * 0.35
            z_hi = z + h * 0.55
            top = z + h + 1.0

        def edge(p, n=n, twist=twist, z_lo=z_lo, z_hi=z_hi):
            s = _spike(p, n, twist)
            return z_hi - (z_hi - z_lo) * s ** 1.6 - p[:, 2]

        region = SDF(edge, (-r - 1, -r - 1, z_lo - 0.1), (r + 1, r + 1, top))
        snow.append(tier.offset(0.13).intersect(region, k=0.06).intersect(ceiling(top)))
    m.add("Snow", union(*snow), (240, 246, 252), role="detail", tris=1050, smooth=False)
    return m


# ------------------------------------------------------------------------------ cespuglio

def bush(i: int = 1) -> Prop:
    """Cespuglio tondeggiante fatto di ciuffi di foglie low-poly in due verdi, con qualche bacca."""
    m = Prop(f"Bush{i}", voxel=0.03)
    dark = [((-0.95, 0.35, 0.65), (0.95, 0.85, 0.8)), ((0.95, 0.4, 0.6), (0.9, 0.8, 0.75)),
            ((0.05, 0.75, 0.85), (1.05, 0.85, 0.95)), ((-0.45, -0.55, 0.45), (0.8, 0.7, 0.62)),
            ((0.6, -0.55, 0.42), (0.75, 0.68, 0.6))]
    light = [((0.05, -0.05, 1.35), (0.95, 0.85, 0.75)), ((-0.75, -0.3, 1.05), (0.72, 0.66, 0.62)),
             ((0.8, -0.2, 1.0), (0.7, 0.65, 0.6)), ((0.1, -0.8, 0.8), (0.62, 0.55, 0.55))]
    dk = union(*[facet_blob(c, r, n=18, seed=200 + k, depth=(0.86, 1.0), rot=(0, 0, 37 * k)) for k, (c, r) in enumerate(dark)])
    lt = union(*[facet_blob(c, r, n=18, seed=220 + k, depth=(0.86, 1.0), rot=(0, 0, 53 * k)) for k, (c, r) in enumerate(light)])
    dk = dk.intersect(ground())
    m.add("Leaves", dk, (52, 98, 50), tris=420, smooth=False)
    m.add("LeavesLight", lt, (78, 124, 58), role="detail", tris=330, smooth=False)
    berries = []
    for c, d in [((0.1, -0.8, 0.8), (-0.3, -1, 0.5)), ((0.8, -0.2, 1.0), (0.4, -1, 0.3)), ((-0.75, -0.3, 1.05), (-0.6, -1, 0.6)),
                 ((0.05, -0.05, 1.35), (0.3, -0.6, 1)), ((-0.45, -0.55, 0.45), (-0.2, -1, -0.1)), ((0.6, -0.55, 0.42), (0.7, -1, 0.1))]:
        d = np.asarray(d, dtype=np.float64)
        d /= np.linalg.norm(d)
        # punto sulla superficie del ciuffo: si cerca lungo la direzione d
        shape = union(dk, lt)
        t = 0.0
        while shape(np.asarray([np.asarray(c) + d * t], dtype=np.float32))[0] < 0 and t < 2:
            t += 0.02
        p = np.asarray(c) + d * (t - 0.05)
        berries.append(facet_blob(p, (0.12, 0.12, 0.12), n=9, seed=int(t * 100)))
    m.add("Berries", union(*berries), (140, 30, 40), role="detail", tris=130, smooth=False)
    return m


# ------------------------------------------------------------------------------ fiori ed erba

def flower_patch(i: int = 1) -> Prop:
    """Gruppo di fiorellini a 5 petali su steli corti."""
    m = Prop(f"Flowers{i}", voxel=0.02)
    rng = np.random.default_rng(300 + i)
    palettes = [((255, 255, 255), (255, 210, 60)), ((255, 140, 190), (255, 240, 120)), ((170, 140, 255), (255, 230, 120))]
    petals_by_color = {}
    centers, stems = [], []
    for k in range(7):
        x, y = rng.uniform(-1.1, 1.1), rng.uniform(-1.1, 1.1)
        h = rng.uniform(0.45, 0.75)
        pet_col, cen_col = palettes[rng.integers(0, 3)]
        stems.append(capsule((x, y, GROUND), (x, y, h), 0.035))
        ring = [sphere(0.13, (x + 0.16 * math.cos(a), y + 0.16 * math.sin(a), h)) for a in np.linspace(0, 2 * math.pi, 6)[:-1]]
        petals_by_color.setdefault(pet_col, []).append(union(*ring).warp(lambda p, h=h: p * np.array([1, 1, 2.2], dtype=np.float32) - np.array([0, 0, h * 1.2], dtype=np.float32), pad=0.2))
        centers.append(sphere(0.08, (x, y, h + 0.03)))
    m.add("Stems", fast_union(*stems), (70, 150, 70), tris=150)
    per_color = 840 // len(petals_by_color)
    for idx, (col, shapes) in enumerate(petals_by_color.items()):
        m.add(f"Petals{idx}", fast_union(*shapes), col, role="detail", tris=per_color)
    m.add("Centers", fast_union(*centers), (255, 205, 50), role="detail", tris=140)
    return m


def grass_tuft(i: int = 1) -> Prop:
    m = Prop(f"Grass{i}", voxel=0.012)
    rng = np.random.default_rng(400 + i)
    blades = []
    for k in range(9):
        a = rng.uniform(0, 2 * math.pi)
        lean = rng.uniform(0.15, 0.4)
        h = rng.uniform(0.5, 0.85)
        x, y = 0.12 * math.cos(a), 0.12 * math.sin(a)
        blades.append(tube(bezier((x, y, GROUND), (x, y, h * 0.5), (x + lean * math.cos(a) * 0.6, y + lean * math.sin(a) * 0.6, h * 0.9),
                                  (x + lean * math.cos(a), y + lean * math.sin(a), h), 6), [0.06, 0.055, 0.045, 0.035, 0.025, 0.016, 0.01]))
    m.add("Blades", fast_union(*blades, k=0.02), (96, 196, 76), tris=380)
    return m


# ------------------------------------------------------------------------------ nido

NEST_R = 1.42   # raggio dell'anello di rametti
NEST_ZC = 0.76  # altezza del centro dell'anello


def nest() -> Prop:
    """Nido: ciotola bassa, bordo intrecciato di rametti, paglia dorata dentro.

    L'uovo appoggia a z = 0.55 (NestService): il fondo di paglia sta a z ~0.5.
    """
    m = Prop("Nest", voxel=0.02)
    # ciotola: fondo arrotondato appena sotto terra, sale fino sotto l'anello
    bowl = ellipsoid((1.62, 1.62, 0.9), (0, 0, 0.62)).intersect(ground(-0.15)).intersect(ceiling(0.7))
    core = torus(NEST_R, 0.24, (0, 0, NEST_ZC))
    body = noisy(union(bowl, core, k=0.15), 0.025, 6.0, 5)
    m.add("Bowl", body, (122, 84, 50), tris=420, smooth=False)
    # rametti: archi inclinati alternati che si incrociano attorno al bordo (effetto intrecciato)
    twigs = []
    n = 14
    for k in range(n):
        a0 = 2 * math.pi * k / n
        span = 2 * math.pi / n * 1.55
        sgn = 1 if k % 2 == 0 else -1
        rr = NEST_R + (0.13 if k % 2 == 0 else 0.02)
        pts, rad = [], []
        for j in range(7):
            t = j / 6
            a = a0 + span * (t - 0.5)
            z = NEST_ZC + sgn * 0.17 * (2 * t - 1) + 0.06 * math.sin(math.pi * t)
            r = rr + 0.07 * math.sin(math.pi * t)
            pts.append((r * math.cos(a), r * math.sin(a), z))
            rad.append(0.1 + 0.03 * math.sin(math.pi * t))
        twigs.append(tube(pts, rad))
        # secondo giro sul lato interno-alto del bordo
        if k % 2 == 0:
            a = a0 + math.pi / n
            p0 = ((NEST_R - 0.12) * math.cos(a - 0.3), (NEST_R - 0.12) * math.sin(a - 0.3), NEST_ZC + 0.16)
            p1 = ((NEST_R - 0.05) * math.cos(a + 0.3), (NEST_R - 0.05) * math.sin(a + 0.3), NEST_ZC + 0.24)
            twigs.append(capsule(p0, p1, 0.085))
    # qualche rametto che sporge, con una forchetta
    for a, dz, ln in [(0.6, 0.1, 0.75), (2.3, -0.05, 0.6), (3.9, 0.12, 0.7), (5.2, 0.0, 0.65)]:
        p0 = (NEST_R * math.cos(a), NEST_R * math.sin(a), NEST_ZC)
        d = (math.cos(a + 0.5), math.sin(a + 0.5))
        p1 = (p0[0] + d[0] * ln, p0[1] + d[1] * ln, p0[2] + dz + 0.15)
        p2 = (p1[0] + math.cos(a + 1.1) * 0.25, p1[1] + math.sin(a + 1.1) * 0.25, p1[2] + 0.12)
        twigs.append(tube([p0, p1], [0.07, 0.045]))
        twigs.append(tube([lerp3(p0, p1, 0.6), p2], [0.04, 0.03]))
    m.add("Twigs", fast_union(*twigs), (168, 118, 70), role="detail", tris=1150, smooth=False)
    # paglia: letto concavo (fondo a z 0.5) e qualche filo che scavalca il bordo
    def straw_bed(p):
        rho = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2)
        top = 0.5 + 0.2 * (rho / 1.15) ** 2
        return np.maximum(np.maximum(p[:, 2] - top, 0.25 - p[:, 2]), rho - 1.3)
    bed = noisy(SDF(straw_bed, (-1.35, -1.35, 0.2), (1.35, 1.35, 0.85)), 0.02, 9.0, 3)
    strands = []
    rng = np.random.default_rng(77)
    for k in range(9):
        a = rng.uniform(0, 2 * math.pi)
        r0 = rng.uniform(0.5, 0.9)
        p0 = (r0 * math.cos(a), r0 * math.sin(a), 0.62)
        a1 = a + rng.uniform(-0.5, 0.5)
        p1 = (1.3 * math.cos(a1), 1.3 * math.sin(a1), NEST_ZC + 0.32)
        p2 = (1.75 * math.cos(a1 + 0.1), 1.75 * math.sin(a1 + 0.1), NEST_ZC + rng.uniform(-0.05, 0.25))
        strands.append(tube([p0, p1, p2], [0.035, 0.035, 0.025]))
    m.add("Straw", fast_union(bed, *strands), (222, 182, 96), role="detail", tris=520, smooth=False)
    return m


def lerp3(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


CATALOG = {
    "Rock1": lambda: rock(1), "Rock2": lambda: rock(2), "Rock3": lambda: rock(3),
    "RockSpire": rock_spire, "RockShards": rock_shards,
    "PineTree": lambda: pine(), "PineSnowy": pine_snowy,
    "Bush1": lambda: bush(1), "Flowers1": lambda: flower_patch(1), "Flowers2": lambda: flower_patch(2),
    "Grass1": lambda: grass_tuft(1), "Nest": nest,
}

if __name__ == "__main__":
    run(CATALOG)
