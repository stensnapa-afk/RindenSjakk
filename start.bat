@echo off
REM RindenSjakk — start den lokale vieweren (kun denne PC-en, ingen sky).
REM Krever Python 3. Dobbeltklikk denne fila.
cd /d "%~dp0viewer"
start "" http://localhost:8777/
echo RindenSjakk kjorer paa http://localhost:8777/  (lukk dette vinduet for aa stoppe)
python -m http.server 8777 --bind 127.0.0.1
