"""Proposte di stile per l'interfaccia (bozzetti HTML fotografati con Chromium).

Tre direzioni, con font disponibili su Roblox, disegnate sulla stessa schermata del gioco:
- segnavia:  cartelli dei sentieri di montagna (Oswald + Nunito);
- cucito:    giocattolo di stoffa cucito (Denk One + Patrick Hand);
- fumetto:   adesivi da fumetto (Bangers + Ubuntu).
Per ognuna due schermate: HUD in gioco (con avviso valanga, annuncio, messaggio e uovo in mano,
nelle nuove posizioni lontane dal centro) e negozio aperto.

Uso: python art/ui/proposals.py   ->  art/out/ui/proposals/<stile>_hud.png, <stile>_panel.png,
<stile>.png (le due una sopra l'altra)
"""
from __future__ import annotations

import subprocess
from glob import glob
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "art" / "ui" / "fonts"
ICONS = ROOT / "art" / "out" / "images"
OUT = ROOT / "art" / "out" / "ui" / "proposals"
BG = ROOT / "art" / "out" / "world" / "trail.png"
W, H = 1280, 720

MENU = [("Shop", "NEGOZIO"), ("Upgrades", "POTENZIA"), ("Index", "ALBUM"), ("Gifts", "REGALI"),
        ("Quests", "MISSIONI"), ("Wheel", "RUOTA")]
CARDS = [("VIP", "VIP", "+20% monete, Martello d'Oro, tag VIP, offline x2", "249"),
         ("DoubleCoins", "MONETE X2", "I tuoi pet guadagnano il doppio, per sempre", "399"),
         ("Incubator", "+1 INCUBATRICE", "Un'incubatrice in più nel tuo lotto", "149")]
TABS = ["GAME PASS", "POTENZIAMENTI", "MAZZE"]


def icon(name: str) -> str:
    return (ICONS / f"Icon{name}.png").as_uri()


def fonts_css() -> str:
    faces = [("Oswald", "Oswald.woff2", "200 700"), ("Nunito", "Nunito.woff2", "200 1000"),
             ("Denk One", "DenkOne-400.woff2", "400"), ("Patrick Hand", "PatrickHand-400.woff2", "400"),
             ("Bangers", "Bangers-400.woff2", "400"), ("Ubuntu", "Ubuntu-500.woff2", "500"),
             ("Ubuntu", "Ubuntu-700.woff2", "700")]
    return "\n".join(f"@font-face{{font-family:'{f}';src:url({(FONTS / file).as_uri()}) format('woff2');"
                     f"font-weight:{w};}}" for f, file, w in faces)


