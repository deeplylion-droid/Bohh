"""Pescatore degli Abissi (AbyssAngler) - pet del Percorso Estremo (pesci abissali).

Una rana pescatrice colossale che nuota verso chi guarda con la bocca spalancata: corpo rotondo nero-indaco,
lucido come un giocattolo di vinile, che si assottiglia in una coda piegata a S. La mandibola enorme sporge in
avanti (prognatismo) ed e' piena di denti ad ago storti e vetrosi; dalla fronte sale un'antenna lunga e curva
che porta davanti alla faccia una grande esca luminosa bianco-ciano (parte Neon "Bubbles": il gioco ci attacca le
bollicine). Strisce e puntini bioluminescenti ciano sui fianchi, pinne corazzate a raggi appuntiti, occhietti
piccoli e cattivi che brillano color ambra sotto arcate di metallo chiodate.
Tocco "toy horror": una grossa chiave da carica d'ottone piantata nella schiena e una toppa cucita a punti
incrociati sulla pinna della coda.
"""
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, capsule, ellipsoid, euler, prism, round_cone, smin, sphere, torus,  # noqa: E402
                     tube, union)
from lib.toy import Model  # noqa: E402

DRAFT = os.environ.get("DRAFT", "") == "1"
VX = 1.35 if DRAFT else 1.0
T0 = time.time()
rng = np.random.default_rng(7)


def log(msg):
    print(f"[angler {time.time() - T0:6.1f}s] {msg}", flush=True)


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


def glow_tip(a, b, r0, r1=0.008, bend=(0.0, 0.0, 0.0), n=10, frac=0.32, extra=0.012):
    """Punta luminosa di una spina: l'ultimo tratto, appena piu' spesso, che ricopre la punta."""
    a, b, bend = np.asarray(a, float), np.asarray(b, float), np.asarray(bend, float)
    pts = bezier(tuple(a), tuple(a + (b - a) / 3 + bend), tuple(a + (b - a) * 2 / 3 + bend), tuple(b), n)
    radii = taper(n + 1, r0, r1, 0.9)
    k = int(round(n * (1 - frac)))
    return tube(pts[k:], [r + extra for r in radii[k:]])


class Spine:
    """Linea mediana del pesce, fitta, con un sistema di riferimento (T verso la coda, D dorso, L lato +X)."""

    def __init__(self, ctrl, step=0.01, n_per=24, up=(0.0, 0.0, 1.0)):
        P, S = resample(catmull(ctrl, n_per), step)
        T = np.gradient(P, axis=0)
        T /= np.linalg.norm(T, axis=1, keepdims=True)
        U = np.broadcast_to(np.asarray(up, dtype=np.float64), P.shape)
        D = U - T * np.einsum("ij,ij->i", U, T)[:, None]
        D /= np.linalg.norm(D, axis=1, keepdims=True)
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


# ============================================================ palette
INDIGO = (24, 19, 50)        # corpo nero-indaco (un nero puro in gioco e' piatto)
FIN = (78, 46, 150)          # membrane delle pinne viola scuro
ARMOR = (96, 106, 146)       # raggi, arcate, spuntoni e antenna (metallo brunito)
BIOLUM = (36, 232, 255)      # strisce, puntini e branchie bioluminescenti (Neon)
LURE = (120, 246, 255)       # esca ciano (Neon)
EYE = (255, 190, 40)         # occhi ambra (Neon)
PUPIL = (14, 6, 22)
MAW = (46, 10, 52)           # bocca viola-nera
TOOTH = (226, 246, 255)      # denti vetrosi
BRASS = (236, 180, 64)       # chiave da carica
WHITE = (255, 255, 255)

m = Model("AbyssAngler", "pet")

# ============================================================ spina: testa alzata, ventre basso, coda che risale (S)
SPINE_CTRL = [(-0.06, -1.22, 2.02), (-0.04, -0.82, 1.94), (0.04, -0.32, 1.78), (0.28, 0.14, 1.6), (0.66, 0.44, 1.5),
              (0.98, 0.78, 1.56), (1.1, 1.16, 1.74), (1.02, 1.44, 2.04)]
sp = Spine(SPINE_CTRL)
L = sp.len
log(f"spina lunga {L:.2f}")


