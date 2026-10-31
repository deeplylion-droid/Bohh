"""Copertine del gioco (miniature 16:9 della pagina Roblox, 1920x1080): scene 3D vere renderizzate in Blender
(Cycles CPU), con lo stesso stile della miniatura quadrata della vetta (promo/icon_scenes.py: AgX "Punchy",
montagne sfaccettate, neve e roccia con foschia, mare di nuvole, cielo a gradiente, passata di bagliore + bloom e
vignettatura in numpy) e il Bacon Hair costruito in promo/avatar.py. I titoli li aggiunge promo/cover_compose.py.

Scene:
- steal:   il Bacon Hair corre su una cresta innevata con un uovo Ultra luminoso sopra la testa, inseguito dal
           Titan Rex gigante che ruggisce; cielo azzurro, sole, vette e mare di nuvole.
- giants:  i giganti piu' fighi in fila sulla vetta al tramonto (Penta Drago al centro, Cerbero, Titan Rex,
           Grifone del Tuono, Komodo Infernale...), controluce caldo, la Balena Cosmica che vola nel cielo.
- extreme: il Bacon Hair salta sopra un fiume di lava nell'Inferno del Percorso Estremo, con i diavoli
           (Behemoth, Abaddon, Belzebu') attorno; uovo Estremo sul santuario.
- hatch:   un uovo Ultra che si schiude con raggi di luce e il Penta Drago che esce.

Uso (dalla cartella art/):
    PREVIEW=1 nice -n 10 ../.tools/venv/bin/python promo/covers.py steal 640 16 prova   # bozza veloce
    nice -n 10 ../.tools/venv/bin/python promo/covers.py steal 1920 160 final          # finale
    ../.tools/venv/bin/python promo/cover_compose.py                                   # titoli + foglio
Uscita in art/out/promo/covers/work/: <scena>_<tag>.png (render), _glow.png (superfici luminose), _post.png
(bagliore, vignettatura, saturazione: e' l'immagine che usa cover_compose.py).
Variabili d'ambiente comuni: PREVIEW=1 (niente suddivisione delle mesh ne' profondita' di campo), CAM/TARGET
("x,y,z"), LENS, FSTOP, EXPO, SAT (saturazione in post), BLOOM, VIG; quelle di ogni scena sono nel suo codice
(env("NOME", predefinito)).
"""
from __future__ import annotations

import math
import os
import random
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import avatar as A  # noqa: E402
import icon_scenes as S  # noqa: E402
from icon_scenes import env, lin  # noqa: E402

ART = Path(__file__).resolve().parents[1]
PREVIEW = os.environ.get("PREVIEW", "") == "1"
OUT = ART / "out" / "promo" / "covers"
WORK = OUT / "work"


# =================================================================================== impostazioni
def setup(w: int, samples: int, vt="AgX", look="AgX - Punchy", exposure=0.0):
    sc = S.setup_render(w, samples, vt=env("VT", vt), look=env("LOOK", look), exposure=env("EXPO", exposure))
    sc.render.resolution_x = w
    sc.render.resolution_y = w * 9 // 16
    sc.cycles.adaptive_threshold = 0.02
    if PREVIEW:
        sc.cycles.max_bounces = 4
        sc.cycles.diffuse_bounces = 2
        sc.cycles.glossy_bounces = 2
        sc.cycles.transmission_bounces = 2
    return sc


def tag_glow(mat, on=True):
    """Segna un materiale come sorgente di bagliore (la passata 'glow' lo tiene, il resto diventa holdout)."""
    mat["glow"] = bool(on)
    return mat


def emissive(o) -> bool:
    for m in o.data.materials:
        if m is None:
            continue
        if "glow" in m.keys():
            if m["glow"]:
                return True
            continue
        if not m.use_nodes:
            continue
        b = m.node_tree.nodes.get("Principled BSDF")
        if b is not None and b.inputs["Emission Strength"].default_value > 0 and \
                max(b.inputs["Emission Color"].default_value[:3]) > 0:
            return True
    return False


def pet(name, loc=(0, 0, 0), rot_z=0.0, scale=1.0, kind="pet", subdiv=1, glow=1.0, prefix=""):
    """Carica un pet/uovo del progetto (append_model) con suddivisione e bagliore regolabile."""
    root, objs = S.append_model(ART / f"out/{kind}/{name}/{name}.blend", loc, rot_z, scale, prefix=prefix)
    if not PREVIEW and subdiv:
        S.subdivide([o for o in objs if len(o.data.polygons) < 60000], subdiv)
    for o in objs:
        for m in o.data.materials:
            b = m.node_tree.nodes.get("Principled BSDF") if m and m.use_nodes else None
            if b is not None and b.inputs["Emission Strength"].default_value > 0:
                b.inputs["Emission Strength"].default_value *= glow
    return root, objs


