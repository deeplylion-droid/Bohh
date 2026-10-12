"""Cinghiale da Guerra (WarBoar) - pet Primordiale.

Un cinghiale mastodontico lanciato alla carica: testa bassa, garrese enorme e muscoloso, una zampa
anteriore alzata che raspa il terreno sopra un mucchietto di zolle appena sollevate. Corazza di ferro
rivettata: spallacci a tre lame sovrapposte con spuntoni d'acciaio, due piastre sulla schiena e viti a
vista con il taglio a croce. Cresta irta di setole nere dalla fronte alla groppa, coda dritta come un
facocero alla carica, enormi zanne d'osso a mezzaluna cerchiate d'acciaio, fauci aperte con file di denti
aguzzi, grugno sfregiato da tre graffi che ardono. Occhi rossi incandescenti cerchiati di nero sotto
arcate aggrottate; dalle narici sbuffa il vapore della rabbia (parte Neon "Rage": il gioco ci attacca
braci e fumo, insieme ai graffi del grugno) e vene di rabbia pulsano dove finisce la corazza.
Tocco "toy horror": una toppa cucita sul fianco, una cicatrice ricucita sull'arcata, una lunga cucitura
sulla coscia e una cavigliera con la catena spezzata.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, box, capsule, cylinder, ellipsoid, euler, halfspace_z, look_matrix, octahedron,  # noqa: E402
                     rot_matrix, round_cone, smin, sphere, tube, union)
from lib.toy import Model  # noqa: E402

VX = float(os.environ.get("VX", "1"))  # bozza: VX=1.5 usa voxel piu' grossi per iterare in fretta


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
        print(f"[boar] attenzione: {len(bad)} raggi partono fuori dalla forma, es. {np.round(o[bad[0]], 3)}")
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
    shapes = [s for s in shapes if s is not None]
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
    """Strato sottile (guscio fra -inn e +out attorno a core) dentro 'region'; core valutato solo vicino."""
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


def horn(base, d, L, r0, curl=(0, 0, 0), n=5, r1=0.006, power=1.0):
    """Cono curvo (zanna, artiglio, dente, setola): parte da base verso d (lunghezza L) e si piega verso 'curl'."""
    base, d, c = np.asarray(base, float), norm(d), np.asarray(curl, float)
    ts = np.linspace(0.0, 1.0, n)
    pts = [tuple(base + d * L * t + c * L * t * t) for t in ts]
    return tube(pts, [r0 + (r1 - r0) * t ** power for t in ts])


def rot_pts(R, pts, pivot=(0, 0, 0)):
    pv = np.asarray(pivot, dtype=np.float64)
    return (np.asarray(pts, dtype=np.float64) - pv) @ np.asarray(R, dtype=np.float64).T + pv


def frame(fwd, up):
    """Colonne: X locale (destra), Y locale (= -fwd), Z locale (up ortogonalizzato)."""
    f = norm(fwd)
    u = norm(np.asarray(up, float) - f * float(np.dot(up, f)))
    r = np.cross(f, u)
    return np.stack([r, -f, u], axis=1).astype(np.float32)


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


def x_stitch(sdf, c, t, size=0.08, r=0.018, lift=0.0):
    """Punto a X centrato in c (t = direzione della cucitura)."""
    n = grad(sdf, c)
    t = norm(np.asarray(t, float) - n * float(np.dot(t, n)))
    s = np.cross(n, t)
    out = []
    for a, b in ((t + s, -t - s), (t - s, -t + s)):
        pa = on_surface(sdf, c + a * size * 0.5, lift, 3)
        pb = on_surface(sdf, c + b * size * 0.5, lift, 3)
        out.append(capsule(tuple(pa), tuple(pb), r))
    return out


def slash(base, origin, a, b, n=9, w=0.035):
    """Graffio: curva sulla superficie da a a b, proiettata da origin. Ritorna (solco, riempimento)."""
    tgt = [np.asarray(a, float) * (1 - t) + np.asarray(b, float) * t for t in np.linspace(0, 1, n)]
    pts, nr = project_many(base, [origin] * n, [p - np.asarray(origin, float) for p in tgt])
    prof = [math.sin(math.pi * (0.08 + 0.84 * j / (n - 1))) ** 0.8 for j in range(n)]
    groove = tube([tuple(p) for p in pts], [max(w * f, 0.008) for f in prof])
    fill = tube([tuple(p - q * w * 0.45) for p, q in zip(pts, nr)], [max(w * 0.62 * f, 0.007) for f in prof])
    return groove, fill, pts




# ============================================================ colori
FUR = (124, 72, 40)          # bruno terroso, saturo
SNOUT = (52, 32, 28)         # disco del grugno, contorno degli occhi, interno delle orecchie: quasi nero
BRISTLE = (34, 22, 20)       # setole quasi nere
IRON = (104, 98, 96)         # piastre di ferro (grigio caldo: il metallo riflette il cielo)
STEEL = (206, 202, 198)      # rivetti, viti e spuntoni
PATCH = (176, 58, 32)        # toppa di stoffa rosso ruggine
BONE = (244, 232, 204)       # zanne e denti
HOOF = (46, 36, 36)
MAW = (52, 12, 16)
THREAD = (240, 226, 192)
CHAIN = (126, 118, 112)
RAGE = (255, 52, 18)
EYE_RED = (255, 30, 22)
TONGUE = (178, 50, 62)
DIRT = (92, 64, 44)

m = Model("WarBoar", "pet", voxel=0.03 * VX)
rng = np.random.default_rng(7)

# ============================================================ testa (locale: origine sulla nuca, grugno verso -Y)
LIFT = 0.1                         # corpo piu' alto: zampe piu' lunghe e potenti
HEAD_POS = np.array([0.0, -0.84, 1.52 + LIFT])
HS = 1.2
R_HEAD = euler(16.0, 0.0, 8.0)     # testa bassa da carica, girata appena verso chi guarda (3/4)
HINGE = np.array([0.0, -0.24, -0.16])
JAW = 30.0
R_JAW = euler(JAW, 0.0, 0.0)


def H(s):
    return s.scale(HS).rotate(R_HEAD).translate(HEAD_POS)


def hp(p):
    return rot_pts(R_HEAD, np.asarray(p, dtype=np.float64) * HS) + HEAD_POS


def JW(s):
    return s.rotate(R_JAW, pivot=HINGE)


def jp(p):
    return rot_pts(R_JAW, p, HINGE)


def lip_z(y):
    """Linea della bocca (spazio locale): bassa sotto il disco, arricciata dove esce la zanna."""
    return np.interp(y, [-1.5, -1.06, -0.96, -0.87, -0.66, 0.2], [-0.27, -0.25, -0.12, -0.10, -0.17, -0.16])


cran = ellipsoid((0.47, 0.42, 0.35), (0, -0.18, 0.10))
crown = ellipsoid((0.43, 0.30, 0.16), (0, -0.36, 0.32))
shelf = ellipsoid((0.44, 0.20, 0.17), (0, -0.52, 0.30))
jowls = [ellipsoid((0.25, 0.30, 0.24), (sx * 0.28, -0.40, -0.12)) for sx in (1, -1)]
snout = loft(-0.45, -1.10, 0.28, 0.19, 0.25, 0.18, 0.06, -0.03, r=0.09, rc=0.03, tp=0.3)
disc = cylinder((0, -1.06, -0.01), (0, -1.13, -0.01), 0.19, round=0.032)
flares = [ellipsoid((0.10, 0.16, 0.10), (sx * 0.19, -0.88, -0.13)) for sx in (1, -1)]
brows = [capsule((sx * 0.04, -0.74, 0.28), (sx * 0.47, -0.50, 0.47), 0.11) for sx in (1, -1)]
# ciuffi di pelo ispido sulle guance, all'indietro: testa piu' selvaggia e spigolosa
tufts = []
for sx in (1, -1):
    for (bx, by, bz, dz, L) in ((0.36, -0.30, -0.16, -0.25, 0.26), (0.40, -0.16, -0.02, -0.05, 0.24),
                                (0.30, -0.44, -0.27, -0.45, 0.2)):
        tufts.append(horn((sx * bx, by, bz), (sx * 0.55, 0.8, dz), L, 0.075, curl=(0, 0.1, -0.05), n=4, r1=0.012))
jaw = loft(-0.25, -1.04, 0.28, 0.17, 0.15, 0.10, -0.31, -0.27, r=0.08, rc=0.04)
chin = ellipsoid((0.15, 0.10, 0.09), (0, -1.0, -0.31))
head0 = union(cran, crown, shelf, *jowls, k=0.17)
head0 = union(head0, snout, k=0.16)
head0 = union(head0, disc, k=0.05)
head0 = union(head0, *flares, k=0.08)
head0 = union(head0, *brows, k=0.08)
head0 = union(head0, *tufts, k=0.04)
head0 = shrink(union(head0, jaw, chin, k=0.1))

# occhi sotto le arcate, sporgenti, che guardano dritti verso chi carica
EYE_D = {sx: norm((sx * 0.46, -0.8, 0.3)) for sx in (1, -1)}
EYE_C = {}
for sx in (1, -1):
    o = np.array((sx * 0.12, -0.46, 0.17))
    EYE_C[sx], _ = surf(head0, o, o + np.array((sx * 0.5, -0.85, 0.06)))


def eye_place(shape, sx, offset=(0.0, 0.0, 0.0)):
    """Coordinate locali dell'occhio: X di lato, -Y verso lo sguardo, Z in alto; origine sulla superficie."""
    return shape.translate(offset).rotate(look_matrix(EYE_D[sx])).translate(EYE_C[sx])


