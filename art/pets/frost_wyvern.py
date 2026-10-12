"""Viverna di Ghiaccio (FrostWyvern) - pet PRIMORDIALE (grotte di cristallo).

Una viverna appollaiata sulle zampe posteriori, artigli piantati a terra e coda avvolta attorno ai
piedi, con le ali alzate in alto sopra la schiena come una vela a V stretta (non spalancate). Il collo
si inarca all'indietro e la testa si sporge verso chi guarda con le fauci spalancate: zanne di
ghiaccio su due file, gola scura e un soffio di gelo che si carica in bocca (parte Neon "Frost": il
gioco ci attacca le scintille di ghiaccio). Scaglie azzurro ghiaccio, ventre blu profondo a placche,
membrane blu notte, corna e stalattiti di ghiaccio lungo collo, schiena e coda, occhi a fessura
luminosi sotto arcate sopraccigliari aggrottate. Tocco "toy horror": una toppa viola cucita a punti
incrociati sulla membrana dell'ala destra.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, box, capsule, ellipsoid, euler, halfspace_z, prism, project,  # noqa: E402
                     rot_matrix, round_cone, smin, sphere, tube, union)
from lib.toy import Model  # noqa: E402


# ============================================================ helper (lib/ non si modifica: copiati/adattati qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


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


def footprint(fx, fy, cy):
    """Ellisse nel piano XY locale (distanza approssimata), per delimitare la bocca."""
    def f(p):
        ex = p[:, 0] / fx
        ey = (p[:, 1] - cy) / fy
        return (np.sqrt(ex * ex + ey * ey) - 1.0) * min(fx, fy)
    return f


def crystal(length, radius, tip=0.32, sides=6):
    """Cristallo sfaccettato lungo +Z (base in z=0): prisma regolare con punta piramidale."""
    normals = np.array([[math.cos(2 * math.pi * i / sides), math.sin(2 * math.pi * i / sides)] for i in range(sides)],
                       dtype=np.float32)
    apothem = radius * math.cos(math.pi / sides)
    z_tip = length * (1 - tip)
    slope = apothem / (length - z_tip)
    k = 1.0 / math.sqrt(1.0 + slope * slope)

    def f(p):
        side = (p[:, :2] @ normals.T).max(axis=1)
        d = np.maximum(side - apothem, (side - apothem + slope * (p[:, 2] - z_tip)) * k)
        return np.maximum(d, -p[:, 2])

    return SDF(f, (-radius, -radius, 0.0), (radius, radius, length))


def orient(shape, base, direction, spin=0.0):
    """Porta l'asse +Z della forma lungo direction, con la base nel punto base."""
    d = norm(direction)
    ax = np.cross([0.0, 0.0, 1.0], d)
    s = float(np.linalg.norm(ax))
    if spin:
        shape = shape.rot(0, 0, spin)
    if s > 1e-6:
        shape = shape.rotate(rot_matrix(ax, math.degrees(math.atan2(s, d[2]))))
    return shape.translate(base)


def icicle(base, d, L, r, spin=0.0, sides=5):
    """Stalattite di ghiaccio sfaccettata (punta lunga) piantata in base lungo d."""
    return orient(crystal(L, r, tip=0.62, sides=sides), base, d, spin=spin)


def polyline(pts):
    pts = np.asarray(pts, dtype=np.float64)
    seg = np.diff(pts, axis=0)
    ln = np.linalg.norm(seg, axis=1)
    return pts, seg, ln, np.concatenate([[0.0], np.cumsum(ln)])


def closest_on(P, p):
    """Per ogni punto: ascissa s del punto piu' vicino della polilinea."""
    pts, seg, ln, cum = P
    best = np.full(len(p), np.inf)
    s_out = np.zeros(len(p))
    for k in range(len(seg)):
        t = np.clip(((p - pts[k]) @ seg[k]) / (ln[k] ** 2), 0.0, 1.0)
        c = pts[k] + t[:, None] * seg[k]
        d = np.linalg.norm(p - c, axis=1)
        msk = d < best
        best[msk] = d[msk]
        s_out[msk] = cum[k] + t[msk] * ln[k]
    return s_out


def plate_band(pts, radius, period, groove):
    """Regione a placche lungo una linea: fascia di raggio 'radius' tagliata da solchi ogni 'period'."""
    P = polyline(pts)
    band = tube([tuple(p) for p in pts], radius)

    def f(p):
        b = band(p)
        s = closest_on(P, p.astype(np.float64))
        g = np.abs(np.mod(s / period, 1.0) - 0.5) * period
        return np.maximum(b, groove * 0.5 - g).astype(np.float32)

    return SDF(f, band.lo, band.hi)


