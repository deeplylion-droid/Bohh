"""Leone Nebulosa (NebulaLion) - pet ULTRA del negozio Robux: il gigante piu' spettacolare del gioco.

Re leone celeste colossale, ritto e fiero su un frammento di asteroide sospeso nel vuoto (roccia spigolosa
che finisce a punta, schegge di cristallo luminose, sassi che gli orbitano attorno). La testa e' alta e
ruggisce verso chi guarda; la zampa anteriore destra e' avanzata su uno sperone di roccia.

- Corpo blu notte con muscoli marcati e puntini di stelle; su spalle e fianchi la costellazione del Leone
  in linee d'oro luminose (parte Neon "StarLines").
- CRINIERA a galassia a spirale, molto piu' grande della testa: ciuffi a fiamma su piu' strati che girano
  attorno al muso, dal nucleo luminoso (Neon "GalaxyCore") al magenta, al viola, fino ai bracci a spirale
  ciano (Neon "Nebula": il gioco ci attacca la nebbiolina luminosa rosa/viola/ciano).
- Occhi d'oro luminosi come stelle (con scintilla a quattro punte), zanne, sopracciglia possenti.
- Corona: un sottile anello d'oro inclinato sospeso sopra la testa, con tre pianetini in orbita.
- Coda con il ciuffo a cometa (Neon "Stars": il gioco ci attacca le scintille bianco-oro); la coda e'
  il gruppo "Tail" e ondeggia attorno all'attaccatura.
- Tocco "toy horror": sul petto una cucitura a punti incrociati mezza scucita da cui esce l'imbottitura
  di polvere di stelle luminosa.
"""
import itertools
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, box, capsule, crystal, ellipsoid, euler, project, round_cone, smin,  # noqa: E402
                     sphere, torus, tube, union)
from lib.toy import Model  # noqa: E402


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
    return [tuple(float(x) for x in q) for q in out]


def flatten(shape, s, axis=1):
    """Schiaccia (s<1) o allunga (s>1) una forma lungo un asse, con distanza conservativa."""
    def f(p):
        q = p.copy()
        q[:, axis] = q[:, axis] / s
        return shape(q) * min(s, 1.0)

    lo, hi = shape.lo.copy(), shape.hi.copy()
    lo[axis] *= s
    hi[axis] *= s
    return SDF(f, lo, hi)


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
    """Guscio sottile di una forma (per disegni sopra altre parti)."""
    return SDF(lambda p: (lambda d: np.maximum(d - out, -(d + inn)))(shape(p)), shape.lo - out, shape.hi + out)


def taper(n, r0, r1, power=1.0):
    return [r0 + (r1 - r0) * (i / (n - 1)) ** power for i in range(n)]


def horn(p0, p1, p2, p3, r0, r1, n=12, power=0.9):
    """Corno/artiglio affusolato lungo una bezier."""
    return tube(bezier(p0, p1, p2, p3, n), taper(n + 1, r0, r1, power))


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


def lerp(a, b, t):
    return tuple(np.asarray(a, dtype=np.float64) * (1 - t) + np.asarray(b, dtype=np.float64) * t)


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


def project_many(sdf, origins, dirs, max_dist=2.0, n=200):
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
    return pts, normals_at(sdf, pts)


def ray_hits(sdf, origins, dirs, max_dist=4.0, n=320):
    """Raggi che partono FUORI dalla forma: (punti, normali, colpito?) del primo contatto."""
    D = np.asarray(dirs, dtype=np.float64).reshape(-1, 3)
    D = D / np.linalg.norm(D, axis=1, keepdims=True)
    O = np.asarray(origins, dtype=np.float64).reshape(-1, 3)
    if len(D) == 1:
        D = np.repeat(D, len(O), axis=0)
    ts = np.linspace(0.0, max_dist, n)
    P = (O[:, None, :] + ts[None, :, None] * D[:, None, :]).reshape(-1, 3).astype(np.float32)
    inside = sdf(P).reshape(len(D), n) < 0
    hit = inside.any(axis=1)
    first = np.argmax(inside, axis=1)
    lo, hi = ts[np.maximum(first - 1, 0)], ts[first]
    for _ in range(22):
        mid = 0.5 * (lo + hi)
        v = sdf((O + mid[:, None] * D).astype(np.float32))
        lo, hi = np.where(v > 0, mid, lo), np.where(v > 0, hi, mid)
    pts = O + 0.5 * (lo + hi)[:, None] * D
    return pts, normals_at(sdf, pts), hit


def normals_at(sdf, pts, eps=1e-3):
    g = np.zeros_like(pts)
    for ax in range(3):
        e = np.zeros(3)
        e[ax] = eps
        g[:, ax] = sdf((pts + e).astype(np.float32)) - sdf((pts - e).astype(np.float32))
    return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)


def bounded(sdf, lo, hi):
    """Stessa forma con un box di ingombro piu' stretto (i box delle forme ruotate sono molto larghi)."""
    return SDF(sdf.f, lo, hi)


def above(z):
    """Taglio piatto: niente sotto la quota z."""
    return SDF(lambda p: z - p[:, 2], (-20, -20, z), (20, 20, 20))


def sparkle(c, n, L, r, rot=0.0):
    """Stellina a quattro punte appoggiata alla superficie (c = centro, n = normale)."""
    n = norm(n)
    t1 = np.cross(n, (0.0, 0.0, 1.0))
    t1 = norm(t1) if np.linalg.norm(t1) > 1e-6 else np.array([1.0, 0.0, 0.0])
    t2 = np.cross(n, t1)
    a = math.radians(rot)
    t1, t2 = t1 * math.cos(a) + t2 * math.sin(a), t2 * math.cos(a) - t1 * math.sin(a)
    c = np.asarray(c, dtype=np.float64)
    arms = [round_cone(tuple(c), tuple(c + d * L), r, r * 0.18) for d in (t1, -t1, t2, -t2)]
    return union(*arms, sphere(r * 1.25, tuple(c)))


# ------------------------------------------------------------ ciuffi a fiamma (criniera e cometa)
def flame_profile(t, base=0.55, peak=0.3, tip=0.85):
    rise = base + (1.0 - base) * math.sin(min(t / peak, 1.0) * math.pi / 2)
    return rise * (1.0 - t) ** tip


