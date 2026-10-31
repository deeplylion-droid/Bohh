"""Guardiano Anubi (AnubisGuard) - pet del Percorso Estremo (antico Egitto).

Il guardiano delle tombe: uno sciacallo nero e muscoloso, in piedi su un piccolo piedistallo di
arenaria con i geroglifici che brillano di blu. Gambe da sciacallo (ginocchio avanti, garretto
alto), coda folta con un anello d'oro. Testa da sciacallo con il muso lungo e affilato, orecchie
altissime a punta bordate d'oro con l'interno di lapislazzuli, occhi blu incandescenti truccati con
la linea d'oro "dell'occhio di Horus" e un ghigno furbo pieno di dentini aguzzi.
Gioielli da faraone: un largo collare usekh d'oro a fasce di lapislazzuli con le gocce sul bordo,
bracciali d'oro a righe blu, cintura d'oro e gonnellino shendyt blu plissettato con il grembiule
d'oro a righe blu. Con la destra tiene lo scettro was piantato sul piedistallo, con la sinistra
alza un khopesh di bronzo dal filo incandescente (parte Neon "Mane": il gioco ci attacca le
scintille elettriche).
Tocco "toy horror": il braccio sinistro e' avvolto in bende da mummia ricucite con un filo rosso
scuro, con un lembo di benda che pende.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, box, capsule, cylinder, ellipsoid, euler, halfspace_z, prism, project,  # noqa: E402
                     round_cone, smin, sphere, torus, tube, union)
from lib.toy import Model  # noqa: E402

DRAFT = os.environ.get("DRAFT", "") == "1"
VX = 1.35 if DRAFT else 1.0   # bozza: voxel piu' grossi per iterare in fretta


# ============================================================ helper (lib/ non si modifica: copiati/adattati qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def grad(sdf, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float64)
    g = np.array([sdf((p + e)[None, :].astype(np.float32))[0] - sdf((p - e)[None, :].astype(np.float32))[0]
                  for e in np.eye(3) * eps])
    return g / max(np.linalg.norm(g), 1e-9)


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


def paint(core, region, out=0.016, inn=0.035, margin=0.05):
    """Strato di "vernice" (guscio fra -inn e +out attorno a core) dentro 'region'; core valutato solo vicino."""
    def f(p):
        r = region(p)
        d = np.maximum(r, margin).astype(np.float32)
        idx = np.nonzero(r < margin)[0]
        if len(idx):
            c = core(p[idx])
            d[idx] = np.maximum(np.maximum(c - out, -c - inn), r[idx])
        return d

    return SDF(f, np.maximum(core.lo - out, region.lo), np.minimum(core.hi + out, region.hi))


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
    return ellipsoid(radii).rotate(M).translate(c)


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


def band(R, t, h, rr=0.012):
    """Fascia (anello a sezione rettangolare arrotondata) nel piano XY: raggio R, spessore 2t, altezza 2h."""
    def f(p):
        rho = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2) - R
        qx = np.abs(rho) - (t - rr)
        qz = np.abs(p[:, 2]) - (h - rr)
        return np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qz, 0) ** 2) + np.minimum(np.maximum(qx, qz), 0) - rr

    e = R + t
    return SDF(f, (-e, -e, -h), (e, e, h))


def footprint(fx, fy, cy):
    """Ellisse nel piano XY locale (distanza approssimata), per delimitare la bocca."""
    def f(p):
        ex = p[:, 0] / fx
        ey = (p[:, 1] - cy) / fy
        return (np.sqrt(ex * ex + ey * ey) - 1.0) * min(fx, fy)
    return f


def limb_frame(a, b, hint=(0.0, -1.0, 0.0)):
    """Base (asse, u, v) di un segmento di arto da a a b, con u il piu' possibile verso 'hint'."""
    ax = norm(np.asarray(b, float) - np.asarray(a, float))
    h = np.asarray(hint, float)
    u = h - ax * float(np.dot(h, ax))
    if np.linalg.norm(u) < 1e-6:
        u = np.array([1.0, 0.0, 0.0]) - ax * ax[0]
    u = norm(u)
    return ax, u, np.cross(ax, u)


# ============================================================ colori
BLACK = (34, 32, 46)        # pelo nero appena bluastro (il nero puro in gioco e' piatto)
GOLD = (248, 192, 62)       # oro (Foil)
LAPIS = (30, 64, 200)       # lapislazzuli
BLUE_GLOW = (70, 186, 255)  # occhi e geroglifici (Neon)
EDGE_GLOW = (120, 226, 255)  # filo del khopesh (Neon "Mane")
STONE = (206, 172, 120)     # arenaria del piedistallo
BRONZE = (204, 134, 62)     # lama del khopesh
LINEN = (226, 214, 186)     # bende da mummia
THREAD = (132, 24, 40)      # filo rosso scuro
MOUTH = (40, 12, 30)
TOOTH = (248, 242, 228)

m = Model("AnubisGuard", "pet")

Z0 = 0.34   # piano del piedistallo (le zampe poggiano qui)

# ============================================================ piedistallo di arenaria spigoloso
plinth = union(box((0.76, 0.6, 0.065), (0, 0.0, 0.065), round=0.012),          # zoccolo
               box((0.69, 0.53, 0.11), (0, 0.0, 0.13 + 0.11 - 0.01), round=0.01),  # blocco
               box((0.72, 0.56, 0.03), (0, 0.0, Z0 - 0.03), round=0.01))           # cornice
FACE_Y = -0.53
plinth = plinth.subtract(box((0.56, 0.03, 0.065), (0, FACE_Y, 0.215)))            # riquadro inciso sul davanti
for c, r, ang in (((0.76, -0.6, 0.13), 0.09, (20, 35, 40)), ((-0.72, 0.56, 0.3), 0.08, (40, 10, 30)),
                  ((0.69, 0.53, 0.1), 0.07, (10, 50, 20)), ((-0.76, -0.6, 0.02), 0.06, (30, 20, 60))):
    plinth = plinth.subtract(box((r, r, r), c).rot(*ang, pivot=c))                # spigoli scheggiati

