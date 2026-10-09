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
from common import (GROUND, Prop, ceiling, cleaved_block, facet_blob, fast_union, ground, noisy,  # noqa: E402
                    run, star_tier, surface_crack)

# ------------------------------------------------------------------------------ rocce

# colori naturali poco saturi: ardesia grigio-blu, grigio caldo, grigio-bruno
ROCK_COLORS = {1: (114, 120, 130), 2: (130, 127, 121), 3: (122, 111, 98)}
PEBBLE_COLORS = {1: (94, 99, 108), 2: (106, 103, 98), 3: (100, 90, 80)}


def rock_body(i: int) -> SDF:
    """Massi spigolosi: blocchi 'spaccati' a facce piatte uniti, con punte, scheggiature e crepe."""
    if i == 1:  # masso largo a cresta con una lastra appuntita appoggiata e un blocco basso
        a = cleaved_block((-0.2, 0, 0.75), (1.55, 1.1, 0.95), seed=101, rot=(0, 0, 10), ridge=0.45, chips=7)
        b = cleaved_block((1.25, 0.25, 1.0), (0.45, 0.9, 1.25), seed=102, rot=(0, -24, 25), peak=0.7, chips=5)
        c = cleaved_block((-1.55, -0.45, 0.35), (0.7, 0.6, 0.45), seed=103, rot=(0, 12, -30), chips=4)
        body = union(a, b, c)
        cracks = [((-0.2, 0, 0.9), (0.1, -1, 0.6), (0.25, 0, -1), 1.5, 3), ((-0.6, 0, 1.0), (-0.3, -0.2, 1), (1, -0.3, 0), 1.2, 4)]
    elif i == 2:  # dente alto e appuntito con un blocco ai piedi e uno dietro
        a = cleaved_block((0, 0, 1.0), (0.95, 0.85, 1.2), seed=201, rot=(0, 6, 30), peak=1.5, taper=0.4, chips=7)
        b = cleaved_block((0.95, -0.55, 0.28), (0.62, 0.5, 0.45), seed=202, rot=(0, 10, -20), ridge=0.22, tilt=16, chips=5)
        c = cleaved_block((-0.75, 0.6, 0.55), (0.75, 0.65, 0.7), seed=203, rot=(0, -8, 60), ridge=0.35, chips=4)
        body = union(a, b, c)
        cracks = [((0, 0, 1.6), (0.3, -1, 0.4), (0, 0, -1), 1.8, 4), ((0.1, 0, 1.2), (1, 0.1, 0.2), (0.2, 0.3, -1), 1.1, 5)]
    else:  # masso basso spaccato dall'alto, con una scheggia caduta
        a = cleaved_block((0, 0, 0.7), (1.75, 1.3, 0.9), seed=301, rot=(0, 0, -8), ridge=0.4, chips=8)
        c = cleaved_block((1.55, -0.85, 0.22), (0.5, 0.42, 0.32), seed=302, rot=(0, 18, 40), chips=4)
        body = union(a, c)
        cracks = [((0.15, 0, 1.0), (0.05, 0.05, 1), (0.15, -1, 0), 2.6, 6), ((0.6, 0, 0.6), (0.4, -1, 0.1), (0.1, 0, -1), 1.0, 7)]
    body = body.intersect(ground())
    for k, (inside, d, along, ln, s) in enumerate(cracks):
        deep = 0.5 if (i == 3 and k == 0) else 0.25
        wide = 0.1 if (i == 3 and k == 0) else 0.06
        body = body.subtract(surface_crack(body, inside, d, along, depth=deep, width=wide, length=ln, zigzag=3, seed=s))
    return body


def rubble(body: SDF, seed: int, n: int, rmin: float, rmax: float, size=(0.22, 0.36), arc=(0.0, 2 * math.pi)) -> SDF:
    """Schegge piatte e angolose mezze interrate ai piedi di una roccia (non la compenetrano)."""
    rng = np.random.default_rng(seed)
    chips = []
    for k in range(n):
        a = rng.uniform(*arc)
        r = rng.uniform(rmin, rmax)
        s = rng.uniform(*size)
        chips.append(cleaved_block((r * math.cos(a), r * math.sin(a), 0.0), (s, s * rng.uniform(0.55, 0.85), s * 0.45),
                                   seed=seed + k, rot=(rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(0, 180)),
                                   ridge=s * 0.3, chips=3))
    return union(*chips).intersect(ground()).subtract(body.offset(0.03))


