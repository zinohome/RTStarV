#!/usr/bin/env python3
"""
磁力计完整数据捕获：dump 全部 64 字节以找到磁力计数据位置。

上次 mag_test.py 只截取了 42 字节，遗漏了 byte[42..63] 区域的磁力计数据。
本脚本捕获完整 64 字节并解码所有可能的 float32。

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


def hexdump_full(data):
    return " ".join(f"{b:02x}" for b in data)


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


def main():
    print("StarV View 磁力计完整数据捕获")
    print("=" * 60)

    report = {"timestamp": datetime.now().isoformat(), "phase": "mag_full_dump"}

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
        # 设置 200Hz + 启用 IMU
        h_cmd.write(b'\x00' + build_cmd_8byte(0x05, 0x07))
        time.sleep(0.2)
        h_cmd.write(b'\x00' + build_cmd_8byte(0x07, 0x01))
        time.sleep(0.5)
        drain(h_data)

        # === Phase 1: 基准 (无磁力计) ===
        print("\n--- 基准 (无磁力计) ---")
        baseline_samples = []
        t0 = time.time()
        while time.time() - t0 < 1.0:
            data = h_data.read(64)
            if data:
                data = bytes(data)
                if len(data) >= 6 and data[0] == 0x42 and data[4] == 0x03 and data[5] == 0x02:
                    baseline_samples.append(data)
            else:
                time.sleep(0.0005)

        print(f"  收到 {len(baseline_samples)} 个 IMU 包")
        for i, d in enumerate(baseline_samples[:3]):
            print(f"  #{i} ({len(d)} bytes): {hexdump_full(d)}")
            print(f"       length_field=0x{d[3]:02x}={d[3]}")

        report["baseline_count"] = len(baseline_samples)
        report["baseline_full"] = [hexdump_full(d) for d in baseline_samples[:5]]

        # === Phase 2: 启用磁力计 ===
        print("\n--- 启用磁力计 ---")
        h_cmd.write(b'\x00' + build_mag_cmd(True))
        time.sleep(1.0)
        drain(h_data)

        mag_samples = []
        t0 = time.time()
        while time.time() - t0 < 2.0:
            data = h_data.read(64)
            if data:
                data = bytes(data)
                if len(data) >= 6 and data[0] == 0x42 and data[4] == 0x03 and data[5] == 0x02:
                    mag_samples.append(data)
            else:
                time.sleep(0.0005)

        print(f"  收到 {len(mag_samples)} 个 IMU 包")
        for i, d in enumerate(mag_samples[:5]):
            print(f"  #{i} ({len(d)} bytes): {hexdump_full(d)}")
            print(f"       length_field=0x{d[3]:02x}={d[3]}")

            # 解码所有可能的 float32
            print(f"       --- float32 解码 ---")
            for off in range(8, min(len(d) - 3, 60), 4):
                val = struct.unpack_from("<f", d, off)[0]
                label = ""
                if 8 <= off <= 20:
                    names = ["acc_x", "acc_y", "acc_z", "gyr_x", "gyr_y", "gyr_z"]
                    label = f" ({names[(off-8)//4]})"
                elif off == 32:
                    ts = struct.unpack_from("<I", d, off)[0]
                    label = f" (timestamp={ts})"
                print(f"         byte[{off:2d}..{off+3:2d}]: {val:12.6f}{label}")

        report["mag_count"] = len(mag_samples)
        report["mag_full"] = [hexdump_full(d) for d in mag_samples[:10]]

        # === 逐字节对比 ===
        if baseline_samples and mag_samples:
            print("\n--- 逐字节差异分析 ---")
            b = baseline_samples[0]
            m = mag_samples[0]
            for i in range(max(len(b), len(m))):
                bv = b[i] if i < len(b) else 0
                mv = m[i] if i < len(m) else 0
                if bv != mv:
                    print(f"  byte[{i:2d}]: 基准=0x{bv:02x}  磁力=0x{mv:02x}")

            # FF 终止符位置
            for label, d in [("基准", b), ("磁力", m)]:
                ff_pos = [i for i in range(len(d)) if d[i] == 0xFF]
                print(f"  {label} FF 位置: {ff_pos}")

    finally:
        h_cmd.write(b'\x00' + build_mag_cmd(False))
        time.sleep(0.1)
        h_cmd.write(b'\x00' + build_cmd_8byte(0x07, 0x00))
        h_cmd.close()
        h_data.close()

    filename = f"mag_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n报告已保存: {filename}")


if __name__ == "__main__":
    main()
