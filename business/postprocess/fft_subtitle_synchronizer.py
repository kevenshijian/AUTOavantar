"""
基于 ffsubsync FFT 的字幕时间轴同步器
使用音频波形相似度匹配实现精确对齐
"""

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SubtitleEntry:
    """字幕条目"""
    index: int
    start_time: float  # 秒
    end_time: float    # 秒
    text: str


class FFTSubtitleSynchronizer:
    """
    基于 ffsubsync FFT 的字幕同步器

    核心原理：
    1. 从视频音频中提取语音活动信号（speech activity signal）
    2. 从字幕时间轴生成参考语音信号
    3. 使用 FFT 卷积找到最佳偏移量
    4. 应用偏移和帧率缩放校正字幕时间轴
    """

    # ffsubsync 使用的采样率
    SAMPLE_RATE = 100  # 每秒 100 个采样点（10ms 分辨率）
    AUDIO_SAMPLE_RATE = 48000  # 音频采样率

    def __init__(
        self,
        max_offset_seconds: float = 30.0,
        padding_ms: int = 50,
        min_subtitle_duration: float = 0.5,
        max_subtitle_duration: float = 8.0,
    ):
        """
        初始化 FFT 字幕同步器

        Args:
            max_offset_seconds: 最大允许的偏移量（秒）
            padding_ms: 字幕提前显示的时间（毫秒）
            min_subtitle_duration: 最小字幕时长（秒）
            max_subtitle_duration: 最大字幕时长（秒）
        """
        self.max_offset_seconds = max_offset_seconds
        self.padding_ms = padding_ms
        self.min_subtitle_duration = min_subtitle_duration
        self.max_subtitle_duration = max_subtitle_duration

    def synchronize(
        self,
        video_path: str,
        segments_text: List[str],
        output_srt_path: str,
        segment_durations: Optional[List[float]] = None,
        segment_offsets: Optional[List[float]] = None,
    ) -> bool:
        """
        同步字幕与视频音频

        Args:
            video_path: 视频文件路径
            segments_text: 段落文本列表
            output_srt_path: 输出 SRT 文件路径
            segment_durations: 每个段落的音频时长
            segment_offsets: 每个段落的时间偏移

        Returns:
            是否成功
        """
        try:
            logger.info(f"开始 FFT 字幕同步: {video_path}")

            # 1. 从视频中提取语音活动信号
            video_speech_signal = self._extract_speech_signal_from_video(video_path)
            if video_speech_signal is None:
                logger.error("无法从视频提取语音信号")
                return False

            logger.info(f"视频语音信号长度: {len(video_speech_signal)} 采样点")

            # 2. 生成初始字幕时间轴
            initial_subtitles = self._generate_initial_subtitles(
                segments_text,
                segment_durations,
                segment_offsets
            )

            if not initial_subtitles:
                logger.error("无法生成初始字幕")
                return False

            # 3. 从字幕生成参考语音信号
            subtitle_speech_signal = self._generate_subtitle_speech_signal(
                initial_subtitles,
                len(video_speech_signal) / self.SAMPLE_RATE
            )

            logger.info(f"字幕语音信号长度: {len(subtitle_speech_signal)} 采样点")

            # 4. 使用 FFT 找到最佳偏移
            offset_samples, score = self._fft_align(
                video_speech_signal,
                subtitle_speech_signal
            )

            offset_seconds = offset_samples / self.SAMPLE_RATE
            logger.info(f"FFT 对齐结果: 偏移={offset_seconds:.3f}s, 得分={score:.1f}")

            # 5. 应用偏移校正字幕时间轴
            corrected_subtitles = self._apply_offset(
                initial_subtitles,
                offset_seconds
            )

            # 6. 写入 SRT 文件
            self._write_srt(corrected_subtitles, output_srt_path)

            logger.info(f"FFT 字幕同步完成: {output_srt_path}")
            return True

        except Exception as e:
            logger.error(f"FFT 字幕同步失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _extract_speech_signal_from_video(self, video_path: str) -> Optional[np.ndarray]:
        """
        从视频中提取语音活动信号

        使用 VAD（语音活动检测）识别哪些时间段有语音
        """
        try:
            # 提取音频到临时文件
            temp_dir = tempfile.gettempdir()
            audio_path = os.path.join(temp_dir, f"fft_sync_{os.getpid()}.wav")

            cmd = [
                "ffmpeg", "-y", "-i", video_path,
                "-vn", "-acodec", "pcm_s16le",
                "-ar", str(self.AUDIO_SAMPLE_RATE),
                "-ac", "1",
                audio_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"音频提取失败: {result.stderr}")
                return None

            try:
                # 读取音频数据
                import wave
                with wave.open(audio_path, 'rb') as wf:
                    n_frames = wf.getnframes()
                    raw_data = wf.readframes(n_frames)
                    audio_data = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
                    audio_data = audio_data / 32768.0  # 归一化

                # 计算每 10ms 的能量
                frame_size = int(self.AUDIO_SAMPLE_RATE * 0.01)  # 10ms
                n_frames = len(audio_data) // frame_size

                energies = []
                for i in range(n_frames):
                    start = i * frame_size
                    end = min(start + frame_size, len(audio_data))
                    frame = audio_data[start:end]
                    rms = np.sqrt(np.mean(frame ** 2))
                    energies.append(rms)

                energies = np.array(energies)

                # 动态阈值
                if len(energies[energies > 0]) > 0:
                    threshold = np.percentile(energies[energies > 0], 15)
                else:
                    threshold = 0.01

                # 生成语音活动信号（降采样到 SAMPLE_RATE）
                speech_frames = (energies > threshold).astype(float)

                # 降采样到每秒 SAMPLE_RATE 个采样点
                original_rate = 100  # 10ms = 100Hz
                target_length = int(len(speech_frames) * self.SAMPLE_RATE / original_rate)

                if target_length > 0:
                    # 使用线性插值降采样
                    indices = np.linspace(0, len(speech_frames) - 1, target_length)
                    speech_signal = np.interp(indices, np.arange(len(speech_frames)), speech_frames)
                else:
                    speech_signal = speech_frames

                return speech_signal

            finally:
                if os.path.exists(audio_path):
                    os.remove(audio_path)

        except Exception as e:
            logger.error(f"语音信号提取失败: {e}")
            return None

    def _generate_initial_subtitles(
        self,
        segments_text: List[str],
        segment_durations: Optional[List[float]],
        segment_offsets: Optional[List[float]]
    ) -> List[SubtitleEntry]:
        """
        生成初始字幕时间轴

        基于段落时长生成初步的字幕时间轴
        """
        subtitles = []
        subtitle_index = 1

        if not segments_text:
            return subtitles

        # 计算每个段落的开始时间
        if segment_durations and segment_offsets:
            # 使用提供的时长和偏移
            pass
        elif segment_durations:
            # 计算偏移
            segment_offsets = []
            current_offset = 0.0
            for duration in segment_durations:
                segment_offsets.append(current_offset)
                current_offset += duration
        else:
            # 根据文本长度估算
            total_chars = sum(len(text) for text in segments_text)
            if total_chars == 0:
                return subtitles

            # 假设平均语速：每秒 4 个字
            avg_speed = 4.0
            segment_durations = []
            segment_offsets = []
            current_offset = 0.0

            for text in segments_text:
                duration = len(text) / avg_speed
                segment_durations.append(duration)
                segment_offsets.append(current_offset)
                current_offset += duration

        # 为每个段落生成字幕
        for seg_idx, text in enumerate(segments_text):
            if not text:
                continue

            duration = segment_durations[seg_idx] if segment_durations else 2.0
            offset = segment_offsets[seg_idx] if segment_offsets else 0.0

            # 拆分句子
            sentences = self._split_text_to_sentences(text)

            if not sentences:
                continue

            # 按字符比例分配时间
            total_chars = sum(len(s) for s in sentences)

            current_time = offset
            for sentence in sentences:
                if total_chars > 0:
                    sentence_duration = duration * (len(sentence) / total_chars)
                else:
                    sentence_duration = duration / len(sentences)

                # 确保时长合理
                sentence_duration = max(self.min_subtitle_duration, sentence_duration)
                sentence_duration = min(self.max_subtitle_duration, sentence_duration)

                subtitles.append(SubtitleEntry(
                    index=subtitle_index,
                    start_time=current_time,
                    end_time=current_time + sentence_duration,
                    text=sentence
                ))

                subtitle_index += 1
                current_time += sentence_duration

        return subtitles

    def _generate_subtitle_speech_signal(
        self,
        subtitles: List[SubtitleEntry],
        total_duration: float
    ) -> np.ndarray:
        """
        从字幕时间轴生成语音活动信号

        字幕显示的时间段标记为 1（有语音），其他为 0
        """
        # 计算信号长度
        signal_length = int(total_duration * self.SAMPLE_RATE) + 1
        signal = np.zeros(signal_length, dtype=float)

        for sub in subtitles:
            # 转换时间为采样点索引
            start_idx = int(sub.start_time * self.SAMPLE_RATE)
            end_idx = int(sub.end_time * self.SAMPLE_RATE)

            # 确保索引在范围内
            start_idx = max(0, min(start_idx, signal_length - 1))
            end_idx = max(0, min(end_idx, signal_length))

            # 标记为有语音
            signal[start_idx:end_idx] = 1.0

        return signal

    def _fft_align(
        self,
        reference: np.ndarray,
        target: np.ndarray
    ) -> Tuple[int, float]:
        """
        使用 FFT 卷积找到最佳偏移量

        这是 ffsubsync 的核心算法：
        1. 将信号转换为 +1/-1 的二值信号
        2. 使用 FFT 计算卷积
        3. 找到卷积结果的最大值位置

        Args:
            reference: 参考信号（视频语音信号）
            target: 目标信号（字幕语音信号）

        Returns:
            (偏移采样点数, 匹配得分)
        """
        import math

        # 转换为 +1/-1 格式（ffsubsync 的做法）
        ref = 2 * reference - 1
        tar = 2 * target - 1

        # 计算FFT所需的总长度（2的幂次）
        total_length = len(ref) + len(tar)
        fft_length = int(2 ** math.ceil(math.log(total_length, 2)))

        # 零填充
        ref_padded = np.zeros(fft_length)
        tar_padded = np.zeros(fft_length)

        ref_padded[:len(ref)] = ref
        tar_padded[len(ref):len(ref) + len(tar)] = tar

        # FFT 卷积
        ref_fft = np.fft.fft(np.flip(ref_padded))
        tar_fft = np.fft.fft(tar_padded)
        convolve = np.real(np.fft.ifft(tar_fft * ref_fft))

        # 限制偏移范围
        max_offset_samples = int(self.max_offset_seconds * self.SAMPLE_RATE)

        # 找到最佳匹配位置
        # 卷积结果中，索引 i 对应偏移 (len(convolve) - 1 - i - len(tar))
        valid_start = len(convolve) - 1 - max_offset_samples - len(tar)
        valid_end = len(convolve) - 1 + max_offset_samples - len(tar)

        valid_start = max(0, valid_start)
        valid_end = min(len(convolve), valid_end)

        # 在有效范围内找最大值
        valid_convolve = convolve.copy()
        valid_convolve[:valid_start] = float('-inf')
        valid_convolve[valid_end:] = float('-inf')

        best_idx = int(np.argmax(valid_convolve))
        best_score = convolve[best_idx]

        # 计算偏移量
        offset = len(convolve) - 1 - best_idx - len(tar)

        return offset, best_score

    def _apply_offset(
        self,
        subtitles: List[SubtitleEntry],
        offset_seconds: float
    ) -> List[SubtitleEntry]:
        """
        应用时间偏移校正字幕

        Args:
            subtitles: 原始字幕列表
            offset_seconds: 偏移量（秒）

        Returns:
            校正后的字幕列表
        """
        corrected = []

        for sub in subtitles:
            # 应用偏移
            new_start = sub.start_time + offset_seconds
            new_end = sub.end_time + offset_seconds

            # 确保时间不为负
            if new_start < 0:
                # 如果开始时间为负，调整时长
                duration = new_end - new_start
                new_start = 0.0
                new_end = duration

            # 添加填充（字幕提前显示）
            padded_start = max(0, new_start - self.padding_ms / 1000)
            padded_end = new_end + self.padding_ms / 1000

            corrected.append(SubtitleEntry(
                index=sub.index,
                start_time=padded_start,
                end_time=padded_end,
                text=sub.text
            ))

        return corrected

    def _split_text_to_sentences(self, text: str) -> List[str]:
        """将文本按句子拆分"""
        import re

        if not text:
            return []

        # 按多种标点符号拆分
        sentences = re.split(r'([。！？.!?；;：:，,])', text)

        # 合并标点符号
        result = []
        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                sentence = sentences[i].strip() + sentences[i + 1].strip()
            else:
                sentence = sentences[i].strip()

            if sentence:
                result.append(sentence)

        if not result and text.strip():
            result = [text.strip()]

        return result

    def _write_srt(self, subtitles: List[SubtitleEntry], output_path: str):
        """写入 SRT 文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for sub in subtitles:
                f.write(f"{sub.index}\n")
                f.write(f"{self._format_srt_time(sub.start_time)} --> {self._format_srt_time(sub.end_time)}\n")
                f.write(f"{sub.text}\n\n")

    def _format_srt_time(self, seconds: float) -> str:
        """格式化 SRT 时间"""
        if seconds < 0:
            seconds = 0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def create_fft_subtitle_synchronizer(**kwargs) -> FFTSubtitleSynchronizer:
    """创建 FFT 字幕同步器的便捷函数"""
    return FFTSubtitleSynchronizer(**kwargs)