def flame(root, e1, e3, L, w, thick=0.42, curl=40.0, wig=0.0, n=8, pw=1.4, base=0.55, peak=0.3, tip=0.85):
    """Ciuffo a fiamma: tubo affusolato e schiacciato che parte da root verso e1 e si arriccia di 'curl' gradi
    verso e2 = e3 x e1 (wig = guizzo a S); e3 = normale della faccia larga (spessore = thick x larghezza).
    Ritorna la forma con l'attributo .line (linea mediana in coordinate mondo)."""
    e1 = norm(e1)
    e3 = np.asarray(e3, dtype=np.float64)
    e3 = norm(e3 - e1 * (e3 @ e1))
    e2 = np.cross(e3, e1)
    pts = [np.zeros(2)]
    for i in range(n):
        t = (i + 0.5) / n
        a = math.radians(curl) * t ** pw + math.radians(wig) * math.sin(2 * math.pi * t)
        pts.append(pts[-1] + (L / n) * np.array([math.cos(a), math.sin(a)]))
    radii = [max(w * flame_profile(i / n, base, peak, tip), 0.007) for i in range(n + 1)]
    sh = flatten(tube([(float(x), float(y), 0.0) for x, y in pts], radii), thick, axis=2)
    M = np.stack([e1, e2, e3], axis=1)
    root = np.asarray(root, dtype=np.float64)
    out = sh.rotate(M.astype(np.float32)).translate(tuple(root))
    out.line = np.array([root + M @ np.array([x, y, 0.0]) for x, y in pts])
    out.e3 = e3
    return out


# ------------------------------------------------------------ rocce a facce piatte (asteroide)
def convex(normals, offsets):
    """Poliedro convesso: intersezione dei semispazi n.p <= d (facce piatte, spigoli vivi)."""
    N = np.asarray(normals, dtype=np.float64)
    N = N / np.linalg.norm(N, axis=1, keepdims=True)
    D = np.asarray(offsets, dtype=np.float64)
    verts = []
    for i, j, k in itertools.combinations(range(len(N)), 3):
        M = N[[i, j, k]]
        if abs(np.linalg.det(M)) < 1e-6:
            continue
        x = np.linalg.solve(M, D[[i, j, k]])
        if np.all(N @ x <= D + 1e-5):
            verts.append(x)
    verts = np.array(verts)
    Nf, Df = N.astype(np.float32), D.astype(np.float32)
    return SDF(lambda p: (p @ Nf.T - Df).max(axis=1), verts.min(0) - 0.01, verts.max(0) + 0.01)


BOUND = np.array([d for d in itertools.product((-1, 0, 1), repeat=3) if any(d)], dtype=np.float64)
BOUND /= np.linalg.norm(BOUND, axis=1, keepdims=True)


def fib_dirs(n, rng, jitter=0.25):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5 ** 0.5) * i + rng.uniform(0, 2 * math.pi)
    d = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], axis=1)
    d = d + rng.normal(size=d.shape) * jitter
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def chunk(c, radii, seed, n=14, depth=(0.78, 1.0), rot=(0, 0, 0), top=None):
    """Scheggia di roccia convessa a facce piatte inscritta in un ellissoide (top = taglio piatto in alto)."""
    rng = np.random.default_rng(seed)
    A = euler(*rot).astype(np.float64) @ np.diag(radii)
    dirs = fib_dirs(n, rng)
    off = np.linalg.norm(dirs @ A, axis=1) * rng.uniform(depth[0], depth[1], len(dirs))
    N = np.concatenate([dirs, BOUND])
    D = np.concatenate([off, np.linalg.norm(BOUND @ A, axis=1)]) + N @ np.asarray(c, dtype=np.float64)
    if top is not None:
        N = np.concatenate([N, [[0.0, 0.0, 1.0]]])
        D = np.concatenate([D, [top]])
    return convex(N, D)


# ============================================================ colori
NAVY = (30, 38, 108)          # blu notte profondo del corpo
NAVY_LT = (62, 74, 180)       # pannello del petto, muso e mento (stoffa piu' chiara)
SPECK = (214, 224, 255)       # puntini di stelle sul manto e nella galassia
GOLD = (255, 194, 58)         # anello della corona, artigli, filo della cucitura
STARLINE = (255, 212, 92)     # costellazioni d'oro luminose
CORE = (255, 196, 244)        # nucleo luminoso della galassia + imbottitura di polvere di stelle
MAGENTA = (236, 38, 168)
VIOLET = (112, 52, 226)
CYAN = (60, 226, 255)
MOUTH = (28, 8, 44)
TOOTH = (255, 250, 240)
TONGUE = (255, 86, 168)
EYE_GOLD = (255, 204, 60)
WHITE = (255, 255, 255)
ROCK = (104, 94, 132)
CRYSTAL = (110, 238, 255)
COMET = (255, 218, 112)       # cometa d'oro chiaro (scintille bianco-oro in gioco)
PLANET_A = (255, 128, 40)     # gigante arancione
PLANET_B = (255, 232, 176)    # pianeta crema con l'anello d'oro
PLANET_C = (36, 206, 168)     # pianetino verde acqua

m = Model("NebulaLion", "pet")
rng = np.random.default_rng(17)

RT = 1.15       # quota del pianoro dell'asteroide (dove poggiano le zampe)
LEDGE = 1.47    # sperone davanti a destra (x > 0) su cui poggia la zampa avanzata

# ============================================================ corpo: torace possente, vita stretta, groppa alta
chest = ellipsoid((0.68, 0.62, 0.7), (0, -0.6, 2.45))
barrel = ellipsoid((0.62, 0.62, 0.58), (0, -0.02, 2.5))
waist = ellipsoid((0.5, 0.4, 0.48), (0, 0.44, 2.53))
rump = ellipsoid((0.55, 0.46, 0.53), (0, 0.8, 2.54))
torso = union(chest, barrel, k=0.3)
torso = union(torso, waist, k=0.32)
torso = union(torso, rump, k=0.3)
pecs = [ellipsoid((0.31, 0.22, 0.33), (sx * 0.26, -1.08, 2.3)) for sx in (1, -1)]
shoulders = [muscle((sx * 0.4, -0.42, 3.06), (sx * 0.57, -0.8, 2.25), 0.29, 0.34) for sx in (1, -1)]
NECK = [(0.0, -0.5, 2.8), (0.0, -0.9, 3.22), (0.0, -1.22, 3.6)]
neck = tube(NECK, [0.48, 0.42, 0.34])
trunk = union(torso, *pecs, k=0.12)
trunk = union(trunk, *shoulders, k=0.1)
trunk = union(trunk, neck, k=0.2)

TOES = []  # (punta del dito, direzione in avanti, scala) per gli artigli


