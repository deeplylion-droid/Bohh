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
from mathutils import Vector, noise

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


CARRY = {"Root": (9, 0, 0), "Neck": (-4, 0, 6), "ShoulderR": (-174, 11, 0), "ShoulderL": (-172, -11, 0),
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
    ax, ay = env("AV_XY", (-0.5, -2.5))
    place_avatar(rig, ax, ay, gz(ax, ay), env("AV_YAW", -26.0), air=env("AIR", 0.3))
    egg_root, egg_objs, egg_c = carry_egg(rig, env("EGG", "EggUltra"), width=env("EGG_W", 2.05), glow=env("EGG_E", 4.0),
                                          sink=env("EGG_SINK", -0.4))

    # --- Titan Rex gigante che insegue (dietro, a destra), fauci spalancate verso il Bacon Hair
    rs = env("REX_S", 5.4)
    rex, rex_objs = pet("TitanRex", (0, 0, 0), env("REX_YAW", -42.0), rs, glow=env("REX_E", 1.8))
    rex.rotation_euler.x = math.radians(env("REX_PITCH", 12.0))  # si sbilancia in avanti: carica
    # la bocca (centro delle fauci nel modello) va dietro il Bacon Hair, poi le zampe sulla neve
    mouth = (0.08, -2.4, 2.2)
    mx, my = env("REX_MOUTH", (2.4, 5.5))
    place_by(rex, mouth, (mx, my, 0.0))
    rx, ry = rex.location.x, rex.location.y
    r_lo, _ = S.bounds(rex_objs)
    rex.location.z += gz(rx, ry) - float(r_lo[2]) - env("REX_SINK", 0.6)
    bpy.context.view_layer.update()
    snout = (0.08, -2.9, 2.7)

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
    head_w = rig.joints["HeadCenter"].matrix_world.translation
    S.area_light("FaceFill", tuple(head_w + Vector((-1.5, -5.0, 0.6))), tuple(head_w), env("FACE", 160.0), 1.5,
                 lin("#fff4e6")[:3])
    S.area_light("EggKey", tuple(egg_c + Vector((-2.5, -5.0, 2.0))), tuple(egg_c), env("EGGKEY", 260.0), 2.0,
                 lin("#ffffff")[:3])
    S.point_light("EggGlow", tuple(egg_c), env("EGGLIGHT", 300.0), 0.6, lin("#ff7ad9")[:3])
    S.point_light("EggGlow2", tuple(egg_c + Vector((0, -1.6, -0.6))), env("EGGLIGHT", 300.0) * 0.6, 0.4, lin("#ffd36b")[:3])

    # --- camera davanti al Bacon Hair, all'altezza del petto, leggermente dal basso
    cam_loc = env("CAM", (-2.0, -14.0, 1.7))
    target = env("TARGET", (0.4, 3.0, 5.9))
    S.camera(cam_loc, target, lens=env("LENS", 25.0), dof_target=tuple(ac) if not PREVIEW else None,
             fstop=env("FSTOP", 8.0))
    flakes("Flakes", cam_loc, target, env("FLAKES", 140), 4.0, 40.0, 0.02, 0.05, seed=4, glow=0.3)
    head = rig.joints["HeadCenter"].matrix_world.translation
    feet = rig.parts["ShoeR"].matrix_world @ Vector((0, 0, -1.82))
    e_lo, e_hi = S.bounds(egg_objs)
    report(feet=feet, head=head, egg_top=(egg_c.x, egg_c.y, e_hi[2]), mouth=model_pt(rex, mouth),
           rex_eye=model_pt(rex, (0.25, -2.1, 3.1)), rex_crown=model_pt(rex, (0, -1.6, 3.6)),
           rex_tail=model_pt(rex, (0.3, 1.9, 2.6)), rex_foot=model_pt(rex, (0.8, -0.5, 0.0)))
    return render_all("steal", tag, w, bloom=0.55)


# =================================================================================== scena 2: giganti al tramonto
def rounded_profile(pts, r, n=6):
    """Profilo (rho, z) con gli spigoli interni raccordati da archi di raggio r (per le rivoluzioni lisce)."""
    pts = [np.array(p, float) for p in pts]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        u = (a - b) / np.linalg.norm(a - b)
        v = (c - b) / np.linalg.norm(c - b)
        rr = min(r, np.linalg.norm(a - b) * 0.45, np.linalg.norm(c - b) * 0.45)
        p0, p1 = b + u * rr, b + v * rr
        for t in np.linspace(0, 1, n):
            # Bezier quadratica con controllo nello spigolo (approssima l'arco)
            out.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t * t * p1)
    out.append(pts[-1])
    return np.array(out)


