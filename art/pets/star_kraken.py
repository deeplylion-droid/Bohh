"""Kraken Stellare (StarKraken) - pet ULTRA del negozio Robux: il gigante "mega galattico".

Un kraken cosmico colossale che emerge da un vortice di nebulosa. Il mantello e' un bulbo enorme viola
profondo attraversato da una fascia di nebulosa magenta e ciano (come una via lattea), punteggiato di stelle e
di costellazioni; sulla fronte un oblo' di vetro con la cornice d'ottone a rivetti mostra una galassia a spirale
luminosa. Tre grandi occhi d'ambra con la pupilla a fessura e le palpebre arrabbiate (il terzo occhio, il piu'
grande, in mezzo alla fronte), una bocca larga a becco spalancata: placche e uncini d'avorio, due file di zanne
aguzze e la gola che brilla. Otto tentacoli spessi con il lato inferiore magenta e ventose a stella luminose:
sei fanno da base arricciandosi a terra a girandola, due si alzano altissimi ai lati in grandi S, pronti a
colpire (gruppi TentacleR/TentacleL); quello sinistro sta per afferrare un pianetino con l'anello d'ottone.
Sopra il mantello fluttua una corona di schegge di cristallo con un alone. Tocco "toy horror": una toppa
cucita sul mantello e una grossa chiave di carica d'ottone piantata nella schiena.

Effetti (nomi delle parti Neon letti da PET_FX): "Stars" = stelline, scintille e costellazioni sul mantello e
nucleo della galassia; "Nebula" = i bracci rosa del vortice di nebulosa a terra. Gli altri pezzi luminosi hanno
nomi diversi (EyeGlow, CupGlow, CupGlowR/L, GalaxyGlow, CrystalGlow, SwirlGlow).
"""
import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, box, capsule, ellipsoid, prism, project, round_cone, smin, sphere,  # noqa: E402
                     star_points, torus, union)
from lib.toy import Model  # noqa: E402

# ============================================================ colori
VIOLET = (70, 30, 150)       # corpo: viola profondo
MAGENTA = (236, 70, 196)     # lato inferiore dei tentacoli, nubi di nebulosa dipinte, fascia del pianeta
CYAN = (40, 206, 255)        # nubi ciano dipinte e pianetino
STAR = (255, 240, 178)       # stelline (Neon)
CUP = (255, 222, 110)        # ventose a stella (Neon)
EYE = (255, 186, 30)         # occhi d'ambra (Neon)
CRYSTAL = (96, 238, 255)     # corona di cristalli e bracci ciano del vortice (Neon)
NEBULA = (255, 80, 206)      # vortice di nebulosa (Neon)
GALAXY = (255, 112, 236)     # bracci della galassia e gola (Neon)
BEAK = (240, 226, 196)       # becco d'avorio
DARK = (14, 8, 30)           # bocca, orbite, pupille, fondo dell'oblo'
TOOTH = (255, 250, 238)
BRASS = (226, 166, 58)       # cornice dell'oblo', chiave di carica, anello del pianeta
PATCH = (172, 136, 246)
GLASS = (176, 232, 255)

Z = np.array([0.0, 0.0, 1.0])
rng = np.random.default_rng(7)


# ============================================================ helper (lib/ non si modifica: definiti qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / max(np.linalg.norm(v), 1e-12)


def sparse_union(shapes, k=0.0, base=None, margin=0.03):
    """Unione di tante forme: ognuna e' valutata solo dentro il proprio ingombro (punti ordinati lungo un
    asse, cosi' ogni forma tocca solo la propria fetta di punti)."""
    shapes = [s for s in shapes if s is not None]
    los = np.array([s.lo for s in shapes], dtype=np.float32) - margin - k
    his = np.array([s.hi for s in shapes], dtype=np.float32) + margin + k

    def f(p):
        d = base(p).astype(np.float32) if base is not None else np.full(len(p), 1.0, dtype=np.float32)
        if len(p) == 0:
            return d
        plo, phi = p.min(0), p.max(0)
        cand = np.nonzero(np.all((his >= plo) & (los <= phi), axis=1))[0]
        if len(cand) == 0:
            return d
        ax = int(np.argmax(phi - plo))
        order = np.argsort(p[:, ax], kind="stable")
        sv = p[order, ax]
        for i in cand:
            a = np.searchsorted(sv, los[i, ax], "left")
            b = np.searchsorted(sv, his[i, ax], "right")
            if b <= a:
                continue
            idx = order[a:b]
            msk = np.all((p[idx] >= los[i]) & (p[idx] <= his[i]), axis=1)
            if msk.any():
                ii = idx[msk]
                d[ii] = smin(d[ii], shapes[i](p[ii]), k)
        return d

    lo, hi = los.min(0), his.max(0)
    if base is not None:
        lo, hi = np.minimum(lo, base.lo), np.maximum(hi, base.hi)
    return SDF(f, lo, hi)


def blobs(centers, radii, k=0.0, nn=6):
    """Tante sfere (albero KD), con unione morbida opzionale: nuvole, puntini, bolle."""
    C = np.asarray(centers, dtype=np.float32)
    R = np.asarray(radii, dtype=np.float32)
    tree = cKDTree(C)
    kk = min(nn, len(C))

    def f(p):
        d, i = tree.query(p, k=kk)
        if kk == 1:
            d, i = d[:, None], i[:, None]
        di = d - R[i]
        mn = di.min(1)
        if k <= 0:
            return mn.astype(np.float32)
        return (mn - k * np.log(np.exp(-(di - mn[:, None]) / k).sum(1))).astype(np.float32)

    return SDF(f, C.min(0) - R.max() - k, C.max(0) + R.max() + k)


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


def thin(shape, out, inn):
    """Guscio sottile attorno alla superficie di una forma."""
    return SDF(lambda p: (lambda d: np.maximum(d - out, -(d + inn)))(shape(p)), shape.lo - out, shape.hi + out)


def flatten(shape, s, axis=2):
    """Schiaccia (s<1) una forma lungo un asse (attorno all'origine)."""
    def f(p):
        q = p.copy()
        q[:, axis] = q[:, axis] / s
        return shape(q) * min(s, 1.0)

    lo, hi = shape.lo.copy(), shape.hi.copy()
    lo[axis] *= s
    hi[axis] *= s
    return SDF(f, lo, hi)


