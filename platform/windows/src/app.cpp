// platform/windows/src/app.cpp
#include "app.h"
#include "d3d11_renderer.h"
#include "screen_layout.h"
#include "screen_capture.h"
#include "hotkey_manager.h"
#include "tray_icon.h"
#include "virtual_display.h"
#include "rtstarv_imu.h"
#include <chrono>

extern LRESULT CALLBACK WndProc(HWND, UINT, WPARAM, LPARAM);

struct App::Modules {
    D3D11Renderer renderer;
    ScreenLayout layout;
    ScreenCapture capture;
    VirtualDisplay vdisplay;
    HotkeyManager hotkeys;
    TrayIcon tray;
};

bool App::init(HINSTANCE hInstance) {
    hinstance_ = hInstance;

    // 注册窗口类
    WNDCLASSEXW wc = {};
    wc.cbSize = sizeof(wc);
    wc.style = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.lpszClassName = L"RTStarVWindow";
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    RegisterClassExW(&wc);

    // 查找 StarV View 显示器并创建全屏窗口
    // 暂时用主显示器的窗口，后续 Task 处理多显示器
    hwnd_ = CreateWindowExW(
        0, L"RTStarVWindow", L"RTStarV",
        WS_POPUP | WS_VISIBLE,
        0, 0, 1920, 1080,
        nullptr, nullptr, hInstance, nullptr);

    if (!hwnd_) return false;

    modules_ = new Modules();

    // 初始化 D3D11
    if (!modules_->renderer.init(hwnd_, 1920, 1080)) return false;

    // 初始化 IMU
    if (rtstarv_init() == 0) {
        state_.imu_connected = true;
        rtstarv_start(200, 0);
    }

    // 初始化虚拟显示器（可选 — 驱动未安装时优雅降级）
    modules_->vdisplay.init();

    // 初始化屏幕捕获
    modules_->capture.init(modules_->renderer.device());

    // 初始化快捷键
    modules_->hotkeys.init(hwnd_);

    // 初始化托盘
    modules_->tray.init(hwnd_, hInstance);

    // 初始化布局
    modules_->layout.set_mode(state_.layout);

    return true;
}

void App::run() {
    MSG msg = {};
    auto last_time = std::chrono::steady_clock::now();

    while (state_.running) {
        while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) { state_.running = false; break; }
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        if (!state_.running) break;

        update();
        render();

        // 限帧 120fps
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration<double>(now - last_time).count();
        if (elapsed < 1.0 / 120.0) {
            auto sleep_ms = static_cast<DWORD>((1.0 / 120.0 - elapsed) * 1000);
            if (sleep_ms > 0) Sleep(sleep_ms);
        }
        last_time = std::chrono::steady_clock::now();
    }
}

void App::update() {
    // 读取 IMU 姿态
    if (state_.imu_connected) {
        RTStarVAttitude att;
        if (rtstarv_get_attitude(&att) == 0) {
            state_.cam_yaw = att.yaw;
            state_.cam_pitch = att.pitch;
            state_.cam_roll = att.roll;
        }
    }

    // 更新布局动画
    modules_->layout.update(0.008f);
}

void App::render() {
    auto& r = modules_->renderer;
    r.begin_frame(0.0f, 0.0f, 0.0f, 1.0f); // 黑色背景

    // 更新摄像机
    r.set_camera(state_.cam_yaw, state_.cam_pitch, state_.cam_roll);

    // 渲染每个虚拟屏幕
    auto screens = modules_->layout.get_screens();
    for (int i = 0; i < static_cast<int>(screens.size()); i++) {
        auto* tex = modules_->capture.get_texture(i);
        bool focused = (i == state_.focus_screen);
        r.draw_screen_quad(screens[i], tex, focused);
    }

    r.end_frame();
}

void App::on_hotkey(int id) {
    switch (id) {
    case 0: // Ctrl+Shift+Space — 居中
        rtstarv_recenter();
        state_.cam_yaw = state_.cam_pitch = state_.cam_roll = 0;
        modules_->layout.recenter();
        break;
    case 1: modules_->layout.set_mode(LayoutMode::Single); state_.layout = LayoutMode::Single; state_.focus_screen = 0; break;
    case 3: modules_->layout.set_mode(LayoutMode::Triple); state_.layout = LayoutMode::Triple; state_.focus_screen = 1; break;
    case 6: modules_->layout.set_mode(LayoutMode::Hex); state_.layout = LayoutMode::Hex; state_.focus_screen = 1; break;
    case 10: // 焦点左移
        if (state_.focus_screen > 0) state_.focus_screen--;
        break;
    case 11: // 焦点右移
        if (state_.focus_screen < static_cast<int>(state_.layout) - 1) state_.focus_screen++;
        break;
    case 12: // 焦点上移（6屏：下排→上排，-3）
        if (state_.layout == LayoutMode::Hex && state_.focus_screen >= 3)
            state_.focus_screen -= 3;
        break;
    case 13: // 焦点下移（6屏：上排→下排，+3）
        if (state_.layout == LayoutMode::Hex && state_.focus_screen < 3)
            state_.focus_screen += 3;
        break;
    }
}

void App::on_tray_command(int cmd) {
    modules_->tray.show_menu(hwnd_, state_.layout);
}

void App::shutdown() {
    if (state_.imu_connected) {
        rtstarv_stop();
        rtstarv_shutdown();
    }
    modules_->tray.destroy();
    modules_->hotkeys.destroy();
    modules_->capture.destroy();
    modules_->vdisplay.destroy();
    modules_->renderer.destroy();
    delete modules_;
    modules_ = nullptr;
    if (hwnd_) DestroyWindow(hwnd_);
}
