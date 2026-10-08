"""Scena di anteprima: tornante della zona Prati con nido, uova, Pulcino e vetta sullo sfondo."""
import math
import sys
from pathlib import Path

import bpy  # noqa: I001 (bpy prima di bmesh)
import bmesh
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.render import setup_world  # noqa: E402
from lib.toy import OUT, srgb_to_linear  # noqa: E402

RES = (1600, 900)
rng = np.random.default_rng(42)


def mat(name, rgb, rough=0.6, metal=0.0, emit=0.0, rgb2=None, scale=0.02):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    col = [srgb_to_linear(c) for c in rgb] + [1]
    b.inputs["Base Color"].default_value = col
    if rgb2 is not None:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = scale
        noise.inputs["Detail"].default_value = 1.0
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        ramp.color_ramp.elements[0].color = col
        ramp.color_ramp.elements[1].position = 0.56
        ramp.color_ramp.elements[1].color = [srgb_to_linear(c) for c in rgb2] + [1]
        nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = col
        b.inputs["Emission Strength"].default_value = emit
    return m


# ------------------------------------------------------------------ percorso a tornante
UP_Y, LOW_Y, HAIR_X, X0 = 92.0, 10.0, 95.0, -260.0
HALF_W = 20.0


def path_points(n_leg=60, n_turn=30):
    pts = []
    for i in range(n_leg + 1):  # tratto alto, scende verso il tornante
        t = i / n_leg
        x = X0 + (HAIR_X - X0) * t
        pts.append((x, UP_Y, 70.0 - 26.0 * t))
    cy, r = (UP_Y + LOW_Y) / 2, (UP_Y - LOW_Y) / 2
    for i in range(1, n_turn):
        a = math.pi / 2 - math.pi * i / n_turn
        pts.append((HAIR_X + r * math.cos(a) * 1.1, cy + r * math.sin(a), 44.0 - 14.0 * i / n_turn))
    for i in range(n_leg + 1):  # tratto basso
        t = i / n_leg
        x = HAIR_X + (X0 - HAIR_X) * t
        pts.append((x, LOW_Y, 30.0 - 26.0 * t))
    return np.array(pts)


PATH = path_points()


def nearest_path(x, y):
    d = np.hypot(PATH[:, 0] - x, PATH[:, 1] - y)
    i = int(np.argmin(d))
    return d[i], PATH[i, 2]


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def terrain_h(x, y):
    base = 0.62 * y + 3.0 * math.sin(x * 0.02) + 2.0 * math.cos(y * 0.035 + x * 0.01) + 12
    d, pz = nearest_path(x, y)
    w = smoothstep(HALF_W + 2.0, HALF_W + 16.0, d)
    return pz * (1 - w) + base * w - 0.05


def build_terrain():
    bm = bmesh.new()
    nx, ny = 240, 220
    xs = np.linspace(-330, 260, nx)
    ys = np.linspace(-120, 420, ny)
    verts = [[bm.verts.new((x, y, terrain_h(x, y))) for x in xs] for y in ys]
    for j in range(ny - 1):
        for i in range(nx - 1):
            bm.faces.new((verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]))
    me = bpy.data.meshes.new("Terrain")
    bm.to_mesh(me)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("Terrain", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat("Grass", (98, 182, 66), 0.85, rgb2=(122, 200, 76), scale=0.035))
    return ob


def build_path():
    bm = bmesh.new()
    left, right = [], []
    for i in range(len(PATH)):
        p = PATH[i]
        q = PATH[min(i + 1, len(PATH) - 1)] if i < len(PATH) - 1 else PATH[i]
        pr = PATH[max(i - 1, 0)]
        t = np.array(q[:2]) - np.array(pr[:2])
        t /= np.linalg.norm(t) + 1e-9
        n = np.array([-t[1], t[0]])
        left.append(bm.verts.new((p[0] + n[0] * HALF_W, p[1] + n[1] * HALF_W, p[2] + 0.12)))
        right.append(bm.verts.new((p[0] - n[0] * HALF_W, p[1] - n[1] * HALF_W, p[2] + 0.12)))
    for i in range(len(PATH) - 1):
        bm.faces.new((left[i], left[i + 1], right[i + 1], right[i]))
    me = bpy.data.meshes.new("Path")
    bm.to_mesh(me)
    ob = bpy.data.objects.new("Path", me)
    bpy.context.scene.collection.objects.link(ob)
    mod = ob.modifiers.new("solid", "SOLIDIFY")
    mod.thickness = 0.4
    ob.data.materials.append(mat("PathSand", (232, 196, 134), 0.9, rgb2=(222, 182, 120), scale=0.06))
    return ob


