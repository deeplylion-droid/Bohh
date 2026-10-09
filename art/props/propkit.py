"""Aiuti comuni per gli script di art/props (ostacoli, guardiani, mazze, trappole).

FineModel: come lib.toy.Model, ma la mesh fine del marching cubes viene ripulita e semplificata
direttamente in Blender invece di essere rimeshata piu' grossolana (lib.toy rimesha le parti che
superano 8x i triangoli richiesti: con budget bassi spigoli vivi, denti e cuciture si rovinano).
Stessa tecnica di env/common.py (Prop), qui valida per qualsiasi tipo di modello ("prop", "bat").
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lib.toy as _toy  # noqa: E402
from lib.sdf import SDF, capsule, ellipsoid, prism, project, tube, union  # noqa: E402
from lib.toy import Model  # noqa: E402

BIG = 1e3


# ------------------------------------------------------------------------------ modello

def _clean_mesh(verts, faces, target=None):
    """Toglie vertici doppi e triangoli degeneri del marching cubes (bloccano la decimazione
    'collapse' di Blender) e, se serve, semplifica la mesh fino a `target` triangoli."""
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
    me = obj.data
    v = np.array([vx.co[:] for vx in me.vertices], dtype=np.float32)
    f = np.array([pl.vertices[:] for pl in me.polygons], dtype=np.int64)
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(me)
    return v, f


class FineModel(Model):
    """Model che decima la mesh fine (voxel della parte) invece di rimesharla piu' grossolana."""

    def build(self, *args, **kw):
        orig = _toy.mesh_sdf
        parts = {id(p.sdf): p for p in self.parts}

        def mesh(sdf, voxel):
            v, f, n = orig(sdf, voxel)
            part = parts.get(id(sdf))
            if part is not None:
                v, f = _clean_mesh(v, f, part.tris * 2 if len(f) > part.tris * 8 else None)
            return v, f, None

        _toy.mesh_sdf = mesh
        try:
            return super().build(*args, **kw)
        finally:
            _toy.mesh_sdf = orig


def run(catalog: dict, default_views: str = "3q,front", default_res: int = 700) -> None:
    """Costruisce i modelli nominati sulla riga di comando (tutti se non ne viene indicato nessuno)."""
    import os
    views = tuple(os.environ.get("VIEWS", default_views).split(","))
    res = int(os.environ.get("RES", default_res))
    names = sys.argv[1:] or list(catalog)
    for name in names:
        if name not in catalog:
            raise SystemExit(f"Modello sconosciuto: {name} (disponibili: {', '.join(catalog)})")
        catalog[name]().build(views=views, res=res)


# ------------------------------------------------------------------------------ campi di base

def unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def fast_union(*shapes: SDF, pad: float = 0.04) -> SDF:
    """Unione netta di molte forme piccole: ognuna e' valutata solo dentro il suo box di ingombro."""
    shapes = [s for s in shapes if s is not None]
    los = [s.lo - pad for s in shapes]
    his = [s.hi + pad for s in shapes]

    def f(p):
        d = np.full(len(p), BIG, dtype=np.float32)
        for s, lo, hi in zip(shapes, los, his):
            msk = np.all((p >= lo) & (p <= hi), axis=1)
            if msk.any():
                idx = np.nonzero(msk)[0]
                d[idx] = np.minimum(d[idx], s(p[idx]))
        return d

    return SDF(f, np.min(los, axis=0), np.max(his, axis=0))


def paint(base: SDF, region: SDF, t: float = 0.02, depth: float = 0.06, k: float = 0.0) -> SDF:
    """Vernice che segue la superficie di base: strato fra -depth e +t, dentro la regione."""
    return base.offset(t).intersect(region, k=k).subtract(base.offset(-depth))


def halfspace(normal, point, size: float = BIG) -> SDF:
    """Semispazio (dentro dove n.(p - point) < 0)."""
    n = unit(normal).astype(np.float32)
    q = np.asarray(point, dtype=np.float32)
    return SDF(lambda p: (p - q) @ n, (-size,) * 3, (size,) * 3)