def prof(u, pts):
    xs, ys = zip(*pts)
    return float(np.interp(u, xs, ys))


def nose(s, r, s0=0.55):
    """Arrotonda il muso: il raggio cresce come un quarto di ellisse nei primi s0."""
    t = min(max(s, 0.0) / s0, 1.0)
    return r * math.sqrt(max(1.0 - (1.0 - t) ** 2, 0.0))


A_PTS = [(0.0, 1.0), (0.22, 1.1), (0.35, 0.96), (0.47, 0.64), (0.6, 0.42), (0.78, 0.29), (1.0, 0.17)]
BT_PTS = [(0.0, 0.88), (0.22, 0.95), (0.35, 0.88), (0.47, 0.64), (0.6, 0.47), (0.78, 0.34), (1.0, 0.23)]
BB_PTS = [(0.0, 0.86), (0.22, 0.98), (0.35, 0.88), (0.47, 0.6), (0.6, 0.42), (0.78, 0.3), (1.0, 0.2)]
s_tab = np.linspace(0.0, L, 400)
A_tab, BT_tab, BB_tab = (np.array([nose(s, prof(s / L, pts)) for s in s_tab]) for pts in (A_PTS, BT_PTS, BB_PTS))


def A(s):
    return float(np.interp(s, s_tab, A_tab))


def BT(s):
    return float(np.interp(s, s_tab, BT_tab))


def BB(s):
    return float(np.interp(s, s_tab, BB_tab))


def surf(s, th, sgn=1.0, sink=0.0):
    """Punto sulla superficie del corpo all'ascissa s e all'angolo ellittico th (0 = fianco, >0 verso il dorso)."""
    a, b = A(s), (BT(s) if th > 0 else BB(s))
    c, T, D, Lat = sp.frame(s)
    n = norm(Lat * sgn * math.cos(th) / a + D * math.sin(th) / b)
    return c + Lat * sgn * a * math.cos(th) + D * b * math.sin(th) - n * sink, n


body = swept_body(sp, A, BT, BB)

# ============================================================ testa: bocca enorme, mandibola sporgente
HEAD_C = sp.frame(0.3 * L)[0]
_hd = sp.frame(0.3 * L)[1]
YAW, MP, GAPE = math.degrees(math.atan2(-_hd[0], _hd[1])) * 0.6, 32.0, 26.0
MR = euler(-MP, 0.0, YAW).astype(np.float64)          # piano della bocca: sale verso il davanti
HP = HEAD_C + np.array([0.0, 0.3, -0.45])             # cerniera della mandibola (angolo della bocca)
MR32, HP32 = MR.astype(np.float32), HP.astype(np.float32)


def to_mouth(p):
    return (p - HP32) @ MR32


def from_mouth(q):
    return q @ MR32.T + HP32


def M(shape):
    """Forma nel sistema della bocca (origine nella cerniera, -Y avanti, Z normale al piano) -> mondo."""
    return shape.rotate(MR32).translate(tuple(HP))


def J(shape):
    """Mandibola chiusa -> aperta (sistema della bocca)."""
    return shape.rot(GAPE, 0, 0)


cheeks = [ellipsoid((0.4, 0.5, 0.42), tuple(HEAD_C + (sx * 0.6, 0.36, -0.22))) for sx in (1, -1)]
head_mass = union(body, *cheeks, k=0.35)
jaw_cut = SDF(lambda p: (lambda q: np.maximum(q[:, 2], q[:, 1]))(to_mouth(p)), (-3, -3, -1), (3, 3, 4))
upper = head_mass.subtract(jaw_cut, k=0.05)
LOC_LO, LOC_HI = (-1.35, -2.0, -1.4), (1.35, 0.4, 0.08)
head_local = SDF(lambda q: head_mass(from_mouth(q)), LOC_LO, LOC_HI)
jaw_local = head_local.intersect(SDF(lambda q: np.maximum(q[:, 2], q[:, 1] - 0.05), LOC_LO, LOC_HI), k=0.05)
chin = ellipsoid((0.72, 0.5, 0.25), (0.0, -1.42, -0.17))
jaw_local = union(jaw_local, chin, k=0.34).intersect(SDF(lambda q: q[:, 2], LOC_LO, LOC_HI), k=0.04)
jaw = M(J(jaw_local))
skin_body = union(upper, jaw, k=0.06)
log("testa pronta")


