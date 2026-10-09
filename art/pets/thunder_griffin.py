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
SILVER = (116, 132, 160)       # corpo da leone grigio tempesta
STORM = (226, 232, 245)        # piume bianco tempesta
HEAD_WHITE = (244, 247, 253)   # testa d'aquila: il bianco piu' luminoso
STEEL = (96, 126, 172)         # copritrici blu acciaio
SLATE = (44, 54, 82)           # ardesia scura: sopracciglia, zampe d'aquila, strisce
REMIGE = (52, 64, 98)          # penne remiganti ardesia
RUFF = (48, 62, 98)            # collare di piume "nube temporalesca" dietro la testa
GOLD = (255, 184, 36)
MOUTH = (64, 16, 40)
TOOTH = (255, 252, 240)
PUPIL = (14, 16, 34)
WHITE = (255, 255, 255)
BOLT = (36, 206, 255)          # fulmini ciano elettrico
EYE_GLOW = (255, 238, 140)
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


def project_many(sdf, origins, dirs, max_dist=1.6, n=160):
    """Come project(), ma per tanti raggi insieme (partenza interna): ritorna (punti, normali)."""
    D = np.asarray(dirs, dtype=np.float64).reshape(-1, 3)
    D = D / np.linalg.norm(D, axis=1, keepdims=True)
    O = np.asarray(origins, dtype=np.float64).reshape(-1, 3)
    if len(O) == 1:
        O = np.repeat(O, len(D), axis=0)
    ts = np.linspace(0.0, max_dist, n)
    P = (O[:, None, :] + ts[None, :, None] * D[:, None, :]).reshape(-1, 3).astype(np.float32)
    out = sdf(P).reshape(len(D), n) > 0
    first = np.argmax(out, axis=1)
    lo, hi = ts[np.maximum(first - 1, 0)], ts[first]
    for _ in range(22):
        mid = 0.5 * (lo + hi)
        v = sdf((O + mid[:, None] * D).astype(np.float32))
        hi, lo = np.where(v > 0, mid, hi), np.where(v > 0, lo, mid)
    pts = O + 0.5 * (lo + hi)[:, None] * D
    g = np.zeros_like(pts)
    for ax in range(3):
        e = np.zeros(3)
        e[ax] = 1e-3
        g[:, ax] = sdf((pts + e).astype(np.float32)) - sdf((pts - e).astype(np.float32))
    return pts, g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)


def paint(base, region, d=0.022, depth=0.05, k=0.012):
    """Vernice a strato sottile (fra -depth e +d dalla superficie) ritagliata dalla regione."""
    t = (d + depth) / 2
    return base.offset(d - t).shell(t).intersect(region, k=k)


GROUND = SDF(lambda p: -p[:, 2], (-20, -20, 0), (20, 20, 20))  # taglio piatto a z = 0: niente sotto i piedi


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


def bolt_outline(length, w0, segs, hold=0.42, power=0.9):
    """Contorno di un fulmine a saetta lungo +u: base larga (w0) in u=0, punta aguzza in u=length.

    segs: lista di (angolo in gradi rispetto all'asse, lunghezza relativa) dei tratti; la larghezza resta
    piena fino alla frazione 'hold' della lunghezza e poi si assottiglia fino alla punta."""
    P = [np.zeros(2)]
    for ang, ln in segs:
        a = math.radians(ang)
        P.append(P[-1] + ln * np.array([math.cos(a), math.sin(a)]))
    P = np.array(P)
    P[:, 1] -= P[-1, 1] * np.linspace(0, 1, len(P))  # la punta torna sull'asse
    P *= length / P[-1, 0]
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)]) / seg.sum()
    for _ in range(8):
        w = w0 * np.clip((1 - s) / (1 - hold), 0, 1) ** power
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
                ml = w[i] / max(float(mm @ n0), 0.4)
            left.append(P[i] + mm * ml)
            right.append(P[i] - mm * ml)
        poly = [tuple(q) for q in left + [P[-1]] + right[::-1]]
        if is_simple(poly):
            return poly
        w0 *= 0.88
    return poly


def bolt(base, direction, face, length, w0, segs, t_edge=0.02, slope=0.38, r=0.008, twist=0.0, hold=0.42):
    """Fulmine 3D: parte da base verso direction, con la faccia piatta rivolta (circa) verso face."""
    U = norm(direction)
    Nf = np.asarray(face, dtype=np.float64)
    Nf = norm(Nf - U * (Nf @ U))
    if twist:
        Nf = rodrigues(Nf, U, twist)
    V = np.cross(Nf, U)
    return blade(bolt_outline(length, w0, segs, hold=hold), base, U, V, t_edge=t_edge, slope=slope, r=r)


def bolt_center(length, segs):
    """Linea mediana (2D) del fulmine costruito da bolt_outline con gli stessi tratti."""
    P = [np.zeros(2)]
    for ang, ln in segs:
        a = math.radians(ang)
        P.append(P[-1] + ln * np.array([math.cos(a), math.sin(a)]))
    P = np.array(P)
    P[:, 1] -= P[-1, 1] * np.linspace(0, 1, len(P))
    return P * (length / P[-1, 0])


