"""Genera build/assets/RakeAssets.glb (tutti i modelli + atlante) e build/assets/manifest.json.

Uso: python3 tools/meshgen/generate.py   (richiede numpy e Pillow)
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from PIL import Image  # noqa: E402

from atlas import build_atlas  # noqa: E402
from gltf import write_glb  # noqa: E402
from models import all_models  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "build", "assets")


def main():
    os.makedirs(OUT, exist_ok=True)
    atlas = build_atlas()
    buf = io.BytesIO()
    Image.fromarray(atlas, "RGBA").save(buf, format="PNG", optimize=True)
    Image.fromarray(atlas, "RGBA").save(os.path.join(OUT, "atlas.png"))
    meshes = all_models()
    manifest = {}
    for m in meshes:
        lo, hi = m.bounds()
        manifest[m.name] = {
            "center": [round((lo[i] + hi[i]) / 2, 4) for i in range(3)],
            "size": [round(hi[i] - lo[i], 4) for i in range(3)],
            "tris": len(m.tris),
        }
        assert len(m.tris) < 20000, m.name
    write_glb(os.path.join(OUT, "RakeAssets.glb"), meshes, buf.getvalue())
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    total = sum(v["tris"] for v in manifest.values())
    print("%d mesh, %d triangoli, glb %.1f KB" % (len(meshes), total, os.path.getsize(os.path.join(OUT, "RakeAssets.glb")) / 1024))
    return meshes, atlas


if __name__ == "__main__":
    main()
