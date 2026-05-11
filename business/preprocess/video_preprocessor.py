"""
视频预处理模块
实现视频面部检测、唇部检测、角度检测等预处理功能
"""

import logging
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import os
import platform
import subprocess

logger = logging.getLogger(__name__)


@dataclass
class FaceDetectionResult:
    """
    面部检测结果
    
    使用 HeyGem 嘴唇完整性标准 + 头部姿态角度限制判定有效性：
    - 左嘴角可见（坐标 > 0）
    - 右嘴角可见（坐标 > 0）
    - 鼻尖可见（坐标 > 0）
    - 上嘴唇可见（坐标 > 0）
    - 下嘴唇可见（坐标 > 0）
    - 偏航角 <= 45°
    - 俯仰角 <= 30°
    """
    frame_index: int
    has_face: bool
    face_bbox: Tuple[int, int, int, int]
    is_valid: bool = False
    reason: str = ""
    landmarks_5: Optional[List[List[float]]] = None
    yaw_angle: Optional[float] = None
    pitch_angle: Optional[float] = None


@dataclass
class VideoPreprocessResult:
    """视频预处理结果"""
    video_path: str
    total_frames: int
    valid_frames: int
    invalid_frames: int
    frame_results: List[FaceDetectionResult]
    valid_frame_paths: List[str]
    duration: float
    fps: float
    resolution: Tuple[int, int]
    is_qualified: bool = True
    reasons: List[str] = None

    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []


