import os
import subprocess
import time
import ctypes
import inspect


class Constants:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOG_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')

def run_system_command(command, timeout=300):
    """
        执行系统指令
    """
    print(time.time(), "执行的指令：", command)
    process = subprocess.Popen(command,
                               creationflags=subprocess.CREATE_NO_WINDOW,
                               shell=True,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    process.wait(timeout=timeout)
    print(time.time(), "指令执行完成")


def run_system_command_with_window(command, timeout=300):
    """
        执行系统指令
    """
    print(time.time(), "执行的指令：", command)
    process = subprocess.Popen(command,
                               shell=True)
    process.wait(timeout=timeout)
    print(time.time(), "指令执行完成")


def _async_raise(tid, exctype):
    """raises the exception, performs cleanup if needed"""
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


def stop_thread(thread):
    try:
        _async_raise(thread.ident, SystemExit)
    except:
        pass
