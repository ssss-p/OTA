from libTSCANAPI import *
from TSMasterAPI import tsapp_start_logging, tsapp_stop_logging
# from libTSCANAPI.TSCAN import tsapp_start_logging
import datetime
import msvcrt
import os
import threading
import time


class CANDevice:
    """同星 CAN/CANFD 设备操作类"""

    def __init__(self):
        self.devices = []
        self.initialized = False
        self._received_messages = []
        self._msg_lock = threading.Lock()
        self._receive_thread = None
        self._receive_running = False

    def initialize(self, support_can=True, support_canfd=True, support_lin=True):
        """初始化库"""
        initialize_lib_tscan(support_can, support_canfd, support_lin)
        self.initialized = True

    def finalize(self):
        """释放库资源"""
        for dev in self.devices:
            if dev.get("handle"):
                self.stop_receiving_thread()
                tsapp_disconnect_by_handle(dev["handle"])
        self.devices = []
        if self.initialized:
            finalize_lib_tscan()
            self.initialized = False

    def scan(self):
        """扫描并返回设备列表（不包含连接）"""
        device_count = c_int32(0)
        tscan_scan_devices(pointer(device_count))

        found = []
        for i in range(device_count.value):
            manu = c_char_p()
            prod = c_char_p()
            serial = c_char_p()
            tscan_get_device_info(i, manu, prod, serial)
            found.append({
                "index": i,
                "name": f"设备{i}",
                "serial": serial.value,
                "product": prod.value,
            })
        return found

    def connect(self, channel_configs=None):
        """
        扫描并连接所有设备。
        channel_configs: 每个设备的通道配置列表，例如：
            [
                [{"type": "canfd", "arb_kbps": 500, "data_kbps": 2000}, ...],
                [{"type": "can", "kbps": 500}, ...],
            ]
        """
        found = self.scan()
        for dev_info in found:
            handle = size_t(0)
            ret = tsapp_connect(dev_info["serial"], handle)
            if ret not in (0, 5):
                raise RuntimeError(f"连接设备 {dev_info['serial']} 失败，错误码={ret}")

            # ret = tsapp_start_logging(handle, b"D:/1.blf")
            # if (0 == ret):
            #     print("start log successfully")
            # else:
            #     print(f"start log failed,the error code is{ret}")

            dev = {
                "name": dev_info["name"],
                "serial": dev_info["serial"],
                "handle": handle,
                "channels": [],
            }

            configs = channel_configs[dev_info["index"]] if channel_configs and dev_info["index"] < len(channel_configs) else []
            for ch_idx, cfg in enumerate(configs):
                ch_info = {"index": ch_idx, "type": cfg["type"]}
                if cfg["type"] == "canfd":
                    tsapp_configure_baudrate_canfd(
                        handle, ch_idx,
                        cfg["arb_kbps"], cfg["data_kbps"], 1, 0, 1
                    )
                    ch_info["label"] = f"CANFD {cfg['arb_kbps']}k/{cfg['data_kbps']}k"
                else:
                    tsapp_configure_baudrate_can(
                        handle, ch_idx,
                        cfg["kbps"], 1
                    )
                    ch_info["label"] = f"CAN {cfg['kbps']}k"
                dev["channels"].append(ch_info)

            self.devices.append(dev)
        return self.devices

    def send_can(self, device_index, channel, can_id, data, is_extended=False):
        """发送一帧 CAN 报文"""
        if device_index >= len(self.devices):
            raise IndexError("设备索引超出范围")
        handle = self.devices[device_index]["handle"]
        msg = TLIBCAN()
        msg.FIdxChn = channel
        msg.FIdentifier = can_id
        msg.FProperties = 1  # TX
        msg.FDLC = len(data)
        for i, b in enumerate(data):
            msg.FData[i] = b
        tsapp_transmit_can_async(handle, msg)

    def send_canfd(self, device_index, channel, can_id, data, is_extended=False):
        """发送一帧 CANFD 报文"""
        if device_index >= len(self.devices):
            raise IndexError("设备索引超出范围")
        handle = self.devices[device_index]["handle"]
        msg = TLIBCANFD()
        msg.FIdxChn = channel
        msg.FIdentifier = can_id
        msg.FProperties = 1
        msg.FDLC = len(data)
        for i, b in enumerate(data):
            msg.FData[i] = b
        tsapp_transmit_canfd_async(handle, msg)

    def receive(self, device_index, channel, msg_type="canfd", timeout_ms=1000):
        """
        接收报文，返回列表。
        msg_type: 'can' 或 'canfd'
        """
        if device_index >= len(self.devices):
            raise IndexError("设备索引超出范围")
        handle = self.devices[device_index]["handle"]
        buf_size = 1000
        frame_count = c_int32(0)
        result = []

        if msg_type == "canfd":
            buf = (TLIBCANFD * buf_size)()
            tsfifo_read_canfd_buffer_frame_count(handle, channel, frame_count)
            if frame_count.value > 0:
                size = c_int32(buf_size)
                tsfifo_receive_canfd_msgs(handle, buf, size, channel, READ_TX_RX_DEF.TX_RX_MESSAGES)
                for i in range(size.value):
                    msg = buf[i]
                    direction = "Tx" if (msg.FProperties & 1) == 1 else "Rx"
                    result.append({
                        "serial":self.devices[device_index]['serial'],
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
            tsfifo_read_can_buffer_frame_count(handle, channel, frame_count)
            if frame_count.value > 0:
                size = c_int32(buf_size)
                tsfifo_receive_can_msgs(handle, buf, size, channel, READ_TX_RX_DEF.TX_RX_MESSAGES)
                for i in range(size.value):
                    msg = buf[i]
                    direction = "Tx" if (msg.FProperties & 1) == 1 else "Rx"
                    result.append({
                        "serial": self.devices[device_index]['serial'],
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
        targets = self.devices if device_index is None else [self.devices[device_index]]
        for dev in targets:
            for ch_info in dev["channels"]:
                if ch_info["type"] == msg_type:
                    messages.extend(self.receive(self.devices.index(dev), ch_info["index"], msg_type))
        return messages

    def start_receiving_thread(self, msg_types=("can", "canfd"), interval_ms=10):
        """启动后台线程实时接收所有设备的 CAN/CANFD 报文。"""
        if self._receive_thread is not None and self._receive_thread.is_alive():
            return
        self._receive_running = True
        self._receive_thread = threading.Thread(
            target=self._receive_loop,
            args=(msg_types, interval_ms),
            daemon=True,
        )
        self._receive_thread.start()

    def stop_receiving_thread(self):
        """停止后台接收线程。"""
        self._receive_running = False
        if self._receive_thread is not None and self._receive_thread.is_alive():
            self._receive_thread.join(timeout=1.0)
        self._receive_thread = None

    def _receive_loop(self, msg_types, interval_ms):
        """后台线程循环接收报文并存入列表。"""
        while self._receive_running:
            for msg_type in msg_types:
                try:
                    msgs = self.receive_all(msg_type=msg_type)
                    if msgs:
                        with self._msg_lock:
                            self._received_messages.extend(msgs)
                except Exception:
                    pass
            time.sleep(interval_ms / 1000.0)

    def get_received_messages(self, clear=False):
        """获取已接收的所有报文，clear=True 则清空缓存。按时间从小到大排序。"""
        with self._msg_lock:
            msgs = self._received_messages.copy()
            if clear:
                self._received_messages.clear()
        # 按时间排序
        msgs = sorted(msgs, key=lambda m: m.get("time", 0))
        return msgs

    def clear_received_messages(self):
        """清空已接收报文缓存。"""
        with self._msg_lock:
            self._received_messages.clear()

    def start_logging(self, log_dir):
        """开始记录 BLF 日志，文件名按日期时间命名。"""
        now = datetime.datetime.now()
        day_dir = now.strftime("%m%d")
        log_root = os.path.join(log_dir, day_dir)
        os.makedirs(log_root, exist_ok=True)

        log_name = now.strftime("%Y-%m-%d_%H-%M-%S") + ".blf"
        log_path = os.path.join(log_root, log_name).replace("\\", "/")
        blf_fileName = log_path.encode("utf-8")
        ret = tsapp_start_logging(b"D:/1.blf")
        # if (0 == ret):
        #     print("start log successfully")
        # else:
        #     print(f"start log failed,the error code is{ret}")

        if ret != 0:
            self.current_log_path = None
            return None

        self.current_log_path = log_path
        return log_path

    def stop_logging(self):
        """停止记录 BLF 日志。"""
        if self.current_log_path is None:
            return None
        tsapp_stop_logging()
        return self.current_log_path


# # 兼容原来的直接运行方式
# if __name__ == "__main__":
#     can = CANDevice()
#     can.initialize(True, True, True)
#     can.connect([
#         [{"type": "canfd", "arb_kbps": 500, "data_kbps": 2000}] * 4,
#         [{"type": "can", "kbps": 500}] * 4,
#     ])
#     print("按 q 退出")
#     while True:
#         msgs = can.receive_all(msg_type="canfd")
#         for msg in msgs:
#             data = " ".join(f"{b:02X}" for b in msg["data"])
#             print(f"{msg['type']} CH{msg['channel']} {msg['direction']} 0x{msg['id']:03X} {msg['dlc']} {data}")
#         if msvcrt.kbhit() and msvcrt.getch() == b'q':
#             break
#     can.finalize()