def throne(name, center, radius=4.0, height=1.6, top="#6d2bd9", rim="#ffc83d", glow="#d86bff"):
    """Trono dei giganti: piedistallo rotondo di pietra a gradini, fascia d'oro, piano colorato e anello luminoso."""
    cx, cy, cz = center
    stone = S.rock_snow_material(name + "Stone", "#5a6380", "#e9eefc", "#9a7bd0", 0.0, 1e4, snow_from=0.9)
    prof = rounded_profile([(0, 0), (radius + 0.5, 0), (radius + 0.5, height * 0.35), (radius, height * 0.42),
                            (radius, height), (0, height)], 0.12)
    base = A.revolve(name, prof, 96, stone, center=(cx, cy, cz))
    gold, nt, out = S.new_material(name + "Gold")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = lin(rim)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.22
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    band = rounded_profile([(radius - 0.05, height * 0.62), (radius + 0.16, height * 0.62), (radius + 0.16, height * 0.86),
                            (radius - 0.05, height * 0.86)], 0.05)
    A.revolve(name + "Band", band, 96, gold, center=(cx, cy, cz))
    felt = S.felt_material(name + "Top", top)
    topp = rounded_profile([(0, height - 0.02), (radius - 0.25, height - 0.02), (radius - 0.25, height + 0.12),
                            (0, height + 0.12)], 0.06)
    A.revolve(name + "TopFelt", topp, 96, felt, center=(cx, cy, cz))
    ring = rounded_profile([(radius - 0.22, height + 0.02), (radius - 0.04, height + 0.02), (radius - 0.04, height + 0.16),
                            (radius - 0.22, height + 0.16)], 0.04)
    A.revolve(name + "Ring", ring, 96, emission(name + "RingM", glow, 6.0), center=(cx, cy, cz))
    return base, cz + height + 0.12


