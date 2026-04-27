"""
IndexTTS API Server - FastAPI 应用入口

提供基于 IndexTTS-2 模型的 TTS 语音合成 REST API。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api_server.config import Settings, settings

logger = logging.getLogger("indextts-api")

# 全局服务实例
_engine = None
_task_queue = None
_audio_service = None
_voice_manager = None
_emotion_service = None
_audio_speed_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时加载模型，关闭时清理资源"""
    import asyncio

    from api_server.services.audio_service import AudioService
    from api_server.services.emotion_mapping import EmotionMappingService
    from api_server.services.task_queue import TaskQueue
    from api_server.services.tts_engine import TTSEngine
    from api_server.services.voice_manager import VoiceManager
    from api_server.services.audio_speed_service import AudioSpeedService

    global _engine, _task_queue, _audio_service, _voice_manager, _emotion_service, _audio_speed_service

    # ---- 启动阶段 ----
    logger.info("=" * 60)
    logger.info("IndexTTS API Server 启动中...")
    logger.info("=" * 60)

    # 配置日志
    logging.basicConfig(
        level=getattr(logging, settings.logging_.level, logging.INFO),
        format=settings.logging_.format,
    )

    # 初始化音频服务
    _audio_service = AudioService(
        output_dir=settings.get_output_dir(),
        retention_hours=settings.audio.retention_hours,
    )

    # 初始化音色管理
    _voice_manager = VoiceManager(
        voices_dir=settings.get_voices_dir(),
        temp_dir=settings.get_temp_dir(),
    )
    _voice_manager.scan_voices()

    # 初始化情绪映射
    _emotion_service = EmotionMappingService(settings.get_emotion_mapping_path())
    _emotion_service.load()

    # 初始化音频语速调节服务
    _audio_speed_service = AudioSpeedService(output_dir=settings.get_temp_dir())
    logger.info("音频语速调节服务初始化成功")

    # 初始化 TTS 引擎
    _engine = TTSEngine()

    # 根据配置决定是否延迟加载
    if settings.model.lazyload:
        # 延迟加载模式：只保存参数，不加载模型
        logger.info("延迟加载模式：启动时不加载模型，首次请求时自动加载")
        _engine.set_load_params(
            cfg_path=settings.get_model_cfg_path(),
            model_dir=settings.get_model_dir(),
            is_fp16=settings.model.is_fp16,
            device=settings.model.device,
            use_cuda_kernel=settings.model.use_cuda_kernel,
        )
        load_task = None
    else:
        # 立即加载模式：在后台线程中加载模型
        def _load_engine():
            logger.info("开始加载 TTS 模型（后台线程）...")
            try:
                _engine.load_model(
                    cfg_path=settings.get_model_cfg_path(),
                    model_dir=settings.get_model_dir(),
                    is_fp16=settings.model.is_fp16,
                    device=settings.model.device,
                    use_cuda_kernel=settings.model.use_cuda_kernel,
                )
                logger.info("TTS 模型加载完成")
            except Exception as e:
                logger.error(f"TTS 模型加载失败: {e}", exc_info=True)
                raise

        load_task = asyncio.get_event_loop().run_in_executor(None, _load_engine)

    # 将服务实例注入路由
    from api_server.routers import system as system_router
    from api_server.routers.tasks import set_task_queue
    from api_server.routers.tts import set_services as set_tts_services
    from api_server.routers.voices import set_voice_manager

    system_router.set_services(_engine, None, settings, _audio_service, _emotion_service)

    # 等待模型加载完成（仅立即加载模式）
    if load_task:
        await load_task

    _task_queue = TaskQueue(
        engine=_engine,
        audio_service=_audio_service,
        max_size=settings.queue.max_size,
        task_timeout_sec=settings.queue.task_timeout_sec,
    )
    await _task_queue.start()

    set_task_queue(_task_queue)
    set_tts_services(_emotion_service, _task_queue, _voice_manager, _audio_speed_service)
    set_voice_manager(_voice_manager)

    system_router.set_services(_engine, _task_queue, settings, _audio_service, _emotion_service)

    # 注册静态文件服务（音频输出目录）
    output_dir = settings.get_output_dir()
    from pathlib import Path

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    app.mount("/api/v1/audio", StaticFiles(directory=output_dir), name="audio")

    logger.info("IndexTTS API Server 启动完成")
    logger.info(f"监听地址: http://{settings.server.host}:{settings.server.port}")
    logger.info(f"API 文档: http://{settings.server.host}:{settings.server.port}/docs")

    # 启动定期清理后台任务（每 30 分钟检查一次）
    _cleanup_task = None
    if settings.audio.retention_hours > 0:

        async def _periodic_cleanup():
            """定期清理过期音频文件"""
            cleanup_interval = 30 * 60  # 30 分钟
            while True:
                await asyncio.sleep(cleanup_interval)
                try:
                    cleaned = _audio_service.cleanup_expired()
                    if cleaned > 0:
                        logger.info(f"定期清理: 删除了 {cleaned} 个过期音频文件")
                except Exception as e:
                    logger.error(f"定期清理失败: {e}")

        _cleanup_task = asyncio.create_task(_periodic_cleanup())
        logger.info("已启动定期音频清理任务（间隔 30 分钟）")

    yield

    # ---- 关闭阶段 ----
    logger.info("IndexTTS API Server 关闭中...")

    # 停止定期清理任务
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass

    # 停止接受新请求，优雅等待当前任务完成
    if _task_queue:
        await _task_queue.stop(graceful_timeout=120.0)

    # 清理过期音频文件
    if _audio_service:
        cleaned = _audio_service.cleanup_expired()
        if cleaned:
            logger.info(f"清理了 {cleaned} 个过期音频文件")

    # 释放 GPU 缓存
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("GPU 缓存已释放")
    except Exception:
        pass

    logger.info("IndexTTS API Server 已关闭")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""
    # 使用国内可访问的 CDN 加速 Swagger UI /docs 页面
    app = FastAPI(
        title="IndexTTS API Server",
        description="""基于 IndexTTS-2 模型的 TTS 语音合成 REST API。

## 快速开始

### 1. 健康检查
```
GET /api/v1/health
```

### 2. 获取可用音色
```
GET /api/v1/voices
```

### 3. 合成语音
```
POST /api/v1/tts/synthesize
Content-Type: application/json

{
  "text": "你好，欢迎使用 IndexTTS。",
  "voice_name": "苏瑶"
}
```

返回 `task_id`，然后轮询 `GET /api/v1/tasks/{task_id}` 获取结果。

### 4. 情感控制（可选）
- **情绪标签**：`"emotion": "高兴"` — 通过映射表自动翻译
- **情绪控制**：`"emotion": "激动", "intensity": 0.6` — 情绪标签 + 强度（0~1）
""",
        version="0.2.0",
        lifespan=lifespan,
        swagger_js_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/5.10.5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/5.10.5/swagger-ui.css",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    from api_server.routers import system as system_router
    from api_server.routers import tasks as tasks_router
    from api_server.routers import tts as tts_router
    from api_server.routers import voices as voices_router

    app.include_router(tts_router.router, prefix="/api/v1/tts", tags=["TTS 合成"])
    app.include_router(tasks_router.router, prefix="/api/v1/tasks", tags=["任务查询"])
    app.include_router(voices_router.router, prefix="/api/v1/voices", tags=["音色管理"])
    app.include_router(system_router.router, prefix="/api/v1", tags=["系统监控"])

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
    )
