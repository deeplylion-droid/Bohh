"""Scarabeo del Sole (SunScarab) - pet del Percorso Estremo (antico Egitto).

Khepri, lo scarabeo che spinge il sole: un enorme scarabeo-gioiello con il carapace turchese lucido
intarsiato d'oro e di lapislazzuli, che si impenna sulle quattro zampe posteriori e solleva sopra la
testa, fra le zampe anteriori dentate, un disco solare incandescente: un grande globo che brucia con
un anello d'oro e una corona di raggi (parte Neon "Flames": il gioco ci attacca il fuoco). Le elitre
sono mezze aperte e da sotto escono le ali membranose di vetro azzurro con le venature d'oro (gruppi
WingL/WingR, il gioco le fa oscillare). Il clipeo dentato d'oro sembra una corona, le antenne finiscono
a ventaglio, gli occhietti brillano come braci del sole e sotto il clipeo ghigna una fila di dentini.
Tocco "toy horror": e' un giocattolo a carica: dalla schiena, fra le elitre aperte, spunta una grossa
chiavetta d'oro con l'impugnatura a forma di ankh, e una toppa ricucita copre una crepa dell'elitra.
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


def slab(c, ax, h, reach=0.3):
    """Fetta fra due piani perpendicolari ad 'ax' (spessore 2h), entro 'reach' dall'asse."""
    c = np.asarray(c, np.float32)
    ax = norm(ax).astype(np.float32)

    def f(p):
        q = p - c
        t = q @ ax
        rad = np.sqrt(np.maximum(np.einsum("ij,ij->i", q, q) - t * t, 0.0))
        return np.maximum(np.abs(t) - h, rad - reach).astype(np.float32)

    return SDF(f, c - reach - h, c + reach + h)


# ============================================================ colori
TURQ = (34, 196, 186)        # carapace turchese
NAVY = (22, 30, 92)          # ventre e addome (blu notte)
GOLD = (255, 200, 70)        # oro (Foil)
LAPIS = (30, 58, 196)        # intarsi di lapislazzuli
SUN_CORE = (255, 238, 150)   # globo del sole e occhietti (Neon)
SUN_FIRE = (255, 112, 24)    # raggi del sole (Neon "Flames")
MEMBRANE = (130, 210, 255)   # ali membranose (vetro)
MOUTH = (40, 10, 30)
TOOTH = (250, 244, 228)
PATCH = (150, 40, 60)        # toppa rosso carminio
THREAD = (250, 236, 200)     # filo chiaro

m = Model("SunScarab", "pet")

# ============================================================ corpo dello scarabeo (spazio locale: orizzontale, testa verso -Y, dorso +Z)
TILT = -34.0                                   # il davanti si alza di 34 gradi
BODY_O = np.array([0.0, 0.12, 1.02])
BS = 1.15                                      # scala del corpo
R_BODY = euler(TILT, 0, 0)


def W(shape):
    """Locale del corpo -> mondo."""
    return shape.scale(BS).rotate(R_BODY).translate(BODY_O)


def wp(p):
    return R_BODY.astype(np.float64) @ (BS * np.asarray(p, dtype=np.float64)) + BODY_O


abdomen = ellipsoid((0.6, 0.78, 0.38), (0, 0.55, -0.05))
thorax = ellipsoid((0.46, 0.38, 0.3), (0, -0.02, -0.08))
pronotum = ellipsoid((0.62, 0.4, 0.36), (0, -0.22, 0.0))
pronotum = pronotum.subtract(ellipsoid((0.32, 0.24, 0.26), (0, -0.66, 0.08)), k=0.05)   # incavo dove sta la testa
head = ellipsoid((0.28, 0.24, 0.17), (0, -0.6, -0.05))
sternites = [ellipsoid((0.55 - 0.05 * j, 0.14, 0.08), (0, 0.25 + 0.2 * j, -0.36 + 0.015 * j)) for j in range(5)]

