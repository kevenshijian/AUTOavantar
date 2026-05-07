# -*- mode: python ; coding: utf-8 -*-
"""
AUTOavantar 打包配置 - 轻量级启动器
使用方法: py310\python.exe -m PyInstaller desktop_launcher.spec

说明：
- 启动器只是一个简单的包装器，调用外部 py310 环境运行后端
- 不打包任何 Python 依赖，所有依赖都在 py310 目录中
- exe 大小约 7MB
"""

from pathlib import Path

# 项目根目录
project_root = Path(SPECPATH)

a = Analysis(
    ['desktop_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[],  # 不打包数据文件
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除所有不需要的模块
        'tkinter', 'matplotlib', 'pandas', 'IPython', 'notebook', 'pytest',
        'sklearn', 'scipy', 'numpy', 'torch', 'transformers', 'diffusers',
        'librosa', 'soundfile', 'moviepy', 'cv2', 'onnxruntime', 'PIL',
        'gradio', 'pyarrow', 'sqlalchemy', 'openai', 'huggingface_hub',
        'uvicorn', 'fastapi', 'starlette', 'pydantic', 'click', 'anyio',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AUTOavantar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'favicon.ico') if (project_root / 'favicon.ico').exists() else None,
)
