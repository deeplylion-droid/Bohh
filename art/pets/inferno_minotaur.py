"""Minotauro Infernale (InfernoMinotaur) - pet PRIMORDIALE, il grado fra Segreto e Ultra (zona: Cratere Vulcanico).

Il guardiano del cratere: un minotauro enorme e muscoloso, in piedi su gambe da toro con gli zoccoli
spaccati, che alza sopra la testa con tutte e due le mani una gigantesca ascia bipenne di ferro dal
filo incandescente (l'ascia e' dritta in alto, pronta a calare). Pelle rosso-bruna solcata da vene di
lava che brillano su petto, addominali, braccia e cosce; criniera ispida nera su collo e spalle,
ciuffi di pelo sopra gli zoccoli e in fondo alla coda. Testa di toro furiosa: corna d'avorio
gigantesche con le punte in fiamme (parte Neon "Flames": il gioco ci attacca il fuoco), occhi di
brace sotto la fronte aggrottata, narici dilatate che sbuffano fuoco, ringhio a fauci aperte con
zanne aguzze e un grosso anello di ferro al naso. Bracciali di ferro chiodati, cintura di cuoio
borchiata e perizoma rosso sangue sfrangiato. Le vene di lava e il filo dell'ascia sono la parte Neon
"Rage" (braci che salgono dal corpo).
Tocco "toy horror": una grossa toppa di stoffa cucita a punti incrociati sulla spalla sinistra e un
enorme bottone da cucito al posto della fibbia della cintura.
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

rng = np.random.default_rng(29)


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
        print(f"[minotaur] attenzione: {len(bad)} raggi partono fuori dalla forma, es. {np.round(o[bad[0]], 3)}")
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


def band(R, t, h, rr=0.014):
    """Fascia (anello a sezione rettangolare arrotondata) nel piano XY: raggio R, spessore 2t, altezza 2h."""
    def f(p):
        rho = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2) - R
        qx = np.abs(rho) - (t - rr)
        qz = np.abs(p[:, 2]) - (h - rr)
        return np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qz, 0) ** 2) + np.minimum(np.maximum(qx, qz), 0) - rr

    e = R + t
    return SDF(f, (-e, -e, -h), (e, e, h))


def flame(L, r0, bend=0.6, wig=0.06, flat=0.62, n=12, fork=0.0):
    """Lingua di fuoco (locale: base nell'origine, sale lungo +Z e si piega verso +Y, piatta lungo X)."""
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
    """Linea spezzata da a a b con n segmenti e scarti laterali alternati (vene e crepe frastagliate)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    side = norm(np.cross(b - a, normal_hint))
    pts = []
    for j in range(n + 1):
        t = j / n
        off = 0.0 if j in (0, n) else (1 if j % 2 else -1) * amp * rng.uniform(0.5, 1.0)
        pts.append(a + (b - a) * t + side * off)
    return pts


def tuft(L, r0, curl=0.25):
    """Ciuffo di pelo (locale: base nell'origine, punta lungo +Z piegata verso +Y), appiattito."""
    pts = bezier((0, 0, -0.03), (0, 0.0, L * 0.4), (0, curl * L * 0.4, L * 0.75), (0, curl * L, L), 6)
    return flatten(tube(pts, taper(7, r0, 0.016, 1.0)), 0.7, axis=0)


# ============================================================ colori
HIDE = (104, 34, 26)        # pelle rosso-bruna
FUR = (44, 24, 22)          # pelo nero-bruno
IVORY = (238, 226, 196)     # corna e denti
FIRE = (255, 126, 22)       # corna in fiamme (Neon)
LAVA = (255, 84, 16)        # vene di lava e filo dell'ascia (Neon)
EYE_GLOW = (255, 206, 52)
MOUTH = (46, 8, 12)
HOOF = (62, 56, 64)         # zoccoli grigio ferro lucido
LEATHER = (66, 40, 30)
BUTTON = (150, 22, 30)      # bottone rosso sangue
CLOTH = (120, 18, 26)       # perizoma rosso sangue
IRON = (150, 146, 156)
STEEL = (118, 116, 126)
WOOD = (64, 40, 28)
PATCH = (88, 86, 100)       # toppa di stoffa grigio carbone
THREAD = (236, 220, 184)

m = Model("InfernoMinotaur", "pet")

# ============================================================ tronco a V
pelvis = ellipsoid((0.46, 0.34, 0.3), (0, 0.06, 1.56))
waist = ellipsoid((0.37, 0.28, 0.3), (0, 0.04, 1.86))
ribcage = ellipsoid((0.56, 0.4, 0.42), (0, 0.05, 2.24))
upper_back = ellipsoid((0.64, 0.38, 0.32), (0, 0.08, 2.48))
torso = union(pelvis, waist, ribcage, upper_back, k=0.25)
pecs = [ell((sx * 0.27, -0.27, 2.38), (0.3, 0.2, 0.24), axis=(sx * 0.3, 0.0, 1.0)) for sx in (1, -1)]
lats = [ellipsoid((0.22, 0.3, 0.42), (sx * 0.47, 0.1, 2.18)) for sx in (1, -1)]
abs_ = [ellipsoid((0.1, 0.075, 0.072), (sx * 0.108, -0.26, z)) for sx in (1, -1) for z in (1.83, 1.98, 2.12)]
traps = ellipsoid((0.46, 0.3, 0.26), (0, 0.12, 2.68))
torso = union(torso, *pecs, *lats, k=0.12)
torso = union(torso, *abs_, k=0.05)
torso = union(torso, traps, k=0.15)
torso = torso.subtract(union(capsule((0, -0.5, 2.5), (0, -0.48, 2.2), 0.035), capsule((0, -0.4, 2.12), (0, -0.4, 1.78), 0.022)),
                       k=0.04)   # solco fra i pettorali e linea alba
neck = round_cone((0, 0.08, 2.48), (0, -0.14, 2.76), 0.34, 0.28)

# ============================================================ braccia alzate: le due mani stringono il manico sopra la testa
HAFT_B = np.array([0.0, 0.2, 3.28])            # pomo del manico, sopra e dietro la testa
HAFT_U = norm((0.0, 0.1, 0.99))                # manico appena inclinato all'indietro


def haft_pt(t):
    return HAFT_B + HAFT_U * t


FIST = {-1: haft_pt(0.26), 1: haft_pt(0.52)}   # destra (-X) piu' in basso, sinistra (+X) piu' in alto
SH = {sx: np.array([sx * 0.66, 0.08, 2.56]) for sx in (1, -1)}
EL = {1: np.array([0.74, 0.18, 3.24]), -1: np.array([-0.76, 0.14, 3.12])}
arms, ELBOW_INFO = [], {}
for sx in (1, -1):
    sh, el = SH[sx], EL[sx]
    fi = FIST[sx] + np.array([sx * 0.06, 0.0, 0.0])
    ua, fa = el - sh, fi - el
    arms += [ellipsoid((0.3, 0.3, 0.3), (sx * 0.69, 0.06, 2.63)),                   # deltoide
             round_cone(sh, el, 0.23, 0.17),
             ell(sh + ua * 0.5 + np.array([0, -0.08, 0.02]), (0.17, 0.16, 0.26), axis=ua),   # bicipite
             ell(sh + ua * 0.45 + np.array([sx * 0.03, 0.09, -0.02]), (0.16, 0.15, 0.26), axis=ua),  # tricipite
             round_cone(el, fi, 0.17, 0.12),
             ell(el + fa * 0.3, (0.17, 0.16, 0.24), axis=fa),                           # avambraccio
             ell(fi, (0.165, 0.15, 0.15), axis=HAFT_U, side=(sx, 0, 0))]                  # pugno
    # nocche in fila davanti al manico
    front = norm(np.array([0, -1.0, 0]) - HAFT_U * float(np.dot((0, -1.0, 0), HAFT_U)))
    for j in range(4):
        kp = FIST[sx] + HAFT_U * (0.1 - 0.067 * j) + front * 0.11 + np.array([-sx * 0.015, 0, 0])
        arms.append(sphere(0.052, tuple(kp)))
    ELBOW_INFO[sx] = (sh, el, fi)

# ============================================================ gambe da toro (ginocchio avanti, garretto indietro)
LEGS = {1: dict(hip=(0.31, 0.02, 1.54), knee=(0.44, -0.32, 1.04), hock=(0.48, 0.06, 0.56), fet=(0.5, -0.1, 0.22)),
        -1: dict(hip=(-0.31, 0.08, 1.54), knee=(-0.42, -0.14, 1.02), hock=(-0.46, 0.3, 0.56), fet=(-0.48, 0.14, 0.22))}
legs, HOOVES = [], []
for sx, L in LEGS.items():
    hip, kn, hk, ft = (np.array(L[k], float) for k in ("hip", "knee", "hock", "fet"))
    fem, gas = kn - hip, hk - kn
    legs += [round_cone(hip, kn, 0.27, 0.18),
             ell(hip + fem * 0.45 + np.array([sx * 0.05, -0.02, 0.0]), (0.29, 0.3, 0.42), axis=fem),     # coscia
             ell(hip + fem * 0.62 + np.array([0, -0.11, 0.0]), (0.17, 0.15, 0.27), axis=fem),          # quadricipite
             round_cone(kn, hk, 0.18, 0.11),
             ell(kn + gas * 0.42 + np.array([0, 0.07, 0.03]), (0.15, 0.16, 0.24), axis=gas),           # polpaccio
             round_cone(hk, ft, 0.12, 0.11),
             round_cone(ft, ft + np.array([0, -0.06, -0.1]), 0.1, 0.12)]
    HOOVES.append((ft + np.array([0, -0.08, -0.16]), sx))

TAIL_PTS = bezier((0, 0.34, 1.64), (0, 0.6, 1.52), (0.05, 0.68, 1.08), (0.12, 0.6, 0.76), 10)
tail = tube(TAIL_PTS, taper(11, 0.075, 0.04))

# ============================================================ testa di toro (spazio locale: muso verso -Y)
HEAD_T = np.array([0.0, -0.32, 2.78], dtype=np.float32)
HS = 1.18                       # scala della testa
R_HEAD = euler(6.0, -4.0, 7.0)  # muso appena abbassato, testa girata e inclinata verso chi guarda
JAW_Z = -0.14
HINGE = (0.0, 0.0, JAW_Z)
GAPE = 26.0


def Hd(shape):
    return shape.scale(HS).rotate(R_HEAD).translate(HEAD_T)


def hp(p):
    return R_HEAD @ (HS * np.asarray(p, dtype=np.float32)) + HEAD_T


def Jw(shape):
    return shape.rot(GAPE, 0, 0, pivot=HINGE)


skull = ellipsoid((0.29, 0.25, 0.3), (0, 0.06, 0.13))                   # cranio alto
poll = ellipsoid((0.31, 0.17, 0.14), (0, 0.06, 0.29))                   # nuca larga: qui escono le corna
face = tbox(0.0, -0.45, 0.25, 0.22, 0.2, 0.0, JAW_Z - 0.03, JAW_Z - 0.03, 0.09)   # faccia piatta e larga
nosepad = ellipsoid((0.26, 0.13, 0.155), (0, -0.47, -0.05))             # grosso naso da toro
cheeks = [ellipsoid((0.13, 0.2, 0.17), (sx * 0.21, -0.08, -0.06)) for sx in (1, -1)]
brows = [capsule((sx * 0.085, -0.29, 0.19), (sx * 0.3, -0.16, 0.285), 0.058) for sx in (1, -1)]
mounds = [ellipsoid((0.09, 0.08, 0.08), (sx * 0.2, -0.22, 0.11)) for sx in (1, -1)]
upper = union(skull, poll, k=0.1)
upper = union(upper, face, k=0.14)
upper = union(upper, nosepad, *cheeks, k=0.08)
upper = union(upper, *mounds, k=0.05)
upper = union(upper, *brows, k=0.09)
# rughe del ringhio sul dorso del muso
wr = [tube([(-0.17, y + 0.03, -0.02), (-0.09, y, 0.03), (0.0, y - 0.01, 0.045), (0.09, y, 0.03), (0.17, y + 0.03, -0.02)],
           0.03) for y in (-0.3, -0.38)]
upper = union(upper, *wr, k=0.035)
NOSTRILS = [(sx * 0.105, -0.585, -0.025) for sx in (1, -1)]
upper = upper.subtract(union(*[ellipsoid((0.058, 0.07, 0.048), c) for c in NOSTRILS]), k=0.025)
upper = upper.subtract(box((0.6, 0.5, 0.3), (0, HINGE[1] - 0.5, JAW_Z - 0.3)), k=0.012)

jaw = union(tbox(0.02, -0.45, 0.21, 0.2, JAW_Z + 0.05, JAW_Z + 0.05, -0.3, -0.27, 0.08),
            ellipsoid((0.2, 0.11, 0.08), (0, -0.4, -0.28)), k=0.06)
jaw = jaw.subtract(box((0.6, 0.6, 0.3), (0, -0.4, JAW_Z + 0.3)), k=0.012)

# occhi di brace incassati sotto la fronte aggrottata
eyes, lids = [], []
for sx in (1, -1):
    p, n = project(upper, (sx * 0.19, -0.2, 0.1), (sx * 0.42, -0.9, -0.02))
    a1 = sx * norm(np.cross((0.0, 0.0, 1.0), n))
    a2 = -sx * n
    a3 = np.cross(a1, a2)
    sl = math.radians(22)
    a1, a3 = a1 * math.cos(sl) + a3 * math.sin(sl), a3 * math.cos(sl) - a1 * math.sin(sl)
    M = np.stack([a1, a2, a3], axis=1).astype(np.float32)
    c = p - n * 0.026
    eyes.append(ellipsoid((0.11, 0.064, 0.068)).rotate(M).translate(c))
    cutp = SDF(lambda q: (0.03 + 0.42 * q[:, 0] - q[:, 2]) / math.sqrt(1.1764), (-0.14, -0.14, -0.14), (0.14, 0.14, 0.14))
    lids.append(ellipsoid((0.124, 0.078, 0.082)).intersect(cutp).rotate(M).translate(c))

# orecchie da toro aperte di lato, sotto e dietro le corna
ears = []
for sx in (1, -1):
    Me = frame((sx * 1.0, 0.3, -0.42), (0, -1.0, 0.1))
    ear = flatten(tube([(0, 0, -0.03), (0, 0, 0.15), (0, -0.02, 0.3)], [0.085, 0.08, 0.022]), 0.45, axis=1)
    ears.append(ear.rotate(Me).translate((sx * 0.27, 0.1, 0.12)))

head_skin = union(union(upper, Jw(jaw), k=0.012), *lids, k=0.012)
head_skin = union(head_skin, *ears, k=0.04)

# bocca: palato e lingua scuri, parete della gola
pal_reg = SDF(lambda p: np.maximum(np.maximum(np.abs(p[:, 0]) - 0.18, p[:, 2] - (JAW_Z + 0.03)),
                                   np.maximum(p[:, 1] - 0.0, -0.5 - p[:, 1])), (-0.19, -0.51, JAW_Z - 0.05),
              (0.19, 0.0, JAW_Z + 0.03))
jaw_reg = SDF(lambda p: np.maximum(np.maximum(np.abs(p[:, 0]) - 0.17, (JAW_Z - 0.03) - p[:, 2]),
                                   np.maximum(p[:, 1] - 0.0, -0.43 - p[:, 1])), (-0.18, -0.44, JAW_Z - 0.03),
              (0.18, 0.0, JAW_Z + 0.05))
dark = [thin(upper, 0.006, 0.03).intersect(pal_reg), Jw(thin(jaw, 0.006, 0.03).intersect(jaw_reg))]
Rinv = euler(-GAPE, 0, 0)
piv = np.asarray(HINGE, dtype=np.float32)


def wedge(p):
    q = (p - piv) @ Rinv.T + piv
    return np.maximum(np.maximum(p[:, 2] - (JAW_Z + 0.004), (JAW_Z - 0.004) - q[:, 2]),
                      np.maximum(np.abs(p[:, 0]) - 0.19, np.maximum(p[:, 1] - 0.04, -0.14 - p[:, 1])))


dark.append(SDF(wedge, (-0.19, -0.14, JAW_Z - 0.3), (0.19, 0.04, JAW_Z + 0.01)))
tongue = Jw(ellipsoid((0.13, 0.22, 0.045), (0, -0.24, JAW_Z - 0.02)))
dark.append(tongue)
dark += [ellipsoid((0.05, 0.05, 0.04), (c[0] * 0.95, -0.53, c[2])) for c in NOSTRILS]   # fondo delle narici

# denti: zanne agli angoli e file di denti aguzzi
teeth, bases_up, bases_lo = [], [], []
for a, big in ((-62, True), (-38, False), (-16, False), (16, False), (38, False), (62, True)):
    d = (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0.0)
    p, n = project(upper, (0, -0.3, JAW_Z + 0.012), d)
    b = p - norm((n[0], n[1], 0.0)) * 0.03
    L = 0.19 if big else 0.08
    teeth.append(round_cone((b[0], b[1], JAW_Z + 0.03), (b[0], b[1] - 0.015, JAW_Z - L), 0.04 if big else 0.026, 0.01))
    bases_up.append((b[0], b[1], JAW_Z + 0.03))
for y in (-0.26, -0.18):
    for sx in (1, -1):
        p, n = project(upper, (0, y, JAW_Z + 0.012), (sx, 0, 0))
        b = p - np.array([sx * 0.03, 0, 0])
        teeth.append(round_cone((b[0], b[1], JAW_Z + 0.03), (b[0], b[1], JAW_Z - 0.065), 0.025, 0.01))
        bases_up.append((b[0], b[1], JAW_Z + 0.03))
for a, big in ((-55, True), (-25, False), (0, False), (25, False), (55, True)):
    d = (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0.0)
    p, n = project(jaw, (0, -0.28, JAW_Z - 0.012), d)
    b = p - norm((n[0], n[1], 0.0)) * 0.03
    L = 0.16 if big else 0.065
    teeth.append(Jw(round_cone((b[0], b[1], JAW_Z - 0.03), (b[0], b[1] - 0.01, JAW_Z + L), 0.038 if big else 0.024,
                               0.01)))
    bases_lo.append((b[0], b[1], JAW_Z - 0.03))


def row_bar(bases):
    pts = sorted(bases, key=lambda q: math.atan2(q[0], -q[1]))
    return tube(pts, 0.016)


teeth += [row_bar(bases_up), Jw(row_bar(bases_lo))]

# corna d'avorio gigantesche: in fuori, poi in alto e in avanti; le punte bruciano
HORNS = []
for sx in (1, -1):
    b = np.array([sx * 0.24, 0.05, 0.3])
    pts = bezier(tuple(b), tuple(b + (sx * 0.3, 0.02, -0.02)), tuple(b + (sx * 0.52, -0.08, 0.1)),
                 tuple(b + (sx * 0.56, -0.24, 0.44)), 16)
    HORNS.append((pts, [0.125 * (1 - 0.88 * (j / 16) ** 1.1) + 0.012 for j in range(17)]))
horn_ivory = [tube(p_[:13], r_[:13]) for p_, r_ in HORNS]
horn_fire = [tube(p_[11:], r_[11:]).offset(0.008) for p_, r_ in HORNS]
horn_flames = []
for p_, r_ in HORNS:
    tip, d = np.asarray(p_[-1]), norm(np.asarray(p_[-1]) - np.asarray(p_[-4]))
    sx = 1 if tip[0] > 0 else -1
    for tilt, L, fk, r0 in ((0.0, 0.46, 0.55, 0.085), (0.75 * sx, 0.32, 0.0, 0.07), (-0.55 * sx, 0.3, 0.0, 0.065),
                            (0.3 * sx, 0.24, 0.0, 0.06)):
        up = norm(d * 0.45 + np.array([tilt * 0.55, 0.25, 1.0]))
        horn_flames.append(flame(L, r0, bend=0.6, wig=0.05, flat=0.72, fork=fk).rotate(frame(up, (0, 1, 0))).translate(
            tip - d * 0.05))

# anello di ferro al naso (passa nel setto fra le narici)
nose_ring = torus(0.105, 0.03).rot(0, 90, 0).translate((0, -0.615, -0.13))

# ciuffo sulla fronte fra le corna
forelock = []
for dx, L, tilt in ((0.0, 0.2, 0.0), (0.08, 0.16, 0.4), (-0.08, 0.16, -0.4)):
    forelock.append(tuft(L * 1.2, 0.06, curl=-0.5).rotate(frame((tilt, -0.6, 0.8), (0, -1, -0.2))).translate(
        (dx, -0.08, 0.33)))

# ============================================================ corpo intero
body0 = union(torso, neck, k=0.18)
body0 = fast_union(arms, k=0.07, base=body0)
body0 = fast_union(legs, k=0.08, base=body0)
body0 = fast_union([tail], k=0.05, base=body0)
body0 = body0.intersect(halfspace_z(0.12))
head_w = Hd(head_skin)
core = fast_union([head_w], k=0.1, base=body0)     # tutto il corpo (per appoggiare vene, pelo e cuciture)
print("[minotaur] corpo pronto", flush=True)

# ============================================================ vene di lava (linee frastagliate sulla pelle)
VEINS = []


def add_vein(origin, a, b, n=6, amp=0.035, w=0.026, branch=None):
    pts = zigzag(a, b, n, amp, np.asarray(a, float) - np.asarray(origin, float))
    VEINS.append((origin, pts, w))
    if branch:
        j, end, nb = branch
        VEINS.append((origin, zigzag(pts[j], end, nb, amp * 0.7, pts[j] - np.asarray(origin, float)), w * 0.7))


for sx in (1, -1):
    # petto: dallo sterno alle spalle, e giu' sugli addominali
    add_vein((0, 0.0, 2.2), (sx * 0.06, -0.6, 2.24), (sx * 0.58, -0.5, 2.56), n=6, w=0.028,
             branch=(3, (sx * 0.42, -0.6, 2.08), 3))
    add_vein((0, 0.0, 1.95), (sx * 0.05, -0.6, 2.06), (sx * 0.3, -0.6, 1.72), n=5, w=0.024)
    # braccia: bicipite e avambraccio
    sh, el, fi = ELBOW_INFO[sx]
    for a, b, o in ((sh * 0.75 + el * 0.25, el * 0.85 + sh * 0.15, sh * 0.5 + el * 0.5),
                    (el * 0.85 + fi * 0.15, el * 0.25 + fi * 0.75, el * 0.5 + fi * 0.5)):
        out = norm(np.cross(b - a, (0, 1, 0))) * sx
        out = norm(out + np.array([0, -0.6, 0.0]))
        add_vein(o, a + out * 0.4, b + out * 0.4, n=5, amp=0.03, w=0.024)
    # cosce
    L = LEGS[sx]
    hip, kn = np.array(L["hip"]), np.array(L["knee"])
    add_vein(hip * 0.5 + kn * 0.5, hip * 0.8 + kn * 0.2 + np.array([sx * 0.3, -0.2, 0]),
             hip * 0.15 + kn * 0.85 + np.array([sx * 0.25, -0.2, 0]), n=6, w=0.026,
             branch=(3, hip * 0.4 + kn * 0.6 + np.array([sx * 0.4, 0.2, 0]), 3))
# collo
add_vein((0, -0.02, 2.66), (0.12, -0.3, 2.5), (0.2, -0.1, 2.86), n=4, amp=0.03, w=0.022)

veins = []
for origin, pts, w in VEINS:
    q, nr = project_many(core, [origin], [np.asarray(p, float) - np.asarray(origin, float) for p in pts])
    k = len(q)
    radii = [w * (0.45 + 0.55 * math.sin(math.pi * (0.05 + 0.9 * j / (k - 1)))) for j in range(k)]
    veins.append(tube([tuple(p - nn * r * 0.35) for p, nn, r in zip(q, nr, radii)], radii))

m.add("Body", body0, HIDE, tris=3000, voxel=0.0435)
neck_top = round_cone((0, 0.0, 2.6), (0, -0.14, 2.76), 0.31, 0.28)
m.add("HeadSkin", SDF(fast_union([head_w], k=0.1, base=neck_top).f, head_w.lo - 0.12,
                      np.maximum(head_w.hi, neck_top.hi) + 0.12), HIDE, role="skin", tris=2400, voxel=0.0272)
print("[minotaur] pelle pronta", flush=True)

# ============================================================ pelo: criniera su collo e spalle, ciuffi
def mane_region(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    ang = np.arctan2(x, y - 0.1)
    edge = 2.5 + 0.06 * np.sin(ang * 9.0)          # bordo inferiore a ciocche
    reg = np.maximum(edge - z, (np.sqrt((x / 0.62) ** 2 + ((y - 0.12) / 0.42) ** 2) - 1.0) * 0.4)
    front = -(y + 0.06) - 0.25 * (z - 2.5)          # > 0 davanti al collo: li' niente pelo
    reg = np.maximum(reg, front)
    # calotta sulla testa: dalla nuca fino all'attaccatura delle corna, bordo davanti a ciocche
    q = (p - HEAD_T) @ R_HEAD / HS
    cap_edge = -0.12 + 0.035 * np.sin(q[:, 0] * 40.0)
    cap = np.maximum.reduce([cap_edge - q[:, 1], 0.22 - q[:, 2], np.abs(q[:, 0]) - 0.3]) * HS
    return np.minimum(reg, cap).astype(np.float32)


mane = paint(core, SDF(mane_region, (-0.7, -0.6, 2.35), (0.7, 0.6, 3.5)), out=0.05, inn=0.03)


def boots_region(p):
    """Pelo ispido sugli stinchi, dal garretto in giu' (bordo superiore a ciocche)."""
    out = np.full(len(p), 9.0, dtype=np.float32)
    for L in LEGS.values():
        hk, ft = np.array(L["hock"], np.float32), np.array(L["fet"], np.float32) + np.array([0, 0, -0.12], np.float32)
        ab = hk - ft
        t = np.clip(((p - ft) @ ab) / float(ab @ ab), 0.0, 1.0)
        d_axis = np.linalg.norm(p - (ft + t[:, None] * ab), axis=1)
        ang = np.arctan2(p[:, 1] - hk[1], p[:, 0] - hk[0])
        top = hk[2] + 0.06 + 0.085 * np.sin(ang * 5.0)
        bot = 0.2 - 0.06 * np.maximum(np.sin(ang * 6.0 + 1.0), 0.0)    # ciocche che ricadono sullo zoccolo
        out = np.minimum(out, np.maximum.reduce([d_axis - 0.32, p[:, 2] - top, bot - p[:, 2]]))
    return out


boots = paint(body0, SDF(boots_region, (-0.9, -0.5, 0.1), (0.9, 0.6, 0.75)), out=0.06, inn=0.03)
fur = [mane, boots]
for j in range(9):   # ciocche che pendono dal bordo della criniera, sulla schiena
    a = math.radians(-80 + 20 * j)
    o = np.array([0.0, 0.12, 2.55])
    d = np.array([math.sin(a), math.cos(a), -0.35])
    p, n = project_many(core, [o], [d])
    p, n = p[0], n[0]
    fur.append(tuft(0.18, 0.075, curl=0.35).rotate(frame(norm(n * 0.25 + np.array([0, 0.1, -1.0])), n)).translate(
        p - n * 0.02))
tail_tip, tail_d = np.asarray(TAIL_PTS[-1]), norm(np.asarray(TAIL_PTS[-1]) - np.asarray(TAIL_PTS[-3]))
for tilt in (0.0, 0.5, -0.5):
    fur.append(tuft(0.22, 0.06, curl=0.2).rotate(frame(norm(tail_d + np.array([tilt, 0, 0])), (0, 1, 0))).translate(
        tail_tip - tail_d * 0.03))
m.add("Fur", fast_union(fur), FUR, role="detail", tris=1700, voxel=0.0462)

# ============================================================ testa: corna, fuoco, occhi, bocca, denti
m.add("Horns", Hd(union(*horn_ivory)), IVORY, role="detail", tris=650, voxel=0.0294)
m.add("Flames", fast_union([Hd(x) for x in horn_fire + horn_flames], k=0.02), FIRE, material="Neon", role="glow",
      tris=900, voxel=0.0226)
eye_glow = [Hd(e) for e in eyes]
m.add("EyeGlow", fast_union(eye_glow), EYE_GLOW, material="Neon", role="glow", tris=300, voxel=0.0172)
m.add("Mouth", Hd(fast_union(dark)), MOUTH, role="eye", tris=420, voxel=0.0304)
m.add("Teeth", Hd(fast_union(teeth)), IVORY, role="shine", tris=520, voxel=0.0198)

# ============================================================ zoccoli spaccati
hooves = []
for (c, sx) in HOOVES:
    for sg in (1, -1):
        hc = c + np.array([sg * 0.062, -0.03, 0.0])
        hooves.append(ell(hc, (0.095, 0.16, 0.15), axis=(0, 0.25, 1.0)))
    hooves.append(ellipsoid((0.17, 0.17, 0.09), tuple(c + np.array([0, 0.05, 0.11]))))
m.add("Hooves", fast_union(hooves, k=0.02).intersect(halfspace_z(0.0)), HOOF, reflectance=0.1, role="detail", tris=420, voxel=0.027)

# ============================================================ cintura borchiata, bottone gigante, perizoma
BELT_Z = (1.6, 1.78)


def belt_fn(p):
    # cintura pesante che scende un po' sul davanti (bordi non piatti: niente facce allineate alla griglia)
    ang = np.arctan2(p[:, 0], -(p[:, 1] - 0.05))
    dz = -0.045 * np.cos(ang) + 0.008 * np.sin(ang * 5.0)
    return np.maximum(BELT_Z[0] + dz - p[:, 2], p[:, 2] - (BELT_Z[1] + dz))


belt_reg = SDF(belt_fn, (-0.7, -0.6, BELT_Z[0] - 0.06), (0.7, 0.6, BELT_Z[1] + 0.06))
belt = paint(core, belt_reg, out=0.055, inn=0.03)
m.add("Belt", belt, LEATHER, role="detail", tris=520, voxel=0.0358)
bf, bn = project(core, (0, 0.0, 1.69), (0, -1, 0))
BTN_C = bf + np.array([0, -0.07, 0.0])
button = cylinder(tuple(BTN_C + (0, 0.025, 0)), tuple(BTN_C + (0, -0.025, 0)), 0.15, round=0.02)
button = union(button, torus(0.13, 0.022).rot(90, 0, 0).translate(tuple(BTN_C + (0, -0.03, 0))), k=0.01)
HOLES = [BTN_C + np.array([dx, 0, dz]) for dx in (-0.045, 0.045) for dz in (-0.045, 0.045)]
button = button.subtract(union(*[cylinder(tuple(h + (0, 0.1, 0)), tuple(h + (0, -0.1, 0)), 0.022) for h in HOLES]))
m.add("Button", button, BUTTON, role="detail", tris=300, voxel=0.0165)


def flap(y0, sgn, top, bot, half_w, seed):
    """Perizoma: pannello sfrangiato che pende dalla cintura (davanti sgn=-1, dietro sgn=+1)."""
    r = np.random.default_rng(seed)
    xs = np.linspace(half_w * 0.95, -half_w * 0.95, 9)
    poly = [(-half_w, top), (half_w, top)]
    for i, x in enumerate(xs):
        poly.append((x, bot + (0.0 if i % 2 else 0.1) + r.uniform(-0.02, 0.02)))
    pr = prism(poly, -0.022, 0.022, round=0.01)   # piano locale XY = (x, z del mondo), spessore lungo Y

    def f(p):
        # superficie del pannello: avvolge il corpo (x^2) e scende in fuori verso il basso
        ys = y0 - sgn * 0.9 * p[:, 0] ** 2 + sgn * 0.12 * (top - p[:, 2])
        q = np.stack([p[:, 0], p[:, 2], p[:, 1] - ys], axis=1)
        return pr(q) * 0.85

    return SDF(f, (-half_w - 0.05, y0 - 0.35, bot - 0.05), (half_w + 0.05, y0 + 0.35, top + 0.05))


cloth = union(flap(-0.36, -1, 1.66, 0.98, 0.27, 3), flap(0.38, 1, 1.66, 1.05, 0.3, 4))
m.add("Loincloth", cloth, CLOTH, material="Fabric", role="detail", tris=460, voxel=0.034)

# ============================================================ ascia bipenne (spazio locale: Z lungo il manico, X di lato)
AXE_C = haft_pt(0.94)
M_AXE = frame(HAFT_U, (0, -1.0, 0.0))   # z = manico, y verso il davanti
BLADE = [(0.07, 0.15), (0.3, 0.17), (0.5, 0.28), (0.68, 0.42), (0.78, 0.22), (0.81, 0.0), (0.78, -0.22),
         (0.68, -0.38), (0.5, -0.24), (0.3, -0.14), (0.07, -0.13)]


def blade_sdf(sx):
    poly = [(sx * x, z) for x, z in BLADE]
    pr = prism(poly, -0.06, 0.06)

    def f(p):
        q = np.stack([p[:, 0], p[:, 2], p[:, 1]], axis=1)   # piano (x, z), spessore lungo y
        t = 0.055 - 0.04 * np.clip((np.abs(p[:, 0]) - 0.07) / 0.72, 0.0, 1.0)
        return np.maximum(pr(q), np.abs(p[:, 1]) - t)

    return SDF(f, (min(0, sx * 0.85), -0.07, -0.55), (max(0, sx * 0.85), 0.07, 0.55))


blades = union(blade_sdf(1), blade_sdf(-1))
socket = cylinder((0, 0, -0.22), (0, 0, 0.22), 0.09, round=0.02)
EDGE_C, EDGE_R = (0.12, 0.0), 0.66


def edge_region(p):
    return EDGE_R - np.sqrt((np.abs(p[:, 0]) - EDGE_C[0]) ** 2 + p[:, 2] ** 2)


axe_iron = union(blades.intersect(SDF(lambda p: -edge_region(p) - 0.0, (-1, -1, -1), (1, 1, 1))), socket, k=0.02)
axe_edge = blades.offset(0.006).intersect(SDF(edge_region, (-1, -1, -1), (1, 1, 1)))
m.add("AxeHead", axe_iron.rotate(M_AXE).translate(AXE_C), STEEL, material="Metal", role="detail", tris=900,
      voxel=0.0256)
haft = union(capsule(tuple(HAFT_B), tuple(haft_pt(1.18)), 0.05), sphere(0.08, tuple(HAFT_B)), k=0.03)
haft = union(haft, round_cone(tuple(haft_pt(1.14)), tuple(haft_pt(1.36)), 0.06, 0.014))
m.add("AxeHaft", haft, WOOD, material="Wood", role="detail", tris=370, voxel=0.0218)

# ============================================================ ferro: bracciali chiodati, anello al naso, borchie, fasce del manico
iron = [Hd(nose_ring)]
for sx in (1, -1):
    sh, el, fi = ELBOW_INFO[sx]
    ax = norm(fi - el)
    c = el + (fi - el) * 0.72
    Mb = frame(ax, (0, -1, 0))
    iron.append(band(0.135, 0.035, 0.065).rotate(Mb).translate(c))
    for a in (0.0, 2.1, 4.2):
        d = Mb @ np.array([math.cos(a), math.sin(a), 0.0], dtype=np.float32)
        iron.append(round_cone(tuple(c + d * 0.15), tuple(c + d * 0.26), 0.04, 0.012))
# spallaccio di ferro sul lato esterno della spalla destra, con tre spuntoni
PD_C = np.array([-0.71, 0.06, 2.64])
PD_N = norm((-1.0, -0.15, 0.25))
pauldron = ellipsoid((0.36, 0.36, 0.36), tuple(PD_C)).shell(0.026).intersect(
    SDF(lambda p: 0.03 - (p - PD_C) @ PD_N.astype(np.float32), PD_C - 0.4, PD_C + 0.4))
iron.append(pauldron)
for dz, dy in ((0.14, -0.02), (-0.02, -0.14), (-0.04, 0.12)):
    d = norm(PD_N + np.array([0, dy, dz]) * 1.6)
    iron.append(round_cone(tuple(PD_C + d * 0.34), tuple(PD_C + d * 0.55), 0.05, 0.013))
for a in np.linspace(-1.2, 1.2, 6):   # borchie sulla cintura
    if abs(a) < 0.3:
        continue
    p, n = project(core, (0, 0.0, 1.69), (math.sin(a), -math.cos(a), 0))
    iron.append(sphere(0.034, tuple(p + n * 0.05)))
for t in (0.08, 0.68, 1.16):
    c = haft_pt(t)
    iron.append(band(0.058, 0.014, 0.025).rotate(M_AXE).translate(c))
m.add("IronGear", fast_union(iron), IRON, material="Metal", role="detail", tris=900, voxel=0.0347)

# ============================================================ toppa cucita sulla spalla sinistra (+X)
PF_O, PF_N = project(core, (0.45, 0.0, 2.5), (0.55, -1.0, 0.1))
PM = frame(PF_N, (0, 0, 1))   # z = normale uscente, y verso l'alto


def patch_region(p):
    q = (p - PF_O) @ PM
    return np.maximum(np.abs(q[:, 0]) - 0.2, np.abs(q[:, 1]) - 0.19).astype(np.float32)


patch = paint(core, SDF(patch_region, PF_O - 0.35, PF_O + 0.35), out=0.022, inn=0.03)
m.add("Patch", patch, PATCH, material="Fabric", role="detail", tris=300, voxel=0.031)
stitches = []
corners = [(-0.2, -0.19), (0.2, -0.19), (0.2, 0.19), (-0.2, 0.19)]
for i in range(4):
    a, b = np.array(corners[i]), np.array(corners[(i + 1) % 4])
    for t in (0.2, 0.5, 0.8):
        c2 = a + (b - a) * t
        tdir = norm(b - a)
        nrm2 = np.array([-tdir[1], tdir[0]])
        for sg in (1, -1):
            e1 = c2 - nrm2 * 0.045 - tdir * 0.03 * sg
            e2 = c2 + nrm2 * 0.045 + tdir * 0.03 * sg
            w1 = PF_O + PM @ np.array([e1[0], e1[1], 0.0], dtype=np.float32)
            w2 = PF_O + PM @ np.array([e2[0], e2[1], 0.0], dtype=np.float32)
            stitches.append(capsule(tuple(on_surface(core, w1, 0.03, 3)), tuple(on_surface(core, w2, 0.03, 3)), 0.017))
for sg in (1, -1):   # filo incrociato nei buchi del bottone
    a = HOLES[0] if sg > 0 else HOLES[1]
    b = HOLES[3] if sg > 0 else HOLES[2]
    stitches.append(capsule(tuple(a + (0, -0.035, 0)), tuple(b + (0, -0.035, 0)), 0.016))
m.add("Stitches", fast_union(stitches), THREAD, role="detail", tris=400, voxel=0.0185)

# ============================================================ RAGE: vene di lava e filo incandescente dell'ascia
m.add("Rage", fast_union(veins + [axe_edge.rotate(M_AXE).translate(AXE_C)]), LAVA, material="Neon", role="glow",
      tris=1300, voxel=0.0175)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 600)))