EA, EB, EC = 0.13, 0.064, 0.088
EYE_SINK = 0.025
sockets = union(*[eye_place(ellipsoid((EA + 0.03, 0.08, EC + 0.025)), sx, (0, 0.04, 0)) for sx in (1, -1)])
head1 = head0.subtract(sockets, k=0.03)
LID_CUT, LID_SLOPE = 0.024, 0.55
lids = []
for sx in (1, -1):
    A, B, C = EA + 0.022, EB + 0.022, EC + 0.022

    def lid_plane(p, sx=sx):
        return (LID_CUT - LID_SLOPE * sx * p[:, 0] - p[:, 2]) / math.sqrt(1 + LID_SLOPE ** 2)

    lid = ellipsoid((A, B, C)).intersect(SDF(lid_plane, (-A, -B, -C), (A, B, C)), k=0.01)
    lids.append(eye_place(lid, sx, (0, EYE_SINK, 0)))
head1 = union(head1, *lids, k=0.012)

# rughe della fronte aggrottata e pieghe del ringhio sul dorso del grugno, dietro il disco
furrows = []
for sx in (1, -1):
    o = np.array((sx * 0.05, -0.45, 0.2))
    q, _ = project_many(head1, [o] * 5, [np.array((sx * (0.05 + 0.012 * j), -0.66 + 0.05 * j, 0.44)) - o
                                        for j in range(5)])
    furrows.append(tube([tuple(p) for p in q], [0.012, 0.02, 0.022, 0.018, 0.01]))
