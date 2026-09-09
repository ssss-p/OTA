import os
import time

import allure

from common.conftest import *
from common.common import Constants
from common.logger import log_info, log_step, log_error, log_error_continue
from library.can_driver.CAN_TSMaster_Thread import CANDevice
from xlsx_to_json import xlsx_to_json
from json_reader import load_json_files
from utils.can_id_checker import (
    build_can_id_whitelist,
    build_bus_whitelist,
    build_ecu_info_map,
    build_can_id_period_map,
    check_upgrade_scenario,
    check_high_voltage_signal,
    monitor_liquid_cooling_signal,
    UpgradeWindowChecker,
)
from utils.uds_upgrade_checker import UDSUpgradeMonitor, wait_for_upgrade_completion


class TestDemo1:
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
            # [{"type": "canfd", "arb_kbps": 500, "data_kbps": 2000}] * 4,
        ])
        log_info(f"已连接 {len(self.can.devices)} 台 CAN 设备")

        # 记录 SN 与 device_index 的对应关系
        self.device_info = []
        for idx, dev in enumerate(self.can.devices):
            info = f"index={idx}, serial={dev['serial']}"
            self.device_info.append(info)
            log_info(info)

        # 开始记录 BLF 日志
        log_dir = os.path.join(Constants.BASE_DIR, "blf_logs")
        self.blf_log_path = self.can.start_logging(log_dir)
        log_info(f"开始记录 BLF: {self.blf_log_path}")

    def teardown_method(self, *args, **kwargs):
        test_name = os.environ.get('PYTEST_CURRENT_TEST')
        log_info(f"[TEARDOWN] {test_name}")
        self.can.stop_logging()
        if hasattr(self, "can"):
            if hasattr(self, "blf_log_path"):
                try:
                    stopped_path = self.can.stop_logging()
                    log_info(f"停止记录 BLF: {stopped_path}")
                except Exception as e:
                    log_info(f"停止 BLF 记录失败: {e}")
            self.can.finalize()
            log_info("已断开 CAN 设备连接")

    def _wait_high_voltage(self, hv_canid=0x343, timeout_s=300):
        """等待高压信号，超时返回 False。"""
        start_time = time.time()
        with log_step("Step1", "监控高压信号，准备升级"):
            while time.time() - start_time < timeout_s:
                status, result = check_high_voltage_signal(
                    lambda: self.can.get_received_messages(clear=True),
                    hv_canid=hv_canid,
                )
                log_info(f"高压信号检测结果: {status}, {result}")
                if status:
                    return True
                time.sleep(0.5)
        log_error(f"{timeout_s}s 内未收到高压信号 0x{hv_canid:03X}")
        return False

    def _wait_low_voltage(self, lv_canid=0x343, timeout_s=300):
        """等待低压信号，超时返回 False。"""
        start_time = time.time()
        with log_step("Step3", "监控低压信号，准备低压升级"):
            while time.time() - start_time < timeout_s:
                status, result = check_high_voltage_signal(
                    lambda: self.can.get_received_messages(clear=True),
                    hv_canid=lv_canid,
                )
                log_info(f"低压信号检测结果: {status}, {result}")
                if status:
                    return True
                time.sleep(0.5)
        log_error(f"{timeout_s}s 内未收到低压信号 0x{lv_canid:03X}")
        return False

    def _extract_uds_payload(self, data):
        """
        从 CAN 帧数据中提取 UDS 有效载荷（去掉 ISO-TP PCI 头）。

        - 单帧 (SF): 0x0X，PCI 1 字节，数据从索引 1 开始
        - 首帧 (FF): 0x1X YY，PCI 2 字节，数据从索引 2 开始
        - 连续帧/流控帧: 通常不携带完整服务数据，返回 None
        """
        if not data:
            return None
        pci_type = (data[0] >> 4) & 0x0F
        if pci_type == 0x00:
            # 单帧，数据从索引 1 开始
            return data[1:]
        elif pci_type == 0x01:
            # 首帧，数据从索引 2 开始
            return data[2:]
        # 连续帧/流控帧不处理
        return None

    def _wait_upgrade_cycle_end(self, ecu_info_map, timeout_s=600):
        """
        等待上一次 OTA 升级完成（锁定当前升级周期结束），按 ECU 分别判断。

        全局结束标志（不区分 ECU，任意 CANID 收到即可）：
            - 清除 DTC 请求：14 FF FF FF
            - 清除 DTC 响应：54

        ECU 级别结束标志（通过 CANID 区分是哪个 ECU 完成）：
            - DID 读取响应：62 F1 89 / 62 F0 89 / 62 F1 80

        只有当全局 2 个标志全部收到，且每个 ECU 的 3 个 DID 响应都收到后，
        才认为所有 ECU 上一次 OTA 升级完成。
        """
        start_time = time.time()
        log_info(f"[等待上一次升级完成] ecu_info_map={ecu_info_map}")

        # 全局结束标志：不区分 ECU
        global_flags = [
            (0x14, 0xFF, 0xFF, 0xFF),  # 清除 DTC 请求
            (0x54,),  # 清除 DTC 响应
        ]

        # ECU 级别结束标志：通过 CANID 区分 ECU
        ecu_did_flags = [
            (0x62, 0xF1, 0x89),
            (0x62, 0xF0, 0x89),
            (0x62, 0xF1, 0x80),
        ]

        # 全局状态
        global_seen = set()

        # 为每个 ECU 维护状态
        ecu_states = {}
        for resp_canid, info in ecu_info_map.items():
            ecu_name = f"{info['bus_name']}-ECU{info['ecu_index']}"
            ecu_states[resp_canid] = {
                "name": ecu_name,
                "seen_dids": set(),
                "done": False,
            }

        with log_step("Step0", "等待上一次 OTA 升级完成"):
            while time.time() - start_time < timeout_s:
                all_msgs = self.can.get_received_messages(clear=True)
                if all_msgs:
                    log_info(f"等待升级完成中，后台累计收到 {len(all_msgs)} 帧报文")

                for msg in all_msgs:
                    msg_id = msg.get("id")
                    data = msg.get("data") or []
                    payload = self._extract_uds_payload(data)

                    # 调试用：打印原始报文和提取的 UDS payload
                    data_str = " ".join(f"{b:02X}" for b in data)
                    payload_str = " ".join(f"{b:02X}" for b in payload) if payload else "None"
                    msg_id_str = f"0x{msg_id:03X}" if msg_id is not None else "None"
                    log_info(f"[结束标志检查] msg_id={msg_id_str}, data={data_str}, payload={payload_str}")

                    if payload is None:
                        continue

                    # 检查全局标志（任意 CANID）
                    for flag in global_flags:
                        flag_str = " ".join(f"{b:02X}" for b in flag)
                        if len(payload) >= len(flag) and all(payload[i] == flag[i] for i in range(len(flag))):
                            if flag not in global_seen:
                                global_seen.add(flag)
                                log_info(f"[全局] 检测到结束标志 {flag_str}, canid=0x{msg_id:03X}")

                    # 检查 ECU 级别 DID 响应（通过 CANID 区分）
                    if msg_id in ecu_states:
                        state = ecu_states[msg_id]
                        for flag in ecu_did_flags:
                            flag_str = " ".join(f"{b:02X}" for b in flag)
                            if len(payload) >= len(flag) and all(payload[i] == flag[i] for i in range(len(flag))):
                                if flag not in state["seen_dids"]:
                                    state["seen_dids"].add(flag)
                                    log_info(f"[{state['name']}] 检测到 DID 结束标志 {flag_str}, canid=0x{msg_id:03X}")

                # 检查全局标志是否收齐
                global_missing = len(global_flags) - len(global_seen)
                if global_missing > 0:
                    log_info(f"[全局] 还差 {global_missing} 个结束标志")

                # 检查每个 ECU 的完成情况
                all_done = (global_missing == 0)
                for resp_canid, state in ecu_states.items():
                    did_missing = len(ecu_did_flags) - len(state["seen_dids"])
                    if did_missing == 0:
                        if not state["done"]:
                            state["done"] = True
                            elapsed = time.time() - start_time
                            did_markers = [" ".join(f"{b:02X}" for b in m) for m in state["seen_dids"]]
                            did_str = ", ".join(did_markers)
                            log_info(f"[{state['name']}] 已收齐所有 DID 结束标志: {did_str}, canid=0x{resp_canid:03X}, 耗时 {elapsed:.1f}s")
                    else:
                        all_done = False
                        log_info(f"[{state['name']}] 还差 {did_missing} 个 DID 结束标志")

                if all_done:
                    elapsed = time.time() - start_time
                    log_info(f"所有 ECU 上一次升级完成，耗时 {elapsed:.1f}s")
                    return True

                time.sleep(0.5)

        log_error(f"等待升级完成超时 ({timeout_s}s)，未检测到结束标志")
        return False

    def _monitor_upgrade_stage(self, ecu_info_map, stage_name="高压升级阶段", timeout_s=600, can_id_whitelist=None, period_map=None):
        """监控一个升级阶段，直到所有 ECU 完成或超时。"""
        start_time = time.time()
        total_ecu_count = len(ecu_info_map)
        log_info(f"[{stage_name}] 开始监控，ECU 数量: {total_ecu_count}")
        
        if can_id_whitelist is None:
            can_id_whitelist = set()
        
        if period_map is None:
            period_map = {}

        if total_ecu_count == 0:
            log_error(f"[{stage_name}] ecu_info_map 为空，无法监控升级流程")
            return False

        # 构建 ECU 监控器（基于 ecu_info_map）
        # 先按总线聚合：同一条总线的所有 ECU 的白名单/req/resp 合并，作为整条总线的合法 CANID
        bus_valid_canids = {}   # bus_name -> set(合法CANID并集)
        bus_whitelist_periods = {}  # bus_name -> {canid: period_ms or None}
        for resp_canid, info in ecu_info_map.items():
            bus_name = info["bus_name"]
            req = info.get("req_canid") or 0x700
            wl = info.get("whitelist_canids", set())
            bus_valid_canids.setdefault(bus_name, set()).update(wl)
            bus_valid_canids[bus_name].update({req, resp_canid, 0x7DF})
            bl = bus_whitelist_periods.setdefault(bus_name, {})
            for c in wl:
                bl[c] = period_map.get(c)

        # 每条总线一个窗口检查器（整条总线共享，每对 28 83 03/28 80 03 判定一次）
        bus_checkers = {}
        for resp_canid, info in ecu_info_map.items():
            bus_name = info["bus_name"]
            if bus_name not in bus_checkers:
                bus_channel = info.get("channel")
                bus_checkers[bus_name] = UpgradeWindowChecker(
                    ecu_name=bus_name,
                    whitelist_periods=bus_whitelist_periods.get(bus_name, {}),
                    valid_canids=bus_valid_canids.get(bus_name, set()),
                    func_canid=0x7DF,
                    req_canid=info.get("req_canid"),
                    channel=bus_channel,
                )
                log_info(f"[窗口检查] 总线[{bus_name}] 按 channel={bus_channel} 单独 check")

        ecu_monitors = {}
        for resp_canid, info in ecu_info_map.items():
            ecu_name = f"{info['bus_name']}-ECU{info['ecu_index']}"
            req_canid = info.get("req_canid") or 0x700
            whitelist_canids = info.get("whitelist_canids", set())
            # 该 ECU 的合法 CANID = 白名单 + reqid + respid + 功能寻址 0x7DF
            valid_canids = whitelist_canids | {req_canid, resp_canid, 0x7DF}
            ecu_channel = info.get("channel")
            ecu_monitors[ecu_name] = {
                "monitor": UDSUpgradeMonitor(
                    req_canid=req_canid,
                    resp_canid=resp_canid,
                    func_canid=0x7DF,
                    name=ecu_name,
                    channel=ecu_channel,
                ),
                "resp_canid": resp_canid,
                "req_canid": req_canid,
                "whitelist_canids": whitelist_canids,
                "valid_canids": valid_canids,
                "bus_name": info["bus_name"],
                "ecu_index": info.get("ecu_index") or 0,
            }
            log_info(f"[{stage_name}] 添加 ECU 监控: {ecu_name}, resp=0x{resp_canid:03X}, req=0x{req_canid:03X}, channel={ecu_channel}, 白名单={len(whitelist_canids)}个")

        # 按 BUS NAME 分组，找出每个总线上最后一个 ECU（ECUindex 最大）
        bus_last_ecu = {}
        for resp_canid, info in ecu_info_map.items():
            bus_name = info["bus_name"]
            ecu_index = info.get("ecu_index") or 0
            if bus_name not in bus_last_ecu or ecu_index > bus_last_ecu[bus_name]["ecu_index"]:
                bus_last_ecu[bus_name] = {
                    "resp_canid": resp_canid,
                    "ecu_index": ecu_index,
                    "ecu_name": f"{bus_name}-ECU{ecu_index}",
                }

        # 等待所有 ECU 的最后一个完成
        all_done = False
        loop_count = 0
        # 液冷报文 0x111 全程时间戳（收尾做周期检查）
        lc_times = []
        with log_step("Step2", stage_name):
            while time.time() - start_time < timeout_s and not all_done:
                loop_count += 1
                # 获取报文（已按时间排序）
                all_msgs = self.can.get_received_messages(clear=True)
                log_info(f"[{stage_name}] 第 {loop_count} 轮循环，收到 {len(all_msgs)} 帧报文")

                # # 液冷报文 0x111 全程时间戳累积
                # for m in all_msgs:
                #     if m.get("id") == 0x111:
                #         lc_times.append(m.get("time"))
                
                # 收集所有 ECU 的 req/resp CAN ID 及功能寻址 0x7DF，只打印这些报文
                log_target_canids = {0x7DF}
                for ecu_name, ecu_info in ecu_monitors.items():
                    log_target_canids.add(ecu_info["req_canid"])
                    log_target_canids.add(ecu_info["resp_canid"])

                # 打印收到的报文（仅 reqid/respid/0x7DF 功能寻址）——已注释，避免日志过大
                # for msg in all_msgs:
                #     msg_id = msg.get("id")
                #     if msg_id not in log_target_canids:
                #         continue
                #     data = msg.get("data", [])
                #     direction = msg.get("direction", "Rx")
                #     channel = msg.get("channel", 0)
                #     msg_type = msg.get("type", "CAN")
                #     data_hex = " ".join(f"{b:02X}" for b in data)
                #     msg_time = msg.get("time", 0)
                #     log_info(f"[{msg_type}] Ch{channel} {direction} ID=0x{msg_id:03X} Time={msg_time:.6f}s Data=[{data_hex}]")

                # 处理所有 ECU 的升级进度
                for ecu_name, ecu_info in ecu_monitors.items():
                    monitor = ecu_info["monitor"]
                    monitor.process_messages(all_msgs)

                # 1. 先更新 step_gate（前4步完成允许开窗）——必须在 chk.process 之前
                for bus_name, chk in bus_checkers.items():
                    if not chk.step_gate:
                        for ecu_name, ecu_info in ecu_monitors.items():
                            if ecu_info["bus_name"] == bus_name and ecu_info["monitor"].current_step >= 5:
                                chk.set_step_gate(True)
                                break

                # 2. 让 chk.process 先处理报文——优先精确检测 28 83 03(开窗) 和 28 80 03(关窗) 帧
                #    此时 step_gate 已正确置位，不会用旧缓存开窗；28 80 03 能被正确识别记录精确关窗时间
                for bus_name, chk in bus_checkers.items():
                    if all_msgs:
                        chk.process(all_msgs)

                # 3. 兜底关窗：只有当 chk 还没通过 28 80 03 帧关窗，且本总线上
                #    所有 ECU 都已过窗口阶段（没有任何 ECU 处于 0 < step < 25，
                #    即没有 ECU 正在 5~24 步之间）时才兜底。
                #    注意：同总线顺序升级时，第1个 ECU 完成后 current_step=30>=24，
                #    但第2个 ECU 可能刚开始 step=3~5，此时若仅以"任意 ECU step>=24"
                #    判断，会在新窗口刚打开时就误关窗（结束时间早于开始时间）。
                for bus_name, chk in bus_checkers.items():
                    if chk.opened and not chk.closed:
                        bus_ecus = [
                            ecu_info for ecu_name, ecu_info in ecu_monitors.items()
                            if ecu_info["bus_name"] == bus_name
                        ]
                        # 检查是否还有 ECU 处于窗口流程中（step 在 1~24 之间且未完成）
                        any_in_window = any(
                            0 < ecu_info["monitor"].current_step < 25
                            and not ecu_info["monitor"].is_upgrade_success
                            for ecu_info in bus_ecus
                        )
                        if not any_in_window:
                            chk.set_end_step(True)

                # 每段(每个ECU)窗口结果：关窗时刻已在 chk 内部快照（数据不被下一个
                # ECU 开窗清空），这里逐段取出打印，保证每段窗口时间独立准确
                for bus_name, chk in bus_checkers.items():
                    for res in chk.pop_unreported_results():
                        time_range_str = (
                            f" [窗口时间: {res['start']:.6f}s ~ {res['end']:.6f}s]"
                            if res["start"] is not None and res["end"] is not None else ""
                        )
                        label = f"[{bus_name}] 升级窗口第{res['phase']}段(5~23步){time_range_str}"
                        if res["passed"]:
                            log_info(f"{label}检查 PASS: 白名单均出现且按周期发送, 无黑名单")
                        else:
                            for r in res["reasons"]:
                                log_error_continue(f"{label}检查 FAIL: {r}")

                for ecu_name, ecu_info in ecu_monitors.items():
                    monitor = ecu_info["monitor"]
                    current_step = monitor.current_step
                    current_desc = monitor.current_desc
                    is_success = monitor.is_upgrade_success
                    is_complete = monitor.is_upgrade_complete
                    elapsed = monitor.get_elapsed_time()
                    progress = monitor.get_progress_summary()

                    log_info(
                        f"[{ecu_name}] 步骤{current_step} {current_desc}, "
                        f"升级成功={is_success}, 升级完成={is_complete}, "
                        f"进度={progress['progress_pct']:.0f}%, 耗时={elapsed:.2f}s"
                    )

                    # 步骤缺失/顺序异常检测：已按需求关闭（step16/17/18 为"第二个segment"条件步骤，
                    # 单segment升级时本就不发，会持续误报"缺失或顺序异常"，故不再打印 error）

                upgrading = []
                completed = []
                for ecu_name, ecu_info in ecu_monitors.items():
                    monitor = ecu_info["monitor"]
                    if monitor.is_upgrade_complete:
                        completed.append(ecu_name)
                    else:
                        upgrading.append(ecu_name)

                # 按 BUS NAME 检查最后一个 ECU 是否完成
                all_bus_last_done = True
                for bus_name, last_info in bus_last_ecu.items():
                    last_ecu_name = last_info["ecu_name"]
                    last_monitor = ecu_monitors.get(last_ecu_name, {}).get("monitor")
                    if last_monitor is None:
                        all_bus_last_done = False
                        continue
                    last_success = last_monitor.is_upgrade_success
                    last_complete = last_monitor.is_upgrade_complete
                    done = last_complete
                    log_info(
                        f"[{bus_name}] 最后一个 ECU {last_ecu_name} "
                        f"升级成功={last_success}, 升级完成={last_complete}"
                    )
                    if not done:
                        all_bus_last_done = False

                log_info(
                    f"[{stage_name}] 完成判定检查: completed={len(completed)}/{total_ecu_count}, "
                    f"upgrading={len(upgrading)}, all_bus_last_done={all_bus_last_done}"
                )

                # 精确判定：所有 ECU 都升级成功 或 所有 ECU 都升级完成
                if len(completed) == total_ecu_count:
                    log_info(f"{stage_name} 全部 ECU 升级完成")
                    all_done = True
                    continue

                # 总线级判定：每路 CAN 的最后一个 ECU 都已完成
                if all_bus_last_done:
                    log_info(f"{stage_name} 每路 CAN 最后一个 ECU 均已完成")
                    all_done = True
                    continue

                # 兜底判定：没有 ECU 处于升级中，且已完成数量等于总 ECU 数量
                if len(upgrading) == 0 and len(completed) == total_ecu_count:
                    log_info(f"{stage_name} 全部 ECU 升级完成（兜底判定）")
                    all_done = True
                    continue

                # 如果还有 ECU 未开始升级，继续等待
                if len(upgrading) == total_ecu_count:
                    log_info(f"等待 ECU 开始升级... 已完成 {len(completed)}/{total_ecu_count}")

                time.sleep(0.5)

            # 兜底：窗口已打开但未收到关窗帧（超时/提前结束）也判定一次
            for bus_name, chk in bus_checkers.items():
                chk.finalize()
                for res in chk.pop_unreported_results():
                    time_range_str = (
                        f" [窗口时间: {res['start']:.6f}s ~ {res['end']:.6f}s]"
                        if res["start"] is not None and res["end"] is not None else ""
                    )
                    label = f"[{bus_name}] 升级窗口第{res['phase']}段(5~23步){time_range_str}"
                    if res["passed"]:
                        log_info(f"{label}检查 PASS: 白名单均出现且按周期发送, 无黑名单")
                    else:
                        for r in res["reasons"]:
                            log_error_continue(f"{label}检查 FAIL: {r}")

            # # 液冷报文 0x111 全程周期检查（整个运行过程，周期100ms±10%）
            # lc_passed, lc_reasons = self._check_liquid_cooling_period(lc_times, canid=0x111, period_ms=100, tol=0.10)
            # if lc_passed:
            #     log_info("液冷报文(0x111)全程周期检查 PASS: 周期100ms±10%")
            # else:
            #     for r in lc_reasons:
            #         log_error_continue(f"液冷报文(0x111)全程周期检查 FAIL: {r}")

        if not all_done:
            log_error(f"{stage_name} 超时，未完成所有 ECU 升级")

        return all_done

    def _check_liquid_cooling_period(self, times, canid=0x111, period_ms=100, tol=0.10):
        """全程检查液冷报文周期：相邻帧间隔是否都在 period_ms±tol 内。返回 (passed, reasons)。"""
        if len(times) < 2:
            return True, []  # 样本不足，不判定
        lower = period_ms * (1 - tol)
        upper = period_ms * (1 + tol)
        for i in range(1, len(times)):
            d = (times[i] - times[i - 1]) * 1000.0
            if d < lower or d > upper:
                return False, [
                    f"液冷报文 CANID=0x{canid:03X} 周期异常, 期望={period_ms}ms(±{tol:.0%}), "
                    f"两帧间隔={d:.1f}ms, 时间戳=[{times[i - 1]:.6f}, {times[i]:.6f}]"
                ]
        return True, []

    @allure.title("test_001")
    @allure.description("OTA 升级监控：高压升级 -> 低压升级 -> 全部完成")
    def test_01(self):

        log_info("=== 开始执行 test_01 ===")
        general_list = self.json_data.get("general", [])
        signal_list = self.json_data.get("signal", [])
        log_info(f"general 配置数量: {len(general_list)}")
        log_info(f"signal 配置数量: {len(signal_list)}")

        # 启动后台线程实时接收所有 CAN/CANFD 报文
        self.can.start_receiving_thread(msg_types=("canfd", "canfd"), interval_ms=10)
        log_info("已启动后台 CAN 报文接收线程")

        # 构建 CANID 白名单集合：同一总线的 id 以及周期存在对应关系
        self.can_id_whitelist = build_bus_whitelist(general_list)
        total_id_count = sum(len(v) for v in self.can_id_whitelist.values())
        log_info(f"CANID 白名单(按总线) 总线数: {len(self.can_id_whitelist)}, id总数: {total_id_count}")
        for bus_name, id_period_map in self.can_id_whitelist.items():
            detail = ", ".join(
                f"0x{k:03X}={('周期' + str(v) + 'ms') if v is not None else '无周期'}"
                for k, v in sorted(id_period_map.items())
            )
            log_info(f"[白名单] 总线[{bus_name}] ({len(id_period_map)}个): {detail}")

        # 构建 ECU 信息映射
        ecu_info_map = build_ecu_info_map(general_list)
        log_info(f"ECU 数量: {len(ecu_info_map)}")

        # 构建 CANID 周期映射
        self.can_id_period_map = build_can_id_period_map(general_list)
        log_info(f"CANID 周期映射数量: {len(self.can_id_period_map)}")

        # Step2: 监控完整的 UDS 30 步升级流程
        if not self._monitor_upgrade_stage(
            ecu_info_map,
            stage_name="UDS 30步升级流程监控",
            timeout_s=40*60,
            can_id_whitelist=self.can_id_whitelist,
            period_map=self.can_id_period_map,
        ):
            time.sleep(2)
            log_error("UDS 30步升级流程监控失败")


        log_info("=== 所有 ECU 升级完成，test_01 执行结束 ===")
