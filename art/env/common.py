"""Funzioni comuni agli script degli oggetti di scenario (env/*.py).

Convenzioni degli oggetti: origine al centro della base (z = 0), fronte verso -Y, la parte bassa
scende fino a circa z = -0.2 (GROUND) cosi' sui pendii non sembrano mai sospesi.

Stile dell'ambiente: niente forme "a caramella". Rocce spigolose a facce piatte (smooth=False),
con punte, scheggiature e crepe; piante stilizzate ma credibili; colori naturali poco saturi.
"""
from __future__ import annotations

import itertools
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lib.toy as _toy  # noqa: E402
from lib.sdf import SDF, euler, project, smin  # noqa: E402
from lib.toy import Model  # noqa: E402

BIG = 1e3
GROUND = -0.2


# ------------------------------------------------------------------------------ modello

def _predecimate(verts, faces, target):
    """Semplifica in Blender una mesh troppo fitta (stessa decimazione 'collapse' di lib.toy)."""
    import bpy
    obj = _toy.make_object("_tmp", verts, faces)
    _toy.decimate(obj, target)
    me = obj.data
    v = np.array([vx.co[:] for vx in me.vertices], dtype=np.float32)
    f = np.array([pl.vertices[:] for pl in me.polygons], dtype=np.int64)
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(me)
    return v, f


class Prop(Model):
    """Model per gli oggetti di scenario (kind "prop").

    lib.toy.Model rimesha piu' grossolano le parti che superano 8x i triangoli richiesti: con budget
    bassi gli spigoli vivi si arrotondano e i dettagli sottili (crepe, rametti, fili) spariscono.
    Qui la mesh fine viene invece semplificata direttamente in Blender (le facce piane si riducono
    a pochi triangoli senza perdere gli spigoli). L'uscita (FBX, JSON, render) e' identica.
    """

    def __init__(self, name: str, voxel: float = 0.04, **kw):
        super().__init__(name, "prop", voxel=voxel, **kw)

    def build(self, *args, **kw):
        orig = _toy.mesh_sdf
        parts = {id(p.sdf): p for p in self.parts}

        def mesh(sdf, voxel):
            v, f, n = orig(sdf, voxel)
            part = parts.get(id(sdf))
            if part is not None and len(f) > part.tris * 8:
                v, f = _predecimate(v, f, part.tris * 2)
                n = None
            return v, f, n

        _toy.mesh_sdf = mesh
        try:
            return super().build(*args, **kw)
        finally:
            _toy.mesh_sdf = orig


# ------------------------------------------------------------------------------ campi di base

def noisy(shape: SDF, amp: float, freq: float, seed: int, waves: int = 6) -> SDF:
    """Deforma la superficie con rumore (somma di sinusoidi) per forme naturali."""
    rng = np.random.default_rng(seed)
    ws = [(rng.normal(size=3).astype(np.float32) * freq, rng.uniform(0, 6.28), rng.uniform(0.5, 1.0)) for _ in range(waves)]

    def f(p):
        d = shape(p)
        n = np.zeros(len(p), dtype=np.float32)
        for k, ph, w in ws:
            n += w * np.sin(p @ k + ph)
        return d + amp * n / 3.0

    return SDF(f, shape.lo - amp * 2, shape.hi + amp * 2)


def ground(z0: float = GROUND) -> SDF:
    """Semispazio z >= z0 (da intersecare per avere una base piatta appena sotto terra)."""
    return SDF(lambda p: z0 - p[:, 2], (-BIG, -BIG, z0), (BIG, BIG, BIG))


def ceiling(z1: float) -> SDF:
    """Semispazio z <= z1."""
    return SDF(lambda p: p[:, 2] - z1, (-BIG, -BIG, -BIG), (BIG, BIG, z1))


