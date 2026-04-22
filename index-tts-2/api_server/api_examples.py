"""
IndexTTS API 请求示例集

提供各种常见场景的 API 调用示例，包含：
- cURL 命令行示例
- Python requests 同步示例
- Python aiohttp 异步示例
- 完整测试用例

用法：
    # 基础合成
    python api_examples.py --example basic

    # 异步批量合成
    python api_examples.py --example batch

    # 直接运行所有示例（需先启动服务）
    python api_examples.py --run-all
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional

import requests

# ============================================================================
# 配置
# ============================================================================

API_BASE = "http://127.0.0.1:7860"
API_V1 = f"{API_BASE}/api/v1"
TIMEOUT = 120


# ============================================================================
# 示例 1: cURL 命令行示例
# ============================================================================

CURL_EXAMPLES = {
    "健康检查": """
# 健康检查
curl -X GET "{api_v1}/health"
""",
    "配置查询": """
# 配置查询
curl -X GET "{api_v1}/config"
""",
    "音色列表": """
# 获取可用音色列表
curl -X GET "{api_v1}/voices"
""",
    "基础合成": """
# 基础语音合成
curl -X POST "{api_v1}/tts/synthesize" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "text": "你好，欢迎使用 IndexTTS 语音合成服务。",
    "voice_name": "苏瑶"
  }}'
""",
    "带情感的合成": """
# 使用情绪标签合成
curl -X POST "{api_v1}/tts/synthesize" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "text": "今天天气真不错！",
    "voice_name": "苏瑶",
    "emotion": "高兴"
  }}'
""",
    "情感向量直传": """
# 直接传入情感向量（更精确控制）
curl -X POST "{api_v1}/tts/synthesize" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "text": "这是一个悲伤的故事。",
    "voice_name": "苏瑶",
    "emotion_vec": {{"vec1": 0.3, "vec3": 0.8, "vec7": 0.2}}
  }}'
""",
    "自定义推理参数": """
# 使用标准推理模式 + 自定义采样参数
curl -X POST "{api_v1}/tts/synthesize" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "text": "这段话需要更细腻的表达。",
    "voice_name": "苏瑶",
    "inference_mode": "standard",
    "temperature": 0.9,
    "top_p": 0.85,
    "top_k": 50,
    "num_beams": 5
  }}'
""",
    "任务状态查询": """
# 查询任务状态（将 YOUR_TASK_ID 替换为实际 task_id）
curl -X GET "{api_v1}/tasks/YOUR_TASK_ID"
""",
    "队列位置查询": """
# 查询队列位置
curl -X GET "{api_v1}/tasks/YOUR_TASK_ID/status"
""",
    "音频下载": """
