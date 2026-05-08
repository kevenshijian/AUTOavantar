"""
加密验证模块
处理激活码的加密验证

安全特性：
- RSA-2048 + SHA-256 签名验证
- 时序攻击防护（使用 hmac.compare_digest）
- 输入长度限制
- 强制公钥验证
"""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Literal, Optional


# ============================================================
# 安全常量
# ============================================================
# 激活码最大长度（防止内存耗尽攻击）
MAX_ACTIVATION_CODE_LENGTH = 2048

# 激活类型定义
LicenseType = Literal["yearly", "three_year", "lifetime"]

# 激活类型对应的有效期天数
LICENSE_TYPE_DAYS = {
    "yearly": 365,
    "three_year": 1095,
    "lifetime": None  # 终身无过期
}


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
        public_key: 公钥（必需，安全优先）

    Returns:
        验证结果字典
    """
    try:
        # 安全检查：激活码长度限制
        if len(activation_code) > MAX_ACTIVATION_CODE_LENGTH:
            return {"valid": False, "error": "激活码格式无效"}

        # 安全检查：公钥必须存在
        if not public_key:
            return {"valid": False, "error": "系统配置错误"}

        # 解码激活码
        # 格式: BASE64(JSON数据).签名
        parts = activation_code.split(".")
        if len(parts) != 2:
            return {"valid": False, "error": "激活码格式无效"}

        # 安全检查：各部分长度限制
        if len(parts[0]) > MAX_ACTIVATION_CODE_LENGTH or len(parts[1]) > MAX_ACTIVATION_CODE_LENGTH:
            return {"valid": False, "error": "激活码格式无效"}

        # 解码数据部分
        try:
            data_json = base64.urlsafe_b64decode(parts[0] + "==").decode("utf-8")
            data = json.loads(data_json)
        except Exception:
            return {"valid": False, "error": "激活码数据解析失败"}

        # 验证机器码（使用时序安全比较）
        stored_machine_code = data.get("machine_code", "")
        if not hmac.compare_digest(stored_machine_code, machine_code):
            return {"valid": False, "error": "激活码与当前机器不匹配"}

        # 验证签名（强制验证）
        if not verify_signature(parts[0], parts[1], public_key):
            return {"valid": False, "error": "激活码签名验证失败"}

        # 检查过期时间
        if data.get("expires_at"):
            expires = datetime.fromisoformat(data["expires_at"])
            if datetime.now() > expires:
                return {"valid": False, "error": "激活码已过期"}

        return {
            "valid": True,
            "max_quota": data.get("max_quota", 10),
            "contact_info": data.get("contact_info", {}),
            "license_type": data.get("license_type", "yearly"),  # 安全默认值
            "expires_at": data.get("expires_at")
        }

    except Exception:
        # 安全：不泄露异常详情
        return {"valid": False, "error": "验证失败"}


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
        # cryptography 库未安装，无法验证签名
        # 这是安全关键操作，不允许降级
        import logging
        logging.getLogger("license").error(
            "cryptography 库未安装，无法验证激活码签名。"
            "请安装: pip install cryptography"
        )
        return False
    except InvalidSignature:
        return False
    except Exception:
        return False


def generate_activation_code(
    machine_code: str,
    max_quota: int = 10,
    contact_info: Optional[Dict] = None,
    private_key: Optional[str] = None,
    license_type: LicenseType = "yearly"
) -> str:
    """
    生成激活码

    Args:
        machine_code: 机器码
        max_quota: 最大配额
        contact_info: 联系信息
        private_key: 私钥（必需）
        license_type: 激活类型（yearly/three_year/lifetime）

    Returns:
        激活码字符串

    Raises:
        ValueError: 未提供私钥或激活类型无效时
    """
    if private_key is None:
        raise ValueError(
            "生成激活码必须提供私钥。"
            "安全要求：不允许生成无签名的激活码。"
        )

    if license_type not in LICENSE_TYPE_DAYS:
        raise ValueError(
            f"无效的激活类型: {license_type}。"
            f"有效类型: {list(LICENSE_TYPE_DAYS.keys())}"
        )

    # 计算过期时间
    expires_at = None
    if license_type != "lifetime":
        days = LICENSE_TYPE_DAYS[license_type]
        expires_at = (datetime.now() + timedelta(days=days)).isoformat()

    data = {
        "machine_code": machine_code,
        "max_quota": max_quota,
        "contact_info": contact_info or {},
        "license_type": license_type,
        "expires_at": expires_at,
        "created_at": datetime.now().isoformat()
    }

    # 编码数据
    data_json = json.dumps(data, ensure_ascii=False)
    data_b64 = base64.urlsafe_b64encode(data_json.encode()).decode().rstrip("=")

    # 使用私钥签名
    signature = sign_data(data_b64, private_key)

    return f"{data_b64}.{signature}"


def sign_data(data: str, private_key: str) -> str:
    """
    使用私钥签名数据

    Args:
        data: 待签名数据
        private_key: 私钥

    Returns:
        签名字符串

    Raises:
        RuntimeError: 签名失败或 cryptography 库未安装
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
        raise RuntimeError(
            "cryptography 库未安装，无法签名激活码。"
            "请安装: pip install cryptography"
        )
    except Exception as e:
        raise RuntimeError(f"签名失败: {e}")
