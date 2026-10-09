"""Drago di Lava (Lava Dragon) - pet Leggendario. Carattere: feroce sbruffone (ghigno pieno di denti, ala ricucita)."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, box, capsule, ellipsoid, prism, project, round_cone, smin,  # noqa: E402
                     sphere, tube, union)
from lib.toy import Model  # noqa: E402


# ============================================================ helper "toy horror" (lib/ non si modifica: copiati qui)
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


def curve_on(sdf, pts, direction=(0, -1, 0), lift=0.0):
    """Proietta punti (interni alla forma) sulla superficie lungo 'direction'."""
    d = norm(direction)
    out = []
    for q in pts:
        p, n = project(sdf, np.asarray(q, float), d)
        out.append(np.asarray(p, float) + np.asarray(n, float) * lift)
    return out


def grin_sdf(cx, cz, w, depth, curve, tilt=0.0, y_max=-0.2, power=0.75):
    """Bocca a mezzaluna nel piano XZ (estrusa lungo Y, solo per y < y_max)."""
    def f(p):
        x = (p[:, 0] - cx) / w
        up = cz + curve * x * x + tilt * x
        lo = up - depth * np.clip(1.0 - x * x, 0.0, None) ** power
        d = np.maximum(np.maximum(p[:, 2] - up, lo - p[:, 2]), (np.abs(x) - 1.0) * w)
        return np.maximum(d, p[:, 1] - y_max)

    pad = abs(curve) + abs(tilt) + depth + 0.05
    return SDF(f, (cx - w, -6.0, cz - pad), (cx + w, y_max, cz + pad))


def grin_teeth(surf, y_in, cx, cz, w, depth, curve, tilt=0.0, n=8, length=0.08, r=0.03, lower=0,
               power=0.75, span=0.84, lift=0.006):
    """Dentini aguzzi bianchi lungo il bordo superiore (e inferiore) della bocca."""
    def tooth(x, upper):
        up = cz + curve * x * x + tilt * x
        open_h = depth * max(1.0 - x * x, 0.0) ** power
        z_edge = up if upper else up - open_h
        s = -1.0 if upper else 1.0
        L = min(length, 0.55 * open_h)
        X = cx + x * w
        base, tip = curve_on(surf, [(X, y_in, z_edge - s * 0.012), (X, y_in, z_edge + s * L)], lift=lift)
        return round_cone(tuple(base), tuple(tip), r * min(1.0, 0.45 + open_h / depth), 0.004)

    teeth = [tooth(-span + 2 * span * (i + 0.5) / n, True) for i in range(n)]
    teeth += [tooth(-span * 0.75 + 1.5 * span * (i + 0.5) / lower, False) for i in range(lower)]
    return teeth


def brow(surf, y_in, pts_xz, r=0.045, lift=0.0):
    """Sopracciglio spesso e affusolato (punti dal lato interno a quello esterno, nel piano XZ)."""
    pts = curve_on(surf, [(x, y_in, z) for x, z in pts_xz], lift=lift)
    pts = resample(pts, 0.04)
    n = len(pts)
    radii = [r * (0.72 + 0.28 * math.sin(math.pi * min(i / (n - 1) * 1.6, 1.0))) * (1.0 - 0.45 * (i / (n - 1)) ** 2)
             for i in range(n)]
    return tube([tuple(p) for p in pts], radii)


def lid_parts(frame, a, b, c, cut, slope=0.0, t=0.02, lash_r=0.02):
    """Palpebra superiore pesante (colore pelle) e linea scura del bordo (coordinate locali dell'occhio)."""
    A, B, C = a + t, b + t, c + t
    plane = SDF(lambda p: (cut + slope * p[:, 0] - p[:, 2]) / math.sqrt(1 + slope * slope), (-A, -B, -C), (A, B, C))
    lid = ellipsoid((A, B, C)).intersect(plane)
    pts = []
    for x in np.linspace(-A * 0.98, A * 0.98, 15):
        z = cut + slope * x
        q = 1 - (x / A) ** 2 - (z / C) ** 2
        if q > 0.01:
            pts.append((x, -B * math.sqrt(q), z))
    return frame.place(lid), frame.place(tube(pts, lash_r))


# ============================================================ colori
RED = (204, 34, 32)
RED_DARK = (108, 14, 26)
GOLD = (255, 180, 38)
BONE = (250, 230, 188)
MEMBRANE = (255, 110, 30)
PATCH = (100, 40, 150)
LAVA = (255, 96, 12)
FLAME_IN = (255, 212, 58)
EYE = (30, 12, 22)
WHITE = (255, 255, 255)

m = Model("LavaDragon", "pet")

HEAD_C = (0, -0.12, 2.12)
body = ellipsoid((0.95, 0.88, 0.98), (0, 0.06, 1.02))
head = ellipsoid((0.98, 0.86, 0.84), HEAD_C)
SN_C = (0, -0.86, 1.84)
snout = ellipsoid((0.56, 0.58, 0.38), SN_C)
# braccia piu' lunghe con manone artigliate, zampe tozze
SHOULDER = [(sx * 0.7, -0.28, 1.3) for sx in (1, -1)]
HAND = [(sx * 0.92, -0.7, 0.86) for sx in (1, -1)]
arms = union(*[round_cone(s, h, 0.21, 0.17) for s, h in zip(SHOULDER, HAND)],
             *[sphere(0.2, (h[0], h[1] - 0.02, h[2] - 0.04)) for h in HAND])
legs = union(*[ellipsoid((0.34, 0.42, 0.26), (sx * 0.5, -0.32, 0.26)) for sx in (1, -1)])
tail = tube(bezier((0, 0.7, 0.62), (0.2, 1.4, 0.45), (0.9, 1.55, 0.55), (1.2, 1.2, 0.95), 14),
            [0.42 - 0.025 * i for i in range(15)])
core = union(body, head, k=0.42)
core = union(core, snout, k=0.25)
core = union(core, arms, legs, tail, k=0.16)
nostrils = union(sphere(0.06, (0.15, -1.32, 2.05)), sphere(0.06, (-0.15, -1.32, 2.05)))
core = core.subtract(nostrils, k=0.04)
m.add("Body", core, RED, tris=4800)

# pancia a placche dorate
belly_region = ellipsoid((0.66, 0.8, 0.72), (0, -0.6, 0.98))
grooves = union(*[box((1.0, 1.0, 0.025), (0, -0.8, z)) for z in (0.62, 0.92, 1.22)])
m.add("Belly", core.offset(0.02).intersect(belly_region).subtract(grooves), GOLD, role="detail", tris=1300)

# macchie di lava luminose su schiena e testa
lava_spots = union(
    ellipsoid((0.32, 0.3, 0.2), (0.45, 0.55, 1.5)), ellipsoid((0.26, 0.24, 0.18), (-0.5, 0.6, 1.2)),
    ellipsoid((0.22, 0.2, 0.16), (0.05, 0.78, 0.9)), ellipsoid((0.25, 0.22, 0.2), (-0.35, 0.35, 2.75)),
    ellipsoid((0.2, 0.2, 0.16), (0.55, 0.1, 2.65)), ellipsoid((0.2, 0.2, 0.2), (0.7, 1.45, 0.75)),
    ellipsoid((0.18, 0.22, 0.14), (0.86, -0.3, 1.5)), ellipsoid((0.15, 0.2, 0.12), (-0.86, -0.3, 1.46)),
)
m.add("Lava", core.offset(0.018).intersect(lava_spots), LAVA, material="Neon", role="glow", tris=900)

# corna, artigli dei piedi e delle mani (osso)
horns = union(*[tube(bezier((sx * 0.42, 0.0, 2.72), (sx * 0.5, 0.25, 3.08), (sx * 0.62, 0.55, 3.22), (sx * 0.78, 0.72, 3.18), 10),
                     [0.16 - 0.013 * i for i in range(11)]) for sx in (1, -1)])
claws = []
for sx in (1, -1):
    for dx in (-0.14, 0.0, 0.14):
        claws.append(round_cone((sx * 0.5 + dx, -0.66, 0.2), (sx * 0.5 + dx * 1.15, -0.84, 0.1), 0.075, 0.025))
for h in HAND:
    hx, hy, hz = h
    for dx, dz in ((-0.1, 0.02), (0.0, -0.06), (0.1, 0.02)):
        a = (hx + dx * (1 if hx > 0 else -1), hy - 0.14, hz - 0.06 + dz)
        claws.append(round_cone(a, (a[0] * 1.03, a[1] - 0.2, a[2] - 0.1), 0.065, 0.02))
m.add("Horns", union(horns, *claws), BONE, role="detail", tris=1100, voxel=0.018)

# creste dorsali luminose
spikes = []
for i, (y, z) in enumerate([(0.55, 2.62), (0.88, 2.15), (0.98, 1.65), (0.95, 1.15), (1.02, 0.72)]):
    r = 0.2 - 0.02 * i
    spikes.append(round_cone((0, y - 0.05, z - 0.05), (0, y + 0.22, z + 0.12), r, 0.04))
m.add("Spikes", union(*spikes, k=0.02), LAVA, material="Neon", role="glow", tris=800)

# ali: membrana + ossa; quella destra ha uno strappo ricucito, quella sinistra una toppa viola
wing_poly = [(0.0, 0.0), (0.7, 0.36), (1.38, 0.84), (1.55, 0.4), (1.3, 0.08), (1.28, -0.3), (0.94, -0.22),
             (0.8, -0.56), (0.48, -0.36), (0.24, -0.5)]
membrane = prism(wing_poly, -0.035, 0.035, round=0.03)
bones = union(tube([(0, 0, 0), (0.7, 0.36, 0), (1.38, 0.84, 0)], [0.08, 0.065, 0.045]),
              tube([(0.7, 0.36, 0), (1.3, 0.08, 0)], [0.055, 0.035]),
              tube([(0.7, 0.36, 0), (0.8, -0.56, 0)], [0.055, 0.035]))


def wing_stitches(a, b, n=6, side=0.065, r=0.016):
    """Strappo ricucito sulla membrana: taglio scuro + punti trasversali su entrambe le facce."""
    a, b = np.array(a, float), np.array(b, float)
    t = (b - a) / np.linalg.norm(b - a)
    s = np.array([-t[1], t[0]])
    out = []
    for zf in (0.04, -0.04):
        out.append(capsule((a[0], a[1], zf * 0.9), (b[0], b[1], zf * 0.9), 0.012))
        for i in range(n):
            c = a + (b - a) * (i + 0.5) / n
            out.append(capsule((c[0] - s[0] * side, c[1] - s[1] * side, zf), (c[0] + s[0] * side, c[1] + s[1] * side, zf), r))
    return out


def patch_parts(c, hw, hh, ang, r=0.015):
    """Toppa (rettangolo sulla membrana, entrambe le facce) + cucitura a trattini sul bordo."""
    region = box((hw, hh, 0.2), (0, 0, 0), round=0.03).rot(0, 0, ang).translate((c[0], c[1], 0))
    pts = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh), (-hw, -hh)]
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    pts = [(c[0] + x * ca - y * sa, c[1] + x * sa + y * ca) for x, y in pts]
    dashes = []
    for zf in (0.045, -0.045):
        line = resample([(x, y, zf) for x, y in pts], 0.025)
        for i in range(0, len(line) - 2, 4):
            dashes.append(capsule(tuple(line[i]), tuple(line[i + 2]), r))
    return membrane.offset(0.012).intersect(region), dashes


