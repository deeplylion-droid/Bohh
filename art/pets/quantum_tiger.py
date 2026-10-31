"""Tigre Quantica (QuantumTiger) - pet del Percorso Estremo (felini super intelligenti).

Una tigre bianca argentata, possente e regale, in piedi su un disco antigravita' che fluttua sopra un'onda
di energia. Le strisce sono circuiti luminosi che si alternano ciano e magenta (con le piazzole saldate in fondo),
anche sulla fronte, sulle guance, sulle zampe e sulla coda. In mezzo alla fronte si apre un terzo occhio verticale
che brilla di rosa: le tracce dei circuiti partono da li'. Attorno alla testa orbitano tre anelli olografici come in
un atomo, ognuno con il suo elettrone (parte Neon "Nebula": il gioco ci aggancia una nebulosa viola-blu); i
circuiti ciano sono la parte "Mane" (scintille elettriche). Sguardo fiero con occhi azzurro ghiaccio, mento alto,
gorgiera bianca e due zanne che spuntano dal sorriso sicuro. La coda a S (gruppo "Tail") ha anelli magenta e la
punta luminosa. Tocco "toy horror": una toppa blu notte cucita sulla spalla destra con grossi punti a croce rosa.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, box, capped_cone, capsule, cylinder, ellipsoid, euler, halfspace_z,  # noqa: E402
                     look_matrix, prism,
                     round_cone, smax, smin, sphere, torus, tube, union)
from lib.toy import Model  # noqa: E402


# ============================================================ helper (lib/ non si modifica: copiati/adattati qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def mix(a, b, t):
    return np.asarray(a, dtype=np.float64) * (1 - t) + np.asarray(b, dtype=np.float64) * t


def grad(sdf, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float64)
    g = np.zeros(3)
    for ax in range(3):
        e = np.zeros(3)
        e[ax] = eps
        g[ax] = sdf((p + e)[None, :].astype(np.float32))[0] - sdf((p - e)[None, :].astype(np.float32))[0]
    return g / max(np.linalg.norm(g), 1e-9)


def on_surface(sdf, p, lift=0.0, iters=4):
    """Porta p sulla superficie (a distanza 'lift' verso l'esterno) seguendo il gradiente."""
    p = np.asarray(p, dtype=np.float64)
    for _ in range(iters):
        d = float(sdf(p[None, :].astype(np.float32))[0])
        p = p - grad(sdf, p) * (d - lift)
    return p


def grad_many(sdf, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float64).reshape(-1, 3)
    g = np.zeros_like(p)
    for ax in range(3):
        e = np.zeros(3)
        e[ax] = eps
        g[:, ax] = sdf((p + e).astype(np.float32)) - sdf((p - e).astype(np.float32))
    return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)


def project_many(sdf, origins, dirs, max_dist=3.0, steps=300, iters=26):
    """Tanti raggi insieme (partenza interna): ritorna (punti della superficie, normali)."""
    o = np.asarray(origins, dtype=np.float64).reshape(-1, 3)
    d = np.asarray(dirs, dtype=np.float64).reshape(-1, 3)
    if len(d) == 1 and len(o) > 1:
        d = np.repeat(d, len(o), axis=0)
    if len(o) == 1 and len(d) > 1:
        o = np.repeat(o, len(d), axis=0)
    d = d / np.linalg.norm(d, axis=1, keepdims=True)
    n = len(o)
    ts = np.linspace(0.0, max_dist, steps)
    pts = (o[:, None, :] + ts[None, :, None] * d[:, None, :]).reshape(-1, 3).astype(np.float32)
    vals = sdf(pts).reshape(n, steps)
    if (vals[:, 0] > 0).any():
        bad = np.nonzero(vals[:, 0] > 0)[0]
        print(f"[tiger] attenzione: {len(bad)} raggi partono fuori dalla forma, es. {np.round(o[bad[0]], 3)}")
    outside = vals > 0
    if not outside.any(axis=1).all():
        raise ValueError("project_many: un raggio non esce dalla forma")
    first = np.argmax(outside, axis=1)
    lo, hi = ts[np.maximum(first - 1, 0)], ts[first]
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        out = sdf((o + mid[:, None] * d).astype(np.float32)) > 0
        hi = np.where(out, mid, hi)
        lo = np.where(out, lo, mid)
    p = o + (0.5 * (lo + hi))[:, None] * d
    return p, grad_many(sdf, p)


def surf(sdf, origin, target):
    """Punto della superficie (e normale) andando da origin (interno) verso target."""
    p, n = project_many(sdf, [origin], [np.asarray(target, float) - np.asarray(origin, float)])
    return p[0], n[0]


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