for y, w in ((-0.62, 0.17), (-0.69, 0.18), (-0.98, 0.15)):
    pts = [(x, y + 0.03 * abs(x) / w, 0.0) for x in np.linspace(-w, w, 9)]
    q, _ = project_many(head1, [(0, y, 0.0)] * 9, [np.array(p) - np.array((0, y, -0.3)) for p in pts])
    furrows.append(tube([tuple(p) for p in q], [0.01, 0.018, 0.022, 0.022, 0.02, 0.022, 0.022, 0.018, 0.01]))
head2 = head1.subtract(fast_union(furrows), k=0.02)

# tre graffi profondi sul grugno (lato verso la camera 3/4): il solco arde di rabbia
scar_cut, scar_fill = [], []
for i in range(3):
    dy = -0.085 * i
    g, f, _ = slash(head2, (0.0, -0.84 + dy, -0.04), (0.21, -0.76 + dy, -0.08), (-0.05, -0.88 + dy, 0.17), n=9,
                    w=0.034)
    scar_cut.append(g)
    scar_fill.append(f)
head2 = head2.subtract(fast_union(scar_cut), k=0.012)

# narici nel disco, allargate dalla rabbia (dentro brillano: il vapore della rabbia)
NOST = [(sx * 0.07, -1.17, -0.02) for sx in (1, -1)]
nostrils = union(*[ellipsoid((0.04, 0.06, 0.06), c).rot(0, sx * 25, 0, pivot=c) for sx, c in zip((1, -1), NOST)])
head2 = head2.subtract(nostrils, k=0.02)


# bocca: la mandibola si apre attorno alla cerniera (ghigno)
def upper_region(p):
    f = lip_z(p[:, 1]) - p[:, 2]             # < 0 sopra il labbro
    g = (HINGE[1] + 0.02) - p[:, 1]          # < 0 dietro la cerniera
    return np.minimum(f, g)


U_REG = SDF(upper_region, (-3, -3, -3), (3, 3, 3))
L_REG = SDF(lambda p: -upper_region(p), (-3, -3, -3), (3, 3, 3))
upper = head2.intersect(U_REG, k=0.015)
lower_closed = head2.intersect(L_REG, k=0.015)
lower = JW(lower_closed)
head_solid = shrink(union(upper, lower, k=0.02))


def gap_fn(p):
    f = p[:, 2] - lip_z(p[:, 1])                       # < 0 sotto il labbro superiore
    q = (p - HINGE) @ R_JAW.astype(np.float32) + HINGE  # coordinate della mandibola chiusa
    g = lip_z(q[:, 1]) - q[:, 2]                       # < 0 sopra il labbro inferiore
    h = p[:, 1] - (HINGE[1] - 0.04)                     # < 0 davanti alla cerniera
    return np.maximum(np.maximum(f, g), h)


GAP = SDF(gap_fn, (-0.5, -1.4, -0.7), (0.5, 0.0, 0.2))
maw_l = head0.offset(-0.04).intersect(GAP)

# orecchie a punta tirate indietro (una mozzicata in battaglia)
EARS, INNER = [], []
for sx in (1, -1):
    ax = norm((sx * 0.5, 0.58, 0.64))
    base = np.array((sx * 0.30, -0.08, 0.40))
    side = np.cross(ax, (sx, 0, 0))
    e = ell(base + ax * 0.26, (0.19, 0.055, 0.36), axis=ax, side=side)
    INNER.append(ell(base + ax * 0.26 + np.array([sx * 0.06, 0, 0]), (0.125, 0.065, 0.27), axis=ax, side=side))
    if sx > 0:
        e = e.subtract(sphere(0.08, tuple(base + ax * 0.4 + norm(side) * 0.19)), k=0.01)
    EARS.append(e)

# ============================================================ corpo (spazio Blender): garrese enorme, ventre raccolto
torso = union(
    ellipsoid((0.80, 0.60, 0.72), (0, -0.38, 1.72 + LIFT)),   # petto profondo
    ellipsoid((0.74, 0.66, 0.62), (0, -0.20, 2.18 + LIFT)),   # garrese (gobba)
    ellipsoid((0.62, 0.60, 0.55), (0, 0.26, 1.78 + LIFT)),    # ventre
    ellipsoid((0.52, 0.47, 0.52), (0, 0.74, 1.72 + LIFT)),    # bacino
    k=0.3)
torso = shrink(torso)

