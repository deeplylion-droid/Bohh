"""Grifone del Tuono (ThunderGriffin) - pet ULTRA, il livello piu' alto: in gioco e' esposto gigante
(circa 38 stud) su una torre dietro la base del giocatore.

Carattere: il sovrano della tempesta, fiero e minaccioso. Testa d'aquila bianca con il grande becco
d'oro adunco spalancato in uno strido (bordo seghettato di dentini aguzzi: il tocco "toy horror"),
occhi socchiusi che brillano sotto sopracciglia piumate a punta, una cicatrice ricucita sull'occhio.
Petto in fuori coperto di piume a scaglie, un artiglio d'oro alzato, corpo da leone grigio argento con
cosce muscolose e zampe con gli unghioli fuori. Attorno a collo e testa una enorme CRINIERA DI FULMINI
(parte Neon "Mane": il gioco ci aggancia le scintille), fulmini anche sul ciuffo della coda e sui bordi
delle grandi ali alzate (gruppi WingR/WingL, perno alla spalla), con qualche penna strappata.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, capsule, ellipsoid, project, round_cone, smin, sphere, tube,  # noqa: E402
                     union)
from lib.toy import Model  # noqa: E402

# ============================================================ colori
SILVER = (172, 182, 202)       # corpo da leone grigio tempesta
STORM = (238, 242, 250)        # piume bianco tempesta
STEEL = (96, 126, 172)         # copritrici blu acciaio
SLATE = (44, 54, 82)           # ardesia scura: sopracciglia, zampe d'aquila, strisce
REMIGE = (52, 64, 98)          # penne remiganti ardesia
GOLD = (255, 184, 36)
MOUTH = (64, 16, 40)
TOOTH = (255, 252, 240)
PUPIL = (14, 16, 34)
WHITE = (255, 255, 255)
BOLT = (70, 222, 255)          # fulmini ciano elettrico
BOLT_HOT = (255, 244, 168)     # fulmini bianco-giallo
EYE_GLOW = (150, 246, 255)
THREAD = (72, 40, 112)


# ============================================================ helper (lib/ non si modifica: definiti qui)
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
    return [tuple(float(x) for x in q) for q in out]


def paint(base, region, d=0.022, depth=0.05, k=0.012):
    """Vernice a strato sottile (fra -depth e +d dalla superficie) ritagliata dalla regione."""
    t = (d + depth) / 2
    return base.offset(d - t).shell(t).intersect(region, k=k)


def halfspace(c, n):
    """Semispazio dietro il piano per c con normale n (dentro dove (p - c).n < 0)."""
    c = np.asarray(c, dtype=np.float32)
    n = norm(n).astype(np.float32)
    return SDF(lambda p: (p - c) @ n, c - 50, c + 50)


def bounded(sdf, lo, hi):
    """Stessa forma con un box di ingombro piu' stretto (i box delle forme ruotate sono molto larghi)."""
    return SDF(sdf.f, lo, hi)


def frame_from_z(d, hint=(1.0, 0.0, 0.0)):
    z = norm(d)
    x = np.asarray(hint, dtype=np.float64)
    x = x - z * (x @ z)
    if np.linalg.norm(x) < 1e-6:
        x = np.array([0.0, 1.0, 0.0]) - z * z[1]
    x = norm(x)
    return np.stack([x, np.cross(z, x), z], axis=1).astype(np.float32)


