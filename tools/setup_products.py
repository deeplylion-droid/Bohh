"""Crea o aggiorna su Roblox i game pass e i prodotti sviluppatore del gioco (Open Cloud) e scrive i
loro id in src/shared/Config/Products.luau.

Idempotente: cerca per nome quelli gia' esistenti e li aggiorna (nome, descrizione, prezzo, icona,
in vendita) invece di crearne di nuovi. Uso: python tools/setup_products.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import rbxcloud  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "src" / "shared" / "Config" / "Products.luau"
ICONS = ROOT / "art" / "out" / "images"
BASE = rbxcloud.BASE
U = rbxcloud.UNIVERSE_ID

PASSES = {
    "VIP": ("VIP", "+20% coins from all pets, VIP chat tag, the Golden Mallet and double offline earnings.", 249, "IconVIP"),
    "DoubleCoins": ("2x Coins", "All your pets earn double coins, forever.", 399, "IconDoubleCoins"),
    "ExtraIncubator": ("+1 Incubator", "One more incubator in your base to hatch more eggs at once.", 149, "IconIncubator"),
    "BigBackpack": ("Big Backpack", "Carry one more egg at a time up the mountain.", 199, "IconBackpack"),
    "FastHatch": ("Fast Hatch", "Every egg hatches twice as fast.", 299, "IconHatchSpeed"),
    "SuperBarrier": ("Super Barrier", "Your laser barrier lasts 60 seconds longer and recharges faster.", 149, "IconBarrier"),
}
PRODUCTS = {
    "SkipHatchSmall": ("Skip Hatch (up to Rare)", "Instantly finishes the incubator egg that needs the most time (Common to Rare eggs).", 19, "IconSkipHatch"),
    "SkipHatchMedium": ("Skip Hatch (up to Legendary)", "Instantly finishes the incubator egg that needs the most time (up to Legendary eggs).", 49, "IconSkipHatch"),
    "SkipHatchLarge": ("Skip Hatch (any egg)", "Instantly finishes the incubator egg that needs the most time, any rarity.", 99, "IconSkipHatch"),
    "Luck15": ("2x Luck - 15 min", "Doubles your luck for 15 minutes: more mutations, giant pets and rarer pets.", 99, "IconLuck"),
    "CoinsSmall": ("Coin Pouch", "A pouch of coins (15 minutes of your income, at least 1,500).", 49, "IconCoinsSmall"),
    "CoinsMedium": ("Coin Chest", "A chest of coins (1 hour of your income, at least 7,500).", 149, "IconCoinsMedium"),
    "CoinsLarge": ("Coin Mountain", "A mountain of coins (4 hours of your income, at least 40,000).", 399, "IconCoinsLarge"),
}


def _get(url: str) -> dict:
    return rbxcloud._json(rbxcloud._request("GET", url))


def list_all(kind: str) -> list[dict]:
    if kind == "pass":
        url = f"{BASE}/game-passes/v1/universes/{U}/game-passes/creator?pageSize=50"
        key = "gamePasses"
    else:
        url = f"{BASE}/developer-products/v2/universes/{U}/developer-products/creator?pageSize=50"
        key = "developerProducts"
    out, token = [], None
    while True:
        data = _get(url + (f"&pageToken={token}" if token else ""))
        out.extend(data.get(key, []))
        token = data.get("nextPageToken")
        if not token:
            return out


def upsert(kind: str, existing: dict | None, name: str, desc: str, price: int, icon: str, dry: bool) -> int:
    fields = {"name": (None, name), "description": (None, desc), "price": (None, str(price)), "isForSale": (None, "true")}
    img = ICONS / f"{icon}.png"
    if kind == "pass":
        base = f"{BASE}/game-passes/v1/universes/{U}/game-passes"
        id_key = "gamePassId"
    else:
        base = f"{BASE}/developer-products/v2/universes/{U}/developer-products"
        id_key = "productId"
    action = "aggiorna" if existing else "crea"
    print(f"  {action} {kind} {name!r} ({price} R$)")
    if dry:
        return int(existing[id_key]) if existing else 0
    with img.open("rb") as fh:
        files = dict(fields)
        files["imageFile"] = (img.name, fh, "image/png")
        if existing:
            rbxcloud._json(rbxcloud._request("PATCH", f"{base}/{existing[id_key]}", files=files, retries=4))
            return int(existing[id_key])
        data = rbxcloud._json(rbxcloud._request("POST", base, files=files, retries=4))
        return int(data[id_key])


def write_config(ids: dict[str, int]) -> None:
    s = CONFIG.read_text()
    for key, value in ids.items():
        s, n = re.subn(rf"(\t{key} = \{{ key = \"{key}\", id = )\d+", rf"\g<1>{value}", s)
        if n != 1:
            raise SystemExit(f"Voce {key} non trovata in {CONFIG}")
    CONFIG.write_text(s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ids: dict[str, int] = {}
    for kind, table in (("pass", PASSES), ("product", PRODUCTS)):
        current = list_all(kind)
        by_name = {item["name"]: item for item in current}
        probes = [item for item in current if item["name"] == "__probe__"]
        for key, (name, desc, price, icon) in table.items():
            existing = by_name.get(name)
            if existing is None and probes:
                existing = probes.pop(0)  # riusa le voci di prova invece di lasciarle in giro
            ids[key] = upsert(kind, existing, name, desc, price, icon, args.dry_run)
    if not args.dry_run:
        write_config(ids)
        print(f"id scritti in {CONFIG.relative_to(ROOT)}")
    for k, v in ids.items():
        print(f"  {k} = {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
