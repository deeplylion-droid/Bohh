"""Pacchetto dei pet e delle uova di Climb & Steal Eggs da passare a un altro progetto o agente.

Contiene i modelli 3D (FBX + JSON delle parti) con un'anteprima ciascuno, il catalogo con i dati
di gioco e gli id degli asset gia' caricati su Roblox, il manifest Luau pronto da usare, il codice
Roblox di riferimento (caricamento, scala, mutazioni, effetti) e gli script Blender per rigenerare
o modificare i modelli. La guida per chi lo riceve e' PACK_README.md (diventa README.md nel pacchetto).

Uso (dalla radice): .tools/venv/bin/python tools/export_pack.py [--out build/pack]
Serve aver costruito i modelli (art/out/pet, art/out/egg) e caricato gli asset (Assets.luau).
Uscita: <out>/ClimbStealEggs_PetsEggs/ e <out>/ClimbStealEggs_PetsEggs.zip
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art"
NAME = "ClimbStealEggs_PetsEggs"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# codice Roblox di riferimento copiato cosi' com'e' (percorso nel progetto -> nel pacchetto)
REFERENCE = {
    "src/shared/Visuals.luau": "roblox/reference/Visuals.luau",
    "src/server/Services/AssetService.luau": "roblox/reference/AssetService.luau",
    "src/shared/Config/Pets.luau": "roblox/reference/Config/Pets.luau",
    "src/shared/Config/Rarities.luau": "roblox/reference/Config/Rarities.luau",
    "src/shared/Config/Variants.luau": "roblox/reference/Config/Variants.luau",
}


def font(size: int, bold: bool = True):
    try:
        return ImageFont.truetype(FONT if bold else FONT_REG, size)
    except OSError:
        return ImageFont.load_default()


def build_catalog(tmp: Path) -> dict:
    out = tmp / "catalog_raw.json"
    subprocess.run([str(ROOT / ".tools/bin/lune"), "run", "tools/pack/catalog.luau", str(out)], cwd=ROOT, check=True)
    cat = json.loads(out.read_text())
    out.unlink()
    # le liste vuote arrivano da Luau come oggetti vuoti
    for item in cat["pets"] + cat["eggs"]:
        if item["model"] and not item["model"]["effectParts"]:
            item["model"]["effectParts"] = []
    return cat


def trimmed(png: Path) -> Image.Image:
    """Render (sfondo trasparente) su bianco, ritagliato attorno al soggetto e alla sua ombra."""
    im = Image.open(png).convert("RGBA")
    flat = Image.new("RGBA", im.size, (255, 255, 255, 255))
    flat.alpha_composite(im)
    box = im.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox() or (0, 0, im.width, im.height)
    pad = int(0.04 * max(im.size))
    box = (max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad))
    return flat.convert("RGB").crop(box)


def fit(im: Image.Image, w: int, h: int) -> Image.Image:
    k = min(w / im.width, h / im.height)
    small = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), (255, 255, 255))
    canvas.paste(small, ((w - small.width) // 2, (h - small.height) // 2))
    return canvas


def copy_models(cat: dict, pack: Path) -> None:
    for kind, items, folder in (("pet", cat["pets"], "pets"), ("egg", cat["eggs"], "eggs")):
        for item in items:
            src = ART / "out" / kind / item["id"]
            dst = pack / "models" / folder / item["id"]
            dst.mkdir(parents=True, exist_ok=True)
            for ext in (".fbx", ".json"):
                shutil.copy2(src / f"{item['id']}{ext}", dst / f"{item['id']}{ext}")
            fit(trimmed(src / f"{item['id']}_3q.png"), 512, 512).save(dst / f"{item['id']}.jpg", quality=90)
            item["files"] = {
                "fbx": f"models/{folder}/{item['id']}/{item['id']}.fbx",
                "json": f"models/{folder}/{item['id']}/{item['id']}.json",
                "preview": f"models/{folder}/{item['id']}/{item['id']}.jpg",
            }


def sheet(items: list[dict], rarities: list[dict], kind: str, path: Path, cols: int, grouped: bool = True) -> None:
    """Foglio con tutti i modelli in griglia con nome italiano e id: divisi per rarita' (pet) o in
    un'unica griglia (uova); il bordo di ogni casella ha il colore della rarita'."""
    cell, label, pad, head = 230, 46, 12, 40
    color = {r["id"]: tuple(r["color"]) for r in rarities}
    dark = {r["id"]: tuple(r["colorDark"]) for r in rarities}
    rows = []
    if grouped:
        for r in rarities:
            group = [i for i in items if i["rarity"] == r["id"]]
            for k in range(0, len(group), cols):
                rows.append((r, group[k:k + cols], k == 0))
    else:
        for k in range(0, len(items), cols):
            rows.append((None, items[k:k + cols], False))
    width = pad + cols * (cell + pad)
    height = pad + sum((head if first else 0) + cell + label + pad for _, _, first in rows)
    img = Image.new("RGB", (width, height), (246, 244, 250))
    d = ImageDraw.Draw(img)
    f_head, f_name, f_id = font(22), font(15), font(12, bold=False)
    y = pad
    for r, group, first in rows:
        if first:
            title = f"{r['name']['it']} / {r['name']['en']}" if r.get("name") else r["id"]
            d.rounded_rectangle((pad, y, width - pad, y + head - 8), 10, fill=dark[r["id"]])
            d.text((pad + 12, y + 5), title.upper(), fill=color[r["id"]], font=f_head)
            y += head
        for k, item in enumerate(group):
            x = pad + k * (cell + pad)
            src = ART / "out" / kind / item["id"] / f"{item['id']}_3q.png"
            img.paste(fit(trimmed(src), cell, cell), (x, y))
            d.rectangle((x, y, x + cell - 1, y + cell + label - 1), outline=color[item["rarity"]], width=4)
            name = item["name"]["it"] if item.get("name") else item["id"]
            tw = d.textlength(name, font=f_name)
            d.text((x + (cell - tw) / 2, y + cell + 4), name, fill=(40, 30, 60), font=f_name)
            tw = d.textlength(item["id"], font=f_id)
            d.text((x + (cell - tw) / 2, y + cell + 24), item["id"], fill=(110, 100, 130), font=f_id)
        y += cell + label + pad
    img.save(path, quality=90)


def lua(v, indent: str) -> str:
    """Valore Python -> sorgente Luau (tabelle annidate su piu' righe)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(round(v, 4)) if isinstance(v, float) else str(v)
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, list):
        if all(isinstance(x, (int, float)) for x in v):
            return "{ " + ", ".join(lua(x, indent) for x in v) + " }"
        inner = indent + "\t"
        return "{\n" + "".join(f"{inner}{lua(x, inner)},\n" for x in v) + indent + "}"
    if isinstance(v, dict):
        inner = indent + "\t"
        body = "".join(f"{inner}{k} = {lua(x, inner)},\n" for k, x in v.items() if x is not None)
        return "{\n" + body + indent + "}"
    raise TypeError(type(v))


