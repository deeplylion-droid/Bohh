"""Pantera Psichica (PsychicPanther) - pet del Percorso Estremo (felini super intelligenti).

Una pantera nera dai riflessi viola, seduta fiera come una statua: zampe anteriori dritte e unite, petto in fuori,
mento alto e la coda avvolta attorno alle zampe. La calotta del cranio non c'e' piu': al suo posto una cupola di
vetro trasparente mostra un cervello rosa che brilla, tutto circonvoluzioni. Occhi viola intensi e luminosi sotto
palpebre severe, due zanne bianche che spuntano dal muso chiuso. Dalla schiena salgono lingue di aura viola e a terra
brilla un sigillo psichico (parte Neon "Nebula": il gioco ci aggancia la nebulosa viola-blu); attorno fluttuano tre
sfere psichiche con un anello ciascuna (parte Neon "Aura": scintille rosa-viola) dentro gusci di vetro viola.
Tocco "toy horror": la cupola e' cucita alla testa con grossi punti a croce rosa, tutto attorno.
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
        print(f"[panther] attenzione: {len(bad)} raggi partono fuori dalla forma, es. {np.round(o[bad[0]], 3)}")
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


def wisp(base, d, L, r0, curl, wiggle=0.0, n=7, r1=0.014, phase=0.0):
    """Lingua di energia: tubo che si assottiglia fino a una punta, con una curva a S (wiggle)."""
    base, d, c = np.asarray(base, float), norm(d), np.asarray(curl, float)
    side = np.cross(d, c)
    side = norm(side) if np.linalg.norm(side) > 1e-6 else norm(np.cross(d, (0.0, 0.0, 1.0)) + 1e-3)
    pts, radii = [], []
    for i in range(n):
        t = i / (n - 1)
        p = base + d * L * t + c * L * t * t + side * wiggle * L * math.sin(t * math.pi * 1.6 + phase) * t
        pts.append(tuple(p))
        radii.append(max(r0 * (1 - t) ** 0.85, r1))
    return tube(pts, radii)


def catmull(points, n=6):
    """Curva liscia (Catmull-Rom) che passa per tutti i punti."""
    P = [np.asarray(p, dtype=np.float64) for p in points]
    P = [2 * P[0] - P[1]] + P + [2 * P[-1] - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for j in range(n):
            t = j / n
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return [tuple(float(x) for x in q) for q in out]


# ============================================================ colori
FUR = (36, 30, 50)          # pelo nero con riflessi viola
ACCENT = (74, 60, 104)      # muso, mento e interno delle orecchie grigio-viola scuro
GLASS = (226, 214, 255)     # cupola di vetro
BRAIN = (255, 92, 200)      # cervello rosa luminoso
EYE_GLOW = (196, 110, 255)  # occhi viola accesi
PUPIL = (18, 6, 30)
THREAD = (255, 130, 206)    # filo dei punti attorno alla cupola (e naso)
AURA = (150, 64, 255)       # aura viola
ORB = (255, 150, 250)       # nucleo delle sfere psichiche
ORB_GLASS = (196, 130, 255)
TOOTH = (255, 252, 246)

m = Model("PsychicPanther", "pet")
rng = np.random.default_rng(53)

# ============================================================ testa (spazio locale: muso verso -Y)
HEAD_POS = np.array([0.0, -0.5, 2.2])
HS = 1.24
R_HEAD = euler(-8.0, 0.0, 12.0)       # mento alto, fiera, girata verso la camera 3/4


def H(s):
    return s.scale(HS).rotate(R_HEAD).translate(HEAD_POS)


def hp(p):
    return rot_pts(R_HEAD, np.asarray(p, dtype=np.float64) * HS) + HEAD_POS


def hv(v):
    return rot_pts(R_HEAD, v)


cran = ellipsoid((0.4, 0.38, 0.34), (0, 0.04, 0.05))
brow_ridge = [ellipsoid((0.15, 0.11, 0.08), (sx * 0.15, -0.25, 0.13)) for sx in (1, -1)]
cheeks = [ellipsoid((0.22, 0.2, 0.19), (sx * 0.19, -0.1, -0.11)) for sx in (1, -1)]
muzzle = ellipsoid((0.17, 0.19, 0.14), (0, -0.28, -0.12))
pads = [ellipsoid((0.095, 0.09, 0.08), (sx * 0.066, -0.38, -0.145)) for sx in (1, -1)]
chin = ellipsoid((0.08, 0.08, 0.065), (0, -0.31, -0.255))
bridge = capsule((0, -0.2, 0.08), (0, -0.41, -0.045), 0.07)
head0 = union(cran, *cheeks, k=0.14)
head0 = union(head0, muzzle, *brow_ridge, k=0.1)
head0 = union(head0, *pads, chin, bridge, k=0.06)

# calotta cranica tagliata: al suo posto la cupola di vetro col cervello
CUT_Z = 0.19
DOME = ellipsoid((0.37, 0.355, 0.37), (0, 0.04, CUT_Z)).intersect(halfspace_z(CUT_Z - 0.03, above=True))
skull = head0.intersect(halfspace_z(CUT_Z + 0.01, above=False), k=0.02)

# occhi viola intensi (palpebra superiore inclinata verso il naso, inferiore che stringe)
EYE_D = {sx: norm((sx * 0.43, -0.88, 0.06)) for sx in (1, -1)}
EYE_C = {}
for sx in (1, -1):
    o = np.array((sx * 0.1, -0.12, 0.04))
    EYE_C[sx], _ = surf(head0, o, o + EYE_D[sx])


def eye_place(shape, sx, offset=(0.0, 0.0, 0.0)):
    """Coordinate locali dell'occhio: X verso il naso (-x mondo), -Y verso lo sguardo, Z in alto."""
    return shape.translate(offset).rotate(look_matrix(EYE_D[sx])).translate(EYE_C[sx])


