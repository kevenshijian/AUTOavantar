import os
import json
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import sqlite3
import cv2
import torch
import numpy as np
import logging

logger = logging.getLogger(__name__)

@dataclass
class DigitalHumanTemplate:
    template_id: str
    name: str
    description: str
    video_path: str
    face_data_path: str
    preview_path: str
    duration: float
    resolution: str
    fps: int
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]

class TemplateService:
    def __init__(
        self,
        template_dir: str = "./templates",
        db_path: str = "./templates/templates.db"
    ):
        self.template_dir = Path(template_dir)
        self.db_path = Path(db_path)
        self.template_dir.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                template_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                video_path TEXT,
                face_data_path TEXT,
                preview_path TEXT,
                duration REAL,
                resolution TEXT,
                fps INTEGER,
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def list_templates(
        self,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None
    ) -> List[DigitalHumanTemplate]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if search:
            cursor.execute(
                """
                SELECT * FROM templates 
                WHERE name LIKE ? OR description LIKE ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (f"%{search}%", f"%{search}%", limit, skip)
            )
        else:
            cursor.execute(
                """
                SELECT * FROM templates 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, skip)
            )
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_template(row) for row in rows]
    
    def get_template(self, template_id: str) -> Optional[DigitalHumanTemplate]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM templates WHERE template_id = ?",
            (template_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        return self._row_to_template(row) if row else None
    
    def create_template(
        self,
        name: str,
        video_path: str,
        description: str = "",
        template_id: Optional[str] = None
    ) -> DigitalHumanTemplate:
        import uuid
        template_id = template_id or str(uuid.uuid4())
        
        template_path = self.template_dir / template_id
        template_path.mkdir(parents=True, exist_ok=True)
        
        dest_video_path = template_path / "source.mp4"
        shutil.copy(video_path, dest_video_path)
        
        cap = cv2.VideoCapture(str(dest_video_path))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0
        cap.release()
        
        face_data_path = template_path / "face.pt"
        preview_path = template_path / "preview.jpg"
        
        self._extract_face_data(dest_video_path, face_data_path, preview_path)
        
        now = datetime.now().isoformat()
        template = DigitalHumanTemplate(
            template_id=template_id,
            name=name,
            description=description,
            video_path=str(dest_video_path),
            face_data_path=str(face_data_path),
            preview_path=str(preview_path),
            duration=duration,
            resolution=f"{width}x{height}",
            fps=fps,
            created_at=now,
            updated_at=now,
            metadata={}
        )
        
        self._save_template(template)
        
        meta_path = template_path / "meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(asdict(template), f, ensure_ascii=False, indent=2)
        
        logger.info(f"Template created: {template_id}")
        return template
    
    def _extract_face_data(
        self,
        video_path: Path,
        face_data_path: Path,
        preview_path: Path
    ):
        try:
            from app.services import FaceDetectService
            
            face_detect = FaceDetectService()
            cap = cv2.VideoCapture(str(video_path))
            ret, first_frame = cap.read()
            cap.release()
            
            if ret:
                faces = face_detect.detect(first_frame)
                if faces:
                    face = faces[0]
                    face_data = {
                        "first_frame": first_frame.tolist(),
                        "landmarks": face["landmarks"].tolist(),
                        "bbox": face["bbox"].tolist()
                    }
                    torch.save(face_data, face_data_path)
                    
                    preview = cv2.resize(first_frame, (320, 180))
                    cv2.imwrite(str(preview_path), preview)
                    logger.info(f"Face data extracted for template")
        except Exception as e:
            logger.error(f"Failed to extract face data: {e}")
    
    def _save_template(self, template: DigitalHumanTemplate):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO templates 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template.template_id,
                template.name,
                template.description,
                template.video_path,
                template.face_data_path,
                template.preview_path,
                template.duration,
                template.resolution,
                template.fps,
                template.created_at,
                template.updated_at,
                json.dumps(template.metadata)
            )
        )
        conn.commit()
        conn.close()
    
    def delete_template(self, template_id: str):
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        template_path = Path(template.video_path).parent
        if template_path.exists():
            shutil.rmtree(template_path)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM templates WHERE template_id = ?",
            (template_id,)
        )
        conn.commit()
        conn.close()
        
        logger.info(f"Template deleted: {template_id}")
    
    def _row_to_template(self, row) -> DigitalHumanTemplate:
        return DigitalHumanTemplate(
            template_id=row[0],
            name=row[1],
            description=row[2] or "",
            video_path=row[3],
            face_data_path=row[4],
            preview_path=row[5],
            duration=row[6],
            resolution=row[7],
            fps=row[8],
            created_at=row[9],
            updated_at=row[10],
            metadata=json.loads(row[11]) if row[11] else {}
        )
    
    def import_existing_templates(self):
        if not self.template_dir.exists():
            return
        
        for template_id in os.listdir(self.template_dir):
            template_path = self.template_dir / template_id
            if not template_path.is_dir():
                continue
            
            meta_path = template_path / "meta.json"
            if meta_path.exists():
                continue
            
            video_path = template_path / "source.mp4"
            face_path = template_path / "face.pt"
            
            if video_path.exists() and face_path.exists():
                try:
                    self.create_template(
                        name=template_id,
                        video_path=str(video_path),
                        description="Imported template",
                        template_id=template_id
                    )
                    logger.info(f"Imported existing template: {template_id}")
                except Exception as e:
                    logger.error(f"Failed to import template {template_id}: {e}")
