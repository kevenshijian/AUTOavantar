"""
硬件匹配模块
用于验证激活码与硬件的匹配
"""

from typing import Dict


def get_hardware_ids() -> Dict[str, str]:
    """
    获取硬件ID（从 machine_code 模块导入）
    """
    from core.license.machine_code import get_hardware_ids as _get_hardware_ids
    return _get_hardware_ids()


def check_hardware_match(expected_ids: Dict[str, str]) -> bool:
    """
    检查硬件是否匹配

    Args:
        expected_ids: 预期的硬件ID

    Returns:
        是否匹配
    """
    current_ids = get_hardware_ids()

    # 至少需要匹配2个硬件特征
    match_count = 0
    for key in ["cpu", "motherboard", "disk"]:
        if expected_ids.get(key) == current_ids.get(key):
            match_count += 1

    return match_count >= 2


def get_hardware_signature() -> str:
    """
    获取硬件签名

    Returns:
        硬件签名字符串
    """
    ids = get_hardware_ids()
    return f"{ids.get('cpu', 'N/A')}-{ids.get('motherboard', 'N/A')}"