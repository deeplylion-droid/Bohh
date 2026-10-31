"""Testa di Vetro (GlassHead) - pet del Percorso Estremo (pesci abissali).

Un pesce barile (barreleye) che risale dagli abissi in diagonale, con il corpo affusolato scuro piegato a S: sopra la
testa ha una cupola di vetro trasparente, fissata con un collare di metallo chiodato come un barattolo da
collezione, e dentro si vedono i due grandi occhi a tubo verdi e luminosi che guardano in alto (le lenti sono la parte
Neon "Bubbles": il gioco ci attacca le bollicine, come in un acquario). Sotto la cupola il muso ha due narici che
sembrano occhietti e una boccuccia imbronciata. Grandi pinne pettorali a ventaglio aperte come ali, pinne con il
bordo verde luminoso e lunghe code a nastro che ondeggiano sotto di lui. Misterioso e alieno.
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
    print(f"[glass {time.time() - T0:6.1f}s] {msg}", flush=True)


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

    def __init__(self, ctrl, step=0.01, n_per=24, up=(0.0, 0.0, 1.0), up2=None, twist=0.0):
        P, S = resample(catmull(ctrl, n_per), step)
        T = np.gradient(P, axis=0)
        T /= np.linalg.norm(T, axis=1, keepdims=True)
        U = np.broadcast_to(np.asarray(up, dtype=np.float64), P.shape)
        if up2 is not None:      # il riferimento ruota da 'up' a 'up2' lungo la curva (nastri attorcigliati)
            ang = (S / S[-1] * twist)[:, None]
            U = U * np.cos(ang) + np.asarray(up2, dtype=np.float64)[None, :] * np.sin(ang)
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
BODY = (20, 32, 44)          # corpo scuro blu-petrolio
BELLY = (58, 84, 98)         # ventre ardesia chiaro
FIN = (28, 64, 78)           # membrane verde petrolio scuro
GLOW = (90, 255, 140)        # bordi delle pinne, linea laterale (Neon)
TUBE = (50, 214, 104)        # occhi a tubo (Neon)
LENS = (196, 255, 110)       # lenti degli occhi (Neon "Bubbles")
DOME = (206, 255, 238)       # cupola di vetro
METAL = (150, 166, 176)      # collare e chiodi
DARK = (12, 10, 18)          # narici, bocca, pupille
WHITE = (255, 255, 255)

m = Model("GlassHead", "pet")

# ============================================================ corpo affusolato che risale in diagonale, piegato a S
SPINE_CTRL = [(0.0, -1.36, 2.62), (0.0, -0.92, 2.5), (0.04, -0.42, 2.26), (0.2, 0.05, 1.98), (0.45, 0.42, 1.76),
              (0.55, 0.82, 1.6), (0.42, 1.12, 1.52)]
sp = Spine(SPINE_CTRL)
L = sp.len
log(f"spina lunga {L:.2f}")


def prof(u, pts):
    xs, ys = zip(*pts)
    return float(np.interp(u, xs, ys))


def nose(s, r, s0=0.46):
    t = min(max(s, 0.0) / s0, 1.0)
    return r * math.sqrt(max(1.0 - (1.0 - t) ** 2, 0.0))


A_PTS = [(0.0, 0.44), (0.15, 0.5), (0.35, 0.5), (0.55, 0.42), (0.75, 0.28), (0.9, 0.17), (1.0, 0.12)]
BT_PTS = [(0.0, 0.36), (0.15, 0.4), (0.35, 0.52), (0.55, 0.5), (0.75, 0.34), (0.9, 0.21), (1.0, 0.15)]
BB_PTS = [(0.0, 0.46), (0.15, 0.56), (0.35, 0.6), (0.55, 0.5), (0.75, 0.32), (0.9, 0.19), (1.0, 0.14)]
s_tab = np.linspace(0.0, L, 400)
A_tab, BT_tab, BB_tab = (np.array([nose(s, prof(s / L, pts)) for s in s_tab]) for pts in (A_PTS, BT_PTS, BB_PTS))


def A(s):
    return float(np.interp(s, s_tab, A_tab))


def BT(s):
    return float(np.interp(s, s_tab, BT_tab))


def BB(s):
    return float(np.interp(s, s_tab, BB_tab))


def surf(s, th, sgn=1.0, sink=0.0):
    a, b = A(s), (BT(s) if th > 0 else BB(s))
    c, T, D, Lat = sp.frame(s)
    n = norm(Lat * sgn * math.cos(th) / a + D * math.sin(th) / b)
    return c + Lat * sgn * a * math.cos(th) + D * b * math.sin(th) - n * sink, n


body = swept_body(sp, A, BT, BB)


def angle_f(p):
    i, s, u, w = sp.coords(p)
    sc = np.clip(s, 0, L)
    a = np.interp(sc, s_tab, A_tab)
    b = np.where(w > 0, np.interp(sc, s_tab, BT_tab), np.interp(sc, s_tab, BB_tab))
    return s, np.arctan2(w / np.maximum(b, 1e-3), np.abs(u) / np.maximum(a, 1e-3)), np.sqrt(a * b)


belly = shell_paint(body, SDF(lambda p: (lambda s, th, r: np.maximum((th + 0.55) * r, np.maximum(0.12 * L - s, s - 0.93 * L)))(
    *angle_f(p)).astype(np.float32), body.lo, body.hi), out=0.02, inn=0.05)

# ============================================================ cupola di vetro sulla testa, occhi a tubo dentro
DS = 0.24 * L
dc, dT, dD, dL = sp.frame(DS)
D_C = dc + dD * (BT(DS) * 0.55)
D_R = np.array([0.52, 0.82, 0.74])                  # semiassi (lato, lungo la spina, in alto)
MD = np.stack([dL, -dT, dD], axis=1).astype(np.float32)   # X lato, Y verso il muso, Z dorso
dome = place(ellipsoid(tuple(D_R)), MD, D_C)
dome = dome.intersect(SDF(lambda p: -((p - D_C.astype(np.float32)) @ dD.astype(np.float32)) - 0.02,
                          dome.lo, dome.hi))          # solo la meta' sopra il centro
# occhi a tubo: cilindri un po' inclinati in avanti con la lente in cima
tubes, lenses, pupils, shines = [], [], [], []
for sx in (1, -1):
    base = D_C + dL * sx * 0.2 - dT * 0.08 - dD * 0.1
    axis = norm(dD * 1.0 - dT * 0.36 + dL * sx * 0.14)
    top = base + axis * 0.42
    tubes.append(round_cone(tuple(base), tuple(top), 0.14, 0.158))
    tubes.append(sphere(0.15, tuple(base)))
    lenses.append(sphere(0.172, tuple(top + axis * 0.04)))
    pupils.append(sphere(0.078, tuple(top + axis * 0.155)))
# riflesso bianco sulla cupola (il vetro del giocattolo)
shines.append(place(ellipsoid((0.2, 0.055, 0.04)), np.stack([dL, -dT, dD], axis=1).astype(np.float32) @
                    euler(-38, 0, 0).astype(np.float32), D_C + (-dT * 0.45 + dD * 0.56 + dL * 0.16)))
log("cupola pronta")

# collare di metallo chiodato dove la cupola incontra la testa
ring = []
for phi in np.linspace(0, 2 * math.pi, 49)[:-1]:
    dirr = np.array([math.cos(phi), math.sin(phi), 0.0])
    # dall'alto della cupola scende lungo il meridiano finche' entra nel corpo
    for beta in np.linspace(0.2, math.pi / 2 + 0.25, 120):
        q = np.array([D_R[0] * math.sin(beta) * dirr[0], D_R[1] * math.sin(beta) * dirr[1], D_R[2] * math.cos(beta)])
        pw = MD.astype(np.float64) @ q + D_C
        if body(pw[None, :].astype(np.float32))[0] < 0.0:
            ring.append(pw)
            break
ring = np.array(ring)
collar = [tube([tuple(r) for r in list(ring) + [ring[0]]], 0.05)]
rivets = [sphere(0.035, tuple(ring[i] + norm(ring[i] - D_C) * 0.045)) for i in range(0, len(ring), 4)]
log(f"collare: {len(ring)} punti")

# ============================================================ faccia: narici-occhietti e boccuccia imbronciata
nose_c, nT, nD, nL = sp.frame(0.05 * L)
nares = []
for sx in (1, -1):
    o = nose_c + nD * 0.05
    d = norm(-nT * 1.0 + nL * sx * 0.45 + nD * 0.38)
    ts = np.linspace(0, 1, 400)
    v = body((o[None, :] + ts[:, None] * d[None, :]).astype(np.float32))
    p = o + ts[np.nonzero(v > 0)[0][0]] * d
    nares.append(sphere(0.068, tuple(p - d * 0.02)))
    shines.append(sphere(0.02, tuple(p + d * 0.04 + nD * 0.03 - nL * sx * 0.012)))
brows = []
for sx in (1, -1):
    o = nose_c + nD * 0.05
    pts = []
    for t in (-0.6, 0.0, 0.6):
        d = norm(-nT * 1.0 + nL * sx * (0.45 + 0.22 * t) + nD * (0.6 + 0.12 * t))
        ts = np.linspace(0, 1, 400)
        v = body((o[None, :] + ts[:, None] * d[None, :]).astype(np.float32))
        pts.append(o + ts[np.nonzero(v > 0)[0][0]] * d)
    brows.append(tube([tuple(q) for q in pts], [0.034, 0.042, 0.03]))
mouth_pts = []
for t in np.linspace(-1, 1, 9):
    o = nose_c - nD * 0.12
    d = norm(-nT * 1.0 + nL * t * 0.7 - nD * (0.35 + 0.25 * t * t))
    ts = np.linspace(0, 1, 400)
    v = body((o[None, :] + ts[:, None] * d[None, :]).astype(np.float32))
    mouth_pts.append(o + ts[np.nonzero(v > 0)[0][0]] * d)
mouth = tube([tuple(p) for p in mouth_pts], [0.022, 0.03, 0.036, 0.04, 0.04, 0.04, 0.036, 0.03, 0.022])
log("faccia pronta")

# ============================================================ pinne con il bordo luminoso
def fan(angs, lengths, base_w=0.12, thick=0.03, notch=0.8):
    angs = np.radians(angs)
    poly, edge = [(0.0, -base_w)], []
    for k_, (ang, Ln) in enumerate(zip(angs, lengths)):
        if k_ > 0:
            am = 0.5 * (angs[k_ - 1] + ang)
            lm = 0.5 * (lengths[k_ - 1] + Ln) * notch
            poly.append((math.cos(am) * lm, math.sin(am) * lm))
            edge.append((math.cos(am) * lm, math.sin(am) * lm))
        poly.append((math.cos(ang) * Ln, math.sin(ang) * Ln))
        edge.append((math.cos(ang) * Ln, math.sin(ang) * Ln))
    poly.append((0.0, base_w))
    mem = prism(poly, -thick, thick, round=thick * 0.9)
    rays = [round_cone((0, 0, 0), (math.cos(a) * Ln * 0.86, math.sin(a) * Ln * 0.86, 0), 0.04, 0.02) for a, Ln in zip(angs, lengths)]
    rim = tube([(x, y, 0.0) for x, y in edge], 0.03)
    return union(mem, *rays, k=0.02), rim


fins_mem, fins_rim = {}, {}
PEC_S = 0.4 * L
for sx, nm in ((1, "FinR"), (-1, "FinL")):
    c, T, D, Lat = sp.frame(PEC_S)
    base, n = surf(PEC_S, -0.12, sx, sink=0.06)
    span = norm(Lat * sx * 1.0 + T * 0.18 + D * 0.36)
    Mf = basis(span, T * 1.0 - D * 0.2)
    mem, rim = fan(np.linspace(-66, 60, 7), [0.86, 1.06, 1.2, 1.26, 1.2, 1.04, 0.82], base_w=0.2, notch=0.9)
    fins_mem[nm] = (place(mem, Mf, base), tuple(base))
    fins_rim[nm] = place(rim, Mf, base)

statics, static_glow = [], []
# dorsale tondeggiante
for s0, s1, h, sgn in ((0.5 * L, 0.68 * L, 0.36, 1), (0.74 * L, 0.86 * L, 0.3, -1)):
    top = [(s0 + (s1 - s0) * t, sgn * ((BT if sgn > 0 else BB)(s0 + (s1 - s0) * t) - 0.04 + h * math.sin(math.pi * t ** 0.7)))
           for t in np.linspace(0, 1, 9)]
    base_l = [(s, sgn * ((BT if sgn > 0 else BB)(s) - 0.08)) for s in np.linspace(s1, s0, 6)]
    statics.append(spine_fin(sp, top + base_l, 0.028, (s0 - 0.2, s1 + 0.2), (-1.2, 1.2)))
    static_glow.append(tube([tuple(sp.world(a, 0.0, b + 0.01 * sgn)) for a, b in top[1:-1]], 0.026))
# ventrali (pelviche)
for sx in (1, -1):
    s3 = 0.58 * L
    base, n = surf(s3, -1.05, sx, sink=0.03)
    c, T, D, Lat = sp.frame(s3)
    Mv = basis(norm(T * 0.7 - D * 0.6 + Lat * sx * 0.35), Lat * sx)
    mem, rim = fan(np.linspace(-30, 30, 3), [0.4, 0.46, 0.4], base_w=0.07, thick=0.024)
    statics.append(place(mem, Mv, base))
    static_glow.append(place(rim, Mv, base))
# linea laterale luminosa
for sx in (1, -1):
    pts = [surf(s, 0.05 + 0.05 * math.sin(s * 4.0), sx, sink=0.012)[0] for s in np.linspace(0.42 * L, 0.95 * L, 14)]
    static_glow.append(tube([tuple(p) for p in pts], taper(14, 0.028, 0.014)))
log("pinne pronte")

# ============================================================ coda a velo: due lobi lunghi come nastri (gruppo "Tail")
TAIL_PIVOT = tuple(sp.world(L - 0.04, 0.0, 0.0))
tail_poly = [(L - 0.12, -0.14), (L + 0.12, -0.3), (L + 0.3, -0.24), (L + 0.24, 0.0), (L + 0.3, 0.24), (L + 0.12, 0.3),
             (L - 0.12, 0.14)]
tail_fan = spine_fin(sp, tail_poly, 0.03, (L - 0.3, L + 0.6), (-0.5, 0.5))
tail_glow = [tube([tuple(sp.world(a, 0.0, b)) for a, b in tail_poly[2:5]], 0.026)]
ribbons = []


def ribbon(pts, w0, w1, thick=0.026, twist=0.0):
    """Nastro sottile lungo una curva (largo w0 all'inizio, w1 in fondo) con i bordi luminosi; ritorna (forma, bordi)."""
    rs = Spine(pts, step=0.01, n_per=14, up=(0.0, 0.0, 1.0), up2=(1.0, 0.0, 0.0), twist=twist)
    rl = rs.len

    def hw_of(t):
        return w1 + (w0 - w1) * (1.0 - t) ** 1.6

    def f(p):
        i, s, u, w = rs.coords(p)
        t = np.clip(s / rl, 0, 1)
        a = np.maximum(np.abs(w) - hw_of(t), np.maximum(-s, s - rl))
        b = np.abs(u) - thick
        return (np.minimum(np.maximum(a, b), 0.0) + np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2)).astype(np.float32)

    shape = SDF(f, rs.P.min(0) - w0 - 0.05, rs.P.max(0) + w0 + 0.05)
    idx = list(range(int(len(rs.P) * 0.08), len(rs.P), 7)) + [len(rs.P) - 1]
    edges = []
    for sg in (1, -1):
        e = [tuple(rs.P[i] + rs.D[i] * sg * (hw_of(rs.S[i] / rl) - 0.014)) for i in idx]
        edges.append(tube(e, 0.024))
    edges.append(sphere(0.05, tuple(rs.P[-1])))
    return shape, edges


