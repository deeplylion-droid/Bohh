"""Crea build/CoinRush.rbxlx dagli script in src/ (alternativa a `rojo build`, senza dipendenze)."""
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
OUT = ROOT / "build" / "CoinRush.rbxlx"

_ref = 0


def item(cls, name, children=(), source=None):
    global _ref
    _ref += 1
    props = f'<string name="Name">{escape(name)}</string>'
    if source is not None:
        assert "]]>" not in source, f"{name}: il sorgente contiene ']]>'"
        props += f'<ProtectedString name="Source"><![CDATA[{source}]]></ProtectedString>'
    inner = "".join(children)
    return f'<Item class="{cls}" referent="RBX{_ref}"><Properties>{props}</Properties>{inner}</Item>'


def read(rel):
    return (SRC / rel).read_text(encoding="utf-8")


tree = [
    item("ReplicatedStorage", "ReplicatedStorage", [
        item("Folder", "Shared", [
            item("ModuleScript", "Config", source=read("shared/Config.luau")),
        ]),
    ]),
    item("ServerScriptService", "ServerScriptService", [
        item("Script", "GameMode", [
            item("ModuleScript", "Arena", source=read("server/GameMode/Arena.luau")),
            item("ModuleScript", "Coins", source=read("server/GameMode/Coins.luau")),
        ], source=read("server/GameMode/init.server.luau")),
    ]),
    item("StarterPlayer", "StarterPlayer", [
        item("StarterPlayerScripts", "StarterPlayerScripts", [
            item("LocalScript", "HUD", source=read("client/HUD.client.luau")),
        ]),
    ]),
]

xml = (
    '<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">'
    + "".join(tree)
    + "</roblox>\n"
)

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(xml, encoding="utf-8")
print(f"Creato {OUT.relative_to(ROOT)}")