def ground_z(objs):
    lo, _ = S.bounds(objs)
    return float(lo[2])


# =================================================================================== materiali e oggetti di scena
def emission(name, color, strength):
    return tag_glow(S.emission_material(name, color, strength))


def flakes(name, cam_loc, target, n, dmin, dmax, rmin, rmax, seed, spread=0.62, color="#ffffff", glow=0.4,
           aspect=16 / 9):
    """Fiocchi (o scintille) sparsi nel campo visivo della camera (16:9)."""
    import bmesh
    from mathutils import Matrix
    rng = random.Random(seed)
    fwd = (Vector(target) - Vector(cam_loc)).normalized()
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(fwd).normalized()
    bm = bmesh.new()
    for _ in range(n):
        d = dmin + (dmax - dmin) * rng.random() ** 1.5
        u, v = rng.uniform(-spread, spread) * aspect, rng.uniform(-spread, spread)
        p = Vector(cam_loc) + fwd * d + right * (u * d * 0.5) + up * (v * d * 0.5)
        r = rng.uniform(rmin, rmax) * (0.6 + 0.4 * d / dmax)
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r, matrix=Matrix.Translation(p))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    mat, nt, out = S.new_material(name)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = lin(color)
    b.inputs["Emission Color"].default_value = lin(color)
    b.inputs["Emission Strength"].default_value = glow
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    tag_glow(mat, False)
    ob.data.materials.append(mat)
    ob.visible_shadow = False
    return ob


def snow_puffs(name, centers, n_each=14, r=(0.12, 0.45), spread=0.9, seed=1, mat=None):
    """Sbuffi di neve sollevati (gruppi di sfere), per i passi di corsa e le zampate dei giganti."""
    import bmesh
    from mathutils import Matrix
    rng = random.Random(seed)
    bm = bmesh.new()
    for (cx, cy, cz), sc in centers:
        for _ in range(n_each):
            p = Vector((cx + rng.gauss(0, spread * sc), cy + rng.gauss(0, spread * sc * 0.6),
                        cz + abs(rng.gauss(0, spread * sc * 0.7))))
            rad = rng.uniform(*r) * sc
            bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rad, matrix=Matrix.Translation(p))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat is None:
        mat = S.snow_material(name + "M", tint=(244, 249, 255))
    ob.data.materials.append(mat)
    return ob


def sky_gradient(stops, light_color, light_strength, sun_dir=None, sun_color="#fff2c8", sun_size=0.02,
                 sun_strength=6.0, halo=0.25, halo_color="#ffe9b0", stars=0.0):
    """Cielo come icon_scenes.world_sky ma con un disco solare e un alone attorno (visti dalla camera)."""
    w = S.world_sky(stops, light_color, light_strength, stars=stars)
    if sun_dir is None:
        return w
    nt = w.node_tree
    tc = [n for n in nt.nodes if n.type == "TEX_COORD"][0]
    vm = nt.nodes.new("ShaderNodeVectorMath")
    vm.operation = "DOT_PRODUCT"
    nt.links.new(tc.outputs["Generated"], vm.inputs[0])
    vm.inputs[1].default_value = Vector(sun_dir).normalized()
    dot = vm.outputs["Value"]
    disc = S.ramp(nt, dot, [(1 - sun_size * 1.15, (0, 0, 0, 1)), (1 - sun_size, (1, 1, 1, 1))])
    glow_ = S.ramp(nt, dot, [(0.7, (0, 0, 0, 1)), (0.97, (0.35, 0.35, 0.35, 1)), (1.0, (1, 1, 1, 1))])
    bg_cam = [n for n in nt.nodes if n.type == "BACKGROUND" and n.inputs["Strength"].default_value == 1.0
              and n.inputs["Color"].is_linked][0]
    base = bg_cam.inputs["Color"].links[0].from_socket
    add = nt.nodes.new("ShaderNodeMix")
    add.data_type = "RGBA"
    add.blend_type = "ADD"
    nt.links.new(S.math_node(nt, "MULTIPLY", glow_, halo), add.inputs[0])
    nt.links.new(base, S.sock(add, "A_Color"))
    S.sock(add, "B_Color").default_value = lin(halo_color)
    add2 = nt.nodes.new("ShaderNodeMix")
    add2.data_type = "RGBA"
    add2.blend_type = "ADD"
    nt.links.new(S.math_node(nt, "MULTIPLY", disc, sun_strength), add2.inputs[0])
    nt.links.new(S.sock(add, "Result_Color", out=True), S.sock(add2, "A_Color"))
    S.sock(add2, "B_Color").default_value = lin(sun_color)
    nt.links.new(S.sock(add2, "Result_Color", out=True), bg_cam.inputs["Color"])
    return w


