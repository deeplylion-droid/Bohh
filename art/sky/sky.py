"""Cielo pastello per lo Sky di Roblox: art/out/images/SkySide.png (le 4 facce laterali, uguali),
SkyUp.png e SkyDn.png, 1024x1024.

Il colore dipende solo dall'altezza sull'orizzonte: le facce combaciano qualunque sia il loro
orientamento. Le nuvole vere le disegnano Terrain.Clouds e il mare di nuvole sotto la montagna.
"""
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parents[1] / "out" / "images"
SIZE = 1024

# (elevazione in gradi, colore RGB) dal basso verso l'alto
STOPS = [
    (-90, (196, 214, 246)),
    (-8, (226, 236, 255)),
    (0, (255, 226, 238)),   # bagliore rosa all'orizzonte
    (6, (236, 226, 255)),   # lavanda
    (18, (176, 210, 255)),
    (45, (118, 178, 255)),
    (90, (84, 150, 252)),   # azzurro intenso allo zenit
]


def color_at(elev_deg: np.ndarray) -> np.ndarray:
    xs = np.array([s[0] for s in STOPS], dtype=np.float64)
    out = np.zeros(elev_deg.shape + (3,))
    for c in range(3):
        ys = np.array([s[1][c] for s in STOPS], dtype=np.float64)
        out[..., c] = np.interp(elev_deg, xs, ys)
    return out


def face(kind: str) -> Image.Image:
    v, u = np.mgrid[-1:1:SIZE * 1j, -1:1:SIZE * 1j]
    if kind == "side":
        elev = np.degrees(np.arctan2(-v, np.sqrt(u * u + 1)))
    elif kind == "up":
        elev = np.degrees(np.arctan2(1, np.sqrt(u * u + v * v)))
    else:
        elev = np.degrees(np.arctan2(-1, np.sqrt(u * u + v * v)))
    rgb = color_at(elev)
    # leggero rumore per evitare le fasce di colore (banding) nei gradienti
    rng = np.random.default_rng(7)
    rgb += rng.uniform(-1.2, 1.2, rgb.shape)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    face("side").save(OUT / "SkySide.png")
    face("up").save(OUT / "SkyUp.png")
    face("down").save(OUT / "SkyDn.png")
    print("cielo salvato in", OUT)


if __name__ == "__main__":
    main()
