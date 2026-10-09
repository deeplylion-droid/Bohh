"""Piccolo Grifone (BabyGriffin) - pet Epico volante (grotte di cristallo).

Carattere: il bulletto coraggioso. Sopracciglia a V, occhi d'oro socchiusi e il becco adunco piegato in
un sorrisetto sfrontato. E' fatto di due peluche cuciti insieme: il cappuccio d'aquila bianco e' ricucito
sul corpo da leoncino. Ali piumate animabili (WingR/WingL, perno alla spalla) e coda col ciuffo.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capsule, ellipsoid, project, project_curve, round_cone,  # noqa: E402
                     sphere, tube, union)
from lib.toy import Model  # noqa: E402

FUR = (212, 146, 76)
CREAM = (250, 226, 178)
FEATHER = (252, 250, 242)
BEAK = (255, 182, 36)
WING = (122, 68, 40)
COVERT = (232, 178, 92)
TUFT = (96, 52, 34)
MOUTH = (60, 24, 30)
IRIS = (255, 196, 36)
EYE = (22, 14, 26)
WHITE = (255, 255, 255)
THREAD = (86, 30, 96)


# ============================================================ helper "toy horror" (definiti qui: lib non si tocca)
def normal_at(sdf, p, eps=1e-3):
    """Normale uscente della superficie di sdf vicino al punto p."""
    p = np.asarray(p, dtype=np.float32)
    g = np.array([sdf((p + e)[None])[0] - sdf((p - e)[None])[0] for e in np.eye(3, dtype=np.float32) * eps])
    return g / max(float(np.linalg.norm(g)), 1e-9)


def resample(pts, step):
    """Ricampiona una polilinea a passo costante."""
    pts = np.asarray(pts, dtype=np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    acc = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for s in np.linspace(0.0, acc[-1], max(int(round(acc[-1] / step)), 1) + 1):
        i = int(min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1))
        f = (s - acc[i]) / max(seg[i], 1e-9)
        out.append(pts[i] * (1 - f) + pts[i + 1] * f)
    return np.array(out)


def fast_union(shapes, margin=0.06):
    """Unione di tante forme piccole: ognuna e' valutata solo dentro il proprio box di ingombro."""
    los = [s.lo - margin for s in shapes]
    his = [s.hi + margin for s in shapes]

    def f(p):
        d = np.full(len(p), 1e3, dtype=np.float32)
        for s, lo, hi in zip(shapes, los, his):
            mask = np.all((p >= lo) & (p <= hi), axis=1)
            if mask.any():
                d[mask] = np.minimum(d[mask], s(p[mask]))
        return d

    return SDF(f, np.min(los, axis=0), np.max(his, axis=0))


def stitches(base, pts, step=0.09, length=0.07, r=0.016, cross=True):
    """Cucitura: trattini corti lungo una curva gia' appoggiata sulla superficie (cross: punti a cavallo)."""
    q = resample(pts, step)
    dashes = []
    for i, p in enumerate(q):
        t = q[min(i + 1, len(q) - 1)] - q[max(i - 1, 0)]
        n = normal_at(base, p)
        d = np.cross(n, t) if cross else t
        d = d / np.linalg.norm(d)
        dashes.append(capsule(tuple(p - d * length / 2), tuple(p + d * length / 2), r))
    return fast_union(dashes)


def lid_shape(radii, cut, slope=0.0, grow=0.016, k=0.012):
    """Palpebra pesante (coordinate locali del Frame): calotta dell'occhio ingrandito sopra z = cut + slope*x."""
    a, b, c = radii
    nrm = math.sqrt(1.0 + slope * slope)
    above = SDF(lambda p: (cut + slope * p[:, 0] - p[:, 2]) / nrm, (-1, -1, -1), (1, 1, 1))
    return ellipsoid((a + grow, b + grow, c + grow)).intersect(above, k=k)


def surface_tube(base, pts2d, radii, y=-0.3, inset=0.0, direction=(0, -1, 0)):
    """Tubo (sopracciglio, bocca) disegnato nella vista frontale e appoggiato sulla superficie."""
    return tube(project_curve(base, [(x, y, z) for x, z in pts2d], direction, inset=inset), radii)


def paint(base, region, d=0.022, depth=0.045, k=0.012):
    """Vernice a strato sottile (fra -depth e +d dalla superficie) ritagliata dalla regione: niente grandi
    superfici nascoste, quindi voxel fine a parita' di triangoli. Spessore d + depth >= 2.5 voxel."""
    t = (d + depth) / 2
    return base.offset(d - t).shell(t).intersect(region, k=k)


def flat_y(shape, ky):
    """Schiaccia una forma (centrata in y=0) lungo Y."""
    return shape.warp(lambda p: p * [[1.0, ky, 1.0]])


# ============================================================ modello
m = Model("BabyGriffin", "pet")
PK = 0.01