def muscle(a, b, rx, ry, hint=(1.0, 0.0, 0.0)):
    """Ellissoide (massa muscolare) con l'asse lungo da a a b."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    half = float(np.linalg.norm(b - a)) / 2
    return ellipsoid((rx, ry, half)).rotate(frame_from_z(b - a, hint)).translate(tuple((a + b) / 2))


# ------------------------------------------------------------ forme piatte "a lama" (fulmini, penne, becco)
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


def blade(outline, origin, u_dir, v_dir, t_edge=0.012, slope=0.5, t_max=None, cap=None, r=0.006):
    """Forma piatta 'a gemma': contorno 2D (u, v) estruso lungo n = u x v, sottile sul bordo (t_edge)
    e piu' spessa verso l'interno (pendenza slope; al massimo t_max o cap(u))."""
    U = norm(u_dir)
    V = np.asarray(v_dir, dtype=np.float64)
    V = norm(V - U * (V @ U))
    N = np.cross(U, V)
    M = np.stack([U, V, N], axis=1).astype(np.float32)
    O = np.asarray(origin, dtype=np.float32)
    d2 = poly_d2(outline)
    pts = np.asarray(outline, dtype=np.float64)
    ext = pts.max(0) - pts.min(0)
    tm = t_edge + slope * 0.5 * float(min(ext))
    if t_max is not None:
        tm = min(tm, t_max)

    def f(p):
        q = (p - O) @ M
        dd = d2(q[:, 0], q[:, 1])
        th = t_edge + slope * np.maximum(-dd, 0.0)
        if t_max is not None:
            th = np.minimum(th, t_max)
        if cap is not None:
            th = np.minimum(th, cap(q[:, 0]))
        a = dd + r
        b = np.abs(q[:, 2]) - th + r
        return np.minimum(np.maximum(a, b), 0.0) + np.sqrt(np.maximum(a, 0.0) ** 2 + np.maximum(b, 0.0) ** 2) - r

    corners = np.array([O + U * u + V * v + N * s * (tm + 0.01) for u, v in pts for s in (-1, 1)])
    return SDF(f, corners.min(0) - 0.01, corners.max(0) + 0.01)


def segs_cross(a, b, c, d):
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return (orient(a, b, c) * orient(a, b, d) < 0) and (orient(c, d, a) * orient(c, d, b) < 0)


def is_simple(poly):
    n = len(poly)
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if segs_cross(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]):
                return False
    return True


def bolt_outline(length, w0, segs):
    """Contorno di un fulmine a zig-zag lungo +u: base larga (w0) in u=0, punta aguzza in u=length.

    segs: lista di (angolo in gradi rispetto all'asse, lunghezza relativa) dei tratti."""
    P = [np.zeros(2)]
    for ang, ln in segs:
        a = math.radians(ang)
        P.append(P[-1] + ln * np.array([math.cos(a), math.sin(a)]))
    P = np.array(P)
    P[:, 1] -= P[-1, 1] * np.linspace(0, 1, len(P))  # la punta torna sull'asse
    P *= length / P[-1, 0]
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)]) / seg.sum()
    for _ in range(6):
        w = w0 * (1 - s) ** 0.8
        left, right = [], []
        for i in range(len(P) - 1):
            d1 = (P[i + 1] - P[i]) / seg[i]
            n1 = np.array([-d1[1], d1[0]])
            if i == 0:
                mm, ml = n1, w[0]
            else:
                d0 = (P[i] - P[i - 1]) / seg[i - 1]
                n0 = np.array([-d0[1], d0[0]])
                mm = norm(n0 + n1)
                ml = w[i] / max(float(mm @ n0), 0.35)
            left.append(P[i] + mm * ml)
            right.append(P[i] - mm * ml)
        poly = [tuple(q) for q in left + [P[-1]] + right[::-1]]
        if is_simple(poly):
            return poly
        w0 *= 0.85
    return poly


def bolt(base, direction, face, length, w0, segs, t_edge=0.014, slope=0.42, r=0.008):
    """Fulmine 3D: parte da base verso direction, con la faccia piatta rivolta (circa) verso face."""
    U = norm(direction)
    Nf = np.asarray(face, dtype=np.float64)
    Nf = norm(Nf - U * (Nf @ U))
    V = np.cross(Nf, U)
    return blade(bolt_outline(length, w0, segs), base, U, V, t_edge=t_edge, slope=slope, r=r)


def random_segs(rng, n=None, steep=(14, 26), kink=(48, 66)):
    """Tratti di un fulmine: lunghi e ripidi alternati a scatti corti e laterali (la forma a saetta)."""
    n = n or int(rng.integers(2, 4))
    sgn = 1 if rng.random() < 0.5 else -1
    out = []
    for i in range(n):
        out.append((sgn * rng.uniform(*steep), rng.uniform(0.8, 1.15)))
        if i < n - 1:
            out.append((-sgn * rng.uniform(*kink), rng.uniform(0.32, 0.42)))
    out.append((sgn * rng.uniform(*steep), rng.uniform(0.7, 0.95)))
    return out


def leaf_outline(L, w, back=0.4, n=7, tip_pow=1.7):
    """Contorno di una piuma a scaglia lungo +u: dorso arrotondato in u = -back*L, punta in u = L."""
    left = []
    for i in range(1, n + 1):  # dorso: semiellisse
        t = -1 + i / (n + 1)
        left.append((back * L * t, w * math.sqrt(max(1 - t * t, 0.0))))
    for i in range(n):
        t = i / n
        left.append((L * t, w * (1 - t ** tip_pow) ** 0.75))
    right = [(u, -v) for u, v in left]
    return [(-back * L, 0.0)] + left + [(L, 0.0)] + right[::-1]


def feather_outline(L, w, base_w=0.3, peak=0.3, tip_start=0.72, finger=None, bend=0.0, asym=0.0, n=12,
                    notches=(), round_tip=True):
    """Contorno di una penna lungo +u (calamo in u = 0, punta in u = L).

    finger: (t, frazione) restringe il vessillo da t in poi (penne 'a dito' dell'aquila);
    notches: lista di (t, lato, profondita') per le penne strappate dai fulmini."""
    def half(t):
        if t < peak:
            h = base_w + (1 - base_w) * math.sin(t / peak * math.pi / 2)
        else:
            h = 1.0
        if finger is not None:
            t0, frac = finger
            k = min(max((t - t0) / 0.12, 0.0), 1.0)
            h *= 1 - (1 - frac) * (k * k * (3 - 2 * k))
        if t > tip_start:
            q = (t - tip_start) / (1 - tip_start)
            h *= math.sqrt(max(1 - q * q, 0.0)) if round_tip else (1 - q ** 1.4) ** 0.8
        return w * h

    left, right = [], []
    for i in range(n):
        t = i / n
        off = bend * t * t
        hl, hr = half(t) * (1 + asym), half(t) * (1 - asym)
        for nt, side, depth in notches:
            if abs(t - nt) < 0.5 / n:
                if side > 0:
                    hl *= 1 - depth
                else:
                    hr *= 1 - depth
        left.append((L * t, off + hl))
        right.append((L * t, off - hr))
    return left + [(L, bend)] + right[::-1]


