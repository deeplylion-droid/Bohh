"""Scorpione d'Acciaio (IronScorpion) - pet Primordiale.

(bozza: la descrizione definitiva arriva alla fine)
"""
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, box, capsule, cylinder, ellipsoid, round_cone, smax, smin, sphere,  # noqa: E402
                     torus, tube, union)
from lib.toy import Model  # noqa: E402

DRAFT = os.environ.get("DRAFT", "") == "1"
VX = 1.5 if DRAFT else 1.0  # bozza: voxel piu' grossi per iterare in fretta
T0 = time.time()


def log(msg):
    print(f"[scorpion {time.time() - T0:6.1f}s] {msg}", flush=True)


# ============================================================ palette (Canyon)
SAND = (232, 178, 90)       # corazza color sabbia dorata
RUST = (160, 52, 24)        # creste, anelli della coda, spine, zampe, dita delle chele
BLACK = (34, 26, 30)        # articolazioni, mandibole, punte, pungiglione
GOLD = (255, 190, 40)       # rivetti, gabbia del bulbo e chiave (Metal)
BONE = (246, 234, 204)      # denti, artigli, spine
VENOM = (124, 255, 36)      # veleno (Neon)
EYE_G = (198, 255, 52)      # occhi (Neon)
SOCKET = (14, 8, 12)
WHITE = (255, 255, 255)


# ============================================================ helper (lib/ non si modifica: definiti qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


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


def spheres(centers, radii):
    """Tante sfere in un colpo solo (albero KD): rivetti, regioni delle articolazioni."""
    C = np.asarray(centers, dtype=np.float32)
    R = np.asarray(radii, dtype=np.float32)
    tree = cKDTree(C)
    k = min(4, len(C))

    def f(p):
        d, i = tree.query(p, k=k)
        if k == 1:
            d, i = d[:, None], i[:, None]
        return np.min(d - R[i], axis=1).astype(np.float32)

    return SDF(f, C.min(0) - R.max(), C.max(0) + R.max())


def normal_at(sdf, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float32)
    g = np.array([sdf((p + e)[None, :])[0] - sdf((p - e)[None, :])[0] for e in np.eye(3, dtype=np.float32) * eps])
    return g / max(np.linalg.norm(g), 1e-9)


def proj(sdf, origin, direction, max_dist=2.5, n=500):
    """Punto della superficie lungo il raggio (origin deve essere dentro) e normale uscente."""
    o = np.asarray(origin, dtype=np.float64)
    d = norm(direction)
    ts = np.linspace(0.0, max_dist, n)
    vals = sdf((o[None, :] + ts[:, None] * d[None, :]).astype(np.float32))
    idx = np.nonzero(vals > 0)[0]
    if vals[0] > 0 or len(idx) == 0:
        raise ValueError(f"proj: raggio da {o} non valido")
    lo_t, hi_t = ts[max(idx[0] - 1, 0)], ts[idx[0]]
    for _ in range(24):
        mid = 0.5 * (lo_t + hi_t)
        if sdf((o + mid * d)[None, :].astype(np.float32))[0] > 0:
            hi_t = mid
        else:
            lo_t = mid
    p = o + 0.5 * (lo_t + hi_t) * d
    return p, normal_at(sdf, p)


def basis(fwd, up):
    """Colonne: X locale (lato), Y locale (avanti = fwd), Z locale (su, ortogonalizzato)."""
    y = norm(fwd)
    z = norm(np.asarray(up, float) - y * float(np.dot(up, y)))
    x = np.cross(y, z)
    return np.stack([x, y, z], axis=1).astype(np.float32)


def place(shape, M, origin):
    return shape.rotate(M).translate(tuple(np.asarray(origin, dtype=np.float64)))


def halfspace(fn, lo=(-9, -9, -9), hi=(9, 9, 9)):
    return SDF(fn, lo, hi)