class VideoPreprocessor:
    """
    视频预处理器
    
    使用 HeyGem 嘴唇完整性标准 + 头部姿态角度限制检测面部有效性
    """
    
    YAW_THRESHOLD = 45.0
    PITCH_THRESHOLD = 30.0

    def __init__(
        self,
        temp_dir: str = "temp/preprocess"
    ):
        """
        初始化视频预处理器

        Args:
            temp_dir: 临时目录
        """
        self.temp_dir = temp_dir

        # 创建临时目录
        os.makedirs(temp_dir, exist_ok=True)

        # 尝试导入面部检测库
        self.face_detector = None
        self._init_face_detector()

    def _init_face_detector(self):
        """初始化面部检测器"""
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            # 优先检查项目根目录的models文件夹
            model_path = "models/face_landmarker.task"
            if not os.path.exists(model_path):
                # 检查绝对路径
                absolute_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models", "face_landmarker.task")
                if os.path.exists(absolute_path):
                    model_path = absolute_path
                else:
                    model_path = "tools/stream/onnx_models/face_landmarker.task"
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Face Landmarker 模型文件不存在: {model_path}")

            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE,
                num_faces=1,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.face_detector = vision.FaceLandmarker.create_from_options(options)
            self.mp_face_mesh = mp
            logger.info(f"已加载 MediaPipe FaceLandmarker 模型: {model_path}")
        except Exception as e:
            logger.warning(f"MediaPipe 不可用，将使用 OpenCV Haar 级联检测器: {e}")
            self.face_detector = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            self.mp_face_mesh = None

    def _get_video_rotation(self, video_path: str) -> int:
        """
        获取视频的旋转角度

        Args:
            video_path: 视频文件路径

        Returns:
            旋转角度 (0, 90, 180, 270)
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=rotation',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            if result.returncode == 0 and result.stdout.strip():
                rotation = int(result.stdout.strip())
                rotation = ((rotation % 360) + 360) % 360
                logger.info(f"检测到视频旋转角度: {rotation}°")
                return rotation
        except Exception as e:
            logger.debug(f"ffprobe 获取旋转失败: {e}")

        return 0

    def _rotate_frame(self, frame: np.ndarray, rotation: int) -> np.ndarray:
        """
        根据旋转角度旋转帧

        Args:
            frame: 输入帧
            rotation: 旋转角度 (0, 90, 180, 270)

        Returns:
            旋转后的帧
        """
        if rotation == 0 or frame is None:
            return frame

        if rotation == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif rotation == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        elif rotation == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        return frame

    def detect_faces(self, video_path: str) -> VideoPreprocessResult:
        """
        检测视频中的面部

        Args:
            video_path: 视频文件路径

        Returns:
            预处理结果
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        cap = cv2.VideoCapture(video_path)

        # 获取视频旋转角度
        rotation = self._get_video_rotation(video_path)

        # 获取视频信息
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0

        # 如果视频需要旋转 90 或 270 度，实际分辨率需要交换
        if rotation in (90, 270):
            width, height = height, width

        logger.info(
            f"开始处理视频: {video_path}, "
            f"总帧数: {total_frames}, FPS: {fps}, 分辨率: {width}x{height}, 旋转: {rotation}°"
        )

        frame_results: List[FaceDetectionResult] = []
        valid_frame_indices: List[int] = []

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 应用旋转
            frame = self._rotate_frame(frame, rotation)

            # 检测当前帧
            result = self._detect_face_in_frame(frame, frame_idx)

            if result.is_valid:
                valid_frame_indices.append(frame_idx)

            frame_results.append(result)
            frame_idx += 1

            # 进度日志
            if frame_idx % 100 == 0:
                logger.debug(f"已处理 {frame_idx}/{total_frames} 帧")

        cap.release()

        # 统计结果
        valid_frames = len(valid_frame_indices)
        invalid_frames = total_frames - valid_frames
        is_qualified = valid_frames > 0 and (valid_frames / total_frames) > 0.5

        reasons = []
        if invalid_frames > total_frames * 0.5:
            reasons.append("有效帧数不足 50%")
        if valid_frames == 0:
            reasons.append("未检测到有效人脸")

        result = VideoPreprocessResult(
            video_path=video_path,
            total_frames=total_frames,
            valid_frames=valid_frames,
            invalid_frames=invalid_frames,
            frame_results=frame_results,
            valid_frame_paths=valid_frame_indices,
            duration=duration,
            fps=fps,
            resolution=(width, height),
            is_qualified=is_qualified,
            reasons=reasons
        )

        logger.info(
            f"视频预处理完成: 有效帧 {valid_frames}/{total_frames}, "
            f"是否合格: {is_qualified}"
        )

        return result

    def process_video(self, input_path: str, output_path: str) -> bool:
        """
        处理视频，删除不合格帧

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径

        Returns:
            是否处理成功
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"视频文件不存在: {input_path}")

        # 检测面部，获取有效帧索引
        result = self.detect_faces(input_path)
        valid_frame_indices = result.valid_frame_paths

        if not valid_frame_indices:
            logger.warning("没有有效帧，无法处理视频")
            return False

        # 获取视频旋转角度
        rotation = self._get_video_rotation(input_path)

        # 读取输入视频
        cap = cv2.VideoCapture(input_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 如果视频需要旋转 90 或 270 度，输出分辨率需要交换
        if rotation in (90, 270):
            output_width, output_height = height, width
        else:
            output_width, output_height = width, height

        # 创建输出视频写入器
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(output_path, fourcc, fps, (output_width, output_height))

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 应用旋转
            frame = self._rotate_frame(frame, rotation)

            # 只写入有效帧
            if frame_idx in valid_frame_indices:
                out.write(frame)

            frame_idx += 1

        # 释放资源
        cap.release()
        out.release()

        logger.info(f"视频处理完成，输出路径: {output_path}")
        return True

    def _detect_face_in_frame(
        self,
        frame: np.ndarray,
        frame_idx: int
    ) -> FaceDetectionResult:
        """
        检测单帧中的面部
        
        使用 HeyGem 嘴唇完整性标准 + 头部姿态角度限制：
        - 左嘴角可见（坐标 > 0）
        - 右嘴角可见（坐标 > 0）
        - 上嘴唇可见（坐标 > 0）
        - 下嘴唇可见（坐标 > 0）
        - 偏航角 <= 45°
        - 俯仰角 <= 30°
        """
        result = FaceDetectionResult(
            frame_index=frame_idx,
            has_face=False,
            face_bbox=(0, 0, 0, 0),
            is_valid=False,
            landmarks_5=None
        )

        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            if hasattr(self.face_detector, 'detect'):
                import mediapipe as mp
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                results = self.face_detector.detect(mp_image)

                if results.face_landmarks:
                    landmarks = results.face_landmarks[0]

                    result.has_face = True
                    result.face_bbox = self._get_face_bbox_from_landmarks(frame, landmarks)
                    result.landmarks_5 = self._extract_5_point_landmarks(landmarks, frame.shape)

                    validation = self._validate_face_with_landmarks(landmarks, frame.shape)
                    result.is_valid = validation['is_valid']
                    result.yaw_angle = validation['yaw']
                    result.pitch_angle = validation['pitch']
                    if not validation['is_valid']:
                        result.reason = ", ".join(validation['reasons'])
                else:
                    result.reason = "未检测到人脸"
            elif hasattr(self.face_detector, 'process'):
                results = self.face_detector.process(rgb_frame)

                if results.multi_face_landmarks:
                    landmarks = results.multi_face_landmarks[0]
                    result.has_face = True
                    result.face_bbox = self._get_face_bbox(frame, landmarks)
                    result.landmarks_5 = self._extract_5_point_landmarks(landmarks, frame.shape)

                    validation = self._validate_face_with_landmarks(landmarks, frame.shape)
                    result.is_valid = validation['is_valid']
                    result.yaw_angle = validation['yaw']
                    result.pitch_angle = validation['pitch']
                    if not validation['is_valid']:
                        result.reason = ", ".join(validation['reasons'])
                else:
                    result.reason = "未检测到人脸"
            else:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_detector.detectMultiScale(gray, 1.3, 5)

                if len(faces) > 0:
                    result.has_face = True
                    result.face_bbox = tuple(faces[0])
                    result.is_valid = True
                    result.landmarks_5 = None
                else:
                    result.reason = "未检测到人脸"

        except Exception as e:
            logger.debug(f"帧 {frame_idx} 检测失败: {e}")
            result.reason = str(e)

        return result

    def _extract_5_point_landmarks(
        self,
        landmarks: Any,
        frame_shape: Tuple[int, int, int]
    ) -> List[List[float]]:
        """
        从 MediaPipe 478 点关键点提取 HeyGem 兼容的 5 点关键点。

        5 点顺序: [左眼, 右眼, 鼻尖, 左嘴角, 右嘴角]

        Args:
            landmarks: MediaPipe 关键点
            frame_shape: 帧形状 (h, w, c)

        Returns:
            5 点关键点列表 [[x1,y1], [x2,y2], [x3,y3], [x4,y4], [x5,y5]]
        """
        h, w = frame_shape[:2]

        # MediaPipe 关键点索引
        # 左眼中心: 取 133 和 33 的平均 (眼角)
        left_eye_x = (landmarks[133].x + landmarks[33].x) / 2 * w
        left_eye_y = (landmarks[133].y + landmarks[33].y) / 2 * h

        # 右眼中心: 取 362 和 263 的平均 (眼角)
        right_eye_x = (landmarks[362].x + landmarks[263].x) / 2 * w
        right_eye_y = (landmarks[362].y + landmarks[263].y) / 2 * h

        # 鼻尖: 使用索引 4 (鼻尖)
        nose_x = landmarks[4].x * w
        nose_y = landmarks[4].y * h

        # 左嘴角: 索引 61
        left_mouth_x = landmarks[61].x * w
        left_mouth_y = landmarks[61].y * h

        # 右嘴角: 索引 291
        right_mouth_x = landmarks[291].x * w
        right_mouth_y = landmarks[291].y * h

        return [
            [float(left_eye_x), float(left_eye_y)],
            [float(right_eye_x), float(right_eye_y)],
            [float(nose_x), float(nose_y)],
            [float(left_mouth_x), float(left_mouth_y)],
            [float(right_mouth_x), float(right_mouth_y)]
        ]

    def _get_face_bbox(
        self,
        frame: np.ndarray,
        landmarks: Any
    ) -> Tuple[int, int, int, int]:
        """从关键点获取面部边界框"""
        h, w = frame.shape[:2]

        # 简化：使用整个画面作为边界框
        return (0, 0, w, h)

    def _get_face_bbox_from_landmarks(
        self,
        frame: np.ndarray,
        landmarks: Any
    ) -> Tuple[int, int, int, int]:
        """从 MediaPipe Tasks API 关键点获取面部边界框"""
        h, w = frame.shape[:2]

        if not landmarks:
            return (0, 0, w, h)

        # 获取所有关键点的 x, y 坐标
        x_coords = [landmark.x * w for landmark in landmarks]
        y_coords = [landmark.y * h for landmark in landmarks]

        # 计算边界框
        min_x = int(min(x_coords))
        min_y = int(min(y_coords))
        max_x = int(max(x_coords))
        max_y = int(max(y_coords))

        # 添加一些边距
        padding = 10
        min_x = max(0, min_x - padding)
        min_y = max(0, min_y - padding)
        max_x = min(w, max_x + padding)
        max_y = min(h, max_y + padding)

        bbox_w = max_x - min_x
        bbox_h = max_y - min_y

        return (min_x, min_y, bbox_w, bbox_h)

    def _calculate_head_pose(
        self,
        landmarks: Any,
        frame_shape: Tuple[int, int, int]
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        计算头部姿态角度（偏航角和俯仰角）
        
        Args:
            landmarks: MediaPipe 478 点关键点
            frame_shape: 帧形状 (h, w, c)
        
        Returns:
            (yaw, pitch) 偏航角和俯仰角（度），计算失败返回 (None, None)
        """
        if landmarks is None:
            return None, None
        
        try:
            h, w = frame_shape[:2]
            
            model_points = np.array([
                (0.0, 0.0, 0.0),
                (0.0, -63.6, -12.5),
                (-43.3, 32.7, -26.0),
                (43.3, 32.7, -26.0),
                (-28.9, -28.9, -24.1),
                (28.9, -28.9, -24.1)
            ], dtype=np.float64)
            
            image_points = np.array([
                (landmarks[4].x * w, landmarks[4].y * h),
                (landmarks[152].x * w, landmarks[152].y * h),
                (landmarks[33].x * w, landmarks[33].y * h),
                (landmarks[263].x * w, landmarks[263].y * h),
                (landmarks[61].x * w, landmarks[61].y * h),
                (landmarks[291].x * w, landmarks[291].y * h)
            ], dtype=np.float64)
            
            focal_length = w
            camera_matrix = np.array([
                [focal_length, 0, w / 2],
                [0, focal_length, h / 2],
                [0, 0, 1]
            ], dtype=np.float64)
            
            dist_coeffs = np.zeros((4, 1))
            
            success, rotation_vector, _ = cv2.solvePnP(
                model_points, image_points, camera_matrix, dist_coeffs,
                flags=cv2.SOLVEPNP_EPNP
            )
            
            if not success:
                return None, None
            
            rotation_mat, _ = cv2.Rodrigues(rotation_vector)
            
            proj_matrix = np.hstack((rotation_mat, np.zeros((3, 1))))
            _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(proj_matrix)
            
            yaw_deg = float(euler_angles[1][0])
            pitch_deg = float(euler_angles[0][0])
            
            if pitch_deg > 90:
                pitch_deg = pitch_deg - 180
            elif pitch_deg < -90:
                pitch_deg = pitch_deg + 180
            if yaw_deg > 180:
                yaw_deg = yaw_deg - 360
            
            return yaw_deg, pitch_deg
            
        except Exception as e:
            logger.debug(f"计算头部姿态失败: {e}")
            return None, None

    def _check_lip_completeness(
        self,
        landmarks: Any,
        frame_shape: Tuple[int, int, int]
    ) -> Tuple[bool, List[str]]:
        """
        检查嘴唇完整性
        
        Args:
            landmarks: MediaPipe 478 点关键点
            frame_shape: 帧形状 (h, w, c)
        
        Returns:
            (是否完整, 缺失部位列表)
        """
        if landmarks is None:
            return False, ["关键点不可用"]
        
        h, w = frame_shape[:2]
        missing = []
        
        left_mouth_x = landmarks[61].x * w
        left_mouth_y = landmarks[61].y * h
        if left_mouth_x <= 0 or left_mouth_y <= 0:
            missing.append("左嘴角不可见")
        
        right_mouth_x = landmarks[291].x * w
        right_mouth_y = landmarks[291].y * h
        if right_mouth_x <= 0 or right_mouth_y <= 0:
            missing.append("右嘴角不可见")
        
        upper_lip_x = landmarks[13].x * w
        upper_lip_y = landmarks[13].y * h
        if upper_lip_x <= 0 or upper_lip_y <= 0:
            missing.append("上嘴唇不可见")
        
        lower_lip_x = landmarks[14].x * w
        lower_lip_y = landmarks[14].y * h
        if lower_lip_x <= 0 or lower_lip_y <= 0:
            missing.append("下嘴唇不可见")
        
        return len(missing) == 0, missing

    def _validate_face_with_landmarks(
        self,
        landmarks: Any,
        frame_shape: Tuple[int, int, int]
    ) -> Dict[str, Any]:
        """
        综合验证面部有效性
        
        Args:
            landmarks: MediaPipe 478 点关键点
            frame_shape: 帧形状 (h, w, c)
        
        Returns:
            {'is_valid': bool, 'reasons': List[str], 'yaw': float, 'pitch': float}
        """
        reasons = []
        yaw = None
        pitch = None
        
        if landmarks is None:
            return {'is_valid': False, 'reasons': ['关键点不可用'], 'yaw': None, 'pitch': None}
        
        lip_complete, lip_missing = self._check_lip_completeness(landmarks, frame_shape)
        if not lip_complete:
            reasons.extend(lip_missing)
        
        yaw, pitch = self._calculate_head_pose(landmarks, frame_shape)
        
        if yaw is None or pitch is None:
            reasons.append("无法计算头部姿态")
        else:
            if abs(yaw) > self.YAW_THRESHOLD:
                reasons.append(f"偏航角过大({yaw:.1f}°)")
            if abs(pitch) > self.PITCH_THRESHOLD:
                reasons.append(f"俯仰角过大({pitch:.1f}°)")
        
        return {
            'is_valid': len(reasons) == 0,
            'reasons': reasons,
            'yaw': yaw,
            'pitch': pitch
        }

    def extract_valid_frames(
        self,
        video_path: str,
        output_dir: str,
        frame_interval: int = 1
    ) -> List[str]:
        """
        提取有效帧

        Args:
            video_path: 视频路径
            output_dir: 输出目录
            frame_interval: 帧间隔

        Returns:
            有效帧文件路径列表
        """
        result = self.detect_faces(video_path)

        if not result.is_qualified:
            logger.warning(f"视频预处理不合格: {result.reasons}")

        os.makedirs(output_dir, exist_ok=True)

        cap = cv2.VideoCapture(video_path)
        valid_paths = []

        for idx in result.valid_frame_paths:
            if idx % frame_interval != 0:
                continue

            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()

            if ret:
                output_path = os.path.join(output_dir, f"frame_{idx:06d}.jpg")
                cv2.imwrite(output_path, frame)
                valid_paths.append(output_path)

        cap.release()

        logger.info(f"提取了 {len(valid_paths)} 个有效帧到 {output_dir}")
        return valid_paths

    def quick_check(self, video_path: str) -> Dict[str, Any]:
        """
        快速检查视频是否可用（不处理每一帧）

        Args:
            video_path: 视频路径

        Returns:
            检查结果
        """
        if not os.path.exists(video_path):
            return {"valid": False, "reason": "文件不存在"}

        # 检查文件大小
        file_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
        if file_size < 0.1:
            return {"valid": False, "reason": "文件过小"}

        # 检查视频格式
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"valid": False, "reason": "无法打开视频"}

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        cap.release()

        # 简单检查
        if fps <= 0 or fps > 60:
            return {"valid": False, "reason": f"FPS异常: {fps}"}

        if width < 128 or height < 128:
            return {"valid": False, "reason": f"分辨率过低: {width}x{height}"}

        return {
            "valid": True,
            "fps": fps,
            "resolution": (width, height),
            "total_frames": total_frames,
            "duration": total_frames / fps if fps > 0 else 0
        }


