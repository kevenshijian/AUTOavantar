"""
任务相关的数据模型
定义任务状态枚举和任务信息的数据结构
"""

from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    """任务状态枚举"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskInfo(BaseModel):
    """内部任务信息（用于任务队列管理）- 支持原版 IndexTTS2 情绪参数"""

    task_id: str = Field(..., description="任务唯一标识")
    status: TaskStatus = Field(TaskStatus.PENDING, description="当前状态")
    text: str = Field(..., description="合成文本")
    voice_path: str = Field(..., description="音色特征文件路径")
    output_path: Optional[str] = Field(None, description="输出音频文件路径")

    emo_audio_prompt: Optional[str] = Field(None, description="情绪参考音频路径")
    emo_alpha: float = Field(1.0, description="情绪强度 0.0~1.0")
    emo_vector: Optional[List[float]] = Field(None, description="8元素情绪向量")
    use_emo_text: bool = Field(False, description="是否根据文本自动推断情绪")
    emo_text: Optional[str] = Field(None, description="指定情绪文本")
    use_random: bool = Field(False, description="是否启用随机采样")

    temperature: float = Field(1.0, description="生成温度")
    top_p: float = Field(0.8, description="Top-p")
    top_k: int = Field(30, description="Top-k")
    num_beams: int = Field(3, description="Beam search 数量")

    audio_url: Optional[str] = Field(None, description="音频访问 URL，completed 时填入")
    duration_sec: Optional[float] = Field(None, description="音频时长（秒），completed 时填入")
    inference_time_sec: Optional[float] = Field(None, description="推理耗时（秒），completed 时填入")
    error_message: Optional[str] = Field(None, description="错误信息，failed 时填入")
    queue_position: int = Field(0, description="队列位置，0 表示正在处理")
    estimated_wait_sec: Optional[float] = Field(None, description="预估等待时间（秒）")
    created_at: Optional[str] = Field(None, description="任务创建时间（ISO 8601）")
    completed_at: Optional[str] = Field(None, description="任务完成时间（ISO 8601）")