# geroglifici luminosi nel riquadro: occhio di Horus, ankh, djed, ankh, occhio
GY = FACE_Y + 0.012   # appena fuori dal fondo del riquadro (che e' a FACE_Y + 0.03)


def ankh(x0, z0, s=1.0):
    loop = torus(0.03 * s, 0.011 * s).rot(90, 0, 0).translate((x0, GY, z0 + 0.06 * s))
    return union(loop, capsule((x0, GY, z0 - 0.06 * s), (x0, GY, z0 + 0.028 * s), 0.012 * s),
                 capsule((x0 - 0.045 * s, GY, z0 + 0.02 * s), (x0 + 0.045 * s, GY, z0 + 0.02 * s), 0.012 * s))


def eye_of_horus(x0, z0, sx=1, s=1.0):
    pts = [(x0 + sx * dx * s, GY, z0 + dz * s) for dx, dz in ((-0.07, 0.0), (-0.03, 0.025), (0.02, 0.028), (0.06, 0.008))]
    low = [(x0 + sx * dx * s, GY, z0 + dz * s) for dx, dz in ((-0.07, 0.0), (-0.025, -0.02), (0.02, -0.018), (0.06, 0.008))]
    parts = [tube(pts, 0.01 * s), tube(low, 0.01 * s), sphere(0.02 * s, (x0, GY, z0 + 0.004 * s)),
             tube([(x0 - sx * 0.065 * s, GY, z0 + 0.05 * s), (x0, GY, z0 + 0.06 * s), (x0 + sx * 0.06 * s, GY, z0 + 0.045 * s)],
                  0.01 * s),                                                        # sopracciglio
             tube([(x0 + sx * 0.06 * s, GY, z0 + 0.008 * s), (x0 + sx * 0.11 * s, GY, z0 + 0.012 * s)], 0.009 * s),
             tube([(x0 - sx * 0.005 * s, GY, z0 - 0.02 * s), (x0 - sx * 0.01 * s, GY, z0 - 0.07 * s),
                   (x0 + sx * 0.02 * s, GY, z0 - 0.085 * s), (x0 + sx * 0.035 * s, GY, z0 - 0.07 * s)], 0.009 * s)]
    return union(*parts)


def djed(x0, z0, s=1.0):
    parts = [capsule((x0, GY, z0 - 0.065 * s), (x0, GY, z0 + 0.06 * s), 0.016 * s)]
    for j in range(4):
        z = z0 + (0.0 + 0.022 * j) * s
        parts.append(capsule((x0 - 0.04 * s, GY, z), (x0 + 0.04 * s, GY, z), 0.008 * s))
    return union(*parts)


glyphs = [eye_of_horus(-0.4, 0.21, sx=1), ankh(-0.17, 0.215), djed(0.0, 0.215), ankh(0.17, 0.215),
          eye_of_horus(0.4, 0.21, sx=-1)]

# ============================================================ tronco a V
pelvis = ellipsoid((0.31, 0.24, 0.22), (0, 0.04, 1.48))
waist = ellipsoid((0.22, 0.18, 0.22), (0, 0.03, 1.69))
ribcage = ellipsoid((0.4, 0.29, 0.29), (0, 0.03, 1.96))
upper_back = ellipsoid((0.55, 0.29, 0.24), (0, 0.08, 2.11))
torso = union(pelvis, waist, ribcage, upper_back, k=0.2)
pecs = [ell((sx * 0.21, -0.19, 2.04), (0.24, 0.15, 0.18), axis=(sx * 0.3, 0.0, 1.0)) for sx in (1, -1)]
lats = [ell((sx * 0.35, 0.08, 1.95), (0.17, 0.22, 0.3), axis=(sx * 0.35, 0.0, 1.0)) for sx in (1, -1)]
abs_ = [ellipsoid((0.072, 0.058, 0.054), (sx * 0.082, -0.19, z)) for sx in (1, -1) for z in (1.66, 1.77, 1.88)]
traps = ellipsoid((0.34, 0.23, 0.2), (0, 0.11, 2.26))
torso = union(torso, *pecs, *lats, k=0.1)
torso = union(torso, *abs_, k=0.04)
torso = union(torso, traps, k=0.12)
torso = torso.subtract(capsule((0, -0.36, 2.15), (0, -0.34, 1.95), 0.026), k=0.035)   # solco fra i pettorali
neck = round_cone((0, 0.08, 2.13), (0, -0.05, 2.47), 0.19, 0.15)


# ============================================================ braccia
def fist(F, U, K, s=1.0):
    """Pugno chiuso attorno a un manico con asse U; nocche verso K."""
    U = norm(U)
    K = norm(np.asarray(K, float) - U * float(np.dot(K, U)))
    T = np.cross(U, K)
    parts = [ell(F - K * 0.02 * s, (0.105 * s, 0.1 * s, 0.12 * s), axis=U, side=K)]
    for t in (0.075, 0.025, -0.025, -0.075):   # quattro dita tozze arrotolate attorno al manico, nocche in rilievo
        c = F + U * t * s * 1.08
        parts.append(capsule(tuple(c + K * 0.1 * s + T * 0.02 * s), tuple(c + K * 0.05 * s - T * 0.085 * s), 0.036 * s))
        parts.append(sphere(0.042 * s, tuple(c + K * 0.105 * s + T * 0.015 * s)))
    parts.append(capsule(tuple(F + U * 0.1 * s - K * 0.03 * s + T * 0.07 * s),
                         tuple(F + U * 0.1 * s + K * 0.06 * s - T * 0.07 * s), 0.04 * s))     # pollice
    return union(*parts, k=0.022)


