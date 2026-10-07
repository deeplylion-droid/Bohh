"""Modelli procedurali di "The Rake": vegetazione, telecamere, strumenti e creatura.

Ogni funzione restituisce una lista di Mesh. L'origine di ogni mesh è il suo punto di aggancio
(base dell'albero, centro della telecamera, impugnatura dell'attrezzo, giuntura dell'arto).
"""
import math
import random

from atlas import T
from gltf import Mesh
from shapes import (add, bent_path, blob, cross, cylinder, dot, lerp, mul, norm, rotate, rounded_box, sub, tri_out, tube,
                    two_sided)


def moss_on_top(base_tile, threshold=0.55):
    return lambda n: T["moss"] if n[1] > threshold else base_tile


# --------------------------------------------------------------------------------------------
# Alberi


def pine(name, seed, height, snag=False):
    rnd = random.Random(seed)
    trunk = Mesh(name + "_Trunk", smooth=True, tex_scale=0.3)
    base_r = height * 0.03 + 0.55
    top = height * (0.72 if snag else 0.95)
    lean = (rnd.uniform(-0.04, 0.04), 0, rnd.uniform(-0.04, 0.04))
    pts, radii = [], []
    steps = 14
    for i in range(steps + 1):
        t = i / steps
        y = -1.5 + (top + 1.5) * t
        bend = math.sin(t * math.pi * rnd.uniform(0.8, 1.6)) * 0.4
        pts.append((lean[0] * y + bend * 0.3, y, lean[2] * y + bend * 0.2))
        flare = 1 + 0.9 * max(0.0, 1 - (y + 1.5) / 3.5) ** 2
        radii.append(max(0.12, base_r * (1 - t * 0.88) * flare))
    if snag:
        radii[-1] = radii[-2] * 0.8  # tronco spezzato
    tube(trunk, pts, radii, 12, T["bark_gray" if snag else "bark_pine"], noise=0.07, seed=seed, end_tile=T["wood_cut"],
         ring_jitter=(lambda i, j: (0, rnd.uniform(-0.6, 0.6), 0)) if snag else None)
    # radici
    for k in range(5):
        ang = k / 5 * math.pi * 2 + rnd.uniform(-0.3, 0.3)
        d = (math.cos(ang), -0.35, math.sin(ang))
        start = (math.cos(ang) * base_r * 0.6, 0.6, math.sin(ang) * base_r * 0.6)
        path = bent_path(start, d, rnd.uniform(2.5, 4), 4, 0.15, rnd)
        tube(trunk, path, [base_r * 0.55 * (1 - i / 4) + 0.08 for i in range(5)], 7, T["bark_pine"], noise=0.1, seed=seed + k)
    # rami secchi in basso
    for k in range(rnd.randint(5, 9) + (6 if snag else 0)):
        y = rnd.uniform(3, top * (0.9 if snag else 0.35))
        ang = rnd.uniform(0, math.pi * 2)
        d = (math.cos(ang), rnd.uniform(-0.5, 0.1), math.sin(ang))
        idx = min(int((y + 1.5) / (top + 1.5) * steps), steps)
        start = add(pts[idx], (0, y - pts[idx][1], 0))
        path = bent_path(start, d, rnd.uniform(1.5, 4 if snag else 3), 3, 0.25, rnd)
        tube(trunk, path, [0.22, 0.15, 0.09, 0.03], 5, T["bark_gray"], noise=0.1, seed=seed + 50 + k, cap_start=False)
    meshes = [trunk]
    if snag:
        return meshes

    foliage = Mesh(name + "_Foliage", smooth=False, tex_scale=0.35)
    tiers = rnd.randint(9, 12)
    y0 = height * 0.24
    for k in range(tiers):
        t = k / (tiers - 1)
        y_top = y0 + (height - y0) * t ** 0.92
        R = height * 0.25 * (1 - t) ** 0.8 + 1.0
        drop = R * 0.55 + 1.2
        center = (lean[0] * y_top + rnd.uniform(-0.3, 0.3), 0, lean[2] * y_top + rnd.uniform(-0.3, 0.3))
        axis_top = (center[0], y_top + 0.5, center[2])
        n = max(9, int(R * 2.6)) | 1
        off = rnd.uniform(0, math.pi)
        tile = T["needles_dark"] if t < 0.55 or rnd.random() < 0.3 else T["needles_mid"]
        mid, outer = [], []
        for j in range(n):
            ang = off + 2 * math.pi * j / n
            spike = 1.0 if j % 2 == 0 else 0.72
            r = R * spike * rnd.uniform(0.85, 1.15)
            outer.append((center[0] + math.cos(ang) * r, y_top - drop * rnd.uniform(0.8, 1.05) * (0.8 + 0.2 * spike), center[2] + math.sin(ang) * r))
            rm = R * 0.5 * rnd.uniform(0.9, 1.1)
            mid.append((center[0] + math.cos(ang) * rm, y_top - drop * 0.32, center[2] + math.sin(ang) * rm))
        below = (center[0], y_top - drop * 1.4, center[2])
        above = (center[0], y_top + drop * 3, center[2])
        under = (center[0], y_top - drop * 0.62, center[2])
        for j in range(n):
            k2 = (j + 1) % n
            tri_out(foliage, axis_top, mid[j], mid[k2], below, tile)
            tri_out(foliage, mid[j], outer[j], outer[k2], below, tile)
            tri_out(foliage, mid[j], outer[k2], mid[k2], below, tile)
            tri_out(foliage, outer[j], outer[k2], under, above, T["needles_dark"])
        # secondo strato sfalsato di "rami" a punta per dare volume
        if t < 0.85:
            for j in range(n):
                ang = off + 2 * math.pi * (j + 0.5) / n
                d = (math.cos(ang), 0, math.sin(ang))
                root = (center[0] + d[0] * R * 0.3, y_top - drop * 0.45, center[2] + d[2] * R * 0.3)
                side = (-d[2] * R * 0.22, 0, d[0] * R * 0.22)
                tipp = (center[0] + d[0] * R * rnd.uniform(1.0, 1.2), y_top - drop * rnd.uniform(1.0, 1.3), center[2] + d[2] * R * rnd.uniform(1.0, 1.2))
                l = add(lerp(root, tipp, 0.45), add(side, (0, 0.25, 0)))
                r = add(lerp(root, tipp, 0.45), add(mul(side, -1), (0, 0.25, 0)))
                tri_out(foliage, root, l, tipp, below, T["needles_dark"])
                tri_out(foliage, root, tipp, r, below, T["needles_dark"])
                tri_out(foliage, l, r, tipp, above, T["needles_dark"])
                tri_out(foliage, root, r, l, above, T["needles_dark"])
    tip = (lean[0] * height, height + 1.5, lean[2] * height)
    tube(foliage, [(tip[0], height - 0.5, tip[2]), tip], [0.35, 0.02], 5, T["needles_mid"], cap_end=False)
    meshes.append(foliage)
    return meshes


