"""
桌面启动器 - PyWebView 版本
用于打包成独立的可执行文件

功能：
- 使用 PyWebView 创建原生窗口嵌入 Vue 前端
- 后端托管前端静态文件
- 系统托盘支持
- 单实例检测
- 窗口状态持久化
- 版本更新检测与自动更新
"""

import os
import sys
import subprocess
import threading
import time
import json
import webbrowser
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# 日志文件路径
LOG_FILE = None

def log(message):
    """写入日志"""
    global LOG_FILE
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line, flush=True)
    if LOG_FILE:
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
        except:
            pass

# PyWebView
import webview

# Windows 互斥体（单实例检测）
try:
    import win32event
    import win32api
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# 系统托盘
try:
    import pystray
    from PIL import Image
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False


# 配置
MUTEX_NAME = "Global\\AUTOavantar_SingleInstance"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 9010
STARTUP_TIMEOUT = 120  # 秒
WINDOW_DEFAULT_WIDTH = 1280
WINDOW_DEFAULT_HEIGHT = 800
CONFIG_FILE = "backend/data/window_config.json"
VERSION_URL = "https://raw.githubusercontent.com/Eikwang/AUTOavantar/main/VERSION"


def get_app_dir():
    """获取应用程序目录

    打包模式下，exe 应该放在与 py310、backend 同级的目录中运行。
    这是发布包的标准结构。
    """
    if getattr(sys, 'frozen', False):
        # 打包模式：exe 所在目录就是应用目录
        return Path(sys.executable).parent
    else:
        # 开发模式：返回脚本所在目录
        return Path(__file__).parent


def init_logging():
    """初始化日志文件"""
    global LOG_FILE
    app_dir = get_app_dir()
    log_dir = app_dir / "backend" / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    LOG_FILE = log_dir / "launcher.log"
    log(f"日志文件: {LOG_FILE}")
    log(f"应用目录: {app_dir}")
    log(f"Python 版本: {sys.version}")
    log(f"工作目录: {os.getcwd()}")
    return LOG_FILE


def read_version():
    """读取版本号"""
    app_dir = get_app_dir()
    version_file = app_dir / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding='utf-8').strip()
    return "1.0.0"


def compare_versions(v1: str, v2: str) -> int:
    """
    比较版本号

    Returns:
        -1: v1 < v2
        0: v1 == v2
        1: v1 > v2
    """
    def parse(v: str) -> tuple:
        return tuple(int(p) for p in v.split('.') if p.isdigit())
    try:
        p1, p2 = parse(v1), parse(v2)
        max_len = max(len(p1), len(p2))
        p1 = p1 + (0,) * (max_len - len(p1))
        p2 = p2 + (0,) * (max_len - len(p2))
        return (p1 > p2) - (p1 < p2)
    except Exception:
        return 0


def fetch_remote_version() -> tuple:
    """
    从 GitHub 获取远程版本号

    Returns:
        (success, remote_version)
    """
    try:
        req = urllib.request.Request(VERSION_URL, method='GET')
        req.add_header('User-Agent', 'AUTOavantar-Version-Check')
        with urllib.request.urlopen(req, timeout=5) as response:
            version = response.read().decode('utf-8').strip()
            return True, version
    except Exception as e:
        log(f"获取远程版本失败: {e}")
        return False, None


def check_for_updates() -> tuple:
    """
    检查是否有更新

    Returns:
        (has_update, local_version, remote_version)
    """
    local_version = read_version()
    success, remote_version = fetch_remote_version()

    if success and remote_version:
        if compare_versions(remote_version, local_version) > 0:
            return True, local_version, remote_version

    return False, local_version, local_version


def find_python():
    """查找 Python 解释器"""
    app_dir = get_app_dir()
    py310_path = app_dir / "py310" / "python.exe"
    if py310_path.exists():
        return str(py310_path)
    return "python"


def check_single_instance():
    """单实例检测"""
    if not HAS_WIN32:
        return True

    try:
        mutex = win32event.CreateMutex(None, False, MUTEX_NAME)
        last_error = win32api.GetLastError()
        if last_error == win32event.ERROR_ALREADY_EXISTS:
            return False
        return True
    except Exception:
        return True


def load_window_config():
    """加载窗口配置"""
    app_dir = get_app_dir()
    config_path = app_dir / CONFIG_FILE

    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return {
                    'width': max(800, config.get('width', WINDOW_DEFAULT_WIDTH)),
                    'height': max(600, config.get('height', WINDOW_DEFAULT_HEIGHT)),
                    'x': config.get('x'),
                    'y': config.get('y'),
                    'maximized': config.get('maximized', False)
                }
        except Exception:
            pass

    return {
        'width': WINDOW_DEFAULT_WIDTH,
        'height': WINDOW_DEFAULT_HEIGHT,
        'x': None,
        'y': None,
        'maximized': False
    }