ARMS = {
    # destra (-X): tiene lo scettro was piantato sul piedistallo
    -1: dict(sh=(-0.56, 0.06, 2.12), el=(-0.8, 0.12, 1.74), wr=(-0.75, -0.2, 1.73), fi=(-0.72, -0.33, 1.75),
             K=(-0.3, -1.0, 0.0)),
    # sinistra (+X): bendata, alza il khopesh
    1: dict(sh=(0.56, 0.06, 2.12), el=(1.0, 0.1, 1.98), wr=(0.99, -0.05, 2.5), fi=(0.98, -0.08, 2.62),
            K=(0.3, -1.0, 0.0)),
}
STAFF_X, STAFF_Y = -0.72, -0.33
STAFF_U = (0.0, 0.0, 1.0)
KH_U = norm((0.1, -0.04, 1.0))   # manico del khopesh: dritto in alto, appena in fuori
arm_parts, arm_sdf, FISTS = {}, {}, []
for sx, A in ARMS.items():
    sh, el, wr, fi = (np.array(A[k], float) for k in ("sh", "el", "wr", "fi"))
    ua, fa = el - sh, wr - el
    parts = [ellipsoid((0.22, 0.22, 0.23), (sx * 0.58, 0.06, 2.14)),                   # deltoide
             round_cone(sh, el, 0.17, 0.12),
             ell(sh + ua * 0.5 + np.array([0, -0.06, 0.03]), (0.13, 0.12, 0.2), axis=ua),     # bicipite
             ell(sh + ua * 0.45 + np.array([0, 0.07, -0.02]), (0.12, 0.12, 0.2), axis=ua),    # tricipite
             round_cone(el, wr, 0.12, 0.09),
             ell(el + fa * 0.3, (0.13, 0.12, 0.17), axis=fa),                               # avambraccio
             round_cone(wr, fi, 0.09, 0.1)]
    arm_sdf[sx] = union(*parts[1:6], k=0.06)
    U = STAFF_U if sx < 0 else KH_U
    arm_parts[sx] = parts
    FISTS.append(fist(fi, U, A["K"], 1.15))
arms = arm_parts[-1] + arm_parts[1]

# ============================================================ gambe da sciacallo (ginocchio avanti, garretto alto)
LEGS = {sx: dict(hip=(sx * 0.21, 0.05, 1.44), knee=(sx * 0.3, -0.2, 1.0), hock=(sx * 0.32, 0.16, 0.66),
                 paw=(sx * 0.34, -0.06, Z0 + 0.07)) for sx in (1, -1)}
legs, TOES = [], []


def paw(c, fwd, s=1.0):
    fwd = norm((fwd[0], fwd[1], 0.0))
    side = np.array([-fwd[1], fwd[0], 0.0])
    c = np.asarray(c, float)
    pad = ellipsoid((0.15 * s, 0.17 * s, 0.085 * s)).rotate(frame((0, 0, 1), fwd)).translate(c)
    toes = []
    for dx in (-0.1, -0.034, 0.034, 0.1):
        a = c + side * dx * s + np.array([0, 0, 0.015])
        tip = c + side * dx * 1.3 * s + fwd * (0.16 - abs(dx) * 0.4) * s
        tip[2] = Z0 + 0.055 * s
        toes.append(capsule(tuple(a), tuple(tip), 0.056 * s))
        TOES.append((tip, norm(fwd + side * dx * 2.0), s))
    return union(pad, *toes, k=0.04)


for sx, L in LEGS.items():
    hip, kn, hk, pw = (np.array(L[k], float) for k in ("hip", "knee", "hock", "paw"))
    fem, shin = kn - hip, hk - kn
    legs += [round_cone(hip, kn, 0.2, 0.13),
             ell(hip + fem * 0.45 + np.array([sx * 0.04, -0.02, 0.0]), (0.19, 0.2, 0.29), axis=fem),   # coscia
             ell(hip + fem * 0.7 + np.array([0, -0.08, 0.0]), (0.12, 0.11, 0.17), axis=fem),          # quadricipite
             round_cone(kn, hk, 0.13, 0.085),
             ell(kn + shin * 0.35 + np.array([0, 0.05, 0.02]), (0.11, 0.12, 0.17), axis=shin),       # polpaccio
             round_cone(hk, pw + np.array([0, 0.03, 0.04]), 0.085, 0.09)]
    legs.append(paw(pw, (sx * 0.12, -1.0), 0.95))

# coda folta da sciacallo che scende dietro le gambe e si arriccia in fuori
TAIL_PTS = bezier((0, 0.24, 1.42), (0.0, 0.62, 1.28), (0.16, 0.82, 0.86), (0.36, 0.66, 0.58), 12)
TAIL_R = [0.07, 0.085, 0.11, 0.13, 0.145, 0.15, 0.148, 0.14, 0.125, 0.105, 0.08, 0.055, 0.03]
tail = tube(TAIL_PTS, TAIL_R)

# ============================================================ testa da sciacallo (spazio locale: muso verso -Y)
HEAD_T = np.array([0.0, -0.17, 2.72], dtype=np.float32)
HS = 1.22
R_HEAD = euler(7.0, -3.0, 9.0)   # muso appena abbassato, girato verso la camera 3/4
JAW_Z = -0.07
HINGE = (0.0, 0.04, JAW_Z)
GAPE = 16.0


def Hd(shape):
    return shape.scale(HS).rotate(R_HEAD).translate(HEAD_T)


def Jw(shape):
    return shape.rot(GAPE, 0, 0, pivot=HINGE)


