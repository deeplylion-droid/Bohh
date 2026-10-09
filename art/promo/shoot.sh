#!/usr/bin/env bash
# Fotografa una pagina HTML con Chromium headless: shoot.sh pagina.html out.png 1920 1080
set -euo pipefail
HTML="$(realpath "$1")"
OUT="$(realpath -m "$2")"
W="${3:-1920}"
H="${4:-1080}"
SHELL_BIN=$(ls -d /opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell 2>/dev/null | head -1)
"$SHELL_BIN" --no-sandbox --hide-scrollbars --force-device-scale-factor=1 \
  --window-size="$W,$H" --screenshot="$OUT" "file://$HTML" >/dev/null 2>&1
echo "salvato $OUT"
