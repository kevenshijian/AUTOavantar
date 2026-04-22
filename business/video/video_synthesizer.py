"""
视频合成模块
实现数字人视频生成功能（调用 HeyGem）
"""

import logging
import os
import time
import shutil
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

import requests

from core.api_clients import HeyGemClient
from core.models.task import ScriptSegment, Task, TaskConfig

logger = logging.getLogger(__name__)

# HeyGem 超时自动重启配置
HEYGEM_TIMEOUT = 240  # 秒，HeyGem 处理时间一般较长，设为 120 秒
MAX_AUTO_RESTART = 3  # 同一任务内同一服务最多自动重启 3 次


@dataclass
class VideoSegmentResult:
    """视频段落结果"""
    segment_id: str
    audio_path: str
    video_path: Optional[str]
    duration: float
    status: str  # success, failed
    error_message: Optional[str] = None
    intermediate_files: List[str] = field(default_factory=list)


class VideoSynthesizer:
    """视频合成器 - 封装 HeyGem 和视频处理功能"""

    def __init__(
        self,
        heygem_host: str = "http://localhost:9889",
        output_dir: str = "temp/video"
    ):
        """
        初始化视频合成器

        Args:
            heygem_host: HeyGem 服务地址
            output_dir: 视频输出目录
        """
        self.heygem_host = heygem_host
        self.output_dir = output_dir
        self.heygem_client: Optional[HeyGemClient] = None

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        self._init_heygem_client()

    def _init_heygem_client(self):
        """初始化 HeyGem 客户端"""
        try:
            self.heygem_client = HeyGemClient(
                host=self.heygem_host,
                output_dir=self.output_dir
            )
            logger.info(f"HeyGem 客户端初始化成功: {self.heygem_host}")
        except Exception as e:
            logger.error(f"HeyGem 客户端初始化失败: {e}")

    def generate_segment(
        self,
        segment: ScriptSegment,
        video_source: str,
        config: TaskConfig,
        task_id: Optional[str] = None
    ) -> VideoSegmentResult:
        """
        生成单个视频段落

        Args:
            segment: 文案段落（包含音频路径）
            video_source: 源视频路径
            config: 配置
            task_id: 任务ID，用于文件命名前缀

        Returns:
            视频结果
        """
        if not segment.audio_path:
            logger.error(f"段落 {segment.segment_id} 没有音频路径")
            return VideoSegmentResult(
                segment_id=segment.segment_id,
                audio_path="",
                video_path=None,
                duration=0.0,
                status="failed",
                error_message="没有音频文件"
            )

        # 检查音频文件是否存在
        audio_file_path = segment.audio_path
        if not os.path.exists(audio_file_path):
            logger.error(f"音频文件不存在: {audio_file_path}")
            # 尝试查找文件
            possible_paths = [
                audio_file_path,
                os.path.join("output", audio_file_path),
                os.path.join("..", audio_file_path),
                audio_file_path.replace("\\", "/"),
            ]
            found = False
            for p in possible_paths:
                if os.path.exists(p):
                    audio_file_path = p
                    logger.info(f"找到音频文件: {audio_file_path}")
                    found = True
                    break
            if not found:
                return VideoSegmentResult(
                    segment_id=segment.segment_id,
                    audio_path=segment.audio_path,
                    video_path=None,
                    duration=0.0,
                    status="failed",
                    error_message=f"音频文件不存在: {segment.audio_path}"
                )

        # 检查视频源文件是否存在
        if video_source and not os.path.exists(video_source):
            logger.error(f"视频源文件不存在: {video_source}")

        # 确保音频文件路径为绝对路径
        audio_file = os.path.abspath(audio_file_path).replace("\\", "/")

        # 根据场景类型选择视频，确保视频路径为绝对路径
        video_file = self._select_video(segment, video_source)
        if video_file and not os.path.isabs(video_file):
            video_file = os.path.abspath(video_file).replace("\\", "/")

        try:
            # 调用 HeyGem 生成视频（带自动重启功能）
            video_path = self._run_heygem_with_auto_restart(
                audio_path=audio_file,
                video_source=video_file,
                config=config,
                face_id=0,
                cancel_callback=None
            )

            if video_path and os.path.exists(video_path):
                # 生成文件名：使用 task_id 前缀，格式为 {task_id}_video_{segment_id}.mp4
                if task_id:
                    video_filename = f"{task_id}_video_{segment.segment_id}.mp4"
                else:
                    video_filename = f"{segment.segment_id}.mp4"
                
                output_path = self._save_video(
                    video_path,
                    video_filename
                )

                # 获取视频时长
                duration = self._get_video_duration(output_path)

                segment.video_path = output_path
                segment.duration = duration
                segment.output_path = output_path

                return VideoSegmentResult(
                    segment_id=segment.segment_id,
                    audio_path=segment.audio_path,
                    video_path=output_path,
                    duration=duration,
                    status="success"
                )

            return VideoSegmentResult(
                segment_id=segment.segment_id,
                audio_path=segment.audio_path,
                video_path=None,
                duration=0.0,
                status="failed",
                error_message="HeyGem生成失败或未返回视频"
            )

        except Exception as e:
            logger.error(f"段落 {segment.segment_id} 视频生成失败: {e}")
            return VideoSegmentResult(
                segment_id=segment.segment_id,
                audio_path=segment.audio_path,
                video_path=None,
                duration=0.0,
                status="failed",
                error_message=str(e)
            )

    def _select_video(self, segment: ScriptSegment, default_video: str) -> str:
        """根据场景和情感选择视频"""
        import os
        from core.models.task import SceneType
        
        # 情绪标签相似映射
        emotion_similarity = {
            "JOY": ["HAPPY", "EXCITED", "DELIGHTED"],
            "ANGER": ["ANGRY", "FRUSTRATED", "IRRITATED"],
            "SADNESS": ["SAD", "DEPRESSED", "GLOOMY"],
            "FEAR": ["SCARED", "AFRAID", "TERRIFIED"],
            "DISGUST": ["DISGUSTED", "REPULSED", "HORRIFIED"],
            "DEPRESSION": ["DEPRESSED", "SAD", "MELANCHOLY"],
            "SURPRISE": ["SURPRISED", "AMAZED", "ASTONISHED"],
            "CALM": ["CALM", "RELAXED", "PEACEFUL"]
        }
        
        # 场景类型到视频列表的映射
        scene_to_videos = {
            SceneType.OPENING: ["opening_video"],
            SceneType.ENDING: ["ending_video"],
            SceneType.LOOP: ["loop_videos"],
            SceneType.SCENE: ["scene_videos"]
        }
        
        # 获取当前场景类型对应的视频列表
        video_lists = scene_to_videos.get(segment.scene_type, ["loop_videos"])
        
        # 尝试根据情绪标签选择视频
        if hasattr(segment, 'emotion') and segment.emotion:
            emotion_name = segment.emotion.name
            
            # 遍历视频列表
            for video_list_name in video_lists:
                # 这里简化处理，实际应该从任务对象中获取视频列表
                # 假设任务对象有对应的视频列表属性
                pass
        
        # 如果没有找到匹配的视频，使用默认视频
        return default_video.replace("\\", "/")

    def generate_all(
        self,
        task: Task,
        config: TaskConfig,
        cancel_callback: Optional[callable] = None
    ) -> List[VideoSegmentResult]:
        """
        生成任务所有视频段落

        Args:
            task: 任务
            config: 配置

        Returns:
            视频结果列表
        """
        results = []

        # 检查是否取消
        if cancel_callback and cancel_callback():
            logger.info("任务被取消，停止视频生成")
            for segment in task.segments:
                results.append(VideoSegmentResult(
                    segment_id=segment.segment_id,
                    audio_path=segment.audio_path or "",
                    video_path=None,
                    duration=0.0,
                    status="failed",
                    error_message="任务被取消"
                ))
            return results

        # 检查任务和配置
        if not task:
            logger.error("任务对象为空")
            return results
        
        if not task.segments:
            logger.warning("任务没有段落")
            return results

        # 检查 HeyGem 客户端是否初始化
        if not self.heygem_client:
            logger.error("HeyGem 客户端未初始化")
            for segment in task.segments:
                results.append(VideoSegmentResult(
                    segment_id=segment.segment_id,
                    audio_path=segment.audio_path or "",
                    video_path=None,
                    duration=0.0,
                    status="failed",
                    error_message="HeyGem 客户端未初始化"
                ))
            return results

        # 使用源视频或开场视频作为默认视频源
        source_video = task.source_video_path or task.opening_video
        if not source_video:
            logger.error("没有提供源视频")
            for segment in task.segments:
                results.append(VideoSegmentResult(
                    segment_id=segment.segment_id,
                    audio_path=segment.audio_path or "",
                    video_path=None,
                    duration=0.0,
                    status="failed",
                    error_message="没有提供源视频"
                ))
            return results

        if not os.path.exists(source_video):
            logger.error(f"源视频文件不存在: {source_video}")
            for segment in task.segments:
                results.append(VideoSegmentResult(
                    segment_id=segment.segment_id,
                    audio_path=segment.audio_path or "",
                    video_path=None,
                    duration=0.0,
                    status="failed",
                    error_message=f"源视频文件不存在: {source_video}"
                ))
            return results

        # 处理双人模式
        if config.enable_double_mode:
            # 获取按标签分组的音频路径
            tone_audio_paths = getattr(task, 'tone_audio_paths', None)
            
            if not tone_audio_paths:
                logger.error("双人模式需要按标签分组的音频路径")
                for segment in task.segments:
                    results.append(VideoSegmentResult(
                        segment_id=segment.segment_id,
                        audio_path=segment.audio_path or "",
                        video_path=None,
                        duration=0.0,
                        status="failed",
                        error_message="双人模式需要按标签分组的音频路径"
                    ))
                return results
            
            # 检查是否所有标签都已完成（不仅仅是最终视频存在）
            # 只有当所有标签的视频都已生成时才跳过
            all_tones_completed = True
            completed_tone_videos = getattr(task, 'completed_tone_videos', {})
            
            for tone in tone_audio_paths.keys():
                if tone not in completed_tone_videos or not os.path.exists(completed_tone_videos[tone]):
                    all_tones_completed = False
                    break
            
            if task.final_video_path and os.path.exists(task.final_video_path) and all_tones_completed:
                logger.info(f"双人模式最终视频已存在且所有标签已完成，跳过生成: {task.final_video_path}")
                for segment in task.segments:
                    results.append(VideoSegmentResult(
                        segment_id=segment.segment_id,
                        audio_path=segment.audio_path or "",
                        video_path=task.final_video_path,
                        duration=segment.duration or 0.0,
                        status="success"
                    ))
                return results
            
            # 如果最终视频存在但部分标签未完成，删除旧的最终视频，重新生成
            if task.final_video_path and os.path.exists(task.final_video_path) and not all_tones_completed:
                logger.warning(f"双人模式最终视频存在但部分标签未完成，将重新生成")
                # 不删除旧视频，而是重新生成并覆盖
            
            try:
                # 存储每个标签生成的视频路径（使用字典跟踪）
                tone_video_paths = []
                # 收集所有中间文件
                all_intermediate_files = []
                
                # 初始化或恢复已完成标签视频字典
                if not hasattr(task, 'completed_tone_videos'):
                    task.completed_tone_videos = {}
                
                # 确保源视频是绝对路径
                if not os.path.isabs(source_video):
                    source_video = os.path.abspath(source_video)
                
                # 导入标签匹配器
                from .tag_matcher import get_tag_matcher
                tag_matcher = get_tag_matcher()
                
                # 创建一个临时 segment 用于标签匹配
                @dataclass
                class TempSegment:
                    tone: str
                    segment_id: str = ""
                
                # 按标签顺序处理
                for tone, audio_paths in tone_audio_paths.items():
                    # 检查是否取消
                    if cancel_callback and cancel_callback():
                        logger.info("任务被取消，停止双人模式视频生成")
                        break
                    
                    # 检查该标签是否已完成
                    if tone in completed_tone_videos and os.path.exists(completed_tone_videos[tone]):
                        logger.info(f"标签 '{tone}' 视频已完成，跳过: {completed_tone_videos[tone]}")
                        tone_video_paths.append(completed_tone_videos[tone])
                        continue
                    
                    left_audio = audio_paths.get("left")
                    right_audio = audio_paths.get("right")
                    
                    if not left_audio and not right_audio:
                        logger.warning(f"标签 '{tone}' 没有音频，跳过")
                        continue
                    
                    # 转换为绝对路径
                    if left_audio and not os.path.isabs(left_audio):
                        left_audio = os.path.abspath(left_audio)
                    if right_audio and not os.path.isabs(right_audio):
                        right_audio = os.path.abspath(right_audio)
                    
                    logger.info(f"处理标签 '{tone}': 左音频={left_audio}, 右音频={right_audio}")
                    
                    # 为当前标签匹配视频素材
                    temp_segment = TempSegment(tone=tone)
                    matched_video, is_scene_matched = self._get_scene_video(task, temp_segment)
                    
                    if not matched_video:
                        matched_video = source_video
                        is_scene_matched = False
                    
                    if not os.path.isabs(matched_video):
                        matched_video = os.path.abspath(matched_video)
                    
                    # 判断是否是场景标签且匹配成功
                    is_scene_tag = tag_matcher.is_scene_tag(tone)
                    
                    if is_scene_tag and is_scene_matched:
                        # 场景标签匹配成功：直接合并视频和音频，不调用 HeyGem
                        logger.info(f"标签 '{tone}' 场景视频匹配成功，直接合并视频和音频")
                        
                        # 合并左、右音频
                        scene_combined_audio = None
                        audio_list = []
                        if left_audio:
                            audio_list.append(left_audio)
                        if right_audio:
                            audio_list.append(right_audio)
                        
                        if audio_list:
                            scene_combined_audio = os.path.join(self.output_dir, f"scene_combined_{tone}_{task.task_id}.wav")
                            if len(audio_list) == 1:
                                scene_combined_audio = audio_list[0]
                            else:
                                if not self._concat_audio_files(audio_list, scene_combined_audio):
                                    scene_combined_audio = None
                                else:
                                    # 记录中间文件
                                    all_intermediate_files.append(scene_combined_audio)
                        
                        if scene_combined_audio:
                            # 获取音频时长
                            audio_duration = self._get_audio_duration(scene_combined_audio)
                            if audio_duration > 0:
                                # 输出文件名
                                scene_output_path = os.path.join(self.output_dir, f"scene_{tone}_{task.task_id}.mp4")
                                
                                # 使用 ffmpeg 处理：替换音频，并调整视频长度
                                success = self._replace_audio_in_video(matched_video, scene_combined_audio, scene_output_path, audio_duration)
                                
                                if success and os.path.exists(scene_output_path):
                                    tone_video_paths.append(scene_output_path)
                                    # 记录已完成的标签视频
                                    task.completed_tone_videos[tone] = scene_output_path
                                    # 记录中间文件（如果不是最终输出）
                                    all_intermediate_files.append(scene_output_path)
                                    logger.info(f"标签 '{tone}' 场景视频生成完成: {scene_output_path}")
                                else:
                                    logger.error(f"标签 '{tone}' 场景视频生成失败")
                    else:
                        # 非场景标签：调用 HeyGem 合成，先左后右
                        current_source = matched_video
                        left_result = None
                        
                        # 第一次推理：左边说话人，使用 face_id=0
                        if left_audio and os.path.exists(left_audio):
                            logger.info(f"标签 '{tone}' 执行第一次 HeyGem 推理（左边说话人），视频源: {current_source}")
                            left_result = self._run_heygem_inference(left_audio, current_source, config, face_id=0, cancel_callback=cancel_callback)
                            # 如果任务被取消，跳出循环
                            if cancel_callback and cancel_callback():
                                logger.info(f"标签 '{tone}' 第一次推理后检测到任务已取消")
                                break
                            # 记录第一次推理结果作为中间文件
                            if left_result and os.path.exists(left_result):
                                all_intermediate_files.append(left_result)
                            current_source = left_result
                        else:
                            left_result = current_source
                            if left_audio:
                                logger.warning(f"标签 '{tone}' 左边音频文件不存在: {left_audio}")
                        
                        # 第二次推理：右边说话人，使用 face_id=1
                        if right_audio and os.path.exists(right_audio):
                            logger.info(f"标签 '{tone}' 执行第二次 HeyGem 推理（右边说话人）...")
                            right_result = self._run_heygem_inference(right_audio, left_result, config, face_id=1, cancel_callback=cancel_callback)
                            # 如果任务被取消，跳出循环
                            if cancel_callback and cancel_callback():
                                logger.info(f"标签 '{tone}' 第二次推理后检测到任务已取消")
                                break
                            # 记录第二次推理结果作为中间文件
                            if right_result and os.path.exists(right_result):
                                all_intermediate_files.append(right_result)
                            
                            # 方案 2：直接使用原始左右音频合并（新方案）
                            final_video_with_both_audio = None
                            if right_result and os.path.exists(right_result):
                                final_output_path = os.path.join(self.output_dir, f"final_{tone}_{task.task_id}.mp4")
                                final_video_with_both_audio = self._merge_left_right_audio_to_video(
                                    video_path=right_result,
                                    left_audio_path=left_audio,
                                    right_audio_path=right_audio,
                                    output_path=final_output_path
                                )
                            
                            # 使用合并了两个声音的视频
                            if final_video_with_both_audio and os.path.exists(final_video_with_both_audio):
                                tone_video_paths.append(final_video_with_both_audio)
                                # 记录已完成的标签视频
                                task.completed_tone_videos[tone] = final_video_with_both_audio
                                # 记录中间文件
                                all_intermediate_files.append(final_output_path)
                                logger.info(f"标签 '{tone}' 视频生成完成（含左右声音）: {final_video_with_both_audio}")
                            else:
                                # 如果合并失败，回退到只有右边声音的视频
                                tone_video_paths.append(right_result)
                                # 记录已完成的标签视频
                                task.completed_tone_videos[tone] = right_result
                                logger.warning(f"标签 '{tone}' 音频合并失败，使用只有右边声音的视频: {right_result}")
                        else:
                            # 如果没有右边音频，使用左边结果
                            tone_video_paths.append(left_result)
                            # 记录已完成的标签视频
                            if left_result:
                                task.completed_tone_videos[tone] = left_result
                            if right_audio:
                                logger.warning(f"标签 '{tone}' 右边音频文件不存在: {right_audio}")
                
                # 合并所有标签的视频
                if len(tone_video_paths) == 1:
                    final_video = tone_video_paths[0]
                elif len(tone_video_paths) > 1:
                    final_video = self._concat_videos(tone_video_paths, task.task_id)
                    # 记录合并后的视频作为中间文件
                    if final_video:
                        merged_path = os.path.join(self.output_dir, f"merged_{task.task_id}.mp4")
                        if final_video == merged_path:
                            all_intermediate_files.append(merged_path)
                else:
                    final_video = None
                
                # 从中间文件列表中移除最终输出视频
                if final_video and final_video in all_intermediate_files:
                    all_intermediate_files.remove(final_video)
                
                if final_video:
                    task.final_video_path = final_video
                    logger.info(f"双人模式视频生成完成: {final_video}")
                    logger.info(f"双人模式中间文件: {all_intermediate_files}")
                    
                    # 为每个段落创建结果
                    for segment in task.segments:
                        results.append(VideoSegmentResult(
                            segment_id=segment.segment_id,
                            audio_path=segment.audio_path or "",
                            video_path=final_video,
                            duration=segment.duration or 0.0,
                            status="success",
                            intermediate_files=all_intermediate_files
                        ))
                else:
                    logger.error("双人模式视频生成失败：没有生成任何视频")
                    for segment in task.segments:
                        results.append(VideoSegmentResult(
                            segment_id=segment.segment_id,
                            audio_path=segment.audio_path or "",
                            video_path=None,
                            duration=0.0,
                            status="failed",
                            error_message="双人模式视频生成失败：没有生成任何视频"
                        ))
                
                task.progress = 90
            except Exception as e:
                logger.error(f"双人模式视频生成失败: {e}")
                for segment in task.segments:
                    results.append(VideoSegmentResult(
                        segment_id=segment.segment_id,
                        audio_path=segment.audio_path or "",
                        video_path=None,
                        duration=0.0,
                        status="failed",
                        error_message=str(e)
                    ))
        else:
            # 单人模式
            # 根据场景类型分配视频
            from .tag_matcher import get_tag_matcher
            tag_matcher = get_tag_matcher()
            
            for i, segment in enumerate(task.segments):
                if cancel_callback and cancel_callback():
                    logger.info("任务被取消，停止单人模式视频生成")
                    break
                
                if segment.output_path and os.path.exists(segment.output_path):
                    logger.info(f"段落 {segment.segment_id} 视频已存在，跳过生成: {segment.output_path}")
                    results.append(VideoSegmentResult(
                        segment_id=segment.segment_id,
                        audio_path=segment.audio_path or "",
                        video_path=segment.output_path,
                        duration=segment.duration or 0.0,
                        status="success"
                    ))
                    continue
                
                try:
                    # 检查段落是否有音频
                    if not segment.audio_path:
                        logger.error(f"段落 {segment.segment_id} 没有音频路径")
                        results.append(VideoSegmentResult(
                            segment_id=segment.segment_id,
                            audio_path="",
                            video_path=None,
                            duration=0.0,
                            status="failed",
                            error_message="没有音频文件"
                        ))
                        continue

                    # 检查音频文件是否存在
                    if not os.path.exists(segment.audio_path):
                        logger.error(f"音频文件不存在: {segment.audio_path}")
                        results.append(VideoSegmentResult(
                            segment_id=segment.segment_id,
                            audio_path=segment.audio_path,
                            video_path=None,
                            duration=0.0,
                            status="failed",
                            error_message=f"音频文件不存在: {segment.audio_path}"
                        ))
                        continue

                    # 选择对应场景的视频
                    video_source, is_scene_matched = self._get_scene_video(task, segment)
                    
                    # 检查是否是场景标签且匹配成功
                    tone = getattr(segment, 'tone', '')
                    if tag_matcher.is_scene_tag(tone) and is_scene_matched and video_source:
                        # 场景视频匹配成功：不需要调用 HeyGem 合成，直接使用匹配到的视频，然后合并音频
                        logger.info(f"段落 {segment.segment_id} 场景标签 '{tone}' 匹配成功，跳过 HeyGem 合成，直接使用匹配视频: {video_source}")
                        result = self._process_scene_video(segment, video_source, task_id=task.task_id)
                        results.append(result)
                    else:
                        # 非场景视频或场景视频匹配失败：正常调用 HeyGem 合成
                        if tag_matcher.is_scene_tag(tone) and not is_scene_matched:
                            logger.info(f"段落 {segment.segment_id} 场景标签 '{tone}' 匹配失败，使用开场视频并调用 HeyGem 合成")
                        result = self.generate_segment(
                            segment=segment,
                            video_source=video_source or source_video,
                            config=config,
                            task_id=task.task_id
                        )
                        results.append(result)

                    # 更新进度
                    task.progress = 50 + (i + 1) / len(task.segments) * 40

                    time.sleep(1)  # 避免并发过高
                except Exception as e:
                    logger.error(f"生成视频段落 {segment.segment_id} 时发生异常: {e}")
                    results.append(VideoSegmentResult(
                        segment_id=segment.segment_id,
                        audio_path=segment.audio_path or "",
                        video_path=None,
                        duration=0.0,
                        status="failed",
                        error_message=str(e)
                    ))

        return results
    
    def _process_scene_video(self, segment: ScriptSegment, video_path: str, task_id: Optional[str] = None) -> VideoSegmentResult:
        """
        处理场景视频：不需要调用 HeyGem 合成，直接将音频合并到视频中并对齐长度
        
        Args:
            segment: 文案段落
            video_path: 匹配到的场景视频路径
            task_id: 任务ID，用于文件命名前缀
            
        Returns:
            处理结果
        """
        if not os.path.exists(video_path):
            logger.error(f"场景视频不存在: {video_path}")
            return VideoSegmentResult(
                segment_id=segment.segment_id,
                audio_path=segment.audio_path or "",
                video_path=None,
                duration=0.0,
                status="failed",
                error_message=f"场景视频不存在: {video_path}"
            )
        
        if not segment.audio_path or not os.path.exists(segment.audio_path):
            logger.error(f"音频文件不存在: {segment.audio_path}")
            return VideoSegmentResult(
                segment_id=segment.segment_id,
                audio_path=segment.audio_path or "",
                video_path=None,
                duration=0.0,
                status="failed",
                error_message="音频文件不存在"
            )
        
        try:
            # 获取音频时长
            audio_duration = self._get_audio_duration(segment.audio_path)
            
            # 获取视频时长
            video_duration = self._get_video_duration(video_path)
            
            if audio_duration <= 0 or video_duration <= 0:
                logger.error(f"无法获取音视频时长: 音频={audio_duration}, 视频={video_duration}")
                raise Exception(f"无法获取音视频时长: 音频={audio_duration}, 视频={video_duration}")
            
            logger.info(f"场景视频处理: 音频时长={audio_duration:.2f}s, 视频时长={video_duration:.2f}s")
            
            # 输出文件名：使用 task_id 前缀
            if task_id:
                output_filename = f"{task_id}_scene_{segment.segment_id}.mp4"
            else:
                output_filename = f"scene_{segment.segment_id}.mp4"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # 使用 ffmpeg 处理：替换音频，并调整视频长度
            success = self._replace_audio_in_video(video_path, segment.audio_path, output_path, audio_duration)
            
            if not success or not os.path.exists(output_path):
                logger.error(f"场景视频处理失败，输出文件不存在")
                raise Exception("场景视频处理失败，输出文件不存在")
            
            # 更新段落信息
            segment.video_path = output_path
            segment.duration = audio_duration
            segment.output_path = output_path
            
            logger.info(f"场景视频 {segment.segment_id} 处理完成: {output_path}")
            
            return VideoSegmentResult(
                segment_id=segment.segment_id,
                audio_path=segment.audio_path,
                video_path=output_path,
                duration=audio_duration,
                status="success"
            )
            
        except Exception as e:
            logger.error(f"处理场景视频 {segment.segment_id} 失败: {e}")
            return VideoSegmentResult(
                segment_id=segment.segment_id,
                audio_path=segment.audio_path or "",
                video_path=None,
                duration=0.0,
                status="failed",
                error_message=str(e)
            )
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        try:
            import subprocess
            
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ]
            
            logger.info(f"执行 ffprobe 获取音频时长: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            
            if result.returncode != 0:
                stderr = result.stderr.decode('utf-8', errors='ignore')
                logger.error(f"ffprobe 执行失败: {stderr}")
                return -1.0
            
            duration_str = result.stdout.decode('utf-8', errors='ignore').strip()
            if not duration_str:
                logger.error(f"ffprobe 返回空结果")
                return -1.0
            
            duration = float(duration_str)
            logger.info(f"音频时长获取成功: {duration:.2f}s")
            return duration
            
        except subprocess.TimeoutExpired:
            logger.error(f"获取音频时长超时: {audio_path}")
            return -1.0
        except ValueError as e:
            logger.error(f"解析音频时长失败: {e}")
            return -1.0
        except Exception as e:
            logger.error(f"获取音频时长失败: {e}")
            return -1.0
    
    def _replace_audio_in_video(self, video_path: str, audio_path: str, output_path: str, target_duration: float) -> bool:
        """
        替换视频中的音频，并确保输出时长等于目标音频时长
        
        Args:
            video_path: 输入视频路径
            audio_path: 新音频路径
            output_path: 输出路径
            target_duration: 目标时长（音频时长）
            
        Returns:
            是否成功
        """
        import subprocess
        
        video_duration = self._get_video_duration(video_path)
        
        if video_duration <= 0:
            logger.error(f"无法获取视频时长: {video_duration}")
            return False
        
        logger.info(f"视频时长: {video_duration:.2f}s, 目标时长: {target_duration:.2f}s")
        
        if target_duration <= video_duration:
            # 音频时长小于等于视频时长：直接裁剪视频
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-t', str(target_duration),
                output_path
            ]
        else:
            # 音频时长大于视频时长：循环播放视频
            import math
            loop_count = int(math.ceil(target_duration / video_duration))
            logger.info(f"需要循环播放视频 {loop_count} 次")
            
            cmd = [
                'ffmpeg', '-y',
                '-stream_loop', str(loop_count - 1),
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-t', str(target_duration),
                '-shortest',
                output_path
            ]
        
        logger.info(f"执行 ffmpeg 处理场景视频: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode != 0:
            stderr = result.stderr.decode('utf-8', errors='ignore')
            logger.error(f"ffmpeg 执行失败: {stderr}")
            return False
        
        logger.info(f"ffmpeg 执行成功，输出: {output_path}")
        return True

    def _get_scene_video(self, task: Task, segment: ScriptSegment) -> tuple:
        """
        根据场景类型和文案标签获取匹配的视频素材
        按照需求文档重新实现匹配逻辑：
        1. 开场/结束标签 → 固定匹配开场/结束视频
        2. 情绪类标签 → 在循环视频区域匹配，映射到8个标准标签，相同标签随机选择
        3. 场景类标签 → 在场景视频区域匹配，支持相似标签，相同标签随机选择
        4. 如果没有匹配 → 使用开场视频作为后备
        
        Args:
            task: 任务对象
            segment: 文案段落，包含标签（tone）
            
        Returns:
            tuple: (视频路径, 是否匹配成功)
            - 视频路径：匹配的视频路径，如果没有匹配则返回后备的开场视频
            - 是否匹配成功：True 表示成功匹配到场景视频，False 表示回退到开场视频
        """
        from .tag_matcher import get_tag_matcher
        
        tag_matcher = get_tag_matcher()
        # 标签数据在服务启动时和设置变更时已加载，无需每次重新加载
        tone = getattr(segment, 'tone', '')
        
        if not tone:
            logger.warning(f"段落 {segment.segment_id} 没有标签，使用开场视频")
            return (self._get_fallback_video(task), False)
        
        # ==================== 规则 1: 开场/结束标签 ====================
        if tone == "开场":
            if task.opening_video_with_tags:
                return (task.opening_video_with_tags.file_path, False)
            elif task.opening_video:
                return (task.opening_video, False)
            else:
                return (self._get_fallback_video(task), False)
        
        if tone == "结束":
            if task.ending_video_with_tags:
                return (task.ending_video_with_tags.file_path, False)
            elif task.ending_video:
                return (task.ending_video, False)
            else:
                return (self._get_fallback_video(task), False)
        
        # ==================== 规则 2: 场景类标签 ====================
        if tag_matcher.is_scene_tag(tone):
            scene_video_list = self._collect_scene_videos(task)
            if not scene_video_list:
                logger.warning(f"段落 {segment.segment_id} 场景标签 '{tone}' 没有场景视频，使用开场视频")
                return (self._get_fallback_video(task), False)
            
            match_result = tag_matcher.match_scene_video(tone, scene_video_list)
            if match_result:
                return (match_result.video_path, True)
            
            logger.warning(f"段落 {segment.segment_id} 场景标签 '{tone}' 匹配失败，使用开场视频")
            return (self._get_fallback_video(task), False)
        
        # ==================== 规则 3: 情绪类标签 ====================
        if tag_matcher.is_emotion_tag(tone):
            loop_video_list = self._collect_loop_videos(task)
            if not loop_video_list:
                logger.warning(f"段落 {segment.segment_id} 情绪标签 '{tone}' 没有循环视频，使用开场视频")
                return (self._get_fallback_video(task), False)
            
            match_result = tag_matcher.match_emotion_video(tone, loop_video_list)
            if match_result:
                return (match_result.video_path, False)
            
            logger.warning(f"段落 {segment.segment_id} 情绪标签 '{tone}' 匹配失败，使用开场视频")
            return (self._get_fallback_video(task), False)
        
        # ==================== 未知标签 ====================
        logger.warning(f"段落 {segment.segment_id} 未知标签 '{tone}'，使用开场视频")
        return (self._get_fallback_video(task), False)
    
    def _collect_scene_videos(self, task: Task) -> List[Dict]:
        """
        收集所有场景视频，转换为统一格式
        
        Args:
            task: 任务对象
            
        Returns:
            场景视频列表，每个元素是 {'file_path': str, 'scene_tags': List[str]}
        """
        result = []
        
        # 处理带标签的场景视频
        if hasattr(task, 'scene_videos_with_tags') and task.scene_videos_with_tags:
            for video in task.scene_videos_with_tags:
                result.append({
                    'file_path': video.file_path,
                    'scene_tags': video.scene_tags
                })
        
        # 如果没有带标签的，尝试从旧接口获取
        if not result and hasattr(task, 'scene_videos') and task.scene_videos:
            for video_path in task.scene_videos:
                scene_tags = []
                # 从文件名提取标签
                for tag in ["环境展示", "产品展示", "细节展示", "功能介绍", "使用效果"]:
                    if tag in video_path:
                        scene_tags.append(tag)
                result.append({
                    'file_path': video_path,
                    'scene_tags': scene_tags
                })
        
        return result
    
    def _collect_loop_videos(self, task: Task) -> List[Dict]:
        """
        收集所有循环视频，转换为统一格式
        
        Args:
            task: 任务对象
            
        Returns:
            循环视频列表，每个元素是 {'file_path': str, 'emotion_tags': List[str]}
        """
        result = []
        
        # 处理带标签的循环视频
        if hasattr(task, 'loop_videos_with_tags') and task.loop_videos_with_tags:
            for video in task.loop_videos_with_tags:
                result.append({
                    'file_path': video.file_path,
                    'emotion_tags': video.emotion_tags
                })
        
        # 如果没有带标签的，尝试从旧接口获取
        if not result and hasattr(task, 'loop_videos') and task.loop_videos:
            standard_emotions = ["开心", "生气", "难过", "害怕", "厌恶", "低落", "惊喜", "冷静"]
            for video_path in task.loop_videos:
                emotion_tags = []
                # 从文件名提取标签
                for emotion in standard_emotions:
                    if emotion in video_path:
                        emotion_tags.append(emotion)
                result.append({
                    'file_path': video_path,
                    'emotion_tags': emotion_tags
                })
        
        return result
    
    def _get_fallback_video(self, task: Task) -> str:
        """
        获取后备视频（开场视频）
        
        Args:
            task: 任务对象
            
        Returns:
            后备视频路径
        """
        if task.opening_video_with_tags:
            return task.opening_video_with_tags.file_path
        if task.opening_video:
            return task.opening_video
        return task.source_video_path

    def _run_heygem_with_auto_restart(
        self,
        audio_path: str,
        video_source: str,
        config: TaskConfig,
        face_id: int = -1,
        cancel_callback=None
    ) -> str:
        """
        带自动重启的 HeyGem 推理
        
        捕获超时后自动重启 HeyGem 服务并重试，
        超过 MAX_AUTO_RESTART 次后抛出异常。
        
        Args:
            audio_path: 音频文件路径
            video_source: 视频源路径
            config: 任务配置
            face_id: 面部编号
            cancel_callback: 取消回调函数
            
        Returns:
            生成的视频路径
            
        Raises:
            Exception: 超过最大重启次数仍失败
        """
        restart_count = 0
        
        while True:
            # 检查是否取消
            if cancel_callback and cancel_callback():
                raise Exception("任务被取消")
            
            try:
                # 调用 HeyGem 生成视频（带超时）
                result = self._run_heygem_inference_with_timeout(
                    audio_path=audio_path,
                    video_source=video_source,
                    config=config,
                    face_id=face_id,
                    timeout=HEYGEM_TIMEOUT
                )
                
                return result
                
            except requests.Timeout:
                restart_count += 1
                if restart_count > MAX_AUTO_RESTART:
                    raise Exception(f"HeyGem 多次重启仍无响应 (已重启 {restart_count - 1} 次)")
                
                logger.warning(
                    f"HeyGem 请求超时 ({HEYGEM_TIMEOUT}s)，自动重启 "
                    f"({restart_count}/{MAX_AUTO_RESTART})"
                )
                
                # 获取 ServiceManager 并重启 HeyGem
                from core.service_manager import get_service_manager
                sm = get_service_manager()
                if sm:
                    try:
                        sm.restart_service("heygem")
                        logger.info("HeyGem 服务重启完成，继续任务")
                    except Exception as e:
                        logger.error(f"HeyGem 服务重启失败: {e}")
                        raise
                else:
                    raise Exception("ServiceManager 未初始化，无法自动重启")
                    
            except (FileNotFoundError, OSError) as e:
                # 文件不存在错误（如 [Errno 2] No such file or directory），需要重启服务
                restart_count += 1
                if restart_count > MAX_AUTO_RESTART:
                    raise Exception(f"HeyGem 多次重启仍无法找到文件 (已重启 {restart_count - 1} 次): {e}")
                
                logger.warning(
                    f"HeyGem 返回文件不存在错误: {e}，自动重启服务 "
                    f"({restart_count}/{MAX_AUTO_RESTART})"
                )
                
                # 获取 ServiceManager 并重启 HeyGem
                from core.service_manager import get_service_manager
                sm = get_service_manager()
                if sm:
                    try:
                        sm.restart_service("heygem")
                        logger.info("HeyGem 服务重启完成，继续任务")
                    except Exception as restart_e:
                        logger.error(f"HeyGem 服务重启失败: {restart_e}")
                        raise
                else:
                    raise Exception("ServiceManager 未初始化，无法自动重启")
            
            except requests.ConnectionError as e:
                # 连接错误（如 [WinError 10061] 由于目标计算机积极拒绝，无法连接），需要重启服务
                restart_count += 1
                if restart_count > MAX_AUTO_RESTART:
                    raise Exception(f"HeyGem 多次重启仍无法连接 (已重启 {restart_count - 1} 次): {e}")
                
                logger.warning(
                    f"HeyGem 连接被拒绝，可能是服务启动失败或卡顿: {e}，自动重启服务 "
                    f"({restart_count}/{MAX_AUTO_RESTART})"
                )
                
                # 获取 ServiceManager 并重启 HeyGem
                from core.service_manager import get_service_manager
                sm = get_service_manager()
                if sm:
                    try:
                        sm.restart_service("heygem")
                        logger.info("HeyGem 服务重启完成，继续任务")
                    except Exception as restart_e:
                        logger.error(f"HeyGem 服务重启失败: {restart_e}")
                        raise
                else:
                    raise Exception("ServiceManager 未初始化，无法自动重启")
                    
            except Exception as e:
                # 其他异常，直接抛出
                raise

    def _run_heygem_inference_with_timeout(
        self,
        audio_path: str,
        video_source: str,
        config: TaskConfig,
        face_id: int = -1,
        timeout: int = HEYGEM_TIMEOUT
    ) -> str:
        """
        带超时的 HeyGem 推理
        
        直接调用 HeyGem API，不使用 tenacity 重试，确保超时能被正确捕获
        
        Args:
            audio_path: 音频文件路径
            video_source: 视频源路径
            config: 任务配置
            face_id: 面部编号
            timeout: 超时时间（秒）
            
        Returns:
            生成的视频路径
            
        Raises:
            requests.Timeout: 请求超时
        """
        import requests
        import uuid
        
        # 生成唯一的输出文件名
        unique_id = str(uuid.uuid4())[:8]
        output_filename = f"heygem_output_{unique_id}.mp4"
        output_path = os.path.join(self.output_dir, output_filename)
        
        # 构建请求参数
        params = {
            "video_file": video_source,
            "audio_file": audio_path,
            "ifface": str(config.heygem_ifface).lower(),
            "face_id": face_id,
            "steps": config.heygem_steps
        }
        
        logger.info(f"调用 HeyGem API (带超时 {timeout}s): {self.heygem_host}/")
        
        # 直接发送请求，不使用 tenacity 重试，确保超时能被正确捕获
        response = self.heygem_client.session.get(
            self.heygem_host,
            params=params,
            timeout=timeout
        )
        
        if response.status_code != 200:
            error_msg = f"HeyGem API 请求失败: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
        
        # 解析响应
        result = response.json()
        status = result.get("status")
        
        if status != "success":
            error_msg = result.get("message", "未知错误")
            logger.error(f"HeyGem 任务失败: {error_msg}")
            raise RuntimeError(f"HeyGem 任务失败: {error_msg}")
        
        # 获取输出视频 URL（使用与原 generate_video 方法相同的字段名）
        output_video_url = result.get("output_video_url")
        
        # 检查 URL 是否有效（非空且非空字符串）
        if not output_video_url or not output_video_url.strip():
            error_msg = result.get("message", "未知错误")
            logger.error(f"HeyGem 返回无效的视频 URL: '{output_video_url}', 错误信息: {error_msg}")
            raise ValueError(f"HeyGem 返回无效的视频 URL: '{output_video_url}'")
        
        logger.info(f"HeyGem 任务成功完成")
        logger.info(f"输出视频 URL: {output_video_url}")
        
        # 下载视频文件到本地（复用 HeyGemClient 的下载逻辑）
        actual_path = self._download_video_from_url(output_video_url)
        
        if not actual_path:
            raise Exception(f"无法下载视频: {output_video_url}")
        
        # 保存视频到输出目录
        import shutil
        if os.path.exists(actual_path):
            shutil.copy2(actual_path, output_path)
            # 删除原始下载文件
            if actual_path != output_path and os.path.exists(actual_path):
                try:
                    os.remove(actual_path)
                    logger.debug(f"已删除原始视频文件: {actual_path}")
                except Exception as e:
                    logger.warning(f"删除原始视频文件失败: {actual_path}, 错误: {e}")
            # 返回绝对路径
            abs_output_path = os.path.abspath(output_path)
            logger.info(f"HeyGem 推理成功，视频已保存到: {abs_output_path}")
            return abs_output_path
        else:
            raise Exception(f"生成的视频文件不存在: {actual_path}")

    def _run_heygem_inference(self, audio_path: str, video_source: str, config: TaskConfig, face_id: int = -1, cancel_callback=None) -> str:
        """
        执行 HeyGem 推理（带自动重启）

        捕获超时或文件不存在错误后自动重启 HeyGem 服务并重试，
        超过 MAX_AUTO_RESTART 次后抛出异常。

        Args:
            audio_path: 音频路径
            video_source: 视频源路径
            config: 配置
            face_id: 驱动人脸序号，0=第一张，-1=所有脸
            cancel_callback: 取消回调函数，返回 True 表示任务已取消

        Returns:
            生成的视频路径
        """
        restart_count = 0
        
        while True:
            # 检查是否取消
            if cancel_callback and cancel_callback():
                raise Exception("任务被取消")
            
            try:
                return self._run_heygem_inference_once(
                    audio_path=audio_path,
                    video_source=video_source,
                    config=config,
                    face_id=face_id,
                    cancel_callback=cancel_callback
                )
                
            except requests.Timeout:
                restart_count += 1
                if restart_count > MAX_AUTO_RESTART:
                    raise Exception(f"HeyGem 多次重启仍无响应 (已重启 {restart_count - 1} 次)")
                
                logger.warning(
                    f"HeyGem 请求超时 (300s)，自动重启 "
                    f"({restart_count}/{MAX_AUTO_RESTART})"
                )
                
                # 获取 ServiceManager 并重启 HeyGem
                from core.service_manager import get_service_manager
                sm = get_service_manager()
                if sm:
                    try:
                        sm.restart_service("heygem")
                        logger.info("HeyGem 服务重启完成，继续任务")
                    except Exception as e:
                        logger.error(f"HeyGem 服务重启失败: {e}")
                        raise
                else:
                    raise Exception("ServiceManager 未初始化，无法自动重启")
                    
            except (FileNotFoundError, OSError) as e:
                # 文件不存在错误（如 [Errno 2] No such file or directory），需要重启服务
                restart_count += 1
                if restart_count > MAX_AUTO_RESTART:
                    raise Exception(f"HeyGem 多次重启仍无法找到文件 (已重启 {restart_count - 1} 次): {e}")
                
                logger.warning(
                    f"HeyGem 返回文件不存在错误: {e}，自动重启服务 "
                    f"({restart_count}/{MAX_AUTO_RESTART})"
                )
                
                # 获取 ServiceManager 并重启 HeyGem
                from core.service_manager import get_service_manager
                sm = get_service_manager()
                if sm:
                    try:
                        sm.restart_service("heygem")
                        logger.info("HeyGem 服务重启完成，继续任务")
                    except Exception as restart_e:
                        logger.error(f"HeyGem 服务重启失败: {restart_e}")
                        raise
                else:
                    raise Exception("ServiceManager 未初始化，无法自动重启")
            
            except requests.ConnectionError as e:
                # 连接错误（如 [WinError 10061] 由于目标计算机积极拒绝，无法连接），需要重启服务
                restart_count += 1
                if restart_count > MAX_AUTO_RESTART:
                    raise Exception(f"HeyGem 多次重启仍无法连接 (已重启 {restart_count - 1} 次): {e}")
                
                logger.warning(
                    f"HeyGem 连接被拒绝，可能是服务启动失败或卡顿: {e}，自动重启服务 "
                    f"({restart_count}/{MAX_AUTO_RESTART})"
                )
                
                # 获取 ServiceManager 并重启 HeyGem
                from core.service_manager import get_service_manager
                sm = get_service_manager()
                if sm:
                    try:
                        sm.restart_service("heygem")
                        logger.info("HeyGem 服务重启完成，继续任务")
                    except Exception as restart_e:
                        logger.error(f"HeyGem 服务重启失败: {restart_e}")
                        raise
                else:
                    raise Exception("ServiceManager 未初始化，无法自动重启")
                    
            except Exception as e:
                # 其他异常，直接抛出
                raise
    
    def _run_heygem_inference_once(self, audio_path: str, video_source: str, config: TaskConfig, face_id: int = -1, cancel_callback=None) -> str:
        """
        执行单次 HeyGem 推理（不带自动重启）

        Args:
            audio_path: 音频路径
            video_source: 视频源路径
            config: 配置
            face_id: 驱动人脸序号，0=第一张，-1=所有脸
            cancel_callback: 取消回调函数，返回 True 表示任务已取消

        Returns:
            生成的视频路径
        """
        import os
        
        # 调用前检查取消状态
        if cancel_callback and cancel_callback():
            logger.info("HeyGem 推理前检测到任务已取消，跳过推理")
            return None
        
        # 生成唯一的输出文件名
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        output_filename = f"heygem_output_{unique_id}.mp4"
        output_path = os.path.join(self.output_dir, output_filename)
        
        # 执行推理（使用无tenacity的调用方式）
        try:
            # 直接调用API，不通过generate_video方法（避免tenacity重试）
            import requests
            
            # 构建请求参数
            params = {
                "video_file": video_source,
                "audio_file": audio_path,
                "ifface": str(config.heygem_ifface).lower(),
                "face_id": face_id,
                "steps": config.heygem_steps
            }
            
            logger.info(f"调用 HeyGem API: {self.heygem_host}/")
            
            # 直接发送请求，不使用 tenacity 重试
            response = self.heygem_client.session.get(
                self.heygem_host,
                params=params,
                timeout=300  # 5分钟超时
            )
            
            if response.status_code != 200:
                error_msg = f"HeyGem API 请求失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise ConnectionError(error_msg)
            
            # 解析响应
            result = response.json()
            status = result.get("status")
            
            if status != "success":
                error_msg = result.get("message", "未知错误")
                logger.error(f"HeyGem 任务失败: {error_msg}")
                raise RuntimeError(f"HeyGem 任务失败: {error_msg}")
            
            # 获取输出视频 URL
            output_video_url = result.get("output_video_url")
            
            # 检查 URL 是否有效
            if not output_video_url or not output_video_url.strip():
                error_msg = result.get("message", "未知错误")
                logger.error(f"HeyGem 返回无效的视频 URL: '{output_video_url}', 错误信息: {error_msg}")
                raise ValueError(f"HeyGem 返回无效的视频 URL: '{output_video_url}'")
            
            logger.info(f"HeyGem 任务成功完成")
            logger.info(f"输出视频 URL: {output_video_url}")
            
            # 下载视频文件到本地
            video_path = self._download_video_from_url(output_video_url)
            
            if not video_path:
                raise Exception(f"无法下载视频: {output_video_url}")
            
            # 调用后检查取消状态
            if cancel_callback and cancel_callback():
                logger.info("HeyGem 推理完成后检测到任务已取消，丢弃结果")
                return None
            
            # 保存视频到输出目录
            import shutil
            if os.path.exists(video_path):
                shutil.copy2(video_path, output_path)
                # 删除原始下载文件，避免占用磁盘空间
                if video_path != output_path and os.path.exists(video_path):
                    try:
                        os.remove(video_path)
                        logger.debug(f"已删除原始视频文件: {video_path}")
                    except Exception as e:
                        logger.warning(f"删除原始视频文件失败: {video_path}, 错误: {e}")
                # 返回绝对路径，确保后续调用能找到文件
                abs_output_path = os.path.abspath(output_path)
                logger.info(f"HeyGem 推理成功，视频已保存到: {abs_output_path}")
                return abs_output_path
            else:
                raise Exception(f"生成的视频文件不存在: {video_path}")
        except Exception as e:
            logger.error(f"HeyGem 推理执行失败: {e}")
            raise

    def _download_video_from_url(self, video_url: str) -> Optional[str]:
        """
        从 URL 下载视频文件到本地
        
        Args:
            video_url: 视频 URL
            
        Returns:
            本地视频文件路径，失败返回 None
        """
        try:
            # 从 URL 中提取文件名，或生成临时文件名
            if video_url.startswith("http"):
                filename = os.path.basename(video_url)
                if not filename or not filename.endswith(".mp4"):
                    filename = f"video_{int(time.time())}.mp4"
            else:
                # 如果是本地路径，直接返回
                if os.path.exists(video_url):
                    return video_url
                filename = os.path.basename(video_url)
            
            # 确定保存目录
            save_path = os.path.join(self.output_dir, filename)
            
            # 如果是本地路径，尝试复制
            if not video_url.startswith("http"):
                if os.path.exists(video_url):
                    import shutil
                    shutil.copy2(video_url, save_path)
                    logger.info(f"视频已复制: {video_url} -> {save_path}")
                    return save_path
                else:
                    logger.warning(f"视频文件不存在: {video_url}")
                    return None
            
            # 从 URL 下载
            logger.info(f"正在下载视频: {video_url}")
            response = self.heygem_client.session.get(video_url, timeout=300)
            
            if response.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"视频已下载: {save_path}")
                return save_path
            else:
                logger.error(f"下载视频失败: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"下载视频时出错: {e}")
            return None

    def _save_video(self, source_path: str, filename: str) -> str:
        """保存视频到输出目录（移动而非复制，避免磁盘空间浪费）"""
        output_path = os.path.join(self.output_dir, filename)

        try:
            if source_path != output_path:
                shutil.move(source_path, output_path)
                logger.info(f"视频已移动: {source_path} -> {output_path}")
        except Exception as e:
            logger.error(f"移动视频失败，尝试复制: {e}")
            try:
                shutil.copy2(source_path, output_path)
                logger.info(f"视频已复制: {source_path} -> {output_path}")
            except Exception as e2:
                logger.error(f"复制视频也失败: {e2}")
                raise

        return output_path

    def _get_video_duration(self, video_path: str) -> float:
        """获取视频时长"""
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            return frames / fps if fps > 0 else 0.0
        except cv2.error as e:
            logger.error(f"视频文件格式错误: {e}")
            return 0.0
        except Exception as e:
            logger.error(f"获取视频时长时发生异常: {e}")
            raise

    def concatenate_videos(
        self,
        video_paths: List[str],
        output_path: str,
        audio_paths: Optional[List[str]] = None
    ) -> bool:
        """
        合并多个视频片段

        Args:
            video_paths: 视频路径列表
            output_path: 输出路径
            audio_paths: 可选的独立音频列表

        Returns:
            是否成功
        """
        if not video_paths:
            return False

        try:
            import subprocess

            # 如果有独立音频，先合并音频
            if audio_paths:
                temp_video = output_path.replace(".mp4", "_temp.mp4")
                self._concat_videos_simple(video_paths, temp_video)

                # 合并音频
                self._merge_audio_video(temp_video, audio_paths, output_path)

                # 清理临时文件
                if os.path.exists(temp_video):
                    os.remove(temp_video)
            else:
                # 直接合并视频
                self._concat_videos_simple(video_paths, output_path)

            logger.info(f"视频合并成功: {output_path}")
            return True

        except Exception as e:
            logger.error(f"视频合并失败: {e}")
            return False

    def _concat_videos(self, video_paths: List[str], task_id: str) -> Optional[str]:
        """
        合并多个视频文件
        
        Args:
            video_paths: 视频文件路径列表
            task_id: 任务ID
            
        Returns:
            合并后的视频路径，失败返回 None
        """
        import subprocess
        
        if not video_paths:
            logger.warning("没有视频文件需要合并")
            return None
        
        if len(video_paths) == 1:
            return video_paths[0]
        
        try:
            output_path = os.path.join(self.output_dir, f"merged_{task_id}.mp4")
            
            # 第一步：收集所有视频的信息，确定目标分辨率和帧率
            video_infos = []
            target_width = 0
            target_height = 0
            target_fps = 30
            
            for path in video_paths:
                if not os.path.isabs(path):
                    path = os.path.abspath(path)
                info = self._get_video_info(path)
                if info:
                    video_infos.append((path, info))
                    # 使用最大的分辨率作为目标
                    if info.get("width", 0) > target_width or info.get("height", 0) > target_height:
                        target_width = max(target_width, info.get("width", 0))
                        target_height = max(target_height, info.get("height", 0))
                    # 使用最常见的帧率
                    if info.get("fps", 0) > 0:
                        target_fps = info.get("fps", 30)
                else:
                    video_infos.append((path, None))
            
            logger.info(f"目标分辨率: {target_width}x{target_height}, 目标帧率: {target_fps}")
            
            # 第二步：检查是否所有视频参数一致
            needs_normalize_all = False
            for path, info in video_infos:
                if not info:
                    needs_normalize_all = True
                    logger.warning(f"无法获取视频信息，需要标准化: {path}")
                    break
                # 检查分辨率是否一致
                if info.get("width", 0) != target_width or info.get("height", 0) != target_height:
                    needs_normalize_all = True
                    logger.info(f"视频分辨率不一致: {info.get('width')}x{info.get('height')} vs {target_width}x{target_height}，需要标准化: {path}")
                    break
                # 检查编码
                if info.get("codec", "").lower() not in ["h264", "libx264"]:
                    needs_normalize_all = True
                    logger.info(f"视频编码不是 h264: {info.get('codec')}，需要标准化: {path}")
                    break
            
            # 第三步：对所有视频进行标准化处理
            normalized_paths = []
            for i, (path, info) in enumerate(video_infos):
                if needs_normalize_all or (info and self._check_video_needs_normalize(info)):
                    # 标准化视频
                    normalized_path = os.path.join(self.output_dir, f"normalized_{task_id}_{i}.mp4")
                    if self._normalize_video_with_resolution(path, normalized_path, target_width, target_height, target_fps):
                        normalized_paths.append(normalized_path)
                        logger.info(f"视频标准化完成: {path} -> {normalized_path}")
                    else:
                        logger.warning(f"视频标准化失败，使用原始视频: {path}")
                        normalized_paths.append(path)
                else:
                    normalized_paths.append(path)
            
            # 创建临时文件列表
            list_file = os.path.join(self.output_dir, f"concat_list_{task_id}.txt")
            with open(list_file, 'w', encoding='utf-8') as f:
                for path in normalized_paths:
                    if not os.path.isabs(path):
                        path = os.path.abspath(path)
                    escaped_path = path.replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")
            
            # 使用重新编码的方式合并，确保所有视频参数一致
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", list_file,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                output_path
            ]
            
            logger.info(f"执行视频合并命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 清理临时文件
            if os.path.exists(list_file):
                os.remove(list_file)
            
            # 清理标准化后的临时视频文件
            for path in normalized_paths:
                if "normalized_" in path and os.path.exists(path):
                    try:
                        os.remove(path)
                        logger.debug(f"清理临时标准化视频: {path}")
                    except Exception as e:
                        logger.warning(f"清理临时文件失败: {path}, 错误: {e}")
            
            if result.returncode == 0:
                logger.info(f"视频合并成功: {output_path}")
                return output_path
            else:
                logger.error(f"视频合并失败: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"视频合并时发生异常: {e}")
            return None

    def _concat_audio_files(self, audio_files: List[str], output_path: str) -> bool:
        """
        合并多个音频文件
        
        Args:
            audio_files: 音频文件路径列表
            output_path: 输出文件路径
            
        Returns:
            是否成功
        """
        import subprocess
        import uuid
        
        if not audio_files:
            logger.warning("没有音频文件需要合并")
            return False
        
        try:
            # 使用 concat 协议
            concat_file = os.path.join(self.output_dir, f"concat_{uuid.uuid4().hex[:8]}.txt")
            
            with open(concat_file, 'w', encoding='utf-8') as f:
                for audio_path in audio_files:
                    # 转换为绝对路径
                    if not os.path.isabs(audio_path):
                        audio_path = os.path.abspath(audio_path)
                    if os.path.exists(audio_path):
                        # 路径中可能包含特殊字符，需要转义
                        escaped_path = audio_path.replace("'", "'\\''")
                        f.write(f"file '{escaped_path}'\n")
            
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c:a", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                "-y",
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 清理临时文件
            if os.path.exists(concat_file):
                os.remove(concat_file)
            
            if result.returncode == 0:
                return True
            else:
                logger.error(f"合并音频失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"合并音频时发生异常: {e}")
            return False

    def _concat_videos_simple(self, video_paths: List[str], output_path: str):
        """简单合并视频（无音频）"""
        import subprocess

        # 创建临时文件列表
        list_file = os.path.join(self.output_dir, "concat_list.txt")
        with open(list_file, 'w', encoding='utf-8') as f:
            for path in video_paths:
                f.write(f"file '{path}'\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", output_path
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        os.remove(list_file)

    def _extract_audio_from_video(self, video_path: str, output_audio_path: str) -> bool:
        """
        从视频中提取音频
        
        Args:
            video_path: 视频文件路径
            output_audio_path: 输出音频文件路径
            
        Returns:
            是否成功
        """
        import subprocess
        
        try:
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                "-y",
                output_audio_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(output_audio_path):
                logger.info(f"从视频中提取音频成功: {output_audio_path}")
                return True
            else:
                logger.error(f"从视频中提取音频失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"提取音频时发生异常: {e}")
            return False
    
    def _merge_left_right_audio_to_video(
        self,
        video_path: str,
        left_audio_path: str,
        right_audio_path: str,
        output_path: str
    ) -> Optional[str]:
        """
        合并左右音频到视频（双人模式）
        
        Args:
            video_path: 第二次 HeyGem 生成的视频（只有右边声音）
            left_audio_path: 从第一次结果提取的左边音频
            right_audio_path: 原始的右边音频
            output_path: 最终输出视频路径
            
        Returns:
            最终视频路径，失败返回 None
        """
        import subprocess
        
        try:
            # 先合并左右音频
            combined_audio = os.path.join(self.output_dir, f"combined_{os.path.basename(output_path).replace('.mp4', '')}.wav")
            
            if left_audio_path and right_audio_path:
                # 同时有左右音频，使用 amix 混合并保持音量
                cmd = [
                    "ffmpeg",
                    "-i", left_audio_path,
                    "-i", right_audio_path,
                    "-filter_complex", "amix=inputs=2:duration=longest,volume=2",
                    "-ac", "1",
                    "-ar", "16000",
                    "-y",
                    combined_audio
                ]
            elif left_audio_path:
                # 只有左边音频
                import shutil
                shutil.copy2(left_audio_path, combined_audio)
            elif right_audio_path:
                # 只有右边音频
                import shutil
                shutil.copy2(right_audio_path, combined_audio)
            else:
                logger.error("没有可用的音频文件")
                return None
            
            # 执行音频合并（如果需要）
            if left_audio_path and right_audio_path:
                result = subprocess.run(cmd, capture_output=True)
                if result.returncode != 0:
                    stderr = result.stderr.decode('utf-8', errors='ignore')
                    logger.error(f"合并左右音频失败: {stderr}")
                    return None
            
            # 将合并后的音频替换到视频中
            final_output = output_path
            
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-i", combined_audio,
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                "-y",
                final_output
            ]
            
            result = subprocess.run(cmd, capture_output=True)
            
            # 清理临时文件
            if os.path.exists(combined_audio):
                os.remove(combined_audio)
            
            if result.returncode == 0 and os.path.exists(final_output):
                logger.info(f"合并左右音频到视频成功: {final_output}")
                return final_output
            else:
                stderr = result.stderr.decode('utf-8', errors='ignore')
                logger.error(f"合并音频到视频失败: {stderr}")
                return None
                
        except Exception as e:
            logger.error(f"合并左右音频时发生异常: {e}")
            return None
    
    def _merge_audio_video(
        self,
        video_path: str,
        audio_paths: List[str],
        output_path: str
    ):
        """合并音频和视频"""
        import subprocess

        # 先合并所有音频
        concat_audio = os.path.join(self.output_dir, "concat_audio.wav")

        list_file = os.path.join(self.output_dir, "audio_list.txt")
        with open(list_file, 'w', encoding='utf-8') as f:
            for path in audio_paths:
                f.write(f"file '{path}'\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", concat_audio
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        os.remove(list_file)

        # 合并音频和视频
        cmd = [
            "ffmpeg", "-y", "-i", video_path, "-i", concat_audio,
            "-c:v", "copy", "-c:a", "aac", "-strict", "experimental",
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        # 清理临时音频
        if os.path.exists(concat_audio):
            os.remove(concat_audio)

    def _get_video_info(self, video_path: str) -> Optional[Dict[str, Any]]:
        """
        获取视频信息（分辨率、帧率、编码等）
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            视频信息字典，失败返回 None
        """
        import subprocess
        import json
        
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.error(f"ffprobe 执行失败: {result.stderr}")
                return None
            
            data = json.loads(result.stdout)
            
            video_stream = None
            audio_stream = None
            
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video" and video_stream is None:
                    video_stream = stream
                elif stream.get("codec_type") == "audio" and audio_stream is None:
                    audio_stream = stream
            
            if not video_stream:
                logger.error(f"视频文件中没有视频流: {video_path}")
                return None
            
            # 解析帧率
            fps_str = video_stream.get("r_frame_rate", "30/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps = float(num) / float(den) if float(den) != 0 else 30.0
            else:
                fps = float(fps_str)
            
            return {
                "width": video_stream.get("width", 0),
                "height": video_stream.get("height", 0),
                "fps": fps,
                "codec": video_stream.get("codec_name", ""),
                "duration": float(data.get("format", {}).get("duration", 0)),
                "has_audio": audio_stream is not None,
                "audio_codec": audio_stream.get("codec_name", "") if audio_stream else None
            }
            
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            return None

    def _check_video_needs_normalize(self, video_info: Dict[str, Any]) -> bool:
        """
        检查视频是否需要标准化
        
        标准化条件：
        - 编码不是 h264
        - 分辨率不是标准分辨率（如 1080p, 720p）
        - 帧率不是常见帧率（如 24, 25, 30, 60）
        
        Args:
            video_info: 视频信息字典
            
        Returns:
            是否需要标准化
        """
        if not video_info:
            return True
        
        codec = video_info.get("codec", "")
        fps = video_info.get("fps", 0)
        
        # 检查编码
        if codec.lower() not in ["h264", "libx264"]:
            logger.info(f"视频编码不是 h264: {codec}，需要标准化")
            return True
        
        # 检查帧率（允许 24, 25, 30, 60 等常见帧率）
        common_fps = [23.976, 24, 25, 29.97, 30, 59.94, 60]
        fps_match = any(abs(fps - cfps) < 0.1 for cfps in common_fps)
        if not fps_match:
            logger.info(f"视频帧率不是常见帧率: {fps}，需要标准化")
            return True
        
        return False

    def _normalize_video(self, input_path: str, output_path: str) -> bool:
        """
        标准化视频（统一编码、帧率）
        
        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            
        Returns:
            是否成功
        """
        import subprocess
        
        try:
            # 获取输入视频信息
            video_info = self._get_video_info(input_path)
            if not video_info:
                logger.error(f"无法获取视频信息: {input_path}")
                return False
            
            # 标准化参数
            # 保持原始分辨率，统一编码为 h264，帧率保持原样或转为 30fps
            fps = video_info.get("fps", 30)
            if fps < 20 or fps > 60:
                fps = 30
            
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-r", str(fps),
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                output_path
            ]
            
            logger.info(f"执行视频标准化: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"视频标准化成功: {output_path}")
                return True
            else:
                logger.error(f"视频标准化失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"视频标准化超时: {input_path}")
            return False
        except Exception as e:
            logger.error(f"视频标准化异常: {e}")
            return False

    def _normalize_video_with_resolution(self, input_path: str, output_path: str, target_width: int, target_height: int, target_fps: float) -> bool:
        """
        标准化视频（统一分辨率、编码、帧率）
        
        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            target_width: 目标宽度
            target_height: 目标高度
            target_fps: 目标帧率
            
        Returns:
            是否成功
        """
        import subprocess
        
        try:
            # 使用 scale 滤镜缩放视频，同时统一编码和帧率
            # scale 参数：force_original_aspect_ratio=decrease 保持宽高比，不超过目标尺寸
            # pad 参数：填充到目标尺寸
            scale_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
            
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-vf", scale_filter,
                "-r", str(target_fps),
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                output_path
            ]
            
            logger.info(f"执行视频标准化（分辨率: {target_width}x{target_height}, 帧率: {target_fps}）: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"视频标准化成功: {output_path}")
                return True
            else:
                logger.error(f"视频标准化失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"视频标准化超时: {input_path}")
            return False
        except Exception as e:
            logger.error(f"视频标准化异常: {e}")
            return False

    def close(self):
        """关闭客户端"""
        if self.heygem_client:
            self.heygem_client.close()


def create_video_synthesizer(
    heygem_host: str = "http://localhost:9889",
    output_dir: str = "temp/video"
) -> VideoSynthesizer:
    """创建视频合成器的便捷函数"""
    return VideoSynthesizer(heygem_host=heygem_host, output_dir=output_dir)