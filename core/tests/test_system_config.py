"""
测试系统配置管理器

验证 SystemConfigManager 的持久化存储功能
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

# 测试目标模块路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSystemConfig:
    """测试 SystemConfig 数据类"""

    def test_default_values(self):
        """默认值测试"""
        from core.system_config import SystemConfig
        
        config = SystemConfig()
        assert config.low_memory_mode == False

    def test_to_dict(self):
        """序列化为字典"""
        from core.system_config import SystemConfig
        
        config = SystemConfig(low_memory_mode=True)
        result = config.to_dict()
        
        assert isinstance(result, dict)
        assert result["low_memory_mode"] == True

    def test_from_dict(self):
        """从字典反序列化"""
        from core.system_config import SystemConfig
        
        data = {"low_memory_mode": True}
        config = SystemConfig.from_dict(data)
        
        assert config.low_memory_mode == True

    def test_from_dict_missing_key_uses_default(self):
        """字典缺少键时使用默认值"""
        from core.system_config import SystemConfig
        
        data = {}
        config = SystemConfig.from_dict(data)
        
        assert config.low_memory_mode == False


class TestSystemConfigManager:
    """测试 SystemConfigManager"""

    def test_load_with_nonexistent_file_uses_defaults(self):
        """配置文件不存在时使用默认值"""
        from core.system_config import SystemConfigManager
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "nonexistent_config.json")
            manager = SystemConfigManager(config_path)
            
            config = manager.load()
            
            assert config.low_memory_mode == False
            assert not os.path.exists(config_path)  # 不自动创建文件

    def test_set_and_get_low_memory_mode(self):
        """设置和获取低显存模式"""
        from core.system_config import SystemConfigManager
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.json")
            manager = SystemConfigManager(config_path)
            manager.load()
            
            result = manager.set_low_memory_mode(True)
            
            assert result == True
            assert manager.get_low_memory_mode() == True

    def test_save_creates_valid_json_file(self):
        """保存后配置文件为有效 JSON"""
        from core.system_config import SystemConfigManager
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.json")
            manager = SystemConfigManager(config_path)
            manager.load()
            manager.set_low_memory_mode(True)
            manager.save()
            
            assert os.path.exists(config_path)
            
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert data["low_memory_mode"] == True

    def test_persistence_after_reload(self):
        """重新加载后设置值保持不变 → AC-219"""
        from core.system_config import SystemConfigManager
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.json")
            
            # 第一次加载并设置
            manager1 = SystemConfigManager(config_path)
            manager1.load()
            manager1.set_low_memory_mode(True)
            manager1.save()
            
            # 第二次加载（模拟重启系统）
            manager2 = SystemConfigManager(config_path)
            manager2.load()
            
            assert manager2.get_low_memory_mode() == True

    def test_set_low_memory_mode_false(self):
        """设置低显存模式为 False"""
        from core.system_config import SystemConfigManager
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.json")
            manager = SystemConfigManager(config_path)
            manager.load()
            
            manager.set_low_memory_mode(True)
            assert manager.get_low_memory_mode() == True
            
            manager.set_low_memory_mode(False)
            assert manager.get_low_memory_mode() == False

    def test_load_existing_config_file(self):
        """加载已存在的配置文件"""
        from core.system_config import SystemConfigManager
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.json")
            
            # 预先创建配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({"low_memory_mode": True}, f)
            
            manager = SystemConfigManager(config_path)
            config = manager.load()
            
            assert config.low_memory_mode == True

    def test_load_corrupted_json_uses_defaults(self):
        """配置文件损坏时使用默认值"""
        from core.system_config import SystemConfigManager
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.json")
            
            # 写入无效 JSON
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write("not a valid json")
            
            manager = SystemConfigManager(config_path)
            config = manager.load()
            
            assert config.low_memory_mode == False


class TestGetConfigManager:
    """测试全局单例获取"""

    def test_returns_singleton_instance(self):
        """get_config_manager 返回全局单例"""
        from core.system_config import get_config_manager, _reset_config_manager
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 重置单例
            _reset_config_manager()
            
            # 设置临时配置路径
            import core.system_config as module
            original_path = module._default_config_path
            module._default_config_path = os.path.join(tmp_dir, "config.json")
            
            try:
                manager1 = get_config_manager()
                manager2 = get_config_manager()
                
                assert manager1 is manager2
            finally:
                module._default_config_path = original_path
                _reset_config_manager()
