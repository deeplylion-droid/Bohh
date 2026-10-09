"""Render dei pet e delle uova per icona e miniature del gioco: sfondo trasparente, senza ombra a terra
(le immagini vengono ritagliate e composte in HTML) e a risoluzione piu' alta delle anteprime.

Uso (dalla cartella art/): ../.tools/venv/bin/python promo/render_heroes.py Yeti:3q EggLegendary:front ...
Uscita: art/out/promo/<Nome>_<vista>.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.render import render_objects  # noqa: E402

ART = Path(__file__).resolve().parents[1]
OUT = ART / "out" / "promo"


def find_blend(name: str) -> Path:
    for kind in ("pet", "egg", "prop", "bat"):
        p = ART / "out" / kind / name / f"{name}.blend"
        if p.exists():
            return p
    raise SystemExit(f"modello non trovato: {name}")


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    res = 1400
    for spec in argv:
        name, _, view = spec.partition(":")
        view = view or "3q"
        bpy.ops.wm.open_mainfile(filepath=str(find_blend(name)))
        objs = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.name.startswith("ShadowCatcher")]
        out = OUT / f"{name}_{view}.png"
        render_objects(objs, out, view=view, res=res, ground=False, samples=96)
        print(f"[promo] {out.relative_to(ART)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
