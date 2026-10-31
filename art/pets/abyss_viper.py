"""Vipera degli Abissi (AbyssViper) - pet del Percorso Estremo (pesci abissali).

Un pesce vipera lunghissimo, sospeso nel buio come un serpente marino: il corpo blu-nero iridescente si avvolge
in una grande S verticale, con la testa in alto protesa verso chi guarda e la coda a forbice in basso. Le fauci sono
spalancate e le zanne, enormi e ricurve come sciabole, non ci stanno in bocca: le punte brillano di magenta (parte Neon
"Aura": il gioco ci attacca le scintille rosa-viola); brillano anche le punte delle pinne. Una fila
di fotofori magenta corre lungo tutto il ventre seguendo la S, una banda viola metallizzata (il riflesso iridescente)
segue il fianco, le pinne sono lame affilate. Dal mento pende un barbiglio sottile con un bulbo luminoso in fondo
(parte Neon "Bubbles": il gioco ci attacca le bollicine). Occhi grandi e luminosi sotto sopracciglia aggrottate.
Tocco "toy horror": una cicatrice ricucita a punti incrociati attraversa la testa.
"""
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, box, capsule, ellipsoid, euler, prism, project, round_cone, smin, sphere, torus,  # noqa: E402
                     tube, union)
from lib.sdf import tube as _tube  # noqa: E402
from lib.toy import Model  # noqa: E402


def tube(points, radii, k=0.0):
    """Come lib.sdf.tube, ma toglie i punti consecutivi coincidenti (un tratto lungo zero rovina il campo)."""
    pts = [np.asarray(q, dtype=np.float64) for q in points]
    rr = [float(radii)] * len(pts) if isinstance(radii, (int, float)) else [float(r) for r in radii]
    keep = [0] + [i for i in range(1, len(pts)) if np.linalg.norm(pts[i] - pts[i - 1]) > 1e-6]
    return _tube([tuple(pts[i]) for i in keep], [rr[i] for i in keep], k=k)

DRAFT = os.environ.get("DRAFT", "") == "1"
VX = 1.35 if DRAFT else 1.0
T0 = time.time()
rng = np.random.default_rng(7)


def log(msg):
    print(f"[viper {time.time() - T0:6.1f}s] {msg}", flush=True)


# ============================================================ helper (lib/ non si modifica: definiti qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


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


def catmull(points, n_per=10):
    """Curva di Catmull-Rom che passa per i punti (polilinea fitta)."""
    P = np.asarray(points, dtype=np.float64)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n_per, endpoint=False):
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return np.array(out)


def resample(pts, step):
    pts = np.asarray(pts, dtype=np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(int(round(cum[-1] / step)), 1)
    ss = np.linspace(0.0, cum[-1], n + 1)
    return np.array([np.interp(ss, cum, pts[:, k]) for k in range(3)]).T, ss


def poly2d(pts):
    """Distanza con segno da un poligono 2D: f(u, v)."""
    pts = np.asarray(pts, dtype=np.float32)
    keep = [i for i in range(len(pts)) if np.linalg.norm(pts[i] - pts[i - 1]) > 1e-7]
    pts = pts[keep]

    def d2(px, py):
        d = np.full(px.shape, np.inf, dtype=np.float32)
        s = np.ones(px.shape, dtype=np.float32)
        for i in range(len(pts)):
            vi, vj = pts[i], pts[i - 1]
            ex, ey = vj[0] - vi[0], vj[1] - vi[1]
            wx, wy = px - vi[0], py - vi[1]
            t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey), 0.0, 1.0)
            bx, by = wx - ex * t, wy - ey * t
            d = np.minimum(d, bx * bx + by * by)
            c1, c2, c3 = py >= vi[1], py < vj[1], ex * wy > ey * wx
            s = np.where((c1 & c2 & c3) | (~c1 & ~c2 & ~c3), -s, s)
        return s * np.sqrt(d)

    return d2


def ell2(x, y, a, b):
    """Distanza (approssimata) da un'ellisse di semiassi a, b."""
    k0 = np.sqrt((x / a) ** 2 + (y / b) ** 2)
    k1 = np.sqrt((x / (a * a)) ** 2 + (y / (b * b)) ** 2)
    return np.where(k1 > 1e-7, k0 * (k0 - 1.0) / np.maximum(k1, 1e-7), -np.minimum(a, b))


def shell_paint(base, region, out=0.02, inn=0.05, margin=0.04):
    """Vernice a guscio sottile di 'base' dentro 'region' (base valutata solo vicino alla regione)."""
    def f(p):
        r = region(p)
        d = np.maximum(r, margin).astype(np.float32)
        idx = np.nonzero(r < margin)[0]
        if len(idx):
            c = base(p[idx])
            d[idx] = np.maximum(np.maximum(c - out, -(c + inn)), r[idx])
        return d

    return SDF(f, np.maximum(region.lo, base.lo - out), np.minimum(region.hi, base.hi + out))