# ============================================================ bocca scura: palato, pavimento e gola
def lip_fp(q, inset):
    hw = np.interp(q[:, 1], [-1.95, -1.6, -1.1, -0.6, -0.2, 0.05], [0.0, 0.46, 0.76, 0.95, 0.98, 0.88]) - inset
    return np.maximum(np.abs(q[:, 0]) - hw, np.maximum(-1.95 + inset - q[:, 1], q[:, 1] - 0.02))


pal_reg = SDF(lambda p: (lambda q: np.maximum(lip_fp(q, 0.1), np.abs(q[:, 2]) - 0.08))(to_mouth(p)), upper.lo, upper.hi)
maw = [shell_paint(upper, pal_reg, out=0.012, inn=0.04, margin=0.03)]
floor_reg = SDF(lambda q: np.maximum(lip_fp(q, 0.14), np.abs(q[:, 2]) - 0.08), (-1.2, -2.0, -0.1), (1.2, 0.1, 0.1))
maw.append(M(J(shell_paint(jaw_local, floor_reg, out=0.012, inn=0.04, margin=0.03))))
_Rinv = euler(-GAPE, 0, 0).astype(np.float32)


def throat_f(q):
    qq = q @ _Rinv.T
    fp = np.maximum(np.abs(q[:, 0]) - np.interp(q[:, 1], [-1.0, -0.6, -0.2, 0.05], [0.0, 0.62, 0.85, 0.75]), -0.78 - q[:, 1])
    return np.maximum(np.maximum(q[:, 2] - 0.01, -0.01 - qq[:, 2]), np.maximum(fp, q[:, 1] - 0.1))


maw.append(M(SDF(throat_f, (-1.0, -0.85, -0.75), (1.0, 0.15, 0.05))))
log("bocca pronta")

# ============================================================ denti ad ago storti e vetrosi
upper_local = SDF(lambda q: upper(from_mouth(q)), LOC_LO, (1.35, 0.4, 1.0))


def rim_points(shape, z, n, a0, a1, cy):
    pts = []
    for a in np.linspace(a0, a1, n):
        d = np.array([math.sin(math.radians(a)), -math.cos(math.radians(a)), 0.0])
        o = np.array([0.0, cy, z])
        ts = np.linspace(0.0, 2.2, 500)
        v = shape((o[None, :] + ts[:, None] * d[None, :]).astype(np.float32))
        idx = np.nonzero(v > 0)[0]
        if len(idx) and v[0] < 0:
            pts.append(o + ts[idx[0]] * d)
    return pts


teeth = []
UP_RIM = rim_points(upper_local, 0.03, 13, -80, 80, -0.55)
LO_RIM = rim_points(jaw_local, -0.03, 12, -76, 76, -0.75)
for j, b in enumerate(UP_RIM):
    inward = norm(np.array([-b[0], -0.55 - b[1], 0.0]))
    big = j % 2 == 0
    L_t = (0.34 if big else 0.2) * rng.uniform(0.8, 1.15)
    tip = b + inward * 0.14 * rng.uniform(0.5, 1.2) + np.array([rng.uniform(-0.05, 0.05), 0.0, -L_t])
    teeth.append(M(spike(b + np.array([0, 0, 0.05]) + inward * 0.05, tip, 0.05 if big else 0.036, 0.007,
                         bend=inward * 0.05 + rng.uniform(-0.03, 0.03, 3), n=6)))
for j, b in enumerate(LO_RIM):
    inward = norm(np.array([-b[0], -0.75 - b[1], 0.0]))
    big = j % 2 == 1 or j in (5, 6)
    L_t = (0.5 if big else 0.27) * rng.uniform(0.85, 1.15)
    tip = b + inward * 0.1 * rng.uniform(0.3, 1.3) + np.array([rng.uniform(-0.06, 0.06), -0.05, L_t])
    teeth.append(M(J(spike(b - np.array([0, 0, 0.05]) + inward * 0.05, tip, 0.06 if big else 0.04, 0.007,
                           bend=-inward * 0.07 + rng.uniform(-0.035, 0.035, 3), n=6))))