def forked_bolt(base, direction, face, length, w0, segs, twist=0.0, fork=(0.42, 32, 0.4), rng=None):
    """Fulmine con una diramazione che parte da uno spigolo della saetta (fork = (posizione, angolo, lunghezza))."""
    U = norm(direction)
    Nf = np.asarray(face, dtype=np.float64)
    Nf = norm(Nf - U * (Nf @ U))
    if twist:
        Nf = rodrigues(Nf, U, twist)
    V = np.cross(Nf, U)
    main = blade(bolt_outline(length, w0, segs), base, U, V, t_edge=0.02, slope=0.38, r=0.008)
    C = bolt_center(length, segs)
    k = int(np.argmin(np.abs(C[1:-1, 0] / length - fork[0]))) + 1  # spigolo piu' vicino alla posizione voluta
    side = 1.0 if C[k, 1] - C[k - 1, 1] < 0 else -1.0  # la diramazione esce dal lato convesso dello spigolo
    fb = np.asarray(base) + U * C[k, 0] + V * C[k, 1]
    fd = rodrigues(U, Nf, side * fork[1])
    branch = bolt(fb - fd * 0.03, fd, Nf, fork[2] * length, 0.55 * w0, random_segs(rng, n=2))
    return [main, branch]


def random_segs(rng, n=None, steep=(16, 26), kink=(64, 76), jog=None):
    """Tratti di un fulmine: lunghi e ripidi alternati a scatti laterali (la classica saetta)."""
    n = n or int(rng.integers(2, 4))
    jog = jog or ((0.72, 0.9) if n >= 3 else (0.5, 0.64))
    sgn = 1 if rng.random() < 0.5 else -1
    out = []
    for i in range(n):
        out.append((sgn * rng.uniform(*steep), rng.uniform(0.75, 1.0)))
        if i < n - 1:
            out.append((-sgn * rng.uniform(*kink), rng.uniform(*jog)))
    out.append((sgn * rng.uniform(*steep), rng.uniform(0.85, 1.05)))
    return out


def rodrigues(v, k, ang):
    """Ruota il vettore v attorno all'asse k di ang gradi."""
    v, k = np.asarray(v, dtype=np.float64), norm(k)
    a = math.radians(ang)
    return v * math.cos(a) + np.cross(k, v) * math.sin(a) + k * (k @ v) * (1 - math.cos(a))


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
    notches: lista di (t, lato, profondita', larghezza) degli strappi a V delle penne bruciate dai fulmini."""
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
        for nt, side, depth, width in notches:
            cut = 1 - depth * max(0.0, 1 - abs(t - nt) / width)
            if side > 0:
                hl *= cut
            else:
                hr *= cut
        left.append((L * t, off + hl))
        right.append((L * t, off - hr))
    return left + [(L, bend)] + right[::-1]


# ============================================================ corpo (leone) + collo
m = Model("ThunderGriffin", "pet")
rng = np.random.default_rng(23)


def ell_x(radii, c, ang):
    return ellipsoid(radii).rot(ang, 0, 0).translate(c)


chest = ell_x((0.47, 0.55, 0.63), (0, -0.25, 1.53), -22)
ribs = ell_x((0.42, 0.56, 0.42), (0, 0.3, 1.27), -20)
rump = ellipsoid((0.39, 0.42, 0.42), (0, 0.9, 0.9))
torso = union(union(chest, ribs, k=0.32), rump, k=0.3)
shoulders = union(*[muscle((sx * 0.27, -0.32, 1.74), (sx * 0.31, -0.52, 1.04), 0.21, 0.27) for sx in (1, -1)])

# zampe posteriori da leone, accovacciate e pronte allo scatto (unghioli d'oro fuori)
HIND = {}
hind_parts = []
for sx in (1, -1):
    knee, hock, paw = (sx * 0.41, 0.44, 0.5), (sx * 0.41, 0.98, 0.2), (sx * 0.42, 0.6, 0.105)
    toes = [(sx * 0.42 + dx, 0.41 + (0.035 if abs(dx) > 0.06 else 0.0), 0.078) for dx in (-0.125, -0.042, 0.042, 0.125)]
    HIND[sx] = dict(knee=knee, hock=hock, paw=paw, toes=toes)
    hind_parts += [
        muscle((sx * 0.3, 1.04, 1.12), (sx * 0.4, 0.5, 0.46), 0.33, 0.39),      # coscia
        muscle((sx * 0.37, 0.76, 0.96), (sx * 0.45, 0.42, 0.56), 0.21, 0.19),    # quadricipite
        round_cone(knee, hock, 0.17, 0.1),                                        # gamba
        muscle((sx * 0.42, 0.6, 0.52), (sx * 0.42, 0.96, 0.27), 0.135, 0.155),   # polpaccio
        round_cone(hock, (sx * 0.42, 0.7, 0.12), 0.1, 0.105),                     # metatarso
        ellipsoid((0.18, 0.22, 0.11), paw),
        *[sphere(0.08, t) for t in toes],
    ]
hind = union(*hind_parts, k=0.07)

# zampe anteriori d'aquila: la sinistra (x<0) poggia, la destra (x>0) e' alzata con gli artigli aperti
F_SH = {sx: (sx * 0.29, -0.48, 1.3) for sx in (1, -1)}
F_KNEE = {-1: (-0.34, -0.4, 0.62), 1: (0.43, -0.94, 1.42)}
F_FOOT = {-1: (-0.35, -0.54, 0.135), 1: (0.48, -1.22, 1.24)}
fore = union(*[round_cone(F_SH[sx], F_KNEE[sx], 0.21, 0.135) for sx in (1, -1)])

NECK = catmull([(0, -0.32, 1.66), (0, -0.5, 2.04), (0, -0.63, 2.36), (0, -0.7, 2.58)], 3)
neck = tube(NECK, [0.42 - 0.13 * (i / (len(NECK) - 1)) for i in range(len(NECK))])

TAIL = catmull([(0.04, 1.2, 0.95), (0.3, 1.62, 0.64), (0.75, 1.82, 0.4), (1.16, 1.64, 0.45), (1.43, 1.38, 0.78),
                (1.52, 1.28, 1.16), (1.45, 1.22, 1.5)], 4)
NT = len(TAIL) - 1
tail = tube(TAIL, [0.135 - 0.055 * (i / NT) for i in range(NT + 1)])

core = union(union(torso, shoulders, k=0.16), neck, k=0.22)
core = union(core, hind, fore, k=0.08)

# confine fra piume d'aquila (davanti) e pelo da leone (dietro): asse del petto/collo e piano obliquo garrese -> sterno
A0, A1 = np.array([0.0, -0.24, 1.0]), np.array([0.0, -0.68, 2.5])
AX = norm(A1 - A0)
PL_C = np.array([0.0, -0.2, 0.88])
PL_N = norm((0.0, 0.97, -0.243))


def hidden_front(p):
    """Zona del busto tutta coperta dal piumaggio pieno (li' il corpo non serve: triangoli risparmiati)."""
    a = 0.07 - (p - A0.astype(np.float32)) @ AX.astype(np.float32)
    b = (p - PL_C.astype(np.float32)) @ PL_N.astype(np.float32) + 0.05
    return -np.maximum(a, b)


lion_full = union(union(union(torso, shoulders, k=0.16), neck, k=0.22), hind, k=0.08)
lion_full = union(lion_full, tail, k=0.05)
body = union(SDF(lambda p: np.maximum(lion_full(p), hidden_front(p)), lion_full.lo, lion_full.hi), fore, k=0.0)
m.add("Body", bounded(body, (-0.78, -1.15, -0.05), (1.72, 2.05, 2.9)).intersect(GROUND), SILVER, tris=6900, voxel=0.022)

# ============================================================ testa d'aquila (grande, fiera)
HS = 1.22
H = np.array([0.0, -0.76, 2.76])


def hp(dx, dy, dz):
    return tuple(H + HS * np.array([dx, dy, dz]))


skull = ellipsoid((0.3 * HS, 0.38 * HS, 0.29 * HS), tuple(H))
cheeks = union(*[ellipsoid((0.15 * HS, 0.18 * HS, 0.14 * HS), hp(sx * 0.15, -0.2, -0.11)) for sx in (1, -1)])
ridge = union(*[ellipsoid((0.145 * HS, 0.15 * HS, 0.085 * HS)).rot(0, -sx * 20, 0).translate(hp(sx * 0.16, -0.22, 0.12))
                for sx in (1, -1)])
head = union(union(skull, cheeks, k=0.12 * HS), ridge, k=0.08 * HS)
head_neck = union(head, neck, k=0.14)

# piume della nuca: punte che scappano all'indietro
hackles = []
for el, n_az, L, w in ((-0.25, 6, 0.34, 0.085), (0.15, 5, 0.34, 0.09)):
    for j in range(n_az):
        az = math.radians(-125 + 250 * j / (n_az - 1))
        d = np.array([math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)])
        if d[1] < -0.1:
            continue
        p, nrm = project(head_neck, H, d)
        T = np.array([0.0, 1.0, -0.35])
        T = norm(T - nrm * (T @ nrm))
        U = norm(T + 0.22 * nrm)
        V = np.cross(nrm, U)
        hackles.append(blade(leaf_outline(L, w, back=0.35, n=4), p + nrm * 0.005, U, V, t_edge=0.012, slope=0.32))

