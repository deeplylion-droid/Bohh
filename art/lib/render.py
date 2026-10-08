"""Render di anteprima in Cycles con luce simile a un esterno di Roblox."""
from __future__ import annotations

import math
import os
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

VIEWS = {
    # direzione dalla quale guarda la camera (spazio Blender, fronte = -Y)
    "3q": (0.62, -1.0, 0.42),
    "front": (0.0, -1.0, 0.18),
    "side": (1.0, -0.05, 0.2),
    "back": (-0.5, 1.0, 0.35),
    "top": (0.35, -0.7, 1.1),
    "low": (0.5, -1.0, 0.05),
}


def setup_world(sky=(0.76, 0.83, 0.96), strength=0.85, sun_strength=3.0, sun_dir=(-0.55, -0.75, 0.9),
                view_transform=os.environ.get("VT", "Standard"), look=os.environ.get("LOOK", "None"), exposure=0.0, samples=48):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.render.film_transparent = True
    try:
        scene.view_settings.view_transform = view_transform
        scene.view_settings.look = look
    except TypeError:
        pass
    scene.view_settings.exposure = exposure
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    # cielo a gradiente: zenit azzurro, orizzonte chiaro e caldo, terreno beige (riflessi credibili sui metalli)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    # Generated nel world = direzione di vista in [-1,1]: rimappa z in [0,1] (0.5 = orizzonte)
    remap = nt.nodes.new("ShaderNodeMath")
    remap.operation = "MULTIPLY_ADD"
    remap.inputs[1].default_value = 0.5
    remap.inputs[2].default_value = 0.5
    nt.links.new(sep.outputs["Z"], remap.inputs[0])
    nt.links.new(remap.outputs[0], ramp.inputs["Fac"])
    el = ramp.color_ramp.elements
    el[0].position = 0.0
    el[0].color = (0.30, 0.26, 0.22, 1)
    el[1].position = 1.0
    el[1].color = (*[pow(c, 2.2) for c in sky], 1)
    mid = el.new(0.5)
    mid.color = (0.86, 0.88, 0.86, 1)
    hz = el.new(0.6)
    hz.color = (*[pow(c, 2.2) * 0.9 + 0.08 for c in sky], 1)
    low = el.new(0.47)
    low.color = (0.55, 0.50, 0.44, 1)
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs[1].default_value = strength
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = sun_strength
    sun.angle = math.radians(4)
    sun.color = (1.0, 0.96, 0.9)
    so = bpy.data.objects.new("Sun", sun)
    scene.collection.objects.link(so)
    d = Vector(sun_dir).normalized()
    so.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    # luce di contorno per staccare la sagoma dallo sfondo
    rim = bpy.data.lights.new("Rim", "AREA")
    rim.energy = 400
    rim.size = 6
    rim.color = (0.85, 0.92, 1.0)
    ro = bpy.data.objects.new("Rim", rim)
    scene.collection.objects.link(ro)
    return so, ro


def frame_camera(objs, view="3q", res=900, lens=60, fill=0.78, aspect=(1, 1)):
    scene = bpy.context.scene
    pts = []
    for o in objs:
        m = o.matrix_world
        verts = list(o.data.vertices)
        pts.extend([m @ v.co for v in verts[:: max(1, len(verts) // 400)]])
    pts = np.array([tuple(p) for p in pts])
    lo, hi = pts.min(0), pts.max(0)
    center = Vector(((lo + hi) / 2).tolist())
    radius = float(np.linalg.norm(hi - lo) / 2)
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = lens
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    d = Vector(VIEWS.get(view, view)).normalized()
    fov = 2 * math.atan(cam_data.sensor_width / (2 * lens))
    dist = radius / math.sin(fov / 2) / fill
    cam.location = center + d * dist
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x = int(res * aspect[0])
    scene.render.resolution_y = int(res * aspect[1])
    cam_data.clip_end = dist * 10
    return cam, center, radius, lo


def add_shadow_catcher(z: float, size: float):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    plane = bpy.context.object
    plane.name = "ShadowCatcher"
    plane.is_shadow_catcher = True
    return plane


def render_objects(objs, path: Path, view="3q", res=900, ground=True, **world_kw):
    scene = bpy.context.scene
    # rimuove luci/camere di render precedenti
    for o in list(scene.objects):
        if o.type in ("LIGHT", "CAMERA") or o.name.startswith("ShadowCatcher"):
            bpy.data.objects.remove(o, do_unlink=True)
    sun, rim = setup_world(**world_kw)
    cam, center, radius, lo = frame_camera(objs, view, res)
    rim.location = center + Vector((-radius * 2.2, radius * 2.5, radius * 1.8))
    rim.rotation_euler = (center - rim.location).to_track_quat("-Z", "Y").to_euler()
    if ground:
        add_shadow_catcher(float(lo[2]) + 0.002, radius * 12)
    scene.render.filepath = str(path)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    bpy.ops.render.render(write_still=True)
    return path
