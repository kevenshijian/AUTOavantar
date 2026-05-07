"""
引擎模块初始化
提供统一的引擎管理接口
"""

import os
import logging
from typing import Dict, Any, Optional

import yaml

from core.engines.gpu_manager import (
    GPUResourceManager,
    EngineType,
    get_gpu_manager,
    reset_gpu_manager
)

logger = logging.getLogger("autoavantar.engines")


def create_engines_from_config(
    config_path: Optional[str] = None,
    project_root: Optional[str] = None,
    low_memory_mode: bool = False
) -> Dict[str, Any]:
    """
    从配置文件创建引擎实例

    Args:
        config_path: 配置文件路径，None 则使用默认路径
        project_root: 项目根目录，用于解析相对路径
        low_memory_mode: 是否启用低显存模式（True 时不预加载模型）

    Returns:
        包含 tts_engine 和 heygem_engine 的字典

    配置文件格式（YAML）：
        tts:
          cfg_path: checkpoints/indextts/config.yaml
          model_dir: checkpoints/indextts
          use_fp16: true
          managed: true

        heygem:
          heygem_root: engines/heygem
          batch_size: 4
          managed: true
    """
    # 确定项目根目录
    if project_root is None:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # 确定配置文件路径
    if config_path is None:
        config_path = os.path.join(project_root, "backend", "config", "engine_config.yaml")

    # 默认配置
    default_config = {
        "tts": {
            "cfg_path": "checkpoints/config.yaml",
            "model_dir": "checkpoints",
            "use_fp16": True,
            "managed": True
        },
        "heygem": {
            "heygem_root": "engines/heygem",
            "batch_size": 4,
            "managed": True
        }
    }

    # 加载配置文件
    config = default_config.copy()
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
            if loaded_config:
                # 合并配置（保留默认值）
                for key in default_config:
                    if key in loaded_config:
                        config[key] = {**default_config[key], **loaded_config[key]}
                logger.info(f"已加载引擎配置: {config_path}")
        except Exception as e:
            logger.warning(f"加载引擎配置失败，使用默认值: {e}")
    else:
        logger.info(f"配置文件不存在，使用默认配置: {config_path}")

    # 根据低显存模式决定是否预加载模型
    preload_model = not low_memory_mode
    logger.info(f"低显存模式: {low_memory_mode}, 预加载模型: {preload_model}")

    # 创建引擎实例
    engines = {}

    # 创建 TTSEngine
    try:
        from core.engines.tts_engine import TTSEngine

        tts_cfg = config.get("tts", default_config["tts"])
        tts_cfg_path = tts_cfg.get("cfg_path", "checkpoints/config.yaml")
        tts_model_dir = tts_cfg.get("model_dir", "checkpoints")

        # 解析相对路径
        if not os.path.isabs(tts_cfg_path):
            tts_cfg_path = os.path.join(project_root, tts_cfg_path)
        if not os.path.isabs(tts_model_dir):
            tts_model_dir = os.path.join(project_root, tts_model_dir)

        tts_engine = TTSEngine(
            cfg_path=tts_cfg_path,
            model_dir=tts_model_dir,
            use_fp16=tts_cfg.get("use_fp16", True),
            managed=tts_cfg.get("managed", True),
            preload_model=preload_model
        )

        engines["tts_engine"] = tts_engine
        logger.info("TTSEngine 创建成功")

    except Exception as e:
        logger.error(f"创建 TTSEngine 失败: {e}")
        engines["tts_engine"] = None

    # 创建 HeyGemEngine
    try:
        from core.engines.heygem_engine import HeyGemEngine

        heygem_cfg = config.get("heygem", default_config["heygem"])
        heygem_root = heygem_cfg.get("heygem_root", "engines/heygem")

        # 解析相对路径
        if not os.path.isabs(heygem_root):
            heygem_root = os.path.join(project_root, heygem_root)

        heygem_engine = HeyGemEngine(
            heygem_root=heygem_root,
            batch_size=heygem_cfg.get("batch_size", 4),
            managed=heygem_cfg.get("managed", True),
            preload_model=preload_model
        )

        engines["heygem_engine"] = heygem_engine
        logger.info("HeyGemEngine 创建成功")

    except Exception as e:
        logger.error(f"创建 HeyGemEngine 失败: {e}")
        engines["heygem_engine"] = None

    return engines


__all__ = [
    'GPUResourceManager',
    'EngineType',
    'get_gpu_manager',
    'reset_gpu_manager',
    'create_engines_from_config'
]