def scene_giants(w: int, samples: int, tag: str):
    S.reset()
    # Standard (non AgX): i colori saturi del tramonto e delle fiamme restano accesi invece di sbiadire
    setup(w, samples, vt="Standard", look="None", exposure=-0.4)

    def ground(gx, gy):
        r = np.hypot(gx * 0.8, gy - 6)
        z = -0.012 * np.clip(r - 16, 0, None) ** 2
        z += 0.3 * S.fbm(gx, gy, 0.08, 3, 7) + 0.06 * S.fbm(gx, gy, 0.9, 2, 3)
        return z

    def gz(x, y):
        return float(ground(np.array([[x]]), np.array([[y]]))[0, 0])

    snow = S.grid_object("Snow", -60, 60, -30, 70, 260, 220, ground)
    snow.data.materials.append(S.snow_material("Snow", tint=(226, 220, 246), fog=(lin("#ff9d8a"), 0.003, 40.0)))

    # --- trono al centro con il Penta Drago
    tx, ty = env("THRONE_XY", (0.0, 9.0))
    _, top_z = throne("Throne", (tx, ty, gz(tx, ty) - 0.3), radius=env("THRONE_R", 4.6), height=env("THRONE_H", 2.2))
    ds = env("DRAGON_S", 2.5)
    dragon, d_objs = pet("PentaDragon", (tx, ty + 0.3, top_z - 0.05), env("DRAGON_YAW", 0.0), ds, glow=env("DRAGON_E", 2.2))

    # --- altri giganti attorno (sinistra -> destra nel fotogramma)
    cast = [
        ("InfernoKomodo", env("KOMODO", (-14.5, 1.5, 40.0)), env("KOMODO_S", 2.5), 2.0),
        ("Cerberus", env("CERB", (-8.6, 6.5, 16.0)), env("CERB_S", 2.8), 1.6),
        ("ThunderGriffin", env("GRIF", (8.8, 7.0, -14.0)), env("GRIF_S", 2.6), 2.0),
        ("FrostWyvern", env("WYV", (14.5, 2.5, -32.0)), env("WYV_S", 2.4), 2.0),
    ]
    giants = {"PentaDragon": d_objs}
    for name, (x, y, rot), s_, g in cast:
        root, objs = pet(name, (x, y, 0), rot, s_, glow=g)
        lo, _ = S.bounds(objs)
        root.location.z = gz(x, y) - float(lo[2]) - 0.15
        giants[name] = objs
    bpy.context.view_layer.update()

    # --- la Balena Cosmica vola nel cielo (senza la sua nuvoletta)
    wx, wy, wz = env("WHALE", (15.0, 34.0, 16.5))
    whale, w_objs = pet("CosmicWhale", (wx, wy, wz), env("WHALE_YAW", -78.0), env("WHALE_S", 4.0), glow=2.4)
    for o in w_objs:
        if o.name.split(".")[0] == "Cloud":
            o.hide_render = True
    whale.rotation_euler.x = math.radians(env("WHALE_PITCH", 0.0))
    whale.rotation_euler.y = math.radians(env("WHALE_ROLL", 0.0))

    # --- uova luminose sulla neve, davanti
    eggs = []
    for i, (name, x, y, rot, s_) in enumerate((("EggLegendary", -5.6, -5.5, 15, 0.95), ("EggUltra", 5.6, -6.0, -20, 0.8))):
        root, objs = pet(name, (x, y, 0), rot, s_, kind="egg", glow=2.6, prefix=f"E{i}_")
        root.location.z = gz(x, y) - 0.12
        eggs.append(objs)
    bpy.context.view_layer.update()

    # --- cielo del tramonto: oro all'orizzonte, rosa, viola, indaco in alto; il sole basso dietro i giganti
    sun_dir = Vector(env("SUN", (0.32, 1.0, 0.1))).normalized()
    sky_gradient([(0.0, lin("#ffd36e")), (0.05, lin("#ff9d5c")), (0.13, lin("#ff6a8e")), (0.3, lin("#c04fd8")),
                  (0.55, lin("#6a3fd0")), (1.0, lin("#33289a"))], light_color=lin("#b49cff"),
                 light_strength=env("AMB", 0.35), sun_dir=tuple(sun_dir), sun_size=0.0005, sun_strength=20.0,
                 halo=1.2, halo_color="#ffb070", stars=env("STARS", 0.0))
    fogc = "#ff9d8a"
    m1 = S.rock_snow_material("Mnt1", "#5a3f86", "#ffd1dc", fogc, 0.0045, 30, snow_from=0.5)
    m2 = S.rock_snow_material("Mnt2", "#5a3f86", "#ffc6d6", fogc, 0.0065, 30, snow_from=0.45)
    S.mountain_layer("Far1", 120, 60, 280, [(-110, 150, 30, 0.55, 0.5), (-45, 160, 40, 0.5, 0.5), (50, 145, 36, 0.55, 0.5),
                                           (120, 156, 28, 0.5, 0.5)], m1, nx=200, ny=50, seed=41, rough=5.0, z_off=env("FARZ", -36.0))
    S.mountain_layer("Far2", 240, 80, 460, [(-180, 280, 46, 0.45, 0.4), (-70, 300, 56, 0.42, 0.4), (70, 285, 50, 0.45, 0.4),
                                           (190, 300, 44, 0.42, 0.4)], m2, nx=220, ny=50, seed=43, rough=6.0, z_off=env("FARZ", -36.0) - 6)
    cloud_sea(env("ZCLOUD", -30.0), "#ff9d8a", color=(255, 200, 196), glow=0.45, density=0.0011)
    # nuvole del tramonto (rosa sopra, viola sotto)
    cmat = S.cloud_material("Puffy", (255, 186, 196), "#ff9d8a", 0.0008, 80.0, glow=0.55)
    tag_glow(cmat, False)
    for i, (c, s_) in enumerate((((-95, 190, 38), 13), ((-40, 230, 50), 10), ((60, 260, 64), 12), ((-130, 260, 70), 9))):
        puffy_cloud(f"Cumulus{i}", c, s_, cmat, seed=10 + i)

    # --- luci: sole basso di controluce (contorni caldi), riempimento freddo da davanti, luci delle uova
    S.sun_light("Sun", tuple(sun_dir), env("SUNL", 5.0), lin("#ffa65c")[:3], angle=2.0)
    for name, objs in giants.items():
        lo, hi = S.bounds(objs)
        c = Vector(((lo + hi) / 2).tolist())
        size = float(hi[2] - lo[2])
        # controluce caldo da dietro a destra (come il sole) e da dietro a sinistra (piu' rosa)
        S.area_light(f"Rim{name}", tuple(c + Vector((1.0 * size, 1.5 * size, 0.8 * size))), tuple(c),
                     env("RIM", 300.0) * size ** 2, 0.5 * size, lin("#ffb066")[:3])
        S.area_light(f"Rim2{name}", tuple(c + Vector((-1.2 * size, 1.3 * size, 0.7 * size))), tuple(c),
                     env("RIM", 300.0) * 0.6 * size ** 2, 0.5 * size, lin("#ff7fb0")[:3])
        # luce principale calda da davanti a sinistra
        S.area_light(f"Key{name}", tuple(c + Vector((-1.3 * size, -1.8 * size, 1.1 * size))), tuple(c),
                     env("KEY", 55.0) * size ** 2, 0.8 * size, lin("#fff0dc")[:3])
    S.area_light("FillCam", tuple(Vector(env("CAM", (0.0, -26.0, 3.2))) + Vector((6, 0, 4))), (0, 6, 5),
                 env("FILL", 2500.0), 20.0, lin("#9fb0ff")[:3])
    wl, wh = S.bounds(w_objs)
    wc = Vector(((wl + wh) / 2).tolist())
    S.area_light("WhaleKey", tuple(wc + Vector((-8, -14, 6))), tuple(wc), env("WHALEKEY", 9000.0), 8.0, lin("#ffe6f0")[:3])
    S.area_light("WhaleRim", tuple(wc + Vector((6, 10, 8))), tuple(wc), env("WHALERIM", 9000.0), 8.0, lin("#ffb066")[:3])
    for i, objs in enumerate(eggs):
        lo, hi = S.bounds(objs)
        c = Vector(((lo + hi) / 2).tolist())
        S.point_light(f"EggL{i}", tuple(c + Vector((0, -1.2, 0.2))), env("EGGLIGHT", 220.0), 0.5, lin("#ffcf7a")[:3])

    cam_loc = env("CAM", (0.0, -28.0, 3.4))
    target = env("TARGET", (0.0, 6.0, 8.2))
    dlo, dhi = S.bounds(d_objs)
    S.camera(cam_loc, target, lens=env("LENS", 30.0), dof_target=(0, ty, 5) if not PREVIEW else None, fstop=env("FSTOP", 8.0))
    flakes("Sparkles", cam_loc, target, env("FLAKES", 90), 6.0, 50.0, 0.025, 0.06, seed=9, color="#ffe9c4", glow=2.0)
    pts = {"dragon_top": ((dlo[0] + dhi[0]) / 2, ty, dhi[2]), "dragon_l": (dlo[0], ty, dhi[2] * 0.6),
           "dragon_r": (dhi[0], ty, dhi[2] * 0.6)}
    for name, objs in giants.items():
        lo, hi = S.bounds(objs)
        pts[name[:6]] = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, hi[2])
    wl, wh = S.bounds(w_objs)
    pts["whale"] = tuple((wl + wh) / 2)
    pts["whale_l"] = (wl[0], (wl[1] + wh[1]) / 2, (wl[2] + wh[2]) / 2)
    report(**pts)
    return render_all("giants", tag, w, bloom=0.5, sat=1.1)


