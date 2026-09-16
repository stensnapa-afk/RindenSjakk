@echo off
REM RindenSjakk - start den lokale vieweren (kun denne PC-en, ingen sky).
REM Dobbeltklikk denne fila. Bruker venv om det finnes, ellers system-Python.
setlocal
cd /d "%~dp0"
set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
start "" http://localhost:8777/
echo RindenSjakk kjorer paa http://localhost:8777/  (lukk dette vinduet for aa stoppe)
cd viewer
%PY% -m http.server 8777 --bind 127.0.0.1