def cloud_sea(z, fog_color, color=(236, 242, 255), glow=0.2, density=0.0016, start=40.0, x=(-500, 500),
              y=(-80, 900), seed=3):
    cl = S.grid_object("Clouds", x[0], x[1], y[0], y[1], 240, 240,
                       lambda gx, gy: z + 5.0 * S.turb(gx, gy, 0.02, 4, seed) + 3.5 * S.fbm(gx, gy, 0.006, 2, seed + 6))
    cl.data.materials.append(tag_glow(S.cloud_material("Clouds", color, fog_color, density, start, glow=glow), False))
    return cl


def puffy_cloud(name, center, size, mat, seed=0, n=9):
    """Nuvola cumulo (gruppo di sfere schiacciate) per il cielo."""
    import bmesh
    from mathutils import Matrix
    rng = random.Random(seed)
    bm = bmesh.new()
    cx, cy, cz = center
    for i in range(n):
        t = (i / (n - 1) - 0.5) * 2
        r = size * (0.55 + 0.45 * (1 - t * t)) * rng.uniform(0.8, 1.1)
        p = (cx + t * size * 1.6 + rng.uniform(-0.2, 0.2) * size, cy + rng.uniform(-0.3, 0.3) * size,
             cz + r * 0.35 + rng.uniform(-0.1, 0.1) * size)
        m = Matrix.Translation(p) @ Matrix.Diagonal((1.0, 0.8, 0.72, 1.0))
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=r, matrix=m)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    ob.visible_shadow = False
    return ob


# =================================================================================== passate finali
def glow_pass(path: Path, width: int, extra=()):
    """Seconda passata veloce a bassa risoluzione: solo le superfici luminose (materiali dei pet con emissione o
    segnati con tag_glow), tutto il resto e' holdout. Serve al bagliore in post."""
    sc = bpy.context.scene
    hold, _, out = S.new_material("Holdout")
    hn = hold.node_tree.nodes.new("ShaderNodeHoldout")
    hold.node_tree.links.new(hn.outputs[0], out.inputs["Surface"])
    for o in list(sc.objects):
        if o.type == "LIGHT":
            o.hide_render = True
        if o.type != "MESH":
            continue
        if emissive(o) or any(o.name.startswith(e) for e in extra):
            continue
        o.data.materials.clear()
        o.data.materials.append(hold)
    if sc.world:
        for n in sc.world.node_tree.nodes:
            if n.type == "BACKGROUND":
                n.inputs["Strength"].default_value = 0.0
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.resolution_x = width
    sc.render.resolution_y = width * 9 // 16
    sc.cycles.samples = 24
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 0
    sc.camera.data.dof.use_dof = False
    return S.render_to(path)


def finish(beauty: Path, glow: Path | None, bloom=0.5, radii=(0.01, 0.03, 0.08), vignette=0.16, sat=1.12,
           contrast=1.04, lift=0.0):
    """Bagliore (somma di sfocature gaussiane della passata luminosa, in 'screen'), saturazione e contrasto
    leggeri, vignettatura. Scrive <render>_post.png."""
    from PIL import Image
    from scipy.ndimage import gaussian_filter

    im = np.asarray(Image.open(beauty).convert("RGB"), dtype=np.float32) / 255.0
    h, w = im.shape[:2]
    if glow is not None and glow.exists() and bloom > 0:
        g = Image.open(glow).convert("RGBA").resize((w, h), Image.BILINEAR)
        g = np.asarray(g, dtype=np.float32) / 255.0
        g = g[..., :3] * g[..., 3:4]
        acc = np.zeros_like(g)
        for i, r in enumerate(radii):
            for ch in range(3):
                acc[..., ch] += gaussian_filter(g[..., ch], r * w) * (1.0 / (i + 1)) ** 0.5
        acc *= bloom
        im = 1.0 - (1.0 - im) * (1.0 - np.clip(acc, 0, 1))
    if sat != 1.0:
        lum = (im * np.array([0.2126, 0.7152, 0.0722])).sum(-1, keepdims=True)
        im = np.clip(lum + (im - lum) * sat, 0, 1)
    if contrast != 1.0:
        im = np.clip((im - 0.5) * contrast + 0.5 + lift, 0, 1)
    if vignette > 0:
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        im *= (1.0 - vignette * np.clip(r - 0.6, 0, 1) ** 1.5)[..., None]
    post = beauty.with_name(beauty.stem + "_post.png")
    Image.fromarray((np.clip(im, 0, 1) * 255 + 0.5).astype(np.uint8)).save(post)
    print(f"[covers] {post}")
    return post