LEGS = {
    # anteriore destra (-x): piantata, spinge in avanti
    "FR": dict(pts=[(-0.54, -0.44, 1.55), (-0.60, -0.56, 0.9), (-0.62, -0.66, 0.33), (-0.62, -0.70, 0.21)],
               r=[0.36, 0.23, 0.165, 0.155], hoof=((-0.62, -0.77, 0.125), (0, -1, 0), (0, 0, 1))),
    # anteriore sinistra (+x): raspa il terreno, zoccolo trascinato indietro con la punta che scava
    "FL": dict(pts=[(0.54, -0.40, 1.55), (0.68, -1.0, 1.14), (0.71, -0.92, 0.74), (0.71, -0.88, 0.66)],
               r=[0.34, 0.215, 0.16, 0.15], hoof=((0.71, -0.85, 0.57), (0, -0.85, -0.53), (0, -0.53, 0.85))),
    # posteriori: prosciutti enormi, garretti che spingono
    "HL": dict(pts=[(0.42, 0.74, 1.60), (0.53, 0.46, 1.04), (0.57, 0.92, 0.6), (0.58, 0.86, 0.27),
                    (0.58, 0.84, 0.21)],
               r=[0.40, 0.25, 0.165, 0.15, 0.145], hoof=((0.58, 0.79, 0.125), (0.05, -1, 0), (0, 0, 1))),
    "HR": dict(pts=[(-0.42, 0.74, 1.60), (-0.53, 0.52, 1.02), (-0.57, 1.0, 0.62), (-0.58, 0.96, 0.27),
                    (-0.58, 0.94, 0.21)],
               r=[0.40, 0.25, 0.165, 0.15, 0.145], hoof=((-0.58, 0.89, 0.125), (-0.05, -1, 0), (0, 0, 1))),
}
leg_parts = []
for key, L in LEGS.items():
    pts = [np.array(p) for p in L["pts"]]
    leg_parts.append(tube([tuple(p) for p in pts], L["r"], k=0.05))
    a, b = pts[0], pts[1]
    sx = 1 if a[0] > 0 else -1
    if key[0] == "H":   # prosciutto
        leg_parts.append(ell(a * 0.55 + b * 0.45 + np.array([sx * 0.05, 0.08, 0.0]), (0.37, 0.40, 0.52), axis=b - a))
        tuft_d = norm(np.array([sx * 0.3, 1.0, -0.5]))
    elif key == "FL":   # zampa alzata: avambraccio piu' asciutto, si vede la piega del ginocchio
        leg_parts.append(ell(a * 0.55 + b * 0.45 + np.array([sx * 0.04, 0.0, 0.02]), (0.26, 0.27, 0.36), axis=b - a))
        tuft_d = norm(np.array([sx * 0.3, 1.0, 0.2]))
    else:               # spalla e avambraccio muscolosi
        leg_parts.append(ell(a * 0.5 + b * 0.5 + np.array([sx * 0.05, -0.04, 0.0]), (0.29, 0.30, 0.42), axis=b - a))
        tuft_d = norm(np.array([sx * 0.3, 1.0, -0.2]))
    c = pts[1] * 0.6 + pts[2] * 0.4
    leg_parts.append(ell(c + np.array([0, 0.03, 0.0]), (0.19, 0.2, 0.26), axis=pts[2] - pts[1]))
    # ciuffi di pelo ispido dietro il gomito / il garretto
    for dz, L_ in ((0.06, 0.24), (-0.08, 0.18)):
        tb = pts[1] + np.array([0, 0.12, dz])
        leg_parts.append(horn(tb, tuft_d + np.array([0, 0, dz]), L_, 0.08, n=3, r1=0.014))
legs = union(*leg_parts, k=0.08)

# coda dritta verso l'alto come un facocero alla carica
TAIL_PTS = [(0, 1.06, 2.0 + LIFT), (0, 1.15, 2.18 + LIFT), (0, 1.2, 2.36 + LIFT), (0, 1.22, 2.52 + LIFT)]
tail = tube(TAIL_PTS, [0.1, 0.085, 0.07, 0.06])
# frangia di pelo ispido sotto la pancia e il petto
fringe = []
for i, y in enumerate(np.linspace(-0.6, 0.62, 9)):
    for sx in (1, -1):
        x = sx * (0.32 + 0.05 * (i % 2))
        q, nq = surf(torso, (x * 0.5, y, 1.6), (x, y, 0.6))
        fringe.append(horn(q - nq * 0.05, nq + np.array([0, 0.5, -0.4]), 0.2 + 0.05 * (i % 3), 0.075, n=3, r1=0.014))

neck = capsule((0, -0.52, 1.86 + LIFT), tuple(hp((0, -0.1, 0.05))), 0.54)
core = union(torso, neck, k=0.25)
core = union(core, H(head_solid), k=0.2)
core = union(core, H(union(*EARS)), k=0.05)
core = union(core, legs, k=0.12)
core = union(core, tail, k=0.07)
core = fast_union(fringe, k=0.04, base=core)
core = shrink(core.intersect(halfspace_z(0.0, above=True)))
m.add("Body", core, FUR, tris=4500, voxel=0.049 * VX)

# disco del grugno, contorno scuro degli occhi e interno delle orecchie (quasi nero)
disc_face = paint(head_solid, cylinder((0, -1.10, -0.01), (0, -1.4, -0.01), 0.19), out=0.016, inn=0.045)
rims = union(*[eye_place(ellipsoid((EA + 0.055, 0.3, EC + 0.05)), sx, (0, EYE_SINK, 0)).subtract(
    eye_place(ellipsoid((EA - 0.01, 0.4, EC - 0.01)), sx, (0, EYE_SINK, 0))) for sx in (1, -1)])
eye_rims = paint(head_solid, rims, out=0.016, inn=0.045)
ear_in = paint(union(*EARS), union(*INNER), out=0.014, inn=0.035)
m.add("Snout", H(union(disc_face, eye_rims, ear_in)), SNOUT, role="detail", tris=600, voxel=0.04 * VX)

