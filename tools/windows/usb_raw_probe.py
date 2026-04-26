#!/usr/bin/env python3
"""
第三轮探测：绕过 HID 层，用 pyusb 直接探索 USB 描述符和端点。

前两轮 HID 探测发现：标准 HID 无法激活 IMU 数据流。
本轮目标：
  1. 枚举所有 USB 接口（包括非 HID 接口 0/1/2）
  2. 读取完整 USB 描述符（Device/Config/Interface/Endpoint）
  3. 获取 HID Report Descriptor 原始字节
  4. 尝试在每个 Interrupt IN 端点上直接读取数据
  5. 尝试 USB 控制传输激活 IMU

依赖：
  pip install pyusb
  Windows 需要安装 libusb：
    pip install libusb
  或从 https://github.com/libusb/libusb/releases 下载 libusb-1.0.dll
  放到 Python 安装目录或脚本同目录

用法：
  python usb_raw_probe.py
"""

import sys
import time
import json
import struct
from datetime import datetime

try:
    import usb.core
    import usb.util
    import usb.backend.libusb1
except ImportError:
    print("错误：需要安装 pyusb")
    print("  pip install pyusb")
    print("  pip install libusb  (Windows)")
    sys.exit(1)

VID = 0x2A45
PID = 0x2050

# HID 类请求常量
HID_GET_REPORT = 0x01
HID_SET_REPORT = 0x09
HID_GET_DESCRIPTOR = 0x06
HID_REPORT_TYPE_INPUT = 0x01
HID_REPORT_TYPE_OUTPUT = 0x02
HID_REPORT_TYPE_FEATURE = 0x03
HID_DESCRIPTOR_TYPE_REPORT = 0x22


def find_device():
    """查找设备，尝试不同后端"""
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        # Windows 上尝试显式加载 libusb
        try:
            import libusb
            backend = usb.backend.libusb1.get_backend(find_library=lambda x: libusb._platform.lib._name)
            dev = usb.core.find(idVendor=VID, idProduct=PID, backend=backend)
        except Exception:
            pass

    if dev is None:
        try:
            backend = usb.backend.libusb1.get_backend(find_library=lambda x: "libusb-1.0.dll")
            dev = usb.core.find(idVendor=VID, idProduct=PID, backend=backend)
        except Exception:
            pass

    return dev


def dump_device_descriptor(dev, report):
    """读取并记录设备描述符"""
    info = {
        "bcdUSB": f"0x{dev.bcdUSB:04X}",
        "bDeviceClass": dev.bDeviceClass,
        "bDeviceSubClass": dev.bDeviceSubClass,
        "bDeviceProtocol": dev.bDeviceProtocol,
        "bMaxPacketSize0": dev.bMaxPacketSize0,
        "idVendor": f"0x{dev.idVendor:04X}",
        "idProduct": f"0x{dev.idProduct:04X}",
        "bcdDevice": f"0x{dev.bcdDevice:04X}",
        "bNumConfigurations": dev.bNumConfigurations,
        "iManufacturer": dev.iManufacturer,
        "iProduct": dev.iProduct,
        "iSerialNumber": dev.iSerialNumber,
    }

    # 尝试读取字符串描述符
    for field, idx in [("manufacturer", dev.iManufacturer),
                       ("product", dev.iProduct),
                       ("serial", dev.iSerialNumber)]:
        if idx:
            try:
                info[f"{field}_string"] = usb.util.get_string(dev, idx)
            except Exception as e:
                info[f"{field}_string"] = f"(error: {e})"

    report["device"] = info
    print(f"  USB {info['bcdUSB']}, Class={dev.bDeviceClass}")
    print(f"  Vendor: {info.get('manufacturer_string', '?')}")
    print(f"  Product: {info.get('product_string', '?')}")
    print(f"  Serial: {info.get('serial_string', '?')}")
    print(f"  bcdDevice: {info['bcdDevice']}")
    print(f"  Configurations: {dev.bNumConfigurations}")


