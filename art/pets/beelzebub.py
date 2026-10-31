"""Belzebu' (Beelzebub) - ricompensa del Sentiero Estremo (demoni biblici).

Il Signore delle Mosche: un re-mosca demoniaco ritto sulle zampe, tozzo e corazzato, con le spalle curve e la
testa inclinata da sovrano annoiato. Due enormi occhi composti rosso rubino a faccette (parte "Eyes", facce piatte
come un gioiello tagliato: celle di Voronoi sulla cupola) occupano quasi tutta la testa; sotto, sul muso
sporgente, un ghigno pieno di denti aguzzi fra due mandibole uncinate, e due antenne piumate in mezzo agli occhi.
In testa una corona d'oro storta, scivolata di lato, con le punte a sfera e tre gemme velenose (parte Neon
"GemGlow"). Corpo di chitina blu notte metallizzata come una mosca carnaria: torace massiccio con spallacci neri
chiodati e piastra a punta con nervatura d'oro, addome ad anelli segnati da bordini neri, zampe da insetto sottili
e irte di setole con artigli neri, e un terzo paio di braccine ripiegate sotto il petto. Con la mano sinistra
stringe un piccolo scettro d'oro con una sfera di veleno in una gabbia d'artigli (parte Neon "Venom": il gioco ci
attacca le gocce verdi), la destra e' alzata con gli artigli aperti. Sulle spalle un mantello regale cremisi
strappato e bucato, bordato d'oro e chiuso da una catenella, con l'alto colletto a ventaglio dietro la testa;
dalla schiena escono due grandi ali da mosca trasparenti, venate e sbrindellate (gruppi "WingR"/"WingL": il gioco
le fa vibrare). Attorno gli ronza uno sciame di mosche su tre orbite inclinate (parte Neon "Shadow": il gioco ci
attacca il fumo viola).

Tocco "toy horror": la corona storta, il ghigno di denti aguzzi e una toppa viola ricucita a punti incrociati
sulla pancia.
"""
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.mesher import mesh_sdf  # noqa: E402
from lib.sdf import (SDF, bezier, capsule, cylinder, ellipsoid, euler, halfspace_z, prism, project,  # noqa: E402
                     round_cone, smax, smin, sphere, torus, tube, union)
from lib.toy import Model  # noqa: E402

DRAFT = os.environ.get("DRAFT", "") == "1"
VX = 1.35 if DRAFT else 1.0  # bozza: voxel piu' grossi per iterare in fretta
rng = np.random.default_rng(1666)
T0 = time.time()


def log(msg):
    print(f"[beelzebub {time.time() - T0:6.1f}s] {msg}", flush=True)


# ============================================================ helper (lib/ non si modifica: copiati/adattati qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def mix(a, b, t):
    return np.asarray(a, dtype=np.float64) * (1 - t) + np.asarray(b, dtype=np.float64) * t


def grad(sdf, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float64)
    g = np.array([sdf((p + e)[None, :].astype(np.float32))[0] - sdf((p - e)[None, :].astype(np.float32))[0]
                  for e in np.eye(3) * eps])
    return g / max(np.linalg.norm(g), 1e-9)


def grad_many(sdf, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float64).reshape(-1, 3)
    g = np.zeros_like(p)
    for ax in range(3):
        e = np.zeros(3)
        e[ax] = eps
        g[:, ax] = sdf((p + e).astype(np.float32)) - sdf((p - e).astype(np.float32))
    return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)


def project_many(sdf, origins, dirs, max_dist=2.5, steps=300, iters=24):
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
        log(f"attenzione: {len(bad)} raggi partono fuori dalla forma, es. {np.round(o[bad[0]], 3)}")
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


def on_surface(sdf, p, lift=0.0, iters=4):
    """Porta p sulla superficie (a distanza 'lift' verso l'esterno) seguendo il gradiente."""
    p = np.asarray(p, dtype=np.float64)
    for _ in range(iters):
        d = float(sdf(p[None, :].astype(np.float32))[0])
        p = p - grad(sdf, p) * (d - lift)
    return p


def fast_union(shapes, k=0.0, base=None, margin=0.06):
    """Unione di tante forme, ognuna valutata solo vicino al proprio ingombro."""
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


def paint(core, region, out=0.016, inn=0.035, margin=0.05, k=0.0):
    """Strato di "vernice" (guscio fra -inn e +out attorno a core) dentro 'region'; core valutato solo vicino."""
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


def flatten(shape, s, axis=1):
    """Schiaccia (s<1) una forma lungo un asse locale, con distanza conservativa."""
    def f(p):
        q = p.copy()
        q[:, axis] = q[:, axis] / s
        return shape(q) * min(s, 1.0)

    lo, hi = shape.lo.copy(), shape.hi.copy()
    lo[axis] *= s
    hi[axis] *= s
    return SDF(f, lo, hi)


def thin(shape, out, inn):
    """Guscio sottile di una forma (per disegni sopra altre parti)."""
    return SDF(lambda p: (lambda d: np.maximum(d - out, -(d + inn)))(shape(p)), shape.lo - out, shape.hi + out)


def frame(z_dir, y_hint):
    """Matrice di rotazione (colonne x, y, z) con z = z_dir e y il piu' vicino possibile a y_hint."""
    z = norm(z_dir)
    y = np.asarray(y_hint, dtype=np.float64)
    y = y - z * np.dot(y, z)
    if np.linalg.norm(y) < 1e-6:
        y = np.array([0.0, 0.0, 1.0]) - z * z[2]
    y = norm(y)
    return np.stack([np.cross(y, z), y, z], axis=1).astype(np.float32)


def ell(c, radii, axis=(0, 0, 1), side=(1, 0, 0)):
    """Ellissoide con il terzo raggio lungo 'axis' (il primo il piu' possibile verso 'side')."""
    z = norm(axis)
    x = np.asarray(side, dtype=np.float64)
    x = x - z * float(np.dot(x, z))
    if np.linalg.norm(x) < 1e-6:
        x = np.array([0.0, 1.0, 0.0]) - z * z[1]
    x = norm(x)
    M = np.stack([x, np.cross(z, x), z], axis=1).astype(np.float32)
    return ellipsoid(radii).rotate(M).translate(tuple(np.asarray(c, dtype=np.float64)))


def taper(n, r0, r1, power=1.0):
    return [r0 + (r1 - r0) * (i / (n - 1)) ** power for i in range(n)]


def horn(p0, p1, p2, p3, r0, r1, n=12, power=0.9):
    """Corno/artiglio affusolato lungo una bezier."""
    return tube(bezier(p0, p1, p2, p3, n), taper(n + 1, r0, r1, power))


