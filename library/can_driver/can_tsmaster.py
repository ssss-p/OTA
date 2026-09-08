from TSMasterAPI import *
from ctypes import *
import time
msgcan = TLIBCAN()
msgcan.__init__()
CANData = [0x12,0x23,0x56,0x78,0x78,0x79,0x89,0x99]
msgcan.set_data(CANData)

msgcanfd = TLIBCANFD()
msgcanfd.FIdxChn = 1
msgcanfd.FIdentifier = 0x101
msgcanfd.FProperties = 5
msgcanfd.FFDProperties = 0x1
msgcanfd.FDLC = 9
CANDatafd = [0x78,0x79,0x89,0x99,0x12,0x23,0x56,0x78]
for i in range(len(CANDatafd)):
    msgcanfd.FData[i] = CANDatafd[i]

def On_CAN_EVENT(OBJ, ACAN):
    # print(f"id is :{ACAN.contents.FIdentifier} time is {ACAN.contents.FTimeUs / 1000000}")
    msg_id = ACAN.contents.FIdentifier
    time_s = ACAN.contents.FTimeUs / 1000000
    msg_dlc = ACAN.contents.FDLC
    chennel_id = ACAN.contents.FIdxChn

    payload_bytes = bytes(ACAN.contents.FData)
    data_len = len(payload_bytes)
    payload_hex = payload_bytes.hex().upper()
    # print(hex(msg_id), chennel_id, time_s, msg_dlc, data_len, payload_hex)
    print(chennel_id)
OnCANevent = TCANQueueEvent_Win32(On_CAN_EVENT)
obj = c_ulonglong(0)

def On_CANFD_EVENT(OBJ, ACANFD):
    msg_id = ACANFD.contents.FIdentifier
    time_s = ACANFD.contents.FTimeUs / 1000000
    msg_dlc = ACANFD.contents.FDLC
    chennel_id = ACANFD.contents.FIdxChn
    if ACANFD.contents.FFDProperties ==0:
        payload_bytes = bytes(ACANFD.contents.FData)
        payload_bytes = payload_bytes[:8]  # 只取前8个byte
        data_len = 8
        payload_hex = payload_bytes.hex().upper()
        # print(hex(msg_id),chennel_id,time_s,msg_dlc,data_len,payload_hex)
        print(chennel_id)
        # print(hex(msg_id), chennel_id, time_s, msg_dlc, data_len)
    else:
        payload_bytes = bytes(ACANFD.contents.FData)
        data_len = len(payload_bytes)
        payload_hex = payload_bytes.hex().upper()
        # print(hex(msg_id),chennel_id,time_s,msg_dlc,data_len,payload_hex)
        # print(hex(msg_id),chennel_id,time_s,msg_dlc,data_len)
        print(chennel_id)
OnCANFDevent = TCANFDQueueEvent_Win32(On_CANFD_EVENT)
obj1 = c_ulonglong(1)

def connect():
    ret = tsapp_set_can_channel_count(10)
    if(0 == ret):
        print("channel set successfully")
    else:
        print(f"channel set failed,the error code is{ret}")

    ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 0,"TC1016".encode("UTF8"), 3, 11, 0, 0, True)
    ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 1,"TC1016".encode("UTF8"), 3, 11, 0, 1, True)
    ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 2,"TC1016".encode("UTF8"), 3, 11, 0, 2, True)
    ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 3,"TC1016".encode("UTF8"), 3,11, 0, 3, True)
    ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 4, "TC1016".encode("UTF8"), 3, 11, 1, 0, True)
    ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 5, "TC1016".encode("UTF8"), 3, 11, 1, 1, True)
    ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 6, "TC1016".encode("UTF8"), 3, 11, 1, 2, True)
    ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 7, "TC1016".encode("UTF8"), 3, 11, 1, 3, True)
    ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 8, "TC1016".encode("UTF8"), 3, 11, 2, 0, True)
    ret = tsapp_set_mapping_verbose(b"TSMaster", 0, 9, "TC1016".encode("UTF8"), 3, 11, 2, 2, True)
    if(0 == ret):
        print("mapping successfully")
    else:
        print(f"mapping failed,the error code is{ret}")

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
    # ret = tsapp_configure_baudrate_can(0, 500.0, 0, True)
    # ret = tsapp_configure_baudrate_can(2, 500.0, 0, True)
    # ret = tsapp_configure_baudrate_can(0, 500.0, 0, True)
    # ret = tsapp_configure_baudrate_can(0, 500.0, 0, True)
    # ret = tsapp_configure_baudrate_can(0, 500.0, 0, True)
    if(0 == ret):
        print("baudrate set successfully")
    else:
        print(f"baudrate set failed,the error code is{ret}")

    # ret = tsapp_register_pretx_event_can(obj, OnCANevent)
    # if(0 == ret):
    #     print("event set successfully")
    # else:
    #     print(f"event set failed,the error code is{ret}")
    ret = tsapp_connect()
    if(0 == ret):
        print("connect successfully")
    else:
        print(f"connect failed,the error code is{ret}")
    tsfifo_enable_receive_fifo()
    # ret = tsapp_register_event_can(obj, OnCANevent)
    ret = tsapp_register_event_canfd(obj1, OnCANFDevent)
    if ret == 0:
        print("event set successfully")
    else:
        print(f"event set failed,the error code is{ret}")

