"""Abaddon (Abaddon) - ricompensa del Sentiero Estremo (demoni biblici).

Il Distruttore, re delle locuste dell'abisso: un destriero da guerra demoniaco dal corpo da cavallo corazzato come
una locusta. Posa da parata di guerra: la zampa anteriore destra alzata, il collo inarcato e la testa alta che
ringhia verso chi guarda. Pelle nera appena violacea; il muso da cavallo porta una testiera di bronzo scuro con un
corno ricurvo, paraocchi d'oro e occhi di brace che bruciano sotto le arcate (parte Neon "EmberGlow"); le fauci
spalancate mostrano zanne da leone. Fra le orecchie una corona d'oro a sette punte con tre gemme di brace. Una
lunga criniera cremisi ricade a ciocche ondulate sui lati del collo, con le punte che ardono come braci (parte
Neon "Flames": il gioco ci attacca il fuoco); ciuffi cremisi coprono anche i nodelli, come in un cavallo da
guerra. Corazza di bronzo scuro bordata d'oro e borchiata: collo a segmenti, pettorale con medaglione e gemma di
brace, spallacci con tre punte d'oro, anelli sul ventre come l'addome di una locusta (con le fessure che brillano
di brace) e piastra sulla groppa; zampe posteriori da locusta con file di spine, zoccoli ferrati d'oro. Sulla
schiena due paia d'ali da locusta: le anteriori strette, scure e coriacee, le posteriori a ventaglio, ambrate,
trasparenti e un po' strappate (gruppi "WingR"/"WingL": il gioco le fa vibrare). Dalla groppa si alza una lunga
coda da scorpione a segmenti di bronzo bordati d'oro e chiodati che si inarca sopra il dorso e finisce in un
pungiglione velenoso che brilla (parte Neon "Venom": il gioco ci attacca le gocce di veleno; tutta la coda e' nel
gruppo "Tail" e ondeggia attorno all'attaccatura).

Tocco "toy horror": una grande chiave a molla d'oro piantata nel fianco, come un cavallo giocattolo caricato che
ha preso vita, e la criniera cucita al collo con grossi punti a croce.
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
from lib.sdf import (SDF, bezier, box, capsule, cylinder, ellipsoid, euler, halfspace_z, prism, project,  # noqa: E402
                     round_cone, smax, smin, sphere, torus, tube, union)
from lib.toy import Model  # noqa: E402

DRAFT = os.environ.get("DRAFT", "") == "1"
VX = 1.35 if DRAFT else 1.0  # bozza: voxel piu' grossi per iterare in fretta
rng = np.random.default_rng(909)
T0 = time.time()


def log(msg):
    print(f"[abaddon {time.time() - T0:6.1f}s] {msg}", flush=True)


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


def curve_frames(pts):
    """Tangenti normalizzate di una polilinea."""
    P = np.asarray(pts, dtype=np.float64)
    T = np.gradient(P, axis=0)
    return P, T / np.linalg.norm(T, axis=1, keepdims=True)


# ============================================================ colori
HIDE = (40, 30, 40)         # pelle nera da locusta, appena violacea
BRONZE = (158, 100, 54)     # corazza di bronzo scuro
GOLD = (244, 188, 70)
HAIR = (158, 24, 38)        # criniera cremisi (le punte ardono come braci)
EMBER = (255, 112, 26)      # occhi e fessure di brace (Neon)
FIRE = (255, 136, 30)       # punte della criniera che ardono (Neon)
VENOM = (176, 255, 64)      # pungiglione velenoso (Neon)
MOUTH = (40, 10, 14)
TOOTH = (250, 244, 226)
DARK = (34, 24, 26)         # zoccoli e spine
WING = (255, 156, 40)       # ali posteriori ambrate trasparenti
FRAME = (48, 30, 26)        # ali anteriori coriacee e venature
THREAD = (242, 226, 184)

m = Model("Abaddon", "pet")

# ============================================================ testa da cavallo (spazio locale: muso verso -Y)
HEAD_T = np.array([0.0, -1.06, 2.56], dtype=np.float32)
HS = 1.4
R_HEAD = euler(15.0, 6.0, 13.0)     # muso in basso come un destriero, girato e inclinato verso chi guarda
JAW_Z = -0.13
HINGE = (0.0, 0.02, JAW_Z)
GAPE = 28.0


def Hd(shape):
    return shape.scale(HS).rotate(R_HEAD).translate(HEAD_T)


def hp(p):
    return R_HEAD @ (HS * np.asarray(p, dtype=np.float32)) + HEAD_T


def hv(v):
    return R_HEAD @ np.asarray(v, dtype=np.float32)


def Jw(shape):
    return shape.rot(GAPE, 0, 0, pivot=HINGE)


cran = ellipsoid((0.2, 0.24, 0.22), (0, 0.06, 0.05))
cheeks = [ellipsoid((0.13, 0.22, 0.2), (sx * 0.12, 0.0, -0.1)) for sx in (1, -1)]
face = tbox(-0.02, -0.72, 0.17, 0.14, 0.2, 0.02, JAW_Z - 0.02, JAW_Z - 0.02, 0.07)
nose = ellipsoid((0.16, 0.12, 0.13), (0, -0.7, -0.06))
brows = [capsule((sx * 0.06, -0.2, 0.16), (sx * 0.2, -0.08, 0.2), 0.05) for sx in (1, -1)]
upper = union(cran, *cheeks, k=0.1)
upper = union(upper, face, k=0.12)
upper = union(upper, nose, k=0.08)
upper = union(upper, *brows, k=0.06)
NOSTRILS = [(sx * 0.09, -0.8, -0.04) for sx in (1, -1)]
# labbro arricciato del ringhio: pieghe sul muso sopra i canini
snarl = [tube([(sx * 0.15, -0.72, -0.02), (sx * 0.12, -0.6, 0.04), (sx * 0.13, -0.48, 0.03)], 0.028) for sx in (1, -1)]
upper = union(upper, *snarl, k=0.03)
upper = upper.subtract(union(*[ellipsoid((0.04, 0.05, 0.035), c) for c in NOSTRILS]), k=0.02)
upper = upper.subtract(box((0.5, 0.6, 0.3), (0, HINGE[1] - 0.6, JAW_Z - 0.3)), k=0.01)
jaw = union(tbox(0.0, -0.66, 0.16, 0.12, JAW_Z + 0.04, JAW_Z + 0.04, -0.29, -0.23, 0.06),
            ellipsoid((0.12, 0.1, 0.075), (0, -0.58, -0.23)), k=0.05)
jaw = jaw.subtract(box((0.5, 0.6, 0.3), (0, -0.4, JAW_Z + 0.3)), k=0.01)

# occhi di brace (sotto la testiera di bronzo) con la palpebra arrabbiata
eyes, lids, brow_plates, EYE_PN = [], [], [], {}
for sx in (1, -1):
    p, n = project(upper, (sx * 0.1, -0.13, 0.06), (sx * 0.8, -0.58, 0.12))
    EYE_PN[sx] = (p, n)
    a1 = norm(np.cross((0.0, 0.0, 1.0), n)) * sx       # orizzontale lungo la testa (verso la nuca)
    a3 = norm(np.cross(n, a1)) * sx                      # verso l'alto
    if a3[2] < 0:
        a3 = -a3
    M = np.stack([a1, norm(np.cross(a3, a1)), a3], axis=1).astype(np.float32)
    c = p - n * 0.012
    eyes.append(ellipsoid((0.125, 0.085, 0.105)).rotate(M).translate(c))
    # arcata di bronzo arrabbiata: bassa verso il naso, alta verso la nuca
    pts = [c + M @ np.array(q, dtype=np.float32) + n * 0.03 for q in ((-0.15, 0.0, 0.05), (-0.05, 0.0, 0.11),
                                                                   (0.06, 0.0, 0.14), (0.15, 0.0, 0.15))]
    brow_plates.append(tube([tuple(q) for q in pts], [0.03, 0.045, 0.045, 0.03]))

ears = []
for sx in (1, -1):
    Me = frame((sx * 0.35, 0.25, 1.0), (0, -1.0, 0.0))
    ear = flatten(tube([(0, 0, -0.02), (0, 0, 0.1), (0, -0.01, 0.22)], [0.065, 0.06, 0.012]), 0.5, axis=1)
    ears.append(ear.rotate(Me).translate((sx * 0.12, 0.14, 0.2)))
head_skin = union(union(upper, Jw(jaw), k=0.012), *lids, k=0.012)
head_skin = union(head_skin, *ears, k=0.03)

# bocca: palato e lingua scuri, gola
pal_reg = SDF(lambda p: np.maximum(np.maximum(np.abs(p[:, 0]) - 0.125, p[:, 2] - (JAW_Z + 0.03)),
                                   np.maximum(p[:, 1] - 0.0, -0.72 - p[:, 1])), (-0.13, -0.73, JAW_Z - 0.05),
              (0.13, 0.0, JAW_Z + 0.03))
jaw_reg = SDF(lambda p: np.maximum(np.maximum(np.abs(p[:, 0]) - 0.115, (JAW_Z - 0.03) - p[:, 2]),
                                   np.maximum(p[:, 1] - 0.0, -0.64 - p[:, 1])), (-0.12, -0.65, JAW_Z - 0.03),
              (0.12, 0.0, JAW_Z + 0.05))
dark = [thin(upper, 0.006, 0.07).intersect(pal_reg), Jw(thin(jaw, 0.006, 0.07).intersect(jaw_reg))]
Rinv = euler(-GAPE, 0, 0)
piv = np.asarray(HINGE, dtype=np.float32)


def wedge(p):
    q = (p - piv) @ Rinv.T + piv
    return np.maximum(np.maximum(p[:, 2] - (JAW_Z + 0.004), (JAW_Z - 0.004) - q[:, 2]),
                      np.maximum(np.abs(p[:, 0]) - 0.13, np.maximum(p[:, 1] - 0.03, -0.12 - p[:, 1])))


dark.append(SDF(wedge, (-0.13, -0.12, JAW_Z - 0.3), (0.13, 0.03, JAW_Z + 0.01)))
dark.append(Jw(ellipsoid((0.085, 0.26, 0.03), (0, -0.36, JAW_Z - 0.012))))     # lingua
dark += [ellipsoid((0.03, 0.04, 0.026), (c[0] * 0.95, -0.77, c[2])) for c in NOSTRILS]

# zanne da leone: due canini grossi sopra e sotto, incisivi aguzzi davanti
teeth, bases_up, bases_lo = [], [], []
for y_, x_dir, big in ((-0.55, 1, True), (-0.55, -1, True), (-0.36, 1, False), (-0.36, -1, False), (-0.22, 1, False),
                       (-0.22, -1, False)):
    p, n = project(upper, (0, y_, JAW_Z + 0.012), (x_dir, 0, 0))
    b = p - np.array([x_dir * 0.025, 0, 0])
    L = 0.19 if big else 0.06
    teeth.append(round_cone((b[0], b[1], JAW_Z + 0.03), (b[0], b[1] - (0.02 if big else 0), JAW_Z - L),
                            0.034 if big else 0.02, 0.008))
    bases_up.append((b[0], b[1], JAW_Z + 0.03))
for a in (-40, -14, 14, 40):
    d = (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0.0)
    p, n = project(upper, (0, -0.53, JAW_Z + 0.012), d)
    b = p - norm((n[0], n[1], 0.0)) * 0.025
    teeth.append(round_cone((b[0], b[1], JAW_Z + 0.03), (b[0], b[1], JAW_Z - 0.065), 0.02, 0.007))
    bases_up.append((b[0], b[1], JAW_Z + 0.03))
for y_, x_dir, big in ((-0.5, 1, True), (-0.5, -1, True), (-0.32, 1, False), (-0.32, -1, False)):
    p, n = project(jaw, (0, y_, JAW_Z - 0.012), (x_dir, 0, 0))
    b = p - np.array([x_dir * 0.025, 0, 0])
    L = 0.16 if big else 0.055
    teeth.append(Jw(round_cone((b[0], b[1], JAW_Z - 0.03), (b[0], b[1] - (0.015 if big else 0), JAW_Z + L),
                               0.03 if big else 0.019, 0.008)))
    bases_lo.append((b[0], b[1], JAW_Z - 0.03))
for a in (-30, 0, 30):
    d = (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0.0)
    p, n = project(jaw, (0, -0.46, JAW_Z - 0.012), d)
    b = p - norm((n[0], n[1], 0.0)) * 0.025
    teeth.append(Jw(round_cone((b[0], b[1], JAW_Z - 0.03), (b[0], b[1], JAW_Z + 0.06), 0.019, 0.007)))
    bases_lo.append((b[0], b[1], JAW_Z - 0.03))


def row_bar(bases):
    pts = sorted(bases, key=lambda q: math.atan2(q[0], -q[1]))
    return tube(pts, 0.013)


teeth += [row_bar(bases_up), Jw(row_bar(bases_lo))]

# testiera di bronzo sul muso (con cresta e paraocchi svasati) e corona d'oro fra le orecchie
def chanfron_reg(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    w = 0.065 + 0.075 * np.clip((y + 0.52) / 0.5, 0, 1)
    return np.maximum.reduce([np.abs(x) - w, -0.52 - y, y - 0.08, 0.06 - z]).astype(np.float32)


chanfron = paint(head_skin, SDF(chanfron_reg, (-0.3, -0.8, -0.1), (0.3, 0.1, 0.4)), out=0.04, inn=0.03, k=0.02)
chanfron = union(chanfron, tube([(0, -0.52, 0.12), (0, -0.36, 0.18), (0, -0.12, 0.25), (0, 0.02, 0.28)],
                                [0.022, 0.03, 0.034, 0.03]), k=0.02)
# corno di bronzo sulla fronte della testiera, piegato in avanti
chanfron = union(chanfron, horn((0, -0.3, 0.2), (0, -0.36, 0.3), (0, -0.4, 0.38), (0, -0.5, 0.44), 0.06, 0.012, n=8),
                 k=0.02)
eye_guards = []
for sx in (1, -1):
    p, n = EYE_PN[sx]
    eye_guards.append(torus(0.13, 0.022).rotate(frame(n, (0, 0, 1))).translate(tuple(p - n * 0.005)))
crown_l = [band(0.16, 0.024, 0.045).translate((0, 0, 0.0)), torus(0.16, 0.018).translate((0, 0, -0.042))]
for k in range(7):
    a = math.radians(-90 + 360 / 7 * k)
    d = np.array([math.cos(a), math.sin(a), 0.0])
    tall = (0.3, 0.24, 0.17, 0.14, 0.14, 0.17, 0.24)[k]
    b = d * 0.16 + np.array([0, 0, 0.02])
    tip = d * 0.21 + np.array([0, 0, tall])
    crown_l.append(round_cone(tuple(b), tuple(tip), 0.045, 0.008))
    crown_l.append(sphere(0.02, tuple(tip + np.array([0, 0, 0.01]))))
CROWN_T = np.array([0.0, 0.1, 0.28])
CROWN_M = euler(-8.0, 0.0, 0.0)
crown_gems = [sphere(0.03, tuple(CROWN_M @ np.array([math.cos(math.radians(a)) * 0.184, math.sin(math.radians(a)) * 0.184,
                                                      0.0]) + CROWN_T)) for a in (-90, -38, -142)]
crown = union(*crown_l).rotate(CROWN_M).translate(tuple(CROWN_T))

# ============================================================ corpo da destriero (spazio Blender)
chest = ellipsoid((0.5, 0.42, 0.54), (0, -0.54, 1.44))
barrel = ellipsoid((0.47, 0.68, 0.47), (0, 0.04, 1.42))
haunch = ellipsoid((0.48, 0.42, 0.49), (0, 0.6, 1.48))
withers = ellipsoid((0.38, 0.36, 0.34), (0, -0.42, 1.78))
torso = union(chest, barrel, haunch, k=0.25)
torso = union(torso, withers, k=0.2)
NECK_PTS = bezier((0, -0.46, 1.66), (0, -0.66, 1.98), (0, -0.82, 2.26), tuple(hp((0, 0.16, -0.04))), 10)
NP, NT = curve_frames(NECK_PTS)
neck_parts = []
for i, (c, t) in enumerate(zip(NP, NT)):
    u = i / (len(NP) - 1)
    neck_parts.append(ell(c, (0.3 - 0.1 * u, 0.4 - 0.13 * u, 0.22), axis=t, side=(1, 0, 0)))
neck = union(*neck_parts, k=0.08)

LEGS = {
    # zampa anteriore sinistra (-X) a terra
    (-1, "f"): [(-0.34, -0.6, 1.3), (-0.37, -0.6, 0.98), (-0.36, -0.66, 0.56), (-0.36, -0.7, 0.2)],
    # zampa anteriore destra (+X) alzata, da parata: avambraccio avanti, stinco giu', zoccolo piegato indietro
    (1, "f"): [(0.34, -0.6, 1.3), (0.39, -0.76, 1.08), (0.41, -1.06, 1.08), (0.41, -1.08, 0.72)],
    (1, "h"): [(0.36, 0.62, 1.4), (0.42, 0.42, 0.98), (0.4, 0.84, 0.6), (0.39, 0.72, 0.2)],
    (-1, "h"): [(-0.36, 0.62, 1.4), (-0.42, 0.38, 0.98), (-0.4, 0.82, 0.6), (-0.39, 0.7, 0.2)],
}
leg_parts, HOOVES, SPINE_LEGS, FETLOCKS, CANNONS = [], [], [], [], []
for (sx, kind), pts in LEGS.items():
    a, b, c, d = (np.array(q, dtype=np.float64) for q in pts)
    if kind == "f":
        leg_parts += [round_cone(a, b, 0.3, 0.22), ell(mix(a, b, 0.4), (0.26, 0.27, 0.32), axis=b - a),
                      round_cone(b, c, 0.21, 0.15), ell(mix(b, c, 0.3), (0.18, 0.18, 0.24), axis=c - b),
                      round_cone(c, d, 0.14, 0.13)]
    else:
        leg_parts += [ell((sx * 0.4, 0.58, 1.24), (0.3, 0.42, 0.46), axis=(0, -0.35, 1)),
                      round_cone(a, b, 0.29, 0.21), round_cone(b, c, 0.21, 0.14),
                      ell(mix(b, c, 0.35) + np.array([0, 0.04, 0.02]), (0.18, 0.19, 0.25), axis=c - b),
                      round_cone(c, d, 0.14, 0.13)]
        SPINE_LEGS.append((b, c, d, sx))
    if (sx, kind) == (1, "f"):
        fwd = norm((0.0, 0.45, -1.0))
        up = norm(np.cross(np.cross(fwd, (0, 0, 1.0)), fwd))
        hoof_c = d + norm(d - c) * 0.1
        HOOVES.append((hoof_c, norm(d - c), True))
    else:
        HOOVES.append((d + np.array([0, -0.02, -0.12]), np.array([0, 0, -1.0]), False))
    leg_parts.append(sphere(0.16, tuple(d)))   # nodello
    CANNONS.append((c, d, sx))
    FETLOCKS.append((d, norm(d - c), (sx, kind) == (1, "f")))

# coda da scorpione: si alza dalla groppa e si inarca sopra il dorso (gruppo "Tail")
TAIL_PIVOT = (0.0, 0.96, 1.7)
TAIL_C = catmull([(0, 0.96, 1.7), (0, 1.24, 2.0), (0, 1.34, 2.4), (0.02, 1.22, 2.78), (0.04, 0.94, 3.0),
                  (0.04, 0.6, 3.04), (0.03, 0.36, 2.9)], 8)
core0 = union(torso, neck, k=0.16)
core0 = fast_union(leg_parts, k=0.06, base=core0)
core0 = shrink(core0.intersect(halfspace_z(0.0)))
head_w = Hd(head_skin)
core = shrink(fast_union([head_w], k=0.08, base=core0))
log("corpo pronto")

# ============================================================ corazza di bronzo: collo a segmenti, pettorale, anelli, groppa
armor, gold, embers = [], [], []
armor.append(Hd(chanfron))
armor += [Hd(b) for b in brow_plates]
gold += [Hd(g) for g in eye_guards] + [Hd(crown)]
embers += [Hd(g) for g in crown_gems]
for u in (0.12, 0.32, 0.52, 0.72, 0.9):   # piastre del collo a segmenti sulla gola, come il ventre di un insetto
    i = int(round(u * (len(NP) - 1)))
    c, t = NP[i], NT[i]
    throat = norm(np.array([0.0, -t[2], t[1]]))
    reg = SDF(lambda p, c=c.astype(np.float32), t=t.astype(np.float32), th=throat.astype(np.float32):
              np.maximum(np.abs((p - c) @ t) - 0.075, 0.0 - (p - c) @ th).astype(np.float32), c - 0.6, c + 0.6)
    armor.append(paint(core0, reg, out=0.05, inn=0.03, k=0.02))


def peytral_reg(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    bot = 1.14 + 0.32 * (x / 0.38) ** 2
    return np.maximum.reduce([y + 0.72, np.abs(x) - 0.38, bot - z, z - 1.74]).astype(np.float32)


armor.append(paint(core0, SDF(peytral_reg, (-0.5, -1.1, 0.95), (0.5, -0.5, 1.9)), out=0.055, inn=0.03, k=0.02))
pe = []
for x in np.linspace(-0.37, 0.37, 15):
    pe.append(np.array([x, -1.2, 1.16 + 0.32 * (x / 0.38) ** 2]))
pp, pnn = project_many(core0, [(0, -0.3, 1.4)] * len(pe), [q - np.array([0, -0.3, 1.4]) for q in pe])
gold.append(tube([tuple(q + n_ * 0.05) for q, n_ in zip(pp, pnn)], 0.032))
pb, pn = project(core0, (0, -0.5, 1.45), (0, -1, 0.1))
gold.append(cylinder(tuple(pb - pn * 0.02), tuple(pb + pn * 0.07), 0.11, round=0.02))       # medaglione
embers.append(ellipsoid((0.05, 0.05, 0.05), tuple(pb + pn * 0.08)))
RINGS = (-0.26, 0.02, 0.3)
for y0 in RINGS:   # anelli ad addome di locusta sul ventre e sui fianchi
    reg = SDF(lambda p, y0=y0: np.maximum(np.abs(p[:, 1] - y0) - 0.105, 1.02 - p[:, 2]).astype(np.float32),
              (-0.6, y0 - 0.2, 0.9), (0.6, y0 + 0.2, 1.95))
    armor.append(paint(core0, reg, out=0.055, inn=0.03, k=0.02))
    angs = np.radians(np.linspace(-118, 118, 17))
    for edge, kind in ((y0 - 0.11, "gold"), (y0 + 0.115, "ember")):
        pts, nrs = project_many(core0, [(0, edge, 1.4)] * len(angs), [(math.sin(a), 0.0, math.cos(a)) for a in angs])
        if kind == "gold":
            gold.append(tube([tuple(q + n_ * 0.045) for q, n_ in zip(pts, nrs)], 0.032))
        else:
            embers.append(tube([tuple(q + n_ * 0.004) for q, n_ in zip(pts, nrs)], 0.032))
    for a in np.radians((-70, -35, 0, 35, 70)):   # borchie
        q, n_ = project(core0, (0, y0, 1.4), (math.sin(a), 0.0, math.cos(a)))
        gold.append(sphere(0.04, tuple(q + n_ * 0.055)))


# spallacci di bronzo con tre punte d'oro sulle spalle
for sx in (1, -1):
    c = np.array([sx * 0.4, -0.58, 1.52])
    n = norm((sx * 0.85, -0.25, 0.5))
    dome = ellipsoid((0.3, 0.32, 0.3), tuple(c)).shell(0.028).intersect(
        SDF(lambda p, c=c, n=n.astype(np.float32): (0.04 - (p - c) @ n).astype(np.float32), c - 0.4, c + 0.4))
    armor.append(dome)
    gold.append(torus(0.25, 0.03).rotate(frame(n, (0, 1, 0))).translate(tuple(c + n * 0.075)))
    for dz, dy, L in ((0.12, 0.0, 0.26), (-0.05, -0.2, 0.19), (-0.05, 0.2, 0.19)):
        d = norm(n + np.array([0, dy * 2.0, dz]))
        b = c + d * 0.28
        gold.append(round_cone(tuple(b - d * 0.04), tuple(b + d * L), 0.05, 0.008))


# spine d'oro da locusta lungo il dorso, fra le ali e la coda
for y0, L in ((-0.02, 0.24), (0.2, 0.3), (0.42, 0.28), (0.64, 0.22)):
    q, n_ = project(core0, (0, y0, 1.4), (0, 0.12, 1.0))
    d = norm(n_ + np.array([0, 0.55, 0.0]))
    gold.append(round_cone(tuple(q - d * 0.03), tuple(q + d * L), 0.06, 0.01))


# schinieri di bronzo sugli stinchi, con l'anello d'oro in alto e una punta sul ginocchio
for c, d, sx in CANNONS:
    ax = norm(d - c)

    def greave_reg(p, c=c.astype(np.float32), ax=ax.astype(np.float32), L=float(np.linalg.norm(d - c))):
        t = (p - c) @ ax
        radial = np.linalg.norm((p - c) - t[:, None] * ax[None, :], axis=1) - 0.3     # solo attorno a questa zampa
        return np.maximum(np.maximum(0.12 * L - t, t - 0.8 * L), radial).astype(np.float32)

    armor.append(paint(core0, SDF(greave_reg, np.minimum(c, d) - 0.3, np.maximum(c, d) + 0.3), out=0.04, inn=0.03,
                       k=0.015))
    top = c + ax * float(np.linalg.norm(d - c)) * 0.14
    gold.append(torus(0.165, 0.032).rotate(frame(ax, (0, 1, 0))).translate(tuple(top)))
    fwd = norm(np.array([sx * 0.25, -1.0, 0.0]) - ax * float(np.dot((sx * 0.25, -1.0, 0.0), ax)))
    gold.append(round_cone(tuple(c + fwd * 0.12), tuple(c + fwd * 0.3 - ax * 0.04), 0.05, 0.008))


def crupper_reg(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    return np.maximum.reduce([0.46 - y, 1.52 - z + 0.25 * (x / 0.4) ** 2, y - 1.02]).astype(np.float32)


armor.append(paint(core0, SDF(crupper_reg, (-0.5, 0.4, 1.3), (0.5, 1.1, 1.95)), out=0.055, inn=0.03, k=0.02))

# ============================================================ criniera nera che si alza e vola all'indietro (punte di brace)
locks, crest, lock_tips = [], [], []
for i in range(1, len(NP) - 1, 1):
    c, t = NP[i], NT[i]
    back = norm(np.array([0.0, t[2], -t[1]]))       # verso la cresta del collo (dietro e in alto)
    u = i / (len(NP) - 1)
    r = 0.4 - 0.13 * u
    crest.append((c + back * (r * 0.86), back))
crest.append((hp((0, 0.1, 0.24)), norm(hv((0, 0.5, 0.86)))))
crest = crest[::-1]   # dalla nuca al garrese
lrng = np.random.default_rng(4)


def hair_tuft(L, r0, bend=0.75, fork=0.0, flat=0.55):
    """Ciocca a fiamma (locale: base nell'origine, sale lungo +Z e si piega all'indietro verso +Y, piatta lungo X):
    ritorna (ciocca, punta che arde)."""
    f = flame(L, r0, bend=bend, wig=0.05, flat=flat, fork=fork)
    cut = 0.62 * L
    body = f.intersect(SDF(lambda p, c=cut: (p[:, 2] - c).astype(np.float32), (-9, -9, -9), (9, 9, 9)))
    tip = f.offset(0.006).intersect(SDF(lambda p, c=cut - 0.03: (c - p[:, 2]).astype(np.float32), (-9, -9, -9), (9, 9, 9)))
    return body, tip


# cresta a fiamme dalla nuca al garrese: ciocche grandi che si piegano all'indietro
for j, (root, nrm_) in enumerate(crest):
    u = j / max(len(crest) - 1, 1)                     # 0 = nuca, 1 = garrese
    L = (0.74 - 0.3 * u + lrng.uniform(-0.04, 0.04)) * (0.62 if j == 0 else 1.0)
    up = norm(nrm_ * 0.75 + np.array([0.0, 0.25, 0.45]))
    Mf = frame(up, (0, 1, 0))
    body, tip = hair_tuft(L, 0.15 - 0.04 * u, bend=0.8, fork=0.5 if j % 2 == 0 else 0.0)
    base = np.asarray(root, float) - nrm_ * 0.06
    locks.append(body.rotate(Mf).translate(tuple(base)))
    lock_tips.append(tip.rotate(Mf).translate(tuple(base)))
    for sgn in (1, -1):   # ciocche laterali che ricadono sui due lati del collo
        if j % 2 == 1 or j == 0:
            continue
        side_up = norm(nrm_ * 0.35 + np.array([sgn * 0.85, 0.3, 0.1]))
        Ms = frame(side_up, (0, 1, 0))
        b2, t2 = hair_tuft(L * 0.8, 0.12 - 0.03 * u, bend=1.0)
        base2 = np.asarray(root, float) - nrm_ * 0.08 + np.array([sgn * 0.06, 0.0, 0.0])
        locks.append(b2.rotate(Ms).translate(tuple(base2)))
        lock_tips.append(t2.rotate(Ms).translate(tuple(base2)))
# ciuffi di pelo sui nodelli (zampe "a calzino" da cavallo da guerra)
for d, ax, raised in FETLOCKS:
    for a in np.linspace(0, 2 * math.pi, 9)[:-1]:
        side_v = np.array([math.cos(a), math.sin(a), 0.0])
        side_v = norm(side_v - ax * float(np.dot(side_v, ax)))
        base = d + side_v * 0.13 + ax * 0.0
        tipp = base + side_v * 0.09 + ax * 0.17
        locks.append(round_cone(tuple(base), tuple(tipp), 0.075, 0.014))
hair = fast_union(locks, k=0.0).intersect(halfspace_z(0.0))

# ============================================================ ali da locusta (2 paia per lato)
WSCALE = 1.3
FORE = [(0.0, 0.03), (0.3, 0.08), (0.8, 0.105), (1.18, 0.09), (1.33, 0.02), (1.27, -0.06), (0.8, -0.085), (0.3, -0.07),
        (0.02, -0.03)]
HIND = [(0.0, 0.0), (0.5, -0.03), (1.0, -0.09), (1.14, -0.24), (1.08, -0.44), (0.84, -0.6), (0.5, -0.62),
        (0.2, -0.44), (0.03, -0.14)]
HIND_TEARS = {1: [((1.1, -0.36), 0.07), ((0.7, -0.62), 0.06)], -1: [((0.98, -0.52), 0.08), ((1.12, -0.16), 0.05)]}


def wing_local(sx):
    fore = prism(FORE, -0.026, 0.026, round=0.02).translate((0, 0, 0.03))
    hind = prism(HIND, -0.016, 0.016, round=0.014).translate((0, 0, -0.02))
    tears = union(*[cylinder((cx, cy, -0.2), (cx, cy, 0.2), r) for (cx, cy), r in HIND_TEARS[sx]])
    hind = hind.subtract(tears)
    veins = [tube([(0.02, 0.0, 0.03), (0.6, 0.06, 0.03), (1.2, 0.04, 0.03)], 0.03),     # costa dell'ala anteriore
             tube([(0.03, -0.02, 0.03), (0.7, -0.04, 0.03), (1.24, -0.03, 0.03)], 0.024)]
    for ex, ey in ((1.08, -0.12), (1.1, -0.34), (0.94, -0.52), (0.68, -0.61), (0.38, -0.54), (0.16, -0.36)):
        veins.append(tube([(0.03, -0.03, -0.02), (ex * 0.5, ey * 0.45, -0.02), (ex, ey, -0.02)], [0.034, 0.028, 0.022]))
    for rr in (0.55, 0.85):   # venature trasversali ad arco
        arc = [(rr * math.cos(a) * 1.05, -rr * math.sin(a) * 0.72 - 0.02, -0.02) for a in np.linspace(0.08, 1.35, 7)]
        veins.append(tube(arc, 0.022))
    frame_ = union(fore, union(*veins).intersect(union(prism(HIND, -0.2, 0.2), prism(FORE, -0.2, 0.2)).offset(0.012))
                   .subtract(tears.offset(0.01)))
    return hind.scale(WSCALE), frame_.scale(WSCALE)


WING_ROOT = {sx: np.array([sx * 0.24, -0.24, 1.98]) for sx in (1, -1)}


def wing_matrix():
    along = norm((0.52, 0.45, 0.74))
    chord = np.array([0.0, -0.45, 1.0])
    chord = norm(chord - along * float(np.dot(chord, along)))
    nrm = np.cross(along, chord)
    return np.stack([along, chord, nrm], axis=1).astype(np.float32)


WING_M = wing_matrix()

# ============================================================ coda da scorpione (gruppo "Tail")
seg_l, seg_g = [], []
P, Tn = curve_frames(TAIL_C)
cum = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
NSEG = 10
for k in range(NSEG):
    s0, s1 = cum[-1] * k / NSEG, cum[-1] * (k + 1) / NSEG
    i0, i1 = np.searchsorted(cum, s0), min(np.searchsorted(cum, s1), len(P) - 1)
    a, b = P[i0], P[i1]
    r = 0.19 - 0.09 * k / (NSEG - 1)
    c = (a + b) / 2
    seg_l.append(ell(c, (r, r * 0.92, np.linalg.norm(b - a) * 0.62), axis=b - a, side=(1, 0, 0)))
    seg_l.append(round_cone(tuple(a), tuple(b), r * 0.72, r * 0.68))
    t = norm(b - a)
    if k > 0:
        seg_g.append(torus(r * 0.8, 0.022).rotate(frame(t, (1, 0, 0))).translate(tuple(a)))
    # spuntoni sul dorso della coda
    out = norm(np.cross(t, (1.0, 0.0, 0.0)))
    if out[2] < 0 and out[1] < 0.6:
        out = -out
    seg_g.append(round_cone(tuple(c + out * r * 0.8), tuple(c + out * (r + 0.09) - t * 0.04), 0.03, 0.006))
tip, tdir = P[-1], Tn[-1]
BULB_C = tip + tdir * 0.1
venom = [ell(BULB_C, (0.14, 0.14, 0.18), axis=tdir)]
Mb = frame(tdir, (1, 0, 0))
for t in (-0.07, 0.05):
    seg_g.append(torus(0.135 if t < 0 else 0.136, 0.018).rotate(Mb).translate(tuple(BULB_C + tdir * t)))
down = np.array([0.0, 0.0, -1.0])
barb0 = BULB_C + tdir * 0.14
seg_g.append(horn(tuple(barb0), tuple(barb0 + tdir * 0.14), tuple(barb0 + tdir * 0.2 + down * 0.1),
                  tuple(barb0 + tdir * 0.14 + down * 0.26), 0.055, 0.008, n=10))
for d_, L_ in ((np.array([1.0, 0, 0]), 0.1), (np.array([-1.0, 0, 0]), 0.1)):   # spine laterali del bulbo
    seg_g.append(round_cone(tuple(BULB_C + d_ * 0.1), tuple(BULB_C + d_ * (0.1 + L_) + tdir * 0.05), 0.026, 0.006))

# ============================================================ zoccoli ferrati, spine da locusta, chiave a molla, cuciture
darks = []
for (hc, d, raised) in HOOVES:
    if raised:
        axis = d
        darks.append(ell(hc, (0.14, 0.14, 0.11), axis=axis))
        gold.append(torus(0.13, 0.025).rotate(frame(axis, (0, 1, 0))).translate(tuple(hc + axis * 0.08)))
    else:
        darks.append(cylinder(tuple(hc + np.array([0, 0, -0.08])), tuple(hc + np.array([0, 0, 0.1])), 0.15, round=0.03))
        gold.append(torus(0.15, 0.03).translate(tuple(hc + np.array([0, 0, -0.06]))))
for b, c, d, sx in SPINE_LEGS:   # file di spine sugli stinchi posteriori (zampa da locusta)
    for t in (0.25, 0.45, 0.65, 0.85):
        q = mix(b, c, t)
        out = norm(np.array([sx * 0.35, 0.9, 0.25]))
        darks.append(round_cone(tuple(q + out * 0.08), tuple(q + out * 0.24 + np.array([0, 0, 0.04])), 0.035, 0.006))
# chiave a molla d'oro piantata nel fianco destro (+X)
kp, kn = project(core0, (0, 0.12, 1.42), (1.0, 0.05, 0.12))
shaft_end = kp + kn * 0.2
gold += [cylinder(tuple(kp - kn * 0.05), tuple(shaft_end), 0.04, round=0.01),
         cylinder(tuple(kp + kn * 0.04), tuple(kp + kn * 0.08), 0.07, round=0.015)]
Mk = frame(kn, (0, 0, 1))
for sz in (1, -1):   # impugnatura a farfalla
    lobe_c = shaft_end + kn * 0.1 + Mk @ np.array([0, sz * 0.13, 0.0], dtype=np.float32)
    gold.append(torus(0.1, 0.035).rotate(frame(Mk[:, 0], Mk[:, 1])).translate(tuple(lobe_c)))
gold.append(sphere(0.06, tuple(shaft_end + kn * 0.1)))
# punti a croce che cuciono la criniera al collo
stitches = []
for i in range(1, len(crest) - 1, 2):
    c = np.asarray(crest[i][0], float)
    t_ = norm(np.asarray(crest[i + 1][0], float) - np.asarray(crest[i - 1][0], float))
    nn = grad(core, c)
    sd = norm(np.cross(t_, nn))
    for sg in (1, -1):
        a = on_surface(core, c - sd * 0.11 - t_ * 0.04 * sg, 0.015, 3)
        b = on_surface(core, c + sd * 0.11 + t_ * 0.04 * sg, 0.015, 3)
        stitches.append(capsule(tuple(a), tuple(b), 0.018))

# ============================================================ parti
m.add("Body", core0, HIDE, tris=2450, voxel=0.03 * VX)
neck_end = fast_union([ell(NP[-1], (0.17, 0.22, 0.2), axis=NT[-1])], k=0.0)
m.add("Head", shrink(fast_union([head_w], k=0.06, base=neck_end)), HIDE, role="skin", tris=1500, voxel=0.02 * VX)
m.add("Armor", fast_union(armor), BRONZE, material="Metal", role="detail", tris=2600, voxel=0.026 * VX)
m.add("Gold", fast_union(gold), GOLD, material="Foil", role="detail", tris=1700, voxel=0.018 * VX)
m.add("Hair", hair, HAIR, role="detail", tris=1300, voxel=0.024 * VX)
m.add("EmberGlow", fast_union([Hd(e) for e in eyes] + embers), EMBER, material="Neon", role="glow", tris=600,
      voxel=0.014 * VX)
# punte della criniera che ardono come braci: il gioco ci attacca il fuoco
m.add("Flames", fast_union(lock_tips), FIRE, material="Neon", role="glow", tris=420, voxel=0.016 * VX)
m.add("Mouth", Hd(fast_union(dark)), MOUTH, role="eye", tris=320, voxel=0.018 * VX)
m.add("Teeth", Hd(fast_union(teeth)), TOOTH, role="shine", tris=420, voxel=0.013 * VX)
m.add("Dark", fast_union(darks).intersect(halfspace_z(0.0)), DARK, role="detail", tris=700, voxel=0.018 * VX)
for sx, nm in ((1, "WingR"), (-1, "WingL")):
    hind, frame_ = wing_local(sx)
    place = (lambda s: s.rotate(WING_M).translate(tuple(WING_ROOT[1]))) if sx > 0 else \
        (lambda s: s.rotate(WING_M).translate(tuple(WING_ROOT[1])).mirrored())
    piv = tuple(float(v) for v in WING_ROOT[sx])
    m.add(nm, place(hind), WING, role="detail", tris=460, voxel=0.02 * VX, transparency=0.25, reflectance=0.1,
          group=nm, pivot=piv)
    m.add(nm + "Frame", place(frame_), FRAME, role="detail", tris=420, voxel=0.016 * VX, group=nm, pivot=piv)
m.add("Tail", fast_union(seg_l, k=0.04), BRONZE, material="Metal", role="detail", tris=1100, voxel=0.024 * VX,
      group="Tail", pivot=TAIL_PIVOT)
m.add("TailGold", fast_union(seg_g), GOLD, material="Foil", role="detail", tris=600, voxel=0.015 * VX, group="Tail",
      pivot=TAIL_PIVOT)
m.add("Venom", fast_union(venom), VENOM, material="Neon", role="glow", tris=240, voxel=0.018 * VX, group="Tail",
      pivot=TAIL_PIVOT)
m.add("Stitches", fast_union(stitches), THREAD, role="detail", tris=200, voxel=0.013 * VX)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    fit_voxels(m)
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