def scallop(a, b, toward, pull=0.36, n=8):
    a, b, c = (np.asarray(v, dtype=np.float64) for v in (a, b, toward))
    mid = (a + b) / 2
    ctrl = mid + (c - mid) * pull
    return [tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * ctrl + t * t * b) for t in np.linspace(0, 1, n + 2)[1:-1]], (a, ctrl, b)


# ============================================================ colori
SCALE = (124, 186, 242)      # scaglie azzurro ghiaccio
ARMOR = (44, 76, 178)        # placche dorsali blu
BELLY = (30, 54, 150)        # ventre blu profondo
MEMBRANE = (36, 44, 128)     # membrane delle ali blu notte
PATCH = (150, 84, 226)       # toppa viola
THREAD = (240, 250, 255)     # filo della toppa
ICE = (196, 240, 255)        # stalattiti, corna, artigli
TOOTH = (236, 252, 255)
MAW = (16, 18, 52)           # gola, pupille
FROST = (90, 244, 255)       # soffio di gelo (Neon)
EYE_GLOW = (70, 236, 255)    # occhi (Neon)

m = Model("FrostWyvern", "pet")

# ============================================================ tronco eretto, appollaiato
torso = union(ellipsoid((0.4, 0.38, 0.5), (0, -0.2, 1.74)).rot(14, 0, 0, pivot=(0, -0.2, 1.74)),   # petto
              ellipsoid((0.43, 0.42, 0.46), (0, 0.04, 1.3)),        # ventre
              ellipsoid((0.42, 0.42, 0.38), (0, 0.3, 0.98)), k=0.3)   # bacino
torso = union(torso, ellipsoid((0.3, 0.24, 0.36), (0, -0.38, 1.66)).rot(14, 0, 0, pivot=(0, -0.38, 1.66)), k=0.15)  # sterno
torso = union(torso, *[ellipsoid((0.2, 0.22, 0.2), (sx * 0.3, -0.04, 1.97)) for sx in (1, -1)], k=0.12)  # attacchi ali

# zampe posteriori digitigrade, accucciate, artigli piantati a terra
TOES = []
legs = []
for sx in (1, -1):
    x = sx * 0.5
    hip, knee, ankle, ball = (sx * 0.36, 0.3, 0.98), (x, -0.16, 0.66), (x * 1.02, 0.26, 0.24), (x * 1.04, -0.08, 0.09)
    parts = [ellipsoid((0.27, 0.4, 0.31), (sx * 0.42, 0.08, 0.82)).rot(30, 0, 0, pivot=(sx * 0.42, 0.08, 0.82)),  # coscia
             round_cone(hip, knee, 0.26, 0.16),
             round_cone(knee, ankle, 0.15, 0.1),
             ellipsoid((0.12, 0.16, 0.2), (x * 1.01, 0.05, 0.48)),   # polpaccio
             round_cone(ankle, ball, 0.1, 0.09),
             ellipsoid((0.17, 0.2, 0.1), ball)]
    for dx, dy in ((-0.15, 0.06), (0.0, 0.0), (0.15, 0.06)):
        tip = (ball[0] + dx, -0.42 + dy, 0.06)
        parts.append(round_cone(ball, tip, 0.075, 0.06))
        TOES.append((tip, norm((dx * 0.8, -1.0, 0.0)), 1.0))
    back = (ball[0] - sx * 0.04, 0.2, 0.06)   # sperone posteriore
    parts.append(round_cone(ball, back, 0.065, 0.05))
    TOES.append((back, norm((-sx * 0.2, 1.0, 0.0)), 0.75))
    legs.append(union(*parts, k=0.06))

# coda che scende a terra e si avvolge attorno al piede destro, fino davanti
TA = [(0.0, 0.5, 0.86), (0.05, 1.0, 0.55), (0.42, 1.2, 0.2), (0.92, 0.95, 0.14)]
TB = [(0.92, 0.95, 0.14), (1.3, 0.72, 0.1), (1.32, 0.1, 0.12), (0.96, -0.32, 0.18)]
TAIL_DENSE = np.array(bezier(*TA, 50) + bezier(*TB, 50)[1:])


def tail_rad(u):
    return 0.3 + (0.06 - 0.3) * u ** 0.85


_ti = list(range(0, len(TAIL_DENSE), 5)) + ([len(TAIL_DENSE) - 1] if (len(TAIL_DENSE) - 1) % 5 else [])
tail = tube([tuple(TAIL_DENSE[i]) for i in _ti], [tail_rad(i / (len(TAIL_DENSE) - 1)) for i in _ti])
TAIL_END = TAIL_DENSE[-1]
TAIL_DIR = norm(TAIL_DENSE[-1] - TAIL_DENSE[-4])

