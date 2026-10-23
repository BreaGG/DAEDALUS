@echo off
setlocal
cd /d "%~dp0"
title DAEDALUS
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
    echo [DAEDALUS] Creating virtual environment...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 (
        echo Python 3.11+ not found. Install it from https://www.python.org/downloads/
        pause
        exit /b 1
    )
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo Could not install dependencies.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m daedalus %*
pause