# ============================================================ corpo (leone) + collo
m = Model("ThunderGriffin", "pet")
rng = np.random.default_rng(23)


def ell_x(radii, c, ang):
    return ellipsoid(radii).rot(ang, 0, 0).translate(c)


chest = ell_x((0.46, 0.54, 0.62), (0, -0.24, 1.46), -14)
ribs = ell_x((0.42, 0.56, 0.43), (0, 0.34, 1.37), -10)
rump = ellipsoid((0.37, 0.42, 0.42), (0, 0.97, 1.15))
torso = union(union(chest, ribs, k=0.32), rump, k=0.3)
shoulders = union(*[muscle((sx * 0.27, -0.3, 1.66), (sx * 0.31, -0.48, 1.0), 0.2, 0.26) for sx in (1, -1)])

# zampe posteriori da leone, accovacciate e pronte allo scatto (unghioli d'oro fuori)
HIND = {}
hind_parts = []
for sx in (1, -1):
    knee, hock, paw = (sx * 0.37, 0.55, 0.66), (sx * 0.37, 1.03, 0.37), (sx * 0.38, 0.76, 0.1)
    toes = [(sx * 0.38 + dx, 0.585 + (0.03 if abs(dx) > 0.05 else 0.0), 0.066) for dx in (-0.105, -0.035, 0.035, 0.105)]
    HIND[sx] = dict(knee=knee, hock=hock, paw=paw, toes=toes)
    hind_parts += [
        muscle((sx * 0.29, 1.06, 1.32), (sx * 0.36, 0.6, 0.64), 0.25, 0.3),     # coscia
        muscle((sx * 0.34, 0.8, 1.16), (sx * 0.39, 0.5, 0.74), 0.16, 0.15),     # quadricipite
        round_cone(knee, hock, 0.16, 0.095),                                     # gamba
        muscle((sx * 0.37, 0.7, 0.68), (sx * 0.37, 1.0, 0.42), 0.11, 0.13),     # polpaccio
        round_cone(hock, (sx * 0.38, 0.84, 0.15), 0.095, 0.1),                   # metatarso
        ellipsoid((0.15, 0.19, 0.1), paw),
        *[sphere(0.068, t) for t in toes],
    ]
hind = union(*hind_parts, k=0.07)

# zampe anteriori d'aquila: la sinistra (x<0) poggia, la destra (x>0) e' alzata con gli artigli aperti
F_SH = {sx: (sx * 0.29, -0.44, 1.24) for sx in (1, -1)}
F_KNEE = {-1: (-0.34, -0.37, 0.6), 1: (0.39, -0.9, 1.02)}
F_FOOT = {-1: (-0.35, -0.5, 0.135), 1: (0.41, -1.1, 0.74)}
fore = union(*[round_cone(F_SH[sx], F_KNEE[sx], 0.2, 0.13) for sx in (1, -1)])

NECK = catmull([(0, -0.3, 1.6), (0, -0.46, 2.0), (0, -0.57, 2.3), (0, -0.63, 2.5)], 3)
neck = tube(NECK, [0.4 - 0.14 * (i / (len(NECK) - 1)) for i in range(len(NECK))])

TAIL = catmull([(0.04, 1.26, 1.18), (0.22, 1.63, 0.9), (0.6, 1.83, 0.46), (1.03, 1.63, 0.3), (1.32, 1.22, 0.47),
                (1.4, 0.92, 0.85), (1.32, 0.8, 1.18)], 4)
NT = len(TAIL) - 1
tail = tube(TAIL, [0.13 - 0.055 * (i / NT) for i in range(NT + 1)])

core = union(union(torso, shoulders, k=0.16), neck, k=0.22)
core = union(core, hind, fore, k=0.08)
m.add("Body", bounded(union(core, tail, k=0.05), (-0.72, -1.12, -0.05), (1.56, 2.0, 2.82)), SILVER, tris=9000,
      voxel=0.022)

# ============================================================ testa d'aquila
H = np.array([0.0, -0.69, 2.66])
skull = ellipsoid((0.3, 0.38, 0.29), tuple(H))
cheeks = union(*[ellipsoid((0.15, 0.18, 0.14), (sx * 0.15, -0.89, 2.55)) for sx in (1, -1)])
ridge = union(*[ellipsoid((0.14, 0.15, 0.08)).rot(0, -sx * 18, 0).translate((sx * 0.16, -0.91, 2.78)) for sx in (1, -1)])
head = union(union(skull, cheeks, k=0.12), ridge, k=0.08)
head_neck = union(head, neck, k=0.14)

