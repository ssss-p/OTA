
from common.logger import log_error_continue, log_info

# UDS 升级步骤定义（30步流程）
# 每个步骤: (step_num, req_pattern, resp_pattern, desc, is_func_addr, optional)
# req_pattern/resp_pattern: None 表示不需要匹配特定报文
# is_func_addr: True 表示功能寻址，False 表示物理寻址
# optional: True 表示可选步骤

UDS_STEPS = [
    # 步骤2: 功能寻址 - 进入扩展会话
    (2,  (0x10, 0x83),         None,         "功能寻址进入扩展会话",       True,  False),
    # 步骤3: 检查编程条件
    (3,  (0x31, 0x01, 0x02, 0x03), (0x71, 0x01, 0x02, 0x03, 0x00), "检查编程条件",   False, False),
    # 步骤4: 控制DTC设置 - 功能寻址
    (4,  (0x85, 0x82),         None,                  "功能寻址控制DTC设置(关闭)",  True,  False),
    # 步骤5: 通讯控制 - 功能寻址
    (5,  (0x28, 0x83, 0x03),   None,                  "功能寻址通讯控制",           True,  False),
    # 步骤6: 请求进入编程会话
    (6,  (0x10, 0x02),         (0x50, 0x02),         "请求进入编程会话",            False, False),
    # 步骤7: 安全访问请求种子
    (7,  (0x27, 0x11),         (0x67, 0x11),         "安全访问请求种子",            False, False),
    # 步骤8: 安全访问发送密钥
    (8,  (0x27, 0x12),         (0x67, 0x12),         "安全访问发送密钥",            False, False),
    # 步骤9: 读取当前运行分区 (可选)
    (9,  (0x22, 0xF0, 0xF0),   (0x62, 0xF0, 0xF0),   "读取当前运行分区",            False, True),
    # 步骤10: 写入指纹
    (10, (0x2E, 0xF1, 0x84),   (0x6E, 0xF1, 0x84),   "写入指纹",                   False, False),
    # 步骤11: 请求下载
    (11, (0x34, 0x00, 0x44),   (0x74, 0x40),         "请求下载",                   False, False),
    # 步骤12: 传输数据 (会在循环中被多次匹配)
    (12, (0x36,),              (0x76,),              "传输数据",                   False, False),
    # 步骤13: 请求退出下载
    (13, (0x37,),              (0x77,),              "请求退出下载",                False, False),
    # 步骤14: 安全签名校验
    (14, (0x31, 0x01, 0xDD, 0x02), (0x71, 0x01, 0xDD, 0x02, 0x00), "安全签名校验(首次)", False, False),
    # 步骤15: 擦除内存
    (15, (0x31, 0x01, 0xFF, 0x00, 0x44), (0x71, 0x01, 0xFF, 0x00, 0x00), "擦除内存",    False, False),
    # 步骤16: 请求下载(第二个segment)
    (16, (0x34, 0x00, 0x44),   (0x74,),               "请求下载(第二个segment)",     False, False),
    # 步骤17: 传输数据(第二个segment)
    (17, (0x36,),              (0x76,),              "传输数据(第二个segment)",     False, False),
    # 步骤18: 请求退出下载(第二个segment)
    (18, (0x37,),              (0x77,),              "请求退出下载(第二个segment)",  False, False),
    # 步骤19: 跳转到步骤16处理更多segment (由步骤18后触发，由步骤20结束)
    # 注意：步骤19是逻辑跳转，不是一个独立步骤
    # 步骤20: 安全签名校验(第二次)(不check)
    (20, (0x31, 0x01, 0xDD, 0x02), (0x71, 0x01, 0xDD, 0x02, 0x00), "安全签名校验(第二次)", False, False),
    # 步骤22: 阻止自动切换分区(可选)
    (22, (0x31, 0x01, 0xDD, 0x0F), (0x71, 0x01, 0xDD, 0x0F, 0x00), "阻止自动切换分区",    False, True),
    # 步骤23: 检查编程依赖性
    (23, (0x31, 0x01, 0xFF, 0x01), (0x71, 0x01, 0xFF, 0x01, 0x00), "检查编程依赖性",    False, False),
    # 步骤24: 通讯控制复位 - 功能寻址
    (24, (0x28, 0x80, 0x03),   None,                  "功能寻址通讯控制(复位)",      True,  False),
    # 步骤25: 复位
    (25, (0x11, 0x01),         (0x51, 0x01),         "ECU复位(升级成功标志)",        False, False),
    # 步骤26: 功能寻址进入扩展会话(无响应)
    (26, (0x10, 0x83),         None,                  "功能寻址进入扩展会话(无响应)", True,  False),
    # 步骤29: 控制DTC设置 - 功能寻址
    (29, (0x85, 0x82),         None,                  "功能寻址控制DTC设置(开启)",   True,  False),

]

# 升级完成结束标志：DID 响应（22 的 positive response 为 62）
COMPLETION_DIDS = [
    (0x62, 0xF0, 0x89),  # 读取 ECU 升级状态/标识
    (0x62, 0xF1, 0x89),  # 读取应用软件标识
    (0x62, 0xF1, 0x80),  # 读取其他标识
]

# 步骤号 -> 该步骤请求的服务 ID（req_pattern[0]）
# 用于 NRC 归属判定：UDS 负响应 7F <sid> <nrc> 中的 sid 永远等于被拒绝请求的服务 ID，
# 因此只有 sid 与当前步骤请求服务 ID 一致的负响应才算该步骤的负响应；
# 其余（如 ECU 周期性发来的 7F 22 31 状态帧）与本升级步骤无关，忽略。
STEP_REQ_SID = {s[0]: s[1][0] for s in UDS_STEPS if s[1]}