def branch(mesh, start, direction, length_, radius, depth, rnd, tile, tips, moss=None):
    steps = 4
    path = bent_path(start, direction, length_, steps, 0.35, rnd, upward=0.05)
    radii = [radius * (1 - 0.7 * i / steps) for i in range(steps + 1)]
    tube(mesh, path, radii, max(4, 8 - depth * 2), tile, noise=0.12, seed=rnd.randint(0, 10 ** 6), cap_start=False)
    if depth >= 3 or radius < 0.08:
        tips.append(path[-1])
        if moss is not None and rnd.random() < 0.6:
            hang = path[-1]
            tube(moss, [hang, add(hang, (0, -rnd.uniform(1, 2.5), 0))], [0.09, 0.02], 4, T["moss"], cap_end=False)
        return
    for _ in range(rnd.randint(2, 3)):
        t = rnd.uniform(0.45, 0.95)
        idx = int(t * steps)
        p = lerp(path[idx], path[min(idx + 1, steps)], t * steps - idx)
        d = norm(add(sub(path[-1], path[0]), (0, 0, 0)))
        axis = norm(cross(d, (rnd.uniform(-1, 1), 0.1, rnd.uniform(-1, 1))))
        nd = norm(add(rotate(d, axis, rnd.uniform(0.4, 1.0)), (0, 0.15, 0)))
        branch(mesh, p, nd, length_ * rnd.uniform(0.55, 0.75), radii[idx] * 0.65, depth + 1, rnd, tile, tips, moss)


