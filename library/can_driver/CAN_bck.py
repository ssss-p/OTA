from libTSCANAPI import *
import msvcrt

# ========== 1. 初始化 ==========
initialize_lib_tscan(True, True, True)

# ========== 2. 扫描设备，获取每台的序列号 ==========
device_count = c_int32(0)
tscan_scan_devices(pointer(device_count))
print(f"发现 {device_count.value} 台设备")

# if device_count.value < 2:
#     print("错误：需要连接两台 1016 设备！")
#     finalize_lib_tscan()
#     exit()

devices = []
for i in range(device_count.value):
    manu = c_char_p()
    prod = c_char_p()
    serial = c_char_p()
    tscan_get_device_info(i, manu, prod, serial)
    devices.append({
        "name": f"设备{i}",
        "serial": serial.value,
    })
    print(f"  [{i}] 序列号={serial.value}  产品={prod.value}")

# ========== 3. 分别连接两台设备（用序列号区分） ==========
for dev in devices:
    dev["handle"] = size_t(0)
    ret = tsapp_connect(dev["serial"], dev["handle"])
    if ret in (0, 5):
        print(f"{dev['name']} [{dev['serial']}] 连接成功, handle={dev['handle'].value}")
    else:
        print(f"{dev['name']} [{dev['serial']}] 连接失败! 错误码={ret}")
        finalize_lib_tscan()
        exit()

# ========== 4. 通道配置 ==========
# 每个通道: type="canfd" 或 "can", 以及对应波特率
# 设备0（第一台1016）: 通道0=CANFD, 通道1=CAN
# 设备1（第二台1016）: 全部CANFD
channel_configs = [
    [
        {"type": "canfd", "arb_kbps": 500, "data_kbps": 2000},  # CH0
        {"type": "canfd", "arb_kbps": 500, "data_kbps": 2000},  # CH1
        {"type": "canfd", "arb_kbps": 500, "data_kbps": 2000},  # CH2
        {"type": "canfd", "arb_kbps": 500, "data_kbps": 2000},  # CH3
    ],
    [
        {"type": "can",  "kbps": 500},   # CH0
        {"type": "can",  "kbps": 500},                          # CH1
        {"type": "can",  "kbps": 500},
        {"type": "can",  "kbps": 500},
    ],
]

for i, dev in enumerate(devices):
    configs = channel_configs[i] if i < len(channel_configs) else []
    dev["channels"] = []
    for ch_idx, cfg in enumerate(configs):
        ch_info = {"index": ch_idx, "type": cfg["type"]}
        if cfg["type"] == "canfd":
            tsapp_configure_baudrate_canfd(
                dev["handle"], ch_idx,
                cfg["arb_kbps"], cfg["data_kbps"], 1, 0, 1
            )
            ch_info["label"] = f"CANFD {cfg['arb_kbps']}k/{cfg['data_kbps']}k"
        else:
            tsapp_configure_baudrate_can(
                dev["handle"], ch_idx,
                cfg["kbps"], 1
            )
            ch_info["label"] = f"CAN {cfg['kbps']}k"
        dev["channels"].append(ch_info)
        print(f"  {dev['name']} CH{ch_idx}: {ch_info['label']} 已配置")

# ========== 5. FIFO 轮询接收 ==========
RECV_BUF_SIZE = 100
for dev in devices:
    dev["buf_canfd"] = (TLIBCANFD * RECV_BUF_SIZE)()
    dev["buf_can"] = (TLIBCAN * RECV_BUF_SIZE)()

print("\n" + "=" * 100)
print(f"{'设备/序列号':<25} {'CH':<4} {'类型':<6} {'方向':<4} {'ID':<10} {'DLC':<4} {'数据':<48} {'时间戳'}")
print("=" * 100)

while True:
    for dev in devices:
        for ch_info in dev["channels"]:
            ch = ch_info["index"]
            frame_count = c_int32(0)

            if ch_info["type"] == "canfd":
                tsfifo_read_canfd_buffer_frame_count(dev["handle"], ch, frame_count)
                if frame_count.value > 0:
                    size = c_int32(RECV_BUF_SIZE)
                    tsfifo_receive_canfd_msgs(
                        dev["handle"], dev["buf_canfd"], size,
                        ch, READ_TX_RX_DEF.TX_RX_MESSAGES
                    )
                    for i in range(size.value):
                        msg = dev["buf_canfd"][i]
                        direction = "Tx" if (msg.FProperties & 1) == 1 else "Rx"
                        data = " ".join(f"{msg.FData[j]:02X}" for j in range(msg.FDLC))
                        label = f"{dev['name']}({dev['serial']})"
                        print(
                            f"{label:<25} "
                            f"{msg.FIdxChn:<4} "
                            f"{'CANFD':<6} "
                            f"{direction:<4} "
                            f"0x{msg.FIdentifier:03X}     "
                            f"{msg.FDLC:<4} "
                            f"{data:<48} "
                            f"{msg.FTimeUs / 1000000:.6f}s"
                        )
            else:
                tsfifo_read_can_buffer_frame_count(dev["handle"], ch, frame_count)
                if frame_count.value > 0:
                    size = c_int32(RECV_BUF_SIZE)
                    tsfifo_receive_can_msgs(
                        dev["handle"], dev["buf_can"], size,
                        ch, READ_TX_RX_DEF.TX_RX_MESSAGES
                    )
                    for i in range(size.value):
                        msg = dev["buf_can"][i]
                        direction = "Tx" if (msg.FProperties & 1) == 1 else "Rx"
                        data = " ".join(f"{msg.FData[j]:02X}" for j in range(msg.FDLC))
                        label = f"{dev['name']}({dev['serial']})"
                        print(
                            f"{label:<25} "
                            f"{msg.FIdxChn:<4} "
                            f"{'CAN':<6} "
                            f"{direction:<4} "
                            f"0x{msg.FIdentifier:03X}     "
                            f"{msg.FDLC:<4} "
                            f"{data:<48} "
                            f"{msg.FTimeUs / 1000000:.6f}s"
                        )

    if msvcrt.kbhit() and msvcrt.getch() == b'q':
        break

# ========== 6. 清理 ==========
for dev in devices:
    tsapp_disconnect_by_handle(dev["handle"])
finalize_lib_tscan()
print("已断开连接")