def tbox(y_back, y_front, w_back, w_front, top_back, top_front, bot_back, bot_front, r):
    """Scatola arrotondata che si restringe da y_back a y_front (muso e mandibola squadrati)."""
    cy, hy = (y_back + y_front) / 2, abs(y_back - y_front) / 2

    def f(p):
        t = np.clip((p[:, 1] - y_back) / (y_front - y_back), 0.0, 1.0)
        w = w_back + (w_front - w_back) * t
        top = top_back + (top_front - top_back) * t
        bot = bot_back + (bot_front - bot_back) * t
        qx = np.abs(p[:, 0]) - (w - r)
        qy = np.abs(p[:, 1] - cy) - (hy - r)
        qz = np.abs(p[:, 2] - (top + bot) / 2) - ((top - bot) / 2 - r)
        qm = np.maximum(np.maximum(qx, qy), qz)
        o = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2 + np.maximum(qz, 0) ** 2)
        return (o + np.minimum(qm, 0) - r).astype(np.float32)

    w = max(w_back, w_front)
    return SDF(f, (-w, min(y_back, y_front), min(bot_back, bot_front)), (w, max(y_back, y_front), max(top_back, top_front)))


def band(R, t, h, rr=0.014):
    """Fascia (anello a sezione rettangolare arrotondata) nel piano XY: raggio R, spessore 2t, altezza 2h."""
    def f(p):
        rho = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2) - R
        qx = np.abs(rho) - (t - rr)
        qz = np.abs(p[:, 2]) - (h - rr)
        return np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qz, 0) ** 2) + np.minimum(np.maximum(qx, qz), 0) - rr

    e = R + t
    return SDF(f, (-e, -e, -h), (e, e, h))


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


def flame(L, r0, bend=0.6, wig=0.06, flat=0.62, n=12, fork=0.0):
    """Lingua di fuoco (locale: base nell'origine, sale lungo +Z e si piega verso +Y, piatta lungo X)."""
    pts = bezier((0, 0, -0.04), (wig, 0.0, L * 0.38), (-wig, bend * L * 0.3, L * 0.72), (wig * 0.5, bend * L, L), n)
    ts = np.linspace(0.0, 1.0, n + 1)
    radii = [r0 * (1.0 + 0.3 * math.sin(math.pi * min(t * 1.7, 1.0))) * (1.0 - t) ** 0.85 + 0.02 for t in ts]
    shape = tube(pts, radii)
    if fork:
        q = np.asarray(pts[int(n * 0.32)])
        side = bezier(tuple(q), tuple(q + (0, L * 0.12, L * 0.12)), tuple(q + (-wig, L * 0.32, L * 0.22)),
                      tuple(q + (0, L * fork, L * 0.36)), 6)
        shape = union(shape, tube(side, taper(7, r0 * 0.62, 0.02, 0.9)), k=0.03)
    return flatten(shape, flat, axis=0)


def zigzag(a, b, n, amp, normal_hint):
    """Linea spezzata da a a b con n segmenti e scarti laterali alternati (per crepe frastagliate)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    side = norm(np.cross(b - a, normal_hint))
    pts = []
    for j in range(n + 1):
        t = j / n
        off = 0.0 if j in (0, n) else (1 if j % 2 else -1) * amp * rng.uniform(0.5, 1.0)
        pts.append(a + (b - a) * t + side * off)
    return pts


def poisson_pick(points, spacing, seed=0):
    """Sottoinsieme di punti a distanza >= spacing l'uno dall'altro (scelta greedy in ordine casuale)."""
    order = np.random.default_rng(seed).permutation(len(points))
    inv = 1.0 / spacing
    s2 = spacing * spacing
    grid = defaultdict(list)
    acc = []
    for i in order:
        p = points[i]
        key = (int(math.floor(p[0] * inv)), int(math.floor(p[1] * inv)), int(math.floor(p[2] * inv)))
        ok = True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        q = points[j]
                        if (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 + (q[2] - p[2]) ** 2 < s2:
                            ok = False
                            break
                    if not ok:
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            acc.append(i)
            grid[key].append(i)
    return np.array(acc, dtype=np.int64)


def fit_voxels(model, fill=7.3):
    """Sceglie per ogni parte il voxel piu' fine che resta sotto il limite di facce di toy.build (tris x 8).

    toy.build, se la mesh e' troppo densa, rimesha puntando a tris x 5 (piu' grossolano del necessario)."""
    for part in model.parts:
        _, f, _ = mesh_sdf(part.sdf, part.voxel)
        if len(f) > part.tris * 7.8:
            part.voxel = part.voxel * math.sqrt(len(f) / (part.tris * fill))
            log(f"{part.name}: voxel {part.voxel:.4f} ({len(f)} facce per {part.tris} tris)")


class Voronoi:
    """Celle di Voronoi di semi sparsi sulla superficie: distanza (con segno) dal bordo della cella piu' vicina."""

    def __init__(self, seeds, k=7):
        self.S = np.asarray(seeds, dtype=np.float32)
        self.tree = cKDTree(self.S)
        self.k = min(k, len(self.S))

    def query(self, p, mask=None):
        """Ritorna (indice del seme piu' vicino, distanza dal bordo della cella, distanza dal bordo con una cella
        di tipo diverso secondo 'mask')."""
        _, idx = self.tree.query(p, k=self.k)
        i0 = idx[:, 0]
        s0 = self.S[i0]
        pp0 = np.einsum("ij,ij->i", p - s0, p - s0)
        e = np.full(len(p), 9.0, dtype=np.float32)
        ed = np.full(len(p), 9.0, dtype=np.float32)
        m0 = mask[i0] if mask is not None else None
        for j in range(1, self.k):
            ij = idx[:, j]
            sj = self.S[ij]
            num = np.einsum("ij,ij->i", p - sj, p - sj) - pp0
            den = 2.0 * np.linalg.norm(sj - s0, axis=1)
            t = num / np.maximum(den, 1e-6)
            e = np.minimum(e, t)
            if mask is not None:
                ed = np.where(mask[ij] != m0, np.minimum(ed, t), ed)
        return i0, e, ed


def catmull(points, n_per=6):
    """Spline di Catmull-Rom che passa per tutti i punti."""
    P = [np.asarray(q, dtype=np.float64) for q in points]
    P = [P[0] + (P[0] - P[1])] + P + [P[-1] + (P[-1] - P[-2])]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n_per, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-2])
    return np.array(out)