# 升级成功标志：51 01
UPGRADE_SUCCESS_PATTERN = (0x51, 0x01)


def _extract_uds_payload(data):
    """
    从 CAN 帧数据中提取 UDS 有效载荷（去掉 ISO-TP / 自定义帧头）。

    - 单帧 (SF): 0x0N (N>=1)，PCI 1 字节，数据从索引 1 开始
    - 自定义长帧: 0x00 0xXX ...，PCI 2 字节，数据从索引 2 开始
      （该 CANFD 设备对 >7 字节的 UDS 报文用 0x00 开头的自定义头封装，
       而非标准 ISO-TP 多帧拆分，如 00 12 67 11 E2 ... 实际载荷为 67 11 E2 ...）
    - 首帧 (FF): 0x1X YY，PCI 2 字节，数据从索引 2 开始
    - 连续帧/流控帧: 通常不携带完整服务数据，返回原数据（由调用方判断是否匹配）
    """
    if not data:
        return data
    # 自定义长帧头 0x00 <XX>：CANFD 设备用 0x00 开头封装长 UDS 报文，需跳过前 2 字节。
    # 标准 ISO-TP 中 SF 长度不为 0，故 0x00 首字节在此环境中必为自定义长帧头。
    if data[0] == 0x00 and len(data) >= 3:
        return data[2:]
    pci_type = (data[0] >> 4) & 0x0F
    if pci_type == 0x00:
        # 单帧(SF)：0x0N (N>=1)，长度字节占 1 字节。
        # 注意：此函数必须保持"幂等"——已剥离的 payload 首字节是 UDS 服务字节
        # （如 0x10/0x50/0x74，高半字节常为 1），绝不能再加 FF 分支跳过 2 字节，
        # 否则对已剥离 payload 二次调用时 10 83 会被剥成 83 导致所有步骤匹配失败。
        return data[1:]
    return data


def _match_pattern(data, pattern):
    """检查报文的 data 是否匹配给定的模式（支持 ISO-TP 帧，前缀匹配）。"""
    if data is None or pattern is None:
        return pattern is None
    payload = _extract_uds_payload(data)
    if len(payload) < len(pattern):
        return False
    _res = all(payload[i] == pattern[i] for i in range(len(pattern)))
    return _res


def _find_msg_by_pattern(messages, canid, pattern, is_func_addr=None):
    """
    从报文中查找匹配指定 CANID 和数据模式的报文。

    Args:
        messages: 报文列表
        canid: CANID (物理寻址或功能寻址)
        pattern: 数据模式元组
        is_func_addr: True 只查功能寻址(0x7FF), False 只查物理寻址(非0x7FF), None 两者都查

    Returns:
        第一个匹配的报文字典，未找到返回 None
    """
    for msg in messages:
        if msg.get("id") != canid:
            continue
        if is_func_addr is True and canid != 0x7FF:
            continue
        if is_func_addr is False and canid == 0x7FF:
            continue
        data = msg.get("data") or []
        if _match_pattern(data, pattern):
            return msg
    return None


def _find_resp_for_req(messages, req_canid, resp_canid, func_canid, req_pattern, resp_pattern, start_time=None):
    """
    在报文中查找 req 对应的 resp。

    Args:
        messages: 报文列表（已按时间排序）
        req_canid: 请求 CANID
        resp_canid: 响应 CANID
        func_canid: 功能寻址 CANID
        req_pattern: 请求数据模式
        resp_pattern: 响应数据模式（None 表示不需要响应）
        start_time: 只查找 start_time 之后的报文

    Returns:
        响应报文，未找到返回 None
    """
    req_found = False
    for msg in messages:
        if start_time is not None and msg.get("time", 0) < start_time:
            continue
        msg_id = msg.get("id")
        data = msg.get("data") or []

        # 检查是否是请求报文（物理寻址或功能寻址）
        is_req = False
        if msg_id == req_canid and _match_pattern(data, req_pattern):
            is_req = True
        elif func_canid and msg_id == func_canid and _match_pattern(data, req_pattern):
            is_req = True

        if is_req:
            req_found = True
            continue

        # 如果已经收到请求，查找响应
        if req_found and msg_id == resp_canid:
            if resp_pattern is None:
                # 不需要特定响应，任何 resp_canid 的报文都算
                return msg
            if _match_pattern(data, resp_pattern):
                return msg

    return None


