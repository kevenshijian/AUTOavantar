"""
GET `/` 兼容接口 — 兼容现有 HeyGemClient 的请求格式

编排完整推理流程：
WeNet BNF 特征 → 视频帧 → 人脸检测 → DINet 批量推理 → 视频合成

技术方案参考：4 API 设计 → AC-001, AC-002
"""
import os
import uuid
import logging
import traceback
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class CompatEndpoint:
    """兼容接口的业务逻辑类，方便测试"""

    def __init__(self, settings=None):
        self._settings = settings
        self._services = None  # 缓存服务实例，避免每次请求重建（GPU 显存泄漏）

    @property
    def settings(self):
        if self._settings is None:
            from app.config import get_settings
            self._settings = get_settings()
        return self._settings

    def _get_services(self) -> dict:
        """获取或初始化推理服务（单例缓存）

        避免每次请求重新创建 ONNX InferenceSession，
        否则 GPU 显存会因旧 session 未释放而耗尽。
        """
        if self._services is not None:
            return self._services

        from app.services.video_service import VideoService
        from app.services.audio_service import AudioService
        from app.services.face_detect_service import FaceDetectService
        from app.services.dinet_service import DINetService
        from app.services.wenet_service import WenetService

        settings = self.settings

        wenet_service = WenetService(
            config_path=str(Path(settings.WENET_CONFIG)),
            model_path=str(Path(settings.WENET_MODEL)),
            device=settings.WENET_DEVICE,
        )
        audio_service = AudioService(device=settings.DEVICE, wenet_service=wenet_service)
        video_service = VideoService()
        scrfd_model_path = str(settings.SCRFD_MODEL_DIR / settings.SCRFD_MODEL)
        face_detect_service = FaceDetectService(model_path=scrfd_model_path, device=settings.DEVICE)
        dinet_model_path = str(settings.DINET_MODEL_DIR / settings.DINET_MODEL)
        dinet_service = DINetService(model_path=dinet_model_path, device=settings.DEVICE, batch_size=settings.BATCH_SIZE, inference_mode="inference")

        self._services = {
            "wenet": wenet_service,
            "audio": audio_service,
            "video": video_service,
            "face_detect": face_detect_service,
            "dinet": dinet_service,
        }
        return self._services

    def _validate_params(
        self,
        video_file: str,
        audio_file: str,
        ifface: str = "false",
        face_id: int = 0,
        steps: int = 16,
    ) -> dict:
        """验证并规范化请求参数

        Returns:
            验证后的参数字典

        Raises:
            ValueError: 参数格式错误
            FileNotFoundError: 文件不存在
        """
        # 必填参数检查
        if not video_file:
            raise ValueError("video_file is required")
        if not audio_file:
            raise ValueError("audio_file is required")

        # 文件存在性检查
        if not os.path.exists(video_file):
            raise FileNotFoundError(f"Video file not found: {video_file}")
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        # face_id 校验
        if face_id not in (0, 1):
            raise ValueError(f"face_id must be 0 or 1, got {face_id}")

        # steps 范围限制 [1, 64]
        steps = max(1, min(64, steps))

        return {
            "video_file": video_file,
            "audio_file": audio_file,
            "ifface": ifface,
            "face_id": face_id,
            "steps": steps,
        }

    @staticmethod
    def _prepare_audio_feature(bn_features: np.ndarray) -> np.ndarray:
        """将 WeNet BNF 特征从 (T, 256) 转置为 ONNX 输入格式 (1, 256, T)

        Args:
            bn_features: WeNet BNF 特征 (T, 256)

        Returns:
            audio_feature: (1, 256, T) 供 DINet ONNX 输入
        """
        return bn_features.T[np.newaxis, :, :].astype(np.float32)

    @staticmethod
    def _compute_frame_audio_map(num_frames: int, num_audio_features: int) -> list:
        """计算帧到音频特征的映射索引范围 [start, end)

        Args:
            num_frames: 视频帧数
            num_audio_features: 音频特征帧数

        Returns:
            长度为 num_frames 的列表，每个元素是 [start, end) 范围
        """
        frame_to_audio = []
        audio_per_frame = num_audio_features / num_frames
        for i in range(num_frames):
            start = int(i * audio_per_frame)
            end = int((i + 1) * audio_per_frame)
            start = max(0, start)
            end = min(num_audio_features, end)
            if start >= end:
                end = start + 1
                end = min(num_audio_features, end)
            frame_to_audio.append([start, end])
        return frame_to_audio

    def _generate_output_path(self) -> str:
        """生成唯一的输出视频路径"""
        result_dir = Path(self.settings.RESULT_DIR)
        result_dir.mkdir(parents=True, exist_ok=True)
        filename = f"result_{uuid.uuid4().hex[:8]}.mp4"
        return str(result_dir / filename)

    def process_request(
        self,
        video_file: str,
        audio_file: str,
        ifface: str = "false",
        face_id: int = 0,
        steps: int = 16,
    ) -> dict:
        """执行完整的数字人视频生成流程

        Returns:
            {"status": "success", "output_video_url": "...", "message": "..."}
            或
            {"status": "error", "message": "..."}
        """
        try:
            # 1. 参数验证
            params = self._validate_params(video_file, audio_file, ifface, face_id, steps)
            logger.info(f"Processing request: video={params['video_file']}, audio={params['audio_file']}")

            # 2. 获取服务（单例缓存，避免重复创建 ONNX session）
            services = self._get_services()
            audio_service = services["audio"]
            video_service = services["video"]
            face_detect_service = services["face_detect"]
            dinet_service = services["dinet"]
            steps = params["steps"]

            # 2a. 更新 DINet batch_size
            if dinet_service.batch_size != steps:
                dinet_service.batch_size = steps

            # 3. 提取音频特征
            logger.info("Extracting audio features...")
            bn_features = audio_service.extract_wenet_features(params["audio_file"])
            logger.info(f"Audio features: shape={bn_features.shape}")

            # 4. 读取视频帧
            logger.info("Reading video frames...")
            frames, fps, (width, height) = video_service.read_video_frames(params["video_file"])
            logger.info(f"Video: {len(frames)} frames, {fps}fps, {width}x{height}")

            # 5. 加载模板（从视频同一目录查找 face.pt）
            template_path = self._find_template(params["video_file"])
            if template_path:
                dinet_service.load_template(template_path)
                logger.info(f"Template loaded: {template_path}")

            # 6. 逐帧处理
            num_frames = len(frames)
            num_audio_features = bn_features.shape[0]
            frame_to_audio = self._compute_frame_audio_map(num_frames, num_audio_features)

            processed_frames = []
            batch_face_data = []
            batch_audio_indices = []
            batch_original_frames = []
            batch_bboxes = []

            for i, frame in enumerate(frames):
                faces = face_detect_service.detect(frame)

                if faces:
                    if face_id < len(faces):
                        face = faces[face_id]
                    else:
                        face = face_detect_service.get_largest_face(faces) if len(faces) > 1 else faces[0]

                    cropped = face_detect_service.crop_face(frame, face["bbox"], padding=0.2)

                    cropped_resized = cv2.resize(cropped, (dinet_service.img_size, dinet_service.img_size))

                    face_data = dinet_service.preprocess_frame(cropped_resized, None)
                    batch_face_data.append(face_data)
                    batch_audio_indices.append(frame_to_audio[i])
                    batch_original_frames.append(frame.copy())
                    batch_bboxes.append(face["bbox"])
                else:
                    processed_frames.append(frame)

                if len(batch_face_data) >= steps:
                    self._process_batch(
                        dinet_service, bn_features, batch_face_data,
                        batch_audio_indices, processed_frames,
                        batch_original_frames, batch_bboxes
                    )
                    batch_face_data = []
                    batch_audio_indices = []
                    batch_original_frames = []
                    batch_bboxes = []

            if batch_face_data:
                self._process_batch(
                    dinet_service, bn_features, batch_face_data,
                    batch_audio_indices, processed_frames,
                    batch_original_frames, batch_bboxes
                )

            # 7. 合成视频
            output_path = self._generate_output_path()
            logger.info(f"Creating output video: {output_path}")
            video_service.create_video_from_frames(
                processed_frames, params["audio_file"], output_path, fps=fps
            )

            # 8. 返回结果
            output_video_url = output_path
            logger.info(f"Video generated successfully: {output_video_url}")

            return {
                "status": "success",
                "output_video_url": output_video_url,
                "message": "Video generated successfully",
            }

        except (ValueError, FileNotFoundError) as e:
            logger.warning(f"Request validation error: {e}")
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"Processing failed: {e}\n{traceback.format_exc()}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    def _process_batch(
        dinet_service, bn_features, batch_face_data,
        batch_audio_indices, processed_frames,
        batch_original_frames, batch_bboxes
    ):
        """执行批量推理并将生成的面部贴回原始帧

        如果批量推理因 CUDA OOM 失败，自动降级为逐帧推理。

        Args:
            dinet_service: DINetService 实例
            bn_features: WeNet BNF 特征 (T, 256)
            batch_face_data: 预处理后的帧数据列表
            batch_audio_indices: 每帧对应的音频特征范围 [start, end)
            processed_frames: 已处理帧列表（输出）
            batch_original_frames: 原始帧列表
            batch_bboxes: 人脸边界框列表
        """
        import cv2

        batch_audio = []
        for idx_range in batch_audio_indices:
            start, end = idx_range
            audio_slice = bn_features[start:end]
            batch_audio.append(audio_slice)

        try:
            results = dinet_service.inference_batch(batch_audio, batch_face_data)
            for i, result in enumerate(results):
                original_frame = batch_original_frames[i]
                bbox = batch_bboxes[i]
                composed = CompatEndpoint._compose_face_to_frame(result, original_frame, bbox)
                processed_frames.append(composed)
            return
        except Exception as e:
            logger.warning(f"Batch inference failed (batch_size={len(batch_face_data)}): {e}")
            try:
                import gc
                gc.collect()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                except (ImportError, OSError):
                    pass
            except Exception:
                pass

        if len(batch_face_data) > 1:
            logger.info(f"Retrying with single-frame inference for {len(batch_face_data)} frames")
            for i in range(len(batch_face_data)):
                try:
                    results = dinet_service.inference_batch(
                        [batch_audio[i]], [batch_face_data[i]]
                    )
                    for j, result in enumerate(results):
                        original_frame = batch_original_frames[i]
                        bbox = batch_bboxes[i]
                        composed = CompatEndpoint._compose_face_to_frame(result, original_frame, bbox)
                        processed_frames.append(composed)
                    try:
                        import gc
                        gc.collect()
                    except Exception:
                        pass
                except Exception as e2:
                    logger.error(f"Single-frame inference also failed: {e2}")
                    processed_frames.append(batch_original_frames[i])
        else:
            for original_frame in batch_original_frames:
                processed_frames.append(original_frame)

    @staticmethod
    def _compose_face_to_frame(
        generated_face: np.ndarray,
        original_frame: np.ndarray,
        bbox: list,
        padding_ratio: float = 0.2
    ) -> np.ndarray:
        """将生成的面部图像贴回原始帧

        Args:
            generated_face: DINet 生成的面部图像 (H, W, 3) BGR
            original_frame: 原始视频帧 (H, W, 3) BGR
            bbox: 人脸边界框 [x1, y1, x2, y2, score] 或 [x1, y1, x2, y2]
            padding_ratio: 边界框扩展比例，需与裁剪时一致

        Returns:
            合成后的完整帧 (H, W, 3) BGR
        """
        import cv2

        if len(bbox) >= 4:
            x1, y1, x2, y2 = bbox[:4]
        else:
            return original_frame.copy()

        h, w = original_frame.shape[:2]
        face_w = x2 - x1
        face_h = y2 - y1

        pad_w = face_w * padding_ratio
        pad_h = face_h * padding_ratio

        crop_x1 = max(0, int(x1 - pad_w))
        crop_y1 = max(0, int(y1 - pad_h))
        crop_x2 = min(w, int(x2 + pad_w))
        crop_y2 = min(h, int(y2 + pad_h))

        crop_w = crop_x2 - crop_x1
        crop_h = crop_y2 - crop_y1

        result = original_frame.copy()

        if generated_face.shape[0] != crop_h or generated_face.shape[1] != crop_w:
            generated_face = cv2.resize(generated_face, (crop_w, crop_h))

        result[crop_y1:crop_y2, crop_x1:crop_x2] = generated_face

        return result

    @staticmethod
    def _find_template(video_file: str) -> Optional[str]:
        """查找与视频同目录的模板文件 face.pt"""
        video_dir = os.path.dirname(video_file)
        # 查找视频同目录和上级 face_cache 目录
        candidates = [
            os.path.join(video_dir, "face.pt"),
            os.path.join(video_dir, "..", "face_cache", "DW.pt"),
        ]
        for candidate in candidates:
            candidate = os.path.normpath(candidate)
            if os.path.exists(candidate):
                return candidate
        return None