# ============================================================ testa (coordinate locali: nuca nell'origine, muso verso -Y)
HEAD_T = np.array([0.05, -0.78, 2.86])
HS = 1.38
R_HEAD = euler(5.0, 6.0, 14.0)    # muso quasi orizzontale, testa girata e inclinata verso la camera 3/4
GAPE = 50.0
JAW_Z = -0.04
HINGE = (0.0, -0.05, JAW_Z)


def H(s):
    return s.scale(HS).rotate(R_HEAD).translate(HEAD_T)


def hp(p):
    return R_HEAD.astype(np.float64) @ (np.asarray(p, dtype=np.float64) * HS) + HEAD_T


def J(s):
    return s.rot(GAPE, 0, 0, pivot=HINGE)


cran = ellipsoid((0.2, 0.25, 0.17), (0, -0.08, 0.1))
occ = ellipsoid((0.17, 0.15, 0.15), (0, 0.06, 0.09))
muzzle = tbox(-0.16, -0.88, 0.165, 0.085, 0.2, 0.095, JAW_Z - 0.04, JAW_Z - 0.03, 0.04)
nose = ellipsoid((0.09, 0.07, 0.058), (0, -0.84, 0.07))
ridge = capsule((0, -0.24, 0.21), (0, -0.78, 0.115), 0.036)
cheeks = [ellipsoid((0.095, 0.17, 0.08), (sx * 0.17, -0.22, 0.01)) for sx in (1, -1)]
brows = [capsule((sx * 0.05, -0.47, 0.17), (sx * 0.24, -0.21, 0.29), 0.068) for sx in (1, -1)]
mounds = [ellipsoid((0.09, 0.075, 0.08), (sx * 0.15, -0.36, 0.12)) for sx in (1, -1)]
upper = union(cran, occ, k=0.12)
upper = union(upper, muzzle, k=0.12)
upper = union(upper, nose, ridge, k=0.06)
upper = union(upper, *cheeks, k=0.07)
upper = union(upper, *mounds, k=0.05)
upper = union(upper, *brows, k=0.045)
upper = upper.subtract(union(*[ellipsoid((0.028, 0.045, 0.022)).rot(0, sx * 30, 0).translate((sx * 0.055, -0.89, 0.095))
                               for sx in (1, -1)]), k=0.015)                      # narici
upper = upper.subtract(box((0.6, 0.5, 0.3), (0, HINGE[1] - 0.5, JAW_Z - 0.3)), k=0.012)
jaw = union(tbox(-0.02, -0.84, 0.155, 0.08, JAW_Z + 0.05, JAW_Z + 0.05, -0.18, -0.12, 0.04),
            ellipsoid((0.16, 0.14, 0.1), (0, -0.06, -0.1)),
            ellipsoid((0.065, 0.07, 0.05), (0, -0.78, -0.13)), k=0.06)
jaw = jaw.subtract(box((0.6, 0.6, 0.3), (0, -0.4, JAW_Z + 0.3)), k=0.012)

# occhi a mandorla luminosi con pupilla a fessura e palpebra arrabbiata
eye_glow, dark, lids = [], [], []
for sx in (1, -1):
    p, n = project(upper, (sx * 0.15, -0.36, 0.12), (sx * 0.62, -0.78, 0.06))
    a1 = sx * norm(np.cross((0.0, 0.0, 1.0), n))
    a2 = -sx * n
    a3 = np.cross(a1, a2)
    sl = math.radians(22)
    a1, a3 = a1 * math.cos(sl) + a3 * math.sin(sl), a3 * math.cos(sl) - a1 * math.sin(sl)
    M = np.stack([a1, a2, a3], axis=1).astype(np.float32)
    c = p - n * 0.022
    eye = ellipsoid((0.105, 0.055, 0.044)).rotate(M).translate(c)
    eye_glow.append(eye)
    dark.append(ellipsoid((0.122, 0.04, 0.078)).rotate(M).translate(p - n * 0.036))
    dark.append(thin(eye, 0.006, 0.02).intersect(ellipsoid((0.016, 0.2, 0.046)).rotate(M).translate(c)))
    cutp = SDF(lambda q: (-0.004 + 0.5 * q[:, 0] - q[:, 2]) / math.sqrt(1 + 0.5 ** 2), (-0.14, -0.14, -0.14),
               (0.14, 0.14, 0.14))
    lids.append(ellipsoid((0.11, 0.066, 0.064)).intersect(cutp).rotate(M).translate(c))

