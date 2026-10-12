"""Ariete Furioso (RageRam) - pet Primordiale.

Un ariete gigantesco impennato sulle zampe posteriori e proteso in avanti, pronto a dare una testata:
corpo avvolto in una lana scura da nube temporalesca (batuffoli color carbone con le cime piu' chiare,
come nuvoloni illuminati dall'alto), petto enorme, zampe anteriori piegate e alzate, testa bassa che
punta in avanti la fronte corazzata. Corna a spirale gigantesche di ossidiana nera, ad anelli, con la
lava arancione che arde nei solchi fra gli anelli e in una crepa a zig-zag (parte Neon "Flames": il
gioco ci attacca il fuoco). Muso col naso romano, ghigno a fauci aperte pieno di zanne aguzze, occhi
gialli incandescenti con la pupilla orizzontale da capro, zoccoli pesanti cerchiati di ferro.
Tocco "toy horror": un grosso bottone rosso cucito sul petto, sopracciglia ricucite a punti incrociati,
viti a vista sui cerchi degli zoccoli e una chiave di carica arrugginita piantata nella schiena.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, capsule, cylinder, ellipsoid, euler, halfspace_z, look_matrix,  # noqa: E402
                     round_cone, smin, sphere, tube, union)
from lib.toy import Model  # noqa: E402

VX = float(os.environ.get("VX", "1"))  # bozza: VX=1.5 usa voxel piu' grossi per iterare in fretta


# ============================================================ helper (lib/ non si modifica: copiati/adattati qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


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
        print(f"[ram] attenzione: {len(bad)} raggi partono fuori dalla forma, es. {np.round(o[bad[0]], 3)}")
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


class Sweep:
    """Tubo a raggio variabile lungo una polilinea (corna): distanza dal punto piu' vicino meno il raggio."""

    def __init__(self, pts, radii):
        self.P = np.asarray(pts, dtype=np.float64)
        self.seg = np.diff(self.P, axis=0)
        self.ln = np.linalg.norm(self.seg, axis=1)
        self.cum = np.concatenate([[0.0], np.cumsum(self.ln)])
        self.r = np.asarray(radii, dtype=np.float64)
        self.length = float(self.cum[-1])

    def closest(self, p):
        best = np.full(len(p), np.inf)
        s_out = np.zeros(len(p))
        for k in range(len(self.seg)):
            t = np.clip(((p - self.P[k]) @ self.seg[k]) / (self.ln[k] ** 2), 0.0, 1.0)
            c = self.P[k] + t[:, None] * self.seg[k]
            d = np.linalg.norm(p - c, axis=1)
            msk = d < best
            best[msk] = d[msk]
            s_out[msk] = self.cum[k] + t[msk] * self.ln[k]
        return best, s_out

    def at(self, s):
        """Punto e tangente all'ascissa curvilinea s."""
        s = float(np.clip(s, 0.0, self.length))
        k = int(min(np.searchsorted(self.cum, s, side="right") - 1, len(self.seg) - 1))
        t = (s - self.cum[k]) / max(self.ln[k], 1e-9)
        return self.P[k] + self.seg[k] * t, self.seg[k] / self.ln[k]

    def sdf(self, mod=None, scale=1.0):
        def f(p):
            d, s = self.closest(p.astype(np.float64))
            r = np.interp(s, self.cum, self.r) * scale
            if mod is not None:
                r = r * mod(s)
            return (d - r).astype(np.float32)

        pad = float(self.r.max()) * 1.25 + 0.02
        return SDF(f, self.P.min(0) - pad, self.P.max(0) + pad)

    def field(self, fn):
        """SDF di una regione definita sull'ascissa curvilinea: fn(s) < 0 dentro."""
        def f(p):
            _, s = self.closest(p.astype(np.float64))
            return fn(s).astype(np.float32)

        pad = float(self.r.max()) * 1.3 + 0.05
        return SDF(f, self.P.min(0) - pad, self.P.max(0) + pad)


from lib.mesher import mesh_sdf  # noqa: E402

