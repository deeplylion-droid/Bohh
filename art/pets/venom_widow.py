"""Vedova Velenosa (VenomWidow) - pet ULTRA, il pezzo forte del gioco.

Una vedova nera gigantesca, lucida come un giocattolo di vinile e grondante di veleno: addome enorme con una
grande clessidra rossa luminosa, otto occhi verde tossico (i due principali sotto palpebre arrabbiate),
cheliceri con zanne ricurve dalla punta d'osso che sbavano veleno, otto zampe lunghissime a segmenti con le
articolazioni ben leggibili, spine e artigli d'osso. Posa d'attacco: le due paia anteriori alzate e protese in
avanti, le posteriori piantate larghe. Tocco "toy horror": una cucitura sull'addome da cui trapela il veleno e
una toppa cucita.

Tutti gli effetti verdi (gocce, colature, schizzi, pustole, vene, pozza) sono nell'unica parte "Venom" (Neon):
il gioco ci attacca le particelle di gocciolamento e di nebbia tossica.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capsule, ellipsoid, prism, project, round_cone, smin, sphere,  # noqa: E402
                     tube, union)
from lib.toy import Model  # noqa: E402

# ============================================================ colori
BLACK = (18, 14, 26)       # nero lucido (blu-viola scurissimo: il nero puro in gioco e' piatto)
CHITIN = (48, 22, 64)      # viola-nero di articolazioni, cheliceri e filiere
RED = (235, 22, 44)        # clessidra (Neon)
VENOM = (124, 255, 36)     # verde acido (Neon)
EYE_G = (176, 255, 60)     # occhi verde tossico (Neon)
BONE = (242, 230, 200)     # punte di zanne, spine e artigli
SOCKET = (10, 6, 14)
WHITE = (255, 255, 255)
PATCH = (92, 46, 124)

rng = np.random.default_rng(11)


# ============================================================ helper (lib/ non si modifica: definiti qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def fast_union(shapes, k=0.0, base=None, margin=0.06):
    """Unione di tante forme piccole, ognuna valutata solo vicino al proprio ingombro."""
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


def spheres(centers, radii):
    """Tante sfere in un colpo solo (albero KD): articolazioni, pustole, bolle."""
    C = np.asarray(centers, dtype=np.float32)
    R = np.asarray(radii, dtype=np.float32)
    tree = cKDTree(C)
    k = min(4, len(C))

    def f(p):
        d, i = tree.query(p, k=k)
        if k == 1:
            d, i = d[:, None], i[:, None]
        return np.min(d - R[i], axis=1).astype(np.float32)

    return SDF(f, C.min(0) - R.max(), C.max(0) + R.max())


def resample(points, step):
    pts = np.asarray(points, dtype=np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(int(round(cum[-1] / step)), 1)
    out = []
    for s in np.linspace(0.0, cum[-1], n + 1):
        i = int(min(np.searchsorted(cum, s, side="right") - 1, len(seg) - 1))
        t = (s - cum[i]) / max(seg[i], 1e-9)
        out.append(pts[i] * (1 - t) + pts[i + 1] * t)
    return out


def paint(base, region, d=0.022, depth=0.045, k=0.012):
    """Vernice a strato sottile (fra -depth e +d dalla superficie) ritagliata dalla regione."""
    t = (d + depth) / 2
    return base.offset(d - t).shell(t).intersect(region, k=k)


def normal_at(sdf, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float32)
    g = np.array([sdf((p + e)[None, :])[0] - sdf((p - e)[None, :])[0] for e in np.eye(3, dtype=np.float32) * eps])
    return g / max(np.linalg.norm(g), 1e-9)


def to_surface(sdf, p, iters=4):
    p = np.asarray(p, dtype=np.float64)
    for _ in range(iters):
        p = p - normal_at(sdf, p) * float(sdf(p[None, :].astype(np.float32))[0])
    return p


def lid_shape(radii, cut, slope=0.0, grow=0.016, k=0.012):
    """Palpebra (coordinate locali del Frame): calotta dell'occhio ingrandito sopra z = cut + slope*x."""
    a, b, c = radii
    nrm = math.sqrt(1.0 + slope * slope)
    above = SDF(lambda p: (cut + slope * p[:, 0] - p[:, 2]) / nrm, (-1, -1, -1), (1, 1, 1))
    return ellipsoid((a + grow, b + grow, c + grow)).intersect(above, k=k)


