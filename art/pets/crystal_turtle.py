"""Tartaruga di Cristallo (CrystalTurtle) - pet Epico (grotte di cristallo).

Carattere: il brontolone. Sopracciglia aggrottate, palpebre pesanti, mento in fuori con i denti di
cristallo che spuntano dal labbro inferiore e un occhio che brilla. Il guscio e' un geode pieno di
cristalli sfaccettati viola e azzurri con le punte luminose.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, capsule, ellipsoid, project, project_curve, rot_matrix, round_cone,  # noqa: E402
                     sphere, tube, union)
from lib.toy import Model  # noqa: E402

SKIN = (44, 164, 150)
SKIN_LIGHT = (176, 230, 196)
SHELL = (52, 38, 98)
CRYSTAL_P = (168, 86, 240)
CRYSTAL_C = (70, 214, 240)
GLOW_C = (110, 255, 250)
GLOW_P = (255, 90, 230)
TOOTH = (214, 250, 255)
DARK = (28, 22, 48)
EYE = (20, 16, 30)
WHITE = (255, 255, 255)


# ============================================================ helper "toy horror" (definiti qui: lib non si tocca)


def poly_xz(poly, y0, y1):
    """Regione disegnata nella vista frontale: poligono nel piano XZ estruso lungo Y fra y0 e y1."""
    pts = np.asarray(poly, dtype=np.float32)

    def f(p):
        px, pz = p[:, 0], p[:, 2]
        d = np.full(len(p), np.inf, dtype=np.float32)
        s = np.ones(len(p), dtype=np.float32)
        for i in range(len(pts)):
            vi, vj = pts[i], pts[i - 1]
            ex, ez = vj[0] - vi[0], vj[1] - vi[1]
            wx, wz = px - vi[0], pz - vi[1]
            t = np.clip((wx * ex + wz * ez) / max(ex * ex + ez * ez, 1e-12), 0.0, 1.0)
            d = np.minimum(d, (wx - ex * t) ** 2 + (wz - ez * t) ** 2)
            c1, c2, c3 = pz >= vi[1], pz < vj[1], ex * wz > ez * wx
            s = np.where((c1 & c2 & c3) | (~c1 & ~c2 & ~c3), -s, s)
        return np.maximum(s * np.sqrt(d), np.maximum(y0 - p[:, 1], p[:, 1] - y1))

    return SDF(f, (pts[:, 0].min(), y0, pts[:, 1].min()), (pts[:, 0].max(), y1, pts[:, 1].max()))


def lid_shape(radii, cut, slope=0.0, grow=0.016, k=0.012):
    """Palpebra pesante (coordinate locali del Frame): calotta dell'occhio ingrandito sopra z = cut + slope*x."""
    a, b, c = radii
    nrm = math.sqrt(1.0 + slope * slope)
    above = SDF(lambda p: (cut + slope * p[:, 0] - p[:, 2]) / nrm, (-1, -1, -1), (1, 1, 1))
    return ellipsoid((a + grow, b + grow, c + grow)).intersect(above, k=k)


def surface_tube(base, pts2d, radii, y=-0.3, inset=0.0, direction=(0, -1, 0)):
    """Tubo (sopracciglio, bocca) disegnato nella vista frontale e appoggiato sulla superficie."""
    return tube(project_curve(base, [(x, y, z) for x, z in pts2d], direction, inset=inset), radii)


def grin(base, upper, lower, y_back, up_teeth=(), down_teeth=(), tooth=(0.06, 0.026), d=0.034):
    """Ghigno: bocca scura fra labbro superiore e inferiore (punti 2D x,z da sinistra a destra) + dentini."""
    region = poly_xz(list(upper) + list(lower[-2:0:-1]), -3.0, y_back)  # gli angoli sono in comune
    mouth = base.offset(d).intersect(region, k=0.006)
    lip = base.offset(d)
    (ux, uz), (lx, lz) = np.array(upper).T, np.array(lower).T
    length, r = tooth
    teeth = []
    for x in up_teeth:
        z = float(np.interp(x, ux, uz))
        b, t = project_curve(lip, [(x, y_back - 0.6, z + 0.012), (x, y_back - 0.6, z - length)], (0, -1, 0), inset=0.004)
        teeth.append(round_cone(b, t, r, 0.006))
    for x in down_teeth:
        z = float(np.interp(x, lx, lz))
        b, t = project_curve(lip, [(x, y_back - 0.6, z - 0.012), (x, y_back - 0.6, z + length * 0.8)], (0, -1, 0),
                             inset=0.004)
        teeth.append(round_cone(b, t, r * 0.85, 0.006))
    return mouth, teeth


