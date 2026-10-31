"""Il "bacon hair": il giocatore che compare nelle icone dei giochi piu' giocati di Roblox, fatto con
gli oggetti veri di Roblox, identico all'originale (niente personaggio rifatto a mano). Portato da
Recolor (deeplylion-droid/Roblox-Max, branch recolor/mondo-2: recolor/tools/store/bacon.py e
recolor/docs/bacon-hair.md) sulla nostra art/lib.

- Pal Hair (63690008): la sua mesh 83293901 e la texture 6858317867, Scale (1, 1.05, 1).
- Blue and Black Motorcycle Shirt (144076358): immagine 144076357; Dark Green Jeans (144076760):
  immagine 144076759; avvolte sui blocchi R6 come fa Roblox (modello 585 x 559). Pelle (248, 248, 250).
- Faccia disegnata ed espressiva (bacon_faces.py), non la faccia di serie.

  .tools/venv/bin/python art/promo/bacon.py fetch     scarica gli oggetti in art/cache/bacon (la chiave la
                                                      aggiunge il proxy dell'ambiente, come in tools/rbxcloud.py;
                                                      i file scaricati NON vanno nel repository)
  .tools/venv/bin/python art/promo/bacon_faces.py     disegna le facce in art/cache/bacon/faces

In Blender: bacon(pose, face) da' il personaggio con i piedi all'origine, rivolto verso -Y (la sua destra
e' -X), con le giunture ArmR, ArmL, LegR, LegL, Head, Lean (gradi; un'oscillazione in avanti e'
negativa; anche ArmR_y/ArmR_z, HeadTilt, Turn).
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE.parent
DIR = ART / "cache" / "bacon"
FACES = DIR / "faces"
HAIR_MESH, HAIR_TEXTURE, SHIRT, PANTS = 83293901, 6858317867, 144076357, 144076759
SKIN = (248, 248, 250)
W, H = 585.0, 559.0  # il modello dei vestiti classici

# The template's rectangles (x, y, width, height), for the torso and for a right and a left limb.
TORSO = {"F": (231, 74, 128, 128), "B": (427, 74, 128, 128), "R": (165, 74, 64, 128), "L": (361, 74, 64, 128),
         "U": (231, 8, 128, 64), "D": (231, 204, 128, 64)}
LIMB_RIGHT = {"F": (217, 355, 64, 128), "R": (151, 355, 64, 128), "B": (85, 355, 64, 128), "L": (19, 355, 64, 128),
              "U": (217, 289, 64, 64), "D": (217, 485, 64, 64)}
LIMB_LEFT = {"F": (308, 355, 64, 128), "L": (374, 355, 64, 128), "B": (440, 355, 64, 128), "R": (506, 355, 64, 128),
             "U": (308, 289, 64, 64), "D": (308, 485, 64, 64)}


def fetch() -> None:
    """Scarica mesh e texture dei capelli, maglia e pantaloni con l'asset delivery di Open Cloud."""
    import gzip

    sys.path.insert(0, str(ART.parent / "tools"))
    import rbxcloud  # noqa: PLC0415

    DIR.mkdir(parents=True, exist_ok=True)
    for asset, name in ((HAIR_MESH, "hair.mesh"), (HAIR_TEXTURE, "hair.png"), (SHIRT, "shirt.png"), (PANTS, "pants.png")):
        meta = rbxcloud._session.get(f"{rbxcloud.BASE}/asset-delivery-api/v1/assetId/{asset}", timeout=60)
        meta.raise_for_status()
        data = rbxcloud._session.get(meta.json()["location"], timeout=120).content
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        (DIR / name).write_bytes(data)
        print(f"{name}: {len(data)} byte")


# ------------------------------------------------------------------------------------ Blender

def _bpy():
    import bpy
    return bpy


def lin(rgb):
    sys.path.insert(0, str(ART))
    from lib.toy import srgb_to_linear  # noqa: PLC0415

    return [srgb_to_linear(c) for c in rgb]  # rgb in 0..255


def material(name: str, rgb, rough: float = 0.32, coat: float = 0.0):
    bpy = _bpy()
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*lin(rgb), 1.0)
    b.inputs["Roughness"].default_value = rough
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.06
    return m


def solid(name: str, sdf, mat, voxel: float = 0.05, tris: int = 2500):
    sys.path.insert(0, str(ART))
    from lib.mesher import mesh_sdf  # noqa: PLC0415
    from lib.toy import decimate, make_object  # noqa: PLC0415

    verts, faces, _ = mesh_sdf(sdf, voxel)
    obj = make_object(name, verts, faces)
    decimate(obj, tris)
    obj.data.materials.append(mat)
    return obj


def link(obj, parent=None, location=(0, 0, 0), rotation=(0, 0, 0), scale=1.0):
    from mathutils import Euler  # noqa: PLC0415

    obj.parent = parent
    obj.location = location
    obj.rotation_euler = Euler([math.radians(a) for a in rotation])
    obj.scale = (scale, scale, scale)
    return obj


