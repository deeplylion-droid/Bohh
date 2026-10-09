"""Pentadrago (PentaDragon) - pet ULTRA, il grado di rarita' piu' alto: il boss della torre.

Drago colossale viola reale con CINQUE teste su lunghi colli serpentini aperti a ventaglio dal
petto. La testa centrale, la piu' grande e alta, porta una corona di corna d'oro e ruggisce con la
gola carica di energia; le altre quattro hanno ognuna un'espressione (ringhio a denti scoperti,
ruggito verso il cielo, ghigno sornione a bocca chiusa, sibilo con la lingua biforcuta). Ali da
pipistrello enormi e alzate, con membrane strappate e una toppa cucita col filo d'oro (il tocco
"toy horror"), quattro zampe muscolose con artigli d'oro, placche lilla su ventre e colli, spine
dorsali e una mazza chiodata in fondo alla coda.

AURA: tutti i pezzi luminosi dell'aura stanno nell'unica parte Neon "Aura" (il gioco ci attacca
le particelle): anello di energia crepitante ai piedi, schegge di rune sospese attorno al corpo e
un nucleo di cristallo nel petto da cui partono cinque venature, una per ogni collo.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, bezier, box, capsule, ellipsoid, euler, halfspace_z, prism, project,  # noqa: E402
                     round_cone, smin, sphere, tube, union)
from lib.toy import Model  # noqa: E402


# ============================================================ helper (lib/ non si modifica: copiati/adattati qui)
def norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def grad(sdf, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float64)
    g = np.zeros(3)
    for ax in range(3):
        e = np.zeros(3)
        e[ax] = eps
        g[ax] = sdf((p + e)[None, :].astype(np.float32))[0] - sdf((p - e)[None, :].astype(np.float32))[0]
    return g / max(np.linalg.norm(g), 1e-9)


def on_surface(sdf, p, lift=0.0, iters=4):
    """Porta p sulla superficie (a distanza 'lift' verso l'esterno) seguendo il gradiente."""
    p = np.asarray(p, dtype=np.float64)
    for _ in range(iters):
        d = float(sdf(p[None, :].astype(np.float32))[0])
        p = p - grad(sdf, p) * (d - lift)
    return p


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


def flatten(shape, s, axis=1):
    """Schiaccia (s<1) o allunga (s>1) una forma lungo un asse, con distanza conservativa."""
    def f(p):
        q = p.copy()
        q[:, axis] = q[:, axis] / s
        return shape(q) * min(s, 1.0)

    lo, hi = shape.lo.copy(), shape.hi.copy()
    lo[axis] *= s
    hi[axis] *= s
    return SDF(f, lo, hi)


def shell_paint(base, region, out=0.02, inn=0.05, margin=0.04):
    """Vernice a guscio sottile di 'base' dentro 'region' (base valutata solo vicino alla regione).

    Equivale a base.offset(out).subtract(base.offset(-inn)).intersect(region), ma valuta la base una
    volta sola e solo dove serve.
    """
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


def blade(L, rb, thin_k=0.42, curve=0.35, n=6):
    """Spina a lama lungo +Z (base nell'origine), sottile lungo X, punta piegata verso +Y."""
    pts = bezier((0, 0, -0.03), (0, 0, L * 0.45), (0, curve * L * 0.35, L * 0.8), (0, curve * L, L), n)
    return flatten(tube(pts, taper(n + 1, rb, 0.012, 1.15)), thin_k, axis=0)


def diamond(h, w, d=None):
    """Bipiramide (scheggia di cristallo) lungo Z: semi-altezza h, semi-larghezze w (X) e d (Y)."""
    d = d or w
    k = 1.0 / math.sqrt(1 / w ** 2 + 1 / d ** 2 + 1 / h ** 2)

    def f(p):
        q = np.abs(p)
        return (q[:, 0] / w + q[:, 1] / d + q[:, 2] / h - 1.0) * k

    return SDF(f, (-w, -d, -h), (w, d, h))


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


# ============================================================ colori
PURPLE = (104, 40, 176)      # viola reale: corpo e ossa delle ali
PURPLE_DK = (54, 16, 88)     # membrane delle ali
LILAC = (206, 172, 248)      # placche di ventre e colli, toppa sull'ala
GOLD = (255, 190, 58)        # corna, artigli, spine, mazza, filo della toppa
MOUTH = (34, 6, 40)          # interno delle bocche, contorno e pupille degli occhi
TOOTH = (255, 251, 242)
TONGUE = (236, 72, 156)
EYE_GLOW = (255, 132, 240)
AURA = (212, 74, 255)

m = Model("PentaDragon", "pet")

# ============================================================ tronco possente
chest = ellipsoid((0.66, 0.58, 0.6), (0, -0.32, 1.32))
belly = ellipsoid((0.6, 0.62, 0.52), (0, 0.18, 1.14))
hips = ellipsoid((0.56, 0.52, 0.5), (0, 0.68, 1.06))
yoke = ellipsoid((0.64, 0.42, 0.4), (0, -0.4, 1.68))  # spalle alte da cui partono i cinque colli
pecs = [ellipsoid((0.3, 0.2, 0.3), (sx * 0.27, -0.76, 1.4)) for sx in (1, -1)]
back_ridge = tube(bezier((0, -0.32, 1.98), (0, 0.12, 1.66), (0, 0.6, 1.58), (0, 1.0, 1.4), 8), 0.1)
wing_roots = [ellipsoid((0.2, 0.24, 0.2), (sx * 0.4, 0.14, 1.72)) for sx in (1, -1)]
trunk = union(chest, belly, hips, k=0.35)
trunk = union(trunk, yoke, k=0.25)
trunk = union(trunk, *pecs, back_ridge, k=0.12)
trunk = union(trunk, *wing_roots, k=0.12)

TOES = []  # (punta del dito, direzione in avanti) per gli artigli


def front_leg(sx):
    sh, el, wr, paw = (sx * 0.56, -0.36, 1.2), (sx * 0.7, -0.24, 0.68), (sx * 0.68, -0.44, 0.22), (sx * 0.68, -0.56, 0.11)
    muscles = [ellipsoid((0.27, 0.33, 0.37), (sx * 0.6, -0.4, 1.18)),   # spalla
               round_cone(sh, el, 0.25, 0.17),
               ellipsoid((0.17, 0.21, 0.27), (sx * 0.69, -0.4, 0.9)),   # bicipite
               round_cone(el, wr, 0.18, 0.125),
               ellipsoid((0.165, 0.19, 0.23), (sx * 0.72, -0.3, 0.5)),  # avambraccio
               ellipsoid((0.21, 0.27, 0.13), paw)]
    toes = []
    for dx, dy in ((-0.17, 0.07), (-0.058, 0.0), (0.058, 0.0), (0.17, 0.07)):
        tip = (paw[0] + dx, -0.82 + dy, 0.075)
        toes.append(capsule(paw, tip, 0.072))
        TOES.append((tip, norm((dx * 0.6, -1.0, 0.0)), 1.0))
    return union(union(*muscles, k=0.09), *toes, k=0.06)


def rear_leg(sx):
    hip, knee, hock, foot = (sx * 0.55, 0.66, 1.0), (sx * 0.68, 0.36, 0.6), (sx * 0.68, 0.86, 0.32), (sx * 0.68, 0.62, 0.1)
    muscles = [ellipsoid((0.31, 0.46, 0.48), (sx * 0.56, 0.62, 0.98)),   # coscia
               round_cone(hip, knee, 0.27, 0.165),
               round_cone(knee, hock, 0.165, 0.105),
               ellipsoid((0.14, 0.19, 0.21), (sx * 0.69, 0.66, 0.5)),    # polpaccio
               round_cone(hock, (sx * 0.68, 0.72, 0.1), 0.105, 0.11),
               ellipsoid((0.2, 0.26, 0.12), foot)]
    toes = []
    for dx, dy in ((-0.16, 0.07), (-0.055, 0.0), (0.055, 0.0), (0.16, 0.07)):
        tip = (foot[0] + dx, 0.38 + dy, 0.072)
        toes.append(capsule(foot, tip, 0.068))
        TOES.append((tip, norm((dx * 0.6, -1.0, 0.0)), 0.92))
    return union(union(*muscles, k=0.09), *toes, k=0.06)


legs = [front_leg(1), front_leg(-1), rear_leg(1), rear_leg(-1)]

# coda lunga che gira sul fianco destro e finisce con una mazza chiodata
TA = [(0, 0.92, 1.08), (0.05, 1.7, 0.72), (0.75, 2.1, 0.3), (1.35, 1.78, 0.3)]
TB = [(1.35, 1.78, 0.3), (1.8, 1.55, 0.3), (2.0, 1.05, 0.48), (1.86, 0.68, 0.8)]
TAIL_DENSE = np.array(bezier(*TA, 60) + bezier(*TB, 50)[1:])


def tail_rad(u):
    return 0.36 + (0.085 - 0.36) * u ** 0.8


_ti = list(range(0, len(TAIL_DENSE), 5)) + ([len(TAIL_DENSE) - 1] if (len(TAIL_DENSE) - 1) % 5 else [])
tail = tube([tuple(TAIL_DENSE[i]) for i in _ti], [tail_rad(i / (len(TAIL_DENSE) - 1)) for i in _ti])
MACE_C = np.array(TB[-1])
tail = union(tail, sphere(0.17, tuple(MACE_C)), k=0.06)

# ============================================================ le cinque teste
JAW_Z = -0.05                 # quota (locale) della linea della bocca
HINGE = (0.0, -0.03, JAW_Z)   # cerniera della mandibola
NECK_SOCKET = (0.0, 0.1, -0.03)

HEADS = [
    # la regina al centro: la piu' grande e alta, corona d'oro, ruggito con la gola carica di energia
    dict(T=(0.0, -0.92, 3.12), s=1.12, yaw=0, pitch=14, roll=0, open=34, crown=True, horn=1.35, nose_horn=True,
         lid=((0.006, 0.42), (0.006, 0.42)), slant=16, tongue="in", glow=True, tooth=1.15,
         P0=(0, -0.45, 1.86), d0=(0, -0.62, 0.78), L0=0.62, L1=0.6, r0=0.28),
    # destra interna: ringhio a denti scoperti, occhi stretti, testa inclinata
    dict(T=(0.98, -0.86, 2.58), s=0.88, yaw=24, pitch=6, roll=-12, open=14, horn=1.05, nose_horn=True,
         lid=((-0.01, 0.5), (-0.01, 0.5)), slant=22, tongue="in", tooth=1.1,
         P0=(0.3, -0.42, 1.74), d0=(0.42, -0.72, 0.55), L0=0.5, L1=0.48, r0=0.23),
    # sinistra interna: ruggito verso il cielo
    dict(T=(-0.98, -0.86, 2.66), s=0.88, yaw=-26, pitch=-10, roll=8, open=28, horn=1.1,
         lid=((0.016, 0.3), (0.016, 0.3)), slant=12, tongue="in", glow=True,
         P0=(-0.3, -0.42, 1.74), d0=(-0.42, -0.72, 0.55), L0=0.5, L1=0.48, r0=0.23),
    # destra esterna: ghigno sornione a bocca chiusa (denti a incastro in vista), un occhio socchiuso
    dict(T=(1.56, -0.74, 2.0), s=0.78, yaw=42, pitch=8, roll=-6, open=3, horn=1.0, grin=True,
         lid=((0.004, 0.25), (-0.024, 0.1)), slant=18,
         P0=(0.52, -0.32, 1.55), d0=(0.72, -0.62, 0.3), L0=0.5, L1=0.42, r0=0.21),
    # sinistra esterna: sibilo con la lingua biforcuta fuori
    dict(T=(-1.56, -0.74, 1.98), s=0.78, yaw=-40, pitch=0, roll=10, open=20, horn=1.0,
         lid=((0.0, 0.45), (0.0, 0.45)), slant=20, tongue="out",
         P0=(-0.52, -0.32, 1.55), d0=(-0.72, -0.62, 0.3), L0=0.5, L1=0.42, r0=0.21),
]


def footprint(fx, fy, cy):
    """Ellisse nel piano XY locale (distanza approssimata), per delimitare la bocca."""
    def f(p):
        ex = p[:, 0] / fx
        ey = (p[:, 1] - cy) / fy
        return (np.sqrt(ex * ex + ey * ey) - 1.0) * min(fx, fy)
    return f


def head_kit(h):
    """Teschio cornuto con mandibola aperta di h['open'] gradi; ritorna le forme (spazio mondo) per parte."""
    s = h["s"]
    T = np.asarray(h["T"], dtype=np.float32)
    R = euler(h["pitch"], h["roll"], h["yaw"])
    th = h["open"]

    def W(shape):  # locale -> mondo
        return shape.scale(s).rotate(R).translate(T)

    def J(shape):  # sistema della mandibola chiusa -> mandibola aperta
        return shape.rot(th, 0, 0, pivot=HINGE)

    # ---- cranio, muso, arcate sopracciliari feroci (coordinate locali: muso verso -Y)
    cran = ellipsoid((0.24, 0.27, 0.22), (0, -0.08, 0.1))
    occ = ellipsoid((0.2, 0.17, 0.18), (0, 0.08, 0.1))
    snout = ellipsoid((0.155, 0.31, 0.12), (0, -0.44, 0.03))
    nose = ellipsoid((0.13, 0.11, 0.1), (0, -0.67, 0.05))
    ridge = capsule((0, -0.16, 0.22), (0, -0.62, 0.115), 0.05)
    cheeks = [ellipsoid((0.09, 0.15, 0.085), (sx * 0.18, -0.19, 0.0)) for sx in (1, -1)]
    brows = [capsule((sx * 0.065, -0.35, 0.175), (sx * 0.235, -0.13, 0.255), 0.062) for sx in (1, -1)]
    upper = union(cran, occ, k=0.12)
    upper = union(upper, snout, k=0.14)
    upper = union(upper, nose, ridge, k=0.07)
    upper = union(upper, *cheeks, k=0.08)
    upper = union(upper, *brows, k=0.05)
    upper = upper.subtract(union(*[sphere(0.034, (sx * 0.065, -0.765, 0.095)) for sx in (1, -1)]), k=0.02)
    upper = upper.subtract(box((0.6, 0.5, 0.3), (0, HINGE[1] - 0.5, JAW_Z - 0.3)), k=0.015)

    jaw = union(ellipsoid((0.14, 0.3, 0.085), (0, -0.37, -0.1)),
                ellipsoid((0.17, 0.17, 0.1), (0, -0.1, -0.09)),
                ellipsoid((0.1, 0.09, 0.07), (0, -0.62, -0.095)), k=0.08)
    jaw = jaw.subtract(box((0.6, 0.6, 0.3), (0, -0.4, JAW_Z + 0.3)), k=0.015)

    # ---- occhi luminosi a mandorla con pupilla a fessura, palpebra arrabbiata
    glow, dark, lids = [], [], []
    for sx, (cut, slope) in zip((1, -1), h["lid"]):
        p, n = project(upper, (sx * 0.08, -0.2, 0.125), (sx * 0.62, -0.76, 0.1))
        a1 = sx * norm(np.cross((0.0, 0.0, 1.0), n))  # dall'angolo interno a quello esterno
        a2 = -sx * n
        a3 = np.cross(a1, a2)
        sl = math.radians(h["slant"])
        a1, a3 = a1 * math.cos(sl) + a3 * math.sin(sl), a3 * math.cos(sl) - a1 * math.sin(sl)
        M = np.stack([a1, a2, a3], axis=1).astype(np.float32)
        c = p - n * 0.02
        eye = ellipsoid((0.074, 0.044, 0.046)).rotate(M).translate(c)
        glow.append(eye)
        dark.append(ellipsoid((0.092, 0.036, 0.062)).rotate(M).translate(p - n * 0.032))
        dark.append(thin(eye, 0.004, 0.02).intersect(ellipsoid((0.013, 0.2, 0.04)).rotate(M).translate(c)))
        cutp = SDF(lambda q, c0=cut, k0=slope: (c0 + k0 * q[:, 0] - q[:, 2]) / math.sqrt(1 + k0 * k0),
                   (-0.12, -0.12, -0.12), (0.12, 0.12, 0.12))
        lids.append(ellipsoid((0.086, 0.052, 0.058)).intersect(cutp).rotate(M).translate(c))

    # ---- bocca: palato e lingua scuri, parete della gola, denti aguzzi su due file
    pal_fp, jaw_fp = footprint(0.085, 0.25, -0.4), footprint(0.08, 0.24, -0.38)
    pal_reg = SDF(lambda p: np.maximum(pal_fp(p), p[:, 2] - (JAW_Z + 0.03)), (-0.09, -0.66, JAW_Z - 0.05),
                  (0.09, -0.14, JAW_Z + 0.03))
    jaw_reg = SDF(lambda p: np.maximum(jaw_fp(p), (JAW_Z - 0.03) - p[:, 2]), (-0.09, -0.63, JAW_Z - 0.03),
                  (0.09, -0.13, JAW_Z + 0.05))
    dark.append(shell_paint(upper, pal_reg, out=0.006, inn=0.03, margin=0.02))
    dark.append(J(shell_paint(jaw, jaw_reg, out=0.006, inn=0.03, margin=0.02)))
    if th > 6:
        Rinv = euler(-th, 0, 0)
        piv = np.asarray(HINGE, dtype=np.float32)
        thr_fp = footprint(0.12, 0.14, -0.1)

        def wedge(p, Rinv=Rinv, piv=piv, fp=thr_fp):
            q = (p - piv) @ Rinv.T + piv
            return np.maximum(np.maximum(p[:, 2] - (JAW_Z + 0.004), (JAW_Z - 0.004) - q[:, 2]), fp(p))

        dark.append(SDF(wedge, (-0.12, -0.24, JAW_Z - 0.25), (0.12, 0.04, JAW_Z + 0.01)))
    if h.get("glow"):
        yg = -0.21
        gap = (HINGE[1] - yg) * math.tan(math.radians(th))
        glow.append(sphere(min(0.075, 0.45 * gap), (0, yg + 0.02, JAW_Z - gap * 0.5)))

    teeth = []
    inset = -0.006 if h.get("grin") else 0.024
    tk = h.get("tooth", 1.0)
    rows_up = [((0, -0.45, JAW_Z + 0.012), (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0), abs(a) > 50)
               for a in np.linspace(-58, 58, 7)]
    rows_up += [((0, y, JAW_Z + 0.012), (sx, 0, 0), False) for y in (-0.34, -0.26, -0.18) for sx in (1, -1)]
    for o, d, big in rows_up:
        p, n = project(upper, o, d)
        b = p - norm((n[0], n[1], 0.0)) * inset
        L = (0.12 if big else 0.06) * tk
        r = 0.032 if big else 0.02
        teeth.append(round_cone((b[0], b[1], JAW_Z + 0.025), (b[0], b[1], JAW_Z - L), r, 0.004))
    rows_lo = [((0, -0.42, JAW_Z - 0.012), (math.sin(math.radians(a)), -math.cos(math.radians(a)), 0), abs(a) > 40)
               for a in np.linspace(-48, 48, 5)]
    rows_lo += [((0, y, JAW_Z - 0.012), (sx, 0, 0), False) for y in (-0.3, -0.21) for sx in (1, -1)]
    for o, d, big in rows_lo:
        p, n = project(jaw, o, d)
        b = p - norm((n[0], n[1], 0.0)) * inset
        L = (0.09 if big else 0.05) * tk
        r = 0.027 if big else 0.018
        teeth.append(J(round_cone((b[0], b[1], JAW_Z - 0.025), (b[0], b[1], JAW_Z + L), r, 0.004)))

    tongue = None
    if h.get("tongue") == "in":
        tongue = J(ellipsoid((0.07, 0.19, 0.035), (0, -0.33, JAW_Z - 0.012)))
    elif h.get("tongue") == "out":
        stem = tube([(0, -0.2, JAW_Z - 0.02), (0, -0.42, JAW_Z), (0, -0.62, JAW_Z + 0.005), (0, -0.8, JAW_Z - 0.04)],
                    [0.05, 0.045, 0.036, 0.028])
        forks = [tube([(0, -0.8, JAW_Z - 0.04), (sx * 0.035, -0.9, JAW_Z - 0.07), (sx * 0.075, -0.97, JAW_Z - 0.06)],
                      [0.026, 0.018, 0.01]) for sx in (1, -1)]
        tongue = J(union(stem, *forks, k=0.02))

    # ---- corna d'oro (piu' grandi e con la corona per la regina), spine della mandibola, cresta
    gold = []
    hs = h.get("horn", 1.0)
    for sx in (1, -1):
        b = np.array([sx * 0.1, 0.0, 0.24])
        gold.append(horn(b, b + np.array([sx * 0.06, 0.2, 0.13]) * hs, b + np.array([sx * 0.15, 0.43, 0.18]) * hs,
                         b + np.array([sx * 0.21, 0.62, 0.36]) * hs, 0.075 * hs ** 0.5, 0.013, n=16))
        b2 = np.array([sx * 0.19, 0.0, 0.06])
        gold.append(horn(b2, b2 + (sx * 0.13, 0.12, -0.02), b2 + (sx * 0.23, 0.24, 0.01), b2 + (sx * 0.31, 0.33, 0.09),
                         0.05, 0.012))
        jb = np.array([sx * 0.14, -0.08, -0.12])
        gold.append(J(horn(jb, jb + (sx * 0.08, 0.08, -0.03), jb + (sx * 0.13, 0.16, -0.05), jb + (sx * 0.17, 0.22, -0.04),
                           0.04, 0.012, n=8)))
        if h.get("crown"):
            cb = np.array([sx * 0.05, -0.1, 0.27])
            gold.append(horn(cb, cb + (sx * 0.02, 0.0, 0.15), cb + (sx * 0.07, 0.08, 0.27), cb + (sx * 0.12, 0.2, 0.34),
                             0.052, 0.012))
            cb = np.array([sx * 0.16, -0.06, 0.24])
            gold.append(horn(cb, cb + (sx * 0.08, 0.02, 0.12), cb + (sx * 0.15, 0.1, 0.2), cb + (sx * 0.22, 0.2, 0.24),
                             0.045, 0.012))
    if h.get("nose_horn"):
        gold.append(horn((0, -0.56, 0.12), (0, -0.61, 0.21), (0, -0.59, 0.27), (0, -0.52, 0.31), 0.045, 0.012, n=8))
    for y, z, L in ((-0.14, 0.28, 0.1), (0.0, 0.3, 0.12), (0.13, 0.26, 0.1)):
        gold.append(blade(L, 0.05).rotate(frame((0, 0.45, 1.0), (0, 1, 0))).translate((0, y, z)))

    skin = union(upper, J(jaw), *lids, k=0.012)
    return dict(skin=W(skin), gold=[W(g) for g in gold], dark=[W(d) for d in dark], teeth=[W(t) for t in teeth],
                glow=[W(g) for g in glow], tongue=W(tongue) if tongue is not None else None)


def neck_kit(h):
    """Collo serpentino a S dalla base nel petto all'attacco della testa."""
    s = h["s"]
    R = euler(h["pitch"], h["roll"], h["yaw"]).astype(np.float64)
    T = np.asarray(h["T"], dtype=np.float64)
    P3 = R @ (s * np.asarray(NECK_SOCKET)) + T
    P2 = P3 + R @ norm((0, 0.72, -0.69)) * h["L1"]
    P0 = np.asarray(h["P0"], dtype=np.float64)
    P1 = P0 + norm(h["d0"]) * h["L0"]
    r0, r1 = h["r0"], 0.15 * s

    def rad(u):
        return r1 + (r0 - r1) * (1.0 - u) ** 2

    n = 16
    sdf = tube(bezier(P0, P1, P2, P3, n), [rad(i / n) for i in range(n + 1)])
    return dict(sdf=sdf, dense=np.array(bezier(P0, P1, P2, P3, 120)), rad=rad, s=s)


heads = [head_kit(h) for h in HEADS]
necks = [neck_kit(h) for h in HEADS]
neckheads = [union(nk["sdf"], hk["skin"], k=0.07 * h["s"]) for nk, hk, h in zip(necks, heads, HEADS)]

body_main = fast_union(legs, k=0.13, base=trunk)
core = fast_union([tail, *neckheads], k=0.16, base=body_main)
core = core.intersect(halfspace_z(0.0))
m.add("Body", core, PURPLE, tris=15000, voxel=0.025)

# ============================================================ placche lilla: ventre a fasce e gola dei colli
BO = np.array([0.0, -0.1, 1.2])   # centro delle fasce del ventre (piano YZ)
U0, U1, NPL = 162.0, 322.0, 8
GROOVES = np.linspace(U0, U1, NPL + 1)[1:-1]


def belly_region_fn(p):
    y = p[:, 1] - BO[1]
    z = p[:, 2] - BO[2]
    rho = np.sqrt(y * y + z * z) + 1e-6
    th = np.degrees(np.arctan2(z, y)) % 360.0
    t = np.clip((th - U0) / (U1 - U0), 0.0, 1.0)
    w = 0.3 + 0.17 * np.sin(np.pi * np.clip(t * 1.25, 0.0, 1.0))
    deg = np.pi / 180.0 * rho
    d_range = np.maximum(U0 - th, th - U1) * deg
    d_groove = (1.7 - np.min(np.abs(th[:, None] - GROOVES[None, :]), axis=1)) * deg
    return np.maximum(np.maximum(np.abs(p[:, 0]) - w, d_range), d_groove)


belly_plates = shell_paint(trunk, SDF(belly_region_fn, (-0.5, -1.25, 0.45), (0.5, 0.85, 1.85)), out=0.022, inn=0.05)

THROAT = (0, -0.55, -0.83)


def neck_plates(nk, n_pl=9, t0=0.1, t1=0.9, gap=0.02):
    ts = np.linspace(t0, t1, n_pl + 1)
    info, L = along(nk["dense"], nk["rad"], (ts[:-1] + ts[1:]) / 2, THROAT)
    plen = (t1 - t0) * L / n_pl
    regs = []
    for c, tan, f, r in info:
        M = np.stack([np.cross(tan, f), tan, f], axis=1).astype(np.float32)
        regs.append(ellipsoid((r * 0.8, plen / 2 - gap, r * 0.75)).rotate(M).translate(c + f * r * 0.62))
    return shell_paint(nk["sdf"], fast_union(regs), out=0.02, inn=0.045)


m.add("Belly", union(belly_plates, *[neck_plates(nk) for nk in necks]), LILAC, role="detail", tris=5200, voxel=0.019)

# ============================================================ oro: corna, spine dorsali, artigli, mazza
gold = []
for hk in heads:
    gold += hk["gold"]
for nk in necks:  # spine lungo il dorso di ogni collo, piegate verso il corpo
    info, _ = along(nk["dense"], nk["rad"], np.linspace(0.2, 0.84, 5), THROAT)
    for j, (c, tan, f, r) in enumerate(info):
        Lb = 0.17 * nk["s"] * (1.1 - 0.35 * j / 4)
        gold.append(blade(Lb, 0.06 * nk["s"]).rotate(frame(-f - tan * 0.55, -tan)).translate(c - f * (r - 0.04)))
for y, L in [(-0.2, 0.3), (0.04, 0.34), (0.28, 0.34), (0.52, 0.31), (0.76, 0.27), (0.98, 0.23)]:
    p, nrm = project(trunk, (0, y, 1.2), (0, 0, 1))
    gold.append(blade(L, 0.11).rotate(frame(nrm + np.array([0, 0.5, 0]), (0, 1, 0))).translate(p - nrm * 0.045))
info, _ = along(TAIL_DENSE, tail_rad, np.linspace(0.08, 0.9, 9), (0, 0, -1))
for j, (c, tan, f, r) in enumerate(info):
    gold.append(blade(0.22 - 0.012 * j, 0.09 - 0.005 * j).rotate(frame(-f + tan * 0.5, tan)).translate(c - f * (r - 0.03)))
t_end = norm(TAIL_DENSE[-1] - TAIL_DENSE[-4])
ga = math.pi * (3 - math.sqrt(5))
for i in range(16):
    zf = 1 - 2 * (i + 0.5) / 16
    d = np.array([math.cos(ga * i) * math.sqrt(1 - zf * zf), math.sin(ga * i) * math.sqrt(1 - zf * zf), zf])
    if np.dot(d, -t_end) > 0.45:
        continue
    gold.append(round_cone(tuple(MACE_C + d * 0.1), tuple(MACE_C + d * 0.36), 0.062, 0.012))
gold.append(round_cone(tuple(MACE_C + t_end * 0.1), tuple(MACE_C + t_end * 0.46), 0.07, 0.012))
for tip, fwd, sz in TOES:
    t0 = np.asarray(tip, dtype=np.float64)
    gold.append(horn(t0 + (0, 0, 0.02), t0 + fwd * 0.08 * sz + (0, 0, 0.035 * sz), t0 + fwd * 0.15 * sz + (0, 0, 0.0),
                     t0 + fwd * 0.19 * sz + (0, 0, -0.052 * sz), 0.058 * sz, 0.012, n=8))

# nucleo di energia nel petto (incastonato in una montatura d'oro)
CORE_P, CORE_N = project(trunk, (0, -0.3, 1.6), (0, -1.0, 0.06))
CORE_M = frame(np.array([0, 0, 1.0]) - CORE_N * CORE_N[2], CORE_N)  # z verso l'alto sul petto, y = normale
CORE_C = CORE_P - CORE_N * 0.02
bezel = [CORE_C + CORE_M @ np.array(v, dtype=np.float32) for v in ((0.0, 0.0, 0.23), (0.15, 0.0, 0.0), (0.0, 0.0, -0.23),
                                                                   (-0.15, 0.0, 0.0), (0.0, 0.0, 0.23))]
gold.append(tube([tuple(v) for v in bezel], 0.032))
m.add("Horns", fast_union(gold), GOLD, role="detail", tris=9000, voxel=0.016)

# ============================================================ facce: bocche e occhi scuri, denti, lingue, occhi luminosi
m.add("Mouth", fast_union([d for hk in heads for d in hk["dark"]]), MOUTH, role="eye", tris=3000, voxel=0.012)
m.add("Teeth", fast_union([t for hk in heads for t in hk["teeth"]]), TOOTH, role="shine", tris=4500, voxel=0.01)
m.add("Tongue", union(*[hk["tongue"] for hk in heads if hk["tongue"] is not None]), TONGUE, role="detail", tris=700,
      voxel=0.012)
m.add("EyeGlow", fast_union([g for hk in heads for g in hk["glow"]]), EYE_GLOW, material="Neon", role="glow", tris=1400,
      voxel=0.011)

# ============================================================ ali enormi alzate (piano piatto XZ, poi inclinate)
WS = (0.42, 1.8)      # spalla (perno dell'animazione)
WE = (0.95, 2.62)     # gomito
WW = (1.36, 3.42)     # polso
WF = [(2.3, 3.82), (2.82, 3.0), (2.7, 2.02), (2.05, 1.3)]  # punte delle dita
WB = (0.62, 1.4)      # attacco posteriore sul fianco
WT = 0.03             # meta' spessore della membrana
PIVOT_Y = 0.18


def wing_dy(x, z):
    u = np.clip((x - WS[0]) / 2.4, 0.0, 1.0)
    return 0.24 * u + 0.07 * (z - WS[1]) + 0.12 * u * (1.0 - u)


def wing_warp(shape):
    """Porta una forma costruita sul piano piatto dell'ala (y=0) sull'ala inclinata all'indietro."""
    def f(p):
        q = p.copy()
        q[:, 1] = q[:, 1] - PIVOT_Y - wing_dy(q[:, 0], q[:, 2])
        return shape(q)

    lo, hi = shape.lo.copy(), shape.hi.copy()
    lo[1] += PIVOT_Y - 0.06
    hi[1] += PIVOT_Y + 0.5
    return SDF(f, lo, hi)


def scallop(a, b, toward, pull=0.36, n=8):
    a, b, c = (np.asarray(v, dtype=np.float64) for v in (a, b, toward))
    mid = (a + b) / 2
    ctrl = mid + (c - mid) * pull
    return [tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * ctrl + t * t * b) for t in np.linspace(0, 1, n + 2)[1:-1]], (a, ctrl, b)


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


