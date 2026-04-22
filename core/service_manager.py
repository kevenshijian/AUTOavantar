"""
ServiceManager - 服务进程管理模块
管理 IndexTTS 和 HeyGem 子进程的生命周期（启动、停止、重启、状态查询）
"""

import logging
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any

import requests

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """服务状态枚举"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class ManagedService:
    """被管理的服务"""
    name: str
    status: ServiceStatus = ServiceStatus.STOPPED
    process: Optional[subprocess.Popen] = None
    pid: Optional[int] = None
    started_at: Optional[float] = None
    restart_count: int = 0  # 当前任务内重启次数
    error_message: str = ""
    health_url: str = ""
    start_command: list = field(default_factory=list)
    working_dir: str = ""
    ready_timeout: float = 120.0


def get_base_dir() -> str:
    """获取项目根目录（支持开发模式和打包模式）
    
    - 开发模式: 返回脚本所在目录
    - PyInstaller 打包模式: 返回 EXE 所在目录
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包模式
        return os.path.dirname(sys.executable)
    else:
        # 开发模式 - 向上两级找到项目根目录（core/service_manager.py -> core/ -> 项目根目录）
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(current_file_dir)


def build_service_env() -> Dict[str, str]:
    """构建子进程环境变量（与启动系统.bat 完全一致）
    
    设置的环境变量:
    - PATH: 包含 py310 相关路径前缀
    - PYTHONEXECUTABLE: Python 解释器路径
    - FFMPEG_PATH: FFmpeg 路径
    - CU_PATH: CUDA 库路径
    - CUDA_BIN_PATH: CUDA bin 路径
    - GRADIO_TEMP_DIR: Gradio 临时目录
    - USE_ONNX: 是否使用 ONNX
    - DS_BUILD_AIO: DeepSpeed AIO 构建标志
    - DS_BUILD_SPARSE_ATTN: DeepSpeed 稀疏注意力构建标志
    - HF_ENDPOINT: HuggingFace 镜像端点
    - HF_HOME: HuggingFace 下载目录
    - TRANSFORMERS_CACHE: Transformers 缓存目录
    - XFORMERS_FORCE_DISABLE_TRITON: 禁用 Triton
    - PYTORCH_CUDA_ALLOC_CONF: PyTorch CUDA 内存分配配置
    - HF_HUB_OFFLINE: HuggingFace 离线模式
    - TRANSFORMERS_OFFLINE: Transformers 离线模式
    """
    base_dir = get_base_dir()
    python_path = os.path.join(base_dir, "py310")
    
    if not os.path.exists(python_path):
        raise FileNotFoundError(f"Python 环境未找到: {python_path}")
    
    python_executable = os.path.join(python_path, "python.exe")
    ffmpeg_path = os.path.join(python_path, "ffmpeg", "bin")
    cu_path = os.path.join(python_path, "Lib", "site-packages", "torch", "lib")
    cuda_bin_path = os.path.join(python_path, "Library", "bin")
    
    # 查找系统 CUDA 安装路径
    cuda_base = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "NVIDIA GPU Computing Toolkit", "CUDA")
    cuda_version_path = None
    if os.path.exists(cuda_base):
        # 查找最新版本
        versions = sorted([d for d in os.listdir(cuda_base) if d.startswith("v")], reverse=True)
        if versions:
            cuda_version_path = os.path.join(cuda_base, versions[0])
    
    env = os.environ.copy()
    
    # 设置 PATH（前置自定义路径）
    path_parts = [
        os.path.join(base_dir, "node-v24.15.0-win-x64"),  # Node.js 路径
        python_path,
        os.path.join(python_path, "Scripts"),
        ffmpeg_path,
        cu_path,
        cuda_bin_path,
    ]
    
    # 添加系统 CUDA 路径到 PATH
    if cuda_version_path:
        cuda_bin = os.path.join(cuda_version_path, "bin")
        cuda_libnvvp = os.path.join(cuda_version_path, "libnvvp")
        if os.path.exists(cuda_bin):
            path_parts.append(cuda_bin)
        if os.path.exists(cuda_libnvvp):
            path_parts.append(cuda_libnvvp)
    
    env["PATH"] = ";".join(path_parts) + ";" + env.get("PATH", "")
    
    # 设置 CUDA 库路径（LIB 环境变量，用于链接器）
    if cuda_version_path:
        cuda_lib_x64 = os.path.join(cuda_version_path, "lib", "x64")
        cuda_lib64 = os.path.join(cuda_version_path, "lib64")
        lib_paths = []
        if os.path.exists(cuda_lib_x64):
            lib_paths.append(cuda_lib_x64)
        if os.path.exists(cuda_lib64):
            lib_paths.append(cuda_lib64)
        if lib_paths:
            existing_lib = env.get("LIB", "")
            env["LIB"] = ";".join(lib_paths) + (";" + existing_lib if existing_lib else "")
    
    # Python 环境变量
    env["PYTHONEXECUTABLE"] = python_executable
    env["FFMPEG_PATH"] = ffmpeg_path
    env["CU_PATH"] = cu_path
    env["CUDA_BIN_PATH"] = cuda_bin_path
    
    # AI 环境变量
    env["GRADIO_TEMP_DIR"] = os.path.join(base_dir, "tmp") + os.sep
    env["USE_ONNX"] = "true"
    env["DS_BUILD_AIO"] = "0"
    env["DS_BUILD_SPARSE_ATTN"] = "0"
    env["HF_ENDPOINT"] = "https://hf-mirror.com"
    env["HF_HOME"] = os.path.join(base_dir, "hf_download")
    env["TRANSFORMERS_CACHE"] = os.path.join(base_dir, "tf_download")
    env["XFORMERS_FORCE_DISABLE_TRITON"] = "1"
    env["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    
    return env


class ServiceManager:
    """服务管理器 - 管理 IndexTTS 和 HeyGem 子进程"""
    
    def __init__(self, monitor_interval: float = 10.0):
        """初始化服务管理器
        
        Args:
            monitor_interval: 监控线程检查间隔（秒），默认10秒
        """
        self._services: Dict[str, ManagedService] = {}
        self._lock = threading.Lock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._monitor_interval = monitor_interval  # 监控检查间隔
        
        # 初始化服务对象配置
        base_dir = get_base_dir()
        python_exe = os.path.join(base_dir, "py310", "python.exe")
        
        # IndexTTS 服务配置
        self._services["indextts"] = ManagedService(
            name="indextts",
            health_url="http://localhost:7860/api/v1/health",
            start_command=[
                python_exe, "-m", "uvicorn", "api_server.main:app",
                "--host", "0.0.0.0", "--port", "7860"
            ],
            working_dir=os.path.join(base_dir, "index-tts-2"),
            ready_timeout=60.0
        )

        # HeyGem 服务配置
        self._services["heygem"] = ManagedService(
            name="heygem",
            health_url="http://localhost:9889",
            start_command=[python_exe, "app.py"],
            working_dir=os.path.join(base_dir, "heygem-win-50-onnx"),
            ready_timeout=60.0
        )
        
        logger.info("ServiceManager 初始化完成")
    
    def start(self) -> bool:
        """启动服务管理器（启动后台监控线程）
        
        Returns:
            bool: 是否成功启动
        """
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("ServiceManager 监控线程已启动")
        return True
    
    def stop(self) -> bool:
        """停止服务管理器（停止后台监控线程）
        
        Returns:
            bool: 是否成功停止
        """
        self._running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        logger.info("ServiceManager 监控线程已停止")
        return True
    
    def start_service(self, service_name: str) -> bool:
        """启动服务子进程
        
        Args:
            service_name: 服务名称 ("indextts" 或 "heygem")
            
        Returns:
            bool: 是否成功启动
            
        Raises:
            FileNotFoundError: Python 环境未找到
        """
        with self._lock:
            svc = self._services.get(service_name)
            if not svc:
                logger.error(f"未知服务: {service_name}")
                return False
            
            # 检查服务是否已经在运行（通过健康检查）
            if self._check_service_health(service_name):
                svc.status = ServiceStatus.RUNNING
                svc.error_message = ""
                logger.info(f"服务 {service_name} 已在运行中（外部启动）")
                return True

            # 清理旧的进程对象（如果存在）
            if svc.process is not None:
                try:
                    if svc.process.poll() is not None:
                        # 进程已退出，清理对象
                        logger.debug(f"服务 {service_name} 旧进程已退出，清理进程对象")
                        svc.process = None
                        svc.pid = None
                except Exception as e:
                    logger.debug(f"检查旧进程状态失败: {e}")
                    svc.process = None
                    svc.pid = None

            try:
                # 构建环境变量
                env = build_service_env()

                # 确保工作目录存在
                if not os.path.exists(svc.working_dir):
                    logger.error(f"工作目录不存在: {svc.working_dir}")
                    svc.status = ServiceStatus.FAILED
                    svc.error_message = f"工作目录不存在: {svc.working_dir}"
                    return False

                # 启动子进程（使用独立控制台窗口）
                logger.info(f"启动服务 {service_name}...")
                logger.info(f"命令: {' '.join(svc.start_command)}")
                logger.info(f"工作目录: {svc.working_dir}")

                if sys.platform == "win32":
                    # Windows: 使用 start 命令启动独立控制台窗口
                    # 注意：使用 DETACHED_PROCESS 标志创建独立进程
                    cmd_str = ' '.join(f'"{c}"' if ' ' in c else c for c in svc.start_command)
                    full_cmd = f'cd /d "{svc.working_dir}" && start "{service_name}" cmd /c "{cmd_str}"'
                    svc.process = subprocess.Popen(
                        full_cmd,
                        env=env,
                        shell=True,
                        # 不检查进程状态，因为 start 命令会立即返回
                    )
                    # 使用 shell=True 时，process 对象代表的是 shell 进程
                    # 设置为 None 以避免在 _wait_for_ready 中错误检查
                    svc.process = None
                else:
                    # 非 Windows 平台
                    svc.process = subprocess.Popen(
                        svc.start_command,
                        cwd=svc.working_dir,
                        env=env,
                    )

                svc.pid = None  # 使用 start 命令时无法获取真实 PID
                svc.status = ServiceStatus.STARTING
                svc.started_at = time.time()
                svc.restart_count = 0
                svc.error_message = ""

                logger.info(f"服务 {service_name} 进程已启动（独立控制台窗口）")
                
            except FileNotFoundError as e:
                svc.status = ServiceStatus.FAILED
                svc.error_message = f"Python 环境未找到: {e}"
                logger.error(f"启动服务 {service_name} 失败: {svc.error_message}")
                raise
            except Exception as e:
                svc.status = ServiceStatus.FAILED
                svc.error_message = str(e)
                logger.error(f"启动服务 {service_name} 失败: {e}")
                return False
        
        # 等待服务就绪（在锁外执行，避免阻塞其他操作）
        if self._wait_for_ready(service_name):
            with self._lock:
                svc.status = ServiceStatus.RUNNING
            logger.info(f"服务 {service_name} 已就绪")
            return True
        else:
            with self._lock:
                svc.status = ServiceStatus.FAILED
                if not svc.error_message:
                    svc.error_message = f"服务就绪超时 ({svc.ready_timeout}s)"
            logger.error(f"服务 {service_name} 就绪超时")
            return False
    
    def stop_service(self, service_name: str) -> bool:
        """停止服务子进程
        
        Args:
            service_name: 服务名称 ("indextts" 或 "heygem")
            
        Returns:
            bool: 是否成功停止
        """
        with self._lock:
            svc = self._services.get(service_name)
            if not svc:
                logger.error(f"未知服务: {service_name}")
                return False
            
            # 先检查服务是否正在运行（使用更宽松的标准）
            is_running = False
            try:
                resp = requests.get(svc.health_url, timeout=3)
                # 只要能响应就认为服务在运行（不管状态码是什么）
                is_running = True
            except (requests.ConnectionError, requests.Timeout):
                is_running = False
            except Exception:
                is_running = False
            
            if not is_running:
                logger.info(f"服务 {service_name} 未在运行")
                svc.status = ServiceStatus.STOPPED
                svc.process = None
                svc.pid = None
                svc.started_at = None
                return True
            
            # 尝试停止进程
            try:
                # 无论是否有进程对象，都尝试通过端口查找并停止服务
                # 这样可以处理进程PID已改变的情况
                port = int(svc.health_url.split(':')[-1].split('/')[0])
                logger.info(f"停止服务 {service_name}，通过端口 {port} 查找进程...")
                
                # 使用 netstat 找到占用端口的进程
                try:
                    result = subprocess.run(
                        ["netstat", "-ano"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    for line in result.stdout.split('\n'):
                        if f":{port}" in line and "LISTENING" in line:
                            # 提取 PID
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                pid = parts[-1]
                                logger.info(f"发现占用端口 {port} 的进程 PID: {pid}")
                                
                                # 终止进程
                                kill_result = subprocess.run(
                                    ["taskkill", "/F", "/T", "/PID", pid],
                                    capture_output=True,
                                    timeout=10
                                )
                                if kill_result.returncode == 0:
                                    logger.info(f"成功终止进程 PID: {pid}")
                                else:
                                    stderr = kill_result.stderr.decode('utf-8', errors='ignore') if kill_result.stderr else "未知错误"
                                    logger.warning(f"终止进程失败: {stderr}")
                except Exception as e:
                    logger.error(f"查找端口占用失败: {e}")
                
                # 如果有进程对象，也尝试直接停止（作为备用）
                if svc.process and svc.pid:
                    try:
                        logger.info(f"尝试通过进程对象停止服务 {service_name} (PID: {svc.pid})...")
                        # 备用：直接 kill
                        try:
                            svc.process.kill()
                        except:
                            pass
                        
                        # 等待进程结束
                        try:
                            svc.process.wait(timeout=5)
                        except:
                            pass
                    except Exception as e:
                        logger.warning(f"通过进程对象停止失败: {e}")
                
                # 等待服务完全停止（增加等待时间）
                time.sleep(3)
                
                # 多次尝试检查服务是否停止（最多尝试5次）
                max_attempts = 5
                for attempt in range(max_attempts):
                    try:
                        # 对于停止检查，我们使用更宽松的标准：只要无法连接到服务就认为它已经停止
                        resp = requests.get(svc.health_url, timeout=3)
                        # 如果能连接到服务，继续等待
                        logger.info(f"服务 {service_name} 仍在运行，等待中... (尝试 {attempt+1}/{max_attempts})")
                        time.sleep(2)
                    except (requests.ConnectionError, requests.Timeout):
                        # 无法连接到服务，说明服务已经停止
                        logger.info(f"服务 {service_name} 已停止")
                        svc.status = ServiceStatus.STOPPED
                        svc.process = None
                        svc.pid = None
                        svc.started_at = None
                        return True
                    except Exception:
                        # 其他错误，也认为服务已经停止
                        logger.info(f"服务 {service_name} 已停止")
                        svc.status = ServiceStatus.STOPPED
                        svc.process = None
                        svc.pid = None
                        svc.started_at = None
                        return True
                
                # 多次尝试后服务仍在运行
                logger.error(f"服务 {service_name} 停止失败，服务仍在运行")
                return False
                    
            except Exception as e:
                logger.error(f"停止服务 {service_name} 失败: {e}")
                return False
    
    def restart_service(self, service_name: str) -> bool:
        """重启服务子进程
        
        Args:
            service_name: 服务名称 ("indextts" 或 "heygem")
            
        Returns:
            bool: 是否成功重启
        """
        logger.info(f"重启服务 {service_name}...")
        
        # 停止服务
        stop_success = self.stop_service(service_name)
        if not stop_success:
            logger.error(f"停止服务 {service_name} 失败，无法重启")
            return False
        
        # 等待端口释放（减少等待时间，使用更合理的值）
        logger.info(f"等待端口释放，暂停 3 秒...")
        time.sleep(3)
        
        # 启动服务
        start_success = self.start_service(service_name)
        if not start_success:
            logger.error(f"启动服务 {service_name} 失败")
            return False
        
        # 额外等待服务完全就绪，确保API端口可用
        logger.info(f"服务 {service_name} 启动成功，等待API完全就绪...")
        svc = self._services.get(service_name)
        if svc:
            # 等待最多30秒，确保服务能响应HTTP请求
            max_wait = 30
            start_time = time.time()
            while time.time() - start_time < max_wait:
                try:
                    resp = requests.get(svc.health_url, timeout=2)
                    if resp.status_code < 500:
                        logger.info(f"服务 {service_name} API已就绪")
                        return True
                except:
                    pass
                time.sleep(1)
            logger.warning(f"服务 {service_name} API就绪等待超时，但服务已启动")
        
        return True
    
    def get_status(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """获取服务状态
        
        Args:
            service_name: 服务名称，为 None 时返回所有服务状态
            
        Returns:
            服务状态字典
        """
        with self._lock:
            if service_name:
                svc = self._services.get(service_name)
                if not svc:
                    return {"error": f"未知服务: {service_name}"}
                return self._get_service_status_dict(svc)
            else:
                return {
                    name: self._get_service_status_dict(svc)
                    for name, svc in self._services.items()
                }
    
    def _get_service_status_dict(self, svc: ManagedService) -> Dict[str, Any]:
        """获取单个服务的状态字典"""
        result = {
            "name": svc.name,
            "status": svc.status.value,
            "pid": svc.pid,
            "restart_count": svc.restart_count,
            "error_message": svc.error_message if svc.error_message else None
        }
        
        if svc.started_at:
            result["started_at"] = datetime.fromtimestamp(svc.started_at).isoformat()
            result["uptime_seconds"] = int(time.time() - svc.started_at)
        else:
            result["started_at"] = None
            result["uptime_seconds"] = 0
            
        return result
    
    def _check_service_health(self, service_name: str) -> bool:
        """检查服务健康状态
        
        Args:
            service_name: 服务名称
            
        Returns:
            bool: 服务是否健康（服务进程在运行且能响应 HTTP 请求）
        """
        svc = self._services[service_name]
        
        try:
            # 统一的健康检查逻辑：只要服务能响应 HTTP 请求就认为是健康的
            # 不检查 model_loaded，因为模型可能被卸载但服务仍在运行
            resp = requests.get(svc.health_url, timeout=5)
            # 只要不是服务器错误（5xx）就认为服务健康
            # - 200: 正常运行
            # - 4xx: 客户端错误，但服务在运行（如 HeyGem 返回 422）
            return resp.status_code < 500
        except (requests.ConnectionError, requests.Timeout):
            return False
        except Exception as e:
            logger.debug(f"健康检查异常 [{service_name}]: {e}")
            return False
    
    def _wait_for_ready(self, service_name: str) -> bool:
        """等待服务就绪（通过 HTTP 健康检查）

        Args:
            service_name: 服务名称

        Returns:
            bool: 服务是否就绪
        """
        svc = self._services[service_name]
        start_time = time.time()
        poll_interval = 2.0  # 轮询间隔（秒）
        check_count = 0

        while time.time() - start_time < svc.ready_timeout:
            check_count += 1
            elapsed = time.time() - start_time

            # HTTP 健康检查
            if self._check_service_health(service_name):
                logger.info(f"服务 {service_name} 就绪 (耗时 {elapsed:.1f}s, 检查 {check_count} 次)")
                return True

            # 每 10 秒输出一次等待日志
            if check_count % 5 == 0:
                logger.debug(f"等待服务 {service_name} 就绪... (已等待 {elapsed:.0f}s)")

            time.sleep(poll_interval)

        # 超时
        logger.warning(f"服务 {service_name} 就绪超时 ({svc.ready_timeout}s, 检查 {check_count} 次)")
        return False
    
    def _monitor_loop(self):
        """后台监控线程：检测进程存活状态"""
        logger.info("服务监控线程启动")
        
        while self._running:
            try:
                with self._lock:
                    for name, svc in self._services.items():
                        # 首先检查服务健康状态（无论当前状态如何）
                        is_healthy = self._check_service_health(name)
                        
                        if is_healthy:
                            # 服务健康，更新状态为运行中
                            if svc.status != ServiceStatus.RUNNING:
                                svc.status = ServiceStatus.RUNNING
                                svc.error_message = ""
                                logger.info(f"检测到服务 {name} 正在运行")
                        else:
                            # 服务不健康（可能是模型卸载、服务繁忙、或进程退出）
                            # 只有当进程确实退出时才标记为失败
                            if svc.status == ServiceStatus.RUNNING:
                                # 检查进程是否真的退出了
                                if svc.process and svc.process.poll() is not None:
                                    # 进程确实退出了
                                    svc.status = ServiceStatus.FAILED
                                    svc.error_message = f"进程意外退出，返回码: {svc.process.returncode}"
                                    logger.error(f"服务 {name} 意外退出: {svc.error_message}")
                                elif svc.process is None:
                                    # 没有进程对象，可能是外部启动的服务
                                    # 不标记为失败，只记录警告
                                    logger.debug(f"服务 {name} 健康检查失败（可能是模型卸载或服务繁忙）")
                                else:
                                    # 进程还在运行，只是健康检查失败（可能是模型卸载）
                                    logger.debug(f"服务 {name} 健康检查失败，但进程仍在运行")
                                
                time.sleep(self._monitor_interval)
                
            except Exception as e:
                logger.error(f"监控线程异常: {e}")
                time.sleep(self._monitor_interval)
        
        logger.info("服务监控线程停止")
    
    def shutdown(self):
        """关闭所有服务（用于系统关闭时清理）"""
        logger.info("ServiceManager 正在关闭所有服务...")
        
        # 停止监控线程
        self.stop()
        
        # 停止所有服务
        for name in self._services:
            self.stop_service(name)
        
        logger.info("ServiceManager 已关闭")


# 全局 ServiceManager 实例（单例模式）
_service_manager_instance: Optional[ServiceManager] = None
_service_manager_lock = threading.Lock()


def get_service_manager() -> Optional[ServiceManager]:
    """获取全局 ServiceManager 实例
    
    Returns:
        ServiceManager 实例，如果未初始化则返回 None
    """
    global _service_manager_instance
    return _service_manager_instance


def create_service_manager() -> ServiceManager:
    """创建并初始化全局 ServiceManager 实例
    
    Returns:
        ServiceManager 实例
        
    Note:
        通常在后端 lifespan 启动时调用一次
    """
    global _service_manager_instance
    
    with _service_manager_lock:
        if _service_manager_instance is None:
            _service_manager_instance = ServiceManager()
            _service_manager_instance.start()
            logger.info("全局 ServiceManager 实例已创建")
        
        return _service_manager_instance


def destroy_service_manager():
    """销毁全局 ServiceManager 实例
    
    Note:
        通常在后端 lifespan 关闭时调用一次
    """
    global _service_manager_instance
    
    with _service_manager_lock:
        if _service_manager_instance is not None:
            _service_manager_instance.shutdown()
            _service_manager_instance = None
            logger.info("全局 ServiceManager 实例已销毁")