def convex(normals, offsets, c=(0, 0, 0), ext: float = 2.0, soft: float = 0.0) -> SDF:
    """Poliedro convesso: intersezione dei semispazi n.(p - c) <= d.

    soft > 0 usa un massimo "morbido" (log-sum-exp) che smussa leggermente gli spigoli.
    """
    nrm = np.asarray([unit(n) for n in normals], dtype=np.float32)
    off = np.asarray(offsets, dtype=np.float32)
    c = np.asarray(c, dtype=np.float32)

    def f(p):
        q = (p - c) @ nrm.T - off
        m = q.max(axis=1)
        if soft > 0:
            m = m + soft * np.log(np.exp((q - m[:, None]) / soft).sum(axis=1))
        return m

    return SDF(f, c - ext, c + ext)


# ------------------------------------------------------------------------------ superficie

def resample(path, step: float):
    """Ricampiona una lista di (punto, normale) a passo costante."""
    pts = np.array([p for p, _ in path])
    nrm = np.array([n for _, n in path])
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for t in np.arange(0.0, s[-1] + 1e-9, step):
        i = min(int(np.searchsorted(s, t, side="right")) - 1, len(seg) - 1)
        f = (t - s[i]) / max(seg[i], 1e-9)
        n = nrm[i] + (nrm[i + 1] - nrm[i]) * f
        out.append((pts[i] + (pts[i + 1] - pts[i]) * f, n / np.linalg.norm(n)))
    return out


def stitches(path, every: float, half: float, r: float, line_r: float = 0.0, inset: float = 0.0,
             cross: bool = False) -> SDF:
    """Cucitura da peluche lungo un percorso (punto, normale): trattini corti perpendicolari
    (o a X con cross=True), con una linea sottile opzionale lungo il percorso."""
    pts = resample(path, every)
    out = []
    if line_r > 0:
        out.append(tube([p - n * inset for p, n in resample(path, every / 3)], line_r))
    for i, (p, n) in enumerate(pts):
        t = pts[min(i + 1, len(pts) - 1)][0] - pts[max(i - 1, 0)][0]
        t = t / max(np.linalg.norm(t), 1e-9)
        side = np.cross(n, t)
        c = p - n * inset
        if cross:
            a, b = unit(side + t), unit(side - t)
            out += [capsule(c - a * half, c + a * half, r), capsule(c - b * half, c + b * half, r)]
        else:
            out.append(capsule(c - side * half, c + side * half, r))
    return fast_union(*out)