def basis(x_dir, y_hint):
    """Colonne: X locale = x_dir, Y locale il piu' vicino possibile a y_hint, Z = X x Y."""
    x = norm(x_dir)
    y = np.asarray(y_hint, dtype=np.float64)
    y = norm(y - x * float(np.dot(y, x)))
    return np.stack([x, y, np.cross(x, y)], axis=1).astype(np.float32)


def place(shape, M, origin):
    return shape.rotate(M).translate(tuple(np.asarray(origin, dtype=np.float64)))


def taper(n, r0, r1, power=1.0):
    return [r0 + (r1 - r0) * (i / (n - 1)) ** power for i in range(n)]


def spike(a, b, r0, r1=0.008, bend=None, n=8):
    """Spina/dente affusolato da a verso b, eventualmente piegato (bend = spostamento del punto medio)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if bend is None:
        return round_cone(tuple(a), tuple(b), r0, r1)
    bend = np.asarray(bend, float)
    pts = bezier(tuple(a), tuple(a + (b - a) / 3 + bend), tuple(a + (b - a) * 2 / 3 + bend), tuple(b), n)
    return tube(pts, taper(n + 1, r0, r1, 0.9))


class Spine:
    """Linea mediana del pesce, fitta, con un sistema di riferimento (T verso la coda, D dorso, L lato +X)."""

    def __init__(self, ctrl, step=0.01, n_per=24, side=(1.0, 0.0, 0.0)):
        P, S = resample(catmull(ctrl, n_per), step)
        T = np.gradient(P, axis=0)
        T /= np.linalg.norm(T, axis=1, keepdims=True)
        U = np.broadcast_to(np.asarray(side, dtype=np.float64), P.shape)
        LAT = U - T * np.einsum("ij,ij->i", U, T)[:, None]
        LAT /= np.linalg.norm(LAT, axis=1, keepdims=True)
        D = np.cross(LAT, T)                 # dorso: perpendicolare alla S, dal lato "esterno" in cima
        self.P, self.S, self.T, self.D = P, S, T, D
        self.LAT = np.cross(T, D)
        self.len = float(S[-1])
        self.tree = cKDTree(P)

    def coords(self, p):
        _, i = self.tree.query(p, workers=2)
        v = p - self.P[i]
        s = self.S[i] + np.einsum("ij,ij->i", v, self.T[i])
        return i, s, np.einsum("ij,ij->i", v, self.LAT[i]), np.einsum("ij,ij->i", v, self.D[i])

    def frame(self, s):
        """Punto e assi (T, D, L) all'ascissa s (oltre le estremita' prosegue dritto)."""
        j = int(np.clip(np.searchsorted(self.S, s), 1, len(self.S) - 1))
        w = float(np.clip((s - self.S[j - 1]) / (self.S[j] - self.S[j - 1]), 0.0, 1.0))
        c = self.P[j - 1] * (1 - w) + self.P[j] * w
        T, D = norm(self.T[j - 1] * (1 - w) + self.T[j] * w), norm(self.D[j - 1] * (1 - w) + self.D[j] * w)
        if s < 0:
            c = self.P[0] + self.T[0] * s
        elif s > self.len:
            c = self.P[-1] + self.T[-1] * (s - self.len)
        return c, T, D, np.cross(T, D)

    def world(self, s, u, w):
        c, T, D, L = self.frame(s)
        return c + L * u + D * w


def swept_body(sp, A, BT, BB, pad=0.0):
    """Corpo a sezione ellittica lungo la spina: semiassi (funzioni dell'ascissa s) laterale A, dorsale BT, ventrale BB."""
    s_tab = np.linspace(0.0, sp.len, 400)
    a_tab, bt_tab, bb_tab = (np.array([fn(s) for s in s_tab]) for fn in (A, BT, BB))

    def f(p):
        i, s, u, w = sp.coords(p)
        sc = np.clip(s, 0.0, sp.len)
        a = np.maximum(np.interp(sc, s_tab, a_tab), 1e-3)
        b = np.maximum(np.where(w > 0, np.interp(sc, s_tab, bt_tab), np.interp(sc, s_tab, bb_tab)), 1e-3)
        d = ell2(u, w, a, b)
        out = np.maximum(-s, s - sp.len)
        return np.where(out > 0, np.sqrt(np.maximum(d, 0.0) ** 2 + out ** 2), d).astype(np.float32)

    r = max(a_tab.max(), bt_tab.max(), bb_tab.max()) + pad
    return SDF(f, sp.P.min(0) - r, sp.P.max(0) + r)


def spine_fin(sp, poly_sw, thick, s_range, w_range, edge=0.3):
    """Pinna sottile nel piano (s, w) della spina: poligono 2D, spessore che si assottiglia verso il bordo."""
    d2 = poly2d(poly_sw)

    def f(p):
        i, s, u, w = sp.coords(p)
        a = d2(s, w)
        b = np.abs(u) - thick * (1.0 - edge * np.clip(1.0 + a / 0.12, 0.0, 1.0))
        return (np.minimum(np.maximum(a, b), 0.0) + np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2)).astype(np.float32)

    pts = [sp.world(s, 0.0, w) for s in np.linspace(*s_range, 12) for w in w_range]
    pts = np.array(pts)
    return SDF(f, pts.min(0) - 0.2, pts.max(0) + 0.2)