def membrane(notches):
    flat = prism(WING_POLY, -WT, WT, round=WT * 0.9)
    return flat.subtract(union(*notches)) if notches else flat


def P3(xz, y=0.0):
    return (float(xz[0]), y, float(xz[1]))


arm = union(tube([P3(WS), P3(WE)], [0.1, 0.082]), tube([P3(WE), P3(WW)], [0.085, 0.066]),
            sphere(0.1, P3(WE)), sphere(0.09, P3(WW)), k=0.03)
fingers = []
for i, tip in enumerate(WF):
    a, b = np.array(WW, dtype=np.float64), np.array(tip, dtype=np.float64)
    dd = b - a
    perp = np.array([dd[1], -dd[0]]) / np.linalg.norm(dd)
    bow = 0.0 if i == 0 else 0.05
    pts = bezier(P3(a), P3(a + dd * 0.35 + perp * bow), P3(a + dd * 0.7 + perp * bow), P3(b), 8)
    fingers.append(tube(pts, taper(9, 0.064 - 0.005 * i, 0.022)))
wing_bones = union(arm, *fingers, k=0.03)

wing_claws = [horn(P3(WW, -0.02), (WW[0] - 0.02, -0.06, WW[1] + 0.12), (WW[0] - 0.08, -0.1, WW[1] + 0.22),
                   (WW[0] - 0.16, -0.12, WW[1] + 0.24), 0.052, 0.012, n=8)]
