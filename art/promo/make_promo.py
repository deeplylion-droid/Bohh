"""Icona (512x512) e miniature (1920x1080) del gioco: render dei pet e delle uova composti in HTML su uno
sfondo di montagne sfaccettate disegnato in SVG, fotografati con Chromium headless.

Prima: ../.tools/venv/bin/python promo/render_heroes.py ... (dalla cartella art/), poi dalla radice:
    .tools/venv/bin/python art/promo/make_promo.py
Uscita: art/promo/final/icon.png, thumbnail_1.png, thumbnail_2.png, thumbnail_3.png
"""
from __future__ import annotations

import math
import random
import subprocess
from glob import glob
from pathlib import Path

from PIL import Image

ART = Path(__file__).resolve().parents[1]
PROMO = ART / "promo"
RENDERS = ART / "out" / "promo"
CROP = RENDERS / "crop"
FINAL = PROMO / "final"
ICONS = ART / "out" / "images"
INK = "#1d1630"


# ------------------------------------------------------------------------------------------ immagini
def crop(name: str) -> str:
    """Render ritagliato sulla sagoma (con un piccolo margine), come URI file://."""
    src = RENDERS / f"{name}.png"
    if not src.exists():
        src = ICONS / f"{name}.png"
    dst = CROP / f"{name}.png"
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        im = Image.open(src).convert("RGBA")
        box = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        if box:
            pad = 8
            box = (max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad))
            im = im.crop(box)
        CROP.mkdir(parents=True, exist_ok=True)
        im.save(dst)
    return dst.as_uri()


def size_of(name: str) -> tuple[int, int]:
    crop(name)
    with Image.open(CROP / f"{name}.png") as im:
        return im.size


# ------------------------------------------------------------------------------------------ sfondo
def ridge(w: float, base: float, n: int, hmin: float, hmax: float, rng: random.Random):
    """Creste alternate valle/picco da sinistra a destra (fuori dai bordi per non lasciare buchi)."""
    pts = []
    step = (w + 400) / n
    x = -200.0
    for _ in range(n):
        pts.append((x + rng.uniform(0.0, 0.15) * step, base - rng.uniform(0.15, 0.4) * hmin))
        pts.append((x + rng.uniform(0.4, 0.6) * step, base - rng.uniform(hmin, hmax)))
        x += step
    pts.append((w + 200, base - rng.uniform(0.15, 0.4) * hmin))
    return pts