# bocca: palato e mandibola scuri, gola, soffio di gelo che si carica
pal_fp, jaw_fp = footprint(0.1, 0.36, -0.48), footprint(0.09, 0.34, -0.46)
pal_reg = SDF(lambda p: np.maximum(pal_fp(p), p[:, 2] - (JAW_Z + 0.03)), (-0.11, -0.8, JAW_Z - 0.05),
              (0.11, -0.12, JAW_Z + 0.03))
jaw_reg = SDF(lambda p: np.maximum(jaw_fp(p), (JAW_Z - 0.03) - p[:, 2]), (-0.1, -0.76, JAW_Z - 0.03),
              (0.1, -0.12, JAW_Z + 0.05))
dark.append(shell_paint(upper, pal_reg, out=0.006, inn=0.03, margin=0.02))
dark.append(J(shell_paint(jaw, jaw_reg, out=0.006, inn=0.03, margin=0.02)))
Rinv = euler(-GAPE, 0, 0)
_piv = np.asarray(HINGE, dtype=np.float32)
_thr = footprint(0.13, 0.1, -0.1)


def wedge(p):
    q = (p - _piv) @ Rinv.T + _piv
    return np.maximum(np.maximum(p[:, 2] - (JAW_Z + 0.004), (JAW_Z - 0.004) - q[:, 2]), _thr(p))


dark.append(SDF(wedge, (-0.13, -0.21, JAW_Z - 0.3), (0.13, 0.04, JAW_Z + 0.01)))
frost = []
for yg, rk in ((-0.27, 0.5), (-0.42, 0.36)):
    gap = (HINGE[1] - yg) * math.tan(math.radians(GAPE))
    frost.append(ellipsoid((min(0.11, rk * gap), min(0.13, rk * gap * 1.2), min(0.11, rk * gap)),
                           (0, yg, JAW_Z - gap * 0.5)))

# denti di ghiaccio su due file, zanne grandi davanti
teeth = []
rows_up = [((0, -0.7, JAW_Z + 0.012), (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0), abs(a) > 45)
           for a in np.linspace(-60, 60, 5)]
rows_up += [((0, y, JAW_Z + 0.012), (sx, 0, 0), y > -0.45) for y in (-0.5, -0.36, -0.22) for sx in (1, -1)]
for o, d, big in rows_up:
    p, n = project(upper, o, d)
    b = p - norm((n[0], n[1], 0.0)) * 0.024
    L = 0.17 if big else 0.09
    r = 0.04 if big else 0.028
    teeth.append(round_cone((b[0], b[1], JAW_Z + 0.025), (b[0], b[1], JAW_Z - L), r, 0.004))
rows_lo = [((0, -0.66, JAW_Z - 0.012), (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0), abs(a) > 35)
           for a in np.linspace(-50, 50, 3)]
rows_lo += [((0, y, JAW_Z - 0.012), (sx, 0, 0), False) for y in (-0.42, -0.27) for sx in (1, -1)]
for o, d, big in rows_lo:
    p, n = project(jaw, o, d)
    b = p - norm((n[0], n[1], 0.0)) * 0.024
    L = 0.13 if big else 0.075
    r = 0.034 if big else 0.026
    teeth.append(J(round_cone((b[0], b[1], JAW_Z - 0.025), (b[0], b[1], JAW_Z + L), r, 0.004)))

# corna di ghiaccio all'indietro, speroni della mandibola, cresta di stalattiti sul cranio
head_ice = []
for sx in (1, -1):
    b = np.array([sx * 0.1, 0.0, 0.24])
    head_ice.append(horn(b, b + (sx * 0.07, 0.24, 0.14), b + (sx * 0.19, 0.56, 0.18), b + (sx * 0.29, 0.86, 0.42),
                         0.094, 0.012, n=16))
    bb = np.array([sx * 0.2, -0.26, 0.27])   # spuntone sopra l'arcata, piegato all'indietro
    head_ice.append(horn(bb, bb + (sx * 0.03, 0.06, 0.07), bb + (sx * 0.07, 0.13, 0.11), bb + (sx * 0.1, 0.22, 0.14),
                         0.045, 0.01, n=8))
    b2 = np.array([sx * 0.19, 0.0, 0.07])
    head_ice.append(horn(b2, b2 + (sx * 0.13, 0.12, -0.02), b2 + (sx * 0.24, 0.24, 0.0), b2 + (sx * 0.33, 0.34, 0.08),
                         0.05, 0.012))
    jb = np.array([sx * 0.14, -0.08, -0.12])
    head_ice.append(J(horn(jb, jb + (sx * 0.08, 0.08, -0.03), jb + (sx * 0.13, 0.16, -0.05),
                           jb + (sx * 0.18, 0.24, -0.04), 0.042, 0.012, n=8)))
    for j, (y, z, L) in enumerate(((-0.16, 0.0, 0.2), (-0.02, -0.03, 0.24))):  # frangia sulle guance
        p, n = project(upper, (sx * 0.08, y, z), (sx, 0.25, 0.1))
        head_ice.append(icicle(p - n * 0.02, n + np.array([0, 0.9, 0.15]), L, 0.045, spin=20 * j))