def paw(c, fwd=(0.0, -1.0, 0.0), s=1.0):
    """Zampa da leone: cuscinetto largo + 4 dita tozze (le punte vanno in TOES per gli artigli)."""
    c = np.asarray(c, dtype=np.float64)
    fwd = norm(fwd)
    side = norm(np.cross(fwd, (0.0, 0.0, 1.0)))
    parts = [ellipsoid((0.2 * s, 0.23 * s, 0.115 * s), tuple(c))]
    for dx in (-0.135, -0.046, 0.046, 0.135):
        back = 0.04 if abs(dx) > 0.06 else 0.0
        t = c + fwd * (0.17 - back) * s + side * dx * s + np.array([0.0, 0.0, -0.03 * s])
        parts.append(sphere(0.08 * s, tuple(t)))
        TOES.append((t + fwd * 0.055 * s, fwd, s))
    return union(*parts, k=0.04)


def front_leg(sx, sh, el, wr, pw):
    sh, el, wr, pw = (np.asarray(v, dtype=np.float64) for v in (sh, el, wr, pw))
    parts = [round_cone(tuple(sh), tuple(el), 0.32, 0.23),                                   # omero
             muscle(sh + (0, 0.16, -0.06), el + (0, 0.12, 0.06), 0.22, 0.26),                # tricipite
             round_cone(tuple(el), tuple(wr), 0.22, 0.165),                                   # avambraccio
             muscle(el + (sx * 0.03, -0.05, -0.03), lerp(el, wr, 0.62), 0.2, 0.21),          # muscoli dell'avambraccio
             round_cone(tuple(wr), tuple(pw + (0, 0.05, 0.03)), 0.165, 0.175)]               # metacarpo
    return union(union(*parts, k=0.08), paw(pw, s=1.28), k=0.06)


def hind_leg(sx):
    knee, hock, pw = (sx * 0.5, 0.48, 1.95), (sx * 0.48, 1.04, 1.55), (sx * 0.48, 0.88, RT + 0.11)
    knee, hock, pw = (np.asarray(v, dtype=np.float64) for v in (knee, hock, pw))
    parts = [muscle((sx * 0.4, 1.0, 2.76), knee + (0, 0.02, 0.04), 0.37, 0.44),            # coscia
             muscle((sx * 0.45, 0.6, 2.5), knee + (0, -0.04, 0.06), 0.25, 0.26),         # quadricipite
             round_cone(tuple(knee), tuple(hock), 0.2, 0.135),                             # tibia
             muscle(knee + (0, 0.13, -0.02), lerp(knee, hock, 0.72), 0.17, 0.19),         # polpaccio
             round_cone(tuple(hock), tuple(pw + (0, 0.06, 0.04)), 0.135, 0.15)]           # metatarso
    return union(union(*parts, k=0.08), paw(pw, s=1.2), k=0.06)


FRONT = {1: ((0.5, -0.74, 2.56), (0.57, -1.04, 2.02), (0.55, -1.42, 1.76), (0.55, -1.58, LEDGE + 0.12)),   # avanzata
         -1: ((-0.5, -0.7, 2.56), (-0.55, -0.7, 1.9), (-0.53, -0.86, 1.46), (-0.53, -1.02, RT + 0.12))}
legs = [front_leg(sx, *FRONT[sx]) for sx in (1, -1)] + [hind_leg(sx) for sx in (1, -1)]
body = fast_union(legs, k=0.1, base=trunk)
m.add("Body", body.intersect(above(RT - 0.03)), NAVY, tris=9000, voxel=0.026)

# ============================================================ testa ruggente (coordinate locali: muso verso -Y)
H_T = np.array([0.0, -1.44, 3.8])
H_S = 1.3
H_R = euler(-5, 0, 0)
JAW_Z = -0.07
HINGE = (0.0, 0.02, JAW_Z)
OPEN = 36.0


def HW(s):
    return s.scale(H_S).rotate(H_R).translate(tuple(H_T))


def J(s):
    return s.rot(OPEN, 0, 0, pivot=HINGE)


cran = ellipsoid((0.33, 0.32, 0.28), (0, 0.04, 0.1))
forehead = ellipsoid((0.28, 0.18, 0.15), (0, -0.18, 0.19))
cheeks = [ellipsoid((0.14, 0.17, 0.15), (sx * 0.24, -0.2, -0.0)) for sx in (1, -1)]
muzzle = tbox(-0.12, -0.56, 0.22, 0.18, 0.16, 0.1, JAW_Z - 0.03, JAW_Z - 0.03, 0.075)
bridge = capsule((0, -0.2, 0.23), (0, -0.5, 0.15), 0.085)
pads = [ellipsoid((0.13, 0.13, 0.115), (sx * 0.095, -0.5, -0.02)) for sx in (1, -1)]
brows = [capsule((sx * 0.035, -0.37, 0.17), (sx * 0.28, -0.27, 0.275), 0.078) for sx in (1, -1)]
upper = union(cran, forehead, k=0.12)
upper = union(upper, muzzle, k=0.1)
upper = union(upper, bridge, *cheeks, k=0.08)
upper = union(upper, *pads, k=0.05)
upper = union(upper, *brows, k=0.05)
# rughe del ringhio sul dorso del naso
upper = upper.subtract(union(*[capsule((-0.075, y, 0.24 - 0.28 * (y + 0.3)), (0.075, y, 0.24 - 0.28 * (y + 0.3)), 0.012)
                               for y in (-0.33, -0.39)]), k=0.01)
upper = upper.subtract(box((0.6, 0.5, 0.3), (0, HINGE[1] - 0.5, JAW_Z - 0.3)), k=0.012)

jaw = union(tbox(0.0, -0.5, 0.18, 0.14, JAW_Z + 0.04, JAW_Z + 0.04, -0.22, -0.19, 0.06),
            ellipsoid((0.18, 0.15, 0.11), (0, -0.06, -0.12)),
            ellipsoid((0.12, 0.09, 0.08), (0, -0.44, -0.18)), k=0.06)
jaw = jaw.subtract(box((0.6, 0.6, 0.3), (0, -0.4, JAW_Z + 0.3)), k=0.012)

# orecchie tonde (l'interno rosa e' nella parte "Tongue")
ears, ear_in = [], []
for sx in (1, -1):
    c = (sx * 0.25, 0.04, 0.33)
    R = euler(8, sx * -18, sx * -20)
    ears.append(ellipsoid((0.125, 0.06, 0.13)).rotate(R).translate(c))
    ear_in.append(ellipsoid((0.08, 0.03, 0.09)).rotate(R).translate((sx * 0.245, -0.01, 0.32)))