# ============================================================ bocca, denti, zanne
m.add("Mouth", H(maw_l), MAW, role="eye", tris=340, voxel=0.046 * VX)
tongue = union(ellipsoid((0.15, 0.3, 0.07), (0, -0.52, -0.25)), ellipsoid((0.12, 0.16, 0.06), (0, -0.82, -0.23)),
               k=0.08).subtract(capsule((0, -0.3, -0.17), (0, -0.95, -0.15), 0.02), k=0.02)
m.add("Tongue", H(JW(tongue)), TONGUE, role="detail", tris=200, voxel=0.038 * VX)

teeth = []
UP_T = [(-1.0, 0.08), (-0.80, 0.12), (-0.72, 0.09), (-0.63, 0.12), (-0.54, 0.08), (-0.45, 0.07)]
LO_T = [(-0.98, 0.08), (-0.78, 0.10), (-0.70, 0.08), (-0.61, 0.11), (-0.52, 0.08), (-0.43, 0.06)]
for sx in (1, -1):
    for y, L in UP_T:
        z = float(lip_z(y))
        e, _ = surf(upper, (0.0, y, z + 0.035), (sx, y, z + 0.035))
        b = np.array([e[0] - sx * 0.03, y, z + 0.04])
        L = L * (1 + rng.normal(0, 0.1))
        teeth.append(horn(b, (sx * 0.12, 0.15, -1.0), L + 0.04, 0.032 + 0.1 * L, n=4, r1=0.005, power=1.2))
    for y, L in LO_T:
        z = float(lip_z(y))
        e, _ = surf(lower_closed, (0.0, y, z - 0.035), (sx, y, z - 0.035))
        b = np.array([e[0] - sx * 0.03, y, z - 0.04])
        L = L * (1 + rng.normal(0, 0.1))
        teeth.append(JW(horn(b, (sx * 0.1, 0.12, 1.0), L + 0.04, 0.03 + 0.1 * L, n=4, r1=0.005, power=1.2)))
m.add("Teeth", H(fast_union(teeth)), BONE, role="shine", tris=700, voxel=0.025 * VX)

# zanne enormi da facocero: escono di lato dalla mandibola, salgono e si piegano a mezzaluna verso l'interno
tusks, tusk_bands = [], []
for sx in (1, -1):
    b = jp(np.array((sx * 0.16, -0.86, -0.24)))
    d0, cu, LT, R0 = norm((sx * 0.9, -0.1, 0.32)), np.array((-sx * 0.5, 0.22, 0.72)), 0.92, 0.12
    tusks.append(horn(b, d0, LT, R0, curl=cu, n=10, r1=0.016, power=1.1))
    tt = 0.32
    c_ = b + d0 * LT * tt + cu * LT * tt * tt
    tan = norm(d0 + 2 * cu * tt)
    rr = R0 + (0.016 - R0) * tt ** 1.1
    tusk_bands.append(chain_link(c_, np.cross(tan, (0, 1, 0)), tan, 0.0, rr + 0.012, 0.034))
TUSK_BANDS = H(union(*tusk_bands))
m.add("Tusks", H(fast_union(tusks)), BONE, role="detail", tris=700, voxel=0.031 * VX)

# ============================================================ setole: cresta irta dalla fronte alla groppa
SPINE = [hp((0, -0.52, 0.46)), hp((0, -0.30, 0.56)), hp((0, -0.05, 0.52)), np.array((0, -0.6, 2.36 + LIFT)),
         np.array((0, -0.30, 2.74 + LIFT)), np.array((0, 0.0, 2.66 + LIFT)), np.array((0, 0.35, 2.38 + LIFT)),
         np.array((0, 0.72, 2.18 + LIFT)), np.array((0, 0.96, 2.08 + LIFT))]
SPINE = resample(SPINE, 0.02)
SP_S = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(SPINE, axis=0), axis=1))])
SP_LEN = float(SP_S[-1])


def spine_at(s):
    i = int(np.clip(np.searchsorted(SP_S, s), 1, len(SPINE) - 1))
    t = (s - SP_S[i - 1]) / max(SP_S[i] - SP_S[i - 1], 1e-9)
    return SPINE[i - 1] * (1 - t) + SPINE[i] * t, norm(SPINE[i] - SPINE[i - 1])


def mane_len(s):
    return float(np.interp(s / SP_LEN, [0.0, 0.12, 0.3, 0.42, 0.6, 0.8, 1.0],
                           [0.2, 0.32, 0.5, 0.62, 0.5, 0.36, 0.22]))


bristles = []
s, j = 0.05, 0
while s < SP_LEN - 0.02:
    c, t = spine_at(s)
    up = norm(np.array([0, 0, 1.0]) - t * t[2])
    p, nrm = surf(core, c - up * 0.35, c + up)
    L = mane_len(s) * rng.uniform(0.85, 1.1)
    sx = 1 if j % 2 == 0 else -1
    for k_, (side, ll, r0) in enumerate(((0.0, 1.0, 0.075), (sx * 1.0, 0.7, 0.06))):
        d = norm(nrm * 1.0 + t * 0.7 + np.array([side * 0.45, 0, 0]) + rng.normal(0, 0.06, 3))
        base = p - nrm * 0.045 + np.array([side * 0.05, 0, 0])
        bristles.append(horn(base, d, L * ll, r0, curl=t * 0.2, n=4, r1=0.01))
    s += 0.135
    j += 1
