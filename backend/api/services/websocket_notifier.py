"""
WebSocket 通知集成模块
将工作流服务的任务状态变化推送到 WebSocket 客户端
"""

import logging
from typing import Optional
from api.services.workflow_service import WorkflowService, TaskCallback
from api.routers.websocket import manager

logger = logging.getLogger("websocket_notifier")


class WebSocketNotifier:
    """WebSocket 通知器"""

    def __init__(self):
        self._workflow_service: Optional[WorkflowService] = None

    async def register_with_service(self, workflow_service: WorkflowService):
        """
        注册到工作流服务

        为所有任务注册 WebSocket 通知回调
        """
        self._workflow_service = workflow_service

        # 设置全局回调处理新任务
        # 注意：实际使用时，需要在创建任务时注册回调
        logger.info("WebSocket 通知器已注册到工作流服务")

    def create_task_callback(self, task_id: str) -> TaskCallback:
        """
        创建任务的 WebSocket 回调

        Args:
            task_id: 任务ID

        Returns:
            任务回调对象
        """
        async def on_status_change(task_id: str, task):
            """状态变化回调"""
            logger.info(f"on_status_change 被调用: task_id={task_id}, status={task.status}")
            await manager.broadcast_status_update(
                task_id=task_id,
                status=task.status.value if hasattr(task.status, 'value') else str(task.status),
                progress=task.progress,
                stage=task.current_stage,
                message=f"任务状态更新: {task.status}"
            )
            logger.info(f"on_status_change 完成: task_id={task_id}")

        async def on_progress(task_id: str, progress: float, stage: str):
            """进度更新回调"""
            logger.info(f"on_progress 被调用: task_id={task_id}, progress={progress}, stage={stage}")
            await manager.broadcast_status_update(
                task_id=task_id,
                status="processing",
                progress=progress,
                stage=stage,
                message=f"处理中: {stage}"
            )
            logger.info(f"on_progress 完成: task_id={task_id}")

        async def on_complete(task_id: str, result):
            """任务完成回调"""
            logger.info(f"on_complete 被调用: task_id={task_id}")
            await manager.broadcast_status_update(
                task_id=task_id,
                status="completed",
                progress=100.0,
                stage="completed",
                message="任务完成",
                output_path=result.output_path if hasattr(result, 'output_path') else None
            )
            logger.info(f"on_complete 完成: task_id={task_id}")

        async def on_error(task_id: str, error_message: str):
            """任务错误回调"""
            logger.info(f"on_error 被调用: task_id={task_id}, error={error_message}")
            await manager.broadcast_status_update(
                task_id=task_id,
                status="failed",
                progress=0.0,
                stage="failed",
                message=f"任务失败: {error_message}"
            )
            logger.info(f"on_error 完成: task_id={task_id}")

        return TaskCallback(
            on_status_change=on_status_change,
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error
        )


# 全局通知器实例
notifier = WebSocketNotifier()


async def notify_task_update(
    task_id: str,
    status: str,
    progress: float,
    stage: str = "",
    message: str = "",
    output_path: str = None
):
    """
    通知任务更新

    供其他模块直接调用

    Args:
        task_id: 任务ID
        status: 任务状态
        progress: 进度 (0-100)
        stage: 当前阶段
        message: 消息
        output_path: 输出路径（可选）
    """
    data = {
        "type": "status_update",
        "task_id": task_id,
        "status": status,
        "progress": progress,
        "stage": stage,
        "message": message,
        "timestamp": __import__('datetime').datetime.now().isoformat()
    }

    if output_path:
        data["output_path"] = output_path

    await manager.broadcast_to_task(task_id, data)


async def register_task_websocket(task_id: str, workflow_service: WorkflowService):
    """
    为任务注册 WebSocket 通知

    在创建任务后调用，将 WebSocket 通知回调注册到任务

    Args:
        task_id: 任务ID
        workflow_service: 工作流服务实例
    """
    callback = notifier.create_task_callback(task_id)
    workflow_service.register_callback(task_id, callback)
    logger.info(f"任务 {task_id} 的 WebSocket 通知已注册")
