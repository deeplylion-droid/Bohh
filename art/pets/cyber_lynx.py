"""Lince Cyber (CyberLynx) - pet del Percorso Estremo (felini super intelligenti).

Una lince dorata, snella e sicura di se', acquattata con le zampe anteriori puntate e il posteriore raccolto,
la testa alta e girata verso chi guarda con l'aria di chi ha gia' capito tutto. Davanti agli occhi un visore
olografico: fascia di vetro ciano traslucido avvolta sul muso, con linee di dati luminose, un mirino attorno
all'occhio destro e due capsule cromate alle tempie. Gli occhi socchiusi (palpebra pesante) guardano di lato,
un sopracciglio e' alzato e il ghigno storto alla Stregatto mostra una fila di dentini aguzzi.
I ciuffi delle orecchie sono antenne nere sottili con la punta luminosa; sul pelo corrono circuiti ciano
(parte Neon "Mane": il gioco ci aggancia le scintille elettriche). La coda alzata finisce in una punta
robotica cromata (gruppo "Tail") con un proiettore che proietta un piccolo tesseratto olografico.
Tocco "toy horror": la punta robotica e' fissata al pelo con graffette metalliche e l'orecchio destro e'
ricucito con punti a croce.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, capped_cone, capsule, cylinder, ellipsoid, euler, halfspace_z, look_matrix, prism,  # noqa: E402
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
        print(f"[lynx] attenzione: {len(bad)} raggi partono fuori dalla forma, es. {np.round(o[bad[0]], 3)}")
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
FUR = (218, 162, 96)          # pelo dorato-fulvo
CREAM = (252, 240, 218)       # muso, gorgiera, petto e pancia
DARK = (40, 28, 32)           # macchie, dorso delle orecchie, antenne, sopracciglia, cuciture
CHROME = (210, 218, 232)      # metallo cromato
GLOW = (30, 232, 255)         # circuiti ciano
HUD = (170, 255, 250)         # linee di dati del visore (bianco-ciano)
VISOR = (40, 205, 255)        # vetro ciano del visore
HOLO = (100, 238, 255)        # ologramma e cono di luce
EYE_W = (255, 255, 248)
IRIS = (190, 255, 60)         # occhi giallo-verdi da lince
INK = (22, 14, 24)            # pupille, bocca, naso
TOOTH = (255, 252, 244)

m = Model("CyberLynx", "pet")
rng = np.random.default_rng(31)

# ============================================================ testa (spazio locale: muso verso -Y)
HEAD_POS = np.array([0.0, -1.06, 1.94])
HS = 1.42
R_HEAD = euler(-6.0, 0.0, 13.0)       # mento un po' alto (aria di superiorita'), girata verso la camera 3/4


def H(s):
    return s.scale(HS).rotate(R_HEAD).translate(HEAD_POS)


def hp(p):
    return rot_pts(R_HEAD, np.asarray(p, dtype=np.float64) * HS) + HEAD_POS


def hv(v):
    return rot_pts(R_HEAD, v)


cran = ellipsoid((0.41, 0.38, 0.35), (0, 0.04, 0.07))
brow_ridge = [ellipsoid((0.15, 0.11, 0.08), (sx * 0.15, -0.25, 0.17)) for sx in (1, -1)]
cheeks = [ellipsoid((0.23, 0.21, 0.2), (sx * 0.2, -0.1, -0.12)) for sx in (1, -1)]
muzzle = ellipsoid((0.18, 0.17, 0.15), (0, -0.26, -0.13))
pads = [ellipsoid((0.1, 0.09, 0.085), (sx * 0.072, -0.36, -0.15)) for sx in (1, -1)]
chin = ellipsoid((0.095, 0.09, 0.075), (0, -0.29, -0.3))
bridge = capsule((0, -0.2, 0.1), (0, -0.39, -0.055), 0.07)
head0 = union(cran, *cheeks, k=0.14)
head0 = union(head0, muzzle, *brow_ridge, k=0.1)
head0 = union(head0, *pads, chin, bridge, k=0.06)

# gorgiera da lince: ciuffi a punta che scendono dalle guance (la "barba")
ruff, RUFF_AX = [], []
for sx in (1, -1):
    for bx, bz, dz, L, r0 in ((0.3, 0.0, -0.15, 0.3, 0.1), (0.31, -0.11, -0.5, 0.36, 0.115),
                              (0.27, -0.21, -0.9, 0.36, 0.11), (0.17, -0.28, -1.6, 0.3, 0.1)):
        base = np.array((sx * bx, -0.06 - 0.05 * (0.31 - bx), bz))
        d = norm((sx * 0.85, 0.15, dz))
        ruff.append(horn(base, d, L, r0, curl=(0, 0.05, -0.1), n=4, r1=0.014))
        RUFF_AX.append((base, d, L))
ruff.append(horn(np.array((0.0, -0.26, -0.3)), norm((0.0, -0.25, -1.0)), 0.2, 0.09, curl=(0, 0.05, 0), n=4, r1=0.014))
head1 = head0
ruff_solid = union(*ruff)

# occhi socchiusi (palpebra pesante, sguardo di lato)
EYE_D = {sx: norm((sx * 0.42, -0.88, 0.1)) for sx in (1, -1)}
EYE_C = {}
for sx in (1, -1):
    o = np.array((sx * 0.1, -0.12, 0.08))
    EYE_C[sx], _ = surf(head0, o, o + EYE_D[sx])


def eye_place(shape, sx, offset=(0.0, 0.0, 0.0)):
    """Coordinate locali dell'occhio: X verso il naso (-x mondo), -Y verso lo sguardo, Z in alto."""
    return shape.translate(offset).rotate(look_matrix(EYE_D[sx])).translate(EYE_C[sx])