def manifest(cat: dict, path: Path) -> None:
    """Manifest Luau dei soli pet e uova, nello stesso formato di Assets.Models del gioco."""
    models = {}
    for kind, items in (("pet", cat["pets"]), ("egg", cat["eggs"])):
        for item in items:
            m = item["model"]
            parts = [{k: p.get(k) for k in ("name", "color", "material", "role", "transparency", "reflectance",
                                            "group", "pivot", "center")} for p in m["parts"]]
            models[item["id"]] = {"asset": m["robloxAssetId"], "kind": kind, "size": m["size"], "parts": parts}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "--!strict\n"
        "-- Modelli 3D dei pet e delle uova di Climb & Steal Eggs: id dell'asset \"Model\" su Roblox\n"
        "-- (InsertService:LoadAsset) e proprieta' di ogni MeshPart. Stesso formato di Assets.Models nel\n"
        "-- gioco originale: vedi reference/AssetService.luau (build) per applicarle. Generato da\n"
        "-- tools/export_pack.py.\n\n"
        "return " + lua(models, "") + "\n"
    )


def copy_sources(pack: Path) -> None:
    for rel, dst in REFERENCE.items():
        target = pack / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    # stessa struttura del progetto (source/art/lib, pets, eggs): lib/toy.py scrive in source/art/out
    src = pack / "source" / "art"
    for sub in ("lib", "pets"):
        (src / sub).mkdir(parents=True, exist_ok=True)
        for f in sorted((ART / sub).glob("*.py")):
            shutil.copy2(f, src / sub / f.name)
    (src / "eggs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ART / "eggs" / "eggs.py", src / "eggs" / "eggs.py")
    shutil.copy2(ART / "README.md", src / "README.md")
    tools = pack / "source" / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    for f in ("upload_assets.py", "rbxcloud.py"):
        shutil.copy2(ROOT / "tools" / f, tools / f)


def models_table(cat: dict) -> str:
    rows = ["| Id | Nome (IT / EN) | Rarità | Altezza (stud) | Zona | Effetti | Asset Roblox |",
            "|---|---|---|---|---|---|---|"]
    for p in cat["pets"]:
        n = p["name"] or {"it": p["id"], "en": p["id"]}
        extra = " (gigante)" if p["giant"] else (" (vola)" if p["flying"] else "")
        rows.append(f"| {p['id']} | {n['it']} / {n['en']} | {p['rarity']} | {p['height']}{extra} | "
                    f"{p.get('zone') or ''} | {', '.join(p['model']['effectParts'])} | {p['model']['robloxAssetId']} |")
    rows += ["", "| Id | Nome (IT / EN) | Rarità | Asset Roblox |", "|---|---|---|---|"]
    for e in cat["eggs"]:
        n = e["name"] or {"it": e["id"], "en": e["id"]}
        rows.append(f"| {e['id']} | {n['it']} / {n['en']} | {e['rarity']} | {e['model']['robloxAssetId']} |")
    return "\n".join(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "build" / "pack"))
    args = ap.parse_args()
    out = Path(args.out)
    pack = out / NAME
    if pack.exists():
        shutil.rmtree(pack)
    pack.mkdir(parents=True)
    cat = build_catalog(out)
    copy_models(cat, pack)
    sheet(cat["pets"], cat["rarities"], "pet", pack / "anteprima_pet.jpg", cols=5)
    sheet(cat["eggs"], cat["rarities"], "egg", pack / "anteprima_uova.jpg", cols=5, grouped=False)
    manifest(cat, pack / "roblox" / "PetAssets.luau")
    copy_sources(pack)
    (pack / "catalog.json").write_text(json.dumps(cat, indent=1, ensure_ascii=False) + "\n")
    readme = (ROOT / "tools" / "pack" / "PACK_README.md").read_text()
    (pack / "README.md").write_text(readme.replace("{{MODELS_TABLE}}", models_table(cat)))
    zpath = out / f"{NAME}.zip"
    if zpath.exists():
        zpath.unlink()
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(pack.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(out))
    size = sum(f.stat().st_size for f in pack.rglob("*") if f.is_file())
    print(f"pet {len(cat['pets'])}, uova {len(cat['eggs'])}: {pack} ({size / 1e6:.1f} MB)")
    print(f"zip: {zpath} ({zpath.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
