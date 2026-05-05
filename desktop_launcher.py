"""
桌面启动器
用于打包成独立的可执行文件
"""

import os
import sys
import subprocess
import threading
import webbrowser
import time
from pathlib import Path


def get_base_dir():
    """获取基础目录"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的路径
        return Path(sys._MEIPASS)
    else:
        # 开发环境
        return Path(__file__).parent


def start_backend():
    """启动后端服务"""
    base_dir = get_base_dir()

    # 设置工作目录
    os.chdir(base_dir)

    # 添加路径
    sys.path.insert(0, str(base_dir))

    # 启动服务
    import uvicorn
    from api.main import app

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9010,
        log_level="info"
    )


def open_browser():
    """延迟打开浏览器"""
    time.sleep(3)  # 等待服务启动
    webbrowser.open("http://localhost:9010")


def main():
    """主入口"""
    print("=" * 50)
    print("  AUTOavantar 数字人视频生成系统")
    print("  版本: 1.1.0")
    print("=" * 50)
    print()
    print("正在启动服务，请稍候...")
    print("服务地址: http://localhost:9010")
    print()

    # 在后台线程打开浏览器
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # 启动后端服务
    try:
        start_backend()
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"\n启动失败: {e}")
        input("按回车键退出...")


if __name__ == "__main__":
    main()