cran = ellipsoid((0.235, 0.25, 0.24), (0, 0.04, 0.06))
occ = ellipsoid((0.18, 0.16, 0.17), (0, 0.15, 0.0))
snout = tbox(-0.02, -0.66, 0.15, 0.058, 0.17, 0.062, JAW_Z - 0.04, JAW_Z - 0.03, 0.048)
cheeks = [ellipsoid((0.1, 0.15, 0.1), (sx * 0.16, -0.06, -0.03)) for sx in (1, -1)]
brows = [capsule((sx * 0.04, -0.26, 0.185), (sx * 0.19, -0.11, 0.225), 0.042) for sx in (1, -1)]
nose = ellipsoid((0.06, 0.05, 0.045), (0, -0.655, 0.058))
upper = union(cran, occ, k=0.1)
upper = union(upper, snout, k=0.12)
upper = union(upper, *cheeks, k=0.07)
upper = union(upper, nose, k=0.03)
upper = union(upper, *brows, k=0.05)
upper = upper.subtract(box((0.5, 0.5, 0.3), (0, HINGE[1] - 0.5, JAW_Z - 0.3)), k=0.01)

jaw = union(tbox(0.02, -0.6, 0.13, 0.05, JAW_Z + 0.04, JAW_Z + 0.04, JAW_Z - 0.13, JAW_Z - 0.08, 0.04),
            ellipsoid((0.13, 0.13, 0.08), (0, -0.02, -0.13)), k=0.05)
jaw = jaw.subtract(box((0.5, 0.6, 0.3), (0, -0.4, JAW_Z + 0.3)), k=0.01)

# ---- occhi blu incandescenti a mandorla, palpebra severa
eyes, lids, EYE_INFO = [], [], {}
for sx in (1, -1):
    p, n = project(upper, (sx * 0.1, -0.12, 0.09), (sx * 0.62, -0.76, 0.12))
    a1 = sx * norm(np.cross((0.0, 0.0, 1.0), n))
    a2 = -sx * n
    a3 = np.cross(a1, a2)
    sl = math.radians(18)
    a1, a3 = a1 * math.cos(sl) + a3 * math.sin(sl), a3 * math.cos(sl) - a1 * math.sin(sl)
    M = np.stack([a1, a2, a3], axis=1).astype(np.float32)
    c = p - n * 0.02
    eyes.append(ellipsoid((0.085, 0.045, 0.045)).rotate(M).translate(c))
    cutp = SDF(lambda q: (0.016 + 0.4 * q[:, 0] - q[:, 2]) / math.sqrt(1.16), (-0.14, -0.14, -0.14), (0.14, 0.14, 0.14))
    lids.append(ellipsoid((0.096, 0.056, 0.056)).intersect(cutp).rotate(M).translate(c))
    EYE_INFO[sx] = (c, a1, a3, n)   # a1: verso l'esterno-dietro, a3: in alto
# ---- orecchie altissime: lastra nera, bordo d'oro, interno di lapislazzuli (piano locale: x largo, y lungo, z davanti)
EAR_POLY = [(-0.13, -0.08), (0.13, -0.08), (0.125, 0.12), (0.095, 0.3), (0.05, 0.5), (0.0, 0.66), (-0.05, 0.5),
            (-0.095, 0.3), (-0.125, 0.12)]
EAR_T = 0.03
ABOVE = SDF(lambda p: -p[:, 1], (-1, 0, -1), (1, 1, 1))   # solo la parte fuori dalla testa (y locale > 0)
ear_black, ear_gold, ear_lapis = [], [], []
for sx in (1, -1):
    base = np.array([sx * 0.12, 0.07, 0.17])
    axis = norm((sx * 0.2, 0.14, 1.0))
    n0 = norm((sx * 0.22, -1.0, 0.1))
    w = norm(np.cross(axis, n0))
    nn = np.cross(w, axis)
    M = np.stack([w, axis, nn], axis=1).astype(np.float32)
    plate = prism(EAR_POLY, -EAR_T, EAR_T, round=0.022)
    ear_black.append(plate.rotate(M).translate(base))
    rim = prism(EAR_POLY, -EAR_T, EAR_T).offset(0.013).subtract(prism(EAR_POLY, -1, 1).offset(-0.042)).intersect(ABOVE)
    ear_gold.append(rim.rotate(M).translate(base))
    inner = prism(EAR_POLY, EAR_T - 0.03, EAR_T + 0.008).intersect(prism(EAR_POLY, -1, 1).offset(-0.05)).intersect(ABOVE)
    ear_lapis.append(inner.rotate(M).translate(base))

head_skin = union(union(upper, Jw(jaw), k=0.012), *lids, k=0.012)
head_skin = union(head_skin, *ear_black, k=0.035)

# ---- trucco d'oro "occhio di Horus": linea che allunga l'occhio verso la tempia e lacrima sotto l'occhio
liners = []
for sx in (1, -1):
    c, a1, a3, n = EYE_INFO[sx]
    line = [c + a1 * (0.07 + 0.045 * j) + a3 * (0.012 + 0.006 * j) for j in range(5)]
    line = [on_surface(head_skin, q, 0.004, 4) for q in line]
    liners.append(tube([tuple(q) for q in line], [0.017, 0.017, 0.016, 0.014, 0.011]))
    tear = [c - a3 * 0.05 + a1 * 0.005, c - a3 * 0.09 + a1 * 0.01, c - a3 * 0.125 + a1 * 0.035,
            c - a3 * 0.12 + a1 * 0.065]
    tear = [on_surface(head_skin, q, 0.004, 4) for q in tear]
    liners.append(tube([tuple(q) for q in tear], [0.015, 0.015, 0.014, 0.012]))

# ---- bocca: palato e lingua scuri, gola, naso; ghigno pieno di dentini aguzzi
dark = []
pal_fp, jaw_fp = footprint(0.075, 0.29, -0.33), footprint(0.062, 0.27, -0.32)
pal_reg = SDF(lambda p: np.maximum(pal_fp(p), p[:, 2] - (JAW_Z + 0.03)), (-0.09, -0.64, JAW_Z - 0.05),
              (0.09, -0.02, JAW_Z + 0.03))
jaw_reg = SDF(lambda p: np.maximum(jaw_fp(p), (JAW_Z - 0.03) - p[:, 2]), (-0.08, -0.61, JAW_Z - 0.03),
              (0.08, -0.02, JAW_Z + 0.05))
