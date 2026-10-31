"""Balena Cosmica (CosmicWhale) - pet ULTRA del negozio Robux: il gigante piu' spettacolare del gioco.

Una megattera colossale che nuota fra le stelle: sale verso l'alto con il corpo a S dolce (testa quasi in
piano, corpo che sale ripido, coda che si rialza), sospesa sopra un piccolo vortice di nebulosa: sbuffi
lavanda in tre bracci a spirale con sbuffi luminosi rosa che filtrano fra l'uno e l'altro (la parte piu'
bassa, appoggiata a z = 0). Dorso indaco profondo che sfuma nel viola dei fianchi, pennellate di nebulosa
magenta e ciano arricciate a spirale e tante lentiggini-stella luminose. Pancia lavanda chiara con le
pieghe golari profonde della megattera, bitorzoli sul muso, pinna dorsale sulla gobba. Pinne pettorali
lunghissime aperte come ali, con il bordo d'attacco a bitorzoli e il contorno ciano luminoso. Le pinne
caudali, girate un po' di lato e bordate di ciano, lasciano una scia di cometa: un ventaglio di strisce
luminose rosa che si assottigliano, quella centrale arricciata come la cresta di un'onda. Sopra la
schiena orbita un piccolo pianeta turchese con l'anello d'oro inclinato, con due lune minuscole.
Faccia: grandi occhi saggi a palpebra pesante con le pupille a stella luminose, ghigno storto da furbetto
con i dentini aguzzi a incastro. Tocco "toy horror": una cucitura d'oro lungo la pancia, strappata in un
punto, da cui esce l'imbottitura di polvere di stelle, e una grande chiave di carica d'ottone nella schiena.

Effetti del gioco (Visuals.PET_FX): "Stars" = lentiggini-stella, imbottitura e stelline della scia
(scintille di stelle); "Nebula" = scia di cometa e luce rosa del vortice (bagliore di nebulosa).
Gli altri pezzi luminosi hanno nomi diversi (EyeGlow, FinGlowR/L, TailGlow). Le pinne pettorali sono i
gruppi FinR/FinL con il perno alla spalla (il gioco le fa oscillare attorno all'asse avanti-dietro).
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import SDF, capsule, ellipsoid, euler, project, round_cone, smin, sphere, star_points, tube, union  # noqa: E402
from lib.toy import Model  # noqa: E402

# ============================================================ colori
NAVY = (36, 32, 116)          # dorso: indaco profondo
VIOLET = (112, 54, 204)       # fianchi
LAVENDER = (230, 218, 255)    # pancia e pieghe golari
MAGENTA = (240, 66, 196)      # pennellate di nebulosa
CYAN = (40, 214, 255)
FIN = (86, 52, 186)           # pinne pettorali
STAR = (255, 236, 168)        # stelle bianco-oro (Neon)
RIM = (64, 236, 255)          # contorni luminosi delle pinne e della coda (Neon)
NEBULA = (255, 104, 222)      # scia di cometa e filamenti della nebulosa (Neon)
EYE_DARK = (20, 12, 52)       # iride
EYE_STAR = (255, 222, 96)     # pupille a stella (Neon)
WHITE = (255, 255, 255)
MOUTH = (44, 10, 58)
TOOTH = (255, 250, 242)
THREAD = (255, 206, 90)       # filo d'oro della cucitura
BRASS = (226, 164, 56)        # chiave di carica e anello del pianeta
CLOUD = (190, 140, 255)       # sbuffi del vortice di nebulosa
PLANET = (34, 198, 190)
MOON = (232, 226, 250)


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
    return [np.asarray(q, dtype=np.float64) for q in out]


def piping(points, radii, step=0.03):
    """Tubo morbido lungo una curva (unione veloce di capsule corte): fili, scie, contorni luminosi.
    radii: un raggio, uno per punto, oppure pochi valori distribuiti uniformemente lungo la curva."""
    pts = [np.asarray(p, dtype=np.float64) for p in points]
    rad = np.asarray(radii if np.ndim(radii) else [radii] * len(pts), dtype=np.float64)
    seg = np.linalg.norm(np.diff(np.array(pts), axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    dense = resample(pts, step)
    where = cum if len(rad) == len(pts) else np.linspace(0.0, cum[-1], len(rad))
    rs = np.interp(np.linspace(0.0, cum[-1], len(dense)), where, rad)
    return fast_union([round_cone(tuple(dense[i]), tuple(dense[i + 1]), rs[i], rs[i + 1]) for i in range(len(dense) - 1)],
                      margin=0.01)


def skin_paint(base, region, out=0.018, inn=0.06, margin=0.05):
    """Vernice a guscio sottile sulla pelle di 'base' dentro 'region'. La pelle (economica) viene valutata
    per prima e la regione (costosa) solo vicino alla pelle."""
    def f(p):
        c = base(p)
        d = np.maximum(c - out, -(c + inn)).astype(np.float32)
        idx = np.nonzero(d < margin)[0]
        if len(idx):
            d[idx] = np.maximum(d[idx], region(p[idx]))
        return d

    return SDF(f, np.maximum(region.lo, base.lo - out), np.minimum(region.hi, base.hi + out))


def dome(r, center, base_pt, nrm):
    """Sfera tagliata dal piano che passa per base_pt con normale nrm (la parte dentro la pelle non serve)."""
    nrm = np.asarray(nrm, dtype=np.float32)
    b = np.asarray(base_pt, dtype=np.float32)
    plane = SDF(lambda q: (b - q) @ nrm, np.asarray(center) - r - 0.01, np.asarray(center) + r + 0.01)
    return sphere(r, tuple(center)).intersect(plane)


def thin(shape, out, inn):
    """Guscio sottile di una forma (per disegni sopra altre parti)."""
    return SDF(lambda p: (lambda d: np.maximum(d - out, -(d + inn)))(shape(p)), shape.lo - out, shape.hi + out)


def rodrigues(v, k, ang):
    """Ruota il vettore v attorno all'asse k di ang gradi."""
    v, k = np.asarray(v, dtype=np.float64), norm(k)
    a = math.radians(ang)
    return v * math.cos(a) + np.cross(k, v) * math.sin(a) + k * (k @ v) * (1 - math.cos(a))


def basis(out, up_hint):
    """Matrice (colonne x, y, z) con z = out e y il piu' vicino possibile a up_hint."""
    z = norm(out)
    y = np.asarray(up_hint, dtype=np.float64)
    y = y - z * (y @ z)
    if np.linalg.norm(y) < 1e-6:
        y = np.array([0.0, 1.0, 0.0]) - z * z[1]
    y = norm(y)
    return np.stack([np.cross(y, z), y, z], axis=1).astype(np.float32)


def local(shape_fn, M, origin, lo, hi):
    """Forma definita da shape_fn(q) in coordinate locali (colonne di M = assi locali, origine origin)."""
    M = np.asarray(M, dtype=np.float32)
    O = np.asarray(origin, dtype=np.float32)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])],
                       dtype=np.float32) @ M.T + O
    return SDF(lambda p: shape_fn((p - O) @ M), corners.min(0), corners.max(0))


