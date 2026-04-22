"""ServiceManager 单元测试"""

import os
import sys
import tempfile
import time
from unittest.mock import MagicMock, patch, Mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.service_manager import (
    ServiceManager, ServiceStatus, ManagedService, build_service_env, get_base_dir,
    get_service_manager, create_service_manager, destroy_service_manager
)


class TestServiceManager:
    """ServiceManager 单元测试"""
    
    @pytest.fixture
    def temp_py310_dir(self):
        """创建临时 py310 目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            py310_dir = os.path.join(tmpdir, "py310")
            os.makedirs(py310_dir)
            # 创建 python.exe 占位文件
            open(os.path.join(py310_dir, "python.exe"), "w").close()
            yield tmpdir
    
    def test_build_service_env_contains_all_keys(self, temp_py310_dir):
        """测试 build_service_env() 返回的 env 包含所有必需的环境变量"""
        with patch("core.service_manager.get_base_dir") as mock_get_base:
            mock_get_base.return_value = temp_py310_dir
            
            env = build_service_env()
            
            required_keys = [
                "PATH", "PYTHONEXECUTABLE", "FFMPEG_PATH", "CU_PATH",
                "CUDA_BIN_PATH", "GRADIO_TEMP_DIR", "USE_ONNX",
                "DS_BUILD_AIO", "DS_BUILD_SPARSE_ATTN", "HF_ENDPOINT",
                "HF_HOME", "TRANSFORMERS_CACHE", "XFORMERS_FORCE_DISABLE_TRITON",
                "PYTORCH_CUDA_ALLOC_CONF", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"
            ]
            
            for key in required_keys:
                assert key in env, f"缺少必需的环境变量: {key}"
            
            assert env["USE_ONNX"] == "true"
            assert env["DS_BUILD_AIO"] == "0"
            assert env["HF_ENDPOINT"] == "https://hf-mirror.com"
    
    def test_build_service_env_py310_not_found(self, temp_py310_dir):
        """测试 py310 目录不存在时抛出 FileNotFoundError"""
        with patch("core.service_manager.get_base_dir") as mock_get_base:
            non_existent_dir = os.path.join(temp_py310_dir, "non_existent")
            mock_get_base.return_value = non_existent_dir
            
            with pytest.raises(FileNotFoundError) as exc_info:
                build_service_env()
            
            assert "Python 环境未找到" in str(exc_info.value)
    
    def test_start_service_starts_subprocess(self, temp_py310_dir):
        """测试 start_service() 启动子进程后状态变化"""
        with patch("core.service_manager.get_base_dir") as mock_get_base:
            mock_get_base.return_value = temp_py310_dir
            
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None  # 进程存活
            
            with patch("subprocess.Popen", return_value=mock_process) as mock_popen:
                with patch.object(ServiceManager, "_wait_for_ready", return_value=True):
                    with patch("os.path.exists", return_value=True):
                        sm = ServiceManager()
                        
                        # 初始状态
                        initial_status = sm.get_status("indextts")
                        assert initial_status["status"] == ServiceStatus.STOPPED.value
                        
                        # 启动服务
                        result = sm.start_service("indextts")
                        
                        assert result is True
                        assert mock_popen.called
                        
                        new_status = sm.get_status("indextts")
                        assert new_status["status"] == ServiceStatus.RUNNING.value
                        assert new_status["pid"] == 12345
    
    def test_stop_service_stops_subprocess(self, temp_py310_dir):
        """测试 stop_service() 终止进程后 status = STOPPED, process = None"""
        with patch("core.service_manager.get_base_dir") as mock_get_base:
            mock_get_base.return_value = temp_py310_dir
            
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            
            with patch("subprocess.Popen", return_value=mock_process):
                with patch.object(ServiceManager, "_wait_for_ready", return_value=True):
                    with patch("os.path.exists", return_value=True):
                        sm = ServiceManager()
                        
                        # 先启动
                        sm.start_service("indextts")
                        
                        # 停止
                        with patch("subprocess.run") as mock_taskkill:
                            mock_taskkill_result = MagicMock()
                            mock_taskkill_result.returncode = 0
                            mock_taskkill.return_value = mock_taskkill_result
                            
                            result = sm.stop_service("indextts")
                            
                            assert result is True
                            new_status = sm.get_status("indextts")
                            assert new_status["status"] == ServiceStatus.STOPPED.value
                            assert new_status["pid"] is None
                            assert sm._services["indextts"].process is None
    
    def test_restart_service_restarts_subprocess(self, temp_py310_dir):
        """测试 restart_service() 等价于 stop + start"""
        with patch("core.service_manager.get_base_dir") as mock_get_base:
            mock_get_base.return_value = temp_py310_dir
            
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            
            with patch("subprocess.Popen", return_value=mock_process):
                with patch.object(ServiceManager, "_wait_for_ready", return_value=True):
                    with patch("os.path.exists", return_value=True):
                        sm = ServiceManager()
                        
                        sm.start_service("indextts")
                        
                        with patch("subprocess.run") as mock_taskkill:
                            mock_taskkill_result = MagicMock()
                            mock_taskkill_result.returncode = 0
                            mock_taskkill.return_value = mock_taskkill_result
                            
                            # 监控 restart 过程
                            old_pid = sm.get_status("indextts")["pid"]
                            
                            result = sm.restart_service("indextts")
                            
                            assert result is True
                            new_status = sm.get_status("indextts")
                            assert new_status["status"] == ServiceStatus.RUNNING.value
    
    def test_monitor_thread_detects_process_death(self, temp_py310_dir):
        """测试进程意外退出时监控线程将 status 设为 FAILED"""
        with patch("core.service_manager.get_base_dir") as mock_get_base:
            mock_get_base.return_value = temp_py310_dir
            
            mock_process = MagicMock()
            mock_process.pid = 12345
            
            with patch("subprocess.Popen", return_value=mock_process):
                with patch.object(ServiceManager, "_wait_for_ready", return_value=True):
                    with patch("os.path.exists", return_value=True):
                        sm = ServiceManager(monitor_interval=0.1)  # 使用短间隔加速测试
                        sm.start()  # 启动监控线程
                        sm.start_service("indextts")
                        
                        # 模拟进程退出
                        mock_process.poll.return_value = 1  # 非 None 表示进程已退出
                        
                        # 给监控线程一点时间检测
                        time.sleep(0.5)
                        
                        status = sm.get_status("indextts")
                        assert status["status"] == ServiceStatus.FAILED.value
                        assert "进程意外退出" in status["error_message"]
                        
                        sm.stop()
    
    def test_shutdown_stops_all_services(self, temp_py310_dir):
        """测试 shutdown() 终止所有子进程"""
        with patch("core.service_manager.get_base_dir") as mock_get_base:
            mock_get_base.return_value = temp_py310_dir
            
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            
            with patch("subprocess.Popen", return_value=mock_process):
                with patch.object(ServiceManager, "_wait_for_ready", return_value=True):
                    with patch("os.path.exists", return_value=True):
                        sm = ServiceManager()
                        sm.start()
                        sm.start_service("indextts")
                        sm.start_service("heygem")
                        
                        with patch("subprocess.run") as mock_taskkill:
                            mock_taskkill_result = MagicMock()
                            mock_taskkill_result.returncode = 0
                            mock_taskkill.return_value = mock_taskkill_result
                            
                            sm.shutdown()
                            
                            for name in ["indextts", "heygem"]:
                                status = sm.get_status(name)
                                assert status["status"] == ServiceStatus.STOPPED.value
    
    def test_get_status_returns_all_services(self, temp_py310_dir):
        """测试 get_status() 返回 dict 包含 indextts 和 heygem 两个 key"""
        with patch("core.service_manager.get_base_dir") as mock_get_base:
            mock_get_base.return_value = temp_py310_dir
            
            sm = ServiceManager()
            all_status = sm.get_status()
            
            assert "indextts" in all_status
            assert "heygem" in all_status
            
            for name in ["indextts", "heygem"]:
                assert "status" in all_status[name]
                assert "pid" in all_status[name]
                assert "started_at" in all_status[name]
                assert "uptime_seconds" in all_status[name]
    
    def test_start_service_unknown_service_fails(self, temp_py310_dir):
        """测试启动未知服务返回 False"""
        with patch("core.service_manager.get_base_dir") as mock_get_base:
            mock_get_base.return_value = temp_py310_dir
            
            sm = ServiceManager()
            result = sm.start_service("unknown_service")
            
            assert result is False
    
    def test_singleton_instance(self, temp_py310_dir):
        """测试单例模式工作正常"""
        destroy_service_manager()  # 清理之前的实例
        
        with patch("core.service_manager.get_base_dir") as mock_get_base:
            mock_get_base.return_value = temp_py310_dir
            
            sm1 = create_service_manager()
            sm2 = create_service_manager()
            
            assert sm1 is sm2
            
            retrieved = get_service_manager()
            assert retrieved is sm1
            
            destroy_service_manager()
            assert get_service_manager() is None
