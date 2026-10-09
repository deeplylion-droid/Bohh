"""Disegna in HTML le scene esportate da tests/ui/render_ui.luau e le fotografa con Chromium headless.

Riproduce le regole di impaginazione di Roblox che usa l'interfaccia (UDim2, AnchorPoint, UIListLayout,
UIGridLayout, UIPadding, UIScale, ScrollingFrame, TextScaled...) e disegna sopra una sagoma
approssimativa dell'interfaccia di Roblox (barra in alto, chat, elenco giocatori, barra degli strumenti,
comandi touch) per vedere le sovrapposizioni.

Uso: python tests/ui/to_html.py [scena...]   (default: tutte le scene in art/out/ui/*.json)
Uscita: art/out/ui/<scena>.html e <scena>.png, piu' art/out/ui/contact.png con tutte le scene.
"""
from __future__ import annotations

import html
import json
import math
import re
import subprocess
import sys
from glob import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "art" / "out" / "ui"
FONTS = ROOT / "art" / "promo"
INSET = 58  # altezza della barra in alto di Roblox (GuiService:GetGuiInset)

GUIOBJ = {"Frame", "TextLabel", "TextButton", "TextBox", "ImageLabel", "ImageButton", "ScrollingFrame", "ViewportFrame",
          "CanvasGroup"}
TEXT = {"TextLabel", "TextButton", "TextBox"}
IMAGE = {"ImageLabel", "ImageButton"}

FONT_FAMILY = {
    "LuckiestGuy": "'Luckiest Guy', 'Noto Color Emoji'",
    "FredokaOne": "'Fredoka One', 'Noto Color Emoji'",
}
DEFAULT_FONT = "'DejaVu Sans', 'Noto Color Emoji', sans-serif"


def load_images() -> dict[str, Path]:
    lock = json.loads((ROOT / "art" / "assets.lock.json").read_text())
    out = {}
    for name, entry in lock.get("images", {}).items():
        for key in ("image", "decal"):
            if entry.get(key):
                out[str(entry[key])] = ROOT / "art" / "out" / "images" / f"{name}.png"
    return out


IMAGES = load_images()


# ------------------------------------------------------------------------------------------
# Valori
# ------------------------------------------------------------------------------------------
def rgb(c, alpha: float = 1.0) -> str:
    return f"rgba({c[1]},{c[2]},{c[3]},{alpha:.3f})"


def mul(c, k):  # colore * colore (gradienti su sfondo colorato)
    return ["Color3", round(c[1] * k[1] / 255), round(c[2] * k[2] / 255), round(c[3] * k[3] / 255)]


def enum(v, default=None):
    return v[1] if isinstance(v, list) and v and v[0] == "Enum" else default


def udim(v, size: float) -> float:
    return v[1] * size + v[2]


def udim2(v, pw: float, ph: float) -> tuple[float, float]:
    return v[1] * pw + v[2], v[3] * ph + v[4]


def child_of(node, cls: str):
    for k in node.get("k", []):
        if k["c"] == cls:
            return k
    return None


def gradient_css(grad, base, transp_bg: float) -> str:
    seq = grad["p"].get("Color", ["ColorSequence", [0, 255, 255, 255], [1, 255, 255, 255]])
    tseq = grad["p"].get("Transparency", ["NumberSequence", [0, 0], [1, 0]])
    rot = grad["p"].get("Rotation", 0)

    def t_at(t):
        pts = tseq[1:]
        for a, b in zip(pts, pts[1:]):
            if a[0] <= t <= b[0]:
                f = 0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
                return a[1] + (b[1] - a[1]) * f
        return pts[-1][1]

    stops = []
    for kp in seq[1:]:
        col = mul(base, ["Color3", kp[1], kp[2], kp[3]])
        alpha = (1 - transp_bg) * (1 - t_at(kp[0]))
        stops.append(f"{rgb(col, alpha)} {kp[0] * 100:.1f}%")
    return f"linear-gradient({rot + 90}deg, {', '.join(stops)})"


def rich(text: str, is_rich: bool) -> str:
    if not is_rich:
        return html.escape(text)
    out = html.escape(text, quote=False)
    out = re.sub(r"&lt;font color=(?:&quot;|\")?(#[0-9a-fA-F]{6})(?:&quot;|\")?&gt;", r'<span style="color:\1">', out)
    out = re.sub(r"&lt;font[^&]*&gt;", "<span>", out)
    out = out.replace("&lt;/font&gt;", "</span>")
    for tag in ("b", "i", "u", "s"):
        out = out.replace(f"&lt;{tag}&gt;", f"<{tag}>").replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    out = re.sub(r"&lt;br\s*/?&gt;", "<br>", out)
    return out


