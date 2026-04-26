#!/usr/bin/env python3
"""
备用探测：通过 Windows HID API 获取 Report Descriptor 和更多信息。

如果 usb_raw_probe.py 因为驱动问题无法运行，用这个脚本。
不需要 libusb，只用 hidapi + ctypes 调用 Windows HID API。

目标：
  1. 获取每个接口的 Preparsed Data / Report Descriptor 信息
  2. 用不同的 Output Report 格式组合尝试激活
  3. 长时间监听接口 5（30 秒），看是否有延迟响应
  4. 分析接口 3 的状态字节含义

依赖：
  pip install hidapi

用法：
  python hid_descriptor_probe.py
"""

import hid
import sys
import time
import json
import ctypes
from datetime import datetime

VID = 0x2A45
PID = 0x2050


def probe_interface3_protocol(device, result):
    """
    接口 3 会对 output report 返回 64 字节状态包。
    系统地变化每个字节，观察响应变化，推断协议结构。
    """
    print(f"\n  [3] 协议逆向分析...")

    # 已知响应模式：
    # 发 00*64        -> 42 00 75 08 29 01 00 00 01 ff 00...
    # 发 00 42        -> 42 00 7b 08 29 01 00 00 07 ff 00...
    # 字节 2: 0x75 vs 0x7b, 字节 8: 0x01 vs 0x07

    # 策略：以 0x42 为基础（它引起了变化），系统地变化后续字节
    commands = []

    # 1. 单字节命令扫描：发送 [0x00, X] 其中 X 从 0x00 到 0xFF
    #    看哪些命令 ID 引起不同响应
    print("    Phase 1: 命令 ID 扫描 (0x00-0xFF)...")
    baseline = None
    interesting_cmds = []

    for cmd_id in range(0x100):
        buf = bytearray(65)  # Report ID 0x00 + 64 bytes
        buf[0] = 0x00  # Report ID
        buf[1] = cmd_id
        try:
            device.write(bytes(buf))
            time.sleep(0.02)
            device.set_nonblocking(True)
            resp = device.read(256)
            if resp:
                if baseline is None and cmd_id == 0:
                    baseline = list(resp)
                if baseline and list(resp) != baseline:
                    hex_resp = " ".join(f"{b:02x}" for b in resp[:16])
                    interesting_cmds.append({
                        "cmd_id": f"0x{cmd_id:02X}",
                        "response_prefix": hex_resp,
                        "diff_bytes": find_diff_bytes(baseline, list(resp)),
                    })
                    print(f"      CMD 0x{cmd_id:02X}: 响应不同! {hex_resp}")
        except IOError:
            pass

    if baseline:
        result["baseline_response"] = " ".join(f"{b:02x}" for b in baseline[:16])
    result["interesting_commands"] = interesting_cmds
    print(f"    发现 {len(interesting_cmds)} 个引起不同响应的命令")

    # 2. 对有响应变化的命令，逐字节探测子命令
    print("\n    Phase 2: 子命令探测...")
    subcmd_results = []

    for cmd in interesting_cmds[:5]:  # 最多探测 5 个
        cmd_id = int(cmd["cmd_id"], 16)
        print(f"      CMD 0x{cmd_id:02X} 子命令扫描...")

        for sub in range(0x100):
            buf = bytearray(65)
            buf[0] = 0x00
            buf[1] = cmd_id
            buf[2] = sub
            try:
                device.write(bytes(buf))
                time.sleep(0.02)
                device.set_nonblocking(True)
                resp = device.read(256)
                if resp and baseline and list(resp) != baseline:
                    # 检查是否和只发 cmd_id 时不同
                    hex_resp = " ".join(f"{b:02x}" for b in resp[:16])
                    subcmd_results.append({
                        "cmd": f"0x{cmd_id:02X}",
                        "sub": f"0x{sub:02X}",
                        "response_prefix": hex_resp,
                    })
            except IOError:
                pass

    result["subcmd_results"] = subcmd_results[:50]  # 最多保存 50 条
    print(f"    发现 {len(subcmd_results)} 个有效子命令组合")