tip = np.array(TAIL_PTS[-1])
for d in ((0.5, -0.2, 0.6), (-0.5, -0.1, 0.6), (0.1, 0.45, 0.8), (0.0, -0.5, 0.7), (0.3, 0.3, 0.9)):
    bristles.append(horn(tip - np.array([0, 0, 0.04]), d, 0.26, 0.05, n=3, r1=0.01))
m.add("Mane", fast_union(bristles), BRISTLE, role="detail", tris=1250, voxel=0.036 * VX)

# ============================================================ corazza di ferro: spallacci e piastre sulla schiena
plates, rivets, spikes = [], [], []
BANDS = [(0.0, 0.36), (0.42, 0.80)]
for i, (y0, y1) in enumerate(BANDS):
    lift = 0.085 - 0.01 * i

    def band_reg(p, y0=y0, y1=y1):
        zc = 1.9 + LIFT + 0.12 * np.clip((p[:, 1] - 0.2) / 0.7, 0, 1)
        slab = np.maximum(y0 - p[:, 1], p[:, 1] - y1)
        return np.maximum(np.maximum(slab, zc - p[:, 2]), 0.12 - np.abs(p[:, 0]))

    reg = SDF(band_reg, (-1.2, y0, 1.7), (1.2, y1, 3.2))
    plates.append(paint(torso, reg, out=lift, inn=0.02))
    for yr in (y0 + 0.08, y1 - 0.08):
        for sx in (1, -1):
            for a in (24, 52, 76):
                ar = math.radians(a)
                dvec = np.array([sx * math.sin(ar), 0.0, math.cos(ar)])
                q, nn = surf(torso.offset(lift), np.array([0.0, yr, 1.8]), np.array([0.0, yr, 1.8]) + dvec)
                rivets.append(sphere(0.042, tuple(q - nn * 0.01)))
    # spuntone sopra ogni piastra, ai lati della cresta
    for sx in (1, -1):
        o = np.array((0.0, (y0 + y1) / 2, 1.9))
        q, nn = surf(torso.offset(lift), o, o + np.array((sx * 0.45, 0, 0.9)))
        d = norm(nn + np.array([0, 0.35, 0.3]))
        spikes.append(horn(q - d * 0.05, d, 0.32, 0.08, curl=(0, 0.12, 0.0), n=4, r1=0.012))
# spallacci: tre lame sovrapposte a scandole per lato (bordi netti), rivetti sul bordo basso, spuntoni in cima
ZC = 1.84 + LIFT
LAMES = [(17.0, 47.0, 0.115), (43.0, 70.0, 0.09), (66.0, 93.0, 0.065)]
PY0, PY1 = -0.80, 0.04


def lame_fn(p, t0, t1, sx):
    dz = p[:, 2] - ZC
    th = np.degrees(np.arctan2(sx * p[:, 0], dz))
    r = np.sqrt(p[:, 0] ** 2 + dz ** 2)
    dth = np.maximum(t0 - th, th - t1) * (np.pi / 180.0) * r
    f = np.clip((th - 17.0) / 76.0, 0.0, 1.0)
    dy = np.maximum((PY0 + 0.12 * f) - p[:, 1], p[:, 1] - (PY1 - 0.16 * f))
    return np.maximum(dth, dy)


for sx in (1, -1):
    for (t0, t1, lift) in LAMES:
        reg = SDF(lambda p, t0=t0, t1=t1, sx=sx: lame_fn(p, t0, t1, sx), (-1.4, PY0, 0.9), (1.4, PY1, 3.4))
        plates.append(paint(torso, reg, out=lift, inn=0.02))
        th = math.radians(t1 - 5.5)
        f = (t1 - 5.5 - 17.0) / 76.0
        for y in np.linspace(PY0 + 0.12 * f + 0.1, PY1 - 0.16 * f - 0.1, 5):
            o = np.array((0.0, y, ZC))
            q, nn = surf(torso.offset(lift), o, o + np.array((sx * math.sin(th), 0.0, math.cos(th))))
            rivets.append(sphere(0.042, tuple(q - nn * 0.01)))
    for (y, L) in ((-0.58, 0.52), (-0.36, 0.44), (-0.14, 0.32)):
        th = math.radians(31.0)
        o = np.array((0.0, y, ZC))
        q, nn = surf(torso.offset(0.115), o, o + np.array((sx * math.sin(th), 0.0, math.cos(th))))
        d = norm(nn + np.array([0, 0.3, 0.45]))
        spikes.append(horn(q - d * 0.06, d, L + 0.02, 0.095, curl=(0, 0.16, 0.05), n=5, r1=0.014))
# viti a vista con il taglio a croce (toy): una per lato sulla schiena
for sx, y in ((1, 0.62), (-1, 0.2)):
    o = np.array((0.0, y, 1.8))
    q, nn = surf(torso.offset(0.08), o, o + np.array((sx * 0.75, 0, 0.66)))
    head_s = cylinder(tuple(q - nn * 0.02), tuple(q + nn * 0.035), 0.085, round=0.015)
    t1 = norm(np.cross(nn, (1, 0, 0)))
    t2 = norm(np.cross(nn, t1))
    cut = union(capsule(tuple(q + nn * 0.055 + t1 * 0.06), tuple(q + nn * 0.055 - t1 * 0.06), 0.015),
                capsule(tuple(q + nn * 0.055 + t2 * 0.06), tuple(q + nn * 0.055 - t2 * 0.06), 0.015))
    spikes.append(head_s.subtract(cut, k=0.005))
