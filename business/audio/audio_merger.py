"""
音频合并模块
支持多音频片段合并，并进行响度统一处理
"""

import os
import logging
import uuid
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
from datetime import datetime

logger = logging.getLogger("audio-merger")

NUMPY_AVAILABLE = False
LIBROSA_AVAILABLE = False

try:
    import numpy as np
    import soundfile as sf
    NUMPY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"numpy 或 soundfile 未安装，音频处理功能受限: {e}")

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError as e:
    logger.warning(f"librosa 未安装，响度统一功能受限: {e}")


class AudioValidationError(Exception):
    """音频验证错误"""
    pass


class AudioMergeError(Exception):
    """音频合并错误"""
    pass


class AtomicFileWriter:
    """原子性文件写入器"""
    
    def __init__(self, target_path: Union[str, Path], file_format: str = None):
        """
        初始化原子文件写入器
        
        Args:
            target_path: 目标文件路径
            file_format: 文件格式（如 'WAV', 'WAVEX', 'FLAC' 等），默认为 None，会自动从目标路径推断
        """
        self.target_path = Path(target_path)
        self.temp_path = None
        self.file_format = file_format
        self.logger = logging.getLogger("audio-merger.atomic-writer")
        
        # 如果没有指定格式，从目标路径推断
        if self.file_format is None:
            suffix = self.target_path.suffix.lower()
            format_map = {
                '.wav': 'WAV',
                '.flac': 'FLAC',
                '.ogg': 'OGG',
                '.mp3': 'MP3',
                '.m4a': 'M4A'
            }
            self.file_format = format_map.get(suffix, 'WAV')
    
    def __enter__(self):
        """创建临时文件"""
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        # 临时文件保持与目标文件相同的后缀，这样 soundfile 可以识别格式
        self.temp_path = self.target_path.with_suffix('.tmp_' + uuid.uuid4().hex[:8] + self.target_path.suffix)
        return self.temp_path
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """完成原子写入或回滚"""
        if exc_type is not None:
            # 发生异常，删除临时文件
            if self.temp_path and self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                    self.logger.info(f"原子写入回滚成功: {self.temp_path}")
                except Exception as e:
                    self.logger.error(f"删除临时文件失败: {self.temp_path}, 错误: {e}")
            return False
        
        # 没有异常，执行原子替换
        try:
            if self.temp_path and self.temp_path.exists():
                # 如果目标文件存在，先删除
                if self.target_path.exists():
                    self.target_path.unlink()
                
                # 移动临时文件到目标位置
                shutil.move(str(self.temp_path), str(self.target_path))
                self.logger.info(f"原子写入成功: {self.target_path}")
                return True
        except Exception as e:
            self.logger.error(f"原子写入失败: {e}")
            # 尝试清理
            if self.temp_path and self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except:
                    pass
            raise
    
    def write(self, data):
        """写入数据到临时文件"""
        if self.temp_path:
            with open(self.temp_path, 'wb') as f:
                f.write(data)
            return True
        return False


