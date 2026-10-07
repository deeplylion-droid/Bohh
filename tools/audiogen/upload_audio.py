"""Carica build/audio/*.ogg su Roblox e scrive src/shared/Audio.luau (ID e intervalli degli effetti)."""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AUDIO = os.path.join(ROOT, "build", "audio")
USER = os.environ.get("ROBLOX_CREATOR_USER_ID", "118377242")


def curl(args):
    cmd = ["curl", "-sS"] + args
    if os.environ.get("ROBLOX_API_KEY"):
        cmd += ["-H", "x-api-key: " + os.environ["ROBLOX_API_KEY"]]
    return json.loads(subprocess.check_output(cmd))


def upload(name, path):
    request = json.dumps({"assetType": "Audio", "displayName": name, "description": "The Rake: Caccia nei Boschi",
                          "creationContext": {"creator": {"userId": USER}}})
    op = curl(["-X", "POST", "https://apis.roblox.com/assets/v1/assets", "-F", "request=%s;type=application/json" % request,
               "-F", "fileContent=@%s;type=audio/ogg" % path])
    if "operationId" not in op:
        sys.exit("Caricamento fallito: %s" % op)
    for _ in range(60):
        time.sleep(3)
        res = curl(["https://apis.roblox.com/assets/v1/operations/" + op["operationId"]])
        if res.get("done"):
            print(name, res["response"]["assetId"], res["response"].get("moderationResult"))
            return res["response"]["assetId"]
    sys.exit("Timeout")


def main():
    sfx = upload("TheRakeSfx", os.path.join(AUDIO, "Sfx.ogg"))
    amb = upload("TheRakeAmbience", os.path.join(AUDIO, "Ambience.ogg"))
    regions = json.load(open(os.path.join(AUDIO, "regions.json")))
    lines = ["-- Generato da tools/audiogen/upload_audio.py: non modificare a mano.",
             "-- Suoni sintetizzati: un loop d'ambiente e un foglio di effetti riprodotti per intervalli.", "return {",
             '\tAMBIENCE = "rbxassetid://%s",' % amb, '\tSFX = "rbxassetid://%s",' % sfx, "\tREGIONS = {"]
    for name, r in regions.items():
        lines.append("\t\t%s = { start = %g, length = %g, loop = %s }," % (name, r["start"], r["length"], "true" if r["loop"] else "false"))
    lines += ["\t},", "}", ""]
    open(os.path.join(ROOT, "src", "shared", "Audio.luau"), "w").write("\n".join(lines))
    print("Scritto src/shared/Audio.luau")


if __name__ == "__main__":
    main()
