"""
健康检查路由
"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


def get_engines_status():
    """获取引擎状态"""
    from core.engines.gpu_manager import get_gpu_manager

    gpu_manager = get_gpu_manager()
    engines_status = {}

    if gpu_manager:
        # 访问内部引擎字典
        from core.engines.gpu_manager import EngineType
        engines_dict = gpu_manager._engines

        # TTS 引擎状态
        tts_engine = engines_dict.get(EngineType.TTS)
        if tts_engine:
            engines_status["tts_engine"] = {
                "status": "loaded" if getattr(tts_engine, 'is_model_loaded', False) else "unloaded",
                "managed": True
            }
        else:
            engines_status["tts_engine"] = {
                "status": "not_registered",
                "managed": False
            }

        # HeyGem 引擎状态
        heygem_engine = engines_dict.get(EngineType.HEYGEM)
        if heygem_engine:
            engines_status["heygem_engine"] = {
                "status": "loaded" if getattr(heygem_engine, 'is_model_loaded', False) else "unloaded",
                "managed": True
            }
        else:
            engines_status["heygem_engine"] = {
                "status": "not_registered",
                "managed": False
            }
    else:
        engines_status = {
            "tts_engine": {"status": "unknown", "error": "GPUResourceManager not initialized"},
            "heygem_engine": {"status": "unknown", "error": "GPUResourceManager not initialized"}
        }

    return engines_status


@router.get("/health")
async def health_check():
    """健康检查接口 - 包含引擎状态"""
    engines_status = get_engines_status()

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "AUTOavantar API",
        "mode": "engine",
        "engines": engines_status
    }


@router.get("/health/engines")
async def engines_health_check():
    """引擎健康检查接口 - 返回 TTSEngine 和 HeyGemEngine 的状态"""
    engines_status = get_engines_status()

    return {
        "timestamp": datetime.now().isoformat(),
        "mode": "engine",
        "engines": engines_status
    }
