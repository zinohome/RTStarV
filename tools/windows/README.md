# StarV View USB 探测工具（Windows）

## 环境准备

1. 安装 Python 3.10+（https://python.org），安装时勾选 "Add Python to PATH"
2. 打开 PowerShell（按 Win+X 选择"终端"或"PowerShell"），运行：

```powershell
pip install hidapi
```

3. 把 `tools/windows/` 整个文件夹拷贝到 Windows 电脑上

## 探测流程

一共两步，大约 5 分钟。

---

### Step 1：找到 StarV View 的 VID/PID

**1.1 先不要连接眼镜**，在 PowerShell 中 cd 到脚本目录，运行：

```powershell
python usb_enumerate.py > before.txt
```

**1.2 用 USB-C 线连接 StarV View 到电脑**，等待 3 秒让系统识别，再运行：

```powershell
python usb_enumerate.py > after.txt
```

**1.3 对比两个文件**：

```powershell
Compare-Object (Get-Content before.txt) (Get-Content after.txt)
```

输出中带 `=>` 标记的就是新增设备（StarV View）。可能会有多条记录，这是因为同一个设备有多个 USB 接口（显示、音频、传感器等），这是正常的。

**1.4 记下 VID 和 PID**。例如看到 `VID=0x2E04 PID=0x0301`，把这两个十六进制值记下来。所有新增记录的 VID/PID 应该是相同的。

---

### Step 2：全面探测 IMU

**2.1 编辑 `usb_probe.py`**，找到文件开头的这两行，填入 Step 1 记下的值：

```python
VID = 0x0000  # 改成实际值，例如 0x2E04
PID = 0x0000  # 改成实际值，例如 0x0301
```

**2.2 同时编辑 `usb_dump.py`**，找到同样的两行，填入相同的值。

**2.3 运行全面探测**：

```powershell
python usb_probe.py
```

脚本会自动：
- 打开 StarV View 的每个 USB 接口
- 被动监听是否有数据自动推送
- 尝试多种已知的 AR 眼镜 IMU 激活指令
- 记录所有响应

探测过程大约 30 秒，结束后会生成一个 `probe_report_YYYYMMDD_HHMMSS.json` 文件。

**2.4 把以下文件发给开发者：**
- `probe_report_*.json`（探测报告）
- `after.txt`（设备列表）

---

## 常见问题

**Q: pip install hidapi 报错？**
A: 试试 `pip install hidapi --user`，或者用管理员权限运行 PowerShell。

**Q: 运行脚本提示"无法打开设备"？**
A: 右键 PowerShell → "以管理员身份运行"，再试一次。部分 USB HID 设备需要管理员权限。

**Q: 对比后没有新增设备？**
A: 确认 USB-C 线支持数据传输（不是纯充电线）。StarV View 需要 USB-C to USB-C 或 USB-C to USB-A 数据线。

**Q: 探测报告里所有接口都没有数据？**
A: 这也是有用的信息，说明 IMU 可能不走标准 HID 协议，需要其他方式探测。把报告发给开发者分析。
