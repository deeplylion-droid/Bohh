"""Tortellone Cosmico - pet Segreto volante (creatura meme originale).

Un grosso tortellone giocattolo di pasta viola cosmica: un anello ripieno e paffuto con il buchino
al centro, il bordo pizzicato e smerlato tutto attorno, le due punte schiacciate in basso, stelline
luminose, alette di pasta e una piccola luna luminosa in orbita. Carattere: lo svitato - occhi
spaiati (uno enorme con la pupilla minuscola, uno piccolo e strizzato), sopracciglia storte e un
ghigno largo col labbro smerlato pieno di dentini; una toppa ricucita sul fianco.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capsule, ellipsoid, prism, project, round_cone, sphere, tube, union)  # noqa: E402
from lib.toy import Model  # noqa: E402

DOUGH = (116, 48, 200)
CRIMP = (176, 122, 255)
STAR = (255, 226, 110)
WING = (196, 156, 255)
MOON = (255, 224, 110)
CRATER = (214, 168, 70)
ORBIT = (140, 210, 255)
EYE_WHITE = (255, 253, 246)
PUPIL = (24, 14, 30)
MOUTH = (38, 10, 48)
TOOTH = (255, 252, 242)
PATCH = (70, 214, 200)
THREAD = (40, 14, 60)
WHITE = (255, 255, 255)

m = Model("TortelloneCosmico", "pet")


# ---------------------------------------------------------------- helper locali
def seg2(x, z, a, b, r):
    px, pz = x - a[0], z - a[1]
    ex, ez = b[0] - a[0], b[1] - a[1]
    t = np.clip((px * ex + pz * ez) / (ex * ex + ez * ez + 1e-12), 0.0, 1.0)
    dx, dz = px - ex * t, pz - ez * t
    return np.sqrt(dx * dx + dz * dz) - r


def stencil(fn2d, xr, zr, depth=0.35):
    """Estrude una forma 2D fn2d(x, z) lungo l'asse locale Y (decalcomania da Frame.place)."""
    def f(p):
        return np.maximum(fn2d(p[:, 0], p[:, 2]), np.abs(p[:, 1]) - depth)
    return SDF(f, (xr[0], -depth, zr[0]), (xr[1], depth, zr[1]))


def normal_at(base, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float32)
    g = np.array([base((p + e)[None, :])[0] - base((p - e)[None, :])[0]
                  for e in np.eye(3, dtype=np.float32) * eps])
    return g / max(np.linalg.norm(g), 1e-9)


def on_surf(base, src, q):
    src = np.asarray(src, dtype=np.float64)
    return project(base, src, np.asarray(q, dtype=np.float64) - src)


def spheres(centers, radii):
    C = np.asarray(centers, dtype=np.float32)
    R = np.asarray(radii, dtype=np.float32)
    tree = cKDTree(C)
    k = min(4, len(C))

    def f(p):
        d, i = tree.query(p, k=k)
        return np.min(d - R[i], axis=1).astype(np.float32)
    return SDF(f, C.min(0) - R.max(), C.max(0) + R.max())


def stitches(base, pts, n, dash, r, across=True, lift=0.006, closed=False):
    pts = np.asarray(pts, dtype=np.float64)
    if closed:
        pts = np.vstack([pts, pts[:1]])
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for t in np.linspace(0.0, s[-1], n, endpoint=not closed):
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


# ---------------------------------------------------------------- anello ripieno (piano XZ, guarda verso -Y)
ZC = 1.42
RR = 0.7


def tube_r(phi):
    """Raggio del 'ripieno': paffuto in alto (dove c'e' la faccia), piu' sottile in basso."""
    return 0.5 + 0.08 * np.cos(phi)


def ring_fn(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2] - ZC
    rho = np.sqrt(x * x + z * z)
    phi = np.arctan2(x, z)  # 0 in alto
    return np.sqrt((rho - RR) ** 2 + (y * 1.08) ** 2) - tube_r(phi)


ring = SDF(ring_fn, (-1.35, -0.62, ZC - 1.35), (1.35, 0.62, ZC + 1.35))
# le due punte schiacciate e sovrapposte in basso
FL_Z = ZC - RR - 0.3
flaps = union(ellipsoid((0.32, 0.1, 0.17), (0.1, -0.4, FL_Z)).rot(0, -32, 0, pivot=(0.1, -0.4, FL_Z)),
              ellipsoid((0.32, 0.1, 0.17), (-0.1, -0.27, FL_Z - 0.02)).rot(0, 32, 0, pivot=(-0.1, -0.27, FL_Z - 0.02)), k=0.03)