# piume del collo sulla nuca: punte che scappano all'indietro (lato fiero dell'aquila)
hackles = []
for el, n_az, L, w in ((-0.15, 7, 0.3, 0.075), (0.25, 6, 0.32, 0.08), (0.62, 4, 0.28, 0.075)):
    for j in range(n_az):
        az = math.radians(-125 + 250 * j / (n_az - 1)) if n_az > 1 else 0.0
        d = np.array([math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)])
        if d[1] < -0.1:
            continue
        p, nrm = project(head_neck, H, d)
        T = np.array([0.0, 1.0, -0.35])
        T = norm(T - nrm * (T @ nrm))
        U = norm(T + 0.22 * nrm)
        V = np.cross(nrm, U)
        hackles.append(blade(leaf_outline(L, w, back=0.35), p + nrm * 0.005, U, V, t_edge=0.012, slope=0.32))
m.add("Head", union(head, fast_union(hackles), k=0.02), STORM, role="detail", tris=5500, voxel=0.016)

# ============================================================ becco d'oro spalancato (seghettato)
bp, _ = project(head, tuple(H), (0, -1.0, -0.18))
BU = norm((0, -1.0, -0.12))
BV = norm(np.array([0, 0, 1.0]) - BU * BU[2])
BB = np.asarray(bp) - BU * 0.1  # base affondata nella faccia
UPPER = [(-0.08, 0.15), (0.05, 0.19), (0.18, 0.185), (0.29, 0.15), (0.38, 0.085), (0.44, -0.005), (0.468, -0.105),
         (0.458, -0.2), (0.425, -0.29), (0.398, -0.232), (0.378, -0.16), (0.352, -0.103), (0.31, -0.072),
         (0.22, -0.056), (0.12, -0.05), (0.02, -0.05), (-0.08, -0.03)]


def beak_cap(u):
    return 0.15 * (1 - 0.74 * np.clip(u / 0.46, 0.0, 1.0) ** 1.2) + 0.006


upper = blade(UPPER, BB, BU, BV, t_edge=0.014, slope=0.95, cap=beak_cap, r=0.008)
HINGE = np.array([-0.05, -0.05])
OPEN = math.radians(-26)


def open_jaw(pts):
    c, s = math.cos(OPEN), math.sin(OPEN)
    return [tuple(HINGE + np.array([c * (u - HINGE[0]) - s * (v - HINGE[1]), s * (u - HINGE[0]) + c * (v - HINGE[1])]))
            for u, v in pts]


LOWER_TOP = [(-0.06, -0.04), (0.06, -0.058), (0.17, -0.07), (0.27, -0.088), (0.335, -0.112)]
LOWER = open_jaw(LOWER_TOP + [(0.305, -0.15), (0.22, -0.17), (0.1, -0.18), (0.0, -0.17), (-0.08, -0.12)])
lower = blade(LOWER, BB, BU, BV, t_edge=0.014, slope=0.9, cap=lambda u: 0.11 * (1 - 0.6 * np.clip(u / 0.34, 0, 1)) + 0.006,
              r=0.008)
m.add("Beak", union(upper, lower, k=0.01), GOLD, role="detail", tris=2600, voxel=0.011, reflectance=0.12)


def beak_pt(u, v, w=0.0):
    return BB + BU * u + BV * v + np.array([w, 0.0, 0.0])


# bocca scura fra le mandibole + narici sulla cera
lt = open_jaw(LOWER_TOP)
gape_poly = [(-0.07, -0.035), (0.33, -0.07)] + [lt[-1], lt[-2], lt[-3], lt[0]][::1]
gape_poly = [(-0.07, -0.035), (0.31, -0.07), (0.33, -0.1)] + lt[::-1][:-1] + [(-0.07, -0.06)]
mouth_in = blade(gape_poly, BB, BU, BV, t_edge=0.09, slope=0.0, r=0.01)
tongue = round_cone(tuple(beak_pt(-0.02, -0.09)), tuple(beak_pt(0.2, -0.12)), 0.05, 0.02)
nostrils = union(*[ellipsoid((0.022, 0.03, 0.016)).rot(0, 0, sx * 20).translate(tuple(beak_pt(0.07, 0.115, sx * 0.075)))
                   for sx in (1, -1)])
m.add("Mouth", union(mouth_in, tongue, nostrils), MOUTH, role="detail", tris=700, voxel=0.011)

# dentini aguzzi sul bordo del becco (sopra e sotto)
teeth = []
for u in np.linspace(0.03, 0.29, 8):
    v = float(np.interp(u, [p[0] for p in UPPER[-5:][::-1]], [p[1] for p in UPPER[-5:][::-1]]))
    hw = 0.014 + 0.95 * 0.012
    for sx in (1, -1):
        a = beak_pt(u, v + 0.012, sx * hw)
        teeth.append(round_cone(tuple(a), tuple(a - BV * 0.052 + np.array([sx * 0.006, 0, 0])), 0.016, 0.003))