def poly_d2(pts):
    """Distanza con segno 2D da un poligono semplice (vertici Nx2)."""
    pts = np.asarray(pts, dtype=np.float32)
    keep = [i for i in range(len(pts)) if np.linalg.norm(pts[i] - pts[i - 1]) > 1e-6]
    pts = pts[keep]
    edges = [(pts[i], pts[i - 1]) for i in range(len(pts))]

    def d2(px, py):
        d = np.full(px.shape, np.inf, dtype=np.float32)
        s = np.ones(px.shape, dtype=np.float32)
        for vi, vj in edges:
            ex, ey = vj[0] - vi[0], vj[1] - vi[1]
            wx, wy = px - vi[0], py - vi[1]
            t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey), 0.0, 1.0)
            bx, by = wx - ex * t, wy - ey * t
            d = np.minimum(d, bx * bx + by * by)
            c1 = py >= vi[1]
            c2 = py < vj[1]
            c3 = ex * wy > ey * wx
            s = np.where((c1 & c2 & c3) | (~c1 & ~c2 & ~c3), -s, s)
        return s * np.sqrt(d)

    return d2


def lamina(outline, origin, u_dir, v_dir, t_edge=0.014, slope=0.4, t_max=0.08, r=0.006, warp=None, pad=0.0):
    """Forma piatta 'a gemma' (pinne, coda, stelle): contorno 2D (u, v) estruso lungo n = u x v, sottile sul
    bordo e piu' spessa all'interno. warp(q) deforma le coordinate locali (piega, torsione): pad = quanto
    la forma deformata esce dal piano. Il contorno 2D viene valutato solo vicino al piano (veloce)."""
    U = norm(u_dir)
    V = np.asarray(v_dir, dtype=np.float64)
    V = norm(V - U * (V @ U))
    N = np.cross(U, V)
    M = np.stack([U, V, N], axis=1).astype(np.float32)
    O = np.asarray(origin, dtype=np.float32)
    d2 = poly_d2(outline)
    pts = np.asarray(outline, dtype=np.float64)
    ext = pts.max(0) - pts.min(0)
    tm = min(t_edge + slope * 0.5 * float(min(ext)), t_max)

    def f(p):
        q = (p - O) @ M
        if warp is not None:
            q = warp(q)
        d = (np.abs(q[:, 2]) - tm).astype(np.float32)
        idx = np.nonzero(d < 0.05)[0]
        if len(idx):
            qq = q[idx]
            dd = d2(qq[:, 0], qq[:, 1])
            th = np.minimum(t_edge + slope * np.maximum(-dd, 0.0), tm)
            a = dd + r
            b = np.abs(qq[:, 2]) - th + r
            d[idx] = np.minimum(np.maximum(a, b), 0.0) + np.sqrt(np.maximum(a, 0.0) ** 2 + np.maximum(b, 0.0) ** 2) - r
        return d

    corners = np.array([O + U * u + V * v + N * s * (tm + 0.02 + pad) for u, v in pts for s in (-1, 1)])
    return SDF(f, corners.min(0) - 0.02 - pad, corners.max(0) + 0.02 + pad)


def table(us, vs, n=2001):
    """Profilo liscio (PCHIP: niente oscillazioni) campionato, valutato con np.interp (veloce)."""
    from scipy.interpolate import PchipInterpolator
    f = PchipInterpolator(us, vs)
    xs = np.linspace(us[0], us[-1], n)
    ys = f(xs).astype(np.float32)
    return lambda u: np.interp(u, xs, ys).astype(np.float32)


# ============================================================ spina dorsale a S e corpo a sezioni ellittiche
class Spine:
    """Spina dorsale (polilinea densa nel piano YZ, dal muso alla coda). Per ogni punto da' u (0 = punta del
    muso, 1 = attacco della coda), lo scarto laterale x, lo scarto n lungo la normale 'su' della sezione e la
    sporgenza a oltre le estremita'. Le coordinate vengono da una tabella 2D (y, z) precalcolata."""

    def __init__(self, P, step=0.01, pad=1.4):
        self.P = np.asarray(P, dtype=np.float64)
        seg = np.diff(self.P, axis=0)
        self.len = np.linalg.norm(seg, axis=1)
        self.D = seg / self.len[:, None]
        self.cum = np.concatenate([[0.0], np.cumsum(self.len)])
        self.L = float(self.cum[-1])
        T = np.vstack([self.D[:1], self.D[:-1] + self.D[1:], self.D[-1:]])
        self.T = T / np.linalg.norm(T, axis=1)[:, None]
        self.lo = self.P.min(0) - pad
        hi = self.P.max(0) + pad
        self.step = step
        ys = np.arange(self.lo[0], hi[0] + step, step)
        zs = np.arange(self.lo[1], hi[1] + step, step)
        self.ny, self.nz = len(ys), len(zs)
        Y, Z = np.meshgrid(ys, zs, indexing="ij")
        u, n, a = self.closest(np.stack([Y.ravel(), Z.ravel()], axis=1))
        self.tu = u.reshape(self.ny, self.nz).astype(np.float32)
        self.tn = n.reshape(self.ny, self.nz).astype(np.float32)
        self.ta = a.reshape(self.ny, self.nz).astype(np.float32)

    def closest(self, Q, chunk=1500):
        A = self.P[:-1]
        M = len(A)
        us, ns, as_ = [], [], []
        for i0 in range(0, len(Q), chunk):
            q = Q[i0:i0 + chunk]
            w = q[:, None, :] - A[None, :, :]
            t = np.clip(np.einsum("cmk,mk->cm", w, self.D), 0.0, self.len[None, :])
            diff = w - t[:, :, None] * self.D[None, :, :]
            j = np.argmin(np.einsum("cmk,cmk->cm", diff, diff), axis=1)
            r = np.arange(len(q))
            tj = t[r, j]
            fr = (tj / self.len[j])[:, None]
            Tv = self.T[j] * (1 - fr) + self.T[j + 1] * fr
            Tv /= np.linalg.norm(Tv, axis=1, keepdims=True)
            rel = q - (A[j] + self.D[j] * tj[:, None])
            Nv = np.stack([-Tv[:, 1], Tv[:, 0]], axis=1)
            along = np.einsum("ck,ck->c", rel, Tv)
            a = np.where((j == 0) & (tj <= 1e-9), np.minimum(along, 0.0),
                         np.where((j == M - 1) & (tj >= self.len[-1] - 1e-9), np.maximum(along, 0.0), 0.0))
            us.append((self.cum[j] + tj) / self.L)
            ns.append(np.einsum("ck,ck->c", rel, Nv))
            as_.append(a)
        return np.concatenate(us), np.concatenate(ns), np.concatenate(as_)

    def coords(self, p):
        fy = (p[:, 1] - self.lo[0]) / self.step
        fz = (p[:, 2] - self.lo[1]) / self.step
        iy = np.clip(np.floor(fy).astype(np.int64), 0, self.ny - 2)
        iz = np.clip(np.floor(fz).astype(np.int64), 0, self.nz - 2)
        wy = np.clip(fy - iy, 0.0, 1.0).astype(np.float32)
        wz = np.clip(fz - iz, 0.0, 1.0).astype(np.float32)

        def bil(tab):
            return ((tab[iy, iz] * (1 - wy) + tab[iy + 1, iz] * wy) * (1 - wz)
                    + (tab[iy, iz + 1] * (1 - wy) + tab[iy + 1, iz + 1] * wy) * wz)

        return bil(self.tu), p[:, 0], bil(self.tn), bil(self.ta)

    def frame(self, u):
        """Centro della sezione u, tangente (verso la coda) e normale 'su' (vettori 3D)."""
        s = float(np.clip(u, 0.0, 1.0)) * self.L
        i = int(np.clip(np.searchsorted(self.cum, s, side="right") - 1, 0, len(self.len) - 1))
        fr = (s - self.cum[i]) / self.len[i]
        c = self.P[i] + self.D[i] * (s - self.cum[i])
        T = self.T[i] * (1 - fr) + self.T[i + 1] * fr
        T /= np.linalg.norm(T)
        return np.array([0.0, c[0], c[1]]), np.array([0.0, T[0], T[1]]), np.array([0.0, -T[1], T[0]])


