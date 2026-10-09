"""Icone 3D dell'interfaccia (pulsanti, negozio, game pass e developer product).

Uso (dalla cartella art/), un solo processo Blender alla volta:
    nice -n 10 ../.tools/venv/bin/python icons/icons.py Coin Egg ...   # alcune icone
    nice -n 10 ../.tools/venv/bin/python icons/icons.py all            # tutte
    ../.tools/venv/bin/python icons/icons.py sheet                     # foglio di controllo
Variabili d'ambiente: RES (512), SAMPLES (48), VIEW ("x,y,z" forza la direzione della camera),
OUTDIR (cartella alternativa al posto di art/out, per le prove).

Uscita: art/out/images/Icon<Nome>.png, sfondo trasparente, oggetto inquadrato sulla sua sagoma.
Stile: giocattolo in vinile lucido come pet e uova; forme grosse e semplici, 2-6 colori per icona,
stessa camera e stessa luce per tutto il set.
"""
from __future__ import annotations

import math
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib import toy  # noqa: E402
from lib.sdf import (SDF, Frame, _len, bezier, box, capped_cone, capsule, cylinder, egg, ellipsoid,  # noqa: E402
                     halfspace_z, octahedron, prism, project, project_curve, round_cone, smax, sphere,
                     star_points, stick, torus, tube, union)
from lib.toy import Model  # noqa: E402

# direzione della camera comune a tutto il set (spazio Blender, il modello guarda verso -Y):
# leggermente da destra e dall'alto, quasi frontale (le facce piatte restano leggibili)
DEFAULT_VIEW = (0.35, -1.0, 0.45)
FILL = 0.92  # frazione del riquadro occupata dal lato maggiore della sagoma
GLOSS = 0.15  # vernice trasparente leggera su tutto (vinile lucido); l'oro ne ha di piu'
# le icone sono solo immagini: budget di triangoli altissimo, cosi' Model.build non rimesha piu'
# grossolano e non decima (la decimazione dava bordi bitorzoluti, riflessi a strisce sotto la vernice
# lucida e triangoli ribaltati): si usa la mesh del marching cubes con le normali esatte dell'SDF
TRIS_SCALE = 100

# ---------------------------------------------------------------------- palette
GOLD = (255, 194, 30)
GOLD_DEEP = (240, 150, 16)
GOLD_LIGHT = (255, 230, 110)
EMBLEM = (255, 240, 150)
WHITE = (255, 255, 255)
CREAM = (255, 244, 220)
EYE = (36, 24, 40)
MOUTH = (120, 44, 60)
BLUSH = (255, 116, 150)
RED = (238, 46, 58)
RED_DARK = (176, 22, 44)
GREEN = (84, 214, 72)
GREEN_DARK = (34, 150, 58)
GREEN_LIGHT = (176, 248, 120)
BLUE = (60, 156, 255)
BLUE_DARK = (30, 84, 200)
SKY = (120, 200, 255)
PINK = (255, 104, 178)
PINK_LIGHT = (255, 150, 206)
LAVENDER = (182, 152, 255)
ORANGE = (255, 138, 28)
ORANGE_LIGHT = (255, 206, 110)
YELLOW = (255, 220, 54)
WOOD = (204, 126, 64)
WOOD_LIGHT = (240, 184, 118)
WOOD_DARK = (150, 86, 44)
TAN = (226, 164, 98)
SILVER = (214, 222, 236)
GREY = (158, 172, 196)
GREY_DARK = (84, 92, 120)
SLATE = (74, 80, 108)
SPOT = (196, 146, 98)
SPOT_LIGHT = (226, 186, 140)
SKIN = (255, 204, 84)
INK = (52, 30, 44)