def ground(model):
    """Porta il punto piu' basso del modello a z = 0.

    Prima campiona il fondo di ogni parte (veloce), poi rimesha le parti piu' basse con lo stesso mesher della
    build (i dettagli piu' sottili del voxel spariscono dalla mesh: conta la mesh vera, non la forma ideale).
    """
    from lib.mesher import mesh_sdf
    found = []
    for part in model.parts:
        s = part.sdf
        lo, hi = s.lo.astype(np.float64), s.hi.astype(np.float64)
        vox = 0.02
        xs = np.arange(lo[0], hi[0] + vox, vox)
        ys = np.arange(lo[1], hi[1] + vox, vox)
        z = lo[2]
        while z < hi[2]:
            zs = np.arange(z, z + 0.16, vox)
            g = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), -1).reshape(-1, 3).astype(np.float32)
            d = s(g)
            if (d < 0).any():
                found.append((float(g[d < 0][:, 2].min()), part))
                break
            z += 0.16
    low = min(z for z, _ in found)
    zmin = np.inf
    for z, part in found:
        if z > low + 0.08:
            continue
        voxel = part.voxel or model.voxel
        verts, faces, _ = mesh_sdf(part.sdf, voxel)
        while len(faces) > part.tris * 8 and voxel < 2.0:
            voxel *= math.sqrt(len(faces) / (part.tris * 5))
            verts, faces, _ = mesh_sdf(part.sdf, voxel)
        zmin = min(zmin, float(verts[:, 2].min()))
    log(f"punto piu' basso: z = {zmin:.3f}")
    for part in model.parts:
        part.sdf = part.sdf.translate((0.0, 0.0, -zmin))
        if part.pivot is not None:
            part.pivot = (part.pivot[0], part.pivot[1], part.pivot[2] - zmin)




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


def footprint(fx, fy, cy):
    """Ellisse nel piano XY locale (distanza approssimata), per delimitare la bocca."""
    def f(p):
        ex = p[:, 0] / fx
        ey = (p[:, 1] - cy) / fy
        return (np.sqrt(ex * ex + ey * ey) - 1.0) * min(fx, fy)
    return f


def thin(shape, out, inn):
    """Guscio sottile di una forma (per disegni sopra altre parti)."""
    return SDF(lambda p: (lambda d: np.maximum(d - out, -(d + inn)))(shape(p)), shape.lo - out, shape.hi + out)


# ============================================================ palette
SKIN = (20, 26, 64)          # blu-nero (un nero puro in gioco e' piatto)
SHEEN = (116, 74, 226)       # riflesso iridescente viola (Foil)
BELLY = (92, 88, 150)        # ventre argento-lavanda
FIN = (64, 42, 150)          # pinne a lama viola scuro
GLOW = (255, 66, 206)        # fotofori, punte delle zanne, barbiglio (Neon magenta)
EYE = (255, 92, 214)         # occhi (Neon)
PUPIL = (12, 6, 20)
MAW = (40, 6, 36)            # bocca
FANG = (238, 242, 255)       # zanne
THREAD = (240, 230, 210)     # filo della cicatrice
WHITE = (255, 255, 255)

m = Model("AbyssViper", "pet")
SCALE = 0.9

# ============================================================ testa (coordinate locali: cranio nell'origine, muso verso -Y)
HS = 1.55
LEAN = euler(20.0, 0.0, 0.0).astype(np.float64)     # tutta la S inclinata in avanti: la vipera si lancia verso chi guarda
LEAN_C = np.array([0.0, 0.0, 1.4])


def lean(p):
    return LEAN @ (np.asarray(p, dtype=np.float64) - LEAN_C) + LEAN_C


