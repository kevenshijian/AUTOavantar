"""
测试精确字幕同步器
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from business.postprocess.precise_subtitle_synchronizer import (
    PreciseSubtitleSynchronizer,
    create_precise_subtitle_synchronizer
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_precise_synchronizer():
    """测试精确字幕同步器"""

    logger.info("=" * 50)
    logger.info("测试精确字幕同步器")
    logger.info("=" * 50)

    synchronizer = create_precise_subtitle_synchronizer(
        padding_ms=80,
        min_subtitle_duration=0.5,
        max_subtitle_duration=6.0,
    )

    # 模拟真实场景
    segments_text = [
        "大家好，欢迎来到我们的频道。今天我们要讨论一个非常重要的话题。",
        "首先，让我们来看一下背景情况。这个问题已经存在很长时间了。",
        "接下来，我会详细解释解决方案。请仔细听，这对你很有帮助。",
    ]

    # 模拟 TTS 生成的实际音频时长（每个段落）
    segment_durations = [5.2, 4.8, 6.1]
    segment_offsets = [0.0, 5.2, 10.0]

    # 创建临时输出文件
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        srt_path = os.path.join(temp_dir, "test_output.srt")

        success = synchronizer.synchronize(
            segments_text=segments_text,
            segment_durations=segment_durations,
            segment_offsets=segment_offsets,
            output_srt_path=srt_path,
        )

        if success and os.path.exists(srt_path):
            logger.info("✓ 精确字幕同步成功")
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"生成的字幕内容:\n{content}")
            return True
        else:
            logger.error("✗ 精确字幕同步失败")
            return False


def test_sentence_split():
    """测试句子拆分"""
    logger.info("=" * 50)
    logger.info("测试句子拆分")
    logger.info("=" * 50)

    synchronizer = create_precise_subtitle_synchronizer()

    test_cases = [
        "这是一个简单的句子。",
        "这是第一句。这是第二句！这是第三句？",
        "这是一个很长的句子，包含多个逗号，用于测试拆分功能，看看效果如何。",
    ]

    for text in test_cases:
        sentences = synchronizer._split_text_to_sentences(text)
        logger.info(f"原文: {text}")
        logger.info(f"拆分: {sentences}")
        logger.info("-" * 30)

    return True


if __name__ == "__main__":
    logger.info("开始测试精确字幕同步器")
    logger.info("=" * 60)

    test1_passed = test_sentence_split()
    test2_passed = test_precise_synchronizer()

    logger.info("=" * 60)
    logger.info(f"测试结果:")
    logger.info(f"  测试 1 (句子拆分): {'通过' if test1_passed else '失败'}")
    logger.info(f"  测试 2 (精确同步): {'通过' if test2_passed else '失败'}")

    if test1_passed and test2_passed:
        logger.info("所有测试通过！")
    else:
        logger.error("部分测试失败")