def fast_union(*shapes: SDF, k: float = 0.0) -> SDF:
    """Unione (morbida) che valuta ogni forma solo dentro il suo box di ingombro.

    Molto piu' veloce di union() con decine di primitive (foglie, rametti, fili di paglia).
    Fuori da tutti i box la distanza vale BIG: il segno resta corretto per il marching cubes.
    """
    shapes = [s for s in shapes if s is not None]
    pad = max(k, 0.02) * 2.0
    boxes = [(s.lo - pad, s.hi + pad) for s in shapes]

    def f(p):
        d = np.full(len(p), BIG, dtype=np.float32)
        for s, (lo, hi) in zip(shapes, boxes):
            m = np.all((p >= lo) & (p <= hi), axis=1)
            if not m.any():
                continue
            idx = np.nonzero(m)[0]
            d[idx] = smin(d[idx], s(p[idx]), k)
        return d

    lo = np.min([s.lo for s in shapes], axis=0) - k
    hi = np.max([s.hi for s in shapes], axis=0) + k
    return SDF(f, lo, hi)


def wavy_above(z0: float, amp: float, lobes: int, phase: float = 0.0, center=(0.0, 0.0)) -> SDF:
    """Regione sopra un bordo orizzontale ondulato z0 + amp*sin(lobes*theta + phase)."""
    cx, cy = center

    def f(p):
        th = np.arctan2(p[:, 1] - cy, p[:, 0] - cx)
        return z0 + amp * np.sin(lobes * th + phase) - p[:, 2]

    return SDF(f, (-BIG, -BIG, z0 - abs(amp)), (BIG, BIG, BIG))


def paint(base: SDF, region: SDF, t: float = 0.03) -> SDF:
    """'Vernice' in rilievo di spessore t sulla superficie di base, limitata a region."""
    return base.offset(t).intersect(region)


# ------------------------------------------------------------------------------ poliedri (rocce)

def _unit(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def convex(normals, offsets) -> SDF:
    """Poliedro convesso: intersezione dei semispazi n.p <= d (facce piatte, spigoli vivi).

    Il box di ingombro e' calcolato esattamente dai vertici del poliedro.
    """
    N = np.asarray(normals, dtype=np.float64)
    N = N / np.linalg.norm(N, axis=1, keepdims=True)
    D = np.asarray(offsets, dtype=np.float64)
    verts = []
    for i, j, k in itertools.combinations(range(len(N)), 3):
        M = N[[i, j, k]]
        if abs(np.linalg.det(M)) < 1e-6:
            continue
        x = np.linalg.solve(M, D[[i, j, k]])
        if np.all(N @ x <= D + 1e-5):
            verts.append(x)
    verts = np.array(verts)
    lo, hi = verts.min(0), verts.max(0)
    Nf, Df = N.astype(np.float32), D.astype(np.float32)

    def f(p):
        return (p @ Nf.T - Df).max(axis=1)

    return SDF(f, lo, hi)


def sphere_dirs(n: int, rng, jitter: float = 0.3) -> np.ndarray:
    """n direzioni ben distribuite sulla sfera (spirale di Fibonacci) con un po' di disordine."""
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5 ** 0.5) * i + rng.uniform(0, 6.28)
    d = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], axis=1)
    d = d + rng.normal(size=d.shape) * jitter
    return d / np.linalg.norm(d, axis=1, keepdims=True)


_BOUND_DIRS = np.array([d for d in itertools.product((-1, 0, 1), repeat=3) if any(d)], dtype=np.float64)
_BOUND_DIRS /= np.linalg.norm(_BOUND_DIRS, axis=1, keepdims=True)


