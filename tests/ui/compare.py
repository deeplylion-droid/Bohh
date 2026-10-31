"""Confronto prima/dopo dell'interfaccia: affianca le foto delle scene (tests/ui/to_html.py) salvate
prima di un restyling (cartella "prima") a quelle attuali, in un'unica immagine da mandare.

Uso: python tests/ui/compare.py [--before DIR] [--out FILE] [scena...]
     default: prima = art/out/ui_before, dopo = art/out/ui, uscita = art/out/ui/confronto.png
Le scene che finiscono con "_phone" vanno nella sezione dei telefoni.
"""
from __future__ import annotations

import html
import subprocess
import sys
from glob import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AFTER = ROOT / "art" / "out" / "ui"
FONT = ROOT / "art" / "ui" / "fonts" / "Nunito.woff2"

LABELS = {
    "hud_busy": "HUD in gioco (valanga, evento, uovo in mano)",
    "hud": "HUD",
    "shop": "Negozio",
    "shop_boosts": "Negozio · potenziamenti",
    "upgrades": "Potenziamenti",
    "index": "Album dei pet",
    "quests": "Missioni",
    "gifts": "Regali",
    "wheel": "Ruota della fortuna",
    "settings": "Opzioni",
    "codes": "Codici",
    "hatch": "Schiusa",
    "toasts": "Messaggi e annunci",
    "tutorial": "Tutorial",
    "loading": "Caricamento",
    "hud_phone": "Telefono · HUD",
    "shop_phone": "Telefono · negozio",
    "quests_phone": "Telefono · missioni",
    "hatch_phone": "Telefono · schiusa",
    "toasts_phone": "Telefono · messaggi",
    "tutorial_phone": "Telefono · tutorial",
}
DEFAULT = ["hud_busy", "shop", "upgrades", "index", "quests", "gifts", "wheel", "hatch", "toasts", "hud_phone",
           "shop_phone", "quests_phone"]


def chromium() -> str:
    found = glob("/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell")
    if not found:
        raise SystemExit("Chromium headless non trovato")
    return found[0]


def main(argv: list[str]) -> int:
    before = ROOT / "art" / "out" / "ui_before"
    out = AFTER / "confronto.png"
    names: list[str] = []
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--before":
            before = Path(args.pop(0)).resolve()
        elif a == "--out":
            out = Path(args.pop(0)).resolve()
        else:
            names.append(a)
    names = names or DEFAULT
    rows = []
    for name in names:
        b, a = before / f"{name}.png", AFTER / f"{name}.png"
        if not b.exists() or not a.exists():
            print(f"manca la foto di {name} ({'prima' if not b.exists() else 'dopo'})")
            continue
        phone = name.endswith("_phone")
        label = html.escape(LABELS.get(name, name))
        rows.append((phone, f'<div class="row"><div class="label">{label}</div><div class="pair">'
                            f'<img src="{b.as_uri()}"><img src="{a.as_uri()}"></div></div>'))
    desktop = "".join(r for p, r in rows if not p)
    phone = "".join(r for p, r in rows if p)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: 'Nunito'; font-weight: 200 1000; src: url('{FONT.as_uri()}'); }}
body {{ margin:0; width:1360px; background:#1e164a; color:#fff; font-family:'Nunito', sans-serif; }}
.head {{ padding:28px 40px 6px; }}
h1 {{ margin:0; font-weight:900; font-size:40px; }}
.sub {{ font-weight:700; font-size:19px; color:#c9c4f2; margin-top:4px; }}
.cols {{ display:flex; gap:20px; padding:18px 40px 0; }}
.cols div {{ width:630px; font-weight:900; font-size:22px; letter-spacing:1px; }}
.cols .a {{ color:#7bf87a; }}
.cols .b {{ color:#ffb3c0; }}
h2 {{ margin:26px 40px 0; font-weight:900; font-size:26px; color:#ffd228; }}
.row {{ padding:14px 40px 4px; }}
.label {{ display:inline-block; font-weight:800; font-size:17px; background:#fff; color:#1e164a;
  border-radius:999px; padding:4px 16px; margin-bottom:8px; }}
.pair {{ display:flex; gap:20px; }}
.pair img {{ width:630px; border-radius:14px; display:block; box-shadow:0 6px 0 rgba(0,0,0,.35); }}
.foot {{ height:30px; }}
</style></head><body>
<div class="head"><h1>Climb &amp; Steal Eggs · interfaccia nuova</h1>
<div class="sub">Prima: stile "cucito" (feltro, cuciture, Denk One + Patrick Hand) → Dopo: stile "Vetta Pop"
(superfici lisce brillanti, pulsanti a pillola con bordo 3D, schede bianche, Nunito)</div></div>
<div class="cols"><div class="b">PRIMA</div><div class="a">DOPO</div></div>
{desktop}
{"<h2>Telefono</h2>" + phone if phone else ""}
<div class="foot"></div>
</body></html>"""
    page_path = out.with_suffix(".html")
    page_path.write_text(page)
    # altezza della pagina: righe del PC (16:9) e dei telefoni (844x390) piu' le intestazioni
    n_desk = sum(1 for p, _ in rows if not p)
    n_phone = len(rows) - n_desk
    height = 190 + n_desk * (630 * 720 // 1280 + 58) + (70 + n_phone * (630 * 390 // 844 + 58) if n_phone else 0) + 30
    subprocess.run([chromium(), "--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--allow-file-access-from-files", "--virtual-time-budget=4000", f"--window-size=1360,{height}",
                    f"--screenshot={out}", page_path.as_uri()], check=True, capture_output=True)
    # copia JPEG, piu' leggera da mandare
    from PIL import Image

    jpg = out.with_suffix(".jpg")
    Image.open(out).convert("RGB").save(jpg, quality=86, optimize=True)
    print(f"confronto: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out} e {jpg.name}  ({len(rows)} scene)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
