from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: float = 0.0
    message: str = ""
    result_url: Optional[str] = None
    created_at: str
    updated_at: str

class TemplateInfo(BaseModel):
    template_id: str
    name: str
    description: str
    preview_url: str
    duration: float
    resolution: str
    created_at: str

class TemplateDetail(BaseModel):
    template_id: str
    name: str
    description: str
    preview_url: str
    video_duration: float
    resolution: str
    fps: int
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = {}

class HealthResponse(BaseModel):
    status: str
    version: str
    models_loaded: bool
    gpu_available: bool

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None

class GenerateResult(BaseModel):
    task_id: str
    status: TaskStatus
    video_url: Optional[str] = None
    duration: Optional[float] = None
    message: str = ""