X = np.array([1.0, 0.0, 0.0])
L_BODY = 4.7
SNOUT = (-2.15, 3.09)                     # punta della spina (y, z): il muso
# pendenza (gradi, positiva = verso l'alto andando verso la testa): testa quasi in piano, corpo che sale ripido,
# coda che si rialza: una S dolce
ANG = table([0.0, 0.14, 0.32, 0.55, 0.75, 0.9, 1.0], [3, 18, 38, 40, 20, -8, -30])


def spine_points(n=400):
    pts = [np.array(SNOUT, dtype=np.float64)]
    for i in range(n):
        th = math.radians(float(ANG((i + 0.5) / n)))
        pts.append(pts[-1] + L_BODY / n * np.array([math.cos(th), -math.sin(th)]))
    return np.array(pts)


SP = Spine(spine_points())

# sezioni: semiasse laterale rx, sopra ru, sotto rd (testa grande da giocattolo, gola piena della megattera)
PU = [0.00, 0.05, 0.12, 0.22, 0.32, 0.44, 0.56, 0.68, 0.80, 0.90, 1.00]
RX = table(PU, [0.34, 0.52, 0.64, 0.72, 0.74, 0.69, 0.58, 0.44, 0.28, 0.18, 0.13])
RU = table(PU, [0.24, 0.39, 0.50, 0.58, 0.62, 0.62, 0.55, 0.44, 0.32, 0.22, 0.13])
RD = table(PU, [0.28, 0.45, 0.60, 0.70, 0.72, 0.64, 0.50, 0.37, 0.25, 0.16, 0.11])
CAP0, CAP1 = 0.3, 0.12


def trunk_fn(p):
    u, x, n, a = SP.coords(p)
    rx, ru, rd = RX(u), RU(u), RD(u)
    rz = np.where(n > 0, ru, rd)
    ra = np.where(a < 0, CAP0, CAP1)
    qx, qn, qa = x / rx, n / rz, a / ra
    k0 = np.sqrt(qx * qx + qn * qn + qa * qa)
    k1 = np.sqrt((qx / rx) ** 2 + (qn / rz) ** 2 + (qa / ra) ** 2)
    return (k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)).astype(np.float32)


_P = SP.P
TRUNK = SDF(trunk_fn, (-0.82, _P[:, 0].min() - 0.42, _P[:, 1].min() - 0.8), (0.82, _P[:, 0].max() + 0.3,
                                                                              _P[:, 1].max() + 0.75))


def surf(u, th, fwd=0.0, side=1, sdf=None, lift=0.0):
    """Punto della superficie: dal centro della sezione u verso l'angolo th (gradi: 0 = fianco, 90 = dorso,
    -90 = pancia) sul lato side, inclinato in avanti (verso il muso) di fwd. Ritorna (punto, normale)."""
    c, T, N = SP.frame(u)
    d = side * math.cos(math.radians(th)) * X + math.sin(math.radians(th)) * N - fwd * T
    p, n = project(sdf or TRUNK, c, d)
    return p + n * lift, n


def surf_d(u, dx, dn, dt, sdf=None, lift=0.0):
    """Come surf, ma con la direzione data nel riferimento della sezione (laterale, su, avanti)."""
    c, T, N = SP.frame(u)
    p, n = project(sdf or TRUNK, c, dx * X + dn * N - dt * T)
    return p + n * lift, n


def uth(p):
    """(u, angolo th in gradi, lato) di punti 3D (per disegnare sulla pelle)."""
    u, x, n, a = SP.coords(p)
    return u, np.degrees(np.arctan2(n, np.abs(x))), np.sign(x)


m = Model("CosmicWhale", "pet")

# ============================================================ testa: orbite in rilievo e guance del ghigno
EYE_U, EYE_TH, EYE_FWD = 0.14, 7.0, 1.15
EYE_R = np.array([0.22, 0.19, 0.12])

head_bits = []
for sx in (1, -1):
    pe, ne = surf(EYE_U, EYE_TH, EYE_FWD, side=sx)
    head_bits.append(ellipsoid((0.21, 0.21, 0.18)).translate(pe - ne * 0.1))      # orbita in rilievo
    pc, nc = surf(0.215, -22, 0.15, side=sx)
    head_bits.append(ellipsoid((0.17, 0.2, 0.15)).translate(pc - nc * 0.1))      # guancia del ghigno
CORE = union(TRUNK, *head_bits, k=0.15)

# ============================================================ pinna dorsale sulla gobba
DU = 0.665
dc, dT, dN = SP.frame(DU)
dp, dn_ = surf(DU, 90)
DORSAL_OUT = [(-0.36, -0.12), (-0.17, -0.02), (0.0, 0.09), (0.11, 0.19), (0.21, 0.28), (0.23, 0.22), (0.2, 0.13),
              (0.21, 0.04), (0.32, -0.12)]
dorsal = lamina(DORSAL_OUT, dp - dn_ * 0.02, dT, dN, t_edge=0.02, slope=0.5, t_max=0.08)
hump = ellipsoid((0.17, 0.38, 0.13)).translate(dp - dn_ * 0.06 - dT * 0.06)

# ============================================================ coda: pinne caudali larghe, alzate e girate di lato
TC, TT, TN = SP.frame(1.0)
FLICK, ROLL = 14.0, 24.0
F_DIR = rodrigues(TT, X, FLICK)                 # corda delle pinne caudali (indietro e in su)
F_LAT = rodrigues(X, F_DIR, ROLL)               # apertura (girata: la pinna destra piu' bassa)
F_ROOT = TC - TT * 0.16
FS = 1.12                                       # apertura delle pinne caudali


def fluke_outline():
    le = [(0.0, -0.1), (0.12, -0.08), (0.26, -0.02), (0.42, 0.07), (0.58, 0.18), (0.73, 0.31), (0.86, 0.45),
          (0.96, 0.6), (1.02, 0.76)]
    te = []
    for a in np.linspace(0.97, 0.02, 17):
        b = 0.62 + 0.13 * a ** 3 - 0.14 * math.exp(-(a / 0.12) ** 2)
        b += 0.024 * (0.5 + 0.5 * math.cos(2 * math.pi * (a - 0.97) / 0.0905))   # bordo seghettato
        te.append((a, b))
    right = [(a * FS, b * FS) for a, b in le + te]
    left = [(-a, b) for a, b in right[::-1]]
    return right + left[1:-1]


FLUKE_OUT = fluke_outline()
flukes = lamina(FLUKE_OUT, F_ROOT, F_LAT, F_DIR, t_edge=0.018, slope=0.32, t_max=0.09)


def fluke_pt(a, b):
    return F_ROOT + F_LAT * a + norm(F_DIR - F_LAT * (F_DIR @ F_LAT)) * b


BODY = union(CORE, hump, k=0.1)
BODY = union(BODY, dorsal, k=0.05)
BODY = union(BODY, flukes, k=0.1)