class UDSUpgradeMonitor:
    """UDS 升级流程监控状态机（单个 ECU）"""

    def __init__(self, req_canid=0x700, resp_canid=0x600, func_canid=0x7DF, name="ECU", channel=None):
        self.req_canid = req_canid
        self.resp_canid = resp_canid
        self.func_canid = func_canid
        self.name = name
        # channel 过滤：只处理该通道的报文（对应 OTA.xlsx 的 channel bus 列）。
        # 功能寻址 0x7DF 会出现在多个通道的日志中，必须按 channel 区分，
        # 否则 Ch0 的 10 83 会让所有 ECU 同时推进。None 表示不过滤。
        # 归一化为 int，防止 xlsx 读出字符串 "0" 与驱动整数 0 比较失败。
        if channel is not None:
            try:
                channel = int(channel)
            except (TypeError, ValueError):
                log_error_continue(f"[{name}] channel 配置无法解析为 int: {channel!r}，该 ECU 不按 channel 过滤")
                channel = None
        self.channel = channel
        # 状态跟踪
        self.step_status = {}  # {step_num: "pending"|"ok"|"error"|"skipped"}
        self.current_step = 0
        self.current_desc = "等待开始"
        self.is_upgrade_success = False
        self.is_upgrade_complete = False
        self.found_completion_marker = False
        self.upgrade_start_time = None
        self.upgrade_end_time = None
        self.step_results = []  # [(step_num, status, msg_time), ...]
        self.last_msg_time = None
        # 传输数据的块计数
        self.data_block_count = 0
        # 多 segment 处理
        self.segment_count = 0  # 0=首次下载, 1+=后续segment
        # 步骤17的响应匹配计数
        self.step17_resp_count = 0
        # 当前在哪个步骤的传输循环中
        self.in_data_transfer_loop = False
        self.loop_end_step = 0  # 循环结束后应该到达的步骤
        # 已记录的错误响应，避免重复打印
        self._logged_errors = set()

    def _apply_step(self, step_num, status, msg_time=None):
        """更新步骤状态"""
        self.step_status[step_num] = status
        self.step_results.append((step_num, status, msg_time))
        if status == "ok":
            self.current_step = step_num
            self.current_desc = self._get_step_desc(step_num)

    def _get_step_desc(self, step_num):
        for s in UDS_STEPS:
            if s[0] == step_num:
                return s[3]
        return "未知步骤"

    def _is_func_addr_step(self, step_num):
        for s in UDS_STEPS:
            if s[0] == step_num:
                return s[4]
        return False

    def _is_optional_step(self, step_num):
        for s in UDS_STEPS:
            if s[0] == step_num:
                return s[5]
        return False

    def process_messages(self, messages):
        """
        处理一批评文，返回当前状态。

        返回:
            (changed: bool, step_num: int, desc: str)
        """
        changed = False

        for msg in messages:
            # channel 过滤：只处理本 ECU 对应通道的报文。
            # self.channel 构造时已归一化为 int；这里把 msg 的 channel 也转 int 再比，
            # 防止驱动返回类型不一致（如字符串）导致误过滤、状态机卡死。
            if self.channel is not None:
                try:
                    msg_ch = int(msg.get("channel"))
                except (TypeError, ValueError):
                    msg_ch = msg.get("channel")
                if msg_ch != self.channel:
                    continue
            self.last_msg_time = msg.get("time")

            msg_id = msg.get("id")
            data = msg.get("data") or []
            payload = _extract_uds_payload(data)

            # 检查是否收到升级成功标志 51 01（ECUReset 肯定响应，步骤25）。
            # 必须限定 step>=25：刷写工具会在步骤25之前就发 02 51 01 帧，
            # 不限定步骤会导致步骤17等中途就误报"升级成功=True"。
            # 注意：必须传原始 data，_match_pattern 内部会自行剥离帧头。
            if self.current_step >= 25 and msg_id == self.resp_canid and _match_pattern(data, UPGRADE_SUCCESS_PATTERN):
                if not self.is_upgrade_success:
                    self.is_upgrade_success = True
                    changed = True
                    if self.upgrade_start_time is None:
                        self.upgrade_start_time = msg.get("time")

            # 检查是否收到升级完成结束标志（注意：必须用原始 data，_match_pattern 内部会自行剥离帧头）
            for did in COMPLETION_DIDS:
                if _match_pattern(data, did):
                    self.found_completion_marker = True
                    changed = True

            # # 步骤30完成后标记升级完成
            # if self.step_status.get(30) == "ok":
            #     self.is_upgrade_complete = True
            #     self.upgrade_end_time = msg.get("time")
            #     changed = True

            # 如果已经完成30步，不再处理其他报文
            if self.is_upgrade_complete:
                continue

            # 根据当前状态处理报文
            changed = self._process_step_message(msg, msg_id, data) or changed

        return changed

    def _process_step_message(self, msg, msg_id, data):
        """根据当前步骤处理报文，返回是否有状态变化"""
        changed = False
        step = self.current_step
        payload = _extract_uds_payload(data)

        # 检测 UDS 负响应（7F <sid> <error_code>），打印错误但不停止脚本
        # 只关注该 ECU 的合法 CANID（req/resp/功能寻址），其他 CANID 的负响应忽略
        valid_canids = {self.req_canid, self.resp_canid, self.func_canid}
        if payload and len(payload) >= 3 and payload[0] == 0x7F and msg_id in valid_canids:
            sid = payload[1]
            error_code = payload[2]
            # NRC 0x78 (responsePending/响应挂起) 属于正常 UDS 流控，
            # 表示 ECU 尚未处理完，稍后会跟一个肯定响应，不计为错误，
            # 直接跳过，让状态机继续等待后续肯定响应。
            if error_code == 0x78:
                # 步骤6(进入编程会话 10 02)：NRC 78 响应挂起也算通过，
                # 不一定需要等待肯定响应 50 02
                if step == 6 and sid == 0x10 and msg_id == self.resp_canid:
                    self._apply_step(6, "ok", msg.get("time"))
                    # 步骤7、8、9不做check，直接补齐，等待写入指纹响应(6E F1 84)
                    self._apply_step(7, "ok", msg.get("time"))
                    self._apply_step(8, "ok", msg.get("time"))
                    self._apply_step(9, "ok", msg.get("time"))
                    self.current_step = 10
                    self.current_desc = self._get_step_desc(10)
                    return True
                # 步骤15(擦除内存 31 01 FF 00 44)：NRC 78 响应挂起也算通过，
                # 不一定需要等待肯定响应 71 01 FF 00 00。
                # 必须同步设置 segment_count/data_block_count/in_data_transfer_loop，
                # 否则后续 step16→17 不会进入传输循环，36/76/37 帧全部被忽略，
                # 状态机永远卡在步骤17。
                if step == 15 and sid == 0x31 and msg_id == self.resp_canid:
                    self._apply_step(15, "ok", msg.get("time"))
                    self.segment_count += 1
                    self.data_block_count = 0
                    self.in_data_transfer_loop = True
                    self.loop_end_step = 20
                    self.current_step = 16
                    self.current_desc = self._get_step_desc(16)
                    return True
                return changed
            # NRC 归属：UDS 负响应 7F <sid> <nrc> 中的 sid 永远等于被拒绝请求的服务 ID。
            # 只有 sid 与当前步骤请求服务 ID 一致才算本步骤的负响应；
            # 否则是别的服务的响应（如 ECU 周期性发来的 7F 22 31 状态帧），与本升级步骤无关，忽略。
            expected_sid = STEP_REQ_SID.get(step)
            if expected_sid is None or sid != expected_sid:
                return changed
            error_key = (msg_id, sid, error_code, step)
            if error_key not in self._logged_errors:
                self._logged_errors.add(error_key)
                data_str = " ".join(f"{b:02X}" for b in data)
                log_error_continue(
                    f"[{self.name}] 步骤{step}({self.current_desc}) 收到负响应: "
                    f"7F {sid:02X} {error_code:02X} (服务=0x{sid:02X}, 错误码=0x{error_code:02X}), "
                    f"canid=0x{msg_id:03X}, data={data_str}"
                )
                # 记录当前步骤为 error，但继续运行
                if step > 0 and self.step_status.get(step) not in ("ok", "skipped"):
                    self._apply_step(step, "error", msg.get("time"))
                changed = True

        if self.in_data_transfer_loop:
            # 处理数据传输循环
            changed = self._process_data_transfer_loop(msg, msg_id, data) or changed
            return changed

        # 步骤0: 等待升级开始
        # 真实升级流程以默认会话响应 50 01 开头，随后才是检查编程条件 71 01 02 03。
        # ECU 已取消 10 03 和 50 03 的流程，仅保留 50 01 响应作为起始信号。
        if step == 0:
            # 起始判定：收到步骤1肯定响应 50 01，或直接收到功能寻址 10 83（0x7DF）
            # 两种情况都视为升级流程已开始，步骤1、2补齐，进入步骤3
            is_step1_resp = (msg_id == self.resp_canid and _match_pattern(data, (0x50, 0x01)))
            is_ext_session_req = (msg_id == self.func_canid and _match_pattern(data, (0x10, 0x83)))
            if is_step1_resp or is_ext_session_req:
                self.upgrade_start_time = msg.get("time")
                self._apply_step(1, "ok", msg.get("time"))
                self._apply_step(2, "ok", msg.get("time"))
                self.current_step = 3
                self.current_desc = self._get_step_desc(3)
                changed = True
            return changed

        # 逐步骤检查
        if step == 2:
            # 功能寻址进入扩展会话：check 0x7DF 上的 10 83 请求帧（无响应，传原始 data 避免二次剥离）
            if msg_id == self.func_canid and _match_pattern(data, (0x10, 0x83)):
                self._apply_step(2, "ok", msg.get("time"))
                self.current_step = 3
                self.current_desc = self._get_step_desc(3)
                changed = True

        elif step == 3:
            # 检查编程条件请求 31 01 02 03
            if msg_id == self.resp_canid and _match_pattern(data, (0x71, 0x01, 0x02, 0x03, 0x00)):
                self._apply_step(3, "ok", msg.get("time"))
                self.current_step = 4
                self.current_desc = self._get_step_desc(4)
                changed = True

        elif step == 4:
            # DTC设置控制 85 82 功能寻址 - 收到请求即认为完成
            if (msg_id == self.func_canid) and _match_pattern(data, (0x85, 0x82)):
                self._apply_step(4, "ok", msg.get("time"))
                self.current_step = 5
                self.current_desc = self._get_step_desc(5)
                changed = True

        elif step == 5:
            # 通讯控制 28 83 03 功能寻址
            if (msg_id == self.func_canid) and _match_pattern(data, (0x28, 0x83, 0x03)):
                self._apply_step(5, "ok", msg.get("time"))
                self.current_step = 6
                self.current_desc = self._get_step_desc(6)
                changed = True

        elif step == 6:
            # 请求进入编程会话 10 02 -> 50 02
            if msg_id == self.resp_canid and _match_pattern(data, (0x50, 0x02)):
                self._apply_step(6, "ok", msg.get("time"))
                # 步骤7/8（安全访问种子/密钥）不做 check，直接补齐
                self._apply_step(7, "ok", msg.get("time"))
                self._apply_step(8, "ok", msg.get("time"))
                # 步骤9（读取当前运行分区）不做 check，直接补齐
                self._apply_step(9, "ok", msg.get("time"))
                self.current_step = 10
                self.current_desc = self._get_step_desc(10)
                changed = True

        elif step == 10:
            # 写入指纹 2E F1 84 -> 6E F1 84
            if msg_id == self.resp_canid and _match_pattern(data, (0x6E, 0xF1, 0x84)):
                self._apply_step(10, "ok", msg.get("time"))
                self.current_step = 11
                self.current_desc = self._get_step_desc(11)
                changed = True

        elif step == 11:
            # 请求下载 34 00 44 -> 74 XX（dataFormatIdentifier 各 ECU 不同，如 0x20/0x40，只匹配 74 服务字节）
            if msg_id == self.resp_canid and _match_pattern(data, (0x74,)):
                self._apply_step(11, "ok", msg.get("time"))
                self.data_block_count = 0
                self.segment_count = 0
                # 进入数据传输循环
                self.in_data_transfer_loop = True
                self.loop_end_step = 14
                self.current_step = 12
                self.current_desc = self._get_step_desc(12)
                changed = True

        elif step == 13:
            # 请求退出下载 37 -> 77
            if msg_id == self.resp_canid and _match_pattern(data, (0x77,)):
                self._apply_step(13, "ok", msg.get("time"))
                # 步骤14（安全签名校验）不做 check，直接补齐
                self._apply_step(14, "ok", msg.get("time"))
                self.current_step = 15
                self.current_desc = self._get_step_desc(15)
                changed = True

        elif step == 15:
            # 擦除内存 31 01 FF 00 44 -> 71 01 FF 00 00
            if msg_id == self.resp_canid and len(payload) >= 5 and payload[0] == 0x71 and payload[1] == 0x01 and payload[2] == 0xFF and payload[3] == 0x00:
                self._apply_step(15, "ok", msg.get("time"))
                self.segment_count += 1
                self.data_block_count = 0
                # 进入第二个 segment 的数据传输循环
                self.in_data_transfer_loop = True
                self.loop_end_step = 20
                self.current_step = 16
                self.current_desc = self._get_step_desc(16)
                changed = True

        elif step == 16:
            # 第二个 segment 的请求下载响应
            if msg_id == self.resp_canid and _match_pattern(data, (0x74,)):
                self._apply_step(16, "ok", msg.get("time"))
                # 必须进入传输循环：step17 只在 _process_data_transfer_loop 中处理，
                # 主状态机没有 step17 分支。若此处不设 in_data_transfer_loop=True，
                # 36/76/37 帧全部被忽略，状态机永远卡在步骤17。
                self.in_data_transfer_loop = True
                self.data_block_count = 0
                self.current_step = 17
                self.current_desc = self._get_step_desc(17)
                changed = True

        elif step == 18:
            # 第二个 segment 请求退出下载响应
            if msg_id == self.resp_canid and _match_pattern(data, (0x77,)):
                self._apply_step(18, "ok", msg.get("time"))
                # 步骤20（安全签名校验第二次）不做 check，直接补齐
                self._apply_step(20, "ok", msg.get("time"))
                self.current_step = 22
                self.current_desc = self._get_step_desc(22)
                changed = True

        elif step == 22:
            # 步骤22可选（阻止自动切换分区）
            # 检查是否跳过了步骤22（直接到步骤23）
            # 注意：71 01 FF 01 是 step 23 的响应，在 step 22 被跳过时它就是下一帧，
            # 所以这里消费它意味着同时完成了 step 22(skipped) 和 step 23(ok)，应直接跳到 step 24。
            if msg_id == self.resp_canid and len(payload) >= 5 and payload[0] == 0x71 and payload[1] == 0x01 and payload[2] == 0xFF and payload[3] == 0x01:
                self._apply_step(22, "skipped")
                self._apply_step(23, "ok", msg.get("time"))
                self.current_step = 24
                self.current_desc = self._get_step_desc(24)
                changed = True
            elif msg_id == self.resp_canid and len(payload) >= 5 and payload[0] == 0x71 and payload[1] == 0x01 and payload[2] == 0xDD and payload[3] == 0x0F:
                self._apply_step(22, "ok", msg.get("time"))
                self.current_step = 23
                self.current_desc = self._get_step_desc(23)
                changed = True

        elif step == 23:
            # 检查编程依赖性 31 01 FF 01 -> 71 01 FF 01 00
            # 正常走到这里说明 step 22 有正常响应(71 01 DD 0F)，step 23 还没被消费
            if msg_id == self.resp_canid and len(payload) >= 5 and payload[0] == 0x71 and payload[1] == 0x01 and payload[2] == 0xFF and payload[3] == 0x01:
                self._apply_step(23, "ok", msg.get("time"))
                self.current_step = 24
                self.current_desc = self._get_step_desc(24)
                changed = True

        elif step == 24:
            # 通讯控制 28 80 03 功能寻址
            if (msg_id == self.func_canid) and _match_pattern(data, (0x28, 0x80, 0x03)):
                self._apply_step(24, "ok", msg.get("time"))
                self.current_step = 25
                self.current_desc = self._get_step_desc(25)
                changed = True

        elif step == 25:
            # 复位 11 01 -> 51 01
            if msg_id == self.resp_canid and _match_pattern(data, (0x51, 0x01)):
                self._apply_step(25, "ok", msg.get("time"))
                self.is_upgrade_success = True
                # 步骤26（功能寻址 10 83）无响应，不做 check，直接补齐
                self._apply_step(26, "ok", msg.get("time"))
                self.current_step = 29
                self.current_desc = self._get_step_desc(29)
                changed = True

        elif step == 29:
            # DTC设置控制 85 82 功能寻址（步骤29 开启，与步骤4 报文相同，靠顺序区分）
            if (msg_id == self.func_canid) and _match_pattern(data, (0x85, 0x82)):
                self._apply_step(29, "ok", msg.get("time"))
                # 步骤30不单独check：step 29 完成后直接视为升级完成
                self.current_step = 30
                self.current_desc = "升级完成"
                self.is_upgrade_complete = True
                self.upgrade_end_time = msg.get("time")
                changed = True

        # elif step == 30:
        #     # 功能寻址进入默认会话 10 01 -> 50 01
        #     if msg_id == self.resp_canid and _match_pattern(data, (0x50, 0x01)):
        #         self._apply_step(30, "ok", msg.get("time"))
        #         self.is_upgrade_complete = True
        #         self.upgrade_end_time = msg.get("time")
        #         changed = True

        return changed

    def _process_data_transfer_loop(self, msg, msg_id, data):
        """处理数据传输循环（步骤12/17的36->76循环）"""
        changed = False
        payload = _extract_uds_payload(data)

        # 第二个 segment 的请求下载响应 74（step15 之后已进入本循环，在此消费）
        if msg_id == self.resp_canid and self.current_step == 16 and _match_pattern(data, (0x74,)):
            self._apply_step(16, "ok", msg.get("time"))
            # 直接推进到传输数据步骤，不依赖后续 36 请求帧的匹配
            self.current_step = 17
            self.current_desc = self._get_step_desc(17)
            changed = True

        # 检查是否是传输数据请求 36 XX
        # 注意：刷写工具可能使用自定义帧格式发送 36（如 10 00 00 00 10 02 36 XX），
        # 此时 36 不在 payload[0] 位置，无法匹配。因此块计数主要依赖 76 响应，
        # 36 仅在标准格式时更新描述（不计数，避免与 76 重复计数）。
        if msg_id == self.req_canid and len(payload) >= 1 and payload[0] == 0x36:
            if self.segment_count == 0:
                self.current_step = 12
                self.current_desc = f"传输数据(第{self.data_block_count + 1}块)"
            else:
                self.current_step = 17
                self.current_desc = f"传输数据(segment{self.segment_count}第{self.data_block_count + 1}块)"
            changed = True

        # 检查是否是传输数据响应 76 XX
        # 76 是裸 SF 帧（02 76 XX），能正确匹配。
        # 以此作为块计数的权威来源：36 可能使用自定义帧格式无法匹配，
        # 但 76 响应始终是标准格式。
        elif msg_id == self.resp_canid and len(payload) >= 1 and payload[0] == 0x76:
            self.data_block_count += 1
            if self.segment_count == 0:
                self.current_step = 12
                self.current_desc = f"传输数据(第{self.data_block_count}块)"
                self._apply_step(12, "ok", msg.get("time"))
            else:
                self.current_step = 17
                self.current_desc = f"传输数据(segment{self.segment_count}第{self.data_block_count}块)"
                self._apply_step(17, "ok", msg.get("time"))
            changed = True

        # 检查是否是请求退出下载 37（req CANID 上的请求帧）
        # 兜底按原始字节匹配：设备自定义短帧封装(如 00 37)payload 解析不出 37，
        # 但短帧(data[0] 高半字节为0)的第 2 字节就是服务字节，CF 数据帧(data[0] 高半字节为2)已排除
        elif (msg_id == self.req_canid and (_match_pattern(data, (0x37,))
              or (len(data) >= 2 and (data[0] & 0xF0) == 0x0 and data[1] == 0x37))):
            if self.segment_count == 0:
                self._apply_step(12, "ok", msg.get("time"))
                self.current_step = 13
                self.current_desc = self._get_step_desc(13)
            else:
                self._apply_step(17, "ok", msg.get("time"))
                self.current_step = 18
                self.current_desc = self._get_step_desc(18)
            self.in_data_transfer_loop = False
            self.data_block_count = 0
            changed = True

        # 兜底：37 请求帧封装解析失败时，用 77 响应（resp CANID）结束循环
        # 若 77 先到，说明 37 必然已发出，对应步骤直接标 ok 跳到下一步，避免卡死
        # 同样支持原始字节匹配自定义短帧封装(如 00 77)
        elif (msg_id == self.resp_canid and (_match_pattern(data, (0x77,))
              or (len(data) >= 2 and (data[0] & 0xF0) == 0x0 and data[1] == 0x77))):
            if self.segment_count == 0:
                self._apply_step(12, "ok", msg.get("time"))
                self._apply_step(13, "ok", msg.get("time"))
                # 步骤14（安全签名校验）不做 check，直接补齐
                self._apply_step(14, "ok", msg.get("time"))
                self.current_step = 15
                self.current_desc = self._get_step_desc(15)
            else:
                self._apply_step(17, "ok", msg.get("time"))
                self._apply_step(18, "ok", msg.get("time"))
                # 步骤20（安全签名校验第二次）不做 check，直接补齐
                self._apply_step(20, "ok", msg.get("time"))
                self.current_step = 22
                self.current_desc = self._get_step_desc(22)
            self.in_data_transfer_loop = False
            self.data_block_count = 0
            changed = True
            log_info(f"[{self.name}] 传输循环由 77 响应兜底结束, segment={self.segment_count}, 进入步骤{self.current_step}")

        # 调试：循环中收到疑似 36/37/77 的帧但 CANID 或解析不符，打日志便于定位
        elif (len(payload) >= 1 and payload[0] in (0x36, 0x37, 0x77)) or \
             (len(data) >= 2 and (data[0] & 0xF0) == 0x0 and data[1] in (0x37, 0x77)):
            data_str = " ".join(f"{b:02X}" for b in data)
            log_info(
                f"[{self.name}] 传输循环内收到疑似 36/37/77 帧但未匹配: "
                f"canid=0x{msg_id:03X}, req=0x{self.req_canid:03X}, resp=0x{self.resp_canid:03X}, data={data_str}"
            )

        return changed

    def get_step_details(self):
        """获取所有步骤的详细信息"""
        details = []
        for s in UDS_STEPS:
            step_num = s[0]
            desc = s[3]
            status = self.step_status.get(step_num, "pending")
            optional = s[5]
            details.append({
                "step": step_num,
                "desc": desc,
                "status": status,
                "optional": optional,
            })
        return details

    def get_elapsed_time(self):
        """获取升级耗时（秒）"""
        if self.upgrade_start_time is None:
            return 0.0
        end = self.upgrade_end_time if self.upgrade_end_time else (self.last_msg_time or self.upgrade_start_time)
        return end - self.upgrade_start_time

    def get_progress_summary(self):
        """获取升级进度摘要"""
        total = len([s for s in UDS_STEPS if not s[5]])  # 非可选步骤数
        completed = len([s for s in UDS_STEPS if self.step_status.get(s[0]) == "ok" and not s[5]])
        return {
            "total_required_steps": total,
            "completed_required_steps": completed,
            "progress_pct": (completed / total * 100) if total > 0 else 0,
        }


