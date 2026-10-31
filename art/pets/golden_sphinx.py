"""Sfinge Dorata (GoldenSphinx) - pet del Percorso Estremo (antico Egitto).

La guardiana degli enigmi: una sfinge regale con il corpo di leone d'oro lucido, che si sta alzando
dalla posa sdraiata: le zampe posteriori ancora piegate a terra, il petto sollevato e le zampe
anteriori appoggiate su un blocco di arenaria. Il volto e' una maschera da faraone d'oro con lo sguardo
intenso: occhi a mandorla turchesi incandescenti con la pupilla a fessura, il trucco blu notte
allungato verso le tempie e le sopracciglia di lapislazzuli. Porta il copricapo nemes a righe blu e
oro con le due bande che scendono sul petto, l'ureo (il cobra reale) che si alza sulla fronte e la
barba posticcia intrecciata. Due grandi ali di falco mezze alzate (gruppi WingL/WingR, il gioco le fa
oscillare) con le file di penne d'oro e di lapislazzuli. Sui fianchi corre un fregio di geroglifici
turchesi incandescenti (parte Neon "Frost": il gioco ci attacca scintille azzurre); la coda
arrotolata a terra finisce in un ciuffo a righe.
Tocco "toy horror": un sorriso sornione a un angolo della bocca con i dentini aguzzi e una crepa nella
maschera d'oro, sotto l'occhio, da cui filtra la luce turchese, ricucita con tre punti a croce.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, box, capsule, ellipsoid, euler, halfspace_z, project,  # noqa: E402
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
GOLD_BODY = (232, 168, 44)   # corpo d'oro (Foil), un po' piu' caldo dei gioielli
GOLD = (255, 208, 84)        # nemes, ali, gioielli (Foil)
LAPIS = (26, 56, 188)        # lapislazzuli
TURQ = (70, 255, 214)        # fregio di geroglifici (Neon "Frost")
EYE_GLOW = (150, 255, 236)   # occhi e crepa (Neon)
KOHL = (18, 22, 58)          # trucco degli occhi e pupille
TOOTH = (250, 246, 232)
STONE = (206, 170, 116)      # arenaria del blocco
THREAD = (132, 24, 40)       # filo rosso scuro

m = Model("GoldenSphinx", "pet")

# ============================================================ blocco di arenaria sotto le zampe anteriori
BLK_C = np.array([0.0, -0.98, 0.16])
BLK_TOP = 0.32
block = box((0.44, 0.27, 0.16), tuple(BLK_C), round=0.012)
for c, r, ang in (((0.44, -1.25, 0.3), 0.08, (20, 35, 40)), ((-0.44, -0.71, 0.32), 0.07, (40, 10, 30)),
                  ((-0.45, -1.25, 0.05), 0.07, (10, 50, 20)), ((0.12, -1.25, 0.32), 0.045, (30, 20, 60))):
    block = block.subtract(box((r, r, r), c).rot(*ang, pivot=c))                    # spigoli scheggiati
block = block.subtract(union(capsule((0.18, -1.26, 0.27), (0.3, -1.26, 0.12), 0.012),
                             capsule((0.3, -1.26, 0.12), (0.26, -1.26, 0.03), 0.01)))   # crepa

# ============================================================ corpo di leone (petto alzato, posteriore ancora a terra)
rump = ellipsoid((0.4, 0.4, 0.34), (0, 0.72, 0.38))
waist = ell((0, 0.32, 0.55), (0.32, 0.3, 0.38), axis=(0, -1.0, 0.45))
ribs = ell((0, -0.05, 0.84), (0.39, 0.33, 0.44), axis=(0, -0.6, 1.0))
chest = ell((0, -0.42, 1.08), (0.41, 0.35, 0.44), axis=(0, -0.3, 1.0))
withers = ellipsoid((0.38, 0.3, 0.27), (0, -0.2, 1.3))
scap = [ell((sx * 0.29, -0.3, 1.1), (0.2, 0.26, 0.32), axis=(0, -0.3, 1.0)) for sx in (1, -1)]
body = union(rump, waist, ribs, k=0.25)
body = union(body, chest, withers, k=0.22)
body = union(body, *scap, k=0.12)
neck = round_cone((0, -0.46, 1.36), (0, -0.68, 1.8), 0.27, 0.19)

# zampe anteriori tese sul blocco
TOES = []


def paw(c, fwd, s=1.0, z_floor=0.0):
    fwd = norm((fwd[0], fwd[1], 0.0))
    side = np.array([-fwd[1], fwd[0], 0.0])
    c = np.asarray(c, float)
    pad = ellipsoid((0.16 * s, 0.17 * s, 0.09 * s)).rotate(frame((0, 0, 1), fwd)).translate(c)
    toes = []
    for dx in (-0.105, -0.036, 0.036, 0.105):
        a = c + side * dx * s + np.array([0, 0, 0.015])
        tip = c + side * dx * 1.3 * s + fwd * (0.17 - abs(dx) * 0.4) * s
        tip[2] = z_floor + 0.06 * s
        toes.append(capsule(tuple(a), tuple(tip), 0.06 * s))
        TOES.append((tip, norm(fwd + side * dx * 2.0), s, z_floor))
    return union(pad, *toes, k=0.04)


legs, WRISTS = [], []
for sx in (1, -1):
    sh, el, wr, pw = (np.array(v, float) for v in ((sx * 0.29, -0.4, 1.02), (sx * 0.31, -0.5, 0.68),
                                                    (sx * 0.27, -0.84, 0.48), (sx * 0.25, -0.96, BLK_TOP + 0.08)))
    legs += [round_cone(sh, el, 0.21, 0.15),
             ell((sh + el) / 2 + np.array([sx * 0.03, -0.05, 0.0]), (0.17, 0.18, 0.24), axis=el - sh),  # avambraccio
             round_cone(el, wr, 0.14, 0.11),
             round_cone(wr, pw + np.array([0, 0.03, 0.03]), 0.11, 0.11)]
    legs.append(paw(pw, (sx * 0.08, -1.0), 1.0, BLK_TOP))
    WRISTS.append((el * 0.35 + wr * 0.65, wr - el, el, wr))
# zampe posteriori piegate a terra (coscia grossa, stinco sotto, zampa in avanti accanto alla pancia)
for sx in (1, -1):
    legs += [ell((sx * 0.33, 0.6, 0.38), (0.22, 0.42, 0.33), axis=(0, 1.0, 0.25)),            # coscia
             round_cone((sx * 0.36, 0.86, 0.2), (sx * 0.42, 0.3, 0.1), 0.13, 0.1)]             # stinco a terra
    legs.append(paw((sx * 0.43, 0.16, 0.08), (sx * 0.05, -1.0), 0.95, 0.0))

# coda arrotolata a terra sul fianco destro (+X, verso la camera 3/4)
TAIL_PTS = bezier((0, 1.0, 0.44), (0.12, 1.36, 0.3), (0.62, 1.22, 0.07), (0.66, 0.74, 0.07), 14)
tail = tube(TAIL_PTS, taper(15, 0.085, 0.05))
TAIL_END = np.array(TAIL_PTS[-1])
TAIL_DIR = norm(np.array(TAIL_PTS[-1]) - np.array(TAIL_PTS[-3]))
tuft_core = union(ell(TAIL_END + TAIL_DIR * 0.12, (0.085, 0.085, 0.17), axis=TAIL_DIR),
                  round_cone(tuple(TAIL_END + TAIL_DIR * 0.2), tuple(TAIL_END + TAIL_DIR * 0.34), 0.07, 0.015), k=0.05)

core = union(body, neck, k=0.14)
core = fast_union(legs, k=0.07, base=core)
core = fast_union([tail], k=0.05, base=core)
core = core.intersect(halfspace_z(0.0))
print("[sphinx] corpo pronto", flush=True)

# ============================================================ testa: maschera da faraone (spazio locale: volto verso -Y)
HEAD_T = np.array([0.0, -0.8, 2.07], dtype=np.float32)
HS = 1.3
R_HEAD = euler(-4.0, 3.0, 8.0)   # mento appena alzato (fiero), girata verso la camera 3/4


def Hd(shape):
    return shape.scale(HS).rotate(R_HEAD).translate(HEAD_T)


skull = ellipsoid((0.2, 0.22, 0.24), (0, 0.03, 0.05))
face = ellipsoid((0.175, 0.12, 0.22), (0, -0.1, -0.02))
cheeks = [ellipsoid((0.075, 0.075, 0.075), (sx * 0.115, -0.15, -0.07)) for sx in (1, -1)]
chin = ellipsoid((0.11, 0.1, 0.075), (0, -0.12, -0.2))
brow_ridge = [capsule((sx * 0.025, -0.205, 0.105), (sx * 0.155, -0.15, 0.1), 0.03) for sx in (1, -1)]
nose = round_cone((0, -0.205, 0.07), (0, -0.25, -0.055), 0.022, 0.036)
nose_wings = [sphere(0.026, (sx * 0.028, -0.235, -0.06)) for sx in (1, -1)]
lips = [ellipsoid((0.066, 0.03, 0.02), (0, -0.212, -0.118)), ellipsoid((0.058, 0.03, 0.022), (0, -0.2, -0.158))]
head_core = union(skull, face, k=0.08)
head_core = union(head_core, *cheeks, chin, k=0.06)
head_core = union(head_core, *brow_ridge, k=0.04)
head_core = union(head_core, nose, *nose_wings, k=0.025)
head_core = union(head_core, *lips, k=0.02)

# ---- occhi a mandorla incandescenti, pupilla a fessura, palpebra pesante (sguardo intenso)
eyes, pupils, lids, EYE = [], [], [], {}
for sx in (1, -1):
    p, n = project(head_core, (sx * 0.08, -0.1, 0.04), (sx * 0.25, -1.0, 0.0))
    a1 = sx * norm(np.cross((0.0, 0.0, 1.0), n))
    a2 = -sx * n
    a3 = np.cross(a1, a2)
    sl = math.radians(9)
    a1, a3 = a1 * math.cos(sl) + a3 * math.sin(sl), a3 * math.cos(sl) - a1 * math.sin(sl)
    M = np.stack([a1, a2, a3], axis=1).astype(np.float32)
    c = p - n * 0.014
    e = ellipsoid((0.07, 0.03, 0.034)).rotate(M).translate(c)
    eyes.append(e)
    pupils.append(thin(e, 0.006, 0.02).intersect(ellipsoid((0.012, 0.2, 0.036)).rotate(M).translate(c)))
    cutp = SDF(lambda q: (0.012 + 0.1 * q[:, 0] - q[:, 2]), (-0.1, -0.1, -0.1), (0.1, 0.1, 0.1))
    lids.append(ellipsoid((0.078, 0.04, 0.044)).intersect(cutp).rotate(M).translate(c))
    EYE[sx] = (c, a1, a3, n)
head_skin = union(head_core, *lids, k=0.01)

# ---- trucco blu notte: contorno a mandorla allungato verso la tempia; sopracciglia di lapislazzuli
kohl, brows = [], []
for sx in (1, -1):
    c, a1, a3, n = EYE[sx]
    upper = [c + a1 * x + a3 * (0.022 * math.sqrt(max(1 - (x / 0.074) ** 2, 0.0)) + 0.006) for x in np.linspace(-0.074, 0.074, 9)]
    upper += [c + a1 * (0.074 + 0.032 * j) + a3 * (0.004 + 0.002 * j) for j in range(1, 4)]
    lower = [c + a1 * x - a3 * (0.026 * math.sqrt(max(1 - (x / 0.074) ** 2, 0.0)) + 0.004) for x in np.linspace(-0.05, 0.074, 7)]
    lower += [c + a1 * (0.074 + 0.03 * j) - a3 * (0.004 - 0.006 * j) for j in range(1, 3)]
    upper = [on_surface(head_skin, q, 0.002, 4) for q in upper]
    lower = [on_surface(head_skin, q, 0.002, 4) for q in lower]
    kohl.append(tube([tuple(q) for q in upper], taper(len(upper), 0.008, 0.007)))
    kohl.append(tube([tuple(q) for q in lower], taper(len(lower), 0.005, 0.006)))
    brow = [c + a1 * x + a3 * (0.058 + 0.06 * (x + 0.07) + 0.01 * math.sin((x + 0.07) / 0.21 * math.pi))
            for x in np.linspace(-0.06, 0.13, 8)]
    brow = [on_surface(head_skin, q, 0.004, 4) for q in brow]
    brows.append(tube([tuple(q) for q in brow], taper(8, 0.017, 0.01)))

# ---- bocca: sorriso sornione chiuso da un lato, aperto sui dentini aguzzi dall'altro
MOUTH_PTS = [(-0.062, -0.214, -0.132), (-0.03, -0.226, -0.139), (0.0, -0.229, -0.14), (0.03, -0.226, -0.136),
             (0.058, -0.216, -0.123), (0.078, -0.198, -0.104)]
mouth_line = tube(MOUTH_PTS, [0.008, 0.01, 0.012, 0.016, 0.016, 0.01])
grin_open = ell((0.035, -0.222, -0.134), (0.042, 0.03, 0.017), axis=(0.25, 0, 1.0))
head_skin = head_skin.subtract(grin_open, k=0.008)
mouth_dark = [mouth_line, ell((0.035, -0.205, -0.134), (0.04, 0.02, 0.015), axis=(0.25, 0, 1.0))]
teeth = []
for x, L in ((0.004, 0.024), (0.022, 0.026), (0.04, 0.026), (0.058, 0.022)):
    zt = -0.124 + 0.18 * (x - 0.0) * 0.5
    teeth.append(round_cone((x, -0.222, zt + 0.006), (x, -0.226, zt - L), 0.008, 0.002))
teeth.append(capsule((-0.005, -0.219, -0.12 + 0.002), (0.065, -0.214, -0.114), 0.006))

# ---- crepa nella maschera sotto l'occhio sinistro (+X), luce turchese, tre punti a croce
c, a1, a3, n = EYE[1]
crack_pts = [c - a3 * 0.04 + a1 * 0.01, c - a3 * 0.07 + a1 * 0.03, c - a3 * 0.1 + a1 * 0.015,
             c - a3 * 0.13 + a1 * 0.04, c - a3 * 0.16 + a1 * 0.025]
crack_pts = [on_surface(head_skin, q, -0.004, 4) for q in crack_pts]
crack = tube([tuple(q) for q in crack_pts], [0.008, 0.013, 0.014, 0.012, 0.007])
head_skin = head_skin.subtract(tube([tuple(q) for q in crack_pts], [0.006, 0.011, 0.012, 0.01, 0.005]), k=0.004)
face_stitches = []
for j in (1, 2, 3):
    q = crack_pts[j]
    t_ = norm(crack_pts[min(j + 1, 4)] - crack_pts[j - 1])
    side = norm(np.cross(t_, grad(head_skin, q)))
    for sg in (1, -1):
        pa = on_surface(head_skin, q - side * 0.03 - t_ * 0.012 * sg, 0.004, 4)
        pb = on_surface(head_skin, q + side * 0.03 + t_ * 0.012 * sg, 0.004, 4)
        face_stitches.append(capsule(tuple(pa), tuple(pb), 0.0075))

# ---- nemes: copricapo a righe, ali laterali che si allargano verso le spalle
def nemes_f(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    t = np.clip((0.16 - z) / 0.52, 0.0, 1.0)                 # 0 alla fronte, 1 sulle spalle
    w = 0.235 + 0.19 * t ** 1.25
    yb = 0.2 + 0.04 * t
    yf = -0.135 + 0.02 * t
    dx = np.abs(x) - w
    dy = np.maximum(yf - y, y - yb)
    dz = np.maximum(-0.36 - z, z - 0.1)
    return (np.maximum(np.maximum(dx, dy), dz) * 0.85).astype(np.float32)


cap = ellipsoid((0.245, 0.265, 0.27), (0, 0.035, 0.06))
nemes_l = union(cap, SDF(nemes_f, (-0.45, -0.2, -0.38), (0.45, 0.26, 0.12)), k=0.05)
nemes_l = nemes_l.subtract(ellipsoid((0.185, 0.3, 0.28), (0, -0.2, -0.06)), k=0.03)     # spazio per il volto
nemes_l = nemes_l.subtract(ellipsoid((0.2, 0.22, 0.2), (0, 0.06, -0.42)), k=0.04)       # collo
# fascia d'oro in rilievo sulla fronte, al bordo del nemes
headband_l = torus(0.2, 0.022).rot(-10, 0, 0).translate((0, -0.045, 0.14)).intersect(
    SDF(lambda p: p[:, 1] - 0.02, (-1, -1, -1), (1, 0.02, 1)))

# ---- ureo: cobra reale che si alza dalla fascia sulla fronte (cappuccio con intarsio blu, occhi accesi)
UB, _ = project(head_core, (0, -0.05, 0.17), (0, -1.0, 0.35))
uraeus_body_l = tube(bezier(tuple(UB + (0, 0.01, -0.01)), tuple(UB + (0, -0.06, 0.04)), tuple(UB + (0, 0.0, 0.12)),
                            tuple(UB + (0, -0.04, 0.18)), 8), taper(9, 0.032, 0.026))
HOOD_C = UB + np.array([0, -0.05, 0.19])
hood_l = flatten(ellipsoid((0.085, 0.07, 0.1)), 0.35, axis=1).translate(HOOD_C)
uraeus_head_l = ell(HOOD_C + np.array([0, -0.035, 0.1]), (0.032, 0.032, 0.048), axis=(0, -1.0, 0.35))
uraeus_l = union(uraeus_body_l, hood_l, uraeus_head_l, k=0.02)
hood_inlay_l = flatten(ellipsoid((0.056, 0.07, 0.072)), 0.25, axis=1).translate(HOOD_C + np.array([0, -0.019, -0.005]))
uraeus_eyes_l = [sphere(0.0105, tuple(HOOD_C + np.array([sx * 0.019, -0.064, 0.112]))) for sx in (1, -1)]

# ---- barba posticcia intrecciata
BEARD = bezier((0, -0.125, -0.22), (0, -0.15, -0.34), (0, -0.165, -0.44), (0, -0.2, -0.53), 8)
beard_l = tube(BEARD, [0.036, 0.038, 0.04, 0.042, 0.043, 0.044, 0.045, 0.046, 0.044])
beard_l = union(beard_l, ell(np.array(BEARD[-1]) + (0, -0.01, -0.01), (0.05, 0.035, 0.022), axis=(0, -0.3, 1.0)), k=0.02)
beard_bands_l = []
for j in range(1, 8):
    q0, q1 = np.array(BEARD[j - 1]), np.array(BEARD[min(j + 1, 8)])
    beard_bands_l.append(paint(beard_l, slab(np.array(BEARD[j]), q1 - q0, 0.013, 0.1), out=0.011, inn=0.03))


def hp(p):
    return (R_HEAD.astype(np.float64) @ (HS * np.asarray(p, dtype=np.float64))) + HEAD_T


def to_head(p):
    """Mondo -> spazio locale della testa (per i motivi a righe)."""
    return ((p - HEAD_T) @ R_HEAD) / HS


# ---- bande del nemes che scendono sul petto (in coordinate del mondo, appoggiate al petto)
lappets = []
for sx in (1, -1):
    top = hp((sx * 0.26, -0.07, -0.16))
    pb, nb = project(core, (sx * 0.27, -0.4, 1.12), (0, -1.0, 0.05))
    bot = pb + nb * 0.06
    strip = flatten(tube([(0, 0, 0.0), (0, 0, -0.33), (0, 0, -0.66)], [0.072, 0.078, 0.072]), 0.3, axis=1)
    L = float(np.linalg.norm(top - bot))
    lappets.append(strip.scale(L / 0.66).rotate(frame(top - bot, (0.0, -1.0, 0.1))).translate(top))
nemes_w = union(Hd(nemes_l), *lappets, k=0.04)

STRIPE_F = np.array([0.0, -0.62, 0.04], dtype=np.float32)  # centro dei cerchi delle righe (davanti al volto)
STRIPE_P = 0.16


CAVITY = ellipsoid((0.185, 0.3, 0.28), (0, -0.2, -0.06))
NECK_HOLE = ellipsoid((0.2, 0.22, 0.2), (0, 0.06, -0.42))


def stripe_region_w(p):
    q = to_head(p)
    d = np.sqrt(np.einsum("ij,ij->i", q - STRIPE_F, q - STRIPE_F)) / STRIPE_P
    fr = d - np.floor(d)
    band = (np.abs(fr - 0.25) - 0.25) * STRIPE_P * HS
    hidden = np.minimum(np.abs(CAVITY(q)) - 0.02, np.abs(NECK_HOLE(q)) - 0.02) * -1.0   # > 0 sulle pareti nascoste
    return np.maximum(band, hidden * HS).astype(np.float32)


nemes_stripes = paint(nemes_w, SDF(stripe_region_w, nemes_w.lo - 0.05, nemes_w.hi + 0.05), out=0.016, inn=0.04)

# ============================================================ collare usekh sul petto (sotto le bande del nemes e la barba)
SC_C = np.array([0.0, -0.55, 1.5], dtype=np.float32)            # base del collo
SC_A = norm((0.0, -0.22, 0.44))                                   # asse del collo
SC_F = norm(np.cross((1.0, 0.0, 0.0), SC_A))                      # davanti (perpendicolare all'asse)
SC_IN, SC_OUT, SC_T = 0.3, 0.55, 0.03


def sc_zone(p, r_in=SC_IN, r_out=SC_OUT):
    q = p - SC_C
    d = np.sqrt(np.einsum("ij,ij->i", q, q))
    t = q @ SC_A.astype(np.float32)
    rho = np.sqrt(np.maximum(d * d - t * t, 0.0))
    front = (q @ SC_F.astype(np.float32))
    return np.maximum.reduce([r_in - d, d - r_out, 0.24 - rho, -0.05 - front]).astype(np.float32)


SC_ZONE = SDF(sc_zone, SC_C - SC_OUT - 0.05, SC_C + SC_OUT + 0.05)
collar_base = paint(core, SC_ZONE, out=SC_T, inn=0.025)
col_top = core.offset(SC_T)


def sc_curve(r, n=40, span=118.0):
    """Punti sulla superficie del collare a distanza r dal centro, sul davanti (da un fianco all'altro)."""
    pts = []
    for phi in np.radians(np.linspace(-span, span, n)):
        out = SC_F * math.cos(phi) + np.array([1.0, 0.0, 0.0]) * math.sin(phi)

        def q_of(th, out=out):
            return SC_C + r * (-SC_A * math.cos(th) + out * math.sin(th))
        lo_t, hi_t = 0.0, 0.62 * math.pi
        if col_top(q_of(lo_t)[None, :].astype(np.float32))[0] > 0 or col_top(q_of(hi_t)[None, :].astype(np.float32))[0] < 0:
            continue
        for _ in range(30):
            mid = 0.5 * (lo_t + hi_t)
            if col_top(q_of(mid)[None, :].astype(np.float32))[0] < 0:
                lo_t = mid
            else:
                hi_t = mid
        if sc_zone(q_of(lo_t)[None, :].astype(np.float32), r - 0.02, r + 0.02)[0] > 0.03:
            continue
        pts.append((q_of(lo_t), q_of(lo_t - 0.04) - q_of(lo_t + 0.04)))
    return pts


collar_rods = []
for r, rr in ((SC_IN + 0.01, 0.024), (0.43, 0.02), (SC_OUT - 0.005, 0.026)):
    pts = [q for q, _ in sc_curve(r)]
    collar_rods.append(tube([tuple(q) for q in pts], rr))
collar_drops = []
for q, down in sc_curve(SC_OUT + 0.02, n=17, span=110.0):
    nrm = grad(col_top, q)
    down = norm(down - nrm * float(np.dot(down, nrm)))
    a_ = q + nrm * 0.005
    collar_drops.append(round_cone(tuple(a_ + down * 0.005), tuple(a_ + down * 0.085), 0.024, 0.04))

# ============================================================ ali di falco mezze alzate (piano locale u lungo il braccio, v verso le punte)
WING_SH = np.array([0.26, -0.1, 1.44])          # spalla (perno dell'animazione), lato +X
N_OUT = norm((0.5, -0.8, 0.22))                 # faccia in vista dell'ala (in fuori e in avanti)
U0 = np.array([0.52, 0.34, 0.8])
WU = norm(U0 - N_OUT * float(np.dot(U0, N_OUT)))
WV = -norm(np.cross(N_OUT, WU))
WW = np.cross(WU, WV)                           # = -N_OUT
W_M = np.stack([WU, WV, WW], axis=1).astype(np.float32)
ARM_L = 1.05


def feather(base, d, L, a, layer, th=0.03):
    """Penna: ellissoide schiacciato che parte da 'base' (piano dell'ala) lungo la direzione d."""
    d = norm((d[0], d[1], 0.0))
    c = np.array([base[0] + d[0] * L / 2, base[1] + d[1] * L / 2, layer])
    return ellipsoid((a, L / 2, th)).rotate(frame((0.0, 0.0, 1.0), d)).translate(c)


wing_gold_l, wing_lapis_l = [], []
arm_pts = [(u, -0.035 * math.sin(math.pi * u / ARM_L), -0.02) for u in np.linspace(0.0, ARM_L, 9)]
wing_gold_l.append(tube(arm_pts, taper(9, 0.08, 0.055)))
for u in np.linspace(0.05, ARM_L - 0.03, 8):                           # fila 1: piccole penne d'oro a scaglia
    wing_gold_l.append(feather((u, -0.05), (0.2, 1.0), 0.25, 0.08, -0.05))
for u in np.linspace(0.07, ARM_L - 0.04, 7):                           # fila 2: copritrici di lapislazzuli
    wing_lapis_l.append(feather((u, 0.06), (0.16, 1.0), 0.36, 0.085, -0.025))
FLIGHT = []
for i, u in enumerate(np.linspace(0.0, 0.66, 7)):                     # secondarie
    FLIGHT.append(((u, 0.18), (0.1 + 0.05 * i, 1.0), 0.5 + 0.035 * i))
for i, ang in enumerate(np.linspace(66, 6, 7)):                        # remiganti a ventaglio dal polso
    a_ = math.radians(ang)
    FLIGHT.append(((0.74 + 0.05 * i, 0.2 - 0.035 * i), (math.cos(a_), math.sin(a_)), 0.66 + 0.045 * i))
for j, (base, d, L) in enumerate(FLIGHT):
    (wing_gold_l if j % 2 else wing_lapis_l).append(feather(base, d, L, 0.078, 0.0 + 0.008 * (j % 2)))


def place_wing(shape, sx):
    s = shape.rotate(W_M).translate(WING_SH)
    return s if sx > 0 else s.mirrored()


# ============================================================ fregio di geroglifici turchesi sui fianchi
FS = 1.22   # scala del fregio


def flank_point(sx, s, t):
    """Coordinate del fregio (s lungo il corpo da davanti, t in alto) -> punto interno da proiettare."""
    y = -0.2 + s * FS
    z = 0.84 - 0.6 * s * FS + t * FS
    return np.array([sx * 0.05, y, z])


def glyph_strokes():
    """Tratti dei geroglifici nel piano del fregio (s, t)."""
    st = [[(0.0, -0.13), (0.45, -0.13)]]                                          # riga di base
    c = 0.07                                                                     # ankh
    st += [[(c + 0.035 * math.cos(a), 0.05 + 0.04 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 13)],
           [(c, 0.01), (c, -0.09)], [(c - 0.04, 0.0), (c + 0.04, 0.0)]]
    c = 0.2                                                                      # occhio
    st += [[(c - 0.06, 0.0), (c - 0.02, 0.03), (c + 0.03, 0.03), (c + 0.06, 0.0)],
           [(c - 0.06, 0.0), (c - 0.02, -0.025), (c + 0.03, -0.022), (c + 0.06, 0.0)],
           [(c, -0.025), (c - 0.005, -0.08), (c + 0.025, -0.09)], [(c - 0.055, 0.06), (c + 0.06, 0.055)]]
    c = 0.33                                                                     # acqua (tre zig-zag)
    for tt in (0.05, 0.0, -0.05):
        st.append([(c - 0.06 + 0.024 * k, tt + (0.014 if k % 2 else -0.014)) for k in range(6)])
    c = 0.46                                                                     # disco solare con il punto
    st.append([(c + 0.045 * math.cos(a), 0.0 + 0.045 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 15)])
    st.append([(c - 0.004, 0.0), (c + 0.004, 0.0)])
    return st


frieze = []
for sx in (1, -1):
    for stroke in glyph_strokes():
        pts2 = resample(np.array(stroke), 0.016)
        origins = [flank_point(sx, s_, t_) for s_, t_ in pts2]
        q, nr = project_many(core, origins, [(sx, 0.0, 0.0)])
        frieze.append(tube([tuple(p - n * 0.006) for p, n in zip(q, nr)], 0.02))

# ============================================================ artigli e ciuffo della coda
claws = []
for tip, fwd, sz, zf in TOES:
    t0 = np.asarray(tip, dtype=np.float64)
    claws.append(horn(t0 + (0, 0, 0.012), t0 + fwd * 0.05 * sz + (0, 0, 0.025 * sz), t0 + fwd * 0.1 * sz,
                      t0 + fwd * 0.13 * sz + (0, 0, -0.035 * sz), 0.04 * sz, 0.012, n=7).intersect(halfspace_z(zf + 0.002)))
front_legs = [union(round_cone(e_, w_, 0.15, 0.11), round_cone(w_, w_ + (w_ - e_) * 0.3, 0.11, 0.11)) for _, _, e_, w_ in WRISTS]
bracelets = [paint(fl, slab(c, ax, 0.035, 0.25), out=0.026, inn=0.02) for fl, (c, ax, _, _) in zip(front_legs, WRISTS)]
tuft_bands = [paint(tuft_core, slab(TAIL_END + TAIL_DIR * d, TAIL_DIR, 0.028, 0.3), out=0.012, inn=0.03)
              for d in (0.05, 0.16, 0.27)]

# ============================================================ parti
GS = float(os.environ.get("GS", 1.1))   # scala finale del modello


def add(name, sdf, color, voxel, **kw):
    if "pivot" in kw and kw["pivot"] is not None:
        kw["pivot"] = tuple(float(c) * GS for c in kw["pivot"])
    m.add(name, sdf.scale(GS) if GS != 1.0 else sdf, color, voxel=voxel * GS * VX, **kw)


add("Body", fast_union([tuft_core], base=core), GOLD_BODY, 0.032, material="Foil", tris=2800)
add("Face", Hd(head_skin), GOLD_BODY, 0.012, material="Foil", role="skin", tris=1300)
add("Nemes", fast_union([nemes_w, Hd(union(headband_l, uraeus_l, beard_l))]), GOLD, 0.017, material="Foil",
    role="detail", tris=1500)
add("CollarGold", fast_union(collar_rods + collar_drops), GOLD, 0.012, material="Foil", role="detail", tris=500)
add("NemesStripes", nemes_stripes, LAPIS, 0.016, role="detail", tris=1600)
add("Collar", collar_base, LAPIS, 0.022, role="detail", tris=600)
lapis = [Hd(x) for x in brows + beard_bands_l + [hood_inlay_l]] + tuft_bands + claws + bracelets
add("Lapis", fast_union(lapis), LAPIS, 0.009, role="detail", tris=900)
add("Block", block, STONE, 0.03, role="detail", tris=250, smooth=False)
add("Frost", fast_union(frieze), TURQ, 0.012, material="Neon", role="glow", tris=900)
add("EyeGlow", Hd(fast_union(eyes + [crack] + uraeus_eyes_l)), EYE_GLOW, 0.008, material="Neon", role="glow", tris=300)
add("Kohl", Hd(fast_union(kohl + pupils + mouth_dark)), KOHL, 0.007, role="eye", tris=550)
add("Teeth", Hd(fast_union(teeth)), TOOTH, 0.005, role="shine", tris=150)
add("Stitches", Hd(fast_union(face_stitches)), THREAD, 0.005, role="detail", tris=150)
for sx, nm in ((1, "WingR"), (-1, "WingL")):
    piv = tuple(WING_SH * np.array([sx, 1, 1]))
    add(nm, place_wing(fast_union(wing_lapis_l), sx), LAPIS, 0.018, role="detail", tris=1000, group=nm, pivot=piv)
    add(nm + "Gold", place_wing(fast_union(wing_gold_l), sx), GOLD, 0.018, material="Foil", role="detail", tris=1000,
        group=nm, pivot=piv)

if __name__ == "__main__":
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    if only:
        m.parts = [p for p in m.parts if p.name in only]
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
