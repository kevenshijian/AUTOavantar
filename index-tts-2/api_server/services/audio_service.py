"""
音频文件服务
管理合成音频的存储、访问和清理
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("indextts-api.audio")


class AudioService:
    """
    音频文件服务

    - 生成音频文件输出路径
    - 查找音频文件
    - 清理过期音频文件
    """

    def __init__(self, output_dir: str, retention_hours: int = 24) -> None:
        """
        Args:
            output_dir: 音频输出目录
            retention_hours: 文件保留时间（小时），0 表示不清理
        """
        self._output_dir = Path(output_dir)
        self._retention_hours = retention_hours
        self._output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"音频服务初始化: dir={self._output_dir}, retention={retention_hours}h")

    def generate_output_path(self, task_id: str) -> str:
        """为任务生成输出文件路径"""
        return str(self._output_dir / f"{task_id}.wav")

    def get_audio_path(self, filename: str) -> Optional[str]:
        """
        根据文件名获取音频文件完整路径。

        Args:
            filename: 文件名（如 "abc123.wav"）

        Returns:
            文件完整路径，不存在则返回 None
        """
        # 安全检查：防止路径遍历
        if ".." in filename or "/" in filename or "\\" in filename:
            return None

        path = self._output_dir / filename
        if path.exists() and path.is_file():
            return str(path)
        return None

    def cleanup_expired(self) -> int:
        """
        清理过期的音频文件。

        Returns:
            清理的文件数量
        """
        if self._retention_hours <= 0:
            return 0

        cutoff = time.time() - self._retention_hours * 3600
        cleaned = 0
        total_scanned = 0

        for filepath in self._output_dir.glob("*.wav"):
            total_scanned += 1
            if filepath.stat().st_mtime < cutoff:
                try:
                    file_size_mb = filepath.stat().st_size / 1024 / 1024
                    filepath.unlink()
                    cleaned += 1
                    logger.debug(f"清理音频: {filepath.name} ({file_size_mb:.2f}MB)")
                except OSError as e:
                    logger.warning(f"清理音频文件失败: {filepath}, 错误: {e}")

        if cleaned > 0:
            logger.info(
                f"清理完成: 扫描 {total_scanned} 个文件, 删除 {cleaned} 个过期文件, "
                f"保留策略: {self._retention_hours}h"
            )

        return cleaned
