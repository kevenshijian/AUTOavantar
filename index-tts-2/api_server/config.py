"""
配置管理模块
基于 pydantic-settings + YAML 实现分层配置
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# api_server 目录作为 base_dir
_BASE_DIR = Path(__file__).resolve().parent


def _load_yaml_config() -> dict:
    """加载 api_server/config.yaml 默认配置"""
    config_path = _BASE_DIR / "config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


_yaml = _load_yaml_config()


class ServerSettings(BaseSettings):
    """服务配置"""

    host: str = Field("0.0.0.0", description="监听地址")
    port: int = Field(7860, description="监听端口")
    reload: bool = Field(False, description="热重载（仅开发环境）")


class ModelSettings(BaseSettings):
    """模型配置"""

    cfg_path: str = Field("checkpoints/config.yaml", description="模型配置文件路径")
    model_dir: str = Field("checkpoints", description="模型权重目录")
    is_fp16: bool = Field(True, description="FP16 混合精度推理")
    device: Optional[str] = Field(None, description="推理设备，None 自动检测")
    use_cuda_kernel: Optional[bool] = Field(None, description="BigVGAN CUDA kernel")


class InferenceSettings(BaseSettings):
    """推理默认参数"""

    mode: str = Field("fast", description="默认推理模式: fast | standard")
    temperature: float = Field(1.0, ge=0.1, le=2.0, description="默认生成温度")
    top_p: float = Field(0.8, ge=0.0, le=1.0, description="默认 top-p")
    top_k: int = Field(30, ge=1, le=100, description="默认 top-k")
    num_beams: int = Field(3, ge=1, le=10, description="默认 beam search 数量")


class QueueSettings(BaseSettings):
    """任务队列配置"""

    max_size: int = Field(10, ge=1, description="队列最大长度")
    task_timeout_sec: int = Field(600, ge=60, description="单任务最大等待+执行时间（秒）")


class VoiceSettings(BaseSettings):
    """音色配置"""

    voices_dir: str = Field("voices", description="预设音色目录")
    temp_dir: str = Field("tmp", description="临时音色文件目录")


class AudioSettings(BaseSettings):
    """音频输出配置"""

    output_dir: str = Field("outputs", description="合成音频输出目录")
    retention_hours: int = Field(24, ge=0, description="音频文件保留时间（小时），0 不清理")
    sample_rate: int = Field(24000, description="输出采样率")


class EmotionSettings(BaseSettings):
    """情绪映射配置"""

    mapping_file: str = Field("emotion_mapping.yaml", description="情绪映射文件，相对于 index-tts-2 目录")


class LoggingSettings(BaseSettings):
    """日志配置"""

    level: str = Field("INFO", description="日志级别")
    format: str = Field(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        description="日志格式",
    )


class Settings(BaseSettings):
    """
    应用全局配置

    优先级: 环境变量 > YAML 配置文件 > 默认值
    环境变量前缀: INDEXTTS_API_
    """

    model_config = SettingsConfigDict(
        env_prefix="INDEXTTS_API_",
        env_nested_delimiter="_",
        case_sensitive=False,
    )

    server: ServerSettings = Field(default_factory=lambda: ServerSettings(**_yaml.get("server", {})))
    model: ModelSettings = Field(default_factory=lambda: ModelSettings(**_yaml.get("model", {})))
    inference: InferenceSettings = Field(default_factory=lambda: InferenceSettings(**_yaml.get("inference", {})))
    queue: QueueSettings = Field(default_factory=lambda: QueueSettings(**_yaml.get("queue", {})))
    voice: VoiceSettings = Field(default_factory=lambda: VoiceSettings(**_yaml.get("voice", {})))
    audio: AudioSettings = Field(default_factory=lambda: AudioSettings(**_yaml.get("audio", {})))
    emotion: EmotionSettings = Field(default_factory=lambda: EmotionSettings(**_yaml.get("emotion", {})))
    logging_: LoggingSettings = Field(
        default_factory=lambda: LoggingSettings(**_yaml.get("logging", {})),
        alias="logging",
    )

    @property
    def base_dir(self) -> Path:
        """api_server 根目录"""
        return _BASE_DIR

    @property
    def project_dir(self) -> Path:
        """index-tts-2 项目根目录"""
        return _BASE_DIR.parent

    def get_model_cfg_path(self) -> str:
        """返回模型配置文件的绝对路径"""
        path = Path(self.model.cfg_path)
        if not path.is_absolute():
            path = self.project_dir / path
        return str(path)

    def get_model_dir(self) -> str:
        """返回模型权重目录的绝对路径"""
        path = Path(self.model.model_dir)
        if not path.is_absolute():
            path = self.project_dir / path
        return str(path)

    def get_voices_dir(self) -> str:
        """返回预设音色目录的绝对路径"""
        path = Path(self.voice.voices_dir)
        if not path.is_absolute():
            path = self.project_dir / path
        return str(path)

    def get_temp_dir(self) -> str:
        """返回临时目录的绝对路径"""
        path = Path(self.voice.temp_dir)
        if not path.is_absolute():
            path = self.project_dir / path
        return str(path)

    def get_output_dir(self) -> str:
        """返回音频输出目录的绝对路径"""
        path = Path(self.audio.output_dir)
        if not path.is_absolute():
            path = self.project_dir / path
        return str(path)

    def get_emotion_mapping_path(self) -> str:
        """返回情绪映射文件的绝对路径"""
        path = Path(self.emotion.mapping_file)
        if not path.is_absolute():
            path = self.project_dir / path
        return str(path)


# 全局单例
settings = Settings()
