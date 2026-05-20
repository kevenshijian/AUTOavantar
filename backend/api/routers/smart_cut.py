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
            transition=request.transition
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
        material_type = request.get("type", "character")  # character 或 scene

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
                message=f"不支持的素材类型: {material_type}"
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
    """保存为角色素材"""
    import json
    import uuid

    # 生成角色ID和名称
    role_id = f"r{len(json.loads(service._get_mock_roles())) + 1:03d}"
    role_name = f"角色_{len(json.loads(service._get_mock_roles())) + 1}"

    # 选择开场视频（第一个片段）
    opening_video = None
    loop_videos = []
    ending_video = None

    for i, segment in enumerate(segments):
        video_path = segment.get("video_path", "")
        if not video_path:
            continue

        full_path = service.base_dir / video_path
        if full_path.exists():
            if opening_video is None:
                opening_video = str(full_path.relative_to(service.base_dir))
            else:
                loop_videos.append({"path": str(full_path.relative_to(service.base_dir))})

    # 生成缩略图
    thumbnail_path = service._generate_role_thumbnail(opening_video or "", loop_videos, ending_video, role_id)

    # 保存到模拟数据
    mock_data_path = Path(__file__).parent.parent.parent / "data" / "mock_roles.json"
    mock_data_path.parent.mkdir(parents=True, exist_ok=True)

    with open(mock_data_path, 'r', encoding='utf-8') as f:
        mock_roles = json.load(f)

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

    mock_roles.append(new_role)

    with open(mock_data_path, 'w', encoding='utf-8') as f:
        json.dump(mock_roles, f, ensure_ascii=False, indent=2)

    return {
        "role_id": role_id,
        "role_name": role_name,
        "video_count": len(segments),
        "thumbnail": thumbnail_path
    }


async def _save_as_scene(segments: list, service) -> dict:
    """保存为场景素材"""
    import json

    # 生成场景ID和名称
    scene_id = f"s{len(json.loads(service._get_mock_scenes())) + 1:03d}"
    scene_name = f"场景_{len(json.loads(service._get_mock_scenes())) + 1}"

    # 收集所有视频路径
    scene_videos = []
    for segment in segments:
        video_path = segment.get("video_path", "")
        if video_path:
            full_path = service.base_dir / video_path
            if full_path.exists():
                scene_videos.append({"path": str(full_path.relative_to(service.base_dir))})

    # 生成缩略图
    thumbnail_path = service._generate_scene_thumbnail(scene_videos, scene_id)

    # 保存到模拟数据
    mock_data_path = Path(__file__).parent.parent.parent / "data" / "mock_scenes.json"
    mock_data_path.parent.mkdir(parents=True, exist_ok=True)

    with open(mock_data_path, 'r', encoding='utf-8') as f:
        mock_scenes = json.load(f)

    new_scene = {
        "scene_id": scene_id,
        "scene_name": scene_name,
        "scene_type": "场景",
        "scene_videos": scene_videos,
        "description": "",
        "video_count": len(scene_videos),
        "thumbnail": thumbnail_path
    }

    mock_scenes.append(new_scene)

    with open(mock_data_path, 'w', encoding='utf-8') as f:
        json.dump(mock_scenes, f, ensure_ascii=False, indent=2)

    return {
        "scene_id": scene_id,
        "scene_name": scene_name,
        "video_count": len(scene_videos),
        "thumbnail": thumbnail_path
    }


def _get_mock_roles(self) -> str:
    """获取模拟角色数据"""
    mock_data_path = Path(__file__).parent.parent.parent / "data" / "mock_roles.json"
    if mock_data_path.exists():
        with open(mock_data_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "[]"


def _get_mock_scenes(self) -> str:
    """获取模拟场景数据"""
    mock_data_path = Path(__file__).parent.parent.parent / "data" / "mock_scenes.json"
    if mock_data_path.exists():
        with open(mock_data_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "[]"


def _generate_role_thumbnail(self, opening_video: str, loop_videos: list, ending_video: str, role_id: str) -> str:
    """生成角色缩略图"""
    import base64
    import cv2

    # 选择视频
    video_path = None
    if opening_video:
        video_path = opening_video
    else:
        all_videos = [{"path": v["path"]} for v in loop_videos]
        if ending_video:
            all_videos.append({"path": ending_video})
        if all_videos:
            video_path = all_videos[0]["path"]

    if not video_path:
        return ""

    # 提取第一帧
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return ""

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        return ""

    # 编码为base64
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    frame_base64 = base64.b64encode(buffer).decode('utf-8')

    # 返回相对路径
    return f"data/thumbnails/roles/{role_id}.jpg"


def _generate_scene_thumbnail(self, scene_videos: list, scene_id: str) -> str:
    """生成场景缩略图"""
    import base64
    import cv2

    if not scene_videos:
        return ""

    # 选择第一个视频
    video_path = scene_videos[0]["path"]

    # 提取第一帧
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return ""

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        return ""

    # 编码为base64
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    frame_base64 = base64.b64encode(buffer).decode('utf-8')

    # 返回相对路径
    return f"data/thumbnails/scenes/{scene_id}.jpg"
