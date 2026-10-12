"""Lupo Ombra (ShadowWolf) - pet PRIMORDIALE (fra Segreto e Ultra), zona Foresta.

Un enorme metalupo nero-viola acquattato e pronto a balzare: zampe anteriori larghe e massicce piantate
a terra con gli artigli fuori, spalle alte con le scapole sporgenti, posteriori raccolti come molle, testa
grossa, bassa e protesa che ringhia. Muso lungo arricciato pieno di pieghe, labbro alzato su gengive rosso
sangue, zanne lunghissime da metalupo e file di denti aguzzi; orecchie a punta tirate all'indietro,
sopracciglia pesanti e occhi viola a fessura che brillano. Dal collo e dalle spalle sale una folta criniera
di fumo scuro che brucia di viola (parte Neon "Shadow": il gioco ci aggancia il fumo nero) e continua lungo
la schiena; graffi di battaglia sulla spalla e sull'anca bruciano dello stesso viola. La coda folta e'
alzata e arricciata in avanti per stare nell'ingombro, scodinzola (gruppo "Tail") e in punta si sfalda in
fumo. Collare di cuoio rosso sangue con borchie d'acciaio a punta e un anello da cui penzola una catena
spezzata.
Tocco "toy horror": una grossa chiave di carica d'ottone piantata nella schiena e una lunga cucitura a
punti incrociati sul fianco destro.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, capsule, cylinder, ellipsoid, euler, halfspace_z, look_matrix,  # noqa: E402
                     round_cone, smax, smin, sphere, tube, union)
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
    """Come project() della libreria, ma per tanti raggi insieme: ritorna (punti, normali)."""
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
        print(f"[wolf] attenzione: {len(bad)} raggi partono fuori dalla forma, es. {np.round(o[bad[0]], 3)}")
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
    """Strato di "vernice" sottile (guscio fra -inn e +out attorno a core) dentro 'region' (bordo arrotondato k)."""
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


def loft(y0, y1, w0, w1, h0, h1, z0, z1, r, rc=0.0, tp=0.0):
    """Box arrotondato che si restringe lungo Y (da y0 a y1): mezza larghezza w, mezza altezza h, centro z."""
    ya, yb = min(y0, y1), max(y0, y1)

    def f(p):
        t = np.clip((p[:, 1] - y0) / (y1 - y0), 0.0, 1.0)
        w = w0 + (w1 - w0) * t
        h = h0 + (h1 - h0) * t
        zc = z0 + (z1 - z0) * t
        if tp:
            u = np.clip((p[:, 2] - zc + h) / (2 * h), 0.0, 1.0)
            w = w * (1.0 - tp * u)
        qx = np.abs(p[:, 0]) - (w - r)
        qz = np.abs(p[:, 2] - zc) - (h - r)
        d2 = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qz, 0) ** 2) + np.minimum(np.maximum(qx, qz), 0) - r
        dy = np.maximum(p[:, 1] - yb, ya - p[:, 1])
        a, b = d2 + rc, dy + rc
        return np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2) + np.minimum(np.maximum(a, b), 0) - rc

    wm = max(w0, w1)
    return SDF(f, (-wm, ya, min(z0 - h0, z1 - h1)), (wm, yb, max(z0 + h0, z1 + h1)))


def pie(c, r, a_lo, a_hi, half_w):
    """Spicchio attorno all'asse X passante per c: angoli (gradi) misurati dall'avanti (-Y) verso l'alto."""
    lo_, hi_ = math.radians(a_lo), math.radians(a_hi)
    c = np.asarray(c, dtype=np.float32)

    def f(p):
        fy = -(p[:, 1] - c[1])
        dz = p[:, 2] - c[2]
        rr = np.sqrt(fy * fy + dz * dz) - r
        d1 = dz * math.cos(hi_) - fy * math.sin(hi_)
        d2 = -(dz * math.cos(lo_) - fy * math.sin(lo_))
        return np.maximum(np.maximum(rr, np.abs(p[:, 0]) - half_w), np.maximum(d1, d2))

    return SDF(f, (-half_w, c[1] - r, c[2] - r), (half_w, c[1] + r, c[2] + r))


def plane_sdf(point, normal, lo=(-6, -6, -6), hi=(6, 6, 6)):
    """Semispazio: dentro dove (p - point) . normal < 0."""
    pt = np.asarray(point, dtype=np.float32)
    n = norm(normal).astype(np.float32)
    return SDF(lambda p: (p - pt) @ n, lo, hi)


def horn(base, d, L, r0, curl=(0, 0, 0), n=5, r1=0.006, power=1.0):
    """Cono curvo (corno, artiglio, dente): parte da base verso d (lunghezza L) e si piega verso 'curl'."""
    base, d, c = np.asarray(base, float), norm(d), np.asarray(curl, float)
    ts = np.linspace(0.0, 1.0, n)
    pts = [tuple(base + d * L * t + c * L * t * t) for t in ts]
    return tube(pts, [r0 + (r1 - r0) * t ** power for t in ts])


def rot_pts(R, pts, pivot=(0, 0, 0)):
    pv = np.asarray(pivot, dtype=np.float64)
    return (np.asarray(pts, dtype=np.float64) - pv) @ np.asarray(R, dtype=np.float64).T + pv


def polyline(pts):
    pts = np.asarray(pts, dtype=np.float64)
    seg = np.diff(pts, axis=0)
    ln = np.linalg.norm(seg, axis=1)
    return pts, seg, ln, np.concatenate([[0.0], np.cumsum(ln)])


