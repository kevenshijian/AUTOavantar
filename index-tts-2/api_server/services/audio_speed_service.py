"""
音频语速调节服务
在 index-tts 中复用 audio_speed_processor.py 技术
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger("indextts-api.audio-speed")


class AudioSpeedService:
    """
    音频语速调节服务

    使用 FFmpeg + rubberband 滤镜实现高质量语速调节
    支持 0.8-1.2 倍语速范围
    管理临时音频文件的生命周期
    """

    def __init__(self, output_dir: str = "temp/audio_speed"):
        """
        初始化音频语速调节服务

        Args:
            output_dir: 临时音频文件输出目录
        """
        # 如果是相对路径，转换为绝对路径
        if not os.path.isabs(output_dir):
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            output_dir = os.path.join(project_root, output_dir)

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 跟踪所有生成的临时文件
        self._temp_files: Set[str] = set()

        logger.info(f"音频语速调节服务初始化: {self.output_dir}")

    def adjust_audio_speed(
        self,
        audio_path: str,
        speed: float,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        调节音频语速

        Args:
            audio_path: 输入音频路径
            speed: 语速倍率 (0.8-1.2)
            output_path: 输出音频路径（可选，默认自动生成）

        Returns:
            调节后的音频路径，失败返回 None
        """
        # 规范化路径：处理相对路径和正斜杠/反斜杠
        audio_path = os.path.normpath(audio_path.replace('\\', '/'))

        # 如果是相对路径，转换为绝对路径
        if not os.path.isabs(audio_path):
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            audio_path = os.path.join(project_root, audio_path)
            audio_path = os.path.normpath(audio_path)

        if not os.path.exists(audio_path):
            logger.error(f"音频文件不存在: {audio_path}")
            return None

        if speed == 1.0:
            logger.info(f"语速为 1.0，无需调节，直接返回原音频: {audio_path}")
            return audio_path

        if speed < 0.8 or speed > 1.2:
            logger.warning(f"语速 {speed} 超出支持范围 (0.8-1.2)，限制到范围内")
            speed = max(0.8, min(1.2, speed))

        if output_path is None:
            # 确保 output_dir 是绝对路径
            output_dir_abs = self.output_dir
            if not output_dir_abs.is_absolute():
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                output_dir_abs = Path(project_root) / self.output_dir
            output_path = str(
                output_dir_abs / f"speed_{Path(audio_path).stem}_{speed}x{Path(audio_path).suffix}"
            )
        else:
            # 如果提供了 output_path，确保是绝对路径
            output_path = os.path.abspath(output_path)

        # 确保输出目录存在
        output_dir_path = Path(output_path).parent
        output_dir_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"调节音频语速: {audio_path} -> {output_path}, 速度: {speed}x")

        try:
            # 使用 rubberband 滤镜进行语速调节
            # tempo 参数：>1 加快，<1 减慢
            cmd = [
                "ffmpeg",
                "-y",
                "-i", audio_path,
                "-af", f"rubberband=tempo={speed}",
                "-c:a", "libmp3lame",
                "-b:a", "320k",
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"音频语速调节成功: {output_path}")
                # 跟踪临时文件
                self._temp_files.add(output_path)
                return output_path
            else:
                logger.error(f"音频语速调节失败: {result.stderr}")
                return None

        except FileNotFoundError:
            logger.error("FFmpeg 未找到，请确保已安装并添加到 PATH")
            return None
        except Exception as e:
            logger.error(f"音频语速调节异常: {e}")
            return None

    def cleanup_temp_file(self, audio_path: str) -> None:
        """
        清理单个临时音频文件

        Args:
            audio_path: 要清理的音频文件路径
        """
        if audio_path in self._temp_files and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                self._temp_files.discard(audio_path)
                logger.info(f"已清理临时音频文件: {audio_path}")
            except Exception as e:
                logger.warning(f"清理临时音频文件失败: {audio_path}, 错误: {e}")

    def cleanup_all_temp_files(self) -> None:
        """
        清理所有临时音频文件
        """
        temp_files_list = list(self._temp_files)
        for audio_path in temp_files_list:
            self.cleanup_temp_file(audio_path)

        logger.info(f"已清理所有临时音频文件，共 {len(temp_files_list)} 个")

    def __del__(self):
        """
        析构函数：清理临时文件
        """
        self.cleanup_all_temp_files()


def create_audio_speed_service(output_dir: str = "temp/audio_speed") -> AudioSpeedService:
    """
    创建音频语速调节服务实例

    Args:
        output_dir: 临时音频文件输出目录

    Returns:
        AudioSpeedService 实例
    """
    return AudioSpeedService(output_dir)