for tip in WF:
    dd = norm(np.array(tip) - np.array(WW))
    tp = np.array(tip)
    wing_claws.append(horn(P3(tp - dd * 0.03), P3(tp + dd * 0.05), P3(tp + dd * 0.1 + np.array([dd[1], -dd[0]]) * 0.03),
                           P3(tp + dd * 0.13 + np.array([dd[1], -dd[0]]) * 0.07), 0.034, 0.01, n=6))

NOTCH_R = [notch(EDGES[1], 0.42, 0.075, 0.2), notch(EDGES[3], 0.55, 0.05, 0.24), notch(EDGES[0], 0.7, 0.04, 0.12)]
NOTCH_L = [notch(EDGES[2], 0.5, 0.07, 0.19), notch(EDGES[1], 0.75, 0.04, 0.14)]

# toppa cucita (ala sinistra): rettangolo lilla su entrambe le facce, punti incrociati col filo d'oro
PC, PHW, PHH, PANG = (2.0, 3.36), 0.16, 0.12, 20.0
_ca, _sa = math.cos(math.radians(PANG)), math.sin(math.radians(PANG))
PATCH_RECT = [(PC[0] + x * _ca - y * _sa, PC[1] + x * _sa + y * _ca) for x, y in ((-PHW, -PHH), (PHW, -PHH), (PHW, PHH), (-PHW, PHH))]
stitches = []
_line = resample([np.array(v) for v in PATCH_RECT + [PATCH_RECT[0]]], 0.062)
for i in range(len(_line) - 1):
    tdir = norm(_line[i + 1] - _line[i])
    side = np.array([-tdir[1], tdir[0]]) * 0.036
    for zf in (WT + 0.012, -(WT + 0.012)):
        a, b = _line[i] - side, _line[i] + side
        stitches.append(capsule((a[0], a[1], zf), (b[0], b[1], zf), 0.011))