EA, EB, EC = 0.115, 0.05, 0.085
sockets = union(*[eye_place(ellipsoid((0.125, 0.075, 0.095)), sx, (0, 0.03, 0)) for sx in (1, -1)])
head1 = head1.subtract(sockets, k=0.03)
lids = []
for sx in (1, -1):
    A, B, C = EA + 0.022, EB + 0.026, EC + 0.024

    def lid_plane(p, sx=sx, cut=0.012, slope=0.15):
        return (cut + slope * sx * p[:, 0] - p[:, 2]) / math.sqrt(1 + slope ** 2)

    lid = ellipsoid((A, B, C)).intersect(SDF(lid_plane, (-A, -B, -C), (A, B, C)))
    lids.append(eye_place(lid, sx, (0, 0.034, 0)))
head1 = union(head1, *lids, k=0.01)

# ghigno storto alla Stregatto: solco scuro fra le labbra (angolo destro piu' alto)
UPPER = [(-0.3, -0.14), (-0.22, -0.2), (-0.13, -0.232), (-0.045, -0.242), (0.0, -0.234), (0.045, -0.242),
         (0.13, -0.232), (0.22, -0.19), (0.32, -0.07)]
LOWER = [(-0.3, -0.14), (-0.22, -0.25), (-0.13, -0.315), (0.0, -0.335), (0.13, -0.315), (0.22, -0.25),
         (0.32, -0.07)]
mouth_prism = poly_xz(UPPER + LOWER[-2:0:-1], -3.0, 0.1)
_mx = np.linspace(-0.32, 0.33, 14)
_my = np.array([surf(head0, (x * 0.4, -0.05, float(np.interp(x, *np.array(UPPER).T)) - 0.03),
                     (x, -0.8, float(np.interp(x, *np.array(UPPER).T)) - 0.03))[0][1] for x in _mx])
mouth_reg = SDF(lambda p: np.maximum(mouth_prism(p), p[:, 1] - (np.interp(p[:, 0], _mx, _my) + 0.07)),
                mouth_prism.lo, mouth_prism.hi)
cut = SDF(lambda p: smax(mouth_reg(p), -(head1(p) + 0.06), 0.01), mouth_reg.lo, mouth_reg.hi)
head2 = head1.subtract(cut, k=0.012)
NOSE_C = np.array((0.0, -0.43, -0.06))
nostrils = union(*[ellipsoid((0.02, 0.03, 0.018)).rot(0, sx * 30, sx * 25).translate(NOSE_C + (sx * 0.032, -0.012, -0.015))
                   for sx in (1, -1)])


# orecchie alte e appuntite
def ear_shape():
    cone = round_cone((0, 0, -0.04), (0, 0, 0.44), 0.17, 0.018)
    slab = SDF(lambda p: np.abs(p[:, 1]) - 0.06, (-1, -1, -1), (1, 1, 1))
    cup = round_cone((0, -0.065, 0.02), (0, -0.065, 0.36), 0.11, 0.012)
    return cone.intersect(slab, k=0.02).subtract(cup, k=0.015)


EAR_R = {sx: euler(-8, sx * 16, -sx * 8) for sx in (1, -1)}
EAR_T = {sx: np.array((sx * 0.25, 0.07, 0.28)) for sx in (1, -1)}


def ear_pose(s, sx):
    return s.rotate(EAR_R[sx]).translate(EAR_T[sx])


def ear_pt(p, sx):
    return rot_pts(EAR_R[sx], p) + EAR_T[sx]


