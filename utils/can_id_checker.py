"""CAN ID 白名单检查工具"""

from collections import defaultdict

from common.logger import log_info, log_error_continue


def build_can_id_whitelist(general_list):
    """
    从 general 配置列表中解析 CANID 白名单。
    支持逗号分隔的多个 ID，如 "0x331,0x313,0x181"。

    Args:
        general_list: general sheet 转换后的字典列表

    Returns:
        set: 白名单 CANID 整数集合
    """
    whitelist = set()
    for item in general_list:
        canid_str = item.get("CANID")
        if not canid_str:
            continue
        for part in canid_str.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                whitelist.add(int(part, 16))
            except ValueError:
                continue
    return whitelist


def build_bus_whitelist(general_list):
    """
    按总线构建 CANID 白名单，同一总线的 id 以及周期存在对应关系。

    将 general 中每行的 CANID（逗号分隔）与 peroid（逗号分隔，按顺序一一对应）
    按 BUS NAME 分组聚合。

    Args:
        general_list: general sheet 转换后的字典列表

    Returns:
        dict: {bus_name: {canid_int: period_ms}}，周期未配置时为 None
    """
    bus_whitelist = {}
    for item in general_list:
        bus_name = item.get("BUS NAME")
        canid_str = item.get("CANID")
        if not bus_name or not canid_str:
            continue
        canids = [c.strip() for c in str(canid_str).split(",") if c.strip()]
        period_str = item.get("peroid")
        periods = [p.strip() for p in str(period_str).split(",") if p.strip()] if period_str else []
        bus_map = bus_whitelist.setdefault(bus_name, {})
        for i, canid in enumerate(canids):
            try:
                canid_int = int(canid, 16)
            except ValueError:
                continue
            period = None
            if i < len(periods):
                try:
                    period = int(periods[i])
                except ValueError:
                    period = None
            bus_map[canid_int] = period
    return bus_whitelist


def check_can_id_whitelist(messages, whitelist):
    """
    检查报文列表中的 CANID 是否都在白名单中。

    Args:
        messages: 报文列表，每个报文字典需包含 "id" 键
        whitelist: 白名单 CANID 整数集合

    Returns:
        (is_valid, non_whitelist_ids)
        is_valid: bool，True 表示全部在白名单中
        non_whitelist_ids: list，非白名单的 CANID 字符串列表（去重排序），无则为空列表
    """
    received_ids = {m["id"] for m in messages}
    non_whitelist = received_ids - whitelist
    if non_whitelist:
        return False, sorted([f"0x{x:03X}" for x in non_whitelist])
    return True, []


def build_can_id_period_map(general_list):
    """
    从 general 配置列表中解析 CANID 与周期的对应关系。
    CANID 和周期按逗号分隔后的顺序一一对应，例如：
        CANID: "0x331,0x313,0x181"
        peroid: "100,100,20"
    返回 {0x331: 100, 0x313: 100, 0x181: 20}

    Args:
        general_list: general sheet 转换后的字典列表

    Returns:
        dict: CANID 整数 -> 周期 ms
    """
    period_map = {}
    for item in general_list:
        canid_str = item.get("CANID")
        period_str = item.get("peroid")
        if not canid_str or not period_str:
            continue
        canids = [c.strip() for c in canid_str.split(",") if c.strip()]
        periods = [p.strip() for p in str(period_str).split(",") if p.strip()]
        for i, canid in enumerate(canids):
            if i >= len(periods):
                break
            try:
                period_map[int(canid, 16)] = int(periods[i])
            except ValueError:
                continue
    return period_map