EA, EB, EC = 0.104, 0.048, 0.072
head1 = skull.subtract(union(*[eye_place(ellipsoid((0.116, 0.074, 0.086)), sx, (0, 0.03, 0)) for sx in (1, -1)]),
                       k=0.03)
lids = []
for sx in (1, -1):
    A, B, C = EA + 0.022, EB + 0.026, EC + 0.024

    def top_plane(p, sx=sx):
        return (0.03 - 0.42 * sx * p[:, 0] - p[:, 2]) / math.sqrt(1 + 0.42 ** 2)

    def low_plane(p):
        return p[:, 2] + 0.046

    lid = ellipsoid((A, B, C)).intersect(SDF(top_plane, (-A, -B, -C), (A, B, C)))
    low = ellipsoid((A, B, C)).intersect(SDF(low_plane, (-A, -B, -C), (A, B, C)))
    lids += [eye_place(lid, sx, (0, 0.034, 0)), eye_place(low, sx, (0, 0.036, 0))]
head1 = union(head1, *lids, k=0.01)

# bocca chiusa: solco del labbro (la forma lo fa leggere anche sul nero)
NOSE_C = np.array((0.0, -0.462, -0.05))
LIP = [(0.0, -0.09), (0.0, -0.16), (0.05, -0.195), (0.11, -0.19), (0.17, -0.16), (0.205, -0.125)]
lip_tubes = []
for sx in (1, -1):
    tg = resample([np.array((sx * x, -0.6, z)) for x, z in LIP], 0.015)
    q, _ = project_many(head0, [(sx * 0.4 * t[0], -0.1, t[2]) for t in tg], [(0.0, -1.0, 0.0)] * len(tg))
    lip_tubes.append(tube([tuple(p) for p in q], 0.016))
head1 = head1.subtract(union(*lip_tubes), k=0.01)
nostrils = union(*[ellipsoid((0.018, 0.026, 0.016)).rot(0, sx * 30, sx * 25).translate(NOSE_C + (sx * 0.03, -0.012, -0.014))
                   for sx in (1, -1)])


# orecchie tonde e piccole, ai lati della cupola
def ear_shape():
    cone = round_cone((0, 0, -0.03), (0, 0, 0.17), 0.15, 0.07)
    slab = SDF(lambda p: np.abs(p[:, 1]) - 0.055, (-1, -1, -1), (1, 1, 1))
    cup = round_cone((0, -0.06, 0.0), (0, -0.06, 0.15), 0.095, 0.042)
    return cone.intersect(slab, k=0.025).subtract(cup, k=0.02)