HEAD_T = lean((0.0, -0.98, 2.92))
R_HEAD = euler(-14.0, 0.0, 8.0)       # muso alzato, girato verso la camera 3/4
GAPE = 56.0
JAW_Z = -0.05
HINGE = (0.0, 0.12, JAW_Z)


def H(s):
    return s.scale(HS).rotate(R_HEAD).translate(tuple(HEAD_T))


def hp(p):
    return R_HEAD.astype(np.float64) @ (np.asarray(p, dtype=np.float64) * HS) + HEAD_T


def J(s):
    return s.rot(GAPE, 0, 0, pivot=HINGE)


def jp(p):
    """Punto della mandibola chiusa -> aperta (locale)."""
    q = np.asarray(p, dtype=np.float64) - HINGE
    return euler(GAPE, 0, 0).astype(np.float64) @ q + HINGE


cran = ellipsoid((0.26, 0.3, 0.25), (0, 0.02, 0.07))
occ = ellipsoid((0.21, 0.2, 0.2), (0, 0.24, 0.03))
snout = tbox(0.0, -0.52, 0.2, 0.1, 0.2, 0.09, JAW_Z - 0.03, JAW_Z - 0.02, 0.07)
cheeks = [ellipsoid((0.1, 0.18, 0.12), (sx * 0.17, 0.0, 0.0)) for sx in (1, -1)]
brows = [capsule((sx * 0.07, -0.3, 0.2), (sx * 0.25, -0.05, 0.28), 0.058) for sx in (1, -1)]
upper = union(cran, occ, k=0.12)
upper = union(upper, snout, k=0.12)
upper = union(upper, *cheeks, k=0.07)
upper = union(upper, *brows, k=0.05)
upper = upper.subtract(box((0.6, 0.5, 0.3), (0, HINGE[1] - 0.5, JAW_Z - 0.3)), k=0.012)
jaw = union(tbox(0.14, -0.7, 0.19, 0.085, JAW_Z + 0.04, JAW_Z + 0.04, -0.18, -0.11, 0.05),
            ellipsoid((0.18, 0.16, 0.1), (0, 0.08, -0.1)), ellipsoid((0.08, 0.08, 0.055), (0, -0.62, -0.12)), k=0.06)
jaw = jaw.subtract(box((0.6, 0.6, 0.3), (0, -0.4, JAW_Z + 0.3)), k=0.012)

# occhi grandi a mandorla, luminosi, pupilla a fessura, palpebra arrabbiata; macchia luminosa dietro l'occhio
eye_glow, pupils, shines, photo_head, lids = [], [], [], [], []
for sx in (1, -1):
    p, n = project(upper, (sx * 0.05, -0.16, 0.1), (sx * 0.82, -0.48, 0.24))
    a1 = sx * norm(np.cross((0.0, 0.0, 1.0), n))
    a2 = -sx * n
    a3 = np.cross(a1, a2)
    sl = math.radians(18)
    a1, a3 = a1 * math.cos(sl) + a3 * math.sin(sl), a3 * math.cos(sl) - a1 * math.sin(sl)
    Me = np.stack([a1, a2, a3], axis=1).astype(np.float32)
    c = p - n * 0.024
    eye = ellipsoid((0.15, 0.08, 0.1)).rotate(Me).translate(c)
    eye_glow.append(eye)
    pupils.append(thin(eye, 0.007, 0.026).intersect(ellipsoid((0.03, 0.07, 0.086)).rotate(Me).translate(c + n * 0.075)))
    cutp = SDF(lambda q: (0.012 + 0.45 * q[:, 0] - q[:, 2]) / math.sqrt(1 + 0.45 ** 2), (-0.16, -0.16, -0.16), (0.16, 0.16, 0.16))
    lids.append(ellipsoid((0.162, 0.092, 0.11)).intersect(cutp).rotate(Me).translate(c))
    shines.append(sphere(0.025, tuple(c + n * 0.078 + a3 * 0.014 - a1 * sx * 0.055)))
    q, nq = project(upper, (sx * 0.05, 0.12, 0.02), (sx * 0.9, 0.2, -0.1))
    photo_head.append(place(ellipsoid((0.07, 0.04, 0.025)), np.stack([norm(np.cross(nq, (0, 0, 1))), np.cross(nq, norm(np.cross(nq, (0, 0, 1)))), nq], axis=1).astype(np.float32), q))