def rock(i: int) -> Prop:
    m = Prop(f"Rock{i}", voxel=0.025)
    body = rock_body(i)
    m.add("Rock", body, ROCK_COLORS[i], tris=520, smooth=False)
    arc = {1: (3.6, 5.6), 2: (4.0, 6.2), 3: (3.4, 5.0)}[i]
    m.add("Chips", rubble(body, 140 + 10 * i, 3, 1.7, 2.2, arc=arc), PEBBLE_COLORS[i], role="detail", tris=140, smooth=False)
    return m


def rock_spire() -> Prop:
    """Pinnacolo di roccia alto e frastagliato (~7) per pareti e bordi del sentiero."""
    m = Prop("RockSpire", voxel=0.03)
    column = cleaved_block((0.05, 0, 2.5), (1.15, 0.95, 2.7), seed=501, rot=(0, 4, 30), taper=0.45, peak=1.7, chips=8)
    twin = cleaved_block((-0.9, 0.45, 1.8), (0.68, 0.6, 1.9), seed=502, rot=(0, -10, 10), taper=0.35, peak=1.0, chips=5)
    shard = cleaved_block((0.95, 0.4, 3.0), (0.42, 0.34, 1.0), seed=503, rot=(0, 20, 55), peak=0.8, chips=4)
    ledge = cleaved_block((0.9, -0.6, 1.2), (0.7, 0.55, 0.45), seed=504, rot=(0, 10, -25), ridge=0.2, chips=4)
    base1 = cleaved_block((0.4, -0.3, 0.3), (1.6, 1.2, 0.55), seed=505, rot=(0, 0, 15), ridge=0.25, chips=7)
    base2 = cleaved_block((-1.2, -0.4, 0.25), (0.8, 0.7, 0.5), seed=506, rot=(0, 8, -35), ridge=0.3, chips=4)
    body = union(column, twin, shard, ledge, base1, base2).intersect(ground())
    for inside, d, along, ln, s in [((0.05, 0, 3.4), (0.2, -1, 0.1), (0.05, 0, -1), 2.4, 11),
                                    ((0.05, 0, 4.6), (1, -0.4, 0.3), (0, 0.2, -1), 1.4, 12),
                                    ((0.4, -0.3, 0.4), (-0.2, -1, 0.3), (1, 0, -0.3), 1.4, 13)]:
        body = body.subtract(surface_crack(body, inside, d, along, depth=0.3, width=0.08, length=ln, zigzag=3, seed=s))
    m.add("Rock", body, (110, 116, 126), tris=1150, smooth=False)
    m.add("Chips", rubble(body, 510, 4, 1.9, 2.4, (0.28, 0.42), arc=(3.3, 6.0)), (92, 96, 104), role="detail", tris=180, smooth=False)
    return m