EAR_R = {sx: euler(-6, sx * 42, -sx * 10) for sx in (1, -1)}
EAR_T = {sx: np.array((sx * 0.33, 0.07, 0.16)) for sx in (1, -1)}


def ear_pose(s, sx):
    return s.rotate(EAR_R[sx]).translate(EAR_T[sx])


ears = [ear_pose(ear_shape(), sx) for sx in (1, -1)]
ear_fluff = union(*[ear_pose(round_cone((0, 0.0, 0.02), (0, 0.0, 0.14), 0.08, 0.035), sx) for sx in (1, -1)])
head2 = union(head1, *ears, k=0.04)
head_final = shrink(head2.subtract(nostrils, k=0.01))

# ============================================================ corpo seduto, fiero (posa da statua)
hips = ellipsoid((0.44, 0.44, 0.44), (0, 0.32, 0.5))
belly = ell((0, 0.05, 0.92), (0.38, 0.38, 0.52), axis=(0, 0.25, 1))
chest = ell((0, -0.2, 1.28), (0.4, 0.38, 0.44), axis=(0, 0.2, 1))
scap = [ell((sx * 0.24, -0.16, 1.52), (0.14, 0.18, 0.22), axis=(0, 0.3, 1)) for sx in (1, -1)]
torso = union(union(hips, belly, k=0.3), chest, k=0.3)
torso = union(torso, *scap, k=0.15)
haunches = [ell((sx * 0.34, 0.2, 0.42), (0.27, 0.46, 0.38), axis=(0, -1, 0.35)) for sx in (1, -1)]
NECK = [(0, -0.2, 1.5), (0, -0.33, 1.8), (0, -0.42, 2.0)]
neck = tube(NECK, [0.3, 0.27, 0.25], k=0.08)
FRONT = {sx: dict(sh=np.array([sx * 0.22, -0.28, 1.32]), el=np.array([sx * 0.235, -0.33, 0.8]),
                  wr=np.array([sx * 0.215, -0.47, 0.2]), paw=np.array([sx * 0.205, -0.52, 0.085])) for sx in (1, -1)}
leg_parts = list(haunches)
for sx, L in FRONT.items():
    sh, el, wr, paw = L["sh"], L["el"], L["wr"], L["paw"]
    leg_parts += [
        ell(mix(sh, el, 0.45) + np.array([sx * 0.02, 0.0, 0.0]), (0.17, 0.19, 0.32), axis=el - sh),
        round_cone(sh, el, 0.17, 0.12),
        round_cone(el, wr, 0.12, 0.095),
        round_cone(wr, paw, 0.095, 0.1),
        ellipsoid((0.145, 0.19, 0.085), tuple(paw + np.array([0, -0.04, 0.0]))),
    ]
    for dx in (-0.09, -0.03, 0.03, 0.09):
        leg_parts.append(sphere(0.052, tuple(paw + np.array([dx, -0.17 + 0.6 * dx * dx, -0.02]))))
for sx in (1, -1):    # zampe posteriori appoggiate davanti alle cosce
    hf = np.array([sx * 0.4, -0.12, 0.075])
    leg_parts += [ellipsoid((0.14, 0.3, 0.078), tuple(hf)),
                  round_cone(tuple(hf + (0, 0.22, 0.02)), (sx * 0.38, 0.32, 0.3), 0.1, 0.16)]
    for dx in (-0.08, -0.027, 0.027, 0.08):
        leg_parts.append(sphere(0.05, tuple(hf + np.array([dx, -0.27 + 0.6 * dx * dx, -0.012]))))
legs = union(*leg_parts, k=0.07)

# coda avvolta attorno alle zampe anteriori (ferma, appoggiata a terra)
TAIL_PTS = catmull([(0.0, 0.66, 0.3), (0.36, 0.8, 0.12), (0.7, 0.42, 0.1), (0.74, -0.18, 0.1), (0.5, -0.66, 0.1),
                    (0.12, -0.84, 0.13)], 5)