# ============================================================ occhi luminosi socchiusi
EYE_R = (0.128, 0.068, 0.112)
frames = {sx: Frame(head, tuple(H), (sx * 0.6, -0.78, 0.12), sink=0.04) for sx in (1, -1)}


def lid_cut(a, b, c, cut, slope, grow=0.02, above=True):
    A, B, C = a + grow, b + grow, c + grow
    sg = 1.0 if above else -1.0
    plane = SDF(lambda p: sg * (cut + slope * p[:, 0] - p[:, 2]) / math.sqrt(1 + slope * slope), (-A, -B, -C), (A, B, C))
    return ellipsoid((A, B, C)).intersect(plane)


glows, pupils, shines, lids_top, lids_low = [], [], [], [], []
for sx, f in frames.items():
    glows.append(f.place(ellipsoid(EYE_R)))
    pupils.append(f.place(ellipsoid((0.036, 0.022, 0.044)), (sx * 0.008, -0.064, -0.018)))
    shines.append(f.place(sphere(0.021), (-0.04, -0.07, 0.032)))
    lids_top.append(f.place(lid_cut(*EYE_R, cut=0.03, slope=-sx * 0.55)))
    lids_low.append(f.place(lid_cut(*EYE_R, cut=-0.08, slope=sx * 0.15, above=False)))
m.add("Head", union(head, fast_union(hackles), *lids_low, k=0.0), HEAD_WHITE, role="detail", tris=4300, voxel=0.016)
m.add("EyeGlow", union(*glows), EYE_GLOW, material="Neon", role="glow", tris=500, voxel=0.012)
m.add("Pupils", union(*pupils), PUPIL, role="eye", tris=200, voxel=0.009)
m.add("Shine", union(*shines), WHITE, role="shine", tris=120, voxel=0.008)

