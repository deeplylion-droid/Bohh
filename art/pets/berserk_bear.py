"""Orso Berserker (BerserkBear) - pet PRIMORDIALE (fra Segreto e Ultra), zona Foresta.

Un orso gigantesco ritto sulle zampe posteriori che ruggisce a fauci spalancate: testa protesa in
avanti, muso arricciato pieno di pieghe, file di denti aguzzi con zanne enormi su gengive scoperte,
sopracciglia pesanti e aggrottate, occhi rossi che bruciano di rabbia. Le braccia sono alzate ai lati
della testa con le zampe aperte (cuscinetti in vista) e artigli lunghissimi e uncinati; gobba e spalle
enormi, pelo irto sul collo, sulle guance e sui gomiti. Pittura di guerra rosso sangue a strisce sul
muso, sulle spalle, sugli avambracci e sulle cosce; tre graffi profondi sul petto e una cicatrice
sull'occhio brillano di rabbia (parte Neon "Rage": il gioco ci attacca le braci). Al collo una collana
di grosse zanne legate a un laccio di cuoio con perline rosse.
Tocco "toy horror": un orecchio strappato e ricucito storto con grandi punti a croce, da cui esce un
ciuffo di imbottitura, e una toppa verde bosco cucita sulla coscia.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, box, capsule, ellipsoid, euler, halfspace_z, look_matrix,  # noqa: E402
                     rot_matrix, round_cone, smax, smin, sphere, tube, union)
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
        print(f"[bear] attenzione: {len(bad)} raggi partono fuori dalla forma, es. {np.round(o[bad[0]], 3)}")
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


def wrap_curves(base, P, s, a0, a1, side, up=(0, 0, 1), lean=0.0, wob=0.0, n=14, phase=0.0):
    """Curva sulla superficie che gira attorno all'asse P alla stazione s: angoli da a0 ad a1 (gradi,
    0 = direzione 'up', positivi verso il lato 'side' = +1/-1); lean la fa scivolare lungo l'asse."""
    c, t = poly_at(P, s)
    u = norm(np.asarray(up, float) - t * float(np.dot(up, t)))
    v = np.cross(t, u)
    dirs = []
    for j, a in enumerate(np.linspace(a0, a1, n)):
        f = j / (n - 1)
        ar = math.radians(a)
        dirs.append(u * math.cos(ar) + side * v * math.sin(ar) + t * (lean * f + wob * math.sin(f * 5.0 + phase)))
    pts, _ = project_many(base, [c], dirs)
    return pts


def stripe_tube(pts, w, both=False):
    """Striscia: tubo che si assottiglia fino a una punta (o a entrambe le estremita')."""
    n = len(pts)
    radii = []
    for j in range(n):
        f = j / (n - 1)
        if both:
            r = math.sin(math.pi * min(max(f, 0.0), 1.0)) ** 0.6
        else:
            r = (0.6 + 0.4 * math.sin(math.pi * min(f * 1.6, 1.0) / 2)) * (1.0 - f ** 2.4)
        radii.append(max(w * r, 0.008))
    return tube([tuple(p) for p in pts], radii)


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
    fill = tube([tuple(p - q * w * 0.45) for p, q in zip(pts, nr)], [max(w * 0.62 * f, 0.007) for f in prof])
    return groove, fill


# ============================================================ colori
FUR = (96, 56, 34)          # pelo marrone scuro
SHAGGY = (68, 39, 26)       # pelo irto piu' scuro (collo, gobba, gomiti, guance, testa)
MUZZLE = (188, 138, 90)     # muso, orecchie interne e cuscinetti color nocciola
WARPAINT = (198, 16, 26)    # pittura di guerra rosso sangue
RAGE = (255, 40, 18)        # neon rosso-arancio
BONE = (244, 234, 208)      # artigli e zanne della collana
TOOTH = (252, 249, 238)
MAW = (34, 8, 12)           # gola, naso, pupille
GUM = (176, 46, 64)         # gengive scoperte e lingua
CORD = (140, 92, 54)        # laccio di cuoio chiaro
THREAD = (34, 16, 44)       # filo nero-viola delle cuciture
STUFF = (244, 238, 224)     # imbottitura che esce dallo strappo
PATCH = (46, 96, 58)        # toppa verde bosco

m = Model("BerserkBear", "pet")
rng = np.random.default_rng(5)

# ============================================================ testa (spazio locale: muso verso -Y)
HEAD_POS = np.array([0.0, -0.80, 3.00])
HS = 1.08                              # scala della testa
R_HEAD = euler(-12.0, -5.0, 9.0)      # muso alzato nel ruggito, girato un po' verso la camera 3/4
GAPE = 50.0                            # apertura delle fauci (gradi)
J = np.array([0.0, -0.10, -0.17])     # cerniera della mandibola
R_JAW = euler(GAPE, 0.0, 0.0)


def H(s):
    return s.scale(HS).rotate(R_HEAD).translate(HEAD_POS)


