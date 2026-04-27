"""
HeyGem 视频生成客户端 (新 API 版本)
使用简单的 GET 请求调用 HeyGem 服务，返回视频 URL
"""

import logging
import requests
from typing import Optional, Tuple, Dict, Any
import os
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("autoavantar")


class HeyGemClient:

    def __init__(self, host: str, output_dir: Optional[str] = None):
        """
        初始化客户端

        Args:
            host: HeyGem 服务地址，如 http://localhost:9889
            output_dir: HeyGem 输出目录路径（已废弃，保留兼容性）
        """
        self.host = host.rstrip("/")
        self.output_dir = output_dir
        self.session = requests.Session()
        
        logger.info(f"HeyGem 客户端初始化: {self.host}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
        reraise=True
    )
    def generate_video(
        self,
        audio_file: str,
        video_file: str,
        face_id: int = 0,
        ifface: bool = True,
        steps: int = 16,
        timeout: int = 300
    ):
        """
        生成视频（新 API 版本）

        Args:
            audio_file: 音频文件路径
            video_file: 视频文件路径
            face_id: 面部编号，0=左边说话人，1=右边说话人，单人模式默认 0
            ifface: 是否使用原始参数模式，True=使用原始参数，False=不使用
            timeout: 超时时间（秒）

        Returns:
            生成结果视频路径、任务信息、下载视频路径
        """
        # 记录开始时间
        start_time = time.time()

        # 构建请求参数
        params = {
            "video_file": video_file,
            "audio_file": audio_file,
            "ifface": str(ifface).lower(),
            "face_id": face_id,
            "steps": steps
        }

        logger.info(f"调用 HeyGem 新 API: {self.host}/")
        logger.info(f"视频文件: {video_file}")
        logger.info(f"音频文件: {audio_file}")
        logger.info(f"使用原始参数: {ifface}")
        logger.info(f"面部编号: {face_id}")
        logger.info(f"推理步数: {steps}")
        
        try:
            # 发送 GET 请求
            response = self.session.get(
                self.host,
                params=params,
                timeout=timeout
            )
            
            if response.status_code != 200:
                error_msg = f"HeyGem API 请求失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise ConnectionError(error_msg)
            
            # 解析响应
            result = response.json()
            status = result.get("status")
            
            if status != "success":
                error_msg = result.get("message", "未知错误")
                logger.error(f"HeyGem 任务失败: {error_msg}")
                raise RuntimeError(f"HeyGem 任务失败: {error_msg}")
            
            # 获取输出视频 URL
            output_video_url = result.get("output_video_url")
            # 检查 URL 是否有效（非空且非空字符串）
            if not output_video_url or not output_video_url.strip():
                error_msg = result.get("message", "未知错误")
                logger.error(f"HeyGem 返回无效的视频 URL: '{output_video_url}', 错误信息: {error_msg}")
                raise ValueError(f"HeyGem 返回无效的视频 URL: '{output_video_url}'")
            
            logger.info(f"HeyGem 任务成功完成，耗时: {time.time() - start_time:.2f} 秒")
            logger.info(f"输出视频 URL: {output_video_url}")
            
            # 下载视频文件到本地
            video_path = self._download_video(output_video_url)
            
            if video_path:
                return video_path, "", video_path
            else:
                return output_video_url, "", output_video_url

        except requests.Timeout as e:
            logger.warning(f"HeyGem API 超时，将重试: {e}")
            raise
        except requests.RequestException as e:
            logger.warning(f"HeyGem API 请求失败，将重试: {e}")
            raise

    def _download_video(self, video_url: str) -> Optional[str]:
        """
        下载视频文件到本地

        Args:
            video_url: 视频 URL

        Returns:
            本地视频文件路径，失败返回 None
        """
        try:
            # 从 URL 中提取文件名，或生成临时文件名
            if video_url.startswith("http"):
                filename = os.path.basename(video_url)
                if not filename or not filename.endswith(".mp4"):
                    filename = f"video_{int(time.time())}.mp4"
            else:
                # 如果是本地路径，直接返回
                if os.path.exists(video_url):
                    return video_url
                filename = os.path.basename(video_url)
            
            # 确定保存目录
            if self.output_dir and os.path.exists(self.output_dir):
                save_dir = self.output_dir
            else:
                save_dir = os.getcwd()
            
            save_path = os.path.join(save_dir, filename)
            
            # 如果是本地路径，尝试复制
            if not video_url.startswith("http"):
                if os.path.exists(video_url):
                    import shutil
                    shutil.copy2(video_url, save_path)
                    logger.info(f"视频已复制: {video_url} -> {save_path}")
                    return save_path
                else:
                    logger.warning(f"视频文件不存在: {video_url}")
                    return None
            
            # 从 URL 下载
            logger.info(f"正在下载视频: {video_url}")
            response = self.session.get(video_url, timeout=300)
            
            if response.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"视频已下载: {save_path}")
                return save_path
            else:
                logger.error(f"下载视频失败: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"下载视频时出错: {e}")
            return None

    def cleanup_gpu(self):
        """
        触发 HeyGem 服务的 GPU 显存清理（工作流所有任务完成后调用）
        调用 /api/v1/gpu/release 端点释放显存
        
        注意：不要在每个 generate_video 后自动调用，因为 cy_app 内部使用
        multiprocessing，过于频繁的 gc.collect 会破坏子进程的共享状态。
        应在工作流级别，所有视频段落生成完毕后调用一次。
        """
        try:
            cleanup_url = f"{self.host}/api/v1/gpu/release"
            resp = self.session.post(cleanup_url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"[GPU Cleanup] HeyGem 显存释放成功: released={data.get('released_models', [])}")
            else:
                logger.warning(f"[GPU Cleanup] HeyGem 显存释放失败: {resp.status_code} - {resp.text}")
        except requests.RequestException as e:
            logger.warning(f"[GPU Cleanup] HeyGem 显存释放请求失败: {e}")

    def close(self):
        """
        关闭客户端
        """
        if hasattr(self, 'session') and self.session:
            self.session.close()
            logger.info("HeyGem 客户端已关闭")


def create_heygem_client(host: str) -> HeyGemClient:
    """
    创建 HeyGem 客户端

    Args:
        host: HeyGem 服务地址

    Returns:
        HeyGemClient: HeyGem 客户端实例
    """
    return HeyGemClient(host=host)