def mountains_svg(w: int, h: int, layers, seed: int = 7, trail: bool = False) -> str:
    """Catene di montagne low-poly: faccia in luce, faccia in ombra, neve con il bordo frastagliato."""
    rng = random.Random(seed)
    out = []
    for li, (base, n, hmin, hmax, lit, shade, snow, snow_shade) in enumerate(layers):
        pts = ridge(w, base, n, hmin, hmax, rng)
        poly = [(-200, h + 10)] + pts + [(w + 200, h + 10)]
        out.append(f'<polygon points="{" ".join(f"{x:.0f},{y:.0f}" for x, y in poly)}" fill="{lit}"/>')
        for i in range(1, len(pts) - 1, 2):
            (vx0, vy0), (px, py), (vx1, vy1) = pts[i - 1], pts[i], pts[i + 1]
            # faccia in ombra: dal picco alla valle destra e giu' fino alla base
            foot = (px + (vx1 - px) * 0.25, h + 10)
            out.append(f'<polygon points="{px:.0f},{py:.0f} {vx1:.0f},{vy1:.0f} {vx1:.0f},{h + 10} {foot[0]:.0f},{foot[1]}" '
                       f'fill="{shade}"/>')
            # spigolo intermedio: una seconda sfaccettatura piu' chiara sul lato in luce
            mid = (px - (px - vx0) * 0.45, py + (vy0 - py) * 0.62)
            out.append(f'<polygon points="{px:.0f},{py:.0f} {mid[0]:.0f},{mid[1]:.0f} {px - (px - vx0) * 0.15:.0f},{h + 10}" '
                       f'fill="{lit}" opacity="0.0"/>')
            if snow:
                k = rng.uniform(0.3, 0.42)
                left = (px + (vx0 - px) * k, py + (vy0 - py) * k)
                right = (px + (vx1 - px) * k, py + (vy1 - py) * k)
                jag = [left]
                m = 5
                for j in range(1, m):
                    t = j / m
                    x = left[0] + (right[0] - left[0]) * t
                    y = left[1] + (right[1] - left[1]) * t + (rng.uniform(10, 34) if j % 2 else rng.uniform(-14, 4))
                    jag.append((x, y))
                jag.append(right)
                cap = [(px, py)] + jag
                out.append(f'<polygon points="{" ".join(f"{x:.0f},{y:.0f}" for x, y in cap)}" fill="{snow}"/>')
                # meta' destra della neve in ombra
                sh = [(px, py)] + [p for p in jag if p[0] >= px] + [(px + (right[0] - px) * 0.2, (py + right[1]) / 2 + 30)]
                out.append(f'<polygon points="{" ".join(f"{x:.0f},{y:.0f}" for x, y in sh)}" fill="{snow_shade}"/>')
        if trail and li == len(layers) - 2:
            # sentiero a tornanti sulla montagna di mezzo
            px, py = max(((x, y) for x, y in pts[1::2] if w * 0.35 < x < w * 0.65), key=lambda p: -p[1], default=(w / 2, base - hmax))
            zig = []
            yb = base + 40
            for k2 in range(7):
                t = k2 / 6
                y = yb + (py + 40 - yb) * t
                half = (1 - t) * 260 + 30
                zig.append((px + (half if k2 % 2 else -half), y))
            d = " ".join(f"{x:.0f},{y:.0f}" for x, y in zig)
            out.append(f'<polyline points="{d}" fill="none" stroke="#8a6a4a" stroke-width="16" stroke-linejoin="round" '
                       f'stroke-linecap="round" opacity="0.9"/>')
            out.append(f'<polyline points="{d}" fill="none" stroke="#c9a77c" stroke-width="8" stroke-linejoin="round" '
                       f'stroke-linecap="round"/>')
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">{"".join(out)}</svg>'


def snow_dots(w: int, h: int, n: int, seed: int) -> str:
    rng = random.Random(seed)
    dots = []
    for _ in range(n):
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(2, 6)
        dots.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="#fff" opacity="{rng.uniform(0.5, 0.95):.2f}"/>')
    return f'<svg class="layer" width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">{"".join(dots)}</svg>'


def rays(cx: float, cy: float, n: int, color: str, opacity: float, size: int) -> str:
    wedges = []
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = a0 + math.pi / n
        x0, y0 = cx + size * math.cos(a0), cy + size * math.sin(a0)
        x1, y1 = cx + size * math.cos(a1), cy + size * math.sin(a1)
        wedges.append(f'<polygon points="{cx:.0f},{cy:.0f} {x0:.0f},{y0:.0f} {x1:.0f},{y1:.0f}" fill="{color}"/>')
    return f'<g opacity="{opacity}">{"".join(wedges)}</g>'


def ground_svg(w: int, h: int, top: float, seed: int) -> str:
    """Primo piano innevato con rocce appuntite."""
    rng = random.Random(seed)
    pts = [(0, top + rng.uniform(-10, 10))]
    for i in range(1, 9):
        pts.append((w * i / 8, top + rng.uniform(-28, 18)))
    poly = [(0, h)] + pts + [(w, h)]
    out = [f'<polygon points="{" ".join(f"{x:.0f},{y:.0f}" for x, y in poly)}" fill="#eaf3ff"/>',
           f'<polygon points="0,{top + 60} {w},{top + 40} {w},{h} 0,{h}" fill="#d7e6fb"/>']
    for _ in range(9):
        x = rng.choice([rng.uniform(0, w * 0.18), rng.uniform(w * 0.82, w)])
        s = rng.uniform(40, 120)
        y = top + rng.uniform(10, 80)
        tip = (x + rng.uniform(-0.2, 0.2) * s, y - s * rng.uniform(0.9, 1.5))
        a, b = (x - s * 0.55, y + 10), (x + s * 0.6, y + 10)
        out.append(f'<polygon points="{a[0]:.0f},{a[1]:.0f} {tip[0]:.0f},{tip[1]:.0f} {b[0]:.0f},{b[1]:.0f}" fill="#6b7290"/>')
        out.append(f'<polygon points="{tip[0]:.0f},{tip[1]:.0f} {b[0]:.0f},{b[1]:.0f} {x + s * 0.1:.0f},{y + 10:.0f}" fill="#4a4f6b"/>')
        out.append(f'<polygon points="{tip[0]:.0f},{tip[1]:.0f} {tip[0] - s * 0.18:.0f},{tip[1] + s * 0.35:.0f} '
                   f'{tip[0] + s * 0.12:.0f},{tip[1] + s * 0.3:.0f}" fill="#f4f8ff"/>')
    return f'<svg class="layer" width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">{"".join(out)}</svg>'


