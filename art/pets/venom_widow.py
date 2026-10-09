"""Vedova Velenosa (VenomWidow) - pet ULTRA, il pezzo forte del gioco.

Una vedova nera gigantesca, lucida come un giocattolo di vinile e grondante di veleno: addome enorme con una
grande clessidra rossa luminosa, otto occhi verde tossico (i due principali sotto palpebre arrabbiate),
cheliceri con zanne ricurve dalla punta d'osso che sbavano veleno, otto zampe lunghissime a segmenti con le
articolazioni ben leggibili, spine e artigli d'osso. Posa d'attacco: le due paia anteriori alzate e protese in
avanti, le posteriori piantate larghe con le ginocchia alte sopra il corpo. Tocco "toy horror": una cucitura
sull'addome da cui trapela il veleno (vene luminose che si allargano dalla ferita) e una toppa cucita.

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
from lib.sdf import (SDF, Frame, bezier, box, capsule, ellipsoid, prism, project, round_cone, smin, sphere,  # noqa: E402
                     tube, union)
from lib.toy import Model  # noqa: E402

# ============================================================ colori
BLACK = (18, 14, 26)       # nero lucido (blu-viola scurissimo: il nero puro in gioco e' piatto)
CHITIN = (48, 22, 64)      # viola-nero di articolazioni, zanne e filiere
RED = (235, 22, 44)        # clessidra (Neon)
VENOM = (124, 255, 36)     # verde acido (Neon)
EYE_G = (150, 255, 46)     # occhi verde tossico (Neon)
BONE = (242, 230, 200)     # punte di zanne, spine e artigli, filo delle cuciture
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


def below_line(cut, slope=0.0):
    """Semispazio sotto la retta z = cut + slope*x (coordinate locali del Frame): taglia il bordo alto degli occhi."""
    nrm = math.sqrt(1.0 + slope * slope)
    return SDF(lambda p: (p[:, 2] - cut - slope * p[:, 0]) / nrm, (-1, -1, -1), (1, 1, 1))


def spindle(a, b, ra, rm, rb, at=0.42):
    """Segmento di zampa a fuso (piu' grosso verso l'attaccatura, stretto alle articolazioni)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    mid = a + (b - a) * at
    return union(round_cone(tuple(a), tuple(mid), ra, rm), round_cone(tuple(mid), tuple(b), rm, rb))


def spindle_r(t, ra, rm, rb, at=0.42):
    return ra + (rm - ra) * t / at if t < at else rm + (rb - rm) * (t - at) / (1 - at)


def flow(sdf, p0, step=0.03, n=70, min_tan=0.3, meander=0.45):
    """Colatura: dal punto p0 scende lungo la superficie seguendo la gravita' finche' la parete e' ripida."""
    p = to_surface(sdf, p0)
    pts = [p.copy()]
    ph = float(rng.uniform(0, 6.3))
    for i in range(n):
        nrm = normal_at(sdf, p)
        t = np.array([0.0, 0.0, -1.0]) + nrm * nrm[2]
        tl = float(np.linalg.norm(t))
        if tl < min_tan:
            break
        side = np.cross(nrm, t / tl)
        p = to_surface(sdf, p + (t / tl + side * meander * math.sin(i * 0.55 + ph)) * step, iters=3)
        pts.append(p.copy())
    return pts


def drip(sdf, p0, r0=0.026, r1=0.04, drop=0.065, hang=0.13, sink=0.4, **kw):
    """Colatura di veleno che scende sulla superficie, si gonfia e finisce con una goccia appesa."""
    pts = flow(sdf, p0, **kw)
    if len(pts) < 3:
        pts = [pts[0], pts[0] + np.array([0, 0, -0.03]), pts[0] + np.array([0, 0, -0.06])]
    nrms = [normal_at(sdf, q) for q in pts]
    n = len(pts)
    ph = float(rng.uniform(0, 6.3))
    radii = [(r0 + (r1 - r0) * (i / (n - 1)) ** 1.5) * (1 + 0.28 * max(0.0, math.sin(i * 0.8 + ph))) for i in range(n)]
    path = [q - nn * r * sink for q, nn, r in zip(pts, nrms, radii)]
    end = pts[-1] + nrms[-1] * radii[-1] * 0.3
    c = end + np.array([0.0, 0.0, -hang])
    return [tube([tuple(q) for q in path], radii),
            union(round_cone(tuple(end), tuple(c + np.array([0, 0, drop * 0.5])), radii[-1], drop * 0.7),
                  sphere(drop, tuple(c)), k=0.03)]


