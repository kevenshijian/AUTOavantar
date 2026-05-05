"""
加密验证模块
处理激活码的加密验证
"""

import base64
import hashlib
import json
from typing import Any, Dict, Optional


def verify_activation_code(
    activation_code: str,
    machine_code: str,
    public_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    验证激活码

    Args:
        activation_code: 激活码
        machine_code: 机器码
        public_key: 公钥（可选）

    Returns:
        验证结果字典
    """
    try:
        # 解码激活码
        # 格式: BASE64(JSON数据).签名
        parts = activation_code.split(".")
        if len(parts) != 2:
            return {"valid": False, "error": "激活码格式无效"}

        # 解码数据部分
        try:
            data_json = base64.urlsafe_b64decode(parts[0] + "==").decode("utf-8")
            data = json.loads(data_json)
        except Exception:
            return {"valid": False, "error": "激活码数据解析失败"}

        # 验证机器码
        if data.get("machine_code") != machine_code:
            return {"valid": False, "error": "激活码与当前机器不匹配"}

        # 验证签名（如果有公钥）
        if public_key:
            if not verify_signature(parts[0], parts[1], public_key):
                return {"valid": False, "error": "激活码签名验证失败"}

        # 检查过期时间
        if data.get("expires_at"):
            from datetime import datetime
            expires = datetime.fromisoformat(data["expires_at"])
            if datetime.now() > expires:
                return {"valid": False, "error": "激活码已过期"}

        return {
            "valid": True,
            "max_quota": data.get("max_quota", 10),
            "contact_info": data.get("contact_info", {}),
            "expires_at": data.get("expires_at")
        }

    except Exception as e:
        return {"valid": False, "error": f"验证失败: {str(e)}"}


def verify_signature(data: str, signature: str, public_key: str) -> bool:
    """
    验证签名

    Args:
        data: 原始数据
        signature: 签名
        public_key: 公钥

    Returns:
        签名是否有效
    """
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.exceptions import InvalidSignature

        # 加载公钥
        pub_key = load_pem_public_key(public_key.encode())

        # 解码签名
        sig_bytes = base64.urlsafe_b64decode(signature + "==")

        # 验证签名
        pub_key.verify(
            sig_bytes,
            data.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        return True

    except ImportError:
        # 如果没有安装 cryptography，使用简单验证
        return simple_verify(data, signature, public_key)
    except InvalidSignature:
        return False
    except Exception:
        return False


def simple_verify(data: str, signature: str, public_key: str) -> bool:
    """
    简单验证（不使用加密库）

    仅用于开发测试，生产环境应使用正式签名验证
    """
    # 计算预期签名
    expected = hashlib.sha256((data + public_key[:32]).encode()).hexdigest()[:32]
    return signature[:32] == expected


def generate_activation_code(
    machine_code: str,
    max_quota: int = 10,
    contact_info: Optional[Dict] = None,
    private_key: Optional[str] = None
) -> str:
    """
    生成激活码

    Args:
        machine_code: 机器码
        max_quota: 最大配额
        contact_info: 联系信息
        private_key: 私钥（可选）

    Returns:
        激活码字符串
    """
    data = {
        "machine_code": machine_code,
        "max_quota": max_quota,
        "contact_info": contact_info or {},
        "created_at": __import__("datetime").datetime.now().isoformat()
    }

    # 编码数据
    data_json = json.dumps(data, ensure_ascii=False)
    data_b64 = base64.urlsafe_b64encode(data_json.encode()).decode().rstrip("=")

    # 生成签名
    if private_key:
        signature = sign_data(data_b64, private_key)
    else:
        # 简单签名（开发用）
        signature = hashlib.sha256(data_b64.encode()).hexdigest()[:32]

    return f"{data_b64}.{signature}"


def sign_data(data: str, private_key: str) -> str:
    """
    使用私钥签名数据

    Args:
        data: 待签名数据
        private_key: 私钥

    Returns:
        签名字符串
    """
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        # 加载私钥
        priv_key = load_pem_private_key(private_key.encode(), password=None)

        # 签名
        signature = priv_key.sign(
            data.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        return base64.urlsafe_b64encode(signature).decode().rstrip("=")

    except ImportError:
        # 简单签名
        return hashlib.sha256((data + private_key[:32]).encode()).hexdigest()[:32]
    except Exception as e:
        raise RuntimeError(f"签名失败: {e}")