log(f"{len(teeth)} denti")
# gengive luminose: una linea ciano dove spuntano i denti (il ghigno brilla nel buio)
gums = [M(tube([tuple(b + norm(np.array([-b[0], -0.55 - b[1], 0.0])) * 0.03 + np.array([0, 0, 0.02])) for b in UP_RIM], 0.03)),
        M(J(tube([tuple(b + norm(np.array([-b[0], -0.75 - b[1], 0.0])) * 0.03 - np.array([0, 0, 0.02])) for b in LO_RIM], 0.03)))]

# ============================================================ occhietti cattivi luminosi sotto arcate chiodate
eye_glow, pupils, shines, armor = [], [], [], []
for sx in (1, -1):
    d = norm((sx * 0.56, -0.56, 0.6))
    o = HEAD_C + np.array([sx * 0.2, 0.0, 0.3])
    ts = np.linspace(0, 2, 600)
    v = upper((o[None, :] + ts[:, None] * d[None, :]).astype(np.float32))
    p = o + ts[np.nonzero(v > 0)[0][0]] * d
    n = norm(p - (HEAD_C + np.array([0, 0.2, 0.0])))
    c = p - n * 0.03
    side = norm(np.cross((0, 0, 1), n)) * sx          # tangente orizzontale verso la coda
    up = norm(np.cross(n, side)) * sx                   # tangente verso l'alto
    eye_glow.append(sphere(0.125, tuple(c)))
    pupils.append(place(ellipsoid((0.024, 0.082, 0.03)), np.stack([side, up, n], axis=1).astype(np.float32), c + n * 0.1))
    shines.append(sphere(0.026, tuple(c + n * 0.115 + up * 0.055 - side * 0.04)))
    a = c + n * 0.08 + up * 0.07 - side * 0.2
    b = c + n * 0.03 + up * 0.2 + side * 0.18
    armor.append(tube([tuple(a), tuple((a + b) / 2 + up * 0.03 + n * 0.05), tuple(b)], [0.065, 0.08, 0.06]))
    for t, Ls in ((0.2, 0.15), (0.55, 0.22), (0.9, 0.2)):
        q = a * (1 - t) + b * t + up * 0.04
        armor.append(spike(q, q + norm(up * 1.0 + side * 0.7 + n * 0.15) * Ls, 0.045, 0.006))
# spuntoni delle guance (opercolo), all'indietro
for sx in (1, -1):
    for th, sn, Ls in ((0.05, 0.41, 0.3), (-0.3, 0.42, 0.22)):
        p, n = surf(sn * L, th, sx, sink=0.05)
        c, T, D, Lat = sp.frame(sn * L)
        armor.append(spike(p, p + norm(n * 0.7 + T * 1.0) * Ls, 0.06, 0.007))
log("occhi pronti")

# ============================================================ esca: antenna curva dalla fronte, orbe luminoso
LB = HEAD_C + np.array([0.0, -0.45, 0.66])
LURE_C = np.array([-0.04, -1.86, 3.2])
stalk_pts = bezier(tuple(LB), tuple(LB + (0.0, 0.3, 1.6)), tuple(LURE_C + (0.0, 0.62, 0.95)), tuple(LURE_C + (0, 0, 0.3)), 28)
stalk = tube(stalk_pts, taper(29, 0.08, 0.036, 0.8))
cup = round_cone(tuple(LURE_C + np.array([0, 0, 0.34])), tuple(LURE_C + np.array([0, 0, 0.18])), 0.045, 0.12)
lure = sphere(0.27, tuple(LURE_C))
filaments = []
for dx, dy in ((0.11, 0.05), (-0.11, 0.06), (0.0, -0.11)):
    a = LURE_C + np.array([dx, dy, -0.2])
    filaments.append(tube(bezier(tuple(a), tuple(a + (dx * 0.6, dy * 0.5, -0.12)), tuple(a + (dx * 1.2, dy, -0.2)),
                                 tuple(a + (dx * 0.8, dy * 1.4, -0.34)), 8), taper(9, 0.035, 0.014)))
    filaments.append(sphere(0.042, tuple(a + (dx * 0.8, dy * 1.4, -0.36))))
