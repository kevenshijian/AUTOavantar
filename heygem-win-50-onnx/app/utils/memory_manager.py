import torch
import gc
from typing import Optional, Dict, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self, device: str = "cuda"):
        self.device = device
        self.allocated_before = {}
    
    def get_memory_info(self) -> Dict[str, float]:
        if self.device == "cuda" and torch.cuda.is_available():
            return {
                "allocated_mb": torch.cuda.memory_allocated() / 1024 / 1024,
                "cached_mb": torch.cuda.memory_reserved() / 1024 / 1024,
                "max_allocated_mb": torch.cuda.max_memory_allocated() / 1024 / 1024
            }
        return {}
    
    def clear_cache(self):
        if self.device == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
            logger.info("CUDA cache cleared")
    
    @contextmanager
    def track_memory(self, name: str = "operation"):
        if self.device == "cuda" and torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            before = torch.cuda.memory_allocated()
        
        yield
        
        if self.device == "cuda" and torch.cuda.is_available():
            after = torch.cuda.memory_allocated()
            peak = torch.cuda.max_memory_allocated()
            logger.info(
                f"Memory [{name}]: "
                f"before={before/1024/1024:.1f}MB, "
                f"after={after/1024/1024:.1f}MB, "
                f"peak={peak/1024/1024:.1f}MB"
            )
    
    @contextmanager
    def inference_mode(self):
        with torch.no_grad():
            yield
        self.clear_cache()
    
    def optimize_for_inference(self):
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.deterministic = False
        if self.device == "cuda":
            torch.cuda.set_device(0)
        logger.info("Optimized PyTorch for inference")
    
    def get_gpu_utilization(self) -> Dict[str, Any]:
        if self.device != "cuda" or not torch.cuda.is_available():
            return {"available": False}
        
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            
            return {
                "available": True,
                "gpu_utilization": util.gpu,
                "memory_utilization": util.memory,
                "memory_used_mb": mem_info.used / 1024 / 1024,
                "memory_total_mb": mem_info.total / 1024 / 1024,
                "memory_free_mb": mem_info.free / 1024 / 1024
            }
        except ImportError:
            return {"available": False, "error": "pynvml not installed"}
        except Exception as e:
            return {"available": False, "error": str(e)}

memory_manager = MemoryManager()