# ============================================================ bitorzoli (testa) e palpebre: parte "Knobs" (pelle, voxel fini)
knobs = []
for u, th, r in [(0.015, 90, 0.05), (0.05, 90, 0.055), (0.088, 90, 0.055), (0.125, 90, 0.05),
                 (0.025, 64, 0.045), (0.065, 66, 0.05), (0.104, 68, 0.046),
                 (0.04, 40, 0.04), (0.08, 44, 0.042)]:
    for sx in ((1, -1) if th != 90 else (1,)):
        p, n = surf(u, th, 0.0, side=sx, sdf=CORE)
        knobs.append(dome(r, p - n * r * 0.35, p - n * 0.015, n))


# ============================================================ occhi grandi e saggi (palpebra pesante, pupilla a stella)
def eye_kit(lid_cut, lid_slope, low_cut):
    """Occhio destro: sclera bianca, iride scura, pupilla a stella luminosa, riflessi, palpebre e sopracciglio."""
    pe, ne = surf(EYE_U, EYE_TH, EYE_FWD, side=1, sdf=CORE)
    c, T, N = SP.frame(EYE_U)
    M = basis(ne, N)                       # x verso la coda (angolo esterno), y su, z fuori
    C = pe - ne * 0.05
    front = local(lambda q: 0.02 - q[:, 2], M, C, (-0.3, -0.3, 0.0), (0.3, 0.3, 0.3))
    ball = ellipsoid(EYE_R).rotate(M).translate(C)
    sclera = ball.intersect(front)
    ox, oy = -0.035, -0.01                 # l'iride guarda un po' avanti

    def on_ball(lx, ly, lift=0.0):
        z = EYE_R[2] * math.sqrt(max(1 - (lx / EYE_R[0]) ** 2 - (ly / EYE_R[1]) ** 2, 0.0))
        return C + M @ np.array([lx, ly, z + lift], dtype=np.float32)

    iris_reg = local(lambda q: np.maximum(np.sqrt((q[:, 0] - ox) ** 2 + (q[:, 1] - oy) ** 2) - 0.13, 0.02 - q[:, 2]),
                     M, C, (-0.18, -0.18, 0.0), (0.12, 0.15, 0.16))
    iris = thin(ball, 0.007, 0.03).intersect(iris_reg)
    star2 = poly_d2(star_points(5, 0.085, 0.037, 90))
    star_reg = local(lambda q: np.maximum(star2(q[:, 0] - ox, q[:, 1] - oy), 0.04 - q[:, 2]), M, C,
                     (-0.13, -0.13, 0.0), (0.07, 0.09, 0.16))
    pupil = thin(ball, 0.014, 0.03).intersect(star_reg)
    shines = [sphere(0.032, tuple(on_ball(ox + 0.07, oy + 0.065, 0.004))),
              sphere(0.016, tuple(on_ball(ox - 0.06, oy - 0.055, 0.006)))]

    def cut_plane(cut, slope, above):
        sg = 1.0 if above else -1.0
        return local(lambda q: np.maximum(sg * (cut + slope * q[:, 0] - q[:, 1]) / math.sqrt(1 + slope * slope),
                                          0.015 - q[:, 2]), M, C, (-0.3, -0.3, 0.0), (0.3, 0.3, 0.3))

    upper = ellipsoid(tuple(EYE_R + 0.026)).rotate(M).translate(C).intersect(cut_plane(lid_cut, lid_slope, True), k=0.014)
    lower = ellipsoid(tuple(EYE_R + 0.02)).rotate(M).translate(C).intersect(cut_plane(low_cut, -0.12, False), k=0.014)
    brow_pts = [C + M @ np.array([0.23 * math.cos(a), 0.2 * math.sin(a) + 0.04, 0.03], dtype=np.float32)
                for a in np.radians([155, 125, 95, 65, 35])]
    brow = tube([tuple(q) for q in brow_pts], [0.03, 0.046, 0.054, 0.048, 0.032])
    return dict(sclera=sclera, iris=iris, pupil=pupil, shines=shines, lids=[upper, lower, brow])


EYE_R_KIT = eye_kit(0.068, -0.14, -0.125)     # occhio destro
EYE_L_KIT = eye_kit(0.052, -0.2, -0.13)       # occhio sinistro (palpebra un filo piu' bassa: sguardo sornione)


def both(kit_r, kit_l, key):
    a, b = kit_r[key], kit_l[key]
    if isinstance(a, list):
        return a + [s.mirrored() for s in b]
    return [a, b.mirrored()]


# ============================================================ bocca: ghigno furbo e storto con dentini aguzzi a incastro
def mouth_rad(t):
    return 0.056 + 0.012 * math.sin(math.pi * min(t / 0.7, 1.0)) - 0.03 * max(t - 0.7, 0.0) / 0.3


MOUTH_PATH = [(0.0, -40, 0.9), (0.035, -27, 0.45), (0.085, -23, 0.12), (0.13, -20, 0.0), (0.17, -17, 0.0),
              (0.205, -8, 0.0), (0.225, 3, 0.0), (0.234, 12, -0.05)]   # (u, th, avanti): sotto l'occhio, poi su


def mouth_kit(lift):
    """Meta' destra del ghigno, dal centro del muso all'angolo (lift = gradi in piu' per l'angolo della bocca):
    fascia scura della bocca e denti alternati sopra e sotto."""
    pts = [surf_d(0.0, 0.0, -0.62, 1.0, sdf=CORE)[0]]
    for k, (u, th, fwd) in enumerate(MOUTH_PATH):
        extra = lift * max(0, k - (len(MOUTH_PATH) - 4)) / 3
        pts.append(surf(u, th + extra, fwd, side=1, sdf=CORE)[0])
    line = resample(catmull(pts, 6), 0.018)
    n_ = len(line)
    reg = piping(line, [mouth_rad(i / (n_ - 1)) for i in range(n_)], step=0.02)
    teeth = []
    for j, s_ in enumerate(np.arange(0.02, 0.86, 0.047)):
        i = int(s_ * (n_ - 1))
        q = line[i]
        tng = norm(line[min(i + 1, n_ - 1)] - line[max(i - 1, 0)])
        nrm = grad(CORE, q)
        up = norm(np.cross(tng, nrm))
        if up[2] < 0:
            up = -up
        w = mouth_rad(s_)
        sg = 1.0 if j % 2 == 0 else -1.0            # alternati sopra e sotto: denti a incastro
        L_t = 1.55 * w * (1 - 0.25 * s_)
        base = q + up * sg * w * 0.92 - nrm * 0.008
        tip = base - up * sg * L_t + nrm * 0.018
        teeth.append(round_cone(tuple(base), tuple(tip), 0.035 * (1 - 0.25 * s_), 0.005))
    return reg, teeth


MOUTH_REG_R, TEETH_R = mouth_kit(0.0)           # lato destro
MOUTH_REG_L, TEETH_L = mouth_kit(9.0)           # lato sinistro: angolo piu' alto, ghigno storto da furbetto
mouth = skin_paint(CORE, union(MOUTH_REG_R, MOUTH_REG_L.mirrored()), out=0.014, inn=0.05)
teeth = TEETH_R + [t.mirrored() for t in TEETH_L]

# sfiatatoio doppio sulla testa (fessure scure)
blow = []
for sx in (1, -1):
    p, n = surf(0.2, 80, 0.0, side=sx, sdf=CORE)
    c, T, N = SP.frame(0.2)
    blow.append(capsule(tuple(p - T * 0.06 - n * 0.01), tuple(p + T * 0.05 + X * sx * 0.03 - n * 0.01), 0.024))


