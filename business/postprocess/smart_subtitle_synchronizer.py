"""
智能字幕时间轴同步器
结合句子特征、语音规律和音频时长，精确分配字幕时间

核心改进：
1. 分析句子特征（长度、标点、语义）
2. 根据语音规律调整时间分配
3. 处理长短句混合的情况
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
    has_punctuation: bool
    punctuation_type: str  # 'period', 'exclamation', 'question', 'comma', 'none'
    estimated_duration: float  # 估算时长
    weight: float  # 时间分配权重


class SmartSubtitleSynchronizer:
    """
    智能字幕时间轴同步器

    核心算法：
    1. 分析每个句子的特征
    2. 根据语音规律估算时长
    3. 在段落时长约束下优化分配
    """

    # 语音规律参数
    CHARS_PER_SECOND = 4.5  # 平均每秒字数
    MIN_SENTENCE_DURATION = 0.5  # 最小句子时长
    MAX_SENTENCE_DURATION = 5.0  # 最大句子时长（超过则拆分）
    PUNCTUATION_PAUSE = {
        'period': 0.3,      # 句号停顿
        'exclamation': 0.4, # 感叹号停顿
        'question': 0.4,    # 问号停顿
        'comma': 0.15,      # 逗号停顿
        'none': 0.1,        # 无标点
    }

    def __init__(
        self,
        padding_ms: int = 80,
        buffer_ms: int = 100,  # 段落末尾缓冲
    ):
        self.padding_ms = padding_ms
        self.buffer_ms = buffer_ms

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
        """
        try:
            logger.info("开始智能字幕同步")

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

                # 分析句子
                sentences = self._analyze_sentences(text)

                # 计算时间分配
                sentence_times = self._allocate_time(
                    sentences,
                    offset,
                    duration
                )

                # 生成字幕
                for start, end, sentence in sentence_times:
                    all_subtitles.append({
                        'index': subtitle_index,
                        'start': start,
                        'end': end,
                        'text': sentence
                    })
                    subtitle_index += 1

            # 写入 SRT
            self._write_srt(all_subtitles, output_srt_path)

            logger.info(f"智能字幕同步完成，生成 {len(all_subtitles)} 条字幕")
            return True

        except Exception as e:
            logger.error(f"智能字幕同步失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _analyze_sentences(self, text: str) -> List[SentenceInfo]:
        """
        分析文本，拆分句子并提取特征
        """
        # 按句末标点拆分
        parts = re.split(r'([。！？.!?])', text)

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

            # 如果句子太长，拆分
            if info.char_count > 25:
                sub_sentences = self._split_long_sentence(sentence)
                for sub in sub_sentences:
                    sentences.append(self._analyze_single_sentence(sub))
            else:
                sentences.append(info)

        return sentences

    def _analyze_single_sentence(self, sentence: str) -> SentenceInfo:
        """分析单个句子"""
        char_count = len(sentence)

        # 检测标点类型
        punctuation_type = 'none'
        if sentence.endswith('。') or sentence.endswith('.'):
            punctuation_type = 'period'
        elif sentence.endswith('！') or sentence.endswith('!'):
            punctuation_type = 'exclamation'
        elif sentence.endswith('?') or sentence.endswith('?'):
            punctuation_type = 'question'
        elif sentence.endswith('，') or sentence.endswith(','):
            punctuation_type = 'comma'

        has_punctuation = punctuation_type != 'none'

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
        if has_punctuation:
            weight += 2  # 标点增加权重

        return SentenceInfo(
            text=sentence,
            char_count=char_count,
            has_punctuation=has_punctuation,
            punctuation_type=punctuation_type,
            estimated_duration=estimated_duration,
            weight=weight
        )

    def _split_long_sentence(self, sentence: str) -> List[str]:
        """拆分长句子"""
        # 按逗号拆分
        parts = re.split(r'([，,；;：:])', sentence)

        result = []
        for i in range(0, len(parts), 2):
            if i + 1 < len(parts):
                result.append(parts[i].strip() + parts[i + 1])
            else:
                if parts[i].strip():
                    result.append(parts[i].strip())

        if not result:
            result = [sentence]

        # 如果拆分后仍有超长句，强制分割
        final_result = []
        for s in result:
            if len(s) > 25:
                # 每 15 字分割
                chunks = [s[i:i+15] for i in range(0, len(s), 15)]
                final_result.extend(chunks)
            else:
                final_result.append(s)

        return final_result if final_result else [sentence]

    def _allocate_time(
        self,
        sentences: List[SentenceInfo],
        segment_offset: float,
        segment_duration: float
    ) -> List[Tuple[float, float, str]]:
        """
        分配时间

        策略：
        1. 计算总估算时长
        2. 如果估算时长 < 实际时长：按比例扩展
        3. 如果估算时长 > 实际时长：按比例压缩
        4. 确保每句最小时长
        """
        if not sentences:
            return []

        # 计算总权重和总估算时长
        total_weight = sum(s.weight for s in sentences)
        total_estimated = sum(s.estimated_duration for s in sentences)

        # 可用时长（留缓冲）
        available_duration = segment_duration - self.buffer_ms / 1000

        # 计算缩放因子
        if total_estimated > 0:
            scale_factor = available_duration / total_estimated
        else:
            scale_factor = 1.0

        # 分配时间
        times = []
        current_time = segment_offset

        for i, sentence in enumerate(sentences):
            # 缩放后的时长
            duration = sentence.estimated_duration * scale_factor

            # 确保最小时长
            duration = max(self.MIN_SENTENCE_DURATION, duration)

            # 对于极短句子（<5字），限制最大时长
            if sentence.char_count <= 5:
                duration = min(duration, 1.0)

            # 计算开始时间（提前显示）
            start = current_time - self.padding_ms / 1000
            if start < segment_offset:
                start = segment_offset

            # 计算结束时间
            end = current_time + duration

            # 确保不超出段落
            max_end = segment_offset + segment_duration - 0.05
            if end > max_end:
                end = max_end
                duration = end - start

            # 确保时长足够
            if duration < self.MIN_SENTENCE_DURATION:
                duration = self.MIN_SENTENCE_DURATION
                end = start + duration
                if end > max_end:
                    end = max_end
                    start = max(segment_offset, end - self.MIN_SENTENCE_DURATION)

            times.append((start, end, sentence.text))

            # 更新当前时间
            current_time = end

            # 句末停顿
            if sentence.punctuation_type in ['period', 'exclamation', 'question']:
                current_time += 0.1

        return times

    def _write_srt(self, subtitles: List[dict], output_path: str):
        """写入 SRT 文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for sub in subtitles:
                f.write(f"{sub['index']}\n")
                f.write(f"{self._format_time(sub['start'])} --> {self._format_time(sub['end'])}\n")
                f.write(f"{sub['text']}\n\n")

    def _format_time(self, seconds: float) -> str:
        """格式化 SRT 时间"""
        if seconds < 0:
            seconds = 0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def create_smart_subtitle_synchronizer(**kwargs) -> SmartSubtitleSynchronizer:
    """创建智能字幕同步器"""
    return SmartSubtitleSynchronizer(**kwargs)