def hp(p):
    return rot_pts(R_HEAD, np.asarray(p, dtype=np.float64) * HS) + HEAD_POS


def hv(v):
    return rot_pts(R_HEAD, v)


def JW(s):
    return s.rotate(R_JAW, pivot=J)


cran = ellipsoid((0.50, 0.46, 0.43), (0, 0.04, 0.10))
jowls = [ellipsoid((0.27, 0.30, 0.26), (sx * 0.31, -0.20, -0.07)) for sx in (1, -1)]
snout = loft(-0.20, -0.92, 0.30, 0.205, 0.235, 0.15, 0.03, -0.01, r=0.1, rc=0.07, tp=0.3)
brows = [capsule((sx * 0.07, -0.48, 0.235), (sx * 0.34, -0.29, 0.32), 0.09) for sx in (1, -1)]
bridge = capsule((0, -0.40, 0.22), (0, -0.84, 0.135), 0.075)
upper = union(cran, *jowls, k=0.18)
upper = union(upper, snout, k=0.18)
upper = union(upper, *brows, bridge, k=0.1)

# orbite incavate e palpebre pesanti tagliate in diagonale (piu' basse verso il naso): sguardo furioso
EYE_D = {sx: norm((sx * 0.42, -0.88, 0.08)) for sx in (1, -1)}
EYE_C = {}
for sx in (1, -1):
    o = np.array((sx * 0.15, -0.25, 0.15))
    EYE_C[sx], _ = surf(upper, o, o + EYE_D[sx])


def eye_place(shape, sx, offset=(0.0, 0.0, 0.0)):
    """Coordinate locali dell'occhio: X di lato, -Y verso lo sguardo, Z in alto; origine sulla superficie."""
    return shape.translate(offset).rotate(look_matrix(EYE_D[sx])).translate(EYE_C[sx])


EA, EB, EC = 0.098, 0.05, 0.068
sockets = union(*[eye_place(ellipsoid((0.13, 0.085, 0.096)), sx, (0, 0.03, 0)) for sx in (1, -1)])
upper = upper.subtract(sockets, k=0.04)
LID_CUT, LID_SLOPE = 0.022, 0.5
lids = []
for sx in (1, -1):
    A, B, C = EA + 0.026, EB + 0.03, EC + 0.028

    def lid_plane(p, sx=sx):
        return (LID_CUT - LID_SLOPE * sx * p[:, 0] - p[:, 2]) / math.sqrt(1 + LID_SLOPE ** 2)

    lid = ellipsoid((A, B, C)).intersect(SDF(lid_plane, (-A, -B, -C), (A, B, C)))
    lids.append(eye_place(lid, sx, (0, 0.04, 0)))
upper = shrink(union(upper, *lids, k=0.015))

# pieghe del ringhio sul dorso del muso e ai lati del naso
wrinkles = []
for y, w in ((-0.60, 0.18), (-0.68, 0.18), (-0.76, 0.17)):
    tg = [(x, y + 0.04 * abs(x) / w, 0.0) for x in np.linspace(-w, w, 9)]
    q, _ = curve_on(upper, (0, y, -0.02), [np.array(p) + np.array((0, 0, 0.3)) for p in tg])
    wrinkles.append(tube([tuple(p) for p in q], [0.014, 0.025, 0.032, 0.034, 0.034, 0.034, 0.032, 0.025, 0.014]))
for sx in (1, -1):
    for y0 in (-0.64, -0.74):
        q, _ = curve_on(upper, (sx * 0.05, y0, 0.0),
                        [np.array((sx * (0.16 + 0.035 * j), y0 - 0.02 + 0.05 * j, 0.14 - 0.055 * j)) for j in range(5)])
        wrinkles.append(tube([tuple(p) for p in q], [0.012, 0.026, 0.03, 0.024, 0.01]))
upper_carved = upper.subtract(fast_union(wrinkles), k=0.02)

# mandibola (chiusa) poi aperta attorno alla cerniera
mand = loft(-0.04, -0.84, 0.27, 0.17, 0.11, 0.08, -0.27, -0.245, r=0.08, rc=0.06)
chin = ellipsoid((0.15, 0.09, 0.10), (0, -0.78, -0.28))
masseter = [ellipsoid((0.15, 0.24, 0.17), (sx * 0.25, -0.22, -0.30)) for sx in (1, -1)]
lower_closed = shrink(union(mand, chin, *masseter, k=0.1))
lower = JW(lower_closed)

web = pie(J, 0.30, -GAPE - 8.0, 12.0, 0.27)
head_solid = union(upper_carved, lower, k=0.08)
head_solid = shrink(union(head_solid, web, k=0.1))

