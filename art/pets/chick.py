"""Pulcino (Chick) - pet Comune. Carattere: dispettoso (ghigno a dentini, un sopracciglio alzato)."""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capsule, ellipsoid, prism, project, round_cone, sphere,  # noqa: E402
                     tube, union)
from lib.toy import Model  # noqa: E402

YELLOW = (255, 194, 18)
YELLOW_DARK = (242, 140, 14)
CREAM = (255, 232, 150)
ORANGE = (255, 100, 18)
EYE = (24, 14, 32)
MOUTH = (58, 10, 44)
THREAD = (84, 36, 112)
WHITE = (255, 255, 255)

m = Model("Chick", "pet")


# ------------------------------------------------------------------ aiuti (ghigno, palpebre, cuciture)
def face_prism(poly, y0, y1, r=0.0):
    """Regione: poligono nel piano XZ (coppie x, z) estruso lungo Y fra y0 e y1."""
    return prism(poly, -y1, -y0, round=r).rot(90, 0, 0)


def paint(base, region, t=0.02, depth=0.05):
    """Vernice sottile che segue la superficie (solo uno strato vicino alla pelle)."""
    return base.offset(t).intersect(region).subtract(base.offset(-depth))


def above_line(z0, slope, size=1.0):
    """Semispazio z > z0 + slope * x (coordinate locali): taglio delle palpebre."""
    n = math.sqrt(1 + slope * slope)
    return SDF(lambda p: (slope * p[:, 0] - p[:, 2] + z0) / n, (-size,) * 3, (size,) * 3)


def fast_union(shapes, pad=0.04):
    """Unione semplice di molte forme piccole: ognuna e' valutata solo vicino al suo ingombro."""
    los = [s.lo - pad for s in shapes]
    his = [s.hi + pad for s in shapes]

    def f(p):
        d = np.ones(len(p), dtype=np.float32)
        for s, lo, hi in zip(shapes, los, his):
            msk = np.all((p >= lo) & (p <= hi), axis=1)
            if msk.any():
                d[msk] = np.minimum(d[msk], s(p[msk]))
        return d

    return SDF(f, np.min(los, axis=0), np.max(his, axis=0))


def grin(xc, zc, half_w, curve, slope, thick, n_up, n_lo, tooth_w, y0, y1):
    """Bocca a mezzaluna e dentini aguzzi (sopra a punta in giu', sotto alternati), coordinate x, z del muso."""
    def top(x):
        u = (x - xc) / half_w
        return zc + curve * u * u + slope * u, thick * max(0.0, 1 - u * u) ** 0.7

    xs = np.linspace(xc - half_w, xc + half_w, 25)
    upper = [(x, top(x)[0]) for x in xs]
    lower = [(x, top(x)[0] - top(x)[1]) for x in xs[-2:0:-1]]  # niente vertici doppi: prism() darebbe NaN
    mouth = face_prism(upper + lower, y0, y1, r=0.004)
    step = 1.6 * half_w / n_up
    teeth = []
    for i in range(n_up):  # n_up dispari e n_lo pari: i denti di sotto cadono fra quelli di sopra
        x = xc + (i - (n_up - 1) / 2) * step
        z, th = top(x)
        teeth.append(face_prism([(x - tooth_w / 2, z + 0.02), (x + tooth_w / 2, z + 0.02), (x, z - 0.6 * th)],
                                y0, y1, r=0.004))
    for i in range(n_lo):
        x = xc + (i - (n_lo - 1) / 2) * step
        z, th = top(x)
        teeth.append(face_prism([(x - tooth_w * 0.42, z - th - 0.02), (x + tooth_w * 0.42, z - th - 0.02),
                                 (x, z - 0.5 * th)], y0, y1, r=0.004))
    return mouth, union(*teeth).intersect(mouth.offset(-0.009))