def facet_blob(c, radii, n: int = 16, seed: int = 0, depth=(0.82, 1.0), rot=(0, 0, 0),
               zmax: float = 1.0, top: float = 1.0) -> SDF:
    """Blocco convesso a facce piatte inscritto in un ellissoide (sasso, scheggia, ciuffo low-poly).

    n facce casuali tagliano l'ellissoide a profondita' 'depth' (frazione del raggio): piu' e'
    bassa, piu' le facce sono grandi e irregolari. zmax < 1 esclude le facce quasi orizzontali in
    alto, cosi' le facce ripide convergono in una punta o in una cresta; top scala il piano di
    chiusura superiore (top > 1 lascia libera la punta).
    """
    rng = np.random.default_rng(seed)
    c = np.asarray(c, dtype=np.float64)
    A = euler(*rot).astype(np.float64) @ np.diag(radii)
    dirs = sphere_dirs(n, rng)
    dirs = dirs[dirs[:, 2] <= zmax]
    off = np.linalg.norm(dirs @ A, axis=1) * rng.uniform(depth[0], depth[1], size=len(dirs))
    boff = np.linalg.norm(_BOUND_DIRS @ A, axis=1)
    boff = np.where(_BOUND_DIRS[:, 2] > 0.5, boff * top, boff)
    N = np.concatenate([dirs, _BOUND_DIRS])
    D = np.concatenate([off, boff]) + N @ c
    return convex(N, D)


def slab(poly, z0: float, z1: float, bevel: float = 0.0, tilt=(0, 0, 0), seed: int | None = None,
         chips: int = 0, chip_depth: float = 0.12) -> SDF:
    """Prisma poligonale convesso (poly in senso qualsiasi) tra z0 e z1, con smussi a 45 gradi
    sugli spigoli orizzontali (bevel) e scheggiature casuali sugli spigoli (chips)."""
    pts = np.asarray(poly, dtype=np.float64)
    cxy = pts.mean(0)
    N, D = [], []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        e = b - a
        nn = np.array([e[1], -e[0]])
        nn /= np.linalg.norm(nn)
        if np.dot(nn, a - cxy) < 0:
            nn = -nn
        N.append([nn[0], nn[1], 0.0])
        D.append(float(np.dot(nn, a)))
        if bevel > 0:
            for sz, zz in ((1, z1), (-1, z0)):
                bn = _unit([nn[0], nn[1], sz])
                # piano a 45 gradi che taglia lo spigolo di 'bevel'
                D.append(float(np.dot(bn, [a[0] - nn[0] * bevel, a[1] - nn[1] * bevel, zz])))
                N.append(bn.tolist())
    N += [[0, 0, 1], [0, 0, -1]]
    D += [z1, -z0]
    if chips and seed is not None:
        rng = np.random.default_rng(seed)
        N0, D0 = np.array(N), np.array(D)
        for _ in range(chips):
            # taglio obliquo vicino a un vertice in alto o in basso
            k = rng.integers(0, n)
            zz = z1 if rng.uniform() < 0.6 else z0
            corner = np.array([pts[k][0], pts[k][1], zz])
            out = _unit([pts[k][0] - cxy[0], pts[k][1] - cxy[1], 0.0])
            nn = _unit(out + np.array([0, 0, 1.0 if zz == z1 else -1.0]) * rng.uniform(0.5, 1.5) + rng.normal(size=3) * 0.25)
            N.append(nn.tolist())
            D.append(float(np.dot(nn, corner)) - chip_depth * rng.uniform(0.6, 1.4))
        del N0, D0
    shape = convex(N, D)
    if any(tilt):
        cz = (z0 + z1) / 2
        shape = shape.rot(*tilt, pivot=(cxy[0], cxy[1], cz))
    return shape


def irregular_poly(n: int, rx: float, ry: float, seed: int, jitter: float = 0.25, rot: float = 0.0):
    """Poligono convesso irregolare (per lastre e strati di roccia)."""
    rng = np.random.default_rng(seed)
    angs = np.sort(rng.uniform(0, 2 * math.pi, n) * 0.35 + np.linspace(0, 2 * math.pi, n, endpoint=False) * 0.65 + rot)
    pts = []
    for a in angs:
        r = 1 - rng.uniform(0, jitter)
        pts.append((rx * r * math.cos(a), ry * r * math.sin(a)))
    return pts


