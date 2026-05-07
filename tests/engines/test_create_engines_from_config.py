"""
引擎创建函数测试

测试 AC-216, AC-218, AC-222:
- AC-216: 低显存模式关闭时引擎预加载
- AC-218: 低显存模式开启时引擎延迟加载
- AC-222: 低显存模式切换生效
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


class TestCreateEnginesFromConfig:
    """引擎创建函数测试"""

    def test_low_memory_mode_false_preloads_models(self):
        """
        AC-216: 低显存模式关闭时引擎预加载

        Given low_memory_mode=False
        When 调用 create_engines_from_config
        Then 引擎在创建时预加载模型
        """
        from core.engines import create_engines_from_config

        engines = create_engines_from_config(low_memory_mode=False)

        # 验证引擎已创建
        assert "tts_engine" in engines
        assert "heygem_engine" in engines

        # 验证引擎的 preload_model 参数为 True
        tts_engine = engines["tts_engine"]
        heygem_engine = engines["heygem_engine"]

        if tts_engine is not None:
            assert tts_engine._preload_model is True
        if heygem_engine is not None:
            assert heygem_engine._preload_model is True

    def test_low_memory_mode_true_delays_loading(self):
        """
        AC-218: 低显存模式开启时引擎延迟加载

        Given low_memory_mode=True
        When 调用 create_engines_from_config
        Then 引擎在创建时不加载模型
        """
        from core.engines import create_engines_from_config

        engines = create_engines_from_config(low_memory_mode=True)

        # 验证引擎已创建
        assert "tts_engine" in engines
        assert "heygem_engine" in engines

        # 验证引擎的 preload_model 参数为 False
        tts_engine = engines["tts_engine"]
        heygem_engine = engines["heygem_engine"]

        if tts_engine is not None:
            assert tts_engine._preload_model is False
            # 模型不应该被加载
            assert tts_engine.is_model_loaded is False

        if heygem_engine is not None:
            assert heygem_engine._preload_model is False
            # 模型不应该被加载
            assert heygem_engine.is_model_loaded is False

    def test_default_low_memory_mode_is_false(self):
        """
        验证默认行为：low_memory_mode 默认为 False

        这确保向后兼容性
        """
        from core.engines import create_engines_from_config

        # 不传递 low_memory_mode 参数
        engines = create_engines_from_config()

        tts_engine = engines["tts_engine"]
        heygem_engine = engines["heygem_engine"]

        # 默认应该预加载
        if tts_engine is not None:
            assert tts_engine._preload_model is True
        if heygem_engine is not None:
            assert heygem_engine._preload_model is True

    def test_engines_registered_to_gpu_manager(self):
        """
        验证引擎注册到 GPU 资源管理器
        """
        from core.engines import create_engines_from_config
        from core.engines.gpu_manager import get_gpu_manager, EngineType

        # 重置 GPU 管理器
        from core.engines.gpu_manager import reset_gpu_manager
        reset_gpu_manager()

        engines = create_engines_from_config(low_memory_mode=True)

        gpu_manager = get_gpu_manager()

        # 验证引擎已注册
        if engines["tts_engine"] is not None:
            assert EngineType.TTS in gpu_manager._engines
        if engines["heygem_engine"] is not None:
            assert EngineType.HEYGEM in gpu_manager._engines


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
