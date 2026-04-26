#!/usr/bin/env python3
"""
第五轮探测：基于精确逆向的 IMU 启用命令

从 libsv_hid.so 逆向确认的命令格式：
  cmd 0x6d (sv_hid_open_hid_data) 的 8 字节包：

  byte[0] = 0x42          (magic)
  byte[1] = checksum_high  (sum of byte[3..6] >> 8)
  byte[2] = checksum_low   (sum of byte[3..6] & 0xFF)
  byte[3] = 0x06          (路由)
  byte[4] = 0x03          (路由)
  byte[5] = 0x07          (路由)
  byte[6] = enable_flag   (0x01=开启, 0x00=关闭)
  byte[7] = 0xFF          (终止符)

  校验和: 0x06+0x03+0x07+0x01 = 0x11
  完整包: 42 00 11 06 03 07 01 FF

依赖：pip install hidapi
"""

import sys
import time
import struct
import json
from datetime import datetime

try:
    import hid
except ImportError:
    print("错误：需要安装 hidapi")
    print("  pip install hidapi")
    sys.exit(1)

VID = 0x2A45
PID = 0x2050


def calculate_crc(data, start, length):
    """复现 libsv_hid.so 中的 calculate_crc 函数"""
    s = 0
    for i in range(start, start + length):
        s = (s + data[i]) & 0xFFFF
    return (s >> 8) & 0xFF, s & 0xFF


def build_imu_enable_cmd():
    """构建 IMU 启用命令 (cmd 0x6d)"""
    buf = bytearray(64)
    buf[0] = 0x42   # magic
    buf[3] = 0x06   # routing
    buf[4] = 0x03   # routing
    buf[5] = 0x07   # routing
    buf[6] = 0x01   # enable = 1
    buf[7] = 0xFF   # terminator
    buf[1], buf[2] = calculate_crc(buf, 3, 4)
    return bytes(buf)


def build_imu_disable_cmd():
    """构建 IMU 禁用命令"""
    buf = bytearray(64)
    buf[0] = 0x42
    buf[3] = 0x06
    buf[4] = 0x03
    buf[5] = 0x07
    buf[6] = 0x00   # enable = 0
    buf[7] = 0xFF
    buf[1], buf[2] = calculate_crc(buf, 3, 4)
    return bytes(buf)


def hexdump(data, n=64):
    return " ".join(f"{b:02x}" for b in data[:n])


def classify_packet(data):
    if len(data) < 6 or data[0] != 0x42:
        return "non_starv"
    cat, sub = data[4], data[5]
    if cat == 0x01 and sub == 0x06:
        return "IMU_9DOF"
    elif cat == 0x01 and sub == 0x02:
        return "IMU_6DOF"
    elif cat == 0x01 and sub == 0x07:
        return "LOG_MSG"
    elif cat == 0x07 and sub == 0x01:
        return "IMU_VARIANT_C"
    elif cat == 0x07 and sub == 0x02:
        return "IMU_VARIANT_B"
    elif cat == 0x07 and sub == 0x03:
        return "IMU_EXTENDED"
    elif cat == 0x08 and sub == 0x04:
        return "CMD_RESPONSE"
    elif cat == 0x29 and sub == 0x01:
        return "EXTENDED_DATA"
    else:
        return f"OTHER(0x{cat:02X},0x{sub:02X})"


def is_imu_data(cls):
    return cls in ("IMU_9DOF", "IMU_6DOF", "IMU_VARIANT_B", "IMU_VARIANT_C", "IMU_EXTENDED")


def try_float32_at(data, offset):
    if offset + 24 > len(data):
        return None
    values = struct.unpack_from("<6f", data, offset)
    labels = ["acc_x", "acc_y", "acc_z", "gyr_x", "gyr_y", "gyr_z"]
    return dict(zip(labels, values))


def is_plausible_imu(vals):
    if not vals:
        return False
    acc = [vals[f"acc_{a}"] for a in "xyz"]
    mag = sum(a * a for a in acc) ** 0.5
    has_nan = any(v != v for v in vals.values())
    has_inf = any(abs(v) > 1e30 for v in vals.values())
    return 3.0 < mag < 20.0 and not has_nan and not has_inf


def read_packets(h, duration_s):
    packets = []
    t0 = time.time()
    while time.time() - t0 < duration_s:
        data = h.read(64)
        if data:
            packets.append({"time": round(time.time() - t0, 4), "data": bytes(data)})
        else:
            time.sleep(0.001)
    return packets


def drain(h):
    for _ in range(200):
        if not h.read(64):
            break


def open_interface(devices, iface):
    for d in devices:
        if d.get("interface_number") == iface:
            h = hid.device()
            try:
                h.open_path(d["path"])
                h.set_nonblocking(1)
                return h
            except Exception as e:
                print(f"  无法打开接口 {iface}: {e}")
    return None