def paint(core, region, out=0.016, inn=0.035, margin=0.05, k=0.02):
    """Strato di "vernice" sottile (guscio fra -inn e +out attorno a core) dentro 'region'."""
    def f(p):
        r = region(p)
        d = np.maximum(r, margin).astype(np.float32)
        idx = np.nonzero(r < margin)[0]
        if len(idx):
            c = core(p[idx])
            d[idx] = smax(np.maximum(c - out, -c - inn), r[idx], k)
        return d

    return SDF(f, np.maximum(core.lo - out, region.lo), np.minimum(core.hi + out, region.hi))


def shrink(s, step=0.05, pad=0.03):
    """Ricalcola un ingombro stretto (le unioni morbide annidate lo gonfiano) campionando la forma."""
    lo, hi = s.lo.astype(np.float64), s.hi.astype(np.float64)
    n = np.maximum(np.ceil((hi - lo) / step).astype(int) + 1, 2)
    xs, ys, zs = (np.linspace(lo[i], hi[i], n[i]) for i in range(3))
    gy, gz = np.meshgrid(ys, zs, indexing="ij")
    plane = np.stack([np.zeros_like(gy), gy, gz], -1).reshape(-1, 3).astype(np.float32)
    a, b = np.full(3, np.inf), np.full(3, -np.inf)
    for x in xs:
        plane[:, 0] = x
        msk = s(plane) < step * 1.5
        if msk.any():
            pts = plane[msk]
            a, b = np.minimum(a, pts.min(0)), np.maximum(b, pts.max(0))
    return SDF(s.f, a - step - pad, b + step + pad)


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


def orient(axis, side=(1.0, 0.0, 0.0)):
    """Matrice che porta l'asse Z locale su 'axis' (e X locale il piu' possibile verso 'side')."""
    a = norm(axis)
    s = np.asarray(side, dtype=np.float64)
    s = s - a * float(s @ a)
    if np.linalg.norm(s) < 1e-6:
        s = np.array([0.0, 1.0, 0.0]) - a * a[1]
    s = norm(s)
    return np.stack([s, np.cross(a, s), a], axis=1).astype(np.float32)


def ell(c, radii, axis=(0, 0, 1), side=(1, 0, 0)):
    """Ellissoide con il terzo raggio lungo 'axis' (il primo verso 'side')."""
    return ellipsoid(radii).rotate(orient(axis, side)).translate(tuple(np.asarray(c, dtype=np.float64)))


def rot_pts(R, pts, pivot=(0, 0, 0)):
    pv = np.asarray(pivot, dtype=np.float64)
    return (np.asarray(pts, dtype=np.float64) - pv) @ np.asarray(R, dtype=np.float64).T + pv


def horn(base, d, L, r0, curl=(0, 0, 0), n=5, r1=0.006, power=1.0):
    """Cono curvo (ciuffo, artiglio, dente): parte da base verso d (lunghezza L) e si piega verso 'curl'."""
    base, d, c = np.asarray(base, float), norm(d), np.asarray(curl, float)
    ts = np.linspace(0.0, 1.0, n)
    pts = [tuple(base + d * L * t + c * L * t * t) for t in ts]
    return tube(pts, [r0 + (r1 - r0) * t ** power for t in ts])


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


def surface_line(base, origin_fn, pts2d, step=0.025):
    """Linea disegnata in 2D (lista di punti) e proiettata sulla superficie: origin_fn(q2) -> (origine, target)."""
    dense = resample([np.array([a, b, 0.0]) for a, b in pts2d], step)
    os_, ts_ = zip(*[origin_fn(q[0], q[1]) for q in dense])
    pts, nrs = project_many(base, list(os_), [np.asarray(t) - np.asarray(o) for o, t in zip(os_, ts_)])
    return pts, nrs


def stitch_cross(base, center, tangent, size=0.05, r=0.014, lift=0.008):
    """Punto a croce (X) sulla superficie."""
    c = np.asarray(center, float)
    nr = grad(base, c)
    t = norm(np.asarray(tangent, float) - nr * float(np.dot(tangent, nr)))
    s = np.cross(nr, t)
    out = []
    for a, b in ((t + s, -t - s), (t - s, -t + s)):
        pa = on_surface(base, c + a * size * 0.7, lift, 3)
        pb = on_surface(base, c + b * size * 0.7, lift, 3)
        out.append(capsule(tuple(pa), tuple(pb), r))
    return out


