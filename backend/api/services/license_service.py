"""
授权服务层
处理激活状态检查、激活码验证、配额管理等核心业务逻辑
"""

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel

logger = logging.getLogger("autoavantar.license")


class LicenseStatus(BaseModel):
    """许可证状态"""
    is_activated: bool
    machine_code: str
    remaining_quota: int
    max_quota: int
    activation_time: Optional[str] = None
    contact_info: Dict[str, str] = {}


class ActivationResult(BaseModel):
    """激活结果"""
    success: bool
    message: str
    remaining_quota: int = 0
    max_quota: int = 0


class QuotaCheckResult(BaseModel):
    """配额检查结果"""
    has_quota: bool
    remaining: int
    max_quota: int
    message: str = ""


class LicenseService:
    """
    授权服务 - 单例模式

    核心职责：
    1. 管理激活状态
    2. 验证激活码
    3. 管理配额
    """

    MAX_DAILY_QUOTA = 10
    LICENSE_FILENAME = "license.key"
    LICENSE_BACKUP_DIR = Path.home() / ".autoavantar"
    QUOTA_REGISTRY_KEY = "AutoAvantar"
    QUOTA_REGISTRY_VALUE = "DailyQuota"

    def __init__(self):
        self._public_key: Optional[str] = None
        self._license_data: Optional[Dict] = None
        self._init_public_key()

    def _init_public_key(self) -> None:
        """初始化公钥"""
        key_path = Path(__file__).parent.parent.parent / "config" / "license" / "public_key.pem"
        if key_path.exists():
            with open(key_path, 'r', encoding='utf-8') as f:
                self._public_key = f.read()
            logger.info("公钥已加载")
        else:
            logger.warning(f"公钥文件不存在: {key_path}")

    def get_machine_code(self) -> str:
        """
        获取机器码

        Returns:
            机器码字符串
        """
        from core.license.machine_code import get_machine_code as _get_machine_code
        return _get_machine_code()

    def get_license_status(self) -> LicenseStatus:
        """
        获取许可证状态

        Returns:
            LicenseStatus 对象
        """
        machine_code = self.get_machine_code()

        # 尝试加载许可证
        license_data = self._load_license()
        if license_data is None:
            return LicenseStatus(
                is_activated=False,
                machine_code=machine_code,
                remaining_quota=0,
                max_quota=0
            )

        # 验证许可证
        if not self._verify_license(license_data, machine_code):
            return LicenseStatus(
                is_activated=False,
                machine_code=machine_code,
                remaining_quota=0,
                max_quota=0
            )

        # 获取配额
        remaining = self._get_remaining_quota()

        return LicenseStatus(
            is_activated=True,
            machine_code=machine_code,
            remaining_quota=remaining,
            max_quota=self.MAX_DAILY_QUOTA,
            activation_time=license_data.get("activation_time"),
            contact_info=license_data.get("contact_info", {})
        )

    def activate(self, activation_code: str) -> ActivationResult:
        """
        激活许可证

        Args:
            activation_code: 激活码

        Returns:
            ActivationResult 对象
        """
        from core.license.crypto import verify_activation_code

        machine_code = self.get_machine_code()

        # 验证激活码
        result = verify_activation_code(activation_code, machine_code, self._public_key)
        if not result.get("valid"):
            return ActivationResult(
                success=False,
                message=result.get("error", "激活码无效")
            )

        # 保存许可证
        license_data = {
            "activation_code": activation_code,
            "machine_code": machine_code,
            "activation_time": datetime.now().isoformat(),
            "max_quota": result.get("max_quota", self.MAX_DAILY_QUOTA),
            "contact_info": result.get("contact_info", {})
        }

        self._save_license(license_data)
        self._license_data = license_data

        # 初始化配额
        self._save_quota(license_data.get("max_quota", self.MAX_DAILY_QUOTA))

        return ActivationResult(
            success=True,
            message="激活成功",
            remaining_quota=license_data.get("max_quota", self.MAX_DAILY_QUOTA),
            max_quota=license_data.get("max_quota", self.MAX_DAILY_QUOTA)
        )

    def check_quota(self) -> QuotaCheckResult:
        """
        检查配额

        Returns:
            QuotaCheckResult 对象
        """
        status = self.get_license_status()

        if not status.is_activated:
            return QuotaCheckResult(
                has_quota=False,
                remaining=0,
                max_quota=0,
                message="未激活"
            )

        return QuotaCheckResult(
            has_quota=status.remaining_quota > 0,
            remaining=status.remaining_quota,
            max_quota=status.max_quota,
            message="配额充足" if status.remaining_quota > 0 else "配额已用完"
        )

    def check_and_consume_quota(self) -> bool:
        """
        检查并消耗配额

        Returns:
            是否有配额可用
        """
        quota = self._get_remaining_quota()
        if quota <= 0:
            return False

        self.consume_quota()
        return True

    def consume_quota(self) -> int:
        """
        消耗一个配额

        Returns:
            剩余配额
        """
        remaining = self._get_remaining_quota()
        new_remaining = max(0, remaining - 1)
        self._save_quota_to_registry(new_remaining)
        logger.info(f"配额已消耗，剩余: {new_remaining}")
        return new_remaining

    def _get_remaining_quota(self) -> int:
        """获取剩余配额"""
        quota_data = self._load_quota()
        if quota_data is None:
            return 0

        # 检查日期
        quota_date = quota_data.get("date")
        today = date.today().isoformat()

        if quota_date != today:
            # 新的一天，重置配额
            license_data = self._load_license()
            max_quota = license_data.get("max_quota", self.MAX_DAILY_QUOTA) if license_data else self.MAX_DAILY_QUOTA
            self._save_quota(max_quota)
            return max_quota

        return quota_data.get("remaining", 0)

    def _get_hardware_ids(self) -> Dict[str, str]:
        """获取硬件ID"""
        from core.license.hardware_match import get_hardware_ids as _get_hardware_ids
        return _get_hardware_ids()

    def _verify_license(self, license_data: Dict, machine_code: str) -> bool:
        """验证许可证"""
        if license_data.get("machine_code") != machine_code:
            return False

        # 可以添加更多验证逻辑
        return True

    def _load_license(self) -> Optional[Dict]:
        """加载许可证"""
        if self._license_data is not None:
            return self._license_data

        license_path = self.LICENSE_BACKUP_DIR / self.LICENSE_FILENAME
        if not license_path.exists():
            return None

        try:
            with open(license_path, 'r', encoding='utf-8') as f:
                self._license_data = json.load(f)
            return self._license_data
        except Exception as e:
            logger.error(f"加载许可证失败: {e}")
            return None

    def _save_license(self, license_data: Dict) -> None:
        """保存许可证"""
        self.LICENSE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        license_path = self.LICENSE_BACKUP_DIR / self.LICENSE_FILENAME

        try:
            with open(license_path, 'w', encoding='utf-8') as f:
                json.dump(license_data, f, indent=2, ensure_ascii=False)
            logger.info(f"许可证已保存: {license_path}")
        except Exception as e:
            logger.error(f"保存许可证失败: {e}")

    def _load_quota(self) -> Optional[Dict]:
        """加载配额数据"""
        # 优先从注册表加载
        quota_data = self._load_quota_from_registry()
        if quota_data:
            return quota_data

        # 从文件加载
        return self._load_and_verify_quota_file()

    def _load_and_verify_quota_file(self) -> Optional[Dict]:
        """从文件加载配额"""
        quota_path = self.LICENSE_BACKUP_DIR / "quota.json"
        if not quota_path.exists():
            return None

        try:
            with open(quota_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配额文件失败: {e}")
            return None

    def _load_quota_from_registry(self) -> Optional[Dict]:
        """从注册表加载配额"""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                f"Software\\{self.QUOTA_REGISTRY_KEY}",
                0,
                winreg.KEY_READ
            )
            date_val = winreg.QueryValueEx(key, "date")[0]
            remaining_val = winreg.QueryValueEx(key, "remaining")[0]
            winreg.CloseKey(key)
            return {"date": date_val, "remaining": remaining_val}
        except Exception:
            return None

    def _save_quota(self, remaining: int) -> None:
        """保存配额到所有位置"""
        self._save_quota_to_registry(remaining)
        self._sync_quota_to_all_locations(remaining)

    def _save_quota_to_registry(self, remaining: int) -> None:
        """保存配额到注册表"""
        try:
            import winreg
            key = winreg.CreateKey(
                winreg.HKEY_CURRENT_USER,
                f"Software\\{self.QUOTA_REGISTRY_KEY}"
            )
            winreg.SetValueEx(key, "date", 0, winreg.REG_SZ, date.today().isoformat())
            winreg.SetValueEx(key, "remaining", 0, winreg.REG_DWORD, remaining)
            winreg.CloseKey(key)
        except Exception as e:
            logger.error(f"保存配额到注册表失败: {e}")

    def _sync_quota_to_all_locations(self, remaining: int) -> None:
        """同步配额到所有位置"""
        quota_data = {
            "date": date.today().isoformat(),
            "remaining": remaining
        }

        # 保存到文件
        self.LICENSE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        quota_path = self.LICENSE_BACKUP_DIR / "quota.json"
        try:
            with open(quota_path, 'w', encoding='utf-8') as f:
                json.dump(quota_data, f, indent=2)
        except Exception as e:
            logger.error(f"同步配额到文件失败: {e}")


# 全局单例
_license_service: Optional[LicenseService] = None


def get_license_service() -> LicenseService:
    """获取授权服务单例"""
    global _license_service
    if _license_service is None:
        _license_service = LicenseService()
    return _license_service
