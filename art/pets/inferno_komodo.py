"""Komodo Infernale (InfernoKomodo) - pet Ultra (il livello piu' alto).

Un enorme drago di Komodo incrociato con un alligatore: corpo lungo, basso e muscoloso su quattro
zampe divaricate con grandi artigli ricurvi, testa massiccia con la mascella lunga e pesante piena di
denti frastagliati, socchiusa, e la lingua biforcuta che guizza fuori. Lungo collo, schiena e coda
corrono file di placche da dinosauro frastagliate che BRUCIANO; la pelle carbone e' fatta di scaglie
bitorzolute (osteodermi) con crepe di lava luminose su fianchi e zampe; occhi di brace.
Tocco "toy horror": la coda e' ricucita al corpo con punti grossi e dalla cucitura filtra il fuoco.

Tutte le parti che bruciano sono nella parte Neon "Flames" (il gioco ci attacca fuoco e braci).
"""
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.mesher import mesh_sdf  # noqa: E402
from lib.sdf import (SDF, Frame, bezier, capsule, ellipsoid, euler, project, rot_matrix, round_cone,  # noqa: E402
                     smax, smin, sphere, tube, union)
from lib.toy import Model  # noqa: E402

DRAFT = os.environ.get("DRAFT", "") == "1"
VX = 1.6 if DRAFT else 1.0  # bozza: voxel piu' grossi per iterare in fretta
T0 = time.time()


def log(msg):
    print(f"[komodo {time.time() - T0:6.1f}s] {msg}", flush=True)


# ============================================================ helper (lib/ non si modifica: definiti qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def grad(sdf, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float64)
    g = np.array([sdf((p + e)[None, :].astype(np.float32))[0] - sdf((p - e)[None, :].astype(np.float32))[0]
                  for e in np.eye(3) * eps])
    return g / max(np.linalg.norm(g), 1e-9)


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
    return np.array(out)


def poly2d(pts):
    """Distanza con segno da un poligono 2D (come prism di lib/sdf): f(u, v)."""
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


def proj(sdf, origin, direction, max_dist=2.0, n=400):
    """Come project() di lib/sdf ma su un raggio piu' corto (piu' veloce). None se parte da fuori."""
    o = np.asarray(origin, dtype=np.float64)
    d = norm(direction)
    ts = np.linspace(0.0, max_dist, n)
    vals = sdf((o[None, :] + ts[:, None] * d[None, :]).astype(np.float32))
    if vals[0] > 0:
        return None, None
    idx = np.nonzero(vals > 0)[0]
    if len(idx) == 0:
        return None, None
    lo_t, hi_t = ts[max(idx[0] - 1, 0)], ts[idx[0]]
    for _ in range(18):
        mid = 0.5 * (lo_t + hi_t)
        if sdf((o + mid * d)[None, :].astype(np.float32))[0] > 0:
            hi_t = mid
        else:
            lo_t = mid
    p = o + 0.5 * (lo_t + hi_t) * d
    e6 = np.concatenate([np.eye(3), -np.eye(3)]) * 1e-3
    v6 = sdf((p[None, :] + e6).astype(np.float32))
    g = v6[:3] - v6[3:]
    return p, g / max(np.linalg.norm(g), 1e-9)


def halfspace(fn, lo=(-9, -9, -9), hi=(9, 9, 9)):
    return SDF(fn, lo, hi)


def frame_matrix(normal, tangent, roll=0.0):
    """Colonne: X locale, Y locale (lungo la tangente), Z locale (lungo la normale)."""
    z = norm(normal)
    y = norm(np.asarray(tangent, float) - z * float(np.dot(tangent, z)))
    x = np.cross(y, z)
    mt = np.stack([x, y, z], axis=1).astype(np.float32)
    if roll:
        mt = mt @ rot_matrix((0, 1, 0), roll)
    return mt


def place(shape, mt, p):
    return shape.rotate(mt).translate(p)


def paint(base, region, d=0.02, depth=0.045, k=0.0):
    """Vernice a strato sottile (fra -depth e +d dalla superficie) ritagliata dalla regione."""
    t = (d + depth) / 2
    return base.offset(d - t).shell(t).intersect(region, k=k)


def lid_shape(radii, cut, slope=0.0, grow=0.018, k=0.01):
    """Palpebra pesante (coordinate locali del Frame): calotta dell'occhio ingrandito sopra z = cut + slope*x."""
    a, b, c = radii
    nrm = math.sqrt(1.0 + slope * slope)
    above = SDF(lambda p: (cut + slope * p[:, 0] - p[:, 2]) / nrm, (-1, -1, -1), (1, 1, 1))
    return ellipsoid((a + grow, b + grow, c + grow)).intersect(above, k=k)


# ============================================================ palette
SKIN = (56, 44, 40)          # carbone caldo
BELLY = (150, 72, 46)        # pancia rosso ruggine
PLATE = (128, 36, 22)        # base di placche e corna: rosso bruciato
FIRE = (255, 118, 20)        # fuoco (Neon)
EYE_GLOW = (255, 214, 64)    # occhi di brace
PUPIL = (26, 10, 8)
BONE = (240, 228, 200)       # denti e artigli
MOUTH = (46, 10, 14)
TONGUE = (196, 42, 60)
WHITE = (255, 255, 255)

m = Model("InfernoKomodo", "pet", voxel=0.022 * VX)

# ============================================================ testa (coordinate locali: cerniera della mascella)
HS = 1.15                                   # scala della testa (massiccia)
HEAD_POS = np.array([0.13, -1.76, 1.36], dtype=np.float32)
R_HEAD = euler(-5.0, 4.0, 17.0)             # testa alta, girata verso chi guarda
HINGE = np.array([0.0, 0.06, -0.03], dtype=np.float32)
JAW_OPEN = 21.0
R_JAW = euler(JAW_OPEN, 0.0, 0.0)


