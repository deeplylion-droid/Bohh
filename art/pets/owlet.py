"""Gufetto (Owlet) - pet Non comune. Carattere: inquietante (occhi sgranati a pupille minuscole, ghigno storto)."""
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import Frame, bezier, ellipsoid, prism, project, round_cone, sphere, tube, union  # noqa: E402
from lib.toy import Model  # noqa: E402

BODY = (124, 88, 92)
WING = (86, 58, 70)
CREAM = (250, 232, 200)
CHEVRON = (98, 52, 72)
AMBER = (255, 170, 16)
PUPIL = (22, 12, 24)
WHITE = (255, 255, 255)
BEAK = (255, 190, 40)
BROW = (70, 40, 56)
MOUTH = (62, 14, 42)

m = Model("Owlet", "pet")


def face_prism(poly, y0, y1, r=0.0):
    """Regione: poligono nel piano XZ (coppie x, z) estruso lungo Y fra y0 e y1."""
    return prism(poly, -y1, -y0, round=r).rot(90, 0, 0)


def grin(xc, zc, half_w, curve, slope, thick, teeth_spec, y0, y1):
    """Bocca a mezzaluna (regione) e denti aguzzi (regione): teeth_spec (x, larghezza, frazione, 'up'/'low')."""
    def top(x):
        u = (x - xc) / half_w
        return zc + curve * u * u + slope * u, thick * max(0.0, 1 - u * u) ** 0.7

    xs = np.linspace(xc - half_w, xc + half_w, 21)
    upper = [(x, top(x)[0]) for x in xs]
    lower = [(x, top(x)[0] - top(x)[1]) for x in xs[-2:0:-1]]  # niente vertici doppi: prism() darebbe NaN
    mouth = face_prism(upper + lower, y0, y1, r=0.003)
    teeth = []
    for x, w, frac, kind in teeth_spec:
        z, th = top(x)
        if kind == "up":
            poly = [(x - w / 2, z + 0.02), (x + w / 2, z + 0.02), (x, z - frac * th)]
        else:
            poly = [(x - w / 2, z - th - 0.02), (x + w / 2, z - th - 0.02), (x, z - (1 - frac) * th)]
        teeth.append(face_prism(poly, y0, y1, r=0.003))
    return mouth, union(*teeth).intersect(mouth.offset(-0.006))

# ------------------------------------------------------------------ batuffolo tondo con ciuffi a orecchie
HEAD_C = (0, -0.04, 1.95)
body = ellipsoid((0.9, 0.84, 0.88), (0, 0.06, 0.92))
head = ellipsoid((0.88, 0.8, 0.74), HEAD_C)
tufts = union(*[round_cone((sx * 0.42, 0.02, 2.46), (sx * 0.7, 0.1, 2.92), 0.2, 0.035) for sx in (1, -1)])
core = union(body, head, k=0.45)
core = union(core, tufts, k=0.12)
m.add("Body", core, BODY, tris=5600)
painted = core.offset(0.02)


def paint(region, t=0.02, depth=0.07):
    """Vernice sottile che segue la superficie (solo uno strato vicino alla pelle: niente facce interne inutili)."""
    return core.offset(t).intersect(region).subtract(core.offset(-depth))


# ------------------------------------------------------------------ dischi facciali e pancia color crema
eye_dirs = [(0.42 * sx, -1.0, 0.06) for sx in (1, -1)]
disc_frames = [Frame(core, HEAD_C, d) for d in eye_dirs]
discs = union(*[sphere(0.43, f.surface) for f in disc_frames], ellipsoid((0.3, 0.4, 0.2), (0.04, -0.8, 1.62)), k=0.12)
mouth, teeth = grin(0.05, 1.6, 0.2, 0.05, 0.05, 0.075, [(-0.04, 0.036, 0.6, "up"), (0.06, 0.036, 0.62, "up"),
                                                         (0.16, 0.034, 0.6, "up"), (0.01, 0.03, 0.5, "low"),
                                                         (0.11, 0.03, 0.5, "low")], -1.4, -0.4)
belly = ellipsoid((0.56, 0.5, 0.56), (0, -0.7, 0.84))
# puntini chiari sulla fronte, a "V" sopra i dischi
dots = []
for dx, dy, dz, r in ((0.0, -0.5, 0.86, 0.05), (0.17, -0.45, 0.87, 0.045), (-0.17, -0.45, 0.87, 0.045),
                      (0.33, -0.34, 0.88, 0.04), (-0.33, -0.34, 0.88, 0.04), (0.09, -0.3, 0.95, 0.04),
                      (-0.09, -0.3, 0.95, 0.04), (0.25, -0.2, 0.95, 0.035), (-0.25, -0.2, 0.95, 0.035)):
    dots.append(sphere(r, Frame(core, HEAD_C, (dx, dy, dz)).surface))