def eyelid(frame, radii, z0, slope):
    """Palpebra superiore pesante: guscio un po' piu' grande dell'occhio, tagliato sotto la linea z0 + slope*x."""
    shell = ellipsoid((radii[0] + 0.022, radii[1] + 0.03, radii[2] + 0.022))
    return frame.place(shell.intersect(above_line(z0, slope), k=0.012))


def front_path(base, pts2d, y_in):
    """Proietta punti (x, z) sulla superficie lungo -Y partendo da y_in (dentro la forma): (punto, normale)."""
    return [project(base, (x, y_in, z), (0, -1, 0)) for x, z in pts2d]


def resample(path, step):
    pts = np.array([p for p, _ in path])
    nrm = np.array([n for _, n in path])
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for t in np.arange(0.0, s[-1] + 1e-9, step):
        i = min(int(np.searchsorted(s, t, side="right")) - 1, len(seg) - 1)
        f = (t - s[i]) / max(seg[i], 1e-9)
        n = nrm[i] + (nrm[i + 1] - nrm[i]) * f
        out.append((pts[i] + (pts[i + 1] - pts[i]) * f, n / np.linalg.norm(n)))
    return out


def seam(path, every=0.085, half=0.042, r=0.013, line_r=0.009, inset=0.004):
    """Cucitura: linea sottile + punti corti perpendicolari (come una cicatrice di peluche)."""
    pts = resample(path, every)
    out = [tube([p - n * inset for p, n in resample(path, 0.03)], line_r)]
    for i, (p, n) in enumerate(pts):
        t = pts[min(i + 1, len(pts) - 1)][0] - pts[max(i - 1, 0)][0]
        side = np.cross(n, t / np.linalg.norm(t))
        c = p - n * inset
        out.append(capsule(c - side * half, c + side * half, r))
    return fast_union(out)


# ------------------------------------------------------------------ corpo, testa, zampe lunghette
HEAD_C = (0, -0.06, 2.06)
body = ellipsoid((0.98, 0.92, 0.86), (0, 0.02, 1.12))
head = ellipsoid((0.88, 0.82, 0.78), HEAD_C)
core = union(body, head, k=0.38)
m.add("Body", core, YELLOW, tris=4600)

belly_region = ellipsoid((0.66, 0.72, 0.6), (0, -0.62, 1.06))
m.add("Belly", paint(core, belly_region), CREAM, role="detail", tris=1100)

# ciuffo spettinato e codina
curl1 = tube(bezier((0, 0.0, 2.76), (0.0, -0.1, 3.16), (0.26, 0.0, 3.24), (0.3, 0.1, 3.02), 10),
             [0.13, 0.12, 0.1, 0.09, 0.08, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045])
curl2 = tube(bezier((-0.05, 0.02, 2.76), (-0.2, -0.04, 3.06), (-0.42, 0.04, 3.04), (-0.44, 0.16, 2.88), 10),
             [0.11, 0.1, 0.09, 0.08, 0.07, 0.06, 0.055, 0.05, 0.045, 0.04, 0.04])
curl3 = tube(bezier((0.05, 0.08, 2.78), (0.12, 0.26, 3.0), (0.02, 0.4, 3.04), (-0.06, 0.42, 2.9), 8),
             [0.09, 0.08, 0.07, 0.06, 0.055, 0.05, 0.045, 0.04, 0.04])
tuft = union(curl1, curl2, curl3, sphere(0.16, (0, 0.0, 2.74)), k=0.08)
tail = union(*[tube([(dx * 0.3, 0.75, 1.22), (dx * 0.5, 1.12, 1.5 + 0.08 * (1 - abs(dx)))], [0.16, 0.07])
               for dx in (-1, 0, 1)], k=0.1)
m.add("Tuft", union(tuft, tail), YELLOW_DARK, role="detail", tris=1300)

# ali con tre "dita" di piume (animabili)
wing = union(ellipsoid((0.16, 0.36, 0.42), (0, 0, -0.1)),
             *[round_cone((0, dy, -0.3), (0.02, dy - 0.05, -0.64), 0.1, 0.065) for dy in (-0.16, 0.0, 0.16)], k=0.06)