def H(shape):
    return shape.scale(HS).rotate(R_HEAD).translate(HEAD_POS)


def Hp(p):
    return HEAD_POS + R_HEAD @ (HS * np.asarray(p, dtype=np.float32))


def J(shape):
    """Forma della mandibola (posa chiusa, locale) -> aperta -> mondo."""
    return H(shape.rotate(R_JAW, pivot=HINGE))


def to_head(p):
    """Mondo -> coordinate locali della testa."""
    return ((p - HEAD_POS) @ R_HEAD) / HS


def lip_up(y):
    return -0.03 + 0.014 * np.sin((y + 0.1) * 9.0)


def lip_lo(y):
    return -0.045 + 0.0 * y


upper = union(
    ellipsoid((0.40, 0.42, 0.29), (0, -0.04, 0.12)),      # cranio
    ellipsoid((0.345, 0.56, 0.2), (0, -0.52, 0.05)),      # base del muso
    ellipsoid((0.27, 0.40, 0.15), (0, -0.88, 0.03)),      # muso
    ellipsoid((0.22, 0.17, 0.115), (0, -1.06, 0.03)),     # punta a U (alligatore)
    k=0.16)
upper = union(upper, ellipsoid((0.14, 0.12, 0.08), (0, -1.02, 0.115)), k=0.06)  # gobba delle narici
upper = union(upper, *[ellipsoid((0.19, 0.28, 0.22), (sx * 0.31, 0.05, -0.02)) for sx in (1, -1)], k=0.1)  # guance
brow_ridges = [ellipsoid((0.125, 0.25, 0.085)).rot(15, 0, -sx * 10).translate((sx * 0.24, -0.25, 0.3)) for sx in (1, -1)]
skull_ridges = [capsule((sx * 0.21, -0.12, 0.34), (sx * 0.26, 0.16, 0.31), 0.055) for sx in (1, -1)]
knobs_snout = [proj(upper, (sx * 0.13, y, 0.0), (0, 0, 1))[0] for sx in (1, -1) for y in (-0.5, -0.66, -0.82)]
upper = union(upper, *brow_ridges, *skull_ridges, k=0.07)
upper = union(upper, *[sphere(0.042, q - np.array([0, 0, 0.012])) for q in knobs_snout], k=0.03)
# osteodermi bitorzoluti sul cranio e sulle guance (come le scaglie del corpo)
_hk = []
for x, y in ((0.12, -0.06), (0.25, 0.0), (0.0, 0.03), (0.13, 0.11), (0.23, 0.19), (0.05, 0.2), (0.33, 0.12)):
    for sx in ((1, -1) if x else (1,)):
        q, n = proj(upper, (sx * x, y, 0.0), (0.0, 0.1, 1.0))
        _hk.append(sphere(0.04, q - n * 0.016))
for y, z in ((-0.06, 0.02), (0.07, -0.04), (0.17, 0.06), (0.02, -0.13), (0.15, -0.12)):
    for sx in (1, -1):
        q, n = proj(upper, (sx * 0.1, y, z), (sx, 0.0, 0.15))
        _hk.append(sphere(0.036, q - n * 0.015))
upper = union(upper, *_hk, k=0.025)

# occhi di brace sotto le arcate sopraccigliari, palpebre pesanti e inclinate (sguardo cattivo)
EYE_R = (0.115, 0.08, 0.098)
eye_frames = {sx: Frame(upper, (sx * 0.12, -0.27, 0.17), (sx * 1.0, -0.6, 0.36), sink=0.045) for sx in (1, -1)}
lids = [f.place(lid_shape(EYE_R, 0.042, slope=-sx * 0.4)) for sx, f in eye_frames.items()]
upper = union(upper, *lids, k=0.012)
upper = upper.intersect(halfspace(lambda p: lip_up(p[:, 1]) - p[:, 2]), k=0.03)
nostrils = union(*[ellipsoid((0.046, 0.04, 0.042), (sx * 0.06, -1.05, 0.19)) for sx in (1, -1)])
upper = upper.subtract(nostrils, k=0.02)

lower = union(
    ellipsoid((0.37, 0.5, 0.16), (0, -0.32, -0.125)),
    ellipsoid((0.28, 0.42, 0.11), (0, -0.8, -0.09)),
    ellipsoid((0.21, 0.15, 0.09), (0, -1.03, -0.08)),
    k=0.14)
lower = union(lower, *[ellipsoid((0.2, 0.26, 0.16), (sx * 0.28, -0.08, -0.14)) for sx in (1, -1)], k=0.08)
lower = lower.intersect(halfspace(lambda p: p[:, 2] - lip_lo(p[:, 1])), k=0.03)
throat = ellipsoid((0.3, 0.46, 0.21), (0, 0.1, -0.21))

head_up_w = H(upper)
jaw_w = J(lower)
throat_w = H(throat)

# ============================================================ corpo
torso = union(ellipsoid((0.62, 0.64, 0.48), (0, -0.62, 0.92)),   # petto profondo
              ellipsoid((0.7, 0.72, 0.44), (0, 0.0, 0.78)),      # pancia larga
              ellipsoid((0.58, 0.58, 0.42), (0, 0.6, 0.8)),      # fianchi
              k=0.32)
MUSCLES = ([ellipsoid((0.35, 0.41, 0.34), (sx * 0.44, -0.72, 1.06)) for sx in (1, -1)]       # spalle
           + [ellipsoid((0.34, 0.42, 0.34), (sx * 0.44, 0.55, 0.88)) for sx in (1, -1)])  # cosce
torso = union(torso, *MUSCLES, k=0.18)
NECK_PTS = [(0.0, -0.8, 1.0), (0.05, -1.2, 1.18), tuple(Hp((0.0, 0.14, 0.04)))]
neck = tube(NECK_PTS, [0.47, 0.41, 0.35])

