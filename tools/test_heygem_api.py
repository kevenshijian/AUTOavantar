#!/usr/bin/env python
# coding=utf-8
"""
HeyGem API 测试脚本

用法:
  python tools/test_heygem_api.py --video <视频路径> --audio <音频路径> [--server URL] [--face-id ID] [--steps N]

示例:
  python tools/test_heygem_api.py --video backend/uploads/videos/role/xxx.mp4 --audio backend/output/temp/audio/seg_000.wav
  python tools/test_heygem_api.py --video D:/AI/AUTOavantar/测试素材/role.mp4 --audio D:/AI/AUTOavantar/测试素材/test.wav --diagnose

参数:
  --video       模板视频文件路径（必填）
  --audio       音频文件路径（必填）
  --server      API 服务器地址（默认 http://127.0.0.1:9889）
  --face-id     人脸索引，0 或 1（默认 0）
  --steps       推理批次大小（默认 16）
  --diagnose    同时运行 ONNX 模型输出范围诊断
  --timeout     请求超时秒数（默认 300）
"""
import argparse
import sys
import os
import time
import json
import urllib.request
import urllib.parse
import urllib.error
import numpy as np

# 添加项目根目录到 sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# heygem 根目录
HEYGEM_ROOT = os.path.join(PROJECT_ROOT, "engines", "heygem")
if HEYGEM_ROOT not in sys.path:
    sys.path.insert(0, HEYGEM_ROOT)


def test_api(server: str, video: str, audio: str, face_id: int, steps: int, timeout: int):
    """调用 HeyGem API 生成视频"""
    params = urllib.parse.urlencode({
        "video_file": video,
        "audio_file": audio,
        "ifface": "false",
        "face_id": face_id,
        "steps": steps,
    })
    url = f"{server}/?{params}"

    print(f"\n{'='*60}")
    print(f"HeyGem API 测试")
    print(f"{'='*60}")
    print(f"  服务器: {server}")
    print(f"  视频:   {video}")
    print(f"  音频:   {audio}")
    print(f"  face_id: {face_id}")
    print(f"  steps:  {steps}")
    print(f"  URL:    {url}")
    print(f"{'='*60}")

    start_time = time.time()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.status
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        status_code = e.code
    except urllib.error.URLError as e:
        print(f"\n[错误] 无法连接服务器: {e.reason}")
        print(f"  请确认服务器已启动: python engines/heygem/app.py")
        return None
    except Exception as e:
        print(f"\n[错误] 请求异常: {e}")
        return None

    elapsed = time.time() - start_time

    print(f"\n  状态码: {status_code}")
    print(f"  耗时:   {elapsed:.1f}s")

    try:
        result = json.loads(body)
        print(f"  结果:   {json.dumps(result, ensure_ascii=False, indent=4)}")
        if result.get("status") == "success":
            output_path = result.get("output_video_url", "")
            if output_path and os.path.exists(output_path):
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                print(f"  输出文件: {output_path} ({size_mb:.1f} MB)")
        return result
    except json.JSONDecodeError:
        print(f"  原始响应: {body[:500]}")
        return None


