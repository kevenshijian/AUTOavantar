@echo off
chcp 65001 >nul
title AUTOavantar 打包发行版

echo ========================================
echo   AUTOavantar 打包发行版
echo ========================================
echo.

REM 检查 Python 环境
if not exist "py310\python.exe" (
    echo [错误] 未找到 Python 环境: py310\python.exe
    pause
    exit /b 1
)

REM 检查 PyInstaller
..\py310\python.exe -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [安装] 正在安装 PyInstaller...
    ..\py310\python.exe -m pip install pyinstaller
)

echo [1/4] 清理旧的打包文件...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

echo [2/4] 构建前端...
cd frontend
call npm run build
cd ..

echo [3/4] 打包后端...
cd backend
..\py310\python.exe -m PyInstaller ../desktop_launcher.py --name AUTOavantar --onefile --windowed --add-data "../frontend/dist;frontend/dist" --add-data "../config;config" --add-data "../Portrait;Portrait" --add-data "../voicel;voicel" --add-data "../engines;engines" --hidden-import uvicorn --hidden-import fastapi --hidden-import pydantic
cd ..

echo [4/4] 复制必要文件...
if not exist "dist" mkdir dist
copy backend\dist\AUTOavantar.exe dist\

echo.
echo ========================================
echo   打包完成！
echo   输出文件: dist\AUTOavantar.exe
echo ========================================
echo.

pause