def analyze_imu_stream(packets, report):
    """分析 IMU 数据流"""
    imu_types = {}
    for pkt in packets:
        cls = classify_packet(pkt["data"])
        imu_types[cls] = imu_types.get(cls, 0) + 1

    print(f"\n  数据包分类:")
    for cls, count in sorted(imu_types.items(), key=lambda x: -x[1]):
        print(f"    {cls}: {count}")

    # 挑选 IMU 数据包
    imu_pkts = [p for p in packets if is_imu_data(classify_packet(p["data"]))]
    if not imu_pkts:
        imu_pkts = [p for p in packets if p["data"][0] == 0x42
                     and classify_packet(p["data"]) not in ("LOG_MSG", "EXTENDED_DATA", "CMD_RESPONSE")]

    if not imu_pkts:
        print("  未检测到 IMU 数据包")
        report["imu_found"] = False
        return

    print(f"\n  IMU 数据包: {len(imu_pkts)} 个")
    report["imu_found"] = True
    report["imu_count"] = len(imu_pkts)

    # Hexdump 前 10 个
    print(f"\n  前 10 个 IMU 数据包 hexdump:")
    samples = []
    for i, pkt in enumerate(imu_pkts[:10]):
        d = pkt["data"]
        cls = classify_packet(d)
        print(f"  #{i:2d} [{pkt['time']:.3f}s] {cls:15s} {hexdump(d)}")
        samples.append({"time": pkt["time"], "type": cls, "hex": hexdump(d)})
    report["imu_samples"] = samples

    # 尝试 float32 解码
    print(f"\n  float32 解码尝试:")
    found_offset = None
    for pkt in imu_pkts[:5]:
        d = pkt["data"]
        for off in range(6, 40, 2):
            vals = try_float32_at(d, off)
            if vals and is_plausible_imu(vals):
                if found_offset is None:
                    found_offset = off
                    print(f"    *** 合理的 IMU 数据 @ offset {off} ***")
                    for k, v in vals.items():
                        print(f"      {k}: {v:12.6f}")
                break

    if found_offset is None:
        print("    无匹配（数据可能不是 float32，或偏移未覆盖）")
        # 打印所有候选
        for off in [6, 8, 10, 12]:
            d = imu_pkts[0]["data"]
            vals = try_float32_at(d, off)
            if vals:
                print(f"    @ offset {off}: " +
                      ", ".join(f"{v:.4f}" for v in vals.values()))
    else:
        report["float32_offset"] = found_offset

    # 采样率估算
    if len(imu_pkts) > 5:
        intervals = [imu_pkts[i]["time"] - imu_pkts[i-1]["time"]
                     for i in range(1, len(imu_pkts)) if
                     imu_pkts[i]["time"] > imu_pkts[i-1]["time"]]
        if intervals:
            avg = sum(intervals) / len(intervals)
            hz = 1.0 / avg if avg > 0 else 0
            print(f"\n  估算采样率: ~{hz:.0f} Hz")
            report["sample_rate_hz"] = round(hz, 1)


def main():
    print(f"StarV View IMU 精确激活 (VID=0x{VID:04X} PID=0x{PID:04X})")
    print(f"时间: {datetime.now().isoformat()}")
    print("=" * 60)

    cmd_enable = build_imu_enable_cmd()
    cmd_disable = build_imu_disable_cmd()
    print(f"IMU 启用命令: {hexdump(cmd_enable, 8)}")
    print(f"IMU 禁用命令: {hexdump(cmd_disable, 8)}")

    report = {
        "timestamp": datetime.now().isoformat(),
        "phase": "imu_activate_v2_precise",
        "enable_cmd": hexdump(cmd_enable, 8),
        "disable_cmd": hexdump(cmd_disable, 8),
    }

    devices = hid.enumerate(VID, PID)
    if not devices:
        print("\n未找到设备！")
        report["error"] = "设备未找到"
        save_report(report)
        sys.exit(1)

    print(f"\n找到 {len(devices)} 个 HID 接口:")
    for d in devices:
        iface = d.get("interface_number", -1)
        print(f"  接口 {iface}: usage_page=0x{d.get('usage_page',0):04X} "
              f"product={d.get('product_string','')}")

    # 在接口 3 和 4 上尝试
    for iface_num in [3, 4]:
        print(f"\n{'=' * 60}")
        print(f"接口 {iface_num}")
        print("=" * 60)

        h = open_interface(devices, iface_num)
        if h is None:
            print(f"  跳过接口 {iface_num}")
            continue

        try:
            # Step 1: 清空缓冲区
            drain(h)

            # Step 2: 发送 IMU 启用命令
            print(f"\n  发送 IMU 启用命令: {hexdump(cmd_enable, 8)}")
            try:
                written = h.write(b'\x00' + cmd_enable)
                print(f"  写入: {written} 字节")
            except Exception as e:
                print(f"  写入失败: {e}")
                report[f"iface{iface_num}_error"] = str(e)
                continue

            # Step 3: 等待 500ms 让设备响应
            time.sleep(0.5)

            # Step 4: 读取 10 秒数据
            print(f"\n  读取数据 (10秒)...")
            packets = read_packets(h, 10.0)
            print(f"  共收到 {len(packets)} 个数据包")

            if packets:
                report[f"iface{iface_num}_total_packets"] = len(packets)
                analyze_imu_stream(packets, report)

                # 保存所有原始数据包用于离线分析
                report[f"iface{iface_num}_all_packets"] = [
                    {"time": p["time"], "hex": hexdump(p["data"])}
                    for p in packets[:200]
                ]
            else:
                print("  无数据")
                report[f"iface{iface_num}_total_packets"] = 0

            # Step 5: 发送禁用命令
            print(f"\n  发送 IMU 禁用命令...")
            try:
                h.write(b'\x00' + cmd_disable)
            except Exception:
                pass

        finally:
            h.close()

    save_report(report)


def save_report(report):
    filename = f"imu_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n{'=' * 60}")
    print(f"报告已保存: {filename}")
    print("请将此文件发回分析。")


if __name__ == "__main__":
    main()
