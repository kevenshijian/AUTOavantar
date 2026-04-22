from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Optional
import uuid
from datetime import datetime
import os
import cv2
import numpy as np

from app.models import (
    GenerateRequest,
    GenerateSyncRequest,
    TaskResponse,
    TaskStatus,
    GenerateResult
)
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("api.digital_human")
router = APIRouter(prefix="/api/v1/digital-human", tags=["Digital Human"])

_tasks_store: dict = {}

def get_task_store():
    return _tasks_store

@router.post("/submit", response_model=TaskResponse)
async def submit_task(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    task_store: dict = Depends(get_task_store)
):
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    task_store[task_id] = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "progress": 0.0,
        "message": "Task submitted",
        "request": request.dict(),
        "created_at": now,
        "updated_at": now,
        "result_url": None
    }
    
    background_tasks.add_task(
        process_digital_human_task,
        task_id,
        request,
        task_store
    )
    
    logger.info(f"Task submitted: {task_id}")
    
    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        created_at=now,
        updated_at=now
    )

@router.get("/query/{task_id}", response_model=TaskResponse)
async def query_task(
    task_id: str,
    task_store: dict = Depends(get_task_store)
):
    task = task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskResponse(
        task_id=task["task_id"],
        status=task["status"],
        progress=task.get("progress", 0.0),
        message=task.get("message", ""),
        result_url=task.get("result_url"),
        created_at=task["created_at"],
        updated_at=task["updated_at"]
    )

@router.get("/download/{task_id}")
async def download_result(
    task_id: str,
    task_store: dict = Depends(get_task_store)
):
    task = task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Task not completed")
    
    result_path = task.get("result_path")
    if not result_path or not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="Result file not found")
    
    return FileResponse(
        result_path,
        media_type="video/mp4",
        filename=f"digital_human_{task_id}.mp4"
    )

@router.delete("/cancel/{task_id}")
async def cancel_task(
    task_id: str,
    task_store: dict = Depends(get_task_store)
):
    task = task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] == TaskStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="Cannot cancel processing task")
    
    task["status"] = TaskStatus.FAILED
    task["message"] = "Task cancelled by user"
    task["updated_at"] = datetime.now().isoformat()
    
    logger.info(f"Task cancelled: {task_id}")
    
    return {"message": "Task cancelled", "task_id": task_id}

async def process_digital_human_task(
    task_id: str,
    request: GenerateRequest,
    task_store: dict
):
    try:
        task_store[task_id]["status"] = TaskStatus.PROCESSING
        task_store[task_id]["message"] = "Processing started"
        task_store[task_id]["updated_at"] = datetime.now().isoformat()
        
        settings = get_settings()
        
        import tempfile
        import requests
        import os
        
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = os.path.join(temp_dir, "audio.wav")
            output_path = os.path.join(temp_dir, "output.mp4")
            
            task_store[task_id]["progress"] = 0.1
            task_store[task_id]["message"] = "Downloading audio"
            
            audio_url = request.audio_url
            if audio_url.startswith("file:///"):
                local_path = audio_url[8:]
                import shutil
                shutil.copy(local_path, audio_path)
            elif audio_url.startswith("file://"):
                local_path = audio_url[7:]
                import shutil
                shutil.copy(local_path, audio_path)
            else:
                audio_resp = requests.get(audio_url, timeout=60)
                with open(audio_path, "wb") as f:
                    f.write(audio_resp.content)
            
            task_store[task_id]["progress"] = 0.2
            task_store[task_id]["message"] = "Loading template"
            
            template_path = os.path.join(
                settings.TEMPLATES_DIR,
                request.template_id,
                "face.pt"
            )
            
            if not os.path.exists(template_path):
                raise ValueError(f"Template not found: {request.template_id}")
            
            task_store[task_id]["progress"] = 0.3
            task_store[task_id]["message"] = "Processing audio"
            
            from app.services import AudioService
            audio_service = AudioService(device=settings.DEVICE)
            audio_features = audio_service.extract_wenet_features(audio_path)
            
            task_store[task_id]["progress"] = 0.4
            task_store[task_id]["message"] = "Loading DINet model"
            
            from app.services import DINetService
            dinet_service = DINetService(
                model_path=str(settings.DINET_MODEL_DIR / settings.DINET_MODEL),
                device=settings.DEVICE,
                batch_size=settings.BATCH_SIZE
            )
            dinet_service.load_template(template_path)
            
            task_store[task_id]["progress"] = 0.5
            task_store[task_id]["message"] = "Generating video frames"
            
            template_video_path = os.path.join(
                settings.TEMPLATES_DIR,
                request.template_id,
                "source.mp4"
            )
            
            if os.path.exists(template_video_path):
                from app.services import VideoService, FaceDetectService
                
                video_service = VideoService()
                face_detect = FaceDetectService(device=settings.DEVICE)
                
                frames, fps, (width, height) = video_service.read_video_frames(template_video_path)
                
                num_frames = len(frames)
                num_audio_features = len(audio_features)
                
                frame_to_audio_idx = []
                for i in range(num_frames):
                    audio_idx = int(i * num_audio_features / num_frames)
                    audio_idx = min(audio_idx, num_audio_features - 1)
                    frame_to_audio_idx.append(audio_idx)
                
                processed_frames = []
                for i, frame in enumerate(frames):
                    progress = 0.5 + 0.4 * (i / len(frames))
                    task_store[task_id]["progress"] = progress
                    task_store[task_id]["message"] = f"Processing frame {i+1}/{len(frames)}"
                    
                    faces = face_detect.detect(frame)
                    if faces:
                        face = face_detect.get_largest_face(faces)
                        aligned = face_detect.align_face(frame, face["landmarks"], size=dinet_service.img_size)
                        
                        audio_idx = frame_to_audio_idx[i]
                        audio_feat = audio_features[audio_idx]
                        
                        face_data = dinet_service.preprocess_frame(aligned, face["landmarks"])
                        result = dinet_service.inference_single(audio_feat, face_data)
                        
                        if result.shape[:2] != (height, width):
                            result = cv2.resize(result, (width, height))
                        processed_frames.append(result)
                    else:
                        processed_frames.append(frame)
                
                task_store[task_id]["progress"] = 0.9
                task_store[task_id]["message"] = "Composing video"
                
                video_service.create_video_from_frames(
                    processed_frames,
                    audio_path,
                    output_path,
                    fps=fps
                )
            else:
                raise ValueError(f"Template video not found: {template_video_path}")
            
            result_dir = settings.RESULT_DIR
            result_dir.mkdir(parents=True, exist_ok=True)
            final_path = result_dir / f"{task_id}.mp4"
            
            import shutil
            shutil.copy(output_path, final_path)
            
            task_store[task_id]["status"] = TaskStatus.COMPLETED
            task_store[task_id]["progress"] = 1.0
            task_store[task_id]["message"] = "Task completed"
            task_store[task_id]["result_url"] = f"/api/v1/digital-human/download/{task_id}"
            task_store[task_id]["result_path"] = str(final_path)
            task_store[task_id]["updated_at"] = datetime.now().isoformat()
            
            logger.info(f"Task completed: {task_id}")
            
    except Exception as e:
        logger.error(f"Task failed: {task_id}, error: {str(e)}")
        task_store[task_id]["status"] = TaskStatus.FAILED
        task_store[task_id]["message"] = str(e)
        task_store[task_id]["updated_at"] = datetime.now().isoformat()