def dump_all_interfaces(dev, report):
    """枚举所有配置、接口、端点"""
    interfaces = []

    for cfg in dev:
        print(f"\n  Configuration {cfg.bConfigurationValue}:")
        print(f"    bNumInterfaces: {cfg.bNumInterfaces}")

        for intf in cfg:
            iface_info = {
                "bInterfaceNumber": intf.bInterfaceNumber,
                "bAlternateSetting": intf.bAlternateSetting,
                "bInterfaceClass": intf.bInterfaceClass,
                "bInterfaceSubClass": intf.bInterfaceSubClass,
                "bInterfaceProtocol": intf.bInterfaceProtocol,
                "bNumEndpoints": intf.bNumEndpoints,
                "class_name": usb_class_name(intf.bInterfaceClass),
                "endpoints": [],
            }

            # 尝试读取接口字符串
            if intf.iInterface:
                try:
                    iface_info["interface_string"] = usb.util.get_string(dev, intf.iInterface)
                except Exception:
                    pass

            print(f"\n    Interface {intf.bInterfaceNumber} (Alt {intf.bAlternateSetting}):")
            print(f"      Class: {intf.bInterfaceClass} ({iface_info['class_name']})")
            print(f"      SubClass: {intf.bInterfaceSubClass}  Protocol: {intf.bInterfaceProtocol}")
            print(f"      Endpoints: {intf.bNumEndpoints}")

            for ep in intf:
                ep_info = {
                    "bEndpointAddress": f"0x{ep.bEndpointAddress:02X}",
                    "bmAttributes": ep.bmAttributes,
                    "type": endpoint_type_name(ep.bmAttributes),
                    "direction": "IN" if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else "OUT",
                    "wMaxPacketSize": ep.wMaxPacketSize,
                    "bInterval": ep.bInterval,
                }
                iface_info["endpoints"].append(ep_info)
                print(f"      EP 0x{ep.bEndpointAddress:02X}: {ep_info['type']} {ep_info['direction']}, "
                      f"MaxPacket={ep.wMaxPacketSize}, Interval={ep.bInterval}ms")

            interfaces.append(iface_info)

    report["interfaces"] = interfaces
    return interfaces


def get_hid_report_descriptors(dev, interfaces, report):
    """对所有 HID 接口，获取 Report Descriptor"""
    print("\n" + "=" * 60)
    print("HID Report Descriptor 读取")
    print("=" * 60)

    hid_descriptors = []

    for iface_info in interfaces:
        if iface_info["bInterfaceClass"] != 3:  # 不是 HID
            continue

        iface_num = iface_info["bInterfaceNumber"]
        print(f"\n  接口 {iface_num}:")

        try:
            # HID Report Descriptor: GET_DESCRIPTOR, type=0x22, wIndex=interface
            # bmRequestType: 0x81 (Device-to-host, Standard, Interface)
            desc = dev.ctrl_transfer(
                0x81,  # bmRequestType: IN, Standard, Interface
                HID_GET_DESCRIPTOR,  # bRequest
                (HID_DESCRIPTOR_TYPE_REPORT << 8) | 0,  # wValue: Report Descriptor type
                iface_num,  # wIndex: interface number
                4096,  # wLength
                timeout=2000
            )
            hex_str = " ".join(f"{b:02x}" for b in desc)
            hid_descriptors.append({
                "interface": iface_num,
                "length": len(desc),
                "raw_hex": hex_str,
                "parsed": parse_hid_report_descriptor(bytes(desc)),
            })
            print(f"    长度: {len(desc)} 字节")
            print(f"    原始: {hex_str[:120]}...")
        except Exception as e:
            hid_descriptors.append({
                "interface": iface_num,
                "error": str(e),
            })
            print(f"    错误: {e}")

    report["hid_report_descriptors"] = hid_descriptors