# bocca: palato e mandibola scuri, gola
dark = []
pal_fp, jaw_fp = footprint(0.1, 0.3, -0.34), footprint(0.088, 0.33, -0.38)
pal_reg = SDF(lambda p: np.maximum(pal_fp(p), p[:, 2] - (JAW_Z + 0.03)), (-0.11, -0.66, JAW_Z - 0.05), (0.11, -0.02, JAW_Z + 0.03))
jaw_reg = SDF(lambda p: np.maximum(jaw_fp(p), (JAW_Z - 0.03) - p[:, 2]), (-0.1, -0.72, JAW_Z - 0.03), (0.1, -0.03, JAW_Z + 0.05))
dark.append(thin(upper, 0.006, 0.03).intersect(pal_reg))
dark.append(J(thin(jaw, 0.006, 0.03).intersect(jaw_reg)))
_Rinv = euler(-GAPE, 0, 0)
_piv = np.asarray(HINGE, dtype=np.float32)
_thr = footprint(0.14, 0.12, -0.02)


def wedge(p):
    q = (p - _piv) @ _Rinv.T + _piv
    return np.maximum(np.maximum(p[:, 2] - (JAW_Z + 0.004), (JAW_Z - 0.004) - q[:, 2]), _thr(p))


dark.append(SDF(wedge, (-0.14, -0.16, JAW_Z - 0.36), (0.14, 0.12, JAW_Z + 0.01)))

# zanne enormi a sciabola (punte luminose) + dentini
fangs, fang_tips = [], []


def saber(pts, r0, glow_from=0.7):
    """Zanna a sciabola: (fusto, punta luminosa un po' piu' spessa che la ricopre)."""
    n = len(pts) - 1
    radii = [r0 * (1 - i / n) ** 0.85 + 0.008 for i in range(n + 1)]
    k = int(round(n * glow_from))
    return tube(pts[:k + 2], radii[:k + 2]), tube(pts[k:], [r + 0.007 for r in radii[k:]])


for sx in (1, -1):
    a = math.radians(sx * 30)
    p, n = project(upper, (0, -0.42, JAW_Z + 0.012), (math.sin(a), -math.cos(a), 0))
    b = p - norm((n[0], n[1], 0.0)) * 0.03
    shaft, tip = saber(bezier(tuple(b + (0, 0, 0.03)), tuple(b + (0, -0.08, -0.18)), tuple(b + (0, -0.06, -0.36)),
                              tuple(b + (sx * -0.02, 0.07, -0.5)), 12), 0.04)
    fangs.append(shaft)
    fang_tips.append(tip)
    a = math.radians(sx * 26)
    p, n = project(jaw, (0, -0.5, JAW_Z - 0.012), (math.sin(a), -math.cos(a), 0))
    b = p - norm((n[0], n[1], 0.0)) * 0.03
    shaft, tip = saber(bezier(tuple(b - (0, 0, 0.03)), tuple(b + (0, -0.09, 0.24)), tuple(b + (0, -0.05, 0.48)),
                              tuple(b + (sx * -0.03, 0.1, 0.66)), 14), 0.046)
    fangs.append(J(shaft))
    fang_tips.append(J(tip))
    for y, L_t in ((-0.3, 0.12), (-0.18, 0.1), (-0.06, 0.08)):
        p, n = project(upper, (0, y, JAW_Z + 0.012), (sx, 0, 0))
        b = p - norm((n[0], n[1], 0.0)) * 0.025
        fangs.append(round_cone((b[0], b[1], JAW_Z + 0.025), (b[0], b[1] - 0.01, JAW_Z - L_t), 0.024, 0.005))
    for y, L_t in ((-0.4, 0.14), (-0.26, 0.11), (-0.12, 0.09)):
        p, n = project(jaw, (0, y, JAW_Z - 0.012), (sx, 0, 0))
        b = p - norm((n[0], n[1], 0.0)) * 0.025
        fangs.append(J(round_cone((b[0], b[1], JAW_Z - 0.025), (b[0], b[1] - 0.01, JAW_Z + L_t), 0.026, 0.005)))

# fotofori sulla mandibola
for sx in (1, -1):
    for y in (-0.56, -0.42, -0.28, -0.14, 0.0):
        p, n = project(jaw, (0, y, -0.1), (sx * 0.7, 0, -0.7))
        photo_head.append(J(sphere(0.028, tuple(p))))

# cicatrice ricucita sulla testa (lato verso la camera)
scar, stitches = [], []
o = np.array([0.0, 0.0, 0.0])
sc_pts = []
for t in np.linspace(0, 1, 7):
    q = np.array([0.07, -0.18, 0.3]) * (1 - t) + np.array([0.3, 0.3, 0.08]) * t
    p, n = project(upper, o, q - o)
    sc_pts.append(p - n * 0.008)