def spindle(a, b, ra, rm, rb, at=0.42):
    """Segmento di zampa a fuso (piu' grosso verso l'attaccatura, stretto alle articolazioni)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    mid = a + (b - a) * at
    return union(round_cone(tuple(a), tuple(mid), ra, rm), round_cone(tuple(mid), tuple(b), rm, rb))


def flow(sdf, p0, step=0.03, n=60, min_tan=0.3):
    """Colatura: dal punto p0 scende lungo la superficie seguendo la gravita' finche' la parete e' ripida."""
    p = to_surface(sdf, p0)
    pts = [p.copy()]
    for _ in range(n):
        nrm = normal_at(sdf, p)
        t = np.array([0.0, 0.0, -1.0]) + nrm * nrm[2]
        tl = float(np.linalg.norm(t))
        if tl < min_tan:
            break
        p = to_surface(sdf, p + t / tl * step, iters=3)
        pts.append(p.copy())
    return pts


def drip(sdf, p0, r0=0.024, r1=0.034, drop=0.06, hang=0.12, step=0.03, n=60, min_tan=0.3, sink=0.4):
    """Colatura di veleno che scende sulla superficie e finisce con una goccia appesa."""
    pts = flow(sdf, p0, step, n, min_tan)
    if len(pts) < 2:
        pts = [pts[0], pts[0] + np.array([0, 0, -0.02])]
    nrms = [normal_at(sdf, q) for q in pts]
    m_ = len(pts)
    radii = [r0 + (r1 - r0) * (i / max(m_ - 1, 1)) ** 1.5 for i in range(m_)]
    path = [q + nn * r * (1 - 2 * sink) for q, nn, r in zip(pts, nrms, radii)]
    end = path[-1]
    c = end + np.array([0.0, 0.0, -hang]) + nrms[-1] * 0.01
    shapes = [tube([tuple(q) for q in path], radii),
              round_cone(tuple(end), tuple(c), radii[-1], drop * 0.8), sphere(drop, tuple(c - np.array([0, 0, drop * 0.25])))]
    return union(*shapes, k=0.02)


def hang_drop(top, length, r_top, r_drop):
    """Goccia appesa (filo che si gonfia in una lacrima) sotto il punto top."""
    top = np.asarray(top, float)
    c = top + np.array([0.0, 0.0, -length])
    return union(round_cone(tuple(top), tuple(c + np.array([0, 0, r_drop * 0.6])), r_top, r_drop * 0.75),
                 sphere(r_drop, tuple(c)), k=0.025)


def orient_points(pts2d, frame, lift=0.0):
    return [frame.point((x, -lift, z)) for x, z in pts2d]


# ============================================================ corpo: addome enorme + cefalotorace
m = Model("VenomWidow", "pet")

AB_C = np.array([0.0, 1.2, 1.2])
AB_R = (1.08, 1.26, 1.0)
AB_PITCH = -6.0
EGG = 0.09


def _egg(p):
    """Addome a uovo: piu' pieno dietro, piu' stretto verso il peduncolo."""
    q = p.copy()
    s = 1.0 + EGG * np.clip(p[:, 1] / AB_R[1], -1.0, 1.0)
    q[:, 0] /= s
    q[:, 2] /= s
    return q


abdomen = ellipsoid(AB_R).warp(_egg, pad=0.12).rot(AB_PITCH, 0, 0).translate(AB_C)

# cefalotorace basso e proteso, inclinato verso l'alto davanti (posa d'attacco)
CT_PIV = (0.0, -0.5, 0.94)
CT_PITCH = -18.0
_c, _s = math.cos(math.radians(CT_PITCH)), math.sin(math.radians(CT_PITCH))
_R = np.array([[1, 0, 0], [0, _c, -_s], [0, _s, _c]])


def ct_point(q):
    return _R @ (np.asarray(q, float) - CT_PIV) + CT_PIV


