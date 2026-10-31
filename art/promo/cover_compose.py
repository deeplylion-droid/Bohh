"""Titoli delle copertine (1920x1080): il render 3D di promo/covers.py come sfondo e il titolo in lettere da
cartone (Luckiest Guy) con riempimento a gradiente, contorno scuro spesso, ombra piena "estrusa" sotto e un'ombra
morbida per staccarlo dallo sfondo, come le miniature di prima; fotografati con Chromium (promo/shoot.sh).
Poi il foglio con tutte le copertine e le prove in piccolo (480x270, come si vedono nella pagina del gioco).

Uso (dalla radice del repository, dopo i render finali di covers.py):
    .tools/venv/bin/python art/promo/cover_compose.py                 # tutte, dai render "final"
    .tools/venv/bin/python art/promo/cover_compose.py --tag b2 cover_1 # una sola, da un render di prova
Uscita: art/promo/final/cover_1.png ... cover_4.png e covers_sheet.png; le pagine HTML e le prove 480x270 in
art/out/promo/covers/compose/.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from PIL import Image

ART = Path(__file__).resolve().parents[1]
PROMO = ART / "promo"
WORK = ART / "out" / "promo" / "covers" / "work"
COMP = ART / "out" / "promo" / "covers" / "compose"
FINAL = PROMO / "final"
INK = "#1d1630"
W, H = 1920, 1080

GOLD = "linear-gradient(#fffbd0 0%, #ffe14a 42%, #ffb01f 78%, #ff8a14 100%)"
CYAN = "linear-gradient(#ffffff 0%, #c9fbff 30%, #4fe3ff 70%, #16a8ff 100%)"
PINK = "linear-gradient(#fff0f8 0%, #ffb3dc 35%, #ff5fae 75%, #ff2f86 100%)"
FIRE = "linear-gradient(#fffbd0 0%, #ffe14a 38%, #ff9a1f 72%, #ff4d1a 100%)"

# per ogni copertina: scena e tag del render, righe del titolo (testo, dimensione), gradiente, posizione/rotazione
COVERS = {
    "cover_1": dict(scene="steal", lines=[("STEAL THE", 136), ("EGGS!", 228)], grad=GOLD,
                    box="left:40px;top:190px;width:680px;", rot=-5),
    "cover_2": dict(scene="giants", lines=[("HATCH GIANT", 140), ("PETS!", 210)], grad=GOLD,
                    box="left:50px;top:36px;width:900px;", rot=-4),
    "cover_3": dict(scene="extreme", lines=[("EXTREME", 180), ("TRAIL!", 180)], grad=CYAN,
                    box="left:0;right:0;top:52px;", rot=-3, inline=True),
    "cover_4": dict(scene="hatch", lines=[("HATCH", 166), ("MONSTERS!", 166)], grad=FIRE,
                    box="left:0;right:0;top:46px;", rot=-3, inline=True),
}


def css() -> str:
    return f"""
