"""Primitive geometriche in coordinate Roblox (Y in alto, fronte = -Z)."""
import math
import random

from gltf import Mesh


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def norm(a):
    l = length(a) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def rotate(v, axis, angle):
    """Rotazione di Rodrigues."""
    axis = norm(axis)
    c, s = math.cos(angle), math.sin(angle)
    return add(add(mul(v, c), mul(cross(axis, v), s)), mul(axis, dot(axis, v) * (1 - c)))


def tri_out(mesh, a, b, c, ref, tile):
    """Triangolo orientato in modo che la normale punti lontano da ref."""
    n = cross(sub(b, a), sub(c, a))
    centroid = mul(add(add(a, b), c), 1 / 3)
    if dot(n, sub(centroid, ref)) < 0:
        b, c = c, b
    mesh.tri(a, b, c, tile)


def two_sided(mesh, a, b, c, tile):
    mesh.tri(a, b, c, tile)
    mesh.tri(a, c, b, tile)


def _tile_for(tile, normal):
    return tile(normal) if callable(tile) else tile


def tube(mesh, points, radii, segments, tile, noise=0.0, seed=0, cap_start=True, cap_end=True, end_tile=None, ring_jitter=None):
    """Tubo lungo una polilinea con raggi variabili. tile può essere una funzione della normale."""
    rnd = random.Random(seed)
    n = len(points)
    tangents = []
    for i in range(n):
        a = points[max(i - 1, 0)]
        b = points[min(i + 1, n - 1)]
        tangents.append(norm(sub(b, a)))
    up = (0, 1, 0) if abs(tangents[0][1]) < 0.9 else (1, 0, 0)
    normal = norm(cross(tangents[0], up))
    rings = []
    for i in range(n):
        t = tangents[i]
        normal = norm(sub(normal, mul(t, dot(normal, t))))
        binormal = cross(t, normal)
        ring = []
        for j in range(segments):
            ang = 2 * math.pi * j / segments
            r = radii[i] * (1 + noise * (rnd.random() * 2 - 1))
            offset = add(mul(normal, math.cos(ang) * r), mul(binormal, math.sin(ang) * r))
            p = add(points[i], offset)
            if ring_jitter:
                p = add(p, ring_jitter(i, j))
            ring.append(p)
        rings.append(ring)
    for i in range(n - 1):
        ref = lerp(points[i], points[i + 1], 0.5)
        for j in range(segments):
            k = (j + 1) % segments
            a, b, c, d = rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]
            nrm = norm(cross(sub(b, a), sub(d, a)))
            tl = _tile_for(tile, nrm)
            tri_out(mesh, a, b, c, ref, tl)
            tri_out(mesh, a, c, d, ref, tl)
    caps = []
    if cap_start and radii[0] > 0.01:
        caps.append((0, -1))
    if cap_end and radii[-1] > 0.01:
        caps.append((n - 1, 1))
    for idx, sign in caps:
        center = points[idx]
        ref = sub(center, mul(tangents[idx], sign))
        tl = end_tile if end_tile is not None else _tile_for(tile, mul(tangents[idx], sign))
        ring = rings[idx]
        for j in range(segments):
            tri_out(mesh, center, ring[j], ring[(j + 1) % segments], ref, tl)
    return rings


def bent_path(start, direction, total, steps, bend, rnd, upward=0.0):
    """Polilinea che parte da start e cambia direzione casualmente."""
    pts = [start]
    d = norm(direction)
    seg = total / steps
    p = start
    for _ in range(steps):
        d = norm(add(add(d, (rnd.uniform(-bend, bend), rnd.uniform(-bend, bend) + upward, rnd.uniform(-bend, bend))), (0, 0, 0)))
        p = add(p, mul(d, seg))
        pts.append(p)
    return pts


def icosphere(subdiv):
    t = (1 + 5 ** 0.5) / 2
    verts = [norm(v) for v in [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
             (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(subdiv):
        cache = {}

        def mid(i, j):
            key = (min(i, j), max(i, j))
            if key not in cache:
                verts.append(norm(lerp(verts[i], verts[j], 0.5)))
                cache[key] = len(verts) - 1
            return cache[key]

        new = []
        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            new += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = new
    return verts, faces


def blob(mesh, center, scale, tile, noise=0.25, subdiv=2, seed=0, flatten_below=None):
    """Sfera deformata (rocce, cespugli, chiome). tile può dipendere dalla normale."""
    rnd = random.Random(seed)
    verts, faces = icosphere(subdiv)
    bumps = [(norm((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))), rnd.uniform(0.3, 1.0)) for _ in range(6)]
    pts = []
    for v in verts:
        k = 1 + noise * sum(max(0.0, dot(v, d)) ** 3 * w for d, w in bumps) - noise * 0.4 + noise * 0.25 * (rnd.random() - 0.5)
        p = (v[0] * scale[0] * k, v[1] * scale[1] * k, v[2] * scale[2] * k)
        if flatten_below is not None and p[1] < flatten_below:
            p = (p[0], flatten_below + (p[1] - flatten_below) * 0.15, p[2])
        pts.append(add(center, p))
    for a, b, c in faces:
        pa, pb, pc = pts[a], pts[b], pts[c]
        nrm = norm(cross(sub(pb, pa), sub(pc, pa)))
        tri_out(mesh, pa, pb, pc, center, _tile_for(tile, nrm))


def rounded_box(mesh, center, half, tile, sharp=0.18, seg=10):
    """Superellissoide: scatola con spigoli arrotondati."""
    def f(w, m):
        return math.copysign(abs(math.cos(w)) ** m, math.cos(w))

    def g(w, m):
        return math.copysign(abs(math.sin(w)) ** m, math.sin(w))

    grid = []
    for i in range(seg + 1):
        lat = -math.pi / 2 + math.pi * i / seg
        row = []
        for j in range(seg * 2):
            lon = -math.pi + 2 * math.pi * j / (seg * 2)
            x = half[0] * f(lat, sharp) * f(lon, sharp)
            y = half[1] * g(lat, sharp)
            z = half[2] * f(lat, sharp) * g(lon, sharp)
            row.append(add(center, (x, y, z)))
        grid.append(row)
    for i in range(seg):
        for j in range(seg * 2):
            k = (j + 1) % (seg * 2)
            a, b, c, d = grid[i][j], grid[i][k], grid[i + 1][k], grid[i + 1][j]
            nrm = norm(cross(sub(b, a), sub(d, a)))
            tl = _tile_for(tile, nrm)
            tri_out(mesh, a, b, c, center, tl)
            tri_out(mesh, a, c, d, center, tl)


def cylinder(mesh, a, b, r1, r2, segments, tile, caps=True, end_tile=None):
    tube(mesh, [a, b], [r1, r2], segments, tile, cap_start=caps, cap_end=caps, end_tile=end_tile)
