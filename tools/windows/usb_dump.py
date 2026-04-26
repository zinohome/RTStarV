#!/usr/bin/env python3
"""
连接 StarV View 并持续 dump 所有 HID 数据包。

用法：
  1. 先运行 usb_enumerate.py 找到 VID/PID
  2. 修改下方 VID 和 PID 值
  3. 运行：python usb_dump.py
  4. 转动眼镜观察数据变化
  5. Ctrl+C 停止
  6. 保存输出：python usb_dump.py > imu_dump.txt 2>&1
"""

import hid
import sys
import time

# ============================================
# >>> 请填入 usb_enumerate.py 找到的实际值 <<<
VID = 0x0000  # 改成实际的 Vendor ID
PID = 0x0000  # 改成实际的 Product ID
# ============================================

def main():
    if VID == 0x0000 or PID == 0x0000:
        print("错误：请先修改脚本中的 VID 和 PID 值！")
        print("运行 usb_enumerate.py 获取实际值。")
        sys.exit(1)

    print(f"正在连接 StarV View (VID=0x{VID:04X} PID=0x{PID:04X})...")

    device = hid.device()
    try:
        device.open(VID, PID)
    except IOError as e:
        print(f"连接失败: {e}")
        print("\n可能的原因：")
        print("  1. VID/PID 不正确")
        print("  2. 眼镜未连接")
        print("  3. 需要管理员权限（右键以管理员身份运行 PowerShell）")
        sys.exit(1)

    device.set_nonblocking(True)

    mfr = device.get_manufacturer_string() or "(unknown)"
    prod = device.get_product_string() or "(unknown)"
    print(f"已连接: {mfr} - {prod}")
    print(f"等待数据包... (Ctrl+C 停止)\n")

    packet_count = 0
    empty_count = 0
    start_time = time.time()

    try:
        while True:
            data = device.read(256)
            if data:
                packet_count += 1
                empty_count = 0
                elapsed = time.time() - start_time
                hex_str = " ".join(f"{b:02x}" for b in data)
                print(f"[{elapsed:8.3f}s] #{packet_count:6d} ({len(data):3d}B) {hex_str}")
            else:
                empty_count += 1
                if empty_count == 1000:
                    print("... 1秒内无数据，设备可能需要激活指令。")
                    print("    请运行 usb_probe.py 尝试激活。")
                time.sleep(0.001)
    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        rate = packet_count / elapsed if elapsed > 0 else 0
        print(f"\n\n统计：")
        print(f"  持续时间: {elapsed:.1f}s")
        print(f"  数据包数: {packet_count}")
        print(f"  平均频率: {rate:.1f} Hz")
    finally:
        device.close()

if __name__ == "__main__":
    main()