# 单例缓存，避免每次请求创建新实例导致 GPU 显存泄漏
_compat_endpoint_instance: Optional[CompatEndpoint] = None


def get_compat_endpoint() -> CompatEndpoint:
    global _compat_endpoint_instance
    if _compat_endpoint_instance is None:
        _compat_endpoint_instance = CompatEndpoint()
    return _compat_endpoint_instance


@router.get("/")
async def compat_generate_video(
    video_file: str = Query(..., description="模板视频文件路径"),
    audio_file: str = Query(..., description="音频文件路径"),
    ifface: str = Query("false", description="是否使用原始参数模式"),
    face_id: int = Query(0, description="合成面部索引（0 或 1）"),
    steps: int = Query(16, description="推理批次大小"),
):
    """兼容现有 HeyGemClient 的数字人视频生成接口

    GET /?video_file=/path/video.mp4&audio_file=/path/audio.wav&ifface=false&face_id=0&steps=16
    """
    endpoint = get_compat_endpoint()

    # 先做参数验证（返回 400 错误）
    try:
        endpoint._validate_params(video_file, audio_file, ifface, face_id, steps)
    except (ValueError, FileNotFoundError) as e:
        status_code = 400
        return JSONResponse(
            status_code=status_code,
            content={"status": "error", "message": str(e)}
        )

    # 执行推理
    result = endpoint.process_request(video_file, audio_file, ifface, face_id, steps)

    if result["status"] == "error":
        status_code = 500
        # 区分验证错误和推理错误
        if "not found" in result["message"].lower():
            status_code = 400
        return JSONResponse(
            status_code=status_code,
            content=result
        )

    return JSONResponse(status_code=200, content=result)


# 导出路由
compat_router = router