def hang_drop(top, length, r_top, r_drop):
    """Goccia appesa (filo che si gonfia in una lacrima) sotto il punto top."""
    top = np.asarray(top, float)
    c = top + np.array([0.0, 0.0, -length])
    return union(round_cone(tuple(top), tuple(c + np.array([0, 0, r_drop * 0.6])), r_top, r_drop * 0.7),
                 sphere(r_drop, tuple(c)), k=0.025)


def walk(sdf, p0, heading, length, step=0.04, wiggle=0.09, bend=0.06):
    """Cammina sulla superficie da p0 verso heading con svolte casuali (percorso di una vena)."""
    p = to_surface(sdf, p0)
    h = np.asarray(heading, float)
    pts = [p.copy()]
    for _ in range(max(int(length / step), 2)):
        nrm = normal_at(sdf, p)
        h = norm(h - nrm * float(h @ nrm))
        ang = rng.normal() * wiggle + bend
        h = norm(h * math.cos(ang) + np.cross(nrm, h) * math.sin(ang))
        p = to_surface(sdf, p + h * step, iters=3)
        pts.append(p.copy())
    return pts


def vein(sdf, p0, heading, length, r0, r1=0.013, branches=2, depth=1, sink=0.3):
    """Vena luminosa ramificata che serpeggia sulla superficie (lista di tubi)."""
    pts = walk(sdf, p0, heading, length, bend=float(rng.uniform(-0.07, 0.07)))
    n = len(pts)
    radii = [r0 + (r1 - r0) * (i / (n - 1)) ** 0.7 for i in range(n)]
    nrms = [normal_at(sdf, q) for q in pts]
    out = [tube([tuple(q - nn * r * sink) for q, nn, r in zip(pts, nrms, radii)], radii)]
    if depth > 0:
        for j in range(branches):
            i = int(rng.integers(max(n // 4, 1), max(n * 3 // 4, n // 4 + 2)))
            i = min(i, n - 2)
            t = norm(np.subtract(pts[i + 1], pts[i - 1]))
            side = np.cross(nrms[i], t) * (1 if j % 2 == 0 else -1)
            out += vein(sdf, pts[i], t + side * 1.3, length * 0.42, radii[i] * 0.85, r1, branches=1, depth=depth - 1,
                        sink=sink)
    return out


def x_stitch(sdf, c, tangent, size=0.085, r=0.02, lift=0.03):
    """Punto a X (filo d'osso) a cavallo di una cucitura."""
    nrm = normal_at(sdf, c)
    t = norm(tangent - nrm * float(tangent @ nrm))
    s = np.cross(nrm, t)
    out = []
    for e in (norm(s + 0.8 * t), norm(s - 0.8 * t)):
        a = to_surface(sdf, c - e * size) + nrm * 0.004
        b = to_surface(sdf, c + e * size) + nrm * 0.004
        out.append(tube([tuple(a), tuple(c + nrm * lift), tuple(b)], r))
    return out


def dash_stitches(sdf, pts, n, dash, r, lift, closed=True):
    """Trattini di cucitura (perpendicolari al bordo) lungo una polilinea sulla superficie."""
    pts = np.asarray(pts, dtype=np.float64)
    if closed:
        pts = np.vstack([pts, pts[:1]])
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for t in np.linspace(0.0, s[-1], n, endpoint=not closed):
        i = min(np.searchsorted(s, t, side="right") - 1, len(seg) - 1)
        w = (t - s[i]) / max(seg[i], 1e-9)
        p = pts[i] * (1 - w) + pts[i + 1] * w
        tan = (pts[i + 1] - pts[i]) / max(seg[i], 1e-9)
        nrm = normal_at(sdf, p)
        d = norm(np.cross(nrm, tan))
        c = p + nrm * lift
        out.append(capsule(tuple(c - d * dash * 0.5), tuple(c + d * dash * 0.5), r))
    return out


# ============================================================ corpo: addome enorme + cefalotorace
m = Model("VenomWidow", "pet")

AB_C = np.array([0.0, 1.5, 1.3])
AB_R = (1.2, 1.36, 1.1)
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

# cefalotorace impennato: la testa si alza e guarda avanti (posa di minaccia)
CT_PIV = (0.0, -0.1, 0.9)
CT_PITCH = -32.0
_c, _s = math.cos(math.radians(CT_PITCH)), math.sin(math.radians(CT_PITCH))
_R = np.array([[1, 0, 0], [0, _c, -_s], [0, _s, _c]])


def ct_point(q):
    return _R @ (np.asarray(q, float) - CT_PIV) + CT_PIV


thorax = ellipsoid((0.62, 0.6, 0.34), (0, -0.5, 0.94)).rot(CT_PITCH, 0, 0, pivot=CT_PIV)
HEAD_C0 = np.array([0.0, -1.02, 1.04])
head_raw = union(ellipsoid((0.5, 0.47, 0.39), tuple(HEAD_C0)), ellipsoid((0.36, 0.27, 0.24), (0, -1.18, 1.27)), k=0.16)
head = head_raw.rot(CT_PITCH, 0, 0, pivot=CT_PIV)
HEAD_C = ct_point(HEAD_C0)
ceph = union(thorax, head, k=0.3)
pedicel = capsule((0, -0.02, 0.86), (0, 0.42, 0.98), 0.15)
body = union(abdomen, pedicel, k=0.12)

# cheliceri: basi corte e gonfie sotto gli occhi che puntano in giu' (nere lucide, fuse con la testa)
CHEL = {sx: [np.array([sx * 0.15, -1.1, 1.42]), np.array([sx * 0.18, -1.27, 1.17])] for sx in (1, -1)}
chel = {sx: union(sphere(0.17, tuple(c[0])), round_cone(tuple(c[0]), tuple(c[1]), 0.165, 0.135), k=0.05)
        for sx, c in CHEL.items()}
ceph = union(ceph, *chel.values(), k=0.05)

# cucitura sul fianco destro dell'addome: il solco (qui) e il veleno che ne trapela (in "Venom")
SEAM_F = Frame(abdomen, AB_C, (1.0, 0.1, 0.32))
SEAM = [to_surface(abdomen, SEAM_F.point((x * 1.1, 0.0, z * 1.1))) for x, z in
        ((0.16, 0.58), (0.06, 0.42), (0.1, 0.24), (0.0, 0.06), (0.05, -0.12), (-0.04, -0.3), (0.0, -0.48))]
SEAM = [to_surface(abdomen, q) for q in resample(SEAM, 0.05)]
body = body.subtract(tube([tuple(q) for q in SEAM], 0.056), k=0.016)
m.add("Body", body, BLACK, reflectance=0.2, tris=11000, voxel=0.027)

# ------------------------------------------------------------ occhi: 2 grandi + 6 piccoli raccolti sulla fronte
EYES = [  # (direzione dal centro della testa, raggi, principale?)
    ((0.31, -1.0, 0.1), (0.15, 0.095, 0.128), True),      # principali (AME): a mandorla, inclinati
    ((0.15, -0.85, 0.62), (0.06, 0.045, 0.06), False),    # mediani posteriori
    ((0.62, -0.8, 0.12), (0.064, 0.048, 0.064), False),   # laterali anteriori
    ((0.46, -0.7, 0.57), (0.05, 0.04, 0.05), False),      # laterali posteriori
]
eye_glow, sockets, shines = [], [], []
for sx in (1, -1):
    for d, R, main in EYES:
        f = Frame(head, HEAD_C, (sx * d[0], d[1], d[2]), sink=R[1] * (0.25 if main else 0.4))
        if main:
            # occhio a mandorla con l'angolo interno in giu' e il bordo alto tagliato dritto: sguardo cattivo
            # (nel Frame l'asse X locale punta verso il centro per l'occhio destro e verso l'esterno per il sinistro)
            tilt, slope, cut = sx * 14.0, -sx * 0.6, 0.045
            eye_glow.append(f.place(ellipsoid(R).rot(0, tilt, 0).intersect(below_line(cut, slope), k=0.01)))
            sockets.append(f.place(ellipsoid((R[0] * 1.2, R[1] * 0.8, R[2] * 1.32)).rot(0, tilt, 0)
                                   .intersect(below_line(cut + 0.03, slope), k=0.01), (0, 0.014, 0)))
            shines.append(f.place(sphere(0.03), (0.03, -R[1] * 0.9, -0.012)))
            shines.append(f.place(sphere(0.015), (-0.06, -R[1] * 0.76, -0.06)))
        else:
            eye_glow.append(f.place(ellipsoid(R)))
            sockets.append(f.place(ellipsoid((R[0] * 1.3, R[1] * 0.85, R[2] * 1.3)), (0, 0.012, 0)))
            shines.append(f.place(sphere(R[0] * 0.22), (R[0] * 0.3, -R[1] * 0.85, R[2] * 0.25)))
m.add("Head", ceph, BLACK, reflectance=0.2, tris=5000, voxel=0.021)

# ============================================================ zampe
# giunti (lato destro, x > 0; il sinistro e' speculare): J0 dentro il cefalotorace, J1 fine coxa/trocantere,
# J2 ginocchio (fine femore), J3 fine patella, J4 fine tibia, J5 fine metatarso, J6 punta del tarso
LEGS = {
    # I: alzata in alto sopra la testa e protesa in avanti, artiglio a uncino
    "I": ([(0.3, -0.85, 1.42), (0.52, -1.0, 1.6), (1.02, -1.18, 2.22), (1.18, -1.35, 2.34), (1.58, -1.95, 2.42),
           (1.86, -2.6, 2.1), (1.92, -2.84, 1.8)], 1.0),
    # II: alzata, tesa in avanti e in fuori, punta sospesa
    "II": ([(0.42, -0.66, 1.28), (0.66, -0.78, 1.42), (1.3, -0.98, 2.12), (1.48, -1.1, 2.2), (2.12, -1.56, 1.95),
            (2.66, -2.02, 1.48), (2.82, -2.2, 1.24)], 0.96),
    # III e IV: piantate larghe a terra, ginocchia alte sopra il corpo
    "III": ([(0.46, -0.46, 1.14), (0.7, -0.48, 1.28), (1.32, -0.56, 2.14), (1.52, -0.58, 2.2), (2.14, -0.55, 1.22),
             (2.68, -0.46, 0.32), (2.86, -0.42, 0.016)], 0.9),
    "IV": ([(0.4, -0.26, 1.0), (0.62, -0.16, 1.12), (1.2, 0.3, 2.1), (1.36, 0.44, 2.15), (1.92, 1.0, 1.22),
            (2.38, 1.56, 0.32), (2.52, 1.72, 0.016)], 0.95),
}
SEG_R = [(0.14, 0.14, 0.13), (0.13, 0.152, 0.116), (0.12, 0.134, 0.112), (0.108, 0.12, 0.092),
         (0.09, 0.09, 0.074), (0.072, 0.064, 0.014)]
KNUCKLE_R = [0.156, 0.144, 0.128, 0.104, 0.084]
# spine: (segmento, posizione lungo il segmento, angolo attorno all'asse, lunghezza)
SPIKES = [(1, 0.28, 75, 0.28), (1, 0.55, -70, 0.32), (1, 0.8, 85, 0.26), (3, 0.28, -65, 0.27), (3, 0.62, 60, 0.24),
          (4, 0.42, -30, 0.2), (4, 0.75, 40, 0.17)]


def leg_joints(pts, sx):
    J = [np.array(q, float) * np.array([sx, 1.0, 1.0]) for q in pts]
    # direzione laterale: orizzontale, perpendicolare al piano della zampa
    h = J[-1] - J[0]
    h[2] = 0.0
    h = norm(h)
    return J, np.array([-h[1], h[0], 0.0])


def seg_frame(J, lat, seg):
    """Asse del segmento, lato dorsale e lato laterale."""
    a, b = J[seg], J[seg + 1]
    s = norm(b - a)
    ll = norm(lat - s * float(lat @ s))
    p1 = np.cross(ll, s)
    if p1[2] < 0:
        p1 = -p1
    return a, b, s, p1, ll


def build_leg(J, lat, sc):
    """Ritorna (pezzi neri, articolazioni [(centro, raggio)], pezzi d'osso)."""
    black, bone, knuck = [], [], []
    for i in range(6):
        a, b = J[i], J[i + 1]
        ra, rm, rb = [r * sc for r in SEG_R[i]]
        if i < 5:
            black.append(spindle(a, b, ra, rm, rb))
        else:  # tarso: nero fino al 60%, poi artiglio d'osso
            c = a + (b - a) * 0.6
            black.append(round_cone(tuple(a), tuple(c), ra, rm * 0.9))
            bone.append(round_cone(tuple(a + (b - a) * 0.5), tuple(b), rm * 1.04, 0.008))
    for i, r in enumerate(KNUCKLE_R):
        knuck.append((J[i + 1], r * sc))
    for seg, t, psi, L in SPIKES:
        a, b, s, p1, ll = seg_frame(J, lat, seg)
        d = norm(math.cos(math.radians(psi)) * p1 + math.sin(math.radians(psi)) * ll + 0.6 * s)
        base = a + (b - a) * t
        r_leg = spindle_r(t, *SEG_R[seg]) * sc
        L = L * sc
        black.append(round_cone(tuple(base + d * r_leg * 0.4), tuple(base + d * (r_leg + L * 0.52)), 0.058 * sc, 0.03))
        bone.append(round_cone(tuple(base + d * (r_leg + L * 0.45)), tuple(base + d * (r_leg + L)), 0.042, 0.005))
    return black, knuck, bone


def leg_vein(J, lat, sc, phase):
    """Vena luminosa che si avvolge attorno al femore e si biforca verso il ginocchio."""
    a, b, s, p1, ll = seg_frame(J, lat, 1)
    out = []
    for turn, t0, t1, ph in ((0.7, 0.08, 0.95, phase), (0.35, 0.55, 0.92, phase + 2.2)):
        pts, radii = [], []
        for t in np.linspace(t0, t1, 16):
            ang = ph + 2 * math.pi * turn * (t - t0) + 0.35 * math.sin(11 * t)
            r = spindle_r(t, *SEG_R[1]) * sc
            pts.append(tuple(a + (b - a) * t + (p1 * math.cos(ang) + ll * math.sin(ang)) * r * 0.97))
            radii.append(0.025 - 0.006 * (t - t0) / (t1 - t0))
        out.append(tube(pts, radii))
    return out


legs_front, legs_back, knuckles, bone_bits, leg_veins = [], [], [], [], []
for li, (name, (pts, sc)) in enumerate(LEGS.items()):
    for sx in (1, -1):
        J, lat = leg_joints(pts, sx)
        blk, kn, bn = build_leg(J, lat, sc)
        (legs_front if name in ("I", "II") else legs_back).extend(blk)
        knuckles.extend(kn)
        bone_bits.extend(bn)
        leg_veins += leg_vein(J, lat, sc, phase=1.3 * li + (0.0 if sx > 0 else 2.0))

# pedipalpi: piccole "braccia" ai lati dei cheliceri, sollevate
PALP = [(0.27, -1.0, 1.34), (0.42, -1.24, 1.18), (0.47, -1.44, 1.34), (0.44, -1.62, 1.24), (0.4, -1.7, 1.06)]
PALP_R = [0.06, 0.056, 0.05, 0.044, 0.03, 0.01]
for sx in (1, -1):
    P = [np.array([sx * x, y, z]) for x, y, z in PALP]
    for i in range(len(P) - 1):
        if i < len(P) - 2:
            legs_front.append(spindle(P[i], P[i + 1], PALP_R[i], PALP_R[i] * 1.1, PALP_R[i + 1]))
        else:
            c = P[i] + (P[i + 1] - P[i]) * 0.55
            legs_front.append(round_cone(tuple(P[i]), tuple(c), PALP_R[i], PALP_R[i] * 0.85))
            bone_bits.append(round_cone(tuple(P[i] + (P[i + 1] - P[i]) * 0.45), tuple(P[i + 1]), PALP_R[i] * 1.02,
                                        0.006))
    for q, r in zip(P[1:-1], (0.068, 0.06, 0.05)):
        knuckles.append((q, r))


# ============================================================ zanne a falce (viola-nero, punta d'osso) e dentini
chitin, fang_tips, fang_tip_pts, fang_curves, bristles = [], [], [], [], []
for sx, c in CHEL.items():
    base = c[1] + np.array([0.0, -0.03, -0.04])
    fang = bezier(tuple(base), (sx * 0.28, -1.5, 0.95), (sx * 0.21, -1.6, 0.7), (sx * 0.05, -1.5, 0.58), 18)
    fr = [0.098 * (1 - i / 18) ** 0.75 + 0.007 for i in range(19)]
    chitin.append(tube(fang[:12], fr[:12]))
    chitin.append(sphere(0.118, tuple(base)))   # snodo della zanna
    fang_tips.append(tube(fang[10:], [fr[i] + 0.008 * max(0.0, 1 - (i - 10) / 3) for i in range(10, 19)]))
    fang_tip_pts.append(np.array(fang[-1]))
    fang_curves.append((fang, fr))
    # setole nere sul davanti del chelicero
    for (u, v), L in zip(((0.2, -0.4), (0.45, 0.35), (0.65, -0.2), (0.85, 0.3), (0.35, 0.95)), (0.13, 0.12, 0.12, 0.1, 0.11)):
        q = c[0] + (c[1] - c[0]) * u
        p0, nn = project(chel[sx], q, (sx * v, -1.0, -0.15))
        bristles.append(round_cone(tuple(p0 - nn * 0.03), tuple(p0 + norm(nn + np.array([0, 0, -0.9])) * L), 0.034, 0.006))
chitin.append(spheres([q for q, _ in knuckles], [r for _, r in knuckles]))
# filiere in fondo all'addome
SPIN, SPIN_N = project(abdomen, AB_C, (0.0, 0.8, -0.6))
for dx, dz in ((-0.09, 0.03), (0.09, 0.03), (0.0, -0.06)):
    q = SPIN + np.array([dx, 0.0, dz]) - SPIN_N * 0.06
    chitin.append(round_cone(tuple(q), tuple(q + SPIN_N * 0.2 + np.array([dx * 0.6, 0, 0])), 0.075, 0.045))
m.add("LegsFront", fast_union(legs_front + bristles, k=0.012), BLACK, reflectance=0.2, tris=8500, voxel=0.0235)
m.add("LegsBack", fast_union(legs_back, k=0.012), BLACK, reflectance=0.2, tris=7500, voxel=0.0255)
silk = bezier(tuple(SPIN + SPIN_N * 0.12), tuple(SPIN + SPIN_N * 0.3 + [0, 0.05, -0.1]), (0.0, 2.92, 0.22), (0.0, 2.98, 0.0), 14)
bone_bits.append(tube(silk, [0.03 - 0.0008 * i for i in range(15)]))    # filo di seta che la ancora a terra
m.add("Chitin", fast_union(chitin, k=0.01), CHITIN, reflectance=0.15, role="detail", tris=4500, voxel=0.0275)

# punti a X sulla cucitura (filo d'osso)
stitches = []
seam_rs = resample(SEAM, 0.12)
for i in range(1, len(seam_rs) - 1):
    stitches += x_stitch(abdomen, seam_rs[i], np.subtract(seam_rs[i + 1], seam_rs[i - 1]), size=0.085, r=0.021)

# ============================================================ toppa cucita (fianco sinistro, vista di fronte)
PF = Frame(abdomen, AB_C, (-0.66, -0.36, 0.66))
PW, PH = 0.22, 0.18
patch_region = PF.place(box((PW, 0.7, PH), round=0.06).rot(0, 14, 0))
m.add("Patch", paint(abdomen, patch_region, d=0.032, depth=0.04, k=0.006), PATCH, material="Fabric", role="detail",
      tris=600, voxel=0.017)
border = []
for i in range(32):
    tt = 2 * math.pi * i / 32
    x, z = (PW - 0.045) * math.cos(tt), (PH - 0.045) * math.sin(tt)
    sq = max(abs(math.cos(tt)), abs(math.sin(tt)))
    x, z = x / sq ** 0.7, z / sq ** 0.7
    ca, sa = math.cos(math.radians(-14)), math.sin(math.radians(-14))
    border.append(to_surface(abdomen, PF.point((x * ca - z * sa, 0.0, x * sa + z * ca))))
stitches += dash_stitches(abdomen, border, 12, 0.075, 0.019, lift=0.036)
m.add("Bone", fast_union(fang_tips + bone_bits + stitches), BONE, role="detail", tris=3200, voxel=0.02)

# ============================================================ clessidra rossa sul dorso dell'addome (+ macchioline)
HG = Frame(abdomen, AB_C, (0.0, -0.5, 0.86))
W, H, w0 = 0.38, 0.72, 0.06
hg_poly = [(W, H), (-W, H), (-W * 0.55, H * 0.5), (-w0, 0.05), (-w0, -0.05), (-W * 0.55, -H * 0.5), (-W, -H), (W, -H),
           (W * 0.55, -H * 0.5), (w0, -0.05), (w0, 0.05), (W * 0.55, H * 0.5)]
hg_region = HG.place(prism(hg_poly, -0.7, 0.7).offset(0.03).rot(90, 0, 0))
dots = []
for d, r in (((0.0, 0.52, 0.86), 0.075), ((0.0, 0.8, 0.6), 0.064), ((0.0, 0.96, 0.28), 0.052)):
    p, _ = project(abdomen, AB_C, d)
    dots.append(sphere(r, tuple(p)))
m.add("Hourglass", paint(abdomen, union(hg_region, *dots), d=0.02, depth=0.05, k=0.006), RED, material="Neon",
      role="glow", tris=1800, voxel=0.021)

# ============================================================ occhi
m.add("EyeGlow", union(*eye_glow), EYE_G, material="Neon", role="glow", tris=1500, voxel=0.0115)
m.add("Sockets", union(*sockets), SOCKET, role="eye", tris=900, voxel=0.016)

# ============================================================ veleno (unica parte "Venom")
venom = list(leg_veins)
# veleno che trasuda dalle articolazioni delle zampe alzate e pende in gocce
for name, (pts, sc) in LEGS.items():
    if name not in ("I", "II"):
        continue
    for sx in (1, -1):
        J, _ = leg_joints(pts, sx)
        for j, L, rd in ((2, 0.16, 0.05), (4, 0.11, 0.04)):
            top = J[j] - np.array([0.0, 0.0, KNUCKLE_R[j - 1] * sc * 0.8])
            venom.append(hang_drop(top, L, 0.032, rd))
# fili lunghi appesi alle zanne, una goccia in caduta e bava che pende fra le due punte
for tp, L in zip(fang_tip_pts, (0.22, 0.17)):
    venom.append(hang_drop(tp + np.array([0, -0.004, 0.014]), L, 0.02, 0.052))
a, b = fang_tip_pts
sag = [a + (b - a) * t + np.array([0.0, -0.012, -0.11 * math.sin(math.pi * t)]) for t in np.linspace(0, 1, 9)]
venom.append(tube([tuple(q) for q in sag], [0.018, 0.019, 0.021, 0.024, 0.026, 0.024, 0.021, 0.019, 0.018]))
venom.append(hang_drop(sag[4], 0.08, 0.024, 0.04))
fall = np.array([a[0], a[1], 0.18])
venom.append(union(sphere(0.04, tuple(fall)), round_cone(tuple(fall), tuple(fall + [0, 0, 0.08]), 0.038, 0.008), k=0.02))
# veleno che cola lungo il dorso delle zanne (la punta d'osso resta scoperta)
for fang, fr in fang_curves:
    pts, radii = [], []
    for i in range(2, 14):
        t = norm(np.subtract(fang[i + 1], fang[i - 1]))
        back = norm(np.array([0.0, 1.0, 0.3]) - t * float(t @ np.array([0.0, 1.0, 0.3])))
        pts.append(tuple(np.asarray(fang[i]) + back * fr[i] * 0.85))
        radii.append(0.026 if i < 12 else 0.03)
    venom.append(tube(pts, radii))
# pozza a terra sotto le zanne, con schizzi e una corona dove cade la goccia
pz = np.array([0.0, -1.5, 0.0])
venom.append(union(ellipsoid((0.34, 0.25, 0.028), tuple(pz)), ellipsoid((0.17, 0.15, 0.028), tuple(pz + [0.27, -0.12, 0])),
                   ellipsoid((0.15, 0.12, 0.028), tuple(pz + [-0.25, 0.1, 0])),
                   ellipsoid((0.1, 0.09, 0.028), tuple(pz + [-0.12, -0.25, 0])), k=0.08))
for ang in range(0, 360, 30):
    rr = 0.46 + 0.08 * math.sin(ang * 3.1)
    q = pz + [rr * math.cos(math.radians(ang)), rr * 0.82 * math.sin(math.radians(ang)), 0.0]
    venom.append(ellipsoid((0.034, 0.034, 0.02), tuple(q)))
for q, r in (((-0.16, -1.42), 0.045), ((0.2, -1.64), 0.036), ((-0.3, -1.4), 0.028), ((0.1, -1.36), 0.03)):
    venom.append(sphere(r, (q[0], q[1], 0.022)))   # bolle tossiche che affiorano dalla pozza
crown_c = np.array([a[0], a[1], 0.0])
for ang in range(0, 360, 45):
    d = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0.0])
    venom.append(round_cone(tuple(crown_c + d * 0.06), tuple(crown_c + d * 0.1 + [0, 0, 0.09]), 0.022, 0.012))
    venom.append(sphere(0.02, tuple(crown_c + d * 0.11 + [0, 0, 0.11])))
# veleno che trapela dalla cucitura e vene che si allargano dalla ferita
venom.append(tube([tuple(q - normal_at(abdomen, q) * 0.014) for q in SEAM], 0.046))
for i in (1, 5, 9, 13, 17):
    if i >= len(SEAM) - 1:
        continue
    t = norm(np.subtract(SEAM[i + 1], SEAM[i - 1]))
    side = np.cross(normal_at(abdomen, SEAM[i]), t) * (1 if i % 4 == 1 else -1)
    venom += vein(abdomen, SEAM[i], side + t * rng.uniform(-0.4, 0.4), rng.uniform(0.4, 0.62), 0.032, branches=2)
# vene sul fianco sinistro (visibili di fronte) e sul retro
for d, h, L in (((-0.95, 0.3, 0.1), (0.2, 0.6, 0.8), 0.75), ((0.35, 0.95, 0.05), (0.5, 0.2, 0.8), 0.6)):
    p0, _ = project(abdomen, AB_C, d)
    venom += vein(abdomen, p0, h, L, 0.034, branches=2)
# colature che scendono lungo i fianchi dell'addome e finiscono in gocce appese
for d in ((0.62, -0.3, 0.72), (-0.6, -0.2, 0.75), (-0.62, 0.62, 0.5), (0.3, 0.9, 0.55), (0.12, -0.6, 0.8)):
    p0, _ = project(abdomen, AB_C, d)
    venom += drip(abdomen, p0, r0=0.03, r1=0.046, drop=0.075, hang=0.15)
# pustole e bolle tossiche a grappoli
pc, pr = [], []
for d, n in (((0.86, 0.55, -0.1), 7), ((-0.88, 0.25, -0.15), 6), ((-0.4, 0.85, 0.55), 5), ((0.5, -0.5, 0.35), 4)):
    c0, _ = project(abdomen, AB_C, d)
    for i in range(n):
        q = c0 + rng.normal(size=3) * 0.12
        p, nn = project(abdomen, AB_C, q - AB_C)
        r = float(rng.uniform(0.035, 0.085)) if i else 0.11
        pc.append(p - nn * r * 0.3)
        pr.append(r)
venom.append(spheres(pc, pr))
m.add("Venom", fast_union(venom), VENOM, material="Neon", role="glow", tris=14000, voxel=0.0143)

m.add("Shine", union(*shines), WHITE, role="shine", tris=300, voxel=0.009)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
