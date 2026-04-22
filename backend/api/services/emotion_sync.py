"""
情绪标签 YAML 同步服务
CR-022: 标签组管理功能
"""

import os
import yaml
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger("autoavantar-api.emotion_sync")


class EmotionSyncService:
    """情绪标签 YAML 同步服务"""
    
    def __init__(self, yaml_path: str):
        self.yaml_path = Path(yaml_path)
    
    async def sync_to_yaml(self, emotion_tags: List[Dict[str, Any]]) -> bool:
        """
        将情绪标签同步到 YAML 文件
        
        Args:
            emotion_tags: 情绪标签列表，每个标签包含 name、vec1-vec8、speed
            
        Returns:
            是否同步成功
        """
        try:
            data = {}
            for tag in emotion_tags:
                name = tag["name"]
                data[name] = {}
                
                for i in range(1, 9):
                    vec_key = f"vec{i}"
                    if vec_key in tag and tag[vec_key] is not None:
                        data[name][vec_key] = tag[vec_key]
                
                if "speed" in tag and tag["speed"] is not None:
                    data[name]["speed"] = tag["speed"]
            
            self.yaml_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            logger.info(f"情绪标签同步到 YAML 成功: {self.yaml_path}")
            return True
            
        except Exception as e:
            logger.error(f"情绪标签同步到 YAML 失败: {e}")
            return False
    
    async def load_from_yaml(self) -> List[Dict[str, Any]]:
        """
        从 YAML 文件加载情绪标签
        
        Returns:
            情绪标签列表
        """
        if not self.yaml_path.exists():
            logger.info(f"YAML 文件不存在: {self.yaml_path}")
            return []
        
        try:
            with open(self.yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data:
                return []
            
            tags = []
            for name, params in data.items():
                tag = {"name": name}
                
                for i in range(1, 9):
                    vec_key = f"vec{i}"
                    tag[vec_key] = params.get(vec_key, 0.0)
                
                tag["speed"] = params.get("speed", 1.0)
                tags.append(tag)
            
            logger.info(f"从 YAML 加载情绪标签成功: {len(tags)} 个")
            return tags
            
        except Exception as e:
            logger.error(f"从 YAML 加载情绪标签失败: {e}")
            return []