def monitor_upgrade_process(messages, req_canid=0x700, resp_canid=0x600, func_canid=0x7FF):
    """
    监控单个 ECU 的 UDS 升级流程（30步）。

    Args:
        messages: 报文列表，每个报文字典需包含 "id"、"time"、"data" 键
        req_canid: 诊断仪请求 CANID（物理寻址）
        resp_canid: ECU 响应 CANID
        func_canid: 功能寻址 CANID（默认 0x7FF）

    Returns:
        (is_success: bool, result: dict)
        result 包含:
            - is_upgrade_success: bool, 是否收到 51 01
            - is_upgrade_complete: bool, 是否完成30步
            - current_step: int, 当前步骤号
            - current_desc: str, 当前步骤描述
            - step_results: list, 步骤结果列表
            - step_details: list, 步骤详细信息
            - upgrade_time_s: float, 升级耗时
            - found_completion_marker: bool, 是否找到结束标志
            - failed_step: int, 失败的步骤号（如果有）
            - error_message: str, 错误信息
    """
    monitor = UDSUpgradeMonitor(req_canid, resp_canid, func_canid)
    monitor.process_messages(messages)

    result = {
        "is_upgrade_success": monitor.is_upgrade_success,
        "is_upgrade_complete": monitor.is_upgrade_complete,
        "current_step": monitor.current_step,
        "current_desc": monitor.current_desc,
        "step_results": monitor.step_results,
        "step_details": monitor.get_step_details(),
        "upgrade_time_s": monitor.get_elapsed_time(),
        "found_completion_marker": monitor.found_completion_marker,
        "51_01_received": monitor.is_upgrade_success,
        "failed_step": 0,
        "error_message": "",
    }

    # 找出第一个未完成的必需步骤
    for detail in result["step_details"]:
        if detail["status"] == "pending" and not detail["optional"]:
            result["failed_step"] = detail["step"]
            result["error_message"] = f"步骤{detail['step']} {detail['desc']} 未完成"
            break

    is_success = monitor.is_upgrade_success or monitor.is_upgrade_complete
    return is_success, result


