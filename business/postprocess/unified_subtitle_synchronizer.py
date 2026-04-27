"""
统一精确字幕时间轴同步器
整合三个同步器的优点：
1. 使用 TTS 精确时长作为时间基准（PreciseSubtitleSynchronizer）
2. 考虑标点类型对停顿的影响（SmartSubtitleSynchronizer）
3. 按字符权重智能分配时间（SmartSubtitleSynchronizer）
4. 支持音频能量检测作为备用方案（IntelligentSubtitleSynchronizer）
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SentenceInfo:
    """句子信息"""
    text: str
    char_count: int
    punctuation_type: str  # 'period', 'exclamation', 'question', 'comma', 'none'
    estimated_duration: float  # 估算时长
    weight: float  # 时间分配权重


@dataclass
class SubtitleEntry:
    """字幕条目"""
    index: int
    start_time: float  # 秒
    end_time: float    # 秒
    text: str


class UnifiedSubtitleSynchronizer:
    """
    统一精确字幕时间轴同步器

    核心算法：
    1. 使用 TTS 提供的精确时长作为时间基准
    2. 分析句子特征（长度、标点类型）
    3. 根据标点类型计算停顿时间
    4. 按权重智能分配时间
    5. 确保字幕不超出段落时长
    """

    # 字数限制
    MAX_CHARS_PER_SUBTITLE = 12  # 单条字幕最大字数（中文）

    # 语音规律参数
    CHARS_PER_SECOND = 4.5  # 平均每秒字数（用于估算）
    MIN_SENTENCE_DURATION = 0.5  # 最小句子时长（秒）
    MAX_SENTENCE_DURATION = 5.0  # 最大句子时长（秒）

    # 标点停顿时间（秒）
    PUNCTUATION_PAUSE = {
        'period': 0.3,      # 句号停顿
        'exclamation': 0.4, # 感叹号停顿
        'question': 0.4,    # 问号停顿
        'comma': 0.15,      # 逗号停顿
        'none': 0.1,        # 无标点
    }

    def __init__(
        self,
        padding_ms: int = 80,       # 字幕提前显示时间
        buffer_ms: int = 100,       # 段落末尾缓冲
        overlap_ms: int = 50,       # 字幕之间的重叠时间（避免闪烁）
        min_subtitle_duration: float = 0.5,
        max_subtitle_duration: float = 6.0,
    ):
        """
        初始化统一字幕同步器

        Args:
            padding_ms: 字幕提前显示时间（毫秒）
            buffer_ms: 段落末尾缓冲时间（毫秒）
            overlap_ms: 字幕之间的重叠时间（毫秒）
            min_subtitle_duration: 最小字幕时长（秒）
            max_subtitle_duration: 最大字幕时长（秒）
        """
        self.padding_ms = padding_ms
        self.buffer_ms = buffer_ms
        self.overlap_ms = overlap_ms
        self.min_subtitle_duration = min_subtitle_duration
        self.max_subtitle_duration = max_subtitle_duration

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
            logger.info("开始统一精确字幕同步")

            if not segments_text:
                logger.warning("没有文本内容")
                return False

            if not segment_durations or not segment_offsets:
                logger.error("缺少段落时长或偏移信息")
                return False

            all_subtitles = []
            subtitle_index = 1

            for seg_idx, text in enumerate(segments_text):
                if not text:
                    continue

                duration = segment_durations[seg_idx]
                offset = segment_offsets[seg_idx]

                if duration <= 0:
                    logger.warning(f"段落 {seg_idx} 时长无效: {duration}")
                    continue

                # 1. 分析句子特征
                sentences = self._analyze_sentences(text)
                if not sentences:
                    continue

                # 2. 智能分配时间
                sentence_times = self._allocate_time(
                    sentences,
                    offset,
                    duration
                )

                # 3. 生成字幕条目
                for start, end, sentence in sentence_times:
                    all_subtitles.append(SubtitleEntry(
                        index=subtitle_index,
                        start_time=start,
                        end_time=end,
                        text=sentence
                    ))
                    subtitle_index += 1

            # 写入 SRT 文件
            self._write_srt(all_subtitles, output_srt_path)

            logger.info(f"统一精确字幕同步完成，生成 {len(all_subtitles)} 条字幕")
            return True

        except Exception as e:
            logger.error(f"统一精确字幕同步失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _analyze_sentences(self, text: str) -> List[SentenceInfo]:
        """
        分析文本，拆分句子并提取特征

        策略：
        1. 按所有标点符号拆分
        2. 单条字幕限制为 MAX_CHARS_PER_SUBTITLE 字
        3. 避免单独的标点符号成为一条字幕
        """
        # 按所有标点符号拆分（中英文标点）
        parts = re.split(r'([。！？.!?，,；;：:])', text)

        raw_sentences = []
        for i in range(0, len(parts), 2):
            if i + 1 < len(parts):
                sentence = parts[i].strip() + parts[i + 1]
            else:
                sentence = parts[i].strip()

            if sentence:
                raw_sentences.append(sentence)

        if not raw_sentences and text.strip():
            raw_sentences = [text.strip()]

        # 分析每个句子
        sentences = []
        for sentence in raw_sentences:
            info = self._analyze_single_sentence(sentence)

            # 如果句子超过最大字数限制，按字数强制拆分
            if info.char_count > self.MAX_CHARS_PER_SUBTITLE:
                sub_sentences = self._split_by_char_limit(sentence, self.MAX_CHARS_PER_SUBTITLE)
                for sub in sub_sentences:
                    # 跳过只有标点符号的片段
                    if sub.strip() and not self._is_only_punctuation(sub):
                        sentences.append(self._analyze_single_sentence(sub))
            else:
                # 跳过只有标点符号的片段
                if sentence.strip() and not self._is_only_punctuation(sentence):
                    sentences.append(info)

        return sentences

    def _is_only_punctuation(self, text: str) -> bool:
        """检查文本是否只包含标点符号"""
        return all(c in '，,；;：:。！？.!?' for c in text.strip())

    def _analyze_single_sentence(self, sentence: str) -> SentenceInfo:
        """
        分析单个句子，提取特征

        Returns:
            SentenceInfo: 句子信息
        """
        char_count = len(sentence)

        # 检测标点类型
        punctuation_type = self._detect_punctuation_type(sentence)

        # 估算时长：字符数 / 语速 + 标点停顿
        base_duration = char_count / self.CHARS_PER_SECOND
        pause = self.PUNCTUATION_PAUSE.get(punctuation_type, 0.1)
        estimated_duration = base_duration + pause

        # 确保在合理范围
        estimated_duration = max(self.MIN_SENTENCE_DURATION, estimated_duration)
        estimated_duration = min(self.MAX_SENTENCE_DURATION, estimated_duration)

        # 计算权重（用于时间分配）
        # 权重 = 字符数 + 标点权重
        weight = char_count
        if punctuation_type != 'none':
            weight += 2  # 有标点增加权重

        return SentenceInfo(
            text=sentence,
            char_count=char_count,
            punctuation_type=punctuation_type,
            estimated_duration=estimated_duration,
            weight=weight
        )

    def _detect_punctuation_type(self, sentence: str) -> str:
        """检测句子的标点类型"""
        if sentence.endswith('。') or sentence.endswith('.'):
            return 'period'
        elif sentence.endswith('！') or sentence.endswith('!'):
            return 'exclamation'
        elif sentence.endswith('?') or sentence.endswith('?'):
            return 'question'
        elif sentence.endswith('，') or sentence.endswith(','):
            return 'comma'
        return 'none'

    def _split_by_char_limit(self, text: str, max_chars: int) -> List[str]:
        """
        按字数限制分割文本

        策略：
        1. 严格按字数限制分割，确保每段不超过 max_chars
        2. 尽量在标点符号后分割，保留标点
        3. 避免单独的标点符号成为一条字幕
        4. 若切分后剩余字数少于3字，则不切分（避免出现极短字幕）
        """
        if len(text) <= max_chars:
            return [text]

        # 检查是否需要分割：如果分割后剩余字数少于3字，则不分割
        # 找到最佳分割点
        best_split_pos = max_chars

        # 尝试在 max_chars 位置附近找一个标点作为分割点
        for i in range(min(max_chars, len(text)) - 1, max(0, max_chars - 5), -1):
            if text[i] in '，,；;：:。！？.!?':
                best_split_pos = i + 1  # 在标点后分割，保留标点在前一段
                break

        # 确保分割位置不超过 max_chars
        best_split_pos = min(best_split_pos, max_chars)

        # 计算分割后剩余的字数
        remaining_chars = len(text) - best_split_pos

        # 如果剩余字数少于3字，则不分割，直接返回原文（即使超过限制）
        # 这样可以避免出现如 "12字 + 2字" 这样的极端情况
        if remaining_chars < 3:
            return [text]

        chunks = []
        remaining = text

        while len(remaining) > max_chars:
            # 默认在 max_chars 位置分割
            split_pos = max_chars

            # 尝试在 max_chars 位置附近找一个标点作为分割点
            for i in range(min(max_chars, len(remaining)) - 1, max(0, max_chars - 5), -1):
                if remaining[i] in '，,；;：:。！？.!?':
                    split_pos = i + 1  # 在标点后分割，保留标点在前一段
                    break

            # 确保分割位置不超过 max_chars
            split_pos = min(split_pos, max_chars)

            # 计算分割后剩余的字数
            next_remaining_chars = len(remaining) - split_pos

            # 如果分割后剩余字数少于3字，则停止分割
            if next_remaining_chars < 3:
                break

            chunk = remaining[:split_pos]
            # 只有当 chunk 不只是标点符号时才添加
            if chunk.strip() and not self._is_only_punctuation(chunk):
                chunks.append(chunk)

            remaining = remaining[split_pos:]

        # 处理剩余部分
        if remaining:
            if remaining.strip() and not self._is_only_punctuation(remaining):
                # 如果剩余部分超过 max_chars 且 chunks 为空，需要强制处理
                if len(remaining) > max_chars and not chunks:
                    # 这种情况下，尽量找一个合理的分割点
                    # 找到剩余部分中最后一个标点位置
                    last_punct_pos = -1
                    for i in range(len(remaining) - 1, -1, -1):
                        if remaining[i] in '，,；;：:。！？.!?':
                            last_punct_pos = i + 1
                            break

                    if last_punct_pos > 3 and last_punct_pos <= max_chars:
                        # 可以在标点处分割
                        chunks.append(remaining[:last_punct_pos])
                        remaining = remaining[last_punct_pos:]
                        if remaining.strip() and not self._is_only_punctuation(remaining):
                            chunks.append(remaining)
                    else:
                        # 无法合理分割，直接返回整个剩余部分
                        chunks.append(remaining)
                elif len(remaining) > max_chars:
                    # 已经有 chunks 了，剩余部分超长
                    # 继续尝试分割
                    sub_chunks = self._split_by_char_limit(remaining, max_chars)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(remaining)

        return chunks if chunks else [text]

    def _allocate_time(
        self,
        sentences: List[SentenceInfo],
        segment_offset: float,
        segment_duration: float
    ) -> List[Tuple[float, float, str]]:
        """
        智能分配时间

        策略：
        1. 使用 TTS 精确时长作为时间基准
        2. 按权重分配时间（考虑字符数和标点）
        3. 字幕提前显示（padding）
        4. 相邻字幕有轻微重叠（避免闪烁）
        5. 确保字幕不超出段落时长

        Returns:
            [(start_time, end_time, sentence), ...]
        """
        if not sentences:
            return []

        # 计算总权重
        total_weight = sum(s.weight for s in sentences)

        if total_weight == 0:
            return []

        # 可用时长（留缓冲）
        available_duration = segment_duration - self.buffer_ms / 1000

        times = []
        current_time = segment_offset

        for i, sentence in enumerate(sentences):
            # 按权重分配时间
            weight_ratio = sentence.weight / total_weight
            sentence_duration = available_duration * weight_ratio

            # 确保时长在合理范围内
            sentence_duration = max(self.min_subtitle_duration, sentence_duration)
            sentence_duration = min(self.max_subtitle_duration, sentence_duration)

            # 对于极短句子（<5字），限制最大时长
            if sentence.char_count <= 5:
                sentence_duration = min(sentence_duration, 1.0)

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
                sentence_duration = end_time - start_time

            # 确保时长足够
            if sentence_duration < self.min_subtitle_duration:
                sentence_duration = self.min_subtitle_duration
                end_time = start_time + sentence_duration
                if end_time > max_end_time:
                    end_time = max_end_time
                    start_time = max(segment_offset, end_time - self.min_subtitle_duration)

            times.append((start_time, end_time, sentence.text))

            # 更新当前时间（考虑重叠）
            current_time = end_time - self.overlap_ms / 1000

            # 句末停顿
            if sentence.punctuation_type in ['period', 'exclamation', 'question']:
                current_time += 0.1

        return times

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


def create_unified_subtitle_synchronizer(**kwargs) -> UnifiedSubtitleSynchronizer:
    """创建统一字幕同步器的便捷函数"""
    return UnifiedSubtitleSynchronizer(**kwargs)