def save_window_config(width, height, x, y, maximized):
    """保存窗口配置"""
    app_dir = get_app_dir()
    config_path = app_dir / CONFIG_FILE
    config_dir = config_path.parent

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        config = {
            'width': width,
            'height': height,
            'x': x,
            'y': y,
            'maximized': maximized
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f)
    except Exception:
        pass


class LauncherApp:
    """启动器应用"""

    def __init__(self):
        self.app_dir = get_app_dir()
        self.version = read_version()
        self.window = None
        self.backend_process = None
        self.tray_icon = None
        self.is_running = False
        self.window_config = load_window_config()
        self.backend_ready = False
        self.update_pending = False
        self.local_version = self.version
        self.remote_version = self.version


class Api:
    """WebView API 类"""

    def __init__(self, app: LauncherApp):
        self.app = app

    def startUpdate(self):
        """开始更新流程"""
        log("用户选择立即更新")
        self.app.update_pending = True

        # 创建更新标记
        update_flag = self.app.app_dir / ".update_pending"
        update_flag.write_text("pending", encoding='utf-8')

        # 退出应用
        if self.app.window:
            self.app.window.destroy()

        os._exit(0)

    def deferUpdate(self):
        """稍后更新"""
        log("用户选择稍后更新")
        # 继续正常启动流程

    def start_backend(self):
        """启动后端服务"""
        python_exe = find_python()
        log(f"Python 解释器: {python_exe}")

        # 设置工作目录
        backend_dir = self.app_dir / "backend"
        log(f"后端目录: {backend_dir}")
        log(f"后端目录存在: {backend_dir.exists()}")

        if backend_dir.exists():
            os.chdir(backend_dir)
            log(f"切换工作目录到: {backend_dir}")
        else:
            os.chdir(self.app_dir)
            log(f"切换工作目录到: {self.app_dir}")

        # 设置环境变量
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.app_dir)
        log(f"PYTHONPATH: {env['PYTHONPATH']}")

        # 启动后端
        cmd = [
            python_exe,
            "-m", "uvicorn",
            "api.main:app",
            "--host", BACKEND_HOST,
            "--port", str(BACKEND_PORT),
            "--log-level", "warning"
        ]
        log(f"启动命令: {cmd}")

        # Windows 下隐藏控制台窗口
        startupinfo = None
        creationflags = 0
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            self.backend_process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并 stderr 到 stdout
                text=True,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            log(f"后端进程已启动，PID: {self.backend_process.pid}")

            # 启动线程实时读取后端输出
            def read_backend_output():
                if self.backend_process and self.backend_process.stdout:
                    for line in self.backend_process.stdout:
                        log(f"[后端] {line.rstrip()}")

            output_thread = threading.Thread(target=read_backend_output, daemon=True)
            output_thread.start()
        except Exception as e:
            log(f"启动后端失败: {e}")
            return None

        return self.backend_process

    def wait_for_backend(self, timeout=STARTUP_TIMEOUT):
        """等待后端就绪"""
        url = f"http://{BACKEND_HOST}:{BACKEND_PORT}/api/health"
        log(f"等待后端就绪: {url}")
        start_time = time.time()
        attempt = 0

        while time.time() - start_time < timeout:
            attempt += 1
            try:
                req = urllib.request.Request(url, method='GET')
                with urllib.request.urlopen(req, timeout=1) as response:
                    if response.status == 200:
                        log(f"后端已就绪 (尝试 {attempt} 次)")
                        return True
            except Exception as e:
                if attempt % 10 == 0:
                    log(f"等待中... (尝试 {attempt} 次): {e}")
            time.sleep(1)  # 减少等待间隔，加快检测速度

        log(f"后端启动超时 ({timeout} 秒)")
        # 检查后端进程状态
        if self.backend_process:
            log(f"后端进程状态: {self.backend_process.poll()}")
            if self.backend_process.poll() is not None:
                stdout, stderr = self.backend_process.communicate()
                log(f"后端进程 stdout: {stdout}")
                log(f"后端进程 stderr: {stderr}")
        return False

    def get_running_task_count(self):
        """获取正在运行的任务数量"""
        try:
            url = f"http://{BACKEND_HOST}:{BACKEND_PORT}/api/tasks/running-count"
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data.get('count', 0)
        except Exception:
            return 0

    def create_tray_icon(self):
        """创建系统托盘图标"""
        if not HAS_TRAY:
            return None

        icon_path = self.app_dir / "favicon.ico"
        if icon_path.exists():
            try:
                image = Image.open(icon_path)
                # 转换为 RGBA 模式并调整到标准托盘图标尺寸
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')
                # 托盘图标标准尺寸为 64x64 或 32x32
                if image.size != (64, 64):
                    image = image.resize((64, 64), Image.Resampling.LANCZOS)
            except Exception as e:
                log(f"加载图标失败: {e}，使用默认图标")
                image = Image.new('RGBA', (64, 64), color=(0, 122, 255, 255))
        else:
            image = Image.new('RGBA', (64, 64), color=(0, 122, 255, 255))

        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", self.show_window, default=True),
            pystray.MenuItem("打开输出目录", self.open_output_dir),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self.quit_app)
        )

        self.tray_icon = pystray.Icon(
            "AUTOavantar",
            image,
            f"AUTOavantar v{self.version}",
            menu
        )

        return self.tray_icon

    def show_window(self):
        """显示窗口"""
        if self.window:
            self.window.show()

    def open_output_dir(self):
        """打开输出目录"""
        output_dir = self.app_dir / "output"
        if output_dir.exists():
            webbrowser.open(str(output_dir))
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            webbrowser.open(str(output_dir))

    def quit_app(self):
        """退出应用"""
        # 检查是否有运行中的任务
        running_count = self.get_running_task_count()
        if running_count > 0:
            # 通过窗口显示确认对话框
            if self.window:
                result = self.window.confirm("有任务正在执行，确定要退出吗？", "确认退出")
                if not result:
                    return

        # 停止托盘
        if self.tray_icon:
            self.tray_icon.stop()

        # 停止后端
        if self.backend_process:
            try:
                self.backend_process.terminate()
                self.backend_process.wait(timeout=5)
            except Exception:
                self.backend_process.kill()

        # 退出程序
        os._exit(0)

    def on_closing(self):
        """窗口关闭事件"""
        # 保存窗口状态
        if self.window:
            save_window_config(
                self.window.width,
                self.window.height,
                self.window.x,
                self.window.y,
                False
            )

        # 隐藏窗口，显示托盘
        self.window.hide()

        if self.tray_icon:
            self.tray_icon.visible = True

        return False  # 阻止窗口关闭

    def on_resized(self, width, height):
        """窗口大小改变事件"""
        save_window_config(width, height, self.window.x, self.window.y, False)

    def on_moved(self, x, y):
        """窗口移动事件"""
        save_window_config(self.window.width, self.window.height, x, y, False)

    def on_maximized(self):
        """窗口最大化事件"""
        save_window_config(self.window.width, self.window.height, self.window.x, self.window.y, True)

    def check_update_flag(self) -> bool:
        """检查是否有更新标记"""
        update_flag = self.app_dir / ".update_pending"
        return update_flag.exists()

    def clear_update_flag(self):
        """清除更新标记"""
        update_flag = self.app_dir / ".update_pending"
        if update_flag.exists():
            update_flag.unlink()

    def execute_update_and_restart(self):
        """执行更新并重启"""
        log("开始执行更新流程...")

        # 1. 清除更新标记
        self.clear_update_flag()

        # 2. 执行 git pull
        try:
            git_exe = self.app_dir / "py310" / "git-cmd.exe"
            if not git_exe.exists():
                # 尝试使用系统 git
                git_exe = "git"

            result = subprocess.run(
                [str(git_exe), "pull"],
                cwd=str(self.app_dir),
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                log(f"git pull 失败: {result.stderr}")
                return False

            log(f"git pull 成功: {result.stdout}")
        except Exception as e:
            log(f"执行 git pull 异常: {e}")
            return False

        # 3. 重启应用
        try:
            exe_path = self.app_dir / "AUTOavantar.exe"
            if exe_path.exists():
                subprocess.Popen([str(exe_path)], cwd=str(self.app_dir))
                log(f"已启动新进程: {exe_path}")
        except Exception as e:
            log(f"重启应用失败: {e}")
            return False

        return True

    def start_update_script(self):
        """启动独立更新脚本"""
        update_script = self.app_dir / "tools" / "update_and_restart.py"
        python_exe = find_python()

        if update_script.exists():
            try:
                # 启动更新脚本（独立进程）
                subprocess.Popen(
                    [python_exe, str(update_script)],
                    cwd=str(self.app_dir),
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                )
                log("更新脚本已启动")
            except Exception as e:
                log(f"启动更新脚本失败: {e}")
        else:
            log(f"更新脚本不存在: {update_script}")

    def run(self):
        """运行应用"""
        # 单实例检测
        if not check_single_instance():
            print("已有实例运行，退出")
            return

        # 检查更新标记（上次退出前触发的更新）
        if self.check_update_flag():
            log("检测到更新标记，执行更新...")
            self.execute_update_and_restart()
            return

        # 版本检测
        has_update, self.local_version, self.remote_version = check_for_updates()
        log(f"版本检测: 本地={self.local_version}, 远程={self.remote_version}, 有更新={has_update}")

        # 加载画面 HTML
        update_section = ""
        if has_update:
            update_section = f"""
                <div class="update-info">
                    <p class="update-title">发现新版本 {self.remote_version}</p>
                    <p class="update-current">当前版本: {self.local_version}</p>
                    <div class="update-buttons">
                        <button onclick="startUpdate()">立即更新</button>
                        <button class="secondary" onclick="deferUpdate()">稍后提醒</button>
                    </div>
                </div>
            """

        loading_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    margin: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    font-family: 'Microsoft YaHei', sans-serif;
                }}
                .container {{
                    text-align: center;
                    color: white;
                }}
                .title {{
                    font-size: 32px;
                    font-weight: bold;
                    margin-bottom: 20px;
                }}
                .version {{
                    font-size: 16px;
                    opacity: 0.8;
                    margin-bottom: 30px;
                }}
                .spinner {{
                    width: 50px;
                    height: 50px;
                    border: 4px solid rgba(255,255,255,0.3);
                    border-top: 4px solid white;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 20px;
                }}
                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
                .message {{
                    font-size: 16px;
                }}
                .update-info {{
                    margin-top: 30px;
                    padding: 20px;
                    background: rgba(255,255,255,0.15);
                    border-radius: 10px;
                }}
                .update-title {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #ffd700;
                    margin-bottom: 10px;
                }}
                .update-current {{
                    font-size: 14px;
                    opacity: 0.8;
                    margin-bottom: 15px;
                }}
                .update-buttons {{
                    display: flex;
                    gap: 10px;
                    justify-content: center;
                }}
                .update-buttons button {{
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 14px;
                    transition: all 0.3s;
                }}
                .update-buttons button:first-child {{
                    background: #ffd700;
                    color: #333;
                }}
                .update-buttons button:first-child:hover {{
                    background: #ffed4a;
                }}
                .update-buttons button.secondary {{
                    background: rgba(255,255,255,0.2);
                    color: white;
                }}
                .update-buttons button.secondary:hover {{
                    background: rgba(255,255,255,0.3);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="title">AUTOavantar</div>
                <div class="version">v{self.version}</div>
                <div class="spinner"></div>
                <div class="message">系统启动中，请稍候...</div>
                {update_section}
            </div>
            <script>
                function startUpdate() {{
                    window.pywebview.api.startUpdate();
                }}
                function deferUpdate() {{
                    window.pywebview.api.deferUpdate();
                }}
            </script>
        </body>
        </html>
        """

        # 错误画面 HTML
        error_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {
                    margin: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    background: #f44336;
                    font-family: 'Microsoft YaHei', sans-serif;
                    color: white;
                    text-align: center;
                }
            </style>
        </head>
        <body>
            <div>
                <h1>启动失败</h1>
                <p>后端服务启动超时，请检查日志</p>
            </div>
        </body>
        </html>
        """

        # 创建主窗口（初始显示加载画面）
        # 创建 API 实例
        api = Api(self)

        self.window = webview.create_window(
            f'AUTOavantar v{self.version}',
            html=loading_html,
            js_api=api,
            width=self.window_config['width'],
            height=self.window_config['height'],
            x=self.window_config['x'],
            y=self.window_config['y'],
            resizable=True,
            min_size=(800, 600)
        )

        # 启动后端线程
        def backend_thread():
            self.start_backend()

        backend_thread_obj = threading.Thread(target=backend_thread, daemon=True)
        backend_thread_obj.start()

        # 等待后端就绪并切换到主界面
        def wait_and_switch():
            if self.wait_for_backend():
                self.backend_ready = True
                # 切换到后端 URL
                self.window.load_url(f'http://{BACKEND_HOST}:{BACKEND_PORT}')

                # 绑定事件
                self.window.events.closing += self.on_closing
                self.window.events.resized += self.on_resized
                self.window.events.moved += self.on_moved

                # 创建托盘图标
                self.create_tray_icon()

                # 启动托盘（在后台线程）
                if self.tray_icon:
                    tray_thread = threading.Thread(
                        target=lambda: self.tray_icon.run(),
                        daemon=True
                    )
                    tray_thread.start()
            else:
                # 启动超时，显示错误
                self.window.load_html(error_html)

        # 启动等待线程
        wait_thread = threading.Thread(target=wait_and_switch, daemon=True)
        wait_thread.start()

        # 启动 WebView 事件循环（必须在主线程）
        webview.start(debug=False)


def main():
    """主入口"""
    init_logging()
    log("=" * 50)
    log("AUTOavantar 桌面启动器启动")
    log("=" * 50)
    app = LauncherApp()
    app.run()


if __name__ == "__main__":
    main()
