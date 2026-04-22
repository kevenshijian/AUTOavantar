"""
IndexTTS 语音合成客户端
支持 IndexTTS REST API 协议（v0.2.0+）

替代旧的 Gradio 6.x API 客户端，与 IndexTTS API Server (api_server/) 配合使用。
对外接口保持兼容，调用方（AudioProcessor）无需修改。
"""

import logging
import os
import time
from typing import Dict, Any, List, Optional, Tuple

import requests

logger = logging.getLogger("autoavantar")


class IndexTTSClient:
    """
    IndexTTS 语音合成客户端 (REST API 兼容)

    与 IndexTTS API Server (api_server/) 通信，使用标准 REST API 协议。
    """

    def __init__(self, host: str, output_dir: Optional[str] = None):
        """
        初始化客户端

        Args:
            host: IndexTTS API Server 服务地址，如 http://localhost:7860
            output_dir: IndexTTS 输出目录路径（可选，提供则直接从目录获取音频）
        """
        self.host = host.rstrip("/")
        self.api_base = f"{self.host}/api/v1"
        self.output_dir = output_dir
        self.session = requests.Session()

        if self.output_dir:
            logger.info(f"IndexTTS 客户端初始化: {self.host}, 输出目录: {self.output_dir}")
        else:
            logger.info(f"IndexTTS 客户端初始化: {self.host}")

    def health_check(self) -> Dict[str, Any]:
        """
        检查服务健康状态

        Returns:
            健康状态字典
        """
        try:
            resp = self.session.get(f"{self.api_base}/health", timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"健康检查失败: {e}")
        return {"status": "error", "model_loaded": False}

    def unload_model(self) -> Dict[str, Any]:
        """
        卸载 IndexTTS 模型，释放 GPU 显存。

        适用于 TTS 完成后、HeyGem 视频生成前的显存释放。
        卸载后需要重启 IndexTTS 服务才能恢复。

        Returns:
            卸载结果字典，包含 success 和 message 字段
        """
        try:
            resp = self.session.post(f"{self.api_base}/unload", timeout=30)
            if resp.status_code == 200:
                result = resp.json()
                logger.info(f"IndexTTS 模型卸载: {result.get('message', '成功')}")
                return result
            else:
                logger.warning(f"IndexTTS 模型卸载失败: {resp.status_code} - {resp.text}")
                return {"success": False, "message": f"卸载请求失败: {resp.status_code}"}
        except Exception as e:
            logger.warning(f"IndexTTS 模型卸载异常: {e}")
            return {"success": False, "message": f"卸载异常: {e}"}

    def synthesize(
        self,
        text: str,
        prompt: str,
        speed: float = 1,
        voices_dropdown: str = "使用参考音频",
        emo_control_method: str = "使用情感向量控制",
        emo_ref_path: Optional[str] = None,
        emo_weight: float = 1,
        emo_text: str = "",
        emo_random: bool = False,
        max_tokens: int = 100,
        vec1: float = 0,
        vec2: float = 0,
        vec3: float = 0,
        vec4: float = 0,
        vec5: float = 0,
        vec6: float = 0,
        vec7: float = 0,
        vec8: float = 0,
        do_sample: bool = True,
        top_p: float = 0.8,
        top_k: int = 30,
        temperature: float = 0.8,
        length_penalty: float = 0,
        num_beams: int = 3,
        repetition_penalty: float = 10,
        max_mel: int = 1500,
        timeout: int = 600,
        emotion: Optional[str] = None,
        intensity: Optional[float] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        合成语音（兼容旧 Gradio 接口签名）

        内部将参数映射为 REST API 调用，通过 POST /api/v1/tts/synthesize 提交任务，
        然后轮询任务状态直到完成。

        优先使用 emotion + intensity 方式（推荐）：
            emotion: 情绪标签（如"开场"、"开心"等）
            intensity: 情绪强度 0.0~2.0

        兼容旧方式：
            vec1-vec8: 情感向量值（如果 emotion 未提供时使用）

        Args:
            text: 要合成的文本
            prompt: 音色参考音频路径
            speed: 语速（保留参数，REST API 暂不支持）
            voices_dropdown: 音色列表选项（忽略，使用 prompt 路径）
            emo_control_method: 情感控制方式（忽略）
            emo_ref_path: 情感参考音频路径（忽略）
            emo_weight: 情感权重（兼容旧方式）
            emo_text: 情感描述文本（忽略）
            emo_random: 情感随机采样（忽略）
            max_tokens: 分句最大 Token 数
            vec1-vec8: 情感向量值（兼容旧方式）
            do_sample: 是否采样
            top_p: 采样参数
            top_k: 采样参数
            temperature: 温度参数
            length_penalty: 长度惩罚（忽略）
            num_beams: beam 数量
            repetition_penalty: 重复惩罚（忽略）
            max_mel: 最大 mel tokens（忽略）
            timeout: 超时时间（秒）
            emotion: 情绪标签（推荐）
            intensity: 情绪强度 0.0~2.0（配合 emotion 使用）

        Returns:
            Tuple[str, Dict[str, Any]]: 任务 ID 和结果字典
        """
        # 构建请求体
        payload: Dict[str, Any] = {
            "text": text,
            "reference_audio": prompt,
            "inference_mode": "fast",
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "num_beams": num_beams,
        }

        # 优先使用 emotion + intensity 方式
        if emotion:
            payload["emotion"] = emotion
            if intensity is not None:
                payload["intensity"] = intensity
            else:
                payload["intensity"] = 1.0
            logger.info(f"使用情绪标签: {emotion}, 强度: {payload.get('intensity', 1.0)}")
        else:
            # 兼容旧方式：构建情感向量参数（非零时才传入）
            vec_map = {
                "vec1": vec1, "vec2": vec2, "vec3": vec3, "vec4": vec4,
                "vec5": vec5, "vec6": vec6, "vec7": vec7, "vec8": vec8,
            }
            if any(v != 0 for v in vec_map.values()):
                emotion_vec = vec_map
                payload["emotion_vec"] = emotion_vec
                logger.info(f"使用情感向量: {emotion_vec}")

        url = f"{self.api_base}/tts/synthesize"

        logger.info(f"调用 IndexTTS REST API: {url}")
        logger.info(f"文本长度: {len(text)}")
        logger.info(f"音色参考: {prompt}")

        try:
            # 提交任务
            resp = self.session.post(url, json=payload, timeout=60)

            if resp.status_code == 202:
                result = resp.json()
                task_id = result.get("task_id")
                queue_position = result.get("queue_position", 0)
                logger.info(f"任务已提交: {task_id}, 队列位置: {queue_position}")
            elif resp.status_code == 503:
                raise ConnectionError(f"IndexTTS 服务未就绪: {resp.json().get('detail', '未知错误')}")
            elif resp.status_code == 400:
                raise ValueError(f"IndexTTS 请求参数错误: {resp.json().get('detail', '未知错误')}")
            else:
                raise ConnectionError(f"IndexTTS API 请求失败: {resp.status_code} - {resp.text}")

            # 等待任务完成
            output = self._poll_task(task_id, timeout=timeout)

            return task_id, output

        except requests.exceptions.Timeout as e:
            logger.warning(f"IndexTTS API 超时: {e}")
            raise
        except requests.RequestException as e:
            logger.warning(f"IndexTTS API 请求失败: {e}")
            raise
        except Exception as e:
            logger.error(f"IndexTTS 合成失败: {e}")
            raise

    def _poll_task(self, task_id: str, timeout: int = 600, poll_interval: float = 2.0) -> Dict[str, Any]:
        """
        轮询任务状态直到完成

        Args:
            task_id: 任务 ID
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            任务结果字典

        Raises:
            TimeoutError: 超时
            RuntimeError: 任务失败
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                resp = self.session.get(
                    f"{self.api_base}/tasks/{task_id}",
                    timeout=30
                )

                if resp.status_code != 200:
                    logger.warning(f"查询任务状态失败: {resp.status_code}")
                    time.sleep(poll_interval)
                    continue

                data = resp.json()
                status = data.get("status")

                if status == "completed":
                    audio_url = data.get("audio_url")
                    audio_path_local = data.get("audio_path")
                    logger.info(f"任务完成: {task_id}, 音频: {audio_url}")

                    # 优先使用 API 返回的本地路径
                    if audio_path_local and os.path.exists(audio_path_local):
                        logger.info(f"使用 API 返回的本地音频路径: {audio_path_local}")
                        return {"status": "success", "audio_path": audio_path_local}

                    # 其次通过 URL 下载
                    if audio_url:
                        audio_path = self._download_audio(audio_url, task_id)
                        if audio_path:
                            return {"status": "success", "audio_path": audio_path}
                        else:
                            logger.warning(f"下载音频失败，尝试使用输出目录监听作为后备方案")

                    # 后备方案：从输出目录获取
                    if self.output_dir:
                        audio_path = self.get_latest_audio_from_output_dir(
                            after_time=start_time,
                            max_wait=10
                        )
                        if audio_path:
                            return {"status": "success", "audio_path": audio_path}

                    return {"status": "success", "audio_url": audio_url}

                elif status == "failed":
                    error_msg = data.get("error_message", "未知错误")
                    raise RuntimeError(f"IndexTTS 任务失败: {error_msg}")

                elif status in ("pending", "processing"):
                    logger.debug(f"任务 {task_id} 状态: {status}")
                    time.sleep(poll_interval)

            except (requests.RequestException, requests.Timeout) as e:
                logger.warning(f"轮询任务状态时出错: {e}")
                time.sleep(poll_interval)

        raise TimeoutError(f"IndexTTS 任务超时 ({timeout}秒)")

    def _download_audio(self, audio_url: str, task_id: str) -> Optional[str]:
        """
        从 API 下载音频文件

        Args:
            audio_url: 音频 URL（如 /api/v1/audio/xxx.wav）
            task_id: 任务 ID（用于命名文件）

        Returns:
            下载后的本地文件路径，失败返回 None
        """
        if self.output_dir:
            save_dir = self.output_dir
        else:
            save_dir = "."

        try:
            full_url = f"{self.host}{audio_url}"
            resp = self.session.get(full_url, timeout=60)
            if resp.status_code == 200:
                save_path = os.path.join(save_dir, f"{task_id}.wav")
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                logger.info(f"音频已下载: {save_path}")
                return save_path
        except Exception as e:
            logger.warning(f"下载音频失败: {e}")
        return None

    def refresh_outputs(self) -> Tuple[Dict[str, Any], str, str]:
        """
        刷新输出（兼容旧接口）

        Returns:
            Tuple[任务列表, 最新播放器路径, 最新下载路径]
        """
        # REST API 模式下无需刷新，直接返回空结果
        return {}, "", ""

    def get_latest_audio_from_output_dir(
        self,
        after_time: Optional[float] = None,
        max_wait: int = 60,
        check_interval: float = 2.0
    ) -> Optional[str]:
        """
        从 IndexTTS 输出目录直接获取最新生成的音频文件

        Args:
            after_time: 只考虑在此时间之后生成的文件（Unix 时间戳）
            max_wait: 最大等待时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            最新音频文件的完整路径，如果超时返回 None
        """
        if not self.output_dir or not os.path.exists(self.output_dir):
            logger.warning(f"输出目录不存在或未设置: {self.output_dir}")
            return None

        logger.info(f"开始监听输出目录: {self.output_dir}")
        start_time = time.time()
        last_checked_time = after_time or start_time

        while time.time() - start_time < max_wait:
            try:
                audio_files = []
                for filename in os.listdir(self.output_dir):
                    if filename.endswith('.wav'):
                        file_path = os.path.join(self.output_dir, filename)
                        file_mtime = os.path.getmtime(file_path)

                        if file_mtime >= last_checked_time:
                            audio_files.append((file_mtime, file_path))

                if audio_files:
                    audio_files.sort(reverse=True, key=lambda x: x[0])
                    latest_mtime, latest_file = audio_files[0]
                    logger.info(f"找到最新音频文件: {latest_file} (修改时间: {time.ctime(latest_mtime)})")
                    return latest_file

                logger.debug(f"等待新音频文件生成... ({int(time.time() - start_time)}/{max_wait}秒)")
                time.sleep(check_interval)

            except Exception as e:
                logger.error(f"监听输出目录时出错: {e}")
                time.sleep(check_interval)

        logger.error(f"等待超时 ({max_wait}秒)，未找到新的音频文件")
        return None

    def close(self):
        """关闭客户端"""
        self.session.close()
        logger.info("IndexTTS 客户端已关闭")


def create_indextts_client(host: str) -> IndexTTSClient:
    """
    创建 IndexTTS 客户端

    Args:
        host: IndexTTS 服务地址

    Returns:
        IndexTTSClient: IndexTTS 客户端实例
    """
    return IndexTTSClient(host=host)
