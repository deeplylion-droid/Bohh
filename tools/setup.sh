#!/usr/bin/env bash
# Installa gli strumenti di sviluppo in .tools/ (non versionato):
# Rojo, Lune, StyLua, Selene, luau-lsp + Python venv con Blender (bpy) e librerie.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/.tools"
BIN="$TOOLS/bin"
mkdir -p "$BIN" "$TOOLS/dl"

ROJO=7.7.1; LUNE=0.10.5; STYLUA=2.5.2; SELENE=0.32.0; LUAU_LSP=1.70.1

fetch() { # url zipname
  local out="$TOOLS/dl/$2"
  [ -s "$out" ] || curl -fsSL -o "$out" "$1"
  python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$out" "$BIN"
}
fetch "https://github.com/rojo-rbx/rojo/releases/download/v$ROJO/rojo-$ROJO-linux-x86_64.zip" rojo.zip
fetch "https://github.com/lune-org/lune/releases/download/v$LUNE/lune-$LUNE-linux-x86_64.zip" lune.zip
fetch "https://github.com/JohnnyMorganz/StyLua/releases/download/v$STYLUA/stylua-linux-x86_64.zip" stylua.zip
fetch "https://github.com/Kampfkarren/selene/releases/download/$SELENE/selene-$SELENE-linux.zip" selene.zip
fetch "https://github.com/JohnnyMorganz/luau-lsp/releases/download/$LUAU_LSP/luau-lsp-linux-x86_64.zip" luau-lsp.zip
chmod +x "$BIN"/*

# Definizioni dei tipi Roblox per luau-lsp
DEFS="$TOOLS/globalTypes.d.luau"
[ -s "$DEFS" ] || curl -fsSL -o "$DEFS" "https://raw.githubusercontent.com/JohnnyMorganz/luau-lsp/main/scripts/globalTypes.d.luau"

# Python: Blender come modulo + librerie per mesh e API
if [ ! -x "$TOOLS/venv/bin/python" ]; then
  python3 -m venv "$TOOLS/venv"
  "$TOOLS/venv/bin/pip" install -q --upgrade pip
fi
"$TOOLS/venv/bin/pip" install -q bpy==5.2.2 numpy requests scikit-image trimesh pillow
echo "Strumenti pronti in $TOOLS"