for y, z, L in ((-0.12, 0.25, 0.16), (0.04, 0.26, 0.2)):
    head_ice.append(icicle((0, y, z - 0.04), (0, 0.55, 1.0), L, 0.055, sides=4))
head_ice.append(horn((0, -0.72, 0.1), (0, -0.76, 0.2), (0, -0.74, 0.27), (0, -0.67, 0.32), 0.05, 0.011, n=8))   # corno sul naso

skin_head = union(upper, J(jaw), *lids, k=0.012)

# ============================================================ collo inarcato all'indietro
NECK_SOCKET = (0.0, 0.12, -0.02)
P3n = hp(NECK_SOCKET)
P2n = P3n + R_HEAD.astype(np.float64) @ norm((0, 0.72, -0.69)) * 0.55
P0n = np.array([0.0, -0.22, 1.9])
P1n = P0n + norm((0.0, 0.3, 1.0)) * 0.62
NR0, NR1 = 0.27, 0.15 * HS


def neck_rad(u):
    return NR1 + (NR0 - NR1) * (1.0 - u) ** 2


NECK_DENSE = np.array(bezier(P0n, P1n, P2n, P3n, 120))
neck = tube(bezier(P0n, P1n, P2n, P3n, 16), [neck_rad(i / 16) for i in range(17)])
_us = np.linspace(0.84, 1.0, 5)
_pts = [tuple(float(c) for c in (1 - u) ** 3 * P0n + 3 * (1 - u) ** 2 * u * P1n + 3 * (1 - u) * u ** 2 * P2n + u ** 3 * P3n)
        for u in _us]
neck_end = tube(_pts, [neck_rad(u) - 0.012 + 0.02 * min(max((u - 0.84) / 0.06, 0.0), 1.0) for u in _us])

core = union(torso, neck, k=0.14)
core = fast_union(legs, k=0.1, base=core)
core = union(core, tail, k=0.12)
core = core.intersect(halfspace_z(0.0))
m.add("Body", core, SCALE, tris=3700, voxel=0.0354)
m.add("Head", union(neck_end, H(skin_head), k=0.07 * HS), SCALE, role="skin", tris=2300, voxel=0.026)

# ============================================================ ventre blu profondo a placche (petto, pancia, gola)
fan = [(0, -math.cos(math.radians(a)), math.sin(math.radians(a))) for a in np.linspace(-62, 58, 18)]
v_pts = []
for d in fan:
    p, n = project(torso, (0, 0.05, 1.45), d)
    if p[2] > 1.0:
        v_pts.append(p)
neck_info, _ = along(NECK_DENSE, neck_rad, np.linspace(0.12, 0.93, 12), (0, -1.0, -0.6))
n_pts = [c + f * r for c, tan, f, r in neck_info]
belly_reg = union(plate_band(v_pts, 0.28, 0.2, 0.026), plate_band(n_pts, 0.12, 0.14, 0.022))
m.add("Belly", shell_paint(union(torso, neck, k=0.14), belly_reg, out=0.022, inn=0.075), BELLY, role="detail", tris=950,
      voxel=0.034)

# ============================================================ placche dorsali blu: schiena, collo, coda e cresta del cranio
fan_b = [(0, math.cos(math.radians(a)), math.sin(math.radians(a))) for a in np.linspace(-40, 72, 16)]
b_pts = []
for d in fan_b:
    p, n = project(torso, (0, 0.05, 1.45), d)
    if p[2] > 0.95:
        b_pts.append(p)
b_pts = b_pts[::-1]   # dall'alto in basso
neck_b, _ = along(NECK_DENSE, neck_rad, np.linspace(0.1, 0.9, 12), (0, -1.0, -0.6))
nb_pts = [c - f * r for c, tan, f, r in neck_b]
tail_b, _ = along(TAIL_DENSE, tail_rad, np.linspace(0.02, 0.9, 22), (0, 0, -1))
tb_pts = [c - f * r for c, tan, f, r in tail_b]
armor_reg = union(plate_band(b_pts, 0.22, 0.17, 0.03), plate_band(nb_pts, 0.12, 0.13, 0.026))
armor = [shell_paint(union(torso, neck, k=0.14), armor_reg, out=0.022, inn=0.075),
         shell_paint(tail, plate_band(tb_pts, 0.13, 0.15, 0.028), out=0.022, inn=0.075)]