# zampe: (spalla/anca, gomito/ginocchio, polso/caviglia, direzione delle dita)
LEGS = {
    "FR": ((0.45, -0.8, 0.82), (0.9, -1.05, 0.6), (0.98, -1.34, 0.17), (0.3, -1.0)),   # avanti: fa un passo
    "FL": ((-0.45, -0.66, 0.82), (-0.9, -0.56, 0.6), (-0.98, -0.64, 0.17), (-0.3, -1.0)),
    "HR": ((0.46, 0.6, 0.78), (0.98, 0.45, 0.64), (1.04, 0.88, 0.17), (0.5, -1.0)),    # dietro: spinge
    "HL": ((-0.46, 0.52, 0.78), (-0.98, 0.16, 0.66), (-1.03, 0.28, 0.17), (-0.5, -1.0)),
}
leg_shapes, toe_tips, LEG_INFO = [], [], {}
for key, (s, e, w, fwd) in LEGS.items():
    hind = key[0] == "H"
    s, e, w = map(np.array, (s, e, w))
    r_up, r_lo = (0.32, 0.22) if hind else (0.29, 0.215)
    upper_leg = round_cone(tuple(s), tuple(e), r_up, r_up * 0.74)
    bulge = ellipsoid((r_up * 1.0, r_up * 1.3, r_up * 1.0), tuple(s * 0.42 + e * 0.58 + np.array([0, 0, 0.05])))
    lower_leg = round_cone(tuple(e), tuple(w), r_lo, r_lo * 0.7)
    calf = ellipsoid((r_lo * 1.12, r_lo * 1.15, r_lo * 1.35), tuple(e * 0.6 + w * 0.4 + np.array([0, 0.02, 0])))
    fd = norm((fwd[0], fwd[1], 0.0))
    side = np.array([-fd[1], fd[0], 0.0])
    palm_c = w + fd * 0.1
    palm_c[2] = 0.09
    palm = ellipsoid((0.19, 0.21, 0.09)).rotate(frame_matrix((0, 0, 1), fd)).translate(tuple(palm_c))
    toes = []
    spread = (-50, -23, 0, 23, 48)
    lens = (0.23, 0.31, 0.35, 0.31, 0.25) if not hind else (0.25, 0.34, 0.39, 0.35, 0.27)
    for ang, ln in zip(spread, lens):
        a = math.radians(ang)
        d = fd * math.cos(a) + side * math.sin(a)
        p0 = palm_c + d * 0.06
        p1 = palm_c + d * (ln * 0.55) + np.array([0, 0, 0.04])
        p2 = palm_c + d * ln
        p2[2] = 0.065
        toes.append(tube([tuple(p0), tuple(p1), tuple(p2)], [0.085, 0.07, 0.056]))
        toe_tips.append((p2, d))
    ankle = round_cone(tuple(w), tuple(palm_c + np.array([0, 0, 0.05])), r_lo * 0.7, 0.11)
    leg_shapes.append(union(union(upper_leg, bulge, k=0.09), union(lower_leg, calf, k=0.07), k=0.08))
    leg_shapes.append(union(palm, *toes, k=0.05).union(ankle, k=0.06))
    LEG_INFO[key] = (s, e, w, r_up, r_lo)

# coda lunga e grossa che curva verso destra (+X) e striscia a terra
TAIL_N = 26
_tp = bezier((0.0, 0.92, 0.78), (0.0, 1.58, 0.64), (0.34, 2.12, 0.22), (1.28, 2.45, 0.2), TAIL_N)
TAIL_R = [0.035 + 0.395 * (1 - i / TAIL_N) ** 0.95 for i in range(TAIL_N + 1)]
TAIL_PTS = [(x, y, max(z, r * 0.96)) for (x, y, z), r in zip(_tp, TAIL_R)]
tail = tube(TAIL_PTS, TAIL_R)

core0 = fast_union([neck], k=0.22, base=torso)
core0 = fast_union([head_up_w, throat_w], k=0.14, base=core0)
core0 = fast_union([jaw_w], k=0.07, base=core0)
core0 = fast_union(leg_shapes, k=0.1, base=core0)
core0 = fast_union([tail], k=0.22, base=core0)
log("core0 pronto")

# ============================================================ crepe di lava: linee frastagliate su fianchi, collo, zampe e coda
rng = np.random.default_rng(11)
UP = np.array([0.0, 0.0, 1.0])


def walk(start, ang, n, step, turn, zlim=(0.56, 1.12)):
    """Passeggiata 2D (y, z) con svolte casuali, chiusa nella fascia dei fianchi: ritorna la polilinea."""
    pts = [np.array(start, float)]
    for _ in range(n):
        ang += rng.uniform(-turn, turn)
        q = pts[-1] + step * np.array([math.cos(ang), math.sin(ang)])
        if not zlim[0] < q[1] < zlim[1]:
            ang = -ang
            q = pts[-1] + step * np.array([math.cos(ang), math.sin(ang)])
            q[1] = min(max(q[1], zlim[0]), zlim[1])
        pts.append(q)
    return pts


CRACKS = {}  # regione -> lista di (punti, forza iniziale, forza finale)


def add_line(region, pts, s0, s1):
    pts = [q for q in pts if q is not None]
    if len(pts) > 1:
        CRACKS.setdefault(region, []).append((np.array(pts), s0, s1))


def on_flank(sx, yy, zz):
    return proj(core0, (sx * 0.05, yy, zz), (sx, 0.0, 0.12 * (zz - 0.8)))[0]


