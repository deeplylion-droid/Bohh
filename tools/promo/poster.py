"""Immagini di presentazione della pagina dell'esperienza (miniatura 1920x1080 e icona 512x512).
Bosco notturno procedurale con nebbia, fascio di torcia, sagoma di The Rake ricavata dal render del
modello 3D e titolo. Uso: python3 poster.py sagoma.png cartella_uscita"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

rng = np.random.default_rng(7)
FONT_TITLE = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_SUB = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"


def lerp(a, b, t):
    return a + (b - a) * t


def pine(draw, x, ground, h, w, jag):
    """Pino: tronco e palchi triangolari frastagliati."""
    draw.rectangle([x - w * 0.05, ground - h * 0.25, x + w * 0.05, ground], fill=255)
    tiers = 9
    for i in range(tiers):
        t = i / (tiers - 1)
        top = ground - h + h * 0.82 * t
        half = w * (0.12 + 0.5 * t) * (0.85 + rng.random() * 0.3)
        y0 = top + h * 0.03
        pts = [(x, ground - h + h * 0.82 * t - h * 0.1)]
        n = 7
        for k in range(n + 1):
            u = k / n
            px = x + half * (u * 2 - 1)
            py = y0 + h * 0.13 + (rng.random() - 0.5) * jag * h * 0.04
            pts.append((px, py))
        draw.polygon(pts, fill=255)


def forest_layer(W, H, ground, count, hmin, hmax, clear=None):
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    xs = np.sort(rng.uniform(-100, W + 100, count))
    for x in xs:
        if clear and clear[0] < x < clear[1]:
            continue  # radura: lascia vedere la creatura
        h = rng.uniform(hmin, hmax)
        g = ground + rng.uniform(-0.01, 0.02) * H
        pine(d, x, g, h, h * rng.uniform(0.32, 0.42), 1.0)
    d.rectangle([0, ground + 0.01 * H, W, H], fill=255)
    return np.asarray(img, dtype=np.float32) / 255.0


def creature_mask(path):
    """Sagoma di profilo (seconda vista del render): maschera + ombreggiatura originale."""
    im = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    crop = im[:, 470:760]
    mask = np.clip((crop - 40) / 30, 0, 1)
    ys, xs = np.nonzero(mask > 0.5)
    crop, mask = crop[ys.min():ys.max() + 1, xs.min():xs.max() + 1], mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return mask, crop / 255.0


def compose(W, H, sil, out, title_scale=1.0, creature_x=0.66, creature_h=0.62, icon=False):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u, v = xx / W, yy / H
    # cielo notturno con alone di luna
    sky_top, sky_low = np.array([4, 6, 10]), np.array([22, 30, 34])
    img = lerp(sky_top, sky_low, (v ** 1.4)[..., None])
    mx, my = 0.8 * W, 0.12 * H
    moon = np.exp(-(((xx - mx) ** 2 + (yy - my) ** 2) / (2 * (0.18 * H) ** 2)))
    img += moon[..., None] * np.array([38, 46, 52])
    disc = np.clip(1 - np.sqrt((xx - mx) ** 2 + (yy - my) ** 2) / (0.035 * H), 0, 1) ** 0.3
    img = lerp(img, np.array([205, 210, 200]), disc[..., None] * 0.85)

    fog_col = np.array([46, 58, 60])
    # fascio della torcia: dal basso a sinistra (il giocatore) verso la creatura
    cx = creature_x * W
    src = np.array([0.02 * W, 1.05 * H])
    aim = np.array([cx, 0.72 * H]) - src
    aim /= np.linalg.norm(aim)
    rel = np.stack([xx - src[0], yy - src[1]], -1)
    dist = np.linalg.norm(rel, axis=-1) + 1e-3
    cosang = (rel @ aim) / dist
    beam = np.clip((cosang - 0.94) / 0.06, 0, 1) ** 1.6 * np.exp(-dist / (1.4 * W))

    # strati del bosco, dal più lontano al più vicino, con nebbia che sale dal suolo
    layers = [
        (0.70, 70, 0.20 * H, 0.38 * H, 0.80),
        (0.74, 55, 0.28 * H, 0.50 * H, 0.62),
        (0.79, 40, 0.38 * H, 0.66 * H, 0.42),
        (0.86, 22, 0.55 * H, 0.95 * H, 0.18),
        (0.97, 9, 0.90 * H, 1.40 * H, 0.03),
    ]
    sil_mask, sil_shade = sil
    for li, (ground, count, hmin, hmax, fogness) in enumerate(layers):
        if icon:
            count = max(4, count // 3)
        clear = None
        if li >= 2:
            half = (0.16 if li == 2 else 0.30 if li == 3 else 0.42) * W * (1.3 if icon else 1)
            clear = (cx - half, cx + half)
        m = forest_layer(W, H, ground * H, count, hmin, hmax, clear)
        m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2 if li < 3 else 0.6)), dtype=np.float32) / 255
        col = lerp(np.array([3, 4, 5]), fog_col, fogness)
        col_img = col + beam[..., None] * np.array([120, 115, 95]) * fogness * 1.4
        img = lerp(img, col_img, m[..., None])
        # nebbia bassa tra uno strato e l'altro
        band = np.exp(-((v - ground) / 0.05) ** 2) * 0.35 * (1 - li / len(layers))
        img = lerp(img, fog_col * 1.1, band[..., None])
        if li == 2:
            # la creatura sta tra il terzo e il quarto strato
            sh, sw = sil_mask.shape
            th = int(creature_h * H)
            tw = int(sw * th / sh)
            mk = np.asarray(Image.fromarray((sil_mask * 255).astype(np.uint8)).resize((tw, th), Image.LANCZOS), dtype=np.float32) / 255
            sd = np.asarray(Image.fromarray((sil_shade * 255).astype(np.uint8)).resize((tw, th), Image.LANCZOS), dtype=np.float32) / 255
            x0 = int(cx - tw / 2)
            y0 = int(0.83 * H - th)
            full = np.zeros((H, W), np.float32)
            shade = np.zeros((H, W), np.float32)
            xa, xb = max(0, x0), min(W, x0 + tw)
            ya, yb = max(0, y0), min(H, y0 + th)
            full[ya:yb, xa:xb] = mk[ya - y0:yb - y0, xa - x0:xb - x0]
            shade[ya:yb, xa:xb] = sd[ya - y0:yb - y0, xa - x0:xb - x0]
            lit = np.clip(beam * 2.2, 0, 1)
            # in penombra: solo il fascio la rischiara, dall'alto sfuma nel buio e nella nebbia
            fade = np.clip((yy - y0) / th, 0, 1)
            body = np.array([8, 8, 8]) + (shade[..., None] * np.array([150, 144, 128])) * (0.06 + 0.55 * lit[..., None] * (0.35 + 0.65 * fade[..., None]))
            body = lerp(body, fog_col * 0.7, 0.18)
            img = lerp(img, body, full[..., None])
            # occhi: due punti luminosi sul muso (lato sinistro, in alto)
            rows = np.nonzero(mk.max(1) > 0.5)[0]
            top = rows.min()
            head_rows = mk[top:top + int(th * 0.08)]
            hx = np.nonzero(head_rows.max(0) > 0.5)[0].min()
            ex, ey = x0 + hx + tw * 0.07, y0 + top + th * 0.045
            for k, off in enumerate((0, tw * 0.035)):
                r2 = (xx - (ex + off)) ** 2 + (yy - ey) ** 2
                core = np.exp(-r2 / (2 * (0.0035 * H) ** 2))
                halo = np.exp(-r2 / (2 * (0.022 * H) ** 2))
                img += (core[..., None] * np.array([255, 210, 190]) + halo[..., None] * np.array([200, 25, 12]) * 0.55) * (1.0 if k == 0 else 0.75)
    # alone del fascio nell'aria
    img += beam[..., None] * np.array([70, 68, 58])

    # vignettatura, grana, leggera dominante fredda
    vig = 1 - 0.75 * np.clip(((u - 0.5) ** 2 + (v - 0.5) ** 2) * 2.2, 0, 1) ** 1.3
    img *= vig[..., None]
    img += rng.normal(0, 5.5, (H, W, 1))
    img = np.clip(img, 0, 255).astype(np.uint8)
    pil = Image.fromarray(img)

    # titolo
    d = ImageDraw.Draw(pil)
    if icon:
        f1 = ImageFont.truetype(FONT_TITLE, int(H * 0.15))
        text = "THE RAKE"
        tw_ = d.textlength(text, font=f1)
        tx, ty = (W - tw_) / 2, H * 0.80
        glow = Image.new("L", pil.size, 0)
        ImageDraw.Draw(glow).text((tx, ty), text, font=f1, fill=255)
        glow = glow.filter(ImageFilter.GaussianBlur(H * 0.02))
        pil = Image.composite(Image.new("RGB", pil.size, (120, 8, 6)), pil, glow.point(lambda p: int(p * 0.8)))
        d = ImageDraw.Draw(pil)
        d.text((tx, ty), text, font=f1, fill=(226, 220, 204))
    else:
        f1 = ImageFont.truetype(FONT_TITLE, int(H * 0.15 * title_scale))
        f2 = ImageFont.truetype(FONT_SUB, int(H * 0.042 * title_scale))
        tx, ty = W * 0.06, H * 0.10
        glow = Image.new("L", pil.size, 0)
        ImageDraw.Draw(glow).text((tx, ty), "THE RAKE", font=f1, fill=255)
        glow = glow.filter(ImageFilter.GaussianBlur(H * 0.018))
        pil = Image.composite(Image.new("RGB", pil.size, (120, 8, 6)), pil, glow.point(lambda p: int(p * 0.75)))
        d = ImageDraw.Draw(pil)
        d.text((tx, ty), "THE RAKE", font=f1, fill=(226, 220, 204))
        sub = "C A C C I A   N E I   B O S C H I"
        d.text((tx + H * 0.006, ty + H * 0.19 * title_scale), sub, font=f2, fill=(190, 30, 22))
        f3 = ImageFont.truetype(FONT_SUB, int(H * 0.028))
        d.text((tx + H * 0.006, ty + H * 0.26 * title_scale), "Horror cooperativo  ·  2-6 giocatori  ·  Prima persona", font=f3, fill=(150, 156, 150))
    pil.save(out)


if __name__ == "__main__":
    sil = creature_mask(sys.argv[1])
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    compose(1920, 1080, sil, os.path.join(out, "miniatura_1920x1080.png"))
    compose(512, 512, sil, os.path.join(out, "icona_512x512.png"), creature_x=0.5, creature_h=0.7, icon=True)
    print("ok")