wing_r = wing.rot(15, 0, 0).rot(0, -22, 0).translate((0.95, -0.02, 1.42))
m.add("WingR", wing_r, YELLOW_DARK, role="detail", tris=900, group="WingR", pivot=(0.82, -0.02, 1.62))
m.add("WingL", wing_r.mirrored(), YELLOW_DARK, role="detail", tris=900, group="WingL", pivot=(-0.82, -0.02, 1.62))

# zampe e piedi a tre dita
feet = []
for sx in (1, -1):
    x = sx * 0.36
    feet.append(tube([(x * 0.94, -0.08, 0.6), (x, -0.16, 0.16)], [0.085, 0.075]))
    feet.append(sphere(0.12, (x, -0.2, 0.13)))
    feet += [capsule((x, -0.24, 0.085), (x + dx, -0.62, 0.078), 0.078) for dx in (-0.17, 0.0, 0.17)]
m.add("Feet", union(*feet, k=0.06), ORANGE, role="detail", tris=1300)

# ------------------------------------------------------------------ faccia: occhi con palpebre, sopracciglia, ghigno
EYE_R = (0.15, 0.09, 0.2)
eye_frames = [Frame(head, HEAD_C, (0.42 * sx, -1.0, 0.16), sink=0.05) for sx in (1, -1)]
pupils = [f.place(ellipsoid(EYE_R)) for f in eye_frames]
# occhio sinistro (x>0) aperto sotto il sopracciglio alzato, destro socchiuso e furbo
lids = union(eyelid(eye_frames[0], EYE_R, 0.11, 0.0), eyelid(eye_frames[1], EYE_R, 0.02, 0.12))
m.add("Lids", lids, YELLOW, role="skin", tris=700, voxel=0.012)

brows = []
for p0, p1, p2 in (((0.15, 2.5), (0.3, 2.63), (0.5, 2.57)), ((-0.13, 2.44), (-0.3, 2.47), (-0.5, 2.46))):
    pts = bezier((p0[0], 0, p0[1]), (p1[0], 0, p1[1]), (p1[0], 0, p1[1]), (p2[0], 0, p2[1]), 8)
    path = front_path(core, [(p[0], p[2]) for p in pts], -0.4)
    brows.append(tube([p - n * 0.01 for p, n in path], list(np.linspace(0.05, 0.03, len(path)))))

beak = union(ellipsoid((0.17, 0.15, 0.085), (0, -0.06, 0.03)), ellipsoid((0.12, 0.1, 0.06), (0, -0.03, -0.07)), k=0.04)
m.add("Beak", Frame(head, HEAD_C, (0, -1.0, -0.02), sink=0.07).place(beak), ORANGE, role="detail", tris=700,
      voxel=0.013)

mouth, teeth = grin(0.03, 1.87, 0.34, 0.06, 0.05, 0.13, 7, 4, 0.05, -1.4, -0.4)
seam_path = front_path(core.offset(0.02), [(0.0, z) for z in np.linspace(1.5, 0.62, 12)], -0.3)
belly_seam = seam(seam_path, inset=-0.002, line_r=0.01)
m.add("Stitches", union(*brows, belly_seam), THREAD, role="detail", tris=1300, voxel=0.01)

m.add("Eyes", union(*pupils), EYE, role="eye", tris=900, voxel=0.012)
m.add("Mouth", paint(core, mouth, t=0.014, depth=0.03), MOUTH, role="eye", tris=600, voxel=0.008)
shines = []
for f, (hz, lz) in zip(eye_frames, ((0.03, -0.11), (-0.03, -0.12))):
    shines.append(f.place(sphere(0.042), (-0.05, -0.08, hz)))
    shines.append(f.place(sphere(0.022), (0.055, -0.072, lz)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=400, voxel=0.009)
m.add("Teeth", paint(core, teeth, t=0.03, depth=0.02), WHITE, role="shine", tris=700, voxel=0.007)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