thorax = ellipsoid((0.62, 0.6, 0.34), (0, -0.46, 0.96)).rot(CT_PITCH, 0, 0, pivot=CT_PIV)
HEAD_C0 = np.array([0.0, -1.0, 1.06])
head_raw = union(ellipsoid((0.46, 0.44, 0.36), tuple(HEAD_C0)), ellipsoid((0.33, 0.25, 0.22), (0, -1.14, 1.27)), k=0.16)
head = head_raw.rot(CT_PITCH, 0, 0, pivot=CT_PIV)
HEAD_C = ct_point(HEAD_C0)
ceph = union(thorax, head, k=0.3)
pedicel = capsule((0, -0.06, 0.88), (0, 0.34, 1.0), 0.15)
core = union(ceph, pedicel, k=0.1)
core = union(core, abdomen, k=0.12)

# cheliceri: basi gonfie sotto gli occhi che curvano in avanti e in giu' (neri lucidi, fusi con la testa)
CHEL = {sx: [np.array([sx * 0.15, -1.16, 0.92]), np.array([sx * 0.185, -1.36, 0.74]),
             np.array([sx * 0.15, -1.44, 0.55])] for sx in (1, -1)}
chel = [union(round_cone(tuple(c[0]), tuple(c[1]), 0.165, 0.145), round_cone(tuple(c[1]), tuple(c[2]), 0.145, 0.1), k=0.06)
        for c in CHEL.values()]
core = union(core, *chel, k=0.05)

# ------------------------------------------------------------ occhi: 2 grandi + 6 piccoli raccolti sulla fronte
EYES = [  # (direzione dal centro della testa, raggi, palpebra)
    ((0.25, -1.0, 0.36), (0.13, 0.075, 0.13), True),      # principali (AME)
    ((0.13, -0.6, 1.0), (0.068, 0.048, 0.068), False),    # mediani posteriori
    ((0.52, -0.85, 0.6), (0.06, 0.045, 0.06), False),     # laterali anteriori
    ((0.55, -0.45, 0.95), (0.052, 0.04, 0.052), False),   # laterali posteriori
]
eye_glow, sockets, lids, shines = [], [], [], []
for sx in (1, -1):
    for d, R, has_lid in EYES:
        f = Frame(head, HEAD_C, (sx * d[0], d[1], d[2]), sink=R[1] * 0.45)
        eye_glow.append(f.place(ellipsoid(R)))
        sockets.append(f.place(ellipsoid((R[0] * 1.3, R[1] * 0.85, R[2] * 1.3)), (0, 0.012, 0)))
        if has_lid:
            lids.append(f.place(lid_shape(R, cut=0.015, slope=-sx * 0.95, grow=0.022)))
            shines.append(f.place(sphere(0.026), (-sx * 0.05, -R[1] * 0.9, -0.03)))
            shines.append(f.place(sphere(0.012), (sx * 0.06, -R[1] * 0.8, -0.075)))
        else:
            shines.append(f.place(sphere(R[0] * 0.22), (R[0] * 0.3, -R[1] * 0.85, R[2] * 0.25)))
core = union(core, *lids, k=0.02)
m.add("Body", core, BLACK, reflectance=0.15, tris=9000, voxel=0.018)