def dead_tree(name, seed):
    rnd = random.Random(seed)
    mesh = Mesh(name, smooth=True, tex_scale=0.35)
    moss = Mesh(name + "_tmp", smooth=False)
    tips = []
    d = norm((rnd.uniform(-0.25, 0.25), 1, rnd.uniform(-0.25, 0.25)))
    branch(mesh, (0, -1.5, 0), d, rnd.uniform(13, 18), 1.45, 0, rnd, T["bark_gray"], tips, moss)
    for k in range(4):
        ang = k / 4 * math.pi * 2 + rnd.uniform(-0.4, 0.4)
        path = bent_path((math.cos(ang) * 0.5, 0.5, math.sin(ang) * 0.5), (math.cos(ang), -0.3, math.sin(ang)), 3, 3, 0.2, rnd)
        tube(mesh, path, [0.5, 0.3, 0.15, 0.04], 6, T["bark_gray"], noise=0.15, seed=seed + k)
    mesh.merge(moss)
    return [mesh]


def broadleaf(name, seed):
    rnd = random.Random(seed)
    trunk = Mesh(name + "_Trunk", smooth=True, tex_scale=0.35)
    leaves = Mesh(name + "_Leaves", smooth=False, tex_scale=0.4)
    tips = []
    tile = T["bark_birch"] if rnd.random() < 0.5 else T["bark_pine"]
    d = norm((rnd.uniform(-0.1, 0.1), 1, rnd.uniform(-0.1, 0.1)))
    branch(trunk, (0, -1.5, 0), d, rnd.uniform(11, 14), 1.0, 1, rnd, tile, tips)
    for i, p in enumerate(tips):
        s = rnd.uniform(2.2, 3.8)
        blob(leaves, p, (s, s * 0.8, s), lambda n: T["leaves"] if n[1] > -0.2 else T["needles_dark"], noise=0.45, subdiv=1, seed=seed * 31 + i)
    return [trunk, leaves]


# --------------------------------------------------------------------------------------------
# Sottobosco e rocce


def bush(name, seed):
    rnd = random.Random(seed)
    mesh = Mesh(name, smooth=False, tex_scale=0.5)
    for i in range(rnd.randint(4, 6)):
        s = rnd.uniform(1.0, 1.9)
        c = (rnd.uniform(-1.3, 1.3), s * 0.55, rnd.uniform(-1.3, 1.3))
        tile = rnd.choice([T["leaves"], T["needles_mid"], T["fern"]])
        blob(mesh, c, (s, s * 0.75, s), tile, noise=0.5, subdiv=1, seed=seed * 13 + i, flatten_below=-0.3)
    return [mesh]


def fern(name, seed):
    rnd = random.Random(seed)
    mesh = Mesh(name, smooth=False, tex_scale=0.6)
    for f in range(rnd.randint(8, 12)):
        ang = f / 10 * math.pi * 2 + rnd.uniform(-0.3, 0.3)
        out = (math.cos(ang), 0, math.sin(ang))
        side = (-out[2], 0, out[0])
        length_ = rnd.uniform(2.2, 3.4)
        rise = rnd.uniform(1.0, 1.8)
        prev = (0, 0.1, 0)
        steps = 7
        for s in range(1, steps + 1):
            t = s / steps
            p = add(mul(out, length_ * t), (0, 0.1 + rise * math.sin(t * math.pi * 0.85), 0))
            w = 0.55 * math.sin(t * math.pi) + 0.05
            l = add(lerp(prev, p, 0.5), mul(side, w))
            r = add(lerp(prev, p, 0.5), mul(side, -w))
            l = add(l, (0, -0.15, 0))
            r = add(r, (0, -0.15, 0))
            two_sided(mesh, prev, l, p, T["fern"])
            two_sided(mesh, prev, p, r, T["fern"])
            prev = p
    return [mesh]


