"""Carica build/assets/RakeBody.glb (creatura con scheletro) e scrive src/shared/RakeAsset.luau."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from upload import curl, ROOT, ASSETS, USER  # noqa: E402

import time  # noqa: E402


def main():
    request = json.dumps({"assetType": "Model", "displayName": "TheRakeBody", "description": "The Rake: corpo con scheletro",
                          "creationContext": {"creator": {"userId": USER}}})
    op = curl(["-X", "POST", "https://apis.roblox.com/assets/v1/assets", "-F", "request=%s;type=application/json" % request,
               "-F", "fileContent=@%s;type=model/gltf-binary" % os.path.join(ASSETS, "RakeBody.glb")])
    if "operationId" not in op:
        sys.exit("Caricamento fallito: %s" % op)
    for _ in range(80):
        time.sleep(3)
        res = curl(["https://apis.roblox.com/assets/v1/operations/" + op["operationId"]])
        if res.get("done"):
            break
    else:
        sys.exit("Timeout")
    asset_id = res["response"]["assetId"]
    print("Asset", asset_id, res["response"].get("moderationResult"))
    info = json.load(open(os.path.join(ASSETS, "rake_bones.json")))
    c, s = info["center"], info["size"]
    lines = ["-- Generato da tools/meshgen/upload_creature.py: non modificare a mano.",
             "-- Corpo di The Rake (mesh con scheletro) e posizione a riposo delle ossa (suolo a y = 0).", "return {",
             "\tASSET_ID = %s," % asset_id,
             "\tcenter = Vector3.new(%g, %g, %g)," % tuple(c),
             "\tsize = Vector3.new(%g, %g, %g)," % tuple(s), "\tBONES = {"]
    for name, p in info["bones"].items():
        lines.append("\t\t%s = Vector3.new(%g, %g, %g)," % (name, p[0], p[1], p[2]))
    lines += ["\t},", "}", ""]
    open(os.path.join(ROOT, "src", "shared", "RakeAsset.luau"), "w").write("\n".join(lines))
    print("Scritto src/shared/RakeAsset.luau")


if __name__ == "__main__":
    main()
