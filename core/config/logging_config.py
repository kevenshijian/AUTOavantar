"""
统一日志配置模块
确保所有模块使用相同的日志记录方式
"""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir: str = "logs") -> None:
    """
    设置统一的日志配置

    Args:
        log_dir: 日志文件目录
    """
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)

    # 日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # 控制台处理器（强制UTF-8编码）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    # 修复Windows控制台编码问题
    if hasattr(console_handler.stream, 'reconfigure'):
        console_handler.stream.reconfigure(encoding='utf-8')

    # 文件处理器（带轮转，UTF-8编码）
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "autoavantar.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))

    # 根日志配置
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # 禁用某些第三方库的日志
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("ffmpeg").setLevel(logging.WARNING)

    # 记录初始化信息
    root_logger.info("日志配置初始化完成")
