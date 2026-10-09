"""Libreria SDF (signed distance field) per modellare forme morbide "da giocattolo".

Convenzioni: spazio Blender (Z in alto, il fronte del modello guarda verso -Y),
1 unita' = 1 stud Roblox. Ogni SDF conosce un box di ingombro conservativo,
usato per campionare la griglia del marching cubes.
"""
from __future__ import annotations

import math
from typing import Callable, Iterable, Sequence

import numpy as np

Vec = Sequence[float]


def _v(x) -> np.ndarray:
    return np.asarray(x, dtype=np.float32)


def _len(p: np.ndarray) -> np.ndarray:
    return np.sqrt(np.einsum("ij,ij->i", p, p))


def smin(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    return -smin(-a, -b, k)


def rot_matrix(axis: Vec, deg: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=np.float64)
    axis = axis / np.linalg.norm(axis)
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    x, y, z = axis
    return np.array([
        [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
        [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
        [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
    ], dtype=np.float32)


def euler(rx: float = 0, ry: float = 0, rz: float = 0) -> np.ndarray:
    """Matrice di rotazione XYZ (gradi), come in Blender."""
    return rot_matrix((0, 0, 1), rz) @ rot_matrix((0, 1, 0), ry) @ rot_matrix((1, 0, 0), rx)


class SDF:
    def __init__(self, f: Callable[[np.ndarray], np.ndarray], lo: Vec, hi: Vec):
        self.f = f
        self.lo = np.asarray(lo, dtype=np.float32)
        self.hi = np.asarray(hi, dtype=np.float32)

    def __call__(self, p: np.ndarray) -> np.ndarray:
        return self.f(p)

    # ------------------------------------------------------------ booleane
    def union(self, *others: "SDF", k: float = 0.0) -> "SDF":
        return union(self, *others, k=k)

    def subtract(self, other: "SDF", k: float = 0.0) -> "SDF":
        a, b = self, other

        def f(p):
            return smax(a(p), -b(p), k)

        return SDF(f, a.lo, a.hi)

    def intersect(self, other: "SDF", k: float = 0.0) -> "SDF":
        a, b = self, other

        def f(p):
            return smax(a(p), b(p), k)

        return SDF(f, np.maximum(a.lo, b.lo), np.minimum(a.hi, b.hi))

    # ------------------------------------------------------------ trasformazioni
    def translate(self, v: Vec) -> "SDF":
        a, v = self, _v(v)
        return SDF(lambda p: a(p - v), a.lo + v, a.hi + v)

    def rotate(self, m: np.ndarray, pivot: Vec = (0, 0, 0)) -> "SDF":
        """Ruota la forma con la matrice m attorno al punto pivot."""
        a = self
        m = np.asarray(m, dtype=np.float32)
        piv = _v(pivot)
        inv = m.T

        def f(p):
            return a((p - piv) @ inv.T + piv)

        corners = np.array([[x, y, z] for x in (a.lo[0], a.hi[0]) for y in (a.lo[1], a.hi[1])
                            for z in (a.lo[2], a.hi[2])], dtype=np.float32)
        rc = (corners - piv) @ m.T + piv
        return SDF(f, rc.min(0), rc.max(0))

    def rot(self, rx: float = 0, ry: float = 0, rz: float = 0, pivot: Vec = (0, 0, 0)) -> "SDF":
        return self.rotate(euler(rx, ry, rz), pivot)

    def scale(self, s: float) -> "SDF":
        a = self
        return SDF(lambda p: a(p / s) * s, a.lo * s, a.hi * s)

    def offset(self, d: float) -> "SDF":
        """Gonfia (d>0) o sgonfia (d<0) la superficie."""
        a = self
        return SDF(lambda p: a(p) - d, a.lo - max(d, 0), a.hi + max(d, 0))

    def shell(self, t: float) -> "SDF":
        a = self
        return SDF(lambda p: np.abs(a(p)) - t, a.lo - t, a.hi + t)

    def mirror_x(self) -> "SDF":
        """Specchia la meta' x>0 sul lato x<0 (forme simmetriche)."""
        a = self

        def f(p):
            q = p.copy()
            q[:, 0] = np.abs(q[:, 0])
            return a(q)

        ext = max(abs(float(a.lo[0])), abs(float(a.hi[0])))
        return SDF(f, (-ext, a.lo[1], a.lo[2]), (ext, a.hi[1], a.hi[2]))

    def symmetric(self) -> "SDF":
        """Unione della forma e della sua copia specchiata su X."""
        return union(self, self.mirrored())

    def mirrored(self) -> "SDF":
        a = self

        def f(p):
            q = p.copy()
            q[:, 0] = -q[:, 0]
            return a(q)

        return SDF(f, (-a.hi[0], a.lo[1], a.lo[2]), (-a.lo[0], a.hi[1], a.hi[2]))

    def warp(self, fn: Callable[[np.ndarray], np.ndarray], pad: float = 0.0) -> "SDF":
        """Deforma lo spazio (fn mappa i punti). Non e' piu' una distanza esatta."""
        a = self
        return SDF(lambda p: a(fn(p)), a.lo - pad, a.hi + pad)

    def bounds_pad(self, pad: float) -> "SDF":
        return SDF(self.f, self.lo - pad, self.hi + pad)


def union(*shapes: SDF, k: float = 0.0) -> SDF:
    shapes = [s for s in shapes if s is not None]
    if len(shapes) == 1:
        return shapes[0]

    def f(p):
        d = shapes[0](p)
        for s in shapes[1:]:
            d = smin(d, s(p), k)
        return d

    lo = np.min([s.lo for s in shapes], axis=0) - k
    hi = np.max([s.hi for s in shapes], axis=0) + k
    return SDF(f, lo, hi)


# ---------------------------------------------------------------- primitive

def sphere(r: float, c: Vec = (0, 0, 0)) -> SDF:
    c = _v(c)
    return SDF(lambda p: _len(p - c) - r, c - r, c + r)


def ellipsoid(radii: Vec, c: Vec = (0, 0, 0)) -> SDF:
    r = _v(radii)
    c = _v(c)

    def f(p):
        q = p - c
        k0 = _len(q / r)
        k1 = _len(q / (r * r))
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)

    return SDF(f, c - r, c + r)


def box(half: Vec, c: Vec = (0, 0, 0), round: float = 0.0) -> SDF:
    b = _v(half) - round
    c = _v(c)

    def f(p):
        q = np.abs(p - c) - b
        outside = _len(np.maximum(q, 0.0))
        inside = np.minimum(np.max(q, axis=1), 0.0)
        return outside + inside - round

    h = _v(half)
    return SDF(f, c - h, c + h)


def capsule(a: Vec, b: Vec, r: float) -> SDF:
    return round_cone(a, b, r, r)


def round_cone(a: Vec, b: Vec, ra: float, rb: float) -> SDF:
    """Cono arrotondato fra i punti a (raggio ra) e b (raggio rb)."""
    a = _v(a)
    b = _v(b)
    ba = b - a
    l2 = float(ba @ ba)
    rr = ra - rb
    a2 = l2 - rr * rr
    il2 = 1.0 / max(l2, 1e-9)

    def f(p):
        pa = p - a
        y = pa @ ba
        z = y - l2
        xv = pa * l2 - np.outer(y, ba)
        x2 = np.einsum("ij,ij->i", xv, xv)
        y2 = y * y * l2
        z2 = z * z * l2
        k = np.sign(rr) * rr * rr * x2
        res = np.empty_like(y)
        m1 = np.sign(z) * a2 * z2 > k
        m2 = (~m1) & (np.sign(y) * a2 * y2 < k)
        m3 = ~(m1 | m2)
        res[m1] = np.sqrt(x2[m1] + z2[m1]) * il2 - rb
        res[m2] = np.sqrt(x2[m2] + y2[m2]) * il2 - ra
        res[m3] = (np.sqrt(x2[m3] * a2 * il2) + y[m3] * rr) * il2 - ra
        return res

    rmax = max(ra, rb)
    return SDF(f, np.minimum(a, b) - rmax, np.maximum(a, b) + rmax)


def cylinder(a: Vec, b: Vec, r: float, round: float = 0.0) -> SDF:
    """Cilindro fra i punti a e b, con bordi arrotondati opzionali."""
    a = _v(a)
    b = _v(b)
    ba = b - a
    baba = float(ba @ ba)
    rr = r - round

    def f(p):
        pa = p - a
        paba = pa @ ba
        xv = pa * baba - np.outer(paba, ba)
        x = _len(xv) - rr * baba
        y = np.abs(paba - baba * 0.5) - baba * 0.5
        x2 = x * x
        y2 = y * y * baba
        d = np.where(np.maximum(x, y) < 0.0, -np.minimum(x2, y2),
                     np.where(x > 0.0, x2, 0.0) + np.where(y > 0.0, y2, 0.0))
        return np.sign(d) * np.sqrt(np.abs(d)) / baba - round

    return SDF(f, np.minimum(a, b) - r, np.maximum(a, b) + r)


def torus(R: float, r: float, c: Vec = (0, 0, 0)) -> SDF:
    """Toro nel piano XY (asse Z)."""
    c = _v(c)

    def f(p):
        q = p - c
        qx = np.sqrt(q[:, 0] ** 2 + q[:, 1] ** 2) - R
        return np.sqrt(qx * qx + q[:, 2] ** 2) - r

    e = R + r
    return SDF(f, c - (e, e, r), c + (e, e, r))


def revolve(profile: Callable[[np.ndarray], np.ndarray], radius: float, z0: float, z1: float,
            c: Vec = (0, 0, 0)) -> SDF:
    """Solido di rivoluzione attorno a Z: profile(z) restituisce il raggio (>=0).

    La distanza e' approssimata (corretta vicino alla superficie) tramite il gradiente numerico.
    """
    c = _v(c)
    eps = 1e-3

    def g(rho, z):
        return rho - profile(z)

    def f(p):
        q = p - c
        rho = np.sqrt(q[:, 0] ** 2 + q[:, 1] ** 2)
        z = q[:, 2]
        zc = np.clip(z, z0, z1)
        val = g(rho, zc)
        dprof = (profile(np.clip(zc + eps, z0, z1)) - profile(np.clip(zc - eps, z0, z1))) / (2 * eps)
        lat = val / np.sqrt(1.0 + dprof * dprof)
        # fuori dall'intervallo in z: distanza dai "tappi"
        over = np.maximum(z0 - z, z - z1)
        return np.where(over > 0, np.sqrt(np.maximum(lat, 0) ** 2 + over ** 2), lat)

    return SDF(f, c + (-radius, -radius, z0), c + (radius, radius, z1))


def egg(radius: float, height: float, taper: float = 0.22, c: Vec = (0, 0, 0)) -> SDF:
    """Uovo con base in z=0 e punta in z=height (piu' stretto in alto)."""
    h = height

    def prof(z):
        t = np.clip(z / h, 0.0, 1.0)
        # profilo: ellisse deformata, piu' piena in basso
        u = 2.0 * t - 1.0
        base = np.sqrt(np.clip(1.0 - u * u, 0.0, 1.0))
        shape = 1.0 - taper * u
        return radius * base * shape

    return revolve(prof, radius * (1 + taper), 0.0, h, c)


def prism(poly: Sequence[Vec], z0: float, z1: float, round: float = 0.0) -> SDF:
    """Prisma con base poligonale 2D (in XY, ordine qualsiasi) tra z0 e z1."""
    pts = np.asarray(poly, dtype=np.float32)
    n = len(pts)

    def d2(px, py):
        d = np.full(px.shape, np.inf, dtype=np.float32)
        s = np.ones(px.shape, dtype=np.float32)
        for i in range(n):
            vi = pts[i]
            vj = pts[i - 1]
            ex, ey = vj[0] - vi[0], vj[1] - vi[1]
            wx, wy = px - vi[0], py - vi[1]
            t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey), 0.0, 1.0)
            bx, by = wx - ex * t, wy - ey * t
            d = np.minimum(d, bx * bx + by * by)
            c1 = py >= vi[1]
            c2 = py < vj[1]
            c3 = ex * wy > ey * wx
            flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
            s = np.where(flip, -s, s)
        return s * np.sqrt(d)

    zm = 0.5 * (z0 + z1)
    hz = 0.5 * (z1 - z0) - round

    def f(p):
        dxy = d2(p[:, 0], p[:, 1]) + round
        dz = np.abs(p[:, 2] - zm) - hz
        wx = np.maximum(dxy, 0)
        wy = np.maximum(dz, 0)
        return np.minimum(np.maximum(dxy, dz), 0) + np.sqrt(wx * wx + wy * wy) - round

    lo = (pts[:, 0].min(), pts[:, 1].min(), z0)
    hi = (pts[:, 0].max(), pts[:, 1].max(), z1)
    return SDF(f, lo, hi)


def star_points(n: int, r_out: float, r_in: float, rot_deg: float = 90) -> list[tuple[float, float]]:
    pts = []
    for i in range(n * 2):
        a = math.radians(rot_deg + i * 180.0 / n)
        r = r_out if i % 2 == 0 else r_in
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


def octahedron(s: float, c: Vec = (0, 0, 0)) -> SDF:
    c = _v(c)

    def f(p):
        q = np.abs(p - c)
        return (q.sum(axis=1) - s) * 0.57735027

    return SDF(f, c - s, c + s)


def tube(points: Sequence[Vec], radii: Sequence[float] | float, k: float = 0.0) -> SDF:
    """Catena di coni arrotondati lungo una polilinea (code, corna, fili)."""
    if isinstance(radii, (int, float)):
        radii = [float(radii)] * len(points)
    parts = [round_cone(points[i], points[i + 1], radii[i], radii[i + 1]) for i in range(len(points) - 1)]
    return union(*parts, k=k)


def bezier(p0: Vec, p1: Vec, p2: Vec, p3: Vec, n: int = 12) -> list[tuple[float, float, float]]:
    p0, p1, p2, p3 = map(np.asarray, (p0, p1, p2, p3))
    out = []
    for i in range(n + 1):
        t = i / n
        q = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3
        out.append(tuple(float(x) for x in q))
    return out


def plane(normal: Vec, d: float, lo: Vec, hi: Vec) -> SDF:
    n = _v(normal)
    n = n / np.linalg.norm(n)
    return SDF(lambda p: p @ n - d, lo, hi)


def halfspace_z(z: float, above: bool = True, lo: Vec = (-100, -100, -100), hi: Vec = (100, 100, 100)) -> SDF:
    """Semispazio: dentro se z > valore (above) o z < valore."""
    if above:
        return SDF(lambda p: z - p[:, 2], (lo[0], lo[1], z), hi)
    return SDF(lambda p: p[:, 2] - z, lo, (hi[0], hi[1], z))


def empty() -> SDF:
    return SDF(lambda p: np.full(len(p), 1e3, dtype=np.float32), (0, 0, 0), (0, 0, 0))


# ---------------------------------------------------------------- appoggio sulla superficie

def project(sdf: SDF, origin: Vec, direction: Vec, max_dist: float = 10.0):
    """Punto della superficie colpito andando da origin (interno) verso direction.

    Ritorna (punto, normale) come array numpy. Utile per appoggiare occhi, nasi, macchie.
    """
    o = np.asarray(origin, dtype=np.float64)
    d = np.asarray(direction, dtype=np.float64)
    d = d / np.linalg.norm(d)
    ts = np.linspace(0.0, max_dist, 2000)
    pts = (o[None, :] + ts[:, None] * d[None, :]).astype(np.float32)
    vals = sdf(pts)
    idx = np.nonzero(vals > 0)[0]
    if len(idx) == 0:
        raise ValueError("Nessuna superficie lungo il raggio")
    i = int(idx[0])
    lo_t, hi_t = ts[max(i - 1, 0)], ts[i]
    for _ in range(40):
        mid = 0.5 * (lo_t + hi_t)
        v = sdf((o + mid * d)[None, :].astype(np.float32))[0]
        if v > 0:
            hi_t = mid
        else:
            lo_t = mid
    p = o + 0.5 * (lo_t + hi_t) * d
    eps = 1e-3
    g = np.zeros(3)
    for ax in range(3):
        e = np.zeros(3)
        e[ax] = eps
        g[ax] = sdf((p + e)[None, :].astype(np.float32))[0] - sdf((p - e)[None, :].astype(np.float32))[0]
    n = g / max(np.linalg.norm(g), 1e-9)
    return p, n


def look_matrix(normal: Vec, up: Vec = (0, 0, 1)) -> np.ndarray:
    """Matrice che porta l'asse -Y locale sulla normale (per orientare dettagli sulla superficie)."""
    f = np.asarray(normal, dtype=np.float64)
    f = f / np.linalg.norm(f)
    u = np.asarray(up, dtype=np.float64)
    r = np.cross(f, u)
    if np.linalg.norm(r) < 1e-6:
        r = np.array([1.0, 0, 0])
    r = r / np.linalg.norm(r)
    u2 = np.cross(r, f)
    # colonne: asse X locale -> r, asse Y locale -> -f, asse Z locale -> u2
    return np.stack([r, -f, u2], axis=1).astype(np.float32)


def stick(shape: SDF, base: SDF, origin: Vec, direction: Vec, sink: float = 0.0, up: Vec = (0, 0, 1)) -> SDF:
    """Appoggia shape (modellata attorno all'origine, fronte verso -Y) sulla superficie di base.

    La forma viene orientata lungo la normale e affondata di 'sink' (positivo = dentro).
    """
    p, n = project(base, origin, direction)
    m = look_matrix(n, up)
    return shape.rotate(m).translate(p - n * sink)


class Frame:
    """Sistema di riferimento appoggiato a una superficie (asse -Y locale = normale uscente)."""

    def __init__(self, base: SDF, origin: Vec, direction: Vec, sink: float = 0.0, up: Vec = (0, 0, 1)):
        p, n = project(base, origin, direction)
        self.normal = n
        self.surface = p
        self.matrix = look_matrix(n, up)
        self.origin = p - n * sink

    def place(self, shape: SDF, offset: Vec = (0, 0, 0)) -> SDF:
        """Posiziona shape (coordinate locali: X destra, -Y fuori dalla superficie, Z su)."""
        return shape.translate(offset).rotate(self.matrix).translate(self.origin)

    def point(self, offset: Vec) -> np.ndarray:
        return self.matrix @ np.asarray(offset, dtype=np.float32) + self.origin


def project_curve(base: SDF, points: Sequence[Vec], direction: Vec, inset: float = 0.0,
                  start_back: float = 0.6) -> list[tuple[float, float, float]]:
    """Proietta una polilinea sulla superficie lungo 'direction' (es. (0,-1,0) per il muso).

    Ogni punto parte arretrato di start_back (deve essere dentro la forma); inset sposta il
    risultato verso l'interno (per incidere/annegare i dettagli).
    """
    d = np.asarray(direction, dtype=np.float64)
    d = d / np.linalg.norm(d)
    out = []
    for q in points:
        q = np.asarray(q, dtype=np.float64) - d * start_back
        p, n = project(base, q, d)
        p = p - n * inset
        out.append(tuple(float(x) for x in p))
    return out


def capped_cone(a: Vec, b: Vec, ra: float, rb: float, round: float = 0.0) -> SDF:
    """Tronco di cono con basi piatte (bordi arrotondati opzionali) fra a (raggio ra) e b (raggio rb)."""
    a = _v(a)
    b = _v(b)
    ra_, rb_ = ra - round, rb - round
    ba = b - a
    baba = float(ba @ ba)
    rba = rb_ - ra_

    def f(p):
        pa = p - a
        paba = (pa @ ba) / baba
        x = np.sqrt(np.maximum(np.einsum("ij,ij->i", pa, pa) - paba * paba * baba, 0.0))
        cax = np.maximum(0.0, x - np.where(paba < 0.5, ra_, rb_))
        cay = np.abs(paba - 0.5) - 0.5
        k = rba * rba + baba
        fcl = np.clip((rba * (x - ra_) + paba * baba) / k, 0.0, 1.0)
        cbx = x - ra_ - fcl * rba
        cby = paba - fcl
        s = np.where((cbx < 0.0) & (cay < 0.0), -1.0, 1.0)
        d2 = np.minimum(cax * cax + cay * cay * baba, cbx * cbx + cby * cby * baba)
        return s * np.sqrt(d2) - round

    r = max(ra, rb)
    return SDF(f, np.minimum(a, b) - r, np.maximum(a, b) + r)


def crystal(length: float, radius: float, tip: float = 0.3, sides: int = 6) -> SDF:
    """Cristallo sfaccettato: prisma regolare lungo +Z (da 0 a length) con punta piramidale.

    tip = frazione della lunghezza occupata dalla punta. Da usare con smooth=False.
    """
    angles = [2 * math.pi * i / sides for i in range(sides)]
    normals = np.array([[math.cos(a), math.sin(a)] for a in angles], dtype=np.float32)
    apothem = radius * math.cos(math.pi / sides)
    z_tip = length * (1 - tip)

    def f(p):
        q = p[:, :2] @ normals.T  # distanze lungo le normali delle facce laterali
        side = q.max(axis=1)
        # nella punta il raggio si riduce linearmente fino a zero
        t = np.clip((p[:, 2] - z_tip) / max(length - z_tip, 1e-6), 0.0, 1.0)
        r = apothem * (1 - t)
        slope = apothem / max(length - z_tip, 1e-6)
        d_side = (side - r) / np.sqrt(1 + slope * slope * (p[:, 2] > z_tip))
        return np.maximum(np.maximum(d_side, -p[:, 2]), p[:, 2] - length)

    return SDF(f, (-radius, -radius, 0.0), (radius, radius, length))
