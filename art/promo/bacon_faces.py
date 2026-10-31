"""Facce disegnate del "bacon hair" (copiate da Recolor, deeplylion-droid/Roblox-Max,
recolor/tools/store/faces.py): Pillow a 1024 x 1024 su fondo trasparente, per il davanti della testa.
Occhi grandi con i riflessi e bocca spalancata, come le facce degli avatar nelle icone dei giochi piu'
giocati di Roblox.

  python art/promo/bacon_faces.py [CARTELLA]      scrive excited.png e shocked.png (art/cache/bacon/faces)
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

INK = (24, 18, 40, 255)
WHITE = (255, 255, 255, 255)
MOUTH = (120, 20, 40, 255)
TONGUE = (255, 96, 130, 255)
TEETH = (255, 255, 255, 255)
CHEEK = (255, 120, 140, 110)
SIZE = 1024
SS = 2  # drawn twice as large, then shrunk: smooth edges


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (SIZE * SS, SIZE * SS), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def s(*values: float) -> list[float]:
    return [v * SS for v in values]


def eye(draw, cx, cy, rx, ry, look=(0.0, 0.0), pupil=0.62):
    draw.ellipse(s(cx - rx - 14, cy - ry - 14, cx + rx + 14, cy + ry + 14), fill=INK)
    draw.ellipse(s(cx - rx, cy - ry, cx + rx, cy + ry), fill=WHITE)
    px, py = cx + look[0] * rx * 0.3, cy + look[1] * ry * 0.3
    pr = rx * pupil
    draw.ellipse(s(px - pr, py - pr * 1.08, px + pr, py + pr * 1.08), fill=INK)
    draw.ellipse(s(px - pr * 0.55 - pr * 0.28, py - pr * 0.62 - pr * 0.28, px - pr * 0.55 + pr * 0.28, py - pr * 0.62 + pr * 0.28), fill=WHITE)
    draw.ellipse(s(px + pr * 0.3 - pr * 0.12, py + pr * 0.2 - pr * 0.12, px + pr * 0.3 + pr * 0.12, py + pr * 0.2 + pr * 0.12), fill=WHITE)


def brow(draw, points, width=34):
    draw.line([v * SS for xy in points for v in xy], fill=INK, width=width * SS, joint="curve")
    for x, y in (points[0], points[-1]):
        draw.ellipse(s(x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=INK)


def finish(image: Image.Image, cheeks: bool = True) -> Image.Image:
    if cheeks:
        blush = Image.new("RGBA", image.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(blush)
        for cx in (250, 774):
            d.ellipse(s(cx - 80, 590, cx + 80, 660), fill=CHEEK)
        blush = blush.filter(ImageFilter.GaussianBlur(18 * SS))
        image = Image.alpha_composite(blush, image)
    return image.resize((SIZE, SIZE), Image.LANCZOS)


def excited() -> Image.Image:
    """Big happy eyes looking ahead and a huge open grin: the noob loving the paint."""
    image, draw = canvas()
    eye(draw, 330, 420, 118, 150, look=(0.25, -0.1))
    eye(draw, 694, 420, 118, 150, look=(0.25, -0.1))
    brow(draw, [(220, 222), (330, 186), (430, 214)])
    brow(draw, [(594, 214), (694, 186), (804, 222)])
    # The grin: a wide D, the teeth on top, the tongue at the bottom.
    box = s(250, 560, 774, 900)
    draw.chord(box, 0, 180, fill=INK)
    inner = s(276, 586, 748, 868)
    draw.chord(inner, 0, 180, fill=MOUTH)
    draw.rectangle(s(300, 736, 724, 776), fill=TEETH)
    draw.ellipse(s(400, 770, 640, 880), fill=TONGUE)
    return finish(image)


def shocked() -> Image.Image:
    """Eyes wide open, tiny pupils and a round open mouth: the Greyling's fright, or the egg's."""
    image, draw = canvas()
    eye(draw, 330, 410, 128, 160, pupil=0.36)
    eye(draw, 694, 410, 128, 160, pupil=0.36)
    brow(draw, [(214, 196), (330, 150), (440, 190)])
    brow(draw, [(584, 190), (694, 150), (810, 196)])
    draw.ellipse(s(402, 610, 622, 880), fill=INK)
    draw.ellipse(s(424, 632, 600, 858), fill=MOUTH)
    draw.ellipse(s(450, 760, 574, 850), fill=TONGUE)
    return finish(image, cheeks=False)


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "cache" / "bacon" / "faces")
    out.mkdir(parents=True, exist_ok=True)
    excited().save(out / "excited.png")
    shocked().save(out / "shocked.png")
    print(f"faces in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