# elitre: gusci a cupola divisi a meta', aperte di 38 gradi verso l'esterno (cerniera davanti, vicino alla linea di mezzo)
ELY_OUT = ellipsoid((0.65, 0.86, 0.5), (0, 0.58, -0.04))
ELY_IN = ellipsoid((0.58, 0.79, 0.42), (0, 0.58, -0.04))
OPEN = 30.0
HINGE = {sx: np.array([sx * 0.6, 0.3, -0.06]) for sx in (1, -1)}   # cerniera sul bordo esterno: si aprono dal centro


def elytron_local(sx, shape):
    """Porta una forma costruita sull'elitra chiusa (lato sx) nella posizione aperta (a conchiglia, dalla sutura)."""
    return shape.rot(-6.0, sx * OPEN, sx * 6.0, pivot=tuple(HINGE[sx]))


def ely_half(sx):
    side = SDF(lambda p, sx=sx: (0.012 - sx * p[:, 0]).astype(np.float32), (-3, -3, -3), (3, 3, 3))
    bottom = SDF(lambda p: (-0.07 - p[:, 2]).astype(np.float32), (-3, -3, -3), (3, 3, 3))
    return ELY_OUT.subtract(ELY_IN).intersect(side).intersect(bottom)


elytra = [elytron_local(sx, ely_half(sx)) for sx in (1, -1)]

# ---- decorazioni delle elitre (costruite sull'elitra chiusa): bordo e nervature d'oro, intarsio di lapislazzuli


def ely_paint(sx, region_fn, out, inn):
    """Vernice sull'elitra chiusa (solo sulla cupola, sopra il taglio del bordo), poi aperta."""
    reg = SDF(lambda p: np.maximum(region_fn(p), -0.078 - p[:, 2]).astype(np.float32), (-1, -0.4, -0.1), (1, 1.6, 0.6))
    return elytron_local(sx, paint(ELY_OUT, reg, out=out, inn=inn).intersect(
        SDF(lambda p, sx=sx: (0.0 - sx * p[:, 0]).astype(np.float32), (-3, -3, -3), (3, 3, 3))))


ely_gold, ely_lapis, ely_patch = [], [], []
for sx in (1, -1):
    def rim(p, sx=sx):
        d_bot = p[:, 2] - (-0.07 + 0.055)                     # fascia sul bordo esterno-basso
        d_mid = np.maximum(sx * p[:, 0] - (0.012 + 0.05), -0.01 - sx * p[:, 0])   # fascia lungo la sutura
        return np.minimum(d_bot, d_mid).astype(np.float32)
    ely_gold.append(ely_paint(sx, rim, 0.014, 0.075))
    for xc in (0.26, 0.46):                                   # nervature longitudinali
        ely_gold.append(ely_paint(sx, lambda p, sx=sx, xc=xc: (np.abs(sx * p[:, 0] - xc) - 0.017).astype(np.float32),
                                  0.012, 0.02))

    def inlay(p, sx=sx):
        return np.maximum.reduce([np.abs(sx * p[:, 0] - 0.36) - 0.065, np.abs(p[:, 1] - 0.62) - 0.42]).astype(np.float32)
    ely_lapis.append(ely_paint(sx, inlay, 0.008, 0.02))
# toppa carminio ricucita sull'elitra destra (+X, verso la camera 3/4), sopra una crepa
PATCH_C = (0.36, 1.18)   # (x, y) sull'elitra chiusa


def patch_reg(p):
    return np.maximum(np.abs(p[:, 0] - PATCH_C[0]) - 0.1, np.abs(p[:, 1] - PATCH_C[1]) - 0.11).astype(np.float32)


