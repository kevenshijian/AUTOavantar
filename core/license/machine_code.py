"""
机器码生成模块
基于硬件信息生成唯一的机器标识
"""

import hashlib
import platform
import subprocess
from typing import Dict


def _run_powershell(command: str) -> str:
    """
    执行 PowerShell 命令并返回结果

    Args:
        command: PowerShell 命令

    Returns:
        命令输出结果
    """
    try:
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_hardware_ids() -> Dict[str, str]:
    """
    获取硬件ID

    使用 PowerShell Get-CimInstance 替代已弃用的 wmic 命令，
    兼容 Windows 10 21H2+ 和 Windows 11

    Returns:
        硬件ID字典
    """
    ids = {}

    if platform.system() != "Windows":
        return {"cpu": "unknown", "motherboard": "unknown", "disk": "unknown", "mac": "unknown"}

    # CPU ID
    try:
        result = _run_powershell("Get-CimInstance -ClassName Win32_Processor | Select-Object -ExpandProperty ProcessorId")
        if result:
            ids["cpu"] = result
        else:
            ids["cpu"] = "unknown"
    except Exception:
        ids["cpu"] = "unknown"

    # 主板序列号
    try:
        result = _run_powershell("Get-CimInstance -ClassName Win32_BaseBoard | Select-Object -ExpandProperty SerialNumber")
        if result:
            ids["motherboard"] = result
        else:
            ids["motherboard"] = "unknown"
    except Exception:
        ids["motherboard"] = "unknown"

    # 磁盘序列号
    try:
        result = _run_powershell("Get-CimInstance -ClassName Win32_DiskDrive | Select-Object -ExpandProperty SerialNumber")
        if result:
            ids["disk"] = result
        else:
            ids["disk"] = "unknown"
    except Exception:
        ids["disk"] = "unknown"

    # MAC 地址
    try:
        result = _run_powershell("Get-CimInstance -ClassName Win32_NetworkAdapter | Where-Object { $_.MACAddress } | Select-Object -ExpandProperty MACAddress -First 1")
        if result:
            ids["mac"] = result
        else:
            ids["mac"] = "unknown"
    except Exception:
        ids["mac"] = "unknown"

    return ids


def get_machine_code() -> str:
    """
    获取机器码

    基于多个硬件特征生成唯一标识

    Returns:
        机器码字符串 (16位)
    """
    hardware_ids = get_hardware_ids()

    # 组合所有硬件ID
    combined = "|".join([
        hardware_ids.get("cpu", ""),
        hardware_ids.get("motherboard", ""),
        hardware_ids.get("disk", ""),
        hardware_ids.get("mac", "")
    ])

    # 生成哈希
    hash_obj = hashlib.sha256(combined.encode())
    machine_code = hash_obj.hexdigest()[:16].upper()

    return machine_code


if __name__ == "__main__":
    print(f"机器码: {get_machine_code()}")
    print(f"硬件ID: {get_hardware_ids()}")