def parse_hid_report_descriptor(data):
    """简单解析 HID Report Descriptor，提取 Report ID 和 Usage"""
    items = []
    i = 0
    while i < len(data):
        byte0 = data[i]
        if byte0 == 0xFE:  # Long item
            if i + 2 < len(data):
                size = data[i + 1]
                i += 3 + size
            else:
                break
            continue

        size = byte0 & 0x03
        if size == 3:
            size = 4
        item_type = (byte0 >> 2) & 0x03
        tag = (byte0 >> 4) & 0x0F

        if i + 1 + size > len(data):
            break

        value_bytes = data[i + 1:i + 1 + size]
        if size == 1:
            value = value_bytes[0]
        elif size == 2:
            value = struct.unpack("<H", value_bytes)[0]
        elif size == 4:
            value = struct.unpack("<I", value_bytes)[0]
        else:
            value = 0

        type_names = {0: "Main", 1: "Global", 2: "Local", 3: "Reserved"}
        main_tags = {0x08: "Input", 0x09: "Output", 0x0B: "Feature",
                     0x0A: "Collection", 0x0C: "End Collection"}
        global_tags = {0x00: "Usage Page", 0x01: "Logical Minimum",
                       0x02: "Logical Maximum", 0x03: "Physical Minimum",
                       0x04: "Physical Maximum", 0x05: "Unit Exponent",
                       0x06: "Unit", 0x07: "Report Size", 0x08: "Report ID",
                       0x09: "Report Count"}
        local_tags = {0x00: "Usage", 0x01: "Usage Minimum", 0x02: "Usage Maximum"}

        if item_type == 0:
            tag_name = main_tags.get(tag, f"Main(0x{tag:X})")
        elif item_type == 1:
            tag_name = global_tags.get(tag, f"Global(0x{tag:X})")
        elif item_type == 2:
            tag_name = local_tags.get(tag, f"Local(0x{tag:X})")
        else:
            tag_name = f"Reserved(0x{tag:X})"

        items.append({
            "offset": i,
            "tag": tag_name,
            "value": f"0x{value:X}" if value > 9 else str(value),
            "raw": " ".join(f"{b:02x}" for b in data[i:i + 1 + size]),
        })

        i += 1 + size

    return items


def try_interrupt_reads(dev, interfaces, report):
    """尝试在每个 Interrupt IN 端点上直接读取数据"""
    print("\n" + "=" * 60)
    print("Interrupt IN 端点直接读取")
    print("=" * 60)

    endpoint_reads = []

    for iface_info in interfaces:
        iface_num = iface_info["bInterfaceNumber"]

        for ep_info in iface_info["endpoints"]:
            if ep_info["direction"] != "IN":
                continue
            if "Interrupt" not in ep_info["type"]:
                continue

            ep_addr = int(ep_info["bEndpointAddress"], 16)
            max_packet = ep_info["wMaxPacketSize"]
            print(f"\n  接口 {iface_num}, EP 0x{ep_addr:02X} (MaxPacket={max_packet}):")

            # 先尝试 claim 接口
            try:
                if dev.is_kernel_driver_active(iface_num):
                    dev.detach_kernel_driver(iface_num)
                    print(f"    已分离内核驱动")
            except (usb.core.USBError, NotImplementedError):
                pass

            try:
                usb.util.claim_interface(dev, iface_num)
            except usb.core.USBError as e:
                endpoint_reads.append({
                    "interface": iface_num,
                    "endpoint": f"0x{ep_addr:02X}",
                    "error": f"无法 claim 接口: {e}",
                })
                print(f"    无法 claim 接口: {e}")
                continue

            # 读取 3 秒
            packets = []
            t0 = time.time()
            read_errors = 0
            while time.time() - t0 < 3.0:
                try:
                    data = dev.read(ep_addr, max_packet, timeout=50)
                    if data and len(data) > 0:
                        packets.append({
                            "time": round(time.time() - t0, 4),
                            "data": " ".join(f"{b:02x}" for b in data),
                            "length": len(data),
                        })
                except usb.core.USBTimeoutError:
                    pass
                except usb.core.USBError as e:
                    read_errors += 1
                    if read_errors >= 3:
                        break

            result = {
                "interface": iface_num,
                "endpoint": f"0x{ep_addr:02X}",
                "packets_received": len(packets),
                "samples": packets[:10],
                "read_errors": read_errors,
            }
            if packets:
                result["rate_hz"] = round(len(packets) / 3.0, 1)
                print(f"    收到 {len(packets)} 个数据包 (~{result['rate_hz']} Hz)")
            else:
                print(f"    无数据 (错误: {read_errors})")

            endpoint_reads.append(result)

            try:
                usb.util.release_interface(dev, iface_num)
            except Exception:
                pass

    report["interrupt_reads"] = endpoint_reads


