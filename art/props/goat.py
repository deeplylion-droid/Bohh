"""Capra di montagna (Goat) - ostacolo che carica i giocatori sui sentieri.

Peluche bianco con un tocco "toy horror": occhi gialli da capra con la pupilla orizzontale sotto
palpebre pesanti, sopracciglia spesse e inclinate, ghigno largo con dentini aguzzi sotto il naso
rosa, corna grigio-brune ad anelli, barbetta, zoccoli neri, gobba e ciuffi di pelo da capra di
montagna, una toppa blu notte cucita sul fianco e una cucitura sul petto. Testa bassa e
inclinata, pronta a caricare.
Dimensioni reali: lunga ~3.7, alta ~4.4 con le corna; piedi su z = 0, guarda verso -Y.

Uso: python props/goat.py
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.sdf import (Frame, bezier, box, capped_cone, capsule, ellipsoid, project, rot_matrix, round_cone,  # noqa: E402
                     sphere, torus, tube, union)
from propkit import (FineModel, eyelid, face_prism, fast_union, grin_regions, paint, patch_outline,  # noqa: E402
                     patch_region, run, stitches)

FUR = (244, 242, 238)
BEARD = (206, 204, 212)
PINK = (255, 146, 168)
HORN = (150, 126, 106)
HOOF = (40, 34, 42)
EYE_GOLD = (255, 194, 52)
PUPIL = (22, 14, 26)
MOUTH = (52, 14, 44)
THREAD = (82, 44, 104)
PATCH = (58, 68, 132)
WHITE = (255, 255, 255)

HEAD_C = np.array((0.0, -1.12, 3.08))
TIP_C = np.array((0.0, -1.97, 2.66))  # punta del muso
LEGS = [(sx * 0.5, y) for sx in (1, -1) for y in (-0.6, 0.84)]
# la testa e' modellata dritta e poi abbassata, inclinata e girata un po' verso destra (posa da carica)
HEAD_POSE = dict(rx=8, ry=7, rz=7, pivot=(0, -0.75, 2.5))


def H(shape):
    """Porta una forma della testa nella posa finale."""
    return shape.rot(**HEAD_POSE)


def ring(c, d, R, r):
    """Anello (toro di raggio R, sezione r) centrato in c con l'asse lungo d."""
    d = np.asarray(d, dtype=np.float64)
    d = d / np.linalg.norm(d)
    z = np.array([0.0, 0.0, 1.0])
    ax = np.cross(z, d)
    s = float(np.linalg.norm(ax))
    t = torus(R, r)
    if s > 1e-6:
        t = t.rotate(rot_matrix(ax, math.degrees(math.atan2(s, float(z @ d)))))
    return t.translate(c)


