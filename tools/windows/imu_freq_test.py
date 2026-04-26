#!/usr/bin/env python3
"""
IMU 采样率测试：发送 cmd 0x20 设置频率后读取数据验证。

已确认的频率编码 (从 libsv_hid.so 逆向):
  code 0x07 = 200 Hz
  code 0x08 = 100 Hz
  code 0x09 = 50 Hz
  code 0x0A = 25 Hz
  code 0x0B = 12.5 Hz (默认)

命令格式: 42 SS CC 06 03 05 XX FF
  (SS CC = byte[3..6] 的校验和)

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

FREQ_CODES = {
    200: 0x07,
    100: 0x08,
    50:  0x09,
    25:  0x0A,
    12:  0x0B,
}


def calculate_crc(data, start, length):
    s = 0
    for i in range(start, start + length):
        s = (s + data[i]) & 0xFFFF
    return (s >> 8) & 0xFF, s & 0xFF


def build_cmd(routing_byte3, value_byte):
    """构建 8 字节命令包: 42 SS CC 06 03 RR VV FF"""
    buf = bytearray(64)
    buf[0] = 0x42
    buf[3] = 0x06
    buf[4] = 0x03
    buf[5] = routing_byte3
    buf[6] = value_byte
    buf[7] = 0xFF
    buf[1], buf[2] = calculate_crc(buf, 3, 4)
    return bytes(buf)


def build_imu_enable():
    return build_cmd(0x07, 0x01)


def build_imu_disable():
    return build_cmd(0x07, 0x00)


def build_set_freq(freq_hz):
    code = FREQ_CODES.get(freq_hz)
    if code is None:
        raise ValueError(f"不支持的频率: {freq_hz} Hz (支持: {list(FREQ_CODES.keys())})")
    return build_cmd(0x05, code)


def hexdump(data, n=8):
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


def read_imu_packets(h, duration_s):
    """读取指定时间内的 IMU 数据包"""
    packets = []
    t0 = time.time()
    while time.time() - t0 < duration_s:
        data = h.read(64)
        if data:
            data = bytes(data)
            if len(data) >= 6 and data[0] == 0x42 and data[4] == 0x03 and data[5] == 0x02:
                packets.append({"time": time.time() - t0, "data": data})
        else:
            time.sleep(0.0005)
    return packets


def measure_rate(packets):
    if len(packets) < 2:
        return 0
    duration = packets[-1]["time"] - packets[0]["time"]
    if duration <= 0:
        return 0
    return (len(packets) - 1) / duration


def decode_imu(data):
    if len(data) < 32:
        return None
    vals = struct.unpack_from("<6f", data, 8)
    return {
        "acc_x": vals[0], "acc_y": vals[1], "acc_z": vals[2],
        "gyr_x": vals[3], "gyr_y": vals[4], "gyr_z": vals[5],
    }


def main():
    print(f"StarV View IMU 采样率测试")
    print(f"时间: {datetime.now().isoformat()}")
    print("=" * 60)

    report = {"timestamp": datetime.now().isoformat(), "phase": "freq_test"}

    devices = hid.enumerate(VID, PID)
    if not devices:
        print("未找到设备！")
        sys.exit(1)

    # 打开两个接口
    h_cmd = open_interface(devices, 3)
    h_data = open_interface(devices, 4)
    if not h_cmd or not h_data:
        print("无法打开接口 3 和 4")
        sys.exit(1)

    try:
        results = []

        for freq_hz in [12, 25, 50, 100, 200]:
            print(f"\n--- 测试 {freq_hz} Hz ---")

            # 1. 先禁用 IMU
            cmd_disable = build_imu_disable()
            h_cmd.write(b'\x00' + cmd_disable)
            time.sleep(0.3)
            drain(h_data)

            # 2. 设置频率
            cmd_freq = build_set_freq(freq_hz)
            print(f"  设置频率: {hexdump(cmd_freq)}")
            h_cmd.write(b'\x00' + cmd_freq)
            time.sleep(0.3)

            # 3. 启用 IMU
            cmd_enable = build_imu_enable()
            print(f"  启用 IMU: {hexdump(cmd_enable)}")
            h_cmd.write(b'\x00' + cmd_enable)
            time.sleep(0.5)

            # 4. 读取 5 秒数据
            drain(h_data)
            packets = read_imu_packets(h_data, 5.0)
            rate = measure_rate(packets)

            print(f"  收到: {len(packets)} 个 IMU 包")
            print(f"  实测采样率: {rate:.1f} Hz")

            # 解码一个样本
            if packets:
                vals = decode_imu(packets[0]["data"])
                if vals:
                    acc_mag = (vals["acc_x"]**2 + vals["acc_y"]**2 + vals["acc_z"]**2)**0.5
                    print(f"  样本 |acc|: {acc_mag:.2f} m/s²")

            results.append({
                "target_hz": freq_hz,
                "code": f"0x{FREQ_CODES[freq_hz]:02X}",
                "cmd": hexdump(cmd_freq),
                "packets": len(packets),
                "measured_hz": round(rate, 1),
            })

        # 5. 完成，禁用 IMU
        h_cmd.write(b'\x00' + build_imu_disable())

        report["results"] = results
        print(f"\n{'=' * 60}")
        print("汇总:")
        print(f"{'目标 Hz':>8s} {'编码':>6s} {'包数':>6s} {'实测 Hz':>10s}")
        print("-" * 36)
        for r in results:
            print(f"{r['target_hz']:>8d} {r['code']:>6s} {r['packets']:>6d} {r['measured_hz']:>10.1f}")

    finally:
        h_cmd.close()
        h_data.close()

    filename = f"freq_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n报告已保存: {filename}")


if __name__ == "__main__":
    main()
