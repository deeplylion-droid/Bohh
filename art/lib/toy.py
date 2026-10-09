"""Costruzione di modelli multi-parte (un colore/materiale per parte) per Roblox.

Ogni parte diventa una MeshPart. Pipeline: SDF -> marching cubes -> Blender
(decimazione, smooth shading) -> FBX (1 unita' = 1 stud) + JSON con colori/ruoli.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

import bpy
import numpy as np

from .mesher import mesh_sdf
from .sdf import SDF

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "art" / "out"


def srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


@dataclass
class Part:
    name: str
    sdf: SDF
    color: tuple[int, int, int]
    material: str = "SmoothPlastic"  # materiale Roblox
    role: str = "skin"  # skin | detail | eye | shine | glow | fixed
    tris: int = 3000
    voxel: float | None = None
    transparency: float = 0.0
    reflectance: float = 0.0
    group: str | None = None  # gruppo per animazioni procedurali (es. "WingL")
    pivot: tuple[float, float, float] | None = None  # perno del gruppo (spazio Blender)
    smooth: bool = True  # False = faccette piatte (stile low-poly per rocce)


@dataclass
class Model:
    name: str
    kind: str = "pet"  # pet | egg | prop | icon
    voxel: float = 0.03
    parts: list[Part] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def add(self, name: str, sdf: SDF, color, **kw) -> Part:
        p = Part(name, sdf, tuple(int(c) for c in color), **kw)
        self.parts.append(p)
        return p

    # ------------------------------------------------------------------ build
    def build(self, render: bool = True, views: tuple[str, ...] = ("3q",), res: int = 900,
              export: bool = True) -> dict:
        out = OUT / self.kind / self.name
        out.mkdir(parents=True, exist_ok=True)
        reset_scene()
        objs = []
        info_parts = []
        for part in self.parts:
            voxel = part.voxel or self.voxel
            verts, faces, _ = mesh_sdf(part.sdf, voxel)
            # evita decimazioni estreme (deformano la forma): rimesha piu' grossolano
            while len(faces) > part.tris * 8 and voxel < 2.0:
                voxel *= math.sqrt(len(faces) / (part.tris * 5))
                verts, faces, _ = mesh_sdf(part.sdf, voxel)
            obj = make_object(part.name, verts, faces)
            decimate(obj, part.tris)
            if not part.smooth:
                for poly in obj.data.polygons:
                    poly.use_smooth = False
            obj.data.materials.append(make_material(part))
            objs.append(obj)
            bb = bounds_of([obj])
            center = (bb[0] + bb[1]) / 2
            size = bb[1] - bb[0]
            info_parts.append({
                "name": part.name,
                "color": list(part.color),
                "material": part.material,
                "role": part.role,
                "transparency": part.transparency,
                "reflectance": part.reflectance,
                "group": part.group,
                "pivot": to_roblox(part.pivot) if part.pivot else None,
                "center": to_roblox(center),
                "size": [float(size[0]), float(size[2]), float(size[1])],
                "tris": len(obj.data.polygons),
            })
        bb = bounds_of(objs)
        info = {
            "name": self.name,
            "kind": self.kind,
            "parts": info_parts,
            "boundsMin": to_roblox_min(bb),
            "size": [float(bb[1][0] - bb[0][0]), float(bb[1][2] - bb[0][2]), float(bb[1][1] - bb[0][1])],
            "tris": sum(p["tris"] for p in info_parts),
            "meta": self.meta,
        }
        if export:
            export_fbx(objs, out / f"{self.name}.fbx")
            (out / f"{self.name}.json").write_text(json.dumps(info, indent=1))
            bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{self.name}.blend"))
        if render and self.kind == "icon":
            # icone dell'interfaccia: sfondo trasparente, niente ombra a terra, in art/out/images
            from .render import render_objects
            images = OUT / "images"
            images.mkdir(parents=True, exist_ok=True)
            render_objects(objs, images / f"Icon{self.name}.png", view=views[0] if views else "3q", res=res,
                           ground=False)
        elif render:
            from .render import render_objects
            for v in views:
                render_objects(objs, out / f"{self.name}_{v}.png", view=v, res=res)
        print(f"[toy] {self.kind}/{self.name}: {info['tris']} tris, size {np.round(info['size'], 2).tolist()}")
        return info


# ---------------------------------------------------------------------- blender helpers

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_object(name: str, verts: np.ndarray, faces: np.ndarray):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts.tolist(), [], faces.tolist())
    mesh.validate(clean_customdata=False)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj


def decimate(obj, target_tris: int):
    n = len(obj.data.polygons)
    if n <= target_tris:
        return
    mod = obj.modifiers.new("dec", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = max(target_tris / n, 0.002)
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = obj
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    for poly in obj.data.polygons:
        poly.use_smooth = True


def bounds_of(objs):
    pts = []
    for o in objs:
        m = o.matrix_world
        for v in o.data.vertices:
            pts.append(tuple(m @ v.co))
    pts = np.array(pts)
    return pts.min(0), pts.max(0)


def to_roblox(v) -> list[float]:
    """Blender (x, y, z) -> Roblox (-x, z, y) (verificato con caricamento di prova)."""
    return [float(-v[0]), float(v[2]), float(v[1])]


def to_roblox_min(bb) -> list[float]:
    lo, hi = bb
    return [float(-hi[0]), float(lo[2]), float(lo[1])]


def export_fbx(objs, path: Path):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True, global_scale=0.01, axis_forward="-Z", axis_up="Y",
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE", mesh_smooth_type="FACE",
        use_mesh_modifiers=True, add_leaf_bones=False, bake_anim=False, path_mode="STRIP",
    )


# ---------------------------------------------------------------------- materiali (anteprima)

def make_material(part: Part):
    mat = bpy.data.materials.new(f"{part.name}_{part.material}")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    col = [srgb_to_linear(c) for c in part.color] + [1.0]
    bsdf.inputs["Base Color"].default_value = col
    m = part.material
    rough = {"SmoothPlastic": 0.42, "Plastic": 0.55, "Metal": 0.32, "Foil": 0.22, "Glass": 0.04,
             "Ice": 0.12, "Neon": 0.5, "Wood": 0.7, "Slate": 0.85, "Sand": 0.9, "Grass": 0.9,
             "Snow": 0.6, "Rock": 0.85, "Basalt": 0.8, "Marble": 0.3, "Fabric": 0.95,
             "Granite": 0.7, "Pebble": 0.8, "Concrete": 0.9, "Brick": 0.85, "Cobblestone": 0.85,
             "WoodPlanks": 0.75, "Leather": 0.6, "CrackedLava": 0.8, "Ground": 0.95,
             "LeafyGrass": 0.9, "Mud": 0.9, "Salt": 0.7, "Limestone": 0.8, "Pavement": 0.9,
             "Asphalt": 0.9, "DiamondPlate": 0.4, "CorrodedMetal": 0.7}.get(m, 0.5)
    bsdf.inputs["Roughness"].default_value = rough
    if m in ("Metal", "Foil", "DiamondPlate"):
        bsdf.inputs["Metallic"].default_value = 1.0
    if m == "Neon":
        bsdf.inputs["Emission Color"].default_value = col
        bsdf.inputs["Emission Strength"].default_value = 1.3
    if m in ("Glass", "Ice"):
        bsdf.inputs["Transmission Weight"].default_value = 0.35 if m == "Glass" else 0.3
        bsdf.inputs["Coat Weight"].default_value = 0.8
        bsdf.inputs["Coat Roughness"].default_value = 0.03
        bsdf.inputs["IOR"].default_value = 1.45
    if part.reflectance > 0:
        bsdf.inputs["Coat Weight"].default_value = min(1.0, part.reflectance * 2)
        bsdf.inputs["Coat Roughness"].default_value = 0.05
    if part.transparency > 0:
        bsdf.inputs["Alpha"].default_value = 1.0 - part.transparency
    return mat