for sx, nm in ((1, "WingR"), (-1, "WingL")):
    piv = (sx * WS[0], PIVOT_Y, WS[1])
    flat = membrane(NOTCH_R if sx > 0 else NOTCH_L)
    mem = wing_warp(flat.rot(90, 0, 0))
    bones_w = wing_warp(wing_bones)
    claws_w = wing_warp(union(*wing_claws))
    if sx < 0:
        claws_w = union(claws_w, wing_warp(fast_union(stitches).rot(90, 0, 0)))
        patch = wing_warp(flat.offset(0.012).intersect(prism(PATCH_RECT, -1.0, 1.0)).rot(90, 0, 0))
    mir = (lambda q: q) if sx > 0 else (lambda q: q.mirrored())
    m.add(nm, mir(mem), PURPLE_DK, role="detail", tris=3500, voxel=0.024, group=nm, pivot=piv)
    m.add(nm + "Bone", mir(bones_w), PURPLE, role="skin", tris=2200, voxel=0.016, group=nm, pivot=piv)
    m.add(nm + "Claw", mir(claws_w), GOLD, role="detail", tris=700 if sx > 0 else 1300, voxel=0.012, group=nm, pivot=piv)
    if sx < 0:
        m.add("WingLPatch", mir(patch), LILAC, role="detail", tris=300, voxel=0.014, group=nm, pivot=piv)