# ============================================================ colori
FUR = (214, 220, 238)       # pelo bianco-argento
WHITE = (253, 253, 255)     # muso, gorgiera, petto, macchie sopra gli occhi
NAVY = (30, 34, 76)         # dorso delle orecchie, contorno degli occhi, toppa
CYAN = (20, 230, 255)       # circuiti ciano
MAGENTA = (255, 40, 205)    # circuiti magenta
RING = (214, 176, 255)      # anelli olografici quantici (lavanda)
THIRD = (255, 140, 240)     # terzo occhio
IRIS = (110, 220, 255)      # occhi azzurro ghiaccio
INK = (16, 14, 36)          # pupille, naso, labbra
TOOTH = (255, 252, 246)
DISC = (58, 64, 92)         # disco antigravita' (metallo canna di fucile)
THREAD = (255, 92, 196)     # filo della toppa

m = Model("QuantumTiger", "pet")
rng = np.random.default_rng(47)

# ============================================================ testa (spazio locale: muso verso -Y)
HEAD_POS = np.array([0.0, -1.08, 2.5])
HS = 1.32
R_HEAD = euler(-4.0, 0.0, 10.0)       # mento alto e fiero, girata verso la camera 3/4


def H(s):
    return s.scale(HS).rotate(R_HEAD).translate(HEAD_POS)


def hp(p):
    return rot_pts(R_HEAD, np.asarray(p, dtype=np.float64) * HS) + HEAD_POS


def hv(v):
    return rot_pts(R_HEAD, v)


cran = ellipsoid((0.43, 0.39, 0.36), (0, 0.04, 0.06))
brow_ridge = [ellipsoid((0.16, 0.12, 0.09), (sx * 0.16, -0.25, 0.15)) for sx in (1, -1)]
cheeks = [ellipsoid((0.25, 0.22, 0.21), (sx * 0.22, -0.1, -0.1)) for sx in (1, -1)]
muzzle = ellipsoid((0.21, 0.19, 0.16), (0, -0.27, -0.12))
pads_l = [ellipsoid((0.115, 0.1, 0.095), (sx * 0.08, -0.37, -0.14)) for sx in (1, -1)]
chin = ellipsoid((0.1, 0.09, 0.075), (0, -0.3, -0.27))
bridge = capsule((0, -0.2, 0.1), (0, -0.41, -0.04), 0.085)
head0 = union(cran, *cheeks, k=0.14)
head0 = union(head0, muzzle, *brow_ridge, k=0.1)
head0 = union(head0, *pads_l, chin, bridge, k=0.06)

# occhi fieri (palpebra superiore inclinata verso il naso, palpebra inferiore che stringe lo sguardo)
EYE_D = {sx: norm((sx * 0.42, -0.88, 0.08)) for sx in (1, -1)}
EYE_C = {}
for sx in (1, -1):
    o = np.array((sx * 0.1, -0.12, 0.06))
    EYE_C[sx], _ = surf(head0, o, o + EYE_D[sx])


def eye_place(shape, sx, offset=(0.0, 0.0, 0.0)):
    """Coordinate locali dell'occhio: X verso il naso (-x mondo), -Y verso lo sguardo, Z in alto."""
    return shape.translate(offset).rotate(look_matrix(EYE_D[sx])).translate(EYE_C[sx])


EA, EB, EC = 0.1, 0.048, 0.076
head1 = head0.subtract(union(*[eye_place(ellipsoid((0.112, 0.074, 0.088)), sx, (0, 0.03, 0)) for sx in (1, -1)]),
                       k=0.03)
lids = []
for sx in (1, -1):
    A, B, C = EA + 0.022, EB + 0.026, EC + 0.024

    def top_plane(p, sx=sx):
        return (0.034 - 0.32 * sx * p[:, 0] - p[:, 2]) / math.sqrt(1 + 0.32 ** 2)

    def low_plane(p):
        return p[:, 2] + 0.052

    lid = ellipsoid((A, B, C)).intersect(SDF(top_plane, (-A, -B, -C), (A, B, C)))
    low = ellipsoid((A, B, C)).intersect(SDF(low_plane, (-A, -B, -C), (A, B, C)))
    lids += [eye_place(lid, sx, (0, 0.034, 0)), eye_place(low, sx, (0, 0.036, 0))]
head1 = union(head1, *lids, k=0.01)

# terzo occhio verticale sulla fronte
T_D = norm((0.0, -0.72, 0.66))
T_C, _ = surf(head0, (0.0, 0.0, 0.05), np.array((0.0, 0.0, 0.05)) + T_D)


def third_place(shape, offset=(0.0, 0.0, 0.0)):
    return shape.translate(offset).rotate(look_matrix(T_D, up=(0.0, 0.66, 0.72))).translate(T_C)


