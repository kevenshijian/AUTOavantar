"""
激活码生成工具
用于开发者生成激活码

使用方法:
    python tools/generate_activation_code.py <机器码> --private-key <私钥文件>

示例:
    python tools/generate_activation_code.py ABCD1234567890AB --private-key config/license/private_key.pem
    python tools/generate_activation_code.py ABCD1234567890AB --private-key config/license/private_key.pem --quota 100
    python tools/generate_activation_code.py ABCD1234567890AB --private-key config/license/private_key.pem --type yearly
    python tools/generate_activation_code.py ABCD1234567890AB --private-key config/license/private_key.pem --type three_year
    python tools/generate_activation_code.py ABCD1234567890AB --private-key config/license/private_key.pem --type lifetime

注意: 私钥文件是必需的，用于生成有效的签名激活码。
"""

import sys
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.license.crypto import generate_activation_code
from core.license.machine_code import get_machine_code


def main():
    parser = argparse.ArgumentParser(description="生成激活码")
    parser.add_argument("machine_code", nargs="?", help="目标机器码（不提供则使用本机机器码）")
    parser.add_argument("--quota", "-q", type=int, default=10, help="每日配额（默认 10）")
    parser.add_argument("--contact", "-c", default="", help="联系信息")
    parser.add_argument("--private-key", "-k", required=True, help="私钥文件路径（必需）")
    parser.add_argument(
        "--type", "-t",
        choices=["yearly", "three_year", "lifetime"],
        default="yearly",
        help="激活类型：yearly（一年期，默认）、three_year（三年期）、lifetime（终身）"
    )

    args = parser.parse_args()

    # 获取机器码
    if args.machine_code:
        machine_code = args.machine_code
    else:
        machine_code = get_machine_code()
        print(f"本机机器码: {machine_code}")

    # 加载私钥
    key_path = Path(args.private_key)
    if not key_path.exists():
        print(f"错误: 私钥文件不存在: {key_path}")
        sys.exit(1)

    try:
        with open(key_path, 'r', encoding='utf-8') as f:
            private_key = f.read()
        print(f"已加载私钥: {key_path}")
    except Exception as e:
        print(f"错误: 读取私钥文件失败: {e}")
        sys.exit(1)

    # 生成激活码
    contact_info = {}
    if args.contact:
        contact_info["contact"] = args.contact

    try:
        activation_code = generate_activation_code(
            machine_code=machine_code,
            max_quota=args.quota,
            contact_info=contact_info,
            private_key=private_key,
            license_type=args.type
        )
    except ValueError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: 生成激活码失败: {e}")
        sys.exit(1)

    # 显示激活类型说明
    type_descriptions = {
        "yearly": "一年期（365天有效）",
        "three_year": "三年期（1095天有效）",
        "lifetime": "终身（永久有效）"
    }

    print("\n" + "=" * 60)
    print("激活码已生成")
    print("=" * 60)
    print(f"机器码: {machine_code}")
    print(f"激活类型: {type_descriptions.get(args.type, args.type)}")
    print(f"每日配额: {args.quota}")
    print(f"联系信息: {args.contact or '无'}")
    print("-" * 60)
    print(f"激活码: {activation_code}")
    print("=" * 60)


if __name__ == "__main__":
    main()
