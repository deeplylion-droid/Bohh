"""Gallina Galattica - pet Segreto (creatura meme originale).

Una gallina giocattolo venuta dallo spazio: corpo indaco-viola punteggiato di stelline luminose,
cresta e bargigli rosa nebulosa, becco e zampe d'oro, un anello come quello di Saturno (ciano
luminoso) inclinato attorno al corpo e una coda-nebulosa. Carattere: la brontolona cosmica -
palpebre pesanti, sopracciglia aggrottate, pupille piccole e luminose, becco col morso inverso
pieno di dentini (le galline coi denti esistono solo nello spazio) e una cucitura sulla pancia.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, capsule, ellipsoid, project, round_cone, sphere, tube, union)  # noqa: E402
from lib.toy import Model  # noqa: E402

INDIGO = (62, 34, 138)
BELLY = (122, 84, 206)
STAR = (255, 226, 110)
PINK = (255, 64, 176)
GOLD = (255, 186, 26)
TOOTH = (255, 252, 242)
RING = (60, 230, 255)
WING = (44, 26, 112)
NEBULA = (168, 40, 190)
EYE = (20, 12, 30)
PUPIL = (110, 245, 255)
MOUTH = (30, 10, 34)
WHITE = (255, 255, 255)

m = Model("GallinaGalattica", "pet")


# ---------------------------------------------------------------- helper locali
def normal_at(base, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float32)
    g = np.array([base((p + e)[None, :])[0] - base((p - e)[None, :])[0]
                  for e in np.eye(3, dtype=np.float32) * eps])
    return g / max(np.linalg.norm(g), 1e-9)


def on_surf(base, src, q):
    src = np.asarray(src, dtype=np.float64)
    return project(base, src, np.asarray(q, dtype=np.float64) - src)


def spheres(centers, radii):
    """Unione veloce di tante sfere (vicini piu' prossimi)."""
    C = np.asarray(centers, dtype=np.float32)
    R = np.asarray(radii, dtype=np.float32)
    tree = cKDTree(C)
    k = min(4, len(C))

    def f(p):
        d, i = tree.query(p, k=k)
        return np.min(d - R[i], axis=1).astype(np.float32)
    return SDF(f, C.min(0) - R.max(), C.max(0) + R.max())


def stitches(base, pts, n, dash, r, across=True, lift=0.006):
    pts = np.asarray(pts, dtype=np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for t in np.linspace(0.0, s[-1], n):
        i = min(np.searchsorted(s, t, side="right") - 1, len(seg) - 1)
        w = (t - s[i]) / max(seg[i], 1e-9)
        p = pts[i] * (1 - w) + pts[i + 1] * w
        tan = (pts[i + 1] - pts[i]) / max(seg[i], 1e-9)
        nrm = normal_at(base, p)
        d = np.cross(nrm, tan) if across else tan - nrm * float(tan @ nrm)
        d /= np.linalg.norm(d)
        c = p + nrm * lift
        out.append(capsule(c - d * dash * 0.5, c + d * dash * 0.5, r))
    return union(*out)


# ---------------------------------------------------------------- corpo
HEAD_C = (0.0, -0.32, 2.04)
BODY_C = (0.0, 0.1, 1.08)
body = ellipsoid((0.84, 0.92, 0.8), BODY_C).rot(-8, 0, 0, pivot=BODY_C)
head = ellipsoid((0.64, 0.6, 0.6), HEAD_C)
core = union(body, head, k=0.36)
m.add("Body", core, INDIGO, tris=4300)

belly_region = ellipsoid((0.56, 0.6, 0.6), (0.0, -0.66, 1.0))
m.add("Belly", core.offset(0.02).intersect(belly_region), BELLY, role="detail", tris=800)

# stelline luminose sparse sul piumaggio (non sulla pancia)
rng = np.random.default_rng(8)
st_c, st_r = [], []
for _ in range(400):
    v = rng.normal(size=3)
    v /= np.linalg.norm(v)
    src = HEAD_C if v[2] > 0.55 and rng.random() < 0.5 else BODY_C
    p, n = project(core, src, v)
    pp = p[None, :].astype(np.float32)
    if belly_region(pp)[0] < 0.06:
        continue
    if p[1] < -0.55 and p[2] > 1.7:
        continue  # niente stelle sul viso
    if p[2] < 0.42:
        continue
    if any(np.linalg.norm(p - q) < 0.13 for q in st_c):
        continue
    st_c.append(p + n * 0.008)
    st_r.append(rng.uniform(0.022, 0.03))
    if len(st_c) >= 60:
        break
# alcune stelline a quattro punte (scintille) nei punti piu' visibili
twinkles = []
for src, d, L in ((HEAD_C, (0.75, -0.2, 0.75), 0.14), (BODY_C, (0.9, -0.45, 0.55), 0.15), (BODY_C, (0.8, 0.3, 0.75), 0.13),
                  (HEAD_C, (-0.75, -0.1, 0.65), 0.13), (BODY_C, (-0.9, -0.4, 0.35), 0.14), (BODY_C, (0.55, 0.85, 0.2), 0.13)):
    c, n = project(core, src, d)
    c = c + n * 0.01
    t1 = np.cross(n, (0.0, 0.0, 1.0))
    t1 /= np.linalg.norm(t1)
    t2 = np.cross(n, t1)
    for dd in (t1, -t1, t2, -t2):
        twinkles.append(round_cone(tuple(c), tuple(c + dd * L), 0.034, 0.004))
    twinkles.append(sphere(0.045, c))
m.add("Stars", union(spheres(st_c, st_r), *twinkles), STAR, material="Neon", role="glow", tris=1200, voxel=0.009)

# ---------------------------------------------------------------- testa: occhi brontoloni, becco col morso inverso
EYE_R = (0.15, 0.09, 0.19)
eye_frames = [Frame(core, HEAD_C, (0.42 * sx, -1.0, 0.2), sink=0.045) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(ellipsoid(EYE_R)) for f in eye_frames]), EYE, role="eye", tris=500, voxel=0.012)
pupils, shines, lids = [], [], []
for f, sx in zip(eye_frames, (1, -1)):
    px, pz = 0.02 * sx, -0.05
    py = -EYE_R[1] * math.sqrt(max(1 - (px / EYE_R[0]) ** 2 - (pz / EYE_R[2]) ** 2, 0.0))
    pupils.append(f.place(ellipsoid((0.045, 0.03, 0.055)), (px, py + 0.016, pz)))
    shines.append(f.place(sphere(0.026), (-0.06, -0.075, -0.035)))
    slope = 0.3  # piu' basso verso il becco: aria scocciata

    def cut(p, sx=sx, slope=slope):
        return (0.05 - slope * sx * p[:, 0] - p[:, 2]) / math.sqrt(1 + slope * slope)
    lid_shell = ellipsoid((EYE_R[0] + 0.028, EYE_R[1] + 0.028, EYE_R[2] + 0.028))
    lids.append(f.place(lid_shell.intersect(SDF(cut, lid_shell.lo, lid_shell.hi))))
