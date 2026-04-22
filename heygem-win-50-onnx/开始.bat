echo off
set GRADIO_TEMP_DIR=%cd%\tmp\
SET PYTHON_PATH=%cd%\py39\
set USE_ONNX=true
rem overriding default python env vars in order not to interfere with any system python installation
SET PYTHONHOME=
SET PYTHONPATH=
SET PYTHONEXECUTABLE=%PYTHON_PATH%\python.exe
SET PYTHONWEXECUTABLE=%PYTHON_PATH%pythonw.exe
SET PYTHON_EXECUTABLE=%PYTHON_PATH%\python.exe
SET PYTHONW_EXECUTABLE=%PYTHON_PATH%pythonw.exe
SET PYTHON_BIN_PATH=%PYTHON_EXECUTABLE%
SET PYTHON_LIB_PATH=%PYTHON_PATH%\Lib\site-packages
set CU_PATH=%PYTHON_PATH%\Lib\site-packages\torch\lib
set cuda_PATH=%PYTHON_PATH%\Library\bin
SET FFMPEG_PATH=%cd%\py39\ffmpeg\bin
SET PATH=%PYTHON_PATH%;%PYTHON_PATH%\Scripts;%FFMPEG_PATH%;%CU_PATH%;%cuda_PATH%;%PATH%
set HF_ENDPOINT=https://hf-mirror.com
set HF_HOME=%CD%\hf_download
set TRANSFORMERS_CACHE=%CD%\tf_download
set XFORMERS_FORCE_DISABLE_TRITON=1
@REM set CUDA_VISIBLE_DEVICES=0
@REM set PYTHONPATH=third_party/AcademiCodec;third_party/Matcha-TTS
set PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

"%PYTHON_EXECUTABLE%" -s app.py
pause
