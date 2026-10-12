"""Golem di Cristallo (CrystalGolem) - pet PRIMORDIALE (grotte di cristallo).

Un colosso di pietra blu-grigia tagliata a facce piatte, curvo in avanti come un gorilla, che sbatte
uno contro l'altro due pugni enormi davanti alla pancia (fra le nocche scoccano schegge di luce
azzurra). Dalle spalle e dalla schiena spuntano grandi cristalli viola e azzurri con le punte
luminose; la testa, piccola e incassata fra le spalle, ha un'arcata sopraccigliare pesante, occhi
azzurri luminosi e una mascella sporgente piena di denti di cristallo. Nel petto pulsa un nucleo di
cristallo viola (parte Neon "Aura": il gioco ci attacca le particelle di magia viola) da cui partono
crepe luminose che scendono fino ai pugni. Tocco "toy horror": e' snodato come un action figure,
con giunti blu notte a spalle, gomiti, polsi e anche, viti a croce in vista e il nucleo montato in
una ghiera avvitata come lo sportellino delle pile.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, box, cylinder, ellipsoid, euler, halfspace_z, prism, project, rot_matrix,  # noqa: E402
                     smin, tube, union)
from lib.toy import Model  # noqa: E402


# ============================================================ helper (lib/ non si modifica: copiati/adattati qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def fast_union(shapes, k=0.0, base=None, margin=0.06):
    """Unione di tante forme, ognuna valutata solo vicino al proprio ingombro."""
    shapes = list(shapes)
    los = np.array([s.lo for s in shapes]) - margin - k
    his = np.array([s.hi for s in shapes]) + margin + k

    def f(p):
        d = base(p) if base is not None else np.full(len(p), 1.0, dtype=np.float32)
        if len(p) == 0:
            return d
        plo, phi = p.min(0), p.max(0)
        for i in np.nonzero(np.all((his >= plo) & (los <= phi), axis=1))[0]:
            msk = np.all((p >= los[i]) & (p <= his[i]), axis=1)
            if msk.any():
                idx = np.nonzero(msk)[0]
                d[idx] = smin(d[idx], shapes[i](p[idx]), k)
        return d

    lo, hi = los.min(0), his.max(0)
    if base is not None:
        lo, hi = np.minimum(lo, base.lo), np.maximum(hi, base.hi)
    return SDF(f, lo, hi)


def orient_m(axis, side=(1.0, 0.0, 0.0)):
    """Matrice (colonne x, y, z) che porta Z locale su 'axis' e X locale il piu' possibile verso 'side'."""
    a = norm(axis)
    s = np.asarray(side, dtype=np.float64)
    s = s - a * float(s @ a)
    if np.linalg.norm(s) < 1e-6:
        s = np.array([0.0, 1.0, 0.0]) - a * a[1]
    s = norm(s)
    return np.stack([s, np.cross(a, s), a], axis=1).astype(np.float32)


def rock(c, radii, R=None, n=18, seed=0, cut=(0.84, 0.97), jitter=0.16):
    """Masso sfaccettato: poliedro convesso (intersezione di semispazi) attorno a un ellissoide.

    Le facce casuali tagliano l'ellissoide fra cut[0] e cut[1] del suo ingombro in quella direzione;
    sei facce sugli assi lo chiudono nel box dei raggi. R porta gli assi locali nel mondo (colonne).
    Va usato in parti con smooth=False: facce piatte e spigoli vivi.
    """
    rng = np.random.default_rng(seed)
    ga = math.pi * (3 - math.sqrt(5))
    off = rng.uniform(0, 2 * math.pi)
    dirs = []
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(max(1 - z * z, 0.0))
        d = np.array([r * math.cos(ga * i + off), r * math.sin(ga * i + off), z]) + rng.normal(0, jitter, 3)
        dirs.append(d / np.linalg.norm(d))
    radii = np.asarray(radii, dtype=np.float64)
    N = np.array(dirs)
    h = np.sqrt(((N * radii) ** 2).sum(1)) * rng.uniform(cut[0], cut[1], n)
    N = np.concatenate([N, np.eye(3), -np.eye(3)]).astype(np.float32)
    h = np.concatenate([h, radii, radii]).astype(np.float32)
    R = np.eye(3, dtype=np.float32) if R is None else np.asarray(R, dtype=np.float32)
    c = np.asarray(c, dtype=np.float32)

    def f(p):
        q = (p - c) @ R
        return (q @ N.T - h).max(axis=1)

    ext = np.abs(R) @ radii.astype(np.float32)
    return SDF(f, c - ext, c + ext)


