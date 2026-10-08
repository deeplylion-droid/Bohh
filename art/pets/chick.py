"""Pulcino (Chick) - pet Comune."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import bezier, capsule, ellipsoid, sphere, stick, tube, union  # noqa: E402
from lib.toy import Model  # noqa: E402

YELLOW = (255, 212, 48)
YELLOW_DARK = (255, 180, 30)
CREAM = (255, 242, 186)
ORANGE = (255, 132, 28)
EYE = (30, 24, 38)
WHITE = (255, 255, 255)
BLUSH = (255, 120, 150)

m = Model("Chick", "pet")

HEAD_C = (0, -0.06, 1.92)
body = ellipsoid((1.0, 0.94, 0.9), (0, 0.02, 0.95))
head = ellipsoid((0.9, 0.85, 0.82), HEAD_C)
core = union(body, head, k=0.38)
m.add("Body", core, YELLOW, tris=5200)

belly_region = ellipsoid((0.7, 0.75, 0.6), (0, -0.62, 0.86))
m.add("Belly", core.offset(0.022).intersect(belly_region), CREAM, role="detail", tris=1400)

# ciuffo a tre riccioli + codina
curl1 = tube(bezier((0, 0.0, 2.6), (0.0, -0.08, 3.0), (0.22, 0.02, 3.08), (0.25, 0.1, 2.88), 10),
             [0.13, 0.12, 0.1, 0.09, 0.08, 0.07, 0.065, 0.06, 0.055, 0.05, 0.045])
curl2 = tube(bezier((-0.05, 0.02, 2.6), (-0.18, -0.02, 2.92), (-0.38, 0.06, 2.9), (-0.36, 0.14, 2.74), 10),
             [0.11, 0.1, 0.09, 0.08, 0.07, 0.06, 0.055, 0.05, 0.045, 0.04, 0.04])
curl3 = tube(bezier((0.05, 0.06, 2.62), (0.1, 0.2, 2.86), (0.0, 0.32, 2.88), (-0.05, 0.34, 2.76), 8),
             [0.09, 0.08, 0.07, 0.06, 0.055, 0.05, 0.045, 0.04, 0.04])
tuft = union(curl1, curl2, curl3, sphere(0.16, (0, 0.0, 2.58)), k=0.08)
tail = union(*[tube([(dx * 0.3, 0.75, 1.05), (dx * 0.5, 1.12, 1.32 + 0.08 * (1 - abs(dx)))], [0.16, 0.07]) for dx in (-1, 0, 1)], k=0.1)
m.add("Tuft", union(tuft, tail, k=0.0), YELLOW_DARK, role="detail", tris=1600)

# ali (animabili)
wing_r = ellipsoid((0.17, 0.44, 0.36), (0, 0, 0)).rot(0, -20, 0).rot(14, 0, 0).translate((0.98, 0.05, 1.05))
m.add("WingR", wing_r, YELLOW_DARK, role="detail", tris=900, group="WingR", pivot=(0.86, 0.0, 1.32))
m.add("WingL", wing_r.mirrored(), YELLOW_DARK, role="detail", tris=900, group="WingL", pivot=(-0.86, 0.0, 1.32))

# occhi grandi e lucidi appoggiati sulla testa
from lib.sdf import Frame  # noqa: E402

eye_shape = ellipsoid((0.15, 0.09, 0.2))
eye_frames = [Frame(head, HEAD_C, (0.42 * sx, -1.0, 0.06), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in eye_frames]), EYE, role="eye", tris=1000, voxel=0.015)
# riflessi: stesso lato in entrambi gli occhi (luce coerente), sporgono dalla superficie dell'occhio
shines = []
for f in eye_frames:
    shines.append(f.place(sphere(0.058), (-0.05, -0.075, 0.075)))
    shines.append(f.place(sphere(0.03), (0.055, -0.07, -0.085)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=500, voxel=0.01)

# guance
blush = ellipsoid((0.17, 0.04, 0.1))
m.add("Blush", union(stick(blush, head, HEAD_C, (0.72, -0.85, -0.32), sink=0.02),
                     stick(blush, head, HEAD_C, (-0.72, -0.85, -0.32), sink=0.02)),
      BLUSH, role="detail", tris=500, voxel=0.015)

# becco a "diamante"
beak = union(ellipsoid((0.2, 0.17, 0.1), (0, -0.06, 0.04)), ellipsoid((0.15, 0.12, 0.075), (0, -0.03, -0.08)), k=0.04)
m.add("Beak", stick(beak, head, HEAD_C, (0, -1.0, -0.14), sink=0.07), ORANGE, role="detail", tris=900, voxel=0.015)

# zampe: tre dita per piede
def foot(x):
    toes = [capsule((x, -0.22, 0.08), (x + dx, -0.62, 0.065), 0.08) for dx in (-0.17, 0.0, 0.17)]
    return union(*toes, sphere(0.13, (x, -0.2, 0.1)), k=0.07)

m.add("Feet", union(foot(0.38), foot(-0.38)), ORANGE, role="detail", tris=1300)

if __name__ == "__main__":
    import os
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
