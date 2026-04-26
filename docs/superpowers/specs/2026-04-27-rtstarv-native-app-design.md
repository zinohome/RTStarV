# RTStarV 原生跨平台应用 — 设计文档

> 日期：2026-04-27
> 前置文档：`2026-04-26-rtstarv-ar-workspace-design.md`（原始设计，Unity 方案）
> 本文档替代 Unity 方案，改为纯原生实现

---

## 1. 方案变更

原设计采用 Unity 跨平台方案。经评估，改为纯原生方案：

| 维度 | Unity 方案 | 原生方案（本文档） |
|------|-----------|-------------------|
| Windows | Unity + C++ 插件 | C++ / DirectX 11 / Win32 |
| macOS | Unity + C++ 插件 | Swift / Metal / Cocoa |
| Android | Unity + C++ 插件 | Kotlin / OpenGL ES |
| IMU 驱动 | C++ hidapi（共享） | C++ hidapi（共享） |
| 构建依赖 | Unity Editor | MinGW（交叉编译）/ Xcode / Android Studio |

**变更理由**：
1. 开发环境在 Ubuntu，无法创建/验证 Unity 项目
2. 原生方案性能最优（D3D11 直接渲染、DXGI 零拷贝捕获）
3. 无 Unity 运行时依赖，交付物更小
4. 核心算法（IMU 解析、姿态解算）已是 C++，三端共享

---

## 2. 系统架构

```
┌──────────────────────────────────────────────────────┐
│                   平台应用层                           │
│                                                      │
│  Windows              macOS              Android     │
│  D3D11 渲染           Metal 渲染         OpenGL ES   │
│  DXGI 捕获            ScreenCaptureKit   MediaProj.  │
│  IddSampleDriver      CGVirtualDisplay   USB Host    │
│  Win32 快捷键/托盘     Cocoa 快捷键/菜单栏  触摸板 UI   │
│                                                      │
├──────────────────────────────────────────────────────┤
│                   共享 C++ 核心                        │
│                                                      │
│  imu_protocol.h      协议常量、命令构建器              │
│  imu_parser.cpp       IMU 数据包解析（6DOF + 9DOF）   │
│  attitude_solver.cpp  互补滤波姿态解算                 │
│  usb_device.cpp       hidapi 封装                    │
│  imu_reader.cpp       后台读取线程 + 双缓冲            │
│  rtstarv_imu.h        C ABI 导出接口                  │
│                                                      │
└──────────────────────────────────────────────────────┘
         │ USB-C (DP Alt Mode + USB HID)
┌────────┴────────┐
│   StarV View    │
│   1080p 120Hz   │
│   IMU 200Hz     │
└─────────────────┘
```

---

## 3. Windows 原生应用

### 3.1 核心循环

```
main() {
    初始化 Win32 窗口（StarV View 显示器上全屏）
    初始化 D3D11 设备 + SwapChain (1920×1080 @ 120Hz)
    初始化 IMU 驱动（hidapi）
    初始化 DXGI 屏幕捕获
    初始化虚拟显示器（IddSampleDriver）
    注册全局热键
    创建系统托盘图标

    while (running) {
        处理 Win32 消息（热键、托盘事件）
        读取 IMU 姿态 → 更新摄像机旋转
        AcquireNextFrame → 更新屏幕纹理
        渲染 3D 场景（虚拟屏幕 quad）
        Present → 输出到 StarV View
    }

    清理（销毁虚拟显示器、停止 IMU、释放 D3D11）
}
```

### 3.2 D3D11 渲染

- SwapChain 绑定到 StarV View 对应的 DXGI Output
- 场景只包含：黑色背景 + N 个带纹理的 quad（虚拟屏幕）
- 每个 quad = 4 顶点 + 2 三角形，纹理来自屏幕捕获
- 摄像机：透视投影，位于原点，只旋转（yaw/pitch/roll 来自 IMU）
- Shader 极简：顶点变换（MVP 矩阵）+ 纹理采样，无光照

### 3.3 虚拟屏幕布局

球面定位，所有屏幕在半径 R=5.0 单位的球面上，面朝原点。

**1 屏模式**：
- 屏幕 0：yaw=0°, pitch=0°

**3 屏模式**：
- 屏幕 0：yaw=-35°, pitch=0°（左）
- 屏幕 1：yaw=0°, pitch=0°（中）
- 屏幕 2：yaw=+35°, pitch=0°（右）