m.add("Armor", fast_union(plates), IRON, material="Metal", role="detail", tris=2000, voxel=0.041 * VX)
m.add("Rivets", fast_union(rivets + [TUSK_BANDS]), STEEL, material="Metal", role="detail", tris=750, voxel=0.03 * VX)
m.add("Spikes", fast_union(spikes), STEEL, material="Metal", role="detail", tris=650, voxel=0.037 * VX)

# ============================================================ zoccoli fessi
hooves = []
for key, L in LEGS.items():
    c, fwd, upv = (np.array(v, dtype=np.float64) for v in L["hoof"])
    M = frame(fwd, upv)
    toes = [ellipsoid((0.1, 0.17, 0.145), (sx * 0.092, -0.035, 0.0)).rot(0, 0, -sx * 7) for sx in (1, -1)]
    shape = union(*toes, k=0.012).intersect(SDF(lambda p: -0.115 - p[:, 2], (-1, -1, -0.115), (1, 1, 1)))
    hooves.append(shape.rotate(M).translate(c))
    pts = [np.array(p) for p in L["pts"]]
    fl = pts[-2]
    back = -norm(fwd)
    # ciuffo scuro di pelo ispido sopra lo zoccolo
    axl = norm(pts[-2] - pts[-1])
    hub = pts[-1] + axl * 0.08
    hooves.append(round_cone(tuple(c), tuple(hub + axl * 0.06), 0.15, 0.165))
    s1 = norm(np.cross(axl, (0, 1, 0)) if abs(axl[1]) < 0.9 else np.cross(axl, (1, 0, 0)))
    s2 = np.cross(axl, s1)
    for a in np.linspace(0, 2 * math.pi, 8, endpoint=False):
        rd = s1 * math.cos(a) + s2 * math.sin(a)
        hooves.append(horn(hub + axl * 0.1 + rd * 0.12, rd * 0.55 - axl * 0.85, 0.15, 0.05, n=3, r1=0.01))
    for sx in (1, -1):
        dw = fl + back * 0.11 + np.array([sx * 0.07, 0, -0.04])
        hooves.append(horn(dw, back * 0.6 + np.array([0, 0, -0.8]), 0.09, 0.04, n=3, r1=0.012))
m.add("Hooves", fast_union(hooves).intersect(halfspace_z(0.0, above=True)), HOOF, role="detail", tris=900,
      voxel=0.0365 * VX)

# ============================================================ occhi rossi incandescenti
eyes = []
for sx in (1, -1):
    eyes.append(eye_place(ellipsoid((EA, EB, EC)).rot(0, sx * 14, 0), sx, (0, EYE_SINK, 0)))
m.add("EyeGlow", H(union(*eyes)), EYE_RED, material="Neon", role="glow", tris=300, voxel=0.021 * VX)

# ============================================================ rabbia: narici + graffi del grugno (Neon "Rage")
nost_glow = union(*[ellipsoid((0.034, 0.03, 0.05), (c[0], c[1] + 0.035, c[2])) for c in NOST])
m.add("Rage", H(union(nost_glow, fast_union(scar_fill))), RAGE, material="Neon", role="glow", tris=450,
      voxel=0.017 * VX)

# ============================================================ vene di rabbia che pulsano sotto la corazza


def vein_pts(p0, d0, n, step, turn):
    pts, d = [np.asarray(p0, float)], norm(d0)
    for j in range(n):
        d = norm(d + rng.normal(0, turn, 3) * 0.5 + (0.35 if j % 2 else -0.35) * np.cross(d, (0, 0, 1)))
        pts.append(pts[-1] + d * step)
    return pts