ears = [ear_pose(ear_shape(), sx) for sx in (1, -1)]
EAR_CUPS = [ear_pose(round_cone((0, -0.065, 0.02), (0, -0.065, 0.36), 0.11, 0.012), sx) for sx in (1, -1)]
EAR_TIPS = [ear_pose(ear_shape().offset(0.014).intersect(SDF(lambda p: 0.27 - 0.25 * p[:, 1] - p[:, 2], (-1, -1, -1),
                                                               (1, 1, 1)), k=0.01), sx) for sx in (1, -1)]
head2 = union(head2, *ears, k=0.04)
head_final = shrink(head2.subtract(nostrils, k=0.01))

# ============================================================ corpo (acquattato: spalle alte, gomiti fuori, posteriore raccolto)
chest = ellipsoid((0.41, 0.45, 0.45), (0, -0.45, 0.92))
ribs = ellipsoid((0.35, 0.5, 0.36), (0, 0.1, 0.87))
haunch = ellipsoid((0.42, 0.42, 0.42), (0, 0.62, 0.8))
scap = [ell((sx * 0.25, -0.47, 1.26), (0.15, 0.2, 0.24), axis=(0, -0.3, 1.0)) for sx in (1, -1)]
torso = union(union(chest, ribs, k=0.3), haunch, k=0.28)
torso = union(torso, *scap, k=0.15)
NECK = [(0, -0.55, 1.15), (0, -0.8, 1.45), (0, -0.98, 1.68)]
neck = tube(NECK, [0.36, 0.33, 0.3], k=0.08)

FRONT = {sx: dict(sh=np.array([sx * 0.3, -0.55, 0.95]), el=np.array([sx * 0.42, -0.42, 0.46]),
                  wr=np.array([sx * 0.4, -0.74, 0.15]), paw=np.array([sx * 0.4, -0.86, 0.1])) for sx in (1, -1)}
HIND = {sx: dict(hip=np.array([sx * 0.32, 0.6, 0.88]), knee=np.array([sx * 0.47, 0.2, 0.48]),
                 hock=np.array([sx * 0.43, 0.88, 0.2]), paw=np.array([sx * 0.43, 0.56, 0.09])) for sx in (1, -1)}
leg_parts = []
for sx, L in FRONT.items():
    sh, el, wr, paw = L["sh"], L["el"], L["wr"], L["paw"]
    leg_parts += [
        ell(mix(sh, el, 0.4) + np.array([sx * 0.03, 0.0, 0.0]), (0.23, 0.25, 0.34), axis=el - sh),
        round_cone(sh, el, 0.22, 0.16),
        round_cone(el, wr, 0.16, 0.12),
        ell(mix(el, wr, 0.3), (0.15, 0.16, 0.22), axis=wr - el),
        round_cone(wr, paw, 0.12, 0.13),
        ellipsoid((0.2, 0.25, 0.105), tuple(paw + np.array([0, -0.05, 0.0]))),
    ]
    for dx in (-0.12, -0.04, 0.04, 0.12):
        leg_parts.append(sphere(0.068, tuple(paw + np.array([dx, -0.23 + 0.6 * dx * dx, -0.025]))))
for sx, L in HIND.items():
    hip, knee, hock, paw = L["hip"], L["knee"], L["hock"], L["paw"]
    leg_parts += [
        ell(mix(hip, knee, 0.45) + np.array([sx * 0.06, 0.04, 0.0]), (0.27, 0.32, 0.44), axis=knee - hip),
        round_cone(hip, knee, 0.26, 0.16),
        round_cone(knee, hock, 0.15, 0.1),
        ell(mix(knee, hock, 0.35) + np.array([0, 0.03, 0.03]), (0.14, 0.15, 0.24), axis=hock - knee),
        round_cone(hock, paw, 0.1, 0.11),
        ellipsoid((0.18, 0.23, 0.1), tuple(paw + np.array([0, -0.05, 0.0]))),
    ]
    for dx in (-0.11, -0.037, 0.037, 0.11):
        leg_parts.append(sphere(0.062, tuple(paw + np.array([dx, -0.2 + 0.6 * dx * dx, -0.02]))))
legs = union(*leg_parts, k=0.06)

core = union(torso, neck, k=0.18)
core = union(core, H(head_final), k=0.1)
core = union(core, legs, k=0.08)
core0 = shrink(core.intersect(halfspace_z(0.0, above=True)))
body_only = shrink(union(union(torso, neck, k=0.18), legs, k=0.08).intersect(halfspace_z(0.0, above=True)))

# ============================================================ coda alzata (gruppo "Tail") con punta robotica
TAIL_PTS = bezier((0.0, 0.9, 0.98), (0.0, 1.4, 1.05), (0.0, 1.68, 1.5), (0.0, 1.55, 1.95), 16)
TAIL_PIVOT = (0.0, 0.92, 0.98)
NT = len(TAIL_PTS) - 1
FUR_END = 9                                   # da qui in poi la coda e' robotica
tail_r = [0.15 - 0.03 * (i / NT) for i in range(NT + 1)]
tail_fur = tube(TAIL_PTS[:FUR_END + 1], tail_r[:FUR_END + 1])