# occhi luminosi a mandorla (oro), pupilla a fessura, scintilla a stella, palpebra arrabbiata
eye_glow, eye_dark, eye_shine, lids = [], [], [], []
for sx in (1, -1):
    p, n = project(upper, (sx * 0.15, -0.22, 0.09), (sx * 0.55, -0.82, 0.02))
    a1 = sx * norm(np.cross((0.0, 0.0, 1.0), n))
    a2 = -sx * n
    a3 = np.cross(a1, a2)
    sl = math.radians(14)
    a1, a3 = a1 * math.cos(sl) + a3 * math.sin(sl), a3 * math.cos(sl) - a1 * math.sin(sl)
    M = np.stack([a1, a2, a3], axis=1).astype(np.float32)
    c = p - n * 0.02
    eye = ellipsoid((0.1, 0.055, 0.06)).rotate(M).translate(c)
    eye_glow.append(eye)
    eye_dark.append(ellipsoid((0.12, 0.045, 0.078)).rotate(M).translate(p - n * 0.04))       # contorno scuro
    eye_dark.append(thin(eye, 0.004, 0.02).intersect(ellipsoid((0.015, 0.2, 0.05)).rotate(M).translate(c)))
    cutp = SDF(lambda q: (0.016 + 0.45 * q[:, 0] - q[:, 2]) / math.sqrt(1 + 0.45 ** 2), (-0.16, -0.16, -0.16), (0.16, 0.16, 0.16))
    lids.append(ellipsoid((0.114, 0.066, 0.068)).intersect(cutp).rotate(M).translate(c))
    sc = c + n * 0.05 - a1 * 0.03 + a3 * 0.014
    eye_shine.append(sparkle(sc, n, 0.04, 0.01, rot=12))

# bocca: palato e mandibola scuri, parete della gola, lingua; naso scuro largo
pal_fp, jaw_fp = footprint(0.15, 0.24, -0.31), footprint(0.13, 0.22, -0.3)
pal_reg = SDF(lambda p: np.maximum(pal_fp(p), p[:, 2] - (JAW_Z + 0.03)), (-0.16, -0.56, JAW_Z - 0.05), (0.16, -0.06, JAW_Z + 0.03))
jaw_reg = SDF(lambda p: np.maximum(jaw_fp(p), (JAW_Z - 0.03) - p[:, 2]), (-0.14, -0.53, JAW_Z - 0.03), (0.14, -0.07, JAW_Z + 0.05))
mouth_dark = [shell_paint(upper, pal_reg, out=0.006, inn=0.03, margin=0.02),
              J(shell_paint(jaw, jaw_reg, out=0.006, inn=0.03, margin=0.02))]
_Rinv = euler(-OPEN, 0, 0)
_piv = np.asarray(HINGE, dtype=np.float32)
_thr = footprint(0.16, 0.12, -0.12)


def _wedge(p):
    q = (p - _piv) @ _Rinv.T + _piv
    return np.maximum(np.maximum(p[:, 2] - (JAW_Z + 0.004), (JAW_Z - 0.004) - q[:, 2]), _thr(p))


mouth_dark.append(SDF(_wedge, (-0.17, -0.25, JAW_Z - 0.3), (0.17, 0.04, JAW_Z + 0.01)))
nose = union(ellipsoid((0.11, 0.06, 0.055), (0, -0.565, 0.135)), ellipsoid((0.045, 0.045, 0.05), (0, -0.585, 0.08)), k=0.045)
mouth_dark.append(nose)
tongue = J(union(ellipsoid((0.11, 0.21, 0.042), (0, -0.28, JAW_Z - 0.035)),
                 ellipsoid((0.09, 0.06, 0.036), (0, -0.46, JAW_Z + 0.0)).rot(-25, 0, 0, pivot=(0, -0.43, JAW_Z)), k=0.04))

# zanne: canini lunghi sopra e sotto, incisivi e denti laterali
teeth = []
for sx in (1, -1):
    p, n = project(upper, (sx * 0.02, -0.45, JAW_Z + 0.012), (sx, -0.25, 0))
    b = p - norm((n[0], n[1], 0.0)) * 0.032
    teeth.append(horn((b[0], b[1], JAW_Z + 0.03), (b[0], b[1], JAW_Z - 0.06), (b[0], b[1] + 0.01, JAW_Z - 0.14),
                      (b[0] - sx * 0.006, b[1] + 0.03, JAW_Z - 0.2), 0.042, 0.005, n=8))
    for y, L in ((-0.36, 0.055), (-0.27, 0.06), (-0.18, 0.045)):
        p, n = project(upper, (0, y, JAW_Z + 0.012), (sx, 0, 0))
        b = p - norm((n[0], n[1], 0.0)) * 0.028
        teeth.append(round_cone((b[0], b[1], JAW_Z + 0.02), (b[0], b[1], JAW_Z - L), 0.024, 0.004))
    for x in (0.03, 0.08):
        p, n = project(upper, (sx * x, -0.38, JAW_Z + 0.012), (0, -1, 0))
        b = p + np.array([0.0, 0.028, 0.0])
        teeth.append(round_cone((b[0], b[1], JAW_Z + 0.02), (b[0], b[1], JAW_Z - 0.045), 0.019, 0.004))
    # canino inferiore e denti della mandibola (costruiti a bocca chiusa, poi ruotati)
    p, n = project(jaw, (sx * 0.02, -0.4, JAW_Z - 0.012), (sx, -0.3, 0))
    b = p - norm((n[0], n[1], 0.0)) * 0.032
    teeth.append(J(horn((b[0], b[1], JAW_Z - 0.03), (b[0], b[1], JAW_Z + 0.04), (b[0], b[1] + 0.008, JAW_Z + 0.09),
                        (b[0] - sx * 0.006, b[1] + 0.02, JAW_Z + 0.14), 0.036, 0.005, n=7)))
    for y in (-0.29, -0.19):
        p, n = project(jaw, (0, y, JAW_Z - 0.012), (sx, 0, 0))
        b = p - norm((n[0], n[1], 0.0)) * 0.026
        teeth.append(J(round_cone((b[0], b[1], JAW_Z - 0.02), (b[0], b[1], JAW_Z + 0.045), 0.021, 0.004)))

head_skin = union(upper, J(jaw), *lids, k=0.012)
head_skin = union(head_skin, *ears, k=0.05)
# pannello chiaro del muso (cuscinetti dei baffi) e del mento
muz_reg = union(*[ellipsoid((0.16, 0.17, 0.15), (sx * 0.095, -0.54, -0.03)) for sx in (1, -1)])
head_paint = [shell_paint(upper, muz_reg, out=0.012, inn=0.04),
              J(shell_paint(jaw, ellipsoid((0.17, 0.22, 0.14), (0, -0.4, -0.16)), out=0.012, inn=0.04))]
# la parte "Head" contiene anche l'ultimo tratto del collo (niente gradino fra le due parti)
m.add("Head", union(HW(head_skin), tube([NECK[1], NECK[2], (0.0, -1.38, 3.74)], [0.42, 0.34, 0.3]), k=0.08), NAVY,
      role="skin", tris=6000, voxel=0.014)

