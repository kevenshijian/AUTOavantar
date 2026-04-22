#!/user/bin/env python
# coding=utf-8
"""
@project : digital-human-api
@author  : system
@file   : model_manager.py
@ide    : PyCharm
@time   : 2025-03-10
"""

import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Type, Union

from app.inference.base_engine import BaseInferenceEngine
from app.inference.onnx_engine import ONNXEngine
from app.utils.logger import create_logger

logger = create_logger("inference.model_manager")


class ModelManager:
    _instance: Optional["ModelManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        models_dir: Optional[Union[str, Path]] = None,
        default_device: str = "cuda",
        engine_class: Type[BaseInferenceEngine] = ONNXEngine,
    ):
        if self._initialized:
            return

        self._models: Dict[str, BaseInferenceEngine] = {}
        self._model_configs: Dict[str, Dict[str, Any]] = {}
        self._models_dir = Path(models_dir) if models_dir else Path("models")
        self._default_device = default_device
        self._engine_class = engine_class
        self._model_lock = threading.Lock()
        self._initialized = True

        logger.info(
            f"ModelManager initialized. "
            f"Models dir: {self._models_dir}, "
            f"Default device: {self._default_device}"
        )

    @classmethod
    def get_instance(cls) -> "ModelManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance.unload_all()
                cls._instance = None
                logger.info("ModelManager instance reset")

    def register_model(
        self,
        model_name: str,
        model_path: Union[str, Path],
        device: Optional[str] = None,
        auto_load: bool = False,
        warmup_shape: Optional[Dict[str, Tuple[int, ...]]] = None,
        **engine_kwargs,
    ) -> None:
        config = {
            "model_path": str(model_path),
            "device": device or self._default_device,
            "engine_kwargs": engine_kwargs,
            "warmup_shape": warmup_shape,
            "auto_load": auto_load,
        }

        self._model_configs[model_name] = config
        logger.info(f"Registered model '{model_name}': {model_path}")

        if auto_load:
            self.load_model(model_name)

    def load_model(
        self,
        model_name: str,
        device: Optional[str] = None,
        **engine_kwargs,
    ) -> BaseInferenceEngine:
        with self._model_lock:
            if model_name in self._models and self._models[model_name].is_loaded():
                logger.debug(f"Model '{model_name}' already loaded")
                return self._models[model_name]

            if model_name not in self._model_configs:
                raise ValueError(f"Model '{model_name}' not registered. Call register_model() first.")

            config = self._model_configs[model_name]
            model_path = config["model_path"]
            use_device = device or config["device"]
            kwargs = {**config.get("engine_kwargs", {}), **engine_kwargs}

            engine = self._engine_class(
                model_path=model_path,
                device=use_device,
                **kwargs,
            )
            engine.load_model()

            self._models[model_name] = engine

            warmup_shape = config.get("warmup_shape")
            if warmup_shape:
                engine.warmup(warmup_shape)

            logger.info(f"Model '{model_name}' loaded successfully on {use_device}")
            return engine

    def get_model(self, model_name: str) -> BaseInferenceEngine:
        if model_name in self._models and self._models[model_name].is_loaded():
            return self._models[model_name]

        if model_name in self._model_configs:
            return self.load_model(model_name)

        raise ValueError(
            f"Model '{model_name}' not found. "
            f"Registered models: {list(self._model_configs.keys())}"
        )

    def unload_model(self, model_name: str) -> None:
        with self._model_lock:
            if model_name in self._models:
                self._models[model_name].unload()
                del self._models[model_name]
                logger.info(f"Model '{model_name}' unloaded")

    def unload_all(self) -> None:
        with self._model_lock:
            for model_name in list(self._models.keys()):
                self._models[model_name].unload()
            self._models.clear()
            logger.info("All models unloaded")

    def is_loaded(self, model_name: str) -> bool:
        return model_name in self._models and self._models[model_name].is_loaded()

    def list_models(self) -> Dict[str, Dict[str, Any]]:
        result = {}
        for name, config in self._model_configs.items():
            result[name] = {
                "path": config["model_path"],
                "device": config["device"],
                "is_loaded": self.is_loaded(name),
            }
        return result

    def get_loaded_models(self) -> Dict[str, BaseInferenceEngine]:
        return {
            name: engine
            for name, engine in self._models.items()
            if engine.is_loaded()
        }

    def warmup_model(
        self,
        model_name: str,
        input_shapes: Dict[str, Tuple[int, ...]],
        runs: int = 3,
    ) -> None:
        engine = self.get_model(model_name)
        engine.warmup(input_shapes, runs)
        logger.info(f"Model '{model_name}' warmed up")

    def benchmark_model(
        self,
        model_name: str,
        inputs: Dict[str, Any],
        runs: int = 100,
    ) -> Dict[str, float]:
        engine = self.get_model(model_name)
        return engine.benchmark(inputs, runs)

    def preload_models(self, model_names: Optional[list] = None) -> None:
        names_to_load = model_names or list(self._model_configs.keys())

        for name in names_to_load:
            if name in self._model_configs:
                try:
                    self.load_model(name)
                except Exception as e:
                    logger.error(f"Failed to preload model '{name}': {e}")

    def __contains__(self, model_name: str) -> bool:
        return model_name in self._model_configs

    def __len__(self) -> int:
        return len(self._models)

    def __repr__(self) -> str:
        loaded = len([m for m in self._models.values() if m.is_loaded()])
        return (
            f"ModelManager("
            f"registered={len(self._model_configs)}, "
            f"loaded={loaded})"
        )


def get_model_manager() -> ModelManager:
    return ModelManager.get_instance()


def get_model(model_name: str) -> BaseInferenceEngine:
    return get_model_manager().get_model(model_name)
