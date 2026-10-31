"""Texture della corrente per le rapide del Percorso Estremo: strisce di schiuma bianca allungate
(si ripetono in entrambe le direzioni), con trasparenza. Il client le fa scorrere sull'acqua e sulle
cascate (Texture.OffsetStudsU/V).

Uso: python art/env/water_flow.py  ->  art/out/images/WaterFlow.png
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parents[2] / "art" / "out" / "images"
SIZE = 256


def blur_wrap(a: np.ndarray, rx: int, ry: int) -> np.ndarray:
    """Media mobile con bordi che si ripetono (rx lungo x, ry lungo y)."""
    out = a.copy()
    if rx:
        acc = np.zeros_like(a)
        for d in range(-rx, rx + 1):
            acc += np.roll(a, d, axis=1)
        out = acc / (2 * rx + 1)
    if ry:
        acc = np.zeros_like(out)
        for d in range(-ry, ry + 1):
            acc += np.roll(out, d, axis=0)
        out = acc / (2 * ry + 1)
    return out


def main() -> None:
    rng = np.random.default_rng(11)
    # rumore allungato lungo x: strisce di corrente
    base = rng.random((SIZE, SIZE))
    streaks = blur_wrap(base, 22, 1)
    streaks = (streaks - streaks.min()) / (streaks.max() - streaks.min())
    # macchie di schiuma piu' corte
    foam = blur_wrap(rng.random((SIZE, SIZE)), 6, 2)
    foam = (foam - foam.min()) / (foam.max() - foam.min())
    v = np.clip((streaks - 0.55) * 3.2, 0, 1) * 0.75 + np.clip((foam - 0.62) * 4, 0, 1) * 0.5
    alpha = (np.clip(v, 0, 1) * 220).astype(np.uint8)
    white = np.full((SIZE, SIZE), 255, np.uint8)
    img = Image.fromarray(np.dstack([white, white, white, alpha]), "RGBA")
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / "WaterFlow.png")
    print(f"[water] {OUT / 'WaterFlow.png'}")


if __name__ == "__main__":
    main()
