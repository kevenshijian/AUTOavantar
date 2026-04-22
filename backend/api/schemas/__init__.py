"""
API 数据模型模块
定义请求和响应的数据结构
遵循 Pydantic V2 规范
"""

from backend.api.schemas.schemas import (
    # 任务相关
    TaskStatus,
    TaskStage, 
    ScriptSegment,
    TaskConfig,
    TaskBase,
    TaskResponse,
    TaskCreateRequest,
    TaskUpdateRequest,
    TaskControlRequest,
    TaskListResponse,
    TaskStatusUpdate,
    # 素材相关
    MaterialType,
    VideoItem,
    RoleMaterial,
    BgmMaterial,
    SceneMaterial,
    ReferenceAudio,
    Tag,
    # 响应模型
    ApiResponse,
    PaginatedResponse,
    # 系统相关
    SystemStatus,
    ServiceConfig,
)

__all__ = [
    # 任务相关
    "TaskStatus",
    "TaskStage", 
    "ScriptSegment",
    "TaskConfig",
    "TaskBase",
    "TaskResponse",
    "TaskCreateRequest",
    "TaskUpdateRequest",
    "TaskControlRequest",
    "TaskListResponse",
    "TaskStatusUpdate",
    # 素材相关
    "MaterialType",
    "VideoItem",
    "RoleMaterial",
    "BgmMaterial",
    "SceneMaterial",
    "ReferenceAudio",
    "Tag",
    # 响应模型
    "ApiResponse",
    "PaginatedResponse",
    # 系统相关
    "SystemStatus",
    "ServiceConfig",
]
