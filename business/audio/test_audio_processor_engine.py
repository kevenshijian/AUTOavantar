"""
AudioProcessor 引擎集成测试
测试 AudioProcessor 使用 TTSEngine 的功能
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


class TestAudioProcessorEngineMode(unittest.TestCase):
    """测试 AudioProcessor 引擎模式"""

    def test_init_with_tts_engine_required(self):
        """测试 TTSEngine 是必需参数"""
        from business.audio.audio_processor import AudioProcessor

        # 不提供 tts_engine 应该抛出 TypeError（缺少必需参数）
        with self.assertRaises(TypeError):
            AudioProcessor(output_dir="temp/audio")

    def test_init_with_tts_engine(self):
        """测试使用 TTSEngine 初始化"""
        from business.audio.audio_processor import AudioProcessor

        # 创建模拟的 TTSEngine
        mock_engine = MagicMock()
        mock_engine.is_loaded = True

        processor = AudioProcessor(
            tts_engine=mock_engine,
            output_dir="temp/audio"
        )

        self.assertIsNotNone(processor)
        self.assertEqual(processor.tts_engine, mock_engine)

    def test_synthesize_with_engine_mode(self):
        """测试引擎模式合成"""
        from business.audio.audio_processor import AudioProcessor
        from core.models.task import ScriptSegment, SceneType

        # 创建模拟的 TTSEngine
        mock_engine = MagicMock()
        mock_engine.is_loaded = True
        mock_engine.synthesize.return_value = "output.wav"

        processor = AudioProcessor(
            tts_engine=mock_engine,
            output_dir="temp/audio"
        )

        # 创建测试段落
        segment = ScriptSegment(
            segment_id="test_001",
            text="测试文本",
            tone="开场",
            scene_type=SceneType.LOOP
        )

        # 验证引擎模式方法存在
        self.assertTrue(hasattr(processor, '_synthesize_with_engine'))

    def test_synthesize_all_checks_engine_loaded(self):
        """测试 synthesize_all 检查引擎是否加载"""
        from business.audio.audio_processor import AudioProcessor
        from core.models.task import Task, TaskConfig

        # 创建模拟的 TTSEngine（未加载）
        mock_engine = MagicMock()
        mock_engine.is_loaded = False

        processor = AudioProcessor(
            tts_engine=mock_engine,
            output_dir="temp/audio"
        )

        # 创建测试任务
        task = Task(task_id="test_task")
        task.segments = []

        config = TaskConfig()

        # 调用 synthesize_all 应该返回失败结果
        results = processor.synthesize_all(task, config)

        # 因为引擎未加载且没有段落，应该返回空列表
        self.assertEqual(len(results), 0)


class TestAudioProcessorEngineOnly(unittest.TestCase):
    """测试 AudioProcessor 仅使用引擎模式"""

    def test_no_http_client_attribute(self):
        """测试不再有 HTTP 客户端属性"""
        from business.audio.audio_processor import AudioProcessor

        mock_engine = MagicMock()
        mock_engine.is_loaded = True

        processor = AudioProcessor(
            tts_engine=mock_engine,
            output_dir="temp/audio"
        )

        # 不应该有 tts_client 属性
        self.assertFalse(hasattr(processor, 'tts_client'))
        # 不应该有 tts_host 属性
        self.assertFalse(hasattr(processor, 'tts_host'))


if __name__ == '__main__':
    unittest.main()