BASE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1280px;height:720px;overflow:hidden;background:#000}
.stage{position:relative;width:1280px;height:720px;background:url(BG) center/cover}
.rbx{position:absolute;top:12px;left:12px;display:flex;gap:10px}
.rbx i{display:block;height:44px;border-radius:22px;background:rgba(25,27,29,.75)}
.rbx i:first-child{width:44px}.rbx i:last-child{width:136px}
.abs{position:absolute}
img.ic{display:block;object-fit:contain}
.shade{position:absolute;inset:0;background:rgba(10,14,20,.28)}
"""


def page(css: str, body: str) -> str:
    return (f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{fonts_css()}"
            f"{BASE_CSS.replace('BG', BG.as_uri())}{css}</style></head>"
            f"<body><div class='stage'><div class='rbx'><i></i><i></i></div>{body}</div></body></html>")


# =========================================================================== SEGNAVIA
SEG_CSS = """
:root{--paper:#F3EFE6;--ink:#1E2A33;--red:#D3262B;--red2:#9E1A1E;--yel:#F2B30C;--yel2:#B88200;
--wood:#8C5B34;--wood2:#5E3B1F;--green:#2D7A4C;--green2:#1D5634;--slate:#5A6872}
.t{font-family:'Oswald';font-weight:700;text-transform:uppercase;letter-spacing:.5px}
.b{font-family:'Nunito';font-weight:800}
.plank{background:repeating-linear-gradient(176deg,var(--wood) 0 9px,#93613a 9px 11px,var(--wood) 11px 22px);
 border:3px solid var(--wood2);border-radius:6px;box-shadow:0 4px 0 var(--wood2)}
.nail{position:absolute;width:8px;height:8px;border-radius:50%;background:#C9C2B6;border:2px solid var(--wood2)}
.coins{left:500px;top:8px;width:280px;height:76px}
.coins .num{position:absolute;left:78px;top:-2px;font-size:38px;color:#fff;text-shadow:2px 3px 0 var(--wood2)}
.coins .rate{position:absolute;left:80px;top:48px;padding:0 8px;height:20px;line-height:20px;border-radius:3px;
 background:var(--green);color:#fff;font-size:13px}
.coins img{position:absolute;left:10px;top:9px;width:56px;height:56px}
.stripe{background:linear-gradient(90deg,var(--red) 0 33%,#fff 33% 66%,var(--red) 66%)}
.alert{left:405px;top:88px;width:470px;height:50px;background:var(--red);border:3px solid var(--ink);
 border-radius:6px;box-shadow:0 4px 0 var(--ink);display:flex;align-items:center;color:#fff}
.alert .tri{width:0;height:0;margin:0 10px 0 12px;border-left:17px solid transparent;border-right:17px solid transparent;
 border-bottom:30px solid var(--yel);position:relative}
.alert .tri:after{content:'!';position:absolute;left:-4px;top:5px;font:700 20px 'Oswald';color:var(--ink)}
.alert .h{font-size:26px;margin-right:10px}.alert .s{font-size:15px;opacity:.95;flex:1}
.alert .clock{background:#fff;color:var(--ink);font-size:22px;padding:0 10px;margin-right:6px;border-radius:4px;height:36px;line-height:36px}
.ann{left:360px;top:146px;width:560px;height:34px;background:rgba(30,42,51,.88);border-radius:5px;color:#fff;
 font-size:15px;display:flex;align-items:center;padding-left:14px;border-left:8px solid #FFC72C}
.ann em{font-style:normal;color:#FFC72C}
.menu{left:16px;top:300px}
.tile{position:absolute;width:100px;height:92px;background:#fff;border:3px solid var(--ink);border-radius:6px;
 box-shadow:0 5px 0 var(--ink);overflow:hidden}
.tile .stripe{position:absolute;left:0;right:0;top:0;height:12px}
.tile img{position:absolute;left:18px;top:16px;width:64px;height:64px}
.lab{position:absolute;width:100px;height:22px;line-height:22px;text-align:center;background:var(--ink);color:#fff;
 font-size:14px;border-radius:3px}
.small{position:absolute;width:62px;height:56px;background:var(--slate);border:3px solid var(--ink);border-radius:6px;
 box-shadow:0 4px 0 var(--ink)}
.small img{position:absolute;left:9px;top:6px;width:38px;height:38px}
.def{right:16px;top:400px;width:96px;height:90px;background:var(--red);border:3px solid var(--ink);border-radius:6px;
 box-shadow:0 5px 0 var(--ink)}
.def img{position:absolute;left:14px;top:10px;width:62px;height:62px}
.deflab{right:16px;top:500px;width:96px}
.carry{left:420px;top:548px;width:440px;height:92px;background:var(--paper);border:3px solid var(--ink);border-radius:6px;
 box-shadow:0 5px 0 var(--ink);overflow:hidden}
.carry .bar{position:absolute;left:0;top:0;bottom:0;width:10px;background:#F2A623}
.carry img{position:absolute;left:20px;top:8px;width:72px;height:72px}
.carry .h{position:absolute;left:104px;top:6px;font-size:28px;color:#C77700}
.carry .s{position:absolute;left:106px;top:48px;font-size:15px;color:var(--ink)}
.carry .s b{color:var(--red)}
.carry .n{position:absolute;left:106px;top:68px;font-size:13px;color:var(--slate)}
.toast{right:16px;bottom:24px;width:360px;height:50px;background:var(--paper);border:3px solid var(--ink);
 border-radius:6px;box-shadow:0 4px 0 var(--ink);display:flex;align-items:center;gap:10px;padding-left:10px;font-size:17px;color:var(--ink)}
.toast img{width:34px;height:34px}.toast .g{color:var(--green);font-family:'Oswald';font-weight:700;font-size:20px}
.panel{left:210px;top:158px;width:860px;height:540px;background:var(--paper);border:4px solid var(--ink);border-radius:8px;
 box-shadow:0 7px 0 var(--ink)}
.sign{position:absolute;left:24px;top:-30px;height:58px;width:236px;padding:0 0 0 22px;background:var(--yel);border:4px solid var(--ink);
 clip-path:polygon(0 0,calc(100% - 30px) 0,100% 50%,calc(100% - 30px) 100%,0 100%);font-size:36px;line-height:50px;color:var(--ink)}
.signback{position:absolute;left:20px;top:-34px;height:66px;width:246px;background:var(--ink);
 clip-path:polygon(0 0,calc(100% - 34px) 0,100% 50%,calc(100% - 34px) 100%,0 100%)}
.post{position:absolute;left:68px;top:-58px;width:16px;height:30px;background:var(--wood);border:3px solid var(--ink)}
.close{position:absolute;right:-18px;top:-18px;width:52px;height:52px;background:var(--red);border:4px solid var(--ink);border-radius:6px;
 box-shadow:0 4px 0 var(--ink);color:#fff;font-size:30px;text-align:center;line-height:42px}
.tabs{position:absolute;left:330px;top:-22px;display:flex;gap:10px}
.tab{height:42px;padding:0 30px 0 14px;font-size:20px;line-height:36px;border:3px solid var(--ink);color:#fff;background:var(--wood);
 clip-path:polygon(0 0,calc(100% - 18px) 0,100% 50%,calc(100% - 18px) 100%,0 100%)}
.tab.on{background:var(--yel);color:var(--ink)}
.cards{position:absolute;left:26px;top:52px;right:26px;display:flex;gap:18px}
.card{position:relative;flex:1;height:300px;background:#fff;border:3px solid var(--ink);border-radius:6px;overflow:hidden}
.card .stripe{position:absolute;left:0;right:0;top:0;height:10px}
.card img{position:absolute;left:50%;top:26px;width:110px;height:110px;margin-left:-55px}
.card .h{position:absolute;left:0;right:0;top:142px;text-align:center;font-size:28px;color:var(--ink)}
.card .d{position:absolute;left:16px;right:16px;top:186px;text-align:center;font-size:15px;color:var(--slate);line-height:1.25}
.buy{position:absolute;left:22px;right:22px;bottom:16px;height:44px;background:var(--green);border:3px solid var(--ink);border-radius:5px;
 box-shadow:inset 0 -5px 0 var(--green2);color:#fff;font-size:22px;text-align:center;line-height:36px}
.row2{position:absolute;left:26px;right:26px;top:372px;display:flex;gap:18px}
.row2 .card{height:150px}
"""


def segnavia(panel: bool) -> str:
    b = ["<div class='abs coins plank'><i class='nail' style='left:6px;top:6px'></i><i class='nail' style='right:6px;top:6px'></i>"
         f"<img src='{icon('Coin')}'><div class='num t'>$245K</div><div class='rate b'>+$1.25K/s</div></div>"]
    b.append("<div class='abs menu'>")
    for i, (ic, lab) in enumerate(MENU):
        x, y = (i % 3) * 112, (i // 3) * 136
        b.append(f"<div class='tile' style='left:{x}px;top:{y}px'><div class='stripe'></div><img src='{icon(ic)}'></div>"
                 f"<div class='lab t' style='left:{x}px;top:{y + 102}px'>{lab}</div>")
    for i, ic in enumerate(["Codes", "Settings"]):
        b.append(f"<div class='small' style='left:{i * 74}px;top:270px'><img src='{icon(ic)}'></div>")
    b.append("</div>")
    b.append(f"<div class='abs def'><img src='{icon('Barrier')}'></div><div class='abs lab t deflab'>DIFESA</div>")
    if not panel:
        b.append("<div class='abs alert'><div class='tri'></div><div class='h t'>VALANGA!</div>"
                 "<div class='s b'>Corri in un rifugio!</div><div class='clock t'>0:12</div></div>")
        b.append("<div class='abs ann b'>Luca ha trovato un uovo&nbsp;<em>LEGGENDARIO</em>&nbsp;nel Canyon!</div>")
        b.append(f"<div class='abs carry'><div class='bar'></div><img src='{icon('Egg')}'><div class='h t'>UOVO LEGGENDARIO ×2</div>"
                 "<div class='s b'>Velocità <b>-51%</b> · Pesante</div><div class='n b'>Portalo al tuo lotto in cima!</div></div>")
        b.append(f"<div class='abs toast b'><img src='{icon('CoinsSmall')}'>Hai raccolto <span class='g'>$3.4K</span></div>")
    else:
        b.append("<div class='shade'></div><div class='abs panel'>")
        b.append("<div class='post'></div><div class='signback'></div><div class='sign t'>NEGOZIO</div>")
        b.append("<div class='close t'>✕</div><div class='tabs'>" + "".join(
            f"<div class='tab t{' on' if i == 0 else ''}'>{t}</div>" for i, t in enumerate(TABS)) + "</div>")
        b.append("<div class='cards'>" + "".join(
            f"<div class='card'><div class='stripe'></div><img src='{icon(ic)}'><div class='h t'>{h}</div>"
            f"<div class='d b'>{d}</div><div class='buy t'>R$ {p}</div></div>" for ic, h, d, p in CARDS) + "</div>")
        b.append("<div class='row2'>" + "".join(
            f"<div class='card'><div class='stripe'></div><img src='{icon(ic)}' style='width:86px;height:86px;margin-left:-43px;top:22px'>"
            f"<div class='h t' style='top:110px'>{h}</div></div>"
            for ic, h in (("Backpack", "ZAINO GRANDE"), ("HatchSpeed", "SCHIUSA VELOCE"), ("Barrier", "SUPER BARRIERA"))) + "</div>")
        b.append("</div>")
    return page(SEG_CSS, "".join(b))


# =========================================================================== CUCITO
FELT = ("url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'>"
        "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3' stitchTiles='stitch'/>"
        "<feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .16 0'/></filter>"
        "<rect width='160' height='160' filter='url(%23n)'/></svg>\")")
CUC_CSS = """
:root{--brown:#2A160E;--cream:#FFFCF6;--thread:#FFFFFF;--mustard:#FFB800;--red:#FF2E4D;--teal:#00C2AE;--plum:#A148FF;--navy:#2D6BFF;--pink:#FF4FA8;--green:#21D45B}
.t{font-family:'Denk One';text-transform:uppercase}
.b{font-family:'Patrick Hand'}
.felt{background-image:FELT}
.stitch{position:absolute;inset:1px;border:3px dashed var(--thread);border-radius:inherit;pointer-events:none}
.coins{left:500px;top:8px;width:280px;height:78px;border-radius:39px;background-color:var(--mustard);border:4px solid var(--brown);
 box-shadow:0 5px 0 var(--brown)}
.coins img{position:absolute;left:9px;top:9px;width:54px;height:54px}
.coins .num{position:absolute;left:74px;top:0px;font-size:36px;color:#fff;-webkit-text-stroke:2.5px var(--brown);paint-order:stroke fill;text-shadow:2px 3px 0 var(--brown)}
.coins .rate{position:absolute;left:76px;top:44px;font-size:20px;color:var(--brown)}
.alert{left:410px;top:88px;width:460px;height:54px;border-radius:14px;background-color:var(--red);border:4px solid var(--brown);
 box-shadow:0 5px 0 var(--brown);color:var(--cream);display:flex;align-items:center;padding:0 14px}
.alert .h{font-size:28px;margin-right:12px;color:#fff;-webkit-text-stroke:2px var(--brown);paint-order:stroke fill}.alert .s{font-size:21px;flex:1;color:#fff}
.alert .clock{font-size:24px;background:var(--cream);color:var(--brown);border-radius:8px;padding:0 10px;transform:rotate(3deg)}
.ann{left:370px;top:150px;width:540px;height:36px;border-radius:8px;background-color:var(--cream);border:3px solid var(--brown);
 color:var(--brown);font-size:20px;display:flex;align-items:center;justify-content:center}
.ann em{font-style:normal;color:#E07B00}
.menu{left:16px;top:300px}
.disc{position:absolute;width:100px;height:100px;border-radius:50%;border:4px solid var(--brown);box-shadow:0 5px 0 var(--brown)}
.disc img{position:absolute;left:16px;top:16px;width:60px;height:60px}
.tag{position:absolute;height:26px;padding:0 10px 0 18px;background:var(--cream);border:2px solid var(--brown);border-radius:4px;
 color:var(--brown);font-size:18px;line-height:22px;white-space:nowrap}
.tag:before{content:'';position:absolute;left:5px;top:8px;width:6px;height:6px;border-radius:50%;background:var(--brown)}
.btn4{position:absolute;width:58px;height:58px;border-radius:50%;border:4px solid var(--brown);box-shadow:0 4px 0 var(--brown)}
.btn4 img{position:absolute;left:9px;top:9px;width:32px;height:32px}
.def{right:16px;top:398px;width:100px;height:100px;border-radius:50%;background-color:var(--red);border:4px solid var(--brown);box-shadow:0 5px 0 var(--brown)}
.def img{position:absolute;left:16px;top:16px;width:60px;height:60px}
.carry{left:420px;top:536px;width:440px;height:108px;border-radius:18px;background-color:var(--navy);border:4px solid var(--brown);box-shadow:0 5px 0 var(--brown)}
.carry img{position:absolute;left:16px;top:16px;width:70px;height:70px}
.carry .h{position:absolute;left:96px;top:12px;font-size:26px;color:#FFD23A;-webkit-text-stroke:2px var(--brown);paint-order:stroke fill}
.carry .s{position:absolute;left:98px;top:46px;font-size:20px;color:var(--cream)}
.carry .s b{color:#FF9A8A;font-weight:400}
.carry .n{position:absolute;left:98px;top:68px;font-size:16px;color:#C9D6E8}
.toast{right:16px;bottom:24px;height:52px;padding:0 16px 0 26px;background:var(--cream);border:3px solid var(--brown);border-radius:6px;
 box-shadow:0 4px 0 var(--brown);display:flex;align-items:center;gap:10px;font-size:22px;color:var(--brown);transform:rotate(-1.5deg)}
.toast:before{content:'';position:absolute;left:8px;top:20px;width:9px;height:9px;border-radius:50%;background:var(--brown)}
.toast img{width:32px;height:32px}.toast .g{color:#12A846}
.panel{left:210px;top:160px;width:860px;height:540px;border-radius:28px;background-color:var(--teal);border:5px solid var(--brown);box-shadow:0 7px 0 var(--brown)}
.label{position:absolute;left:50%;top:-30px;transform:translateX(-50%) rotate(-2deg);height:60px;padding:0 40px;background:var(--cream);
 border:4px solid var(--brown);border-radius:6px;font-size:38px;line-height:52px;color:var(--brown)}
.label:before,.label:after{content:'';position:absolute;top:8px;bottom:8px;width:0;border-left:3px dashed var(--brown)}
.label:before{left:4px}.label:after{right:4px}
.sew{position:absolute;right:-20px;top:-20px;width:58px;height:58px;border-radius:50%;background:var(--red);border:4px solid var(--brown);box-shadow:0 4px 0 var(--brown)}
.sew i{position:absolute;width:9px;height:9px;border-radius:50%;background:var(--brown)}
.sew b{position:absolute;left:24px;top:8px;width:3px;height:34px;background:var(--thread);transform:rotate(45deg);border-radius:2px}
.sew b+b{transform:rotate(-45deg)}
.tabs{position:absolute;left:0;right:0;top:46px;display:flex;justify-content:center;gap:14px}
.tab{height:44px;padding:0 22px;font-size:21px;line-height:38px;border-radius:10px;border:3px solid var(--brown);color:var(--brown);background-color:var(--mustard)}
.tab.on{background-color:var(--cream)}
.cards{position:absolute;left:28px;right:28px;top:110px;display:flex;gap:22px}
.card{position:relative;flex:1;height:270px;border-radius:16px;background-color:var(--cream);border:4px solid var(--brown)}
.card:nth-child(1){transform:rotate(-1deg)}.card:nth-child(3){transform:rotate(1.2deg)}
.card .stitch{border-color:#DCD3C4}
.card img{position:absolute;left:50%;top:16px;width:104px;height:104px;margin-left:-52px}
.card .h{position:absolute;left:0;right:0;top:124px;text-align:center;font-size:25px;color:var(--brown)}
.card .d{position:absolute;left:18px;right:18px;top:160px;text-align:center;font-size:19px;color:#6B5240;line-height:1.05}
.price{position:absolute;left:50%;bottom:14px;transform:translateX(-50%) rotate(-3deg);height:42px;padding:0 18px 0 30px;background:var(--red);
 border:3px solid var(--brown);border-radius:6px 21px 21px 6px;color:var(--cream);font-size:24px;line-height:36px;white-space:nowrap}
.price:before{content:'';position:absolute;left:9px;top:13px;width:10px;height:10px;border-radius:50%;background:var(--cream);border:2px solid var(--brown)}
.row2{position:absolute;left:28px;right:28px;top:404px;display:flex;gap:22px}
.row2 .card{height:116px}
"""


def cucito(panel: bool) -> str:
    colors = ["var(--red)", "var(--navy)", "var(--plum)", "var(--pink)", "var(--teal)", "var(--mustard)"]
    b = [f"<div class='abs coins felt'><div class='stitch'></div><img src='{icon('Coin')}'>"
         "<div class='num t'>$245K</div><div class='rate b'>+$1.25K/s</div></div>"]
    b.append("<div class='abs menu'>")
    for i, (ic, lab) in enumerate(MENU):
        x, y = (i % 3) * 112, (i // 3) * 140
        b.append(f"<div class='disc felt' style='left:{x}px;top:{y}px;background-color:{colors[i]}'><div class='stitch'></div>"
                 f"<img src='{icon(ic)}'></div><div class='tag b' style='left:{x + 2}px;top:{y + 106}px'>{lab.capitalize()}</div>")
    for i, (ic, col) in enumerate((("Codes", "var(--mustard)"), ("Settings", "#9AA3B8"))):
        b.append(f"<div class='btn4 felt' style='left:{i * 72}px;top:284px;background-color:{col}'><div class='stitch' style='border-width:2px'></div>"
                 f"<img src='{icon(ic)}'></div>")
    b.append("</div>")
    b.append(f"<div class='abs def felt'><div class='stitch'></div><img src='{icon('Barrier')}'></div>"
             "<div class='abs tag b' style='right:22px;top:506px'>Difesa</div>")
    if not panel:
        b.append("<div class='abs alert felt'><div class='stitch' style='border-width:2px'></div>"
                 "<div class='h t'>VALANGA!</div><div class='s b'>Corri in un rifugio!</div><div class='clock t'>0:12</div></div>")
        b.append("<div class='abs ann b'>Luca ha trovato un uovo&nbsp;<em>Leggendario</em>&nbsp;nel Canyon!</div>")
        b.append(f"<div class='abs carry felt'><div class='stitch'></div><img src='{icon('Egg')}'>"
                 "<div class='h t'>UOVO LEGGENDARIO ×2</div><div class='s b'>Velocità <b>-51%</b> · Pesante</div>"
                 "<div class='n b'>Portalo al tuo lotto in cima!</div></div>")
        b.append(f"<div class='abs toast b'><img src='{icon('CoinsSmall')}'>Hai raccolto <span class='g'>$3.4K</span></div>")
    else:
        b.append("<div class='shade'></div><div class='abs panel felt'><div class='stitch'></div>")
        b.append("<div class='label t'>Negozio</div><div class='sew'><i style='left:14px;top:14px'></i><i style='right:14px;top:14px'></i>"
                 "<i style='left:14px;bottom:14px'></i><i style='right:14px;bottom:14px'></i><b></b><b></b></div>")
        b.append("<div class='tabs'>" + "".join(
            f"<div class='tab t felt{' on' if i == 0 else ''}'>{t}</div>" for i, t in enumerate(TABS)) + "</div>")
        b.append("<div class='cards'>" + "".join(
            f"<div class='card felt'><div class='stitch'></div><img src='{icon(ic)}'><div class='h t'>{h}</div>"
            f"<div class='d b'>{d}</div><div class='price t'>R$ {p}</div></div>" for ic, h, d, p in CARDS) + "</div>")
        b.append("<div class='row2'>" + "".join(
            f"<div class='card felt'><div class='stitch'></div><img src='{icon(ic)}' style='width:70px;height:70px;margin-left:-35px;top:12px'>"
            f"<div class='h t' style='top:82px;font-size:21px'>{h}</div></div>"
            for ic, h in (("Backpack", "ZAINO GRANDE"), ("HatchSpeed", "SCHIUSA VELOCE"), ("Barrier", "SUPER BARRIERA"))) + "</div>")
        b.append("</div>")
    return page(CUC_CSS.replace("FELT", FELT), "".join(b))


# =========================================================================== FUMETTO
DOTS = "radial-gradient(rgba(20,20,20,.18) 1.6px,transparent 1.8px) 0 0/9px 9px"
FUM_CSS = """
:root{--ink:#141414;--paper:#FFFBEF;--yel:#FFD23F;--red:#F2545B;--blue:#3A86FF;--green:#2FB36C;--pink:#FF6FB5;--orange:#FF9F1C}
.t{font-family:'Bangers';letter-spacing:1px;text-transform:uppercase}
.b{font-family:'Ubuntu';font-weight:700}
.stk{border:4px solid var(--ink);box-shadow:5px 5px 0 var(--ink)}
.coins{left:505px;top:8px;width:270px;height:70px;background:var(--yel);border-radius:6px;transform:rotate(-1deg)}
.coins img{position:absolute;left:8px;top:6px;width:52px;height:52px}
.coins .num{position:absolute;left:68px;top:0px;font-size:46px;color:var(--ink)}
.coins .rate{position:absolute;right:-14px;bottom:-14px;background:var(--green);color:#fff;font-size:15px;padding:3px 9px;border:3px solid var(--ink);transform:rotate(4deg)}
.alert{left:420px;top:92px;width:440px;height:54px;background:var(--red);border-radius:4px;display:flex;align-items:center;padding:0 12px;color:#fff;transform:rotate(-1deg)}
.alert .h{font-size:34px;margin-right:12px;text-shadow:3px 3px 0 var(--ink)}.alert .s{font-size:16px;flex:1}
.alert .clock{font-size:26px;background:var(--paper);color:var(--ink);border:3px solid var(--ink);padding:0 8px;transform:rotate(3deg)}
.ann{left:380px;top:158px;width:520px;height:36px;background:var(--paper);border:3px solid var(--ink);box-shadow:3px 3px 0 var(--ink);
 font-size:15px;display:flex;align-items:center;justify-content:center;color:var(--ink)}
.ann em{font-style:normal;background:var(--orange);padding:0 5px;border:2px solid var(--ink);margin:0 5px}
.menu{left:16px;top:300px}
.st{position:absolute;width:100px;height:92px;border-radius:8px}
.st img{position:absolute;left:16px;top:10px;width:64px;height:64px}
.lab{position:absolute;padding:1px 8px;background:var(--paper);border:3px solid var(--ink);font-size:17px;color:var(--ink);white-space:nowrap}
.sm{position:absolute;width:60px;height:56px;border-radius:6px}
.sm img{position:absolute;left:9px;top:6px;width:36px;height:36px}
.def{right:20px;top:400px;width:96px;height:90px;background:var(--red);border-radius:8px;transform:rotate(3deg)}
.def img{position:absolute;left:14px;top:8px;width:62px;height:62px}
.carry{left:420px;top:548px;width:440px;height:90px;background:var(--paper);border-radius:6px}
.carry:before{content:'';position:absolute;inset:0;background:DOTS;opacity:.5}
.carry img{position:absolute;left:12px;top:6px;width:72px;height:72px}
.carry .h{position:absolute;left:96px;top:4px;font-size:32px;color:var(--orange);text-shadow:2px 2px 0 var(--ink)}
.carry .s{position:absolute;left:98px;top:44px;font-size:15px;color:var(--ink)}
.carry .s b{color:var(--red)}
.carry .n{position:absolute;left:98px;top:64px;font-size:13px;color:#555;font-weight:500}
.toast{right:20px;bottom:30px;height:54px;padding:0 18px;background:#fff;border-radius:26px;display:flex;align-items:center;gap:10px;font-size:17px;color:var(--ink)}
.toast:after{content:'';position:absolute;right:40px;bottom:-16px;width:18px;height:18px;background:#fff;border-right:4px solid var(--ink);border-bottom:4px solid var(--ink);transform:rotate(45deg) skew(10deg,10deg)}
.toast img{width:34px;height:34px}.toast .g{color:var(--green);font-family:'Bangers';font-size:24px;letter-spacing:1px}
.panel{left:210px;top:160px;width:860px;height:530px;background:var(--paper);border:5px solid var(--ink);box-shadow:9px 9px 0 var(--ink);border-radius:6px}
.panel:before{content:'';position:absolute;left:0;right:0;top:0;height:84px;background:DOTS,var(--blue)}
.cap{position:absolute;left:30px;top:-30px;padding:0 26px;height:64px;background:var(--yel);border:4px solid var(--ink);box-shadow:5px 5px 0 var(--ink);
 font-size:50px;line-height:60px;color:var(--ink);transform:rotate(-3deg)}
.close{position:absolute;right:-22px;top:-22px;width:56px;height:56px;background:var(--red);border:4px solid var(--ink);box-shadow:4px 4px 0 var(--ink);
 border-radius:50%;color:#fff;font-size:34px;text-align:center;line-height:50px;transform:rotate(8deg)}
.tabs{position:absolute;left:330px;top:22px;display:flex;gap:10px}
.tab{height:44px;padding:0 18px;font-size:24px;line-height:38px;border:4px solid var(--ink);background:#fff;color:var(--ink)}
.tab.on{background:var(--yel);box-shadow:4px 4px 0 var(--ink);transform:rotate(-2deg)}
.cards{position:absolute;left:28px;right:28px;top:110px;display:flex;gap:20px}
.card{position:relative;flex:1;height:270px;background:#fff;border:4px solid var(--ink);box-shadow:5px 5px 0 var(--ink)}
.card:before{content:'';position:absolute;right:0;top:0;width:90px;height:90px;background:DOTS;opacity:.7}
.card img{position:absolute;left:50%;top:14px;width:104px;height:104px;margin-left:-52px}
.card .h{position:absolute;left:0;right:0;top:122px;text-align:center;font-size:32px;color:var(--ink)}
.card .d{position:absolute;left:14px;right:14px;top:162px;text-align:center;font-size:14px;color:#444;line-height:1.25;font-weight:500}
.buy{position:absolute;left:24px;right:24px;bottom:14px;height:44px;background:var(--green);border:4px solid var(--ink);box-shadow:4px 4px 0 var(--ink);
 color:#fff;font-size:26px;text-align:center;line-height:38px;text-shadow:2px 2px 0 var(--ink)}
.row2{position:absolute;left:28px;right:28px;top:404px;display:flex;gap:20px}
.row2 .card{height:104px}
"""


def fumetto(panel: bool) -> str:
    colors = ["var(--green)", "var(--blue)", "#B07CFF", "var(--pink)", "#3CC6E8", "var(--orange)"]
    rots = [-3, 2, -2, 3, -2, 2]
    b = [f"<div class='abs coins stk'><img src='{icon('Coin')}'><div class='num t'>$245K</div><div class='rate b'>+$1.25K/s</div></div>"]
    b.append("<div class='abs menu'>")
    for i, (ic, lab) in enumerate(MENU):
        x, y = (i % 3) * 112, (i // 3) * 136
        b.append(f"<div class='st stk' style='left:{x}px;top:{y}px;background:{colors[i]};transform:rotate({rots[i]}deg)'><img src='{icon(ic)}'></div>"
                 f"<div class='lab t' style='left:{x + 6}px;top:{y + 92}px;transform:rotate({-rots[i] / 2}deg)'>{lab}</div>")
    for i, (ic, col) in enumerate((("Codes", "var(--yel)"), ("Settings", "#C9C9C9"))):
        b.append(f"<div class='sm stk' style='left:{i * 74}px;top:274px;background:{col}'><img src='{icon(ic)}'></div>")
    b.append("</div>")
    b.append(f"<div class='abs def stk'><img src='{icon('Barrier')}'></div><div class='abs lab t' style='right:30px;top:504px'>DIFESA</div>")
    if not panel:
        b.append("<div class='abs alert stk'><div class='h t'>VALANGA!</div><div class='s b'>Corri in un rifugio!</div><div class='clock t'>0:12</div></div>")
        b.append("<div class='abs ann b'>Luca ha trovato un uovo <em class='t'>LEGGENDARIO</em> nel Canyon!</div>")
        b.append(f"<div class='abs carry stk'><img src='{icon('Egg')}'><div class='h t'>UOVO LEGGENDARIO ×2</div>"
                 "<div class='s b'>Velocità <b>-51%</b> · Pesante</div><div class='n b'>Portalo al tuo lotto in cima!</div></div>")
        b.append(f"<div class='abs toast stk b'><img src='{icon('CoinsSmall')}'>Hai raccolto <span class='g'>$3.4K!</span></div>")
    else:
        b.append("<div class='shade'></div><div class='abs panel'>")
        b.append("<div class='cap t'>NEGOZIO</div><div class='close t'>✕</div>")
        b.append("<div class='tabs'>" + "".join(
            f"<div class='tab t{' on' if i == 0 else ''}'>{t}</div>" for i, t in enumerate(TABS)) + "</div>")
        b.append("<div class='cards'>" + "".join(
            f"<div class='card'><img src='{icon(ic)}'><div class='h t'>{h}</div><div class='d b'>{d}</div>"
            f"<div class='buy t'>R$ {p}</div></div>" for ic, h, d, p in CARDS) + "</div>")
        b.append("<div class='row2'>" + "".join(
            f"<div class='card'><img src='{icon(ic)}' style='width:62px;height:62px;margin-left:-31px;top:8px'>"
            f"<div class='h t' style='top:68px;font-size:26px'>{h}</div></div>"
            for ic, h in (("Backpack", "ZAINO GRANDE"), ("HatchSpeed", "SCHIUSA VELOCE"), ("Barrier", "SUPER BARRIERA"))) + "</div>")
        b.append("</div>")
    return page(FUM_CSS.replace("DOTS", DOTS), "".join(b))


STYLES = {"segnavia": segnavia, "cucito": cucito, "fumetto": fumetto}


def chromium() -> str:
    found = glob("/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell")
    if not found:
        raise SystemExit("Chromium non trovato")
    return sorted(found)[-1]


def shoot(html: str, png: Path) -> None:
    src = png.with_suffix(".html")
    src.write_text(html)
    subprocess.run([chromium(), "--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--allow-file-access-from-files", "--virtual-time-budget=3000", f"--window-size={W},{H}",
                    f"--screenshot={png}", src.as_uri()], check=True, capture_output=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in STYLES.items():
        shots = []
        for kind in ("hud", "panel"):
            png = OUT / f"{name}_{kind}.png"
            shoot(fn(kind == "panel"), png)
            shots.append(Image.open(png).convert("RGB"))
        both = Image.new("RGB", (W, 2 * H + 16), (20, 20, 24))
        both.paste(shots[0], (0, 0))
        both.paste(shots[1], (0, H + 16))
        both.save(OUT / f"{name}.png")
        print(f"[proposte] {name}: {OUT / f'{name}.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