ely_patch.append(ely_paint(1, patch_reg, 0.02, 0.02))
patch_st = []
ELY_R = elytron_local(1, ELY_OUT)
corners = [(-0.1, -0.11), (0.1, -0.11), (0.1, 0.11), (-0.1, 0.11)]
for i in range(4):
    a2, b2 = np.array(corners[i]), np.array(corners[(i + 1) % 4])
    for t in (0.3, 0.7):
        c2 = a2 + (b2 - a2) * t
        tdir = norm(b2 - a2)
        nrm2 = np.array([-tdir[1], tdir[0]])
        for sg in (1, -1):
            e1 = c2 - nrm2 * 0.028 - tdir * 0.018 * sg
            e2 = c2 + nrm2 * 0.028 + tdir * 0.018 * sg
            q1 = project(ELY_OUT, (PATCH_C[0] + e1[0] - 0.2, PATCH_C[1] + e1[1], 0.0), (1.0, 0.0, 1.6))[0]
            q2 = project(ELY_OUT, (PATCH_C[0] + e2[0] - 0.2, PATCH_C[1] + e2[1], 0.0), (1.0, 0.0, 1.6))[0]
            patch_st.append(capsule(tuple(q1), tuple(q2), 0.011))
patch_st = [elytron_local(1, union(*patch_st))]

# ---- pronoto: bordo d'oro, gemma di lapislazzuli incastonata
pron_rim = paint(pronotum, SDF(lambda p: np.maximum(p[:, 2] + 0.01, -0.09 - p[:, 2]).astype(np.float32), (-1, -1, -0.1),
                                (1, 1, 0.0)), out=0.016, inn=0.03)
GEM_P, GEM_N = project(pronotum, (0, -0.2, 0.0), (0, -0.05, 1.0))
gem = ellipsoid((0.15, 0.18, 0.065)).translate(GEM_P - GEM_N * 0.015)
bezel = torus(0.16, 0.024).translate(GEM_P - GEM_N * 0.004)
pron_lines = []
for sx in (1, -1):
    a0 = project(pronotum, (sx * 0.15, -0.2, 0.0), (sx * 0.45, 0.0, 1.0))[0]
    a1 = project(pronotum, (sx * 0.15, -0.2, 0.0), (sx * 1.0, 0.2, 0.45))[0]
    pron_lines.append(capsule(tuple(a0), tuple(a1), 0.02))

# ---- testa: clipeo dentato d'oro (la corona), occhietti accesi, antenne a ventaglio, ghigno di dentini
CLY = []
for a in np.linspace(192, 348, 15):
    k = int(round((a - 192) / (156 / 14)))
    r = 0.42 if (k % 2 == 1 and 1 <= k <= 13) else 0.33
    CLY.append((r * math.cos(math.radians(a)), -0.6 + r * math.sin(math.radians(a))))
CLY += [(0.28, -0.5), (-0.28, -0.5)]
clypeus = prism(CLY, -0.06, 0.0, round=0.016).rot(12, 0, 0, pivot=(0, -0.6, 0.0)).translate((0, 0, 0.03))
eyes = [sphere(0.058, (sx * 0.255, -0.57, -0.07)) for sx in (1, -1)]
antennae = []
for sx in (1, -1):
    a0, a1 = np.array([sx * 0.2, -0.72, -0.09]), np.array([sx * 0.4, -0.84, -0.16])
    antennae.append(capsule(tuple(a0), tuple(a1), 0.024))
    for j, spread in enumerate((-0.5, 0.0, 0.5)):
        dd = norm((sx * 0.6, -0.6 + spread * 0.4, -0.2 + spread * 0.5))
        antennae.append(flatten(ellipsoid((0.03, 0.095, 0.04)), 0.5, axis=0).rotate(frame(dd, (0, 0, 1))).translate(
            a1 + dd * 0.07))
mouth = ellipsoid((0.17, 0.06, 0.04), (0, -0.8, -0.11))
teeth = []
for x in np.linspace(-0.13, 0.13, 7):
    yb = -0.8 - 0.055 * math.sqrt(max(1 - (x / 0.17) ** 2, 0.0))
    teeth.append(round_cone((x, yb + 0.014, -0.1), (x, yb + 0.004, -0.165), 0.018, 0.004))
for sx in (1, -1):   # mandibole a uncino agli angoli
    teeth.append(horn((sx * 0.16, -0.78, -0.1), (sx * 0.21, -0.86, -0.13), (sx * 0.16, -0.94, -0.15),
                      (sx * 0.08, -0.95, -0.16), 0.028, 0.007, n=8))