scar.append(tube([tuple(x) for x in sc_pts], 0.02))
for j in (1, 2, 3, 4, 5):
    c = sc_pts[j]
    tdir = norm(sc_pts[j + 1] - sc_pts[j - 1])
    nn = project(upper, o, c - o)[1]
    sd = norm(np.cross(tdir, nn))
    for sg in (1, -1):
        a_ = c - sd * 0.05 - tdir * 0.025 * sg + nn * 0.006
        b_ = c + sd * 0.05 + tdir * 0.025 * sg + nn * 0.006
        stitches.append(capsule(tuple(a_), tuple(b_), 0.014))

head_skin = union(upper, J(jaw), *lids, k=0.012)
# cresta di lame sul cranio, all'indietro
crest = []
for j, (y, h) in enumerate(((-0.14, 0.13), (0.02, 0.17), (0.18, 0.2), (0.32, 0.17))):
    p, n = project(upper, (0, y, 0.05), (0, 0.15, 1))
    crest.append(spike(p - n * 0.03, p + norm(n + np.array([0, 0.9, 0])) * h, 0.05, 0.008))
log("testa pronta")

# ============================================================ corpo a S verticale (dalla nuca alla coda)
SPINE_CTRL = [lean(q) for q in [(0.0, -0.7, 2.8), (0.1, -0.26, 2.72), (0.44, 0.26, 2.44), (0.66, 0.58, 1.94),
                                 (0.52, 0.44, 1.4), (0.04, -0.02, 1.1), (-0.44, -0.42, 0.8), (-0.62, -0.52, 0.4),
                                 (-0.44, -0.24, 0.12), (-0.12, 0.2, 0.06)]]
sp = Spine(SPINE_CTRL, side=(1.0, 0.0, 0.0))
L = sp.len
log(f"spina lunga {L:.2f}")


def prof(u, pts):
    xs, ys = zip(*pts)
    return float(np.interp(u, xs, ys))


A_PTS = [(0.0, 0.29), (0.12, 0.3), (0.35, 0.28), (0.55, 0.23), (0.75, 0.17), (0.92, 0.11), (1.0, 0.08)]
B_PTS = [(0.0, 0.35), (0.12, 0.38), (0.35, 0.36), (0.55, 0.3), (0.75, 0.22), (0.92, 0.14), (1.0, 0.1)]
s_tab = np.linspace(0.0, L, 400)
A_tab = np.array([prof(s / L, A_PTS) for s in s_tab])
B_tab = np.array([prof(s / L, B_PTS) for s in s_tab])


def A(s):
    return float(np.interp(s, s_tab, A_tab))


def B(s):
    return float(np.interp(s, s_tab, B_tab))


def surf(s, th, sgn=1.0, sink=0.0):
    a, b = A(s), B(s)
    c, T, D, Lat = sp.frame(s)
    n = norm(Lat * sgn * math.cos(th) / a + D * math.sin(th) / b)
    return c + Lat * sgn * a * math.cos(th) + D * b * math.sin(th) - n * sink, n


body = swept_body(sp, A, B, B)


def spine_angle_f(p):
    """(s, theta) di ogni punto: theta = angolo ellittico (0 fianco, +pi/2 dorso, -pi/2 ventre)."""
    i, s, u, w = sp.coords(p)
    sc = np.clip(s, 0, L)
    a = np.interp(sc, s_tab, A_tab)
    b = np.interp(sc, s_tab, B_tab)
    return s, np.arctan2(w / b, np.abs(u) / a), np.sqrt(a * b)


def belly_f(p):
    s, th, r = spine_angle_f(p)
    d = (th + 0.78) * r
    return np.maximum(d, np.maximum(-s - 0.3, s - 0.97 * L)).astype(np.float32)


def sheen_f(p):
    s, th, r = spine_angle_f(p)
    sn = np.clip(s / L, 0, 1)
    wd = 0.2 * np.clip(np.minimum(sn / 0.08, (0.95 - sn) / 0.15), 0.0, 1.0)
    d = (np.abs(th - 0.42) - wd) * r
    return np.maximum(d, np.maximum(-s - 0.3, s - 0.95 * L)).astype(np.float32)


belly = shell_paint(body, SDF(belly_f, body.lo, body.hi), out=0.02, inn=0.05)
sheen = shell_paint(body, SDF(sheen_f, body.lo, body.hi), out=0.02, inn=0.05)

# fotofori: due file lungo il ventre che seguono tutta la S
photos = []
for sx in (1, -1):
    for s in np.arange(0.05 * L, 0.94 * L, 0.15):
        p, n = surf(s, -0.78, sx, sink=0.014)
        photos.append(sphere(0.047 * (1.0 - 0.4 * s / L), tuple(p)))
log(f"{len(photos)} fotofori")