def monitor_upgrade_progress(messages, resp_canid=0x600, func_canid=0x7FF, max_time_s=None):
    """
    简化版 ECU 升级进度监控（仅基于响应 CANID 判断）。

    Args:
        messages: 报文列表
        resp_canid: ECU 响应 CANID
        func_canid: 功能寻址 CANID
        max_time_s: 最大超时时间（秒），超出后判定为超时

    Returns:
        dict: 包含 current_step、is_upgrade_success、step_details 等
    """
    # 检查是否收到 51 01（升级成功）
    is_success = False
    success_time = None
    start_time = None
    if messages:
        start_time = messages[0].get("time")
        for msg in messages:
            if msg.get("id") == resp_canid:
                data = msg.get("data") or []
                if _match_pattern(data, UPGRADE_SUCCESS_PATTERN):
                    is_success = True
                    success_time = msg.get("time")

    # 基于成功标志判断完成状态
    is_complete = False
    if is_success:
        is_complete = True

    elapsed = (success_time - start_time) if (success_time and start_time) else 0.0

    return {
        "current_step": 25 if is_success else 0,
        "current_desc": "复位(升级成功标志)" if is_success else "等待开始",
        "is_upgrade_success": is_success,
        "is_upgrade_complete": is_complete,
        "step_details": [],
        "elapsed_time_s": elapsed,
        "51_01_received": is_success,
    }