def vein(base, origin, p0, d0, n=8, step=0.06, turn=0.5, r0=0.027):
    """Vena incandescente: linea serpeggiante sulla superficie che si assottiglia, con un ramo."""
    out = []
    main = vein_pts(p0, d0, n, step, turn)
    br = vein_pts(main[n // 2], norm(np.asarray(d0) + rng.normal(0, 0.8, 3)), n // 2, step * 0.9, turn)
    for pts, rr in ((main, r0), (br, r0 * 0.7)):
        q, nr = project_many(base, [origin] * len(pts), [p - np.asarray(origin, float) for p in pts])
        q = [p + nn * 0.003 for p, nn in zip(q, nr)]
        out.append(tube([tuple(p) for p in q], [max(rr * (1 - j / len(q)) ** 0.7, 0.009) for j in range(len(q))]))
    return union(*out)


VEINS = [
    ((0.0, -0.75, 1.75), (0.66, -0.86, 1.92), (0.1, -0.9, -0.4)),     # collo +x, dal bordo dello spallaccio
    ((0.0, -0.75, 1.75), (0.72, -0.62, 1.42), (0.1, -0.3, -1.0)),     # braccio +x
    ((0.0, -0.75, 1.75), (-0.66, -0.86, 1.92), (-0.1, -0.9, -0.4)),   # collo -x
    ((0.0, 0.62, 1.6), (0.62, 0.74, 1.96), (0.2, 0.3, -1.0)),         # coscia +x
    ((0.0, 0.62, 1.6), (0.56, 0.36, 1.86), (0.2, -0.2, -1.0)),        # fianco +x
    ((0.0, 0.62, 1.6), (-0.62, 0.74, 1.96), (-0.2, 0.3, -1.0)),       # coscia -x
]
veins = [vein(core, o, p0, d0) for o, p0, d0 in VEINS]
m.add("Veins", fast_union(veins), RAGE, material="Neon", role="glow", tris=520, voxel=0.0178 * VX)

# ============================================================ toy horror: toppa cucita sul fianco + cicatrice ricucita
PC, PN = surf(core, (0.2, 0.30, 1.58), (1.0, 0.34, 1.5))
PM = look_matrix(PN)
PW, PH = 0.25, 0.2
PATCH_ROT = rot_matrix((0, 1, 0), 12)
patch_reg = box((PW, 0.4, PH), round=0.05).rotate(PATCH_ROT).rotate(PM).translate(PC)
m.add("Patch", paint(core, patch_reg, out=0.03, inn=0.03), PATCH, material="Fabric", role="detail", tris=300,
      voxel=0.034 * VX)
thread = []
patch_surf = core.offset(0.03)
border = []
for i in range(28):
    tt = 2 * math.pi * i / 28
    x, z = (PW - 0.045) * math.cos(tt), (PH - 0.045) * math.sin(tt)
    sq = max(abs(math.cos(tt)), abs(math.sin(tt)))
    x, z = x / sq ** 0.75, z / sq ** 0.75
    border.append(on_surface(patch_surf, PM @ (PATCH_ROT @ np.array([x, 0.0, z])) + PC, 0.0, 4))
border = resample(border + [border[0]], 0.135)
for i in range(len(border) - 1):
    thread += x_stitch(patch_surf, border[i], border[i + 1] - border[i - 1], size=0.1, r=0.027, lift=-0.012)
# cicatrice ricucita sopra l'occhio destro (-x): taglia l'arcata dall'alto in basso
scar = [hp((-0.30 + 0.02 * t, -0.42 - 0.3 * t, 0.62 - 0.5 * t)) for t in np.linspace(0, 1, 7)]
scar = [on_surface(core, p, 0.0, 6) for p in scar]
thread += [tube([tuple(p) for p in scar], 0.02)]
cs = resample(scar, 0.09)
for i in range(1, len(cs) - 1):
    thread += x_stitch(core, cs[i], cs[i + 1] - cs[i - 1], size=0.095, r=0.025, lift=-0.008)
# cucitura lunga sulla coscia (+x): la pelle e' stata ricucita dopo una battaglia
seam = [on_surface(core, np.array((0.9, 0.5 + 0.28 * t, 1.62 - 0.62 * t)), 0.0, 6) for t in np.linspace(0, 1, 7)]
thread += [tube([tuple(p) for p in seam], 0.02)]
ss = resample(seam, 0.1)
for i in range(1, len(ss) - 1):
    thread += x_stitch(core, ss[i], ss[i + 1] - ss[i - 1], size=0.1, r=0.026, lift=-0.008)
m.add("Thread", fast_union(thread), THREAD, role="detail", tris=800, voxel=0.0218 * VX)

# ============================================================ cavigliera con la catena spezzata (zampa post. sx)
LHL = [np.array(p) for p in LEGS["HL"]["pts"]]
ax = norm(LHL[3] - LHL[2])
cc = LHL[2] * 0.45 + LHL[3] * 0.55
cuff = chain_link(cc, np.cross(ax, (1, 0, 0)), ax, 0.0, 0.185, 0.055)   # cavigliera di ferro
iron = [cuff]
hook = cc + np.array([0.2, 0.08, -0.04])
links = [(hook + np.array([0.0, 0.02, -0.06]), (0, 0.2, 1), (0, 1, 0)),
         (hook + np.array([0.02, 0.08, -0.18]), (0.1, 0.4, 1), (1, 0, 0)),
         (hook + np.array([0.03, 0.17, -0.28]), (0.1, 1, 0.3), (0, 0.3, -1))]
for c_, a_, n_ in links:
    iron.append(chain_link(c_, a_, n_, 0.045, 0.06, 0.031))
lc = np.array([hook[0] + 0.05, hook[1] + 0.36, 0.05])
broken = chain_link(lc, (0.2, 1, 0), (0, 0, 1), 0.045, 0.06, 0.031)
iron.append(broken.subtract(sphere(0.05, tuple(lc + norm((0.2, 1, 0)) * 0.1))))
m.add("Chain", fast_union(iron).intersect(halfspace_z(0.0, above=True)), CHAIN, material="Metal", role="detail",
      tris=550, voxel=0.024 * VX)

# solco di terra sollevato dallo zoccolo che raspa: zolle sfaccettate dietro lo zoccolo
clods = [ellipsoid((0.24, 0.2, 0.08), (0.72, -0.72, 0.0)).rot(0, 0, 20, pivot=(0.72, -0.72, 0.0))]
for (x, y, z, s) in ((0.72, -0.72, 0.05, 0.13), (0.58, -0.66, 0.0, 0.1), (0.86, -0.68, 0.0, 0.1),
                     (0.68, -0.56, 0.0, 0.095), (0.82, -0.84, 0.0, 0.08), (0.61, -0.84, 0.0, 0.075),
                     (0.80, -0.54, 0.0, 0.07), (0.74, -0.44, 0.16, 0.06), (0.67, -0.36, 0.3, 0.045)):
    rot = rng.uniform(0, 70, 3)
    c_ = (x, y, z + s * 0.42)
    clods.append(octahedron(s, c_).rot(*rot, pivot=c_))
m.add("Dirt", fast_union(clods).intersect(halfspace_z(0.0, above=True)), DIRT, role="detail", tris=300,
      voxel=0.025 * VX, smooth=False)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
