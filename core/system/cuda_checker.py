"""
CUDA 驱动检测服务
检测 GPU 驱动版本是否满足 CUDA 12.x 要求
"""

import logging
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger("autoavantar.cuda")


class CUDACheckResult(BaseModel):
    """CUDA 检测结果"""
    available: bool
    driver_version: Optional[str] = None
    cuda_version: Optional[str] = None
    gpu_name: Optional[str] = None
    gpu_memory_gb: float = 0.0
    is_supported: bool = False
    minimum_driver: str = "525.60.13"
    minimum_memory_gb: float = 6.0
    message: str = ""


class CUDAChecker:
    """
    CUDA 驱动检测器

    检测规则：
    - PyTorch 2.8.0+cu128 要求 CUDA 12.x
    - 最低驱动版本：525.60.13（NVIDIA 官方 CUDA 12.x 要求）
    - 最低显存：6GB（建议 8GB+）
    """

    MINIMUM_DRIVER_VERSION = "525.60.13"
    MINIMUM_MEMORY_GB = 6.0

    def __init__(self):
        self._torch = None
        self._torch_available = False
        self._check_torch()

    def _check_torch(self):
        """检查 PyTorch 是否可用"""
        try:
            import torch
            self._torch = torch
            self._torch_available = torch.cuda.is_available()
            logger.info(f"PyTorch CUDA 可用: {self._torch_available}")
        except ImportError:
            logger.warning("PyTorch 未安装")
            self._torch_available = False

    def check(self) -> CUDACheckResult:
        """
        执行 CUDA 检测

        Returns:
            CUDACheckResult: 检测结果
        """
        if not self._torch_available:
            return CUDACheckResult(
                available=False,
                is_supported=False,
                message="PyTorch CUDA 不可用。请检查 CUDA 安装或 GPU 驱动。"
            )

        try:
            # 获取 GPU 信息
            gpu_name = self._torch.cuda.get_device_name(0)
            gpu_memory_bytes = self._torch.cuda.get_device_properties(0).total_memory
            gpu_memory_gb = round(gpu_memory_bytes / (1024 ** 3), 1)

            # 获取 CUDA 版本
            cuda_version = self._torch.version.cuda

            # 获取驱动版本
            driver_version = self._get_driver_version()

            # 检查是否满足要求
            is_driver_ok = self._compare_driver_versions(
                driver_version,
                self.MINIMUM_DRIVER_VERSION
            ) >= 0 if driver_version else False

            is_memory_ok = gpu_memory_gb >= self.MINIMUM_MEMORY_GB

            is_supported = is_driver_ok and is_memory_ok

            # 生成提示信息
            if is_supported:
                message = "GPU 驱动正常"
            else:
                issues = []
                if not is_driver_ok:
                    issues.append(f"驱动版本过低（当前: {driver_version or '未知'}，需要: {self.MINIMUM_DRIVER_VERSION}+）")
                if not is_memory_ok:
                    issues.append(f"显存不足（当前: {gpu_memory_gb}GB，建议: {self.MINIMUM_MEMORY_GB}GB+）")
                message = "。".join(issues) + "。请更新显卡驱动或使用更高配置的 GPU。"

            result = CUDACheckResult(
                available=True,
                driver_version=driver_version,
                cuda_version=cuda_version,
                gpu_name=gpu_name,
                gpu_memory_gb=gpu_memory_gb,
                is_supported=is_supported,
                message=message
            )

            logger.info(f"CUDA 检测完成: {result.model_dump()}")
            return result

        except Exception as e:
            logger.error(f"CUDA 检测失败: {e}")
            return CUDACheckResult(
                available=False,
                is_supported=False,
                message=f"CUDA 检测失败: {str(e)}"
            )

    def _get_driver_version(self) -> Optional[str]:
        """获取 NVIDIA 驱动版本"""
        try:
            # 方法1: 通过 nvidia-smi 获取
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                if version:
                    return version
        except Exception:
            pass

        try:
            # 方法2: 通过 PyTorch 获取
            if self._torch:
                # torch.cuda.get_device_properties 不直接提供驱动版本
                # 但可以通过 torch.utils.cmake_prefix_path 推断
                pass
        except Exception:
            pass

        try:
            # 方法3: Windows 注册表
            if hasattr(self, '_get_driver_version_windows'):
                version = self._get_driver_version_windows()
                if version:
                    return version
        except Exception:
            pass

        return None

    def _get_driver_version_windows(self) -> Optional[str]:
        """Windows 平台通过注册表获取驱动版本"""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            )

            for i in range(winreg.QueryInfoKey(key)[0]):
                subkey_name = winreg.EnumKey(key, i)
                if "NVIDIA" in subkey_name.upper() and "Display" in subkey_name.upper():
                    try:
                        subkey = winreg.OpenKey(key, subkey_name)
                        version, _ = winreg.QueryValueEx(subkey, "DisplayVersion")
                        winreg.CloseKey(subkey)
                        if version:
                            return version
                    except Exception:
                        continue

            winreg.CloseKey(key)
        except Exception:
            pass

        return None

    def _compare_driver_versions(self, v1: str, v2: str) -> int:
        """
        比较两个驱动版本号

        Returns:
            -1: v1 < v2
            0: v1 == v2
            1: v1 > v2
        """
        def parse_version(v: str) -> tuple:
            """解析版本号为元组"""
            parts = v.replace(',', '.').split('.')
            return tuple(int(p) for p in parts if p.isdigit())

        try:
            p1 = parse_version(v1)
            p2 = parse_version(v2)

            # 补齐长度
            max_len = max(len(p1), len(p2))
            p1 = p1 + (0,) * (max_len - len(p1))
            p2 = p2 + (0,) * (max_len - len(p2))

            if p1 < p2:
                return -1
            elif p1 > p2:
                return 1
            return 0
        except Exception:
            return 0


# 全局单例
_cuda_checker: Optional[CUDAChecker] = None


def get_cuda_checker() -> CUDAChecker:
    """获取 CUDA 检测器单例"""
    global _cuda_checker
    if _cuda_checker is None:
        _cuda_checker = CUDAChecker()
    return _cuda_checker
