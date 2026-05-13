"""
GPU 资源管理器 - 统一管理 IndexTTS 和 HeyGem 的显存占用

设计要点：
1. 单例模式确保全局唯一
2. 线程安全锁保护状态切换
3. 复用现有引擎的 unload 方法

使用方式：
    from core.engines.gpu_manager import get_gpu_manager, EngineType

    gpu_manager = get_gpu_manager()

    # TTS 阶段开始
    gpu_manager.acquire(EngineType.TTS)
    # ... 执行 TTS 推理 ...
    gpu_manager.release(EngineType.TTS)

    # 视频阶段开始
    gpu_manager.acquire(EngineType.HEYGEM)
    # ... 执行视频生成 ...
    gpu_manager.release(EngineType.HEYGEM)
"""

import gc
import threading
from enum import Enum
from typing import Optional, Dict, Any, List

import logging

logger = logging.getLogger("autoavantar.gpu_manager")


class EngineType(Enum):
    """引擎类型枚举"""
    TTS = "tts"
    HEYGEM = "heygem"


class GPUResourceManager:
    """
    GPU 资源管理器 - 单例模式

    核心职责：
    1. 管理引擎的加载/卸载
    2. 协调显存占用（同一时间只有一个引擎占用 GPU）
    3. 提供显存状态查询

    使用流程：
    - acquire(engine_type): 获取 GPU 使用权，如果其他引擎占用则先释放
    - release(engine_type): 释放 GPU 使用权
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._current_holder: Optional[EngineType] = None
        self._engines: Dict[EngineType, Any] = {}
        self._engine_lock = threading.Lock()
        self._initialized = True
        logger.info("GPU 资源管理器初始化完成")

    def register_engine(self, engine_type: EngineType, engine: Any) -> None:
        """注册引擎实例"""
        with self._engine_lock:
            self._engines[engine_type] = engine
            logger.info(f"引擎已注册: {engine_type.value}")

    def unregister_engine(self, engine_type: EngineType) -> None:
        """注销引擎实例"""
        with self._engine_lock:
            if engine_type in self._engines:
                del self._engines[engine_type]
                logger.info(f"引擎已注销: {engine_type.value}")

    def get_engine(self, engine_type: EngineType) -> Optional[Any]:
        """获取已注册的引擎实例"""
        with self._engine_lock:
            return self._engines.get(engine_type)

    def acquire(self, engine_type: EngineType, timeout: float = 30.0) -> bool:
        """
        获取 GPU 使用权

        如果其他引擎正在占用 GPU，会先释放它

        Args:
            engine_type: 请求使用 GPU 的引擎类型
            timeout: 释放操作的超时时间（秒），默认 30 秒

        Returns:
            是否成功获取使用权
        """
        with self._engine_lock:
            if self._current_holder == engine_type:
                # 已经持有，无需操作
                return True

            if self._current_holder is not None:
                # 其他引擎占用，需要先释放（带超时保护）
                logger.info(f"释放 {self._current_holder.value} 引擎以切换到 {engine_type.value}")
                released = self._release_internal_with_timeout(self._current_holder, timeout)
                if not released:
                    logger.warning(f"释放 {self._current_holder.value} 引擎超时，强制继续")

            self._current_holder = engine_type
            logger.info(f"{engine_type.value} 引擎已获取 GPU 使用权")
            return True

    def release(self, engine_type: EngineType) -> None:
        """
        释放 GPU 使用权

        Args:
            engine_type: 释放使用权的引擎类型
        """
        with self._engine_lock:
            if self._current_holder == engine_type:
                self._release_internal(engine_type)
                self._current_holder = None
                logger.info(f"{engine_type.value} 引擎已释放 GPU 使用权")

    def _release_internal(self, engine_type: EngineType) -> None:
        """内部释放方法（不加锁）"""
        engine = self._engines.get(engine_type)
        if engine is not None and hasattr(engine, 'unload'):
            try:
                engine.unload()
                logger.info(f"{engine_type.value} 引擎 unload 完成")
            except Exception as e:
                logger.error(f"{engine_type.value} 引擎 unload 失败: {e}")

        # 清理 CUDA 缓存
        self._empty_cuda_cache()

    def _release_internal_with_timeout(self, engine_type: EngineType, timeout: float) -> bool:
        """
        带超时保护的内部释放方法

        Args:
            engine_type: 引擎类型
            timeout: 超时时间（秒）

        Returns:
            是否在超时前完成释放
        """
        result = {'completed': False, 'error': None}

        def _do_release():
            try:
                engine = self._engines.get(engine_type)
                if engine is not None and hasattr(engine, 'unload'):
                    engine.unload()
                    logger.info(f"{engine_type.value} 引擎 unload 完成")
                result['completed'] = True
            except Exception as e:
                result['error'] = str(e)
                logger.error(f"{engine_type.value} 引擎 unload 失败: {e}")

        # 在独立线程中执行释放
        release_thread = threading.Thread(target=_do_release, daemon=True)
        release_thread.start()
        release_thread.join(timeout=timeout)

        # 无论是否超时，都清理 CUDA 缓存
        self._empty_cuda_cache()

        if release_thread.is_alive():
            # 线程仍在运行，表示超时
            logger.warning(f"{engine_type.value} 引擎 unload 超时（{timeout}秒），已强制继续")
            return False

        return result['completed']

    def force_release_all(self) -> Dict[str, Any]:
        """
        强制释放所有引擎资源

        Returns:
            释放结果
        """
        with self._engine_lock:
            results = {}
            for engine_type in list(self._engines.keys()):
                try:
                    self._release_internal(engine_type)
                    results[engine_type.value] = "released"
                except Exception as e:
                    results[engine_type.value] = f"error: {e}"

            self._current_holder = None
            self._empty_cuda_cache()
            logger.info("所有引擎资源已强制释放")
            return results

    def get_memory_info(self) -> Dict[str, Any]:
        """
        获取显存信息

        Returns:
            显存使用情况
        """
        try:
            import torch
            if torch.cuda.is_available():
                device = torch.cuda.current_device()
                total = torch.cuda.get_device_properties(device).total_memory
                allocated = torch.cuda.memory_allocated(device)
                reserved = torch.cuda.memory_reserved(device)
                return {
                    "total_mb": total / 1024 / 1024,
                    "allocated_mb": allocated / 1024 / 1024,
                    "reserved_mb": reserved / 1024 / 1024,
                    "free_mb": (total - allocated) / 1024 / 1024,
                    "current_holder": self._current_holder.value if self._current_holder else None
                }
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"获取显存信息失败: {e}")

        return {
            "total_mb": 0,
            "allocated_mb": 0,
            "reserved_mb": 0,
            "free_mb": 0,
            "current_holder": self._current_holder.value if self._current_holder else None
        }

    def _empty_cuda_cache(self) -> None:
        """清理 CUDA 缓存"""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                gc.collect()
                logger.debug("CUDA 缓存已清理")
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"清理 CUDA 缓存失败: {e}")

    @property
    def current_holder(self) -> Optional[str]:
        """当前占用 GPU 的引擎"""
        return self._current_holder.value if self._current_holder else None

    @property
    def is_managed(self) -> bool:
        """是否有引擎正在管理 GPU"""
        return self._current_holder is not None


# 全局单例访问
_gpu_manager_instance: Optional[GPUResourceManager] = None


def get_gpu_manager() -> GPUResourceManager:
    """
    获取 GPU 资源管理器单例

    Returns:
        GPUResourceManager 实例
    """
    global _gpu_manager_instance
    if _gpu_manager_instance is None:
        _gpu_manager_instance = GPUResourceManager()
    return _gpu_manager_instance


def reset_gpu_manager() -> None:
    """
    重置 GPU 资源管理器单例

    用于测试或特殊情况，一般不需要调用
    """
    global _gpu_manager_instance
    if _gpu_manager_instance is not None:
        try:
            _gpu_manager_instance.force_release_all()
        except Exception as e:
            logger.error(f"重置时释放资源失败: {e}")
    _gpu_manager_instance = None
    logger.info("GPUResourceManager 单例已重置")