# ------------------------------------------------------------------ props
_lib_cache = {}


def load_prop(kind, name):
    key = (kind, name)
    if key in _lib_cache:
        return _lib_cache[key]
    path = OUT / kind / name / f"{name}.blend"
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.objects = [n for n in src.objects]
    coll = bpy.data.collections.new(f"P_{name}")
    for o in dst.objects:
        if o is not None and o.type == "MESH":
            coll.objects.link(o)
    _lib_cache[key] = coll
    return coll


def place(kind, name, loc, rot=0.0, scale=1.0):
    coll = load_prop(kind, name)
    e = bpy.data.objects.new(f"I_{name}", None)
    e.instance_type = "COLLECTION"
    e.instance_collection = coll
    e.location = loc
    e.rotation_euler = (0, 0, rot)
    e.scale = (scale, scale, scale)
    bpy.context.scene.collection.objects.link(e)
    return e


def on_ground(x, y):
    return (x, y, terrain_h(x, y))


def off_path(x, y, margin=2.0):
    d, _ = nearest_path(x, y)
    return d > HALF_W + margin


def scatter():
    # bordo del sentiero: sassi su entrambi i lati
    for i in range(0, len(PATH), 2):
        p = PATH[i]
        q = PATH[min(i + 1, len(PATH) - 1)]
        t = np.array(q[:2]) - np.array(p[:2])
        if np.linalg.norm(t) < 1e-6:
            continue
        t /= np.linalg.norm(t)
        n = np.array([-t[1], t[0]])
        for side in (1, -1):
            x, y = p[0] + n[0] * side * (HALF_W + 1.0), p[1] + n[1] * side * (HALF_W + 1.0)
            if rng.random() < 0.7:
                place("prop", f"Rock{rng.integers(1, 4)}", (x, y, p[2] - 0.3), rng.uniform(0, 6.28), rng.uniform(0.6, 1.1))
    # scarpata rocciosa fra i due tratti (lato a monte del tratto basso)
    for x in np.arange(-250, 80, 7.5):
        y = LOW_Y + HALF_W + 9 + rng.uniform(-2, 3)
        place("prop", f"Rock{rng.integers(1, 4)}", on_ground(x, y), rng.uniform(0, 6.28), rng.uniform(2.2, 3.4))
    for _ in range(140):
        x, y = rng.uniform(-320, 250), rng.uniform(-110, 400)
        if off_path(x, y, 10):
            place("prop", "PineTree", on_ground(x, y), rng.uniform(0, 6.28), rng.uniform(1.4, 2.2))
    for _ in range(70):
        x, y = rng.uniform(-200, 120), rng.uniform(-60, 160)
        if off_path(x, y, 6):
            place("prop", "Bush1", on_ground(x, y), rng.uniform(0, 6.28), rng.uniform(1.0, 1.6))
    for _ in range(320):
        x, y = rng.uniform(-150, 90), rng.uniform(-60, 140)
        if off_path(x, y, 2.5):
            place("prop", f"Flowers{rng.integers(1, 3)}", on_ground(x, y), rng.uniform(0, 6.28), rng.uniform(1.3, 2.0))
    for _ in range(500):
        x, y = rng.uniform(-150, 90), rng.uniform(-60, 140)
        if off_path(x, y, 1.5):
            place("prop", "Grass1", on_ground(x, y), rng.uniform(0, 6.28), rng.uniform(2.0, 3.2))
    for _ in range(40):
        x, y = rng.uniform(-300, 240), rng.uniform(-100, 380)
        if off_path(x, y, 8):
            place("prop", f"Rock{rng.integers(1, 4)}", on_ground(x, y), rng.uniform(0, 6.28), rng.uniform(1.5, 4.0))