for i, u in enumerate(np.linspace(0.05, 0.25, 5)):
    q = open_jaw([(u, float(np.interp(u, [p[0] for p in LOWER_TOP], [p[1] for p in LOWER_TOP])))])[0]
    for sx in (1, -1):
        a = beak_pt(q[0], q[1] - 0.01, sx * 0.024)
        nrm2 = BV * math.cos(OPEN) - BU * math.sin(OPEN)
        teeth.append(round_cone(tuple(a), tuple(a + nrm2 * 0.042), 0.014, 0.003))
m.add("Teeth", fast_union(teeth), TOOTH, role="detail", tris=900, voxel=0.008)


# ============================================================ piumaggio bianco a scaglie (collo, petto, spalle, "calzoni")
PL_C = np.array([0.0, -0.15, 0.85])
PL_N = norm((0.0, 0.985, -0.174))  # piano obliquo garrese -> sterno: davanti piume d'aquila, dietro pelo da leone
painted = core.offset(0.024)


def scale_feather(base_sdf, origin, direction, point_dir, L, w, lift=0.004, tilt=0.2, back=0.4):
    """Piuma a scaglia appoggiata sulla superficie, con la punta verso point_dir e leggermente sollevata."""
    p, nrm = project(base_sdf, origin, direction)
    T = np.asarray(point_dir, dtype=np.float64)
    T = T - nrm * (T @ nrm)
    if np.linalg.norm(T) < 1e-6:
        return None, p
    U = norm(norm(T) + tilt * nrm)
    V = np.cross(nrm, U)
    return blade(leaf_outline(L, w, back=back, n=4), p + nrm * lift, U, V, t_edge=0.012, slope=0.3), p


scales = []
A0, A1 = np.array([0.0, -0.22, 0.98]), np.array([0.0, -0.6, 2.38])
AX = norm(A1 - A0)
FWD = norm(np.array([0.0, -1.0, 0.0]) - AX * (-AX[1]))
SIDE = np.array([1.0, 0.0, 0.0])
rows = np.linspace(0.0, 1.0, 12)
for k, t in enumerate(rows):
    c = A0 + (A1 - A0) * t
    L = 0.2 - 0.07 * t
    w = 0.085 - 0.025 * t
    nps = int(10 + 6 * t)
    for j in range(nps):
        psi = math.radians(-170 + 340 * (j + 0.5 * (k % 2)) / nps)
        d = math.cos(psi) * FWD + math.sin(psi) * SIDE
        sh, p = scale_feather(painted, c, d, -AX, L, w)
        if sh is None or (p - PL_C) @ PL_N > 0.05 or p[2] > 2.45:
            continue
        scales.append(sh)
# "calzoni" di piume sulle zampe anteriori, con la frangia che copre il ginocchio
for sx in (1, -1):
    a, b = np.array(F_SH[sx]), np.array(F_KNEE[sx])
    ax = norm(b - a)
    s1 = norm(np.cross(ax, (0.0, 0.0, 1.0)) if abs(ax[2]) < 0.9 else np.cross(ax, (1.0, 0.0, 0.0)))
    s2 = np.cross(ax, s1)
    for k, t in enumerate((0.35, 0.55, 0.75, 0.93)):
        c = a + (b - a) * t
        for j in range(9):
            psi = 2 * math.pi * (j + 0.5 * (k % 2)) / 9
            d = math.cos(psi) * s1 + math.sin(psi) * s2
            L = 0.17 if t < 0.9 else 0.22
            sh, p = scale_feather(painted, c, d, ax, L, 0.075, tilt=0.28)
            if sh is not None:
                scales.append(sh)
plume_region = halfspace(PL_C - PL_N * 0.06, PL_N)
plumage = bounded(union(paint(core, plume_region, d=0.024, depth=0.06), fast_union(scales), k=0.0),
                  (-0.78, -1.4, 0.3), (0.78, 0.3, 2.62))
m.add("Plumage", plumage, STORM, role="detail", tris=11000, voxel=0.016)

# ============================================================ zampe d'aquila: tarso a scaglie (ardesia) e artigli d'oro


def rodrigues(v, k, ang):
    v, k = np.asarray(v, dtype=np.float64), norm(k)
    a = math.radians(ang)
    return v * math.cos(a) + np.cross(k, v) * math.sin(a) + k * (k @ v) * (1 - math.cos(a))


def toe(F, D, lens, radii, curl, talon_len, talon_r, talon_curl):
    """Dito (tubo a nocche che si piega verso il basso) + artiglio d'oro ricurvo; ritorna (dito, artiglio)."""
    lat = np.cross(D, (0.0, 0.0, 1.0))
    lat = norm(lat) if np.linalg.norm(lat) > 1e-6 else np.array([1.0, 0.0, 0.0])
    pts, d = [np.asarray(F, dtype=np.float64)], norm(D)
    for ln, c in zip(lens, curl):
        d = rodrigues(d, lat, -c)
        pts.append(pts[-1] + d * ln)
    knuckles = union(*[sphere(r * 1.08, tuple(q)) for q, r in zip(pts[1:-1], radii[1:-1])])
    digit = union(tube([tuple(q) for q in pts], list(radii)), knuckles, k=0.03)
    tp = [pts[-1] - d * 0.02]
    td = d
    n = 6
    for i in range(n):
        td = rodrigues(td, lat, -talon_curl / n)
        tp.append(tp[-1] + td * talon_len / n)
    claw = tube([tuple(q) for q in tp], [talon_r * (1 - i / n) ** 0.9 + 0.004 for i in range(n + 1)])
    return digit, claw