NT = len(TAIL_PTS) - 1
tail = tube(TAIL_PTS, [0.11 - 0.04 * (i / NT) for i in range(NT + 1)])

core = union(torso, neck, k=0.16)
core = union(core, H(head_final), k=0.1)
core = union(core, legs, k=0.08)
core = union(core, tail, k=0.06)
core0 = shrink(core.intersect(halfspace_z(0.0, above=True)))
body_only = shrink(union(union(torso, neck, k=0.16), legs, k=0.08).intersect(halfspace_z(0.0, above=True)))

# ============================================================ cervello rosa (lobi con circonvoluzioni) dentro la cupola
BR_C = np.array((0.0, 0.04, CUT_Z + 0.05))


def brain_f(p):
    q = p - BR_C.astype(np.float32)
    ax = np.abs(q[:, 0])
    # due emisferi separati dalla scissura centrale
    h = np.stack([ax - 0.128, q[:, 1], q[:, 2]], 1) / np.array((0.15, 0.27, 0.205), dtype=np.float32)
    k0 = np.linalg.norm(h, axis=1)
    k1 = np.linalg.norm(h / np.array((0.15, 0.27, 0.205), dtype=np.float32), axis=1)
    d = k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)
    # circonvoluzioni: solchi ondulati che attraversano i lobi
    u = 30.0 * q[:, 1] + 3.4 * np.sin(17.0 * ax + 1.0) + 2.6 * np.sin(15.0 * q[:, 2] + 0.5) + 1.4 * np.sin(29.0 * ax)
    groove = np.maximum(0.0, 1.0 - np.abs(np.sin(u)) / 0.42)
    return d + 0.022 * groove ** 2


brain = SDF(brain_f, BR_C - (0.3, 0.3, 0.23), BR_C + (0.3, 0.3, 0.23))

# ============================================================ punti cuciti attorno alla cupola (+ naso rosa)
stitch_base = union(head_final, DOME)
stitches = []
NS = 16
for i in range(NS):
    th = 2 * math.pi * (i + 0.5) / NS
    c = np.array((0.375 * math.cos(th), 0.04 + 0.36 * math.sin(th), CUT_Z - 0.005))
    t = np.array((-math.sin(th), math.cos(th), 0.0))
    stitches += stitch_cross(stitch_base, on_surface(stitch_base, c, 0.0), t, size=0.075, r=0.017, lift=0.01)
nose = union(*[ellipsoid((0.034, 0.03, 0.026), tuple(NOSE_C + (sx * 0.03, 0.0, 0.012))) for sx in (1, -1)],
             ellipsoid((0.024, 0.026, 0.024), tuple(NOSE_C + (0.0, -0.008, -0.032))), k=0.045).subtract(nostrils, k=0.008)

# ============================================================ aura viola: lingue di energia dalla schiena + sigillo a terra
flames = []
for i, (a, L) in enumerate(((-62, 0.62), (-36, 0.85), (-12, 1.05), (12, 1.05), (36, 0.85), (62, 0.62))):
    ar = math.radians(a)
    c = np.array((0.0, 0.0, 1.42))
    p, nr = surf(body_only, c, c + np.array((math.sin(ar) * 0.9, 0.55, math.cos(ar) * 0.5)))
    d = norm(np.array((math.sin(ar) * 0.55, 0.45, 1.0)))
    flames.append(wisp(p - nr * 0.05, d, L * rng.uniform(0.95, 1.05), 0.11, np.array((math.sin(ar) * 0.25, 0.3, -0.1)),
                       wiggle=0.12 * (1 if i % 2 else -1), phase=rng.uniform(0, 3), r1=0.02))
for a, L in ((-20, 0.55), (20, 0.55)):
    ar = math.radians(a)
    c = np.array((0.0, 0.25, 0.9))
    p, nr = surf(body_only, c, c + np.array((math.sin(ar), 1.0, 0.25)))
    flames.append(wisp(p - nr * 0.05, norm(np.array((math.sin(ar) * 0.3, 0.6, 1.0))), L, 0.09,
                       np.array((0.0, 0.25, -0.05)), wiggle=0.12, phase=rng.uniform(0, 3), r1=0.02))
