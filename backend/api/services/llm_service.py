"""
LLM服务模块
提供文案生成功能
"""

import json
import logging
import os
import re
from typing import Optional

import httpx

logger = logging.getLogger("autoavantar-api.llm")


class LLMScriptGenerator:
    """LLM文案生成器"""
    
    def __init__(self, provider: str, api_key: str, model: str):
        """初始化LLM文案生成器"""
        self.provider = provider
        self.api_key = api_key
        self.model = model
        logger.info(f"LLM 文案生成器初始化成功，提供商: {provider}, 模型: {model}")
    
    async def generate(self, prompt: str) -> str:
        """生成文案
        
        Args:
            prompt: 提示词（已包含主题的完整提示词）
            
        Returns:
            生成的文案（JSON格式）
        """
        if not self.api_key:
            raise ValueError("DeepSeek API Key 未配置，请在设置中配置 API Key")
        
        logger.info(f"开始调用 DeepSeek API 生成文案，提示词: {prompt[:100]}...")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 2048
                    }
                )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"DeepSeek API 调用失败，状态码: {response.status_code}, 响应: {error_detail}")
                    raise Exception(f"API 调用失败: {error_detail}")
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                logger.info(f"DeepSeek API 调用成功，生成文案长度: {len(content)}")
                
                # 尝试提取 JSON 内容
                script = self._extract_json(content)
                
                return script
                
        except httpx.RequestError as e:
            logger.error(f"DeepSeek API 请求失败: {e}")
            raise Exception(f"API 请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"文案生成失败: {e}")
            raise
    
    def _extract_json(self, content: str) -> str:
        """从返回内容中提取 JSON 字符串
        
        Args:
            content: API 返回的内容
            
        Returns:
            JSON 字符串
        """
        # 尝试直接解析
        try:
            json.loads(content)
            return content
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json ... ``` 包裹的内容
        json_pattern = r'```(?:json)?\s*([\s\S]*?)```'
        matches = re.findall(json_pattern, content)
        for match in matches:
            try:
                json.loads(match.strip())
                return match.strip()
            except json.JSONDecodeError:
                continue
        
        # 尝试提取第一个 { 到最后一个 } 之间的内容
        first_brace = content.find('{')
        last_brace = content.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            potential_json = content[first_brace:last_brace + 1]
            try:
                json.loads(potential_json)
                return potential_json
            except json.JSONDecodeError:
                pass
        
        # 如果都无法解析，返回原始内容
        logger.warning("无法从返回内容中提取 JSON，返回原始内容")
        return content


def create_script_generator(provider: str, api_key: str, model: str) -> LLMScriptGenerator:
    """创建LLM文案生成器实例
    
    Args:
        provider: LLM提供商
        api_key: API密钥
        model: 模型名称
        
    Returns:
        LLMScriptGenerator实例
    """
    return LLMScriptGenerator(provider, api_key, model)
