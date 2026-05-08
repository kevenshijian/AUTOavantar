"""
许可证管理路由
处理激活、状态检查等请求
"""

import time
from collections import defaultdict
from threading import Lock

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.services.license_service import get_license_service

router = APIRouter()


# ============================================================
# 速率限制器 - 防止暴力破解攻击
# ============================================================
class RateLimiter:
    """
    简单的内存速率限制器

    使用滑动窗口算法，基于客户端 IP 进行限制
    """

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        """
        初始化速率限制器

        Args:
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口（秒）
        """
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """
        检查是否允许请求

        Args:
            client_id: 客户端标识（通常是 IP 地址）

        Returns:
            (是否允许, 剩余等待秒数)
        """
        now = time.time()
        cutoff = now - self._window_seconds

        with self._lock:
            # 清理过期记录
            self._requests[client_id] = [
                t for t in self._requests[client_id] if t > cutoff
            ]

            # 检查是否超过限制
            if len(self._requests[client_id]) >= self._max_requests:
                # 计算需要等待的时间
                oldest = self._requests[client_id][0]
                wait_seconds = int(oldest + self._window_seconds - now) + 1
                return False, max(1, wait_seconds)

            # 记录本次请求
            self._requests[client_id].append(now)
            return True, 0

    def get_remaining(self, client_id: str) -> int:
        """获取剩余请求次数"""
        now = time.time()
        cutoff = now - self._window_seconds

        with self._lock:
            self._requests[client_id] = [
                t for t in self._requests[client_id] if t > cutoff
            ]
            return max(0, self._max_requests - len(self._requests[client_id]))


# 激活接口速率限制器：每分钟最多 5 次尝试
_activate_limiter = RateLimiter(max_requests=5, window_seconds=60)


def _get_client_ip(request: Request) -> str:
    """获取客户端 IP 地址"""
    # 检查代理头
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # 检查真实 IP 头
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # 使用直接连接 IP
    return request.client.host if request.client else "unknown"


# ============================================================
# 请求/响应模型
# ============================================================
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
    license_type: str | None = None  # yearly/three_year/lifetime
    expires_at: str | None = None  # 过期时间


class QuotaResponse(BaseModel):
    """配额响应"""
    has_quota: bool
    remaining: int
    max_quota: int
    message: str = ""


# ============================================================
# 路由端点
# ============================================================
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
        activation_time=status.activation_time,
        license_type=status.license_type,
        expires_at=status.expires_at
    )


@router.post("/activate", response_model=ActivateResponse)
async def activate(request: Request, body: ActivateRequest):
    """
    激活许可证

    Args:
        request: FastAPI 请求对象（用于速率限制）
        body: 包含激活码的请求体

    Returns:
        激活结果

    Raises:
        HTTPException: 速率限制触发时返回 429
    """
    # 速率限制检查
    client_ip = _get_client_ip(request)
    allowed, wait_seconds = _activate_limiter.is_allowed(client_ip)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"请求过于频繁，请 {wait_seconds} 秒后重试"
        )

    # 输入长度验证
    if len(body.activation_code) > 2048:
        raise HTTPException(
            status_code=400,
            detail="激活码格式无效"
        )

    service = get_license_service()
    result = service.activate(body.activation_code)

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


@router.get("/quota/stage/{stage}", response_model=QuotaResponse)
async def check_quota_for_stage(stage: str):
    """
    检查指定环节的配额

    Args:
        stage: 环节名称 (create/audio/video/postprocess)

    Returns:
        配额信息
    """
    # 校验 stage 参数
    valid_stages = {"create", "audio", "video", "postprocess"}
    if stage not in valid_stages:
        raise HTTPException(
            status_code=400,
            detail=f"无效的环节: {stage}。有效值: {', '.join(valid_stages)}"
        )

    service = get_license_service()
    result = service.check_quota_for_stage(stage)

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
