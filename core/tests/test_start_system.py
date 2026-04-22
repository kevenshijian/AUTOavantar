"""
Task-9: Python 启动器测试

测试 start_system.py 的功能
"""

import os
import sys
from unittest.mock import MagicMock, patch, Mock
from pathlib import Path

import pytest


class TestGetBaseDir:
    """测试 get_base_dir() 函数"""

    def test_dev_mode_returns_script_dir(self):
        """开发模式下返回脚本所在目录 → AC-217"""
        from start_system import get_base_dir
        
        result = get_base_dir()
        
        # 验证：返回的是 Path 对象
        assert isinstance(result, Path)
        # 验证：目录存在
        assert result.exists()
        # 验证：包含 main.py（项目根目录的特征）
        assert (result / "main.py").exists() or (result / "start_system.py").exists()


class TestSetupEnvironment:
    """测试 setup_environment() 函数"""

    def test_py310_not_found_raises_error(self):
        """py310 目录不存在时抛出 FileNotFoundError → AC-209"""
        from start_system import setup_environment
        
        fake_dir = Path("/nonexistent/path")
        
        with pytest.raises(FileNotFoundError) as exc_info:
            setup_environment(fake_dir)
        
        assert "Python 目录不存在" in str(exc_info.value)


class TestStartProcess:
    """测试 start_process() 函数"""

    def test_start_process_on_windows(self):
        """Windows 上使用 start 命令在新窗口启动"""
        from start_system import start_process
        
        with patch('sys.platform', 'win32'):
            with patch('subprocess.run') as mock_run:
                start_process(
                    name="TestService",
                    cmd=["python", "app.py"],
                    cwd=Path("."),
                    env=os.environ.copy(),
                    title="Test Window"
                )
                
                # 验证：调用了 subprocess.run
                mock_run.assert_called_once()

    def test_start_process_creates_window_with_title(self):
        """启动时创建带标题的窗口"""
        from start_system import start_process
        
        with patch('sys.platform', 'win32'):
            with patch('subprocess.run') as mock_run:
                start_process(
                    name="TestService",
                    cmd=["python", "app.py"],
                    cwd=Path("."),
                    env=os.environ.copy(),
                    title="Custom Title"
                )
                
                # 验证：命令包含窗口标题
                call_args = mock_run.call_args[0][0]
                assert "Custom Title" in " ".join(call_args)


class TestMainFunction:
    """测试 main() 函数"""

    def test_main_exits_on_missing_py310(self):
        """py310 不存在时打印错误并退出 → AC-209"""
        from start_system import main
        
        # 使用临时目录（没有 py310）
        fake_dir = Path("/nonexistent/path")
        
        with patch('start_system.get_base_dir', return_value=fake_dir):
            with patch('sys.exit') as mock_exit:
                with patch('builtins.input', return_value=''):
                    main()
                    
                    mock_exit.assert_called_once_with(1)

    def test_main_starts_services_in_order(self):
        """依次启动 IndexTTS、HeyGem、后端、前端 → AC-198"""
        # 创建临时目录结构
        import tempfile
        import shutil
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            py310 = tmp_path / "py310"
            py310.mkdir()
            (py310 / "python.exe").touch()
            (py310 / "Scripts").mkdir()
            (py310 / "ffmpeg").mkdir()
            (py310 / "ffmpeg" / "bin").mkdir()
            (py310 / "Lib").mkdir()
            (py310 / "Lib" / "site-packages").mkdir()
            (py310 / "Lib" / "site-packages" / "torch").mkdir()
            (py310 / "Lib" / "site-packages" / "torch" / "lib").mkdir()
            (py310 / "Library").mkdir()
            (py310 / "Library" / "bin").mkdir()
            
            indextts = tmp_path / "index-tts-2"
            indextts.mkdir()
            (indextts / "app.py").touch()
            
            heygem = tmp_path / "heygem-win-50-onnx"
            heygem.mkdir()
            (heygem / "app.py").touch()
            
            backend = tmp_path / "backend"
            backend.mkdir()
            (backend / "api").mkdir()
            (backend / "api" / "main.py").touch()
            
            frontend = tmp_path / "frontend"
            frontend.mkdir()
            (frontend / "package.json").touch()
            
            from start_system import main
            
            start_order = []
            
            def mock_start_process(name, **kwargs):
                start_order.append(name)
            
            # 模拟 time.sleep 在最后进入 while True 前抛出 KeyboardInterrupt
            sleep_count = [0]
            def mock_sleep(seconds):
                sleep_count[0] += 1
                if sleep_count[0] > 5:  # 在打开浏览器后停止
                    raise KeyboardInterrupt()
            
            with patch('start_system.get_base_dir', return_value=tmp_path):
                with patch('start_system.start_process', side_effect=mock_start_process):
                    with patch('time.sleep', side_effect=mock_sleep):
                        with patch('os.startfile'):
                            main()
            
            # 验证：启动顺序正确
            assert start_order == ["IndexTTS", "HeyGem", "FastAPI Backend", "Vue3 Frontend"]

    def test_service_start_interval_is_5_seconds(self):
        """各服务启动间隔 5 秒"""
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            py310 = tmp_path / "py310"
            py310.mkdir()
            (py310 / "python.exe").touch()
            (py310 / "Scripts").mkdir()
            (py310 / "ffmpeg").mkdir()
            (py310 / "ffmpeg" / "bin").mkdir()
            (py310 / "Lib").mkdir()
            (py310 / "Lib" / "site-packages").mkdir()
            (py310 / "Lib" / "site-packages" / "torch").mkdir()
            (py310 / "Lib" / "site-packages" / "torch" / "lib").mkdir()
            (py310 / "Library").mkdir()
            (py310 / "Library" / "bin").mkdir()
            
            # 创建服务文件以触发完整启动流程
            indextts = tmp_path / "index-tts-2"
            indextts.mkdir()
            (indextts / "app.py").touch()
            
            heygem = tmp_path / "heygem-win-50-onnx"
            heygem.mkdir()
            (heygem / "app.py").touch()
            
            backend = tmp_path / "backend"
            backend.mkdir()
            (backend / "api").mkdir()
            (backend / "api" / "main.py").touch()
            
            frontend = tmp_path / "frontend"
            frontend.mkdir()
            (frontend / "package.json").touch()
            
            from start_system import main
            
            sleep_calls = []
            
            def track_sleep(seconds):
                sleep_calls.append(seconds)
                if len(sleep_calls) > 5:
                    raise KeyboardInterrupt()
            
            with patch('start_system.get_base_dir', return_value=tmp_path):
                with patch('start_system.start_process'):
                    with patch('time.sleep', side_effect=track_sleep):
                        with patch('os.startfile'):
                            main()
            
            # 验证：前 4 个 sleep 都是 5 秒（服务启动间隔）
            for seconds in sleep_calls[:4]:
                assert seconds == 5
            # 第 5 个是 3 秒（打开浏览器前）
            assert sleep_calls[4] == 3
