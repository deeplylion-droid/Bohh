"""Immagini dello stile "cucito" dell'interfaccia: trama del feltro e cuciture tratteggiate bianche
(ricolorabili con ImageColor3), disegnate a 4x per restare nitide.

- FeltNoise: trama da ripetere (ScaleType Tile) sopra i colori pieni, con ImageTransparency alta.
- StitchH / StitchV: un tratto di cucitura da ripetere sui lati (tile 16x4 / 4x16 px).
- StitchCorner<R>: quarto di cerchio tratteggiato per l'angolo in alto a sinistra di un riquadro
  con UICorner di raggio R px (gli altri angoli si ottengono ruotando l'immagine).
- StitchRing: anello tratteggiato per i pulsanti rotondi (disegnato per un diametro di 100 px).
Il centro della cucitura sta a STITCH_IN px dal bordo, attaccato al contorno scuro esterno.

Uso: python art/ui/felt_images.py  ->  art/out/images/*.png
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[2] / "art" / "out" / "images"
K = 4  # sovracampionamento
THICK = 3.0  # spessore della cucitura (px a schermo)
STITCH_IN = 2.5  # distanza del centro della cucitura dal bordo del riquadro (px)
PERIOD = 14.0  # tratto + spazio (px)
DASH = 8.5  # lunghezza del tratto (px)
CORNERS = (8, 12, 16, 20, 28, 40)


def dash_tile(vertical: bool) -> Image.Image:
    w, h = 16 * K, 4 * K
    im = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    y0, y1 = (h - THICK * K) / 2, (h + THICK * K) / 2
    x0 = (16 - DASH) / 2 * K
    d.rounded_rectangle((x0, y0, x0 + DASH * K, y1), radius=THICK * K / 2, fill=(255, 255, 255, 255))
    return im.rotate(90, expand=True) if vertical else im


def arc_dashes(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, a0: float, a1: float, n: int):
    """n tratti lungo l'arco (gradi, senso antiorario nell'immagine) di raggio r (px gia' scalati)."""
    span = a1 - a0
    step = span / n
    dash_deg = step * (DASH / PERIOD)
    for i in range(n):
        start = a0 + i * step + (step - dash_deg) / 2
        pts = []
        for t in np.linspace(start, start + dash_deg, 12):
            a = math.radians(t)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        draw.line(pts, fill=(255, 255, 255, 255), width=int(THICK * K), joint="curve")
        for px, py in (pts[0], pts[-1]):
            rr = THICK * K / 2
            draw.ellipse((px - rr, py - rr, px + rr, py + rr), fill=(255, 255, 255, 255))


def corner(radius: int) -> Image.Image:
    size = radius * K
    im = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    r = (radius - STITCH_IN) * K
    arc = math.pi / 2 * (radius - STITCH_IN)
    n = max(1, round(arc / PERIOD))
    # angolo in alto a sinistra: centro dell'arco nell'angolo in basso a destra dell'immagine
    arc_dashes(d, size, size, r, 180, 270, n)
    return im


def ring(diameter: int = 100) -> Image.Image:
    size = diameter * K
    im = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    r = (diameter / 2 - STITCH_IN) * K
    n = max(6, round(2 * math.pi * (diameter / 2 - STITCH_IN) / PERIOD))
    arc_dashes(d, size / 2, size / 2, r, 0, 360, n)
    return im


def felt_noise(size: int = 128, seed: int = 7) -> Image.Image:
    rng = np.random.default_rng(seed)
    v = rng.random((size, size))
    # pelo del feltro: puntini chiari e scuri, piu' una leggera variazione a macchie
    blur = np.zeros_like(v)
    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            blur += np.roll(np.roll(rng.random((size, size)), dx, 0), dy, 1)
    blur /= 25
    tone = np.where(v > 0.5, 255, 0).astype(np.uint8)
    alpha = (np.abs(v - 0.5) * 2 * 150 + (blur - 0.5) * 120).clip(0, 255).astype(np.uint8)
    rgba = np.dstack([tone, tone, tone, alpha])
    return Image.fromarray(rgba, "RGBA")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dash_tile(False).save(OUT / "StitchH.png")
    dash_tile(True).save(OUT / "StitchV.png")
    for r in CORNERS:
        corner(r).save(OUT / f"StitchCorner{r}.png")
    ring().save(OUT / "StitchRing.png")
    felt_noise().save(OUT / "FeltNoise.png")
    print(f"[felt] immagini in {OUT}")


if __name__ == "__main__":
    main()
