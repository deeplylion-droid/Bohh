"""Proposte di icona (512x512): composizione della toppa di feltro (concetto C) in HTML/CSS, file finali e
foglio di confronto, fotografati con Chromium headless.

Prima i render 3D (dalla cartella art/):
    nice -n 10 ../.tools/venv/bin/python promo/icon_scenes.py guardiano 1024 128 final
    nice -n 10 ../.tools/venv/bin/python promo/icon_scenes.py uovo 1024 128 final
    nice -n 10 ../.tools/venv/bin/python promo/icon_scenes.py toppa 1024 128 final
poi (dalla radice del repo): .tools/venv/bin/python art/promo/icon_compose.py [variante della toppa]
Uscita: art/out/promo/icon_proposals/icon_A_guardiano.png, icon_B_uovo.png, icon_C_toppa.png, sheet.png
(le varianti della toppa provate restano in icon_proposals/work/).

Revisione di B (uovo sulla vetta): icon_scenes.py vetta / vetta_bandiera 1024 64 final, poi
    .tools/venv/bin/python art/promo/icon_compose.py vetta
Uscita: icon_B_vetta.png, icon_B_vetta_bandiera.png e sheet_B.png (con la B attuale per confronto).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from glob import glob
from pathlib import Path

from PIL import Image, ImageFilter

ART = Path(__file__).resolve().parents[1]
FONTS = ART / "ui" / "fonts"
OUT = ART / "out" / "promo" / "icon_proposals"
WORK = OUT / "work"
BROWN = "#2A160E"
CREAM = "#FFFCF6"

# texture di feltro: rumore frattale bianco a bassa opacita' (come le proposte dell'interfaccia "cucito")
FELT = ("url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'>"
        "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' stitchTiles='stitch'/>"
        "<feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .2 0'/></filter>"
        "<rect width='200' height='200' filter='url(%23n)'/></svg>\")")
# fibre piu' grosse e scure (il feltro non e' uniforme)
FIBERS = ("url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'>"
          "<filter id='m'><feTurbulence type='fractalNoise' baseFrequency='.045' numOctaves='2' seed='7' stitchTiles='stitch'/>"
          "<feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -.9 .5'/></filter>"
          "<rect width='300' height='300' filter='url(%23m)'/></svg>\")")


def chromium() -> str:
    found = glob("/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell")
    if not found:
        raise SystemExit("Chromium non trovato")
    return sorted(found)[-1]


def shoot(html: str, png: Path, w: int, h: int) -> Path:
    src = png.with_suffix(".html")
    src.write_text(html)
    subprocess.run([chromium(), "--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--allow-file-access-from-files", "--virtual-time-budget=3000", f"--window-size={w},{h}",
                    f"--screenshot={png}", src.as_uri()], check=True, capture_output=True)
    return png


def fonts_css() -> str:
    faces = [("Denk One", "DenkOne-400.woff2"), ("Patrick Hand", "PatrickHand-400.woff2")]
    return "\n".join(f"@font-face{{font-family:'{f}';src:url({(FONTS / file).as_uri()}) format('woff2');}}" for f, file in faces)


def crop_alpha(src: Path, dst: Path, pad: int = 6) -> tuple[int, int]:
    im = Image.open(src).convert("RGBA")
    box = im.getchannel("A").point(lambda a: 255 if a > 10 else 0).getbbox()
    if box:
        box = (max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad))
        im = im.crop(box)
    im.save(dst)
    return im.size


def stitch_rect(x, y, w, h, r, color="#fff", width=6, dash=(17, 11), opacity=1.0) -> str:
    return (f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='{r}' fill='none' stroke='{color}' stroke-width='{width}' "
            f"stroke-dasharray='{dash[0]} {dash[1]}' stroke-linecap='round' opacity='{opacity}'/>")


def stitch_circle(cx, cy, r, color="#fff", width=6, dash=(17, 11)) -> str:
    return (f"<circle cx='{cx}' cy='{cy}' r='{r}' fill='none' stroke='{color}' stroke-width='{width}' "
            f"stroke-dasharray='{dash[0]} {dash[1]}' stroke-linecap='round'/>")


# ------------------------------------------------------------------------------------------ toppa (concetto C)
VARIANTS = {
    # nome: (feltro della toppa, feltro del disco dietro al soggetto, testo?, forma)
    "teal": dict(felt="#00C2AE", disc="#FFFCF6", disc_alpha=0.0, text=True, shape="square"),
    "teal_notext": dict(felt="#00C2AE", disc="#FFFCF6", disc_alpha=0.0, text=False, shape="square"),
    "navy_moon": dict(felt="#2D6BFF", disc="#FFE9A8", disc_alpha=1.0, text=True, shape="square"),
    "round": dict(felt="#00C2AE", bg="#2D6BFF", disc="#FFE9A8", disc_alpha=0.0, text=True, shape="round"),
}


def toppa_html(hero: Path, hero_size: tuple[int, int], v: dict) -> str:
    felt, text = v["felt"], v["text"]
    W = 512
    hw, hh = hero_size
    # soggetto: alto circa il 76% (con testo il soggetto sale un poco per lasciare posto all'etichetta)
    target_h = v.get("hero_h", 392 if text else 410)
    scale = target_h / hh
    w_px, h_px = hw * scale, hh * scale
    cx = W / 2 + v.get("hero_dx", 0)
    top = v.get("hero_top", 16 if text else 40)
    left = cx - w_px / 2
    svg = [f"<svg class='sv' width='{W}' height='{W}' viewBox='0 0 {W} {W}'>"]
    if v["shape"] == "square":
        svg.append(stitch_rect(20, 20, W - 40, W - 40, 46, width=5, dash=(15, 10)))
    else:
        svg.append(stitch_circle(W / 2, W / 2 + 6, 214))
    svg.append("</svg>")
    disc = ""
    if v.get("disc_alpha", 0) > 0:
        disc = (f"<div class='disc felt' style='background-color:{v['disc']}'></div>"
                f"<svg class='sv' width='{W}' height='{W}'>{stitch_circle(330, 168, 104, color=BROWN, width=4, dash=(12, 9))}</svg>")
    label = ""
    if text:
        label = ("<div class='label felt'><i class='l'></i><i class='r'></i><span>STEAL EGGS</span></div>")
    if v["shape"] == "square":
        base = f"<div class='patch felt' style='background-color:{felt}'><div class='fib'></div></div>"
    else:
        base = (f"<div class='bgfelt felt' style='background-color:{v['bg']}'><div class='fib'></div></div>"
                f"<div class='roundpatch felt' style='background-color:{felt}'><div class='fib'></div></div>")
    snow = "".join(f"<i class='flake' style='left:{x}px;top:{y}px;width:{s}px;height:{s}px'></i>"
                   for x, y, s in v.get("flakes", []))
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'><style>{fonts_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{W}px;overflow:hidden;background:{BROWN}}}
.felt{{background-image:{FELT}}}
.fib{{position:absolute;inset:0;border-radius:inherit;background-image:{FIBERS};opacity:.12;mix-blend-mode:multiply}}
.patch{{position:absolute;left:9px;top:9px;width:{W - 18}px;height:{W - 18}px;border-radius:56px;
  box-shadow:inset 0 -10px 0 rgba(0,0,0,.10), inset 0 8px 0 rgba(255,255,255,.10)}}
.bgfelt{{position:absolute;inset:0}}
.roundpatch{{position:absolute;left:{W / 2 - 236}px;top:{W / 2 - 230}px;width:472px;height:472px;border-radius:50%;
  border:9px solid {BROWN};box-shadow:0 8px 0 {BROWN}}}
.sv{{position:absolute;left:0;top:0}}
.disc{{position:absolute;left:{330 - 112}px;top:{168 - 112}px;width:224px;height:224px;border-radius:50%;border:6px solid {BROWN}}}
.flake{{position:absolute;border-radius:50%;background:#fff;opacity:.9}}
.shadow{{position:absolute;left:{cx - w_px * 0.36}px;top:{top + h_px * 0.94}px;width:{w_px * 0.72}px;height:{h_px * 0.085}px;
  border-radius:50%;background:{BROWN};opacity:.45;filter:blur(5px)}}
.hero{{position:absolute;left:{left}px;top:{top}px;width:{w_px}px;height:{h_px}px;filter:drop-shadow(0 0 0 {BROWN})}}
.label{{position:absolute;left:50%;bottom:30px;transform:translateX(-50%) rotate(-3deg);height:86px;padding:0 40px;
  background-color:{CREAM};border:6px solid {BROWN};border-radius:10px;box-shadow:0 8px 0 {BROWN};white-space:nowrap}}
.label span{{display:block;font-family:'Denk One';font-size:54px;line-height:74px;color:{BROWN};letter-spacing:1px}}
.label i{{position:absolute;top:10px;bottom:10px;width:0;border-left:4px dashed {BROWN}}}
.label i.l{{left:10px}}.label i.r{{right:10px}}
</style></head><body>{base}{''.join(svg)}{disc}{snow}<div class='shadow'></div>
<img class='hero' src='{hero.as_uri()}'>{label}</body></html>"""


