"""
标签组管理路由
CR-022: 标签组管理功能
"""

import json
import logging
from typing import Optional, List
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator

from api.services.database import get_database_service, DatabaseService
from api.services.emotion_sync import EmotionSyncService

logger = logging.getLogger("autoavantar-api.tags")

router = APIRouter()

EMOTION_YAML_PATH = Path(__file__).parent.parent.parent.parent / "index-tts-2" / "emotion_mapping.yaml"


class TagGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    type: str = Field(default="scene", pattern="^(scene|emotion)$")


class TagGroupUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    similar_tags: List[str] = Field(default_factory=list)


class TagUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    similar_tags: List[str] = Field(default_factory=list)


class EmotionTagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    vec1: float = Field(default=0.0, ge=0.0, le=1.0)
    vec2: float = Field(default=0.0, ge=0.0, le=1.0)
    vec3: float = Field(default=0.0, ge=0.0, le=1.0)
    vec4: float = Field(default=0.0, ge=0.0, le=1.0)
    vec5: float = Field(default=0.0, ge=0.0, le=1.0)
    vec6: float = Field(default=0.0, ge=0.0, le=1.0)
    vec7: float = Field(default=0.0, ge=0.0, le=1.0)
    vec8: float = Field(default=0.0, ge=0.0, le=1.0)
    speed: float = Field(default=1.0, ge=0.8, le=1.2)


class EmotionTagUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    vec1: float = Field(default=0.0, ge=0.0, le=1.0)
    vec2: float = Field(default=0.0, ge=0.0, le=1.0)
    vec3: float = Field(default=0.0, ge=0.0, le=1.0)
    vec4: float = Field(default=0.0, ge=0.0, le=1.0)
    vec5: float = Field(default=0.0, ge=0.0, le=1.0)
    vec6: float = Field(default=0.0, ge=0.0, le=1.0)
    vec7: float = Field(default=0.0, ge=0.0, le=1.0)
    vec8: float = Field(default=0.0, ge=0.0, le=1.0)
    speed: float = Field(default=1.0, ge=0.8, le=1.2)


async def get_db() -> DatabaseService:
    try:
        db = get_database_service()
        return db
    except RuntimeError:
        raise HTTPException(status_code=500, detail="数据库服务不可用")


def get_emotion_sync_service() -> EmotionSyncService:
    return EmotionSyncService(str(EMOTION_YAML_PATH))