def empty(name: str):
    bpy = _bpy()
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def face_on(head, image: Path, base):
    """La faccia disegnata sul davanti della testa: le facce anteriori prendono un secondo materiale,
    l'immagine della faccia sopra la pelle, proiettata dritta dal davanti."""
    bpy = _bpy()
    me = head.data
    skin = me.materials[0]
    m = bpy.data.materials.new("Face")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.3
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(image))
    tex.extension = "CLIP"
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    a_in = [s for s in mix.inputs if s.name == "A" and s.type == "RGBA"][0]
    b_in = [s for s in mix.inputs if s.name == "B" and s.type == "RGBA"][0]
    out = [s for s in mix.outputs if s.type == "RGBA"][0]
    a_in.default_value = (*lin(base), 1.0)
    nt.links.new(tex.outputs["Alpha"], mix.inputs["Factor"])
    nt.links.new(tex.outputs["Color"], b_in)
    nt.links.new(out, b.inputs["Base Color"])
    me.materials.append(m)
    uv = me.uv_layers.new(name="UVMap")
    span = 1.36
    for poly in me.polygons:
        poly.material_index = 1 if poly.normal.y < -0.15 else 0
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (0.5 - v.x / span, 0.5 + (v.z - 0.02) / span)
    return skin

def read_mesh_v1(path: Path):
    """A Roblox mesh of version 1.00: per face three vertices of [position][normal][uv], its
    positions twice the size (Roblox halves them), its V upside down."""
    text = path.read_text(encoding="ascii", errors="ignore")
    assert text.startswith("version 1.0"), "only version 1.00 meshes"
    groups = re.findall(r"\[([^\]]*)\]", text)
    verts, uvs = [], []
    for i in range(0, len(groups) - 2, 3):
        x, y, z = (float(v) for v in groups[i].split(","))
        u, v = (float(t) for t in groups[i + 2].split(",")[:2])
        verts.append((x * 0.5, y * 0.5, z * 0.5))
        uvs.append((u, 1.0 - v))
    return verts, uvs


def roblox_to_blender(p):
    """Roblox's space (Y up, -Z ahead) to the player's here (Z up, -Y ahead), not mirrored."""
    return (-p[0], p[2], p[1])


def image_material(name: str, layers, rough: float = 0.42):
    """A material of the skin under `layers` of pictures (paths), each drawn over the one
    before by its alpha, through the object's UVs."""
    bpy = _bpy()
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = 0.15
    rgb = nt.nodes.new("ShaderNodeRGB")
    rgb.outputs[0].default_value = (*lin(SKIN), 1.0)
    colour = rgb.outputs[0]
    for path in layers:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(path), check_existing=True)
        tex.interpolation = "Cubic"
        tex.extension = "CLIP"
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        nt.links.new(tex.outputs["Alpha"], mix.inputs["Factor"])
        nt.links.new(colour, [s for s in mix.inputs if s.name == "A" and s.type == "RGBA"][0])
        nt.links.new(tex.outputs["Color"], [s for s in mix.inputs if s.name == "B" and s.type == "RGBA"][0])
        colour = [s for s in mix.outputs if s.type == "RGBA"][0]
    nt.links.new(colour, b.inputs["Base Color"])
    return m


def block(name: str, size, centre, regions, material, bevel: float = 0.09):
    """A box of `size` (x across, y deep, z up) round `centre`, each face wrapped with its
    rectangle of the template as Roblox wraps a body part: the front (-Y) as F, the right (-X)
    as R, and so on, the top and the bottom laid against the front's edges."""
    bpy = _bpy()
    import bmesh

    w, d, h = size
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    hx, hy, hz = w / 2, d / 2, h / 2

    def rect(key, u, v):
        x0, y0, rw, rh = regions[key]
        return ((x0 + u * rw) / W, 1.0 - (y0 + (1.0 - v) * rh) / H)

    # Each face: four corners (x, y, z) in order round the face as seen from outside, from its
    # bottom left, and the template's (u, v) at each, (0, 0) its bottom left.
    faces = {
        "F": [((-hx, -hy, -hz), (0, 0)), ((hx, -hy, -hz), (1, 0)), ((hx, -hy, hz), (1, 1)), ((-hx, -hy, hz), (0, 1))],
        "B": [((hx, hy, -hz), (0, 0)), ((-hx, hy, -hz), (1, 0)), ((-hx, hy, hz), (1, 1)), ((hx, hy, hz), (0, 1))],
        "R": [((-hx, hy, -hz), (0, 0)), ((-hx, -hy, -hz), (1, 0)), ((-hx, -hy, hz), (1, 1)), ((-hx, hy, hz), (0, 1))],
        "L": [((hx, -hy, -hz), (0, 0)), ((hx, hy, -hz), (1, 0)), ((hx, hy, hz), (1, 1)), ((hx, -hy, hz), (0, 1))],
        "U": [((-hx, -hy, hz), (0, 0)), ((hx, -hy, hz), (1, 0)), ((hx, hy, hz), (1, 1)), ((-hx, hy, hz), (0, 1))],
        "D": [((-hx, hy, -hz), (0, 0)), ((hx, hy, -hz), (1, 0)), ((hx, -hy, -hz), (1, 1)), ((-hx, -hy, -hz), (0, 1))],
    }
    cache = {}
    for key, corners in faces.items():
        vs = []
        for co, _ in corners:
            if co not in cache:
                cache[co] = bm.verts.new(co)
            vs.append(cache[co])
        face = bm.faces.new(vs)
        for loop, (_, (u, v)) in zip(face.loops, corners):
            loop[uv].uv = rect(key, u, v)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = centre
    me.materials.append(material)
    mod = obj.modifiers.new("Round", "BEVEL")
    mod.width = bevel
    mod.segments = 4
    mod.limit_method = "NONE"
    mod.harden_normals = False
    for poly in me.polygons:
        poly.use_smooth = True
    return obj