def check_can_id_periods(messages, period_map, tolerance=0.05, whitelist=None):
    """
    检查报文周期是否符合预期，默认只检查白名单内且配置了周期的 CANID。

    Args:
        messages: 报文列表，每个报文字典需包含 "id" 和 "time" 键（时间单位：秒）
        period_map: CANID 整数 -> 周期 ms 的字典
        tolerance: 允许误差比例，默认 0.05 表示 ±5%
        whitelist: 可选，白名单 CANID 整数集合。传入后只检查白名单内的报文周期

    Returns:
        (is_valid, abnormal_periods)
        is_valid: bool，True 表示所有检查项周期正常
        abnormal_periods: list，异常周期信息字典列表，无则为空列表
            [{"canid": "0x331", "expected_ms": 100, "actual_avg_ms": 105.2,
              "deviation_ms": [102, 98, ...]}, ...]
    """
    from collections import defaultdict

    if whitelist is None:
        whitelist = set(period_map.keys())

    msgs_by_id = defaultdict(list)
    for msg in messages:
        canid = msg.get("id")
        if canid in whitelist and canid in period_map:
            msgs_by_id[canid].append(msg)

    abnormal = []
    skip_count = 3  # 去掉线程启动初期可能不稳定的几个间隔
    for canid, msgs in msgs_by_id.items():
        expected_ms = period_map[canid]
        if len(msgs) < 2 + skip_count:
            continue
        times = sorted(m["time"] for m in msgs)
        intervals = [(times[i] - times[i - 1]) * 1000 for i in range(1, len(times))]
        if not intervals:
            continue
        stable_intervals = intervals[skip_count:]
        if not stable_intervals:
            continue
        # 用众数代表真实周期，CAN 报文周期通常是固定值
        from collections import Counter
        rounded_intervals = [round(x, 1) for x in stable_intervals]
        counter = Counter(rounded_intervals)
        actual_period = counter.most_common(1)[0][0]

        lower = expected_ms * (1 - tolerance)
        upper = expected_ms * (1 + tolerance)
        if actual_period < lower or actual_period > upper:
            abnormal.append({
                "canid": f"0x{canid:03X}",
                "expected_ms": expected_ms,
                "actual_period_ms": actual_period,
                "all_intervals_ms": [round(x, 2) for x in intervals],
            })

    return len(abnormal) == 0, abnormal


def build_ecu_info_map(general_list):
    """
    从 general 配置列表中解析每个 ECU 的信息。

    返回 dict: {resp_canid_int: {"bus_name": str, "ecu_index": int, "req_canid": int or None, "whitelist_canids": set(int)}}
    """
    ecu_info_map = {}
    for item in general_list:
        resp_str = item.get("resp CANID")
        req_str = item.get("req CANID")
        canid_str = item.get("CANID")
        # 必须至少提供 resp CANID
        if not resp_str:
            continue
        try:
            resp_canid = int(resp_str, 16)
        except ValueError:
            continue
        try:
            req_canid = int(req_str, 16) if req_str else None
        except ValueError:
            req_canid = None
        whitelist_canids = set()
        if canid_str:
            for part in str(canid_str).split(","):
                part = part.strip()
                if not part:
                    continue
                try:
                    whitelist_canids.add(int(part, 16))
                except ValueError:
                    continue
        ecu_info_map[resp_canid] = {
            "bus_name": item.get("BUS NAME"),
            "channel": item.get("channel bus"),
            "ecu_index": item.get("ECUindex"),
            "req_canid": req_canid,
            "whitelist_canids": whitelist_canids,
        }
    return ecu_info_map


