import json
import time
import threading
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue
import uuid

logger = logging.getLogger(__name__)

class TaskPriority(Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 10
    URGENT = 20

@dataclass
class Task:
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: TaskPriority
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: float = 0.0
    retry_count: int = 0
    max_retries: int = 3

class InMemoryTaskQueue:
    def __init__(self, max_size: int = 100):
        self.queue = Queue(maxsize=max_size)
        self.tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
    
    def enqueue(
        self,
        task_type: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> str:
        task_id = task_id or str(uuid.uuid4())
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            payload=payload,
            priority=priority,
            status="pending",
            created_at=datetime.now()
        )
        
        with self._lock:
            self.tasks[task_id] = task
            self.queue.put((priority.value, task_id, task_type))
        
        logger.info(f"Task enqueued: {task_id}, type: {task_type}")
        return task_id
    
    def dequeue(self, timeout: float = 1.0) -> Optional[Task]:
        try:
            _, task_id, task_type = self.queue.get(timeout=timeout)
            with self._lock:
                task = self.tasks.get(task_id)
                if task:
                    task.status = "processing"
                    task.started_at = datetime.now()
                return task
        except:
            return None
    
    def update_progress(self, task_id: str, progress: float, message: str = ""):
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.progress = progress
    
    def complete_task(self, task_id: str, result: Dict[str, Any]):
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.status = "completed"
                task.progress = 100.0
                task.completed_at = datetime.now()
                task.result = result
    
    def fail_task(self, task_id: str, error: str, retry: bool = True):
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                if retry and task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.status = "pending"
                    self.queue.put((task.priority.value, task_id, task.task_type))
                    logger.warning(f"Task retry: {task_id}, count: {task.retry_count}")
                else:
                    task.status = "failed"
                    task.error = error
                    task.completed_at = datetime.now()
                    logger.error(f"Task failed: {task_id}, error: {error}")
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                return {
                    "task_id": task.task_id,
                    "status": task.status,
                    "progress": task.progress,
                    "error": task.error,
                    "result": task.result,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None
                }
        return None
    
    def start_worker(self, handler: Callable[[Task], None], max_workers: int = 1):
        self._running = True
        
        def worker_loop():
            while self._running:
                task = self.dequeue(timeout=1.0)
                if task:
                    try:
                        handler(task)
                    except Exception as e:
                        self.fail_task(task.task_id, str(e))
        
        self._worker_thread = threading.Thread(target=worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("Task worker started")
    
    def stop_worker(self):
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("Task worker stopped")

_task_queue: Optional[InMemoryTaskQueue] = None

def get_task_queue() -> InMemoryTaskQueue:
    global _task_queue
    if _task_queue is None:
        _task_queue = InMemoryTaskQueue()
    return _task_queue