LAYERS = [
    # base, picchi, altezza min/max, luce, ombra, neve, neve in ombra
    (620, 6, 260, 420, "#a9b8e8", "#8d9bd1", "#f2f6ff", "#cfd9f5"),
    (760, 5, 260, 420, "#7d88c4", "#626cab", "#f6f9ff", "#c3cdee"),
    (900, 4, 220, 330, "#5b5f9e", "#474a84", "#ffffff", "#c8d2f0"),
]


# ------------------------------------------------------------------------------------------ pagine
def css(w: int, h: int) -> str:
    return f"""
@font-face {{ font-family: Luckiest; src: url('{(PROMO / "luckiest-guy-latin-400-normal.woff2").as_uri()}'); }}
@font-face {{ font-family: Fredoka; src: url('{(PROMO / "fredoka-one-latin-400-normal.woff2").as_uri()}'); }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {w}px; height: {h}px; overflow: hidden; }}
body {{ position: relative; background: linear-gradient(#3f8cff 0%, #7cc0ff 45%, #cfe9ff 70%); font-family: Luckiest; }}
.layer {{ position: absolute; left: 0; top: 0; }}
.pet {{ position: absolute; transform: translate(-50%, -100%); }}
.pet img {{ display: block; width: 100%; height: auto; }}
.outlined img {{ filter: drop-shadow(0 0 0 {INK}) drop-shadow(5px 0 0 {INK}) drop-shadow(-5px 0 0 {INK})
  drop-shadow(0 5px 0 {INK}) drop-shadow(0 -5px 0 {INK}) drop-shadow(0 14px 10px rgba(20, 10, 40, .35)); }}
.shadow {{ position: absolute; border-radius: 50%; background: radial-gradient(rgba(40, 40, 90, .45), rgba(40, 40, 90, 0) 70%);
  transform: translate(-50%, -50%); }}
.glow {{ position: absolute; border-radius: 50%; transform: translate(-50%, -50%); }}
.title {{ position: absolute; white-space: nowrap; text-align: center; }}
.title .t {{ position: relative; display: block; line-height: .92; }}
.title .back > span, .title .front > span {{ display: block; }}
.title .back {{ position: absolute; left: 0; right: 0; top: 0; color: {INK}; }}
.title .front {{ position: relative; -webkit-background-clip: text; background-clip: text; color: transparent; }}
.ribbon {{ position: absolute; font-family: Luckiest; color: #fff; white-space: nowrap; border-radius: 22px; border: 7px solid {INK};
  box-shadow: 0 9px 0 {INK}; text-shadow: 0 4px 0 rgba(29, 22, 48, .5); }}
"""


def title(text: str, size: int, gradient: str, stroke: int, depth: int, extra: str = "") -> str:
    """Testo gommoso: contorno spesso e scuro, ombra solida sotto, riempimento a gradiente."""
    lines = text.split("|")
    back = "".join(f"<span>{ln}</span>" for ln in lines)
    # il gradiente si ripete su ogni riga (non sfuma da una riga all'altra)
    front = "".join(f'<span style="background-image:{gradient};-webkit-background-clip:text;background-clip:text;'
                    f'color:transparent">{ln}</span>' for ln in lines)
    return (f'<div class="title" style="font-size:{size}px;{extra}"><div class="t">'
            f'<div class="back" style="-webkit-text-stroke:{stroke * 2}px {INK};text-shadow:0 {depth}px 0 {INK}">{back}</div>'
            f'<div class="front">{front}</div></div></div>')