def pal_hair(material):
    bpy = _bpy()
    verts, uvs = read_mesh_v1(DIR / "hair.mesh")
    scale = (1.0, 1.05, 1.0)  # its SpecialMesh's Scale
    me = bpy.data.meshes.new("PalHair")
    points = [roblox_to_blender((v[0] * scale[0], v[1] * scale[1], v[2] * scale[2])) for v in verts]
    faces = [(i, i + 2, i + 1) for i in range(0, len(points) - 2, 3)]  # the mirror turns them round
    me.from_pydata(points, [], faces)
    layer = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            layer.data[li].uv = uvs[me.loops[li].vertex_index]
    me.materials.append(material)
    for poly in me.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new("PalHair", me)
    bpy.context.scene.collection.objects.link(obj)
    weld = obj.modifiers.new("Weld", "WELD")
    weld.merge_threshold = 0.0005
    return obj


def bacon(pose: dict, face: str = "excited", noob_sides: bool = False):
    """The bacon hair, posed: feet at the origin, facing -Y, joints as scenes.noob's. With
    `noob_sides` its limbs are named as the noob's (ArmR on +X), so a scene posed for the noob
    poses it the same; the clothes stay on the right sides."""
    sys.path.insert(0, str(ART))
    from lib.sdf import cylinder  # noqa: PLC0415

    shirt, pants = DIR / "shirt.png", DIR / "pants.png"
    root = empty("Bacon")
    torso_mat = image_material("BaconTorso", [pants, shirt])
    arm_mat = image_material("BaconArms", [shirt])
    leg_mat = image_material("BaconLegs", [pants])
    body = empty("BaconBody")
    link(body, root, (0, 0, 2.0), (pose.get("Lean", 0), 0, pose.get("Turn", 0)))
    link(block("Torso", (2, 1, 2), (0, 0, 0), TORSO, torso_mat), body, (0, 0, 1.0))
    skin = material("BaconSkin", SKIN, rough=0.32, coat=0.2)
    head = solid("Head", cylinder((0, 0, -0.56), (0, 0, 0.56), 0.64, round=0.3), skin, voxel=0.03, tris=5000)
    face_on(head, FACES / f"{face}.png", SKIN)
    link(head, body, (0, 0, 2.62), (pose.get("HeadTilt", 0), 0, pose.get("Head", 0)))
    hair_mat = image_material("PalHair", [DIR / "hair.png"], rough=0.5)
    # Pal Hair hangs from the head's HairAttachment (0, 0.6, 0) by its own (0, 0.35, 0.25).
    link(pal_hair(hair_mat), head, roblox_to_blender((0.0, 0.25, -0.2497)))
    limbs = ((1, "R", LIMB_LEFT), (-1, "L", LIMB_RIGHT)) if noob_sides else ((-1, "R", LIMB_RIGHT), (1, "L", LIMB_LEFT))
    for side, name, limb in limbs:
        arm = empty(f"Arm{name}")
        link(arm, body, (side * 1.5, 0, 1.5), (pose.get(f"Arm{name}", 0), pose.get(f"Arm{name}_y", 0), pose.get(f"Arm{name}_z", 0)))
        link(block(f"ArmBlock{name}", (1, 1, 2), (0, 0, 0), limb, arm_mat), arm, (0, 0, -0.5))
        leg = empty(f"Leg{name}")
        link(leg, body, (side * 0.5, 0, 0.0), (pose.get(f"Leg{name}", 0), 0, 0))
        link(block(f"LegBlock{name}", (1, 1, 2), (0, 0, 0), limb, leg_mat), leg, (0, 0, -1.0))
    return root


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        fetch()
    else:
        print(__doc__)
