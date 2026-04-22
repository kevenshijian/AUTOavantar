"""
一键启动系统脚本

双击此脚本即可启动整个系统：
- IndexTTS (端口 7860) - 独立控制台窗口
- HeyGem (端口 9889) - 独立控制台窗口
- FastAPI 后端 (端口 9010) - 独立控制台窗口
- Vue3 前端 (端口 5173) - 独立控制台窗口

每个服务都有独立的控制台窗口，方便查看日志和排查错误。

支持开发模式和打包模式（sys.frozen）
"""

import os
import sys
import subprocess
import time
from pathlib import Path


def get_base_dir() -> Path:
    """
    获取基础目录

    打包模式下（sys.frozen），返回 EXE 所在目录
    开发模式下，返回脚本所在目录

    → AC-217
    """
    if getattr(sys, 'frozen', False):
        # 打包模式：EXE 所在目录
        return Path(sys.executable).parent.resolve()
    else:
        # 开发模式：脚本所在目录
        return Path(__file__).parent.resolve()


def setup_environment(base_dir: Path) -> dict:
    """
    设置环境变量

    与 启动系统.bat 完全一致的环境变量设置

    → AC-212
    """
    env = os.environ.copy()

    # Python 环境路径
    py310_path = base_dir / "py310"
    if not py310_path.exists():
        raise FileNotFoundError(f"Python 目录不存在: {py310_path}")

    # 基础路径
    python_exe = py310_path / "python.exe"
    ffmpeg_path = py310_path / "ffmpeg" / "bin"
    cu_path = py310_path / "Lib" / "site-packages" / "torch" / "lib"
    cuda_bin_path = py310_path / "Library" / "bin"
    node_path = base_dir / "node-v24.15.0-win-x64"

    # PATH：前置所有自定义路径
    path_parts = [
        str(node_path),
        str(py310_path),
        str(py310_path / "Scripts"),
        str(ffmpeg_path),
        str(cu_path),
        str(cuda_bin_path),
        env.get("PATH", "")
    ]
    env["PATH"] = os.pathsep.join(path_parts)

    # Python 可执行文件
    env["PYTHONEXECUTABLE"] = str(python_exe)

    # FFmpeg 和 CUDA 路径
    env["FFMPEG_PATH"] = str(ffmpeg_path)
    env["CU_PATH"] = str(cu_path)
    env["CUDA_BIN_PATH"] = str(cuda_bin_path)

    # AI 环境变量
    env["GRADIO_TEMP_DIR"] = str(base_dir / "tmp")
    env["USE_ONNX"] = "true"
    env["DS_BUILD_AIO"] = "0"
    env["DS_BUILD_SPARSE_ATTN"] = "0"
    env["HF_ENDPOINT"] = "https://hf-mirror.com"
    env["HF_HOME"] = str(base_dir / "hf_download")
    env["TRANSFORMERS_CACHE"] = str(base_dir / "tf_download")
    env["XFORMERS_FORCE_DISABLE_TRITON"] = "1"
    env["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"

    return env


def start_service_with_console(
    name: str,
    cmd: list,
    cwd: Path,
    env: dict,
) -> subprocess.Popen:
    """
    启动服务（独立控制台窗口）

    使用 Windows start 命令启动服务，每个服务都有独立的控制台窗口。
    日志直接输出到控制台，方便查看和调试。

    Args:
        name: 服务名称（用于窗口标题）
        cmd: 命令列表
        cwd: 工作目录
        env: 环境变量

    Returns:
        subprocess.Popen 实例
    """
    print(f"[启动] {name}...")

    if sys.platform != "win32":
        # 非 Windows 平台，使用普通方式启动
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
        )
        print(f"[OK] {name} 已启动 (PID: {proc.pid})")
        return proc

    # Windows 平台：使用 start 命令启动独立控制台窗口
    # 构建完整的命令字符串
    cmd_str = ' '.join(f'"{c}"' if ' ' in c else c for c in cmd)

    # start 命令格式: start "title" cmd /c "cd /d path && command"
    # 使用 shell=True 执行 start 命令
    full_cmd = f'start "{name}" cmd /c "cd /d "{cwd}" && {cmd_str}"'

    proc = subprocess.Popen(
        full_cmd,
        env=env,
        shell=True,
    )

    print(f"[OK] {name} 已启动（独立控制台窗口）")
    return proc