def extract_uds_payload(data):
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


def build_upgrade_context(general_list, stage_name="升级流程"):
    """
    构建升级监控上下文：CANID 白名单（按总线，id 与周期一一对应）、
    ECU 信息映射、CANID 周期映射、每路总线最后一个 ECU。

    Args:
        general_list: general sheet 转换后的字典列表
        stage_name: 阶段名称（用于日志展示）

    Returns:
        dict: {
            "can_id_whitelist": {bus_name: {canid_int: period_ms or None}},
            "ecu_info_map": {resp_canid: {...}},
            "can_id_period_map": {canid_int: period_ms},
            "bus_last_ecu": {bus_name: {"resp_canid", "ecu_index", "ecu_name"}},
        }
    """
    # CANID 白名单（按总线聚合，同一总线的 id 以及周期存在对应关系）
    can_id_whitelist = build_bus_whitelist(general_list)
    total_id_count = sum(len(v) for v in can_id_whitelist.values())
    log_info(f"[{stage_name}] CANID 白名单(按总线) 总线数: {len(can_id_whitelist)}, id总数: {total_id_count}")
    for bus_name, id_period_map in can_id_whitelist.items():
        detail = ", ".join(
            f"0x{k:03X}={('周期' + str(v) + 'ms') if v is not None else '无周期'}"
            for k, v in sorted(id_period_map.items())
        )
        log_info(f"[白名单] 总线[{bus_name}] ({len(id_period_map)}个): {detail}")

    # ECU 信息映射
    ecu_info_map = build_ecu_info_map(general_list)
    log_info(f"[{stage_name}] ECU 数量: {len(ecu_info_map)}")

    # CANID 周期映射
    can_id_period_map = build_can_id_period_map(general_list)
    log_info(f"[{stage_name}] CANID 周期映射数量: {len(can_id_period_map)}")

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

    return {
        "can_id_whitelist": can_id_whitelist,
        "ecu_info_map": ecu_info_map,
        "can_id_period_map": can_id_period_map,
        "bus_last_ecu": bus_last_ecu,
    }