# 下载合成音频（将 FILENAME.wav 替换为实际文件名）
curl -O "{api_v1}/audio/FILENAME.wav"
""",
}


# ============================================================================
# 示例 2: Python requests 同步示例
# ============================================================================

def example_requests_basic():
    """基础语音合成"""
    print("\n--- Python requests: 基础合成 ---")

    # 1. 健康检查
    resp = requests.get(f"{API_V1}/health", timeout=10)
    resp.raise_for_status()
    health = resp.json()
    print(f"服务状态: {health['status']}")
    print(f"模型已加载: {health['model_loaded']}")

    # 2. 获取音色列表
    resp = requests.get(f"{API_V1}/voices", timeout=10)
    resp.raise_for_status()
    voices = resp.json()["voices"]
    if not voices:
        print("没有可用音色")
        return
    voice_name = voices[0]["name"]
    print(f"使用音色: {voice_name}")

    # 3. 提交合成任务
    resp = requests.post(
        f"{API_V1}/tts/synthesize",
        json={
            "text": "你好，这是一段测试语音。",
            "voice_name": voice_name,
        },
        timeout=60,
    )
    resp.raise_for_status()
    task = resp.json()
    task_id = task["task_id"]
    print(f"任务已提交: {task_id}")

    # 4. 轮询等待完成
    while True:
        time.sleep(1)
        resp = requests.get(f"{API_V1}/tasks/{task_id}", timeout=10)
        resp.raise_for_status()
        result = resp.json()

        if result["status"] == "completed":
            print(f"合成完成!")
            print(f"音频 URL: {result['audio_url']}")
            print(f"音频时长: {result['duration_sec']:.2f}s")
            print(f"推理耗时: {result['inference_time_sec']:.2f}s")
            break
        elif result["status"] == "failed":
            print(f"合成失败: {result['error_message']}")
            break


def example_requests_with_emotion():
    """带情感的语音合成"""
    print("\n--- Python requests: 情感合成 ---")

    # 获取音色
    resp = requests.get(f"{API_V1}/voices", timeout=10)
    resp.raise_for_status()
    voices = resp.json()["voices"]
    voice_name = voices[0]["name"]

    # 使用情绪标签
    resp = requests.post(
        f"{API_V1}/tts/synthesize",
        json={
            "text": "哇，太开心了！今天是我的生日！",
            "voice_name": voice_name,
            "emotion": "高兴",  # 通过映射表翻译
        },
        timeout=60,
    )
    resp.raise_for_status()
    task_id = resp.json()["task_id"]
    print(f"情绪合成任务: {task_id}")

    # 使用情感向量直传（更精确）
    resp = requests.post(
        f"{API_V1}/tts/synthesize",
        json={
            "text": "我感到很难过，一切都没有意义了。",
            "voice_name": voice_name,
            "emotion_vec": {"vec1": 0.2, "vec3": 0.9, "vec7": 0.1},  # vec3 控制悲伤
        },
        timeout=60,
    )
    resp.raise_for_status()
    print(f"情感向量任务: {resp.json()['task_id']}")


def example_requests_batch():
    """批量合成（串行）"""
    print("\n--- Python requests: 批量合成 ---")

    resp = requests.get(f"{API_V1}/voices", timeout=10)
    resp.raise_for_status()
    voice_name = resp.json()["voices"][0]["name"]

    texts = [
        "第一段文本。",
        "第二段文本。",
        "第三段文本。",
    ]

    task_ids = []
    for text in texts:
        resp = requests.post(
            f"{API_V1}/tts/synthesize",
            json={"text": text, "voice_name": voice_name},
            timeout=60,
        )
        resp.raise_for_status()
        task_ids.append(resp.json()["task_id"])
        print(f"已提交: {text[:20]}... -> {task_ids[-1]}")

    # 等待所有任务完成
    print("等待所有任务完成...")
    completed = 0
    while completed < len(task_ids):
        for tid in task_ids:
            resp = requests.get(f"{API_V1}/tasks/{tid}", timeout=10)
            if resp.json()["status"] == "completed":
                completed += 1
                print(f"完成: {tid}")
        time.sleep(1)

    print(f"全部完成! 共 {len(task_ids)} 个任务")


def example_requests_custom_params():
    """自定义推理参数"""
    print("\n--- Python requests: 自定义参数 ---")

    resp = requests.get(f"{API_V1}/voices", timeout=10)
    voice_name = resp.json()["voices"][0]["name"]

    # 快速模式（默认）
    resp = requests.post(
        f"{API_V1}/tts/synthesize",
        json={
            "text": "快速模式，牺牲质量换取速度。",
            "voice_name": voice_name,
            "inference_mode": "fast",
            "num_beams": 1,
        },
        timeout=60,
    )
    fast_task = resp.json()["task_id"]

    # 标准模式（更高质量）
    resp = requests.post(
        f"{API_V1}/tts/synthesize",
        json={
            "text": "标准模式，质量更高但速度较慢。",
            "voice_name": voice_name,
            "inference_mode": "standard",
            "num_beams": 5,
            "temperature": 0.8,
        },
        timeout=120,
    )
    standard_task = resp.json()["task_id"]

    print(f"快速任务: {fast_task}")
    print(f"标准任务: {standard_task}")


def example_requests_download_audio():
    """下载音频文件"""
    print("\n--- Python requests: 下载音频 ---")

    resp = requests.get(f"{API_V1}/voices", timeout=10)
    voice_name = resp.json()["voices"][0]["name"]

    # 提交合成任务
    resp = requests.post(
        f"{API_V1}/tts/synthesize",
        json={"text": "这段语音会被下载保存。", "voice_name": voice_name},
        timeout=60,
    )
    task_id = resp.json()["task_id"]

    # 等待完成
    while True:
        resp = requests.get(f"{API_V1}/tasks/{task_id}", timeout=10)
        result = resp.json()
        if result["status"] == "completed":
            break
        time.sleep(1)

    # 下载音频
    audio_url = result["audio_url"]
    filename = audio_url.split("/")[-1]

    resp = requests.get(f"{API_BASE}{audio_url}", timeout=30)
    resp.raise_for_status()

    output_path = Path("output") / filename
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_bytes(resp.content)

    print(f"音频已保存: {output_path}")
    print(f"文件大小: {len(resp.content)} bytes")


# ============================================================================
# 示例 3: Python aiohttp 异步示例
# ============================================================================

async def example_async_basic():
    """异步基础合成"""
    import aiohttp

    print("\n--- aiohttp: 异步基础合成 ---")

    async with aiohttp.ClientSession() as session:
        # 健康检查
        async with session.get(f"{API_V1}/health", timeout=30) as resp:
            health = await resp.json()
            print(f"服务状态: {health['status']}")

        # 获取音色
        async with session.get(f"{API_V1}/voices", timeout=30) as resp:
            voices_data = await resp.json()
            voice_name = voices_data["voices"][0]["name"]
            print(f"使用音色: {voice_name}")

        # 提交任务
        async with session.post(
            f"{API_V1}/tts/synthesize",
            json={"text": "这是一段异步合成的语音。", "voice_name": voice_name},
            timeout=60,
        ) as resp:
            task = await resp.json()
            task_id = task["task_id"]
            print(f"任务已提交: {task_id}")

        # 轮询等待完成
        while True:
            await asyncio.sleep(1)
            async with session.get(f"{API_V1}/tasks/{task_id}", timeout=30) as resp:
                result = await resp.json()
                if result["status"] == "completed":
                    print(f"完成: {result['audio_url']}")
                    break
                elif result["status"] == "failed":
                    print(f"失败: {result['error_message']}")
                    break


async def example_async_batch():
    """异步批量合成（并发）"""
    import aiohttp

    print("\n--- aiohttp: 异步批量合成 ---")

    texts = [
        "第一段文本。",
        "第二段文本。",
        "第三段文本。",
        "第四段文本。",
        "第五段文本。",
    ]

    async with aiohttp.ClientSession() as session:
        # 获取音色
        async with session.get(f"{API_V1}/voices", timeout=30) as resp:
            voices_data = await resp.json()
            voice_name = voices_data["voices"][0]["name"]

        # 并发提交所有任务
        async def submit_and_wait(text: str):
            async with session.post(
                f"{API_V1}/tts/synthesize",
                json={"text": text, "voice_name": voice_name},
                timeout=60,
            ) as resp:
                task = await resp.json()
                task_id = task["task_id"]

            # 轮询等待完成
            while True:
                await asyncio.sleep(1)
                async with session.get(
                    f"{API_V1}/tasks/{task_id}", timeout=30
                ) as resp:
                    result = await resp.json()
                    if result["status"] == "completed":
                        return result["audio_url"]
                    elif result["status"] == "failed":
                        return None

        # 并发执行
        results = await asyncio.gather(*[submit_and_wait(t) for t in texts])

        for i, url in enumerate(results):
            status = "完成" if url else "失败"
            print(f"  任务 {i+1}: {status} - {url}")


# ============================================================================
# 示例 4: 完整测试套件
# ============================================================================

def run_full_tests(verbose: bool = True):
    """运行完整测试套件"""
    print("\n" + "=" * 60)
    print(" IndexTTS API 完整测试套件")
    print("=" * 60)

    passed = 0
    failed = 0

    # 测试 1: 健康检查
    print("\n[1/8] 健康检查...")
    try:
        resp = requests.get(f"{API_V1}/health", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        assert data["status"] == "ready", f"服务未就绪: {data['status']}"
        print("  ✓ PASS")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1
        return failed  # 后续测试依赖服务

    # 测试 2: 配置查询
    print("[2/8] 配置查询...")
    try:
        resp = requests.get(f"{API_V1}/config", timeout=10)
        resp.raise_for_status()
        config = resp.json()
        if verbose:
            print(f"  设备: {config['device']}, FP16: {config['fp16']}")
        print("  ✓ PASS")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1

    # 测试 3: 音色列表
    print("[3/8] 音色列表...")
    try:
        resp = requests.get(f"{API_V1}/voices", timeout=10)
        resp.raise_for_status()
        voices = resp.json()["voices"]
        assert len(voices) > 0, "没有可用音色"
        voice_name = voices[0]["name"]
        if verbose:
            print(f"  可用音色: {len(voices)} 个，第一音色: {voice_name}")
        print("  ✓ PASS")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1
        return failed  # 后续测试依赖音色

    # 测试 4: 基础合成
    print("[4/8] 基础合成...")
    try:
        start = time.time()
        resp = requests.post(
            f"{API_V1}/tts/synthesize",
            json={"text": "测试文本。", "voice_name": voice_name},
            timeout=60,
        )
        resp.raise_for_status()
        task_id = resp.json()["task_id"]

        # 等待完成
        while True:
            time.sleep(1)
            resp = requests.get(f"{API_V1}/tasks/{task_id}", timeout=10)
            result = resp.json()
            if result["status"] == "completed":
                elapsed = time.time() - start
                if verbose:
                    print(f"  耗时: {elapsed:.1f}s, 音频: {result['audio_url']}")
                print("  ✓ PASS")
                passed += 1
                break
            elif result["status"] == "failed":
                raise Exception(result.get("error_message", "未知错误"))
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1

    # 测试 5: 情感合成
    print("[5/8] 情感合成...")
    try:
        resp = requests.post(
            f"{API_V1}/tts/synthesize",
            json={
                "text": "太高兴了！",
                "voice_name": voice_name,
                "emotion_vec": {"vec1": 0.9, "vec7": 0.6},
            },
            timeout=60,
        )
        resp.raise_for_status()
        task_id = resp.json()["task_id"]

        while True:
            time.sleep(1)
            resp = requests.get(f"{API_V1}/tasks/{task_id}", timeout=10)
            if resp.json()["status"] == "completed":
                print("  ✓ PASS")
                passed += 1
                break
            elif resp.json()["status"] == "failed":
                raise Exception(resp.json().get("error_message"))
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1

    # 测试 6: 自定义参数
    print("[6/8] 自定义参数合成...")
    try:
        resp = requests.post(
            f"{API_V1}/tts/synthesize",
            json={
                "text": "自定义参数测试。",
                "voice_name": voice_name,
                "inference_mode": "standard",
                "temperature": 0.8,
                "top_p": 0.9,
                "num_beams": 5,
            },
            timeout=120,
        )
        resp.raise_for_status()
        task_id = resp.json()["task_id"]

        while True:
            time.sleep(1)
            resp = requests.get(f"{API_V1}/tasks/{task_id}", timeout=10)
            if resp.json()["status"] == "completed":
                print("  ✓ PASS")
                passed += 1
                break
            elif resp.json()["status"] == "failed":
                raise Exception(resp.json().get("error_message"))
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1

    # 测试 7: 队列状态
    print("[7/8] 队列状态查询...")
    try:
        resp = requests.post(
            f"{API_V1}/tts/synthesize",
            json={"text": "队列测试。", "voice_name": voice_name},
            timeout=60,
        )
        resp.raise_for_status()
        task_id = resp.json()["task_id"]

        resp = requests.get(f"{API_V1}/tasks/{task_id}/status", timeout=10)
        resp.raise_for_status()
        status = resp.json()
        assert "queue_position" in status
        print("  ✓ PASS")
        passed += 1

        # 等待完成清理
        while True:
            time.sleep(1)
            resp = requests.get(f"{API_V1}/tasks/{task_id}", timeout=10)
            if resp.json()["status"] in ("completed", "failed"):
                break
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1

    # 测试 8: 错误处理
    print("[8/8] 错误处理...")
    try:
        resp = requests.post(
            f"{API_V1}/tts/synthesize",
            json={"text": "没有提供音色"},  # 缺少 voice_name
            timeout=10,
        )
        if resp.status_code == 400:
            print("  ✓ PASS (正确返回 400)")
            passed += 1
        else:
            print(f"  ✗ FAIL (期望 400, 实际 {resp.status_code})")
            failed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1

    # 汇总
    print("\n" + "=" * 60)
    print(f" 测试结果: {passed}/{passed+failed} 通过")
    if failed == 0:
        print(" 全部通过!")
    else:
        print(f" 失败: {failed} 项")
    print("=" * 60)

    return failed


# ============================================================================
# 命令行接口
# ============================================================================

def print_curl_examples():
    """打印所有 cURL 示例"""
    print("\n" + "=" * 60)
    print(" cURL 请求示例")
    print("=" * 60)

    for name, code in CURL_EXAMPLES.items():
        print(f"\n### {name}")
        print(code.format(api_v1=API_V1))


def main():
    parser = argparse.ArgumentParser(
        description="IndexTTS API 请求示例集",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python api_examples.py --list-curl        # 列出所有 cURL 示例
  python api_examples.py --example basic     # 运行指定示例
  python api_examples.py --run-all          # 运行完整测试套件
  python api_examples.py --host http://localhost:7860  # 指定 API 地址
        """,
    )
    parser.add_argument(
        "--host", default=API_BASE, help=f"API 服务地址 (默认: {API_BASE})"
    )
    parser.add_argument("--list-curl", action="store_true", help="列出所有 cURL 示例")
    parser.add_argument(
        "--example",
        choices=["basic", "emotion", "batch", "params", "download"],
        help="运行指定示例",
    )
    parser.add_argument(
        "--run-all", action="store_true", help="运行完整测试套件"
    )

    args = parser.parse_args()

    global API_BASE, API_V1
    API_BASE = args.host.rstrip("/")
    API_V1 = f"{API_BASE}/api/v1"

    if args.list_curl:
        print_curl_examples()
        return

    if args.example:
        example_map = {
            "basic": example_requests_basic,
            "emotion": example_requests_with_emotion,
            "batch": example_requests_batch,
            "params": example_requests_custom_params,
            "download": example_requests_download_audio,
        }
        try:
            example_map[args.example]()
        except requests.ConnectionError:
            print(f"\n错误: 无法连接到 {API_BASE}，请确认服务已启动")
            sys.exit(1)
        return

    if args.run_all:
        try:
            failed = run_full_tests()
            sys.exit(0 if failed == 0 else 1)
        except requests.ConnectionError:
            print(f"\n错误: 无法连接到 {API_BASE}，请确认服务已启动")
            sys.exit(1)
        return

    # 默认: 打印帮助信息
    parser.print_help()
    print("\n\n提示: 使用 --list-curl 查看所有 cURL 示例")
    print("提示: 使用 --run-all 运行完整测试套件")


if __name__ == "__main__":
    main()
