// platform/windows/src/main.cpp
#include "app.h"

static App* g_app = nullptr;

LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
    case WM_HOTKEY:
        if (g_app) g_app->on_hotkey(static_cast<int>(wParam));
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    case WM_APP + 1: // 托盘消息
        if (LOWORD(lParam) == WM_RBUTTONUP && g_app)
            g_app->on_tray_command(-1); // 弹出菜单
        if (LOWORD(lParam) == WM_LBUTTONDBLCLK && g_app)
            g_app->on_hotkey(0); // 双击 = 居中
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wParam, lParam);
}

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE, LPWSTR, int) {
    App app;
    g_app = &app;

    if (!app.init(hInstance)) {
        MessageBoxW(nullptr, L"RTStarV 初始化失败", L"错误", MB_OK | MB_ICONERROR);
        return 1;
    }

    app.run();
    app.shutdown();
    g_app = nullptr;
    return 0;
}