def check_low_memory_mode(base_dir: Path) -> bool:
    """
    检查是否启用低显存模式

    通过读取系统配置文件判断

    Args:
        base_dir: 项目根目录

    Returns:
        bool: 是否启用低显存模式
    """
    import json

    # 尝试读取系统配置文件（JSON 格式）
    config_path = base_dir / "backend" / "data" / "system_config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                low_memory_mode = config.get('low_memory_mode', False)
                if low_memory_mode:
                    print(f"[INFO] 检测到低显存模式已启用")
                    return True
        except Exception as e:
            print(f"[WARN] 读取系统配置失败: {e}")

    return False


def main():
    """
    主函数：依次启动所有服务

    → AC-198
    """
    print("=" * 60)
    print("   Digital Human Video System - Starter")
    print("   每个服务将在独立控制台窗口中运行")
    print("=" * 60)
    print()

    # 获取基础目录
    base_dir = get_base_dir()
    print(f"[INFO] 基础目录: {base_dir}")

    # 设置环境变量
    try:
        env = setup_environment(base_dir)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        print("请确保 'py310' 文件夹存在于当前目录。")
        input("按回车键退出...")
        sys.exit(1)
        return

    python_exe = env["PYTHONEXECUTABLE"]
    print(f"[OK] 环境变量已加载")
    print(f"[INFO] Python: {python_exe}")
    print()

    # 检查低显存模式
    low_memory_mode = check_low_memory_mode(base_dir)

    print("=" * 60)
    print("   启动服务...")
    print("=" * 60)
    print()

    # [1/4] 启动 IndexTTS（低显存模式下跳过）
    # if low_memory_mode:
    #     print("[SKIP] 低显存模式：跳过 IndexTTS 启动（任务执行时按需启动）")
    # else:
    #     indextts_dir = base_dir / "index-tts-2"
    #     if (indextts_dir / "app.py").exists():
    #         start_service_with_console(
    #             name="IndexTTS",
    #             cmd=[python_exe, "-m", "uvicorn", "api_server.main:app",
    #                  "--host", "0.0.0.0", "--port", "7860", "--reload"],
    #             cwd=indextts_dir,
    #             env=env,
    #         )
    #     else:
    #         print("[SKIP] index-tts-2/app.py 不存在")

    #     time.sleep(5)

    # # [2/4] 启动 HeyGem（低显存模式下跳过）
    # if low_memory_mode:
    #     print("[SKIP] 低显存模式：跳过 HeyGem 启动（任务执行时按需启动）")
    # else:
    #     heygem_dir = base_dir / "heygem-win-50-onnx"
    #     if (heygem_dir / "app.py").exists():
    #         start_service_with_console(
    #             name="HeyGem",
    #             cmd=[python_exe, "app.py"],
    #             cwd=heygem_dir,
    #             env=env,
    #         )
    #     else:
    #         print("[SKIP] heygem-win-50-onnx/app.py 不存在")

    #     time.sleep(5)

    # [3/4] 启动 FastAPI 后端
    backend_dir = base_dir / "backend"
    if (backend_dir / "api" / "main.py").exists():
        start_service_with_console(
            name="FastAPI Backend",
            cmd=[python_exe, "-m", "uvicorn", "api.main:app",
                 "--host", "0.0.0.0", "--port", "9010", "--reload"],
            cwd=backend_dir,
            env=env,
        )
    else:
        print("[ERROR] backend/api/main.py 不存在")

    time.sleep(5)

    # [4/4] 启动前端
    frontend_dir = base_dir / "frontend"

    # 打包模式：优先使用 frontend.exe
    frontend_exe = frontend_dir / "frontend.exe"
    if frontend_exe.exists():
        start_service_with_console(
            name="Vue3 Frontend",
            cmd=[str(frontend_exe)],
            cwd=frontend_dir,
            env=env,
        )
    elif (frontend_dir / "package.json").exists():
        # 开发模式：使用 npm run dev
        npm_cmd = base_dir / "node-v24.15.0-win-x64" / "npm.cmd"
        start_service_with_console(
            name="Vue3 Frontend",
            cmd=[str(npm_cmd), "run", "dev"],
            cwd=frontend_dir,
            env=env,
        )
    else:
        print("[SKIP] frontend 不存在")

    time.sleep(3)

    # 打开浏览器
    print()
    print("=" * 60)
    print("   [完成] 所有服务已启动")
    print("=" * 60)
    print()
    print("   每个服务都在独立的控制台窗口中运行")
    print("   关闭对应的控制台窗口即可停止服务")
    print()
    print("   正在打开浏览器...")
    print()

    if sys.platform == "win32":
        os.startfile("http://localhost:5173")
    else:
        subprocess.run(["xdg-open", "http://localhost:5173"], check=False)

    print("=" * 60)
    print("   系统已启动，此窗口可以关闭")
    print("   服务在独立的控制台窗口中运行")
    print("=" * 60)


if __name__ == "__main__":
    main()
