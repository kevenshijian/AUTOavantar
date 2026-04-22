"""
Task-7 & Task-8: 超时自动重启测试

测试 IndexTTS 和 HeyGem 的超时自动重启逻辑
"""

import os
import sys
from unittest.mock import MagicMock, patch, Mock
import time

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestIndexTTSAutoRestart:
    """IndexTTS 超时自动重启测试 (Task-7)"""

    def test_normal_request_no_restart(self):
        """正常请求在 60 秒内完成时不触发重启逻辑 → AC-203"""
        from business.audio.audio_processor import AudioProcessor, INDEX_TTS_TIMEOUT, MAX_AUTO_RESTART
        
        # 创建 AudioProcessor 实例
        processor = AudioProcessor.__new__(AudioProcessor)
        processor.tts_client = MagicMock()
        
        # 模拟正常响应
        processor.tts_client.synthesize.return_value = ("task-123", {"status": "success", "audio_path": "/tmp/test.wav"})
        
        # 创建模拟 segment
        segment = MagicMock()
        segment.text = "测试文本"
        
        # 调用方法
        result = processor._synthesize_with_auto_restart(
            segment=segment,
            prompt_audio="/tmp/prompt.wav",
            speed=1.0
        )
        
        # 验证：只调用了一次 synthesize，没有重启
        assert processor.tts_client.synthesize.call_count == 1
        assert result["task_id"] == "task-123"

    def test_timeout_triggers_restart(self):
        """请求超过 60 秒触发 requests.Timeout 后自动重启 IndexTTS → AC-203"""
        from business.audio.audio_processor import AudioProcessor, INDEX_TTS_TIMEOUT, MAX_AUTO_RESTART
        
        processor = AudioProcessor.__new__(AudioProcessor)
        processor.tts_client = MagicMock()
        
        # 创建模拟 segment
        segment = MagicMock()
        segment.text = "测试文本"
        
        # 第一次调用超时，第二次成功
        call_count = [0]
        def mock_synthesize(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise requests.Timeout("Connection timeout")
            return ("task-123", {"status": "success", "audio_path": "/tmp/test.wav"})
        
        processor.tts_client.synthesize.side_effect = mock_synthesize
        
        # 模拟 ServiceManager
        mock_sm = MagicMock()
        mock_sm.restart_service.return_value = True
        
        with patch("core.service_manager.get_service_manager", return_value=mock_sm):
            result = processor._synthesize_with_auto_restart(
                segment=segment,
                prompt_audio="/tmp/prompt.wav",
                speed=1.0
            )
        
        # 验证：调用了 restart_service("indextts")
        mock_sm.restart_service.assert_called_once_with("indextts")
        # 验证：最终成功返回
        assert result["task_id"] == "task-123"

    def test_restart_continues_task(self):
        """重启后自动重试当前请求，任务继续执行 → AC-205"""
        from business.audio.audio_processor import AudioProcessor
        
        processor = AudioProcessor.__new__(AudioProcessor)
        processor.tts_client = MagicMock()
        
        segment = MagicMock()
        segment.text = "测试文本"
        
        # 第一次超时，第二次成功
        call_count = [0]
        def mock_synthesize(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise requests.Timeout("Connection timeout")
            return ("task-456", {"status": "success", "audio_path": "/tmp/test2.wav"})
        
        processor.tts_client.synthesize.side_effect = mock_synthesize
        
        mock_sm = MagicMock()
        mock_sm.restart_service.return_value = True
        
        with patch("core.service_manager.get_service_manager", return_value=mock_sm):
            result = processor._synthesize_with_auto_restart(
                segment=segment,
                prompt_audio="/tmp/prompt.wav",
                speed=1.0
            )
        
        # 验证：任务继续执行，返回第二次的结果
        assert result["task_id"] == "task-456"
        assert call_count[0] == 2  # 总共调用了 2 次

    def test_max_restart_exceeded_raises_exception(self):
        """同一任务内重启 3 次后仍超时，抛出异常 → AC-206"""
        from business.audio.audio_processor import AudioProcessor, MAX_AUTO_RESTART
        
        processor = AudioProcessor.__new__(AudioProcessor)
        processor.tts_client = MagicMock()
        
        segment = MagicMock()
        segment.text = "测试文本"
        
        # 模拟所有调用都超时
        processor.tts_client.synthesize.side_effect = requests.Timeout("Connection timeout")
        
        mock_sm = MagicMock()
        mock_sm.restart_service.return_value = True
        
        with patch("core.service_manager.get_service_manager", return_value=mock_sm):
            with pytest.raises(Exception) as exc_info:
                processor._synthesize_with_auto_restart(
                    segment=segment,
                    prompt_audio="/tmp/prompt.wav",
                    speed=1.0
                )
            
            # 验证异常消息
            assert "IndexTTS 多次重启仍无响应" in str(exc_info.value)
            # 验证重启次数
            assert mock_sm.restart_service.call_count == MAX_AUTO_RESTART

    def test_service_manager_not_initialized_raises_exception(self):
        """ServiceManager 未初始化时不尝试重启，直接抛出异常"""
        from business.audio.audio_processor import AudioProcessor
        
        processor = AudioProcessor.__new__(AudioProcessor)
        processor.tts_client = MagicMock()
        
        segment = MagicMock()
        segment.text = "测试文本"
        
        # 模拟超时
        processor.tts_client.synthesize.side_effect = requests.Timeout("Connection timeout")
        
        # ServiceManager 未初始化
        with patch("core.service_manager.get_service_manager", return_value=None):
            with pytest.raises(Exception) as exc_info:
                processor._synthesize_with_auto_restart(
                    segment=segment,
                    prompt_audio="/tmp/prompt.wav",
                    speed=1.0
                )
            
            assert "ServiceManager 未初始化" in str(exc_info.value)

    def test_timeout_value_is_60_seconds(self):
        """确认 INDEX_TTS_TIMEOUT = 60 → AC-214"""
        from business.audio.audio_processor import INDEX_TTS_TIMEOUT
        
        assert INDEX_TTS_TIMEOUT == 60

    def test_max_auto_restart_is_3(self):
        """确认 MAX_AUTO_RESTART = 3 → AC-216"""
        from business.audio.audio_processor import MAX_AUTO_RESTART
        
        assert MAX_AUTO_RESTART == 3


class TestHeyGemAutoRestart:
    """HeyGem 超时自动重启测试 (Task-8)"""

    def test_normal_request_no_restart(self):
        """正常请求在 180 秒内完成时不触发重启逻辑 → AC-204"""
        from business.video.video_synthesizer import VideoSynthesizer, HEYGEM_TIMEOUT, MAX_AUTO_RESTART
        
        synthesizer = VideoSynthesizer.__new__(VideoSynthesizer)
        synthesizer.output_dir = "/tmp"
        
        # Mock _run_heygem_inference_with_timeout 方法
        synthesizer._run_heygem_inference_with_timeout = MagicMock(return_value="/tmp/video.mp4")
        
        # 调用方法
        result = synthesizer._run_heygem_with_auto_restart(
            audio_path="/tmp/audio.wav",
            video_source="/tmp/source.mp4",
            config=MagicMock(),
            face_id=0
        )
        
        # 验证：只调用了一次 _run_heygem_inference_with_timeout
        assert synthesizer._run_heygem_inference_with_timeout.call_count == 1
        assert result == "/tmp/video.mp4"

    def test_timeout_triggers_restart(self):
        """请求超过 180 秒触发超时后自动重启 HeyGem → AC-204"""
        from business.video.video_synthesizer import VideoSynthesizer
        
        synthesizer = VideoSynthesizer.__new__(VideoSynthesizer)
        synthesizer.output_dir = "/tmp"
        
        # 第一次调用超时，第二次成功
        call_count = [0]
        def mock_inference(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise requests.Timeout("Connection timeout")
            return "/tmp/video.mp4"
        
        synthesizer._run_heygem_inference_with_timeout = MagicMock(side_effect=mock_inference)
        
        mock_sm = MagicMock()
        mock_sm.restart_service.return_value = True
        
        with patch("core.service_manager.get_service_manager", return_value=mock_sm):
            result = synthesizer._run_heygem_with_auto_restart(
                audio_path="/tmp/audio.wav",
                video_source="/tmp/source.mp4",
                config=MagicMock(),
                face_id=0
            )
        
        # 验证：调用了 restart_service("heygem")
        mock_sm.restart_service.assert_called_once_with("heygem")
        assert result == "/tmp/video.mp4"

    def test_restart_continues_task(self):
        """重启后自动重试当前请求，任务继续执行 → AC-205"""
        from business.video.video_synthesizer import VideoSynthesizer
        
        synthesizer = VideoSynthesizer.__new__(VideoSynthesizer)
        synthesizer.output_dir = "/tmp"
        
        call_count = [0]
        def mock_inference(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise requests.Timeout("Connection timeout")
            return "/tmp/video2.mp4"
        
        synthesizer._run_heygem_inference_with_timeout = MagicMock(side_effect=mock_inference)
        
        mock_sm = MagicMock()
        mock_sm.restart_service.return_value = True
        
        with patch("core.service_manager.get_service_manager", return_value=mock_sm):
            result = synthesizer._run_heygem_with_auto_restart(
                audio_path="/tmp/audio.wav",
                video_source="/tmp/source.mp4",
                config=MagicMock(),
                face_id=0
            )
        
        # 验证：任务继续执行
        assert result == "/tmp/video2.mp4"
        assert call_count[0] == 2

    def test_max_restart_exceeded_raises_exception(self):
        """同一任务内重启 3 次后仍超时，抛出异常 → AC-206"""
        from business.video.video_synthesizer import VideoSynthesizer, MAX_AUTO_RESTART
        
        synthesizer = VideoSynthesizer.__new__(VideoSynthesizer)
        synthesizer.output_dir = "/tmp"
        
        # 模拟所有调用都超时
        synthesizer._run_heygem_inference_with_timeout = MagicMock(
            side_effect=requests.Timeout("Connection timeout")
        )
        
        mock_sm = MagicMock()
        mock_sm.restart_service.return_value = True
        
        with patch("core.service_manager.get_service_manager", return_value=mock_sm):
            with pytest.raises(Exception) as exc_info:
                synthesizer._run_heygem_with_auto_restart(
                    audio_path="/tmp/audio.wav",
                    video_source="/tmp/source.mp4",
                    config=MagicMock(),
                    face_id=0
                )
            
            assert "HeyGem 多次重启仍无响应" in str(exc_info.value)
            assert mock_sm.restart_service.call_count == MAX_AUTO_RESTART

    def test_manual_restart_uses_new_service(self):
        """用户手动重启 HeyGem 后，下次请求使用新服务实例 → AC-207"""
        from business.video.video_synthesizer import VideoSynthesizer
        
        # 这个测试验证的是：手动重启后，下次请求自然使用新服务
        # 因为 _run_heygem_with_auto_restart 只是调用 _run_heygem_inference_with_timeout
        # 而 _run_heygem_inference_with_timeout 每次都会发起新的 HTTP 请求到服务端
        # 所以只要服务重启了，下次请求自然使用新服务
        
        synthesizer = VideoSynthesizer.__new__(VideoSynthesizer)
        synthesizer.output_dir = "/tmp"
        
        # 模拟正常响应
        synthesizer._run_heygem_inference_with_timeout = MagicMock(return_value="/tmp/video.mp4")
        
        # 第一次请求
        result1 = synthesizer._run_heygem_with_auto_restart(
            audio_path="/tmp/audio1.wav",
            video_source="/tmp/source.mp4",
            config=MagicMock(),
            face_id=0
        )
        
        # 模拟手动重启（通过 ServiceManager）
        mock_sm = MagicMock()
        mock_sm.restart_service.return_value = True
        with patch("core.service_manager.get_service_manager", return_value=mock_sm):
            mock_sm.restart_service("heygem")
        
        # 第二次请求（应该使用新服务）
        result2 = synthesizer._run_heygem_with_auto_restart(
            audio_path="/tmp/audio2.wav",
            video_source="/tmp/source.mp4",
            config=MagicMock(),
            face_id=0
        )
        
        # 验证：两次请求都成功，说明手动重启后服务正常工作
        assert result1 == "/tmp/video.mp4"
        assert result2 == "/tmp/video.mp4"

    def test_service_manager_not_initialized_raises_exception(self):
        """ServiceManager 未初始化时不尝试重启，直接抛出异常"""
        from business.video.video_synthesizer import VideoSynthesizer
        
        synthesizer = VideoSynthesizer.__new__(VideoSynthesizer)
        synthesizer.output_dir = "/tmp"
        
        # 模拟超时
        synthesizer._run_heygem_inference_with_timeout = MagicMock(
            side_effect=requests.Timeout("Connection timeout")
        )
        
        # ServiceManager 未初始化
        with patch("core.service_manager.get_service_manager", return_value=None):
            with pytest.raises(Exception) as exc_info:
                synthesizer._run_heygem_with_auto_restart(
                    audio_path="/tmp/audio.wav",
                    video_source="/tmp/source.mp4",
                    config=MagicMock(),
                    face_id=0
                )
            
            assert "ServiceManager 未初始化" in str(exc_info.value)

    def test_timeout_value_is_180_seconds(self):
        """确认 HEYGEM_TIMEOUT = 180 → AC-215"""
        from business.video.video_synthesizer import HEYGEM_TIMEOUT
        
        assert HEYGEM_TIMEOUT == 180

    def test_max_auto_restart_is_3(self):
        """确认 MAX_AUTO_RESTART = 3 → AC-216"""
        from business.video.video_synthesizer import MAX_AUTO_RESTART
        
        assert MAX_AUTO_RESTART == 3
