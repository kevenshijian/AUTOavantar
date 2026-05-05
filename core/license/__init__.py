"""
授权模块初始化
"""

from core.license.machine_code import get_machine_code
from core.license.crypto import verify_activation_code
from core.license.hardware_match import get_hardware_ids

__all__ = [
    'get_machine_code',
    'verify_activation_code',
    'get_hardware_ids'
]