# ============================================================ colori
WOOL = (58, 60, 70)          # lana carbone da nube temporalesca
WOOL_LIGHT = (138, 144, 158)  # cime dei batuffoli, piu' chiare (nuvoloni illuminati dall'alto)
HIDE = (112, 74, 52)         # muso e zampe: bruno terroso
MUZZLE = (170, 140, 112)     # punta del muso piu' chiara
OBSIDIAN = (30, 25, 34)      # corna di ossidiana
LAVA = (255, 116, 20)        # lava nelle crepe (Neon "Flames")
EYE_GLOW = (255, 206, 48)    # occhi gialli incandescenti
PUPIL = (22, 10, 10)
HOOF = (52, 48, 54)
IRON = (124, 118, 116)
RUST = (156, 74, 38)
BUTTON = (184, 42, 32)
THREAD = (242, 228, 194)
BONE = (244, 232, 204)
MAW = (50, 14, 18)
TONGUE = (176, 52, 66)

m = Model("RageRam", "pet", voxel=0.03 * VX)
rng = np.random.default_rng(5)
UP = np.array([0.0, 0.0, 1.0])

# ============================================================ testa (spazio locale: origine sulla nuca, muso verso -Y)
HEAD_POS = np.array([0.0, -0.86, 2.88])
HS = 1.38
R_HEAD = euler(32.0, 0.0, 8.0)     # testa bassa, fronte in avanti: pronto alla testata
HINGE = np.array([0.0, -0.22, -0.29])
JAW = 30.0
R_JAW = euler(JAW, 0.0, 0.0)


def H(s):
    return s.scale(HS).rotate(R_HEAD).translate(HEAD_POS)


def hp(p):
    return rot_pts(R_HEAD, np.asarray(p, dtype=np.float64) * HS) + HEAD_POS


def JW(s):
    return s.rotate(R_JAW, pivot=HINGE)


def lip_z(y):
    return np.interp(y, [-1.3, -0.82, -0.72, -0.6, -0.48, 0.2], [-0.31, -0.30, -0.25, -0.23, -0.28, -0.29])


cran = ellipsoid((0.32, 0.33, 0.31), (0, -0.14, -0.06))
boss = ellipsoid((0.29, 0.20, 0.21), (0, -0.30, 0.04))          # fronte corazzata (la testata)
face = loft(-0.28, -0.74, 0.27, 0.20, 0.25, 0.20, -0.12, -0.24, r=0.1, rc=0.04, tp=0.15)
ridge = capsule((0, -0.42, 0.06), (0, -0.70, -0.06), 0.11)      # naso romano
muzzle = ellipsoid((0.19, 0.12, 0.17), (0, -0.76, -0.27))
cheeks = [ellipsoid((0.21, 0.24, 0.22), (sx * 0.19, -0.36, -0.2)) for sx in (1, -1)]
brows = [capsule((sx * 0.05, -0.51, 0.07), (sx * 0.34, -0.35, 0.18), 0.085) for sx in (1, -1)]
jaw = loft(-0.22, -0.74, 0.21, 0.16, 0.11, 0.09, -0.40, -0.38, r=0.06, rc=0.03)
chin = ellipsoid((0.13, 0.08, 0.08), (0, -0.72, -0.43))
head0 = union(cran, boss, *cheeks, k=0.12)
head0 = union(head0, face, ridge, k=0.12)
head0 = union(head0, muzzle, k=0.08)
head0 = union(head0, *brows, k=0.06)
head0 = shrink(union(head0, jaw, chin, k=0.08))

# occhi gialli da capro sotto arcate aggrottate (guardano in avanti, oltre la fronte abbassata)
EYE_D = {sx: norm((sx * 0.62, -0.62, 0.4)) for sx in (1, -1)}
EYE_C = {}
for sx in (1, -1):
    o = np.array((sx * 0.08, -0.38, -0.06))
    EYE_C[sx], _ = surf(head0, o, o + EYE_D[sx])


def eye_place(shape, sx, offset=(0.0, 0.0, 0.0)):
    return shape.translate(offset).rotate(look_matrix(EYE_D[sx])).translate(EYE_C[sx])


EA, EB, EC = 0.12, 0.055, 0.085
EYE_SINK = 0.022
sockets = union(*[eye_place(ellipsoid((EA + 0.025, 0.07, EC + 0.02)), sx, (0, 0.035, 0)) for sx in (1, -1)])
head1 = head0.subtract(sockets, k=0.025)
LID_CUT, LID_SLOPE = 0.018, 0.7
lids = []
for sx in (1, -1):
    A, B, C = EA + 0.02, EB + 0.02, EC + 0.02

    def lid_plane(p, sx=sx):
        return (LID_CUT - LID_SLOPE * sx * p[:, 0] - p[:, 2]) / math.sqrt(1 + LID_SLOPE ** 2)

    lid = ellipsoid((A, B, C)).intersect(SDF(lid_plane, (-A, -B, -C), (A, B, C)), k=0.01)
    lids.append(eye_place(lid, sx, (0, EYE_SINK, 0)))
