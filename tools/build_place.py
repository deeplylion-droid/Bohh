"""Crea build/TheRake.rbxlx da default.project.json e dagli script in src/.

Alternativa a `rojo build` senza dipendenze. Segue le stesse convenzioni di Rojo:
  init.server.luau -> Script, init.client.luau -> LocalScript, init.luau -> ModuleScript
  (la cartella diventa lo script e gli altri file i suoi figli);
  *.server.luau -> Script, *.client.luau -> LocalScript, *.luau -> ModuleScript, cartelle -> Folder.
"""
import json
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "default.project.json"
OUT = ROOT / "build" / "TheRake.rbxlx"

SCRIPT_SUFFIXES = [
    (".server.luau", "Script"),
    (".client.luau", "LocalScript"),
    (".luau", "ModuleScript"),
]

_ref = 0


def prop_xml(name, value):
    if isinstance(value, bool):
        return f'<bool name="{name}">{"true" if value else "false"}</bool>'
    if isinstance(value, int):
        return f'<int name="{name}">{value}</int>'
    if isinstance(value, float):
        return f'<float name="{name}">{value}</float>'
    if isinstance(value, str):
        return f'<string name="{name}">{escape(value)}</string>'
    raise ValueError(f"Tipo di proprietà non supportato per {name}: {value!r}")


def item(cls, name, children=(), source=None, properties=None):
    global _ref
    _ref += 1
    props = prop_xml("Name", name)
    for key, value in (properties or {}).items():
        props += prop_xml(key, value)
    if source is not None:
        assert "]]>" not in source, f"{name}: il sorgente contiene ']]>'"
        props += f'<ProtectedString name="Source"><![CDATA[{source}]]></ProtectedString>'
    inner = "".join(children)
    return f'<Item class="{cls}" referent="RBX{_ref}"><Properties>{props}</Properties>{inner}</Item>'


def script_kind(path):
    for suffix, cls in SCRIPT_SUFFIXES:
        if path.name.endswith(suffix):
            return path.name[: -len(suffix)], cls
    return None, None


def from_path(name, path):
    if path.is_file():
        _, cls = script_kind(path)
        assert cls, f"File non riconosciuto: {path}"
        return item(cls, name, source=path.read_text(encoding="utf-8"))

    init, init_cls = None, "Folder"
    children = []
    for child in sorted(path.iterdir()):
        base, cls = script_kind(child) if child.is_file() else (child.name, "Folder")
        if base is None:
            continue
        if child.is_file() and base == "init":
            init, init_cls = child, cls
            continue
        children.append(from_path(base, child))
    source = init.read_text(encoding="utf-8") if init else None
    return item(init_cls, name, children, source=source)


def from_node(name, node):
    if "$path" in node:
        return from_path(name, ROOT / node["$path"])
    children = [from_node(key, value) for key, value in node.items() if not key.startswith("$")]
    return item(node.get("$className", name), name, children, properties=node.get("$properties"))


project = json.loads(PROJECT.read_text(encoding="utf-8"))
tree = project["tree"]
services = [from_node(key, value) for key, value in tree.items() if not key.startswith("$")]

xml = (
    '<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">'
    + "".join(services)
    + "</roblox>"  # niente a-capo finale: Open Cloud lo rifiuta ("Invalid Content stream")
)

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(xml, encoding="utf-8")
print(f"Creato {OUT.relative_to(ROOT)}")
