@echo off
setlocal
cd /d "%~dp0"
python -c "import pygame" >nul 2>nul
if errorlevel 1 (
    echo Installing Pygame...
    python -m pip install -r requirements.txt
    if errorlevel 1 pause & exit /b 1
)
python poker.py
if errorlevel 1 pause