# ============================================================ pinne a lama
def blade(length, width, sweep=0.0, thick=0.03):
    """Lama 2D nel piano XY locale: base nell'origine (larga 'width'), punta in (length, sweep)."""
    poly = [(0.0, -width / 2), (length * 0.35, -width * 0.62 + sweep * 0.2), (length * 0.7, -width * 0.38 + sweep * 0.6),
            (length, sweep), (length * 0.62, width * 0.12 + sweep * 0.5), (length * 0.3, width * 0.42 + sweep * 0.15),
            (0.0, width / 2)]
    return prism(poly, -thick, thick, round=thick * 0.9)


fins_pec = {}
for sx, nm in ((1, "FinR"), (-1, "FinL")):
    s0 = 0.1 * L
    base, n = surf(s0, -0.45, sx, sink=0.04)
    c, T, D, Lat = sp.frame(s0)
    span = norm(T * 0.5 + Lat * sx * 0.86 - D * 0.1)
    Mf = basis(span, D * 1.0 + T * 0.2)
    fins_pec[nm] = (place(blade(1.2, 0.28, sweep=-0.1), Mf, base), tuple(base))

fins = []
# dorsale: alta lama all'indietro subito dietro la testa
s0 = 0.1 * L
dor = [(s0 - 0.04, B(s0) - 0.08), (s0 + 0.12, B(s0) + 0.3), (s0 + 0.32, B(s0) + 0.6), (s0 + 0.4, B(s0) + 0.52),
       (s0 + 0.38, B(s0) + 0.3), (s0 + 0.5, B(s0 + 0.5) + 0.02)]
dor += [(s, B(s) - 0.08) for s in np.linspace(s0 + 0.46, s0, 6)]
fins.append(spine_fin(sp, dor, 0.03, (s0 - 0.2, s0 + 0.8), (0.0, 1.2)))
# punte luminose delle pinne (come le zanne)
tip_glow = [tube([tuple(sp.world(s0 + 0.2, 0.0, B(s0) + 0.43)), tuple(sp.world(s0 + 0.32, 0.0, B(s0) + 0.6)),
                  tuple(sp.world(s0 + 0.39, 0.0, B(s0) + 0.52))], [0.026, 0.034, 0.024])]
# adiposa e anale vicino alla coda
s1 = 0.8 * L
fins.append(spine_fin(sp, [(s1 - 0.04, B(s1) - 0.06), (s1 + 0.16, B(s1) + 0.22), (s1 + 0.28, B(s1) + 0.24),
                           (s1 + 0.24, B(s1 + 0.24) - 0.02)] + [(s, B(s) - 0.06) for s in np.linspace(s1 + 0.2, s1, 4)],
                      0.026, (s1 - 0.2, s1 + 0.5), (0.0, 0.8)))
s2 = 0.76 * L
tip_glow.append(tube([tuple(sp.world(s2 + 0.25, 0.0, -B(s2) - 0.32)), tuple(sp.world(s2 + 0.34, 0.0, -B(s2) - 0.4)),
                      tuple(sp.world(s2 + 0.39, 0.0, -B(s2) - 0.35))], [0.022, 0.03, 0.022]))
fins.append(spine_fin(sp, [(s2 - 0.04, -B(s2) + 0.06), (s2 + 0.16, -B(s2) - 0.24), (s2 + 0.34, -B(s2) - 0.4),
                           (s2 + 0.4, -B(s2) - 0.34), (s2 + 0.36, -B(s2 + 0.36) + 0.02)]
                      + [(s, -B(s) + 0.06) for s in np.linspace(s2 + 0.32, s2, 5)], 0.026, (s2 - 0.2, s2 + 0.6), (-1.0, 0.0)))
# ventrali (pelviche): due piccole lame
for sx in (1, -1):
    s3 = 0.44 * L
    base, n = surf(s3, -1.1, sx, sink=0.03)
    c, T, D, Lat = sp.frame(s3)
    fins.append(place(blade(0.42, 0.13, sweep=0.03, thick=0.024), basis(norm(T * 0.8 - D * 0.45 + Lat * sx * 0.3), Lat), base))

# coda a forbice con lobi a lama (gruppo "Tail")
TAIL_PIVOT = tuple(sp.world(L - 0.04, 0.0, 0.0))
tail_poly = [(L - 0.12, -0.07), (L + 0.2, -0.22), (L + 0.5, -0.46), (L + 0.82, -0.66), (L + 0.6, -0.36), (L + 0.38, -0.1),
             (L + 0.3, 0.0), (L + 0.38, 0.1), (L + 0.6, 0.36), (L + 0.82, 0.66), (L + 0.5, 0.46), (L + 0.2, 0.22),
             (L - 0.12, 0.07)]
