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
set BACKEND_DIR=%SCRIPT_DIR%backend
set FRONTEND_DIR=%SCRIPT_DIR%frontend
set PATH=%SCRIPT_DIR%node-v24.15.0-win-x64;%PATH%

REM Python Env
set PYTHON_PATH=%SCRIPT_DIR%py310\
if not exist "%PYTHON_PATH%" (
    echo [ERROR] Python directory not found: %PYTHON_PATH%
    echo Please ensure 'py310' folder exists in current directory.
    pause
    exit /b 1
)

set PYTHONEXECUTABLE=%PYTHON_PATH%python.exe
set FFMPEG_PATH=%PYTHON_PATH%ffmpeg\bin
set CU_PATH=%PYTHON_PATH%Lib\site-packages\torch\lib
set CUDA_BIN_PATH=%PYTHON_PATH%Library\bin

REM Set PATH (Prepend custom paths)
set PATH=%PYTHON_PATH%;%PYTHON_PATH%Scripts;%FFMPEG_PATH%;%CU_PATH%;%CUDA_BIN_PATH%;%PATH%

REM AI Env Vars
set GRADIO_TEMP_DIR=%SCRIPT_DIR%tmp\
set USE_ONNX=true
set DS_BUILD_AIO=0
set DS_BUILD_SPARSE_ATTN=0
set HF_ENDPOINT=https://hf-mirror.com
set HF_HOME=%CD%\hf_download
set TRANSFORMERS_CACHE=%CD%\tf_download
set XFORMERS_FORCE_DISABLE_TRITON=1
set PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
set HF_HUB_OFFLINE=0
set TRANSFORMERS_OFFLINE=0

echo [OK] Environment variables loaded.
echo [INFO] Python: %PYTHONEXECUTABLE%
echo.

echo ========================================
echo    Starting Services...
echo ========================================
echo.

REM [1/5] Start IndexTTS
echo [1/5] Starting IndexTTS...
if exist "%SCRIPT_DIR%index-tts-2\app.py" (
    start "IndexTTS" cmd /c "cd /d "%SCRIPT_DIR%index-tts-2" && "%PYTHONEXECUTABLE%" -m uvicorn api_server.main:app --host 0.0.0.0 --port 7860 --reload"
    echo [OK] IndexTTS started.
) else (
    echo [SKIP] index-tts-2\app.py not found.
)
timeout /t 5 /nobreak >nul

REM [2/5] Start HeyGem
echo [2/5] Starting HeyGem...
if exist "%SCRIPT_DIR%heygem-win-50-onnx\app.py" (
    start "HeyGem" cmd /c "cd /d "%SCRIPT_DIR%heygem-win-50-onnx" && "%PYTHONEXECUTABLE%" app.py"
    echo [OK] HeyGem started.
) else (
    echo [SKIP] heygem-win-50-onnx\app.py not found.
)
timeout /t 5 /nobreak >nul

REM [3/5] Start FastAPI Backend
echo [3/5] Starting FastAPI Backend...
if exist "%BACKEND_DIR%\api\main.py" (
    start "FastAPI Backend" cmd /c "cd /d "%BACKEND_DIR%" && "%PYTHONEXECUTABLE%" -m uvicorn api.main:app --host 0.0.0.0 --port 9010 --reload"
    echo [OK] FastAPI Backend started.
) else (
    echo [ERROR] Backend entry not found: %BACKEND_DIR%\api\main.py
)
timeout /t 5 /nobreak >nul

REM [4/5] Start Vue3 Frontend
echo [4/5] Starting Vue3 Frontend...
if exist "%FRONTEND_DIR%\package.json" (
    where npm >nul 2>nul
    if %errorlevel% neq 0 (
        echo [WARN] npm not found. Please install Node.js.
    )
    start "Vue3 Frontend" cmd /c "cd /d "%FRONTEND_DIR%" && npm run dev"
    echo [OK] Vue3 Frontend started.
) else (
    echo [SKIP] Frontend package.json not found.
)
timeout /t 5 /nobreak >nul

REM [5/5] Open Browser
echo [5/5] Opening browser...
timeout /t 3 /nobreak >nul
start http://localhost:5173