# corpo da leoncino seduto
torso = ellipsoid((0.62, 0.68, 0.8), (0, 0.14, 0.95))
haunch = union(*[ellipsoid((0.38, 0.52, 0.36), (sx * 0.45, 0.25, 0.38)) for sx in (1, -1)])
legs = []
for sx in (1, -1):
    x = sx * 0.36
    toes = [sphere(0.075, (x + 0.1 * dx, -0.8, 0.08)) for dx in (-1.5, -0.5, 0.5, 1.5)]
    legs.append(union(round_cone((sx * 0.32, -0.3, 1.02), (x, -0.5, 0.2), 0.18, 0.16),
                      ellipsoid((0.22, 0.27, 0.15), (x, -0.6, 0.15)), *toes, k=0.06))
hind = union(*[union(ellipsoid((0.19, 0.29, 0.13), (sx * 0.6, -0.16, 0.13)),
                     *[sphere(0.065, (sx * 0.6 + 0.085 * dx, -0.42, 0.07)) for dx in (-1, 0, 1)], k=0.05)
               for sx in (1, -1)])
neck = capsule((0, -0.02, 1.42), (0, -0.18, 1.92), 0.34)
HEAD_C = (0, -0.24, 2.24)
head = union(ellipsoid((0.65, 0.62, 0.55), HEAD_C),
             *[ellipsoid((0.26, 0.2, 0.13), (sx * 0.27, -0.7, HEAD_C[2] + 0.24)).rot(0, -sx * 12, 0,
                                                                                     pivot=(sx * 0.27, -0.7, 2.48))
               for sx in (1, -1)], k=0.12)
core_nt = union(union(torso, haunch, k=0.25), neck, k=0.2)
core_nt = union(core_nt, head, k=0.22)
core_nt = union(core_nt, *legs, hind, k=0.08)
TAIL = bezier((0, 0.72, 0.42), (0.12, 1.28, 0.28), (0.42, 1.5, 0.95), (0.3, 1.28, 1.42), 12)
tail = tube(TAIL, [0.11 - 0.004 * i for i in range(13)])

# occhi d'oro con palpebre socchiuse e inclinate (sguardo da duro)
frames = {sx: Frame(head, HEAD_C, (0.5 * sx, -1.0, 0.1), sink=0.045) for sx in (1, -1)}
EYE_R = (0.15, 0.085, 0.16)
lids = union(*[frames[sx].place(lid_shape(EYE_R, 0.065, -sx * 0.36)) for sx in (1, -1)])
core = union(core_nt, tail, k=0.06)
m.add("Body", core, FUR, material="Fabric", tris=4200)

# cappuccio d'aquila bianco (vernice sopra la cucitura inclinata) + palpebre + ciuffo di piume
SEAM_C = np.array([0.0, -0.1, 1.5])
SEAM_N = np.array([0.0, -0.42, 1.0]) / np.linalg.norm([0.0, -0.42, 1.0])
above_seam = SDF(lambda p: -((p - SEAM_C) @ SEAM_N), (-2, -2, 0.8), (2, 2, 4))
hood = core_nt.offset(0.022).intersect(above_seam, k=0.008)  # pezzo pieno: l'unica faccia nascosta e' il taglio del collo
crest = union(*[tube(bezier((sx * 0.12, 0.05, 2.62), (sx * 0.16, 0.35, 2.82), (sx * 0.24, 0.6, 2.82),
                             (sx * 0.3, 0.78, 2.66 + 0.08 * (1 - abs(sx))), 8), [0.15 - 0.014 * i for i in range(9)])
                for sx in (-1, 0, 1)], k=0.05)
m.add("Head", union(hood, lids, crest), FEATHER, material="Fabric", role="detail", tris=2600, voxel=0.03)

# pancia color crema
belly = paint(core_nt, ellipsoid((0.42, 0.45, 0.5), (0, -0.48, 0.82)).intersect(
    SDF(lambda p: (p - SEAM_C) @ SEAM_N + 0.06, (-2, -2, -2), (2, 2, 2))), depth=0.06, k=PK)
m.add("Belly", belly, CREAM, material="Fabric", role="detail", tris=700, voxel=0.03)

# becco adunco d'oro: superiore a uncino, inferiore piu' piccolo
painted = head.offset(0.022)
bp, bn = project(head, HEAD_C, (0, -1.0, -0.12))
B = np.array(bp)
upper_beak = tube([tuple(B + [0, 0.14, 0.07]), tuple(B + [0, -0.16, 0.06]), tuple(B + [0, -0.36, -0.04]),
                   tuple(B + [0, -0.4, -0.2]), tuple(B + [0, -0.33, -0.3])],
                  [0.23, 0.18, 0.12, 0.065, 0.022]).warp(lambda p: p * [[1.3, 1.0, 1.0]])
lower_beak = tube([tuple(B + [0, 0.08, -0.12]), tuple(B + [0, -0.16, -0.18]), tuple(B + [0, -0.26, -0.2])],
                  [0.14, 0.09, 0.045]).warp(lambda p: p * [[1.3, 1.0, 1.0]])
m.add("Beak", union(upper_beak, lower_beak, k=0.03), BEAK, role="detail", tris=1000, voxel=0.012)

