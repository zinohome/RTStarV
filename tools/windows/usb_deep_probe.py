#!/usr/bin/env python3
"""
深度探测 StarV View 的 USB 接口。

在首轮探测基础上进一步分析：
  1. 读取每个接口的 HID Report Descriptor
  2. 尝试 Feature Report 读写（上次 output report 写入失败的接口 5）
  3. 尝试不同 Report ID 的 Input Report 读取
  4. 对接口 3 的状态响应做更多分析
  5. 长时间监听接口 5，看是否有延迟数据流

用法：
  python usb_deep_probe.py
"""

import hid
import sys
import time
import json
from datetime import datetime

VID = 0x2A45
PID = 0x2050

def probe_feature_reports(device, iface_num, result):
    """尝试读取所有可能的 Feature Report（Report ID 0x00-0xFF）"""
    print(f"\n  [{iface_num}] 探测 Feature Report...")
    found_reports = []

    for report_id in range(0x00, 0x100):
        try:
            data = device.get_feature_report(report_id, 256)
            if data and len(data) > 0:
                hex_str = " ".join(f"{b:02x}" for b in data[:32])
                if len(data) > 32:
                    hex_str += f" ... ({len(data)} bytes total)"
                found_reports.append({
                    "report_id": f"0x{report_id:02X}",
                    "length": len(data),
                    "data": " ".join(f"{b:02x}" for b in data),
                })
                print(f"    Report 0x{report_id:02X}: ({len(data)}B) {hex_str}")
        except IOError:
            pass

    result["feature_reports"] = found_reports
    print(f"    共找到 {len(found_reports)} 个 Feature Report")


def probe_input_reports(device, iface_num, result):
    """尝试读取带不同 Report ID 的 Input Report"""
    print(f"\n  [{iface_num}] 探测 Input Report...")

    device.set_nonblocking(True)
    packets = []
    t0 = time.time()

    # 先监听 3 秒
    while time.time() - t0 < 3.0:
        data = device.read(256)
        if data:
            packets.append({
                "time": round(time.time() - t0, 4),
                "data": " ".join(f"{b:02x}" for b in data),
                "length": len(data),
            })
        else:
            time.sleep(0.001)

    result["input_reports"] = packets[:20]
    result["input_report_count"] = len(packets)
    if packets:
        rate = len(packets) / 3.0
        result["input_report_rate_hz"] = round(rate, 1)
        print(f"    收到 {len(packets)} 个 Input Report (~{rate:.1f} Hz)")
    else:
        print(f"    无 Input Report")


def probe_set_feature_activate(device, iface_num, result):
    """尝试通过 Set Feature Report 激活 IMU"""
    print(f"\n  [{iface_num}] 尝试 Feature Report 激活...")

    activate_sequences = [
        {"name": "Feature ID=0x02 enable",   "data": [0x02, 0x01]},
        {"name": "Feature ID=0x02 stream",   "data": [0x02, 0x19, 0x01]},
        {"name": "Feature ID=0x01 enable",   "data": [0x01, 0x01]},
        {"name": "Feature ID=0x01 stream",   "data": [0x01, 0x01, 0x01]},
        {"name": "Feature ID=0x03 enable",   "data": [0x03, 0x01]},
        {"name": "Feature ID=0x0A enable",   "data": [0x0A, 0x01]},
        {"name": "Feature ID=0x42 query",    "data": [0x42, 0x01]},
        {"name": "Feature ID=0x42 enable",   "data": [0x42, 0x01, 0x01]},
    ]

    results_list = []
    for seq in activate_sequences:
        try:
            written = device.send_feature_report(bytes(seq["data"]))
            time.sleep(0.3)

            # 检查是否有数据流开始
            device.set_nonblocking(True)
            responses = []
            for _ in range(200):
                data = device.read(256)
                if data:
                    responses.append(" ".join(f"{b:02x}" for b in data))
                else:
                    break
                time.sleep(0.001)

            entry = {
                "name": seq["name"],
                "sent": " ".join(f"{b:02x}" for b in seq["data"]),
                "written": written,
                "responses": responses[:5],
                "total_responses": len(responses),
            }
            results_list.append(entry)

            status = f"{len(responses)} 响应" if responses else "无响应"
            print(f"    [{seq['name']}] wrote={written}, {status}")

        except IOError as e:
            results_list.append({
                "name": seq["name"],
                "sent": " ".join(f"{b:02x}" for b in seq["data"]),
                "error": str(e),
            })
            print(f"    [{seq['name']}] 错误: {e}")

    result["feature_activate"] = results_list


def probe_interface3_status(device, result):
    """深入分析接口 3 的状态响应"""
    print(f"\n  [3] 深入分析状态响应...")

    # 发送不同的指令看响应是否变化
    test_commands = [
        {"name": "all zeros",     "data": bytes(64)},
        {"name": "query info",    "data": bytes([0x00, 0x42])},
        {"name": "query version", "data": bytes([0x00, 0x56])},
        {"name": "query sensor",  "data": bytes([0x00, 0x53])},
        {"name": "IMU config",    "data": bytes([0x00, 0x49, 0x01])},
    ]

    results_list = []
    for cmd in test_commands:
        try:
            device.write(cmd["data"])
            time.sleep(0.1)
            device.set_nonblocking(True)
            data = device.read(256)
            hex_str = " ".join(f"{b:02x}" for b in data) if data else "(none)"
            entry = {
                "name": cmd["name"],
                "sent": " ".join(f"{b:02x}" for b in cmd["data"][:8]),
                "response": hex_str,
                "length": len(data) if data else 0,
            }
            results_list.append(entry)
            print(f"    [{cmd['name']}] -> {hex_str[:60]}...")
        except IOError as e:
            results_list.append({"name": cmd["name"], "error": str(e)})
            print(f"    [{cmd['name']}] 错误: {e}")

    result["status_analysis"] = results_list


def main():
    report = {
        "timestamp": datetime.now().isoformat(),
        "vid": f"0x{VID:04X}",
        "pid": f"0x{PID:04X}",
        "phase": "deep_probe",
        "interfaces": [],
    }

    print(f"StarV View 深度探测 (VID=0x{VID:04X} PID=0x{PID:04X})")
    print("=" * 60)

    all_devices = hid.enumerate(VID, PID)
    if not all_devices:
        print("未找到设备！")
        sys.exit(1)

    print(f"找到 {len(all_devices)} 个接口")

    for d in all_devices:
        iface = d.get('interface_number', -1)
        path = d['path']
        result = {"interface": iface, "path": path.decode() if isinstance(path, bytes) else str(path)}

        print(f"\n{'=' * 60}")
        print(f"接口 {iface}")
        print(f"  Usage Page: 0x{d.get('usage_page', 0):04X}")
        print(f"  Usage:      0x{d.get('usage', 0):04X}")

        device = hid.device()
        try:
            device.open_path(path)
        except IOError as e:
            result["error"] = f"无法打开: {e}"
            report["interfaces"].append(result)
            print(f"  无法打开: {e}")
            continue

        # 所有接口都做 Feature Report 探测
        probe_feature_reports(device, iface, result)

        # 所有接口都尝试 Feature Report 激活
        probe_set_feature_activate(device, iface, result)

        # 激活后监听 Input Report
        probe_input_reports(device, iface, result)

        # 接口 3 额外做状态分析
        if iface == 3:
            probe_interface3_status(device, result)

        device.close()
        report["interfaces"].append(result)

    # 保存报告
    report_file = f"deep_probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"深度探测报告已保存到: {report_file}")
    print(f"请将此文件发送给开发者分析。")

if __name__ == "__main__":
    main()
