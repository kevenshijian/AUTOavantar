"""
素材库管理模块
实现视频素材、BGM 素材、角色素材、标签的存储、检索、元数据管理
"""

import logging
import os
import json
import sqlite3
import shutil
import hashlib
import uuid
import platform
import subprocess
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
import cv2
import numpy as np

from core.models.task import SceneType
from core.models.material import (
    VideoItem,
    AudioItem,
    FaceAnalysisConfig,
    RoleMaterial as CoreRoleMaterial,
    BgmMaterial as CoreBgmMaterial,
    GlobalTag as CoreGlobalTag,
    PermissionType,
    BgmCopyrightType,
    TagType,
    VersionInfo
)

logger = logging.getLogger(__name__)


@dataclass
class VideoMaterial:
    """视频素材（兼容旧接口）"""
    id: str
    name: str
    file_path: str
    scene_type: str
    emotion_tags: List[str]
    duration: float
    thumbnail_path: str
    created_at: str
    metadata: Dict[str, Any]


@dataclass
class BgmMaterial:
    """BGM 素材（兼容旧接口）"""
    id: str
    name: str
    file_path: str
    duration: float
    created_at: str
    metadata: Dict[str, Any]
    emotion_tags: List[str] = field(default_factory=list)
    scene_category: str = ""
    copyright_info: str = ""
    is_deleted: bool = False


@dataclass
class RoleMaterial:
    """角色素材（兼容旧接口）"""
    role_id: str
    role_name: str
    cover_url: Optional[str] = None
    use_count: int = 0
    remark: Optional[str] = None
    permission: str = "private"
    opening: List[Dict] = field(default_factory=list)
    loop: List[Dict] = field(default_factory=list)
    scene: List[Dict] = field(default_factory=list)
    ending: List[Dict] = field(default_factory=list)
    face_analysis_config: Dict = field(default_factory=lambda: {
        "head_angle_threshold": 30.0,
        "mouth_occlusion_threshold": 0.5
    })
    audio_list: List[Dict] = field(default_factory=list)
    is_double_mode: bool = False
    left_audio_id: Optional[str] = None
    right_audio_id: Optional[str] = None
    current_version: str = "1.0"
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class GlobalTag:
    """全局标签（兼容旧接口）"""
    tag_id: str
    tag_name: str
    tag_type: str
    sort: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class FaceAnalysisResult:
    """面部分析结果"""
    video_path: str
    total_frames: int
    valid_frames: int
    mouth_occlusion_frames: int
    side_head_frames: int
    is_qualified: bool = True
    reasons: List[str] = field(default_factory=list)
    details: List[Dict] = field(default_factory=list)
    # 合格帧索引列表（用于后续过滤视频）
    valid_frame_indices: List[int] = field(default_factory=list)


