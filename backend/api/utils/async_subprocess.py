"""
异步 subprocess 工具模块
提供非阻塞的 subprocess 执行，避免阻塞 FastAPI 事件循环
"""

import asyncio
import logging
import platform
import subprocess
from typing import List, Optional, Tuple

logger = logging.getLogger("async_subprocess")

# Windows 平台静默创建进程的标志
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


async def async_run_subprocess(
    cmd: List[str],
    timeout: Optional[float] = None,
    check: bool = False,
    **kwargs
) -> Tuple[int, bytes, bytes]:
    """
    异步执行 subprocess 命令，替代 subprocess.run

    使用 asyncio.create_subprocess_exec 实现，不会阻塞事件循环。

    Args:
        cmd: 命令列表，如 ["ffmpeg", "-i", "input.mp4", "output.mp4"]
        timeout: 超时时间（秒），None 表示不超时
        check: 是否检查返回码（非0时抛出异常）
        **kwargs: 传递给 asyncio.create_subprocess_exec 的额外参数

    Returns:
        (returncode, stdout, stderr) 元组
    """
    creationflags = kwargs.pop("creationflags", CREATE_NO_WINDOW)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=creationflags,
            **kwargs
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )

        if check and process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode, cmd,
                stdout, stderr
            )

        return process.returncode, stdout, stderr

    except asyncio.TimeoutError:
        try:
            process.kill()
            await process.wait()
        except Exception:
            pass
        logger.warning(f"命令超时 ({timeout}s): {cmd[0]}")
        return -1, b"", b"timeout"

    except Exception as e:
        logger.error(f"命令执行失败: {e}")
        raise


async def async_run_ffprobe(
    video_path: str,
    entries: str = "format=duration",
    output_format: str = "json"
) -> dict:
    """
    异步执行 ffprobe 获取视频信息

    Args:
        video_path: 视频文件路径
        entries: ffprobe show_entries 参数
        output_format: 输出格式

    Returns:
        解析后的 JSON 数据字典
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", entries,
        "-of", output_format,
        video_path
    ]

    returncode, stdout, stderr = await async_run_subprocess(cmd)

    if returncode != 0:
        logger.error(f"ffprobe 失败: {stderr.decode() if stderr else ''}")
        return {}

    try:
        import json
        return json.loads(stdout.decode())
    except Exception:
        return {}


async def async_run_ffmpeg(cmd: List[str], timeout: Optional[float] = None) -> Tuple[int, bytes, bytes]:
    """
    异步执行 FFmpeg 命令

    自动添加 -y 参数（覆盖输出）和 Windows creationflags。

    Args:
        cmd: FFmpeg 命令列表（不含 -y）
        timeout: 超时时间（秒）

    Returns:
        (returncode, stdout, stderr) 元组
    """
    # 确保包含 -y 参数（覆盖输出文件）
    if "-y" not in cmd:
        cmd = [cmd[0], "-y"] + cmd[1:]

    return await async_run_subprocess(cmd, timeout=timeout)