"""
桌面启动器
用于打包成独立的可执行文件
启动器会调用同目录下的 py310 环境运行后端服务
引擎模式：系统启动时自动加载 TTSEngine 和 HeyGemEngine
"""

import os
import sys
import subprocess
import threading
import webbrowser
import time
import urllib.request
import urllib.error
from pathlib import Path


def get_app_dir():
    """获取应用程序目录"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的路径
        return Path(sys.executable).parent
    else:
        # 开发环境
        return Path(__file__).parent


def find_python():
    """查找 Python 解释器"""
    app_dir = get_app_dir()

    # 优先使用 py310 环境
    py310_path = app_dir / "py310" / "python.exe"
    if py310_path.exists():
        return str(py310_path)

    # 使用系统 Python
    return "python"


def wait_for_backend_ready(host="localhost", port=9010, timeout=120):
    """
    等待后端服务就绪

    Args:
        host: 后端主机地址
        port: 后端端口
        timeout: 超时时间（秒）

    Returns:
        bool: 服务是否就绪
    """
    url = f"http://{host}:{port}/api/health"
    start_time = time.time()

    print(f"[等待] 等待后端服务就绪 (最多 {timeout} 秒)...")

    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    print(f"[就绪] 后端服务已就绪")
                    return True
        except urllib.error.URLError:
            pass
        except Exception:
            pass

        time.sleep(1)
        elapsed = int(time.time() - start_time)
        if elapsed % 5 == 0:  # 每 5 秒输出一次进度
            print(f"[等待] 已等待 {elapsed} 秒...")

    print(f"[超时] 后端服务未在 {timeout} 秒内就绪")
    return False


def start_backend():
    """启动后端服务"""
    app_dir = get_app_dir()
    python_exe = find_python()

    # 设置工作目录到 backend
    backend_dir = app_dir / "backend"
    if backend_dir.exists():
        os.chdir(backend_dir)
    else:
        os.chdir(app_dir)

    # 设置环境变量
    env = os.environ.copy()
    env["PYTHONPATH"] = str(app_dir)

    # 启动 uvicorn
    cmd = [
        python_exe,
        "-m", "uvicorn",
        "api.main:app",
        "--host", "0.0.0.0",
        "--port", "9010",
        "--log-level", "info"
    ]

    print(f"[启动] 使用 Python: {python_exe}")
    print(f"[启动] 工作目录: {os.getcwd()}")
    print(f"[启动] 引擎模式: 系统将自动加载 TTSEngine 和 HeyGemEngine")
    print()

    try:
        subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"\n启动失败: {e}")
        input("按回车键退出...")


def open_browser_when_ready():
    """等待后端就绪后打开浏览器"""
    # 等待后端 API 就绪
    if wait_for_backend_ready():
        print("[打开] 正在打开浏览器...")
        webbrowser.open("http://localhost:9010")
    else:
        print("[错误] 后端服务启动超时，请检查日志")


def main():
    """主入口"""
    print("=" * 60)
    print("  AUTOavantar 数字人视频生成系统")
    print("  版本: 1.2.0")
    print("  模式: 引擎模式（无需 HTTP 服务）")
    print("=" * 60)
    print()
    print("正在启动服务，请稍候...")
    print()
    print("服务地址: http://localhost:9010")
    print("API 文档: http://localhost:9010/docs")
    print()
    print("提示: 系统启动时会自动加载 TTS 和 HeyGem 引擎")
    print("      首次启动可能需要较长时间，请耐心等待...")
    print()

    # 在后台线程等待后端就绪后打开浏览器
    browser_thread = threading.Thread(target=open_browser_when_ready, daemon=True)
    browser_thread.start()

    # 启动后端服务
    start_backend()


if __name__ == "__main__":
    main()