# ============================================================ becco d'oro adunco, spalancato e seghettato
BS = 1.25
bp, _ = project(head, tuple(H), (0, -1.0, -0.2))
BU = norm((0, -1.0, -0.12))
BV = norm(np.array([0, 0, 1.0]) - BU * BU[2])
BB = np.asarray(bp) - BU * 0.1 * BS  # base affondata nella faccia
UPPER = [(-0.08, 0.15), (0.05, 0.19), (0.18, 0.185), (0.29, 0.15), (0.38, 0.085), (0.44, -0.005), (0.468, -0.105),
         (0.458, -0.2), (0.425, -0.29), (0.398, -0.232), (0.378, -0.16), (0.352, -0.103), (0.31, -0.072),
         (0.22, -0.056), (0.12, -0.05), (0.02, -0.05), (-0.08, -0.03)]
UPPER = [(u * BS, v * BS) for u, v in UPPER]


def beak_cap(u):
    return BS * (0.178 * (1 - 0.78 * np.clip(u / (0.46 * BS), 0.0, 1.0) ** 1.1) + 0.006)


upper = blade(UPPER, BB, BU, BV, t_edge=0.016, slope=0.95, cap=beak_cap, r=0.009)
HINGE = np.array([-0.05, -0.05]) * BS
OPEN = math.radians(-30)


def open_jaw(pts):
    c, s_ = math.cos(OPEN), math.sin(OPEN)
    return [tuple(HINGE + np.array([c * (u - HINGE[0]) - s_ * (v - HINGE[1]), s_ * (u - HINGE[0]) + c * (v - HINGE[1])]))
            for u, v in pts]


LOWER_TOP = [(u * BS, v * BS) for u, v in [(-0.06, -0.04), (0.06, -0.058), (0.17, -0.07), (0.27, -0.088), (0.345, -0.112)]]
LOWER = open_jaw(LOWER_TOP + [(u * BS, v * BS) for u, v in [(0.32, -0.16), (0.22, -0.19), (0.1, -0.205), (0.0, -0.195),
                                                            (-0.085, -0.13)]])
lower = blade(LOWER, BB, BU, BV, t_edge=0.016, slope=0.9,
              cap=lambda u: BS * (0.135 * (1 - 0.55 * np.clip(u / (0.34 * BS), 0, 1)) + 0.006), r=0.009)
m.add("Beak", union(upper, lower, k=0.01), GOLD, role="detail", tris=2000, voxel=0.012, reflectance=0.12)


def beak_pt(u, v, w=0.0):
    return BB + BU * u + BV * v + np.array([w, 0.0, 0.0])


# bocca scura fra le mandibole + lingua + narici sulla cera
lt = open_jaw(LOWER_TOP)
gape_poly = [(-0.07 * BS, -0.035 * BS), (0.31 * BS, -0.07 * BS), (0.33 * BS, -0.1 * BS)] + lt[::-1][:-1] + \
    [(-0.07 * BS, -0.06 * BS)]
mouth_in = blade(gape_poly, BB, BU, BV, t_edge=0.052, slope=0.0, r=0.01)
tongue = round_cone(tuple(beak_pt(-0.02 * BS, -0.11 * BS)), tuple(beak_pt(0.2 * BS, -0.16 * BS)), 0.042, 0.016)
nostrils = union(*[ellipsoid((0.025, 0.034, 0.018)).rot(0, 0, sx * 20).translate(tuple(beak_pt(0.07 * BS, 0.115 * BS,
                                                                                                    sx * 0.075 * BS)))
                   for sx in (1, -1)])
m.add("Mouth", union(mouth_in, tongue, nostrils), MOUTH, role="detail", tris=500, voxel=0.014)

# dentini aguzzi sul bordo del becco (sopra e sotto)
teeth = []
tom_u = [q[0] for q in UPPER[-5:][::-1]]
tom_v = [q[1] for q in UPPER[-5:][::-1]]
for u in np.linspace(0.03, 0.3, 8) * BS:
    v = float(np.interp(u, tom_u, tom_v))
    hw = 0.016 + 0.95 * 0.014
    for sx in (1, -1):
        a = beak_pt(u, v + 0.012, sx * hw)
        teeth.append(round_cone(tuple(a), tuple(a - BV * 0.062 + np.array([sx * 0.008, 0, 0])), 0.019, 0.003))
low_u = [q[0] for q in LOWER_TOP]
low_v = [q[1] for q in LOWER_TOP]
nrm_low = BV * math.cos(OPEN) - BU * math.sin(OPEN)
for u in np.linspace(0.05, 0.27, 5) * BS:
    q = open_jaw([(u, float(np.interp(u, low_u, low_v)))])[0]
    for sx in (1, -1):
        a = beak_pt(q[0], q[1] - 0.012, sx * 0.03)
        teeth.append(round_cone(tuple(a), tuple(a + nrm_low * 0.05), 0.017, 0.003))
m.add("Teeth", fast_union(teeth), TOOTH, role="detail", tris=700, voxel=0.009)

# ============================================================ piumaggio bianco a scaglie (collo, petto, spalle, "calzoni")


def scale_feather(p, nrm, point_dir, L, w, lift=0.0, tilt=0.3, back=0.42):
    """Piuma a scaglia appoggiata in p (normale nrm), con la punta verso point_dir e leggermente sollevata."""
    T = np.asarray(point_dir, dtype=np.float64)
    T = T - nrm * (T @ nrm)
    if np.linalg.norm(T) < 1e-6:
        return None
    U = norm(norm(T) + tilt * nrm)
    V = np.cross(nrm, U)
    return blade(leaf_outline(L, w, back=back, n=5, tip_pow=2.6), p + nrm * lift, U, V, t_edge=0.013, slope=0.26)


