"""Anteprima software (numpy) di una o più mesh: python3 render.py NomeMesh [...] -> PNG nella scratchpad."""
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from atlas import TILE, TILES, build_atlas  # noqa: E402
from models import all_models  # noqa: E402


def render(meshes, atlas, path, size=420, yaw=0.6, pitch=0.25):
    tris = []
    for m in meshes:
        for t in m.tris:
            tris.append(t)
    P = np.array([[p for p in t[:3]] for t in tris], dtype=float)
    tiles = np.array([t[3] for t in tris])
    lo, hi = P.reshape(-1, 3).min(0), P.reshape(-1, 3).max(0)
    c = (lo + hi) / 2
    P = P - c
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    R = np.array([[cy, 0, -sy], [0, 1, 0], [sy, 0, cy]]) @ np.eye(3)
    R = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]]) @ R
    V = P @ R.T
    scale = size * 0.85 / max(hi - lo)
    img = np.full((size, size, 3), 30.0)
    zbuf = np.full((size, size), -1e9)
    N = np.cross(V[:, 1] - V[:, 0], V[:, 2] - V[:, 0])
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-9
    light = np.array([0.4, 0.7, 0.6]); light /= np.linalg.norm(light)
    tile_col = []
    for i in range(TILES * TILES):
        tx, ty = i % TILES, i // TILES
        tile_col.append(atlas[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE, :3].reshape(-1, 3).mean(0))
    for k in range(len(V)):
        if N[k, 2] <= 0:  # back-face culling (camera guarda verso -z)
            continue
        pts = V[k][:, :2] * scale * np.array([1, -1]) + size / 2
        x0, y0 = np.floor(pts.min(0)).astype(int)
        x1, y1 = np.ceil(pts.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
        if x0 > x1 or y0 > y1:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx_, cy_) = pts
        d = (by - cy_) * (ax - cx_) + (cx_ - bx) * (ay - cy_)
        if abs(d) < 1e-9:
            continue
        w1 = ((by - cy_) * (xs - cx_) + (cx_ - bx) * (ys - cy_)) / d
        w2 = ((cy_ - ay) * (xs - cx_) + (ax - cx_) * (ys - cy_)) / d
        w3 = 1 - w1 - w2
        mask = (w1 >= 0) & (w2 >= 0) & (w3 >= 0)
        z = w1 * V[k, 0, 2] + w2 * V[k, 1, 2] + w3 * V[k, 2, 2]
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        upd = mask & (z > sub)
        sub[upd] = z[upd]
        shade = 0.35 + 0.65 * max(0.0, float(N[k] @ light))
        img[y0:y1 + 1, x0:x1 + 1][upd] = tile_col[tiles[k]] * shade * 1.6
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(path)


if __name__ == "__main__":
    out = sys.argv[1]
    names = sys.argv[2:]
    atlas = build_atlas()
    meshes = {m.name: m for m in all_models()}
    groups = [n.split("+") for n in names]
    images = []
    for i, g in enumerate(groups):
        p = os.path.join(out, "prev_%d.png" % i)
        render([meshes[n] for n in g], atlas, p)
        images.append(Image.open(p))
    W = sum(im.width for im in images)
    sheet = Image.new("RGB", (W, images[0].height))
    x = 0
    for im in images:
        sheet.paste(im, (x, 0))
        x += im.width
    sheet.save(os.path.join(out, "preview.png"))
    print("ok")