SIG_C = np.array((0.0, -0.05, 0.0))
sigil = [torus(1.0, 0.03, tuple(SIG_C + (0.0, 0.0, 0.03)))]
for j in range(6):
    a = math.radians(30 + 60 * j)
    c = SIG_C + np.array((1.0 * math.cos(a), 1.0 * math.sin(a), 0.0))
    sigil.append(cylinder(tuple(c), tuple(c + (0, 0, 0.045)), 0.068, round=0.012))
aura = union(fast_union(flames, k=0.03).subtract(body_only.offset(-0.05)), fast_union(sigil))

# ============================================================ tre sfere psichiche fluttuanti
ORBS = [np.array((-0.86, -0.42, 1.3)), np.array((0.92, 0.05, 1.95)), np.array((-0.5, 0.55, 2.86))]
orb_core, orb_glass = [], []
for i, c in enumerate(ORBS):
    orb_core.append(sphere(0.1, tuple(c)))
    nrm = norm((0.4 * (1 if i % 2 else -1), 0.3, 1.0))
    orb_core.append(torus(0.205, 0.026).rotate(orient(nrm)).translate(tuple(c)))
    orb_glass.append(sphere(0.158, tuple(c)))

# ============================================================ parti
HEAD_ZONE = H(ellipsoid((0.64, 0.62, 0.6), (0.0, -0.05, 0.04)))
m.add("Body", core0.subtract(HEAD_ZONE.offset(-0.03)), FUR, tris=2700, voxel=0.03)
m.add("Head", core0.intersect(HEAD_ZONE.offset(0.03)), FUR, tris=2700, voxel=0.022)
pad_solid = union(*[ellipsoid((0.098, 0.093, 0.083), (sx * 0.067, -0.383, -0.145)) for sx in (1, -1)],
                  ellipsoid((0.083, 0.083, 0.068), (0, -0.313, -0.257)), k=0.03)
pad_solid = pad_solid.subtract(nostrils.offset(0.01)).subtract(union(*lip_tubes).offset(0.004), k=0.008)
m.add("Accent", H(union(pad_solid.subtract(head0.offset(-0.09)), ear_fluff)), ACCENT, role="detail", tris=700,
      voxel=0.016)
m.add("Dome", H(DOME), GLASS, material="Glass", role="detail", tris=900, voxel=0.018, transparency=0.45)
m.add("Brain", H(brain), BRAIN, material="Neon", role="glow", tris=1600, voxel=0.01)
m.add("Stitches", union(H(fast_union(stitches)), H(nose)), THREAD, role="detail", tris=700, voxel=0.01)

eyes, pupils, shines = [], [], []
for sx in (1, -1):
    eyes.append(H(eye_place(ellipsoid((EA, EB, EC)).rot(0, sx * 12, 0), sx, (0, 0.03, 0))))
    look = -0.01
    pupils.append(H(eye_place(ellipsoid((0.017, 0.02, 0.056)), sx, (look, -0.016, -0.006))))
    shines.append(H(eye_place(sphere(0.018), sx, (look - 0.03, -0.024, -0.004))))
m.add("EyeGlow", union(*eyes), EYE_GLOW, material="Neon", role="glow", tris=400, voxel=0.01)
m.add("Pupils", union(*pupils), PUPIL, role="eye", tris=400, voxel=0.008)
fangs = []
for sx in (1, -1):
    b, _ = surf(head0, (sx * 0.035, -0.2, -0.19), (sx * 0.075, -0.8, -0.2))
    fangs.append(round_cone(tuple(b + np.array((0, 0.02, 0.005))), tuple(b + np.array((sx * -0.004, -0.012, -0.072))),
                            0.021, 0.005))
m.add("Shine", union(H(union(*fangs)), *shines), TOOTH, role="shine", tris=500, voxel=0.008)
m.add("Nebula", aura, AURA, material="Neon", role="glow", tris=2200, voxel=0.016)
m.add("Aura", fast_union(orb_core), ORB, material="Neon", role="glow", tris=1000, voxel=0.014)
m.add("OrbGlass", fast_union(orb_glass), ORB_GLASS, material="Glass", role="detail", tris=600, voxel=0.015,
      transparency=0.45)


if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
