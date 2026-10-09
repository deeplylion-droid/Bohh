"""Carica su Roblox i modelli 3D e le immagini generate in art/out e rigenera src/shared/Assets.luau.

- Modelli: art/out/<tipo>/<Nome>/<Nome>.fbx (+ .json) con tipo pet, egg, prop, bat o fx:
  caricati come asset "Model" (in gioco li carica InsertService:LoadAsset).
- Immagini: art/out/images/<Nome>.png: caricate come "Decal"; l'id dell'immagine vera si ricava
  con una sessione Luau (InsertService:LoadAsset sul decal).
- Suoni: tools/sounds.json (asset audio della libreria ufficiale Roblox).

Lo stato (id e hash dei file) e' in art/assets.lock.json: i file invariati non vengono ricaricati,
quelli cambiati diventano una nuova versione dello stesso asset.

Uso:
  python tools/upload_assets.py              # carica cio' che e' nuovo o cambiato, rigenera Assets.luau
  python tools/upload_assets.py --only Chick,EggCommon
  python tools/upload_assets.py --dry-run    # mostra cosa farebbe
  python tools/upload_assets.py --verify Chick   # confronta le parti caricate con il JSON
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import rbxcloud  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "art" / "out"
LOCK = ROOT / "art" / "assets.lock.json"
MANIFEST = ROOT / "src" / "shared" / "Assets.luau"
SOUNDS = ROOT / "tools" / "sounds.json"
KINDS = ("pet", "egg", "prop", "bat", "fx")


def sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def load_lock() -> dict:
    if LOCK.exists():
        return json.loads(LOCK.read_text())
    return {"models": {}, "images": {}}


def save_lock(lock: dict) -> None:
    LOCK.write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n")


def find_models() -> dict[str, dict]:
    found = {}
    for kind in KINDS:
        base = OUT / kind
        if not base.exists():
            continue
        for d in sorted(base.iterdir()):
            fbx = d / f"{d.name}.fbx"
            js = d / f"{d.name}.json"
            if fbx.exists() and js.exists():
                found[d.name] = {"fbx": fbx, "json": js, "kind": kind}
    return found


def find_images() -> dict[str, Path]:
    base = OUT / "images"
    if not base.exists():
        return {}
    return {p.stem: p for p in sorted(base.glob("*.png"))}


def asset_id_of(response: dict) -> int:
    if "assetId" in response:
        return int(response["assetId"])
    m = re.search(r"assets/(\d+)", response.get("path", ""))
    if not m:
        raise rbxcloud.CloudError(f"assetId non trovato nella risposta: {response}")
    return int(m.group(1))


def upload_one(name: str, path: Path, asset_type: str, existing: int | None) -> int:
    if existing:
        rbxcloud.update_asset(existing, path, asset_type)
        return existing
    resp = rbxcloud.upload_asset(path, asset_type, name, description="Climb & Steal Eggs")
    return asset_id_of(resp)


def resolve_images(decals: dict[str, int]) -> dict[str, int]:
    """Ricava l'id dell'immagine contenuta in ciascun decal (sessione Luau sul luogo)."""
    if not decals:
        return {}
    pairs = ",".join(f'["{k}"]={v}' for k, v in decals.items())
    script = f"""
local InsertService = game:GetService("InsertService")
local out = {{}}
for name, id in {{{pairs}}} do
	local ok, model = pcall(InsertService.LoadAsset, InsertService, id)
	if ok then
		local d = model:FindFirstChildWhichIsA("Decal", true)
		table.insert(out, name .. "=" .. (if d then d.Texture else "?"))
	else
		table.insert(out, name .. "=ERR " .. tostring(model))
	end
