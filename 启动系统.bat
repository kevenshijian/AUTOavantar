@echo off
chcp 65001 >nul
title AUTOavantar 数字人视频生成系统

echo ========================================
echo   AUTOavantar 数字人视频生成系统
echo   版本: 1.1.0
echo ========================================
echo.

REM 检查 Python 环境
if not exist "py310\python.exe" (
    echo [错误] 未找到 Python 环境: py310\python.exe
    echo 请确保 py310 目录存在
    pause
    exit /b 1
)

REM 切换到 backend 目录
cd backend

REM 启动后端服务
echo [启动] 正在启动后端服务...
echo.
..\py310\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 9010

pause
