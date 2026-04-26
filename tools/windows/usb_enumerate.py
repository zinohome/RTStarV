#!/usr/bin/env python3
"""
枚举所有 USB HID 设备，用于找到 StarV View 的 VID/PID。

用法：
  1. 眼镜未连接时运行一次：python usb_enumerate.py > before.txt
  2. 连接眼镜后再运行：python usb_enumerate.py > after.txt
  3. 对比两个文件找出新增设备
"""

import hid
import sys

def main():
    devices = hid.enumerate()
    print(f"共发现 {len(devices)} 个 HID 设备\n")
    print("=" * 70)

    for i, d in enumerate(devices):
        vid = d['vendor_id']
        pid = d['product_id']
        mfr = d.get('manufacturer_string', '') or '(unknown)'
        prod = d.get('product_string', '') or '(unknown)'
        iface = d.get('interface_number', -1)
        usage_page = d.get('usage_page', 0)
        usage = d.get('usage', 0)

        print(f"[{i+1}] VID=0x{vid:04X}  PID=0x{pid:04X}")
        print(f"    Manufacturer: {mfr}")
        print(f"    Product:      {prod}")
        print(f"    Interface:    {iface}")
        print(f"    Usage Page:   0x{usage_page:04X}")
        print(f"    Usage:        0x{usage:04X}")
        print(f"    Path:         {d['path']}")
        print("-" * 70)

if __name__ == "__main__":
    main()
