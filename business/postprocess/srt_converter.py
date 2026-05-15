"""
SRT 格式转换工具 - 将强制对齐结果转换为 SRT 字幕格式

按标点符号拆分字幕条目，每条不超过 12 字
"""

from typing import List, Dict
from pathlib import Path
from dataclasses import dataclass


# 字幕最大字符数
MAX_CHARS_PER_SUBTITLE = 12

# 中文字符标点符号（用于拆分字幕）
CHINESE_PUNCTUATION = "，。！？；：、,.!?;:"


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


def convert_timestamps_to_srt(
    time_stamps: List[Dict],
    full_text: str = None,
    max_chars: int = MAX_CHARS_PER_SUBTITLE
) -> List[SrtEntry]:
    """
    将字/词级时间戳转换为 SRT 字幕条目

    Args:
        time_stamps: 字/词级时间戳列表，每个元素包含 text, start_time, end_time
        full_text: 完整文案文本（预留参数，可用于验证时间戳完整性或辅助拆分）
        max_chars: 每条字幕最大字符数，默认 12

    Returns:
        List[SrtEntry]: SRT 字幕条目列表
    """
    if not time_stamps:
        return []

    # 按标点符号拆分字幕
    subtitle_entries: List[SrtEntry] = []
    current_text = ""
    current_start_time = None
    current_end_time = None

    for ts in time_stamps:
        char_text = ts.text
        start_time = ts.start_time
        end_time = ts.end_time

        # 初始化起始时间
        if current_start_time is None:
            current_start_time = start_time

        # 添加字符到当前字幕
        current_text += char_text
        current_end_time = end_time

        # 检查是否需要拆分
        should_split = False

        # 条件 1：达到最大字符数
        if len(current_text) >= max_chars:
            should_split = True

        # 条件 2：遇到标点符号
        if char_text in CHINESE_PUNCTUATION and len(current_text) > 1:
            should_split = True

        # 执行拆分
        if should_split:
            subtitle_entries.append(SrtEntry(
                text=current_text.strip(),
                start_time=current_start_time,
                end_time=current_end_time
            ))
            current_text = ""
            current_start_time = None
            current_end_time = None

    # 处理剩余的字符
    if current_text.strip():
        subtitle_entries.append(SrtEntry(
            text=current_text.strip(),
            start_time=current_start_time,
            end_time=current_end_time
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