for sx in (1, -1):
    for y0, z0, a0 in ((-0.62, 1.06, -1.25), (-0.12, 1.02, -1.4), (0.4, 1.02, -1.75), (-0.42, 0.8, -0.3)):
        main = walk((y0, z0), a0, 9, 0.07, 0.42)
        add_line(f"flank{sx}", [on_flank(sx, yy, zz) for yy, zz in main], 1.0, 0.4)
        for j in (3, 6):
            br = walk(main[j], a0 + rng.choice([-1, 1]) * rng.uniform(0.6, 1.1), 4, 0.06, 0.4)
            add_line(f"flank{sx}", [on_flank(sx, yy, zz) for yy, zz in br], 0.7, 0.25)
    if sx < 0:  # collo (lato sinistro): una crepa che scende dietro la testa
        pts = []
        for t in np.linspace(0.0, 1.0, 8):
            c = np.array(NECK_PTS[0]) * t + np.array(NECK_PTS[2]) * (1 - t)
            pts.append(proj(core0, c, (sx, rng.uniform(-0.3, 0.3), 0.35 - 0.5 * t))[0])
        add_line(f"neck{sx}", pts, 0.9, 0.5)
# cicatrice ricucita sul lato destro del collo (quello verso chi guarda)
SCAR = []
for t in np.linspace(0.0, 1.0, 10):
    c = np.array(NECK_PTS[0]) * t + np.array(NECK_PTS[2]) * (1 - t)
    SCAR.append(proj(core0, c, (1.0, -0.15 + 0.3 * t, 0.75 - 0.95 * t))[0])
SCAR = [q for q in SCAR if q is not None]
add_line("scar", SCAR, 1.0, 1.0)
for key, (s0, e0, w0, r_up, r_lo) in LEG_INFO.items():
    sx = 1 if s0[0] > 0 else -1
    pts = []
    for a, b, tilt, n in ((s0 * 0.6 + e0 * 0.4, e0, (0, -0.35, 1.0), 6), (e0, w0 + (w0 - e0) * -0.1, (sx, -0.7, 0.1), 6)):
        ax = norm(b - a)
        out = norm(np.array(tilt, float) - ax * float(np.dot(tilt, ax)))
        perp = np.cross(ax, out)
        for t in np.linspace(0.0, 1.0, n):
            pts.append(proj(core0, a + (b - a) * t, out + perp * rng.uniform(-0.4, 0.4))[0])
    add_line(f"leg{key}", pts, 1.0, 0.35)
for sx in (1, -1):
    for j0, j1, st in ((3, 13, 0.9), (13, 21, 0.6)):
        pts = []
        for j in range(j0, j1):
            c = np.array(TAIL_PTS[j])
            tj = norm(np.array(TAIL_PTS[j + 1]) - np.array(TAIL_PTS[j - 1]))
            sd = norm(np.cross(tj, UP)) * sx
            pts.append(proj(core0, c, sd + UP * (0.3 + rng.uniform(-0.3, 0.3)))[0])
        add_line(f"tail{j0}", pts, st, st * 0.5)

# cucitura della coda (toy horror): la coda e' ricucita al corpo e dalla cucitura filtra il fuoco
Y_CUT = 1.22
_ti = int(np.argmin([abs(q[1] - Y_CUT) for q in TAIL_PTS]))
SEAM_C = np.array([TAIL_PTS[_ti][0], Y_CUT, TAIL_PTS[_ti][2] + 0.02])
SEAM = []
for th in np.radians(np.concatenate([np.linspace(-75, 58, 15), np.linspace(122, 255, 15)])):
    q, _ = proj(core0, SEAM_C, (math.cos(th), 0.0, math.sin(th)))
    SEAM.append(q)
add_line("seam", SEAM[:15], 1.0, 1.0)
add_line("seam", SEAM[15:], 1.0, 1.0)


class CrackSet:
    """Punti fitti lungo le crepe (con la loro forza) in un KD-tree."""

    def __init__(self, lines, step=0.012):
        pts, st = [], []
        for poly, s0, s1 in lines:
            rs = resample(poly, step)
            pts.append(rs)
            st.append(np.linspace(s0, s1, len(rs)))
        self.pts = np.concatenate(pts)
        self.st = np.concatenate(st)
        self.tree = cKDTree(self.pts)
        self.lo, self.hi = self.pts.min(0), self.pts.max(0)

    def query(self, p, bound):
        d, i = self.tree.query(p, distance_upper_bound=bound, workers=2)
        ok = np.isfinite(d)
        return d, np.where(ok, i, 0), ok


CR_ALL = CrackSet([ln for lines in CRACKS.values() for ln in lines])
CR_SETS = [CrackSet(lines) for lines in CRACKS.values()]
log(f"crepe: {sum(len(v) for v in CRACKS.values())} linee in {len(CRACKS)} zone")

# ============================================================ pancia rosso ruggine (anche gola e meta' bassa della mandibola)
belly_zone = fast_union([
    ellipsoid((0.86, 1.4, 0.33), (0, -0.15, 0.4)),
    capsule((0, -0.9, 0.64), tuple(Hp((0, 0.05, -0.3))), 0.26),
    H(ellipsoid((0.32, 0.5, 0.15), (0, 0.02, -0.32))),
    J(ellipsoid((0.44, 0.74, 0.15), (0, -0.52, -0.22))),
    tube([(x, y, z - 0.75 * r) for (x, y, z), r in zip(TAIL_PTS[:16], TAIL_R[:16])], [r * 0.6 for r in TAIL_R[:16]]),
], k=0.08)


# ============================================================ scaglie bitorzolute (celle di Voronoi sulla pelle)


def scale_spacing(p):
    """Passo delle scaglie: grandi su schiena e fianchi, piccole su zampe, collo e coda; niente sulla testa."""
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    sp = np.full(len(p), 0.17)
    sp = np.where(np.abs(x) > 0.7, 0.12, sp)                     # zampe
    sp = np.where(y < -1.1, 0.13, sp)                            # collo
    sp = np.where(y > 1.0, 0.16 - 0.05 * np.clip((y - 1.0) / 1.8, 0, 1), sp)  # coda
    return sp