def diagnose_onnx_output():
    """诊断 ONNX 模型实际输出范围"""
    print(f"\n{'='*60}")
    print(f"ONNX 模型输出范围诊断")
    print(f"{'='*60}")

    model_path = os.path.join(HEYGEM_ROOT, "landmark2face_wy/checkpoints/anylang/dinet_v1_20240131_wrapped.onnx")
    if not os.path.exists(model_path):
        print(f"[错误] 模型文件不存在: {model_path}")
        return

    try:
        import onnxruntime as ort
    except ImportError:
        print("[错误] onnxruntime 未安装")
        return

    # 创建 session（优先 CUDA）
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    providers = []
    provider_options_list = []
    if "CUDAExecutionProvider" in ort.get_available_providers():
        providers.append("CUDAExecutionProvider")
        provider_options_list.append({
            "arena_extend_strategy": "kSameAsRequested",
        })
    providers.append("CPUExecutionProvider")
    provider_options_list.append({})

    try:
        session = ort.InferenceSession(model_path, sess_options=so, providers=providers, provider_options=provider_options_list)
    except Exception as e:
        print(f"[错误] 无法加载模型: {e}")
        # fallback to CPU only
        try:
            session = ort.InferenceSession(model_path, sess_options=so, providers=["CPUExecutionProvider"])
        except Exception as e2:
            print(f"[错误] CPU 模式也无法加载: {e2}")
            return

    actual_providers = session.get_providers()
    print(f"  Providers: {actual_providers}")

    # 打印输入输出信息
    for inp in session.get_inputs():
        print(f"  输入: {inp.name}, shape={inp.shape}, type={inp.type}")
    for out in session.get_outputs():
        print(f"  输出: {out.name}, shape={out.shape}, type={out.type}")

    # 用随机数据测试 /127.5-1 归一化
    np.random.seed(42)
    batch = 1
    T = 10
    img_size = 256

    raw = np.random.randint(0, 256, (batch, 3, img_size, img_size)).astype(np.float32)

    # 方式1: /127.5-1 归一化
    mask_B = raw / 127.5 - 1.0
    B_img_ = raw / 127.5 - 1.0
    concat_images = np.concatenate([mask_B, B_img_], axis=1)  # (1, 6, 256, 256)
    audio_feature = np.random.randn(batch, 256, T).astype(np.float32) * 0.1

    outputs = session.run(["generated_image"], {
        "audio_feature": audio_feature,
        "concat_images": concat_images,
    })
    result_127 = outputs[0]
    print(f"\n  [/127.5-1 归一化]")
    print(f"    输出 shape: {result_127.shape}")
    print(f"    输出范围:   min={result_127.min():.6f}, max={result_127.max():.6f}, mean={result_127.mean():.6f}")

    # 方式2: /255.0 归一化
    mask_B_255 = raw / 255.0
    B_img_255 = raw / 255.0
    concat_images_255 = np.concatenate([mask_B_255, B_img_255], axis=1)

    outputs_255 = session.run(["generated_image"], {
        "audio_feature": audio_feature,
        "concat_images": concat_images_255,
    })
    result_255 = outputs_255[0]
    print(f"\n  [/255.0 归一化]")
    print(f"    输出 shape: {result_255.shape}")
    print(f"    输出范围:   min={result_255.min():.6f}, max={result_255.max():.6f}, mean={result_255.mean():.6f}")

    # 判断正确的还原方式
    print(f"\n  [判断]")
    if result_127.min() >= -0.1 and result_127.max() <= 1.1:
        if result_127.min() >= -0.5:
            print(f"    /127.5-1 输出范围偏向 [0, 1] → 还原: (value + 1) * 127.5")
            print(f"    ⚠ 但输出包含负值 → 如果 min < 0，用 np.clip((value + 1) * 127.5, 0, 255)")
        else:
            print(f"    /127.5-1 输出范围 [-1, 1] → 还原: (value + 1) * 127.5")
    else:
        print(f"    /127.5-1 输出范围异常: [{result_127.min():.4f}, {result_127.max():.4f}]")

    if result_255.min() >= -0.1 and result_255.max() <= 1.1:
        print(f"    /255.0 输出范围 [0, 1] → 还原: value * 255")

    # 使用真实人脸数据测试（如果有的话）
    # 用常数填充（模拟正常人脸像素值约 100-200）
    realistc = np.full((batch, 3, img_size, img_size), 150.0, dtype=np.float32) + np.random.randn(batch, 3, img_size, img_size).astype(np.float32) * 30
    realistc = np.clip(realistc, 0, 255)

    mask_B_r = realistc / 127.5 - 1.0
    B_img_r = realistc / 127.5 - 1.0
    concat_r = np.concatenate([mask_B_r, B_img_r], axis=1)

    outputs_r = session.run(["generated_image"], {
        "audio_feature": audio_feature,
        "concat_images": concat_r,
    })
    result_r = outputs_r[0]
    print(f"\n  [模拟真实人脸 /127.5-1]")
    print(f"    输出范围:   min={result_r.min():.6f}, max={result_r.max():.6f}, mean={result_r.mean():.6f}")

    # 还原对比
    method1 = np.clip((result_r + 1.0) * 127.5, 0, 255).astype(np.uint8)
    method2 = np.clip(result_r * 255, 0, 255).astype(np.uint8)
    print(f"\n  [还原方法对比 — 模拟真实人脸]")
    print(f"    (value+1)*127.5 → pixel range: [{method1.min()}, {method1.max()}], mean={method1.mean():.1f}")
    print(f"    value*255        → pixel range: [{method2.min()}, {method2.max()}], mean={method2.mean():.1f}")

    # 保存诊断帧
    try:
        import cv2
        diag_dir = os.path.join(PROJECT_ROOT, "result", "diagnose")
        os.makedirs(diag_dir, exist_ok=True)

        # 方法1
        frame1 = method1[0].transpose(1, 2, 0)[:, :, ::-1]  # RGB → BGR
        cv2.imwrite(os.path.join(diag_dir, "diag_method1_add1_mul1275.png"), frame1)

        # 方法2
        frame2 = method2[0].transpose(1, 2, 0)[:, :, ::-1]
        cv2.imwrite(os.path.join(diag_dir, "diag_method2_mul255.png"), frame2)

        print(f"\n  诊断图像已保存到: {diag_dir}")
        print(f"    diag_method1_add1_mul1275.png — (value+1)*127.5 还原")
        print(f"    diag_method2_mul255.png       — value*255 还原")
    except ImportError:
        pass

    del session
    print(f"\n  诊断完成。")


def main():
    parser = argparse.ArgumentParser(description="HeyGem API 测试脚本")
    parser.add_argument("--video", required=True, help="模板视频文件路径")
    parser.add_argument("--audio", required=True, help="音频文件路径")
    parser.add_argument("--server", default="http://127.0.0.1:9889", help="API 服务器地址")
    parser.add_argument("--face-id", type=int, default=0, help="人脸索引 (0 或 1)")
    parser.add_argument("--steps", type=int, default=16, help="推理批次大小")
    parser.add_argument("--diagnose", action="store_true", help="运行 ONNX 输出范围诊断")
    parser.add_argument("--timeout", type=int, default=300, help="请求超时秒数")

    args = parser.parse_args()

    # 验证文件存在
    if not os.path.exists(args.video):
        print(f"[错误] 视频文件不存在: {args.video}")
        sys.exit(1)
    if not os.path.exists(args.audio):
        print(f"[错误] 音频文件不存在: {args.audio}")
        sys.exit(1)

    # 可选：先运行诊断
    if args.diagnose:
        diagnose_onnx_output()

    # 调用 API
    test_api(args.server, args.video, args.audio, args.face_id, args.steps, args.timeout)


if __name__ == "__main__":
    main()
