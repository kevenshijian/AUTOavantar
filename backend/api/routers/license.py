"""
许可证管理路由
处理激活、状态检查等请求
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.services.license_service import get_license_service

router = APIRouter()


class ActivateRequest(BaseModel):
    """激活请求"""
    activation_code: str


class ActivateResponse(BaseModel):
    """激活响应"""
    success: bool
    message: str
    remaining_quota: int = 0
    max_quota: int = 0


class StatusResponse(BaseModel):
    """状态响应"""
    is_activated: bool
    machine_code: str
    remaining_quota: int
    max_quota: int
    activation_time: str | None = None


class QuotaResponse(BaseModel):
    """配额响应"""
    has_quota: bool
    remaining: int
    max_quota: int
    message: str = ""


@router.get("/status", response_model=StatusResponse)
async def get_status():
    """
    获取许可证状态

    Returns:
        许可证状态信息
    """
    service = get_license_service()
    status = service.get_license_status()

    return StatusResponse(
        is_activated=status.is_activated,
        machine_code=status.machine_code,
        remaining_quota=status.remaining_quota,
        max_quota=status.max_quota,
        activation_time=status.activation_time
    )


@router.post("/activate", response_model=ActivateResponse)
async def activate(request: ActivateRequest):
    """
    激活许可证

    Args:
        request: 包含激活码的请求

    Returns:
        激活结果
    """
    service = get_license_service()
    result = service.activate(request.activation_code)

    return ActivateResponse(
        success=result.success,
        message=result.message,
        remaining_quota=result.remaining_quota,
        max_quota=result.max_quota
    )


@router.get("/quota", response_model=QuotaResponse)
async def check_quota():
    """
    检查配额

    Returns:
        配额信息
    """
    service = get_license_service()
    result = service.check_quota()

    return QuotaResponse(
        has_quota=result.has_quota,
        remaining=result.remaining,
        max_quota=result.max_quota,
        message=result.message
    )


@router.post("/quota/consume")
async def consume_quota():
    """
    消耗一个配额

    Returns:
        剩余配额
    """
    service = get_license_service()

    if not service.check_and_consume_quota():
        raise HTTPException(status_code=403, detail="配额已用完")

    quota = service.check_quota()
    return {"remaining": quota.remaining, "message": "配额已消耗"}
