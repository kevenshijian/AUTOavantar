"""
后期处理模块
"""

from .post_processor import (
    PostProcessor,
    PostProcessResult,
    create_post_processor
)
from .unified_subtitle_synchronizer import (
    UnifiedSubtitleSynchronizer,
    create_unified_subtitle_synchronizer
)
from .precise_subtitle_synchronizer import (
    PreciseSubtitleSynchronizer,
    create_precise_subtitle_synchronizer
)
from .smart_subtitle_synchronizer import (
    SmartSubtitleSynchronizer,
    create_smart_subtitle_synchronizer
)

__all__ = [
    "PostProcessor",
    "PostProcessResult",
    "create_post_processor",
    # 统一精确字幕同步器（推荐使用）
    "UnifiedSubtitleSynchronizer",
    "create_unified_subtitle_synchronizer",
    # 以下为旧版同步器，保留兼容
    "PreciseSubtitleSynchronizer",
    "create_precise_subtitle_synchronizer",
    "SmartSubtitleSynchronizer",
    "create_smart_subtitle_synchronizer",
]