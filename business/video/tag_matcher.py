"""
标签匹配算法
实现文案、音频、视频素材基于标签的精准匹配
"""
import json
import logging
import os
import random
import sqlite3
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 数据库路径（与 DatabaseService 一致）
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "backend", "data")
DB_PATH = os.path.join(DB_DIR, "app.db")


@dataclass
class MatchScore:
    """匹配分数"""
    video_path: str
    emotion_match_score: float = 0.0
    scene_match_score: float = 0.0
    total_score: float = 0.0


def _load_scene_tags_from_db(group_id: Optional[int] = None) -> Dict[str, List[str]]:
    """
    使用同步 sqlite3 从数据库加载场景标签
    
    Args:
        group_id: 要加载的标签组ID，None表示加载默认标签组
        
    Returns:
        {标签名: [相似标签列表]} 字典，加载失败返回空字典
    """
    # 尝试多个可能的数据库路径
    search_paths = [
        DB_PATH,
        os.path.join("backend", "data", "app.db"),
        os.path.join("data", "app.db"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend", "data", "app.db")),
    ]
    
    db_file = None
    for p in search_paths:
        if os.path.exists(p):
            db_file = p
            break
    
    if not db_file:
        logger.debug(f"未找到数据库文件，搜索路径: {search_paths}")
        return {}
    
    try:
        conn = sqlite3.connect(db_file, timeout=5.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if group_id is not None:
            # 加载指定的标签组
            cursor.execute(
                "SELECT id FROM tag_groups WHERE id = ? AND type = 'scene'",
                (group_id,)
            )
            group = cursor.fetchone()
        else:
            # 查找默认场景标签组
            cursor.execute(
                "SELECT id FROM tag_groups WHERE is_default = 1 AND type = 'scene' LIMIT 1"
            )
            group = cursor.fetchone()
            
            if not group:
                # 没有默认组，取第一个场景标签组
                cursor.execute(
                    "SELECT id FROM tag_groups WHERE type = 'scene' ORDER BY created_at ASC LIMIT 1"
                )
                group = cursor.fetchone()
        
        if not group:
            conn.close()
            return {}
        
        selected_group_id = group["id"]
        
        # 加载标签
        cursor.execute(
            "SELECT name, similar_tags FROM tags WHERE group_id = ?",
            (selected_group_id,)
        )
        tags = cursor.fetchall()
        
        result = {}
        for tag in tags:
            name = tag["name"]
            similar = json.loads(tag["similar_tags"]) if tag["similar_tags"] else []
            result[name] = similar
        
        conn.close()
        logger.info(f"从数据库同步加载标签组 {selected_group_id}，共 {len(result)} 个标签: {list(result.keys())}")
        return result
        
    except Exception as e:
        logger.error(f"从数据库加载标签失败: {e}")
        return {}


class TagMatcher:
    """标签匹配器"""
    
    def __init__(self, db=None):
        """初始化标签匹配器
        
        Args:
            db: 数据库服务实例（可选，保留兼容性）
        """
        self.db = db
        self.current_group_id: Optional[int] = None
        
        # ==================== 情绪标签映射 ====================
        # 标准情绪标签（视频端支持的8个标签）
        self.standard_emotion_tags = [
            "开心", "生气", "难过", "害怕", "厌恶", "低落", "惊喜", "冷静"
        ]
        
        self.emotion_mapping = {
            # 开心组
            "开心": "开心",
            "高兴": "开心",
            
            # 惊喜组
            "惊喜": "惊喜",
            "兴奋": "惊喜",
            "激动": "惊喜",
            
            # 生气组
            "生气": "生气",
            "愤怒": "生气",
            
            # 难过组
            "难过": "难过",
            "悲伤": "难过",
            "伤心": "难过",
            
            # 害怕组
            "害怕": "害怕",
            "恐惧": "害怕",
            "惊慌": "害怕",
            
            # 厌恶组
            "厌恶": "厌恶",
            "讨厌": "厌恶",
            "憎恨": "厌恶",
            
            # 低落组
            "低落": "低落",
            "忧伤": "低落",
            "沮丧": "低落",
            
            # 平淡/冷静组
            "平淡": "冷静",
            "冷静": "冷静",
        }
        
        # ==================== 情绪相似关系（优先级匹配）====================
        self.emotion_similarity = {
            "开心": ["开心", "惊喜", "生气"],
            "惊喜": ["惊喜", "开心", "生气"],
            "生气": ["生气", "厌恶", "难过"],
            "难过": ["难过", "低落", "害怕"],
            "害怕": ["害怕", "难过", "生气"],
            "厌恶": ["厌恶", "生气", "难过"],
            "低落": ["低落", "难过", "冷静"],
            "冷静": ["冷静", "低落", "开心"],
        }
        
        # ==================== 场景标签映射（从数据库动态加载）====================
        self._scene_similarity: Dict[str, List[str]] = {}
        self.loaded_scene_similarity = self._scene_similarity  # 兼容测试用的公共属性
        self._scene_tags_loaded = False
        self._load_scene_tags()
    
    def _load_scene_tags(self, group_id: Optional[int] = None):
        """从数据库同步加载场景标签数据
        
        Args:
            group_id: 要加载的标签组ID，None表示加载默认标签组
        """
        loaded = _load_scene_tags_from_db(group_id)
        if loaded:
            self._scene_similarity = loaded
            self.loaded_scene_similarity = self._scene_similarity  # 同步更新测试用属性
            self.current_group_id = group_id
            logger.info(f"从数据库同步加载标签组 {group_id}，共 {len(loaded)} 个标签: {list(loaded.keys())}")
        elif group_id is not None:
            # 指定加载的标签组不存在时，返回空
            self._scene_similarity = {}
            self.loaded_scene_similarity = self._scene_similarity  # 同步更新测试用属性
            self.current_group_id = None
            logger.warning(f"指定的标签组 {group_id} 不存在，加载失败")
        else:
            # 数据库中没有数据时的最小回退（仅用于首次安装无数据场景）
            self._scene_similarity = {
                "环境展示": ["产品展示", "细节展示"],
                "产品展示": ["功能介绍", "使用效果"],
                "细节展示": ["产品展示", "功能介绍"],
                "功能介绍": ["细节展示", "使用效果"],
                "使用效果": ["产品展示", "功能介绍"],
            }
            self.loaded_scene_similarity = self._scene_similarity  # 同步更新测试用属性
            self.current_group_id = None
            logger.info("数据库无标签数据，使用最小回退配置")
        
        self._scene_tags_loaded = True
    
    async def load_tag_group(self, group_id: int) -> bool:
        """加载指定的标签组，替换当前使用的场景标签
        
        Args:
            group_id: 标签组ID
            
        Returns:
            是否加载成功
        """
        try:
            self._scene_tags_loaded = False
            self._load_scene_tags(group_id)
            return len(self._scene_similarity) > 0
        except Exception as e:
            logger.error(f"加载标签组 {group_id} 失败: {e}")
            return False
    
    def reload_scene_tags(self):
        """强制重新从数据库加载场景标签（标签设置变更后调用）"""
        self._scene_tags_loaded = False
        # 保留当前使用的标签组ID重新加载
        current_group = self.current_group_id
        self._scene_similarity = {}
        self._load_scene_tags(current_group)
        logger.info(f"场景标签已重新加载: {list(self._scene_similarity.keys())}")
    
    def get_similar_scenes(self, scene_tag: str) -> List[str]:
        """
        获取场景标签的相似标签列表
        
        Args:
            scene_tag: 场景标签
            
        Returns:
            相似标签列表
        """
        return self._scene_similarity.get(scene_tag, [])
    
    def is_standard_emotion(self, tag: str) -> bool:
        """检查是否是标准情绪标签"""
        return tag in self.standard_emotion_tags
    
    def is_opening_or_ending(self, tag: str) -> bool:
        """检查是否是开场或结束标签"""
        return tag in ["开场", "结束"]
    
    def is_scene_tag(self, tag: str) -> bool:
        """
        检查是否是场景标签
        
        基于数据库中加载的标签组动态判断
        """
        # 开场/结束不算场景标签（它们有专用处理逻辑）
        if tag in ["开场", "结束"]:
            return False
        return tag in self._scene_similarity
    
    def is_emotion_tag(self, tag: str) -> bool:
        """检查是否是情绪标签"""
        return tag in self.emotion_mapping
    
    def get_mapped_emotion(self, emotion_tag: str) -> Optional[str]:
        """将文案情绪标签映射到标准视频情绪标签"""
        return self.emotion_mapping.get(emotion_tag)
    
    def match_emotion_video(self,
                           target_emotion: str,
                           emotion_videos: List[Dict]) -> Optional[MatchScore]:
        """
        在循环视频区域匹配情绪标签（支持优先级匹配）
        """
        mapped_emotion = self.get_mapped_emotion(target_emotion)
        if not mapped_emotion:
            logger.warning(f"情绪标签 '{target_emotion}' 无法映射到标准标签")
            return None
        
        priority_list = self.emotion_similarity.get(mapped_emotion, [mapped_emotion])
        
        for priority, emotion_tag in enumerate(priority_list):
            matched_videos = []
            for video in emotion_videos:
                emotion_tags = video.get("emotion_tags", [])
                if emotion_tag in emotion_tags:
                    matched_videos.append(video)
            
            if matched_videos:
                selected = random.choice(matched_videos)
                score = 1.0 - (priority * 0.2)
                logger.info(f"情绪标签 '{target_emotion}' → 映射为 '{mapped_emotion}', "
                           f"按优先级匹配到 '{emotion_tag}'，"
                           f"在 {len(matched_videos)} 个视频中随机选择: {selected['file_path']}")
                return MatchScore(
                    video_path=selected["file_path"],
                    emotion_match_score=score,
                    scene_match_score=0.0,
                    total_score=score
                )
        
        logger.warning(f"情绪标签 '{target_emotion}' (映射为 '{mapped_emotion}') "
                       f"在所有优先级标签 {priority_list} 中都没有找到匹配视频")
        return None
    
    def match_scene_video(self,
                         target_scene: str,
                         scene_videos: List[Dict]) -> Optional[MatchScore]:
        """
        在场景视频区域匹配场景标签
        """
        # 第一步：尝试精确匹配
        exact_matches = []
        for video in scene_videos:
            scene_tags = video.get("scene_tags", [])
            if target_scene in scene_tags:
                exact_matches.append(video)
        
        if exact_matches:
            selected = random.choice(exact_matches)
            logger.info(f"场景标签 '{target_scene}' 精确匹配，"
                       f"在 {len(exact_matches)} 个匹配视频中随机选择: {selected['file_path']}")
            return MatchScore(
                video_path=selected["file_path"],
                emotion_match_score=0.0,
                scene_match_score=1.0,
                total_score=1.0
            )
        
        # 第二步：尝试相似标签匹配
        similar_scenes = self.get_similar_scenes(target_scene)
        for similar_tag in similar_scenes:
            similar_matches = []
            for video in scene_videos:
                scene_tags = video.get("scene_tags", [])
                if similar_tag in scene_tags:
                    similar_matches.append(video)
            
            if similar_matches:
                selected = random.choice(similar_matches)
                logger.info(f"场景标签 '{target_scene}' 没有精确匹配，"
                           f"使用相似标签 '{similar_tag}'，随机选择: {selected['file_path']}")
                return MatchScore(
                    video_path=selected["file_path"],
                    emotion_match_score=0.0,
                    scene_match_score=0.7,
                    total_score=0.7
                )
        
        logger.warning(f"场景标签 '{target_scene}' 没有找到匹配（包括相似标签 {similar_scenes}）")
        return None


# ==================== 全局单例 ====================
_tag_matcher_instance: Optional[TagMatcher] = None


def get_tag_matcher(db=None) -> TagMatcher:
    """
    获取全局标签匹配器实例
    
    首次调用时自动从数据库加载标签数据（使用同步 sqlite3，无需异步）
    
    Returns:
        TagMatcher 实例
    """
    global _tag_matcher_instance
    if _tag_matcher_instance is None:
        _tag_matcher_instance = TagMatcher(db=db)
        logger.info(f"标签匹配器已创建，场景标签: {list(_tag_matcher_instance._scene_similarity.keys())}")
    return _tag_matcher_instance


def reload_tag_matcher():
    """
    强制重新加载标签匹配器的场景标签数据
    
    在标签设置变更后调用此函数
    """
    global _tag_matcher_instance
    if _tag_matcher_instance is not None:
        _tag_matcher_instance.reload_scene_tags()
    else:
        # 实例不存在，创建一个新的
        _tag_matcher_instance = TagMatcher()


# 保留兼容性的异步函数
async def init_tag_matcher(db=None) -> TagMatcher:
    """
    初始化标签匹配器（兼容性接口，现在内部使用同步加载）
    """
    matcher = get_tag_matcher(db=db)
    # 如果传入了 db，尝试重新加载以确保数据最新
    if db:
        matcher.reload_scene_tags()
    return matcher