# cavita' della bocca: canale superiore, canale inferiore (ruotato), gola
beta = math.radians(GAPE / 2)
n_up = np.array([0.0, -math.sin(beta), math.cos(beta)])
above_bis = plane_sdf(J, -n_up)
below_bis = plane_sdf(J, n_up)
up_ch = loft(0.02, -0.88, 0.20, 0.125, 0.5, 0.5, -0.61, -0.63, r=0.07, rc=0.1)
lo_ch = loft(0.02, -0.78, 0.19, 0.115, 0.5, 0.5, 0.275, 0.29, r=0.07, rc=0.1)
throat = ellipsoid((0.15, 0.2, 0.15), (0.0, -0.08, -0.22))
cavity = union(up_ch.intersect(above_bis), JW(lo_ch).intersect(below_bis), throat, k=0.04)
nostrils = union(*[ellipsoid((0.03, 0.05, 0.03)).rot(0, sx * 30, sx * 25).translate((sx * 0.065, -0.99, 0.085))
                   for sx in (1, -1)])


def ear_shape():
    disc = ellipsoid((0.165, 0.075, 0.155))
    cup = ellipsoid((0.115, 0.06, 0.105), (0, -0.065, 0.015))
    return disc.subtract(cup, k=0.02)


EAR_CUP = ellipsoid((0.115, 0.06, 0.105), (0, -0.065, 0.015))
# orecchio sinistro (x < 0) normale
EAR_L = ear_shape().rot(0, -22, 18).translate((-0.33, 0.06, 0.46))
EAR_CUP_L = EAR_CUP.rot(0, -22, 18).translate((-0.33, 0.06, 0.46))
# ciuffi irti fra le orecchie, piegati all'indietro (parte "ShaggyFur")
crown = [horn((x, y, 0.40), (x * 1.2, 0.8, 0.8), 0.24, 0.085, curl=(0, 0.35, -0.2), n=4, r1=0.012)
         for x, y in ((0.0, -0.1), (0.12, 0.04), (-0.12, 0.04))]
head_solid = union(head_solid, EAR_L, k=0.05)

# ============================================================ corpo (spazio Blender)
torso = union(
    ellipsoid((0.68, 0.58, 0.62), (0, 0.06, 1.26)),    # bacino
    ellipsoid((0.95, 0.68, 0.72), (0, -0.10, 1.98)),   # torace
    ellipsoid((0.84, 0.58, 0.52), (0, 0.18, 2.46)),    # gobba e spalle
    k=0.35)
belly_b = ellipsoid((0.56, 0.38, 0.46), (0, -0.28, 1.36))
pecs = [ell((sx * 0.38, -0.56, 2.14), (0.39, 0.27, 0.33), axis=(0, -0.3, 1)) for sx in (1, -1)]
traps = [ellipsoid((0.33, 0.37, 0.29), (sx * 0.43, 0.04, 2.62)) for sx in (1, -1)]
NECK_PTS = [(0, -0.04, 2.40), (0, -0.36, 2.70), (0, -0.64, 2.90)]
neck = tube(NECK_PTS, [0.52, 0.48, 0.42], k=0.1)
throat_skin = ell(hp((0.0, -0.18, -0.42)), (0.30, 0.30, 0.32), axis=hv((0, -0.3, -1.0)))

# zampe posteriori corte e massicce a gambe larghe (la sinistra avanti), piedi piatti con cinque dita
LEGS = {1: dict(hip=np.array([0.46, 0.12, 1.20]), knee=np.array([0.60, -0.08, 0.70]),
                ankle=np.array([0.60, 0.12, 0.32]), foot=np.array([0.62, -0.13, 0.15])),
        -1: dict(hip=np.array([-0.46, 0.04, 1.20]), knee=np.array([-0.62, -0.34, 0.72]),
                 ankle=np.array([-0.62, -0.16, 0.32]), foot=np.array([-0.64, -0.42, 0.15]))}
leg_parts, TOES = [], []
for sx, L in LEGS.items():
    hip, knee, ankle, foot = L["hip"], L["knee"], L["ankle"], L["foot"]
    leg_parts += [
        ell(mix(hip, knee, 0.45) + np.array([sx * 0.06, -0.02, 0.0]), (0.46, 0.48, 0.58), axis=knee - hip),  # coscia
        round_cone(knee, ankle, 0.32, 0.25),
        ell(mix(knee, ankle, 0.3) + np.array([0, 0.10, 0.0]), (0.26, 0.26, 0.31), axis=ankle - knee),        # polpaccio
        ellipsoid((0.34, 0.48, 0.20), tuple(foot)),
    ]
    for i, dx in enumerate((-0.22, -0.11, 0.0, 0.11, 0.22)):
        tp = foot + np.array([dx, -0.42 + 0.9 * dx * dx, -0.02])
        leg_parts.append(sphere(0.096, tuple(tp)))
        TOES.append(tp)
legs = union(*leg_parts, k=0.08)

# braccia d'attacco: la destra alzata in alto pronta a colpire, la sinistra protesa in avanti ad artigliare
ARM_POSE = {1: ((0.72, -0.18, 2.44), (1.24, -0.24, 2.80), (1.22, -0.48, 3.40)),
            -1: ((-0.72, -0.26, 2.40), (-1.20, -0.60, 2.34), (-1.18, -1.00, 2.86))}
