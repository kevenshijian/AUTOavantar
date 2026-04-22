import onnxruntime as ort
import numpy as np
import cv2
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class EnhanceService:
    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cuda"
    ):
        self.device = device
        self.model_path = model_path or self._get_default_model_path()
        self.session = None
        self._load_model()
    
    def _get_default_model_path(self) -> str:
        base_dir = Path(__file__).parent.parent.parent
        return str(base_dir / "pretrain_models" / "face_lib" / "face_restore" / "gfpgan" / "GFPGANv1.4.onnx")
    
    def _load_model(self):
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if self.device == "cuda" else ['CPUExecutionProvider']
        try:
            self.session = ort.InferenceSession(self.model_path, providers=providers)
            logger.info(f"GFPGAN model loaded from: {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load GFPGAN model: {e}")
            raise
    
    def preprocess(self, image: np.ndarray, target_size: int = 512) -> Tuple[np.ndarray, Tuple[int, int]]:
        h, w = image.shape[:2]
        scale = target_size / max(h, w)
        new_h, new_w = int(h * scale), int(w * scale)
        resized = cv2.resize(image, (new_w, new_h))
        
        pad_h = target_size - new_h
        pad_w = target_size - new_w
        padded = cv2.copyMakeBorder(resized, 0, pad_h, 0, pad_w, cv2.BORDER_REFLECT)
        
        normalized = (padded.astype(np.float32) / 255.0 - 0.5) / 0.5
        tensor = normalized.transpose(2, 0, 1)[np.newaxis, ...]
        
        return tensor, (h, w)
    
    def postprocess(self, output: np.ndarray, original_size: Tuple[int, int]) -> np.ndarray:
        output = output.squeeze(0).transpose(1, 2, 0)
        output = (output * 0.5 + 0.5) * 255
        output = np.clip(output, 0, 255).astype(np.uint8)
        
        h, w = original_size
        output = cv2.resize(output, (w, h))
        return output
    
    def enhance(self, image: np.ndarray) -> np.ndarray:
        if image is None or image.size == 0:
            return image
        
        input_tensor, original_size = self.preprocess(image)
        
        input_name = self.session.get_inputs()[0].name
        output_name = self.session.get_outputs()[0].name
        
        output = self.session.run([output_name], {input_name: input_tensor})[0]
        
        result = self.postprocess(output, original_size)
        logger.debug(f"Enhanced face image: {image.shape} -> {result.shape}")
        return result
    
    def enhance_faces(
        self,
        images: List[np.ndarray],
        batch_size: int = 4
    ) -> List[np.ndarray]:
        results = []
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            batch_results = [self.enhance(img) for img in batch]
            results.extend(batch_results)
        return results
