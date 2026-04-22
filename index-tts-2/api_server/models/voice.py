"""
音色相关的数据模型
定义音色信息查询和上传响应的数据结构
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class VoiceInfo(BaseModel):
    """单个音色信息"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="音色名称（不含扩展名）")
    file: str = Field(..., description="音色文件名")
    size_bytes: int = Field(..., description="文件大小（字节）")
    status: str = Field("ready", description="音色状态: ready | error")


class VoiceListResponse(BaseModel):
    """预设音色列表响应"""

    model_config = ConfigDict(from_attributes=True)

    voices: list[VoiceInfo] = Field(default_factory=list, description="音色列表")


class VoiceUploadResponse(BaseModel):
    """音色上传（临时）响应"""

    model_config = ConfigDict(from_attributes=True)

    temp_path: str = Field(..., description="临时音色特征文件路径")
    feature_shape: list[int] = Field(..., description="特征张量形状")


class VoiceCreateResponse(BaseModel):
    """音色创建（保存为预设）响应"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="音色名称")
    file: str = Field(..., description="音色文件名")
    size_bytes: int = Field(..., description="文件大小（字节）")
    status: str = Field("ready", description="音色状态")
    created_at: Optional[datetime] = Field(None, description="创建时间")
