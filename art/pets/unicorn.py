"""Unicorno (Unicorn) - pet Leggendario. Carattere: inquietante-tenero (occhione innocente + occhio a bottone)."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capsule, cylinder, ellipsoid, prism, project, round_cone, smin,  # noqa: E402
                     sphere, star_points, stick, torus, tube, union)
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


def curve_on(sdf, pts, direction=(0, -1, 0), lift=0.0):
    """Proietta punti (interni alla forma) sulla superficie lungo 'direction'."""
    d = norm(direction)
    out = []
    for q in pts:
        p, n = project(sdf, np.asarray(q, float), d)
        out.append(np.asarray(p, float) + np.asarray(n, float) * lift)
    return out


def stitch_row(sdf, pts, dash=0.075, gap=0.05, r=0.017, cross=False, cross_len=0.11, sink=0.35, closed=False):
    """Cucitura sulla superficie: trattini lungo la linea, oppure punti trasversali (cross=True)."""
    pts = list(pts) + ([pts[0]] if closed else [])
    pts = resample(pts, (dash + gap) * (0.8 if cross else 1.0))
    out = []
    for i in range(len(pts) if cross else len(pts) - 1):
        if cross:
            p = pts[i]
            t = norm(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)])
            side = norm(np.cross(t, grad(sdf, p)))
            a = on_surface(sdf, p - side * cross_len / 2, -r * sink, 3)
            b = on_surface(sdf, p + side * cross_len / 2, -r * sink, 3)
        else:
            a = on_surface(sdf, pts[i], -r * sink, 2)
            b = on_surface(sdf, pts[i] + (pts[i + 1] - pts[i]) * dash / (dash + gap), -r * sink, 2)
        out.append(capsule(tuple(a), tuple(b), r))
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


def button_parts(frame, r=0.16, th=0.055, hole=0.024, thread_r=0.019):
    """Bottone cucito (disco con bordo e 4 fori) + filo a X, fronte verso l'esterno."""
    disc = cylinder((0, 0.03, 0), (0, -th, 0), r, round=th * 0.45)
    rim = torus(r * 0.8, th * 0.3).rot(90, 0, 0).translate((0, -th, 0))
    hd = r * 0.3
    holes = union(*[cylinder((sx * hd, 0.2, sz * hd), (sx * hd, -th - 0.2, sz * hd), hole) for sx in (1, -1) for sz in (1, -1)])
    btn = union(disc, rim, k=0.02).subtract(holes, k=0.008)
    y = -th + 0.004
    thread = union(capsule((-hd, y, -hd), (hd, y, hd), thread_r), capsule((-hd, y, hd), (hd, y, -hd), thread_r))
    return frame.place(btn), frame.place(thread)


# ============================================================ colori
WHITE_BODY = (246, 244, 252)
HOOF = (214, 52, 128)
BLUSH = (255, 96, 156)
GOLD = (255, 188, 36)
EYE = (26, 12, 40)
WHITE = (255, 255, 255)
MOUTH_IN = (66, 14, 54)
BUTTON = (98, 40, 164)
STITCH = (74, 26, 116)
MANE = [  # un colore per parte, dal ciuffo alla coda
    ("Pink", (255, 62, 156)),
    ("Orange", (255, 134, 22)),
    ("Yellow", (255, 212, 28)),
    ("Mint", (34, 204, 122)),
    ("Sky", (34, 144, 255)),
    ("Lilac", (146, 74, 240)),
]


def snap(points, sdf, target):
    """Porta i punti a distanza 'target' dalla superficie (ciocche che aderiscono al corpo)."""
    return [tuple(on_surface(sdf, p, target)) for p in points]


def lock_path(root, U, V, length, curl_r, turns=0.75, n_line=6, n_curl=10, sag=0.0):
    """Ciocca: tratto quasi dritto lungo U, poi ricciolo a spirale verso V."""
    root, U, V = np.asarray(root, float), norm(U), norm(V)
    V = norm(V - U * (V @ U))
    pts = [root + U * length * (i / n_line) + V * sag * math.sin(math.pi * i / n_line) for i in range(n_line + 1)]
    c = pts[-1] + V * curl_r
    for j in range(1, n_curl + 1):
        a = j / n_curl * turns * 2 * math.pi
        r = curl_r * (1 - 0.45 * j / n_curl)
        pts.append(c + (-V * math.cos(a) + U * math.sin(a)) * r)
    return pts