def probe_interface5_long_listen(path, result):
    """接口 5 在首轮探测中有短暂响应，长时间监听看是否有数据"""
    print(f"\n  [5] 长时间监听 (30 秒)...")

    device = hid.device()
    try:
        device.open_path(path)
    except IOError as e:
        result["long_listen_error"] = str(e)
        print(f"    无法打开: {e}")
        return

    device.set_nonblocking(True)

    packets = []
    t0 = time.time()
    while time.time() - t0 < 30.0:
        data = device.read(256)
        if data:
            packets.append({
                "time": round(time.time() - t0, 4),
                "data": " ".join(f"{b:02x}" for b in data),
                "length": len(data),
            })
        else:
            time.sleep(0.005)

    result["long_listen_packets"] = packets[:50]
    result["long_listen_total"] = len(packets)
    if packets:
        print(f"    收到 {len(packets)} 个数据包")
    else:
        print(f"    30 秒内无数据")

    # 尝试写入后监听
    print(f"  [5] 尝试写入后监听...")
    write_cmds = [
        ("Report ID=0", bytes([0x00, 0x02, 0x19, 0x01])),
        ("Report ID=1", bytes([0x01, 0x02, 0x19, 0x01])),
        ("Report ID=2", bytes([0x02, 0x19, 0x01])),
        ("Short 0x01", bytes([0x00, 0x01])),
        ("Meizu IMU", bytes([0x00, 0x42, 0x02, 0x01])),
    ]

    write_results = []
    for name, cmd in write_cmds:
        try:
            written = device.write(cmd)
            time.sleep(0.5)
            resps = []
            for _ in range(500):
                data = device.read(256)
                if data:
                    resps.append(" ".join(f"{b:02x}" for b in data))
                else:
                    break
                time.sleep(0.001)

            write_results.append({
                "name": name,
                "sent": " ".join(f"{b:02x}" for b in cmd),
                "written": written,
                "responses": resps[:5],
                "total": len(resps),
            })
            resp_str = f"{len(resps)} 响应" if resps else "无响应"
            print(f"    [{name}] written={written}, {resp_str}")
        except IOError as e:
            write_results.append({"name": name, "error": str(e)})
            print(f"    [{name}] 错误: {e}")

    result["interface5_write_results"] = write_results
    device.close()


def probe_all_report_ids_output(device, iface_num, result):
    """尝试不同 Report ID 的 Output Report"""
    print(f"\n  [{iface_num}] Output Report ID 扫描...")

    # HID Output Report 的第一个字节是 Report ID
    # 尝试每个 Report ID + 简单的 enable 命令
    found = []

    for rid in range(0x100):
        buf = bytearray(65)
        buf[0] = rid
        buf[1] = 0x01  # enable
        try:
            written = device.write(bytes(buf))
            if written > 0:
                time.sleep(0.02)
                device.set_nonblocking(True)
                resp = device.read(256)
                if resp:
                    found.append({
                        "report_id": f"0x{rid:02X}",
                        "written": written,
                        "response": " ".join(f"{b:02x}" for b in resp[:16]),
                    })
        except IOError:
            pass

    result[f"output_report_id_scan_{iface_num}"] = found
    print(f"    发现 {len(found)} 个有响应的 Report ID")


def find_diff_bytes(a, b):
    """找出两个字节列表的差异位置"""
    diffs = []
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            diffs.append({
                "offset": i,
                "baseline": f"0x{a[i]:02X}",
                "current": f"0x{b[i]:02X}",
            })
    return diffs


def main():
    print(f"StarV View HID 协议逆向探测 (VID=0x{VID:04X} PID=0x{PID:04X})")
    print("=" * 60)

    report = {
        "timestamp": datetime.now().isoformat(),
        "vid": f"0x{VID:04X}",
        "pid": f"0x{PID:04X}",
        "phase": "hid_protocol_probe",
    }

    all_devices = hid.enumerate(VID, PID)
    if not all_devices:
        print("未找到设备！")
        sys.exit(1)

    print(f"找到 {len(all_devices)} 个接口")

    iface5_path = None

    for d in all_devices:
        iface = d.get('interface_number', -1)
        path = d['path']

        if iface == 5:
            iface5_path = path

        if iface == 3:
            print(f"\n{'=' * 60}")
            print(f"接口 3: 协议逆向")
            device = hid.device()
            try:
                device.open_path(path)
                result = {"interface": 3}
                probe_interface3_protocol(device, result)
                probe_all_report_ids_output(device, 3, result)
                report["interface3"] = result
                device.close()
            except IOError as e:
                print(f"  无法打开: {e}")

        if iface == 4:
            print(f"\n{'=' * 60}")
            print(f"接口 4: Output Report ID 扫描")
            device = hid.device()
            try:
                device.open_path(path)
                result = {"interface": 4}
                probe_all_report_ids_output(device, 4, result)
                report["interface4"] = result
                device.close()
            except IOError as e:
                print(f"  无法打开: {e}")

    if iface5_path:
        print(f"\n{'=' * 60}")
        print(f"接口 5: 深度探测")
        result = {"interface": 5}
        probe_interface5_long_listen(iface5_path, result)
        report["interface5"] = result

    # 保存报告
    report_file = f"hid_protocol_probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"协议逆向探测报告已保存到: {report_file}")
    print(f"请将此文件发送给开发者分析。")


if __name__ == "__main__":
    main()
