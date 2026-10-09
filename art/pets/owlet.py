"""Gufetto (Owlet) - pet Non comune."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import Frame, ellipsoid, prism, round_cone, sphere, stick, union  # noqa: E402
from lib.toy import Model  # noqa: E402

BODY = (150, 124, 108)
WING = (116, 92, 80)
CREAM = (252, 238, 214)
CHEVRON = (172, 128, 96)
AMBER = (255, 164, 28)
PUPIL = (24, 18, 22)
WHITE = (255, 255, 255)
BEAK = (255, 194, 56)
BLUSH = (255, 138, 150)

m = Model("Owlet", "pet")

# ------------------------------------------------------------------ batuffolo tondo con ciuffi a orecchie
HEAD_C = (0, -0.04, 1.95)
body = ellipsoid((0.9, 0.84, 0.88), (0, 0.06, 0.92))
head = ellipsoid((0.88, 0.8, 0.74), HEAD_C)
tufts = union(*[round_cone((sx * 0.42, 0.02, 2.46), (sx * 0.7, 0.1, 2.92), 0.2, 0.035) for sx in (1, -1)])
core = union(body, head, k=0.45)
core = union(core, tufts, k=0.12)
m.add("Body", core, BODY, tris=5600)
painted = core.offset(0.02)


def paint(region, t=0.02, depth=0.05):
    """Vernice sottile che segue la superficie (solo uno strato vicino alla pelle: niente facce interne inutili)."""
    return core.offset(t).intersect(region).subtract(core.offset(-depth))


# ------------------------------------------------------------------ dischi facciali e pancia color crema
eye_dirs = [(0.42 * sx, -1.0, 0.06) for sx in (1, -1)]
disc_frames = [Frame(core, HEAD_C, d) for d in eye_dirs]
discs = union(*[sphere(0.43, f.surface) for f in disc_frames], k=0.12)
belly = ellipsoid((0.56, 0.5, 0.56), (0, -0.7, 0.84))
# puntini chiari sulla fronte, a "V" sopra i dischi
dots = []
for dx, dy, dz, r in ((0.0, -0.5, 0.86, 0.05), (0.17, -0.45, 0.87, 0.045), (-0.17, -0.45, 0.87, 0.045),
                      (0.33, -0.34, 0.88, 0.04), (-0.33, -0.34, 0.88, 0.04), (0.09, -0.3, 0.95, 0.04),
                      (-0.09, -0.3, 0.95, 0.04), (0.25, -0.2, 0.95, 0.035), (-0.25, -0.2, 0.95, 0.035)):
    dots.append(sphere(r, Frame(core, HEAD_C, (dx, dy, dz)).surface))
m.add("Cream", paint(union(discs, belly, *dots)), CREAM, role="detail", tris=2000)

# piume a "V" sulla pancia (sopra la vernice crema)
def chevron(x, z, w=0.085, h=0.06, t=0.04):
    poly = [(-w, h), (0.0, 0.0), (w, h), (w, h + t), (0.0, t), (-w, h + t)]
    return prism(poly, 0.0, 1.6, round=0.012).rot(90, 0, 0).translate((x, 0.0, z))


chevrons = union(*[chevron(x, z) for z, xs in ((1.06, (-0.19, 0.0, 0.19)), (0.86, (-0.29, -0.095, 0.095, 0.29)),
                                                  (0.66, (-0.19, 0.0, 0.19)), (0.47, (-0.095, 0.095)))
                   for x in xs])
m.add("Chevrons", paint(chevrons.intersect(belly), t=0.034, depth=0.035), CHEVRON, role="detail", tris=1000,
      voxel=0.012)

# ------------------------------------------------------------------ occhioni color ambra
eye_frames = [Frame(painted, HEAD_C, d, sink=0.03) for d in eye_dirs]
m.add("Iris", union(*[f.place(ellipsoid((0.22, 0.06, 0.22))) for f in eye_frames]), AMBER, role="detail", tris=900,
      voxel=0.013)
m.add("Eyes", union(*[f.place(ellipsoid((0.14, 0.07, 0.15)), (0, -0.02, 0)) for f in eye_frames]), PUPIL, role="eye",
      tris=800, voxel=0.012)
shines = []
for f in eye_frames:
    shines.append(f.place(sphere(0.056), (-0.05, -0.08, 0.06)))
    shines.append(f.place(sphere(0.028), (0.055, -0.075, -0.065)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=450, voxel=0.01)

# becco e zampette a tre artigli
beak = union(ellipsoid((0.1, 0.08, 0.1), (0, -0.04, 0.02)), round_cone((0, -0.06, 0.0), (0, -0.1, -0.13), 0.075, 0.025),
             k=0.04)
beak = Frame(painted, HEAD_C, (0, -1.0, -0.2), sink=0.04).place(beak)
talons = []
for sx in (1, -1):
    x = sx * 0.3
    talons.append(sphere(0.11, (x, -0.24, 0.12)))
    talons += [round_cone((x, -0.3, 0.1), (x + dx, -0.58, 0.065), 0.07, 0.03) for dx in (-0.11, 0.0, 0.11)]
m.add("Beak", union(beak, union(*talons, k=0.05)), BEAK, role="detail", tris=1100, voxel=0.014)

blush = ellipsoid((0.13, 0.035, 0.08))
m.add("Blush", union(*[stick(blush, painted, HEAD_C, (0.62 * sx, -0.85, -0.3), sink=0.015) for sx in (1, -1)]),
      BLUSH, role="detail", tris=400, voxel=0.013)

# ------------------------------------------------------------------ ali con il bordo a piume (animabili)
wing = union(ellipsoid((0.15, 0.4, 0.5)), *[ellipsoid((0.12, 0.15, 0.17), (0, dy, -0.42)) for dy in (-0.22, 0.0, 0.22)],
             k=0.04)
wing_r = wing.rot(0, -12, 0).translate((0.88, 0.08, 1.0))
m.add("WingR", wing_r, WING, role="detail", tris=900, voxel=0.02, group="WingR", pivot=(0.78, 0.08, 1.42))
m.add("WingL", wing_r.mirrored(), WING, role="detail", tris=900, voxel=0.02, group="WingL", pivot=(-0.78, 0.08, 1.42))

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