def avatar(loc, rot):
    """Avatar stile Roblox classico che porta un uovo sopra la testa (per dare la scala)."""
    yellow = mat("Skin", (245, 205, 48), 0.5)
    blue = mat("Shirt", (13, 105, 172), 0.6)
    green = mat("Pants", (40, 127, 71), 0.6)
    parts = []
    def bx(loc_, size, m, rx=0.0):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc_)
        o = bpy.context.object
        o.scale = size
        o.rotation_euler = (math.radians(rx), 0, 0)
        b = o.modifiers.new("bevel", "BEVEL")
        b.width = 0.08
        b.segments = 3
        o.data.materials.append(m)
        parts.append(o)
        return o
    bx((0, 0, 3.0), (2.0, 1.0, 2.0), blue)
    bx((-0.5, 0, 1.0), (0.95, 1.0, 2.0), green)
    bx((0.5, 0, 1.0), (0.95, 1.0, 2.0), green)
    bx((-1.5, 0, 4.6), (0.95, 1.0, 2.0), yellow)
    bx((1.5, 0, 4.6), (0.95, 1.0, 2.0), yellow)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.62, depth=1.2, location=(0, 0, 4.6))
    head = bpy.context.object
    b = head.modifiers.new("bevel", "BEVEL")
    b.width = 0.25
    b.segments = 4
    head.data.materials.append(yellow)
    parts.append(head)
    root = bpy.data.objects.new("Avatar", None)
    bpy.context.scene.collection.objects.link(root)
    for o in parts:
        o.parent = root
    root.location = loc
    root.rotation_euler = (0, 0, rot)
    return root


def fence():
    wood = mat("FenceWood", (176, 118, 66), 0.7)
    posts, rails = [], []
    step = 3
    prev = None
    for i in range(0, len(PATH), step):
        p = PATH[i]
        q = PATH[min(i + 1, len(PATH) - 1)]
        t = np.array(q[:2]) - np.array(p[:2])
        if np.linalg.norm(t) < 1e-6:
            continue
        t /= np.linalg.norm(t)
        n = np.array([-t[1], t[0]])
        # lato a valle: per il tratto basso e' -Y (verso la camera), per quello alto e' verso il tratto basso
        if p[0] > HAIR_X - 2:
            prev = None
            continue  # niente staccionata nel tornante
        side = 1 if p[1] < (UP_Y + LOW_Y) / 2 else -1
        x, y = p[0] + n[0] * side * (HALF_W - 0.8), p[1] + n[1] * side * (HALF_W - 0.8)
        z = p[2] + 0.1
        bpy.ops.mesh.primitive_cylinder_add(radius=0.38, depth=3.6, location=(x, y, z + 1.8))
        o = bpy.context.object
        o.data.materials.append(wood)
        if prev is not None and np.hypot(prev[0] - x, prev[1] - y) < 25:
            for h in (1.4, 2.7):
                a = Vector((prev[0], prev[1], prev[2] + h))
                b = Vector((x, y, z + h))
                mid = (a + b) / 2
                bpy.ops.mesh.primitive_cylinder_add(radius=0.2, depth=(b - a).length, location=mid)
                r = bpy.context.object
                r.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
                r.data.materials.append(wood)
        prev = (x, y, z)


def shelter(x, y):
    """Rifugio anti-valanga: tettoia di legno addossata alla scarpata."""
    z = terrain_h(x, y)
    wood = mat("Wood", (150, 98, 56), 0.7)
    roof = mat("Roof", (214, 74, 52), 0.6)
    def boxo(name, loc, size, m):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        o = bpy.context.object
        o.name = name
        o.scale = size
        b = o.modifiers.new("bevel", "BEVEL")
        b.width = 0.12
        b.segments = 3
        o.data.materials.append(m)
        return o
    for dx in (-5, 5):
        for dy in (-2.5, 2.5):
            boxo("Post", (x + dx, y + dy, z + 3.2), (0.7, 0.7, 6.4), wood)
    r1 = boxo("Roof1", (x, y - 1.6, z + 7.0), (12.5, 4.6, 0.5), roof)
    r1.rotation_euler = (math.radians(-22), 0, 0)
    r2 = boxo("Roof2", (x, y + 2.4, z + 7.2), (12.5, 4.2, 0.5), roof)
    r2.rotation_euler = (math.radians(18), 0, 0)
    sign = boxo("Sign", (x, y - 3.0, z + 5.6), (5.5, 0.3, 1.4), mat("SignBoard", (255, 226, 120), 0.5))


