from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form
from typing import List, Optional
from pathlib import Path
import os
import uuid
from datetime import datetime

from app.models import TemplateInfo, TemplateDetail
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("api.templates")
router = APIRouter(prefix="/api/v1/templates", tags=["Templates"])

_templates_store: dict = {}

def get_template_store():
    return _templates_store

@router.get("", response_model=List[TemplateInfo])
async def list_templates(
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    template_store: dict = Depends(get_template_store)
):
    settings = get_settings()
    templates = []
    
    templates_dir = settings.TEMPLATES_DIR
    if templates_dir.exists():
        for template_id in os.listdir(templates_dir):
            template_path = templates_dir / template_id
            if template_path.is_dir():
                meta_path = template_path / "meta.json"
                if meta_path.exists():
                    import json
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    
                    templates.append(TemplateInfo(
                        template_id=template_id,
                        name=meta.get("name", template_id),
                        description=meta.get("description", ""),
                        preview_url=f"/api/v1/templates/{template_id}/preview",
                        duration=meta.get("duration", 0.0),
                        resolution=meta.get("resolution", "1920x1080"),
                        created_at=meta.get("created_at", "")
                    ))
    
    if search:
        templates = [t for t in templates if search.lower() in t.name.lower()]
    
    return templates[skip:skip + limit]

@router.get("/{template_id}", response_model=TemplateDetail)
async def get_template(
    template_id: str,
    template_store: dict = Depends(get_template_store)
):
    settings = get_settings()
    template_path = settings.TEMPLATES_DIR / template_id
    
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    
    meta_path = template_path / "meta.json"
    if meta_path.exists():
        import json
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    else:
        meta = {}
    
    return TemplateDetail(
        template_id=template_id,
        name=meta.get("name", template_id),
        description=meta.get("description", ""),
        preview_url=f"/api/v1/templates/{template_id}/preview",
        video_duration=meta.get("duration", 0.0),
        resolution=meta.get("resolution", "1920x1080"),
        fps=meta.get("fps", 25),
        created_at=meta.get("created_at", ""),
        updated_at=meta.get("updated_at", ""),
        metadata=meta.get("metadata", {})
    )

@router.post("", response_model=TemplateDetail)
async def create_template(
    video_file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
    template_store: dict = Depends(get_template_store)
):
    settings = get_settings()
    template_id = str(uuid.uuid4())
    
    template_path = settings.TEMPLATES_DIR / template_id
    template_path.mkdir(parents=True, exist_ok=True)
    
    video_path = template_path / "source.mp4"
    with open(video_path, "wb") as f:
        content = await video_file.read()
        f.write(content)
    
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    
    from app.services import FaceDetectService
    face_detect = FaceDetectService(device=settings.DEVICE)
    
    cap = cv2.VideoCapture(str(video_path))
    ret, first_frame = cap.read()
    cap.release()
    
    if ret:
        faces = face_detect.detect(first_frame)
        if faces:
            landmarks = faces[0]["landmarks"]
            bbox = faces[0]["bbox"]
            
            face_data = {
                "first_frame": first_frame.tolist(),
                "landmarks": landmarks.tolist() if hasattr(landmarks, 'tolist') else landmarks,
                "bbox": bbox.tolist() if hasattr(bbox, 'tolist') else bbox
            }
            import torch
            torch.save(face_data, template_path / "face.pt")
            
            preview_path = template_path / "preview.jpg"
            preview = cv2.resize(first_frame, (320, 180))
            cv2.imwrite(str(preview_path), preview)
    
    now = datetime.now().isoformat()
    meta = {
        "name": name,
        "description": description,
        "duration": duration,
        "resolution": f"{width}x{height}",
        "fps": fps,
        "created_at": now,
        "updated_at": now,
        "metadata": {}
    }
    
    import json
    with open(template_path / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Template created: {template_id}")
    
    return TemplateDetail(
        template_id=template_id,
        name=name,
        description=description,
        preview_url=f"/api/v1/templates/{template_id}/preview",
        video_duration=duration,
        resolution=f"{width}x{height}",
        fps=fps,
        created_at=now,
        updated_at=now,
        metadata={}
    )

@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    template_store: dict = Depends(get_template_store)
):
    settings = get_settings()
    template_path = settings.TEMPLATES_DIR / template_id
    
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    
    import shutil
    shutil.rmtree(template_path)
    
    logger.info(f"Template deleted: {template_id}")
    
    return {"message": "Template deleted", "template_id": template_id}

@router.get("/{template_id}/preview")
async def get_template_preview(
    template_id: str,
    template_store: dict = Depends(get_template_store)
):
    settings = get_settings()
    preview_path = settings.TEMPLATES_DIR / template_id / "preview.jpg"
    
    if not preview_path.exists():
        raise HTTPException(status_code=404, detail="Preview not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(
        preview_path,
        media_type="image/jpeg",
        filename=f"{template_id}_preview.jpg"
    )