head1 = head1.subtract(third_place(ellipsoid((0.058, 0.06, 0.092)), (0, 0.03, 0)), k=0.02)
third_lid = third_place(ellipsoid((0.066, 0.07, 0.1)).subtract(ellipsoid((0.048, 0.2, 0.084))), (0, 0.035, 0))
head1 = union(head1, third_lid, k=0.008)


# orecchie tonde da tigre
def ear_shape():
    cone = round_cone((0, 0, -0.03), (0, 0, 0.19), 0.17, 0.085)
    slab = SDF(lambda p: np.abs(p[:, 1]) - 0.06, (-1, -1, -1), (1, 1, 1))
    cup = round_cone((0, -0.065, 0.0), (0, -0.065, 0.17), 0.11, 0.05)
    return cone.intersect(slab, k=0.025).subtract(cup, k=0.02)


EAR_R = {sx: euler(-12, sx * 30, -sx * 12) for sx in (1, -1)}
EAR_T = {sx: np.array((sx * 0.3, 0.07, 0.25)) for sx in (1, -1)}


def ear_pose(s, sx):
    return s.rotate(EAR_R[sx]).translate(EAR_T[sx])


def ear_pt(p, sx):
    return rot_pts(EAR_R[sx], p) + EAR_T[sx]


ears = [ear_pose(ear_shape(), sx) for sx in (1, -1)]
EAR_CUPS = [ear_pose(round_cone((0, -0.065, 0.0), (0, -0.065, 0.17), 0.11, 0.05), sx) for sx in (1, -1)]
EAR_BACKS = [ear_pose(ear_shape().offset(0.013).intersect(SDF(lambda p: 0.004 - p[:, 1], (-1, -1, -1), (1, 1, 1)),
                                                          k=0.01), sx) for sx in (1, -1)]
EAR_SPOTS = [ear_pose(ellipsoid((0.07, 0.03, 0.06), (0.0, 0.07, 0.07)), sx) for sx in (1, -1)]
NOSE_C = np.array((0.0, -0.457, -0.05))
nostrils = union(*[ellipsoid((0.022, 0.03, 0.019)).rot(0, sx * 30, sx * 25).translate(NOSE_C + (sx * 0.036, -0.014, -0.016))
                   for sx in (1, -1)])
head2 = union(head1, *ears, k=0.04)
head_final = shrink(head2.subtract(nostrils, k=0.01))

# ============================================================ corpo (in piedi, petto in fuori, zampa destra avanti)
DISC_TOP = 0.5
chest = ellipsoid((0.47, 0.5, 0.5), (0, -0.45, 1.5))
ribs = ellipsoid((0.42, 0.56, 0.45), (0, 0.1, 1.47))
haunch = ellipsoid((0.45, 0.42, 0.45), (0, 0.63, 1.46))
scap = [ell((sx * 0.27, -0.47, 1.8), (0.16, 0.22, 0.26), axis=(0, -0.3, 1.0)) for sx in (1, -1)]
torso = union(union(chest, ribs, k=0.3), haunch, k=0.28)
torso = union(torso, *scap, k=0.15)
NECK = [(0, -0.55, 1.75), (0, -0.82, 2.1), (0, -0.98, 2.34)]
neck = tube(NECK, [0.4, 0.36, 0.32], k=0.08)
PZ = DISC_TOP + 0.085
FRONT = {1: dict(sh=np.array([0.33, -0.5, 1.5]), el=np.array([0.39, -0.56, 1.02]), wr=np.array([0.37, -0.86, 0.69]),
                 paw=np.array([0.37, -0.96, PZ])),
         -1: dict(sh=np.array([-0.33, -0.5, 1.5]), el=np.array([-0.38, -0.4, 1.02]), wr=np.array([-0.36, -0.5, 0.68]),
                  paw=np.array([-0.36, -0.58, PZ]))}
HIND = {sx: dict(hip=np.array([sx * 0.34, 0.62, 1.45]), knee=np.array([sx * 0.42, 0.36, 1.0]),
                 hock=np.array([sx * 0.39, 0.84, 0.77]), paw=np.array([sx * 0.39, 0.72, PZ])) for sx in (1, -1)}
leg_parts = []
for sx, L in FRONT.items():
    sh, el, wr, paw = L["sh"], L["el"], L["wr"], L["paw"]
    leg_parts += [
        ell(mix(sh, el, 0.4) + np.array([sx * 0.04, 0.0, 0.0]), (0.26, 0.28, 0.36), axis=el - sh),
        round_cone(sh, el, 0.24, 0.17),
        round_cone(el, wr, 0.17, 0.13),
        ell(mix(el, wr, 0.3), (0.17, 0.18, 0.24), axis=wr - el),
        round_cone(wr, paw, 0.13, 0.135),
        ellipsoid((0.21, 0.26, 0.105), tuple(paw + np.array([0, -0.05, 0.0]))),
    ]
    for dx in (-0.125, -0.042, 0.042, 0.125):
        leg_parts.append(sphere(0.072, tuple(paw + np.array([dx, -0.235 + 0.6 * dx * dx, -0.02]))))
