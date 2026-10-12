"""Cobra Reale (KingCobra) - pet Primordiale (zona Canyon).

Un cobra gigantesco che si erge dalle sue spire: il corpo nero carbone con bande ocra a V e' arrotolato in una spirale
compatta a due giri, il collo si alza dritto, corazzato da grandi squame ventrali color sabbia, e si apre in un
cappuccio enorme e concavo: davanti e' d'oro con le costole nere a raggiera e il bordo nero, dietro ha due occhi finti
ocra a mandorla, cattivi, come un secondo sguardo. La testa e' protesa verso chi guarda con la bocca spalancata
(rosso scuro), due lunghe zanne d'osso che grondano veleno verde luminoso, la lingua biforcuta che guizza fuori, occhi
verdi luminosi con la pupilla a fessura sotto creste nere e tre grandi placche d'oro sulla testa: la corona del re.
Tocco "toy horror": il cappuccio e' cucito al collo con grandi punti a X color osso lungo una cucitura nera.

Il veleno che gocciola dalle zanne e' nell'unica parte "Venom" (Neon): il gioco ci attacca le particelle verdi.
"""
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import SDF, bezier, capsule, ellipsoid, round_cone, smax, smin, sphere, tube, union  # noqa: E402
from lib.toy import Model  # noqa: E402

T0 = time.time()


def log(msg):
    print(f"[cobra {time.time() - T0:6.1f}s] {msg}", flush=True)


# ============================================================ palette (Canyon)
SKIN = (46, 38, 48)         # pelle nero-carbone (con una punta di viola: il nero puro in gioco e' piatto)
BAND = (224, 150, 40)       # bande a V color ocra
GOLD = (250, 186, 44)       # faccia del cappuccio
BELLY = (238, 204, 138)     # scaglie ventrali color sabbia
BLACK = (24, 18, 26)        # disegni del cappuccio, sopracciglia, cucitura
THREAD = (246, 232, 200)    # filo delle cuciture
MOUTH = (112, 18, 38)       # bocca rosso scuro
TONGUE = (196, 40, 46)
BONE = (248, 240, 220)      # zanne
VENOM = (124, 255, 36)      # veleno (Neon)
EYE_G = (200, 255, 50)      # occhi (Neon)
PUPIL = (10, 6, 12)
WHITE = (255, 255, 255)


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


def paint(base, region, d=0.02, depth=0.03, k=0.0):
    """Vernice a strato sottile (fra -depth e +d dalla superficie) ritagliata dalla regione."""
    t = (d + depth) / 2
    return base.offset(d - t).shell(t).intersect(region, k=k)


def hang_drop(top, length, r_top, r_drop):
    """Goccia appesa (filo che si gonfia in una lacrima) sotto il punto top."""
    top = np.asarray(top, float)
    c = top + np.array([0.0, 0.0, -length])
    return union(round_cone(tuple(top), tuple(c + np.array([0, 0, r_drop * 0.6])), r_top, r_drop * 0.7),
                 sphere(r_drop, tuple(c)), k=0.025)


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
    out = np.array([np.interp(ss, cum, pts[:, k]) for k in range(3)]).T
    return out, ss


def poly2d(pts):
    """Distanza con segno da un poligono 2D: f(u, v)."""
    pts = np.asarray(pts, dtype=np.float32)

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


# ============================================================ modello
m = Model("KingCobra", "pet", voxel=0.03)
GROUND = halfspace(lambda p: -p[:, 2], (-9, -9, 0), (9, 9, 9))

# ------------------------------------------------------------ spina dorsale: spirale a terra + collo che si alza
COIL_C = np.array([0.0, 0.22])
PHI0, PHI1 = -12.0, 598.0


def coil_pt(u):
    phi = math.radians(PHI0 + (PHI1 - PHI0) * u)
    r = 1.06 - 0.44 * u
    rad = 0.06 + 0.3 * float(smoothstep(0.0, 0.3, u)) - 0.035 * u
    z = rad * 0.86 + 0.53 * float(smoothstep(0.42, 0.66, u))
    return np.array([COIL_C[0] + r * math.cos(phi), COIL_C[1] + 1.07 * r * math.sin(phi), z]), rad


