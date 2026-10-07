"""Atlante 4x4 di texture procedurali (512x512) condiviso da tutti i modelli. Richiede numpy."""
import numpy as np

TILE = 128
TILES = 4

NAMES = [
    "bark_pine", "bark_gray", "bark_birch", "needles_dark",
    "needles_mid", "leaves", "moss", "rock",
    "wood_cut", "metal", "plastic", "camo",
    "skin", "wood_warm", "rubber", "fern",
]
T = {name: i for i, name in enumerate(NAMES)}

rng = np.random.default_rng(7)


def value_noise(size, cells, seed):
    """Rumore a valori periodico (si ripete ai bordi della cella)."""
    g = np.random.default_rng(seed).random((cells + 1, cells + 1))
    g[-1, :] = g[0, :]
    g[:, -1] = g[:, 0]
    coords = np.linspace(0, cells, size, endpoint=False)
    i = coords.astype(int)
    f = coords - i
    f = f * f * (3 - 2 * f)
    y0, x0 = np.meshgrid(i, i, indexing="ij")
    fy, fx = np.meshgrid(f, f, indexing="ij")
    a = g[y0, x0]
    b = g[y0, x0 + 1]
    c = g[y0 + 1, x0]
    d = g[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(size, base, octaves, seed, sx=1, sy=1):
    out = np.zeros((size, size))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        n = value_noise(size, base * 2 ** o, seed + o)
        if sx != 1 or sy != 1:
            n = stretch(value_noise(size, base * 2 ** o, seed + o), sx, sy)
        out += n * amp
        total += amp
        amp *= 0.5
    return out / total


def stretch(n, sx, sy):
    """Allunga il rumore lungo un asse campionando a passo diverso (venature)."""
    size = n.shape[0]
    ys = (np.arange(size) * sy).astype(int) % size
    xs = (np.arange(size) * sx).astype(int) % size
    return n[np.ix_(ys, xs)]


def mix(c1, c2, t):
    c1 = np.array(c1, dtype=float)
    c2 = np.array(c2, dtype=float)
    return c1[None, None, :] * (1 - t[..., None]) + c2[None, None, :] * t[..., None]


def tile(name, seed):
    s = TILE
    if name == "bark_pine":
        n = fbm(s, 4, 4, seed)
        streak = stretch(value_noise(s, 16, seed + 10), 4, 1)
        t = np.clip(n * 0.6 + streak * 0.6, 0, 1)
        img = mix((38, 26, 18), (92, 66, 46), t)
        cracks = streak < 0.25
        img[cracks] *= 0.45
    elif name == "bark_gray":
        n = fbm(s, 4, 4, seed)
        streak = stretch(value_noise(s, 12, seed + 3), 5, 1)
        img = mix((52, 50, 46), (118, 112, 102), np.clip(n * 0.5 + streak * 0.6, 0, 1))
        img[streak < 0.22] *= 0.5
    elif name == "bark_birch":
        n = fbm(s, 4, 3, seed)
        img = mix((175, 170, 158), (226, 222, 210), n)
        marks = stretch(value_noise(s, 8, seed + 5), 1, 6) > 0.72
        img[marks] = img[marks] * 0.2 + np.array([20, 18, 16]) * 0.8
    elif name in ("needles_dark", "needles_mid", "fern"):
        base = {"needles_dark": ((10, 24, 14), (34, 58, 30)), "needles_mid": ((20, 40, 20), (52, 80, 38)), "fern": ((26, 52, 22), (70, 104, 42))}[name]
        n = fbm(s, 8, 4, seed)
        fine = value_noise(s, 64, seed + 2)
        img = mix(base[0], base[1], np.clip(n * 0.7 + fine * 0.5 - 0.1, 0, 1))
    elif name == "leaves":
        n = fbm(s, 6, 4, seed)
        fine = value_noise(s, 48, seed + 9)
        img = mix((30, 44, 18), (86, 92, 36), np.clip(n * 0.6 + fine * 0.5 - 0.1, 0, 1))
    elif name == "moss":
        n = fbm(s, 6, 4, seed)
        img = mix((34, 48, 20), (78, 96, 40), n)
    elif name == "rock":
        n = fbm(s, 4, 5, seed)
        speck = value_noise(s, 64, seed + 4)
        img = mix((58, 58, 60), (128, 126, 122), np.clip(n * 0.8 + speck * 0.3, 0, 1))
    elif name == "wood_cut":
        yy, xx = np.mgrid[0:s, 0:s] / s - 0.5
        r = np.sqrt(xx ** 2 + yy ** 2) + fbm(s, 4, 3, seed) * 0.05
        rings = (np.sin(r * 90) + 1) / 2
        img = mix((120, 88, 58), (176, 138, 96), rings)
    elif name == "metal":
        n = stretch(value_noise(s, 32, seed), 1, 8)
        img = mix((38, 40, 44), (70, 72, 76), n)
    elif name == "plastic":
        n = fbm(s, 8, 3, seed)
        img = mix((16, 17, 19), (34, 35, 38), n)
    elif name == "camo":
        a = fbm(s, 3, 3, seed)
        b = fbm(s, 3, 3, seed + 50)
        img = np.zeros((s, s, 3))
        img[:] = (78, 72, 48)
        img[a > 0.55] = (44, 52, 30)
        img[b > 0.6] = (32, 26, 18)
        img *= (0.85 + value_noise(s, 32, seed + 3)[..., None] * 0.3)
    elif name == "skin":
        n = fbm(s, 4, 5, seed)
        veins = np.abs(fbm(s, 6, 3, seed + 20) - 0.5) < 0.025
        img = mix((150, 145, 138), (214, 208, 198), n)
        img[veins] = img[veins] * 0.6 + np.array([90, 70, 90]) * 0.4
        blotch = fbm(s, 3, 3, seed + 40) > 0.62
        img[blotch] *= 0.8
    elif name == "wood_warm":
        grain = stretch(fbm(s, 6, 3, seed), 1, 6)
        img = mix((70, 42, 22), (128, 82, 44), grain)
    elif name == "rubber":
        n = fbm(s, 16, 2, seed)
        img = mix((14, 14, 14), (28, 28, 28), n)
    else:
        img = np.full((s, s, 3), 128.0)
    return np.clip(img, 0, 255)


def build_atlas():
    atlas = np.zeros((TILE * TILES, TILE * TILES, 4), dtype=np.uint8)
    for i, name in enumerate(NAMES):
        tx, ty = i % TILES, i // TILES
        atlas[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE, :3] = tile(name, 100 + i * 7).astype(np.uint8)
        atlas[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE, 3] = 255
    return atlas
