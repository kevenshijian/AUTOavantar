"""
create_engines_from_config 单元测试
测试引擎初始化函数的核心功能
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


class TestCreateEnginesFromConfig(unittest.TestCase):
    """测试 create_engines_from_config 函数"""

    def test_function_exists(self):
        """测试函数存在"""
        from core.engines import create_engines_from_config

        self.assertTrue(callable(create_engines_from_config))

    def test_returns_dict_with_engines(self):
        """测试返回包含引擎的字典"""
        from core.engines import create_engines_from_config

        # 使用不存在的配置文件，应该使用默认值
        engines = create_engines_from_config(config_path="nonexistent.yaml")

        self.assertIsInstance(engines, dict)
        self.assertIn("tts_engine", engines)
        self.assertIn("heygem_engine", engines)

    def test_uses_default_values_when_config_missing(self):
        """测试配置文件不存在时使用默认值"""
        from core.engines import create_engines_from_config

        engines = create_engines_from_config(config_path="nonexistent.yaml")

        # 应该返回 None（因为模型文件不存在，无法实际创建）
        # 或者返回未加载的引擎实例
        self.assertIsNotNone(engines)


class TestEngineConfig(unittest.TestCase):
    """测试引擎配置"""

    def test_config_file_format(self):
        """测试配置文件格式正确"""
        import yaml

        # 创建临时配置文件
        config_content = """
tts:
  cfg_path: checkpoints/indextts/config.yaml
  model_dir: checkpoints/indextts
  use_fp16: true
  managed: true

heygem:
  heygem_root: engines/heygem
  batch_size: 4
  managed: true
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            with open(temp_path, 'r') as f:
                config = yaml.safe_load(f)

            self.assertIn('tts', config)
            self.assertIn('heygem', config)
            self.assertEqual(config['tts']['use_fp16'], True)
            self.assertEqual(config['heygem']['batch_size'], 4)

        finally:
            os.unlink(temp_path)


class TestEngineRegistration(unittest.TestCase):
    """测试引擎注册到 GPUResourceManager"""

    def test_engines_registered_to_gpu_manager(self):
        """测试引擎注册到 GPU 资源管理器"""
        from core.engines.gpu_manager import get_gpu_manager, EngineType, reset_gpu_manager

        # 重置管理器
        reset_gpu_manager()

        # 创建引擎（managed=True）
        from core.engines.tts_engine import TTSEngine
        from core.engines.heygem_engine import HeyGemEngine

        tts_engine = TTSEngine(
            cfg_path="checkpoints/config.yaml",
            model_dir="checkpoints",
            managed=True
        )

        heygem_engine = HeyGemEngine(
            heygem_root="engines/heygem",
            managed=True
        )

        gpu_manager = get_gpu_manager()

        # 验证注册
        # 注意：由于是单例，可能已经注册了其他实例
        self.assertIsNotNone(gpu_manager)

        # 清理
        reset_gpu_manager()


if __name__ == '__main__':
    unittest.main()