def preprocess_video(video_path: str, temp_dir: str = "temp/preprocess") -> VideoPreprocessResult:
    """便捷函数：预处理视频"""
    preprocessor = VideoPreprocessor(temp_dir=temp_dir)
    return preprocessor.detect_faces(video_path)


def quick_check_video(video_path: str) -> Dict[str, Any]:
    """便捷函数：快速检查视频"""
    preprocessor = VideoPreprocessor()
    return preprocessor.quick_check(video_path)


class HeyGemVideoValidator:
    """
    HeyGem 视频验证器
    检查视频是否符合 HeyGem 的要求
    
    使用嘴唇完整性标准：
    - 左右嘴角可见
    - 鼻尖可见
    """

    MIN_FACE_WIDTH_RATIO = 0.15
    MAX_FACE_WIDTH_RATIO = 0.7
    MIN_VALID_FRAME_RATIO = 0.7

    def __init__(self):
        self.preprocessor = VideoPreprocessor()

    def validate(self, video_path: str) -> Dict[str, Any]:
        """
        验证视频是否符合 HeyGem 要求

        Returns:
            验证结果字典:
            - valid: 是否通过验证
            - issues: 问题列表
            - details: 详细信息
        """
        result = {
            "valid": True,
            "issues": [],
            "details": {}
        }

        basic_check = self.preprocessor.quick_check(video_path)
        if not basic_check.get("valid", False):
            result["valid"] = False
            result["issues"].append(f"基本检查失败: {basic_check.get('reason')}")
            return result

        preprocess_result = self.preprocessor.detect_faces(video_path)

        valid_frames = 0
        size_issues = 0

        h, w = preprocess_result.resolution

        for frame_result in preprocess_result.frame_results:
            if not frame_result.has_face:
                continue

            bbox = frame_result.face_bbox
            face_width_ratio = bbox[2] / w
            if (face_width_ratio < self.MIN_FACE_WIDTH_RATIO or
                face_width_ratio > self.MAX_FACE_WIDTH_RATIO):
                size_issues += 1

            if frame_result.is_valid:
                valid_frames += 1

        total_frames = preprocess_result.total_frames
        valid_ratio = valid_frames / total_frames if total_frames > 0 else 0

        result["details"] = {
            "total_frames": total_frames,
            "valid_frames": valid_frames,
            "valid_ratio": valid_ratio,
            "size_issues": size_issues,
            "resolution": preprocess_result.resolution,
            "fps": preprocess_result.fps,
            "duration": preprocess_result.duration
        }

        if valid_ratio < self.MIN_VALID_FRAME_RATIO:
            result["valid"] = False
            result["issues"].append(
                f"有效帧数不足: {valid_ratio*100:.1f}% (需要 >{self.MIN_VALID_FRAME_RATIO*100}%)"
            )

        if size_issues > total_frames * 0.3:
            result["valid"] = False
            result["issues"].append(
                f"面部大小问题过多: {size_issues}/{total_frames} 帧"
            )

        return result


def validate_heygem_video(video_path: str) -> Dict[str, Any]:
    """便捷函数：验证视频是否符合 HeyGem 要求"""
    validator = HeyGemVideoValidator()
    return validator.validate(video_path)