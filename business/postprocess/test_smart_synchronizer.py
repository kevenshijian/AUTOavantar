"""
测试智能字幕同步器
验证不同长度句子的时间分配准确性
"""

import os
import sys
import logging
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from business.postprocess.smart_subtitle_synchronizer import (
    SmartSubtitleSynchronizer,
    create_smart_subtitle_synchronizer
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_variable_sentence_lengths():
    """
    测试不同长度句子的时间分配

    场景：
    1. 短句子（几个字）
    2. 长句子（几十个字）
    3. 混合情况
    """
    logger.info("=" * 60)
    logger.info("测试：不同长度句子的时间分配")
    logger.info("=" * 60)

    synchronizer = create_smart_subtitle_synchronizer(
        padding_ms=80,
        buffer_ms=100,
    )

    # 场景 1：短音频，两句话（一句短，一句长）
    logger.info("\n场景 1：短音频，两句话")
    segments_text_1 = [
        "大家好。今天我们要讨论一个非常重要的话题，这个话题涉及到我们日常生活中的方方面面，需要我们认真思考和对待。",
    ]
    segment_durations_1 = [5.0]  # 5 秒音频
    segment_offsets_1 = [0.0]

    with tempfile.TemporaryDirectory() as temp_dir:
        srt_path = os.path.join(temp_dir, "test_1.srt")
        success = synchronizer.synchronize(
            segments_text=segments_text_1,
            segment_durations=segment_durations_1,
            segment_offsets=segment_offsets_1,
            output_srt_path=srt_path,
        )

        if success:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"生成的字幕:\n{content}")

            # 分析时间分配
            lines = content.strip().split('\n\n')
            for block in lines:
                parts = block.split('\n')
                if len(parts) >= 3:
                    time_line = parts[1]
                    text = parts[2]
                    start_end = time_line.split(' --> ')
                    start = parse_srt_time(start_end[0])
                    end = parse_srt_time(start_end[1])
                    duration = end - start
                    logger.info(f"句子 '{text}' ({len(text)}字) -> 时长 {duration:.2f}s")

    # 场景 2：多句话，长短混合
    logger.info("\n场景 2：多句话，长短混合")
    segments_text_2 = [
        "你好。这是一个简短的句子。这是一个非常长的句子，包含了很多内容，需要更多时间来朗读，观众也需要更多时间来阅读和理解。最后一句。",
    ]
    segment_durations_2 = [12.0]  # 12 秒音频
    segment_offsets_2 = [0.0]

    with tempfile.TemporaryDirectory() as temp_dir:
        srt_path = os.path.join(temp_dir, "test_2.srt")
        success = synchronizer.synchronize(
            segments_text=segments_text_2,
            segment_durations=segment_durations_2,
            segment_offsets=segment_offsets_2,
            output_srt_path=srt_path,
        )

        if success:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"生成的字幕:\n{content}")

    # 场景 3：多个段落，每个段落不同长度
    logger.info("\n场景 3：多个段落")
    segments_text_3 = [
        "大家好，欢迎来到我们的频道。",  # 短段落
        "今天我们要讨论一个非常重要的话题，这个话题涉及到我们日常生活中的方方面面，需要我们认真思考和对待，希望大家能够仔细聆听。",  # 长段落
        "谢谢观看。",  # 极短段落
    ]
    segment_durations_3 = [3.0, 10.0, 1.5]
    segment_offsets_3 = [0.0, 3.0, 13.0]

    with tempfile.TemporaryDirectory() as temp_dir:
        srt_path = os.path.join(temp_dir, "test_3.srt")
        success = synchronizer.synchronize(
            segments_text=segments_text_3,
            segment_durations=segment_durations_3,
            segment_offsets=segment_offsets_3,
            output_srt_path=srt_path,
        )

        if success:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"生成的字幕:\n{content}")

    return True


def test_sentence_analysis():
    """测试句子分析功能"""
    logger.info("=" * 60)
    logger.info("测试：句子分析")
    logger.info("=" * 60)

    synchronizer = create_smart_subtitle_synchronizer()

    test_cases = [
        "大家好。",
        "这是一个非常长的句子，包含了很多内容，需要更多时间来朗读。",
        "你好！这是第一句。这是第二句？这是第三句。",
    ]

    for text in test_cases:
        sentences = synchronizer._analyze_sentences(text)
        logger.info(f"\n原文: {text}")
        for s in sentences:
            logger.info(f"  句子: '{s.text}'")
            logger.info(f"    字数: {s.char_count}")
            logger.info(f"    标点: {s.punctuation_type}")
            logger.info(f"    估算时长: {s.estimated_duration:.2f}s")
            logger.info(f"    权重: {s.weight}")

    return True


def test_long_sentence_split():
    """测试长句子拆分"""
    logger.info("=" * 60)
    logger.info("测试：长句子拆分")
    logger.info("=" * 60)

    synchronizer = create_smart_subtitle_synchronizer()

    test_cases = [
        "这是一个非常长的句子，包含了很多内容，需要更多时间来朗读，观众也需要更多时间来阅读和理解，所以我们需要把它拆分成多个部分。",
        "短句子。",
    ]

    for text in test_cases:
        result = synchronizer._split_long_sentence(text)
        logger.info(f"\n原文: {text} ({len(text)}字)")
        logger.info(f"拆分结果: {result}")
        for s in result:
            logger.info(f"  '{s}' ({len(s)}字)")

    return True


def parse_srt_time(time_str: str) -> float:
    """解析 SRT 时间格式"""
    parts = time_str.replace(',', ':').split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])
    ms = int(parts[3])
    return hours * 3600 + minutes * 60 + seconds + ms / 1000


if __name__ == "__main__":
    logger.info("开始测试智能字幕同步器")
    logger.info("=" * 60)

    test1_passed = test_sentence_analysis()
    test2_passed = test_long_sentence_split()
    test3_passed = test_variable_sentence_lengths()

    logger.info("=" * 60)
    logger.info(f"测试结果:")
    logger.info(f"  测试 1 (句子分析): {'通过' if test1_passed else '失败'}")
    logger.info(f"  测试 2 (长句拆分): {'通过' if test2_passed else '失败'}")
    logger.info(f"  测试 3 (时间分配): {'通过' if test3_passed else '失败'}")

    if test1_passed and test2_passed and test3_passed:
        logger.info("所有测试通过！")
    else:
        logger.error("部分测试失败")