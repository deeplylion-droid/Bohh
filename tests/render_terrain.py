"""Render 3D di controllo della montagna (heightfield da terrain.json + sentiero da layout.json)."""
import json, math, sys
import bpy  # noqa: I001
import bmesh
import numpy as np
from mathutils import Vector

sys.path.insert(0, "art")
from lib.render import setup_world  # noqa: E402

T = json.load(open("art/out/terrain.json"))
L = json.load(open("art/out/layout.json"))
x0, z0, step = T["x0"], T["z0"], T["step"]
rows = T["rows"]
mats = T["mats"]
colors = T["colors"]
nz = len(rows)
nx = len(rows[0])

def zone_color(y, kind, slope):
    if kind == "path":
        return (0.77, 0.6, 0.41)
    if kind in ("crater",):
        return (0.26, 0.23, 0.28)
    if kind in ("rim", "volcano"):
        return (0.26, 0.23, 0.28) if slope > 1.2 else (1.0, 0.41, 0.14)
    steep = slope > 1.1
    if y > 322:
        return (0.57, 0.6, 0.67) if steep else (0.95, 0.97, 1.0)
    if y > 288:
        return (0.57, 0.6, 0.67) if steep else (0.44, 0.78, 0.29)
    if y > 241:
        return (0.45, 0.44, 0.57) if steep else (0.27, 0.63, 0.3)
    if y > 193:
        return (0.89, 0.52, 0.31) if steep else (0.77, 0.6, 0.41)
    if y > 145:
        return (0.45, 0.44, 0.57) if steep else (0.66, 0.59, 0.84)
    return (0.26, 0.23, 0.28)

H = np.array(rows, dtype=float)

bpy.ops.wm.read_factory_settings(use_empty=True)
bm = bmesh.new()
verts = []
for j in range(nz):
    for i in range(nx):
        # Roblox (x, y, z) -> Blender (-x, z, y)
        x = x0 + i * step; z = z0 + j * step
        verts.append(bm.verts.new((-x, z, max(H[j, i], 40))))
bm.verts.ensure_lookup_table()
col = bm.loops.layers.color.new("col")
for j in range(nz - 1):
    for i in range(nx - 1):
        a = j * nx + i
        f = bm.faces.new((verts[a], verts[a + 1], verts[a + nx + 1], verts[a + nx]))
        c = colors.get(mats[j][i], [1, 0, 1])
        for loop in f.loops:
            loop[col] = (*[pow(v, 2.2) for v in c], 1.0)
me = bpy.data.meshes.new("terrain"); bm.to_mesh(me)
ob = bpy.data.objects.new("terrain", me); bpy.context.scene.collection.objects.link(ob)
mat = bpy.data.materials.new("tm"); mat.use_nodes = True
nt = mat.node_tree; attr = nt.nodes.new("ShaderNodeVertexColor"); attr.layer_name = "col"
nt.links.new(attr.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
me.materials.append(mat)
# sentiero
pm = bpy.data.materials.new("path"); pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.9, 0.72, 0.45, 1)
pts = L["path"]
bm2 = bmesh.new(); prevL = prevR = None
for k in range(len(pts)):
    x, y, z, _ = pts[k]
    nxp = pts[min(k + 1, len(pts) - 1)]; pvp = pts[max(k - 1, 0)]
    dx, dz = nxp[0] - pvp[0], nxp[2] - pvp[2]; n = math.hypot(dx, dz) or 1
    rx, rz = -dz / n * 22, dx / n * 22
    l = bm2.verts.new((-(x + rx), z + rz, y + 0.2)); r = bm2.verts.new((-(x - rx), z - rz, y + 0.2))
    if prevL:
        bm2.faces.new((prevL, l, r, prevR))
    prevL, prevR = l, r
me2 = bpy.data.meshes.new("path"); bm2.to_mesh(me2)
ob2 = bpy.data.objects.new("path", me2); bpy.context.scene.collection.objects.link(ob2); me2.materials.append(pm)
# lotti in vetta (scatole gialle)
ym = bpy.data.materials.new("plot"); ym.use_nodes = True
ym.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0.75, 0.2, 1)
for i in range(1, 9):
    x, z, lx, lz = L[f"plot{i}"]
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-x, z, 333))
    o = bpy.context.object; o.scale = (60, 66, 6)
    o.rotation_euler = (0, 0, math.atan2(-(-lx), lz))
    o.data.materials.append(ym)
# mare di nuvole (piano bianco a y=70)
bpy.ops.mesh.primitive_plane_add(size=3000, location=(0, 300, 70))
cl = bpy.context.object
cm = bpy.data.materials.new("cloud"); cm.use_nodes = True
cm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.95, 0.96, 1.0, 1)
cl.data.materials.append(cm)
setup_world(sky=(0.55, 0.72, 1.0), sun_dir=(-0.3, -0.7, 0.8), sun_strength=3.0, strength=1.0, samples=32)
scene = bpy.context.scene
scene.render.film_transparent = False
for name, loc, tgt in [("south", (-60, 1300, 560), (0, 330, 200)), ("top", (-10, 260, 1500), (0, 250, 150)), ("summit", (60, -60, 380), (0, 380, 240))]:
    cd = bpy.data.cameras.new(name); cd.lens = 32; cd.clip_end = 5000
    cam = bpy.data.objects.new(name, cd); scene.collection.objects.link(cam)
    cam.location = Vector(loc); cam.rotation_euler = (Vector(tgt) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 1400, 1000
    scene.render.filepath = f"art/out/terrain_{name}.png"
    bpy.ops.render.render(write_still=True)
print("done")
