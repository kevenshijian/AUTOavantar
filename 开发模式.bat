@echo off
chcp 65001 >nul
title AUTOavantar 开发模式

echo ========================================
echo   AUTOavantar 开发模式
echo ========================================
echo.

REM 检查 Python 环境
if not exist "py310\python.exe" (
    echo [错误] 未找到 Python 环境: py310\python.exe
    pause
    exit /b 1
)

echo [1/3] 启动后端服务 (端口 9010)...
start "Backend" cmd /c "cd backend && ..\py310\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 9010 --reload"

echo [2/3] 等待后端启动...
timeout /t 5 /nobreak >nul

echo [3/3] 启动前端开发服务 (端口 5173)...
cd frontend
start "Frontend" cmd /c "npm run dev"

echo.
echo ========================================
echo   开发环境已启动
echo   后端: http://localhost:9010
echo   前端: http://localhost:5173
echo   API文档: http://localhost:9010/docs
echo ========================================
echo.

pause
