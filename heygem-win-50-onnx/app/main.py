from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.config import get_settings
from app.utils.logger import setup_logging, get_logger
from app.api.v1 import digital_human_router, templates_router, health_router
from app.api.compat import compat_router

setup_logging(log_level=logging.INFO)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Digital Human API...")
    settings = get_settings()

    settings.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
    settings.RESULT_DIR.mkdir(parents=True, exist_ok=True)
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Server running on {settings.HOST}:{settings.PORT}")
    logger.info(f"Device: {settings.DEVICE}")
    logger.info(f"Batch size: {settings.BATCH_SIZE}")

    yield

    logger.info("Shutting down Digital Human API...")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Digital Human Video Generation API",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(health_router)
    app.include_router(compat_router)        # GET / 兼容接口
    app.include_router(digital_human_router)
    app.include_router(templates_router)

    # ── GPU 显存管理端点 ──

    @app.post("/api/v1/gpu/release")
    async def release_gpu():
        """释放 HeyGem 所有 GPU 显存占用（包括 WeNet 和 DigitalHuman 模型）"""
        try:
            import torch
            import gc

            # 记录清理前的 GPU 状态
            allocated_before = 0.0
            reserved_before = 0.0
            if torch.cuda.is_available():
                allocated_before = torch.cuda.memory_allocated() / 1024**2
                reserved_before = torch.cuda.memory_reserved() / 1024**2

            released_models = []

            # 1. 释放 TransDhTask 单例（HeyGem 核心模型）
            try:
                from service.trans_dh_service import TransDhTask
                if TransDhTask.reset_instance():
                    released_models.append("TransDhTask (WeNet + DigitalHuman)")
                    logger.info("TransDhTask instance released")
            except Exception as e:
                logger.error(f"Error releasing TransDhTask: {e}")

            # 2. 释放 ModelManager 中的 ONNX 模型
            try:
                from app.inference.model_manager import get_model_manager
                manager = get_model_manager()
                onnx_models = list(manager.get_loaded_models().keys())
                if onnx_models:
                    manager.unload_all()
                    released_models.extend(onnx_models)
                    logger.info(f"ONNX models unloaded: {onnx_models}")
            except Exception as e:
                logger.error(f"Error releasing ONNX models: {e}")

            # 3. 强制垃圾回收和显存清理
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

            # 记录清理后的 GPU 状态
            allocated_after = 0.0
            reserved_after = 0.0
            if torch.cuda.is_available():
                allocated_after = torch.cuda.memory_allocated() / 1024**2
                reserved_after = torch.cuda.memory_reserved() / 1024**2

            logger.info(
                f"GPU release: allocated {allocated_before:.1f}→{allocated_after:.1f}MB, "
                f"reserved {reserved_before:.1f}→{reserved_after:.1f}MB, "
                f"released: {released_models}"
            )

            return {
                "status": "success",
                "message": "GPU memory released successfully",
                "memory_before_mb": {
                    "allocated": round(allocated_before, 2),
                    "reserved": round(reserved_before, 2)
                },
                "memory_after_mb": {
                    "allocated": round(allocated_after, 2),
                    "reserved": round(reserved_after, 2)
                },
                "released_models": released_models,
                "note": "Next request will trigger model reloading (cold start ~5-10s)"
            }
        except Exception as e:
            logger.error(f"GPU release failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    @app.get("/api/v1/gpu/status")
    async def gpu_status():
        """查询当前 GPU 显存状态"""
        import torch

        # 获取显存信息
        allocated_mb = 0.0
        reserved_mb = 0.0
        max_allocated_mb = 0.0
        cuda_available = torch.cuda.is_available()

        if cuda_available:
            allocated_mb = torch.cuda.memory_allocated() / 1024**2
            reserved_mb = torch.cuda.memory_reserved() / 1024**2
            max_allocated_mb = torch.cuda.max_memory_allocated() / 1024**2

        # 获取已加载的模型
        models_loaded = []
        try:
            from app.inference.model_manager import get_model_manager
            manager = get_model_manager()
            models_loaded = list(manager.get_loaded_models().keys())
        except:
            pass

        # 检查 TransDhTask 是否已初始化
        transdh_initialized = False
        try:
            from service.trans_dh_service import TransDhTask
            transdh_initialized = hasattr(TransDhTask, '_instance') and TransDhTask._instance is not None
        except:
            pass

        return {
            "cuda_available": cuda_available,
            "memory_mb": {
                "allocated": round(allocated_mb, 2),
                "reserved": round(reserved_mb, 2),
                "max_allocated": round(max_allocated_mb, 2)
            },
            "models": {
                "onnx_models_loaded": models_loaded,
                "transdh_initialized": transdh_initialized
            }
        }

    # 保留旧接口以兼容
    @app.post("/api/cleanup/gpu")
    async def cleanup_gpu_legacy():
        """【兼容接口】请使用 POST /api/v1/gpu/release"""
        return await release_gpu()

    @app.get("/api/cleanup/gpu/status")
    async def gpu_status_legacy():
        """【兼容接口】请使用 GET /api/v1/gpu/status"""
        return await gpu_status()

    # ── 全局异常处理 ──

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Global exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(exc)}
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,
        reload=settings.DEBUG
    )