def rock_shards() -> Prop:
    """Gruppo di 3-4 lame di roccia appuntite e inclinate (~3)."""
    m = Prop("RockShards", voxel=0.022)
    blades = [  # centro, mezze misure (largo, sottile, alto), punta, rotazione
        ((0.0, 0.1, 1.05), (0.55, 0.2, 1.1), 0.9, (8, -5, 15)),
        ((0.75, -0.35, 0.75), (0.45, 0.17, 0.85), 0.7, (-10, 22, 60)),
        ((-0.7, -0.15, 0.65), (0.42, 0.16, 0.75), 0.65, (6, -24, -35)),
        ((0.15, 0.75, 0.55), (0.4, 0.16, 0.6), 0.55, (-20, 8, 100)),
    ]
    shards = [cleaved_block(c, h, seed=600 + k, rot=rot, peak=pk, taper=0.1, tilt=6, chips=4)
              for k, (c, h, pk, rot) in enumerate(blades)]
    body = union(*shards).intersect(ground())
    for inside, d, along, ln, s in [((0, 0.1, 1.3), (0.2, -1, 0), (0, 0, -1), 1.2, 21),
                                    ((0.75, -0.35, 0.9), (0.6, -1, 0), (0.3, 0, -1), 0.8, 22)]:
        body = body.subtract(surface_crack(body, inside, d, along, depth=0.1, width=0.045, length=ln, zigzag=2, seed=s))
    m.add("Rock", body, (110, 116, 128), tris=620, smooth=False)
    base = cleaved_block((0.05, 0.1, -0.05), (1.15, 0.95, 0.3), seed=640, rot=(0, 0, 20), chips=6).intersect(ground())
    m.add("Base", base.subtract(body.offset(0.01)), (94, 98, 108), role="detail", tris=160, smooth=False)
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
    """Cespuglio tondeggiante: ciuffi di foglie low-poly irregolari in due verdi, qualche bacca."""
    m = Prop(f"Bush{i}", voxel=0.03)
    rng = np.random.default_rng(3 + i)
    w, h = 1.55, 1.9
    dark, light = [], []
    for k in range(8):  # anello basso, verde scuro
        a = 2 * math.pi * k / 8 + rng.uniform(-0.3, 0.3)
        r = rng.uniform(0.75, 1.0) * w * 0.7
        sz = rng.uniform(0.62, 0.85)
        dark.append(((r * math.cos(a), r * math.sin(a) * 0.85, sz * 0.75), (sz * 1.1, sz, sz * 0.95)))
    for k in range(6):  # sopra e davanti, verde chiaro
        a = 2 * math.pi * k / 6 + rng.uniform(-0.4, 0.4) + 0.5
        r = rng.uniform(0.2, 0.55) * w * 0.7
        sz = rng.uniform(0.6, 0.8)
        light.append(((r * math.cos(a), r * math.sin(a) * 0.85 - 0.15, h * 0.5 + rng.uniform(-0.15, 0.25)), (sz * 1.05, sz, sz * 0.95)))
    light.append(((0.05, -0.05, h * 0.64), (0.8, 0.75, 0.68)))
    blob = dict(n=14, depth=(0.78, 1.0), zmax=0.8, top=1.15)
    dk = union(*[facet_blob(c, r, seed=200 + k, rot=(0, 0, 37 * k), **blob) for k, (c, r) in enumerate(dark)]).intersect(ground())
    lt = union(*[facet_blob(c, r, seed=220 + k, rot=(0, 0, 53 * k), **blob) for k, (c, r) in enumerate(light)])
    m.add("Leaves", dk, (46, 92, 48), tris=440, smooth=False)
    m.add("LeavesLight", lt, (84, 130, 60), role="detail", tris=330, smooth=False)
    # bacche scure appoggiate sui ciuffi, verso il davanti
    shape = union(dk, lt)
    berries = []
    for k, (c, _) in enumerate(light[:5] + dark[:3]):
        d = np.array([c[0] * 0.6, -1.0, 0.35 + 0.2 * (k % 3)])
        d /= np.linalg.norm(d)
        t = 0.0
        while shape(np.asarray([np.asarray(c) + d * t], dtype=np.float32))[0] < 0 and t < 2:
            t += 0.02
        berries.append(facet_blob(np.asarray(c) + d * (t - 0.04), (0.11, 0.11, 0.11), n=9, seed=260 + k))
    m.add("Berries", union(*berries), (128, 26, 38), role="detail", tris=110, smooth=False)
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
NEST_ZC = 0.7   # altezza del centro dell'anello
NEST_RT = 0.26  # raggio del "tubo" dell'anello


def _rim_point(th, psi, rr):
    """Punto sulla superficie dell'anello: psi = 0 esterno, 90 sopra, 180 interno (gradi)."""
    rho = NEST_R + rr * math.cos(math.radians(psi))
    return (rho * math.cos(th), rho * math.sin(th), NEST_ZC + rr * math.sin(math.radians(psi)))