def pet(name: str, x: float, y: float, width: float, flip: bool = False, z: int = 5, outline: bool = True,
        rot: float = 0.0, shadow: bool = True) -> str:
    uri = crop(name)
    w, h = size_of(name)
    height = width * h / w
    tf = f"translate(-50%, -100%) rotate({rot}deg)" + (" scaleX(-1)" if flip else "")
    sh = (f'<div class="shadow" style="left:{x}px;top:{y - height * 0.02}px;width:{width * 0.9}px;height:{width * 0.2}px;'
          f'z-index:{z - 1}"></div>') if shadow else ""
    return (sh + f'<div class="pet{" outlined" if outline else ""}" style="left:{x}px;top:{y}px;width:{width}px;'
            f'transform:{tf};z-index:{z}"><img src="{uri}"></div>')


def glow(x, y, r, inner, outer="rgba(255,255,255,0)", z=2) -> str:
    return (f'<div class="glow" style="left:{x}px;top:{y}px;width:{2 * r}px;height:{2 * r}px;'
            f'background:radial-gradient({inner} 0%, {outer} 70%);z-index:{z}"></div>')


def page(w: int, h: int, body: str, bg: str = "") -> str:
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{css(w, h)}</style></head>'
            f'<body style="{bg}">{body}</body></html>')


GOLD = "linear-gradient(#fff7a8 0%, #ffd83d 45%, #ffa51f 100%)"
WHITE = "linear-gradient(#ffffff 0%, #ffffff 55%, #d5e4ff 100%)"
PINK = "linear-gradient(#ffd0e8 0%, #ff6fb3 55%, #ff2f7e 100%)"
CYAN = "linear-gradient(#e6fffd 0%, #7ff4ff 50%, #2bb8ff 100%)"
RED = "linear-gradient(#ffd2c2 0%, #ff6a55 50%, #e11d3a 100%)"


def icon() -> str:
    W = H = 512
    body = [
        f'<svg class="layer" width="{W}" height="{H}">{rays(256, 250, 18, "#ffffff", 0.16, 520)}</svg>',
        mountains_svg(W, H, [(470, 3, 170, 240, "#8fa0e0", "#6f7cc0", "#f6f9ff", "#cfd9f5"),
                             (540, 3, 120, 170, "#5b5f9e", "#474a84", "#ffffff", "#c8d2f0")], seed=3)
        .replace("<svg ", '<svg class="layer" '),
        glow(196, 330, 170, "rgba(255,226,90,.95)", z=3),
        pet("Yeti_3q", 352, 500, 300, z=5),
        pet("EggLegendary_3q", 170, 492, 190, z=6, rot=-10),
        title("STEAL|EGGS!", 92, GOLD, 9, 9, "left:0;right:0;top:16px;transform:rotate(-4deg);z-index:9"),
    ]
    bg = "background: radial-gradient(circle at 50% 42%, #ffb347 0%, #ff7a3d 38%, #c43ad6 78%, #5b2bb0 100%);"
    return page(W, H, "".join(body), bg)


def thumb_title() -> str:
    W, H = 1920, 1080
    body = [
        f'<svg class="layer" width="{W}" height="{H}">{rays(960, 380, 22, "#ffffff", 0.12, 1400)}</svg>',
        mountains_svg(W, H, LAYERS, seed=11).replace("<svg ", '<svg class="layer" '),
        snow_dots(W, H, 70, 5),
        ground_svg(W, H, 870, 4),
        glow(960, 860, 300, "rgba(255,230,110,.9)", z=3),
        pet("EggLegendary_3q", 960, 1000, 300, z=7),
        pet("EggMythic_3q", 790, 1010, 190, z=6, rot=-8),
        pet("EggEpic_3q", 1130, 1012, 190, z=6, rot=8),
        pet("FoxKit_3q", 470, 1040, 400, z=8),
        pet("Yeti_3q", 1480, 1040, 450, flip=True, z=8),
        pet("Chick_3q", 250, 1060, 230, z=9),
        pet("Unicorn_3q", 1730, 1065, 300, flip=True, z=9),
        title("CLIMB & STEAL|EGGS!", 168, GOLD, 13, 16, "left:0;right:0;top:40px;transform:rotate(-2.5deg);z-index:12"),
    ]
    return page(W, H, "".join(body))