def goat() -> FineModel:
    m = FineModel("Goat", "prop", voxel=0.03)

    # ------------------------------------------------------------------ testa (coordinate "dritte")
    cranium = ellipsoid((0.75, 0.68, 0.7), tuple(HEAD_C))
    snout = round_cone((0, -1.45, 2.96), tuple(TIP_C), 0.5, 0.37)
    head_full = union(cranium, snout, k=0.25)
    ear_c = [(sx * 0.86, -1.01, 3.16) for sx in (1, -1)]
    ears = [ellipsoid((0.37, 0.13, 0.16)).rot(0, sx * 22, sx * 18).translate(c) for sx, c in zip((1, -1), ear_c)]
    head_skin = union(head_full, *ears, k=0.06)  # superficie per le "vernici" del muso

    # ------------------------------------------------------------------ corpo
    neck = capsule((0, -0.6, 2.2), (0, -0.95, 2.76), 0.45)
    body = ellipsoid((0.9, 1.05, 0.8), (0, 0.1, 2.02))
    chest = ellipsoid((0.76, 0.55, 0.7), (0, -0.56, 2.02))
    hump = ellipsoid((0.62, 0.62, 0.42), (0, -0.3, 2.62))  # gobba sulle spalle da capra di montagna
    torso = union(body, chest, neck, hump, k=0.3)
    # gorgiera di pelo arruffato sotto il collo (sagoma a ciuffi)
    ruff = [ellipsoid((0.2, 0.17, 0.26), (x, -0.98 + abs(x) * 0.55, z)) for x, z in
            ((0.0, 1.78), (0.24, 1.86), (-0.24, 1.86), (0.44, 2.02), (-0.44, 2.02), (0.12, 1.66), (-0.12, 1.66))]
    torso = union(torso, union(*ruff, k=0.04), k=0.08)
    legs = []
    for x, y in LEGS:
        if y > 0:  # zampe posteriori con coscia piena
            leg = union(round_cone((x * 0.9, y, 1.9), (x, y + 0.02, 0.32), 0.38, 0.27),
                        ellipsoid((0.38, 0.5, 0.56), (x * 0.84, y - 0.08, 1.78)), k=0.1)
        else:
            leg = round_cone((x * 0.92, y, 1.82), (x, y - 0.03, 0.32), 0.36, 0.27)
        # ciuffi di pelo alle ginocchia
        tufts = [sphere(0.13, (x + 0.28 * math.cos(a), y + 0.28 * math.sin(a), 1.02 - 0.05 * math.sin(3 * a)))
                 for a in np.linspace(0, 2 * math.pi, 7)[:-1]]
        legs.append(union(leg, union(*tufts, k=0.03), k=0.06))
    tail = round_cone((0, 1.02, 2.34), (0, 1.26, 2.74), 0.18, 0.07)
    core = union(union(torso, H(head_full), k=0.3), *legs, k=0.14)
    core = union(core, tail, *[H(e) for e in ears], k=0.06)
    m.add("Body", core, FUR, material="Fabric", tris=2100)

    # ------------------------------------------------------------------ occhi da capra con palpebre pesanti
    eye_r = (0.2, 0.11, 0.22)
    frames = [Frame(head_full, tuple(HEAD_C), (0.5 * sx, -1.0, 0.3), sink=0.06) for sx in (1, -1)]
    eyeball = ellipsoid(eye_r)
    m.add("Eyes", H(union(*[f.place(eyeball) for f in frames])), EYE_GOLD, role="eye", tris=280, voxel=0.012)
    # pupilla orizzontale (rettangolo arrotondato) dipinta sul davanti dell'occhio
    bar = box((0.11, 0.2, 0.042), (0, -0.1, -0.015), round=0.04)
    pupil = eyeball.offset(0.012).intersect(bar).subtract(eyeball.offset(-0.03))
    m.add("Pupils", H(union(*[f.place(pupil) for f in frames])), PUPIL, role="eye", tris=160, voxel=0.008)
    shines = [f.place(sphere(0.038), (-0.07, -0.1, 0.06)) for f in frames]
    shines += [f.place(sphere(0.019), (0.08, -0.095, -0.08)) for f in frames]
    m.add("Shine", H(union(*shines)), WHITE, role="shine", tris=100, voxel=0.007)
    # palpebre piu' basse verso il centro del muso (sguardo torvo). Nota: nel Frame la x locale e' -x del mondo.
    lids = union(eyelid(frames[0], eye_r, 0.085, -0.34), eyelid(frames[1], eye_r, 0.1, 0.26))
    m.add("Lids", H(lids), FUR, material="Fabric", role="skin", tris=260, voxel=0.012)

    # naso rosa a triangolo sulla punta del muso e interno delle orecchie
    tip_front, _ = project(head_full, tuple(TIP_C), (0, -1, 0.35))
    nz = tip_front[2]
    nose_region = face_prism([(-0.25, nz + 0.12), (0.25, nz + 0.12), (0.0, nz - 0.13)], -2.8, -1.8, round=0.07)
    inner_ears = [ellipsoid((0.27, 0.2, 0.095), (sx * 0.04, -0.12, 0.02)).rot(0, sx * 22, sx * 18).translate(c)
                  for sx, c in zip((1, -1), ear_c)]
    pink = union(paint(head_skin, nose_region, t=0.02, depth=0.06), paint(head_skin, union(*inner_ears), t=0.02, depth=0.06))
    m.add("Snout", H(pink), PINK, role="detail", tris=300, voxel=0.013)

    # ghigno largo e sbilenco (avvolge il muso) con dentini aguzzi, narici a virgola
    mouth, up, lo = grin_regions(0.0, nz - 0.2, 0.4, 0.17, 0.02, 0.14, 9, 4, 0.062, -2.8, -1.6, asym=0.06)
    nostrils = []
    for sx in (1, -1):
        c = (sx * 0.11, -2.3, nz + 0.07)
        nostrils.append(ellipsoid((0.05, 0.4, 0.026), c).rot(0, sx * 30, 0, pivot=c))
    m.add("Mouth", H(union(paint(head_skin, mouth, t=0.034, depth=0.05), paint(head_skin, union(*nostrils), t=0.034,
                                                                            depth=0.05))),
          MOUTH, role="eye", tris=320, voxel=0.009)
    teeth = union(*[t for t in (up, lo) if t is not None]).intersect(mouth.offset(0.003))
    m.add("Teeth", H(paint(head_skin, teeth, t=0.048, depth=0.02)), WHITE, role="shine", tris=320, voxel=0.006)

    # sopracciglia spesse (una alzata, una aggrottata), cucitura sul petto, toppa cucita sul fianco
    brows = []
    for pts in (((0.1, 0.36), (0.3, 0.55), (0.52, 0.44)), ((-0.08, 0.32), (-0.3, 0.42), (-0.52, 0.44))):
        ctrl = [(x, -0.75, z) for x, z in pts]
        path = [project(head_full, tuple(HEAD_C), d) for d in bezier(ctrl[0], ctrl[1], ctrl[1], ctrl[2], 8)]
        brows.append(tube([p + n * 0.012 for p, n in path], list(np.linspace(0.068, 0.042, len(path)))))
    chest_path = [project(core, (0, -0.4, z), (0, -1, 0.15)) for z in np.linspace(2.5, 1.5, 10)]
    seam = stitches(chest_path, 0.12, 0.06, 0.018, line_r=0.012, inset=-0.012)
    patch_c, patch_n = project(core, (0.2, 0.55, 2.02), (1, 0.15, 0.35))
    patch = dict(center=patch_c, normal=patch_n, rx=0.36, ry=0.3, angle=14)
    m.add("Patch", paint(core, patch_region(**patch), t=0.025, depth=0.06), PATCH, material="Fabric", role="detail",
          tris=200, voxel=0.014)
    outline = patch_outline(core.offset(0.025), **{**patch, "rx": 0.28, "ry": 0.22})
    patch_seam = stitches(outline, 0.1, 0.045, 0.016, inset=-0.014, cross=True)
    m.add("Thread", fast_union(H(union(*brows)), seam, patch_seam), THREAD, role="detail", tris=650, voxel=0.01)

    # ------------------------------------------------------------------ corna ad anelli, barbetta, zoccoli
    horns = []
    n = 26
    for sx in (1, -1):
        pts = bezier((sx * 0.3, -0.97, 3.55), (sx * 0.42, -1.03, 4.14), (sx * 0.82, -0.42, 4.36), (sx * 1.0, 0.01, 3.9), n)
        radii = [0.23 - 0.16 * i / n for i in range(n + 1)]
        rings = [ring(pts[i], np.subtract(pts[i + 1], pts[i - 1]), radii[i] - 0.012, 0.034) for i in range(5, n - 2, 3)]
        horns.append(union(tube(pts, radii), *rings, k=0.02))
    m.add("Horns", H(union(*horns)), HORN, role="detail", tris=760, voxel=0.013)

    chin, _ = project(head_full, tuple(TIP_C + (0, 0.25, 0.05)), (0, -0.25, -1))
    beard = union(tube(bezier(tuple(chin + (0, 0.06, 0.06)), tuple(chin + (0, -0.03, -0.14)), tuple(chin + (0, -0.06, -0.3)),
                              tuple(chin + (0, 0.0, -0.5)), 7), [0.15, 0.15, 0.14, 0.12, 0.095, 0.065, 0.04, 0.02]),
                  tube(bezier(tuple(chin + (0.07, 0.04, 0.0)), tuple(chin + (0.1, -0.02, -0.16)), tuple(chin + (0.12, 0.0, -0.28)),
                              tuple(chin + (0.15, 0.04, -0.36)), 5), [0.08, 0.075, 0.06, 0.04, 0.028, 0.016]), k=0.03)
    m.add("Beard", H(beard), BEARD, material="Fabric", role="detail", tris=200, voxel=0.013)

    hooves = []
    for x, y in LEGS:
        yy = y - 0.03 if y < 0 else y + 0.02
        h = capped_cone((x, yy, 0.0), (x, yy, 0.4), 0.33, 0.29, round=0.08)
        cleft = box((0.026, 0.12, 0.12), (x, yy - 0.36, 0.03))
        hooves.append(h.subtract(cleft, k=0.02))
    m.add("Hooves", union(*hooves), HOOF, role="detail", tris=340, voxel=0.016)
    return m


CATALOG = {"Goat": goat}

if __name__ == "__main__":
    run(CATALOG)
