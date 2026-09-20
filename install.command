#!/bin/bash
# ============================================================
#  RindenSjakk - installer for Mac. Dobbeltklikk i Finder.
#  Kjorer alt lokalt, ingen sky. (Windows: bruk install.bat)
#  Forste gang: hoyreklikk -> Apne (Gatekeeper).
# ============================================================
cd "$(dirname "$0")" || exit 1
echo ""
echo "=== RindenSjakk installasjon (Mac) ==="
echo ""

# --- Python 3 ---
if ! command -v python3 >/dev/null 2>&1; then
  echo "[MANGLER] Python 3 er ikke installert."
  echo "Installer fra https://www.python.org/downloads/  (eller: brew install python)"
  echo "og kjor denne fila pa nytt etterpa."
  command -v open >/dev/null 2>&1 && open "https://www.python.org/downloads/"
  echo ""
  read -r -p "Trykk Enter for a avslutte..."
  exit 1
fi
echo "[OK] Python 3 funnet: $(python3 --version 2>&1)"

# --- Node.js (kreves av yt-dlp for YouTube) ---
if ! command -v node >/dev/null 2>&1; then
  echo "[MANGLER] Node.js (brukes til a laste ned YouTube-video)."
  echo "Installer fra https://nodejs.org/en/download  (eller: brew install node)"
  echo "og kjor denne fila pa nytt."
  command -v open >/dev/null 2>&1 && open "https://nodejs.org/en/download"
  echo ""
  read -r -p "Trykk Enter for a avslutte..."
  exit 1
fi
echo "[OK] Node.js funnet: $(node --version 2>&1)"

# --- virtuelt miljo + avhengigheter ---
echo ""
echo "Lager virtuelt miljo (.venv) ..."
python3 -m venv .venv || { echo "Kunne ikke lage venv."; read -r -p "Enter..."; exit 1; }

echo "Installerer avhengigheter (kan ta et par minutter) ..."
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt || { echo "Installasjon feilet."; read -r -p "Enter..."; exit 1; }

echo ""
echo "============================================================"
echo "  Ferdig!"
echo "   - Start appen:          dobbeltklikk  start.command"
echo "   - Hent parti fra video: dobbeltklikk  hent.command"
echo "============================================================"
echo ""
read -r -p "Trykk Enter for a lukke..."
