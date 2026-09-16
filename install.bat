@echo off
REM ============================================================
REM  RindenSjakk - installer for hjemme-PC (Windows)
REM  Dobbeltklikk denne fila. Kjorer alt lokalt, ingen sky.
REM ============================================================
setlocal
cd /d "%~dp0"
echo.
echo === RindenSjakk installasjon ===
echo.

REM --- Python 3 ---
where python >nul 2>&1
if errorlevel 1 (
  echo [MANGLER] Python 3 er ikke installert.
  echo Aapner nedlastingssiden. Kryss av "Add python.exe to PATH" under installasjon,
  echo og kjor denne fila paa nytt etterpaa.
  start "" https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)
echo [OK] Python funnet.

REM --- Node.js (kreves av yt-dlp for YouTube) ---
where node >nul 2>&1
if errorlevel 1 (
  echo [MANGLER] Node.js er ikke installert ^(brukes til aa laste ned YouTube-video^).
  echo Aapner nedlastingssiden. Installer, og kjor denne fila paa nytt.
  start "" https://nodejs.org/en/download
  echo.
  pause
  exit /b 1
)
echo [OK] Node.js funnet.

REM --- virtuelt miljo + avhengigheter ---
echo.
echo Lager virtuelt miljo (.venv) ...
python -m venv .venv
if errorlevel 1 ( echo Kunne ikke lage venv. & pause & exit /b 1 )

echo Installerer avhengigheter ^(kan ta et par minutter^) ...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo Installasjon feilet. & pause & exit /b 1 )

echo.
echo ============================================================
echo  Ferdig!
echo   - Start appen:            dobbeltklikk  start.bat
echo   - Hent parti fra video:   hent.bat "https://youtu.be/..."
echo ============================================================
echo.
pause