def look(fwd, up=(0, 0, 1)):
    """Matrice con colonne (destra, avanti, su): l'asse Y locale va su 'fwd'."""
    f = norm(fwd)
    r = np.cross(f, np.asarray(up, dtype=np.float64))
    if np.linalg.norm(r) < 1e-6:
        r = np.array([1.0, 0.0, 0.0])
    r = norm(r)
    u = np.cross(r, f)
    return np.stack([r, f, u], axis=1).astype(np.float32)


def fib_sphere(n):
    """n direzioni quasi uniformi sulla sfera (spirale di Fibonacci)."""
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5 ** 0.5) * i
    return np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], axis=1)


# ============================================================ colori
CHITIN = (34, 46, 72)       # chitina blu notte metallizzata (mosca carnaria)
ARMOR = (24, 26, 34)        # placche nere lucide
GOLD = (240, 184, 62)
CAPE = (138, 16, 40)        # mantello cremisi
EYE_RED = (200, 20, 32)     # occhi composti rosso rubino
WING = (198, 192, 224)
VEIN = (52, 34, 44)
FLY = (108, 46, 184)        # sciame (Neon viola scuro)
GEM = (150, 255, 70)        # gemme velenose (Neon)
MOUTH = (34, 8, 18)
TOOTH = (250, 244, 228)
CLAW = (28, 22, 28)
PATCH = (104, 62, 156)
THREAD = (242, 226, 184)

m = Model("Beelzebub", "pet")

# ============================================================ testa (spazio locale: faccia verso -Y)
HEAD_T = np.array([0.0, -0.24, 2.55], dtype=np.float32)
HS = 1.32
R_HEAD = euler(-4.0, 9.0, 11.0)     # appena alzata, inclinata di lato e girata verso chi guarda


def Hd(shape):
    return shape.scale(HS).rotate(R_HEAD).translate(HEAD_T)


def hp(p):
    return R_HEAD @ (HS * np.asarray(p, dtype=np.float32)) + HEAD_T


def hv(v):
    return R_HEAD @ np.asarray(v, dtype=np.float32)


head_core = ellipsoid((0.26, 0.27, 0.3), (0, 0.05, 0.03))
frons = ellipsoid((0.1, 0.12, 0.22), (0, -0.2, 0.02))
muzzle = ellipsoid((0.18, 0.17, 0.15), (0, -0.25, -0.24))                # muso sporgente sotto gli occhi: il ghigno
jowls = [ellipsoid((0.09, 0.11, 0.1), (sx * 0.12, -0.19, -0.24)) for sx in (1, -1)]
head = union(head_core, frons, k=0.1)
head = union(head, muzzle, *jowls, k=0.08)

# ghigno: mezzaluna scavata nella faccia bassa (piu' alta agli angoli), con due file di denti aguzzi
GRIN_W = 0.155


def grin_lines(x):
    """Quote (locali) del labbro di sopra e di sotto alla larghezza x."""
    t = np.clip(np.abs(x) / GRIN_W, 0, 1)
    top = -0.215 + 0.05 * t ** 2
    bot = -0.295 + 0.085 * t ** 2.2
    return top, bot


def grin_f(p):
    top, bot = grin_lines(p[:, 0])
    mid, half = (top + bot) / 2, np.maximum((top - bot) / 2, 1e-3)
    dz = np.abs(p[:, 2] - mid) - half
    dx = np.abs(p[:, 0]) - GRIN_W
    return np.maximum(np.maximum(dz, dx), p[:, 1] + 0.33).astype(np.float32)


grin_reg = SDF(grin_f, (-GRIN_W - 0.01, -0.6, -0.34), (GRIN_W + 0.01, -0.3, -0.12))
head = head.subtract(grin_reg, k=0.015)
mouth_dark = thin(head, 0.004, 0.03).intersect(grin_reg.offset(0.012))
teeth = []
for row, sgn in (("top", -1.0), ("bot", 1.0)):
    xs = np.linspace(-GRIN_W * 0.88, GRIN_W * 0.88, 9 if row == "top" else 8)
    for x in xs:
        top, bot = grin_lines(np.array([x]))
        z0 = float(top[0] if row == "top" else bot[0]) - sgn * 0.004
        p, n = project(head, (x * 0.9, -0.22, z0 - sgn * 0.02), (0, -1, 0))
        b = p - np.array([0, -0.012, 0]) - n * 0.01
        L = 0.055 + 0.02 * (1 - abs(x) / GRIN_W)
        teeth.append(round_cone(tuple(b), tuple(b + np.array([0, -0.01, sgn * L])), 0.021, 0.004))
    lip = [project(head, (x * 0.9, -0.22, float((grin_lines(np.array([x]))[0] if row == "top" else grin_lines(np.array([x]))[1])[0])
                          - sgn * 0.012), (0, -1, 0))[0] for x in np.linspace(-GRIN_W * 0.92, GRIN_W * 0.92, 7)]
    teeth.append(tube([tuple(q + np.array([0, 0.008, 0])) for q in lip], 0.014))

# occhi composti: due enormi cupole a faccette esagonali (celle di Voronoi), solo la meta' esterna
EYE_C = {sx: np.array([sx * 0.25, -0.07, 0.05]) for sx in (1, -1)}
EYE_R = np.array([0.285, 0.275, 0.315])
EYE_OUT = {sx: norm((sx * 0.8, -0.58, 0.14)) for sx in (1, -1)}
eye_parts, eye_shine = [], []
dirs = fib_sphere(96)
for sx in (1, -1):
    c = EYE_C[sx]
    seeds = c + dirs * EYE_R                                   # semi sulla superficie dell'ellissoide
    nrm = np.array([norm(d / EYE_R) for d in dirs])            # normali dell'ellissoide
    keep = (dirs @ EYE_OUT[sx]) > -0.45
    seeds, nrm = seeds[keep].astype(np.float32), nrm[keep].astype(np.float32)
    tree = cKDTree(seeds)
    ell_e = ellipsoid(tuple(EYE_R), tuple(c))

    def facets(p, seeds=seeds, nrm=nrm, tree=tree, ell_e=ell_e):
        _, idx = tree.query(p, k=5)
        d = np.full(len(p), -9.0, dtype=np.float32)
        for j in range(5):
            s, n = seeds[idx[:, j]], nrm[idx[:, j]]
            d = np.maximum(d, np.einsum("ij,ij->i", p - s, n) - 0.012)
        return np.maximum(d, ell_e(p) - 0.03)

    cut_n = EYE_OUT[sx].astype(np.float32)
    cut = SDF(lambda p, c=c, n=cut_n: (0.06 - (p - c) @ n).astype(np.float32), c - 0.4, c + 0.4)
    eye_parts.append(SDF(facets, c - EYE_R - 0.05, c + EYE_R + 0.05).intersect(cut))
    # riflessi: una macchia grande e una piccola in alto davanti
    for d_, r_ in ((norm((sx * 0.35, -0.75, 0.55)), (0.06, 0.03, 0.045)), (norm((sx * 0.6, -0.6, 0.38)), (0.03, 0.018, 0.025))):
        q = c + d_ * EYE_R * 1.03
        eye_shine.append(ellipsoid(r_).rotate(look(-d_ * np.array([1, 1, 1]))).translate(tuple(q)))