head1 = union(head1, *lids, k=0.01)

# narici dilatate
NOST = [(sx * 0.075, -0.87, -0.22) for sx in (1, -1)]
nostrils = union(*[ellipsoid((0.035, 0.05, 0.05), c).rot(0, sx * 30, 0, pivot=c) for sx, c in zip((1, -1), NOST)])
head2 = head1.subtract(nostrils, k=0.015)


def upper_region(p):
    f = lip_z(p[:, 1]) - p[:, 2]
    g = (HINGE[1] + 0.02) - p[:, 1]
    return np.minimum(f, g)


U_REG = SDF(upper_region, (-3, -3, -3), (3, 3, 3))
L_REG = SDF(lambda p: -upper_region(p), (-3, -3, -3), (3, 3, 3))
upper = head2.intersect(U_REG, k=0.012)
lower_closed = head2.intersect(L_REG, k=0.012)
head_solid = shrink(union(upper, JW(lower_closed), k=0.02))


def gap_fn(p):
    f = p[:, 2] - lip_z(p[:, 1])
    q = (p - HINGE) @ R_JAW.astype(np.float32) + HINGE
    g = lip_z(q[:, 1]) - q[:, 2]
    h = p[:, 1] - (HINGE[1] - 0.04)
    return np.maximum(np.maximum(f, g), h)


GAP = SDF(gap_fn, (-0.4, -1.3, -0.8), (0.4, 0.0, 0.0))
maw_l = head0.offset(-0.035).intersect(GAP)

# orecchie orizzontali sotto le corna
EARS = []
for sx in (1, -1):
    ax = norm((sx * 0.8, 0.5, -0.45))
    base = np.array((sx * 0.24, -0.06, -0.18))
    EARS.append(ell(base + ax * 0.15, (0.065, 0.03, 0.15), axis=ax, side=(0, 0, 1)))

# ============================================================ corna a spirale (ossidiana) con la lava negli anelli
HORN_P = 0.105      # passo degli anelli


def horn_path(sx, n=72):
    a0, a1 = math.radians(-35.0), math.radians(252.0)
    pts, rads = [], []
    for i in range(n + 1):
        t = i / n
        a = a0 + (a1 - a0) * t
        R = 0.44 * math.exp(-0.72 * t)
        pts.append((sx * (0.14 + 0.44 * t ** 0.85), 0.10 + R * math.sin(a), -0.14 + R * math.cos(a)))
        rads.append(0.038 + 0.165 * (1 - t) ** 0.85)
    return pts, rads


HORNS = {sx: Sweep(*horn_path(sx)) for sx in (1, -1)}


def ridge_mod_for(Ls):
    def mod(s):
        return 1.0 + 0.1 * np.cos(2 * np.pi * s / HORN_P) * smoothstep(0.03 * Ls, 0.15 * Ls, s)
    return mod


horn_black, lava = [], []
for sx, sw in HORNS.items():
    Ls = sw.length
    black = sw.sdf(mod=ridge_mod_for(Ls))
    # crepa a zig-zag lungo il lato esterno della spirale
    crack = []
    for s in np.linspace(0.12 * Ls, 0.86 * Ls, 34):
        c, t = sw.at(s)
        out = np.array([sx, 0.0, 0.0]) - t * t[0] * sx
        out = norm(out)
        side = np.cross(t, out)
        phi = 0.55 * math.sin(s * 46.0) + 0.25 * math.sin(s * 19.0 + sx)
        r = float(np.interp(s, sw.cum, sw.r))
        crack.append(c + (out * math.cos(phi) + side * math.sin(phi)) * r * 1.02)
    groove = tube([tuple(p) for p in crack], 0.034)
    horn_black.append(black.subtract(groove, k=0.01))
    # nucleo di lava liscio dentro il corno: affiora nei solchi fra gli anelli e nella crepa
    core = sw.sdf(scale=0.945)
    span = sw.field(lambda s, Ls=Ls: np.maximum(0.08 * Ls - s, s - 0.9 * Ls))
    lava.append(core.intersect(span, k=0.02))
m_horns = H(fast_union(horn_black))
m_lava = H(fast_union(lava))

