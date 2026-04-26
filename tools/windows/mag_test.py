#!/usr/bin/env python3
"""
磁力计测试：启用磁力计后观察 IMU 数据包是否包含额外数据。

从 sv_hid_set_mag_sensor (0x53094) 逆向:
  cmd 0x15, 9 字节包: 42 SS CC 07 03 10 XX 00 FF
  CRC 覆盖 byte[3..7] (5 字节)

测试步骤:
  1. 设置 200 Hz + 启用 IMU → 读取基准数据（无磁力计）
  2. 启用磁力计 → 读取数据，对比差异
  3. 禁用磁力计 + 禁用 IMU

依赖: pip install hidapi
"""

import sys
import time
import struct
import json
from datetime import datetime

try:
    import hid
except ImportError:
    print("错误：pip install hidapi")
    sys.exit(1)

VID = 0x2A45
PID = 0x2050


def calculate_crc(data, start, length):
    s = 0
    for i in range(start, start + length):
        s = (s + data[i]) & 0xFFFF
    return (s >> 8) & 0xFF, s & 0xFF


def build_cmd_8byte(r3, value):
    """8 字节命令: 42 SS CC 06 03 RR VV FF"""
    buf = bytearray(64)
    buf[0] = 0x42
    buf[3] = 0x06
    buf[4] = 0x03
    buf[5] = r3
    buf[6] = value
    buf[7] = 0xFF
    buf[1], buf[2] = calculate_crc(buf, 3, 4)
    return bytes(buf)


def build_mag_cmd(enable):
    """9 字节磁力计命令: 42 SS CC 07 03 10 XX 00 FF"""
    buf = bytearray(64)
    buf[0] = 0x42
    buf[3] = 0x07
    buf[4] = 0x03
    buf[5] = 0x10
    buf[6] = 0x01 if enable else 0x00
    buf[7] = 0x00
    buf[8] = 0xFF
    buf[1], buf[2] = calculate_crc(buf, 3, 5)
    return bytes(buf)


def hexdump(data, n=42):
    return " ".join(f"{b:02x}" for b in data[:n])


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


def drain(h):
    for _ in range(500):
        if not h.read(64):
            break


def read_all_packets(h, duration_s):
    packets = []
    t0 = time.time()
    while time.time() - t0 < duration_s:
        data = h.read(64)
        if data:
            packets.append({"time": time.time() - t0, "data": bytes(data)})
        else:
            time.sleep(0.0005)
    return packets


def classify(data):
    if len(data) < 6 or data[0] != 0x42:
        return "non_starv"
    return f"cat=0x{data[4]:02X},sub=0x{data[5]:02X}"