# antenne corte con il pennacchio di setole
antennae = []
for sx in (1, -1):
    a0 = np.array([sx * 0.045, -0.27, 0.15])
    pts = bezier(tuple(a0), tuple(a0 + (sx * 0.02, -0.07, 0.07)), tuple(a0 + (sx * 0.08, -0.12, 0.13)),
                 tuple(a0 + (sx * 0.14, -0.13, 0.2)), 6)
    antennae.append(tube(pts, taper(7, 0.026, 0.016)))
    tip = np.array(pts[-1])
    for k in range(5):
        d = norm((sx * 0.5 + 0.25 * (k - 2), -0.3, 1.0 - 0.1 * abs(k - 2)))
        antennae.append(round_cone(tuple(tip), tuple(tip + d * 0.09), 0.012, 0.004))
    antennae.append(sphere(0.03, tuple(tip)))

# mandibole uncinate agli angoli della bocca
mandibles = []
for sx in (1, -1):
    b = np.array([sx * 0.2, -0.17, -0.25])
    mandibles.append(horn(tuple(b), tuple(b + (sx * 0.06, -0.08, -0.04)), tuple(b + (sx * 0.02, -0.18, -0.12)),
                          tuple(b + (-sx * 0.07, -0.2, -0.2)), 0.045, 0.01, n=10))
    for t_ in (0.35, 0.6):   # dentelli sul bordo interno
        q = np.array(bezier(tuple(b), tuple(b + (sx * 0.06, -0.08, -0.04)), tuple(b + (sx * 0.02, -0.18, -0.12)),
                            tuple(b + (-sx * 0.07, -0.2, -0.2)), 10)[int(t_ * 10)])
        mandibles.append(round_cone(tuple(q), tuple(q + np.array([-sx * 0.045, -0.01, 0.0])), 0.016, 0.004))

# corona d'oro storta (spazio locale della corona: anello attorno a Z)
crown_l, gems_l = [], []
CR = 0.17
crown_l.append(band(CR, 0.024, 0.042))
crown_l.append(torus(CR, 0.018).translate((0, 0, -0.04)))
for k in range(5):
    a = math.radians(-90 + 72 * k)
    d = np.array([math.cos(a), math.sin(a), 0.0])
    tall = 0.26 if k == 0 else (0.2 if k in (1, 4) else 0.16)
    b = d * CR + np.array([0, 0, 0.03])
    tip = d * (CR + 0.03) + np.array([0, 0, tall])
    crown_l.append(round_cone(tuple(b), tuple(tip), 0.045, 0.012))
    crown_l.append(sphere(0.024, tuple(tip + np.array([0, 0, 0.012]))))
for a_deg, r in ((-90, 0.03), (-50, 0.022), (-130, 0.022)):
    a = math.radians(a_deg)
    gems_l.append(sphere(r, (math.cos(a) * (CR + 0.026), math.sin(a) * (CR + 0.026), 0.0)))
CROWN_M = euler(10.0, 24.0, 0.0)
CROWN_T = np.array([-0.03, 0.05, 0.34])


def Cr(shape):
    return Hd(shape.rotate(CROWN_M).translate(tuple(CROWN_T)))


# ============================================================ corpo (spazio Blender)
seg = []
for z, (rx, ry, rz) in ((0.66, (0.38, 0.35, 0.16)), (0.85, (0.48, 0.44, 0.18)), (1.04, (0.53, 0.48, 0.19)),
                        (1.22, (0.51, 0.46, 0.18)), (1.38, (0.44, 0.4, 0.15))):
    seg.append(ellipsoid((rx, ry, rz), (0, 0.08, z)))
abdomen = union(*seg, k=0.035)
thorax = ellipsoid((0.58, 0.45, 0.42), (0, -0.0, 1.82))
shoulders = [ellipsoid((0.28, 0.28, 0.28), (sx * 0.52, 0.04, 1.96)) for sx in (1, -1)]
neck = round_cone((0, 0.02, 2.0), tuple(hp((0, 0.08, -0.12))), 0.2, 0.15)
torso = union(abdomen, thorax, k=0.07)
torso = union(torso, *shoulders, neck, k=0.12)

# zampe da insetto (ginocchio avanti, caviglia indietro) con tre dita artigliate
LEGS = {sx: dict(hip=np.array([sx * 0.26, 0.1, 0.72]), knee=np.array([sx * 0.47, -0.16, 0.5]),
                 ankle=np.array([sx * 0.43, 0.15, 0.2]), foot=np.array([sx * 0.44, 0.02, 0.07])) for sx in (1, -1)}
leg_parts, TOE_TIPS, KNOBS = [], [], []
for sx, L in LEGS.items():
    leg_parts += [round_cone(L["hip"], L["knee"], 0.16, 0.1),
                  ell(mix(L["hip"], L["knee"], 0.4), (0.13, 0.13, 0.18), axis=L["knee"] - L["hip"]),
                  round_cone(L["knee"], L["ankle"], 0.095, 0.065),
                  round_cone(L["ankle"], L["foot"], 0.065, 0.07),
                  ellipsoid((0.11, 0.14, 0.06), tuple(L["foot"] + np.array([0, -0.04, -0.01])))]
    KNOBS += [(L["knee"], 0.115), (L["ankle"], 0.085)]
    for dx in (-0.075, 0.0, 0.075):
        a = L["foot"] + np.array([dx, -0.06, 0.0])
        tip = L["foot"] + np.array([dx * 1.8, -0.26 + 0.6 * abs(dx), -0.025])
        leg_parts.append(round_cone(tuple(a), tuple(tip), 0.045, 0.036))
        TOE_TIPS.append((tip, norm(tip - a)))

# braccia: la sinistra (+X) stringe lo scettro, la destra (-X) e' alzata con gli artigli aperti
SC_B = np.array([0.86, -0.4, 0.98])                  # fondo dello scettro
SC_U = norm((-0.22, -0.3, 1.0))                      # asse dello scettro (verso la punta)
SC_L = 1.14
GRIP = SC_B + SC_U * 0.36
ARMS = {1: (np.array([0.6, 0.0, 1.92]), np.array([0.9, 0.04, 1.46]), GRIP + np.array([0.06, 0.1, -0.02])),
        -1: (np.array([-0.6, 0.0, 1.92]), np.array([-1.0, 0.04, 1.66]), np.array([-1.1, -0.22, 2.02]))}