def poly_at(P, s):
    """Punto e tangente (normalizzata) della polilinea all'ascissa curvilinea s."""
    pts, seg, ln, cum = P
    s = float(np.clip(s, 0.0, cum[-1]))
    i = int(min(np.searchsorted(cum, s, side="right") - 1, len(seg) - 1))
    t = (s - cum[i]) / ln[i]
    return pts[i] + seg[i] * t, seg[i] / ln[i]


def curve_on(base, origin, targets):
    """Punti della superficie lungo i raggi da origin (interno) verso i punti 'targets'."""
    o = np.asarray(origin, float)
    pts, nr = project_many(base, [o] * len(targets), [np.asarray(t, float) - o for t in targets])
    return pts, nr


def line_pts(a, b, n):
    return [mix(a, b, t) for t in np.linspace(0, 1, n)]


def slash(base, origin, a, b, n=9, w=0.04):
    """Graffio: curva sulla superficie da a a b (punti interni/vicini), proiettata da origin."""
    pts, nr = curve_on(base, origin, line_pts(a, b, n))
    prof = [math.sin(math.pi * (0.08 + 0.84 * j / (n - 1))) ** 0.8 for j in range(n)]
    groove = tube([tuple(p) for p in pts], [max(w * f, 0.008) for f in prof])
    fill = tube([tuple(p - q * w * 0.45) for p, q in zip(pts, nr)], [max(w * 0.62 * f, 0.012) for f in prof])
    return groove, fill


def chain_link(c, axis, normal, half_len, R, r):
    """Maglia di catena (anello allungato): asse lungo 'axis', piano dell'anello perpendicolare a 'normal'."""
    a = norm(axis)
    nn = norm(np.asarray(normal, float) - a * float(np.dot(normal, a)))
    s = np.cross(nn, a)
    M = np.stack([s, nn, a], axis=1).astype(np.float32)
    c = np.asarray(c, dtype=np.float32)

    def f(p):
        q = (p - c) @ M
        qz = q[:, 2] - np.clip(q[:, 2], -half_len, half_len)
        ring = np.sqrt(q[:, 0] ** 2 + qz ** 2) - R
        return np.sqrt(ring ** 2 + q[:, 1] ** 2) - r

    e = half_len + R + r
    return SDF(f, c - e, c + e)


def wisp(base, d, L, r0, curl, wiggle=0.0, n=7, r1=0.014, phase=0.0):
    """Lingua di fumo: tubo che si assottiglia fino a una punta, con una curva a S (wiggle)."""
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


# ============================================================ colori
FUR = (50, 37, 70)          # pelo nero-viola
UNDER = (110, 96, 138)      # labbra, mento e orecchie interne grigio-viola
RUFF = (31, 23, 46)         # ciuffi irti piu' scuri (guance, gomiti, schiena)
SMOKE = (110, 40, 222)      # fumo viola profondo (Neon)
EYE_GLOW = (212, 128, 255)  # occhi viola accesi
BONE = (236, 228, 208)      # artigli
TOOTH = (250, 247, 238)
GUM = (158, 20, 38)         # gengive rosso sangue e lingua
MAW = (26, 10, 22)          # gola, naso, pupille
COLLAR = (150, 18, 32)      # cuoio rosso sangue
IRON = (168, 166, 182)      # borchie e catena d'acciaio
BRASS = (196, 146, 64)      # chiave di carica d'ottone
THREAD = (226, 216, 196)    # filo chiaro della cucitura sul fianco

m = Model("ShadowWolf", "pet")
rng = np.random.default_rng(9)

# ============================================================ testa (spazio locale: muso verso -Y)
HEAD_POS = np.array([0.0, -1.2, 1.44])
HS = 1.22                              # scala della testa
R_HEAD = euler(6.0, 0.0, 10.0)        # testa bassa e protesa, girata un po' verso la camera 3/4
GAPE = 24.0                            # fauci socchiuse nel ringhio
J = np.array([0.0, -0.06, -0.12])     # cerniera della mandibola
R_JAW = euler(GAPE, 0.0, 0.0)


def H(s):
    return s.scale(HS).rotate(R_HEAD).translate(HEAD_POS)


def hp(p):
    return rot_pts(R_HEAD, np.asarray(p, dtype=np.float64) * HS) + HEAD_POS


def hv(v):
    return rot_pts(R_HEAD, v)


def JW(s):
    return s.rotate(R_JAW, pivot=J)


cran = ellipsoid((0.32, 0.37, 0.30), (0, 0.03, 0.10))
cheeks = [ellipsoid((0.2, 0.26, 0.19), (sx * 0.2, -0.12, -0.06)) for sx in (1, -1)]
snout = loft(-0.16, -0.94, 0.19, 0.1, 0.165, 0.095, 0.02, -0.01, r=0.065, rc=0.05, tp=0.4)
brows = [capsule((sx * 0.05, -0.35, 0.19), (sx * 0.26, -0.22, 0.28), 0.06) for sx in (1, -1)]
bridge = capsule((0, -0.31, 0.18), (0, -0.88, 0.095), 0.055)
upper = union(cran, *cheeks, k=0.16)
upper = union(upper, snout, k=0.16)
upper = union(upper, *brows, bridge, k=0.08)

# orbite incavate e palpebre tagliate in diagonale: occhi socchiusi e cattivi
EYE_D = {sx: norm((sx * 0.52, -0.84, 0.12)) for sx in (1, -1)}
EYE_C = {}
for sx in (1, -1):
    o = np.array((sx * 0.1, -0.2, 0.12))
    EYE_C[sx], _ = surf(upper, o, o + EYE_D[sx])