def stroke_shadow(t: float, color: str) -> str:
    parts = []
    for r, n in ((t, 28), (t * 0.66, 18), (t * 0.33, 10)):
        for i in range(n):
            a = 2 * math.pi * i / n
            parts.append(f"{r * math.cos(a):.2f}px {r * math.sin(a):.2f}px 0 {color}")
    return ", ".join(parts)


# ------------------------------------------------------------------------------------------
# Metriche dei font (larghezza dei caratteri misurata in Chromium, per AutomaticSize)
# ------------------------------------------------------------------------------------------
METRIC_FONTS = {"LuckiestGuy": "'Luckiest Guy'", "FredokaOne": "'Fredoka One'", "Default": "'DejaVu Sans'"}
METRICS: dict = {}


def load_metrics(chars: set[str]) -> None:
    cache = OUT / "font_metrics.json"
    data = json.loads(cache.read_text()) if cache.exists() else {}
    missing = sorted(c for c in chars if any(c not in data.get(f, {}) for f in METRIC_FONTS))
    if missing or any("_lh" not in data.get(f, {}) for f in METRIC_FONTS):
        page_path = OUT / "_metrics.html"
        fams = json.dumps(METRIC_FONTS)
        page_path.write_text(f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: 'Luckiest Guy'; src: url('{(FONTS / "luckiest-guy-latin-400-normal.woff2").as_uri()}'); }}
@font-face {{ font-family: 'Fredoka One'; src: url('{(FONTS / "fredoka-one-latin-400-normal.woff2").as_uri()}'); }}
</style></head><body><span style="font-family:'Luckiest Guy'">a</span><span style="font-family:'Fredoka One'">a</span>
<pre id="out"></pre><script>
const chars = {json.dumps(missing)};
const fams = {fams};
document.fonts.ready.then(() => {{
  const c = document.createElement('canvas').getContext('2d');
  const res = {{}};
  for (const [k, fam] of Object.entries(fams)) {{
    c.font = '100px ' + fam + ", 'Noto Color Emoji'";
    const m = c.measureText('Hg');
    res[k] = {{_lh: m.fontBoundingBoxAscent + m.fontBoundingBoxDescent}};
    for (const ch of chars) res[k][ch] = c.measureText(ch).width;
  }}
  document.getElementById('out').textContent = JSON.stringify(res);
}});
</script></body></html>""")
        dom = subprocess.run([chromium(), "--no-sandbox", "--allow-file-access-from-files", "--virtual-time-budget=3000",
                              "--dump-dom", page_path.as_uri()], check=True, capture_output=True, text=True).stdout
        m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        if m:
            fresh = json.loads(html.unescape(m.group(1)))
            for k, v in fresh.items():
                data.setdefault(k, {}).update(v)
            cache.write_text(json.dumps(data))
    METRICS.clear()
    METRICS.update(data)


def plain(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def text_size(text: str, font: str, ts: float) -> tuple[float, float]:
    """Larghezza e altezza di un testo (TextSize di Roblox) senza a capo automatico."""
    m = METRICS.get(font if font in METRICS else "Default", {})
    lh = m.get("_lh", 100) or 100
    css = ts * 100 / lh
    lines = plain(text).split("\n")
    width = max(sum(m.get(ch, 55) for ch in line) for line in lines) * css / 100
    return width, ts * len(lines)


# ------------------------------------------------------------------------------------------
# Impaginazione
# ------------------------------------------------------------------------------------------
def sort_children(kids, sort_order="LayoutOrder"):
    items = [(i, k) for i, k in enumerate(kids) if k["c"] in GUIOBJ and k["p"].get("Visible", True)]
    if sort_order == "Name":
        items.sort(key=lambda ik: (ik[1]["n"], ik[0]))
    else:
        items.sort(key=lambda ik: (ik[1]["p"].get("LayoutOrder", 0), ik[0]))
    return [k for _, k in items]


def own_size(node, pw, ph):
    p = node["p"]
    size = p.get("Size", ["UDim2", 0, 100, 0, 100])
    sc = enum(p.get("SizeConstraint"), "RelativeXY")
    if sc == "RelativeYY":
        w, h = size[1] * ph + size[2], size[3] * ph + size[4]
    elif sc == "RelativeXX":
        w, h = size[1] * pw + size[2], size[3] * pw + size[4]
    else:
        w, h = udim2(size, pw, ph)
    auto = enum(p.get("AutomaticSize"), "None")
    if auto != "None":
        nw, nh = natural_size(node, w, h)
        if auto in ("X", "XY"):
            w = max(w, nw)
        if auto in ("Y", "XY"):
            h = max(h, nh)
    return w, h


def natural_size(node, w, h):
    """Misura naturale del contenuto (per AutomaticSize): testo e figli, piu' il padding."""
    p = node["p"]
    padn = child_of(node, "UIPadding")
    pl = pr = pt = pb = 0.0
    if padn:
        pp = padn["p"]
        pl, pr = udim(pp.get("PaddingLeft", ["UDim", 0, 0]), w), udim(pp.get("PaddingRight", ["UDim", 0, 0]), w)
        pt, pb = udim(pp.get("PaddingTop", ["UDim", 0, 0]), h), udim(pp.get("PaddingBottom", ["UDim", 0, 0]), h)
    nw = nh = 0.0
    if node["c"] in TEXT and not p.get("TextScaled", False) and p.get("Text"):
        nw, nh = text_size(p["Text"], enum(p.get("Font"), "Legacy"), p.get("TextSize", 14))
    kids = [k for k in node.get("k", []) if k["c"] in GUIOBJ and k["p"].get("Visible", True)]
    layout = child_of(node, "UIListLayout")
    if layout and kids:
        lp = layout["p"]
        horizontal = enum(lp.get("FillDirection"), "Vertical") == "Horizontal"
        sizes = [own_size(k, w, h) for k in kids]
        pad = udim(lp.get("Padding", ["UDim", 0, 0]), w if horizontal else h) * (len(kids) - 1)
        if horizontal:
            nw, nh = max(nw, sum(sz[0] for sz in sizes) + pad), max(nh, max(sz[1] for sz in sizes))
        else:
            nw, nh = max(nw, max(sz[0] for sz in sizes)), max(nh, sum(sz[1] for sz in sizes) + pad)
    else:
        for k in kids:
            cw, ch = own_size(k, w, h)
            pos = k["p"].get("Position", ["UDim2", 0, 0, 0, 0])
            nw = max(nw, pos[2] + cw)
            nh = max(nh, pos[4] + ch)
    return nw + pl + pr, nh + pt + pb