def tail_frame(i):
    p = np.asarray(TAIL_PTS[i], dtype=np.float64)
    t = norm(np.asarray(TAIL_PTS[min(i + 1, NT)]) - np.asarray(TAIL_PTS[max(i - 1, 0)]))
    return p, t


tech, tail_glow = [], []
cuff_p, cuff_t = tail_frame(FUR_END)
tech.append(cylinder(cuff_p - cuff_t * 0.06, cuff_p + cuff_t * 0.06, 0.16, round=0.025))       # ghiera
for i in range(FUR_END + 1, NT):
    p, t = tail_frame(i)
    tech.append(cylinder(p - t * 0.032, p + t * 0.032, 0.112, round=0.016))                    # anelli
tech.append(tube(TAIL_PTS[FUR_END:], 0.075))                                                     # anima
TIP, TIP_T = tail_frame(NT)
HOLO_UP = norm((0.0, -0.12, 1.0))
tech.append(cylinder(TIP - TIP_T * 0.05, TIP + HOLO_UP * 0.07, 0.13, round=0.02))                 # proiettore
proj_cup = cylinder(TIP + HOLO_UP * 0.035, TIP + HOLO_UP * 0.14, 0.09)
tech_shape = fast_union(tech, k=0.01).subtract(proj_cup, k=0.01)

# graffette metalliche che tengono la punta robotica attaccata al pelo
staples = []
sp_p, sp_t = tail_frame(FUR_END - 1)
s1 = norm(np.cross(sp_t, (1.0, 0.0, 0.0)))
s2 = np.cross(sp_t, s1)
for k_ in range(6):
    a = 2 * math.pi * k_ / 6 + 0.3
    rad = s1 * math.cos(a) + s2 * math.sin(a)
    c = sp_p + rad * (tail_r[FUR_END - 1] + 0.006) + sp_t * 0.06
    a0, b0 = c - sp_t * 0.08, c + sp_t * 0.05
    staples += [capsule(tuple(a0), tuple(b0), 0.017),
                capsule(tuple(a0), tuple(a0 - rad * 0.035), 0.015),
                capsule(tuple(b0), tuple(b0 - rad * 0.035), 0.015)]
m_tail_tech = union(tech_shape, fast_union(staples))

# ologramma: cono di luce e tesseratto (due cubi annidati collegati agli spigoli)
LENS = TIP + HOLO_UP * 0.1
CUBE_C = TIP + HOLO_UP * 0.62
_e3 = norm((1.0, 1.0, 1.0))
_e1 = norm((1.0, -1.0, 0.0))
R_CUBE = (euler(0.0, 0.0, 20.0) @ np.stack([_e1, np.cross(_e3, _e1), _e3])).astype(np.float64)  # cubo su uno spigolo


