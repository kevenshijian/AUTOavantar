"""
智能字幕时间轴同步器测试脚本
"""

import os
import sys
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from business.postprocess.subtitle_synchronizer import (
    IntelligentSubtitleSynchronizer,
    SubtitleEntry,
    create_subtitle_synchronizer
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_subtitle_synchronizer():
    """测试字幕同步器基本功能"""

    # 创建同步器实例
    synchronizer = create_subtitle_synchronizer(
        min_silence_ms=150,
        silence_thresh_db=-35,
        padding_ms=80,
    )

    # 测试句子拆分
    test_text = "你好，欢迎使用智能字幕系统。这是一个测试文本。"
    sentences = synchronizer._split_text_to_sentences(test_text)
    logger.info(f"拆分结果: {sentences}")

    # 测试 SRT 时间格式化
    test_times = [0.0, 1.5, 3.456, 65.789, 3661.123]
    for t in test_times:
        formatted = synchronizer._format_srt_time(t)
        logger.info(f"时间 {t}s -> {formatted}")

    # 测试长字幕拆分
    long_text = "这是一个非常长的字幕，需要被拆分成多个部分，以便更好地显示在屏幕上。"
    split_result = synchronizer._split_long_subtitle(long_text, 0.0, 10.0, 1)
    logger.info(f"长字幕拆分结果: {len(split_result)} 条")
    for sub in split_result:
        logger.info(f"  [{sub.index}] {sub.start_time:.2f}s - {sub.end_time:.2f}s: {sub.text}")

    logger.info("基本功能测试完成")


def test_speech_detection():
    """测试语音检测功能"""
    import numpy as np

    synchronizer = create_subtitle_synchronizer()

    # 创建模拟音频数据（包含静音和语音段）
    sample_rate = 16000
    duration = 5.0  # 5秒
    n_samples = int(sample_rate * duration)

    # 创建包含语音段的音频
    audio = np.zeros(n_samples, dtype=np.float32)

    # 模拟几个语音段（0.5-1.5秒，2.0-3.0秒，3.5-4.5秒）
    speech_segments = [(0.5, 1.5), (2.0, 3.0), (3.5, 4.5)]
    for start, end in speech_segments:
        start_idx = int(start * sample_rate)
        end_idx = int(end * sample_rate)
        # 添加随机噪声模拟语音
        audio[start_idx:end_idx] = np.random.randn(end_idx - start_idx) * 0.3

    # 检测语音段
    detected = synchronizer._detect_speech_segments(audio)

    logger.info(f"模拟语音段: {speech_segments}")
    logger.info(f"检测语音段: {detected}")

    # 验证检测结果
    if len(detected) == len(speech_segments):
        logger.info("语音段数量匹配")
    else:
        logger.warning(f"语音段数量不匹配: 期望 {len(speech_segments)}, 实际 {len(detected)}")


def test_text_alignment():
    """测试文本对齐功能"""

    synchronizer = create_subtitle_synchronizer()

    # 测试数据
    sentences = ["第一句话。", "第二句话。", "第三句话。"]
    speech_segments = [(0.0, 1.5), (2.0, 3.5), (4.0, 5.5)]

    # 对齐文本
    subtitles = synchronizer._align_text_to_speech(
        segments_text=sentences,
        speech_segments=speech_segments,
    )

    logger.info(f"对齐结果: {len(subtitles)} 条字幕")
    for sub in subtitles:
        logger.info(f"  [{sub.index}] {sub.start_time:.2f}s - {sub.end_time:.2f}s: {sub.text}")


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("开始测试智能字幕时间轴同步器")
    logger.info("=" * 50)

    test_subtitle_synchronizer()
    logger.info("-" * 50)

    test_speech_detection()
    logger.info("-" * 50)

    test_text_alignment()
    logger.info("-" * 50)

    logger.info("所有测试完成")