def shingles(base, origin, axis, fwd, edges, lobes, lobe_d, d_lo=0.022, d_hi=0.07, pw=1.7, extra=None):
    """Piumaggio a file sovrapposte (come tegole) attorno a un asse: ogni fila ha il bordo inferiore a lobi
    (le punte delle piume) sollevato sopra la fila successiva. edges = quote lungo l'asse dei bordi delle file."""
    O = np.asarray(origin, dtype=np.float32)
    A = norm(axis).astype(np.float32)
    F = norm(np.asarray(fwd, dtype=np.float64) - A * (np.asarray(fwd) @ A)).astype(np.float32)
    S = np.cross(A, F).astype(np.float32)
    hs = list(edges)

    def f(p):
        q = p - O
        h = q @ A
        phi = np.arctan2(q @ S, q @ F)
        tau = np.full(len(p), -1.0, dtype=np.float32)
        edge0 = None
        for k in range(len(hs)):
            u = phi / (2 * math.pi) * lobes[k] + 0.5 * (k % 2)
            x = 2 * (u - np.floor(u)) - 1
            edge = hs[k] - lobe_d[k] * (1 - np.abs(x) ** pw)
            if k == 0:
                edge0 = edge
            span = (hs[k + 1] - hs[k] if k + 1 < len(hs) else hs[k] - hs[k - 1]) + lobe_d[k]
            tau = np.where(h >= edge, (h - edge) / span, tau)
        D = d_lo + (d_hi - d_lo) * (1 - np.clip(tau, 0, 1)) ** 1.6
        d = np.maximum(base(p) - D, (edge0 - h) * 0.8)
        if extra is not None:
            d = np.maximum(d, extra(p))
        return d

    return SDF(f, base.lo - d_hi, base.hi + d_hi)


def plume_side(p):
    """Bordo posteriore del piumaggio (piano obliquo) con le punte delle piume che sporgono sul pelo."""
    h = (p - A0) @ AX.astype(np.float32)
    x = 2 * ((h / 0.17) - np.floor(h / 0.17)) - 1
    return ((p - PL_C.astype(np.float32)) @ PL_N.astype(np.float32) - 0.1 * (1 - np.abs(x) ** 1.7)) * 0.8


trunk = union(union(torso, shoulders, k=0.16), neck, k=0.22)
T_EDGES = [0.02, 0.25, 0.46, 0.65, 0.82, 0.98, 1.13, 1.27, 1.4, 1.52]
chest_pl = shingles(trunk, A0, AX, (0.0, -1.0, 0.0), T_EDGES, [13, 13, 14, 14, 15, 15, 16, 17, 18, 19],
                    [0.17, 0.16, 0.15, 0.14, 0.13, 0.12, 0.11, 0.1, 0.09, 0.08], extra=plume_side)
chest_pl = bounded(chest_pl, (-0.75, -1.3, 0.62), (0.75, 0.35, 2.75))
legs_pl, fringe = [], []
for sx in (1, -1):
    a, b = np.array(F_SH[sx]), np.array(F_KNEE[sx])
    Lg = float(np.linalg.norm(b - a))
    ax = norm(b - a)
    leg = round_cone(tuple(a), tuple(b), 0.21, 0.135)
    legs_pl.append(shingles(leg, a, ax, (0.0, -1.0, 0.3), [0.12 * Lg, 0.4 * Lg, 0.66 * Lg], [8, 8, 9], [0.12, 0.12, 0.12],
                            extra=lambda p, b=b, ax=ax: ((p - b.astype(np.float32)) @ ax.astype(np.float32)) * 0.8))
    s1 = norm(np.cross(ax, (0.0, 0.0, 1.0)) if abs(ax[2]) < 0.9 else np.cross(ax, (1.0, 0.0, 0.0)))
    s2 = np.cross(ax, s1)
    c = a + (b - a) * 0.86
    dirs = [math.cos(2 * math.pi * j / 9) * s1 + math.sin(2 * math.pi * j / 9) * s2 for j in range(9)]
    pts, nrms = project_many(leg.offset(0.03), c, dirs)
    for q, nrm in zip(pts, nrms):
        sh = scale_feather(q, nrm, ax, 0.27, 0.09, tilt=0.42)
        if sh is not None:
            fringe.append(sh)
plumage = union(chest_pl, *legs_pl, fast_union(fringe))

m.add("Plumage", plumage, STORM, role="detail", tris=10800, voxel=0.016)

# ============================================================ zampe d'aquila: tarso a scaglie (ardesia) e artigli d'oro


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
    claw = tube([tuple(q) for q in tp], [talon_r * (1 - i / n) ** 0.75 + 0.004 for i in range(n + 1)])
    return digit, claw


def eagle_foot(F, fwd, pitch, spread, raised):
    digits, claws = [], []
    for i, phi in enumerate((-spread, 0.0, spread)):
        D = rodrigues(fwd, (0.0, 0.0, 1.0), phi)
        D = rodrigues(D, np.cross(D, (0.0, 0.0, 1.0)), -pitch)
        lens = (0.15, 0.13, 0.11) if i == 1 else (0.13, 0.11, 0.1)
        curl = (0, 10, 20) if raised else (2, 6, 10)
        dg, cl = toe(F, D, lens, (0.075, 0.064, 0.056, 0.048), curl, 0.32 if raised else 0.25, 0.05,
                     112 if raised else 92)
        digits.append(dg)
        claws.append(cl)
    back = rodrigues(-np.asarray(fwd, dtype=np.float64), (0.0, 0.0, 1.0), 15)
    back = rodrigues(back, np.cross(back, (0.0, 0.0, 1.0)), -(25 if raised else 12))
    dg, cl = toe(F, back, (0.1, 0.07), (0.07, 0.058, 0.05), (0, 18), 0.22, 0.048, 100)
    digits.append(dg)
    claws.append(cl)
    return digits, claws