shines.append(ellipsoid((0.07, 0.04, 0.05)).rot(0, 30, -20).translate(tuple(LURE_C + norm((0.45, -0.6, 0.65)) * 0.25)))
nodes = []
for i in (8, 13, 18, 23):     # anelli luminosi lungo l'antenna (come gli anelli di una canna da pesca)
    tdir = norm(np.array(stalk_pts[i + 1]) - np.array(stalk_pts[i - 1]))
    r_st = taper(29, 0.08, 0.036, 0.8)[i]
    nodes.append(place(torus(r_st + 0.012, 0.026), basis(norm(np.cross(tdir, (1.0, 0.0, 0.0))), (1.0, 0.0, 0.0)) @
                       np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=np.float32).T, np.array(stalk_pts[i])))
log("esca pronta")

# ============================================================ bioluminescenza: branchie, strisce, puntini
glow = []
for sx in (1, -1):
    for k_, sn in enumerate((0.43, 0.465, 0.5)):
        pts = []
        for th in np.linspace(-0.55, 0.5, 9):
            s = sn * L + 0.07 * math.cos(th * 2.4)
            p, n = surf(s, th, sx, sink=0.012)
            pts.append(tuple(p))
        glow.append(tube(pts, [0.02, 0.03, 0.036, 0.04, 0.04, 0.04, 0.036, 0.03, 0.02]))
    # due strisce ondulate sul fianco
    for th0, amp, ph, s0, s1 in ((0.38, 0.1, 0.0, 0.55, 0.96), (-0.25, 0.1, 1.9, 0.57, 0.92)):
        pts, rad = [], []
        for t in np.linspace(0.0, 1.0, 22):
            sn = s0 + (s1 - s0) * t
            p, n = surf(sn * L, th0 + amp * math.sin(sn * 19.0 + ph), sx, sink=0.012)
            pts.append(tuple(p))
            rad.append(0.012 + 0.03 * math.sin(math.pi * t) ** 0.7)
        glow.append(tube(pts, rad))
    # fila di puntini lungo la linea laterale
    for t in np.linspace(0.0, 1.0, 9):
        sn = 0.55 + 0.38 * t
        p, n = surf(sn * L, 0.07 + 0.1 * math.sin(sn * 19.0 + 0.95), sx, sink=0.022)
        glow.append(sphere(0.055 - 0.02 * t, tuple(p)))
    # lentiggini luminose sulla testa
    for th, sn, r in ((1.0, 0.22, 0.045), (1.15, 0.3, 0.05), (0.92, 0.36, 0.04), (1.25, 0.4, 0.035), (0.8, 0.27, 0.035)):
        p, n = surf(sn * L, th, sx, sink=0.02)
        glow.append(sphere(r, tuple(p)))
# fotofori lungo i fianchi della mandibola (sotto il labbro)
jaw_dots = []
for sx in (1, -1):
    for k_, a_ in enumerate(np.linspace(26, 74, 5)):
        d = np.array([sx * math.sin(math.radians(a_)), -math.cos(math.radians(a_)), -0.42])
        o = np.array([0.0, -0.7, -0.28])
        ts = np.linspace(0.0, 2.2, 500)
        v = jaw_local((o[None, :] + ts[:, None] * d[None, :]).astype(np.float32))
        idx = np.nonzero(v > 0)[0]
        if len(idx) and v[0] < 0:
            q = o + ts[idx[0]] * norm(d) * np.linalg.norm(d) - norm(d) * 0.02
            jaw_dots.append(M(J(sphere(0.052 - 0.004 * k_, tuple(q)))))
glow += jaw_dots
log("bioluminescenza pronta")


# ============================================================ pinne corazzate a raggi appuntiti
def fan_fin(angs, lengths, base_w=0.12, thick=0.035, notch=0.68, ray_r=0.05, tip_ext=0.14):
    """Pinna a ventaglio nel piano XY locale (base nell'origine, si apre verso +X): membrana + raggi a spina."""
    angs = np.radians(angs)
    poly = [(0.0, -base_w)]
    for k_, (ang, Ln) in enumerate(zip(angs, lengths)):
        if k_ > 0:
            am = 0.5 * (angs[k_ - 1] + ang)
            lm = 0.5 * (lengths[k_ - 1] + Ln) * notch
            poly.append((math.cos(am) * lm, math.sin(am) * lm))
        poly.append((math.cos(ang) * Ln, math.sin(ang) * Ln))
    poly.append((0.0, base_w))
    mem = prism(poly, -thick, thick, round=thick * 0.9)
    rays = [spike((0, 0, 0), np.array([math.cos(a), math.sin(a), 0.0]) * (Ln + tip_ext), ray_r, 0.006,
                  bend=np.array([0, 0, 0.03]), n=6) for a, Ln in zip(angs, lengths)]
    return mem, union(*rays)


