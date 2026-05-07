"""
GTCRN 音频降噪模块
使用 ONNX 模型进行音频降噪
"""

import logging
import os
import numpy as np
import soundfile as sf
from typing import Optional, Tuple
from pathlib import Path

# 尝试导入torch，如果失败则使用备用方案
try:
    import torch
    torch_available = True
except ImportError:
    torch_available = False
    logging.warning("Torch not available, using alternative implementation")

logger = logging.getLogger(__name__)


class GTCDenoiser:
    """GTCRN 音频降噪器（ONNX 版本）"""
    
    def __init__(
        self,
        model_path: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools", "stream", "onnx_models", "gtcrn_simple.onnx"),
        device: Optional[str] = None,
        denoise_strength: float = 1
    ):
        """
        初始化 GTCRN 降噪器
        
        Args:
            model_path: ONNX 模型文件路径
            device: 运行设备 (cuda/cpu)，默认自动选择
            denoise_strength: 降噪强度 (0.0-1.0)，默认 0.7
        """
        
        self.model_path = model_path
        self.denoise_strength = denoise_strength
        
        # 自动选择设备
        if device is None:
            self.device = "cuda" if self._is_cuda_available() else "cpu"
        else:
            self.device = device
            
        self.session = None
        self._load_model()
        
        logger.info(f"GTCRN 降噪器初始化完成，设备：{self.device}")
    
    def _is_cuda_available(self) -> bool:
        """检查 CUDA 是否可用"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    def _load_model(self):
        """加载 ONNX 模型"""
        try:
            import onnxruntime as ort
            
            # 检查模型文件是否存在
            if not os.path.exists(self.model_path):
                logger.warning(f"模型文件不存在：{self.model_path}")
                # 尝试其他可能的路径
                alt_paths = [
                    "tools/stream/onnx_models/gtcrn.onnx",
                    "voicel/tools/stream/onnx_models/gtcrn_simple.onnx",
                    "voicel/tools/stream/onnx_models/gtcrn.onnx",
                    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools", "stream", "onnx_models", "gtcrn_simple.onnx"),
                    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools", "stream", "onnx_models", "gtcrn.onnx")
                ]
                for alt_path in alt_paths:
                    if os.path.exists(alt_path):
                        self.model_path = alt_path
                        logger.info(f"使用备用模型路径：{alt_path}")
                        break
                else:
                    raise FileNotFoundError(f"未找到 GTCRN ONNX 模型文件")
            
            # 配置 SessionOptions
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            # 根据设备选择 provider
            if self.device == "cuda":
                try:
                    providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
                except Exception:
                    providers = ['CPUExecutionProvider']
            else:
                providers = ['CPUExecutionProvider']
            
            self.session = ort.InferenceSession(
                self.model_path,
                sess_options=sess_options,
                providers=providers
            )
            
            logger.info(f"成功加载 GTCRN ONNX 模型：{self.model_path}")
                
        except ImportError:
            logger.error("未安装 onnxruntime，请安装：pip install onnxruntime-gpu 或 pip install onnxruntime")
            raise
        except Exception as e:
            logger.error(f"加载 GTCRN ONNX 模型失败：{e}")
            raise
    
    def set_denoise_strength(self, strength: float):
        """
        设置降噪强度
        
        Args:
            strength: 降噪强度 (0.0-1.0)
        """
        if not 0.0 <= strength <= 1.0:
            raise ValueError("降噪强度必须在 0.0-1.0 之间")
        self.denoise_strength = strength
        logger.info(f"降噪强度已设置为：{strength:.2f}")
    
    def denoise(self, audio_path: str, output_path: Optional[str] = None) -> str:
        """
        对音频文件进行降噪
        
        Args:
            audio_path: 输入音频文件路径
            output_path: 输出音频文件路径（可选，默认在原路径后加_denoised）
            
        Returns:
            降噪后的音频文件路径
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在：{audio_path}")
        
        try:
            # 读取音频
            audio_data, sample_rate = sf.read(audio_path)
            
            # 如果是立体声，转为单声道
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)
            
            # 重采样到 16kHz（GTCRN 要求）
            if sample_rate != 16000:
                audio_data = self._resample(audio_data, sample_rate, 16000)
            
            # 降噪处理
            enhanced_audio = self._process_audio(audio_data)
            
            # 确定输出路径 - 直接使用原路径，替换原音频
            if output_path is None:
                output_path = audio_path
            
            # 保存降噪后的音频（替换原音频）
            sf.write(output_path, enhanced_audio, 16000)
            
            logger.info(f"音频降噪完成，已替换原音频：{output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"音频降噪失败：{e}")
            raise
    
    def denoise_from_array(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        output_path: Optional[str] = None
    ) -> Tuple[np.ndarray, str]:
        """
        对音频数组进行降噪
        
        Args:
            audio_data: 音频数据数组
            sample_rate: 采样率
            output_path: 输出路径（可选）
            
        Returns:
            (降噪后的音频数组，输出路径)
        """
        # 如果是立体声，转为单声道
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)
        
        # 重采样到 16kHz
        if sample_rate != 16000:
            audio_data = self._resample(audio_data, sample_rate, 16000)
        
        # 降噪处理
        enhanced_audio = self._process_audio(audio_data)
        
        # 保存文件（如果需要）
        if output_path:
            sf.write(output_path, enhanced_audio, 16000)
            logger.info(f"音频降噪完成：{output_path}")
        
        return enhanced_audio, output_path
    
    def _process_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """
        处理音频数据
        
        Args:
            audio_data: 音频数据数组（16kHz）
            
        Returns:
            降噪后的音频数据
        """
        with torch.no_grad():
            # 分帧处理（每次处理 1 秒）
            chunk_size = 16000
            total_length = len(audio_data)
            
            # 填充到 chunk_size 的倍数
            if total_length % chunk_size != 0:
                padding = chunk_size - (total_length % chunk_size)
                audio_data = np.pad(audio_data, (0, padding), mode='constant')
            
            # 分块处理
            enhanced_chunks = []
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                enhanced_chunk = self._enhance_chunk(chunk)
                enhanced_chunks.append(enhanced_chunk)
            
            # 拼接结果
            enhanced_audio = np.concatenate(enhanced_chunks)

            # 应用降噪强度混合（在截取原始长度之前）
            if self.denoise_strength < 1.0:
                if len(enhanced_audio) >= total_length:
                    mix_audio = enhanced_audio[:total_length]
                else:
                    mix_audio = enhanced_audio
                enhanced_audio = (
                    self.denoise_strength * mix_audio +
                    (1 - self.denoise_strength) * audio_data[:len(mix_audio)]
                )

            # 截取到原始长度
            enhanced_audio = enhanced_audio[:total_length]

            return enhanced_audio
    
    def _enhance_chunk(self, audio_chunk: np.ndarray) -> np.ndarray:
        """
        增强单个音频块（逐帧处理流式ONNX模型）

        Args:
            audio_chunk: 音频块数据

        Returns:
            增强后的音频块
        """
        import torch

        audio_tensor = torch.from_numpy(audio_chunk).float()

        if audio_tensor.dim() == 1:
            audio_tensor = audio_tensor.unsqueeze(0)

        spec_complex = torch.stft(
            audio_tensor,
            n_fft=512,
            hop_length=256,
            win_length=512,
            window=torch.hann_window(512, device=audio_tensor.device).pow(0.5),
            return_complex=True
        )

        spec_np = spec_complex.cpu().numpy()

        if self.session is None:
            return audio_chunk

        time_steps = spec_np.shape[2]

        conv_cache = np.zeros((2, 1, 16, 16, 33), dtype=np.float32)
        tra_cache = np.zeros((2, 3, 1, 1, 16), dtype=np.float32)
        inter_cache = np.zeros((2, 1, 33, 16), dtype=np.float32)

        enhanced_frames = []
        for i in range(time_steps):
            frame = spec_np[:, :, i]

            frame_real = frame.real
            frame_imag = frame.imag
            frame_real_imag = np.stack([frame_real, frame_imag], axis=-1)

            frame_real_imag = frame_real_imag[:, :, np.newaxis, :]

            enhanced_frame, conv_cache, tra_cache, inter_cache = self.session.run(None, {
                'mix': frame_real_imag,
                'conv_cache': conv_cache,
                'tra_cache': tra_cache,
                'inter_cache': inter_cache
            })

            enhanced_complex = enhanced_frame[0, :, 0, 0] + 1j * enhanced_frame[0, :, 0, 1]
            enhanced_frames.append(enhanced_complex)

        enhanced_spec_complex = np.stack(enhanced_frames, axis=1)

        enhanced_spec_tensor = torch.from_numpy(enhanced_spec_complex.real).float() + \
                              1j * torch.from_numpy(enhanced_spec_complex.imag).float()

        enhanced_audio = torch.istft(
            enhanced_spec_tensor,
            n_fft=512,
            hop_length=256,
            win_length=512,
            window=torch.hann_window(512, device=audio_tensor.device).pow(0.5),
            return_complex=False
        )

        return enhanced_audio.squeeze().cpu().numpy()
    
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
            重采样后的音频
        """
        try:
            import librosa
            return librosa.resample(audio_data, orig_sr=orig_sr, target_sr=target_sr)
        except ImportError:
            # 简单重采样（线性插值）
            duration = len(audio_data) / orig_sr
            target_length = int(duration * target_sr)
            indices = np.linspace(0, len(audio_data) - 1, target_length)
            return np.interp(indices, np.arange(len(audio_data)), audio_data)


def create_denoiser(
    model_path: str = "tools/stream/onnx_models/gtcrn_simple.onnx",
    denoise_strength: float = 0.7
) -> GTCDenoiser:
    """
    创建降噪器的便捷函数
    
    Args:
        model_path: ONNX 模型路径
        denoise_strength: 降噪强度
        
    Returns:
        GTCDenoiser 实例
    """
    return GTCDenoiser(model_path=model_path, denoise_strength=denoise_strength)