# ============================================================ pennellate di colore: fianchi viola, pancia lavanda a pieghe
def belly_edge(u):
    return np.interp(u, [0.0, 0.25, 0.45, 0.58, 0.67, 0.75], [-40, -40, -42, -54, -72, -95])


PLEAT_STEP = 11.0
PLEAT_END = 0.47


def belly_region_fn(p):
    u, x, n, a = SP.coords(p)
    th = np.degrees(np.arctan2(n, np.abs(x)))
    r = 0.5 * (RX(u) + RD(u))
    d = np.radians(th - belly_edge(u)) * r
    d = np.maximum(d, (u - 0.75) * L_BODY)
    d = np.maximum(d, n + np.interp(u, [0.0, 0.12, 0.22], [0.25, 0.16, 0.0]))   # mento: bordo a U sotto la bocca
    k = np.round((th + 90.0) / PLEAT_STEP - 0.5) + 0.5
    dg = 0.018 - np.abs(np.radians(th - (-90.0 + k * PLEAT_STEP))) * r
    dg = np.minimum(dg, (PLEAT_END - u) * L_BODY)
    dg = np.minimum(dg, (u - 0.03) * L_BODY)
    return np.maximum(d, dg).astype(np.float32)


belly = skin_paint(CORE, SDF(belly_region_fn, TRUNK.lo, TRUNK.hi), out=0.022, inn=0.06)


def flank_top(u):
    return -4.0 + 11.0 * np.sin(2 * np.pi * u * 2.3 + 1.6)


def flank_region_fn(p):
    u, th, sd = uth(p)
    r = 0.5 * (RX(u) + RU(u))
    d_top = np.radians(th - flank_top(u)) * r
    d_low = np.radians(belly_edge(u) - th) * r
    front = 0.29 - 0.08 * np.clip((th + 40.0) / 40.0, 0, 1)      # bordo anteriore obliquo, dietro l'occhio
    d_front = (front - u) * L_BODY
    return np.maximum(np.maximum(d_top, d_low), d_front).astype(np.float32)


flank = skin_paint(CORE, SDF(flank_region_fn, TRUNK.lo, TRUNK.hi), out=0.016, inn=0.06)


# ------------------------------------------------------------ vortici di nebulosa (magenta e ciano) sui fianchi
def band2d(pts, hw):
    """Distanza 2D (s, w) da una polilinea con mezza larghezza variabile."""
    P = np.asarray(pts, dtype=np.float32)
    H = np.asarray(hw, dtype=np.float32)

    def f(s, w):
        d = np.full(s.shape, 1e3, dtype=np.float32)
        for i in range(len(P) - 1):
            a, b = P[i], P[i + 1]
            e = b - a
            l2 = float(e @ e) + 1e-12
            t = np.clip(((s - a[0]) * e[0] + (w - a[1]) * e[1]) / l2, 0.0, 1.0)
            dx, dy = s - a[0] - e[0] * t, w - a[1] - e[1] * t
            d = np.minimum(d, np.sqrt(dx * dx + dy * dy) - (H[i] + (H[i + 1] - H[i]) * t))
        return d

    return f


def swirl(s0, w0, s1, w1, curl_r, turns, hw0, spin, n=18, wave=0.07, phase=0.0):
    """Pennellata che scorre da (s0, w0) a (s1, w1) e finisce arricciata a spirale (raggio curl_r, verso spin)."""
    pts, hws = [], []
    for i in range(n):
        t = i / (n - 1)
        pts.append((s0 + (s1 - s0) * t, w0 + (w1 - w0) * t + wave * math.sin(math.pi * t * 1.6 + phase)))
        hws.append(hw0 * (0.55 + 0.45 * math.sin(math.pi * min(t * 1.6, 1.0) * 0.5)))
    d = np.array(pts[-1]) - np.array(pts[-2])
    d /= np.linalg.norm(d)
    cen = np.array(pts[-1]) + np.array([-d[1], d[0]]) * spin * curl_r
    a0 = math.atan2(pts[-1][1] - cen[1], pts[-1][0] - cen[0])
    m_ = 30
    for i in range(1, m_ + 1):
        t = i / m_
        a = a0 + spin * 2 * math.pi * turns * t
        rr = curl_r * (1 - 0.75 * t)
        pts.append((cen[0] + rr * math.cos(a), cen[1] + rr * math.sin(a)))
        hws.append(hw0 * (1 - 0.6 * t) + 0.01)
    return pts, hws


def side_paint(bands, side):
    fs = [band2d(p, h) for p, h in bands]

    def f(p):
        u, th, sd = uth(p)
        s = u * L_BODY
        w = np.radians(th) * RX(u)
        d = np.full(len(p), 1e3, dtype=np.float32)
        for g in fs:
            d = np.minimum(d, g(s, w))
        return np.where(sd * side > 0, d, 1.0).astype(np.float32)

    lo, hi = TRUNK.lo.copy(), TRUNK.hi.copy()
    if side > 0:
        lo[0] = -0.02
    else:
        hi[0] = 0.02
    return SDF(f, lo, hi)


PINK_R = [swirl(1.05, 0.5, 2.05, 0.3, 0.24, 1.15, 0.09, -1, phase=0.3),
          swirl(2.55, 0.62, 3.25, 0.32, 0.17, 1.1, 0.07, 1, wave=0.05),
          swirl(3.45, 0.05, 3.95, 0.12, 0.1, 1.0, 0.045, -1, wave=0.03)]
CYAN_R = [swirl(1.45, 0.07, 2.5, -0.04, 0.19, 1.1, 0.075, 1, phase=1.0),
          swirl(2.4, 0.95, 3.15, 0.8, 0.13, 1.0, 0.05, -1, wave=0.04)]
PINK_L = [swirl(1.15, 0.3, 2.2, 0.08, 0.22, 1.15, 0.085, 1, phase=0.8),
          swirl(2.75, 0.7, 3.45, 0.42, 0.15, 1.1, 0.065, -1, wave=0.05)]
CYAN_L = [swirl(1.0, 0.85, 1.95, 0.65, 0.18, 1.1, 0.07, -1, phase=0.2),
          swirl(2.3, -0.12, 3.15, 0.05, 0.19, 1.1, 0.07, 1),
          swirl(3.4, 0.25, 3.95, 0.2, 0.1, 1.0, 0.045, 1, wave=0.03)]
swirl_pink = skin_paint(CORE, union(side_paint(PINK_R, 1), side_paint(PINK_L, -1)), out=0.026, inn=0.06)
swirl_cyan = skin_paint(CORE, union(side_paint(CYAN_R, 1), side_paint(CYAN_L, -1)), out=0.026, inn=0.06)

# ============================================================ pinne pettorali lunghissime (gruppi FinR / FinL)
FIN_L = 2.0
FIN_U, FIN_TH = 0.3, -34.0


def fin_profile(n=64):
    ts = np.linspace(0.0, 1.0, n)
    sweep = 0.26 * ts ** 1.7
    chord = 0.5 * np.sqrt(np.maximum(1 - ts ** 2.6, 0.0)) * (0.78 + 0.22 * np.exp(-((ts - 0.3) / 0.25) ** 2))
    return ts, sweep - 0.36 * chord, sweep + 0.64 * chord, sweep