def crystal(length, radius, tip=0.32, sides=6):
    """Cristallo sfaccettato lungo +Z (base in z=0): prisma regolare con punta piramidale."""
    normals = np.array([[math.cos(2 * math.pi * i / sides), math.sin(2 * math.pi * i / sides)] for i in range(sides)],
                       dtype=np.float32)
    apothem = radius * math.cos(math.pi / sides)
    z_tip = length * (1 - tip)
    slope = apothem / (length - z_tip)
    k = 1.0 / math.sqrt(1.0 + slope * slope)

    def f(p):
        side = (p[:, :2] @ normals.T).max(axis=1)
        d = np.maximum(side - apothem, (side - apothem + slope * (p[:, 2] - z_tip)) * k)
        return np.maximum(d, -p[:, 2])

    return SDF(f, (-radius, -radius, 0.0), (radius, radius, length))


def orient(shape, base, direction, spin=0.0):
    """Porta l'asse +Z della forma lungo direction, con la base nel punto base."""
    d = norm(direction)
    ax = np.cross([0.0, 0.0, 1.0], d)
    s = float(np.linalg.norm(ax))
    if spin:
        shape = shape.rot(0, 0, spin)
    if s > 1e-6:
        shape = shape.rotate(rot_matrix(ax, math.degrees(math.atan2(s, d[2]))))
    return shape.translate(base)


def below(z):
    return SDF(lambda p: p[:, 2] - z, (-5, -5, -5), (5, 5, z))


def above(z):
    return SDF(lambda p: z - p[:, 2], (-5, -5, z), (5, 5, 5))


def diamond3(a, b, c):
    """Ottaedro allungato (gemma): semiassi a, b, c lungo X, Y, Z."""
    k = 1.0 / math.sqrt(1 / a ** 2 + 1 / b ** 2 + 1 / c ** 2)

    def f(p):
        q = np.abs(p)
        return (q[:, 0] / a + q[:, 1] / b + q[:, 2] / c - 1.0) * k

    return SDF(f, (-a, -b, -c), (a, b, c))


def screw(base, nrm, r=0.07, spin=0.0):
    """Vite a croce: testa bombata lungo la normale, con l'intaglio a croce."""
    h = r * 0.5
    head = union(cylinder((0, 0, -0.06), (0, 0, h * 0.5), r), ellipsoid((r, r, h), (0, 0, h * 0.5)))
    sw = r * 0.2
    slot = union(box((r * 1.3, sw, h), (0, 0, h * 1.45)), box((sw, r * 1.3, h), (0, 0, h * 1.45)))
    return orient(head.subtract(slot), base, nrm, spin=spin)


def surf(sdf, origin, direction):
    """Punto della superficie (e normale) partendo da origin (dentro) lungo direction."""
    p, n = project(sdf, origin, direction)
    return np.asarray(p, dtype=np.float64), np.asarray(n, dtype=np.float64)


def crack(sdf, pairs, r0=0.034, r1=0.016, sink=0.35):
    """Crepa luminosa: per ogni coppia (punto interno, punto verso cui andare) un punto della superficie.

    I punti doppi vengono saltati (un segmento lungo zero riempirebbe tutto il suo ingombro).
    """
    out = []
    for o, q in pairs:
        o = np.asarray(o, dtype=np.float64)
        p, n = surf(sdf, o, np.asarray(q, dtype=np.float64) - o)
        p = p - n * r0 * sink
        if out and np.linalg.norm(p - np.asarray(out[-1])) < 0.02:
            continue
        out.append(tuple(p))
    nn = len(out)
    return tube(out, [r0 + (r1 - r0) * i / max(nn - 1, 1) for i in range(nn)])


# ============================================================ colori
STONE = (80, 96, 142)       # pietra blu-grigia
JOINT = (30, 40, 116)       # plastica blu notte dei giunti
METAL = (205, 212, 228)     # viti e ghiera del nucleo
VIOLET = (146, 60, 236)     # cristalli viola
CYAN = (46, 196, 240)       # cristalli azzurri
ICE = (204, 240, 255)       # denti, artigli e spuntoni di ghiaccio
AURA = (150, 70, 255)       # nucleo e crepe (Neon viola)
CYAN_GLOW = (96, 250, 255)  # occhi, punte azzurre, schegge dell'urto (Neon)
MAW = (22, 16, 48)          # bocca e orbite