@font-face {{ font-family: Luckiest; src: url('{(PROMO / "luckiest-guy-latin-400-normal.woff2").as_uri()}'); }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
body {{ position: relative; font-family: Luckiest; }}
.bg {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
.title {{ position: absolute; text-align: center; white-space: nowrap;
  filter: drop-shadow(0 18px 22px rgba(10, 4, 30, .55)); }}
.title .t {{ position: relative; display: block; line-height: .9; }}
.title .back, .title .front {{ display: block; }}
.title .front {{ position: relative; }}
.title .back {{ position: absolute; left: 0; right: 0; top: 0; color: {INK}; }}
.title span {{ display: block; }}
.title.inline span {{ display: inline; }}
"""


def title(lines, grad, box, rot, inline=False, stroke=14, depth=16) -> str:
    """Testo gommoso a strati: dietro il contorno spesso con l'ombra piena (estrusa), davanti il gradiente.
    Il gradiente si ripete per ogni riga (o parola, se inline)."""
    def spans(front: bool):
        out = []
        for i, (text, size) in enumerate(lines):
            style = f"font-size:{size}px;"
            if front:
                style += f"background-image:{grad};-webkit-background-clip:text;background-clip:text;color:transparent;"
            # spazio fra le parole sulla stessa riga (stessa dimensione della parola)
            sep = f'<span style="font-size:{size}px">&nbsp;</span>' if inline and i < len(lines) - 1 else ""
            out.append(f'<span style="{style}">{text}</span>{sep}')
        return "".join(out)

    back_style = f"-webkit-text-stroke:{stroke * 2}px {INK};text-shadow:0 {depth}px 0 {INK}, 0 {depth + 2}px 0 {INK}"
    cls = "title inline" if inline else "title"
    return (f'<div class="{cls}" style="{box}transform:rotate({rot}deg);"><div class="t">'
            f'<div class="back" style="{back_style}">{spans(False)}</div>'
            f'<div class="front">{spans(True)}</div></div></div>')


def page(bg: Path, body: str) -> str:
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{css()}</style></head><body>'
            f'<img class="bg" src="{bg.as_uri()}">{body}</body></html>')


def shoot(html: str, name: str, out: Path) -> Path:
    COMP.mkdir(parents=True, exist_ok=True)
    src = COMP / f"{name}.html"
    src.write_text(html, encoding="utf-8")
    subprocess.run(["bash", str(PROMO / "shoot.sh"), str(src), str(out), str(W), str(H)], check=True)
    return out


def background(scene: str, tag: str) -> Path:
    """Il render post-prodotto della scena, portato a 1920x1080 se e' una prova piu' piccola."""
    src = WORK / f"{scene}_{tag}_post.png"
    im = Image.open(src).convert("RGB")
    if im.size != (W, H):
        dst = COMP / f"{scene}_{tag}_bg.png"
        COMP.mkdir(parents=True, exist_ok=True)
        im.resize((W, H), Image.LANCZOS).save(dst)
        return dst
    return src


def sheet(paths: list[Path], out: Path, cols: int = 2, gap: int = 24) -> Path:
    ims = [Image.open(p).convert("RGB").resize((W // 2, H // 2), Image.LANCZOS) for p in paths]
    rows = (len(ims) + cols - 1) // cols
    sw = cols * (W // 2) + (cols + 1) * gap
    sh = rows * (H // 2) + (rows + 1) * gap
    s = Image.new("RGB", (sw, sh), (24, 20, 40))
    for i, im in enumerate(ims):
        r, c = divmod(i, cols)
        s.paste(im, (gap + c * (W // 2 + gap), gap + r * (H // 2 + gap)))
    s.save(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("covers", nargs="*", default=list(COVERS))
    ap.add_argument("--tag", default="final")
    ap.add_argument("--out", default=None, help="cartella di uscita (predefinita: art/promo/final per i 'final')")
    args = ap.parse_args()
    out_dir = Path(args.out) if args.out else (FINAL if args.tag == "final" else COMP)
    out_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for name in args.covers:
        c = COVERS[name]
        bg = background(c["scene"], args.tag)
        html = page(bg, title(c["lines"], c["grad"], c["box"], c["rot"], c.get("inline", False)))
        out = shoot(html, name if args.tag == "final" else f"{name}_{args.tag}", out_dir / (
            f"{name}.png" if args.tag == "final" else f"{name}_{args.tag}.png"))
        small = COMP / f"{out.stem}_480.png"
        Image.open(out).convert("RGB").resize((480, 270), Image.LANCZOS).save(small)
        done.append(out)
        print(f"[compose] {out}  (prova piccola: {small})")
    if args.tag == "final" and len(args.covers) == len(COVERS):
        print(f"[compose] {sheet([out_dir / f'{n}.png' for n in COVERS], out_dir / 'covers_sheet.png')}")
    elif len(done) > 1:
        print(f"[compose] {sheet(done, COMP / f'sheet_{args.tag}.png')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
