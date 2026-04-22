#!/user/bin/env python
# coding=utf-8
"""
@project : digital-human-api
@author  : system
@file   : base_engine.py
@ide    : PyCharm
@time   : 2025-03-10
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import time

from app.utils.logger import create_logger

logger = create_logger("inference.base_engine")


class BaseInferenceEngine(ABC):
    def __init__(self, model_path: str, device: str = "cuda"):
        self.model_path = model_path
        self.device = device
        self.session = None
        self._input_info: Optional[Dict[str, Any]] = None
        self._output_info: Optional[Dict[str, Any]] = None
        self._is_loaded = False
        logger.info(f"Initialized {self.__class__.__name__} with model: {model_path}, device: {device}")

    @abstractmethod
    def load_model(self) -> None:
        pass

    @abstractmethod
    def infer(self, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        pass

    @abstractmethod
    def get_input_info(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_output_info(self) -> Dict[str, Any]:
        pass

    def is_loaded(self) -> bool:
        return self._is_loaded

    def warmup(self, input_shapes: Dict[str, Tuple[int, ...]], runs: int = 3) -> None:
        if not self._is_loaded:
            logger.warning("Model not loaded, cannot warmup")
            return

        logger.info(f"Starting warmup with {runs} runs...")
        dummy_inputs = {}
        for name, shape in input_shapes.items():
            dummy_inputs[name] = np.random.randn(*shape).astype(np.float32)

        for i in range(runs):
            start_time = time.perf_counter()
            self.infer(dummy_inputs)
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.debug(f"Warmup run {i + 1}/{runs}: {elapsed:.2f}ms")

        logger.info("Warmup completed")

    def benchmark(
        self,
        inputs: Dict[str, np.ndarray],
        runs: int = 100,
        warmup_runs: int = 10
    ) -> Dict[str, float]:
        if not self._is_loaded:
            logger.warning("Model not loaded, cannot benchmark")
            return {}

        logger.info(f"Starting benchmark with {runs} runs (warmup: {warmup_runs})...")

        for _ in range(warmup_runs):
            self.infer(inputs)

        latencies = []
        for _ in range(runs):
            start_time = time.perf_counter()
            self.infer(inputs)
            elapsed = (time.perf_counter() - start_time) * 1000
            latencies.append(elapsed)

        latencies_np = np.array(latencies)
        results = {
            "mean_ms": float(np.mean(latencies_np)),
            "std_ms": float(np.std(latencies_np)),
            "min_ms": float(np.min(latencies_np)),
            "max_ms": float(np.max(latencies_np)),
            "median_ms": float(np.median(latencies_np)),
            "p95_ms": float(np.percentile(latencies_np, 95)),
            "p99_ms": float(np.percentile(latencies_np, 99)),
            "fps": 1000.0 / np.mean(latencies_np),
        }

        logger.info(
            f"Benchmark results: mean={results['mean_ms']:.2f}ms, "
            f"median={results['median_ms']:.2f}ms, "
            f"fps={results['fps']:.2f}"
        )

        return results

    def unload(self) -> None:
        if self.session is not None:
            del self.session
            self.session = None
            self._is_loaded = False
            logger.info(f"Unloaded model: {self.model_path}")

    def __del__(self):
        self.unload()

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"model_path='{self.model_path}', "
            f"device='{self.device}', "
            f"is_loaded={self._is_loaded})"
        )
