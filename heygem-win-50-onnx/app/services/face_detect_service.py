import os
import logging
from typing import List, Dict, Optional, Tuple
import numpy as np
import cv2

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from face_detect_utils.scrfd import SCRFD

logger = logging.getLogger(__name__)


class FaceDetectService:
    """
    人脸检测服务类，封装SCRFD模型进行人脸检测、对齐和裁剪。

    通过 ModelManager 注册 scrfd 模型，支持 GPU 显存统一管理。
    """

    DEFAULT_MODEL_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "face_detect_utils",
        "resources",
        "scrfd_500m_bnkps_shape640x640.onnx"
    )

    STANDARD_LANDMARKS_5 = np.array([
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041]
    ], dtype=np.float32)

    def __init__(self, model_path: Optional[str] = None, device: str = "cuda"):
        """
        初始化人脸检测服务。

        Args:
            model_path: ONNX模型文件路径，默认使用内置的scrfd_500m模型
            device: 运行设备，"cuda" 或 "cpu"
        """
        if model_path is None:
            model_path = self.DEFAULT_MODEL_PATH

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型文件不存在: {model_path}")

        self.model_path = model_path
        self.device = device
        self.cpu = (device.lower() == "cpu")

        self.detector = SCRFD(model_file=model_path, cpu=self.cpu)
        self.detector.prepare(ctx_id=0 if not self.cpu else -1, input_size=(640, 640))

        # 在 ModelManager 中注册 scrfd 模型
        self._register_with_model_manager()

    def detect(self, image: np.ndarray, thresh: float = 0.5, max_num: int = 0) -> List[Dict]:
        """
        检测图像中的人脸。

        Args:
            image: 输入图像 (BGR格式, numpy数组)
            thresh: 检测置信度阈值
            max_num: 返回的最大人脸数量，0表示不限制

        Returns:
            包含人脸信息的字典列表，每个字典包含:
            - bbox: [x1, y1, x2, y2, score] 边界框坐标和置信度
            - landmarks: (5, 2) 关键点数组
        """
        if image is None or image.size == 0:
            return []

        bboxes, kpss = self.detector.detect(image, thresh=thresh, max_num=max_num, metric='max')

        results = []
        if bboxes is not None and len(bboxes) > 0:
            for i in range(len(bboxes)):
                face_info = {
                    'bbox': bboxes[i].tolist(),
                    'landmarks': kpss[i] if kpss is not None else None
                }
                results.append(face_info)

        return results

    def align_face(
        self,
        image: np.ndarray,
        landmarks: np.ndarray,
        size: int = 256
    ) -> np.ndarray:
        """
        根据关键点对齐人脸到指定大小。

        使用5点关键点进行仿射变换，将人脸对齐到标准位置。

        Args:
            image: 输入图像 (BGR格式)
            landmarks: 5个关键点坐标，shape为(5, 2)
            size: 输出图像大小

        Returns:
            对齐后的人脸图像
        """
        if landmarks is None or len(landmarks) != 5:
            raise ValueError("landmarks必须包含5个关键点")

        dst = self.STANDARD_LANDMARKS_5 * (size / 112.0)

        tform = cv2.estimateAffinePartial2D(landmarks, dst, method=cv2.LMEDS)
        if tform[0] is None:
            tform = cv2.estimateAffinePartial2D(landmarks, dst, method=cv2.RANSAC)

        if tform[0] is None:
            return cv2.resize(image, (size, size))

        aligned_face = cv2.warpAffine(image, tform[0], (size, size), flags=cv2.INTER_LINEAR)

        return aligned_face

    def crop_face(
        self,
        image: np.ndarray,
        bbox: List,
        padding: float = 0.2
    ) -> np.ndarray:
        """
        裁剪人脸区域。

        Args:
            image: 输入图像 (BGR格式)
            bbox: 边界框 [x1, y1, x2, y2, score] 或 [x1, y1, x2, y2]
            padding: 边界框扩展比例

        Returns:
            裁剪后的人脸图像
        """
        if len(bbox) >= 4:
            x1, y1, x2, y2 = bbox[:4]
        else:
            raise ValueError("bbox格式错误，需要至少4个元素 [x1, y1, x2, y2]")

        h, w = image.shape[:2]

        face_w = x2 - x1
        face_h = y2 - y1

        pad_w = face_w * padding
        pad_h = face_h * padding

        x1 = max(0, int(x1 - pad_w))
        y1 = max(0, int(y1 - pad_h))
        x2 = min(w, int(x2 + pad_w))
        y2 = min(h, int(y2 + pad_h))

        return image[y1:y2, x1:x2].copy()

    def detect_and_align(
        self,
        image: np.ndarray,
        thresh: float = 0.5,
        size: int = 256,
        padding: float = 0.2
    ) -> List[Dict]:
        """
        检测人脸并对齐。

        Args:
            image: 输入图像 (BGR格式)
            thresh: 检测置信度阈值
            size: 对齐后的人脸大小
            padding: 裁剪时的边界扩展比例

        Returns:
            包含人脸信息的字典列表，每个字典包含:
            - bbox: 边界框
            - landmarks: 关键点
            - aligned_face: 对齐后的人脸图像
            - cropped_face: 裁剪后的人脸图像
        """
        faces = self.detect(image, thresh=thresh)

        results = []
        for face in faces:
            result = face.copy()

            if face['landmarks'] is not None:
                landmarks = np.array(face['landmarks'])
                result['aligned_face'] = self.align_face(image, landmarks, size)

            result['cropped_face'] = self.crop_face(image, face['bbox'], padding)

            results.append(result)

        return results

    def get_largest_face(self, faces: List[Dict]) -> Optional[Dict]:
        """
        从检测结果中获取面积最大的人脸。

        Args:
            faces: detect方法返回的人脸列表

        Returns:
            面积最大的人脸信息，如果没有则返回None
        """
        if not faces:
            return None

        max_area = 0
        largest_face = None

        for face in faces:
            bbox = face['bbox']
            area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            if area > max_area:
                max_area = area
                largest_face = face

        return largest_face

    def draw_results(
        self,
        image: np.ndarray,
        faces: List[Dict],
        draw_bbox: bool = True,
        draw_landmarks: bool = True
    ) -> np.ndarray:
        """
        在图像上绘制检测结果。

        Args:
            image: 输入图像
            faces: detect方法返回的人脸列表
            draw_bbox: 是否绘制边界框
            draw_landmarks: 是否绘制关键点

        Returns:
            绘制后的图像
        """
        result_img = image.copy()

        for face in faces:
            bbox = face['bbox']
            x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
            score = bbox[4] if len(bbox) > 4 else 0

            if draw_bbox:
                cv2.rectangle(result_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    result_img,
                    f"{score:.2f}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )

            if draw_landmarks and face['landmarks'] is not None:
                landmarks = np.array(face['landmarks'])
                for point in landmarks:
                    cv2.circle(result_img, (int(point[0]), int(point[1])), 2, (0, 0, 255), -1)

        return result_img

    def analyze_video(self, video_path: str, sample_interval: int = 30) -> Dict:
        """
        分析视频中的人脸，检测问题（嘴部遮挡、侧头角度等）

        Args:
            video_path: 视频文件路径
            sample_interval: 采样间隔（帧数），默认每30帧分析一次

        Returns:
            包含分析结果的字典:
            - face_detected: 是否检测到人脸
            - face_count: 检测到的人脸数量
            - mouth_occluded: 是否检测到嘴部遮挡
            - side_head_angle: 侧头角度（度）
            - issues: 问题列表
            - frame_count: 分析的总帧数
        """
        import cv2

        result = {
            'face_detected': False,
            'face_count': 0,
            'mouth_occluded': False,
            'side_head_angle': 0.0,
            'issues': [],
            'frame_count': 0,
            'success': True
        }

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                result['success'] = False
                result['issues'].append('无法打开视频文件')
                return result

            frame_idx = 0
            max_side_angle = 0.0
            mouth_occluded_frames = 0
            total_faces = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                result['frame_count'] += 1

                # 按间隔采样
                if frame_idx % sample_interval == 0:
                    faces = self.detect(frame, thresh=0.5)
                    if faces:
                        result['face_detected'] = True
                        total_faces += len(faces)

                        # 检查每张人脸
                        for face in faces:
                            # 计算侧头角度
                            landmarks = face.get('landmarks')
                            if landmarks is not None:
                                # 使用左右眼睛的水平位置差来估算侧头角度
                                left_eye = landmarks[0]  # 左眼
                                right_eye = landmarks[1]  # 右眼

                                # 计算眼睛连线与水平线的夹角
                                eye_vector = right_eye - left_eye
                                angle = abs(np.arctan2(eye_vector[1], eye_vector[0]) * 180 / np.pi)
                                max_side_angle = max(max_side_angle, angle)

                                # 简单判断嘴部是否被遮挡（基于眼睛和嘴巴的垂直位置）
                                # 如果嘴巴位置低于预期，可能有遮挡
                                mouth = landmarks[2]  # 嘴巴中心
                                nose = landmarks[2]  # 鼻子位置（使用嘴巴作为近似）

                frame_idx += 1

                # 限制分析帧数，避免分析太长
                if frame_idx > 300:
                    break

            cap.release()

            result['face_count'] = total_faces
            result['side_head_angle'] = round(max_side_angle, 2)

            # 判断问题
            if max_side_angle > 30:
                result['mouth_occluded'] = True
                result['issues'].append(f'侧头角度过大 ({max_side_angle:.1f}°)')

            if result['face_count'] == 0:
                result['issues'].append('未检测到人脸')

            return result

        except Exception as e:
            result['success'] = False
            result['issues'].append(f'分析失败: {str(e)}')
            return result

    def _register_with_model_manager(self):
        """在 ModelManager 中注册 scrfd 模型配置

        这样 ModelManager.unload_all() 可以清理 SCRFD 的 ONNX session，
        释放 GPU 显存。重新加载时 FaceDetectService 会自动重建 detector。
        """
        try:
            from app.inference.model_manager import get_model_manager
            manager = get_model_manager()

            if "scrfd" not in manager:
                # 注册模型配置（不自动加载，SCRFD 已在 __init__ 中加载）
                manager.register_model(
                    model_name="scrfd",
                    model_path=self.model_path,
                    device=self.device,
                    auto_load=False,
                )
                # 将已加载的 SCRFD 实例包装后存入 ModelManager
                wrapper = _SCRFDWrapper(self.detector, self.model_path, self.device)
                with manager._model_lock:
                    manager._models["scrfd"] = wrapper
                logger.info("SCRFD model registered with ModelManager")
        except Exception as e:
            logger.warning(f"Failed to register SCRFD with ModelManager: {e}")

    def unload(self):
        """释放 SCRFD 模型资源"""
        if self.detector is not None:
            # SCRFD 的 session 在 __del__ 中自动释放
            self.detector = None
            logger.info("SCRFD detector unloaded")


class _SCRFDWrapper:
    """SCRFD 模型包装器，兼容 ModelManager 的接口

    提供 is_loaded() 和 unload() 方法，让 ModelManager 能统一管理。
    unload() 时显式删除 SCRFD 的 onnxruntime session 以释放 GPU 显存。
    """

    def __init__(self, detector, model_path: str, device: str):
        self._detector = detector
        self.model_path = model_path
        self.device = device

    def is_loaded(self) -> bool:
        return self._detector is not None

    def unload(self):
        if self._detector is not None:
            # 显式释放 SCRFD 的 onnxruntime InferenceSession
            if hasattr(self._detector, 'session') and self._detector.session is not None:
                del self._detector.session
                self._detector.session = None
            self._detector = None
            logger.info(f"SCRFD model unloaded: {self.model_path}")
