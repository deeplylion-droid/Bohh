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


def image_quad(name, image_path):
    """Quadrato con un'immagine sulla faccia anteriore (-Z locale Roblox), come una SurfaceGui Front."""
    mesh = bpy.data.meshes.new(name)
    # guardando la faccia anteriore la destra e' -X locale: u=0 a x=+0.5
    verts = [(0.5, -0.5, -0.52), (-0.5, -0.5, -0.52), (-0.5, 0.5, -0.52), (0.5, 0.5, -0.52)]
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new()
    for i, (u, v) in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[i].uv = (u, v)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(image_path))
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    bsdf.inputs["Emission Strength"].default_value = 0.6
    if hasattr(m, "blend_method"):
        m.blend_method = "BLEND"
    mesh.materials.append(m)
    return mesh


def add_parts(world):
    coll = bpy.data.collections.new("World")
    bpy.context.scene.collection.children.link(coll)
    skipped = 0
    for p in world["parts"]:
        if p["n"] == "WheelFace":
            # faccia trasparente della ruota della fortuna: si disegna l'immagine della SurfaceGui
            obj = bpy.data.objects.new("WheelFace", image_quad("WheelFace", ROOT / "art/out/images/WheelFace.png"))
            obj.matrix_world = part_matrix(p)
            coll.objects.link(obj)
            continue
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