end
return table.concat(out, "\\n")
"""
    r = rbxcloud.run_luau(script, timeout_s=240)
    if r["state"] != "COMPLETE":
        raise rbxcloud.CloudError(f"Risoluzione immagini fallita: {r['error']} {r['logs'][-5:]}")
    result = {}
    for line in (r["results"] or [""])[0].splitlines():
        name, _, tex = line.partition("=")
        m = re.search(r"(\d+)\s*$", tex)
        if m:
            result[name] = int(m.group(1))
        else:
            print(f"  ! immagine {name}: {tex}")
    return result


def lua_value(v, indent: str = "") -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "nil"
    if isinstance(v, (int, float)):
        if isinstance(v, float):
            return f"{v:.4f}".rstrip("0").rstrip(".") if abs(v) > 1e-9 else "0"
        return str(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        if any(isinstance(x, dict) for x in v):
            inner = indent + "\t"
            return "{\n" + "\n".join(f"{inner}{lua_value(x, inner)}," for x in v) + f"\n{indent}}}"
        return "{ " + ", ".join(lua_value(x, indent) for x in v) + " }"
    if isinstance(v, dict):
        inner = indent + "\t"
        items = []
        for k, x in v.items():
            if x is None:
                continue
            key = k if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k) else f"[{json.dumps(k)}]"
            items.append(f"{inner}{key} = {lua_value(x, inner)},")
        if not items:
            return "{}"
        return "{\n" + "\n".join(items) + f"\n{indent}}}"
    raise TypeError(type(v))


def write_manifest(lock: dict, models: dict[str, dict]) -> None:
    entries = {}
    for name in sorted(lock["models"]):
        rec = lock["models"][name]
        src = models.get(name)
        info = json.loads(src["json"].read_text()) if src else rec.get("info")
        if not info:
            continue
        parts = [
            {
                "name": p["name"],
                "color": p["color"],
                "material": p["material"],
                "role": p["role"],
                "transparency": p.get("transparency") or None,
                "reflectance": p.get("reflectance") or None,
                "group": p.get("group"),
                "pivot": [round(c, 4) for c in p["pivot"]] if p.get("pivot") else None,
                "center": [round(c, 4) for c in p["center"]],
            }
            for p in info["parts"]
        ]
        entries[name] = {
            "asset": rec["asset"],
            "kind": info["kind"],
            "size": [round(c, 4) for c in info["size"]],
            "parts": parts,
        }
    images = {name: f"rbxassetid://{rec['image']}" for name, rec in sorted(lock["images"].items()) if rec.get("image")}
    sounds = {}
    if SOUNDS.exists():
        for key, rec in sorted(json.loads(SOUNDS.read_text()).items()):
            sounds[key] = f"rbxassetid://{rec['id']}"
    lines = [
        "--!strict",
        "-- Elenco degli asset caricati su Roblox (generato da tools/upload_assets.py: non modificare a mano).",
        "-- Models: modelli 3D (InsertService:LoadAsset) con le proprieta' di ogni parte.",
        "-- Images / Sounds: id pronti per l'uso.",
        "",
        "export type PartInfo = {",
        "\tname: string,",
        "\tcolor: { number },",
        "\tmaterial: string,",
        "\trole: string,",
        "\ttransparency: number?,",
        "\treflectance: number?,",
        "\tgroup: string?,",
        "\tpivot: { number }?,",
        "\tcenter: { number }?,",
        "}",
        "",
        "export type ModelInfo = {",
        "\tasset: number,",
        "\tkind: string,",
        "\tsize: { number },",
        "\tparts: { PartInfo },",
        "}",
        "",
        "return {",
        f"\tModels = {lua_value(entries, chr(9))} :: {{ [string]: ModelInfo }},",
        f"\tImages = {lua_value(images, chr(9))} :: {{ [string]: string }},",
        f"\tSounds = {lua_value(sounds, chr(9))} :: {{ [string]: string }},",
        "}",
        "",
    ]
    MANIFEST.write_text("\n".join(lines))


def verify(name: str, lock: dict, models: dict[str, dict]) -> None:
    rec = lock["models"].get(name)
    if not rec:
        raise SystemExit(f"{name} non e' stato caricato")
    info = json.loads(models[name]["json"].read_text())
    script = f"""
local m = game:GetService("InsertService"):LoadAsset({rec['asset']})
local out = {{}}
for _, d in m:GetDescendants() do
	if d:IsA("MeshPart") then
		local p, r = d.Position, d.CFrame.Rotation
		local rx, ry, rz = r:ToEulerAnglesXYZ()
		table.insert(out, string.format("%s pos=(%.3f,%.3f,%.3f) size=(%.3f,%.3f,%.3f) rot=(%.1f,%.1f,%.1f)",
			d.Name, p.X, p.Y, p.Z, d.Size.X, d.Size.Y, d.Size.Z, math.deg(rx), math.deg(ry), math.deg(rz)))
	end
end
return table.concat(out, "\\n")
"""
    r = rbxcloud.run_luau(script, timeout_s=120)
    print(f"stato {r['state']} {r['error'] or ''}")
    loaded = {}
    for line in (r["results"] or [""])[0].splitlines():
        loaded[line.split(" ")[0]] = line
    for p in info["parts"]:
        print(f"JSON {p['name']}: center={[round(c, 3) for c in p['center']]} size={[round(c, 3) for c in p['size']]}")
        print(f"     {loaded.get(p['name'], '(mancante)')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="nomi separati da virgola")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify")
    ap.add_argument("--manifest-only", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    lock = load_lock()
    models = find_models()
    images = find_images()
    if args.verify:
        verify(args.verify, lock, models)
        return 0
    only = set(args.only.split(",")) if args.only else None

    todo = []
    if not args.manifest_only:
        for name, src in models.items():
            if only and name not in only:
                continue
            h = sha1(src["fbx"])
            rec = lock["models"].get(name)
            if rec and rec.get("hash") == h:
                continue
            todo.append(("model", name, src["fbx"], "Model", rec["asset"] if rec else None, h))
        for name, path in images.items():
            if only and name not in only:
                continue
            h = sha1(path)
            rec = lock["images"].get(name)
            if rec and rec.get("hash") == h:
                continue
            # un'immagine cambiata diventa un nuovo decal (l'id dell'immagine cambia comunque)
            todo.append(("image", name, path, "Decal", None, h))
    print(f"da caricare: {len(todo)}")
    for t in todo:
        print(f"  {t[0]:5} {t[1]}{' (nuova versione)' if t[4] else ''}")
    if args.dry_run:
        return 0

    new_decals = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(upload_one, t[1], t[2], t[3], t[4]): t for t in todo}
        for fut in as_completed(futures):
            kind, name, _, _, _, h = futures[fut]
            try:
                asset = fut.result()
            except Exception as exc:  # un errore non blocca gli altri caricamenti
                print(f"  ! {name}: {exc}")
                continue
            if kind == "model":
                lock["models"][name] = {"asset": asset, "hash": h}
            else:
                lock["images"][name] = {"decal": asset, "hash": h}
                new_decals[name] = asset
            print(f"  ok {name} -> {asset}")
            save_lock(lock)
    if new_decals:
        for name, image in resolve_images(new_decals).items():
            lock["images"][name]["image"] = image
        save_lock(lock)
    write_manifest(lock, models)
    print(f"manifest aggiornato: {MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