ARMS, PAWS, arm_parts, CLAW_ROOTS = {}, {}, [], []
for sx in (1, -1):
    sh, el, wr = (np.array(q) for q in ARM_POSE[sx])
    ARMS[sx] = (sh, el, wr)

    arm_parts += [
        ellipsoid((0.38, 0.38, 0.38), tuple(sh + np.array([sx * 0.08, 0.0, 0.08]))),           # deltoide
        round_cone(sh, el, 0.33, 0.27),
        ell(mix(sh, el, 0.55) + np.array([0, -0.10, 0.07]), (0.23, 0.23, 0.30), axis=el - sh),   # bicipite
        round_cone(el, wr, 0.29, 0.22),
        ell(mix(el, wr, 0.35) + np.array([sx * 0.06, 0.04, 0.0]), (0.29, 0.29, 0.37), axis=wr - el),  # avambraccio
    ]
    U = norm(wr - el)
    F0 = np.array([-sx * 0.25, -1.0, 0.0])
    F = norm(F0 - U * float(F0 @ U))                         # normale del palmo (avanti e un po' verso il centro)
    S = norm(np.cross(F, U))
    P = wr + U * 0.16
    PAWS[sx] = (P, U, F, S)
    arm_parts.append(ell(P, (0.28, 0.17, 0.25), axis=U, side=S))
    for k, a in enumerate((-56.0, -28.0, 0.0, 28.0, 56.0)):
        ar = math.radians(a)
        dk = U * math.cos(ar) + S * math.sin(ar)
        ln = 0.31 if abs(a) < 40 else 0.27
        b0 = P + dk * 0.12
        b1 = P + dk * ln + F * 0.06                          # dita piegate in avanti, verso chi guarda
        arm_parts.append(round_cone(b0, b1, 0.10, 0.088))
        CLAW_ROOTS.append((b1, dk, F, abs(a) < 40))
arms = union(*arm_parts, k=0.07)

core = union(torso, belly_b, *pecs, *traps, k=0.2)
core = union(core, neck, k=0.2)
core = union(core, H(head_solid), k=0.14)
core = union(core, throat_skin, k=0.18)
core = union(core, legs, k=0.14)
core = union(core, arms, k=0.12)
core = core.subtract(H(cavity), k=0.03)
core = core.subtract(H(nostrils), k=0.02)
core0 = shrink(core.intersect(halfspace_z(0.0, above=True)))


# ============================================================ pelo irto: collare, guance, gomiti, gobba
def tufts(base, origin, targets, flow, L, r0, lean=0.6, sink=0.05):
    """Ciuffi di pelo a punta: dalla superficie (raggi da origin verso targets) seguono la direzione 'flow'."""
    pts, nrs = curve_on(base, origin, targets)
    out = []
    for p, nr in zip(pts, nrs):
        fl = np.asarray(flow, float)
        fl = fl - nr * float(fl @ nr)
        fl = norm(fl) if np.linalg.norm(fl) > 1e-6 else nr
        d = norm(nr * (1 - lean) + fl * lean)
        out.append(horn(p - nr * sink, d, L * rng.uniform(0.88, 1.12), r0, curl=tuple(fl * 0.3 - nr * 0.12), n=4,
                        r1=0.014))
    return out


fur = []
# collare di pelo attorno al collo (lati e dietro): punte verso il basso e all'indietro
NC = np.array([0.0, -0.16, 2.58])
for ring, (dz, n_r, L, r0) in enumerate(((0.12, 6, 0.4, 0.14), (-0.14, 5, 0.36, 0.13))):
    tg = []
    for i in range(n_r):
        a = math.radians(68 + 112 * (i + 0.5 * ring) / (n_r - 1 + ring))
        for sgn in ((1, -1) if a < math.radians(179) else (1,)):
            tg.append(NC + np.array([sgn * math.sin(a), -math.cos(a), dz]))
    fur += tufts(core0, NC, tg, (0, 0.4, -1.0), L, r0, lean=0.7)
# gobba: ciuffi che puntano all'indietro e in alto
tg = [np.array((x, 1.0, 2.65 + z)) for x, z in ((0.0, 0.25), (0.3, 0.1), (-0.3, 0.1), (0.15, -0.2), (-0.15, -0.2))]
fur += tufts(core0, (0, 0.1, 2.4), tg, (0, 1.0, 0.5), 0.32, 0.12)
# guance: ciuffi che scappano all'indietro
for sx in (1, -1):
    tg = [hp((sx * 0.9, -0.05 + dy, -0.08 + dz)) for dy, dz in ((0.06, 0.0), (-0.1, -0.2))]
    fur += tufts(core0, hp((sx * 0.25, -0.2, -0.05)), tg, hv((sx * 0.6, 1.0, -0.3)), 0.3, 0.1, lean=0.72)