@router.get("/groups")
async def get_tag_groups(db: DatabaseService = Depends(get_db)):
    """获取所有标签组列表"""
    async with db.get_connection() as conn:
        cursor = await conn.cursor()
        await cursor.execute(
            "SELECT id, name, type, is_default, created_at, updated_at FROM tag_groups ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        
        groups = []
        for row in rows:
            groups.append({
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "is_default": row["is_default"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            })
        
        return {"groups": groups}


@router.post("/groups")
async def create_tag_group(
    data: TagGroupCreate,
    db: DatabaseService = Depends(get_db)
):
    """创建新标签组"""
    async with db.get_connection() as conn:
        cursor = await conn.cursor()
        
        await cursor.execute(
            "SELECT id FROM tag_groups WHERE name = ?",
            (data.name,)
        )
        existing = await cursor.fetchone()
        
        if existing:
            raise HTTPException(status_code=400, detail=f"标签组名称 '{data.name}' 已存在")
        
        now = datetime.now().isoformat()
        await cursor.execute(
            "INSERT INTO tag_groups (name, type, is_default, created_at, updated_at) VALUES (?, ?, 0, ?, ?)",
            (data.name, data.type, now, now)
        )
        await conn.commit()
        
        await cursor.execute("SELECT last_insert_rowid()")
        result = await cursor.fetchone()
        group_id = result[0]
        
        # 刷新标签匹配器缓存
        from business.video.tag_matcher import reload_tag_matcher
        reload_tag_matcher()
        
        return {
            "id": group_id,
            "name": data.name,
            "type": data.type,
            "is_default": 0,
            "created_at": now,
            "updated_at": now
        }


@router.put("/groups/{group_id}")
async def update_tag_group(
    group_id: int,
    data: TagGroupUpdate,
    db: DatabaseService = Depends(get_db)
):
    """更新标签组名称"""
    async with db.get_connection() as conn:
        cursor = await conn.cursor()
        
        await cursor.execute(
            "SELECT id FROM tag_groups WHERE id = ?",
            (group_id,)
        )
        existing = await cursor.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="标签组不存在")
        
        await cursor.execute(
            "SELECT id FROM tag_groups WHERE name = ? AND id != ?",
            (data.name, group_id)
        )
        duplicate = await cursor.fetchone()
        
        if duplicate:
            raise HTTPException(status_code=400, detail=f"标签组名称 '{data.name}' 已存在")
        
        now = datetime.now().isoformat()
        await cursor.execute(
            "UPDATE tag_groups SET name = ?, updated_at = ? WHERE id = ?",
            (data.name, now, group_id)
        )
        await conn.commit()
        
        await cursor.execute(
            "SELECT id, name, type, is_default, created_at, updated_at FROM tag_groups WHERE id = ?",
            (group_id,)
        )
        row = await cursor.fetchone()
        
        # 刷新标签匹配器缓存
        from business.video.tag_matcher import reload_tag_matcher
        reload_tag_matcher()
        
        return {
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "is_default": row["is_default"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }


@router.delete("/groups/{group_id}")
async def delete_tag_group(
    group_id: int,
    db: DatabaseService = Depends(get_db)
):
    """删除标签组（级联删除标签）"""
    async with db.get_connection() as conn:
        cursor = await conn.cursor()
        
        await cursor.execute(
            "SELECT id, name FROM tag_groups WHERE id = ?",
            (group_id,)
        )
        existing = await cursor.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="标签组不存在")
        
        await cursor.execute(
            "DELETE FROM tag_groups WHERE id = ?",
            (group_id,)
        )
        await conn.commit()
        
        # 刷新标签匹配器缓存
        from business.video.tag_matcher import reload_tag_matcher
        reload_tag_matcher()
        
        return {"id": group_id, "name": existing["name"], "deleted": True}


@router.get("/groups/{group_id}/tags")
async def get_tags_by_group(
    group_id: int,
    db: DatabaseService = Depends(get_db)
):
    """获取标签组内的所有标签"""
    async with db.get_connection() as conn:
        cursor = await conn.cursor()
        
        await cursor.execute(
            "SELECT id FROM tag_groups WHERE id = ?",
            (group_id,)
        )
        group = await cursor.fetchone()
        
        if not group:
            raise HTTPException(status_code=404, detail="标签组不存在")
        
        await cursor.execute(
            "SELECT id, name, similar_tags, created_at, updated_at FROM tags WHERE group_id = ? ORDER BY created_at ASC",
            (group_id,)
        )
        rows = await cursor.fetchall()
        
        tags = []
        for row in rows:
            similar_tags = json.loads(row["similar_tags"]) if row["similar_tags"] else []
            tags.append({
                "id": row["id"],
                "group_id": group_id,
                "name": row["name"],
                "similar_tags": similar_tags,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            })
        
        return {"tags": tags}


@router.post("/groups/{group_id}/tags")
async def add_tag_to_group(
    group_id: int,
    data: TagCreate,
    db: DatabaseService = Depends(get_db)
):
    """添加标签到标签组"""
    async with db.get_connection() as conn:
        cursor = await conn.cursor()
        
        await cursor.execute(
            "SELECT id FROM tag_groups WHERE id = ?",
            (group_id,)
        )
        group = await cursor.fetchone()
        
        if not group:
            raise HTTPException(status_code=404, detail="标签组不存在")
        
        await cursor.execute(
            "SELECT id FROM tags WHERE group_id = ? AND name = ?",
            (group_id, data.name)
        )
        existing = await cursor.fetchone()
        
        if existing:
            raise HTTPException(status_code=400, detail=f"标签 '{data.name}' 已存在于该标签组")
        
        now = datetime.now().isoformat()
        similar_json = json.dumps(data.similar_tags, ensure_ascii=False)
        
        await cursor.execute(
            "INSERT INTO tags (group_id, name, similar_tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (group_id, data.name, similar_json, now, now)
        )
        await conn.commit()
        
        await cursor.execute("SELECT last_insert_rowid()")
        result = await cursor.fetchone()
        tag_id = result[0]
        
        # 刷新标签匹配器缓存
        from business.video.tag_matcher import reload_tag_matcher
        reload_tag_matcher()
        
        return {
            "id": tag_id,
            "group_id": group_id,
            "name": data.name,
            "similar_tags": data.similar_tags,
            "created_at": now,
            "updated_at": now
        }


@router.put("/{tag_id}")
async def update_tag(
    tag_id: int,
    data: TagUpdate,
    db: DatabaseService = Depends(get_db)
):
    """更新标签"""
    async with db.get_connection() as conn:
        cursor = await conn.cursor()
        
        await cursor.execute(
            "SELECT id, group_id FROM tags WHERE id = ?",
            (tag_id,)
        )
        existing = await cursor.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="标签不存在")
        
        group_id = existing["group_id"]
        
        await cursor.execute(
            "SELECT id FROM tags WHERE group_id = ? AND name = ? AND id != ?",
            (group_id, data.name, tag_id)
        )
        duplicate = await cursor.fetchone()
        
        if duplicate:
            raise HTTPException(status_code=400, detail=f"标签名称 '{data.name}' 已存在于该标签组")
        
        now = datetime.now().isoformat()
        similar_json = json.dumps(data.similar_tags, ensure_ascii=False)
        
        await cursor.execute(
            "UPDATE tags SET name = ?, similar_tags = ?, updated_at = ? WHERE id = ?",
            (data.name, similar_json, now, tag_id)
        )
        await conn.commit()
        
        # 刷新标签匹配器缓存
        from business.video.tag_matcher import reload_tag_matcher
        reload_tag_matcher()
        
        await cursor.execute(
            "SELECT id, group_id, name, similar_tags, created_at, updated_at FROM tags WHERE id = ?",
            (tag_id,)
        )
        row = await cursor.fetchone()
        
        similar_tags = json.loads(row["similar_tags"]) if row["similar_tags"] else []
        
        return {
            "id": row["id"],
            "group_id": row["group_id"],
            "name": row["name"],
            "similar_tags": similar_tags,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }


