"""
AudioService — 音频 IO 服务

提供音频转换、加载和 WeNet BNF 特征提取功能。
v2: 使用 WenetService 替代错误的 MelSpectrogram 实现。

技术方案参考：5.1 WeNet BNF 特征提取 → AC-003
"""
import subprocess
import os
import logging
from typing import Tuple, Optional
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioService:
    def __init__(self, device: str = "cuda", wenet_service=None):
        """初始化 AudioService

        Args:
            device: 推理设备（仅用于向后兼容，实际不使用）
            wenet_service: WenetService 实例，用于 BNF 特征提取
        """
        self.device = device
        self._wenet_service = wenet_service
        self._ffmpeg_path = self._find_ffmpeg()

    def _find_ffmpeg(self) -> str:
        possible_paths = [
            "ffmpeg",
            os.path.join(os.path.dirname(__file__), "..", "..", "py39", "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(os.path.dirname(__file__), "..", "..", "ffmpeg", "bin", "ffmpeg.exe"),
        ]
        for path in possible_paths:
            try:
                subprocess.run([path, "-version"], capture_output=True, check=True)
                return path
            except:
                continue
        return "ffmpeg"

    def convert_audio(
        self,
        input_path: str,
        output_path: str,
        sample_rate: int = 16000,
        channels: int = 1
    ) -> str:
        cmd = [
            self._ffmpeg_path,
            "-y",
            "-i", input_path,
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-acodec", "pcm_s16le",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {result.stderr}")
        logger.info(f"Converted audio: {input_path} -> {output_path}")
        return output_path

    def load_audio(self, audio_path: str, sample_rate: int = 16000) -> Tuple[np.ndarray, int]:
        try:
            import torchaudio
            waveform, sr = torchaudio.load(audio_path)
            if sr != sample_rate:
                resampler = torchaudio.transforms.Resample(sr, sample_rate)
                waveform = resampler(waveform)
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            return waveform.numpy().squeeze(), sample_rate
        except ImportError:
            import librosa
            waveform, sr = librosa.load(audio_path, sr=sample_rate, mono=True)
            return waveform, sr

    def extract_wenet_features(
        self,
        audio_path: str,
        sample_rate: int = 16000,
        feature_dim: int = 256
    ) -> np.ndarray:
        """提取 WeNet BNF 特征

        使用 WenetService 提取真实的 WeNet Conformer BNF 特征 (T, 256)，
        替代之前错误的 MelSpectrogram 实现。

        Args:
            audio_path: 音频文件路径
            sample_rate: 采样率（默认 16000）
            feature_dim: 特征维度（默认 256，用于向后兼容）

        Returns:
            BNF 特征数组，shape = (T, 256)，dtype = float32

        Raises:
            RuntimeError: WenetService 未初始化
        """
        if self._wenet_service is None:
            raise RuntimeError(
                "WenetService not initialized. "
                "Please provide wenet_service to AudioService constructor."
            )

        features = self._wenet_service.extract_features(audio_path)

        logger.info(f"Extracted WeNet BNF features shape: {features.shape}")
        return features

    def get_audio_duration(self, audio_path: str) -> float:
        cmd = [
            self._ffmpeg_path,
            "-i", audio_path,
            "-hide_banner"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stderr
        for line in output.split("\n"):
            if "Duration:" in line:
                time_str = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = time_str.split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
        return 0.0

    def extract_audio_from_video(
        self,
        video_path: str,
        output_audio_path: str,
        sample_rate: int = 16000
    ) -> str:
        cmd = [
            self._ffmpeg_path,
            "-y",
            "-i", video_path,
            "-vn",
            "-ar", str(sample_rate),
            "-ac", "1",
            "-acodec", "pcm_s16le",
            output_audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {result.stderr}")
        logger.info(f"Extracted audio from video: {video_path}")
        return output_audio_path
