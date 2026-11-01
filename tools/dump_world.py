"""Esporta le parti del mondo costruito su un server vero (tests/cloud/dump_world.luau) in un JSON per
tests/render_world.py. Compila e carica il luogo come versione salvata (non pubblicata), a meno di
--version N.

Uso: .tools/venv/bin/python tools/dump_world.py [--version N] [--out art/out/world.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cloud_test  # noqa: E402
import rbxcloud  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int)
    ap.add_argument("--out", default="art/out/world.json")
    args = ap.parse_args()
    version = args.version or cloud_test.build()
    print(f"versione: {version}")
    script = (ROOT / "tests" / "cloud" / "dump_world.luau").read_text()
    r = rbxcloud.run_luau(script, version=version, timeout_s=290, poll_timeout=900)
    if r["state"] != "COMPLETE" or not r["results"]:
        print(f"stato: {r['state']}  errore: {r['error']}")
        print("\n".join((r["logs"] or [])[-30:]))
        return 1
    data = json.loads(r["results"][0])
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data))
    print(f"{data['count']} parti -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