class AudioMerger:
    """音频合并器类"""
    
    SUPPORTED_FORMATS = ['.wav', '.mp3', '.flac', '.ogg', '.m4a']
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_CLIPS_COUNT = 50
    MAX_TOTAL_DURATION = 3600  # 1小时
    
    def __init__(
        self,
        output_dir: str = None,
        target_loudness: float = -20.0,
        sample_rate: int = 16000
    ):
        """
        初始化音频合并器
        
        Args:
            output_dir: 输出目录
            target_loudness: 目标响度（dB），默认-20dB
            sample_rate: 采样率，默认16000Hz
        """
        if output_dir is None:
            project_root = Path(__file__).parent.parent.parent
            output_dir = project_root / "backend" / "data" / "merged_audios"
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.target_loudness = target_loudness
        self.sample_rate = sample_rate
        
        logger.info(f"音频合并器初始化完成，输出目录: {self.output_dir}")
        logger.info(f"目标响度: {self.target_loudness}dB, 采样率: {self.sample_rate}Hz")
    
    def validate_audio_file(self, file_path: Union[str, Path]) -> Tuple[bool, str, Dict]:
        """
        验证音频文件
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            (是否有效, 错误信息, 文件信息字典)
        """
        file_path = Path(file_path)
        info = {
            "path": str(file_path),
            "name": file_path.name,
            "size": 0,
            "duration": 0.0,
            "sample_rate": 0,
            "channels": 0,
            "format": file_path.suffix.lower()
        }
        
        if not file_path.exists():
            return False, f"文件不存在: {file_path}", info
        
        if not file_path.is_file():
            return False, f"路径不是文件: {file_path}", info
        
        if file_path.suffix.lower() not in self.SUPPORTED_FORMATS:
            return False, f"不支持的音频格式: {file_path.suffix}", info
        
        try:
            file_size = file_path.stat().st_size
            info["size"] = file_size
            
            if file_size > self.MAX_FILE_SIZE:
                return False, f"文件大小超过限制: {file_size} > {self.MAX_FILE_SIZE} bytes", info
            
            if file_size == 0:
                return False, "文件为空", info
            
            if NUMPY_AVAILABLE:
                audio_data, sr = sf.read(str(file_path), dtype='float32')
                info["duration"] = len(audio_data) / sr
                info["sample_rate"] = sr
                info["channels"] = 1 if len(audio_data.shape) == 1 else audio_data.shape[1]
                
                if info["duration"] <= 0:
                    return False, "音频时长无效", info
                
                return True, "", info
            else:
                return True, "", info
                
        except Exception as e:
            logger.error(f"验证音频文件失败: {file_path}, 错误: {e}")
            return False, f"读取音频文件失败: {str(e)}", info
    
    def validate_audio_clips(self, clips: List[Dict]) -> Tuple[bool, str, List[Dict]]:
        """
        验证音频片段列表
        
        Args:
            clips: 音频片段列表
            
        Returns:
            (是否有效, 错误信息, 验证后的片段列表)
        """
        if not clips or len(clips) == 0:
            return False, "音频片段列表为空", []
        
        if len(clips) > self.MAX_CLIPS_COUNT:
            return False, f"音频片段数量超过限制: {len(clips)} > {self.MAX_CLIPS_COUNT}", []
        
        validated_clips = []
        total_duration = 0.0
        
        for i, clip in enumerate(clips):
            audio_path = clip.get('path')
            
            if not audio_path:
                logger.warning(f"第{i+1}个音频片段缺少路径")
                continue
            
            is_valid, error, info = self.validate_audio_file(audio_path)
            
            if not is_valid:
                logger.warning(f"第{i+1}个音频片段验证失败: {error}")
                continue
            
            total_duration += info["duration"]
            
            if total_duration > self.MAX_TOTAL_DURATION:
                return False, f"音频总时长超过限制: {total_duration:.2f}s > {self.MAX_TOTAL_DURATION}s", []
            
            validated_clips.append({
                "path": audio_path,
                "name": clip.get('name', info["name"]),
                "duration": info["duration"],
                "index": i
            })
        
        if not validated_clips:
            return False, "没有可用的音频片段", []
        
        logger.info(f"验证通过: {len(validated_clips)}/{len(clips)} 个音频片段，总时长: {total_duration:.2f}s")
        return True, "", validated_clips
    
    def merge_audio_clips(
        self,
        audio_clips: List[Dict],
        output_filename: str = None
    ) -> Tuple[bool, str, float, str]:
        """
        合并多个音频片段
        
        Args:
            audio_clips: 音频片段列表，每个元素包含:
                - path: 音频文件路径
                - name: 音频名称（可选）
                - duration: 音频时长（可选）
            output_filename: 输出文件名（可选），如果不提供则自动生成
            
        Returns:
            (成功标志, 输出文件路径, 总时长, 错误信息)
        """
        start_time = datetime.now()
        
        if not NUMPY_AVAILABLE:
            return False, "", 0.0, "numpy 或 soundfile 未安装"
        
        try:
            # 验证音频片段
            is_valid, error, validated_clips = self.validate_audio_clips(audio_clips)
            
            if not is_valid:
                return False, "", 0.0, error
            
            # 如果只有一个片段，直接处理
            if len(validated_clips) == 1:
                return self._process_single_audio(validated_clips[0])
            
            # 生成输出文件名
            if not output_filename:
                output_filename = f"merged_{uuid.uuid4().hex[:8]}.wav"
            elif not output_filename.endswith('.wav'):
                output_filename += '.wav'
            
            output_path = self.output_dir / output_filename
            
            logger.info(f"开始合并 {len(validated_clips)} 个音频片段")
            
            # 加载和处理所有音频片段
            processed_clips = []
            total_duration = 0.0
            
            for clip in validated_clips:
                audio_path = Path(clip['path'])
                
                try:
                    # 读取音频
                    audio_data, sr = sf.read(str(audio_path), dtype='float32')
                    
                    # 转换为单声道
                    if len(audio_data.shape) > 1:
                        audio_data = np.mean(audio_data, axis=1)
                    
                    # 统一采样率
                    if sr != self.sample_rate:
                        audio_data = self._resample(audio_data, sr, self.sample_rate)
                    else:
                        audio_data = audio_data.astype(np.float32)
                    
                    # 应用响度统一
                    audio_data = self._normalize_loudness(audio_data)
                    
                    # 收集处理后的音频和时长
                    clip_duration = len(audio_data) / self.sample_rate
                    total_duration += clip_duration
                    
                    processed_clips.append(audio_data)
                    
                    logger.info(f"已处理音频片段 [{clip['index']+1}/{len(validated_clips)}]: {clip['name']}")
                    
                except Exception as e:
                    logger.error(f"处理音频片段失败: {clip['name']}, 错误: {e}")
                    continue
            
            if not processed_clips:
                return False, "", 0.0, "没有可用的音频片段"
            
            # 合并音频片段
            merged_audio = np.concatenate(processed_clips)
            
            # 再次应用响度统一到合并后的音频
            merged_audio = self._normalize_loudness(merged_audio)
            
            # 使用原子写入保存合并后的音频
            with AtomicFileWriter(output_path) as temp_path:
                sf.write(str(temp_path), merged_audio, self.sample_rate)
            
            # 返回相对于项目根目录的路径
            project_root = Path(__file__).parent.parent.parent
            relative_path = output_path.relative_to(project_root)
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"音频合并完成，输出文件: {output_path}，总时长: {total_duration:.2f}秒，耗时: {elapsed_time:.2f}s")
            
            return True, str(relative_path), total_duration, ""
            
        except Exception as e:
            logger.error(f"音频合并失败: {e}")
            return False, "", 0.0, str(e)
    
    def merge_uploaded_files(
        self,
        uploaded_files: List[Tuple[str, bytes]],
        output_filename: str = None
    ) -> Tuple[bool, str, float, str]:
        """
        合并上传的音频文件
        
        Args:
            uploaded_files: 上传的文件列表，每个元素为 (文件名, 文件内容)
            output_filename: 输出文件名
            
        Returns:
            (成功标志, 输出文件路径, 总时长, 错误信息)
        """
        start_time = datetime.now()
        
        if not NUMPY_AVAILABLE:
            return False, "", 0.0, "numpy 或 soundfile 未安装"
        
        if not uploaded_files or len(uploaded_files) == 0:
            return False, "", 0.0, "没有上传的文件"
        
        if len(uploaded_files) > self.MAX_CLIPS_COUNT:
            return False, "", 0.0, f"上传文件数量超过限制: {len(uploaded_files)} > {self.MAX_CLIPS_COUNT}"
        
        try:
            # 创建临时目录保存上传的文件
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                temp_audio_paths = []
                total_duration = 0.0
                
                # 保存上传的文件
                for filename, file_content in uploaded_files:
                    file_ext = Path(filename).suffix.lower()
                    
                    if file_ext not in self.SUPPORTED_FORMATS:
                        logger.warning(f"跳过不支持的文件格式: {filename}")
                        continue
                    
                    if len(file_content) > self.MAX_FILE_SIZE:
                        logger.warning(f"跳过过大的文件: {filename} ({len(file_content)} bytes)")
                        continue
                    
                    temp_file_path = temp_path / f"{uuid.uuid4().hex[:8]}_{filename}"
                    
                    try:
                        with open(temp_file_path, 'wb') as f:
                            f.write(file_content)
                        
                        temp_audio_paths.append(str(temp_file_path))
                        logger.info(f"已保存上传文件: {filename} -> {temp_file_path}")
                    except Exception as e:
                        logger.error(f"保存上传文件失败: {filename}, 错误: {e}")
                        continue
                
                if not temp_audio_paths:
                    return False, "", 0.0, "没有可用的音频文件"
                
                # 构建音频片段列表
                audio_clips = [{"path": path} for path in temp_audio_paths]
                
                # 合并音频
                success, output_path, duration, error = self.merge_audio_clips(
                    audio_clips,
                    output_filename=output_filename
                )
                
                elapsed_time = (datetime.now() - start_time).total_seconds()
                logger.info(f"处理上传文件完成，耗时: {elapsed_time:.2f}s")
                
                return success, output_path, duration, error
                
        except Exception as e:
            logger.error(f"处理上传文件失败: {e}")
            return False, "", 0.0, str(e)
    
    def _process_single_audio(self, clip: Dict) -> Tuple[bool, str, float, str]:
        """
        处理单个音频文件
        
        Args:
            clip: 音频片段信息
            
        Returns:
            (成功标志, 输出文件路径, 时长, 错误信息)
        """
        try:
            audio_path = Path(clip['path'])
            
            if not audio_path.exists():
                return False, "", 0.0, f"音频文件不存在: {audio_path}"
            
            # 读取音频
            audio_data, sr = sf.read(str(audio_path), dtype='float32')
            
            # 转换为单声道
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)
            
            # 统一采样率
            if sr != self.sample_rate:
                audio_data = self._resample(audio_data, sr, self.sample_rate)
            else:
                audio_data = audio_data.astype(np.float32)
            
            # 应用响度统一
            audio_data = self._normalize_loudness(audio_data)
            
            # 计算时长
            duration = len(audio_data) / self.sample_rate
            
            # 生成输出文件名
            output_filename = f"processed_{uuid.uuid4().hex[:8]}.wav"
            output_path = self.output_dir / output_filename
            
            # 使用原子写入保存处理后的音频
            with AtomicFileWriter(output_path) as temp_path:
                sf.write(str(temp_path), audio_data, self.sample_rate)
            
            # 返回相对于项目根目录的路径
            project_root = Path(__file__).parent.parent.parent
            relative_path = output_path.relative_to(project_root)
            
            logger.info(f"单个音频处理完成: {output_path}，时长: {duration:.2f}秒")
            
            return True, str(relative_path), duration, ""
            
        except Exception as e:
            logger.error(f"处理单个音频失败: {e}")
            return False, "", 0.0, str(e)
    
    def _normalize_loudness(self, audio_data: np.ndarray) -> np.ndarray:
        """
        统一音频响度
        
        Args:
            audio_data: 音频数据
            
        Returns:
            响度统一后的音频数据
        """
        if not LIBROSA_AVAILABLE:
            max_val = np.abs(audio_data).max()
            if max_val > 0:
                return audio_data / max_val * 0.9
            return audio_data
        
        try:
            rms = np.sqrt(np.mean(audio_data ** 2))
            
            if rms > 0:
                target_rms = 10 ** (self.target_loudness / 20)
                gain = target_rms / rms
                gain = min(gain, 5.0)
                audio_data = audio_data * gain
            
            audio_data = np.clip(audio_data, -1.0, 1.0)
            
            return audio_data
            
        except Exception as e:
            logger.warning(f"响度统一失败: {e}，使用简单归一化")
            max_val = np.abs(audio_data).max()
            if max_val > 0:
                return audio_data / max_val * 0.9
            return audio_data
    
    def _resample(
        self,
        audio_data: np.ndarray,
        orig_sr: int,
        target_sr: int
    ) -> np.ndarray:
        """
        重采样音频
        
        Args:
            audio_data: 音频数据
            orig_sr: 原始采样率
            target_sr: 目标采样率
            
        Returns:
            重采样后的音频数据
        """
        if not LIBROSA_AVAILABLE:
            duration = len(audio_data) / orig_sr
            target_length = int(duration * target_sr)
            indices = np.linspace(0, len(audio_data) - 1, target_length)
            return np.interp(indices, np.arange(len(audio_data)), audio_data).astype(np.float32)
        
        try:
            return librosa.resample(
                audio_data,
                orig_sr=orig_sr,
                target_sr=target_sr
            ).astype(np.float32)
        except Exception as e:
            logger.warning(f"重采样失败: {e}，使用简单插值")
            duration = len(audio_data) / orig_sr
            target_length = int(duration * target_sr)
            indices = np.linspace(0, len(audio_data) - 1, target_length)
            return np.interp(indices, np.arange(len(audio_data)), audio_data).astype(np.float32)


def create_audio_merger(
    output_dir: str = None,
    target_loudness: float = -20.0,
    sample_rate: int = 16000
) -> AudioMerger:
    """
    创建音频合并器的便捷函数
    
    Args:
        output_dir: 输出目录
        target_loudness: 目标响度
        sample_rate: 采样率
        
    Returns:
        AudioMerger 实例
    """
    return AudioMerger(
        output_dir=output_dir,
        target_loudness=target_loudness,
        sample_rate=sample_rate
    )