arm_parts, CLAW_ROOTS = [], []
for sx, (sh, el, wr) in ARMS.items():
    arm_parts += [round_cone(sh, el, 0.17, 0.13),
                  ell(mix(sh, el, 0.45), (0.15, 0.15, 0.2), axis=el - sh),
                  round_cone(el, wr, 0.13, 0.1),
                  ell(mix(el, wr, 0.35), (0.12, 0.12, 0.17), axis=wr - el)]
# pugno attorno allo scettro (+X)
side = norm(np.cross(SC_U, (0, -1, 0)))
fist_c = GRIP + side * 0.0
arm_parts.append(ell(fist_c + np.array([0.02, 0.03, 0.0]), (0.12, 0.105, 0.11), axis=SC_U))
for k, t in enumerate((-0.07, 0.0, 0.07)):     # nocche e artigli che avvolgono l'asta sul davanti
    q = GRIP + SC_U * t
    fwd = norm(np.cross(SC_U, side)) if np.cross(SC_U, side)[1] < 0 else -norm(np.cross(SC_U, side))
    arm_parts.append(sphere(0.045, tuple(q + side * 0.08 + fwd * 0.03)))
    CLAW_ROOTS.append((q + side * 0.07 + fwd * 0.07, norm(-side * 0.8 + fwd * 0.6), 0.1, fwd))
# mano aperta (-X): palmo verso chi guarda, tre dita lunghe aperte a ventaglio e il pollice
sh, el, wr = ARMS[-1]
U = norm(wr - el + np.array([0, 0, 0.25]))
Fp = norm(np.array([0.15, -1.0, 0.0]) - U * float(np.dot((0.15, -1.0, 0.0), U)))
S = norm(np.cross(Fp, U))
palm = wr + U * 0.1
arm_parts.append(ell(palm, (0.12, 0.07, 0.12), axis=U, side=S))
for a_deg in (-35, -5, 25, 80):
    ar = math.radians(a_deg)
    dk = norm(U * math.cos(ar) + S * math.sin(ar))
    ln = 0.2 if a_deg != 80 else 0.13
    b0 = palm + dk * 0.08
    b1 = b0 + dk * ln + Fp * 0.05
    arm_parts.append(round_cone(tuple(b0), tuple(b1), 0.05, 0.042))
    CLAW_ROOTS.append((b1, norm(dk + Fp * 0.5), 0.13 if a_deg != 80 else 0.1, Fp))

# terzo paio di zampe: due braccine da insetto ripiegate sotto il petto, con gli artigli che si toccano
mini = []
for sx in (1, -1):
    a = np.array([sx * 0.42, -0.2, 1.58])
    b = np.array([sx * 0.5, -0.44, 1.4])
    c = np.array([sx * 0.16, -0.56, 1.36])
    mini += [round_cone(tuple(a), tuple(b), 0.06, 0.045), round_cone(tuple(b), tuple(c), 0.045, 0.035),
             sphere(0.06, tuple(b))]
    for dz in (0.03, -0.03):
        CLAW_ROOTS.append((c + np.array([0, 0, dz]), norm(np.array([-sx * 1.0, -0.4, dz * 4])), 0.09, np.array([0, -1.0, 0])))
    KNOBS.append((b, 0.07))

core0 = union(torso, union(*leg_parts, k=0.06), k=0.08)
core0 = union(core0, union(*arm_parts, k=0.05), k=0.07)
core0 = fast_union(mini, k=0.03, base=core0)
core0 = shrink(core0.intersect(halfspace_z(0.0)))
head_w = Hd(head)
core = shrink(fast_union([head_w], k=0.06, base=core0))
log("corpo pronto")

# ============================================================ corazza nera: spallacci chiodati e piastra sul petto
armor, spikes, gold = [], [], []
for sx in (1, -1):
    c = np.array([sx * 0.56, 0.02, 1.98])
    n = norm((sx * 0.75, 0.0, 0.66))
    dome = ellipsoid((0.3, 0.32, 0.27), tuple(c)).shell(0.03).intersect(
        SDF(lambda p, c=c, n=n.astype(np.float32): (0.02 - (p - c) @ n).astype(np.float32), c - 0.4, c + 0.4))
    armor.append(dome)
    gold.append(torus(0.25, 0.02).rotate(frame(n, (0, 1, 0))).translate(tuple(c + n * 0.06)))   # bordo d'oro
    for dz, dy, L in ((0.0, 0.0, 0.26), (-0.06, -0.18, 0.18), (-0.06, 0.18, 0.18)):
        d = norm(n + np.array([sx * 0.0, dy * 2.2, dz]))
        b = c + d * 0.26
        spikes.append(round_cone(tuple(b - d * 0.04), tuple(b + d * L), 0.055, 0.01))


def chest_reg(p):
    """Piastra sul petto: scudo a punta che scende dalle clavicole sulla parte alta del torace."""
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    lo = 1.5 + 0.55 * np.abs(x) / 0.5
    return np.maximum.reduce([lo - z, z - 2.06, np.abs(x) - 0.52, y - 0.05]).astype(np.float32)


breast = paint(core0, SDF(chest_reg, (-0.6, -0.6, 1.45), (0.6, 0.1, 2.1)), out=0.045, inn=0.03, k=0.02)
armor.append(breast)
# nervatura centrale d'oro sulla piastra e bordo alto a collare
rib_t = [np.array([0.0, -0.8, z]) for z in np.linspace(1.56, 2.0, 7)]
rp, rn = project_many(core0, [(0, 0.0, 1.78)] * len(rib_t), [t - np.array([0, 0.0, 1.78]) for t in rib_t])
gold.append(tube([tuple(p_ + n_ * 0.05) for p_, n_ in zip(rp, rn)], [0.02, 0.026, 0.03, 0.032, 0.03, 0.026, 0.022]))
for sx in (1, -1):
    v_t = [np.array([sx * x, -0.8, 1.52 + 0.55 * x / 0.5 + 0.02]) for x in np.linspace(0.04, 0.48, 7)]
    vp, vn = project_many(core0, [(0, 0.0, 1.78)] * len(v_t), [t - np.array([0, 0.0, 1.78]) for t in v_t])
    gold.append(tube([tuple(p_ + n_ * 0.045) for p_, n_ in zip(vp, vn)], 0.022))
gold.append(sphere(0.06, tuple(rp[1] + rn[1] * 0.06)))

