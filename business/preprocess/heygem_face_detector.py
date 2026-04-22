"""
HeyGem 兼容的面部检测模块
使用与 HeyGem 相同的 SCRFD 模型进行面部检测
"""

import os
import sys
import logging
import numpy as np
import cv2
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 添加 HeyGem 路径到 sys.path
# 当前文件: business/preprocess/heygem_face_detector.py
# 项目根目录: D:/AI/AUTOavantar
# HeyGem 目录: D:/AI/AUTOavantar/heygem-win-50-onnx
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CURRENT_DIR)  # business
_PROJECT_ROOT = os.path.dirname(_PROJECT_ROOT)  # AUTOavantar (项目根)
HEYGEM_PATH = os.path.join(_PROJECT_ROOT, "heygem-win-50-onnx")

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
class HeyGemFaceResult:
    """HeyGem 格式的面部检测结果"""
    bbox: List[float]  # [x1, y1, x2, y2, score]
    landmarks: np.ndarray  # (5, 2) 关键点
    face_id: int  # 人脸序号


class HeyGemFaceDetector:
    """
    使用 SCRFD 模型的面部检测器
    与 HeyGem 内部使用的检测器完全一致
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        use_gpu: bool = True,
        input_size: Tuple[int, int] = (640, 640)
    ):
        """
        初始化 SCRFD 面部检测器

        Args:
            model_path: SCRFD 模型路径
            use_gpu: 是否使用 GPU
            input_size: 输入图像大小
        """
        self.model_path = model_path
        self.use_gpu = use_gpu
        self.input_size = input_size
        self.detector = None
        self._init_detector()

    def _init_detector(self):
        """初始化 SCRFD 检测器"""
        try:
            from face_detect_utils.scrfd import SCRFD

            # 查找模型文件
            if self.model_path is None:
                possible_paths = [
                    os.path.join(HEYGEM_PATH, "face_detect_utils", "resources", "scrfd_500m_bnkps_shape640x640.onnx"),
                    os.path.join(HEYGEM_PATH, "face_detect_utils", "resources", "scrfd_10g_bnkps.onnx"),
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        self.model_path = path
                        break

            if self.model_path is None or not os.path.exists(self.model_path):
                logger.warning(f"SCRFD 模型文件不存在: {self.model_path}")
                return

            logger.info(f"加载 SCRFD 模型: {self.model_path}")

            # 初始化检测器
            cpu = not self.use_gpu
            self.detector = SCRFD(model_file=self.model_path, cpu=cpu)
            self.detector.prepare(ctx_id=0 if self.use_gpu else -1, input_size=self.input_size)

            logger.info("SCRFD 面部检测器初始化成功")

        except ImportError as e:
            logger.warning(f"无法导入 SCRFD: {e}")
            self.detector = None
        except Exception as e:
            logger.error(f"SCRFD 初始化失败: {e}")
            self.detector = None

    def detect_faces(
        self,
        image: np.ndarray,
        thresh: float = 0.5,
        max_num: int = 1
    ) -> List[HeyGemFaceResult]:
        """
        检测图像中的人脸

        Args:
            image: 输入图像 (BGR 格式)
            thresh: 检测置信度阈值
            max_num: 最大检测数量

        Returns:
            人脸检测结果列表
        """
        if self.detector is None:
            logger.warning("SCRFD 检测器未初始化")
            return []

        if image is None or image.size == 0:
            return []

        try:
            # 使用 SCRFD 检测
            bboxes, kpss = self.detector.detect(
                image,
                thresh=thresh,
                max_num=max_num,
                metric='max'
            )

            results = []

            if bboxes is not None and len(bboxes) > 0:
                for i in range(len(bboxes)):
                    # 提取边界框
                    bbox = bboxes[i].tolist()

                    # 提取关键点
                    if kpss is not None and len(kpss) > i:
                        landmarks = kpss[i]  # shape: (5, 2)
                    else:
                        landmarks = None

                    # 验证关键点
                    if landmarks is None:
                        continue

                    # 确保关键点是正确的形状
                    if landmarks.shape != (5, 2):
                        logger.warning(f"关键点形状错误: {landmarks.shape}")
                        continue

                    result = HeyGemFaceResult(
                        bbox=bbox,
                        landmarks=landmarks,
                        face_id=i
                    )
                    results.append(result)

            return results

        except Exception as e:
            logger.error(f"面部检测失败: {e}")
            return []

    def align_face(
        self,
        image: np.ndarray,
        landmarks: np.ndarray,
        output_size: int = 256
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        对齐面部到标准位置

        Args:
            image: 输入图像 (BGR 格式)
            landmarks: 5 点关键点
            output_size: 输出大小

        Returns:
            (对齐后的图像, 变换矩阵)
        """
        if landmarks is None or len(landmarks) != 5:
            logger.warning("关键点格式错误")
            return None, None

        try:
            # 转换关键点为 float32
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
                image,
                tform[0],
                (output_size, output_size),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0
            )

            return aligned, tform[0]

        except Exception as e:
            logger.error(f"面部对齐失败: {e}")
            return None, None

    def analyze_video(
        self,
        video_path: str,
        sample_interval: int = 30
    ) -> Dict[str, Any]:
        """
        分析视频中的人脸质量 (基于嘴唇完整性检测)

        核心逻辑:
        - 合格帧: 左右嘴角都能被检测到 + 鼻尖可见
        - 不合格帧: 缺少嘴角或严重侧脸
        """
        result = {
            'face_detected': False,
            'face_count': 0,
            'valid_lip_frames': 0,      # 嘴唇完整的帧
            'total_analyzed': 0,
            'missing_left_corner': 0,   # 缺少左嘴角
            'missing_right_corner': 0,  # 缺少右嘴角
            'missing_nose': 0,          # 缺少鼻尖
            'missing_both_corners': 0, # 两边嘴角都缺失
            'issues': [],
            'lip_visibility_ratios': [],
            'success': True
        }

        if not os.path.exists(video_path):
            result['success'] = False
            result['issues'].append('视频文件不存在')
            return result

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            result['success'] = False
            result['issues'].append('无法打开视频')
            return result

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 按间隔采样
            if frame_idx % sample_interval == 0:
                result['total_analyzed'] += 1

                faces = self.detect_faces(frame, thresh=0.5)

                if faces:
                    result['face_detected'] = True
                    result['face_count'] = max(result['face_count'], len(faces))

                    # 检查每个人脸
                    for face in faces:
                        landmarks = face.landmarks

                        # SCRFD 5 点: [左眼, 右眼, 鼻尖, 左嘴角, 右嘴角]
                        left_eye = landmarks[0]
                        right_eye = landmarks[1]
                        nose = landmarks[2]
                        left_corner = landmarks[3]   # 左嘴角
                        right_corner = landmarks[4]    # 右嘴角

                        # 检查各点是否存在 (坐标 > 0)
                        has_left_corner = left_corner[0] > 0 and left_corner[1] > 0
                        has_right_corner = right_corner[0] > 0 and right_corner[1] > 0
                        has_nose = nose[0] > 0 and nose[1] > 0

                        # 统计
                        if not has_left_corner:
                            result['missing_left_corner'] += 1
                        if not has_right_corner:
                            result['missing_right_corner'] += 1
                        if not has_nose:
                            result['missing_nose'] += 1
                        if not has_left_corner and not has_right_corner:
                            result['missing_both_corners'] += 1

                        # 嘴唇完整: 左右嘴角都可见 + 鼻尖可见
                        # 即使有轻微侧脸，只要嘴唇完整就可以
                        if has_left_corner and has_right_corner and has_nose:
                            result['valid_lip_frames'] += 1
                            # 计算嘴角水平位置差异 (用于判断侧脸程度)
                            lip_width = abs(right_corner[0] - left_corner[0])
                            result['lip_visibility_ratios'].append(1.0)

            frame_idx += 1

            # 限制分析帧数
            if frame_idx > 300:
                break

        cap.release()

        # 判断是否合格
        if result['total_analyzed'] > 0:
            valid_ratio = result['valid_lip_frames'] / result['total_analyzed']
            result['valid_lip_ratio'] = valid_ratio

            logger.info(f"嘴唇检测分析: 有效帧 {result['valid_lip_frames']}/{result['total_analyzed']} ({valid_ratio:.1%})")
            logger.info(f"  - 缺少左嘴角: {result['missing_left_corner']}")
            logger.info(f"  - 缺少右嘴角: {result['missing_right_corner']}")
            logger.info(f"  - 缺少鼻尖: {result['missing_nose']}")

            # 判断问题
            if result['missing_both_corners'] > result['total_analyzed'] * 0.3:
                result['issues'].append(f'大量帧无法检测到嘴唇 ({result["missing_both_corners"]}/{result["total_analyzed"]})')

            if valid_ratio < 0.5:
                result['issues'].append(f'有效嘴唇帧比例过低: {valid_ratio:.1%}')

        return result


def create_heygem_detector(use_gpu: bool = True) -> HeyGemFaceDetector:
    """创建 HeyGem 面部检测器的便捷函数"""
    return HeyGemFaceDetector(use_gpu=use_gpu)


def quick_analyze_video(video_path: str) -> Dict[str, Any]:
    """
    快速分析视频人脸

    Args:
        video_path: 视频路径

    Returns:
        分析结果
    """
    detector = HeyGemFaceDetector(use_gpu=False)
    return detector.analyze_video(video_path, sample_interval=30)


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    # 创建检测器
    detector = HeyGemFaceDetector(use_gpu=False)

    # 测试检测 (需要提供测试图像路径)
    test_img_path = "test.jpg"
    if os.path.exists(test_img_path):
        img = cv2.imread(test_img_path)
        faces = detector.detect_faces(img)

        print(f"检测到 {len(faces)} 张人脸")
        for face in faces:
            print(f"  人脸 {face.face_id}: bbox={face.bbox[:4]}, landmarks shape={face.landmarks.shape}")
    else:
        print(f"测试图像不存在: {test_img_path}")
        print("检测器初始化完成，可以处理视频")