def render_all(name: str, tag: str, width: int, bloom=0.5, sat=1.12, vignette=0.16, extra_glow=(), radii=(0.01, 0.03, 0.08)):
    if os.environ.get("NORENDER") == "1":
        return None
    stem = name + (f"_{tag}" if tag else "")
    beauty = S.render_to(WORK / f"{stem}.png")
    glow = glow_pass(WORK / f"{stem}_glow.png", max(320, width // 3), extra_glow)
    return finish(beauty, glow, bloom=env("BLOOM", bloom), sat=env("SAT", sat), vignette=env("VIG", vignette),
                  radii=radii)


def cam_basis(cam_loc, target):
    fwd = (Vector(target) - Vector(cam_loc)).normalized()
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(fwd).normalized()
    return fwd, right, up


# =================================================================================== avatar con l'uovo
def carry_egg(rig, egg_name="EggUltra", width=2.3, glow=1.6, sink=0.18):
    """Mette un uovo sopra la testa del Bacon Hair, appoggiato fra le mani (in gioco gli oggetti rubati si
    impilano sopra la testa). Restituisce (root, oggetti, centro)."""
    bpy.context.view_layer.update()
    hands = []
    for side in ("R", "L"):
        sh = rig.joints[f"Shoulder{side}"]
        hands.append(sh.matrix_world @ Vector((0, 0, -1.42)))
    head_c = rig.joints["HeadCenter"].matrix_world.translation
    root, objs = pet(egg_name, (0, 0, 0), 0.0, 1.0, kind="egg", glow=glow, prefix="Carry_")
    lo, hi = S.bounds([o for o in objs if not o.name.startswith("Ring")])
    shell = [o for o in objs if o.name.split(".")[0] == "Shell"]
    slo, shi = S.bounds(shell) if shell else (lo, hi)
    sc = width / float(shi[0] - slo[0])
    mid = (hands[0] + hands[1]) / 2
    top = max(head_c.z + A.HEAD_H, mid.z)
    root.scale = (sc, sc, sc)
    root.location = (mid.x, mid.y, top - sink - float(slo[2]) * sc)
    # l'uovo ruota con il personaggio
    root.rotation_euler = (0, 0, rig.root.rotation_euler.z)
    root.parent = None
    bpy.context.view_layer.update()
    lo, hi = S.bounds(objs)
    return root, objs, Vector(((lo + hi) / 2).tolist())


def place_by(root, model_pt, world_pt):
    """Sposta root in modo che il punto model_pt (coordinate del modello, prima della scala) finisca su world_pt."""
    bpy.context.view_layer.update()
    cur = root.matrix_world @ Vector(model_pt)
    root.location += Vector(world_pt) - cur
    bpy.context.view_layer.update()


def model_pt(root, p):
    return root.matrix_world @ Vector(p)


def place_avatar(rig, x, y, ground, yaw, air=0.0):
    """Posa gia' applicata: mette i piedi (il punto piu' basso) a quota ground + air."""
    rig.root.location = (x, y, 10.0)
    rig.root.rotation_euler.z = math.radians(yaw)
    bpy.context.view_layer.update()
    lo, _ = A.world_bounds(rig)
    rig.root.location.z = 10.0 - (float(lo[2]) - ground) + air
    bpy.context.view_layer.update()


# =================================================================================== scena 1: ruba l'uovo
def screen(pt):
    """Posizione di un punto nel fotogramma (0..1, origine in basso a sinistra) per comporre senza render."""
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    v = world_to_camera_view(sc, sc.camera, Vector(pt))
    return round(v.x, 3), round(v.y, 3)


def report(**pts):
    print("[covers] schermo: " + "  ".join(f"{k}={screen(v)}" for k, v in pts.items()))


CARRY = {"Root": (9, 0, 0), "Neck": (-4, 0, 6), "ShoulderR": (-176, 5, 0), "ShoulderL": (-174, -5, 0),
         "HipR": (-44, 0, 0), "HipL": (40, 0, 0)}


def scene_steal(w: int, samples: int, tag: str):
    S.reset()
    setup(w, samples, exposure=env("EXPO", 0.1))

    # --- cresta innevata lungo l'asse Y (verso la camera), il terreno cade ai lati
    def ridge(gx, gy):
        z = -0.03 * (gx - 2.0) ** 2
        z += 0.25 * S.fbm(gx, gy, 0.15, 3, 4) + 0.05 * S.fbm(gx, gy, 1.1, 2, 9)
        z -= 0.04 * np.clip(np.abs(gx - 2.0) - 10, 0, None) ** 2
        return z

    def gz(x, y):
        return float(ridge(np.array([[x]]), np.array([[y]]))[0, 0])

    snow = S.grid_object("Snow", -40, 44, -30, 70, 260, 260, ridge)
    snow.data.materials.append(S.snow_material("Snow", tint=(240, 247, 255), fog=(lin("#b4dcff"), 0.005, 25.0)))

    # --- Bacon Hair: corre verso la camera (un po' verso sinistra) con l'uovo Ultra sopra la testa
    rig = A.build("Bacon", shirt=env("SHIRT", "#22d046"))
    A.pose(rig, CARRY)
    ax, ay = env("AV_XY", (0.0, 0.0))
    place_avatar(rig, ax, ay, gz(ax, ay), env("AV_YAW", -26.0), air=env("AIR", 0.3))
    egg_root, egg_objs, egg_c = carry_egg(rig, env("EGG", "EggUltra"), width=env("EGG_W", 2.3), glow=env("EGG_E", 2.2),
                                          sink=env("EGG_SINK", 0.25))

    # --- Titan Rex gigante che insegue (dietro, a destra), fauci spalancate verso il Bacon Hair
    rs = env("REX_S", 3.2)
    rex, rex_objs = pet("TitanRex", (0, 0, 0), env("REX_YAW", -30.0), rs, glow=env("REX_E", 1.8))
    # il muso (davanti, in alto nel modello) va dietro e sopra il Bacon Hair; poi i piedi sulla neve
    snout = (0.0, -2.96, 2.6)
    place_by(rex, snout, env("REX_SNOUT", (3.0, 5.0, 8.0)))
    rx, ry = rex.location.x, rex.location.y
    rex.location.z = gz(rx, ry) - 0.06 * rs
    bpy.context.view_layer.update()

    # --- neve sollevata dai passi (tanti piccoli grumi) e dalle zampe del gigante
    bl = A.world_bounds(rig)
    r_lo, r_hi = S.bounds(rex_objs)
    snow_puffs("Puffs", [((ax + 0.5, ay + 1.6, gz(ax, ay + 1.6)), 0.5), ((ax - 0.4, ay + 2.6, gz(ax, ay + 2.6)), 0.4),
                         ((rx - 2.0, ry - 4.5, gz(rx - 2, ry - 4.5)), 1.6), ((rx + 2.5, ry - 2.0, gz(rx + 2.5, ry - 2)), 1.4)],
               n_each=26, r=(0.05, 0.22), spread=0.8, seed=5)

    # --- cielo azzurro luminoso, vette lontane e mare di nuvole (siamo in alto)
    sky_gradient([(0.0, lin("#eefaff")), (0.07, lin("#bfe6ff")), (0.22, lin("#74c2ff")), (0.45, lin("#3d9bff")),
                  (1.0, lin("#2a7df5"))], light_color=lin("#a8ccff"), light_strength=env("AMB", 1.0))
    fogc = "#b4dcff"
    m1 = S.rock_snow_material("Mnt1", "#41548a", "#f4f8ff", fogc, 0.004, 30, snow_from=0.5)
    m2 = S.rock_snow_material("Mnt2", "#41548a", "#eef4ff", fogc, 0.006, 30, snow_from=0.45)
    S.mountain_layer("Far1", 110, 60, 260, [(-90, 140, 34, 0.55, 0.5), (-30, 150, 44, 0.5, 0.5), (40, 135, 38, 0.55, 0.5),
                                           (110, 146, 30, 0.5, 0.5)], m1, nx=200, ny=50, seed=31, rough=5.0, z_off=env("FARZ", -34.0))
    S.mountain_layer("Far2", 230, 80, 420, [(-160, 270, 50, 0.45, 0.4), (-60, 290, 60, 0.42, 0.4), (60, 275, 55, 0.45, 0.4),
                                           (170, 290, 48, 0.42, 0.4)], m2, nx=220, ny=50, seed=37, rough=6.0, z_off=env("FARZ", -34.0) - 6)
    cloud_sea(env("ZCLOUD", -28.0), fogc, glow=0.3, density=0.0012)
    cmat = S.cloud_material("Puffy", (250, 252, 255), fogc, 0.0015, 60.0, glow=0.35)
    tag_glow(cmat, False)
    for i, (c, s_) in enumerate((((-60, 150, 30), 9), ((70, 170, 44), 11), ((-20, 200, 58), 8))):
        puffy_cloud(f"Cumulus{i}", c, s_, cmat, seed=i)

    # --- luci: sole caldo da davanti a sinistra, cielo, controluce sui contorni, bagliore dell'uovo
    sun_dir = Vector(env("SUN", (-0.55, -0.45, 0.7))).normalized()
    S.sun_light("Sun", tuple(sun_dir), env("SUNL", 3.6), lin("#fff1dc")[:3], angle=3.0)
    ac = Vector(((bl[0] + bl[1]) / 2).tolist())
    rc = Vector(((r_lo + r_hi) / 2).tolist())
    S.area_light("FillFront", tuple(ac + Vector((5, -12, 3))), tuple(ac), env("FILL", 1200.0), 10.0, lin("#d6e8ff")[:3])
    S.area_light("RimAv", tuple(ac + Vector((4, 7, 5))), tuple(ac + Vector((0, 0, 1))), env("RIM", 2600.0), 4.0,
                 lin("#eef6ff")[:3])
    S.area_light("RimAvL", tuple(ac + Vector((-6, 5, 4))), tuple(ac + Vector((0, 0, 1))), env("RIM", 2600.0) * 0.8, 4.0,
                 lin("#fff3e0")[:3])
    S.area_light("RimRex", tuple(rc + Vector((-6, 16, 14))), tuple(rc), env("RIMREX", 30000.0), 14.0, lin("#eef6ff")[:3])
    S.area_light("FillRex", tuple(rc + Vector((-8, -24, 6))), tuple(rc), env("FILLREX", 9000.0), 18.0, lin("#ffe6cc")[:3])
    S.point_light("EggGlow", tuple(egg_c), env("EGGLIGHT", 300.0), 0.6, lin("#ff7ad9")[:3])
    S.point_light("EggGlow2", tuple(egg_c + Vector((0, -1.6, -0.6))), env("EGGLIGHT", 300.0) * 0.6, 0.4, lin("#ffd36b")[:3])

    # --- camera davanti al Bacon Hair, all'altezza del petto, leggermente dal basso
    cam_loc = env("CAM", (4.5, -14.0, 3.6))
    target = env("TARGET", (4.6, 4.0, 6.4))
    S.camera(cam_loc, target, lens=env("LENS", 32.0), dof_target=tuple(ac) if not PREVIEW else None,
             fstop=env("FSTOP", 6.0))
    flakes("Flakes", cam_loc, target, env("FLAKES", 140), 4.0, 40.0, 0.02, 0.05, seed=4, glow=0.3)
    head = rig.joints["HeadCenter"].matrix_world.translation
    feet = rig.parts["ShoeR"].matrix_world.translation
    e_lo, e_hi = S.bounds(egg_objs)
    report(feet=feet, head=head, egg_top=(egg_c.x, egg_c.y, e_hi[2]), snout=model_pt(rex, snout),
           rex_crown=model_pt(rex, (0, -1.6, 3.72)), rex_tail=model_pt(rex, (0, 1.93, 1.5)),
           rex_foot=model_pt(rex, (0.8, -0.5, 0.0)))
    return render_all("steal", tag, w, bloom=0.55)


SCENES = {"steal": scene_steal}

if __name__ == "__main__":
    which = sys.argv[1]
    w = int(sys.argv[2]) if len(sys.argv) > 2 else 640
    samples = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    tag = sys.argv[4] if len(sys.argv) > 4 else ""
    SCENES[which](w, samples, tag)