# segmenti in rilievo sull'addome: bordini neri nelle pieghe fra un anello e l'altro


def oval_ring(z, rx, ry, cy, r):
    """Anello a sezione circolare (raggio r) lungo l'ellisse (rx, ry) alla quota z."""
    def f(p):
        q = np.sqrt((p[:, 0] / rx) ** 2 + ((p[:, 1] - cy) / ry) ** 2)
        return (np.sqrt(((q - 1.0) * min(rx, ry)) ** 2 + (p[:, 2] - z) ** 2) - r).astype(np.float32)
    return SDF(f, (-rx - r, cy - ry - r, z - r), (rx + r, cy + ry + r, z + r))


for z in (0.755, 0.945, 1.13, 1.3):
    x_hit = project(abdomen, (0, 0.08, z), (1, 0, 0))[0][0]
    y_hit = project(abdomen, (0, 0.08, z), (0, -1, 0))[0][1]
    armor.append(oval_ring(z, x_hit + 0.005, 0.08 - y_hit + 0.005, 0.08, 0.026))

# ============================================================ scettro d'oro con la sfera velenosa in una gabbia d'artigli
SC_T = SC_B + SC_U * SC_L
rod = capsule(tuple(SC_B), tuple(SC_T - SC_U * 0.08), 0.03)
Msc = frame(SC_U, (0, -1, 0))
gold += [rod, sphere(0.05, tuple(SC_B))]
for t in (0.2, 0.52, 0.86):
    gold.append(band(0.042, 0.016, 0.02).rotate(Msc).translate(tuple(SC_B + SC_U * t)))
ORB_C = SC_T + SC_U * 0.06
cup = ellipsoid((0.085, 0.085, 0.05)).intersect(halfspace_z(0.0, above=False)).rotate(Msc).translate(tuple(SC_T - SC_U * 0.02))
gold.append(cup)
for k in range(4):   # artigli d'oro che stringono la sfera
    a = math.radians(45 + 90 * k)
    d = Msc @ np.array([math.cos(a), math.sin(a), 0.0], dtype=np.float32)
    b0 = SC_T - SC_U * 0.01 + d * 0.06
    gold.append(horn(tuple(b0), tuple(b0 + d * 0.07 + SC_U * 0.06), tuple(b0 + d * 0.05 + SC_U * 0.16),
                     tuple(ORB_C + SC_U * 0.12 + d * 0.012), 0.02, 0.008, n=8))
gold.append(sphere(0.026, tuple(ORB_C + SC_U * 0.14)))
gems = [sphere(0.1, tuple(ORB_C))]

# ============================================================ mantello cremisi strappato e colletto a ventaglio
Z_TOP, Z_BOT = 1.96, 0.1
srng = np.random.default_rng(21)
TATTER = srng.uniform(-0.04, 0.04, 40)


def cape_geom(x, z):
    """Superficie del mantello y = Y(x, z) dietro il corpo (si avvolge in avanti ai lati)."""
    u = np.clip((Z_TOP - z) / (Z_TOP - Z_BOT), 0, 1)
    yc = 0.5 + 0.24 * u
    k = 0.72 - 0.3 * u
    return yc - k * x * x, u