CTRL, CTRL_R = [], []
for u in np.linspace(0.0, 1.0, 37):
    q, r = coil_pt(u)
    CTRL.append(q)
    CTRL_R.append(r)
CTRL[0] = CTRL[0] + np.array([0.06, 0.05, 0.12])     # punta della coda che si arriccia in su
# il collo si alza davanti alla spirale, piega in avanti in cima (testa protesa verso chi guarda)
RISE = [((0.02, -0.52, 0.92), 0.315), ((0.12, -0.5, 1.28), 0.3), ((0.08, -0.38, 1.66), 0.29),
        ((0.0, -0.27, 2.05), 0.28), ((0.0, -0.21, 2.45), 0.27), ((0.0, -0.24, 2.8), 0.255), ((0.0, -0.38, 3.03), 0.235)]
for q, r in RISE:
    CTRL.append(np.array(q))
    CTRL_R.append(r)
dense = catmull(CTRL, 10)
# raggi: interpolati lungo i punti di controllo
dr = np.repeat(np.asarray(CTRL_R[:-1]), 10)
dr = np.concatenate([dr, [CTRL_R[-1]]])
_cum = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(dense, axis=0), axis=1))])
SPINE, S = resample(dense, 0.02)
RAD = np.interp(S, _cum, np.convolve(np.pad(dr, 5, mode="edge"), np.ones(11) / 11, mode="valid"))
S_LEN = float(S[-1])
TAN = np.gradient(SPINE, axis=0)
TAN /= np.linalg.norm(TAN, axis=1, keepdims=True)
S_RISE = float(S[np.argmin(np.linalg.norm(SPINE - np.array(RISE[0][0]), axis=1))])   # inizio del collo
# direzione dorsale: in alto sulla spirale, all'indietro sul collo
_w = smoothstep(S_RISE - 0.3, S_RISE + 0.5, S)[:, None]
_up = (1 - _w) * np.array([0.0, 0.0, 1.0]) + _w * np.array([0.0, 1.0, 0.0])
DOR = _up - TAN * np.einsum("ij,ij->i", _up, TAN)[:, None]
DOR /= np.linalg.norm(DOR, axis=1, keepdims=True)
LAT = np.cross(TAN, DOR)
SP_TREE = cKDTree(SPINE)
log(f"spina: {len(SPINE)} punti, lunghezza {S_LEN:.2f}, collo da s = {S_RISE:.2f}")


def spine_coords(p):
    """Per ogni punto: indice del punto di spina piu' vicino, ascissa s lungo il corpo e angolo dal dorso."""
    _, i = SP_TREE.query(p, workers=2)
    v = p - SPINE[i]
    s = S[i] + np.einsum("ij,ij->i", v, TAN[i])
    a = np.arctan2(np.einsum("ij,ij->i", v, LAT[i]), np.einsum("ij,ij->i", v, DOR[i]))
    return i, s, a


def tube_f(p):
    d, i = SP_TREE.query(p, k=6, workers=2)
    return np.min(d - RAD[i], axis=1).astype(np.float32)


body_tube = SDF(tube_f, SPINE.min(0) - 0.4, SPINE.max(0) + 0.4)
# pancia appiattita a terra
body_tube = body_tube.intersect(GROUND)

# ------------------------------------------------------------ cappuccio: scudo enorme e concavo attorno al collo
HOOD_Y, HOOD_W = -0.2, 1.3
HOOD_OUT = [(0.0, 1.64), (0.33, 1.7), (0.68, 1.86), (1.02, 2.1), (1.24, 2.4), (1.3, 2.64), (1.23, 2.88), (1.04, 3.07),
            (0.72, 3.19), (0.36, 3.23), (0.0, 3.21)]
HOOD_OUT = HOOD_OUT + [(-x, z) for x, z in reversed(HOOD_OUT[1:-1])]
_hood2d = poly2d(HOOD_OUT)


