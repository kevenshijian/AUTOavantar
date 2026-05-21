"""
智能裁剪路由
提供视频智能分割、片段管理、合成输出等功能
"""

import logging
import os
import uuid
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.schemas import ApiResponse
from api.services.smart_cut_service import get_smart_cut_service

logger = logging.getLogger("autoavantar-api.smart_cut")

router = APIRouter()


# ==================== 数据模型 ====================

class SmartCutTaskCreate(BaseModel):
    """创建智能裁剪任务请求"""
    video_path: str
    video_name: str = ""
    duration: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    total_frames: int = 0
    config: Dict[str, Any] = Field(default_factory=lambda: {
        "min_segment_duration": 10,
        "enable_brightness": False,
        "enable_pose": False,
        "enable_motion": False,
        "enable_silence": False
    })


class SmartCutMergeRequest(BaseModel):
    """合成视频请求"""
    segments: List[Dict[str, str]]
    output_name: str = ""
    resolution: str = "1080p"
    fps: int = 30
    transition: str = "none"
    bgm_path: Optional[str] = None


class SmartCutExtractAudioRequest(BaseModel):
    """提取音频请求"""
    segment_path: str
    name: str = ""


# ==================== 辅助函数 ====================

def generate_task_id() -> str:
    """生成任务ID"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"sc_{timestamp}_{short_uuid}"


# ==================== API 路由 ====================

@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "smart_cut"}


@router.post("/upload", response_model=ApiResponse)
async def upload_video(file: UploadFile = File(...)):
    """
    上传视频文件

    接收视频文件，校验格式，提取视频信息，返回预览数据
    """
    service = get_smart_cut_service()

    try:
        # 读取文件内容
        file_content = await file.read()

        # 调用服务处理上传
        result = await service.upload_video(
            file_content=file_content,
            filename=file.filename or "未命名视频.mp4",
            content_type=file.content_type
        )

        logger.info(f"视频上传成功: {result['video_id']} - {result['video_name']}")

        return ApiResponse(
            code=200,
            message="上传成功",
            data=result
        )

    except ValueError as e:
        logger.warning(f"视频上传失败: {e}")
        return ApiResponse(
            code=400,
            message=str(e)
        )
    except Exception as e:
        logger.error(f"视频上传异常: {e}")
        return ApiResponse(
            code=500,
            message=f"上传失败：{str(e)}"
        )


@router.post("/tasks", response_model=ApiResponse)
async def create_task(
    request: SmartCutTaskCreate,
    background_tasks: BackgroundTasks = None
):
    """
    创建智能裁剪任务

    创建任务并启动异步识别流程
    """
    service = get_smart_cut_service()

    try:
        # 1. 校验参数
        min_duration = request.config.get("min_segment_duration", 10)
        if min_duration < 3 or min_duration > 240:
            return ApiResponse(
                code=400,
                message="最短片段时长必须在 3-240 秒之间"
            )

        # 2. 检查视频文件是否存在
        video_path = service.base_dir / request.video_path
        if not video_path.exists():
            return ApiResponse(
                code=400,
                message="视频文件不存在"
            )

        # 3. 检查是否有进行中的任务使用同一视频
        from api.services.database import get_database_service
        db = get_database_service()

        existing_task = await db.smart_cut_task_get_by_video_path(request.video_path)
        if existing_task:
            logger.warning(f"视频已有进行中的任务: {request.video_path} -> {existing_task['task_id']}")
            return ApiResponse(
                code=400,
                message="当前视频已有裁剪任务正在进行中"
            )

        # 4. 生成任务ID
        task_id = generate_task_id()

        # 5. 创建任务记录
        await db.smart_cut_task_create(
            task_id=task_id,
            video_path=request.video_path,
            video_name=request.video_name,
            video_duration=request.duration,
            video_fps=request.fps,
            video_width=request.width,
            video_height=request.height,
            total_frames=request.total_frames,
            config=request.config
        )

        # 6. 启动异步识别任务
        background_tasks.add_task(
            run_smart_cut_task,
            task_id=task_id,
            video_path=request.video_path,
            config=request.config
        )

        logger.info(f"创建智能裁剪任务: {task_id}")

        return ApiResponse(
            code=200,
            message="任务创建成功",
            data={
                "task_id": task_id
            }
        )

    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        return ApiResponse(
            code=500,
            message=f"创建任务失败：{str(e)}"
        )


async def run_smart_cut_task(task_id: str, video_path: str, config: Dict[str, Any]):
    """
    后台执行智能裁剪任务

    Args:
        task_id: 任务ID
        video_path: 视频路径
        config: 配置参数
    """
    service = get_smart_cut_service()

    try:
        await service.execute_smart_cut(
            task_id=task_id,
            video_path=video_path,
            config=config
        )
    except Exception as e:
        logger.error(f"智能裁剪任务执行失败: {task_id}, {e}")


@router.get("/tasks/{task_id}", response_model=ApiResponse)
async def get_task(task_id: str):
    """
    查询任务状态

    返回任务状态、进度、当前阶段等信息
    """
    service = get_smart_cut_service()

    try:
        task_status = await service.get_task_status(task_id)

        if not task_status:
            return ApiResponse(
                code=404,
                message="任务不存在"
            )

        return ApiResponse(
            code=200,
            message="success",
            data=task_status
        )

    except Exception as e:
        logger.error(f"查询任务状态失败: {e}")
        return ApiResponse(
            code=500,
            message=f"查询失败：{str(e)}"
        )


@router.get("/tasks/{task_id}/segments", response_model=ApiResponse)
async def get_segments(task_id: str):
    """
    获取片段列表

    返回裁剪完成后的所有片段信息
    """
    service = get_smart_cut_service()

    try:
        segments_info = await service.get_segments(task_id)

        if not segments_info:
            return ApiResponse(
                code=404,
                message="任务不存在"
            )

        return ApiResponse(
            code=200,
            message="success",
            data=segments_info
        )

    except Exception as e:
        logger.error(f"获取片段列表失败: {e}")
        return ApiResponse(
            code=500,
            message=f"获取失败：{str(e)}"
        )


@router.post("/extract-audio", response_model=ApiResponse)
async def extract_audio(request: SmartCutExtractAudioRequest):
    """
    提取音频

    从指定片段中提取音频文件
    """
    service = get_smart_cut_service()

    try:
        # 检查片段文件是否存在
        segment_path = service.base_dir / request.segment_path
        if not segment_path.exists():
            return ApiResponse(
                code=400,
                message="片段文件不存在"
            )

        # 调用服务提取音频
        result = await service.extract_audio_from_segment(
            segment_path=str(segment_path),
            name=request.name
        )

        if result:
            return ApiResponse(
                code=200,
                message="音频提取成功",
                data=result
            )
        else:
            return ApiResponse(
                code=500,
                message="音频提取失败"
            )

    except Exception as e:
        logger.error(f"提取音频失败: {e}")
        return ApiResponse(
            code=500,
            message=f"提取音频失败：{str(e)}"
        )


@router.post("/merge", response_model=ApiResponse)
async def merge_videos(
    request: SmartCutMergeRequest,
    background_tasks: BackgroundTasks = None
):
    """
    合成视频

    将多个片段合成为新视频
    """
    service = get_smart_cut_service()

    try:
        # 校验片段列表
        if not request.segments or len(request.segments) == 0:
            return ApiResponse(
                code=400,
                message="请至少选择一个片段"
            )

        # 调用服务合成视频
        result = await service.merge_segments(
            segments=request.segments,
            output_name=request.output_name,
            resolution=request.resolution,
            fps=request.fps,
            transition=request.transition,
            bgm_path=request.bgm_path
        )

        if result:
            return ApiResponse(
                code=200,
                message="视频合成成功",
                data=result
            )
        else:
            return ApiResponse(
                code=500,
                message="视频合成失败"
            )

    except Exception as e:
        logger.error(f"合成视频失败: {e}")
        return ApiResponse(
            code=500,
            message=f"合成视频失败：{str(e)}"
        )


@router.get("/history", response_model=ApiResponse)
async def get_history():
    """
    获取历史记录列表

    返回所有已完成的裁剪任务，按时间倒序排列
    """
    service = get_smart_cut_service()

    try:
        history = await service.get_history()
        return ApiResponse(
            code=200,
            message="success",
            data={"history": history}
        )

    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        return ApiResponse(
            code=500,
            message=f"获取历史记录失败：{str(e)}"
        )


@router.delete("/tasks/{task_id}", response_model=ApiResponse)
async def delete_task(task_id: str):
    """
    删除任务

    删除任务记录及相关临时文件
    """
    service = get_smart_cut_service()

    try:
        success = await service.delete_task(task_id)

        if not success:
            return ApiResponse(
                code=404,
                message="任务不存在"
            )

        return ApiResponse(
            code=200,
            message="任务删除成功"
        )

    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        return ApiResponse(
            code=500,
            message=f"删除失败：{str(e)}"
        )


@router.post("/save-to-material", response_model=ApiResponse)
async def save_to_material(request: dict):
    """
    保存片段到素材库

    将选中的片段视频复制到 data 目录，并创建素材库记录
    """
    service = get_smart_cut_service()

    try:
        # 解析请求数据
        segments = request.get("segments", [])
        material_type = request.get("type", "character")  # character, scene, reference_audio, bgm

        if not segments:
            return ApiResponse(
                code=400,
                message="请至少选择一个片段"
            )

        # 验证片段路径
        for segment in segments:
            segment_path = segment.get("video_path", "")
            if not segment_path:
                continue

            # 检查片段文件是否存在
            full_path = service.base_dir / segment_path
            if not full_path.exists():
                return ApiResponse(
                    code=400,
                    message=f"片段文件不存在: {segment_path}"
                )

        # 根据类型创建素材
        if material_type == "character":
            result = await _save_as_character(segments, service)
        elif material_type == "scene":
            result = await _save_as_scene(segments, service)
        else:
            return ApiResponse(
                code=400,
                message=f"不支持的素材类型: {material_type}，仅支持 character 或 scene"
            )

        return ApiResponse(
            code=200,
            message="保存成功",
            data=result
        )

    except Exception as e:
        logger.error(f"保存到素材库失败: {e}")
        return ApiResponse(
            code=500,
            message=f"保存失败：{str(e)}"
        )


async def _save_as_character(segments: list, service) -> dict:
    """保存为角色素材，将视频文件复制到 data/roles/ 目录"""
    import json
    import uuid
    import shutil

    # 导入 materials 模块的函数和数据
    from api.routers.materials import (
        MOCK_ROLES, save_mock_roles, generate_role_thumbnail, resolve_video_path
    )
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent.parent

    role_id = f"r{len(MOCK_ROLES) + 1:03d}"
    role_name = f"角色_{len(MOCK_ROLES) + 1}"

    # 将视频文件复制到 backend/data/roles/ 目录
    role_dir = project_root / "backend" / "data" / "roles"
    role_dir.mkdir(parents=True, exist_ok=True)

    def copy_video_to_role_dir(video_path_str: str) -> str:
        if not video_path_str:
            return ""
        resolved = resolve_video_path(video_path_str)
        if not resolved or not resolved.exists():
            logger.warning(f"角色视频源文件不存在: {video_path_str}")
            return video_path_str
        dest_filename = f"role_{uuid.uuid4().hex[:8]}{resolved.suffix}"
        dest_path = role_dir / dest_filename
        shutil.copy2(str(resolved), str(dest_path))
        logger.info(f"角色视频已复制到: {dest_path}")
        return f"backend/data/roles/{dest_filename}"

    # 分配视频：第一个为开场，其余为循环
    opening_video = None
    loop_videos = []
    ending_video = None

    for i, segment in enumerate(segments):
        video_path = segment.get("video_path", "")
        if not video_path:
            continue

        if opening_video is None:
            opening_video = copy_video_to_role_dir(video_path)
        else:
            saved_path = copy_video_to_role_dir(video_path)
            loop_videos.append({"path": saved_path})

    # 生成缩略图
    thumbnail_path = generate_role_thumbnail(
        opening_video=opening_video or "",
        loop_videos=loop_videos,
        ending_video=ending_video or "",
        role_id=role_id
    ) or ""

    new_role = {
        "role_id": role_id,
        "role_name": role_name,
        "role_type": "human",
        "scenes": [],
        "opening_video": opening_video or "",
        "loop_videos": loop_videos,
        "ending_video": ending_video or "",
        "audio_id": "",
        "description": "",
        "video_count": len(segments),
        "is_double_mode": False,
        "left_audio_id": None,
        "right_audio_id": None,
        "thumbnail": thumbnail_path
    }

    MOCK_ROLES.append(new_role)
    save_mock_roles()
    logger.info(f"智能裁剪保存角色素材: {role_id}, 视频数: {len(segments)}")

    return {
        "role_id": role_id,
        "role_name": role_name,
        "video_count": len(segments),
        "thumbnail": thumbnail_path
    }


async def _save_as_scene(segments: list, service) -> dict:
    """保存为场景素材，将视频文件复制到 data/scenes/ 目录"""
    import json
    import uuid
    import shutil

    # 导入 materials 模块的函数和数据
    from api.routers.materials import (
        MOCK_SCENES, save_mock_scenes, generate_scene_thumbnail, resolve_video_path
    )
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent.parent

    scene_id = f"s{len(MOCK_SCENES) + 1:03d}"
    scene_name = f"场景_{len(MOCK_SCENES) + 1}"

    # 将视频文件复制到 backend/data/scenes/ 目录
    scene_dir = project_root / "backend" / "data" / "scenes"
    scene_dir.mkdir(parents=True, exist_ok=True)

    saved_scene_videos = []
    for segment in segments:
        video_path = segment.get("video_path", "")
        if not video_path:
            continue

        resolved = resolve_video_path(video_path)
        if not resolved or not resolved.exists():
            logger.warning(f"场景视频源文件不存在: {video_path}")
            continue

        dest_filename = f"scene_{uuid.uuid4().hex[:8]}{resolved.suffix}"
        dest_path = scene_dir / dest_filename
        shutil.copy2(str(resolved), str(dest_path))
        logger.info(f"场景视频已复制到: {dest_path}")
        saved_scene_videos.append({"path": f"backend/data/scenes/{dest_filename}"})

    # 生成缩略图
    thumbnail_path = generate_scene_thumbnail(
        scene_videos=saved_scene_videos,
        scene_id=scene_id
    ) or ""

    new_scene = {
        "scene_id": scene_id,
        "scene_name": scene_name,
        "scene_type": "场景",
        "scene_videos": saved_scene_videos,
        "description": "",
        "video_count": len(saved_scene_videos),
        "thumbnail": thumbnail_path
    }

    MOCK_SCENES.append(new_scene)
    save_mock_scenes()
    logger.info(f"智能裁剪保存场景素材: {scene_id}, 视频数: {len(saved_scene_videos)}")

    return {
        "scene_id": scene_id,
        "scene_name": scene_name,
        "video_count": len(saved_scene_videos),
        "thumbnail": thumbnail_path
    }


@router.get("/merged-videos", response_model=ApiResponse)
async def get_merged_videos():
    """
    获取合成视频列表

    返回 output 目录中所有合成视频文件的信息
    """
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    output_dir = project_root / "output"

    if not output_dir.exists():
        return ApiResponse(code=200, message="success", data={"videos": []})

    videos = []
    for f in sorted(output_dir.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        # 获取视频时长
        duration = 0.0
        try:
            import cv2
            cap = cv2.VideoCapture(str(f))
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                if fps > 0:
                    duration = frame_count / fps
            cap.release()
        except Exception:
            pass

        videos.append({
            "name": f.stem,
            "path": f"output/{f.name}",
            "size": f.stat().st_size,
            "duration": round(duration, 2),
            "created_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
        })

    return ApiResponse(code=200, message="success", data={"videos": videos})


@router.delete("/merged-videos/{filename}", response_model=ApiResponse)
async def delete_merged_video(filename: str):
    """
    删除合成视频文件

    从 output 目录中删除指定的合成视频
    """
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    output_dir = project_root / "output"

    video_file = output_dir / filename

    if not video_file.exists():
        return ApiResponse(
            code=404,
            message="文件不存在"
        )

    # 安全检查：确保文件在 output 目录内
    try:
        video_file.resolve().relative_to(output_dir.resolve())
    except ValueError:
        return ApiResponse(
            code=400,
            message="非法路径"
        )

    video_file.unlink()
    logger.info(f"已删除合成视频: {filename}")

    return ApiResponse(
        code=200,
        message="删除成功"
    )