def eagle_foot(F, fwd, pitch, spread, raised):
    digits, claws = [], []
    for i, phi in enumerate((-spread, 0.0, spread)):
        D = rodrigues(fwd, (0.0, 0.0, 1.0), phi)
        D = rodrigues(D, np.cross(D, (0.0, 0.0, 1.0)), -pitch)
        lens = (0.14, 0.12, 0.1) if i == 1 else (0.12, 0.1, 0.09)
        curl = (8, 22, 30) if raised else (2, 6, 10)
        dg, cl = toe(F, D, lens, (0.07, 0.06, 0.052, 0.045), curl, 0.19 if raised else 0.16, 0.046,
                     150 if raised else 95)
        digits.append(dg)
        claws.append(cl)
    back = rodrigues(-np.asarray(fwd, dtype=np.float64), (0.0, 0.0, 1.0), 15)
    back = rodrigues(back, np.cross(back, (0.0, 0.0, 1.0)), -(25 if raised else 32))
    dg, cl = toe(F, back, (0.1, 0.07), (0.065, 0.055, 0.048), (0, 18), 0.14, 0.042, 110)
    digits.append(dg)
    claws.append(cl)
    return digits, claws


slate_bits, gold_bits = [], []
for sx in (1, -1):
    kn, ft = np.array(F_KNEE[sx]), np.array(F_FOOT[sx])
    tars = round_cone(tuple(kn), tuple(ft), 0.088, 0.078)
    rings = [round_cone(tuple(kn + (ft - kn) * (t - 0.05)), tuple(kn + (ft - kn) * (t + 0.05)), 0.098, 0.094)
             for t in (0.2, 0.36, 0.52, 0.68, 0.84)]
    raised = sx > 0
    fwd = norm((0.12 * sx, -1.0, 0.0))
    digits, claws = eagle_foot(ft, fwd, 38 if raised else 0, 38 if raised else 30, raised)
    slate_bits += [union(tars, *rings, k=0.02), *digits]
    gold_bits += claws
# unghioli dei piedi da leone
for sx in (1, -1):
    for t in HIND[sx]["toes"]:
        a = np.array(t) + (0, -0.05, -0.005)
        gold_bits.append(tube([tuple(a), tuple(a + (0, -0.05, -0.02)), tuple(a + (0, -0.08, -0.06))], [0.03, 0.022, 0.004]))

# ============================================================ occhi luminosi, palpebre e sopracciglia a punta
EYE_R = (0.094, 0.05, 0.084)
frames = {sx: Frame(head, tuple(H), (sx * 0.62, -0.76, 0.12), sink=0.034) for sx in (1, -1)}


def lid_cut(a, b, c, cut, slope, grow=0.018, above=True):
    A, B, C = a + grow, b + grow, c + grow
    s = 1.0 if above else -1.0
    plane = SDF(lambda p: s * (cut + slope * p[:, 0] - p[:, 2]) / math.sqrt(1 + slope * slope), (-A, -B, -C), (A, B, C))
    return ellipsoid((A, B, C)).intersect(plane)


glows, pupils, shines, lids_top, lids_low = [], [], [], [], []
for sx, f in frames.items():
    glows.append(f.place(ellipsoid(EYE_R)))
    pupils.append(f.place(ellipsoid((0.03, 0.02, 0.034)), (sx * 0.004, -0.047, -0.012)))
    shines.append(f.place(sphere(0.017), (-0.028, -0.052, 0.028)))
    lids_top.append(f.place(lid_cut(*EYE_R, cut=0.012, slope=-sx * 0.55)))
    lids_low.append(f.place(lid_cut(*EYE_R, cut=-0.058, slope=sx * 0.12, above=False)))
m.add("EyeGlow", union(*glows), EYE_GLOW, material="Neon", role="glow", tris=700, voxel=0.01)
m.add("Pupils", union(*pupils), PUPIL, role="eye", tris=300, voxel=0.008)
m.add("Shine", union(*shines), WHITE, role="shine", tris=150, voxel=0.007)


def surf_pt(sdf, origin, target, lift=0.0):
    o = np.asarray(origin, dtype=np.float64)
    p, n = project(sdf, o, np.asarray(target, dtype=np.float64) - o)
    return np.asarray(p) + np.asarray(n) * lift


