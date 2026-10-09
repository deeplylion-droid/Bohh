"""Titano Rex (TitanRex) - pet ULTRA, il livello piu' alto.

Un tirannosauro titanico evaso dalla sua prigione, in posa d'attacco: corpo proteso in avanti,
testa che si lancia verso chi guarda con le fauci spalancate (gola scura, lingua enorme, file di
denti frastagliati color osso su gengive scoperte), cranio massiccio con arcate sopraccigliari
pesanti e corna nere, zampe enormi e muscolose con artigli giganti, braccine corte ma cattive
alzate, coda spessa sollevata. Pelle rosso sangue a strisce nere da tigre, pancia rosso polvere a
placche, spine e scudi ossei neri lungo la schiena. Occhi, cicatrici di artigli e vene brillano
di rabbia (parte Neon "Rage": il gioco ci attacca braci e vapore). Tocco "toy horror": cucitura
a punti incrociati sul petto e una cavigliera di ferro con la catena spezzata.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, capsule, ellipsoid, euler, halfspace_z, round_cone, smin,  # noqa: E402
                     sphere, tube, union, bezier)
from lib.toy import Model  # noqa: E402


# ============================================================ helper (lib/ non si modifica: copiati/adattati qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def grad_many(sdf, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float64).reshape(-1, 3)
    g = np.zeros_like(p)
    for ax in range(3):
        e = np.zeros(3)
        e[ax] = eps
        g[:, ax] = sdf((p + e).astype(np.float32)) - sdf((p - e).astype(np.float32))
    return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)


def project_many(sdf, origins, dirs, max_dist=3.0, steps=300, iters=26):
    """Come project() della libreria, ma per tanti raggi insieme: ritorna (punti, normali)."""
    o = np.asarray(origins, dtype=np.float64).reshape(-1, 3)
    d = np.asarray(dirs, dtype=np.float64).reshape(-1, 3)
    if len(d) == 1 and len(o) > 1:
        d = np.repeat(d, len(o), axis=0)
    d = d / np.linalg.norm(d, axis=1, keepdims=True)
    n = len(o)
    ts = np.linspace(0.0, max_dist, steps)
    pts = (o[:, None, :] + ts[None, :, None] * d[:, None, :]).reshape(-1, 3).astype(np.float32)
    vals = sdf(pts).reshape(n, steps)
    if (vals[:, 0] > 0).any():
        bad = np.nonzero(vals[:, 0] > 0)[0]
        print(f"[titan] attenzione: {len(bad)} raggi partono fuori dalla forma, es. {np.round(o[bad[0]], 3)}")
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


def paint(core, region, out=0.016, inn=0.035, margin=0.05):
    """Strato di "vernice" sottile (guscio fra -inn e +out attorno a core) dentro 'region'.

    Come core.offset(out).subtract(core.offset(-inn)).intersect(region), ma valuta core solo
    vicino alla regione (molto piu' veloce sulle forme complesse).
    """
    def f(p):
        r = region(p)
        d = np.maximum(r, margin).astype(np.float32)
        idx = np.nonzero(r < margin)[0]
        if len(idx):
            c = core(p[idx])
            d[idx] = np.maximum(np.maximum(c - out, -c - inn), r[idx])
        return d

    return SDF(f, np.maximum(core.lo - out, region.lo), np.minimum(core.hi + out, region.hi))


def shrink(s, step=0.05, pad=0.03):
    """Ricalcola un ingombro stretto (le unioni morbide annidate lo gonfiano) campionando la forma."""
    lo, hi = s.lo.astype(np.float64), s.hi.astype(np.float64)
    n = np.maximum(np.ceil((hi - lo) / step).astype(int) + 1, 2)
    xs, ys, zs = (np.linspace(lo[i], hi[i], n[i]) for i in range(3))
    gy, gz = np.meshgrid(ys, zs, indexing="ij")
    plane = np.stack([np.zeros_like(gy), gy, gz], -1).reshape(-1, 3).astype(np.float32)
    a, b = np.full(3, np.inf), np.full(3, -np.inf)
    for x in xs:
        plane[:, 0] = x
        msk = s(plane) < step * 1.5
        if msk.any():
            pts = plane[msk]
            a, b = np.minimum(a, pts.min(0)), np.maximum(b, pts.max(0))
    return SDF(s.f, a - step - pad, b + step + pad)


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


def orient(axis, side=(1.0, 0.0, 0.0)):
    """Matrice che porta l'asse Z locale su 'axis' (e X locale il piu' possibile verso 'side')."""
    a = norm(axis)
    s = np.asarray(side, dtype=np.float64)
    s = s - a * float(s @ a)
    if np.linalg.norm(s) < 1e-6:
        s = np.array([0.0, 1.0, 0.0]) - a * a[1]
    s = norm(s)
    return np.stack([s, np.cross(a, s), a], axis=1).astype(np.float32)


def ell(c, radii, axis=(0, 0, 1), side=(1, 0, 0)):
    """Ellissoide con il terzo raggio lungo 'axis'."""
    return ellipsoid(radii).rotate(orient(axis, side)).translate(c)


def loft(y0, y1, w0, w1, h0, h1, z0, z1, r, rc=0.0):
    """Box arrotondato che si restringe lungo Y (da y0 a y1): mezza larghezza w, mezza altezza h, centro z.

    r arrotonda gli spigoli della sezione, rc i bordi delle due facce di testa.
    """
    ya, yb = min(y0, y1), max(y0, y1)

    def f(p):
        t = np.clip((p[:, 1] - y0) / (y1 - y0), 0.0, 1.0)
        w = w0 + (w1 - w0) * t
        h = h0 + (h1 - h0) * t
        zc = z0 + (z1 - z0) * t
        qx = np.abs(p[:, 0]) - (w - r)
        qz = np.abs(p[:, 2] - zc) - (h - r)
        d2 = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qz, 0) ** 2) + np.minimum(np.maximum(qx, qz), 0) - r
        dy = np.maximum(p[:, 1] - yb, ya - p[:, 1])
        a, b = d2 + rc, dy + rc
        return np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2) + np.minimum(np.maximum(a, b), 0) - rc

    wm = max(w0, w1)
    return SDF(f, (-wm, ya, min(z0 - h0, z1 - h1)), (wm, yb, max(z0 + h0, z1 + h1)))


def pie(c, r, a_lo, a_hi, half_w):
    """Spicchio attorno all'asse X passante per c: angoli (gradi) misurati dall'avanti (-Y) verso l'alto."""
    lo_, hi_ = math.radians(a_lo), math.radians(a_hi)
    c = np.asarray(c, dtype=np.float32)

    def f(p):
        fy = -(p[:, 1] - c[1])
        dz = p[:, 2] - c[2]
        rr = np.sqrt(fy * fy + dz * dz) - r
        d1 = dz * math.cos(hi_) - fy * math.sin(hi_)
        d2 = -(dz * math.cos(lo_) - fy * math.sin(lo_))
        return np.maximum(np.maximum(rr, np.abs(p[:, 0]) - half_w), np.maximum(d1, d2))

    return SDF(f, (-half_w, c[1] - r, c[2] - r), (half_w, c[1] + r, c[2] + r))


