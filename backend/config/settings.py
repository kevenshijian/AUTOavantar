"""
配置管理模块
定义应用配置和环境变量
"""

import os
import secrets
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # API 配置
    API_TITLE: str = "AUTOavantar API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "数字人视频生成系统 API"
    
    # JWT 配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    
    # CORS 配置
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 9010
    RELOAD: bool = True
    
    # 文件上传配置
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_VIDEO_EXTENSIONS: list = [".mp4", ".avi", ".mov", ".mkv", ".wmv"]
    ALLOWED_AUDIO_EXTENSIONS: list = [".mp3", ".wav", ".m4a", ".aac", ".flac"]
    
    # 任务配置
    TASK_POLL_INTERVAL: int = 3  # 轮询间隔（秒）
    MAX_CONCURRENT_TASKS: int = 3

    # LLM 配置
    LLM_PROVIDER: str = "deepseek"
    LLM_API_KEY: Optional[str] = None

    # 路径配置
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    OUTPUT_DIR: str = "output"
    TEMP_DIR: str = "tmp"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


def get_settings() -> Settings:
    """获取配置实例"""
    return Settings()


settings = get_settings()