dark.append(thin(upper, 0.006, 0.03).intersect(pal_reg))
dark.append(Jw(thin(jaw, 0.006, 0.03).intersect(jaw_reg)))
Rinv = euler(-GAPE, 0, 0)
piv = np.asarray(HINGE, dtype=np.float32)
thr_fp = footprint(0.1, 0.09, -0.05)


def wedge(p):
    q = (p - piv) @ Rinv.T + piv
    return np.maximum(np.maximum(p[:, 2] - (JAW_Z + 0.004), (JAW_Z - 0.004) - q[:, 2]), thr_fp(p))


dark.append(SDF(wedge, (-0.1, -0.15, JAW_Z - 0.2), (0.1, 0.05, JAW_Z + 0.01)))
dark.append(ellipsoid((0.05, 0.04, 0.036), (0, -0.685, 0.066)))   # tartufo

teeth, bases_up, bases_lo = [], [], []
rows_up = [((0, -0.54, JAW_Z + 0.012), (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0), abs(a) > 40)
           for a in np.linspace(-55, 55, 5)]
rows_up += [((0, y, JAW_Z + 0.012), (sx, 0, 0), False) for y in (-0.48, -0.4, -0.32, -0.24, -0.16) for sx in (1, -1)]
for o, d, big in rows_up:
    p, n = project(upper, o, d)
    b = p - norm((n[0], n[1], 0.0)) * 0.022
    L = 0.12 if big else 0.06
    r = 0.028 if big else 0.019
    teeth.append(round_cone((b[0], b[1], JAW_Z + 0.025), (b[0], b[1] - (0.012 if big else 0.0), JAW_Z - L), r, 0.008))
    bases_up.append((b[0], b[1], JAW_Z + 0.025))
rows_lo = [((0, -0.5, JAW_Z - 0.012), (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0), abs(a) > 35)
           for a in np.linspace(-48, 48, 4)]
rows_lo += [((0, y, JAW_Z - 0.012), (sx, 0, 0), False) for y in (-0.42, -0.34, -0.26, -0.18) for sx in (1, -1)]
for o, d, big in rows_lo:
    p, n = project(jaw, o, d)
    b = p - norm((n[0], n[1], 0.0)) * 0.022
    L = 0.09 if big else 0.05
    r = 0.024 if big else 0.017
    teeth.append(Jw(round_cone((b[0], b[1], JAW_Z - 0.025), (b[0], b[1], JAW_Z + L), r, 0.008)))
    bases_lo.append((b[0], b[1], JAW_Z - 0.025))


def row_bar(bases):
    pts = sorted(bases, key=lambda q: math.atan2(q[0], -q[1]))
    return tube(pts, 0.013)


teeth += [row_bar(bases_up), Jw(row_bar(bases_lo))]

# ============================================================ corpo intero
body0 = union(torso, neck, k=0.14)
body0 = fast_union(arms, k=0.06, base=body0)
body0 = fast_union(legs, k=0.07, base=body0)
body0 = fast_union([tail], k=0.06, base=body0)
body0 = body0.intersect(halfspace_z(Z0))
head_w = Hd(head_skin)
print("[anubis] corpo pronto", flush=True)

# ============================================================ gonnellino shendyt plissettato (blu), cintura e grembiule d'oro
KZ0, KZ1 = 1.15, 1.6


def kilt_dims(z):
    t = np.clip((KZ1 - z) / (KZ1 - KZ0), 0.0, 1.0)   # 0 in vita, 1 all'orlo
    return t, 0.33 + 0.24 * t ** 0.85, 0.26 + 0.19 * t ** 0.85, 0.04 - 0.14 * t


def kilt_f(p):
    z = p[:, 2]
    t, rx, ry, cy = kilt_dims(z)
    ang = np.arctan2(p[:, 0], -(p[:, 1] - cy))
    pleat = 1.0 + 0.03 * np.sin(ang * 24.0) * t
    e = np.sqrt((p[:, 0] / rx) ** 2 + ((p[:, 1] - cy) / ry) ** 2)
    d_side = (e - pleat) * np.minimum(rx, ry) * 0.8
    d_cap = np.maximum(KZ0 - z, z - KZ1)
    return np.maximum(d_side, d_cap).astype(np.float32)


kilt = SDF(kilt_f, (-0.64, -0.64, KZ0), (0.64, 0.5, KZ1))
kilt = kilt.subtract(ellipsoid((0.46, 0.34, 0.2), (0, -0.1, KZ0 - 0.07)), k=0.03)   # orlo aperto, non un tappo
waist_core = union(torso, kilt)
belt = paint(waist_core, SDF(lambda p: np.maximum(1.5 - p[:, 2], p[:, 2] - 1.615), (-0.7, -0.7, 1.43), (0.7, 0.7, 1.68)),
             out=0.045, inn=0.03)
HEM_Z = KZ0 + 0.018
hem_pts = []
for ang in np.linspace(-math.pi, math.pi, 97):
    t, rx, ry, cy = kilt_dims(np.float32(HEM_Z))
    r = 1.0 / math.sqrt((math.sin(ang) / rx) ** 2 + (math.cos(ang) / ry) ** 2) * (1.0 + 0.03 * math.sin(ang * 24.0) * t)
    hem_pts.append((r * math.sin(ang), float(cy) - r * math.cos(ang), HEM_Z))
hem = tube(hem_pts, 0.022)


def apron_surface_y(x, z):
    t, rx, ry, cy = kilt_dims(z)
    return cy - ry * np.sqrt(np.clip(1.0 - (x / rx) ** 2, 0.05, 1.0)) * 1.04 - 0.022


AP_TOP, AP_BOT = 1.54, 1.04
AP_POLY = [(-0.14, AP_TOP), (0.14, AP_TOP), (0.21, AP_BOT), (-0.21, AP_BOT)]


