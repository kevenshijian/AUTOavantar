"""
优先级任务队列模块
支持任务优先级和取消功能
"""

import logging
import threading
import queue
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import IntEnum
import time

logger = logging.getLogger(__name__)


class TaskPriority(IntEnum):
    """任务优先级"""
    HIGH = 1
    NORMAL = 5
    LOW = 10


@dataclass
class TaskItem:
    """任务项"""
    task_id: str
    data: Dict[str, Any]
    priority: TaskPriority
    submit_time: float
    
    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.submit_time < other.submit_time


class PriorityTaskQueue:
    """
    优先级任务队列
    
    支持按优先级取出任务，支持任务取消。
    线程安全实现。
    """
    
    def __init__(self, max_size: int = 0):
        """
        初始化队列
        
        Args:
            max_size: 队列最大容量，0 表示无限制
        """
        self._queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=max_size)
        self._tasks: Dict[str, TaskItem] = {}
        self._cancelled: set = set()
        self._lock = threading.Lock()
    
    def submit(
        self, 
        task_id: str, 
        data: Dict[str, Any], 
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> bool:
        """
        提交任务到队列
        
        Args:
            task_id: 任务 ID
            data: 任务数据
            priority: 任务优先级
            
        Returns:
            是否成功提交
        """
        with self._lock:
            if task_id in self._tasks:
                logger.warning(f"任务 {task_id} 已存在")
                return False
            
            item = TaskItem(
                task_id=task_id,
                data=data,
                priority=priority,
                submit_time=time.time()
            )
            
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                logger.warning(f"任务队列已满，无法提交任务 {task_id}")
                return False
            
            self._tasks[task_id] = item
            
            logger.debug(f"任务 {task_id} 已提交，优先级: {priority.name}")
            return True
    
    def get(self, timeout: Optional[float] = None) -> Tuple[str, Dict[str, Any], TaskPriority]:
        """
        从队列获取任务
        
        Args:
            timeout: 超时时间（秒），None 表示阻塞
            
        Returns:
            (task_id, data, priority) 元组
            
        Raises:
            queue.Empty: 队列为空或超时
        """
        item = self._queue.get(timeout=timeout)
        
        with self._lock:
            if item.task_id in self._cancelled:
                self._cancelled.discard(item.task_id)
                if item.task_id in self._tasks:
                    del self._tasks[item.task_id]
                return self.get(timeout=timeout)
            
            del self._tasks[item.task_id]
        
        return item.task_id, item.data, item.priority
    
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
            
            self._cancelled.add(task_id)
            del self._tasks[task_id]
            
            logger.info(f"任务 {task_id} 已取消")
            return True
    
    def empty(self) -> bool:
        """检查队列是否为空"""
        with self._lock:
            return len(self._tasks) == 0
    
    def size(self) -> int:
        """获取队列大小（可用任务数）"""
        with self._lock:
            return len(self._tasks)
    
    def contains(self, task_id: str) -> bool:
        """检查任务是否存在"""
        with self._lock:
            return task_id in self._tasks
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取队列状态
        
        Returns:
            状态字典
        """
        with self._lock:
            by_priority = {
                "high": 0,
                "normal": 0,
                "low": 0
            }
            
            for item in self._tasks.values():
                if item.priority == TaskPriority.HIGH:
                    by_priority["high"] += 1
                elif item.priority == TaskPriority.NORMAL:
                    by_priority["normal"] += 1
                else:
                    by_priority["low"] += 1
            
            return {
                "total": len(self._tasks),
                "by_priority": by_priority
            }