# ---- chiavetta della carica d'oro (impugnatura ad ankh) piantata nel dorso fra le elitre aperte
KEY_B, KEY_N = project(abdomen, (0, 0.62, -0.05), (0, -0.1, 1.0))
KEY_TOP = KEY_B + KEY_N * 0.32
key = [cylinder(tuple(KEY_B - KEY_N * 0.06), tuple(KEY_TOP), 0.04),
       cylinder(tuple(KEY_B + KEY_N * 0.01), tuple(KEY_B + KEY_N * 0.06), 0.09, round=0.015)]
KM = frame(KEY_N, (1.0, 0.0, 0.0))    # z lungo la chiavetta, y di lato (l'ankh sta nel piano x-z locale)
ankh_loop = torus(0.1, 0.036).rot(90, 0, 0)
ankh_l = union(ankh_loop.translate((0, 0, 0.15)), capsule((-0.17, 0, 0.0), (0.17, 0, 0.0), 0.038),
               capsule((0, 0, -0.18), (0, 0, 0.04), 0.04), k=0.02)
key.append(flatten(ankh_l, 0.7, axis=1).rotate(np.stack([KM[:, 1], KM[:, 0], KM[:, 2]], axis=1)).translate(KEY_TOP + KEY_N * 0.04))

# ============================================================ zampe blu notte con spine d'oro: le anteriori reggono il sole
SUN_C = np.array([0.0, -0.7, 2.42])
SUN_R = 0.38
RING_R = 0.47
leg_shapes, leg_spikes = [], []
for sx in (1, -1):
    cx = wp((sx * 0.28, -0.25, -0.3))
    knee = np.array([sx * 0.7, -0.62, 1.38])
    tib = np.array([sx * 0.6, -0.74, 1.94])
    ga = math.radians(122)
    grip = SUN_C + np.array([sx * (RING_R + 0.02) * math.sin(ga), -0.02, (RING_R + 0.02) * math.cos(ga)])
    leg_shapes.append(tube([tuple(cx), tuple(cx * 0.5 + knee * 0.5 + np.array([sx * 0.08, 0.0, -0.04])), tuple(knee)],
                           [0.12, 0.13, 0.095]))
    leg_shapes.append(tube([tuple(knee), tuple(knee * 0.5 + tib * 0.5 + np.array([sx * 0.05, 0, 0])), tuple(tib)],
                           [0.095, 0.085, 0.07]))
    leg_shapes.append(tube([tuple(tib), tuple(tib * 0.5 + grip * 0.5 + np.array([sx * 0.04, -0.02, 0])), tuple(grip)],
                           [0.05, 0.045, 0.04]))
    leg_shapes += [sphere(0.115, tuple(knee)), sphere(0.08, tuple(tib))]
    ax = norm(tib - knee)
    out = norm(np.array([sx, -0.3, 0.0]) - ax * float(np.dot((sx, -0.3, 0.0), ax)))
    for t, L in ((0.2, 0.13), (0.45, 0.15), (0.7, 0.17), (0.92, 0.15)):   # denti della tibia scavatrice
        b_ = knee + (tib - knee) * t
        leg_spikes.append(round_cone(tuple(b_), tuple(b_ + norm(out + ax * 0.45) * L), 0.04, 0.008))
    for d_ in (np.array([-sx * 0.04, -0.03, 0.08]), np.array([-sx * 0.08, 0.04, 0.06])):   # artigli sull'anello
        leg_spikes.append(horn(grip, grip + d_ * 0.5, grip + d_ + np.array([-sx * 0.03, 0, 0]),
                               grip + d_ * 1.2 + np.array([-sx * 0.05, 0, -0.03]), 0.028, 0.007, n=6))
    # zampe medie (in fuori e avanti) e posteriori (in fuori e indietro)
    for coxa, knee2, foot, toe in (((sx * 0.36, 0.1, -0.32), (sx * 0.86, -0.14, 0.66), (sx * 0.96, -0.36, 0.07),
                                    (sx * 0.99, -0.58, 0.04)),
                                   ((sx * 0.36, 0.42, -0.34), (sx * 0.84, 0.66, 0.58), (sx * 0.92, 0.98, 0.07),
                                    (sx * 0.94, 1.22, 0.04))):
        c0 = wp(coxa)
        k2, f2, t2 = (np.array(v, float) for v in (knee2, foot, toe))
        leg_shapes.append(tube([tuple(c0), tuple(c0 * 0.5 + k2 * 0.5 + np.array([0, 0, 0.08])), tuple(k2)], [0.115, 0.125, 0.095]))
        leg_shapes.append(tube([tuple(k2), tuple(k2 * 0.5 + f2 * 0.5 + np.array([sx * 0.03, 0, 0])), tuple(f2)],
                               [0.09, 0.078, 0.062]))
        leg_shapes.append(tube([tuple(f2), tuple(f2 * 0.5 + t2 * 0.5 + np.array([0, 0, 0.012])), tuple(t2)], [0.05, 0.042, 0.034]))
        leg_shapes += [sphere(0.11, tuple(k2)), sphere(0.065, tuple(f2))]
        ax = norm(f2 - k2)
        side = norm(np.cross(ax, (0.0, 0.0, 1.0)))
        if np.dot(side, (sx, 0, 0)) < 0:
            side = -side
        for t, L in ((0.3, 0.11), (0.62, 0.12), (0.9, 0.1)):
            b_ = k2 + (f2 - k2) * t
            leg_spikes.append(round_cone(tuple(b_), tuple(b_ + norm(side + ax * 0.6) * L), 0.03, 0.006))
        dd = norm(t2 - f2)
        for sg in (1, -1):   # due unghiette in punta
            sd = norm(np.cross(dd, (0, 0, 1))) * sg
            leg_spikes.append(horn(t2, t2 + dd * 0.05 + sd * 0.025, t2 + dd * 0.1 + sd * 0.05,
                                   t2 + dd * 0.12 + sd * 0.06 + np.array([0, 0, -0.03]), 0.026, 0.007, n=5))