def fin_outline():
    ts, v_le, v_te, sweep = fin_profile()
    knobs_t = np.linspace(0.11, 0.88, 10)
    knob_r = 0.055 * (1 - 0.45 * (knobs_t - 0.11) / 0.77)
    le = []
    for t, v in zip(ts, v_le):
        bump = np.sqrt(np.maximum(knob_r ** 2 - ((t - knobs_t) * FIN_L) ** 2, 0.0)).max()
        le.append((t * FIN_L, float(v - bump * 0.85)))
    le[-1] = (FIN_L, float(sweep[-1] + 0.06))
    te = [(t * FIN_L, float(v)) for t, v in zip(ts[::-1][1:-1], v_te[::-1][1:-1])]
    return [(-0.12, float(v_le[0])), *le, *te, (-0.12, float(v_te[0]))]


FIN_OUT = fin_outline()
f_c, f_T, f_N = SP.frame(FIN_U)
FIN_ROOT, FIN_NRM = surf(FIN_U, FIN_TH, 0.0, side=1, sdf=CORE)
FIN_SPAN = norm(0.9 * X + 0.3 * f_T + 0.04 * f_N)     # aperte quasi in orizzontale, come ali
FIN_V = norm(f_T - FIN_SPAN * (f_T @ FIN_SPAN))
FIN_N = np.cross(FIN_SPAN, FIN_V)
FIN_ORIGIN = FIN_ROOT - FIN_NRM * 0.1
FIN_DROOP, FIN_TWIST = 0.2, 14.0


def fin_warp(q):
    t = np.clip(q[:, 0] / FIN_L, 0.0, 1.0)
    q = q.copy()
    q[:, 2] = q[:, 2] + FIN_DROOP * t ** 2       # la punta scende
    a = np.radians(FIN_TWIST) * t                # leggera torsione
    v, w = q[:, 1].copy(), q[:, 2].copy()
    q[:, 1] = v * np.cos(a) - w * np.sin(a)
    q[:, 2] = v * np.sin(a) + w * np.cos(a)
    return q


def fin_world(u, v, off=0.0):
    """Punto 3D della superficie media della pinna destra (coordinate piatte u, v)."""
    t = min(max(u / FIN_L, 0.0), 1.0)
    a = math.radians(FIN_TWIST) * t
    q = (u, v * math.cos(a) - off * math.sin(a), -v * math.sin(a) + off * math.cos(a) - FIN_DROOP * t * t)
    return FIN_ORIGIN + FIN_SPAN * q[0] + FIN_V * q[1] + FIN_N * q[2]


fin_r = lamina(FIN_OUT, FIN_ORIGIN, FIN_SPAN, FIN_V, t_edge=0.022, slope=0.36, t_max=0.09, warp=fin_warp, pad=0.3)
# contorno luminoso: tubicino lungo tutto il bordo (tranne la radice dentro il corpo)
_ts, _le, _te, _sw = fin_profile()
rim_pts = [fin_world(u, v + 0.01) for u, v in FIN_OUT[1:len(_ts) + 1] if u > 0.2]
rim_pts += [fin_world(u, v - 0.01) for u, v in FIN_OUT[len(_ts) + 1:-1] if u > 0.2]
fin_rim_r = piping(rim_pts, 0.024, step=0.025)
FIN_PIVOT = tuple(float(c) for c in FIN_ROOT)

# ============================================================ stelle: lentiggini luminose su dorso e fianchi
rng = np.random.default_rng(7)
KEY_U = 0.4
avoid = [(np.asarray(surf(EYE_U, EYE_TH, EYE_FWD, side=s, sdf=CORE)[0]), 0.36) for s in (1, -1)]
avoid += [(np.asarray(surf(KEY_U, 90, sdf=CORE)[0]), 0.28), (np.asarray(dp), 0.38),
          (np.asarray(surf(0.2, 80, sdf=CORE)[0]), 0.16), (np.asarray(surf(0.2, 80, side=-1, sdf=CORE)[0]), 0.16)]
stars = []
placed = []
for _ in range(3000):
    u = rng.uniform(0.03, 0.9)
    th = rng.uniform(-22.0, 90.0)
    side = 1 if rng.random() < 0.5 else -1
    if u < 0.27 and th < -2:                     # niente stelle sulla bocca
        continue
    s, w = u * L_BODY, math.radians(th) * float(RX(u)) * side
    if any(math.hypot(s - s2, w - w2) < 0.21 for s2, w2, _ in placed):
        continue
    p, n = surf(u, th, 0.0, side=side, sdf=CORE)
    if any(np.linalg.norm(p - a) < r for a, r in avoid):
        continue
    placed.append((s, w, (p, n)))
for s, w, (p, n) in placed:
    roll = rng.uniform(0, 90)
    k = rng.random()
    up = rodrigues(np.array([0.0, 0.0, 1.0]) - n * n[2], n, roll)
    if k < 0.24:
        r_out = rng.uniform(0.078, 0.096)
    elif k < 0.46:
        r_out = rng.uniform(0.058, 0.066)
    else:
        stars.append(dome(rng.uniform(0.026, 0.032), p + n * 0.006, p - n * 0.012, n))
        continue
    stars.append(lamina(star_points(4, r_out, r_out * 0.42, 90), p + n * 0.016, np.cross(up, n), up, t_edge=0.013,
                        slope=0.5, t_max=0.028, r=0.004))

# ============================================================ cucitura sul fianco destro con imbottitura di stelle
SEAM = [surf(u, th, 0.0, side=1, sdf=CORE)[0] for u, th in ((0.4, -31), (0.46, -34), (0.52, -38), (0.58, -43),
                                                               (0.64, -49))]
SEAM_LINE = resample(catmull(SEAM, 6), 0.012)
TEAR = (0.34, 0.66)          # tratto aperto (frazione della cucitura)
nS = len(SEAM_LINE)
stitches, seam_dark, stuffing = [], [], []
for i in range(0, nS - 1, 6):
    t = i / (nS - 1)
    if TEAR[0] - 0.03 < t < TEAR[1] + 0.03:
        continue
    q = SEAM_LINE[i]
    tng = norm(SEAM_LINE[i + 1] - SEAM_LINE[i])
    nrm = grad(CORE, q)
    side_v = norm(np.cross(nrm, tng))
    a = on_surface(CORE, q - side_v * 0.065, 0.018)
    b = on_surface(CORE, q + side_v * 0.065, 0.018)
    stitches.append(capsule(tuple(a), tuple(b), 0.017))