def eye_place(shape, sx, offset=(0.0, 0.0, 0.0)):
    """Coordinate locali dell'occhio: X di lato, -Y verso lo sguardo, Z in alto; origine sulla superficie."""
    return shape.translate(offset).rotate(look_matrix(EYE_D[sx])).translate(EYE_C[sx])


EA, EB, EC = 0.108, 0.048, 0.064
sockets = union(*[eye_place(ellipsoid((0.118, 0.075, 0.082)), sx, (0, 0.028, 0)) for sx in (1, -1)])
upper = upper.subtract(sockets, k=0.035)
LID_CUT, LID_SLOPE = 0.02, 0.6
lids = []
for sx in (1, -1):
    A, B, C = EA + 0.024, EB + 0.028, EC + 0.026

    def lid_plane(p, sx=sx):
        return (LID_CUT - LID_SLOPE * sx * p[:, 0] - p[:, 2]) / math.sqrt(1 + LID_SLOPE ** 2)

    lid = ellipsoid((A, B, C)).intersect(SDF(lid_plane, (-A, -B, -C), (A, B, C)))
    lids.append(eye_place(lid, sx, (0, 0.036, 0)))
upper = shrink(union(upper, *lids, k=0.012))

# pieghe del ringhio sul dorso del muso e ai lati del naso
wrinkles = []
for y, w in ((-0.56, 0.13), (-0.64, 0.125), (-0.72, 0.12)):
    tg = [(x, y + 0.04 * abs(x) / w, 0.0) for x in np.linspace(-w, w, 9)]
    q, _ = curve_on(upper, (0, y, -0.03), [np.array(p) + np.array((0, 0, 0.3)) for p in tg])
    wrinkles.append(tube([tuple(p) for p in q], [0.012, 0.022, 0.028, 0.03, 0.03, 0.03, 0.028, 0.022, 0.012]))
for sx in (1, -1):
    for y0 in (-0.6, -0.71):
        q, _ = curve_on(upper, (sx * 0.03, y0, -0.02),
                        [np.array((sx * (0.1 + 0.03 * j), y0 + 0.045 * j, 0.1 - 0.045 * j)) for j in range(5)])
        wrinkles.append(tube([tuple(p) for p in q], [0.012, 0.024, 0.028, 0.022, 0.01]))
upper_carved = upper.subtract(fast_union(wrinkles), k=0.016)

# mandibola (chiusa) poi aperta attorno alla cerniera
mand = loft(-0.04, -0.84, 0.19, 0.095, 0.075, 0.05, -0.20, -0.17, r=0.045, rc=0.035)
chin = ellipsoid((0.09, 0.07, 0.06), (0, -0.80, -0.19))
masseter = [ellipsoid((0.12, 0.20, 0.13), (sx * 0.18, -0.16, -0.20)) for sx in (1, -1)]
lower_closed = shrink(union(mand, chin, *masseter, k=0.08))
lower = JW(lower_closed)
web = pie(J, 0.24, -GAPE - 8.0, 12.0, 0.19)
head_solid = union(upper_carved, lower, k=0.06)
head_solid = shrink(union(head_solid, web, k=0.08))

# cavita' della bocca: canale superiore, canale inferiore (ruotato), gola
beta = math.radians(GAPE / 2)
n_up = np.array([0.0, -math.sin(beta), math.cos(beta)])
above_bis = plane_sdf(J, -n_up)
below_bis = plane_sdf(J, n_up)
up_ch = loft(0.02, -0.9, 0.125, 0.062, 0.5, 0.5, -0.60, -0.56, r=0.05, rc=0.08)
lo_ch = loft(0.02, -0.82, 0.118, 0.055, 0.5, 0.5, 0.335, 0.34, r=0.05, rc=0.08)
throat = ellipsoid((0.11, 0.16, 0.10), (0.0, -0.04, -0.14))
cavity = union(up_ch.intersect(above_bis), JW(lo_ch).intersect(below_bis), throat, k=0.035)
nostrils = union(*[ellipsoid((0.022, 0.04, 0.022)).rot(0, sx * 30, sx * 25).translate((sx * 0.04, -0.985, 0.07))
                   for sx in (1, -1)])


# orecchie a punta appiattite all'indietro (aggressive)
def ear_shape():
    cone = round_cone((0, 0, -0.04), (0, 0, 0.36), 0.15, 0.016)
    slab = SDF(lambda p: np.abs(p[:, 1]) - 0.055, (-1, -1, -1), (1, 1, 1))
    cup = round_cone((0, -0.06, 0.02), (0, -0.06, 0.29), 0.095, 0.012)
    return cone.intersect(slab, k=0.02).subtract(cup, k=0.015)


def ear_pose(s, sx):
    return s.scale(1.15).rot(-34, sx * 20, -sx * 10).translate((sx * 0.19, 0.1, 0.27))


ears = [ear_pose(ear_shape(), sx) for sx in (1, -1)]
EAR_CUPS = [ear_pose(round_cone((0, -0.06, 0.02), (0, -0.06, 0.29), 0.095, 0.012), sx) for sx in (1, -1)]
head_solid = union(head_solid, *ears, k=0.04)

