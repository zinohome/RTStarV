#!/usr/bin/env python3
"""
全面探测 StarV View 的 USB HID 接口。

功能：
  1. 尝试打开所有与 StarV View VID/PID 匹配的接口
  2. 对每个接口发送已知的 AR 眼镜 IMU 激活指令
  3. 记录所有响应数据
  4. 生成探测报告

用法：
  1. 先修改 VID 和 PID
  2. 运行：python usb_probe.py
  3. 将输出发给开发者分析
"""

import hid
import sys
import time
import json
from datetime import datetime

# ============================================
# >>> 请填入 usb_enumerate.py 找到的实际值 <<<
VID = 0x0000
PID = 0x0000
# ============================================

# 已知的 AR 眼镜 IMU 激活指令（来自 Xreal/Rokid/其他逆向工程）
ACTIVATE_SEQUENCES = [
    {"name": "Xreal style",        "data": bytes([0x00, 0x02, 0x19, 0x01])},
    {"name": "Xreal alt",          "data": bytes([0x02, 0x19, 0x01])},
    {"name": "Rokid style",        "data": bytes([0x00, 0x02, 0x01])},
    {"name": "Generic enable 1",   "data": bytes([0x00, 0x01, 0x01])},
    {"name": "Generic enable 2",   "data": bytes([0x00, 0x01])},
    {"name": "Feature report 1",   "data": bytes([0x01])},
    {"name": "Start stream",       "data": bytes([0x00, 0xAA, 0x01])},
    {"name": "Sensor on",          "data": bytes([0x00, 0x01, 0x00, 0x01])},
]

def probe_interface(path, iface_num, report):
    """探测单个 HID 接口"""
    result = {
        "interface": iface_num,
        "path": path.decode() if isinstance(path, bytes) else str(path),
        "passive_data": [],
        "activate_results": [],
    }

    device = hid.device()
    try:
        device.open_path(path)
    except IOError as e:
        result["error"] = f"无法打开: {e}"
        report["interfaces"].append(result)
        return

    device.set_nonblocking(True)

    # Phase 1: 被动监听 2 秒，看是否有数据自动推送
    print(f"\n  接口 {iface_num}: 被动监听 2 秒...")
    passive_packets = 0
    t0 = time.time()
    while time.time() - t0 < 2.0:
        data = device.read(256)
        if data:
            passive_packets += 1
            if passive_packets <= 5:
                result["passive_data"].append({
                    "time": round(time.time() - t0, 3),
                    "hex": " ".join(f"{b:02x}" for b in data),
                    "length": len(data),
                })
        else:
            time.sleep(0.001)

    print(f"    被动监听: {passive_packets} 个数据包")

    if passive_packets > 10:
        result["passive_rate_hz"] = round(passive_packets / 2.0, 1)
        print(f"    频率: ~{result['passive_rate_hz']} Hz — 可能已找到 IMU 数据流!")
        device.close()
        report["interfaces"].append(result)
        return

    # Phase 2: 尝试发送激活指令
    print(f"    尝试激活指令...")
    for seq in ACTIVATE_SEQUENCES:
        try:
            written = device.write(seq["data"])
        except IOError as e:
            result["activate_results"].append({
                "name": seq["name"],
                "sent": " ".join(f"{b:02x}" for b in seq["data"]),
                "error": str(e),
            })
            continue

        time.sleep(0.3)

        responses = []
        for _ in range(100):
            data = device.read(256)
            if data:
                responses.append(" ".join(f"{b:02x}" for b in data))
            else:
                break
            time.sleep(0.001)

        activate_result = {
            "name": seq["name"],
            "sent": " ".join(f"{b:02x}" for b in seq["data"]),
            "written": written,
            "responses": responses[:5],
            "total_responses": len(responses),
        }
        result["activate_results"].append(activate_result)

        if responses:
            print(f"    [{seq['name']}] -> {len(responses)} 个响应!")
        else:
            print(f"    [{seq['name']}] -> 无响应")

    # Phase 3: 再次被动监听 2 秒（激活指令可能已生效）
    print(f"    激活后监听 2 秒...")
    post_packets = 0
    post_data = []
    t0 = time.time()
    while time.time() - t0 < 2.0:
        data = device.read(256)
        if data:
            post_packets += 1
            if post_packets <= 5:
                post_data.append(" ".join(f"{b:02x}" for b in data))
        else:
            time.sleep(0.001)

    if post_packets > 0:
        result["post_activate_rate_hz"] = round(post_packets / 2.0, 1)
        result["post_activate_samples"] = post_data
        print(f"    激活后: {post_packets} 个数据包 (~{result['post_activate_rate_hz']} Hz)")

    device.close()
    report["interfaces"].append(result)


def main():
    if VID == 0x0000 or PID == 0x0000:
        print("错误：请先修改脚本中的 VID 和 PID 值！")
        sys.exit(1)

    report = {
        "timestamp": datetime.now().isoformat(),
        "vid": f"0x{VID:04X}",
        "pid": f"0x{PID:04X}",
        "interfaces": [],
    }

    print(f"StarV View 全面探测 (VID=0x{VID:04X} PID=0x{PID:04X})")
    print("=" * 60)

    # 找到所有匹配的接口
    all_devices = hid.enumerate(VID, PID)
    if not all_devices:
        print("未找到设备！请确认眼镜已连接且 VID/PID 正确。")
        sys.exit(1)

    print(f"找到 {len(all_devices)} 个匹配接口")

    for d in all_devices:
        iface = d.get('interface_number', -1)
        path = d['path']
        prod = d.get('product_string', '') or '(unknown)'
        print(f"\n接口 {iface}: {prod}")
        print(f"  Usage Page: 0x{d.get('usage_page', 0):04X}")
        print(f"  Usage:      0x{d.get('usage', 0):04X}")
        probe_interface(path, iface, report)

    # 保存报告
    report_file = f"probe_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"探测报告已保存到: {report_file}")
    print(f"请将此文件发送给开发者分析。")

if __name__ == "__main__":
    main()
