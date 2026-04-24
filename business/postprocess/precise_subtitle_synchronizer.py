"""
精确字幕时间轴同步器
基于 TTS 生成的实际音频时长，精确分配字幕时间
"""

import logging
import os
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SubtitleEntry:
    """字幕条目"""
    index: int
    start_time: float  # 秒
    end_time: float    # 秒
    text: str


class PreciseSubtitleSynchronizer:
    """
    精确字幕时间轴同步器

    核心原理：
    1. TTS 已经为每个段落生成了精确的音频时长
    2. 直接使用这些时长信息分配字幕时间
    3. 不需要 FFT 对齐或能量检测

    这是最可靠的方法，因为音频时长是已知的精确值。
    """

    def __init__(
        self,
        padding_ms: int = 80,  # 字幕提前显示时间
        min_subtitle_duration: float = 0.5,
        max_subtitle_duration: float = 6.0,
        overlap_ms: int = 50,  # 字幕之间的重叠时间（避免闪烁）
    ):
        """
        初始化精确字幕同步器

        Args:
            padding_ms: 字幕提前显示时间（毫秒）
            min_subtitle_duration: 最小字幕时长（秒）
            max_subtitle_duration: 最大字幕时长（秒）
            overlap_ms: 字幕之间的重叠时间（毫秒）
        """
        self.padding_ms = padding_ms
        self.min_subtitle_duration = min_subtitle_duration
        self.max_subtitle_duration = max_subtitle_duration
        self.overlap_ms = overlap_ms

    def synchronize(
        self,
        segments_text: List[str],
        segment_durations: List[float],
        segment_offsets: List[float],
        output_srt_path: str,
    ) -> bool:
        """
        同步字幕

        Args:
            segments_text: 段落文本列表
            segment_durations: 每个段落的音频时长（来自 TTS）
            segment_offsets: 每个段落的时间偏移
            output_srt_path: 输出 SRT 文件路径

        Returns:
            是否成功
        """
        try:
            logger.info("开始精确字幕同步")

            if not segments_text:
                logger.warning("没有文本内容")
                return False

            if not segment_durations or not segment_offsets:
                logger.error("缺少段落时长或偏移信息")
                return False

            subtitles = []
            subtitle_index = 1

            for seg_idx, text in enumerate(segments_text):
                if not text:
                    continue

                duration = segment_durations[seg_idx]
                offset = segment_offsets[seg_idx]

                if duration <= 0:
                    logger.warning(f"段落 {seg_idx} 时长无效: {duration}")
                    continue

                # 拆分句子
                sentences = self._split_text_to_sentences(text)
                if not sentences:
                    continue

                # 计算每句字幕的时间
                sentence_times = self._calculate_sentence_times(
                    sentences,
                    offset,
                    duration
                )

                # 生成字幕条目
                for start_time, end_time, sentence in sentence_times:
                    subtitles.append(SubtitleEntry(
                        index=subtitle_index,
                        start_time=start_time,
                        end_time=end_time,
                        text=sentence
                    ))
                    subtitle_index += 1

            # 写入 SRT 文件
            self._write_srt(subtitles, output_srt_path)

            logger.info(f"精确字幕同步完成，生成 {len(subtitles)} 条字幕")
            return True

        except Exception as e:
            logger.error(f"精确字幕同步失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _calculate_sentence_times(
        self,
        sentences: List[str],
        segment_offset: float,
        segment_duration: float
    ) -> List[tuple]:
        """
        计算每句字幕的开始和结束时间

        策略：
        1. 按字符比例分配时间
        2. 字幕提前显示（padding）
        3. 相邻字幕有轻微重叠（避免闪烁）
        4. 确保字幕不超出段落时长

        Returns:
            [(start_time, end_time, sentence), ...]
        """
        if not sentences:
            return []

        total_chars = sum(len(s) for s in sentences)
        if total_chars == 0:
            return []

        times = []
        current_time = segment_offset

        # 预留一些缓冲时间（段落末尾）
        available_duration = segment_duration - 0.1  # 留 100ms 缓冲

        for i, sentence in enumerate(sentences):
            # 按字符比例计算时长
            char_ratio = len(sentence) / total_chars
            sentence_duration = available_duration * char_ratio

            # 确保时长在合理范围内
            sentence_duration = max(self.min_subtitle_duration, sentence_duration)
            sentence_duration = min(self.max_subtitle_duration, sentence_duration)

            # 计算开始时间（提前显示）
            start_time = current_time - self.padding_ms / 1000
            if start_time < segment_offset:
                start_time = segment_offset

            # 计算结束时间
            end_time = current_time + sentence_duration

            # 确保不超出段落范围
            max_end_time = segment_offset + segment_duration - 0.05
            if end_time > max_end_time:
                end_time = max_end_time

            # 确保时长足够
            if end_time - start_time < self.min_subtitle_duration:
                end_time = start_time + self.min_subtitle_duration
                if end_time > max_end_time:
                    end_time = max_end_time
                    start_time = end_time - self.min_subtitle_duration

            times.append((start_time, end_time, sentence))

            # 更新当前时间（考虑重叠）
            current_time = end_time - self.overlap_ms / 1000

        return times

    def _split_text_to_sentences(self, text: str) -> List[str]:
        """
        将文本按句子拆分

        优先按句号、问号、感叹号拆分
        如果句子太长，再按逗号拆分
        """
        import re

        if not text:
            return []

        # 先按主要句末标点拆分
        major_splits = re.split(r'([。！？.!?])', text)

        # 合并标点
        major_sentences = []
        for i in range(0, len(major_splits), 2):
            if i + 1 < len(major_splits):
                major_sentences.append(major_splits[i].strip() + major_splits[i + 1])
            else:
                if major_splits[i].strip():
                    major_sentences.append(major_splits[i].strip())

        # 如果句子太长（超过 max_subtitle_duration 对应的字符数），再拆分
        # 假设平均语速每秒 4 字，max_subtitle_duration = 6s，最多 24 字
        max_chars_per_subtitle = int(self.max_subtitle_duration * 4)

        final_sentences = []
        for sentence in major_sentences:
            if len(sentence) <= max_chars_per_subtitle:
                final_sentences.append(sentence)
            else:
                # 按逗号拆分
                comma_splits = re.split(r'([，,；;：:])', sentence)
                for j in range(0, len(comma_splits), 2):
                    if j + 1 < len(comma_splits):
                        final_sentences.append(comma_splits[j].strip() + comma_splits[j + 1])
                    else:
                        if comma_splits[j].strip():
                            final_sentences.append(comma_splits[j].strip())

        # 过滤空句子
        final_sentences = [s for s in final_sentences if s.strip()]

        if not final_sentences and text.strip():
            final_sentences = [text.strip()]

        return final_sentences

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


def create_precise_subtitle_synchronizer(**kwargs) -> PreciseSubtitleSynchronizer:
    """创建精确字幕同步器的便捷函数"""
    return PreciseSubtitleSynchronizer(**kwargs)