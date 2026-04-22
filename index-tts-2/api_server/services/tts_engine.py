"""
TTS 推理引擎
封装 indextts.infer_v2.IndexTTS2 (编译模块)，支持原版情绪参数方式
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict, List

logger = logging.getLogger("indextts-api.engine")


class TTSEngine:
    """
    TTS 推理引擎 - 封装 indextts.infer_v2.IndexTTS2

    支持原版 IndexTTS2 的情绪参数方式：
    - emo_audio_prompt + emo_alpha: 情绪参考音频
    - emo_vector: 8元素列表 [happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]
    - use_emo_text=True: 根据文本自动推断情绪
    - use_emo_text=True + emo_text: 根据指定情绪文本推断
    """

    def __init__(self):
        self._model = None
        self._loaded = False
        self._device = None
        self._is_fp16 = False
        self._load_params = None  # 保存加载参数，用于卸载后自动重载

    def load_model(
        self,
        cfg_path,
        model_dir,
        is_fp16=True,
        device=None,
        use_cuda_kernel=None,
    ):
        """
        加载模型权重 - 使用 indextts.infer_v2.IndexTTS2
        """
        logger.info("加载 TTS 模型: cfg=%s, dir=%s, fp16=%s", cfg_path, model_dir, is_fp16)

        from indextts.infer_v2 import IndexTTS2

        self._model = IndexTTS2(
            cfg_path=cfg_path,
            model_dir=model_dir,
            is_fp16=is_fp16,
            device=device,
            use_cuda_kernel=use_cuda_kernel,
        )

        self._is_fp16 = is_fp16
        self._device = device
        self._loaded = True

        # 保存加载参数，用于卸载后自动重载
        self._load_params = {
            "cfg_path": cfg_path,
            "model_dir": model_dir,
            "is_fp16": is_fp16,
            "device": device,
            "use_cuda_kernel": use_cuda_kernel,
        }

        logger.info("TTS 引擎加载完成")

    def unload_model(self):
        """
        卸载模型并释放 GPU 显存。

        调用后模型不可用，需要重新 load_model() 才能恢复推理。
        卸载时保留加载参数，支持后续自动重载。
        """
        if not self._loaded:
            logger.info("模型未加载，无需卸载")
            return

        import gc

        logger.info("开始卸载 TTS 模型，释放 GPU 显存...")

        # 删除模型引用（保留 _load_params 用于自动重载）
        del self._model
        self._model = None
        self._loaded = False

        # 触发垃圾回收
        gc.collect()

        # 释放 GPU 缓存
        self._empty_cache()

        logger.info("TTS 模型已卸载，GPU 显存已释放")

    def reload_model(self):
        """
        使用之前保存的参数重新加载模型。

        Returns:
            bool: 是否成功重载

        Raises:
            RuntimeError: 没有保存的加载参数
        """
        if self._load_params is None:
            raise RuntimeError("没有可用的加载参数，无法重载模型（首次加载参数未保存）")

        if self._loaded:
            logger.info("模型已加载，无需重载")
            return True

        logger.info("开始重新加载 TTS 模型...")
        self.load_model(**self._load_params)
        return True

    @property
    def is_loaded(self):
        return self._loaded

    def synthesize(
        self,
        text,
        voice_path,
        output_path,
        emo_audio_prompt=None,
        emo_alpha=1.0,
        emo_vector=None,
        use_emo_text=False,
        emo_text=None,
        use_random=False,
        temperature=1.0,
        top_p=0.8,
        top_k=30,
        num_beams=3,
    ):
        """
        执行 TTS 推理 - 使用 indextts.infer_v2.IndexTTS2

        Args:
            voice_path: 音色文件路径，支持 .wav 音频文件或 .pt 特征文件
            emo_audio_prompt: 情绪参考音频路径
            emo_alpha: 情绪强度 0.0~1.0
            emo_vector: 8元素情绪向量列表 [happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]
            use_emo_text: 是否根据文本自动推断情绪
            emo_text: 指定情绪文本
            use_random: 是否启用随机采样
        """
        if not self._loaded:
            logger.info("模型未加载，尝试自动重载...")
            try:
                self.reload_model()
                logger.info("模型自动重载成功")
            except Exception as e:
                raise RuntimeError(f"模型未加载且自动重载失败: {e}") from e

        start_time = time.perf_counter()

        generation_kwargs = {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "num_beams": num_beams,
        }

        audio_prompt = voice_path
        if voice_path.endswith(".pt"):
            audio_prompt = self._resolve_audio_from_pt(voice_path)

        infer_kwargs = {
            "spk_audio_prompt": audio_prompt,
            "text": text,
            "output_path": output_path,
            "verbose": False,
            **generation_kwargs,
        }

        if emo_audio_prompt is not None:
            infer_kwargs["emo_audio_prompt"] = emo_audio_prompt
            infer_kwargs["emo_alpha"] = emo_alpha

        if emo_vector is not None:
            if isinstance(emo_vector, (list, tuple)) and len(emo_vector) == 8:
                infer_kwargs["emo_vector"] = list(emo_vector)
            else:
                logger.warning("emo_vector 格式无效，应为8元素列表，已忽略")

        if use_emo_text:
            infer_kwargs["use_emo_text"] = True
            if emo_text is not None:
                infer_kwargs["emo_text"] = emo_text

        if use_random:
            infer_kwargs["use_random"] = True

        self._model.infer(**infer_kwargs)

        inference_time = time.perf_counter() - start_time
        logger.info("TTS 合成完成: time=%.2fs, output=%s", inference_time, output_path)

        return output_path

    def _resolve_audio_from_pt(self, pt_path: str) -> str:
        """
        从 .pt 文件解析音频文件路径

        .pt 文件存储格式: {"audio": "相对/绝对音频路径"}
        """
        import torch

        data = torch.load(pt_path, map_location="cpu")

        if isinstance(data, dict) and "audio" in data:
            audio_path = data["audio"]
            if isinstance(audio_path, str):
                if os.path.isabs(audio_path):
                    if os.path.exists(audio_path):
                        return audio_path
                else:
                    pt_dir = Path(pt_path).parent
                    for _ in range(3):
                        candidate = pt_dir / audio_path
                        if candidate.exists():
                            return str(candidate)
                        pt_dir = pt_dir.parent
                    project_root = Path(__file__).parent.parent.parent
                    candidate = project_root / audio_path
                    if candidate.exists():
                        return str(candidate)
                raise FileNotFoundError(f"音频文件不存在: {audio_path}")
            raise ValueError(f".pt 文件中的 'audio' 不是字符串: {type(audio_path)}")

        raise ValueError(f".pt 文件缺少 'audio' 键: {list(data.keys()) if isinstance(data, dict) else type(data)}")

    def _empty_cache(self):
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif hasattr(torch, "mps") and torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception:
            pass
