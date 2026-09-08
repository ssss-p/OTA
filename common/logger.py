import datetime
import logging
import logging.handlers
import multiprocessing
import os
import sys
import win32api
import win32con
from contextlib import contextmanager

import allure


class CustomRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """自定义轮转日志，备份文件命名格式: YYYY-MM-DD_HH-MM-SS_N.log"""

    def _make_backup_name(self, n):
        base = self.baseFilename
        dir_name = os.path.dirname(base)
        base_name = os.path.basename(base)  # 2026-08-28_14-15-37.log
        stem = base_name[:-4] if base_name.endswith('.log') else base_name
        return os.path.join(dir_name, f"{stem}_{n}.log")

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = self._make_backup_name(i)
                dfn = self._make_backup_name(i + 1)
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
        dfn = self._make_backup_name(1)
        if os.path.exists(dfn):
            os.remove(dfn)
        os.rename(self.baseFilename, dfn)
        if not self.delay:
            self.stream = self._open()


# 关闭 faker 的日志
logging.getLogger("faker.factory").setLevel(logging.WARNING)
logging.getLogger("faker.providers").setLevel(logging.WARNING)

from common.common import Constants

LOG_QUEUE = multiprocessing.Queue()


class Logger:
    def __init__(self, loggername=None):
        self.loggername = loggername

        self.generate_logger()

    def show_msgbox(self, msg, title="提示"):
        result = win32api.MessageBox(0, f"{msg}\n\n点击确定后继续执行",
                                     f"{title}",
                                     win32con.MB_OK | win32con.MB_SYSTEMMODAL
                                     )
        if result == win32con.IDYES:
            return True
        elif result == win32con.IDNO:
            return False
        return False

    def generate_logger(self):
        """定义一个函数，回调logger实例"""
        # 创建一个logger
        self.logger = logging.getLogger(self.loggername)
        self.logger.setLevel(logging.DEBUG)

        # 创建一个handler，用于写入日志文件
        if not os.path.exists(Constants.LOG_BASE_DIR):
            os.makedirs(Constants.LOG_BASE_DIR)

        day = datetime.datetime.now().strftime('%m%d')
        log_root = os.path.join(Constants.LOG_BASE_DIR, day)
        if not os.path.exists(log_root):
            os.makedirs(log_root)
        logname = os.path.join(log_root, datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S.log'))

        # fh = logging.FileHandler(logname, encoding='utf-8')  # 指定utf-8格式编码，避免输出的日志文本乱码
        # 按文件大小输出日志，10M一个文件，自动在后面加1
        fh = CustomRotatingFileHandler(logname, mode='a', maxBytes=10240000, backupCount=200,
                                       encoding='utf-8')
        # fh.setLevel(logging.DEBUG)

        # 创建一个handler，用于将日志输出到控制台
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)

        # 定义handler的输出格式
        formatter = logging.Formatter('%(asctime)s-[%(name)s]-[%(levelname)s]-%(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        # 给logger添加handler
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def write_log_only(self, pstr):
        self.logger.info(pstr)

    def write_log(self, pstr, tp="info"):
        if tp == "info":
            self.logger.info(pstr)
            with allure.step(pstr):
                pass
        elif tp == "error":
            self.logger.error(pstr)
            # 根据用户配置，是否保留异常测试的现场，弹框提示  -s
            # from config.config_data import get_user_config
            # user_config = get_user_config()
            # if user_config.preserve_the_state_upon_failure is True:
            #     self.show_msgbox(rf"""{pstr}""")
            # 根据用户配置，是否保留异常测试的现场，弹框提示  -e

            with allure.step(pstr):
                assert False, pstr

        elif tp == "error_continue":
            self.logger.error(pstr)
            with allure.step(f"❌ {pstr}"):
                allure.attach(pstr, "错误详情", allure.attachment_type.TEXT)
        elif tp == "box":
            self.logger.info(pstr)
            
            # 保留测试的现场，弹框提示  -s
            self.show_msgbox(rf"""{pstr}""")
            # 保留测试的现场，弹框提示  -e
            
            with allure.step(pstr):
                pass
        elif tp == "debug":
            self.logger.debug(pstr)
            with allure.step(pstr):
                pass
        elif tp == "warning":
            self.logger.warning(pstr)
            with allure.step(f"⚠️ {pstr}"):
                pass
                # allure.attach(
                #     body=pstr,
                #     name="警告详情",
                #     attachment_type=allure.attachment_type.TEXT
                # )


logger = Logger("baimingdan")


def __log_only(*args, **kwargs):
    pstr = ""
    for item in args[:-1]:
        pstr += str(item) + " "
    pstr += str(args[-1])
    logger.write_log_only(pstr)
    return pstr


def __log_base(tp, *args, **kwargs):
    pstr = ""
    for item in args[:-1]:
        pstr += str(item) + " "
    pstr += str(args[-1])
    logger.write_log(pstr, tp=tp)
    return pstr


@contextmanager
def log_step(*args, **kwargs):
    """
        with log_step("步骤标题信息"):
            log_info("操作信息")
    """
    with allure.step(__log_only(*args, **kwargs)):
        yield


def log_info(*args, **kwargs):
    return __log_base("info", *args, **kwargs)


def log_debug(*args, **kwargs):
    return __log_base("debug", *args, **kwargs)


def log_warning(*args, **kwargs):
    return __log_base("warning", *args, **kwargs)


def log_error(*args, **kwargs):
    """
        出错，停止
    """
    return __log_base("error", *args, **kwargs)


def log_error_continue(*args, **kwargs):
    """
        出错，继续
    """
    return __log_base("error_continue", *args, **kwargs)


def log_box(*args, **kwargs):
    """
        弹框
    """
    return __log_base("box", *args, **kwargs)