fins_mem, fins_ray = {}, {}
PEC_S = 0.44 * L
for sx, nm in ((1, "FinR"), (-1, "FinL")):
    c, T, D, Lat = sp.frame(PEC_S)
    base = sp.world(PEC_S, sx * A(PEC_S) * 0.92, 0.08)
    span = norm(Lat * sx * 1.0 + T * 0.25 + D * 0.42)
    Mf = basis(span, T * 1.0 - D * 0.2)
    mem, rays = fan_fin(np.linspace(-60, 55, 5), [0.92, 1.16, 1.26, 1.12, 0.84], base_w=0.18)
    fins_mem[nm] = (place(mem, Mf, base), tuple(base))
    fins_ray[nm] = place(rays, Mf, base)

# pinna dorsale: alte spine all'indietro con la membrana fra una e l'altra
D_S0, D_S1 = 0.44 * L, 0.7 * L
dor_poly, dor_rays, dor_tips = [], [], []
for k_, t in enumerate(np.linspace(0.0, 1.0, 6)):
    s = D_S0 + (D_S1 - D_S0) * t
    h = BT(s) + 0.95 - 0.42 * t
    tip_s = s + 0.24
    if k_ > 0:
        dor_poly.append((s + 0.02, BT(s) + (h - BT(s)) * 0.5))
    dor_poly.append((tip_s - 0.04, h - 0.06))
    a, b = sp.world(s, 0.0, BT(s) - 0.12), sp.world(tip_s, 0.0, h + 0.12)
    dor_rays.append(spike(a, b, 0.065, 0.007, bend=sp.frame(s)[1] * -0.06, n=10))
    dor_tips.append(glow_tip(a, b, 0.065, 0.007, bend=sp.frame(s)[1] * -0.06))
dor_poly += [(D_S1 + 0.34, BT(D_S1 + 0.34) - 0.02)]
dor_poly += [(s, BT(s) - 0.12) for s in np.linspace(D_S1 + 0.3, D_S0 - 0.06, 9)]
dorsal = spine_fin(sp, dor_poly, 0.035, (D_S0 - 0.2, D_S1 + 0.5), (0.0, 1.8))

# pinna anale sotto la coda
A_S0, A_S1 = 0.74 * L, 0.88 * L
an_poly, an_rays = [], []
for k_, t in enumerate(np.linspace(0.0, 1.0, 3)):
    s = A_S0 + (A_S1 - A_S0) * t
    h = BB(s) + 0.36 - 0.08 * t
    if k_ > 0:
        an_poly.append((s + 0.01, -(BB(s) + (h - BB(s)) * 0.5)))
    an_poly.append((s + 0.13, -h))
    an_rays.append(spike(sp.world(s, 0.0, -(BB(s) - 0.1)), sp.world(s + 0.2, 0.0, -(h + 0.1)), 0.05, 0.007))
an_poly += [(A_S1 + 0.22, -BB(A_S1 + 0.22) + 0.02)]
an_poly += [(s, -BB(s) + 0.1) for s in np.linspace(A_S1 + 0.18, A_S0 - 0.04, 6)]
anal = spine_fin(sp, an_poly, 0.032, (A_S0 - 0.2, A_S1 + 0.4), (-1.3, 0.0))