brows = []
for sx in (1, -1):
    p0 = surf_pt(head, H, (sx * 0.05, -1.2, 2.72), -0.01)
    p1 = surf_pt(head, H, (sx * 0.17, -1.1, 2.84), 0.005)
    p2 = surf_pt(head, H, (sx * 0.3, -0.9, 2.9), 0.0)
    p3 = p2 + np.array([sx * 0.11, 0.2, 0.1])
    p4 = p3 + np.array([sx * 0.07, 0.18, 0.1])
    brows.append(tube([tuple(q) for q in (p0, p1, p2, p3, p4)], [0.045, 0.06, 0.055, 0.034, 0.008]))
    q0 = surf_pt(head, H, (sx * 0.3, -0.62, 2.88), -0.01)
    brows.append(tube([tuple(q0), tuple(q0 + (sx * 0.12, 0.2, 0.04)), tuple(q0 + (sx * 0.18, 0.36, 0.06))], [0.045, 0.03, 0.007]))
    q1 = surf_pt(head, H, (sx * 0.33, -0.66, 2.74), -0.01)
    brows.append(tube([tuple(q1), tuple(q1 + (sx * 0.12, 0.18, -0.02)), tuple(q1 + (sx * 0.17, 0.32, -0.04))], [0.04, 0.026, 0.007]))
m.add("Slate", union(*slate_bits, *brows, *lids_top), SLATE, role="detail", tris=5000, voxel=0.013)
m.add("Talons", fast_union(gold_bits), GOLD, role="detail", tris=2600, voxel=0.011, reflectance=0.12)
m.add("Lids", union(*lids_low), STORM, role="detail", tris=300, voxel=0.01)

# ============================================================ criniera di fulmini (+ ciuffo della coda): parte Neon "Mane"
MC = np.array([0.0, -0.48, 2.5])
mane = []
N_OUT = 17
for i in range(N_OUT):
    th = math.radians(-150 + 300 * i / (N_OUT - 1))
    R = np.array([math.sin(th), 0.0, math.cos(th)])
    sweep = math.radians(30 + 18 * abs(math.degrees(th)) / 150)
    D = norm(R * math.cos(sweep) + np.array([0.0, 1.0, 0.0]) * math.sin(sweep))
    L = (0.72 + 0.46 * math.cos(th * 0.72)) * rng.uniform(0.92, 1.08)
    B = MC + np.array([0.2 * math.sin(th), 0.04, 0.22 * math.cos(th)])
    mane.append(bolt(B, D, (rng.normal(0, 0.2), -1.0, rng.normal(0, 0.2)), L, rng.uniform(0.072, 0.09), random_segs(rng)))
N_IN = 12
for i in range(N_IN):
    th = math.radians(-138 + 276 * i / (N_IN - 1))
    R = np.array([math.sin(th), 0.0, math.cos(th)])
    sweep = math.radians(14 + 10 * abs(math.degrees(th)) / 140)
    D = norm(R * math.cos(sweep) + np.array([0.0, 1.0, 0.0]) * math.sin(sweep))
    L = (0.5 + 0.12 * math.cos(th)) * rng.uniform(0.9, 1.1)
    B = MC + np.array([0.18 * math.sin(th), -0.04, 0.2 * math.cos(th)])
    mane.append(bolt(B, D, (rng.normal(0, 0.2), -1.0, rng.normal(0, 0.2)), L, rng.uniform(0.07, 0.085),
                     random_segs(rng, n=2)))
# ciuffo di fulmini sulla punta della coda
TT = np.array(TAIL[-1])
TD = norm(np.array(TAIL[-1]) - np.array(TAIL[-3]))
ts1 = norm(np.cross(TD, (0.0, 0.0, 1.0)))
ts2 = np.cross(TD, ts1)
for i in range(6):
    a = 2 * math.pi * i / 6 + 0.3
    D = norm(TD * 1.0 + 0.62 * (math.cos(a) * ts1 + math.sin(a) * ts2))
    mane.append(bolt(TT - TD * 0.05, D, np.cross(D, ts1) + 0.3 * ts2, rng.uniform(0.32, 0.44), 0.065, random_segs(rng, n=2)))
mane.append(bolt(TT - TD * 0.05, TD, ts1, 0.5, 0.075, random_segs(rng, n=2)))
m.add("Mane", fast_union(mane), BOLT, material="Neon", role="glow", tris=10000, voxel=0.012)

# ============================================================ ali enormi alzate (gruppi WingR / WingL)
WS, WE, WW, WH = np.array([0.0, 0.0]), np.array([0.42, 0.36]), np.array([0.82, 1.02]), np.array([1.0, 1.26])


def wfeather(base_xz, ang, L, w, y0, t_edge=0.013, slope=0.32, **kw):
    a = math.radians(ang)
    U = np.array([math.cos(a), 0.0, math.sin(a)])
    V = np.array([-math.sin(a), 0.0, math.cos(a)])
    o = np.array([base_xz[0], y0, base_xz[1]])
    return blade(feather_outline(L, w, **kw), o, U, V, t_edge=t_edge, slope=slope, r=0.006)