body = union(ring, flaps, k=0.08)
m.add("Body", body, DOUGH, tris=4800)

# bordo pizzicato e smerlato tutto attorno (pinna sottile nel piano dell'anello)
N_SCALLOP = 22


def crimp_fn(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2] - ZC
    rho = np.sqrt(x * x + z * z)
    phi = np.arctan2(x, z)
    r_in = RR + tube_r(phi) * 0.55
    r_out = RR + tube_r(phi) + 0.16 + 0.045 * np.cos(N_SCALLOP * phi)
    thick = 0.05 + 0.008 * np.cos(N_SCALLOP * phi)  # creste del pizzicotto
    d_rad = np.maximum(r_in - rho, rho - r_out)
    return np.maximum(d_rad, np.abs(y) - thick) - 0.012


crimp = SDF(crimp_fn, (-1.55, -0.1, ZC - 1.55), (1.55, 0.1, ZC + 1.55))
# la punta del triangolo di pasta ripiegata all'insu' (la "cresta" tipica del tortellino), bordo smerlato
outline = []
for (x0, y0), (x1, y1) in (((-0.36, 0.0), (0.0, 0.62)), ((0.0, 0.62), (0.36, 0.0))):
    ex, ey = x1 - x0, y1 - y0
    L = math.hypot(ex, ey)
    nx, ny = ey / L, -ex / L
    if x0 < 0:
        nx, ny = -nx, -ny
    for i in range(22):
        t = i / 22
        w = 0.025 * math.sin(t * 7 * 2 * math.pi) * min(1.0, 4 * t, 4 * (1 - t))
        outline.append((x0 + ex * t + nx * w, y0 + ey * t + ny * w))
outline.append((0.36, 0.0))
outline.append((0.36, -0.25))
outline.append((-0.36, -0.25))
PEAK_Z = ZC + RR + tube_r(0.0) - 0.05
peak = prism(outline, -0.05, 0.05, round=0.03).rot(90, 0, 0).rot(-24, 0, 0).translate((0.0, 0.16, PEAK_Z))
crimp = union(crimp, peak, k=0.05)
m.add("Crimp", crimp, CRIMP, role="detail", tris=3200, voxel=0.013)

# ---------------------------------------------------------------- stelline luminose (puntini + scintille a 4 punte)
rng = np.random.default_rng(13)
st_c, st_r = [], []
FACE_ZONE = (0.0, -0.5, ZC + 0.62)
for _ in range(500):
    phi = rng.uniform(-math.pi, math.pi)
    psi = rng.uniform(-math.pi, math.pi)
    c_t = np.array([RR * math.sin(phi), 0.0, ZC + RR * math.cos(phi)])
    d = np.array([math.sin(phi) * math.cos(psi), math.sin(psi), math.cos(phi) * math.cos(psi)])
    p, n = project(body, c_t, d)
    if np.linalg.norm(p - np.array(FACE_ZONE)) < 0.62 or abs(p[1]) < 0.12:
        continue
    if any(np.linalg.norm(p - q) < 0.15 for q in st_c):
        continue
    st_c.append(p + n * 0.006)
    st_r.append(rng.uniform(0.022, 0.03))
    if len(st_c) >= 18:
        break
twinkles = []
for phi, psi, L in ((-1.2, -0.7, 0.14), (1.25, -0.6, 0.15), (2.3, -0.8, 0.13), (-2.4, -0.75, 0.13), (0.6, 0.9, 0.13),
                    (-0.7, 0.9, 0.13), (3.0, 0.8, 0.12), (-1.7, -1.0, 0.12), (2.75, -0.7, 0.12), (-2.9, -0.6, 0.12)):
    c_t = np.array([RR * math.sin(phi), 0.0, ZC + RR * math.cos(phi)])
    d = np.array([math.sin(phi) * math.cos(psi), math.sin(psi), math.cos(phi) * math.cos(psi)])
    c, n = project(body, c_t, d)
    c = c + n * 0.01
    t1 = np.cross(n, (0.0, 1.0, 0.0)) if abs(n[1]) < 0.9 else np.cross(n, (1.0, 0.0, 0.0))
    t1 /= np.linalg.norm(t1)
    t2 = np.cross(n, t1)
    for dd in (t1, -t1, t2, -t2):
        twinkles.append(round_cone(tuple(c), tuple(c + dd * L), 0.032, 0.004))
    twinkles.append(sphere(0.042, c))