def list_layout(layout, kids, cw, ch):
    lp = layout["p"]
    vertical = enum(lp.get("FillDirection"), "Vertical") == "Vertical"
    pad = udim(lp.get("Padding", ["UDim", 0, 0]), ch if vertical else cw)
    halign = enum(lp.get("HorizontalAlignment"), "Left")
    valign = enum(lp.get("VerticalAlignment"), "Top")
    items = sort_children(kids, enum(lp.get("SortOrder"), "LayoutOrder"))
    sizes = [own_size(k, cw, ch) for k in items]
    total = sum(s[1] if vertical else s[0] for s in sizes) + pad * max(0, len(items) - 1)
    pos = {}
    if vertical:
        y = {"Top": 0, "Center": (ch - total) / 2, "Bottom": ch - total}[valign]
        for k, (w, h) in zip(items, sizes):
            x = {"Left": 0, "Center": (cw - w) / 2, "Right": cw - w}[halign]
            pos[id(k)] = (x, y, w, h)
            y += h + pad
    else:
        x = {"Left": 0, "Center": (cw - total) / 2, "Right": cw - total}[halign]
        for k, (w, h) in zip(items, sizes):
            y = {"Top": 0, "Center": (ch - h) / 2, "Bottom": ch - h}[valign]
            pos[id(k)] = (x, y, w, h)
            x += w + pad
    return pos, total