for sx, L in HIND.items():
    hip, knee, hock, paw = L["hip"], L["knee"], L["hock"], L["paw"]
    leg_parts += [
        ell(mix(hip, knee, 0.45) + np.array([sx * 0.06, 0.04, 0.0]), (0.29, 0.33, 0.45), axis=knee - hip),
        round_cone(hip, knee, 0.27, 0.17),
        round_cone(knee, hock, 0.16, 0.11),
        ell(mix(knee, hock, 0.35) + np.array([0, 0.03, 0.03]), (0.15, 0.16, 0.24), axis=hock - knee),
        round_cone(hock, paw, 0.11, 0.12),
        ellipsoid((0.19, 0.24, 0.1), tuple(paw + np.array([0, -0.05, 0.0]))),
    ]
    for dx in (-0.115, -0.038, 0.038, 0.115):
        leg_parts.append(sphere(0.064, tuple(paw + np.array([dx, -0.21 + 0.6 * dx * dx, -0.018]))))
legs = union(*leg_parts, k=0.06)
ABOVE_DISC = halfspace_z(DISC_TOP, above=True)

core = union(torso, neck, k=0.18)
core = union(core, H(head_final), k=0.1)
core = union(core, legs, k=0.08)
core0 = shrink(core.intersect(ABOVE_DISC))
body_only = shrink(union(union(torso, neck, k=0.18), legs, k=0.08).intersect(ABOVE_DISC))

# ============================================================ coda a S alzata (gruppo "Tail")
TAIL_PTS = bezier((0.0, 0.98, 1.62), (0.0, 1.5, 1.5), (0.0, 1.78, 2.1), (0.0, 1.45, 2.58), 18)
TAIL_PIVOT = (0.0, 1.0, 1.62)
NT = len(TAIL_PTS) - 1
tail_r = [0.125 - 0.035 * (i / NT) for i in range(NT + 1)]
tail_r[-1] = 0.07
tail = tube(TAIL_PTS, tail_r)


def tail_frame(i):
    p = np.asarray(TAIL_PTS[i], dtype=np.float64)
    t = norm(np.asarray(TAIL_PTS[min(i + 1, NT)]) - np.asarray(TAIL_PTS[max(i - 1, 0)]))
    return p, t


tail_glow = []
for i in (5, 8, 11, 14):
    p, t = tail_frame(i)
    tail_glow.append(torus(tail_r[i] + 0.004, 0.026).rotate(orient(t)).translate(tuple(p)))
tip_p, tip_t = tail_frame(NT)
tail_glow.append(sphere(0.085, tuple(tip_p + tip_t * 0.02)))
tail_glow_s = fast_union(tail_glow)

# ============================================================ disco antigravita' + onda di energia a terra
DC = np.array((0.0, 0.08, 0.0))
disc = cylinder(tuple(DC + (0, 0, 0.38)), tuple(DC + (0, 0, DISC_TOP - 0.06)), 1.12, round=0.06)
disc = disc.subtract(torus(0.92, 0.034, tuple(DC + (0, 0, DISC_TOP))), k=0.01)
disc = disc.subtract(torus(0.55, 0.03, tuple(DC + (0, 0, DISC_TOP))), k=0.01)
thrusters = []
disc_cyan = [torus(0.92, 0.024, tuple(DC + (0, 0, DISC_TOP - 0.004))),
             sphere(0.32, tuple(DC + (0, 0, 0.36))).intersect(halfspace_z(0.33, above=False)),
             torus(0.5, 0.022, tuple(DC + (0, 0, 0.022))), torus(0.86, 0.02, tuple(DC + (0, 0, 0.02)))]
for k_ in range(4):
    a = math.radians(45 + 90 * k_)
    c = DC + np.array((0.74 * math.cos(a), 0.74 * math.sin(a), 0.0))
    thrusters.append(capped_cone(tuple(c + (0, 0, 0.36)), tuple(c + (0, 0, 0.22)), 0.12, 0.085, round=0.015))
    disc_cyan.append(cylinder(tuple(c + (0, 0, 0.205)), tuple(c + (0, 0, 0.225)), 0.065))
disc_magenta = [torus(1.12, 0.034, tuple(DC + (0, 0, 0.41))), torus(0.55, 0.022, tuple(DC + (0, 0, DISC_TOP - 0.004)))]

