import os
import time

import allure

from common.conftest import *
from common.common import Constants
from common.logger import log_info, log_step, log_error, log_error_continue
from library.can_driver.CAN import CANDevice
from xlsx_to_json import xlsx_to_json
from json_reader import load_json_files
from utils.can_id_checker import (
    build_can_id_whitelist,
    build_can_id_period_map,
    build_ecu_info_map,
    check_can_id_periods,
    check_upgrade_scenario,
    check_high_voltage_signal, monitor_liquid_cooling_signal,
)
# from TSMasterAPI import *
# initialize_lib_tsmaster("TSMaster".encode("utf8"))


class TestDemo:
    def setup_method(self, *args, **kwargs):
        test_name = os.environ.get('PYTEST_CURRENT_TEST')
        log_info(f"[SETUP] {test_name}")

        # 每次运行前，自动把 OTA.xlsx 转换为 json
        log_info("正在转换 OTA.xlsx 到 JSON...")
        self.ota_data = xlsx_to_json("OTA.xlsx", "ota_json")
        log_info(f"已转换 {len(self.ota_data)} 个 sheet")

        # 读取所有 json 文件到变量
        log_info("正在读取 JSON 文件...")
        self.json_data = load_json_files("ota_json")
        log_info(f"已读取 {len(self.json_data)} 个 JSON 文件")

        # 初始化 CAN 设备
        self.can = CANDevice()
        self.can.initialize(True, True, True)
        self.can.connect([
            [{"type": "canfd", "arb_kbps": 500, "data_kbps": 2000}] * 4,
            # [{"type": "can", "kbps": 500}] * 4,
            [{"type": "canfd", "arb_kbps": 500, "data_kbps": 2000}] * 4,
        ])
        log_info(f"已连接 {len(self.can.devices)} 台 CAN 设备")

        # 记录 SN 与 device_index 的对应关系
        self.device_info = []
        for idx, dev in enumerate(self.can.devices):
            info = f"index={idx}, serial={dev['serial']}"
            self.device_info.append(info)
            log_info(info)

        # 开始记录 BLF 日志（全局只调用一次）
        log_dir = os.path.join(Constants.BASE_DIR, "blf_logs")
        self.blf_log_path = self.can.start_logging(log_dir)
        log_info(f"开始记录 BLF: {self.blf_log_path}")

    def teardown_method(self, *args, **kwargs):
        test_name = os.environ.get('PYTEST_CURRENT_TEST')
        log_info(f"[TEARDOWN] {test_name}")
        if hasattr(self, "can"):
            # 停止 BLF 日志记录
            if hasattr(self, "blf_log_path"):
                try:
                    stopped_path = self.can.stop_logging()
                    log_info(f"停止记录 BLF: {stopped_path}")
                except Exception as e:
                    log_info(f"停止 BLF 记录失败: {e}")
            self.can.finalize()
            log_info("已断开 CAN 设备连接")

    @allure.title("test_001")
    @allure.description("CAN 发送接收测试示例")
    def test_01(self):
        log_info("=== 开始执行 test_01 ===")
        # 示例：读取 general 和 signal 数据
        general_list = self.json_data.get("general", [])
        signal_list = self.json_data.get("signal", [])
        log_info(f"general 配置数量: {len(general_list)}")
        log_info(f"signal 配置数量: {len(signal_list)}")

        # 启动后台线程实时接收所有 CAN/CANFD 报文
        self.can.start_receiving_thread(msg_types=("canfd", "canfd"), interval_ms=10)
        log_info("已启动后台 CAN 报文接收线程")

        # 构建 CANID 白名单集合
        self.can_id_whitelist = build_can_id_whitelist(general_list)
        log_info(f"CANID 白名单数量: {len(self.can_id_whitelist)}")
        if self.can_id_whitelist:
            log_info(f"白名单: {[hex(x) for x in sorted(self.can_id_whitelist)]}")
            # 从后台线程缓存中获取所有已接收的报文

        #打印所有信息
        time.sleep(10)
        all_msgs = self.can.get_received_messages(clear=True)
        log_info(f"后台线程累计接收到 {len(all_msgs)} 帧报文")
        for idx, msg in enumerate(all_msgs):
            log_info(f"报文 {idx}: id=0x{msg['id']:03X},seria = {msg['serial']} channel={msg['channel']} time={msg['time']:.6f}s, data={' '.join(f'{byte:02X}' for byte in msg['data'])}")

        # 高压判断
        # with log_step("Step1", "监控高压信号，准备升级"):
        #     status, result = check_high_voltage_signal(
        #         lambda: self.can.get_received_messages(clear=True), 0x1F0
        #     )
        #     log_info(f"高压信号检测结果: {status}, {result}")

        # while True:
        #     # 从后台线程缓存中获取所有已接收的报文
        #     all_msgs = self.can.get_received_messages(clear=True)
        #     log_info(f"后台线程累计接收到 {len(all_msgs)} 帧报文")
        #     for idx, msg in enumerate(all_msgs):
        #         log_info(f"报文 {idx}: id=0x{msg['id']:03X},seria = {msg['serial']} channel={msg['channel']} time={msg['time']:.6f}s, data={' '.join(f'{byte:02X}' for byte in msg['data'])}")
        #
        #     # 监控液冷信号 + 周期 + payload
        #     with log_step("Step2","监控液冷信号 + 周期 + payload"):
        #         ok, msg, prev_time, next_time = monitor_liquid_cooling_signal(
        #             all_msgs,
        #             liquid_cooling_canid=0x160,
        #             period_ms=10  # 期望周期 10ms
        #         )
        #         if not ok:
        #             log_info(f"液冷信号周期异常: 上一帧 {prev_time}s, 下一帧 {next_time}s")
        #
        #
        #     # 检查目前升级的控制器是否存在白名单报文，如果存在白名单报文，该白名单报文不做监控。其他没有升级的ecu的白名单报文要监控id以及周期
        #
        #     # 检查当前升级的ecu是否出现11 01 复位。如果在发送51 01后的2min中内不监控非黑名单报文。2min后出现就白名单以外的报文就可以判定为fail。
        #
        #     # 按升级场景检查白名单
        #     # 根据接收到的 resp CANID 自动判断正在升级的 ECU，其白名单报文允许缺失
        #     ecu_info_map = build_ecu_info_map(general_list)
        #     scenario_ok, scenario_result = check_upgrade_scenario(
        #         all_msgs,
        #         self.can_id_whitelist,
        #         upgrade_response_data=(0x12, 0xf5),
        #         grace_period_s=120,
        #         ecu_info_map=ecu_info_map,
        #     )
        #     log_info(f"升级场景判断结果: {scenario_result}")
        #     if not scenario_ok:
        #         log_error(f"{scenario_ok},存在异常报文或缺失: {scenario_result}")
        #
        #
        #     #监控低压信号做判断
        #     with log_step("Step4", "监控低压信号，准备低压升级"):
        #         status, result = check_high_voltage_signal(
        #             lambda: self.can.get_received_messages(clear=True), 0x343
        #         )
        #         if status:
        #             log_info(f"低压压信号检测结果: {status}, {result}")
        #             break
        # # 低压判断
        # # 新一轮低压升级check
        #
        # # if 所有通道都出现了54
        #
        # log_info("=== test_01 执行结束 ===")

