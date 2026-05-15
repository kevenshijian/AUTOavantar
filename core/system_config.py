"""
SystemConfig - 系统配置管理模块
负责持久化存储系统级设置（如低显存模式）
"""

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SystemConfig:
    """系统配置数据类"""
    low_memory_mode: bool = False  # 低显存模式，默认关闭
    ultra_low_memory: bool = False  # 超低显存模式，默认关闭
    enable_precise_subtitle: bool = False  # 精准字幕功能，默认关闭

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "low_memory_mode": self.low_memory_mode,
            "ultra_low_memory": self.ultra_low_memory,
            "enable_precise_subtitle": self.enable_precise_subtitle
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SystemConfig":
        """从字典反序列化"""
        return cls(
            low_memory_mode=data.get("low_memory_mode", False),
            ultra_low_memory=data.get("ultra_low_memory", False),
            enable_precise_subtitle=data.get("enable_precise_subtitle", False)
        )


class SystemConfigManager:
    """系统配置管理器 - 负责配置的加载、保存和访问"""
    
    def __init__(self, config_path: str = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为 backend/data/system_config.json
        """
        if config_path is None:
            # 默认路径
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "backend", "data", "system_config.json")
        
        self.config_path = config_path
        self._config: Optional[SystemConfig] = None
        self._lock = threading.Lock()
    
    def load(self) -> SystemConfig:
        """加载配置
        
        如果配置文件不存在或损坏，返回默认配置
        
        Returns:
            SystemConfig: 配置对象
        """
        with self._lock:
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self._config = SystemConfig.from_dict(data)
                    logger.info(f"系统配置已加载: {self.config_path}")
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"配置文件损坏或无法读取，使用默认配置: {e}")
                    self._config = SystemConfig()
            else:
                logger.info("配置文件不存在，使用默认配置")
                self._config = SystemConfig()
            
            return self._config
    
    def save(self) -> bool:
        """保存配置到文件
        
        Returns:
            bool: 是否保存成功
        """
        with self._lock:
            if self._config is None:
                logger.warning("配置未加载，无法保存")
                return False
            
            try:
                # 确保目录存在
                config_dir = os.path.dirname(self.config_path)
                if config_dir:
                    os.makedirs(config_dir, exist_ok=True)
                
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
                
                logger.info(f"系统配置已保存: {self.config_path}")
                return True
            except IOError as e:
                logger.error(f"保存配置失败: {e}")
                return False
    
    def set_low_memory_mode(self, enabled: bool) -> bool:
        """设置低显存模式
        
        Args:
            enabled: 是否启用低显存模式
            
        Returns:
            bool: 是否设置成功
        """
        with self._lock:
            if self._config is None:
                self.load()
            
            self._config.low_memory_mode = enabled
            logger.info(f"低显存模式已设置为: {enabled}")
        
        # 自动保存
        return self.save()
    
    def get_low_memory_mode(self) -> bool:
        """获取低显存模式

        Returns:
            bool: 是否启用低显存模式
        """
        with self._lock:
            if self._config is None:
                self.load()
            return self._config.low_memory_mode

    def set_ultra_low_memory(self, enabled: bool) -> bool:
        """设置超低显存模式

        Args:
            enabled: 是否启用超低显存模式

        Returns:
            bool: 是否设置成功
        """
        with self._lock:
            if self._config is None:
                self.load()

            self._config.ultra_low_memory = enabled
            logger.info(f"超低显存模式已设置为: {enabled}")

        # 自动保存
        return self.save()

    def get_ultra_low_memory(self) -> bool:
        """获取超低显存模式

        Returns:
            bool: 是否启用超低显存模式
        """
        with self._lock:
            if self._config is None:
                self.load()
            return self._config.ultra_low_memory

    def set_enable_precise_subtitle(self, enabled: bool) -> bool:
        """设置精准字幕功能

        Args:
            enabled: 是否启用精准字幕功能

        Returns:
            bool: 是否设置成功
        """
        with self._lock:
            if self._config is None:
                self.load()

            self._config.enable_precise_subtitle = enabled
            logger.info(f"精准字幕功能已设置为：{enabled}")

        # 自动保存
        return self.save()

    def get_enable_precise_subtitle(self) -> bool:
        """获取精准字幕功能

        Returns:
            bool: 是否启用精准字幕功能
        """
        with self._lock:
            if self._config is None:
                self.load()
            return self._config.enable_precise_subtitle


# 全局配置管理器实例（单例模式）
_config_manager_instance: Optional[SystemConfigManager] = None
_config_manager_lock = threading.Lock()

# 默认配置路径
_default_config_path: Optional[str] = None


def get_config_manager() -> SystemConfigManager:
    """获取全局配置管理器实例
    
    Returns:
        SystemConfigManager: 配置管理器单例
    """
    global _config_manager_instance
    
    with _config_manager_lock:
        if _config_manager_instance is None:
            config_path = _default_config_path  # 可能为 None，使用默认值
            _config_manager_instance = SystemConfigManager(config_path)
            _config_manager_instance.load()
            logger.info("全局配置管理器已创建")
        
        return _config_manager_instance


def set_default_config_path(path: str):
    """设置默认配置路径（用于测试或自定义路径）
    
    Args:
        path: 配置文件路径
    """
    global _default_config_path
    _default_config_path = path


def _reset_config_manager():
    """重置全局配置管理器（仅用于测试）"""
    global _config_manager_instance
    with _config_manager_lock:
        _config_manager_instance = None
