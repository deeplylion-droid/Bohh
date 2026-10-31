"""Behemoth (Behemoth) - ricompensa del Sentiero Estremo (demoni biblici).

La bestia colossale dell'abisso: un toro-bisonte gigantesco in posa di carica, con la testa bassa e la fronte
avanti, la gobba enorme sulle spalle e la zampa anteriore destra che raspa il terreno. Il dorso, i fianchi, il
collo e le zampe fino agli stinchi sono corazzati da placche di ossidiana nera sfaccettate e lucide (parte
"Armor", a facce piatte come vetro vulcanico: celle di Voronoi sulla superficie) separate da fessure da cui
filtra la lava incandescente (parte Neon "Rage": il gioco ci attacca le braci; la stessa lava brilla nelle crepe
della pelle delle zampe, nelle narici e in gola). Sulla gobba spunta una cresta di schegge di ossidiana, ognuna
con un colletto di lava alla base. Corna enormi arricciate a spirale come quelle di un ariete, color osso, con
tre anelli di ferro chiodati infilati sopra e le punte in fiamme (parte Neon "Flames"); la coda alzata
(gruppo "Tail": il gioco la fa ondeggiare) brucia in punta. Occhietti piccoli e feroci che brillano sotto le
arcate aggrottate, narici dilatate piene di braci da cui escono sbuffi di fumo, ghigno a fauci socchiuse con
file di denti aguzzi e la gola che arde. Ai polsi e a un garretto ceppi di ferro con le catene spezzate che si
trascinano a terra.
Tocco "toy horror": la grande placca della fronte e' spaccata e ricucita alla buona con grossi punti a croce,
e la lava filtra dalla cucitura.
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
from lib.sdf import (SDF, bezier, box, capsule, crystal, ellipsoid, euler, halfspace_z, project,  # noqa: E402
                     round_cone, smax, smin, sphere, tube, union)
from lib.toy import Model  # noqa: E402

DRAFT = os.environ.get("DRAFT", "") == "1"
VX = 1.35 if DRAFT else 1.0  # bozza: voxel piu' grossi per iterare in fretta
rng = np.random.default_rng(666)
T0 = time.time()


def log(msg):
    print(f"[behemoth {time.time() - T0:6.1f}s] {msg}", flush=True)


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


# ============================================================ colori
OBSIDIAN = (40, 32, 52)     # placche di ossidiana nero-viola, lucide
HIDE = (84, 26, 32)         # pelle bruciata rosso scuro sotto la corazza
LAVA = (255, 92, 16)        # lava nelle fessure (Neon)
FIRE = (255, 140, 30)       # fiamme sulle punte delle corna (Neon)
EYE_GLOW = (255, 214, 64)
MOUTH = (44, 10, 14)
TOOTH = (246, 236, 214)
BONE = (226, 208, 172)      # corna color osso
IRON = (118, 114, 128)
SMOKE = (196, 188, 194)
THREAD = (240, 224, 190)

m = Model("Behemoth", "pet")

# ============================================================ testa (spazio locale: muso verso -Y)
HEAD_T = np.array([0.0, -1.36, 1.84], dtype=np.float32)
HS = 1.3                           # scala della testa
R_HEAD = euler(16.0, -5.0, 9.0)    # muso abbassato nella carica, girato appena verso chi guarda
JAW_Z = -0.17
HINGE = (0.0, 0.06, JAW_Z)
GAPE = 25.0


def Hd(shape):
    return shape.scale(HS).rotate(R_HEAD).translate(HEAD_T)


def hp(p):
    return R_HEAD @ (HS * np.asarray(p, dtype=np.float32)) + HEAD_T


def hv(v):
    return R_HEAD @ np.asarray(v, dtype=np.float32)


def Jw(shape):
    return shape.rot(GAPE, 0, 0, pivot=HINGE)


skull = ellipsoid((0.42, 0.36, 0.33), (0, 0.08, 0.1))
poll = ellipsoid((0.44, 0.2, 0.17), (0, 0.06, 0.26))                     # nuca larga: qui escono le corna
face = tbox(0.02, -0.6, 0.33, 0.25, 0.25, 0.08, JAW_Z - 0.03, JAW_Z - 0.03, 0.1)
nosepad = ellipsoid((0.26, 0.13, 0.15), (0, -0.63, -0.05))
flares = [ellipsoid((0.09, 0.09, 0.085), (sx * 0.14, -0.68, -0.01)) for sx in (1, -1)]   # narici dilatate
cheeks = [ellipsoid((0.17, 0.25, 0.21), (sx * 0.27, -0.1, -0.1)) for sx in (1, -1)]
brows = [capsule((sx * 0.07, -0.42, 0.21), (sx * 0.38, -0.24, 0.34), 0.08) for sx in (1, -1)]
mounds = [ellipsoid((0.1, 0.09, 0.09), (sx * 0.24, -0.3, 0.12)) for sx in (1, -1)]
upper = union(skull, poll, k=0.1)
upper = union(upper, face, k=0.14)
upper = union(upper, nosepad, *cheeks, k=0.08)
upper = union(upper, *flares, k=0.05)
upper = union(upper, *mounds, k=0.05)
upper = union(upper, *brows, k=0.09)
# rughe del ringhio sul dorso del muso
wr = [tube([(-0.2, y + 0.03, -0.0), (-0.1, y, 0.05), (0.0, y - 0.01, 0.065), (0.1, y, 0.05), (0.2, y + 0.03, -0.0)],
           0.03) for y in (-0.36, -0.45)]
upper = union(upper, *wr, k=0.035)
NOSTRILS = [(sx * 0.14, -0.77, -0.035) for sx in (1, -1)]
upper = upper.subtract(union(*[ellipsoid((0.065, 0.08, 0.052), c) for c in NOSTRILS]), k=0.025)
upper = upper.subtract(box((0.7, 0.5, 0.3), (0, HINGE[1] - 0.5, JAW_Z - 0.3)), k=0.012)

jaw = union(tbox(0.04, -0.52, 0.26, 0.23, JAW_Z + 0.05, JAW_Z + 0.05, -0.34, -0.3, 0.08),
            ellipsoid((0.21, 0.11, 0.08), (0, -0.46, -0.31)), k=0.06)
jaw = jaw.subtract(box((0.7, 0.6, 0.3), (0, -0.4, JAW_Z + 0.3)), k=0.012)

# occhietti feroci incassati sotto le arcate
eyes, lids = [], []
for sx in (1, -1):
    p, n = project(upper, (sx * 0.2, -0.2, 0.1), (sx * 0.5, -0.86, 0.0))
    a1 = sx * norm(np.cross((0.0, 0.0, 1.0), n))
    a2 = -sx * n
    a3 = np.cross(a1, a2)
    sl = math.radians(20)
    a1, a3 = a1 * math.cos(sl) + a3 * math.sin(sl), a3 * math.cos(sl) - a1 * math.sin(sl)
    M = np.stack([a1, a2, a3], axis=1).astype(np.float32)
    c = p - n * 0.022
    eyes.append(ellipsoid((0.086, 0.052, 0.056)).rotate(M).translate(c))
    cutp = SDF(lambda q: (0.012 + 0.5 * q[:, 0] - q[:, 2]) / math.sqrt(1.25), (-0.12, -0.12, -0.12), (0.12, 0.12, 0.12))
    lids.append(ellipsoid((0.09, 0.062, 0.066)).intersect(cutp).rotate(M).translate(c))

# orecchie corte, aperte di lato sotto le corna
ears = []
for sx in (1, -1):
    Me = frame((sx * 1.0, 0.35, -0.3), (0, -1.0, 0.1))
    ear = flatten(tube([(0, 0, -0.03), (0, 0, 0.12), (0, -0.02, 0.24)], [0.08, 0.075, 0.02]), 0.45, axis=1)
    ears.append(ear.rotate(Me).translate((sx * 0.38, 0.14, 0.04)))

head_skin = union(union(upper, Jw(jaw), k=0.012), *lids, k=0.012)
head_skin = union(head_skin, *ears, k=0.04)

# bocca: palato e lingua scuri, gola che arde
pal_reg = SDF(lambda p: np.maximum(np.maximum(np.abs(p[:, 0]) - 0.2, p[:, 2] - (JAW_Z + 0.03)),
                                   np.maximum(p[:, 1] - 0.02, -0.56 - p[:, 1])), (-0.21, -0.57, JAW_Z - 0.05),
              (0.21, 0.02, JAW_Z + 0.03))
jaw_reg = SDF(lambda p: np.maximum(np.maximum(np.abs(p[:, 0]) - 0.19, (JAW_Z - 0.03) - p[:, 2]),
                                   np.maximum(p[:, 1] - 0.02, -0.48 - p[:, 1])), (-0.2, -0.49, JAW_Z - 0.03),
              (0.2, 0.02, JAW_Z + 0.05))
dark = [thin(upper, 0.006, 0.07).intersect(pal_reg), Jw(thin(jaw, 0.006, 0.07).intersect(jaw_reg))]
Rinv = euler(-GAPE, 0, 0)
piv = np.asarray(HINGE, dtype=np.float32)


def wedge(p):
    q = (p - piv) @ Rinv.T + piv
    return np.maximum(np.maximum(p[:, 2] - (JAW_Z + 0.004), (JAW_Z - 0.004) - q[:, 2]),
                      np.maximum(np.abs(p[:, 0]) - 0.21, np.maximum(p[:, 1] - 0.06, -0.12 - p[:, 1])))


dark.append(SDF(wedge, (-0.21, -0.12, JAW_Z - 0.3), (0.21, 0.06, JAW_Z + 0.01)))
dark += [ellipsoid((0.055, 0.06, 0.045), (c[0] * 0.96, -0.72, c[2])) for c in NOSTRILS]
gullet = [ellipsoid((0.13, 0.12, 0.05), (0, -0.12, JAW_Z - 0.035)).rot(GAPE * 0.5, 0, 0, pivot=HINGE)]   # gola che arde
nostril_glow = [ellipsoid((0.045, 0.05, 0.035), (c[0] * 0.97, -0.735, c[2])) for c in NOSTRILS]

# denti: zanne agli angoli e file di denti aguzzi
teeth, bases_up, bases_lo = [], [], []
for a, big in ((-64, True), (-42, False), (-21, False), (0, False), (21, False), (42, False), (64, True)):
    d = (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0.0)
    p, n = project(upper, (0, -0.3, JAW_Z + 0.012), d)
    b = p - norm((n[0], n[1], 0.0)) * 0.03
    L = 0.2 if big else 0.085
    teeth.append(round_cone((b[0], b[1], JAW_Z + 0.03), (b[0], b[1] - 0.015, JAW_Z - L), 0.042 if big else 0.027, 0.01))
    bases_up.append((b[0], b[1], JAW_Z + 0.03))
for y in (-0.27, -0.18):
    for sx in (1, -1):
        p, n = project(upper, (0, y, JAW_Z + 0.012), (sx, 0, 0))
        b = p - np.array([sx * 0.03, 0, 0])
        teeth.append(round_cone((b[0], b[1], JAW_Z + 0.03), (b[0], b[1], JAW_Z - 0.07), 0.026, 0.01))
        bases_up.append((b[0], b[1], JAW_Z + 0.03))
for a, big in ((-56, True), (-28, False), (0, False), (28, False), (56, True)):
    d = (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0.0)
    p, n = project(jaw, (0, -0.28, JAW_Z - 0.012), d)
    b = p - norm((n[0], n[1], 0.0)) * 0.03
    L = 0.11 if big else 0.075
    teeth.append(Jw(round_cone((b[0], b[1], JAW_Z - 0.03), (b[0], b[1] - 0.01, JAW_Z + L), 0.034 if big else 0.026,
                               0.01)))
    bases_lo.append((b[0], b[1], JAW_Z - 0.03))


def row_bar(bases):
    pts = sorted(bases, key=lambda q: math.atan2(q[0], -q[1]))
    return tube(pts, 0.016)


teeth += [row_bar(bases_up), Jw(row_bar(bases_lo))]

# corna enormi arricciate a spirale: escono dalla nuca, girano all'indietro e in basso, poi puntano avanti
HORN_PATHS = []
HORN_CTRL = [(0.25, 0.05, 0.27), (0.46, 0.15, 0.5), (0.72, 0.33, 0.52), (0.89, 0.42, 0.28), (0.92, 0.28, 0.0),
             (0.85, 0.03, -0.12), (0.84, -0.2, -0.02), (0.93, -0.38, 0.18), (1.0, -0.46, 0.42)]
for sx in (1, -1):
    HORN_PATHS.append(catmull([(sx * x, y, z) for x, y, z in HORN_CTRL], 6))


def horn_radius(u):
    base = 0.21 * (1 - 0.87 * u ** 1.1) + 0.012
    ridge = 0.0
    return base * (1 + ridge)


horn_bone, horn_fire, horn_flames = [], [], []
for P in HORN_PATHS:
    n = len(P)
    rad = [horn_radius(i / (n - 1)) for i in range(n)]
    cut = int(n * 0.82)
    horn_bone.append(tube([tuple(q) for q in P[:cut + 1]], rad[:cut + 1]))
    horn_fire.append(tube([tuple(q) for q in P[cut - 1:]], rad[cut - 1:]).offset(0.01))
    tip, d = P[-1], norm(P[-1] - P[-4])
    sx = 1 if tip[0] > 0 else -1
    for tilt, L, fk, r0 in ((0.0, 0.5, 0.55, 0.09), (0.8 * sx, 0.34, 0.0, 0.07), (-0.6 * sx, 0.32, 0.0, 0.065),
                            (0.3 * sx, 0.26, 0.0, 0.06)):
        up = norm(d * 0.4 + np.array([tilt * 0.55, 0.15, 1.0]))
        horn_flames.append(flame(L, r0, bend=0.6, wig=0.05, flat=0.72, fork=fk).rotate(frame(up, (0, 1, 0))).translate(
            tip - d * 0.04))

# ============================================================ corpo (spazio Blender)
chest = ellipsoid((0.8, 0.66, 0.74), (0, -0.46, 1.8))
withers = ellipsoid((0.7, 0.56, 0.55), (0, -0.44, 2.3))
hump = ellipsoid((0.58, 0.6, 0.42), (0, -0.24, 2.52))
barrel = ellipsoid((0.6, 0.56, 0.54), (0, 0.28, 1.86))
rump = ellipsoid((0.48, 0.42, 0.44), (0, 0.74, 1.9))
torso = union(chest, withers, hump, k=0.3)
torso = union(torso, barrel, rump, k=0.32)
pecs = [ellipsoid((0.33, 0.26, 0.38), (sx * 0.32, -0.96, 1.66)) for sx in (1, -1)]
delts = [ellipsoid((0.33, 0.44, 0.48), (sx * 0.6, -0.46, 1.84)) for sx in (1, -1)]
torso = union(torso, *pecs, *delts, k=0.16)
NECK_A, NECK_B = (0, -0.58, 2.1), tuple(hp((0, 0.2, 0.06)))
neck = round_cone(NECK_A, NECK_B, 0.6, 0.46)
dewlap = ellipsoid((0.32, 0.36, 0.36), tuple(hp((0, 0.06, -0.42))))       # giogaia sotto la gola

HOOVES = []   # (centro della pianta, direzione avanti, scala, sollevato)
LEG_AXES = []  # (ginocchio/garretto, piede, raggio) per i ceppi


def front_leg(sx, raised=False):
    sh = np.array([sx * 0.6, -0.52, 1.72])
    el = np.array([sx * 0.68, -0.6, 1.2])
    if raised:   # zampa che raspa il terreno: ginocchio piegato in avanti, zoccolo sollevato all'indietro
        kn = np.array([sx * 0.7, -1.06, 0.8])
        ft = np.array([sx * 0.72, -0.86, 0.46])
        fwd = norm((sx * 0.05, -0.45, -1.0))
    else:
        kn = np.array([sx * 0.68, -0.8, 0.66])
        ft = np.array([sx * 0.68, -0.9, 0.24])
        fwd = norm((sx * 0.1, -1.0, 0.0))
    parts = [round_cone(sh, el, 0.43, 0.32),
             ell(mix(sh, el, 0.45) + np.array([sx * 0.05, -0.08, 0]), (0.34, 0.34, 0.44), axis=el - sh),
             round_cone(el, kn, 0.32, 0.23),
             ell(mix(el, kn, 0.3) + np.array([0, -0.04, 0]), (0.26, 0.26, 0.34), axis=kn - el),
             round_cone(kn, ft, 0.23, 0.21)]
    HOOVES.append((ft, fwd, 1.05, raised))
    LEG_AXES.append((kn, ft, 0.215))
    return union(*parts, k=0.08)


def hind_leg(sx):
    hip = np.array([sx * 0.44, 0.8, 1.78])
    st = np.array([sx * 0.52, 0.56, 1.24])
    hk = np.array([sx * 0.52, 0.98, 0.72])
    ft = np.array([sx * 0.52, 0.88, 0.24])
    parts = [ell((sx * 0.47, 0.7, 1.52), (0.37, 0.5, 0.58), axis=(0, -0.3, 1)),     # coscia
             round_cone(hip, st, 0.33, 0.24),
             round_cone(st, hk, 0.24, 0.17),
             ell(mix(st, hk, 0.4) + np.array([0, 0.06, 0.04]), (0.2, 0.22, 0.28), axis=hk - st),   # polpaccio
             round_cone(hk, ft, 0.17, 0.2)]
    HOOVES.append((ft, norm((sx * 0.05, -1.0, 0.0)), 1.0, False))
    LEG_AXES.append((hk, ft, 0.175))
    return union(*parts, k=0.08)


legs = [front_leg(1, raised=True), front_leg(-1), hind_leg(1), hind_leg(-1)]

# coda alzata che si inarca sopra la groppa: la punta brucia
TAIL_PTS = bezier((0, 1.04, 2.12), (0, 1.36, 2.32), (0.06, 1.34, 2.68), (0.12, 1.1, 2.84), 12)
tail = tube(TAIL_PTS, taper(13, 0.15, 0.065))

core0 = union(torso, neck, k=0.22)
core0 = fast_union(legs, k=0.1, base=core0)
core0 = fast_union([dewlap], k=0.1, base=core0)
core0 = shrink(core0.intersect(halfspace_z(0.0)))
head_w = Hd(head_skin)
core = shrink(fast_union([head_w], k=0.1, base=core0))
log("corpo pronto")

# ============================================================ placche di ossidiana (celle di Voronoi sulla superficie)
SPACING = 0.37
sv, _sf, sn = mesh_sdf(core, 0.045)
pick = poisson_pick(sv, SPACING, seed=7)
SEEDS, SEED_N = sv[pick].astype(np.float64), sn[pick].astype(np.float64)
# fronte: due placche (destra e sinistra) separate da una crepa centrale, tolti i semi automatici li' vicino
FH_C, FH_N = project(head_w, hp((0, -0.12, 0.05)), hv((0, -0.5, 0.86)))
FH_X = hv((1.0, 0.0, 0.0))
keep = np.linalg.norm(SEEDS - FH_C, axis=1) > 0.4
SEEDS, SEED_N = SEEDS[keep], SEED_N[keep]
FH_SEEDS = []
for sx in (1, -1):
    p, n = project(head_w, hp((sx * 0.13, -0.08, 0.05)), hv((sx * 0.2, -0.5, 0.86)))
    FH_SEEDS.append((p, n))
SEEDS = np.vstack([SEEDS] + [p[None] for p, _ in FH_SEEDS])
SEED_N = np.vstack([SEED_N] + [n[None] for _, n in FH_SEEDS])
FOREHEAD = np.zeros(len(SEEDS), dtype=bool)
FOREHEAD[-2:] = True


def plated_mask(p):
    """Dove crescono le placche: dorso, fianchi, spalle, cosce, collo (non pancia, zampe basse, testa)."""
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    q = (p - HEAD_T) @ R_HEAD / HS       # coordinate locali della testa
    in_head = (np.abs(q[:, 0]) < 0.6) & (q[:, 1] < 0.34) & (q[:, 1] > -0.95) & (q[:, 2] > -0.6)
    body_line = 1.46 - 0.1 * np.clip((y + 0.3) / 1.2, -1, 1)          # sotto questa quota: pancia scoperta
    legs_line = np.where(np.abs(x) > 0.46, np.where(y < 0, 0.62, 0.72), body_line)
    ok = z > legs_line
    ok &= ~in_head
    ok &= ~((y > 0.98) & (z > 2.08) & (np.abs(x) < 0.3))               # coda
    return ok


PLATED = plated_mask(SEEDS) | FOREHEAD
LAVA_CELL = PLATED & ~FOREHEAD
log(f"semi delle placche: {len(SEEDS)} ({int(PLATED.sum())} con placca)")
VOR = Voronoi(SEEDS)
# faccia piatta di ogni placca: piano appena inclinato a caso, alzato di h sopra il seme
tilt = rng.normal(0, 0.17, (len(SEEDS), 3))
FACE_N = np.array([norm(n + t - n * float(np.dot(t, n))) for n, t in zip(SEED_N, tilt)], dtype=np.float32)
FACE_H = rng.uniform(0.05, 0.075, len(SEEDS)).astype(np.float32)
FACE_H += (0.035 * np.clip((SEEDS[:, 2] - 2.32) / 0.5, 0, 1)).astype(np.float32)   # cresta del dorso piu' spessa
for j in np.nonzero(FOREHEAD)[0]:   # placche della fronte: spesse, inclinate verso l'esterno (a scudo)
    sxj = 1.0 if float(np.dot(SEEDS[j] - FH_C, FH_X)) > 0 else -1.0
    FACE_N[j] = norm(FH_N + FH_X * sxj * 0.32).astype(np.float32)
    FACE_H[j] = 0.075
GAP = 0.04
GROOVE = 0.02
H_MIN, H_MAX = 0.032, 0.12
SEEDS32 = SEEDS.astype(np.float32)


def region(i0, ed, mask):
    """< 0 dentro le celle 'mask', > 0 fuori (distanza dal bordo fra i due tipi di cella)."""
    return np.where(mask[i0], -ed, ed)


def armor_f(p):
    """Corazza piena: placche rialzate e, sotto le fessure, il corpo fino al fondo del solco."""
    i0, e, ed = VOR.query(p, PLATED)
    c = core(p)
    plane = np.einsum("ij,ij->i", p - SEEDS32[i0], FACE_N[i0]) - FACE_H[i0]
    top = np.maximum(np.minimum(plane, c - H_MIN), c - H_MAX)
    solid = np.minimum(smax(top, GAP - e, 0.018), c + GROOVE)
    return np.maximum(solid, region(i0, ed, PLATED)).astype(np.float32)


def lava_f(p):
    """Lava sul fondo delle fessure fra le placche."""
    i0, e, ed = VOR.query(p, LAVA_CELL)
    c = core(p)
    d = np.maximum(np.maximum(c - 0.006, -c - 0.09), e - (GAP + 0.01))
    return np.maximum(d, region(i0, ed, LAVA_CELL)).astype(np.float32)


def hide_f(p):
    """Pelle scoperta: il corpo fuori dalle celle con placca."""
    i0, e, ed = VOR.query(p, PLATED)
    return np.maximum(core0(p), -region(i0, ed, PLATED)).astype(np.float32)


armor = SDF(armor_f, core.lo - 0.12, core.hi + 0.12)
lava_net = SDF(lava_f, core.lo - 0.05, core.hi + 0.05)
hide = SDF(hide_f, core0.lo, core0.hi)

# crepe di lava sulla pelle scoperta delle zampe (linee frastagliate)
leg_cracks = []
for a, b, o in ((np.array([0.86, -0.7, 1.1]), np.array([0.84, -0.98, 0.68]), np.array([0.62, -0.74, 0.95])),
                (np.array([-0.86, -0.62, 1.1]), np.array([-0.84, -0.86, 0.55]), np.array([-0.62, -0.68, 0.9])),
                (np.array([0.7, 0.66, 1.08]), np.array([0.66, 1.06, 0.68]), np.array([0.5, 0.8, 0.95])),
                (np.array([-0.7, 0.66, 1.08]), np.array([-0.66, 1.06, 0.68]), np.array([-0.5, 0.8, 0.95]))):
    pts = zigzag(a, b, 5, 0.04, a - o)
    q, nr = project_many(core0, [o], [np.asarray(p_, float) - o for p_ in pts])
    k = len(q)
    radii = [0.032 * (0.45 + 0.55 * math.sin(math.pi * (0.05 + 0.9 * j / (k - 1)))) for j in range(k)]
    leg_cracks.append(tube([tuple(p_ - n_ * r_ * 0.3) for p_, n_, r_ in zip(q, nr, radii)], radii))

# bava di lava che cola dagli angoli della bocca (fuori dalle labbra, appesa verso il basso)
drool = []
for sx, L in ((1, 0.2), (-1, 0.13)):
    q, qn = project(head_skin, (sx * 0.2, -0.15, -0.14), (sx, -0.3, -0.25))
    p0 = hp(q - qn * 0.01)
    p1 = p0 + np.array([0.0, -0.01, -L * 0.55])
    p2 = p0 + np.array([0.0, -0.015, -L])
    drool += [tube([tuple(p0), tuple(p1), tuple(p2)], [0.034, 0.02, 0.026]),
              sphere(0.042, tuple(p2 + np.array([0, 0, -0.01])))]

# crepa al centro della fronte (fra le due placche): la lava filtra dalla cucitura
fh_line = [hp((0, y, 0.0)) for y in (-0.44, -0.32, -0.2, -0.08, 0.04, 0.12)]
FH_O = hp((0, -0.12, -0.08))
fh_pts, fh_nrm = project_many(head_w, [FH_O], [q - FH_O + hv((0, 0, 0.45)) for q in fh_line])
crack_fh = tube([tuple(p_ + n_ * 0.012) for p_, n_ in zip(fh_pts, fh_nrm)], [0.026, 0.036, 0.04, 0.04, 0.036, 0.026])

# schegge di ossidiana sulla gobba e sulle spalle: cresta centrale e due file laterali
shards = []
SHARD_BASES = []
for y, L, r in ((-0.88, 0.36, 0.085), (-0.64, 0.58, 0.12), (-0.38, 0.76, 0.14), (-0.1, 0.66, 0.13), (0.18, 0.5, 0.11),
                (0.44, 0.34, 0.085)):
    p, n = project(core, (0, y, 1.95), (0, 0.08, 1))
    ax = norm(n + np.array([0, 0.55, 0.0]))
    shards.append(crystal(L, r, tip=0.5, sides=5).rotate(frame(ax, (1, 0, 0))).translate(tuple(p - ax * 0.09)))
    SHARD_BASES.append((p, ax, r))
for sx in (1, -1):
    for y, z, L, r in ((-0.7, 2.44, 0.4, 0.09), (-0.42, 2.6, 0.52, 0.105), (-0.14, 2.56, 0.44, 0.095),
                       (0.14, 2.38, 0.32, 0.08), (0.4, 2.14, 0.24, 0.065)):
        p, n = project(core, (0, y, z - 0.6), (sx * 0.6, 0.0, 0.8))
        ax = norm(n + np.array([sx * 0.15, 0.5, 0.35]))
        shards.append(crystal(L, r, tip=0.5, sides=5).rotate(frame(ax, (0, 1, 0))).translate(tuple(p - ax * 0.08)))
        SHARD_BASES.append((p, ax, r))
    for y, z, L, r in ((-0.5, 2.04, 0.26, 0.07), (-0.2, 2.12, 0.22, 0.06)):     # spalle
        p, n = project(core, (sx * 0.2, y, z - 0.2), (sx * 1.0, -0.1, 0.25))
        ax = norm(n + np.array([0, 0.45, 0.3]))
        shards.append(crystal(L, r, tip=0.5, sides=5).rotate(frame(ax, (0, 1, 0))).translate(tuple(p - ax * 0.07)))

# colletti di lava alla base delle schegge (sono emerse dalla lava)
shard_lava = [ell(p + ax * 0.03, (r * 1.45, r * 1.45, 0.05), axis=ax) for p, ax, r in SHARD_BASES]

# ============================================================ zoccoli spaccati di ossidiana
hooves = []
for ft, fwd, s, raised in HOOVES:
    side = norm(np.cross(fwd, (0, 0, 1))) if abs(fwd[2]) < 0.9 else np.array([1.0, 0, 0])
    up = norm(np.cross(side, fwd))
    base = ft + np.array([0, 0, -0.24]) if not raised else ft - up * 0.24
    for sg in (1, -1):
        hc = base + side * sg * 0.088 * s + fwd * 0.06 * s + up * 0.11 * s
        hooves.append(ell(hc, (0.12 * s, 0.2 * s, 0.15 * s), axis=up, side=side))
    hooves.append(ell(base + up * 0.2 * s, (0.23 * s, 0.23 * s, 0.075 * s), axis=up, side=side))   # corona
hoof_sdf = fast_union(hooves, k=0.02).intersect(halfspace_z(0.0))

# ============================================================ ceppi di ferro e catene spezzate
cuffs, chain = [], []


def chain_run(start, dirs, n, size=1.0):
    """Catena di n maglie a partire da 'start' lungo le direzioni dirs (una per maglia); l'ultima e' spezzata."""
    out = []
    p = np.asarray(start, float)
    for i in range(n):
        d = norm(dirs[min(i, len(dirs) - 1)])
        ref = np.array([0, 0, 1.0]) if abs(d[2]) < 0.8 else np.array([1.0, 0, 0])
        nrm = np.cross(d, ref) if i % 2 == 0 else ref - d * float(np.dot(ref, d))
        c = p + d * 0.075 * size
        lk = chain_link(c, d, nrm, 0.04 * size, 0.055 * size, 0.024 * size)
        if i == n - 1:   # maglia spezzata: aperta in punta
            lk = lk.subtract(sphere(0.045 * size, tuple(c + d * 0.08 * size)))
        out.append(lk)
        p = p + d * 0.13 * size
    return out


for li, (a, b, r) in enumerate(LEG_AXES[:3]):
    t = (0.5, 0.42, 0.4)[li]
    c = mix(a, b, t)
    ax = norm(a - b)
    M = frame(ax, (0, -1, 0))
    cuffs.append(band(r + 0.035, 0.042, 0.075).rotate(M).translate(tuple(c)))
    for ang in np.linspace(0, 2 * math.pi, 7)[:-1]:   # borchie sul ceppo
        d = M @ np.array([math.cos(ang), math.sin(ang), 0.0], dtype=np.float32)
        cuffs.append(sphere(0.042, tuple(c + d * (r + 0.078))))
    out_dir = norm(np.array([1.0 if li != 1 else -1.0, 0.25, 0.0]))
    out_dir = norm(out_dir - ax * float(np.dot(out_dir, ax)))
    ring_c = c + out_dir * (r + 0.1)
    chain.append(chain_link(ring_c, ax, out_dir, 0.0, 0.056, 0.024))
    if li == 0:     # zampa alzata: la catena penzola
        chain += chain_run(ring_c + np.array([0, 0, -0.04]), [(0, 0.15, -1.0)], 3)
    else:           # zampe a terra: la catena cade e si trascina sul terreno
        sx = -1.0 if li == 1 else 1.0
        chain += chain_run(ring_c + np.array([0, 0, -0.04]), [(sx * 0.15, 0.1, -1.0), (sx * 0.5, 0.35, -0.9),
                                                              (sx * 0.8, 0.6, -0.05)], 3)
for P in HORN_PATHS:   # anelli di ferro chiodati infilati sulle corna: la bestia era stata incatenata
    n = len(P)
    for u in (0.2, 0.4, 0.58):
        i = int(u * (n - 1))
        c = P[i]
        ax = norm(P[min(i + 1, n - 1)] - P[max(i - 1, 0)])
        r = horn_radius(i / (n - 1))
        M = frame(ax, (0, 0, 1))
        cuffs.append(Hd(band(r + 0.012, 0.03, 0.045).rotate(M).translate(tuple(c))))
        for ang in np.linspace(0, 2 * math.pi, 6)[:-1]:
            d = M @ np.array([math.cos(ang), math.sin(ang), 0.0], dtype=np.float32)
            cuffs.append(Hd(sphere(0.032, tuple(c + d * (r + 0.042)))))
cuff_sdf = fast_union(cuffs)
chain_sdf = fast_union(chain).intersect(halfspace_z(0.004))

# ============================================================ fumo dalle narici (sbuffi da cartone animato)
smoke = []
srng = np.random.default_rng(3)
for sx, c in zip((1, -1), NOSTRILS):
    o = hp(np.array(c) + np.array([0, -0.05, -0.03]))
    a = norm(hv((sx * 0.9, -0.35, -0.25)))       # lo sbuffo esce di lato e poi sale arricciandosi
    up = np.array([0, 0, 1.0])
    for k, (da, du, r) in enumerate(((0.05, -0.01, 0.04), (0.14, 0.0, 0.06), (0.25, 0.05, 0.075), (0.3, 0.16, 0.06),
                                     (0.26, 0.25, 0.045))):
        cc = o + a * da + up * du
        smoke.append(sphere(r, tuple(cc)))
        if 1 <= k <= 2:   # gli sbuffi grossi sono grappoli di palline
            for j in range(3):
                off = norm(srng.normal(0, 1, 3) + up * 0.4) * r * 0.7
                smoke.append(sphere(r * srng.uniform(0.6, 0.75), tuple(cc + off)))
smoke_sdf = union(*smoke, k=0.03)

# ============================================================ punti a croce sulla crepa della fronte
stitches = []
for j in (1, 2, 3):
    c, nn = fh_pts[j], fh_nrm[j]
    tdir = norm(fh_pts[j + 1] - fh_pts[j - 1])
    sd = norm(np.cross(tdir, nn))
    for sg in (1, -1):
        a = c - sd * 0.11 - tdir * 0.045 * sg + nn * 0.08
        b = c + sd * 0.11 + tdir * 0.045 * sg + nn * 0.08
        stitches.append(capsule(tuple(on_surface(armor, a, 0.008, 3)), tuple(on_surface(armor, b, 0.008, 3)), 0.026))
stitch_sdf = fast_union(stitches)

# ============================================================ parti
m.add("Body", hide, HIDE, tris=2100, voxel=0.045 * VX)
neck_end = round_cone(tuple(mix(NECK_A, NECK_B, 0.55)), NECK_B, 0.6 * 0.45 + 0.46 * 0.55 - 0.01, 0.45)
m.add("Head", shrink(fast_union([head_w, dewlap], k=0.1, base=neck_end)), HIDE, role="skin", tris=2100,
      voxel=0.034 * VX)
m.add("Armor", fast_union([armor] + shards), OBSIDIAN, role="detail", tris=4200, voxel=0.05 * VX, reflectance=0.12,
      smooth=False)
m.add("Rage", fast_union([lava_net, crack_fh] + leg_cracks + shard_lava + drool + [Hd(x) for x in gullet + nostril_glow]), LAVA, material="Neon",
      role="glow", tris=1800, voxel=0.05 * VX)
m.add("Horns", Hd(union(*horn_bone)), BONE, role="detail", tris=1100, voxel=0.04 * VX)
tail_tip, tail_d = np.asarray(TAIL_PTS[-1]), norm(np.asarray(TAIL_PTS[-1]) - np.asarray(TAIL_PTS[-3]))
tail_fire = [flame(L, r0, bend=0.5, wig=0.05, flat=0.7, fork=fk).rotate(
    frame(norm(np.array([tl, 0.2, 1.0]) + tail_d * 0.3), (0, 1, 0))).translate(tail_tip - tail_d * 0.04)
    for tl, L, r0, fk in ((0.0, 0.42, 0.09, 0.5), (0.7, 0.3, 0.07, 0.0), (-0.7, 0.3, 0.07, 0.0))]
m.add("Flames", fast_union([Hd(x) for x in horn_fire + horn_flames], k=0.02), FIRE, material="Neon",
      role="glow", tris=760, voxel=0.028 * VX)
# coda (gruppo "Tail": il gioco la fa ondeggiare attorno all'attaccatura) con la fiamma in punta
TAIL_PIVOT = tuple(float(v) for v in TAIL_PTS[0])
m.add("Tail", union(tail, sphere(0.17, TAIL_PIVOT), k=0.05), HIDE, role="skin", tris=320, voxel=0.03 * VX,
      group="Tail", pivot=TAIL_PIVOT)
m.add("TailFire", fast_union(tail_fire, k=0.02), FIRE, material="Neon", role="glow", tris=260, voxel=0.022 * VX,
      group="Tail", pivot=TAIL_PIVOT)
m.add("EyeGlow", fast_union([Hd(e) for e in eyes]), EYE_GLOW, material="Neon", role="glow", tris=160, voxel=0.017 * VX)
m.add("Mouth", Hd(fast_union(dark)), MOUTH, role="eye", tris=360, voxel=0.034 * VX)
m.add("Teeth", Hd(fast_union(teeth)), TOOTH, role="shine", tris=440, voxel=0.022 * VX)
m.add("Hooves", hoof_sdf, OBSIDIAN, role="detail", tris=380, voxel=0.042 * VX, reflectance=0.12)
m.add("Shackles", cuff_sdf, IRON, material="Metal", role="detail", tris=800, voxel=0.026 * VX)
m.add("Chains", chain_sdf, IRON, material="Metal", role="detail", tris=620, voxel=0.019 * VX)
m.add("Smoke", smoke_sdf, SMOKE, role="detail", tris=300, voxel=0.025 * VX, transparency=0.2)
m.add("Stitches", stitch_sdf, THREAD, role="detail", tris=220, voxel=0.018 * VX)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    fit_voxels(m)
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