# ============================================================ anelli quantici attorno alla testa
RING_C = hp((0.0, 0.0, 0.08))
RING_R = 0.86
ring_normals = [norm((0.0, 0.42, 1.0)), norm((0.82, 0.25, 0.62)), norm((-0.82, 0.25, 0.62))]
rings, electrons_c, electrons_m = [], [], []
for i, nrm in enumerate(ring_normals):
    rings.append(torus(RING_R - 0.04 * i, 0.021).rotate(orient(nrm)).translate(tuple(RING_C)))
    Rm = orient(nrm)
    a = math.radians((40, 200, 320)[i])
    e = rot_pts(Rm, ((RING_R - 0.04 * i) * math.cos(a), (RING_R - 0.04 * i) * math.sin(a), 0.0)) + RING_C
    (electrons_c if i % 2 == 0 else electrons_m).append(sphere(0.055, tuple(e)))

# ============================================================ strisce-circuito (ciano e magenta, si alternano)
CR0, CR1 = 0.034, 0.018


def stripe_on(base, pts_world_targets, origins, r0=CR0, r1=CR1, pad=True):
    pts, nrs = project_many(base, origins, [t - o for t, o in zip(pts_world_targets, origins)])
    dense = resample(pts, 0.03)
    nn = grad_many(base, dense)
    q, nq = project_many(base, [p - n * 0.08 for p, n in zip(dense, nn)], list(nn))
    n = len(q)
    out = [tube([tuple(p) for p in q], [r0 + (r1 - r0) * (i / max(n - 1, 1)) for i in range(n)])]
    if pad:
        out.append(cylinder(tuple(q[-1] - nq[-1] * 0.03), tuple(q[-1] + nq[-1] * 0.012), 0.04, round=0.01))
    return out


stripes = {0: [], 1: []}
BODY_ZC = 1.47
for sx in (1, -1):
    for j, y0 in enumerate((-0.42, -0.16, 0.1, 0.36, 0.6, 0.84)):
        jog = 0.07 * (1 if j % 2 == 0 else -1)
        path = [(8, 0.0), (42, 0.0), (48, jog), (80, jog), (88, 0.0), (112, 0.0)]
        if y0 > 0.7:
            path = path[:4]
        org, tgt = [], []
        for ang, dy in path:
            a = math.radians(ang)
            y = y0 + dy
            o = np.array((0.0, y, BODY_ZC))
            org.append(o)
            tgt.append(o + np.array((sx * math.sin(a), 0.0, math.cos(a))))
        stripes[j % 2] += stripe_on(body_only, tgt, org)
    # fasce sulle zampe (archi sul lato esterno)
    for L, keys, ts, col in ((FRONT[sx], ("el", "wr"), (0.25, 0.68), 0), (HIND[sx], ("knee", "hock"), (0.3, 0.75), 1),
                             (HIND[sx], ("hip", "knee"), (0.55,), 0)):
        a_, b_ = L[keys[0]], L[keys[1]]
        ax = norm(b_ - a_)
        s1 = norm(np.cross(ax, (0.0, 1.0, 0.0)))
        s1 = s1 if s1[0] * sx > 0 else -s1
        s2 = np.cross(ax, s1)
        for t in ts:
            c = mix(a_, b_, t)
            org = [c] * 7
            tgt = [c + (s1 * math.cos(math.radians(th)) + s2 * math.sin(math.radians(th))) for th in np.linspace(-80, 80, 7)]
            stripes[col] += stripe_on(body_only, tgt, org, r0=0.03, r1=0.022, pad=False)
            col = 1 - col
