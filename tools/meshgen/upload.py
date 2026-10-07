"""Carica build/assets/RakeAssets.glb su Roblox (Open Cloud Assets API) e scrive src/shared/Assets.luau.

Uso: ROBLOX_CREATOR_USER_ID=... python3 tools/meshgen/upload.py
La chiave API è aggiunta dal proxy dell'ambiente; in locale imposta l'header x-api-key (ROBLOX_API_KEY).
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ASSETS = os.path.join(ROOT, "build", "assets")
USER = os.environ.get("ROBLOX_CREATOR_USER_ID", "118377242")


def curl(args):
    cmd = ["curl", "-sS"] + args
    key = os.environ.get("ROBLOX_API_KEY")
    if key:
        cmd += ["-H", "x-api-key: " + key]
    return json.loads(subprocess.check_output(cmd))


def main():
    request = json.dumps({
        "assetType": "Model",
        "displayName": "TheRakeAssets",
        "description": "Modelli procedurali di The Rake: Caccia nei Boschi",
        "creationContext": {"creator": {"userId": USER}},
    })
    op = curl(["-X", "POST", "https://apis.roblox.com/assets/v1/assets",
               "-F", "request=%s;type=application/json" % request,
               "-F", "fileContent=@%s;type=model/gltf-binary" % os.path.join(ASSETS, "RakeAssets.glb")])
    if "operationId" not in op:
        sys.exit("Caricamento fallito: %s" % op)
    for _ in range(60):
        time.sleep(3)
        res = curl(["https://apis.roblox.com/assets/v1/operations/" + op["operationId"]])
        if res.get("done"):
            break
    else:
        sys.exit("Timeout in attesa dell'elaborazione")
    asset_id = res["response"]["assetId"]
    print("Asset", asset_id, res["response"].get("moderationResult"))

    manifest = json.load(open(os.path.join(ASSETS, "manifest.json")))
    lines = [
        "-- Generato da tools/meshgen/upload.py: non modificare a mano.",
        "-- Modelli 3D caricati su Roblox e dimensioni originali (in stud) di ogni mesh.",
        "return {",
        "\tASSET_ID = %s," % asset_id,
        "\tMESHES = {",
    ]
    for name, info in sorted(manifest.items()):
        c, s = info["center"], info["size"]
        lines.append("\t\t%s = { center = Vector3.new(%g, %g, %g), size = Vector3.new(%g, %g, %g) }," % (name, c[0], c[1], c[2], s[0], s[1], s[2]))
    lines += ["\t},", "}", ""]
    with open(os.path.join(ROOT, "src", "shared", "Assets.luau"), "w") as f:
        f.write("\n".join(lines))
    print("Scritto src/shared/Assets.luau")


if __name__ == "__main__":
    main()
