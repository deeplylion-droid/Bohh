"""Cerca le facce complanari sovrapposte (z-fighting) tra le parti di un lotto, dal dump del mondo
(art/out/world.json, da tests/cloud/dump_world.luau).

Uso: python tests/zfight_plot.py [indice_lotto]
"""
import json
import math
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SUMMIT = np.array([0.0, 330.0, 0.0])
PLOT_RADIUS = 130
EPS = 0.01


def plot_frame(i):
    a = math.radians(40 * i)
    center = SUMMIT + np.array([math.sin(a), 0, math.cos(a)]) * PLOT_RADIUS
    # CFrame.Angles(0, a, 0): colonne = assi locali x, y, z nel mondo
    rot = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    return center + np.array([0, 1.2, 0]), rot


def local_box(part, center, rot):
    p = np.array(part["p"], dtype=float)
    s = np.array(part["s"], dtype=float)
    r = np.array(part["r"][:3], dtype=float)
    u = np.array(part["r"][3:6], dtype=float)
    b = np.cross(r, u)
    axes = np.stack([r, u, b], axis=1)  # colonne: assi della parte nel mondo
    local_axes = rot.T @ axes
    # le parti devono essere allineate agli assi del lotto
    if not np.allclose(np.abs(local_axes), np.round(np.abs(local_axes)), atol=1e-3):
        return None
    half = np.abs(local_axes) @ (s / 2)
    c = rot.T @ (p - center)
    return c - half, c + half


def main():
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    center, rot = plot_frame(idx)
    parts = json.load(open(ROOT / "art" / "out" / "world.json"))["parts"]
    boxes = []
    for part in parts:
        if np.linalg.norm(np.array(part["p"]) - center) > 75 or part.get("t", 0) >= 1:
            continue
        if part.get("c") == "MeshPart":
            continue
        lb = local_box(part, center, rot)
        if lb is None:
            continue
        boxes.append((part["n"], part.get("sh", "Block"), part.get("m"), lb[0], lb[1]))
    found = {}
    for (na, sha, ma, alo, ahi), (nb, shb, mb, blo, bhi) in combinations(boxes, 2):
        # devono toccarsi o sovrapporsi
        if np.any(alo > bhi + EPS) or np.any(blo > ahi + EPS):
            continue
        for ax in range(3):
            others = [k for k in range(3) if k != ax]
            for side, (pa, pb) in (("-", (alo[ax], blo[ax])), ("+", (ahi[ax], bhi[ax]))):
                if abs(pa - pb) > EPS:
                    continue
                lo = np.maximum(alo[others], blo[others])
                hi = np.minimum(ahi[others], bhi[others])
                area = float(np.prod(np.clip(hi - lo, 0, None)))
                if area > 0.01:
                    key = tuple(sorted((na, nb))) + ("xyz"[ax] + side,)
                    found[key] = found.get(key, 0) + area
    for key, area in sorted(found.items(), key=lambda kv: -kv[1]):
        print(f"{key[0]:>16} / {key[1]:<16} faccia {key[2]}  area {area:7.2f}")
    print(f"{len(boxes)} parti, {len(found)} coppie con facce complanari")


if __name__ == "__main__":
    main()
