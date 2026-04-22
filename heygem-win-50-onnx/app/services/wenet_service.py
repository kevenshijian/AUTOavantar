"""
WenetService — WeNet Conformer BNF 特征提取服务

封装 ConformerEncoder 模型加载（CPU）和 BNF 特征提取逻辑，
替代 audio_service.py 中错误的 MelSpectrogram 实现。

技术方案参考：5.1 WeNet BNF 特征提取 → AC-003
"""
import os
import time
import logging
from pathlib import Path
from typing import Optional, Union

import numpy as np

try:
    import torch
except ImportError:
    torch = None  # 延迟到实际使用时再报错

logger = logging.getLogger(__name__)

# 默认 hparams，与 compute_ctc_att_bnf.py 中 hparams1 一致
DEFAULT_HPARAMS = {
    'sample_rate': 16000,
    'preemphasis': 0.97,
    'n_fft': 1024,
    'hop_length': 160,
    'win_length': 800,
    'num_mels': 80,
    'n_mfcc': 13,
    'window': "hann",
    'fmin': 0.0,
    'fmax': 8000.0,
    'ref_db': 20,
    'min_db': -80.0,
    'iterations': 100,
    'silence_db': -28.0,
    'center': True,
}


class WenetService:
    """WeNet Conformer BNF 特征提取服务

    封装 ConformerEncoder 模型加载和 BNF 特征提取逻辑。
    默认在 CPU 上运行，不占用 GPU 显存。

    使用方式：
        service = WenetService(config_path, model_path, device="cpu")
        features = service.extract_features("audio.wav")  # (T, 256) float32
        # 转置为 DINet ONNX 输入格式：
        audio_feature = features.T[np.newaxis, :, :]  # (1, 256, T)
    """

    def __init__(
        self,
        config_path: str,
        model_path: str,
        device: str = "cpu",
        fp16: bool = False,
        hparams: Optional[dict] = None,
    ):
        """初始化 WenetService

        Args:
            config_path: WeNet 模型配置文件路径 (YAML)
            model_path: WeNet 模型权重文件路径 (.pt)
            device: 运行设备，默认 "cpu"
            fp16: 是否使用半精度推理（仅 GPU 有效）
            hparams: 音频处理参数，默认使用 DEFAULT_HPARAMS

        Raises:
            FileNotFoundError: 配置或模型文件不存在
            RuntimeError: 模型加载失败
        """
        self.device = device
        self.fp16 = fp16 and device == "cuda"
        self.hparams = {**DEFAULT_HPARAMS, **(hparams or {})}

        # 验证文件存在
        if not os.path.isfile(config_path):
            raise FileNotFoundError(f"WeNet config file not found: {config_path}")
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"WeNet model file not found: {model_path}")

        # 加载模型
        self.model = None
        self.configs = None
        self._load_model(config_path, model_path)

        logger.info(f"WenetService initialized: device={device}, fp16={self.fp16}")

    def _load_model(self, config_path: str, model_path: str):
        """加载 WeNet ConformerEncoder 模型"""
        try:
            import torch
            import yaml
            from wenet.transformer.encoder import ConformerEncoder
        except ImportError as e:
            raise RuntimeError(f"Failed to import WeNet dependencies: {e}")

        # 加载配置
        config_file = Path(config_path)
        with config_file.open("r", encoding="utf-8") as f:
            self.configs = yaml.safe_load(f)

        # 构建模型
        input_size = self.configs.get('input_dim', 80)
        encoder = ConformerEncoder(
            input_size=input_size,
            **self.configs['encoder_conf']
        )
        self.model = _PPGModel(encoder)

        # 加载权重（只取 encoder 部分，排除 global_cmvn）
        ckpt_state_dict = torch.load(model_path, map_location="cpu")
        model_state_dict = self.model.state_dict()

        filtered_ckpt = {
            k: v for k, v in ckpt_state_dict.items()
            if "encoder" in k and "encoder.global_cmvn" not in k and k in model_state_dict
        }
        model_state_dict.update(filtered_ckpt)
        self.model.load_state_dict(model_state_dict)

        logger.info(
            f"WeNet checkpoint loaded: {len(filtered_ckpt)}/{len(ckpt_state_dict)} keys matched"
        )

        # 设备和精度
        self.model.to(self.device)
        if self.fp16:
            self.model.half()
        self.model.eval()

    def extract_features(
        self,
        audio_input: Union[str, np.ndarray],
        section: int = 560000,
    ) -> np.ndarray:
        """提取 WeNet BNF 特征

        Args:
            audio_input: 音频文件路径 (str) 或 numpy 数组 (float32, 16kHz)
            section: 分段长度（样本数），默认 560000（35 秒）

        Returns:
            BNF 特征数组，shape = (T, 256)，dtype = float32

        Raises:
            FileNotFoundError: 音频文件不存在
            RuntimeError: 特征提取失败
        """
        import torch
        from wenet.tools._extract_feats import wav2mfcc_v2, load_wav

        # 加载音频
        if isinstance(audio_input, str):
            if not os.path.isfile(audio_input):
                raise FileNotFoundError(f"Audio file not found: {audio_input}")
            wav_arr = load_wav(audio_input, sr=self.hparams["sample_rate"])
        elif isinstance(audio_input, np.ndarray):
            wav_arr = audio_input
        else:
            raise TypeError("audio_input must be a file path (str) or a numpy array.")

        # 前后各填充 6400 个零样本
        zero = np.zeros(6400, dtype=np.float32)
        wav_arr = np.concatenate((zero, wav_arr, zero))

        # 分段处理
        result = []
        use_autocast = self.fp16 and self.device == "cuda"
        with torch.amp.autocast(device_type=self.device, enabled=use_autocast):
            for i in range(len(wav_arr) // section + 1):
                wav_chunk = wav_arr[section * i:section * (i + 1)]

                if len(wav_chunk) == 0:
                    continue

                # 短音频自动填充到 1 秒
                add_silence_flag = False
                if len(wav_chunk) < self.hparams["sample_rate"]:
                    silence_to_add = self.hparams["sample_rate"] - len(wav_chunk)
                    wav_chunk = np.append(
                        wav_chunk,
                        np.zeros(silence_to_add, dtype=np.float32)
                    )
                    add_silence_flag = True

                # 提取 MFCC 特征
                mel, _ = wav2mfcc_v2(
                    wav_chunk,
                    sr=self.hparams["sample_rate"],
                    n_mfcc=self.hparams["n_mfcc"],
                    n_fft=self.hparams["n_fft"],
                    hop_len=self.hparams["hop_length"],
                    win_len=self.hparams["win_length"],
                    window=self.hparams["window"],
                    num_mels=self.hparams["num_mels"],
                    center=self.hparams["center"],
                )

                # 送入 ConformerEncoder
                wav_tensor = torch.from_numpy(mel).float().to(self.device).unsqueeze(0)
                wav_length = torch.LongTensor([mel.shape[0]]).to(self.device)

                with torch.no_grad():
                    bnf = self.model(wav_tensor, wav_length)

                bnf_npy = bnf.float().squeeze(0).cpu().numpy()

                # 如果填充了静音，裁剪掉最后 25 帧
                if add_silence_flag:
                    bnf_npy = bnf_npy[:-25]

                result.append(bnf_npy)

        if not result:
            return np.array([], dtype=np.float32).reshape(0, 256)

        bnf_final = np.concatenate(result, axis=0).astype(np.float32)

        logger.info(
            f"WenetService extracted features: shape={bnf_final.shape}, "
            f"audio_duration~={len(wav_arr)/self.hparams['sample_rate']:.1f}s"
        )

        return bnf_final


class _PPGModel(torch.nn.Module):
    """WeNet PPG 模型封装（与 compute_ctc_att_bnf.py 中 PPGModel 一致）"""

    def __init__(self, encoder):
        super().__init__()
        self.encoder = encoder

    def forward(self, feats, feats_lengths):
        encoder_out, _ = self.encoder(feats, feats_lengths)
        return encoder_out