# ------------------------------------------------------------------------------- voxel della Tana
def add_den_voxels(path):
    """Terreno vero attorno alla Tana dei Mostri (da tests/cloud/dump_den_voxels.luau): superficie a
    occupazione 0.5 con marching cubes, colorata col materiale del voxel pieno piu' vicino."""
    from skimage import measure

    D = json.load(open(path))
    res = D["res"]
    names = D["materials"]
    slices = D["slices"]
    nx, ny, nz = len(slices), len(slices[0]), len(slices[0][0].split(","))
    occ = np.zeros((nx, ny, nz), dtype=np.float32)
    mat = np.zeros((nx, ny, nz), dtype=np.int16)
    for ix in range(nx):
        for iy in range(ny):
            for iz, cell in enumerate(slices[ix][iy].split(",")):
                o, m = cell.split(".")
                occ[ix, iy, iz] = int(o) / 255
                mat[ix, iy, iz] = int(m) - 1
    padded = np.pad(occ, 1, constant_values=0)
    verts, faces, _, _ = measure.marching_cubes(padded, 0.5)
    verts = verts - 1  # padding
    # centri dei voxel: x0 + (i + 0.5) * res
    world = np.empty_like(verts)
    world[:, 0] = D["x0"] + (verts[:, 0] + 0.5) * res
    world[:, 1] = D["y0"] + (verts[:, 1] + 0.5) * res
    world[:, 2] = D["z0"] + (verts[:, 2] + 0.5) * res
    colors = {
        "Basalt": (60, 54, 62), "CrackedLava": (236, 92, 34), "Rock": (126, 130, 142), "Slate": (96, 94, 114),
        "Asphalt": (74, 66, 72), "Ground": (140, 108, 78), "Snow": (240, 245, 252),
    }
    mesh = bpy.data.meshes.new("DenVoxels")
    mesh.from_pydata([tuple(rb(v)) for v in world], [], faces.tolist())
    col = mesh.color_attributes.new("col", "FLOAT_COLOR", "CORNER")
    full = occ > 0.5
    for poly in mesh.polygons:
        c = np.mean(verts[list(poly.vertices)], axis=0)
        i, j, k = (int(round(v)) for v in c)
        best = None
        for di in (0, -1, 1):
            for dj in (0, -1, 1):
                for dk in (0, -1, 1):
                    a, b, cc = i + di, j + dj, k + dk
                    if 0 <= a < nx and 0 <= b < ny and 0 <= cc < nz and full[a, b, cc]:
                        best = names[mat[a, b, cc]]
                        break
                if best:
                    break
            if best:
                break
        rgb = colors.get(best or "Basalt", (90, 90, 90))
        lin = [srgb_to_linear(rgb[0]), srgb_to_linear(rgb[1]), srgb_to_linear(rgb[2]), 1.0]
        for li in poly.loop_indices:
            col.data[li].color = lin
    obj = bpy.data.objects.new("DenVoxels", mesh)
    bpy.context.scene.collection.objects.link(obj)
    m = bpy.data.materials.new("DenVoxelMat")
    m.use_nodes = True
    nt = m.node_tree
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "col"
    nt.links.new(attr.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    obj.active_material = m
    print(f"voxel della Tana: {len(faces)} triangoli")
    return (D["x0"], D["z0"], D["x0"] + nx * res, D["z0"] + nz * res)


# ------------------------------------------------------------------------------- terreno
def add_terrain(T, skip=None):
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
            if skip:
                x = x0 + (i + 0.5) * step
                z = z0 + (j + 0.5) * step
                if skip[0] + 8 < x < skip[2] - 8 and skip[1] + 8 < z < skip[3] - 8:
                    continue  # li' c'e' il terreno vero della Tana (voxel)
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
    "junction": ((70, 372, 40), (22, 330, 110), 30),
    # uscita dalla vetta: fine del viale e inizio della rampa del sentiero, vista dalla rampa
    "exit": ((26, 334, 196), (0, 329, 150), 30),
    # per la miniatura: la vetta vista da ovest, con i giganti dei lotti 1-5 tutti in vista
    "promo": ((-240, 440, 105), (50, 352, -62), 23),
    "plot": ((40, 352, 50), (88, 331, 104), 26),
    # lotto 1 da vicino: piedistalli, pedane, incubatrici; e il cancello con le sue colonne
    "pads": ((62, 345, 66), (84, 331, 96), 30),
    "gate": ((52, 343, 58), (83, 341, 99), 34),
    "trail": ((190, 340, 250), (20, 262, 320), 28),
    "crater": ((70, 210, 470), (70, 96, 630), 28),
    # Tana dei Mostri: il vulcano a sud del cratere, l'imbocco del tunnel e la grotta (dall'interno)
    "volcano": ((330, 300, 520), (70, 140, 800), 28),
    "denentrance": ((86, 106, 690), (70, 100, 735), 26),
    "denportal": ((70, 98, 708), (70, 104, 732), 24),
    "dencave": ((84, 100, 852), (70, 92, 896), 22),
    "denaltar": ((70, 96, 846), (70, 92, 900), 18),
    "denback": ((70, 114, 898), (70, 90, 842), 18),
    "dentunnel": ((60, 96, 770), (82, 92, 806), 20),
    "dentunnel2": ((81, 95, 803), (70, 89, 838), 20),
    "mountain": ((-260, 420, 1250), (0, 210, 320), 34),
    # piazza: ruota della fortuna, bacheca delle missioni, scale del re della collina (dallo spawn)
    "plaza": ((0, 346, 92), (0, 336, 4), 20),
    "wheel": ((14, 338, 44), (46, 341, 28), 24),
    "board": ((-14, 338, 44), (-46, 338, 28), 24),
    "hill": ((34, 352, 40), (0, 336, 0), 22),
}


def render(view, res=None):
    res = res or (int(os.environ.get("WIDTH", 1280)), int(os.environ.get("HEIGHT", 720)))
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
    # TRANSPARENT=1: sfondo trasparente (per comporre un cielo nelle immagini promozionali)
    scene.render.film_transparent = os.environ.get("TRANSPARENT") == "1"
    # niente luce di contorno (serve solo ai ritratti dei modelli)
    for o in list(scene.objects):
        if o.name.startswith("Rim"):
            bpy.data.objects.remove(o)
    # DEN=1: terreno vero della Tana dai voxel del server (al posto della mappa delle altezze li')
    skip = None
    den_path = ROOT / "art" / "out" / "den_voxels.json"
    if os.environ.get("DEN") == "1" and den_path.exists():
        skip = add_den_voxels(den_path)
    add_terrain(json.load(open(ROOT / "art" / "out" / "terrain.json")), skip)
    add_parts(json.load(open(ROOT / "art" / "out" / "world.json")))
    for v in views:
        render(v)
        print("render", v)


if __name__ == "__main__":
    main()