# fessura del becco che si piega in un sorrisetto (angolo sinistro +X all'insu'), narici
gape = tube([tuple(B + [-0.25, 0.07, -0.08]), tuple(B + [-0.15, -0.07, -0.12]), tuple(B + [0.0, -0.24, -0.15]),
             tuple(B + [0.15, -0.07, -0.12]), tuple(B + [0.26, 0.05, -0.04]), tuple(B + [0.32, 0.08, 0.05])], 0.026)
nostrils = union(*[sphere(0.032, tuple(B + [sx * 0.085, -0.25, 0.06])) for sx in (1, -1)])
m.add("Mouth", union(gape, nostrils), MOUTH, role="detail", tris=500, voxel=0.01)

# sopracciglia a V e ciuffo della coda (marrone scuro)
brows = union(*[surface_tube(head, [(sx * 0.48, HEAD_C[2] + 0.36), (sx * 0.33, HEAD_C[2] + 0.33),
                                    (sx * 0.13, HEAD_C[2] + 0.2)], [0.046, 0.06, 0.05], y=HEAD_C[1] - 0.6,
                             inset=0.0) for sx in (1, -1)])
tip = np.array(TAIL[-1])
tuft = union(*[ellipsoid((0.13, 0.13, 0.17)).rot(a * 25, 0, a * 40).translate(tuple(tip + [0.04 * a, -0.03 * a, 0.08]))
               for a in (-1, 0, 1)], sphere(0.14, tuple(tip)), k=0.05)
m.add("Tuft", union(brows, tuft), TUFT, material="Fabric", role="detail", tris=800, voxel=0.014)

# occhi: iride d'oro, pupilla, riflesso piccolo
irises, pupils, shines = [], [], []
for sx, f in frames.items():
    irises.append(f.place(ellipsoid(EYE_R)))
    pupils.append(f.place(ellipsoid((0.066, 0.04, 0.072)), (0.0, -0.068, -0.04)))
    shines.append(f.place(sphere(0.025), (-0.035, -0.094, -0.01)))
m.add("Iris", union(*irises), IRIS, role="eye", tris=400, voxel=0.012)
m.add("Pupils", union(*pupils), EYE, role="eye", tris=300, voxel=0.009)
m.add("Shine", union(*shines), WHITE, role="shine", tris=150, voxel=0.007)

# cucitura viola dove il cappuccio e' ricucito sul corpo
seam_pts = []
for a in np.linspace(0, 2 * math.pi, 49):
    d = np.array([math.cos(a), math.sin(a), 0.0])
    d[2] = -(d[0] * SEAM_N[0] + d[1] * SEAM_N[1]) / SEAM_N[2]
    p, _ = project(core_nt.offset(0.022), SEAM_C + [0, -0.05, 0.05], d)
    seam_pts.append(tuple(p))
m.add("Stitches", stitches(core_nt.offset(0.022), seam_pts, step=0.1, length=0.11, r=0.018), THREAD, role="detail",
      tris=900, voxel=0.013)


# ali piumate (modellate nel piano XZ: x verso l'esterno, z in alto), animabili
def feather(base, tip, r0, r1, thick):
    return flat_y(round_cone(base, tip, r0, r1), r0 / thick)


EDGE = bezier((0.0, 0.0, 0.0), (0.25, 0.0, 0.3), (0.6, 0.0, 0.44), (0.92, 0.0, 0.34), 30)


def edge_at(t):
    return np.array(EDGE[int(round(t * 30))])


prim = []  # remiganti appese al bordo d'attacco: corte e verso il basso vicino al corpo, lunghe e aperte in punta
for i in range(9):
    t = 0.12 + 0.88 * i / 8
    a = math.radians(-88 + 100 * t)
    ln = 0.36 + 0.42 * t
    base = edge_at(t)
    prim.append(feather(tuple(base), tuple(base + ln * np.array([math.cos(a), 0.0, math.sin(a)])), 0.11, 0.08, 0.036))
cov = [flat_y(tube(EDGE[::5], [0.15, 0.15, 0.14, 0.12, 0.1, 0.08, 0.065]), 0.15 / 0.06)]
for i in range(6):
    t = 0.12 + 0.7 * i / 5
    a = math.radians(-85 + 70 * t)
    base = edge_at(t)
    cov.append(feather(tuple(base), tuple(base + 0.27 * np.array([math.cos(a), 0.0, math.sin(a)])), 0.11, 0.095,
                       0.046))
SHOULDER = (0.4, 0.28, 1.5)


def place_wing(shape, sx):
    s = shape.rot(0, 0, 32).rot(0, -18, 0).translate(SHOULDER)
    return s if sx > 0 else s.mirrored()


for sx, nm in ((1, "WingR"), (-1, "WingL")):
    piv = (sx * SHOULDER[0], SHOULDER[1], SHOULDER[2])
    m.add(nm, place_wing(union(*prim, k=0.02), sx), WING, role="detail", tris=1300, voxel=0.016, group=nm, pivot=piv)
    m.add(nm + "Covert", place_wing(union(*cov, k=0.03).translate((0, -0.03, 0)), sx), COVERT, role="detail", tris=800,
          voxel=0.016, group=nm, pivot=piv)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
