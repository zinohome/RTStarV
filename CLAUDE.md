# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

RTStarV 是 StarV View AR 眼镜的配套主机端应用。**StarV View 本身是纯显示器+IMU，零计算能力**，所有逻辑（渲染、姿态解算、虚拟显示器）均在 host 端运行。

- USB HID：VID=0x2A45（Meizu），PID=0x2050
- 接口 3：命令发送；接口 4：IMU 数据接收
- IMU 数据：float32，200Hz，6DOF + 可选磁力计 9DOF

## 代码架构

```
RTStarV/
├── native/              # 共享 C++ 核心，三端复用
│   ├── include/
│   │   ├── imu_protocol.h    # 协议常量、CRC、命令构建器
│   │   └── rtstarv_imu.h     # C ABI 公共接口（跨平台导出）
│   └── src/
│       ├── imu_parser.*      # USB 包解析（6DOF / 9DOF）
│       ├── usb_device.*      # hidapi 封装（按 interface 打开）
│       ├── imu_reader.*      # 后台读取线程 + 双缓冲
│       ├── attitude_solver.* # 互补滤波姿态解算（alpha=0.98）
│       └── rtstarv_imu.cpp   # C ABI 导出层
├── platform/windows/    # Windows 原生应用（C++17 / D3D11 / Win32）
│   ├── src/             # 主应用逻辑
│   ├── shaders/         # HLSL（screen_vs.hlsl / screen_ps.hlsl）
│   ├── idd_driver/      # IddSampleDriver 虚拟显示器（需 WDK + VS）
│   └── third_party/hidapi/  # hidapi 源码（直接编译进主程序）
├── docs/
│   ├── protocol/starv-view-usb-protocol.md  # USB 协议完整逆向文档
│   └── superpowers/specs/2026-04-27-rtstarv-native-app-design.md  # 架构设计文档
└── tools/windows/       # Python 探测/调试工具（hidapi/hid 直接操作）
```

**架构关键点**：`platform/windows/CMakeLists.txt` 通过相对路径直接编译 `../../native/src/` 下的源文件，不构建独立库，避免跨平台 ABI 问题。Windows 平台同样把 hidapi 源码（`third_party/hidapi/windows/hid.c`）直接编译进主程序，无外部依赖。

## 构建命令

### 共享核心（Parser 测试，Linux/macOS 无 hidapi 时可用）

```bash
cd native
cmake -B build
cmake --build build
ctest --test-dir build          # 运行 11 个解析器单元测试
./build/test_parser             # 直接运行
```

### 共享核心（完整驱动，需 hidapi-libusb）

```bash
cd native
cmake -B build
cmake --build build
```

如找到 hidapi-libusb，会额外生成 `librtstarv_imu.so`。

### Windows 应用（在 Windows 上构建）

```cmd
cd platform\windows
cmake -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
```

生成：`build\Release\RTStarV.exe`

### Windows 应用（Ubuntu 交叉编译，需 mingw-w64）

```bash
cd platform/windows
cmake -B build -DCMAKE_TOOLCHAIN_FILE=toolchain-mingw.cmake
cmake --build build
```

### 虚拟显示器驱动（仅 Windows + WDK + Visual Studio）

打开 `platform/windows/idd_driver/RTStarVDisplay.sln`，编译 Release x64。

## 运行测试

```bash
cd native && cmake -B build && cmake --build build && ctest --test-dir build -V
```

11 个测试覆盖：命令构建（IMU enable/disable/freq/mag）、CRC 校验、真实设备数据包解析。

## USB 协议关键事实

IMU 数据包判定：`buf[0]==0x42 && buf[4]==0x03 && buf[5]==0x02`

- 6DOF：`buf[7]==0x03`，float32 数据从 byte[8] 开始（acc_xyz + gyr_xyz）
- 9DOF：`buf[7]==0x33`，额外 3× float32 在 byte[40]（mag_xyz）

IMU 启用序列（顺序固定）：
1. 设置采样率：`42 00 15 06 03 05 07 FF`（200Hz）
2. 启用 IMU：`42 00 11 06 03 07 01 FF`
3. 启用磁力计（可选）：`42 00 1b 07 03 10 01 00 FF`

命令格式：`42 CRC_H CRC_L [payload...] FF`，CRC = byte[3..N-2] 逐字节相加，高字节在前。

## Windows 应用快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Shift+Space` | 一键居中 |
| `Ctrl+Shift+1/3/6` | 1/3/6 屏模式 |
| `Ctrl+Shift+←/→` | 焦点屏幕左/右切换 |
| `Ctrl+Shift+↑/↓` | 焦点屏幕上/下切换（6屏） |

## 开发注意事项

- 遵循平台原生行为，不加不必要的自定义处理
- 虚拟屏幕布局：球面半径 R=5.0，3屏间隔 ±35°，6屏另加 ±12.5° pitch
- 屏幕捕获用 DXGI Desktop Duplication（零 CPU 拷贝），帧率 60fps，渲染 120fps
- 虚拟显示器（IddSampleDriver）安装需管理员权限 + 测试签名模式
- Python 调试工具在 `tools/windows/`，需 `pip install hidapi`