seam_dark.append(piping([on_surface(CORE, q, 0.006) for q in SEAM_LINE[::4]], 0.016, step=0.02))
i0, i1 = int(TEAR[0] * (nS - 1)), int(TEAR[1] * (nS - 1))
mid = SEAM_LINE[(i0 + i1) // 2]
mid_n = grad(CORE, mid)
tear_tng = norm(SEAM_LINE[i1] - SEAM_LINE[i0])
for t in np.linspace(0.0, 1.0, 13):           # squarcio: fessura scura a mandorla
    q = SEAM_LINE[int(i0 + (i1 - i0) * t)]
    w = 0.075 * math.sin(math.pi * t) + 0.016
    seam_dark.append(sphere(w, tuple(q - grad(CORE, q) * (w * 0.5))))
for t_, sd in ((0.06, 1), (0.94, -1)):        # due punti strappati che penzolano dai bordi dello squarcio
    q = SEAM_LINE[int(i0 + (i1 - i0) * t_)]
    nrm = grad(CORE, q)
    sv = norm(np.cross(nrm, tear_tng))
    a = on_surface(CORE, q + sv * 0.06, 0.016)
    stitches.append(piping([a, a + sv * 0.02 + nrm * 0.05 - tear_tng * sd * 0.03,
                            a + nrm * 0.07 - tear_tng * sd * 0.05 + np.array([0.0, 0.0, -0.1])], 0.014, step=0.012))
# l'imbottitura di polvere di stelle che sbuffa fuori dallo squarcio e cade verso la nebulosa
for off, up_, r in [(0.0, 0.0, 0.075), (0.09, 0.01, 0.06), (-0.09, -0.01, 0.058), (0.045, 0.05, 0.05),
                    (-0.05, 0.045, 0.048), (0.03, -0.05, 0.046), (-0.03, -0.055, 0.044)]:
    sv = norm(np.cross(mid_n, tear_tng))
    c = mid + tear_tng * off + sv * up_ + mid_n * (0.03 + 0.035 * (r > 0.07))
    stuffing.append(sphere(r, tuple(c)))
down = norm(np.array([0.0, 0.0, -1.0]) + mid_n * 0.5)
for j, (dist, r) in enumerate([(0.2, 0.04), (0.33, 0.034), (0.46, 0.029), (0.59, 0.025), (0.72, 0.022)]):
    c = mid + mid_n * 0.09 + down * dist + tear_tng * 0.06 * math.sin(j * 1.7)
    stuffing.append(sphere(r, tuple(c)))
for off, up_, r_out in ((0.13, 0.06, 0.06), (-0.12, -0.07, 0.055), (0.02, -0.16, 0.05)):   # stelline nell'imbottitura
    sv = norm(np.cross(mid_n, tear_tng))
    c = mid + tear_tng * off + sv * up_ + mid_n * 0.06
    stuffing.append(lamina(star_points(4, r_out, r_out * 0.42, 90), c, tear_tng, sv, t_edge=0.014, slope=0.5,
                           t_max=0.028, r=0.004))

# ============================================================ chiave di carica d'ottone nella schiena
KEY_P, KEY_N = surf(KEY_U, 90, sdf=CORE)
KEY_AX = norm(KEY_N * 0.85 + SP.frame(KEY_U)[1] * 0.15)
KEY_B = norm(np.cross(KEY_AX, norm((0.62, -0.78, 0.0))))   # piano dell'impugnatura rivolto verso la vista 3/4
KEY_M = np.stack([KEY_B, KEY_AX, np.cross(KEY_B, KEY_AX)], axis=1).astype(np.float32)
KS = 1.25


def key_fn(q):
    q = q / KS
    bx, by, bz = q[:, 0], q[:, 1], q[:, 2]
    rho = np.sqrt(bx * bx + bz * bz)
    collar = np.maximum(rho - 0.12, np.abs(by) - 0.035)
    shaft = np.maximum(rho - 0.045, np.abs(by - 0.17) - 0.17)
    bead = np.sqrt((rho - 0.05) ** 2 + (by - 0.17) ** 2) - 0.03
    c1 = np.sqrt((bx - 0.18) ** 2 + (by - 0.5) ** 2) - 0.16
    c2 = np.sqrt((bx + 0.18) ** 2 + (by - 0.5) ** 2) - 0.16
    c3 = np.sqrt(bx ** 2 + (by - 0.35) ** 2) - 0.075
    d2 = smin(smin(c1, c2, 0.06), c3, 0.06)
    holes = np.minimum(np.sqrt((bx - 0.19) ** 2 + (by - 0.51) ** 2) - 0.06,
                       np.sqrt((bx + 0.19) ** 2 + (by - 0.51) ** 2) - 0.06)
    d2 = np.maximum(d2, -holes)
    rr = 0.02
    a, b = d2 + rr, np.abs(bz) - 0.045 + rr
    bow = np.minimum(np.maximum(a, b), 0.0) + np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2) - rr
    return (np.minimum(np.minimum(smin(collar, shaft, 0.02), bead), bow) * KS).astype(np.float32)


key = local(key_fn, KEY_M, KEY_P - KEY_N * 0.03, (-0.5, -0.1, -0.2), (0.5, 0.9, 0.2))

# ============================================================ vortice di nebulosa (appoggiato a terra): sbuffi a spirale
# sbuffi lavanda in tre bracci a spirale; fra uno sbuffo e l'altro spuntano sbuffi luminosi rosa (parte "Nebula")
CLOUD_C = np.array([0.0, 0.05, 0.0])
puffs = [ellipsoid((0.46, 0.46, 0.38), tuple(CLOUD_C + (0.0, 0.0, 0.3))),
         ellipsoid((0.3, 0.3, 0.25), tuple(CLOUD_C + (0.1, -0.1, 0.58)))]
glow = [ellipsoid((0.2, 0.2, 0.17), tuple(CLOUD_C + (-0.2, 0.16, 0.6)))]
for arm in range(3):
    for i in range(6):
        t = i / 5
        ang = arm * 2 * math.pi / 3 + 0.6 + t * 1.15 * math.pi
        rr = 0.44 + 0.7 * t
        pr = 0.3 * (1 - 0.5 * t)
        c = CLOUD_C + np.array([rr * math.cos(ang), rr * math.sin(ang), pr * 0.72])
        puffs.append(ellipsoid((pr * 1.12, pr * 1.12, pr * 0.92), tuple(c)))
        if i in (1, 4):                             # luce di nebulosa che filtra fra gli sbuffi
            a2 = ang + 0.42 / (0.6 + t)
            r2 = rr + 0.02
            gp = pr * (0.62 if i < 4 else 0.72)
            glow.append(ellipsoid((gp, gp, gp * 0.85), tuple(CLOUD_C + np.array([r2 * math.cos(a2), r2 * math.sin(a2),
                                                                                   pr * 0.95]))))

GROUND = SDF(lambda p: -p[:, 2], (-20, -20, 0), (20, 20, 20))
cloud = fast_union(puffs, k=0.1).intersect(GROUND)

# scia di cometa: un ventaglio di strisce luminose che si staccano dal bordo delle pinne caudali, scorrono
# all'indietro assottigliandosi fino a una punta sottile; quella centrale si arriccia come la cresta di un'onda
BACK = norm(np.array([0.0, 0.7, -0.71]))       # verso dove resta la scia (la balena sale in avanti)
F_CHORD = norm(F_DIR - F_LAT * (F_DIR @ F_LAT))


def te_point(a):
    """Punto sul bordo d'uscita delle pinne caudali (coordinata laterale a, prima dell'apertura FS)."""
    b = 0.62 + 0.13 * abs(a) ** 3 - 0.14 * math.exp(-(a / 0.12) ** 2)
    return fluke_pt(a * FS, b * FS - 0.03)


comet = []
for a, L, r0 in ((-0.86, 0.7, 0.038), (-0.44, 1.0, 0.048), (0.0, 1.35, 0.06), (0.44, 1.0, 0.048), (0.86, 0.7, 0.038)):
    st = te_point(a)
    lat = np.array([-st[0] * 0.45, 0.0, 0.0])        # le strisce convergono un po' verso il centro
    ctrl = [st, st + F_CHORD * 0.1 * L + BACK * 0.08 * L, st + F_CHORD * 0.1 * L + BACK * 0.42 * L + lat * 0.5,
            st + BACK * 0.8 * L + lat + np.array([0.0, 0.0, 0.05 * math.sin(a * 3)])]
    if a == 0.0:                                      # la striscia centrale finisce arricciata all'insu'
        end = ctrl[-1]
        tng = norm(ctrl[-1] - ctrl[-2])
        upv = norm(np.array([0.0, -tng[2], tng[1]]))
        cen = end + upv * 0.2
        rel = end - cen
        a0 = math.atan2(rel @ upv, rel @ tng)
        for i in range(1, 13):
            t = i / 12
            ang = a0 + 2 * math.pi * 0.95 * t
            rr = 0.2 * (1 - 0.6 * t)
            ctrl.append(cen + (tng * math.cos(ang) + upv * math.sin(ang)) * rr)
    curve = catmull(ctrl, 6)
    n_ = len(curve)
    comet.append(piping(curve, [r0 * (1 - 0.82 * (i / (n_ - 1)) ** 0.9) for i in range(n_)], step=0.022))