def place_wing(shape, sx):
    s = shape.rot(90, 0, 0).rot(0, 0, 38).rot(0, -24, 0).translate((0.42, 0.58, 1.86))
    return s if sx > 0 else s.mirrored()


tear = wing_stitches((1.02, 0.5), (1.24, 0.13))
patch, patch_dashes = patch_parts((0.98, 0.2), 0.17, 0.14, 24)
for sx, nm in ((1, "WingR"), (-1, "WingL")):
    piv = (sx * 0.42, 0.58, 1.86)
    m.add(nm, place_wing(membrane, sx), MEMBRANE, role="detail", tris=800, voxel=0.018, group=nm, pivot=piv)
    extra = tear if sx > 0 else patch_dashes
    m.add(nm + "Bone", place_wing(union(bones, fast_union(extra)), sx), RED_DARK, role="detail", tris=700, voxel=0.012,
          group=nm, pivot=piv)
m.add("WingLPatch", place_wing(patch, -1), PATCH, role="detail", tris=200, voxel=0.012, group="WingL", pivot=(-0.42, 0.58, 1.86))

# fiamma sulla punta della coda
tip = (1.25, 1.12, 1.05)
flame_out = union(sphere(0.3, tip), round_cone(tip, (1.42, 1.0, 1.75), 0.3, 0.04), k=0.1)
flame_in = union(sphere(0.18, (tip[0] - 0.04, tip[1] - 0.1, tip[2] + 0.02)),
                 round_cone((tip[0] - 0.04, tip[1] - 0.1, tip[2] + 0.02), (1.32, 0.98, 1.5), 0.18, 0.03), k=0.08)