def wing_layers(ragged):
    rem, cov, marg, sparks = [], [], [], []
    hand_trail = np.array([0.8, -0.6])
    arm_trail = np.array([0.86, -0.52])
    P_LEN = [0.86, 0.92, 0.98, 1.04, 1.1, 1.15, 1.18, 1.15, 1.04]
    for i in range(9):
        t = i / 8
        base = WW + (WH - WW) * t + hand_trail * 0.04
        ang = 6 + 60 * t ** 0.95
        notches = ()
        if i in ragged:
            notches = ((0.78, 1, 0.55), (0.86, -1, 0.5), (0.93, 1, 0.45))
        rem.append(wfeather(base, ang, P_LEN[i], 0.072, 0.0, finger=(0.5, 0.62) if i >= 4 else None, bend=-0.035,
                            asym=-0.18, notches=notches, n=14))
        cov += [wfeather(base - hand_trail * 0.03, ang + 2, 0.36 * P_LEN[i], 0.082, s * 0.03, slope=0.3) for s in (-1, 1)]
        if i in ragged:
            a = math.radians(ang)
            tip = base + P_LEN[i] * np.array([math.cos(a), math.sin(a)]) * 0.9
            sparks.append((tip, ang))
    for j in range(9):
        t = j / 8
        base = WW + (WE - WW) * t * 0.96 + arm_trail * 0.04
        ang = 2 - 66 * t
        L = 0.82 - 0.14 * t
        rem.append(wfeather(base, ang, L, 0.078, 0.0, asym=-0.1, n=12))
        cov += [wfeather(base - arm_trail * 0.03, ang + 3, 0.42 * L, 0.088, s * 0.03, slope=0.3) for s in (-1, 1)]
    for f, ang, L in ((0.25, -72, 0.62), (0.5, -86, 0.56), (0.75, -100, 0.5)):
        base = WE + (WS - WE) * f + np.array([0.3, -0.95]) * 0.03
        rem.append(wfeather(base, ang, L, 0.08, 0.0, n=10))
        cov += [wfeather(base, ang + 3, 0.45 * L, 0.088, s * 0.03, slope=0.3) for s in (-1, 1)]
    # copritrici mediane e piccole (bianche) + bordo d'attacco + alula
    edge = resample([WS, WE, WW, WH], 0.11)
    for q in edge[1:-1]:
        q = np.asarray(q)
        frac = (q[1]) / WH[1]
        ang = -60 + 70 * frac
        for s in (-1, 1):
            marg.append(wfeather(q + np.array([0.04, -0.02]), ang, 0.2, 0.07, s * 0.05, slope=0.32, n=8))
    marg.append(tube([(x, 0.0, z) for x, z in (WS, WE, WW, WH)], [0.11, 0.085, 0.068, 0.045]))
    hand = norm(WH - WW)
    hang = math.degrees(math.atan2(hand[1], hand[0]))
    for k, (dl, da) in enumerate(((0.0, 18), (0.05, 10), (0.1, 2))):
        b = WW + hand * dl
        marg.append(wfeather(b, hang + da, 0.3 - 0.05 * k, 0.06, -0.02, n=8))
    return rem, cov, marg, sparks


WING_ROOT = np.array([0.3, 0.12, 1.82])


def place_wing(shape, sx):
    s = shape.rot(-12, 0, 0).rot(0, 0, 28).translate(tuple(WING_ROOT))
    return s if sx > 0 else s.mirrored()


for sx, nm, ragged in ((1, "WingR", (5, 7)), (-1, "WingL", (6,))):
    rem, cov, marg, sparks = wing_layers(ragged)
    piv = (float(sx * WING_ROOT[0]), float(WING_ROOT[1]), float(WING_ROOT[2]))
    wb = []
    hand = norm(WH - WW)
    for tip, ang in sparks:
        a = math.radians(ang)
        wb.append(bolt((tip[0], 0.0, tip[1]), (math.cos(a), 0.0, math.sin(a)), (0.0, -1.0, 0.0), 0.3, 0.05,
                       random_segs(rng, n=2), t_edge=0.012, slope=0.4))
    wb.append(bolt((WH[0] - 0.05, 0.0, WH[1] - 0.05), rodrigues(np.array([hand[0], 0.0, hand[1]]), (0, 1, 0), -25),
                   (0.0, -1.0, 0.0), 0.36, 0.055, random_segs(rng, n=2)))
    for t in (0.35, 0.7):
        q = WE + (WW - WE) * t
        wb.append(bolt((q[0], 0.0, q[1]), (-0.6, 0.0, 0.8), (0.0, -1.0, 0.0), 0.24, 0.045, random_segs(rng, n=2)))
    m.add(nm, place_wing(fast_union(rem), sx), REMIGE, role="detail", tris=4200, voxel=0.013, group=nm, pivot=piv)
    m.add(nm + "Covert", place_wing(fast_union(cov), sx), STEEL, role="detail", tris=2600, voxel=0.013, group=nm, pivot=piv)
    m.add(nm + "Marginal", place_wing(fast_union(marg), sx), STORM, role="detail", tris=2200, voxel=0.013, group=nm,
          pivot=piv)
    m.add("WingBolts" + nm[-1], place_wing(fast_union(wb), sx), BOLT_HOT, material="Neon", role="glow", tris=800,
          voxel=0.011, group=nm, pivot=piv)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