head_stripe = tube([(0, -0.7, 0.16), (0, -0.5, 0.22), (0, -0.25, 0.28), (0, 0.0, 0.27), (0, 0.12, 0.2)], 0.07)
armor.append(H(shell_paint(upper, head_stripe, out=0.016, inn=0.06)))
m.add("Armor", fast_union(armor), ARMOR, role="detail", tris=1400, voxel=0.0375)

# ============================================================ ali alzate sopra la schiena (piano XZ, poi inclinate)
WS = (0.36, 2.0)      # spalla (perno dell'animazione)
WE = (0.86, 2.66)     # gomito
WW = (0.8, 3.42)      # polso, alto sopra la testa
WF = [(1.3, 3.95), (1.66, 3.3), (1.56, 2.48), (1.12, 1.82)]  # punte delle dita
WB = (0.44, 1.38)     # attacco sul fianco
WT = 0.045            # meta' spessore della membrana
PIVOT_Y = 0.02


def wing_dy(x, z):
    return 0.34 * (x - WS[0]) / 1.3 + 0.1 * (z - WS[1])   # piano: la decimazione non lascia striature


def wing_warp(shape):
    """Porta una forma costruita sul piano piatto dell'ala (y=0) sull'ala inclinata all'indietro."""
    def f(p):
        q = p.copy()
        q[:, 1] = q[:, 1] - PIVOT_Y - wing_dy(q[:, 0], q[:, 2])
        return shape(q)

    lo, hi = shape.lo.copy(), shape.hi.copy()
    lo[1] += PIVOT_Y - 0.1
    hi[1] += PIVOT_Y + 0.65
    return SDF(f, lo, hi)


EDGES = [scallop(WF[0], WF[1], WW), scallop(WF[1], WF[2], WW), scallop(WF[2], WF[3], WW), scallop(WF[3], WB, WE, pull=0.3)]
WING_POLY = [WS, WE, WW, WF[0]] + EDGES[0][0] + [WF[1]] + EDGES[1][0] + [WF[2]] + EDGES[2][0] + [WF[3]] + EDGES[3][0] + [WB]


def notch(edge, t, w, depth):
    """Strappo a V nel bordo d'uscita (triangolo da sottrarre, nel piano dell'ala)."""
    a, c, b = edge[1]
    p = (1 - t) ** 2 * a + 2 * (1 - t) * t * c + t * t * b
    d = norm(2 * (1 - t) * (c - a) + 2 * t * (b - c))
    inward = norm(np.asarray(WW) - p)
    return prism([tuple(p - d * w - inward * 0.08), tuple(p + d * w - inward * 0.08), tuple(p + inward * depth + d * w * 0.4)],
                 -1.0, 1.0)


def P3(xz, y=0.0):
    return (float(xz[0]), y, float(xz[1]))


arm = union(tube([P3(WS), P3(WE)], [0.095, 0.078]), tube([P3(WE), P3(WW)], [0.08, 0.064]),
            sphere(0.095, P3(WE)), sphere(0.085, P3(WW)), k=0.03)
fingers = []
for i, tip in enumerate(WF):
    a, b = np.array(WW, dtype=np.float64), np.array(tip, dtype=np.float64)
    dd = b - a
    perp = np.array([dd[1], -dd[0]]) / np.linalg.norm(dd)
    bow = 0.0 if i == 0 else 0.05
    pts = bezier(P3(a), P3(a + dd * 0.35 + perp * bow), P3(a + dd * 0.7 + perp * bow), P3(b), 8)
    fingers.append(tube(pts, taper(9, 0.06 - 0.004 * i, 0.022)))
wing_bones = union(arm, *fingers, k=0.03)

wing_claws = [horn(P3(WW, -0.02), (WW[0] - 0.02, -0.07, WW[1] + 0.12), (WW[0] - 0.09, -0.12, WW[1] + 0.22),
                   (WW[0] - 0.18, -0.14, WW[1] + 0.24), 0.056, 0.012, n=8)]       # pollice uncinato
for tip in WF:
    dd = norm(np.array(tip) - np.array(WW))
    tp = np.array(tip)
    wing_claws.append(horn(P3(tp - dd * 0.03), P3(tp + dd * 0.05), P3(tp + dd * 0.1 + np.array([dd[1], -dd[0]]) * 0.03),
                           P3(tp + dd * 0.14 + np.array([dd[1], -dd[0]]) * 0.07), 0.036, 0.01, n=6))

