#!/usr/bin/env python3
"""
自动对比连接前后的 USB 设备列表，找出 StarV View。

用法：
  1. 先不要连接眼镜，运行：python usb_diff.py
  2. 按提示连接眼镜，回车继续
  3. 脚本自动对比并显示新增设备
"""

import hid
import time

def get_devices():
    """获取当前所有 HID 设备，返回按 (VID, PID, interface) 去重的字典"""
    devices = {}
    for d in hid.enumerate():
        key = (d['vendor_id'], d['product_id'], d.get('interface_number', -1))
        devices[key] = d
    return devices

def print_device(d):
    vid = d['vendor_id']
    pid = d['product_id']
    mfr = d.get('manufacturer_string', '') or '(unknown)'
    prod = d.get('product_string', '') or '(unknown)'
    iface = d.get('interface_number', -1)
    usage_page = d.get('usage_page', 0)
    usage = d.get('usage', 0)

    print(f"  VID=0x{vid:04X}  PID=0x{pid:04X}  Interface={iface}")
    print(f"  Manufacturer: {mfr}")
    print(f"  Product:      {prod}")
    print(f"  Usage Page:   0x{usage_page:04X}  Usage: 0x{usage:04X}")

def main():
    print("=" * 50)
    print("  StarV View USB 设备探测")
    print("=" * 50)
    print()
    print("请确保 StarV View 眼镜【没有连接】电脑")
    input("准备好后按回车...")

    print("\n扫描当前设备...")
    before = get_devices()
    print(f"发现 {len(before)} 个 HID 接口")

    print("\n现在请用 USB-C 线连接 StarV View 眼镜")
    input("连接好后按回车...")

    print("\n等待系统识别...")
    time.sleep(3)

    print("再次扫描...")
    after = get_devices()
    print(f"发现 {len(after)} 个 HID 接口")

    # 找出新增的设备
    new_keys = set(after.keys()) - set(before.keys())

    if not new_keys:
        print("\n未发现新增设备！")
        print("可能的原因：")
        print("  1. USB-C 线是纯充电线，不支持数据传输")
        print("  2. 眼镜没有通过 HID 协议暴露接口")
        print("  3. 需要安装驱动")
        return

    print(f"\n{'=' * 50}")
    print(f"  发现 {len(new_keys)} 个新增接口（StarV View）")
    print(f"{'=' * 50}\n")

    vid_set = set()
    for key in sorted(new_keys):
        d = after[key]
        print_device(d)
        print()
        vid_set.add((d['vendor_id'], d['product_id']))

    # 总结
    print("=" * 50)
    print("  总结")
    print("=" * 50)
    for vid, pid in vid_set:
        print(f"\n  >>> VID=0x{vid:04X}  PID=0x{pid:04X} <<<")
        print(f"\n  请将这两个值填入 usb_probe.py 和 usb_dump.py 中：")
        print(f"    VID = 0x{vid:04X}")
        print(f"    PID = 0x{pid:04X}")

if __name__ == "__main__":
    main()
