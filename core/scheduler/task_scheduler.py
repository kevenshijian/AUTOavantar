"""
任务调度器模块
"""

import logging
import threading
import time
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STOPPED = "stopped"
    TIMEOUT = "timeout"


@dataclass
class QueuedTask:
    """队列任务"""
    task_id: str
    config: Dict
    created_at: datetime
    status: TaskStatus = TaskStatus.PENDING
    timeout: float = 3600.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    is_priority: bool = False


class SimpleTaskScheduler:
    """
    简单任务调度器

    特点：
    - 单线程顺序执行
    - FIFO 队列（按创建时间排序）
    - 支持插队功能
    - 支持任务超时
    """

    def __init__(self):
        self._queue: List[QueuedTask] = []
        self._priority_task: Optional[QueuedTask] = None
        self._current_task: Optional[QueuedTask] = None
        self._tasks: Dict[str, QueuedTask] = {}
        self._executor: Optional[Callable] = None
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._cancel_event = threading.Event()

    def set_executor(self, executor: Callable):
        """设置任务执行器"""
        self._executor = executor

    def start(self):
        """启动调度器"""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._cancel_event.clear()
            self._worker_thread = threading.Thread(target=self._run_loop, daemon=True)
            self._worker_thread.start()
            logger.info("SimpleTaskScheduler 已启动")

    def stop(self):
        """停止调度器"""
        with self._lock:
            self._running = False
            self._stop_event.set()
            self._cancel_event.set()
            if self._worker_thread:
                self._worker_thread.join(timeout=5.0)
            logger.info("SimpleTaskScheduler 已停止")

    def is_running(self) -> bool:
        """检查调度器是否运行中"""
        return self._running

    def submit(self, task_id: str, config: Dict, timeout: float = 3600.0) -> bool:
        """
        提交任务到队列

        Args:
            task_id: 任务 ID
            config: 任务配置
            timeout: 超时时间（秒）

        Returns:
            是否成功提交
        """
        with self._lock:
            if task_id in self._tasks:
                existing_task = self._tasks[task_id]
                # 只拒绝正在运行或排队的任务，允许重新提交已取消/失败/完成的任务
                if existing_task.status in [TaskStatus.RUNNING]:
                    logger.warning(f"任务 {task_id} 正在运行中，无法重新提交")
                    return False
                if existing_task.status in [TaskStatus.PENDING]:
                    logger.warning(f"任务 {task_id} 已在队列中，无法重复提交")
                    return False

                # 清理旧任务状态
                del self._tasks[task_id]
                if task_id in [t.task_id for t in self._queue]:
                    self._queue = [t for t in self._queue if t.task_id != task_id]

            task = QueuedTask(
                task_id=task_id,
                config=config,
                created_at=datetime.now(),
                timeout=timeout
            )
            self._queue.append(task)
            self._tasks[task_id] = task
            logger.info(f"任务 {task_id} 已提交到队列")
            return True

    def submit_priority(self, task_id: str, config: Dict, timeout: float = 3600.0) -> bool:
        """
        提交插队任务

        Args:
            task_id: 任务 ID
            config: 任务配置
            timeout: 超时时间（秒）

        Returns:
            是否成功提交
        """
        with self._lock:
            if task_id in self._tasks:
                existing_task = self._tasks[task_id]
                if existing_task.status in [TaskStatus.RUNNING]:
                    logger.warning(f"任务 {task_id} 正在运行中，无法重新提交")
                    return False

                # 清理旧任务状态
                del self._tasks[task_id]
                if self._priority_task and self._priority_task.task_id == task_id:
                    self._priority_task = None
                if task_id in [t.task_id for t in self._queue]:
                    self._queue = [t for t in self._queue if t.task_id != task_id]

            task = QueuedTask(
                task_id=task_id,
                config=config,
                created_at=datetime.now(),
                timeout=timeout,
                is_priority=True
            )
            self._priority_task = task
            self._tasks[task_id] = task
            logger.info(f"插队任务 {task_id} 已提交")
            return True

    def set_priority(self, task_id: str) -> bool:
        """
        将已存在的任务设置为插队任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功设置
        """
        with self._lock:
            if task_id not in self._tasks:
                logger.warning(f"任务 {task_id} 不存在")
                return False

            task = self._tasks[task_id]
            if task.status != TaskStatus.PENDING:
                logger.warning(f"任务 {task_id} 不是待执行状态")
                return False

            # 如果已有插队任务，取消其插队标记
            if self._priority_task and self._priority_task.task_id != task_id:
                self._priority_task.is_priority = False

            # 设置新的插队任务
            task.is_priority = True
            self._priority_task = task
            logger.info(f"任务 {task_id} 已设为插队任务")
            return True

    def cancel(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功取消
        """
        with self._lock:
            if task_id not in self._tasks:
                return False

            task = self._tasks[task_id]

            if task.status == TaskStatus.RUNNING:
                # 正在运行的任务，设置取消标志
                self._cancel_event.set()
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                logger.info(f"运行中任务 {task_id} 已请求取消")
                return True

            if task.status == TaskStatus.PENDING:
                # 从队列中移除
                self._queue = [t for t in self._queue if t.task_id != task_id]
                if self._priority_task and self._priority_task.task_id == task_id:
                    self._priority_task = None
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                logger.info(f"排队任务 {task_id} 已取消")
                return True

            logger.warning(f"任务 {task_id} 状态为 {task.status}，无法取消")
            return False

    def get_status(self, task_id: str) -> Optional[Dict]:
        """
        获取任务状态

        Args:
            task_id: 任务 ID

        Returns:
            任务状态字典，如果任务不存在则返回 None
        """
        with self._lock:
            if task_id not in self._tasks:
                return None

            task = self._tasks[task_id]
            return {
                "task_id": task.task_id,
                "status": task.status.value,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "error_message": task.error_message,
                "is_priority": task.is_priority
            }

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        获取任务状态（别名方法，兼容旧接口）

        Args:
            task_id: 任务 ID

        Returns:
            任务状态字典，如果任务不存在则返回 None
        """
        return self.get_status(task_id)

    def get_all_status(self) -> Dict:
        """
        获取所有任务状态

        Returns:
            包含所有任务状态的字典
        """
        with self._lock:
            return {
                "running": self._running,
                "current_task": self._current_task.task_id if self._current_task else None,
                "queue_size": len(self._queue),
                "priority_task": self._priority_task.task_id if self._priority_task else None,
                "pending_tasks": [t.task_id for t in self._queue if t.status == TaskStatus.PENDING]
            }

    def _run_loop(self):
        """主循环"""
        while self._running:
            try:
                self._execute_next_task()
            except Exception as e:
                logger.error(f"任务执行异常: {e}")

            time.sleep(0.1)

    def _execute_next_task(self):
        """执行下一个任务"""
        with self._lock:
            if self._priority_task:
                task = self._priority_task
                self._priority_task = None
            elif self._queue:
                task = self._queue.pop(0)
            else:
                return

            self._current_task = task
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self._cancel_event.clear()

        logger.info(f"开始执行任务 {task.task_id}")

        timeout_occurred = False
        timeout_timer = None

        def timeout_handler():
            nonlocal timeout_occurred
            timeout_occurred = True
            self._cancel_event.set()
            with self._lock:
                if task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.TIMEOUT
                    task.error_message = f"任务超时 ({task.timeout}s)"
                    task.completed_at = datetime.now()
                    logger.warning(f"任务 {task.task_id} 执行超时")

        if task.timeout and task.timeout > 0:
            timeout_timer = threading.Timer(task.timeout, timeout_handler)
            timeout_timer.start()

        try:
            if self._executor and not timeout_occurred:
                self._executor(task.task_id, task.config)

            if timeout_timer:
                timeout_timer.cancel()

            with self._lock:
                if task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now()
                    logger.info(f"任务 {task.task_id} 执行完成")
                elif task.status == TaskStatus.CANCELLED:
                    logger.info(f"任务 {task.task_id} 已取消")

        except Exception as e:
            if timeout_timer:
                timeout_timer.cancel()

            with self._lock:
                if not timeout_occurred:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                    task.completed_at = datetime.now()
                    logger.error(f"任务 {task.task_id} 执行失败: {e}")

        finally:
            with self._lock:
                self._current_task = None