# ============================================================ corpo impennato (spazio Blender)
torso = union(
    ellipsoid((0.44, 0.42, 0.44), (0, 0.50, 1.36)),   # bacino
    ellipsoid((0.46, 0.44, 0.48), (0, 0.16, 1.70)),   # ventre (vita piu' stretta)
    ellipsoid((0.58, 0.50, 0.54), (0, -0.16, 2.02)),  # petto enorme, proteso in avanti
    ellipsoid((0.52, 0.44, 0.42), (0, -0.30, 2.28)),  # spalle
    k=0.3)
neck = tube([(0, -0.34, 2.28), (0, -0.56, 2.54), tuple(hp((0, 0.02, -0.16)))], [0.38, 0.35, 0.3], k=0.08)

LEGS = {
    # posteriori: accovacciate, reggono tutto il peso
    "HL": dict(pts=[(0.36, 0.52, 1.36), (0.51, 0.10, 1.04), (0.53, 0.70, 0.62), (0.53, 0.56, 0.21), (0.53, 0.52, 0.15)],
               r=[0.36, 0.23, 0.16, 0.14, 0.135], hoof=((0.53, 0.47, 0.13), (0.04, -1, 0), (0, 0, 1))),
    "HR": dict(pts=[(-0.36, 0.52, 1.36), (-0.51, 0.16, 1.02), (-0.53, 0.76, 0.60), (-0.53, 0.62, 0.21),
                    (-0.53, 0.58, 0.15)],
               r=[0.36, 0.23, 0.16, 0.14, 0.135], hoof=((-0.53, 0.53, 0.13), (-0.04, -1, 0), (0, 0, 1))),
    # anteriori: alzate e piegate davanti al petto (la sinistra piu' in alto, colpisce l'aria)
    "FL": dict(pts=[(0.36, -0.36, 2.08), (0.47, -0.74, 1.90), (0.51, -1.14, 2.08), (0.52, -1.24, 1.74),
                    (0.52, -1.23, 1.66)],
               r=[0.28, 0.17, 0.125, 0.115, 0.11], hoof=((0.52, -1.21, 1.56), (0, -0.9, -0.45), (0, -0.45, 0.9))),
    "FR": dict(pts=[(-0.36, -0.36, 2.02), (-0.47, -0.72, 1.76), (-0.51, -1.10, 1.78), (-0.52, -1.16, 1.44),
                    (-0.52, -1.14, 1.36)],
               r=[0.28, 0.17, 0.125, 0.115, 0.11], hoof=((-0.52, -1.12, 1.26), (0, -0.9, -0.45), (0, -0.45, 0.9))),
}
hide_legs, wool_limbs = [], []
for key, L in LEGS.items():
    pts = [np.array(p) for p in L["pts"]]
    hide_legs.append(tube([tuple(p) for p in pts[1:]], L["r"][1:], k=0.04))
    hide_legs.append(round_cone(tuple(pts[0] * 0.3 + pts[1] * 0.7), tuple(pts[1]), L["r"][1] * 1.15, L["r"][1]))
    f_ = 0.5 if key[0] == "H" else 0.65
    wool_limbs.append(round_cone(tuple(pts[0]), tuple(pts[0] * (1 - f_) + pts[1] * f_), L["r"][0] * 1.15,
                                 L["r"][1] * 1.55))
wool_core = union(torso, neck, k=0.2)
wool_core = shrink(union(wool_core, *wool_limbs, k=0.12))

# chiave di carica e bottone: dove stanno (niente batuffoli li')
BTN_C, BTN_N = surf(wool_core, (0, 0.1, 1.3), (0, -1.0, 1.26))
BTN_N = norm(BTN_N + np.array([0.0, -1.2, 0.2]))   # il bottone guarda chi lo osserva
KEY_C, KEY_N = surf(wool_core, (0, -0.1, 2.18), (0, 1.0, 2.4))

# batuffoli da nuvola temporalesca sparsi sulla superficie (campionamento a distanza minima)
verts, _f, _n = mesh_sdf(wool_core, 0.05)
verts = verts[rng.permutation(len(verts))]
nrms = grad_many(wool_core, verts)
puffs, caps, chosen = [], [], []
SPACING = 0.29
for v, nv in zip(verts, nrms):
    if np.linalg.norm(v - BTN_C) < 0.36 or np.linalg.norm(v - KEY_C) < 0.15 or v[2] < 0.7:
        continue
    if chosen and np.min(np.sum((np.asarray(chosen) - v) ** 2, axis=1)) < SPACING ** 2:
        continue
    chosen.append(v)
    r = rng.uniform(0.19, 0.25)
    c = v - nv * r * 0.38
    puffs.append(sphere(r, tuple(c)))
    if nv[2] > -0.2 and rng.random() < 0.55:
        caps.append(sphere(r * 0.6, tuple(c + norm(UP * 1.5 + nv) * r * 0.72)))