# ============================================================ disco solare: globo incandescente, anello d'oro, corona di raggi
sun_core = sphere(SUN_R, tuple(SUN_C))
sun_ring = torus(RING_R, 0.05).rot(90, 0, 0).translate(tuple(SUN_C))
rays = []
for i in range(16):
    a = math.radians(i * 22.5 + 11.25)
    d = np.array([math.sin(a), 0.0, math.cos(a)])
    long_ = i % 2 == 0
    L = 0.36 if long_ else 0.22
    b = SUN_C + d * (RING_R + 0.02)
    ray = round_cone(tuple(b), tuple(b + d * L), 0.075 if long_ else 0.055, 0.012)
    rays.append(flatten(ray.translate(tuple(-SUN_C)), 0.45, axis=1).translate(tuple(SUN_C)))
# seconda corona di raggi piu' corti, sfalsata e un po' dietro (volume)
for i in range(16):
    a_ = math.radians(i * 22.5)
    d = np.array([math.sin(a_), 0.0, math.cos(a_)])
    b_ = SUN_C + d * (RING_R - 0.02) + np.array([0, 0.07, 0])
    ray = round_cone(tuple(b_), tuple(b_ + d * 0.16), 0.05, 0.01)
    rays.append(flatten(ray.translate(tuple(-SUN_C)), 0.5, axis=1).translate(tuple(SUN_C)))

# ============================================================ ali membranose (vetro azzurro) con le venature d'oro
WING_HINGE = np.array([0.2, 0.12, 0.14])          # locale del corpo, lato +X
WD = norm((0.62, 0.62, 0.48))                     # direzione dell'ala (fuori, indietro, in alto), locale
WN0 = np.array([0.15, -0.25, 1.0])                # normale circa in alto
WE = norm(np.cross(WN0, WD))                      # larghezza dell'ala nel suo piano
WN = np.cross(WD, WE)
WING_M = np.stack([WD, WE, WN], axis=1).astype(np.float32)   # x lungo l'ala, y largo, z normale
WING_POLY = [(0.0, -0.06), (0.3, -0.15), (0.75, -0.21), (1.15, -0.2), (1.4, -0.1), (1.48, 0.02), (1.38, 0.15),
             (1.06, 0.25), (0.62, 0.25), (0.25, 0.15), (0.0, 0.06)]