# ============================================================ AURA (unica parte Neon "Aura")
aura = []
rng = np.random.default_rng(11)
RC, RR = 0.12, 1.55
ring = [(RR * math.cos(a), RC + RR * math.sin(a), 0.075 + 0.016 * math.sin(5 * a)) for a in np.linspace(0, 2 * math.pi, 73)]
aura += [round_cone(ring[i], ring[i + 1], 0.034, 0.034) for i in range(72)]
crack = []
for i in range(121):
    a = 2 * math.pi * i / 120
    off = (1 if i % 2 else -1) * rng.uniform(0.04, 0.085)
    crack.append(((RR + off) * math.cos(a), RC + (RR + off) * math.sin(a), 0.09 + rng.uniform(-0.03, 0.05)))
aura += [round_cone(crack[i], crack[i + 1], 0.019, 0.019) for i in range(120)]
for i in range(14):  # fiammate di energia che salgono dall'anello
    a = 2 * math.pi * (i + 0.5) / 14 + rng.uniform(-0.12, 0.12)
    out = np.array([math.cos(a), math.sin(a), 0.0])
    tang = np.array([-math.sin(a), math.cos(a), 0.0])
    base = np.array([RR * math.cos(a), RC + RR * math.sin(a), 0.07])
    H = rng.uniform(0.2, 0.46)
    mid = base + out * 0.03 + tang * rng.uniform(-0.05, 0.05) + (0, 0, H * 0.5)
    aura.append(tube([tuple(base), tuple(mid), tuple(base + out * 0.06 + (0, 0, H))], [0.042, 0.026, 0.008]))
