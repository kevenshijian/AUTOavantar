"""
TTS 合成路由
处理语音合成请求，接入情绪映射逻辑
"""

import logging

from fastapi import APIRouter, HTTPException

from api_server.models.tts import InferMode, SynthesizeRequest, SynthesizeResponse

logger = logging.getLogger("indextts-api.tts")

router = APIRouter()

# 服务实例，在 main.py lifespan 中初始化后注入
_emotion_service = None
_task_queue = None
_voice_manager = None
_audio_speed_service = None


def set_services(emotion_service, task_queue, voice_manager, audio_speed_service=None) -> None:
    """注入服务实例（由 main.py 在启动时调用）"""
    global _emotion_service, _task_queue, _voice_manager, _audio_speed_service
    _emotion_service = emotion_service
    _task_queue = task_queue
    _voice_manager = voice_manager
    _audio_speed_service = audio_speed_service


@router.post("/synthesize", response_model=SynthesizeResponse, status_code=202)
async def synthesize(request: SynthesizeRequest):
    """
    提交 TTS 合成任务

    支持原版 IndexTTS2 的4种情绪控制方式：
    1. emotion + intensity: 情绪标签 + 强度
    2. emo_audio_prompt + emo_alpha: 情绪参考音频 + 强度
    3. emo_vector: 8元素列表 [happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]
    4. use_emo_text=True: 根据文本自动推断情绪
    """
    if not request.voice_name and not request.reference_audio:
        raise HTTPException(status_code=400, detail="必须提供 voice_name 或 reference_audio")

    if _task_queue is None:
        raise HTTPException(status_code=503, detail="服务正在启动中，请稍后重试")

    voice_path = None
    if request.voice_name:
        if _voice_manager is None:
            raise HTTPException(status_code=503, detail="音色管理服务未初始化")
        voice_path = _voice_manager.get_voice_path(request.voice_name)
        if voice_path is None:
            raise HTTPException(status_code=400, detail=f"音色 '{request.voice_name}' 不存在")
    elif request.reference_audio:
        voice_path = request.reference_audio

    emo_vector = None
    emo_alpha = 1.0
    speed = 1.0

    if request.emo_vector is not None:
        emo_vector = request.emo_vector
        emo_alpha = request.emo_alpha
        logger.info(f"使用直接传入的 emo_vector: {emo_vector}, emo_alpha={emo_alpha}")
    elif request.emotion:
        if _emotion_service is None:
            raise HTTPException(status_code=503, detail="情绪映射服务未初始化")
        if _emotion_service.load_error:
            raise HTTPException(status_code=503, detail="情绪映射表不可用，无法处理情绪参数")
        vec, speed, error = _emotion_service.resolve(request.emotion)
        if vec is None:
            raise HTTPException(status_code=400, detail=error)
        emo_vector = vec
        emo_alpha = request.intensity
        logger.info(f"情绪标签解析: '{request.emotion}' + intensity={request.intensity} → emo_vector={emo_vector}, speed={speed}")

    # 根据语速参数调节参考音频
    adjusted_voice_path = voice_path
    if _audio_speed_service and speed != 1.0:
        logger.info(f"根据情绪语速调节参考音频: {speed}x")
        adjusted_path = _audio_speed_service.adjust_audio_speed(voice_path, speed)
        if adjusted_path:
            adjusted_voice_path = adjusted_path
            logger.info(f"参考音频语速调节完成: {adjusted_voice_path}")
        else:
            logger.warning(f"参考音频语速调节失败，使用原始音频: {voice_path}")

    try:
        task = await _task_queue.submit(
            text=request.text,
            voice_path=adjusted_voice_path,
            emo_audio_prompt=None,
            emo_alpha=emo_alpha,
            emo_vector=emo_vector,
            use_emo_text=request.use_emo_text,
            emo_text=request.emo_text,
            use_random=request.use_random,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            num_beams=request.num_beams,
        )

        # 如果使用了调节后的音频，注册到任务队列以便清理
        if _audio_speed_service and adjusted_voice_path != voice_path:
            _task_queue.register_temp_audio(task.task_id, adjusted_voice_path)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return SynthesizeResponse(
        task_id=task.task_id,
        status=task.status.value,
        queue_position=task.queue_position,
    )