def grid_layout(layout, kids, cw, ch):
    lp = layout["p"]
    cell = udim2(lp.get("CellSize", ["UDim2", 0, 100, 0, 100]), cw, ch)
    padx, pady = udim2(lp.get("CellPadding", ["UDim2", 0, 5, 0, 5]), cw, ch)
    items = sort_children(kids, enum(lp.get("SortOrder"), "LayoutOrder"))
    cols = max(1, int((cw + padx + 0.001) // (cell[0] + padx)))
    maxc = lp.get("FillDirectionMaxCells", 0)
    if maxc:
        cols = min(cols, maxc)
    used = min(cols, len(items)) if items else 0
    rows = math.ceil(len(items) / cols) if items else 0
    gw = used * cell[0] + max(0, used - 1) * padx
    gh = rows * cell[1] + max(0, rows - 1) * pady
    halign = enum(lp.get("HorizontalAlignment"), "Left")
    valign = enum(lp.get("VerticalAlignment"), "Top")
    x0 = {"Left": 0, "Center": (cw - gw) / 2, "Right": cw - gw}[halign]
    y0 = {"Top": 0, "Center": (ch - gh) / 2, "Bottom": ch - gh}[valign]
    pos = {}
    for i, k in enumerate(items):
        r, c = divmod(i, cols)
        pos[id(k)] = (x0 + c * (cell[0] + padx), y0 + r * (cell[1] + pady), cell[0], cell[1])
    return pos, gh


class Renderer:
    def __init__(self):
        self.warnings: list[str] = []

    def children_html(self, node, w, h, scrolling=False):
        p = node["p"]
        kids = node.get("k", [])
        padn = child_of(node, "UIPadding")
        pl = pr = pt = pb = 0.0
        if padn:
            pp = padn["p"]
            pl = udim(pp.get("PaddingLeft", ["UDim", 0, 0]), w)
            pr = udim(pp.get("PaddingRight", ["UDim", 0, 0]), w)
            pt = udim(pp.get("PaddingTop", ["UDim", 0, 0]), h)
            pb = udim(pp.get("PaddingBottom", ["UDim", 0, 0]), h)
        cw, ch = w - pl - pr, h - pt - pb
        layout = child_of(node, "UIListLayout") or child_of(node, "UIGridLayout")
        pos, content = {}, 0.0
        if layout:
            if layout["c"] == "UIListLayout":
                pos, content = list_layout(layout, kids, cw, ch)
            else:
                pos, content = grid_layout(layout, kids, cw, ch)
        items = [k for k in kids if k["c"] in GUIOBJ]
        order = sorted(range(len(items)), key=lambda i: (items[i]["p"].get("ZIndex", 1), i))
        parts = []
        extent = 0.0
        for i in order:
            k = items[i]
            if not k["p"].get("Visible", True):
                continue
            frag, bottom = self.node_html(k, cw, ch, pl, pt, pos.get(id(k)))
            parts.append(frag)
            extent = max(extent, bottom)
        if layout:
            extent = max(extent, pt + content)
        return "".join(parts), extent + pb

    def node_html(self, node, pw, ph, ox, oy, laid=None):
        p = node["p"]
        cls = node["c"]
        if laid:
            x, y, w, h = laid
        else:
            w, h = own_size(node, pw, ph)
            pos = udim2(p.get("Position", ["UDim2", 0, 0, 0, 0]), pw, ph)
            ap = p.get("AnchorPoint", ["Vector2", 0, 0])
            x, y = pos[0] - ap[1] * w, pos[1] - ap[2] * h
        x += ox
        y += oy
        style = [f"left:{x:.2f}px", f"top:{y:.2f}px", f"width:{max(0, w):.2f}px", f"height:{max(0, h):.2f}px"]
        transforms = []
        rot = p.get("Rotation", 0)
        if rot:
            transforms.append(f"rotate({rot}deg)")
        scale = child_of(node, "UIScale")
        if scale and scale["p"].get("Scale", 1) != 1:
            transforms.append(f"scale({scale['p']['Scale']})")
        if transforms:
            style.append("transform:" + " ".join(transforms))
            if scale and scale["p"].get("Scale", 1) != 1:
                ap = p.get("AnchorPoint", ["Vector2", 0, 0])
                style.append(f"transform-origin:{ap[1] * 100:.0f}% {ap[2] * 100:.0f}%")
        # sfondo
        bt = p.get("BackgroundTransparency", 0)
        bg = p.get("BackgroundColor3", ["Color3", 163, 162, 165])
        grad = child_of(node, "UIGradient")
        grad_on = grad is not None and grad["p"].get("Enabled", True)
        if bt < 1 and cls != "ViewportFrame" or cls == "ViewportFrame" and bt < 1:
            if grad_on:
                style.append(f"background:{gradient_css(grad, bg, bt)}")
            else:
                style.append(f"background:{rgb(bg, 1 - bt)}")
        corner = child_of(node, "UICorner")
        if corner:
            cr = corner["p"].get("CornerRadius", ["UDim", 0, 8])
            m = min(w, h)
            r = min(cr[1] * m + cr[2], m / 2)
            style.append(f"border-radius:{r:.2f}px")
        clip = p.get("ClipsDescendants", False) or cls == "ScrollingFrame"
        if clip:
            style.append("overflow:hidden")
        # contorno del riquadro
        strokes = [k for k in node.get("k", []) if k["c"] == "UIStroke" and k["p"].get("Enabled", True)]
        text_stroke = None
        shadows = []
        for s in strokes:
            mode = enum(s["p"].get("ApplyStrokeMode"), "Contextual")
            t = s["p"].get("Thickness", 1)
            col = rgb(s["p"].get("Color", ["Color3", 0, 0, 0]), 1 - s["p"].get("Transparency", 0))
            if cls in TEXT and mode == "Contextual":
                text_stroke = (t, col, s["p"].get("Transparency", 0))
            else:
                shadows.append(f"0 0 0 {t}px {col}")
        if not strokes and not corner and bt < 1 and p.get("BorderSizePixel", 1) > 0 and cls in GUIOBJ:
            shadows.append(f"0 0 0 {p.get('BorderSizePixel', 1)}px rgb(27,42,53)")
        if shadows:
            style.append("box-shadow:" + ", ".join(shadows))
        inner = []
        if cls in TEXT:
            inner.append(self.text_html(node, w, h, text_stroke, grad if grad_on else None))
        elif cls in IMAGE:
            img = p.get("Image", "")
            m = re.search(r"(\d+)", img or "")
            if m and m.group(1) in IMAGES:
                fit = {"Fit": "contain", "Crop": "cover"}.get(enum(p.get("ScaleType"), "Stretch"), "fill")
                op = 1 - p.get("ImageTransparency", 0)
                uri = IMAGES[m.group(1)].as_uri()
                inner.append(
                    f'<img src="{uri}" style="position:absolute;left:0;top:0;width:100%;'
                    f'height:100%;object-fit:{fit};opacity:{op}">')
                tint = p.get("ImageColor3", ["Color3", 255, 255, 255])
                if tint[1:] != [255, 255, 255]:
                    # ImageColor3 moltiplica i colori dell'immagine
                    msize = {"contain": "contain", "cover": "cover"}.get(fit, "100% 100%")
                    inner.append(
                        f'<div style="position:absolute;inset:0;background:{rgb(tint)};mix-blend-mode:multiply;'
                        f'opacity:{op};-webkit-mask:url({uri}) center/{msize} no-repeat;mask:url({uri}) center/{msize} no-repeat">'
                        f'</div>')
            elif img:
                self.warnings.append(f"immagine sconosciuta {img} in {node['n']}")
        elif cls == "ViewportFrame":
            inner.append(self.viewport_html(node))
        if cls == "ScrollingFrame":
            kids_html, extent = self.children_html(node, w, h, scrolling=True)
            inner.append(f'<div style="position:absolute;left:0;top:0;width:{w:.2f}px;height:{max(h, extent):.2f}px">'
                         f"{kids_html}</div>")
            if extent > h + 1:
                th = p.get("ScrollBarThickness", 12)
                col = rgb(p.get("ScrollBarImageColor3", ["Color3", 0, 0, 0]), 1 - p.get("ScrollBarImageTransparency", 0))
                bar_h = h * h / extent
                inner.append(f'<div style="position:absolute;right:0;top:0;width:{th}px;height:{bar_h:.1f}px;'
                             f'background:{col};border-radius:{th / 2}px"></div>')
        else:
            kids_html, _ = self.children_html(node, w, h)
            inner.append(kids_html)
        name = html.escape(node["n"], quote=True)
        return f'<div class="g {cls}" data-n="{name}" style="{";".join(style)}">{"".join(inner)}</div>', y + h

    def text_html(self, node, w, h, stroke, grad):
        p = node["p"]
        text = p.get("Text", "")
        placeholder = False
        if node["c"] == "TextBox" and not text:
            text = p.get("PlaceholderText", "")
            placeholder = True
        tt = p.get("TextTransparency", 0)
        if not text or tt >= 1:
            return ""
        font = enum(p.get("Font"), "Legacy")
        family = FONT_FAMILY.get(font, DEFAULT_FONT)
        scaled = p.get("TextScaled", False)
        wrapped = p.get("TextWrapped", False)
        cons = child_of(node, "UITextSizeConstraint")
        maxts = min(100, cons["p"].get("MaxTextSize", 100)) if cons else 100
        mints = cons["p"].get("MinTextSize", 1) if cons else 1
        xa = {"Left": "flex-start", "Center": "center", "Right": "flex-end"}[enum(p.get("TextXAlignment"), "Center")]
        ya = {"Top": "flex-start", "Center": "center", "Bottom": "flex-end"}[enum(p.get("TextYAlignment"), "Center")]
        ta = {"flex-start": "left", "center": "center", "flex-end": "right"}[xa]
        color = p.get("PlaceholderColor3" if placeholder else "TextColor3", ["Color3", 0, 0, 0])
        fill = rgb(color, 1 - tt)
        content = rich(text, p.get("RichText", False))
        padn = child_of(node, "UIPadding")
        pad = ""
        if padn:
            pp = padn["p"]
            pad = (f"padding:{udim(pp.get('PaddingTop', ['UDim', 0, 0]), h)}px {udim(pp.get('PaddingRight', ['UDim', 0, 0]), w)}px "
                   f"{udim(pp.get('PaddingBottom', ['UDim', 0, 0]), h)}px {udim(pp.get('PaddingLeft', ['UDim', 0, 0]), w)}px;")
        ws = "pre-wrap" if wrapped else "pre"
        attrs = (f'data-scaled="{1 if scaled else 0}" data-ts="{p.get("TextSize", 14)}" data-max="{maxts}" '
                 f'data-min="{mints}" data-font="{font}"')
        layers = []
        if stroke and stroke[2] < 1:
            layers.append(f'<span class="tx stroke" style="color:{stroke[1]};text-shadow:{stroke_shadow(stroke[0], stroke[1])};'
                          f'white-space:{ws};text-align:{ta}">{content}</span>')
        if grad:
            layers.append(f'<span class="tx" style="background:{gradient_css(grad, color, 0)};-webkit-background-clip:text;'
                          f'background-clip:text;color:transparent;white-space:{ws};text-align:{ta}">{content}</span>')
        else:
            layers.append(f'<span class="tx" style="color:{fill};white-space:{ws};text-align:{ta}">{content}</span>')
        boxes = "".join(
            f'<div class="tb" {attrs} style="position:absolute;inset:0;display:flex;justify-content:{xa};align-items:{ya};'
            f'font-family:{family};{pad}">{layer}</div>' for layer in layers)
        return boxes

    def viewport_html(self, node):
        def find_model(n):
            for k in n.get("k", []):
                if k["c"] == "Model":
                    return k
                found = find_model(k)
                if found:
                    return found
            return None

        model = find_model(node)
        if not model or not model.get("a"):
            return ""
        pet = model["a"].get("PetId")
        if not pet:
            return ""
        img = cropped_pet(pet)
        if img is None:
            self.warnings.append(f"render mancante per {pet}")
            return ""
        dark = False
        for k in model.get("k", []):
            c = k["p"].get("Color")
            if c and c[1:] == [20, 14, 36]:
                dark = True
        filt = "filter:brightness(0) opacity(0.85);" if dark else ""
        # la camera del gioco inquadra il pet in circa l'80% dell'altezza del riquadro
        return (f'<img src="{img.as_uri()}" style="position:absolute;left:10%;top:10%;width:80%;height:80%;'
                f'object-fit:contain;transform:scaleX(-1);{filt}">')

    def gui_html(self, gui, vw, vh, scale):
        p = gui["p"]
        if not p.get("Enabled", True):
            return ""
        top = 0 if p.get("IgnoreGuiInset", False) else INSET
        sc = child_of(gui, "UIScale")
        s = sc["p"].get("Scale", 1) if sc else 1
        w, h = vw / s, (vh - top) / s
        kids, _ = self.children_html({"p": {}, "k": gui.get("k", [])}, w, h)
        return (f'<div class="gui" data-n="{gui["n"]}" style="left:0;top:{top}px;width:{w:.2f}px;height:{h:.2f}px;'
                f'transform:scale({s});transform-origin:0 0">{kids}</div>')


def cropped_pet(pet: str) -> Path | None:
    """Render 3/4 del pet ritagliato sulla sagoma (i render hanno molto margine)."""
    src = ROOT / "art" / "out" / "pet" / pet / f"{pet}_3q.png"
    if not src.exists():
        return None
    dst = OUT / "pets" / f"{pet}.png"
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return dst
    from PIL import Image

    im = Image.open(src).convert("RGBA")
    box = im.getchannel("A").point(lambda a: 255 if a > 160 else 0).getbbox()
    if box:
        im = im.crop(box)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst)
    return dst


def core_gui(vw: int, vh: int, touch: bool, core: dict) -> str:
    """Sagoma (approssimata) dell'interfaccia di Roblox sopra al gioco."""
    out = []
    show_list = core.get("PlayerList", True)
    show_tools = core.get("Backpack", True)
    pill = "position:absolute;background:rgba(18,18,21,0.72);border-radius:22px"
    out.append(f'<div style="{pill};left:12px;top:12px;width:44px;height:44px"></div>')
    out.append(f'<div style="{pill};left:64px;top:12px;width:136px;height:44px"></div>')
    label = "position:absolute;color:rgba(255,255,255,0.55);font:12px 'DejaVu Sans';"
    if not touch:
        # finestra della chat (TextChatService) in alto a sinistra
        out.append(f'<div style="position:absolute;left:8px;top:{INSET + 4}px;width:400px;height:250px;'
                   f'border:1px dashed rgba(255,255,255,0.45);border-radius:8px;background:rgba(0,0,0,0.18)">'
                   f'<span style="{label}left:8px;top:6px">chat di Roblox</span></div>')
    if not touch and show_list:
        # elenco giocatori (aperto di default su PC)
        rows = 8
        out.append(f'<div style="position:absolute;right:12px;top:{INSET + 4}px;width:220px;height:{rows * 34 + 8}px;'
                   f'background:rgba(18,18,21,0.6);border-radius:8px">'
                   f'<span style="{label}left:8px;top:6px">elenco giocatori (8)</span></div>')
    slot = 50 if touch else 60
    if show_tools:
        out.append(f'<div style="position:absolute;left:{vw / 2 - slot / 2}px;top:{vh - slot - 4}px;width:{slot}px;'
                   f'height:{slot}px;background:rgba(30,30,34,0.6);border:2px solid rgba(255,255,255,0.25);'
                   f'border-radius:8px"><span style="{label}left:4px;top:2px">1</span>'
                   f'<span style="{label}left:6px;top:{slot / 2 - 7}px">Bat</span></div>')
    if touch:
        small = min(vw, vh) <= 500
        js = 70 if small else 120
        jx, jy = (vw - 95, vh - 90) if small else (vw - 170, vh - 210)
        out.append(f'<div style="position:absolute;left:{jx}px;top:{jy}px;width:{js}px;height:{js}px;border-radius:50%;'
                   f'border:2px solid rgba(255,255,255,0.6);background:rgba(255,255,255,0.12)">'
                   f'<span style="{label}left:{js / 2 - 14}px;top:{js / 2 - 7}px">salto</span></div>')
        tr = 60 if small else 90
        out.append(f'<div style="position:absolute;left:{40}px;top:{vh - 2 * tr - 30}px;width:{2 * tr}px;height:{2 * tr}px;'
                   f'border-radius:50%;border:2px dashed rgba(255,255,255,0.35)">'
                   f'<span style="{label}left:{tr - 24}px;top:{tr - 7}px">levetta</span></div>')
    return f'<div id="core" style="position:absolute;inset:0;pointer-events:none">{"".join(out)}</div>'


SCRIPT = """
<script>
const FACTORS = {};
function factor(font) {
  if (FACTORS[font] !== undefined) return FACTORS[font];
  const fam = {LuckiestGuy: "'Luckiest Guy'", FredokaOne: "'Fredoka One'"}[font] || "'DejaVu Sans'";
  const c = document.createElement('canvas').getContext('2d');
  c.font = '100px ' + fam;
  const m = c.measureText('Hg');
  const lh = m.fontBoundingBoxAscent + m.fontBoundingBoxDescent;
  FACTORS[font] = lh > 0 ? 100 / lh : 1;
  return FACTORS[font];
}
function apply(box, ts) {
  for (const sp of box.querySelectorAll('.tx')) {
    sp.style.fontSize = (ts * factor(box.dataset.font)) + 'px';
    sp.style.lineHeight = ts + 'px';
  }
}
function fits(box) {
  const sp = box.querySelector('.tx');
  const cs = getComputedStyle(box);
  const bw = box.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
  const bh = box.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
  if (sp.style.whiteSpace === 'pre-wrap') sp.style.maxWidth = bw + 'px';
  const r = sp.getBoundingClientRect();
  // le dimensioni del rettangolo includono la scala dei genitori: si confrontano con quelle del box
  const br = box.getBoundingClientRect();
  const kx = br.width / Math.max(1, box.clientWidth), ky = br.height / Math.max(1, box.clientHeight);
  return r.width / kx <= bw + 0.6 && r.height / ky <= bh + 0.6;
}
function fitAll() {
  const groups = new Map();
  for (const box of document.querySelectorAll('.tb')) {
    const key = box.parentElement;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(box);
  }
  for (const [, boxes] of groups) {
    const main = boxes[boxes.length - 1];
    let ts = parseFloat(main.dataset.ts);
    if (main.dataset.scaled === '1') {
      let lo = parseFloat(main.dataset.min), hi = parseFloat(main.dataset.max);
      apply(main, hi);
      if (!fits(main)) {
        while (hi - lo > 0.5) {
          const mid = (lo + hi) / 2;
          apply(main, mid);
          if (fits(main)) lo = mid; else hi = mid;
        }
        ts = Math.floor(lo);
      } else ts = hi;
    }
    for (const b of boxes) apply(b, ts);
    for (const b of boxes) {
      const sp = b.querySelector('.tx');
      if (sp.style.whiteSpace === 'pre-wrap') {
        const cs = getComputedStyle(b);
        sp.style.maxWidth = (b.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)) + 'px';
      }
    }
    if (!fits(main)) main.parentElement.dataset.overflow = '1';
  }
  document.body.dataset.done = '1';
}
document.fonts.ready.then(fitAll);
</script>
"""


def collect_chars(node, out: set[str]) -> None:
    for key in ("Text", "PlaceholderText"):
        v = node["p"].get(key)
        if isinstance(v, str):
            out.update(plain(v))
    for k in node.get("k", []):
        collect_chars(k, out)


def page(scene: dict) -> tuple[str, list[str]]:
    vw, vh = scene["viewport"]
    chars: set[str] = set()
    collect_chars(scene["root"], chars)
    load_metrics(chars)
    r = Renderer()
    guis = [g for g in scene["root"].get("k", []) if g["c"] == "ScreenGui"]
    guis.sort(key=lambda g: g["p"].get("DisplayOrder", 0))
    touch = scene.get("touch", scene["scene"].endswith("phone"))
    body = "".join(r.gui_html(g, vw, vh, scene.get("scale", 1)) for g in guis)
    # la sagoma di Roblox sta sopra ai pannelli del gioco
    core = core_gui(vw, vh, touch, scene.get("core") or {})
    bg = ROOT / "art" / "out" / "world" / "trail.png"
    bg_css = f"background:#4a6b8c url('{bg.as_uri()}') center/cover" if bg.exists() else "background:#4a6b8c"
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: 'Luckiest Guy'; src: url('{(FONTS / "luckiest-guy-latin-400-normal.woff2").as_uri()}'); }}
@font-face {{ font-family: 'Fredoka One'; src: url('{(FONTS / "fredoka-one-latin-400-normal.woff2").as_uri()}'); }}
html, body {{ margin:0; padding:0; width:{vw}px; height:{vh}px; overflow:hidden; {bg_css}; }}
.gui, .g {{ position:absolute; box-sizing:border-box; }}
.tx {{ display:block; }}
</style></head><body>{body}{core}{SCRIPT}</body></html>"""
    return doc, r.warnings


def chromium() -> str:
    found = glob("/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell")
    if not found:
        raise SystemExit("Chromium headless non trovato")
    return found[0]


def shoot(html_path: Path, png: Path, vw: int, vh: int) -> None:
    subprocess.run([chromium(), "--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--allow-file-access-from-files", "--virtual-time-budget=4000", f"--window-size={vw},{vh}",
                    f"--screenshot={png}", html_path.as_uri()], check=True, capture_output=True)


def contact_sheet(pngs: list[Path]) -> Path:
    from PIL import Image, ImageDraw

    thumbs = []
    for pth in pngs:
        im = Image.open(pth).convert("RGB")
        k = 640 / im.width
        thumbs.append((pth.stem, im.resize((640, round(im.height * k)))))
    cols = 3
    cell_h = max(t.height for _, t in thumbs) + 28
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 650 + 10, rows * cell_h + 10), (24, 20, 36))
    d = ImageDraw.Draw(sheet)
    for i, (name, t) in enumerate(thumbs):
        r, c = divmod(i, cols)
        x, y = 10 + c * 650, 10 + r * cell_h
        d.text((x, y), name, fill=(230, 230, 240))
        sheet.paste(t, (x, y + 18))
    out = OUT / "contact.png"
    sheet.save(out)
    return out


def main(argv: list[str]) -> int:
    names = argv or sorted(Path(p).stem for p in glob(str(OUT / "*.json")) if Path(p).stem != "font_metrics")
    pngs = []
    for name in names:
        scene = json.loads((OUT / f"{name}.json").read_text())
        doc, warnings = page(scene)
        html_path = OUT / f"{name}.html"
        html_path.write_text(doc)
        png = OUT / f"{name}.png"
        shoot(html_path, png, *scene["viewport"])
        pngs.append(png)
        print(f"{name}: {png.relative_to(ROOT)}" + (f"  ({len(warnings)} avvisi)" if warnings else ""))
        for w in sorted(set(warnings))[:10]:
            print("   ", w)
    if len(pngs) > 1:
        print("riepilogo:", contact_sheet(pngs).relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