# nuvoletta sulla nuca, fra le corna, e codino
for p in ((0.0, -0.05, 0.16), (0.1, 0.08, 0.1), (-0.1, 0.08, 0.1), (0.0, 0.16, 0.0)):
    q = hp(p)
    puffs.append(sphere(0.15 * HS, tuple(q)))
    caps.append(sphere(0.11 * HS, tuple(q + UP * 0.1)))
for p, r in (((0, 0.82, 1.08), 0.16), ((0.06, 0.92, 0.96), 0.13), ((-0.05, 0.9, 0.88), 0.11)):
    puffs.append(sphere(r, p))
wool = fast_union(puffs, k=0.045, base=wool_core)
wool = shrink(wool.intersect(halfspace_z(0.0, above=True)))
m.add("Wool", wool, WOOL, material="Fabric", tris=3400, voxel=0.042 * VX)
m.add("WoolTufts", paint(wool, fast_union(caps), out=0.02, inn=0.09), WOOL_LIGHT, material="Fabric", role="detail",
      tris=1300, voxel=0.045 * VX)

# ============================================================ pelle: testa, orecchie, zampe
m.add("Face", H(union(head_solid, *EARS, k=0.03)), HIDE, role="detail", tris=2100, voxel=0.036 * VX)
m.add("Legs", union(*hide_legs), HIDE, role="detail", tris=1300, voxel=0.046 * VX)

# ============================================================ corna e lava
m.add("Horns", m_horns, OBSIDIAN, role="detail", tris=2700, voxel=0.033 * VX, reflectance=0.12)
m.add("Flames", m_lava, LAVA, material="Neon", role="glow", tris=800, voxel=0.05 * VX)

# ============================================================ bocca, denti, lingua
m.add("Mouth", H(maw_l), MAW, role="eye", tris=250, voxel=0.048 * VX)
teeth = []
UP_T = [(-0.74, 0.16), (-0.66, 0.09), (-0.59, 0.11), (-0.52, 0.08), (-0.45, 0.08), (-0.38, 0.06)]
LO_T = [(-0.71, 0.14), (-0.63, 0.08), (-0.56, 0.09), (-0.49, 0.07), (-0.42, 0.06)]
for sx in (1, -1):
    for y, L in UP_T:
        z = float(lip_z(y))
        e, _ = surf(upper, (0.0, y, z + 0.03), (sx, y, z + 0.03))
        b = np.array([e[0] - sx * 0.025, y, z + 0.035])
        teeth.append(horn(b, (sx * 0.1, 0.12, -1.0), L + 0.035, 0.026 + 0.12 * L, n=4, r1=0.004, power=1.2))
    for y, L in LO_T:
        z = float(lip_z(y))
        e, _ = surf(lower_closed, (0.0, y, z - 0.03), (sx, y, z - 0.03))
        b = np.array([e[0] - sx * 0.025, y, z - 0.035])
        teeth.append(JW(horn(b, (sx * 0.08, 0.1, 1.0), L + 0.035, 0.024 + 0.12 * L, n=4, r1=0.004, power=1.2)))
m.add("Teeth", H(fast_union(teeth)), BONE, role="shine", tris=650, voxel=0.027 * VX)
tongue = ellipsoid((0.11, 0.22, 0.05), (0, -0.52, -0.37)).subtract(capsule((0, -0.34, -0.32), (0, -0.72, -0.32), 0.015),
                                                                     k=0.015)
m.add("Tongue", H(JW(tongue)), TONGUE, role="detail", tris=150, voxel=0.032 * VX)

# ============================================================ occhi
eyes, pupils = [], []
for sx in (1, -1):
    eyes.append(eye_place(ellipsoid((EA, EB, EC)), sx, (0, EYE_SINK, 0)))
    pupils.append(eye_place(ellipsoid((0.068, 0.02, 0.017)), sx, (sx * 0.006, EYE_SINK - EB + 0.008, -0.004)))
m.add("EyeGlow", H(union(*eyes)), EYE_GLOW, material="Neon", role="glow", tris=260, voxel=0.024 * VX)
m.add("Pupils", H(union(*pupils)), PUPIL, role="eye", tris=160, voxel=0.0114 * VX)

