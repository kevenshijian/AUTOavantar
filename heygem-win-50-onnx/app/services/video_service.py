import subprocess
import os
import cv2
import numpy as np
from typing import List, Optional, Tuple
from pathlib import Path
import logging
import tempfile

logger = logging.getLogger(__name__)

class VideoService:
    def __init__(self, fps: int = 25):
        self.fps = fps
        self._ffmpeg_path = self._find_ffmpeg()
    
    def _find_ffmpeg(self) -> str:
        possible_paths = [
            "ffmpeg",
            os.path.join(os.path.dirname(__file__), "..", "..", "py39", "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(os.path.dirname(__file__), "..", "..", "ffmpeg", "bin", "ffmpeg.exe"),
        ]
        for path in possible_paths:
            try:
                subprocess.run([path, "-version"], capture_output=True, check=True)
                return path
            except:
                continue
        return "ffmpeg"
    
    def read_video_frames(self, video_path: str) -> Tuple[List[np.ndarray], int, Tuple[int, int]]:
        frames = []
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        
        cap.release()
        logger.info(f"Read {len(frames)} frames from {video_path}")
        return frames, fps, (width, height)
    
    def write_video_frames(
        self,
        frames: List[np.ndarray],
        output_path: str,
        fps: Optional[int] = None
    ) -> str:
        if not frames:
            raise ValueError("No frames to write")
        
        fps = fps or self.fps
        height, width = frames[0].shape[:2]
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        for frame in frames:
            out.write(frame)
        
        out.release()
        logger.info(f"Wrote {len(frames)} frames to {output_path}")
        return output_path
    
    def merge_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str
    ) -> str:
        cmd = [
            self._ffmpeg_path,
            "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"FFmpeg merge warning: {result.stderr}")
        
        logger.info(f"Merged audio to video: {output_path}")
        return output_path
    
    def create_video_from_frames(
        self,
        frames: List[np.ndarray],
        audio_path: Optional[str],
        output_path: str,
        fps: Optional[int] = None
    ) -> str:
        fps = fps or self.fps
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            temp_video = tmp.name
        
        try:
            self.write_video_frames(frames, temp_video, fps)
            
            if audio_path and os.path.exists(audio_path):
                self.merge_audio(temp_video, audio_path, output_path)
            else:
                import shutil
                shutil.copy(temp_video, output_path)
            
            return output_path
        finally:
            if os.path.exists(temp_video):
                os.unlink(temp_video)
    
    def get_video_info(self, video_path: str) -> dict:
        cap = cv2.VideoCapture(video_path)
        info = {
            "fps": int(cap.get(cv2.CAP_PROP_FPS)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "duration": 0.0
        }
        if info["fps"] > 0:
            info["duration"] = info["frame_count"] / info["fps"]
        cap.release()
        return info