@router.delete("/{tag_id}")
async def delete_tag(
    tag_id: int,
    db: DatabaseService = Depends(get_db)
):
    """删除标签"""
    async with db.get_connection() as conn:
        cursor = await conn.cursor()
        
        await cursor.execute(
            "SELECT id, name FROM tags WHERE id = ?",
            (tag_id,)
        )
        existing = await cursor.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="标签不存在")
        
        await cursor.execute(
            "DELETE FROM tags WHERE id = ?",
            (tag_id,)
        )
        await conn.commit()
        
        # 刷新标签匹配器缓存
        from business.video.tag_matcher import reload_tag_matcher
        reload_tag_matcher()
        
        return {"id": tag_id, "name": existing["name"], "deleted": True}


@router.get("/emotions")
async def get_emotion_tags(db: DatabaseService = Depends(get_db)):
    """获取所有情绪标签"""
    async with db.get_connection() as conn:
        cursor = await conn.cursor()
        
        await cursor.execute(
            "SELECT id, name, vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8, speed, created_at, updated_at FROM tags WHERE group_id IS NULL ORDER BY created_at ASC"
        )
        rows = await cursor.fetchall()
        
        emotions = []
        for row in rows:
            emotions.append({
                "id": row["id"],
                "name": row["name"],
                "vec1": row["vec1"],
                "vec2": row["vec2"],
                "vec3": row["vec3"],
                "vec4": row["vec4"],
                "vec5": row["vec5"],
                "vec6": row["vec6"],
                "vec7": row["vec7"],
                "vec8": row["vec8"],
                "speed": row["speed"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            })
        
        return {"emotions": emotions}


@router.post("/emotions")
async def create_emotion_tag(
    data: EmotionTagCreate,
    db: DatabaseService = Depends(get_db)
):
    """创建情绪标签"""
    async with db.get_connection() as conn:
        cursor = await conn.cursor()
        
        await cursor.execute(
            "SELECT id FROM tags WHERE name = ? AND group_id IS NULL",
            (data.name,)
        )
        existing = await cursor.fetchone()
        
        if existing:
            raise HTTPException(status_code=400, detail=f"情绪标签 '{data.name}' 已存在")
        
        now = datetime.now().isoformat()
        try:
            await cursor.execute(
                "INSERT INTO tags (group_id, name, vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8, speed, created_at, updated_at) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (data.name, data.vec1, data.vec2, data.vec3, data.vec4, data.vec5, data.vec6, data.vec7, data.vec8, data.speed, now, now)
            )
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                raise HTTPException(status_code=400, detail=f"标签名称 '{data.name}' 与场景标签冲突，请使用其他名称")
            raise
        await conn.commit()
        
        await cursor.execute("SELECT last_insert_rowid()")
        result = await cursor.fetchone()
        tag_id = result[0]
        
        return {
            "id": tag_id,
            "name": data.name,
            "vec1": data.vec1,
            "vec2": data.vec2,
            "vec3": data.vec3,
            "vec4": data.vec4,
            "vec5": data.vec5,
            "vec6": data.vec6,
            "vec7": data.vec7,
            "vec8": data.vec8,
            "speed": data.speed,
            "created_at": now,
            "updated_at": now
        }


@router.put("/emotions/{tag_id}")
async def update_emotion_tag(
    tag_id: int,
    data: EmotionTagUpdate,
    db: DatabaseService = Depends(get_db)
):
    """更新情绪标签"""
    async with db.get_connection() as conn:
        cursor = await conn.cursor()
        
        await cursor.execute(
            "SELECT id FROM tags WHERE id = ? AND group_id IS NULL",
            (tag_id,)
        )
        existing = await cursor.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="情绪标签不存在")
        
        await cursor.execute(
            "SELECT id FROM tags WHERE name = ? AND group_id IS NULL AND id != ?",
            (data.name, tag_id)
        )
        duplicate = await cursor.fetchone()
        
        if duplicate:
            raise HTTPException(status_code=400, detail=f"情绪标签名称 '{data.name}' 已存在")
        
        now = datetime.now().isoformat()
        await cursor.execute(
            "UPDATE tags SET name = ?, vec1 = ?, vec2 = ?, vec3 = ?, vec4 = ?, vec5 = ?, vec6 = ?, vec7 = ?, vec8 = ?, speed = ?, updated_at = ? WHERE id = ?",
            (data.name, data.vec1, data.vec2, data.vec3, data.vec4, data.vec5, data.vec6, data.vec7, data.vec8, data.speed, now, tag_id)
        )
        await conn.commit()
        
        await cursor.execute(
            "SELECT id, name, vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8, speed, created_at, updated_at FROM tags WHERE id = ?",
            (tag_id,)
        )
        row = await cursor.fetchone()
        
        return {
            "id": row["id"],
            "name": row["name"],
            "vec1": row["vec1"],
            "vec2": row["vec2"],
            "vec3": row["vec3"],
            "vec4": row["vec4"],
            "vec5": row["vec5"],
            "vec6": row["vec6"],
            "vec7": row["vec7"],
            "vec8": row["vec8"],
            "speed": row["speed"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }


@router.delete("/emotions/{tag_id}")
async def delete_emotion_tag(
    tag_id: int,
    db: DatabaseService = Depends(get_db)
):
    """删除情绪标签"""
    async with db.get_connection() as conn:
        cursor = await conn.cursor()
        
        await cursor.execute(
            "SELECT id, name FROM tags WHERE id = ? AND group_id IS NULL",
            (tag_id,)
        )
        existing = await cursor.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="情绪标签不存在")
        
        await cursor.execute(
            "DELETE FROM tags WHERE id = ?",
            (tag_id,)
        )
        await conn.commit()
        
        return {"id": tag_id, "name": existing["name"], "deleted": True}


@router.post("/emotions/sync")
async def sync_emotions_to_yaml(
    db: DatabaseService = Depends(get_db),
    sync_service: EmotionSyncService = Depends(get_emotion_sync_service)
):
    """同步情绪标签到 YAML 文件"""
    async with db.get_connection() as conn:
        cursor = await conn.cursor()
        
        await cursor.execute(
            "SELECT name, vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8, speed FROM tags WHERE group_id IS NULL"
        )
        rows = await cursor.fetchall()
        
        emotion_tags = []
        for row in rows:
            emotion_tags.append({
                "name": row["name"],
                "vec1": row["vec1"],
                "vec2": row["vec2"],
                "vec3": row["vec3"],
                "vec4": row["vec4"],
                "vec5": row["vec5"],
                "vec6": row["vec6"],
                "vec7": row["vec7"],
                "vec8": row["vec8"],
                "speed": row["speed"]
            })
        
        success = await sync_service.sync_to_yaml(emotion_tags)
        
        if not success:
            raise HTTPException(status_code=500, detail="同步到 YAML 文件失败")
        
        return {"synced": True, "count": len(emotion_tags)}