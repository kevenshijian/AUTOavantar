@echo off
:: Force UTF-8 output for console (must be executed before any Chinese output if using ANSI file with chcp)
chcp 65001 >nul 2>&1

title Digital Human Video System Starter

echo ========================================
echo    Digital Human Video System - Starter
echo ========================================
echo.

REM ================= Environment Config =================
set SCRIPT_DIR=%~dp0
set PYTHON_EXE=%SCRIPT_DIR%py310\python.exe
"%PYTHON_EXE%" start_system.py