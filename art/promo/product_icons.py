"""Icone dei prodotti dei giganti galattici (finestra d'acquisto di Roblox): il render 3/4 del pet su
un cielo cosmico con stelle. Uso: python art/promo/product_icons.py  ->  art/out/images/<Id>.png
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "art" / "out" / "images"
PETS = ("NebulaLion", "StarKraken", "CosmicWhale")
SIZE = 512


def sky(seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:SIZE, 0:SIZE] / SIZE
    # gradiente blu notte -> viola, con una nebulosa morbida
    r = 30 + 90 * y + 60 * np.exp(-((x - 0.7) ** 2 + (y - 0.3) ** 2) / 0.06)
    g = 20 + 30 * y + 20 * np.exp(-((x - 0.3) ** 2 + (y - 0.6) ** 2) / 0.05)
    b = 80 + 120 * (1 - y) + 80 * np.exp(-((x - 0.3) ** 2 + (y - 0.6) ** 2) / 0.05)
    img = Image.fromarray(np.dstack([r, g, b]).clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    d = ImageDraw.Draw(img)
    for _ in range(140):
        sx, sy = rng.uniform(0, SIZE, 2)
        s = rng.uniform(0.6, 2.4)
        a = int(rng.uniform(120, 255))
        d.ellipse((sx - s, sy - s, sx + s, sy + s), fill=(255, 255, 255, a))
    # qualche stella a quattro punte
    for _ in range(6):
        sx, sy = rng.uniform(30, SIZE - 30, 2)
        s = rng.uniform(6, 12)
        for ang in (0, math.pi / 2):
            dx, dy = math.cos(ang) * s, math.sin(ang) * s
            d.line((sx - dx, sy - dy, sx + dx, sy + dy), fill=(255, 255, 230, 220), width=2)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for i, pet in enumerate(PETS):
        src = ROOT / "art" / "out" / "pet" / pet / f"{pet}_3q.png"
        if not src.exists():
            print(f"[icone] manca il render di {pet}")
            continue
        im = Image.open(src).convert("RGBA")
        # ritaglia sul contenuto (alpha) e mette il pet grande al centro
        bbox = im.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox() or (0, 0, im.width, im.height)
        im = im.crop(bbox)
        k = (SIZE * 0.86) / max(im.width, im.height)
        im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
        base = sky(17 + i)
        glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((SIZE * 0.12, SIZE * 0.12, SIZE * 0.88, SIZE * 0.88), fill=(200, 160, 255, 90))
        base.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
        base.alpha_composite(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2 + 10))
        base.convert("RGB").save(OUT / f"{pet}.png")
        print(f"[icone] {OUT / f'{pet}.png'}")


if __name__ == "__main__":
    main()
