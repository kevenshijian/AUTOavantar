"""
SRT 格式转换工具 - 将强制对齐结果转换为 SRT 字幕格式

按标点符号拆分字幕条目，每条不超过 12 字

注意：qwen_asr 的 tokenize_space_lang 方法会将中文拆分成单个字符，
但标点符号会被合并到非 CJK 部分。例如：
- 输入："大家好，今天我们来学习。"
- 拆分：['大', '家', '好，今天我们来学习。']

因此需要在处理时将包含标点符号的 token 进一步拆分。
"""

from typing import List, Dict
from pathlib import Path
from dataclasses import dataclass
import re


# 字幕最大字符数
MAX_CHARS_PER_SUBTITLE = 12

# 中文字符标点符号（用于拆分字幕，但不显示在字幕中）
CHINESE_PUNCTUATION = "，。！？；：、,.!?;:）】》\"'」』～~—…"

# 标点符号正则表达式（用于拆分包含标点的 token）
PUNCTUATION_PATTERN = re.compile(r'([，。！？；：、,.!?;:）】》"\'」』～~—…])')


@dataclass
class SrtEntry:
    """SRT 字幕条目"""
    text: str
    start_time: float
    end_time: float

    @property
    def start_time_str(self) -> str:
        """SRT 格式的开始时间字符串"""
        return format_srt_timestamp(self.start_time)

    @property
    def end_time_str(self) -> str:
        """SRT 格式的结束时间字符串"""
        return format_srt_timestamp(self.end_time)


def _split_token_with_punctuation(token: str) -> List[str]:
    """
    将包含标点符号的 token 拆分成多个部分

    例如："好，今天我们来学习。" -> ['好', '，', '今天我们来学习', '。']

    Args:
        token: 可能包含标点符号的 token

    Returns:
        拆分后的 token 列表
    """
    # 使用正则表达式拆分，保留标点符号作为独立部分
    parts = PUNCTUATION_PATTERN.split(token)
    # 过滤空字符串
    return [p for p in parts if p]


