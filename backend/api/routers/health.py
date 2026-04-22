"""
健康检查路由
"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health_check():
    """健康检查接口 - 包含子服务状态"""
    from core.service_manager import get_service_manager
    
    sm = get_service_manager()
    services_status = {}
    
    if sm:
        status = sm.get_status()
        for name, svc_status in status.items():
            services_status[name] = {
                "status": svc_status.get("status", "unknown"),
                "pid": svc_status.get("pid"),
                "uptime_seconds": svc_status.get("uptime_seconds", 0),
                "error_message": svc_status.get("error_message")
            }
    else:
        services_status = {
            "indextts": {"status": "unknown", "error": "ServiceManager not initialized"},
            "heygem": {"status": "unknown", "error": "ServiceManager not initialized"}
        }
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "AUTOavantar API",
        "services": services_status
    }


@router.get("/health/services")
async def services_health_check():
    """子服务健康检查接口 - 返回 IndexTTS 和 HeyGem 的连通状态"""
    from core.service_manager import get_service_manager
    
    sm = get_service_manager()
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "services": {}
    }
    
    if sm:
        status = sm.get_status()
        for name, svc_status in status.items():
            result["services"][name] = {
                "status": svc_status.get("status", "unknown"),
                "pid": svc_status.get("pid"),
                "uptime_seconds": svc_status.get("uptime_seconds", 0),
                "error_message": svc_status.get("error_message")
            }
    else:
        result["services"] = {
            "indextts": {"status": "unknown", "error": "ServiceManager not initialized"},
            "heygem": {"status": "unknown", "error": "ServiceManager not initialized"}
        }
    
    return result