# gomiti e avambracci: ciuffi verso il basso
for sx, (sh, el, wr) in ARMS.items():
    tg = [el + np.array([sx * 0.3, 0.3, -0.35]), el + np.array([sx * 0.0, 0.45, -0.3]),
          mix(el, wr, 0.4) + np.array([sx * 0.35, 0.35, 0.0]), mix(el, wr, 0.45) + np.array([-sx * 0.1, 0.45, 0.0])]
    fur += tufts(core0, mix(el, wr, 0.15), tg, (sx * 0.25, 0.3, -1.0), 0.34, 0.12)
# (niente ciuffi alle caviglie: i piedi restano puliti)
fur += [H(c) for c in crown]

# ============================================================ cicatrici di artigli (solchi che brillano)
scar_cut, scar_glow = [], []
for i in range(3):
    dx = 0.15 * i
    g, f = slash(core0, (0.0, -0.1, 1.7), (0.56 - dx, -0.5, 2.0 - 0.02 * i), (0.06 - dx, -0.6, 1.26 - 0.02 * i),
                 n=12, w=0.045)
    scar_cut.append(g)
    scar_glow.append(f)
# cicatrice che taglia l'occhio sinistro (x < 0)
g, f = slash(core0, hp((-0.1, -0.15, 0.1)), hp((-0.30, -0.36, 0.52)), hp((-0.17, -0.52, -0.12)), n=10, w=0.032)
scar_cut.append(g)
scar_glow.append(f)
# graffi sull'avambraccio destro
sh, el, wr = ARMS[1]
for i in range(2):
    o = mix(el, wr, 0.5)
    g, f = slash(core0, o, mix(el, wr, 0.28 + 0.16 * i) + np.array([0.2, -0.4, 0.0]),
                 mix(el, wr, 0.55 + 0.16 * i) + np.array([-0.2, -0.4, 0.0]), n=8, w=0.034)
    scar_cut.append(g)
    scar_glow.append(f)
core = core0.subtract(fast_union(scar_cut), k=0.02)


def vein(base, origin, p0, d0, n=6, step=0.06, turn=0.45, r0=0.026):
    """Vena di rabbia: linea serpeggiante sulla superficie che si assottiglia."""
    pts, d = [np.asarray(p0, float)], norm(d0)
    for _ in range(n):
        d = norm(d + rng.normal(0, turn, 3) * 0.5)
        pts.append(pts[-1] + d * step)
    q, nr = curve_on(base, origin, pts)
    q = [p + nn * 0.004 for p, nn in zip(q, nr)]
    return tube([tuple(p) for p in q], [max(r0 * (1 - j / len(q)) ** 0.8, 0.012) for j in range(len(q))])


# vene incandescenti che partono dai graffi del petto
scar_glow += [vein(core, (0.0, -0.1, 1.7), p0, d0) for p0, d0 in (
    ((0.62, -0.42, 2.02), (0.4, 0.3, 0.8)), ((0.40, -0.55, 2.06), (0.0, 0.0, 1.0)), ((0.04, -0.62, 1.22), (-0.3, 0, -1)),
    ((-0.12, -0.6, 1.24), (-0.8, 0.1, -0.4)), ((0.3, -0.6, 1.62), (1.0, 0.2, -0.2)))]


# ============================================================ orecchio destro strappato e ricucito storto
R0_EAR = euler(0, 22, -18)
T0_EAR = np.array([0.33, 0.06, 0.46])
HINGE = rot_pts(R0_EAR, (0.0, 0.065, -0.075)) + T0_EAR     # bordo dietro in basso: e' rimasto attaccato
EAR_N = grad(upper, rot_pts(R0_EAR, (0.0, 0.0, -0.075)) + T0_EAR)
# ricucito storto: piegato all'indietro (lo strappo si apre davanti, verso chi guarda) e girato nel suo piano
R_FLOP = rot_matrix(EAR_N, 16.0) @ rot_matrix(rot_pts(R0_EAR, (1.0, 0.0, 0.0)), -40.0)
EAR_LIFT = EAR_N * 0.03


def ear_pt(p):
    """Punto dell'orecchio strappato (coordinate locali dell'orecchio) nello spazio della testa."""
    return rot_pts(R_FLOP, rot_pts(R0_EAR, p) + T0_EAR, HINGE) + EAR_LIFT


def ear_place(s):
    return s.rotate(R0_EAR).translate(T0_EAR).rotate(R_FLOP, pivot=HINGE).translate(EAR_LIFT)