m.add("Stars", union(spheres(st_c, st_r), *twinkles), STAR, material="Neon", role="glow", tris=900, voxel=0.009)

# ---------------------------------------------------------------- faccia da svitato: occhi spaiati, ghigno smerlato
HEAD_SRC = (0.0, 0.0, ZC + RR)  # centro del tubo in alto
eyeL_f = Frame(body, HEAD_SRC, (-0.48, -1.0, 0.42), sink=0.05)   # occhio enorme (a sinistra nell'immagine)
eyeS_f = Frame(body, HEAD_SRC, (0.46, -1.0, 0.36), sink=0.04)    # occhio piccolo e strizzato
BIG, SMALL = (0.2, 0.11, 0.22), (0.13, 0.08, 0.13)
m.add("EyeWhites", union(eyeL_f.place(ellipsoid(BIG)), eyeS_f.place(ellipsoid(SMALL))), EYE_WHITE, role="shine",
      tris=450, voxel=0.012)
pupils, shines = [], []
for f, R, (px, pz), pr in ((eyeL_f, BIG, (0.05, 0.03), 0.05), (eyeS_f, SMALL, (0.0, -0.02), 0.05)):
    py = -R[1] * math.sqrt(max(1 - (px / R[0]) ** 2 - (pz / R[2]) ** 2, 0.0))
    pupils.append(f.place(ellipsoid((pr, 0.035, pr * 1.15)), (px, py + 0.02, pz)))
    shines.append(f.place(sphere(0.02), (px - 0.02, py - 0.014, pz + 0.028)))
m.add("Pupils", union(*pupils), PUPIL, role="eye", tris=250, voxel=0.008)
m.add("Shine", union(*shines), WHITE, role="shine", tris=150, voxel=0.007)


def lid_cut(p):
    return (0.035 + 0.25 * p[:, 0] - p[:, 2]) / math.sqrt(1 + 0.25 ** 2)


lid_shell = ellipsoid((SMALL[0] + 0.03, SMALL[1] + 0.03, SMALL[2] + 0.03))
m.add("Lid", eyeS_f.place(lid_shell.intersect(SDF(lid_cut, lid_shell.lo, lid_shell.hi))), DOUGH, role="skin",
      tris=300, voxel=0.01)


def grin_edges(u, a, h, curve, skew):
    t = np.clip(u / a, -1.0, 1.0)
    top = curve * t * t + skew * t + 0.016 * np.cos(u * 46.0) * (1 - t * t)  # labbro smerlato come la pasta
    bot = top - h * np.power(np.clip(1.0 - t * t, 0.0, 1.0), 0.7)
    return top, bot


mouth_f = Frame(body, HEAD_SRC, (0.0, -1.0, -0.2))
GA, GH, GC, GS = 0.46, 0.24, 0.17, 0.05


def mouth_fn(x, z):
    top, bot = grin_edges(-x, GA, GH, GC, GS)
    return np.maximum(np.maximum(z - top, bot - z), np.abs(x) - GA) * 0.8


m.add("Mouth", body.offset(0.014).intersect(mouth_f.place(stencil(mouth_fn, (-0.52, 0.52), (-0.35, 0.3), 0.5))),
      MOUTH, role="detail", tris=500, voxel=0.01)
teeth = []
src = np.array(HEAD_SRC, dtype=np.float64)
for n_row, span, sign, frac, L in ((10, 0.84, 1.0, 0.55, 0.09), (8, 0.7, -1.0, 0.42, 0.07)):
    for i in range(n_row):
        u = GA * span * (-1.0 + 2.0 * (i + 0.5) / n_row)
        top, bot = grin_edges(u, GA, GH, GC, GS)
        li = min(L, (top - bot) * frac)
        if li < 0.03:
            continue
        z0 = top - 0.004 if sign > 0 else bot + 0.004
        pa, na = project(body, src, mouth_f.point((-u, -0.3, z0)) - src)
        pb, nb = project(body, src, mouth_f.point((-u, -0.3, z0 - sign * li)) - src)
        teeth.append(round_cone(pa + na * 0.016, pb + nb * 0.016, 0.027, 0.006))
m.add("Teeth", union(*teeth), TOOTH, role="detail", tris=600, voxel=0.009)

