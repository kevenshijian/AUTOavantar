from fastapi import APIRouter
from app.models import HealthResponse
from app.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    settings = get_settings()
    
    models_loaded = False
    try:
        models_dir = settings.DINET_MODEL_DIR
        dinet_path = models_dir / settings.DINET_MODEL
        models_loaded = dinet_path.exists()
    except:
        pass
    
    gpu_available = False
    try:
        import torch
        gpu_available = torch.cuda.is_available()
    except ImportError:
        pass
    
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        models_loaded=models_loaded,
        gpu_available=gpu_available
    )