def reeds(name, seed):
    rnd = random.Random(seed)
    mesh = Mesh(name, smooth=False, tex_scale=0.6)
    for b in range(rnd.randint(14, 22)):
        x, z = rnd.uniform(-1.2, 1.2), rnd.uniform(-1.2, 1.2)
        h = rnd.uniform(2.5, 5)
        lean = (rnd.uniform(-0.4, 0.4), 0, rnd.uniform(-0.4, 0.4))
        w = rnd.uniform(0.08, 0.14)
        base_l, base_r = (x - w, 0, z), (x + w, 0, z)
        mid = add((x, h * 0.6, z), mul(lean, 0.5))
        tip = add((x, h, z), lean)
        two_sided(mesh, base_l, base_r, mid, T["fern"])
        two_sided(mesh, mid, add(mid, (w * 0.6, 0, 0)), tip, T["fern"])
        if rnd.random() < 0.25:
            tube(mesh, [add(mid, mul(lean, 0.3)), add(mid, add((0, 0.7, 0), mul(lean, 0.3)))], [0.12, 0.12], 5, T["bark_pine"])
    return [mesh]


def rock(name, seed, scale):
    mesh = Mesh(name, smooth=True, tex_scale=0.2)
    blob(mesh, (0, scale[1] * 0.35, 0), scale, moss_on_top(T["rock"], 0.6), noise=0.45, subdiv=2, seed=seed, flatten_below=-scale[1] * 0.2)
    return [mesh]


def log(name, seed):
    rnd = random.Random(seed)
    mesh = Mesh(name, smooth=True, tex_scale=0.3)
    L = rnd.uniform(9, 13)
    pts = [(-L / 2 + L * i / 8, 0.9 + math.sin(i * 0.7) * 0.15, math.sin(i * 0.5) * 0.3) for i in range(9)]
    tube(mesh, pts, [1.0 - i * 0.04 for i in range(9)], 12, moss_on_top(T["bark_pine"], 0.5), noise=0.08, seed=seed,
         end_tile=T["wood_cut"])
    for k in range(4):
        p = pts[rnd.randint(1, 7)]
        d = (rnd.uniform(-0.3, 0.3), rnd.uniform(0.2, 1), rnd.choice([-1, 1]))
        tube(mesh, bent_path(p, d, rnd.uniform(1, 2.2), 2, 0.3, rnd), [0.25, 0.15, 0.05], 5, T["bark_gray"], cap_start=False)
    return [mesh]


def stump(name, seed):
    rnd = random.Random(seed)
    mesh = Mesh(name, smooth=True, tex_scale=0.3)
    tube(mesh, [(0, -1, 0), (0, 0.6, 0), (0, 1.6, 0)], [1.6, 1.3, 1.15], 12, T["bark_pine"], noise=0.08, seed=seed,
         end_tile=T["wood_cut"], ring_jitter=lambda i, j: (0, rnd.uniform(-0.25, 0.25) if i == 2 else 0, 0))
    for k in range(5):
        ang = k / 5 * math.pi * 2
        path = bent_path((math.cos(ang) * 0.9, 0.3, math.sin(ang) * 0.9), (math.cos(ang), -0.4, math.sin(ang)), 2.2, 3, 0.15, rnd)
        tube(mesh, path, [0.45, 0.3, 0.15, 0.04], 6, T["bark_pine"], noise=0.1, seed=seed + k)
    return [mesh]


def mushrooms(name, seed):
    rnd = random.Random(seed)
    mesh = Mesh(name, smooth=True, tex_scale=1.2)
    for i in range(rnd.randint(4, 7)):
        x, z = rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8)
        h = rnd.uniform(0.3, 0.8)
        cylinder(mesh, (x, 0, z), (x, h, z), 0.06, 0.05, 6, T["bark_birch"], caps=False)
        r = rnd.uniform(0.15, 0.35)
        blob(mesh, (x, h, z), (r, r * 0.45, r), T["skin"], noise=0.1, subdiv=1, seed=seed + i, flatten_below=-r * 0.1)
    return [mesh]


# --------------------------------------------------------------------------------------------
# Telecamere (fronte = -Z, origine al centro del corpo)