trail_stars = []
for q, r_out in ((te_point(0.0) + F_CHORD * 0.5 + BACK * 0.75 + np.array([0.32, 0.0, 0.2]), 0.08),
                 (te_point(0.6) + F_CHORD * 0.2 + BACK * 0.65 + np.array([0.25, 0.0, -0.08]), 0.06),
                 (te_point(-0.6) + F_CHORD * 0.25 + BACK * 0.7 + np.array([-0.25, 0.0, 0.1]), 0.065),
                 (te_point(0.95) + F_CHORD * 0.12 + np.array([0.12, 0.05, 0.12]), 0.055)):
    up = norm(rng.normal(size=3))
    nn = norm(np.cross(up, X))
    trail_stars.append(lamina(star_points(4, r_out, r_out * 0.42, 90), q, np.cross(up, nn), up, t_edge=0.016,
                              slope=0.5, t_max=0.032, r=0.004))

# ============================================================ pianeta con l'anello e due lune
PLANET_C = np.array([0.72, 1.2, 2.72])
planet = sphere(0.3, tuple(PLANET_C))
RING_M = euler(24, -18, 0)


def ring_fn(q):
    rho = np.sqrt(q[:, 0] ** 2 + q[:, 1] ** 2)
    a, b = np.abs(rho - 0.57) - 0.09 + 0.014, np.abs(q[:, 2]) - 0.03 + 0.014
    return np.minimum(np.maximum(a, b), 0.0) + np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2) - 0.014


ring = local(ring_fn, RING_M, PLANET_C, (-0.7, -0.7, -0.05), (0.7, 0.7, 0.05))
band_reg = local(lambda q: np.abs(q[:, 2] - 0.14) - 0.045, RING_M, PLANET_C, (-0.35, -0.35, -0.35),
                 (0.35, 0.35, 0.35))
planet_bands = thin(planet, 0.012, 0.03).intersect(band_reg)
MOON1 = PLANET_C + np.array([-0.62, 0.1, 0.42])
MOON2 = np.array([1.1, -2.2, 3.2])
moons = union(sphere(0.1, tuple(MOON1)), sphere(0.075, tuple(MOON2)))
craters = [sphere(0.032, tuple(MOON1 + norm((0.4, -0.7, 0.5)) * 0.105)),
           sphere(0.024, tuple(MOON1 + norm((0.8, -0.4, -0.2)) * 0.105)),
           sphere(0.026, tuple(MOON2 + norm((0.3, -0.9, 0.3)) * 0.08))]
moons = moons.subtract(union(*craters), k=0.01)

# ============================================================ parti
# voxel scelti in base all'area di ogni parte: le facce del marching cubes (~3.1 * area / voxel^2) restano entro
# 8 volte i triangoli finali, cosi' il builder non ingrossa i voxel (dettagli fini e gusci di vernice integri)
m.add("Body", BODY, NAVY, tris=9700, voxel=0.029)
m.add("Knobs", fast_union(knobs + both(EYE_R_KIT, EYE_L_KIT, "lids")), NAVY, role="skin", tris=2100, voxel=0.014)
m.add("Flank", flank, VIOLET, role="detail", tris=4100, voxel=0.026)
m.add("Belly", belly, LAVENDER, role="detail", tris=5900, voxel=0.023)
m.add("SwirlPink", swirl_pink, MAGENTA, role="detail", tris=3300, voxel=0.0205)
m.add("SwirlCyan", swirl_cyan, CYAN, role="detail", tris=2900, voxel=0.0205)
m.add("Stars", fast_union(stars + stuffing + trail_stars), STAR, material="Neon", role="glow", tris=4500, voxel=0.0125)
m.add("Eyes", union(*both(EYE_R_KIT, EYE_L_KIT, "iris")), EYE_DARK, role="eye", tris=1000, voxel=0.011)
m.add("EyeGlow", union(*both(EYE_R_KIT, EYE_L_KIT, "pupil")), EYE_STAR, material="Neon", role="glow", tris=800,
      voxel=0.0085)
m.add("Shine", union(*both(EYE_R_KIT, EYE_L_KIT, "sclera"), *both(EYE_R_KIT, EYE_L_KIT, "shines")), WHITE, role="shine",
      tris=1300, voxel=0.014)
m.add("Mouth", fast_union([mouth, *blow, *seam_dark]), MOUTH, role="eye", tris=2300, voxel=0.016)
m.add("Teeth", fast_union(teeth), TOOTH, role="shine", tris=1800, voxel=0.0115)
m.add("Stitches", fast_union(stitches), THREAD, role="detail", tris=800, voxel=0.011)
FIN_PIVOT_L = (-FIN_PIVOT[0], FIN_PIVOT[1], FIN_PIVOT[2])
m.add("FinR", fin_r, FIN, role="detail", tris=2300, voxel=0.019, group="FinR", pivot=FIN_PIVOT)
m.add("FinL", fin_r.mirrored(), FIN, role="detail", tris=2300, voxel=0.019, group="FinL", pivot=FIN_PIVOT_L)
m.add("FinGlowR", fin_rim_r, RIM, material="Neon", role="glow", tris=1150, voxel=0.015, group="FinR", pivot=FIN_PIVOT)
m.add("FinGlowL", fin_rim_r.mirrored(), RIM, material="Neon", role="glow", tris=1150, voxel=0.015, group="FinL",
      pivot=FIN_PIVOT_L)
fl_rim = [fluke_pt(a, b + 0.012) for a, b in FLUKE_OUT[1:9]]
fl_rim += [fluke_pt(a, b - 0.012) for a, b in FLUKE_OUT[9:-8]]
fl_rim += [fluke_pt(a, b + 0.012) for a, b in FLUKE_OUT[-8:]]
m.add("TailGlow", piping(fl_rim, 0.022, step=0.025), RIM, material="Neon", role="glow", tris=1350, voxel=0.016)
m.add("Nebula", fast_union(comet + glow), NEBULA, material="Neon", role="glow", tris=3000, voxel=0.0235)
m.add("Cloud", cloud, CLOUD, role="detail", tris=3200, voxel=0.034)
m.add("Gold", union(key, ring), BRASS, material="Metal", role="detail", tris=2400, voxel=0.022, reflectance=0.1)
m.add("Planet", planet, PLANET, role="detail", tris=700, voxel=0.027)
m.add("Moons", union(moons, planet_bands), MOON, role="detail", tris=900, voxel=0.0175)

# ============================================================ scala globale: altezza ~4 unita' come gli altri Ultra
SCALE = 1.14
for part in m.parts:
    part.sdf = part.sdf.scale(SCALE)
    part.voxel = part.voxel * SCALE if part.voxel else None
    if part.pivot is not None:
        part.pivot = tuple(float(c * SCALE) for c in part.pivot)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