# ============================================================ zampe
# giunti (lato destro, x > 0; il sinistro e' speculare): J0 dentro il cefalotorace, J1 fine coxa/trocantere,
# J2 ginocchio (fine femore), J3 fine patella, J4 fine tibia, J5 fine metatarso, J6 punta del tarso
LEGS = {
    # I: alzata in alto e protesa in avanti, artiglio a uncino
    "I": ([(0.3, -0.92, 1.0), (0.5, -1.08, 1.2), (0.98, -1.3, 2.05), (1.12, -1.46, 2.22), (1.5, -2.08, 2.46),
           (1.78, -2.72, 2.12), (1.86, -2.96, 1.8)], 1.0),
    # II: alzata a meta', tesa in avanti e in fuori, punta sospesa
    "II": ([(0.42, -0.72, 0.96), (0.64, -0.84, 1.14), (1.2, -1.04, 2.08), (1.38, -1.14, 2.2), (2.0, -1.6, 1.82),
            (2.5, -2.06, 1.16), (2.62, -2.22, 0.86)], 0.96),
    # III e IV: piantate larghe a terra, ginocchia alte sopra il corpo
    "III": ([(0.46, -0.5, 0.93), (0.68, -0.52, 1.1), (1.22, -0.6, 2.12), (1.4, -0.62, 2.2), (1.98, -0.58, 1.2),
             (2.48, -0.48, 0.32), (2.64, -0.44, 0.016)], 0.9),
    "IV": ([(0.4, -0.28, 0.91), (0.6, -0.18, 1.08), (1.12, 0.3, 2.1), (1.26, 0.44, 2.18), (1.78, 0.98, 1.22),
            (2.22, 1.52, 0.32), (2.36, 1.68, 0.016)], 0.95),
}
SEG_R = [(0.12, 0.12, 0.112), (0.112, 0.13, 0.1), (0.104, 0.116, 0.098), (0.094, 0.104, 0.08),
         (0.078, 0.078, 0.064), (0.062, 0.055, 0.012)]
KNUCKLE_R = [0.134, 0.124, 0.11, 0.09, 0.072]
# spine: (segmento, posizione lungo il segmento, angolo attorno all'asse, lunghezza)
SPIKES = [(1, 0.32, 70, 0.22), (1, 0.6, -60, 0.24), (1, 0.84, 75, 0.19), (3, 0.34, -55, 0.2), (3, 0.7, 50, 0.18),
          (4, 0.5, -20, 0.15)]


def leg_joints(pts, sx):
    J = [np.array(q, float) * np.array([sx, 1.0, 1.0]) for q in pts]
    # direzione laterale: orizzontale, perpendicolare al piano della zampa
    h = J[-1] - J[0]
    h[2] = 0.0
    h = norm(h)
    lat = np.array([-h[1], h[0], 0.0])
    return J, lat


def build_leg(J, lat, sc, spikes=SPIKES):
    """Ritorna (pezzi neri, articolazioni [(centro, raggio)], pezzi d'osso)."""
    black, bone, knuck = [], [], []
    for i in range(6):
        a, b = J[i], J[i + 1]
        ra, rm, rb = [r * sc for r in SEG_R[i]]
        if i < 5:
            black.append(spindle(a, b, ra, rm, rb))
        else:  # tarso: nero fino al 60%, poi artiglio d'osso
            c = a + (b - a) * 0.62
            black.append(round_cone(tuple(a), tuple(c), ra, rm * 0.95))
            bone.append(round_cone(tuple(a + (b - a) * 0.52), tuple(b), rm * 0.92, 0.008))
    for i, r in enumerate(KNUCKLE_R):
        knuck.append((J[i + 1], r * sc))
    for seg, t, psi, L in spikes:
        a, b = J[seg], J[seg + 1]
        s = norm(b - a)
        ll = norm(lat - s * float(lat @ s))
        p1 = np.cross(ll, s)
        if p1[2] < 0:
            p1 = -p1
        d = norm(math.cos(math.radians(psi)) * p1 + math.sin(math.radians(psi)) * ll + 0.6 * s)
        base = a + (b - a) * t
        r_leg = SEG_R[seg][1] * sc
        L = L * sc
        p_in = base + d * r_leg * 0.4
        p_mid = base + d * (r_leg + L * 0.55)
        tip = base + d * (r_leg + L)
        black.append(round_cone(tuple(p_in), tuple(p_mid), 0.046 * sc, 0.026))
        bone.append(round_cone(tuple(base + d * (r_leg + L * 0.45)), tuple(tip), 0.029, 0.005))
    return black, knuck, bone


legs_front, legs_back, knuckles, bone_bits, leg_axes = [], [], [], [], []
for name, (pts, sc) in LEGS.items():
    for sx in (1, -1):
        J, lat = leg_joints(pts, sx)
        blk, kn, bn = build_leg(J, lat, sc)
        (legs_front if name in ("I", "II") else legs_back).extend(blk)
        knuckles.extend(kn)
        bone_bits.extend(bn)
        leg_axes.append((name, sx, J, lat, sc))

