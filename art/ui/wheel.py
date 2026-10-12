"""Faccia della ruota della fortuna (piazza della vetta e pannello): art/out/images/WheelFace.png.

Solo gli spicchi colorati, il cerchio d'oro con le lampadine e il mozzo: icone e testi dei premi
li aggiunge il gioco sopra l'immagine (cosi' sono tradotti e mostrano gli importi del giocatore).
Gli spicchi vanno in senso orario a partire da quello in alto, nello stesso ordine e con gli
stessi colori di Plaza.Wheel.Segments in src/shared/Config/Plaza.luau.

Uso: python art/ui/wheel.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[1] / "out" / "images" / "WheelFace.png"

COLORS = [
    (255, 196, 40),  # monete
    (64, 150, 255),  # uovo
    (84, 214, 72),  # fortuna
    (255, 138, 28),  # monete+
    (170, 90, 255),  # uovo+
    (20, 196, 186),  # fortuna+
    (255, 80, 160),  # monete++
    (230, 36, 48),  # jackpot: uovo primordiale
]
OUTLINE = (29, 22, 48)
GOLD = (255, 200, 40)
GOLD_DEEP = (226, 140, 10)
GOLD_LIGHT = (255, 236, 140)

SS = 2048  # si disegna al doppio e si riduce (bordi lisci)
SIZE = 1024


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(len(a)))


def radial(size: int, inner: tuple, outer: tuple, r0: float, r1: float) -> Image.Image:
    """Sfumatura radiale RGBA dal centro: colore inner fino a r0, outer da r1 in poi."""
    c = size / 2
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for y in range(size):
        dy = y + 0.5 - c
        for x in range(size):
            d = math.hypot(x + 0.5 - c, dy)
            t = min(max((d - r0) / max(r1 - r0, 1e-6), 0.0), 1.0)
            px[x, y] = lerp(inner, outer, t)
    return img


def circle_mask(size: int, r: float) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    c = size / 2
    ImageDraw.Draw(m).ellipse((c - r, c - r, c + r, c + r), fill=255)
    return m


def main() -> None:
    S = SS
    c = S / 2
    R = S * 0.49  # bordo esterno del cerchio d'oro
    RW = R * 0.9  # raggio degli spicchi
    n = len(COLORS)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ombra morbida sotto la ruota
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((c - R, c - R + S * 0.012, c + R, c + R + S * 0.012), fill=(20, 12, 40, 150))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(S * 0.006)))

    # cerchio d'oro (bordo scuro, oro, riflesso)
    d.ellipse((c - R, c - R, c + R, c + R), fill=OUTLINE)
    rr = R - S * 0.008
    ring = radial(S // 4, GOLD_LIGHT, GOLD, S // 16, S // 8).resize((S, S), Image.BILINEAR)
    img.paste(ring, (0, 0), circle_mask(S, rr))

    # spicchi
    wedges = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wedges)
    box = (c - RW, c - RW, c + RW, c + RW)
    for i, col in enumerate(COLORS):
        mid = -90 + i * 360 / n
        wd.pieslice(box, mid - 180 / n, mid + 180 / n, fill=col)
    # luce: piu' chiaro verso il centro, piu' scuro verso il bordo
    shade = radial(S // 4, (255, 255, 255, 80), (0, 0, 0, 26), S * 0.02, RW / 4).resize((S, S), Image.BILINEAR)
    lit = wedges.copy()
    lit.alpha_composite(shade)
    lit.putalpha(ImageChops.multiply(wedges.getchannel("A"), circle_mask(S, RW)))
    d.ellipse((c - RW - S * 0.008, c - RW - S * 0.008, c + RW + S * 0.008, c + RW + S * 0.008), fill=OUTLINE)
    img.alpha_composite(lit)

    # separatori bianchi con contorno scuro
    for i in range(n):
        a = math.radians(-90 + (i + 0.5) * 360 / n)
        p0 = (c + math.cos(a) * S * 0.04, c + math.sin(a) * S * 0.04)
        p1 = (c + math.cos(a) * RW, c + math.sin(a) * RW)
        d.line((p0, p1), fill=OUTLINE, width=int(S * 0.016))
    for i in range(n):
        a = math.radians(-90 + (i + 0.5) * 360 / n)
        p0 = (c + math.cos(a) * S * 0.04, c + math.sin(a) * S * 0.04)
        p1 = (c + math.cos(a) * (RW - S * 0.004), c + math.sin(a) * (RW - S * 0.004))
        d.line((p0, p1), fill=(255, 255, 255), width=int(S * 0.008))

    # lampadine sul cerchio d'oro
    rb = (R + RW) / 2 + S * 0.002
    br = S * 0.013
    for k in range(24):
        a = math.radians(-90 + k * 15 + 7.5)
        x, y = c + math.cos(a) * rb, c + math.sin(a) * rb
        d.ellipse((x - br - S * 0.004, y - br - S * 0.004, x + br + S * 0.004, y + br + S * 0.004), fill=OUTLINE)
        col = (255, 255, 236) if k % 2 == 0 else (255, 120, 60)
        d.ellipse((x - br, y - br, x + br, y + br), fill=col)
        h = br * 0.42
        d.ellipse((x - br * 0.5 - h / 2, y - br * 0.5 - h / 2, x - br * 0.5 + h / 2, y - br * 0.5 + h / 2),
                  fill=(255, 255, 255))

    # mozzo
    hr = S * 0.075
    d.ellipse((c - hr - S * 0.008, c - hr - S * 0.008, c + hr + S * 0.008, c + hr + S * 0.008), fill=OUTLINE)
    hub = radial(S // 4, GOLD_LIGHT, GOLD_DEEP, 0, hr / 4).resize((S, S), Image.BILINEAR)
    img.paste(hub, (0, 0), circle_mask(S, hr))
    hr2 = hr * 0.55
    d.ellipse((c - hr2, c - hr2, c + hr2, c + hr2), fill=GOLD_DEEP)
    d.ellipse((c - hr2 * 0.8, c - hr2 * 0.8, c + hr2 * 0.8, c + hr2 * 0.8), fill=GOLD)
    d.ellipse((c - hr * 0.62, c - hr * 0.7, c - hr * 0.2, c - hr * 0.35), fill=(255, 250, 220))

    out = img.resize((SIZE, SIZE), Image.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUT)
    print(f"[wheel] {OUT}")


if __name__ == "__main__":
    main()