def monitor_multi_ecu_upgrade(messages, ecu_list):
    """
    同时监控多个 ECU 的升级进度。

    Args:
        messages: 报文列表，每个报文字典需包含 "id"、"time"、"data" 键
        ecu_list: ECU 配置列表，每个元素为 dict：
            {
                "name": str,        # ECU 名称（用于日志展示）
                "req_canid": int,   # 诊断仪请求 CANID
                "resp_canid": int,  # ECU 响应 CANID
                "func_canid": int,  # 功能寻址 CANID（可选）
            }

    Returns:
        dict: {ecu_name: progress_result}
    """
    results = {}
    for ecu in ecu_list:
        name = ecu.get("name", f"ECU_0x{ecu['resp_canid']:03X}")
        req_canid = ecu.get("req_canid") or 0x700
        resp_canid = ecu.get("resp_canid") or 0x600
        func_canid = ecu.get("func_canid") or 0x7DF

        is_success, result = monitor_upgrade_process(
            messages,
            req_canid=req_canid,
            resp_canid=resp_canid,
            func_canid=func_canid,
        )

        results[name] = {
            "current_step": result.get("failed_step", 0) if not is_success else 30,
            "current_desc": result.get("error_message", "升级完成") if not is_success else "升级完成",
            "is_upgrade_success": result.get("is_upgrade_success", False),
            "is_upgrade_complete": result.get("is_upgrade_complete", False),
            "step_details": result.get("step_details", []),
            "elapsed_time_s": result.get("upgrade_time_s", 0.0),
            "found_completion_marker": result.get("found_completion_marker", False),
            "raw_result": result,
        }

    return results


