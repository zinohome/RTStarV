# StarV View USB 探测工具（Windows）

## 环境准备

1. 安装 Python 3.10+（https://python.org）
2. 打开 PowerShell，运行：

```powershell
pip install hidapi
```

## 使用方法

### Step 1：找到 StarV View 的 VID/PID

1. **先不要连接眼镜**，运行：
```powershell
python usb_enumerate.py > before.txt
```

2. **用 USB-C 连接 StarV View**，再运行：
```powershell
python usb_enumerate.py > after.txt
```

3. 对比两个文件，新增的设备就是 StarV View：
```powershell
Compare-Object (Get-Content before.txt) (Get-Content after.txt)
```

4. 记下 VID 和 PID 值。

### Step 2：抓取 IMU 数据

1. 编辑 `usb_dump.py`，填入 Step 1 找到的 VID 和 PID
2. 运行：
```powershell
python usb_dump.py
```

3. 转动眼镜，观察数据包变化，按 Ctrl+C 停止
4. 将输出保存发给我：
```powershell
python usb_dump.py > imu_dump.txt 2>&1
```

### Step 3：全面探测

如果 Step 2 没有数据，运行全面探测脚本：
```powershell
python usb_probe.py
```

它会自动尝试多种激活指令并记录所有响应。