m = Model("CrystalGolem", "pet")

# ============================================================ tronco curvo (massi sfaccettati)
torso_rocks = [
    rock((0, 0.2, 1.1), (0.58, 0.42, 0.32), n=16, seed=1),                       # bacino
    rock((0, -0.02, 1.44), (0.62, 0.5, 0.34), R=euler(10, 0, 0), n=16, seed=2),   # ventre
    rock((0, -0.1, 1.98), (0.88, 0.6, 0.52), R=euler(14, 0, 0), n=18, seed=3),    # petto
    rock((0, 0.36, 2.5), (0.78, 0.52, 0.46), R=euler(-12, 0, 0), n=16, seed=7),   # gobba
    rock((0, -0.18, 2.6), (0.56, 0.38, 0.26), n=14, seed=8),                      # trapezi
]
torso_rocks += [rock((sx * 0.36, -0.5, 2.06), (0.38, 0.22, 0.3), R=euler(14, 0, sx * 10), n=14, seed=5 + sx)
                for sx in (1, -1)]                                                  # pettorali
torso_rocks += [rock((sx * 0.6, 0.02, 2.48), (0.36, 0.42, 0.36), n=14, seed=10 + sx) for sx in (1, -1)]  # spalle
torso = fast_union(torso_rocks)

# ============================================================ gambe tozze e larghe
leg_rocks, TOES, KNEES = [], [], []
for sx in (1, -1):
    x = sx * 0.62
    leg_rocks += [
        rock((x, -0.12, 0.16), (0.36, 0.48, 0.21), R=euler(0, 0, -sx * 8), n=14, seed=20 + sx),   # piede
        rock((x, 0.0, 0.54), (0.31, 0.33, 0.35), R=euler(-6, 0, 0), n=14, seed=23 + sx),          # stinco
        rock((x, -0.2, 0.86), (0.2, 0.16, 0.18), n=10, seed=26 + sx),                            # ginocchio
        rock((sx * 0.55, 0.1, 1.02), (0.33, 0.39, 0.31), R=euler(18, 0, 0), n=14, seed=29 + sx),  # coscia
    ]
    KNEES.append((x, -0.2, 0.86))
    for j, dx in enumerate((-0.21, 0.0, 0.21)):
        c = (x + dx, -0.57, 0.12)
        leg_rocks.append(rock(c, (0.115, 0.15, 0.115), n=10, seed=40 + 3 * sx + j))
        TOES.append(c)

# ============================================================ braccia da action figure e pugni enormi
FS = 1.13                                   # scala dei pugni
ARM = {}
arm_rocks, fist_rocks = [], []
for sx in (1, -1):
    S = np.array([sx * 1.1, -0.08, 2.42])   # spalla
    E = np.array([sx * 1.44, -0.46, 1.62])  # gomito
    FC = np.array([sx * 0.45, -1.24, 0.66])  # centro del pugno
    A = norm((-sx, -0.18, 0.0))             # direzione del colpo (verso l'altro pugno)
    Fw = norm(np.array([0.0, -1.0, 0.0]) - A * float(A @ np.array([0.0, -1.0, 0.0])))
    RF = np.stack([A, -Fw, np.array([0.0, 0.0, 1.0])], axis=1).astype(np.float32)  # locale: x colpo, -y verso chi guarda
    W = FC - A * 0.44 * FS                  # polso
    DC = np.array([sx * 1.4, -0.06, 2.58])  # centro del deltoide
    ARM[sx] = dict(S=S, E=E, W=W, FC=FC, RF=RF, DC=DC)
    side = (sx, 0, 0)
    arm_rocks += [
        rock(DC, (0.34, 0.4, 0.33), n=14, seed=50 + sx),                                            # deltoide
        rock(S + (E - S) * 0.52, (0.28, 0.28, 0.37), R=orient_m(E - S, side), n=12, seed=53 + sx),  # omero
        rock(E + (W - E) * 0.28, (0.22, 0.22, 0.24), R=orient_m(W - E, side), n=12, seed=56 + sx),  # avambraccio
        rock(E + (W - E) * 0.66, (0.34, 0.34, 0.37), R=orient_m(W - E, side), n=14, seed=59 + sx),
    ]
    # pugno chiuso in verticale (pollice in alto, palmo verso chi guarda): dita a rotoli separati, nocche in avanti
    fist = [rock((-0.14, 0.06, 0.0), (0.27, 0.28, 0.37), n=12, seed=62 + sx, cut=(0.9, 0.98))]
    for j, z in enumerate((0.235, 0.0, -0.235)):   # tre dita tozze arrotolate, ben separate
        fist.append(rock((0.08 - 0.02 * j, -0.15, z), (0.25, 0.18, 0.1), n=12, seed=70 + 4 * sx + j,
                         cut=(0.9, 0.98)))
        fist.append(rock((0.3 - 0.015 * j, 0.0, z), (0.11, 0.16, 0.1), n=10, seed=80 + 4 * sx + j,
                         cut=(0.88, 0.98)))
    fist.append(rock((-0.02, -0.17, 0.37), (0.22, 0.13, 0.1), R=euler(0, 10, 0), n=10, seed=90 + sx))   # pollice
    fist.append(rock((-0.42, 0.06, 0.0), (0.17, 0.21, 0.27), n=10, seed=93 + sx))                        # polso
    fist_rocks += [f_.scale(FS).rotate(RF).translate(FC) for f_ in fist]

