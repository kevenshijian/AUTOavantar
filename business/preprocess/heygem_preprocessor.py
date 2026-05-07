"""
HeyGem 兼容的视频面部预处理模块
使用 SCRFD 模型进行面部检测，与 HeyGem 内部检测器一致
"""

import logging
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import os
import sys

logger = logging.getLogger(__name__)

# 添加 HeyGem 路径到 sys.path
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CURRENT_DIR)  # business
_PROJECT_ROOT = os.path.dirname(_PROJECT_ROOT)  # AUTOavantar (项目根)
HEYGEM_PATH = os.path.join(_PROJECT_ROOT, "Portrait")

if HEYGEM_PATH not in sys.path:
    sys.path.insert(0, HEYGEM_PATH)

logger.info(f"添加 HeyGem 路径: {HEYGEM_PATH}")

# HeyGem 标准 5 点关键点 (112x112 标准)
HEYGEM_STANDARD_LANDMARKS_5 = np.array([
    [38.2946, 51.6963],   # 左眼
    [73.5318, 51.5014],   # 右眼
    [56.0252, 71.7366],   # 鼻尖
    [41.5493, 92.3655],   # 左嘴角
    [70.7299, 92.2041]    # 右嘴角
], dtype=np.float32)


@dataclass
class FaceAlignmentResult:
    """面部对齐结果"""
    frame_index: int
    success: bool
    aligned_face: Optional[np.ndarray] = None
    transform_matrix: Optional[np.ndarray] = None
    face_bbox: Optional[Tuple[int, int, int, int]] = None
    landmarks_5: Optional[np.ndarray] = None  # 使用 numpy array
    error: Optional[str] = None


@dataclass
class HeyGemPreprocessResult:
    """HeyGem 预处理结果"""
    video_path: str
    output_path: str
    total_frames: int
    processed_frames: int
    failed_frames: int
    is_qualified: bool
    reasons: List[str]
    face_size_ratio: float


