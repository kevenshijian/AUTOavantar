"""
FastAPI 应用入口
AUTOavantar 数字人视频生成系统后端 API
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.services.database import init_database, close_database
from api.services.workflow_service import init_workflow_service, shutdown_workflow_service
from api.routers.websocket import manager
from config.settings import settings

# 添加项目路径到 sys.path，确保可以导入 core 模块
base_dir = Path(__file__).parent.parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from core.config.logging_config import setup_logging

# 配置日志
setup_logging()

# 获取 logger
logger = logging.getLogger("autoavantar-api")


async def websocket_heartbeat_checker():
    """WebSocket 心跳检测后台任务"""
    while True:
        try:
            # 增加超时时间到 120 秒，给浏览器更多时间
            await manager.check_inactive_connections(timeout_seconds=120)
            await asyncio.sleep(30)  # 每 30 秒检查一次
        except Exception as e:
            logger.error(f"WebSocket 心跳检测异常: {e}")
            await asyncio.sleep(5)


# ServiceManager 全局实例
_service_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理
    
    启动顺序优化：
    1. 创建必要目录
    2. 初始化数据库和工作流服务（确保 API 立即可用）
    3. 初始化 ServiceManager
    4. 启动 WebSocket 心跳检测
    5. 后台启动 IndexTTS 和 HeyGem 服务（不阻塞 API 就绪）
    """
    global _service_manager
    
    # 启动时执行
    logger.info("=" * 50)
    logger.info("AUTOavantar API 服务启动中...")

    # 1. 创建必要的目录
    os.makedirs("data", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)

    # 2. 初始化数据库（优先初始化，确保 API 立即可用）
    try:
        db = await init_database()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        db = None

    # 3. 初始化工作流服务（优先初始化，确保 API 立即可用）
    try:
        workflow_service = await init_workflow_service(
            output_dir="output",
            max_concurrent_tasks=3,
            database=db
        )
        logger.info("工作流服务初始化完成")

        # 恢复未完成的任务（断点续传）
        if db:
            recovered = await workflow_service.recover_incomplete_tasks()
            if recovered:
                logger.info(f"已恢复 {len(recovered)} 个未完成任务")
    except Exception as e:
        logger.error(f"工作流服务初始化失败: {e}")

    # 4. 初始化 ServiceManager（但不启动服务）
    try:
        from core.service_manager import create_service_manager, destroy_service_manager
        from core.system_config import get_config_manager
        
        _service_manager = create_service_manager()
        logger.info("ServiceManager 初始化完成")
        
    except Exception as e:
        logger.error(f"ServiceManager 初始化失败: {e}")
        _service_manager = None

    # 5. 启动 WebSocket 心跳检测任务
    heartbeat_task = asyncio.create_task(websocket_heartbeat_checker())
    logger.info("WebSocket 心跳检测已启动")

    # API 已就绪，可以开始接收请求
    logger.info("=" * 50)
    logger.info("✅ AUTOavantar API 服务已就绪")
    logger.info("=" * 50)

    # 6. 后台启动 IndexTTS 和 HeyGem 服务（不阻塞 API 就绪）
    if _service_manager:
        try:
            from core.system_config import get_config_manager
            config_manager = get_config_manager()
            low_memory_mode = config_manager.get_low_memory_mode()
            
            if low_memory_mode:
                logger.info("低显存模式已启用，启动时不启动 IndexTTS 和 HeyGem")
            else:
                async def start_services_background():
                    await asyncio.sleep(1.0)  # 延迟 1 秒，确保 API 完全就绪
                    try:
                        logger.info("开始后台启动 IndexTTS 服务...")
                        success = _service_manager.start_service("indextts")
                        if success:
                            logger.info("✅ IndexTTS 服务启动成功")
                        else:
                            logger.error("❌ IndexTTS 服务启动失败")
                    except Exception as e:
                        logger.error(f"❌ IndexTTS 服务启动异常: {e}")
                    
                    try:
                        logger.info("开始后台启动 HeyGem 服务...")
                        success = _service_manager.start_service("heygem")
                        if success:
                            logger.info("✅ HeyGem 服务启动成功")
                        else:
                            logger.error("❌ HeyGem 服务启动失败")
                    except Exception as e:
                        logger.error(f"❌ HeyGem 服务启动异常: {e}")
                
                asyncio.create_task(start_services_background())
                logger.info("📋 服务启动任务已提交（后台执行，不阻塞 API）")
                
        except Exception as e:
            logger.error(f"服务启动配置检查失败: {e}")

    yield

    # 关闭时执行
    logger.info("AUTOavantar API 服务关闭中...")

    # 取消 WebSocket 心跳检测任务
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    logger.info("WebSocket 心跳检测已停止")

    # 关闭工作流服务
    try:
        await shutdown_workflow_service()
        logger.info("工作流服务已关闭")
    except Exception as e:
        logger.error(f"工作流服务关闭失败: {e}")

    # 关闭数据库
    try:
        await close_database()
        logger.info("数据库连接已关闭")
    except Exception as e:
        logger.error(f"数据库关闭失败: {e}")

    # 关闭 ServiceManager
    try:
        from core.service_manager import destroy_service_manager
        destroy_service_manager()
        logger.info("ServiceManager 已关闭")
    except Exception as e:
        logger.error(f"ServiceManager 关闭失败: {e}")


