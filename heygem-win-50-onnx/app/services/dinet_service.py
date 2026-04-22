"""
DINetService — 重写版本

修复 4 个 BUG 并适配 ONNX 2 输入 concat 模式：
1. ✅ _load_model() 调用 engine.load_model()
2. ✅ 归一化改为 /127.5-1（inference 模式，与 ONNX 训练一致）
3. ✅ 2 输入 concat 模式：audio_feature(B,256,T) + concat_images(B,6,H,W)
4. ✅ 动态高斯 blend mask（cv2.GaussianBlur 替代 F.conv2d）
5. ✅ 移除 PyTorch CUDA tensor 依赖，纯 numpy + cv2
6. ✅ 推理异常时返回原始帧（不崩溃）

基于：
- 阶段 0 验证：dinet_v1_20240131_wrapped.onnx 是 2 输入模式
- 原始 PyTorch 实现：landmark2face_wy/digitalhuman_interface.py inference1()
"""
import os
import numpy as np
import cv2
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DINetService:
    INFERENCE_MODES = ("inference", "inference_notraining")

    def __init__(
        self,
        model_path: str,
        device: str = "cuda",
        batch_size: int = 4,
        inference_mode: str = "inference_notraining"
    ):
        self.model_path = model_path
        self.device = device
        self.batch_size = batch_size
        self.img_size = 256
        self.crop_size = 5

        self.mask: Optional[np.ndarray] = None
        self.mask_re: Optional[np.ndarray] = None
        self.fuse_mask: Optional[np.ndarray] = None
        self.nblend: bool = True

        if inference_mode not in self.INFERENCE_MODES:
            raise ValueError(f"Invalid inference_mode: {inference_mode}. Must be one of {self.INFERENCE_MODES}")
        self.inference_mode = inference_mode

        self._load_model()

    def _load_model(self):
        """加载 ONNX 模型，通过 ModelManager 注册和获取"""
        try:
            from app.inference.model_manager import get_model_manager
            manager = get_model_manager()

            # 在 ModelManager 中注册 dinet 模型（如未注册或路径变更）
            if "dinet" not in manager or manager._model_configs.get("dinet", {}).get("model_path") != self.model_path:
                manager.register_model(
                    model_name="dinet",
                    model_path=self.model_path,
                    device=self.device,
                    auto_load=False,
                )

            # 通过 ModelManager 获取引擎（懒加载：如已卸载会自动 reload）
            self.engine = manager.get_model("dinet")
            logger.info(f"DINet model loaded via ModelManager: {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load DINet model: {e}")
            raise

    def load_template(self, template_path: str) -> Dict[str, Any]:
        """从 .pt 文件加载模板数据"""
        import torch
        try:
            template_data = torch.load(template_path, weights_only=False, map_location="cpu")
            return self.load_template_from_dict(template_data)
        except Exception as e:
            logger.error(f"Failed to load template: {e}")
            raise

    @staticmethod
    def _to_numpy(data) -> np.ndarray:
        """将 torch.Tensor 或其他数据转为 numpy float32 数组"""
        if isinstance(data, np.ndarray):
            return data.astype(np.float32)
        try:
            import torch
            if isinstance(data, torch.Tensor):
                return data.detach().cpu().numpy().astype(np.float32)
        except ImportError:
            pass
        return np.array(data, dtype=np.float32)

    def load_template_from_dict(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """从字典加载模板数据（不依赖 torch.load）"""
        try:
            self.img_size = template_data.get("model_input_size", [256])[0]
            self.crop_size = int(5 * (self.img_size / 256))

            # 加载 mask 数据（全部转为 numpy，不使用 torch tensor）
            fuse_mask = self._to_numpy(template_data.get("fuse_mask", np.ones((self.img_size, self.img_size), dtype=np.float32)))
            self.fuse_mask = cv2.resize(fuse_mask, (self.img_size, self.img_size))

            input_mask = self._to_numpy(template_data.get("input_mask", np.ones((self.img_size, self.img_size), dtype=np.float32)))
            self.mask = input_mask

            input_mask_re = self._to_numpy(template_data.get("input_mask_re", np.ones((self.img_size, self.img_size), dtype=np.float32) * 0.5))
            self.mask_re = input_mask_re

            self.nblend = template_data.get("nblend", True)

            logger.info(f"Template loaded: img_size={self.img_size}, crop_size={self.crop_size}, nblend={self.nblend}")
            return template_data
        except Exception as e:
            logger.error(f"Failed to load template from dict: {e}")
            raise

    def _normalize(self, img: np.ndarray, mask: Optional[np.ndarray] = None) -> np.ndarray:
        """归一化：/127.5-1（inference 模式），带 mask 时 = img/127.5*mask-1"""
        img = img / 127.5 - 1.0
        if mask is not None:
            return (img + 1.0) * mask - 1.0
        return img

    def _normalize_notraining(self, img: np.ndarray, mask: Optional[np.ndarray] = None) -> np.ndarray:
        """归一化：/255（inference_notraining 模式），值域 [0, 1]"""
        img = img / 255.0
        if mask is not None:
            return img * mask
        return img

    def _detect_inference_mode(self, template_data: Dict[str, Any]) -> str:
        """根据模板数据自动检测推理模式

        有 fuse_mask → inference 模式
        无 fuse_mask → inference_notraining 模式
        """
        fuse_mask = template_data.get("fuse_mask")
        if fuse_mask is not None:
            return "inference"
        return "inference_notraining"

    def _get_crop_region(self, mode: str) -> Tuple[int, int, int, int]:
        """获取裁剪区域参数

        inference 模式：crop_h=0, crop_h_end=-10, crop_w=5, crop_w_end=-5
        inference_notraining 模式：crop_size=5*(img_size/256)
        """
        if mode == "inference":
            crop_h = int(0 * (self.img_size / 256))
            crop_h_end = int(-10 * (self.img_size / 256))
            crop_w = int(5 * (self.img_size / 256))
            crop_w_end = int(-5 * (self.img_size / 256))
            return crop_h, crop_h_end, crop_w, crop_w_end
        else:
            crop_size = int(5 * (self.img_size / 256))
            return crop_size, -crop_size, crop_size, -crop_size

    def preprocess_frame(
        self,
        frame: np.ndarray,
        landmarks: Optional[np.ndarray] = None,
        mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """预处理单帧对齐人脸

        Args:
            frame: 对齐后的人脸图像 (H, W, 3) BGR 格式
            landmarks: 68 点关键点 (68, 2)，用于生成 blend mask
            mode: 推理模式，"inference" 或 "inference_notraining"，默认使用 self.inference_mode

        Returns:
            dict: {
                mask_B: (3, H, W) float32 — 归一化后 × mask
                B_img: (3, H, W) float32 — 归一化后 × mask_re
                B_img_raw: (3, H, W) float32 — 归一化（无 mask），用于融合
                original: (H, W, 3) uint8 — 原始帧
                crop_size: int — 裁剪偏移
                blend_mask: (H, W) uint8 — 嘴部区域二值 mask（动态融合用）
                mode: str — 使用的推理模式
            }
        """
        if mode is None:
            mode = self.inference_mode

        crop_h, crop_h_end, crop_w, crop_w_end = self._get_crop_region(mode)

        if frame.shape[0] != self.img_size or frame.shape[1] != self.img_size:
            frame = cv2.resize(frame, (self.img_size, self.img_size))

        mask_B_pre = frame.copy()
        mask_B_crop = mask_B_pre[crop_h:crop_h_end if crop_h_end < 0 else None,
                                 crop_w:crop_w_end if crop_w_end < 0 else None]
        B_img_crop = mask_B_crop.copy()

        if mask_B_crop.shape[0] != self.img_size or mask_B_crop.shape[1] != self.img_size:
            mask_B_crop = cv2.resize(mask_B_crop, (self.img_size, self.img_size))
            B_img_crop = cv2.resize(B_img_crop, (self.img_size, self.img_size))

        mask_B_rgb = mask_B_crop[:, :, ::-1].transpose(2, 0, 1).astype(np.float32)
        B_img_rgb = B_img_crop[:, :, ::-1].transpose(2, 0, 1).astype(np.float32)

        if mode == "inference":
            mask_B_norm = self._normalize(mask_B_rgb, mask=self.mask)
            B_img_norm = self._normalize(B_img_rgb, mask=self.mask_re)
            B_img_bgr = B_img_crop.transpose(2, 0, 1).astype(np.float32)
            B_img_raw = self._normalize(B_img_bgr)
        else:
            mask_B_norm = self._normalize_notraining(mask_B_rgb, mask=self.mask)
            B_img_norm = self._normalize_notraining(B_img_rgb, mask=self.mask_re)
            B_img_rgb_for_fusion = B_img_crop[:, :, ::-1].transpose(2, 0, 1).astype(np.float32)
            B_img_raw = self._normalize_notraining(B_img_rgb_for_fusion)

        blend_mask = None
        if landmarks is not None:
            blend_mask = self.get_face_mask(mask_B_pre, landmarks)
            blend_mask = blend_mask[crop_h:crop_h_end if crop_h_end < 0 else None,
                                    crop_w:crop_w_end if crop_w_end < 0 else None]
            if blend_mask.shape[:2] != (self.img_size, self.img_size):
                blend_mask = cv2.resize(blend_mask, (self.img_size, self.img_size),
                                       interpolation=cv2.INTER_LINEAR)

        return {
            "mask_B": mask_B_norm,
            "B_img": B_img_norm,
            "B_img_raw": B_img_raw,
            "original": mask_B_pre,
            "crop_size": self.crop_size,
            "blend_mask": blend_mask,
            "mode": mode,
        }

    @staticmethod
    def get_face_mask(img: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
        """根据 68 点关键点生成嘴部区域二值 mask

        Args:
            img: 图像 (H, W, 3)
            landmarks: 68 点关键点 (68, 2)

        Returns:
            二值 mask (H, W)，嘴部区域 255，其余 0
        """
        img_shape = img.shape[0]
        mask = np.zeros((img_shape, img_shape), dtype=np.uint8)

        if len(landmarks) >= 68:
            landmarks = landmarks.astype(int)
            # 嘴部轮廓点 (3:15 + 29) 的凸包
            wanted_numpy = np.concatenate([landmarks[2:15], landmarks[29:30]])
            wanted_numpy = cv2.convexHull(wanted_numpy)
            cv2.fillConvexPoly(mask, wanted_numpy, 255)

            # 补充椭圆区域
            mid = (landmarks[5, :] + landmarks[11, :]) // 2
            axis_w = max(1, int((landmarks[11, 0] - landmarks[5, 0] + 3 * (img_shape // 266)) // 2))
            axis_h = max(1, int(60 * (img_shape // 266)))
            cv2.ellipse(
                mask,
                (int(mid[0]), int(mid[1])),
                (axis_w, axis_h),
                0, 0, 180,
                255, -1
            )
        elif len(landmarks) >= 5:
            # 5 点模式：简单椭圆
            left_mouth = landmarks[3]
            right_mouth = landmarks[4]
            center = (int((left_mouth[0] + right_mouth[0]) // 2),
                     int((left_mouth[1] + right_mouth[1]) // 2))
            w = int(abs(right_mouth[0] - left_mouth[0]) * 1.5)
            h = int(w * 0.8)
            cv2.ellipse(mask, center, (w, h), 0, 0, 360, 255, -1)
        else:
            # 回退：中心圆
            center = (img_shape // 2, img_shape // 2)
            cv2.circle(mask, center, img_shape // 3, 255, -1)

        # 膨胀 mask
        amask = (mask > 0).astype(np.uint8) * 255
        kernel_size = (5 * (img_shape // 266) + 1, 5 * (img_shape // 266) + 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_size)
        eroded_mask = cv2.dilate(amask, kernel, iterations=1)
        return eroded_mask

    @staticmethod
    def _gaussian_blend_mask(blend_mask: np.ndarray, img_size: int = 256) -> np.ndarray:
        """动态高斯融合 mask

        用 cv2.GaussianBlur 平滑嘴部区域边缘，替代原始 F.conv2d

        Args:
            blend_mask: 二值 mask (H, W)，嘴部区域 255
            img_size: 图像尺寸

        Returns:
            融合权重 (1, 3, H, W)，值域 [0, 1]
        """
        kernel_size = 16 * int(img_size / 256) + 1
        if kernel_size % 2 == 0:
            kernel_size += 1
        sigma = kernel_size / 6.0

        # 高斯模糊平滑边缘
        blurred = cv2.GaussianBlur(blend_mask, (kernel_size, kernel_size), sigma)

        # 归一化到 [0, 1]
        weights = blurred.astype(np.float32) / 255.0

        # 扩展到 3 通道 + batch 维度 (1, 3, H, W)
        weights = np.stack([weights] * 3, axis=0)[np.newaxis]
        return weights

    def inference_batch(
        self,
        audio_features: List[np.ndarray],
        face_data_list: List[Dict[str, Any]]
    ) -> List[np.ndarray]:
        """批量推理

        Args:
            audio_features: WeNet BNF 特征列表，每个 (T, 256)
            face_data_list: 预处理后的帧数据列表

        Returns:
            合成后的帧列表 (H, W, 3) uint8 BGR
        """
        results = []
        for i in range(0, len(audio_features), self.batch_size):
            batch_audio = audio_features[i:i + self.batch_size]
            batch_face = face_data_list[i:i + self.batch_size]
            batch_results = self._process_batch(batch_audio, batch_face)
            results.extend(batch_results)
        return results

    def _process_batch(
        self,
        audio_features: List[np.ndarray],
        face_data_list: List[Dict[str, Any]]
    ) -> List[np.ndarray]:
        """处理一个批次的推理

        Args:
            audio_features: BNF 特征列表 (T, 256)
            face_data_list: 帧数据列表

        Returns:
            合成帧列表 (H, W, 3) uint8 BGR
        """
        if not audio_features:
            return []

        batch_size = len(audio_features)

        try:
            # 准备音频特征：转置 (T, 256) → (1, 256, T)，再 stack 为 (B, 256, T)
            lab_list = [af.transpose(1, 0) for af in audio_features]
            # 补齐 T 维度到最大值
            max_T = max(lab.shape[1] for lab in lab_list)
            lab_padded = []
            for lab in lab_list:
                if lab.shape[1] < max_T:
                    pad = np.zeros((256, max_T - lab.shape[1]), dtype=np.float32)
                    lab = np.concatenate([lab, pad], axis=1)
                lab_padded.append(lab)
            audio_feature = np.stack(lab_padded, axis=0)  # (B, 256, max_T)
            del lab_list, lab_padded  # 及时释放中间数组

            # 准备图像数据
            mask_B_list = []
            B_img_list = []
            B_img_raw_list = []
            blend_mask_list = []
            crop_sizes = []

            for face_data in face_data_list:
                mask_B_list.append(face_data["mask_B"])
                B_img_list.append(face_data["B_img"])
                B_img_raw_list.append(face_data["B_img_raw"])
                crop_sizes.append(face_data.get("crop_size", self.crop_size))
                blend_mask_list.append(face_data.get("blend_mask"))

            # Stack 为 batch
            mask_B = np.stack(mask_B_list, axis=0)   # (B, 3, H, W)
            B_img_ = np.stack(B_img_list, axis=0)    # (B, 3, H, W)
            B_img_raw = np.stack(B_img_raw_list, axis=0)  # (B, 3, H, W)
            del mask_B_list, B_img_list, B_img_raw_list

            concat_images = np.concatenate([mask_B, B_img_], axis=1)  # (B, 6, H, W)
            del mask_B, B_img_

            outputs = self.engine.infer({
                "audio_feature": audio_feature,
                "concat_images": concat_images
            })
            generated = outputs["generated_image"]  # (B, 3, H, W)，ONNX 输出值域 [0, 1]
            del audio_feature, concat_images, outputs

            generated = generated[:, [2, 1, 0], :, :]  # RGB → BGR

            current_mode = face_data_list[0].get("mode", self.inference_mode) if face_data_list else self.inference_mode

            if current_mode == "inference":
                generated = generated * 2.0 - 1.0  # [0, 1] → [-1, 1]
            else:
                pass

            if self.nblend and self.mask_re is not None:
                mask_re_batch = self.mask_re[np.newaxis, np.newaxis, :, :]
                mask_re_batch = np.repeat(mask_re_batch, batch_size, axis=0)
                mask_re_zero = (mask_re_batch == 0)
                generated = np.where(mask_re_zero, B_img_raw, generated)
                del mask_re_batch, mask_re_zero

            fuse_res = self._apply_blend_mask(generated, B_img_raw, blend_mask_list, batch_size, current_mode)
            del generated, B_img_raw

            if current_mode == "inference":
                np.clip(fuse_res, -1.0, 1.0, out=fuse_res)
            else:
                np.clip(fuse_res, 0.0, 1.0, out=fuse_res)

        except Exception as e:
            logger.error(f"DINet inference error: {e}", exc_info=True)
            return [face_data["original"] for face_data in face_data_list]

        results = []
        for i, face_data in enumerate(face_data_list):
            crop_size = crop_sizes[i]
            output_frame = face_data["original"].copy()
            current_mode = face_data.get("mode", self.inference_mode)

            if current_mode == "inference":
                generated_frame = ((fuse_res[i].transpose(1, 2, 0) + 1.0) * 127.5).astype(np.uint8)
            else:
                generated_frame = (fuse_res[i].transpose(1, 2, 0) * 255.0).astype(np.uint8)

            crop_h = output_frame.shape[0] - 2 * crop_size
            crop_w = output_frame.shape[1] - 2 * crop_size
            if generated_frame.shape[0] != crop_h or generated_frame.shape[1] != crop_w:
                generated_frame = cv2.resize(generated_frame, (crop_w, crop_h))
            output_frame[crop_size:-crop_size, crop_size:-crop_size] = generated_frame
            results.append(output_frame)

        return results

    def _apply_blend_mask(
        self,
        generated: np.ndarray,
        B_img_raw: np.ndarray,
        blend_mask_list: List[Optional[np.ndarray]],
        batch_size: int,
        mode: str = "inference"
    ) -> np.ndarray:
        """应用动态高斯融合 mask

        如果有 blend_mask，使用动态高斯融合；
        否则使用模板中的静态 fuse_mask。

        Args:
            generated: ONNX 输出 (B, 3, H, W)
            B_img_raw: 原始图像（归一化后）(B, 3, H, W)
            blend_mask_list: 动态 blend mask 列表
            batch_size: 批次大小
            mode: 推理模式

        Returns:
            融合结果 (B, 3, H, W)
        """
        has_blend_masks = any(bm is not None for bm in blend_mask_list)

        if has_blend_masks:
            # 动态高斯融合
            fuse_res = np.zeros_like(generated)
            for i in range(batch_size):
                blend_mask = blend_mask_list[i]
                if blend_mask is not None:
                    weights = self._gaussian_blend_mask(blend_mask, self.img_size)
                else:
                    # 没有 blend mask 的帧使用静态 fuse_mask
                    weights = self._static_fuse_weights()
                fuse_res[i] = generated[i] * weights[0] + B_img_raw[i] * (1 - weights[0])
        else:
            # 静态 fuse_mask 融合
            weights = self._static_fuse_weights()
            fuse_res = generated * weights + B_img_raw * (1 - weights)

        return fuse_res

    def _static_fuse_weights(self) -> np.ndarray:
        """获取静态 fuse_mask 权重 (1, 3, H, W)"""
        if self.fuse_mask is not None:
            weights = np.stack([self.fuse_mask] * 3, axis=0)[np.newaxis]
        else:
            weights = np.ones((1, 3, self.img_size, self.img_size), dtype=np.float32)
        return weights

    def inference_single(
        self,
        audio_feature: np.ndarray,
        face_data: Dict[str, Any]
    ) -> np.ndarray:
        """单帧推理"""
        return self._process_batch([audio_feature], [face_data])[0]