def scale_mask(p):
    """Dove la pelle ha le scaglie in rilievo (0..1)."""
    z = p[:, 2]
    q = to_head(p)
    head = smoothstep(0.12, 0.32, q[:, 1])                        # niente sulla testa
    feet = smoothstep(0.15, 0.27, z)                              # niente su mani e piedi
    belly = smoothstep(0.0, 0.08, belly_zone(p.astype(np.float32)))  # niente sulla pancia
    return head * feet * belly


class Scales:
    def __init__(self, base, seed=7):
        v, _f, _n = mesh_sdf(base, 0.035)
        rng = np.random.default_rng(seed)
        v = v[rng.permutation(len(v))]
        mk = scale_mask(v)
        v = v[mk > 0.02]
        sp = scale_spacing(v)
        cs = float(sp.max())
        grid, acc, accr = {}, [], []
        for p, r in zip(v, sp):
            key = (int(p[0] // cs), int(p[1] // cs), int(p[2] // cs))
            ok = True
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for j in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                            rr = 0.5 * (r + accr[j])
                            if (acc[j][0] - p[0]) ** 2 + (acc[j][1] - p[1]) ** 2 + (acc[j][2] - p[2]) ** 2 < rr * rr:
                                ok = False
                                break
                        if not ok:
                            break
                    if not ok:
                        break
                if not ok:
                    break
            if ok:
                grid.setdefault(key, []).append(len(acc))
                acc.append(p)
                accr.append(r)
        self.seeds = np.array(acc, dtype=np.float64)
        self.size = np.array(accr)
        self.h = self.size * 0.27 * rng.uniform(0.75, 1.2, len(acc))
        self.tree = cKDTree(self.seeds)

    def query(self, p):
        d, idx = self.tree.query(p, k=2, workers=2)
        s1, s2 = self.seeds[idx[:, 0]], self.seeds[idx[:, 1]]
        sep = np.linalg.norm(s2 - s1, axis=1)
        e = (d[:, 1] ** 2 - d[:, 0] ** 2) / (2.0 * np.maximum(sep, 1e-6))
        return d[:, 0], e, idx[:, 0]


SC = Scales(core0)
log(f"scaglie: {len(SC.seeds)} celle")
GROOVE = 0.022


def body_f(p):
    d = core0(p)
    near = np.nonzero(np.abs(d) < 0.09)[0]
    if len(near):
        q = p[near]
        sub = d[near]
        mk = scale_mask(q)
        act = mk > 0.002
        if act.any():
            d1, e, i1 = SC.query(q[act].astype(np.float64))
            rho = d1 / np.maximum(d1 + e, 1e-6)
            prof = smoothstep(0.0, GROOVE, e) ** 0.8 * (0.45 + 0.55 * (1.0 - rho * rho))
            sub[act] -= (SC.h[i1] * prof * mk[act]).astype(np.float32)
        # solco lungo le crepe di lava
        dc, ic, ok = CR_ALL.query(q, 0.06)
        if ok.any():
            st = CR_ALL.st[ic[ok]]
            rg = 0.048 * (0.6 + 0.4 * st)
            g = np.clip(1.0 - (dc[ok] / rg) ** 2, 0.0, 1.0)
            sub[ok] += (0.03 * st * g * g).astype(np.float32)
        d[near] = sub
    return d


body = SDF(lambda p: np.maximum(body_f(p), -p[:, 2]), core0.lo, core0.hi)  # piante piatte a z = 0

# tre parti color pelle (stessa superficie, tagli sovrapposti): corpo, testa (piu' dettaglio) e coda ricucita.
# La testa si chiama "HeadSkin" e non "Head": il ragdoll del gioco tocca le parti "Head" dentro il personaggio.
HEAD_CUT = 0.3  # piano dietro il cranio (coordinata y locale della testa), limitato a un box attorno alla testa


def head_region(p):
    q = to_head(p)
    return np.maximum.reduce([q[:, 1] - HEAD_CUT, np.abs(q[:, 0]) - 0.62, np.abs(q[:, 2]) - 0.6])


body_cut = halfspace(lambda p: np.maximum(p[:, 1] - (Y_CUT + 0.015), -0.015 - head_region(p)))
head_cut = halfspace(lambda p: head_region(p) - 0.015)
tail_cut = halfspace(lambda p: (Y_CUT - 0.015) - p[:, 1])
m.add("Body", body.intersect(body_cut), SKIN, tris=15000, voxel=0.0232 * VX)
HEAD_LO = np.minimum.reduce([head_up_w.lo, jaw_w.lo, throat_w.lo]) - 0.1
HEAD_HI = np.maximum.reduce([head_up_w.hi, jaw_w.hi, throat_w.hi]) + 0.1
m.add("HeadSkin", SDF(body.intersect(head_cut).f, HEAD_LO, HEAD_HI), SKIN, role="skin", tris=7000, voxel=0.0198 * VX)
m.add("Tail", body.intersect(tail_cut), SKIN, role="skin", tris=5500, voxel=0.0159 * VX)

# fuoco nelle crepe: linea continua nel solco + i bordi delle scaglie vicine che si accendono
CR_D = 0.15


def crack_sdf(cs):
    def f(p):
        out = np.full(len(p), 1.0, dtype=np.float32)
        dd, ic, ok = cs.query(p, CR_D)
        near = np.nonzero(ok)[0]
        if len(near):
            q = p[near]
            st = cs.st[ic[near]]
            dn = dd[near]
            b = body_f(q)
            _d1, e, _i = SC.query(q.astype(np.float64))
            w_line = 0.032 * (0.45 + 0.55 * st)
            w_net = 0.024 * st * np.clip(1.0 - dn / CR_D, 0.0, 1.0)
            region = np.minimum(dn - w_line, e - w_net)
            out[near] = np.maximum(np.abs(b + 0.013) - 0.021, region)
        return out

    return SDF(f, cs.lo - CR_D - 0.05, cs.hi + CR_D + 0.05)


cracks = fast_union([crack_sdf(cs) for cs in CR_SETS])

# punti incrociati delle cuciture (filo color osso)


def cross_stitches(line, step=0.105, half_len=0.042, half_w=0.062, r=0.016):
    """Punti a X a cavallo della linea, appoggiati sulla pelle (il filo scavalca il solco che brucia)."""
    out = []
    pr = resample(line, step)
    for j in range(len(pr)):
        c = pr[j]
        t = norm(pr[min(j + 1, len(pr) - 1)] - pr[max(j - 1, 0)])
        a = norm(np.cross(grad(core0, c), t))
        for sgn in (1, -1):
            ends = []
            for q in (c - t * half_len - a * half_w * sgn, c + t * half_len + a * half_w * sgn):
                n_q = grad(core0, q)
                pq, _ = proj(body, q - n_q * 0.15, n_q, max_dist=0.4, n=160)
                ends.append(pq + n_q * 0.006 if pq is not None else q)
            out.append(capsule(tuple(ends[0]), tuple(ends[1]), r))
    return out


stitches = cross_stitches(SEAM[:15]) + cross_stitches(SEAM[15:]) + cross_stitches(SCAR, step=0.11)


def belly_grooves(p):
    g1 = np.abs(((p[:, 1] / 0.15) % 1.0) - 0.5) * 0.15 - 0.017
    g2 = np.abs(((p[:, 0] / 0.21 + 0.5) % 1.0) - 0.5) * 0.21 - 0.017
    return np.minimum(g1, g2)


belly = paint(body, belly_zone).subtract(SDF(belly_grooves, (-9, -9, -9), (9, 9, 9)))
m.add("Belly", belly, BELLY, role="detail", tris=3800, voxel=0.0326 * VX)

# ============================================================ placche dorsali che bruciano
SPINE = [tuple(Hp((0.0, 0.1, 0.12))), (0.05, -1.25, 1.17), (0.0, -0.95, 1.03), (0.0, -0.6, 0.95), (0.0, -0.2, 0.86),
         (0.0, 0.2, 0.82), (0.0, 0.6, 0.82)] + [tuple(p) for p in TAIL_PTS[2:]]
SPINE = resample(SPINE, 0.02)
_seg = np.linalg.norm(np.diff(SPINE, axis=0), axis=1)
SPINE_S = np.concatenate([[0.0], np.cumsum(_seg)])
SPINE_LEN = float(SPINE_S[-1])


def spine_at(s):
    i = int(np.clip(np.searchsorted(SPINE_S, s), 1, len(SPINE) - 1))
    t = (s - SPINE_S[i - 1]) / max(SPINE_S[i] - SPINE_S[i - 1], 1e-9)
    return SPINE[i - 1] * (1 - t) + SPINE[i] * t, norm(SPINE[i] - SPINE[i - 1])


# contorno di una placca alta 1 (u verso la coda, v in alto): fiamma frastagliata inclinata all'indietro
PLATE_POLY = [(-0.27, -0.22), (-0.31, 0.08), (-0.27, 0.34), (-0.17, 0.6), (-0.02, 0.84), (0.16, 1.0), (0.14, 0.8),
              (0.33, 0.78), (0.24, 0.58), (0.4, 0.48), (0.29, 0.32), (0.33, 0.12), (0.27, -0.22)]
_pd = poly2d(PLATE_POLY)


def plate_sdf(h, wid=1.0, phase=0.0):
    """Placca (coordinate locali: X spessore, Y verso la coda, Z in alto). Ritorna (placca, nucleo scuro)."""
    t0 = max(0.075 * h, 0.026)
    bev = 0.16 * h
    sw = h * wid

    def d2(p):
        return _pd(p[:, 1] / sw, p[:, 2] / h) * min(sw, h)

    def f(p):
        d = d2(p)
        v = np.clip(p[:, 2] / h, 0.0, 1.0)
        tx = t0 * (1.0 - 0.45 * v) * (0.4 + 0.6 * smoothstep(0.0, bev, -d))
        dx = np.abs(p[:, 0]) - tx
        r = 0.008
        d = d + r
        dx = dx + r
        return np.minimum(np.maximum(d, dx), 0.0) + np.sqrt(np.maximum(d, 0) ** 2 + np.maximum(dx, 0) ** 2) - r

    def core(p):
        # parte scura: sotto una linea a fiammelle e lontana dal bordo (che brucia)
        u = p[:, 1] / sw
        v = p[:, 2] / h
        line = 0.56 + 0.07 * np.sin(u * 28.0 + phase) + 0.04 * np.sin(u * 61.0 + 2 * phase)
        rim = 0.02 + 0.1 * h * v ** 2
        return np.maximum((v - line) * h, d2(p) + rim)

    ext = (t0 + 0.02, 0.42 * sw + 0.03, 1.02 * h + 0.03)
    lo, hi = (-ext[0], -0.33 * sw - 0.03, -0.24 * h), ext
    return SDF(f, lo, hi), SDF(core, lo, hi)


def plate_height(s):
    """Altezza delle placche lungo la spina: piccole sul collo, enormi su spalle e schiena, poi sempre piu' basse."""
    pts = [(0.0, 0.4), (0.35, 0.6), (0.8, 0.96), (1.25, 1.2), (1.7, 1.22), (2.15, 1.0), (2.55, 0.68), (3.2, 0.42),
           (4.0, 0.22), (SPINE_LEN, 0.1)]
    xs, ys = zip(*pts)
    return float(np.interp(s, xs, ys))


# collo e schiena: coppie di placche aperte a V (come un kentrosauro); coda: una fila sola che si rimpicciolisce
plates, plate_cores, fire_tips = [], [], []
s, i = 0.12, 0
while s < SPINE_LEN - 0.1:
    c, tan = spine_at(s)
    h = plate_height(s)
    paired = s < 2.6
    p_mid, n_mid = proj(core0, c, UP)
    side = norm(np.cross(tan, n_mid))
    for sx in ((1, -1) if paired else (0,)):
        if sx:
            p, _ = proj(core0, c + side * sx * (0.06 + 0.06 * h), n_mid)
            nrm = norm(n_mid + side * sx * 0.45)
        else:
            p, nrm = p_mid, n_mid
        mtx = frame_matrix(nrm, tan)
        pl, pc = plate_sdf(h, wid=1.0 if h > 0.3 else 1.3, phase=i * 1.7 + sx)
        pos = p - nrm * (0.05 + 0.05 * h)
        plates.append(place(pl, mtx, pos))
        plate_cores.append(place(pc, mtx, pos))
        fire_tips.append(pos + mtx @ np.array([0, 0.16 * h, h], dtype=np.float32))
    s += (0.1 + 0.5 * h) if paired else (0.1 + 0.62 * h)
    i += 1
log(f"placche: {len(plates)}")

# file laterali di spuntoni (anchilosauro) sopra i fianchi e lungo la coda, con la punta che brucia
spike_dark, spike_fire = [], []
LATERAL = [(s_, 56.0, 0.25 - 0.06 * abs(s_ - 1.6)) for s_ in np.arange(0.62, 2.5, 0.3)]
LATERAL += [(s_, 70.0, 0.2 * (1.0 - (s_ - 2.7) / 1.7)) for s_ in np.arange(2.7, 4.1, 0.27)]
for s_, ang, hh in LATERAL:
    c, tan = spine_at(s_)
    upp = norm(UP - tan * float(np.dot(UP, tan)))
    side = norm(np.cross(tan, upp))
    for sx in (1, -1):
        d = upp * math.cos(math.radians(ang)) + side * sx * math.sin(math.radians(ang))
        p, n = proj(core0, c, d)
        if p is None:
            continue
        ax = norm(n + tan * 0.5 + upp * 0.15)
        r0 = 0.05 + 0.18 * hh
        base = p - ax * 0.05
        spike_dark.append(round_cone(tuple(base), tuple(base + ax * (0.05 + hh * 0.62)), r0, r0 * 0.5))
        spike_fire.append(round_cone(tuple(base + ax * (0.05 + hh * 0.55)), tuple(base + ax * (0.05 + hh)), r0 * 0.56 + 0.006,
                                     0.012))
log(f"spuntoni laterali: {len(spike_dark)}")

# corna all'indietro sul cranio e spuntoni sulle guance (rosso bruciato con la punta che brucia)
HORNS = [((0.25, 0.08, 0.3), (0.33, 0.3, 0.42), (0.4, 0.48, 0.52), (0.46, 0.62, 0.66), 0.085),
         ((0.38, 0.02, -0.06), (0.5, 0.16, -0.1), (0.6, 0.3, -0.12), (0.68, 0.42, -0.1), 0.065),
         ((0.16, 0.16, 0.36), (0.18, 0.3, 0.46), (0.2, 0.4, 0.52), (0.22, 0.5, 0.56), 0.05)]
horn_dark, horn_fire = [], []
for sx in (1, -1):
    for a, b, c2, d, r0 in HORNS:
        pts = bezier(*[(sx * q[0], q[1], q[2]) for q in (a, b, c2, d)], 12)
        radii = [r0 * (1 - 0.88 * (j / 12) ** 1.1) for j in range(13)]
        horn_dark.append(tube(pts[:10], radii[:10]))
        horn_fire.append(tube(pts[8:], radii[8:]).offset(0.006))
        fire_tips.append(Hp(pts[-1]))

plates_u = fast_union(plates)
cores_u = fast_union(plate_cores, margin=0.08)
plate_dark = plates_u.intersect(cores_u.offset(-0.02))
m.add("Plates", fast_union([plate_dark, H(union(*horn_dark)), fast_union(spike_dark)]), PLATE, role="detail", tris=7000,
      voxel=0.0252 * VX)
plate_fire = plates_u.offset(0.009).intersect(SDF(lambda p: -cores_u(p), cores_u.lo, cores_u.hi))


# ============================================================ bocca, denti, lingua (coordinate locali della testa)


def hw_mouth(y):
    return np.interp(y, [-1.2, -1.07, -0.95, -0.7, -0.35, 0.0], [0.0, 0.12, 0.19, 0.245, 0.31, 0.33])


def mouth_fn(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    d_up = z - (lip_up(y) + 0.03)
    q = (p - HINGE) @ R_JAW + HINGE
    d_lo = (lip_lo(q[:, 1]) - 0.03) - q[:, 2]
    d_w = np.abs(x) - (hw_mouth(y) - 0.05)
    d_f = -1.0 - y
    d_b = y - 0.04
    d = smax(d_up, d_lo, 0.04)
    for other in (d_w, d_f, d_b):
        d = smax(d, other, 0.05)
    return d


mouth_wedge = SDF(mouth_fn, (-0.4, -1.1, -0.6), (0.4, 0.1, 0.1))
cavity = ellipsoid((0.2, 0.62, 0.17), (0, -0.92, -0.17)).rot(-JAW_OPEN * 0.5, 0, 0, pivot=(0, -0.92, -0.17))
mouth_dark = mouth_wedge.subtract(cavity, k=0.04)
throat_fire = ellipsoid((0.14, 0.12, 0.11), (0, -0.5, -0.2))
nostril_fire = union(*[ellipsoid((0.04, 0.035, 0.03), (sx * 0.06, -1.05, 0.165)) for sx in (1, -1)])


def tooth(b, t, r, lean):
    mid = b + (t - b) * 0.5 + lean
    return tube([tuple(b), tuple(mid), tuple(t)], [r, r * 0.62, 0.006])


# denti: lungo il bordo delle labbra, lunghezze irregolari (frastagliati), zanne da coccodrillo
TEETH_UP = [(-0.06, 0.07), (-0.16, 0.1), (-0.27, 0.08), (-0.37, 0.12), (-0.48, 0.09), (-0.58, 0.13), (-0.68, 0.1),
            (-0.78, 0.19), (-0.87, 0.11), (-0.95, 0.14)]
TEETH_LO = [(-0.12, 0.06), (-0.23, 0.08), (-0.34, 0.1), (-0.45, 0.08), (-0.56, 0.11), (-0.67, 0.09), (-0.78, 0.12),
            (-0.9, 0.2), (-0.99, 0.1)]
teeth_up, teeth_lo = [], []
for sx in (1, -1):
    for y, L in TEETH_UP:
        z = float(lip_up(y))
        e, _ = project(upper, (0.0, y, z + 0.03), (sx, 0, 0))
        b = np.array([e[0] - sx * 0.035, y, z + 0.03])
        t = np.array([e[0] - sx * 0.008, y + 0.03, z - L])
        teeth_up.append(tooth(b, t, 0.032 + 0.11 * L, np.array([0, -0.012, 0])))
    for y, L in TEETH_LO:
        z = float(lip_lo(y))
        e, _ = project(lower, (0.0, y, z - 0.03), (sx, 0, 0))
        b = np.array([e[0] - sx * 0.035, y, z - 0.03])
        t = np.array([e[0] - sx * 0.006, y + 0.025, z + L])
        teeth_lo.append(tooth(b, t, 0.03 + 0.11 * L, np.array([0, -0.012, 0])))
# denti davanti, sulla curva della U
for ang, L in ((14, 0.09), (36, 0.12)):
    for sx in (1, -1):
        d = np.array((sx * math.sin(math.radians(ang)), -math.cos(math.radians(ang)), 0.0))
        z = float(lip_up(-1.05))
        e, _ = project(upper, (0.0, -0.85, z + 0.03), d)
        b = e - d * 0.035 + np.array([0, 0, 0.03])
        t = e - d * 0.01 + np.array([0, 0.025, -L])
        teeth_up.append(tooth(b, t, 0.032 + 0.11 * L, np.array([0, -0.01, 0])))
        z = float(lip_lo(-1.0))
        e, _ = project(lower, (0.0, -0.85, z - 0.03), d)
        b = e - d * 0.035 + np.array([0, 0, -0.03])
        t = e - d * 0.01 + np.array([0, 0.02, L * 0.9])
        teeth_lo.append(tooth(b, t, 0.03 + 0.11 * L, np.array([0, -0.01, 0])))
teeth_w = union(H(fast_union(teeth_up)), J(fast_union(teeth_lo)))

# lingua biforcuta che guizza fuori dalla bocca
TONGUE_PTS = bezier((0.0, -0.55, -0.16), (0.0, -1.0, -0.2), (0.03, -1.24, -0.3), (0.05, -1.38, -0.22), 14)
tongue_main = tube(TONGUE_PTS, [0.05 - 0.0012 * i for i in range(15)])
tip = np.array(TONGUE_PTS[-1])
forks = [tube(bezier(tuple(tip), tuple(tip + (sx * 0.03, -0.06, 0.0)), tuple(tip + (sx * 0.08, -0.12, 0.03)),
                     tuple(tip + (sx * 0.1, -0.17, 0.08)), 6), [0.03, 0.028, 0.025, 0.02, 0.015, 0.011, 0.007])
         for sx in (1, -1)]
tongue_w = H(union(tongue_main, *forks, k=0.02))

eyes = union(*[H(f.place(ellipsoid(EYE_R))) for f in eye_frames.values()])
pupils = union(*[H(f.place(ellipsoid((0.021, 0.034, 0.076)), (0.0, -EYE_R[1] + 0.016, -0.006)))
                 for f in eye_frames.values()])
eye_shine = union(*[H(f.place(sphere(0.022), (-sx * 0.042, -EYE_R[1] + 0.01, 0.026))) for sx, f in eye_frames.items()])

# ============================================================ artigli ricurvi (osso)
claws = []
for p2, d in toe_tips:
    a = p2 + d * 0.02
    pts = bezier(tuple(a), tuple(a + d * 0.08 + np.array([0, 0, 0.035])), tuple(a + d * 0.17 + np.array([0, 0, 0.005])),
                 tuple(a + d * 0.22 + np.array([0, 0, -0.058])), 8)
    claws.append(tube(pts, [0.05, 0.048, 0.044, 0.037, 0.03, 0.022, 0.015, 0.01, 0.006]))

# ============================================================ fuoco: tutto in un'unica parte "Flames"
flames = fast_union([plate_fire, H(union(throat_fire, nostril_fire, *horn_fire)), cracks, fast_union(spike_fire)])
m.add("Flames", flames, FIRE, material="Neon", role="glow", tris=12800, voxel=0.0206 * VX)
m.add("Claws", fast_union(claws + stitches), BONE, role="detail", tris=3000, voxel=0.0175 * VX)
m.add("Teeth", teeth_w, BONE, role="shine", tris=3400, voxel=0.0159 * VX)
m.add("Mouth", H(mouth_dark), MOUTH, role="eye", tris=900, voxel=0.032 * VX)
m.add("Tongue", tongue_w, TONGUE, role="detail", tris=600, voxel=0.016 * VX)
m.add("EyeGlow", eyes, EYE_GLOW, material="Neon", role="glow", tris=550, voxel=0.015 * VX)
m.add("Pupils", pupils, PUPIL, role="eye", tris=200, voxel=0.011 * VX)
m.add("Shine", eye_shine, WHITE, role="shine", tris=150, voxel=0.007 * VX)

m.meta["fireTips"] = [[round(float(-p[0]), 3), round(float(p[2]), 3), round(float(p[1]), 3)] for p in fire_tips]

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
    log("fatto")