# fronte: tracce che partono dal terzo occhio verso la nuca, strisce sulle guance e sopra gli occhi
head_traces = {0: [], 1: []}
for col, tr in ((0, ((0.0, -0.2, 0.45), (0.0, 0.0, 0.49), (0.0, 0.25, 0.44))),
                (1, ((0.05, -0.27, 0.38), (0.12, -0.18, 0.44), (0.17, 0.0, 0.46), (0.2, 0.18, 0.4))),
                (1, ((-0.05, -0.27, 0.38), (-0.12, -0.18, 0.44), (-0.17, 0.0, 0.46), (-0.2, 0.18, 0.4))),
                (0, ((0.31, -0.18, 0.1), (0.36, -0.05, 0.16), (0.4, 0.1, 0.16))),
                (0, ((-0.31, -0.18, 0.1), (-0.36, -0.05, 0.16), (-0.4, 0.1, 0.16))),
                (1, ((0.36, -0.2, -0.04), (0.43, -0.08, -0.02), (0.45, 0.05, -0.08))),
                (1, ((-0.36, -0.2, -0.04), (-0.43, -0.08, -0.02), (-0.45, 0.05, -0.08))),
                (0, ((0.3, -0.16, -0.17), (0.38, -0.04, -0.2), (0.38, 0.08, -0.26))),
                (0, ((-0.3, -0.16, -0.17), (-0.38, -0.04, -0.2), (-0.38, 0.08, -0.26)))):
    tg = resample([np.array(p) for p in tr], 0.02)
    q, nq = project_many(head0, [(0.0, 0.0, 0.0)] * len(tg), [np.asarray(t) for t in tg])
    n = len(q)
    head_traces[col].append(tube([tuple(p) for p in q], [0.026 - 0.01 * (i / (n - 1)) for i in range(n)]))
    head_traces[col].append(cylinder(tuple(q[-1] - nq[-1] * 0.03), tuple(q[-1] + nq[-1] * 0.01), 0.03, round=0.008))

# ============================================================ parti: pelle
HEAD_ZONE = H(ellipsoid((0.66, 0.62, 0.66), (0.0, -0.05, 0.08)))
m.add("Body", core0.subtract(HEAD_ZONE.offset(-0.03)), FUR, tris=2500, voxel=0.03)
m.add("Head", core0.intersect(HEAD_ZONE.offset(0.03)), FUR, tris=2500, voxel=0.024)
m.add("Tail", tail, FUR, tris=450, voxel=0.028, group="Tail", pivot=TAIL_PIVOT)

# ============================================================ pelo bianco: gorgiera, cuscinetti del muso, petto, macchie
ruff = []
for sx in (1, -1):
    for bz, dz, L, r0 in ((0.0, -0.1, 0.27, 0.1), (-0.11, -0.45, 0.31, 0.11), (-0.21, -0.85, 0.27, 0.1)):
        base = np.array((sx * 0.33, -0.04, bz))
        ruff.append(horn(base, norm((sx * 0.9, 0.3, dz)), L, r0, curl=(0, 0.08, -0.08), n=4, r1=0.016))
pad_solid = union(*[ellipsoid((0.118, 0.102, 0.097), (sx * 0.081, -0.373, -0.142)) for sx in (1, -1)],
                  ellipsoid((0.104, 0.094, 0.078), (0, -0.303, -0.272)), k=0.03).subtract(nostrils.offset(0.01))
brow_spots = [eye_place(ellipsoid((0.07, 0.2, 0.04)), sx, (sx * -0.0, 0.0, 0.135)) for sx in (1, -1)]
white_head = union(ruff_s := union(*ruff).subtract(head0.offset(-0.03)), pad_solid.subtract(head0.offset(-0.04)),
                   union(*EAR_SPOTS).subtract(head0.offset(-0.02)))
chest_tufts = [ell((0.0, -0.94, 1.5), (0.27, 0.13, 0.34), axis=(0, -0.35, 1.0))]
for bx, bz, L in ((0.0, 1.38, 0.3), (0.14, 1.44, 0.26), (-0.14, 1.44, 0.26), (0.07, 1.26, 0.22), (-0.07, 1.26, 0.22)):
    b, nb = surf(body_only, (bx * 0.5, -0.6, bz), (bx, -1.5, bz))
    chest_tufts.append(horn(b - nb * 0.06, norm(nb * 0.5 + np.array((bx * 0.6, 0.0, -1.0))), L, 0.09,
                            curl=(0, 0.1, 0), n=4, r1=0.015))
chest_fluff = fast_union(chest_tufts, k=0.03).subtract(body_only.offset(-0.03))
white = union(H(white_head), chest_fluff,
              paint(core0, H(union(*brow_spots)), out=0.014, inn=0.04, k=0.01),
              paint(core0, H(union(*EAR_CUPS).offset(0.02)), out=0.014, inn=0.045))
m.add("WhiteFur", white, WHITE, role="detail", tris=1100, voxel=0.02)

# ============================================================ blu notte: dorso delle orecchie, contorno occhi, toppa cucita
liner = paint(head1, union(*[eye_place(ellipsoid((EA + 0.03, 0.3, EC + 0.028)).subtract(ellipsoid((EA + 0.004, 0.4, EC + 0.004))),
                                       sx, (0, 0.03, 0)) for sx in (1, -1)]), out=0.012, inn=0.03, k=0.006)