# =================================================================================== scena 3: Percorso Estremo (Inferno)
def lava_material(name="Lava", strength=6.0, scale=0.18):
    """Lava: crosta scura a placche con crepe incandescenti (giallo -> arancio), molto luminosa."""
    mat, nt, out = S.new_material(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 0.45, 1.0)  # placche allungate nel verso della corrente
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = scale
    nz = S.node(nt, "ShaderNodeTexNoise", Scale=scale * 2.5, Detail=4.0, Roughness=0.6)
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    # distorsione del voronoi con il rumore (crepe irregolari)
    add = nt.nodes.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    nt.links.new(mp.outputs["Vector"], add.inputs[0])
    sc_ = nt.nodes.new("ShaderNodeVectorMath")
    sc_.operation = "SCALE"
    sc_.inputs["Scale"].default_value = 2.5
    nt.links.new(nz.outputs["Color"], sc_.inputs[0])
    nt.links.new(sc_.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], vor.inputs["Vector"])
    # bordo delle placche = crepa luminosa; il centro delle placche resta crosta un po' scura
    crack = S.ramp(nt, vor.outputs["Distance"], [(0.0, (1, 1, 1, 1)), (0.06, (0.85, 0.85, 0.85, 1)), (0.2, (0.18, 0.18, 0.18, 1)),
                                                 (0.45, (0.05, 0.05, 0.05, 1))])
    # crosta scura sulle placche, crepe incandescenti, qualche chiazza calda dal rumore
    hot = S.ramp(nt, nz.outputs["Fac"], [(0.45, (0, 0, 0, 1)), (0.75, (0.7, 0.7, 0.7, 1))])
    k = S.math_node(nt, "MAXIMUM", crack, hot)
    col = S.ramp(nt, k, [(0.0, lin("#3a0d06")), (0.22, lin("#b3260a")), (0.45, lin("#ff5a0a")), (0.7, lin("#ff9a1a")),
                         (1.0, lin("#fff07a"))])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(col, em.inputs["Color"])
    nt.links.new(S.math_node(nt, "MULTIPLY", S.math_node(nt, "POWER", k, 1.4), strength), em.inputs["Strength"])
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = lin("#2a0c06")
    b.inputs["Roughness"].default_value = 0.6
    addsh = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(b.outputs[0], addsh.inputs[0])
    nt.links.new(em.outputs[0], addsh.inputs[1])
    nt.links.new(addsh.outputs[0], out.inputs["Surface"])
    return tag_glow(mat, False)


