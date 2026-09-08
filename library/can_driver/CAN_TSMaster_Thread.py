"""
基于 TSMaster 的 CAN/CANFD 设备操作类
实现线程获取报文的功能，类似 CAN.py 的 CANDevice 类
"""

from TSMasterAPI import *
from ctypes import *
import threading
import time
from collections import deque


class CANDevice:
    """基于 TSMaster 的 CAN/CANFD 设备操作类"""

    def __init__(self):
        self.devices = []
        self.initialized = False
        self._received_messages = []
        self._msg_lock = threading.Lock()
        self._receive_thread = None
        self._receive_running = False
        self._channel_count = 0
        self._channel_configs = []

    def initialize(self, support_can=True, support_canfd=True, support_lin=True):
        """初始化库"""
        initialize_lib_tsmaster("TSMaster".encode("utf8"))
        ret = tsapp_set_can_channel_count(10)  # 设置通道数量
        if ret == 0:
            print("channel count set successfully")
        else:
            print(f"channel count set failed, error code: {ret}")
        self.initialized = True

    def finalize(self):
        """释放库资源"""
        self.stop_receiving_thread()
        ret = tsapp_disconnect()
        if ret == 0:
            print("disconnect successfully")
        else:
            print(f"disconnect failed, error code: {ret}")
        tsfifo_disable_receive_fifo()
        self.devices = []
        self.initialized = False

    def scan(self):
        """扫描并返回设备列表"""
        # TSMaster 通常连接到本地应用，这里返回默认设备
        return [{
            "index": 0,
            "name": "TSMaster Device",
            "serial": "TSMaster",
            "product": "TSMaster",
        }]

    def connect(self, channel_configs=None):
        """
        连接设备并配置通道。

        Args:
            channel_configs: 通道配置列表
                [
                    [{"type": "canfd", "arb_kbps": 500, "data_kbps": 2000}, ...],
                    [{"type": "can", "kbps": 500}, ...],
                ]
        """
        self._channel_configs = channel_configs if channel_configs else []

        # 设置通道映射
        # for i in range(len(channel_configs[0]) if channel_configs else 1):
        #     if i < 2:  # 最多配置2个通道
        #         ret = tsapp_set_mapping_verbose(
        #             b"TSMaster", 0, i,
        #             "TC1016".encode("UTF8"), 3, 11, i, i, True
        #         )
        #         if ret == 0:
        #             print(f"channel {i} mapping successfully")
        #         else:
        #             print(f"channel {i} mapping failed, error code: {ret}")
        ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 0, "TC1016".encode("UTF8"), 3, 11, 0, 0, True)
        ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 1, "TC1016".encode("UTF8"), 3, 11, 0, 1, True)
        ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 2, "TC1016".encode("UTF8"), 3, 11, 0, 2, True)
        ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 3, "TC1016".encode("UTF8"), 3, 11, 0, 3, True)
        ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 4, "TC1016".encode("UTF8"), 3, 11, 1, 0, True)
        ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 5, "TC1016".encode("UTF8"), 3, 11, 1, 1, True)
        ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 6, "TC1016".encode("UTF8"), 3, 11, 1, 2, True)
        ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 7, "TC1016".encode("UTF8"), 3, 11, 1, 3, True)
        ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 8, "TC1016".encode("UTF8"), 3, 11, 2, 0, True)
        ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 9, "TC1016".encode("UTF8"), 3, 11, 2, 2, True)
        if ret == 0:
            print(f"channel {i} mapping successfully")
        else:
            print(f"channel {i} mapping failed, error code: {ret}")

        # 配置波特率
        # if channel_configs and len(channel_configs) > 0:
        #     for ch_idx, cfg in enumerate(channel_configs[0]):
        #         if cfg.get("type") == "canfd":
        #             ret = tsapp_configure_baudrate_canfd(
        #                 0,  # handle
        #                 float(cfg.get("arb_kbps", 500)),
        #                 float(cfg.get("data_kbps", 2000)),
        #                 1, 0, True
        #             )
        #             print(f"CANFD channel {ch_idx} baudrate set successfully")
        #         elif cfg.get("type") == "can":
        #             ret = tsapp_configure_baudrate_can(
        #                 ch_idx,
        #                 float(cfg.get("kbps", 500)),
        #                 0, True
        #             )
        #             print(f"CAN channel {ch_idx} baudrate set successfully")


        # ret = tsapp_configure_baudrate_can(1, 500.0, 0, True)
        ret = tsapp_configure_baudrate_canfd(0, 500.0, 2000.0, 1, 0, True)
        ret = tsapp_configure_baudrate_canfd(1, 500.0, 2000.0, 1, 0, True)
        ret = tsapp_configure_baudrate_canfd(2, 500.0, 2000.0, 1, 0, True)
        ret = tsapp_configure_baudrate_canfd(3, 500.0, 2000.0, 1, 0, True)
        ret = tsapp_configure_baudrate_canfd(4, 500.0, 2000.0, 1, 0, True)
        ret = tsapp_configure_baudrate_canfd(5, 500.0, 2000.0, 1, 0, True)
        ret = tsapp_configure_baudrate_canfd(6, 500.0, 2000.0, 1, 0, True)
        ret = tsapp_configure_baudrate_canfd(7, 500.0, 2000.0, 1, 0, True)
        ret = tsapp_configure_baudrate_canfd(8, 500.0, 2000.0, 1, 0, True)
        ret = tsapp_configure_baudrate_canfd(9, 500.0, 2000.0, 1, 0, True)
        # 连接
        ret = tsapp_connect()
        if ret == 0:
            print("connect successfully")
        else:
            print(f"connect failed, error code: {ret}")

        # 启用接收FIFO
        tsfifo_enable_receive_fifo()

        # 记录设备信息
        dev = {
            "name": "TSMaster Device",
            "serial": "TSMaster",
            "handle": 0,
            "channels": [],
        }

        # if channel_configs and len(channel_configs) > 0:
        #     for ch_idx, cfg in enumerate(channel_configs[0]):
        #         dev["channels"].append({
        #             "index": ch_idx,
        #             "type": cfg.get("type", "canfd"),
        #             "label": f"{cfg.get('type', 'CANFD').upper()} {cfg.get('arb_kbps', 500)}k/{cfg.get('data_kbps', 2000)}k"
        #         })

        self.devices.append(dev)
        self._channel_count = len(dev["channels"])

        return self.devices

    def send_can(self, device_index, channel, can_id, data, is_extended=False):
        """发送一帧 CAN 报文"""
        msg = TLIBCAN()
        msg.FIdxChn = channel
        msg.FIdentifier = can_id
        msg.FProperties = 1  # TX
        msg.FDLC = len(data)
        for i, b in enumerate(data):
            msg.FData[i] = b
        tsapp_transmit_can_async(0, msg)

    def send_canfd(self, device_index, channel, can_id, data, is_extended=False):
        """发送一帧 CANFD 报文"""
        msg = TLIBCANFD()
        msg.FIdxChn = channel
        msg.FIdentifier = can_id
        msg.FProperties = 1  # TX
        msg.FDLC = len(data)
        for i, b in enumerate(data):
            msg.FData[i] = b
        tsapp_transmit_canfd_async(0, msg)

    # def _on_can_message(self, OBJ, ACAN):
    #     """CAN 报文回调函数"""
    #     msg_id = ACAN.contents.FIdentifier
    #     time_s = ACAN.contents.FTimeUs / 1000000
    #     msg_dlc = ACAN.contents.FDLC
    #     channel_id = ACAN.contents.FIdxChn
    #
    #     payload = [ACAN.contents.FData[i] for i in range(min(msg_dlc, 8))]
    #
    #     msg_dict = {
    #         "serial": "TSMaster",
    #         "channel": channel_id,
    #         "type": "CAN",
    #         "direction": "Tx" if (ACAN.contents.FProperties & 1) == 1 else "Rx",
    #         "id": msg_id,
    #         "dlc": msg_dlc,
    #         "data": payload,
    #         "time": time_s,
    #     }
    #
    #     with self._msg_lock:
    #         self._received_messages.append(msg_dict)

    def _on_canfd_message(self, OBJ, ACANFD):
        """CANFD 报文回调函数"""
        msg_id = ACANFD.contents.FIdentifier
        time_s = ACANFD.contents.FTimeUs / 1000000
        msg_dlc = ACANFD.contents.FDLC
        channel_id = ACANFD.contents.FIdxChn

        # 判断是CAN还是CANFD数据
        if ACANFD.contents.FFDProperties == 0:
            # 传统CAN数据（8字节）
            payload = [ACANFD.contents.FData[i] for i in range(8)]
        else:
            # CANFD数据
            payload = [ACANFD.contents.FData[i] for i in range(min(msg_dlc, 64))]

        # 打印报文信息
        direction = "Tx" if (ACANFD.contents.FProperties & 1) == 1 else "Rx"
        data_hex = " ".join(f"{b:02X}" for b in payload)
        print(f"[CANFD] Ch{channel_id} {direction} ID=0x{msg_id:03X} DLC={msg_dlc} Data=[{data_hex}] Time={time_s:.6f}s")

        msg_dict = {
            "serial": "TSMaster",
            "channel": channel_id,
            "type": "CANFD",
            "direction": direction,
            "id": msg_id,
            "dlc": msg_dlc,
            "data": payload,
            "time": time_s,
        }

        with self._msg_lock:
            self._received_messages.append(msg_dict)

    def receive(self, device_index=0, channel=None, msg_type="canfd", timeout_ms=1000):
        """
        接收报文，返回列表。
        Args:
            device_index: 设备索引
            channel: 通道索引，None表示所有通道
            msg_type: 'can' 或 'canfd'
            timeout_ms: 超时时间（毫秒）
        """
        result = []
        buf_size = 1000
        frame_count = c_int32(0)

        if msg_type == "canfd":
            buf = (TLIBCANFD * buf_size)()
            channels_to_read = [channel] if channel is not None else range(self._channel_count)

            for ch in channels_to_read:
                tsfifo_read_canfd_buffer_frame_count(0, ch, frame_count)
                if frame_count.value > 0:
                    size = c_int32(buf_size)
                    tsfifo_receive_canfd_msgs(0, buf, size, ch, READ_TX_RX_DEF.TX_RX_MESSAGES)
                    for i in range(size.value):
                        msg = buf[i]
                        direction = "Tx" if (msg.FProperties & 1) == 1 else "Rx"
                        result.append({
                            "serial": "TSMaster",
                            "channel": msg.FIdxChn,
                            "type": "CANFD",
                            "direction": direction,
                            "id": msg.FIdentifier,
                            "dlc": msg.FDLC,
                            "data": [msg.FData[j] for j in range(msg.FDLC)],
                            "time": msg.FTimeUs / 1000000,
                        })
        else:
            buf = (TLIBCAN * buf_size)()
            channels_to_read = [channel] if channel is not None else range(self._channel_count)

            for ch in channels_to_read:
                tsfifo_read_can_buffer_frame_count(0, ch, frame_count)
                if frame_count.value > 0:
                    size = c_int32(buf_size)
                    tsfifo_receive_can_msgs(0, buf, size, ch, READ_TX_RX_DEF.TX_RX_MESSAGES)
                    for i in range(size.value):
                        msg = buf[i]
                        direction = "Tx" if (msg.FProperties & 1) == 1 else "Rx"
                        result.append({
                            "serial": "TSMaster",
                            "channel": msg.FIdxChn,
                            "type": "CAN",
                            "direction": direction,
                            "id": msg.FIdentifier,
                            "dlc": msg.FDLC,
                            "data": [msg.FData[j] for j in range(msg.FDLC)],
                            "time": msg.FTimeUs / 1000000,
                        })

        return result

    def receive_all(self, device_index=None, msg_type="canfd"):
        """轮询所有通道，返回报文列表"""
        messages = []
        channels_to_read = range(self._channel_count)

        for ch in channels_to_read:
            messages.extend(self.receive(device_index=0, channel=ch, msg_type=msg_type))

        return messages

    def start_receiving_thread(self, msg_types=("canfd", "canfd"), interval_ms=10):
        """
        启动后台线程实时接收所有设备的 CAN/CANFD 报文。

        Args:
            msg_types: 要接收的报文类型元组，例如 ("canfd", "can") 或 ("can", "canfd")
            interval_ms: 轮询间隔（毫秒）
        """
        if self._receive_thread is not None and self._receive_thread.is_alive():
            print("Receiving thread already running")
            return

        self._receive_running = True

        # 注册CAN事件回调
        # self._can_event = TCANQueueEvent_Win32(self._on_can_message)
        # self._can_obj = c_ulonglong(0)
        # ret_can = tsapp_register_event_can(self._can_obj, self._can_event)
        # if ret_can == 0:
        #     print("CAN event registered successfully")
        # else:
        #     print(f"CAN event registration failed, error code: {ret_can}")

        # 注册CANFD事件回调
        self._canfd_event = TCANFDQueueEvent_Win32(self._on_canfd_message)
        self._canfd_obj = c_ulonglong(1)
        ret_canfd = tsapp_register_event_canfd(self._canfd_obj, self._canfd_event)
        if ret_canfd == 0:
            print("CANFD event registered successfully")
        else:
            print(f"CANFD event registration failed, error code: {ret_canfd}")

        # 启动后台线程
        self._receive_thread = threading.Thread(
            target=self._receive_loop,
            args=(msg_types, interval_ms),
            daemon=True,
        )
        self._receive_thread.start()
        print(f"Receiving thread started (interval: {interval_ms}ms)")

    def stop_receiving_thread(self):
        """停止后台接收线程"""
        self._receive_running = False
        if self._receive_thread is not None:
            self._receive_thread.join(timeout=2.0)
            if not self._receive_thread.is_alive():
                print("Receiving thread stopped")
            else:
                print("Receiving thread stop timeout")
        self._receive_thread = None

    def _receive_loop(self, msg_types, interval_ms):
        """
        后台线程循环接收报文。

        Args:
            msg_types: 要接收的报文类型元组
            interval_ms: 轮询间隔（毫秒）
        """
        while self._receive_running:
            try:
                for msg_type in msg_types:
                    msgs = self.receive_all(msg_type=msg_type)
                    if msgs:
                        with self._msg_lock:
                            self._received_messages.extend(msgs)
            except Exception as e:
                print(f"Error in receive loop: {e}")

            time.sleep(interval_ms / 1000.0)

    def get_received_messages(self, clear=False):
        """
        获取已接收的所有报文。

        Args:
            clear: 是否清空缓存

        Returns:
            list: 报文列表，按时间从小到大排序
        """
        with self._msg_lock:
            msgs = self._received_messages.copy()
            if clear:
                self._received_messages.clear()

        # 按时间排序
        msgs = sorted(msgs, key=lambda m: m.get("time", 0))
        return msgs

    def clear_received_messages(self):
        """清空已接收报文缓存"""
        with self._msg_lock:
            self._received_messages.clear()
        print("Received messages cleared")

    def start_logging(self, log_dir):
        """
        开始记录 BLF 日志

        Args:
            log_dir: 日志目录路径
        """
        import datetime
        import os

        now = datetime.datetime.now()
        day_dir = now.strftime("%m%d")
        log_root = os.path.join(log_dir, day_dir)
        os.makedirs(log_root, exist_ok=True)

        log_file = os.path.join(log_root, now.strftime("%H%M%S") + ".blf")
        ret = tsapp_start_logging(log_file.encode('utf-8'))
        # ret = tsapp_start_logging(b"D:/1.blf")
        if ret == 0:
            print(f"Logging started")
        else:
            print(f"Logging start failed, error code: {ret}")

    def stop_logging(self):
        """停止记录 BLF 日志"""
        ret = tsapp_stop_logging()
        if ret == 0:
            print("Logging stopped")
        else:
            print(f"Logging stop failed, error code: {ret}")


# 示例用法
if __name__ == "__main__":
    can = CANDevice()
    can.initialize()

    # 配置通道
    channel_configs = [
        [
            {"type": "canfd", "arb_kbps": 500, "data_kbps": 2000},
            {"type": "canfd", "arb_kbps": 500, "data_kbps": 2000},
        ]
    ]

    can.connect(channel_configs)

    # 启动接收线程
    can.start_receiving_thread(msg_types=("canfd", "can"), interval_ms=10)

    try:
        # 运行10秒，每秒打印接收到的报文数量
        for i in range(10):
            time.sleep(1)
            msgs = can.get_received_messages(clear=True)
            print(f"Second {i+1}: Received {len(msgs)} messages")
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        can.stop_receiving_thread()
        can.finalize()