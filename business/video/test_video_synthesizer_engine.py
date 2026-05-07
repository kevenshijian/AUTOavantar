"""
VideoSynthesizer 引擎集成测试
测试 VideoSynthesizer 使用 HeyGemEngine 的功能
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


class TestVideoSynthesizerEngineMode(unittest.TestCase):
    """测试 VideoSynthesizer 引擎模式"""

    def test_init_with_heygem_engine_required(self):
        """测试 HeyGemEngine 是必需参数"""
        from business.video.video_synthesizer import VideoSynthesizer

        # 不提供 heygem_engine 应该抛出 TypeError（缺少必需参数）
        with self.assertRaises(TypeError):
            VideoSynthesizer(output_dir="temp/video")

    def test_init_with_heygem_engine(self):
        """测试使用 HeyGemEngine 初始化"""
        from business.video.video_synthesizer import VideoSynthesizer

        # 创建模拟的 HeyGemEngine
        mock_engine = MagicMock()
        mock_engine.is_loaded = True

        synthesizer = VideoSynthesizer(
            heygem_engine=mock_engine,
            output_dir="temp/video"
        )

        self.assertIsNotNone(synthesizer)
        self.assertEqual(synthesizer.heygem_engine, mock_engine)

    def test_run_heygem_inference_engine_mode_method_exists(self):
        """测试引擎模式推理方法存在"""
        from business.video.video_synthesizer import VideoSynthesizer

        # 创建模拟的 HeyGemEngine
        mock_engine = MagicMock()
        mock_engine.is_loaded = True

        synthesizer = VideoSynthesizer(
            heygem_engine=mock_engine,
            output_dir="temp/video"
        )

        # 验证引擎模式方法存在
        self.assertTrue(hasattr(synthesizer, '_run_heygem_inference_engine'))


class TestVideoSynthesizerEngineOnly(unittest.TestCase):
    """测试 VideoSynthesizer 仅使用引擎模式"""

    def test_no_http_client_attribute(self):
        """测试不再有 HTTP 客户端属性"""
        from business.video.video_synthesizer import VideoSynthesizer

        mock_engine = MagicMock()
        mock_engine.is_loaded = True

        synthesizer = VideoSynthesizer(
            heygem_engine=mock_engine,
            output_dir="temp/video"
        )

        # 不应该有 heygem_client 属性
        self.assertFalse(hasattr(synthesizer, 'heygem_client'))
        # 不应该有 heygem_host 属性
        self.assertFalse(hasattr(synthesizer, 'heygem_host'))


if __name__ == '__main__':
    unittest.main()
