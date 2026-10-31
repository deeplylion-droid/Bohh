"""Scene 3D per le proposte di icona del gioco (512x512): render Cycles 1024x1024, poi bagliore e
riduzione a 512 in numpy/PIL.

Scene:
- guardiano: Cerbero sulla neve, inquadratura dal basso, che ringhia verso chi guarda e fa la guardia a
  un uovo incandescente; crepuscolo freddo e blu sulle vette innevate (le sue fiamme calde risaltano).
- uovo:      l'uovo-mostro (promo/egg_monster.py) su una cima innevata di notte, luna grande e pallida,
  neve che cade.
- toppa:     solo il soggetto (uovo-mostro) su sfondo trasparente, con luce da "giocattolo" per la
  toppa di feltro composta in HTML (promo/icon_compose.py).
- vetta / vetta_bandiera: revisione di "uovo": l'uovo-mostro sulla punta di un picco aguzzo (roccia
  sfaccettata, creste con cornici di neve), camera in bolla piu' bassa della vetta (l'orizzonte resta sotto
  la base dell'uovo), mare di nuvole con altre cime molto piu' in basso; con o senza bandierina di vetta.

Uso (dalla cartella art/; prima promo/egg_monster.py per l'uovo-mostro):
    nice -n 10 ../.tools/venv/bin/python promo/icon_scenes.py guardiano 1024 80 final
    nice -n 10 ../.tools/venv/bin/python promo/icon_scenes.py uovo 1024 96 final
    nice -n 10 ../.tools/venv/bin/python promo/icon_scenes.py toppa 1024 64 final
    nice -n 10 ../.tools/venv/bin/python promo/icon_scenes.py vetta 1024 64 final
    nice -n 10 ../.tools/venv/bin/python promo/icon_scenes.py vetta_bandiera 1024 64 final
Uscita in art/out/promo/icon_proposals/work/: <scena>_<tag>.png (render), _glow.png (passata delle superfici
luminose), _post.png (con bagliore e vignettatura), _512.png e _150.png (ridotte); per "toppa" solo il render
RGBA, che icon_compose.py mette sulla toppa di feltro.
Variabili d'ambiente per iterare: PREVIEW=1 (niente suddivisione delle mesh, niente profondita' di campo),
VT/LOOK/EXPO (gestione del colore), CAM e TARGET ("x,y,z"), LENS, EGG (Legendary/Primal) ed EGG_SCALE per il
guardiano, EGGCOL (red/cream/teal/orange/pink/mint) per l'uovo-mostro, KEY/FILL/RIM/GLOSS (luci), BLOOM;
per la vetta FEGG/MTOP/GAP (inquadratura), CAP/STEEP/RIDGE_A/RIDGE_LIFT/CORNICE (forma del picco), ZCLOUD,
FARZ, FLAG_SIDE/FLAG_POS/FLAG_LEN (bandierina).
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

ART = Path(__file__).resolve().parents[1]
PREVIEW = os.environ.get("PREVIEW", "") == "1"
OUT = ART / "out" / "promo" / "icon_proposals"
WORK = OUT / "work"


# =================================================================================== utilita'
def lin(c) -> tuple[float, float, float, float]:
    """Colore sRGB (0-255 o '#rrggbb') -> lineare RGBA."""
    if isinstance(c, str):
        c = tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))

    def f(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    return (f(c[0]), f(c[1]), f(c[2]), 1.0)


def env(name: str, default):
    v = os.environ.get(name)
    if v is None:
        return default
    if isinstance(default, tuple):
        return tuple(float(x) for x in v.split(","))
    return type(default)(v)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup_render(res: int, samples: int, vt="AgX", look="AgX - Punchy", exposure=0.0, transparent=False):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.015
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 8
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 6
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.blur_glossy = 1.0
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    sc.render.image_settings.color_depth = "8"
    sc.view_settings.view_transform = vt
    sc.view_settings.look = look if vt == "AgX" else "None"
    sc.view_settings.exposure = exposure
    return sc


def node(nt, kind, **inputs):
    n = nt.nodes.new(kind)
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def sock(n, ident, out=False):
    """Socket per identificatore (i nodi Mix hanno piu' ingressi con lo stesso nome)."""
    for s in (n.outputs if out else n.inputs):
        if s.identifier == ident:
            return s
    raise KeyError(ident)


def mix_color(nt, fac, a, b):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "RGBA"
    for val, ident in ((a, "A_Color"), (b, "B_Color")):
        if isinstance(val, tuple):
            sock(m, ident).default_value = val
        else:
            nt.links.new(val, sock(m, ident))
    if isinstance(fac, float):
        m.inputs[0].default_value = fac
    else:
        nt.links.new(fac, m.inputs[0])
    return sock(m, "Result_Color", out=True)


def math_node(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = float(v)
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def ramp(nt, fac, stops, interp="LINEAR"):
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.color_ramp.interpolation = interp
    el = r.color_ramp.elements
    el[0].position, el[0].color = stops[0][0], stops[0][1]
    el[1].position, el[1].color = stops[-1][0], stops[-1][1]
    for pos, col in stops[1:-1]:
        e = el.new(pos)
        e.color = col
    nt.links.new(fac, r.inputs["Fac"])
    return r.outputs["Color"]


def new_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return mat, nt, out


def fog_mix(nt, shader_out, fog_color, density, start=0.0, strength=1.0):
    """Prospettiva aerea economica: il materiale sfuma nel colore della foschia con la distanza."""
    cam = nt.nodes.new("ShaderNodeCameraData")
    d = math_node(nt, "SUBTRACT", cam.outputs["View Distance"], start)
    d = math_node(nt, "MAXIMUM", d, 0.0)
    e = math_node(nt, "MULTIPLY", d, -density)
    e = math_node(nt, "EXPONENT", e)
    fac = math_node(nt, "SUBTRACT", 1.0, e)
    em = node(nt, "ShaderNodeEmission", Color=fog_color, Strength=strength)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fac, mix.inputs[0])
    nt.links.new(shader_out, mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    return mix.outputs[0]


# =================================================================================== materiali
def snow_material(name="Snow", tint=(236, 244, 255), fog=None):
    mat, nt, out = new_material(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n1 = node(nt, "ShaderNodeTexNoise", Scale=22.0, Detail=6.0, Roughness=0.6)
    nt.links.new(tc.outputs["Object"], n1.inputs["Vector"])
    n2 = node(nt, "ShaderNodeTexNoise", Scale=1.6, Detail=3.0, Roughness=0.5)
    nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
    bump = node(nt, "ShaderNodeBump", Strength=0.22, Distance=0.05)
    h = math_node(nt, "ADD", n1.outputs["Fac"], math_node(nt, "MULTIPLY", n2.outputs["Fac"], 2.0))
    nt.links.new(h, bump.inputs["Height"])
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    base = lin(tint)
    # leggere variazioni di tinta (neve piu' azzurra nelle conche)
    col = mix_color(nt, n2.outputs["Fac"], tuple(c * 0.86 for c in base[:3]) + (1,), base)
    nt.links.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.42
    b.inputs["Subsurface Weight"].default_value = 0.35
    b.inputs["Subsurface Radius"].default_value = (0.35, 0.6, 1.0)
    b.inputs["Subsurface Scale"].default_value = 0.08
    b.inputs["Specular IOR Level"].default_value = 0.55
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    sh = b.outputs[0]
    if fog:
        sh = fog_mix(nt, sh, *fog)
    nt.links.new(sh, out.inputs["Surface"])
    return mat


def rock_snow_material(name, rock, snow, fog_color, density, start=0.0, snow_from=0.62, fog_strength=1.0):
    """Montagne sfaccettate: roccia sulle pareti ripide, neve sui pendii dolci, foschia con la distanza."""
    mat, nt, out = new_material(name)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["True Normal"], sep.inputs[0])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", Scale=0.35, Detail=2.0)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    k = math_node(nt, "ADD", sep.outputs["Z"], math_node(nt, "MULTIPLY", math_node(nt, "SUBTRACT", nz.outputs["Fac"], 0.5), 0.5))
    fac = ramp(nt, k, [(snow_from - 0.04, (0, 0, 0, 1)), (snow_from + 0.04, (1, 1, 1, 1))])
    col = mix_color(nt, fac, lin(rock), lin(snow))
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.8
    sh = fog_mix(nt, b.outputs[0], lin(fog_color), density, start, fog_strength)
    nt.links.new(sh, out.inputs["Surface"])
    return mat


def emission_material(name, color, strength):
    mat, nt, out = new_material(name)
    em = node(nt, "ShaderNodeEmission", Color=lin(color), Strength=strength)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


# =================================================================================== geometria
def grid_object(name, x0, x1, y0, y1, nx, ny, height, smooth=True):
    """Griglia (nx x ny vertici) con quota z = height(x, y) (array numpy)."""
    xs = np.linspace(x0, x1, nx)
    ys = np.linspace(y0, y1, ny)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    gz = height(gx, gy)
    verts = np.stack([gx, gy, gz], -1).reshape(-1, 3)
    idx = np.arange(nx * ny).reshape(nx, ny)
    a, b, c, d = idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]
    faces = np.stack([a, b, c, d], -1).reshape(-1, 4)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts.tolist(), [], faces.tolist())
    mesh.validate()
    for p in mesh.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def fbm(x, y, scale, octaves=4, seed=0):
    """Rumore frattale (vettoriale, numpy) con mathutils.noise."""
    out = np.zeros_like(x)
    off = Vector((seed * 17.3, seed * 9.1, seed * 3.7))
    flat_x, flat_y = x.ravel(), y.ravel()
    vals = np.array([noise.fractal(Vector((a * scale, b * scale, 0.0)) + off, 0.5, 2.0, octaves)
                     for a, b in zip(flat_x, flat_y)])
    out[...] = vals.reshape(x.shape)
    return out


