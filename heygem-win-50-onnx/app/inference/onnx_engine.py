#!/user/bin/env python
# coding=utf-8
"""
@project : digital-human-api
@author  : system
@file   : onnx_engine.py
@ide    : PyCharm
@time   : 2025-03-10
"""

import os
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.inference.base_engine import BaseInferenceEngine
from app.utils.logger import create_logger

logger = create_logger("inference.onnx_engine")


class ONNXEngine(BaseInferenceEngine):
    def __init__(
        self,
        model_path: str,
        device: str = "cuda",
        provider_options: Optional[Dict[str, Any]] = None,
        session_options: Optional[Dict[str, Any]] = None,
    ):
        self.provider_options = provider_options or {}
        self.session_options = session_options or {}
        self._input_names: List[str] = []
        self._output_names: List[str] = []
        super().__init__(model_path, device)

    def _get_providers(self) -> List[str]:
        providers = []
        if self.device == "cuda":
            providers.append("CUDAExecutionProvider")
        providers.append("CPUExecutionProvider")
        return providers

    def _get_provider_options(self) -> List[Dict[str, Any]]:
        options = []
        if self.device == "cuda":
            cuda_options = {
                "device_id": self.provider_options.get("device_id", 0),
                # kSameAsRequested: 按需分配，避免 kNextPowerOfTwo 导致 BFC Arena 过早耗尽
                "arena_extend_strategy": self.provider_options.get(
                    "arena_extend_strategy", "kSameAsRequested"
                ),
                # 不限制 GPU 显存上限（默认 None = 不限制），
                # 之前的 2GB 限制导致 DINet Resize 节点需要 768MB 临时缓冲区时
                # BFC Arena 报告 Available memory of 0 而分配失败
                "gpu_mem_limit": self.provider_options.get("gpu_mem_limit", None),
                "cudnn_conv_algo_search": self.provider_options.get(
                    "cudnn_conv_algo_search", "EXHAUSTIVE"
                ),
                "do_copy_in_default_stream": self.provider_options.get(
                    "do_copy_in_default_stream", True
                ),
            }
            # 移除 None 值（onnxruntime 不接受 None）
            cuda_options = {k: v for k, v in cuda_options.items() if v is not None}
            options.append(cuda_options)
        options.append({})
        return options

    def _create_session_options(self):
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError("onnxruntime is required for ONNXEngine. Install with: pip install onnxruntime-gpu")

        so = ort.SessionOptions()

        so.graph_optimization_level = self.session_options.get(
            "graph_optimization_level", ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        intra_op_num_threads = self.session_options.get("intra_op_num_threads", None)
        if intra_op_num_threads is not None:
            so.intra_op_num_threads = intra_op_num_threads

        inter_op_num_threads = self.session_options.get("inter_op_num_threads", None)
        if inter_op_num_threads is not None:
            so.inter_op_num_threads = inter_op_num_threads

        execution_mode = self.session_options.get("execution_mode", None)
        if execution_mode is not None:
            so.execution_mode = execution_mode

        enable_mem_pattern = self.session_options.get("enable_mem_pattern", True)
        so.enable_mem_pattern = enable_mem_pattern

        enable_mem_reuse = self.session_options.get("enable_mem_reuse", True)
        so.enable_mem_reuse = enable_mem_reuse

        enable_cpu_mem_arena = self.session_options.get("enable_cpu_mem_arena", True)
        so.enable_cpu_mem_arena = enable_cpu_mem_arena

        return so

    def load_model(self) -> None:
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found: {self.model_path}")

        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError("onnxruntime is required for ONNXEngine. Install with: pip install onnxruntime-gpu")

        logger.info(f"Loading ONNX model from: {self.model_path}")

        so = self._create_session_options()
        providers = self._get_providers()
        provider_options = self._get_provider_options()

        try:
            self.session = ort.InferenceSession(
                self.model_path,
                sess_options=so,
                providers=providers,
                provider_options=provider_options,
            )
        except Exception as e:
            logger.warning(f"Failed to load with CUDA provider, falling back to CPU: {e}")
            self.session = ort.InferenceSession(
                self.model_path,
                sess_options=so,
                providers=["CPUExecutionProvider"],
            )
            self.device = "cpu"

        self._input_names = [inp.name for inp in self.session.get_inputs()]
        self._output_names = [out.name for out in self.session.get_outputs()]

        self._input_info = self._extract_io_info(self.session.get_inputs())
        self._output_info = self._extract_io_info(self.session.get_outputs())

        self._is_loaded = True

        actual_providers = self.session.get_providers()
        logger.info(
            f"Model loaded successfully. "
            f"Inputs: {self._input_names}, "
            f"Outputs: {self._output_names}, "
            f"Providers: {actual_providers}"
        )

    def _extract_io_info(self, io_list: List[Any]) -> Dict[str, Any]:
        info = {}
        for io in io_list:
            shape = []
            for dim in io.shape:
                if isinstance(dim, str):
                    shape.append(-1)
                else:
                    shape.append(dim)

            info[io.name] = {
                "name": io.name,
                "shape": tuple(shape),
                "type": io.type,
            }
        return info

    def infer(self, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        if not self._is_loaded or self.session is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        input_feed = {}
        for name in self._input_names:
            if name in inputs:
                input_feed[name] = inputs[name]
            else:
                raise ValueError(f"Required input '{name}' not provided. Available: {list(inputs.keys())}")

        outputs = self.session.run(self._output_names, input_feed)

        result = {}
        for i, name in enumerate(self._output_names):
            result[name] = outputs[i]

        return result

    def infer_batch(self, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        return self.infer(inputs)

    def get_input_info(self) -> Dict[str, Any]:
        if self._input_info is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        return self._input_info

    def get_output_info(self) -> Dict[str, Any]:
        if self._output_info is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        return self._output_info

    def get_input_names(self) -> List[str]:
        return self._input_names.copy()

    def get_output_names(self) -> List[str]:
        return self._output_names.copy()

    def get_input_shape(self, input_name: Optional[str] = None) -> Tuple[int, ...]:
        if input_name is None:
            if len(self._input_names) == 0:
                raise ValueError("No inputs available")
            input_name = self._input_names[0]

        if input_name not in self._input_info:
            raise ValueError(f"Input '{input_name}' not found. Available: {self._input_names}")

        return self._input_info[input_name]["shape"]

    def get_output_shape(self, output_name: Optional[str] = None) -> Tuple[int, ...]:
        if output_name is None:
            if len(self._output_names) == 0:
                raise ValueError("No outputs available")
            output_name = self._output_names[0]

        if output_name not in self._output_info:
            raise ValueError(f"Output '{output_name}' not found. Available: {self._output_names}")

        return self._output_info[output_name]["shape"]

    def get_providers(self) -> List[str]:
        if self.session is None:
            return []
        return self.session.get_providers()

    def set_provider(self, provider: str) -> None:
        if self.session is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        available_providers = self.session.get_providers()
        if provider not in available_providers:
            raise ValueError(f"Provider '{provider}' not available. Available: {available_providers}")

        self.session.set_providers([provider])
        logger.info(f"Switched to provider: {provider}")

    def profile(self, inputs: Dict[str, np.ndarray]) -> Dict[str, Any]:
        if not self._is_loaded or self.session is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        try:
            import onnxruntime as ort

            so = self._create_session_options()
            so.enable_profiling = True

            profile_session = ort.InferenceSession(
                self.model_path,
                sess_options=so,
                providers=self._get_providers(),
            )

            profile_session.run(self._output_names, inputs)

            profile_file = profile_session.end_profiling()
            logger.info(f"Profile saved to: {profile_file}")

            return {"profile_file": profile_file}

        except Exception as e:
            logger.error(f"Profiling failed: {e}")
            return {"error": str(e)}
