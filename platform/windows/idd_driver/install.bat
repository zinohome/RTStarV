@echo off
:: platform/windows/idd_driver/install.bat
:: 以管理员权限运行此脚本安装虚拟显示器驱动

echo RTStarV Virtual Display Driver Installer
echo ==========================================

:: 检查管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 请右键以管理员身份运行此脚本！
    pause
    exit /b 1
)

:: 检查测试签名模式
bcdedit /enum {current} | findstr /i "testsigning.*Yes" >nul 2>&1
if %errorlevel% neq 0 (
    echo 需要启用测试签名模式:
    echo   bcdedit /set testsigning on
    echo 然后重启电脑。
    pause
    exit /b 1
)

:: 安装驱动
echo 安装驱动...
devcon install RTStarVDisplay.inf Root\RTStarVDisplay

if %errorlevel% equ 0 (
    echo 安装成功！
) else (
    echo 安装失败，错误码: %errorlevel%
)

pause
