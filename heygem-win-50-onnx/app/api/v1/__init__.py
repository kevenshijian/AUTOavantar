from .digital_human import router as digital_human_router
from .templates import router as templates_router
from .health import router as health_router

__all__ = ['digital_human_router', 'templates_router', 'health_router']