def disconnect():
    ret = tsapp_disconnect()
    if(0 == ret):
        print("disconnect successfully")
    else:
        print(f"disconnect failed,the error code is{ret}")
    tsfifo_disable_receive_fifo()

def RBS_start():
    isruning = c_bool()
    ret = tscom_can_rbs_start()
    if(0 == ret):
        print("rbs start successfully")
    else:
        print(f"rbs start failed,the error code is{ret}")
    tscom_can_rbs_activate_network_by_name(0, True, b"CAN_FD_Powertrain", False)
    tscom_can_rbs_activate_node_by_name(0, True, b"CAN_FD_Powertrain", b"Engine", False)
    ret = tscom_can_rbs_activate_message_by_name(0, True, b"CAN_FD_Powertrain", b"Engine",b"EngineData")
    if(0 == ret):
        print("EngineData activate successfully")
    else:
        print(f"EngineData activate failed,the error code is{ret}")
    ret = tscom_can_rbs_activate_message_by_name(0, True, b"CAN_FD_Powertrain", b"Engine", b"ABSdata")
    if(0 == ret):
        print("ABSdata activate successfully")
    else:
        ret = tscom_can_rbs_activate_message_by_name(0, True, b"CAN_FD_Powertrain", b"Engine", b"GearBoxInfo")
    if(0 == ret):
        print("GearBoxInfo activate successfully")
    else:
        print(f"GearBoxInfo activate failed,the error code is{ret}")
    ret = tscom_can_rbs_set_signal_value_by_element(0, b"CAN_FD_Powertrain", b"Engine", b"GearBoxInfo", b"Gear",c_double(1.0))
    if(0 == ret):
        print("GearBoxInfo set successfully")
    else:
        print(f"GearBoxInfo set failed,the error code is{ret}")
    ret = can_rbs_set_rc_signal(b"0/CAN_FD_Powertrain/Engine/EngineData/EngSpeed")
    if(0 == ret):
        print("EngSpeed rc signal set successfully")
    else:
        print(f"EngSpeed rc signal set failed,the error code is{ret}")
    # ret = can_rbs_set_crc_signal(b"0/CAN_FD_Powertrain/Engine/ABSdata/CarSpeed",b"crc.crc8",0,4)
    # if(0 == ret):
    #     print("crc.crc8 set successfully")
    # else:
    #     print(f"crc.crc8 set failed,the error code is{ret}")
    ret = tscom_can_rbs_is_running(isruning)
    if(0 == ret):
        print("rbs is running")
    else:
        print(f"rbs didn't running failed,the error code is{ret}")
# filepath = b"C:\Users\guohaiyang\Desktop\dabate\CAN_FD_Powertrain.dbc"
# blf_fileName = b"C:\Users\guohaiyang\Desktop\dll\log_test.blf"
dbcid = c_ulong(0)
signalvalue = c_double(0)
idHandle = c_int32(0)
udsHandle = s32(0)
AReqDataArray = (c_uint8 * 100)()
AReqDataArray[0] = c_uint8(0x22)
AReqDataArray[1] = c_uint8(0xf1)
AReqDataArray[2] = c_uint8(0x90)
AResSize = c_int(10000)
AResponseDataArray = (c_uint8 * 10000)()