# ============================================================ nucleo nel petto: modulo esagonale "a pile" avvitato
CORE_N = norm((0.0, -1.0, 0.12))       # guarda avanti (non segue la faccia del masso)
CORE_P, _ = surf(torso, (0, -0.2, 1.62), CORE_N)
CORE_M = orient_m(CORE_N, (1, 0, 0))   # z locale = normale, x orizzontale, y verso l'alto


def core_local(shape):
    return shape.rotate(CORE_M).translate(CORE_P)


HEX = [(0.38 * math.cos(math.radians(90 + 60 * i)), 0.46 * math.sin(math.radians(90 + 60 * i))) for i in range(6)]
housing = core_local(prism(HEX, -0.22, 0.07, round=0.03))
core_cut = core_local(prism([(x * 1.06, y * 1.06) for x, y in HEX], 0.0, 1.2))
gem = core_local(diamond3(0.15, 0.23, 0.19).translate((0, 0, 0.07)))

body = fast_union(torso_rocks + leg_rocks + arm_rocks).subtract(core_cut).intersect(halfspace_z(0.0))
m.add("Body", body, STONE, tris=3700, voxel=0.053, smooth=False)
fists = fast_union(fist_rocks)
m.add("Fists", fists, STONE, role="skin", tris=2400, voxel=0.0335, smooth=False)


# ============================================================ testa incassata fra le spalle (coordinate locali)
HEAD_POS = np.array([0.0, -0.74, 2.68])
HS = 1.22
R_HEAD = euler(8.0, 7.0, 10.0)   # muso un po' basso, testa inclinata e girata verso la camera 3/4


def H(s):
    return s.scale(HS).rotate(R_HEAD).translate(HEAD_POS)


cran = rock((0, 0.08, 0.08), (0.37, 0.34, 0.32), n=16, seed=101)
brows = [rock((sx * 0.17, -0.25, 0.16), (0.22, 0.13, 0.1), R=euler(10, -sx * 24, 0), n=12, seed=102 + sx)
         for sx in (1, -1)]
bridge = rock((0, -0.31, 0.08), (0.1, 0.1, 0.09), n=10, seed=105)
cheeks = [rock((sx * 0.25, -0.17, -0.1), (0.15, 0.17, 0.13), n=12, seed=106 + sx) for sx in (1, -1)]
muzzle = rock((0, -0.28, -0.1), (0.22, 0.12, 0.09), n=12, seed=109)
jaw = rock((0, -0.22, -0.38), (0.35, 0.33, 0.15), R=euler(-8, 0, 0), n=14, seed=110)
chin = rock((0, -0.47, -0.42), (0.16, 0.09, 0.1), n=10, seed=113)
masseters = [rock((sx * 0.29, -0.04, -0.27), (0.12, 0.17, 0.15), n=10, seed=111 + sx) for sx in (1, -1)]
head_l = fast_union([cran, *brows, bridge, *cheeks, muzzle, jaw, chin, *masseters])
mouth_slot = box((0.22, 0.25, 0.04), (0, -0.44, -0.205))
EYE_C = {}
for sx in (1, -1):
    p, _ = surf(cran, (sx * 0.15, 0.0, 0.0), (0, -1, 0))
    EYE_C[sx] = p