# ============================================================ criniera a galassia a spirale
G = np.array([0.0, -1.18, 3.86])   # centro della galassia: dietro al muso
BK = np.array([0.0, 1.0, 0.0])     # verso il fondo
MS = 1.16                          # scala della criniera
VS = 0.86                          # disco un po' schiacciato in verticale (galassia vista di scorcio)
TOP_TILT = 10.0                    # inclinazione all'indietro in piu' per i ciuffi della meta' alta


def rdir(th):
    return np.array([math.cos(th), 0.0, math.sin(th)])


def tdir(th):  # senso antiorario visto da davanti
    return np.array([-math.sin(th), 0.0, math.cos(th)])


def ell(th):
    return math.sqrt(math.cos(th) ** 2 + (VS * math.sin(th)) ** 2)


def reach(th):
    """Ciuffi piu' corti in basso (sotto il mento) per lasciare vedere il petto."""
    return ell(th) * (1.0 - 0.34 * max(0.0, -math.sin(th)) ** 1.4)


def tuft(r0, th, b, L, w, alpha, tilt, curl, top_tilt=True, **kw):
    """Ciuffo della galassia: radice a raggio r0 / angolo th (profondita' b), inclinato di alpha verso il senso
    antiorario e di tilt all'indietro (la criniera e' una coppa poco profonda aperta verso chi guarda)."""
    root = G + MS * r0 * ell(th) * rdir(th) + b * BK
    a = math.radians(alpha)
    d = math.cos(a) * rdir(th) + math.sin(a) * tdir(th)
    t = math.radians(tilt + (TOP_TILT * max(0.0, math.sin(th)) ** 1.5 if top_tilt else 0.0))   # in alto piu' all'indietro
    return flame(root, math.cos(t) * d + math.sin(t) * BK, -BK, MS * L * reach(th), MS * w, **kw)


core, inner, outer, neb = [], [], [], []
for i in range(24):                       # nucleo luminoso attorno al muso
    th = 2 * math.pi * i / 24 + rng.uniform(-0.05, 0.05)
    core.append(tuft(0.34, th, -0.16, 0.4 * rng.uniform(0.9, 1.1), 0.13, 28, 10, 45, thick=0.5, base=0.8))
for i in range(22):                       # magenta
    th = 2 * math.pi * (i + 0.5) / 22 + rng.uniform(-0.05, 0.05)
    inner.append(tuft(0.5, th, -0.07, 0.86 * rng.uniform(0.9, 1.1), 0.21, 30, 16, 52, thick=0.5, base=0.8))
for j, (r0, b, L, w, n_t) in enumerate(((0.74, 0.03, 0.96, 0.22, 20), (0.82, 0.1, 1.0, 0.2, 16))):   # viola (due giri)
    for i in range(n_t):
        th = 2 * math.pi * (i + 0.5 * j) / n_t + 0.12 + rng.uniform(-0.05, 0.05)
        outer.append(tuft(r0, th, b, L * rng.uniform(0.9, 1.1), w, 40 + 4 * j, 24 + 4 * j, 70, thick=0.46, base=0.8))
for i in range(9):                        # punte ciano fra i bracci
    th = 2 * math.pi * (i + 0.3) / 9
    neb.append(tuft(0.9, th, 0.16, 0.5 * rng.uniform(0.9, 1.1), 0.13, 50, 28, 55, base=0.8))
ARMS = [(-32.0, 1.0), (88.0, 0.92), (208.0, 0.86)]
for a0, f in ARMS:                        # grandi bracci a spirale
    arm = tuft(0.84, math.radians(a0), 0.16, 2.05 * f, 0.33, 62, 18, 100, n=18, thick=0.42, base=0.85, peak=0.22,
               top_tilt=False)
    neb.append(arm)
    for u, L in ((0.26, 0.5), (0.46, 0.44), (0.64, 0.36), (0.8, 0.26)):
        i0 = int(u * (len(arm.line) - 1))
        tng = norm(arm.line[i0 + 1] - arm.line[i0])
        out_dir = norm(np.cross(tng, arm.e3))  # lato convesso del braccio (verso l'esterno)
        neb.append(flame(arm.line[i0], norm(tng + out_dir * 0.75), arm.e3, L * f * MS, 0.12 * MS, curl=38, n=7, base=0.8))
# criniera dietro al disco: anelli di ciuffi attorno a nuca e collo che scendono all'indietro fino alle spalle
# (danno volume alla criniera nelle viste di 3/4 e di lato)
WITHERS = np.array([0.0, -0.42, 3.02])
NAX = norm(WITHERS - G)                      # asse del collo, dalla testa verso il garrese
NU = np.array([1.0, 0.0, 0.0])
NV = np.cross(NU, NAX)                       # "su" attorno al collo
for k, (s_ax, R, L, w, n_t, a_lo, a_hi) in enumerate(((0.1, 0.62, 0.92, 0.28, 14, -18, 198), (0.32, 0.58, 0.88, 0.27, 13, -12, 192),
                                                       (0.54, 0.52, 0.8, 0.25, 12, -8, 188), (0.76, 0.44, 0.68, 0.22, 10, 0, 180))):
    C = G + NAX * s_ax * float(np.linalg.norm(WITHERS - G))
    for i in range(n_t):
        th = math.radians(a_lo + (a_hi - a_lo) * (i + 0.5 * (k % 2)) / (n_t - 1 + 0.5 * (k % 2)))
        rad = math.cos(th) * NU + math.sin(th) * NV
        root = C + rad * MS * R * 0.62
        e1 = norm(rad * 0.6 + NAX * 1.0 + np.cross(NAX, rad) * 0.25)
        sh = flame(root, e1, rad, MS * L * rng.uniform(0.9, 1.1), MS * w, curl=28, thick=0.5, base=0.85)
        (inner if (i + k) % 3 == 0 else outer).append(sh)
        if k == 3 and i % 2 == 0:   # qualche punta ciano anche dietro
            tip = sh.line[-3]
            neb.append(flame(tip, norm(e1 + rad * 0.3), rad, MS * 0.36, MS * 0.1, curl=30, n=6, base=0.8))

# cupola di ciuffi dietro la testa: di lato la criniera diventa una massa tonda, non una cresta
DOME_C = G + BK * 0.3 + np.array([0.0, 0.0, 0.08])
dome_dirs = [d for d in fib_dirs(70, np.random.default_rng(5), jitter=0.08) if d @ BK > 0.2 and d[2] > -0.15]
for i, d in enumerate(dome_dirs):
    root = DOME_C + d * MS * 0.42
    e1 = norm(d + BK * 0.7 + np.array([0.0, 0.0, -0.15]))
    (outer if i % 3 else inner).append(flame(root, e1, d, MS * 0.82 * rng.uniform(0.9, 1.1), MS * 0.27, curl=25, thick=0.5,
                                             base=0.85))