m.add("Pupils", union(*pupils), PUPIL, material="Neon", role="glow", tris=300, voxel=0.008)
m.add("Shine", union(*shines), WHITE, role="shine", tris=200, voxel=0.008)
m.add("Lids", union(*lids), INDIGO, role="skin", tris=500, voxel=0.011)

beak_f = Frame(core, HEAD_C, (0.0, -1.0, -0.12), sink=0.06)
upper = round_cone((0.0, 0.02, 0.03), (0.0, -0.25, -0.05), 0.13, 0.035)
lower = round_cone((0.0, 0.0, -0.1), (0.0, -0.29, -0.1), 0.105, 0.05)  # mandibola sporgente
beak = union(upper, lower, k=0.03)
teeth = []
for tx, h in ((-0.06, 0.07), (0.0, 0.085), (0.06, 0.07)):
    base_t = beak_f.point((tx, -0.27 + abs(tx) * 0.6, -0.06))
    tip_t = beak_f.point((tx * 1.05, -0.28 + abs(tx) * 0.6, -0.06 + h))
    teeth.append(round_cone(base_t, tip_t, 0.024, 0.006))
for tx in (-0.11, 0.11):
    teeth.append(round_cone(beak_f.point((tx, -0.2, -0.07)), beak_f.point((tx * 1.05, -0.21, -0.015)), 0.02, 0.005))
m.add("Teeth", union(*teeth), TOOTH, role="detail", tris=300, voxel=0.008)