class MaterialLibrary:
    """素材库管理器"""

    DEFAULT_EMOTION_TAGS = ["中性", "温柔", "活泼", "激昂", "严肃", "悲伤", "惊喜"]
    DEFAULT_SCENE_TAGS = ["开场", "循环", "场景", "结束", "日常", "商务", "教育", "娱乐"]

    def __init__(self, db_path: str = "data/materials.db"):
        """
        初始化素材库

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                scene_type TEXT NOT NULL,
                emotion_tags TEXT,
                duration REAL,
                thumbnail_path TEXT,
                created_at TEXT,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bgms (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                duration REAL,
                created_at TEXT,
                metadata TEXT,
                emotion_tags TEXT,
                scene_category TEXT,
                scene_tags TEXT,
                copyright_info TEXT,
                copyright_type TEXT DEFAULT 'free',
                volume REAL DEFAULT 1.0,
                is_deleted INTEGER DEFAULT 0
            )
        """)

        # 数据库迁移: 确保 is_deleted 列存在
        try:
            cursor.execute("SELECT is_deleted FROM bgms LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE bgms ADD COLUMN is_deleted INTEGER DEFAULT 0")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                role_id TEXT PRIMARY KEY,
                role_name TEXT NOT NULL,
                cover_url TEXT,
                use_count INTEGER DEFAULT 0,
                remark TEXT,
                permission TEXT DEFAULT 'private',
                opening TEXT,
                loop TEXT,
                scene TEXT,
                ending TEXT,
                face_analysis_config TEXT,
                audio_list TEXT,
                is_double_mode INTEGER DEFAULT 0,
                left_audio_id TEXT,
                right_audio_id TEXT,
                current_version TEXT DEFAULT '1.0',
                version_history TEXT,
                tags TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        try:
            cursor.execute("SELECT is_double_mode FROM roles LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE roles ADD COLUMN is_double_mode INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE roles ADD COLUMN left_audio_id TEXT")
            cursor.execute("ALTER TABLE roles ADD COLUMN right_audio_id TEXT")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                tag_id TEXT PRIMARY KEY,
                tag_name TEXT NOT NULL,
                tag_type TEXT NOT NULL,
                sort INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        self._init_default_tags(cursor)

        conn.commit()
        conn.close()
        logger.info(f"素材库数据库初始化完成: {self.db_path}")

    def _init_default_tags(self, cursor: sqlite3.Cursor):
        """初始化默认标签"""
        cursor.execute("SELECT COUNT(*) FROM tags")
        if cursor.fetchone()[0] == 0:
            now = datetime.now().isoformat()
            for idx, tag_name in enumerate(self.DEFAULT_EMOTION_TAGS):
                tag_id = f"tag_{hashlib.md5(tag_name.encode()).hexdigest()[:8]}"
                cursor.execute("""
                    INSERT OR IGNORE INTO tags (tag_id, tag_name, tag_type, sort, created_at, updated_at)
                    VALUES (?, ?, 'emotion', ?, ?, ?)
                """, (tag_id, tag_name, idx, now, now))

            for idx, tag_name in enumerate(self.DEFAULT_SCENE_TAGS):
                tag_id = f"tag_{hashlib.md5(tag_name.encode()).hexdigest()[:8]}"
                cursor.execute("""
                    INSERT OR IGNORE INTO tags (tag_id, tag_name, tag_type, sort, created_at, updated_at)
                    VALUES (?, ?, 'scene', ?, ?, ?)
                """, (tag_id, tag_name, idx + 100, now, now))

            logger.info("已初始化默认标签")

    def add_video(
        self,
        file_path: str,
        name: str,
        scene_type: str,
        emotion_tags: Optional[List[str]] = None,
        thumbnail_dir: str = "data/materials/thumbnails"
    ) -> VideoMaterial:
        """添加视频素材"""
        file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
        video_id = f"vid_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_hash}"

        duration = self._get_video_duration(file_path)
        thumbnail_path = self._generate_thumbnail(file_path, thumbnail_dir, video_id)
        storage_path = self._copy_to_storage(file_path, "videos", video_id)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        emotion_tags_str = json.dumps(emotion_tags or [])

        cursor.execute("""
            INSERT INTO videos (id, name, file_path, scene_type, emotion_tags, duration, thumbnail_path, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            video_id,
            name,
            storage_path,
            scene_type,
            emotion_tags_str,
            duration,
            thumbnail_path,
            datetime.now().isoformat(),
            "{}"
        ))

        conn.commit()
        conn.close()

        material = VideoMaterial(
            id=video_id,
            name=name,
            file_path=storage_path,
            scene_type=scene_type,
            emotion_tags=emotion_tags or [],
            duration=duration,
            thumbnail_path=thumbnail_path,
            created_at=datetime.now().isoformat(),
            metadata={}
        )

        logger.info(f"添加视频素材: {name} ({video_id})")
        return material

    def add_bgm(
        self,
        file_path: str,
        name: str,
        emotion_tags: Optional[List[str]] = None,
        scene_category: str = "",
        copyright_info: str = "",
        volume: float = 0.3,
        fade_in: float = 0.0,
        fade_out: float = 0.0
    ) -> BgmMaterial:
        """
        添加 BGM 素材

        Args:
            file_path: 音频文件路径
            name: 素材名称
            emotion_tags: 情绪标签列表
            scene_category: 场景分类
            copyright_info: 版权信息
            volume: 音量 (0.0 - 1.0)
            fade_in: 淡入时间（秒）
            fade_out: 淡出时间（秒）

        Returns:
            BGM 素材对象
        """
        file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
        bgm_id = f"bgm_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_hash}"

        duration = self._get_audio_duration(file_path)
        storage_path = self._copy_to_storage(file_path, "bgm", bgm_id)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        emotion_tags_str = json.dumps(emotion_tags or [])
        now = datetime.now().isoformat()

        # 存储扩展属性
        metadata = json.dumps({
            'volume': volume,
            'fade_in': fade_in,
            'fade_out': fade_out
        })

        cursor.execute("""
            INSERT INTO bgms (id, name, file_path, duration, created_at, metadata, emotion_tags, scene_category, copyright_info, is_deleted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            bgm_id,
            name,
            storage_path,
            duration,
            now,
            metadata,
            emotion_tags_str,
            scene_category,
            copyright_info
        ))

        conn.commit()
        conn.close()

        material = BgmMaterial(
            id=bgm_id,
            name=name,
            file_path=storage_path,
            duration=duration,
            created_at=now,
            metadata={},
            emotion_tags=emotion_tags or [],
            scene_category=scene_category,
            copyright_info=copyright_info,
            is_deleted=False
        )

        logger.info(f"添加 BGM 素材: {name} ({bgm_id})")
        return material

    def add_bgm_with_tags(
        self,
        file_path: str,
        name: str,
        emotion_tags: Optional[List[str]] = None,
        scene_tags: Optional[List[str]] = None,
        copyright_type: str = "free",
        copyright_remark: Optional[str] = None
    ) -> CoreBgmMaterial:
        """
        添加BGM并设置情绪标签和场景分类

        Args:
            file_path: 音频文件路径
            name: 素材名称
            emotion_tags: 情绪标签列表
            scene_tags: 场景标签列表
            copyright_type: 版权类型 (free/authorized/original)
            copyright_remark: 版权备注

        Returns:
            BGM 素材对象 (使用 core.models.material)
        """
        file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
        bgm_id = f"bgm_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_hash}"

        duration = self._get_audio_duration(file_path)
        storage_path = self._copy_to_storage(file_path, "bgm", bgm_id)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        emotion_tags_str = json.dumps(emotion_tags or [])
        scene_tags_str = json.dumps(scene_tags or [])
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO bgms (
                id, name, file_path, duration, created_at, metadata,
                emotion_tags, scene_tags, copyright_type, copyright_remark,
                volume, is_deleted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, 0)
        """, (
            bgm_id,
            name,
            storage_path,
            duration,
            now,
            "{}",
            emotion_tags_str,
            scene_tags_str,
            copyright_type,
            copyright_remark or ""
        ))

        conn.commit()
        conn.close()

        material = CoreBgmMaterial(
            bgm_id=bgm_id,
            bgm_name=name,
            duration=duration,
            file_size=file_size,
            file_path=storage_path,
            emotion_tags=emotion_tags or [],
            scene_tags=scene_tags or [],
            copyright_type=BgmCopyrightType(copyright_type),
            copyright_remark=copyright_remark,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        logger.info(f"添加BGM (带标签): {name} ({bgm_id}), 情绪标签: {emotion_tags}, 场景标签: {scene_tags}")
        return material

    def get_bgms_by_tag(
        self,
        tag: str,
        tag_type: str = "emotion"
    ) -> List[CoreBgmMaterial]:
        """
        按标签获取BGM

        Args:
            tag: 标签名称
            tag_type: 标签类型 (emotion/scene)

        Returns:
            BGM 素材列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if tag_type == "emotion":
            query = "SELECT * FROM bgms WHERE is_deleted = 0 AND emotion_tags LIKE ?"
        else:
            query = "SELECT * FROM bgms WHERE is_deleted = 0 AND scene_tags LIKE ?"

        cursor.execute(query, (f"%{tag}%",))
        rows = cursor.fetchall()
        conn.close()

        materials = []
        for row in rows:
            materials.append(CoreBgmMaterial(
                bgm_id=row[0],
                bgm_name=row[1],
                duration=row[3],
                file_path=row[2],
                emotion_tags=json.loads(row[6]) if row[6] else [],
                scene_tags=json.loads(row[7]) if row[7] else [],
                copyright_type=BgmCopyrightType(row[9]) if row[9] else BgmCopyrightType.FREE,
                copyright_remark=row[10] or "",
                created_at=datetime.fromisoformat(row[4]) if row[4] else datetime.now(),
                updated_at=datetime.now()
            ))

        return materials

    def normalize_bgm_volume(
        self,
        bgm_id: str,
        target_volume: float = 1.0
    ) -> bool:
        """
        音量标准化功能

        Args:
            bgm_id: BGM ID
            target_volume: 目标音量 (0.0-2.0)

        Returns:
            是否成功
        """
        if not 0.0 <= target_volume <= 2.0:
            logger.warning(f"目标音量超出范围: {target_volume}")
            return False

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT file_path FROM bgms WHERE id = ?", (bgm_id,))
        row = cursor.fetchone()

        if not row or not row[0]:
            conn.close()
            return False

        cursor.execute(
            "UPDATE bgms SET volume = ? WHERE id = ?",
            (target_volume, bgm_id)
        )

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        if success:
            logger.info(f"BGM音量标准化: {bgm_id}, 目标音量: {target_volume}")

        return success

    def get_videos(
        self,
        scene_type: Optional[str] = None,
        emotion_tag: Optional[str] = None,
        search_key: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> List[VideoMaterial]:
        """获取视频素材列表

        Args:
            scene_type: 场景类型筛选
            emotion_tag: 情绪标签筛选
            search_key: 搜索关键词（搜索名称）
            page: 页码，从1开始
            page_size: 每页数量

        Returns:
            视频素材列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM videos WHERE 1=1"
        params = []

        if scene_type:
            query += " AND scene_type = ?"
            params.append(scene_type)

        if emotion_tag:
            query += " AND emotion_tags LIKE ?"
            params.append(f"%{emotion_tag}%")

        if search_key:
            query += " AND name LIKE ?"
            params.append(f"%{search_key}%")

        # 获取总数
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # 添加分页
        offset = (page - 1) * page_size
        query += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        materials = []
        for row in rows:
            materials.append(VideoMaterial(
                id=row[0],
                name=row[1],
                file_path=row[2],
                scene_type=row[3],
                emotion_tags=json.loads(row[4]) if row[4] else [],
                duration=row[5],
                thumbnail_path=row[6],
                created_at=row[7],
                metadata=json.loads(row[8]) if row[8] else {}
            ))

        return materials

    def get_bgms(
        self,
        emotion_tag: Optional[str] = None,
        scene_category: Optional[str] = None,
        include_deleted: bool = False
    ) -> List[BgmMaterial]:
        """
        获取 BGM 素材列表

        Args:
            emotion_tag: 情绪标签筛选
            scene_category: 场景分类筛选
            include_deleted: 是否包含已删除的

        Returns:
            BGM 素材列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM bgms WHERE 1=1"
        params = []

        if not include_deleted:
            query += " AND is_deleted = ?"
            params.append(0)

        if emotion_tag:
            query += " AND emotion_tags LIKE ?"
            params.append(f"%{emotion_tag}%")

        if scene_category:
            query += " AND scene_category = ?"
            params.append(scene_category)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        materials = []
        for row in rows:
            materials.append(BgmMaterial(
                id=row[0],
                name=row[1],
                file_path=row[2],
                duration=row[3],
                created_at=row[4],
                metadata=json.loads(row[5]) if row[5] else {},
                emotion_tags=json.loads(row[6]) if row[6] else [],
                scene_category=row[7] or "",
                copyright_info=row[8] or "",
                is_deleted=bool(row[9])
            ))

        return materials

    def update_bgm(
        self,
        bgm_id: str,
        name: Optional[str] = None,
        emotion_tags: Optional[List[str]] = None,
        scene_category: Optional[str] = None,
        copyright_info: Optional[str] = None
    ) -> bool:
        """
        更新 BGM 信息

        Args:
            bgm_id: BGM ID
            name: 新名称
            emotion_tags: 新情绪标签
            scene_category: 新场景分类
            copyright_info: 新版权信息

        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if emotion_tags is not None:
            updates.append("emotion_tags = ?")
            params.append(json.dumps(emotion_tags))

        if scene_category is not None:
            updates.append("scene_category = ?")
            params.append(scene_category)

        if copyright_info is not None:
            updates.append("copyright_info = ?")
            params.append(copyright_info)

        if not updates:
            conn.close()
            return False

        params.append(bgm_id)
        cursor.execute(f"UPDATE bgms SET {', '.join(updates)} WHERE id = ?", params)

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        if success:
            logger.info(f"更新 BGM: {bgm_id}")
        return success

    def delete_bgm(self, bgm_id: str, hard_delete: bool = False) -> bool:
        """
        删除 BGM 素材

        Args:
            bgm_id: BGM ID
            hard_delete: 是否硬删除（物理删除文件）

        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if hard_delete:
            cursor.execute("SELECT file_path FROM bgms WHERE id = ?", (bgm_id,))
            row = cursor.fetchone()
            if row and row[0] and os.path.exists(row[0]):
                os.remove(row[0])

            cursor.execute("DELETE FROM bgms WHERE id = ?", (bgm_id,))
        else:
            cursor.execute("UPDATE bgms SET is_deleted = 1 WHERE id = ?", (bgm_id,))

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        if success:
            logger.info(f"删除 BGM: {bgm_id} (hard={hard_delete})")
        return success

    def delete_video(self, video_id: str) -> bool:
        """删除视频素材"""
        return self._delete_material(video_id, "videos")

    def _delete_material(self, material_id: str, table: str) -> bool:
        """删除素材"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(f"SELECT file_path, thumbnail_path FROM {table} WHERE id = ?", (material_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False

        file_path, thumbnail_path = row

        # 删除文件（支持相对路径和绝对路径）
        if file_path:
            # 尝试相对路径和绝对路径
            if os.path.exists(file_path):
                os.remove(file_path)
            elif not os.path.isabs(file_path):
                # 如果是相对路径且不存在，尝试从当前目录查找
                abs_path = os.path.abspath(file_path)
                if os.path.exists(abs_path):
                    os.remove(abs_path)

        if thumbnail_path:
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            elif not os.path.isabs(thumbnail_path):
                abs_path = os.path.abspath(thumbnail_path)
                if os.path.exists(abs_path):
                    os.remove(abs_path)

        cursor.execute(f"DELETE FROM {table} WHERE id = ?", (material_id,))
        conn.commit()
        conn.close()

        logger.info(f"删除素材: {material_id}")
        return True

    def _get_video_duration(self, video_path: str) -> float:
        """获取视频时长"""
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            return frames / fps if fps > 0 else 0.0
        except:
            return 0.0

    def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        try:
            import wave
            with wave.open(audio_path, 'r') as w:
                frames = w.getnframes()
                rate = w.getframerate()
                return frames / rate if rate > 0 else 0.0
        except:
            return 0.0

    def _generate_thumbnail(
        self,
        video_path: str,
        output_dir: str,
        video_id: str
    ) -> str:
        """生成视频缩略图

        Returns:
            相对路径，如 "data/materials/thumbnails/vid_xxx.jpg"
        """
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{video_id}.jpg")

        try:
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)

            ret, frame = cap.read()
            cap.release()

            if ret:
                frame = cv2.resize(frame, (320, 180))
                cv2.imwrite(output_path, frame)
                # 返回相对路径，而不是绝对路径
                return os.path.join(output_dir, f"{video_id}.jpg").replace('\\', '/')
        except Exception as e:
            logger.warning(f"生成缩略图失败: {e}")

        return ""

    def _copy_to_storage(
        self,
        source_path: str,
        category: str,
        material_id: str
    ) -> str:
        """复制文件到存储目录

        Returns:
            相对路径，如 "data/materials/videos/vid_xxx.mp4"
        """
        storage_dir = f"data/materials/{category}"
        os.makedirs(storage_dir, exist_ok=True)

        ext = os.path.splitext(source_path)[1]
        dest_path = os.path.join(storage_dir, f"{material_id}{ext}")

        shutil.copy2(source_path, dest_path)
        # 返回相对路径，而不是绝对路径
        return os.path.join(storage_dir, f"{material_id}{ext}").replace('\\', '/')

    def _generate_file_hash(self, file_path: str) -> str:
        """生成文件哈希"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    def create_role(
        self,
        role_name: str,
        cover_url: Optional[str] = None,
        remark: Optional[str] = None,
        permission: str = "private",
        tags: Optional[List[str]] = None,
        face_analysis_config: Optional[Dict] = None,
        opening: Optional[List[Dict]] = None,
        loop: Optional[List[Dict]] = None,
        scene: Optional[List[Dict]] = None,
        ending: Optional[List[Dict]] = None,
        audio_list: Optional[List[Dict]] = None
    ) -> RoleMaterial:
        """
        创建角色素材

        Args:
            role_name: 角色名称
            cover_url: 封面URL
            remark: 备注
            permission: 权限 (public/private/shared)
            tags: 标签列表
            face_analysis_config: 面部分析配置
            opening: 开场视频列表 (使用 VideoItem 结构)
            loop: 循环视频列表 (使用 VideoItem 结构)
            scene: 场景视频列表 (使用 VideoItem 结构)
            ending: 结束视频列表 (使用 VideoItem 结构)
            audio_list: 音频列表 (使用 AudioItem 结构)

        Returns:
            角色素材对象
        """
        file_hash = hashlib.md5(role_name.encode()).hexdigest()[:8]
        role_id = f"role_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_hash}"

        now = datetime.now().isoformat()

        default_config = {
            "head_angle_threshold": 30.0,
            "mouth_occlusion_threshold": 0.5
        }
        if face_analysis_config:
            default_config.update(face_analysis_config)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        version_history = json.dumps([{
            "version": "1.0",
            "create_time": now,
            "description": "初始版本"
        }])

        cursor.execute("""
            INSERT INTO roles (
                role_id, role_name, cover_url, use_count, remark, permission,
                opening, loop, scene, ending, face_analysis_config, audio_list,
                current_version, version_history, tags, created_at, updated_at
            ) VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, '1.0', ?, ?, ?, ?)
        """, (
            role_id,
            role_name,
            cover_url,
            remark,
            permission,
            json.dumps(opening or []),
            json.dumps(loop or []),
            json.dumps(scene or []),
            json.dumps(ending or []),
            json.dumps(default_config),
            json.dumps(audio_list or []),
            version_history,
            json.dumps(tags or []),
            now,
            now
        ))

        conn.commit()
        conn.close()

        role = RoleMaterial(
            role_id=role_id,
            role_name=role_name,
            cover_url=cover_url,
            use_count=0,
            remark=remark,
            permission=permission,
            opening=opening or [],
            loop=loop or [],
            scene=scene or [],
            ending=ending or [],
            face_analysis_config=default_config,
            audio_list=audio_list or [],
            current_version="1.0",
            tags=tags or [],
            created_at=now,
            updated_at=now
        )

        logger.info(f"创建角色素材: {role_name} ({role_id})")
        return role

    def create_role_with_video_items(
        self,
        role_name: str,
        cover_url: Optional[str] = None,
        remark: Optional[str] = None,
        permission: PermissionType = PermissionType.PRIVATE,
        tags: Optional[List[str]] = None,
        face_analysis_config: Optional[FaceAnalysisConfig] = None,
        opening: Optional[List[VideoItem]] = None,
        loop: Optional[List[VideoItem]] = None,
        scene: Optional[List[VideoItem]] = None,
        ending: Optional[List[VideoItem]] = None,
        audio_list: Optional[List[AudioItem]] = None
    ) -> CoreRoleMaterial:
        """
        创建角色素材（使用 VideoItem 和 AudioItem 数据模型）

        Args:
            role_name: 角色名称
            cover_url: 封面URL
            remark: 备注
            permission: 权限类型
            tags: 标签列表
            face_analysis_config: 面部分析配置
            opening: 开场视频列表 (VideoItem)
            loop: 循环视频列表 (VideoItem)
            scene: 场景视频列表 (VideoItem)
            ending: 结束视频列表 (VideoItem)
            audio_list: 音频列表 (AudioItem)

        Returns:
            角色素材对象 (使用 core.models.material)
        """
        file_hash = hashlib.md5(role_name.encode()).hexdigest()[:8]
        role_id = f"role_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_hash}"

        now = datetime.now()

        default_config = FaceAnalysisConfig()
        if face_analysis_config:
            default_config.head_angle_threshold = face_analysis_config.head_angle_threshold
            default_config.mouth_occlusion_threshold = face_analysis_config.mouth_occlusion_threshold

        def video_items_to_dict(items: Optional[List[VideoItem]]) -> List[Dict]:
            if not items:
                return []
            return [{"file_path": v.file_path, "emotion_tags": v.emotion_tags, "duration": v.duration} for v in items]

        def audio_items_to_dict(items: Optional[List[AudioItem]]) -> List[Dict]:
            if not items:
                return []
            return [{"file_path": a.file_path, "emotion_tag": a.emotion_tag, "denoise_enabled": a.denoise_enabled} for v in items]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        version_info = VersionInfo(version="1.0", create_time=now, description="初始版本")
        version_history = json.dumps([{
            "version": version_info.version,
            "create_time": version_info.create_time.isoformat(),
            "description": version_info.description
        }])

        cursor.execute("""
            INSERT INTO roles (
                role_id, role_name, cover_url, use_count, remark, permission,
                opening, loop, scene, ending, face_analysis_config, audio_list,
                current_version, version_history, tags, created_at, updated_at
            ) VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, '1.0', ?, ?, ?, ?)
        """, (
            role_id,
            role_name,
            cover_url,
            remark,
            permission.value,
            json.dumps(video_items_to_dict(opening)),
            json.dumps(video_items_to_dict(loop)),
            json.dumps(video_items_to_dict(scene)),
            json.dumps(video_items_to_dict(ending)),
            json.dumps({"head_angle_threshold": default_config.head_angle_threshold,
                       "mouth_occlusion_threshold": default_config.mouth_occlusion_threshold}),
            json.dumps(audio_items_to_dict(audio_list)),
            version_history,
            json.dumps(tags or []),
            now.isoformat(),
            now.isoformat()
        ))

        conn.commit()
        conn.close()

        role = CoreRoleMaterial(
            role_id=role_id,
            role_name=role_name,
            cover_url=cover_url,
            use_count=0,
            remark=remark,
            permission=permission,
            opening=opening or [],
            loop=loop or [],
            scene=scene or [],
            ending=ending or [],
            face_analysis_config=default_config,
            audio_list=audio_list or [],
            current_version="1.0",
            version_history=[version_info],
            created_at=now,
            updated_at=now
        )

        logger.info(f"创建角色素材 (VideoItem): {role_name} ({role_id})")
        return role

    def get_roles(
        self,
        name: Optional[str] = None,
        tag: Optional[str] = None
    ) -> List[RoleMaterial]:
        """
        获取角色列表

        Args:
            name: 角色名称筛选
            tag: 标签筛选

        Returns:
            角色素材列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM roles WHERE 1=1"
        params = []

        if name:
            query += " AND role_name LIKE ?"
            params.append(f"%{name}%")

        if tag:
            query += " AND tags LIKE ?"
            params.append(f"%{tag}%")

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        roles = []
        for row in rows:
            roles.append(RoleMaterial(
                role_id=row[0],
                role_name=row[1],
                cover_url=row[2],
                use_count=row[3],
                remark=row[4],
                permission=row[5],
                opening=json.loads(row[6]) if row[6] else [],
                loop=json.loads(row[7]) if row[7] else [],
                scene=json.loads(row[8]) if row[8] else [],
                ending=json.loads(row[9]) if row[9] else [],
                face_analysis_config=json.loads(row[10]) if row[10] else {},
                audio_list=json.loads(row[11]) if row[11] else [],
                current_version=row[12],
                tags=json.loads(row[13]) if row[13] else [],
                created_at=row[14],
                updated_at=row[15]
            ))

        return roles

    def add_role(
        self,
        role_id: str,
        role_name: str,
        cover_url: Optional[str] = None,
        remark: Optional[str] = None,
        permission: str = "private",
        is_double_mode: bool = False,
        left_audio_id: Optional[str] = None,
        right_audio_id: Optional[str] = None
    ) -> RoleMaterial:
        """创建角色

        Args:
            role_id: 角色ID
            role_name: 角色名称
            cover_url: 封面URL
            remark: 备注
            permission: 权限
            is_double_mode: 是否双人模式
            left_audio_id: 左边说话人参考音频ID
            right_audio_id: 右边说话人参考音频ID

        Returns:
            创建的角色对象
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = time.strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO roles (
                role_id, role_name, cover_url, use_count, remark, permission,
                opening, loop, scene, ending, face_analysis_config, audio_list,
                is_double_mode, left_audio_id, right_audio_id,
                current_version, tags, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            role_id, role_name, cover_url, 0, remark, permission,
            "[]", "[]", "[]", "[]", "{}", "[]",
            1 if is_double_mode else 0, left_audio_id, right_audio_id,
            "1.0", "[]", now, now
        ))

        conn.commit()
        conn.close()

        logger.info(f"创建角色: {role_name} ({role_id}), 双人模式: {is_double_mode}")

        return RoleMaterial(
            role_id=role_id,
            role_name=role_name,
            cover_url=cover_url,
            use_count=0,
            remark=remark,
            permission=permission,
            opening=[],
            loop=[],
            scene=[],
            ending=[],
            face_analysis_config={},
            audio_list=[],
            is_double_mode=is_double_mode,
            left_audio_id=left_audio_id,
            right_audio_id=right_audio_id,
            current_version="1.0",
            tags=[],
            created_at=now,
            updated_at=now
        )

    def get_role_by_id(self, role_id: str) -> Optional[RoleMaterial]:
        """
        根据ID获取角色

        Args:
            role_id: 角色ID

        Returns:
            角色素材对象，不存在则返回 None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM roles WHERE role_id = ?", (role_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return RoleMaterial(
            role_id=row[0],
            role_name=row[1],
            cover_url=row[2],
            use_count=row[3],
            remark=row[4],
            permission=row[5],
            opening=json.loads(row[6]) if row[6] else [],
            loop=json.loads(row[7]) if row[7] else [],
            scene=json.loads(row[8]) if row[8] else [],
            ending=json.loads(row[9]) if row[9] else [],
            face_analysis_config=json.loads(row[10]) if row[10] else {},
            audio_list=json.loads(row[11]) if row[11] else [],
            is_double_mode=bool(row[12]) if len(row) > 12 else False,
            left_audio_id=row[13] if len(row) > 13 else None,
            right_audio_id=row[14] if len(row) > 14 else None,
            current_version=row[15] if len(row) > 15 else "1.0",
            tags=json.loads(row[16]) if len(row) > 16 and row[16] else [],
            created_at=row[17] if len(row) > 17 else "",
            updated_at=row[18] if len(row) > 18 else ""
        )

    def get_role_by_name(self, role_name: str) -> Optional[RoleMaterial]:
        """根据名称获取角色

        Args:
            role_name: 角色名称

        Returns:
            角色素材对象，不存在则返回 None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM roles WHERE role_name = ?", (role_name,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return RoleMaterial(
            role_id=row[0],
            role_name=row[1],
            cover_url=row[2],
            use_count=row[3],
            remark=row[4],
            permission=row[5],
            opening=json.loads(row[6]) if row[6] else [],
            loop=json.loads(row[7]) if row[7] else [],
            scene=json.loads(row[8]) if row[8] else [],
            ending=json.loads(row[9]) if row[9] else [],
            face_analysis_config=json.loads(row[10]) if row[10] else {},
            audio_list=json.loads(row[11]) if row[11] else [],
            is_double_mode=bool(row[12]) if len(row) > 12 else False,
            left_audio_id=row[13] if len(row) > 13 else None,
            right_audio_id=row[14] if len(row) > 14 else None,
            current_version=row[15] if len(row) > 15 else "1.0",
            tags=json.loads(row[16]) if len(row) > 16 and row[16] else [],
            created_at=row[17] if len(row) > 17 else "",
            updated_at=row[18] if len(row) > 18 else ""
        )

    def get_role_by_id_with_models(self, role_id: str) -> Optional[CoreRoleMaterial]:
        """
        根据ID获取角色（使用 VideoItem 和 AudioItem 数据模型）

        Args:
            role_id: 角色ID

        Returns:
            角色素材对象 (CoreRoleMaterial)，不存在则返回 None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM roles WHERE role_id = ?", (role_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        def parse_video_items(data: List[Dict]) -> List[VideoItem]:
            return [VideoItem(
                file_path=d.get("file_path", ""),
                emotion_tags=d.get("emotion_tags", []),
                scene_tags=d.get("scene_tags", []),
                duration=d.get("duration", 0.0)
            ) for d in data]

        def parse_audio_items(data: List[Dict]) -> List[AudioItem]:
            return [AudioItem(
                file_path=d.get("file_path", ""),
                emotion_tag=d.get("emotion_tag", ""),
                denoise_enabled=d.get("denoise_enabled", False)
            ) for d in data]

        face_config = json.loads(row[10]) if row[10] else {}
        face_analysis_config = FaceAnalysisConfig(
            head_angle_threshold=face_config.get("head_angle_threshold", 30.0),
            mouth_occlusion_threshold=face_config.get("mouth_occlusion_threshold", 0.5)
        )

        opening_data = json.loads(row[6]) if row[6] else []
        loop_data = json.loads(row[7]) if row[7] else []
        scene_data = json.loads(row[8]) if row[8] else []
        ending_data = json.loads(row[9]) if row[9] else []
        audio_data = json.loads(row[11]) if row[11] else []
        version_data = json.loads(row[13]) if row[13] else []

        version_history = [
            VersionInfo(
                version=v.get("version", "1.0"),
                create_time=datetime.fromisoformat(v.get("create_time", datetime.now().isoformat())),
                description=v.get("description")
            )
            for v in version_data
        ]

        return CoreRoleMaterial(
            role_id=row[0],
            role_name=row[1],
            cover_url=row[2],
            use_count=row[3],
            remark=row[4],
            permission=PermissionType(row[5]) if row[5] else PermissionType.PRIVATE,
            opening=parse_video_items(opening_data),
            loop=parse_video_items(loop_data),
            scene=parse_video_items(scene_data),
            ending=parse_video_items(ending_data),
            face_analysis_config=face_analysis_config,
            audio_list=parse_audio_items(audio_data),
            current_version=row[12] or "1.0",
            version_history=version_history,
            tags=json.loads(row[14]) if row[14] else [],
            created_at=datetime.fromisoformat(row[15]) if row[15] else datetime.now(),
            updated_at=datetime.fromisoformat(row[16]) if row[16] else datetime.now()
        )

    def update_role(
        self,
        role_id: str,
        role_name: Optional[str] = None,
        cover_url: Optional[str] = None,
        remark: Optional[str] = None,
        permission: Optional[str] = None,
        tags: Optional[List[str]] = None,
        face_analysis_config: Optional[Dict] = None,
        opening: Optional[List[Dict]] = None,
        loop: Optional[List[Dict]] = None,
        scene: Optional[List[Dict]] = None,
        ending: Optional[List[Dict]] = None,
        audio_list: Optional[List[Dict]] = None,
        is_double_mode: Optional[bool] = None,
        left_audio_id: Optional[str] = None,
        right_audio_id: Optional[str] = None
    ) -> bool:
        """
        更新角色信息

        Args:
            role_id: 角色ID
            role_name: 新名称
            cover_url: 新封面URL
            remark: 新备注
            permission: 新权限
            tags: 新标签
            face_analysis_config: 新面部分析配置
            opening: 新开场视频列表
            loop: 新循环视频列表
            scene: 新场景视频列表
            ending: 新结束视频列表
            audio_list: 新音频列表
            is_double_mode: 是否双人模式
            left_audio_id: 左边说话人参考音频ID
            right_audio_id: 右边说话人参考音频ID

        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        updates = []
        params = []

        if role_name is not None:
            updates.append("role_name = ?")
            params.append(role_name)

        if cover_url is not None:
            updates.append("cover_url = ?")
            params.append(cover_url)

        if remark is not None:
            updates.append("remark = ?")
            params.append(remark)

        if permission is not None:
            updates.append("permission = ?")
            params.append(permission)

        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))

        if face_analysis_config is not None:
            updates.append("face_analysis_config = ?")
            params.append(json.dumps(face_analysis_config))

        if opening is not None:
            updates.append("opening = ?")
            params.append(json.dumps(opening))

        if loop is not None:
            updates.append("loop = ?")
            params.append(json.dumps(loop))

        if scene is not None:
            updates.append("scene = ?")
            params.append(json.dumps(scene))

        if ending is not None:
            updates.append("ending = ?")
            params.append(json.dumps(ending))

        if audio_list is not None:
            updates.append("audio_list = ?")
            params.append(json.dumps(audio_list))

        if is_double_mode is not None:
            updates.append("is_double_mode = ?")
            params.append(1 if is_double_mode else 0)

        if left_audio_id is not None:
            updates.append("left_audio_id = ?")
            params.append(left_audio_id)

        if right_audio_id is not None:
            updates.append("right_audio_id = ?")
            params.append(right_audio_id)

        if not updates:
            conn.close()
            return False

        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())

        params.append(role_id)
        cursor.execute(f"UPDATE roles SET {', '.join(updates)} WHERE role_id = ?", params)

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        if success:
            logger.info(f"更新角色: {role_id}")
        return success

    def delete_role(self, role_id: str) -> bool:
        """
        删除角色素材

        Args:
            role_id: 角色ID

        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT cover_url FROM roles WHERE role_id = ?", (role_id,))
        row = cursor.fetchone()

        if row and row[0] and os.path.exists(row[0]):
            try:
                os.remove(row[0])
            except:
                pass

        cursor.execute("DELETE FROM roles WHERE role_id = ?", (role_id,))

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        if success:
            logger.info(f"删除角色: {role_id}")
        return success

    def increment_role_use_count(self, role_id: str) -> bool:
        """
        增加角色使用次数

        Args:
            role_id: 角色ID

        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE roles
            SET use_count = use_count + 1, updated_at = ?
            WHERE role_id = ?
        """, (datetime.now().isoformat(), role_id))

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        if success:
            logger.info(f"角色使用次数+1: {role_id}")
        return success

    def get_audios(self):
        """
        获取参考音频列表（从 tasks.db 的 t_material_reference_audio 表）

        Returns:
            参考音频列表（包含 name 和 file_path 属性的对象列表）
        """
        from dataclasses import dataclass

        @dataclass
        class AudioItem:
            """参考音频项"""
            name: str
            file_path: str

        # 连接 tasks.db 获取参考音频
        tasks_db_path = self.db_path.replace("materials.db", "tasks.db")
        conn = sqlite3.connect(tasks_db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT audio_name, file_path
                FROM t_material_reference_audio
                WHERE is_deleted = 0
                ORDER BY create_time DESC
            """)
            rows = cursor.fetchall()
            conn.close()

            return [AudioItem(name=row[0], file_path=row[1]) for row in rows]
        except sqlite3.OperationalError:
            # 表不存在
            conn.close()
            return []
        except Exception as e:
            logger.warning(f"获取参考音频失败: {e}")
            conn.close()
            return []

    def get_emotion_tags(self) -> List[GlobalTag]:
        """获取所有情绪标签"""
        return self._get_tags_by_type("emotion")

    def get_scene_tags(self) -> List[GlobalTag]:
        """获取所有场景标签"""
        return self._get_tags_by_type("scene")

    def _get_tags_by_type(self, tag_type: str) -> List[GlobalTag]:
        """根据类型获取标签"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM tags WHERE tag_type = ? ORDER BY sort",
            (tag_type,)
        )
        rows = cursor.fetchall()
        conn.close()

        tags = []
        for row in rows:
            tags.append(GlobalTag(
                tag_id=row[0],
                tag_name=row[1],
                tag_type=row[2],
                sort=row[3],
                created_at=row[4],
                updated_at=row[5]
            ))

        return tags

    def get_global_tags(
        self,
        tag_type: Optional[str] = None
    ) -> List[CoreGlobalTag]:
        """
        获取全局标签（按类型：emotion/scene）

        Args:
            tag_type: 标签类型筛选 (emotion/scene)，不传则返回全部

        Returns:
            全局标签列表 (使用 core.models.material)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if tag_type:
            cursor.execute(
                "SELECT * FROM tags WHERE tag_type = ? ORDER BY sort",
                (tag_type,)
            )
        else:
            cursor.execute("SELECT * FROM tags ORDER BY sort")

        rows = cursor.fetchall()
        conn.close()

        tags = []
        for row in rows:
            tags.append(CoreGlobalTag(
                tag_id=row[0],
                tag_name=row[1],
                tag_type=TagType(row[2]) if row[2] else TagType.EMOTION,
                sort=row[3],
                created_at=datetime.fromisoformat(row[4]) if row[4] else datetime.now(),
                updated_at=datetime.fromisoformat(row[5]) if row[5] else datetime.now()
            ))

        return tags

    def add_global_tag(
        self,
        tag_name: str,
        tag_type: str,
        sort: int = 0
    ) -> CoreGlobalTag:
        """
        添加标签

        Args:
            tag_name: 标签名称
            tag_type: 标签类型 (emotion/scene)
            sort: 排序

        Returns:
            标签对象 (使用 core.models.material)
        """
        tag_id = f"tag_{uuid.uuid4().hex[:8]}"
        now = datetime.now()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tags (tag_id, tag_name, tag_type, sort, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tag_id, tag_name, tag_type, sort, now.isoformat(), now.isoformat()))

        conn.commit()
        conn.close()

        tag = CoreGlobalTag(
            tag_id=tag_id,
            tag_name=tag_name,
            tag_type=TagType(tag_type) if tag_type else TagType.EMOTION,
            sort=sort,
            created_at=now,
            updated_at=now
        )

        logger.info(f"添加标签: {tag_name} ({tag_type})")
        return tag

    def delete_global_tag(self, tag_id: str) -> bool:
        """
        删除标签

        Args:
            tag_id: 标签ID

        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM tags WHERE tag_id = ?", (tag_id,))

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        if success:
            logger.info(f"删除标签: {tag_id}")
        return success

    def create_tag(
        self,
        tag_name: str,
        tag_type: str,
        sort: int = 0
    ) -> GlobalTag:
        """
        创建标签（兼容旧接口）

        Args:
            tag_name: 标签名称
            tag_type: 标签类型 (emotion/scene)
            sort: 排序

        Returns:
            标签对象
        """
        tag_id = f"tag_{hashlib.md5(tag_name.encode()).hexdigest()[:8]}"
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tags (tag_id, tag_name, tag_type, sort, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tag_id, tag_name, tag_type, sort, now, now))

        conn.commit()
        conn.close()

        tag = GlobalTag(
            tag_id=tag_id,
            tag_name=tag_name,
            tag_type=tag_type,
            sort=sort,
            created_at=now,
            updated_at=now
        )

        logger.info(f"创建标签: {tag_name} ({tag_type})")
        return tag

    def update_tag(
        self,
        tag_id: str,
        tag_name: Optional[str] = None,
        sort: Optional[int] = None
    ) -> bool:
        """
        更新标签

        Args:
            tag_id: 标签ID
            tag_name: 新名称
            sort: 新排序

        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        updates = []
        params = []

        if tag_name is not None:
            updates.append("tag_name = ?")
            params.append(tag_name)

        if sort is not None:
            updates.append("sort = ?")
            params.append(sort)

        if not updates:
            conn.close()
            return False

        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())

        params.append(tag_id)
        cursor.execute(f"UPDATE tags SET {', '.join(updates)} WHERE tag_id = ?", params)

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        if success:
            logger.info(f"更新标签: {tag_id}")
        return success

    def delete_tag(self, tag_id: str) -> bool:
        """
        删除标签（兼容旧接口）

        Args:
            tag_id: 标签ID

        Returns:
            是否成功
        """
        return self.delete_global_tag(tag_id)

    def face_analyze(self, video_path: str, sample_interval: int = 0) -> FaceAnalysisResult:
        """
        对视频进行面部分析 (使用 HeyGem 兼容的 SCRFD 模型)

        Args:
            video_path: 视频路径
            sample_interval: 采样间隔，0表示每帧分析

        Returns:
            面部位析结果
        """
        logger.info(f"开始面部分析 (HeyGem SCRFD): {video_path}")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        # 优先使用 HeyGem 的 SCRFD 检测器
        try:
            from business.preprocess.heygem_face_detector import HeyGemFaceDetector

            logger.info("使用 HeyGem SCRFD 面部检测器...")
            detector = HeyGemFaceDetector(use_gpu=False)

            if detector.detector is None:
                logger.warning("SCRFD 初始化失败，尝试使用 MediaPipe")
                raise Exception("SCRFD 不可用")

            logger.info("SCRFD 检测器初始化成功")

        except Exception as e:
            # 回退到 MediaPipe
            logger.warning(f"SCRFD 不可用，使用 MediaPipe: {e}")
            return self._face_analyze_mediapipe(video_path, sample_interval)

        # 打开视频
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        logger.info(f"视频信息: 总帧数={total_frames}, FPS={fps:.2f}, 分辨率={width}x{height}")

        valid_lip_frames = 0  # 嘴唇完整的帧
        missing_left_corner = 0   # 缺少左嘴角
        missing_right_corner = 0  # 缺少右嘴角
        missing_nose = 0          # 缺少鼻尖
        missing_both_corners = 0 # 两边都缺失
        no_face_frames = 0
        details: List[Dict[str, Any]] = []
        valid_indices: List[int] = []

        # 采样间隔
        if sample_interval is None or sample_interval <= 0:
            frame_step = 1
        else:
            frame_step = max(1, int(sample_interval))

        analyze_count = (total_frames + frame_step - 1) // frame_step
        logger.info(f"将分析 {analyze_count} 帧 (采样间隔={frame_step})")

        frame_idx = 0
        while frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()

            if not ret:
                break

            # 进度输出 (每 10%)
            progress_frame = (frame_idx // frame_step)
            if progress_frame % max(1, analyze_count // 10) == 0:
                percent = (progress_frame * 100) // max(1, analyze_count)
                logger.info(f"嘴唇检测进度: {progress_frame}/{analyze_count} ({percent}%)")

            try:
                # 使用 SCRFD 检测
                faces = detector.detect_faces(frame, thresh=0.5, max_num=1)

                detail = {
                    "frame": frame_idx,
                    "has_face": False,
                    "has_left_corner": False,
                    "has_right_corner": False,
                    "has_nose": False,
                    "valid_lip": False,
                }

                if faces:
                    face = faces[0]
                    detail["has_face"] = True

                    # SCRFD 5 点: [左眼, 右眼, 鼻尖, 左嘴角, 右嘴角]
                    landmarks = face.landmarks

                    left_corner = landmarks[3]   # 左嘴角
                    right_corner = landmarks[4]  # 右嘴角
                    nose = landmarks[2]          # 鼻尖

                    has_left = left_corner[0] > 0 and left_corner[1] > 0
                    has_right = right_corner[0] > 0 and right_corner[1] > 0
                    has_nose_tip = nose[0] > 0 and nose[1] > 0

                    detail["has_left_corner"] = has_left
                    detail["has_right_corner"] = has_right
                    detail["has_nose"] = has_nose_tip

                    # 统计
                    if not has_left:
                        missing_left_corner += 1
                    if not has_right:
                        missing_right_corner += 1
                    if not has_nose_tip:
                        missing_nose += 1
                    if not has_left and not has_right:
                        missing_both_corners += 1

                    # 嘴唇完整: 左右嘴角都可见 + 鼻尖可见
                    if has_left and has_right and has_nose_tip:
                        valid_lip_frames += 1
                        valid_indices.append(frame_idx)
                        detail["valid_lip"] = True
                else:
                    no_face_frames += 1

                details.append(detail)

            except Exception as e:
                logger.debug(f"帧 {frame_idx} 分析失败: {e}")

            frame_idx += frame_step

        cap.release()

        logger.info(f"嘴唇检测分析完成:")
        logger.info(f"  - 总帧数: {total_frames}")
        logger.info(f"  - 有效嘴唇帧: {valid_lip_frames}")
        logger.info(f"  - 无面部: {no_face_frames}")
        logger.info(f"  - 缺少左嘴角: {missing_left_corner}")
        logger.info(f"  - 缺少右嘴角: {missing_right_corner}")
        logger.info(f"  - 缺少鼻尖: {missing_nose}")

        # 生成结果
        reasons = []
        is_qualified = True

        if no_face_frames > total_frames * 0.3:
            is_qualified = False
            reasons.append(f"无面部帧数过多: {no_face_frames}/{total_frames}")

        if missing_both_corners > total_frames * 0.2:
            is_qualified = False
            reasons.append(f"大量帧无法检测到嘴唇: {missing_both_corners}")

        # 有效嘴唇帧比例
        valid_ratio = valid_lip_frames / total_frames if total_frames > 0 else 0
        if valid_ratio < 0.5:
            is_qualified = False
            reasons.append(f"有效嘴唇帧比例过低: {valid_ratio:.1%}")

        return FaceAnalysisResult(
            video_path=video_path,
            total_frames=total_frames,
            valid_frames=valid_lip_frames,
            mouth_occlusion_frames=missing_both_corners,
            side_head_frames=missing_left_corner + missing_right_corner,
            is_qualified=is_qualified,
            reasons=reasons,
            details=details,
            valid_frame_indices=valid_indices,
        )

    def _face_analyze_mediapipe(self, video_path: str, sample_interval: int = 0) -> FaceAnalysisResult:
        """
        回退方案: 使用 MediaPipe 进行面部分析
        """
        logger.info("使用 MediaPipe 进行面部分析...")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        # 初始化检测器
        detector = None
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            logger.info("加载 MediaPipe Face Landmarker 模型...")

            model_path = "models/face_landmarker.task"
            if not os.path.exists(model_path):
                model_path = "tools/stream/onnx_models/face_landmarker.task"
            if not os.path.exists(model_path):
                logger.warning(f"Face Landmarker 模型文件不存在，使用简化分析")
                return self._simple_face_analyze(video_path)

            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE,
                num_faces=1,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5
            )
            detector = vision.FaceLandmarker.create_from_options(options)
            logger.info("MediaPipe 模型加载成功")
        except Exception as e:
            logger.warning(f"MediaPipe 不可用，使用简化分析: {e}")
            return self._simple_face_analyze(video_path)

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"视频信息: 总帧数={total_frames}, FPS={fps:.2f}, 分辨率={width}x{height}")

        valid_frames = 0
        mouth_occlusion_frames = 0
        side_head_frames = 0
        no_face_frames = 0
        details: List[Dict[str, Any]] = []
        valid_indices: List[int] = []

        # sample_interval=0 表示全帧分析；否则按给定间隔采样
        if sample_interval is None or sample_interval <= 0:
            frame_step = 1
        else:
            frame_step = max(1, int(sample_interval))

        analyze_count = (total_frames + frame_step - 1) // frame_step
        logger.info(f"将分析 {analyze_count} 帧 (采样间隔={frame_step})")

        from core.models.material import FaceAnalysisConfig
        cfg = FaceAnalysisConfig()  # 使用默认阈值（包括 45°）

        frame_idx = 0
        while frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()

            if not ret:
                break

            # 每 10% 进度输出一次日志
            progress_percent = (frame_idx // frame_step) * 100 // analyze_count if analyze_count > 0 else 0
            if frame_idx % (frame_step * max(1, analyze_count // 10)) == 0:
                logger.info(f"面部分析进度: {frame_idx // max(1, frame_step)}/{analyze_count} ({progress_percent}%)")

            try:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                results = detector.detect(mp_image)

                detail = {
                    "frame": frame_idx,
                    "has_face": False,
                    "mouth_occluded": False,
                    "side_head": False,
                    "yaw_deg": 0.0,
                }

                if results.face_landmarks:
                    landmarks = results.face_landmarks[0]
                    detail["has_face"] = True

                    h, w = frame.shape[:2]

                    # 关键点索引：这里采用简化近似，使用鼻尖 + 左右眼角估计偏航角
                    nose_tip = landmarks[1]
                    left_eye_outer = landmarks[33]
                    right_eye_outer = landmarks[263]

                    # 近似人脸中心 x
                    face_center_x = (left_eye_outer.x + right_eye_outer.x) / 2.0
                    nose_x_norm = nose_tip.x
                    offset = (nose_x_norm - face_center_x) * w
                    face_width = abs(right_eye_outer.x - left_eye_outer.x) * w + 1e-6

                    # 粗略 yaw 角（度），不追求绝对准确，只用于 >45° 剔除
                    yaw_deg = float(np.degrees(np.arctan2(offset, face_width)))
                    detail["yaw_deg"] = yaw_deg

                    # 嘴部遮挡启发式：鼻尖到嘴中心的垂直距离异常（过小）视为遮挡
                    left_mouth = landmarks[13]
                    right_mouth = landmarks[14]
                    mouth_center_y = (left_mouth.y + right_mouth.y) / 2.0 * h
                    nose_y = nose_tip.y * h
                    vertical_dist = mouth_center_y - nose_y
                    expected_dist = h * 0.08  # 经验值：鼻尖到嘴垂直距离

                    mouth_occluded = vertical_dist < expected_dist * cfg.mouth_occlusion_threshold

                    if mouth_occluded:
                        mouth_occlusion_frames += 1
                        detail["mouth_occluded"] = True

                    # 侧头：基于 yaw 角绝对值
                    side_head = abs(yaw_deg) > cfg.head_angle_threshold
                    if side_head:
                        side_head_frames += 1
                        detail["side_head"] = True

                    # 合格帧：有人脸且未嘴部遮挡、未超过阈值
                    is_valid = detail["has_face"] and not mouth_occluded and not side_head
                    if is_valid:
                        valid_frames += 1
                        valid_indices.append(frame_idx)
                else:
                    no_face_frames += 1

                details.append(detail)

            except Exception as e:
                logger.debug(f"帧 {frame_idx} 分析失败: {e}")

            frame_idx += frame_step

        cap.release()
        detector.close()

        logger.info(f"面部分析完成:")
        logger.info(f"  - 总帧数: {total_frames}")
        logger.info(f"  - 有效帧: {valid_frames}")
        logger.info(f"  - 无面部: {no_face_frames}")
        logger.info(f"  - 嘴部遮挡: {mouth_occlusion_frames}")
        logger.info(f"  - 侧头: {side_head_frames}")

        reasons = []
        is_qualified = True

        if mouth_occlusion_frames > total_frames * 0.3:
            is_qualified = False
            reasons.append(f"嘴部遮挡帧数过多: {mouth_occlusion_frames}")

        if side_head_frames > total_frames * 0.3:
            is_qualified = False
            reasons.append(f"侧头帧数过多: {side_head_frames}")

        if valid_frames < total_frames * 0.5:
            is_qualified = False
            reasons.append(f"有效人脸帧数不足: {valid_frames}/{total_frames}")

        result = FaceAnalysisResult(
            video_path=video_path,
            total_frames=total_frames,
            valid_frames=valid_frames,
            mouth_occlusion_frames=mouth_occlusion_frames,
            side_head_frames=side_head_frames,
            is_qualified=is_qualified,
            reasons=reasons,
            details=details,
            valid_frame_indices=valid_indices,
        )

        logger.info(
            f"面部分析完成: 有效帧 {valid_frames}/{total_frames}, "
            f"嘴部遮挡: {mouth_occlusion_frames}, 侧头: {side_head_frames}, "
            f"是否合格: {is_qualified}"
        )

        return result

    def _simple_face_analyze(self, video_path: str) -> FaceAnalysisResult:
        """简化的人脸分析（使用 OpenCV Haar 级联）"""
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        valid_frames = 0
        details = []

        frame_idx = 0
        sample_interval = max(1, total_frames // 30)

        while frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()

            if not ret:
                break

            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.3, 5)

                detail = {
                    "frame": frame_idx,
                    "has_face": len(faces) > 0
                }

                if len(faces) > 0:
                    valid_frames += 1

                details.append(detail)

            except Exception as e:
                logger.debug(f"帧 {frame_idx} 分析失败: {e}")

            frame_idx += sample_interval

        cap.release()

        is_qualified = valid_frames >= total_frames * 0.5
        reasons = [] if is_qualified else [f"检测到人脸帧数不足: {valid_frames}/{total_frames}"]

        valid_indices = [d["frame"] for d in details if d.get("has_face")]

        return FaceAnalysisResult(
            video_path=video_path,
            total_frames=total_frames,
            valid_frames=valid_frames,
            mouth_occlusion_frames=0,
            side_head_frames=0,
            is_qualified=is_qualified,
            reasons=reasons,
            details=details,
            valid_frame_indices=valid_indices,
        )

    def _get_video_rotation(self, video_path: str) -> int:
        """
        获取视频的旋转角度

        Args:
            video_path: 视频文件路径

        Returns:
            旋转角度 (0, 90, 180, 270)
        """
        # 首先尝试用 ffprobe 获取旋转元数据
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=rotation',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            if result.returncode == 0 and result.stdout.strip():
                rotation = int(result.stdout.strip())
                # 标准化为 0, 90, 180, 270
                rotation = ((rotation % 360) + 360) % 360
                logger.info(f"ffprobe 检测到旋转角度: {rotation}°")
                return rotation
        except Exception as e:
            logger.debug(f"ffprobe 获取旋转失败: {e}")

        # 备用方案: 读取第一帧，根据尺寸判断是否需要旋转
        # 如果视频高度 > 宽度，认为是竖屏视频，需要 90 度旋转
        try:
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()

                # 简单判断: 如果高度明显大于宽度，认为是竖屏
                if height > width * 1.2:
                    logger.info(f"检测到竖屏视频: {width}x{height}, 需要旋转 90°")
                    return 90
                elif width > height * 1.2:
                    logger.info(f"检测到横屏视频: {width}x{width}")
                    return 0
        except Exception as e:
            logger.debug(f"OpenCV 检测方向失败: {e}")

        return 0

    def _rotate_frame(self, frame: np.ndarray, rotation: int) -> np.ndarray:
        """
        根据旋转角度旋转帧

        Args:
            frame: 输入帧
            rotation: 旋转角度 (0, 90, 180, 270)

        Returns:
            旋转后的帧
        """
        if rotation == 0 or frame is None:
            return frame

        if rotation == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif rotation == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        elif rotation == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        return frame

    def filter_video_by_face_analysis(
        self,
        video_path: str,
        valid_frame_indices: Optional[List[int]] = None,
        output_replace: bool = True
    ) -> str:
        """
        根据面部分析结果过滤视频，只保留合格帧并重新封装视频。

        使用 ffmpeg 滤镜来保持视频元数据（包括旋转信息）

        Args:
            video_path: 原始视频路径
            valid_frame_indices: 可选的合格帧索引列表；为空时会先调用 face_analyze(video_path, sample_interval=1)
            output_replace: 是否直接覆盖原视频

        Returns:
            最终视频路径（默认为原路径）
        """
        logger.info(f"开始视频过滤: {video_path}")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        # 检查是否存在同名的 MP4 文件（转换后的视频）
        video_dir = os.path.dirname(video_path)
        video_name = os.path.basename(video_path)
        name_without_ext = os.path.splitext(video_name)[0]
        mp4_path = os.path.join(video_dir, name_without_ext + ".mp4")

        has_mp4_converted = False
        if video_name.lower().endswith('.mp4') == False and os.path.exists(mp4_path):
            logger.info(f"检测到转换后的 MP4 文件: {mp4_path}")
            has_mp4_converted = True

        if valid_frame_indices is None:
            logger.info("未提供有效帧索引，先进行面部分析...")
            analysis = self.face_analyze(video_path, sample_interval=1)
            valid_frame_indices = analysis.valid_frame_indices

        total_valid = len(valid_frame_indices)
        logger.info(f"有效帧数量: {total_valid}")

        if not valid_frame_indices:
            logger.warning(f"视频 {video_path} 无合格帧，保持原视频不变")
            return video_path

        # 使用 ffmpeg 过滤，保持元数据
        temp_output = video_path + ".filtered.tmp.mp4"

        try:
            # 构建 ffmpeg select 滤镜表达式
            # 创建帧选择: "select='eq(n,0)+eq(n,10)+eq(n,25)+...'"
            indices = sorted(valid_frame_indices)
            select_expr = '+'.join([f'eq(n,{idx})' for idx in indices])
            select_filter = f"select='{select_expr}',setpts=N/FRAME_RATE/TB"

            logger.info(f"使用 ffmpeg 过滤，保留 {len(indices)} 帧")

            # 执行 ffmpeg 命令
            cmd = [
                'ffmpeg',
                '-y',  # 覆盖输出文件
                '-i', video_path,
                '-vf', select_filter,
                '-c:v', 'libx264',  # 使用 H.264 编码
                '-preset', 'fast',
                '-crf', '23',
                '-c:a', 'copy',  # 复制音频
                temp_output
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 分钟超时
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )

            if result.returncode != 0:
                logger.error(f"ffmpeg 过滤失败: {result.stderr}")
                raise RuntimeError(f"ffmpeg 过滤失败: {result.stderr[:200]}")

            logger.info(f"ffmpeg 过滤完成")

        except subprocess.TimeoutExpired:
            logger.error("ffmpeg 执行超时")
            raise
        except Exception as e:
            logger.error(f"ffmpeg 过滤出错: {e}")
            raise

        logger.info(f"视频过滤完成: 写入 {total_valid} 帧")

        final_path = video_path
        if output_replace:
            # 替换原始视频
            try:
                os.replace(temp_output, video_path)
                logger.info(f"已替换原视频: {video_path}")
            except OSError:
                # Windows 上若替换失败，尝试先删除再重命名
                try:
                    if os.path.exists(video_path):
                        os.remove(video_path)
                    os.replace(temp_output, video_path)
                    logger.info(f"已替换原视频 (删除后重命名): {video_path}")
                except Exception as e:
                    logger.error(f"替换视频失败: {e}")
                    final_path = temp_output

            # 如果存在转换后的 MP4 文件，也进行替换
            if has_mp4_converted and os.path.exists(mp4_path):
                try:
                    # 使用 ffmpeg 过滤 MP4 文件，保持元数据
                    temp_mp4_output = mp4_path + ".filtered.tmp.mp4"

                    indices = sorted(valid_frame_indices)
                    select_expr = '+'.join([f'eq(n,{idx})' for idx in indices])
                    select_filter = f"select='{select_expr}',setpts=N/FRAME_RATE/TB"

                    cmd = [
                        'ffmpeg',
                        '-y',
                        '-i', video_path,  # 使用刚过滤好的原视频
                        '-vf', select_filter,
                        '-c:v', 'libx264',
                        '-preset', 'fast',
                        '-crf', '23',
                        '-c:a', 'copy',
                        temp_mp4_output
                    ]

                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=300,
                        creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
                    )

                    if result.returncode != 0:
                        logger.error(f"ffmpeg 过滤 MP4 失败: {result.stderr}")
                    else:
                        # 替换 MP4 文件
                        try:
                            os.replace(temp_mp4_output, mp4_path)
                            logger.info(f"已替换转换后的 MP4: {mp4_path}")
                        except OSError:
                            try:
                                if os.path.exists(mp4_path):
                                    os.remove(mp4_path)
                                os.replace(temp_mp4_output, mp4_path)
                                logger.info(f"已替换转换后的 MP4 (删除后重命名): {mp4_path}")
                            except Exception as e:
                                logger.error(f"替换 MP4 失败: {e}")

                except Exception as e:
                    logger.error(f"处理转换后的 MP4 失败: {e}")
        else:
            final_path = temp_output
            logger.info(f"保留过滤后视频: {final_path}")

        return final_path


def create_material_library(db_path: str = "data/materials.db") -> MaterialLibrary:
    """创建素材库的便捷函数"""
    return MaterialLibrary(db_path=db_path)