# ============================================================ zoccoli pesanti cerchiati di ferro (con le viti)
hooves, iron = [], []
for key, L in LEGS.items():
    c, fwd, upv = (np.array(v, dtype=np.float64) for v in L["hoof"])
    M = frame(fwd, upv)
    toes = [ellipsoid((0.1, 0.16, 0.14), (sx * 0.09, -0.035, 0.0)).rot(0, 0, -sx * 7) for sx in (1, -1)]
    shape = union(*toes, k=0.012).intersect(SDF(lambda p: -0.11 - p[:, 2], (-1, -1, -0.11), (1, 1, 1)))
    hooves.append(shape.rotate(M).translate(c))
    pts = [np.array(p) for p in L["pts"]]
    axl = norm(pts[-2] - pts[-1])
    band_c = c + axl * 0.1
    s1 = norm(np.cross(axl, (0, 1, 0)) if abs(axl[1]) < 0.9 else np.cross(axl, (1, 0, 0)))
    s2 = np.cross(axl, s1)
    iron.append(chain_link(band_c, s1, axl, 0.0, 0.165, 0.045))   # cerchio di ferro sopra lo zoccolo
    for a in np.linspace(0, 2 * math.pi, 4, endpoint=False) + 0.4:
        rd = s1 * math.cos(a) + s2 * math.sin(a)
        iron.append(sphere(0.048, tuple(band_c + rd * 0.2)))
m.add("Hooves", fast_union(hooves).intersect(halfspace_z(0.0, above=True)), HOOF, role="detail", tris=650,
      voxel=0.031 * VX)

# chiave di carica arrugginita piantata nella schiena (toy horror)
kd = norm(KEY_N + np.array([0, 0.15, 0.25]))
k0 = KEY_C - kd * 0.08
k1 = KEY_C + kd * 0.3
key = [cylinder(tuple(k0), tuple(k1), 0.045, round=0.01), cylinder(tuple(KEY_C - kd * 0.01), tuple(KEY_C + kd * 0.05),
                                                                   0.09, round=0.015)]
kx = norm(np.cross(kd, (1, 0, 0)))   # le alette stanno nel piano verticale: si vedono di lato
for sgn in (1, -1):
    ctr = k1 + kd * 0.06 + kx * sgn * 0.13
    key.append(chain_link(ctr, kx, np.cross(kd, kx), 0.0, 0.1, 0.035))
key.append(sphere(0.06, tuple(k1 + kd * 0.06)))
m.add("Key", fast_union(key), RUST, material="Metal", role="detail", tris=450, voxel=0.0195 * VX)
m.add("Iron", fast_union(iron), IRON, material="Metal", role="detail", tris=450, voxel=0.0345 * VX)

# ============================================================ bottone cucito sul petto + sopracciglia ricucite
BM = look_matrix(BTN_N)
BR = 0.25
btn = cylinder((0, 0.02, 0), (0, -0.06, 0), BR, round=0.025)
rim = chain_link((0, -0.065, 0), (0, 0, 1), (0, 1, 0), 0.0, BR - 0.035, 0.022)
holes = union(*[cylinder((hx, 0.1, hz), (hx, -0.2, hz), 0.03) for hx in (-0.062, 0.062) for hz in (-0.062, 0.062)])
button = union(btn, rim).subtract(holes, k=0.006).rot(0, 18, 0)
m.add("Button", button.rotate(BM).translate(BTN_C), BUTTON, role="detail", tris=400, voxel=0.025 * VX)
thread = []
for a, b in (((-0.062, -0.062), (0.062, 0.062)), ((-0.062, 0.062), (0.062, -0.062))):
    pa = np.array([a[0], -0.07, a[1]])
    pb = np.array([b[0], -0.07, b[1]])
    th = capsule(tuple(pa), tuple(pb), 0.026).rot(0, 18, 0)
    thread.append(th.rotate(BM).translate(BTN_C))
# sopracciglia ricucite: tre punti a X inclinati sopra ogni occhio
brow_shapes = []
for sx in (1, -1):
    for j in range(3):
        t_ = j / 2
        p = np.array((sx * (0.11 + 0.19 * t_), -0.49 + 0.13 * t_, 0.11 + 0.1 * t_))
        q = on_surface(head_solid, p, 0.0, 6)
        tdir = np.array((sx * 0.17, 0.12, 0.09))
        brow_shapes += x_stitch(head_solid, q, tdir, size=0.095, r=0.02, lift=-0.005)
thread += [H(s) for s in brow_shapes]
m.add("Thread", fast_union(thread), THREAD, role="detail", tris=650, voxel=0.0168 * VX)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