def apron_shape(poly, half_t, dy=0.0):
    pr = prism(poly, -1.0, 1.0)

    def f(p):
        q = np.stack([p[:, 0], p[:, 2], np.zeros(len(p), np.float32)], axis=1).astype(np.float32)
        d2 = pr(q)
        ys = apron_surface_y(p[:, 0], np.minimum(p[:, 2], KZ1)) + dy
        return (np.maximum(d2, np.abs(p[:, 1] - ys) - half_t) * 0.85).astype(np.float32)

    xs = [v[0] for v in poly]
    zs = [v[1] for v in poly]
    return SDF(f, (min(xs) - 0.05, -0.8, min(zs) - 0.05), (max(xs) + 0.05, -0.1, max(zs) + 0.05))


apron = apron_shape(AP_POLY, 0.022)
APRON_STRIPES = []
for zc in (1.38, 1.25, 1.12):
    hw = 0.14 + 0.07 * (AP_TOP - zc) / (AP_TOP - AP_BOT) - 0.035
    APRON_STRIPES.append(apron_shape([(-hw, zc - 0.03), (hw, zc - 0.03), (hw, zc + 0.03), (-hw, zc + 0.03)], 0.012,
                                     dy=-0.018))

# ============================================================ collare usekh: base di lapislazzuli, verghe e gocce d'oro
# il collare poggia su una forma liscia (petto + spalle) e i muscoli che sporgono sotto vengono tolti dal corpo
COL_C = np.array([0.0, 0.03, 2.22], dtype=np.float32)
COL_IN, COL_OUT, COL_T = 0.215, 0.5, 0.035
col_proxy = union(ellipsoid((0.47, 0.37, 0.36), (0, 0.02, 2.04)),
                  *[ellipsoid((0.26, 0.26, 0.25), (sx * 0.58, 0.06, 2.16)) for sx in (1, -1)], k=0.14)
col_top = col_proxy.offset(COL_T)


def collar_zone(p, r_in=COL_IN, r_out=COL_OUT):
    q = p - COL_C
    d = np.sqrt(np.einsum("ij,ij->i", q, q))
    rh = np.sqrt(q[:, 0] ** 2 + q[:, 1] ** 2)
    return np.maximum(r_in - rh, d - r_out).astype(np.float32)


ZONE = SDF(collar_zone, COL_C - COL_OUT - 0.05, COL_C + COL_OUT + 0.05)
CARVE = SDF(lambda p: np.maximum(collar_zone(p, COL_IN - 0.02, COL_OUT - 0.005), -col_proxy(p)), ZONE.lo, ZONE.hi)
collar_base = paint(col_proxy, ZONE, out=COL_T, inn=0.03)


def ring_curve(r, n=72):
    """Punti della superficie del collare a distanza r dal centro, tutto intorno al collo."""
    pts = []
    for phi in np.linspace(-math.pi, math.pi, n, endpoint=False):
        def q_of(th, phi=phi):
            return COL_C + r * np.array([math.sin(phi) * math.sin(th), -math.cos(phi) * math.sin(th), -math.cos(th)])
        lo_t, hi_t = 0.0, 0.9 * math.pi
        if col_top(q_of(lo_t)[None, :].astype(np.float32))[0] > 0 or col_top(q_of(hi_t)[None, :].astype(np.float32))[0] < 0:
            continue
        for _ in range(30):
            mid = 0.5 * (lo_t + hi_t)
            if col_top(q_of(mid)[None, :].astype(np.float32))[0] < 0:
                lo_t = mid
            else:
                hi_t = mid
        pts.append((q_of(lo_t), q_of(lo_t + 0.03) - q_of(lo_t - 0.03)))
    return pts


def inner_curve(n=60):
    """Bordo interno del collare (attorno al collo): sulla verticale a distanza COL_IN dall'asse del collo."""
    pts = []
    for phi in np.linspace(-math.pi, math.pi, n, endpoint=False):
        x, y = COL_C[0] + COL_IN * math.sin(phi), COL_C[1] - COL_IN * math.cos(phi)
        lo_z, hi_z = 1.95, 2.7
        for _ in range(30):
            mid = 0.5 * (lo_z + hi_z)
            if col_top(np.array([[x, y, mid]], np.float32))[0] < 0:
                lo_z = mid
            else:
                hi_z = mid
        pts.append(np.array([x, y, lo_z - 0.01]))
    return pts


def closed_tube(pts, r):
    pts = [tuple(float(c) for c in q) for q in pts]
    return tube(pts + [pts[0]], r)


collar_rods = [closed_tube(inner_curve(), 0.026)]
for r, rr in ((0.32, 0.02), (0.41, 0.02), (COL_OUT - 0.005, 0.026)):
    collar_rods.append(closed_tube([q for q, _ in ring_curve(r)], rr))
beads = []
for q, down in ring_curve(COL_OUT + 0.02, n=32):
    nrm = grad(col_top, q)
    down = norm(down - nrm * float(np.dot(down, nrm)))
    a = q + nrm * 0.005
    beads.append(round_cone(tuple(a + down * 0.005), tuple(a + down * 0.085), 0.024, 0.04))

# ============================================================ bracciali d'oro a righe blu
def slab(c, ax, h, reach=0.3):
    c = np.asarray(c, np.float32)
    ax = norm(ax).astype(np.float32)

    def f(p):
        q = p - c
        t = q @ ax
        rad = np.sqrt(np.maximum(np.einsum("ij,ij->i", q, q) - t * t, 0.0))
        return np.maximum(np.abs(t) - h, rad - reach).astype(np.float32)

    return SDF(f, c - reach - h, c + reach + h)