def check_upgrade_scenario(
    messages,
    whitelist,
    upgrade_response_data=(0x51, 0x01),
    grace_period_s=120,
    allowed_missing_canids=None,
    ecu_info_map=None,
):
    """
    根据升级场景判断报文是否正常。

    规则：
    1. 通过 resp CANID + 51 01 判断哪个 ECU 正在升级
    2. 同一 CAN 总线顺序升级（由 ECUindex 确定），下一个开始则上一个完成
    3. 不同 CAN 总线的控制器并行升级
    4. 升级中 ECU：宽限期内非白名单报文不判断
    5. 不升级 ECU：非白名单报文正常判断
    6. 宽限期结束后，所有 ECU 都正常判断

    Args:
        messages: 报文列表，每个报文字典需包含 "id"、"time" 和 "data" 键
        whitelist: 白名单 CANID 整数集合
        upgrade_response_data: 升级响应数据前缀，默认 (0x51, 0x01)
        grace_period_s: 宽限期秒数，默认 120 秒
        allowed_missing_canids: 允许缺失的白名单 CANID 集合
        ecu_info_map: ECU 信息映射，格式见 build_ecu_info_map

    Returns:
        (is_normal, result)
        is_normal: bool，True 表示无异常
        result: dict
            {
                "upgrading_ecus": list,  # 当前正在升级的 ECU 信息
                "completed_ecus": list,  # 已完成升级的 ECU 信息
                "abnormal_non_whitelist": list,
                "abnormal_missing": list,
            }
    """
    if allowed_missing_canids is None:
        allowed_missing_canids = set()

    # 按时间排序报文
    sorted_messages = sorted(messages, key=lambda m: m["time"])

    # 按 BUS NAME 分组 ECU 信息
    bus_ecus = {}
    if ecu_info_map:
        for resp_canid, info in ecu_info_map.items():
            bus_name = info["bus_name"]
            if bus_name not in bus_ecus:
                bus_ecus[bus_name] = {}
            bus_ecus[bus_name][resp_canid] = info

    # 记录每个 ECU 的升级时间窗口 (resp_canid -> (start_time, end_time))
    upgrading_time_windows = {}

    # 按时间顺序遍历，找出每个 ECU 的升级时间窗口
    if ecu_info_map:
        for msg in sorted_messages:
            canid = msg["id"]
            if canid not in ecu_info_map:
                continue

            data = msg.get("data") or []
            # 检查是否是升级响应报文 (51 01)
            if len(data) >= len(upgrade_response_data):
                match = all(data[i] == upgrade_response_data[i] for i in range(len(upgrade_response_data)))
                if match and canid not in upgrading_time_windows:
                    upgrading_time_windows[canid] = (msg["time"], msg["time"] + grace_period_s)

    # 确定当前正在升级和已完成升级的 ECU
    # 同一总线上：ECUindex 最大的且在宽限期内的是正在升级的，比它小的已完成
    current_time = sorted_messages[-1]["time"] if sorted_messages else 0
    active_upgrading_ecus = []
    completed_ecus = []

    for bus_name, ecus in bus_ecus.items():
        # 按 ECUindex 排序
        sorted_ecus = sorted(ecus.items(), key=lambda x: x[1].get("ecu_index") or 0, reverse=True)

        # 找到正在升级的 ECU（宽限期内且 ECUindex 最大）
        found_upgrading = False
        for resp_canid, info in sorted_ecus:
            if resp_canid in upgrading_time_windows:
                start_time, end_time = upgrading_time_windows[resp_canid]
                if end_time > current_time:
                    if not found_upgrading:
                        # 宽限期内且 ECUindex 最大，是正在升级的
                        active_upgrading_ecus.append({
                            "resp_canid": f"0x{resp_canid:03X}",
                            "bus_name": info["bus_name"],
                            "ecu_index": info["ecu_index"],
                            "whitelist_canids": sorted([f"0x{x:03X}" for x in info["whitelist_canids"]]),
                            "start_time": start_time,
                            "end_time": end_time,
                        })
                        allowed_missing_canids = allowed_missing_canids | info["whitelist_canids"]
                        found_upgrading = True
                    else:
                        # 比正在升级的 ECUindex 小，说明已升级完成
                        completed_ecus.append({
                            "resp_canid": f"0x{resp_canid:03X}",
                            "bus_name": info["bus_name"],
                            "ecu_index": info["ecu_index"],
                            "whitelist_canids": sorted([f"0x{x:03X}" for x in info["whitelist_canids"]]),
                        })

    # 判断非白名单报文是否异常
    # 规则：只有升级中 ECU 的 resp CANID 报文，在宽限期内才不判断；
    #      其他 ECU 的非白名单报文都正常判断。
    abnormal_non_whitelist = []
    for msg in sorted_messages:
        canid = msg["id"]
        if canid in whitelist:
            continue

        # 如果该报文的 CANID 是某个升级中 ECU 的 resp CANID，检查是否在宽限期内
        if canid in upgrading_time_windows:
            start_time, end_time = upgrading_time_windows[canid]
            if start_time <= msg["time"] <= end_time:
                continue  # 升级中 ECU 的 resp 报文，宽限期内不判断

        # 其他情况（不升级 ECU 或宽限期外）正常判断
        abnormal_non_whitelist.append({
            "canid": f"0x{canid:03X}",
            "time": round(msg["time"], 6),
        })

    # 判断白名单报文缺失是否异常（排除正在升级的 ECU 白名单）
    received_ids = {m["id"] for m in sorted_messages}
    missing_ids = whitelist - received_ids - allowed_missing_canids
    abnormal_missing = sorted([f"0x{x:03X}" for x in missing_ids])

    is_normal = len(abnormal_non_whitelist) == 0 and len(abnormal_missing) == 0
    return is_normal, {
        "upgrading_ecus": active_upgrading_ecus,
        "completed_ecus": completed_ecus,
        "abnormal_non_whitelist": abnormal_non_whitelist,
        "abnormal_missing": abnormal_missing,
    }