def plane_sdf(point, normal, lo=(-6, -6, -6), hi=(6, 6, 6)):
    """Semispazio: dentro dove (p - point) . normal < 0."""
    pt = np.asarray(point, dtype=np.float32)
    n = norm(normal).astype(np.float32)
    return SDF(lambda p: (p - pt) @ n, lo, hi)


def horn(base, d, L, r0, curl=(0, 0, 0), n=5, r1=0.006, power=1.0):
    """Cono curvo (corno, artiglio, dente): parte da base verso d (lunghezza L) e si piega verso 'curl'."""
    base, d, c = np.asarray(base, float), norm(d), np.asarray(curl, float)
    ts = np.linspace(0.0, 1.0, n)
    pts = [tuple(base + d * L * t + c * L * t * t) for t in ts]
    return tube(pts, [r0 + (r1 - r0) * t ** power for t in ts])


def rot_pts(R, pts, pivot=(0, 0, 0)):
    pv = np.asarray(pivot, dtype=np.float64)
    return (np.asarray(pts, dtype=np.float64) - pv) @ np.asarray(R, dtype=np.float64).T + pv


# ============================================================ colori
SKIN = (126, 14, 24)        # cremisi scuro, rosso sangue
STRIPE = (24, 12, 16)       # strisce nere da tigre
BELLY = (196, 98, 86)       # pancia rosso polvere
BONE = (246, 236, 212)      # denti e artigli color osso
SPIKE = (32, 24, 28)        # spine, corna e scudi neri
MAW = (36, 6, 12)           # gola e interno della bocca
GUM = (168, 44, 62)
TONGUE = (206, 78, 98)
RAGE = (255, 44, 18)        # neon rosso-arancio
THREAD = (18, 10, 12)
IRON = (84, 80, 86)