SHARDS = [((1.38, -1.28, 0.95), 0.21, (20, 10, 30)), ((-1.42, -1.2, 0.72), 0.18, (-15, 20, -40)),
          ((2.1, -0.3, 0.6), 0.16, (10, -25, 60)), ((-2.05, -0.12, 1.08), 0.22, (25, 15, 10)),
          ((1.2, 2.08, 1.2), 0.17, (-20, 30, 0)), ((-1.55, 1.5, 0.62), 0.19, (15, -10, 45)),
          ((-0.62, -1.9, 0.44), 0.13, (0, 35, 15))]
for c, hh, (rx, ry, rz) in SHARDS:
    aura.append(diamond(hh, hh * 0.36, hh * 0.3).rot(rx, ry, rz).translate(c))
aura.append(diamond(0.2, 0.125, 0.07).rotate(CORE_M).translate(CORE_C))  # cristallo-nucleo nel petto
# cinque venature di energia dal nucleo alla base di ogni collo
for nk in necks:
    (c, tan, f, r), = along(nk["dense"], nk["rad"], [0.06], THROAT)[0]
    target = c + f * r
    pts = []
    for j, t in enumerate(np.linspace(0.0, 1.0, 11)):
        q = CORE_P * (1 - t) + target * t
        side = norm(np.cross(target - CORE_P, CORE_N))
        q = q + side * (0.035 if j % 2 else -0.035) * math.sin(math.pi * t) - CORE_N * 0.08
        pts.append(tuple(on_surface(core, q, lift=0.0, iters=5)))
    aura.append(tube(pts, taper(len(pts), 0.026, 0.012)))
m.add("Aura", fast_union(aura), AURA, material="Neon", role="glow", tris=5500, voxel=0.015)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