PATCH_C, PATCH_N = surf(body_only, (0.1, -0.42, 1.6), (0.9, -0.5, 1.75))
PR = orient(PATCH_N, side=(0.0, 1.0, 0.0))
patch_reg = box((0.16, 0.13, 0.4), round=0.04).rotate(PR).translate(tuple(PATCH_C))
patch = paint(core0, patch_reg, out=0.02, inn=0.05, k=0.01)
m.add("Navy", union(H(union(*EAR_BACKS)), H(liner), patch), NAVY, role="detail", tris=700, voxel=0.018)
stitches = []
for u, v in [(-0.16, y) for y in (-0.09, 0.0, 0.09)] + [(0.16, y) for y in (-0.09, 0.0, 0.09)] + \
            [(x, -0.13) for x in (-0.08, 0.0, 0.08)] + [(x, 0.13) for x in (-0.08, 0.0, 0.08)]:
    c = PATCH_C + PR[:, 0] * u + PR[:, 1] * v
    tang = PR[:, 1] if abs(u) > 0.1 else PR[:, 0]
    stitches += stitch_cross(core0, on_surface(core0, c, 0.0), tang, size=0.06, r=0.014, lift=0.02)
m.add("Stitches", fast_union(stitches), THREAD, role="detail", tris=350, voxel=0.01)

# ============================================================ circuiti luminosi (ciano = "Mane": scintille elettriche)
m.add("Mane", fast_union(stripes[0] + [H(union(*head_traces[0]))] + disc_cyan + electrons_c), CYAN, material="Neon",
      role="glow", tris=1500, voxel=0.013)
m.add("CircuitsMagenta", fast_union(stripes[1] + [H(union(*head_traces[1]))] + disc_magenta + electrons_m), MAGENTA,
      material="Neon", role="glow", tris=1300, voxel=0.013)
m.add("TailGlow", tail_glow_s, MAGENTA, material="Neon", role="glow", tris=400, voxel=0.014, group="Tail",
      pivot=TAIL_PIVOT)
m.add("Nebula", fast_union(rings), RING, material="Neon", role="glow", tris=700, voxel=0.012)

# ============================================================ occhi, terzo occhio, naso, bocca
irises, pupils, shines = [], [], []
for sx in (1, -1):
    irises.append(H(eye_place(ellipsoid((EA, EB, EC)).rot(0, sx * 8, 0), sx, (0, 0.03, 0))))
    look = -0.012
    pupils.append(H(eye_place(ellipsoid((0.034, 0.02, 0.036)), sx, (look, -0.014, -0.004))))
    shines.append(H(eye_place(sphere(0.019), sx, (look - 0.03, -0.022, -0.006))))
m.add("Iris", union(*irises), IRIS, role="eye", tris=400, voxel=0.01)
m.add("ThirdEye", H(third_place(ellipsoid((0.05, 0.045, 0.084)), (0, 0.032, 0))), THIRD, material="Neon", role="glow",
      tris=400, voxel=0.009)
third_slit = third_place(ellipsoid((0.013, 0.02, 0.06)), (0, -0.01, 0))
nose = union(*[ellipsoid((0.04, 0.032, 0.028), tuple(NOSE_C + (sx * 0.034, 0.0, 0.012))) for sx in (1, -1)],
             ellipsoid((0.028, 0.028, 0.026), tuple(NOSE_C + (0.0, -0.008, -0.034))), k=0.05).subtract(nostrils, k=0.008)
LIP = [(0.0, -0.09), (0.0, -0.165), (0.06, -0.205), (0.13, -0.2), (0.2, -0.16), (0.235, -0.13)]
lip_curves = []
for sx in (1, -1):
    tg = resample([np.array((sx * x, -0.6, z)) for x, z in LIP], 0.015)
    q, _ = project_many(head0, [(sx * 0.4 * t[0], -0.1, t[2]) for t in tg], [(0.0, -1.0, 0.0)] * len(tg))
    lip_curves.append(tube([tuple(p) for p in q], 0.017))
m.add("Ink", union(*pupils, H(union(third_slit, nose, *lip_curves))), INK, role="eye", tris=700, voxel=0.01)

fangs = []
for sx in (1, -1):
    b, _ = surf(head0, (sx * 0.04, -0.2, -0.19), (sx * 0.085, -0.8, -0.2))
    fangs.append(round_cone(tuple(b + np.array((0, 0.02, 0.005))), tuple(b + np.array((sx * -0.004, -0.012, -0.085))),
                            0.024, 0.005))
m.add("Shine", union(H(union(*fangs)), *shines), TOOTH, role="shine", tris=500, voxel=0.008)

# ============================================================ disco antigravita' (metallo) e propulsori
m.add("HoverDisc", union(disc, fast_union(thrusters)), DISC, material="Metal", role="detail", tris=1300, voxel=0.02)


if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
