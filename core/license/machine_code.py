"""
机器码生成模块
基于硬件信息生成唯一的机器标识
"""

import hashlib
import platform
import subprocess
from typing import Dict


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


def get_hardware_ids() -> Dict[str, str]:
    """
    获取硬件ID

    Returns:
        硬件ID字典
    """
    ids = {}

    # CPU ID
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "cpu", "get", "ProcessorId"],
                capture_output=True,
                text=True,
                timeout=10
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                ids["cpu"] = lines[1].strip()
    except Exception:
        ids["cpu"] = "unknown"

    # 主板序列号
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "baseboard", "get", "SerialNumber"],
                capture_output=True,
                text=True,
                timeout=10
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                ids["motherboard"] = lines[1].strip()
    except Exception:
        ids["motherboard"] = "unknown"

    # 磁盘序列号
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "diskdrive", "get", "SerialNumber"],
                capture_output=True,
                text=True,
                timeout=10
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                ids["disk"] = lines[1].strip()
    except Exception:
        ids["disk"] = "unknown"

    # MAC 地址
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "nic", "get", "MACAddress"],
                capture_output=True,
                text=True,
                timeout=10
            )
            lines = result.stdout.strip().split("\n")
            macs = [line.strip() for line in lines[1:] if line.strip()]
            if macs:
                ids["mac"] = macs[0]  # 使用第一个MAC地址
    except Exception:
        ids["mac"] = "unknown"

    return ids


if __name__ == "__main__":
    print(f"机器码: {get_machine_code()}")
    print(f"硬件ID: {get_hardware_ids()}")
