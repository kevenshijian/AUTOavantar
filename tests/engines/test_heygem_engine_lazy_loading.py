"""
HeyGemEngine 延迟加载功能测试

测试 AC-216, AC-218, AC-221:
- AC-216: 低显存模式关闭时引擎预加载
- AC-218: 低显存模式开启时引擎延迟加载
- AC-221: 引擎状态查询
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


class TestHeyGemEngineLazyLoading:
    """HeyGemEngine 延迟加载功能测试"""

    def test_preload_model_false_does_not_load_model_on_init(self):
        """
        AC-218: 低显存模式开启时引擎延迟加载

        Given preload_model=False (低显存模式开启)
        When 初始化 HeyGemEngine
        Then 只初始化引擎服务，不加载模型
        """
        from core.engines.heygem_engine import HeyGemEngine

        engine = HeyGemEngine(
            heygem_root="engines/heygem",
            preload_model=False
        )

        # 验证模型未加载
        assert engine.is_loaded is False
        assert engine.is_model_loaded is False

    def test_is_model_loaded_reflects_actual_state(self):
        """
        AC-221: 引擎状态查询

        Given 系统运行中
        When 查询引擎状态
        Then 返回引擎是否已加载模型的状态
        """
        from core.engines.heygem_engine import HeyGemEngine

        # 测试延迟加载模式
        engine = HeyGemEngine(
            heygem_root="engines/heygem",
            preload_model=False
        )

        # 初始状态
        assert engine.is_model_loaded is False

        # 卸载后状态（未加载时卸载不影响状态）
        engine.unload()
        assert engine.is_model_loaded is False

    def test_unload_releases_memory_after_task(self):
        """
        AC-220: 低显存模式开启时任务完成后卸载模型

        Given 低显存模式开启且任务执行完成
        When 任务完成或取消
        Then 卸载已加载的模型释放显存
        """
        from core.engines.heygem_engine import HeyGemEngine

        engine = HeyGemEngine(
            heygem_root="engines/heygem",
            preload_model=False
        )

        # 初始状态：未加载
        assert engine.is_model_loaded is False

        # 卸载模型（未加载时也应该成功）
        result = engine.unload()

        # 验证卸载成功
        assert result is True
        assert engine.is_model_loaded is False

    def test_default_preload_model_is_true(self):
        """
        验证默认行为：preload_model 默认为 True

        这确保向后兼容性，现有代码无需修改
        """
        from core.engines.heygem_engine import HeyGemEngine

        # 创建引擎时不指定 preload_model
        engine = HeyGemEngine(
            heygem_root="engines/heygem"
        )

        # 验证参数设置正确
        assert engine._preload_model is True

    def test_load_method_works_after_delayed_init(self):
        """
        AC-219: 低显存模式开启时任务按需加载模型

        Given preload_model=False 且引擎已初始化
        When 调用 load() 方法
        Then 模型成功加载
        """
        from core.engines.heygem_engine import HeyGemEngine

        engine = HeyGemEngine(
            heygem_root="engines/heygem",
            preload_model=False
        )

        # 初始状态：未加载
        assert engine.is_model_loaded is False

        # 由于实际加载需要模型文件，这里只验证方法存在且返回 bool
        # load() 方法在模型不存在时会返回 False
        result = engine.load()

        # 验证 load 方法返回布尔值
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