ear_r = ear_place(ear_shape().intersect(halfspace_z(-0.075, above=True)))   # bordo strappato piatto
EAR_CUP_R = ear_place(EAR_CUP)
body = union(core, H(ear_r))
# la pelle e' divisa in due parti dalla stessa forma (sovrapposte di poco: la giunta non si vede), cosi' la testa
# ha piu' triangoli del corpo
HEAD_ZONE = H(ellipsoid((0.86, 1.02, 0.92), (0.0, -0.30, -0.02)))
m.add("Body", body.subtract(HEAD_ZONE.offset(-0.03)), FUR, tris=3500, voxel=0.051)
m.add("Head", body.intersect(HEAD_ZONE.offset(0.03)), FUR, tris=2600, voxel=0.037)
shaggy = fast_union(fur).subtract(core0.offset(-0.035))        # la radice dei ciuffi dentro il corpo non serve
m.add("ShaggyFur", shaggy.intersect(halfspace_z(0.004, above=True)), SHAGGY, role="detail", tris=1900, voxel=0.0395)



# ============================================================ muso nocciola, orecchie interne, cuscinetti
muzzle_reg = union(
    ellipsoid((0.30, 0.42, 0.26), (0, -0.82, 0.0)),            # muso
    JW(ellipsoid((0.25, 0.48, 0.16), (0, -0.62, -0.30))),       # mento e labbro inferiore
    k=0.04).subtract(cavity.offset(0.05))                        # non dentro la bocca

cups = union(EAR_CUP_L.offset(0.03), EAR_CUP_R.offset(0.03))
pads = [ell(P + F * 0.15 - U * 0.02, (0.2, 0.12, 0.17), axis=U, side=S) for P, U, F, S in PAWS.values()]
pads += [sphere(0.07, tuple(b1 + F * 0.07)) for b1, dk, F, big in CLAW_ROOTS]      # polpastrelli
muzzle = union(paint(core, H(muzzle_reg), out=0.018, inn=0.06),
               paint(body, H(cups), out=0.016, inn=0.05),
               paint(core, fast_union(pads), out=0.018, inn=0.06))
m.add("Muzzle", muzzle, MUZZLE, role="detail", tris=900, voxel=0.0378)

# ============================================================ pittura di guerra rosso sangue
paint_l = []
for sx in (1, -1):
    # due strisce sulle guance, dall'occhio verso la mascella
    for a, b in (((0.27, -0.44, 0.06), (0.52, -0.10, -0.08)), ((0.25, -0.46, -0.05), (0.47, -0.14, -0.23))):
        pts, _ = curve_on(core, hp((sx * 0.12, -0.2, -0.02)), [hp((sx * p[0], p[1], p[2])) for p in line_pts(a, b, 9)])
        paint_l.append(stripe_tube(pts, 0.05, both=True))
    sh, el, wr = ARMS[sx]
    # due fasce sull'avambraccio, vicino al polso
    for s in (0.6, 0.8):
        P_ = polyline([el, wr])
        pts = wrap_curves(core, P_, P_[3][-1] * s, -180, 180, 1, up=(0, -1, 0), n=24)
        paint_l.append(tube([tuple(p) for p in pts], 0.042))
    # due strisce sulla coscia
    L = LEGS[sx]
    for j in range(2):
        c = mix(L["hip"], L["knee"], 0.5) + np.array([0, 0, 0.1 - 0.2 * j])
        tg = line_pts(c + np.array([-sx * 0.25, -0.5, 0.06]), c + np.array([sx * 0.5, -0.4, -0.1]), 9)
        pts, _ = curve_on(core, c, tg)
        paint_l.append(stripe_tube(pts, 0.05, both=True))
# striscia in mezzo alla fronte, dal naso alla nuca
pts, _ = curve_on(core, hp((0, -0.15, 0.05)), [hp(p) for p in line_pts((0, -0.74, 0.22), (0, -0.12, 0.54), 10)])
paint_l.append(stripe_tube(pts[::-1], 0.055))
war = paint(core, fast_union(paint_l), out=0.018, inn=0.06)

# ============================================================ collana di zanne (laccio a U sul petto)
origins, dirs = [], []
for t in np.linspace(-1, 1, 25):
    z = 2.12 + 0.36 * t * t

    o = np.array((0.4 * t, -0.25, z))
    origins.append(o)
    dirs.append(np.array((0.8 * t, -1.0, 0.05)))
cord_p, cord_n = project_many(core0, origins, dirs)
cord_c = [p + nn * 0.034 for p, nn in zip(cord_p, cord_n)]
cord = [tube([tuple(p) for p in cord_c], 0.036)]
fangs, beads = [], []
mid_i = len(cord_c) // 2
for j, (di, Lf) in enumerate(((-6, 0.2), (-4, 0.25), (-2, 0.3), (0, 0.35), (2, 0.3), (4, 0.25), (6, 0.2))):
    i = mid_i + di
    p, nn = cord_c[i], cord_n[i]
    d = norm(np.array([0, 0, -1.0]) + nn * 0.5)
    fangs.append(horn(p + nn * 0.012 + np.array([0, 0, -0.02]), d, Lf * 1.25, 0.078 if di == 0 else 0.068,
                      curl=tuple(nn * 0.3), n=5, r1=0.007, power=1.2))

    cord.append(sphere(0.05, tuple(p + nn * 0.01)))                        # nodo attorno alla radice
    if j < 6:
        beads.append(sphere(0.042, tuple(cord_c[i + 1])))