# ============================================================ corpo (acquattato: davanti basso, groppa alta)
chest = ellipsoid((0.55, 0.52, 0.56), (0, -0.50, 1.10))
ribs = ellipsoid((0.49, 0.52, 0.47), (0, 0.0, 1.28))
waist = ellipsoid((0.34, 0.33, 0.34), (0, 0.38, 1.38))
haunch = ellipsoid((0.43, 0.40, 0.44), (0, 0.67, 1.50))
torso = union(union(chest, ribs, k=0.3), waist, haunch, k=0.25)
scap = [ell((sx * 0.32, -0.42, 1.64), (0.2, 0.22, 0.36), axis=(0, -0.45, 1.0)) for sx in (1, -1)]  # scapole
NECK = [(0, -0.42, 1.47), (0, -0.8, 1.5), (0, -1.08, 1.47)]
neck = tube(NECK, [0.47, 0.42, 0.37], k=0.08)
throat_skin = ell(hp((0.0, -0.12, -0.30)), (0.22, 0.26, 0.22), axis=hv((0, -0.4, -1.0)))

# zampe: anteriori larghe piantate a terra, posteriori raccolte come molle
FRONT = {sx: dict(sh=np.array([sx * 0.38, -0.62, 1.22]), el=np.array([sx * 0.57, -0.66, 0.64]),
                  wr=np.array([sx * 0.67, -0.95, 0.22]), paw=np.array([sx * 0.7, -1.09, 0.105])) for sx in (1, -1)}
HIND = {sx: dict(hip=np.array([sx * 0.30, 0.64, 1.44]), knee=np.array([sx * 0.42, 0.30, 0.84]),
                 hock=np.array([sx * 0.42, 0.92, 0.42]), paw=np.array([sx * 0.42, 0.76, 0.085])) for sx in (1, -1)}
leg_parts, TOES = [], []
for sx, L in FRONT.items():
    sh, el, wr, paw = L["sh"], L["el"], L["wr"], L["paw"]
    leg_parts += [
        ell(mix(sh, el, 0.4) + np.array([sx * 0.04, -0.03, 0.0]), (0.28, 0.3, 0.4), axis=el - sh),     # omero
        round_cone(sh, el, 0.27, 0.19),
        ell(mix(el, wr, 0.3) + np.array([0, 0.03, 0.0]), (0.18, 0.19, 0.27), axis=wr - el),             # avambraccio
        round_cone(el, wr, 0.19, 0.14),
        round_cone(wr, paw, 0.14, 0.145),
        ellipsoid((0.21, 0.27, 0.11), tuple(paw + np.array([0, -0.05, 0.0]))),
    ]
    for dx in (-0.13, -0.045, 0.045, 0.13):
        tp = paw + np.array([dx, -0.24 + 0.6 * dx * dx, -0.025])
        leg_parts.append(sphere(0.075, tuple(tp)))
        TOES.append((tp, 1.0))
for sx, L in HIND.items():
    hip, knee, hock, paw = L["hip"], L["knee"], L["hock"], L["paw"]
    leg_parts += [
        ell(mix(hip, knee, 0.45) + np.array([sx * 0.05, 0.04, 0.0]), (0.28, 0.33, 0.45), axis=knee - hip),  # coscia
        round_cone(hip, knee, 0.26, 0.17),
        round_cone(knee, hock, 0.17, 0.115),
        ell(mix(knee, hock, 0.35) + np.array([0, 0.04, 0.03]), (0.15, 0.17, 0.25), axis=hock - knee),        # polpaccio
        round_cone(hock, paw, 0.115, 0.12),
        ellipsoid((0.17, 0.22, 0.09), tuple(paw + np.array([0, -0.05, 0.0]))),
    ]
    for dx in (-0.11, -0.035, 0.035, 0.11):
        tp = paw + np.array([dx, -0.2 + 0.6 * dx * dx, -0.02])
        leg_parts.append(sphere(0.062, tuple(tp)))
        TOES.append((tp, 0.8))
legs = union(*leg_parts, k=0.06)

core = union(torso, *scap, k=0.15)
core = union(core, neck, k=0.18)
core = union(core, H(head_solid), k=0.12)
core = union(core, throat_skin, k=0.15)
core = union(core, legs, k=0.1)
core = core.subtract(H(cavity), k=0.025)
core = core.subtract(H(nostrils), k=0.015)
core0 = shrink(core.intersect(halfspace_z(0.0, above=True)))

# coda folta alzata che si arriccia in avanti (parte a se': il gioco la fa scodinzolare)
TAIL_PTS = bezier((0.0, 0.96, 1.62), (0.0, 1.34, 1.92), (0.0, 1.30, 2.74), (0.0, 0.80, 2.90), 16)
TAIL_R = [0.13 + 0.11 * math.sin(math.pi * min(i / 16 * 1.25, 1.0)) ** 0.8 - 0.05 * (i / 16) ** 2 for i in range(17)]
TAIL_PIVOT = (0.0, 0.98, 1.62)
tail_core = tube(TAIL_PTS, TAIL_R)
T_P = polyline(TAIL_PTS)
tail_fur = []
for j, s in enumerate(np.linspace(0.18, 0.86, 7)):
    c, t = poly_at(T_P, T_P[3][-1] * s)
    up = norm(np.array([0, 0, 1.0]) - t * t[2])
    side = np.cross(t, up)
    for a in (-70, 0, 70) if j % 2 == 0 else (-35, 35):
        dd = up * math.cos(math.radians(a)) + side * math.sin(math.radians(a))
        p, nr = surf(tail_core, c, c + dd)
        tail_fur.append(horn(p - nr * 0.04, norm(nr * 0.45 + t * 0.9), 0.2, 0.075, curl=tuple(t * 0.25), n=4,
                             r1=0.016))