def thumb_hatch() -> str:
    W, H = 1920, 1080
    body = [
        f'<svg class="layer" width="{W}" height="{H}">{rays(960, 620, 26, "#ffe9a8", 0.22, 1600)}</svg>',
        glow(960, 640, 560, "rgba(255,245,200,.95)", "rgba(255,180,60,0)", z=2),
        pet("UovissimoImperatore_3q", 960, 860, 420, z=8),
        pet("Phoenix_3q", 560, 820, 360, z=7),
        pet("TortelloneCosmico_3q", 1370, 830, 390, flip=True, z=7),
        pet("GelatoneMontagnone_3q", 250, 1000, 270, z=9),
        pet("LavaDragon_3q", 1680, 1010, 330, flip=True, z=9),
    ]
    eggs = ["EggCommon_3q", "EggUncommon_3q", "EggRare_3q", "EggEpic_3q", "EggLegendary_3q", "EggMythic_3q",
            "EggDivine_3q", "EggSecret_3q"]
    for i, e in enumerate(eggs):
        x = 520 + i * 126
        body.append(pet(e, x, 1060, 104 + i * 4, z=10, shadow=False))
    body.append(title("HATCH RARE|PETS!", 176, PINK, 13, 16, "left:0;right:0;top:36px;transform:rotate(-2deg);z-index:12"))
    # etichette vicino ai pet giusti: Gelatone (mitico) a sinistra, Tortellone (segreto) a destra
    body.append(f'<div class="ribbon" style="left:120px;top:560px;font-size:46px;padding:8px 26px;background:#ff4f8b;'
                f'transform:rotate(-8deg);z-index:11">MYTHIC</div>')
    body.append(f'<div class="ribbon" style="left:1250px;top:330px;font-size:46px;padding:8px 26px;background:#8a3dff;'
                f'transform:rotate(7deg);z-index:11">SECRET</div>')
    body.append(f'<div class="ribbon" style="left:820px;top:330px;font-size:40px;padding:6px 22px;background:#ffb21f;'
                f'transform:rotate(-3deg);z-index:11">37 PETS</div>')
    bg = "background: radial-gradient(circle at 50% 58%, #ffcf6b 0%, #ff7d4f 32%, #b8379f 62%, #3b1f7a 100%);"
    return page(W, H, "".join(body), bg)


def thumb_steal() -> str:
    W, H = 1920, 1080
    laser = "".join(
        f'<div style="position:absolute;left:1180px;top:{y}px;width:640px;height:18px;border-radius:9px;'
        f'background:#ff3550;box-shadow:0 0 22px 8px rgba(255,40,70,.75);z-index:6"></div>' for y in (560, 660, 760, 860))
    posts = "".join(
        f'<div style="position:absolute;left:{x}px;top:520px;width:44px;height:420px;border-radius:12px;background:#4a4f6b;'
        f'border:6px solid {INK};z-index:7"></div>' for x in (1160, 1800))
    body = [
        mountains_svg(W, H, LAYERS, seed=21).replace("<svg ", '<svg class="layer" '),
        snow_dots(W, H, 60, 9),
        ground_svg(W, H, 880, 12),
        laser, posts,
        pet("IconAlarm", 1822, 545, 150, z=9, shadow=False),
        glow(700, 820, 300, "rgba(255,226,90,.85)", z=3),
        pet("FoxKit_3q", 640, 1040, 520, z=8),
        pet("EggLegendary_3q", 930, 900, 230, z=9, rot=18),
        pet("Chick_3q", 1500, 1050, 300, flip=True, z=9),
        pet("IconThief", 230, 330, 210, z=9, shadow=False),
        title("STEAL THEIR|EGGS!", 172, RED, 13, 16, "left:0;right:0;top:34px;transform:rotate(-2.5deg);z-index:12"),
    ]
    body.append(f'<div class="ribbon" style="right:150px;top:250px;font-size:52px;padding:8px 30px;background:#2bb8ff;'
                f'transform:rotate(5deg);z-index:11">PROTECT YOURS!</div>')
    return page(W, H, "".join(body))


def chromium() -> str:
    found = glob("/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell")
    if not found:
        raise SystemExit("Chromium headless non trovato")
    return found[0]