m.add("WarPaint", union(war, fast_union(beads)), WARPAINT, role="detail", tris=1150, voxel=0.0315)
m.add("Necklace", fast_union(cord), CORD, role="detail", tris=380, voxel=0.022)

# ============================================================ denti aguzzi su gengive scoperte


def rim_path(w_back, w_front, y_back, y_front, y_tip, n_side=40, n_arc=16):
    """Linea dei denti di un lato (da dietro al centro davanti) nel piano XY locale."""
    pts = [(w_back + (w_front - w_back) * t, y_back + (y_front - y_back) * t) for t in np.linspace(0, 1, n_side)]
    for a in np.linspace(0, math.pi / 2, n_arc)[1:]:
        pts.append((w_front * math.cos(a), y_front - (y_front - y_tip) * math.sin(a)))
    return np.array(pts)


def tooth_row(jaw_sdf, path, z_in, down, teeth_spec, back_lean=0.25, out_lean=0.08):
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
        side = math.copysign(1.0, p[0]) if abs(p[0]) > 0.03 else 0.0
        d = norm([side * out_lean + rng.normal(0, 0.05), back_lean + rng.normal(0, 0.05), down])
        teeth.append(horn(p - d * 0.05, d, L + 0.05, r, curl=(0, 0.18, 0), n=4, r1=0.005, power=1.2))
        gums.append(ellipsoid((r * 1.5, r * 1.6, r * 0.95), tuple(p + np.array([0, 0, -down * 0.012]))))
    return teeth, gums


# (frazione lungo il bordo da dietro, lunghezza, raggio alla base)
UP_T = [(0.05, 0.07, 0.03), (0.2, 0.09, 0.034), (0.36, 0.1, 0.036), (0.56, 0.33, 0.068), (0.74, 0.08, 0.03),
        (0.87, 0.075, 0.028), (0.98, 0.07, 0.026)]
LO_T = [(0.06, 0.07, 0.03), (0.24, 0.09, 0.033), (0.42, 0.09, 0.034), (0.62, 0.25, 0.06), (0.8, 0.07, 0.027),

        (0.96, 0.065, 0.025)]
teeth_all, gums_all = [], []
for sx in (1, -1):
    upath = rim_path(0.235, 0.165, -0.34, -0.74, -0.88)
    upath[:, 0] *= sx
    t_, g_ = tooth_row(upper, upath, -0.08, -1.0, [(f, L * rng.uniform(0.92, 1.08), r) for f, L, r in UP_T])
    teeth_all += [H(t) for t in t_]
    gums_all += [H(g) for g in g_]
    lpath = rim_path(0.22, 0.15, -0.32, -0.68, -0.80)
    lpath[:, 0] *= sx
    t_, g_ = tooth_row(lower_closed, lpath, -0.22, 1.0, [(f, L * rng.uniform(0.92, 1.08), r) for f, L, r in LO_T],
                       back_lean=0.2)
    teeth_all += [H(JW(t)) for t in t_]
    gums_all += [H(JW(g)) for g in g_]
m.add("Teeth", fast_union(teeth_all), TOOTH, role="shine", tris=950, voxel=0.0205)

# lingua grossa con il solco centrale (stessa parte delle gengive)
tongue_l = union(ellipsoid((0.15, 0.30, 0.075), (0, -0.36, -0.215)),
                 ellipsoid((0.12, 0.16, 0.07), (0, -0.62, -0.19)).rot(-12, 0, 0, pivot=(0, -0.62, -0.19)), k=0.08)
tongue_l = tongue_l.subtract(capsule((0, -0.2, -0.13), (0, -0.74, -0.10), 0.02), k=0.025)
m.add("Gums", union(fast_union(gums_all, k=0.025), H(JW(tongue_l))), GUM, role="detail", tris=450, voxel=0.033)

# ============================================================ occhi infuocati, bocca, naso, pupille
maw = paint(core, H(cavity).offset(0.025), out=0.012, inn=0.07)
nose = H(union(ellipsoid((0.15, 0.095, 0.095), (0, -0.92, 0.085)),
               ellipsoid((0.07, 0.05, 0.05), (0, -0.98, 0.02)), k=0.05).subtract(nostrils, k=0.015))
eyes, pupils = [], []
for sx in (1, -1):
    tilt = sx * 16
    eyes.append(H(eye_place(ellipsoid((EA, EB, EC)).rot(0, tilt, 0), sx, (0, 0.035, 0))))
    pupils.append(H(eye_place(ellipsoid((0.02, 0.022, 0.056)).rot(0, tilt * 0.5, 0), sx, (sx * 0.008, -0.016, -0.006))))
m.add("Maw", maw, MAW, role="eye", tris=480, voxel=0.04)
m.add("Nose", union(nose, fast_union(pupils)), MAW, role="eye", tris=320, voxel=0.017)