def check_can_id_neighbor_period(messages, canid, period_ms, target_time, tolerance=0.05):
    """
    检查指定 CANID 在 target_time 附近的上一帧与下一帧时间差是否满足周期 ±5%。

    Args:
        messages: 报文列表，每个报文字典需包含 "id" 和 "time" 键（时间单位：秒）
        canid: 要检查的 CANID 整数
        period_ms: 期望周期，单位 ms
        target_time: 目标时间点，单位秒
        tolerance: 允许误差比例，默认 0.05 表示 ±5%

    Returns:
        (is_ok, actual_diff_ms)
        is_ok: bool，True 表示时间差在周期 ±5% 范围内
        actual_diff_ms: float or None，实际时间差（ms），无法计算时为 None
    """
    msgs = sorted(
        [m for m in messages if m.get("id") == canid],
        key=lambda m: m["time"],
    )
    if len(msgs) < 2:
        print(f"CANID 0x{canid:03X} 帧数不足，无法计算时间差")
        return False, None

    prev_msg = None
    next_msg = None
    for i, m in enumerate(msgs):
        if m["time"] > target_time:
            next_msg = m
            if i > 0:
                prev_msg = msgs[i - 1]
            break

    if prev_msg is None or next_msg is None:
        print(f"CANID 0x{canid:03X} 在目标时间 {target_time:.6f}s 附近未找到上一帧或下一帧")
        return False, None

    prev_time = prev_msg["time"]
    next_time = next_msg["time"]
    actual_diff_ms = (next_time - prev_time) * 1000.0

    lower = period_ms * (1 - tolerance)
    upper = period_ms * (1 + tolerance)

    print(
        f"CANID 0x{canid:03X} 上一帧时间: {prev_time:.6f}s, "
        f"下一帧时间: {next_time:.6f}s, "
        f"时间差: {actual_diff_ms:.3f}ms, "
        f"期望周期: {period_ms}ms (范围 {lower:.3f}ms ~ {upper:.3f}ms)"
    )

    if lower <= actual_diff_ms <= upper:
        return True, None
    return False, actual_diff_ms


def check_high_voltage_signal(msg_getter, high_voltage_canid=0x343, timeout_minutes=1):
    """
    检查是否收到高压报文（带超时检测）。

    Args:
        msg_getter: 可调用对象，每次调用返回当前收到的报文列表
                    例如: lambda: self.can.get_received_messages(clear=True)
        high_voltage_canid: 高压报文 CANID，默认 0x343
        timeout_minutes: 超时时间（分钟），默认 5

    Returns:
        (is_upgrade_started, message)
        is_upgrade_started: bool，True 表示收到了高压报文
        message: str，说明信息
    """
    import time
    from common.logger import log_info, log_error_continue

    start_time = time.time()
    timeout_seconds = timeout_minutes * 60

    while True:
        elapsed = time.time() - start_time
        if elapsed >= timeout_seconds:
            log_info(f"5min内未收到高压信号，已超时 {elapsed:.1f}s")
            return False, "5min内未收到高压信号，未开始升级"

        all_msgs = msg_getter()
        if all_msgs:
            log_info(f"后台线程累计接收到 {len(all_msgs)} 帧报文")

        for msg in all_msgs:
            if msg.get("id") == high_voltage_canid:
                log_info(f"收到高压信号 CANID=0x{high_voltage_canid:03X}，开始升级")
                return True, "开始升级"

        time.sleep(0.1)


