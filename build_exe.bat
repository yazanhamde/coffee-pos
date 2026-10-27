@echo off
REM ============================================================
REM Build love.jo POS (Windows 7 / Python 3.8 32-bit)
REM Produces an onedir build: dist\coffee_pos\coffee_pos.exe
REM ============================================================
REM Requirements before running:
REM   1) Python 3.8.x 32-bit must be installed
REM      Download: https://www.python.org/downloads/release/python-3810/
REM      (choose "Windows installer (32-bit)", not 64-bit)
REM   2) Run this file from inside the project folder (coffee_pos)
REM ============================================================
REM NOTE: after building, copy the WHOLE dist\coffee_pos folder
REM to the shop computer, not just the .exe file alone.
REM ============================================================

echo [0/4] Checking Python 3.8 (32-bit)...
py -3.8-32 --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python 3.8 32-bit not found via py launcher.
  echo Install it from: https://www.python.org/downloads/release/python-3810/
  pause
  exit /b 1
)
py -3.8-32 --version

echo [1/4] Installing requirements...
py -3.8-32 -m pip install -r requirements.txt

echo [2/4] Cleaning previous build...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q coffee_pos.spec 2>nul

echo [3/4] Building executable (onedir mode)...
py -3.8-32 -m PyInstaller --noconfirm --onedir --windowed --name "coffee_pos" --add-data "ui;ui" --add-data "database;database" --add-data "utils;utils" --add-data "assets;assets" main.py

if not exist "dist\coffee_pos\coffee_pos.exe" (
  echo.
  echo WARNING: exe not created in dist\coffee_pos folder. Check errors above.
  pause
  exit /b 1
)

echo [4/4] Done! Executable folder is in dist\coffee_pos
echo IMPORTANT: copy the WHOLE dist\coffee_pos folder to the shop computer, not just the exe file.
pause