membrane_l = prism(WING_POLY, -0.014, 0.014, round=0.01)
veins_l = [tube([(0.0, -0.04, 0), (0.5, -0.17, 0), (1.12, -0.19, 0), (1.42, -0.08, 0)], [0.045, 0.036, 0.026, 0.014])]
for (ex, ey) in ((1.4, 0.08), (1.18, 0.2), (0.82, 0.24), (0.44, 0.19)):
    veins_l.append(tube([(0.04, 0.0, 0), (ex * 0.5, ey * 0.55 - 0.04, 0), (ex - 0.04, ey - 0.025, 0)], [0.026, 0.019, 0.012]))
veins_l.append(tube([(0.55, -0.17, 0), (0.68, 0.0, 0), (0.76, 0.21, 0)], 0.014))
veins_l.append(tube([(1.0, -0.2, 0), (1.06, 0.0, 0), (1.12, 0.19, 0)], 0.012))


def place_wing(shape, sx):
    s = W(shape.rotate(WING_M).translate(WING_HINGE))
    return s if sx > 0 else s.mirrored()


# ============================================================ parti
GS = float(os.environ.get("GS", 1.0))   # scala finale del modello


def add(name, sdf, color, voxel, **kw):
    if kw.get("pivot") is not None:
        kw["pivot"] = tuple(float(c) * GS for c in kw["pivot"])
    m.add(name, sdf.scale(GS) if GS != 1.0 else sdf, color, voxel=voxel * GS * VX, **kw)


shell = fast_union([W(pronotum), W(head)] + [W(e) for e in elytra], k=0.0)
add("Shell", shell, TURQ, 0.024, role="skin", reflectance=0.12, tris=3000)
belly = W(union(union(abdomen, thorax, k=0.12), *sternites, k=0.04))
add("Belly", belly, NAVY, 0.03, role="detail", tris=1000)
gold = [W(x) for x in ely_gold + [pron_rim, bezel, clypeus] + antennae + pron_lines] + [sun_ring] + [W(k) for k in key]
add("Gold", fast_union(gold), GOLD, 0.016, material="Foil", role="detail", tris=2600)
add("Legs", fast_union(leg_shapes), NAVY, 0.022, role="detail", tris=2000)
add("Spikes", fast_union(leg_spikes), GOLD, 0.014, material="Foil", role="detail", tris=900)
add("Lapis", fast_union([W(x) for x in ely_lapis + [gem]]), LAPIS, 0.016, role="detail", reflectance=0.1, tris=800)
add("SunCore", fast_union([sun_core] + [W(e) for e in eyes]), SUN_CORE, 0.02, material="Neon", role="glow", tris=600)
add("Flames", fast_union(rays), SUN_FIRE, 0.016, material="Neon", role="glow", tris=1300)
add("Mouth", W(mouth), MOUTH, 0.012, role="eye", tris=150)
add("Teeth", W(fast_union(teeth)), TOOTH, 0.008, role="shine", tris=400)
add("Patch", fast_union([W(x) for x in ely_patch]), PATCH, 0.012, material="Fabric", role="detail", tris=200)
add("Stitches", fast_union([W(x) for x in patch_st]), THREAD, 0.008, role="detail", tris=250)
for sx, nm in ((1, "WingR"), (-1, "WingL")):
    hinge_w = wp(WING_HINGE * np.array([sx, 1, 1]))
    add(nm, place_wing(membrane_l, sx), MEMBRANE, 0.016, material="Glass", role="detail", transparency=0.25,
        tris=500, group=nm, pivot=tuple(hinge_w))
    add(nm + "Veins", place_wing(fast_union(veins_l), sx), GOLD, 0.012, material="Foil", role="detail", tris=500,
        group=nm, pivot=tuple(hinge_w))

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