slate_bits, gold_bits = [], []
for sx in (1, -1):
    kn, ft = np.array(F_KNEE[sx]), np.array(F_FOOT[sx])
    tars = round_cone(tuple(kn), tuple(ft), 0.092, 0.082)
    rings = [round_cone(tuple(kn + (ft - kn) * (t - 0.05)), tuple(kn + (ft - kn) * (t + 0.05)), 0.103, 0.098)
             for t in (0.2, 0.36, 0.52, 0.68, 0.84)]
    raised = sx > 0
    fwd = norm((0.12 * sx, -1.0, 0.0))
    digits, claws = eagle_foot(ft, fwd, 8 if raised else 0, 40 if raised else 30, raised)
    slate_bits += [union(tars, *rings, k=0.02), *digits]
    gold_bits += claws
# unghioli dei piedi da leone
for sx in (1, -1):
    for t in HIND[sx]["toes"]:
        a = np.array(t) + (0, -0.05, -0.005)
        gold_bits.append(tube([tuple(a), tuple(a + (0, -0.055, -0.02)), tuple(a + (0, -0.09, -0.065))], [0.032, 0.024, 0.004]))


# ============================================================ sopracciglia piumate a punta (ardesia)
def surf_pt(sdf, origin, target, lift=0.0):
    o = np.asarray(origin, dtype=np.float64)
    p, n = project(sdf, o, np.asarray(target, dtype=np.float64) - o)
    return np.asarray(p) + np.asarray(n) * lift


brows = []
for sx in (1, -1):
    p0 = surf_pt(head, H, hp(sx * 0.05, -0.55, 0.05), -0.012)
    p1 = surf_pt(head, H, hp(sx * 0.17, -0.45, 0.17), 0.008)
    p2 = surf_pt(head, H, hp(sx * 0.3, -0.25, 0.24), 0.0)
    brows.append(tube([tuple(q) for q in (p0, p1, p2)], [0.058, 0.078, 0.07]))
    # piume a lama che scappano all'indietro dal sopracciglio (silhouette feroce)
    for dz, back_y, L, w in ((0.5, 0.75, 0.46, 0.085), (0.22, 0.8, 0.4, 0.078), (-0.05, 0.82, 0.33, 0.07)):
        base = surf_pt(head, H, hp(sx * 0.3, -0.18 + 0.12 * (0.5 - dz), 0.2 - 0.1 * (0.5 - dz)), -0.015)
        D = norm((sx * 0.5, back_y, dz))
        nrm = grad(head, base)
        Nf = norm(nrm - D * (nrm @ D))
        brows.append(blade(leaf_outline(L, w, back=0.25, n=5, tip_pow=1.3), base, D, np.cross(Nf, D),
                           t_edge=0.014, slope=0.4))


# saette luminose sul corpo da leone (cosce e fianchi): il grifone e' carico di elettricita'
lion = union(core, tail, k=0.05)
charge_marks = []
for sx in (1, -1):
    for c0, dr, (dy, dz), L, w in (((0.3, 0.86, 1.0), (1.0, 0.15, 0.25), (-0.45, -1.0), 0.74, 0.06),
                                   ((0.3, 0.92, 0.62), (1.0, 0.25, -0.2), (-0.7, -1.0), 0.5, 0.05),
                                   ((0.1, 0.36, 1.3), (1.0, 0.0, -0.05), (0.2, -1.0), 0.62, 0.055)):
        c0 = np.array([sx * c0[0], c0[1], c0[2]])
        q, nrm = project_many(lion, c0, [(sx * dr[0], dr[1], dr[2])])
        q, nrm = q[0], nrm[0]
        Dm = np.array([0.0, dy, dz])
        Dm = norm(Dm - nrm * (Dm @ nrm))
        region = bolt(q - Dm * 0.04, Dm, nrm, L, w, random_segs(rng, n=3), t_edge=0.12, slope=0.0, r=0.004)
        charge_marks.append(paint(lion, region, d=0.022, depth=0.045, k=0.003))

# cicatrice ricucita sopra l'occhio destro (lato x > 0): taglio scuro + punti a croce
scar_pts = [surf_pt(head, H, hp(*q), 0.004) for q in ((0.1, -0.16, 0.36), (0.22, -0.1, 0.3), (0.32, -0.04, 0.17),
                                                       (0.37, -0.02, 0.02), (0.35, -0.06, -0.13))]
scar_line = resample(catmull(scar_pts, 4), 0.02)
scar = [tube([tuple(q) for q in scar_line], 0.012)]
for q0, q1 in zip(resample(scar_line, 0.075)[:-1], resample(scar_line, 0.075)[1:]):
    c = (np.asarray(q0) + np.asarray(q1)) / 2
    tan = norm(np.asarray(q1) - np.asarray(q0))
    side = norm(np.cross(tan, grad(head, c)))
    a = on_surface(head, c - side * 0.045, 0.004)
    b = on_surface(head, c + side * 0.045, 0.004)
    scar.append(capsule(tuple(a), tuple(b), 0.0125))
