"""
独立更新脚本
在 AUTOavantar.exe 退出后执行 git pull 并重启应用

使用方法:
    python tools/update_and_restart.py

该脚本由 desktop_launcher.py 在用户选择更新后启动，
作为独立进程运行，确保主进程可以正常退出。
"""

import platform
import subprocess
import sys
import os
import time
from pathlib import Path


def get_app_dir() -> Path:
    """获取应用程序目录"""
    script_path = Path(__file__).resolve()
    # tools/update_and_restart.py -> ../../
    return script_path.parent.parent


def find_python() -> str:
    """查找 Python 解释器"""
    app_dir = get_app_dir()
    py310_path = app_dir / "py310" / "python.exe"
    if py310_path.exists():
        return str(py310_path)
    return "python"


def log(message: str):
    """打印日志"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def wait_for_process_exit(process_name: str, timeout: int = 30):
    """等待进程退出"""
    try:
        import psutil
        start_time = time.time()
        while time.time() - start_time < timeout:
            # 检查进程是否还在运行
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and process_name.lower() in proc.info['name'].lower():
                    time.sleep(1)
                    break
            else:
                return True
        return False
    except ImportError:
        # 没有 psutil，直接等待
        time.sleep(5)
        return True


def execute_git_pull(app_dir: Path) -> tuple:
    """
    执行 git pull

    Returns:
        (success, message)
    """
    # 尝试多种 git 路径
    git_paths = [
        app_dir / "py310" / "git-cmd.exe",
        app_dir / "py310" / "bin" / "git.exe",
        "git"
    ]

    git_exe = None
    for path in git_paths:
        if isinstance(path, Path):
            if path.exists():
                git_exe = str(path)
                break
        else:
            # 检查系统 git
            try:
                result = subprocess.run(
                    [path, "--version"],
                    capture_output=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
                )
                if result.returncode == 0:
                    git_exe = path
                    break
            except Exception:
                continue

    if not git_exe:
        return False, "未找到 git"

    log(f"使用 git: {git_exe}")

    try:
        # 执行 git pull
        result = subprocess.run(
            [git_exe, "pull"],
            cwd=str(app_dir),
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        )

        if result.returncode != 0:
            return False, f"git pull 失败: {result.stderr}"

        return True, result.stdout

    except subprocess.TimeoutExpired:
        return False, "git pull 超时"
    except Exception as e:
        return False, f"git pull 异常: {e}"


def restart_application(app_dir: Path):
    """重启应用"""
    exe_path = app_dir / "AUTOavantar.exe"

    if not exe_path.exists():
        log(f"应用不存在: {exe_path}")
        return False

    try:
        # 使用 DETACHED_PROCESS 启动，确保独立进程
        subprocess.Popen(
            [str(exe_path)],
            cwd=str(app_dir),
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
        log(f"已启动新进程: {exe_path}")
        return True
    except Exception as e:
        log(f"重启应用失败: {e}")
        return False


def main():
    """主函数"""
    log("=" * 50)
    log("AUTOavantar 更新脚本启动")
    log("=" * 50)

    app_dir = get_app_dir()
    log(f"应用目录: {app_dir}")

    # 1. 等待主进程退出
    log("等待主进程退出...")
    if not wait_for_process_exit("AUTOavantar", timeout=30):
        log("等待超时，继续执行更新...")

    # 额外等待确保文件释放
    time.sleep(2)

    # 2. 清除更新标记
    update_flag = app_dir / ".update_pending"
    if update_flag.exists():
        update_flag.unlink()
        log("已清除更新标记")

    # 3. 执行 git pull
    log("执行 git pull...")
    success, message = execute_git_pull(app_dir)

    if not success:
        log(f"更新失败: {message}")
        # 更新失败也尝试重启，使用旧版本
        log("尝试重启旧版本...")
    else:
        log(f"更新成功: {message}")

    # 4. 重启应用
    log("重启应用...")
    if restart_application(app_dir):
        log("更新流程完成")
    else:
        log("重启失败，请手动启动应用")

    log("=" * 50)


if __name__ == "__main__":
    main()