def wait_for_upgrade_completion(msg_getter, resp_canid=0x600, completion_dids=None, timeout_s=600, poll_interval_s=0.5):
    """
    等待上一次 OTA 升级完成。

    通过监听报文，检查是否收到升级完成的结束标志（DID 响应）。

    Args:
        msg_getter: 可调用对象，每次调用返回当前收到的报文列表
                    例如: lambda: self.can.get_received_messages(clear=True)
        resp_canid: ECU 响应 CANID
        completion_dids: 升级完成的 DID 列表，默认使用 COMPLETION_DIDS
        timeout_s: 超时时间（秒），默认 600s
        poll_interval_s: 轮询间隔（秒）

    Returns:
        (completed: bool, message: str)
        completed: True 表示检测到升级已完成
        message: 说明信息
    """
    import time

    if completion_dids is None:
        completion_dids = COMPLETION_DIDS

    start_time = time.time()
    last_clear_time = start_time
    seen_msgs = set()  # 用于去重，避免重复处理相同报文

    while time.time() - start_time < timeout_s:
        elapsed = time.time() - start_time
        all_msgs = msg_getter()

        # 过滤出新增的报文（基于时间判断）
        new_msgs = [m for m in all_msgs if m.get("time", 0) >= last_clear_time]
        last_clear_time = time.time()

        for msg in new_msgs:
            msg_key = (msg.get("id"), msg.get("time"), tuple(msg.get("data") or []))
            if msg_key in seen_msgs:
                continue
            seen_msgs.add(msg_key)

            msg_id = msg.get("id")
            data = msg.get("data") or []

            # 检查结束标志
            for did in completion_dids:
                if _match_pattern(data, did):
                    elapsed_s = time.time() - start_time
                    return True, f"检测到升级完成标志 {did}, 耗时 {elapsed_s:.1f}s"

            # 也检查 51 01 作为成功标志
            if msg_id == resp_canid and _match_pattern(data, UPGRADE_SUCCESS_PATTERN):
                elapsed_s = time.time() - start_time
                return True, f"检测到升级成功标志 51 01, 耗时 {elapsed_s:.1f}s"

        time.sleep(poll_interval_s)

    elapsed_total = time.time() - start_time
    return False, f"等待升级完成超时 ({elapsed_total:.1f}s)，未检测到结束标志"


def check_upgrade_completion_status(messages, resp_canid=0x600, completion_dids=None):
    """
    检查报文列表中是否包含升级完成标志。

    Args:
        messages: 报文列表
        resp_canid: ECU 响应 CANID
        completion_dids: 升级完成的 DID 列表

    Returns:
        (found: bool, did_found: tuple or None)
    """
    if completion_dids is None:
        completion_dids = COMPLETION_DIDS

    for msg in messages:
        if msg.get("id") != resp_canid:
            continue
        data = msg.get("data") or []
        for did in completion_dids:
            if _match_pattern(data, did):
                return True, did
    return False, None