def wedge_crack(q, normal, along, depth: float, width: float, length: float) -> SDF:
    """Crepa a V da sottrarre: si apre larga 2*width sulla superficie (punto q, normale uscente
    'normal'), si chiude a profondita' 'depth', lunga 'length' nella direzione 'along'."""
    n = _unit(normal)
    t = np.asarray(along, dtype=np.float64)
    t = _unit(t - np.dot(t, n) * n)
    b = np.cross(n, t)
    q = np.asarray(q, dtype=np.float64)
    apex = (q - n * depth).astype(np.float32)
    kk = width / depth
    n32, t32, b32 = n.astype(np.float32), t.astype(np.float32), b.astype(np.float32)
    s = 1.0 / math.sqrt(1 + kk * kk)

    def f(p):
        v = p - apex
        x = v @ b32
        y = v @ n32
        z = v @ t32
        wedge = (np.abs(x) - kk * y) * s
        # le estremita' si stringono: la crepa sfuma invece di finire di netto
        taper = np.abs(z) / (length * 0.5)
        return np.maximum(wedge + np.maximum(taper - 0.6, 0) * width * 2.5, np.abs(z) - length * 0.5)

    ext = length * 0.5 + depth + width
    return SDF(f, q - ext, q + ext)


def surface_crack(rock: SDF, inside, direction, along, depth: float, width: float, length: float,
                  zigzag: int = 0, seed: int = 0) -> SDF:
    """Crepa sulla superficie di 'rock' nel punto colpito dal raggio inside->direction.

    Con zigzag > 0 la crepa e' una spezzata di piu' tratti (piu' naturale)."""
    p, n = project(rock, inside, direction)
    if not zigzag:
        return wedge_crack(p, n, along, depth, width, length)
    rng = np.random.default_rng(seed)
    t = np.asarray(along, dtype=np.float64)
    t = _unit(t - np.dot(t, n) * n)
    b = np.cross(n, t)
    seg = length / (zigzag + 1)
    pts = [p - t * length * 0.5]
    for i in range(zigzag + 1):
        side = (1 if i % 2 == 0 else -1) * rng.uniform(0.25, 0.5)
        pts.append(pts[-1] + _unit(t + b * side) * seg)
    parts = []
    for a, b2 in zip(pts[:-1], pts[1:]):
        mid = (a + b2) / 2
        try:
            pm, nm = project(rock, np.asarray(inside, dtype=np.float64), mid - np.asarray(inside, dtype=np.float64))
        except ValueError:
            continue
        parts.append(wedge_crack(pm, nm, b2 - a, depth, width, float(np.linalg.norm(b2 - a)) * 1.15))
    return fast_union(*parts)


# ------------------------------------------------------------------------------ piante

def star_tier(z0: float, h: float, R: float, n: int = 8, notch: float = 0.35, droop: float = 0.3,
              lift: float = 0.4, twist: float = 0.0) -> SDF:
    """Palco di abete: cono con bordo a stella (punte dei rami che scendono) e sotto concavo."""
    apex = z0 + h
    two_pi = 2 * math.pi

    def parts(p):
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        th = np.arctan2(y, x) + twist
        rho = np.sqrt(x * x + y * y)
        u = (th * n / two_pi) % 1.0
        spike = np.abs(2 * u - 1)  # 1 sulle punte, 0 negli incavi
        s = R * (1 - notch * (1 - spike))
        zb = z0 - droop * spike
        hh = apex - zb
        side = (rho - s * (apex - z) / hh) * hh / np.sqrt(hh * hh + s * s)
        under = zb + lift * np.clip(1 - rho / s, 0, 1) - z
        return np.maximum(side, under)

    return SDF(parts, (-R, -R, z0 - droop), (R, R, apex))


def run(catalog: dict) -> None:
    """CLI comune: python env/<file>.py Nome1 Nome2 ... (oppure "all")."""
    names = list(catalog) if sys.argv[1:] == ["all"] else sys.argv[1:]
    unknown = [n for n in names if n not in catalog]
    if unknown:
        raise SystemExit(f"Modelli sconosciuti: {unknown}. Disponibili: {list(catalog)}")
    views = tuple(os.environ.get("VIEWS", "3q").split(","))
    res = int(os.environ.get("RES", 500))
    for n in names:
        catalog[n]().build(views=views, res=res)
