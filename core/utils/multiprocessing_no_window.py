"""
Multiprocessing 控制台窗口抑制模块

在 Windows 上，Python 3.10 的 multiprocessing.Process 不支持 creationflags 参数，
导致子进程在 spawn 时会创建控制台窗口。

此模块通过 monkey patch 修改 multiprocessing.popen_spawn_win32.Popen.__init__，
在进程创建时添加 CREATE_NO_WINDOW 标志，从根本上阻止控制台窗口的创建。

使用方法：
    在程序入口点（如 main.py）的最开始导入此模块：
    from core.utils.multiprocessing_no_window import patch_multiprocessing
    patch_multiprocessing()
"""

import sys
import os


def patch_multiprocessing():
    """
    Monkey patch multiprocessing 在 Windows 上创建进程时使用 CREATE_NO_WINDOW

    这是在进程创建时就阻止控制台窗口弹出，而不是在进程启动后隐藏窗口。
    必须在导入任何使用 multiprocessing 的模块之前调用此函数。
    """
    if sys.platform != 'win32':
        return True

    try:
        import _winapi
        import msvcrt
        from multiprocessing import spawn, util
        from multiprocessing.context import reduction, get_spawning_popen, set_spawning_popen

        # CREATE_NO_WINDOW 标志: 0x08000000
        # 阻止创建控制台窗口
        CREATE_NO_WINDOW = 0x08000000

        # 获取原始的 Popen 类和 _close_handles 函数
        from multiprocessing.popen_spawn_win32 import Popen, _close_handles

        # 保存原始方法（用于调试）
        _original_init = Popen.__init__

        def _patched_init(self, process_obj):
            """修补后的 Popen.__init__，添加 CREATE_NO_WINDOW 标志"""
            prep_data = spawn.get_preparation_data(process_obj._name)

            rhandle, whandle = _winapi.CreatePipe(None, 0)
            wfd = msvcrt.open_osfhandle(whandle, 0)
            cmd = spawn.get_command_line(parent_pid=os.getpid(),
                                         pipe_handle=rhandle)
            cmd = ' '.join('"%s"' % x for x in cmd)

            python_exe = spawn.get_executable()

            # 检查是否在 venv 中运行
            WINENV = not (sys.executable == sys._base_executable)
            if WINENV and python_exe == sys.executable:
                python_exe = sys._base_executable
                env = os.environ.copy()
                env["__PYVENV_LAUNCHER__"] = sys.executable
            else:
                env = None

            with open(wfd, 'wb', closefd=True) as to_child:
                try:
                    # 【关键修改】添加 CREATE_NO_WINDOW 标志
                    hp, ht, pid, tid = _winapi.CreateProcess(
                        python_exe, cmd,
                        None, None, False, CREATE_NO_WINDOW, env, None, None)
                    _winapi.CloseHandle(ht)
                except:
                    _winapi.CloseHandle(rhandle)
                    raise

                self.pid = pid
                self.returncode = None
                self._handle = hp
                self.sentinel = int(hp)

                # 使用原始的 _close_handles 函数
                self.finalizer = util.Finalize(self, _close_handles,
                                               (self.sentinel, int(rhandle)))

                set_spawning_popen(self)
                try:
                    reduction.dump(prep_data, to_child)
                    reduction.dump(process_obj, to_child)
                finally:
                    set_spawning_popen(None)

        # 应用 monkey patch
        Popen.__init__ = _patched_init
        return True

    except Exception as e:
        # 如果 patch 失败，记录错误但不中断程序
        import logging
        logging.warning(f"multiprocessing CREATE_NO_WINDOW patch 失败: {e}")
        return False


# 自动应用 patch（当模块被导入时）
# 注意：这种方式可能在某些情况下不够早，建议显式调用 patch_multiprocessing()
_patched = False

def ensure_patched():
    """确保 patch 已应用"""
    global _patched
    if not _patched:
        _patched = patch_multiprocessing()
    return _patched