for (a2, b2), ts in (((WS, WE), (0.45,)), ((WE, WW), (0.3, 0.65))):   # spuntoni di ghiaccio sul braccio
    for t in ts:
        a2v, b2v = np.array(a2, dtype=np.float64), np.array(b2, dtype=np.float64)
        q = a2v + (b2v - a2v) * t
        dd = norm(b2v - a2v)
        out = np.array([-dd[1], dd[0]])        # verso l'interno-alto del braccio (lato opposto alla membrana)
        if out[0] > 0:
            out = -out
        tip_dir = norm(np.array([out[0], -0.35, out[1]]) + np.array([dd[0], 0.0, dd[1]]) * 0.6)
        wing_claws.append(icicle(np.array(P3(q)) - tip_dir * 0.03, tip_dir, 0.2, 0.05, sides=4))
NOTCH_R = [notch(EDGES[2], 0.5, 0.07, 0.18), notch(EDGES[0], 0.62, 0.045, 0.13)]
NOTCH_L = [notch(EDGES[1], 0.42, 0.075, 0.2), notch(EDGES[3], 0.55, 0.05, 0.22), notch(EDGES[0], 0.7, 0.04, 0.12)]

# toppa cucita (ala destra, verso la camera 3/4): rettangolo viola su entrambe le facce, punti incrociati
PC, PHW, PHH, PANG = (1.22, 3.06), 0.21, 0.155, 22.0
_ca, _sa = math.cos(math.radians(PANG)), math.sin(math.radians(PANG))
PATCH_RECT = [(PC[0] + x * _ca - y * _sa, PC[1] + x * _sa + y * _ca)
              for x, y in ((-PHW, -PHH), (PHW, -PHH), (PHW, PHH), (-PHW, PHH))]
stitches = []
_line = resample([np.array(v) for v in PATCH_RECT + [PATCH_RECT[0]]], 0.118)
for i in range(len(_line) - 1):   # punti incrociati sulla faccia davanti (quella che si vede)
    tdir = norm(_line[i + 1] - _line[i])
    side = np.array([-tdir[1], tdir[0]]) * 0.04
    zf = WT + 0.016
    for sg in (1, -1):   # due trattini a X
        a, b = _line[i] - side + tdir * 0.028 * sg, _line[i] + side - tdir * 0.028 * sg
        stitches.append(capsule((a[0], a[1], zf), (b[0], b[1], zf), 0.017))

for sx, nm in ((1, "WingR"), (-1, "WingL")):
    piv = (sx * WS[0], PIVOT_Y, WS[1])
    flat = prism(WING_POLY, -WT, WT, round=WT * 0.9).subtract(union(*(NOTCH_R if sx > 0 else NOTCH_L)))
    mem = wing_warp(flat.rot(90, 0, 0))
    bones_w = wing_warp(wing_bones)
    claws_w = wing_warp(union(*wing_claws))
    if sx > 0:
        claws_w = union(claws_w, wing_warp(fast_union(stitches).rot(90, 0, 0)))
        patch = wing_warp(flat.offset(0.013).intersect(prism(PATCH_RECT, -1.0, 1.0)).rot(90, 0, 0))
    mir = (lambda q: q) if sx > 0 else (lambda q: q.mirrored())
    m.add(nm, mir(mem), MEMBRANE, role="detail", tris=750, voxel=0.038, group=nm, pivot=piv, smooth=False)
    m.add(nm + "Bone", mir(bones_w), SCALE, role="skin", tris=500, voxel=0.035, group=nm, pivot=piv)
    m.add(nm + "Claw", mir(claws_w), ICE, role="detail", tris=620 if sx > 0 else 260,
          voxel=0.0195 if sx > 0 else 0.0232, group=nm, pivot=piv)
    if sx > 0:
        m.add("WingRPatch", mir(patch), PATCH, role="detail", tris=220, voxel=0.03, group=nm, pivot=piv, smooth=False)

# ============================================================ stalattiti di ghiaccio: schiena, collo, coda, corna
ice = [H(s) for s in head_ice]
for y0, z, L in ((-0.05, 1.92, 0.5), (0.04, 1.68, 0.56), (0.12, 1.44, 0.5), (0.22, 1.2, 0.4)):
    p, n = project(torso, (0, y0, z), (0, 1.0, 0.25))
    d = norm(n + np.array([0, 0.3, 0.75]))
    ice.append(icicle(p - d * 0.06, d, L, 0.1, spin=z * 50))