def cam_tripod():
    mesh = Mesh("Cam_Tripod", smooth=False, tex_scale=1.0)
    cylinder(mesh, (0, 0, 0), (0, -1.0, 0), 0.08, 0.08, 8, T["metal"])
    cylinder(mesh, (0, 0.05, 0), (0, -0.25, 0), 0.25, 0.22, 10, T["plastic"])
    for k in range(3):
        ang = k / 3 * math.pi * 2 + math.pi / 2
        foot = (math.cos(ang) * 1.4, -3.75, math.sin(ang) * 1.4)
        knee = lerp((0, -0.3, 0), foot, 0.45)
        cylinder(mesh, (0, -0.3, 0), knee, 0.07, 0.065, 6, T["metal"])
        cylinder(mesh, knee, foot, 0.05, 0.045, 6, T["metal"])
        rounded_box(mesh, knee, (0.09, 0.14, 0.09), T["plastic"], seg=4)
        rounded_box(mesh, foot, (0.08, 0.05, 0.08), T["rubber"], seg=4)
        cylinder(mesh, (0, -1.0, 0), lerp((0, -1.0, 0), knee, 0.8), 0.025, 0.025, 4, T["metal"], caps=False)
    return [mesh]


def _lens(mesh, z_front, radius):
    cylinder(mesh, (0, 0, -0.6), (0, 0, z_front + 0.2), radius, radius, 14, T["plastic"])
    cylinder(mesh, (0, 0, z_front + 0.2), (0, 0, z_front), radius, radius * 1.18, 14, T["rubber"], end_tile=T["plastic"])


def cam_body():
    mesh = Mesh("Cam_Body", smooth=True, tex_scale=1.2)
    rounded_box(mesh, (0, 0, 0), (0.55, 0.42, 0.75), T["plastic"], sharp=0.25)
    _lens(mesh, -1.15, 0.3)
    tube(mesh, [(0, 0.42, 0.45), (0, 0.72, 0.3), (0, 0.72, -0.3), (0, 0.42, -0.45)], [0.06] * 4, 6, T["rubber"])
    rounded_box(mesh, (0.56, 0, 0.2), (0.04, 0.2, 0.25), T["metal"], seg=4)
    return [mesh]


def cam_ir():
    mesh = Mesh("Cam_IR", smooth=True, tex_scale=1.2)
    rounded_box(mesh, (0, 0, 0.1), (0.5, 0.45, 0.7), T["camo"], sharp=0.3)
    cylinder(mesh, (0, 0, -0.55), (0, 0, -0.72), 0.43, 0.43, 18, T["plastic"])
    _lens(mesh, -1.0, 0.22)
    rounded_box(mesh, (0, 0.5, -0.1), (0.46, 0.035, 0.52), T["plastic"], seg=4)
    return [mesh]


def cam_motor():
    mesh = Mesh("Cam_Motor", smooth=True, tex_scale=1.2)
    cylinder(mesh, (0, -0.95, 0), (0, -0.6, 0), 0.55, 0.5, 16, T["metal"])
    for x in (-0.55, 0.55):
        rounded_box(mesh, (x, -0.25, 0), (0.07, 0.45, 0.18), T["metal"], seg=4)
    blob(mesh, (0, 0, 0), (0.48, 0.48, 0.55), T["plastic"], noise=0.0, subdiv=2)
    _lens(mesh, -0.95, 0.22)
    cylinder(mesh, (0.3, 0.35, 0.2), (0.3, 1.1, 0.2), 0.03, 0.02, 5, T["rubber"])
    return [mesh]


def cam_trap():
    mesh = Mesh("Cam_Trap", smooth=True, tex_scale=1.0)
    rounded_box(mesh, (0, 0, 0), (0.48, 0.68, 0.32), T["camo"], sharp=0.3)
    rounded_box(mesh, (0, 0.35, -0.33), (0.3, 0.18, 0.03), T["plastic"], seg=6)
    blob(mesh, (0, -0.28, -0.32), (0.13, 0.13, 0.08), T["plastic"], noise=0.0, subdiv=1)
    cylinder(mesh, (0, 0.02, -0.3), (0, 0.02, -0.45), 0.13, 0.15, 12, T["plastic"])
    rounded_box(mesh, (0, 0, 0.35), (0.5, 0.08, 0.05), T["rubber"], seg=4)
    return [mesh]


