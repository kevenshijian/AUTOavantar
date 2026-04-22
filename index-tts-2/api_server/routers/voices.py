"""
音色管理路由
提供预设音色查询、上传和创建接口
"""

import logging

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from api_server.models.voice import (
    VoiceCreateResponse,
    VoiceInfo,
    VoiceListResponse,
    VoiceUploadResponse,
)

logger = logging.getLogger("indextts-api.voices")

router = APIRouter()

_voice_manager = None  # type: ignore


def set_voice_manager(voice_manager) -> None:
    """注入音色管理服务实例"""
    global _voice_manager
    _voice_manager = voice_manager


@router.get("", response_model=VoiceListResponse)
async def list_voices():
    """
    获取可用预设音色列表

    返回所有预设音色的名称、文件大小和状态。
    """
    if _voice_manager is None:
        raise HTTPException(status_code=503, detail="音色管理服务未初始化")

    voices = _voice_manager.scan_voices()
    return VoiceListResponse(
        voices=[VoiceInfo(**v) for v in voices]
    )


@router.post("/upload", response_model=VoiceUploadResponse)
async def upload_voice(audio_file: UploadFile = File(...)):
    """
    上传自定义音频文件，提取音色特征（不保存为预设）

    上传的音频文件仅用于临时提取特征，不会被保存为预设音色。
    """
    if _voice_manager is None:
        raise HTTPException(status_code=503, detail="音色管理服务未初始化")

    # 校验文件类型
    if audio_file.content_type and not audio_file.content_type.startswith(("audio/",)):
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {audio_file.content_type}，请上传音频文件")

    # 保存上传文件到临时目录
    import tempfile

    suffix = ".wav"
    if audio_file.filename:
        ext = audio_file.filename.rsplit(".", 1)[-1].lower() if "." in audio_file.filename else ""
        if ext in ("mp3", "flac", "ogg", "m4a"):
            suffix = f".{ext}"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await audio_file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        temp_path, shape = _voice_manager.extract_features(tmp_path)
        return VoiceUploadResponse(
            temp_path=temp_path,
            feature_shape=shape,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"音频处理失败: {e}")
    finally:
        import os
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("", response_model=VoiceCreateResponse, status_code=201)
async def create_voice(
    audio_file: UploadFile = File(...),
    name: str = Form(...),
):
    """
    上传音频并保存为新预设音色

    从音频文件提取特征，以指定名称保存为预设音色。
    """
    if _voice_manager is None:
        raise HTTPException(status_code=503, detail="音色管理服务未初始化")

    # 保存上传文件到临时目录
    import tempfile

    suffix = ".wav"
    if audio_file.filename:
        ext = audio_file.filename.rsplit(".", 1)[-1].lower() if "." in audio_file.filename else ""
        if ext in ("mp3", "flac", "ogg", "m4a"):
            suffix = f".{ext}"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await audio_file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        saved_path, size = _voice_manager.save_voice(tmp_path, name)
        from datetime import datetime, timezone

        return VoiceCreateResponse(
            name=name,
            file=f"{name}.pt",
            size_bytes=size,
            status="ready",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"音色保存失败: {e}")
    finally:
        import os
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
