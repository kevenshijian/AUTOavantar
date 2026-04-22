"""
TTS 合成相关的数据模型
定义请求参数、响应格式和推理模式枚举
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class InferMode(str, Enum):
    """推理模式"""
    FAST = "fast"
    STANDARD = "standard"


class SynthesizeRequest(BaseModel):
    """
    TTS 合成请求模型 - 支持原版 IndexTTS2 情绪参数

    voice_name 和 reference_audio 二选一，至少提供一个。

    情绪控制方式（四选一）：
    1. emotion + intensity: 情绪标签 + 强度（通过映射表翻译为情绪参考音频）
    2. emo_audio_prompt + emo_alpha: 直接指定情绪参考音频 + 强度
    3. emo_vector: 8元素列表 [happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]
    4. use_emo_text=True: 根据文本自动推断情绪（可选配合 emo_text）
    """
    model_config = ConfigDict(from_attributes=True)

    text: str = Field(..., min_length=1, max_length=1000, description="合成文本，1-1000 字符")
    voice_name: Optional[str] = Field(None, description="预设音色名称，与 reference_audio 二选一")
    reference_audio: Optional[str] = Field(None, description="自定义音频文件路径（上传后由服务端填入）")

    emotion: Optional[str] = Field(None, description="情绪标签（如 '激动'、'悲伤'），通过映射表翻译为 emo_vector")
    intensity: float = Field(1.0, ge=0.0, le=1.6, description="情绪强度 0.0~2.0，作为 emo_alpha 传递给推理引擎")

    emo_audio_prompt: Optional[str] = Field(None, description="情绪参考音频路径（直接指定，优先级高于 emotion）")
    emo_alpha: float = Field(1.0, ge=0.0, le=1.6, description="情绪强度 0.0~2.0（配合 emo_audio_prompt 使用）")

    emo_vector: Optional[List[float]] = Field(None, description="8元素情绪向量 [happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]，直接指定时优先级最高")
    use_emo_text: bool = Field(False, description="是否根据文本自动推断情绪")
    emo_text: Optional[str] = Field(None, description="指定情绪文本（配合 use_emo_text=True 使用）")
    use_random: bool = Field(False, description="是否启用随机采样（会降低音色克隆保真度）")

    inference_mode: InferMode = Field(InferMode.FAST, description="推理模式：fast（默认）或 standard")
    temperature: float = Field(1.0, ge=0.1, le=2.0, description="生成温度")
    top_p: float = Field(0.8, ge=0.0, le=1.0, description="Top-p 采样阈值")
    top_k: int = Field(30, ge=1, le=100, description="Top-k 采样数量")
    num_beams: int = Field(3, ge=1, le=10, description="Beam search 数量")


class SynthesizeResponse(BaseModel):
    """TTS 合成任务提交响应（202 Accepted）"""
    model_config = ConfigDict(from_attributes=True)

    task_id: str = Field(..., description="任务唯一标识")
    status: str = Field("pending", description="任务状态")
    queue_position: int = Field(..., description="队列位置，0 表示正在处理")


class TaskDetailResponse(BaseModel):
    """任务详情查询响应（200 OK）"""
    model_config = ConfigDict(from_attributes=True)

    task_id: str = Field(..., description="任务唯一标识")
    status: str = Field(..., description="任务状态：pending | processing | completed | failed")
    audio_url: Optional[str] = Field(None, description="音频文件 URL，completed 时返回")
    duration_sec: Optional[float] = Field(None, description="音频时长（秒），completed 时返回")
    inference_time_sec: Optional[float] = Field(None, description="推理耗时（秒），completed 时返回")
    error_message: Optional[str] = Field(None, description="错误信息，failed 时返回")
    created_at: Optional[datetime] = Field(None, description="任务创建时间")
    completed_at: Optional[datetime] = Field(None, description="任务完成时间")


class QueueStatusResponse(BaseModel):
    """队列状态查询响应（200 OK）"""
    model_config = ConfigDict(from_attributes=True)

    task_id: str = Field(..., description="任务唯一标识")
    queue_position: int = Field(..., description="队列位置，0 表示正在处理")
