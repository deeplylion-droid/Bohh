"""Guardiane delle zone profonde (kind "prop", misure reali in stud).

CrystalMother: enorme tartaruga madre di cristallo, giocattolo "toy horror" imponente ma buffo:
corpo verde acqua, guscio blu notte cucito a pannelli con grandi cristalli sfaccettati viola e
ciano (Glass) e alcuni luminosi (Neon), occhi bianchi con pupille piccole sotto palpebre pesanti,
sopracciglia spesse, ghigno largo con file di dentini aguzzi, diadema di cristalli sulla testa.
Alta ~9, lunga ~12.

DragonMother: grande drago di lava madre, versione adulta e minacciosa del pet LavaDragon: corpo
rosso un po' ingobbito, placche dorate sulla pancia (con una cucitura), macchie di lava, creste e
narici luminose (Neon), grandi corna color osso, ali ripiegate con le punte alzate, mani grandi
ad artigli, occhi gialli a fessura sotto palpebre pesanti, sopracciglia bordeaux, ghigno con file
di dentini aguzzi, toppa cucita sulla coscia, coda arrotolata con la fiamma in punta. Alto ~11.

Piedi su z = 0, guardano verso -Y. Uso: python props/guardians.py [CrystalMother] [DragonMother]
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.sdf import (SDF, Frame, bezier, box, crystal, ellipsoid, prism, project, round_cone, sphere,  # noqa: E402
                     tube, union)
from propkit import (FineModel, eyelid, fast_union, grin_regions, halfspace, paint, patch_outline,  # noqa: E402
                     patch_region, run, stitches, unit)

WHITE = (255, 255, 255)


# ================================================================================ aiuti comuni

def crystal_cluster(base: SDF, center, direction, length: float, width: float, seed: int, sink: float = 0.45,
                    sides_n: int = 2, tilt: float = 0.0):
    """Gruppo di cristalli che spunta dalla superficie: (principale, laterali)."""
    rng = np.random.default_rng(seed)
    fr = Frame(base, center, direction, sink=length * sink * 0.5)
    main = crystal(length, width, tip=0.3).rot(90, 0, 0).rot(0, float(rng.uniform(0, 60)), 0).rot(tilt, 0, 0)
    sides = []
    for k in range(sides_n):
        ang = (k / max(sides_n, 1)) * 2 * math.pi + rng.uniform(-0.5, 0.5)
        ln = length * float(rng.uniform(0.45, 0.62))
        side = crystal(ln, width * float(rng.uniform(0.55, 0.72)), tip=0.32).rot(90, 0, 0)
        side = side.rot(0, float(rng.uniform(0, 60)), 0).rot(float(rng.uniform(18, 32)), 0, 0).rot(0, math.degrees(ang), 0)
        off = (math.cos(ang) * width * 0.9, 0.0, math.sin(ang) * width * 0.9)
        sides.append(fr.place(side, off))
    return fr.place(main), sides


def place_basis(shape: SDF, origin, ex, ey) -> SDF:
    """Orienta una forma modellata nel piano XY: x locale -> ex, y locale -> ey (ortogonalizzato), poi trasla."""
    ex = unit(ex)
    ey = np.asarray(ey, dtype=np.float64)
    ey = unit(ey - ex * (ey @ ex))
    ez = np.cross(ex, ey)
    mtx = np.stack([ex, ey, ez], axis=1).astype(np.float32)
    return shape.rotate(mtx).translate(origin)


def front_project(base: SDF, x: float, z: float, y_in: float):
    """Punto della superficie davanti (lungo -Y) partendo da (x, y_in, z) dentro la forma."""
    return project(base, (x, y_in, z), (0, -1, 0))


# ================================================================================ CrystalMother

TEAL = (34, 172, 164)
TEAL_DARK = (20, 112, 116)
SHELL = (34, 62, 104)
RIM = (126, 214, 196)
PLASTRON = (246, 222, 152)
CLAW = (240, 232, 214)
CRYS_PURPLE = (168, 92, 255)
CRYS_BLUE = (64, 196, 255)
GLOW_MINT = (130, 255, 236)
T_EYE = (26, 18, 40)
T_MOUTH = (40, 12, 52)
T_BROW = (30, 26, 64)
T_THREAD = (250, 212, 118)
T_PATCH = (122, 74, 196)

T_HEAD_C = np.array((0.0, -4.25, 6.05))
SHELL_C = np.array((0.0, 0.8, 4.1))
T_LEGS = [(sx * 2.9, y) for sx in (1, -1) for y in (-1.6, 3.4)]


def hex_edges(spacing: float, rx: float, ry: float, cy: float):
    """Spigoli di una griglia esagonale (vista dall'alto) dentro l'ellisse (rx, ry) centrata in (0, cy)."""
    R = spacing / math.sqrt(3)
    edges = set()
    for i in range(-6, 7):
        for j in range(-6, 7):
            cx = i * 1.5 * R
            cyy = cy + j * spacing + (spacing / 2 if i % 2 else 0)
            verts = [(round(cx + R * math.cos(math.pi / 3 * k), 4), round(cyy + R * math.sin(math.pi / 3 * k), 4))
                     for k in range(6)]
            for k in range(6):
                a, b = verts[k], verts[(k + 1) % 6]
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                if (mx / rx) ** 2 + ((my - cy) / ry) ** 2 < 1:
                    edges.add(tuple(sorted((a, b))))
    return sorted(edges)


def crystal_mother() -> FineModel:
    m = FineModel("CrystalMother", "prop", voxel=0.06)

    # ------------------------------------------------------------------ corpo (testa, collo, zampe, coda)
    head = ellipsoid((2.2, 1.95, 1.8), tuple(T_HEAD_C))
    beak = ellipsoid((1.6, 1.15, 1.1), tuple(T_HEAD_C + (0, -1.2, -0.55)))
    head_full = union(head, beak, k=0.55)
    neck = round_cone((0, -1.3, 4.1), (0, -3.4, 5.5), 1.6, 1.35)
    belly = ellipsoid((3.4, 3.9, 1.5), (0, 0.8, 3.3))
    legs, feet = [], []
    for x, y in T_LEGS:
        legs.append(round_cone((x * 0.8, y, 3.55), (x, y - 0.1, 1.0), 1.32, 1.12))
        feet.append(ellipsoid((1.3, 1.45, 0.75), (x, y - 0.35, 0.68)))
    tail = round_cone((0, 4.3, 3.1), (0, 5.6, 2.4), 0.8, 0.32)
    core = union(union(belly, neck, k=0.6), head_full, k=0.7)
    core = union(core, *legs, *feet, tail, k=0.35)
    m.add("Body", core, TEAL, tris=5000)

    # ------------------------------------------------------------------ guscio a cupola cucito a pannelli, bordo e piastrone
    dome = ellipsoid((4.3, 4.5, 2.75), tuple(SHELL_C))
    shell_solid = dome.intersect(halfspace((0, 0, -1), (0, 0, 3.4)), k=0.25)
    rim = ellipsoid((4.55, 4.75, 0.62), (0, 0.8, 3.45))
    # solchi fra le placche esagonali (griglia proiettata sulla cupola) con punti di cucitura a cavallo
    grooves, seams = [], []
    for a, b in hex_edges(2.15, 3.7, 3.9, 0.8):
        pts = []
        for t in np.linspace(0, 1, 6):
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            pts.append(project(dome, tuple(SHELL_C), (x, y - SHELL_C[1], 2.3)))
        grooves.append(tube([p for p, _ in pts], 0.14))
        seams.append(stitches(pts, 0.42, 0.2, 0.06, inset=0.03))
    shell = shell_solid.subtract(fast_union(*grooves), k=0.04)
    m.add("Shell", shell, SHELL, role="detail", tris=2400)
    m.add("Rim", rim.subtract(dome.offset(-0.35)), RIM, role="detail", tris=1000)
    plastron = paint(core, ellipsoid((2.2, 1.3, 1.9), (0, -1.75, 3.95)), t=0.05, depth=0.12)
    plates = union(*[box((3.0, 1.5, 0.05), (0, -2.4, z)) for z in (3.35, 3.95, 4.55)])
    m.add("Plastron", plastron.subtract(plates), PLASTRON, role="detail", tris=700, voxel=0.04)

    # ------------------------------------------------------------------ cristalli sul guscio
    purple, blue, glow = [], [], []
    clusters = [  # direzione dal centro del guscio, lunghezza, larghezza, colore principale
        ((0.0, 0.2, 1.0), 3.05, 0.95, "p"), ((0.8, -0.25, 0.7), 2.7, 0.8, "b"), ((-0.8, -0.1, 0.68), 2.8, 0.82, "p"),
        ((0.62, 0.8, 0.55), 2.35, 0.7, "b"), ((-0.57, 0.85, 0.5), 2.25, 0.68, "b"), ((0.1, -0.85, 0.7), 2.0, 0.6, "b"),
        ((0.0, 1.0, 0.3), 1.8, 0.56, "p"),
    ]
    for i, (d, ln, w, col) in enumerate(clusters):
        main, sides = crystal_cluster(dome, tuple(SHELL_C), d, ln, w, seed=10 + i, sides_n=2 if i else 3)
        (purple if col == "p" else blue).append(main)
        for j, sd in enumerate(sides):
            (glow if j == 0 else (blue if col == "p" else purple)).append(sd)
    # piccoli cristalli anche sulle zampe posteriori (lato esterno) e sulla punta della coda
    for sx in (1, -1):
        main, sides = crystal_cluster(core, (sx * 2.6, 3.4, 2.3), (sx, 0.25, 0.5), 1.05, 0.33, seed=40 + sx, sides_n=1)
        purple.append(main)
        blue.extend(sides)
    main, sides = crystal_cluster(core, (0, 5.2, 2.6), (0.0, 0.6, 1.0), 0.9, 0.28, seed=44, sides_n=1)
    blue.append(main)
    purple.extend(sides)
    # diadema: tre cristalli sulla fronte (quello centrale luminoso)
    crown_mid = Frame(head_full, tuple(T_HEAD_C), (0, -0.3, 1.0), sink=0.15).place(
        crystal(1.35, 0.32, tip=0.38).rot(90, 0, 0).rot(0, 30, 0))
    crown_side = [Frame(head_full, tuple(T_HEAD_C), (sx * 0.42, -0.32, 1.0), sink=0.12).place(
        crystal(0.9, 0.23, tip=0.4).rot(90, 0, 0).rot(0, 15, 0).rot(0, 0, sx * 16)) for sx in (1, -1)]
    glow.append(crown_mid)
    m.add("CrystalsPurple", fast_union(*purple, *crown_side), CRYS_PURPLE, material="Glass", role="detail", tris=1800,
          voxel=0.025, smooth=False)
    m.add("CrystalsBlue", fast_union(*blue), CRYS_BLUE, material="Glass", role="detail", tris=1500, voxel=0.03,
          smooth=False)
    m.add("CrystalsGlow", fast_union(*glow), GLOW_MINT, material="Neon", role="glow", tris=1100, voxel=0.025,
          smooth=False)

    # ------------------------------------------------------------------ faccia: occhi bianchi a pupilla piccola, palpebre pesanti
    eye_r = (0.62, 0.3, 0.62)
    sides_x = (1, -1)
    frames = [Frame(head_full, tuple(T_HEAD_C), (0.48 * sx, -1.0, 0.3), sink=0.14) for sx in sides_x]
    ball = ellipsoid(eye_r)
    m.add("EyeWhites", union(*[f.place(ball) for f in frames]), WHITE, role="shine", tris=450, voxel=0.025)
    # pupille piccole che guardano in basso verso il centro (x locale = -x del mondo)
    pupils = [f.place(ball.offset(0.02).intersect(sphere(0.24, (0.1 * sx, -0.32, -0.14))).subtract(ball.offset(-0.08)))
              for f, sx in zip(frames, sides_x)]
    m.add("Pupils", union(*pupils), T_EYE, role="eye", tris=260, voxel=0.015)
    shines = [f.place(sphere(0.075), (0.1 * sx - 0.08, -0.36, -0.04)) for f, sx in zip(frames, sides_x)]
    m.add("Shine", union(*shines), WHITE, role="shine", tris=100, voxel=0.012)
    lids = union(eyelid(frames[0], eye_r, 0.1, -0.34, grow=(0.07, 0.09, 0.07)),
                 eyelid(frames[1], eye_r, 0.1, 0.34, grow=(0.07, 0.09, 0.07)))
    m.add("Lids", lids, TEAL_DARK, role="detail", tris=450, voxel=0.025)

    # ghigno largo con file di dentini aguzzi
    tip, _ = front_project(head_full, 0.0, T_HEAD_C[2] - 0.5, T_HEAD_C[1])
    mouth, up, lo = grin_regions(0.0, tip[2] - 0.2, 1.38, 0.5, 0.0, 0.5, 15, 8, 0.17, -7.5, -4.0, tooth_len=0.55,
                                 lo_len=0.42)
    m.add("Mouth", paint(core, mouth, t=0.04, depth=0.1), T_MOUTH, role="eye", tris=450, voxel=0.02)
    teeth = union(up, lo).intersect(mouth.offset(0.005))
    m.add("Teeth", paint(core, teeth, t=0.075, depth=0.04), WHITE, role="shine", tris=650, voxel=0.014)

    # sopracciglia spesse e severe, cuciture (pannelli, collo, bordo), toppa cucita sulla zampa
    brows = []
    for sx in sides_x:
        ctrl = [(sx * 0.28, -1.0, 0.6), (sx * 0.85, -1.0, 0.9), (sx * 1.38, -1.0, 0.92)]
        path = [project(head_full, tuple(T_HEAD_C), d) for d in bezier(ctrl[0], ctrl[1], ctrl[1], ctrl[2], 10)]
        brows.append(tube([p + n * 0.03 for p, n in path], list(np.linspace(0.22, 0.13, len(path)))))
    nd = unit((0, -2.1, 1.4))
    nu = np.array((1.0, 0, 0))
    nv = np.cross(nd, nu)
    neck_ring = [project(core, (0, -3.0, 5.25), tuple(math.cos(a) * nu + math.sin(a) * nv))
                 for a in np.linspace(0, 2 * math.pi, 41)]
    neck_seam = stitches(neck_ring, 0.34, 0.15, 0.055, inset=-0.035, cross=True)
    shell_all = union(shell_solid, rim)
    rim_line = [project(shell_all, (0, 0.8, 3.5), (4.4 * math.sin(a), -4.6 * math.cos(a), 0.0))
                for a in np.linspace(-math.pi * 0.95, math.pi * 0.95, 60)]
    rim_seam = stitches(rim_line, 0.38, 0.14, 0.055, inset=-0.035)
    patch_c, patch_n = project(core, (2.5, -1.7, 2.3), (1, -0.55, 0.0))
    patch = dict(center=patch_c, normal=patch_n, rx=0.62, ry=0.52, angle=-12)
    m.add("Patch", paint(core, patch_region(**patch), t=0.04, depth=0.1), T_PATCH, material="Fabric", role="detail",
          tris=250, voxel=0.03)
    patch_seam = stitches(patch_outline(core.offset(0.04), **{**patch, "rx": 0.49, "ry": 0.4}), 0.18, 0.08, 0.04,
                          inset=-0.025, cross=True)
    m.add("Brows", union(*brows), T_BROW, role="detail", tris=400, voxel=0.03)
    m.add("Thread", fast_union(neck_seam, rim_seam, patch_seam, *seams), T_THREAD, role="detail", tris=1900, voxel=0.03)

    # artigli grandi color osso (tre per piede)
    claws = []
    for x, y in T_LEGS:
        for dx in (-0.56, 0.0, 0.56):
            claws.append(round_cone((x + dx, y - 1.25, 0.46), (x + dx * 1.15, y - 1.98, 0.22), 0.34, 0.1))
    m.add("Claws", union(*claws), CLAW, role="detail", tris=700, voxel=0.03)
    return m


# ================================================================================ DragonMother

D_RED = (212, 40, 34)
D_RED_LID = (168, 24, 28)
D_BORDEAUX = (110, 14, 30)
D_GOLD = (255, 190, 56)
D_BONE = (255, 234, 192)
D_MEMBRANE = (255, 116, 38)
D_LAVA = (255, 106, 18)
D_FLAME_IN = (255, 214, 64)
D_EYE = (255, 214, 66)
D_PUPIL = (30, 8, 14)
D_MOUTH = (46, 8, 18)
D_THREAD = (62, 10, 28)
D_PATCH = (88, 40, 124)

D_HEAD_C = np.array((0.0, -1.0, 8.45))
D_SNOUT_C = np.array((0.0, -2.42, 8.05))
D_TAIL = bezier((0, 2.0, 2.9), (0.3, 4.3, 1.2), (2.8, 4.9, 0.62), (4.2, 3.0, 0.72), 18)
D_TAIL_R = [1.05 - 0.72 * i / 18 for i in range(19)]
# la testa e' modellata dritta, poi inclinata e girata un po' verso destra (posa con carattere)
D_HEAD_POSE = dict(rx=5, ry=5, rz=12, pivot=(0, -0.4, 7.4))


def HD(shape):
    """Porta una forma della testa del drago nella posa finale."""
    return shape.rot(**D_HEAD_POSE)


def dragon_mother() -> FineModel:
    m = FineModel("DragonMother", "prop", voxel=0.06)

    # ------------------------------------------------------------------ testa (coordinate "dritte")
    head = ellipsoid((1.7, 1.52, 1.42), tuple(D_HEAD_C))
    snout = ellipsoid((1.2, 1.15, 0.82), tuple(D_SNOUT_C))
    cheeks = union(*[ellipsoid((0.82, 0.78, 0.68), (sx * 1.0, -1.72, 7.9)) for sx in (1, -1)])
    head_full = union(head, snout, cheeks, k=0.5)

    # ------------------------------------------------------------------ corpo: busto largo e ingobbito, zampe lunghe, braccia
    hips = ellipsoid((2.2, 1.95, 2.0), (0, 0.55, 3.95))
    chest = ellipsoid((2.3, 1.9, 2.1), (0, -0.15, 5.95))
    shoulders = [sphere(1.0, (sx * 1.95, 0.0, 6.65)) for sx in (1, -1)]
    neck = round_cone((0, 0.1, 6.8), (0, -0.6, 7.95), 1.3, 1.08)
    legs = []
    for sx in (1, -1):
        x = sx * 1.64
        legs += [ellipsoid((1.05, 1.3, 1.5), (sx * 1.55, 0.35, 3.1)),
                 round_cone((x, 0.25, 2.6), (x, -0.15, 0.82), 0.82, 0.64),
                 ellipsoid((1.05, 1.5, 0.64), (x, -0.72, 0.58))]
    arms, hands, hand_c = [], [], []
    FINGERS = ((-0.5, -0.12), (0.0, 0.08), (0.5, -0.12))
    for sx in (1, -1):
        sh, el, wr = (sx * 2.2, -0.05, 6.55), (sx * 3.05, -0.35, 5.15), (sx * 2.95, -1.65, 5.75)
        arms += [round_cone(sh, el, 0.78, 0.64), round_cone(el, wr, 0.64, 0.56)]
        hc = np.array((sx * 2.95, -2.15, 5.95))
        hand_c.append(hc)
        fingers = [round_cone(tuple(hc), tuple(hc + (sx * dx, -0.85, 0.5 + dz)), 0.42, 0.3) for dx, dz in FINGERS]
        thumb = round_cone(tuple(hc), tuple(hc + (sx * -0.7, -0.35, 0.5)), 0.34, 0.25)
        hands.append(union(ellipsoid((1.0, 0.88, 0.82), tuple(hc)), *fingers, thumb, k=0.14))
    tail = tube(D_TAIL, D_TAIL_R, k=0.1)
    core = union(union(hips, chest, *shoulders, k=0.8), neck, k=0.5)
    core = union(core, HD(head_full), k=0.55)
    core = union(core, *legs, *arms, k=0.3)
    core = union(core, *hands, tail, k=0.2)
    m.add("Body", core, D_RED, tris=6400)

    # ------------------------------------------------------------------ pancia a placche dorate
    belly_region = ellipsoid((1.6, 1.3, 3.0), (0, -1.5, 4.95))
    grooves = union(*[box((3.0, 2.5, 0.05), (0, -1.6, z)) for z in (3.35, 4.0, 4.65, 5.3, 5.95, 6.6)])
    m.add("Belly", paint(core, belly_region, t=0.04, depth=0.12).subtract(grooves), D_GOLD, role="detail", tris=1500,
          voxel=0.04)

    # ------------------------------------------------------------------ lava: macchie, narici, creste, fiamma della coda
    spot_list = [((1.9, 0.0, 6.7), (0.6, 0.5, 0.6), 0.55), ((-1.9, 0.0, 6.7), (-0.6, 0.6, 0.5), 0.5),
                 ((0.0, -1.0, 8.45), (0.45, 0.4, 1.0), 0.42), ((0.0, -1.0, 8.45), (-0.5, 0.6, 1.0), 0.34),
                 ((1.5, 0.4, 3.2), (1, 0.6, 0.2), 0.5), ((-1.5, 0.5, 3.6), (-1, 0.7, 0.2), 0.45),
                 ((0.6, 0.8, 4.8), (0.4, 1, 0.1), 0.45), ((-0.5, 0.6, 5.9), (-0.3, 1, 0.2), 0.4),
                 ((2.9, -0.4, 5.4), (1, 0.1, 0.4), 0.34), ((-2.9, -0.4, 5.4), (-1, 0.1, 0.4), 0.3)]
    spots = []
    for inside, d, r in spot_list:
        p, _ = project(core, inside, d)
        spots.append(sphere(r, tuple(p)))
    for i in (4, 8, 12, 15):  # macchie sulla coda
        p, _ = project(core, D_TAIL[i], (0.2, 0.3, 1))
        spots.append(sphere(D_TAIL_R[i] * 0.55, tuple(p)))
    nostrils = []
    for sx in (1, -1):
        c, _ = project(head_full, tuple(D_SNOUT_C), (sx * 0.32, -1.0, 0.55))
        nostrils.append(ellipsoid((0.14, 0.3, 0.1), tuple(c)).rot(0, sx * 22, 0, pivot=tuple(c)))
    lava = union(paint(core, union(*spots), t=0.035, depth=0.1), HD(paint(head_full, union(*nostrils), t=0.03, depth=0.12)))

    spikes = []
    spine = [(9.55, 0.9), (8.95, 0.95), (8.05, 1.0), (7.15, 1.05), (6.25, 1.05), (5.35, 1.0), (4.45, 0.9), (3.55, 0.75)]
    for z, ln in spine:
        inside = (0, -0.8, z) if z > 8.3 else (0, 0.0, z)
        p, n = project(core, inside, (0, 1, 0.15))
        tipd = unit(n + np.array((0, 0.35, 0.55)))
        spikes.append(round_cone(tuple(p - n * 0.3), tuple(p + tipd * ln), 0.42, 0.06))
    for i in range(3, 17, 3):
        p, n = project(core, D_TAIL[i], (0, 0, 1))
        spikes.append(round_cone(tuple(p - n * 0.2), tuple(p + n * D_TAIL_R[i] * 0.8), D_TAIL_R[i] * 0.42, 0.05))

    tip = np.array(D_TAIL[-1])
    fo = tip + (0.15, 0, 0.3)
    fi = tip + (0.12, -0.25, 0.32)
    flame_out = union(sphere(0.55, tuple(fo)), round_cone(tuple(fo), tuple(tip + (0.5, -0.3, 1.9)), 0.55, 0.06), k=0.15)
    flame_in = union(sphere(0.34, tuple(fi)), round_cone(tuple(fi), tuple(tip + (0.36, -0.42, 1.45)), 0.34, 0.04), k=0.1)
    # tutto cio' che e' lava arancione in una sola parte: macchie, narici, creste, fiamma della coda
    m.add("Lava", fast_union(lava, *spikes, flame_out), D_LAVA, material="Neon", role="glow", tris=2800, voxel=0.035)
    m.add("FlameCore", flame_in, D_FLAME_IN, material="Neon", role="glow", tris=300, voxel=0.03)

    # ------------------------------------------------------------------ corna e spuntoni delle guance (osso), artigli
    horns = []
    for sx in (1, -1):
        pts = bezier((sx * 0.7, -0.55, 9.55), (sx * 0.95, 0.05, 10.55), (sx * 1.65, 0.85, 11.0), (sx * 2.3, 1.4, 10.6), 14)
        horns.append(tube(pts, [0.5 - 0.42 * i / 14 for i in range(15)]))
        horns.append(round_cone((sx * 1.55, -1.3, 8.2), (sx * 2.35, -0.6, 8.5), 0.3, 0.06))
    claws = []
    for sx in (1, -1):
        x = sx * 1.64
        for dx in (-0.47, 0.0, 0.47):
            claws.append(round_cone((x + dx, -2.0, 0.42), (x + dx * 1.2, -2.6, 0.16), 0.27, 0.07))
    for sx, hc in zip((1, -1), hand_c):
        for dx, dz in FINGERS:
            f_tip = hc + (sx * dx, -0.85, 0.5 + dz)
            claws.append(round_cone(tuple(f_tip + (0, -0.12, 0.0)), tuple(f_tip + (sx * dx * 0.3, -0.72, 0.5)), 0.28, 0.05))
        th_tip = hc + (sx * -0.7, -0.35, 0.5)
        claws.append(round_cone(tuple(th_tip), tuple(th_tip + (sx * -0.25, -0.38, 0.38)), 0.21, 0.04))
    m.add("Horns", union(HD(union(*horns)), *claws), D_BONE, role="detail", tris=1800, voxel=0.03)

    # ------------------------------------------------------------------ ali ripiegate (membrana + ossa), animabili
    S = 1.3
    wing_poly = [(x * S, y * S) for x, y in ((0.0, 0.0), (0.55, 3.1), (1.75, 1.25), (1.32, 0.95), (1.6, -0.55),
                                             (1.12, -0.62), (0.98, -1.85), (0.6, -1.5), (0.3, -2.2), (0.0, -0.9))]
    membrane = prism(wing_poly, -0.08, 0.08, round=0.06)
    wr_ = (0.55 * S, 3.1 * S, 0)
    bones = union(tube([(0, 0, 0), wr_], [0.3, 0.22]),
                  tube([wr_, (1.75 * S, 1.25 * S, 0)], [0.18, 0.08]),
                  tube([wr_, (1.6 * S, -0.55 * S, 0)], [0.17, 0.07]),
                  tube([wr_, (0.98 * S, -1.85 * S, 0)], [0.16, 0.06]),
                  round_cone(wr_, (0.62 * S, 3.62 * S, 0.0), 0.2, 0.05))  # artiglio del polso
    for sx, nm in ((1, "WingR"), (-1, "WingL")):
        root = (sx * 1.45, 1.3, 6.4)
        ex, ey = (sx * 0.8, 1.0, -0.15), (sx * 0.12, -0.1, 1.0)
        m.add(nm, place_basis(membrane, root, ex, ey), D_MEMBRANE, role="detail", tris=800, voxel=0.03, group=nm,
              pivot=root)
        m.add(nm + "Bone", place_basis(bones, root, ex, ey), D_BORDEAUX, role="detail", tris=550, voxel=0.03, group=nm,
              pivot=root)

    # ------------------------------------------------------------------ faccia: occhi gialli a fessura, palpebre, sopracciglia, ghigno
    eye_r = (0.52, 0.25, 0.56)
    sides_x = (1, -1)
    frames = [Frame(head_full, tuple(D_HEAD_C), (0.5 * sx, -1.0, 0.3), sink=0.12) for sx in sides_x]
    ball = ellipsoid(eye_r)
    m.add("Eyes", HD(union(*[f.place(ball) for f in frames])), D_EYE, role="eye", tris=420, voxel=0.025)
    slit = ball.offset(0.02).intersect(ellipsoid((0.085, 0.5, 0.4), (0, -0.3, -0.02))).subtract(ball.offset(-0.08))
    m.add("Pupils", HD(union(*[f.place(slit) for f in frames])), D_PUPIL, role="eye", tris=220, voxel=0.015)
    shines = [f.place(sphere(0.072), (-0.17, -0.28, 0.12)) for f in frames]
    shines += [f.place(sphere(0.038), (0.19, -0.26, -0.19)) for f in frames]
    m.add("Shine", HD(union(*shines)), WHITE, role="shine", tris=120, voxel=0.012)
    lids = union(eyelid(frames[0], eye_r, 0.13, -0.42, grow=(0.07, 0.09, 0.07)),
                 eyelid(frames[1], eye_r, 0.13, 0.42, grow=(0.07, 0.09, 0.07)))
    m.add("Lids", HD(lids), D_RED_LID, role="detail", tris=400, voxel=0.025)
    brows = []
    for sx in sides_x:
        ctrl = [(sx * 0.22, -1.0, 0.52), (sx * 0.8, -1.0, 0.86), (sx * 1.36, -1.0, 1.0)]
        path = [project(head_full, tuple(D_HEAD_C), d) for d in bezier(ctrl[0], ctrl[1], ctrl[1], ctrl[2], 10)]
        brows.append(tube([p + n * 0.04 for p, n in path], list(np.linspace(0.24, 0.13, len(path)))))

    sn, _ = front_project(head_full, 0.0, D_SNOUT_C[2], D_SNOUT_C[1])
    mouth, up, lo = grin_regions(0.0, sn[2] - 0.28, 1.22, 0.5, 0.0, 0.5, 13, 7, 0.17, -4.5, -1.6, tooth_len=0.55,
                                 lo_len=0.42, asym=0.12)
    m.add("Mouth", HD(paint(head_full, mouth, t=0.04, depth=0.1)), D_MOUTH, role="eye", tris=420, voxel=0.02)
    teeth = union(up, lo).intersect(mouth.offset(0.005))
    m.add("Teeth", HD(paint(head_full, teeth, t=0.075, depth=0.04)), WHITE, role="shine", tris=600, voxel=0.014)

    # ------------------------------------------------------------------ cuciture: lato della pancia; toppa sulla coscia
    belly_seam = [project(core, (-0.9, 0.0, z), (-0.35, -1, 0)) for z in np.linspace(6.7, 3.1, 16)]
    seams = [stitches(belly_seam, 0.3, 0.15, 0.055, line_r=0.035, inset=-0.04)]
    patch_c, patch_n = project(core, (1.35, 0.2, 2.9), (1, -0.45, 0.1))
    patch = dict(center=patch_c, normal=patch_n, rx=0.62, ry=0.52, angle=10)
    m.add("Patch", paint(core, patch_region(**patch), t=0.04, depth=0.1), D_PATCH, material="Fabric", role="detail",
          tris=250, voxel=0.03)
    seams.append(stitches(patch_outline(core.offset(0.04), **{**patch, "rx": 0.49, "ry": 0.4}), 0.18, 0.08, 0.04,
                          inset=-0.025, cross=True))
    # sopracciglia e cuciture nello stesso bordeaux scuro
    m.add("Thread", fast_union(HD(union(*brows)), *seams), D_THREAD, role="detail", tris=960, voxel=0.025)
    return m


CATALOG = {"CrystalMother": crystal_mother, "DragonMother": dragon_mother}

if __name__ == "__main__":
    run(CATALOG)