def make_toppa(variant: str, hero_png: Path) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    cropped = WORK / f"{hero_png.stem}_crop.png"
    size = crop_alpha(hero_png, cropped)
    v = VARIANTS[variant]
    out = WORK / f"toppa_{variant}.png"
    shoot(toppa_html(cropped, size, v), out, 512, 512)
    small = Image.open(out).convert("RGB").resize((150, 150), Image.LANCZOS)
    small.save(WORK / f"toppa_{variant}_150.png")
    return out


# ------------------------------------------------------------------------------------------ foglio di confronto
def sheet(icons: list[tuple[str, str, Path]], name: str = "sheet",
          title: str = "Climb &amp; Steal Eggs &mdash; proposte di icona") -> Path:
    cols = []
    for code, label, p in icons:
        cols.append(f"""<div class='col'><div class='h'>{code} &middot; {label}</div>
<img class='big' src='{p.as_uri()}'>
<div class='row'><div class='sm light'><img src='{p.as_uri()}'><span>150 px</span></div>
<div class='sm dark'><img src='{p.as_uri()}'><span>150 px</span></div>
<div class='sm tiny light'><img src='{p.as_uri()}'><span>64 px</span></div></div></div>""")
    W, H = 3 * 512 + 4 * 32, 890
    html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><style>{fonts_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;background:#ece7df;font-family:'Patrick Hand';color:{BROWN}}}
.t{{font-family:'Denk One';font-size:34px;padding:22px 32px 6px}}
.note{{font-size:20px;padding:0 32px;color:#6B5240}}
.wrap{{display:flex;gap:32px;padding:10px 32px}}
.col{{width:512px}}
.h{{font-family:'Denk One';font-size:24px;margin-bottom:10px}}
.big{{width:512px;height:512px;display:block}}
.row{{display:flex;gap:18px;margin-top:16px;align-items:flex-end}}
.sm{{padding:12px;border-radius:14px;text-align:center;font-size:18px}}
.sm img{{width:150px;height:150px;display:block;border-radius:14px}}
.tiny img{{width:64px;height:64px;border-radius:8px}}
.light{{background:#ffffff}}.dark{{background:#191b1d;color:#bbb}}
</style></head><body><div class='t'>{title}</div><div class='note'>Ogni icona a 512 px (file vero) e ridotta a 150 px e 64 px con gli angoli arrotondati come nelle schede di Roblox, su sfondo chiaro e scuro.</div><div class='wrap'>{''.join(cols)}</div></body></html>"""
    shot = shoot(html, WORK / f"{name}.png", W, H)
    out = OUT / f"{name}.png"
    shutil.copy(shot, out)
    return out


def downscale(src: Path, dst: Path):
    im = Image.open(src).convert("RGB")
    if im.size != (512, 512):
        im = im.resize((512, 512), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    im.save(dst)


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    variant = argv[0] if argv else "teal"
    if variant == "vetta":
        # revisione di B: l'uovo-mostro sulla punta di un picco (con e senza bandierina di vetta)
        finals = [("B", "attuale", OUT / "icon_B_uovo.png", None),
                  ("B", "vetta", OUT / "icon_B_vetta.png", WORK / "vetta_final_512.png"),
                  ("B", "vetta con bandierina", OUT / "icon_B_vetta_bandiera.png", WORK / "vetta_bandiera_final_512.png")]
        for _, _, dst, src in finals:
            if src is not None:
                downscale(src, dst)
        print("[icone]", sheet([(code, title, dst) for code, title, dst, _ in finals], name="sheet_B",
                               title="Chi c'&egrave; dentro? &mdash; revisione: l'uovo sulla vetta"))
        return 0
    hero = WORK / (argv[1] if len(argv) > 1 else "toppa_hero_final.png")
    if variant == "all":
        for name in VARIANTS:
            print("[toppa]", make_toppa(name, hero))
        return 0
    c = make_toppa(variant, hero)
    if len(argv) > 2 and argv[2] == "only":
        print("[toppa]", c)
        return 0
    a, b = WORK / "guardiano_final_512.png", WORK / "uovo_final_512.png"
    finals = [("A", "Il guardiano", OUT / "icon_A_guardiano.png", a), ("B", "Chi c'è dentro?", OUT / "icon_B_uovo.png", b),
              ("C", "Toppa cucita", OUT / "icon_C_toppa.png", c)]
    for _, _, dst, src in finals:
        downscale(src, dst)
    print("[icone]", sheet([(code, title, dst) for code, title, dst, _ in finals]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