tail = union(tail_core, fast_union(tail_fur), k=0.03)


# ============================================================ ciuffi irti scuri: guance, gomiti, schiena
def tufts(base, origin, targets, flow, L, r0, lean=0.6, sink=0.05):
    """Ciuffi di pelo a punta: dalla superficie (raggi da origin verso targets) seguono la direzione 'flow'."""
    pts, nrs = curve_on(base, origin, targets)
    out = []
    for p, nr in zip(pts, nrs):
        fl = np.asarray(flow, float)
        fl = fl - nr * float(fl @ nr)
        fl = norm(fl) if np.linalg.norm(fl) > 1e-6 else nr
        d = norm(nr * (1 - lean) + fl * lean)
        out.append(horn(p - nr * sink, d, L * rng.uniform(0.88, 1.12), r0, curl=tuple(fl * 0.3 - nr * 0.1), n=4,
                        r1=0.015))
    return out


fur = []
for sx in (1, -1):
    # gorgiera sulle guance: ciuffi che scappano all'indietro e in basso
    tg = [hp((sx * 0.8, 0.05 + dy, -0.1 + dz)) for dy, dz in ((0.0, 0.1), (0.1, -0.06), (-0.04, -0.22), (0.14, -0.3))]
    fur += tufts(core0, hp((sx * 0.15, -0.1, -0.05)), tg, hv((sx * 0.4, 1.0, -0.35)), 0.26, 0.085, lean=0.75)
    # gomiti
    L = FRONT[sx]
    tg = [L["el"] + np.array([sx * 0.25, 0.35, -0.05]), L["el"] + np.array([sx * 0.1, 0.45, 0.1])]
    fur += tufts(core0, L["el"] + np.array([0, 0, 0.05]), tg, (0, 1.0, -0.4), 0.22, 0.08, lean=0.7)
    # dietro le cosce
    L = HIND[sx]
    tg = [mix(L["hip"], L["knee"], 0.5) + np.array([sx * 0.2, 0.5, -0.1]), L["hip"] + np.array([sx * 0.2, 0.5, -0.1])]
    fur += tufts(core0, mix(L["hip"], L["knee"], 0.4), tg, (0, 0.6, -1.0), 0.22, 0.08, lean=0.7)
# pelo ritto lungo la schiena, dalla criniera di fumo alla coda
for y, xs in ((0.08, (-0.12, 0.12)), (0.3, (0.0,)), (0.86, (0.0,))):
    tg = [np.array((x, y + 0.2, 2.4)) for x in xs]
    fur += tufts(core0, (0.0, y, 1.3), tg, (0, 1.0, 0.25), 0.24, 0.085, lean=0.55)
m_fur = fast_union(fur).subtract(core0.offset(-0.035))

# ============================================================ cucitura sul fianco destro (solco + punti incrociati)
SEAM_T = [(0.9, -0.12, 1.62), (0.9, 0.02, 1.42), (0.9, 0.16, 1.24), (0.9, 0.32, 1.1), (0.9, 0.5, 1.02)]
seam_o = [(0.0, y, z) for _, y, z in SEAM_T]
seam_pts, _ = project_many(core0, seam_o, [np.array(t) - np.array(o) for t, o in zip(SEAM_T, seam_o)])
seam_line = resample(seam_pts, 0.03)
seam_groove = tube([tuple(p) for p in seam_line], 0.026)
# graffi di battaglia che bruciano di viola: spalla sinistra e anca destra
scar_cut, scar_glow = [], []
for i in range(3):
    dz = -0.13 * i
    g, f = slash(core0, (-0.3, -0.62, 1.15), (-0.66, -0.88, 1.48 + dz), (-0.64, -0.5, 1.12 + dz), n=10, w=0.036)
    scar_cut.append(g)
    scar_glow.append(f)
for i in range(2):
    dy = 0.14 * i
    g, f = slash(core0, (0.2, 0.62, 1.3), (0.5, 0.42 + dy, 1.78), (0.62, 0.62 + dy, 1.2), n=10, w=0.034)
    scar_cut.append(g)
    scar_glow.append(f)
core = core0.subtract(union(seam_groove, fast_union(scar_cut)), k=0.012)

# la pelle e' divisa in due parti dalla stessa forma (sovrapposte di poco: la giunta non si vede), cosi' la testa
# ha piu' triangoli del corpo
HEAD_ZONE = H(ellipsoid((0.64, 0.80, 0.66), (0.0, -0.32, 0.0)))
m.add("Body", core.subtract(HEAD_ZONE.offset(-0.03)), FUR, tris=3300, voxel=0.0409)
m.add("Head", core.intersect(HEAD_ZONE.offset(0.03)), FUR, tris=2300, voxel=0.0323)
m.add("Tail", tail, FUR, tris=900, voxel=0.0308, group="Tail", pivot=TAIL_PIVOT)

# ============================================================ pelo chiaro: labbra, mento e orecchie interne
under_head = union(ellipsoid((0.2, 0.42, 0.13), (0, -0.62, -0.10)),                # labbra e lati del muso
                   JW(ellipsoid((0.17, 0.5, 0.1), (0, -0.5, -0.22))),                 # mento
                   k=0.04).subtract(cavity.offset(0.045))
underfur = union(paint(core, H(under_head), out=0.016, inn=0.075),
                 paint(core, H(union(*EAR_CUPS).offset(0.03)), out=0.014, inn=0.04))