def ridge_heights(gx, gy, peaks, rough_amp, seed):
    """Catena di picchi aguzzi: ogni picco e' una piramide irregolare, piu' rumore 'a cresta'."""
    h = np.full_like(gx, -5.0)
    for (px, py, ph, sx, sy) in peaks:
        h = np.maximum(h, ph - np.abs(gx - px) * sx - np.abs(gy - py) * sy - 0.35 * ((gx - px) * sx) ** 2 / max(ph, 1))
    n = fbm(gx, gy, 0.09, 4, seed)
    return h + rough_amp * (1.0 - np.abs(n)) * np.clip(h / 6.0, 0.2, 1.0) - 1.0


def mountain_layer(name, y0, depth, x_span, peaks, mat, nx=150, ny=40, rough=2.5, seed=1, z_off=0.0):
    ob = grid_object(name, -x_span, x_span, y0, y0 + depth, nx, ny,
                     lambda gx, gy: ridge_heights(gx, gy, peaks, rough, seed) + z_off, smooth=False)
    ob.data.materials.append(mat)
    return ob


def append_model(blend: Path, location=(0, 0, 0), rot_z=0.0, scale=1.0, prefix=""):
    """Carica tutte le mesh di un .blend del progetto sotto un empty (posizione/rotazione/scala)."""
    with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
        dst.objects = list(src.objects)
    root = bpy.data.objects.new(prefix + blend.stem, None)
    bpy.context.scene.collection.objects.link(root)
    objs = []
    for o in dst.objects:
        if o is None or o.type != "MESH" or o.name.startswith("ShadowCatcher"):
            continue
        bpy.context.scene.collection.objects.link(o)
        o.parent = root
        objs.append(o)
    root.location = location
    root.rotation_euler = (0, 0, math.radians(rot_z))
    root.scale = (scale, scale, scale)
    bpy.context.view_layer.update()
    return root, objs