def nest() -> Prop:
    """Nido: ciotola bassa, bordo di rametti intrecciati, paglia dorata dentro.

    L'uovo appoggia a z = 0.55 (NestService): il fondo di paglia sta a z ~0.5.
    """
    m = Prop("Nest", voxel=0.025)
    # ciotola cava: fondo arrotondato appena sotto terra, pavimento interno a z ~0.45
    bowl = ellipsoid((1.62, 1.62, 0.9), (0, 0, 0.62)).subtract(ellipsoid((1.25, 1.25, 0.65), (0, 0, 1.0)))
    bowl = bowl.intersect(ground(-0.15)).intersect(ceiling(0.75))
    core = torus(NEST_R, NEST_RT, (0, 0, NEST_ZC))
    body = noisy(union(bowl, core, k=0.15), 0.02, 6.0, 5)
    m.add("Bowl", body, (98, 66, 40), tris=420, smooth=False)
    # rametti: archi che corrono sull'anello a quote diverse e si incrociano (intreccio)
    rng = np.random.default_rng(5)
    twigs = []
    n, rad = 16, 0.1
    for k in range(n):
        th0 = 2 * math.pi * k / n + rng.uniform(-0.1, 0.1)
        span = rng.uniform(1.5, 2.0)
        psi0 = [-40, 10, 60, 110, 150][k % 5] + rng.uniform(-15, 15)
        drift = rng.uniform(25, 55) * (1 if k % 2 else -1)
        pts, rr = [], []
        for j in range(7):
            t = j / 6
            lift = 0.06 if j in (0, 6) else 0.0  # le punte si staccano un po'
            pts.append(_rim_point(th0 + span * (t - 0.5), psi0 + drift * (t - 0.5), NEST_RT + rad * 0.6 + lift))
            rr.append(rad * (0.75 + 0.25 * math.sin(math.pi * t)))
        twigs.append(tube(pts, rr))
    m.add("Twigs", fast_union(*twigs), (182, 130, 78), role="detail", tris=1100, voxel=0.02, smooth=False)

    # paglia: letto concavo (fondo a z 0.5) e qualche filo che scavalca il bordo
    def straw_bed(p):
        rho = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2)
        top = 0.5 + 0.35 * (rho / 1.1) ** 2
        return np.maximum(np.maximum(p[:, 2] - top, 0.3 - p[:, 2]), rho - 1.3)

    bed = noisy(SDF(straw_bed, (-1.35, -1.35, 0.3), (1.35, 1.35, 1.05)), 0.025, 8.0, 3)
    strands = []
    rng = np.random.default_rng(78)
    for k in range(6):
        a = 2 * math.pi * k / 6 + rng.uniform(-0.3, 0.3)
        a1 = a + rng.uniform(-0.25, 0.25)
        r0 = rng.uniform(0.75, 0.95)
        p0 = (r0 * math.cos(a), r0 * math.sin(a), 0.5 + 0.35 * (r0 / 1.1) ** 2)
        p1 = (NEST_R * math.cos(a1), NEST_R * math.sin(a1), NEST_ZC + NEST_RT + 0.12)
        p2 = ((NEST_R + 0.38) * math.cos(a1 + 0.08), (NEST_R + 0.38) * math.sin(a1 + 0.08), NEST_ZC + 0.05)
        strands.append(tube([p0, p1, p2], [0.04, 0.042, 0.03]))
    for k in range(9):  # fili sparsi sul letto di paglia
        a = rng.uniform(0, 2 * math.pi)
        r0 = rng.uniform(0.25, 0.85)
        d = rng.uniform(0, 2 * math.pi)
        pts = []
        for t in (-0.32, 0.0, 0.32):
            x, y = r0 * math.cos(a) + t * math.cos(d), r0 * math.sin(a) + t * math.sin(d)
            pts.append((x, y, 0.5 + 0.35 * (math.hypot(x, y) / 1.1) ** 2 + 0.02))
        strands.append(tube(pts, [0.03, 0.035, 0.03]))
    m.add("Straw", fast_union(bed, *strands), (232, 190, 92), role="detail", tris=600, voxel=0.02, smooth=False)
    return m


CATALOG = {
    "Rock1": lambda: rock(1), "Rock2": lambda: rock(2), "Rock3": lambda: rock(3),
    "RockSpire": rock_spire, "RockShards": rock_shards,
    "PineTree": lambda: pine(), "PineSnowy": pine_snowy,
    "Bush1": lambda: bush(1), "Flowers1": lambda: flower_patch(1), "Flowers2": lambda: flower_patch(2),
    "Grass1": lambda: grass_tuft(1), "Nest": nest,
}

if __name__ == "__main__":
    run(CATALOG)
