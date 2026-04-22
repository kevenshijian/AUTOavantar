import threading
import time
import logging
from typing import Dict, Callable, Any
from .task_queue import Task, InMemoryTaskQueue, get_task_queue

logger = logging.getLogger(__name__)

class TaskWorker:
    def __init__(
        self,
        task_queue: InMemoryTaskQueue,
        handlers: Dict[str, Callable],
        max_concurrent: int = 1,
        poll_interval: float = 1.0
    ):
        self.task_queue = task_queue
        self.handlers = handlers
        self.max_concurrent = max_concurrent
        self.poll_interval = poll_interval
        self.running = False
        self.active_tasks = []
        self._stop_event = threading.Event()
    
    def start(self):
        self.running = True
        logger.info(f"Worker started with {self.max_concurrent} concurrent slots")
        
        while self.running:
            if len(self.active_tasks) < self.max_concurrent:
                task = self.task_queue.dequeue(timeout=1)
                if task:
                    thread = threading.Thread(
                        target=self._process_task,
                        args=(task,)
                    )
                    thread.start()
                    self.active_tasks.append(thread)
            
            self.active_tasks = [
                t for t in self.active_tasks if t.is_alive()
            ]
            
            time.sleep(self.poll_interval)
    
    def stop(self):
        self.running = False
        self._stop_event.set()
        for thread in self.active_tasks:
            thread.join(timeout=30)
        logger.info("Worker stopped")
    
    def _process_task(self, task: Task):
        logger.info(f"Processing task {task.task_id} of type {task.task_type}")
        
        try:
            handler = self.handlers.get(task.task_type)
            if not handler:
                raise ValueError(f"No handler for task type: {task.task_type}")
            
            def progress_callback(progress: float, message: str = ""):
                self.task_queue.update_progress(task.task_id, progress, message)
            
            result = handler(task.payload, progress_callback)
            
            self.task_queue.complete_task(task.task_id, result or {})
            logger.info(f"Task {task.task_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {str(e)}")
            self.task_queue.fail_task(task.task_id, str(e))