# broncio: angoli della bocca all'ingiu' ai lati del becco
frown = []
for sx in (1, -1):
    pts = [on_surf(core, HEAD_C, beak_f.point((sx * x, -0.3, z)))[0] for x, z in ((0.12, -0.1), (0.19, -0.13), (0.24, -0.2))]
    frown.append(tube(pts, [0.022, 0.02, 0.016]))
m.add("Mouth", union(*frown), MOUTH, role="detail", tris=300, voxel=0.009)

# zampe d'oro un po' lunghe con dita tozze, e becco
legs = []
for sx in (1, -1):
    hip = (sx * 0.32, -0.02, 0.5)
    ankle = (sx * 0.34, -0.12, 0.12)
    legs += [capsule(hip, ankle, 0.075)]
    for dx, dy in ((-0.14, -0.2), (0.0, -0.24), (0.14, -0.2), (0.0, 0.14)):
        legs.append(capsule(ankle, (ankle[0] + dx, ankle[1] + dy, 0.06), 0.06))
m.add("Gold", union(beak_f.place(beak), union(*legs, k=0.05)), GOLD, role="detail", tris=1100, voxel=0.013,
      reflectance=0.15)

# cresta a tre lobi, bargigli, sopracciglia aggrottate e cucitura: tutto rosa nebulosa
lobes = []
for y, h, r in ((-0.5, 0.13, 0.13), (-0.27, 0.2, 0.16), (-0.03, 0.2, 0.16), (0.2, 0.12, 0.13)):
    base_c = on_surf(core, HEAD_C, (0.0, y, 3.0))[0]
    lobes.append(ellipsoid((0.085, r * 0.9, r), base_c + np.array([0.0, 0.0, h])))
    lobes.append(capsule(tuple(base_c - np.array([0, 0, 0.05])), tuple(base_c + np.array([0.0, 0.0, h])), 0.08))
comb = union(*lobes, k=0.03)
wattle = union(*[ellipsoid((0.07, 0.06, 0.12), beak_f.point((sx * 0.06, -0.12, -0.27))) for sx in (1, -1)], k=0.04)
brows = []
for f, sx in zip(eye_frames, (1, -1)):
    pts = [on_surf(core, HEAD_C, f.point((sx * xi, -0.3, z)))[0] for xi, z in ((-0.17, 0.27), (-0.06, 0.25), (0.05, 0.22), (0.15, 0.16))]
    brows.append(tube(pts, [0.04, 0.055, 0.055, 0.045]))
seam = [on_surf(core, BODY_C, (0.0, -1.5, z))[0] for z in np.linspace(1.5, 0.6, 9)]
m.add("Comb", union(comb, wattle, *brows, stitches(core, seam, 7, 0.14, 0.02)), PINK, role="detail", tris=1300,
      voxel=0.011)

# ---------------------------------------------------------------- ali (animabili) e coda-nebulosa
wing_r = ellipsoid((0.15, 0.5, 0.36), (0, 0, 0)).rot(0, -18, 0).rot(10, 0, 0).translate((0.86, 0.12, 1.12))
m.add("WingR", wing_r, WING, role="detail", tris=800, group="WingR", pivot=(0.74, 0.0, 1.4))
m.add("WingL", wing_r.mirrored(), WING, role="detail", tris=800, group="WingL", pivot=(-0.74, 0.0, 1.4))
feathers = []
for ang, L in ((-34, 0.72), (-12, 0.86), (12, 0.86), (34, 0.72)):
    a = math.radians(ang)
    base_f = np.array([0.0, 0.82, 1.28])
    tip = base_f + np.array([math.sin(a) * 0.55, 0.38, 0.0]) + np.array([0, 0, L * 0.9])
    feathers.append(round_cone(tuple(base_f), tuple(tip), 0.14, 0.09))
m.add("Tail", union(*feathers, k=0.06), NEBULA, role="detail", tris=900)


# ---------------------------------------------------------------- anello di Saturno (ciano luminoso) inclinato
def ring_fn(p, R=1.42, a=0.16, b=0.052):
    rho = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2)
    return (np.sqrt(((rho - R) / a) ** 2 + (p[:, 2] / b) ** 2) - 1.0) * b


ring = SDF(ring_fn, (-1.62, -1.62, -0.06), (1.62, 1.62, 0.06)).rot(16, -12, 0).translate((0.0, 0.08, 1.22))
m.add("Ring", ring, RING, material="Neon", role="glow", tris=1600, voxel=0.013)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