**6 屏模式**：
- 上排：yaw={-35°, 0°, +35°}, pitch=+12.5°
- 下排：yaw={-35°, 0°, +35°}, pitch=-12.5°

每个屏幕视角宽度约 30°（FOV 43.5° 减去 5° 间隙）。

布局切换时先自动居中，屏幕以 slerp 动画滑入（~300ms）。

### 3.4 屏幕捕获（DXGI Desktop Duplication）

- 每个虚拟显示器对应一个 `IDXGIOutputDuplication`
- `AcquireNextFrame()` 返回 `ID3D11Texture2D`，直接作为 quad 纹理（零 CPU 拷贝）
- 捕获 60fps（显示器刷新率），渲染 120fps（中间帧复用上一帧纹理）
- 视野外屏幕暂停捕获，节省 GPU

### 3.5 虚拟显示器（IddSampleDriver）

- 基于微软 IddSampleDriver 示例修改
- KMDF 内核驱动，需 WDK + Visual Studio 编译
- 通过 DeviceIoControl 控制：创建/销毁虚拟显示器
- 每个虚拟显示器 1920×1080 @ 60Hz
- 安装需管理员权限 + 测试签名模式（`bcdedit /set testsigning on`）

用户端操作：
1. 首次运行 `install.bat` 安装驱动
2. 之后应用自动管理虚拟显示器生命周期

### 3.6 快捷键与系统托盘

**全局热键**（`RegisterHotKey()`）：

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Shift+Space` | 一键居中 |
| `Ctrl+Shift+1` | 1 屏模式 |
| `Ctrl+Shift+3` | 3 屏模式 |
| `Ctrl+Shift+6` | 6 屏模式 |
| `Ctrl+Shift+←/→` | 焦点左/右切换 |
| `Ctrl+Shift+↑/↓` | 焦点上/下切换（6屏） |

**焦点屏幕**：
- 当前焦点屏幕显示微弱白色边框
- 切换焦点时 `SetCursorPos()` 跳转鼠标到对应虚拟显示器中央

**系统托盘**：
- 最小化到托盘运行（主显示器不占空间）
- 右键菜单：居中 / 1·3·6 屏 / 退出
- 双击图标 = 一键居中

### 3.7 设备断连处理

- USB 断开 → 摄像机冻结在最后姿态，托盘弹气泡通知
- USB 重连 → 自动重新初始化 IMU 流
- StarV View DP 断开 → 应用暂停渲染，等待重连

---

## 4. macOS 原生应用

### 4.1 技术栈

- Swift + Metal（渲染）
- ScreenCaptureKit（屏幕捕获，macOS 12.3+）
- CGVirtualDisplay（虚拟显示器，macOS 13+）
- hidapi（IMU，通过 ObjC++ 桥接调 C ABI）
- Cocoa（菜单栏应用、全局快捷键）

### 4.2 与 Windows 版对应关系

| Windows | macOS |
|---------|-------|
| D3D11 | Metal |
| DXGI Desktop Duplication | ScreenCaptureKit |
| IddSampleDriver (KMDF) | CGVirtualDisplay (用户态 API) |
| RegisterHotKey | CGEventTap / MASShortcut |
| 系统托盘 | NSStatusBarItem (菜单栏) |
| Win32 窗口 | NSWindow (全屏到 StarV View) |

### 4.3 macOS 优势

- CGVirtualDisplay 是纯用户态 API，比 IddSampleDriver 简单得多
- 无需内核驱动、无需签名、无需管理员权限
- ScreenCaptureKit 支持 GPU 直传

---

## 5. Android 原生应用

### 5.1 技术栈

- Kotlin + OpenGL ES 3.0（渲染）
- MediaProjection API（屏幕捕获）
- Android USB Host API（连接 StarV View HID）
- JNI（桥接 C++ IMU 驱动）

### 5.2 手机端专属功能

**触摸板控制器**：
- 手机屏幕作为触摸板，控制眼镜中的光标
- 单指滑动 → 移动光标
- 单指点击 → 左键
- 长按 → 右键
- 双指滑动 → 滚动

**桌面模式**：
- 启用 Android 桌面模式（DeX 类似），横屏桌面化
- MediaProjection 捕获桌面内容

**UI 布局**：
```
┌──────────────┐
│ 跟头 | 悬停   │  ← 顶部模式切换
├──────────────┤
│              │
│   触摸区域    │  ← 主操作区
│              │
├──────────────┤
│   居中按钮    │  ← 底部
└──────────────┘
```

### 5.3 与电脑端差异

| 电脑端 | 手机端 |
|--------|--------|
| 悬停模式唯一 | 悬停 + 跟头两种模式 |
| 多屏（1/3/6） | 单屏 |
| 全局快捷键 | 触摸板 + 按钮 |
| 虚拟显示器 | MediaProjection |
| 鼠标键盘操作 | 触摸映射 |

---

## 6. 共享 C++ 核心

```
native/
├── include/
│   ├── imu_protocol.h           # 协议常量、CRC、命令构建器
│   └── rtstarv_imu.h            # C ABI 公共接口
├── src/
│   ├── imu_parser.h/cpp         # 包解析（6DOF + 9DOF 磁力计）
│   ├── usb_device.h/cpp         # hidapi 封装（按 interface 打开）
│   ├── imu_reader.h/cpp         # 后台线程 + 双缓冲
│   ├── attitude_solver.h/cpp    # 互补滤波（alpha=0.98）
│   └── rtstarv_imu.cpp          # C ABI 导出层
└── tests/
    └── test_parser.cpp          # 11 个测试，真实设备数据验证
