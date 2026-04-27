"""
功能接口路由
处理面部分析、音频提取、降噪、文案处理等核心功能
"""

import os
import logging
import json
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import subprocess

from config.settings import settings
from business.preprocess.video_preprocessor import VideoPreprocessor
from business.audio.gtcrn_denoiser import GTCDenoiser
from api.services.llm_service import LLMScriptGenerator, create_script_generator

logger = logging.getLogger("autoavantar-api.functions")

router = APIRouter()


class FaceAnalysisRequest(BaseModel):
    """面部分析请求"""
    video_path: str
    video_type: str = "opening"


class FaceAnalysisResponse(BaseModel):
    """面部分析响应"""
    status: str
    invalid_frame_count: int
    output_video_path: Optional[str] = None
    message: str


class ExtractAudioRequest(BaseModel):
    """提取音频请求"""
    video_path: str


class ExtractAudioResponse(BaseModel):
    """提取音频响应"""
    status: str
    audio_path: str
    duration: float
    message: str


class DenoiseRequest(BaseModel):
    """降噪请求"""
    audio_path: str


class DenoiseResponse(BaseModel):
    """降噪响应"""
    status: str
    output_audio_path: str
    message: str


class TextProcessRequest(BaseModel):
    """文案处理请求"""
    text: str
    mode: str = "single"
    gen_type: str = "manual"


class TextProcessResponse(BaseModel):
    """文案处理响应"""
    status: str
    parsed_script: Optional[Dict[str, Any]] = None
    tags: List[str] = []
    message: str


class GenerateScriptRequest(BaseModel):
    """生成文案请求"""
    topic: str
    prompt: str = ""
    mode: str = "single"


class ExtractFrameRequest(BaseModel):
    """提取视频首帧请求"""
    video_path: str


class ExtractFrameResponse(BaseModel):
    """提取视频首帧响应"""
    code: int = 200
    message: str = "success"
    data: Optional[Dict[str, Any]] = None


_face_analyzer: Optional[VideoPreprocessor] = None
_denoiser: Optional[GTCDenoiser] = None


def get_face_analyzer() -> VideoPreprocessor:
    """获取面部分析器实例"""
    global _face_analyzer
    if _face_analyzer is None:
        _face_analyzer = VideoPreprocessor()
    return _face_analyzer


def get_denoiser() -> GTCDenoiser:
    """获取降噪器实例"""
    global _denoiser
    if _denoiser is None:
        _denoiser = GTCDenoiser()
    return _denoiser


def get_script_generator() -> LLMScriptGenerator:
    """获取文案生成器实例（每次调用都重新读取配置以确保使用最新值）"""
    from api.services.workflow_service import load_api_keys_config
    api_config = load_api_keys_config()
    deepseek_api_key = api_config.get('deepseek_api_key', '')
    return create_script_generator(
        provider="deepseek",
        api_key=deepseek_api_key,
        model="deepseek-v4-flash"
    )


def get_similar_tags(tag: str) -> List[str]:
    """
    获取情绪标签的相似标签
    
    Args:
        tag: 情绪标签
    
    Returns:
        相似标签列表
    """
    emotion_params = {
        "开心": {"vec1": 0.2},
        "高兴": {"vec1": 0.2, "vec7": 0.1},
        "生气": {"vec2": 0.2},
        "愤怒": {"vec2": 0.2, "vec5": 0.1},
        "激动": {"vec1": 0.2, "vec2": 0.2},
        "难过": {"vec3": 0.2},
        "悲伤": {"vec3": 0.2, "vec6": 0.1},
        "伤心": {"vec3": 0.2, "vec4": 0.2},
        "害怕": {"vec4": 0.3},
        "恐惧": {"vec4": 0.3, "vec6": 0.3},
        "惊慌": {"vec4": 0.3, "vec7": 0.3},
        "厌恶": {"vec5": 0.3},
        "讨厌": {"vec5": 0.3, "vec6": 0.2},
        "憎恨": {"vec5": 0.3, "vec2": 0.2},
        "低落": {"vec6": 0.3},
        "忧伤": {"vec6": 0.3, "vec3": 0.2},
        "沮丧": {"vec6": 0.3, "vec8": 0.2},
        "惊喜": {"vec7": 0.3},
        "兴奋": {"vec7": 0.3, "vec2": 0.2},
        "平淡": {"vec8": 0.2, "vec5": 0.2},
        "冷静": {"vec8": 0.3}
    }
    
    similar_tags = {
        "开心": ["惊喜", "高兴"],
        "高兴": ["开心", "惊喜"],
        "生气": ["愤怒", "激动"],
        "愤怒": ["生气", "激动"],
        "激动": ["生气", "愤怒", "惊喜"],
        "难过": ["悲伤", "伤心"],
        "悲伤": ["难过", "伤心"],
        "伤心": ["悲伤", "难过"],
        "害怕": ["恐惧", "惊慌"],
        "恐惧": ["害怕", "惊慌"],
        "惊慌": ["害怕", "恐惧"],
        "厌恶": ["讨厌", "憎恨"],
        "讨厌": ["厌恶", "憎恨"],
        "憎恨": ["讨厌", "厌恶"],
        "低落": ["忧伤", "沮丧"],
        "忧伤": ["沮丧", "低落"],
        "沮丧": ["忧伤", "低落"],
        "惊喜": ["开心", "兴奋", "激动"],
        "兴奋": ["激动", "惊喜"],
        "平淡": ["冷静"],
        "冷静": ["平淡"]
    }
    
    return similar_tags.get(tag, [])