EYE_R = (0.1, 0.042, 0.038)
sockets = union(*[ellipsoid((0.124, 0.075, 0.068)).rot(0, -sx * 22, 0).translate(EYE_C[sx]) for sx in (1, -1)])
head_l = head_l.subtract(union(mouth_slot, sockets))
m.add("Head", H(head_l), STONE, role="skin", tris=2600, voxel=0.0281, smooth=False)

# ============================================================ cristalli (viola / azzurri, alcune punte luminose)
groups = {"V": [], "C": [], "GV": [], "GC": []}


def add_crystal(sdf, origin, d, length, radius, col, glow, spin=0.0, sink=0.12, tip=0.32, sides=6, xf=None):
    d = norm(d)
    p, _ = surf(sdf, origin, d)
    base = p - d * sink
    c = crystal(length, radius, tip=tip, sides=sides)
    cut = length * 0.72
    shape = orient(c.intersect(below(cut)) if glow else c, base, d, spin=spin)
    groups[col].append(xf(shape) if xf else shape)
    if glow:
        tip_c = orient(c.intersect(above(cut)), base, d, spin=spin)
        groups["G" + col].append(xf(tip_c) if xf else tip_c)


HUMP_C = (0, 0.36, 2.4)
for d, L, r, col, g in [((0, 0.3, 1.0), 1.3, 0.23, "V", True), ((0.5, 0.35, 0.8), 0.9, 0.16, "C", True),
                        ((-0.5, 0.4, 0.78), 0.95, 0.17, "C", False), ((0.28, 0.85, 0.45), 0.62, 0.12, "V", False),
                        ((-0.32, 0.8, 0.5), 0.6, 0.12, "V", True), ((0.05, 0.95, 0.15), 0.5, 0.11, "C", False),
                        ((0.22, 0.5, 1.0), 0.42, 0.08, "V", False), ((-0.2, 0.6, 0.9), 0.36, 0.075, "C", True)]:
    add_crystal(torso, HUMP_C, d, L, r, col, g, spin=L * 40)
for d, L, r, col, g in [((0.25, 1.0, 0.25), 0.42, 0.1, "C", True), ((-0.3, 1.0, 0.1), 0.36, 0.09, "V", False)]:
    add_crystal(torso, (0, 0.2, 1.5), d, L, r, col, g, spin=L * 50)
body_arms = fast_union(arm_rocks)
for sx in (1, -1):
    DC = ARM[sx]["DC"]
    big = 1.12 if sx < 0 else 1.0   # spalle diverse: il gruppo di sinistra e' piu' grande (sagoma meno simmetrica)
    cl = [((sx * 0.35, 0.05, 1.0), 1.0 * big, 0.18, "V", True), ((sx * 0.55, -0.25, 0.8), 0.56, 0.12, "C", True),
          ((0.0, 0.5, 1.0), 0.7 * big, 0.13, "C", False), ((sx * 0.5, 0.55, 0.55), 0.45, 0.1, "V", False),
          ((-sx * 0.15, -0.3, 1.0), 0.38, 0.08, "V", False)]
    if sx < 0:
        cl.append(((sx * 0.2, 0.25, 1.0), 0.5, 0.1, "C", True))
    for d, L, r, col, g in cl:
        add_crystal(body_arms, DC, d, L, r, col, g, spin=L * 60 + sx * 20)
for d, L, r, col, g in [((0, 0.45, 1.0), 0.62, 0.12, "V", True), ((0.5, 0.35, 0.85), 0.45, 0.09, "C", False),
                        ((-0.5, 0.35, 0.85), 0.42, 0.09, "V", False)]:   # corona di cristalli sulla nuca
    add_crystal(cran, (0, 0.12, 0.1), d, L, r, col, g, spin=30, sink=0.08, xf=H)

m.add("CrystalsViolet", fast_union(groups["V"]), VIOLET, material="Glass", role="detail", tris=950, voxel=0.0469,
      smooth=False)
m.add("CrystalsCyan", fast_union(groups["C"]), CYAN, material="Glass", role="detail", tris=750, voxel=0.0469,
      smooth=False)

