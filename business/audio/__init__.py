"""
音频模块
"""

from .audio_processor import (
    AudioProcessor,
    AudioSegmentResult,
    create_audio_processor
)

__all__ = [
    "AudioProcessor",
    "AudioSegmentResult",
    "create_audio_processor",
]