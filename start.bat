@echo off
REM ============================================================
REM  RindenSjakk - start hele appen (viewer + video-motor).
REM  Kjorer en lokal server paa denne PC-en. Ingen sky.
REM  Bruker .venv om det finnes (fra install.bat), ellers system-Python.
REM ============================================================
setlocal
cd /d "%~dp0"
set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
"%PY%" server.py