# sopracciglia storte (una altissima, una aggrottata) e toppa ricucita sul fianco: filo scuro
brows = []
for f, pts2d in ((eyeL_f, ((0.2, 0.3), (0.08, 0.36), (-0.06, 0.37), (-0.18, 0.32))),
                 (eyeS_f, ((-0.16, 0.2), (-0.06, 0.2), (0.05, 0.17), (0.14, 0.12)))):
    pts = [on_surf(body, HEAD_SRC, f.point((x, -0.3, z)))[0] for x, z in pts2d]
    brows.append(tube(pts, [0.035, 0.048, 0.048, 0.035]))
PATCH_PHI = 1.95  # sul fianco destro in basso: il punto di partenza e' dentro il tubo, non nel buco
PATCH_SRC = (RR * math.sin(PATCH_PHI), 0.0, ZC + RR * math.cos(PATCH_PHI))
PATCH_F = Frame(body, PATCH_SRC, (0.55, -1.0, -0.25), sink=0.0)
PW, PH = 0.2, 0.17


def patch_fn(x, z):
    q = np.maximum(np.abs(x) - (PW - 0.04), 0.0)
    w = np.maximum(np.abs(z) - (PH - 0.04), 0.0)
    return np.sqrt(q * q + w * w) - 0.04


m.add("Patch", body.offset(0.022).intersect(PATCH_F.place(stencil(patch_fn, (-PW - 0.02, PW + 0.02), (-PH - 0.02, PH + 0.02), 0.4))),
      PATCH, role="detail", tris=300, voxel=0.01)
border = []
for i in range(28):
    t = 2 * math.pi * i / 28
    x, z = (PW - 0.035) * math.cos(t), (PH - 0.035) * math.sin(t)
    sq = max(abs(math.cos(t)), abs(math.sin(t)))
    border.append(on_surf(body, PATCH_SRC, PATCH_F.point((x / sq ** 0.6, 0.0, z / sq ** 0.6)))[0])
m.add("Thread", union(*brows, stitches(body, border, 9, 0.05, 0.016, across=False, lift=0.03, closed=True)),
      THREAD, role="detail", tris=500, voxel=0.009)

# ---------------------------------------------------------------- alette di pasta smerlate (animabili)
def wing_shape():
    def f(p):
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        ang = np.arctan2(z, x)
        rr = np.sqrt((x / 0.42) ** 2 + (z / 0.27) ** 2)
        edge = 1.0 + 0.06 * np.cos(14 * ang)
        d2 = (rr - edge) * 0.27
        return np.maximum(d2, np.abs(y) - 0.04) - 0.01
    return SDF(f, (-0.5, -0.06, -0.33), (0.5, 0.06, 0.33))


wr = wing_shape().translate((0.36, 0.0, 0.0)).rot(0, -28, 0).rot(0, 0, 14).translate((1.2, 0.12, ZC + 0.32))
m.add("WingR", wr, WING, role="detail", tris=600, voxel=0.012, group="WingR", pivot=(1.2, 0.12, ZC + 0.32))
m.add("WingL", wr.mirrored(), WING, role="detail", tris=600, voxel=0.012, group="WingL", pivot=(-1.2, 0.12, ZC + 0.32))

# ---------------------------------------------------------------- luna luminosa con la sua scia d'orbita
# la scia parte da dietro il tortellone e gira attorno fino alla luna, in alto a destra davanti
trail = [np.array(q) for q in __import__("lib.sdf", fromlist=["bezier"]).bezier(
    (-0.5, 0.75, 0.95), (1.1, 1.25, 1.0), (1.85, 0.45, 2.2), (1.45, -0.32, 2.72), 22)]
MOON_C = trail[-1] + (trail[-1] - trail[-2]) / np.linalg.norm(trail[-1] - trail[-2]) * 0.22
moon = sphere(0.21, MOON_C)
craters = union(*[sphere(r, MOON_C + d / np.linalg.norm(d) * 0.21) for d, r in (
    (np.array([-0.5, -0.8, 0.3]), 0.065), (np.array([0.25, -0.9, -0.3]), 0.05), (np.array([0.5, -0.6, 0.55]), 0.045),
    (np.array([-0.2, -0.7, -0.65]), 0.04))])
m.add("Moon", moon, MOON, material="Neon", role="glow", tris=400, voxel=0.01)
m.add("MoonCraters", moon.offset(0.012).intersect(craters), CRATER, role="detail", tris=200, voxel=0.008)
m.add("Orbit", tube(trail, [0.006 + 0.0014 * i for i in range(len(trail))]), ORBIT, material="Neon", role="glow",
      tris=500, voxel=0.01)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
