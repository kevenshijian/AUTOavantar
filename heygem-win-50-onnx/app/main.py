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

    @app.post("/api/cleanup/gpu")
    async def cleanup_gpu():
        """主动释放 GPU 显存（卸载所有 ONNX 模型）"""
        try:
            from app.inference.model_manager import get_model_manager
            manager = get_model_manager()

            # 记录清理前的 GPU 状态
            allocated_before = 0.0
            reserved_before = 0.0
            try:
                import torch
                if torch.cuda.is_available():
                    allocated_before = torch.cuda.memory_allocated() / 1024**2
                    reserved_before = torch.cuda.memory_reserved() / 1024**2
            except ImportError:
                pass

            # 卸载所有模型
            models_before = list(manager.get_loaded_models().keys())
            manager.unload_all()

            # 清空 PyTorch 缓存
            try:
                import torch
                import gc
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    gc.collect()
                    torch.cuda.empty_cache()
            except ImportError:
                pass

            # 记录清理后的 GPU 状态
            allocated_after = 0.0
            reserved_after = 0.0
            try:
                import torch
                if torch.cuda.is_available():
                    allocated_after = torch.cuda.memory_allocated() / 1024**2
                    reserved_after = torch.cuda.memory_reserved() / 1024**2
            except ImportError:
                pass

            logger.info(
                f"GPU cleanup: allocated {allocated_before:.1f}→{allocated_after:.1f}MB, "
                f"reserved {reserved_before:.1f}→{reserved_after:.1f}MB, "
                f"unloaded models: {models_before}"
            )

            return {
                "status": "success",
                "allocated_mb": round(allocated_after, 1),
                "reserved_mb": round(reserved_after, 1),
                "message": "GPU memory cleaned, all ONNX models unloaded"
            }
        except Exception as e:
            logger.error(f"GPU cleanup failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    @app.get("/api/cleanup/gpu/status")
    async def gpu_status():
        """查询当前 GPU 显存状态"""
        from app.inference.model_manager import get_model_manager

        allocated_mb = 0.0
        reserved_mb = 0.0
        try:
            import torch
            if torch.cuda.is_available():
                allocated_mb = torch.cuda.memory_allocated() / 1024**2
                reserved_mb = torch.cuda.memory_reserved() / 1024**2
        except ImportError:
            pass

        manager = get_model_manager()
        models_loaded = list(manager.get_loaded_models().keys())

        return {
            "allocated_mb": round(allocated_mb, 1),
            "reserved_mb": round(reserved_mb, 1),
            "models_loaded": models_loaded,
        }

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
