"""Client minimale per le Open Cloud API di Roblox.

La chiave API viene aggiunta automaticamente dal proxy dell'ambiente (header x-api-key);
in alternativa si puo' impostare la variabile ROBLOX_API_KEY.

Uso da riga di comando:
  python tools/rbxcloud.py upload <file> <Model|Decal|Audio> <nome>
  python tools/rbxcloud.py publish <file.rbxl> [Saved|Published]
  python tools/rbxcloud.py luau <script.luau | -e "codice">
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

UNIVERSE_ID = 10769912716
PLACE_ID = 126700834809859
CREATOR_USER_ID = 118377242
BASE = "https://apis.roblox.com"

CONTENT_TYPES = {
    ".fbx": "model/fbx",
    ".gltf": "model/gltf+json",
    ".glb": "model/gltf-binary",
    ".rbxm": "model/x-rbxm",
    ".rbxmx": "model/x-rbxm",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tga": "image/tga",
    ".bmp": "image/bmp",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
}

_session = requests.Session()
if os.environ.get("ROBLOX_API_KEY"):
    _session.headers["x-api-key"] = os.environ["ROBLOX_API_KEY"]


class CloudError(RuntimeError):
    pass


def _request(method: str, url: str, retries: int = 6, **kwargs) -> requests.Response:
    """Richiesta con retry su rate limit (429) ed errori temporanei (5xx)."""
    delay = 2.0
    for attempt in range(retries):
        try:
            resp = _session.request(method, url, timeout=120, **kwargs)
        except requests.RequestException as exc:  # rete instabile
            if attempt == retries - 1:
                raise CloudError(f"{method} {url}: {exc}") from exc
            time.sleep(delay)
            delay *= 2
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == retries - 1:
                break
            wait = float(resp.headers.get("Retry-After") or delay)
            time.sleep(min(wait, 60))
            delay *= 2
            continue
        return resp
    raise CloudError(f"{method} {url}: HTTP {resp.status_code} {resp.text[:500]}")


def _json(resp: requests.Response) -> dict:
    if resp.status_code >= 400:
        raise CloudError(f"HTTP {resp.status_code} {resp.request.method} {resp.url}: {resp.text[:800]}")
    return resp.json() if resp.content else {}


# ---------------------------------------------------------------- asset

def upload_asset(path: str | Path, asset_type: str, display_name: str, description: str = "",
                 poll_timeout: float = 300) -> dict:
    """Carica un file come nuovo asset e attende la fine dell'elaborazione.

    Ritorna la risposta finale dell'operazione (contiene assetId e moderationResult).
    """
    path = Path(path)
    ctype = CONTENT_TYPES.get(path.suffix.lower())
    if not ctype:
        raise CloudError(f"Estensione non supportata: {path.suffix}")
    request = {
        "assetType": asset_type,
        "displayName": display_name[:50],
        "description": description[:1000],
        "creationContext": {"creator": {"userId": str(CREATOR_USER_ID)}},
    }
    with path.open("rb") as fh:
        files = {
            "request": (None, json.dumps(request), "application/json"),
            "fileContent": (path.name, fh, ctype),
        }
        op = _json(_request("POST", f"{BASE}/assets/v1/assets", files=files))
    return wait_operation(op, poll_timeout)


def update_asset(asset_id: int | str, path: str | Path, asset_type: str, poll_timeout: float = 300) -> dict:
    """Carica una nuova versione di un asset esistente (stesso ID)."""
    path = Path(path)
    ctype = CONTENT_TYPES[path.suffix.lower()]
    request = {"assetId": str(asset_id), "assetType": asset_type}
    with path.open("rb") as fh:
        files = {
            "request": (None, json.dumps(request), "application/json"),
            "fileContent": (path.name, fh, ctype),
        }
        op = _json(_request("PATCH", f"{BASE}/assets/v1/assets/{asset_id}", files=files))
    return wait_operation(op, poll_timeout)


def wait_operation(op: dict, timeout: float = 300) -> dict:
    op_id = op.get("operationId") or op.get("path", "").split("/")[-1]
    deadline = time.time() + timeout
    delay = 1.0
    while not op.get("done"):
        if time.time() > deadline:
            raise CloudError(f"Timeout operazione {op_id}")
        time.sleep(delay)
        delay = min(delay * 1.5, 8)
        op = _json(_request("GET", f"{BASE}/assets/v1/operations/{op_id}"))
    if "error" in op:
        raise CloudError(f"Operazione {op_id} fallita: {op['error']}")
    return op.get("response", op)


def get_asset(asset_id: int | str, read_mask: str = "") -> dict:
    url = f"{BASE}/assets/v1/assets/{asset_id}"
    if read_mask:
        url += f"?readMask={read_mask}"
    return _json(_request("GET", url))


def asset_location(asset_id: int | str) -> str:
    data = _json(_request("GET", f"{BASE}/asset-delivery-api/v1/assetId/{asset_id}"))
    if "location" not in data:
        raise CloudError(f"Asset {asset_id} non scaricabile: {data}")
    return data["location"]


# ---------------------------------------------------------------- luoghi

def publish_place(path: str | Path, version_type: str = "Saved") -> int:
    path = Path(path)
    ctype = "application/xml" if path.suffix == ".rbxlx" else "application/octet-stream"
    url = f"{BASE}/universes/v1/{UNIVERSE_ID}/places/{PLACE_ID}/versions?versionType={version_type}"
    data = _json(_request("POST", url, data=path.read_bytes(), headers={"Content-Type": ctype}, retries=3))
    return int(data["versionNumber"])


def update_place(fields: dict) -> dict:
    mask = ",".join(fields.keys())
    url = f"{BASE}/cloud/v2/universes/{UNIVERSE_ID}/places/{PLACE_ID}?updateMask={mask}"
    return _json(_request("PATCH", url, json=fields))


def update_universe(fields: dict) -> dict:
    mask = ",".join(fields.keys())
    url = f"{BASE}/cloud/v2/universes/{UNIVERSE_ID}?updateMask={mask}"
    return _json(_request("PATCH", url, json=fields))


# ---------------------------------------------------------------- Luau execution

def run_luau(script: str, version: int | None = None, timeout_s: int = 120, poll_timeout: float = 600) -> dict:
    """Esegue codice Luau su un server Roblox del luogo (versione indicata o ultima).

    Ritorna {"state", "results", "error", "logs"}.
    """
    base = f"{BASE}/cloud/v2/universes/{UNIVERSE_ID}/places/{PLACE_ID}"
    if version is not None:
        base += f"/versions/{version}"
    body = {"script": script, "timeout": f"{timeout_s}s"}
    task = _json(_request("POST", f"{base}/luau-execution-session-tasks", json=body, retries=8))
    path = task["path"]
    deadline = time.time() + poll_timeout
    delay = 1.0
    while task.get("state") in ("QUEUED", "PROCESSING", None):
        if time.time() > deadline:
            raise CloudError(f"Timeout task Luau {path}")
        time.sleep(delay)
        delay = min(delay * 1.4, 6)
        task = _json(_request("GET", f"{BASE}/cloud/v2/{path}"))
    logs = []
    try:
        page = _json(_request("GET", f"{BASE}/cloud/v2/{path}/logs?view=STRUCTURED"))
        for entry in page.get("luauExecutionSessionTaskLogs", []):
            for msg in entry.get("structuredMessages", []) or []:
                logs.append(f"[{msg.get('messageType', '')}] {msg.get('message', '')}")
            for msg in entry.get("messages", []) or []:
                logs.append(msg)
    except CloudError as exc:
        logs.append(f"(log non disponibili: {exc})")
    return {
        "state": task.get("state"),
        "results": (task.get("output") or {}).get("results"),
        "error": task.get("error"),
        "logs": logs,
    }


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "upload":
        res = upload_asset(argv[2], argv[3], argv[4])
        print(json.dumps(res, indent=2))
    elif cmd == "publish":
        print("versione", publish_place(argv[2], argv[3] if len(argv) > 3 else "Saved"))
    elif cmd == "luau":
        code = argv[3] if argv[2] == "-e" else Path(argv[2]).read_text(encoding="utf-8")
        res = run_luau(code)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res["state"] == "COMPLETE" else 2
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
