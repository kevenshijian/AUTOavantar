#!/user/bin/env python
# coding=utf-8
"""
@project : digital-human-api
@author  : system
@file   : config.py
@ide    : PyCharm
@time   : 2025-03-10
"""

from pathlib import Path
from typing import Optional

from pydantic.v1 import BaseSettings, Field


class Settings(BaseSettings):
    PROJECT_NAME: str = Field(default="Digital Human API", description="Project name")
    VERSION: str = Field(default="1.0.0", description="API version")
    DEBUG: bool = Field(default=False, description="Debug mode")

    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=9889, description="Server port")
    WORKERS: int = Field(default=1, description="Number of workers")

    # 模型路径配置 — 各模型分布在不同目录，需分别指定
    DINET_MODEL_DIR: Path = Field(
        default=Path("landmark2face_wy/checkpoints/anylang"),
        description="DINet model directory"
    )
    DINET_MODEL: str = Field(
        default="dinet_v1_20240131_wrapped.onnx",
        description="DINet model filename"
    )
    SCRFD_MODEL_DIR: Path = Field(
        default=Path("face_detect_utils/resources"),
        description="SCRFD model directory"
    )
    SCRFD_MODEL: str = Field(
        default="scrfd_500m_bnkps_shape640x640.onnx",
        description="SCRFD face detection model filename"
    )
    GFPGAN_MODEL_DIR: Path = Field(
        default=Path("pretrain_models/face_lib/face_restore/gfpgan"),
        description="GFPGAN model directory"
    )
    GFPGAN_MODEL: str = Field(
        default="GFPGANv1.4.onnx",
        description="GFPGAN face restoration model filename"
    )

    DEVICE: str = Field(default="cuda", description="Inference device (cuda/cpu)")
    BATCH_SIZE: int = Field(default=4, description="Batch size for inference")

    # WeNet BNF 特征提取配置
    WENET_MODEL: str = Field(
        default="wenet/examples/aishell/aidata/exp/conformer/wenetmodel.pt",
        description="WeNet Conformer model path (relative to heygem root)"
    )
    WENET_CONFIG: str = Field(
        default="wenet/examples/aishell/aidata/conf/train_conformer_multi_cn.yaml",
        description="WeNet Conformer config path (relative to heygem root)"
    )
    WENET_DEVICE: str = Field(
        default="cpu",
        description="WeNet inference device (cpu recommended, saves GPU memory)"
    )
    USE_TENSORRT: bool = Field(default=False, description="Enable TensorRT acceleration")
    TENSORRT_PRECISION: str = Field(default="fp16", description="TensorRT precision (fp32/fp16/int8)")

    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_DB: int = Field(default=0, description="Redis database index")

    TEMPLATES_DIR: Path = Field(default=Path("templates"), description="Templates directory")
    TEMP_DIR: Path = Field(default=Path("temp"), description="Temporary files directory")
    RESULT_DIR: Path = Field(default=Path("result"), description="Result files directory")

    LOG_DIR: Path = Field(default=Path("log"), description="Log directory")
    LOG_LEVEL: str = Field(default="INFO", description="Log level (DEBUG/INFO/WARNING/ERROR)")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_model_path(model_name: str) -> Path:
    """根据模型名称返回完整模型路径

    Args:
        model_name: 模型名称 ("dinet", "scrfd", "gfpgan")

    Returns:
        模型文件的完整路径
    """
    settings = get_settings()
    model_dirs = {
        "dinet": (settings.DINET_MODEL_DIR, settings.DINET_MODEL),
        "scrfd": (settings.SCRFD_MODEL_DIR, settings.SCRFD_MODEL),
        "gfpgan": (settings.GFPGAN_MODEL_DIR, settings.GFPGAN_MODEL),
    }
    if model_name.lower() in model_dirs:
        model_dir, model_file = model_dirs[model_name.lower()]
        return model_dir / model_file
    raise ValueError(f"Unknown model: {model_name}")
