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

# 中文字符标点符号（用于拆分字幕）
# 包含常见的中文和英文标点符号
# 注意：使用转义引号避免语法错误
CHINESE_PUNCTUATION = "，。！？；：、,.!?;:）】》\"'」』～~—…"

# 标点符号正则表达式（用于拆分包含标点的 token）
# 包含常见的中文和英文标点符号
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
    1. 使用 full_text 作为字幕文本来源（确保完整性）
    2. 使用 time_stamps 提供每个字符的时间信息
    3. 首先按标点符号分段，其次按字数限制

    Args:
        time_stamps: 字/词级时间戳列表，每个元素包含 text, start_time, end_time
        full_text: 完整文案文本（用于确保字幕完整性）
        max_chars: 每条字幕最大字符数，默认 12

    Returns:
        List[SrtEntry]: SRT 字幕条目列表
    """
    if not time_stamps:
        return []

    # 构建字符到时间戳的映射
    # time_stamps 中的每个 item 包含 text（可能是单字符或多字符）和时间
    char_time_map = {}  # 字符索引 -> (start_time, end_time)

    char_index = 0
    for ts in time_stamps:
        token_text = ts.text
        token_start = ts.start_time
        token_end = ts.end_time

        # 计算每个字符的时间（均匀分配）
        if len(token_text) == 1:
            char_time_map[char_index] = (token_start, token_end)
            char_index += 1
        else:
            # 多字符 token，按字符数均匀分配时间
            duration = token_end - token_start
            for i, ch in enumerate(token_text):
                ch_start = token_start + (i / len(token_text)) * duration
                ch_end = token_start + ((i + 1) / len(token_text)) * duration
                char_time_map[char_index] = (ch_start, ch_end)
                char_index += 1

    # 使用 full_text 作为字幕文本（如果提供）
    if full_text:
        text_to_use = full_text
    else:
        # 从时间戳重建文本
        text_to_use = "".join(ts.text for ts in time_stamps)

    # 按标点符号分段
    subtitle_entries: List[SrtEntry] = []
    current_text = ""
    current_start_idx = 0

    for i, char in enumerate(text_to_use):
        if not current_text:
            current_start_idx = i

        current_text += char

        # 检查是否需要拆分
        should_split = False

        # 条件 1：遇到标点符号（且当前字幕长度 > 1）
        if char in CHINESE_PUNCTUATION and len(current_text) > 1:
            should_split = True

        # 条件 2：达到最大字符数（且当前不是标点符号）
        if len(current_text) >= max_chars and char not in CHINESE_PUNCTUATION:
            should_split = True

        # 执行拆分
        if should_split:
            # 获取这段文本的时间范围
            start_time, end_time = _get_time_range(char_time_map, current_start_idx, i)
            subtitle_entries.append(SrtEntry(
                text=current_text.strip(),
                start_time=start_time,
                end_time=end_time
            ))
            current_text = ""

    # 处理剩余的字符
    if current_text.strip():
        start_time, end_time = _get_time_range(char_time_map, current_start_idx, len(text_to_use) - 1)
        subtitle_entries.append(SrtEntry(
            text=current_text.strip(),
            start_time=start_time,
            end_time=end_time
        ))

    return subtitle_entries


def _get_time_range(char_time_map: Dict, start_idx: int, end_idx: int) -> tuple:
    """
    获取字符范围的时间范围

    对于没有时间戳的字符，使用线性插值估算时间

    Args:
        char_time_map: 字符索引到时间的映射
        start_idx: 起始字符索引
        end_idx: 结束字符索引

    Returns:
        (start_time, end_time) 元组
    """
    if not char_time_map:
        return (0.0, 0.3)

    max_idx = max(char_time_map.keys())

    # 获取起始时间
    if start_idx in char_time_map:
        start_time = char_time_map[start_idx][0]
    elif start_idx <= max_idx:
        # 在已知范围内，使用插值
        # 找前一个和后一个有时间戳的字符
        prev_idx = start_idx
        while prev_idx >= 0 and prev_idx not in char_time_map:
            prev_idx -= 1

        next_idx = start_idx
        while next_idx <= max_idx and next_idx not in char_time_map:
            next_idx += 1

        if prev_idx >= 0 and next_idx <= max_idx:
            # 线性插值
            prev_time = char_time_map[prev_idx][0]
            next_time = char_time_map[next_idx][0]
            ratio = (start_idx - prev_idx) / (next_idx - prev_idx) if next_idx != prev_idx else 0
            start_time = prev_time + ratio * (next_time - prev_time)
        elif prev_idx >= 0:
            start_time = char_time_map[prev_idx][1]
        else:
            start_time = 0.0
    else:
        # 超出已知范围，使用最后一个时间戳的结束时间
        start_time = char_time_map[max_idx][1]

    # 获取结束时间
    if end_idx in char_time_map:
        end_time = char_time_map[end_idx][1]
    elif end_idx <= max_idx:
        # 在已知范围内，使用插值
        prev_idx = end_idx
        while prev_idx >= 0 and prev_idx not in char_time_map:
            prev_idx -= 1

        next_idx = end_idx
        while next_idx <= max_idx and next_idx not in char_time_map:
            next_idx += 1

        if prev_idx >= 0 and next_idx <= max_idx:
            prev_time = char_time_map[prev_idx][1]
            next_time = char_time_map[next_idx][1]
            ratio = (end_idx - prev_idx) / (next_idx - prev_idx) if next_idx != prev_idx else 0
            end_time = prev_time + ratio * (next_time - prev_time)
        elif prev_idx >= 0:
            end_time = char_time_map[prev_idx][1]
        else:
            end_time = start_time + 0.3
    else:
        # 超出已知范围，估算时间（每字符约0.3秒）
        end_time = start_time + 0.3 * (end_idx - start_idx + 1)

    return (start_time, end_time)


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