```

已完成并验证：
- USB 协议完整逆向（VID=0x2A45, PID=0x2050）
- 6DOF + 磁力计 9DOF 数据解析
- 5 级采样率控制（12.5-200 Hz）
- 命令构建器 + CRC 校验
- 单元测试全部通过

---

## 7. 文件结构总览

```
RTStarV/
├── native/                          # 共享 C++ 核心（已完成）
│   ├── include/
│   ├── src/
│   └── tests/
├── platform/
│   ├── windows/
│   │   ├── CMakeLists.txt
│   │   ├── toolchain-mingw.cmake
│   │   ├── src/
│   │   │   ├── main.cpp             # 入口 + 主循环
│   │   │   ├── d3d11_renderer.cpp   # D3D11 渲染
│   │   │   ├── screen_capture.cpp   # DXGI 屏幕捕获
│   │   │   ├── virtual_display.cpp  # IddSampleDriver 控制
│   │   │   ├── screen_layout.cpp    # 虚拟屏幕布局管理
│   │   │   ├── hotkey_manager.cpp   # 全局快捷键
│   │   │   ├── tray_icon.cpp        # 系统托盘
│   │   │   └── app.cpp              # 应用状态机
│   │   ├── shaders/
│   │   │   ├── screen_vs.hlsl
│   │   │   └── screen_ps.hlsl
│   │   ├── idd_driver/              # IddSampleDriver（VS + WDK 编译）
│   │   │   ├── RTStarVDisplay.sln
│   │   │   ├── driver/
│   │   │   └── install.bat
│   │   └── resources/
│   │       ├── app.ico
│   │       └── app.rc
│   ├── macos/
│   │   ├── RTStarV.xcodeproj
│   │   └── RTStarV/
│   │       ├── main.swift
│   │       ├── MetalRenderer.swift
│   │       ├── ScreenCapture.swift
│   │       ├── VirtualDisplay.swift
│   │       ├── HotkeyManager.swift
│   │       ├── StatusBarApp.swift
│   │       ├── Shaders.metal
│   │       └── IMUBridge.mm
│   └── android/
│       ├── app/src/main/
│       │   ├── java/.../
│       │   │   ├── MainActivity.kt
│       │   │   ├── TouchpadView.kt
│       │   │   ├── GLRenderer.kt
│       │   │   ├── ScreenCaptureService.kt
│       │   │   └── UsbImuManager.kt
│       │   ├── cpp/native-lib.cpp
│       │   └── res/layout/
│       └── build.gradle
├── docs/
│   ├── protocol/
│   └── superpowers/
└── tools/
```

---

## 8. 开发顺序

1. **Windows 版**：Ubuntu 上交叉编译主程序 + 提供 IddSampleDriver VS 项目
2. **macOS 版**：提供完整 Xcode 项目源码
3. **Android 版**：提供完整 Android Studio 项目源码

---

## 9. 性能目标

| 指标 | 目标 |
|------|------|
| IMU 采样率 | 200 Hz |
| IMU → 渲染延迟 | < 20ms |
| 渲染帧率 | 120 fps（StarV View 刷新率）|
| 屏幕捕获帧率 | 60 fps |
| 一键居中动画 | 200ms |
| 布局切换动画 | 300ms |
