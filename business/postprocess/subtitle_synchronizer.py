"""
智能字幕时间轴同步器
使用改进的音频能量检测算法，实现字幕与语音的精确对齐
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


class IntelligentSubtitleSynchronizer:
    """智能字幕时间轴同步器"""

    # 默认参数
    DEFAULT_SAMPLE_RATE = 16000
    DEFAULT_MIN_SILENCE_MS = 150  # 最小静音时长（毫秒）
    DEFAULT_SILENCE_THRESH_DB = -35  # 静音阈值（dB）
    DEFAULT_MIN_SPEECH_MS = 200  # 最小语音时长（毫秒）
    DEFAULT_PADDING_MS = 50  # 字幕前后填充时间（毫秒）
    DEFAULT_MAX_SUBTITLE_DURATION = 5.0  # 单条字幕最大时长（秒）
    DEFAULT_MIN_SUBTITLE_DURATION = 0.5  # 单条字幕最小时长（秒）
    DEFAULT_MAX_CHARS_PER_SUBTITLE = 12  # 单条字幕最大字数（中文）

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        min_silence_ms: int = DEFAULT_MIN_SILENCE_MS,
        silence_thresh_db: int = DEFAULT_SILENCE_THRESH_DB,
        min_speech_ms: int = DEFAULT_MIN_SPEECH_MS,
        padding_ms: int = DEFAULT_PADDING_MS,
        max_subtitle_duration: float = DEFAULT_MAX_SUBTITLE_DURATION,
        min_subtitle_duration: float = DEFAULT_MIN_SUBTITLE_DURATION,
        max_chars_per_subtitle: int = DEFAULT_MAX_CHARS_PER_SUBTITLE,
    ):
        """
        初始化字幕同步器

        Args:
            sample_rate: 音频采样率
            min_silence_ms: 最小静音时长（毫秒），用于分割语音片段
            silence_thresh_db: 静音阈值（dB），低于此值视为静音
            min_speech_ms: 最小语音时长（毫秒），短于此值的片段将被合并
            padding_ms: 字幕前后填充时间（毫秒），让字幕稍微提前出现
            max_subtitle_duration: 单条字幕最大时长（秒）
            min_subtitle_duration: 单条字幕最小时长（秒）
            max_chars_per_subtitle: 单条字幕最大字数（中文）
        """
        self.sample_rate = sample_rate
        self.min_silence_ms = min_silence_ms
        self.silence_thresh_db = silence_thresh_db
        self.min_speech_ms = min_speech_ms
        self.padding_ms = padding_ms
        self.max_subtitle_duration = max_subtitle_duration
        self.min_subtitle_duration = min_subtitle_duration
        self.max_chars_per_subtitle = max_chars_per_subtitle

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
            segment_durations: 每个段落的音频时长（可选，用于辅助对齐）
            segment_offsets: 每个段落的时间偏移（可选）

        Returns:
            是否成功
        """
        try:
            # 1. 从视频中提取音频
            audio_path = self._extract_audio(video_path)
            if not audio_path:
                logger.error("无法从视频提取音频")
                return False

            try:
                # 2. 加载音频数据
                audio_data = self._load_audio(audio_path)
                if audio_data is None:
                    logger.error("无法加载音频数据")
                    return False

                # 3. 检测语音片段
                speech_segments = self._detect_speech_segments(audio_data)
                if not speech_segments:
                    logger.warning("未检测到语音片段，使用备用方法")
                    speech_segments = self._estimate_speech_segments(
                        len(audio_data) / self.sample_rate,
                        segments_text,
                        segment_durations,
                        segment_offsets
                    )

                # 4. 将文本与语音片段对齐
                subtitles = self._align_text_to_speech(
                    segments_text,
                    speech_segments,
                    segment_durations,
                    segment_offsets
                )

                # 5. 写入 SRT 文件
                self._write_srt(subtitles, output_srt_path)

                logger.info(f"字幕同步完成: {output_srt_path}")
                return True

            finally:
                # 清理临时音频文件
                if os.path.exists(audio_path):
                    os.remove(audio_path)

        except Exception as e:
            logger.error(f"字幕同步失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _extract_audio(self, video_path: str) -> Optional[str]:
        """从视频中提取音频"""
        try:
            temp_dir = tempfile.gettempdir()
            audio_path = os.path.join(temp_dir, f"subtitle_sync_{os.getpid()}.wav")

            cmd = [
                "ffmpeg", "-y", "-i", video_path,
                "-vn", "-acodec", "pcm_s16le",
                "-ar", str(self.sample_rate),
                "-ac", "1",
                audio_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"音频提取失败: {result.stderr}")
                return None

            return audio_path

        except Exception as e:
            logger.error(f"音频提取异常: {e}")
            return None

    def _load_audio(self, audio_path: str) -> Optional[np.ndarray]:
        """加载音频数据"""
        try:
            import wave

            with wave.open(audio_path, 'rb') as wf:
                n_frames = wf.getnframes()
                framerate = wf.getframerate()

                # 读取音频数据
                raw_data = wf.readframes(n_frames)

                # 转换为 numpy 数组
                audio_data = np.frombuffer(raw_data, dtype=np.int16)

                # 归一化为 -1.0 到 1.0
                audio_data = audio_data.astype(np.float32) / 32768.0

                return audio_data

        except Exception as e:
            logger.error(f"音频加载失败: {e}")
            return None

    def _detect_speech_segments(
        self,
        audio_data: np.ndarray
    ) -> List[Tuple[float, float]]:
        """
        检测语音片段（改进的能量检测算法）

        Returns:
            语音片段列表 [(start_time, end_time), ...]
        """
        try:
            # 计算音频能量
            frame_size = int(self.sample_rate * 0.01)  # 10ms 帧
            n_frames = len(audio_data) // frame_size

            if n_frames == 0:
                return []

            # 计算每帧的 RMS 能量
            energies = []
            for i in range(n_frames):
                start = i * frame_size
                end = min(start + frame_size, len(audio_data))
                frame = audio_data[start:end]
                rms = np.sqrt(np.mean(frame ** 2))
                energies.append(rms)

            energies = np.array(energies)

            # 动态计算静音阈值
            # 使用能量的百分位数，而不是固定阈值
            energy_percentile = np.percentile(energies[energies > 0], 10)
            silence_threshold = max(energy_percentile * 0.5, 0.01)

            # 检测语音帧
            is_speech = energies > silence_threshold

            # 转换为时间片段
            speech_segments = []
            in_speech = False
            speech_start = 0

            min_speech_frames = self.min_speech_ms / 10  # 10ms per frame
            min_silence_frames = self.min_silence_ms / 10

            silence_count = 0

            for i, speech in enumerate(is_speech):
                if speech and not in_speech:
                    # 语音开始
                    in_speech = True
                    speech_start = i * 0.01  # 转换为秒
                    silence_count = 0
                elif not speech and in_speech:
                    # 可能是语音结束
                    silence_count += 1
                    if silence_count >= min_silence_frames:
                        # 确认语音结束
                        speech_end = (i - silence_count + 1) * 0.01
                        if (speech_end - speech_start) * 1000 >= self.min_speech_ms:
                            speech_segments.append((speech_start, speech_end))
                        in_speech = False
                elif speech and in_speech:
                    silence_count = 0

            # 处理最后一个语音片段
            if in_speech:
                speech_end = len(is_speech) * 0.01
                if (speech_end - speech_start) * 1000 >= self.min_speech_ms:
                    speech_segments.append((speech_start, speech_end))

            logger.info(f"检测到 {len(speech_segments)} 个语音片段")
            return speech_segments

        except Exception as e:
            logger.error(f"语音检测失败: {e}")
            return []

    def _estimate_speech_segments(
        self,
        total_duration: float,
        segments_text: List[str],
        segment_durations: Optional[List[float]],
        segment_offsets: Optional[List[float]],
    ) -> List[Tuple[float, float]]:
        """
        估算语音片段（备用方法）

        当无法检测到语音时，使用段落时长估算
        """
        speech_segments = []

        if segment_durations and segment_offsets:
            # 使用提供的段落时长和偏移
            for duration, offset in zip(segment_durations, segment_offsets):
                speech_segments.append((offset, offset + duration))
        elif segment_durations:
            # 使用段落时长，从 0 开始累加
            current_offset = 0.0
            for duration in segment_durations:
                speech_segments.append((current_offset, current_offset + duration))
                current_offset += duration
        else:
            # 根据文本长度估算
            total_chars = sum(len(text) for text in segments_text)
            if total_chars == 0:
                return [(0.0, total_duration)]

            current_offset = 0.0
            for text in segments_text:
                duration = total_duration * (len(text) / total_chars)
                speech_segments.append((current_offset, current_offset + duration))
                current_offset += duration

        return speech_segments

    def _align_text_to_speech(
        self,
        segments_text: List[str],
        speech_segments: List[Tuple[float, float]],
        segment_durations: Optional[List[float]] = None,
        segment_offsets: Optional[List[float]] = None,
    ) -> List[SubtitleEntry]:
        """
        将文本与语音片段对齐

        核心算法：
        1. 将所有段落文本拆分为句子
        2. 将句子与语音片段进行最优匹配
        3. 应用时间调整确保字幕不会比声音快
        """
        subtitles = []
        subtitle_index = 1

        # 将所有段落文本拆分为句子
        all_sentences = []
        sentence_to_segment = []  # 记录每个句子属于哪个段落

        for seg_idx, text in enumerate(segments_text):
            sentences = self._split_text_to_sentences(text)
            for sentence in sentences:
                all_sentences.append(sentence)
                sentence_to_segment.append(seg_idx)

        if not all_sentences:
            return subtitles

        # 如果语音片段数量与句子数量匹配，直接配对
        if len(speech_segments) == len(all_sentences):
            for i, (sentence, (start, end)) in enumerate(zip(all_sentences, speech_segments)):
                # 应用填充：让字幕稍微提前出现
                padded_start = max(0, start - self.padding_ms / 1000)
                padded_end = end + self.padding_ms / 1000

                # 确保字幕时长在合理范围内
                duration = padded_end - padded_start
                if duration < self.min_subtitle_duration:
                    padded_end = padded_start + self.min_subtitle_duration
                elif duration > self.max_subtitle_duration:
                    # 长字幕需要拆分
                    split_subtitles = self._split_long_subtitle(
                        sentence,
                        padded_start,
                        padded_end,
                        subtitle_index
                    )
                    subtitles.extend(split_subtitles)
                    subtitle_index += len(split_subtitles)
                    continue

                subtitles.append(SubtitleEntry(
                    index=subtitle_index,
                    start_time=padded_start,
                    end_time=padded_end,
                    text=sentence
                ))
                subtitle_index += 1
        else:
            # 数量不匹配时，使用智能分配算法
            subtitles = self._intelligent_alignment(
                all_sentences,
                speech_segments,
                subtitle_index
            )

        return subtitles

    def _intelligent_alignment(
        self,
        sentences: List[str],
        speech_segments: List[Tuple[float, float]],
        start_index: int
    ) -> List[SubtitleEntry]:
        """
        智能对齐算法

        当句子数量与语音片段数量不匹配时使用
        """
        subtitles = []
        subtitle_index = start_index

        if not speech_segments:
            return subtitles

        # 计算总语音时长
        total_speech_duration = sum(end - start for start, end in speech_segments)

        # 计算总字符数
        total_chars = sum(len(s) for s in sentences)

        if total_chars == 0:
            return subtitles

        # 按字符比例分配时间
        current_time = speech_segments[0][0] if speech_segments else 0.0
        speech_idx = 0

        for sentence in sentences:
            # 计算该句子应占用的时长比例
            char_ratio = len(sentence) / total_chars
            target_duration = total_speech_duration * char_ratio

            # 找到对应的语音片段
            start_time = current_time
            end_time = start_time + target_duration

            # 确保不超过语音片段范围
            while speech_idx < len(speech_segments) and speech_segments[speech_idx][1] < end_time:
                speech_idx += 1

            if speech_idx < len(speech_segments):
                # 使用实际语音片段的结束时间，确保字幕不会超过语音
                actual_end = min(end_time, speech_segments[speech_idx][1])

                # 应用填充
                padded_start = max(0, start_time - self.padding_ms / 1000)
                padded_end = actual_end + self.padding_ms / 1000

                # 确保时长合理
                duration = padded_end - padded_start
                if duration < self.min_subtitle_duration:
                    padded_end = padded_start + self.min_subtitle_duration

                subtitles.append(SubtitleEntry(
                    index=subtitle_index,
                    start_time=padded_start,
                    end_time=padded_end,
                    text=sentence
                ))
                subtitle_index += 1

            current_time = end_time

        return subtitles

    def _split_text_to_sentences(self, text: str) -> List[str]:
        """
        将文本按标点符号拆分

        改进策略：
        1. 按所有标点符号拆分（句末标点 + 逗号类标点）
        2. 单条字幕限制为 max_chars_per_subtitle 字（默认12字）
        3. 避免单独的标点符号成为一条字幕
        """
        import re

        if not text:
            return []

        # 按所有标点符号拆分（中英文标点）
        # 包括：句末标点（。！？.!?）和逗号类标点（，,；;：:）
        sentences = re.split(r'([。！？.!?，,；;：:])', text)

        # 合并标点符号和句子
        result = []
        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                sentence = sentences[i].strip() + sentences[i + 1].strip()
            else:
                sentence = sentences[i].strip()

            if sentence:
                # 跳过只有标点符号的片段
                if all(c in '，,；;：:。！？.!?' for c in sentence.strip()):
                    continue

                # 如果句子超过字数限制，进一步拆分
                if len(sentence) > self.max_chars_per_subtitle:
                    sub_sentences = self._split_by_char_limit(sentence, self.max_chars_per_subtitle)
                    result.extend(sub_sentences)
                else:
                    result.append(sentence)

        # 如果没有拆分出句子，返回原文本
        if not result and text.strip():
            # 如果原文也超长，需要拆分
            if len(text.strip()) > self.max_chars_per_subtitle:
                result = self._split_by_char_limit(text.strip(), self.max_chars_per_subtitle)
            else:
                result = [text.strip()]

        return result

    def _split_by_char_limit(self, text: str, max_chars: int) -> List[str]:
        """
        按字数限制分割文本

        策略：
        1. 严格按字数限制分割，确保每段不超过 max_chars
        2. 尽量在标点符号后分割，保留标点
        3. 避免单独的标点符号成为一条字幕
        """
        if len(text) <= max_chars:
            return [text]

        chunks = []
        remaining = text

        while len(remaining) > max_chars:
            # 默认在 max_chars 位置分割
            split_pos = max_chars

            # 尝试在 max_chars 位置附近找一个标点作为分割点
            for i in range(min(max_chars, len(remaining)) - 1, max(0, max_chars - 5), -1):
                if remaining[i] in '，,；;：:。！？.!?':
                    split_pos = i + 1
                    break

            # 确保分割位置不超过 max_chars
            split_pos = min(split_pos, max_chars)

            chunk = remaining[:split_pos]
            # 只有当 chunk 不只是标点符号时才添加
            if chunk.strip() and not all(c in '，,；;：:。！？.!?' for c in chunk.strip()):
                chunks.append(chunk)

            remaining = remaining[split_pos:]

        if remaining:
            if remaining.strip() and not all(c in '，,；;：:。！？.!?' for c in remaining.strip()):
                chunks.append(remaining)

        return chunks if chunks else [text]

    def _split_long_subtitle(
        self,
        text: str,
        start_time: float,
        end_time: float,
        start_index: int
    ) -> List[SubtitleEntry]:
        """
        拆分过长的字幕

        改进策略：
        1. 按所有标点符号拆分
        2. 确保每段不超过 max_chars_per_subtitle 字
        """
        subtitles = []

        # 按所有标点符号拆分
        import re
        parts = re.split(r'([，,、；;：:。！？.!?])', text)

        # 合并标点
        segments = []
        for i in range(0, len(parts), 2):
            if i + 1 < len(parts):
                segments.append(parts[i].strip() + parts[i + 1].strip())
            else:
                if parts[i].strip():
                    segments.append(parts[i].strip())

        if not segments:
            segments = [text]

        # 如果拆分后仍有超长片段，进一步按字数分割
        final_segments = []
        for seg in segments:
            if len(seg) > self.max_chars_per_subtitle:
                final_segments.extend(self._split_by_char_limit(seg, self.max_chars_per_subtitle))
            else:
                final_segments.append(seg)

        segments = final_segments

        # 按比例分配时间
        total_chars = sum(len(s) for s in segments)
        if total_chars == 0:
            return subtitles

        current_time = start_time
        duration = end_time - start_time

        for i, segment in enumerate(segments):
            seg_duration = duration * (len(segment) / total_chars)
            seg_end = current_time + seg_duration

            subtitles.append(SubtitleEntry(
                index=start_index + i,
                start_time=current_time - self.padding_ms / 1000,
                end_time=seg_end + self.padding_ms / 1000,
                text=segment
            ))
            current_time = seg_end

        return subtitles

    def _write_srt(self, subtitles: List[SubtitleEntry], output_path: str):
        """写入 SRT 文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for sub in subtitles:
                f.write(f"{sub.index}\n")
                f.write(f"{self._format_srt_time(sub.start_time)} --> {self._format_srt_time(sub.end_time)}\n")
                f.write(f"{sub.text}\n\n")

    def _format_srt_time(self, seconds: float) -> str:
        """格式化 SRT 时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def create_subtitle_synchronizer(**kwargs) -> IntelligentSubtitleSynchronizer:
    """创建字幕同步器的便捷函数"""
    return IntelligentSubtitleSynchronizer(**kwargs)