def basalt_material(name, top="#ff7a1e", top_e=2.2, rock="#2a1d24", veins=1.0, fog=("#ff8a4a", 0.004, 30.0)):
    """Roccia vulcanica sfaccettata: pareti scure, le facce in piano diventano crosta arancio incandescente (come i
    muri dell'Inferno in gioco), vene luminose vicino alla lava; foschia calda con la distanza."""
    mat, nt, out = S.new_material(name)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["True Normal"], sep.inputs[0])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = S.node(nt, "ShaderNodeTexNoise", Scale=0.5, Detail=3.0)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    k = S.math_node(nt, "ADD", sep.outputs["Z"], S.math_node(nt, "MULTIPLY", S.math_node(nt, "SUBTRACT", nz.outputs["Fac"], 0.5), 0.3))
    topk = S.ramp(nt, k, [(0.7, (0, 0, 0, 1)), (0.78, (1, 1, 1, 1))])
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = lin(rock)
    b.inputs["Roughness"].default_value = 0.75
    # vene: crepe luminose dal basso (quota) con un voronoi
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 0.35
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    vein = S.ramp(nt, vor.outputs["Distance"], [(0.0, (1, 1, 1, 1)), (0.035, (0, 0, 0, 1))])
    pos = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], pos.inputs[0])
    low = S.ramp(nt, pos.outputs["Z"], [(0.0, (1, 1, 1, 1)), (4.0, (0, 0, 0, 1))])
    vk = S.math_node(nt, "MULTIPLY", S.math_node(nt, "MULTIPLY", vein, low), veins)
    em_k = S.math_node(nt, "MAXIMUM", topk, vk)
    em = node_emission = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin(top)
    nt.links.new(S.math_node(nt, "MULTIPLY", em_k, top_e), em.inputs["Strength"])
    addsh = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(b.outputs[0], addsh.inputs[0])
    nt.links.new(node_emission.outputs[0], addsh.inputs[1])
    sh = addsh.outputs[0]
    if fog:
        sh = S.fog_mix(nt, sh, lin(fog[0]), fog[1], fog[2])
    nt.links.new(sh, out.inputs["Surface"])
    return tag_glow(mat, False)