def process_emotion_tags(emotion_tags: List[str]) -> List[Dict[str, Any]]:
    """
    处理情绪标签，添加相似标签和参数
    
    Args:
        emotion_tags: 情绪标签列表
    
    Returns:
        处理后的情绪标签列表，包含标签、参数和相似标签
    """
    emotion_params = {
        "开心": {"vec1": 0.2},
        "高兴": {"vec1": 0.2, "vec7": 0.1},
        "生气": {"vec2": 0.2},
        "愤怒": {"vec2": 0.2, "vec5": 0.1},
        "激动": {"vec1": 0.2, "vec2": 0.2},
        "难过": {"vec3": 0.2},
        "悲伤": {"vec3": 0.2, "vec6": 0.1},
        "伤心": {"vec3": 0.2, "vec4": 0.2},
        "害怕": {"vec4": 0.3},
        "恐惧": {"vec4": 0.3, "vec6": 0.3},
        "惊慌": {"vec4": 0.3, "vec7": 0.3},
        "厌恶": {"vec5": 0.3},
        "讨厌": {"vec5": 0.3, "vec6": 0.2},
        "憎恨": {"vec5": 0.3, "vec2": 0.2},
        "低落": {"vec6": 0.3},
        "忧伤": {"vec6": 0.3, "vec3": 0.2},
        "沮丧": {"vec6": 0.3, "vec8": 0.2},
        "惊喜": {"vec7": 0.3},
        "兴奋": {"vec7": 0.3, "vec2": 0.2},
        "平淡": {"vec8": 0.2, "vec5": 0.2},
        "冷静": {"vec8": 0.3}
    }
    
    similar_tags = {
        "开心": ["惊喜", "高兴"],
        "高兴": ["开心", "惊喜"],
        "生气": ["愤怒", "激动"],
        "愤怒": ["生气", "激动"],
        "激动": ["生气", "愤怒", "惊喜"],
        "难过": ["悲伤", "伤心"],
        "悲伤": ["难过", "伤心"],
        "伤心": ["悲伤", "难过"],
        "害怕": ["恐惧", "惊慌"],
        "恐惧": ["害怕", "惊慌"],
        "惊慌": ["害怕", "恐惧"],
        "厌恶": ["讨厌", "憎恨"],
        "讨厌": ["厌恶", "憎恨"],
        "憎恨": ["讨厌", "厌恶"],
        "低落": ["忧伤", "沮丧"],
        "忧伤": ["沮丧", "低落"],
        "沮丧": ["忧伤", "低落"],
        "惊喜": ["开心", "兴奋", "激动"],
        "兴奋": ["激动", "惊喜"],
        "平淡": ["冷静"],
        "冷静": ["平淡"]
    }
    
    processed_tags = []
    for tag in emotion_tags:
        if tag in emotion_params:
            processed_tags.append({
                "tag": tag,
                "params": emotion_params[tag],
                "similar_tags": similar_tags.get(tag, [])
            })
    
    return processed_tags