def bounds(objs):
    pts = []
    for o in objs:
        m = o.matrix_world
        vs = o.data.vertices
        step = max(1, len(vs) // 600)
        pts.extend([m @ vs[i].co for i in range(0, len(vs), step)])
    a = np.array([tuple(p) for p in pts])
    return a.min(0), a.max(0)


def part(objs, name):
    for o in objs:
        if o.name.split(".")[0] == name:
            return o
    raise KeyError(name)


def principled(o):
    mat = o.data.materials[0]
    return mat.node_tree.nodes["Principled BSDF"]


def subdivide(objs, levels=1):
    for o in objs:
        mod = o.modifiers.new("sub", "SUBSURF")
        mod.levels = levels
        mod.render_levels = levels


# =================================================================================== luci, cielo, camera
def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def area_light(name, loc, target, energy, size, color, shape="DISK", camera=False):
    li = bpy.data.lights.new(name, "AREA")
    li.energy = energy
    li.size = size
    li.shape = shape
    li.color = color
    ob = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    look_at(ob, target)
    ob.visible_camera = camera
    return ob


def point_light(name, loc, energy, radius, color):
    li = bpy.data.lights.new(name, "POINT")
    li.energy = energy
    li.shadow_soft_size = radius
    li.color = color
    ob = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    return ob


def sun_light(name, direction, energy, color, angle=2.0):
    li = bpy.data.lights.new(name, "SUN")
    li.energy = energy
    li.color = color
    li.angle = math.radians(angle)
    ob = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(ob)
    d = Vector(direction).normalized()
    ob.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    return ob


def world_sky(cam_stops, light_color, light_strength, stars=0.0, star_scale=260.0, cam_strength=1.0):
    """Cielo a gradiente visto dalla camera (stops su elevazione 0..1) e luce ambiente separata."""
    sc = bpy.context.scene
    w = bpy.data.worlds.new("Sky")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    el = math_node(nt, "MAXIMUM", sep.outputs["Z"], 0.0)
    col = ramp(nt, el, cam_stops)
    if stars > 0:
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = star_scale
        vor.inputs["Randomness"].default_value = 1.0
        nt.links.new(tc.outputs["Generated"], vor.inputs["Vector"])
        st = ramp(nt, vor.outputs["Distance"], [(0.0, (1, 1, 1, 1)), (0.06, (0, 0, 0, 1))])
        # solo una parte delle celle diventa stella, e solo in alto nel cielo
        sel = ramp(nt, vor.outputs["Color"], [(0.0, (0, 0, 0, 1)), (0.7, (0, 0, 0, 1)), (0.72, (1, 1, 1, 1))], "CONSTANT")
        hi = ramp(nt, el, [(0.08, (0, 0, 0, 1)), (0.3, (1, 1, 1, 1))])
        s1 = math_node(nt, "MULTIPLY", st, sel)
        s1 = math_node(nt, "MULTIPLY", s1, hi)
        s1 = math_node(nt, "MULTIPLY", s1, stars)
        add = nt.nodes.new("ShaderNodeMix")
        add.data_type = "RGBA"
        add.blend_type = "ADD"
        add.inputs[0].default_value = 1.0
        nt.links.new(col, sock(add, "A_Color"))
        nt.links.new(s1, sock(add, "B_Color"))
        col = sock(add, "Result_Color", out=True)
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.inputs["Strength"].default_value = cam_strength
    nt.links.new(col, bg_cam.inputs["Color"])
    bg_light = node(nt, "ShaderNodeBackground", Color=light_color, Strength=light_strength)
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg_light.outputs[0], mix.inputs[1])
    nt.links.new(bg_cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return w


def camera(loc, target, lens=50.0, dof_target=None, fstop=4.0, shift=(0.0, 0.0)):
    cd = bpy.data.cameras.new("Cam")
    cd.lens = lens
    cd.sensor_width = 36
    cd.clip_start = 0.05
    cd.clip_end = 2000
    cd.shift_x, cd.shift_y = shift
    cam = bpy.data.objects.new("Cam", cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    look_at(cam, target)
    bpy.context.scene.camera = cam
    if dof_target is not None:
        cd.dof.use_dof = True
        cd.dof.focus_distance = (Vector(dof_target) - Vector(loc)).length
        cd.dof.aperture_fstop = fstop
    return cam


# =================================================================================== render e bagliore
def render_to(path: Path):
    sc = bpy.context.scene
    path.parent.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


def glow_pass(path: Path, res: int, emitters: set[str]):
    """Seconda passata veloce (bassa risoluzione): solo le superfici luminose, il resto e' holdout.
    Serve a costruire il bagliore (bloom) in post-produzione."""
    sc = bpy.context.scene
    hold, _, out = new_material("Holdout")
    hn = hold.node_tree.nodes.new("ShaderNodeHoldout")
    hold.node_tree.links.new(hn.outputs[0], out.inputs["Surface"])
    for o in sc.objects:
        if o.type == "LIGHT":
            o.hide_render = True
        if o.type != "MESH":
            continue
        name = o.name.split(".")[0]
        if name in emitters or any(o.name.startswith(e) for e in emitters):
            continue
        o.data.materials.clear()
        o.data.materials.append(hold)
    if sc.world:
        w = sc.world.node_tree
        for n in w.nodes:
            if n.type == "BACKGROUND":
                n.inputs["Strength"].default_value = 0.0
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.cycles.samples = 24
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 0
    if sc.camera.data.dof.use_dof:
        sc.camera.data.dof.use_dof = False
    return render_to(path)


def finish(beauty: Path, glow: Path | None, out512: Path, bloom=0.55, radii=(0.012, 0.035, 0.09), vignette=0.18,
           sharpen=0.6):
    """Aggiunge il bagliore (somma di sfocature gaussiane del passaggio luminoso), vignettatura leggera,
    riduce a 512 con Lanczos e applica una leggera maschera di contrasto."""
    from PIL import Image, ImageFilter
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
    if vignette > 0:
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        im *= (1.0 - vignette * np.clip(r - 0.55, 0, 1) ** 1.6)[..., None]
    full = Image.fromarray((np.clip(im, 0, 1) * 255 + 0.5).astype(np.uint8))
    full.save(beauty.with_name(beauty.stem + "_post.png"))
    small = full.resize((512, 512), Image.LANCZOS)
    if sharpen > 0:
        small = small.filter(ImageFilter.UnsharpMask(radius=1.2, percent=int(sharpen * 100), threshold=2))
    small.save(out512)
    small.resize((150, 150), Image.LANCZOS).save(out512.with_name(out512.stem.replace("_512", "") + "_150.png"))
    return out512


# =================================================================================== scena A
def scene_guardiano(res: int, samples: int, tag: str):
    reset()
    # Standard: fiamme e uovo d'oro restano saturi (con AgX diventano color pesca); il cielo e' piu' scuro per compensare
    setup_render(res, samples, vt=env("VT", "Standard"), look=env("LOOK", "None"), exposure=env("EXPO", -0.25))
    sc = bpy.context.scene

    # --- soggetti
    cer, cer_objs = append_model(ART / "out/pet/Cerberus/Cerberus.blend", (0, 0, 0), rot_z=env("CER_ROT", 0.0))
    egg_kind = env("EGG", "Legendary")
    egg_scale = env("EGG_SCALE", 0.36)
    egg_loc = env("EGG_LOC", (0.0, -1.85, -0.02))
    egg, egg_objs = append_model(ART / f"out/egg/Egg{egg_kind}/Egg{egg_kind}.blend", egg_loc, rot_z=env("EGG_ROT", -18.0),
                                 scale=egg_scale, prefix="E_")
    if not PREVIEW:
        subdivide(cer_objs + egg_objs, 1)
    # neon piu' intensi: fiamme e occhi devono bruciare nel blu della sera
    for o in cer_objs:
        n = o.name.split(".")[0]
        b = principled(o)
        if n == "Flames":
            fc = env("FLAME_C", (255.0, 90.0, 0.0))
            b.inputs["Emission Color"].default_value = lin(fc)
            b.inputs["Base Color"].default_value = lin(fc)
        if n in ("Flames", "LavaCracks", "EyeGlow"):
            b.inputs["Emission Strength"].default_value = {"Flames": env("FLAME_E", 1.0), "LavaCracks": 1.8,
                                                           "EyeGlow": env("EYE_E", 2.5)}[n]
        if n in ("Body", "Heads"):
            b.inputs["Base Color"].default_value = lin(env("BODY", (40, 34, 50)))
            b.inputs["Roughness"].default_value = 0.36
            b.inputs["Coat Weight"].default_value = 0.35
            b.inputs["Coat Roughness"].default_value = 0.12
    for o in egg_objs:
        b = principled(o)
        if b.inputs["Emission Strength"].default_value > 0:
            b.inputs["Emission Strength"].default_value = env("EGG_E", 1.8)
    cer_lo, cer_hi = bounds(cer_objs)
    print("[guardiano] Cerbero", np.round(cer_lo, 2), np.round(cer_hi, 2))
    for pn in ("Claws", "Heads", "Flames"):
        lo, hi = bounds([part(cer_objs, pn)])
        print(f"[guardiano] {pn}", np.round(lo, 2), np.round(hi, 2))

    # --- cielo del crepuscolo: zenit blu notte, orizzonte azzurro ghiaccio
    world_sky([(0.0, lin("#cfe7f5")), (0.06, lin("#97c0ea")), (0.18, lin("#4f80c8")), (0.34, lin("#26499a")),
               (0.55, lin("#132a66")), (1.0, lin("#081538"))],
              light_color=lin("#6f8fd0"), light_strength=0.55, stars=env("STARS", 3.0), star_scale=140.0, cam_strength=1.0)

    # --- neve: cresta sotto Cerbero, che scende dietro (la vetta) e ai lati
    def ground(gx, gy):
        back = np.clip(gy - 2.5, 0, None)
        z = -0.035 * back ** 2 - 0.008 * gx ** 2
        front = np.clip(-gy - 3.5, 0, None)
        z -= 0.02 * front ** 2
        calm = np.clip((gy + 4.5) / 3.0, 0.25, 1.0)  # davanti alla camera la neve e' piu' liscia e bassa
        z += (0.22 * fbm(gx, gy, 0.22, 3, 4) + 0.05 * fbm(gx, gy, 1.3, 2, 9)) * calm
        z -= 0.12 * np.clip(-gy - 2.4, 0, None)
        # neve ammucchiata attorno alle zampe e all'uovo (affondano un poco)
        for (px, py, r, hgt) in ((0, -0.9, 1.6, 0.07), (egg_loc[0], egg_loc[1], 0.8, 0.1)):
            z += hgt * np.exp(-((gx - px) ** 2 + (gy - py) ** 2) / (r * r))
        return z

    snow = grid_object("Snow", -16, 16, -12, 20, 230, 230, ground)
    snow.data.materials.append(snow_material("Snow", tint=(212, 228, 252), fog=(lin("#9cc4ea"), 0.012, 9.0)))

    # --- montagne lontane (tre file, sempre piu' nella foschia)
    fogc = "#8fb6e3"
    m1 = rock_snow_material("Mnt1", "#26304c", "#c9d8f0", fogc, 0.016, 10, snow_from=0.55)
    m2 = rock_snow_material("Mnt2", "#26304c", "#c4d4ee", fogc, 0.022, 10, snow_from=0.5)
    m3 = rock_snow_material("Mnt3", "#26304c", "#c0d0ec", fogc, 0.035, 10, snow_from=0.45)
    mountain_layer("Ridge1", 28, 26, 70, [(-26, 40, 19, 0.85, 0.9), (-6, 44, 15, 0.7, 0.7), (16, 38, 23, 0.9, 0.8),
                                         (36, 42, 17, 0.8, 0.8), (-44, 44, 14, 0.7, 0.7)], m1, seed=2, rough=3.0, z_off=env("MZ", -9.0))
    mountain_layer("Ridge2", 60, 30, 110, [(-50, 72, 30, 0.7, 0.6), (-12, 76, 26, 0.6, 0.6), (28, 70, 33, 0.7, 0.6),
                                          (64, 74, 24, 0.6, 0.6)], m2, seed=5, rough=4.0, z_off=env("MZ", -9.0) - 3)
    mountain_layer("Ridge3", 100, 40, 170, [(-90, 120, 40, 0.55, 0.5), (-30, 124, 46, 0.5, 0.5), (40, 118, 42, 0.55, 0.5),
                                           (100, 126, 38, 0.5, 0.5)], m3, seed=8, rough=5.0, z_off=env("MZ", -9.0) - 6)

    # --- luci: cielo freddo, controluce azzurro per staccare la sagoma nera, calore dell'uovo e delle fiamme
    cx = (cer_lo + cer_hi) / 2
    tgt = Vector((cx[0], cx[1], cx[2]))
    area_light("Key", (-5.0, -6.5, 5.5), tgt, env("KEY", 1000.0), 5.0, lin("#cfe0ff")[:3])
    area_light("RimL", (-5.0, 5.0, 5.5), tgt + Vector((0, -0.6, 1.0)), env("RIM", 2600.0), 3.0, lin("#9fd8ff")[:3])
    area_light("RimR", (5.5, 4.5, 5.0), tgt + Vector((0, -0.6, 1.0)), env("RIM", 2600.0) * 0.9, 3.0, lin("#b4e2ff")[:3])
    area_light("HeadRim", (0.0, 4.0, 7.5), tgt + Vector((0, -0.8, 1.2)), env("HEADRIM", 1800.0), 4.0, lin("#c4e6ff")[:3])
    e_lo, e_hi = bounds(egg_objs)
    ec = (e_lo + e_hi) / 2
    point_light("EggGlow", (ec[0], ec[1] - 0.4, ec[2] + 0.15), env("EGGLIGHT", 160.0), 0.35, lin("#ffb347")[:3])
    point_light("EggUp", (ec[0], ec[1] + 0.25, e_hi[2] + 0.2), env("EGGUP", 160.0), 0.3, lin("#ff9a3a")[:3])
    # luce calda e morbida sull'uovo dal lato della camera: l'oro deve brillare
    area_light("EggKey", (ec[0] - 0.9, ec[1] - 2.2, ec[2] + 1.4), tuple(ec), env("EGGKEY", 90.0), 1.2, lin("#ffe2b0")[:3])
    fl = part(cer_objs, "Flames")
    f_lo, f_hi = bounds([fl])
    for i, x in enumerate(np.linspace(f_lo[0] + 0.3, f_hi[0] - 0.3, 3)):
        point_light(f"Flame{i}", (x, (f_lo[1] + f_hi[1]) / 2 - 0.4, f_hi[2] - 0.35), env("FLAMELIGHT", 45.0), 0.25,
                    lin("#ff8c30")[:3])

    # --- camera bassa, leggermente di tre quarti
    cam_loc = env("CAM", (1.0, -6.9, 0.42))
    target = env("TARGET", (0.05, -0.6, 1.55))
    camera(cam_loc, target, lens=env("LENS", 53.0), shift=(0.0, env("SHIFT", 0.05)))

    name = "guardiano" + (f"_{tag}" if tag else "")
    beauty = render_to(WORK / f"{name}.png")
    glow = glow_pass(WORK / f"{name}_glow.png", max(256, res // 3), {"Flames", "LavaCracks", "EyeGlow", "E_"} |
                     {o.name for o in egg_objs if principled_emits(o)})
    finish(beauty, glow, WORK / f"{name}_512.png", bloom=env("BLOOM", 0.5))


# =================================================================================== scena B
SHELL_COLORS = {
    # guscio, macchie grandi, macchie piccole, punti di cucitura
    "cream": ((255, 242, 214), (186, 128, 84), (222, 172, 122), (226, 38, 64)),
    "red": ((232, 40, 56), (140, 14, 40), (255, 140, 132), (255, 250, 240)),
    "teal": ((52, 196, 186), (18, 112, 120), (160, 238, 226), (255, 250, 240)),
    "mint": ((150, 232, 200), (40, 150, 120), (210, 250, 232), (226, 38, 64)),
    "orange": ((255, 128, 40), (190, 60, 20), (255, 196, 120), (255, 250, 240)),
    "pink": ((255, 92, 160), (176, 30, 96), (255, 170, 210), (255, 250, 240)),
}


def flakes(name, cam_loc, target, n, dmin, dmax, rmin, rmax, seed, spread=0.62, mat=None):
    """Fiocchi di neve sparsi nel campo visivo della camera (una sola mesh di icosfere)."""
    import bmesh
    from mathutils import Matrix
    rng = random.Random(seed)
    fwd = (Vector(target) - Vector(cam_loc)).normalized()
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(fwd).normalized()
    bm = bmesh.new()
    for _ in range(n):
        d = dmin + (dmax - dmin) * rng.random() ** 1.6
        u, v = rng.uniform(-spread, spread), rng.uniform(-spread, spread)
        p = Vector(cam_loc) + fwd * d + right * (u * d * 0.75) + up * (v * d * 0.75)
        r = rng.uniform(rmin, rmax) * (0.6 + 0.4 * d / dmax)
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r, matrix=Matrix.Translation(p))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    ob.visible_shadow = False
    return ob


def moon_disc(name, cam_loc, direction, dist, radius, color="#fff4dc", strength=2.4):
    """Luna: disco emissivo rivolto alla camera, con 'mari' piu' scuri (rumore)."""
    import bmesh
    from mathutils import Matrix
    d = Vector(direction).normalized()
    center = Vector(cam_loc) + d * dist
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=radius)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = center
    ob.rotation_euler = (-d).to_track_quat("Z", "Y").to_euler()
    mat, nt, out = new_material(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", Scale=2.2, Detail=4.0, Roughness=0.55)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    vec = nt.nodes.new("ShaderNodeVectorMath")
    vec.operation = "SCALE"
    vec.inputs["Scale"].default_value = 1.0 / radius
    nt.links.new(tc.outputs["Object"], vec.inputs[0])
    nz.inputs["Scale"].default_value = 2.4
    nt.links.new(vec.outputs[0], nz.inputs["Vector"])
    maria = ramp(nt, nz.outputs["Fac"], [(0.45, (1, 1, 1, 1)), (0.62, (0.78, 0.76, 0.72, 1))])
    base = mix_color(nt, 1.0, lin(color), lin(color))
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs[0].default_value = 1.0
    nt.links.new(base, sock(mul, "A_Color"))
    nt.links.new(maria, sock(mul, "B_Color"))
    em = node(nt, "ShaderNodeEmission", Strength=strength)
    nt.links.new(sock(mul, "Result_Color", out=True), em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    ob.data.materials.append(mat)
    ob.visible_diffuse = ob.visible_glossy = ob.visible_shadow = ob.visible_transmission = False
    return ob, center


def scene_uovo(res: int, samples: int, tag: str):
    reset()
    setup_render(res, samples, vt=env("VT", "AgX"), look=env("LOOK", "AgX - Punchy"), exposure=env("EXPO", -0.1))
    egg, objs = append_model(ART / "out/promo/EggMonster/EggMonster.blend", (0, 0, -0.04), rot_z=env("EGG_ROT", 10.0))
    if not PREVIEW:
        subdivide([o for o in objs if o.name.split(".")[0] in ("Shell", "Teeth", "Inside", "Eyes", "Creature")], 1)
    style_egg_monster(objs, env("EGGCOL", "red"), env("EYE_E", 3.4))
    lo, hi = bounds(objs)
    print("[uovo] uovo-mostro", np.round(lo, 2), np.round(hi, 2))
    eyes_lo, eyes_hi = bounds([part(objs, "Eyes")])
    eye_c = (eyes_lo + eyes_hi) / 2

    # --- cielo notturno con stelle
    world_sky([(0.0, lin("#2a4a86")), (0.08, lin("#1d3770")), (0.25, lin("#12265a")), (0.5, lin("#0a1840")),
               (1.0, lin("#060e2a"))], light_color=lin("#3d5a9e"), light_strength=0.35, stars=env("STARS", 4.0),
              star_scale=120.0)

    # --- camera e luna
    cam_loc = Vector(env("CAM", (1.2, -6.2, 0.9)))
    target = Vector(env("TARGET", (0.05, 0.0, 1.8)))
    lens = env("LENS", 50.0)
    cam = camera(tuple(cam_loc), tuple(target), lens=lens, dof_target=tuple(target) if not PREVIEW else None,
                 fstop=env("FSTOP", 3.2), shift=(env("SHIFTX", 0.0), env("SHIFTY", 0.0)))
    fwd = (target - cam_loc).normalized()
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(fwd).normalized()
    mu, mv = env("MOON", (-0.16, 0.2))  # posizione della luna nel fotogramma (frazioni del campo visivo)
    half = math.tan(math.atan(18.0 / lens))
    mdir = (fwd + right * (mu * 2 * half) + up * (mv * 2 * half)).normalized()
    mdist = 400.0
    mrad = env("MOON_R", 0.2) * 2 * half * mdist  # raggio come frazione della larghezza del fotogramma
    _, mc = moon_disc("Moon", tuple(cam_loc), tuple(mdir), mdist, mrad, strength=env("MOON_E", 1.25))

    # --- cima innevata: l'uovo sta sulla vetta, il terreno scende tutt'intorno
    def ground(gx, gy):
        r = np.sqrt(gx ** 2 + (gy * 0.9) ** 2)
        z = -0.05 * np.clip(r - 1.9, 0, None) ** 1.7
        z += (0.16 * fbm(gx, gy, 0.3, 3, 11) + 0.04 * fbm(gx, gy, 1.5, 2, 3)) * np.clip(r / 2.5, 0.3, 1.0)
        z += 0.14 * np.exp(-(gx ** 2 + gy ** 2) / 1.3 ** 2)  # neve ammucchiata attorno all'uovo
        return z

    snow = grid_object("Snow", -14, 14, -12, 16, 220, 220, ground)
    snow.data.materials.append(snow_material("Snow", tint=(228, 238, 255), fog=(lin("#1d3770"), 0.02, 8.0)))
    fogc = "#1d3770"
    m1 = rock_snow_material("Mnt1", "#141c34", "#8fa6d4", fogc, 0.018, 8, snow_from=0.5)
    m2 = rock_snow_material("Mnt2", "#141c34", "#8299c8", fogc, 0.026, 8, snow_from=0.48)
    mountain_layer("Ridge1", 26, 26, 70, [(-28, 38, 18, 0.85, 0.9), (-8, 44, 14, 0.7, 0.7), (14, 36, 21, 0.9, 0.8),
                                         (34, 42, 16, 0.8, 0.8)], m1, seed=12, rough=3.0, z_off=env("MZ", -11.0))
    mountain_layer("Ridge2", 56, 30, 110, [(-46, 70, 28, 0.7, 0.6), (-6, 76, 24, 0.6, 0.6), (30, 68, 30, 0.7, 0.6),
                                          (66, 74, 22, 0.6, 0.6)], m2, seed=15, rough=4.0, z_off=env("MZ", -11.0) - 4)

    # --- neve che cade
    fl_mat, nt, out = new_material("Flake")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (0.9, 0.94, 1.0, 1)
    b.inputs["Emission Color"].default_value = lin("#cfe0ff")
    b.inputs["Emission Strength"].default_value = 0.35
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    flakes("Flakes", tuple(cam_loc), tuple(target), env("FLAKES", 220), 3.0, 30.0, 0.014, 0.04, seed=4, mat=fl_mat)

    # --- luci: luna in controluce, riempimento freddo dal davanti, bagliore giallo dentro la bocca
    sun_light("MoonLight", tuple(mc - Vector((0, 0, 0))), env("MOONL", 2.6), lin("#d6e4ff")[:3], angle=1.0)
    c = (lo + hi) / 2
    area_light("Fill", (-4.5, -6.5, 4.0), (c[0], c[1], c[2]), env("FILL", 520.0), 6.0, lin("#9bb6ff")[:3])
    area_light("KeyR", (5.0, -5.0, 3.5), (c[0], c[1], c[2] + 0.3), env("KEY", 450.0), 4.0, lin("#dfe8ff")[:3])
    # riflesso lucido da giocattolo di vinile sul guscio (piccola luce morbida in alto a sinistra della camera)
    area_light("Gloss", (-2.2, -6.0, 5.2), (c[0], c[1], c[2] + 0.4), env("GLOSS", 550.0), 1.6, lin("#f4f7ff")[:3])
    area_light("RimB", (-2.5, 5.0, 4.5), (c[0], c[1], c[2] + 0.4), env("RIM", 900.0), 3.0, lin("#cfe0ff")[:3])
    point_light("Inner", (eye_c[0], eye_c[1] - 0.12, eye_c[2] - 0.05), env("INNER", 18.0), 0.12, lin("#ffc34a")[:3])

    name = "uovo" + (f"_{tag}" if tag else "")
    beauty = render_to(WORK / f"{name}.png")
    glow = glow_pass(WORK / f"{name}_glow.png", max(256, res // 3), {"Eyes", "Moon"})
    finish(beauty, glow, WORK / f"{name}_512.png", bloom=env("BLOOM", 0.5), radii=(0.012, 0.04, 0.1))


# =================================================================================== scena B, variante "vetta"
def turb(x, y, scale, octaves=4, seed=0):
    """Rumore 'a nuvola' (turbolenza morbida: somma di |rumore|, gonfia e tondeggiante)."""
    off = Vector((seed * 13.1, seed * 7.7, seed * 2.9))
    vals = np.array([noise.turbulence(Vector((a * scale, b * scale, 0.0)) + off, octaves, False)
                     for a, b in zip(x.ravel(), y.ravel())])
    return vals.reshape(x.shape)


def level_camera(egg_xy, az_deg, lens, h_top, f_egg, m_top, gap, dof_target=None, fstop=3.2, shift_x=0.0):
    """Camera in bolla (verticali dritte) piu' bassa della base dell'uovo, con decentramento verticale.

    f_egg = altezza dell'uovo in frazione del fotogramma, m_top = margine sopra la calotta, gap = di quanto
    (frazione del fotogramma) la base dell'uovo sta sopra la linea dell'orizzonte. La base e' a z = 0."""
    F = 36.0 / lens
    d = h_top / (f_egg * F)
    z_cam = -gap * F * d
    t_top = (h_top - z_cam) / d + m_top * F
    shift = t_top / F - 0.5
    a = math.radians(az_deg)
    loc = Vector((egg_xy[0] + math.sin(a) * d, egg_xy[1] - math.cos(a) * d, z_cam))
    tgt = Vector((egg_xy[0], egg_xy[1], z_cam))
    cam = camera(tuple(loc), tuple(tgt), lens=lens, dof_target=dof_target, fstop=fstop, shift=(shift_x, shift))
    print(f"[vetta] camera: distanza {d:.2f}, quota {z_cam:.2f}, shift {shift:.3f}, orizzonte al {100 * (0.5 + shift):.0f}%")
    return cam, loc, tgt, shift, F


def cloud_material(name, color, fog_color, density, start, glow=0.08):
    mat, nt, out = new_material(name)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = lin(color)
    b.inputs["Roughness"].default_value = 1.0
    b.inputs["Sheen Weight"].default_value = 0.6
    b.inputs["Sheen Tint"].default_value = (0.8, 0.86, 1.0, 1)
    b.inputs["Emission Color"].default_value = lin(color)
    b.inputs["Emission Strength"].default_value = glow  # nuvole al chiaro di luna: un filo di luce propria
    sh = fog_mix(nt, b.outputs[0], lin(fog_color), density, start)
    nt.links.new(sh, out.inputs["Surface"])
    return mat


def felt_material(name, color, sheen=0.6):
    mat, nt, out = new_material(name)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", Scale=180.0, Detail=4.0)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bump = node(nt, "ShaderNodeBump", Strength=0.25, Distance=0.004)
    nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Base Color"].default_value = lin(color)
    b.inputs["Roughness"].default_value = 0.9
    b.inputs["Sheen Weight"].default_value = sheen
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    return mat


def summit_flag(foot, side, height=2.2, lean=(0.0, 0.0), length=0.82, width=0.5, color=(255, 46, 77)):
    """Bandierina di vetta: asta di legno piantata nella neve, pomello dorato e stendardo triangolare di feltro
    rosso che sventola verso 'side', con i punti di cucitura bianchi lungo i bordi (come l'interfaccia)."""
    import bmesh
    from mathutils import Euler, Matrix
    rot = Euler((math.radians(lean[0]), math.radians(lean[1]), 0.0)).to_matrix()
    axis = rot @ Vector((0, 0, 1))
    side = Vector(side).normalized()
    side = (side - axis * side.dot(axis)).normalized()
    nrm = axis.cross(side).normalized()
    p0 = Vector(foot) - axis * 0.3
    p1 = Vector(foot) + axis * height

    def obj_from(bm, name, mat, smooth=True):
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for poly in me.polygons:
            poly.use_smooth = smooth
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        ob.data.materials.append(mat)
        return ob

    # asta e pomello
    basis = Matrix((side, nrm, axis)).transposed().to_4x4()
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.042, radius2=0.034, depth=(p1 - p0).length,
                          matrix=Matrix.Translation((p0 + p1) / 2) @ basis)
    wood, nt, out = new_material("Wood")
    bw = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bw.inputs["Base Color"].default_value = lin((150, 98, 52))
    bw.inputs["Roughness"].default_value = 0.55
    nt.links.new(bw.outputs[0], out.inputs["Surface"])
    obj_from(bm, "FlagPole", wood)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=0.075, matrix=Matrix.Translation(p1 + axis * 0.05))
    gold, nt, out = new_material("Gold")
    bg = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bg.inputs["Base Color"].default_value = lin((255, 196, 60))
    bg.inputs["Metallic"].default_value = 1.0
    bg.inputs["Roughness"].default_value = 0.25
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    obj_from(bm, "FlagKnob", gold)

    # stendardo: triangolo ondulato (base lungo l'asta, punta verso 'side', un po' cadente)
    top = p1 - axis * 0.07

    def cloth(u, v):
        wave = 0.075 * u * math.sin(2 * math.pi * 1.25 * u + 0.5)
        return (top - axis * (width * 0.5) + axis * (width * (1 - u) * (v - 0.5)) + side * (length * u)
                - axis * (0.13 * u * u) + nrm * wave)

    nu, nv = 28, 8
    verts = [cloth(i / nu, j / nv) for i in range(nu + 1) for j in range(nv + 1)]
    faces = [(i * (nv + 1) + j, (i + 1) * (nv + 1) + j, (i + 1) * (nv + 1) + j + 1, i * (nv + 1) + j + 1)
             for i in range(nu) for j in range(nv)]
    me = bpy.data.meshes.new("Pennant")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate()
    for poly in me.polygons:
        poly.use_smooth = True
    pen = bpy.data.objects.new("Pennant", me)
    bpy.context.scene.collection.objects.link(pen)
    sol = pen.modifiers.new("spessore", "SOLIDIFY")
    sol.thickness = 0.018
    sol.offset = 0.0
    pen.data.materials.append(felt_material("FeltRed", color))

    # punti di cucitura bianchi lungo i tre bordi, sul lato verso la camera (-nrm)
    bm = bmesh.new()
    inset = 0.07

    def dash_line(pts):
        acc = 0.0
        for a, b in zip(pts[:-1], pts[1:]):
            seg = (b - a).length
            t = 0.0
            while t < seg:
                if (acc % 0.085) < 0.045:
                    c = a + (b - a) * (t / seg)
                    tang = (b - a).normalized()
                    bin_ = nrm.cross(tang).normalized()
                    m = Matrix((tang * 0.042, bin_ * 0.016, nrm * 0.008)).transposed().to_4x4()
                    m.translation = c - nrm * 0.016
                    bmesh.ops.create_cube(bm, size=1.0, matrix=m)
                step = 0.012
                t += step
                acc += step

    edge_top = [cloth(i / nu, 1.0) - axis * inset * (1 - i / nu) * 0.9 for i in range(nu - 3)]
    edge_bot = [cloth(i / nu, 0.0) + axis * inset * (1 - i / nu) * 0.9 for i in range(nu - 3)]
    edge_pole = [cloth(0.06, j / nv) for j in range(1, nv)]
    for line in (edge_top, edge_bot, edge_pole):
        dash_line(line)
    thread, nt, out = new_material("Thread")
    bt = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bt.inputs["Base Color"].default_value = lin((255, 252, 246))
    bt.inputs["Roughness"].default_value = 0.8
    nt.links.new(bt.outputs[0], out.inputs["Surface"])
    obj_from(bm, "PennantStitches", thread, smooth=False)


def scene_vetta(res: int, samples: int, tag: str, flag: bool = False):
    """Variante di B: l'uovo-mostro sulla punta di un picco aguzzo, sopra un mare di nuvole al chiaro di luna."""
    reset()
    setup_render(res, samples, vt=env("VT", "AgX"), look=env("LOOK", "AgX - Punchy"), exposure=env("EXPO", -0.1))
    egg_rot = env("EGG_ROT", 10.0)
    egg, objs = append_model(ART / "out/promo/EggMonster/EggMonster.blend", (0, 0, -0.08), rot_z=egg_rot)
    if not PREVIEW:
        subdivide([o for o in objs if o.name.split(".")[0] in ("Shell", "Teeth", "Inside", "Eyes", "Creature")], 1)
    style_egg_monster(objs, env("EGGCOL", "red"), env("EYE_E", 3.4))
    lo, hi = bounds(objs)
    eyes_lo, eyes_hi = bounds([part(objs, "Eyes")])
    eye_c = (eyes_lo + eyes_hi) / 2
    c = (lo + hi) / 2

    world_sky([(0.0, lin("#34579a")), (0.06, lin("#1f3b76")), (0.22, lin("#12265a")), (0.5, lin("#0a1840")),
               (1.0, lin("#060e2a"))], light_color=lin("#3d5a9e"), light_strength=0.35, stars=env("STARS", 4.0),
              star_scale=120.0)

    # --- camera in bolla, piu' bassa della vetta: l'orizzonte (e le altre cime) restano sotto la base dell'uovo
    az = env("CAM_AZ", 10.5)
    lens = env("LENS", 70.0)
    cam, cam_loc, _, shift, F = level_camera(
        (0.0, 0.0), az, lens, float(hi[2]), env("FEGG", 0.67), env("MTOP", 0.06), env("GAP", 0.07),
        dof_target=tuple(c) if not PREVIEW else None, fstop=env("FSTOP", 4.0), shift_x=env("SHIFTX", 0.0))
    fwd = Vector((-math.sin(math.radians(az)), math.cos(math.radians(az)), 0.0))
    right = Vector((math.cos(math.radians(az)), math.sin(math.radians(az)), 0.0))
    up = Vector((0, 0, 1))
    mu, mv = env("MOON", (-0.16, 0.2))
    mdir = (fwd + right * ((mu - env("SHIFTX", 0.0)) * F) + up * ((mv + shift) * F)).normalized()
    mdist = 600.0
    _, mc = moon_disc("Moon", tuple(cam_loc), tuple(mdir), mdist, env("MOON_R", 0.2) * F * mdist,
                      strength=env("MOON_E", 1.25))

    # --- il picco: roccia sfaccettata che precipita su tutti i lati, con creste verso la camera e dietro
    cap = env("CAP", 0.95)
    steep = env("STEEP", 1.6)

    def rock(gx, gy):
        r = np.hypot(gx, gy)
        th = np.arctan2(gx, -gy)  # 0 = davanti (-Y), positivo verso +X
        z = -0.15 * r - steep * np.clip(r - cap, 0, None) ** 1.2
        ra_l, ra_r = az - env("RIDGE_A", 55.0), az + env("RIDGE_A", 55.0) - 4
        rl = env("RIDGE_LIFT", 0.52)
        for ra, lift, w in ((ra_l, rl, 0.3), (ra_r, rl * 0.94, 0.3), (az + 180, 0.4, 0.45), (az + 115, 0.3, 0.4)):
            dth = np.angle(np.exp(1j * (th - math.radians(ra))))
            across = r * np.sin(dth)
            ridge = np.exp(-(across / (w + 0.12 * r)) ** 2) * (np.cos(dth) > 0)
            z += lift * steep * ridge * np.clip(r - cap * 0.75, 0, None) ** 1.18
        z += 0.6 * np.abs(fbm(gx, gy, 0.55, 3, 21)) * np.clip((r - cap) / 2.0, 0, 1)
        return z

    def snow_cap(gx, gy):
        r = np.hypot(gx, gy)
        th = np.arctan2(gx, -gy)
        thick = 0.24 * np.exp(-(r / env("CAPR", 1.3)) ** 4) - 0.06
        # neve anche sul filo delle creste davanti (cornici)
        for ra in (az - env("RIDGE_A", 55.0), az + env("RIDGE_A", 55.0) - 4):
            dth = np.angle(np.exp(1j * (th - math.radians(ra))))
            across = r * np.sin(dth)
            thick += env("CORNICE", 0.08) * np.exp(-(across / (0.16 + 0.05 * r)) ** 2) * (np.cos(dth) > 0) * (r > 0.9)
        return rock(gx, gy) + thick + 0.04 * fbm(gx, gy, 1.3, 2, 5)

    z0 = float(snow_cap(np.array([[0.0]]), np.array([[0.0]]))[0, 0])
    off = 0.0 - z0  # la neve in cima sta a z = 0 (l'uovo affonda di 8 cm)
    rk = grid_object("Summit", -24, 24, -24, 24, 150, 150, lambda gx, gy: rock(gx, gy) + off, smooth=False)
    rk.data.materials.append(rock_snow_material("SummitRock", "#232c48", "#dbe6fa", "#1f3b76", 0.004, 12, snow_from=0.66))
    sn = grid_object("SummitSnow", -7, 7, -7, 7, 230, 230, lambda gx, gy: snow_cap(gx, gy) + off)
    sn.data.materials.append(snow_material("Snow", tint=(228, 238, 255), fog=(lin("#1f3b76"), 0.01, 12.0)))

    # --- mare di nuvole molto piu' in basso, con altre cime che ne spuntano
    zc = env("ZCLOUD", -14.0)
    cl = grid_object("Clouds", -420, 420, -60, 900, 260, 260,
                     lambda gx, gy: zc + 4.5 * turb(gx, gy, 0.022, 4, 3) + 3.5 * fbm(gx, gy, 0.006, 2, 9))
    cl.data.materials.append(cloud_material("Clouds", (214, 226, 248), "#3a5ea2", env("CLOUDFOG", 0.0018), 40.0,
                                            glow=env("CLOUDGLOW", 0.24)))
    fogc = "#34579a"
    m1 = rock_snow_material("Far1", "#1a2440", "#b4c6ea", fogc, env("FARFOG", 0.0055), 30, snow_from=0.5)
    m2 = rock_snow_material("Far2", "#1a2440", "#a8bce4", fogc, env("FARFOG", 0.0055) * 1.4, 30, snow_from=0.48)
    # le punte restano qualche metro sotto la nostra vetta (z = 0): basi nascoste nelle nuvole
    fz = env("FARZ", -27.0)
    # (la camera guarda un po' verso -X: a 200 m il fotogramma va da x = -87 a x = 17, a 340 m da -148 a 28)
    mountain_layer("FarPeaks1", 160, 70, 260, [(-82, 196, 20, 0.6, 0.5), (-60, 206, 15, 0.55, 0.5), (4, 190, 18, 0.6, 0.5),
                                              (24, 204, 14, 0.55, 0.5), (-140, 200, 19, 0.55, 0.5)], m1, nx=200, ny=50,
                   seed=31, rough=4.0, z_off=fz)
    mountain_layer("FarPeaks2", 300, 90, 420, [(-132, 340, 23, 0.45, 0.4), (-104, 352, 19, 0.42, 0.4), (-40, 336, 24, 0.45, 0.4),
                                              (12, 346, 22, 0.42, 0.4), (40, 340, 20, 0.45, 0.4)], m2, nx=220, ny=50, seed=37,
                   rough=5.0, z_off=fz - 4)

    # --- neve che cade (stesso fiocco della versione B)
    fl_mat, nt, out = new_material("Flake")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (0.9, 0.94, 1.0, 1)
    b.inputs["Emission Color"].default_value = lin("#cfe0ff")
    b.inputs["Emission Strength"].default_value = 0.35
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    view_c = cam_loc + fwd + up * (shift * F)
    flakes("Flakes", tuple(cam_loc), tuple(view_c), env("FLAKES", 240), 4.5, 40.0, 0.014, 0.042, seed=4, mat=fl_mat, spread=0.42)

    # --- bandierina di vetta (variante)
    if flag:
        fside = env("FLAG_SIDE", 1.0)  # +1 = a destra dell'uovo (bilancia la luna a sinistra), -1 = a sinistra
        fx, fy = env("FLAG_POS", (1.18, -0.12))
        foot = right * (fside * fx) + fwd * fy
        fz_ = float(snow_cap(np.array([[foot.x]]), np.array([[foot.y]]))[0, 0]) + off
        summit_flag((foot.x, foot.y, fz_), right * fside, height=env("FLAG_H", 2.15), lean=(0.0, fside * env("FLAG_LEAN", 6.0)),
                    length=env("FLAG_LEN", 0.72), width=env("FLAG_W", 0.46))

    # --- luci: come la versione B
    sun_light("MoonLight", tuple(mc - cam_loc), env("MOONL", 2.6), lin("#d6e4ff")[:3], angle=1.0)
    area_light("Fill", (-4.5, -6.5, 4.0), (c[0], c[1], c[2]), env("FILL", 520.0), 6.0, lin("#9bb6ff")[:3])
    area_light("KeyR", (5.0, -5.0, 3.5), (c[0], c[1], c[2] + 0.3), env("KEY", 450.0), 4.0, lin("#dfe8ff")[:3])
    area_light("Gloss", (-2.2, -6.0, 5.2), (c[0], c[1], c[2] + 0.4), env("GLOSS", 550.0), 1.6, lin("#f4f7ff")[:3])
    area_light("RimB", (-2.5, 5.0, 4.5), (c[0], c[1], c[2] + 0.4), env("RIM", 900.0), 3.0, lin("#cfe0ff")[:3])
    area_light("SummitFill", (1.0, -9.0, -2.5), (0.0, 0.0, -0.8), env("SUMMITFILL", 650.0), 6.0, lin("#a9bfff")[:3])
    point_light("Inner", (eye_c[0], eye_c[1] - 0.12, eye_c[2] - 0.05), env("INNER", 18.0), 0.12, lin("#ffc34a")[:3])

    name = ("vetta_bandiera" if flag else "vetta") + (f"_{tag}" if tag else "")
    beauty = render_to(WORK / f"{name}.png")
    glow = glow_pass(WORK / f"{name}_glow.png", max(256, res // 3), {"Eyes", "Moon"})
    finish(beauty, glow, WORK / f"{name}_512.png", bloom=env("BLOOM", 0.5), radii=(0.012, 0.04, 0.1))


# =================================================================================== scena C (solo soggetto)
def style_egg_monster(objs, shell="red", eye_e=3.0):
    shell_c, spot_c, spot2_c, thread_c = SHELL_COLORS[shell]
    for o in objs:
        n = o.name.split(".")[0]
        b = principled(o)
        if n == "Shell":
            b.inputs["Base Color"].default_value = lin(shell_c)
            b.inputs["Roughness"].default_value = 0.3
            b.inputs["Coat Weight"].default_value = 0.5
            b.inputs["Coat Roughness"].default_value = 0.08
        elif n == "Spots":
            b.inputs["Base Color"].default_value = lin(spot_c)
        elif n == "Spots2":
            b.inputs["Base Color"].default_value = lin(spot2_c)
        elif n == "Stitches":
            b.inputs["Base Color"].default_value = lin(thread_c)
        elif n == "Teeth":
            b.inputs["Roughness"].default_value = 0.22
            b.inputs["Coat Weight"].default_value = 0.6
            b.inputs["Coat Roughness"].default_value = 0.05
        elif n in ("Inside", "Creature"):
            b.inputs["Roughness"].default_value = 0.75
        elif n == "Eyes":
            b.inputs["Emission Strength"].default_value = eye_e


def scene_toppa(res: int, samples: int, tag: str):
    """Soggetto della toppa: uovo-mostro su sfondo trasparente, luce da foto di prodotto (giocattolo)."""
    reset()
    setup_render(res, samples, vt=env("VT", "Standard"), look=env("LOOK", "AgX - Punchy"), exposure=env("EXPO", 0.0),
                 transparent=True)
    egg, objs = append_model(ART / "out/promo/EggMonster/EggMonster.blend", (0, 0, 0), rot_z=env("EGG_ROT", 14.0))
    if not PREVIEW:
        subdivide([o for o in objs if o.name.split(".")[0] in ("Shell", "Teeth", "Inside", "Eyes", "Creature")], 1)
    style_egg_monster(objs, env("EGGCOL", "red"), env("EYE_E", 3.0))
    lo, hi = bounds(objs)
    c = Vector(((lo + hi) / 2).tolist())
    eyes_lo, eyes_hi = bounds([part(objs, "Eyes")])
    eye_c = (eyes_lo + eyes_hi) / 2
    world_sky([(0.0, lin("#cdd9ee")), (1.0, lin("#e9eef8"))], light_color=lin("#dfe6f4"), light_strength=0.6)
    area_light("Key", (-4.0, -5.5, 5.5), tuple(c), env("KEY", 700.0), 4.5, lin("#fff3e6")[:3])
    area_light("Fill", (5.0, -4.5, 2.2), tuple(c), env("FILL", 300.0), 5.0, lin("#cfe0ff")[:3])
    area_light("Rim", (2.5, 5.0, 5.0), tuple(c + Vector((0, 0, 0.6))), env("RIM", 1200.0), 3.0, lin("#ffffff")[:3])
    area_light("RimL", (-4.0, 3.5, 3.0), tuple(c + Vector((0, 0, 0.4))), env("RIM", 1200.0) * 0.6, 3.0, lin("#dff0ff")[:3])
    point_light("Inner", (eye_c[0], eye_c[1] - 0.12, eye_c[2] - 0.05), env("INNER", 7.0), 0.12, lin("#ffc34a")[:3])
    # niente ombra a terra: l'ombra di contatto sul feltro la disegna l'HTML
    cam_loc = Vector(env("CAM", (1.2, -9.0, 1.6)))
    target = Vector(env("TARGET", (0.05, 0.0, 1.72)))
    camera(tuple(cam_loc), tuple(target), lens=env("LENS", 60.0))
    name = "toppa_hero" + (f"_{tag}" if tag else "")
    beauty = render_to(WORK / f"{name}.png")
    print(f"[toppa] {beauty}")


def principled_emits(o) -> bool:
    try:
        b = o.data.materials[0].node_tree.nodes["Principled BSDF"]
        return b.inputs["Emission Strength"].default_value > 0 and max(b.inputs["Emission Color"].default_value[:3]) > 0
    except (KeyError, IndexError, AttributeError):
        return False


SCENES = {"guardiano": scene_guardiano, "uovo": scene_uovo, "toppa": scene_toppa, "vetta": scene_vetta,
          "vetta_bandiera": lambda res, samples, tag: scene_vetta(res, samples, tag, flag=True)}

if __name__ == "__main__":
    which = sys.argv[1]
    res = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
    samples = int(sys.argv[3]) if len(sys.argv) > 3 else 96
    tag = sys.argv[4] if len(sys.argv) > 4 else ""
    SCENES[which](res, samples, tag)