def shoot(name: str, html: str, w: int, h: int) -> Path:
    FINAL.mkdir(parents=True, exist_ok=True)
    src = RENDERS / f"{name}.html"
    src.write_text(html)
    out = FINAL / f"{name}.png"
    subprocess.run([chromium(), "--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--allow-file-access-from-files", "--virtual-time-budget=4000", f"--window-size={w},{h}",
                    f"--screenshot={out}", src.as_uri()], check=True, capture_output=True)
    print(f"[promo] {out.relative_to(ART.parent)}")
    return out


def thumb_ultra() -> str:
    """I 5 giganti Ultra, con un pet normale davanti per far capire quanto sono enormi."""
    W, H = 1920, 1080
    body = [
        f'<svg class="layer" width="{W}" height="{H}">{rays(960, 700, 30, "#ff3a6a", 0.18, 1700)}</svg>',
        glow(960, 760, 620, "rgba(255,120,80,.75)", "rgba(120,20,80,0)", z=2),
        pet("PentaDragon_3q", 960, 900, 760, z=6),
        pet("TitanRex_3q", 420, 960, 560, z=7),
        pet("ThunderGriffin_3q", 1500, 950, 560, flip=True, z=7),
        pet("InfernoKomodo_3q", 330, 1075, 520, z=9),
        pet("VenomWidow_3q", 1590, 1075, 520, flip=True, z=9),
        pet("EggUltra_3q", 960, 1065, 170, z=10),
        pet("Chick_3q", 1110, 1068, 62, z=11),
        title("ULTRA|GIANTS!", 178, RED, 13, 16, "left:0;right:0;top:30px;transform:rotate(-2deg);z-index:12"),
    ]
    body.append(f'<div class="ribbon" style="left:1280px;top:330px;font-size:56px;padding:8px 30px;background:#ffb21f;'
                f'transform:rotate(6deg);z-index:11">10x BIGGER!</div>')
    bg = "background: radial-gradient(circle at 50% 62%, #ff9a5a 0%, #e0336a 30%, #6a1a7a 62%, #1a0a2e 100%);"
    return page(W, H, "".join(body), bg)


def thumb_summit() -> str:
    """La vetta vera (render del mondo dal server, tests/render_world.py promo con TRANSPARENT=1):
    gli 8 lotti e i giganti sui troni, con cielo e montagne dietro."""
    W, H = 1920, 1080
    world = ART / "out" / "world" / "promo.png"
    far = [
        (760, 7, 260, 400, "#b9c6ee", "#9eacdb", "#f4f7ff", "#d5ddf5"),
        (820, 6, 200, 330, "#8f9bd2", "#7581bd", "#f8faff", "#ccd5f0"),
    ]
    body = [
        f'<svg class="layer" width="{W}" height="{H}">{rays(960, 120, 24, "#ffffff", 0.10, 1500)}</svg>',
        mountains_svg(W, H, far, seed=5).replace("<svg ", '<svg class="layer" '),
        snow_dots(W, 560, 50, 3),
        f'<img class="layer" src="{world.as_uri()}" style="width:{W}px;height:{H}px;z-index:5">',
        title("RULE THE|SUMMIT!", 150, GOLD, 12, 14, "left:0;right:0;top:26px;transform:rotate(-2deg);z-index:12"),
    ]
    body.append(f'<div class="ribbon" style="right:120px;top:120px;font-size:46px;padding:8px 28px;background:#ff3a6a;'
                f'transform:rotate(6deg);z-index:11">GIANTS ON YOUR BASE!</div>')
    return page(W, H, "".join(body))


PAGES = {
    "icon": (icon, 512, 512),
    "thumbnail_1": (thumb_title, 1920, 1080),
    "thumbnail_2": (thumb_hatch, 1920, 1080),
    "thumbnail_3": (thumb_steal, 1920, 1080),
    "thumbnail_4": (thumb_ultra, 1920, 1080),
    "thumbnail_5": (thumb_summit, 1920, 1080),
}


def main(argv: list[str]) -> int:
    for name in argv or list(PAGES):
        fn, w, h = PAGES[name]
        shoot(name, fn(), w, h)
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