def lock_radii(pts, r0, r_peak, r_tip, peak=0.25):
    seg = [0.0] + [float(np.linalg.norm(np.subtract(pts[i + 1], pts[i]))) for i in range(len(pts) - 1)]
    cum = np.cumsum(seg)
    out = []
    for s in cum / cum[-1]:
        if s < peak:
            out.append(r0 + (r_peak - r0) * math.sin(s / peak * math.pi / 2))
        else:
            out.append(r_tip + (r_peak - r_tip) * (1 - (s - peak) / (1 - peak)) ** 1.1)
    return out


def twisted_horn(length, r_base, r_tip, lobes=2, turns=2.2, amp=0.2) -> SDF:
    """Corno a spirale (asse +Z da 0 a length): sezione a lobi che ruota salendo."""
    def f(p):
        rho = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2)
        th = np.arctan2(p[:, 1], p[:, 0])
        t = np.clip(p[:, 2] / length, 0.0, 1.0)
        R = r_base * (1 - t) + r_tip * t
        mod = 1.0 + amp * np.cos(lobes * (th - 2 * math.pi * turns * t))
        d_side = (rho - R * mod) * 0.6
        d_cap = np.maximum(-p[:, 2], p[:, 2] - length)
        a = np.maximum(d_side, 0)
        b = np.maximum(d_cap, 0)
        return np.minimum(np.maximum(d_side, d_cap), 0) + np.sqrt(a * a + b * b)

    e = r_base * (1 + amp)
    return SDF(f, (-e, -e, 0), (e, e, length))


m = Model("Unicorn", "pet")

# ------------------------------------------------------------------ corpo; la testa e' inclinata di lato
TILT, PIVOT = 9.0, (0.0, -0.25, 1.32)


def T(s):
    """Inclina una forma insieme alla testa."""
    return s.rot(0, TILT, 0, pivot=PIVOT)


HEAD_C = (0, -0.42, 1.9)
MZ_C = (0, -0.99, 1.66)
head = ellipsoid((0.72, 0.64, 0.62), HEAD_C)
muzzle = ellipsoid((0.45, 0.36, 0.32), MZ_C)
EAR_C = [(sx * 0.38, -0.3, 2.48) for sx in (1, -1)]
ears = union(*[ellipsoid((0.135, 0.085, 0.25)).rot(0, sx * 22, 0).translate(c) for sx, c in zip((1, -1), EAR_C)])
head_u = union(union(head, muzzle, k=0.18), ears, k=0.06)

torso = ellipsoid((0.66, 0.8, 0.56), (0, 0.22, 0.86))
chest = ellipsoid((0.6, 0.5, 0.52), (0, -0.2, 0.94))
neck = capsule((0, -0.1, 1.12), (0, -0.3, 1.56), 0.36)
LEGS = [(sx * 0.34, y) for sx in (1, -1) for y in (-0.24, 0.62)]
legs = union(*[capsule((x, y, 0.76), (x * 1.06, y + 0.02, 0.22), 0.19) for x, y in LEGS])
body_core = union(union(union(torso, chest, k=0.3), neck, k=0.25), legs, k=0.12)
core_u = union(body_core, head_u, k=0.25)  # testa dritta: serve per costruire i dettagli
core = union(body_core, T(head_u), k=0.25)
m.add("Body", core, WHITE_BODY, tris=4600, voxel=0.025)

# zoccoli lampone e interno delle orecchie
hooves = union(*[cylinder((x * 1.06, y + 0.02, 0.0), (x * 1.06, y + 0.02, 0.21), 0.22, round=0.065) for x, y in LEGS])
ear_in = union(*[ellipsoid((0.075, 0.1, 0.17), (0, -0.07, -0.02)).rot(0, sx * 22, 0).translate(c) for sx, c in zip((1, -1), EAR_C)])
m.add("Hooves", union(hooves, T(core_u.offset(0.02).intersect(ear_in))), HOOF, role="detail", tris=800, voxel=0.016)

