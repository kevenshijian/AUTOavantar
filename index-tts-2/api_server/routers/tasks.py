"""
任务查询路由
提供任务状态和队列位置查询接口
"""

import logging

from fastapi import APIRouter, HTTPException

from api_server.models.tts import QueueStatusResponse, TaskDetailResponse

logger = logging.getLogger("indextts-api.tasks")

router = APIRouter()

_task_queue = None  # type: ignore


def set_task_queue(task_queue) -> None:
    """注入任务队列实例"""
    global _task_queue
    _task_queue = task_queue


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str):
    """
    查询任务详情

    返回任务状态、音频 URL、耗时等信息。
    """
    if _task_queue is None:
        raise HTTPException(status_code=503, detail="服务正在启动中")

    task = _task_queue.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    # 如果任务已完成（成功或失败），清理临时音频文件
    if task.status.value in ("completed", "failed"):
        _task_queue.cleanup_task_temp_audio(task_id)

    return TaskDetailResponse(
        task_id=task.task_id,
        status=task.status.value,
        audio_url=task.audio_url,
        duration_sec=task.duration_sec,
        inference_time_sec=task.inference_time_sec,
        error_message=task.error_message,
        created_at=task.created_at,
        completed_at=task.completed_at,
    )


@router.get("/{task_id}/status", response_model=QueueStatusResponse)
async def get_queue_status(task_id: str):
    """
    查询任务排队位置

    返回当前在队列中的位置和预估等待时间。
    """
    if _task_queue is None:
        raise HTTPException(status_code=503, detail="服务正在启动中")

    task = _task_queue.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    position = _task_queue.get_queue_position(task_id)
    if position is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    return QueueStatusResponse(
        task_id=task.task_id,
        queue_position=position,
    )