m = Model("TitanRex", "pet")

# ============================================================ testa (spazio locale: origine sulla nuca, muso verso -Y)
HEAD_POS = np.array([0.0, -0.80, 3.00])
HS = 1.2                                 # scala della testa
R_HEAD = euler(-2.0, 5.0, 7.0)          # muso dritto, testa inclinata e girata verso la camera 3/4
GAPE = 52.0                              # apertura delle fauci (gradi)
J = np.array([0.0, -0.18, -0.24])       # cerniera della mandibola
R_JAW = euler(GAPE, 0.0, 0.0)


def H(s):
    return s.scale(HS).rotate(R_HEAD).translate(HEAD_POS)


def hp(p):
    return rot_pts(R_HEAD, np.asarray(p, dtype=np.float64) * HS) + HEAD_POS


def JW(s):
    return s.rotate(R_JAW, pivot=J)


def jp(p):
    return rot_pts(R_JAW, p, J)


# --- cranio, guance, muso squadrato, arcate sopraccigliari
cran = ellipsoid((0.45, 0.42, 0.37), (0, -0.30, 0.14))
jowls = [ellipsoid((0.21, 0.30, 0.25), (sx * 0.33, -0.34, -0.06)) for sx in (1, -1)]
snout = loft(-0.40, -1.40, 0.35, 0.22, 0.29, 0.185, 0.06, -0.035, r=0.11, rc=0.08)
tipcap = ellipsoid((0.22, 0.13, 0.19), (0, -1.37, -0.04))
brows = [capsule((sx * 0.13, -0.80, 0.29), (sx * 0.41, -0.52, 0.41), 0.085) for sx in (1, -1)]
lower_lids = [capsule((sx * 0.22, -0.78, 0.10), (sx * 0.41, -0.57, 0.12), 0.04) for sx in (1, -1)]
nasal = [capsule((sx * 0.085, -1.30, 0.17), (sx * 0.12, -0.86, 0.29), 0.045) for sx in (1, -1)]
nost_bumps = [ellipsoid((0.075, 0.09, 0.055), (sx * 0.105, -1.33, 0.13)) for sx in (1, -1)]
upper = union(cran, *jowls, k=0.18)
upper = union(upper, snout, tipcap, k=0.16)
upper = union(upper, *brows, *lower_lids, k=0.08)
upper = union(upper, *nasal, *nost_bumps, k=0.05)

# --- mandibola (chiusa) poi aperta attorno alla cerniera
mand = loft(-0.02, -1.26, 0.33, 0.19, 0.23, 0.12, -0.46, -0.34, r=0.1, rc=0.08)
chin = ellipsoid((0.19, 0.12, 0.13), (0, -1.21, -0.35))
masseter = [ellipsoid((0.17, 0.28, 0.21), (sx * 0.28, -0.30, -0.42)) for sx in (1, -1)]
lower_closed = union(mand, chin, *masseter, k=0.12)
lower = JW(lower_closed)

# --- pelle che unisce le fauci dietro (angolo della bocca)
web = pie(J, 0.36, -GAPE - 8.0, 12.0, 0.33)
head_solid = union(upper, lower, k=0.1)
head_solid = shrink(union(head_solid, web, k=0.12))