# ============================================================ giunti da action figure (blu notte) e viti a croce
joints, screws = [], []
for sx in (1, -1):
    a = ARM[sx]
    S, E, W, DC = a["S"], a["E"], a["W"], a["DC"]
    # spalla: disco girevole nella fessura fra tronco e deltoide, vite grossa sul deltoide
    ax_s = norm((sx, 0.0, 0.1))
    jc = np.array([sx * 1.01, -0.07, 2.5])
    joints.append(cylinder(jc - ax_s * 0.08, jc + ax_s * 0.08, 0.3, round=0.025))
    p, n = surf(body_arms, DC, (sx, -0.35, 0.05))
    screws.append(screw(p - n * 0.01, n, r=0.1, spin=20))
    # gomito: cerniera a barilotto con le viti alle estremita'
    hx = norm(np.cross(E - S, W - E))
    joints.append(cylinder(E - hx * 0.26, E + hx * 0.26, 0.17, round=0.025))
    for sgn in (1, -1):
        screws.append(screw(E + hx * sgn * 0.285, hx * sgn, r=0.085, spin=35))
    # polso: anello
    fa = norm(W - E)
    joints.append(cylinder(W - fa * 0.08, W + fa * 0.06, 0.21, round=0.02))
    # anca: disco e vite sul fianco della coscia
    p, n = surf(body, (sx * 0.55, 0.1, 1.02), (sx, 0.0, 0.08))
    joints.append(cylinder(p - n * 0.05, p + n * 0.03, 0.16, round=0.015))
    screws.append(screw(p + n * 0.035, n, r=0.075, spin=10))
for kc in KNEES:   # vite sulle ginocchia
    p, n = surf(body, kc, (0, -1, 0.15))
    screws.append(screw(p - n * 0.01, n, r=0.07, spin=40))
# modulo del nucleo: scatola blu notte, ghiera d'argento attorno alla gemma, quattro viti agli angoli
joints.append(housing)
screws.append(core_local(tube([(0.21 * math.cos(math.radians(90 + 60 * i)), 0.29 * math.sin(math.radians(90 + 60 * i)), 0.07)
                               for i in range(7)], 0.034)))
for u, v in ((0.27, 0.19), (-0.27, 0.19), (0.27, -0.19), (-0.27, -0.19)):
    screws.append(screw(CORE_P + CORE_M @ np.array([u, v, 0.06], dtype=np.float32), CORE_N, r=0.058, spin=15))
m.add("Joints", fast_union(joints), JOINT, role="detail", tris=800, voxel=0.0529)
m.add("Screws", fast_union(screws), METAL, material="Metal", role="detail", tris=1200, voxel=0.0214)

# ============================================================ ghiaccio: artigli dei piedi, spuntoni degli avambracci, denti
ice, teeth = [], []
for c in TOES:
    ice.append(orient(crystal(0.18, 0.068, tip=0.6, sides=4), (c[0], -0.66, 0.11), (0, -1, -0.3), spin=45))
for sx in (1, -1):
    E, W = ARM[sx]["E"], ARM[sx]["W"]
    for t, L in ((0.36, 0.36), (0.58, 0.45), (0.8, 0.34)):
        o = E + (W - E) * t
        p, n = surf(body_arms, o, (sx * 0.45, 0.35, 1.0))
        dd = norm(n + np.array([0, 0.35, 0.7]))
        ice.append(orient(crystal(L, 0.085, tip=0.5, sides=5), p - dd * 0.09, dd, spin=t * 90))
m.add("IceSpikes", fast_union(ice), ICE, role="detail", tris=500, voxel=0.0277, smooth=False)

for x, L, r in ((-0.24, 0.24, 0.055), (-0.135, 0.11, 0.036), (-0.045, 0.13, 0.036), (0.05, 0.11, 0.036),
                (0.145, 0.13, 0.036), (0.245, 0.25, 0.055)):
    teeth.append(orient(crystal(L, r, tip=0.55, sides=4), (x, -0.45, -0.26), (x * 0.5, -0.25, 1.0), spin=45))
for x, L in ((-0.15, 0.1), (-0.05, 0.08), (0.06, 0.085), (0.16, 0.1)):
    teeth.append(orient(crystal(L, 0.034, tip=0.55, sides=4), (x, -0.37, -0.165), (0, -0.1, -1.0), spin=45))
