"""
服务管理路由
提供 IndexTTS 和 HeyGem 服务的状态查询、重启、启动、停止等操作
"""

from fastapi import APIRouter, HTTPException
from typing import Literal

router = APIRouter()

ServiceName = Literal["indextts", "heygem"]


def _get_service_manager():
    """获取 ServiceManager 实例"""
    from core.service_manager import get_service_manager
    sm = get_service_manager()
    if not sm:
        raise HTTPException(
            status_code=500,
            detail="ServiceManager not initialized"
        )
    return sm


@router.get("/services/status")
async def get_services_status():
    """
    查询所有服务状态
    
    Returns:
        包含 IndexTTS 和 HeyGem 运行状态的字典
    """
    sm = _get_service_manager()
    status = sm.get_status()
    return {"services": status}


@router.post("/services/{service_name}/restart")
async def restart_service(service_name: ServiceName):
    """
    重启指定服务
    
    Args:
        service_name: 服务名称 ("indextts" 或 "heygem")
        
    Returns:
        重启结果
    """
    sm = _get_service_manager()
    
    try:
        success = sm.restart_service(service_name)
        if success:
            return {
                "service": service_name,
                "status": "running",
                "message": "Service restarted successfully"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to restart service {service_name}"
            )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Python environment not found: {e}"
        )


@router.post("/services/{service_name}/start")
async def start_service(service_name: ServiceName):
    """
    启动指定服务（仅在服务停止时有效）
    
    Args:
        service_name: 服务名称 ("indextts" 或 "heygem")
        
    Returns:
        启动结果
    """
    sm = _get_service_manager()
    
    # 检查服务状态
    status = sm.get_status(service_name)
    if status.get("status") == "running":
        raise HTTPException(
            status_code=400,
            detail=f"Service {service_name} is already running"
        )
    
    try:
        success = sm.start_service(service_name)
        if success:
            return {
                "service": service_name,
                "status": "running",
                "message": "Service started successfully"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start service {service_name}"
            )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Python environment not found: {e}"
        )


@router.post("/services/{service_name}/stop")
async def stop_service(service_name: ServiceName):
    """
    停止指定服务
    
    Args:
        service_name: 服务名称 ("indextts" 或 "heygem")
        
    Returns:
        停止结果
    """
    sm = _get_service_manager()
    
    success = sm.stop_service(service_name)
    if success:
        return {
            "service": service_name,
            "status": "stopped",
            "message": "Service stopped successfully"
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop service {service_name}"
        )
