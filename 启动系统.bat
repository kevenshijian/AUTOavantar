@echo off
chcp 65001 >nul
title AUTOavantar

echo ============================================================
echo   AUTOavantar Digital Human Video Generation System
echo   Version: 1.2.0
echo   Mode: Engine Mode
echo ============================================================
echo.
echo Starting service, please wait...
echo.
echo Service URL: http://localhost:9010
echo API Docs: http://localhost:9010/docs
echo.
echo Note: TTS and HeyGem engines will be loaded automatically
echo       First startup may take longer, please wait...
echo.

cd /d "%~dp0"

if exist "py310\python.exe" (
    set PYTHON_EXE=py310\python.exe
) else (
    set PYTHON_EXE=python
)

set PYTHONPATH=%~dp0

%PYTHON_EXE% desktop_launcher.py

pause