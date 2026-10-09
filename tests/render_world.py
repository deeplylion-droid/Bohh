"""Render di controllo del mondo: terreno (art/out/terrain.json, da tests/dump_terrain.luau) +
parti esportate da un server vero (art/out/world.json, da tests/cloud/dump_world.luau).
Le MeshPart dei nostri modelli usano le mesh dei file .blend in art/out.

Uso: .tools/venv/bin/python tests/render_world.py [vista ...]   (viste: summit plot trail crater mountain)
"""
import json
import math
import os
import sys
from pathlib import Path

import bpy  # noqa: I001
import bmesh
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art"))
from lib.render import setup_world  # noqa: E402
from lib.toy import srgb_to_linear  # noqa: E402

OUT = ROOT / "art" / "out" / "world"
M = np.array([[-1, 0, 0], [0, 0, 1], [0, 1, 0]], dtype=float)  # Roblox -> Blender
MINV = M.T


def rb(v):
    return M @ np.asarray(v, dtype=float)


# ------------------------------------------------------------------------------- materiali
_mats = {}
ROUGH = {"SmoothPlastic": 0.45, "Plastic": 0.55, "Neon": 0.5, "Glass": 0.05, "Ice": 0.1, "Metal": 0.3, "Foil": 0.2,
         "Wood": 0.7, "WoodPlanks": 0.7, "Slate": 0.85, "Concrete": 0.9, "Brick": 0.85, "Cobblestone": 0.85,
         "Fabric": 0.95, "Grass": 0.9, "Sand": 0.9, "Marble": 0.3, "Granite": 0.7, "ForceField": 0.3, "Snow": 0.6}


def material(color, mat_name, transparency):
    key = (tuple(color), mat_name, round(transparency, 2))
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(f"{mat_name}_{len(_mats)}")
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    col = [srgb_to_linear(c) for c in color] + [1.0]
    bsdf.inputs["Base Color"].default_value = col
    bsdf.inputs["Roughness"].default_value = ROUGH.get(mat_name, 0.6)
    if mat_name in ("Metal", "Foil", "DiamondPlate"):
        bsdf.inputs["Metallic"].default_value = 1.0
    if mat_name == "Neon":
        bsdf.inputs["Emission Color"].default_value = col
        bsdf.inputs["Emission Strength"].default_value = 2.0
    if transparency > 0 or mat_name in ("Glass", "ForceField"):
        bsdf.inputs["Alpha"].default_value = max(0.05, 1 - transparency)
        m.blend_method = "BLEND" if hasattr(m, "blend_method") else m.blend_method
    _mats[key] = m
    return m


# ------------------------------------------------------------------------------- primitive
def unit_mesh(kind, sm=None):
    """Mesh unitaria (lati 1, centrata) nelle coordinate locali Roblox (x, y, z)."""
    name = f"unit_{kind}_{sm}"
    if name in bpy.data.meshes:
        return bpy.data.meshes[name]
    bm = bmesh.new()
    if kind == "Ball" or sm == "Sphere":
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=0.5)
    elif kind == "Cylinder":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.5, radius2=0.5, depth=1.0)
        # asse del cilindro Roblox = X locale
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "Y"))
    elif kind == "Wedge":
        v = [bm.verts.new(p) for p in [(-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, 0.5), (-0.5, -0.5, 0.5),
                                         (-0.5, 0.5, 0.5), (0.5, 0.5, 0.5)]]
        for f in [(0, 1, 2, 3), (3, 2, 5, 4), (0, 4, 5, 1), (0, 3, 4), (1, 5, 2)]:
            bm.faces.new([v[i] for i in f])
    else:
        bmesh.ops.create_cube(bm, size=1.0)
    # coordinate locali Roblox -> Blender (la matrice dell'oggetto lavora in coordinate Roblox)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = kind in ("Ball", "Cylinder") or sm == "Sphere"
    return mesh


def part_matrix(p, scale_local=None, center_b=None):
    pos = np.array(p["p"], dtype=float)
    right = np.array(p["r"][0:3], dtype=float)
    up = np.array(p["r"][3:6], dtype=float)
    back = np.cross(right, up)
    rot = np.stack([right, up, back], axis=1)
    s = np.array(scale_local if scale_local is not None else p["s"], dtype=float)
    if center_b is None:
        a = M @ rot @ np.diag(s)
        t = rb(pos)
    else:
        a = M @ rot @ np.diag(s) @ MINV
        t = rb(pos) - a @ center_b
    mat = Matrix.Identity(4)
    for i in range(3):
        for j in range(3):
            mat[i][j] = a[i, j]
        mat[i][3] = t[i]
    return mat


# ------------------------------------------------------------------------------- mesh dei modelli
_model_meshes = {}