def faceted_rock(name, center, size, mat, seed=0, sub=2, rough=0.28, flatten=1.0):
    """Masso sfaccettato (icosfera deformata, ombreggiatura piatta)."""
    import bmesh
    from mathutils import Matrix
    rng = np.random.default_rng(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    off = rng.uniform(0, 100, 3)
    for v in bm.verts:
        n = noise.noise(Vector(v.co) * 1.3 + Vector(off))
        v.co *= 1.0 + rough * n
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = center
    sx, sy, sz = size if isinstance(size, tuple) else (size, size, size * flatten)
    ob.scale = (sx, sy, sz)
    ob.rotation_euler.z = rng.uniform(0, 6.28)
    ob.data.materials.append(mat)
    return ob


def pillar(name, x, y, top_z, radius, mat, cap_mat=None):
    prof = rounded_profile([(0, -3.0), (radius * 1.08, -3.0), (radius, top_z - 0.25), (radius * 0.98, top_z), (0, top_z)], 0.18)
    ob = A.revolve(name, prof, 28, mat, center=(x, y, 0))
    for p_ in ob.data.polygons:
        p_.use_smooth = False
    return ob


def portal(name, center, radius, yaw_deg, color="#32f0ff"):
    """Portale del santuario: anello di pietra + vortice luminoso."""
    import bmesh
    from mathutils import Matrix
    cx, cy, cz = center
    rot = Matrix.Rotation(math.radians(yaw_deg), 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "X")
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=64, radius=radius, matrix=Matrix.Translation(center) @ rot)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    disc = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(disc)
    mat, nt, out = S.new_material(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    grad = nt.nodes.new("ShaderNodeTexGradient")
    grad.gradient_type = "SPHERICAL"
    vm = nt.nodes.new("ShaderNodeVectorMath")
    vm.operation = "SCALE"
    vm.inputs["Scale"].default_value = 1.0 / radius
    nt.links.new(tc.outputs["Object"], vm.inputs[0])
    nt.links.new(vm.outputs[0], grad.inputs["Vector"])
    wave = S.node(nt, "ShaderNodeTexWave", Scale=1.2, Distortion=6.0, Detail=3.0)
    wave.wave_type = "RINGS"
    nt.links.new(vm.outputs[0], wave.inputs["Vector"])
    k = S.math_node(nt, "ADD", S.math_node(nt, "MULTIPLY", wave.outputs["Fac"], 0.5), S.math_node(nt, "SUBTRACT", 1.0, grad.outputs["Fac"]))
    col = S.ramp(nt, k, [(0.2, lin("#1a2cff")), (0.6, lin(color)), (1.0, lin("#e8ffff"))])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = env("PORTAL_E", 1.6)
    nt.links.new(col, em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    disc.data.materials.append(tag_glow(mat))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=64, radius1=radius * 1.12, radius2=radius * 1.12, depth=0.6,
                          matrix=Matrix.Translation(center) @ rot)
    me = bpy.data.meshes.new(name + "Frame")
    bm.to_mesh(me)
    bm.free()
    fr = bpy.data.objects.new(name + "Frame", me)
    bpy.context.scene.collection.objects.link(fr)
    sol = fr.modifiers.new("s", "SOLIDIFY")
    sol.thickness = 0.5
    return disc, fr


def scene_extreme(w: int, samples: int, tag: str):
    S.reset()
    setup(w, samples, vt="Standard", look="None", exposure=-0.3)

    # --- canyon: letto del fiume sotto la lava, pareti sfaccettate ai lati che si stringono in lontananza
    def canyon(gx, gy):
        half = 10.0 + 0.03 * np.clip(-gy, 0, None) ** 2 - 0.03 * np.clip(gy - 20, 0, None)
        half = np.maximum(half, 5.0)
        d = np.abs(gx - 1.5 * np.sin(gy * 0.05)) - half
        hgt = env("WALL_H", 6.5) + 2.5 * S.fbm(gx, gy, 0.06, 2, 3)
        z = np.where(d < 0, -1.5, -1.5 + np.clip(d * 1.6, 0, 1) * hgt)
        z += np.clip(d - 6, 0, None) * 0.35
        z += 0.9 * S.fbm(gx, gy, 0.22, 2, 11) * (d > 0)
        return z

    walls = S.grid_object("Canyon", -60, 60, -30, 140, 96, 110, canyon, smooth=False)
    walls.data.materials.append(basalt_material("Basalt", rock="#1c1318", fog=("#ff6a4a", 0.0025, 40.0)))
    lava = S.grid_object("Lava", -60, 60, -30, 160, 120, 160, lambda gx, gy: 0.12 * S.fbm(gx, gy, 0.1, 2, 5))
    lava.data.materials.append(lava_material(strength=env("LAVA_E", 2.6), scale=env("LAVA_SC", 0.12)))

    # --- pilastri di pietra nella lava (il percorso a salti) e massi di lava sulle rive
    pm = basalt_material("PillarRock", top="#ff8a2a", top_e=0.0, rock="#2a1d24", veins=1.5, fog=("#ff6a4a", 0.0025, 40.0))
    jumps = env("PILLARS", 0.0)
    path = [(-3.6, 0.5, 2.4, 1.5), (3.2, 7.5, 2.8, 1.4), (-1.8, 13.5, 2.5, 1.3), (3.0, 19.5, 2.9, 1.3), (-1.0, 26.0, 2.4, 1.2),
            (2.2, 33.0, 2.6, 1.2), (-1.5, 41.0, 2.5, 1.1), (1.5, 49.0, 2.8, 1.1)]
    for i, (x, y, tz, r) in enumerate(path):
        pillar(f"Pillar{i}", x, y, tz, r, pm)
    lr = basalt_material("LavaRockM", top="#ff6a1a", top_e=0.0, rock="#2e2228", veins=2.5)
    rng = np.random.default_rng(4)
    for i in range(16):
        side = -1 if i % 2 == 0 else 1
        y = -4 + i * 5.5 + rng.uniform(-2, 2)
        half = 9.0 - 0.02 * max(y - 20, 0)
        x = side * (max(half, 4.0) - rng.uniform(0.5, 2.0))
        faceted_rock(f"Boulder{i}", (x, y, rng.uniform(-0.6, 0.0)), (rng.uniform(1.0, 2.0),) * 2 + (rng.uniform(0.7, 1.4),),
                     lr, seed=i)

    # --- santuario in fondo: piedistallo azzurro, uovo Estremo, portale
    sx, sy = env("SHRINE", (0.5, 70.0))
    throne("Shrine", (sx, sy, -0.2), radius=3.0, height=2.6, top="#1fb6c9", rim="#ffd23a", glow="#3ff6ff")
    egg, egg_objs = pet("EggExtreme", (sx, sy, 2.6), 15.0, 1.1, kind="egg", glow=3.0)
    portal("Portal", (sx + 7.5, sy + 4.0, 5.0), 4.2, -25.0)

    # --- diavoli giganti sulle sporgenze ai lati (destra: Behemoth, sinistra: Abaddon) e Belzebu' in volo
    beh, beh_objs = pet("Behemoth", env("BEH", (8.6, 11.0, 1.3)), env("BEH_YAW", 42.0), env("BEH_S", 2.7), glow=2.2)
    aba, aba_objs = pet("Abaddon", env("ABA", (-8.8, 17.0, 1.3)), env("ABA_YAW", -40.0), env("ABA_S", 2.7), glow=2.2)
    bee, bee_objs = pet("Beelzebub", env("BEE", (6.0, 34.0, 7.5)), env("BEE_YAW", 25.0), env("BEE_S", 2.3), glow=2.2)
    for i, (root, objs) in enumerate(((beh, beh_objs), (aba, aba_objs))):
        lo, hi = S.bounds(objs)
        x, y = root.location.x, root.location.y
        foot = root.location.z
        root.location.z += foot - float(lo[2]) - 0.15 - foot
        # sporgenza di roccia sotto le zampe
        faceted_rock(f"Ledge{i}", (x, y, foot - 1.6), (float(hi[0] - lo[0]) * 0.75, float(hi[1] - lo[1]) * 0.75, 1.75), lr,
                     seed=40 + i, rough=0.18)
    bpy.context.view_layer.update()

    # --- il Bacon Hair a meta' salto fra due pilastri
    rig = A.build("Bacon", shirt=env("SHIRT", "#22d046"))
    A.pose(rig, env("LEAP_POSE", "leap"))
    ax, ay, az = env("AV", (-0.6, 3.0, 5.4))
    rig.root.location = (ax, ay, az)
    rig.root.rotation_euler.z = math.radians(env("AV_YAW", 50.0))
    bpy.context.view_layer.update()

    # --- cielo infuocato: giallo all'orizzonte, arancio, cremisi, viola in alto
    sky_gradient([(0.0, lin("#ffd25a")), (0.06, lin("#ff8a2a")), (0.16, lin("#ff3d4a")), (0.35, lin("#b0207a")),
                  (0.6, lin("#5a1a7a")), (1.0, lin("#2a0f4a"))], light_color=lin("#ff9a6a"), light_strength=env("AMB", 0.45))
    vm = basalt_material("Volcano", top="#ff7a1e", top_e=1.0, rock="#3a2230", veins=0.0, fog=("#ff7a4a", 0.006, 40.0))
    S.mountain_layer("Volcanoes", 150, 60, 260, [(-60, 175, 48, 0.75, 0.7), (30, 185, 60, 0.7, 0.7), (110, 170, 42, 0.8, 0.7)],
                     vm, nx=160, ny=40, seed=51, rough=5.0, z_off=-12.0)

    # --- braci che salgono
    em_ = flakes("Embers", (0, -14, 3), (0, 20, 6), env("EMBERS", 140), 5.0, 60.0, 0.03, 0.08, seed=12, color="#ffb03a", glow=6.0)
    tag_glow(em_.data.materials[0], True)

    # --- luci: lava da sotto (arancio), cielo, luce principale bianca sul Bacon Hair (la maglia resta verde)
    bl = A.world_bounds(rig)
    ac = Vector(((bl[0] + bl[1]) / 2).tolist())
    S.area_light("LavaBounce", tuple(ac + Vector((0, -2, -6))), tuple(ac), env("BOUNCE", 2500.0), 10.0, lin("#ff7a2a")[:3])
    S.area_light("KeyAv", tuple(ac + Vector((-5, -9, 6))), tuple(ac), env("KEY", 1400.0), 4.0, lin("#fff6ee")[:3])
    S.area_light("RimAv", tuple(ac + Vector((4, 8, 4))), tuple(ac), env("RIM", 1800.0), 3.0, lin("#ffd0a0")[:3])
    for name, objs in (("Beh", beh_objs), ("Aba", aba_objs), ("Bee", bee_objs)):
        lo, hi = S.bounds(objs)
        c = Vector(((lo + hi) / 2).tolist())
        size = float(hi[2] - lo[2])
        S.area_light(f"Key{name}", tuple(c + Vector((-0.6 * size, -1.8 * size, 1.0 * size))), tuple(c),
                     env("PKEY", 60.0) * size ** 2, 0.8 * size, lin("#ffe8d6")[:3])
        S.area_light(f"Rim{name}", tuple(c + Vector((0.4 * size, 1.6 * size, 0.8 * size))), tuple(c),
                     env("PRIM", 160.0) * size ** 2, 0.5 * size, lin("#ff9a4a")[:3])
    el, eh = S.bounds(egg_objs)
    S.point_light("ShrineGlow", tuple(Vector(((el + eh) / 2).tolist()) + Vector((0, -2, 0))), 900.0, 1.0, lin("#3ff6ff")[:3])

    cam_loc = env("CAM", (2.5, -10.0, 5.2))
    target = env("TARGET", (0.0, 20.0, 3.5))
    S.camera(cam_loc, target, lens=env("LENS", 24.0), dof_target=tuple(ac) if not PREVIEW else None, fstop=env("FSTOP", 8.0))
    pts = {"av_feet": bl[0], "av_head": rig.joints["HeadCenter"].matrix_world.translation, "shrine": (sx, sy, 5.0)}
    for name, objs in (("beh", beh_objs), ("aba", aba_objs), ("bee", bee_objs)):
        lo, hi = S.bounds(objs)
        pts[name] = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, hi[2])
    report(**pts)
    return render_all("extreme", tag, w, bloom=0.5, sat=1.08)


SCENES = {"steal": scene_steal, "giants": scene_giants, "extreme": scene_extreme}

if __name__ == "__main__":
    which = sys.argv[1]
    w = int(sys.argv[2]) if len(sys.argv) > 2 else 640
    samples = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    tag = sys.argv[4] if len(sys.argv) > 4 else ""
    SCENES[which](w, samples, tag)
