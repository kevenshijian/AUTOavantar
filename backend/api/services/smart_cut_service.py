"""
智能裁剪服务
提供视频上传、识别、分割、合成等功能
"""

import os
import sys
import json
import logging
import subprocess
import platform
import shutil
import base64
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import uuid

import cv2
import numpy as np

# 添加 models 目录到路径
models_path = Path(__file__).resolve().parent.parent.parent.parent / "models" / "TransNetV2"
if models_path.exists():
    sys.path.insert(0, str(models_path))

logger = logging.getLogger("autoavantar-api.smart_cut_service")


class SmartCutService:
    """智能裁剪服务"""

    # 支持的视频格式
    SUPPORTED_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}

    # 最大文件大小（2GB）
    MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024

    def __init__(self, base_dir: str = None):
        """
        初始化服务

        Args:
            base_dir: 基础目录，默认为 backend 目录
        """
        if base_dir is None:
            # 默认使用 backend 目录
            self.base_dir = Path(__file__).resolve().parent.parent.parent
        else:
            self.base_dir = Path(base_dir)

        # 临时目录
        self.temp_dir = self.base_dir / "temp" / "smart_cut"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"SmartCutService 初始化完成，临时目录: {self.temp_dir}")

    def _generate_video_id(self) -> str:
        """生成视频ID"""
        return f"tmp_{uuid.uuid4().hex[:12]}"

    def _get_video_temp_dir(self, video_id: str) -> Path:
        """获取视频临时目录"""
        return self.temp_dir / video_id

    def _validate_video_format(self, filename: str) -> bool:
        """验证视频格式"""
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.SUPPORTED_FORMATS

    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        使用 ffprobe 获取视频信息

        Args:
            video_path: 视频文件路径

        Returns:
            包含 duration, fps, width, height, total_frames 的字典
        """
        try:
            # 使用 ffprobe 获取视频信息
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate,duration,nb_frames",
                "-show_entries", "format=duration",
                "-of", "json",
                video_path
            ]

            creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            result = subprocess.run(cmd, capture_output=True, text=True, creation_flags=creation_flags)

            if result.returncode != 0:
                logger.error(f"ffprobe 失败: {result.stderr}")
                return {}

            data = json.loads(result.stdout)

            # 提取流信息
            stream = data.get("streams", [{}])[0] if data.get("streams") else {}
            format_info = data.get("format", {})

            # 解析帧率
            fps_str = stream.get("r_frame_rate", "30/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps = float(num) / float(den) if float(den) > 0 else 30.0
            else:
                fps = float(fps_str)

            # 解析时长
            duration = float(stream.get("duration") or format_info.get("duration", 0))

            # 解析总帧数
            nb_frames = stream.get("nb_frames")
            if nb_frames:
                total_frames = int(nb_frames)
            else:
                total_frames = int(duration * fps) if duration > 0 and fps > 0 else 0

            return {
                "width": int(stream.get("width", 0)),
                "height": int(stream.get("height", 0)),
                "fps": round(fps, 2),
                "duration": round(duration, 2),
                "total_frames": total_frames
            }

        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            return {}

    def _generate_thumbnail(self, video_path: str, output_path: str, time_offset: float = 0) -> bool:
        """
        生成视频缩略图

        Args:
            video_path: 视频文件路径
            output_path: 输出图片路径
            time_offset: 时间偏移（秒），默认取第一帧

        Returns:
            是否成功
        """
        try:
            # 使用 OpenCV 提取帧
            cap = cv2.VideoCapture(video_path)

            if not cap.isOpened():
                logger.error(f"无法打开视频: {video_path}")
                return False

            # 设置帧位置
            if time_offset > 0:
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_number = int(time_offset * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                logger.error(f"无法读取视频帧: {video_path}")
                return False

            # 缩放到合适大小
            max_width = 320
            if frame.shape[1] > max_width:
                scale = max_width / frame.shape[1]
                frame = cv2.resize(frame, None, fx=scale, fy=scale)

            # 保存缩略图
            cv2.imwrite(output_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

            logger.info(f"缩略图生成成功: {output_path}")
            return True

        except Exception as e:
            logger.error(f"生成缩略图失败: {e}")
            return False

    def _generate_thumbnail_base64(self, video_path: str, time_offset: float = 0) -> Optional[str]:
        """
        生成视频缩略图的 base64 编码

        Args:
            video_path: 视频文件路径
            time_offset: 时间偏移（秒）

        Returns:
            base64 编码的图片（data:image/jpeg;base64,...）
        """
        try:
            cap = cv2.VideoCapture(video_path)

            if not cap.isOpened():
                return None

            if time_offset > 0:
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_number = int(time_offset * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                return None

            # 缩放
            max_width = 320
            if frame.shape[1] > max_width:
                scale = max_width / frame.shape[1]
                frame = cv2.resize(frame, None, fx=scale, fy=scale)

            # 编码为 base64
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_base64 = base64.b64encode(buffer).decode('utf-8')

            return f"data:image/jpeg;base64,{frame_base64}"

        except Exception as e:
            logger.error(f"生成缩略图 base64 失败: {e}")
            return None

    async def upload_video(
        self,
        file_content: bytes,
        filename: str,
        content_type: str = None
    ) -> Dict[str, Any]:
        """
        上传视频文件

        Args:
            file_content: 文件内容
            filename: 文件名
            content_type: 内容类型

        Returns:
            包含视频信息的字典

        Raises:
            ValueError: 格式不支持或文件过大
        """
        # 1. 验证格式
        if not self._validate_video_format(filename):
            raise ValueError(f"不支持的视频格式，请上传 mp4/avi/mov 文件")

        # 2. 验证大小
        file_size = len(file_content)
        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(f"视频文件过大，请上传小于 2GB 的文件")

        # 3. 生成视频ID和临时目录
        video_id = self._generate_video_id()
        video_temp_dir = self._get_video_temp_dir(video_id)
        video_temp_dir.mkdir(parents=True, exist_ok=True)

        # 4. 保存视频文件
        video_path = video_temp_dir / "video.mp4"
        with open(video_path, "wb") as f:
            f.write(file_content)

        logger.info(f"视频保存成功: {video_path}")

        # 5. 获取视频信息
        try:
            video_info = self._get_video_info(str(video_path))
        except Exception as e:
            # 清理临时文件
            shutil.rmtree(video_temp_dir, ignore_errors=True)
            raise ValueError(f"视频文件损坏或无法读取")

        if not video_info.get("duration"):
            shutil.rmtree(video_temp_dir, ignore_errors=True)
            raise ValueError(f"视频文件损坏或无法读取")

        # 6. 生成缩略图
        thumbnail_base64 = self._generate_thumbnail_base64(str(video_path))

        # 7. 返回结果
        return {
            "video_id": video_id,
            "video_path": str(video_path.relative_to(self.base_dir)),
            "video_name": filename,
            "duration": video_info.get("duration", 0),
            "fps": video_info.get("fps", 0),
            "width": video_info.get("width", 0),
            "height": video_info.get("height", 0),
            "total_frames": video_info.get("total_frames", 0),
            "thumbnail": thumbnail_base64 or ""
        }

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态信息
        """
        from api.services.database import get_database_service

        db = get_database_service()
        task = await db.smart_cut_task_get_by_id(task_id)

        if not task:
            return None

        # 解析 config 和 segments_info
        config = json.loads(task.get("config") or "{}")
        segments_info = json.loads(task.get("segments_info") or "null")

        return {
            "task_id": task["task_id"],
            "status": task["status"],
            "progress": task["progress"],
            "current_stage": task["current_stage"] or "",
            "video_name": task["video_name"] or "",
            "total_frames": task["total_frames"] or 0,
            "processed_frames": int((task["progress"] or 0) / 100 * (task["total_frames"] or 0)),
            "config": config,
            "segments": segments_info,
            "created_at": task["created_at"],
            "updated_at": task["updated_at"]
        }

    async def get_segments(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取片段列表

        Args:
            task_id: 任务ID

        Returns:
            片段列表信息
        """
        from api.services.database import get_database_service

        db = get_database_service()
        task = await db.smart_cut_task_get_by_id(task_id)

        if not task:
            return None

        segments_info = json.loads(task.get("segments_info") or "null")

        return {
            "task_id": task_id,
            "video_path": task["video_path"],
            "segments": segments_info or []
        }

    async def delete_task(self, task_id: str) -> bool:
        """
        删除任务及临时文件

        Args:
            task_id: 任务ID

        Returns:
            是否删除成功
        """
        from api.services.database import get_database_service

        db = get_database_service()
        task = await db.smart_cut_task_get_by_id(task_id)

        if not task:
            return False

        # 删除临时目录
        video_path = task.get("video_path", "")
        if video_path:
            # 从 video_path 提取 video_id
            # video_path 格式: temp/smart_cut/tmp_xxx/video.mp4
            parts = Path(video_path).parts
            if len(parts) >= 3 and parts[0] == "temp" and parts[1] == "smart_cut":
                video_id = parts[2]
                temp_dir = self.temp_dir / video_id
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.info(f"已删除临时目录: {temp_dir}")

        # 删除数据库记录
        return await db.smart_cut_task_delete(task_id)

    def cleanup_temp_files(self, max_age_hours: int = 24):
        """
        清理过期的临时文件

        Args:
            max_age_hours: 最大保留时间（小时）
        """
        import time

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        for item in self.temp_dir.iterdir():
            if item.is_dir():
                # 检查目录修改时间
                dir_mtime = item.stat().st_mtime
                if current_time - dir_mtime > max_age_seconds:
                    shutil.rmtree(item, ignore_errors=True)
                    logger.info(f"已清理过期临时目录: {item}")

    async def execute_smart_cut(
        self,
        task_id: str,
        video_path: str,
        config: Dict[str, Any],
        progress_callback: Callable[[int, str, int, int], None] = None
    ) -> List[Dict[str, Any]]:
        """
        执行智能裁剪

        Args:
            task_id: 任务ID
            video_path: 视频文件路径
            config: 配置参数
                - min_segment_duration: 最短片段时长（秒）
                - enable_brightness: 是否启用亮度检测
                - enable_pose: 是否启用姿态检测
                - enable_motion: 是否启用动作检测
                - enable_silence: 是否启用静音检测
            progress_callback: 进度回调函数 (progress, stage, processed_frames, total_frames)

        Returns:
            片段列表
        """
        from api.services.database import get_database_service
        from api.routers.websocket import manager as ws_manager

        # 获取视频信息
        full_video_path = self.base_dir / video_path
        video_info = self._get_video_info(str(full_video_path))

        if not video_info.get("duration"):
            raise ValueError("无法获取视频信息")

        fps = video_info.get("fps", 30)
        total_frames = video_info.get("total_frames", 0)
        min_segment_duration = config.get("min_segment_duration", 10)
        min_segment_frames = int(min_segment_duration * fps)

        # 更新任务状态
        db = get_database_service()
        await db.smart_cut_task_update(task_id, {
            "status": "processing",
            "current_stage": "初始化识别引擎"
        })

        try:
            # 导入 SmartVideoSegmenter
            try:
                from smart_segmenter import SmartVideoSegmenter
            except ImportError:
                # 尝试从 models 目录导入
                sys.path.insert(0, str(models_path))
                from smart_segmenter import SmartVideoSegmenter

            # 创建分割器实例
            async def update_progress(progress: int, stage: str, processed: int, total: int):
                if progress_callback:
                    progress_callback(progress, stage, processed, total)
                # 更新数据库
                await self._update_task_progress(task_id, progress, stage, processed, total)
                # 推送 WebSocket 进度
                await ws_manager.broadcast_to_task(task_id, {
                    "type": "smart_cut_progress",
                    "task_id": task_id,
                    "progress": progress,
                    "current_stage": stage,
                    "processed_frames": processed,
                    "total_frames": total,
                    "timestamp": datetime.now().isoformat()
                })

            # 初始化分割器
            await update_progress(5, "加载识别模型", 0, total_frames)

            segmenter = SmartVideoSegmenter(
                use_audio=config.get("enable_silence", False),
                use_motion=config.get("enable_motion", False),
                use_brightness=config.get("enable_brightness", False),
                use_pose=config.get("enable_pose", False),
                min_segment_frames=min_segment_frames
            )

            await update_progress(10, "开始智能识别", 0, total_frames)

            # 执行分割（在线程池中运行以避免阻塞）
            loop = asyncio.get_event_loop()
            segments = await loop.run_in_executor(
                None,
                lambda: segmenter.segment_video(str(full_video_path))
            )

            await update_progress(80, "生成片段文件", total_frames, total_frames)

            # 生成片段视频和缩略图
            segment_list = await self._generate_segment_files(
                task_id=task_id,
                video_path=str(full_video_path),
                segments=segments,
                fps=fps,
                progress_callback=update_progress
            )

            await update_progress(100, "识别完成", total_frames, total_frames)

            # 更新任务状态
            await db.smart_cut_task_update(task_id, {
                "status": "completed",
                "progress": 100,
                "current_stage": "识别完成",
                "segments_info": json.dumps(segment_list)
            })

            # 推送完成事件
            await ws_manager.broadcast_to_task(task_id, {
                "type": "smart_cut_completed",
                "task_id": task_id,
                "segments_count": len(segment_list),
                "segments": segment_list,
                "timestamp": datetime.now().isoformat()
            })

            logger.info(f"智能裁剪完成: {task_id}, 共 {len(segment_list)} 个片段")
            return segment_list

        except Exception as e:
            logger.error(f"智能裁剪失败: {e}")
            await db.smart_cut_task_update(task_id, {
                "status": "failed",
                "error_message": str(e)
            })

            # 推送失败事件
            try:
                from api.routers.websocket import manager as ws_manager
                await ws_manager.broadcast_to_task(task_id, {
                    "type": "smart_cut_failed",
                    "task_id": task_id,
                    "error_message": str(e),
                    "timestamp": datetime.now().isoformat()
                })
            except Exception:
                pass

            raise

    async def _update_task_progress(
        self,
        task_id: str,
        progress: int,
        stage: str,
        processed_frames: int,
        total_frames: int
    ):
        """更新任务进度"""
        from api.services.database import get_database_service

        db = get_database_service()
        await db.smart_cut_task_update(task_id, {
            "progress": progress,
            "current_stage": stage
        })

    async def _generate_segment_files(
        self,
        task_id: str,
        video_path: str,
        segments: List[tuple],
        fps: float,
        progress_callback: Callable = None
    ) -> List[Dict[str, Any]]:
        """
        生成片段视频文件和缩略图

        Args:
            task_id: 任务ID
            video_path: 原视频路径
            segments: 片段列表 [(start_frame, end_frame, reason), ...]
            fps: 帧率
            progress_callback: 进度回调

        Returns:
            片段信息列表
        """
        segment_list = []

        # 创建片段输出目录
        video_id = task_id
        output_dir = self.temp_dir / video_id / "segments"
        output_dir.mkdir(parents=True, exist_ok=True)

        total_segments = len(segments)

        for i, (start_frame, end_frame, reason) in enumerate(segments):
            segment_id = f"seg_{i+1:04d}"
            segment_path = output_dir / f"{segment_id}.mp4"
            thumbnail_path = output_dir / f"{segment_id}_thumb.jpg"

            # 计算时间
            start_time = start_frame / fps
            end_time = end_frame / fps
            duration = end_time - start_time

            # 使用 FFmpeg 提取片段
            if self._extract_segment(video_path, str(segment_path), start_time, duration):
                # 生成缩略图
                self._generate_thumbnail(str(segment_path), str(thumbnail_path))

                # 生成分段原因标签
                reason_label = self._get_reason_label(reason)

                segment_list.append({
                    "segment_id": segment_id,
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "start_time": round(start_time, 2),
                    "end_time": round(end_time, 2),
                    "duration": round(duration, 2),
                    "reason": reason,
                    "reason_label": reason_label,
                    "thumbnail": str(thumbnail_path.relative_to(self.base_dir)),
                    "video_path": str(segment_path.relative_to(self.base_dir))
                })

            # 更新进度
            if progress_callback:
                progress = 80 + int((i + 1) / total_segments * 15)
                progress_callback(progress, f"生成片段 {i+1}/{total_segments}", 0, 0)

        return segment_list

    def _extract_segment(
        self,
        video_path: str,
        output_path: str,
        start_time: float,
        duration: float
    ) -> bool:
        """
        使用 FFmpeg 提取视频片段

        Args:
            video_path: 原视频路径
            output_path: 输出路径
            start_time: 开始时间（秒）
            duration: 时长（秒）

        Returns:
            是否成功
        """
        try:
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_time),
                "-i", video_path,
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "fast",
                "-c:a", "aac",
                "-avoid_negative_ts", "make_zero",
                output_path
            ]

            creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            result = subprocess.run(
                cmd,
                capture_output=True,
                creation_flags=creation_flags
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg 提取片段失败: {result.stderr.decode()}")
                return False

            return True

        except Exception as e:
            logger.error(f"提取片段失败: {e}")
            return False

    def _get_reason_label(self, reason: str) -> str:
        """获取分割原因的中文标签"""
        reason_map = {
            "scene_change": "场景切换",
            "silence": "说话停顿",
            "motion": "手势变化",
            "brightness": "光线变化",
            "pose": "肢体动作",
            "default": "自动分割"
        }
        return reason_map.get(reason, "自动分割")

    async def extract_audio_from_segment(
        self,
        segment_path: str,
        name: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        从片段中提取音频

        Args:
            segment_path: 片段视频路径
            name: 音频名称

        Returns:
            包含 audio_path 和 duration 的字典
        """
        try:
            # 生成音频文件名
            segment_name = Path(segment_path).stem
            audio_name = name or f"{segment_name}_audio"
            audio_path = Path(segment_path).parent / f"{audio_name}.wav"

            # 使用 FFmpeg 提取音频
            cmd = [
                "ffmpeg", "-y",
                "-i", segment_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",
                str(audio_path)
            ]

            creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            result = subprocess.run(
                cmd,
                capture_output=True,
                creation_flags=creation_flags
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg 提取音频失败: {result.stderr.decode()}")
                return None

            # 获取音频时长
            duration = self._get_audio_duration(str(audio_path))

            logger.info(f"音频提取成功: {audio_path}")

            return {
                "audio_path": str(audio_path.relative_to(self.base_dir)),
                "duration": duration,
                "name": audio_name
            }

        except Exception as e:
            logger.error(f"提取音频失败: {e}")
            return None

    def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                audio_path
            ]

            creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            result = subprocess.run(cmd, capture_output=True, text=True, creation_flags=creation_flags)

            if result.returncode != 0:
                return 0.0

            data = json.loads(result.stdout)
            return float(data.get("format", {}).get("duration", 0))

        except Exception as e:
            logger.error(f"获取音频时长失败: {e}")
            return 0.0

    async def merge_segments(
        self,
        segments: List[Dict[str, str]],
        output_name: str = "",
        resolution: str = "1080p",
        fps: int = 30,
        transition: str = "none"
    ) -> Optional[Dict[str, Any]]:
        """
        合成视频片段

        Args:
            segments: 片段列表 [{"video_path": "...", "segment_id": "..."}, ...]
            output_name: 输出文件名
            resolution: 分辨率 (720p/1080p/2K)
            fps: 帧率 (30/60)
            transition: 转场效果 (none/fade/wipe)

        Returns:
            包含 output_path, duration, file_size 的字典
        """
        try:
            # 创建输出目录
            output_dir = self.base_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)

            # 生成输出文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = output_name or f"merged_{timestamp}"
            output_path = output_dir / f"{output_name}.mp4"

            # 分辨率映射
            resolution_map = {
                "720p": (1280, 720),
                "1080p": (1920, 1080),
                "2K": (2560, 1440)
            }
            width, height = resolution_map.get(resolution, (1920, 1080))

            # 构建片段文件列表
            segment_files = []
            for seg in segments:
                video_path = self.base_dir / seg["video_path"]
                if video_path.exists():
                    segment_files.append(str(video_path))

            if not segment_files:
                logger.error("没有有效的片段文件")
                return None

            creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0

            # 根据转场效果选择合成方式
            if transition != "none" and len(segment_files) > 1:
                # 使用 xfade 滤镜实现转场效果
                result = self._merge_with_transition(
                    segment_files=segment_files,
                    output_path=str(output_path),
                    width=width,
                    height=height,
                    fps=fps,
                    transition=transition,
                    creation_flags=creation_flags
                )
                if not result:
                    # 转场合成失败，回退到基础拼接
                    logger.warning("转场合成失败，回退到基础拼接")
                    transition = "none"

            if transition == "none" or len(segment_files) == 1:
                # 基础拼接（无转场）
                result = self._merge_basic(
                    segment_files=segment_files,
                    output_path=str(output_path),
                    width=width,
                    height=height,
                    fps=fps,
                    creation_flags=creation_flags
                )

            if not result:
                return None

            # 获取输出文件信息
            file_size = output_path.stat().st_size
            duration = self._get_video_duration(str(output_path))

            logger.info(f"视频合成成功: {output_path}")

            return {
                "output_path": str(output_path.relative_to(self.base_dir)),
                "duration": duration,
                "file_size": file_size
            }

        except Exception as e:
            logger.error(f"合成视频失败: {e}")
            return None

    def _merge_basic(
        self,
        segment_files: List[str],
        output_path: str,
        width: int,
        height: int,
        fps: int,
        creation_flags: int
    ) -> bool:
        """基础拼接（无转场效果）"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        concat_file = Path(output_path).parent / f"concat_{timestamp}.txt"

        try:
            with open(concat_file, "w") as f:
                for seg_path in segment_files:
                    f.write(f"file '{seg_path}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                "-r", str(fps),
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, creation_flags=creation_flags)

            if result.returncode != 0:
                logger.error(f"FFmpeg 基础合成失败: {result.stderr.decode()}")
                return False

            return True

        finally:
            concat_file.unlink(missing_ok=True)

    def _merge_with_transition(
        self,
        segment_files: List[str],
        output_path: str,
        width: int,
        height: int,
        fps: int,
        transition: str,
        creation_flags: int
    ) -> bool:
        """使用 xfade 滤镜实现转场效果"""
        try:
            # 转场映射
            transition_map = {
                "fade": "fade",
                "wipe": "wipeleft"
            }
            xfade_transition = transition_map.get(transition, "fade")
            transition_duration = 1.0  # 转场时长 1 秒

            # 获取每个片段的时长
            durations = []
            for seg_file in segment_files:
                duration = self._get_video_duration(seg_file)
                durations.append(duration)

            if len(durations) < 2:
                return False

            # 构建复杂滤镜链
            # 第一步：将所有视频缩放到统一分辨率
            inputs = []
            filter_parts = []

            for i, seg_file in enumerate(segment_files):
                inputs.extend(["-i", seg_file])
                # 缩放并设置帧率
                filter_parts.append(
                    f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                    f"fps={fps},setpts=PTS-STARTPTS[v{i}]"
                )

            # 第二步：使用 xfade 链接视频
            # 第一个转场
            offset = durations[0] - transition_duration
            filter_parts.append(f"[v0][v1]xfade=transition={xfade_transition}:duration={transition_duration}:offset={offset}[v01]")

            # 后续转场
            prev_output = "v01"
            for i in range(2, len(segment_files)):
                # 计算偏移量：前面所有视频的总时长减去已使用的转场时长
                offset = sum(durations[:i]) - transition_duration * i
                curr_output = f"v0{i}" if i < 10 else f"v{i}"
                filter_parts.append(
                    f"[{prev_output}][v{i}]xfade=transition={xfade_transition}:"
                    f"duration={transition_duration}:offset={offset}[{curr_output}]"
                )
                prev_output = curr_output

            # 最终输出标签
            final_output = prev_output

            # 构建完整命令
            cmd = ["ffmpeg", "-y"]
            cmd.extend(inputs)
            cmd.extend([
                "-filter_complex", ";".join(filter_parts),
                "-map", f"[{final_output}]",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                output_path
            ])

            result = subprocess.run(cmd, capture_output=True, creation_flags=creation_flags)

            if result.returncode != 0:
                logger.error(f"FFmpeg 转场合成失败: {result.stderr.decode()}")
                return False

            return True

        except Exception as e:
            logger.error(f"转场合成异常: {e}")
            return False

    def _get_video_duration(self, video_path: str) -> float:
        """获取视频时长"""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                video_path
            ]

            creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            result = subprocess.run(cmd, capture_output=True, text=True, creation_flags=creation_flags)

            if result.returncode != 0:
                return 0.0

            data = json.loads(result.stdout)
            return float(data.get("format", {}).get("duration", 0))

        except Exception as e:
            logger.error(f"获取视频时长失败: {e}")
            return 0.0


# 全局服务实例
_smart_cut_service: Optional[SmartCutService] = None


def get_smart_cut_service() -> SmartCutService:
    """获取智能裁剪服务实例"""
    global _smart_cut_service
    if _smart_cut_service is None:
        _smart_cut_service = SmartCutService()
    return _smart_cut_service