m.add("Cream", paint(union(discs, belly, *dots).subtract(mouth.offset(0.012))), CREAM, role="detail", tris=2000)

# piume a "V" sulla pancia (sopra la vernice crema)
def chevron(x, z, w=0.085, h=0.06, t=0.04):
    poly = [(-w, h), (0.0, 0.0), (w, h), (w, h + t), (0.0, t), (-w, h + t)]
    return prism(poly, 0.0, 1.6, round=0.012).rot(90, 0, 0).translate((x, 0.0, z))


chevrons = union(*[chevron(x, z) for z, xs in ((1.06, (-0.19, 0.0, 0.19)), (0.86, (-0.29, -0.095, 0.095, 0.29)),
                                                  (0.66, (-0.19, 0.0, 0.19)), (0.47, (-0.095, 0.095)))
                   for x in xs])
m.add("Chevrons", paint(chevrons.intersect(belly), t=0.034, depth=0.035), CHEVRON, role="detail", tris=1000,
      voxel=0.012)

# ------------------------------------------------------------------ occhioni sgranati: iride ambra, pupilla minuscola
eye_frames = [Frame(painted, HEAD_C, d, sink=0.03) for d in eye_dirs]
m.add("Iris", union(*[f.place(ellipsoid((0.235, 0.06, 0.235)), (0, -0.016, 0)) for f in eye_frames]), AMBER,
      role="detail", tris=900, voxel=0.013)
dark = [f.place(ellipsoid((0.256, 0.035, 0.256))) for f in eye_frames]
dark += [f.place(ellipsoid((0.058, 0.04, 0.062)), (0, -0.063, 0)) for f in eye_frames]
m.add("Eyes", union(*dark), PUPIL, role="eye", tris=1000, voxel=0.012)
shines = []
for f in eye_frames:
    shines.append(f.place(sphere(0.03), (-0.09, -0.07, 0.09)))
    shines.append(f.place(sphere(0.016), (0.085, -0.068, -0.08)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=350, voxel=0.008)

# sopracciglia di piume, alte all'interno (sguardo fisso, non arrabbiato)
brows = []
for sx in (1, -1):
    pts = bezier((sx * 0.1, 0, 2.46), (sx * 0.22, 0, 2.5), (sx * 0.36, 0, 2.47), (sx * 0.5, 0, 2.38), 10)
    path = [project(core, (q[0], -0.2, q[2]), (0, -1, 0)) for q in pts]
    brows.append(tube([p - n * 0.006 for p, n in path], [0.03, 0.042, 0.048, 0.05, 0.048, 0.044, 0.04, 0.035, 0.03,
                                                          0.026, 0.022]))
m.add("Brows", union(*brows), BROW, role="detail", tris=700, voxel=0.012)

# becco adunco sopra un ghigno storto con dentini, zampette a tre artigli
beak = union(ellipsoid((0.1, 0.08, 0.1), (0, -0.04, 0.02)), round_cone((0, -0.06, 0.0), (0, -0.1, -0.13), 0.075, 0.025),
             k=0.04)
beak = Frame(painted, HEAD_C, (0, -1.0, -0.2), sink=0.04).place(beak)
talons = []
for sx in (1, -1):
    x = sx * 0.3
    talons.append(sphere(0.11, (x, -0.24, 0.12)))
    talons += [round_cone((x, -0.3, 0.1), (x + dx, -0.58, 0.065), 0.07, 0.03) for dx in (-0.11, 0.0, 0.11)]
m.add("Beak", union(beak, union(*talons, k=0.05)), BEAK, role="detail", tris=1100, voxel=0.014)
m.add("Mouth", paint(mouth, t=0.014, depth=0.03), MOUTH, role="eye", tris=600, voxel=0.009)
m.add("Teeth", paint(teeth, t=0.03, depth=0.02), WHITE, role="shine", tris=500, voxel=0.007)

# ------------------------------------------------------------------ ali con il bordo a piume (animabili)
wing = union(ellipsoid((0.15, 0.4, 0.5)), *[ellipsoid((0.12, 0.15, 0.17), (0, dy, -0.42)) for dy in (-0.22, 0.0, 0.22)],
             k=0.04)
wing_r = wing.rot(0, -12, 0).translate((0.88, 0.08, 1.0))
m.add("WingR", wing_r, WING, role="detail", tris=900, voxel=0.02, group="WingR", pivot=(0.78, 0.08, 1.42))
m.add("WingL", wing_r.mirrored(), WING, role="detail", tris=900, voxel=0.02, group="WingL", pivot=(-0.78, 0.08, 1.42))

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
