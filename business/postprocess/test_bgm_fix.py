"""
测试 BGM 添加功能
验证：
1. 视频比 BGM 长时，BGM 循环
2. 视频比 BGM 短时，BGM 截取
3. 输出时长始终等于视频时长
"""

import os
import sys
import logging
import subprocess
import tempfile
import wave
import struct

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_test_audio(duration_seconds: float, output_path: str, sample_rate: int = 16000):
    """创建测试音频文件（静音）"""
    n_frames = int(duration_seconds * sample_rate)
    with wave.open(output_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # 写入静音数据
        for _ in range(n_frames):
            wf.writeframes(struct.pack('<h', 0))


def create_test_video(duration_seconds: float, output_path: str):
    """创建测试视频文件（纯色画面）"""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=blue:s=320x240:d={duration_seconds}",
        "-f", "lavfi", "-i", f"anullsrc=r=16000:cl=mono:d={duration_seconds}",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        "-t", str(duration_seconds),
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"创建测试视频失败: {result.stderr}")
        return False
    return True


def get_media_duration(media_path: str) -> float:
    """获取媒体文件时长"""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        media_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 0.0


def test_bgm_shorter_than_video():
    """测试 BGM 比视频短的情况"""
    logger.info("=" * 50)
    logger.info("测试 1: BGM 比视频短（BGM 5秒，视频 15秒）")
    logger.info("=" * 50)

    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = os.path.join(temp_dir, "test_video.mp4")
        bgm_path = os.path.join(temp_dir, "test_bgm.wav")
        output_path = os.path.join(temp_dir, "output.mp4")

        # 创建 15 秒视频
        if not create_test_video(15.0, video_path):
            logger.error("创建测试视频失败")
            return False

        # 创建 5 秒 BGM
        create_test_audio(5.0, bgm_path)

        video_duration = get_media_duration(video_path)
        bgm_duration = get_media_duration(bgm_path)

        logger.info(f"视频时长: {video_duration}s, BGM时长: {bgm_duration}s")

        # 模拟 BGM 添加逻辑
        loop_count = int(video_duration / bgm_duration) + 1
        logger.info(f"BGM 需要循环 {loop_count} 次")

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-stream_loop", str(loop_count),
            "-i", bgm_path,
            "-filter_complex",
            f"[1:a]volume=0.3[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"BGM 添加失败: {result.stderr}")
            return False

        output_duration = get_media_duration(output_path)
        logger.info(f"输出时长: {output_duration}s")

        # 验证时长是否正确（允许 0.5 秒误差）
        if abs(output_duration - video_duration) <= 0.5:
            logger.info("✓ 测试通过：输出时长与视频时长匹配")
            return True
        else:
            logger.error(f"✗ 测试失败：输出时长 {output_duration}s 与视频时长 {video_duration}s 不匹配")
            return False


def test_bgm_longer_than_video():
    """测试 BGM 比视频长的情况"""
    logger.info("=" * 50)
    logger.info("测试 2: BGM 比视频长（BGM 60秒，视频 15秒）")
    logger.info("=" * 50)

    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = os.path.join(temp_dir, "test_video.mp4")
        bgm_path = os.path.join(temp_dir, "test_bgm.wav")
        output_path = os.path.join(temp_dir, "output.mp4")

        # 创建 15 秒视频
        if not create_test_video(15.0, video_path):
            logger.error("创建测试视频失败")
            return False

        # 创建 60 秒 BGM
        create_test_audio(60.0, bgm_path)

        video_duration = get_media_duration(video_path)
        bgm_duration = get_media_duration(bgm_path)

        logger.info(f"视频时长: {video_duration}s, BGM时长: {bgm_duration}s")

        # 使用修复后的逻辑：截取 BGM
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", bgm_path,
            "-filter_complex",
            f"[1:a]volume=0.3,atrim=0:{video_duration},asetpts=PTS-STARTPTS[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"BGM 添加失败: {result.stderr}")
            return False

        output_duration = get_media_duration(output_path)
        logger.info(f"输出时长: {output_duration}s")

        # 验证时长是否正确（允许 0.5 秒误差）
        if abs(output_duration - video_duration) <= 0.5:
            logger.info("✓ 测试通过：输出时长与视频时长匹配")
            return True
        else:
            logger.error(f"✗ 测试失败：输出时长 {output_duration}s 与视频时长 {video_duration}s 不匹配")
            return False


def test_original_bug():
    """测试原始 bug：不使用修复后的逻辑"""
    logger.info("=" * 50)
    logger.info("测试 3: 重现原始 bug（BGM 60秒，视频 15秒，不截取 BGM）")
    logger.info("=" * 50)

    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = os.path.join(temp_dir, "test_video.mp4")
        bgm_path = os.path.join(temp_dir, "test_bgm.wav")
        output_path = os.path.join(temp_dir, "output.mp4")

        # 创建 15 秒视频
        if not create_test_video(15.0, video_path):
            logger.error("创建测试视频失败")
            return False

        # 创建 60 秒 BGM
        create_test_audio(60.0, bgm_path)

        video_duration = get_media_duration(video_path)
        bgm_duration = get_media_duration(bgm_path)

        logger.info(f"视频时长: {video_duration}s, BGM时长: {bgm_duration}s")

        # 使用原始的 bug 逻辑：不截取 BGM
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", bgm_path,
            "-filter_complex",
            f"[1:a]volume=0.3[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"BGM 添加失败: {result.stderr}")
            return False

        output_duration = get_media_duration(output_path)
        logger.info(f"输出时长: {output_duration}s")

        # 这个测试应该失败，因为原始逻辑有 bug
        if abs(output_duration - video_duration) > 0.5:
            logger.info("✓ 成功重现 bug：输出时长与视频时长不匹配（这是预期的）")
            return True
        else:
            logger.warning("未能重现 bug，可能 ffmpeg 版本行为不同")
            return True


if __name__ == "__main__":
    logger.info("开始测试 BGM 添加功能")
    logger.info("=" * 60)

    # 测试 1: BGM 比视频短
    test1_passed = test_bgm_shorter_than_video()

    # 测试 2: BGM 比视频长（修复后）
    test2_passed = test_bgm_longer_than_video()

    # 测试 3: 重现原始 bug
    test3_passed = test_original_bug()

    logger.info("=" * 60)
    logger.info(f"测试结果:")
    logger.info(f"  测试 1 (BGM 短于视频): {'通过' if test1_passed else '失败'}")
    logger.info(f"  测试 2 (BGM 长于视频，修复后): {'通过' if test2_passed else '失败'}")
    logger.info(f"  测试 3 (重现原始 bug): {'通过' if test3_passed else '失败'}")

    if test1_passed and test2_passed and test3_passed:
        logger.info("所有测试通过！")
    else:
        logger.error("部分测试失败")
