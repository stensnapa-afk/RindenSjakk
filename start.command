#!/bin/bash
# ============================================================
#  RindenSjakk - start hele appen (viewer + video-motor) pa Mac.
#  Kjorer en lokal server pa denne maskinen. Ingen sky.
#  Dobbeltklikk i Finder. (Windows: bruk start.bat)
#  Bruker .venv om det finnes (fra install.command), ellers python3.
# ============================================================
cd "$(dirname "$0")" || exit 1
PY="python3"
if [ -x "./.venv/bin/python" ]; then PY="./.venv/bin/python"; fi
"$PY" server.py
