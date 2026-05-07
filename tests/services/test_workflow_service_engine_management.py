"""
WorkflowService 引擎管理测试

测试 AC-226, AC-227, AC-228, AC-229:
- AC-226: 低显存模式按阶段加载模型（Service 层不预加载）
- AC-227: 低显存模式阶段完成后卸载模型（由 Workflow 管理）
- AC-228: 低显存模式任务完成后卸载所有模型（由 Workflow 管理）
- AC-229: 低显存模式关闭时模型常驻（由 Workflow 管理）

CR-026 变更：
- WorkflowService 不再在任务开始时预加载引擎
- WorkflowService 不再在任务完成后统一卸载引擎
- 引擎的按阶段加载/卸载由 Workflow 自行管理
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录和 backend 目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
backend_path = os.path.join(project_root, "backend")
sys.path.insert(0, backend_path)


class TestWorkflowServiceEngineManagementCR026:
    """WorkflowService 引擎管理测试 - CR-026 按阶段加载优化"""

    def test_ensure_engines_loaded_does_not_preload_engines(self):
        """
        AC-226: Service 层不预加载引擎

        Given low_memory_mode=True 且引擎未加载
        When 调用 _ensure_engines_loaded()
        Then 不调用引擎的 load() 方法（由 Workflow 按阶段管理）
        """
        from api.services.workflow_service import WorkflowService

        # 创建 mock 引擎
        mock_tts = MagicMock()
        mock_tts.is_model_loaded = False
        mock_tts.load.return_value = True

        mock_heygem = MagicMock()
        mock_heygem.is_model_loaded = False
        mock_heygem.load.return_value = True

        service = WorkflowService(
            tts_engine=mock_tts,
            heygem_engine=mock_heygem,
            low_memory_mode=True
        )

        # 调用 _ensure_engines_loaded 方法
        service._ensure_engines_loaded()

        # CR-026: Service 层不再预加载引擎
        # load 不应该被调用（由 Workflow 按阶段自行管理）
        mock_tts.load.assert_not_called()
        mock_heygem.load.assert_not_called()

    def test_release_engines_after_task_does_not_unload_engines(self):
        """
        AC-227, AC-228: Service 层不统一卸载引擎

        Given low_memory_mode=True 且任务完成
        When 调用 _release_engines_after_task()
        Then 不调用引擎的 unload() 方法（由 Workflow 按阶段管理）
        """
        from api.services.workflow_service import WorkflowService

        # 创建 mock 引擎
        mock_tts = MagicMock()
        mock_tts.is_model_loaded = True
        mock_tts.unload.return_value = True

        mock_heygem = MagicMock()
        mock_heygem.is_model_loaded = True
        mock_heygem.unload.return_value = True

        service = WorkflowService(
            tts_engine=mock_tts,
            heygem_engine=mock_heygem,
            low_memory_mode=True
        )

        # 调用 _release_engines_after_task 方法
        service._release_engines_after_task()

        # CR-026: Service 层不再统一卸载引擎
        # unload 不应该被调用（由 Workflow 按阶段自行管理）
        mock_tts.unload.assert_not_called()
        mock_heygem.unload.assert_not_called()

    def test_ensure_engines_loaded_does_not_preload_when_low_memory_off(self):
        """
        AC-229: 低显存模式关闭时 Service 层也不干预

        Given low_memory_mode=False
        When 调用 _ensure_engines_loaded()
        Then 不调用引擎的 load() 方法（引擎已在初始化时预加载）
        """
        from api.services.workflow_service import WorkflowService

        # 创建 mock 引擎
        mock_tts = MagicMock()
        mock_tts.is_model_loaded = True  # 低显存模式关闭时，引擎已在初始化时加载

        mock_heygem = MagicMock()
        mock_heygem.is_model_loaded = True

        service = WorkflowService(
            tts_engine=mock_tts,
            heygem_engine=mock_heygem,
            low_memory_mode=False
        )

        # 调用 _ensure_engines_loaded 方法
        service._ensure_engines_loaded()

        # 低显存模式关闭时，引擎已在初始化时预加载，不需要再次加载
        mock_tts.load.assert_not_called()
        mock_heygem.load.assert_not_called()

    def test_release_engines_after_task_does_not_unload_when_low_memory_off(self):
        """
        AC-229: 低显存模式关闭时模型保持常驻

        Given low_memory_mode=False 且任务完成
        When 调用 _release_engines_after_task()
        Then 不调用引擎的 unload() 方法
        """
        from api.services.workflow_service import WorkflowService

        # 创建 mock 引擎
        mock_tts = MagicMock()
        mock_tts.is_model_loaded = True

        mock_heygem = MagicMock()
        mock_heygem.is_model_loaded = True

        service = WorkflowService(
            tts_engine=mock_tts,
            heygem_engine=mock_heygem,
            low_memory_mode=False
        )

        # 调用 _release_engines_after_task 方法
        service._release_engines_after_task()

        # 低显存模式关闭时，模型保持常驻
        mock_tts.unload.assert_not_called()
        mock_heygem.unload.assert_not_called()

    def test_workflow_service_has_low_memory_mode_property(self):
        """
        验证 WorkflowService 有 low_memory_mode 属性
        """
        from api.services.workflow_service import WorkflowService

        # 创建 mock 引擎
        mock_tts = MagicMock()
        mock_heygem = MagicMock()

        service = WorkflowService(
            tts_engine=mock_tts,
            heygem_engine=mock_heygem
        )

        # 验证有 low_memory_mode 属性
        assert hasattr(service, 'low_memory_mode')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])