@router.post("/face-analysis", response_model=FaceAnalysisResponse)
async def analyze_face(request: FaceAnalysisRequest):
    """
    面部分析接口

    处理逻辑：
    1. 使用 MediaPipe 检测视频每一帧的面部关键点
    2. 判定规则：
       - 合格：检测到鼻子 + 完整嘴唇（上唇、下唇、左右唇角）
       - 不合格：缺失任一关键点
    3. 删除不合格帧，使用 FFmpeg 重新封装视频
    4. 返回结果：分析状态、不合格帧数、处理后视频路径
    """
    video_path = request.video_path

    if not os.path.exists(video_path):
        raise HTTPException(status_code=400, detail=f"视频文件不存在: {video_path}")

    try:
        analyzer = get_face_analyzer()

        # 检测面部
        result = analyzer.detect_faces(video_path)

        invalid_count = result.invalid_frames

        output_path = video_path
        if invalid_count > 0:
            output_path = video_path.replace(".mp4", "_processed.mp4")
            # 处理视频，删除不合格帧
            process_result = analyzer.process_video(video_path, output_path)
            logger.info(f"面部分析完成，已移除 {invalid_count} 帧不合格画面")

        return FaceAnalysisResponse(
            status="success",
            invalid_frame_count=invalid_count,
            output_video_path=output_path,
            message=f"分析完成，已移除 {invalid_count} 段不合格画面"
        )

    except Exception as e:
        logger.error(f"面部分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"面部分析失败: {str(e)}")


@router.post("/extract-audio", response_model=ExtractAudioResponse)
async def extract_audio(request: ExtractAudioRequest):
    """
    提取音频接口

    处理逻辑：
    1. 使用 FFmpeg 从视频中提取音频（格式：mp3）
    2. 返回结果：音频路径、音频时长
    """
    from pathlib import Path
    from config.settings import settings
    
    full_video_path = request.video_path

    if not os.path.exists(full_video_path):
        raise HTTPException(status_code=400, detail=f"视频文件不存在: {full_video_path}")

    try:
        base_name = os.path.splitext(os.path.basename(full_video_path))[0]
        
        # 构建音频保存路径
        backend_root = Path(__file__).resolve().parent.parent.parent
        audio_dir = backend_root / settings.UPLOAD_DIR / "audios" / "reference"
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        audio_path = str(audio_dir / f"{base_name}_extracted.wav")
        
        # 计算相对于 UPLOAD_DIR 的路径
        relative_audio_path = os.path.relpath(audio_path, str(backend_root / settings.UPLOAD_DIR))

        cmd = [
            "ffmpeg", "-i", full_video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            "-y", audio_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        duration = 0.0
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        try:
            result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            duration = float(result.stdout.strip())
        except:
            pass

        return ExtractAudioResponse(
            status="success",
            audio_path=relative_audio_path,
            duration=duration,
            message="音频提取成功"
        )

    except Exception as e:
        logger.error(f"音频提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"音频提取失败: {str(e)}")


@router.post("/audio-denoise", response_model=DenoiseResponse)
async def denoise_audio(request: DenoiseRequest):
    """
    降噪增强接口

    处理逻辑：
    1. 调用 GTCRN 音频降噪模块处理音频
    2. 替换原音频文件，返回处理后音频路径
    """
    audio_path = request.audio_path

    # 拼接完整路径
    full_audio_path = os.path.join(settings.UPLOAD_DIR, audio_path)

    if not os.path.exists(full_audio_path):
        raise HTTPException(status_code=400, detail=f"音频文件不存在: {full_audio_path}")

    try:
        denoiser = get_denoiser()
        output_path = denoiser.denoise(full_audio_path)

        return DenoiseResponse(
            status="success",
            output_audio_path=output_path,
            message="降噪增强完成"
        )

    except Exception as e:
        logger.error(f"降噪处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"降噪处理失败: {str(e)}")


@router.post("/text-process", response_model=TextProcessResponse)
async def process_text(request: TextProcessRequest):
    """
    文案处理接口

    处理逻辑：
    - 智能生成模式：
      1. 解析 JSON 格式文案，提取字段（开场、情绪标签、场景标签、结束，双人模式额外提取左/右说话人）
      2. 按标签打组（开场、循环、结束），双人模式按说话人分组
    - 手动输入模式：直接返回原文本，不解析
    - 返回结果：解析后的文案结构、标签列表
    """
    try:
        text = request.text
        mode = request.mode
        gen_type = request.gen_type

        if gen_type == "llm" or gen_type == "smart":
            try:
                parsed = json.loads(text)

                tags = []
                emotions = []
                scenes = []

                # 情绪标签列表
                emotion_tags = ["开心", "高兴", "生气", "愤怒", "激动", "难过", "悲伤", "伤心", "害怕", "恐惧", "惊慌", "厌恶", "讨厌", "憎恨", "低落", "忧伤", "沮丧", "惊喜", "兴奋", "平淡", "冷静"]
                # 场景标签列表
                scene_tags = ["环境展示", "产品展示", "细节展示", "功能介绍", "使用效果"]
                # 场景标签相似标签映射
                scene_similar_tags = {
                    "环境展示": ["产品展示", "细节展示"],
                    "产品展示": ["功能介绍", "使用效果"],
                    "细节展示": ["产品展示", "功能介绍"],
                    "功能介绍": ["细节展示", "使用效果"],
                    "使用效果": ["产品展示", "功能介绍"]
                }
                
                # 情绪参数映射
                emotion_params = {
                    "开心": {"vec1": 0.2},
                    "高兴": {"vec1": 0.2, "vec7": 0.1},
                    "生气": {"vec2": 0.2},
                    "愤怒": {"vec2": 0.2, "vec5": 0.1},
                    "激动": {"vec1": 0.2, "vec2": 0.2},
                    "难过": {"vec3": 0.2},
                    "悲伤": {"vec3": 0.2, "vec6": 0.1},
                    "伤心": {"vec3": 0.2, "vec4": 0.2},
                    "害怕": {"vec4": 0.3},
                    "恐惧": {"vec4": 0.3, "vec6": 0.3},
                    "惊慌": {"vec4": 0.3, "vec7": 0.3},
                    "厌恶": {"vec5": 0.3},
                    "讨厌": {"vec5": 0.3, "vec6": 0.2},
                    "憎恨": {"vec5": 0.3, "vec2": 0.2},
                    "低落": {"vec6": 0.3},
                    "忧伤": {"vec6": 0.3, "vec3": 0.2},
                    "沮丧": {"vec6": 0.3, "vec8": 0.2},
                    "惊喜": {"vec7": 0.3},
                    "兴奋": {"vec7": 0.3, "vec2": 0.2},
                    "平淡": {"vec8": 0.2, "vec5": 0.2},
                    "冷静": {"vec8": 0.3}
                }
                
                # 相似标签映射
                similar_tags = {
                    "开心": ["惊喜", "高兴"],
                    "高兴": ["开心", "惊喜"],
                    "生气": ["愤怒", "激动"],
                    "愤怒": ["生气", "激动"],
                    "激动": ["生气", "愤怒", "惊喜"],
                    "难过": ["悲伤", "伤心"],
                    "悲伤": ["难过", "伤心"],
                    "伤心": ["悲伤", "难过"],
                    "害怕": ["恐惧", "惊慌"],
                    "恐惧": ["害怕", "惊慌"],
                    "惊慌": ["害怕", "恐惧"],
                    "厌恶": ["讨厌", "憎恨"],
                    "讨厌": ["厌恶", "憎恨"],
                    "憎恨": ["讨厌", "厌恶"],
                    "低落": ["忧伤", "沮丧"],
                    "忧伤": ["沮丧", "低落"],
                    "沮丧": ["忧伤", "低落"],
                    "惊喜": ["开心", "兴奋", "激动"],
                    "兴奋": ["激动", "惊喜"],
                    "平淡": ["冷静"],
                    "冷静": ["平淡"]
                }

                # 提取开场和结束
                opening = parsed.get("opening", parsed.get("开场", ""))
                ending = parsed.get("ending", parsed.get("结束", ""))

                # 提取情绪标签和场景标签
                emotion_details = []
                scene_details = []
                for key, value in parsed.items():
                    if key in emotion_tags:
                        emotions.append(key)
                        # 添加情绪详情，包括参数和相似标签
                        emotion_detail = {
                            "tag": key,
                            "content": value,
                            "params": emotion_params.get(key, {}),
                            "similar_tags": similar_tags.get(key, [])
                        }
                        emotion_details.append(emotion_detail)
                    elif key in scene_tags:
                        scenes.append(key)
                        # 添加场景详情，包括相似标签
                        scene_detail = {
                            "tag": key,
                            "content": value,
                            "similar_tags": scene_similar_tags.get(key, [])
                        }
                        scene_details.append(scene_detail)

                tags = emotions + scenes

                # 构建解析后的文案结构
                parsed_script = {
                    "opening": opening,
                    "ending": ending,
                    "segments": [],
                    "emotions": emotions,
                    "emotion_details": emotion_details,
                    "scenes": scenes,
                    "scene_details": scene_details,
                    "similar_tags_mapping": {
                        "emotion": similar_tags,
                        "scene": scene_similar_tags
                    }
                }

                # 处理双人模式
                if mode == "dual":
                    left_speaker = []
                    right_speaker = []
                    segments = []
                    
                    # 提取左边说话人和右边说话人内容
                    for key, value in parsed.items():
                        if isinstance(value, list):
                            for i, item in enumerate(value):
                                if isinstance(item, dict):
                                    if "左边说话人" in item:
                                        left_text = item["左边说话人"]
                                        left_speaker.append(left_text)
                                        segments.append({
                                            "text": left_text,
                                            "speaker": "left",
                                            "index": i
                                        })
                                    if "右边说话人" in item:
                                        right_text = item["右边说话人"]
                                        right_speaker.append(right_text)
                                        segments.append({
                                            "text": right_text,
                                            "speaker": "right",
                                            "index": i
                                        })
                    
                    # 按索引排序，确保顺序正确
                    segments.sort(key=lambda x: x["index"])
                    
                    parsed_script["left_speaker"] = left_speaker
                    parsed_script["right_speaker"] = right_speaker
                    parsed_script["segments"] = segments

                # 按标签打组（开场、循环、结束）
                grouped_script = {
                    "开场": opening,
                    "循环": [],
                    "结束": ending
                }

                # 填充循环部分（情绪标签和场景标签）
                for key, value in parsed.items():
                    if key in emotion_tags or key in scene_tags:
                        grouped_script["循环"].append({"标签": key, "内容": value})

                parsed_script["grouped"] = grouped_script

                # 提取封面总结
                if "封面总结" in parsed:
                    parsed_script["cover_summary"] = parsed["封面总结"]

                return TextProcessResponse(
                    status="success",
                    parsed_script=parsed_script,
                    tags=tags,
                    message="文案解析成功"
                )

            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {e}")
                return TextProcessResponse(
                    status="error",
                    message=f"智能生成模式需要 JSON 格式的文案: {str(e)}"
                )
        else:
            return TextProcessResponse(
                status="success",
                parsed_script={
                    "full_text": text,
                    "segments": [{"text": text, "emotion": "calm", "scene": "default"}]
                },
                tags=[],
                message="手动输入模式，文案已接收"
            )

    except Exception as e:
        logger.error(f"文案处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"文案处理失败: {str(e)}")


@router.post("/generate-script")
async def generate_script(request: GenerateScriptRequest):
    """
    LLM 生成文案接口

    Args:
        request: 生成文案请求，包含主题、提示词模板和模式

    Returns:
        生成的文案内容
    """
    try:
        topic = request.topic
        prompt_template = request.prompt
        mode = request.mode
        generator = get_script_generator()

        # 构建最终提示词
        if prompt_template:
            # 如果有自定义模板，替换其中的 {theme} 变量
            final_prompt = prompt_template.replace("{theme}", topic)
        else:
            # 如果没有自定义模板，使用默认模板
            if mode == "single":
                final_prompt = f"根据主题{topic}生成单人讲解文案，包含开场、情绪标签、场景标签、结束部分。请以 JSON 格式返回。"
            else:
                final_prompt = f"根据主题{topic}生成双人对话文案，包含开场、左边说话人、右边说话人、情绪标签、场景标签、结束部分。请以 JSON 格式返回。"
        
        result = await generator.generate(final_prompt)
        
        # 确保返回的是有效的JSON字符串
        try:
            # 验证JSON格式
            json.loads(result)
            script = result
        except json.JSONDecodeError:
            # 如果不是有效的JSON，返回错误
            raise HTTPException(status_code=500, detail="生成的文案格式错误")

        return {
            "code": 200,
            "message": "文案生成成功",
            "data": {
                "script": script,
                "topic": topic,
                "prompt": prompt_template,
                "mode": mode
            }
        }

    except Exception as e:
        logger.error(f"文案生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"文案生成失败: {str(e)}")


@router.post("/extract-frame", response_model=ExtractFrameResponse)
async def extract_frame(request: ExtractFrameRequest):
    """
    提取视频首帧接口

    Args:
        request: 提取首帧请求，包含视频路径

    Returns:
        base64 编码的首帧图像
    """
    import cv2
    import base64
    
    video_path = request.video_path
    
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"视频文件不存在: {video_path}")
    
    try:
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise HTTPException(status_code=500, detail=f"无法打开视频文件: {video_path}")
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            raise HTTPException(status_code=500, detail="无法读取视频帧")
        
        max_width = 400
        if frame.shape[1] > max_width:
            scale = max_width / frame.shape[1]
            frame = cv2.resize(frame, None, fx=scale, fy=scale)
        
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return ExtractFrameResponse(
            code=200,
            message="首帧提取成功",
            data={
                "frame_base64": f"data:image/jpeg;base64,{frame_base64}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提取首帧失败: {e}")
        raise HTTPException(status_code=500, detail=f"提取首帧失败: {str(e)}")
