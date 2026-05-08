# -*- mode: python ; coding: utf-8 -*-
"""
AUTOavantar 打包配置 - PyWebView 启动器
使用方法: py310\python.exe -m PyInstaller desktop_launcher.spec

说明：
- 启动器使用 PyWebView 创建原生窗口嵌入 Vue 前端
- 调用外部 py310 环境运行后端
- 不打包任何 Python 依赖，所有依赖都在 py310 目录中
- exe 大小约 10-15MB
- 无控制台窗口（console=False）

注意：
- excludes 列表仅排除打包进 exe 内部的 Python 模块
- 这些模块不需要在启动器 exe 中，因为后端由外部 py310 运行
- 这与 build_release.ps1 的文件复制无关
"""

from pathlib import Path

# 项目根目录
project_root = Path(SPECPATH)

# 图标文件路径
icon_file = str(project_root / 'favicon.ico')

# 需要打包的 DLL 文件（来自 py310/Library/bin）
py310_lib_bin = project_root / 'py310' / 'Library' / 'bin'
binaries = []
for dll_name in ['ffi.dll', 'ffi-7.dll', 'ffi-8.dll', 'liblzma.dll', 'libbz2.dll']:
    dll_path = py310_lib_bin / dll_name
    if dll_path.exists():
        binaries.append((str(dll_path), '.'))

a = Analysis(
    ['desktop_launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=[],
    hiddenimports=[
        # PyWebView 核心
        'webview',
        'webview.platforms',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        # Windows API
        'win32event',
        'win32api',
        'win32con',
        # 系统托盘
        'pystray',
        'pystray._win32',
        'PIL',
        'PIL.Image',
        # pythonnet (PyWebView 依赖)
        'clr',
        'clr_loader',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除大型科学计算库
        'matplotlib', 'pandas', 'IPython', 'notebook', 'pytest',
        'sklearn', 'scipy', 'numpy', 'torch', 'transformers', 'diffusers',
        'librosa', 'soundfile', 'moviepy', 'cv2', 'onnxruntime',
        'gradio', 'pyarrow', 'sqlalchemy', 'openai', 'huggingface_hub',
        # 排除后端相关（后端由外部 py310 运行）
        'uvicorn', 'fastapi', 'starlette', 'pydantic', 'click', 'anyio',
        # 排除不需要的 GUI 框架
        'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)