def frame(z_dir, y_hint):
    """Rotazione (colonne x, y, z) con z = z_dir e y il piu' vicino possibile a y_hint."""
    z = norm(z_dir)
    y = np.asarray(y_hint, dtype=np.float64)
    y = y - z * np.dot(y, z)
    if np.linalg.norm(y) < 1e-6:
        y = np.array([0.0, 0.0, 1.0]) - z * z[2]
    y = norm(y)
    return np.stack([np.cross(y, z), y, z], axis=1).astype(np.float32)


def surf_frame(base, origin, direction, up=(0, 0, 1)):
    """Punto della superficie e sistema locale: x a destra (vista da fuori), -y verso l'esterno, z in su."""
    p, n = project(base, origin, direction)
    up = np.asarray(up, dtype=np.float64)
    c = norm(up - n * np.dot(n, up))
    a = norm(np.cross(c, n))
    return p, n, np.stack([a, -n, c], axis=1).astype(np.float32)


def place(shape, M, p, offset=(0, 0, 0)):
    return shape.translate(offset).rotate(M).translate(p)


def lpoint(M, p, q):
    return np.asarray(p, dtype=np.float64) + M.astype(np.float64) @ np.asarray(q, dtype=np.float64)


def normal_at(sdf, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float32)
    g = np.array([sdf((p + e)[None, :])[0] - sdf((p - e)[None, :])[0] for e in np.eye(3, dtype=np.float32) * eps])
    return g / max(np.linalg.norm(g), 1e-9)


def to_surface(sdf, p, lift=0.0, iters=5):
    p = np.asarray(p, dtype=np.float64)
    for _ in range(iters):
        p = p - normal_at(sdf, p) * (float(sdf(p[None, :].astype(np.float32))[0]) - lift)
    return p