def cam_stake():
    mesh = Mesh("Cam_Stake", smooth=True, tex_scale=0.6)
    rnd = random.Random(5)
    tube(mesh, [(0, 0.6, 0.45), (0, -1, 0.45), (0, -3.6, 0.45)], [0.18, 0.2, 0.16], 7, T["wood_warm"], noise=0.08, seed=3,
         end_tile=T["wood_cut"], ring_jitter=lambda i, j: (0, rnd.uniform(-0.1, 0.1) if i == 0 else 0, 0))
    return [mesh]


# --------------------------------------------------------------------------------------------
# Attrezzi (origine = impugnatura, fronte = -Z)


def tool_torch():
    mesh = Mesh("Tool_Torch", smooth=True, tex_scale=2.0)
    cylinder(mesh, (0, 0, 0.75), (0, 0, -0.45), 0.16, 0.16, 14, T["metal"], end_tile=T["rubber"])
    for k in range(5):
        z = 0.5 - k * 0.18
        cylinder(mesh, (0, 0, z), (0, 0, z - 0.08), 0.175, 0.175, 14, T["rubber"])
    tube(mesh, [(0, 0, -0.45), (0, 0, -0.6), (0, 0, -0.85)], [0.17, 0.2, 0.29], 16, T["metal"], cap_start=False, end_tile=T["plastic"])
    rounded_box(mesh, (0, 0.17, 0.05), (0.06, 0.04, 0.1), T["rubber"], seg=4)
    return [mesh]


def tool_rifle():
    mesh = Mesh("Tool_Rifle", smooth=True, tex_scale=1.2)
    # calcio in legno
    tube(mesh, [(0, 0.05, 0.35), (0, 0.0, 0.9), (0, -0.12, 1.5), (0, -0.2, 2.0)], [0.12, 0.13, 0.17, 0.2], 8, T["wood_warm"],
         end_tile=T["rubber"])
    rounded_box(mesh, (0, -0.05, 1.7), (0.09, 0.28, 0.32), T["wood_warm"], sharp=0.4)
    # carcassa e impugnatura
    rounded_box(mesh, (0, 0.12, -0.1), (0.1, 0.13, 0.55), T["metal"], sharp=0.2)
    tube(mesh, [(0, 0.0, 0.2), (0, -0.3, 0.3), (0, -0.55, 0.38)], [0.07, 0.075, 0.07], 8, T["rubber"])
    tube(mesh, [(0, -0.02, -0.05), (0, -0.22, -0.02), (0, -0.25, 0.2), (0, -0.05, 0.25)], [0.018] * 4, 5, T["metal"], cap_start=False, cap_end=False)
    # canna e bombola CO2
    cylinder(mesh, (0, 0.15, -0.6), (0, 0.15, -2.6), 0.06, 0.055, 10, T["metal"], end_tile=T["plastic"])
    cylinder(mesh, (0, 0.15, -2.45), (0, 0.15, -2.62), 0.085, 0.085, 10, T["metal"])
    cylinder(mesh, (0, -0.03, -0.5), (0, -0.03, -1.55), 0.08, 0.08, 10, T["metal"], end_tile=T["metal"])
    # mirino ottico
    tube(mesh, [(0, 0.42, 0.35), (0, 0.42, 0.25), (0, 0.42, -0.45), (0, 0.42, -0.6)], [0.11, 0.075, 0.075, 0.12], 12, T["plastic"])
    for z in (0.1, -0.3):
        rounded_box(mesh, (0, 0.3, z), (0.05, 0.08, 0.05), T["metal"], seg=4)
    rounded_box(mesh, (0, 0.24, -2.4), (0.02, 0.06, 0.03), T["metal"], seg=4)
    return [mesh]


def tool_tablet():
    mesh = Mesh("Tool_Tablet", smooth=True, tex_scale=1.5)
    rounded_box(mesh, (0, 0, 0), (0.8, 0.55, 0.06), T["plastic"], sharp=0.15)
    for x in (-0.8, 0.8):
        for y in (-0.55, 0.55):
            rounded_box(mesh, (x * 0.97, y * 0.95, 0), (0.12, 0.12, 0.09), T["rubber"], sharp=0.4, seg=6)
    rounded_box(mesh, (0, -0.4, 0.08), (0.3, 0.06, 0.03), T["rubber"], seg=4)
    return [mesh]