def cube_edges(size):
    h = size / 2
    corners = [np.array((x, y, z)) * h for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    out = []
    for i, a in enumerate(corners):
        for b in corners[i + 1:]:
            if np.sum(np.abs(a - b) > 1e-6) == 1:
                out.append((a, b))
    return corners, out


def cp(a):
    return tuple(rot_pts(R_CUBE, a) + CUBE_C)


holo = [cylinder(LENS - HOLO_UP * 0.03, LENS + HOLO_UP * 0.012, 0.08)] + tail_glow
outer_c, outer_e = cube_edges(0.42)
inner_c, inner_e = cube_edges(0.2)
holo += [capsule(cp(a), cp(b), 0.026) for a, b in outer_e]
holo += [capsule(cp(a), cp(b), 0.023) for a, b in inner_e]
beam = capped_cone(tuple(LENS), tuple(CUBE_C - HOLO_UP * 0.13), 0.06, 0.2, round=0.01)

# ============================================================ visore olografico (vetro ciano avvolto sul muso)
VC = np.array([0.0, -0.02, 0.08])
V_OUT, V_IN = (0.5, 0.49, 0.62), (0.472, 0.462, 0.592)
ZC = 0.088


def v_half(x):
    return 0.096 - 0.045 * np.clip(np.abs(x) / 0.5, 0, 1) ** 2


def v_notch(x):
    return 0.045 * np.maximum(0.0, 1.0 - np.abs(x) / 0.1)


def visor_band(p):
    x, z = p[:, 0], p[:, 2]
    h = v_half(x)
    return np.maximum(np.maximum(z - (ZC + h), (ZC - h + v_notch(x)) - z), p[:, 1])


band = SDF(visor_band, (-0.6, -0.6, -0.1), (0.6, 0.1, 0.25))
visor_local = ellipsoid(V_OUT, tuple(VC)).subtract(ellipsoid(V_IN, tuple(VC))).intersect(band, k=0.01)


def visor_pt(x, z, lift=0.0):
    """Punto sulla faccia esterna del visore (coordinate locali della testa)."""
    a, b, c = V_OUT
    u = 1 - (x / a) ** 2 - ((z - VC[2]) / c) ** 2
    y = VC[1] - b * math.sqrt(max(u, 1e-6))
    p = np.array([x, y, z])
    n = norm(np.array([x / a ** 2, (y - VC[1]) / b ** 2, (z - VC[2]) / c ** 2]))
    return p + n * lift


def visor_line(x0, x1, z, r=0.012, n=6):
    return tube([tuple(visor_pt(x, z, 0.004)) for x in np.linspace(x0, x1, n)], r)


hud = []
for x0, x1, z in ((0.33, 0.46, 0.135), (0.35, 0.45, 0.098), (0.33, 0.43, 0.061), (0.37, 0.45, 0.025)):
    hud.append(visor_line(x0, x1, z, r=0.015, n=5))
for x0, x1, z in ((-0.47, -0.4, 0.12), (-0.47, -0.42, 0.08)):
    hud.append(visor_line(x0, x1, z, r=0.015, n=4))
for x, hgt in ((-0.054, 0.03), (-0.018, 0.055), (0.018, 0.04), (0.054, 0.07)):   # grafico a barre sopra il naso
    z0 = 0.142
    hud.append(tube([tuple(visor_pt(x, z0 - hgt / 2, 0.004)), tuple(visor_pt(x, z0 + hgt / 2, 0.004))], 0.016))
ec_r = EYE_C[-1]
ret_c = np.array([ec_r[0] - 0.01, 0.0, ec_r[2] - 0.004])      # mirino attorno all'occhio sinistro
ret = [tuple(visor_pt(ret_c[0] + 0.098 * math.cos(a), ret_c[2] + 0.098 * math.sin(a), 0.004))
       for a in np.linspace(0, 2 * math.pi, 25)]
hud.append(tube(ret, 0.012))
for a in (0, 90, 180, 270):
    ar = math.radians(a)
    p0 = visor_pt(ret_c[0] + 0.08 * math.cos(ar), ret_c[2] + 0.08 * math.sin(ar), 0.004)
    p1 = visor_pt(ret_c[0] + 0.125 * math.cos(ar), ret_c[2] + 0.125 * math.sin(ar), 0.004)
    hud.append(capsule(tuple(p0), tuple(p1), 0.013))

# capsule cromate alle tempie che reggono il visore + ponticello sul naso
chrome_head = []
for sx in (1, -1):
    pc = np.array((sx * 0.45, -0.07, 0.085))
    chrome_head.append(cylinder(tuple(pc - np.array((sx * 0.1, 0, 0))), tuple(pc + np.array((sx * 0.035, 0, 0))), 0.088,
                                round=0.02))
    chrome_head.append(sphere(0.052, tuple(pc + np.array((sx * 0.045, 0, 0)))))
rim_pts = [tuple(visor_pt(x, ZC + float(v_half(np.array([x]))[0]) - 0.004, -0.008)) for x in np.linspace(-0.47, 0.47, 25)]
chrome_head.append(tube(rim_pts, 0.02))                                   # bordo superiore cromato del visore
clip_top = visor_pt(0.0, ZC - 0.096 + 0.045 + 0.02, -0.015)
chrome_head.append(capsule(tuple(clip_top), (0.0, -0.33, 0.0), 0.024))

# ciuffi-antenna sulle punte delle orecchie con la punta luminosa (+ anellino cromato alla base)
antennas, ant_tips = [], []
for sx in (1, -1):
    tip = ear_pt(np.array((0.0, 0.0, 0.42)), sx)
    d = norm(ear_pt(np.array((0.0, 0.0, 1.0)), sx) - ear_pt(np.array((0.0, 0.0, 0.0)), sx))
    curl = np.array((sx * 0.12, 0.05, 0.0))
    antennas.append(horn(tip - d * 0.06, d, 0.3, 0.034, curl=tuple(curl), n=5, r1=0.013))
    end = tip - d * 0.06 + d * 0.3 + curl * 0.3
    ant_tips.append(sphere(0.056, tuple(end)))
    ant_tips.append(torus(0.052, 0.012).rotate(orient(d)).translate(tuple(end - d * 0.1)))
    chrome_head.append(torus(0.038, 0.014).rotate(orient(d)).translate(tuple(tip + d * 0.0)))

# ============================================================ parti: pelle
HEAD_ZONE = H(ellipsoid((0.66, 0.62, 0.7), (0.0, -0.05, 0.12)))
m.add("Body", core0.subtract(HEAD_ZONE.offset(-0.03)), FUR, tris=2400, voxel=0.0427)
m.add("Head", core0.intersect(HEAD_ZONE.offset(0.03)), FUR, tris=2800, voxel=0.0303)
m.add("Tail", tail_fur, FUR, tris=350, voxel=0.0327, group="Tail", pivot=TAIL_PIVOT)

# ============================================================ pelo chiaro: gorgiera (ciuffi pieni), muso, pettorina, orecchie interne
pad_solid = union(*[ellipsoid((0.106, 0.094, 0.09), (sx * 0.074, -0.373, -0.15)) for sx in (1, -1)],
                  ellipsoid((0.096, 0.092, 0.076), (0, -0.303, -0.302)), k=0.03)
pad_solid = pad_solid.subtract(nostrils.offset(0.01)).subtract(mouth_reg.intersect(head1.offset(0.05)), k=0.006)
bib = ell((0, -0.86, 1.12), (0.26, 0.24, 0.34), axis=(0, -0.45, 1.0))
chest_tufts = [ell((0.0, -0.9, 1.08), (0.25, 0.13, 0.31), axis=(0, -0.35, 1.0))]
for bx, bz, L in ((0.0, 0.98, 0.3), (0.13, 1.03, 0.25), (-0.13, 1.03, 0.25)):
    b, nb = surf(body_only, (bx * 0.5, -0.6, bz), (bx, -1.5, bz))
    chest_tufts.append(horn(b - nb * 0.06, norm(nb * 0.5 + np.array((bx * 0.6, 0.0, -1.0))), L, 0.09,
                            curl=(0, 0.1, 0), n=4, r1=0.018))
chest_fluff = fast_union(chest_tufts, k=0.03).subtract(body_only.offset(-0.08))
ear_fluff = union(*[ear_pose(round_cone((0, 0.0, 0.03), (0, 0.0, 0.3), 0.09, 0.014), sx) for sx in (1, -1)])
cream = union(H(ruff_solid.subtract(head0.offset(-0.08))), H(pad_solid.subtract(head0.offset(-0.09))), chest_fluff,
              H(ear_fluff))
m.add("Cream", cream, CREAM, role="detail", tris=1200, voxel=0.0377)

# ============================================================ segni scuri dipinti: macchie e dorso delle orecchie
spots = []
tries = 0
while len(spots) < 13 and tries < 900:
    tries += 1
    sx = rng.choice((1, -1))
    y, z = rng.uniform(-0.4, 0.8), rng.uniform(0.35, 1.2)
    p, nr = surf(body_only, (0.0, y, max(z, 0.75)), (sx * 1.0, y, z))
    pp = p[None, :].astype(np.float32)
    if p[2] < 0.12 or bib(pp)[0] < 0.08 or any(np.linalg.norm(p - q) < 0.24 for q in spots):
        continue
    spots.append(p)
spot_discs = []
for p in spots:
    nr = grad(body_only, p)
    r = rng.uniform(0.065, 0.09)
    spot_discs.append(ellipsoid((r, r * rng.uniform(0.7, 1.0), 0.05)).rotate(orient(nr, side=(0.0, 1.0, 0.0)))
                      .translate(tuple(p - nr * 0.032)))
tips = []
for i in (0, 1, 2, 4, 5, 6):
    base, d, L = RUFF_AX[i]
    r0 = (0.1, 0.115, 0.11, 0.1)[i % 4]
    tufts_i = horn(base, d, L, r0, curl=(0, 0.05, -0.1), n=6, r1=0.014)
    cut_c = base + d * L * 0.68 + np.array((0, 0.05, -0.1)) * L * 0.46
    tips.append(tufts_i.offset(0.008).intersect(SDF(lambda p, c=cut_c, d=d: (c - p) @ d.astype(np.float32),
                                                    cut_c - 1, cut_c + 1), k=0.01))
marks = union(fast_union(spot_discs), H(union(*EAR_TIPS)), H(fast_union(tips)))
m.add("Marks", marks, DARK, role="detail", tris=600, voxel=0.0321)

# ============================================================ ciuffi-antenna, sopracciglia, cuciture (dettagli sottili scuri)
brows = []
for sx, pts3, rr in ((1, ((0.09, -0.33, 0.25), (0.17, -0.31, 0.33), (0.28, -0.22, 0.32)), (0.02, 0.032, 0.016)),
                     (-1, ((-0.07, -0.33, 0.205), (-0.17, -0.31, 0.215), (-0.28, -0.22, 0.225)), (0.026, 0.03, 0.016))):
    q, _ = project_many(head0, [(0, -0.05, 0.1)] * 3, [np.array(v) - np.array((0, -0.05, 0.1)) for v in pts3])
    brows.append(tube([tuple(x) for x in q], list(rr)))
stitches = []                                   # orecchio destro ricucito: punti a croce sul bordo esterno
ear_axis = hv(ear_pt((0, 0, 1), 1) - ear_pt((0, 0, 0), 1))
for z in (0.05, 0.14, 0.23):
    wp = hp(ear_pt(np.array((0.1, -0.05, z)), 1))
    stitches += stitch_cross(core0, on_surface(core0, wp, 0.0), ear_axis, size=0.07, r=0.016)
m.add("Tufts", union(H(union(*brows, *antennas)), fast_union(stitches)), DARK, role="detail", tris=600, voxel=0.0178)

# ============================================================ visore, cromature, linee di dati
m.add("Visor", H(visor_local), VISOR, material="Glass", role="detail", tris=550, voxel=0.0266, transparency=0.55)

# chip luminoso sul petto (cornice cromata esagonale)
chip_p, chip_n = surf(body_only, (0.0, -0.6, 1.0), (0.0, -1.6, 1.15))
CH_R = orient(chip_n, side=(1.0, 0.0, 0.0))


def hexagon(r, h, round_=0.01):
    pts = [(r * math.cos(math.radians(60 * i + 30)), r * math.sin(math.radians(60 * i + 30))) for i in range(6)]

    return prism(pts, -h, h, round=round_)


chest_frame = hexagon(0.11, 0.03).subtract(hexagon(0.075, 0.06, 0.0)).rotate(CH_R).translate(tuple(chip_p + chip_n * 0.005))
chest_core = hexagon(0.078, 0.022).rotate(CH_R).translate(tuple(chip_p + chip_n * 0.004))
m.add("Chrome", union(H(union(*chrome_head)), chest_frame), CHROME, material="Metal", role="detail", tris=800,
      voxel=0.0235)
m.add("VisorGlow", union(H(union(fast_union(hud), *ant_tips)), chest_core), HUD, material="Neon", role="glow",
      tris=900, voxel=0.0177)

# ============================================================ circuiti luminosi sul pelo (parte Neon "Mane")


def flank_origin(sx):
    def f(y, z):
        return (0.0, y, z), (sx * 1.0, y, z)
    return f


def pad_at(p, nr, r=0.05):
    return cylinder(tuple(p - nr * 0.03), tuple(p + nr * 0.014), r, round=0.012)


FLANK = [[(-0.48, 1.18), (-0.25, 1.18), (-0.12, 1.05), (0.3, 1.05), (0.42, 0.94), (0.58, 0.94)]]
circuits = []
CR = 0.03
for sx in (1, -1):
    for tr in FLANK:
        pts, nrs = surface_line(body_only, flank_origin(sx), tr)
        circuits.append(tube([tuple(p) for p in pts], CR))
        circuits += [pad_at(pts[0], nrs[0]), pad_at(pts[-1], nrs[-1])]
    # zampa anteriore: linea sul davanti fino al bracciale luminoso del polso
    L = FRONT[sx]
    ax_pts = [mix(L["sh"], L["el"], 0.5), L["el"], mix(L["el"], L["wr"], 0.72)]
    targets = [p + np.array((sx * 0.45, -0.6, 0.0)) for p in ax_pts]
    q, _ = project_many(body_only, ax_pts, [t - a for t, a in zip(targets, ax_pts)])
    dense = resample(q, 0.03)
    nn = grad_many(body_only, dense)
    q2, n2 = project_many(body_only, [p - nr * 0.08 for p, nr in zip(dense, nn)], list(nn))
    circuits.append(tube([tuple(p) for p in q2], CR))
    circuits.append(pad_at(q2[0], n2[0]))
    c = mix(L["el"], L["wr"], 0.8)
    circuits.append(torus(0.13, 0.03).rotate(orient(L["wr"] - L["el"])).translate(tuple(c)))
    # zampa posteriore: linea sulla coscia e bracciale al garretto
    L = HIND[sx]
    ax_pts = [mix(L["hip"], L["knee"], t) for t in (0.15, 0.55, 0.92)]
    targets = [p + np.array((sx * 0.8, 0.0, 0.1)) for p in ax_pts]
    q, _ = project_many(body_only, ax_pts, [t - a for t, a in zip(targets, ax_pts)])
    dense = resample(q, 0.03)
    nn = grad_many(body_only, dense)
    q2, n2 = project_many(body_only, [p - nr * 0.08 for p, nr in zip(dense, nn)], list(nn))
    circuits.append(tube([tuple(p) for p in q2], CR))
    circuits += [pad_at(q2[0], n2[0]), pad_at(q2[-1], n2[-1])]
# fronte: chip esagonale sopra il visore e tre tracce verso la nuca
chip_hp, chip_hn = surf(head0, (0, 0, 0.0), (0, -0.25, 0.42))
head_circ = [cylinder(tuple(chip_hp - chip_hn * 0.03), tuple(chip_hp + chip_hn * 0.012), 0.05, round=0.008)]
for tr in (((0.0, -0.2, 0.4), (0.0, 0.05, 0.45), (0.0, 0.26, 0.38)),
           ((0.03, -0.2, 0.4), (0.11, -0.1, 0.42), (0.14, 0.1, 0.42)),
           ((-0.03, -0.2, 0.4), (-0.11, -0.1, 0.42), (-0.14, 0.1, 0.42))):
    tg = resample([np.array(p) for p in tr], 0.025)
    q, nq = project_many(head0, [(0.0, 0.0, 0.0)] * len(tg), [np.asarray(t) for t in tg])
    head_circ.append(tube([tuple(p) for p in q], 0.02))
    head_circ.append(cylinder(tuple(q[-1] - nq[-1] * 0.03), tuple(q[-1] + nq[-1] * 0.01), 0.038, round=0.008))
circuits.append(H(union(*head_circ)))
m.add("Mane", fast_union(circuits), GLOW, material="Neon", role="glow", tris=1300, voxel=0.0237)

# ============================================================ occhi, pupille, bocca, naso
whites, irises, slits, shines = [], [], [], []
for sx in (1, -1):
    whites.append(H(eye_place(ellipsoid((EA, EB, EC)).rot(0, sx * 10, 0), sx, (0, 0.03, 0))))
    look = -0.024        # pupille girate verso la camera (+x mondo = -X locale)
    irises.append(H(eye_place(ellipsoid((0.066, 0.03, 0.07)), sx, (look, 0.004, -0.008))))
    slits.append(H(eye_place(ellipsoid((0.02, 0.02, 0.056)), sx, (look, -0.016, -0.008))))
    shines.append(H(eye_place(sphere(0.02), sx, (look - 0.027, -0.026, -0.014))))
m.add("EyeWhite", union(*whites), EYE_W, role="eye", tris=400, voxel=0.019)
m.add("Iris", union(*irises), IRIS, role="eye", tris=400, voxel=0.0125)
mouth = paint(head2, mouth_reg.offset(0.012), out=0.012, inn=0.03)
nose = union(*[ellipsoid((0.034, 0.03, 0.026), tuple(NOSE_C + (sx * 0.03, 0.0, 0.012))) for sx in (1, -1)],
             ellipsoid((0.024, 0.026, 0.024), tuple(NOSE_C + (0.0, -0.008, -0.032))), k=0.045).subtract(nostrils, k=0.008)
m.add("Ink", union(H(union(mouth, nose)), *slits), INK, role="eye", tris=700, voxel=0.0172)

# dentini aguzzi lungo il labbro superiore (e qualcuno sotto) + riflessi negli occhi
teeth = []
ux, uz = np.array(UPPER).T
lx, lz = np.array(LOWER).T
for x in np.linspace(-0.24, 0.28, 11):
    z = float(np.interp(x, ux, uz))
    b, _ = surf(head1, (x * 0.5, -0.1, z), (x, -0.6, z + 0.01))
    teeth.append(round_cone(tuple(b + np.array((0, 0.024, 0.006))), tuple(b + np.array((0, 0.004, -0.05))), 0.019, 0.004))
for x in np.linspace(-0.17, 0.2, 5):
    z = float(np.interp(x, lx, lz))
    b, _ = surf(head1, (x * 0.5, -0.1, z), (x, -0.6, z))
    teeth.append(round_cone(tuple(b + np.array((0, 0.024, -0.004))), tuple(b + np.array((0, 0.004, 0.036))), 0.016, 0.004))
m.add("Shine", union(H(union(*teeth)), *shines), TOOTH, role="shine", tris=650, voxel=0.0117)

# ============================================================ coda robotica e ologramma (gruppo "Tail")
m.add("TailTech", m_tail_tech, CHROME, material="Metal", role="detail", tris=650, voxel=0.0216, group="Tail",
      pivot=TAIL_PIVOT)
m.add("Hologram", fast_union(holo), HOLO, material="Neon", role="glow", tris=1100, voxel=0.0207, group="Tail",
      pivot=TAIL_PIVOT)
m.add("HoloBeam", beam, HOLO, material="Glass", role="detail", tris=150, voxel=0.0356, transparency=0.6,
      group="Tail", pivot=TAIL_PIVOT)


if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