# ------------------------------------------------------------------ corno d'oro a spirale
horn_base, horn_n = project(head, HEAD_C, (0, -0.62, 0.82))
horn = twisted_horn(0.76, 0.14, 0.018).rot(18, 0, 0).translate(horn_base - horn_n * 0.06)
m.add("Horn", T(horn), GOLD, role="detail", tris=900, voxel=0.012)

# ------------------------------------------------------------------ criniera e coda arcobaleno
locks = {nm: [] for nm, _ in MANE}
NAMES = [nm for nm, _ in MANE]
for nm, sx in (("Pink", 1), ("Orange", -1)):  # frangia ai lati del corno
    root = np.array([sx * 0.05, -0.5, 2.56])
    pts = snap(lock_path(root, (sx * 1.0, -0.35, -0.32), (0, -1.0, -0.7), 0.4, 0.12, turns=0.6, sag=0.04), core_u, 0.08)
    locks[nm].append(T(tube(pts, lock_radii(pts, 0.16, 0.18, 0.04))))
crest = snap(bezier((0, -0.36, 2.58), (0, 0.0, 2.62), (0, 0.16, 2.16), (0, 0.24, 1.34), 40), core_u, 0.02)
roots_t = [0.1, 0.22, 0.36, 0.5, 0.64, 0.8, 0.95]
order = ["Yellow", "Mint", "Sky", "Lilac", "Pink", "Orange", "Yellow"]
for i, nm in enumerate(order):
    root = np.asarray(crest[int(roots_t[i] * (len(crest) - 1))])
    alt = 1 if i % 2 == 0 else -1
    for sx in (1, -1):
        U = (sx * 0.6, 0.1 + 0.1 * i, -0.8) if i < 2 else (sx * 0.78, 0.25 + 0.06 * i, -0.62)
        V = (0, alt * sx, 0.25 * alt)
        length = (0.7, 0.6)[i] if i < 2 else 0.3 + 0.025 * i
        pts = snap(lock_path(root, U, V, length, 0.14, turns=0.7), core_u, 0.075)
        locks[nm].append(T(tube(pts, lock_radii(pts, 0.17, 0.19, 0.04))))
TAIL_ROOT = np.array([0, 0.94, 1.04])
tail_dirs = [(0.15, 0.85, 0.3), (-0.22, 0.9, 0.0), (0.26, 0.8, -0.38), (-0.26, 0.7, -0.6), (0.14, 0.55, -0.85),
             (-0.12, 0.45, -0.92)]
for i, nm in enumerate(NAMES):
    U = norm(tail_dirs[i])
    root = TAIL_ROOT + np.array([0.05 * (1 if i % 2 else -1), 0, -0.03 * i])
    V = norm(np.cross(U, (1 if i % 2 else -1, 0, 0)))
    pts = lock_path(root, U, V, 0.42 + 0.04 * i, 0.17, turns=0.75)
    locks[nm].append(tube(pts, lock_radii(pts, 0.15, 0.2, 0.045, peak=0.2)))
for nm, col in MANE:
    m.add(nm, union(*locks[nm]), col, role="detail", tris=650, voxel=0.016)

# ------------------------------------------------------------------ occhi: uno innocente con pupilla piccola, uno a bottone
EA, EB, EC = 0.21, 0.11, 0.27
f_eye = Frame(head, HEAD_C, (-0.5, -1.0, 0.24), sink=0.05)  # occhio vero (lato -X)
f_btn = Frame(head, HEAD_C, (0.5, -1.0, 0.24), sink=0.0)  # occhio a bottone (lato +X)
eye_white = f_eye.place(ellipsoid((EA, EB, EC)))
pupil = f_eye.place(ellipsoid((0.085, 0.05, 0.105)), (0.01, -EB * 0.88, 0.0))
rim = f_eye.place(tube([(EA * 0.87 * math.cos(t), -0.056, EC * 0.87 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 41)], 0.02))
lashes = []
for phi, ln in ((14, 0.15), (36, 0.19), (58, 0.19), (80, 0.15)):  # lato esterno = +X locale
    a = math.radians(phi)
    p0 = np.array([EA * 0.94 * math.cos(a), -0.025, EC * 0.94 * math.sin(a)])
    d = np.array([math.cos(a + 0.35), 0, math.sin(a + 0.35)])
    p1 = p0 + d * ln * 0.55 + np.array([0, -0.025, 0])
    p2 = p0 + d * ln + np.array([0, -0.01, 0.06])
    lashes.append(f_eye.place(tube([tuple(p0), tuple(p1), tuple(p2)], [0.03, 0.022, 0.011])))
