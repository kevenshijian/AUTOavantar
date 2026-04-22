"""
数字人视频生成系统 - 一键启动入口
"""

import argparse
import logging
import sys
import os

from business.workflow import create_workflow, DigitalHumanWorkflow
from core.config.logging_config import setup_logging

# 配置日志
setup_logging()

# 获取 logger
logger = logging.getLogger("autoavantar")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="数字人视频生成系统")

    parser.add_argument(
        "--source-video", "-s",
        required=True,
        help="源视频路径"
    )
    parser.add_argument(
        "--prompt-audio", "-p",
        required=True,
        help="音色参考音频路径"
    )
    parser.add_argument(
        "--topic", "-t",
        help="主题（用于 LLM 生成文案）"
    )
    parser.add_argument(
        "--script", "-S",
        help="自定义文案（与 --topic 二选一）"
    )
    parser.add_argument(
        "--tts-host",
        default="http://localhost:7860",
        help="IndexTTS 服务地址"
    )
    parser.add_argument(
        "--heygem-host",
        default="http://localhost:9889",
        help="HeyGem 服务地址"
    )
    parser.add_argument(
        "--llm-provider",
        default="deepseek",
        choices=["deepseek", "aliyun"],
        help="LLM 提供商"
    )
    parser.add_argument(
        "--llm-api-key",
        default="",
        help="LLM API 密钥"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="output",
        help="输出目录"
    )
    parser.add_argument(
        "--no-postprocess",
        action="store_true",
        help="禁用后期处理"
    )

    args = parser.parse_args()

    # 参数校验
    if not args.topic and not args.script:
        parser.error("需要提供 --topic 或 --script")

    # 创建工作流
    logger.info("初始化数字人工作流...")
    workflow = create_workflow(
        tts_host=args.tts_host,
        heygem_host=args.heygem_host,
        llm_provider=args.llm_provider,
        llm_api_key=args.llm_api_key,
        output_dir=args.output_dir
    )

    try:
        # 运行
        logger.info("开始生成视频...")

        if args.topic:
            result = workflow.run_with_topic(
                source_video_path=args.source_video,
                topic=args.topic,
                prompt_audio_path=args.prompt_audio
            )
        else:
            result = workflow.run_with_script(
                source_video_path=args.source_video,
                script_text=args.script,
                prompt_audio_path=args.prompt_audio
            )

        # 输出结果
        print("\n" + "=" * 50)
        print(f"任务 ID: {result.task_id}")
        print(f"状态: {result.status}")
        if result.output_path:
            print(f"输出路径: {result.output_path}")
            print(f"完成段落: {result.segments_completed}/{result.total_segments}")
        if result.error_message:
            print(f"错误: {result.error_message}")
        print("=" * 50)

        return 0 if result.status == "success" else 1

    except KeyboardInterrupt:
        logger.info("用户中断")
        return 130

    except Exception as e:
        logger.exception("运行失败")
        print(f"\n错误: {e}")
        return 1

    finally:
        workflow.close()


if __name__ == "__main__":
    sys.exit(main())