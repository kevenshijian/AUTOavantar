from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class GenerateRequest(BaseModel):
    audio_url: str = Field(..., description="音频文件URL")
    template_id: str = Field(..., description="数字人模板ID")
    enhance_face: bool = Field(True, description="是否启用人脸增强")
    output_format: str = Field("mp4", description="输出格式")
    callback_url: Optional[str] = Field(None, description="回调URL")

class GenerateSyncRequest(BaseModel):
    audio_url: str = Field(..., description="音频文件URL")
    template_id: str = Field(..., description="数字人模板ID")
    enhance_face: bool = Field(True, description="是否启用人脸增强")

class TemplateCreateRequest(BaseModel):
    name: str = Field(..., description="模板名称")
    description: str = Field("", description="模板描述")