def convert_timestamps_to_srt(
    time_stamps: List[Dict],
    full_text: str = None,
    max_chars: int = MAX_CHARS_PER_SUBTITLE
) -> List[SrtEntry]:
    """
    将字/词级时间戳转换为 SRT 字幕条目

    策略：
    1. 直接使用 time_stamps 的时间信息（确保时间准确）
    2. 按标点符号分段（遇到标点就拆分）
    3. 不显示标点符号（从字幕文本中移除）

    Args:
        time_stamps: 字/词级时间戳列表，每个元素包含 text, start_time, end_time
        full_text: 完整文案文本（可选，用于辅助验证）
        max_chars: 每条字幕最大字符数，默认 12

    Returns:
        List[SrtEntry]: SRT 字幕条目列表
    """
    if not time_stamps:
        return []

    # 第一步：将所有时间戳展开为单个字符级别的时间戳
    # 这样可以确保每个字符都有准确的时间
    char_timestamps: List[tuple] = []  # (char, start_time, end_time)

    for ts in time_stamps:
        token_text = ts.text
        token_start = ts.start_time
        token_end = ts.end_time

        # 如果 token 包含多个字符（可能包含标点），需要拆分
        if len(token_text) == 1:
            char_timestamps.append((token_text, token_start, token_end))
        else:
            # 拆分多字符 token
            parts = _split_token_with_punctuation(token_text)
            # 计算每个部分的时间（按字符数均匀分配）
            duration = token_end - token_start
            total_chars = len(parts)

            current_offset = 0
            for i, part in enumerate(parts):
                part_start = token_start + (current_offset / len(token_text)) * duration
                part_end = token_start + ((current_offset + len(part)) / len(token_text)) * duration
                # 对于单个字符的部分，直接使用
                if len(part) == 1:
                    char_timestamps.append((part, part_start, part_end))
                else:
                    # 多字符部分（不含标点），按字符分配时间
                    for j, ch in enumerate(part):
                        ch_start = part_start + (j / len(part)) * (part_end - part_start)
                        ch_end = part_start + ((j + 1) / len(part)) * (part_end - part_start)
                        char_timestamps.append((ch, ch_start, ch_end))
                current_offset += len(part)

    # 第二步：按标点符号分段，生成字幕条目
    subtitle_entries: List[SrtEntry] = []
    current_chars: List[tuple] = []  # 收集当前字幕的字符和时间

    for char, start_time, end_time in char_timestamps:
        # 初始化当前字幕的起始时间
        if not current_chars:
            current_start_time = start_time

        # 添加字符到当前字幕
        current_chars.append((char, start_time, end_time))

        # 检查是否需要拆分
        should_split = False

        # 条件 1：遇到标点符号（标点符号作为分段点，但不显示）
        if char in CHINESE_PUNCTUATION:
            should_split = True

        # 条件 2：达到最大字符数（不含标点）
        non_punct_chars = [c for c, _, _ in current_chars if c not in CHINESE_PUNCTUATION]
        if len(non_punct_chars) >= max_chars and char not in CHINESE_PUNCTUATION:
            should_split = True

        # 执行拆分
        if should_split:
            # 提取字幕文本（不含标点符号）
            subtitle_text = ''.join(c for c, _, _ in current_chars if c not in CHINESE_PUNCTUATION)

            if subtitle_text.strip():
                # 获取时间范围：从第一个字符到最后一个非标点字符
                non_punct_items = [(c, s, e) for c, s, e in current_chars if c not in CHINESE_PUNCTUATION]
                if non_punct_items:
                    actual_start = non_punct_items[0][1]
                    actual_end = non_punct_items[-1][2]
                else:
                    actual_start = current_chars[0][1]
                    actual_end = current_chars[-1][2]

                subtitle_entries.append(SrtEntry(
                    text=subtitle_text.strip(),
                    start_time=actual_start,
                    end_time=actual_end
                ))

            # 清空当前字幕
            current_chars = []

    # 处理剩余的字符
    if current_chars:
        subtitle_text = ''.join(c for c, _, _ in current_chars if c not in CHINESE_PUNCTUATION)
        if subtitle_text.strip():
            non_punct_items = [(c, s, e) for c, s, e in current_chars if c not in CHINESE_PUNCTUATION]
            if non_punct_items:
                actual_start = non_punct_items[0][1]
                actual_end = non_punct_items[-1][2]
            else:
                actual_start = current_chars[0][1]
                actual_end = current_chars[-1][2]

            subtitle_entries.append(SrtEntry(
                text=subtitle_text.strip(),
                start_time=actual_start,
                end_time=actual_end
            ))

    return subtitle_entries


def format_srt_timestamp(seconds: float) -> str:
    """
    将秒数格式化为 SRT 时间格式 (HH:MM:SS,mmm)

    Args:
        seconds: 秒数（浮点数）

    Returns:
        str: SRT 格式时间字符串
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt_file(entries: List[SrtEntry], output_path: str) -> str:
    """
    将字幕条目写入 SRT 文件

    Args:
        entries: SRT 字幕条目列表
        output_path: 输出文件路径

    Returns:
        str: 输出的 SRT 文件路径
    """
    output_file = Path(output_path)

    # 确保输出目录存在
    output_dir = output_file.parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        for idx, entry in enumerate(entries, 1):
            # SRT 格式：
            # 序号
            # 开始时间 --> 结束时间
            # 字幕文本
            # 空行
            f.write(f"{idx}\n")
            f.write(f"{entry.start_time_str} --> {entry.end_time_str}\n")
            f.write(f"{entry.text}\n")
            f.write("\n")

    return str(output_file)


def convert_and_write_srt(
    time_stamps: List,
    full_text: str,
    output_path: str,
    max_chars: int = MAX_CHARS_PER_SUBTITLE
) -> str:
    """
    一站式转换：将字/词级时间戳转换为 SRT 文件

    Args:
        time_stamps: 字/词级时间戳列表
        full_text: 完整文案文本
        max_chars: 每条字幕最大字符数
        output_path: 输出 SRT 文件路径

    Returns:
        str: 输出的 SRT 文件路径
    """
    entries = convert_timestamps_to_srt(time_stamps, full_text, max_chars)
    return write_srt_file(entries, output_path)