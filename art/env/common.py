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
from lib.sdf import SDF, cylinder, euler, project, smin  # noqa: E402
from lib.toy import Model  # noqa: E402

BIG = 1e3
GROUND = -0.2


# ------------------------------------------------------------------------------ modello

def _clean_mesh(verts, faces, target=None):
    """Ripulisce la mesh del marching cubes e (se serve) la semplifica in Blender.

    Il marching cubes lascia vertici doppi e triangoli di area nulla: bloccano la decimazione
    'collapse' di Blender, che si ferma a ~1000-2000 triangoli qualunque sia il bersaglio.
    """
    import bmesh
    import bpy
    obj = _toy.make_object("_tmp", verts, faces)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges)
    bmesh.ops.triangulate(bm, faces=[fc for fc in bm.faces if len(fc.verts) > 3])
    bm.to_mesh(obj.data)
    bm.free()
    if target and len(obj.data.polygons) > target:
        _toy.decimate(obj, target)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges)
        bmesh.ops.triangulate(bm, faces=[fc for fc in bm.faces if len(fc.verts) > 3])
        bm.to_mesh(obj.data)
        bm.free()
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
    Qui la mesh fine viene invece ripulita e semplificata direttamente in Blender (le facce piane
    si riducono a pochi triangoli senza perdere gli spigoli). L'uscita (FBX, JSON, render) e' identica.
    """

    def __init__(self, name: str, voxel: float = 0.04, **kw):
        super().__init__(name, "prop", voxel=voxel, **kw)

    def build(self, *args, **kw):
        orig = _toy.mesh_sdf
        parts = {id(p.sdf): p for p in self.parts}

        def mesh(sdf, voxel):
            if isinstance(sdf, MeshShape):  # mesh low-poly costruita direttamente
                return sdf.verts.copy(), sdf.faces.copy(), None
            v, f, n = orig(sdf, voxel)
            part = parts.get(id(sdf))
            if part is not None:
                # una sola decimazione, direttamente al bersaglio: una seconda passata su una mesh
                # gia' decimata puo' far collassare intere parti (es. il pilastro della Mesa)
                v, f = _clean_mesh(v, f, part.tris)
                if len(f) > part.tris * 1.05:
                    print(f"[prop] ATTENZIONE {self.name}/{part.name}: decimazione bloccata a {len(f)} "
                          f"triangoli (richiesti {part.tris}): la forma potrebbe essere rovinata", flush=True)
                n = None
            return v, f, n

        _toy.mesh_sdf = mesh
        try:
            return super().build(*args, **kw)
        finally:
            _toy.mesh_sdf = orig


# ------------------------------------------------------------------------------ mesh dirette

class MeshShape(SDF):
    """Parte gia' in forma di mesh low-poly (foglie sottili, rametti): Prop la usa cosi' com'e',
    senza marching cubes (la decimazione appiattisce e fa sparire le lamine sottili).

    Ogni pezzo e' un solido chiuso e convesso con le facce orientate verso l'esterno."""

    def __init__(self, verts, faces):
        v = np.asarray(verts, dtype=np.float32).reshape(-1, 3)
        f = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
        super().__init__(lambda p: np.full(len(p), BIG, dtype=np.float32), v.min(0), v.max(0))
        self.verts, self.faces = v, f

    def __add__(self, other: "MeshShape") -> "MeshShape":
        return MeshShape(np.concatenate([self.verts, other.verts]),
                         np.concatenate([self.faces, other.faces + len(self.verts)]))


def mesh_concat(meshes) -> MeshShape:
    vs, fs, off = [], [], 0
    for m in meshes:
        vs.append(m.verts)
        fs.append(m.faces + off)
        off += len(m.verts)
    return MeshShape(np.concatenate(vs), np.concatenate(fs))


def _orient_convex(verts, faces):
    """Gira le facce di un pezzo convesso in modo che le normali escano dal baricentro."""
    v = np.asarray(verts, dtype=np.float64)
    c = v.mean(0)
    out = []
    for f in faces:
        a, b, d = v[f[0]], v[f[1]], v[f[2]]
        n = np.cross(b - a, d - a)
        out.append(f if np.dot(n, (a + b + d) / 3 - c) >= 0 else (f[0], f[2], f[1]))
    return out


def mesh_leaf(base, axis, side, length: float, width: float, fold: float, mid: float = 0.45) -> MeshShape:
    """Fogliolina low-poly: rombo piegato lungo la nervatura (tetraedro schiacciato, 4 triangoli).

    base = attaccatura, axis = direzione della foglia, side = direzione della larghezza; i due
    vertici laterali si alzano di 'fold' lungo la normale (piega a V, si vede da sopra e da sotto)."""
    base = np.asarray(base, dtype=np.float64)
    ax = _unit(axis)
    sd = np.asarray(side, dtype=np.float64)
    sd = _unit(sd - np.dot(sd, ax) * ax)
    n = np.cross(sd, ax)
    if n[2] < 0:
        n = -n
    tip = base + ax * length
    l = base + ax * length * mid + sd * width + n * fold
    r = base + ax * length * mid - sd * width + n * fold
    verts = [base, tip, l, r]
    faces = _orient_convex(verts, [(0, 2, 1), (0, 1, 3), (0, 3, 2), (2, 3, 1)])
    return MeshShape(verts, faces)


def mesh_tube(points, radii, sides: int = 3, twist: float = 0.0, inner_caps: bool = False) -> MeshShape:
    """Tubo low-poly (prismi a 'sides' lati) lungo una spezzata, chiuso alle estremita'.

    Ogni tratto e' un prisma convesso orientato a se'; i tappi interni (nascosti) si omettono
    salvo inner_caps=True."""
    pts = [np.asarray(p, dtype=np.float64) for p in points]
    if isinstance(radii, (int, float)):
        radii = [float(radii)] * len(pts)
    # sistema di riferimento trasportato lungo la curva
    t0 = _unit(pts[1] - pts[0])
    ref = np.array([0, 0, 1.0]) if abs(t0[2]) < 0.9 else np.array([1.0, 0, 0])
    u = _unit(np.cross(t0, ref))
    rings = []
    for i, p in enumerate(pts):
        t = _unit(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)])
        u = _unit(u - np.dot(u, t) * t)
        w = np.cross(t, u)
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides + twist * i
            ring.append(p + (u * math.cos(a) + w * math.sin(a)) * radii[i])
        rings.append(ring)
    pieces = []
    for i in range(len(pts) - 1):
        verts = rings[i] + rings[i + 1]
        faces = []
        for k in range(sides):
            k2 = (k + 1) % sides
            faces += [(k, k2, sides + k2), (k, sides + k2, sides + k)]
        if inner_caps or i == 0:
            faces += [(0, k, k + 1) for k in range(1, sides - 1)]
        if inner_caps or i == len(pts) - 2:
            faces += [(sides, sides + k + 1, sides + k) for k in range(1, sides - 1)]
        pieces.append(MeshShape(verts, _orient_convex(verts, faces)))
    return mesh_concat(pieces)


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
               zmax: float = 1.0, top: float = 1.0, bound: float = 1.0) -> SDF:
    """Blocco convesso a facce piatte inscritto in un ellissoide (sasso, scheggia, ciuffo low-poly).

    n facce casuali tagliano l'ellissoide a profondita' 'depth' (frazione del raggio): piu' e'
    bassa, piu' le facce sono grandi e irregolari. zmax < 1 esclude le facce quasi orizzontali in
    alto, cosi' le facce ripide convergono in una punta o in una cresta; top scala il piano di
    chiusura superiore (top > 1 lascia libera la punta). bound > 1 allontana i 26 piani di
    contenimento: dove mancano facce casuali restano spigoli e punte vive.
    """
    rng = np.random.default_rng(seed)
    c = np.asarray(c, dtype=np.float64)
    A = euler(*rot).astype(np.float64) @ np.diag(radii)
    dirs = sphere_dirs(n, rng)
    dirs = dirs[dirs[:, 2] <= zmax]
    off = np.linalg.norm(dirs @ A, axis=1) * rng.uniform(depth[0], depth[1], size=len(dirs))
    boff = np.linalg.norm(_BOUND_DIRS @ A, axis=1) * bound
    boff = np.where(_BOUND_DIRS[:, 2] > 0.5, boff * top, boff)
    N = np.concatenate([dirs, _BOUND_DIRS])
    D = np.concatenate([off, boff]) + N @ c
    return convex(N, D)


def cleaved_block(c, half, seed: int = 0, rot=(0, 0, 0), tilt: float = 10.0, taper: float = 0.15,
                  chips: int = 6, chip=(0.2, 0.5), peak: float = 0.0, ridge: float = 0.0) -> SDF:
    """Blocco di roccia 'spaccato': parallelepipedo (mezze misure 'half') con facce inclinate a caso
    (tilt, gradi), lati che si stringono verso l'alto (taper = frazione della mezza larghezza persa
    dal fondo alla cima), spigoli e vertici scheggiati (chips tagli, profondita' 'chip'). peak > 0
    sostituisce la faccia alta con una piramide (punta alta peak); ridge > 0 con una cresta su x."""
    rng = np.random.default_rng(seed)
    c = np.asarray(c, dtype=np.float64)
    hx, hy, hz = half
    M = euler(*rot).astype(np.float64)
    N, D = [], []

    def add(nl, off):
        nl = _unit(nl)
        nw = M @ nl
        N.append(nw)
        D.append(off + float(nw @ c))

    def jit():
        return rng.normal(size=3) * math.radians(tilt)

    for ax, h in ((0, hx), (1, hy)):
        for s in (1, -1):
            # taper = frazione della mezza larghezza persa dal fondo alla cima
            slope = taper * h / (2 * hz) + rng.normal() * math.radians(tilt) * min(1.0, h / hz)
            nl = np.zeros(3)
            nl[ax] = s
            nl[2] = slope
            j = rng.normal(size=3) * math.radians(tilt)
            j[ax] = 0.0
            j[2] = 0.0
            nl = _unit(nl + j)
            add(nl, h * abs(nl[ax]) * rng.uniform(0.9, 1.0))
    add(_unit(np.array([0, 0, -1.0]) + jit() * 0.3), hz)
    if peak > 0:
        k = rng.integers(3, 5)
        a0 = rng.uniform(0, 2 * math.pi)
        apex = np.array([rng.uniform(-0.25, 0.25) * hx, rng.uniform(-0.25, 0.25) * hy, hz + peak])
        for i in range(k):
            a = a0 + 2 * math.pi * i / k + rng.uniform(-0.3, 0.3)
            e = np.array([math.cos(a) * hx, math.sin(a) * hy, 0.0])
            nl = _unit(np.array([math.cos(a) / hx, math.sin(a) / hy, 1.0 / (peak + hz * 0.6)]) + jit() * 0.5)
            add(nl, float(nl @ apex))
        add(np.array([0, 0, 1.0]), hz + peak)
    elif ridge > 0:
        for s in (1, -1):
            nl = _unit(np.array([0.0, s / hy, 1.0 / ridge]) + jit() * 0.4)
            add(nl, float(nl @ np.array([0, 0, hz + ridge])))
        for s in (1, -1):
            nl = _unit(np.array([s / hx, 0.0, 1.0 / (ridge + hz)]) + jit() * 0.4)
            add(nl, float(nl @ np.array([0, 0, hz + ridge * 0.8])) + rng.uniform(-0.1, 0.1))
        add(np.array([0, 0, 1.0]), hz + ridge)
    else:
        add(_unit(np.array([0, 0, 1.0]) + jit()), hz * rng.uniform(0.92, 1.0))
    # scheggiature su vertici e spigoli: piani che asportano una piccola frazione del blocco
    for _ in range(chips):
        sg = rng.choice([-1.0, 1.0], size=3)
        if rng.uniform() < 0.5:
            sg[rng.integers(0, 3)] = 0.0  # spigolo invece di vertice
        if (peak > 0 or ridge > 0) and sg[2] > 0:
            sg[2] = 0.0  # non smussa la punta o la cresta
        if not sg.any():
            continue
        nl = _unit(sg / np.array([hx, hy, hz]) + rng.normal(size=3) * 0.12)
        sup = hx * abs(nl[0]) + hy * abs(nl[1]) + hz * abs(nl[2])
        add(nl, sup * (1 - rng.uniform(*chip) * 0.35))
    return convex(np.array(N), np.array(D))


def slab(poly, z0: float, z1: float, bevel: float = 0.0, tilt=(0, 0, 0), seed: int | None = None,
         chips: int = 0, chip_depth: float = 0.12, bevel_bottom: float | None = None) -> SDF:
    """Prisma poligonale convesso (poly in senso qualsiasi) tra z0 e z1, con smussi a 45 gradi
    sugli spigoli orizzontali (bevel in alto, bevel_bottom in basso: se None uguale a bevel) e
    scheggiature casuali sugli spigoli (chips)."""
    bevel_bottom = bevel if bevel_bottom is None else bevel_bottom
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
        for sz, zz, bv in ((1, z1, bevel), (-1, z0, bevel_bottom)):
            if bv > 0:
                bn = _unit([nn[0], nn[1], sz])
                # piano a 45 gradi che taglia lo spigolo di 'bv'
                D.append(float(np.dot(bn, [a[0] - nn[0] * bv, a[1] - nn[1] * bv, zz])))
                N.append(bn.tolist())
    N += [[0, 0, 1], [0, 0, -1]]
    D += [z1, -z0]
    if chips and seed is not None:
        rng = np.random.default_rng(seed)
        for _ in range(chips):
            # taglio obliquo vicino a un vertice in alto o in basso
            k = rng.integers(0, n)
            zz = z1 if rng.uniform() < 0.6 else z0
            corner = np.array([pts[k][0], pts[k][1], zz])
            out = _unit([pts[k][0] - cxy[0], pts[k][1] - cxy[1], 0.0])
            nn = _unit(out + np.array([0, 0, 1.0 if zz == z1 else -1.0]) * rng.uniform(0.5, 1.5) + rng.normal(size=3) * 0.25)
            N.append(nn.tolist())
            D.append(float(np.dot(nn, corner)) - chip_depth * rng.uniform(0.6, 1.4))
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


def polyline_crack(points, normals, depth: float, width: float) -> SDF:
    """Crepa a V lungo una spezzata di punti di superficie (con le normali uscenti).

    Larga 2*width sul bordo e profonda 'depth' all'inizio, si assottiglia fino a chiudersi
    all'ultimo punto: una linea scura continua, non una fila di tagli."""
    pts = [np.asarray(p, dtype=np.float64) for p in points]
    nrm = [_unit(n) for n in normals]
    total = sum(float(np.linalg.norm(b - a)) for a, b in zip(pts[:-1], pts[1:]))
    parts, run_len = [], 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        ln = float(np.linalg.norm(b - a))
        n = _unit(nrm[i] + nrm[i + 1])
        t = _unit(b - a)
        f0 = max(0.0, 1 - run_len / total)
        f1 = max(0.0, 1 - (run_len + ln) / total)
        run_len += ln
        parts.append(_tapered_wedge(a, b, n, depth * (0.5 + 0.5 * f0), depth * (0.5 + 0.5 * f1),
                                    width * f0 ** 0.6, max(width * f1 ** 0.6, 0.0)))
    return fast_union(*parts)


def _tapered_wedge(a, b, n, d0, d1, w0, w1) -> SDF:
    """Tratto di crepa da a a b: apertura e profondita' variano linearmente da (w0, d0) a (w1, d1)."""
    t = _unit(b - a - np.dot(b - a, n) * n)
    bn = np.cross(n, t)
    ln = float(np.dot(b - a, t))
    a32, n32, t32, b32 = (np.asarray(v, dtype=np.float32) for v in (a, n, t, bn))
    pad = 0.04

    def f(p):
        v = p - a32
        s = v @ t32
        u = np.clip(s / max(ln, 1e-6), 0.0, 1.0)
        w = w0 + (w1 - w0) * u
        d = d0 + (d1 - d0) * u
        y = v @ n32 + d  # quota sopra il fondo della crepa
        x = np.abs(v @ b32)
        k = w / np.maximum(d, 1e-4)
        wedge = (x - k * y) / np.sqrt(1 + k * k)
        ends = np.maximum(-s - pad, s - ln - pad)
        return np.maximum(wedge, ends)

    ext = max(d0, d1) + max(w0, w1) + pad
    lo = np.minimum(a, b) - ext
    hi = np.maximum(a, b) + ext
    return SDF(f, lo, hi)


def surface_crack(rock: SDF, inside, direction, along, depth: float, width: float, length: float,
                  zigzag: int = 2, seed: int = 0, bend: float = 0.35) -> SDF:
    """Crepa sulla superficie di 'rock': parte dal punto colpito dal raggio inside->direction e
    procede lungo 'along' per 'length' con un andamento a zig-zag (zigzag = numero di svolte)."""
    rng = np.random.default_rng(seed)
    inside = np.asarray(inside, dtype=np.float64)
    if rock(inside[None, :].astype(np.float32))[0] >= 0:
        raise ValueError(f"surface_crack: il punto {inside.tolist()} non e' dentro la roccia")
    p0, n0 = project(rock, inside, direction)
    t = np.asarray(along, dtype=np.float64)
    t = _unit(t - np.dot(t, n0) * n0)
    b = np.cross(n0, t)
    seg = length / (zigzag + 1)
    pts, nrm = [p0], [n0]
    cur = p0
    for i in range(zigzag + 1):
        side = (1 if i % 2 == 0 else -1) * rng.uniform(0.4, 1.0) * bend
        target = cur + _unit(t + b * side) * seg
        # riproietta sulla superficie partendo dall'interno
        try:
            pk, nk = project(rock, inside, target - inside)
        except ValueError:
            break
        pts.append(pk)
        nrm.append(nk)
        cur = pk
    return polyline_crack(pts, nrm, depth, width)


# ------------------------------------------------------------------------------ tronchi

def log_prism(x0: float, x1: float, r: float, sides: int, seed: int, cz: float, jitter: float = 0.07,
              cut0=(0, 0), cut1=(0, 0)) -> SDF:
    """Tronco low-poly lungo X: prisma a 'sides' facce irregolari tra x0 e x1, con i tagli delle
    estremita' leggermente inclinati (cut = inclinazione in y, z)."""
    rng = np.random.default_rng(seed)
    N, D = [], []
    a0 = rng.uniform(0, 2 * math.pi)
    for i in range(sides):
        a = a0 + 2 * math.pi * i / sides + rng.uniform(-0.12, 0.12)
        n = np.array([0.0, math.cos(a), math.sin(a)])
        N.append(n)
        D.append(r * (1 - rng.uniform(0, jitter)) + n[2] * cz)
    for sx, x, cut in ((1, x1, cut1), (-1, x0, cut0)):
        n = np.array([sx, cut[0], cut[1]])
        n /= np.linalg.norm(n)
        N.append(n)
        D.append(float(n @ np.array([x, 0.0, cz])))
    return convex(N, D)


def _near_ends(x0, x1, d, r, cz):
    """Regione entro d dalle due sezioni del tronco (x < x0 + d oppure x > x1 - d)."""
    return SDF(lambda p: np.minimum(p[:, 0] - (x0 + d), (x1 - d) - p[:, 0]), (x0 - 1, -r - 1, cz - r - 1), (x1 + 1, r + 1, cz + r + 1))


def log_parts(x0, x1, r, cz, seed, sides=9, cut0=(0.08, -0.05), cut1=(-0.06, 0.1), bark_t=0.07):
    """Corteccia (prisma pieno) e i due dischi di legno chiaro delle sezioni, con un anello inciso.

    Niente gusci sottili: la decimazione li accartoccia. I dischi sporgono di 0.02 dalle sezioni."""
    outer = log_prism(x0, x1, r, sides, seed, cz, cut0=cut0, cut1=cut1)
    inner = log_prism(x0 - 0.02, x1 + 0.02, r - bark_t, sides, seed, cz, jitter=0.0, cut0=cut0, cut1=cut1)
    ring = SDF(lambda p: np.abs(np.sqrt(p[:, 1] ** 2 + (p[:, 2] - cz) ** 2) - r * 0.5) - 0.025,
               (x0 - 1, -r, cz - r), (x1 + 1, r, cz + r))
    ends = inner.intersect(_near_ends(x0, x1, 0.12, r, cz)).subtract(ring.intersect(_near_ends(x0, x1, 0.0, r, cz)))
    return outer, ends


def bark_grooves(log: SDF, grooves, cz: float, depth: float = 0.07, width: float = 0.035) -> SDF:
    """Solchi della corteccia lungo X: (x centrale, lunghezza, angolo attorno all'asse in gradi)."""
    for k, (x, ln, ang) in enumerate(grooves):
        a = math.radians(ang)
        d = (0.0, math.cos(a), math.sin(a))
        log = log.subtract(surface_crack(log, (x, 0.0, cz), d, (1, 0, 0), depth=depth, width=width, length=ln,
                                         zigzag=1, seed=90 + k, bend=0.08))
    return log


def stub(a, b, r: float) -> SDF:
    """Moncone di ramo da a verso b, tagliato netto in b (diventa low-poly con la decimazione)."""
    return cylinder(a, b, r)


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
