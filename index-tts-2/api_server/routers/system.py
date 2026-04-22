"""
系统监控路由
提供健康检查和配置查询接口
"""

import logging
import time

from fastapi import APIRouter, HTTPException

from api_server.models.system import (
    ConfigResponse,
    GpuInfo,
    HealthResponse,
    TaskStats,
    UnloadResponse,
)

logger = logging.getLogger("indextts-api.system")

router = APIRouter()

_engine = None  # type: ignore
_task_queue = None  # type: ignore
_settings = None  # type: ignore
_audio_service = None  # type: ignore
_emotion_service = None  # type: ignore
_start_time = 0.0
_version = "0.2.0"


def set_services(engine, task_queue, settings, audio_service, emotion_service=None) -> None:
    """注入服务实例"""
    global _engine, _task_queue, _settings, _audio_service, _emotion_service, _start_time
    _engine = engine
    _task_queue = task_queue
    _settings = settings
    _audio_service = audio_service
    _emotion_service = emotion_service
    _start_time = time.time()


def _get_gpu_info() -> GpuInfo:
    """收集 GPU 详细信息"""
    gpu = GpuInfo()
    try:
        import torch

        if torch.cuda.is_available():
                gpu.available = True
                gpu.name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                # 修复：使用正确的属性名 total_memory_in_bytes 替代 total_mem
                if hasattr(props, 'total_mem'):
                    # 旧版本 PyTorch 使用 total_mem
                    gpu.memory_total_mb = round(props.total_mem / 1024 / 1024, 1)
                    gpu.memory_free_mb = round(
                        (props.total_mem - torch.cuda.memory_allocated(0)) / 1024 / 1024, 1
                    )
                elif hasattr(props, 'total_memory_in_bytes'):
                    # 新版本 PyTorch 使用 total_memory_in_bytes
                    gpu.memory_total_mb = round(props.total_memory_in_bytes / 1024 / 1024, 1)
                    gpu.memory_free_mb = round(
                        (props.total_memory_in_bytes - torch.cuda.memory_allocated(0)) / 1024 / 1024, 1
                    )
                else:
                    # 回退方案：使用 torch.cuda.get_device_properties 替代
                    gpu.memory_total_mb = round(torch.cuda.get_device_properties(0).total_memory / 1024 / 1024, 1)
                    gpu.memory_free_mb = round(
                        (torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)) / 1024 / 1024, 1
                    )
                gpu.memory_used_mb = round(torch.cuda.memory_allocated(0) / 1024 / 1024, 1)
                if gpu.memory_total_mb and gpu.memory_total_mb > 0:
                    gpu.memory_utilization = round(gpu.memory_used_mb / gpu.memory_total_mb * 100, 1)
    except Exception as e:
        logger.warning(f"获取 GPU 信息失败: {e}")
    return gpu


def _get_task_stats() -> TaskStats:
    """收集任务统计信息"""
    stats = TaskStats()
    if _task_queue is None:
        return stats

    tasks = _task_queue.get_all_tasks()
    stats.total = len(tasks)
    for t in tasks:
        status = t.status.value if hasattr(t.status, "value") else str(t.status)
        if status == "pending":
            stats.pending += 1
        elif status == "processing":
            stats.processing += 1
        elif status == "completed":
            stats.completed += 1
        elif status == "failed":
            stats.failed += 1
    return stats


@router.get("/health", response_model=HealthResponse)
async def health():
    """
    健康检查接口

    返回模型加载状态、GPU 详细信息、队列信息、任务统计、情绪服务状态等。
    """
    model_loaded = _engine.is_loaded if _engine else False

    # 模型设备信息
    model_device = None
    fp16 = False
    if _engine and _engine.is_loaded:
        model_device = str(_engine._device)
        fp16 = _engine._is_fp16

    gpu = _get_gpu_info()
    task_stats = _get_task_stats()
    queue_length = _task_queue.queue_length if _task_queue else 0
    uptime = round(time.time() - _start_time, 1) if _start_time > 0 else 0

    emotion_available = False
    if _emotion_service is not None:
        emotion_available = _emotion_service.available

    status = "ready" if model_loaded else "loading"

    return HealthResponse(
        status=status,
        model_loaded=model_loaded,
        model_device=model_device,
        fp16=fp16,
        gpu=gpu,
        current_queue_length=queue_length,
        task_stats=task_stats,
        emotion_service_available=emotion_available,
        uptime_sec=uptime,
        version=_version,
    )


@router.post("/unload", response_model=UnloadResponse)
async def unload_model():
    """
    卸载 TTS 模型，释放 GPU 显存。

    卸载后模型不可用，需要重启服务才能恢复。
    适用于 TTS 完成后、其他 GPU 密集任务开始前的显存释放场景。
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="服务未初始化")

    if not _engine.is_loaded:
        return UnloadResponse(success=True, message="模型未加载，无需卸载")

    try:
        _engine.unload_model()
        gpu = _get_gpu_info()
        msg = f"模型已卸载，GPU 显存已释放"
        if gpu.available and gpu.memory_free_mb:
            msg += f"，可用显存: {gpu.memory_free_mb:.0f} MB"
        return UnloadResponse(success=True, message=msg)
    except Exception as e:
        logger.error(f"卸载模型失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"卸载模型失败: {e}")


@router.get("/config", response_model=ConfigResponse)
async def config():
    """
    查询当前推理配置

    返回推理模式、GPU 设备、FP16 状态等配置信息。
    """
    if _settings is None:
        raise HTTPException(status_code=503, detail="服务正在启动中")

    return ConfigResponse(
        inference_mode=_settings.inference.mode,
        device=_settings.model.device or "auto",
        fp16=_settings.model.is_fp16,
        max_queue_size=_settings.queue.max_size,
        task_timeout_sec=_settings.queue.task_timeout_sec,
        audio_retention_hours=_settings.audio.retention_hours,
        default_generation_params={
            "temperature": _settings.inference.temperature,
            "top_p": _settings.inference.top_p,
            "top_k": _settings.inference.top_k,
            "num_beams": _settings.inference.num_beams,
        },
    )