def main():
    print(f"StarV View 磁力计测试")
    print("=" * 60)

    report = {"timestamp": datetime.now().isoformat(), "phase": "mag_test"}

    devices = hid.enumerate(VID, PID)
    if not devices:
        print("未找到设备！")
        sys.exit(1)

    h_cmd = open_interface(devices, 3)
    h_data = open_interface(devices, 4)
    if not h_cmd or not h_data:
        print("无法打开接口")
        sys.exit(1)

    try:
        # === Phase 1: 基准 (无磁力计) ===
        print("\n--- Phase 1: 基准测试 (无磁力计) ---")
        h_cmd.write(b'\x00' + build_cmd_8byte(0x05, 0x07))  # 200 Hz
        time.sleep(0.2)
        h_cmd.write(b'\x00' + build_cmd_8byte(0x07, 0x01))  # IMU enable
        time.sleep(0.5)
        drain(h_data)

        pkts_base = read_all_packets(h_data, 3.0)
        imu_base = [p for p in pkts_base if len(p["data"]) >= 6
                     and p["data"][0] == 0x42 and p["data"][4] == 0x03 and p["data"][5] == 0x02]

        print(f"  总包数: {len(pkts_base)}, IMU 包: {len(imu_base)}")

        # 分类所有包类型
        types = {}
        for p in pkts_base:
            t = classify(p["data"])
            types[t] = types.get(t, 0) + 1
        print(f"  包类型: {types}")

        if imu_base:
            d = imu_base[0]["data"]
            print(f"  基准包 hexdump: {hexdump(d)}")
            print(f"  基准包长度（非零字节）: {sum(1 for b in d if b != 0)}")
            report["baseline_sample"] = hexdump(d)
            report["baseline_nonzero"] = sum(1 for b in d if b != 0)

        # === Phase 2: 启用磁力计 ===
        print("\n--- Phase 2: 启用磁力计 ---")
        mag_enable = build_mag_cmd(True)
        print(f"  发送: {hexdump(mag_enable, 9)}")
        h_cmd.write(b'\x00' + mag_enable)
        time.sleep(1.0)
        drain(h_data)

        pkts_mag = read_all_packets(h_data, 3.0)
        imu_mag = [p for p in pkts_mag if len(p["data"]) >= 6
                    and p["data"][0] == 0x42 and p["data"][4] == 0x03 and p["data"][5] == 0x02]

        # 检查是否有新的包类型
        types_mag = {}
        for p in pkts_mag:
            t = classify(p["data"])
            types_mag[t] = types_mag.get(t, 0) + 1
        print(f"  总包数: {len(pkts_mag)}, IMU 包: {len(imu_mag)}")
        print(f"  包类型: {types_mag}")

        new_types = set(types_mag.keys()) - set(types.keys())
        if new_types:
            print(f"  *** 新包类型: {new_types} ***")
            for p in pkts_mag:
                if classify(p["data"]) in new_types:
                    print(f"      {hexdump(p['data'])}")
                    break

        if imu_mag:
            d = imu_mag[0]["data"]
            print(f"  磁力计包 hexdump: {hexdump(d)}")
            print(f"  磁力计包长度（非零字节）: {sum(1 for b in d if b != 0)}")
            report["mag_sample"] = hexdump(d)
            report["mag_nonzero"] = sum(1 for b in d if b != 0)

            # 对比差异
            if imu_base:
                d_base = imu_base[0]["data"]
                diffs = []
                for i in range(min(len(d), len(d_base))):
                    if d[i] != d_base[i]:
                        diffs.append(i)
                print(f"  与基准差异的字节偏移: {diffs[:20]}")

                # 检查 byte[32+] 区域是否有新数据
                base_tail = sum(1 for b in d_base[32:] if b != 0)
                mag_tail = sum(1 for b in d[32:] if b != 0)
                print(f"  byte[32+] 非零字节: 基准={base_tail}, 磁力计={mag_tail}")

                if mag_tail > base_tail:
                    print(f"  *** 磁力计数据可能在 byte[32+] 区域！***")
                    # 尝试解码额外的 float32
                    for off in [32, 36, 40]:
                        if off + 4 <= len(d):
                            val = struct.unpack_from("<f", d, off)[0]
                            val_b = struct.unpack_from("<f", d_base, off)[0]
                            print(f"    byte[{off}]: 基准={val_b:.6f}, 磁力计={val:.6f}")

        # 打印 5 个磁力计模式的包供对比
        print(f"\n  磁力计模式前 5 包:")
        for i, p in enumerate(imu_mag[:5]):
            print(f"    #{i}: {hexdump(p['data'])}")

        report["baseline_types"] = types
        report["mag_types"] = types_mag

        # === Phase 3: 检查所有接口 ===
        print("\n--- Phase 3: 检查接口 5 是否有磁力计数据 ---")
        h5 = open_interface(devices, 5)
        if h5:
            pkts_5 = read_all_packets(h5, 2.0)
            if pkts_5:
                print(f"  接口 5 收到 {len(pkts_5)} 包")
                for p in pkts_5[:3]:
                    print(f"    {hexdump(p['data'])}")
            else:
                print(f"  接口 5 无数据")
            h5.close()

    finally:
        # 清理
        h_cmd.write(b'\x00' + build_mag_cmd(False))
        time.sleep(0.1)
        h_cmd.write(b'\x00' + build_cmd_8byte(0x07, 0x00))
        h_cmd.close()
        h_data.close()

    filename = f"mag_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n报告已保存: {filename}")


if __name__ == "__main__":
    main()