def snowy_peak():
    snow = mat("Snow", (246, 250, 255), 0.5)
    rock = mat("PeakRock", (126, 136, 160), 0.85)
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=330, radius2=10, depth=420, location=(60, 700, 170))
    peak = bpy.context.object
    peak.data.materials.append(rock)
    tex = bpy.data.textures.new("n", "CLOUDS")
    tex.noise_scale = 40
    d = peak.modifiers.new("disp", "DISPLACE")
    d.texture = tex
    d.strength = 18
    sub = peak.modifiers.new("sub", "SUBSURF")
    sub.levels = 3
    peak.modifiers.move(1, 0)
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=130, radius2=9.6, depth=166, location=(60, 700, 297))
    cap = bpy.context.object
    cap.data.materials.append(snow)
    cap.scale = (1.04, 1.04, 1.0)
    sub = cap.modifiers.new("sub", "SUBSURF")
    sub.levels = 3
    far = mat("FarHills", (150, 176, 214), 0.9)
    for i, (x, y, r, h) in enumerate([(-520, 760, 360, 260), (360, 720, 330, 230), (700, 900, 420, 300)]):
        bpy.ops.mesh.primitive_cone_add(vertices=40, radius1=r, radius2=6, depth=h, location=(x, y, h / 2 - 20))
        o = bpy.context.object
        o.data.materials.append(far)
        s = o.modifiers.new("sub", "SUBSURF")
        s.levels = 2


def clouds():
    cm = mat("Cloud", (255, 255, 255), 0.9)
    for (x, y, z, s) in [(-320, 640, 300, 2.4), (240, 700, 340, 2.0), (520, 760, 260, 2.6), (40, 560, 420, 1.6)]:
        for k in range(6):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=s * rng.uniform(9, 15), location=(x + k * s * 11 - 30, y, z + rng.uniform(-4, 6)))
            o = bpy.context.object
            o.scale = (1.4, 1.0, 0.75)
            bpy.ops.object.shade_smooth()
            o.data.materials.append(cm)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_terrain()
    build_path()
    scatter()
    shelter(-92, LOW_Y + HALF_W + 4)
    fence()
    snowy_peak()
    clouds()
    nx, ny = -40.0, LOW_Y + 12.0
    nz = nearest_path(nx, ny)[1] + 0.1
    place("prop", "Nest", (nx, ny, nz), 0.3, 1.35)
    place("egg", "EggCommon", (nx - 1.1, ny + 0.2, nz + 0.5), 0.4, 1.0)
    place("egg", "EggLegendary", (nx + 1.1, ny - 0.1, nz + 0.5), -0.3, 1.05)
    place("egg", "EggCommon", (nx + 0.1, ny + 1.3, nz + 0.45), 1.2, 0.9)
    cz = nearest_path(-47, LOW_Y + 5)[1] + 0.12
    place("pet", "Chick", (-47, LOW_Y + 5, cz), math.radians(-25), 1.0)
    az = nearest_path(-30, LOW_Y - 2)[1] + 0.12
    avatar((-30, LOW_Y - 2, az), math.radians(-70))
    place("egg", "EggLegendary", (-30, LOW_Y - 2, az + 5.7), 0.2, 0.95)
    sx = -10
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=4.5, location=(sx, UP_Y - 4, nearest_path(sx, UP_Y)[1] + 4.6))
    ball = bpy.context.object
    bpy.ops.object.shade_smooth()
    ball.data.materials.append(mat("Snowball", (245, 249, 255), 0.45))

    scene = bpy.context.scene
    setup_world(sky=(0.55, 0.72, 1.0), sun_dir=(-0.4, -0.6, 0.75), sun_strength=3.4, strength=1.0, samples=64)
    scene.render.film_transparent = False
    scene.render.resolution_x, scene.render.resolution_y = RES
    shots = {
        "wide": ((-128, -62, 72), (-30, 58, 52), 24),
        "close": ((-84, -2, 31), (30, 70, 46), 24),
    }
    for name, (loc, tgt, lens) in shots.items():
        cam_data = bpy.data.cameras.new("Cam_" + name)
        cam_data.lens = lens
        cam_data.clip_end = 4000
        cam = bpy.data.objects.new("Cam_" + name, cam_data)
        scene.collection.objects.link(cam)
        cam.location = Vector(loc)
        cam.rotation_euler = (Vector(tgt) - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.camera = cam
        out = OUT / "scene" / f"meadow_{name}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        scene.render.filepath = str(out)
        bpy.ops.render.render(write_still=True)
        print("render", out)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "scene" / "meadow.blend"))


main()