def try_control_transfer_activate(dev, interfaces, report):
    """通过 USB 控制传输尝试激活 IMU"""
    print("\n" + "=" * 60)
    print("USB 控制传输激活尝试")
    print("=" * 60)

    control_results = []

    # 针对每个 HID 接口尝试 SET_REPORT 控制传输
    for iface_info in interfaces:
        if iface_info["bInterfaceClass"] != 3:
            continue

        iface_num = iface_info["bInterfaceNumber"]
        print(f"\n  接口 {iface_num}:")

        commands = [
            # (name, report_type, report_id, data)
            ("SET Output Report ID=0x00, enable",
             HID_REPORT_TYPE_OUTPUT, 0x00, [0x02, 0x19, 0x01]),
            ("SET Output Report ID=0x00, sensor on",
             HID_REPORT_TYPE_OUTPUT, 0x00, [0x01, 0x01]),
            ("SET Feature Report ID=0x02, enable",
             HID_REPORT_TYPE_FEATURE, 0x02, [0x02, 0x01]),
            ("SET Feature Report ID=0x01, enable",
             HID_REPORT_TYPE_FEATURE, 0x01, [0x01, 0x01]),
            ("SET Output Report ID=0x42, query",
             HID_REPORT_TYPE_OUTPUT, 0x42, [0x42, 0x01]),
            # 尝试 Meizu/StarV 特定命令
            ("SET Output Report ID=0x00, meizu cmd1",
             HID_REPORT_TYPE_OUTPUT, 0x00, [0x42, 0x01, 0x01]),
            ("SET Output Report ID=0x00, meizu imu start",
             HID_REPORT_TYPE_OUTPUT, 0x00, [0x42, 0x02, 0x01]),
            ("SET Output Report ID=0x00, meizu sensor enable",
             HID_REPORT_TYPE_OUTPUT, 0x00, [0x53, 0x01]),
            ("SET Output Report ID=0x00, meizu stream",
             HID_REPORT_TYPE_OUTPUT, 0x00, [0x49, 0x01, 0x01]),
        ]

        for name, rtype, rid, data in commands:
            try:
                # SET_REPORT: bmRequestType=0x21 (Host-to-device, Class, Interface)
                # wValue = (report_type << 8) | report_id
                dev.ctrl_transfer(
                    0x21,           # bmRequestType
                    HID_SET_REPORT, # bRequest
                    (rtype << 8) | rid,  # wValue
                    iface_num,      # wIndex
                    bytes(data),    # data
                    timeout=2000
                )
                status = "OK"
            except usb.core.USBError as e:
                status = f"错误: {e}"

            # 检查是否有数据开始流入
            time.sleep(0.2)
            response_count = 0
            sample = None
            for ep_info in iface_info["endpoints"]:
                if ep_info["direction"] != "IN":
                    continue
                ep_addr = int(ep_info["bEndpointAddress"], 16)
                for _ in range(20):
                    try:
                        resp = dev.read(ep_addr, ep_info["wMaxPacketSize"], timeout=30)
                        if resp and len(resp) > 0:
                            response_count += 1
                            if sample is None:
                                sample = " ".join(f"{b:02x}" for b in resp)
                    except (usb.core.USBTimeoutError, usb.core.USBError):
                        break

            entry = {
                "interface": iface_num,
                "name": name,
                "report_type": rtype,
                "report_id": f"0x{rid:02X}",
                "data": " ".join(f"{b:02x}" for b in data),
                "status": status,
                "responses": response_count,
                "sample": sample,
            }
            control_results.append(entry)

            resp_str = f", {response_count} 响应" if response_count else ""
            print(f"    [{name}] {status}{resp_str}")

    report["control_transfers"] = control_results


