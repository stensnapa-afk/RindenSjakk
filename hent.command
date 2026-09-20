#!/bin/bash
# ============================================================
#  RindenSjakk - hent trekk fra en sjakkvideo -> PGN (Mac).
#  Dobbeltklikk (spor om lenke), eller: ./hent.command "https://youtu.be/..."
#  (Windows: bruk hent.bat)
# ============================================================
cd "$(dirname "$0")" || exit 1
if [ ! -x "./.venv/bin/python" ]; then
  echo "Kjor install.command forst."
  read -r -p "Trykk Enter for a lukke..."
  exit 1
fi
URL="$1"
if [ -z "$URL" ]; then
  read -r -p "Lim inn YouTube-lenke: " URL
fi
if [ -z "$URL" ]; then
  echo "Ingen lenke oppgitt."
  read -r -p "Trykk Enter for a lukke..."
  exit 1
fi
"./.venv/bin/python" engine/process_video.py "$URL"
echo ""
read -r -p "Trykk Enter for a lukke..."