m.add("Stitches", fast_union(scar), THREAD, role="detail", tris=500, voxel=0.008)

# collare di piume scure (nube temporalesca) dietro la testa: da qui esplodono i fulmini della criniera
MC = H + HS * np.array([0.0, 0.22, -0.16])
ruff = []
for layer, (n, th0, L0, w, back, dy) in enumerate(((14, 158, 0.66, 0.15, 26, -0.05), (13, 150, 0.56, 0.14, 18, -0.11))):
    for i in range(n):
        th = math.radians(-th0 + 2 * th0 * (i + 0.5 * layer) / (n - 1 + layer))
        R = np.array([math.sin(th), 0.0, math.cos(th)])
        sweep = math.radians(back + 16 * abs(math.degrees(th)) / th0)
        D = norm(R * math.cos(sweep) + np.array([0.0, 1.0, 0.0]) * math.sin(sweep))
        L = (L0 + 0.1 * math.cos(th)) * rng.uniform(0.94, 1.06)
        B = MC + np.array([0.16 * math.sin(th), dy, 0.18 * math.cos(th)])
        Nf = norm(np.array([0.0, -1.0, 0.0]) - D * (-D[1]))
        ruff.append(blade(leaf_outline(L, w, back=0.2, n=5, tip_pow=1.25), B, D, np.cross(Nf, D), t_edge=0.016,
                          slope=0.36))
m.add("Ruff", fast_union(ruff), RUFF, role="detail", tris=2500, voxel=0.014)
m.add("Slate", union(*slate_bits, *brows, *lids_top).intersect(GROUND), SLATE, role="detail", tris=4100, voxel=0.013)
m.add("Talons", fast_union(gold_bits).intersect(GROUND), GOLD, role="detail", tris=2000, voxel=0.011, reflectance=0.12)

# ============================================================ criniera di fulmini (+ ciuffo della coda): parte Neon "Mane"
mane = []
N_M = 22
for i in range(N_M):
    th = math.radians(-166 + 332 * i / (N_M - 1))
    R = np.array([math.sin(th), 0.0, math.cos(th)])
    big = i % 2 == 0
    sweep = math.radians((18 if big else 28) + 24 * abs(math.degrees(th)) / 166)
    D = norm(R * math.cos(sweep) + np.array([0.0, 1.0, 0.0]) * math.sin(sweep))
    B = MC + np.array([0.2 * math.sin(th), 0.07 if big else 0.03, 0.22 * math.cos(th)])
    if big:
        L = (1.02 + 0.62 * math.cos(th * 0.7)) * rng.uniform(0.95, 1.05)
        mane += forked_bolt(B, D, (0.0, -1.0, 0.0), L, rng.uniform(0.135, 0.15), random_segs(rng, n=3),
                            twist=rng.uniform(-12, 12), fork=(rng.uniform(0.38, 0.55), rng.uniform(28, 40), 0.36), rng=rng)
    else:
        L = (0.78 + 0.16 * math.cos(th)) * rng.uniform(0.94, 1.06)
        mane.append(bolt(B, D, (0.0, -1.0, 0.0), L, rng.uniform(0.11, 0.12), random_segs(rng, n=2),
                         twist=rng.uniform(-12, 12)))
# ciuffo di fulmini sulla punta della coda
TT = np.array(TAIL[-1])
TD = norm(np.array(TAIL[-1]) - np.array(TAIL[-3]))
ts1 = norm(np.cross(TD, (0.0, 0.0, 1.0)))
ts2 = np.cross(TD, ts1)
for i in range(7):
    a = 2 * math.pi * i / 7 + 0.3
    D = norm(TD * 1.0 + 0.7 * (math.cos(a) * ts1 + math.sin(a) * ts2))
    mane.append(bolt(TT - TD * 0.06, D, np.cross(D, ts1) + 0.3 * ts2, rng.uniform(0.42, 0.56), 0.085,
                     random_segs(rng, n=2)))
mane.append(bolt(TT - TD * 0.06, TD, ts1, 0.68, 0.1, random_segs(rng, n=2)))
m.add("Mane", fast_union(mane + charge_marks), BOLT, material="Neon", role="glow", tris=8300, voxel=0.012)

# ============================================================ ali enormi alzate (gruppi WingR / WingL)
WS, WE, WW, WH = np.array([0.0, 0.0]), np.array([0.42, 0.36]), np.array([0.82, 1.02]), np.array([1.0, 1.26])


def wfeather(base_xz, ang, L, w, y0, t_edge=0.02, slope=0.28, **kw):
    a = math.radians(ang)
    U = np.array([math.cos(a), 0.0, math.sin(a)])
    V = np.array([-math.sin(a), 0.0, math.cos(a)])
    o = np.array([base_xz[0], y0, base_xz[1]])
    return blade(feather_outline(L, w, **kw), o, U, V, t_edge=t_edge, slope=slope, r=0.006)


