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

from .task_queue import PriorityTaskQueue, TaskPriority

logger = logging.getLogger(__name__)


class WorkerStatus(Enum):
    """工作线程状态"""
    IDLE = "idle"
    BUSY = "busy"
    PAUSED = "paused"
    STOPPED = "stopped"


class TaskControlCommand(Enum):
    """任务控制命令"""
    NONE = "none"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"


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
class WorkerInfo:
    """工作线程信息"""
    worker_id: str
    status: WorkerStatus = WorkerStatus.IDLE
    current_task_id: Optional[str] = None
    start_time: Optional[datetime] = None
    progress: float = 0.0


class TaskScheduler:
    """任务调度器"""

    def __init__(self, max_workers: int = 1, max_queue_size: int = 0):
        """
        初始化调度器

        Args:
            max_workers: 最大工作线程数
            max_queue_size: 队列最大容量，0 表示无限制
        """
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.workers: Dict[str, WorkerInfo] = {}
        self._priority_queue = PriorityTaskQueue(max_size=max_queue_size)
        self.task_queue: List[str] = []
        self.running_tasks: Dict[str, str] = {}
        self.task_status: Dict[str, Dict[str, Any]] = {}
        self.task_control: Dict[str, TaskControlCommand] = {}
        self._lock = threading.Lock()
        self._worker_threads: List[threading.Thread] = []
        self._running = False
        self._executor: Optional[Callable] = None
        self._stop_event = threading.Event()

        for i in range(max_workers):
            worker_id = f"worker_{i}"
            self.workers[worker_id] = WorkerInfo(worker_id=worker_id)

    def set_executor(self, executor: Callable[[str, Dict[str, Any]], None]):
        """
        设置任务执行器

        Args:
            executor: 执行函数，接收 (task_id, task_data) 参数
        """
        self._executor = executor

    def submit(
        self, 
        task_id: str, 
        task_data: Dict[str, Any], 
        priority: TaskPriority = TaskPriority.NORMAL,
        dependencies: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        max_retries: int = 0
    ) -> bool:
        """
        提交任务到调度器

        Args:
            task_id: 任务 ID
            task_data: 任务数据
            priority: 任务优先级
            dependencies: 依赖的任务 ID 列表
            timeout: 超时时间（秒）
            max_retries: 最大重试次数

        Returns:
            是否成功提交
        """
        with self._lock:
            if task_id in self.task_status and self.task_status[task_id].get("status") not in ["failed", "cancelled", "completed", "timeout", "pending"]:
                logger.warning(f"任务 {task_id} 已存在且正在运行")
                return False
            
            if task_id in self.task_status and self.task_status[task_id].get("status") == "pending":
                logger.info(f"任务 {task_id} 重新提交，从检查点继续")
            
            dependencies = dependencies or []
            has_unsatisfied_deps = any(
                dep_id not in self.task_status or 
                self.task_status[dep_id].get("status") != TaskStatus.COMPLETED.value
                for dep_id in dependencies
            )
            
            if has_unsatisfied_deps:
                self.task_queue.append(task_id)
                self.task_status[task_id] = {
                    "status": TaskStatus.WAITING.value,
                    "progress": 0.0,
                    "current_step": "",
                    "step_progresses": [],
                    "start_time": None,
                    "end_time": None,
                    "duration_seconds": 0.0,
                    "error_message": None,
                    "output_path": None,
                    "result_info": None,
                    "priority": priority.name,
                    "dependencies": dependencies,
                    "timeout": timeout,
                    "max_retries": max_retries,
                    "retry_count": 0
                }
                self.task_control[task_id] = TaskControlCommand.NONE
                logger.info(f"任务 {task_id} 已提交（等待依赖），优先级: {priority.name}")
                return True
            
            success = self._priority_queue.submit(task_id, task_data, priority)
            if not success:
                logger.warning(f"任务队列已满，无法提交任务 {task_id}")
                return False
            
            self.task_queue.append(task_id)
            self.task_status[task_id] = {
                "status": TaskStatus.PENDING.value,
                "progress": 0.0,
                "current_step": "",
                "step_progresses": [],
                "start_time": None,
                "end_time": None,
                "duration_seconds": 0.0,
                "error_message": None,
                "output_path": None,
                "result_info": None,
                "priority": priority.name,
                "dependencies": dependencies,
                "timeout": timeout,
                "max_retries": max_retries,
                "retry_count": 0
            }
            self.task_control[task_id] = TaskControlCommand.NONE
            logger.info(f"任务 {task_id} 已提交，优先级: {priority.name}")
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
            if task_id not in self.task_status:
                return False
            
            status = self.task_status[task_id].get("status")
            if status == TaskStatus.RUNNING.value:
                self.task_control[task_id] = TaskControlCommand.STOP
                self.task_status[task_id]["status"] = TaskStatus.CANCELLED.value
                logger.info(f"运行中任务 {task_id} 已请求取消")
                return True
            
            if status == TaskStatus.PENDING.value:
                self._priority_queue.cancel(task_id)
                if task_id in self.task_queue:
                    self.task_queue.remove(task_id)
                self.task_status[task_id]["status"] = TaskStatus.CANCELLED.value
                logger.info(f"等待中任务 {task_id} 已取消")
                return True
            
            return False

    def should_stop(self, task_id: str) -> bool:
        """
        检查任务是否应该停止

        Args:
            task_id: 任务 ID

        Returns:
            是否应该停止
        """
        with self._lock:
            return self.task_control.get(task_id) == TaskControlCommand.STOP

    def start(self):
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        
        for i in range(self.max_workers):
            worker_id = f"worker_{i}"
            thread = threading.Thread(
                target=self._worker_loop,
                args=(worker_id,),
                daemon=True
            )
            thread.start()
            self._worker_threads.append(thread)
        
        logger.info(f"调度器已启动，工作线程数: {self.max_workers}")

    def stop(self):
        """停止调度器"""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        for thread in self._worker_threads:
            thread.join(timeout=2.0)
        
        self._worker_threads.clear()
        logger.info("调度器已停止")

    def is_running(self) -> bool:
        """检查调度器是否运行中"""
        return self._running

    def _worker_loop(self, worker_id: str):
        """
        工作线程主循环

        Args:
            worker_id: 工作线程 ID
        """
        worker = self.workers[worker_id]
        
        while self._running and not self._stop_event.is_set():
            try:
                task_id, task_data, priority = self._priority_queue.get(timeout=0.5)
            except Exception:
                continue
            
            should_skip = False
            task_timeout = None
            with self._lock:
                if self.task_control.get(task_id) == TaskControlCommand.STOP:
                    self.task_status[task_id]["status"] = TaskStatus.CANCELLED.value
                    should_skip = True
                else:
                    self.task_status[task_id]["status"] = TaskStatus.RUNNING.value
                    self.task_status[task_id]["start_time"] = datetime.now().isoformat()
                    worker.status = WorkerStatus.BUSY
                    worker.current_task_id = task_id
                    task_timeout = self.task_status[task_id].get("timeout")
            
            if should_skip:
                continue
            
            timed_out = False
            timeout_timer = None
            
            if task_timeout:
                def timeout_handler():
                    nonlocal timed_out
                    with self._lock:
                        if self.task_status[task_id].get("status") == TaskStatus.RUNNING.value:
                            timed_out = True
                            self.task_control[task_id] = TaskControlCommand.STOP
                            self.task_status[task_id]["status"] = TaskStatus.TIMEOUT.value
                            self.task_status[task_id]["error_message"] = f"任务超时 ({task_timeout}s)"
                            self.task_status[task_id]["end_time"] = datetime.now().isoformat()
                            logger.warning(f"任务 {task_id} 执行超时")
                
                timeout_timer = threading.Timer(task_timeout, timeout_handler)
                timeout_timer.start()
            
            try:
                if self._executor:
                    self._executor(task_id, task_data)
                
                if timeout_timer:
                    timeout_timer.cancel()
                
                with self._lock:
                    if self.task_status[task_id].get("status") == TaskStatus.RUNNING.value:
                        self.task_status[task_id]["status"] = TaskStatus.COMPLETED.value
                        self.task_status[task_id]["end_time"] = datetime.now().isoformat()
                        logger.info(f"任务 {task_id} 执行完成")
                        self._activate_waiting_tasks(task_id)
            
            except Exception as e:
                if timeout_timer:
                    timeout_timer.cancel()
                
                with self._lock:
                    if timed_out:
                        return
                    
                    max_retries = self.task_status[task_id].get("max_retries", 0)
                    retry_count = self.task_status[task_id].get("retry_count", 0)
                    
                    if retry_count < max_retries:
                        self.task_status[task_id]["retry_count"] = retry_count + 1
                        self.task_status[task_id]["status"] = TaskStatus.PENDING.value
                        self._priority_queue.submit(
                            task_id, 
                            task_data, 
                            priority
                        )
                        logger.info(f"任务 {task_id} 失败，重试 {retry_count + 1}/{max_retries}: {e}")
                    else:
                        self.task_status[task_id]["status"] = TaskStatus.FAILED.value
                        self.task_status[task_id]["error_message"] = str(e)
                        self.task_status[task_id]["end_time"] = datetime.now().isoformat()
                        logger.error(f"任务 {task_id} 执行失败: {e}")
            
            finally:
                with self._lock:
                    worker.status = WorkerStatus.IDLE
                    worker.current_task_id = None
                    if task_id in self.task_queue and not timed_out:
                        self.task_queue.remove(task_id)

    def _activate_waiting_tasks(self, completed_task_id: str):
        """
        激活等待中任务的依赖已满足的任务

        Args:
            completed_task_id: 完成的任务 ID
        """
        for task_id, status in list(self.task_status.items()):
            if status.get("status") != TaskStatus.WAITING.value:
                continue
            
            dependencies = status.get("dependencies", [])
            if completed_task_id not in dependencies:
                continue
            
            all_deps_satisfied = True
            for dep_id in dependencies:
                if dep_id not in self.task_status:
                    all_deps_satisfied = False
                    break
                if self.task_status[dep_id].get("status") != TaskStatus.COMPLETED.value:
                    all_deps_satisfied = False
                    break
            
            if all_deps_satisfied:
                status["status"] = TaskStatus.PENDING.value
                self._priority_queue.submit(
                    task_id, 
                    {"dependencies": dependencies},
                    TaskPriority[status.get("priority", "NORMAL")]
                )
                logger.info(f"任务 {task_id} 依赖已满足，已激活")

    def get_waiting_tasks(self) -> List[str]:
        """
        获取等待中任务列表

        Returns:
            等待中任务 ID 列表
        """
        with self._lock:
            return [
                task_id for task_id, status in self.task_status.items()
                if status.get("status") == TaskStatus.WAITING.value
            ]

    def are_dependencies_satisfied(self, task_id: str) -> bool:
        """
        检查任务依赖是否满足

        Args:
            task_id: 任务 ID

        Returns:
            依赖是否满足
        """
        with self._lock:
            if task_id not in self.task_status:
                return True
            
            dependencies = self.task_status[task_id].get("dependencies", [])
            for dep_id in dependencies:
                if dep_id not in self.task_status:
                    return False
                if self.task_status[dep_id].get("status") != TaskStatus.COMPLETED.value:
                    return False
            
            return True

    def add_task(self, task_id: str, task_data: Dict[str, Any]):
        """添加任务到队列"""
        with self._lock:
            if task_id not in self.task_queue:
                self.task_queue.append(task_id)
                self.task_status[task_id] = {
                    "status": "pending",
                    "progress": 0.0,
                    "current_step": "",
                    "step_progresses": [],
                    "start_time": None,
                    "end_time": None,
                    "duration_seconds": 0.0,
                    "error_message": None,
                    "output_path": None,
                    "result_info": None
                }
                self.task_control[task_id] = TaskControlCommand.NONE
                logger.info(f"任务 {task_id} 已添加到队列")

    def remove_task(self, task_id: str):
        """从队列中移除任务"""
        with self._lock:
            if task_id in self.task_queue:
                self.task_queue.remove(task_id)
            if task_id in self.task_status:
                del self.task_status[task_id]
            if task_id in self.task_control:
                del self.task_control[task_id]
            logger.info(f"任务 {task_id} 已从队列移除")

    def move_task_up(self, task_id: str):
        """任务上移"""
        with self._lock:
            if task_id in self.task_queue:
                idx = self.task_queue.index(task_id)
                if idx > 0:
                    self.task_queue[idx], self.task_queue[idx - 1] = \
                        self.task_queue[idx - 1], self.task_queue[idx]
                    logger.info(f"任务 {task_id} 已上移")

    def move_task_down(self, task_id: str):
        """任务下移"""
        with self._lock:
            if task_id in self.task_queue:
                idx = self.task_queue.index(task_id)
                if idx < len(self.task_queue) - 1:
                    self.task_queue[idx], self.task_queue[idx + 1] = \
                        self.task_queue[idx + 1], self.task_queue[idx]
                    logger.info(f"任务 {task_id} 已下移")

    def move_task_to_top(self, task_id: str):
        """任务置顶"""
        with self._lock:
            if task_id in self.task_queue:
                self.task_queue.remove(task_id)
                self.task_queue.insert(0, task_id)
                logger.info(f"任务 {task_id} 已置顶")

    def move_task_to_bottom(self, task_id: str):
        """任务置底"""
        with self._lock:
            if task_id in self.task_queue:
                self.task_queue.remove(task_id)
                self.task_queue.append(task_id)
                logger.info(f"任务 {task_id} 已置底")

    def pause_task(self, task_id: str):
        """暂停任务"""
        with self._lock:
            if task_id in self.task_status:
                self.task_control[task_id] = TaskControlCommand.PAUSE
                self.task_status[task_id]["status"] = "paused"
                logger.info(f"任务 {task_id} 已暂停")

    def resume_task(self, task_id: str):
        """恢复任务"""
        with self._lock:
            if task_id in self.task_status:
                self.task_control[task_id] = TaskControlCommand.RESUME
                self.task_status[task_id]["status"] = "running"
                logger.info(f"任务 {task_id} 已恢复")

    def stop_task(self, task_id: str):
        """终止任务"""
        with self._lock:
            if task_id in self.task_status:
                self.task_control[task_id] = TaskControlCommand.STOP
                self.task_status[task_id]["status"] = "stopped"
                logger.info(f"任务 {task_id} 已终止")

    def update_task_progress(self, task_id: str, progress: float, current_step: str = "", message: str = ""):
        """更新任务进度"""
        with self._lock:
            if task_id in self.task_status:
                self.task_status[task_id]["progress"] = progress
                if current_step:
                    self.task_status[task_id]["current_step"] = current_step
                if message:
                    step_progresses = self.task_status[task_id]["step_progresses"]
                    step_progresses.append({
                        "step": current_step,
                        "progress": progress,
                        "message": message,
                        "timestamp": datetime.now().isoformat()
                    })
                    self.task_status[task_id]["step_progresses"] = step_progresses

    def set_task_status(self, task_id: str, status: str):
        """设置任务状态"""
        with self._lock:
            if task_id in self.task_status:
                self.task_status[task_id]["status"] = status

    def set_task_result(self, task_id: str, output_path: str, result_info: Dict[str, Any] = None):
        """设置任务结果"""
        with self._lock:
            if task_id in self.task_status:
                self.task_status[task_id]["output_path"] = output_path
                self.task_status[task_id]["result_info"] = result_info
                self.task_status[task_id]["end_time"] = datetime.now().isoformat()
                if self.task_status[task_id].get("start_time"):
                    start = datetime.fromisoformat(self.task_status[task_id]["start_time"])
                    self.task_status[task_id]["duration_seconds"] = (datetime.now() - start).total_seconds()

    def set_task_error(self, task_id: str, error_message: str):
        """设置任务错误"""
        with self._lock:
            if task_id in self.task_status:
                self.task_status[task_id]["error_message"] = error_message
                self.task_status[task_id]["status"] = "failed"
                self.task_status[task_id]["end_time"] = datetime.now().isoformat()

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        with self._lock:
            return self.task_status.get(task_id)

    def get_pending_tasks(self) -> List[str]:
        """获取待运行任务列表"""
        with self._lock:
            return self.task_queue.copy()

    def get_running_tasks(self) -> List[str]:
        """获取运行中任务列表"""
        with self._lock:
            return [tid for tid, status in self.task_status.items()
                    if status.get("status") == "running"]

    def get_completed_tasks(self) -> List[str]:
        """获取已完成任务列表"""
        with self._lock:
            return [tid for tid, status in self.task_status.items()
                    if status.get("status") == "completed"]

    def get_all_task_statuses(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务状态"""
        with self._lock:
            return self.task_status.copy()

    def clear_completed_tasks(self):
        """清除已完成任务"""
        with self._lock:
            completed = [tid for tid, status in self.task_status.items()
                         if status.get("status") in ["completed", "failed"]]
            for tid in completed:
                if tid in self.task_status:
                    del self.task_status[tid]
                if tid in self.task_control:
                    del self.task_control[tid]

    def get_worker_info(self) -> List[Dict[str, Any]]:
        """获取工作线程信息"""
        with self._lock:
            return [
                {
                    "worker_id": w.worker_id,
                    "status": w.status.value,
                    "current_task_id": w.current_task_id,
                    "progress": w.progress
                }
                for w in self.workers.values()
            ]


_global_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """获取全局调度器实例"""
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = TaskScheduler(max_workers=1)
    return _global_scheduler


def init_scheduler(max_workers: int = 1) -> TaskScheduler:
    """初始化全局调度器"""
    global _global_scheduler
    _global_scheduler = TaskScheduler(max_workers=max_workers)
    return _global_scheduler


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

            self._tasks[task_id] = task
            self._queue.append(task)
            logger.info(f"任务 {task_id} 已加入队列，当前队列长度: {len(self._queue)}")
            return True
    
    def set_priority(self, task_id: str) -> bool:
        """
        设置任务为插队任务
        
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
            
            if self._priority_task and self._priority_task.task_id != task_id:
                self._priority_task.is_priority = False
            
            task.is_priority = True
            self._priority_task = task
            logger.info(f"任务 {task_id} 已设为插队任务")
            return True
    
    def cancel_priority(self, task_id: str) -> bool:
        """
        取消插队
        
        Args:
            task_id: 任务 ID
            
        Returns:
            是否成功取消
        """
        with self._lock:
            if self._priority_task and self._priority_task.task_id == task_id:
                self._priority_task.is_priority = False
                self._priority_task = None
                logger.info(f"任务 {task_id} 已取消插队")
                return True
            return False
    
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

            if self._current_task and self._current_task.task_id == task_id:
                task.status = TaskStatus.CANCELLED
                self._cancel_event.set()
                logger.info(f"当前任务 {task_id} 已取消")
                return True

            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                self._queue = [t for t in self._queue if t.task_id != task_id]
                if self._priority_task and self._priority_task.task_id == task_id:
                    self._priority_task = None
                del self._tasks[task_id]
                logger.info(f"队列任务 {task_id} 已取消并移除")
                return True

            # 处理 RUNNING 状态的任务（可能是卡住的任务）
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.CANCELLED
                self._cancel_event.set()
                self._current_task = None
                logger.info(f"运行中任务 {task_id} 已强制取消")
                return True

            return False
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
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
                "is_priority": task.is_priority,
                "timeout": task.timeout
            }
    
    def get_queue_status(self) -> Dict:
        """获取队列状态"""
        with self._lock:
            return {
                "queue_length": len(self._queue),
                "current_task": self._current_task.task_id if self._current_task else None,
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
