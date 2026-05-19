"""
素材数据模型
定义素材相关的实体类
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
import uuid


class PermissionType(Enum):
    """权限类型"""
    PUBLIC = "public"          # 公开
    PRIVATE = "private"         # 私有
    SHARED = "shared"           # 共享


class BgmCopyrightType(Enum):
    """BGM版权类型"""
    FREE = "free"              # 免费
    AUTHORIZED = "authorized"  # 已授权
    ORIGINAL = "original"       # 原创


class TagType(Enum):
    """标签类型"""
    EMOTION = "emotion"        # 情绪
    SCENE = "scene"            # 场景


@dataclass
class FaceAnalysisConfig:
    """面部分析配置"""
    head_angle_threshold: float = 45.0
    mouth_occlusion_threshold: float = 0.5


@dataclass
class AudioItem:
    """音频项"""
    file_path: str
    emotion_tag: str = ""
    denoise_enabled: bool = False


@dataclass
class VideoItem:
    """视频项"""
    file_path: str
    emotion_tags: List[str] = field(default_factory=list)
    scene_tags: List[str] = field(default_factory=list)
    duration: float = 0.0


@dataclass
class VersionInfo:
    """版本信息"""
    version: str
    create_time: datetime = field(default_factory=datetime.now)
    description: Optional[str] = None


@dataclass
class RoleMaterial:
    """角色素材"""
    role_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    role_name: str = ""
    cover_url: Optional[str] = None
    use_count: int = 0
    remark: Optional[str] = None
    permission: PermissionType = PermissionType.PRIVATE

    opening: List[VideoItem] = field(default_factory=list)
    loop: List[VideoItem] = field(default_factory=list)
    scene: List[VideoItem] = field(default_factory=list)
    ending: List[VideoItem] = field(default_factory=list)

    face_analysis_config: FaceAnalysisConfig = field(default_factory=FaceAnalysisConfig)

    audio_list: List[AudioItem] = field(default_factory=list)

    is_double_mode: bool = False
    left_audio_id: Optional[str] = None
    right_audio_id: Optional[str] = None

    current_version: str = "1.0"
    version_history: List[VersionInfo] = field(default_factory=list)

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "role_id": self.role_id,
            "role_name": self.role_name,
            "cover_url": self.cover_url,
            "use_count": self.use_count,
            "remark": self.remark,
            "permission": self.permission.value,
            "opening": [
                {
                    "file_path": v.file_path,
                    "emotion_tags": v.emotion_tags,
                    "duration": v.duration
                }
                for v in self.opening
            ],
            "loop": [
                {
                    "file_path": v.file_path,
                    "emotion_tags": v.emotion_tags,
                    "duration": v.duration
                }
                for v in self.loop
            ],
            "scene": [
                {
                    "file_path": v.file_path,
                    "emotion_tags": v.emotion_tags,
                    "duration": v.duration
                }
                for v in self.scene
            ],
            "ending": [
                {
                    "file_path": v.file_path,
                    "emotion_tags": v.emotion_tags,
                    "duration": v.duration
                }
                for v in self.ending
            ],
            "face_analysis_config": {
                "head_angle_threshold": self.face_analysis_config.head_angle_threshold,
                "mouth_occlusion_threshold": self.face_analysis_config.mouth_occlusion_threshold
            },
            "audio_list": [
                {
                    "file_path": a.file_path,
                    "emotion_tag": a.emotion_tag,
                    "denoise_enabled": a.denoise_enabled
                }
                for a in self.audio_list
            ],
            "is_double_mode": self.is_double_mode,
            "left_audio_id": self.left_audio_id,
            "right_audio_id": self.right_audio_id,
            "current_version": self.current_version,
            "version_history": [
                {
                    "version": v.version,
                    "create_time": v.create_time.isoformat(),
                    "description": v.description
                }
                for v in self.version_history
            ],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class BgmMaterial:
    """背景音乐素材"""
    bgm_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    bgm_name: str = ""
    duration: float = 0.0
    file_size: int = 0
    file_url: Optional[str] = None
    file_path: Optional[str] = None

    emotion_tags: List[str] = field(default_factory=list)
    scene_tags: List[str] = field(default_factory=list)

    copyright_type: BgmCopyrightType = BgmCopyrightType.FREE
    copyright_remark: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "bgm_id": self.bgm_id,
            "bgm_name": self.bgm_name,
            "duration": self.duration,
            "file_size": self.file_size,
            "file_url": self.file_url,
            "file_path": self.file_path,
            "emotion_tags": self.emotion_tags,
            "scene_tags": self.scene_tags,
            "copyright_type": self.copyright_type.value,
            "copyright_remark": self.copyright_remark,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class GlobalTag:
    """全局标签"""
    tag_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    tag_name: str = ""
    tag_type: TagType = TagType.EMOTION
    sort: int = 0

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "tag_id": self.tag_id,
            "tag_name": self.tag_name,
            "tag_type": self.tag_type.value,
            "sort": self.sort,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


def create_role_material(
    role_name: str,
    cover_url: Optional[str] = None,
    permission: PermissionType = PermissionType.PRIVATE
) -> RoleMaterial:
    """创建角色素材的便捷函数"""
    return RoleMaterial(
        role_name=role_name,
        cover_url=cover_url,
        permission=permission
    )


def create_bgm_material(
    bgm_name: str,
    duration: float,
    file_path: str,
    copyright_type: BgmCopyrightType = BgmCopyrightType.FREE
) -> BgmMaterial:
    """创建BGM素材的便捷函数"""
    return BgmMaterial(
        bgm_name=bgm_name,
        duration=duration,
        file_path=file_path,
        copyright_type=copyright_type
    )


def create_global_tag(
    tag_name: str,
    tag_type: TagType,
    sort: int = 0
) -> GlobalTag:
    """创建全局标签的便捷函数"""
    return GlobalTag(
        tag_name=tag_name,
        tag_type=tag_type,
        sort=sort
    )