def tangent_frame(normal, angle: float = 0.0):
    """Due assi (u, v) perpendicolari alla normale, ruotati di `angle` gradi attorno ad essa."""
    n = unit(normal)
    u = unit(np.cross(n, [0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.cross(n, [1.0, 0.0, 0.0]))
    v = np.cross(n, u)
    a = math.radians(angle)
    return u * math.cos(a) + v * math.sin(a), -u * math.sin(a) + v * math.cos(a)


def patch_region(center, normal, rx: float, ry: float, angle: float = 0.0, power: float = 4.0,
                 depth: float = 0.5) -> SDF:
    """Regione per una toppa: "quadrato arrotondato" (superellisse) nel piano tangente, estruso lungo la normale."""
    n = unit(normal).astype(np.float32)
    u, v = (x.astype(np.float32) for x in tangent_frame(normal, angle))
    c = np.asarray(center, dtype=np.float32)
    r = min(rx, ry)

    def f(p):
        q = p - c
        a = np.abs(q @ u) / rx
        b = np.abs(q @ v) / ry
        d = ((a ** power + b ** power) ** (1.0 / power) - 1.0) * r
        return np.maximum(d, np.abs(q @ n) - depth)

    e = max(rx, ry, depth) + 0.05
    return SDF(f, c - e, c + e)


def patch_outline(base: SDF, center, normal, rx: float, ry: float, angle: float = 0.0, power: float = 4.0, n: int = 40):
    """Contorno della toppa proiettato sulla superficie: lista chiusa di (punto, normale)."""
    nn = unit(normal)
    u, v = tangent_frame(normal, angle)
    c = np.asarray(center, dtype=np.float64)
    out = []
    for t in np.linspace(0, 2 * math.pi, n + 1):
        ct, st = math.cos(t), math.sin(t)
        a = rx * np.sign(ct) * abs(ct) ** (2 / power)
        b = ry * np.sign(st) * abs(st) ** (2 / power)
        q = c + u * a + v * b
        out.append(project(base, q - nn * 0.6, nn))
    return out


# ------------------------------------------------------------------------------ faccia "toy horror"

def face_prism(poly, y0: float, y1: float, round: float = 0.0) -> SDF:
    """Regione: poligono nel piano XZ (coppie x, z) estruso lungo Y fra y0 e y1 (y0 < y1)."""
    return prism(poly, -y1, -y0, round=round).rot(90, 0, 0)


def grin_regions(xc: float, zc: float, half_w: float, curve: float, slope: float, thick: float,
                 n_up: int, n_lo: int, tooth_w: float, y0: float, y1: float, tooth_len: float = 0.62,
                 lo_len: float = 0.45, asym: float = 0.0):
    """Ghigno a mezzaluna (regioni estruse lungo Y): bordo superiore z = zc + curve*u^2 + slope*u
    (u in [-1, 1] sulla larghezza), spessore massimo `thick` al centro.

    Ritorna (bocca, denti_sopra, denti_sotto): fila di dentini aguzzi in alto, alternati in basso.
    asym > 0 alza un angolo della bocca (ghigno sbilenco).
    """
    def top(x):
        u = (x - xc) / half_w
        return zc + curve * u * u + slope * u + asym * max(u, 0.0) ** 2, thick * max(0.0, 1 - u * u) ** 0.7

    xs = np.linspace(xc - half_w, xc + half_w, 29)
    upper = [(x, top(x)[0]) for x in xs]
    lower = [(x, top(x)[0] - top(x)[1]) for x in xs[-2:0:-1]]
    mouth = face_prism(upper + lower, y0, y1, round=0.004)
    up, lo = [], []
    for i in range(n_up):
        x = xc - 0.82 * half_w + (i + 0.5) * 1.64 * half_w / n_up
        z, th = top(x)
        up.append(face_prism([(x - tooth_w / 2, z + 0.03), (x + tooth_w / 2, z + 0.03), (x, z - tooth_len * th)],
                             y0, y1, round=0.003))
    for i in range(n_lo):
        x = xc - 0.62 * half_w + (i + 0.5) * 1.24 * half_w / n_lo
        z, th = top(x)
        lo.append(face_prism([(x - tooth_w * 0.42, z - th - 0.03), (x + tooth_w * 0.42, z - th - 0.03),
                              (x, z - th + lo_len * th)], y0, y1, round=0.003))
    return mouth, (union(*up) if up else None), (union(*lo) if lo else None)


def above_line(z0: float, slope: float, size: float = 4.0) -> SDF:
    """Semispazio z > z0 + slope * x (coordinate locali dell'occhio): taglio delle palpebre."""
    n = math.sqrt(1 + slope * slope)
    return SDF(lambda p: (slope * p[:, 0] - p[:, 2] + z0) / n, (-size,) * 3, (size,) * 3)


def eyelid(frame, radii, z0: float, slope: float, grow=(0.03, 0.04, 0.03), k: float = 0.02) -> SDF:
    """Palpebra superiore pesante: guscio poco piu' grande dell'occhio, tenuto sopra z0 + slope*x."""
    shell = ellipsoid((radii[0] + grow[0], radii[1] + grow[1], radii[2] + grow[2]))
    return frame.place(shell.intersect(above_line(z0, slope), k=k))