info, _ = along(NECK_DENSE, neck_rad, np.linspace(0.2, 0.84, 5), (0, -1.0, -0.6))
for j, (c, tan, f, r) in enumerate(info):
    d = norm(-f - tan * 0.45)
    ice.append(icicle(c - f * (r - 0.05), d, 0.34 - 0.025 * j, 0.075, spin=30 * j))
info, _ = along(TAIL_DENSE, tail_rad, np.linspace(0.06, 0.82, 7), (0, 0, -1))
for j, (c, tan, f, r) in enumerate(info):
    d = norm(-f + tan * 0.5)
    ice.append(icicle(c - f * (r - 0.04), d, 0.32 - 0.015 * j, 0.085 - 0.003 * j, spin=25 * j))
# lama di ghiaccio in punta alla coda
ice.append(orient(crystal(0.42, 0.11, tip=0.55, sides=4), TAIL_END - TAIL_DIR * 0.05, TAIL_DIR + np.array([0, 0, 0.45])))
for sg in (1, -1):
    side = norm(np.cross(TAIL_DIR, (0, 0, 1))) * sg
    ice.append(icicle(TAIL_END - TAIL_DIR * 0.06, side + TAIL_DIR * 0.5 + np.array([0, 0, 0.5]), 0.24, 0.06))
m.add("Icicles", fast_union(ice), ICE, material="Ice", role="detail", tris=1500, voxel=0.0353, smooth=False)

# ============================================================ denti, artigli, bocca, gelo, occhi
m.add("Teeth", H(fast_union(teeth)), TOOTH, role="shine", tris=550, voxel=0.0233)
claws = []
for tip, fwd, sz in TOES:
    t0 = np.asarray(tip, dtype=np.float64)
    claws.append(horn(t0 + (0, 0, 0.02), t0 + fwd * 0.09 * sz + (0, 0, 0.04 * sz), t0 + fwd * 0.17 * sz + (0, 0, 0.0),
                      t0 + fwd * 0.21 * sz + (0, 0, -0.055 * sz), 0.062 * sz, 0.012, n=8))
m.add("Claws", fast_union(claws).intersect(halfspace_z(0.003)), ICE, role="detail", tris=380, voxel=0.0236)
m.add("Maw", H(fast_union(dark)), MAW, role="eye", tris=400, voxel=0.0356)
m.add("Frost", H(union(*frost)), FROST, material="Neon", role="glow", tris=300, voxel=0.027)


def frost_vein(base, origin, pts, r0=0.032, r1=0.016):
    """Vena di gelo: polilinea proiettata sulla superficie (da un punto interno) che si assottiglia."""
    o = np.asarray(origin, dtype=np.float64)
    out = []
    for q in pts:
        p, n = project(base, o, np.asarray(q, dtype=np.float64) - o)
        out.append(tuple(p - n * r0 * 0.3))
    return tube(out, taper(len(out), r0, r1))


veins = []
for sx in (1, -1):
    X = lambda q, sx=sx: (sx * q[0], q[1], q[2])   # noqa: E731
    # coscia: crepa ramificata dal fianco al ginocchio
    o = X((0.42, 0.08, 0.82))
    veins.append(frost_vein(core, o, [X(q) for q in ((0.62, 0.3, 1.04), (0.68, 0.19, 0.94), (0.69, 0.1, 0.97), (0.71, 0.0, 0.86),
                                                      (0.7, -0.08, 0.88), (0.67, -0.17, 0.76))]))
    veins.append(frost_vein(core, o, [X(q) for q in ((0.69, 0.1, 0.97), (0.68, 0.05, 1.06), (0.65, -0.03, 1.09))], 0.026))
    veins.append(frost_vein(core, o, [X(q) for q in ((0.71, 0.0, 0.86), (0.7, 0.07, 0.75), (0.68, 0.01, 0.67))], 0.026))
    # fianco del petto
    o = (0.0, 0.0, 1.6)
    veins.append(frost_vein(core, o, [X(q) for q in ((0.36, -0.12, 1.98), (0.41, -0.06, 1.86), (0.43, -0.11, 1.74),
                                                      (0.46, -0.03, 1.62), (0.47, -0.07, 1.5), (0.46, 0.03, 1.4))]))
    veins.append(frost_vein(core, o, [X(q) for q in ((0.43, -0.11, 1.74), (0.4, -0.2, 1.67), (0.36, -0.27, 1.6))], 0.026))
m.add("IceGlow", union(H(union(*eye_glow)), fast_union(veins)), EYE_GLOW, material="Neon", role="glow", tris=520,
      voxel=0.0242)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
