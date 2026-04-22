"""
音色管理服务
管理预设音色的加载、查询和特征提取
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional

import torch
import torchaudio

logger = logging.getLogger("indextts-api.voice")


class VoiceManager:
    """
    音色管理服务

    - 扫描预设音色目录，加载音色列表
    - 从上传的音频文件提取 Mel 频谱特征
    - 保存新音色特征
    """

    def __init__(self, voices_dir: str, temp_dir: str) -> None:
        """
        Args:
            voices_dir: 预设音色目录
            temp_dir: 临时音色文件目录
        """
        self._voices_dir = Path(voices_dir)
        self._temp_dir = Path(temp_dir)
        self._voices_dir.mkdir(parents=True, exist_ok=True)
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        # 缓存音色列表: {name: {"file": ..., "size_bytes": ..., "status": ...}}
        self._voice_cache: dict[str, dict] = {}

    def scan_voices(self) -> list[dict]:
        """
        扫描预设音色目录，返回音色列表。

        Returns:
            [{"name": str, "file": str, "size_bytes": int, "status": "ready"|"error"}, ...]
        """
        voices = []
        self._voice_cache.clear()

        for filepath in sorted(self._voices_dir.glob("*.pt")):
            name = filepath.stem
            try:
                # 验证文件是否为有效的 pt 文件
                data = torch.load(filepath, map_location="cpu")
                if isinstance(data, dict) and "generator" in data:
                    status = "error"
                else:
                    status = "ready"
                del data
            except Exception as e:
                logger.warning(f"音色文件异常: {filepath}, 错误: {e}")
                status = "error"

            info = {
                "name": name,
                "file": filepath.name,
                "size_bytes": filepath.stat().st_size,
                "status": status,
            }
            voices.append(info)
            self._voice_cache[name] = info

        logger.info(f"扫描音色完成: {len(voices)} 个预设音色")
        return voices

    def get_voice_path(self, name: str) -> Optional[str]:
        """获取预设音色的文件路径"""
        info = self._voice_cache.get(name)
        if info and info["status"] == "ready":
            return str(self._voices_dir / info["file"])

        # 如果缓存中没有，尝试直接查找
        filepath = self._voices_dir / f"{name}.pt"
        if filepath.exists():
            return str(filepath)
        return None

    def extract_features(self, audio_path: str, max_duration: float = 60.0) -> tuple[str, list[int]]:
        """
        从音频文件提取 Mel 频谱特征。

        Args:
            audio_path: 音频文件路径
            max_duration: 最大允许时长（秒），超过返回错误

        Returns:
            (特征文件路径, 特征形状)

        Raises:
            ValueError: 文件时长超过限制或不是有效音频
        """
        from indextts.utils.feature_extractors import MelSpectrogramFeatures

        # 加载音频
        audio, sr = torchaudio.load(audio_path)
        duration = audio.shape[-1] / sr

        if duration > max_duration:
            raise ValueError(f"音频时长 {duration:.1f}s 超过限制 {max_duration}s（建议 3-10 秒）")

        # 转单声道
        audio = torch.mean(audio, dim=0, keepdim=True)
        if audio.shape[0] > 1:
            audio = audio[0].unsqueeze(0)

        # 重采样到 24kHz
        if sr != 24000:
            audio = torchaudio.transforms.Resample(sr, 24000)(audio)

        # 提取 Mel 频谱
        mel = MelSpectrogramFeatures()(audio)

        # 保存为临时文件
        temp_name = f"upload_{int(time.time() * 1000)}.pt"
        temp_path = self._temp_dir / temp_name
        torch.save(mel, temp_path)

        shape = list(mel.shape)
        logger.info(f"音色特征提取完成: {audio_path}, shape={shape}, 保存到: {temp_path}")
        return str(temp_path), shape

    def save_voice(self, audio_path: str, name: str) -> tuple[str, int]:
        """
        从音频文件提取特征并保存为预设音色。

        Args:
            audio_path: 音频文件路径
            name: 音色名称

        Returns:
            (保存路径, 文件大小)

        Raises:
            ValueError: 文件时长超过限制
        """
        feature_path, shape = self.extract_features(audio_path)

        # 将特征文件移动到 voices 目录
        dest_path = self._voices_dir / f"{name}.pt"
        if dest_path.exists():
            dest_path.unlink()

        # 读取临时特征并保存到预设目录
        mel = torch.load(feature_path, map_location="cpu")
        torch.save(mel, dest_path)
        os.remove(feature_path)

        size = dest_path.stat().st_size
        logger.info(f"音色保存完成: {name}, 路径: {dest_path}")

        # 更新缓存
        self._voice_cache[name] = {
            "name": name,
            "file": dest_path.name,
            "size_bytes": size,
            "status": "ready",
        }

        return str(dest_path), size