m.add("Underfur", underfur, UNDER, role="detail", tris=600, voxel=0.0385)
m.add("Ruff", m_fur.intersect(halfspace_z(0.004, above=True)), RUFF, role="detail", tris=740, voxel=0.0289)

# ============================================================ criniera di fumo viola (parte Neon "Shadow")
NAPE_IN = np.array([0.0, -0.5, 1.52])           # dentro il collo, subito dietro il collare
WITHERS_IN = np.array([0.0, -0.02, 1.45])        # dentro il garrese
smoke = []
for i, s in enumerate(np.linspace(0.0, 1.0, 5)):
    c = mix(NAPE_IN, WITHERS_IN, s)
    angs = (-105, -62, -20, 22, 64, 106) if i % 2 == 0 else (-84, -42, 0, 42, 84)
    for a in angs:
        ar = math.radians(a + rng.normal(0, 6))
        dirn = np.array([math.sin(ar), 0.12, math.cos(ar)])
        p, nr = surf(core0, c, c + dirn)
        top = math.cos(ar)
        L = (0.56 + 0.7 * max(top, 0.0)) * (1.0 - 0.22 * abs(s - 0.35)) * rng.uniform(0.88, 1.12)
        d = norm(nr * 0.5 + np.array([0.0, 0.2, 1.0]))
        curl = np.array([math.sin(ar) * 0.45, 0.42, -0.2])
        smoke.append(wisp(p - nr * 0.06, d, L, 0.12 + 0.04 * max(top, 0.0), curl, wiggle=0.16 * rng.choice((-1, 1)),
                          phase=rng.uniform(0, 3), r1=0.022))
# lingue piu' basse sui lati del collo (allargano la sagoma vista da davanti)
for s in (0.1, 0.45, 0.8):
    c = mix(NAPE_IN, WITHERS_IN, s)
    for sx in (1, -1):
        ar = math.radians(sx * (128 + rng.normal(0, 5)))
        p, nr = surf(core0, c, c + np.array([math.sin(ar), 0.1, math.cos(ar)]))
        smoke.append(wisp(p - nr * 0.05, norm(nr * 0.8 + np.array([0.0, 0.25, 0.9])), 0.5 * rng.uniform(0.9, 1.1), 0.11,
                          np.array([sx * 0.45, 0.3, -0.1]), wiggle=0.14, phase=rng.uniform(0, 3), r1=0.022))
# la criniera continua un poco lungo la schiena, piu' bassa (la chiave resta libera dietro)
for a in (-30, 30):
    c = np.array([0.0, 0.1, 1.4])
    ar = math.radians(a)
    p, nr = surf(core0, c, c + np.array([math.sin(ar), 0.0, math.cos(ar)]))
    smoke.append(wisp(p - nr * 0.05, norm(nr * 0.4 + np.array([0.0, 0.35, 1.0])), 0.45 * rng.uniform(0.9, 1.1), 0.1,
                      np.array([math.sin(ar) * 0.3, 0.45, -0.2]), wiggle=0.14, phase=rng.uniform(0, 3), r1=0.022))
# fumo che sale anche dalle scapole
for sx in (1, -1):
    for dy, dz in ((0.0, 0.0), (0.18, -0.08)):
        c = np.array([sx * 0.18, -0.4 + dy, 1.5 + dz])
        p, nr = surf(core0, c, c + np.array([sx * 0.8, 0.1, 0.6]))
        smoke.append(wisp(p - nr * 0.05, norm(nr * 0.5 + np.array([sx * 0.2, 0.5, 0.8])), 0.5 * rng.uniform(0.9, 1.1),
                          0.1, np.array([sx * 0.3, 0.4, -0.1]), wiggle=0.1, phase=rng.uniform(0, 3), r1=0.022))
# sbuffi di fumo alla radice della criniera: le lingue nascono da una nuvola
for i, s in enumerate(np.linspace(0.0, 1.0, 6)):
    c = mix(NAPE_IN, WITHERS_IN, s)
    for a in ((-70, 0, 70) if i % 2 == 0 else (-38, 38)):
        ar = math.radians(a + rng.normal(0, 8))
        p, nr = surf(core0, c, c + np.array([math.sin(ar), 0.1, math.cos(ar)]))
        smoke.append(sphere(rng.uniform(0.11, 0.16), tuple(p + nr * 0.02)))
shadow = fast_union(smoke, k=0.04).subtract(core0.offset(-0.04))
m.add("Shadow", shadow, SMOKE, material="Neon", role="glow", tris=2180, voxel=0.0449)

# punta della coda che si sfalda in fumo
TT = np.array(TAIL_PTS[-1])
TD = norm(np.array(TAIL_PTS[-1]) - np.array(TAIL_PTS[-3]))
ts1 = norm(np.cross(TD, (1.0, 0.0, 0.0)))
ts2 = np.cross(TD, ts1)
tail_smoke = [wisp(TT - TD * 0.12, norm(TD * 0.5 + np.array([0, 0, 1.0])), 0.6, 0.13, np.array([0, -0.25, 0.1]),
                   wiggle=0.12)]
for k_ in range(4):
    a = 2 * math.pi * k_ / 4 + 0.4
    off = ts1 * math.cos(a) + ts2 * math.sin(a)
    tail_smoke.append(wisp(TT - TD * 0.1 + off * 0.05, norm(TD * 0.4 + off * 0.28 + np.array([0, 0, 0.9])),
                           0.42 * rng.uniform(0.85, 1.15), 0.09, off * 0.12 + np.array([0, -0.18, 0.1]),
                           wiggle=0.14, phase=rng.uniform(0, 3)))