def cape_f(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    Y, u = cape_geom(x, z)
    dYdx = -2 * (0.72 - 0.3 * u) * x
    d_sheet = (np.abs(y - Y) - 0.034) / np.sqrt(1 + dYdx ** 2 + 0.08)
    W = 0.6 + 0.32 * u
    # orlo in basso sbrindellato: punte a zig-zag di altezza irregolare
    ph = (x + 1.0) * 7.0
    tri = np.abs(ph - np.floor(ph) - 0.5) * 2
    jit = TATTER[np.clip(np.floor(ph).astype(int), 0, len(TATTER) - 1)]
    zb = Z_BOT + 0.2 * tri + jit + 0.08 * (np.abs(x) / 0.9) ** 2
    d_out = np.maximum.reduce([np.abs(x) - W, zb - z, z - Z_TOP])
    return np.maximum(d_sheet, d_out * 0.8).astype(np.float32)


cape = SDF(cape_f, (-0.95, 0.0, 0.0), (0.95, 0.85, Z_TOP + 0.05))
holes = [sphere(r, tuple(np.array([x, cape_geom(np.array([x]), np.array([z]))[0][0], z]))) for x, z, r in
         ((0.42, 0.62, 0.07), (-0.3, 0.42, 0.06), (0.1, 0.9, 0.05), (-0.55, 1.05, 0.045), (0.64, 0.3, 0.05))]
cape = cape.subtract(union(*holes))
ZC0, ZC1 = 1.9, 2.8


def collar_f(p):
    """Colletto alto dietro la testa, che si apre a ventaglio con tre punte."""
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    u = np.clip((z - ZC0) / (ZC1 - ZC0), 0, 1)
    Y = 0.36 + 0.3 * u - (0.95 - 0.45 * u) * x * x
    d_sheet = (np.abs(y - Y) - 0.03) / np.sqrt(1 + (2 * (0.95 - 0.45 * u) * x) ** 2 + 0.1)
    W = 0.34 + 0.4 * u
    ztop = ZC1 - 0.16 * np.abs(np.sin(np.abs(x) / W.clip(0.1) * math.pi * 1.5))
    d_out = np.maximum.reduce([np.abs(x) - W, ZC0 - z, z - ztop])
    return np.maximum(d_sheet, d_out * 0.8).astype(np.float32)


collar = SDF(collar_f, (-0.8, 0.1, ZC0 - 0.02), (0.8, 0.8, ZC1 + 0.02))
# orlo d'oro del colletto e catenella sul petto che chiude il mantello
col_edge = []
for x in np.linspace(-0.7, 0.7, 21):
    u = 1.0
    W = 0.34 + 0.4 * u
    ztop = ZC1 - 0.16 * abs(math.sin(abs(x) / W * math.pi * 1.5))
    zz = ztop - 0.03
    uu = (zz - ZC0) / (ZC1 - ZC0)
    Y = 0.36 + 0.3 * uu - (0.95 - 0.45 * uu) * x * x
    col_edge.append((x, Y, zz))
gold.append(tube(col_edge, 0.024))
# bordino d'oro lungo i lati del mantello
for sx in (1, -1):
    side_pts = []
    for z in np.linspace(Z_TOP - 0.02, 0.36, 12):
        u = (Z_TOP - z) / (Z_TOP - Z_BOT)
        W = 0.6 + 0.32 * u - 0.012
        Y, _ = cape_geom(np.array([sx * W]), np.array([z]))
        side_pts.append((sx * W, float(Y[0]), z))
    gold.append(tube(side_pts, 0.022))
clasp_pts, _ = project_many(core0, [(0, 0.0, 1.8)] * 9,
                            [np.array([x, -1.0, 1.98 - 0.12 * (1 - (x / 0.5) ** 2)]) - np.array([0, 0.0, 1.8])
                             for x in np.linspace(-0.5, 0.5, 9)])
for i in range(len(clasp_pts) - 1):
    a, b = clasp_pts[i] + np.array([0, -0.05, 0]), clasp_pts[i + 1] + np.array([0, -0.05, 0])
    gold.append(capsule(tuple(a), tuple(b), 0.018))
for sx in (1, -1):   # due borchie d'oro dove la catenella aggancia il mantello
    gold.append(sphere(0.06, tuple(clasp_pts[0 if sx < 0 else -1] + np.array([0, -0.04, 0]))))

# ============================================================ ali da mosca trasparenti, venate e sbrindellate
WING_POLY = [(0.0, 0.03), (0.22, 0.11), (0.55, 0.19), (0.9, 0.22), (1.14, 0.17), (1.27, 0.06), (1.26, -0.07),
             (1.12, -0.18), (0.84, -0.25), (0.5, -0.24), (0.22, -0.15), (0.04, -0.05)]
VEINS = [[(0.02, 0.02), (0.5, 0.15), (1.0, 0.19), (1.2, 0.12)],
         [(0.03, 0.0), (0.6, 0.06), (1.05, 0.06), (1.25, 0.0)],
         [(0.04, -0.02), (0.55, -0.06), (0.95, -0.1), (1.18, -0.12)],
         [(0.05, -0.04), (0.42, -0.14), (0.78, -0.22)],
         [(0.62, 0.17), (0.66, 0.06), (0.62, -0.06)],
         [(0.92, 0.2), (0.96, 0.06), (0.98, -0.1), (0.94, -0.2)]]
TEARS = {1: [((1.22, -0.12), 0.08), ((0.86, -0.27), 0.07), ((0.48, -0.26), 0.05), ((0.82, 0.02), 0.045),
             ((1.06, 0.1), 0.03)],
         -1: [((1.28, 0.08), 0.07), ((1.0, -0.22), 0.08), ((0.62, -0.25), 0.055), ((0.68, 0.05), 0.04),
              ((1.02, -0.04), 0.035)]}
WT = 0.02
WSCALE = 1.48


def wing_local(sx):
    flat = prism([(x * WSCALE, y * WSCALE) for x, y in WING_POLY], -WT, WT, round=WT * 0.9)
    cut = union(*[cylinder((cx * WSCALE, cy * WSCALE, -0.1), (cx * WSCALE, cy * WSCALE, 0.1), r * WSCALE)
                  for (cx, cy), r in TEARS[sx]])
    mem = flat.subtract(cut)
    vein_t = []
    for v in VEINS:
        pts = [(x * WSCALE, y * WSCALE, 0.0) for x, y in v]
        vein_t.append(tube(pts, taper(len(pts), 0.03, 0.019)))
    veins = union(*vein_t).intersect(prism([(x * WSCALE, y * WSCALE) for x, y in WING_POLY], -0.1, 0.1).offset(0.012))
    veins = veins.subtract(cut.offset(0.012))
    return mem, veins


WING_ROOT = {sx: np.array([sx * 0.2, 0.42, 2.02]) for sx in (1, -1)}


def wing_matrix(sx):
    along = norm((0.78, 0.42, 0.6))
    nrm = norm(np.array([0.0, -1.0, 0.35]) - along * float(np.dot((0.0, -1.0, 0.35), along)))
    chord = np.cross(nrm, along)
    if chord[2] < 0:
        chord, nrm = -chord, -nrm
    return np.stack([along, chord, nrm], axis=1).astype(np.float32)


WING_M = wing_matrix(1)

# ============================================================ sciame di mosche su orbite inclinate
flies = []
ORBITS = [  # (centro, raggio x, raggio y, inclinazione (gradi attorno a X, attorno a Y), angoli delle mosche)
    ((0, 0.05, 1.3), 1.25, 1.02, (14, -10), (-150, -112, -68, -24, 18, 40, 62, 90, 118, 140, 160, -178)),
    ((0, 0.05, 2.78), 1.02, 0.86, (-16, 14), (-150, -100, -30, 14, 58, 104, 150)),
    ((0, 0.0, 0.62), 0.95, 0.85, (6, 12), (-128, -60, 4, 70, 136)),
]


def fly(c, fwd, s, bank):
    """Mosca (locale: muso verso +Y): torace, addome, testa con gli occhioni, due ali aperte a V all'indietro."""
    parts = [ellipsoid((0.032, 0.036, 0.03)), ellipsoid((0.029, 0.05, 0.026), (0, -0.056, -0.004)),
             sphere(0.028, (0, 0.044, 0.004))]
    parts += [sphere(0.019, (sx * 0.021, 0.05, 0.014)) for sx in (1, -1)]
    for sx in (1, -1):
        parts.append(ellipsoid((0.078, 0.03, 0.015)).rot(0, sx * -14, sx * -38).translate((sx * 0.05, -0.036, 0.03)))
    body = union(*parts, k=0.01)
    return body.rot(0, bank, 0).scale(s).rotate(look(fwd)).translate(tuple(c))


frng = np.random.default_rng(8)
for (c, rx, ry, (tx, ty), angs) in ORBITS:
    Mo = euler(tx, ty, 0)
    c = np.asarray(c, dtype=np.float64)
    for j, a_deg in enumerate(angs):
        a = math.radians(a_deg)
        loc = np.array([rx * math.cos(a), ry * math.sin(a), 0.03 * math.sin(3 * a)])
        tan = np.array([-rx * math.sin(a), ry * math.cos(a), 0.0])
        pos = c + Mo @ loc
        if pos[1] < -0.3 and 2.0 < pos[2] < 3.15 and abs(pos[0]) < 0.8:   # niente mosche davanti alla faccia
            continue
        if pos[1] < -0.2 and 0.5 < pos[2] < 2.0 and abs(pos[0]) < 0.62:   # ne' davanti alla pancia
            continue
        if np.linalg.norm(pos - HEAD_T) < 0.95:                            # ne' sopra gli occhi
            continue
        flies.append(fly(pos, Mo @ tan + np.array([0, 0, frng.uniform(-0.25, 0.25)]), frng.uniform(1.65, 2.05),
                         frng.uniform(-35, 35)))

# ============================================================ artigli neri, setole, punte
claws = list(spikes)
for b1, dk, L, Fd in CLAW_ROOTS:
    claws.append(horn(tuple(b1 - dk * 0.02), tuple(b1 + dk * L * 0.5), tuple(b1 + dk * L * 0.85 + Fd * 0.04),
                      tuple(b1 + dk * L + Fd * 0.09), 0.036, 0.008, n=8))
for tip, d in TOE_TIPS:
    claws.append(horn(tuple(tip - d * 0.02), tuple(tip + d * 0.06), tuple(tip + d * 0.1 + np.array([0, 0, -0.01])),
                      tuple(tip + d * 0.14 + np.array([0, 0, -0.04])), 0.04, 0.01, n=6))
# setole irte sugli stinchi e sul dorso del torace
for sx, L in LEGS.items():
    for t in (0.3, 0.6):
        q = mix(L["knee"], L["ankle"], t)
        d = norm(np.array([sx * 0.4, 0.8, 0.3]))
        claws.append(round_cone(tuple(q + d * 0.06), tuple(q + d * 0.2), 0.022, 0.005))
    q = mix(L["hip"], L["knee"], 0.5)
    claws.append(round_cone(tuple(q + np.array([sx * 0.14, 0.0, 0.0])), tuple(q + np.array([sx * 0.3, 0.06, 0.06])), 0.024, 0.005))
for x, z in ((-0.2, 2.06), (0.0, 2.1), (0.2, 2.06), (-0.34, 1.86), (0.34, 1.86)):
    p_, n_ = project(core0, (x * 0.5, 0.0, z - 0.2), (x, 1.0, 0.3))
    claws.append(round_cone(tuple(p_ - n_ * 0.02), tuple(p_ + norm(n_ + np.array([0, 0.3, 0.4])) * 0.16), 0.024, 0.005))
claws += [Hd(a) for a in antennae] + [Hd(x) for x in mandibles]

# ============================================================ toppa viola ricucita sulla pancia
PF_O, PF_N = project(core0, (0.05, 0.0, 1.0), (0.25, -1.0, -0.05))
PM = frame(PF_N, (0, 0, 1))
PW, PH = 0.17, 0.15


def patch_region(p):
    q = (p - PF_O) @ PM
    a = math.radians(14)
    u = q[:, 0] * math.cos(a) + q[:, 1] * math.sin(a)
    v = -q[:, 0] * math.sin(a) + q[:, 1] * math.cos(a)
    return np.maximum(np.abs(u) - PW, np.abs(v) - PH).astype(np.float32)


patch = paint(core0, SDF(patch_region, PF_O - 0.3, PF_O + 0.3), out=0.022, inn=0.03, k=0.01)
stitches = []
a = math.radians(14)
corners = [(-PW, -PH), (PW, -PH), (PW, PH), (-PW, PH)]
for i in range(4):
    u0, v0 = corners[i]
    u1, v1 = corners[(i + 1) % 4]
    for t in (0.25, 0.75):
        u, v = u0 + (u1 - u0) * t, v0 + (v1 - v0) * t
        tu, tv = norm((u1 - u0, v1 - v0, 0))[:2]
        nu, nv = -tv, tu
        for sg in (1, -1):
            e1 = (u - nu * 0.045 - tu * 0.028 * sg, v - nv * 0.045 - tv * 0.028 * sg)
            e2 = (u + nu * 0.045 + tu * 0.028 * sg, v + nv * 0.045 + tv * 0.028 * sg)
            w = []
            for eu, ev in (e1, e2):
                qx, qy = eu * math.cos(a) - ev * math.sin(a), eu * math.sin(a) + ev * math.cos(a)
                w.append(on_surface(core0, PF_O + PM @ np.array([qx, qy, 0.0], dtype=np.float32), 0.026, 3))
            stitches.append(capsule(tuple(w[0]), tuple(w[1]), 0.016))

# ============================================================ parti
m.add("Body", core0, CHITIN, tris=2600, voxel=0.03 * VX, reflectance=0.08)
m.add("Head", head_w, CHITIN, role="skin", tris=1200, voxel=0.022 * VX, reflectance=0.08)
m.add("Eyes", fast_union([Hd(e) for e in eye_parts]), EYE_RED, role="eye", tris=1500, voxel=0.016 * VX,
      reflectance=0.25, smooth=False)
m.add("Mouth", Hd(mouth_dark), MOUTH, role="eye", tris=240, voxel=0.014 * VX)
# denti del ghigno e riflessi degli occhi (bianco: le mutazioni non li toccano)
m.add("Shine", Hd(fast_union(teeth + eye_shine)), TOOTH, role="shine", tris=500, voxel=0.011 * VX)
m.add("Armor", fast_union(armor), ARMOR, role="detail", tris=1000, voxel=0.024 * VX, reflectance=0.15)
m.add("Regalia", fast_union(gold + [Cr(union(*crown_l))]), GOLD, material="Foil", role="detail", tris=1500,
      voxel=0.016 * VX)
m.add("GemGlow", fast_union([Cr(g) for g in gems_l]), GEM, material="Neon", role="glow", tris=120, voxel=0.01 * VX)
# sfera dello scettro: il veleno che ne gocciola (il gioco ci attacca le gocce verdi)
m.add("Venom", fast_union(gems), GEM, material="Neon", role="glow", tris=140, voxel=0.014 * VX)
m.add("Cape", union(cape, collar), CAPE, material="Fabric", role="detail", tris=1700, voxel=0.024 * VX)
for sx, nm in ((1, "WingR"), (-1, "WingL")):
    mem, veins = wing_local(sx)
    place = (lambda s: s.rotate(WING_M).translate(tuple(WING_ROOT[1]))) if sx > 0 else \
        (lambda s: s.rotate(WING_M).translate(tuple(WING_ROOT[1])).mirrored())
    piv = tuple(float(v) for v in WING_ROOT[sx])
    m.add(nm, place(mem), WING, role="detail", tris=520, voxel=0.02 * VX, transparency=0.45, reflectance=0.12,
          group=nm, pivot=piv)
    m.add(nm + "Veins", place(veins), VEIN, role="detail", tris=300, voxel=0.014 * VX, group=nm, pivot=piv)
m.add("Shadow", fast_union(flies), FLY, material="Neon", role="glow", tris=2000, voxel=0.011 * VX)
m.add("Claws", fast_union(claws).intersect(halfspace_z(0.002)), CLAW, role="detail", tris=900, voxel=0.016 * VX)
m.add("Patch", patch, PATCH, material="Fabric", role="detail", tris=160, voxel=0.02 * VX)
m.add("Stitches", fast_union(stitches), THREAD, role="detail", tris=200, voxel=0.012 * VX)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    fit_voxels(m)
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
