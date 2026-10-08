"""Disegna la mappa dall'alto (art/out/layout_top.png) dal JSON esportato da dump_layout.luau."""
import json, math
from PIL import Image, ImageDraw

d = json.load(open("art/out/layout.json"))
W, H = 1000, 1300
X0, Z0, SC = -330, -230, 1.5  # mondo -> pixel
def px(x, z):
    return ((x - X0) * SC, (z - Z0) * SC)

ZC = {"Meadow": (110, 214, 80), "Forest": (48, 150, 90), "Canyon": (232, 140, 70), "Crystal": (120, 160, 255), "Crater": (255, 80, 40)}
im = Image.new("RGB", (W, H), (30, 34, 48))
dr = ImageDraw.Draw(im)
# vetta
cx, cz = px(0, 0)
dr.ellipse((cx - 178 * SC, cz - 178 * SC, cx + 178 * SC, cz + 178 * SC), outline=(240, 240, 255), width=2)
dr.ellipse((cx - 92 * SC, cz - 92 * SC, cx + 92 * SC, cz + 92 * SC), outline=(160, 160, 190), width=1)
for i in range(1, 9):
    x, z, lx, lz = d[f"plot{i}"]
    # rettangolo 60x66 orientato
    rx, rz = -lz, lx  # destra
    pts = []
    for a, b in ((-30, -33), (30, -33), (30, 33), (-30, 33)):
        wx = x + rx * a + lx * b
        wz = z + rz * a + lz * b
        pts.append(px(wx, wz))
    dr.polygon(pts, outline=(255, 210, 80), width=2)
    gx, gz = px(x + lx * 33, z + lz * 33)
    dr.ellipse((gx - 4, gz - 4, gx + 4, gz + 4), fill=(255, 80, 80))
    dr.text(px(x, z), str(i), fill=(255, 255, 255))
# sentiero (larghezza 44)
pts = d["path"]
for i in range(len(pts) - 1):
    a, b = pts[i], pts[i + 1]
    dr.line((px(a[0], a[2]), px(b[0], b[2])), fill=ZC[a[3]], width=int(44 * SC))
for i in range(0, len(pts), 25):
    a = pts[i]
    dr.text(px(a[0] + 3, a[2] - 6), f"{a[1]:.0f}", fill=(0, 0, 0))
# cratere
cxr, czr = px(70, 620)
dr.ellipse((cxr - 92 * SC, czr - 92 * SC, cxr + 92 * SC, czr + 92 * SC), outline=(255, 120, 60), width=2)
dr.ellipse((cxr - 128 * SC, czr - 128 * SC, cxr + 128 * SC, czr + 128 * SC), outline=(160, 80, 40), width=1)
for x, y, z, lx, lz in d["shelters"]:
    sx, sz = px(x, z)
    dr.rectangle((sx - 7, sz - 7, sx + 7, sz + 7), outline=(255, 255, 255), width=2)
    dr.line((sx, sz, sx + lx * 14, sz + lz * 14), fill=(255, 255, 255), width=2)
for x, y, z, zone in d["nests"]:
    sx, sz = px(x, z)
    dr.ellipse((sx - 4, sz - 4, sx + 4, sz + 4), fill=(255, 245, 200), outline=(80, 50, 20))
for x, y, z, r, leash in d["lairs"]:
    sx, sz = px(x, z)
    dr.ellipse((sx - r * SC, sz - r * SC, sx + r * SC, sz + r * SC), outline=(255, 60, 160), width=2)
    dr.ellipse((sx - leash * SC, sz - leash * SC, sx + leash * SC, sz + leash * SC), outline=(150, 40, 100), width=1)
im.save("art/out/layout_top.png")
print("ok")
