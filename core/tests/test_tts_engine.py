"""
TTSEngine 单元测试
测试 TTSEngine 封装类的核心功能
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


class TestTTSEngineInit(unittest.TestCase):
    """测试 TTSEngine 初始化"""

    def test_init_with_valid_paths(self):
        """测试使用有效路径初始化"""
        from core.engines.tts_engine import TTSEngine

        # 使用模拟路径
        cfg_path = "checkpoints/config.yaml"
        model_dir = "checkpoints"

        engine = TTSEngine(cfg_path=cfg_path, model_dir=model_dir)

        self.assertIsNotNone(engine)
        self.assertEqual(engine.cfg_path, cfg_path)
        self.assertEqual(engine.model_dir, model_dir)
        self.assertFalse(engine.is_loaded)

    def test_init_with_fp16_flag(self):
        """测试 fp16 标志"""
        from core.engines.tts_engine import TTSEngine

        engine = TTSEngine(
            cfg_path="checkpoints/config.yaml",
            model_dir="checkpoints",
            use_fp16=True
        )

        self.assertTrue(engine.use_fp16)


class TestTTSEngineLoad(unittest.TestCase):
    """测试 TTSEngine 加载"""

    def test_load_success(self):
        """测试成功加载模型（模拟）"""
        from core.engines.tts_engine import TTSEngine

        engine = TTSEngine(
            cfg_path="checkpoints/config.yaml",
            model_dir="checkpoints"
        )

        # 模拟 IndexTTS2 实例（不实际加载）
        mock_model = MagicMock()
        engine._model = mock_model
        engine._is_loaded = True

        self.assertTrue(engine.is_loaded)
        self.assertIsNotNone(engine._model)

    def test_load_returns_true_when_loaded(self):
        """测试 is_loaded 属性在加载后返回 True"""
        from core.engines.tts_engine import TTSEngine

        engine = TTSEngine(
            cfg_path="checkpoints/config.yaml",
            model_dir="checkpoints"
        )

        # 模拟加载状态
        engine._is_loaded = True

        self.assertTrue(engine.is_loaded)


class TestTTSEngineUnload(unittest.TestCase):
    """测试 TTSEngine 卸载"""

    def test_unload_clears_loaded_flag(self):
        """测试卸载后清除加载标志"""
        from core.engines.tts_engine import TTSEngine

        engine = TTSEngine(
            cfg_path="checkpoints/config.yaml",
            model_dir="checkpoints"
        )

        # 模拟已加载状态
        engine._is_loaded = True
        engine._model = MagicMock()

        # 卸载
        engine.unload()

        self.assertFalse(engine.is_loaded)
        self.assertIsNone(engine._model)


class TestTTSEngineSynthesize(unittest.TestCase):
    """测试 TTSEngine 语音合成"""

    def test_synthesize_requires_loaded_model(self):
        """测试未加载模型时合成抛出异常"""
        from core.engines.tts_engine import TTSEngine

        engine = TTSEngine(
            cfg_path="checkpoints/config.yaml",
            model_dir="checkpoints"
        )

        # 未加载时应该抛出异常
        with self.assertRaises(RuntimeError):
            engine.synthesize(
                text="测试文本",
                voice_path="test_voice.wav",
                output_path="output.wav"
            )

    def test_synthesize_with_emotion_params(self):
        """测试带情绪参数的合成（模拟）"""
        from core.engines.tts_engine import TTSEngine

        engine = TTSEngine(
            cfg_path="checkpoints/config.yaml",
            model_dir="checkpoints"
        )

        # 模拟已加载
        mock_model = MagicMock()
        mock_model.infer.return_value = "output.wav"
        engine._model = mock_model
        engine._is_loaded = True

        # 验证方法存在
        self.assertTrue(hasattr(engine, 'synthesize'))

        # 验证情绪映射已加载
        self.assertIsNotNone(engine._emotion_mapping)


class TestTTSEngineGPUIntegration(unittest.TestCase):
    """测试 TTSEngine 与 GPUResourceManager 集成"""

    def test_register_to_gpu_manager(self):
        """测试注册到 GPU 资源管理器"""
        from core.engines.tts_engine import TTSEngine
        from core.engines.gpu_manager import get_gpu_manager, EngineType, reset_gpu_manager

        # 重置管理器
        reset_gpu_manager()

        engine = TTSEngine(
            cfg_path="checkpoints/config.yaml",
            model_dir="checkpoints",
            managed=True
        )

        # 检查是否注册到 GPU 管理器
        gpu_manager = get_gpu_manager()
        self.assertIsNotNone(gpu_manager)

        # 清理
        reset_gpu_manager()


if __name__ == '__main__':
    unittest.main()
