"""
任务队列服务
使用 asyncio + ThreadPoolExecutor 实现 GPU 推理任务的串行调度
"""

import asyncio
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

from api_server.models.task import TaskInfo, TaskStatus

logger = logging.getLogger("indextts-api.queue")


class TaskQueue:
    """
    异步任务队列

    - GPU 推理串行执行（ThreadPoolExecutor max_workers=1）
    - 异步提交，立即返回 task_id
    - 支持队列位置查询和任务状态轮询
    """

    def __init__(
        self,
        engine,
        audio_service,
        max_size: int = 10,
        task_timeout_sec: int = 600,
    ) -> None:
        """
        Args:
            engine: TTSEngine 实例
            audio_service: AudioService 实例
            max_size: 队列最大长度
            task_timeout_sec: 单任务超时时间（秒）
        """
        self._engine = engine
        self._audio_service = audio_service
        self._max_size = max_size
        self._task_timeout_sec = task_timeout_sec

        self._tasks: dict[str, TaskInfo] = {}
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._executor: Optional[ThreadPoolExecutor] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

        # 跟踪任务使用的临时音频文件
        self._task_temp_audio: dict[str, list[str]] = {}

    def register_temp_audio(self, task_id: str, audio_path: str) -> None:
        """
        注册任务使用的临时音频文件

        Args:
            task_id: 任务 ID
            audio_path: 临时音频文件路径
        """
        if task_id not in self._task_temp_audio:
            self._task_temp_audio[task_id] = []
        self._task_temp_audio[task_id].append(audio_path)
        logger.debug(f"注册临时音频文件: task_id={task_id}, path={audio_path}")

    def cleanup_task_temp_audio(self, task_id: str) -> None:
        """
        清理任务使用的临时音频文件

        Args:
            task_id: 任务 ID
        """
        if task_id in self._task_temp_audio:
            for audio_path in self._task_temp_audio[task_id]:
                try:
                    import os
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                        logger.info(f"已清理临时音频文件: {audio_path}")
                except Exception as e:
                    logger.warning(f"清理临时音频文件失败: {audio_path}, 错误: {e}")
            del self._task_temp_audio[task_id]

    async def start(self) -> None:
        """启动队列消费者"""
        if self._running:
            return
        self._running = True
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("任务队列已启动")

    async def stop(self, graceful_timeout: float = 120.0) -> None:
        """
        优雅停止队列。

        1. 停止接受新任务
        2. 等待当前正在处理的任务完成
        3. 将队列中剩余 pending 任务标记为 failed
        4. 关闭线程池
        """
        logger.info("任务队列开始优雅关闭...")
        self._running = False

        # 等待 worker 完成（最多等待 graceful_timeout 秒）
        if self._worker_task:
            remaining = self._queue.qsize()
            logger.info(f"等待当前任务完成，队列中剩余 {remaining} 个任务（超时 {graceful_timeout}s）")
            try:
                await asyncio.wait_for(self._worker_task, timeout=graceful_timeout)
            except asyncio.TimeoutError:
                logger.warning(f"任务队列停止超时（{graceful_timeout}s），强制终止")
                self._worker_task.cancel()

        # 将仍在 pending 的任务标记为失败
        cancelled = 0
        for task_id, task in self._tasks.items():
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.FAILED
                task.error_message = "服务关闭，任务被取消"
                task.completed_at = datetime.now(timezone.utc).isoformat()
                cancelled += 1
        if cancelled > 0:
            logger.info(f"取消了 {cancelled} 个未处理的排队任务")

        # 关闭线程池（等待当前推理完成）
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=True)

        logger.info("任务队列已停止")

    @property
    def queue_length(self) -> int:
        """当前队列中待处理的任务数量"""
        return self._queue.qsize()

    async def submit(
        self,
        text: str,
        voice_path: str,
        emo_audio_prompt: Optional[str] = None,
        emo_alpha: float = 1.0,
        emo_vector: Optional[list] = None,
        use_emo_text: bool = False,
        emo_text: Optional[str] = None,
        use_random: bool = False,
        temperature: float = 1.0,
        top_p: float = 0.8,
        top_k: int = 30,
        num_beams: int = 3,
    ) -> TaskInfo:
        """
        提交合成任务 - 支持原版 IndexTTS2 情绪参数

        Returns:
            TaskInfo: 包含 task_id 和初始状态

        Raises:
            RuntimeError: 队列已满
        """
        if self._queue.qsize() >= self._max_size:
            raise RuntimeError(f"任务队列已满（最大 {self._max_size}）")

        task_id = uuid.uuid4().hex[:16]
        output_path = self._audio_service.generate_output_path(task_id)

        task = TaskInfo(
            task_id=task_id,
            status=TaskStatus.PENDING,
            text=text,
            voice_path=voice_path,
            output_path=output_path,
            emo_audio_prompt=emo_audio_prompt,
            emo_alpha=emo_alpha,
            emo_vector=emo_vector,
            use_emo_text=use_emo_text,
            emo_text=emo_text,
            use_random=use_random,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            num_beams=num_beams,
            created_at=datetime.now(timezone.utc).isoformat(),
            queue_position=self._queue.qsize() + 1,
        )

        self._tasks[task_id] = task
        await self._queue.put(task_id)

        logger.info(f"任务已提交: {task_id}, 队列位置: {task.queue_position}")
        return task

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务信息"""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[TaskInfo]:
        """获取所有任务信息（用于统计）"""
        return list(self._tasks.values())

    def get_queue_position(self, task_id: str) -> Optional[int]:
        """获取任务在队列中的位置，0 表示正在处理，None 表示任务不存在"""
        task = self._tasks.get(task_id)
        if task is None:
            return None
        if task.status != TaskStatus.PENDING:
            return 0

        # 计算在 pending 任务中的位置
        position = 0
        for tid, t in self._tasks.items():
            if t.status == TaskStatus.PENDING and tid != task_id:
                # 这里简化处理，返回一个估计值
                pass

        # 遍历队列估算位置
        position = 0
        for tid in list(self._tasks.keys()):
            t = self._tasks[tid]
            if t.status == TaskStatus.PENDING:
                if tid == task_id:
                    return position + 1
                position += 1
        return 0

    def get_estimated_wait(self, task_id: str) -> Optional[float]:
        """估算等待时间（秒）"""
        position = self.get_queue_position(task_id)
        if position is None or position == 0:
            return 0
        # 简单估算：每个任务约 10 秒
        return position * 10.0

    async def _worker(self) -> None:
        """队列消费者循环"""
        logger.info("任务消费者已启动")
        while self._running or not self._queue.empty():
            try:
                task_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            task = self._tasks.get(task_id)
            if task is None:
                continue

            task.status = TaskStatus.PROCESSING
            task.queue_position = 0
            logger.info(f"开始处理任务: {task_id}")

            start_time = time.time()

            try:
                # 在线程池中执行同步推理（带超时）
                loop = asyncio.get_event_loop()
                try:
                    await asyncio.wait_for(
                        loop.run_in_executor(
                            self._executor,
                            self._execute_task,
                            task,
                        ),
                        timeout=self._task_timeout_sec,
                    )
                except asyncio.TimeoutError:
                    task.status = TaskStatus.FAILED
                    task.error_message = f"任务执行超时（{self._task_timeout_sec}s）"
                    task.completed_at = datetime.now(timezone.utc).isoformat()
                    logger.error(f"任务超时: {task_id}, 超时时间: {self._task_timeout_sec}s")
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                task.completed_at = datetime.now(timezone.utc).isoformat()
                logger.error(f"任务执行失败: {task_id}, 错误: {e}", exc_info=True)
            finally:
                inference_time = time.time() - start_time
                task.inference_time_sec = round(inference_time, 3)

                # 更新队列中其他任务的位置
                self._update_queue_positions()

    def _execute_task(self, task: TaskInfo) -> None:
        """在线程池中执行同步推理（GPU 推理必须在线程中执行）"""
        try:
            output_path = self._engine.synthesize(
                text=task.text,
                voice_path=task.voice_path,
                output_path=task.output_path,
                emo_audio_prompt=task.emo_audio_prompt,
                emo_alpha=task.emo_alpha,
                emo_vector=task.emo_vector,
                use_emo_text=task.use_emo_text,
                emo_text=task.emo_text,
                use_random=task.use_random,
                temperature=task.temperature,
                top_p=task.top_p,
                top_k=task.top_k,
                num_beams=task.num_beams,
            )

            # 计算音频时长
            import torchaudio

            wav, sr = torchaudio.load(output_path)
            duration = wav.shape[-1] / sr

            task.status = TaskStatus.COMPLETED
            task.audio_url = f"/api/v1/audio/{task.task_id}.wav"
            task.duration_sec = round(duration, 3)
            task.completed_at = datetime.now(timezone.utc).isoformat()
            logger.info(f"任务完成: {task.task_id}, 时长: {duration:.2f}s")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now(timezone.utc).isoformat()
            raise

    def _update_queue_positions(self) -> None:
        """更新队列中 pending 任务的排队位置"""
        position = 0
        for task_id, task in self._tasks.items():
            if task.status == TaskStatus.PENDING:
                position += 1
                task.queue_position = position