def monitor_liquid_cooling_signal(messages, liquid_cooling_canid=0x181, period_ms=100, tolerance=0.05):
    """
    检查报文列表中液冷信号的周期是否满足要求。

    Args:
        messages: 报文列表，每个报文字典需包含 "id" 和 "time" 键
        liquid_cooling_canid: 液冷信号 CANID，默认 0x181
        period_ms: 期望周期，单位 ms
        tolerance: 允许误差比例，默认 0.05 表示 ±5%

    Returns:
        (is_ok, message, prev_time, next_time)
        is_ok: bool，False 表示检测到周期异常
        message: str，说明信息
        prev_time: float or None，上一帧时间（秒）
        next_time: float or None，下一帧时间（秒）
    """
    from common.logger import log_info, log_error_continue

    # 过滤目标 CANID 的报文并按时间排序
    msgs = sorted(
        [m for m in messages if m.get("id") == liquid_cooling_canid],
        key=lambda m: m["time"],
    )

    # 至少需要2帧才能计算时间差
    if len(msgs) < 2:
        return True, "报文不足", None, None

    # 取最后两帧计算时间差
    prev_msg = msgs[-2]
    next_msg = msgs[-1]

    prev_time = prev_msg["time"]
    next_time = next_msg["time"]
    actual_diff_ms = (next_time - prev_time) * 1000.0

    lower = period_ms * (1 - tolerance)
    upper = period_ms * (1 + tolerance)

    log_info(
        f"液冷信号 0x{liquid_cooling_canid:03X} 上一帧时间: {prev_time:.6f}s, "
        f"下一帧时间: {next_time:.6f}s, "
        f"时间差: {actual_diff_ms:.3f}ms, "
        f"期望周期: {period_ms}ms (范围 {lower:.3f}ms ~ {upper:.3f}ms)"
    )

    if not (lower <= actual_diff_ms <= upper):
        return False, "周期异常", prev_time, next_time

    return True, "周期正常", prev_time, next_time