# --- cavita' della bocca: canale superiore, canale inferiore (ruotato), gola
beta = math.radians(GAPE / 2)
n_up = np.array([0.0, -math.sin(beta), math.cos(beta)])
above_bis = plane_sdf(J, -n_up)
below_bis = plane_sdf(J, n_up)
up_ch = loft(0.05, -1.30, 0.24, 0.115, 0.6, 0.6, -0.66, -0.72, r=0.08, rc=0.1)
lo_ch = loft(0.05, -1.16, 0.23, 0.10, 0.6, 0.6, 0.20, 0.26, r=0.08, rc=0.1)
throat = ellipsoid((0.19, 0.30, 0.22), (0.0, -0.08, -0.30))
cavity = union(up_ch.intersect(above_bis), JW(lo_ch).intersect(below_bis), throat, k=0.05)

# ============================================================ corpo (spazio Blender)
torso = union(
    ellipsoid((0.58, 0.58, 0.58), (0, 0.32, 1.72)),     # bacino
    ellipsoid((0.66, 0.64, 0.70), (0, -0.05, 1.88)),    # ventre
    ellipsoid((0.64, 0.58, 0.66), (0, -0.42, 2.16)),    # torace
    ellipsoid((0.54, 0.48, 0.52), (0, -0.56, 2.50)),    # spalle
    k=0.3)
NECK_PTS = [(0, -0.55, 2.46), (0, -0.70, 2.78), (0, -0.80, 2.98)]
neck = tube(NECK_PTS, [0.52, 0.49, 0.45], k=0.1)
throat_skin = ell(hp((0.0, -0.40, -0.55)), (0.34, 0.30, 0.46), axis=(0, -0.45, -1.0))

# zampe: sinistra (+x) avanti che pesta, destra (-x) indietro
LEGS = {
    1: dict(hip=(0.52, 0.18, 1.56), knee=(0.63, -0.36, 0.96), ankle=(0.67, -0.16, 0.31), ball=(0.68, -0.50, 0.14),
            yaw=-8.0),
    -1: dict(hip=(-0.52, 0.32, 1.56), knee=(-0.58, 0.06, 0.86), ankle=(-0.64, 0.64, 0.37), ball=(-0.66, 0.44, 0.14),
             yaw=6.0),
}
leg_parts, TOES = [], []
for sx, L in LEGS.items():
    hip, knee, ankle, ball = (np.array(L[k]) for k in ("hip", "knee", "ankle", "ball"))
    fem = knee - hip
    leg_parts += [
        round_cone(hip, knee, 0.56, 0.28),
        ell(hip + fem * 0.42 + np.array([sx * 0.07, -0.06, 0.0]), (0.47, 0.50, 0.60), axis=fem),   # coscia enorme
        ell(hip + fem * 0.56 + np.array([sx * 0.19, -0.13, 0.0]), (0.26, 0.28, 0.44), axis=fem),   # quadricipite
        round_cone(knee, ankle, 0.27, 0.165),
        ell(knee + (ankle - knee) * 0.3 + np.array([0, 0.10, 0.03]), (0.21, 0.23, 0.35), axis=ankle - knee),  # polpaccio
        round_cone(ankle, ball, 0.17, 0.15),
        ellipsoid((0.22, 0.25, 0.13), tuple(ball + np.array([0, -0.05, -0.01]))),
    ]
    yaw = L["yaw"]
    for j, a in enumerate((-26.0, 0.0, 26.0)):
        ang = math.radians(a + yaw)
        d = np.array([math.sin(ang), -math.cos(ang), 0.0])
        ln = 0.52 if a == 0 else 0.43
        p0 = ball + np.array([0, 0, -0.01])
        p1 = p0 + d * ln * 0.5 + np.array([0, 0, -0.02])
        p2 = p0 + d * ln + np.array([0, 0, -0.04])
        leg_parts.append(tube([tuple(p0), tuple(p1), tuple(p2)], [0.15, 0.13, 0.10]))
        leg_parts.append(ellipsoid((0.105, 0.105, 0.09), tuple(p1 + np.array([0, 0, 0.025]))))  # nocca
        TOES.append((p2, d))
legs = union(*leg_parts, k=0.08)

