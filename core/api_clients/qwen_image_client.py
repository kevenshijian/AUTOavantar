"""
Qwen-Image API 客户端
实现智能封面生成功能
"""

import logging
import os
import requests
import base64
import uuid
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class QwenImageClient:
    """Qwen-Image API 客户端"""

    def __init__(
        self,
        api_key: str,
        model: str = "qwen-image-2.0-pro"
    ):
        """
        初始化 Qwen-Image 客户端

        Args:
            api_key: API 密钥
            model: 模型名称，默认 qwen-image-2.0-pro
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://dashscope.aliyuncs.com/api/v1"

        logger.info(f"Qwen-Image 客户端初始化完成，模型：{model}")

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        size: str = "1024*1024",
        n: int = 1,
        output_dir: str = "output/covers"
    ) -> Optional[str]:
        """
        生成图片

        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词
            size: 图片尺寸，默认 1024*1024
            n: 生成数量
            output_dir: 输出目录

        Returns:
            生成的图片路径，失败返回 None
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"text": prompt}
                            ]
                        }
                    ]
                },
                "parameters": {
                    "size": size,
                    "n": n,
                    "negative_prompt": negative_prompt or " ",
                    "prompt_extend": True,
                    "watermark": False
                }
            }

            response = requests.post(
                f"{self.base_url}/services/aigc/multimodal-generation/generation",
                headers=headers,
                json=payload,
                timeout=120
            )

            response.raise_for_status()
            result = response.json()

            image_urls = self._extract_image_urls(result)
            if not image_urls:
                logger.error(f"API 未返回图像链接：{self._extract_error_message(result)}")
                return None

            image_path = self._download_image(image_urls[0], output_dir)
            logger.info(f"图片生成成功：{image_path}")
            return image_path

        except Exception as e:
            logger.error(f"生成图片失败：{e}")
            return None

    def generate_image_from_reference(
        self,
        prompt: str,
        reference_image_path: str,
        strength: float = 0.5,
        negative_prompt: str = "",
        size: str = "1024*1024",
        output_dir: str = "output/covers"
    ) -> Optional[str]:
        """
        基于参考图生成图片（Image-to-Image）

        Args:
            prompt: 正向提示词
            reference_image_path: 参考图片路径
            strength: 参考强度 (0-1)，默认 0.5
            negative_prompt: 负向提示词
            size: 图片尺寸
            output_dir: 输出目录

        Returns:
            生成的图片路径，失败返回 None
        """
        try:
            image_base64 = self._encode_image(reference_image_path)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"image": image_base64},
                                {"text": prompt}
                            ]
                        }
                    ]
                },
                "parameters": {
                    "size": size,
                    "n": 1,
                    "negative_prompt": negative_prompt or " ",
                    "prompt_extend": True,
                    "watermark": False
                }
            }

            response = requests.post(
                f"{self.base_url}/services/aigc/multimodal-generation/generation",
                headers=headers,
                json=payload,
                timeout=120
            )

            response.raise_for_status()
            result = response.json()

            image_urls = self._extract_image_urls(result)
            if not image_urls:
                logger.error(f"API 未返回图像链接：{self._extract_error_message(result)}")
                return None

            image_path = self._download_image(image_urls[0], output_dir)
            logger.info(f"基于参考图生成图片成功：{image_path}")
            return image_path

        except Exception as e:
            logger.error(f"基于参考图生成图片失败：{e}")
            return None

    def _encode_image(self, image_path: str) -> str:
        """将图片编码为Base64字符串"""
        mime_type = self._get_mime_type(image_path)
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _get_mime_type(self, file_path: str) -> str:
        """获取文件的MIME类型"""
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".webp": "image/webp",
            ".gif": "image/gif"
        }
        return mime_types.get(ext, "image/png")

    def _download_image(self, url: str, output_dir: str) -> str:
        """下载图片"""
        os.makedirs(output_dir, exist_ok=True)

        response = requests.get(url, timeout=60)
        response.raise_for_status()

        filename = f"cover_{uuid.uuid4().hex}.png"
        output_path = os.path.join(output_dir, filename)

        with open(output_path, "wb") as f:
            f.write(response.content)

        return output_path

    def _extract_image_urls(self, result: Dict[str, Any]) -> List[str]:
        """
        从返回 JSON 中提取图像 URL 列表。

        说明：HTTP 直调与 SDK 返回结构略有差异，本方法做兼容解析。
        """
        try:
            output = result.get("output") or {}
            choices = output.get("choices") or []
            if not choices:
                return []

            # choice.message.content: [{ "image": "..." }, ...]
            message = (choices[0] or {}).get("message") or {}
            contents = message.get("content") or []
            urls: List[str] = []
            for c in contents:
                if isinstance(c, dict) and c.get("image"):
                    urls.append(c["image"])
            return urls
        except Exception:
            return []

    def _extract_error_message(self, result: Dict[str, Any]) -> str:
        """提取错误信息，便于日志定位。"""
        try:
            code = result.get("code") or ""
            message = result.get("message") or ""
            if code or message:
                return f"{code} - {message}".strip(" -")
            return str(result)[:300]
        except Exception:
            return "unknown error"

    def test_connection(self) -> bool:
        """测试连接"""
        try:
            # 使用公网 URL 作为输入图，避免本地/编码差异导致的解析失败
            # （更贴近官方文档的调用方式）。
            test_image_url = (
                "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/"
                "zh-CN/20260310/rdsgaa/image+%2815%29.png"
            )

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"image": test_image_url},
                                {"text": "保持图片主体不变，整体提高清晰度与质感，输出一张高质量封面图。"}
                            ]
                        }
                    ]
                },
                "parameters": {
                    "size": "512*512",
                    "n": 1,
                    "negative_prompt": " ",
                    "prompt_extend": True,
                    "watermark": False
                }
            }

            response = requests.post(
                f"{self.base_url}/services/aigc/multimodal-generation/generation",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            return bool(self._extract_image_urls(result))
        except Exception as e:
            logger.error(f"连接测试失败：{e}")
            return False


def create_qwen_image_client(
    api_key: str,
    model: str = "qwen-image-2.0-pro"
) -> QwenImageClient:
    """创建 Qwen-Image 客户端的便捷函数"""
    return QwenImageClient(api_key=api_key, model=model)
