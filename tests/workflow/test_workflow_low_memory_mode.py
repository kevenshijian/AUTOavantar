"""
Workflow 低显存模式引擎管理测试

测试 AC-226, AC-227, AC-228, AC-229:
- AC-226: 低显存模式按阶段加载模型
- AC-227: 低显存模式阶段完成后卸载模型
- AC-228: 低显存模式任务完成后卸载所有模型
- AC-229: 低显存模式关闭时模型常驻
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


class TestWorkflowLowMemoryMode:
    """Workflow 低显存模式功能测试"""

    def test_workflow_has_low_memory_mode_parameter(self):
        """
        验证 Workflow 有 low_memory_mode 参数
        """
        from business.workflow import DigitalHumanWorkflow

        # 创建 mock 引擎
        mock_tts = MagicMock()
        mock_tts.is_loaded = False
        mock_heygem = MagicMock()
        mock_heygem.is_loaded = False

        workflow = DigitalHumanWorkflow(
            tts_engine=mock_tts,
            heygem_engine=mock_heygem,
            low_memory_mode=True
        )

        # 验证有 low_memory_mode 属性
        assert hasattr(workflow, 'low_memory_mode')
        assert workflow.low_memory_mode is True

    def test_workflow_unloads_tts_after_audio_stage_when_low_memory_on(self):
        """
        AC-227: 低显存模式开启时音频合成完成后卸载 TTS 模型

        Given low_memory_mode=True 且音频合成完成
        When 进入视频合成阶段
        Then TTS 模型被卸载
        """
        from business.workflow import DigitalHumanWorkflow

        # 创建 mock 引擎
        mock_tts = MagicMock()
        mock_tts.is_loaded = True
        mock_tts.unload.return_value = True

        mock_heygem = MagicMock()
        mock_heygem.is_loaded = False
        mock_heygem.load.return_value = True

        workflow = DigitalHumanWorkflow(
            tts_engine=mock_tts,
            heygem_engine=mock_heygem,
            low_memory_mode=True
        )

        # 调用卸载逻辑（模拟音频合成完成后）
        workflow._unload_tts_if_low_memory_mode()

        # 验证 TTS 模型被卸载
        mock_tts.unload.assert_called()

    def test_workflow_keeps_tts_loaded_when_low_memory_off(self):
        """
        AC-229: 低显存模式关闭时 TTS 模型保持常驻

        Given low_memory_mode=False 且音频合成完成
        When 进入视频合成阶段
        Then TTS 模型不被卸载
        """
        from business.workflow import DigitalHumanWorkflow

        # 创建 mock 引擎
        mock_tts = MagicMock()
        mock_tts.is_loaded = True

        mock_heygem = MagicMock()
        mock_heygem.is_loaded = True

        workflow = DigitalHumanWorkflow(
            tts_engine=mock_tts,
            heygem_engine=mock_heygem,
            low_memory_mode=False
        )

        # 调用卸载逻辑（模拟音频合成完成后）
        workflow._unload_tts_if_low_memory_mode()

        # 验证 TTS 模型不被卸载
        mock_tts.unload.assert_not_called()

    def test_workflow_unloads_heygem_after_video_stage_when_low_memory_on(self):
        """
        AC-228: 低显存模式开启时视频合成完成后卸载 HeyGem 模型

        Given low_memory_mode=True 且视频合成完成
        When 任务完成
        Then HeyGem 模型被卸载
        """
        from business.workflow import DigitalHumanWorkflow

        # 创建 mock 引擎
        mock_tts = MagicMock()
        mock_tts.is_loaded = False

        mock_heygem = MagicMock()
        mock_heygem.is_loaded = True
        mock_heygem.unload.return_value = True

        workflow = DigitalHumanWorkflow(
            tts_engine=mock_tts,
            heygem_engine=mock_heygem,
            low_memory_mode=True
        )

        # 调用卸载逻辑（模拟视频合成完成后）
        workflow._cleanup_heygem_gpu()

        # 验证 HeyGem 模型被卸载
        mock_heygem.unload.assert_called()

    def test_workflow_keeps_heygem_loaded_when_low_memory_off(self):
        """
        AC-229: 低显存模式关闭时 HeyGem 模型保持常驻

        Given low_memory_mode=False 且视频合成完成
        When 任务完成
        Then HeyGem 模型不被卸载
        """
        from business.workflow import DigitalHumanWorkflow

        # 创建 mock 引擎
        mock_tts = MagicMock()
        mock_tts.is_loaded = True

        mock_heygem = MagicMock()
        mock_heygem.is_loaded = True

        workflow = DigitalHumanWorkflow(
            tts_engine=mock_tts,
            heygem_engine=mock_heygem,
            low_memory_mode=False
        )

        # 调用卸载逻辑（模拟视频合成完成后）
        workflow._cleanup_heygem_gpu()

        # 验证 HeyGem 模型不被卸载
        mock_heygem.unload.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])