m.add("Rage", fast_union(eyes + scar_glow), RAGE, material="Neon", role="glow", tris=700, voxel=0.0235)

# ============================================================ artigli enormi (mani e piedi) e zanne della collana
claws = []
for b1, dk, F, big in CLAW_ROOTS:
    L = 0.5 if big else 0.42
    d = norm(dk * 0.9 + F * 0.35)
    claws.append(horn(b1 + dk * 0.03, d, L, 0.08 if big else 0.07, curl=tuple(F * 0.75 - dk * 0.3), n=7,
                      r1=0.007, power=1.15))
for tp in TOES:
    claws.append(horn(tp + np.array([0, -0.06, 0.02]), (0, -1.0, -0.2), 0.22, 0.055, curl=(0, 0, -0.5), n=4,
                      r1=0.006))
m.add("Claws", fast_union(claws + fangs).intersect(halfspace_z(0.004, above=True)), BONE, role="detail", tris=1500,
      voxel=0.0295)

# ============================================================ toy horror: punti a croce, imbottitura, toppa
ear_w = H(ear_r)
along = norm(hv(rot_pts(R_FLOP, rot_pts(R0_EAR, (1.0, 0.0, 0.0)))))
fwd = norm(hv(rot_pts(R0_EAR, (0.0, -1.0, 0.0))))                          # verso in cui guarda l'orecchio
stitches = []
for xe in (-0.11, 0.0, 0.11):
    b = on_surface(ear_w, hp(ear_pt((xe, -0.075, 0.035))), 0.006, 4)       # faccia davanti dell'orecchio
    ps = on_surface(core, hp(ear_pt((xe, -0.075, -0.075))), 0.0, 4)
    a = on_surface(core, ps + fwd * 0.08, 0.006, 4)                          # cranio davanti allo strappo
    for sgn in (1, -1):
        stitches.append(capsule(tuple(a - along * sgn * 0.035), tuple(b + along * sgn * 0.035), 0.022))
# imbottitura che spunta da tutto lo strappo, fra il cranio e il bordo davanti staccato dell'orecchio
stuff = []
for xe in (-0.13, -0.065, 0.0, 0.065, 0.13):
    pe = hp(ear_pt((xe, -0.045, -0.075)))
    ps = on_surface(core, pe, 0.0, 4)
    gap = float(np.linalg.norm(pe - ps))
    c0 = mix(pe, ps, 0.5) + fwd * 0.015
    r0 = min(gap * 0.5 + 0.035, 0.085)
    stuff.append(sphere(r0, tuple(c0)))
    for j in range(3):
        off = norm(rng.normal(0, 1.0, 3)) * r0 * rng.uniform(0.5, 0.9)
        stuff.append(sphere(r0 * rng.uniform(0.5, 0.7), tuple(c0 + off)))
# il ciuffo piu' grosso esce all'estremita' esterna dello strappo
c0 = hp(ear_pt((0.19, -0.06, -0.1)))
for j in range(7):
    off = norm(rng.normal(0, 1.0, 3) + fwd * 0.8) * 0.07 * rng.uniform(0.4, 1.0)
    stuff.append(sphere(0.06 * rng.uniform(0.7, 1.1), tuple(c0 + off)))
m.add("Stuffing", union(*stuff, k=0.03), STUFF, material="Fabric", role="detail", tris=400, voxel=0.0163)


# toppa verde bosco cucita sulla coscia sinistra (x < 0), con il filo a trattini tutt'attorno
L = LEGS[-1]
pf = Frame(core, mix(L["hip"], L["knee"], 0.4), (-0.35, -1.0, 0.1), sink=0.0)
PATCH_ROT = 12.0
patch_reg = pf.place(box((0.18, 0.3, 0.16), round=0.04).rot(0, PATCH_ROT, 0))
m.add("Patch", paint(core, patch_reg, out=0.028, inn=0.05), PATCH, material="Fabric", role="detail", tris=240,
      voxel=0.024)
corners = [(-0.155, -0.135), (0.155, -0.135), (0.155, 0.135), (-0.155, 0.135)]
outline = []
ar = math.radians(PATCH_ROT)
for (u0, v0), (u1, v1) in zip(corners, corners[1:] + corners[:1]):
    for t in np.linspace(0, 1, 5)[:-1]:
        u, v = u0 * (1 - t) + u1 * t, v0 * (1 - t) + v1 * t
        uu, vv = u * math.cos(ar) + v * math.sin(ar), -u * math.sin(ar) + v * math.cos(ar)
        outline.append(on_surface(core.offset(0.028), pf.point((uu, 0.0, vv)), 0.0, 4))
outline.append(outline[0])
pts = resample(outline, 0.027)
for i in range(0, len(pts) - 2, 4):
    stitches.append(capsule(tuple(pts[i]), tuple(pts[i + 2]), 0.018))
m.add("Stitches", fast_union(stitches), THREAD, role="detail", tris=400, voxel=0.017)



if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