cuffs_gold, cuffs_lapis = [], []
for sx, A in ARMS.items():
    sh, el, wr = (np.array(A[k], float) for k in ("sh", "el", "wr"))
    c = sh + (el - sh) * 0.33
    cuffs_gold.append(paint(arm_sdf[sx], slab(c, el - sh, 0.055), out=0.035, inn=0.03))
    cuffs_lapis.append(paint(arm_sdf[sx], slab(c, el - sh, 0.02), out=0.047, inn=0.03))
    if sx < 0:   # polsiera larga sul braccio destro (il sinistro e' bendato)
        c = el + (wr - el) * 0.7
        cuffs_gold.append(paint(arm_sdf[sx], slab(c, wr - el, 0.085), out=0.035, inn=0.03))
        for dt in (-0.045, 0.045):
            cuffs_lapis.append(paint(arm_sdf[sx], slab(c + norm(wr - el) * dt, wr - el, 0.017), out=0.047, inn=0.03))

# anello d'oro sulla coda
tail_ring = paint(tail, slab(np.array(TAIL_PTS[8]), np.array(TAIL_PTS[9]) - np.array(TAIL_PTS[7]), 0.04, 0.3),
                  out=0.03, inn=0.03)

# ============================================================ bende da mummia sul braccio sinistro (+X)
A = ARMS[1]
SH_L, EL_L, WR_L = (np.array(A[k], float) for k in ("sh", "el", "wr"))


def wraps_region(a, b, turns, width, t0=0.0, t1=1.0, phase=0.0, hint=(0.0, -1.0, 0.0)):
    ax, u, v = limb_frame(a, b, hint)
    a = np.asarray(a, np.float32)
    L = float(np.linalg.norm(np.asarray(b) - np.asarray(a)))
    pitch = L / turns
    axf, uf, vf = (x.astype(np.float32) for x in (ax, u, v))

    def f(p):
        q = p - a
        t = q @ axf
        ang = np.arctan2(q @ vf, q @ uf)
        s = turns * t / L - ang / (2 * math.pi) + phase
        fr = s - np.floor(s) - 0.5
        d_band = (np.abs(fr) - width * 0.5) * pitch * 0.9
        d_ends = np.maximum(t0 * L - t, t - t1 * L)
        rad = np.sqrt(np.maximum(np.einsum("ij,ij->i", q, q) - t * t, 0.0))
        return np.maximum.reduce([d_band, d_ends, rad - 0.3]).astype(np.float32)

    lo = np.minimum(a, b) - 0.35
    hi = np.maximum(a, b) + 0.35
    return SDF(f, lo, hi)


# fasce di benda separate e storte (si vede il pelo nero fra una e l'altra)
WRAPS = [(EL_L, WR_L, t, tilt, h) for t, tilt, h in ((0.12, 14, 0.04), (0.32, -12, 0.036), (0.52, 16, 0.04),
                                                      (0.72, -10, 0.034), (0.9, 12, 0.03))]
WRAPS += [(SH_L, EL_L, t, tilt, h) for t, tilt, h in ((0.52, -14, 0.036), (0.72, 12, 0.04), (0.92, -8, 0.04))]
wraps = []
for a_, b_, t, tilt, h in WRAPS:
    ax, u, v = limb_frame(a_, b_, (0.0, -1.0, 0.0))
    tilted = norm(ax * math.cos(math.radians(tilt)) + u * math.sin(math.radians(tilt)))
    wraps.append(paint(arm_sdf[1], slab(a_ + (b_ - a_) * t, tilted, h, 0.28), out=0.022, inn=0.025))
# lembo di benda che pende dal gomito (striscia piatta: x larga, y sottile, z lungo la striscia)
flap_l = flatten(tube(bezier((0, 0, 0.04), (0.04, 0.0, -0.14), (-0.04, 0.06, -0.3), (0.05, 0.05, -0.46), 9),
                      taper(10, 0.042, 0.034)), 0.24, axis=1)
FLAP_M = frame((0.0, 0.0, 1.0), norm((0.55, -1.0, 0.0)))
flap = flap_l.rotate(FLAP_M).translate(EL_L + np.array([0.06, -0.03, -0.1]))
bandage_parts = wraps + [flap]

# cuciture a croce rosso scuro sulle bende, sul davanti-esterno del braccio
stitches = []
bandaged = fast_union(wraps, base=arm_sdf[1])
for (a_, b_, t) in ((EL_L, WR_L, 0.32), (EL_L, WR_L, 0.72), (SH_L, EL_L, 0.72)):
    ax, u, v = limb_frame(a_, b_, (0.55, -1.0, 0.1))
    c = a_ + (b_ - a_) * t
    surf = on_surface(bandaged, c + u * 0.3, 0.004, 6)
    for sg in (1, -1):
        p0 = on_surface(bandaged, surf - ax * 0.026 * sg - v * 0.03, 0.004, 4)
        p1 = on_surface(bandaged, surf + ax * 0.026 * sg + v * 0.03, 0.004, 4)
        stitches.append(capsule(tuple(p0), tuple(p1), 0.011))

# ============================================================ khopesh (spazio locale: z lungo il manico, la lama si piega verso +x)
KF = np.array(ARMS[1]["fi"], float)
KM = frame(KH_U, (0.0, 1.0, 0.0))     # x verso l'esterno (+X), y dietro, z lungo il manico
ARC_C, ARC_R = np.array([0.29, 0.0, 0.78]), 0.3
arc_pts, arc_r = [(-0.01, 0.0, 0.16), (-0.01, 0.0, 0.52)], [0.048, 0.064]
for j, a in enumerate(np.linspace(180, -58, 15)):
    t = j / 14
    arc_pts.append((ARC_C[0] + ARC_R * math.cos(math.radians(a)), 0.0, ARC_C[2] + ARC_R * math.sin(math.radians(a))))
    arc_r.append(0.092 * (1 - t) ** 0.6 + 0.014 + 0.042 * math.sin(math.pi * min(t * 1.4, 1.0)))
blade_l = flatten(tube(arc_pts, arc_r), 0.28, axis=1)
EDGE_IN = ARC_R + 0.025