m.add("Teeth", H(fast_union(teeth)), ICE, role="shine", tris=550, voxel=0.0162, smooth=False)

# ============================================================ bocca e orbite scure
maw = [ellipsoid((0.21, 0.08, 0.052), (0, -0.34, -0.205))]
for sx in (1, -1):
    maw.append(ellipsoid((0.126, 0.03, 0.066)).rot(0, -sx * 22, 0).translate(EYE_C[sx] + np.array([0, 0.045, 0.0])))
m.add("Maw", H(union(*maw)), MAW, role="eye", tris=250, voxel=0.0243)

# ============================================================ luce viola: nucleo, crepe, punte viola (Aura)
aura = [gem] + groups["GV"]
cracks = [
    [(0.28, 1.86), (0.38, 1.98), (0.5, 1.96), (0.6, 2.1), (0.76, 2.18)],
    [(-0.27, 1.88), (-0.35, 2.0), (-0.46, 2.03), (-0.56, 2.18)],
    [(0.33, 1.58), (0.46, 1.52), (0.58, 1.58), (0.72, 1.5), (0.84, 1.58)],
    [(-0.33, 1.56), (-0.45, 1.47), (-0.58, 1.5), (-0.72, 1.42)],
    [(0.06, 1.18), (0.13, 1.1), (0.05, 0.98)],
    [(-0.14, 1.2), (-0.26, 1.1), (-0.32, 0.98)],
]
for c in cracks:
    aura.append(crack(torso, [((x * 0.5, -0.1, z), (x, -1.2, z)) for x, z in c], r0=0.04, r1=0.02))
for sx in (1, -1):   # l'energia scorre lungo gli avambracci fino ai pugni
    a = ARM[sx]
    E, W, FC, RF = a["E"], a["W"], a["FC"], a["RF"]
    side = norm(np.cross(W - E, (0, 0, 1)))
    pairs = []
    for j, t in enumerate(np.linspace(0.17, 0.9, 6)):
        o = E + (W - E) * t
        pairs.append((o, o + side * (0.07 if j % 2 else -0.07) + np.array([0, 0, 0.6])))
    aura.append(crack(body_arms, pairs, r0=0.034, r1=0.02))
    pairs = []
    for j, x in enumerate(np.linspace(-0.36, 0.26, 5)):
        o = FC + (RF @ np.array([x, 0.06, 0.0], dtype=np.float32)) * FS
        pairs.append((o, o + RF @ np.array([0.0, 0.05 if j % 2 else -0.05, 1.0], dtype=np.float32)))
    aura.append(crack(fists, pairs, r0=0.03, r1=0.018))
scar = [((-0.05, 0.05, 0.25), (-0.06, -0.3, 0.42)), ((-0.12, 0.0, 0.2), (-0.16, -0.5, 0.26)),
        ((-0.2, 0.0, 0.1), (-0.27, -0.5, 0.13)), ((-0.24, -0.05, -0.05), (-0.34, -0.5, -0.06)),
        ((-0.22, -0.05, -0.15), (-0.33, -0.5, -0.2))]
aura.append(H(crack(head_l, scar, r0=0.026, r1=0.014)))
m.add("Aura", fast_union(aura), AURA, material="Neon", role="glow", tris=1250, voxel=0.0271)

# ============================================================ luce azzurra: occhi, punte azzurre, schegge dell'urto fra i pugni
glow_c = list(groups["GC"])
for sx in (1, -1):
    glow_c.append(H(ellipsoid(EYE_R).rot(0, -sx * 22, 0).translate(EYE_C[sx])))
IMPACT = np.array([0.0, -1.36, 0.66])
for ang, L, w in ((80, 0.4, 0.07), (35, 0.3, 0.06), (-5, 0.26, 0.06), (-45, 0.3, 0.06), (125, 0.3, 0.06)):
    t = math.radians(ang)   # ventaglio di schegge che schizzano in avanti dal punto d'urto
    d = norm((0.0, -math.cos(t), math.sin(t)))
    glow_c.append(orient(diamond3(w, w * 0.8, L * 0.5).rot(0, 0, 45), IMPACT + d * (0.1 + L * 0.5), d))
m.add("CrystalGlow", fast_union(glow_c), CYAN_GLOW, material="Neon", role="glow", tris=600, voxel=0.0226, smooth=False)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