# braccine corte alzate, due dita
ARMS = []
arm_parts = []
for sx in (1, -1):
    sh = np.array([sx * 0.40, -0.80, 2.08])
    el = np.array([sx * 0.57, -0.99, 1.88])
    wr = np.array([sx * 0.53, -1.23, 2.02])
    arm_parts += [round_cone(sh, el, 0.14, 0.095), round_cone(el, wr, 0.095, 0.078),
                  ell(sh + (el - sh) * 0.4 + np.array([0, -0.03, 0.03]), (0.115, 0.115, 0.16), axis=el - sh)]
    for dx in (0.055, -0.055):
        f = np.array([sx * 0.05 + dx, -0.11, -0.03])
        arm_parts.append(round_cone(wr, wr + f, 0.066, 0.05))
        ARMS.append((wr + f, norm(f + np.array([0, -0.04, -0.06]))))
arms = union(*arm_parts, k=0.04)

# coda (parte separata, gruppo "Tail") e moncone nel corpo
TAIL_PTS = bezier((0.0, 0.55, 1.80), (0.0, 1.30, 2.02), (0.38, 1.95, 2.40), (0.95, 2.18, 2.80), 16)
TAIL_R = [0.06 + 0.46 * (1 - i / 16) ** 1.15 for i in range(17)]
TAIL_PIVOT = (0.0, 0.62, 1.81)
stump = tube(TAIL_PTS[:5], [r - 0.03 for r in TAIL_R[:5]])

core = union(torso, neck, k=0.25)
core = union(core, H(head_solid), k=0.18)
core = union(core, throat_skin, k=0.2)
core = union(core, stump, k=0.2)
core = union(core, legs, k=0.12)
core = union(core, arms, k=0.07)
core = core.subtract(H(cavity), k=0.03)
# narici
nostrils = union(*[ellipsoid((0.035, 0.05, 0.03), (sx * 0.11, -1.395, 0.145)) for sx in (1, -1)])
core = core.subtract(H(nostrils), k=0.02)
core = shrink(core.intersect(halfspace_z(0.0, above=True)))
m.add("Body", core, SKIN, tris=15000, voxel=0.02)

tail = tube(TAIL_PTS, TAIL_R, k=0.0)
m.add("Tail", tail, SKIN, role="skin", tris=4000, voxel=0.02, group="Tail", pivot=TAIL_PIVOT)

# ============================================================ denti frastagliati su gengive scoperte
rng = np.random.default_rng(7)


def rim_path(w_back, w_front, y_back, y_front, y_tip, n_side=40, n_arc=16):
    """Linea dei denti di un lato (da dietro al centro davanti) nel piano XY locale."""
    pts = [(w_back + (w_front - w_back) * t, y_back + (y_front - y_back) * t) for t in np.linspace(0, 1, n_side)]
    for a in np.linspace(0, math.pi / 2, n_arc)[1:]:
        pts.append((w_front * math.cos(a), y_front - (y_front - y_tip) * math.sin(a)))
    return np.array(pts)