m.add("Flame", flame_out, LAVA, material="Neon", role="glow", tris=700)
m.add("FlameCore", flame_in, FLAME_IN, material="Neon", role="glow", tris=400)

# ------------------------------------------------------------------ faccia feroce
EA, EB, EC = 0.2, 0.1, 0.26
frames = [Frame(head, HEAD_C, (0.4 * sx, -1.0, 0.24), sink=0.05) for sx in (1, -1)]
eyes, lids, lashes, shines = [], [], [], []
for f, sx in zip(frames, (1, -1)):
    eyes.append(f.place(ellipsoid((EA, EB, EC))))
    lid, lash = lid_parts(f, EA, EB, EC, cut=0.08, slope=-sx * 0.3)
    lids.append(lid)
    lashes.append(lash)
    shines.append(f.place(sphere(0.045), (-0.06, -0.088, -0.02)))
    shines.append(f.place(sphere(0.021), (0.07, -0.08, -0.12)))
m.add("Lids", union(*lids), RED, role="skin", tris=500, voxel=0.012)
brows = [brow(head, HEAD_C[1], [(sx * 0.1, 2.56), (sx * 0.25, 2.63), (sx * 0.42, 2.71), (sx * 0.56, 2.75)], r=0.058)
         for sx in (1, -1)]

# ghigno largo pieno di denti aguzzi sul muso
MOUTH = dict(cx=0.0, cz=1.72, w=0.44, depth=0.17, curve=0.13, tilt=0.03)
mouth_surf = core.offset(0.018)
mouth = mouth_surf.intersect(grin_sdf(**MOUTH, y_max=-0.9))
teeth = grin_teeth(mouth_surf, SN_C[1], **MOUTH, n=10, length=0.085, r=0.032, lower=7)
m.add("Eyes", union(*eyes, *lashes, *brows, mouth), EYE, role="eye", tris=1200, voxel=0.011)
m.add("Shine", union(*shines, *teeth), WHITE, role="shine", tris=700, voxel=0.009)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