def paint(base, region, d=0.022, depth=0.045, k=0.012):
    """Vernice a strato sottile (fra -depth e +d dalla superficie) ritagliata dalla regione: niente grandi
    superfici nascoste, quindi voxel fine a parita' di triangoli. Spessore d + depth >= 2.5 voxel."""
    t = (d + depth) / 2
    return base.offset(d - t).shell(t).intersect(region, k=k)


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
    d = np.asarray(direction, dtype=np.float64)
    d = d / np.linalg.norm(d)
    ax = np.cross([0.0, 0.0, 1.0], d)
    s = float(np.linalg.norm(ax))
    if spin:
        shape = shape.rot(0, 0, spin)
    if s > 1e-6:
        shape = shape.rotate(rot_matrix(ax, math.degrees(math.atan2(s, d[2]))))
    return shape.translate(base)


def below(z):
    """Semispazio z < valore (coordinate locali del cristallo)."""
    return SDF(lambda p: p[:, 2] - z, (-5, -5, -5), (5, 5, z))


def above(z):
    return SDF(lambda p: z - p[:, 2], (-5, -5, z), (5, 5, 5))


# ============================================================ modello
m = Model("CrystalTurtle", "pet")
PK = 0.01

# corpo sotto il guscio, collo e testa grande sporgente, zampe tozze, codina
HEAD_C = (0, -1.16, 1.34)
HZ = HEAD_C[2]
head = ellipsoid((0.66, 0.6, 0.56), HEAD_C)
jaw = ellipsoid((0.47, 0.33, 0.22), (0, -1.52, HZ - 0.27))
head_u = union(head, jaw, k=0.13)
neck = capsule((0, -0.4, 0.72), (0, -0.95, 1.12), 0.34)
belly_body = ellipsoid((0.85, 0.95, 0.42), (0, 0.2, 0.58))
LEGS = [(sx, y) for sx in (1, -1) for y in (-0.45, 0.72)]
legs = []
for sx, y in LEGS:
    fx, fy = sx * 0.8, y + (-0.12 if y < 0 else 0.1)
    toes = [sphere(0.08, (fx + sx * 0.1 * math.sin(a), fy - 0.25 * math.cos(a) * (1 if y < 0 else -1), 0.08))
            for a in (-0.7, 0.0, 0.7)]
    legs.append(union(round_cone((sx * 0.5, y * 0.85, 0.58), (fx, fy, 0.2), 0.23, 0.21),
                       ellipsoid((0.26, 0.3, 0.15), (fx, fy, 0.15)), *toes, k=0.06))
tail = round_cone((0, 0.95, 0.5), (0, 1.4, 0.32), 0.17, 0.04)
core_u = union(union(belly_body, neck, k=0.15), head_u, k=0.2)

# occhi: il destro normale, il sinistro (+X) luminoso e un po' piu' grande; palpebre pesanti e aggrottate
frames = {sx: Frame(head_u, HEAD_C, (0.46 * sx, -1.0, 0.3), sink=0.04) for sx in (1, -1)}
EYE_N = (0.135, 0.08, 0.155)
EYE_G = (0.15, 0.085, 0.17)
lids = union(frames[-1].place(lid_shape(EYE_N, 0.03, 0.3)), frames[1].place(lid_shape(EYE_G, 0.035, -0.3)))
core = union(core_u, *legs, k=0.08)
core = union(core, tail, k=0.06)
core = union(core, lids)
m.add("Body", core, SKIN, tris=4600)

# mento e gola chiari
throat = paint(core_u, ellipsoid((0.46, 0.6, 0.32), (0, -1.3, 0.85)), depth=0.06, k=PK)
m.add("Throat", throat, SKIN_LIGHT, role="detail", tris=700, voxel=0.028)

# guscio-geode
dome = ellipsoid((1.05, 1.15, 0.62), (0, 0.2, 0.86))
rim = ellipsoid((1.12, 1.22, 0.15), (0, 0.2, 0.55))
shell = union(dome, rim, k=0.12).intersect(SDF(lambda p: 0.4 - p[:, 2], (-2, -2, 0.4), (2, 2, 2)))
m.add("Shell", shell, SHELL, role="detail", tris=1800)