class UpgradeWindowChecker:
    """
    单个 ECU 的 UDS 升级"第5步~第24步"窗口白名单/黑名单检查器。

    收到第5步请求帧 (28 83 03, 功能寻址) 时打开窗口，收到第24步请求帧
    (28 80 03, 功能寻址) 时关闭窗口。窗口内对整条总线报文做检查：
    - 白名单(该 ECU 的 CANID 列, 带周期): 全部须出现, 配了周期的须符合周期
    - 黑名单(不在 {req, resp, 白名单, 0x7DF} 的 CANID): 窗口内不能出现

    判定：
    - FAIL: ①白名单有 CANID 缺失 ②有 CANID 周期不符 ③出现黑名单
    - PASS: 无以上问题
    """

    def __init__(self, ecu_name, whitelist_periods, valid_canids,
                 func_canid=0x7DF, req_canid=None, tolerance=0.05, reaction_time=3.0,
                 channel=None):
        self.ecu_name = ecu_name
        # channel 归一化为 int，防止驱动返回字符串类型导致比较失败
        if channel is not None:
            try:
                channel = int(channel)
            except (TypeError, ValueError):
                channel = None
        self.channel = channel  # 仅处理该通道的帧（None=不过滤, 处理所有通道）
        self.whitelist_periods = whitelist_periods  # {canid: period_ms or None}
        self.valid_canids = valid_canids  # set, 黑名单过滤集合
        self.tolerance = tolerance
        self.reaction_time = reaction_time  # 收到28 83 03后预留ECU反应时间(秒)
        self.boundary_canids = {func_canid}
        if req_canid:
            self.boundary_canids.add(req_canid)
        self.opened = False
        self.closed = False
        self.phase = 0  # 已开启的升级窗口段数（每个ECU阶段各一对 28 83 03/28 80 03）
        self.window_open_time = None  # 收到28 83 03的时间戳
        self.window_close_time = None  # 窗口关闭时间戳（收到第24步或兜底判定时）
        self.last_msg_time = None  # 处理的最后一帧报文时间（用于兜底判定）
        self.seen = set()
        self.times = defaultdict(list)
        self.blacklist = set()
        self.blacklist_first = {}  # {canid: 首次出现时间戳}，用于打印黑名单证据
        self.step_gate = False  # 前4步是否完成（外部设置）
        self.comm_control_seen = False  # 是否已收到 28 83 03
        self._pending_open_time = None  # step_gate 打开前缓存的 28 83 03 时间戳
        self.verdict_logged = False  # 当前段判定是否已打印（每对 28 83 03/28 80 03 打印一次）

    @staticmethod
    def _payload(data):
        """去掉 ISO-TP PCI 头，取 UDS 有效载荷（SF/FF）。"""
        if not data:
            return None
        if (data[0] >> 4) & 0x0F == 0x0:
            return data[1:]
        if (data[0] >> 4) & 0x0F == 0x1:
            return data[2:]
        return None

    def process(self, msgs):
        """处理一轮报文：检测窗口边界，并在窗口内(含反应时间之后)累积白名单/黑名单信息。
        窗口边界直接由 UDS 报文帧检测，时间戳最准确：
        - 开窗帧: 28 83 03（功能寻址，禁止非诊断报文发送），对应第5步
        - 关窗帧: 28 80 03（功能寻址，恢复正常通讯），对应第24步
        """
        for msg in msgs:
            mid = msg.get("id")
            if mid is None or mid < 0:
                continue
            # 按通道过滤：只处理本总线的通道（不同总线同时升级, 避免互相污染）
            # msg 的 channel 也转 int 再比较，防止驱动返回类型不一致
            if self.channel is not None:
                try:
                    msg_ch = int(msg.get("channel"))
                except (TypeError, ValueError):
                    msg_ch = msg.get("channel")
                if msg_ch != self.channel:
                    continue
            data = msg.get("data") or []
            t = msg.get("time")
            if t is None:
                # 无时间戳的帧无法参与窗口判定（开窗/关窗/区间检查都依赖时间），
                # 一旦让 t=None 的边界帧开窗，window_open_time=None 会导致
                # _in_check_window 对所有帧放行，窗口时间整体误判
                continue
            self.last_msg_time = t
            p = self._payload(data)
            # 窗口边界检测：直接通过 UDS 功能寻址帧判定，时间戳精确
            if p and mid in self.boundary_canids and len(p) >= 3:
                if p[:3] == [0x28, 0x83, 0x03] and (not self.opened or self.closed):
                    # 开窗帧：28 83 03（需满足前4步完成 step_gate）
                    self.comm_control_seen = True
                    self._pending_open_time = t
                    if self.step_gate:
                        self._do_open_window(t)
                elif p[:3] == [0x28, 0x80, 0x03] and self.opened and not self.closed:
                    # 关窗帧：28 80 03（恢复通讯，对应第24步，无需依赖外部步骤判断，时间戳精确）
                    self.closed = True
                    self.window_close_time = t
                    # 关窗时刻立即打印本段判定：若同一批报文中紧跟下一个 ECU 的
                    # 开窗帧，本段数据会被 _do_open_window 清空，结果必须先输出
                    self._log_verdict()
            # 窗口内累积（收到28 83 03后预留 reaction_time 秒 ECU 反应时间）
            if self.opened and not self.closed and self._in_check_window(t):
                if mid in self.whitelist_periods:
                    self.seen.add(mid)
                    self.times[mid].append(t)
                elif mid not in self.valid_canids:
                    if mid not in self.blacklist:
                        self.blacklist_first[mid] = t
                        # 打印黑名单证据：日志默认只打印 req/resp/0x7DF 报文，
                        # 黑名单 ID 的帧不会出现在常规报文日志中，需在此单独输出以便核对 BLF
                        log_info(
                            f"[{self.ecu_name}] 窗口内检测到黑名单报文 ID=0x{mid:03X} "
                            f"Time={t:.6f}s Ch={msg.get('channel')}"
                        )
                    self.blacklist.add(mid)

    def _in_check_window(self, t):
        """是否在有效检查区间内（窗口打开后 reaction_time 秒之后）。"""
        if t is None:
            return False
        if self.window_open_time is None:
            return True
        if t < self.window_open_time + self.reaction_time:
            return False
        return True

    def _do_open_window(self, t):
        """打开升级检查窗口（上一段结果已在关窗时刻快照到 phase_results，此处清空安全）。"""
        self.phase += 1
        self.opened = True
        self.closed = False
        self.window_open_time = t
        self.window_close_time = None
        self.last_msg_time = t
        self.seen.clear()
        self.times.clear()
        self.blacklist.clear()
        self.blacklist_first.clear()

    def set_step_gate(self, reached):
        """外部调用：前4步(31→71→85序列)完成时设为 True。
        之前缓存的28 83 03帧时间无效，清空后等待step_gate打开后新收到的28 83 03才开窗。
        """
        self.step_gate = reached
        if reached:
            # 清空step_gate之前的旧28 83 03缓存，避免用错误的旧时间开窗
            self._pending_open_time = None
            self.comm_control_seen = False

    def set_end_step(self, reached, close_time=None):
        """外部调用：步骤23完成时设为 True，关闭窗口。"""
        if reached and self.opened and not self.closed:
            self.closed = True
            self.window_close_time = close_time if close_time is not None else self.last_msg_time
            self._log_verdict()

    def _log_verdict(self):
        """关窗时刻立即打印本段判定结果（每对 28 83 03/28 80 03 打印一次）。

        必须在数据被下一个 ECU 开窗清空之前输出；verdict_logged 标志
        防止 test_demo1.py 循环末尾的判定块重复打印同一段。
        """
        if self.verdict_logged or not self.opened:
            return
        self.verdict_logged = True
        passed, reasons = self.evaluate()
        start_t, end_t = self.get_window_time_range()
        time_range_str = (
            f" [窗口时间: {start_t:.6f}s ~ {end_t:.6f}s]"
            if start_t is not None and end_t is not None else ""
        )
        label = f"[{self.ecu_name}] 升级窗口第{self.phase}段(5~23步){time_range_str}"
        if passed:
            log_info(f"{label}检查 PASS: 白名单均出现且按周期发送, 无黑名单")
        else:
            for r in reasons:
                log_error_continue(f"{label}检查 FAIL: {r}")

    def _snapshot_phase(self, end_time):
        """关窗时刻快照本段(当前ECU)的判定结果到 phase_results。
        必须在 _do_open_window 清空数据之前调用，确保每段结果独立、不丢失。
        """
        passed, reasons = self.evaluate()
        start_t, _ = self.get_window_time_range()
        self.phase_results.append({
            "phase": self.phase,
            "start": start_t,
            "end": end_time,
            "passed": passed,
            "reasons": reasons,
        })

    def finalize(self):
        """收尾兜底：窗口仍打开（未收到关窗帧）时，用最后一帧时间关窗并快照。"""
        if self.opened and not self.closed:
            self.closed = True
            self.window_close_time = self.last_msg_time
            self._snapshot_phase(self.window_close_time)

    def pop_unreported_results(self):
        """取出尚未打印的段结果（每个 ECU 一段），调用后标记为已报告。"""
        results = self.phase_results[self._reported_count:]
        self._reported_count = len(self.phase_results)
        return results

    def get_window_time_range(self):
        """获取窗口实际检查的时间范围(开始检查时间, 结束时间)。
        开始检查时间 = 开窗时间(28 83 03) + reaction_time(默认2s，预留ECU反应时间)。
        结束时间优先使用显式关闭时间，兜底用最后一帧报文时间。
        """
        if self.window_open_time is None:
            return None, None
        check_start = self.window_open_time + self.reaction_time
        end_time = self.window_close_time if self.window_close_time is not None else self.last_msg_time
        return check_start, end_time

    def evaluate(self):
        """
        判定窗口结果。

        Returns:
            (passed, reasons)
            passed: bool，None 表示窗口从未打开（不判定）
            reasons: list[str]，FAIL 原因列表，PASS 时为空
        """
        if not self.opened:
            return None, []
        reasons = []
        missing = set(self.whitelist_periods.keys()) - self.seen
        if missing:
            reasons.append("白名单报文未出现: " + ", ".join(f"0x{x:03X}" for x in sorted(missing)))
        # 周期检查（仅对配了周期且采样>=2 的 CANID）
        for canid, period in self.whitelist_periods.items():
            if period is None:
                continue
            ts = sorted(self.times.get(canid, []))
            if len(ts) < 2:
                continue
            diffs = [(ts[i] - ts[i - 1]) * 1000.0 for i in range(1, len(ts))]
            lower = period * (1 - self.tolerance)
            upper = period * (1 + self.tolerance)
            # 逐对检查相邻两帧间隔是否落在 [period±容差] 内（不取均值）
            bad = [(i, d) for i, d in enumerate(diffs) if d < lower or d > upper]
            if bad:
                i, actual = bad[0]
                reasons.append(
                    f"白名单周期异常 CANID=0x{canid:03X}, 期望={period}ms(±{self.tolerance:.0%}), "
                    f"两帧间隔={actual:.1f}ms (第{i + 1}~{i + 2}帧), "
                    f"时间戳=[{ts[i]:.6f}, {ts[i + 1]:.6f}]"
                )
        if self.blacklist:
            parts = []
            for x in sorted(self.blacklist):
                ft = self.blacklist_first.get(x)
                parts.append(f"0x{x:03X}" + (f"(首次@{ft:.6f}s)" if ft is not None else ""))
            reasons.append("出现黑名单报文: " + ", ".join(parts))
        return (len(reasons) == 0), reasons