# --------------------------------------------------------------------------------------------
# The Rake: arti separati per l'animazione (ogni arto pende lungo -Y dalla sua giuntura)


def rake_torso():
    mesh = Mesh("Rake_Torso", smooth=True, tex_scale=0.9)
    # colonna curva in avanti: dal bacino (origine) al torace
    spine = [(0, -0.2, 0.1), (0, 0.5, 0.05), (0, 1.2, -0.15), (0, 1.9, -0.45), (0, 2.5, -0.85), (0, 2.85, -1.15)]
    radii = [0.42, 0.33, 0.38, 0.5, 0.55, 0.4]
    tube(mesh, spine, radii, 14, T["skin"], noise=0.04, seed=11,
         ring_jitter=lambda i, j: (0, 0, 0))
    # costole sporgenti
    for k in range(5):
        y = 1.35 + k * 0.28
        z = -0.25 - k * 0.15
        for side in (-1, 1):
            path = [(side * 0.1, y, z - 0.4), (side * 0.38, y - 0.06, z - 0.22), (side * 0.47, y - 0.14, z + 0.05)]
            tube(mesh, path, [0.06, 0.07, 0.05], 5, T["skin"], cap_start=False, cap_end=False)
    # vertebre sul dorso
    for k in range(8):
        t = k / 7
        p = lerp(spine[1], spine[5], t)
        blob(mesh, add(p, (0, 0, 0.42 + 0.05 * math.sin(t * 3))), (0.09, 0.07, 0.09), T["skin"], noise=0.0, subdiv=1)
    # scapole e clavicole
    for side in (-1, 1):
        blob(mesh, (side * 0.45, 2.55, -0.55), (0.32, 0.2, 0.14), T["skin"], noise=0.1, subdiv=1, seed=side + 4)
        tube(mesh, [(0, 2.75, -1.2), (side * 0.85, 2.7, -1.05)], [0.07, 0.08], 5, T["skin"])
    return [mesh]


def rake_head():
    mesh = Mesh("Rake_Head", smooth=True, tex_scale=1.0)
    # cranio allungato e collo sottile; origine alla base del collo
    tube(mesh, [(0, -0.1, 0.1), (0, 0.25, -0.15), (0, 0.45, -0.4)], [0.17, 0.15, 0.17], 8, T["skin"], cap_start=False)
    blob(mesh, (0, 0.8, -0.45), (0.36, 0.42, 0.6), T["skin"], noise=0.15, subdiv=2, seed=21)
    blob(mesh, (0, 0.95, -0.15), (0.3, 0.3, 0.38), T["skin"], noise=0.1, subdiv=1, seed=24)
    # muso e mascella
    blob(mesh, (0, 0.62, -1.0), (0.27, 0.26, 0.4), T["skin"], noise=0.08, subdiv=2, seed=22)
    blob(mesh, (0, 0.38, -0.95), (0.27, 0.12, 0.35), T["skin"], noise=0.05, subdiv=1, seed=23)
    # denti
    for k in range(9):
        a = -0.8 + k * 0.2
        x, z = math.sin(a) * 0.24, -1.05 - math.cos(a) * 0.22
        two_sided(mesh, (x - 0.035, 0.52, z), (x + 0.035, 0.52, z), (x, 0.4, z - 0.01), T["bark_birch"])
        two_sided(mesh, (x - 0.03, 0.42, z + 0.02), (x + 0.03, 0.42, z + 0.02), (x, 0.52, z), T["bark_birch"])
    # arcate sopraccigliari
    for side in (-1, 1):
        blob(mesh, (side * 0.2, 0.98, -0.98), (0.17, 0.07, 0.1), T["skin"], noise=0.0, subdiv=1)
    return [mesh]


