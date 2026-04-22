"""
系统监控相关的数据模型
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GpuInfo(BaseModel):
    """GPU 详细信息"""

    model_config = ConfigDict(from_attributes=True)

    available: bool = Field(False, description="GPU 是否可用")
    name: Optional[str] = Field(None, description="GPU 名称")
    memory_total_mb: Optional[float] = Field(None, description="GPU 显存总量 (MB)")
    memory_used_mb: Optional[float] = Field(None, description="GPU 显存已用 (MB)")
    memory_free_mb: Optional[float] = Field(None, description="GPU 显存可用 (MB)")
    memory_utilization: Optional[float] = Field(None, description="GPU 显存利用率 (0-100%)")


class TaskStats(BaseModel):
    """任务统计信息"""

    model_config = ConfigDict(from_attributes=True)

    total: int = Field(0, description="历史总任务数")
    pending: int = Field(0, description="当前等待中")
    processing: int = Field(0, description="当前处理中")
    completed: int = Field(0, description="已完成")
    failed: int = Field(0, description="失败")


class HealthResponse(BaseModel):
    """健康检查响应"""

    model_config = ConfigDict(from_attributes=True)

    status: str = Field(..., description="服务状态: loading | ready | error")
    model_loaded: bool = Field(False, description="模型是否已加载")
    model_device: Optional[str] = Field(None, description="当前推理设备")
    fp16: bool = Field(False, description="是否使用 FP16")
    gpu: GpuInfo = Field(default_factory=GpuInfo, description="GPU 详细信息")
    current_queue_length: int = Field(0, description="当前队列长度")
    task_stats: TaskStats = Field(default_factory=TaskStats, description="任务统计")
    emotion_service_available: bool = Field(False, description="情绪映射服务是否可用")
    uptime_sec: float = Field(0, description="服务运行时长（秒）")
    version: str = Field("0.1.0", description="服务版本号")


class ConfigResponse(BaseModel):
    """配置查询响应"""

    model_config = ConfigDict(from_attributes=True)

    inference_mode: str = Field(..., description="默认推理模式")
    device: str = Field(..., description="推理设备")
    fp16: bool = Field(..., description="FP16 状态")
    max_queue_size: int = Field(..., description="队列最大长度")
    task_timeout_sec: int = Field(..., description="单任务超时时间（秒）")
    audio_retention_hours: int = Field(..., description="音频保留时间（小时）")
    default_generation_params: dict = Field(..., description="默认生成参数")


class UnloadResponse(BaseModel):
    """模型卸载响应"""

    model_config = ConfigDict(from_attributes=True)

    success: bool = Field(..., description="是否成功卸载")
    message: str = Field("", description="描述信息")