# stelline a quattro punte sospese attorno alla galassia, fra un braccio e l'altro (parte "Nebula")
for a_, rr, L in ((32.0, 1.95, 0.17), (150.0, 2.0, 0.15), (255.0, 1.75, 0.13), (-62.0, 1.85, 0.14), (118.0, 1.55, 0.11),
                  (190.0, 1.62, 0.12)):
    th = math.radians(a_)
    c = G + MS * rr * ell(th) * rdir(th) + BK * 0.05
    neb.append(sparkle(c, -BK, L * MS, 0.036, rot=a_ * 0.5))
m.add("ManeInner", fast_union(inner, k=0.02), MAGENTA, role="detail", tris=5800, voxel=0.018)
m.add("ManeOuter", fast_union(outer, k=0.02), VIOLET, role="detail", tris=6600, voxel=0.019)
m.add("Nebula", fast_union(neb), CYAN, material="Neon", role="glow", tris=5200, voxel=0.018)

# ============================================================ facce: occhi, bocca, denti
m.add("EyeGlow", HW(union(*eye_glow)), EYE_GOLD, material="Neon", role="glow", tris=500, voxel=0.009)
m.add("Mouth", HW(fast_union(mouth_dark + eye_dark)), MOUTH, role="eye", tris=1400, voxel=0.01)
m.add("Teeth", HW(fast_union(teeth)), TOOTH, role="shine", tris=1300, voxel=0.008)
m.add("Tongue", HW(union(tongue, *ear_in)), TONGUE, role="detail", tris=600, voxel=0.012)
m.add("Shine", HW(union(*eye_shine)), WHITE, role="shine", tris=240, voxel=0.006)

# ============================================================ pancia chiara, cucitura scucita sul petto, polvere di stelle
belly_reg = ellipsoid((0.36, 0.9, 0.3), (0, -0.3, 1.9))                 # pancia
m.add("Belly", union(shell_paint(trunk, belly_reg, out=0.018, inn=0.05), HW(union(*head_paint))), NAVY_LT, role="detail",
      tris=2200, voxel=0.018)

SEAM = [project(trunk, (0, -0.7, z), (0, -1, 0)) for z in np.linspace(2.72, 1.98, 16)]
SPLIT = (2.2, 2.48)   # tratto scucito (quote)
gold, stuffing, starlines = [], [], []
seam_line = resample([p for p, _ in SEAM], 0.08)
for i, p in enumerate(seam_line):
    t = norm(seam_line[min(i + 1, len(seam_line) - 1)] - seam_line[max(i - 1, 0)])
    nrm = grad(trunk, p)
    side = norm(np.cross(t, nrm))
    split = SPLIT[0] <= p[2] <= SPLIT[1]
    w, h = (0.085, 0.03) if split else (0.055, 0.032)
    diag = [(-1, 1), (1, 1)] if not split or i % 2 == 0 else [(-1, 1)]
    for a, b_ in diag:
        q0 = on_surface(trunk, p + side * w * a + t * h, 0.006, 3)
        q1 = on_surface(trunk, p - side * w * a - t * h * b_, 0.006, 3)
        gold.append(capsule(tuple(q0), tuple(q1), 0.0135))
    if split:   # imbottitura di polvere di stelle che esce dalla cucitura
        stuffing.append(sphere(rng.uniform(0.05, 0.075), tuple(p + nrm * 0.03 + side * rng.uniform(-0.02, 0.02))))
for z, dx, s in ((2.08, 0.06, 0.9), (1.98, -0.05, 0.75)):   # granelli di stelle che cadono
    p, n = project(trunk, (0, -0.7, z), (dx, -1, 0))
    starlines.append(sparkle(p + n * 0.012, n, 0.06 * s, 0.014 * s, rot=20))

# ============================================================ costellazione del Leone sui fianchi e sulle spalle
LEO = {"eps": (0.0, 0.9), "mu": (0.2, 1.04), "zeta": (0.44, 0.96), "gam": (0.5, 0.66), "eta": (0.37, 0.4),
       "reg": (0.45, 0.1), "del": (1.34, 0.74), "the": (1.36, 0.3), "bet": (1.86, 0.52)}
LEO_LINES = [("eps", "mu"), ("mu", "zeta"), ("zeta", "gam"), ("gam", "eta"), ("eta", "reg"), ("gam", "del"),
             ("del", "bet"), ("bet", "the"), ("the", "reg"), ("del", "the")]
BRIGHT = {"reg": 1.45, "bet": 1.3, "gam": 1.2}
leo_pts = []


def leo_yz(u, v):
    return -1.02 + u * 0.98, 2.02 + v * 0.82


for sx in (1, -1):
    pos = {}
    for k, (u, v) in LEO.items():
        y, z = leo_yz(u, v)
        pos[k] = project(body, (0, y, z), (sx, 0, 0.1), max_dist=2.0)
    for a, b_ in LEO_LINES:
        (ya, za), (yb, zb) = leo_yz(*LEO[a]), leo_yz(*LEO[b_])
        nseg = max(int(math.hypot(yb - ya, zb - za) / 0.035), 2)
        pts = []
        for t in np.linspace(0, 1, nseg + 1):
            p, n = project(body, (0, ya + (yb - ya) * t, za + (zb - za) * t), (sx, 0, 0.1), max_dist=2.0)
            pts.append(tuple(p + n * 0.004))
        leo_pts += pts
        starlines.append(tube(pts, 0.016))
    for k, (p, n) in pos.items():
        s = BRIGHT.get(k, 1.0)
        starlines.append(sphere(0.036 * s, tuple(p + n * 0.008)))
        if k in BRIGHT:
            starlines.append(sparkle(p + n * 0.012, n, 0.1 * s, 0.02, rot=10))
leo_pts = np.array(leo_pts)

# ============================================================ coda con il ciuffo a cometa (gruppo "Tail")
TAIL = catmull([(0.03, 0.98, 2.64), (0.12, 1.4, 2.44), (0.45, 1.9, 2.02), (0.98, 2.16, 1.98),
                (1.42, 2.02, 2.4), (1.6, 1.72, 2.92)], 5)
