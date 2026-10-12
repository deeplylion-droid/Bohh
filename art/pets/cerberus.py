"""Cerbero (Cerberus) - pet PRIMORDIALE, il grado fra Segreto e Ultra (zona: Cratere Vulcanico).

Il cane infernale a tre teste che fa la guardia al cratere. Corpo nero, compatto e muscoloso come
un molosso, piantato a terra in posa d'attacco: spalle alte e curve, petto enorme, zampe anteriori
larghe con artigli color osso, coda alzata e arricciata sopra la groppa con la punta che brucia.
Tre teste ringhianti girate in direzioni diverse: quella centrale (la capobranco, con due corna
rosso sangue) ringhia a muso basso verso chi guarda, quella alla sua sinistra ulula al cielo con la
gola piena di fuoco, quella alla sua destra digrigna i denti con la testa inclinata. Ogni testa ha
zanne lunghe, file di denti aguzzi, orecchie a punta e occhi gialli incandescenti con la pupilla a
fessura sotto sopracciglia aggrottate. Su teste e colli brucia una criniera di fiamme (parte Neon
"Flames": il gioco ci attacca il fuoco); crepe di lava incandescente su spalle, fianchi e cosce,
spuntoni rosso sangue lungo la schiena e la coda, tre collari di ferro chiodati.
Tocco "toy horror": dal collare di sinistra pende una catena spezzata e il petto e' ricucito con una
cucitura a punti incrociati da cui filtra la lava.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, box, capsule, ellipsoid, euler, halfspace_z, project, round_cone,  # noqa: E402
                     smin, sphere, tube, union)
from lib.toy import Model  # noqa: E402

DRAFT = os.environ.get("DRAFT", "") == "1"
VX = 1.3 if DRAFT else 1.0  # bozza: voxel piu' grossi per iterare in fretta
rng = np.random.default_rng(13)


# ============================================================ helper (lib/ non si modifica: copiati/adattati qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


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


def project_many(sdf, origins, dirs, max_dist=2.0, steps=260, iters=24):
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
        print(f"[cerberus] attenzione: {len(bad)} raggi partono fuori dalla forma, es. {np.round(o[bad[0]], 3)}")
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


def along(dense, rad, ts, hint):
    """Punti di una curva a frazioni di lunghezza ts: (centro, tangente, lato 'hint', raggio)."""
    seg = np.linalg.norm(np.diff(dense, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for t in ts:
        sd = t * cum[-1]
        i = int(min(np.searchsorted(cum, sd, side="right") - 1, len(seg) - 1))
        w = (sd - cum[i]) / max(seg[i], 1e-9)
        c = dense[i] * (1 - w) + dense[i + 1] * w
        tan = norm(dense[i + 1] - dense[i])
        hv = np.asarray(hint, dtype=np.float64)
        f = norm(hv - tan * np.dot(hv, tan))
        out.append((c, tan, f, rad((i + w) / (len(dense) - 1))))
    return out, cum[-1]


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
    """Lingua di fuoco (locale: base nell'origine, sale lungo +Z e si piega verso +Y, piatta lungo X).

    Profilo a goccia (piu' larga poco sopra la base); fork > 0 aggiunge una lingua secondaria all'indietro.
    """
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


# ============================================================ colori
BLACK = (30, 26, 33)        # nero (appena violaceo: il nero puro in gioco e' piatto)
BLOOD = (132, 16, 26)       # rosso sangue: corna, orecchie, spuntoni
LAVA = (255, 76, 14)        # crepe di lava (Neon)
FIRE = (255, 126, 22)       # criniere di fuoco (Neon)
EYE_GLOW = (255, 214, 60)
PUPIL = (22, 4, 6)
MOUTH = (46, 8, 14)
TOOTH = (246, 238, 220)
TONGUE = (196, 50, 64)
IRON = (150, 146, 156)
IRON_DK = (124, 120, 130)
THREAD = (236, 220, 184)

m = Model("Cerberus", "pet")

# ============================================================ tronco da molosso
chest = ellipsoid((0.6, 0.55, 0.64), (0, -0.44, 1.22))
withers = ellipsoid((0.62, 0.44, 0.42), (0, -0.3, 1.62))
ribs = ellipsoid((0.5, 0.48, 0.45), (0, 0.06, 1.3))
waist = ellipsoid((0.36, 0.3, 0.3), (0, 0.42, 1.42))
croup = ellipsoid((0.45, 0.38, 0.4), (0, 0.72, 1.42))
trunk = union(chest, withers, ribs, k=0.3)
trunk = union(trunk, waist, croup, k=0.26)
pecs = [ellipsoid((0.3, 0.22, 0.32), (sx * 0.26, -0.86, 1.16)) for sx in (1, -1)]
delts = [ellipsoid((0.28, 0.38, 0.42), (sx * 0.5, -0.45, 1.34)) for sx in (1, -1)]
hump = ellipsoid((0.5, 0.38, 0.28), (0, -0.38, 1.86))
trunk = union(trunk, *pecs, *delts, hump, k=0.14)

TOES = []  # (punta del dito, direzione in avanti, scala) per gli artigli


def paw(c, fwd, s=1.0):
    fwd = norm((fwd[0], fwd[1], 0.0))
    side = np.array([-fwd[1], fwd[0], 0.0])
    c = np.asarray(c, float)
    pad = ellipsoid((0.21 * s, 0.23 * s, 0.12 * s)).rotate(frame((0, 0, 1), fwd)).translate(c)
    toes = []
    for dx in (-0.135, -0.047, 0.047, 0.135):
        a = c + side * dx * s + np.array([0, 0, 0.02])
        tip = c + side * dx * 1.35 * s + fwd * (0.22 - abs(dx) * 0.45) * s
        tip[2] = 0.078 * s
        toes.append(capsule(tuple(a), tuple(tip), 0.078 * s))
        TOES.append((tip, norm(fwd + side * dx * 2.0), s))
    return union(pad, *toes, k=0.05)


def front_leg(sx):
    sh, el, wr, pw = (np.array(v, float) for v in ((sx * 0.52, -0.5, 1.2), (sx * 0.64, -0.52, 0.74),
                                                     (sx * 0.64, -0.76, 0.28), (sx * 0.66, -0.9, 0.12)))
    parts = [round_cone(sh, el, 0.29, 0.2),
             ellipsoid((0.22, 0.26, 0.32), tuple((sh + el) / 2 + (sx * 0.06, -0.06, 0.02))),     # bicipite
             round_cone(el, wr, 0.2, 0.14),
             ellipsoid((0.17, 0.19, 0.24), tuple(el * 0.68 + wr * 0.32 + (sx * 0.02, -0.04, 0))),  # avambraccio
             round_cone(wr, pw + (0, 0.04, 0.05), 0.14, 0.15)]
    return union(union(*parts, k=0.08), paw(pw, (sx * 0.15, -1.0), 1.12), k=0.06)


def hind_leg(sx):
    hip, kn, hk, pw = (np.array(v, float) for v in ((sx * 0.4, 0.74, 1.28), (sx * 0.5, 0.42, 0.8),
                                                     (sx * 0.5, 0.88, 0.4), (sx * 0.5, 0.74, 0.12)))
    parts = [ellipsoid((0.31, 0.45, 0.48), (sx * 0.45, 0.62, 1.06)),   # coscia
             round_cone(hip, kn, 0.28, 0.17),
             round_cone(kn, hk, 0.17, 0.11),
             ellipsoid((0.14, 0.18, 0.22), tuple(kn * 0.5 + hk * 0.5 + (0, 0.04, 0.04))),   # polpaccio
             round_cone(hk, pw + (0, 0.04, 0.05), 0.11, 0.13)]
    return union(union(*parts, k=0.08), paw(pw, (sx * 0.1, -1.0), 1.02), k=0.06)


legs = [front_leg(1), front_leg(-1), hind_leg(1), hind_leg(-1)]

# coda alzata e spessa che si arriccia sopra la groppa
TA = [(0, 0.92, 1.5), (0, 1.22, 1.56), (0, 1.36, 1.96), (0, 1.22, 2.36)]
TB = [(0, 1.22, 2.36), (0, 1.08, 2.66), (0, 0.82, 2.66), (0, 0.76, 2.44)]
TAIL_DENSE = np.array(bezier(*TA, 40) + bezier(*TB, 30)[1:])


def tail_rad(u):
    return 0.22 + (0.07 - 0.22) * u ** 0.9


_ti = list(range(0, len(TAIL_DENSE), 4)) + ([len(TAIL_DENSE) - 1] if (len(TAIL_DENSE) - 1) % 4 else [])
tail = tube([tuple(TAIL_DENSE[i]) for i in _ti], [tail_rad(i / (len(TAIL_DENSE) - 1)) for i in _ti])

# ============================================================ le tre teste (spazio locale: muso verso -Y)
JAW_Z = -0.06
HINGE = (0.0, 0.04, JAW_Z)
NECK_SOCKET = (0.0, 0.14, -0.07)
THROAT = (0, -0.5, -0.86)

HEADS = [
    # centrale: la capobranco con le corna, ringhia a muso basso verso chi guarda
    dict(T=(0.0, -1.0, 2.14), s=1.2, yaw=0, pitch=9, roll=0, open=34, horns=True, eye_dir=(0.5, -0.86), scar=True, slant=16, lid=(0.022, 0.42),
         tongue=True, P0=(0, -0.56, 1.66), d0=(0, -0.6, 0.55), L0=0.3, L1=0.28, r0=0.34),
    # sinistra (+X): ulula verso il cielo con la gola piena di fuoco; dal suo collare pende la catena
    dict(T=(1.06, -0.82, 2.46), s=0.97, yaw=36, pitch=-16, roll=-12, open=40, slant=12, lid=(0.024, 0.35),
         fire=True, chain=True, P0=(0.32, -0.52, 1.78), d0=(0.6, -0.45, 0.62), L0=0.35, L1=0.28, r0=0.31),
    # destra (-X): digrigna i denti a muso basso, testa inclinata
    dict(T=(-1.05, -0.88, 2.24), s=0.97, yaw=-34, pitch=12, roll=10, open=18, slant=20, lid=(0.008, 0.55),
         tongue=True, P0=(-0.32, -0.52, 1.76), d0=(-0.6, -0.5, 0.55), L0=0.35, L1=0.28, r0=0.31),
]


def footprint(fx, fy, cy):
    """Ellisse nel piano XY locale (distanza approssimata), per delimitare la bocca."""
    def f(p):
        ex = p[:, 0] / fx
        ey = (p[:, 1] - cy) / fy
        return (np.sqrt(ex * ex + ey * ey) - 1.0) * min(fx, fy)
    return f


def head_kit(h):
    """Testa da cane infernale con la mandibola aperta di h['open'] gradi; ritorna le forme (mondo) per parte."""
    s = h["s"]
    T = np.asarray(h["T"], dtype=np.float32)
    R = euler(h["pitch"], h["roll"], h["yaw"])
    th = h["open"]

    def W(shape):  # locale -> mondo
        return shape.scale(s).rotate(R).translate(T)

    def J(shape):  # mandibola chiusa -> aperta
        return shape.rot(th, 0, 0, pivot=HINGE)

    # ---- cranio largo, muso squadrato, guance muscolose, arcate aggrottate
    cran = ellipsoid((0.25, 0.27, 0.22), (0, 0.02, 0.1))
    occ = ellipsoid((0.19, 0.16, 0.17), (0, 0.16, 0.06))
    muzzle = tbox(-0.06, -0.78, 0.19, 0.115, 0.17, 0.075, JAW_Z - 0.04, JAW_Z - 0.04, 0.06)
    nose = ellipsoid((0.1, 0.07, 0.066), (0, -0.76, 0.06))
    ridge = capsule((0, -0.16, 0.2), (0, -0.66, 0.09), 0.045)
    cheeks = [ellipsoid((0.11, 0.17, 0.12), (sx * 0.2, -0.02, 0.04)) for sx in (1, -1)]
    mounds = [ellipsoid((0.085, 0.07, 0.075), (sx * 0.15, -0.3, 0.12)) for sx in (1, -1)]
    brows = [capsule((sx * 0.05, -0.33, 0.215), (sx * 0.26, -0.12, 0.29), 0.066) for sx in (1, -1)]
    upper = union(cran, occ, k=0.12)
    upper = union(upper, muzzle, k=0.14)
    upper = union(upper, nose, ridge, k=0.06)
    upper = union(upper, *cheeks, k=0.08)
    upper = union(upper, *mounds, k=0.05)
    upper = union(upper, *brows, k=0.045)
    # pieghe del ringhio in rilievo sul dorso del muso
    folds = [tube([(-0.12, y + 0.04, 0.06), (-0.06, y + 0.01, 0.115), (0.0, y, 0.13), (0.06, y + 0.01, 0.115),
                   (0.12, y + 0.04, 0.06)], 0.028) for y in (-0.44, -0.54)]
    upper = union(upper, *folds, k=0.035)
    upper = upper.subtract(union(*[sphere(0.034, (sx * 0.05, -0.825, 0.075)) for sx in (1, -1)]), k=0.02)
    upper = upper.subtract(box((0.6, 0.5, 0.3), (0, HINGE[1] - 0.5, JAW_Z - 0.3)), k=0.012)

    jaw = union(tbox(0.0, -0.74, 0.17, 0.1, JAW_Z + 0.05, JAW_Z + 0.05, -0.2, -0.13, 0.05),
                ellipsoid((0.17, 0.15, 0.1), (0, -0.04, -0.11)),
                ellipsoid((0.075, 0.07, 0.05), (0, -0.66, -0.14)), k=0.06)
    jaw = jaw.subtract(box((0.6, 0.6, 0.3), (0, -0.4, JAW_Z + 0.3)), k=0.012)

    # ---- occhi incandescenti a mandorla con pupilla a fessura, palpebra arrabbiata
    glow, pupils, lids = [], [], []
    cut, slope = h["lid"]
    for sx in (1, -1):
        ex, ey = h.get("eye_dir", (0.62, -0.78))
        p, n = project(upper, (sx * 0.15, -0.3, 0.12), (sx * ex, ey, 0.06))
        a1 = sx * norm(np.cross((0.0, 0.0, 1.0), n))
        a2 = -sx * n
        a3 = np.cross(a1, a2)
        sl = math.radians(h["slant"])
        a1, a3 = a1 * math.cos(sl) + a3 * math.sin(sl), a3 * math.cos(sl) - a1 * math.sin(sl)
        M = np.stack([a1, a2, a3], axis=1).astype(np.float32)
        c = p - n * 0.022
        eye = ellipsoid((0.1, 0.055, 0.055)).rotate(M).translate(c)
        glow.append(eye)
        pupils.append(thin(eye, 0.007, 0.024).intersect(ellipsoid((0.021, 0.2, 0.052)).rotate(M).translate(c)))
        cutp = SDF(lambda q, c0=cut, k0=slope: (c0 + k0 * q[:, 0] - q[:, 2]) / math.sqrt(1 + k0 * k0),
                   (-0.14, -0.14, -0.14), (0.14, 0.14, 0.14))
        lids.append(ellipsoid((0.113, 0.068, 0.068)).intersect(cutp).rotate(M).translate(c))

    # ---- bocca: palato e lingua scuri, parete della gola, denti aguzzi
    dark = []
    pal_fp, jaw_fp = footprint(0.1, 0.34, -0.4), footprint(0.088, 0.33, -0.39)
    pal_reg = SDF(lambda p: np.maximum(pal_fp(p), p[:, 2] - (JAW_Z + 0.03)), (-0.11, -0.76, JAW_Z - 0.05),
                  (0.11, -0.04, JAW_Z + 0.03))
    jaw_reg = SDF(lambda p: np.maximum(jaw_fp(p), (JAW_Z - 0.03) - p[:, 2]), (-0.1, -0.74, JAW_Z - 0.03),
                  (0.1, -0.04, JAW_Z + 0.05))
    dark.append(thin(upper, 0.006, 0.03).intersect(pal_reg))
    dark.append(J(thin(jaw, 0.006, 0.03).intersect(jaw_reg)))
    Rinv = euler(-th, 0, 0)
    piv = np.asarray(HINGE, dtype=np.float32)
    thr_fp = footprint(0.13, 0.11, -0.06)

    def wedge(p, Rinv=Rinv, piv=piv, fp=thr_fp):
        q = (p - piv) @ Rinv.T + piv
        return np.maximum(np.maximum(p[:, 2] - (JAW_Z + 0.004), (JAW_Z - 0.004) - q[:, 2]), fp(p))

    dark.append(SDF(wedge, (-0.13, -0.18, JAW_Z - 0.32), (0.13, 0.06, JAW_Z + 0.01)))
    dark.append(ellipsoid((0.088, 0.05, 0.05), (0, -0.785, 0.075)))   # naso
    fire = []
    if h.get("fire"):  # gola piena di fuoco
        yg = -0.2
        gap = (HINGE[1] - yg) * math.tan(math.radians(th))
        fire.append(ellipsoid((0.08, 0.09, min(0.09, 0.5 * gap)), (0, yg, JAW_Z - gap * 0.5)))

    teeth, bases_up, bases_lo = [], [], []
    rows_up = [((0, -0.58, JAW_Z + 0.012), (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0), abs(a) > 50)
               for a in np.linspace(-62, 62, 7)]
    rows_up += [((0, y, JAW_Z + 0.012), (sx, 0, 0), False) for y in (-0.5, -0.41, -0.32, -0.23) for sx in (1, -1)]
    for o, d, big in rows_up:
        p, n = project(upper, o, d)
        b = p - norm((n[0], n[1], 0.0)) * 0.028
        L = 0.2 if big else 0.07
        r = 0.04 if big else 0.022
        teeth.append(round_cone((b[0], b[1], JAW_Z + 0.03), (b[0], b[1] - (0.02 if big else 0.0), JAW_Z - L), r, 0.01))
        bases_up.append((b[0], b[1], JAW_Z + 0.03))
    rows_lo = [((0, -0.54, JAW_Z - 0.012), (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0), abs(a) > 40)
               for a in np.linspace(-52, 52, 5)]
    rows_lo += [((0, y, JAW_Z - 0.012), (sx, 0, 0), False) for y in (-0.45, -0.36, -0.27) for sx in (1, -1)]
    for o, d, big in rows_lo:
        p, n = project(jaw, o, d)
        b = p - norm((n[0], n[1], 0.0)) * 0.028
        L = 0.13 if big else 0.06
        r = 0.034 if big else 0.02
        teeth.append(J(round_cone((b[0], b[1], JAW_Z - 0.03), (b[0], b[1], JAW_Z + L), r, 0.01)))
        bases_lo.append((b[0], b[1], JAW_Z - 0.03))

    def row_bar(bases):
        """Barretta che unisce le radici dei denti (da un lato all'altro, passando davanti)."""
        pts = sorted(bases, key=lambda q: math.atan2(q[0], -q[1]))
        return tube(pts, 0.016)

    teeth.append(row_bar(bases_up))
    teeth.append(J(row_bar(bases_lo)))

    tongue = None
    if h.get("tongue"):
        tongue = J(ellipsoid((0.08, 0.27, 0.035), (0, -0.37, JAW_Z - 0.012)))

    # ---- orecchie a punta tirate indietro, interno rosso sangue
    ears, red = [], []
    for sx in (1, -1):
        base = np.array([sx * 0.16, 0.1, 0.2])
        M = frame((sx * 0.42, 0.62, 0.64), (sx * 0.45, -0.85, 0.3))   # z lungo l'orecchio, y verso il davanti
        Lr = 0.46
        ear = flatten(tube([(0, 0, -0.04), (0, 0, Lr * 0.45), (0, -0.06, Lr)], [0.13, 0.09, 0.014]), 0.42, axis=1)
        ears.append(ear.rotate(M).translate(base))
        inner = flatten(tube([(0, 0, 0.05), (0, 0, Lr * 0.45), (0, -0.05, Lr * 0.86)], [0.08, 0.06, 0.012]), 0.3,
                        axis=1)
        red.append(inner.translate((0, 0.034, 0)).rotate(M).translate(base))
    if h.get("horns"):  # corna della capobranco: salgono dalla fronte e si piegano all'indietro
        for sx in (1, -1):
            b = np.array([sx * 0.1, -0.2, 0.25])
            red.append(horn(b, b + (sx * 0.05, 0.0, 0.14), b + (sx * 0.14, 0.2, 0.22), b + (sx * 0.2, 0.44, 0.2),
                            0.07, 0.015, n=12))

    # ---- criniera di fuoco sulla nuca (fra le orecchie)
    for (y, z, L, r0, tilt, fk) in ((0.02, 0.26, 0.62, 0.115, 0.0, 0.62), (0.16, 0.22, 0.5, 0.1, 0.36, 0.0),
                                    (0.16, 0.22, 0.5, 0.1, -0.36, 0.0)):
        Mf = frame((tilt, 0.55, 1.0), (0, 1, 0))
        fire.append(flame(L, r0, bend=0.7, wig=0.07, fork=fk).rotate(Mf).translate((0, y, z)))

    skin = union(union(upper, J(jaw), k=0.012), *lids, k=0.012)
    skin = union(skin, *ears, k=0.04)

    # ---- cicatrice ricucita che brucia sopra l'occhio sinistro (solo la capobranco)
    scar, scar_st = [], []
    if h.get("scar"):
        o = np.array((0.06, -0.26, 0.1))
        tgt = [np.array((0.06, -0.24, 0.46)) * (1 - t) + np.array((0.36, -0.46, -0.1)) * t for t in np.linspace(0, 1, 8)]
        pts = []
        for q in tgt:
            pp, nn = project(skin, o, q - o)
            pts.append(pp - nn * 0.01)
        scar.append(tube([tuple(x) for x in pts], [0.02, 0.03, 0.036, 0.038, 0.038, 0.036, 0.03, 0.02]))
        for j in (1, 3, 4, 6):
            c = pts[j]
            t_ = norm(pts[j + 1] - pts[j - 1])
            sd = norm(np.cross(t_, grad(skin, c)))
            a = on_surface(skin, c - sd * 0.065 - t_ * 0.012, 0.006, 3)
            b = on_surface(skin, c + sd * 0.065 + t_ * 0.012, 0.006, 3)
            scar_st.append(capsule(tuple(a), tuple(b), 0.017))
    return dict(skin=W(skin), red=[W(x) for x in red], dark=[W(d) for d in dark], pupils=[W(d) for d in pupils],
                teeth=[W(t) for t in teeth], glow=[W(g) for g in glow], fire=[W(f) for f in fire],
                tongue=W(tongue) if tongue is not None else None, scar=[W(x) for x in scar],
                scar_st=[W(x) for x in scar_st], W=W)


def neck_kit(h):
    """Collo tozzo dalla base nel petto all'attacco della testa."""
    s = h["s"]
    R = euler(h["pitch"], h["roll"], h["yaw"]).astype(np.float64)
    T = np.asarray(h["T"], dtype=np.float64)
    P3 = R @ (s * np.asarray(NECK_SOCKET)) + T
    P2 = P3 + R @ norm((0, 0.6, -0.8)) * h["L1"]
    P0 = np.asarray(h["P0"], dtype=np.float64)
    P1 = P0 + norm(h["d0"]) * h["L0"]
    r0, r1 = h["r0"], 0.2 * s

    def rad(u):
        return r1 + (r0 - r1) * (1.0 - u) ** 1.5

    n = 12
    sdf = tube(bezier(P0, P1, P2, P3, n), [rad(i / n) for i in range(n + 1)])
    us = np.linspace(0.78, 1.0, 5)
    pts = [tuple(float(c) for c in (1 - u) ** 3 * P0 + 3 * (1 - u) ** 2 * u * P1 + 3 * (1 - u) * u ** 2 * P2 + u ** 3 * P3)
           for u in us]
    end = tube(pts, [rad(u) - 0.012 + 0.02 * min(max((u - 0.78) / 0.08, 0.0), 1.0) for u in us])
    return dict(sdf=sdf, end=end, dense=np.array(bezier(P0, P1, P2, P3, 120)), rad=rad, s=s)


heads = [head_kit(h) for h in HEADS]
necks = [neck_kit(h) for h in HEADS]

body_main = fast_union(legs, k=0.12, base=trunk)
core = fast_union([tail, *[nk["sdf"] for nk in necks]], k=0.16, base=body_main)
core = core.intersect(halfspace_z(0.0))
print("[cerberus] corpo pronto", flush=True)

# ============================================================ crepe di lava (linee frastagliate sulla pelle)
CRACKS = []  # (origine interna, punti grezzi, larghezza)


def add_crack(origin, a, b, n=6, amp=0.05, w=0.03, branch=None):
    pts = zigzag(a, b, n, amp, np.asarray(a, float) - np.asarray(origin, float))
    CRACKS.append((origin, pts, w))
    if branch:  # (indice del punto di partenza, punto d'arrivo, segmenti)
        j, end, nb = branch
        CRACKS.append((origin, zigzag(pts[j], end, nb, amp * 0.7, pts[j] - np.asarray(origin, float)), w * 0.7))


for sx in (1, -1):
    # spalla -> gomito
    add_crack((sx * 0.3, -0.48, 1.25), (sx * 0.52, -0.3, 1.75), (sx * 0.76, -0.5, 0.84), n=7, w=0.034,
              branch=(3, (sx * 0.78, -0.18, 1.2), 3))
    # fianco
    add_crack((0, 0.06, 1.3), (sx * 0.42, -0.05, 1.68), (sx * 0.56, 0.32, 1.04), n=7, w=0.032,
              branch=(4, (sx * 0.56, -0.08, 1.0), 3))
    # coscia
    add_crack((sx * 0.4, 0.65, 1.06), (sx * 0.52, 0.5, 1.48), (sx * 0.76, 0.78, 0.86), n=6, w=0.032,
              branch=(3, (sx * 0.76, 0.4, 0.94), 3))
    # petto: crepe che partono dalla cucitura
    add_crack((0, -0.44, 1.2), (sx * 0.1, -1.3, 1.36), (sx * 0.52, -1.1, 0.9), n=6, amp=0.04, w=0.03,
              branch=(2, (sx * 0.5, -1.2, 1.5), 3))
    # avambraccio (davanti) e stinco
    add_crack((sx * 0.64, -0.64, 0.52), (sx * 0.74, -0.86, 0.8), (sx * 0.7, -1.0, 0.3), n=4, amp=0.03, w=0.026)
    add_crack((sx * 0.5, 0.64, 0.62), (sx * 0.65, 0.58, 0.74), (sx * 0.63, 0.9, 0.38), n=4, amp=0.03, w=0.024)

crack_tubes = []
for origin, pts, w in CRACKS:
    q, nr = project_many(core, [origin], [np.asarray(p, float) - np.asarray(origin, float) for p in pts])
    k = len(q)
    radii = [w * (0.45 + 0.55 * math.sin(math.pi * (0.05 + 0.9 * j / (k - 1)))) for j in range(k)]
    crack_tubes.append(tube([tuple(p - nn * r * 0.4) for p, nn, r in zip(q, nr, radii)], radii))

# cucitura sul petto: la lava filtra dalla ferita ricucita
SEAM_Z = np.linspace(1.52, 0.84, 7)
seam_pts, seam_n = project_many(core, [(0, -0.5, z) for z in SEAM_Z], [(0, -1.0, 0.05)])
crack_tubes.append(tube([tuple(p - nn * 0.012) for p, nn in zip(seam_pts, seam_n)],
                        [0.02, 0.03, 0.034, 0.034, 0.034, 0.03, 0.02]))
stitches = []
for j in range(1, len(seam_pts) - 1):
    c = seam_pts[j]
    tn = norm(seam_pts[j + 1] - seam_pts[j - 1])
    nn = grad(core, c)
    sd = norm(np.cross(tn, nn))
    for sg in (1, -1):
        a = on_surface(core, c - sd * 0.085 - tn * 0.05 * sg, 0.006, 3)
        b = on_surface(core, c + sd * 0.085 + tn * 0.05 * sg, 0.006, 3)
        stitches.append(capsule(tuple(a), tuple(b), 0.02))

m.add("Body", core, BLACK, tris=3300, voxel=0.048 * VX)
m.add("Heads", fast_union([union(nk["end"], hk["skin"], k=0.07 * h["s"]) for nk, hk, h in zip(necks, heads, HEADS)]),
      BLACK, role="skin", tris=3450, voxel=0.032 * VX)
print("[cerberus] teste pronte", flush=True)

# ============================================================ fiamme: criniere su collo e nuca, punta della coda
fires = [f for hk in heads for f in hk["fire"]]
COLLAR_U = 0.46
for nk in necks:
    info, _ = along(nk["dense"], nk["rad"], [0.18, 0.7, 0.86], THROAT)
    for j, (c, tan, f, r) in enumerate(info):
        L = (0.36 if j < 1 else 0.42) * nk["s"]
        for side, lean in ((0.0, 0.0), (1.0, 0.6), (-1.0, 0.6)):
            sd = np.cross(tan, f)
            d_out = norm(-f + sd * side * lean)
            base = c + d_out * (r - 0.06)
            up = norm(d_out * 0.7 + np.array([0, 0, 0.6]) - tan * 0.15)
            ll = L * (1.0 if side == 0 else 0.74)
            fires.append(flame(ll, 0.1 if side == 0 else 0.08, wig=0.06, fork=0.55 if side == 0 else 0.0).rotate(
                frame(up, -tan)).translate(base))
# cresta di fuoco sul garrese, dietro i colli
for y, z, L in ((-0.42, 2.12, 0.56), (-0.16, 2.08, 0.5), (0.08, 1.98, 0.4)):
    p, nrm = project(trunk, (0, y, 1.5), (0, 0, 1))
    for sx, ll in (((0.0, 1.0), (0.34, 0.74), (-0.34, 0.74)) if y < 0 else ((0.0, 1.0),)):
        up = norm(nrm + np.array([sx, 0.3, 0.0]))
        fires.append(flame(L * ll, 0.115 * (0.8 + 0.2 * ll), wig=0.07, fork=0.6 if sx == 0 else 0.0).rotate(
            frame(up, (0, 1, 0))).translate(
            p + np.array([sx * 0.22, 0, 0]) - nrm * 0.06))
# punta della coda che brucia: tre lingue aperte a ventaglio
t_end = norm(TAIL_DENSE[-1] - TAIL_DENSE[-6])
for tilt, L, back in ((0.0, 0.4, 0.5), (0.9, 0.3, 0.2), (-0.9, 0.3, 0.2)):
    up = norm(np.array([tilt, 0.0, 1.0]) + np.array([0, -back, 0]))
    fires.append(flame(L, 0.085, bend=0.5, wig=0.05, flat=0.7).rotate(frame(up, (0, 1, 0))).translate(
        TAIL_DENSE[-1] - t_end * 0.06))
m.add("Flames", fast_union(fires, k=0.025), FIRE, material="Neon", role="glow", tris=2200, voxel=0.038 * VX)
m.add("LavaCracks", fast_union(crack_tubes + [x for hk in heads for x in hk["scar"]]), LAVA, material="Neon", role="glow", tris=1300, voxel=0.025 * VX)

# ============================================================ facce
m.add("EyeGlow", fast_union([g for hk in heads for g in hk["glow"]]), EYE_GLOW, material="Neon", role="glow", tris=300,
      voxel=0.023 * VX)
m.add("Pupils", fast_union([p for hk in heads for p in hk["pupils"]]), PUPIL, role="eye", tris=200, voxel=0.0195 * VX)
m.add("Mouths", fast_union([d for hk in heads for d in hk["dark"]]), MOUTH, role="eye", tris=600, voxel=0.035 * VX)
m.add("Teeth", fast_union([t for hk in heads for t in hk["teeth"]]), TOOTH, role="shine", tris=1200, voxel=0.0228 * VX)
m.add("Tongues", union(*[hk["tongue"] for hk in heads if hk["tongue"] is not None]), TONGUE, role="detail", tris=200,
      voxel=0.028 * VX)

# ============================================================ rosso sangue: corna, orecchie, spuntoni di schiena e coda
spikes = [x for hk in heads for x in hk["red"]]
for j, (y, L) in enumerate([(0.12, 0.2), (0.32, 0.22), (0.52, 0.2), (0.72, 0.18), (0.9, 0.15)]):
    p, nrm = project(trunk, (0, y, 1.5), (0, 0.15, 1))
    ax = norm(nrm + np.array([0, 0.55, 0]))
    spikes.append(round_cone(tuple(p - ax * 0.04), tuple(p + ax * L), 0.07, 0.013))
CURL_C = np.array([0.0, 1.14, 2.4])   # centro del ricciolo: gli spuntoni stanno sul lato esterno
info, _ = along(TAIL_DENSE, tail_rad, np.linspace(0.3, 0.86, 6), (0, -1.0, 0.3))
for j, (c, tan, f, r) in enumerate(info):
    out = norm((c - CURL_C) - tan * float(np.dot(c - CURL_C, tan)))
    ax = norm(out - tan * 0.5)
    L = (0.15 - 0.012 * j) * (0.75 if j < 2 else 1.0)
    spikes.append(round_cone(tuple(c + out * (r - 0.03)), tuple(c + out * (r - 0.03) + ax * L), 0.055 - 0.004 * j,
                             0.013))
m.add("Horns", fast_union(spikes), BLOOD, role="detail", tris=900, voxel=0.028 * VX)

# ============================================================ artigli color osso
claws = []
for tip, fwd, sz in TOES:
    t0 = np.asarray(tip, dtype=np.float64)
    claws.append(horn(t0 + (0, 0, 0.02), t0 + fwd * 0.07 * sz + (0, 0, 0.035 * sz), t0 + fwd * 0.14 * sz,
                      t0 + fwd * 0.18 * sz + (0, 0, -0.05 * sz), 0.054 * sz, 0.015, n=7))
m.add("Claws", fast_union(claws).intersect(halfspace_z(0.002)), TOOTH, role="detail", tris=500, voxel=0.03 * VX)

# ============================================================ collari di ferro chiodati, catena spezzata
iron, chain = [], []
for nk, h in zip(necks, HEADS):
    (c, tan, f, r), = along(nk["dense"], nk["rad"], [COLLAR_U], THROAT)[0]
    M = frame(tan, f)
    Rc = r + 0.015
    iron.append(band(Rc, 0.045, 0.075).rotate(M).translate(c))
    sd = np.cross(tan, f)
    for a in np.linspace(0, 2 * math.pi, 9)[:-1]:
        if abs(math.cos(a) + 1.0) < 0.3:   # niente spuntoni sotto la gola
            continue
        d = -f * math.cos(a) + sd * math.sin(a)
        iron.append(round_cone(tuple(c + d * (Rc + 0.02)), tuple(c + d * (Rc + 0.22)), 0.054, 0.013))
    if h.get("chain"):
        ring_c = c + f * (Rc + 0.06)
        chain.append(chain_link(ring_c, tan, sd, 0.0, 0.05, 0.016))
        down = np.array([0.0, 0.0, -1.0])
        p = ring_c + np.array([0, 0, -0.07])
        for i in range(4):
            nrm_ = sd if i % 2 == 0 else np.cross(down, sd)
            lk = chain_link(p + down * 0.06, down, nrm_, 0.035, 0.045, 0.017)
            if i == 3:  # l'ultima maglia e' spezzata
                lk = lk.subtract(sphere(0.04, tuple(p + down * 0.15)))
            chain.append(lk)
            p = p + down * 0.105
m.add("Collars", fast_union(iron), IRON, material="Metal", role="detail", tris=1000, voxel=0.032 * VX)
m.add("Chain", fast_union(chain), IRON_DK, material="Metal", role="detail", tris=380, voxel=0.0135 * VX)
m.add("Stitches", fast_union(stitches + [x for hk in heads for x in hk["scar_st"]]), THREAD, role="detail", tris=300, voxel=0.019 * VX)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 600)))