if __name__ == '__main__':

    initialize_lib_tsmaster("TSMaster".encode("utf8"))
    # ACount = c_int32(0)
    # r = tsapp_enumerate_hw_devices(ACount)
    # print(f"devies count is {ACount.value}")
    # tsfifo_clear_can_receive_buffers(0)
    while True:
        key = input("请输入操作：")
        if key == "a":
            connect()
        elif key == "disconnect":
            disconnect()
        elif key == "exit":
            disconnect()
            break
        elif key == "msg_can":
            for i in range(30):
                # ret = tsapp_transmit_can_async(byref(msgcan))
                ret = tsapp_transmit_canfd_async(byref(msgcanfd))
            if(0 == ret):
                print("transmit CAN or CANFD message successfully")
            else:
                print(f"transmit CAN or CANFD message failed,the error code is{ret}")
        elif key == "cyclic_msg":
            ret = tsapp_add_cyclic_msg_can(msgcan,100)
            ret = tsapp_add_cyclic_msg_canfd(msgcanfd,100)
            if(0 == ret):
                print("cyclic message add successfully")
            else:
                print(f"cyclic message add failed,the error code is{ret}")
        elif key == "stop_cyclic":
            ret = tsapp_delete_cyclic_msgs()
            if(0 == ret):
                print("cyclic message delete successfully")
            else:
                print(f"cyclic message delete failed,the error code is{ret}")
        elif key == "load_dbc":
            r = tsdb_load_can_db(filepath, b"0,1", dbcid)
            if(0 == r):
                print("load DBC successfully")
            else:
                print(f"load DBC failed,the error code is{r}")
        elif key == "unload_dbc":
            r = tsdb_unload_can_dbs()
            if(0 == r):
                print("unload DBF successfully")
            else:
                print(f"unload DBF failed,the error code is{r}")
        elif key == "b":
            ret = tsapp_start_logging(b"D:/1.blf")
            if(0 == ret):
                print("start log successfully")
            else:
                print(f"start log failed,the error code is{ret}")
        elif key == "c":
            ret = tsapp_stop_logging()
            if(0 == ret):
                print("stop log successfully")
            else:
                print(f"stop log failed,the error code is{ret}")
        elif key == "read_log":
            blfID = c_ulonglong(0)
            count = c_long(0)
            realCount = c_long(0)
            ret = tslog_blf_read_start(blf_fileName, blfID, count)
            if(0 == ret):
                print("read log successfully")
            else:
                print(f"read log failed,the error code is{ret}")
            C = TLIBCAN()
            FD = TLIBCANFD()
            L = TLIBLIN()
            F = TLIBFlexRay()
            t = c_long()
            for i in range(count.value):
                tslog_blf_read_object(blfID, realCount, t, C, L, FD)
                if t.value == 0:
                    print(C.FTimeUs / 1000000, C.FIdxChn, C.FIdentifier, C.FProperties,
                    C.FDLC,
                    C.FData[0], C.FData[1], C.FData[2], C.FData[3], C.FData[4],
                    C.FData[5], C.FData[6], C.FData[7])
            tslog_blf_read_end(blfID)
        elif key == "start_rbs":
            RBS_start()
        elif key == "stop_rbs":
            tscom_can_rbs_stop()
        elif key == "change_rbs":
            signal_input = input("value = " )
            signal_value = float(signal_input)
            tscom_can_rbs_set_message_cycle_by_name(0, 500,
                                                    b"CAN_FD_Powertrain", b"Engine", b"GearBoxInfo")
            tscom_can_rbs_set_signal_value_by_element(0, b"CAN_FD_Powertrain", b"Engine", b"GearBoxInfo", b"Gear",
                                                      c_double(signal_value))
            time.sleep(0.2)
            tscom_can_rbs_get_signal_value_by_element(0, b"CAN_FD_Powertrain", b"Engine", b"GearBoxInfo", b"Gear",
                                                      signalvalue)
            print(f"value = {signalvalue}")
        elif key == "uds":
            if 0 == tsdiag_can_create(udsHandle, 0, 0, 8, 0x7C0, True, 0X7C8, True, 0X3, True):
                print("UDS_SUCCESSFUL,udsHandle = ", udsHandle)
            for i in range(10):
                r = tstp_can_request_and_get_response(udsHandle, AReqDataArray, 3, AResponseDataArray, AResSize)
                print(AResSize.value)
                for i in range(AResSize.value):
                    print(hex(AResponseDataArray[i]), end="  ")
                    if i == AResSize.value - 1:
                        print(end='\n')

        else:
            print(f"unknown command,the error code is{key}")

    finalize_lib_tsmaster()