def hood_mid(x, z):
    """Superficie media del cappuccio: i bordi si piegano in avanti (concavo verso chi guarda)."""
    return HOOD_Y - 0.36 * (x / HOOD_W) ** 2 + 0.06 * ((z - 2.45) / 0.7) ** 2


def hood_half(x):
    return 0.055 + 0.07 * np.clip(1.0 - (x / HOOD_W) ** 2, 0.0, 1.0)


def hood_f(p, side=0):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    a = _hood2d(x, z) + 0.035
    ym = hood_mid(x, z)
    b = np.abs(y - ym) - hood_half(x) + 0.035
    d = np.minimum(np.maximum(a, b), 0.0) + np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2) - 0.035
    if side < 0:      # meta' davanti
        d = np.maximum(d, y - ym)
    elif side > 0:    # meta' dietro
        d = np.maximum(d, ym - y)
    return d


HOOD_LO, HOOD_HI = (-1.37, -0.85, 1.58), (1.37, 0.12, 3.3)
hood = SDF(hood_f, HOOD_LO, HOOD_HI)
hood_front = SDF(lambda p: np.maximum(hood_f(p, -1), -body_tube(p)), HOOD_LO, HOOD_HI)
hood_back = SDF(lambda p: hood_f(p, 1), HOOD_LO, HOOD_HI)
body_core = union(body_tube, hood_back, k=0.0)
body_all = union(body_tube, hood)
log("cappuccio pronto")

# ------------------------------------------------------------ testa (coordinate locali: Y avanti, Z su)
HEAD_O = SPINE[-1].copy()
HEAD_F = norm((0.0, -1.0, 0.09))     # testa quasi orizzontale: sguardo dritto su chi guarda
HS = 1.32                        # scala della testa
HM = basis(HEAD_F, (0.0, 0.0, 1.0))
JAW = -54.0
HINGE = (0.0, 0.02, -0.05)


def H(shape):
    return place(shape.scale(HS), HM, HEAD_O)


def Hp(q):
    return HEAD_O + HM @ (HS * np.asarray(q, dtype=np.float32))


cranium = union(ellipsoid((0.3, 0.34, 0.19), (0, 0.16, 0.06)), ellipsoid((0.235, 0.3, 0.145), (0, 0.5, 0.04)), k=0.14)
cranium = union(cranium, *[ellipsoid((0.19, 0.22, 0.15), (sx * 0.2, 0.14, -0.02)) for sx in (1, -1)], k=0.1)
brows = [ellipsoid((0.12, 0.22, 0.07)).rot(-6, sx * 24, 0).translate((sx * 0.165, 0.36, 0.17)) for sx in (1, -1)]
cranium = union(cranium, *brows, k=0.06)
upper = cranium.intersect(halfspace(lambda p: -0.045 - p[:, 2]), k=0.02)
lower = union(ellipsoid((0.25, 0.44, 0.085), (0, 0.36, -0.1)), *[ellipsoid((0.17, 0.2, 0.11), (sx * 0.19, 0.12, -0.08))
                                                                     for sx in (1, -1)], k=0.08)
lower = lower.intersect(halfspace(lambda p: p[:, 2] + 0.06), k=0.02)
lower_w = lower.rot(JAW, 0, 0, pivot=HINGE)
head = union(upper, lower_w, k=0.04)
head_w = H(head)