class HeyGemFacePreprocessor:
    """
    HeyGem 兼容的面部预处理器
    使用与 HeyGem 相同的 SCRFD 模型
    """

    # 面部大小阈值
    MIN_FACE_RATIO = 0.15
    MAX_FACE_RATIO = 0.7

    def __init__(self, aligned_size: int = 256):
        self.aligned_size = aligned_size
        self.detector = None
        self._init_detector()

    def _init_detector(self):
        """初始化 SCRFD 检测器"""
        try:
            from face_detect_utils.scrfd import SCRFD

            # 查找模型文件
            possible_paths = [
                os.path.join(HEYGEM_PATH, "face_detect_utils", "resources", "scrfd_500m_bnkps_shape640x640.onnx"),
                os.path.join(HEYGEM_PATH, "face_detect_utils", "resources", "scrfd_10g_bnkps.onnx"),
            ]

            model_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    model_path = path
                    break

            if model_path is None:
                logger.warning("SCRFD 模型文件不存在")
                return

            logger.info(f"加载 SCRFD 模型: {model_path}")

            # 初始化检测器 (使用 CPU)
            self.detector = SCRFD(model_file=model_path, cpu=True)
            self.detector.prepare(ctx_id=-1, input_size=(640, 640))

            logger.info("SCRFD 面部检测器初始化成功")

        except ImportError as e:
            logger.warning(f"无法导入 SCRFD: {e}")
            self.detector = None
        except Exception as e:
            logger.error(f"SCRFD 初始化失败: {e}")
            self.detector = None

    def detect_and_extract_5_points(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        检测面部并提取 5 点关键点 (numpy array 格式)

        Args:
            frame: 输入帧 (BGR 格式)

        Returns:
            5 点关键点 (5, 2) numpy array 或 None
        """
        if self.detector is None:
            return None

        try:
            bboxes, kpss = self.detector.detect(frame, thresh=0.5, max_num=1, metric='max')

            if bboxes is None or len(bboxes) == 0:
                return None

            # 返回第一张人脸的 5 点关键点
            if kpss is not None and len(kpss) > 0:
                return kpss[0]  # shape: (5, 2)

            return None

        except Exception as e:
            logger.debug(f"关键点提取失败: {e}")
            return None

    def align_face(
        self,
        frame: np.ndarray,
        landmarks: np.ndarray,
        output_size: int = 256
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        对齐面部到标准位置

        Args:
            frame: 输入帧 (BGR 格式)
            landmarks: 5 点关键点 (numpy array, shape: (5, 2))
            output_size: 输出大小

        Returns:
            (对齐后的图像, 变换矩阵)
        """
        if landmarks is None or len(landmarks) != 5:
            logger.warning("关键点格式错误")
            return None, None

        try:
            src_points = np.array(landmarks, dtype=np.float32)

            # 目标关键点 (缩放到 output_size)
            scale = output_size / 112.0
            dst_points = HEYGEM_STANDARD_LANDMARKS_5 * scale

            # 计算仿射变换矩阵
            tform = cv2.estimateAffinePartial2D(src_points, dst_points, method=cv2.LMEDS)

            if tform[0] is None:
                tform = cv2.estimateAffinePartial2D(
                    src_points, dst_points, method=cv2.RANSAC
                )

            if tform[0] is None:
                logger.warning("仿射变换计算失败")
                return None, None

            # 应用变换
            aligned = cv2.warpAffine(
                frame,
                tform[0],
                (output_size, output_size),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0
            )

            return aligned, tform[0]

        except Exception as e:
            logger.debug(f"面部对齐失败: {e}")
            return None, None

    def process_frame(
        self,
        frame: np.ndarray,
        frame_idx: int
    ) -> FaceAlignmentResult:
        """
        处理单帧 - 基于嘴唇完整性检测

        合格标准: 左右嘴角都能被检测到 + 鼻尖可见
        """
        result = FaceAlignmentResult(
            frame_index=frame_idx,
            success=False
        )

        # 检测面部并提取关键点
        landmarks_5 = self.detect_and_extract_5_points(frame)

        if landmarks_5 is None:
            result.error = "未检测到人脸"
            return result

        result.landmarks_5 = landmarks_5

        # SCRFD 5 点: [左眼, 右眼, 鼻尖, 左嘴角, 右嘴角]
        left_corner = landmarks_5[3]   # 左嘴角
        right_corner = landmarks_5[4]  # 右嘴角
        nose = landmarks_5[2]          # 鼻尖

        # 检查各点是否存在
        has_left = left_corner[0] > 0 and left_corner[1] > 0
        has_right = right_corner[0] > 0 and right_corner[1] > 0
        has_nose = nose[0] > 0 and nose[1] > 0

        # 嘴唇完整: 左右嘴角都可见 + 鼻尖可见
        if not (has_left and has_right and has_nose):
            missing = []
            if not has_left:
                missing.append("左嘴角")
            if not has_right:
                missing.append("右嘴角")
            if not has_nose:
                missing.append("鼻尖")
            result.error = f"嘴唇不完整: {', '.join(missing)}"
            return result

        # 计算面部边界框
        x_coords = landmarks_5[:, 0]
        y_coords = landmarks_5[:, 1]
        min_x, max_x = int(x_coords.min()), int(x_coords.max())
        min_y, max_y = int(y_coords.min()), int(y_coords.max())
        face_bbox = (min_x, min_y, max_x - min_x, max_y - min_y)
        result.face_bbox = face_bbox

        # 对齐面部
        aligned_face, tform = self.align_face(frame, landmarks_5, self.aligned_size)

        if aligned_face is None:
            result.error = "面部对齐失败"
            return result

        result.success = True
        result.aligned_face = aligned_face
        result.transform_matrix = tform

        return result

    def process_video(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        check_interval: int = 1,
        skip_invalid: bool = True
    ) -> HeyGemPreprocessResult:
        """处理视频 - 面部对齐并生成新视频"""
        logger.info(f"开始 HeyGem 面部预处理 (SCRFD): {video_path}")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        if self.detector is None:
            raise RuntimeError("SCRFD 检测器未初始化")

        if output_path is None:
            output_path = video_path + ".aligned.mp4"

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"视频信息: {width}x{height}, {fps:.2f} FPS")

        out = cv2.VideoWriter(
            output_path,
            cv2.VideoWriter_fourcc(*'mp4v'),
            fps if fps > 0 else 25.0,
            (width, height)
        )

        total_frames = 0
        processed_frames = 0
        failed_frames = 0
        reasons = []
        last_tform = None
        face_size_ratio = 0.0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            total_frames += 1

            # 每隔 check_interval 帧重新检测和对齐
            if total_frames % check_interval == 1:
                # 进度输出
                if total_frames % max(1, height // 10) == 1 or check_interval > 1:
                    logger.info(f"面部对齐进度: {total_frames}/{height} 帧")

                result = self.process_frame(frame, total_frames - 1)

                if result.success:
                    last_tform = result.transform_matrix
                    processed_frames += 1
                    face_size_ratio = result.face_bbox[2] / width if result.face_bbox else 0
                else:
                    if skip_invalid:
                        failed_frames += 1
                        if result.error:
                            reasons.append(f"帧 {total_frames-1}: {result.error}")
                        continue
                    else:
                        if last_tform is None:
                            failed_frames += 1
                            continue

            # 应用对齐变换
            if last_tform is not None:
                try:
                    aligned_frame = cv2.warpAffine(
                        frame,
                        last_tform,
                        (width, height),
                        flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=0
                    )
                    out.write(aligned_frame)
                except Exception as e:
                    logger.debug(f"帧变换失败: {e}")
                    if not skip_invalid:
                        out.write(frame)
            else:
                if not skip_invalid:
                    out.write(frame)

        cap.release()
        out.release()

        # 判断是否合格
        success_ratio = processed_frames / total_frames if total_frames > 0 else 0
        is_qualified = success_ratio > 0.7 and processed_frames > 0

        if not is_qualified:
            if processed_frames == 0:
                reasons.insert(0, "无法检测到任何有效人脸")
            elif success_ratio <= 0.7:
                reasons.insert(0, f"有效帧比例过低: {success_ratio:.1%}")

        logger.info(
            f"视频预处理完成: {video_path} -> {output_path}, "
            f"处理 {processed_frames}/{total_frames} 帧, 脸宽比例: {face_size_ratio:.2%}"
        )

        return HeyGemPreprocessResult(
            video_path=video_path,
            output_path=output_path,
            total_frames=total_frames,
            processed_frames=processed_frames,
            failed_frames=failed_frames,
            is_qualified=is_qualified,
            reasons=reasons[:10],
            face_size_ratio=face_size_ratio
        )


def preprocess_for_heygem(
    video_path: str,
    output_path: Optional[str] = None
) -> HeyGemPreprocessResult:
    """便捷函数: 预处理视频使其符合 HeyGem 要求"""
    preprocessor = HeyGemFacePreprocessor()
    return preprocessor.process_video(video_path, output_path)


def quick_validate_heygem(video_path: str) -> Dict[str, Any]:
    """快速验证视频是否符合 HeyGem 要求"""
    preprocessor = HeyGemFacePreprocessor()

    if preprocessor.detector is None:
        return {
            "valid": False,
            "reason": "SCRFD 检测器未初始化",
            "face_detected": False
        }

    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return {
            "valid": False,
            "reason": "无法读取视频",
            "face_detected": False
        }

    # 检测一帧
    result = preprocessor.process_frame(frame, 0)

    return {
        "valid": result.success,
        "reason": result.error,
        "face_detected": result.landmarks_5 is not None,
        "face_bbox": result.face_bbox,
        "landmarks_5": result.landmarks_5.tolist() if result.landmarks_5 is not None else None
    }