def edge_region(p):
    """< 0 sul lato esterno (convesso) della curva della lama, non sul codolo dritto."""
    rho = np.sqrt((p[:, 0] - ARC_C[0]) ** 2 + (p[:, 2] - ARC_C[2]) ** 2)
    on_arc = np.minimum((ARC_C[2] - 0.03) - p[:, 2], 0.4 - p[:, 0])
    return np.maximum(EDGE_IN - rho, on_arc).astype(np.float32)


edge_l = blade_l.offset(0.007).intersect(SDF(edge_region, (-3, -3, -3), (3, 3, 3)))
blade_body_l = blade_l.intersect(SDF(lambda p: -edge_region(p), (-3, -3, -3), (3, 3, 3)))
grip_l = capsule((0, 0, -0.17), (0, 0, 0.13), 0.04)
fittings_l = union(sphere(0.06, (0, 0, -0.21)), ellipsoid((0.09, 0.055, 0.035), (0, 0, 0.155)),
                   torus(0.045, 0.012).translate((0, 0, 0.1)))


def KH(shape):
    return shape.rotate(KM).translate(KF)


# ============================================================ scettro was (asta blu, testa d'animale e forcella d'oro)
STAFF_TOP = 2.98
staff_shaft = capsule((STAFF_X, STAFF_Y, Z0 + 0.2), (STAFF_X, STAFF_Y, STAFF_TOP - 0.05), 0.034)
staff_gold = [round_cone((STAFF_X, STAFF_Y, STAFF_TOP - 0.06), (STAFF_X, STAFF_Y - 0.22, STAFF_TOP + 0.07), 0.052, 0.03),
              capsule((STAFF_X, STAFF_Y + 0.02, STAFF_TOP - 0.03), (STAFF_X, STAFF_Y + 0.05, STAFF_TOP + 0.11), 0.022),
              capsule((STAFF_X, STAFF_Y - 0.05, STAFF_TOP), (STAFF_X, STAFF_Y - 0.03, STAFF_TOP + 0.13), 0.02),
              capsule((STAFF_X, STAFF_Y, Z0 + 0.25), (STAFF_X - 0.07, STAFF_Y, Z0 + 0.02), 0.028),
              capsule((STAFF_X, STAFF_Y, Z0 + 0.25), (STAFF_X + 0.07, STAFF_Y, Z0 + 0.02), 0.028),
              sphere(0.05, (STAFF_X, STAFF_Y, Z0 + 0.25))]
for z in (0.9, 1.3, 2.05, 2.55):
    staff_gold.append(torus(0.042, 0.02, (STAFF_X, STAFF_Y, z)))

# ============================================================ artigli d'oro
claws = []
for tip, fwd, sz in TOES:
    t0 = np.asarray(tip, dtype=np.float64)
    claws.append(horn(t0 + (0, 0, 0.012), t0 + fwd * 0.05 * sz + (0, 0, 0.025 * sz), t0 + fwd * 0.1 * sz,
                      t0 + fwd * 0.13 * sz + (0, 0, -0.04 * sz), 0.04 * sz, 0.012, n=7))

# ============================================================ parti
GS = float(os.environ.get("GS", 0.92))   # scala finale del modello (altezza ~3.45)


def add(name, sdf, color, voxel, **kw):
    m.add(name, sdf.scale(GS) if GS != 1.0 else sdf, color, voxel=voxel * GS * VX, **kw)


add("Body", body0.subtract(CARVE), BLACK, 0.03, tris=2900)
neck_top = round_cone((0, -0.0, 2.34), (0, -0.05, 2.47), 0.17, 0.15)
add("Head", SDF(fast_union([head_w], k=0.08, base=neck_top).f, head_w.lo - 0.1, np.maximum(head_w.hi, neck_top.hi) + 0.1),
    BLACK, 0.022, role="skin", tris=2100)
add("Fists", fast_union(FISTS), BLACK, 0.013, role="skin", tris=700)
print("[anubis] pelle pronta", flush=True)
add("Plinth", plinth, STONE, 0.03, role="detail", tris=400, smooth=False)
staff_gem = union(*[sphere(0.017, (STAFF_X + sx * 0.034, STAFF_Y - 0.13, STAFF_TOP + 0.02)) for sx in (1, -1)])   # occhi dello scettro
add("Glyphs", fast_union(glyphs + [staff_gem]), BLUE_GLOW, 0.0095, material="Neon", role="glow", tris=650)
add("EyeGlow", Hd(union(*eyes)), BLUE_GLOW, 0.012, material="Neon", role="glow", tris=250)
add("Collar", fast_union(collar_rods + beads), GOLD, 0.013, material="Foil", role="detail", tris=1450)
gold = cuffs_gold + [belt, hem, apron, tail_ring] + [KH(fittings_l)] + staff_gold + claws
add("Gold", fast_union(gold), GOLD, 0.02, material="Foil", role="detail", tris=1750)
add("HeadGold", Hd(fast_union(ear_gold + liners)), GOLD, 0.011, material="Foil", role="detail", tris=600)
add("Lapis", fast_union(cuffs_lapis + APRON_STRIPES + [KH(grip_l)]), LAPIS, 0.014, role="detail", tris=700)
add("Kilt", fast_union([kilt, collar_base, staff_shaft] + [Hd(x) for x in ear_lapis]), LAPIS, 0.022, role="detail",
    tris=1500)
add("Khopesh", KH(blade_body_l), BRONZE, 0.014, material="Metal", role="detail", tris=450)
add("Mane", KH(edge_l), EDGE_GLOW, 0.011, material="Neon", role="glow", tris=350)
add("Bandages", fast_union(bandage_parts), LINEN, 0.013, material="Fabric", role="detail", tris=1000)
add("Stitches", fast_union(stitches), THREAD, 0.011, role="detail", tris=250)
add("Mouth", Hd(fast_union(dark)), MOUTH, 0.014, role="eye", tris=350)
add("Teeth", Hd(fast_union(teeth)), TOOTH, 0.011, role="shine", tris=450)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