NT = len(TAIL) - 1
TAIL_PIVOT = (0.04, 1.1, 2.58)
tail = tube(TAIL, [0.19 - 0.075 * (i / NT) for i in range(NT + 1)])
TT = np.array(TAIL[-1])
TD = norm(np.array(TAIL[-1]) - np.array(TAIL[-3]))
s1 = norm(np.cross(TD, (0.0, 0.0, 1.0)))
s2 = np.cross(TD, s1)
NUC = TT + TD * 0.12
comet = [sphere(0.23, tuple(NUC))]
PL = norm((0.3, 1.0, -0.12))                 # direzione della scia (all'indietro, come spinta dal vento solare)
PU = norm(np.cross(PL, np.cross((0.0, 0.0, 1.0), PL)))   # "su" perpendicolare alla scia
PS = np.cross(PL, PU)
for i, (up, sd, L, w) in enumerate(((0.0, 0.0, 1.35, 0.26), (0.42, 0.1, 1.05, 0.21), (-0.38, -0.1, 1.1, 0.21),
                                    (0.2, -0.38, 0.9, 0.18), (-0.15, 0.4, 0.95, 0.18), (0.7, -0.2, 0.7, 0.15),
                                    (-0.65, 0.25, 0.75, 0.15))):
    d = norm(PL + PU * up + PS * sd)
    comet.append(flame(NUC + d * 0.08, d, PS if abs(sd) < 0.3 else PU, L, w, curl=12 * (1 if up >= 0 else -1),
                       thick=0.5, base=0.9, peak=0.18))
for i in range(7):            # chioma: fiammelle corte attorno al nucleo
    a_ = 2 * math.pi * i / 7 + 0.4
    rad = math.cos(a_) * s1 + math.sin(a_) * s2
    d = norm(rad + TD * 0.45 - PL * 0.3)
    comet.append(flame(NUC + d * 0.1, d, np.cross(d, s1) + 0.01, 0.34, 0.12, curl=30, n=6, base=0.85))
m.add("Tail", tail, NAVY, role="skin", tris=1500, voxel=0.02, group="Tail", pivot=TAIL_PIVOT)
m.add("Stars", fast_union(comet), COMET, material="Neon", role="glow", tris=2000, voxel=0.016, group="Tail", pivot=TAIL_PIVOT)

# ============================================================ corona: anello d'oro inclinato con tre pianetini
CROWN_C = np.array([0.0, -1.56, 4.82])
CROWN_R = 0.52
CROWN_M = euler(24, 10, 0)
gold.append(torus(CROWN_R, 0.04).rotate(CROWN_M).translate(tuple(CROWN_C)))


def ring_pt(a):
    a = math.radians(a)
    return CROWN_C + CROWN_M.astype(np.float64) @ np.array([CROWN_R * math.cos(a), CROWN_R * math.sin(a), 0.0])


PA, PB, PC = ring_pt(205), ring_pt(325), ring_pt(85)
gold.append(torus(0.22, 0.017).rot(28, -24, 0).translate(tuple(PB)))     # anello di Saturno
m.add("PlanetA", sphere(0.16, tuple(PA)), PLANET_A, role="detail", tris=360, voxel=0.012)
m.add("PlanetB", sphere(0.12, tuple(PB)), PLANET_B, role="detail", tris=300, voxel=0.012)
m.add("PlanetC", sphere(0.105, tuple(PC)), PLANET_C, role="detail", tris=260, voxel=0.012)

# ============================================================ artigli d'oro
for tip, fwd, s in TOES:
    t0 = np.asarray(tip, dtype=np.float64)
    gold.append(horn(tuple(t0 + (0, 0, 0.015 * s)), tuple(t0 + fwd * 0.07 * s + (0, 0, 0.03 * s)), tuple(t0 + fwd * 0.13 * s),
                     tuple(t0 + fwd * 0.155 * s + (0, 0, -0.05 * s)), 0.036 * s, 0.006, n=7))
m.add("Gold", fast_union(gold), GOLD, role="detail", tris=2600, voxel=0.01, reflectance=0.12)
m.add("StarLines", fast_union(starlines), STARLINE, material="Neon", role="glow", tris=2600, voxel=0.009)
# nucleo luminoso della galassia + imbottitura di polvere di stelle che esce dalla cucitura del petto
m.add("GalaxyCore", union(fast_union(core), fast_union(stuffing, k=0.03)), CORE, material="Neon", role="glow", tris=3400,
      voxel=0.016)

# ============================================================ puntini di stelle sul manto e nella galassia
specks = []
cand = []
for c in ((0, -0.6, 2.45), (0, 0.0, 2.5), (0, 0.8, 2.55), (0.3, -0.85, 1.95), (-0.3, -0.8, 1.85), (0.4, 0.7, 2.0), (-0.4, 0.7, 2.0)):
    dirs = rng.normal(size=(140, 3))
    pts, nrms = project_many(body, c, dirs)
    cand += list(zip(pts, nrms))
rng.shuffle(cand)
taken = []
for p, n in cand:
    if p[2] < RT + 0.3 or belly_reg(p[None, :].astype(np.float32))[0] < 0.05:
        continue
    if abs(p[0]) < 0.2 and p[1] < -0.9:
        continue
    if len(leo_pts) and np.min(np.linalg.norm(leo_pts - p, axis=1)) < 0.08:
        continue
    if any(np.linalg.norm(p - q) < 0.13 for q in taken):
        continue
    taken.append(p)
    specks.append(sphere(rng.uniform(0.018, 0.026), tuple(p + n * 0.004)))
    if len(taken) >= 70:
        break
mane_front = union(fast_union(inner), fast_union(outer))
xs = rng.uniform(-1.75, 1.75, 300)
zs = G[2] + rng.uniform(-1.3, 1.5, 300)
hp, hn, hit = ray_hits(mane_front, np.stack([xs, np.full_like(xs, G[1] - 1.6), zs], axis=1), (0, 1, 0), max_dist=2.6)
taken = []
for p, n, h in zip(hp, hn, hit):
    if not h or math.hypot(p[0] - H_T[0], p[2] - H_T[2]) < 0.62:
        continue
    if any(np.linalg.norm(p - q) < 0.15 for q in taken):
        continue
    taken.append(p)
    specks.append(sphere(rng.uniform(0.02, 0.028), tuple(p + n * 0.006)))
    if len(taken) >= 30:
        break
m.add("Specks", fast_union(specks), SPECK, role="detail", tris=1200, voxel=0.011)

# ============================================================ frammento di asteroide sospeso (base del modello)


