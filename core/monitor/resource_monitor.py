"""
资源监控模块
实现 GPU、CPU、内存、磁盘等资源监控功能
"""

import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil 未安装，CPU/内存/磁盘监控功能不可用")

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("torch 未安装，GPU 显存监控功能受限")


@dataclass
class ResourceStatus:
    """资源状态数据类"""
    # GPU 资源
    gpu_count: int = 0
    gpu_utilization: float = 0.0  # GPU 利用率 %
    gpu_memory_used: float = 0.0  # 已用显存 MB
    gpu_memory_total: float = 0.0  # 总显存 MB
    gpu_memory_percent: float = 0.0  # 显存使用率 %
    
    # CPU 资源
    cpu_percent: float = 0.0  # CPU 使用率 %
    cpu_count: int = 0  # CPU 核心数
    
    # 内存资源
    memory_percent: float = 0.0  # 内存使用率 %
    memory_used: float = 0.0  # 已用内存 GB
    memory_total: float = 0.0  # 总内存 GB
    
    # 磁盘资源
    disk_percent: float = 0.0  # 磁盘使用率 %
    disk_used: float = 0.0  # 已用磁盘空间 GB
    disk_total: float = 0.0  # 总磁盘空间 GB
    disk_free: float = 0.0  # 剩余磁盘空间 GB
    
    # GPU 锁状态（已移除，gpu_lock 模块不存在）
    gpu_lock_status: Optional[Dict[str, Any]] = None
    
    # 时间戳
    timestamp: datetime = field(default=None)
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "gpu_count": self.gpu_count,
            "gpu_utilization": self.gpu_utilization,
            "gpu_memory_used": self.gpu_memory_used,
            "gpu_memory_total": self.gpu_memory_total,
            "gpu_memory_percent": self.gpu_memory_percent,
            "cpu_percent": self.cpu_percent,
            "cpu_count": self.cpu_count,
            "memory_percent": self.memory_percent,
            "memory_used": self.memory_used,
            "memory_total": self.memory_total,
            "disk_percent": self.disk_percent,
            "disk_used": self.disk_used,
            "disk_total": self.disk_total,
            "disk_free": self.disk_free,
            "gpu_lock_status": self.gpu_lock_status,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class ResourceMonitor:
    """资源监控器"""
    
    def __init__(
        self,
        gpu_memory_threshold: float = 80.0,
        cpu_threshold: float = 80.0,
        memory_threshold: float = 80.0,
        disk_threshold: float = 80.0
    ):
        """
        初始化资源监控器
        
        Args:
            gpu_memory_threshold: GPU 显存阈值 (%), 超过则暂停任务
            cpu_threshold: CPU 使用率阈值 (%)
            memory_threshold: 内存使用率阈值 (%)
            disk_threshold: 磁盘使用率阈值 (%)
        """
        self.gpu_memory_threshold = gpu_memory_threshold
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.disk_threshold = disk_threshold
        
        # 初始化 pynvml（如果可用）
        self.pynvml_available = False
        self._init_pynvml()
        
        logger.info(f"资源监控器初始化完成，GPU 显存阈值：{gpu_memory_threshold}%")
    
    def _init_pynvml(self):
        """初始化 pynvml"""
        try:
            import pynvml
            pynvml.nvmlInit()
            self.pynvml_available = True
            self.device_count = pynvml.nvmlDeviceGetCount()
            logger.info(f"pynvml 初始化成功，检测到 {self.device_count} 个 GPU")
        except Exception as e:
            logger.warning(f"pynvml 初始化失败：{e}，将使用 torch.cuda 监控 GPU")
            self.pynvml_available = False
            if TORCH_AVAILABLE:
                self.device_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
            else:
                self.device_count = 0
                logger.warning("torch 不可用，GPU 数量检测失败")
    
    def get_gpu_status(self, device_id: int = 0) -> Dict[str, float]:
        """
        获取 GPU 状态
        
        Args:
            device_id: GPU 设备 ID
            
        Returns:
            GPU 状态字典
        """
        gpu_info = {
            "gpu_count": self.device_count,
            "gpu_utilization": 0.0,
            "gpu_memory_used": 0.0,
            "gpu_memory_total": 0.0,
            "gpu_memory_percent": 0.0
        }
        
        if self.device_count == 0:
            return gpu_info
        
        try:
            if self.pynvml_available:
                import pynvml
                handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
                
                # GPU 利用率
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_info["gpu_utilization"] = utilization.gpu
                
                # 显存信息
                memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_info["gpu_memory_used"] = memory.used / (1024 * 1024)  # MB
                gpu_info["gpu_memory_total"] = memory.total / (1024 * 1024)  # MB
                gpu_info["gpu_memory_percent"] = (memory.used / memory.total) * 100
            else:
                # 使用 torch.cuda
                if TORCH_AVAILABLE and torch.cuda.is_available():
                    gpu_info["gpu_memory_used"] = torch.cuda.memory_allocated(device_id) / (1024 * 1024)
                    gpu_info["gpu_memory_reserved"] = torch.cuda.memory_reserved(device_id) / (1024 * 1024)
                    gpu_info["gpu_memory_total"] = torch.cuda.get_device_properties(device_id).total_memory / (1024 * 1024)
                    gpu_info["gpu_memory_percent"] = (
                        gpu_info["gpu_memory_used"] / gpu_info["gpu_memory_total"]
                    ) * 100
                else:
                    logger.warning("torch 不可用，无法获取 GPU 显存信息")
        except Exception as e:
            logger.error(f"获取 GPU 状态失败：{e}")
        
        return gpu_info
    
    def get_cpu_status(self) -> Dict[str, float]:
        """获取 CPU 状态"""
        if not PSUTIL_AVAILABLE:
            return {
                "cpu_percent": 0.0,
                "cpu_count": 0
            }
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "cpu_count": psutil.cpu_count()
        }
    
    def get_memory_status(self) -> Dict[str, float]:
        """获取内存状态"""
        if not PSUTIL_AVAILABLE:
            return {
                "memory_percent": 0.0,
                "memory_used": 0.0,
                "memory_total": 0.0
            }
        memory = psutil.virtual_memory()
        return {
            "memory_percent": memory.percent,
            "memory_used": memory.used / (1024 * 1024 * 1024),  # GB
            "memory_total": memory.total / (1024 * 1024 * 1024)  # GB
        }
    
    def get_disk_status(self, path: str = "d:") -> Dict[str, float]:
        """
        获取磁盘状态
        
        Args:
            path: 磁盘路径
            
        Returns:
            磁盘状态字典
        """
        if not PSUTIL_AVAILABLE:
            return {
                "disk_percent": 0.0,
                "disk_used": 0.0,
                "disk_total": 0.0,
                "disk_free": 0.0
            }
        try:
            usage = psutil.disk_usage(path)
            return {
                "disk_percent": usage.percent,
                "disk_used": usage.used / (1024 * 1024 * 1024),  # GB
                "disk_total": usage.total / (1024 * 1024 * 1024),  # GB
                "disk_free": usage.free / (1024 * 1024 * 1024)  # GB
            }
        except Exception as e:
            logger.error(f"获取磁盘状态失败：{e}")
            return {
                "disk_percent": 0.0,
                "disk_used": 0.0,
                "disk_total": 0.0,
                "disk_free": 0.0
            }
    
    def get_all_status(self) -> ResourceStatus:
        """
        获取所有资源状态

        Returns:
            ResourceStatus 对象
        """
        gpu_status = self.get_gpu_status()
        cpu_status = self.get_cpu_status()
        memory_status = self.get_memory_status()
        disk_status = self.get_disk_status()

        return ResourceStatus(
            **gpu_status,
            **cpu_status,
            **memory_status,
            **disk_status,
            timestamp=datetime.now()
        )
    
    def is_resources_available(self) -> bool:
        """
        检查资源是否可用（未超过阈值）
        
        Returns:
            是否可用
        """
        status = self.get_all_status()
        
        # 检查 GPU 显存
        if status.gpu_count > 0 and status.gpu_memory_percent > self.gpu_memory_threshold:
            logger.warning(
                f"GPU 显存使用率过高：{status.gpu_memory_percent:.1f}% > {self.gpu_memory_threshold}%"
            )
            return False
        
        # 检查 CPU
        if status.cpu_percent > self.cpu_threshold:
            logger.warning(
                f"CPU 使用率过高：{status.cpu_percent:.1f}% > {self.cpu_threshold}%"
            )
            return False
        
        # 检查内存
        if status.memory_percent > self.memory_threshold:
            logger.warning(
                f"内存使用率过高：{status.memory_percent:.1f}% > {self.memory_threshold}%"
            )
            return False
        
        # 检查磁盘
        if status.disk_percent > self.disk_threshold:
            logger.warning(
                f"磁盘使用率过高：{status.disk_percent:.1f}% > {self.disk_threshold}%"
            )
            return False
        
        return True
    
    def check_disk_space(self, required_gb: float = 20.0) -> bool:
        """
        检查磁盘空间是否充足
        
        Args:
            required_gb: 需要的最小可用空间 (GB)
            
        Returns:
            是否充足
        """
        status = self.get_disk_status()
        if status.disk_free < required_gb:
            logger.warning(
                f"磁盘可用空间不足：{status.disk_free:.1f}GB < {required_gb}GB"
            )
            return False
        return True
    
    def get_stats_summary(self) -> str:
        """
        获取资源统计摘要
        
        Returns:
            摘要字符串
        """
        status = self.get_all_status()
        
        summary = []
        if status.gpu_count > 0:
            summary.append(
                f"GPU: {status.gpu_memory_percent:.1f}% ({status.gpu_memory_used:.0f}/{status.gpu_memory_total:.0f}MB)"
            )
        summary.append(f"CPU: {status.cpu_percent:.1f}%")
        summary.append(f"内存：{status.memory_percent:.1f}%")
        summary.append(f"磁盘：{status.disk_percent:.1f}% (剩余 {status.disk_free:.1f}GB)")

        return " | ".join(summary)


# 全局监控器实例
_monitor: Optional[ResourceMonitor] = None


def get_monitor() -> ResourceMonitor:
    """获取全局监控器实例"""
    global _monitor
    if _monitor is None:
        _monitor = ResourceMonitor()
    return _monitor


def init_monitor(
    gpu_memory_threshold: float = 80.0,
    cpu_threshold: float = 80.0,
    memory_threshold: float = 80.0,
    disk_threshold: float = 80.0
) -> ResourceMonitor:
    """初始化全局监控器"""
    global _monitor
    _monitor = ResourceMonitor(
        gpu_memory_threshold=gpu_memory_threshold,
        cpu_threshold=cpu_threshold,
        memory_threshold=memory_threshold,
        disk_threshold=disk_threshold
    )
    return _monitor
