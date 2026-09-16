@echo off
REM Hent trekk fra en sjakkvideo -> PGN. Bruk: hent.bat "https://youtu.be/..."
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Bruk: hent.bat "https://www.youtube.com/watch?v=..."  [--start 0] [--interval 0.8]
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Kjor install.bat forst.
  exit /b 1
)
".venv\Scripts\python.exe" engine\process_video.py %*