def catmull(ctrl, n=12):
    """Spline di Catmull-Rom (centripeta) che passa per i punti di controllo."""
    P = [np.asarray(c, dtype=np.float64) for c in ctrl]
    P = [2 * P[0] - P[1]] + P + [2 * P[-1] - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        t0 = 0.0
        t1 = t0 + np.linalg.norm(p1 - p0) ** 0.5
        t2 = t1 + np.linalg.norm(p2 - p1) ** 0.5
        t3 = t2 + np.linalg.norm(p3 - p2) ** 0.5
        for t in np.linspace(t1, t2, n, endpoint=False):
            a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
            b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
            out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    out.append(P[-2])
    return np.array(out)


def resample(pts, step):
    pts = np.asarray(pts, dtype=np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(int(round(cum[-1] / step)), 2)
    s = np.linspace(0.0, cum[-1], n + 1)
    return np.stack([np.interp(s, cum, pts[:, k]) for k in range(3)], axis=1)


def seg_tube(pts, radii):
    """Tubo (catena di coni arrotondati) valutato a pezzi: veloce anche con tanti segmenti."""
    pts = np.asarray(pts, dtype=np.float64)
    radii = np.broadcast_to(np.asarray(radii, dtype=np.float64), (len(pts),))
    return sparse_union([round_cone(tuple(pts[i]), tuple(pts[i + 1]), float(radii[i]), float(radii[i + 1]))
                         for i in range(len(pts) - 1)])


# niente sotto z = 0. L'ingombro parte un filo sotto lo zero: cosi' il piano di taglio non cade su uno strato
# della griglia del marching cubes (darebbe triangoli degeneri che bloccano la decimazione)
GROUND = SDF(lambda p: -p[:, 2], (-9, -9, -0.0071), (9, 9, 9))


def shard(h, r, tip=0.42, sides=6):
    """Cristallo esagonale appuntito alle due estremita' lungo Z (semi-altezza h, raggio r)."""
    nrm = np.array([[math.cos(2 * math.pi * i / sides), math.sin(2 * math.pi * i / sides)] for i in range(sides)],
                   dtype=np.float32)
    ap = r * math.cos(math.pi / sides)
    zt = h * (1.0 - tip)
    slope = ap / (h - zt)

    def f(p):
        side = (p[:, :2] @ nrm.T).max(axis=1)
        az = np.abs(p[:, 2])
        t = np.clip((az - zt) / (h - zt), 0.0, 1.0)
        d = (side - ap * (1.0 - t)) / np.where(az > zt, math.sqrt(1 + slope * slope), 1.0)
        return np.maximum(d, az - h).astype(np.float32)

    return SDF(f, (-r, -r, -h), (r, r, h))


# ============================================================ tentacoli
class Tentacle:
    """Tentacolo lungo una curva densa: raggio che si assottiglia, lato inferiore (ventose) per ogni punto."""

    def __init__(self, pts, r0, r_tip, power, under, step=0.02):
        P = resample(pts, step)
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        self.P, self.L, self.u = P, cum[-1], cum / cum[-1]
        self.r = r_tip + (r0 - r_tip) * (1.0 - self.u) ** power
        T = np.gradient(P, axis=0)
        self.T = T / np.linalg.norm(T, axis=1, keepdims=True)
        U = under(P, self.T)
        U = U - self.T * np.sum(U * self.T, axis=1, keepdims=True)
        self.U = U / np.maximum(np.linalg.norm(U, axis=1, keepdims=True), 1e-9)
        self.tree = cKDTree(P)

    def idx(self, u):
        return int(np.clip(np.searchsorted(self.u, u), 0, len(self.u) - 1))

    def tube(self, u0=0.0, u1=1.0, dr=None, every=3):
        i0, i1 = self.idx(u0), self.idx(u1)
        ids = list(range(i0, i1, every)) + [i1]
        r = self.r[ids] + (dr(self.u[ids]) if dr is not None else 0.0)
        return seg_tube(self.P[ids], r)

    def band(self, half_deg, u0, u1):
        """Regione del lato inferiore (fascia di semi-ampiezza half_deg attorno a U) fra u0 e u1."""
        c0 = math.cos(math.radians(half_deg))
        P, U, uu, L = self.P, self.U, self.u, self.L

        def f(p):
            _, i = self.tree.query(p)
            v = p - P[i]
            dist = np.linalg.norm(v, axis=1) + 1e-9
            cosang = np.sum(v * U[i], axis=1) / dist
            val = (c0 - cosang) * dist
            val = np.maximum(val, np.maximum((u0 - uu[i]) * L, (uu[i] - u1) * L))
            return val.astype(np.float32)

        i0, i1 = self.idx(u0), self.idx(u1)
        rmax = float(self.r[i0:i1 + 1].max()) + 0.05
        return SDF(f, self.P[i0:i1 + 1].min(0) - rmax, self.P[i0:i1 + 1].max(0) + rmax)

    def cups(self, u0, u1, spacing=1.0, ang=30.0, size_k=0.5, rmin=0.045):
        """Ventose su due file alternate lungo il lato inferiore: (punto, normale, tangente, misura)."""
        out = []
        s = u0 * self.L
        side = 1
        while s < u1 * self.L:
            i = self.idx(s / self.L)
            r = self.r[i]
            if r < rmin:
                break
            t, uvec = self.T[i], self.U[i]
            a = math.radians(ang) * side
            d = norm(math.cos(a) * uvec + math.sin(a) * np.cross(t, uvec))
            out.append((self.P[i] + d * r, d, t, r * size_k))
            s += spacing * r
            side = -side
        return out

    def dorsal(self, u0, u1, step, rr, spread=55.0):
        """Puntini di stelle sparsi sul dorso (lato opposto alle ventose)."""
        out = []
        s = u0 * self.L
        while s < u1 * self.L:
            i = self.idx(s / self.L)
            t, uvec = self.T[i], -self.U[i]
            a = math.radians(rr.uniform(-spread, spread))
            d = norm(math.cos(a) * uvec + math.sin(a) * np.cross(t, uvec))
            out.append((self.P[i] + d * (self.r[i] + 0.004), float(rr.uniform(0.028, 0.038))))
            s += step * rr.uniform(0.7, 1.3)
        return out


def ground_tentacle(phi, sw, reach=1.0, R0=0.42, R1=0.11, sweep=340.0, r0=0.32, r_tip=0.035, power=0.8,
                    drift=0.07, sink=0.02):
    """Tentacolo di base: scende dal capo, striscia a terra girando a girandola e si arriccia in su
    (il lato delle ventose resta all'esterno del ricciolo)."""
    ph = math.radians(phi)
    d = np.array([math.sin(ph), -math.cos(ph), 0.0])
    e = np.array([math.cos(ph), math.sin(ph), 0.0])
    nm = 14

    def build(zg):
        ctrl = [0.12 * d + 1.1 * Z, 0.45 * d + 0.86 * Z, 0.82 * d + 0.05 * sw * e + 0.48 * Z,
                1.18 * d + 0.16 * sw * e + zg[0] * Z, 1.55 * reach * d + 0.34 * sw * reach * e + zg[1] * Z,
                1.95 * reach * d + 0.55 * sw * reach * e + zg[2] * Z]
        main = catmull(ctrl, nm)
        h = main[-1] - main[-2]
        h[2] = 0.0
        h = norm(h)
        B = norm(np.cross(Z, h))
        C = main[-1] + Z * R0
        t = np.linspace(0.0, 1.0, 48)
        a = np.radians(-90.0 + sweep * t)
        R = R0 + (R1 - R0) * t ** 0.9
        curl = C[None] + R[:, None] * (np.cos(a)[:, None] * h[None] + np.sin(a)[:, None] * Z[None]) \
            + B[None] * (drift * sw * t)[:, None]
        return np.vstack([main, curl[1:]]), B, len(main)

    zg = [0.2, 0.17, 0.14]
    for _ in range(2):  # il raggio dipende dalla lunghezza: due passate per poggiare bene a terra
        pts, B, nmain = build(zg)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        u = cum / cum[-1]
        zg = [r_tip + (r0 - r_tip) * (1 - u[k * nm]) ** power - sink for k in (3, 4, 5)]

    def under(P, T):
        return np.cross(np.broadcast_to(B, T.shape), T)

    tn = Tentacle(pts, r0, r_tip, power, under)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    tn.u_curl = float(np.sum(seg[:nmain - 1]) / np.sum(seg))
    return tn


# tentacoli alzati: (x, y, z) del lato destro; S che esce bassa, si alza, rientra in vita e si arriccia in alto
RAISED = [(0.32, -0.05, 1.2), (0.92, -0.24, 0.98), (1.48, -0.4, 0.98), (1.92, -0.5, 1.42), (2.06, -0.48, 2.12),
          (1.86, -0.44, 2.76), (1.6, -0.56, 3.24), (1.66, -0.8, 3.6), (1.9, -1.02, 3.72), (2.06, -1.14, 3.56),
          (2.0, -1.12, 3.38)]


def raised_tentacle(sx):
    pts = catmull([(sx * x, y, z) for x, y, z in RAISED], 12)
    target = np.array([0.0, -1.8, 2.2])

    def under(P, T):
        return target[None] - P

    return Tentacle(pts, 0.35, 0.04, 0.72, under)


GT = [ground_tentacle(24, 1, reach=1.03, R0=0.44, sweep=345),
      ground_tentacle(-22, 1, reach=0.97, R0=0.4, sweep=330),
      ground_tentacle(108, 1, reach=1.06, R0=0.42, sweep=340),
      ground_tentacle(-112, 1, reach=1.04, R0=0.44, sweep=345),
      ground_tentacle(158, 1, reach=0.99, R0=0.4, sweep=330),
      ground_tentacle(-156, 1, reach=1.03, R0=0.42, sweep=340)]
RT = {1: raised_tentacle(1), -1: raised_tentacle(-1)}

# ============================================================ testa e mantello
m = Model("StarKraken", "pet")
HEAD_C = np.array([0.0, -0.06, 1.48])
MANT_C = np.array([0.0, 0.36, 2.32])
TILT = 18.0
MANT_UP = np.array([0.0, math.sin(math.radians(TILT)), math.cos(math.radians(TILT))])
head = ellipsoid((1.0, 0.92, 0.8), tuple(HEAD_C))
mantle = ellipsoid((1.03, 1.1, 1.0), tuple(MANT_C)).rot(-TILT, 0, 0, pivot=tuple(MANT_C))
core = union(head, mantle, k=0.5)

# ---- tre occhi: il terzo occhio centrale, piu' grande e alto, con la palpebra a V; i laterali storti
EYES = [dict(d=(0.0, -0.85, 0.55), R=(0.31, 0.14, 0.26), sink=0.055, cut=0.1, slope=0.0, vee=0.42),
        dict(d=(0.7, -0.72, 0.07), R=(0.24, 0.12, 0.2), sink=0.045, cut=0.06, slope=0.45, vee=0.0),
        dict(d=(-0.7, -0.72, 0.07), R=(0.24, 0.12, 0.2), sink=0.045, cut=0.06, slope=-0.45, vee=0.0)]


def below(cut, slope, vee):
    """Semispazio sotto la linea della palpebra z = cut + slope*x + vee*|x| (coordinate locali)."""
    k = 1.0 / math.sqrt(1 + slope ** 2 + vee ** 2)
    return SDF(lambda p: (p[:, 2] - cut - slope * p[:, 0] - vee * np.abs(p[:, 0])) * k, (-2, -2, -2), (2, 2, 2))


def front_of(y):
    """Semispazio davanti al piano locale y (taglia il retro nascosto di occhi e orbite)."""
    return SDF(lambda p: p[:, 1] - y, (-2, -2, -2), (2, 2, 2))


eye_glow, sockets, pupils, shines, lids, brows = [], [], [], [], [], []
for e in EYES:
    p, n, M = surf_frame(core, HEAD_C, e["d"])
    rx, ry, rz = e["R"]
    sk = e["sink"]
    eye = ellipsoid((rx, ry, rz), (0, sk, 0))
    cut = below(e["cut"], e["slope"], e["vee"])
    eye_glow.append(place(eye.intersect(cut, k=0.008).intersect(front_of(sk)), M, p))
    sockets.append(place(ellipsoid((rx * 1.2, ry * 0.9, rz * 1.24), (0, sk + 0.016, 0))
                         .intersect(below(e["cut"] + 0.03, e["slope"], e["vee"]), k=0.008)
                         .intersect(front_of(sk - 0.01)), M, p))
    # pupilla a fessura verticale, stretta e appuntita: sguardo da predatore, un po' in basso verso il giocatore
    pupils.append(place(thin(eye, 0.006, 0.02).intersect(ellipsoid((rx * 0.2, 0.5, rz * 0.8), (0, 0, -0.02)))
                        .intersect(front_of(sk - 0.02)), M, p))
    # palpebra superiore (pelle) che taglia l'occhio e sopracciglio
    lids.append(place(ellipsoid((rx * 1.2, ry * 1.3, rz * 1.24), (0, sk - 0.008, 0)).subtract(cut, k=0.01), M, p))
    zo = e["cut"] + abs(e["slope"]) * rx + e["vee"] * rx + 0.1
    if e["vee"] > 0:
        for s in (1, -1):
            brows.append(place(capsule((s * rx * 1.08, -0.03, zo), (0, -0.06, e["cut"] + 0.08), 0.05), M, p))
    else:
        inner = -1 if e["slope"] > 0 else 1
        zi = e["cut"] - abs(e["slope"]) * rx + 0.08
        brow = round_cone((inner * rx * 0.95, -0.06, zi), (-inner * rx * 0.95, -0.02, zo - 0.02), 0.045, 0.026)
        brows.append(place(brow, M, p))
    shines.append(place(sphere(rx * 0.14), M, p, (-rx * 0.45, sk - ry * 0.84, rz * 0.12)))
    shines.append(place(sphere(rx * 0.075), M, p, (rx * 0.42, sk - ry * 0.82, -rz * 0.45)))

face = union(core, *lids, k=0.02)
face = union(face, *brows, k=0.05)

# ---- oblo' sulla fronte (posizione)
PD, ND = project(core, MANT_C, (0.0, -0.9, 0.42))
MD = frame(ND, (0, 0, 1))
DOME_A = 0.38                        # raggio dell'apertura
REC_C = PD + ND * 0.1
recess = sphere(0.35, tuple(REC_C))

# ---- bocca larga a becco (coordinate locali del sistema MM in PM: x a destra, -y fuori, z su)
PM, NM, MM = surf_frame(core, HEAD_C, (0.0, -1.0, -0.34))


def z_top(x):
    return 0.11 - 0.42 * x * x


def z_bot(x):
    return -0.21 + 0.8 * x * x


def lens_fn(p):
    return (np.maximum(p[:, 2] - z_top(p[:, 0]), z_bot(p[:, 0]) - p[:, 2]) * 0.8).astype(np.float32)


mouth_l = SDF(lens_fn, (-0.6, -0.6, -0.4), (0.6, 0.6, 0.3)).intersect(ellipsoid((0.56, 0.34, 0.32), (0, 0.06, -0.04)))
mouth_cav = place(mouth_l, MM, PM)

# ============================================================ corpo (testa, mantello e radici dei tentacoli)
SPLIT = 1.3   # lunghezza dalla radice a cui i tentacoli di base passano dalla parte Body alla parte Tentacles
stubs = []
for tn in GT:
    tn.us = SPLIT / tn.L
    stubs.append(tn.tube(0.0, tn.us + 0.03))
for sx, tn in RT.items():
    # punto in cui il tentacolo alzato esce dalla testa: perno dell'animazione
    i_out = int(np.nonzero(face(tn.P.astype(np.float32)) > 0)[0][0])
    tn.us = tn.u[i_out] + 0.03
    tn.pivot = tuple(float(v) for v in np.round(tn.P[i_out], 3))
    stubs.append(tn.tube(0.0, tn.us + 0.02))

body = sparse_union(stubs, k=0.24, base=face)
body = body.subtract(recess, k=0.02).subtract(mouth_cav, k=0.025).intersect(GROUND)   # radici poggiate a z = 0
m.add("Body", body, VIOLET, reflectance=0.12, tris=10200, voxel=0.022)


def ramp_dr(u0, du=0.04, a=-0.014, b=0.006):
    return lambda u: a + (b - a) * np.clip((u - u0) / du, 0.0, 1.0)


tents = [tn.tube(tn.us - 0.03, 1.0, dr=ramp_dr(tn.us - 0.03)) for tn in GT]
m.add("Tentacles", sparse_union(tents).intersect(GROUND), VIOLET, reflectance=0.12, tris=9400, voxel=0.022)

for sx, nm in ((1, "TentacleR"), (-1, "TentacleL")):
    tn = RT[sx]
    m.add(nm, tn.tube(tn.us - 0.035, 1.0, dr=ramp_dr(tn.us - 0.035)), VIOLET, reflectance=0.12, tris=3500,
          voxel=0.02, group=nm, pivot=tn.pivot)


# ============================================================ lato inferiore magenta e ventose a stella
def cup_stars(cups):
    """Ventosa a stella luminosa a quattro punte, appoggiata sulla fascia magenta."""
    out = []
    for p, nrm, t, sz in cups:
        st = prism(star_points(4, sz * 0.76, sz * 0.23), -0.006, 0.026 + sz * 0.1)
        out.append(st.rotate(frame(nrm, t)).translate(tuple(p)))
    return out


# fasce spesse verso l'interno: restano intere anche con i voxel grossi che il budget di triangoli impone
under_parts, cup_glow, specks = [], [], []
for tn in GT:
    under_parts.append(shell_paint(tn.tube(tn.u_curl - 0.08, 1.0), tn.band(64, tn.u_curl - 0.07, 1.0),
                                   out=0.02, inn=0.08))
    cup_glow += cup_stars(tn.cups(tn.u_curl - 0.02, 0.96, spacing=1.2, ang=30, size_k=0.7, rmin=0.085))
    specks += tn.dorsal(tn.us, tn.u_curl + 0.12, 0.3, rng)

for sx, nm in ((1, "R"), (-1, "L")):
    tn = RT[sx]
    paint = shell_paint(tn.tube(tn.us, 1.0), tn.band(60, tn.us + 0.02, 1.0), out=0.02, inn=0.08)
    stars = cup_stars(tn.cups(tn.us + 0.04, 0.96, spacing=1.15, ang=30, size_k=0.64, rmin=0.075))
    sp = tn.dorsal(tn.us + 0.05, 0.86, 0.32, rng)
    stars.append(blobs([c for c, _ in sp], [r for _, r in sp]))
    m.add(f"Tentacle{nm}Under", paint, MAGENTA, role="detail", tris=1300, voxel=0.03,
          group=f"Tentacle{nm}", pivot=tn.pivot)
    m.add(f"CupGlow{nm}", sparse_union(stars), CUP, material="Neon", role="glow", tris=800, voxel=0.012,
          group=f"Tentacle{nm}", pivot=tn.pivot)

# ---- toppa cucita sul mantello (lato destro) e chiave di carica sulla schiena: posizioni
PP, _, MP = surf_frame(core, MANT_C, (0.92, 0.1, 0.4))
PATCH_W, PATCH_H, PATCH_ROT = 0.2, 0.17, 12.0
patch_reg = place(prism([(-PATCH_W, -PATCH_H), (PATCH_W, -PATCH_H), (PATCH_W, PATCH_H), (-PATCH_W, PATCH_H)], -0.5, 0.5)
                  .rot(90, 0, 0).rot(0, PATCH_ROT, 0), MP, PP)
PK, NK = project(core, MANT_C, (0.0, 0.92, 0.3))

# ---- fascia di nebulosa dipinta sul mantello (come una via lattea): nubi magenta con nuclei ciano
EXCL = union(sphere(0.64, tuple(PD)),                                  # oblo'
             sphere(0.82, tuple(HEAD_C + np.array([0.0, -0.72, 0.2]))),  # faccia
             sphere(0.36, tuple(PP)), sphere(0.3, tuple(PK)))            # toppa e chiave
BAND_A = norm((-0.86, -0.36, 0.34))
BAND_W = norm(np.cross(BAND_A, norm((0.62, 0.6, 0.48))))
BAND_B = np.cross(BAND_W, BAND_A)
mag_c, mag_r, cy_c, cy_r, band_pts = [], [], [], [], []
rr = np.random.default_rng(3)
for k, t in enumerate(np.linspace(-0.3, 2.6, 36)):
    d = math.cos(t) * BAND_A + math.sin(t) * BAND_B
    p, _ = project(core, MANT_C, d)
    if p[2] < 1.9:
        continue
    band_pts.append(p)
    w = 0.21 + 0.07 * math.sin(3.1 * t + 0.5) + 0.04 * math.sin(7.3 * t)
    mag_c.append(p)
    mag_r.append(w)
    for _ in range(3):
        q = p + BAND_W * rr.normal() * w * 1.2 + rr.normal(size=3) * 0.05
        pp, _ = project(core, MANT_C, q - MANT_C)
        mag_c.append(pp)
        mag_r.append(w * rr.uniform(0.4, 0.75))
    q = p + BAND_W * (0.08 * math.sin(2.3 * t)) + rr.normal(size=3) * 0.025
    pp, _ = project(core, MANT_C, q - MANT_C)
    cy_c.append(pp)
    cy_r.append(w * rr.uniform(0.3, 0.48))
# una seconda nube piu' piccola sul fianco destro davanti
for d, w in (((0.86, -0.25, 0.3), 0.17), ((0.8, -0.05, 0.12), 0.15), ((0.92, -0.42, 0.02), 0.12)):
    p, _ = project(core, MANT_C, d)
    mag_c.append(p)
    mag_r.append(w)
    for _ in range(2):
        pp, _ = project(core, MANT_C, p + rr.normal(size=3) * w - MANT_C)
        mag_c.append(pp)
        mag_r.append(w * rr.uniform(0.4, 0.7))
for d, w in (((0.84, -0.18, 0.2), 0.075), ((0.86, -0.32, 0.1), 0.05)):
    p, _ = project(core, MANT_C, d)
    cy_c.append(p)
    cy_r.append(w)
mag_region = blobs(mag_c, mag_r, k=0.06).subtract(EXCL)
cy_region = blobs(cy_c, cy_r, k=0.04).subtract(EXCL)
under_parts.append(shell_paint(core, mag_region, out=0.02, inn=0.07))

# ============================================================ pianetino con l'anello: la preda che il tentacolo
# sinistro sta per afferrare (fa capire la scala "galattica")
PLANET_C = np.array([-1.1, -1.36, 3.08])
PLANET_R = 0.25
planet = sphere(PLANET_R, tuple(PLANET_C))
planet_band = shell_paint(planet, box((0.5, 0.5, 0.075)).rot(24, -28, 0).translate(tuple(PLANET_C)), out=0.022,
                          inn=0.06)
planet_ring = flatten(torus(0.43, 0.085), 0.36).rot(24, -28, 0).translate(tuple(PLANET_C))
under_parts.append(planet_band)
m.add("Underside", sparse_union(under_parts).intersect(GROUND), MAGENTA, role="detail", tris=4400, voxel=0.032)

# ============================================================ oblo': galassia, vetro, ottone
gal_arms, gal_stars = [], []
GAL_C = PD - ND * 0.05
for j in range(2):
    th = np.linspace(0.0, 1.6 * math.pi, 28)
    r = 0.05 * np.exp(0.34 * th)
    pts = [MD @ np.array([ri * math.cos(t + j * math.pi), ri * math.sin(t + j * math.pi), 0.0]) + GAL_C
           for ri, t in zip(r, th)]
    gal_arms.append(seg_tube(pts, np.linspace(0.045, 0.014, len(pts))))
gal_core = ellipsoid((0.085, 0.085, 0.05)).rotate(MD).translate(tuple(GAL_C))
for i in range(11):
    a = rng.uniform(0, 2 * math.pi)
    rr_ = rng.uniform(0.1, 0.3)
    gal_stars.append(sphere(rng.uniform(0.02, 0.026), tuple(MD @ np.array([rr_ * math.cos(a), rr_ * math.sin(a),
                                                                        rng.uniform(-0.05, 0.04)]) + GAL_C)))

DOME_H = 0.2
DOME_R = (DOME_A ** 2 + DOME_H ** 2) / (2 * DOME_H)
dome = sphere(DOME_R, tuple(PD - ND * (DOME_R - DOME_H))).intersect(
    SDF(lambda p: ((-(p - PD.astype(np.float32)) @ ND.astype(np.float32)) - 0.06).astype(np.float32),
        PD - 1.0, PD + 1.0))
m.add("Dome", dome, GLASS, material="Glass", role="detail", transparency=0.35, reflectance=0.1, tris=700,
      voxel=0.02)

brass = [torus(DOME_A + 0.01, 0.048).rotate(MD).translate(tuple(PD)), planet_ring]
for i in range(10):
    a = 2 * math.pi * i / 10
    brass.append(sphere(0.028, tuple(PD + MD @ np.array([(DOME_A + 0.01) * math.cos(a), (DOME_A + 0.01) * math.sin(a),
                                                         0.045]))))

# ---- chiave di carica d'ottone al centro della schiena (impugnatura verticale, un po' girata)
KW = norm(np.cross(NK, (1.0, 0.0, 0.0)))
KW = norm(KW * math.cos(math.radians(25)) + np.cross(NK, KW) * math.sin(math.radians(25)))
KA = norm(np.cross(NK, KW))
brass.append(capsule(tuple(PK - NK * 0.12), tuple(PK + NK * 0.5), 0.06))
brass.append(round_cone(tuple(PK - NK * 0.02), tuple(PK + NK * 0.1), 0.15, 0.12))
bow_c = PK + NK * 0.62
for s in (1, -1):
    brass.append(torus(0.19, 0.058).rotate(frame(KA, NK)).translate(tuple(bow_c + KW * s * 0.22 + NK * 0.04)))
brass.append(sphere(0.1, tuple(bow_c)))
m.add("Brass", sparse_union(brass, k=0.02), BRASS, material="Metal", role="detail", tris=1800, voxel=0.015)

# ============================================================ faccia: occhi, bocca, becco, denti
m.add("EyeGlow", union(*eye_glow), EYE, material="Neon", role="glow", tris=1300, voxel=0.012)
mouth_lining = thin(mouth_cav, 0.03, 0.008).intersect(core.offset(-0.004))
bowl = thin(recess, 0.022, 0.01).intersect(core.offset(-0.004))
m.add("Sockets", sparse_union(sockets + [mouth_lining, bowl]), DARK, role="eye", tris=1500, voxel=0.018)
m.add("Pupils", sparse_union(pupils), DARK, role="eye", tris=500, voxel=0.009)

# becco d'avorio: due placche a mezzaluna che incorniciano la bocca, con l'uncino al centro (in alto
# scende sulla bocca, in basso sale dal mento)
def h_up(x):
    return 0.075 + 0.06 * np.clip(1.0 - (x / 0.5) ** 2, 0.0, 1.0)


def h_lo(x):
    return 0.065 + 0.045 * np.clip(1.0 - (x / 0.48) ** 2, 0.0, 1.0)


def plate_reg(fn, xmax):
    return place(SDF(lambda p: (np.maximum(np.maximum(fn(p), np.abs(p[:, 0]) - xmax), np.abs(p[:, 1]) - 0.3) * 0.8)
                     .astype(np.float32), (-0.7, -0.35, -0.5), (0.7, 0.35, 0.4)), MM, PM)


up_plate = plate_reg(lambda p: np.maximum(z_top(p[:, 0]) - p[:, 2], p[:, 2] - z_top(p[:, 0]) - h_up(p[:, 0])), 0.5)
lo_plate = plate_reg(lambda p: np.maximum(p[:, 2] - z_bot(p[:, 0]), z_bot(p[:, 0]) - h_lo(p[:, 0]) - p[:, 2]), 0.48)
hook_up = seg_tube([(0, 0.04, 0.25), (0, -0.09, 0.2), (0, -0.165, 0.09), (0, -0.165, -0.02), (0, -0.11, -0.085)],
                   [0.1, 0.085, 0.06, 0.03, 0.006])
hook_lo = seg_tube([(0, 0.04, -0.35), (0, -0.08, -0.31), (0, -0.14, -0.22), (0, -0.12, -0.14)],
                   [0.085, 0.065, 0.035, 0.006])
beak = union(shell_paint(body, up_plate, out=0.05, inn=0.06), shell_paint(body, lo_plate, out=0.045, inn=0.06),
             place(union(flatten(hook_up, 0.6, axis=0), flatten(hook_lo, 0.6, axis=0)), MM, PM), k=0.03)
m.add("Beak", beak, BEAK, role="detail", reflectance=0.15, tris=1500, voxel=0.013)


def surf_local(x, z, inset):
    """Punto della superficie della testa davanti a (x, z) della bocca, affondato di 'inset'."""
    o = lpoint(MM, PM, (x, 0.35, z))
    p, nn = project(core, o, NM)
    return p - nn * inset


teeth = []
DOWN = -MM[:, 2].astype(np.float64)
for x, L, r in ((0.085, 0.12, 0.034), (0.165, 0.13, 0.036), (0.245, 0.11, 0.033), (0.32, 0.09, 0.029),
                (0.39, 0.065, 0.024)):
    for s in (1, -1):
        b = surf_local(s * x, z_top(x) + 0.025, 0.0)
        teeth.append(round_cone(tuple(b), tuple(b + DOWN * L + NM * 0.012), r, 0.003))
for x, L, r in ((0.12, 0.1, 0.032), (0.2, 0.095, 0.03), (0.28, 0.08, 0.027), (0.36, 0.06, 0.022)):
    for s in (1, -1):
        b = surf_local(s * x, z_bot(x) - 0.025, 0.0)
        teeth.append(round_cone(tuple(b), tuple(b - DOWN * L + NM * 0.012), r, 0.003))
shine_parts = teeth + shines

# ============================================================ toppa cucita (lato destro del mantello)
m.add("Patch", shell_paint(face, patch_reg, out=0.032, inn=0.03), PATCH, material="Fabric", role="detail", tris=400,
      voxel=0.014)
corners = [(-PATCH_W, -PATCH_H), (PATCH_W, -PATCH_H), (PATCH_W, PATCH_H), (-PATCH_W, PATCH_H)]
ca, sa = math.cos(math.radians(-PATCH_ROT)), math.sin(math.radians(-PATCH_ROT))


def patch_pt(q, lift):
    w = lpoint(MP, PP, (q[0] * ca - q[1] * sa, 0.0, q[0] * sa + q[1] * ca))
    return to_surface(face, w, lift=lift)


stitches = []
for k in range(4):
    a, b = np.array(corners[k]), np.array(corners[(k + 1) % 4])
    tang = norm(b - a)
    nrm2 = np.array([-tang[1], tang[0]])
    for t in np.linspace(0.14, 0.86, 4):
        q = a + (b - a) * t
        for s in (1, -1):  # punto a X a cavallo del bordo, ad arco sopra la toppa
            dd = (tang * 0.65 * s + nrm2) * 0.042
            stitches.append(seg_tube([patch_pt(q - dd, 0.012), patch_pt(q, 0.042), patch_pt(q + dd, 0.012)], 0.012))
shine_parts += stitches
m.add("Shine", sparse_union(shine_parts), TOOTH, role="shine", tris=1800, voxel=0.0095)

# ============================================================ vortice di nebulosa a terra: tre bracci rosa a nastro che
# finiscono in nuvolette (parte "Nebula") e tre bracci ciano piu' sottili in mezzo (con la corona in "CrystalGlow")
neb_arms, cy_arms, cl_c, cl_r = [], [], [], []
for j in range(3):
    th0 = math.radians(80 + 120 * j)
    t = np.linspace(0.0, 1.0, 44)
    rad = 0.85 + 1.85 * t
    th = th0 + 2.8 * t
    pts = np.stack([rad * np.cos(th), rad * np.sin(th), np.zeros_like(t)], axis=1)
    neb_arms.append(seg_tube(pts, 0.07 + 0.17 * np.sin(np.pi * np.minimum(t * 1.05, 1.0)) ** 0.75))
    e = pts[-4]
    for dx, dy, dz, r_ in ((0.0, 0.0, 0.05, 0.16), (0.13, 0.07, 0.03, 0.12), (-0.11, 0.1, 0.02, 0.11),
                           (0.04, -0.13, 0.02, 0.1), (0.0, 0.03, 0.15, 0.09)):
        cl_c.append(e + np.array([dx, dy, dz]))
        cl_r.append(r_)
    tc = t[:38]
    thc = th0 + math.radians(60) + 2.8 * tc
    radc = 0.9 + 1.85 * tc
    cy_arms.append(seg_tube(np.stack([radc * np.cos(thc), radc * np.sin(thc), np.zeros_like(tc)], axis=1),
                            0.05 + 0.065 * np.sin(np.pi * tc / tc[-1])))
nebula = union(flatten(sparse_union(neb_arms), 0.42), flatten(blobs(cl_c, cl_r, k=0.05), 0.85), k=0.04)
nebula = nebula.intersect(GROUND)
cyan_swirl = flatten(sparse_union(cy_arms), 0.55).intersect(GROUND)

# ============================================================ corona di schegge di cristallo fluttuanti
TOP, _ = project(core, MANT_C, MANT_UP)
CROWN_UP = np.array([0.0, math.sin(math.radians(7)), math.cos(math.radians(7))])   # quasi dritta: si legge di fronte
CC = TOP + np.array([0.0, -0.06, 0.1])
FWD = norm(np.array([0.0, -1.0, 0.0]) - CROWN_UP * np.dot([0.0, -1.0, 0.0], CROWN_UP))
SIDE = np.array([1.0, 0.0, 0.0])
crystals = [torus(0.56, 0.036).rotate(frame(CROWN_UP, FWD)).translate(tuple(CC))]
for psi, hh, rho in ((0, 0.33, 0.46), (36, 0.26, 0.5), (-36, 0.26, 0.5), (74, 0.22, 0.53), (-74, 0.22, 0.53),
                     (115, 0.18, 0.53), (-115, 0.18, 0.53), (152, 0.15, 0.5), (-152, 0.15, 0.5)):
    a = math.radians(psi)
    radial = math.cos(a) * FWD + math.sin(a) * SIDE
    c = CC + radial * rho + CROWN_UP * hh * 0.8
    ax = norm(CROWN_UP + radial * 0.28)
    crystals.append(shard(hh, hh * 0.38).rotate(frame(ax, radial)).translate(tuple(c)))
for psi, hh, rho, up in ((18, 0.1, 0.84, 0.1), (-58, 0.09, 0.83, 0.3), (105, 0.09, 0.8, 0.06),
                         (-140, 0.08, 0.78, 0.2), (165, 0.085, 0.8, 0.34)):
    a = math.radians(psi)
    radial = math.cos(a) * FWD + math.sin(a) * SIDE
    crystals.append(shard(hh, hh * 0.48).rotate(frame(norm(CROWN_UP + radial * 0.6), radial))
                    .translate(tuple(CC + radial * rho + CROWN_UP * up)))
m.add("CrystalGlow", sparse_union(crystals), CRYSTAL, material="Neon", role="glow", tris=1800, voxel=0.016)

m.add("Cyan", union(shell_paint(core, cy_region, out=0.03, inn=0.07), planet), CYAN, role="detail", tris=1300,
      voxel=0.024)

# ============================================================ galassia (bracci) e gola luminosa
throat = place(sphere(0.09), MM, PM, (0, 0.22, -0.04))
m.add("GalaxyGlow", sparse_union(gal_arms + [throat]), GALAXY, material="Neon", role="glow", tris=1000, voxel=0.012)

# ============================================================ stelle (effetto "Stars"): puntini e costellazioni
def slerp_dirs(d0, d1, n):
    d0, d1 = norm(d0), norm(d1)
    om = math.acos(float(np.clip(np.dot(d0, d1), -1.0, 1.0)))
    return [d0 if om < 1e-6 else (math.sin((1 - t) * om) * d0 + math.sin(t * om) * d1) / math.sin(om)
            for t in np.linspace(0.0, 1.0, n)]


def twinkle(c, nrm, L, r0=0.032, rc=0.044):
    t1 = norm(np.cross(nrm, Z))
    t2 = np.cross(nrm, t1)
    return [round_cone(tuple(c), tuple(c + dd * L), r0, 0.006) for dd in (t1, -t1, t2, -t2)] + [sphere(rc, tuple(c))]


# costellazioni: stelle unite da linee luminose che seguono la superficie del mantello
CONST = [([(0.3, -0.55, 0.8), (0.55, -0.45, 0.72), (0.74, -0.36, 0.52), (0.68, -0.1, 0.74), (0.48, 0.04, 0.9)],
          [(0, 1), (1, 2), (2, 3), (3, 4), (1, 3)]),
         ([(-0.76, 0.42, 0.48), (-0.58, 0.66, 0.52), (-0.76, 0.6, 0.12), (-0.42, 0.86, 0.24)],
          [(0, 1), (1, 2), (1, 3)]),
         ([(0.5, 0.78, -0.02), (0.76, 0.54, 0.02), (0.42, 0.9, 0.24)], [(0, 1), (0, 2)])]
const_parts, const_pts = [], []
for nodes, edges in CONST:
    for a, b in edges:
        pts = []
        for d in slerp_dirs(nodes[a], nodes[b], 8):
            p, nrm = project(core, MANT_C, d)
            pts.append(p + nrm * 0.012)
        const_parts.append(seg_tube(pts, 0.022))
    for d in nodes:
        p, nrm = project(core, MANT_C, d)
        const_pts.append(p)
        const_parts += twinkle(p + nrm * 0.012, nrm, 0.085, r0=0.028, rc=0.042)

st_c, st_r = [], []
tries = 0
while len(st_c) < 30 and tries < 4000:
    tries += 1
    if band_pts and rng.random() < 0.5:   # piu' fitte dentro la fascia di nebulosa
        q = band_pts[rng.integers(len(band_pts))] + rng.normal(size=3) * 0.18
        v = norm(q - MANT_C)
    else:
        v = rng.normal(size=3)
        v[2] = abs(v[2]) * 1.2 + 0.1
        v = norm(v)
    p, nrm = project(core, MANT_C, v)
    q = p[None].astype(np.float32)
    if EXCL(q)[0] < 0.02 or patch_reg(q)[0] < 0.06:
        continue
    if p[2] < 1.85 or any(np.linalg.norm(p - c) < 0.15 for c in st_c + const_pts):
        continue
    st_c.append(p + nrm * 0.006)
    st_r.append(rng.uniform(0.03, 0.042))
twinkles = []
for d, L in (((-0.55, 0.4, 0.75), 0.15), ((0.35, 0.85, 0.4), 0.15), ((-0.8, -0.05, 0.42), 0.13),
             ((0.12, 0.42, 1.0), 0.13)):
    c, nrm = project(core, MANT_C, d)
    twinkles += twinkle(c + nrm * 0.01, nrm, L, r0=0.034, rc=0.048)
m.add("Stars", sparse_union([blobs(st_c, st_r), gal_core, *gal_stars, *twinkles, *const_parts]), STAR, material="Neon",
      role="glow", tris=2800, voxel=0.0105)

# ============================================================ vortice di nebulosa a terra (effetto "Nebula")
for c, r in (((2.5, -1.25, 0.0), 0.06), ((-2.55, 0.9, 0.0), 0.05), ((0.6, 2.75, 0.0), 0.055),
             ((-1.4, -2.3, 0.0), 0.05)):
    specks.append((np.array(c) + np.array([0, 0, 0.02]), r))
m.add("Nebula", nebula, NEBULA, material="Neon", role="glow", tris=3400, voxel=0.04)
m.add("SwirlGlow", cyan_swirl, CRYSTAL, material="Neon", role="glow", tris=1000, voxel=0.04)
m.add("CupGlow", sparse_union(cup_glow + [blobs([c for c, _ in specks], [r for _, r in specks])])
      .intersect(GROUND), CUP, material="Neon", role="glow", tris=2900, voxel=0.013)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
