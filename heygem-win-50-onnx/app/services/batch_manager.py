import torch
import numpy as np
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from queue import Queue
from threading import Thread, Event
import time
import logging

logger = logging.getLogger(__name__)

@dataclass
class BatchItem:
    item_id: str
    data: Dict[str, Any]
    callback: Callable
    timestamp: float

class DynamicBatchManager:
    def __init__(
        self,
        inference_func: Callable,
        max_batch_size: int = 8,
        max_wait_time: float = 0.1,
        max_queue_size: int = 100
    ):
        self.inference_func = inference_func
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self.queue = Queue(maxsize=max_queue_size)
        self.running = False
        self.worker_thread = None
        self._stop_event = Event()
    
    def start(self):
        self.running = True
        self.worker_thread = Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("Batch manager started")
    
    def stop(self):
        self.running = False
        self._stop_event.set()
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Batch manager stopped")
    
    def submit(self, item_id: str, data: Dict[str, Any], callback: Callable):
        item = BatchItem(
            item_id=item_id,
            data=data,
            callback=callback,
            timestamp=time.time()
        )
        self.queue.put(item)
        return item_id
    
    def _worker_loop(self):
        while self.running:
            batch = []
            batch_start_time = time.time()
            
            while len(batch) < self.max_batch_size:
                elapsed = time.time() - batch_start_time
                remaining_wait = self.max_wait_time - elapsed
                
                if remaining_wait <= 0 or len(batch) >= self.max_batch_size:
                    break
                
                try:
                    item = self.queue.get(timeout=remaining_wait)
                    batch.append(item)
                except:
                    break
            
            if batch:
                self._process_batch(batch)
    
    def _process_batch(self, batch: List[BatchItem]):
        try:
            batch_data = [item.data for item in batch]
            results = self.inference_func(batch_data)
            
            for item, result in zip(batch, results):
                try:
                    item.callback(item.item_id, result, None)
                except Exception as e:
                    logger.error(f"Callback error for item {item.item_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            for item in batch:
                item.callback(item.item_id, None, str(e))

class FrameBatchProcessor:
    def __init__(
        self,
        dinet_service,
        batch_size: int = 4,
        prefetch_size: int = 8
    ):
        self.dinet_service = dinet_service
        self.batch_size = batch_size
        self.prefetch_size = prefetch_size
    
    def process_frames(
        self,
        frames: List[np.ndarray],
        audio_features: List[np.ndarray],
        face_data_list: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> List[np.ndarray]:
        total_frames = len(frames)
        results = []
        
        for i in range(0, total_frames, self.batch_size):
            batch_end = min(i + self.batch_size, total_frames)
            batch_frames = frames[i:batch_end]
            batch_audio = audio_features[i:batch_end]
            batch_face = face_data_list[i:batch_end]
            
            batch_results = self.dinet_service.inference_batch(
                batch_audio,
                batch_face
            )
            results.extend(batch_results)
            
            if progress_callback:
                progress = batch_end / total_frames
                progress_callback(progress, f"Processed {batch_end}/{total_frames} frames")
        
        return results