m.add("TailSmoke", fast_union(tail_smoke).subtract(tail_core.offset(-0.03)), SMOKE, material="Neon", role="glow",
      tris=400, voxel=0.0269, group="Tail", pivot=TAIL_PIVOT)

# ============================================================ occhi, bocca, naso, pupille
eyes, pupils = [], []
for sx in (1, -1):
    tilt = sx * 20
    eyes.append(H(eye_place(ellipsoid((EA, EB, EC)).rot(0, tilt, 0), sx, (0, 0.032, 0))))
    pupils.append(H(eye_place(ellipsoid((0.017, 0.02, 0.046)).rot(0, tilt * 0.5, 0), sx, (sx * 0.006, -0.012, -0.006))))
m.add("EyeGlow", fast_union(eyes), EYE_GLOW, material="Neon", role="glow", tris=260, voxel=0.0174)
m.add("ScarGlow", fast_union(scar_glow), SMOKE, material="Neon", role="glow", tris=260, voxel=0.0212)
maw = paint(core, H(cavity).offset(0.022), out=0.012, inn=0.06)
m.add("Maw", maw, MAW, role="eye", tris=420, voxel=0.0403)
nose = H(union(ellipsoid((0.088, 0.068, 0.062), (0, -0.925, 0.07)),
               ellipsoid((0.045, 0.04, 0.04), (0, -0.96, 0.02)), k=0.04).subtract(nostrils, k=0.012))
m.add("Nose", union(nose, fast_union(pupils)), MAW, role="eye", tris=320, voxel=0.0135)

# ============================================================ zanne lunghissime e file di denti aguzzi


def rim_path(w_back, w_front, y_back, y_front, y_tip, n_side=40, n_arc=16):
    """Linea dei denti di un lato (da dietro al centro davanti) nel piano XY locale."""
    pts = [(w_back + (w_front - w_back) * t, y_back + (y_front - y_back) * t) for t in np.linspace(0, 1, n_side)]
    for a in np.linspace(0, math.pi / 2, n_arc)[1:]:
        pts.append((w_front * math.cos(a), y_front - (y_front - y_tip) * math.sin(a)))
    return np.array(pts)