# coda a ventaglio con raggi a spina (gruppo "Tail")
TAIL_PIVOT = tuple(sp.world(L - 0.05, 0.0, 0.0))
T_ANG = np.radians(np.linspace(-56, 56, 7))
T_LEN = [1.0, 1.16, 1.02, 0.9, 1.02, 1.16, 1.0]
tail_poly = [(L - 0.14, -0.2)]
tail_rays, tail_tips = [], []
for k_, (ang, Ln) in enumerate(zip(T_ANG, T_LEN)):
    if k_ > 0:
        am = 0.5 * (T_ANG[k_ - 1] + ang)
        lm = 0.5 * (T_LEN[k_ - 1] + Ln) * 0.66
        tail_poly.append((L - 0.06 + math.cos(am) * lm, math.sin(am) * lm))
    tail_poly.append((L - 0.06 + math.cos(ang) * Ln, math.sin(ang) * Ln))
    ta, tb = sp.world(L - 0.12, 0.0, 0.0), sp.world(L - 0.06 + math.cos(ang) * (Ln + 0.14), 0.0, math.sin(ang) * (Ln + 0.14))
    tail_rays.append(spike(ta, tb, 0.055, 0.006))
    tail_tips.append(glow_tip(ta, tb, 0.055, 0.006, frac=0.22, extra=0.014))
tail_poly.append((L - 0.14, 0.2))
tail_fin = spine_fin(sp, tail_poly, 0.035, (L - 0.3, L + 1.2), (-1.0, 1.0))
log("pinne pronte")

# ============================================================ chiave da carica d'ottone nella schiena
KEY_S = 0.76 * L
kc, kT, kD, kL = sp.frame(KEY_S)
key_base = sp.world(KEY_S, 0.06, BT(KEY_S) - 0.1)
key_dir = norm(kD * 1.0 + kL * 0.5)
key_top = key_base + key_dir * 0.4
Mk = basis(key_dir, kT)
key = [capsule(tuple(key_base), tuple(key_top), 0.055), sphere(0.095, tuple(key_base + key_dir * 0.12)),
       sphere(0.075, tuple(key_top))]
for sg in (1, -1):
    key.append(place(torus(0.15, 0.05), basis(Mk[:, 1], Mk[:, 0]), key_top + key_dir * 0.2 + Mk[:, 1] * sg * 0.2))
key.append(place(ellipsoid((0.1, 0.05, 0.08)), Mk, key_top + key_dir * 0.08))
log("chiave pronta")

# ============================================================ parti
m.add("Body", skin_body, INDIGO, tris=4800, voxel=0.045 * VX, reflectance=0.1)
m.add("Maw", fast_union(maw + pupils), MAW, role="eye", tris=900, voxel=0.045 * VX)
m.add("Teeth", fast_union(teeth), TOOTH, material="Glass", role="shine", transparency=0.1, tris=1500, voxel=0.02 * VX)
m.add("EyeGlow", union(*eye_glow), EYE, material="Neon", role="glow", tris=240, voxel=0.022 * VX)
m.add("Shine", union(*shines), WHITE, role="shine", tris=120, voxel=0.012 * VX)
m.add("Armor", fast_union(armor + dor_rays + an_rays + [stalk, cup]), ARMOR, material="Metal", role="detail", tris=1700,
      voxel=0.022 * VX)
m.add("Biolume", fast_union(glow + gums + nodes + dor_tips), BIOLUM, material="Neon",
      role="glow", tris=1400, voxel=0.024 * VX)
m.add("Bubbles", union(lure, *filaments, k=0.03), LURE, material="Neon", role="glow", tris=600, voxel=0.024 * VX)
for nm in ("FinR", "FinL"):
    mem, piv = fins_mem[nm]
    m.add(nm, mem, FIN, role="detail", tris=450, voxel=0.03 * VX, group=nm, pivot=piv)
    m.add(nm + "Rays", fins_ray[nm], ARMOR, material="Metal", role="detail", tris=300, voxel=0.026 * VX, group=nm, pivot=piv)
m.add("Fins", fast_union([dorsal, anal]), FIN, role="detail", tris=800, voxel=0.028 * VX)
m.add("TailFin", tail_fin, FIN, role="detail", tris=550, voxel=0.028 * VX, group="Tail", pivot=TAIL_PIVOT)
m.add("TailRays", fast_union(tail_rays), ARMOR, material="Metal", role="detail", tris=400, voxel=0.026 * VX, group="Tail",
      pivot=TAIL_PIVOT)
m.add("TailGlow", fast_union(tail_tips), BIOLUM, material="Neon", role="glow", tris=200, voxel=0.016 * VX, group="Tail",
      pivot=TAIL_PIVOT)
m.add("WindKey", fast_union(key), BRASS, material="Metal", role="detail", tris=600, voxel=0.02 * VX)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    ground(m)
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
    log("fatto")