# lobo alto: sale all'indietro e poi ricade ondeggiando; lobo basso: scende ondeggiando fin quasi a terra
LOBES = [(0.16, [(0.0, 0.0, 0.0), (-0.04, 0.34, 0.2), (-0.28, 0.72, 0.18), (-0.5, 1.02, -0.14), (-0.48, 1.3, -0.5),
                 (-0.66, 1.52, -0.78)], 0.5),
         (-0.16, [(0.0, 0.0, 0.0), (-0.02, 0.26, -0.28), (-0.22, 0.42, -0.66), (-0.48, 0.5, -0.98), (-0.5, 0.72, -1.3),
                  (-0.72, 0.92, -1.5)], -0.6)]
for dw, ctrl, tw in LOBES:
    start = sp.world(L + 0.1, 0.0, dw)
    shp, edges = ribbon([tuple(start + np.array(c_)) for c_ in ctrl], 0.2, 0.07, twist=tw)
    ribbons.append(shp)
    tail_glow += edges
log("code pronte")

# ============================================================ parti
m.add("Body", union(body, *brows, k=0.03), BODY, tris=4400, voxel=0.028 * VX, reflectance=0.12)
m.add("Belly", belly, BELLY, role="detail", tris=800, voxel=0.03 * VX)
m.add("Dome", dome, DOME, material="Glass", role="detail", transparency=0.55, tris=1400, voxel=0.022 * VX)
m.add("Collar", fast_union(collar + rivets), METAL, material="Metal", role="detail", tris=900, voxel=0.018 * VX)
m.add("EyeTubes", union(*tubes, k=0.02), TUBE, material="Neon", role="glow", tris=500, voxel=0.018 * VX)
m.add("Bubbles", union(*lenses), LENS, material="Neon", role="glow", tris=400, voxel=0.016 * VX)
m.add("Pupils", union(*pupils, *nares, mouth), DARK, role="eye", tris=500, voxel=0.012 * VX)
m.add("Shine", union(*shines), WHITE, role="shine", tris=80, voxel=0.008 * VX)
for nm in ("FinR", "FinL"):
    mem, piv = fins_mem[nm]
    m.add(nm, mem, FIN, role="detail", tris=450, voxel=0.024 * VX, group=nm, pivot=piv)
    m.add(nm + "Edge", fins_rim[nm], GLOW, material="Neon", role="glow", tris=300, voxel=0.016 * VX, group=nm, pivot=piv)
m.add("Fins", fast_union(statics), FIN, role="detail", tris=700, voxel=0.024 * VX)
m.add("FinGlow", fast_union(static_glow), GLOW, material="Neon", role="glow", tris=700, voxel=0.016 * VX)
m.add("TailFin", fast_union([tail_fan] + ribbons), FIN, role="detail", tris=1300, voxel=0.022 * VX, group="Tail",
      pivot=TAIL_PIVOT)
m.add("TailGlow", fast_union(tail_glow), GLOW, material="Neon", role="glow", tris=500, voxel=0.016 * VX, group="Tail",
      pivot=TAIL_PIVOT)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    ground(m)
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
    log("fatto")
