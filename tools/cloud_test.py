"""Compila il luogo, lo carica come versione salvata (non pubblicata) ed esegue un test Luau.

Uso: python tools/cloud_test.py tests/cloud/boot_test.luau [--no-build] [--version N]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import rbxcloud  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def build() -> int:
    out = ROOT / "build" / "ClimbAndStealEggs.rbxl"
    out.parent.mkdir(exist_ok=True)
    subprocess.run([str(ROOT / ".tools/bin/rojo"), "build", str(ROOT / "default.project.json"), "-o", str(out)], check=True)
    return rbxcloud.publish_place(out, "Saved")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--version", type=int)
    ap.add_argument("--timeout", type=int, default=290)
    args = ap.parse_args()
    version = args.version
    if not args.no_build:
        version = build()
        print(f"versione salvata: {version}")
    script = Path(args.script).read_text()
    r = rbxcloud.run_luau(script, version=version, timeout_s=args.timeout, poll_timeout=args.timeout + 600)
    print(f"stato: {r['state']}  errore: {r['error']}")
    for res in r["results"] or []:
        print(res)
    if r["logs"]:
        print("--- log ---")
        print("\n".join(r["logs"][-60:]))
    return 0 if r["state"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