# pedipalpi: piccole "braccia" ai lati dei cheliceri, sollevate
PALP = [(0.27, -1.08, 0.9), (0.42, -1.32, 0.8), (0.46, -1.48, 0.98), (0.42, -1.66, 0.9), (0.38, -1.74, 0.74)]
PALP_R = [0.06, 0.056, 0.05, 0.044, 0.03, 0.01]
for sx in (1, -1):
    P = [np.array([sx * x, y, z]) for x, y, z in PALP]
    for i in range(len(P) - 1):
        if i < len(P) - 2:
            legs_front.append(spindle(P[i], P[i + 1], PALP_R[i], PALP_R[i] * 1.1, PALP_R[i + 1]))
        else:
            c = P[i] + (P[i + 1] - P[i]) * 0.55
            legs_front.append(round_cone(tuple(P[i]), tuple(c), PALP_R[i], PALP_R[i] * 0.9))
            bone_bits.append(round_cone(tuple(P[i] + (P[i + 1] - P[i]) * 0.45), tuple(P[i + 1]), PALP_R[i] * 0.85, 0.006))
    for q, r in zip(P[1:-1], (0.068, 0.06, 0.05)):
        knuckles.append((q, r))

m.add("LegsFront", fast_union(legs_front, k=0.012), BLACK, reflectance=0.1, tris=9000, voxel=0.014)
m.add("LegsBack", fast_union(legs_back, k=0.012), BLACK, reflectance=0.1, tris=7500, voxel=0.014)

# ============================================================ zanne (viola-nero con la punta d'osso) e dentini
chel_parts, fang_tips, fang_tip_pts, teeth = [], [], [], []
for sx, c in CHEL.items():
    base = c[2] + np.array([0.0, -0.02, 0.03])
    fang = bezier(tuple(base), (sx * 0.19, -1.6, 0.36), (sx * 0.12, -1.62, 0.2), (sx * 0.03, -1.5, 0.13), 16)
    fr = [0.096 * (1 - i / 16) ** 0.8 + 0.008 for i in range(17)]
    chel_parts.append(tube(fang[:11], fr[:11]))
    chel_parts.append(sphere(0.112, tuple(base + np.array([0, 0, 0.02]))))   # snodo della zanna
    fang_tips.append(tube(fang[9:], fr[9:]))
    fang_tip_pts.append(np.array(fang[-1]))
    # dentini sul bordo interno del chelicero
    for t in (0.35, 0.6, 0.85):
        q = c[1] + (c[2] - c[1]) * t
        p0, nn = project(chel[0 if sx > 0 else 1], q, (-sx * 0.8, -0.6, -0.1))
        teeth.append(round_cone(tuple(p0 - nn * 0.02), tuple(p0 + norm((-sx * 0.7, -0.5, -0.5)) * 0.09), 0.032, 0.005))
chel_parts.append(spheres([q for q, _ in knuckles], [r for _, r in knuckles]))
# filiere in fondo all'addome
SPIN_C = AB_C + np.array([0.0, 1.1, -0.42])
chel_parts += [round_cone(tuple(AB_C + [dx, 0.95, -0.36]), tuple(AB_C + [dx * 1.4, 1.22, -0.5]), 0.07, 0.04)
               for dx in (-0.08, 0.08)]
m.add("Chitin", fast_union(chel_parts, k=0.01), CHITIN, reflectance=0.15, role="detail", tris=5000, voxel=0.014)
m.add("Bone", fast_union(fang_tips + teeth + bone_bits), BONE, role="detail", tris=3000, voxel=0.012)

# ============================================================ clessidra rossa sul dorso dell'addome
HG = Frame(abdomen, AB_C, (0.0, -0.42, 0.9))
W, H, w0 = 0.36, 0.5, 0.075
hg_poly = [(W, H), (-W, H), (-w0 * 1.6, H * 0.3), (-w0, 0.0), (-w0 * 1.6, -H * 0.3), (-W, -H), (W, -H),
           (w0 * 1.6, -H * 0.3), (w0, 0.0), (w0 * 1.6, H * 0.3)]
