"""
系统配置 API 路由
提供低显存模式等系统级设置的获取和更新接口
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.system_config import get_config_manager

logger = logging.getLogger("autoavantar-api")

router = APIRouter()


class SystemConfigResponse(BaseModel):
    """系统配置响应模型"""
    low_memory_mode: bool


class SystemConfigUpdateRequest(BaseModel):
    """系统配置更新请求模型"""
    low_memory_mode: Optional[bool] = None


@router.get("/config", response_model=SystemConfigResponse)
async def get_system_config():
    """
    获取系统配置
    
    返回当前系统配置，包括低显存模式状态
    → AC-218
    """
    try:
        config_manager = get_config_manager()
        low_memory_mode = config_manager.get_low_memory_mode()
        
        return SystemConfigResponse(low_memory_mode=low_memory_mode)
    except Exception as e:
        logger.error(f"获取系统配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取系统配置失败: {str(e)}")


@router.put("/config", response_model=SystemConfigResponse)
async def update_system_config(request: SystemConfigUpdateRequest):
    """
    更新系统配置
    
    更新系统配置并持久化保存
    → AC-219
    """
    try:
        config_manager = get_config_manager()
        
        # 更新低显存模式
        if request.low_memory_mode is not None:
            success = config_manager.set_low_memory_mode(request.low_memory_mode)
            if not success:
                raise HTTPException(status_code=500, detail="保存配置失败")
            
            logger.info(f"系统配置已更新: low_memory_mode={request.low_memory_mode}")
        
        # 返回更新后的配置
        return SystemConfigResponse(
            low_memory_mode=config_manager.get_low_memory_mode()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新系统配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新系统配置失败: {str(e)}")
