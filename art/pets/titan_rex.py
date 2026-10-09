"""Titano Rex (TitanRex) - pet ULTRA, il livello piu' alto.

Un tirannosauro titanico evaso dalla sua prigione, in posa d'attacco: corpo proteso in avanti,
testa che si lancia verso chi guarda con le fauci spalancate (gola scura, lingua enorme, file di
denti frastagliati color osso su gengive scoperte), cranio massiccio con arcate sopraccigliari
pesanti e corna nere, muso ringhiante pieno di pieghe, zampe enormi e muscolose con artigli
giganti, braccine corte ma cattive alzate, coda spessa sollevata. Pelle rosso sangue a strisce nere
da tigre, pancia rosso polvere a placche, spine e scudi ossei neri lungo la schiena. Occhi,
cicatrici di artigli e vene brillano di rabbia (parte Neon "Rage": il gioco ci attacca braci e
vapore). Tocco "toy horror": cucitura a punti incrociati sul petto e una cavigliera di ferro con
la catena spezzata.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, capsule, cylinder, ellipsoid, euler, halfspace_z, look_matrix, prism,  # noqa: E402
                     round_cone, smax, smin, sphere, tube, union)
from lib.toy import Model  # noqa: E402


# ============================================================ helper (lib/ non si modifica: copiati/adattati qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


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
        print(f"[titan] attenzione: {len(bad)} raggi partono fuori dalla forma, es. {np.round(o[bad[0]], 3)}")
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


def paint(core, region, out=0.016, inn=0.035, margin=0.05):
    """Strato di "vernice" sottile (guscio fra -inn e +out attorno a core) dentro 'region'.

    Come core.offset(out).subtract(core.offset(-inn)).intersect(region), ma valuta core solo
    vicino alla regione (molto piu' veloce sulle forme complesse).
    """
    def f(p):
        r = region(p)
        d = np.maximum(r, margin).astype(np.float32)
        idx = np.nonzero(r < margin)[0]
        if len(idx):
            c = core(p[idx])
            d[idx] = np.maximum(np.maximum(c - out, -c - inn), r[idx])
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
    return ellipsoid(radii).rotate(orient(axis, side)).translate(c)


def loft(y0, y1, w0, w1, h0, h1, z0, z1, r, rc=0.0, tp=0.0):
    """Box arrotondato che si restringe lungo Y (da y0 a y1): mezza larghezza w, mezza altezza h, centro z.

    r arrotonda gli spigoli della sezione, rc i bordi delle due facce di testa, tp stringe la sezione
    in alto (trapezio: la faccia superiore e' larga (1 - tp) volte quella inferiore).
    """
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


def blade(L, h, th, curl=0.45, sweep=0.25):
    """Spina a pinna di squalo nel piano locale XY (X verso la coda, Y in alto), spessore th lungo Z.

    Bordo davanti convesso, bordo dietro concavo, punta piegata all'indietro; si assottiglia in cima.
    """
    tip = np.array([curl * h, h])
    a, b = np.array([-L / 2, -0.08]), np.array([L / 2, -0.08])
    front = [a * (1 - t) ** 2 + 2 * (1 - t) * t * np.array([-L * (0.5 - sweep), h * 0.75]) + t * t * tip
             for t in np.linspace(0, 1, 10)]
    back = [tip * (1 - t) ** 2 + 2 * (1 - t) * t * np.array([curl * h * 0.55 + L * 0.2, h * 0.3]) + t * t * b
            for t in np.linspace(0, 1, 10)[1:]]
    poly = [tuple(p) for p in front + back]
    pr = prism(poly, -th, th)

    def f(p):
        half = th * 0.5 * (1.0 - 0.7 * np.clip(p[:, 1] / h, 0.0, 1.0))
        return smax(pr(p), np.abs(p[:, 2]) - half, 0.03) - 0.004

    return SDF(f, pr.lo - 0.01, pr.hi + 0.01)


def place(shape, origin, x_axis, y_axis):
    """Porta una forma locale nel mondo: X locale -> x_axis, Y locale -> y_axis (ortogonalizzati)."""
    y = norm(y_axis)
    x = norm(np.asarray(x_axis, float) - y * float(np.dot(x_axis, y)))
    z = np.cross(x, y)
    return shape.rotate(np.stack([x, y, z], axis=1).astype(np.float32)).translate(origin)


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


def closest_on(P, p):
    """Per ogni punto: ascissa s del punto piu' vicino della polilinea, il punto e l'indice del segmento."""
    pts, seg, ln, cum = P
    best = np.full(len(p), np.inf)
    s_out = np.zeros(len(p))
    c_out = np.zeros((len(p), 3))
    k_out = np.zeros(len(p), dtype=int)
    for k in range(len(seg)):
        t = np.clip(((p - pts[k]) @ seg[k]) / (ln[k] ** 2), 0.0, 1.0)
        c = pts[k] + t[:, None] * seg[k]
        d = np.linalg.norm(p - c, axis=1)
        msk = d < best
        best[msk] = d[msk]
        s_out[msk] = cum[k] + t[msk] * ln[k]
        c_out[msk] = c[msk]
        k_out[msk] = k
    return s_out, c_out, k_out


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
    """Striscia da tigre: tubo che si assottiglia fino a una punta (o a entrambe le estremita')."""
    n = len(pts)
    radii = []
    for j in range(n):
        f = j / (n - 1)
        if both:
            r = math.sin(math.pi * min(max(f, 0.0), 1.0)) ** 0.7
        else:
            r = (0.55 + 0.45 * math.sin(math.pi * min(f * 1.6, 1.0) / 2)) * (1.0 - f ** 2.2)
        radii.append(max(w * r, 0.007))
    return tube([tuple(p) for p in pts], radii)


def stitch_row(sdf, pts, dash=0.075, gap=0.05, r=0.017, cross=False, cross_len=0.11, sink=0.35, closed=False):
    """Cucitura sulla superficie: trattini lungo la linea, oppure punti trasversali (cross=True)."""
    pts = list(pts) + ([pts[0]] if closed else [])
    pts = resample(pts, (dash + gap) * (0.8 if cross else 1.0))
    out = []
    for i in range(len(pts) if cross else len(pts) - 1):
        if cross:
            p = pts[i]
            t = norm(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)])
            side = norm(np.cross(t, grad(sdf, p)))
            a = on_surface(sdf, p - side * cross_len / 2, -r * sink, 3)
            b = on_surface(sdf, p + side * cross_len / 2, -r * sink, 3)
        else:
            a = on_surface(sdf, pts[i], -r * sink, 2)
            b = on_surface(sdf, pts[i] + (pts[i + 1] - pts[i]) * dash / (dash + gap), -r * sink, 2)
        out.append(capsule(tuple(a), tuple(b), r))
    return out


# ============================================================ colori
SKIN = (138, 12, 18)        # cremisi scuro, rosso sangue
STRIPE = (22, 10, 14)       # strisce nere da tigre
BELLY = (192, 96, 82)       # pancia rosso polvere
BONE = (246, 236, 212)      # denti e artigli color osso
SPIKE = (30, 22, 26)        # spine, corna e scudi neri
MAW = (34, 5, 10)           # gola e interno della bocca
GUM = (170, 50, 72)         # gengive scoperte
TONGUE = (164, 44, 62)      # lingua carnosa
RAGE = (255, 40, 16)        # neon rosso-arancio
THREAD = (16, 9, 11)
IRON = (86, 82, 88)

m = Model("TitanRex", "pet")
rng = np.random.default_rng(11)

# ============================================================ testa (spazio locale: origine sulla nuca, muso verso -Y)
HEAD_POS = np.array([0.0, -1.16, 2.92])
HS = 1.2                                 # scala della testa
R_HEAD = euler(6.0, 9.0, 13.0)          # muso un po' basso, testa inclinata e girata verso la camera 3/4
GAPE = 54.0                              # apertura delle fauci (gradi)
J = np.array([0.0, -0.18, -0.24])       # cerniera della mandibola
R_JAW = euler(GAPE, 0.0, 0.0)


def H(s):
    return s.scale(HS).rotate(R_HEAD).translate(HEAD_POS)


def hp(p):
    return rot_pts(R_HEAD, np.asarray(p, dtype=np.float64) * HS) + HEAD_POS


def hv(v):
    return rot_pts(R_HEAD, v)


def JW(s):
    return s.rotate(R_JAW, pivot=J)


# --- cranio con muscoli temporali e cresta, guance larghe, muso squadrato, arcate sopraccigliari
cran = ellipsoid((0.46, 0.44, 0.36), (0, -0.30, 0.13))
temporal = [ellipsoid((0.21, 0.27, 0.15), (sx * 0.19, -0.22, 0.33)) for sx in (1, -1)]
crest = capsule((0, 0.0, 0.36), (0, -0.50, 0.40), 0.05)
jowls = [ellipsoid((0.22, 0.30, 0.26), (sx * 0.35, -0.36, -0.07)) for sx in (1, -1)]
snout = loft(-0.40, -1.52, 0.37, 0.245, 0.30, 0.17, 0.07, -0.055, r=0.07, rc=0.05, tp=0.54)
brows = [capsule((sx * 0.08, -0.93, 0.33), (sx * 0.42, -0.64, 0.39), 0.10) for sx in (1, -1)]
lower_lids = [capsule((sx * 0.17, -0.90, 0.12), (sx * 0.42, -0.66, 0.13), 0.042) for sx in (1, -1)]
nasal = [capsule((sx * 0.07, -1.42, 0.14), (sx * 0.09, -0.98, 0.27), 0.05) for sx in (1, -1)]
nost_bumps = [ellipsoid((0.05, 0.07, 0.035), (sx * 0.14, -1.46, 0.085)) for sx in (1, -1)]
rugs = [ellipsoid((0.055, 0.06, 0.04), (0.03 * ((i % 2) * 2 - 1), y, 0.25 + 0.2 * (y + 1.0)))
        for i, y in enumerate((-1.06, -1.16, -1.26))]
upper = union(cran, *temporal, *jowls, k=0.16)
upper = union(upper, crest, k=0.08)
upper = union(upper, snout, k=0.16)
upper = union(upper, *brows, *lower_lids, k=0.1)
upper = union(upper, *nasal, *nost_bumps, *rugs, k=0.05)

# orbite: incavate verso avanti-fuori, cosi' lo sguardo arriva anche di fronte
EYE_D = {sx: norm((sx * 0.52, -0.82, 0.10)) for sx in (1, -1)}
EYE_C = {}
for sx in (1, -1):
    EYE_C[sx], _ = surf(upper, (sx * 0.08, -0.62, 0.22), np.array((sx * 0.08, -0.62, 0.22)) + EYE_D[sx])


def eye_place(shape, sx, offset=(0.0, 0.0, 0.0)):
    """Coordinate locali dell'occhio: X di lato, -Y verso lo sguardo, Z in alto; origine sulla superficie."""
    return shape.translate(offset).rotate(look_matrix(EYE_D[sx])).translate(EYE_C[sx])


sockets = union(*[eye_place(ellipsoid((0.16, 0.1, 0.105)), sx, (0, 0.02, 0)) for sx in (1, -1)])
upper = upper.subtract(sockets, k=0.05)
# palpebre superiori pesanti tagliate in diagonale (piu' basse verso il muso): occhi socchiusi e furiosi
EA, EB, EC = 0.125, 0.06, 0.075
LID_CUT, LID_SLOPE = 0.012, 0.42
lids, lid_lines = [], []
for sx in (1, -1):
    A, B, C = EA + 0.028, EB + 0.03, EC + 0.03

    def lid_plane(p, sx=sx):
        return (LID_CUT - LID_SLOPE * sx * p[:, 0] - p[:, 2]) / math.sqrt(1 + LID_SLOPE ** 2)

    lid = ellipsoid((A, B, C)).intersect(SDF(lid_plane, (-A, -B, -C), (A, B, C)))
    lids.append(eye_place(lid, sx, (0, 0.035, 0)))
    pts = []
    for x in np.linspace(-A * 0.97, A * 0.97, 15):
        z = LID_CUT - LID_SLOPE * sx * x
        q = 1 - (x / A) ** 2 - (z / C) ** 2
        if q > 0.02:
            pts.append((x, 0.035 - B * math.sqrt(q), z))
    lid_lines.append(eye_place(tube(pts, 0.016), sx))
upper = shrink(union(upper, *lids, k=0.015))

# pieghe del ringhio: solchi trasversali sul dorso del muso e diagonali sui fianchi del naso
wrinkles = []
for y, w in ((-1.10, 0.19), (-1.19, 0.2), (-1.28, 0.19)):
    pts = [(x, y + 0.03 * abs(x) / w, 0.0) for x in np.linspace(-w, w, 9)]
    q, _ = project_many(upper, [(0, y, 0.0)] * 9, [np.array(p) - np.array((0, y, -0.25)) for p in pts])
    wrinkles.append(tube([tuple(p) for p in q], [0.014, 0.024, 0.03, 0.03, 0.026, 0.03, 0.03, 0.024, 0.014]))
for sx in (1, -1):
    for y0 in (-1.26, -1.36):
        q, _ = project_many(upper, [(sx * 0.05, y0 + 0.1, 0.02)] * 6,
                            [np.array((sx * (0.2 + 0.03 * j), y0 + 0.06 * j, 0.14 - 0.045 * j)) for j in range(6)])
        wrinkles.append(tube([tuple(p) for p in q], [0.012, 0.022, 0.026, 0.024, 0.018, 0.01]))
upper_carved = upper.subtract(fast_union(wrinkles), k=0.02)

# --- mandibola (chiusa) poi aperta attorno alla cerniera
mand = loft(-0.02, -1.36, 0.34, 0.235, 0.23, 0.125, -0.46, -0.35, r=0.1, rc=0.07)
chin = ellipsoid((0.22, 0.11, 0.13), (0, -1.32, -0.37))
masseter = [ellipsoid((0.17, 0.28, 0.21), (sx * 0.30, -0.30, -0.42)) for sx in (1, -1)]
lower_closed = shrink(union(mand, chin, *masseter, k=0.12))
lower = JW(lower_closed)

# --- pelle che unisce le fauci dietro (angolo della bocca)
web = pie(J, 0.36, -GAPE - 8.0, 12.0, 0.34)
head_solid = union(upper_carved, lower, k=0.1)
head_solid = shrink(union(head_solid, web, k=0.12))

# --- cavita' della bocca: canale superiore, canale inferiore (ruotato), gola
beta = math.radians(GAPE / 2)
n_up = np.array([0.0, -math.sin(beta), math.cos(beta)])
above_bis = plane_sdf(J, -n_up)
below_bis = plane_sdf(J, n_up)
up_ch = loft(0.05, -1.40, 0.24, 0.16, 0.6, 0.6, -0.66, -0.73, r=0.08, rc=0.12)
lo_ch = loft(0.05, -1.25, 0.23, 0.14, 0.6, 0.6, 0.20, 0.26, r=0.08, rc=0.12)
throat = ellipsoid((0.17, 0.25, 0.18), (0.0, -0.13, -0.29))
cavity = union(up_ch.intersect(above_bis), JW(lo_ch).intersect(below_bis), throat, k=0.05)
nostrils = union(*[ellipsoid((0.022, 0.05, 0.034)).rot(0, sx * 35, sx * 28).translate((sx * 0.155, -1.51, 0.085))
                   for sx in (1, -1)])

# ============================================================ corpo (spazio Blender)
torso = union(
    ellipsoid((0.66, 0.60, 0.58), (0, 0.36, 1.92)),     # bacino
    ellipsoid((0.74, 0.66, 0.68), (0, -0.04, 1.98)),    # ventre
    ellipsoid((0.74, 0.58, 0.64), (0, -0.46, 2.16)),    # torace
    ellipsoid((0.64, 0.48, 0.50), (0, -0.72, 2.42)),    # spalle
    k=0.3)
pecs = [ell((sx * 0.31, -0.90, 2.10), (0.28, 0.22, 0.32), axis=(0, -0.35, 1)) for sx in (1, -1)]
NECK_PTS = [(0, -0.72, 2.40), (0, -0.98, 2.67), (0, -1.12, 2.86)]
neck = tube(NECK_PTS, [0.58, 0.54, 0.48], k=0.1)
neck_mus = [ell((sx * 0.30, -1.0, 2.62), (0.23, 0.25, 0.45), axis=(0, -0.55, 0.75)) for sx in (1, -1)]
hump = ellipsoid((0.44, 0.36, 0.28), (0, -0.78, 2.78))     # trapezio enorme dietro la testa
throat_skin = ell(hp((0.0, -0.30, -0.55)), (0.32, 0.30, 0.46), axis=hv((0, -0.2, -1.0)))

# zampe: sinistra (+x) avanti che pesta, destra (-x) indietro
LEGS = {
    1: dict(hip=(0.58, 0.20, 1.74), knee=(0.70, -0.36, 1.07), ankle=(0.74, -0.16, 0.32), ball=(0.76, -0.52, 0.14),
            yaw=-8.0),
    -1: dict(hip=(-0.58, 0.36, 1.74), knee=(-0.66, 0.10, 0.97), ankle=(-0.72, 0.68, 0.38), ball=(-0.74, 0.46, 0.14),
             yaw=6.0),
}
leg_parts, TOES, DEWS = [], [], []
for sx, L in LEGS.items():
    hip, knee, ankle, ball = (np.array(L[k]) for k in ("hip", "knee", "ankle", "ball"))
    fem = knee - hip
    leg_parts += [
        round_cone(hip, knee, 0.56, 0.28),
        ell(hip + fem * 0.42 + np.array([sx * 0.07, -0.06, 0.0]), (0.50, 0.52, 0.62), axis=fem),   # coscia enorme
        ell(hip + fem * 0.56 + np.array([sx * 0.19, -0.13, 0.0]), (0.26, 0.28, 0.44), axis=fem),   # quadricipite
        ell(hip + fem * 0.45 + np.array([sx * 0.12, 0.22, -0.02]), (0.24, 0.26, 0.42), axis=fem),  # femorali
        round_cone(knee, ankle, 0.31, 0.19),
        ell(knee + (ankle - knee) * 0.3 + np.array([0, 0.11, 0.03]), (0.25, 0.27, 0.38), axis=ankle - knee),  # polp.
        round_cone(ankle, ball, 0.19, 0.165),
        ellipsoid((0.25, 0.28, 0.14), tuple(ball + np.array([0, -0.05, -0.01]))),
    ]
    yaw = L["yaw"]
    for a in (-26.0, 0.0, 26.0):
        ang = math.radians(a + yaw)
        d = np.array([math.sin(ang), -math.cos(ang), 0.0])
        ln = 0.52 if a == 0 else 0.43
        p0 = ball + np.array([0, 0, -0.01])
        p1 = p0 + d * ln * 0.5 + np.array([0, 0, -0.02])
        p2 = p0 + d * ln + np.array([0, 0, -0.04])
        leg_parts.append(tube([tuple(p0), tuple(p1), tuple(p2)], [0.16, 0.14, 0.105]))
        leg_parts.append(ellipsoid((0.115, 0.115, 0.095), tuple(p1 + np.array([0, 0, 0.025]))))  # nocca
        TOES.append((p2, d))
    # sperone dietro la caviglia
    dw = ankle + (ball - ankle) * 0.55 + np.array([-sx * 0.1, 0.12, 0.0])
    leg_parts.append(round_cone(ankle + (ball - ankle) * 0.4, dw, 0.08, 0.06))
    DEWS.append((dw, norm(dw - (ankle + (ball - ankle) * 0.4)) + np.array([0, 0, -0.3])))
legs = union(*leg_parts, k=0.08)
# solco fra i muscoli davanti e dietro della coscia (gambe piu' definite e potenti)
creases = []
for sx, L in LEGS.items():
    hip, knee = np.array(L["hip"]), np.array(L["knee"])
    q, _ = project_many(legs, [hip + (knee - hip) * t for t in np.linspace(0.12, 0.82, 8)],
                        [norm((sx, 0.3, 0.05))] * 8)
    creases.append(tube([tuple(x) for x in q], [0.02, 0.032, 0.04, 0.042, 0.042, 0.038, 0.03, 0.018]))
legs = legs.subtract(union(*creases), k=0.035)

# braccine corte alzate, due dita
ARMS, ELBOWS, arm_parts = [], [], []
for sx in (1, -1):
    sh = np.array([sx * 0.46, -0.94, 2.18])
    el = np.array([sx * 0.66, -1.12, 2.02])
    wr = np.array([sx * 0.63, -1.32, 2.22])
    arm_parts += [round_cone(sh, el, 0.14, 0.095), round_cone(el, wr, 0.095, 0.078),
                  ell(sh + (el - sh) * 0.4 + np.array([0, -0.03, 0.03]), (0.115, 0.115, 0.16), axis=el - sh)]
    for dx in (0.055, -0.055):
        f = np.array([sx * 0.05 + dx, -0.11, -0.03])
        arm_parts.append(round_cone(wr, wr + f, 0.066, 0.05))
        ARMS.append((wr + f, norm(f + np.array([0, -0.04, -0.06]))))
    ELBOWS.append((el, norm((sx * 0.35, 0.75, -0.25))))
arms = union(*arm_parts, k=0.04)

# coda (parte separata, gruppo "Tail") e moncone nel corpo
TAIL_PTS = bezier((0.0, 0.62, 1.98), (0.0, 1.32, 2.14), (0.55, 1.86, 2.42), (0.95, 1.86, 2.98), 16)
TAIL_R = [0.06 + 0.46 * (1 - i / 16) ** 1.15 for i in range(17)]
TAIL_PIVOT = (0.0, 0.66, 1.99)
stump = tube(TAIL_PTS[:5], [r - 0.03 for r in TAIL_R[:5]])

core = union(torso, *pecs, k=0.15)
core = union(core, neck, *neck_mus, hump, k=0.22)
core = union(core, H(head_solid), k=0.18)
core = union(core, throat_skin, k=0.2)
core = union(core, stump, k=0.2)
core = union(core, legs, k=0.12)
core = union(core, arms, k=0.07)
core = core.subtract(H(cavity), k=0.03)
core = core.subtract(H(nostrils), k=0.02)
core0 = shrink(core.intersect(halfspace_z(0.0, above=True)))

# ============================================================ cicatrici di artigli (solchi che brillano)
# linea della schiena (dentro il corpo): guida per strisce, spine e pancia
SPINE = polyline([hp((0, -0.30, 0.16)), (0, -1.06, 2.98), (0, -0.92, 2.78), (0, -0.70, 2.52), (0, -0.40, 2.24),
                  (0, 0.0, 2.10), (0, 0.38, 2.02), (0, 0.70, 2.02)])


def slash(base, origin, a, b, n=9, w=0.04):
    """Graffio: curva sulla superficie da a a b (punti interni/vicini), proiettata da origin."""
    tgt = [np.asarray(a, float) * (1 - t) + np.asarray(b, float) * t for t in np.linspace(0, 1, n)]
    pts, nr = project_many(base, [origin] * n, [p - np.asarray(origin, float) for p in tgt])
    prof = [math.sin(math.pi * (0.08 + 0.84 * j / (n - 1))) ** 0.8 for j in range(n)]
    groove = tube([tuple(p) for p in pts], [max(w * f, 0.008) for f in prof])
    fill = tube([tuple(p - q * w * 0.5) for p, q in zip(pts, nr)], [max(w * 0.6 * f, 0.006) for f in prof])
    return groove, fill


scar_cut, scar_glow = [], []
# tre graffi sul muso (lato verso la camera 3/4) e due sulla guancia dall'altra parte
for i in range(3):
    dy = -0.1 * i
    a, b = hp((0.22, -0.90 + dy, 0.40)), hp((0.36, -1.12 + dy, -0.08))
    g, f = slash(core0, hp((0.0, -1.0 + dy, 0.08)), a, b, n=10, w=0.03)
    scar_cut.append(g)
    scar_glow.append(f)
for i in range(2):
    dy = -0.11 * i
    g, f = slash(core0, hp((-0.15, -0.36 + dy, 0.0)), hp((-0.5, -0.24 + dy, 0.32)), hp((-0.6, -0.46 + dy, -0.2)),
                 n=9, w=0.03)
    scar_cut.append(g)
    scar_glow.append(f)
# quattro graffi profondi sul fianco sinistro
for i in range(4):
    dy = 0.15 * i - 0.12
    a, b = (0.6, 0.26 + dy, 2.46), (0.7, -0.16 + dy, 1.62)
    g, f = slash(core0, (0.0, 0.05 + dy, 2.02), a, b, n=12, w=0.036)
    scar_cut.append(g)
    scar_glow.append(f)
# tre graffi sulla coscia destra (visibili di fronte)
for i in range(3):
    dz = -0.13 * i
    a, b = (-0.95, -0.20, 1.55 + dz), (-0.80, -0.62, 1.22 + dz)
    g, f = slash(core0, (-0.5, -0.05, 1.35 + dz), a, b, n=9, w=0.035)
    scar_cut.append(g)
    scar_glow.append(f)
core = core0.subtract(fast_union(scar_cut), k=0.025)
m.add("Body", core, SKIN, tris=15000, voxel=0.0285)


def vein(base, origin, p0, d0, n=7, step=0.065, turn=0.45, r0=0.02):
    """Vena di rabbia: linea serpeggiante sulla superficie che si assottiglia."""
    pts, d = [np.asarray(p0, float)], norm(d0)
    for _ in range(n):
        d = norm(d + rng.normal(0, turn, 3) * 0.5)
        pts.append(pts[-1] + d * step)
    q, nr = project_many(base, [origin] * len(pts), [p - np.asarray(origin, float) for p in pts])
    q = [p + nn * 0.004 for p, nn in zip(q, nr)]
    return tube([tuple(p) for p in q], [max(r0 * (1 - j / len(q)) ** 0.8, 0.008) for j in range(len(q))])


# vene incandescenti che si diramano dai graffi (la rabbia che brucia sotto la pelle)
veins = [vein(core, (0.0, 0.05, 2.05), p0, d0) for p0, d0 in (
    ((0.62, 0.42, 2.42), (0, 0.5, 0.8)), ((0.6, 0.22, 2.5), (0.0, 0.15, 1.0)), ((0.74, -0.30, 1.62), (0, -0.6, -0.7)),
    ((0.74, 0.12, 1.58), (0, 0.35, -0.9)), ((0.72, -0.24, 2.05), (0, -1.0, 0.2)))]
veins += [vein(core, (-0.5, 0.0, 1.45), p0, d0) for p0, d0 in (
    ((-0.97, -0.24, 1.6), (0, 0.2, 1.0)), ((-0.85, -0.6, 1.05), (0, -0.4, -0.9)))]
scar_glow += veins

tail = tube(TAIL_PTS, TAIL_R)
m.add("Tail", tail, SKIN, role="skin", tris=3000, voxel=0.0279, group="Tail", pivot=TAIL_PIVOT)

# ============================================================ pancia a placche (rosso polvere)
P_SP = SPINE
# linea ventrale (gola -> petto -> ventre) tracciata con un ventaglio di raggi nel piano di simmetria
fan = [(0, -math.cos(math.radians(a)), math.sin(math.radians(a))) for a in np.linspace(-8, -132, 20)]
v_pts, v_nrm = project_many(core0, [(0, -0.62, 2.12)], fan)
keep = (v_nrm[:, 2] < -0.3) & (v_pts[:, 1] > -1.3)      # solo la pelle rivolta in basso (non l'interno della bocca)
v_pts, v_nrm = v_pts[keep], v_nrm[keep]
V_P = polyline(v_pts)
belly_band = tube([tuple(p) for p in v_pts], 0.38)
jaw_band = H(JW(capsule((0, -0.12, -0.72), (0, -1.28, -0.52), 0.28)))
B_PERIOD, B_GROOVE = 0.17, 0.05


def belly_fn(p):
    band = belly_band(p)
    s, _, _ = closest_on(V_P, p.astype(np.float64))
    g = np.abs(np.mod(s / B_PERIOD, 1.0) - 0.5) * B_PERIOD
    return np.minimum(np.maximum(band, B_GROOVE * 0.5 - g), jaw_band(p)).astype(np.float32)


belly = paint(core, SDF(belly_fn, np.minimum(belly_band.lo, jaw_band.lo), np.maximum(belly_band.hi, jaw_band.hi)),
              out=0.018, inn=0.05)
m.add("Belly", belly, BELLY, role="detail", tris=4600, voxel=0.0245)

T_P = polyline(TAIL_PTS)
t_ups = np.array([norm(np.array([0, 0, 1.0]) - (sg / ln) * (sg / ln)[2]) for sg, ln in zip(T_P[1], T_P[2])])


def tail_belly_fn(p):
    s, c, k = closest_on(T_P, p.astype(np.float64))
    v = p - c
    vn = np.linalg.norm(v, axis=1) + 1e-9
    cosd = -(v * t_ups[k]).sum(1) / vn
    reg = (0.7 - cosd) * vn
    return np.maximum(reg, s - T_P[3][-1] * 0.6).astype(np.float32)


m.add("TailBelly", paint(tail, SDF(tail_belly_fn, tail.lo, tail.hi), out=0.018, inn=0.05), BELLY, role="detail",
      tris=1400, voxel=0.0274, group="Tail", pivot=TAIL_PIVOT)

# ============================================================ strisce nere da tigre
stripes = []
L_SP = P_SP[3][-1]
for side in (1, -1):
    for i, s in enumerate(np.linspace(0.42, L_SP - 0.15, 13)):
        jit = rng.normal(0, 0.035)
        a1 = 100 + rng.normal(0, 10) + (26 if 0.3 < s / L_SP < 0.8 else 0)
        pts = wrap_curves(core, P_SP, s + jit, 9, a1, side, lean=0.12 + rng.normal(0, 0.05), wob=0.03, n=14,
                          phase=rng.uniform(0, 6))
        stripes.append(stripe_tube(pts, 0.085 + rng.normal(0, 0.012)))
        if i % 3 == 1:  # striscia corta in mezzo (biforcazione)
            pts = wrap_curves(core, P_SP, s + 0.09, 40, 70, side, lean=0.05, n=8)
            stripes.append(stripe_tube(pts, 0.055, both=True))
# cosce
for sx, L in LEGS.items():
    TH = polyline([np.array(L["hip"]) + np.array([0, 0, 0.1]), np.array(L["knee"])])
    for f_ in (0.15, 0.32, 0.5, 0.68, 0.84):
        f2 = f_ + rng.normal(0, 0.03)
        a0 = -70 + rng.normal(0, 18)
        pts = wrap_curves(core, TH, TH[3][-1] * f2, a0, a0 + 100 + rng.normal(0, 18), 1, up=(sx, 0, 0),
                          lean=0.3 * rng.choice((-1, 1)) + rng.normal(0, 0.08), wob=0.05, n=14, phase=rng.uniform(0, 6))
        stripes.append(stripe_tube(pts, 0.068 + rng.normal(0, 0.01), both=True))
# testa: strisce a V sul cranio e sulle guance
HP_ = polyline([(0, 0.08, 0.12), (0, -0.62, 0.12)])
for side in (1, -1):
    for s, a1 in ((0.10, 72), (0.26, 78), (0.42, 66)):
        pts = wrap_curves(upper, HP_, s, 12, a1, side, lean=-0.15, n=10)
        stripes.append(H(stripe_tube(pts, 0.075)))
    # V sulla fronte fra gli occhi e strisce sulle guance
    FR = polyline([(0, -0.55, 0.10), (0, -1.0, 0.05)])
    pts = wrap_curves(upper, FR, 0.30, 6, 48, side, lean=0.35, n=8)
    stripes.append(H(stripe_tube(pts, 0.06)))
    CH = polyline([(0, -0.15, -0.05), (0, -0.6, -0.05)])
    for s, a0 in ((0.12, 62), (0.27, 70)):
        pts = wrap_curves(upper, CH, s, a0, a0 + 48, side, lean=-0.25, n=8)
        stripes.append(H(stripe_tube(pts, 0.06, both=True)))
    # mandibola: strisce che scendono dal bordo dei denti verso il mento
    JL = polyline([(0, -0.15, -0.44), (0, -1.25, -0.40)])
    for s in (0.32, 0.56, 0.8):
        pts = wrap_curves(lower_closed, JL, s, 58, 128, side, lean=-0.12, n=9)
        stripes.append(H(JW(stripe_tube(pts, 0.055, both=True))))
stripes_paint = paint(core, fast_union(stripes), out=0.018, inn=0.05)
m.add("Stripes", stripes_paint, STRIPE, role="detail", tris=7800, voxel=0.0258)

tail_stripes = []
for side in (1, -1):
    for i, f_ in enumerate(np.linspace(0.12, 0.86, 9)):
        s = T_P[3][-1] * f_
        pts = wrap_curves(tail, T_P, s, 8, 112 - 30 * f_, side, lean=0.1, n=10)
        tail_stripes.append(stripe_tube(pts, 0.08 * (1.05 - 0.6 * f_)))
m.add("TailStripes", paint(tail, fast_union(tail_stripes), out=0.018, inn=0.05), STRIPE, role="detail", tris=1800,
      voxel=0.0209, group="Tail", pivot=TAIL_PIVOT)

# ============================================================ spine, corna e scudi ossei neri
spikes = []
# spine dorsali a pinna, dalla nuca alla base della coda
sp_s = np.linspace(0.30, L_SP - 0.05, 11)
sp_o, sp_d, sp_t = [], [], []
for s in sp_s:
    c, t = poly_at(P_SP, s)
    sp_o.append(c)
    sp_d.append(norm(np.array([0, 0, 1.0]) - t * t[2]))
    sp_t.append(t)
sp_p, sp_n = project_many(core0, sp_o, sp_d)
for j, (p, nr, t) in enumerate(zip(sp_p, sp_n, sp_t)):
    f = j / (len(sp_s) - 1)
    h = (0.15 + 0.27 * math.sin(math.pi * min(f * 1.25 + 0.05, 1.0))) * (1.0 if j % 2 == 0 else 0.74)
    if j == 5:  # spina spezzata in battaglia
        spikes.append(place(blade(0.3 + 0.5 * h, h * 0.5, 0.09, curl=0.05, sweep=0.1), p - nr * 0.02, t, nr))
        continue
    spikes.append(place(blade(0.22 + 0.5 * h, h, 0.085), p - nr * 0.02, t, nr))
# corna sopra gli occhi e dietro, spuntoni sulle guance
horns_l = []
for sx in (1, -1):
    o = np.array((sx * 0.25, -0.785, 0.36))  # dentro l'arcata sopraccigliare
    p, nr = surf(upper, o, o + np.array((sx * 0.2, 0.1, 1.0)))
    horns_l.append(horn(p - nr * 0.03, nr + np.array([sx * 0.15, 0.55, 0.2]), 0.31, 0.097, curl=(0, 0.38, -0.1), n=6))
    o = np.array((sx * 0.37, -0.67, 0.37))
    p, nr = surf(upper, o, o + np.array((sx * 0.5, 0.3, 0.8)))
    horns_l.append(horn(p - nr * 0.03, nr + np.array([0, 0.6, 0.1]), 0.22, 0.075, curl=(0, 0.32, -0.12), n=5))
    for y, z, L_ in ((-0.46, 0.0, 0.14), (-0.30, -0.08, 0.17), (-0.15, -0.14, 0.12)):
        p, nr = surf(upper, (sx * 0.1, y, z), (sx * 0.7, y + 0.05, z))
        horns_l.append(horn(p - nr * 0.025, nr + np.array([0, 0.35, -0.1]), L_, 0.05, curl=(0, 0.25, 0), n=4))
    # bitorzoli sul naso
    p, nr = surf(upper, (sx * 0.05, -1.12, 0.1), (sx * 0.14, -1.12, 0.32))
    horns_l.append(horn(p - nr * 0.02, nr, 0.06, 0.04, n=3, r1=0.015))
spikes += [H(h_) for h_ in horns_l]
spikes += [horn(e, d, 0.17, 0.05, curl=(0, 0.2, -0.1), n=4) for e, d in ELBOWS]   # speroni sui gomiti
m.add("Spikes", fast_union(spikes), SPIKE, role="detail", tris=3000, voxel=0.019)

tail_sp = []
ts_s = np.linspace(0.25, T_P[3][-1] * 0.92, 9)
ts_o, ts_d, ts_t = [], [], []
for s in ts_s:
    c, t = poly_at(T_P, s)
    ts_o.append(c)
    ts_d.append(norm(np.array([0, 0, 1.0]) - t * t[2]))
    ts_t.append(t)
ts_p, ts_n = project_many(tail, ts_o, ts_d)
for j, (p, nr, t) in enumerate(zip(ts_p, ts_n, ts_t)):
    f = j / (len(ts_s) - 1)
    h = 0.25 * (1.0 - 0.7 * f)
    tail_sp.append(place(blade(0.2 + 0.5 * h, h, 0.075 * (1 - 0.4 * f)), p - nr * 0.02, t, nr))
m.add("TailSpikes", fast_union(tail_sp), SPIKE, role="detail", tris=1300, voxel=0.0167, group="Tail", pivot=TAIL_PIVOT)

# ============================================================ denti frastagliati su gengive scoperte


def rim_path(w_back, w_front, y_back, y_front, y_tip, n_side=40, n_arc=16):
    """Linea dei denti di un lato (da dietro al centro davanti) nel piano XY locale."""
    pts = [(w_back + (w_front - w_back) * t, y_back + (y_front - y_back) * t) for t in np.linspace(0, 1, n_side)]
    for a in np.linspace(0, math.pi / 2, n_arc)[1:]:
        pts.append((w_front * math.cos(a), y_front - (y_front - y_tip) * math.sin(a)))
    return np.array(pts)


def tooth_row(jaw_sdf, path, z_in, down, lengths, back_lean=0.28, out_lean=0.10):
    """Denti lungo 'path' (un lato, da dietro a davanti) piantati sul bordo della mascella + gengive."""
    path3 = np.array([[x, y, z_in] for x, y in path])
    rim, _ = project_many(jaw_sdf, path3, [[0, 0, down]])
    seg = np.linalg.norm(np.diff(rim, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    teeth, gums = [], []
    for i, L in enumerate(lengths):
        s = cum[-1] * (0.03 + 0.955 * i / (len(lengths) - 1))
        k = min(np.searchsorted(cum, s, side="right") - 1, len(seg) - 1)
        p = rim[k] + (rim[k + 1] - rim[k]) * (s - cum[k]) / max(seg[k], 1e-9)
        side = math.copysign(1.0, p[0]) if abs(p[0]) > 0.03 else 0.0
        d = norm([side * out_lean + rng.normal(0, 0.07), back_lean + rng.normal(0, 0.08), down])
        r = 0.13 * L + 0.026
        teeth.append(horn(p - d * 0.06, d, L + 0.06, r, curl=(0, 0.2, 0), n=4, r1=0.005, power=1.3))
        gums.append(ellipsoid((r * 1.45, r * 1.55, r * 0.9), tuple(p + np.array([0, 0, -down * 0.01]))))
    return teeth, gums


# denti superiori: lunghezze irregolari (zanne enormi in mezzo, qualcuno spezzato)
UP_L = [0.11, 0.15, 0.30, 0.19, 0.35, 0.24, 0.29, 0.16, 0.24, 0.18, 0.13, 0.10]
LO_L = [0.10, 0.14, 0.27, 0.17, 0.29, 0.20, 0.15, 0.20, 0.14, 0.10]
teeth_all, gums_all = [], []
for sx in (1, -1):
    upath = rim_path(0.30, 0.20, -0.50, -1.22, -1.46)
    upath[:, 0] *= sx
    t_, g_ = tooth_row(upper, upath, -0.08, -1.0, [L * (1 + rng.normal(0, 0.1)) for L in UP_L[::-1]])
    teeth_all += [H(t) for t in t_]
    gums_all += [H(g) for g in g_]
    lpath = rim_path(0.285, 0.185, -0.52, -1.12, -1.35)
    lpath[:, 0] *= sx
    t_, g_ = tooth_row(lower_closed, lpath, -0.38, 1.0, [L * (1 + rng.normal(0, 0.1)) for L in LO_L[::-1]],
                       back_lean=0.22)
    teeth_all += [H(JW(t)) for t in t_]
    gums_all += [H(JW(g)) for g in g_]
m.add("Teeth", fast_union(teeth_all), BONE, role="shine", tris=6000, voxel=0.0166)
m.add("Gums", fast_union(gums_all, k=0.03), GUM, role="detail", tris=1800, voxel=0.0227)

# lingua grossa con il solco centrale, punta che si alza
tongue_l = union(ellipsoid((0.18, 0.38, 0.09), (0, -0.50, -0.34)),
                 ellipsoid((0.15, 0.22, 0.085), (0, -0.94, -0.29)).rot(-14, 0, 0, pivot=(0, -0.94, -0.29)), k=0.1)
tongue_l = tongue_l.subtract(capsule((0, -0.25, -0.23), (0, -1.06, -0.18), 0.024), k=0.03)
m.add("Tongue", H(JW(tongue_l)), TONGUE, role="detail", tris=800, voxel=0.0241)

# ============================================================ occhi infuocati, interno della bocca
maw = paint(core, H(cavity).offset(0.025), out=0.012, inn=0.06)
eyes, pupils = [], []
for sx in (1, -1):
    tilt = sx * 14  # angolo verso il muso piu' basso: sguardo cattivo
    eyes.append(H(eye_place(ellipsoid((EA, EB, EC)).rot(0, tilt, 0), sx, (0, 0.035, 0))))
    pupils.append(H(eye_place(ellipsoid((0.018, 0.02, 0.064)), sx, (sx * 0.01, -0.02, 0.0))))
    ring = [(EA * 1.06 * math.cos(t), 0.0, EC * 1.1 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 33)]
    pupils.append(H(eye_place(tube(ring, 0.022).rot(0, tilt, 0), sx, (0, 0.012, 0))))
pupils += [H(ll) for ll in lid_lines]
m.add("Maw", maw, MAW, role="eye", tris=3300, voxel=0.0268)
m.add("Pupils", fast_union(pupils), MAW, role="eye", tris=1400, voxel=0.012)
m.add("Rage", fast_union(eyes + scar_glow), RAGE, material="Neon", role="glow", tris=3000, voxel=0.014)

# ============================================================ artigli: piedi (enormi, uncinati verso terra) e mani
claws = []
for p, d in TOES:
    base = p - d * 0.02 + np.array([0, 0, 0.035])
    claws.append(horn(base, d + np.array([0, 0, 0.08]), 0.25, 0.075, curl=(0, 0, -0.55), n=5, r1=0.006))
for p, d in DEWS:
    claws.append(horn(p, d, 0.12, 0.05, curl=(0, 0, -0.4), n=4, r1=0.005))
for p, d in ARMS:
    claws.append(horn(p - d * 0.01, d, 0.13, 0.042, curl=(0, 0, -0.6), n=4, r1=0.004))
m.add("Claws", fast_union(claws).intersect(halfspace_z(0.004, above=True)), BONE, role="detail", tris=2000,
      voxel=0.0133)

# ============================================================ toy horror: cucitura sul petto
seam_pts = list(v_pts[2:12])
seam_surf = core.offset(0.026)
seam = stitch_row(seam_surf, [on_surface(seam_surf, p) for p in seam_pts], dash=0.06, gap=0.06, r=0.026, cross=True,
                  cross_len=0.22)
seam += stitch_row(seam_surf, [on_surface(seam_surf, p) for p in seam_pts], dash=0.08, gap=0.03, r=0.02)
m.add("Stitches", fast_union(seam), THREAD, role="detail", tris=800, voxel=0.0135)

# ============================================================ cavigliera di ferro con la catena spezzata
L1 = LEGS[1]
ank, bal = np.array(L1["ankle"]), np.array(L1["ball"])
ax = norm(bal - ank)
cc = ank + (bal - ank) * 0.42
cuff = cylinder(cc - ax * 0.07, cc + ax * 0.07, 0.235, round=0.025)
cuff = cuff.subtract(cylinder(cc - ax * 0.3, cc + ax * 0.3, 0.165))
ring_side = norm(np.cross(ax, (0, 0, 1)))
if ring_side[0] < 0:
    ring_side = -ring_side
iron = [cuff]
for a in np.linspace(0, 2 * math.pi, 9)[:-1]:
    dvec = ring_side * math.cos(a) + np.cross(ax, ring_side) * math.sin(a)
    iron.append(sphere(0.028, tuple(cc + dvec * 0.245)))
hook = cc + ring_side * 0.27 + np.array([0, 0, -0.05])
iron.append(chain_link(hook + np.array([0.0, 0.0, -0.06]), (0, 0, 1), ax, 0.04, 0.05, 0.022))
iron.append(chain_link(hook + np.array([0.06, 0.12, -0.16]), (0.35, 1, 0), (0, 0, 1), 0.05, 0.055, 0.024))
broken = chain_link(hook + np.array([0.14, 0.33, -0.16]), (0.45, 1, 0.05), (0.3, -0.2, 1), 0.05, 0.055, 0.024)
iron.append(broken.subtract(sphere(0.05, tuple(hook + np.array([0.19, 0.45, -0.16])))))
m.add("Shackle", fast_union(iron).intersect(halfspace_z(0.004, above=True)), IRON, material="Metal", role="detail",
      tris=1800, voxel=0.0134)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