for phi, ln in ((-22, 0.09), (-44, 0.08)):  # due ciglia inferiori
    a = math.radians(phi)
    p0 = np.array([EA * 0.9 * math.cos(a), -0.03, EC * 0.9 * math.sin(a)])
    d = np.array([math.cos(a - 0.3), 0, math.sin(a - 0.3)])
    lashes.append(f_eye.place(tube([tuple(p0), tuple(p0 + d * ln + np.array([0, -0.01, 0]))], [0.02, 0.009])))
btn, thread = button_parts(f_btn, r=0.17)
hl = [f_eye.place(sphere(0.026), (-0.02, -EB * 0.88 - 0.04, 0.045)), f_eye.place(sphere(0.013), (0.035, -EB * 0.88 - 0.035, -0.04))]

# sorriso un po' troppo largo con dentini minuscoli
MOUTH = dict(cx=0.0, cz=1.6, w=0.37, depth=0.08, curve=0.12, tilt=0.0)
mouth_surf = core_u.offset(0.016)
mouth = mouth_surf.intersect(grin_sdf(**MOUTH, y_max=-0.9))
teeth = grin_teeth(mouth_surf, MZ_C[1], **MOUTH, n=12, length=0.04, r=0.018, span=0.86)
nostrils = union(*[Frame(muzzle, MZ_C, (sx * 0.4, -1.0, 0.32), sink=0.02).place(ellipsoid((0.04, 0.03, 0.028))) for sx in (1, -1)])
m.add("Eyes", T(union(pupil, rim, *lashes, mouth, nostrils)), EYE, role="eye", tris=1000, voxel=0.01)
m.add("Shine", T(union(eye_white, *hl, thread, *teeth)), WHITE, role="shine", tris=900, voxel=0.01)
m.add("Button", T(btn), BUTTON, role="eye", tris=600, voxel=0.011)
blush = ellipsoid((0.14, 0.04, 0.08))
m.add("Blush", T(union(*[stick(blush, head, HEAD_C, (sx * 0.8, -0.72, -0.32), sink=0.02) for sx in (1, -1)])),
      BLUSH, role="detail", tris=300, voxel=0.013)

# ------------------------------------------------------------------ toppa a stella cucita sui fianchi + cucitura sul petto
STAR_C = (0.46, 0.96)  # (y, z) sul fianco
star = prism(star_points(5, 0.23, 0.1, rot_deg=180), -0.9, 0.9).rot(0, 90, 0).translate((0, STAR_C[0], STAR_C[1]))
m.add("Stars", core.offset(0.02).intersect(star), (255, 206, 60), material="Neon", role="glow", tris=500, voxel=0.012)
stitches = []
outline = star_points(5, 0.3, 0.15, rot_deg=180)
for sx in (1, -1):
    pts = [(sx * 0.2, STAR_C[0] + y, STAR_C[1] - x) for x, y in outline]  # stessa mappatura della rotazione (0, 90, 0)
    pts = curve_on(core, [tuple(p) for p in resample(pts + [pts[0]], 0.03)], (sx, 0, 0))
    stitches += stitch_row(core, pts, dash=0.05, gap=0.04, r=0.014)
chest_pts = curve_on(core, [(0.0, 0.0, z) for z in np.linspace(1.24, 0.5, 16)])  # cucitura al centro del petto
stitches += stitch_row(core, chest_pts, dash=0.05, gap=0.055, r=0.016, cross=True, cross_len=0.1)
m.add("Stitches", fast_union(stitches), STITCH, role="detail", tris=1000, voxel=0.01)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