# 创建 FastAPI 应用
app = FastAPI(
    title="AUTOavantar API",
    version="1.0.0",
    description="数字人视频生成系统后端 API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
if os.path.exists("uploads"):
    # 替换StaticFiles为自定义文件服务，禁用缓存
    from fastapi import Response
    from starlette.responses import FileResponse
    
    @app.get("/files/{file_path:path}")
    async def serve_files(file_path: str):
        """自定义文件服务，禁用浏览器缓存，支持多个目录"""
        import os
        from pathlib import Path
        
        # 标准化路径：替换反斜杠为正斜杠
        file_path = file_path.replace('\\', '/')
        
        # 确定后端根目录（相对于当前工作目录）
        # 后端从 backend/ 目录启动，所以需要向上找一级
        current_dir = Path.cwd()
        if current_dir.name == "backend":
            backend_root = current_dir
        else:
            backend_root = current_dir / "backend"
        
        # 如果路径已经包含 backend/ 前缀，需要去掉它
        if file_path.startswith('backend/'):
            file_path = file_path[8:]  # 去掉 "backend/" 前缀
        
        # 搜索路径列表（相对于后端根目录）
        search_paths = [
            backend_root / "uploads" / file_path,
            backend_root / file_path,
            backend_root / "data" / file_path,
            Path.cwd().parent / "uploads" / file_path,  # 项目根目录下的 uploads
            Path.cwd().parent / "backend" / file_path,  # 项目根目录下的 backend
        ]
        
        file_full_path = None
        for path in search_paths:
            if path.exists() and path.is_file():
                file_full_path = path
                break
        
        if not file_full_path:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        
        # 使用FileResponse并设置缓存控制头，禁用缓存
        return FileResponse(
            path=file_full_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

# 注册路由 - 调整顺序，将具体路由放在通配符路由之前
from api.routers import tasks, materials, upload, health, websocket, settings, functions, tags, services, system

# 1. 健康检查（最具体的路由）
app.include_router(health.router, prefix="/api", tags=["健康检查"])

# 1.1 系统配置路由
app.include_router(system.router, prefix="/api/system", tags=["系统配置"])

# 1.5 服务管理路由
app.include_router(services.router, prefix="/api", tags=["服务管理"])

# 2. 功能接口（具体路由）
app.include_router(functions.router, prefix="/api", tags=["功能接口"])

# 3. 素材库（具体路由）
app.include_router(materials.router, prefix="/api", tags=["素材库"])

# 4. 上传（具体路由）
app.include_router(upload.router, prefix="/api", tags=["文件上传"])

# 5. WebSocket（具体路由）
app.include_router(websocket.router, prefix="/api", tags=["WebSocket"])

# 6. 设置（具体路由）
app.include_router(settings.router, prefix="/api/settings", tags=["系统设置"])

# 7. 标签管理（具体路由）
app.include_router(tags.router, prefix="/api/tags", tags=["标签管理"])

# 8. 任务管理（包含通配符路由，放在最后）
app.include_router(tasks.router, prefix="/api/tasks", tags=["任务管理"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "AUTOavantar API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
        "websocket": "/api/ws/{task_id}"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=9010,
        reload=True
    )