hg_region = HG.place(prism(hg_poly, -0.6, 0.6).offset(0.03).rot(90, 0, 0))
m.add("Hourglass", paint(abdomen, hg_region, d=0.02, depth=0.05, k=0.006), RED, material="Neon", role="glow",
      tris=1500, voxel=0.012)

# ============================================================ occhi
m.add("EyeGlow", union(*eye_glow), EYE_G, material="Neon", role="glow", tris=1800, voxel=0.01)
m.add("Sockets", union(*sockets), SOCKET, role="eye", tris=1000, voxel=0.01)

# ============================================================ veleno (unica parte "Venom")
venom = []
# gocce appese alle zanne e bava che pende fra le due punte
for tp in fang_tip_pts:
    venom.append(hang_drop(tp + np.array([0, -0.005, 0.01]), 0.13, 0.018, 0.045))
a, b = fang_tip_pts
sag = [a + (b - a) * t + np.array([0.0, -0.01, -0.12 * math.sin(math.pi * t)]) for t in np.linspace(0, 1, 9)]
venom.append(tube([tuple(q) for q in sag], [0.016, 0.017, 0.019, 0.022, 0.024, 0.022, 0.019, 0.017, 0.016]))
venom.append(hang_drop(sag[4], 0.09, 0.022, 0.04))
# pozza a terra sotto le zanne con schizzi
pz = (0.0, -1.46, 0.0)
venom.append(union(ellipsoid((0.3, 0.22, 0.03), pz), ellipsoid((0.16, 0.14, 0.03), (0.22, -1.62, 0.0)),
                   ellipsoid((0.14, 0.12, 0.03), (-0.2, -1.36, 0.0)), k=0.06))
for ang, dist, r in ((20, 0.42, 0.03), (75, 0.36, 0.025), (140, 0.4, 0.03), (200, 0.45, 0.022), (260, 0.38, 0.028),
                     (320, 0.43, 0.024)):
    venom.append(ellipsoid((r * 1.4, r * 1.4, r * 0.6), (pz[0] + dist * math.cos(math.radians(ang)),
                                                        pz[1] + dist * 0.8 * math.sin(math.radians(ang)), 0.0)))
# colature che scendono lungo i fianchi dell'addome e finiscono in gocce appese
for d in ((0.62, -0.1, 0.62), (0.85, 0.35, 0.4), (-0.7, 0.05, 0.55), (-0.6, 0.55, 0.62), (0.3, 0.85, 0.55),
          (-0.25, 0.9, 0.45)):
    p0, _ = project(abdomen, AB_C, d)
    venom.append(drip(abdomen, p0, r0=0.022, r1=0.034, drop=0.055, hang=0.1))
# pustole e bolle tossiche a grappoli
pc, pr = [], []
for d, n in (((0.9, 0.3, 0.1), 6), ((-0.85, 0.5, 0.2), 5), ((0.4, 0.95, 0.35), 5), ((-0.45, -0.5, 0.75), 4)):
    c0, _ = project(abdomen, AB_C, d)
    for i in range(n):
        q = c0 + rng.normal(size=3) * 0.13
        p, nn = project(abdomen, AB_C, q - AB_C)
        r = float(rng.uniform(0.035, 0.09)) if i else 0.1
        pc.append(p - nn * r * 0.35)
        pr.append(r)
venom.append(spheres(pc, pr))
# vene luminose sui femori
for name, sx, J, lat, sc in leg_axes:
    a, b = J[1], J[2]
    s = norm(b - a)
    up = norm(np.cross(norm(lat - s * float(lat @ s)), s))
    if up[2] < 0:
        up = -up
    r = SEG_R[1][1] * sc
    pts = [a + (b - a) * t + up * (r * 0.92) + norm(lat) * 0.02 * math.sin(t * 9) for t in np.linspace(0.12, 0.9, 10)]
    venom.append(tube([tuple(q) for q in pts], 0.022))
m.add("Venom", fast_union(venom), VENOM, material="Neon", role="glow", tris=12000, voxel=0.012)

m.add("Shine", union(*shines), WHITE, role="shine", tris=400, voxel=0.008)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