def try_get_reports_via_control(dev, interfaces, report):
    """通过控制传输 GET_REPORT 读取所有可能的 Input/Feature Report"""
    print("\n" + "=" * 60)
    print("GET_REPORT 控制传输扫描")
    print("=" * 60)

    get_results = []

    for iface_info in interfaces:
        if iface_info["bInterfaceClass"] != 3:
            continue

        iface_num = iface_info["bInterfaceNumber"]
        print(f"\n  接口 {iface_num}:")

        for rtype, rtype_name in [(HID_REPORT_TYPE_INPUT, "Input"),
                                   (HID_REPORT_TYPE_FEATURE, "Feature")]:
            found = 0
            for rid in range(0, 256):
                try:
                    data = dev.ctrl_transfer(
                        0xA1,           # bmRequestType: IN, Class, Interface
                        HID_GET_REPORT, # bRequest
                        (rtype << 8) | rid,  # wValue
                        iface_num,      # wIndex
                        256,            # wLength
                        timeout=500
                    )
                    if data and len(data) > 0:
                        found += 1
                        hex_str = " ".join(f"{b:02x}" for b in data)
                        get_results.append({
                            "interface": iface_num,
                            "type": rtype_name,
                            "report_id": f"0x{rid:02X}",
                            "length": len(data),
                            "data": hex_str,
                        })
                        print(f"    {rtype_name} Report 0x{rid:02X}: ({len(data)}B) {hex_str[:80]}")
                except usb.core.USBError:
                    pass

            if found == 0:
                print(f"    {rtype_name} Report: 无")

    report["get_reports"] = get_results


def usb_class_name(cls):
    names = {
        0: "Per-Interface", 1: "Audio", 2: "CDC", 3: "HID",
        5: "Physical", 6: "Image", 7: "Printer", 8: "Mass Storage",
        9: "Hub", 10: "CDC-Data", 11: "Smart Card", 13: "Content Security",
        14: "Video", 15: "Personal Healthcare", 16: "Audio/Video",
        0xDC: "Diagnostic", 0xE0: "Wireless", 0xEF: "Miscellaneous",
        0xFE: "Application Specific", 0xFF: "Vendor Specific",
    }
    return names.get(cls, f"Unknown(0x{cls:02X})")


def endpoint_type_name(attrs):
    types = {0: "Control", 1: "Isochronous", 2: "Bulk", 3: "Interrupt"}
    return types.get(attrs & 0x03, "Unknown")


def main():
    print(f"StarV View USB 原始探测 (VID=0x{VID:04X} PID=0x{PID:04X})")
    print("=" * 60)

    report = {
        "timestamp": datetime.now().isoformat(),
        "vid": f"0x{VID:04X}",
        "pid": f"0x{PID:04X}",
        "phase": "raw_usb_probe",
    }

    dev = find_device()
    if dev is None:
        print("\n未找到设备！")
        print("可能原因：")
        print("  1. 眼镜未连接")
        print("  2. libusb 未安装：pip install libusb")
        print("  3. Windows 需要 WinUSB/libusb 驱动（见下方说明）")
        print("\n  Windows 驱动替换方法（使用 Zadig）：")
        print("    1. 下载 Zadig: https://zadig.akeo.ie/")
        print("    2. 菜单 Options → List All Devices")
        print("    3. 找到 StarV View 的接口")
        print("    4. 选择 WinUSB 或 libusb-win32 驱动")
        print("    5. 点 Replace Driver")
        print("    ⚠ 注意：替换驱动后 hidapi 将无法访问该接口")
        print("    建议只替换接口 4 或 5 的驱动做测试")
        report["error"] = "设备未找到"
        save_report(report)
        sys.exit(1)

    print(f"\n找到设备!")

    # Step 1: 设备描述符
    print("\n" + "=" * 60)
    print("设备描述符")
    print("=" * 60)
    dump_device_descriptor(dev, report)

    # Step 2: 所有接口和端点
    print("\n" + "=" * 60)
    print("接口和端点枚举")
    print("=" * 60)
    interfaces = dump_all_interfaces(dev, report)

    # Step 3: HID Report Descriptor
    get_hid_report_descriptors(dev, interfaces, report)

    # Step 4: GET_REPORT 控制传输扫描
    try_get_reports_via_control(dev, interfaces, report)

    # Step 5: 控制传输激活
    try_control_transfer_activate(dev, interfaces, report)

    # Step 6: Interrupt IN 直接读取
    try_interrupt_reads(dev, interfaces, report)

    save_report(report)


def save_report(report):
    report_file = f"raw_probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"原始 USB 探测报告已保存到: {report_file}")
    print(f"请将此文件发送给开发者分析。")


if __name__ == "__main__":
    main()