def model_meshes(model):
    if model in _model_meshes:
        return _model_meshes[model]
    found = {}
    for kind in ("pet", "egg", "prop", "bat", "fx"):
        blend = ROOT / "art" / "out" / kind / model / f"{model}.blend"
        if blend.exists():
            with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
                dst.meshes = list(src.meshes)
            for mesh in dst.meshes:
                if mesh is None:
                    continue
                co = np.array([v.co[:] for v in mesh.vertices])
                lo, hi = co.min(0), co.max(0)
                found[mesh.name.split(".")[0]] = (mesh, (lo + hi) / 2, hi - lo)
            break
    _model_meshes[model] = found
    return found


def add_parts(world):
    coll = bpy.data.collections.new("World")
    bpy.context.scene.collection.children.link(coll)
    skipped = 0
    for p in world["parts"]:
        mat = material(p["k"], p["m"], p.get("t", 0))
        obj = None
        if p["c"] == "MeshPart":
            meshes = model_meshes(p["mo"]) if p.get("mo") else {}
            entry = meshes.get(p["n"])
            if entry:
                mesh, center_b, dims_b = entry
                native_rb = np.array([dims_b[0], dims_b[2], dims_b[1]])
                scale = np.array(p["s"]) / np.maximum(native_rb, 1e-6)
                obj = bpy.data.objects.new(p["n"], mesh)
                obj.matrix_world = part_matrix(p, scale_local=scale, center_b=center_b)
            else:
                skipped += 1
                obj = bpy.data.objects.new(p["n"], unit_mesh("Block"))
                obj.matrix_world = part_matrix(p)
        else:
            obj = bpy.data.objects.new(p["n"], unit_mesh(p.get("sh", "Block"), p.get("sm")))
            obj.matrix_world = part_matrix(p)
        # le mesh sono condivise fra molti oggetti: il materiale va assegnato all'oggetto
        if not obj.data.materials:
            obj.data.materials.append(mat)
        coll.objects.link(obj)
        obj.material_slots[0].link = "OBJECT"
        obj.material_slots[0].material = mat
    print(f"parti: {len(world['parts'])}, mesh mancanti: {skipped}")


# ------------------------------------------------------------------------------- terreno
def add_terrain(T):
    x0, z0, step = T["x0"], T["z0"], T["step"]
    rows, mats, colors = T["rows"], T["mats"], T["colors"]
    nz, nx = len(rows), len(rows[0])
    bm = bmesh.new()
    verts = []
    for j in range(nz):
        for i in range(nx):
            x = x0 + i * step
            z = z0 + j * step
            verts.append(bm.verts.new(tuple(rb((x, max(rows[j][i], 40.0), z)))))
    bm.verts.ensure_lookup_table()
    col_layer = bm.loops.layers.color.new("col")
    for j in range(nz - 1):
        for i in range(nx - 1):
            a = j * nx + i
            f = bm.faces.new((verts[a], verts[a + 1], verts[a + nx + 1], verts[a + nx]))
            c = colors.get(mats[j][i], [0.5, 0.5, 0.5])
            lin = [srgb_to_linear(c[0] * 255), srgb_to_linear(c[1] * 255), srgb_to_linear(c[2] * 255), 1.0]
            for loop in f.loops:
                loop[col_layer] = lin
    mesh = bpy.data.meshes.new("Terrain")
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new("Terrain", mesh)
    bpy.context.scene.collection.objects.link(obj)
    m = bpy.data.materials.new("TerrainMat")
    m.use_nodes = True
    nt = m.node_tree
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "col"
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.9
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    obj.active_material = m


VIEWS = {
    # nome: (posizione camera Roblox, punto guardato Roblox, lunghezza focale)
    "summit": ((0, 430, 360), (0, 320, 20), 30),
    # trono del lotto 5 (Pentadrago) visto dalla piazza
    "throne": ((-14, 350, -38), (-58, 360, -160), 24),
    # i giganti dei lotti 1-5 visti dall'alto, dalla parte del sentiero
    "giants": ((60, 470, 330), (-20, 340, -30), 26),
    "plot": ((40, 352, 50), (88, 331, 104), 26),
    "trail": ((190, 340, 250), (20, 262, 320), 28),
    "crater": ((70, 210, 470), (70, 96, 630), 28),
    "mountain": ((-260, 420, 1250), (0, 210, 320), 34),
}


def render(view, res=(1280, 720)):
    cam_pos, target, lens = VIEWS[view]
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = lens
    cam_data.clip_end = 5000
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    loc = Vector(rb(cam_pos))
    tgt = Vector(rb(target))
    cam.location = loc
    cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = res
    OUT.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(OUT / f"{view}.png")
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)


def main():
    views = sys.argv[1:] or list(VIEWS)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_world(samples=int(os.environ.get("SAMPLES", 24)))
    scene = bpy.context.scene
    scene.render.film_transparent = False
    # niente luce di contorno (serve solo ai ritratti dei modelli)
    for o in list(scene.objects):
        if o.name.startswith("Rim"):
            bpy.data.objects.remove(o)
    add_terrain(json.load(open(ROOT / "art" / "out" / "terrain.json")))
    add_parts(json.load(open(ROOT / "art" / "out" / "world.json")))
    for v in views:
        render(v)
        print("render", v)


if __name__ == "__main__":
    main()