# ---------------------------------------------------------------------- inquadratura e render
def _frame_tight(objs, view="3q", res=900, lens=60, fill=0.78, aspect=(1, 1)):
    """Come lib.render.frame_camera, ma inquadra la sagoma proiettata (l'icona riempie il riquadro).

    Ritorna gli stessi valori (camera, centro e raggio del box, minimo del box): la luce di
    contorno resta piazzata come per i modelli.
    """
    import bpy
    from mathutils import Vector

    from lib import render

    scene = bpy.context.scene
    chunks = []
    for o in objs:
        n = len(o.data.vertices)
        co = np.empty(n * 3, dtype=np.float64)
        o.data.vertices.foreach_get("co", co)
        mw = np.array(o.matrix_world)
        chunks.append(co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])
    pts = np.concatenate(chunks)
    lo, hi = pts.min(0), pts.max(0)
    radius = float(np.linalg.norm(hi - lo) / 2)
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = lens
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    d = np.asarray(render.VIEWS.get(view, view), dtype=np.float64)
    d /= np.linalg.norm(d)
    f = -d
    up = np.array([0.0, 0.0, 1.0])
    u = up - f * (up @ f)
    u /= np.linalg.norm(u)
    r = np.cross(f, u)
    t = cam_data.sensor_width / (2 * lens)  # tangente del semicampo (sensore orizzontale, immagine quadrata)
    aim = (lo + hi) / 2
    dist = radius / math.sin(math.atan(t)) / FILL
    for _ in range(14):
        rel = pts - (aim + d * dist)
        z = rel @ f
        x = (rel @ r) / (z * t)
        y = (rel @ u) / (z * t)
        cx, cy = (x.max() + x.min()) / 2, (y.max() + y.min()) / 2
        ext = max(x.max() - x.min(), y.max() - y.min()) / 2
        aim = aim + (r * cx + u * cy) * dist * t
        dist *= ext / FILL
    loc = aim + d * dist
    cam.location = Vector(loc.tolist())
    cam.rotation_euler = (Vector(aim.tolist()) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x = int(res * aspect[0])
    scene.render.resolution_y = int(res * aspect[1])
    cam_data.clip_end = dist * 10
    return cam, Vector(((lo + hi) / 2).tolist()), radius, lo


def _patch_render():
    """Adatta la pipeline dei modelli alle icone, solo in questo processo (lib/ non viene toccata):

    - inquadratura stretta sulla sagoma (_frame_tight) e campioni regolabili (SAMPLES);
    - normali lisce: il mesher calcola le normali esatte dal gradiente dell'SDF ma toy.py le scarta;
      qui diventano normali personalizzate della mesh (niente puntini lucidi dovuti ai triangolini
      del marching cubes sotto la vernice trasparente).
    """
    from lib import render

    if getattr(render, "_icons_patched", False):
        return
    samples = int(os.environ.get("SAMPLES", 48))
    orig_setup = render.setup_world

    def setup_world(**kw):
        kw.setdefault("samples", samples)
        return orig_setup(**kw)

    render.setup_world = setup_world
    render.frame_camera = _frame_tight

    last = {}
    orig_mesh, orig_make, orig_dec = toy.mesh_sdf, toy.make_object, toy.decimate

    def mesh_sdf(sdf, voxel=0.03, *a, **kw):
        verts, faces, normals = orig_mesh(sdf, voxel, *a, **kw)
        last["normals"] = normals
        return verts, faces, normals

    def make_object(name, verts, faces):
        obj = orig_make(name, verts, faces)
        n = last.pop("normals", None)
        if n is not None and len(n) == len(obj.data.vertices):
            obj.data.normals_split_custom_set_from_vertices(np.asarray(n, dtype=np.float64).tolist())
        return obj

    def decimate(obj, target):
        # se mai servisse decimare, le normali personalizzate non sarebbero piu' valide
        if len(obj.data.polygons) > target and "custom_normal" in obj.data.attributes:
            obj.data.attributes.remove(obj.data.attributes["custom_normal"])
        return orig_dec(obj, target)

    toy.mesh_sdf, toy.make_object, toy.decimate = mesh_sdf, make_object, decimate
    render._icons_patched = True


# ---------------------------------------------------------------------- forme di base
def add(m: Model, name: str, sdf: SDF, color, tris: int = 8000, gloss: float = GLOSS, role: str = "detail", **kw):
    kw.setdefault("reflectance", gloss)
    return m.add(name, sdf, color, tris=max(int(tris * TRIS_SCALE), 6000), role=role, **kw)


def tf(shape: SDF, pos=(0, 0, 0), rx=0.0, ry=0.0, rz=0.0) -> SDF:
    """Ruota (XYZ, gradi) attorno all'origine e poi sposta."""
    return shape.rot(rx, ry, rz).translate(pos)


def cyl(a, b, r: float, round: float = 0.0) -> SDF:
    """Cilindro che va esattamente da a a b (lib.cylinder con round lo allunga di round per parte)."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if round > 0:
        d = (b - a) / np.linalg.norm(b - a)
        a, b = a + d * round, b - d * round
    return cylinder(tuple(a), tuple(b), r, round=round)


def ccone(a, b, ra: float, rb: float, round: float = 0.0) -> SDF:
    """Tronco di cono esattamente da a a b (come cyl)."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if round > 0:
        d = (b - a) / np.linalg.norm(b - a)
        a, b = a + d * round, b - d * round
    return capped_cone(tuple(a), tuple(b), ra, rb, round=round)


def inset_poly(pts, d: float):
    """Poligono rientrato di d (lati spostati verso l'interno, vertici = intersezioni dei lati spostati)."""
    P = np.asarray(pts, dtype=np.float64)
    n = len(P)
    area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    sg = 1.0 if area > 0 else -1.0
    out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        e1 = (b - a) / np.linalg.norm(b - a)
        e2 = (c - b) / np.linalg.norm(c - b)
        p1 = b + sg * np.array([-e1[1], e1[0]]) * d
        p2 = b + sg * np.array([-e2[1], e2[0]]) * d
        den = e1[0] * e2[1] - e1[1] * e2[0]
        if abs(den) < 1e-9:
            out.append(tuple(p1))
            continue
        w = p2 - p1
        out.append(tuple(p1 + e1 * (w[0] * e2[1] - w[1] * e2[0]) / den))
    return out


def plate(poly, t: float, r: float | None = None, corner: float = 0.0) -> SDF:
    """Lastra con contorno poligonale nel piano XZ (x a destra, y del poligono = Z), spessore t lungo Y.

    r arrotonda gli spigoli delle facce; corner arrotonda anche gli angoli convessi del contorno
    (prism() li lascia vivi e il marching cubes li rende frastagliati, es. le punte delle stelle).
    """
    r = min(t * 0.45, 0.2) if r is None else r
    if corner > 0:
        inner = prism(inset_poly(poly, corner), -t / 2 + corner, t / 2 - corner, round=max(r - corner, 0.0))
        return inner.offset(corner).rot(90, 0, 0)
    return prism(poly, -t / 2, t / 2, round=r).rot(90, 0, 0)


def front(poly, depth: float = 1.0) -> SDF:
    """Regione: poligono (piano XZ) estruso solo davanti (y da -depth a 0), per le vernici sulla faccia."""
    return prism(poly, 0.0, depth).rot(90, 0, 0)


def paint(base: SDF, region: SDF, t: float = 0.025, depth: float = 0.06) -> SDF:
    """Strato sottile di vernice che segue la superficie di base dentro la regione."""
    return base.offset(t).intersect(region).subtract(base.offset(-depth))


def fast_union(shapes, pad: float = 0.05) -> SDF:
    """Unione di molte forme piccole: ognuna e' valutata solo vicino al suo ingombro."""
    los = [np.asarray(s.lo) - pad for s in shapes]
    his = [np.asarray(s.hi) + pad for s in shapes]

    def f(p):
        d = np.ones(len(p), dtype=np.float32)
        for s, lo, hi in zip(shapes, los, his):
            msk = np.all((p >= lo) & (p <= hi), axis=1)
            if msk.any():
                d[msk] = np.minimum(d[msk], s(p[msk]))
        return d

    return SDF(f, np.min(los, axis=0), np.max(his, axis=0))


def squash(shape: SDF, sx: float = 1.0, sy: float = 1.0, sz: float = 1.0, pad: float = 0.1) -> SDF:
    """Scala non uniforme attorno all'origine (distanza approssimata)."""
    k = np.array([1 / sx, 1 / sy, 1 / sz], dtype=np.float32)
    s = shape.warp(lambda p: p * k, pad=0.0)
    lo = shape.lo * np.array([sx, sy, sz])
    hi = shape.hi * np.array([sx, sy, sz])
    return SDF(s.f, np.minimum(lo, hi) - pad, np.maximum(lo, hi) + pad)


def above(z: float) -> SDF:
    """Semispazio sopra la quota z (per tagliare o dipingere)."""
    return halfspace_z(z, above=True, lo=(-50, -50, -50), hi=(50, 50, 50))


def egg_outline(rad: float, h: float, taper: float = 0.2, n: int = 32):
    """Contorno 2D di un uovo centrato in (0, 0), punta in alto."""
    pts = []
    for i in range(n + 1):
        u = 2 * i / n - 1
        rr = rad * math.sqrt(max(1 - u * u, 0.0)) * (1 - taper * u)
        pts.append((rr, (u * 0.5) * h))
    return pts + [(-x, y) for x, y in reversed(pts[1:-1])]


def rrect(w: float, h: float, r: float, n: int = 6):
    """Rettangolo arrotondato (semilati w, h, raggio r) come poligono 2D."""
    pts = []
    for cx, cy, a0 in ((w - r, h - r, 0), (-w + r, h - r, 90), (-w + r, -h + r, 180), (w - r, -h + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def heart_poly(s: float, n: int = 48):
    """Cuore con la punta in (0, 0) e i lobi verso +y (altezza ~1.8 s)."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x * s / 16, (y + 17) * s / 16))
    return pts


def gear_poly(n: int, r_out: float, r_root: float, tip: float = 0.4, base: float = 0.62, arc: int = 5):
    """Contorno di ingranaggio a n denti trapezoidali (tip/base = larghezza in punta/alla base, in passi)."""
    step = 2 * math.pi / n
    pts = []
    for i in range(n):
        c = i * step
        for a, rr in ((c - step * base / 2, r_root), (c - step * tip / 2, r_out), (c + step * tip / 2, r_out),
                      (c + step * base / 2, r_root)):
            pts.append((rr * math.cos(a), rr * math.sin(a)))
        a0, a1 = c + step * base / 2, c + step - step * base / 2
        for j in range(1, arc):
            a = a0 + (a1 - a0) * j / arc
            pts.append((r_root * math.cos(a), r_root * math.sin(a)))
    return pts


def shield_poly(w: float = 1.0, top: float = 0.95, bottom: float = -1.3, n: int = 12):
    """Contorno di scudo: bordo alto appena bombato, fianchi che curvano fino alla punta in basso."""
    right = [(0.0, top + 0.1), (w * 0.5, top + 0.07), (w * 0.86, top), (w, top - 0.1)]
    curve = bezier((w, top - 0.22, 0), (w, -0.35 * w, 0), (w * 0.62, bottom + 0.42 * w, 0), (0, bottom, 0), n)
    right += [(x, y) for x, y, _ in curve]
    return right + [(-x, y) for x, y in reversed(right[1:-1])]


def strip(pts2d, w0: float, w1: float | None = None):
    """Contorno di un nastro largo w (da w0 a w1) attorno a una polilinea 2D (piano XZ)."""
    pts = np.asarray(pts2d, dtype=np.float64)
    w1 = w0 if w1 is None else w1
    n = len(pts)
    left, right = [], []
    for i in range(n):
        d = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        d /= np.linalg.norm(d)
        nrm = np.array([-d[1], d[0]])
        w = (w0 + (w1 - w0) * i / (n - 1)) / 2
        left.append(tuple(pts[i] + nrm * w))
        right.append(tuple(pts[i] - nrm * w))
    return left + right[::-1]


BOLT = [(0.12, 0.62), (-0.36, -0.06), (-0.04, -0.06), (-0.2, -0.62), (0.36, 0.1), (0.04, 0.1)]  # fulmine


def sparkle(size: float, t: float | None = None) -> SDF:
    """Stellina a quattro punte rivolta verso -Y."""
    t = size * 0.26 if t is None else t
    return plate(star_points(4, size, size * 0.3, rot_deg=90), t, r=t * 0.45, corner=size * 0.06)


def puffy_star(r_out: float, r_in: float, t: float) -> SDF:
    """Stella a cinque punte bombata (piu' sottile sulle punte), rivolta verso -Y."""
    base = plate(star_points(5, r_out, r_in, rot_deg=90), t, r=t * 0.3, corner=0.055 * r_out)
    return base.intersect(ellipsoid((r_out * 1.3, t * 0.5, r_out * 1.3)), k=0.06)


def star_with_face(r_out: float, r_in: float, t: float):
    """Stella bombata e stella interna piu' chiara in rilievo sul davanti (effetto smusso)."""
    s = puffy_star(r_out, r_in, t)
    e = 0.04 * r_out  # di quanto sporge la stella interna
    dome = ellipsoid((r_out * 1.3 + e, t * 0.5 + e, r_out * 1.3 + e))
    inner = plate(star_points(5, r_out * 0.66, r_in * 0.66, rot_deg=90), t * 0.98, r=0.0, corner=0.035 * r_out)
    inner = inner.translate((0, -t * 0.02, 0)).intersect(dome, k=0.025 * r_out)
    return s, inner


def reeds(r: float, h: float, n: int, depth: float = 0.035, width: float = 0.028) -> SDF:
    """Scanalature sul bordo di una moneta (asse Y): da sottrarre al corpo."""
    step = 2 * math.pi / n

    def f(p):
        th = np.arctan2(p[:, 2], p[:, 0])
        k = np.round(th / step) * step
        c, s = np.cos(k), np.sin(k)
        qx = p[:, 0] * c + p[:, 2] * s
        qz = -p[:, 0] * s + p[:, 2] * c
        q = np.stack([np.abs(qx - r) - depth, np.abs(p[:, 1]) - h, np.abs(qz) - width], axis=1)
        return _len(np.maximum(q, 0.0)) + np.minimum(q.max(axis=1), 0.0)

    e = r + depth
    return SDF(f, (-e, -h, -e), (e, h, e))


def coin(r: float = 1.0, t: float = 0.36, emblem: bool = True, rim: float = 0.16, recess: float = 0.08,
         grooves: int = 0):
    """Moneta con asse lungo Y (faccia verso -Y). Ritorna (corpo, emblema a uovo o None)."""
    h = t / 2
    body = cyl((0, -h, 0), (0, h, 0), r, round=min(0.1 * r, h * 0.6))
    inner = r - rim * r
    cut = union(cyl((0, -h - 0.3, 0), (0, -h + recess * r, 0), inner),
                cyl((0, h - recess * r, 0), (0, h + 0.3, 0), inner))
    body = body.subtract(cut, k=0.03 * r)
    if grooves:
        body = body.subtract(reeds(r, h - 0.06 * r, grooves, depth=0.03 * r, width=0.024 * r), k=0.012 * r)
    emb = None
    if emblem:
        e = plate(egg_outline(inner * 0.5, inner * 1.32), 0.11 * r, r=0.05 * r)
        emb = e.translate((0, -h + recess * r - 0.035 * r, 0))
    return body, emb


def small_coin(r: float, t: float) -> SDF:
    """Moneta semplice per i mucchi (disco pieno con incasso appena accennato, niente emblema)."""
    h = t / 2
    body = cyl((0, -h, 0), (0, h, 0), r, round=h * 0.7)
    cut = union(cyl((0, -h - 0.2, 0), (0, -h + 0.012, 0), r * 0.7),
                cyl((0, h - 0.012, 0), (0, h + 0.2, 0), r * 0.7))
    return body.subtract(cut, k=0.012)


def surface_spots(base: SDF, center, n: int, rmin: float, rmax: float, seed: int, placed=None,
                  zmin: float = -0.8, zmax: float = 0.95, back: float = 0.35) -> SDF:
    """Macchie tonde sulla superficie, preferendo il lato verso la camera (-Y)."""
    rng = np.random.default_rng(seed)
    placed = [] if placed is None else placed
    out = []
    tries = 0
    while len(out) < n and tries < 600:
        tries += 1
        v = rng.normal(size=3)
        v /= np.linalg.norm(v)
        if not (zmin <= v[2] <= zmax) or v[1] > back:
            continue
        p, _ = project(base, center, v)
        r = float(rng.uniform(rmin, rmax))
        if all(np.linalg.norm(p - q) > (r + rq) * 1.25 for q, rq in placed):
            placed.append((p, r))
            out.append(sphere(r, p))
    return union(*out)


def spotted_egg(rad: float, h: float, seed: int = 3, n1: int = 6, n2: int = 7):
    """Uovo comune color crema a macchie, centrato nell'origine: (guscio, macchie scure, macchie chiare)."""
    s = egg(rad, h, taper=0.2)
    c = (0, 0, h * 0.45)
    placed = []
    big = surface_spots(s, c, n1, rad * 0.17, rad * 0.27, seed, placed)
    small = surface_spots(s, c, n2, rad * 0.08, rad * 0.13, seed + 11, placed)
    off = (0, 0, -h * 0.45)
    t, dp = 0.018 * rad, 0.06 * rad
    return s.translate(off), paint(s, big, t, dp).translate(off), paint(s, small, t, dp).translate(off)


def face(head: SDF, center, fwd=(0, -1, 0), s: float = 1.0, dx: float = 0.42, dz: float = 0.06,
         mouth_z: float = -0.3, mouth_w: float = 0.17, blush_dx: float = 0.7, blush_z: float = -0.28):
    """Faccina da pet (occhi lucidi con due riflessi, guance, sorriso) appoggiata sulla testa."""
    f = np.asarray(fwd, dtype=np.float64)
    f /= np.linalg.norm(f)
    up = np.array([0.0, 0.0, 1.0])
    r = np.cross(up, f)
    r /= np.linalg.norm(r)
    u = np.cross(f, r)
    c = np.asarray(center, dtype=np.float64)
    eye_shape = ellipsoid((0.15 * s, 0.09 * s, 0.2 * s))
    frames = [Frame(head, c, tuple(f + r * sx * dx + u * dz), sink=0.05 * s) for sx in (1, -1)]
    eyes = union(*[fr.place(eye_shape) for fr in frames])
    shine = union(*[fr.place(sphere(0.06 * s), (-0.05 * s, -0.075 * s, 0.075 * s)) for fr in frames],
                  *[fr.place(sphere(0.032 * s), (0.055 * s, -0.07 * s, -0.085 * s)) for fr in frames])
    bl = ellipsoid((0.17 * s, 0.04 * s, 0.1 * s))
    blush = union(*[stick(bl, head, c, tuple(f + r * sx * blush_dx + u * blush_z), sink=0.02 * s) for sx in (1, -1)])
    pts = bezier((-mouth_w, 0, mouth_z), (-mouth_w * 0.45, 0, mouth_z - 0.12), (mouth_w * 0.45, 0, mouth_z - 0.12),
                 (mouth_w, 0, mouth_z), 12)
    world = [tuple(c + (r * x + u * z) * s) for x, _, z in pts]
    mouth = tube(project_curve(head, world, tuple(f), inset=0.012 * s, start_back=0.0), 0.036 * s)
    return {"eyes": eyes, "shine": shine, "blush": blush, "mouth": mouth}


def gem(size: float) -> SDF:
    """Gemma sfaccettata (ottaedro schiacciato) con la faccia verso -Y: da usare con smooth=False."""
    g = octahedron(1.0).warp(lambda p: p / np.array([0.85, 0.55, 1.05], dtype=np.float32), pad=0.6)
    return SDF(g.f, (-1, -1, -1.1), (1, 1, 1.1)).scale(size)


def glyph_strokes(polys, r: float, y: float = 0.0) -> SDF:
    return union(*[tube([(x, y, z) for x, z in pl], r) for pl in polys])


def x2_polys(x0: float = 0.0):
    """Tratti di "x2" (x minuscola + 2), base a z=0, altezza ~1."""
    x = [[(x0 - 0.42 - 0.2, 0.0), (x0 - 0.42 + 0.2, 0.52)], [(x0 - 0.42 - 0.2, 0.52), (x0 - 0.42 + 0.2, 0.0)]]
    arc = [(x0 + 0.3 + 0.26 * math.cos(math.radians(a)), 0.7 + 0.26 * math.sin(math.radians(a)))
           for a in np.linspace(165, -38, 14)]
    two = [arc + [(x0 + 0.3 - 0.3, 0.0), (x0 + 0.3 + 0.3, 0.0)]]
    return x + two


# ---------------------------------------------------------------------- registro icone
ICONS: dict[str, tuple] = {}


def icon(view=None, voxel=0.02):
    def deco(fn):
        ICONS[fn.__name__] = (fn, view, voxel)
        return fn
    return deco


# ====================================================================== menu
@icon()
def Shop(m):
    """Bancarella con tenda a strisce, smerlata, e moneta-insegna."""
    W, n = 1.32, 7
    w = 2 * W / n
    counter = box((1.08, 0.52, 0.44), (0, 0, 0.44), round=0.1)
    counter = counter.subtract(union(*[box((0.02, 0.1, 0.34), (x, -0.52, 0.42)) for x in (-0.54, 0.0, 0.54)]), k=0.02)
    add(m, "Counter", counter, WOOD, tris=6000, role="skin")
    top = box((1.2, 0.62, 0.075), (0, 0, 0.94), round=0.05)
    posts = union(*[cyl((sx * 1.05, sy, 0.95), (sx * 1.05, sy, 2.1), 0.075) for sx in (1, -1) for sy in (-0.44, 0.44)])
    add(m, "Top", union(top, posts), WOOD_LIGHT, tris=4000)
    roof = box((W, 0.68, 0.055), round=0.045).rot(17, 0, 0).translate((0, -0.08, 2.19))
    val = [(-W, 0.05), (W, 0.05)]
    for k in reversed(range(n)):
        xc = -W + (k + 0.5) * w
        for i in range(8 + (1 if k == 0 else 0)):
            a = -math.pi * i / 8
            val.append((xc + (w / 2) * math.cos(a), -0.16 + (w / 2) * math.sin(a)))
    valance = plate(val, 0.1, r=0.04).translate((0, -0.735, 1.97))
    awning = union(roof, valance, k=0.02)
    white = union(*[box((w / 2, 3.0, 3.0), (-W + (k + 0.5) * w, 0, 2.0)) for k in range(1, n, 2)])
    add(m, "Awning", awning, RED, tris=7000)
    add(m, "Stripes", paint(awning, white, t=0.016, depth=0.03), WHITE, tris=6000, voxel=0.014)
    body, emb = coin(0.46, 0.17)
    add(m, "Coin", tf(body, (0, -0.05, 2.62)), GOLD, tris=4000, gloss=0.3, voxel=0.015)
    add(m, "Emblem", tf(emb, (0, -0.05, 2.62)), EMBLEM, tris=1200, gloss=0.3, voxel=0.01)
    # uova in vendita sul bancone, di tre colori
    for i, (pos, ry, col) in enumerate((((-0.58, -0.2, 0.97), -8, PINK_LIGHT), ((0.0, -0.24, 0.97), 0, GREEN_LIGHT),
                                        ((0.58, -0.2, 0.97), 8, SKY))):
        add(m, f"Egg{i}", tf(egg(0.22, 0.58), pos, ry=ry), col, tris=1500, voxel=0.014)


@icon()
def Upgrades(m):
    """Grande freccia verde con stelline."""
    poly = [(-1.0, 0.12), (0.0, 1.2), (1.0, 0.12), (0.44, 0.12), (0.44, -1.15), (-0.44, -1.15), (-0.44, 0.12)]
    inner = [(-0.74, 0.24), (0.0, 1.0), (0.74, 0.24), (0.28, 0.24), (0.28, -0.98), (-0.28, -0.98), (-0.28, 0.24)]
    arrow = plate(poly, 0.56, r=0.16, corner=0.05)
    add(m, "Arrow", arrow, GREEN_DARK, tris=8000, role="skin")
    add(m, "Face", paint(arrow, front(inner), t=0.035, depth=0.08), GREEN, tris=5000, voxel=0.015)
    sp = union(tf(sparkle(0.36), (0.98, -0.1, 0.98)), tf(sparkle(0.25), (-0.98, -0.1, 0.66)),
               tf(sparkle(0.18), (0.88, -0.1, -0.62)))
    add(m, "Sparkles", sp, YELLOW, tris=3000, voxel=0.014)


@icon()
def Index(m):
    """Libro aperto con un'impronta di zampa."""
    W, D = 1.12, 0.82

    def bend(p):
        q = p.copy()
        ax = np.minimum(np.abs(p[:, 0]) / W, 1.0)
        q[:, 2] = p[:, 2] - 0.26 * (1 - (1 - ax) ** 2)
        return q

    pages = union(box((W / 2, D, 0.11), (W / 2 + 0.025, 0, 0.11), round=0.07),
                  box((W / 2, D, 0.11), (-W / 2 - 0.025, 0, 0.11), round=0.07)).warp(bend, pad=0.3)
    cover = union(box((W / 2 + 0.08, D + 0.09, 0.05), (W / 2 + 0.03, 0, -0.03), round=0.04),
                  box((W / 2 + 0.08, D + 0.09, 0.05), (-W / 2 - 0.03, 0, -0.03), round=0.04)).warp(bend, pad=0.3)

    def surf(x):
        return 0.22 + 0.26 * (1 - (1 - min(abs(x) / W, 1.0)) ** 2)

    # righe di testo e impronta come forme esatte appena rialzate (la vernice sul campo piegato fa righe)
    lines = [tube([(x, y, surf(x) - 0.012) for x in np.linspace(-0.26, -0.92, 28)], 0.032) for y in (0.42, 0.18, -0.06, -0.3)]
    pads = []
    for (x, y), (rx, ry) in (((0.585, -0.15), (0.22, 0.18)), ((0.36, 0.13), (0.085, 0.1)), ((0.5, 0.25), (0.085, 0.1)),
                             ((0.67, 0.25), (0.085, 0.1)), ((0.81, 0.13), (0.085, 0.1))):
        fr = Frame(pages, (x, y, surf(x) - 0.08), (0, 0, 1), sink=0.0, up=(0, 1, 0))  # parte dentro la pagina
        pads.append(fr.place(ellipsoid((rx, 0.045, ry)), (0, 0.012, 0)))
    tilt = dict(rx=50, rz=-8)
    add(m, "Cover", tf(cover, **tilt), BLUE, tris=6000, role="skin")
    add(m, "Pages", tf(pages, **tilt), CREAM, tris=8000)
    add(m, "Lines", tf(union(*lines), **tilt), (176, 190, 222), tris=2500, voxel=0.012)
    add(m, "Paw", tf(union(*pads), **tilt), WOOD_DARK, tris=3000, voxel=0.012)


@icon()
def Gifts(m):
    """Pacco regalo rosa con nastro e fiocco gialli."""
    body = box((0.9, 0.8, 0.66), (0, 0, 0.66), round=0.12)
    lid = box((1.0, 0.9, 0.2), (0, 0, 1.42), round=0.1)
    band = union(box((0.17, 3, 3)), box((3, 0.17, 3)))
    add(m, "Box", body, PINK, tris=6000, role="skin")
    add(m, "Lid", lid, PINK_LIGHT, tris=5000)
    loop = squash(torus(0.3, 0.09).rot(90, 0, 0), sx=1.3)
    loops = union(tf(loop, (0.38, 0, 1.86), ry=-32), tf(loop, (-0.38, 0, 1.86), ry=32))
    knot = ellipsoid((0.17, 0.15, 0.15), (0, -0.02, 1.7))
    ribbon = union(paint(body, band, t=0.03, depth=0.06), paint(lid, band, t=0.03, depth=0.06))
    add(m, "Ribbon", ribbon, YELLOW, tris=5000, voxel=0.015)
    add(m, "Bow", union(loops, knot, k=0.06), YELLOW, tris=5000, voxel=0.015)


@icon()
def Codes(m):
    """Biglietto arancione con stella e linea tratteggiata."""
    w, h = 1.25, 0.74
    body = plate(rrect(w, h, 0.2), 0.32, r=0.11)
    notches = union(cyl((w, -1, 0), (w, 1, 0), 0.25), cyl((-w, -1, 0), (-w, 1, 0), 0.25))
    holes = union(*[sphere(0.055, (0.5, -0.17, z)) for z in np.linspace(-0.52, 0.52, 6)])
    body = body.subtract(notches, k=0.05).subtract(holes, k=0.02)
    ring = plate(rrect(w - 0.09, h - 0.09, 0.13), 0.08, r=0.03).subtract(
        plate(rrect(w - 0.17, h - 0.17, 0.07), 0.3, r=0.0), k=0.015)
    ring = ring.subtract(notches.offset(0.07), k=0.015)
    star = plate([(x - 0.3, z) for x, z in star_points(5, 0.42, 0.19)], 0.1, r=0.035, corner=0.03)
    deco = union(ring, star).translate((0, -0.16, 0))
    tilt = dict(ry=-14, rz=-8)
    add(m, "Ticket", tf(body, **tilt), ORANGE, tris=7000, role="skin")
    add(m, "Deco", tf(deco, **tilt), ORANGE_LIGHT, tris=5000, voxel=0.013)


@icon()
def Settings(m):
    """Ingranaggio grigio."""
    g = plate(gear_poly(8, 1.2, 0.92), 0.46, r=0.12, corner=0.05)
    g = g.subtract(cyl((0, -1, 0), (0, 1, 0), 0.3), k=0.05)
    add(m, "Gear", tf(g, rz=-8), GREY, tris=9000, role="skin")
    hub = torus(0.47, 0.075).rot(90, 0, 0).translate((0, -0.23, 0))
    add(m, "Hub", tf(hub, rz=-8), GREY_DARK, tris=2500, voxel=0.014)


# ====================================================================== valuta e oggetti
@icon()
def Coin(m):
    """Moneta d'oro spessa con l'uovo in rilievo."""
    body, emb = coin(1.0, 0.5, grooves=48)
    add(m, "Coin", tf(body, rz=6), GOLD, tris=14000, gloss=0.3, role="skin")
    add(m, "Emblem", tf(emb, rz=6), EMBLEM, tris=3000, gloss=0.3, voxel=0.012)


@icon()
def Egg(m):
    """Uovo comune color crema a macchie."""
    shell, s1, s2 = spotted_egg(1.0, 2.7)
    t = dict(ry=8)
    add(m, "Shell", tf(shell, **t), CREAM, tris=12000, role="skin")
    add(m, "Spots", tf(s1, **t), SPOT, tris=4000, voxel=0.014)
    add(m, "Spots2", tf(s2, **t), SPOT_LIGHT, tris=3000, voxel=0.014)


@icon()
def Lock(m):
    """Lucchetto d'oro con arco d'argento."""
    body = box((0.92, 0.44, 0.72), (0, 0, 0), round=0.26)
    R, z0, z1 = 0.56, 0.3, 1.02
    arc = [(-R * math.cos(a), 0, z1 + R * math.sin(a)) for a in np.linspace(0, math.pi, 21)]
    shackle = tube([(-R, 0, z0)] + arc + [(R, 0, z0)], 0.17)
    plate_ = cyl((0, -0.4, 0.02), (0, -0.5, 0.02), 0.36, round=0.04)
    hole = union(cyl((0, -0.47, 0.1), (0, -0.545, 0.1), 0.13, round=0.02),
                 plate([(-0.055, 0.1), (0.055, 0.1), (0.1, -0.25), (-0.1, -0.25)], 0.075, r=0.02).translate((0, -0.507, 0)))
    add(m, "Body", body, GOLD, tris=8000, gloss=0.3, role="skin")
    add(m, "Shackle", shackle, SILVER, tris=6000, gloss=0.35)
    add(m, "Plate", plate_, GOLD_LIGHT, tris=2500, gloss=0.3, voxel=0.014)
    add(m, "Keyhole", hole, INK, tris=1500, voxel=0.01)


@icon()
def Trap(m):
    """Tagliola aperta vista dall'alto: anello di denti, piatto rosso al centro, molle corte."""
    R = 1.0
    jaws, teeth = [], []
    angles = np.linspace(0.17, math.pi - 0.17, 8)
    for side, ang, aa in ((1, 20, angles), (-1, -20, (angles[:-1] + angles[1:]) / 2)):  # denti sfalsati
        arc = [(R * math.cos(a), side * R * math.sin(a), 0.0) for a in np.linspace(0, math.pi, 25)]
        jaws.append(tube(arc, 0.11).rot(ang, 0, 0))
        tt = [round_cone((R * math.cos(a), side * R * math.sin(a), 0.05),
                         ((R - 0.07) * math.cos(a), side * (R - 0.07) * math.sin(a), 0.52), 0.115, 0.018) for a in aa]
        teeth.append(union(*tt).rot(ang, 0, 0))
    metal = union(*jaws, *teeth)
    plate_ = cyl((0, 0, -0.12), (0, 0, -0.02), 0.6, round=0.04)
    pan = cyl((0, 0, -0.04), (0, 0, 0.08), 0.42, round=0.05)
    springs = [box((R + 0.05, 0.11, 0.05), (0, 0, -0.07), round=0.04)]
    for sx in (1, -1):
        springs += [torus(0.17, 0.06).rot(0, 90, 0).translate((sx * (R + 0.08 + 0.12 * i), 0, -0.02)) for i in range(3)]
    tilt = dict(rx=30, rz=-10)
    add(m, "Jaws", tf(metal, **tilt), SILVER, tris=10000, gloss=0.35, role="skin")
    add(m, "Pan", tf(pan, **tilt), RED, tris=3000)
    add(m, "Springs", tf(union(plate_, *springs), **tilt), GREY_DARK, tris=6000, voxel=0.015)


@icon()
def Bat(m):
    """Martello di gomma rossa (manico di legno)."""
    head = cyl((-1.05, 0, 0), (1.05, 0, 0), 0.62, round=0.26)
    rings = union(*[torus(0.6, 0.075).rot(0, 90, 0).translate((sx * 0.66, 0, 0)) for sx in (1, -1)])
    handle = cyl((0, 0, -0.5), (0, 0, -2.25), 0.15, round=0.07)
    grip = cyl((0, 0, -1.6), (0, 0, -2.42), 0.2, round=0.11)
    t = dict(ry=32)
    add(m, "Head", tf(head, **t), RED, tris=8000, role="skin")
    add(m, "Bands", tf(rings, **t), WHITE, tris=4000, voxel=0.015)
    add(m, "Handle", tf(handle, **t), WOOD_LIGHT, tris=3000)
    add(m, "Grip", tf(grip, **t), RED_DARK, tris=3000)


@icon()
def Slap(m):
    """Mano aperta da cartone con linee di movimento."""
    palm = union(box((0.5, 0.2, 0.5), round=0.2), ellipsoid((0.56, 0.24, 0.54), (0, 0.02, -0.04)), k=0.1)
    fingers = []
    for x, L, a, r in ((-0.39, 0.72, -13, 0.135), (-0.13, 0.9, -4, 0.15), (0.13, 0.86, 4, 0.15), (0.38, 0.68, 13, 0.14)):
        e = (x + L * math.sin(math.radians(a)), -0.02, 0.3 + L * math.cos(math.radians(a)))
        fingers.append(capsule((x, 0, 0.3), e, r))
    thumb = capsule((0.42, -0.04, -0.12), (0.92, -0.12, 0.3), 0.16)
    wrist = cyl((0, 0, -0.3), (0, 0, -0.95), 0.33, round=0.1)
    hand = union(palm, *fingers, thumb, wrist, k=0.08)
    cuff = cyl((0, 0, -0.74), (0, 0, -1.2), 0.42, round=0.12)
    t = dict(ry=16)
    add(m, "Hand", tf(hand, **t), SKIN, tris=9000, role="skin")
    add(m, "Cuff", tf(cuff, **t), WHITE, tris=3000)
    lines = [tube([(-0.95, -0.05, z), (-0.95 - L, -0.05, z - 0.1)], [0.08, 0.035])
             for z, L in ((0.8, 0.7), (0.32, 0.95), (-0.16, 0.66))]
    add(m, "Lines", union(*lines), (206, 236, 255), tris=2500, voxel=0.015)


@icon()
def Star(m):
    """Stella d'oro bombata."""
    s, inner = star_with_face(1.2, 0.56, 0.74)
    t = dict(rz=8)
    add(m, "Star", tf(s, **t), GOLD, tris=9000, gloss=0.3, role="skin")
    add(m, "Inner", tf(inner, **t), GOLD_LIGHT, tris=5000, gloss=0.3, voxel=0.014)


# ====================================================================== potenziamenti
@icon()
def Speed(m):
    """Scarpa da corsa alata con un fulmine sul fianco."""
    def toe_up(p):
        q = p.copy()
        q[:, 2] -= 0.3 * np.clip((p[:, 0] - 0.55) / 0.7, 0, 1) ** 2
        return q

    sole = box((1.22, 0.47, 0.13), (0.05, 0, 0.13), round=0.12).warp(toe_up, pad=0.35)
    upper = union(ellipsoid((0.78, 0.44, 0.42), (0.42, 0, 0.36)), box((0.52, 0.44, 0.55), (-0.62, 0, 0.62), round=0.34), k=0.35)
    tongue = box((0.15, 0.28, 0.3), (-0.22, 0, 1.0), round=0.14).rot(0, -22, 0, pivot=(-0.22, 0, 0.82))
    upper = union(upper, tongue, k=0.08)
    collar = torus(0.33, 0.09).rot(0, 8, 0).translate((-0.64, 0, 1.15))
    hole = ellipsoid((0.27, 0.27, 0.06), (-0.64, 0, 1.17))
    laces = []
    for x in (0.12, -0.08):
        p, n = project(upper, (x, 0, 0.3), (0.3, 0, 1.0))
        c = p - n * 0.02
        laces.append(capsule((c[0], -0.3, c[2]), (c[0], 0.3, c[2]), 0.06))
    toe = paint(upper, sphere(0.48, (1.12, 0, 0.3)), t=0.025)
    bolt = paint(upper, front([(x * 0.62 - 0.22, z * 0.62 + 0.55) for x, z in BOLT]), t=0.03, depth=0.06)
    feathers = [ellipsoid((L / 2, 0.06, 0.13)).translate((-L / 2, 0, 0)).rot(0, a, 0)
                for L, a in ((0.82, 18), (0.74, 40), (0.62, 62), (0.48, 84))]
    wing = union(*feathers, k=0.05).translate((-0.72, -0.47, 0.82))
    add(m, "Upper", upper, RED, tris=9000, role="skin")
    add(m, "Sole", union(sole, collar, *laces), WHITE, tris=7000)
    add(m, "Toe", toe, WHITE, tris=3000, voxel=0.015)
    add(m, "Hole", hole, INK, tris=800, voxel=0.015)
    add(m, "Bolt", bolt, YELLOW, tris=2500, voxel=0.012)
    add(m, "Wing", wing, WHITE, tris=4000, voxel=0.015)


@icon()
def Strength(m):
    """Braccio che esce da una manica e mostra il bicipite, con polsino rosso."""
    sh, el, wr = (-1.2, 0.0, -0.58), (0.42, 0.0, -0.58), (0.58, 0.0, 0.36)
    upper = round_cone(sh, el, 0.3, 0.3)
    bicep = ellipsoid((0.5, 0.38, 0.47), (-0.2, -0.02, -0.16))
    fore = round_cone(el, wr, 0.33, 0.25)
    fist = box((0.36, 0.32, 0.34), (0.6, 0, 0.76), round=0.24)
    ridges = [capsule((0.36, -0.27, z), (0.84, -0.27, z), 0.08) for z in (0.6, 0.76, 0.92)]
    thumb = capsule((0.32, -0.24, 0.62), (0.64, -0.33, 0.52), 0.11)
    arm = union(upper, bicep, fore, fist, k=0.12)
    arm = union(arm, *ridges, thumb, k=0.04)
    sleeve = ccone((-1.36, 0, -0.55), (-0.84, 0, -0.55), 0.5, 0.47, round=0.13)
    hem = torus(0.47, 0.07).rot(0, 90, 0).translate((-0.86, 0, -0.55))
    band = torus(0.31, 0.1).rot(0, 10, 0).translate((0.56, 0, 0.32))
    add(m, "Arm", arm, SKIN, tris=10000, role="skin")
    add(m, "Sleeve", union(sleeve, hem, k=0.03), BLUE, tris=4000)
    add(m, "Band", band, RED, tris=3000, voxel=0.015)
    sp = union(tf(sparkle(0.34), (-0.78, -0.4, 0.55)), tf(sparkle(0.2), (-0.25, -0.4, 0.78)))
    add(m, "Sparkles", sp, WHITE, tris=2000, voxel=0.012)


@icon()
def Backpack(m):
    """Zainetto verde con tasca, patta e fibbia dorata."""
    body = union(box((0.82, 0.48, 0.8), (0, 0, 0.8), round=0.4), ellipsoid((0.82, 0.48, 0.5), (0, 0, 1.45)), k=0.25)
    pocket = box((0.6, 0.2, 0.4), (0, -0.47, 0.56), round=0.18)
    flap = paint(body, ellipsoid((0.98, 0.9, 0.72), (0, 0.0, 2.02)), t=0.03, depth=0.07)
    strap = box((0.11, 0.05, 0.26), (0, -0.505, 1.24), round=0.04)
    handle = tube(bezier((-0.28, 0, 1.86), (-0.25, 0, 2.2), (0.25, 0, 2.2), (0.28, 0, 1.86), 12), 0.075)
    sides = union(*[box((0.14, 0.3, 0.3), (sx * 0.84, 0, 0.55), round=0.12) for sx in (1, -1)])
    zipper = union(tube([(-0.44, -0.672, 0.88), (0.44, -0.672, 0.88)], 0.03), capsule((0.26, -0.7, 0.86), (0.28, -0.72, 0.72), 0.045))
    add(m, "Body", body, GREEN, tris=9000, role="skin")
    add(m, "Details", union(pocket, flap, strap, handle, sides), GREEN_DARK, tris=8000)
    add(m, "Buckle", box((0.16, 0.06, 0.11), (0, -0.55, 1.06), round=0.04), GOLD, tris=1500, gloss=0.3, voxel=0.012)
    add(m, "Zipper", zipper, WHITE, tris=1500, voxel=0.012)


@icon()
def Incubator(m):
    """Uovo in un nido che brilla di calore, sopra una piastra con anello luminoso, e onde di calore."""
    base = cyl((0, 0, 0), (0, 0, 0.44), 1.12, round=0.16)
    glow_band = torus(1.115, 0.065, (0, 0, 0.22))
    nest = torus(0.74, 0.3, (0, 0, 0.7))
    tufts = [ellipsoid((0.26, 0.2, 0.17)).rot(0, 0, math.degrees(a) + 90).translate(
        (0.78 * math.cos(a), 0.78 * math.sin(a), 0.86 + 0.05 * (i % 2))) for i, a in enumerate(np.linspace(0, 2 * math.pi, 14, endpoint=False))]
    nest = union(nest, *tufts, k=0.1)
    straws = []
    for i in range(9):
        th0 = 2 * math.pi * i / 9 + 0.3
        pts = []
        for j in range(6):
            th, ph = th0 + j * 0.09, -0.6 + j * 0.3
            rr = 0.74 + 0.33 * math.cos(ph)
            pts.append((rr * math.cos(th), rr * math.sin(th), 0.7 + 0.33 * math.sin(ph)))
        straws.append(tube(pts, 0.032))
    bowl = cyl((0, 0, 0.42), (0, 0, 0.66), 0.8, round=0.08)  # fondo del nido, rovente
    shell, s1, s2 = spotted_egg(0.62, 1.62, seed=8, n1=5, n2=5)
    pos = (0, 0, 0.5 + 1.62 * 0.45)
    waves = []
    for sx in (1, -1):
        zs = np.linspace(1.1, 1.85, 14)
        pts = [(sx * (1.0 + 0.08 * math.sin(2 * math.pi * (z - 1.1) / 0.75)), -0.2, z) for z in zs]
        waves.append(tube(pts, list(np.linspace(0.085, 0.05, 14))))
    add(m, "Base", base, SLATE, tris=5000, role="skin")
    add(m, "Glow", union(glow_band, bowl), (255, 160, 40), material="Neon", role="glow", tris=4000, voxel=0.015)
    add(m, "Nest", nest, WOOD, tris=7000)
    add(m, "Straws", fast_union(straws), WOOD_LIGHT, tris=3000, voxel=0.012)
    add(m, "Shell", tf(shell, pos), CREAM, tris=7000)
    add(m, "Spots", tf(s1, pos), SPOT, tris=2500, voxel=0.013)
    add(m, "Spots2", tf(s2, pos), SPOT_LIGHT, tris=2000, voxel=0.013)
    add(m, "Heat", union(*waves), (255, 200, 90), tris=2500, voxel=0.015)


@icon()
def HatchSpeed(m):
    """Cronometro azzurro con un uovo davanti."""
    body = cyl((0, -0.26, 0), (0, 0.26, 0), 1.0, round=0.2)
    dial = paint(body, cyl((0, -1, 0), (0, 0, 0), 0.76), t=0.03, depth=0.06)
    ticks = union(*[capsule((0.52 * math.cos(a), -0.3, 0.52 * math.sin(a)), (0.64 * math.cos(a), -0.3, 0.64 * math.sin(a)), 0.05)
                    for a in (0, math.pi / 2, math.pi)])
    hand = union(capsule((0, -0.31, 0), (0.3, -0.31, 0.42), 0.065), sphere(0.1, (0, -0.31, 0)))
    crown = union(cyl((0, 0, 0.95), (0, 0, 1.2), 0.13), cyl((0, 0, 1.18), (0, 0, 1.38), 0.28, round=0.08))
    a = math.radians(45)
    side = union(cyl((0.92 * math.cos(a), 0, 0.92 * math.sin(a)), (1.08 * math.cos(a), 0, 1.08 * math.sin(a)), 0.1),
                 sphere(0.13, (1.12 * math.cos(a), 0, 1.12 * math.sin(a))))
    shell, s1, s2 = spotted_egg(0.5, 1.34, seed=4, n1=5, n2=4)
    ep = dict(pos=(-0.78, -0.56, -0.45), ry=-10)
    add(m, "Body", body, BLUE, tris=8000, role="skin")
    add(m, "Dial", dial, WHITE, tris=4000, voxel=0.014)
    add(m, "Ticks", union(ticks, hand), INK, tris=2000, voxel=0.012)
    add(m, "Crown", union(crown, side), SILVER, tris=3000, gloss=0.35, voxel=0.015)
    add(m, "Shell", tf(shell, **ep), CREAM, tris=6000)
    add(m, "Spots", tf(s1, **ep), SPOT, tris=2000, voxel=0.012)
    add(m, "Spots2", tf(s2, **ep), SPOT_LIGHT, tris=1500, voxel=0.012)


@icon()
def Pedestal(m):
    """Piedistallo tondo con stella d'oro e bordi dorati."""
    base = cyl((0, 0, 0), (0, 0, 0.3), 1.1, round=0.1)
    flutes = union(*[capsule((0.66 * math.cos(a), 0.66 * math.sin(a), 0.5), (0.66 * math.cos(a), 0.66 * math.sin(a), 1.0), 0.07)
                     for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)])
    column = cyl((0, 0, 0.25), (0, 0, 1.25), 0.62).subtract(flutes, k=0.03)
    top = cyl((0, 0, 1.2), (0, 0, 1.46), 1.0, round=0.1)
    ped = union(base, column, top, k=0.06)
    rims = union(torus(1.09, 0.06, (0, 0, 0.15)), torus(0.99, 0.06, (0, 0, 1.33)))
    s, inner = star_with_face(0.82, 0.38, 0.5)
    sp = dict(pos=(0, 0, 2.34), rz=10)
    add(m, "Pedestal", ped, LAVENDER, tris=8000, role="skin")
    add(m, "Rims", rims, GOLD, tris=4000, gloss=0.3, voxel=0.015)
    add(m, "Star", tf(s, **sp), GOLD, tris=6000, gloss=0.3)
    add(m, "StarInner", tf(inner, **sp), GOLD_LIGHT, tris=3500, gloss=0.3, voxel=0.013)
    sparks = union(tf(sparkle(0.24), (0.98, -0.3, 2.8)), tf(sparkle(0.17), (-0.95, -0.3, 2.18)))
    add(m, "Sparkles", sparks, WHITE, tris=2000, voxel=0.012)


@icon()
def Barrier(m):
    """Scudo laser rosso luminoso in una cornice scura."""
    frame_ = plate(shield_poly(), 0.46, r=0.14, corner=0.05)
    panel_poly = shield_poly(0.76, 0.72, -0.98)
    frame_ = frame_.subtract(plate(panel_poly, 0.4, r=0.0, corner=0.04).translate((0, -0.3, 0)), k=0.03)
    panel = plate(shield_poly(0.79, 0.75, -1.02), 0.3, r=0.06, corner=0.04).translate((0, -0.06, 0))
    clip = plate(shield_poly(0.66, 0.62, -0.84), 2.0, r=0.0)
    lasers = union(*[capsule((-1, -0.215, z), (1, -0.215, z), 0.05) for z in (0.36, 0.0, -0.36)]).intersect(clip)
    rivets = union(*[sphere(0.07, (x, -0.22, z)) for x, z in ((-0.86, 0.86), (0.86, 0.86), (0, -1.12))])
    add(m, "Frame", frame_, SLATE, tris=8000, role="skin")
    add(m, "Panel", panel, (255, 40, 64), material="Neon", role="glow", tris=4000)
    add(m, "Lasers", lasers, (255, 200, 210), material="Neon", role="glow", tris=2500, voxel=0.012)
    add(m, "Rivets", rivets, SILVER, tris=1200, gloss=0.35, voxel=0.012)


# ====================================================================== pass e prodotti del negozio
@icon()
def VIP(m):
    """Corona d'oro a cinque punte con gemme e velluto rosso."""
    Ro, Ri, zl, zh, k, fl = 0.98, 0.84, 0.62, 1.32, 5, 0.12
    th0 = -math.pi / 2

    def crown_f(p):
        rho = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2)
        th = np.arctan2(p[:, 1], p[:, 0])
        u = (th - th0) * k / (2 * np.pi)
        fr = np.abs(u - np.round(u))
        ztop = zl + (zh - zl) * np.clip(1 - 2 * fr, 0, 1) ** 1.3
        z = p[:, 2]
        d = smax(rho - (Ro + fl * z), (Ri + fl * z) - rho, 0.04)
        d = smax(d, z - ztop, 0.07)
        return smax(d, -z, 0.04)

    crown = SDF(crown_f, (-1.3, -1.3, -0.05), (1.3, 1.3, 1.45))
    rm = (Ro + Ri) / 2 + fl * zh
    balls = union(*[sphere(0.13, (rm * math.cos(th0 + 2 * math.pi * i / k), rm * math.sin(th0 + 2 * math.pi * i / k), zh + 0.06))
                    for i in range(k)])
    bead = torus(Ro + 0.01, 0.06, (0, 0, 0.07))
    velvet = ellipsoid((0.86, 0.86, 0.74), (0, 0, 0.42))
    gold = union(crown, balls, bead, sphere(0.12, (0, 0, 1.18)))
    rb = Ro + fl * 0.33  # raggio esterno della fascia all'altezza delle gemme
    ruby = ellipsoid((0.21, 0.11, 0.25), (0, -rb + 0.03, 0.33))
    saph = []
    for a in (-90 + 48, -90 - 48):
        g = ellipsoid((0.14, 0.09, 0.16)).rot(0, 0, a + 90)
        saph.append(g.translate((rb * math.cos(math.radians(a)) * 0.97, rb * math.sin(math.radians(a)) * 0.97, 0.33)))
    t = dict(rx=10)
    add(m, "Crown", tf(gold, **t), GOLD, tris=12000, gloss=0.3, role="skin")
    add(m, "Velvet", tf(velvet, **t), RED_DARK, tris=4000, gloss=0.05)
    add(m, "Ruby", tf(ruby, **t), (255, 34, 84), tris=2000, gloss=0.5, voxel=0.012)
    add(m, "Sapphires", tf(union(*saph), **t), (60, 150, 255), tris=2000, gloss=0.5, voxel=0.012)


@icon()
def DoubleCoins(m):
    """Due monete con un grande "x2" in rilievo."""
    for i, (pos, rz, rx) in enumerate((((-0.45, 0.35, 0.5), 18, 6), ((0.25, -0.05, 0.05), -14, 0))):
        body, emb = coin(0.82, 0.32)
        add(m, f"Coin{i}", tf(body, pos, rx=rx, rz=rz), GOLD, tris=7000, gloss=0.3, role="skin" if i == 0 else "detail")
        add(m, f"Emblem{i}", tf(emb, pos, rx=rx, rz=rz), EMBLEM, tris=2000, gloss=0.3, voxel=0.012)
    polys = x2_polys()
    txt = dict(pos=(0.62, -0.62, -0.95), rz=8)
    # bordo scuro: tratti piu' grossi e arretrati, il davanti dei tratti chiari resta sporgente
    fill = squash(glyph_strokes(polys, 0.13), sx=1.05, sz=1.05)
    back = squash(glyph_strokes(polys, 0.21, y=0.13), sx=1.05, sz=1.05)
    add(m, "Text", tf(fill, **txt), (120, 240, 80), tris=6000, voxel=0.013)
    add(m, "TextBack", tf(back, **txt), (22, 108, 46), tris=6000, voxel=0.013)


@icon()
def SkipHatch(m):
    """Uovo con una crepa e la doppia freccia "avanti veloce"."""
    shell, s1, s2 = spotted_egg(0.82, 2.2, seed=5, n1=5, n2=5)
    crack2d = [(-0.8, 0.28), (-0.55, 0.42), (-0.35, 0.22), (-0.12, 0.44), (0.08, 0.22), (0.3, 0.42), (0.52, 0.24), (0.8, 0.36)]
    crack = tube(project_curve(shell, [(x, 0.0, z) for x, z in crack2d], (0, -1, 0), inset=0.015, start_back=0.0), 0.045)
    ep = dict(pos=(-0.45, 0.3, 0.12), ry=-10)
    add(m, "Shell", tf(shell, **ep), CREAM, tris=8000, role="skin")
    add(m, "Spots", tf(s1, **ep), SPOT, tris=2500, voxel=0.013)
    add(m, "Spots2", tf(s2, **ep), SPOT_LIGHT, tris=2000, voxel=0.013)
    add(m, "Crack", tf(crack, **ep), WOOD_DARK, tris=2000, voxel=0.012)
    tri = [(-0.36, 0.5), (0.44, 0.0), (-0.36, -0.5)]
    arrows = union(*[plate([(x + dx, z) for x, z in tri], 0.34, r=0.13, corner=0.06) for dx in (0.0, 0.56)])
    back = arrows.offset(0.07).translate((0, 0.09, 0))
    ap = dict(pos=(0.32, -0.62, -0.62), rz=-6)
    add(m, "Arrows", tf(arrows, **ap), (70, 190, 255), tris=5000)
    add(m, "ArrowsBack", tf(back, **ap), BLUE_DARK, tris=5000)


@icon()
def Luck(m):
    """Quadrifoglio con cuori bombati."""
    s = 0.62
    leaves, inner = [], []
    for phi in (45, 135, 225, 315):
        th = 90 - phi
        d = np.array([math.cos(math.radians(phi)), 0, math.sin(math.radians(phi))])
        leaf = plate(heart_poly(s), 0.3, r=0.12).rot(0, th, 0)
        leaf = leaf.intersect(ellipsoid((0.8, 0.17, 0.8), tuple(d * 0.62)), k=0.05)
        leaves.append(leaf)
        # cuore interno in rilievo: lastra un po' piu' spessa della foglia, tagliata dalla stessa cupola allargata
        e = 0.03
        hp = [(x, y + 0.42 * s) for x, y in heart_poly(s * 0.5)]
        ih = plate(hp, 0.3 + 2 * e, r=0.0).rot(0, th, 0)
        inner.append(ih.intersect(ellipsoid((0.8 + e, 0.17 + e, 0.8 + e), tuple(d * 0.62)), k=0.02))
    clover = union(*leaves, k=0.04)
    stem = tube(bezier((0.0, 0.07, -0.15), (0.02, 0.07, -0.85), (0.25, 0.07, -1.25), (0.62, 0.05, -1.45), 12),
                [0.11 - 0.003 * i for i in range(13)])
    t = dict(rz=-10)
    add(m, "Leaves", tf(clover, **t), GREEN, tris=10000, role="skin")
    add(m, "Inner", tf(union(*inner), **t), GREEN_LIGHT, tris=4000, voxel=0.013)
    add(m, "Stem", tf(union(stem, sphere(0.13, (0, -0.02, 0))), **t), GREEN_DARK, tris=3000, voxel=0.015)
    sp = union(tf(sparkle(0.28), (1.0, -0.2, 1.0)), tf(sparkle(0.18), (-1.05, -0.2, -0.8)))
    add(m, "Sparkles", sp, YELLOW, tris=2000, voxel=0.012)


@icon()
def CoinsSmall(m):
    """Sacchetto di monete legato, con moneta sul davanti."""
    bulb = ellipsoid((0.98, 0.86, 0.84), (0, 0, 0.84))
    neck = round_cone((0, 0, 1.3), (0, 0, 1.7), 0.42, 0.3)

    def wavy(p):
        q = p.copy()
        th = np.arctan2(p[:, 1], p[:, 0])
        f = 1.0 / (1.0 + 0.1 * np.sin(7 * th) * np.clip((p[:, 2] - 1.72) / 0.3, 0, 1))
        q[:, 0] *= f
        q[:, 1] *= f
        return q

    ruffle = ccone((0, 0, 1.64), (0, 0, 2.05), 0.3, 0.62, round=0.07).warp(wavy, pad=0.12)
    pouch = union(union(bulb, neck, k=0.3), ruffle, k=0.06)
    pouch = pouch.subtract(ellipsoid((0.5, 0.5, 0.2), (0, 0, 2.08)), k=0.05)
    tie = torus(0.37, 0.09, (0, 0, 1.6))
    fr = Frame(bulb, (0, 0, 0.84), (0.12, -1.0, -0.02), sink=0.03)
    cb, ce = coin(0.46, 0.14)
    coins, embs = [fr.place(cb)], [fr.place(ce)]
    for pos, rx, rz in (((0.15, 0.0, 2.1), -25, 28), ((-0.2, 0.12, 2.04), 15, -32)):
        b, e = coin(0.34, 0.12)
        coins.append(tf(b, pos, rx=rx, rz=rz))
        embs.append(tf(e, pos, rx=rx, rz=rz))
    for pos, rx, rz in (((0.92, -0.42, 0.06), 90, 0), ((-0.95, -0.35, 0.3), 10, 30)):
        b, e = coin(0.34, 0.12)
        coins.append(tf(b, pos, rx=rx, rz=rz))
        embs.append(tf(e, pos, rx=rx, rz=rz))
    add(m, "Pouch", pouch, TAN, tris=10000, role="skin")
    add(m, "Tie", tie, RED, tris=3000, voxel=0.015)
    add(m, "Coins", union(*coins), GOLD, tris=8000, gloss=0.3, voxel=0.014)
    add(m, "Emblems", union(*embs), EMBLEM, tris=3000, gloss=0.3, voxel=0.01)


@icon()
def CoinsMedium(m):
    """Forziere aperto pieno di monete."""
    W, D, H = 1.1, 0.7, 0.58
    body = box((W, D, H), (0, 0, H), round=0.1)
    bands = union(*[box((0.12, D + 0.035, H + 0.02), (sx * 0.7, 0, H), round=0.05) for sx in (1, -1)],
                  box((W + 0.035, D + 0.035, 0.07), (0, 0, 2 * H - 0.06), round=0.04),
                  box((W + 0.035, D + 0.035, 0.07), (0, 0, 0.07), round=0.04))
    lockp = box((0.19, 0.05, 0.22), (0, -D - 0.03, 2 * H - 0.3), round=0.05)
    keyhole = union(cyl((0, -D - 0.07, 2 * H - 0.25), (0, -D - 0.1, 2 * H - 0.25), 0.055),
                    box((0.025, 0.02, 0.07), (0, -D - 0.085, 2 * H - 0.33), round=0.01))
    hinge = (0, D, 2 * H)
    shell = cyl((-W, 0, 0), (W, 0, 0), D, round=0.08).subtract(cyl((-W + 0.09, 0, 0), (W - 0.09, 0, 0), D - 0.09))
    lid = shell.intersect(above(0.0)).translate((0, 0, 2 * H)).rot(-104, 0, 0, pivot=hinge)
    lid_bands = union(*[cyl((sx * 0.7 - 0.12, 0, 0), (sx * 0.7 + 0.12, 0, 0), D + 0.035, round=0.03) for sx in (1, -1)])
    lid_bands = lid_bands.subtract(cyl((-W, 0, 0), (W, 0, 0), D - 0.05)).intersect(above(0.0))
    lid_bands = lid_bands.translate((0, 0, 2 * H)).rot(-104, 0, 0, pivot=hinge)
    heap = ellipsoid((1.0, 0.62, 0.44), (0, -0.02, 2 * H - 0.04))
    rng = np.random.default_rng(7)
    coins = []
    for _ in range(20):
        v = rng.normal(size=3)
        v[2] = abs(v[2]) * 1.6 + 0.4
        v[1] = -abs(v[1]) - 0.2
        v /= np.linalg.norm(v)
        fr = Frame(heap, (0, -0.02, 2 * H - 0.04), tuple(v), sink=0.03)
        coins.append(fr.place(small_coin(0.28, 0.09).rot(float(rng.uniform(-18, 18)), 0, float(rng.uniform(-18, 18)))))
    spill = [tf(small_coin(0.26, 0.08), (0.78, -0.98, 0.04), rx=90), tf(small_coin(0.26, 0.08), (-0.55, -1.0, 0.28), rx=12, rz=25)]
    gems_ = union(tf(gem(0.17), (-0.35, -0.42, 1.52), rx=-30, rz=15), tf(gem(0.15), (0.48, -0.36, 1.5), rx=-30, rz=-20))
    add(m, "Chest", body, WOOD, tris=6000, role="skin")
    add(m, "Lid", lid, WOOD, tris=6000)
    add(m, "Bands", union(bands, lockp, lid_bands), GOLD, tris=8000, gloss=0.3)
    add(m, "Keyhole", keyhole, INK, tris=800, voxel=0.01)
    add(m, "Heap", heap, GOLD_DEEP, tris=4000, gloss=0.3)
    add(m, "Coins", fast_union(coins + spill), GOLD, tris=10000, gloss=0.3, voxel=0.013)
    add(m, "Gems", gems_, (255, 46, 96), tris=600, gloss=0.5, voxel=0.012, smooth=False)


@icon()
def CoinsLarge(m):
    """Montagna di monete con pile ai lati, gemme e un grande luccichio."""
    mound = union(round_cone((0, 0.05, -0.2), (0, 0.05, 1.42), 1.3, 0.3), ellipsoid((1.32, 0.95, 0.85)), k=0.3)
    mound = mound.intersect(above(0.0))
    mc = (0, 0.05, 0.4)
    rng = np.random.default_rng(11)
    coins = []
    tries = 0
    pts = []
    while len(coins) < 64 and tries < 3000:
        tries += 1
        v = rng.normal(size=3)
        v[2] = abs(v[2]) * 1.2 + 0.05
        v /= np.linalg.norm(v)
        if v[1] > 0.5:
            continue
        p, _ = project(mound, mc, tuple(v))
        if any(np.linalg.norm(p - q) < 0.3 for q in pts):
            continue
        pts.append(p)
        fr = Frame(mound, mc, tuple(v), sink=0.03)
        c = small_coin(0.31, 0.1).rot(float(rng.uniform(-20, 20)), 0, float(rng.uniform(-20, 20)))
        coins.append(fr.place(c))
    for (x, y), nstack in (((-1.3, -0.55), 6), ((1.36, -0.42), 4)):
        for i in range(nstack):
            coins.append(tf(small_coin(0.3, 0.1), (x + rng.uniform(-0.03, 0.03), y + rng.uniform(-0.03, 0.03), 0.05 + i * 0.102), rx=90))
    big, emb = coin(0.52, 0.17)
    bp = dict(pos=(0.3, -1.08, 0.52), rz=12, rx=-6)
    gems_ = union(tf(gem(0.17), (-0.5, -0.78, 0.98), rx=-35, rz=20), tf(gem(0.15), (0.55, -0.62, 1.38), rx=-35, rz=-15))
    add(m, "Mound", mound, GOLD_DEEP, tris=5000, gloss=0.3, role="skin")
    add(m, "Coins", fast_union(coins), GOLD, tris=18000, gloss=0.3, voxel=0.014)
    add(m, "BigCoin", tf(big, **bp), GOLD, tris=4000, gloss=0.3, voxel=0.014)
    add(m, "Emblem", tf(emb, **bp), EMBLEM, tris=1500, gloss=0.3, voxel=0.01)
    add(m, "Gems", gems_, (70, 150, 255), tris=600, gloss=0.5, voxel=0.012, smooth=False)
    sp = union(tf(sparkle(0.46), (0.95, -0.6, 1.75)), tf(sparkle(0.26), (-1.0, -0.6, 1.3)))
    add(m, "Sparkles", sp, WHITE, tris=2500, voxel=0.012)


# ====================================================================== eventi
CAM = np.asarray(DEFAULT_VIEW, dtype=np.float64) / np.linalg.norm(DEFAULT_VIEW)


@icon()
def Meteor(m):
    """Meteora viola con coda di fiamme a lingue (viola fuori, rosa, nucleo giallo)."""
    rng = np.random.default_rng(2)
    bumps = []
    for _ in range(6):
        v = rng.normal(size=3)
        v /= np.linalg.norm(v)
        bumps.append(sphere(0.36, tuple(v * 0.68)))
    rock = union(sphere(0.88), *bumps, k=0.25)
    craters, rims = [], []
    for v, r in (((-0.5, -1.0, 0.25), 0.25), ((0.25, -1.0, -0.3), 0.19), ((-0.25, -1.0, -0.6), 0.14), ((0.1, -1.0, 0.45), 0.13)):
        p, n = project(rock, (0, 0, 0), v)
        craters.append(sphere(r, tuple(p + n * r * 0.45)))
        rims.append(sphere(r * 1.35, tuple(p)))
    rock_c = rock.subtract(union(*craters), k=0.06)
    c0 = np.array([0.0, 0.2, 0.0])
    main = np.array([1.0, 0.45, 0.85])
    main /= np.linalg.norm(main)
    perp = np.array([-0.85, 0.0, 1.0])
    perp -= main * (perp @ main)
    perp /= np.linalg.norm(perp)
    tongues = ((0.0, 2.55, 1.0), (0.34, 2.0, 0.72), (-0.34, 2.05, 0.72), (0.66, 1.4, 0.55), (-0.66, 1.45, 0.55))

    def flame(scale, shift):
        parts = []
        for ang, L, rr in tongues:
            d = main * math.cos(ang) + perp * math.sin(ang)
            a = c0 + shift
            L2 = L * scale
            pts = bezier(a, a + d * L2 * 0.35 + perp * 0.12 * scale, a + d * L2 * 0.7 - perp * 0.1 * scale, a + d * L2, 10)
            radii = [max(0.86 * rr * scale * (1 - i / 10) ** 0.95, 0.015) for i in range(11)]
            parts.append(tube(pts, radii))
        return union(*parts, k=0.13 * scale)

    outer = flame(1.0, np.zeros(3))
    mid = flame(0.74, main * 0.35 + CAM * 0.4)
    core = flame(0.48, main * 0.75 + CAM * 0.55)
    embers = union(*[sphere(r, p) for p, r in (((2.25, 0.6, 1.95), 0.09), ((2.6, 0.6, 1.3), 0.07), ((1.5, 0.6, 2.5), 0.065))])
    add(m, "Rock", rock_c, (124, 74, 214), tris=8000, role="skin")
    add(m, "Craters", paint(rock_c, union(*rims), t=0.015, depth=0.05), (74, 40, 150), tris=3000, voxel=0.013)
    add(m, "Flame", union(outer, embers), (140, 60, 255), material="Neon", role="glow", tris=8000)
    add(m, "FlameMid", mid, (255, 78, 196), material="Neon", role="glow", tris=5000)
    add(m, "Core", core, (255, 214, 96), material="Neon", role="glow", tris=3000)


@icon()
def GoldenHour(m):
    """Sole d'oro sorridente."""
    head = ellipsoid((1.0, 0.66, 1.0))
    rays = []
    for i in range(12):
        a = math.radians(90 + i * 30)
        L = 1.66 if i % 2 == 0 else 1.4
        d = np.array([math.cos(a), 0, math.sin(a)])
        rays.append(round_cone(tuple(d * 0.82), tuple(d * L), 0.25 if i % 2 == 0 else 0.2, 0.075))
    rays = squash(union(*rays), sy=0.55)
    fc = face(head, (0, 0, 0), s=1.12, dx=0.36, dz=0.1, mouth_z=-0.26, mouth_w=0.2, blush_dx=0.62, blush_z=-0.2)
    add(m, "Sun", head, GOLD, tris=8000, gloss=0.3, role="skin")
    add(m, "Rays", rays, ORANGE, tris=8000, gloss=0.3)
    add(m, "Eyes", fc["eyes"], EYE, role="eye", tris=1500, voxel=0.012)
    add(m, "Shine", fc["shine"], WHITE, role="shine", tris=800, voxel=0.01)
    add(m, "Blush", fc["blush"], (255, 110, 110), tris=800, voxel=0.012)
    add(m, "Mouth", fc["mouth"], MOUTH, tris=1000, voxel=0.01)


@icon()
def Avalanche(m):
    """Montagna innevata e grande palla di neve che rotola, con schizzi e linee di movimento."""
    def ridges(p):
        q = p.copy()
        th = np.arctan2(p[:, 1], p[:, 0])
        f = 1.0 / (1.0 + 0.07 * np.sin(6 * th + 1.7 * p[:, 2]))
        q[:, 0] *= f
        q[:, 1] *= f
        return q

    peak1 = round_cone((-0.35, 0.3, -0.3), (-0.3, 0.3, 1.95), 1.35, 0.14)
    peak2 = round_cone((0.95, 0.65, -0.3), (0.85, 0.65, 1.15), 0.95, 0.12)
    mountain = union(peak1, peak2, k=0.25).warp(ridges, pad=0.15).intersect(above(0.0))

    def snowline(p):
        th = np.arctan2(p[:, 1] - 0.3, p[:, 0] + 0.3)
        return (1.08 + 0.12 * np.sin(7 * th)) - p[:, 2]

    snow = paint(mountain, SDF(snowline, (-3, -3, 0.8), (3, 3, 3)), t=0.035, depth=0.08)
    rng = np.random.default_rng(4)
    ball_c = np.array([0.98, -0.85, 0.66])
    lumps = []
    for _ in range(8):
        v = rng.normal(size=3)
        v /= np.linalg.norm(v)
        lumps.append(sphere(0.2, tuple(ball_c + v * 0.52)))
    ball = union(sphere(0.66, tuple(ball_c)), *lumps, k=0.16)
    up = np.array([-1.0, 0.0, 0.9])
    up /= np.linalg.norm(up)
    side = np.array([up[2], 0.0, -up[0]])
    lines = []
    for off, start, length in ((0.42, 0.78, 0.62), (0.0, 0.9, 0.82), (-0.42, 0.78, 0.55)):
        a0 = ball_c + up * start + side * off + np.array([0, -0.45, 0])
        lines.append(tube([tuple(a0), tuple(a0 + up * length * 0.5), tuple(a0 + up * length)], [0.03, 0.06, 0.022]))
    chunks = union(*[sphere(r, tuple(ball_c + np.array(o))) for o, r in (((-0.95, -0.2, -0.45), 0.12), ((-0.7, -0.25, -0.6), 0.08),
                                                                         ((0.75, -0.2, -0.5), 0.1))])
    add(m, "Mountain", mountain, (92, 108, 168), tris=9000, role="skin")
    add(m, "Snow", snow, (250, 252, 255), tris=6000, voxel=0.015)
    add(m, "Ball", union(ball, chunks), (240, 248, 255), tris=8000)
    add(m, "Lines", union(*lines), (176, 224, 255), tris=2500, voxel=0.012)


@icon()
def Alarm(m):
    """Sirena rossa con raggi di luce."""
    base = cyl((0, 0, 0), (0, 0, 0.34), 1.0, round=0.12)
    collar = torus(0.8, 0.075, (0, 0, 0.36))
    dome = union(cyl((0, 0, 0.3), (0, 0, 0.92), 0.74), sphere(0.74, (0, 0, 0.92)))
    bulb = sphere(0.56, (0, 0, 0.8))
    rays = []
    for sx in (1, -1):
        for a in (5, 38, 70):
            d = np.array([sx * math.cos(math.radians(a)), 0, math.sin(math.radians(a))])
            c = np.array([0, -0.1, 0.92])
            rays.append(capsule(tuple(c + d * 1.05), tuple(c + d * 1.48), 0.085))
    add(m, "Base", base, SLATE, tris=4000, role="skin")
    add(m, "Collar", collar, SILVER, tris=2500, gloss=0.35, voxel=0.015)
    add(m, "Dome", dome, RED, material="Glass", tris=7000, gloss=0.3)
    add(m, "Bulb", bulb, (255, 214, 140), material="Neon", role="glow", tris=2000)
    add(m, "Rays", union(*rays), YELLOW, tris=3000, voxel=0.015)


@icon()
def Thief(m):
    """Ladro: testa tonda con mascherina nera da bandito, berretto scuro con risvolto, occhi furbi e sorrisetto."""
    head = ellipsoid((1.0, 0.92, 0.94))

    def xz_ell(rx, rz, cx, cz, ang=0.0):
        """Ellisse nel piano XZ estrusa lungo Y (regione per dipingere sulla faccia)."""
        return ellipsoid((rx, 3.0, rz)).rot(0, ang, 0).translate((cx, 0, cz))

    front_half = SDF(lambda p: p[:, 1] - 0.25, (-3, -3, -3), (3, 3, 3))
    mask_front = union(xz_ell(0.52, 0.36, 0.43, 0.04, -14), xz_ell(0.52, 0.36, -0.43, 0.04, 14),
                       xz_ell(0.3, 0.2, 0.0, -0.02), k=0.12).intersect(front_half)
    strap = SDF(lambda p: np.abs(p[:, 2] - 0.08) - 0.11, (-3, -3, -0.1), (3, 3, 0.3))
    holes = union(*[xz_ell(0.25, 0.18, sx * 0.42, 0.07, -sx * 14) for sx in (1, -1)])
    mask = paint(head, union(mask_front, strap).subtract(holes), t=0.07, depth=0.05)
    eyes, pupils = [], []
    for sx in (1, -1):
        fr = Frame(head, (0, 0, 0), (sx * 0.44, -1.0, 0.08), sink=0.02)
        eyes.append(fr.place(ellipsoid((0.22, 0.05, 0.15)).rot(0, -sx * 14, 0)))
        pupils.append(fr.place(sphere(0.095), (0.1, -0.04, -0.01)))  # x locale = verso sinistra: sguardo di lato
    cap = paint(head, above(0.5), t=0.1, depth=0.05)
    brim = squash(torus(0.866, 0.165), sy=0.92).translate((0, 0, 0.47))
    pom = sphere(0.2, (0, 0.0, 1.12))
    smirk = bezier((-0.2, 0, -0.44), (-0.05, 0, -0.5), (0.12, 0, -0.48), (0.25, 0, -0.36), 12)
    mouth = tube(project_curve(head, [(x, 0.0, z) for x, _, z in smirk], (0, -1, 0), inset=0.012, start_back=0.0), 0.04)
    kx = 0.98
    r1 = [(x, z) for x, _, z in bezier((kx, 0, 0.06), (kx + 0.2, 0, 0.02), (kx + 0.26, 0, -0.18), (kx + 0.4, 0, -0.4), 10)]
    r2 = [(x, z) for x, _, z in bezier((kx, 0, 0.08), (kx + 0.26, 0, 0.16), (kx + 0.42, 0, 0.08), (kx + 0.6, 0, -0.04), 10)]
    tails = [plate(strip(r, 0.24, 0.17), 0.07, r=0.03).translate((0, 0.2, 0)) for r in (r1, r2)]
    knot = ellipsoid((0.13, 0.12, 0.15), (kx - 0.02, 0.16, 0.08))
    t = dict(rx=-12)
    add(m, "Head", tf(head, **t), (255, 208, 164), tris=8000, role="skin")
    add(m, "Mask", tf(union(mask, *tails, knot, k=0.02), **t), (34, 28, 56), tris=9000, gloss=0.35)
    add(m, "Cap", tf(union(cap, pom, k=0.04), **t), (82, 78, 116), tris=6000)
    add(m, "Brim", tf(brim, **t), (240, 238, 248), tris=3000)
    add(m, "Eyes", tf(union(*eyes), **t), WHITE, tris=1500, voxel=0.012)
    add(m, "Pupils", tf(union(*pupils), **t), EYE, role="eye", tris=1000, voxel=0.01)
    add(m, "Mouth", tf(mouth, **t), MOUTH, tris=800, voxel=0.01)


@icon()
def Friends(m):
    """Due testoline tonde e sorridenti vicine."""
    ca, cb = (-0.84, 0.3, 0.18), (0.62, -0.22, -0.06)
    a = sphere(0.86, ca)
    b = sphere(0.94, cb)
    fa = face(a, ca, fwd=(-0.04, -1, 0.04), s=0.95)
    fb = face(b, cb, fwd=(-0.06, -1, 0.0), s=1.05)
    tuft = tube(bezier((-0.84, 0.3, 0.98), (-0.84, 0.23, 1.4), (-0.54, 0.28, 1.46), (-0.52, 0.36, 1.26), 10),
                [0.13, 0.12, 0.11, 0.1, 0.09, 0.08, 0.075, 0.07, 0.065, 0.06, 0.055])
    ears = union(*[sphere(0.24, (0.62 + sx * 0.6, -0.14, 0.66)) for sx in (1, -1)])
    add(m, "HeadA", union(a, tuft, k=0.08), SKY, tris=7000, role="skin")
    add(m, "HeadB", union(b, ears, k=0.1), YELLOW, tris=7000)
    add(m, "Eyes", union(fa["eyes"], fb["eyes"]), EYE, role="eye", tris=2000, voxel=0.012)
    add(m, "Shine", union(fa["shine"], fb["shine"]), WHITE, role="shine", tris=1000, voxel=0.01)
    add(m, "Blush", union(fa["blush"], fb["blush"]), BLUSH, tris=1000, voxel=0.012)
    add(m, "Mouth", union(fa["mouth"], fb["mouth"]), MOUTH, tris=1200, voxel=0.01)


# ---------------------------------------------------------------------- esecuzione
def build_icon(name: str, res: int):
    fn, view, voxel = ICONS[name]
    m = Model(name, "icon", voxel=voxel)
    fn(m)
    env_view = os.environ.get("VIEW")
    if env_view:
        view = tuple(float(v) for v in env_view.split(","))
    t0 = time.time()
    m.build(views=(view or DEFAULT_VIEW,), res=res, export=False)
    # Model.build crea comunque la cartella out/icon/<Nome>: qui non serve
    for d in (toy.OUT / "icon" / name, toy.OUT / "icon"):
        try:
            d.rmdir()
        except OSError:
            pass
    print(f"[icons] {name}: {time.time() - t0:.1f}s")


def contact_sheet(names, path: Path, cell=150, cols=8, small=64):
    """Foglio di controllo su sfondo blu: griglia a 150 px con i nomi e, sotto, tutte le icone a 64 px."""
    from PIL import Image, ImageDraw, ImageFont

    rows = math.ceil(len(names) / cols)
    pad, label = 14, 22
    W = cols * (cell + pad) + pad
    per_row = (W - pad) // (small + 8)
    small_rows = math.ceil(len(names) / per_row)
    grid_h = rows * (cell + pad + label) + pad
    H = grid_h + small_rows * (small + 8) + pad
    sheet = Image.new("RGBA", (W, H), (58, 112, 196, 255))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    draw.line((pad, grid_h - pad // 2, W - pad, grid_h - pad // 2), fill=(40, 84, 160), width=2)
    for i, n in enumerate(names):
        p = toy.OUT / "images" / f"Icon{n}.png"
        x = pad + (i % cols) * (cell + pad)
        y = pad + (i // cols) * (cell + pad + label)
        if not p.exists():
            draw.text((x + 4, y + cell // 2), f"{n}?", fill=(255, 80, 80), font=font)
            continue
        im = Image.open(p).convert("RGBA")
        sheet.alpha_composite(im.resize((cell, cell), Image.LANCZOS), (x, y))
        tw = draw.textlength(n, font=font)
        draw.text((x + (cell - tw) / 2, y + cell + 3), n, fill=(255, 255, 255), font=font)
        # stessa icona a 64 px (dimensione reale piu' piccola sui pulsanti)
        sx = pad + (i % per_row) * (small + 8)
        sy = grid_h + (i // per_row) * (small + 8)
        sheet.alpha_composite(im.resize((small, small), Image.LANCZOS), (sx, sy))
    sheet.save(path)
    print(f"[icons] foglio: {path}")


def main(argv):
    if os.environ.get("OUTDIR"):
        toy.OUT = Path(os.environ["OUTDIR"])
    names = [a for a in argv if a not in ("all", "sheet")]
    set_names = list(ICONS)
    if "all" in argv:
        names = set_names
    unknown = [n for n in names if n not in ICONS]
    if unknown:
        raise SystemExit(f"Icone sconosciute: {unknown}. Disponibili: {', '.join(ICONS)}")
    if names:
        _patch_render()
        res = int(os.environ.get("RES", 512))
        failed = []
        for n in names:
            try:
                build_icon(n, res)
            except Exception as e:  # noqa: BLE001 - continua con le altre icone
                import traceback
                traceback.print_exc()
                failed.append((n, str(e)))
        if failed:
            print("[icons] FALLITE:", failed)
    if "sheet" in argv:
        contact_sheet(set_names, toy.OUT / "images" / "_icons_sheet.png")
    if not argv:
        print(__doc__)
        print("Icone:", ", ".join(set_names))


if __name__ == "__main__":
    main(sys.argv[1:])
