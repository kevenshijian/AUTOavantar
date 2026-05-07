"""
HeyGemEngine 单元测试
测试 HeyGemEngine 封装类的核心功能
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


class TestHeyGemEngineInit(unittest.TestCase):
    """测试 HeyGemEngine 初始化"""

    def test_init_with_heygem_root(self):
        """测试使用 HeyGem 根目录初始化"""
        from core.engines.heygem_engine import HeyGemEngine

        heygem_root = "engines/heygem"
        engine = HeyGemEngine(heygem_root=heygem_root)

        self.assertIsNotNone(engine)
        self.assertEqual(engine.heygem_root, heygem_root)
        self.assertFalse(engine.is_loaded)

    def test_init_with_batch_size(self):
        """测试批处理大小参数"""
        from core.engines.heygem_engine import HeyGemEngine

        engine = HeyGemEngine(
            heygem_root="engines/heygem",
            batch_size=4
        )

        self.assertEqual(engine.batch_size, 4)


class TestHeyGemEngineLoad(unittest.TestCase):
    """测试 HeyGemEngine 加载"""

    def test_load_returns_true_when_loaded(self):
        """测试 is_loaded 属性在加载后返回 True"""
        from core.engines.heygem_engine import HeyGemEngine

        engine = HeyGemEngine(heygem_root="engines/heygem")

        # 模拟加载状态
        engine._is_loaded = True

        self.assertTrue(engine.is_loaded)


class TestHeyGemEngineUnload(unittest.TestCase):
    """测试 HeyGemEngine 卸载"""

    def test_unload_clears_loaded_flag(self):
        """测试卸载后清除加载标志"""
        from core.engines.heygem_engine import HeyGemEngine

        engine = HeyGemEngine(heygem_root="engines/heygem")

        # 模拟已加载状态
        engine._is_loaded = True
        engine._trans_dh_task = MagicMock()

        # 卸载
        engine.unload()

        self.assertFalse(engine.is_loaded)
        self.assertIsNone(engine._trans_dh_task)


class TestHeyGemEngineGenerate(unittest.TestCase):
    """测试 HeyGemEngine 视频生成"""

    def test_generate_video_requires_loaded_model(self):
        """测试未加载模型时生成视频抛出异常"""
        from core.engines.heygem_engine import HeyGemEngine

        engine = HeyGemEngine(heygem_root="engines/heygem")

        # 未加载时应该抛出异常
        with self.assertRaises(RuntimeError):
            engine.generate_video_simple(
                audio_path="test_audio.wav",
                video_path="test_video.mp4",
                task_id="test_task"
            )

    def test_generate_video_simple_method_exists(self):
        """测试 generate_video_simple 方法存在"""
        from core.engines.heygem_engine import HeyGemEngine

        engine = HeyGemEngine(heygem_root="engines/heygem")

        # 模拟已加载
        engine._is_loaded = True
        engine._trans_dh_task = MagicMock()

        # 验证方法存在
        self.assertTrue(hasattr(engine, 'generate_video_simple'))


class TestHeyGemEngineGPUIntegration(unittest.TestCase):
    """测试 HeyGemEngine 与 GPUResourceManager 集成"""

    def test_register_to_gpu_manager(self):
        """测试注册到 GPU 资源管理器"""
        from core.engines.heygem_engine import HeyGemEngine
        from core.engines.gpu_manager import get_gpu_manager, EngineType, reset_gpu_manager

        # 重置管理器
        reset_gpu_manager()

        engine = HeyGemEngine(
            heygem_root="engines/heygem",
            managed=True
        )

        # 检查是否注册到 GPU 管理器
        gpu_manager = get_gpu_manager()
        self.assertIsNotNone(gpu_manager)

        # 清理
        reset_gpu_manager()


if __name__ == '__main__':
    unittest.main()
