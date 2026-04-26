#!/usr/bin/env python3
"""
第四轮探测：基于逆向工程结果，尝试激活 IMU 数据流。

已知信息（来自 libsv_hid.so 逆向）：
  - 设备通过接口 3 的 HID 通道可通信（deep_probe 已验证）
  - 所有数据包以 0x42 ('B') 开头
  - IMU 启用命令 ID = 0x6d (sv_hid_open_hid_data)
  - IMU 数据包特征: byte[0]=0x42, byte[4]=0x01
  - 传感器值为 float32 IEEE 754 编码

策略：
  1. 先被动监听（也许设备已经在发 IMU 数据）
  2. 尝试多种 cmd 0x6d 包格式发送到接口 3
  3. 每次发送后监听 IMU 数据包
  4. 找到 IMU 数据后，hexdump 并尝试 float32 解码

依赖：
  pip install hidapi
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

INTERFACES_TO_TRY = [3, 4, 5]


def enumerate_devices():
    """枚举所有 StarV View HID 接口"""
    print("枚举 StarV View HID 设备...")
    print("=" * 60)
    devices = hid.enumerate(VID, PID)
    if not devices:
        print("未找到设备！请确认眼镜已通过 USB 连接。")
        return []

    for d in devices:
        iface = d.get("interface_number", -1)
        path = d.get("path", b"").decode("utf-8", errors="replace")
        product = d.get("product_string", "")
        manufacturer = d.get("manufacturer_string", "")
        usage_page = d.get("usage_page", 0)
        usage = d.get("usage", 0)
        print(f"  接口 {iface}: usage_page=0x{usage_page:04X} usage=0x{usage:04X}")
        print(f"    产品: {manufacturer} {product}")
        print(f"    路径: {path[:80]}")
    print()
    return devices


def open_interface(devices, target_iface):
    """打开指定接口"""
    for d in devices:
        if d.get("interface_number") == target_iface:
            h = hid.device()
            try:
                h.open_path(d["path"])
                h.set_nonblocking(1)
                print(f"  已打开接口 {target_iface}")
                return h
            except Exception as e:
                print(f"  无法打开接口 {target_iface}: {e}")
                return None
    print(f"  接口 {target_iface} 不存在")
    return None


def read_packets(h, duration_s=2.0, label=""):
    """读取指定时间内的所有数据包"""
    packets = []
    t0 = time.time()
    while time.time() - t0 < duration_s:
        data = h.read(64)
        if data:
            packets.append({
                "time": round(time.time() - t0, 4),
                "data": bytes(data),
            })
        else:
            time.sleep(0.001)
    return packets


def classify_packet(data):
    """根据逆向工程的 dispatch table 分类数据包"""
    if len(data) < 6:
        return "too_short"
    if data[0] != 0x42:
        return f"non_starv(0x{data[0]:02X})"

    cat = data[4] if len(data) > 4 else 0
    sub = data[5] if len(data) > 5 else 0

    if cat == 0x01 and sub == 0x06:
        return "IMU_PRIMARY_9DOF"
    elif cat == 0x01 and sub == 0x02:
        return "IMU_PRIMARY_6DOF"
    elif cat == 0x01:
        return f"IMU_PRIMARY(sub=0x{sub:02X})"
    elif cat == 0x08 and sub == 0x04:
        return "CMD_RESPONSE_A"
    elif cat == 0x07:
        return f"IMU_EXTENDED(sub=0x{sub:02X})"
    elif cat == 0x06:
        return f"SENSOR_A(sub=0x{sub:02X})"
    elif cat == 0x02:
        return f"SENSOR_B(sub=0x{sub:02X})"
    elif cat == 0x29:
        return f"EXTENDED_DATA(sub=0x{sub:02X})"
    elif cat == 0x03:
        return f"CONFIG(sub=0x{sub:02X})"
    else:
        return f"UNKNOWN(cat=0x{cat:02X},sub=0x{sub:02X})"


def hexdump(data, max_bytes=64):
    """格式化十六进制输出"""
    return " ".join(f"{b:02x}" for b in data[:max_bytes])


def try_float32_decode(data, start_offset=8):
    """尝试从指定偏移开始解码 float32 值"""
    results = {}
    labels = ["acc_x", "acc_y", "acc_z", "gyr_x", "gyr_y", "gyr_z",
              "mag_x", "mag_y", "mag_z"]
    for i, label in enumerate(labels):
        off = start_offset + i * 4
        if off + 4 <= len(data):
            val = struct.unpack_from("<f", data, off)[0]
            results[label] = val
    return results


def is_plausible_imu(floats):
    """检查 float32 值是否像合理的 IMU 数据"""
    if not floats:
        return False

    acc_fields = [floats.get(f"acc_{a}", 0) for a in "xyz"]
    gyr_fields = [floats.get(f"gyr_{a}", 0) for a in "xyz"]

    # 加速度计：应有重力分量，即使运动中也在 3-20 m/s² 范围内
    acc_mag = sum(a * a for a in acc_fields) ** 0.5
    acc_ok = 3.0 < acc_mag < 20.0

    all_zero = all(abs(v) < 1e-30 for v in floats.values())
    has_nan = any(v != v for v in floats.values())
    has_inf = any(abs(v) > 1e30 for v in floats.values())

    return acc_ok and not all_zero and not has_nan and not has_inf


def build_cmd_0x6d_candidates():
    """构建 cmd 0x6d (IMU 启用) 的候选数据包格式

    基于逆向工程：
    - sv_hid_open_hid_data 调用 sv_hid_getHmdCmdData(ctx, 0x6d, buffer)
    - 数据包以 0x42 开头
    - 响应格式中 byte[3] 常为 0x08
    - enable flag = 1 放在某个偏移

    我们不确定命令包的确切布局，所以尝试多种候选格式。
    """
    candidates = []

    # === 基于 response 格式推测的命令格式 ===
    # 响应: 42 00 xx 08 29 01 ... 其中 byte[4]=category, byte[5]=sub

    # A: cmd_id 放在 byte[5] (sub_category 位置)，enable 在 byte[8]
    buf = bytearray(64)
    buf[0] = 0x42
    buf[4] = 0x01  # category
    buf[5] = 0x6d  # cmd_id as sub
    buf[8] = 0x01  # enable
    candidates.append(("A: cat=0x01 sub=0x6d enable@8", bytes(buf)))

    # B: cmd_id 放在 byte[4]，enable 在 byte[5]
    buf = bytearray(64)
    buf[0] = 0x42
    buf[4] = 0x6d  # cmd_id
    buf[5] = 0x01  # enable
    candidates.append(("B: cat=0x6d sub=0x01", bytes(buf)))

    # C: 使用观察到的 response 模式 42 00 xx 08
    buf = bytearray(64)
    buf[0] = 0x42
    buf[3] = 0x08
    buf[4] = 0x6d
    buf[5] = 0x01
    candidates.append(("C: 42 00 00 08 6d 01", bytes(buf)))

    # D: cmd_id 在 byte[1]
    buf = bytearray(64)
    buf[0] = 0x42
    buf[1] = 0x6d
    buf[2] = 0x01  # enable
    candidates.append(("D: 42 6d 01", bytes(buf)))

    # E: 模仿 Xreal Air 的简单格式（magic + cmd + arg）
    buf = bytearray(64)
    buf[0] = 0x42
    buf[1] = 0x00
    buf[2] = 0x6d
    buf[3] = 0x01
    candidates.append(("E: 42 00 6d 01", bytes(buf)))

    # F: 更完整的包头，基于 response 中观察到的 byte[3]=0x08 模式
    buf = bytearray(64)
    buf[0] = 0x42
    buf[1] = 0x00
    buf[2] = 0x00
    buf[3] = 0x08
    buf[4] = 0x01  # IMU category
    buf[5] = 0x6d
    buf[6] = 0x01  # enable
    candidates.append(("F: 42 00 00 08 01 6d 01", bytes(buf)))

    # G: 直接发 0x6d 作为第一个数据字节（HID report 格式）
    # 在 HID 中, byte[0] 是 report ID, 实际数据从 byte[1] 开始
    # 所以 hid_write([0x00, 0x42, ...]) 会把 0x42 作为第一个数据字节
    buf = bytearray(64)
    buf[0] = 0x42
    buf[1] = 0x6d
    buf[2] = 0x00
    buf[3] = 0x00
    buf[4] = 0x01  # enable
    candidates.append(("G: 42 6d 00 00 01", bytes(buf)))

    # H: SunnyVerse 可能用的命令路由格式
    # byte[4:6] = category routing, byte[6] = cmd, byte[7] = arg
    buf = bytearray(64)
    buf[0] = 0x42
    buf[1] = 0x00
    buf[2] = 0x08  # length or type marker
    buf[3] = 0x05  # seen in RE dispatch
    buf[4] = 0x01
    buf[5] = 0x6d
    buf[6] = 0x01  # enable
    candidates.append(("H: 42 00 08 05 01 6d 01", bytes(buf)))

    # I: 最小化 — 只发 cmd 字节
    buf = bytearray(64)
    buf[0] = 0x6d
    buf[1] = 0x01
    candidates.append(("I: raw 6d 01 (no magic)", bytes(buf)))

    # J: 已知能引起响应变化的 0x42 前缀 + cmd 0x6d
    # deep_probe 发现 write([0x00, 0x42]) 产生不同响应
    # 可能 HID report ID = 0x00, 实际数据以 0x42 开头
    buf = bytearray(64)
    buf[0] = 0x42  # magic (data byte 0 after report ID 0x00)
    buf[1] = 0x00
    buf[2] = 0x6d  # cmd at byte[2]
    buf[3] = 0x08
    buf[4] = 0x00
    buf[5] = 0x00
    buf[6] = 0x01  # enable flag
    candidates.append(("J: 42 00 6d 08 00 00 01", bytes(buf)))

    return candidates


def build_other_imu_commands():
    """构建其他可能激活 IMU 的命令"""
    commands = []

    # cmd 0x20: sv_hid_set_imu_frequency — 设置 IMU 采样率可能也激活它
    for freq in [100, 200, 500, 1000]:
        buf = bytearray(64)
        buf[0] = 0x42
        buf[4] = 0x20  # cmd_id
        buf[5] = freq & 0xFF
        buf[6] = (freq >> 8) & 0xFF
        commands.append((f"set_imu_freq({freq}Hz): 42 00 00 00 20 {freq&0xFF:02x}", bytes(buf)))

    # cmd 0x61: sv_hid_set_accel_scale
    buf = bytearray(64)
    buf[0] = 0x42
    buf[4] = 0x61
    buf[5] = 0x01
    commands.append(("set_accel_scale: 42 00 00 00 61 01", bytes(buf)))

    # 不发 cmd 0x49 (set_screen) — 不确定 0x01 是 on 还是 off，可能关屏

    return commands


def phase1_passive_listen(h, report, iface_num):
    """阶段 1: 被动监听，看设备是否已在发送数据"""
    print(f"\n--- 阶段 1: 被动监听接口 {iface_num} (5秒) ---")
    packets = read_packets(h, 5.0)

    summary = {}
    imu_found = False
    for pkt in packets:
        cls = classify_packet(pkt["data"])
        summary[cls] = summary.get(cls, 0) + 1
        if "IMU" in cls:
            imu_found = True

    print(f"  收到 {len(packets)} 个数据包")
    for cls, count in sorted(summary.items(), key=lambda x: -x[1]):
        print(f"    {cls}: {count}")

    if packets:
        print(f"  前3个数据包:")
        for pkt in packets[:3]:
            print(f"    [{pkt['time']:.3f}s] {hexdump(pkt['data'])}")

    report[f"phase1_iface{iface_num}"] = {
        "packets": len(packets),
        "summary": summary,
        "imu_found": imu_found,
        "samples": [hexdump(p["data"]) for p in packets[:5]],
    }
    return imu_found, packets


def phase2_activate_imu(h, report, iface_num):
    """阶段 2: 尝试 cmd 0x6d 候选格式激活 IMU"""
    print(f"\n--- 阶段 2: 尝试 cmd 0x6d 激活 IMU (接口 {iface_num}) ---")

    candidates = build_cmd_0x6d_candidates()
    results = []

    for name, cmd_data in candidates:
        print(f"\n  [{name}]")
        print(f"    发送: {hexdump(cmd_data, 16)}")

        # 清空读缓冲区
        for _ in range(100):
            if not h.read(64):
                break

        # 发送命令（HID write 需要在前面加 report ID 0x00）
        try:
            written = h.write(b'\x00' + cmd_data)
            print(f"    写入: {written} 字节")
        except Exception as e:
            print(f"    写入失败: {e}")
            results.append({"name": name, "error": str(e)})
            continue

        # 等待 200ms 让设备处理
        time.sleep(0.2)

        # 读取 2 秒的响应
        packets = read_packets(h, 2.0)
        imu_packets = []
        other_packets = []

        for pkt in packets:
            cls = classify_packet(pkt["data"])
            if "IMU" in cls:
                imu_packets.append(pkt)
            else:
                other_packets.append(pkt)

        result = {
            "name": name,
            "cmd_hex": hexdump(cmd_data, 16),
            "total_packets": len(packets),
            "imu_packets": len(imu_packets),
            "other_packets": len(other_packets),
        }

        if packets:
            result["first_response"] = hexdump(packets[0]["data"])

        if imu_packets:
            print(f"    *** IMU 数据包发现！{len(imu_packets)} 个 ***")
            result["imu_sample"] = hexdump(imu_packets[0]["data"])

            # 尝试 float32 解码
            for start_off in [8, 6, 10, 12, 4]:
                floats = try_float32_decode(imu_packets[0]["data"], start_off)
                if is_plausible_imu(floats):
                    print(f"    合理的 IMU 数据 (offset={start_off}):")
                    for k, v in floats.items():
                        print(f"      {k}: {v:.6f}")
                    result["imu_decode"] = {
                        "offset": start_off,
                        "values": {k: round(v, 6) for k, v in floats.items()},
                    }
                    break
            else:
                # 尝试所有偏移
                print(f"    IMU 数据包 hexdump: {hexdump(imu_packets[0]['data'])}")
                for start_off in range(2, 32, 2):
                    floats = try_float32_decode(imu_packets[0]["data"], start_off)
                    if is_plausible_imu(floats):
                        print(f"    合理的 IMU 数据 (offset={start_off}):")
                        for k, v in floats.items():
                            print(f"      {k}: {v:.6f}")
                        result["imu_decode"] = {
                            "offset": start_off,
                            "values": {k: round(v, 6) for k, v in floats.items()},
                        }
                        break

            results.append(result)
            report[f"phase2_iface{iface_num}"] = results
            return True, imu_packets

        elif packets:
            print(f"    收到 {len(packets)} 个非 IMU 数据包")
            summary = {}
            for pkt in packets:
                cls = classify_packet(pkt["data"])
                summary[cls] = summary.get(cls, 0) + 1
            for cls, count in sorted(summary.items(), key=lambda x: -x[1]):
                print(f"      {cls}: {count}")
            result["response_summary"] = summary
        else:
            print(f"    无响应")

        results.append(result)

    report[f"phase2_iface{iface_num}"] = results
    return False, []


def phase3_other_commands(h, report, iface_num):
    """阶段 3: 尝试其他可能激活 IMU 的命令"""
    print(f"\n--- 阶段 3: 其他 IMU 相关命令 (接口 {iface_num}) ---")

    commands = build_other_imu_commands()
    results = []

    for name, cmd_data in commands:
        print(f"\n  [{name}]")

        for _ in range(100):
            if not h.read(64):
                break

        try:
            h.write(b'\x00' + cmd_data)
        except Exception as e:
            print(f"    写入失败: {e}")
            results.append({"name": name, "error": str(e)})
            continue

        time.sleep(0.2)
        packets = read_packets(h, 1.5)
        imu_packets = [p for p in packets if "IMU" in classify_packet(p["data"])]

        if imu_packets:
            print(f"    *** IMU 数据包发现！{len(imu_packets)} 个 ***")
            results.append({
                "name": name, "imu_found": True,
                "count": len(imu_packets),
                "sample": hexdump(imu_packets[0]["data"]),
            })
            report[f"phase3_iface{iface_num}"] = results
            return True, imu_packets
        elif packets:
            print(f"    收到 {len(packets)} 个非 IMU 数据包")
        else:
            print(f"    无响应")

        results.append({"name": name, "imu_found": False, "packets": len(packets)})

    report[f"phase3_iface{iface_num}"] = results
    return False, []


SAFE_QUERY_CMDS = [
    0x48,  # get_current_sleep
    0x50,  # get_screen
    0x51,  # get_sn_extend
    0x5f,  # get_screen_rotation
    0x72,  # get_screen_color
]


def phase4_safe_query_scan(h, report, iface_num):
    """阶段 4: 仅扫描已知安全的只读查询命令

    注意：不做 0x00-0xFF 暴力扫描！很多命令 ID 会写入校准数据
    （如 0x5e save_geomagnetic、0x69 set_bias_imu），可能损坏设备。
    只尝试已知的 get_* 查询命令。
    """
    print(f"\n--- 阶段 4: 安全查询命令扫描 (接口 {iface_num}) ---")
    print(f"  仅尝试 {len(SAFE_QUERY_CMDS)} 个已知只读命令...")

    results = []
    imu_found = False

    for cmd_id in SAFE_QUERY_CMDS:
        buf = bytearray(64)
        buf[0] = 0x42
        buf[4] = cmd_id

        for _ in range(50):
            if not h.read(64):
                break

        try:
            h.write(b'\x00' + bytes(buf))
        except Exception:
            continue

        time.sleep(0.1)
        packets = read_packets(h, 0.5)

        has_imu = any("IMU" in classify_packet(p["data"]) for p in packets)
        if has_imu:
            print(f"  *** cmd 0x{cmd_id:02X} → IMU 数据！***")
            imu_pkts = [p for p in packets if "IMU" in classify_packet(p["data"])]
            results.append({
                "cmd_id": f"0x{cmd_id:02X}",
                "imu_found": True,
                "count": len(imu_pkts),
                "sample": hexdump(imu_pkts[0]["data"]),
            })
            imu_found = True
            break
        elif packets:
            results.append({
                "cmd_id": f"0x{cmd_id:02X}",
                "imu_found": False,
                "packets": len(packets),
                "first": hexdump(packets[0]["data"], 16),
            })
            print(f"  cmd 0x{cmd_id:02X}: {len(packets)} 响应")
        else:
            print(f"  cmd 0x{cmd_id:02X}: 无响应")

    report[f"phase4_iface{iface_num}"] = results
    return imu_found


def phase5_hexdump_imu(imu_packets, report):
    """阶段 5: 详细分析 IMU 数据包"""
    print(f"\n--- 阶段 5: IMU 数据包详细分析 ---")
    print(f"  共 {len(imu_packets)} 个 IMU 数据包\n")

    analysis = []

    for i, pkt in enumerate(imu_packets[:20]):
        data = pkt["data"]
        print(f"  #{i:3d} [{pkt['time']:.3f}s] {hexdump(data)}")

        entry = {
            "index": i,
            "time": pkt["time"],
            "hex": hexdump(data),
            "header": {
                "magic": f"0x{data[0]:02X}",
                "byte1": f"0x{data[1]:02X}",
                "byte2": f"0x{data[2]:02X}",
                "byte3": f"0x{data[3]:02X}",
                "category": f"0x{data[4]:02X}",
                "sub": f"0x{data[5]:02X}",
                "byte6": f"0x{data[6]:02X}",
                "byte7": f"0x{data[7]:02X}",
            },
        }

        # 尝试不同偏移的 float32 解码
        best_decode = None
        best_offset = None
        for start_off in range(4, 40, 2):
            floats = try_float32_decode(data, start_off)
            if is_plausible_imu(floats):
                if best_decode is None:
                    best_decode = floats
                    best_offset = start_off

        if best_decode:
            entry["decode_offset"] = best_offset
            entry["values"] = {k: round(v, 6) for k, v in best_decode.items()}
            if i < 5:
                print(f"       float32 @ offset {best_offset}:")
                for k, v in best_decode.items():
                    print(f"         {k}: {v:12.6f}")
        else:
            # 显示所有 float32 候选
            if i < 3:
                print(f"       float32 扫描 (无合理 IMU 匹配):")
                for off in [8, 6, 10, 12]:
                    floats = try_float32_decode(data, off)
                    vals = [f"{v:.4f}" for v in list(floats.values())[:3]]
                    print(f"         @{off}: {', '.join(vals)}")

        analysis.append(entry)

    # 统计
    if len(imu_packets) > 1:
        intervals = []
        for i in range(1, min(len(imu_packets), 100)):
            dt = imu_packets[i]["time"] - imu_packets[i - 1]["time"]
            if dt > 0:
                intervals.append(dt)
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            est_hz = 1.0 / avg_interval if avg_interval > 0 else 0
            print(f"\n  估算采样率: ~{est_hz:.0f} Hz (平均间隔 {avg_interval * 1000:.1f} ms)")
            report["estimated_sample_rate_hz"] = round(est_hz, 1)

    report["phase5_analysis"] = analysis


def main():
    print(f"StarV View IMU 激活探测 (VID=0x{VID:04X} PID=0x{PID:04X})")
    print(f"时间: {datetime.now().isoformat()}")
    print("=" * 60)

    report = {
        "timestamp": datetime.now().isoformat(),
        "vid": f"0x{VID:04X}",
        "pid": f"0x{PID:04X}",
        "phase": "imu_activate_probe",
    }

    devices = enumerate_devices()
    if not devices:
        report["error"] = "设备未找到"
        save_report(report)
        sys.exit(1)

    report["devices"] = [
        {
            "interface": d.get("interface_number"),
            "usage_page": f"0x{d.get('usage_page', 0):04X}",
            "usage": f"0x{d.get('usage', 0):04X}",
            "product": d.get("product_string", ""),
        }
        for d in devices
    ]

    # 在每个接口上尝试
    for iface_num in INTERFACES_TO_TRY:
        print(f"\n{'=' * 60}")
        print(f"探测接口 {iface_num}")
        print("=" * 60)

        h = open_interface(devices, iface_num)
        if h is None:
            continue

        try:
            # Phase 1: 被动监听
            imu_found, imu_packets = phase1_passive_listen(h, report, iface_num)
            if imu_found:
                print(f"\n  *** 接口 {iface_num} 已经在发送 IMU 数据！***")
                phase5_hexdump_imu(imu_packets, report)
                continue

            # Phase 2: cmd 0x6d 候选
            imu_found, imu_packets = phase2_activate_imu(h, report, iface_num)
            if imu_found:
                # 继续读取更多数据
                more_packets = read_packets(h, 5.0)
                all_imu = imu_packets + [p for p in more_packets
                                         if "IMU" in classify_packet(p["data"])]
                phase5_hexdump_imu(all_imu, report)
                continue

            # Phase 3: 其他 IMU 命令
            imu_found, imu_packets = phase3_other_commands(h, report, iface_num)
            if imu_found:
                more_packets = read_packets(h, 5.0)
                all_imu = imu_packets + [p for p in more_packets
                                         if "IMU" in classify_packet(p["data"])]
                phase5_hexdump_imu(all_imu, report)
                continue

            # Phase 4: 安全查询扫描
            if iface_num == 3:
                phase4_safe_query_scan(h, report, iface_num)

        finally:
            h.close()
            print(f"\n  已关闭接口 {iface_num}")

    save_report(report)


def save_report(report):
    # 清理不可序列化的数据
    def clean(obj):
        if isinstance(obj, bytes):
            return hexdump(obj)
        elif isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean(v) for v in obj]
        return obj

    report = clean(report)
    filename = f"imu_probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n{'=' * 60}")
    print(f"探测报告已保存: {filename}")
    print("请将此文件发回分析。")


if __name__ == "__main__":
    main()