def tooth_row(jaw_sdf, path, z_in, down, teeth_spec, back_lean=0.22, out_lean=0.08):
    """Denti lungo 'path' (un lato, da dietro a davanti): teeth_spec = [(frazione, lunghezza, raggio)]."""
    path3 = np.array([[x, y, z_in] for x, y in path])
    rim, _ = project_many(jaw_sdf, path3, [[0, 0, down]])
    seg = np.linalg.norm(np.diff(rim, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    teeth, gums = [], []
    for fr, L, r in teeth_spec:
        s = cum[-1] * fr
        k = min(np.searchsorted(cum, s, side="right") - 1, len(seg) - 1)
        p = rim[k] + (rim[k + 1] - rim[k]) * (s - cum[k]) / max(seg[k], 1e-9)
        side = math.copysign(1.0, p[0]) if abs(p[0]) > 0.02 else 0.0
        d = norm([side * out_lean + rng.normal(0, 0.04), back_lean + rng.normal(0, 0.04), down])
        teeth.append(horn(p - d * 0.04, d, L + 0.04, r, curl=(0, 0.16, 0), n=4, r1=0.01, power=1.2))
        gums.append(ellipsoid((r * 1.5, r * 1.7, r * 1.0), tuple(p + np.array([0, 0, -down * 0.01]))))
    return teeth, gums


# (frazione lungo il bordo da dietro, lunghezza, raggio alla base): zanne da metalupo che scendono oltre il mento
UP_T = [(0.05, 0.07, 0.024), (0.18, 0.1, 0.03), (0.32, 0.075, 0.024), (0.46, 0.07, 0.022), (0.66, 0.33, 0.05),
        (0.82, 0.06, 0.02), (0.92, 0.055, 0.019), (0.99, 0.05, 0.018)]
LO_T = [(0.08, 0.07, 0.024), (0.25, 0.08, 0.026), (0.43, 0.07, 0.023), (0.64, 0.21, 0.042), (0.84, 0.05, 0.018),
        (0.97, 0.045, 0.017)]
teeth_all, gums_all = [], []
for sx in (1, -1):
    upath = rim_path(0.142, 0.08, -0.30, -0.82, -0.93)
    upath[:, 0] *= sx
    t_, g_ = tooth_row(upper, upath, -0.04, -1.0, [(f, L * rng.uniform(0.92, 1.08), r) for f, L, r in UP_T])
    teeth_all += [H(t) for t in t_]
    gums_all += [H(g) for g in g_]
    lpath = rim_path(0.132, 0.066, -0.30, -0.76, -0.85)
    lpath[:, 0] *= sx
    t_, g_ = tooth_row(lower_closed, lpath, -0.16, 1.0, [(f, L * rng.uniform(0.92, 1.08), r) for f, L, r in LO_T],
                       back_lean=0.18)
    teeth_all += [H(JW(t)) for t in t_]
    gums_all += [H(JW(g)) for g in g_]
m.add("Teeth", fast_union(teeth_all), TOOTH, role="shine", tris=880, voxel=0.0199)
tongue_l = union(ellipsoid((0.1, 0.24, 0.05), (0, -0.34, -0.155)),
                 ellipsoid((0.08, 0.12, 0.045), (0, -0.56, -0.14)), k=0.06)
tongue_l = tongue_l.subtract(capsule((0, -0.18, -0.1), (0, -0.64, -0.085), 0.015), k=0.02)
m.add("Gums", union(fast_union(gums_all, k=0.02), H(JW(tongue_l))), GUM, role="detail", tris=420, voxel=0.0295)

# ============================================================ artigli
claws = []
for tp, sc in TOES:
    claws.append(horn(tp + np.array([0, -0.045, 0.02]), (0, -1.0, -0.3), 0.17 * sc + 0.03, 0.04 * sc + 0.006,
                      curl=(0, 0, -0.55), n=5, r1=0.01))
m.add("Claws", fast_union(claws).intersect(halfspace_z(0.004, above=True)), BONE, role="detail", tris=720,
      voxel=0.0186)

# ============================================================ collare di cuoio rosso con borchie e catena spezzata
C0 = np.array([0.0, -0.62, 1.52])                 # centro del collo sotto il collare
CA = norm((0.0, -1.0, -0.15))                     # asse del collo (il collare e' un po' inclinato)
band_reg = SDF(lambda p: np.abs((p - C0.astype(np.float32)) @ CA.astype(np.float32)) - 0.07, C0 - 0.8, C0 + 0.8)
band_reg = band_reg.intersect(sphere(0.62, tuple(C0)))
collar = paint(core0, band_reg, out=0.05, inn=0.03, k=0.012)
m.add("Collar", collar, COLLAR, material="Leather", role="detail", tris=450, voxel=0.0274)

CU = norm(np.array([0.0, 0.0, 1.0]) - CA * CA[2])     # "su" nel piano del collare
CS = np.cross(CA, CU)


def radial(a):
    ar = math.radians(a)
    return CU * math.cos(ar) + CS * math.sin(ar)


iron = []
band_out = core0.offset(0.05)
for a in (-150, -120, -90, -60, 60, 90, 120, 150):
    p, nr = surf(band_out, C0, C0 + radial(a))
    iron.append(round_cone(tuple(p - nr * 0.02), tuple(p + nr * 0.13), 0.042, 0.006))    # borchia a punta
    iron.append(sphere(0.03, tuple(p + nr * 0.0 + CA * 0.045)))                          # chiodini sul bordo
    iron.append(sphere(0.03, tuple(p + nr * 0.0 - CA * 0.045)))
# anello sotto il collare (un po' verso la camera 3/4) e catena spezzata che penzola
RING_A = 168.0
rp, rn = surf(band_out, C0, C0 + radial(RING_A))
ring_c = rp + rn * 0.07
iron.append(chain_link(ring_c, rn, CA, 0.0, 0.065, 0.02))
links = []
pos = ring_c + rn * 0.06
for i in range(3):
    c = pos + np.array([0.0, -0.03, -0.13])
    # tiene la catena fuori dal petto
    dist = float(core0(c[None, :].astype(np.float32))[0])
    if dist < 0.075:
        c = c + grad(core0, c) * (0.075 - dist)
    axis = norm(c - pos + np.array([0, 0, -0.02]))
    nrm = (1.0, 0.0, 0.0) if i % 2 == 0 else tuple(np.cross(axis, (1.0, 0.0, 0.0)))
    lk = chain_link(c - axis * 0.05, axis, nrm, 0.035, 0.045, 0.019)
    if i == 2:   # l'ultima maglia e' spezzata e aperta
        lk = lk.subtract(sphere(0.04, tuple(c - axis * 0.05 + axis * 0.08)))
    links.append(lk)
    pos = c - axis * 0.05 + axis * 0.04
iron += links

m.add("Iron", fast_union(iron), IRON, material="Metal", role="detail", tris=920, voxel=0.0151)

# chiave di carica da giocattolo d'ottone piantata nella schiena
kb, kn = surf(core0, (0.0, 0.56, 1.3), (0.0, 0.6, 2.5))
kd = norm(kn + np.array([0.0, 0.3, 0.0]))
KS = np.array([1.0, 0.0, 0.0])
key = [cylinder(kb - kd * 0.02, kb + kd * 0.045, 0.11, round=0.016),                       # rondella
       capsule(kb - kd * 0.06, kb + kd * 0.4, 0.052)]                                        # perno
top = kb + kd * 0.44
key.append(sphere(0.08, tuple(top)))
for sgn in (1, -1):
    lc = top + KS * sgn * 0.19 + kd * 0.08
    lobe = ell(lc, (0.18, 0.05, 0.15), axis=kd, side=KS).subtract(ell(lc, (0.095, 0.2, 0.075), axis=kd, side=KS))
    key.append(lobe)
m.add("WindUpKey", fast_union(key), BRASS, material="Metal", role="detail", tris=500, voxel=0.0221)

# ============================================================ punti incrociati sulla cucitura del fianco
stitches = []
st_pts = resample(seam_line, 0.1)
surf_h = core0.offset(0.012)
for i in range(1, len(st_pts) - 1):
    c = st_pts[i]
    t = norm(st_pts[i + 1] - st_pts[i - 1])
    nr = grad(core0, c)
    s = np.cross(nr, t)
    for a, b in ((t + s, -t - s), (t - s, -t + s)):
        pa = on_surface(surf_h, c + a * 0.05, 0.0, 3)
        pb = on_surface(surf_h, c + b * 0.05, 0.0, 3)
        stitches.append(capsule(tuple(pa), tuple(pb), 0.02))
m.add("Stitches", fast_union(stitches), THREAD, role="detail", tris=350, voxel=0.0165)


if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
