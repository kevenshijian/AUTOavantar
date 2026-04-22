"""
FastAPI 依赖注入
提供数据库等基础依赖（已移除认证相关功能）
"""

from fastapi import Depends
from api.services.database import DatabaseService, get_database_service


async def get_db() -> DatabaseService:
    """获取数据库服务依赖"""
    return get_database_service()