def wing_layers(ragged):
    """Strati dell'ala (piano XZ locale): remiganti (y=0), copritrici blu acciaio sopra le loro basi, copritrici
    piccole bianche sopra le basi di quelle blu, bordo d'attacco e alula. Ritorna anche le punte delle remiganti."""
    rem, cov, marg, tips, rows = [], [], [], [], []
    hand_trail = np.array([0.8, -0.6])
    arm_trail = np.array([0.86, -0.52])
    P_LEN = [0.96, 1.02, 1.07, 1.11, 1.14, 1.17, 1.19, 1.15, 1.04]
    for i in range(9):  # primarie (le 5 esterne "a dito" come l'aquila)
        t = i / 8
        base = WW + (WH - WW) * t + hand_trail * 0.04
        ang = 6 + 60 * t ** 0.95
        notches = ((0.56, 1, 0.85, 0.06), (0.7, -1, 0.9, 0.055), (0.82, 1, 0.85, 0.05), (0.91, -1, 0.75, 0.04)) \
            if i in ragged else ()
        rem.append(wfeather(base, ang, P_LEN[i], 0.072, 0.0, finger=(0.5, 0.62) if i >= 4 else None, bend=-0.035,
                            asym=-0.18, notches=notches, n=30 if i in ragged else 14))
        rows.append((base, ang, P_LEN[i], hand_trail, 0.4))
        a = math.radians(ang)
        tips.append((base + P_LEN[i] * np.array([math.cos(a), math.sin(a)]) * (0.9 if i in ragged else 0.97), ang, i))
    for j in range(9):  # secondarie
        t = j / 8
        base = WW + (WE - WW) * t * 0.96 + arm_trail * 0.04
        ang = 2 - 66 * t
        L = 0.97 - 0.17 * t
        rem.append(wfeather(base, ang, L, 0.078, 0.0, asym=-0.1, n=12))
        rows.append((base, ang, L, arm_trail, 0.48))
    for f, ang, L in ((0.25, -72, 0.7), (0.5, -86, 0.62), (0.75, -100, 0.54)):  # terziarie
        base = WE + (WS - WE) * f + np.array([0.3, -0.95]) * 0.03
        rem.append(wfeather(base, ang, L, 0.08, 0.0, n=10))
        rows.append((base, ang, L, np.array([0.3, -0.95]), 0.48))
    for base, ang, L, trail, frac in rows:
        cov += [wfeather(base - trail * 0.02, ang + 2, frac * L, 0.088, sd * 0.036, t_edge=0.026, slope=0.26, n=10)
                for sd in (-1, 1)]
        marg += [wfeather(base - trail * 0.07, ang + 3, 0.21, 0.09, sd * 0.064, slope=0.28, n=8) for sd in (-1, 1)]
    marg.append(tube([(x, 0.0, z) for x, z in (WS, WE, WW, WH)], [0.1, 0.07, 0.055, 0.04]))
    hand = norm(WH - WW)
    hang = math.degrees(math.atan2(hand[1], hand[0]))
    for k, (dl, da) in enumerate(((0.0, 18), (0.05, 10), (0.1, 2))):  # alula
        b = WW + hand * dl
        marg.append(wfeather(b, hang + da, 0.3 - 0.05 * k, 0.06, -0.06, n=8))
    return rem, cov, marg, tips


WING_ROOT = np.array([0.3, 0.1, 1.88])


def place_wing(shape, sx):
    s = shape.rot(-12, 0, 0).rot(0, 0, 28).translate(tuple(WING_ROOT))
    return s if sx > 0 else s.mirrored()


for sx, nm, ragged in ((1, "WingR", (5, 7)), (-1, "WingL", (6,))):
    rem, cov, marg, tips = wing_layers(ragged)
    piv = (float(sx * WING_ROOT[0]), float(WING_ROOT[1]), float(WING_ROOT[2]))
    wb = []
    hand = norm(WH - WW)
    for tip, ang, i in tips:
        if i in ragged or i in (2, 8):
            a = math.radians(ang + rng.uniform(-8, 8))
            wb.append(bolt((tip[0], 0.0, tip[1]), (math.cos(a), 0.0, math.sin(a)), (0.0, -1.0, 0.0),
                           0.5 if i in ragged else 0.42, 0.08, random_segs(rng, n=2), t_edge=0.013, slope=0.4))
    wb.append(bolt((WH[0] - 0.05, 0.0, WH[1] - 0.05), rodrigues(np.array([hand[0], 0.0, hand[1]]), (0, 1, 0), -28),
                   (0.0, -1.0, 0.0), 0.56, 0.085, random_segs(rng, n=2)))
    for t in (0.3, 0.62):  # scariche che saltano dal bordo d'attacco
        q = WE + (WW - WE) * t
        wb.append(bolt((q[0] - 0.02, 0.0, q[1] + 0.02), (-0.5, 0.0, 0.87), (0.0, -1.0, 0.0), 0.34, 0.07,
                       random_segs(rng, n=2)))
    m.add(nm, place_wing(fast_union(rem), sx), REMIGE, role="detail", tris=3400, voxel=0.013, group=nm, pivot=piv)
    m.add(nm + "Covert", place_wing(fast_union(cov), sx), STEEL, role="detail", tris=2300, voxel=0.013, group=nm, pivot=piv)
    m.add(nm + "Marginal", place_wing(fast_union(marg), sx), STORM, role="detail", tris=1600, voxel=0.013, group=nm,
          pivot=piv)
    m.add("WingBolts" + nm[-1], place_wing(fast_union(wb), sx), BOLT, material="Neon", role="glow", tris=900,
          voxel=0.011, group=nm, pivot=piv)

# ============================================================ scala globale: altezza ~3.9 unita' (il gioco la riscala)
SCALE = 0.87
for part in m.parts:
    part.sdf = part.sdf.scale(SCALE)
    part.voxel = part.voxel * SCALE if part.voxel else None
    if part.pivot is not None:
        part.pivot = tuple(float(c * SCALE) for c in part.pivot)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