def asteroid():
    r = np.random.default_rng(31)
    cx, cy, ax, ay, zr = 0.0, 0.1, 1.18, 1.56, 0.84
    apex = np.array([0.06, 0.2, 0.0])
    N, D = [], []

    def plane(n, pt):
        n = norm(n)
        N.append(n)
        D.append(float(n @ np.asarray(pt, dtype=np.float64)))

    def enorm(az):
        return norm((math.cos(az) / ax, math.sin(az) / ay, 0.0))

    def epoint(az, f=1.0, z=0.0):
        return np.array([cx + ax * f * math.cos(az), cy + ay * f * math.sin(az), z])

    up = np.array([0.0, 0.0, 1.0])
    plane(up, (0, 0, RT))
    for k in range(11):   # smussi del bordo superiore
        az = 2 * math.pi * k / 11 + r.uniform(-0.15, 0.15)
        tl = math.radians(r.uniform(30, 44))
        plane(enorm(az) * math.sin(tl) + up * math.cos(tl), epoint(az, r.uniform(0.86, 0.92), RT))
    for k in range(12):   # fianchi
        az = 2 * math.pi * (k + 0.5) / 12 + r.uniform(-0.12, 0.12)
        el = math.radians(r.uniform(-4, 16))
        plane(enorm(az) * math.cos(el) + up * math.sin(el), epoint(az, r.uniform(0.97, 1.03), zr))
    for k in range(10):   # fondo a punta: piani che passano per l'apice
        az = 2 * math.pi * k / 10 + r.uniform(-0.18, 0.18)
        rim = epoint(az, r.uniform(0.86, 1.0), zr - r.uniform(0.0, 0.12))
        tang = np.array([-ay * math.sin(az), ax * math.cos(az), 0.0])
        n = norm(np.cross(tang, rim - apex))
        if n @ enorm(az) < 0:
            n = -n
        plane(n, apex)
    return convex(N, D)


def spike_down(top, tip, w, seed, sides=5):
    """Punta di roccia rivolta in basso (stalattite dell'asteroide): base larga w attorno a top, apice in tip."""
    r = np.random.default_rng(seed)
    top, tip = np.asarray(top, dtype=np.float64), np.asarray(tip, dtype=np.float64)
    a = norm(tip - top)
    u = norm(np.cross(a, (0.3, 0.2, 1.0)))
    v = np.cross(a, u)
    N, D = [a * -1.0], [float(-a @ top) + 0.0]
    L = float(np.linalg.norm(tip - top))
    for k in range(sides):
        ang = 2 * math.pi * k / sides + r.uniform(-0.3, 0.3)
        side = math.cos(ang) * u + math.sin(ang) * v
        half = math.atan2(w * r.uniform(0.8, 1.15), L)
        n = norm(side * math.cos(half) + a * math.sin(half))
        N.append(n)
        D.append(float(n @ tip))
    return convex(N, D)


rock = [asteroid(),
        chunk((0.5, -1.4, 1.2), (0.33, 0.31, 0.3), seed=3, top=LEDGE),            # sperone della zampa avanzata
        chunk((-1.04, 0.66, 0.96), (0.36, 0.34, 0.3), seed=4),
        chunk((1.08, 0.82, 0.88), (0.32, 0.36, 0.32), seed=5),
        chunk((-0.76, -1.3, 0.92), (0.32, 0.28, 0.28), seed=6),
        spike_down((-0.5, -0.42, 0.62), (-0.36, -0.3, 0.16), 0.24, seed=7),        # punte sotto l'asteroide
        spike_down((0.58, 0.66, 0.66), (0.42, 0.58, 0.24), 0.22, seed=8),
        spike_down((0.62, -0.62, 0.7), (0.4, -0.42, 0.34), 0.2, seed=9),
        spike_down((-0.56, 0.9, 0.7), (-0.36, 0.7, 0.3), 0.2, seed=10)]
# fascia di asteroidi in orbita: sassi su un'ellisse inclinata attorno alla punta dell'asteroide
BELT_C, BELT_M = np.array([0.05, 0.16, 0.56]), euler(6, -5, 0).astype(np.float64)
belt_rng = np.random.default_rng(21)
for i in range(7):
    a_ = 2 * math.pi * (i + 0.35) / 7 + belt_rng.uniform(-0.15, 0.15)
    c = BELT_C + BELT_M @ np.array([1.5 * math.cos(a_), 1.8 * math.sin(a_), belt_rng.uniform(-0.06, 0.06)])
    sz = belt_rng.uniform(0.12, 0.19)
    rock.append(chunk(c, (sz, sz * 0.82, sz * 0.7), seed=40 + i, rot=tuple(belt_rng.uniform(-40, 40, 3))))
m.add("Rock", fast_union(rock).intersect(above(0.0)), ROCK, material="Slate", role="detail", tris=4200, voxel=0.026,
      smooth=False)

crystals = []
for base, d, L, r in (((-1.0, -1.0, 1.0), (-0.55, -0.5, 0.65), 0.78, 0.15), ((-0.92, -1.12, 0.92), (-0.75, -0.3, 0.38), 0.5, 0.1),
                      ((-1.06, -0.86, 0.94), (-0.4, -0.85, 0.45), 0.42, 0.09), ((1.12, 0.58, 1.0), (0.7, 0.2, 0.6), 0.68, 0.14),
                      ((1.08, 0.8, 0.94), (0.6, 0.55, 0.32), 0.44, 0.1),
                      ((0.98, -0.92, 0.98), (0.7, -0.55, 0.45), 0.5, 0.11), ((0.86, -1.08, 0.9), (0.35, -0.85, 0.3), 0.34, 0.08),
                      ((-0.3, -1.42, 0.86), (-0.15, -0.9, 0.35), 0.38, 0.09),
                      ((0.26, -0.38, 0.32), (0.25, -0.55, -0.8), 0.34, 0.09), ((0.36, -0.3, 0.36), (0.75, -0.2, -0.6), 0.26, 0.07),
                      ((-0.42, 0.42, 0.42), (-0.6, 0.35, -0.7), 0.3, 0.08),
                      ((-0.3, 1.3, 1.12), (-0.2, 0.6, 0.8), 0.38, 0.085), ((-0.12, 1.42, 1.1), (0.25, 0.5, 0.7), 0.26, 0.065)):
    d = norm(d)
    crystals.append(crystal(L, r, tip=0.36, sides=6).rotate(frame_from_z(d)).translate(tuple(np.asarray(base) - d * 0.12)))
m.add("Crystals", fast_union(crystals).intersect(above(0.02)), CRYSTAL, material="Neon", role="glow", tris=1100, voxel=0.016,
      smooth=False)

# ============================================================ scala globale: altezza ~4 unita' (il gioco la riscala)
SCALE = 0.76
for part in m.parts:
    part.sdf = part.sdf.scale(SCALE)
    part.voxel = part.voxel * SCALE if part.voxel else None
    if part.pivot is not None:
        part.pivot = tuple(float(c * SCALE) for c in part.pivot)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
