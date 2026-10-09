"""Icone 3D dell'interfaccia (pulsanti, negozio, game pass e developer product).

Uso (dalla cartella art/), un solo processo Blender alla volta:
    nice -n 10 ../.tools/venv/bin/python icons/icons.py Coin Egg ...   # alcune icone
    nice -n 10 ../.tools/venv/bin/python icons/icons.py all            # tutte
    ../.tools/venv/bin/python icons/icons.py sheet                     # foglio di controllo
Variabili d'ambiente: RES (512), SAMPLES (48), VIEW ("x,y,z" forza la direzione della camera),
OUTDIR (cartella alternativa al posto di art/out, per le prove).

Uscita: art/out/images/Icon<Nome>.png, sfondo trasparente, oggetto inquadrato sulla sua sagoma.
Stile: giocattolo in vinile lucido come pet e uova; forme grosse e semplici, 2-6 colori per icona.
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
from lib.sdf import (SDF, Frame, _len, bezier, box, capped_cone, capsule, crystal, cylinder, egg,  # noqa: E402
                     ellipsoid, octahedron, prism, project, project_curve, round_cone, sphere, star_points,
                     stick, torus, tube, union)
from lib.toy import Model  # noqa: E402

# direzione della camera comune a tutto il set (spazio Blender, il modello guarda verso -Y):
# leggermente da destra e dall'alto, quasi frontale (le facce piatte restano leggibili)
DEFAULT_VIEW = (0.35, -1.0, 0.45)
FILL = 0.92  # frazione del riquadro occupata dal lato maggiore della sagoma

# ---------------------------------------------------------------------- palette
GOLD = (255, 190, 32)
GOLD_DARK = (238, 140, 18)
GOLD_LIGHT = (255, 226, 92)
WHITE = (255, 255, 255)
CREAM = (255, 244, 220)
EYE = (36, 24, 40)
BLUSH = (255, 116, 150)
RED = (238, 46, 58)
RED_DARK = (170, 20, 40)
GREEN = (84, 214, 72)
GREEN_DARK = (34, 150, 58)
GREEN_LIGHT = (170, 246, 120)
BLUE = (60, 156, 255)
BLUE_DARK = (34, 92, 214)
PINK = (255, 104, 178)
PINK_DARK = (214, 50, 132)
PURPLE = (150, 84, 246)
PURPLE_DARK = (88, 40, 176)
ORANGE = (255, 138, 28)
ORANGE_DARK = (226, 88, 16)
BROWN = (170, 104, 56)
BROWN_DARK = (116, 66, 38)
GREY = (172, 182, 198)
GREY_DARK = (98, 106, 124)
SILVER = (214, 222, 234)
SPOT = (196, 146, 98)
SPOT_LIGHT = (226, 186, 140)


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
    render._icons_patched = True


# ---------------------------------------------------------------------- forme di base
def plate(poly, t: float, r: float | None = None) -> SDF:
    """Lastra con contorno poligonale nel piano XZ (x a destra, y del poligono = Z), spessore t lungo Y."""
    r = min(t * 0.45, 0.2) if r is None else r
    return prism(poly, -t / 2, t / 2, round=r).rot(90, 0, 0)


def egg_outline(rad: float, h: float, taper: float = 0.2, n: int = 32):
    """Contorno 2D di un uovo centrato in (0, 0), punta in alto."""
    pts = []
    for i in range(n + 1):
        u = 2 * i / n - 1
        rr = rad * math.sqrt(max(1 - u * u, 0.0)) * (1 - taper * u)
        pts.append((rr, (u * 0.5) * h))
    return pts + [(-x, y) for x, y in reversed(pts[1:-1])]


def sparkle(size: float, t: float | None = None) -> SDF:
    """Stellina a quattro punte rivolta verso -Y."""
    t = size * 0.24 if t is None else t
    return plate(star_points(4, size, size * 0.3, rot_deg=90), t, r=t * 0.45)


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


def coin(r: float = 1.0, t: float = 0.36, emblem: bool = True, rim: float = 0.16, recess: float = 0.05,
         grooves: int = 0):
    """Moneta con asse lungo Y (faccia verso -Y). Ritorna (corpo, emblema a uovo o None)."""
    h = t / 2
    body = cylinder((0, -h, 0), (0, h, 0), r, round=min(0.1 * r, h * 0.6))
    inner = r - rim
    cut = union(cylinder((0, -h - 0.3, 0), (0, -h + recess, 0), inner),
                cylinder((0, h - recess, 0), (0, h + 0.3, 0), inner))
    body = body.subtract(cut, k=0.03 * r)
    if grooves:
        body = body.subtract(reeds(r, h - 0.06 * r, grooves, depth=0.03 * r, width=0.024 * r), k=0.012 * r)
    emb = None
    if emblem:
        e = plate(egg_outline(inner * 0.5, inner * 1.32), 0.11 * r, r=0.05 * r)
        emb = e.translate((0, -h + recess - 0.035 * r, 0))
    return body, emb


def placed(shape: SDF, pos=(0, 0, 0), rx=0.0, ry=0.0, rz=0.0) -> SDF:
    return shape.rot(rx, ry, rz).translate(pos)


# ---------------------------------------------------------------------- registro icone
ICONS: dict[str, tuple] = {}
TESTS = {"MatTest"}  # prove di materiale, non fanno parte del set


def icon(view=None, voxel=0.02):
    def deco(fn):
        ICONS[fn.__name__] = (fn, view, voxel)
        return fn
    return deco


@icon()
def Coin(m: Model):
    body, emb = coin(1.0, 0.4, grooves=44)
    rot = dict(rz=-12)
    m.add("Coin", placed(body, **rot), GOLD, material="Foil", tris=9000)
    m.add("Emblem", placed(emb, **rot), GOLD_LIGHT, material="Foil", role="detail", tris=3000, voxel=0.012)


@icon()
def MatTest(m: Model):
    """Prova materiali per l'oro (non fa parte del set)."""
    variants = (("SmoothPlastic", 0.3, 0, "SmoothPlastic"), ("SmoothPlastic", 0.3, -12, "SmoothPlastic"),
                ("Foil", 0.0, 0, "SmoothPlastic"), ("SmoothPlastic", 0.0, 10, "SmoothPlastic"))
    for i, (mat, refl, rz, emat) in enumerate(variants):
        body, emb = coin(1.0, 0.4, grooves=44)
        x = (i - 1.5) * 2.3
        m.add(f"Coin{i}", placed(body, (x, 0, 0), rz=rz), (255, 198, 30), material=mat, reflectance=refl, tris=6000)
        m.add(f"Emb{i}", placed(emb, (x, 0, 0), rz=rz), (255, 240, 150), material=emat, reflectance=refl,
              role="detail", tris=2000, voxel=0.012)


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
    set_names = [n for n in ICONS if n not in TESTS]
    if "all" in argv:
        names = set_names
    unknown = [n for n in names if n not in ICONS]
    if unknown:
        raise SystemExit(f"Icone sconosciute: {unknown}. Disponibili: {', '.join(ICONS)}")
    if any(n in TESTS for n in names) and not os.environ.get("OUTDIR"):
        raise SystemExit("Le prove vanno in una cartella a parte: impostare OUTDIR")
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