# cristalli: (direzione dal centro del guscio, lunghezza, raggio, colore, punta luminosa)
SHELL_C = np.array([0.0, 0.2, 0.86])
CRYSTALS = [((0.0, 0.08, 1.0), 1.6, 0.27, "P", True), ((0.55, -0.25, 1.0), 1.05, 0.2, "C", True),
            ((-0.6, 0.15, 1.0), 1.15, 0.21, "P", False), ((-0.3, -0.55, 1.0), 0.78, 0.16, "C", True),
            ((0.45, 0.6, 1.0), 0.88, 0.18, "P", True), ((-0.45, 0.85, 0.9), 0.72, 0.15, "C", False),
            ((0.95, -0.45, 0.6), 0.58, 0.13, "C", True), ((-1.0, -0.25, 0.6), 0.62, 0.14, "P", False),
            ((0.2, -0.75, 0.95), 0.46, 0.11, "P", False), ((0.05, 1.0, 0.65), 0.52, 0.12, "C", False),
            ((0.75, 0.3, 0.8), 0.36, 0.08, "G", True), ((-0.75, 0.55, 0.8), 0.34, 0.075, "M", True)]
groups = {"P": [], "C": [], "GC": [], "GP": []}
for i, (d, length, r, col, glow) in enumerate(CRYSTALS):
    p, _ = project(dome, SHELL_C, d)
    base = p - np.asarray(d) / np.linalg.norm(d) * 0.16
    c = crystal(length, r)
    if col in ("G", "M"):
        groups["GC" if col == "G" else "GP"].append(orient(c, base, d, spin=17 * i))
        continue
    cut = length * (0.74 if glow else 2.0)
    groups[col].append(orient(c.intersect(below(cut)), base, d, spin=17 * i))
    if glow:
        groups["GC" if col == "C" else "GP"].append(orient(c.intersect(above(cut)), base, d, spin=17 * i))
m.add("CrystalsPurple", union(*groups["P"]), CRYSTAL_P, material="Glass", role="detail", tris=1700, voxel=0.02,
      smooth=False)
m.add("CrystalsCyan", union(*groups["C"]), CRYSTAL_C, material="Glass", role="detail", tris=1500, voxel=0.02,
      smooth=False)

# occhio luminoso + punte dei cristalli luminose (Neon)
glow_eye = frames[1].place(ellipsoid(EYE_G))
m.add("GlowCyan", union(*groups["GC"], glow_eye), GLOW_C, material="Neon", role="glow", tris=700, voxel=0.014)
m.add("GlowMagenta", union(*groups["GP"]), GLOW_P, material="Neon", role="glow", tris=500, voxel=0.014,
      smooth=False)

# broncio con il mento in fuori: bocca a "n" sottile, denti di cristallo che salgono dal labbro inferiore
upper = [(-0.34, HZ - 0.226), (-0.17, HZ - 0.17), (0.0, HZ - 0.153), (0.17, HZ - 0.17), (0.34, HZ - 0.226)]
lower = [(-0.34, HZ - 0.226), (-0.17, HZ - 0.208), (0.0, HZ - 0.197), (0.17, HZ - 0.208), (0.34, HZ - 0.226)]
Y_BACK = max(project(head_u, (x, HEAD_C[1], z), (0, -1, 0))[0][1] for x, z in upper) + 0.08
mouth, _ = grin(head_u, upper, lower, y_back=Y_BACK, d=0.012)
lip = head_u.offset(0.012)
teeth = []
for x, h in ((-0.19, 0.12), (-0.08, 0.08), (0.09, 0.08), (0.2, 0.12)):
    z = float(np.interp(x, [q[0] for q in lower], [q[1] for q in lower]))
    b, _ = project(lip, (x, Y_BACK, z - 0.02), (0, -1, 0))
    teeth.append(orient(crystal(h, 0.037, tip=0.45, sides=4), b + [0, -0.012, 0], (0, -0.25, 1), spin=45))
brows = union(*[surface_tube(head_u, [(sx * 0.41, HZ + 0.4), (sx * 0.29, HZ + 0.39), (sx * 0.13, HZ + 0.31)],
                             [0.04, 0.054, 0.045], y=HEAD_C[1] - 0.6, inset=0.014) for sx in (1, -1)])
m.add("Dark", union(mouth, brows), DARK, role="detail", tris=900, voxel=0.012)
m.add("Teeth", union(*teeth), TOOTH, material="Glass", role="detail", tris=400, voxel=0.008, smooth=False)

# occhio normale e pupilla a fessura dell'occhio luminoso, riflessi piccoli
eye_n = frames[-1].place(ellipsoid(EYE_N))
slit = frames[1].place(ellipsoid((0.028, 0.03, 0.11)), (0.0, -0.073, -0.02))
m.add("Eyes", union(eye_n, slit), EYE, role="eye", tris=600, voxel=0.01)
shines = [frames[-1].place(sphere(0.034), (-0.05, -0.074, 0.0)), frames[-1].place(sphere(0.017), (0.045, -0.07, -0.08)),
          frames[1].place(sphere(0.028), (-0.065, -0.076, 0.0))]
m.add("Shine", union(*shines), WHITE, role="shine", tris=250, voxel=0.007)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