def tooth_row(jaw_sdf, path, z_in, down, lengths, r_scale=0.24, back_lean=0.28, out_lean=0.10, lift=0.0):
    """Denti lungo 'path' (un lato, da dietro a davanti): proiezione sul bordo della mascella."""
    path3 = np.array([[x, y, z_in] for x, y in path])
    seg = np.linalg.norm(np.diff(path3, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    n = len(lengths)
    teeth, gums = [], []
    ss = np.linspace(cum[-1] * 0.03, cum[-1] * 0.985, n)
    pos = np.array([path3[min(np.searchsorted(cum, s, side="right") - 1, len(seg) - 1)] for s in ss])
    for i, s in enumerate(ss):
        k = min(np.searchsorted(cum, s, side="right") - 1, len(seg) - 1)
        t = (s - cum[k]) / max(seg[k], 1e-9)
        pos[i] = path3[k] * (1 - t) + path3[k + 1] * t
    rims, nrm = project_many(jaw_sdf, pos, np.array([[0, 0, down]]))
    for i, (p, L) in enumerate(zip(rims, lengths)):
        x = p[0]
        side = math.copysign(1.0, x) if abs(x) > 0.02 else 0.0
        d = np.array([side * out_lean + rng.normal(0, 0.06), back_lean + rng.normal(0, 0.07), down])
        d = norm(d)
        r = r_scale * L * 0.55 + 0.022
        base = p - d * 0.06
        curl = np.array([0.0, 0.18, 0.0])
        teeth.append(horn(base, d, L + 0.06, r, curl=curl, n=4, r1=0.005, power=1.25))
        gums.append(ellipsoid((r * 1.45, r * 1.45, r * 1.1), tuple(p - np.array([0, 0, down]) * 0.012)))
    return teeth, gums, rims


# denti superiori: lunghezze irregolari (zanne enormi in mezzo, qualcuno spezzato)
UP_L = [0.10, 0.12, 0.22, 0.27, 0.16, 0.24, 0.20, 0.13, 0.18, 0.12, 0.09]
LO_L = [0.09, 0.11, 0.20, 0.15, 0.22, 0.17, 0.12, 0.15, 0.09]
teeth_all, gums_all = [], []
for sx in (1, -1):
    upath = rim_path(0.265, 0.205, -0.50, -1.16, -1.385)
    upath[:, 0] *= sx
    ul = [L * (1 + rng.normal(0, 0.08)) for L in UP_L[::-1]]
    t_, g_, _ = tooth_row(upper, upath, -0.10, -1.0, ul)
    teeth_all += [H(t) for t in t_]
    gums_all += [H(g) for g in g_]
    lpath = rim_path(0.245, 0.185, -0.52, -1.08, -1.27)
    lpath[:, 0] *= sx
    ll = [L * (1 + rng.normal(0, 0.08)) for L in LO_L[::-1]]
    t_, g_, _ = tooth_row(lower_closed, lpath, -0.36, 1.0, ll, back_lean=0.22)
    teeth_all += [H(JW(t)) for t in t_]
    gums_all += [H(JW(g)) for g in g_]
m.add("Teeth", fast_union(teeth_all), BONE, role="shine", tris=6000, voxel=0.011)
m.add("Gums", fast_union(gums_all, k=0.03).intersect(core.offset(0.03)), GUM, role="detail", tris=2500, voxel=0.012)

# lingua grossa con il solco centrale, punta che si alza
tongue_l = union(ellipsoid((0.17, 0.34, 0.09), (0, -0.48, -0.33)),
                 ellipsoid((0.14, 0.20, 0.085), (0, -0.86, -0.28)).rot(-12, 0, 0, pivot=(0, -0.86, -0.28)), k=0.1)
tongue_l = tongue_l.subtract(capsule((0, -0.25, -0.22), (0, -0.98, -0.18), 0.022), k=0.03)
m.add("Tongue", H(JW(tongue_l)), TONGUE, role="detail", tris=1500, voxel=0.012)

# interno scuro della bocca (rivestimento della cavita') + pupille a fessura
maw = paint(core, H(cavity).offset(0.02), out=0.012, inn=0.03)

# occhi: mandorla inclinata (angolo verso il muso piu' basso) incassata sotto l'arcata
eye_frames = [Frame(upper, (sx * 0.12, -0.62, 0.18), (sx * 0.85, -0.55, 0.08), sink=0.035) for sx in (1, -1)]
eyes, pupils = [], []
for f, sx in zip(eye_frames, (1, -1)):
    eyes.append(H(f.place(ellipsoid((0.105, 0.05, 0.062)).rot(0, sx * 18, 0))))
    pupils.append(H(f.place(ellipsoid((0.016, 0.02, 0.05)), (0.0, -0.035, 0.0))))
m.add("Maw", union(maw, *pupils), MAW, role="eye", tris=2500, voxel=0.012)

# artigli: piedi (enormi, uncinati verso terra) e mani
claws = []
for p, d in TOES:
    base = p - d * 0.02 + np.array([0, 0, 0.035])
    claws.append(horn(base, d + np.array([0, 0, 0.08]), 0.24, 0.072, curl=(0, 0, -0.55), n=5, r1=0.006))
for p, d in ARMS:
    claws.append(horn(p - d * 0.01, d, 0.12, 0.038, curl=(0, 0, -0.55), n=4, r1=0.004))
claws = fast_union(claws).intersect(halfspace_z(0.004, above=True))
m.add("Claws", claws, BONE, role="detail", tris=2500, voxel=0.012)

m.add("Rage", union(*eyes), RAGE, material="Neon", role="glow", tris=1500, voxel=0.012)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
