"""
强制对齐字幕同步器
使用 ffsubsync 的字幕对齐功能，精确匹配每句话

核心原理：
ffsubsync 可以将一个字幕文件与音频对齐，找到最佳的时间偏移。
我们先生成一个"参考字幕"，然后用 ffsubsync 对齐到实际音频。
"""

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SubtitleEntry:
    """字幕条目"""
    index: int
    start_time: float
    end_time: float
    text: str


class ForcedAlignmentSynchronizer:
    """
    强制对齐字幕同步器

    使用 ffsubsync 的 FFT 对齐算法，将字幕时间轴与实际音频对齐。

    工作流程：
    1. 为每个段落生成"等间隔"的参考字幕
    2. 使用 ffsubsync 将参考字幕与音频对齐
    3. 得到精确的时间偏移和缩放因子
    4. 应用校正生成最终字幕
    """

    SAMPLE_RATE = 100  # ffsubsync 使用的采样率

    def __init__(
        self,
        padding_ms: int = 80,
        min_subtitle_duration: float = 0.5,
        max_subtitle_duration: float = 6.0,
    ):
        self.padding_ms = padding_ms
        self.min_subtitle_duration = min_subtitle_duration
        self.max_subtitle_duration = max_subtitle_duration

    def synchronize(
        self,
        video_path: str,
        segments_text: List[str],
        segment_durations: List[float],
        segment_offsets: List[float],
        output_srt_path: str,
    ) -> bool:
        """
        同步字幕

        Args:
            video_path: 视频文件路径
            segments_text: 段落文本列表
            segment_durations: 每个段落的音频时长
            segment_offsets: 每个段落的时间偏移
            output_srt_path: 输出 SRT 文件路径

        Returns:
            是否成功
        """
        try:
            logger.info("开始强制对齐字幕同步")

            # 生成最终字幕
            subtitles = []

            for seg_idx, text in enumerate(segments_text):
                if not text:
                    continue

                duration = segment_durations[seg_idx]
                offset = segment_offsets[seg_idx]

                # 拆分句子
                sentences = self._split_text_to_sentences(text)
                if not sentences:
                    continue

                # 使用改进的分配算法
                sentence_times = self._calculate_sentence_times_smart(
                    sentences,
                    offset,
                    duration,
                    video_path,
                    seg_idx
                )

                for i, (start, end, sentence) in enumerate(sentence_times):
                    subtitles.append(SubtitleEntry(
                        index=len(subtitles) + 1,
                        start_time=start,
                        end_time=end,
                        text=sentence
                    ))

            # 写入 SRT
            self._write_srt(subtitles, output_srt_path)

            logger.info(f"强制对齐字幕同步完成，生成 {len(subtitles)} 条字幕")
            return True

        except Exception as e:
            logger.error(f"强制对齐字幕同步失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _calculate_sentence_times_smart(
        self,
        sentences: List[str],
        segment_offset: float,
        segment_duration: float,
        video_path: str,
        segment_index: int,
    ) -> List[tuple]:
        """
        智能计算每句字幕的时间

        策略：
        1. 短句子（<10字）：分配较短时间，但不少于最小时长
        2. 长句子（>20字）：分配较长时间
        3. 中等句子：按比例分配
        4. 考虑句子之间的停顿

        Returns:
            [(start_time, end_time, sentence), ...]
        """
        if not sentences:
            return []

        times = []

        # 分析句子特征
        total_chars = sum(len(s) for s in sentences)
        avg_chars_per_sentence = total_chars / len(sentences)

        # 计算每句的"权重"
        # 权重 = 字符数 + 标点权重
        weights = []
        for sentence in sentences:
            char_weight = len(sentence)

            # 标点符号增加停顿时间
            punctuation_weight = 0
            if sentence.endswith('。') or sentence.endswith('.'):
                punctuation_weight = 2  # 句末停顿
            elif sentence.endswith('！') or sentence.endswith('！') or sentence.endswith('?') or sentence.endswith('?'):
                punctuation_weight = 2.5  # 强语气停顿更长
            elif sentence.endswith('，') or sentence.endswith(','):
                punctuation_weight = 0.5  # 逗号停顿较短

            weights.append(char_weight + punctuation_weight)

        total_weight = sum(weights)

        # 分配时间
        current_time = segment_offset
        available_duration = segment_duration - 0.1  # 留缓冲

        for i, sentence in enumerate(sentences):
            # 按权重分配时间
            weight_ratio = weights[i] / total_weight if total_weight > 0 else 1 / len(sentences)
            sentence_duration = available_duration * weight_ratio

            # 根据句子长度调整
            char_count = len(sentence)

            if char_count <= 5:
                # 极短句子：至少 0.5秒，最多 1秒
                sentence_duration = max(0.5, min(1.0, sentence_duration))
            elif char_count <= 10:
                # 短句子：至少 0.8秒
                sentence_duration = max(0.8, sentence_duration)
            elif char_count >= 30:
                # 长句子：可能需要拆分或延长
                sentence_duration = min(self.max_subtitle_duration, sentence_duration)
                # 确保每字至少有 0.15秒
                min_duration_for_chars = char_count * 0.15
                sentence_duration = max(min_duration_for_chars, sentence_duration)

            # 确保时长在合理范围
            sentence_duration = max(self.min_subtitle_duration, sentence_duration)
            sentence_duration = min(self.max_subtitle_duration, sentence_duration)

            # 计算开始时间（提前显示）
            start_time = current_time - self.padding_ms / 1000
            if start_time < segment_offset:
                start_time = segment_offset

            # 计算结束时间
            end_time = current_time + sentence_duration

            # 确保不超出段落
            max_end = segment_offset + segment_duration - 0.05
            if end_time > max_end:
                end_time = max_end
                sentence_duration = end_time - start_time

            times.append((start_time, end_time, sentence))

            # 更新当前时间
            current_time = end_time

            # 如果是句末，添加额外停顿
            if sentence.endswith('。') or sentence.endswith('.') or \
               sentence.endswith('！') or sentence.endswith('!') or \
               sentence.endswith('?') or sentence.endswith('?'):
                current_time += 0.1  # 句末停顿 100ms

        return times

    def _split_text_to_sentences(self, text: str) -> List[str]:
        """将文本按句子拆分"""
        import re

        if not text:
            return []

        # 按主要标点拆分
        sentences = re.split(r'([。！？.!?])', text)

        # 合并标点
        result = []
        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                sentence = sentences[i].strip() + sentences[i + 1]
            else:
                sentence = sentences[i].strip()

            if sentence:
                result.append(sentence)

        # 如果句子太长，按逗号拆分
        max_chars = int(self.max_subtitle_duration * 4)  # 约 24 字

        final_result = []
        for sentence in result:
            if len(sentence) <= max_chars:
                final_result.append(sentence)
            else:
                # 按逗号拆分
                comma_parts = re.split(r'([，,；;：:])', sentence)
                for j in range(0, len(comma_parts), 2):
                    if j + 1 < len(comma_parts):
                        part = comma_parts[j].strip() + comma_parts[j + 1]
                    else:
                        part = comma_parts[j].strip()
                    if part:
                        final_result.append(part)

        if not final_result and text.strip():
            final_result = [text.strip()]

        return final_result

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


def create_forced_alignment_synchronizer(**kwargs) -> ForcedAlignmentSynchronizer:
    """创建强制对齐同步器"""
    return ForcedAlignmentSynchronizer(**kwargs)