# bocca: rivestimento rosso scuro del palato e del pavimento della mandibola (le labbra restano scure)
def mouth_f(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    q = p - np.asarray(HINGE, dtype=np.float32)
    c, s = math.cos(math.radians(-JAW)), math.sin(math.radians(-JAW))
    yq = q[:, 1] * c - q[:, 2] * s + HINGE[1]      # coordinate nel sistema della mandibola chiusa
    zq = q[:, 1] * s + q[:, 2] * c + HINGE[2]
    d_up = z - 0.0
    d_lo = -0.12 - zq
    w_up = np.interp(y, [-0.1, 0.3, 0.55, 0.72, 0.8], [0.25, 0.23, 0.155, 0.07, 0.0])
    w_lo = np.interp(yq, [-0.1, 0.3, 0.55, 0.72, 0.8], [0.23, 0.2, 0.13, 0.05, 0.0])
    d_w = np.abs(x) - np.where(z > -0.05, w_up, w_lo)
    d_f = np.maximum(y - 0.8, yq - 0.78)
    d_b = -0.08 - y
    d = smax(d_up, d_lo, 0.02)
    for o in (d_w, d_f, d_b):
        d = smax(d, o, 0.02)
    return d


mouth = paint(head, SDF(mouth_f, (-0.3, -0.15, -0.7), (0.3, 0.85, 0.1)), d=0.03, depth=0.07)

# zanne lunghe davanti, dentini ai lati, lingua biforcuta
fangs, teeth = [], []
FANG_TIPS = []
for sx in (1, -1):
    f = bezier((sx * 0.11, 0.58, -0.0), (sx * 0.125, 0.64, -0.17), (sx * 0.115, 0.6, -0.31), (sx * 0.095, 0.52, -0.4),
               10)
    fangs.append(tube(f, [0.056 * (1 - i / 10) ** 0.8 + 0.007 for i in range(11)]))
    FANG_TIPS.append(Hp(f[-1]))
    for y in (0.24, 0.34, 0.44):
        b = (sx * (0.17 - 0.12 * (y - 0.2)), y, -0.03)
        teeth.append(round_cone(b, (b[0], y - 0.01, -0.1), 0.022, 0.005))
    for y in (0.3, 0.42, 0.52):
        b = (sx * (0.16 - 0.1 * (y - 0.2)), y, -0.07)
        teeth.append(round_cone(b, (b[0], y - 0.01, -0.0), 0.02, 0.005).rot(JAW, 0, 0, pivot=HINGE))
tongue_pts = bezier((0.0, 0.2, -0.1), (0.0, 0.55, -0.16), (0.0, 0.85, -0.1), (0.0, 1.0, -0.2), 12)
tongue = tube(tongue_pts, [0.04 - 0.0015 * i for i in range(13)])
tip = np.array(tongue_pts[-1])
forks = [tube(bezier(tuple(tip), tuple(tip + (sx * 0.03, 0.06, -0.01)), tuple(tip + (sx * 0.07, 0.12, -0.04)),
                     tuple(tip + (sx * 0.09, 0.16, -0.09)), 6), [0.022, 0.02, 0.018, 0.015, 0.012, 0.01, 0.006])
         for sx in (1, -1)]
tongue = union(tongue, *forks, k=0.015).rot(JAW * 0.45, 0, 0, pivot=HINGE)

# occhi: verdi luminosi con la pupilla a fessura, sotto le sopracciglia
eyes, pupils, shines, brow_lines = [], [], [], []
for sx in (1, -1):
    c_loc, n_loc = proj(upper, (sx * 0.05, 0.38, 0.05), (sx * 0.72, 0.56, 0.42))
    c_loc = c_loc - n_loc * 0.035
    Me = basis(n_loc, (0, 0, 1))
    eyes.append(place(ellipsoid((0.11, 0.07, 0.088)).rot(0, sx * 14, 0), Me, c_loc))
    pupils.append(place(ellipsoid((0.024, 0.03, 0.075)), Me, c_loc + n_loc * 0.052))
    shines.append(place(sphere(0.024), Me, c_loc + n_loc * 0.068 + Me[:, 0] * 0.04 + Me[:, 2] * 0.035))
    # cresta sopraccigliare nera, inclinata verso il muso (sguardo cattivo)
    brow_lines.append(place(capsule((-sx * 0.15, 0.02, 0.1), (sx * 0.12, 0.02, 0.045), 0.04), Me, c_loc))
# placche d'oro sulla testa: la "corona" del re (due grandi occipitali + lo scudo fra gli occhi)
crown_region = union(ellipsoid((0.09, 0.14, 0.4), (0.108, 0.04, 0.2)),
                     ellipsoid((0.09, 0.14, 0.4), (-0.108, 0.04, 0.2)),
                     ellipsoid((0.075, 0.11, 0.4), (0.0, 0.33, 0.2)))
crown = paint(upper, crown_region.intersect(halfspace(lambda p: 0.06 - p[:, 2])), d=0.025, depth=0.05)
log("testa pronta")

# ------------------------------------------------------------ squame ventrali corazzate sul collo (a tegole)
BELLY_S0 = S_RISE - 0.35


def belly_f(p):
    i, s, a = spine_coords(p)
    base = tube_f(p)
    t = ((s - BELLY_S0) / 0.17) % 1.0
    off = 0.01 + 0.065 * smoothstep(0.0, 0.1, t) * smoothstep(1.0, 0.9, t)
    d = base - off
    d = np.maximum(d, 0.022 - np.minimum(t, 1.0 - t) * 0.17)    # fessura scura fra una placca e l'altra
    ang = (np.abs(np.abs(a) - math.pi) - 0.85) * RAD[i]       # fascia ventrale (+-50 gradi)
    d = smax(d, ang, 0.02)
    d = np.maximum(d, -(base + 0.08))                           # guscio: niente interno nascosto
    d = np.maximum(d, BELLY_S0 - s)
    d = np.maximum(d, s - (S_LEN - 0.1))
    return d


belly = SDF(belly_f, (-0.75, -1.0, 0.55), (0.75, 0.25, 3.35))

# ------------------------------------------------------------ bande a V ocra sul dorso
BAND_STEP, BAND_W = 0.56, 0.1


def bands_f(p):
    i, s, a = spine_coords(p)
    se = s + 0.55 * np.abs(a) * RAD[i]                        # a V, punta verso la testa
    g = np.abs(((se - 0.25) / BAND_STEP + 0.5) % 1.0 - 0.5) * BAND_STEP - BAND_W
    return np.maximum(np.maximum(g, (np.abs(a) - 1.5) * RAD[i]), np.maximum(0.35 - s, s - (S_LEN - 0.5)))


bands = paint(body_tube, SDF(bands_f, SPINE.min(0) - 0.5, SPINE.max(0) + 0.5), d=0.035, depth=0.09)


def spectacle_f(p):
    """Dietro il cappuccio: due grandi occhi finti ocra (anello + pupilla), come un secondo sguardo."""
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    d = np.full(len(p), 1e3, dtype=np.float32)
    for sx in (1, -1):
        th = math.radians(sx * 24.0)          # a mandorla e inclinati: uno sguardo cattivo anche da dietro
        u = (x - sx * 0.6) * math.cos(th) + (z - 2.6) * math.sin(th)
        v = -(x - sx * 0.6) * math.sin(th) + (z - 2.6) * math.cos(th)
        r = np.sqrt((u / 1.25) ** 2 + (v / 0.72) ** 2)
        slit = np.sqrt((u / 0.3) ** 2 + (v / 1.0) ** 2) - 0.12
        d = np.minimum(d, np.maximum(r - 0.24, -slit))
    return np.maximum(d, hood_mid(x, z) + 0.03 - y)


spectacle = paint(hood_back, SDF(spectacle_f, (-1.0, -0.6, 2.1), (1.0, 0.2, 3.05)), d=0.03, depth=0.07)

# ------------------------------------------------------------ disegni neri sul cappuccio: bordo, costole a raggiera
pattern = []
rim = []
for x, z in HOOD_OUT + [HOOD_OUT[0]]:
    rim.append((x, float(hood_mid(np.float32(x), np.float32(z))), z))
rim_pts, _ = resample(np.array(rim), 0.04)
pattern.append(tube([tuple(q) for q in rim_pts], 0.06))


def hood_front_pt(x, z, lift=0.0):
    y = float(hood_mid(np.float32(x), np.float32(z)) - hood_half(np.float32(x)))
    return np.array([x, y - lift, z])


RIBS = [((0.32, 1.8), (0.55, 1.82), (0.8, 1.93)), ((0.33, 1.97), (0.68, 2.03), (1.1, 2.2)),
        ((0.33, 2.15), (0.79, 2.3), (1.26, 2.52)), ((0.33, 2.34), (0.77, 2.58), (1.2, 2.9)),
        ((0.32, 2.53), (0.62, 2.82), (0.85, 3.13))]
for sx in (1, -1):
    for a, b, c in RIBS:
        pts = bezier((sx * a[0], 0, a[1]), (sx * b[0], 0, b[1]), (sx * b[0], 0, b[1]), (sx * c[0], 0, c[1]), 10)
        q3 = [hood_front_pt(q[0], q[2], -0.005) for q in pts]
        pattern.append(tube([tuple(q) for q in q3], [0.055 - 0.02 * i / 10 for i in range(11)]))

# cucitura: il cappuccio e' cucito al collo (linea nera nella piega + grandi punti a X color osso a cavallo)
stitches, seams = [], []
X_SEAM = 0.26
for sx in (1, -1):
    line = [proj(body_all, (sx * X_SEAM, -0.15, z), (0.0, -1.0, 0.0)) for z in np.linspace(1.8, 2.98, 14)]
    seams.append(tube([tuple(q - n * 0.012) for q, n in line], 0.04))
    for z in np.linspace(1.9, 2.86, 6):
        c, nc = proj(body_all, (sx * X_SEAM, -0.15, z), (0.0, -1.0, 0.0))
        ends = []
        for dx, dz in ((0.14, 0.09), (-0.14, -0.09), (0.14, -0.09), (-0.14, 0.09)):
            q, n = proj(body_all, (sx * (X_SEAM + dx), -0.15, z + dz), (0.0, -1.0, 0.0))
            ends.append(q + n * 0.012)
        for e0, e1 in ((ends[0], ends[1]), (ends[2], ends[3])):
            stitches.append(tube([tuple(e0), tuple(c + nc * 0.055), tuple(e1)], 0.034))
log("disegni e cuciture pronti")

# ------------------------------------------------------------ veleno: gocce dalle zanne, bava fra le mascelle
venom = []
for tp in FANG_TIPS:
    venom.append(sphere(0.036, tuple(tp + np.array([0, 0, -0.005]))))
    venom.append(hang_drop(tp + np.array([0, 0, -0.01]), 0.26, 0.03, 0.066))
fallp = FANG_TIPS[0] + np.array([0.02, -0.03, -0.55])
venom.append(union(sphere(0.045, tuple(fallp)), round_cone(tuple(fallp), tuple(fallp + [0, 0, 0.09]), 0.042, 0.008),
                   k=0.02))

# ------------------------------------------------------------ parti
m.add("Body", body_core, SKIN, tris=4600, voxel=0.034)
m.add("HeadSkin", head_w, SKIN, tris=1500, voxel=0.022)
m.add("HoodFront", hood_front, GOLD, role="detail", tris=1300, voxel=0.03)
m.add("BlackMarkings", fast_union(pattern + seams + [H(union(*brow_lines))]), BLACK, role="detail", tris=1400,
      voxel=0.024)
m.add("GoldCrown", H(crown), GOLD, material="Metal", role="detail", tris=300, voxel=0.016)
m.add("Bands", union(bands, spectacle), BAND, role="detail", tris=1500, voxel=0.03)
m.add("BellyScales", belly, BELLY, role="detail", tris=1500, voxel=0.028)
m.add("Stitches", fast_union(stitches), THREAD, role="detail", tris=700, voxel=0.018)
m.add("Mouth", H(mouth), MOUTH, role="eye", tris=500, voxel=0.03)
m.add("Fangs", H(fast_union(fangs + teeth)), BONE, role="shine", tris=450, voxel=0.013)
m.add("Tongue", H(tongue), TONGUE, role="detail", tris=260, voxel=0.013)
m.add("Venom", fast_union(venom), VENOM, material="Neon", role="glow", tris=600, voxel=0.016)
m.add("EyeGlow", H(union(*eyes)), EYE_G, material="Neon", role="glow", tris=300, voxel=0.012)
m.add("Pupils", H(union(*pupils)), PUPIL, role="eye", tris=150, voxel=0.009)
m.add("Shine", H(union(*shines)), WHITE, role="shine", tris=80, voxel=0.008)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
    log("fatto")