def inside(region):
    """Parte della forma dentro la regione (taglio netto)."""
    return lambda shape: SDF(lambda p: np.maximum(shape(p), region(p)), shape.lo, shape.hi)


def outside(region):
    return lambda shape: SDF(lambda p: np.maximum(shape(p), -region(p)), shape.lo, shape.hi)


def spindle(a, b, ra, rm, rb, at=0.42):
    """Segmento a fuso (piu' grosso verso l'attaccatura, stretto alle articolazioni)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    mid = a + (b - a) * at
    return union(round_cone(tuple(a), tuple(mid), ra, rm), round_cone(tuple(mid), tuple(b), rm, rb))


def hang_drop(top, length, r_top, r_drop):
    """Goccia appesa (filo che si gonfia in una lacrima) sotto il punto top."""
    top = np.asarray(top, float)
    c = top + np.array([0.0, 0.0, -length])
    return union(round_cone(tuple(top), tuple(c + np.array([0, 0, r_drop * 0.6])), r_top, r_drop * 0.7),
                 sphere(r_drop, tuple(c)), k=0.025)


def bow_2d(u, v, lobe_x, lobe_r, hole_r, bar):
    """Impugnatura della chiave a farfalla (piano u, v): due lobi forati uniti da un ponte."""
    d_l = np.sqrt((np.abs(u) - lobe_x) ** 2 + v ** 2) - lobe_r
    d_bar = np.maximum(np.abs(u) - lobe_x, np.abs(v) - bar)
    d = np.minimum(d_l, d_bar)
    d_hole = np.sqrt((np.abs(u) - lobe_x - 0.02) ** 2 + v ** 2) - hole_r
    return np.maximum(d, -d_hole)


def extrude_y(d2, half, rnd=0.02):
    """Estrusione lungo Y locale (bordi arrotondati) di una distanza 2D nel piano XZ."""
    def f(p):
        a = d2(p[:, 0], p[:, 2]) + rnd
        b = np.abs(p[:, 1]) - half + rnd
        return np.minimum(np.maximum(a, b), 0.0) + np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2) - rnd
    return f


# ============================================================ modello
m = Model("IronScorpion", "pet", voxel=0.024 * VX)
GROUND = halfspace(lambda p: -p[:, 2], (-9, -9, 0), (9, 9, 9))   # niente sotto il terreno

# ------------------------------------------------------------ corpo: prosoma (testa-torace) + mesosoma (7 placche)
PRO = ellipsoid((0.58, 0.6, 0.3), (0, -0.62, 0.9))
MESO = ellipsoid((0.72, 0.8, 0.34), (0, 0.36, 0.9))
MESO_END = ellipsoid((0.4, 0.34, 0.27), (0, 1.02, 0.97))
core = union(PRO, MESO, MESO_END, k=0.26)

# carapace: scudo a cupola con il bordo rialzato, la tacca davanti e il tubercolo degli occhi
SKIRT_P = 0.78
car = ellipsoid((0.66, 0.68, 0.36), (0, -0.62, 0.86)).intersect(
    halfspace(lambda p: np.maximum(SKIRT_P - p[:, 2], p[:, 1] + 0.2)), k=0.035)
car = car.subtract(ellipsoid((0.15, 0.2, 0.24), (0, -1.32, 1.02)), k=0.05)
TUB_C = np.array([0.0, -0.84, 1.22])
car = union(car, ellipsoid((0.31, 0.25, 0.14), tuple(TUB_C)), k=0.08)

# placche del mesosoma: ogni placca e' piu' alta dietro (embricate come tegole)
YB = [-0.24, -0.04, 0.16, 0.35, 0.53, 0.7, 0.86, 1.1]
GAP = 0.02
SKIRT_M = 0.72


def plate_off(t):
    return 0.03 + 0.07 * t ** 1.6


def plates_f(p):
    c = core(p)
    y = p[:, 1]
    d = c.copy()
    for i in range(len(YB) - 1):
        y0, y1 = YB[i] + GAP, YB[i + 1] - GAP
        t = np.clip((y - y0) / (y1 - y0), 0.0, 1.0)
        dp = smax(smax(c - plate_off(t), np.abs(y - 0.5 * (y0 + y1)) - 0.5 * (y1 - y0), 0.018), SKIRT_M - p[:, 2], 0.03)
        d = np.minimum(d, dp)
    return d


body = SDF(plates_f, core.lo - 0.12, core.hi + 0.12)


def plate_top(y, x=0.0, lift=0.0):
    """Punto sulla superficie della placca e normale."""
    p, n = proj(body, (x * 0.6, y, 0.85), (x * 1.6, 0.0, 1.0))
    return p + n * lift, n


# creste ruggine: chiglia centrale di ogni placca + una spina ai lati (corazza spinosa)
trim = []
for i in range(len(YB) - 1):
    y0, y1 = YB[i] + GAP + 0.03, YB[i + 1] - GAP - 0.01
    a, na = plate_top(y0)
    b, nb = plate_top(y1)
    trim.append(capsule(tuple(a - na * 0.025), tuple(b + nb * 0.02), 0.05))
    for sx in (1, -1):
        q, n = proj(body, (sx * 0.3, y1 - 0.03, 0.9), (sx, 0.0, 0.32))
        d = norm(n + np.array([0.0, 0.55, 0.25]))
        L = 0.17 if i < 6 else 0.12
        trim.append(round_cone(tuple(q - n * 0.04), tuple(q + d * L), 0.06, 0.012))
# bordo rialzato del carapace (dall'angolo posteriore sinistro, attorno al muso, all'angolo destro)
rim_pts = []
for th in np.radians(np.linspace(-80, 80, 25)):
    q, n = proj(car, (0.0, -0.62, 0.9), (math.sin(th), -math.cos(th), -0.12))
    rim_pts.append(q - n * 0.012)
trim.append(tube([tuple(q) for q in rim_pts[:10]], 0.05))
trim.append(tube([tuple(q) for q in rim_pts[15:]], 0.05))
# creste del carapace che partono dal tubercolo
for sx in (1, -1):
    trim.append(tube([(sx * 0.12, -0.74, 1.27), (sx * 0.24, -0.5, 1.22), (sx * 0.3, -0.26, 1.15)], [0.05, 0.048, 0.04]))
log("corpo pronto")

# ------------------------------------------------------------ coda: 5 segmenti telescopici inarcati sopra il dorso
TAIL_L = [0.5, 0.53, 0.55, 0.57, 0.6]
TAIL_A = [70, 95, 120, 146, 174]
TAIL_W = [0.34, 0.32, 0.3, 0.29, 0.28]
TAIL_H = [0.3, 0.29, 0.28, 0.27, 0.26]
TAIL_DX = [-0.06, -0.14, -0.18, -0.16, -0.1]     # la coda piega un po' a sinistra (bilancia la chiave)
P = [np.array([0.0, 1.0, 0.98])]
for L, a, dx in zip(TAIL_L, TAIL_A, TAIL_DX):
    P.append(P[-1] + norm((dx, math.cos(math.radians(a)), math.sin(math.radians(a)))) * L)
SEG_M = [basis(P[i + 1] - P[i], (0.0, math.sin(math.radians(a)), -math.cos(math.radians(a))))
         for i, a in enumerate(TAIL_A)]
RIM_T = 0.12
tail_armor, tail_rust = [], []
for i, (L, w, h) in enumerate(zip(TAIL_L, TAIL_W, TAIL_H)):
    M = SEG_M[i]
    y0 = 0.07 if i else -0.1          # fra i segmenti resta una fessura da cui brilla il veleno
    seg = box((w, (L - y0) / 2, h), (0, (L + y0) / 2, 0), round=0.17)
    keels = union(*[capsule((sx * w * 0.5, 0.1, h * 0.92), (sx * w * 0.5, L - 0.08, h * 0.96), 0.055) for sx in (1, -1)])
    seg = union(seg, keels, k=0.04)
    cut = L - RIM_T
    tail_armor.append(place(seg.intersect(halfspace(lambda p, c=cut: p[:, 1] - c)), M, P[i]))
    rim = seg.offset(0.035).intersect(halfspace(lambda p, c=cut: np.maximum(c - p[:, 1], p[:, 1] - L)))
    tail_rust.append(place(rim, M, P[i]))
    for sx in (1, -1):
        tail_rust.append(place(round_cone((sx * w * 0.52, L - 0.1, h * 0.96), (sx * w * 0.66, L + 0.07, h + 0.17),
                                          0.065, 0.012), M, P[i]))

# fra un segmento e l'altro brilla il veleno: dischi luminosi nelle fessure (parte "VenomJoints", senza particelle)
joint_glow = []
for i in range(1, 6):
    t_prev = norm(P[i] - P[i - 1])
    t_next = norm(P[i + 1] - P[i]) if i < 5 else t_prev
    ax = norm(t_prev + t_next)
    r = 0.78 * min(TAIL_W[min(i, 4)], TAIL_H[min(i, 4)])
    joint_glow.append(cylinder(tuple(P[i] - ax * 0.04), tuple(P[i] + ax * 0.12), r, round=0.03))

# telson: bulbo di veleno luminoso in una gabbia d'oro, con il pungiglione nero ricurvo
A6 = 205.0
M6 = basis((-0.05, math.cos(math.radians(A6)), math.sin(math.radians(A6))),
           (0.0, math.sin(math.radians(A6)), -math.cos(math.radians(A6))))
BULB_R = (0.29, 0.35, 0.29)
BULB_C = (0.0, 0.34, 0.0)
bulb = place(ellipsoid(BULB_R, BULB_C), M6, P[5])
cage = []
for alpha in (-62.0, 0.0, 62.0, 180.0):
    pts = []
    for v in np.radians(np.linspace(-64, 76, 12)):
        pts.append((BULB_R[0] * 1.01 * math.cos(v) * math.sin(math.radians(alpha)),
                    BULB_C[1] + BULB_R[1] * 1.01 * math.sin(v),
                    BULB_R[2] * 1.01 * math.cos(v) * math.cos(math.radians(alpha))))
    cage.append(tube(pts, 0.036))
collar = torus(0.24, 0.055).rot(90, 0, 0).translate((0, 0.04, 0))
cage = place(union(*cage, collar, k=0.02), M6, P[5])
sting_pts = bezier((0, 0.62, -0.02), (0, 0.86, -0.05), (0, 1.0, -0.22), (0, 0.96, -0.46), 12)
sting = place(tube(sting_pts, [0.12 * (1 - i / 12) ** 0.9 + 0.01 for i in range(13)]), M6, P[5])
STING_TIP = P[5] + M6 @ np.array(sting_pts[-1], dtype=np.float32)
log("coda pronta")

# ------------------------------------------------------------ chiave a molla d'oro, piantata di sbieco nel dorso
KEY_BASE, KEY_N = plate_top(0.4, 0.26)
KEY_D = norm((0.6, 0.22, 0.77))
CAM = norm((0.62, -1.0, 0.42))
KEY_M = basis(CAM - KEY_D * float(CAM @ KEY_D), KEY_D)     # Y = normale della farfalla, Z = gambo
BOW_Z = 0.8
key_local = union(
    cylinder((0, 0, -0.12), (0, 0, 0.04), 0.17, round=0.03),         # rondella
    cylinder((0, 0, 0.0), (0, 0, 0.58), 0.075),                       # gambo
    sphere(0.105, (0, 0, 0.54)),                                      # mozzo
    k=0.02)
bow = SDF(extrude_y(lambda u, v: bow_2d(u, v - BOW_Z, 0.25, 0.23, 0.1, 0.12), 0.065, 0.028),
          (-0.5, -0.08, BOW_Z - 0.26), (0.5, 0.08, BOW_Z + 0.26))
key = place(union(key_local, bow, k=0.03), KEY_M, KEY_BASE - KEY_N * 0.02)
log("chiave pronta")

# ------------------------------------------------------------ chele (pedipalpi) enormi, alzate e aperte verso chi guarda
PALP_J = [(0.24, -1.0, 0.86), (0.56, -1.08, 0.95), (1.0, -0.96, 1.18), (1.1, -1.18, 1.42)]
HAND_R = (0.27, 0.44, 0.35)     # (spessore, lunghezza, larghezza) nel sistema della mano
palp_armor, palp_caps, fingers, finger_tips, finger_teeth, hand_keels, palp_rivets = [], [], [], [], [], [], []
for sx in (1, -1):
    J = [np.array([sx * x, y, z]) for x, y, z in PALP_J]
    arm = union(round_cone(tuple(J[0]), tuple(J[1]), 0.15, 0.14), spindle(J[1], J[2], 0.14, 0.17, 0.13),
                spindle(J[2], J[3], 0.14, 0.18, 0.15, at=0.55))
    caps = spheres([J[1], J[2], J[3]], [0.175, 0.17, 0.185])
    A = norm((0.12 * sx, -0.45, 0.88))
    M = basis(A, (sx, 0.0, 0.0))        # Y locale = asse della mano (in alto), Z locale = verso l'esterno
    hand = union(ellipsoid(HAND_R, (0, 0.4, 0.0)), ellipsoid((0.2, 0.22, 0.24), (0, 0.08, 0.0)), k=0.1)
    hand_w = place(hand, M, J[3])
    caps = SDF(lambda p, c=caps, h=hand_w: np.maximum(c(p), -h(p)), caps.lo, caps.hi)
    palp_armor.append(outside(caps)(arm))
    palp_caps.append(inside(caps)(arm))
    palp_armor.append(hand_w)
    hand_keels.append(place(union(capsule((0, 0.16, 0.34), (0, 0.66, 0.3), 0.06),
                                  capsule((0, 0.16, -0.34), (0, 0.66, -0.3), 0.06),
                                  *[round_cone((0, v, 0.33), (0, v + 0.1, 0.47), 0.05, 0.01) for v in (0.2, 0.38, 0.56)]),
                            M, J[3]))
    for a_, b_, t_ in ((J[1], J[2], 0.5), (J[2], J[3], 0.45)):
        q = a_ + (b_ - a_) * t_
        d_ = norm(np.array([sx * 0.4, 0.3, 1.0]))
        hand_keels.append(round_cone(tuple(q + d_ * 0.1), tuple(q + d_ * 0.32), 0.055, 0.01))
    # dito fisso (esterno, quasi in asse) e dito mobile (interno, spalancato): punte nere, denti d'osso
    fixed = bezier((0, 0.62, 0.12), (0, 0.95, 0.24), (0, 1.27, 0.2), (0, 1.45, 0.0), 12)
    movable = bezier((0, 0.6, -0.13), (0, 0.92, -0.22), (0, 1.2, -0.17), (0, 1.35, 0.0), 12)
    fr = [0.14 * (1 - i / 12) ** 0.85 + 0.02 for i in range(13)]
    teeth_f, teeth_m = [], []
    for j in (3, 5, 7, 9):
        q = np.array(fixed[j])
        teeth_f.append(round_cone(tuple(q - (0, 0, fr[j] * 0.55)), tuple(q + (0, 0.035, -fr[j] * 0.55 - 0.11)), 0.05,
                                  0.007))
        q = np.array(movable[j])
        teeth_m.append(round_cone(tuple(q + (0, 0, fr[j] * 0.5)), tuple(q + (0, 0.035, fr[j] * 0.5 + 0.1)), 0.048,
                                  0.007))
    OPEN = -34.0
    hinge = (0, 0.6, -0.13)
    f_fix = tube(fixed, fr)
    f_mov = tube(movable, [r * 0.96 for r in fr]).rot(OPEN, 0, 0, pivot=hinge)
    tip_fix = halfspace(lambda p: 1.24 - p[:, 1])                      # punte nere
    tip_mov = halfspace(lambda p: 1.15 - p[:, 1]).rot(OPEN, 0, 0, pivot=hinge)
    fingers.append(place(union(outside(tip_fix)(f_fix), outside(tip_mov)(f_mov)), M, J[3]))
    finger_tips.append(place(union(inside(tip_fix)(f_fix), inside(tip_mov)(f_mov)), M, J[3]))
    finger_teeth.append(place(union(*teeth_f, *[t.rot(OPEN, 0, 0, pivot=hinge) for t in teeth_m]), M, J[3]))
    for v in (0.24, 0.52):
        for face in (-1.0, 1.0):
            c_w = J[3] + M @ np.array([0.0, v, 0.0], dtype=np.float32)
            p_, n_ = proj(hand_w, c_w, M @ np.array([face, 0.0, 0.0], dtype=np.float32))
            palp_rivets.append((p_, 0.054))
log("chele pronte")

# ------------------------------------------------------------ cheliceri: mandibole uncinate e seghettate
mand, mand_teeth = [], []
for sx in (1, -1):
    base = np.array([sx * 0.15, -1.12, 0.9])
    mid = np.array([sx * 0.18, -1.32, 0.84])
    mand.append(union(sphere(0.13, tuple(base)), round_cone(tuple(base), tuple(mid), 0.125, 0.11), k=0.03))
    hook = bezier(tuple(mid), (sx * 0.25, -1.48, 0.8), (sx * 0.17, -1.6, 0.74), (sx * 0.02, -1.58, 0.68), 8)
    hr = [0.1 * (1 - i / 8) ** 0.8 + 0.014 for i in range(9)]
    mand.append(tube(hook[:7], hr[:7]))
    mand_teeth.append(tube(hook[5:], [r + 0.004 for r in hr[5:]]))
    for j in (2, 4, 6):
        q = np.array(hook[j])
        tdir = norm(np.array([-sx, -0.25, 0.1]))
        mand_teeth.append(round_cone(tuple(q + tdir * 0.035), tuple(q + tdir * 0.115), 0.03, 0.005))
log("mandibole pronte")

# ------------------------------------------------------------ zampe: 4 paia robuste, ginocchia nere, artigli d'osso
LEGS = [
    [(0.3, -0.88, 0.76), (0.56, -0.98, 0.78), (0.86, -1.1, 1.04), (1.08, -1.3, 0.46), (1.16, -1.42, 0.015)],
    [(0.34, -0.66, 0.74), (0.62, -0.72, 0.76), (1.0, -0.8, 1.07), (1.32, -0.95, 0.46), (1.42, -1.03, 0.015)],
    [(0.34, -0.42, 0.72), (0.62, -0.4, 0.74), (1.04, -0.3, 1.07), (1.39, -0.15, 0.46), (1.49, -0.09, 0.015)],
    [(0.32, -0.2, 0.7), (0.6, -0.1, 0.72), (0.98, 0.17, 1.03), (1.27, 0.52, 0.46), (1.35, 0.65, 0.015)],
]
leg_segs, leg_joints_c, leg_joints_r, leg_bone = [], [], [], []
for sx in (1, -1):
    for li, pts in enumerate(LEGS):
        J = [np.array([sx * x, y, z]) for x, y, z in pts]
        c = J[3] + (J[4] - J[3]) * 0.5
        leg_segs.append(union(round_cone(tuple(J[0]), tuple(J[1]), 0.12, 0.115), spindle(J[1], J[2], 0.11, 0.125, 0.098),
                              spindle(J[2], J[3], 0.098, 0.105, 0.08), round_cone(tuple(J[3]), tuple(c), 0.078, 0.062)))
        leg_bone.append(round_cone(tuple(c), tuple(J[4]), 0.062, 0.014))
        leg_joints_c += [J[1], J[2], J[3]]
        leg_joints_r += [0.145, 0.125, 0.104]
        # spine d'osso sul femore (verso l'alto e in fuori)
        for t, L in ((0.42, 0.13), (0.72, 0.11)):
            q = J[1] + (J[2] - J[1]) * t
            d = norm(np.array([sx * 0.6, 0.0, 1.0]) + norm(J[2] - J[1]) * 0.5)
            leg_bone.append(round_cone(tuple(q + d * 0.07), tuple(q + d * (0.11 + L)), 0.04, 0.007))
legs_all = fast_union(leg_segs).intersect(GROUND)
leg_caps = spheres(leg_joints_c, leg_joints_r)
log("zampe pronte")

# ------------------------------------------------------------ occhi: 2 grandi a mandorla sul tubercolo + 3 per lato
def below_line(cut, slope=0.0):
    """Semispazio sotto la retta z = cut + slope*x (coordinate locali dell'occhio): taglia la palpebra."""
    nrm = math.sqrt(1.0 + slope * slope)
    return SDF(lambda p: (p[:, 2] - cut - slope * p[:, 0]) / nrm, (-1, -1, -1), (1, 1, 1))


eye_glow, sockets, shines, brows = [], [], [], []
for sx in (1, -1):
    p, n = proj(car, TUB_C, (sx * 0.5, -0.85, 0.2))
    Me = basis(n, (0, 0, 1))      # Y locale = normale uscente, Z in alto, X verso sinistra (vista da fuori)
    c = p - n * 0.035
    slope, cut = -sx * 0.5, 0.03
    eye = ellipsoid((0.155, 0.09, 0.105)).rot(0, sx * 16, 0).intersect(below_line(cut, slope), k=0.012)
    eye_glow.append(place(eye, Me, c))
    sockets.append(place(ellipsoid((0.19, 0.075, 0.14)).rot(0, sx * 16, 0).intersect(below_line(cut + 0.035, slope),
                                                                                       k=0.012), Me, c - n * 0.03))
    shines.append(place(sphere(0.036), Me, c + n * 0.078 + Me[:, 0] * 0.045 - Me[:, 2] * 0.01))
    # sopracciglio a V (cattivo): cresta nera sul taglio della palpebra, piu' bassa verso il centro
    x0, x1 = -sx * 0.19, sx * 0.15
    brows.append(place(capsule((x0, 0.03, cut + slope * x0 + 0.045), (x1, 0.03, cut + slope * x1 + 0.04), 0.05), Me, c))
    for j, (dx, dz, r) in enumerate(((0.62, 0.12, 0.07), (0.5, 0.36, 0.058), (0.78, -0.08, 0.052))):
        p, n = proj(car, (sx * 0.2, -0.86, 1.04), (sx * dx, -0.8, dz))
        eye_glow.append(sphere(r, tuple(p - n * r * 0.3)))
        sockets.append(sphere(r * 1.3, tuple(p - n * r * 0.55)))
        shines.append(sphere(r * 0.3, tuple(p + n * r * 0.62 + np.array([0, 0, r * 0.35]))))
# corna ricurve dietro gli occhi e spuntoni agli angoli del carapace (ruggine)
for sx in (1, -1):
    p, n = proj(car, (sx * 0.15, -0.6, 1.0), (sx * 0.45, 0.05, 1.0))
    horn = bezier(tuple(p - n * 0.06), tuple(p + np.array([sx * 0.12, 0.08, 0.26])),
                  tuple(p + np.array([sx * 0.24, 0.26, 0.42])), tuple(p + np.array([sx * 0.3, 0.5, 0.46])), 10)
    trim.append(tube(horn, [0.1 * (1 - i / 10) ** 0.9 + 0.012 for i in range(11)]))
    p, n = proj(car, (sx * 0.2, -0.9, 0.9), (sx * 0.8, -0.6, 0.0))
    trim.append(round_cone(tuple(p - n * 0.05), tuple(p + norm(n + np.array([0, -0.6, 0.1])) * 0.2), 0.07, 0.012))
log("occhi pronti")

# ------------------------------------------------------------ rivetti d'oro
rivets = list(palp_rivets)
for i in range(len(YB) - 1):
    y = YB[i] + GAP + 0.07
    xr = 0.42 if i < 6 else 0.22
    for sx in (1, -1):
        p, n = plate_top(y, sx * xr)
        rivets.append((p, 0.052))
for x, y in ((0.3, -1.04), (0.48, -0.52)):
    for sx in (1, -1):
        p, n = proj(car, (sx * x * 0.5, y, 0.95), (sx * 0.6, 0.0, 1.0))
        rivets.append((p, 0.056))
for i, (L, w, h) in enumerate(zip(TAIL_L, TAIL_W, TAIL_H)):
    for sx in (1, -1):
        rivets.append((P[i] + SEG_M[i] @ np.array([sx * (w + 0.005), L * 0.38, 0.0], dtype=np.float32), 0.052))
log(f"rivetti: {len(rivets)}")

# ------------------------------------------------------------ veleno: bulbo luminoso, goccia appesa al pungiglione
venom = [bulb, sphere(0.046, tuple(STING_TIP + np.array([0, 0, -0.01]))),
         hang_drop(STING_TIP + np.array([0, 0, -0.02]), 0.22, 0.03, 0.064)]
BULB_LOW = P[5] + M6 @ np.array([0.0, BULB_C[1], -BULB_R[2] * 0.97], dtype=np.float32)
venom.append(hang_drop(BULB_LOW + np.array([0, 0, 0.02]), 0.13, 0.026, 0.048))
fall = STING_TIP + np.array([0.0, 0.0, -0.56])
venom.append(union(sphere(0.052, tuple(fall)), round_cone(tuple(fall), tuple(fall + [0, 0, 0.1]), 0.048, 0.009), k=0.02))

# ------------------------------------------------------------ parti
m.add("Armor", fast_union([body, car, fast_union(tail_armor), fast_union(palp_armor)]), SAND, tris=5500,
      voxel=0.039)
m.add("RustTrim", fast_union(trim + tail_rust + hand_keels), RUST, role="detail", tris=2000, voxel=0.044)
m.add("Legs", outside(leg_caps)(legs_all), RUST, role="detail", tris=1400, voxel=0.05)
m.add("PincerFingers", fast_union(fingers), RUST, role="detail", tris=900, voxel=0.034)
chitin = [inside(leg_caps)(legs_all), *palp_caps, *finger_tips, sting, *mand, *brows]
m.add("Chitin", fast_union(chitin), BLACK, role="detail", tris=1100, voxel=0.052)
m.add("BoneTips", fast_union(finger_teeth + mand_teeth + leg_bone).intersect(GROUND), BONE, role="detail", tris=850,
      voxel=0.03)
m.add("Rivets", union(spheres([c for c, _ in rivets], [r for _, r in rivets]), cage), GOLD, material="Metal",
      role="detail", tris=800, voxel=0.035)
m.add("WindUpKey", key, GOLD, material="Metal", role="detail", tris=600, voxel=0.034)
m.add("Venom", fast_union(venom), VENOM, material="Neon", role="glow", tris=700, voxel=0.029)
m.add("VenomJoints", fast_union(joint_glow), VENOM, material="Neon", role="glow", tris=300, voxel=0.04)
m.add("EyeGlow", fast_union(eye_glow), EYE_G, material="Neon", role="glow", tris=480, voxel=0.02)
m.add("EyeSockets", fast_union(sockets), SOCKET, role="eye", tris=300, voxel=0.029)
m.add("Shine", fast_union(shines), WHITE, role="shine", tris=140, voxel=0.012)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
    log("fatto")