def rake_upper_arm():
    mesh = Mesh("Rake_UpperArm", smooth=True, tex_scale=1.2)
    tube(mesh, [(0, 0.1, 0), (0, -0.6, 0.02), (0, -1.6, 0.05), (0, -2.35, 0)], [0.2, 0.16, 0.12, 0.15], 9, T["skin"], noise=0.05, seed=31)
    blob(mesh, (0, -2.35, 0.05), (0.15, 0.15, 0.17), T["skin"], noise=0.0, subdiv=1)
    return [mesh]


def rake_forearm():
    mesh = Mesh("Rake_Forearm", smooth=True, tex_scale=1.2)
    tube(mesh, [(0, 0, 0), (0, -1.0, -0.03), (0, -2.3, 0)], [0.13, 0.11, 0.1], 8, T["skin"], noise=0.05, seed=41)
    blob(mesh, (0, -2.45, 0), (0.17, 0.2, 0.09), T["skin"], noise=0.1, subdiv=1, seed=42)
    for f in range(4):
        x = -0.13 + f * 0.087
        knuckle = (x, -2.6, -0.02)
        mid = (x * 1.3, -3.25 - 0.1 * (f % 2), -0.18)
        tip = (x * 1.5, -3.85 - 0.15 * (f % 2), -0.45)
        tube(mesh, [knuckle, mid], [0.04, 0.032], 5, T["skin"], cap_start=False)
        tube(mesh, [mid, tip], [0.032, 0.002], 5, T["rubber"], cap_start=False, cap_end=False)
    return [mesh]


def rake_thigh():
    mesh = Mesh("Rake_Thigh", smooth=True, tex_scale=1.2)
    tube(mesh, [(0, 0.1, 0), (0, -0.8, -0.05), (0, -1.9, 0)], [0.26, 0.2, 0.15], 9, T["skin"], noise=0.05, seed=51)
    blob(mesh, (0, -1.95, -0.05), (0.17, 0.17, 0.19), T["skin"], noise=0.0, subdiv=1)
    return [mesh]


def rake_shin():
    mesh = Mesh("Rake_Shin", smooth=True, tex_scale=1.2)
    tube(mesh, [(0, 0, 0), (0, -1.0, 0.04), (0, -1.95, 0.0)], [0.14, 0.11, 0.09], 8, T["skin"], noise=0.05, seed=61)
    blob(mesh, (0, -2.05, -0.15), (0.15, 0.1, 0.35), T["skin"], noise=0.1, subdiv=1, seed=62)
    for f in range(3):
        x = -0.1 + f * 0.1
        tube(mesh, [(x, -2.1, -0.4), (x * 1.4, -2.15, -0.75)], [0.045, 0.03], 5, T["skin"], cap_start=False)
        tube(mesh, [(x * 1.4, -2.15, -0.75), (x * 1.6, -2.2, -1.0)], [0.03, 0.002], 5, T["rubber"], cap_start=False, cap_end=False)
    return [mesh]


def all_models():
    out = []
    out += pine("Pine1", 1, 30)
    out += pine("Pine2", 2, 36)
    out += pine("Pine3", 3, 25)
    out += pine("Pine4", 4, 41)
    out += pine("Snag1", 5, 26, snag=True)
    out += dead_tree("Dead1", 11)
    out += dead_tree("Dead2", 12)
    out += dead_tree("Dead3", 13)
    out += broadleaf("Broad1", 21)
    out += broadleaf("Broad2", 22)
    for i in range(3):
        out += bush("Bush%d" % (i + 1), 31 + i)
    for i in range(2):
        out += fern("Fern%d" % (i + 1), 41 + i)
    out += reeds("Reeds1", 51)
    out += rock("Rock1", 61, (2.2, 1.6, 2.0))
    out += rock("Rock2", 62, (3.5, 2.4, 2.8))
    out += rock("Rock3", 63, (1.2, 0.9, 1.4))
    out += rock("Boulder1", 64, (7, 5, 6))
    out += log("Log1", 71)
    out += stump("Stump1", 81)
    out += mushrooms("Mushrooms1", 91)
    out += cam_tripod() + cam_body() + cam_ir() + cam_motor() + cam_trap() + cam_stake()
    out += tool_torch() + tool_rifle() + tool_tablet()
    out += rake_torso() + rake_head() + rake_upper_arm() + rake_forearm() + rake_thigh() + rake_shin()
    return out
