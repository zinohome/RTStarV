# RTStarV Windows 构建指南

## 前置要求

- Windows 10/11
- Visual Studio 2022 (Community 版即可)
- CMake 3.16+
- Windows Driver Kit (WDK) — 仅编译虚拟显示器驱动需要

## 构建主应用

```cmd
cd platform\windows
cmake -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
```

生成文件: `build\Release\RTStarV.exe`

## 构建虚拟显示器驱动（可选）

1. 安装 WDK: https://learn.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk
2. 打开 `idd_driver\RTStarVDisplay.sln`
3. 编译 Release x64
4. 启用测试签名: `bcdedit /set testsigning on` (管理员 cmd) 并重启
5. 运行 `idd_driver\install.bat` (管理员)

## 运行

1. 插上 StarV View 眼镜 (USB-C)
2. 运行 `RTStarV.exe`
3. Ctrl+Shift+Space 一键居中

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Shift+Space` | 一键居中 |
| `Ctrl+Shift+1` | 1 屏模式 |
| `Ctrl+Shift+3` | 3 屏模式 |
| `Ctrl+Shift+6` | 6 屏模式 |
| `Ctrl+Shift+←/→` | 焦点左/右切换 |
| `Ctrl+Shift+↑/↓` | 焦点上/下切换（6屏） |