tail_fin = spine_fin(sp, tail_poly, 0.03, (L - 0.3, L + 1.0), (-0.8, 0.8))
tail_glow = [tube([tuple(sp.world(L + a, 0.0, sg * b)) for a, b in ((0.6, 0.5), (0.82, 0.66), (0.66, 0.42))], [0.024, 0.034, 0.022])
             for sg in (1, -1)]
log("pinne pronte")

# ============================================================ barbiglio luminoso sotto il mento
chin = hp(jp((0.0, -0.5, -0.14)))
bar_pts = bezier(tuple(chin), tuple(chin + (0.05, -0.1, -0.3)), tuple(chin + (-0.06, -0.24, -0.5)), tuple(chin + (0.02, -0.18, -0.74)), 16)
barbel = tube(bar_pts, taper(17, 0.032, 0.018))
bulb_c = np.array(bar_pts[-1]) + np.array([0, 0, -0.08])
bulb = [sphere(0.1, tuple(bulb_c))]
for dx, dy in ((0.07, 0.03), (-0.06, 0.05), (0.0, -0.07)):
    a = bulb_c + np.array([dx, dy, -0.06])
    tip = a + np.array([dx * 1.4, dy * 1.4, -0.2])
    bulb.append(tube([tuple(a), tuple(a + np.array([dx * 0.8, dy * 0.8, -0.1])), tuple(tip)], [0.022, 0.016, 0.012]))
    bulb.append(sphere(0.03, tuple(tip)))
log("barbiglio pronto")

# ============================================================ parti
m.add("Body", union(body, H(head_skin), k=0.06), SKIN, tris=5400, voxel=0.031 * VX, reflectance=0.15)
m.add("Belly", belly, BELLY, role="detail", tris=1300, voxel=0.036 * VX)
# la banda iridescente prosegue sulla testa, da dietro l'occhio alla nuca
head_sheen = thin(upper, 0.016, 0.04).intersect(SDF(lambda q: np.maximum(np.maximum(np.abs(q[:, 2] - 0.13 - 0.12 * (q[:, 1] - 0.1)) - 0.045,
                                                                             0.12 - np.abs(q[:, 0])), np.maximum(-0.06 - q[:, 1], q[:, 1] - 0.5)),
                                                  (-0.4, -0.1, -0.1), (0.4, 0.5, 0.35)))
m.add("Sheen", union(sheen, H(head_sheen)), SHEEN, material="Foil", role="detail", tris=1000, voxel=0.04 * VX)
m.add("Maw", H(fast_union(dark)), MAW, role="eye", tris=500, voxel=0.034 * VX)
m.add("Fangs", H(fast_union(fangs)), FANG, role="shine", tris=1000, voxel=0.026 * VX)
m.add("Aura", H(fast_union(fang_tips)), GLOW, material="Neon", role="glow", tris=360, voxel=0.0185 * VX)
m.add("EyeGlow", H(union(*eye_glow)), EYE, material="Neon", role="glow", tris=300, voxel=0.031 * VX)
m.add("Pupils", H(union(*pupils)), PUPIL, role="eye", tris=300, voxel=0.013 * VX)
m.add("Shine", H(union(*shines)), WHITE, role="shine", tris=120, voxel=0.0115 * VX)
m.add("Photophores", fast_union(photos + [H(x) for x in photo_head] + tip_glow), GLOW, material="Neon", role="glow", tris=1700,
      voxel=0.0195 * VX)
m.add("Barbel", barbel, FIN, role="detail", tris=250, voxel=0.015 * VX)
m.add("Bubbles", union(*bulb, k=0.02), GLOW, material="Neon", role="glow", tris=400, voxel=0.015 * VX)
for nm in ("FinR", "FinL"):
    shp, piv = fins_pec[nm]
    m.add(nm, shp, FIN, material="Foil", role="detail", tris=380, voxel=0.024 * VX, group=nm, pivot=piv)
m.add("Fins", fast_union(fins + [H(c_) for c_ in crest]), FIN, material="Foil", role="detail", tris=1100, voxel=0.025 * VX)
m.add("TailFin", tail_fin, FIN, material="Foil", role="detail", tris=500, voxel=0.025 * VX, group="Tail", pivot=TAIL_PIVOT)
m.add("TailGlow", union(*tail_glow), GLOW, material="Neon", role="glow", tris=200, voxel=0.02 * VX, group="Tail", pivot=TAIL_PIVOT)
m.add("Stitches", H(fast_union(scar + stitches)), THREAD, role="detail", tris=400, voxel=0.018 * VX)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    for part in m.parts:          # scala finale: altezza nativa ~3.4
        part.sdf = part.sdf.scale(SCALE)
        if part.pivot is not None:
            part.pivot = tuple(float(v) * SCALE for v in part.pivot)
    ground(m)
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
    log("fatto")
